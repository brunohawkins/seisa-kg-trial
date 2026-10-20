"""SUMMARY: Tests for entity matching's strict rules (D-096 to D-104).

Each test hands decide() a made-up name with made-up evidence and checks the
outcome, so a later change that loosens a rule (and risks wrong links) fails here.

Run them with:  uv run pytest
"""

# The name tidier and the rule function under test.
from seisa_kg.matching.candidates import tidy
# The rules, and the lookup of joined lei:/ch: pairs.
from seisa_kg.matching.outcomes import company_of, decide


# Make a name entry with the given evidence (anything not given is empty).
def entry(name: str, role: str = "buyer", exact=(), sponsor=(), family=()) -> dict:
    # The same shape step 1 produces.
    return {"name": name, "role": role, "tidy": tidy(name), "exact": list(exact), "sponsor": list(sponsor), "family": list(family)}


# Tidying makes "Limited" and "LTD", capitals and punctuation compare equal, and drops brackets.
def test_tidy_compares_like_with_like():
    # Same company, written two ways.
    assert tidy("Bridgepoint Advisers Limited") == tidy("BRIDGEPOINT ADVISERS LTD")
    # Brackets dropped, dots removed.
    assert tidy("Bridgepoint Direct Lending IV (BDL IV)") == "BRIDGEPOINT DIRECT LENDING IV"


# A ch: and lei: pair already joined by sameEntityAs counts as one company, so it links (D-102).
def test_joined_pair_counts_as_one():
    # The ch: node points at its lei: node.
    out = decide(entry("Apax Partners LLP", exact=["ch:OC303117", "lei:X"]), {"ch:OC303117": "lei:X"}, {})
    # One company: linked to the lei:.
    assert out["outcome"] == "sameEntityAs" and out["to"] == ["lei:X"]


# Two different companies with the same name: never pick one (D-098).
def test_two_companies_is_ambiguous():
    # Two unrelated lei: nodes.
    out = decide(entry("Some Name Ltd", exact=["lei:A", "lei:B"]), {}, {})
    # Ambiguous, with both listed.
    assert out["outcome"] == "ambiguous" and out["to"] == ["lei:A", "lei:B"]


# A family with no sponsor word stays ambiguous, however many candidates share its words (D-103).
def test_family_without_sponsor_is_ambiguous():
    # "Saturn Fund"-style evidence.
    out = decide(entry("Saturn Fund", family=["lei:A", "lei:B"]), {}, {})
    # Not linked.
    assert out["outcome"] == "ambiguous"


# Advisers are out of scope by rule, even when a family search found something (D-104).
def test_adviser_is_out_of_scope():
    # The "Rothschild & Co" case: a false family match.
    out = decide(entry("Rothschild & Co", role="adviser", family=["lei:A"]), {}, {})
    # Out of scope, not ambiguous.
    assert out["outcome"] == "out-of-scope"


# A deal target with no evidence gets a NewsOnlyCompany node, one per tidied name (D-109).
def test_target_becomes_news_only_company():
    # Two spellings of the same name.
    a, b = decide(entry("Zuto", role="target"), {}, {}), decide(entry("ZUTO.", role="target"), {}, {})
    # Both news-only, pointing at the same node.
    assert a["outcome"] == "news-only" and a["to"] == b["to"] == ["ex:newsonlycompany/zuto"]


# Any other name with no evidence and no label is unresolved, never guessed (D-096).
def test_no_evidence_is_unresolved():
    # A seller nobody labelled.
    out = decide(entry("Unknown Seller Co", role="seller"), {}, {})
    # Unresolved.
    assert out["outcome"] == "unresolved"


# Only registry pairs (lei: -> ch:, rule D-025) count as joined; a Match's own sameEntityAs link must not.
def test_pairs_ignore_match_links():
    # One registry pair and one Match link to the same lei:.
    rows = [{"subject": "lei:X", "predicate": "sameEntityAs", "object": {"iri": "ch:1"}},
            # A Match node's link, as written by matching itself.
            {"subject": "ex:match/d1-buyer-1", "predicate": "sameEntityAs", "object": {"iri": "lei:X"}}]
    # Only the registry pair is kept.
    assert company_of(rows) == {"ch:1": "lei:X"}

