"""SUMMARY: Pipeline stage 5 (query) for the property graph. Runs every investor
question in lpg/queries/*.cypher against Neo4j, records each answer with its
sources and how long it took, and checks it against the same question's SPARQL
answer (data/output/answers/rdf/, made by `make query`).

Each question file opens with the same header lines as the SPARQL files, written
as Cypher comments ("// QUESTION: ...", "// KEY: ...", ...). The check compares
the KEY and VALUE columns only (sources and dates are written differently by the
two databases), as a multiset: the same rows, the same number of times.

Outputs:
- data/output/answers/lpg/<question>.json: the full answer, every source included;
- docs/answers-lpg.md: the comparison table, then a readable report.

Timings: Oxigraph runs inside our Python process; Neo4j is a separate server
reached over the network (Bolt), so each Cypher time includes a round trip.
The two numbers are reported side by side, not as a fair race.

Run it with:  make query-lpg   (Neo4j must be running)
"""

# Reads and writes JSON.
import json
# Counts rows for the multiset comparison.
from collections import Counter
# The middle value of a list of timings.
from statistics import median
# A precise clock for timing queries.
import time
# A tidy way of working with file and folder paths.
from pathlib import Path

# The connection to Neo4j (password from .env, never printed).
from seisa_kg.lpg.build import connect
# The SPARQL runner's report writer, its prefix shortener and its settings, so both reports look the same.
from seisa_kg.rdf.ask import ANSWERS_DIR as RDF_ANSWERS, FIELDS, REPORT_ROWS, TIMED_RUNS, short, write_report

# This file's folder.
HERE = Path(__file__).resolve().parent
# The project's top folder.
PROJECT_ROOT = HERE.parents[2]
# Where the Cypher question files live.
QUERIES_DIR = HERE / "queries"
# Where the full answers are saved.
ANSWERS_DIR = PROJECT_ROOT / "data" / "output" / "answers" / "lpg"
# The readable report.
REPORT_PATH = PROJECT_ROOT / "docs" / "answers-lpg.md"


# Read a question file's header lines ("// FIELD: ...") into a dict.
def read_header(text: str) -> dict:
    # The fields found so far.
    header = {}
    # Each line of the file.
    for line in text.splitlines():
        # Each field we look for.
        for field in FIELDS:
            # A line like "// WHY: ...".
            if line.startswith(f"// {field}:"):
                # Keep the text after the colon.
                header[field] = line.split(":", 1)[1].strip()
    # Hand back the fields.
    return header


# Turn one Neo4j value into plain text, written the way the SPARQL answers write it.
def plain(value) -> str:
    # A missing value becomes empty text.
    if value is None:
        # Empty.
        return ""
    # A list (e.g. collected sources) becomes space-separated text, like SPARQL's GROUP_CONCAT.
    if isinstance(value, list):
        # Each item as text, joined by spaces.
        return " ".join(plain(v) for v in value)
    # A Neo4j date or date-time: its ISO text (e.g. "2026-10-18T13:03:52.144700+00:00").
    if hasattr(value, "iso_format"):
        # ISO text.
        return value.iso_format()
    # Anything else (text, numbers) as text.
    return str(value)


# Run one question: time it, and return its header, columns, rows and median time in milliseconds.
def run_question(driver, path: Path) -> dict:
    # The question file's text.
    text = path.read_text(encoding="utf-8")
    # Run it once untimed, so the first timed run isn't slowed by one-off setup (query planning).
    driver.execute_query(text)
    # The timed runs, in milliseconds.
    timings = []
    # Repeat the timed runs.
    for _ in range(TIMED_RUNS):
        # Start the clock.
        start = time.perf_counter()
        # Run the query; execute_query reads every row before it returns.
        result = driver.execute_query(text)
        # Stop the clock and keep the time.
        timings.append((time.perf_counter() - start) * 1000)
    # The column names, in RETURN order.
    columns = list(result.keys)
    # The answer as a list of {column: text} rows.
    answer = [{c: plain(record[c]) for c in columns} for record in result.records]
    # Everything about this run.
    return {"file": path.name, **read_header(text), "columns": columns, "rows": answer,
            # The median time, and every timing so the spread is visible.
            "median_ms": round(median(timings), 2), "timings_ms": [round(t, 2) for t in timings]}


# The columns the check compares: every KEY column (either side of "|" too) and the VALUE column.
def compared_columns(header: dict) -> list[str]:
    # KEY looks like "sponsorName, entity|name, status".
    names = [n.strip() for part in header.get("KEY", "").split(",") for n in part.split("|")]
    # Plus the VALUE column, if any.
    return [n for n in names + [header.get("VALUE", "")] if n]


# Compare the Cypher answer with the SPARQL answer; returns (same?, rows only in SPARQL, rows only in Cypher).
def compare(result: dict) -> tuple[bool, list, list]:
    # The SPARQL answer saved by `make query`.
    rdf = json.loads((RDF_ANSWERS / result["file"].replace(".cypher", ".json")).read_text(encoding="utf-8"))
    # The columns to compare.
    cols = compared_columns(result)
    # The SPARQL rows, with long web addresses shortened to our prefixes (lei:..., ex:...).
    a = Counter(tuple(short(row[c]) for c in cols) for row in rdf["rows"])
    # The Cypher rows (Neo4j already uses the short names).
    b = Counter(tuple(row[c] for c in cols) for row in result["rows"])
    # Same rows, same number of times; plus what differs on each side.
    return a == b, list((a - b).elements()), list((b - a).elements()), rdf["median_ms"]


# Connect, run every question, compare, save the answers and the report.
def main() -> None:
    # The connection.
    driver = connect()
    # Make sure the answers folder exists.
    ANSWERS_DIR.mkdir(parents=True, exist_ok=True)
    # Every question's result.
    results = []
    # The comparison table's rows.
    table = ["| Question | Rows (SPARQL / Cypher) | Same answer? | SPARQL ms | Cypher ms |", "|---|---|---|---|---|"]
    # Any differences, for the report.
    diffs = []
    # Each question file, in name order.
    for path in sorted(QUERIES_DIR.glob("*.cypher")):
        # Run it.
        result = run_question(driver, path)
        # Compare it with the SPARQL answer.
        same, only_rdf, only_lpg, rdf_ms = compare(result)
        # Save the full answer, every source included.
        (ANSWERS_DIR / f"{path.stem}.json").write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
        # Keep it for the report.
        results.append(result)
        # Its line in the comparison table.
        table.append(f"| {path.stem} | {len(result['rows']) + len(only_rdf) - len(only_lpg)} / {len(result['rows'])} | "
                     f"{'yes' if same else '**NO**'} | {rdf_ms} | {result['median_ms']} |")
        # Keep any differences.
        if not same:
            # The question, and up to 5 rows from each side.
            diffs += [f"- **{path.stem}**: only in SPARQL {only_rdf[:5]}; only in Cypher {only_lpg[:5]}"]
        # One progress line.
        print(f"{path.name}: {len(result['rows'])} rows, {result['median_ms']} ms, same as SPARQL: {same}")
    # Close the connection.
    driver.close()
    # The report's opening: what was compared, the table, any differences, and the timing caveat.
    opening = ["# Investor questions: property-graph answers (generated by `make query-lpg`; do not edit by hand)", "",
               "Each Cypher question is the twin of a SPARQL question. **Same answer** compares the KEY and VALUE "
               "columns as a multiset (same rows, same number of times).", "", *table, "",
               *(["**Differences:**", "", *diffs, ""] if diffs else []),
               f"Timings are the median of {TIMED_RUNS} runs. Oxigraph runs inside our Python process; Neo4j is a separate "
               "server reached over the network, so each Cypher time includes a round trip. Side by side, not a fair race.", ""]
    # Write the report, in the same format as the SPARQL one.
    write_report(results, opening, REPORT_PATH)
    # Say where it is.
    print(f"Report: {REPORT_PATH.relative_to(PROJECT_ROOT)}")


# Run main() when this file is run directly, not when it is imported.
if __name__ == "__main__":
    # Start.
    main()
