"""SUMMARY: Pipeline stage 4 (build) for the RDF graph. Reads the shared fact
list (data/interim/facts.jsonl), builds the RDF graph in Oxigraph, checks it,
and saves it as data/output/graph.ttl (Turtle 1.2, with RDF-star).

How each fact row becomes RDF (docs/schema/rdf-schema.md, section 6):
- the row's subject, predicate and object become one triple;
- an annotation (a hidden "reifier" node, RDF 1.2) is attached to that triple:
  - a source fact's annotation points to its SourceRecord (prov:wasDerivedFrom, D-035);
  - our own judgement's annotation points to our rule (prov:wasGeneratedBy, D-029);
  - each of the row's details (start date, status...) is one more property on it;
- each SourceRecord node is built once, from the origin fields of its rows.

The checks (D-038), any of which stops the build:
- the graph must not be empty (an empty graph passes every rule, finding F12);
- one annotation per row, for every predicate (D-033: same data, nothing lost);
- every annotation has an origin (SPARQL, because pyshacl can't see annotations);
- the SHACL shapes in shapes.ttl (pyshacl, on the parts it can see).

Run it with:  make rdf
"""

# Counts how often each value appears.
from collections import Counter
# A tidy way of working with file and folder paths.
from pathlib import Path
# Lets the program stop with an error code when a check fails.
import sys

# The RDF database that supports RDF-star (D-013, D-015).
import pyoxigraph as ox
# The SHACL checker (D-013, D-038).
import pyshacl
# The RDF toolkit pyshacl works on.
import rdflib

# Reading the shared fact list.
from seisa_kg.facts.model import FACTS_PATH, read_facts

# This file's folder, where the shapes and the check queries live.
HERE = Path(__file__).resolve().parent
# The project's top folder: this file's folder, then up three levels (rdf → seisa_kg → src → project).
PROJECT_ROOT = HERE.parents[2]
# Where the finished graph is saved.
OUTPUT_PATH = PROJECT_ROOT / "data" / "output" / "graph.ttl"
# The SHACL shapes file.
SHAPES_PATH = HERE / "shapes.ttl"
# The SPARQL check for annotations with no origin.
ORIGIN_CHECK_PATH = HERE / "checks" / "annotation_without_origin.rq"

# The short prefixes used in fact rows, and the full web addresses they stand for (D-037).
PREFIXES = {
    # Our own vocabulary: classes, properties, sponsors, rules, scope decisions.
    "ex": "https://seisa-kg.example/def/",
    # Entities named by their LEI (D-034).
    "lei": "https://seisa-kg.example/lei/",
    # Entities named by their Companies House number (D-034, from Monday).
    "ch": "https://seisa-kg.example/ch/",
    # Source records (D-035).
    "src": "https://seisa-kg.example/source/",
    # The W3C provenance vocabulary.
    "prov": "http://www.w3.org/ns/prov#",
    # The core RDF vocabulary.
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    # RDF Schema, which holds rdfs:label.
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    # XML Schema datatypes.
    "xsd": "http://www.w3.org/2001/XMLSchema#",
}
# Predicates in rows that map to standard terms rather than to our own ex: vocabulary.
STANDARD_PREDICATES = {"type": "rdf:type", "label": "rdfs:label",
                       # The provenance links used by scope decisions (D-036, D-037).
                       "wasGeneratedBy": "prov:wasGeneratedBy", "wasRevisionOf": "prov:wasRevisionOf"}
# The datatype names used in rows, and the XML Schema datatypes they mean.
DATATYPES = {"date": "xsd:date", "dateTime": "xsd:dateTime"}


# Turn a short name like "lei:ABC" into a full web address (an RDF "named node").
def node(short: str) -> ox.NamedNode:
    # Split at the first colon: prefix, then the local part.
    prefix, local = short.split(":", 1)
    # Glue the prefix's full address to the local part.
    return ox.NamedNode(PREFIXES[prefix] + local)


# Turn a row's predicate name into its RDF property.
def predicate(name: str) -> ox.NamedNode:
    # A standard term if there is one, otherwise our own vocabulary.
    return node(STANDARD_PREDICATES.get(name, f"ex:{name}"))


# Turn a row's object or detail ({"iri": ...} or {"value": ..., "datatype": ...}) into an RDF term.
def term(value: dict) -> ox.NamedNode | ox.Literal:
    # A link to another thing becomes a named node.
    if "iri" in value:
        # Expand the short name.
        return node(value["iri"])
    # A typed value (e.g. a date) gets its XML Schema datatype.
    if "datatype" in value:
        # e.g. "2021-01-17T23:00:00Z"^^xsd:dateTime.
        return ox.Literal(value["value"], datatype=node(DATATYPES[value["datatype"]]))
    # Anything else is plain text.
    return ox.Literal(value["value"])


# Build the graph from the fact rows. Returns the filled Oxigraph store.
def build(rows: list[dict]) -> ox.Store:
    # A fresh in-memory database.
    store = ox.Store()
    # The standard property that links an annotation to the fact it describes.
    reifies = node("rdf:reifies")
    # Source records already seen: record name -> its origin block, so each is built once.
    records = {}
    # Go through every fact row.
    for row in rows:
        # The fact itself, as a triple.
        fact = ox.Triple(node(row["subject"]), predicate(row["predicate"]), term(row["object"]))
        # Assert the fact: it is now part of the graph.
        store.add(ox.Quad(fact.subject, fact.predicate, fact.object))
        # A new annotation node for this row (a fact with two sources gets two).
        annotation = ox.BlankNode()
        # Point the annotation at the fact (RDF 1.2: annotation rdf:reifies <<( s p o )>>).
        store.add(ox.Quad(annotation, reifies, fact))
        # The row's origin: a source record or one of our rules.
        origin = row["origin"]
        # A source fact: point to its source record (D-035).
        if origin["kind"] == "source":
            # annotation prov:wasDerivedFrom src:...
            store.add(ox.Quad(annotation, node("prov:wasDerivedFrom"), node(origin["record"])))
            # Remember the record so its node is built once, below.
            records.setdefault(origin["record"], origin)
        # Our own judgement: point to the rule that made it (D-029).
        else:
            # annotation prov:wasGeneratedBy ex:rule/D-0xx
            store.add(ox.Quad(annotation, node("prov:wasGeneratedBy"), node(f"ex:rule/{origin['rule']}")))
        # Each detail (start date, status...) becomes one more property on the annotation.
        for name, value in row["details"].items():
            # annotation ex:<name> <value>
            store.add(ox.Quad(annotation, node(f"ex:{name}"), term(value)))
    # Build each source record node once (D-035).
    for name, origin in records.items():
        # The record's node.
        record = node(name)
        # "This is a source record."
        store.add(ox.Quad(record, node("rdf:type"), node("ex:SourceRecord")))
        # Which source, e.g. ex:GLEIF.
        store.add(ox.Quad(record, node("ex:source"), node(f"ex:{origin['source']}")))
        # The exact web address the reply came from.
        store.add(ox.Quad(record, node("ex:url"), ox.Literal(origin["url"])))
        # When we fetched it, as a proper date and time.
        store.add(ox.Quad(record, node("ex:retrievedAt"),
                          # The fetch time, typed as xsd:dateTime.
                          ox.Literal(origin["retrieved_at"], datatype=node("xsd:dateTime"))))
    # Hand back the filled database.
    return store


# Run every check (D-038). Returns a list of problems; an empty list means the graph passed.
def check(store: ox.Store, rows: list[dict]) -> list[str]:
    # The problems found so far.
    problems = []
    # Check 0: the graph must not be empty, or every other check would pass on nothing (F12).
    if len(store) == 0 or not rows:
        # Nothing else is worth checking.
        return ["the graph or the fact list is empty"]
    # Count the annotations per predicate, using the fact each one points at.
    annotations = Counter(q.object.predicate for q in store.quads_for_pattern(None, node("rdf:reifies"), None))
    # Count the rows per predicate, as RDF properties.
    expected = Counter(predicate(r["predicate"]) for r in rows)
    # Every predicate must have exactly one annotation per row (D-033).
    for prop in expected.keys() | annotations.keys():
        # Compare the two counts.
        if expected[prop] != annotations[prop]:
            # Report the mismatch.
            problems.append(f"{prop.value}: {expected[prop]} rows but {annotations[prop]} annotations")
    # Check 4: every annotation has an origin (SPARQL in Oxigraph, D-038).
    orphans = list(store.query(ORIGIN_CHECK_PATH.read_text(encoding="utf-8")))
    # Any row returned is a fact with no source and no rule.
    if orphans:
        # Report how many.
        problems.append(f"{len(orphans)} annotations have no source record and no rule")
    # Checks 1–3: SHACL, on a copy of the graph without the annotation links pyshacl can't read (F12).
    plain = ox.Store()
    # Copy every statement whose value is not a triple term.
    plain.extend(q for q in store if not isinstance(q.object, ox.Triple))
    # Hand the copy to rdflib as N-Triples text.
    data = rdflib.Graph().parse(data=plain.dump(format=ox.RdfFormat.N_TRIPLES, from_graph=ox.DefaultGraph()),
                                # Say what format the text is in.
                                format="nt")
    # Make sure the copy really arrived: an empty copy would "conform" silently (F12).
    if len(data) == 0:
        # Report it.
        problems.append("SHACL was given an empty graph")
    # Run the SHACL shapes.
    conforms, _, report = pyshacl.validate(data, shacl_graph=str(SHAPES_PATH), shacl_graph_format="turtle")
    # If any shape failed, keep pyshacl's report.
    if not conforms:
        # Report it in full.
        problems.append("SHACL failed:\n" + report)
    # Hand back the problems (none means pass).
    return problems


# Build, check and save the RDF graph.
def main() -> None:
    # Read the shared fact list.
    rows = read_facts(FACTS_PATH)
    # Build the graph.
    store = build(rows)
    # Say how big it is.
    print(f"Built the RDF graph: {len(rows)} facts -> {len(store)} triples (facts, annotations, source records)")
    # Run every check.
    problems = check(store, rows)
    # If anything failed, list it and stop with an error code, so `make` stops too.
    if problems:
        # One line per problem.
        for p in problems:
            # Print to the error stream.
            print("CHECK FAILED:", p, file=sys.stderr)
        # Exit with an error.
        sys.exit(1)
    # Every check passed.
    print("All checks passed: not empty; one annotation per fact; every annotation has an origin; SHACL")
    # Make sure data/output/ exists.
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Save the graph as Turtle 1.2, writing names with the short prefixes so the file stays readable.
    store.dump(OUTPUT_PATH, format=ox.RdfFormat.TURTLE, from_graph=ox.DefaultGraph(), prefixes=PREFIXES)
    # Say where it was saved.
    print(f"Saved {OUTPUT_PATH.relative_to(PROJECT_ROOT)}")


# Run main() when this file is run directly, not when it is imported.
if __name__ == "__main__":
    # Start.
    main()
