"""SUMMARY: Tests for the answer scorer (src/seisa_kg/evaluation/score.py).

Each test feeds the scorer a tiny made-up reference and candidate whose right
score can be worked out by hand, so the arithmetic of D-059 to D-061 is pinned
down. Made-up data only (PLAN: fixtures for tests only).
"""

# Comparing decimals with a small tolerance.
import pytest

# The scorer under test.
from seisa_kg.evaluation.score import score

# A made-up reference: two managers, each with a count and one source.
REFERENCE = {"KEY": "manager|managerName", "VALUE": "funds", "rows": [
    # Manager A runs 10 funds, stated in record a.
    {"manager": "https://seisa-kg.example/lei/AAA", "managerName": "Alpha GP Ltd", "funds": "10", "sources": "https://api.gleif.org/a"},
    # Manager B runs 4 funds, stated in record b.
    {"manager": "https://seisa-kg.example/lei/BBB", "managerName": "Beta GP Ltd", "funds": "4", "sources": "https://api.gleif.org/b"},
]}


# A perfect copy of the reference scores 1 everywhere.
def test_perfect_answer_scores_one():
    # Score the reference against itself.
    s = score(REFERENCE, {"rows": REFERENCE["rows"]})
    # Every score is 1.
    assert (s["correctness"], s["citation"], s["overall"]) == (1.0, 1.0, 1.0)


# Different column names and the name instead of the LEI still match (items are matched by value).
def test_matches_by_value_not_column_name():
    # A generated query might name its columns differently and return names only.
    s = score(REFERENCE, {"rows": [{"n": "alpha gp ltd", "c": "10", "src": "https://api.gleif.org/a"},
                                   # The second item, with its own source.
                                   {"n": "Beta GP Ltd", "c": "4", "src": "https://api.gleif.org/b"}]})
    # Still perfect.
    assert s["overall"] == 1.0


# Missing one of two items: precision 1, recall 0.5, correctness F1 = 0.667.
def test_missing_item_gets_partial_credit():
    # Only manager A.
    s = score(REFERENCE, {"rows": REFERENCE["rows"][:1]})
    # The F1 of 1 and 0.5.
    assert s["correctness"] == pytest.approx(0.667, abs=0.001)
    # One missed item is reported.
    assert s["errors"]["missed_items"] == 1


# A count that's off earns credit by closeness: 8 against 10 scores 0.8 for that item.
def test_count_closeness():
    # Manager A with 8 instead of 10; manager B exact.
    rows = [dict(REFERENCE["rows"][0], funds="8"), REFERENCE["rows"][1]]
    # Score it.
    s = score(REFERENCE, {"rows": rows})
    # Credit 0.8 + 1 = 1.8 over 2 items each way: precision = recall = 0.9.
    assert s["correctness"] == pytest.approx(0.9)
    # One number is off.
    assert s["errors"]["numbers_off"] == 1


# An answer with no sources scores 0 on citation, however right it is (D-060).
def test_no_citations_scores_zero_citation():
    # The right items, with the sources removed.
    rows = [{k: v for k, v in r.items() if k != "sources"} for r in REFERENCE["rows"]]
    # Score it.
    s = score(REFERENCE, {"rows": rows})
    # Correct, uncited: overall is the average, 0.5.
    assert (s["correctness"], s["citation"], s["overall"]) == (1.0, 0.0, 0.5)


# A wrong source is caught: support falls.
def test_wrong_source_is_unsupported():
    # Manager A cites record b, which doesn't state A's link.
    rows = [dict(REFERENCE["rows"][0], sources="https://api.gleif.org/b"), REFERENCE["rows"][1]]
    # Score it.
    s = score(REFERENCE, {"rows": rows})
    # Half the citations hold up, and half the items are covered: citation = 0.5.
    assert s["citation"] == pytest.approx(0.5)
    # One unsupported citation.
    assert s["errors"]["unsupported_citations"] == 1


# A "not in the data" question: saying so scores 1, inventing items scores 0.
def test_not_available_question():
    # A reference with no rows (the right answer is "not in the data").
    empty = {"KEY": "x", "rows": []}
    # Saying so is right.
    assert score(empty, {"not_available": True})["overall"] == 1.0
    # Inventing an answer is wrong.
    assert score(empty, {"rows": [{"x": "made up"}]})["overall"] == 0.0


# An item whose true answer has no source (e.g. "no Level 2 information") isn't penalised for citing nothing (F21).
def test_item_with_no_true_source_needs_no_citation():
    # A reference where one item has a source and one has none.
    ref = {"KEY": "reason", "rows": [{"reason": "NON_CONSOLIDATING", "sources": "https://api.gleif.org/x"},
                                     # An absence: there is no record to cite.
                                     {"reason": "(no Level 2 information)", "sources": ""}]}
    # The candidate gives the same, citing nothing for the absence.
    s = score(ref, {"rows": ref["rows"]})
    # Full marks.
    assert s["overall"] == 1.0


# Our own source records count as sources, and the full and short forms of one record are the same source (D-122).
def test_source_record_ids_count_as_sources():
    # A news reference, written the way SPARQL writes it: the sentence's full address.
    ref = {"KEY": "target", "rows": [{"target": "Zuto", "sources": "https://seisa-kg.example/source/news/bridgepoint-03/s01"}]}
    # A candidate citing the same sentence by its short id, as Cypher (or an LLM) writes it.
    right = score(ref, {"rows": [{"target": "Zuto", "sources": "src:news/bridgepoint-03/s01"}]})
    # Fully supported and covered.
    assert right["citation"] == 1.0
    # A candidate citing a different sentence.
    wrong = score(ref, {"rows": [{"target": "Zuto", "sources": "src:news/bridgepoint-03/s09"}]})
    # Right item, unsupported citation.
    assert (wrong["correctness"], wrong["citation"]) == (1.0, 0.0)
    # Our entity names (ex:, lei:) are still never sources.
    named = score(ref, {"rows": [{"target": "Zuto", "sources": "ex:sponsor/bridgepoint lei:213800KFNMVI8PDZX472"}]})
    # No citation at all.
    assert named["citation"] == 0.0


# A key column that is empty in the reference is skipped, so an identical answer still scores 1 (found on Q10, D-122).
def test_empty_key_value_is_skipped():
    # Q10-like rows: the second buyer can't be linked, so its linkedTo is empty.
    ref = {"KEY": "buyer, linkedTo", "rows": [{"buyer": "Hg", "linkedTo": "ex:sponsor/hg", "sources": "src:news/hg-06/s03"},
                                              {"buyer": "Tidemark", "linkedTo": "", "sources": "src:news/hg-06/s06"}]}
    # The identical answer.
    assert score(ref, {"rows": ref["rows"]})["overall"] == 1.0


# A Companies House node written in full (SPARQL) and short (Cypher) is the same item (found on Q4, D-122).
def test_companies_house_ids_compare_equal():
    # The answer key writes the full address.
    ref = {"KEY": "node, value", "rows": [{"node": "https://seisa-kg.example/ch/11443992", "value": "plc", "sources": "src:ch/11443992/profile/20261019"}]}
    # The candidate writes the short id.
    s = score(ref, {"rows": [{"node": "ch:11443992", "value": "plc", "sources": "src:ch/11443992/profile/20261019"}]})
    # Full marks.
    assert s["overall"] == 1.0
