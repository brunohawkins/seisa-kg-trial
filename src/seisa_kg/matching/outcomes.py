"""SUMMARY: Matching, step 2 of 2: one outcome per news name, by the strict
rules Bruno decided (D-096 to D-104, D-109). Still adds nothing to the graph.

The rules, tried in order; the first that applies wins:
1. An adviser                         -> out of scope (D-104)
2. Exactly one company fits exactly   -> sameEntityAs that company (D-098, D-102)
3. Two or more companies fit exactly  -> ambiguous, with the candidates (D-098)
4. One sponsor's name as a word       -> refersToGroup that sponsor; a fund family,
                                         if the name has more words, is listed as
                                         "possible, none picked" (D-103)
5. A family but no sponsor word       -> ambiguous, with the candidates (D-103)
6. A label Bruno approved             -> that label (config/match_labels.toml; D-099)
7. A deal target with no other match  -> news-only: a NewsOnlyCompany node, one per
                                         name after tidying (D-109)
8. Anything else                      -> unresolved (D-096)

"Exactly one company": a ch: and lei: pair already joined by sameEntityAs
counts as one (D-102); the link then points at the lei: node.

It writes docs/matching-report.md. Run with: uv run python -m seisa_kg.matching.outcomes
"""

# Counts the outcomes.
from collections import Counter
# Pattern matching, used to make a node name from a company name.
import re
# Reads the approved labels.
import tomllib

# The shared fact list and the project folder.
from seisa_kg.facts.model import PROJECT_ROOT, read_facts
# Step 1: the names, the company index, the sponsor patterns and the evidence.
from seisa_kg.matching.candidates import company_index, distinctive, evidence, news_names, sponsor_patterns, tidy

# The labels Bruno approved.
LABELS_PATH = PROJECT_ROOT / "config" / "match_labels.toml"
# Where the report goes.
REPORT_PATH = PROJECT_ROOT / "docs" / "matching-report.md"


# Company node -> the node that stands for its company (a ch: joined to a lei: is represented by the lei:).
def company_of(rows: list[dict]) -> dict[str, str]:
    # Each ch: node joined to a lei: node by rule D-025 (not a Match's own sameEntityAs link, which starts at ex:match/).
    return {r["object"]["iri"]: r["subject"] for r in rows if r["predicate"] == "sameEntityAs" and r["subject"].startswith("lei:")}


# The approved labels, keyed by the name in lower case.
def load_labels() -> dict[str, dict]:
    # Read the file.
    labels = tomllib.loads(LABELS_PATH.read_text(encoding="utf-8"))["label"]
    # e.g. {"kkr": {"name": "KKR", "outcome": "out-of-scope", "note": "..."}}.
    return {l["name"].lower(): l for l in labels}


# Decide one name's outcome from its evidence. Returns the outcome, its target(s), the rule and the reason.
def decide(n: dict, same: dict, labels: dict) -> dict:
    # The distinct companies among the exact candidates (a joined pair counts once; D-102).
    companies = sorted({same.get(c, c) for c in n["exact"]})
    # The family's distinct companies.
    family = sorted({same.get(c, c) for c in n["family"]})
    # Rule 1: an adviser.
    if n["role"] == "adviser" and not n["sponsor"]:
        # Out of scope by role.
        return {"outcome": "out-of-scope", "to": [], "rule": "D-104", "why": "an outside adviser; our graph covers the sponsors' own companies"}
    # Rule 2: exactly one company.
    if len(companies) == 1:
        # The same company.
        return {"outcome": "sameEntityAs", "to": companies, "rule": "D-098", "why": "the only company with this exact name (after tidying)"}
    # Rule 3: two or more companies.
    if len(companies) > 1:
        # Ambiguous: none picked.
        return {"outcome": "ambiguous", "to": companies, "rule": "D-098", "why": f"{len(companies)} companies have this exact name"}
    # Rule 4: exactly one sponsor's name.
    if len(n["sponsor"]) == 1:
        # The sponsor's own name forms, so "Apax Digital" counts as more specific than "Apax".
        extra = distinctive(n["tidy"]) - {w.upper() for w in sponsor_words(n["sponsor"][0])}
        # A family is listed only when the name says more than the sponsor's name.
        possible = family if extra else []
        # The group, with the family (if any) as possible candidates.
        why = "names the sponsor" + (f"; {len(possible)} possible entities, none picked" if possible else "")
        # Linked to the sponsor's group.
        return {"outcome": "refersToGroup", "to": [f"ex:sponsor/{n['sponsor'][0]}"], "possible": possible, "rule": "D-103", "why": why}
    # Two sponsors in one name (doesn't happen today, but never guess).
    if len(n["sponsor"]) > 1:
        # Ambiguous between sponsors.
        return {"outcome": "ambiguous", "to": [f"ex:sponsor/{s}" for s in n["sponsor"]], "rule": "D-098", "why": "names more than one sponsor"}
    # Rule 5: a family but no sponsor word.
    if family:
        # Ambiguous: none picked.
        return {"outcome": "ambiguous", "to": family, "rule": "D-103", "why": f"{len(family)} entities share its words, and it names no sponsor"}
    # Rule 6: an approved label.
    label = labels.get(n["name"].lower())
    # A label exists.
    if label:
        # Its outcome, with the note or the kind as the reason.
        return {"outcome": label["outcome"], "to": [], "rule": "D-099", "why": label.get("note") or label.get("kind", "")}
    # Rule 7: a deal target with no other match gets a company node known only from the news.
    if n["role"] == "target":
        # One node per tidied name, e.g. "ZUTO" -> ex:newsonlycompany/zuto.
        return {"outcome": "news-only", "to": [news_only_node(n["tidy"])], "rule": "D-109",
                # Why.
                "why": "a company known only from the news; no registry ID, not verified"}
    # Rule 8: nothing applies.
    return {"outcome": "unresolved", "to": [], "rule": "D-096", "why": "no evidence and no approved label"}


# The NewsOnlyCompany node for a tidied name (D-109): lower case, words joined by hyphens.
def news_only_node(tidied: str) -> str:
    # e.g. "SEDEX INFORMATION EXCHANGE LTD" -> "ex:newsonlycompany/sedex-information-exchange-ltd".
    return "ex:newsonlycompany/" + re.sub(r"[^a-z0-9]+", "-", tidied.lower()).strip("-")


# Each sponsor's name forms, as words (e.g. "hg" -> ["Hg", "HgCapital"]).
def sponsor_words(key: str) -> list[str]:
    # The sponsors' configuration.
    config = tomllib.loads((PROJECT_ROOT / "config" / "sponsors.toml").read_text(encoding="utf-8"))["sponsors"]
    # The name forms, tidied the same way as names.
    return [tidy(f) for f in config[key]["name_forms"]]


# Find every name's outcome. Returns the names with their evidence and outcome.
def match_all(rows: list[dict]) -> list[dict]:
    # The company names and scope verdicts.
    by_name, legal, _ = company_index(rows)
    # The joined pairs.
    same = company_of(rows)
    # The approved labels.
    labels = load_labels()
    # The sponsors' name patterns.
    sponsors = sponsor_patterns()
    # Each news name with its evidence.
    names = [{**n, **evidence(n["name"], by_name, legal, sponsors)} for n in news_names(rows)]
    # Each with its outcome added.
    return [{**n, **decide(n, same, labels)} for n in names]


# Write the report Bruno reads.
def write_report(results: list[dict]) -> None:
    # How many names got each outcome.
    counts = Counter(r["outcome"] for r in results)
    # The opening lines.
    L = ["# Matching report (generated by `python -m seisa_kg.matching.outcomes`; do not edit by hand)", "",
         # What this is.
         "One outcome per news name, by the strict rules D-096 to D-104. Nothing is added to the graph yet.", "",
         # The counts.
         f"{len(results)} names: " + ", ".join(f"{k} {v}" for k, v in counts.most_common()), "",
         # The table header.
         "| Role | As written | Outcome | Linked to / candidates | Rule | Why |", "|---|---|---|---|---|---|"]
    # The interesting outcomes first, then the rest; advisers last (they're all the same).
    order = {"sameEntityAs": 0, "refersToGroup": 1, "ambiguous": 2, "news-only": 3, "non-entity": 4, "out-of-scope": 5, "unresolved": 6}
    # One line per name.
    for r in sorted(results, key=lambda r: (r["role"] == "adviser", order[r["outcome"]], r["role"], r["name"].lower())):
        # The targets, shortened when long.
        to = ", ".join(r["to"][:3]) + (f" … +{len(r['to']) - 3}" if len(r["to"]) > 3 else "")
        # The row, with pipes escaped.
        L.append("| " + " | ".join(c.replace("|", "\\|") for c in [r["role"], r["name"], r["outcome"], to or "–", r["rule"], r["why"]]) + " |")
    # Save it.
    REPORT_PATH.write_text("\n".join(L) + "\n", encoding="utf-8")


# Match every name and write the report.
def main() -> None:
    # Every name's outcome.
    results = match_all(read_facts())
    # The report.
    write_report(results)
    # The counts, on screen.
    print(dict(Counter(r["outcome"] for r in results)), f"report: {REPORT_PATH.relative_to(PROJECT_ROOT)}")


# Run main() when the file is run directly.
if __name__ == "__main__":
    # Go.
    main()
