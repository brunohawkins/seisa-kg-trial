"""SUMMARY: A one-off helper for the Companies House source study (19 Oct).

It fetches a handful of real Companies House records, so we can see exactly
what the register gives us before designing anything:
- for each sample company: its profile, its officers (directors) and its
  PSC list ("people with significant control", i.e. who controls it);
- when a controller is itself a UK company, it follows that company's PSC list
  too, climbing the ownership chain a few steps.

Every reply is cached in data/raw/companies_house/<company number>/<part>.json,
with the web address and the date and time it was fetched (brief rule: never
download twice). The API key is read from .env and never printed.
A short readable summary is printed at the end.

Run it with:  uv run python scripts/ch_sample.py
"""

# Reads and writes JSON, the text format Companies House replies in.
import json
# Reads the API key from the environment.
import os
# Lets us pause between requests.
import time
# The current date and time, used to stamp when each reply was fetched.
from datetime import datetime, timezone
# A tidy way of working with file and folder paths.
from pathlib import Path

# The library we use to send web requests.
import httpx
# Loads the secret values in .env into the environment.
from dotenv import load_dotenv

# The start of every Companies House API web address.
BASE_URL = "https://api.company-information.service.gov.uk"
# The project's top folder: this file's folder, then up one level.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
# The folder where every Companies House reply is cached.
CACHE_DIR = PROJECT_ROOT / "data" / "raw" / "companies_house"
# The smallest gap between two live requests: 600 per 5 minutes is 2 a second, so 0.6 s leaves a margin.
MIN_GAP_SECONDS = 0.6
# How many steps up the ownership chain to follow at most.
MAX_CLIMB = 4

# The sample companies, one of each kind, chosen from our In-scope list.
SAMPLES = {
    # An ordinary company (a sponsor's management company).
    "03220373": "BRIDGEPOINT ADVISERS LIMITED",
    # An LLP (a sponsor's main firm).
    "OC301825": "HGCAPITAL LLP",
    # Another LLP, for Apax.
    "OC303117": "APAX PARTNERS LLP",
    # A Scottish limited partnership (a fund vehicle).
    "SL032338": "HG SATURN FAF L.P.",
    # An English limited partnership (a fund vehicle); filled in below from our data.
}

# When our last live request was sent. Starts at zero, i.e. "long ago".
_last_request_at = 0.0


# Fetch one Companies House address, using the cache when possible; returns the saved envelope.
def cached_get(client: httpx.Client, number: str, part: str, path: str) -> dict:
    # Let this function update the shared "last request" time.
    global _last_request_at
    # Where this reply is (or will be) saved.
    cache_file = CACHE_DIR / number / f"{part}.json"
    # If we already have it, read it and return it straight away.
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
    response = client.get(f"{BASE_URL}{path}")
    # Remember when this request was sent, for the next gap check.
    _last_request_at = time.monotonic()
    # A 404 ("not found", e.g. no PSC list for this kind of company) is a real answer, so it is kept.
    if response.status_code != 404:
        # Any other failure stops the program with a clear error.
        response.raise_for_status()
    # Wrap the reply with its provenance: where it came from and when.
    envelope = {
        # The full web address that was asked.
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
    # Save the envelope, nicely indented so it can be read by eye.
    cache_file.write_text(json.dumps(envelope, indent=2, ensure_ascii=False), encoding="utf-8")
    # Hand back the envelope.
    return envelope


# Fetch the three parts we study for one company; returns them as a dictionary.
def fetch_company(client: httpx.Client, number: str) -> dict:
    # The profile, the officers and the PSC list.
    return {
        # Name, type, status, dates, registered address.
        "profile": cached_get(client, number, "profile", f"/company/{number}"),
        # Directors and secretaries, with appointment dates.
        "officers": cached_get(client, number, "officers", f"/company/{number}/officers"),
        # Who controls it, and how.
        "psc": cached_get(client, number, "psc", f"/company/{number}/persons-with-significant-control"),
    }


# Pick one English LP from our In-scope list (the first Hg one, by number).
def one_english_lp() -> tuple[str, str]:
    # The shared fact list.
    rows = [json.loads(line) for line in open(PROJECT_ROOT / "data" / "interim" / "facts.jsonl", encoding="utf-8")]
    # LEIs judged In for Hg.
    hg_in = {"lei:" + r["subject"].split("/")[2] for r in rows if r["predicate"] == "verdict" and r["subject"].startswith("ex:scope/hg/") and r["object"]["iri"] == "ex:In"}
    # Their registration numbers.
    numbers = {r["subject"]: r["object"]["value"] for r in rows if r["predicate"] == "registeredAs"}
    # Their names.
    names = {r["subject"]: r["object"]["value"] for r in rows if r["predicate"] == "legalName"}
    # The Hg In companies whose number starts with LP, sorted by number.
    lps = sorted((numbers[l], names[l]) for l in hg_in if numbers.get(l, "").startswith("LP"))
    # The first one.
    return lps[0]


# Fetch every sample, climb the ownership chains, and print a short summary.
def main() -> None:
    # Load .env so the key is available (its value is never printed).
    load_dotenv(PROJECT_ROOT / ".env")
    # The API key; Companies House uses it as the user name, with an empty password.
    key = os.environ["COMPANIES_HOUSE_API_KEY"]
    # Add the English LP sample.
    number, name = one_english_lp()
    # Put it in the sample list.
    SAMPLES[number] = name
    # One web connection, reused, logging in with the key; 30 seconds before giving up.
    with httpx.Client(auth=(key, ""), timeout=30) as client:
        # Go through each sample company.
        for number, name in SAMPLES.items():
            # Fetch its three parts.
            parts = fetch_company(client, number)
            # Its profile, if found.
            profile = parts["profile"]["body"] or {}
            # The heading line: number, name, type.
            print(f"\n{number}  {name}  [type: {profile.get('type')}, status: {profile.get('company_status')}]")
            # How many officers are listed.
            print(f"  officers: {(parts['officers']['body'] or {}).get('total_results', 'none (404)')}")
            # Climb the chain: start at this company.
            current, step = number, 0
            # Keep climbing while there is a UK company controller and we haven't gone too far.
            while current and step < MAX_CLIMB:
                # The PSC list of the current company.
                psc = (cached_get(client, current, "psc", f"/company/{current}/persons-with-significant-control")["body"] or {})
                # Its controllers.
                items = psc.get("items", [])
                # Say if there's nothing to climb.
                if not items:
                    # No PSC list: say why the climb stops.
                    print(f"  {'  ' * step}PSC: none returned for {current}")
                    # Stop climbing.
                    break
                # The next company to climb to, if any.
                nxt = None
                # Each controller.
                for it in items:
                    # The registration number, if the controller is a company.
                    reg = (it.get("identification") or {}).get("registration_number")
                    # One line: kind, name, how it controls, and its number.
                    print(f"  {'  ' * step}PSC of {current}: {it.get('kind')} | {it.get('name')} | {', '.join(it.get('natures_of_control', []))} | reg no: {reg} | ceased: {it.get('ceased_on', '-')}")
                    # Climb to the first current UK company controller with a plausible number.
                    if reg and not it.get("ceased_on") and nxt is None and it.get("kind") == "corporate-entity-person-with-significant-control":
                        # Companies House numbers are 8 characters, zero-padded.
                        nxt = reg.replace(" ", "").zfill(8) if reg.replace(" ", "").isdigit() else reg.replace(" ", "")
                # If there's a company to climb to, fetch its profile so its name is cached too.
                if nxt:
                    # Fetch its profile (cached).
                    cached_get(client, nxt, "profile", f"/company/{nxt}")
                # Move up one step.
                current, step = nxt, step + 1


# Run main() when this file is run directly, not when it is imported.
if __name__ == "__main__":
    # Start.
    main()
