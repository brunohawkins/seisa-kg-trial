"""SUMMARY: Matching, step 1 of 2: find the candidates for every name in the
news. It decides nothing and adds nothing to the graph (D-096 to D-101).

For each name (a deal's target, buyer, seller, sponsor or fund; an adviser),
it collects three kinds of evidence:
- exact: company nodes whose legal, other or previous name equals the
  news name after tidying (capitals, punctuation, "Limited" -> "LTD", ...).
- sponsor: which of our three sponsors' name forms the name contains as a
  whole word (e.g. "Funds advised by Apax" -> apax).
- family: company nodes whose legal name contains every distinctive word of
  the news name (e.g. "Saturn Fund" -> the 28 "HG SATURN ..." entities).

It writes docs/matching-candidates.md for Bruno to read. Step 2 turns this
evidence into one outcome per name, by the strict rule (D-098, D-099).

Run with: uv run python -m seisa_kg.matching.candidates
"""

# Pattern matching, used for tidying names and finding whole words.
import re
# Reads the sponsors' name forms.
import tomllib
# Groups things into lists by key.
from collections import defaultdict

# The shared fact list and the project folder.
from seisa_kg.facts.model import PROJECT_ROOT, read_facts

# The news predicates that hold a name written in a release, and the role each plays.
NAME_PREDICATES = {"targetName": "target", "buyerName": "buyer", "sellerName": "seller",
                   # The sponsor and fund named on a deal or fund close.
                   "sponsorName": "sponsor", "fundName": "fund"}
# The company-name predicates we compare against (GLEIF's and Companies House's own words).
COMPANY_NAME_PREDICATES = {"legalName", "otherName", "previousName"}
# Legal-form words, written the same way on both sides so "Limited" and "LTD" compare equal.
SUFFIXES = {"LIMITED": "LTD", "INCORPORATED": "INC", "COMPANY": "CO", "LLP": "LLP", "PLC": "PLC"}
# Words that say nothing about which company is meant, ignored when looking for a family.
GENERIC = {"THE", "FUND", "FUNDS", "ADVISED", "MANAGED", "BY", "OF", "AND", "INVESTMENT", "INVESTMENTS",
           # Legal forms and joining words.
           "LTD", "LP", "LLP", "PLC", "INC", "CO", "SARL", "SCSP", "SA", "GP", "S", "A", "R", "L", "P"}
# The fewest distinctive words a name needs before we look for its family (one is enough, e.g. "SATURN").
MIN_WORDS = 1
# Where the report goes.
REPORT_PATH = PROJECT_ROOT / "docs" / "matching-candidates.md"
# The sponsors' configuration file.
SPONSORS_PATH = PROJECT_ROOT / "config" / "sponsors.toml"


# Tidy a name for comparing only (the name as written always stays in the graph).
def tidy(name: str) -> str:
    # Drop anything in brackets, e.g. '(“Michelin”)' or '(BDL IV)'.
    text = re.sub(r"\([^)]*\)", " ", name)
    # Capitals; accents kept, since both sides keep them.
    text = text.upper()
    # "L.P." and "S.À R.L." become "LP" and "SÀRL" by dropping the dots first.
    text = text.replace(".", "")
    # Every other punctuation mark (commas, quotes, apostrophes) becomes a space.
    text = re.sub(r"[^\w\s]", " ", text)
    # Legal-form words written one way.
    words = [SUFFIXES.get(w, w) for w in text.split()]
    # A leading "THE" says nothing.
    if words and words[0] == "THE":
        # Drop it.
        words = words[1:]
    # The tidied name, single-spaced.
    return " ".join(words)


# The distinctive words of a tidied name (the ones that could tell companies apart).
def distinctive(tidied: str) -> set[str]:
    # Every word that isn't generic.
    return {w for w in tidied.split() if w not in GENERIC}


# Every news name: one entry per node, role and name as written.
def news_names(rows: list[dict]) -> list[dict]:
    # The names found.
    out = []
    # Each fact row.
    for r in rows:
        # A deal or fund-close name field (not an "unknown", which names nothing; D-090).
        if r["predicate"] in NAME_PREDICATES and r["object"].get("value") != "unknown":
            # The node, its role, the name as written, and the sentence it came from.
            out.append({"node": r["subject"], "role": NAME_PREDICATES[r["predicate"]], "name": r["object"]["value"],
                        # The sentence record (the source of the name), and the name fact's whole origin.
                        "record": r["origin"].get("record", ""), "origin": r["origin"]})
        # An adviser's name.
        elif r["predicate"] == "name" and r["subject"].startswith("ex:adviser/"):
            # Same shape, with the role "adviser".
            out.append({"node": r["subject"], "role": "adviser", "name": r["object"]["value"], "record": r["origin"].get("record", ""), "origin": r["origin"]})
    # In a fixed order, so the report is the same on every run.
    return sorted(out, key=lambda n: (n["role"], n["name"].lower(), n["node"]))


# Every company node's names, tidied, plus each node's scope verdicts.
def company_index(rows: list[dict]) -> tuple[dict, dict, dict]:
    # Tidied name -> the company nodes that carry it (any of the three name kinds).
    by_name = defaultdict(set)
    # Company node -> its tidied legal names (used for the family search).
    legal = defaultdict(set)
    # Company node -> its scope verdicts, e.g. {"hg: In"} (from rule D-028).
    scope = defaultdict(set)
    # Each fact row.
    for r in rows:
        # A company name from GLEIF or Companies House.
        if r["predicate"] in COMPANY_NAME_PREDICATES and r["subject"].startswith(("lei:", "ch:")):
            # Indexed by its tidied form.
            by_name[tidy(r["object"]["value"])].add(r["subject"])
            # Legal names also go into the family list.
            if r["predicate"] == "legalName":
                # Kept tidied.
                legal[r["subject"]].add(tidy(r["object"]["value"]))
        # A scope verdict, e.g. subject "ex:scope/apax/<LEI>", object "ex:In".
        elif r["predicate"] == "verdict" and r["subject"].startswith("ex:scope/"):
            # The sponsor and the LEI, from the verdict's own name.
            _, sponsor, lei = r["subject"].split("/")
            # e.g. "apax: In".
            scope[f"lei:{lei}"].add(f"{sponsor}: {r['object']['iri'].removeprefix('ex:')}")
    # Hand back the three indexes.
    return by_name, legal, scope


# Each sponsor's key and a pattern matching any of its name forms as a whole word.
def sponsor_patterns() -> dict[str, re.Pattern]:
    # The sponsors' configuration.
    config = tomllib.loads(SPONSORS_PATH.read_text(encoding="utf-8"))["sponsors"]
    # e.g. {"hg": /\b(Hg|HgCapital)\b/i}.
    return {key: re.compile(r"\b(" + "|".join(map(re.escape, s["name_forms"])) + r")\b", re.IGNORECASE) for key, s in config.items()}


# The evidence for one news name.
def evidence(name: str, by_name: dict, legal: dict, sponsors: dict) -> dict:
    # The name tidied for comparing.
    t = tidy(name)
    # Exact: nodes whose name equals it after tidying.
    exact = sorted(by_name.get(t, set()))
    # Sponsor: which sponsors' name forms appear as whole words.
    hits = sorted(k for k, p in sponsors.items() if p.search(name))
    # The words that could tell companies apart.
    words = distinctive(t)
    # Family: nodes whose legal name contains every distinctive word (only when the name has any).
    family = sorted(n for n, names in legal.items() if len(words) >= MIN_WORDS and any(words <= set(x.split()) for x in names)) if words else []
    # Hand back the evidence.
    return {"tidy": t, "words": sorted(words), "exact": exact, "sponsor": hits, "family": family}


# A short list of nodes for the report: the first few, then how many more.
def show(nodes: list[str], legal: dict, scope: dict, limit: int = 3) -> str:
    # Each shown node with one of its legal names and its scope verdicts.
    parts = [f"{n} {sorted(legal.get(n, {''}))[0]}" + (f" [{', '.join(sorted(scope[n]))}]" if scope.get(n) else "") for n in nodes[:limit]]
    # "… +25 more" when the list is longer.
    more = f" … +{len(nodes) - limit} more" if len(nodes) > limit else ""
    # Joined with semicolons; a dash when empty.
    return "; ".join(parts) + more if nodes else "–"


# Write the report Bruno reads.
def write_report(results: list[dict], legal: dict, scope: dict) -> None:
    # Counts for the summary.
    total = len(results)
    # Names with exactly one exact candidate, with several, and with a family but no exact candidate.
    one = sum(len(r["exact"]) == 1 for r in results)
    # Several exact candidates.
    many = sum(len(r["exact"]) > 1 for r in results)
    # A sponsor word.
    spons = sum(bool(r["sponsor"]) for r in results)
    # No evidence of any kind.
    none = sum(not (r["exact"] or r["sponsor"] or r["family"]) for r in results)
    # The opening lines.
    L = ["# Matching candidates (generated by `python -m seisa_kg.matching.candidates`; do not edit by hand)", "",
         # What this is.
         "Step 1 of matching: the evidence for each news name. Nothing is decided or added to the graph here (D-096 to D-101).", "",
         # The summary.
         f"- {total} names. Exactly one exact candidate: {one}. Several exact candidates: {many}. "
         f"A sponsor's name in it: {spons}. No evidence at all: {none}.",
         # How to read the columns.
         "- **exact** = same name after tidying; **sponsor** = a sponsor's name form as a whole word; "
         "**family** = legal names containing every distinctive word. Scope verdicts in brackets.", "",
         # The table header.
         "| Role | As written | Tidied | Exact | Sponsor | Family | Sentence |", "|---|---|---|---|---|---|---|"]
    # One line per name.
    for r in results:
        # Table cells, with pipes escaped so the table holds together.
        cells = [r["role"], r["name"], r["tidy"], show(r["exact"], legal, scope), ", ".join(r["sponsor"]) or "–",
                 # The family: its size, then the first few.
                 f"{len(r['family'])}: {show(r['family'], legal, scope, 2)}" if r["family"] else "–", r["record"]]
        # The row.
        L.append("| " + " | ".join(c.replace("|", "\\|") for c in cells) + " |")
    # Save it.
    REPORT_PATH.write_text("\n".join(L) + "\n", encoding="utf-8")


# Find the evidence for every news name and write the report.
def main() -> None:
    # The whole fact list.
    rows = read_facts()
    # The company names and scope verdicts.
    by_name, legal, scope = company_index(rows)
    # The sponsors' name patterns.
    sponsors = sponsor_patterns()
    # The evidence for each news name.
    results = [{**n, **evidence(n["name"], by_name, legal, sponsors)} for n in news_names(rows)]
    # The report.
    write_report(results, legal, scope)
    # Say where it went.
    print(f"{len(results)} names; report: {REPORT_PATH.relative_to(PROJECT_ROOT)}")


# Run main() when the file is run directly.
if __name__ == "__main__":
    # Go.
    main()
