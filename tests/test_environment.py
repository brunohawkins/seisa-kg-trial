"""SUMMARY: Quick health checks for the project's setup.

These tests prove two things before any real work starts:
1. Every library the project depends on is installed and can be loaded.
2. Our RDF database (pyoxigraph) supports RDF-star, the way we chose to
   attach a source to each fact in the RDF graph (decision D-015).

In this version of pyoxigraph (RDF 1.2), an annotation creates a hidden
"reifier" node that points at the fact, and the source hangs off that
node. The tests check that layout, so we notice if a future upgrade
changes it.

Run them with:  uv run pytest
"""

# Lets us load a library by its name written as text, so one test can loop over many.
import importlib

# The test runner. Gives us helpers like running one test several times.
import pytest

# The RDF database library we use for RDF-star.
import pyoxigraph as ox

# A short web-address prefix for made-up test data, so the Turtle below stays readable.
EX = "http://example.org/"

# A tiny RDF-star example in Turtle (a text format for RDF). It states one fact,
# "Fund A is managed by Firm B", and inside the {| ... |} brackets attaches two
# details about that fact: which record it came from, and when we fetched it.
FACT_WITH_SOURCE = f"""
@prefix ex: <{EX}> .
ex:fundA ex:managedBy ex:firmB {{| ex:source ex:gleifRecord1 ; ex:retrievedAt "2026-10-16" |}} .
""".encode()  # The database wants raw bytes, so turn the text into bytes.


# Run the same check once for each library name in this list.
@pytest.mark.parametrize(
    # The name the test will use for each item in the list.
    "module_name",
    # Every library the project relies on, by the name Python imports it as.
    ["pymupdf", "docx", "httpx", "rdflib", "pyoxigraph", "neo4j", "dotenv"],
)
# Check that one library is installed and loads without errors.
def test_library_imports(module_name):
    # Try to load the library; if it is missing, this line fails the test.
    importlib.import_module(module_name)


# Builds a fresh, empty in-memory RDF database holding the example fact.
def _store_with_example_fact():
    # Create an empty database that lives only in memory (nothing saved to disk).
    store = ox.Store()
    # Read the example Turtle text into the database.
    store.load(FACT_WITH_SOURCE, format=ox.RdfFormat.TURTLE)
    # Hand the filled database back to whichever test asked for it.
    return store


# Check that the fact itself is stored as a normal, true statement.
def test_annotated_fact_is_still_asserted():
    # Get a database containing the example fact.
    store = _store_with_example_fact()
    # Ask a yes/no question: does "Fund A is managed by Firm B" exist in the data?
    result = store.query(f"ASK {{ <{EX}fundA> <{EX}managedBy> <{EX}firmB> }}")
    # The answer must be yes; annotating a fact must not hide the fact.
    assert bool(result)


# Check that we can ask "where did this fact come from?" and get the source back.
def test_source_can_be_queried_from_fact():
    # Get a database containing the example fact.
    store = _store_with_example_fact()
    # SPARQL question: for any "managed by" fact, find its attached source and date.
    rows = list(store.query(
        # Use the short "ex:" prefix in the question too.
        f"PREFIX ex: <{EX}> "
        # Ask for the fund, the manager, the source and the date.
        "SELECT ?fund ?manager ?src ?when WHERE { "
        # Match the fact, then look inside its annotation for source and date.
        "?fund ex:managedBy ?manager {| ex:source ?src ; ex:retrievedAt ?when |} }"
    ))
    # There should be exactly one answer, because we stored exactly one fact.
    assert len(rows) == 1
    # The source returned must be the GLEIF record we attached.
    assert rows[0]["src"] == ox.NamedNode(f"{EX}gleifRecord1")
    # The date returned must be the date we attached.
    assert rows[0]["when"].value == "2026-10-16"


# Check the RDF 1.2 layout: the annotation hangs off a "reifier" node that
# points at the fact through the standard property rdf:reifies.
def test_annotation_uses_a_reifier_node():
    # Get a database containing the example fact.
    store = _store_with_example_fact()
    # The standard RDF property that links a reifier node to the fact it describes.
    reifies = ox.NamedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#reifies")
    # Collect every stored statement whose middle part is rdf:reifies.
    links = list(store.quads_for_pattern(None, reifies, None))
    # There should be exactly one reifier, for our one annotated fact.
    assert len(links) == 1
    # The thing the reifier points at must be a "triple term" (a fact used as a value).
    assert isinstance(links[0].object, ox.Triple)
