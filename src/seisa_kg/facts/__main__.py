"""SUMMARY: Pipeline stage 2 (parse), run as one command. Builds the shared
fact list, data/interim/facts.jsonl, from the cached sources and the sponsor
settings, then prints how many facts of each kind it wrote.

Run it with:  make facts   (or: uv run python -m seisa_kg.facts)
"""

# Counts how often each value appears.
from collections import Counter

# The GLEIF parser: cached replies -> rows.
from seisa_kg.facts.gleif_parse import parse_all
# Saving the rows, and where they are saved.
from seisa_kg.facts.model import FACTS_PATH, write_facts
# The sponsor rows, from config/sponsors.toml.
from seisa_kg.facts.sponsors import sponsor_facts


# Build and save the fact list.
def main() -> None:
    # Parse the GLEIF cache, and get the counts of anything unusual.
    rows, unusual = parse_all()
    # Add the sponsor rows.
    rows += sponsor_facts()
    # Save every row to data/interim/facts.jsonl.
    write_facts(rows)
    # Say where the file is and how big it is.
    print(f"Wrote {len(rows)} facts to {FACTS_PATH.relative_to(FACTS_PATH.parents[2])}")
    # One line per kind of fact, most common first.
    for predicate, n in Counter(r["predicate"] for r in rows).most_common():
        # e.g. "  legalName  489".
        print(f"  {predicate:<26}{n}")
    # Report any unusual cases, rather than hiding them.
    for case, n in unusual.items():
        # e.g. "Unusual: linked reply said not found: 0".
        print(f"Unusual: {case}: {n}")


# Run main() when this file is run directly, not when it is imported.
if __name__ == "__main__":
    # Start.
    main()
