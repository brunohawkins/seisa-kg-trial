"""SUMMARY: Tests for the property graph builder's rules (D-110 to D-114),
on made-up facts, with no Neo4j needed.

Run them with:  uv run pytest
"""

# Real dates, to check typing.
from datetime import date

# The test runner (for checking that an error is raised).
import pytest

# The builder's rules under test.
from seisa_kg.lpg.build import build_nodes, build_relationships, labels_for, rel_type, typed


# A made-up GLEIF-style origin.
SRC = {"kind": "source", "record": "src:gleif/X/20261018", "source": "GLEIF", "url": "https://example.org", "retrieved_at": "2026-10-18T13:52:00+00:00"}


# Make one fact row.
def row(s, p, o, origin=SRC, details=None):
    # The same shape as facts.jsonl.
    return {"subject": s, "predicate": p, "object": o, "origin": origin, "details": details or {}}


# Rule 1: a company gets :Company plus its register; other types keep their own name.
def test_labels():
    # GLEIF, Companies House, and a deal.
    assert labels_for("lei:X", "ex:LegalEntity") == ("Company", "Gleif")
    # Companies House.
    assert labels_for("ch:1", "ex:LegalEntity") == ("Company", "CompaniesHouse")
    # A deal.
    assert labels_for("ex:deal/d1", "ex:Deal") == ("Deal",)


# Rule 2: dates and booleans become real types; text is untouched.
def test_typed():
    # A date.
    assert typed({"value": "2026-06-29", "datatype": "date"}) == date(2026, 6, 29)
    # A boolean.
    assert typed({"value": "true", "datatype": "boolean"}) is True
    # Text, exactly as given.
    assert typed({"value": "approximately $1.393 billion"}) == "approximately $1.393 billion"


# D-114: names in Neo4j style, with the renames.
def test_rel_type():
    # The general rule.
    assert rel_type("fundManagedBy") == "FUND_MANAGED_BY"
    # A rename: one concept, one name.
    assert rel_type("officer") == rel_type("holder") == "HELD_BY"


# Rule 3: a fact kind with two values anywhere is a list everywhere; one node per distinct id.
def test_lists_and_dedup():
    # Two companies; one has two statuses (e.g. from two fetch dates), the same company typed twice.
    rows = [row("lei:A", "type", {"iri": "ex:LegalEntity"}), row("lei:A", "type", {"iri": "ex:LegalEntity"}),
            # The second company.
            row("lei:B", "type", {"iri": "ex:LegalEntity"}),
            # Two statuses on A, one on B.
            row("lei:A", "registrationStatus", {"value": "ISSUED"}), row("lei:A", "registrationStatus", {"value": "LAPSED"}),
            # B's single status.
            row("lei:B", "registrationStatus", {"value": "ISSUED"})]
    # Build.
    nodes = build_nodes(rows)
    # A is one node with both values; B is a list too.
    assert nodes["lei:A"]["props"]["registrationStatus"] == ["ISSUED", "LAPSED"] and nodes["lei:B"]["props"]["registrationStatus"] == ["ISSUED"]


# D-113: a link to something we never fetched ends at a :NotFetched stub, not a made-up company.
def test_not_fetched_stub():
    # An appointment held by a company we have no record of.
    rows = [row("ex:appointment/1", "type", {"iri": "ex:Appointment"}), row("ex:appointment/1", "officer", {"iri": "ch:999"})]
    # Build nodes, then relationships.
    nodes = build_nodes(rows)
    # The stub appears.
    rels, stubs = build_relationships(rows, nodes)
    # One HELD_BY to a :NotFetched stub with only its id.
    assert rels[0]["type"] == "HELD_BY" and stubs == {"ch:999": {"labels": ("NotFetched",), "props": {"id": "ch:999"}}}


# The same link stated twice stops the build (to be decided with make refresh), instead of making two relationships.
def test_duplicate_link_stops():
    # One link, two records.
    rows = [row("lei:A", "type", {"iri": "ex:LegalEntity"}), row("lei:B", "type", {"iri": "ex:LegalEntity"}),
            # The same parent link twice.
            row("lei:A", "fundManagedBy", {"iri": "lei:B"}), row("lei:A", "fundManagedBy", {"iri": "lei:B"})]
    # Build nodes.
    nodes = build_nodes(rows)
    # It refuses.
    with pytest.raises(ValueError):
        # The relationships.
        build_relationships(rows, nodes)
