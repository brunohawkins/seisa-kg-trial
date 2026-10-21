"""SUMMARY: The answer scorer (brief §6; D-059 to D-061). Compares a candidate
answer with a question's reference answer and gives graded scores from 0 to 1:

- correctness (D-059): F1 of precision and recall over answer items; a number
  in an item (e.g. a count) earns partial credit by how close it is;
- citation (D-060): F1 of support (cited sources that really state the fact)
  and coverage (answer items with at least one supporting source);
- overall (D-061): the average of the two.

It also lists what went wrong (missed items, invented items, counts off,
unsupported citations, uncited items), for the brief's "explain where and why
each approach goes wrong".

The reference answer is a question's saved RDF answer
(data/output/answers/rdf/<question>.json). Its KEY line says which columns
identify one item (commas: all of these; "|": either of these), and its VALUE
line, if any, names the column holding a number.

A candidate answer is {"rows": [{column: text, ...}, ...], "not_available": bool}.
Column names may differ from the reference's (a generated query names its own
columns), so items are matched by their values, not by column names, and
sources are any web addresses found in the row.
"""

# Pattern matching, used to find web addresses and tidy text.
import re
# Lets us describe the shape of an answer item.
from dataclasses import dataclass, field

# The start of our own entity addresses, removed so "lei:X" and the full address compare equal.
OUR_BASES = ("https://seisa-kg.example/lei/", "https://seisa-kg.example/def/", "https://seisa-kg.example/ch/", "lei:", "ex:", "ch:")
# A web address: "http" or "https", then anything up to a space.
URL = re.compile(r"https?://\S+")
# Our own entity and vocabulary addresses are names, not sources, so they never count as citations.
OUR_DOMAIN = "https://seisa-kg.example/"
# Our own source records ARE sources (D-122): a short id like "src:news/hg-06/s03" (a news sentence) or "src:gleif/…".
SOURCE_ID = re.compile(r"\bsrc:\S+")
# The same record written in full, as SPARQL answers write it; turned into the short id so both forms compare equal.
SOURCE_IRI = re.compile(r"https://seisa-kg\.example/source/(\S+)")



# One answer item: the values that identify it, an optional number, and its cited sources.
@dataclass
class Item:
    # Every cell of the row, tidied, so it can be matched against a reference key.
    cells: set[str]
    # Every number found in the row (e.g. a count).
    numbers: list[float]
    # Every web address cited in the row.
    sources: set[str]
    # For reference items: the key groups that must all be found (each group: any one alternative will do).
    key: list[set[str]] = field(default_factory=list)
    # For reference items: the number expected (None if the question has no VALUE).
    value: float | None = None


# Tidy a value for comparison: drop our address prefixes, lower case, single spaces, no surrounding quotes.
def norm(text: str) -> str:
    # Start from the text without surrounding spaces or quotes.
    t = text.strip().strip('"')
    # Remove any of our own address prefixes.
    for base in OUR_BASES:
        # Only at the start.
        if t.startswith(base):
            # Cut it off.
            t = t[len(base):]
    # Lower case, with runs of spaces made single.
    return " ".join(t.lower().split())


# Read a number from text, or None if it isn't one.
def number(text: str) -> float | None:
    # Try to read it as a number.
    try:
        # e.g. "124" -> 124.0
        return float(text)
    # Not a number.
    except ValueError:
        # Signal "no number".
        return None


# Turn one candidate row into an Item.
def candidate_item(row: dict) -> Item:
    # Every cell's text.
    texts = [str(v) for v in row.values() if v is not None]
    # The tidied cells, for matching.
    cells = {norm(t) for t in texts}
    # Every number in the row.
    numbers = [n for n in (number(t) for t in texts) if n is not None]
    # Every web address anywhere in the row, except our own names (found by a failing test).
    sources = {u for t in texts for u in URL.findall(t) if not u.startswith(OUR_DOMAIN)}
    # Plus our own source-record ids (e.g. news sentences), short or written in full (D-122).
    sources |= {s for t in texts for s in SOURCE_ID.findall(t)} | {"src:" + s for t in texts for s in SOURCE_IRI.findall(t)}
    # The item.
    return Item(cells, numbers, sources)


# Turn one reference row into an Item, using the question's KEY and VALUE lines.
def reference_item(row: dict, key_spec: str, value_col: str | None) -> Item:
    # Start from the same view a candidate gets.
    item = candidate_item(row)
    # Each comma-separated part of KEY is one group; "|" separates alternatives within a group.
    groups = [{norm(row[c.strip()]) for c in part.split("|") if row.get(c.strip())} for part in key_spec.split(",")]
    # A key column that is empty in the reference (e.g. "linkedTo" for a name that can't be linked) has nothing to find, so it is skipped (D-122).
    item.key = [g for g in groups if g]
    # The expected number, if the question has a VALUE column.
    item.value = number(row[value_col]) if value_col else None
    # The item.
    return item


# Does a candidate item match a reference item? Every key group must have one of its values among the candidate's cells.
def matches(ref: Item, cand: Item) -> bool:
    # All groups found.
    return all(group & cand.cells for group in ref.key)


# How close the candidate's number is to the reference's: 1 is exact, 0 is far off or missing (D-059).
def closeness(ref: Item, cand: Item) -> float:
    # No number expected: a match is fully right.
    if ref.value is None:
        # Full credit.
        return 1.0
    # Score each number in the candidate row, and keep the best (the row may hold other numbers too).
    scores = [max(0.0, 1 - abs(n - ref.value) / max(abs(ref.value), 1)) for n in cand.numbers]
    # The best score, or 0 if the row has no number at all.
    return max(scores, default=0.0)


# The F1 of two fractions: their harmonic mean, or 0 if both are 0.
def f1(a: float, b: float) -> float:
    # Avoid dividing by zero.
    return 2 * a * b / (a + b) if a + b else 0.0


# Score a candidate answer against a reference answer. Returns the scores and what went wrong.
def score(reference: dict, candidate: dict) -> dict:
    # The question's key and value columns.
    key_spec, value_col = reference.get("KEY", ""), reference.get("VALUE")
    # The reference items.
    refs = [reference_item(r, key_spec, value_col) for r in reference["rows"]]
    # The candidate items (none if it said "not available").
    cands = [] if candidate.get("not_available") else [candidate_item(r) for r in candidate.get("rows", [])]
    # A "not in the data" question: the right answer is to say so (D-059).
    if not refs:
        # Right if it gave no items; nothing to cite either way.
        right = 1.0 if not cands else 0.0
        # The scores, with the invented items listed if there are any.
        return {"correctness": right, "precision": right, "recall": right, "citation": right,
                # Support and coverage mean nothing without items, so they follow the verdict.
                "support": right, "coverage": right, "overall": right,
                # What went wrong.
                "errors": {"invented_items": len(cands)}}
    # Pair each reference item with the first unused candidate item that matches it.
    pairs, used = [], set()
    # Each reference item in turn.
    for ref in refs:
        # Look for a matching candidate item not already paired.
        for i, cand in enumerate(cands):
            # Unused and matching.
            if i not in used and matches(ref, cand):
                # Pair them.
                pairs.append((ref, cand))
                # Mark the candidate as used.
                used.add(i)
                # Stop looking for this reference item.
                break
    # The credit earned: each pair counts its closeness (1 if exact).
    credit = sum(closeness(r, c) for r, c in pairs)
    # Precision: credit over everything the candidate said.
    precision = credit / len(cands) if cands else 0.0
    # Recall: credit over everything it should have said.
    recall = credit / len(refs)
    # Correctness = F1 (D-059).
    correctness = f1(precision, recall)
    # Every source the candidate cited, counting repeats across items.
    cited = sum(len(c.sources) for c in cands)
    # The cited sources that really state the fact: those shared with the matching reference item.
    supported = sum(len(c.sources & r.sources) for r, c in pairs)
    # Items whose true answer has no source (e.g. "no Level 2 information": there's no record for an absence).
    # Citing nothing for them is right, so they are left out of coverage (F21).
    exempt = sum(1 for r, c in pairs if not r.sources and not c.sources)
    # Support: the fraction of citations that hold up (D-060); with no citations, full marks only if nothing needed one.
    support = supported / cited if cited else (1.0 if cands and exempt == len(cands) else 0.0)
    # The items that needed a source.
    needing = len(cands) - exempt
    # Coverage: the fraction of those items with at least one supporting source (D-060).
    coverage = sum(1 for r, c in pairs if c.sources & r.sources) / needing if needing else (1.0 if cands else 0.0)
    # Citation = F1 of support and coverage.
    citation = f1(support, coverage)
    # What went wrong, for the error analysis.
    errors = {"missed_items": len(refs) - len(pairs),
              # Candidate items that match nothing in the reference.
              "invented_items": len(cands) - len(pairs),
              # Matched items whose number isn't exact.
              "numbers_off": sum(1 for r, c in pairs if closeness(r, c) < 1),
              # Citations that don't hold up.
              "unsupported_citations": cited - supported,
              # Candidate items with no citation at all, apart from those that needed none.
              "uncited_items": sum(1 for c in cands if not c.sources) - exempt}
    # Every score, rounded for reading, plus the error counts.
    return {"correctness": round(correctness, 3), "precision": round(precision, 3), "recall": round(recall, 3),
            # The citation scores.
            "citation": round(citation, 3), "support": round(support, 3), "coverage": round(coverage, 3),
            # The overall score (D-061).
            "overall": round((correctness + citation) / 2, 3), "errors": errors}
