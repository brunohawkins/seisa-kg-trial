"""SUMMARY: Downloads data from GLEIF, the public register of Legal Entity
Identifiers (LEIs). This is pipeline stage 1 (fetch) for GLEIF.

What it does:
- Searches GLEIF for entities by name (e.g. every entity containing "Apax").
- Fetches one part of an entity's record, e.g. its fund-manager relationship
  or its reason for reporting no parent.
- Saves every reply in data/raw/gleif/ along with the web address it came from
  and the date and time it was fetched. That is the provenance of every GLEIF
  fact we will ever use. A reply already saved is never downloaded again
  (a brief rule).
- Waits between requests so we stay inside GLEIF's limit of 60 per minute.
- "Not found" replies (e.g. an entity with no fund manager) are saved too, so
  we don't keep asking GLEIF the same question.
"""

# Reads and writes JSON, the text format GLEIF replies in.
import json
# Lets us pause between requests and measure time.
import time
# The current date and time, used to stamp when each reply was fetched.
from datetime import datetime, timezone
# A tidy way of working with file and folder paths.
from pathlib import Path

# The library we use to send web requests.
import httpx

# The start of every GLEIF API web address.
BASE_URL = "https://api.gleif.org/api/v1"
# The project's top folder: this file's folder, then up three levels (sources → seisa_kg → src → project).
PROJECT_ROOT = Path(__file__).resolve().parents[3]
# The folder where every GLEIF reply is cached.
CACHE_DIR = PROJECT_ROOT / "data" / "raw" / "gleif"
# The most records GLEIF returns per page of search results.
PAGE_SIZE = 200
# The smallest gap allowed between two live requests, in seconds (60 a minute means 1 per second, plus a margin).
MIN_GAP_SECONDS = 1.1

# When our last live request was sent. Starts at zero, i.e. "long ago".
_last_request_at = 0.0


# Fetch one GLEIF address, using the cache when possible. Returns the saved envelope:
# {"url", "retrieved_at", "status", "body"}, where body is None if GLEIF said "not found".
def _cached_get(client: httpx.Client, cache_file: Path, path: str, params: dict | None = None) -> dict:
    # Let this function update the shared "last request" time.
    global _last_request_at
    # If we already have this reply on disk, read it and return it straight away.
    if cache_file.exists():
        # Turn the saved text back into data.
        return json.loads(cache_file.read_text(encoding="utf-8"))
    # Work out how long ago the last live request was sent.
    wait = MIN_GAP_SECONDS - (time.monotonic() - _last_request_at)
    # If it was too recent, pause for the remaining time.
    if wait > 0:
        # Sleep for the remaining part of the gap.
        time.sleep(wait)
    # Send the request to GLEIF.
    response = client.get(f"{BASE_URL}/{path}", params=params)
    # Remember when this request was sent, for the next gap check.
    _last_request_at = time.monotonic()
    # A 404 ("not found") is a real answer here (e.g. "this fund has no manager"), so it is not an error.
    if response.status_code != 404:
        # Any other failure (e.g. 429 "too many requests") stops the program with a clear error.
        response.raise_for_status()
    # Wrap the reply with its provenance: where it came from and when.
    envelope = {
        # The full web address that was asked, including any search settings.
        "url": str(response.request.url),
        # The date and time it was fetched, in UTC (world standard time).
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        # The reply's status code: 200 means found, 404 means not found.
        "status": response.status_code,
        # GLEIF's actual reply, or None when there was nothing to find.
        "body": response.json() if response.status_code == 200 else None,
    }
    # Make sure the folder for this cache file exists.
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    # Save the envelope so this address is never fetched again.
    cache_file.write_text(json.dumps(envelope, indent=1), encoding="utf-8")
    # Hand the envelope back.
    return envelope


# Search GLEIF for every entity matching a word, across all pages. Returns the list of LEI records.
def search(client: httpx.Client, term: str) -> list[dict]:
    # A safe file-name version of the search word, e.g. "Hg Pooled" -> "hg_pooled".
    slug = term.lower().replace(" ", "_")
    # The records found so far.
    records = []
    # Start with the first page of results.
    page = 1
    # Keep going until the last page has been read.
    while True:
        # The cache file for this word and page, e.g. data/raw/gleif/search/apax_p1.json.
        cache_file = CACHE_DIR / "search" / f"{slug}_p{page}.json"
        # Fetch the page (from the cache if we already have it).
        envelope = _cached_get(client, cache_file, "lei-records", {
            # Search all of GLEIF's text fields for the word.
            "filter[fulltext]": term,
            # Ask for as many records per page as GLEIF allows.
            "page[size]": PAGE_SIZE,
            # Which page we want.
            "page[number]": page,
        })
        # Add this page's records to our list.
        records.extend(envelope["body"]["data"])
        # Stop if this was the last page.
        if page >= envelope["body"]["meta"]["pagination"]["lastPage"]:
            # Leave the loop.
            break
        # Otherwise move on to the next page.
        page += 1
    # Hand back every record found.
    return records


# Fetch an entity's main LEI record (name, address, category...) by its LEI.
# Returns GLEIF's "data" section, or None if GLEIF has no such LEI.
def record(client: httpx.Client, lei: str) -> dict | None:
    # The cache file, e.g. data/raw/gleif/lei-records/<LEI>/record.json.
    cache_file = CACHE_DIR / "lei-records" / lei / "record.json"
    # Fetch it (from the cache if we already have it).
    envelope = _cached_get(client, cache_file, f"lei-records/{lei}")
    # Return the record, or None if GLEIF said "not found".
    return envelope["body"]["data"] if envelope["body"] else None


# Fetch one part of an entity's record, e.g. "fund-manager-relationship".
# Returns GLEIF's "data" section, or None if GLEIF has nothing for that part.
def record_part(client: httpx.Client, lei: str, part: str) -> dict | None:
    # The cache file, e.g. data/raw/gleif/lei-records/<LEI>/fund-manager.json.
    cache_file = CACHE_DIR / "lei-records" / lei / f"{part}.json"
    # Fetch it (from the cache if we already have it).
    envelope = _cached_get(client, cache_file, f"lei-records/{lei}/{part}")
    # If GLEIF said "not found", there is no data to return.
    if envelope["body"] is None:
        # Signal "nothing here" to whoever asked.
        return None
    # The useful part of the reply.
    data = envelope["body"]["data"]
    # Some parts come back as a list (possibly empty); others as a single item.
    if isinstance(data, list):
        # Return the first item, or None if the list is empty.
        return data[0] if data else None
    # It was a single item already, so return it as it is.
    return data
