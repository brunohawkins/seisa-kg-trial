"""SUMMARY: Tests for the RDF builder (src/seisa_kg/rdf/build.py).

Finding F12 showed that a check can "pass" on nothing at all. So besides
checking that a good graph passes, each test here breaks the graph on purpose
and makes sure the matching check catches it. A check that never fails proves
nothing.

The facts are tiny hand-made examples, not real data (PLAN: fixtures for tests only).
"""

# The RDF database library, used to break the graph on purpose.
import pyoxigraph as ox

# The builder's functions under test.
from seisa_kg.rdf.build import build, check, node
# Helpers to make fact rows.
from seisa_kg.facts.model import fact, iri, literal

# A made-up source record origin, shaped like a real GLEIF one.
SOURCE = {"kind": "source", "record": "src:gleif/FUNDLEI/record/20261018", "source": "GLEIF",
          # A made-up address and fetch time.
          "url": "https://api.gleif.org/api/v1/lei-records/FUNDLEI", "retrieved_at": "2026-10-18T13:00:00+00:00"}


# A small, correct set of facts: one entity with a type, a name and a manager link with a start date.
def good_rows() -> list[dict]:
    # The rows.
    return [
        # "This is a legal entity."
        fact("lei:FUNDLEI", "type", iri("ex:LegalEntity"), SOURCE),
        # Its legal name.
        fact("lei:FUNDLEI", "legalName", literal("Example Fund L.P."), SOURCE),
        # Its fund manager, with a start date on the annotation.
        fact("lei:FUNDLEI", "fundManagedBy", iri("lei:MGRLEI"), SOURCE,
             # The start date, typed as a date and time.
             {"startDate": literal("2021-01-17T23:00:00Z", "dateTime")}),
    ]


# A correct graph passes every check.
def test_good_graph_passes():
    # Build from the good rows.
    rows = good_rows()
    # No problems expected.
    assert check(build(rows), rows) == []


# Each row gets exactly one annotation, and the details sit on the annotation, not on the entity.
def test_details_sit_on_the_annotation():
    # Build from the good rows.
    store = build(good_rows())
    # Find the annotation that carries the start date.
    holders = [q.subject for q in store.quads_for_pattern(None, node("ex:startDate"), None)]
    # Exactly one thing carries it...
    assert len(holders) == 1
    # ...and it is an annotation (a blank node), not the fund itself.
    assert isinstance(holders[0], ox.BlankNode)


# An empty graph must fail, not "conform" (the F12 trap).
def test_empty_graph_fails():
    # Check an empty database against an empty fact list.
    assert check(ox.Store(), []) == ["the graph or the fact list is empty"]


# An annotation with its source link removed must be caught by the SPARQL check.
def test_annotation_without_origin_is_caught():
    # Build from the good rows.
    rows = good_rows()
    # Build the graph.
    store = build(rows)
    # Remove one annotation's link to its source record.
    store.remove(next(iter(store.quads_for_pattern(None, node("prov:wasDerivedFrom"), None))))
    # The check must report it.
    assert any("no source record and no rule" in p for p in check(store, rows))


# A source record missing its web address must be caught by SHACL.
def test_source_record_without_url_is_caught():
    # Build from the good rows.
    rows = good_rows()
    # Build the graph.
    store = build(rows)
    # Remove the source record's web address.
    store.remove(next(iter(store.quads_for_pattern(None, node("ex:url"), None))))
    # SHACL must report it.
    assert any(p.startswith("SHACL failed") for p in check(store, rows))


# A row that never made it into the graph must be caught by the count check (D-033).
def test_missing_fact_is_caught():
    # Build from only the first two rows...
    store = build(good_rows()[:2])
    # ...but check against all three.
    assert any("fundManagedBy" in p for p in check(store, good_rows()))
