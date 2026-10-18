"""SUMMARY: Tests for the investor question files (src/seisa_kg/rdf/queries/).

Every question file must parse as SPARQL and carry the header lines the
runner reads (QUESTION, WHY, TYPE). This catches mistakes like writing
"ex:sponsor/apax", where SPARQL reads the "/" as a path, before a build.
"""

# Lets one test run once per question file.
import pytest
# The RDF database library.
import pyoxigraph as ox

# The runner's header reader and where the question files live.
from seisa_kg.rdf.ask import QUERIES_DIR, read_header

# Every question file, in name order.
QUESTION_FILES = sorted(QUERIES_DIR.glob("*.rq"))


# There is at least one question to test (an empty folder would make every other test pass on nothing, F12).
def test_there_are_questions():
    # At least one file.
    assert QUESTION_FILES


# Each question file parses and runs (on an empty graph, so it returns nothing, but a syntax error would fail).
@pytest.mark.parametrize("path", QUESTION_FILES, ids=lambda p: p.name)
def test_question_parses(path):
    # Running the query on an empty database raises an error if the SPARQL is malformed.
    list(ox.Store().query(path.read_text(encoding="utf-8")))


# Each question file has the header lines the report needs.
@pytest.mark.parametrize("path", QUESTION_FILES, ids=lambda p: p.name)
def test_question_has_header(path):
    # Read the header.
    header = read_header(path.read_text(encoding="utf-8"))
    # The three required fields must all be there and non-empty.
    assert all(header.get(field) for field in ("QUESTION", "WHY", "TYPE"))
