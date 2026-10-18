"""SUMMARY: Pipeline stage 5 (query) for the RDF graph. Loads the saved graph
(data/output/graph.ttl), runs every investor question in rdf/queries/*.rq,
and records each answer with its sources and how long it took (brief §3).

Each question file opens with comment lines the runner reads:
    # QUESTION: ...   the question in plain English
    # WHY: ...        why an investor would ask it
    # TYPE: ...       what kind of question it is (several links, counting, ...)
    # NOTE: ...       (optional) anything a reader must know about the answer
    # KEY: ...        for scoring (D-059): the columns that identify one answer item;
    #                 commas mean "all of these", "|" means "either of these"
    # VALUE: ...      (optional) for scoring: the column holding a number, given partial credit

Outputs:
- data/output/answers/rdf/<question>.json: the full answer, every source included;
- docs/answers-rdf.md: a readable report (long source lists shortened).

A question that returns no rows is flagged, not passed silently (lesson of F12).

Run it with:  make query
"""

# Reads and writes JSON.
import json
# The middle value of a list of timings.
from statistics import median
# A precise clock for timing queries.
import time
# A tidy way of working with file and folder paths.
from pathlib import Path

# The RDF database (D-013).
import pyoxigraph as ox

# The short prefixes, used to print long web addresses briefly.
from seisa_kg.rdf.build import OUTPUT_PATH, PREFIXES

# This file's folder.
HERE = Path(__file__).resolve().parent
# The project's top folder: this file's folder, then up three levels (rdf → seisa_kg → src → project).
PROJECT_ROOT = HERE.parents[2]
# Where the question files live.
QUERIES_DIR = HERE / "queries"
# Where the full answers are saved.
ANSWERS_DIR = PROJECT_ROOT / "data" / "output" / "answers" / "rdf"
# The readable report.
REPORT_PATH = PROJECT_ROOT / "docs" / "answers-rdf.md"
# How many timed runs per question; the middle (median) one is reported.
TIMED_RUNS = 5
# How many rows of each answer the report shows (the JSON keeps them all).
REPORT_ROWS = 20
# The header fields the runner reads from each question file.
FIELDS = ("QUESTION", "WHY", "TYPE", "NOTE", "KEY", "VALUE")


# Read a question file's header lines into a dict, e.g. {"QUESTION": "...", "WHY": "..."}.
def read_header(text: str) -> dict:
    # The fields found so far.
    header = {}
    # Look at each line of the file.
    for line in text.splitlines():
        # Each field we look for.
        for field in FIELDS:
            # A line like "# WHY: ..." (SPARQL) or "// WHY: ..." (Cypher).
            if line.startswith((f"# {field}:", f"// {field}:")):
                # Keep the text after the colon.
                header[field] = line.split(":", 1)[1].strip()
    # Hand back the fields.
    return header


# Turn one answer value into plain text: a web address, a value, or empty.
def plain(term) -> str:
    # A missing value (e.g. an OPTIONAL that found nothing) becomes empty text.
    if term is None:
        # Empty.
        return ""
    # Both named nodes and literals carry their text in .value.
    return term.value


# Shorten a long web address with our prefixes, e.g. "https://seisa-kg.example/lei/X" -> "lei:X".
def short(text: str) -> str:
    # Try each prefix.
    for prefix, base in PREFIXES.items():
        # If the text starts with this prefix's address...
        if text.startswith(base):
            # ...swap it for the short form.
            return f"{prefix}:{text[len(base):]}"
    # Not one of ours; leave it as it is.
    return text


# Run one question: time it, and return its header, column names, rows and median time in milliseconds.
def run_question(store: ox.Store, path: Path) -> dict:
    # The question file's text.
    text = path.read_text(encoding="utf-8")
    # Run it once untimed, so the first timed run isn't slowed by one-off setup.
    list(store.query(text))
    # The timed runs, in milliseconds.
    timings = []
    # Repeat the timed runs.
    for _ in range(TIMED_RUNS):
        # Start the clock.
        start = time.perf_counter()
        # Run the query and collect every row (a query only runs fully when its rows are read).
        solutions = store.query(text)
        # Read all the rows.
        rows = list(solutions)
        # Stop the clock and keep the time.
        timings.append((time.perf_counter() - start) * 1000)
    # The column names, in the order the SELECT lists them.
    columns = [v.value for v in solutions.variables]
    # The answer as a list of {column: text} rows.
    answer = [{c: plain(row[c]) for c in columns} for row in rows]
    # Everything about this run.
    return {"file": path.name, **read_header(text), "columns": columns, "rows": answer,
            # The median time, and every timing so the spread is visible.
            "median_ms": round(median(timings), 2), "timings_ms": [round(t, 2) for t in timings]}


# Format one cell for the report: short names, and long source lists cut to the first one plus a count.
def cell(column: str, text: str) -> str:
    # A list of sources: show the first and say how many more.
    if column == "sources" and " " in text:
        # Split the list into its web addresses.
        urls = text.split(" ")
        # The first one, plus a count of the rest.
        return f"{urls[0]} (+{len(urls) - 1} more)"
    # Anything else: shortened, with "|" made safe for a Markdown table.
    return short(text).replace("|", "\\|")


# Write a readable report: the given opening lines, then one section per question (shared by the Neo4j runner).
def write_report(results: list[dict], opening: list[str], path: Path = REPORT_PATH) -> None:
    # Start with the opening lines.
    L = list(opening)
    # One section per question.
    for r in results:
        # The heading and the plain-English parts.
        L += [f"## {r['file']}", "", f"**Question:** {r.get('QUESTION', '')}", "",
              # Why it matters, and what type it is.
              f"**Why it matters:** {r.get('WHY', '')}", "", f"**Type:** {r.get('TYPE', '')}", ""]
        # The note, if the question has one.
        if r.get("NOTE"):
            # Add it.
            L += [f"**Note:** {r['NOTE']}", ""]
        # Size and timing of the answer.
        L += [f"**Answer:** {len(r['rows'])} rows, {r['median_ms']} ms.", ""]
        # For the Neo4j answers: how well they agree with the RDF answer, scored by the answer scorer.
        if r.get("agreement"):
            # The scores, and anything that differs.
            a = r["agreement"]
            # One line.
            L += [f"**Agreement with the RDF answer:** overall {a['overall']} (correctness {a['correctness']}, citation {a['citation']})"
                  # The non-zero differences, if any.
                  + (f"; differences: {a['errors']}" if any(a["errors"].values()) else "; identical."), ""]
        # Flag an empty answer rather than passing it silently.
        if not r["rows"]:
            # The warning.
            L += ["> **No rows.** Check the query: an empty answer can hide a mistake (F12).", ""]
            # Nothing more to show for this question.
            continue
        # The table header.
        L += ["| " + " | ".join(r["columns"]) + " |", "|" + "---|" * len(r["columns"])]
        # The first rows.
        for row in r["rows"][:REPORT_ROWS]:
            # One table row.
            L.append("| " + " | ".join(cell(c, row[c]) for c in r["columns"]) + " |")
        # Say if rows were left out of the report.
        if len(r["rows"]) > REPORT_ROWS:
            # The note.
            L += ["", f"*…and {len(r['rows']) - REPORT_ROWS} more rows in the JSON file.*"]
        # A blank line before the next section.
        L.append("")
    # Save the report.
    path.write_text("\n".join(L), encoding="utf-8")


# Load the graph, run every question, save the answers and the report.
def main() -> None:
    # Start the clock for loading.
    start = time.perf_counter()
    # A fresh in-memory database.
    store = ox.Store()
    # Load the saved graph (Turtle 1.2, with RDF-star).
    store.load(path=str(OUTPUT_PATH), format=ox.RdfFormat.TURTLE)
    # How long loading took, in milliseconds.
    load_ms = (time.perf_counter() - start) * 1000
    # Make sure the answers folder exists.
    ANSWERS_DIR.mkdir(parents=True, exist_ok=True)
    # Every question's result.
    results = []
    # Each question file, in name order (q01, q02, ...).
    for path in sorted(QUERIES_DIR.glob("*.rq")):
        # Run it.
        result = run_question(store, path)
        # Save the full answer, every source included.
        (ANSWERS_DIR / f"{path.stem}.json").write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
        # Keep it for the report.
        results.append(result)
        # One progress line, flagging an empty answer.
        print(f"{path.name}: {len(result['rows'])} rows, {result['median_ms']} ms" + ("  <- NO ROWS" if not result["rows"] else ""))
    # Write the readable report.
    write_report(results, ["# Investor questions: RDF answers (generated by `make query`; do not edit by hand)", "",
                           # How big the graph was, and how long it took to load, so timings can be compared later.
                           f"Graph: {len(store):,} triples, loaded in {load_ms:.0f} ms. Timings are the median of {TIMED_RUNS} runs.",
                           # The status of the questions themselves.
                           "Questions are placeholder drafts (D-058). Full answers, with every source: `data/output/answers/rdf/`.", ""])
    # Say where it is.
    print(f"Report: {REPORT_PATH.relative_to(PROJECT_ROOT)}")


# Run main() when this file is run directly, not when it is imported.
if __name__ == "__main__":
    # Start.
    main()
