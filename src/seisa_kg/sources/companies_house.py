"""SUMMARY: Downloads data from Companies House, the UK register of companies.
This is pipeline stage 1 (fetch) for Companies House (D-072).

What it does:
- Works out our In-scope companies that are registered at Companies House
  (GLEIF's registeredAt = RA000585), by running the scope step on the GLEIF
  data, the same way `make facts` does.
- For each one, fetches four parts: the profile, the officers (current and
  past, every page; D-077), the PSC list (who controls it, every page) and the
  PSC statements (e.g. "no registrable controller", F31).
- Climbs each control chain: when a controller is a UK company, that company
  is fetched too, up to 4 steps up, stopping at loops (F29). Companies reached
  this way are "related": fetched, but given no scope verdict (D-078).
- Saves every reply in data/raw/companies_house/<number>/ with the web address
  and the date and time it was fetched. A saved reply is never downloaded
  again (brief rule). "Not found" replies are saved too.
- Stays inside the limit of 600 requests per 5 minutes.
The API key is read from .env and never printed.

Run it with:  make fetch-ch
"""

# Reads and writes JSON, the text format Companies House replies in.
import json
# Reads the API key from the environment.
import os
# Lets us pause between requests and measure time.
import time
# The current date and time, used to stamp when each reply was fetched.
from datetime import datetime, timezone
# A tidy way of working with file and folder paths.
from pathlib import Path

# The library we use to send web requests.
import httpx
# Loads the secret values in .env into the environment.
from dotenv import load_dotenv

# The tidying rule for hand-typed company numbers, and the UK test (D-076).
from seisa_kg.facts.ch_tidy import is_uk_registered, tidy_company_number
# The GLEIF parser, the sponsor rows and the scope step, to find our In-scope companies.
from seisa_kg.facts.gleif_parse import parse_all
# The sponsor rows (needed by the scope step).
from seisa_kg.facts.sponsors import sponsor_facts
# The scope step: our In / Review / Out judgements (D-028).
from seisa_kg.facts.scope import scope_facts

# The start of every Companies House API web address.
BASE_URL = "https://api.company-information.service.gov.uk"
# The project's top folder: this file's folder, then up three levels (sources → seisa_kg → src → project).
PROJECT_ROOT = Path(__file__).resolve().parents[3]
# The folder where every Companies House reply is cached.
CACHE_DIR = PROJECT_ROOT / "data" / "raw" / "companies_house"
# The smallest gap between two live requests: 600 per 5 minutes is 2 a second, so 0.6 s leaves a margin.
MIN_GAP_SECONDS = 0.6
# How many items to ask for per page (the API's maximum for these lists).
PAGE_SIZE = 100
# How many steps up a control chain to climb at most.
MAX_CLIMB = 4
# The code GLEIF uses for the Companies House register.
CH_REGISTER = "RA000585"

# When our last live request was sent. Starts at zero, i.e. "long ago".
_last_request_at = 0.0
# How many live requests this run has sent (the rest came from the cache).
live_requests = 0


# Fetch one Companies House address, using the cache when possible; returns the saved envelope.
def cached_get(client: httpx.Client, cache_file: Path, path: str, params: dict | None = None) -> dict:
    # Let this function update the shared counters.
    global _last_request_at, live_requests
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
    # Send the request.
    response = client.get(f"{BASE_URL}{path}", params=params)
    # Remember when this request was sent, for the next gap check.
    _last_request_at = time.monotonic()
    # Count it.
    live_requests += 1
    # A 404 ("not found", e.g. no PSC list for an English LP) is a real answer, so it is kept.
    if response.status_code != 404:
        # Any other failure (e.g. 429 "too many requests") stops the program with a clear error.
        response.raise_for_status()
    # Wrap the reply with its provenance: where it came from and when.
    envelope = {
        # The full web address that was asked, including any page settings.
        "url": str(response.request.url),
        # The date and time it was fetched, in UTC.
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        # 200 means found, 404 means not found.
        "status": response.status_code,
        # The reply itself, or None when there was nothing to find.
        "body": response.json() if response.status_code == 200 else None,
    }
    # Make sure the company's folder exists.
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    # Save the envelope so this address is never fetched again.
    cache_file.write_text(json.dumps(envelope, indent=1, ensure_ascii=False), encoding="utf-8")
    # Hand back the envelope.
    return envelope


# Fetch every page of a list (officers or PSCs); returns all the items, across pages.
def all_pages(client: httpx.Client, number: str, part: str, path: str) -> list[dict]:
    # The items found so far.
    items = []
    # Start with the first page.
    page = 1
    # Keep going until every item has been read.
    while True:
        # Fetch this page (from the cache if we have it), e.g. officers_p1.json.
        env = cached_get(client, CACHE_DIR / number / f"{part}_p{page}.json", path,
                         # Ask for a full page, starting after the items already read.
                         {"items_per_page": PAGE_SIZE, "start_index": (page - 1) * PAGE_SIZE})
        # "Not found" means there is no list at all: stop.
        if env["body"] is None:
            # Leave the loop.
            break
        # This page's items.
        batch = env["body"].get("items", [])
        # Add them to the list.
        items += batch
        # Stop when this page was the last one (fewer items than asked for, or we've reached the total).
        if len(batch) < PAGE_SIZE or len(items) >= env["body"].get("total_results", 0):
            # Leave the loop.
            break
        # Otherwise move on to the next page.
        page += 1
    # Hand back every item.
    return items


# Fetch the four parts of one company; returns its PSC items (used for climbing).
def fetch_company(client: httpx.Client, number: str) -> list[dict]:
    # The profile: name, type, status, dates, registered office, previous names.
    cached_get(client, CACHE_DIR / number / "profile.json", f"/company/{number}")
    # The officers, current and past, every page (D-077).
    all_pages(client, number, "officers", f"/company/{number}/officers")
    # The PSC statements, e.g. "no registrable controller" (F31).
    cached_get(client, CACHE_DIR / number / "psc_statements.json", f"/company/{number}/persons-with-significant-control-statements")
    # The PSC list (who controls it), every page; handed back for climbing.
    return all_pages(client, number, "psc", f"/company/{number}/persons-with-significant-control")


# The Companies House numbers of our In-scope companies, worked out from the GLEIF data.
def in_scope_numbers() -> dict[str, str]:
    # Parse the GLEIF cache into rows.
    rows, _ = parse_all()
    # Add the sponsor rows, then the scope decisions (the same steps as `make facts`).
    rows += sponsor_facts()
    # The scope decisions.
    rows += scope_facts(rows)
    # The LEIs judged In for at least one sponsor.
    in_leis = {"lei:" + r["subject"].split("/")[2] for r in rows if r["predicate"] == "verdict" and r["object"]["iri"] == "ex:In"}
    # Each LEI's register and registration number.
    reg_at = {r["subject"]: r["object"]["value"] for r in rows if r["predicate"] == "registeredAt"}
    # The registration number, as GLEIF gives it.
    reg_as = {r["subject"]: r["object"]["value"] for r in rows if r["predicate"] == "registeredAs"}
    # Number -> LEI, for In-scope companies registered at Companies House (D-025's first condition).
    return {reg_as[lei]: lei for lei in sorted(in_leis) if reg_at.get(lei) == CH_REGISTER and lei in reg_as}


# Fetch every In-scope company and climb the control chains.
def fetch_all() -> None:
    # Load .env so the key is available (its value is never printed).
    load_dotenv(PROJECT_ROOT / ".env")
    # The API key; Companies House uses it as the user name, with an empty password.
    key = os.environ["COMPANIES_HOUSE_API_KEY"]
    # Our In-scope companies at Companies House.
    start = in_scope_numbers()
    # Say how many.
    print(f"{len(start)} In-scope companies registered at Companies House")
    # Companies already fetched (also stops loops, F29).
    done = set()
    # Companies reached only by climbing (D-078).
    related = set()
    # One web connection, reused, logging in with the key; 30 seconds before giving up.
    with httpx.Client(auth=(key, ""), timeout=30) as client:
        # The companies to fetch at this step: (number, how many steps up we are).
        frontier = [(n, 0) for n in sorted(start)]
        # Keep going while there are companies left.
        while frontier:
            # Take the next one.
            number, step = frontier.pop(0)
            # Skip it if it was already fetched (a loop or a shared parent).
            if number in done:
                # Next one.
                continue
            # Mark it as done.
            done.add(number)
            # Fetch its four parts; keep its controllers.
            pscs = fetch_company(client, number)
            # Print progress every 25 companies.
            if len(done) % 25 == 0:
                # One short progress line.
                print(f"  {len(done)} companies fetched ({live_requests} live requests so far)")
            # Stop climbing beyond the limit.
            if step >= MAX_CLIMB:
                # Next one.
                continue
            # Each controller of this company.
            for p in pscs:
                # Only companies (not people), and only current controllers, are climbed.
                if p.get("kind") != "corporate-entity-person-with-significant-control" or p.get("ceased_on"):
                    # Next controller.
                    continue
                # The controller's identification (register, country, number).
                ident = p.get("identification") or {}
                # Its tidied number, if it is a UK company with a usable one (D-076).
                nxt = tidy_company_number(ident.get("registration_number")) if is_uk_registered(ident) else None
                # Queue it, one step further up, if it is new.
                if nxt and nxt not in done:
                    # Add it to the list to fetch.
                    frontier.append((nxt, step + 1))
                    # Note it as related if it isn't one of our In-scope companies.
                    if nxt not in start:
                        # Related, not judged (D-078).
                        related.add(nxt)
    # The summary.
    print(f"Done: {len(done)} companies ({len(start)} In-scope, {len(related & done)} related, reached by climbing); "
          # How many requests went to Companies House this run.
          f"{live_requests} live requests. Every reply is cached in data/raw/companies_house/.")


# Run fetch_all() when this file is run directly, not when it is imported.
if __name__ == "__main__":
    # Start the download.
    fetch_all()
