"""SUMMARY: The scope step (D-028): our judgement of which entities belong to
which sponsor. Each entity found by a sponsor's GLEIF search gets one label,
In, Review or Out, with its reason, stored as a ScopeDecision (D-036).

It reads only the shared fact list, so every label traces back to sourced
facts. For each entity it uses the latest GLEIF observation (D-051). The
labels are worked out afresh on every run, on any day.

The tests, in order (the first one that decides, wins):
1. Name (D-047): the legal name contains one of the sponsor's name forms as
   a whole word -> In, unless GLEIF says an outside company manages it -> Review.
2. Care of (D-048, D-050): an address is care of a sponsor company:
   - a company that is In by name, or a care-of name Bruno approved -> In
   - a care-of name Bruno rejected -> Out
   - a care-of name not in our data -> Review (and onto the care-of name list)
3. Street (D-049): the sponsor's word appears only in a street or building
   name -> Out.
4. Former name: only another name (e.g. a previous legal name) matches -> Review.
5. Anything else the search caught -> Review.

Bruno's hand decisions (config/scope_reviews.toml, D-052) are then applied as
second ScopeDecisions that revise the automatic ones (D-037).

It also writes docs/scope-review.md: the review lists for Bruno.
"""

# Pattern matching, used for names and addresses.
import re
# Python's built-in reader for TOML settings files.
import tomllib
# Lets us strip accents (e.g. "à" -> "a") so names compare fairly.
import unicodedata
# Groups things into lists by a key, and counts things.
from collections import Counter, defaultdict
# A tidy way of working with file and folder paths.
from pathlib import Path

# The shared fact format: helpers to build rows.
from seisa_kg.facts.model import fact, iri, literal

# The project's top folder: this file's folder, then up three levels (facts → seisa_kg → src → project).
PROJECT_ROOT = Path(__file__).resolve().parents[3]
# The sponsor settings: name forms and search words.
SPONSORS_PATH = PROJECT_ROOT / "config" / "sponsors.toml"
# Bruno's hand decisions (D-052).
REVIEWS_PATH = PROJECT_ROOT / "config" / "scope_reviews.toml"
# The review lists written for Bruno.
REPORT_PATH = PROJECT_ROOT / "docs" / "scope-review.md"
# The countries where name matches are usual; matches elsewhere are listed for Bruno to skim (D-053).
USUAL_COUNTRIES = ("GB", "GG", "JE", "LU", "IE")
# Words that mark a street or building, for the street test (D-049).
STREET_WORDS = re.compile(r"\b(drive|dr|parkway|pkwy|plaza|street|road|rd|avenue|ave|boulevard|blvd|lane|court|centre|center)\b\.?", re.I)
# The words that end a company name, used to cut a care-of name out of a longer address line.
LEGAL_END = re.compile(r"^(.*?\b(?:limited|ltd|llp|plc|ab|inc|s\.?\s?[àa]\.?\s?r\.?\s?l|sarl|sas|gmbh|llc|l\.p))\.?(?![a-z])", re.I)
# The Level 1 predicates the scope rule reads from each observation.
READ = {"legalName", "otherName", "legalAddress", "headquartersAddress", "jurisdiction"}
# The rules that make scope decisions, with a plain-English label for each Rule node.
RULES = {"D-028": "Scope rule: In, Review or Out (with D-047 to D-053)",
         # Bruno's hand decisions.
         "manual-review": "Bruno's hand decision, from config/scope_reviews.toml (D-052)",
         # The sponsor choice, which the Sponsor nodes point to (D-040).
         "D-023": "The choice of sponsors: Hg, Bridgepoint and Apax"}


# Tidy a name for comparison: no accents, lower case, punctuation as spaces, single spaces.
def norm(name: str) -> str:
    # Split accented letters into letter + accent, then drop the accents.
    plain = "".join(c for c in unicodedata.normalize("NFKD", name) if not unicodedata.combining(c))
    # Lower case, with anything that isn't a letter or digit turned into a space.
    plain = re.sub(r"[^a-z0-9]+", " ", plain.lower())
    # Collapse runs of spaces and trim the ends.
    return " ".join(plain.split())


# Build a pattern that finds any of a sponsor's name forms as a whole word, ignoring case (D-047).
def forms_pattern(forms: list[str]) -> re.Pattern:
    # A form counts only when no letter or digit touches it on either side.
    return re.compile(r"(?<![A-Za-z0-9])(" + "|".join(map(re.escape, forms)) + r")(?![A-Za-z0-9])", re.I)


# Find the care-of part of a one-line address: after "c/o", else the first part if it starts with a name.
def care_of_part(address: str) -> str | None:
    # Look for "c/o" or "care of", and take the text after it up to the next comma.
    m = re.search(r"(?:c/o|care of)\s*([^,]+)", address, re.I)
    # The text after c/o, or else the address's first part.
    part = m.group(1).strip() if m else address.split(",")[0].strip()
    # A first part starting with a number is a street address, not a name.
    if not m and re.match(r"\d", part):
        # No care-of name here.
        return None
    # If the part runs on past the company name (no comma), cut it after the legal-form word.
    cut = LEGAL_END.match(part)
    # The company name alone, e.g. "Apax Partners Guernsey Limited".
    return cut.group(1).strip() if cut else part


# Gather what the scope rule needs from the fact rows: each entity's latest observation, its searches, its managers.
def gather(rows: list[dict]) -> tuple[dict, dict, dict]:
    # For each LEI, every observation: source record -> (fetch time, {predicate: [values]}).
    observations = defaultdict(dict)
    # For each LEI, the search replies (slugs like "apax") that caught it.
    searched_by = defaultdict(set)
    # For each fund's LEI, the LEIs GLEIF says manage it.
    managers = defaultdict(set)
    # Go through every row.
    for r in rows:
        # Only GLEIF entity facts matter here.
        if not r["subject"].startswith("lei:") or r["origin"]["kind"] != "source":
            # Skip anything else.
            continue
        # The LEI, without its prefix.
        lei = r["subject"][4:]
        # The fund-manager link, as GLEIF states it (D-027).
        if r["predicate"] == "fundManagedBy":
            # Remember the manager's LEI.
            managers[lei].add(r["object"]["iri"][4:])
        # Only the Level 1 fields the rule reads.
        if r["predicate"] not in READ:
            # Skip other predicates.
            continue
        # The source record's name, e.g. "src:gleif/<LEI>/search-apax_p1/20261018".
        record = r["origin"]["record"]
        # The reply's name, e.g. "search-apax_p1".
        reply = record.split("/")[2]
        # A search reply: note which search word caught this entity, e.g. "apax".
        if reply.startswith("search-"):
            # The word's file-name form, without the page number.
            searched_by[lei].add(reply[len("search-"):].rsplit("_p", 1)[0])
        # Find (or start) this observation's entry.
        when, fields = observations[lei].setdefault(record, (r["origin"]["retrieved_at"], defaultdict(list)))
        # Add the value under its predicate.
        fields[r["predicate"]].append(r["object"]["value"])
    # Keep only the latest observation of each entity (D-051); ties go to the record name, so the result is fixed.
    latest = {lei: max(obs.items(), key=lambda kv: (kv[1][0], kv[0]))[1][1] for lei, obs in observations.items()}
    # Hand back the three lookups.
    return latest, searched_by, managers


# Work out one automatic label for one entity and one sponsor. Returns (verdict, reason, care-of name to review or None).
def decide(lei, sponsor, ctx) -> tuple[str, str, str | None]:
    # This entity's latest facts.
    f = ctx["latest"][lei]
    # The sponsor's name-form pattern.
    forms = ctx["forms"][sponsor]
    # The entity's legal name (the latest observation has exactly one).
    name = f["legalName"][0]
    # Test 1: the legal name contains a name form.
    hit = forms.search(name)
    # A name match.
    if hit:
        # Managers GLEIF names for it whose own name doesn't contain the sponsor's name.
        outside = [m for m in ctx["managers"][lei] if m in ctx["latest"] and not forms.search(ctx["latest"][m]["legalName"][0])]
        # Managed by an outside company: send to Review (D-028).
        if outside:
            # The first outside manager's name, for the reason.
            mgr = ctx["latest"][sorted(outside)[0]]["legalName"][0]
            # Review, with the reason.
            return "Review", f"name contains '{hit.group(1)}', but GLEIF says it is managed by an outside company: {mgr}", None
        # Otherwise In.
        return "In", f"legal name contains '{hit.group(1)}'", None
    # The care-of names found, and the street-only mentions, across both addresses.
    unknown, street = None, None
    # Look at the legal address, then the headquarters address (D-050).
    for field in ("legalAddress", "headquartersAddress"):
        # Each address of that kind (normally one).
        for address in f.get(field, []):
            # Test 2: the care-of part.
            part = care_of_part(address)
            # It names something containing the sponsor's name.
            if part and forms.search(part) and not STREET_WORDS.search(part):
                # The tidied name, for exact comparison.
                key = norm(part)
                # A company that is In by name (D-048).
                if key in ctx["in_names"][sponsor]:
                    # In, with the reason.
                    return "In", f"{field} is care of '{part}', a {ctx['label'][sponsor]} company in our data", None
                # A care-of name Bruno has decided (D-048, D-052).
                if (key, sponsor) in ctx["care_of"]:
                    # Bruno's verdict and reason for that name.
                    verdict, why = ctx["care_of"][(key, sponsor)]
                    # In or Out, citing Bruno's decision.
                    return verdict, f"{field} is care of '{part}' ({'approved' if verdict == 'In' else 'rejected'} by Bruno: {why})", None
                # A care-of name not in our data: remember it for Review.
                unknown = unknown or part
            # Test 3: the sponsor's word appears somewhere in the address; look at each part.
            for piece in address.split(","):
                # A part with the sponsor's word that looks like a street or building.
                if forms.search(piece) and (STREET_WORDS.search(piece) or re.match(r"\s*\d", piece)):
                    # Remember it for the street test.
                    street = street or piece.strip()
    # A care-of name not in our data: Review, and onto the care-of name list.
    if unknown:
        # Review, with the reason and the name to review.
        return "Review", f"address is care of '{unknown}', a name not in our data", unknown
    # Test 3: the sponsor's word only in a street or building name -> Out (D-049).
    if street:
        # Out, with the reason.
        return "Out", f"'{ctx['label'][sponsor]}' appears only in a street or building name: '{street}'", None
    # Test 4: another name (e.g. a previous legal name) contains a name form.
    for other in f.get("otherName", []):
        # A match in the other name.
        if forms.search(other):
            # Review, with the reason.
            return "Review", f"only another name matches: '{other}'", None
    # Test 5: caught by the search, but nothing else matches.
    return "Review", "found by GLEIF's search, but no name, address or former-name match", None


# Build the ScopeDecision rows for one decision node.
def decision_rows(node: str, lei: str, sponsor: str, verdict: str, reason: str, rule: str) -> list[dict]:
    # Every row of this decision comes from the rule that made it (D-029).
    origin = {"kind": "rule", "rule": rule}
    # The node's rows: what it is, which entity, which sponsor, the verdict, the reason and the rule (D-036).
    return [fact(node, "type", iri("ex:ScopeDecision"), origin),
            # Which entity it is about.
            fact(node, "entity", iri(f"lei:{lei}"), origin),
            # Which sponsor.
            fact(node, "sponsor", iri(f"ex:sponsor/{sponsor}"), origin),
            # In, Review or Out.
            fact(node, "verdict", iri(f"ex:{verdict}"), origin),
            # The evidence, in words.
            fact(node, "reason", literal(reason), origin),
            # The rule that made it, on the node itself.
            fact(node, "wasGeneratedBy", iri(f"ex:rule/{rule}"), origin)]


# Run the scope step. Returns the new rows (decisions and rule nodes); also writes docs/scope-review.md.
def scope_facts(rows: list[dict]) -> list[dict]:
    # Read the sponsor settings.
    with SPONSORS_PATH.open("rb") as fh:
        # Turn the TOML text into Python data.
        sponsors = tomllib.load(fh)["sponsors"]
    # Read Bruno's hand decisions.
    with REVIEWS_PATH.open("rb") as fh:
        # Turn the TOML text into Python data.
        reviews = tomllib.load(fh)
    # Each entity's latest facts, the searches that caught it, and its managers.
    latest, searched_by, managers = gather(rows)
    # Everything the decide() function needs, in one place.
    ctx = {"latest": latest, "managers": managers,
           # Each sponsor's name-form pattern.
           "forms": {k: forms_pattern(s["name_forms"]) for k, s in sponsors.items()},
           # Each sponsor's display name, e.g. "Apax".
           "label": {k: s["name"] for k, s in sponsors.items()},
           # Bruno's care-of name decisions: (tidied name, sponsor) -> (verdict, reason).
           "care_of": {(norm(c["name"]), c["sponsor"]): (c["verdict"].capitalize(), c["reason"]) for c in reviews.get("care_of", [])}}
    # Which entities each sponsor's search caught (its "net").
    nets = {k: sorted(lei for lei, slugs in searched_by.items()
                      # Caught by any of this sponsor's search words.
                      if slugs & {t.lower().replace(" ", "_") for t in s["search_terms"]}) for k, s in sponsors.items()}
    # The tidied legal names of each sponsor's name-matched entities, for the care-of test (D-048).
    ctx["in_names"] = {k: {norm(latest[lei]["legalName"][0]) for lei in nets[k] if ctx["forms"][k].search(latest[lei]["legalName"][0])} for k in sponsors}
    # All the new rows.
    out = []
    # Every automatic decision, for the report: (sponsor, LEI, verdict, reason).
    decided = []
    # Care-of names to review: (name, sponsor) -> number of entities using it.
    names_to_review = Counter()
    # Each sponsor's net.
    for sponsor, leis in nets.items():
        # Each entity in it.
        for lei in leis:
            # The automatic label.
            verdict, reason, unknown = decide(lei, sponsor, ctx)
            # Its rows, made by rule D-028.
            out += decision_rows(f"ex:scope/{sponsor}/{lei}", lei, sponsor, verdict, reason, "D-028")
            # Keep it for the report.
            decided.append((sponsor, lei, verdict, reason))
            # A care-of name to review: count it.
            if unknown:
                # One more entity using this name.
                names_to_review[(unknown, sponsor)] += 1
    # Bruno's hand decisions about single entities (D-052).
    applied = []
    # Each one in the file.
    for d in reviews.get("entity", []):
        # The automatic decision it revises.
        auto = f"ex:scope/{d['sponsor']}/{d['lei']}"
        # The hand decision's own node.
        node = auto + "/manual"
        # Its rows, made by the manual-review rule, with Bruno's reason.
        out += decision_rows(node, d["lei"], d["sponsor"], d["verdict"].capitalize(), d["reason"], "manual-review")
        # It revises the automatic decision (D-037).
        out.append(fact(node, "wasRevisionOf", iri(auto), {"kind": "rule", "rule": "manual-review"}))
        # The date Bruno decided it.
        out.append(fact(node, "decidedOn", literal(str(d["decided"]), "date"), {"kind": "rule", "rule": "manual-review"}))
        # Keep it for the report.
        applied.append(d)
    # One Rule node per rule, so a reader can see what each one is (D-040 open point: rules point to themselves).
    for rule, label in RULES.items():
        # "This is a rule."
        out.append(fact(f"ex:rule/{rule}", "type", iri("ex:Rule"), {"kind": "rule", "rule": rule}))
        # Its plain-English label.
        out.append(fact(f"ex:rule/{rule}", "label", literal(label), {"kind": "rule", "rule": rule}))
    # Write the review lists for Bruno.
    write_report(decided, names_to_review, applied, latest, sponsors)
    # Hand back the new rows.
    return out


# Write docs/scope-review.md: the counts, the review lists, and the lists to skim.
def write_report(decided, names_to_review, applied, latest, sponsors) -> None:
    # The entity's latest legal name.
    name = lambda lei: latest[lei]["legalName"][0]
    # The entity's latest jurisdiction (empty if GLEIF gives none).
    country = lambda lei: (latest[lei].get("jurisdiction") or [""])[0]
    # The lines of the report.
    L = ["# Scope review (generated by `make facts`; do not edit by hand)", "",
         # What the file is for.
         "Record decisions in `config/scope_reviews.toml` (D-052), then run `make facts` again.", "",
         # The counts table.
         "## Counts", "", "| Sponsor | In | Review | Out |", "|---|---|---|---|"]
    # One row per sponsor.
    for k, s in sponsors.items():
        # Count the verdicts for this sponsor.
        c = Counter(v for sp, _, v, _ in decided if sp == k)
        # The table row.
        L.append(f"| {s['name']} | {c['In']} | {c['Review']} | {c['Out']} |")
    # The entities in Review.
    L += ["", "## 1. Entities to review", "", "| Sponsor | LEI | Name | Why |", "|---|---|---|---|"]
    # Each Review decision, sorted by sponsor then name.
    for sp, lei, v, why in sorted(decided, key=lambda d: (d[0], name(d[1]))):
        # Only Review ones.
        if v == "Review":
            # The table row.
            L.append(f"| {sp} | `{lei}` | {name(lei)} | {why} |")
    # The care-of names not in our data.
    L += ["", "## 2. Care-of names to review (one decision covers every entity using the name)", "",
          # The table header.
          "| Sponsor | Care-of name | Entities |", "|---|---|---|"]
    # Each name, most-used first.
    for (n, sp), count in names_to_review.most_common():
        # The table row.
        L.append(f"| {sp} | {n} | {count} |")
    # D-053: name matches outside the usual countries, to skim for look-alikes.
    L += ["", f"## 3. To skim: In by name, outside {', '.join(USUAL_COUNTRIES)} (look-alikes to mark Out, D-053)", "",
          # The table header.
          "| Sponsor | LEI | Name | Country |", "|---|---|---|---|"]
    # Each such entity.
    for sp, lei, v, why in sorted(decided, key=lambda d: (d[0], country(d[1]), name(d[1]))):
        # In by name, and outside the usual countries.
        if v == "In" and why.startswith("legal name") and country(lei)[:2] not in USUAL_COUNTRIES:
            # The table row.
            L.append(f"| {sp} | `{lei}` | {name(lei)} | {country(lei)} |")
    # In by care-of only: worth a skim (e.g. Tembo Capital, F16).
    L += ["", "## 4. To skim: In by care-of address only", "", "| Sponsor | LEI | Name | Why |", "|---|---|---|---|"]
    # Each such entity.
    for sp, lei, v, why in sorted(decided, key=lambda d: (d[0], name(d[1]))):
        # In through the care-of test.
        if v == "In" and "care of" in why:
            # The table row.
            L.append(f"| {sp} | `{lei}` | {name(lei)} | {why} |")
    # The hand decisions already applied.
    L += ["", "## 5. Hand decisions applied", ""]
    # One line each, or a note if there are none yet.
    L += [f"- {d['sponsor']} `{d['lei']}`: {d['verdict']} ({d['reason']}, {d['decided']})" for d in applied] or ["- None yet."]
    # Save the report.
    REPORT_PATH.write_text("\n".join(L) + "\n", encoding="utf-8")
