"""SUMMARY: The "sponsor check". It helps choose which 3 UK private equity firms
(sponsors) to build the project around.

For each candidate sponsor, it searches GLEIF (the public register of Legal
Entity Identifiers, LEIs) for legal entities whose names contain the sponsor's
name. It then counts what GLEIF tells us about them:
  - how many entities there are, and how many are still active
  - what kind they are (FUND, or GENERAL for ordinary companies and partnerships)
  - which countries they are registered in
  - how many are UK companies with a Companies House number, so they can be
    matched to Companies House by number rather than by name
  - how many report a parent company, how many give a reason for having none
    (a "reporting exception"), and how many have a fund-manager link.

Every GLEIF response is saved in data/raw/gleif/sponsor_check/, so re-running
the script never downloads the same page twice (a brief rule). The results
table is printed and also saved to docs/sponsor-check.md.

Caveat: searching by name finds look-alikes too (e.g. an unrelated company with
the same word in its name). The counts are a first look, not a clean list.

Run it with:  uv run python scripts/sponsor_check.py
"""

# Reads and writes JSON, the text format GLEIF's API replies in.
import json
# Lets us pause between web requests, to stay inside GLEIF's rate limit.
import time
# Counts how often each value appears (e.g. how many entities per country).
from collections import Counter
# The current date and time, used to stamp when the check was run.
from datetime import datetime, timezone
# A tidy way of working with file and folder paths.
from pathlib import Path

# The library we use to send web requests.
import httpx

# The project's top folder: this script's folder ("scripts"), then one level up.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Where every raw GLEIF reply is cached.
CACHE_DIR = PROJECT_ROOT / "data" / "raw" / "gleif" / "sponsor_check"
# Where the summary table is saved for reading later.
REPORT_PATH = PROJECT_ROOT / "docs" / "sponsor-check.md"
# GLEIF's address for searching LEI records.
GLEIF_SEARCH_URL = "https://api.gleif.org/api/v1/lei-records"
# The most records GLEIF will return in one page.
PAGE_SIZE = 200
# Seconds to wait between live requests. GLEIF allows 60 per minute, so 1.1s keeps us under.
PAUSE_SECONDS = 1.1
# GLEIF's code for the UK Companies House register.
COMPANIES_HOUSE_RA = "RA000585"

# The candidate sponsors, each with the search words used to find its entities.
# Hg needs several specific words, because searching for just "Hg" would match far too much.
CANDIDATES = {
    # Permira: large European buyout firm, headquartered in London.
    "Permira": ["Permira"],
    # Cinven: European buyout firm, headquartered in London.
    "Cinven": ["Cinven"],
    # Hg: software and services investor, headquartered in London.
    "Hg": ["HgCapital", "Hg Pooled", "Hg Genesis", "Hg Saturn", "Hg Mercury"],
    # Bridgepoint: London-listed mid-market private equity firm.
    "Bridgepoint": ["Bridgepoint"],
    # Apax: global buyout firm, headquartered in London.
    "Apax": ["Apax"],
    # Inflexion: UK mid-market private equity firm.
    "Inflexion": ["Inflexion"],
}


# Fetch one page of search results, from the cache if we have it, otherwise from GLEIF.
def fetch_page(client: httpx.Client, term: str, page: int) -> dict:
    # Build a safe file name for this search word and page, e.g. "hg_pooled_p1.json".
    cache_file = CACHE_DIR / f"{term.lower().replace(' ', '_')}_p{page}.json"
    # If we already saved this exact page earlier, reuse it instead of downloading.
    if cache_file.exists():
        # Read the saved file and turn its text back into data.
        return json.loads(cache_file.read_text(encoding="utf-8"))
    # Wait a moment first, so we never send requests faster than GLEIF allows.
    time.sleep(PAUSE_SECONDS)
    # Ask GLEIF for records whose names or details contain the search word.
    response = client.get(GLEIF_SEARCH_URL, params={
        # The word to search for.
        "filter[fulltext]": term,
        # How many records per page.
        "page[size]": PAGE_SIZE,
        # Which page of results we want.
        "page[number]": page,
    })
    # Stop with a clear error if GLEIF replied with a failure (e.g. 429 "too many requests").
    response.raise_for_status()
    # Turn GLEIF's reply into data we can work with.
    data = response.json()
    # Note when we fetched it, so the saved file records its own retrieval date (provenance).
    data["_retrieved_at"] = datetime.now(timezone.utc).isoformat()
    # Make sure the cache folder exists.
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    # Save the reply so we never need to download this page again.
    cache_file.write_text(json.dumps(data, indent=1), encoding="utf-8")
    # Hand the data back.
    return data


# Collect every LEI record for one sponsor, across all its search words and pages.
def records_for_sponsor(client: httpx.Client, terms: list[str]) -> dict[str, dict]:
    # A lookup of LEI -> record. Keyed by LEI so an entity found twice is only counted once.
    records = {}
    # Go through each search word for this sponsor.
    for term in terms:
        # Start at the first page of results.
        page = 1
        # Keep fetching pages until there are none left.
        while True:
            # Get this page of results.
            data = fetch_page(client, term, page)
            # Add each record on the page to our lookup, using its LEI as the key.
            for record in data["data"]:
                # Store the record under its LEI.
                records[record["id"]] = record
            # Stop once we have reached the last page.
            if page >= data["meta"]["pagination"]["lastPage"]:
                # Leave the page loop and move on to the next search word.
                break
            # Otherwise move on to the next page.
            page += 1
    # Hand back all the unique records found.
    return records


# Work out what one record says about its direct parent company.
def parent_status(record: dict) -> str:
    # The links GLEIF gives for this entity's direct parent.
    links = record["relationships"].get("direct-parent", {}).get("links", {})
    # A "relationship-record" link means GLEIF holds an actual parent relationship.
    if "relationship-record" in links:
        # So the entity reports a parent.
        return "has parent"
    # A "reporting-exception" link means the entity gave a reason for naming no parent.
    if "reporting-exception" in links:
        # So the gap is explained, which the brief wants us to record openly.
        return "exception"
    # Neither: GLEIF holds no information about a parent at all.
    return "unknown"


# Turn one sponsor's records into a row of summary numbers.
def summarise(name: str, records: dict[str, dict]) -> dict:
    # Pull out just the "entity" part of each record (names, country, category and so on).
    entities = [r["attributes"]["entity"] for r in records.values()]
    # Count each entity's parent situation.
    parents = Counter(parent_status(r) for r in records.values())
    # Count entities by kind (FUND, GENERAL, ...).
    categories = Counter(e["category"] for e in entities)
    # Count entities by country of registration.
    countries = Counter(e["jurisdiction"] for e in entities)
    # Return the row of numbers for the table.
    return {
        # The sponsor's name.
        "sponsor": name,
        # How many distinct entities were found.
        "entities": len(entities),
        # How many of those are still active (not closed or merged away).
        "active": sum(e["status"] == "ACTIVE" for e in entities),
        # How many are funds.
        "funds": categories.get("FUND", 0),
        # How many are UK entities registered with Companies House.
        "uk_companies_house": sum(
            # Count it if it is registered at Companies House...
            e["registeredAt"]["id"] == COMPANIES_HOUSE_RA
            # ...looking at each entity in turn.
            for e in entities
        ),
        # How many report an actual parent company.
        "has_parent": parents["has parent"],
        # How many give a reason for naming no parent.
        "exception": parents["exception"],
        # How many have a link to a fund manager.
        "fund_manager_link": sum(
            # Count it if GLEIF lists a fund-manager link for the entity...
            "fund-manager" in r["relationships"]
            # ...looking at each record in turn.
            for r in records.values()
        ),
        # The three most common countries, e.g. "GB 40, LU 30, KY 12".
        "top_countries": ", ".join(f"{c} {n}" for c, n in countries.most_common(3)),
    }


# The main job: check every candidate, then print and save the results table.
def main() -> None:
    # Open one web connection to reuse for every request, timing out after 30 seconds.
    with httpx.Client(timeout=30) as client:
        # Build one summary row per candidate sponsor.
        rows = [summarise(name, records_for_sponsor(client, terms))
                # Look at each candidate sponsor and its search words in turn.
                for name, terms in CANDIDATES.items()]
    # The column titles for the table, in display order.
    headers = ["sponsor", "entities", "active", "funds", "uk_companies_house",
               # (the list carries on onto this line)
               "has_parent", "exception", "fund_manager_link", "top_countries"]
    # Start the table: a title row, then the line markdown needs under it.
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    # Add one table line per sponsor.
    for row in rows:
        # Put that sponsor's values in the same order as the titles.
        lines.append("| " + " | ".join(str(row[h]) for h in headers) + " |")
    # Join the table lines into one block of text.
    table = "\n".join(lines)
    # Today's date, to stamp the report.
    today = datetime.now(timezone.utc).date().isoformat()
    # Make sure the docs folder exists.
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Save the report: a heading, a note on the method, then the table.
    REPORT_PATH.write_text(
        # The heading, with the date of the check.
        f"# Sponsor check ({today})\n\n"
        # How the numbers were produced, and their main limitation.
        "GLEIF full-text name search per sponsor (see scripts/sponsor_check.py). "
        # (the note carries on here)
        "Name search also finds look-alikes, so treat the counts as a first look.\n\n"
        # The table itself.
        + table + "\n",
        # Use UTF-8 so any special characters are saved correctly.
        encoding="utf-8",
    )
    # Show the table on screen too.
    print(table)


# Only run main() when this file is run directly, not when it's imported.
if __name__ == "__main__":
    # Start the main job.
    main()
