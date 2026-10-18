"""SUMMARY: Pipeline stage 1 (fetch) for GLEIF, for all three sponsors at once.
Decision D-039: download GLEIF's Level 2 data for every entity, not a sample.

What it does:
- Searches GLEIF with every search word in config/sponsors.toml (from the
  cache if already done).
- For each entity found, follows the links GLEIF itself gives for its direct
  parent, ultimate parent and fund manager. Each link says which reply to ask
  for: an actual parent ("relationship-record") or a stated reason for no
  parent ("reporting-exception"). So we never guess, and never ask for
  something GLEIF says isn't there.
- Fetches the main record of every parent or fund manager that our search did
  not find, so that every entity in the graph has at least a name.
- Every reply is cached by seisa_kg.sources.gleif and never fetched twice, so
  stopping and re-running simply carries on where it left off.

Run it with:  make fetch-gleif   (about 16 minutes the first time, seconds after)
"""

# Python's built-in reader for TOML settings files.
import tomllib
# A tidy way of working with file and folder paths.
from pathlib import Path

# The library we use to send web requests.
import httpx

# Our own cached GLEIF fetcher: search, record and record_part.
from seisa_kg.sources import gleif

# The project's top folder: this file's folder, then up three levels (sources → seisa_kg → src → project).
PROJECT_ROOT = Path(__file__).resolve().parents[3]
# The sponsor settings file (pipeline stage 0).
CONFIG_PATH = PROJECT_ROOT / "config" / "sponsors.toml"
# The three kinds of Level 2 link we follow, as GLEIF names them in each record.
LINK_KINDS = ("direct-parent", "ultimate-parent", "fund-manager")
# The two link types that point to a reply we want to keep (the third, "lei-record", is handled separately).
WANTED_LINKS = ("relationship-record", "reporting-exception")


# Read the sponsor settings and return {sponsor key: list of search words}.
def load_search_terms() -> dict[str, list[str]]:
    # Open the settings file in binary mode, as tomllib requires.
    with CONFIG_PATH.open("rb") as f:
        # Turn the TOML text into Python data.
        config = tomllib.load(f)
    # Keep just each sponsor's search words, under its short key (e.g. "apax").
    return {key: s["search_terms"] for key, s in config["sponsors"].items()}


# Search GLEIF for every sponsor's words and return {LEI: record}, with no duplicates.
def all_search_records(client: httpx.Client) -> dict[str, dict]:
    # A lookup of LEI -> record, so an entity found by two words or two sponsors is kept once.
    found = {}
    # Go through each sponsor's list of search words.
    for terms in load_search_terms().values():
        # Go through each word.
        for term in terms:
            # Search GLEIF (or the cache) for that word.
            for rec in gleif.search(client, term):
                # Keep the record under its LEI.
                found[rec["id"]] = rec
    # Hand back the unique records.
    return found


# List the record parts GLEIF's own links say to fetch for one entity, e.g. "direct-parent-reporting-exception".
def linked_parts(rec: dict) -> list[str]:
    # The parts found so far.
    parts = []
    # Look at the direct-parent, ultimate-parent and fund-manager links in turn.
    for kind in LINK_KINDS:
        # The links GLEIF gives for this kind (an empty set if it gives none).
        links = rec["relationships"].get(kind, {}).get("links", {})
        # Look at each link type we want.
        for link_type in WANTED_LINKS:
            # Skip it if GLEIF doesn't offer this link for this entity.
            if link_type not in links:
                # Move on to the next link type.
                continue
            # The part's name is the last piece of the web address, e.g. ".../direct-parent-relationship".
            parts.append(links[link_type].rstrip("/").rsplit("/", 1)[-1])
    # Hand back the list of parts to fetch.
    return parts


# The LEI at the far end of a relationship record (the parent or the manager), or None.
def other_end(relationship: dict | None) -> str | None:
    # A reporting exception, or nothing at all, has no other end.
    if not relationship or relationship.get("type") != "relationship-records":
        # Signal "no other entity" to whoever asked.
        return None
    # The relationship's end node is the parent or the fund manager.
    return relationship["attributes"]["relationship"]["endNode"]["id"]


# Fetch every Level 2 reply for every sponsor entity, plus the records of outside parents and managers.
def fetch_all() -> None:
    # One web connection, reused for every request; 30 seconds before giving up on a reply.
    with httpx.Client(timeout=30) as client:
        # Every entity found by searching for our sponsors.
        records = all_search_records(client)
        # The full to-do list of (LEI, part) pairs, worked out before any download starts.
        todo = [(lei, part) for lei, rec in sorted(records.items()) for part in linked_parts(rec)]
        # Say how much there is to do.
        print(f"{len(records)} entities, {len(todo)} Level 2 replies to fetch or read from the cache")
        # LEIs at the far end of a relationship that our search didn't find.
        outsiders = set()
        # Work through the to-do list, counting as we go.
        for i, (lei, part) in enumerate(todo, start=1):
            # Fetch this part (from the cache if we already have it).
            data = gleif.record_part(client, lei, part)
            # Find the parent or manager it points to, if any.
            target = other_end(data)
            # If that entity wasn't in our search results, note it for a name lookup.
            if target and target not in records:
                # Add it to the set of outsiders.
                outsiders.add(target)
            # Print progress every 50 replies, so a long run shows it's alive.
            if i % 50 == 0 or i == len(todo):
                # One short progress line.
                print(f"  {i}/{len(todo)}")
        # Say how many outside entities need their main record.
        print(f"{len(outsiders)} outside parents or managers to look up")
        # Fetch each outsider's main record, in a fixed order.
        for lei in sorted(outsiders):
            # Fetch it (from the cache if we already have it).
            gleif.record(client, lei)
    # Finished.
    print("Done. Every reply is cached in data/raw/gleif/.")


# Run fetch_all() when this file is run directly, not when it is imported.
if __name__ == "__main__":
    # Start the download.
    fetch_all()
