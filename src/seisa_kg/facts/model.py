"""SUMMARY: The shared fact format (decisions D-012, D-033, D-041).

Every fact in the project, whatever its source, is one row with the same
fields, and the rows are saved one per line in data/interim/facts.jsonl.
Both graph builders (RDF and Neo4j) read this one file.

A row looks like this:
    {"subject":   "lei:894500H5QJCD6LESMR63",
     "predicate": "fundManagedBy",
     "object":    {"iri": "lei:894500C7AD948MWIA623"},
     "details":   {"startDate": {"value": "2021-01-17T23:00:00Z", "datatype": "dateTime"}},
     "origin":    {"kind": "source", "record": "src:gleif/894500H5QJCD6LESMR63/fund-manager/20261018",
                   "source": "GLEIF", "url": "https://...", "retrieved_at": "2026-10-18T13:52:00+00:00"}}

- object and each detail are either {"iri": ...} (a link to another thing)
  or {"value": ..., "datatype": ...} (a plain value; datatype is optional).
- origin is either a source record (kind "source", D-035) or one of our
  rules (kind "rule", with "rule": "D-028"), so "the register says" and
  "we concluded" are always told apart (D-029).
"""

# Reads and writes JSON, one row per line.
import json
# A tidy way of working with file and folder paths.
from pathlib import Path

# The project's top folder: this file's folder, then up three levels (facts → seisa_kg → src → project).
PROJECT_ROOT = Path(__file__).resolve().parents[3]
# Where the shared fact list lives (D-041).
FACTS_PATH = PROJECT_ROOT / "data" / "interim" / "facts.jsonl"


# Make a link value: the object (or a detail) is another thing, named by a short IRI like "lei:...".
def iri(name: str) -> dict:
    # Wrap the name so builders know it is a link, not text.
    return {"iri": name}


# Make a plain value, with an optional datatype such as "date" or "dateTime".
def literal(value: str, datatype: str | None = None) -> dict:
    # Plain text needs no datatype.
    if datatype is None:
        # Just the value.
        return {"value": value}
    # A typed value, e.g. a date.
    return {"value": value, "datatype": datatype}


# Build one fact row with all five fields (D-033).
def fact(subject: str, predicate: str, obj: dict, origin: dict, details: dict | None = None) -> dict:
    # The row, with empty details if none were given.
    return {"subject": subject, "predicate": predicate, "object": obj,
            # Extra facts about this fact, e.g. a start date; empty if there are none.
            "details": details or {},
            # Where the fact came from: a source record or one of our rules.
            "origin": origin}


# Write rows to the fact file, one JSON object per line, in a fixed order so re-runs give identical files.
def write_facts(rows: list[dict], path: Path = FACTS_PATH) -> None:
    # Make sure data/interim/ exists.
    path.parent.mkdir(parents=True, exist_ok=True)
    # Sort by the row's full text, so the order never depends on file-system order.
    lines = sorted(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in rows)
    # Save every line, each ending with a newline.
    path.write_text("".join(line + "\n" for line in lines), encoding="utf-8")


# Read the fact file back into a list of rows.
def read_facts(path: Path = FACTS_PATH) -> list[dict]:
    # Open the file as text.
    with path.open(encoding="utf-8") as f:
        # Turn each non-empty line back into a row.
        return [json.loads(line) for line in f if line.strip()]
