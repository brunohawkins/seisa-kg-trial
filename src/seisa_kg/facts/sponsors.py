"""SUMMARY: Turns config/sponsors.toml into rows of the shared fact list.

The three sponsors (Hg, Bridgepoint, Apax) are our own choice (D-023), not
something a register states. So each row's origin is our rule D-023, not a
source record (D-040, following D-029).
"""

# Python's built-in reader for TOML settings files.
import tomllib
# A tidy way of working with file and folder paths.
from pathlib import Path

# The shared fact format: helpers to build rows.
from seisa_kg.facts.model import fact, iri, literal

# The project's top folder: this file's folder, then up three levels (facts → seisa_kg → src → project).
PROJECT_ROOT = Path(__file__).resolve().parents[3]
# The sponsor settings file (pipeline stage 0).
CONFIG_PATH = PROJECT_ROOT / "config" / "sponsors.toml"
# Every sponsor fact comes from our decision D-023 (D-040).
ORIGIN = {"kind": "rule", "rule": "D-023"}


# Build the rows for every sponsor: its type, its name and each of its search words.
def sponsor_facts() -> list[dict]:
    # Open the settings file in binary mode, as tomllib requires.
    with CONFIG_PATH.open("rb") as f:
        # Turn the TOML text into Python data.
        config = tomllib.load(f)
    # All the rows produced.
    rows = []
    # Each sponsor, by its short key (e.g. "apax") and its settings.
    for key, settings in config["sponsors"].items():
        # The sponsor's name in the graph, e.g. ex:sponsor/apax.
        subject = f"ex:sponsor/{key}"
        # "This is a sponsor" (a brand, not a legal entity).
        rows.append(fact(subject, "type", iri("ex:Sponsor"), ORIGIN))
        # The sponsor's name, as people write it.
        rows.append(fact(subject, "label", literal(settings["name"]), ORIGIN))
        # Each word we search GLEIF with for this sponsor.
        for term in settings["search_terms"]:
            # One row per search word.
            rows.append(fact(subject, "searchTerm", literal(term), ORIGIN))
    # Hand back every sponsor row.
    return rows
