"""SUMMARY: The warm-up check before designing the RDF schema. For our three
sponsors (config/sponsors.toml) it answers two questions using GLEIF:

1. Why do entities report no parent? It looks up the stated reason (the
   "reporting exception") for a sample of up to 20 entities per sponsor, plus
   the actual parent for the few entities that do report one.
2. Who manages the funds? For every entity with a fund-manager link, it fetches
   the relationship record (which manager, since when, how well checked), then
   looks up each distinct manager's name once.

Every reply is cached by seisa_kg.sources.gleif, so re-running costs nothing.
The findings are printed and saved to docs/gleif-warmup.md.

Run it with:  uv run python scripts/gleif_warmup.py
"""

# Counts how often each value appears.
from collections import Counter, defaultdict
# A tidy way of working with file and folder paths.
from pathlib import Path
# Python's built-in reader for TOML settings files.
import tomllib

# The library we use to send web requests.
import httpx

# Our own cached GLEIF fetcher (pipeline stage 1).
from seisa_kg.sources import gleif

# The project's top folder: this script's folder ("scripts"), then one level up.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
# The sponsor settings file (pipeline stage 0).
CONFIG_PATH = PROJECT_ROOT / "config" / "sponsors.toml"
# Where the findings report is saved.
REPORT_PATH = PROJECT_ROOT / "docs" / "gleif-warmup.md"
# The most entities per sponsor whose "no parent" reason we look up.
EXCEPTION_SAMPLE_SIZE = 20


# Find every entity for one sponsor, across all its search words, without duplicates.
def sponsor_records(client: httpx.Client, terms: list[str]) -> dict[str, dict]:
    # A lookup of LEI -> record, so an entity found by two search words is only kept once.
    found = {}
    # Go through each search word.
    for term in terms:
        # Search GLEIF (or the cache) for that word.
        for rec in gleif.search(client, term):
            # Keep the record under its LEI.
            found[rec["id"]] = rec
    # Hand back the unique records.
    return found


# Pick an evenly spread sample of up to `size` items from a list, the same way every run.
def spread_sample(items: list[str], size: int) -> list[str]:
    # Sort first, so the sample doesn't depend on the order GLEIF happened to reply in.
    items = sorted(items)
    # If there are few enough, take them all.
    if len(items) <= size:
        # Nothing to sample; return the full list.
        return items
    # The distance between picks, e.g. every 9th item.
    step = len(items) / size
    # Take one item at each step along the list.
    return [items[int(i * step)] for i in range(size)]


# Look up why each sampled entity reports no direct parent. Returns a count per reason.
def exception_reasons(client: httpx.Client, records: dict[str, dict]) -> Counter:
    # The LEIs whose direct parent is a "reporting exception" (a stated reason for no parent).
    leis = [lei for lei, rec in records.items()
            # Keep it if GLEIF offers a reporting-exception link for its direct parent.
            if "reporting-exception" in rec["relationships"].get("direct-parent", {}).get("links", {})]
    # Count how many times each reason appears.
    reasons = Counter()
    # Look up the reason for each entity in the sample.
    for lei in spread_sample(leis, EXCEPTION_SAMPLE_SIZE):
        # Fetch the reporting-exception part of the record.
        exc = gleif.record_part(client, lei, "direct-parent-reporting-exception")
        # Count its reason (e.g. NON_CONSOLIDATING), or "none returned" if GLEIF gave nothing.
        reasons[exc["attributes"]["reason"] if exc else "none returned"] += 1
    # Hand back the counts.
    return reasons


# For the few entities that do report a parent, fetch who the parent is. Returns (child, parent) name pairs.
def actual_parents(client: httpx.Client, records: dict[str, dict]) -> list[tuple[str, str]]:
    # The (child name, parent name) pairs found.
    pairs = []
    # Go through every record for this sponsor.
    for lei, rec in records.items():
        # Skip it unless GLEIF holds an actual direct-parent relationship.
        if "relationship-record" not in rec["relationships"].get("direct-parent", {}).get("links", {}):
            # Move on to the next record.
            continue
        # Fetch the parent's own LEI record.
        parent = gleif.record_part(client, lei, "direct-parent")
        # The parent's legal name, or a note if GLEIF returned nothing.
        parent_name = parent["attributes"]["entity"]["legalName"]["name"] if parent else "(not returned)"
        # Store the child's name and the parent's name together.
        pairs.append((rec["attributes"]["entity"]["legalName"]["name"], parent_name))
    # Hand back the pairs.
    return pairs


# Fetch every fund-manager relationship for one sponsor's entities. Returns the relationship records.
def fund_manager_links(client: httpx.Client, records: dict[str, dict]) -> list[dict]:
    # The relationships found.
    links = []
    # Go through every record for this sponsor.
    for lei, rec in records.items():
        # Skip it if GLEIF lists no fund-manager link at all.
        if "fund-manager" not in rec["relationships"]:
            # Move on to the next record.
            continue
        # Fetch the fund-manager relationship record.
        rel = gleif.record_part(client, lei, "fund-manager-relationship")
        # Skip it if GLEIF had nothing behind the link.
        if rel is None:
            # Move on to the next record.
            continue
        # The relationship details (who, since when, status) live in "attributes".
        attrs = rel["attributes"]
        # The relationship's time periods (e.g. when it started).
        periods = attrs["relationship"].get("periods") or []
        # Keep just the fields we want to report on.
        links.append({
            # The fund's own name.
            "fund": rec["attributes"]["entity"]["legalName"]["name"],
            # The manager's LEI (the far end of the link).
            "manager_lei": attrs["relationship"]["endNode"]["id"],
            # Whether the relationship is current (ACTIVE) or ended.
            "status": attrs["relationship"]["status"],
            # The date the relationship started, if GLEIF gives one (first 10 characters = YYYY-MM-DD).
            "start": next((p["startDate"][:10] for p in periods if p.get("startDate")), None),
            # How well GLEIF checked this relationship (e.g. FULLY_CORROBORATED).
            "corroboration": attrs["registration"]["corroborationLevel"],
        })
    # Hand back the relationships.
    return links


# The main job: run both checks for every sponsor, then print and save a report.
def main() -> None:
    # Read the sponsor settings file.
    config = tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    # The report's lines, starting with its heading and a short method note.
    lines = ["# GLEIF warm-up findings", "",
             # (the method note carries on here)
             "Produced by `scripts/gleif_warmup.py` from cached GLEIF replies in `data/raw/gleif/`.", ""]
    # Open one web connection to reuse for every request, timing out after 30 seconds.
    with httpx.Client(timeout=30) as client:
        # Go through each sponsor in the settings file.
        for sponsor in config["sponsors"].values():
            # Find all of this sponsor's entities.
            records = sponsor_records(client, sponsor["search_terms"])
            # Question 1: why entities report no parent (sample).
            reasons = exception_reasons(client, records)
            # Question 1, part 2: the actual parents, where any are reported.
            parents = actual_parents(client, records)
            # Question 2: the fund-manager relationships.
            links = fund_manager_links(client, records)
            # Count how many funds each manager runs.
            per_manager = Counter(link["manager_lei"] for link in links)
            # Look up each distinct manager's name once.
            manager_names = {}
            # Go through each distinct manager LEI.
            for manager_lei in per_manager:
                # Fetch the manager's own record.
                rec = gleif.record(client, manager_lei)
                # Store its name and country, or a note if GLEIF has no record.
                manager_names[manager_lei] = (
                    # The name and country, e.g. "Apax Management Luxembourg S.à r.l. (LU)".
                    f"{rec['attributes']['entity']['legalName']['name']} ({rec['attributes']['entity']['jurisdiction']})"
                    # Used if the record is missing.
                    if rec else "(no record)")
            # The relationships' start dates that GLEIF provided.
            starts = sorted(link["start"] for link in links if link["start"])
            # Add this sponsor's section to the report.
            lines += [f"## {sponsor['name']} ({len(records)} entities)", "",
                      # The "no parent" reasons and how many entities were sampled.
                      f"- **No-parent reasons** (sample of {sum(reasons.values())}): "
                      # Each reason with its count, e.g. "NON_CONSOLIDATING 18".
                      + ", ".join(f"{r} {n}" for r, n in reasons.most_common()),
                      # The actual parent relationships found, if any.
                      f"- **Actual parents reported:** {len(parents)}"
                      # List them as "child → parent" pairs.
                      + "".join(f"\n  - {child} → {parent}" for child, parent in parents),
                      # How many fund-manager relationships there are, and their statuses.
                      f"- **Fund-manager relationships:** {len(links)} "
                      # e.g. "(ACTIVE 60, INACTIVE 5)".
                      f"({', '.join(f'{s} {n}' for s, n in Counter(l['status'] for l in links).items())})",
                      # The range of start dates, if GLEIF gave any.
                      f"  - Start dates: {starts[0]} to {starts[-1]} ({len(starts)} of {len(links)} have one)"
                      # Used when there are no dates.
                      if starts else "  - Start dates: none given",
                      # How well the relationships were checked.
                      f"  - Corroboration: {dict(Counter(l['corroboration'] for l in links))}",
                      # The managers, with how many funds each one manages.
                      "  - Managers:" + "".join(f"\n    - {manager_names[m]}: {n} funds" for m, n in per_manager.most_common()),
                      # A blank line before the next sponsor.
                      ""]
    # Join the report's lines into one block of text.
    report = "\n".join(lines)
    # Save the report.
    REPORT_PATH.write_text(report + "\n", encoding="utf-8")
    # Show it on screen too.
    print(report)


# Only run main() when this file is run directly, not when it's imported.
if __name__ == "__main__":
    # Start the main job.
    main()
