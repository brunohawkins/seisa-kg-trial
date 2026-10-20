"""SUMMARY: Run any SPARQL query against our RDF graph and print the answer as a
table. A practice tool for learning SPARQL (Oxigraph has no point-and-click
window like Neo4j Desktop, so this is our query box).

The usual prefixes (ex:, lei:, ch:, src:, rdf:, rdfs:, xsd:, prov:) are added
for you if the query doesn't declare them, so short practice queries work.

Use:
  uv run python scripts/sparql.py "SELECT ?k (COUNT(*) AS ?n) WHERE { ?d ex:dealKind ?k } GROUP BY ?k"
  uv run python scripts/sparql.py src/seisa_kg/rdf/queries/q01_apax_fund_managers.rq
"""

# Reads the command-line arguments.
import sys
# Measures how long the query takes.
import time
# A tidy way of working with file paths.
from pathlib import Path

# The RDF database (the same one the pipeline uses).
import pyoxigraph as ox

# The RDF graph built by `make rdf`.
GRAPH = Path(__file__).resolve().parents[1] / "data" / "output" / "graph.ttl"
# The prefixes our graph uses, added to any query that doesn't declare ex: itself.
PREFIXES = """PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd:  <http://www.w3.org/2001/XMLSchema#>
PREFIX prov: <http://www.w3.org/ns/prov#>
PREFIX ex:   <https://seisa-kg.example/def/>
PREFIX lei:  <https://seisa-kg.example/lei/>
PREFIX ch:   <https://seisa-kg.example/ch/>
PREFIX src:  <https://seisa-kg.example/source/>
"""
# The most rows to print.
MAX_ROWS = 30


# A value as short, readable text: IRIs shortened back to their prefix form.
def show(term) -> str:
    # An empty cell (e.g. from OPTIONAL).
    if term is None:
        # Shown as a dash.
        return "–"
    # The term's text.
    text = term.value
    # Each prefix and its address.
    for line in PREFIXES.splitlines():
        # e.g. "ex:" and "https://seisa-kg.example/def/".
        name, address = line.split()[1], line.split()[2].strip("<>")
        # An IRI under that address: write it the short way.
        if isinstance(term, ox.NamedNode) and text.startswith(address):
            # e.g. "ex:deal/hg-01-d1".
            return name + text[len(address):]
    # Anything else as it is.
    return text


# Run the query given on the command line.
def main() -> None:
    # The argument: a query, or a path to a .rq file.
    arg = sys.argv[1]
    # A file path: read the query from it; otherwise the argument is the query.
    query = Path(arg).read_text(encoding="utf-8") if arg.endswith(".rq") else arg
    # Add the prefixes if the query doesn't declare them.
    if "PREFIX ex:" not in query:
        # Prefixes first.
        query = PREFIXES + query
    # Load the graph (about 2 seconds).
    store = ox.Store()
    # From the file.
    store.bulk_load(path=str(GRAPH), format=ox.RdfFormat.TURTLE)
    # Time the query itself.
    start = time.perf_counter()
    # Run it.
    results = store.query(query)
    # The column names.
    columns = [v.value for v in results.variables]
    # Every row, as text.
    rows = [[show(r[c]) for c in columns] for r in results]
    # How long it took, in milliseconds.
    ms = (time.perf_counter() - start) * 1000
    # Each column's width: its widest cell, capped at 60 characters.
    widths = [min(60, max([len(c)] + [len(r[i]) for r in rows])) for i, c in enumerate(columns)]
    # The header line.
    print("  ".join(c.ljust(w) for c, w in zip(columns, widths)))
    # Each row, cut to fit.
    for r in rows[:MAX_ROWS]:
        # Cells padded to their column width.
        print("  ".join(cell[:w].ljust(w) for cell, w in zip(r, widths)))
    # The row count and time.
    print(f"\n{len(rows)} rows, {ms:.1f} ms" + (f" (first {MAX_ROWS} shown)" if len(rows) > MAX_ROWS else ""))


# Run main() when the file is run directly.
if __name__ == "__main__":
    # Go.
    main()
