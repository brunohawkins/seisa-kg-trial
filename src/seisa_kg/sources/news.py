"""SUMMARY: Downloads news releases from the sponsors' own websites
(pipeline stage 1, fetch, for the news; D-079 to D-081).

What it does:
- Reads each sponsor's news list (Hg: one page; Apax: pages 0-4) and keeps the
  links whose titles look like deals, exits or fund closes.
- Downloads each of those releases once, and saves the page in
  data/raw/news/<sponsor>/<slug>.json with its web address and the date and
  time it was fetched (brief rule: never download twice).
- Pulls out each release's title, publication date and main text with a
  standard extractor (trafilatura), and writes a candidate list for Bruno to
  approve: docs/news-candidates.md (D-081).
- Waits between requests and identifies itself; all three sites allow
  programs (robots.txt checked 19 Oct).
- Bridgepoint is NOT fetched here: its article pages sit behind a bot
  challenge (F39), which we do not try to get around.

Run it with:  uv run python -m seisa_kg.sources.news
"""

# Reads and writes JSON, the format each saved page is kept in.
import json
# Pattern matching, used to find links and guess a release's type.
import re
# Lets us pause between requests and measure time.
import time
# The current date and time, used to stamp when each page was fetched.
from datetime import datetime, timezone
# A tidy way of working with file and folder paths.
from pathlib import Path

# The library we use to send web requests.
import httpx
# The standard main-text extractor for web pages.
import trafilatura

# The project's top folder: this file's folder, then up three levels (sources → seisa_kg → src → project).
PROJECT_ROOT = Path(__file__).resolve().parents[3]
# The folder where every downloaded page is cached.
CACHE_DIR = PROJECT_ROOT / "data" / "raw" / "news"
# The candidate list for Bruno.
REPORT_PATH = PROJECT_ROOT / "docs" / "news-candidates.md"
# How we introduce ourselves to the websites.
USER_AGENT = "seisa-kg-trial research project (github.com/brunohawkins)"
# The smallest gap between two requests, in seconds: polite to small corporate sites.
MIN_GAP_SECONDS = 1.5
# Only releases published on or after this date are candidates (D-079: 2025-26).
EARLIEST = "2025-01-01"

# Each sponsor's site: its address, its news-list pages, and the pattern of a release link.
SITES = {
    # Hg lists every release on one page.
    "hg": {"base": "https://hgcapital.com", "lists": ["/news"], "link": r'href="(/insights/[a-z0-9-]+)"'},
    # Apax lists releases over several pages (?page=0 to 4).
    "apax": {"base": "https://www.apax.com", "lists": [f"/news-views/?page={i}" for i in range(5)], "link": r'href="(/news-views/[a-z0-9-]+/)"'},
}
# Words in a link that suggest a deal, an exit or a fund close.
DEAL_WORDS = re.compile(r"acqui|invest|sell|sale|sold|exit|close|closing|fund|raise|merg|combin|partner|backs|backing|stake|agree|complet|majority|minority|buyout|buy")
# Words in a link that suggest an opinion piece, an event or a people announcement instead.
NOT_DEAL_WORDS = re.compile(r"speaks|podcast|webinar|unpacked|joins|appoint|award|ranks|report|review|survey|how-|what-|why-|field-notes|bloomberg|television|scholarship|promot|anniversar|lens|outlook|trends")
# Place words that suggest the target is UK-based (a hint only; Bruno checks).
UK_WORDS = re.compile(r"\b(UK|U\.K\.|United Kingdom|London|England|Scotland|Wales|Manchester|Birmingham|Edinburgh|Glasgow|Leeds|Bristol|Cambridge|Oxford|British)\b")

# When our last live request was sent. Starts at zero, i.e. "long ago".
_last_request_at = 0.0


# Fetch one web page, using the cache when possible; returns the saved envelope.
def cached_get(client: httpx.Client, cache_file: Path, url: str) -> dict:
    # Let this function update the shared "last request" time.
    global _last_request_at
    # If we already have this page on disk, read it and return it straight away.
    if cache_file.exists():
        # Turn the saved text back into data.
        return json.loads(cache_file.read_text(encoding="utf-8"))
    # Work out how long ago the last request was sent.
    wait = MIN_GAP_SECONDS - (time.monotonic() - _last_request_at)
    # If it was too recent, pause for the remaining time.
    if wait > 0:
        # Sleep for the remaining part of the gap.
        time.sleep(wait)
    # Send the request, following redirects.
    response = client.get(url, follow_redirects=True)
    # Remember when this request was sent.
    _last_request_at = time.monotonic()
    # Wrap the page with its provenance: where it came from and when.
    envelope = {
        # The address finally reached (after any redirect).
        "url": str(response.url),
        # The date and time it was fetched, in UTC.
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        # 200 means the page came back normally.
        "status": response.status_code,
        # The page's HTML, exactly as received.
        "html": response.text,
    }
    # Make sure the sponsor's folder exists.
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    # Save the envelope so this page is never fetched again.
    cache_file.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")
    # Hand back the envelope.
    return envelope


# Pull the title, publication date and main text out of a saved page.
def extract(html: str) -> dict:
    # The page's metadata (title, date), as the extractor reads it.
    meta = trafilatura.extract_metadata(html)
    # The main text, without menus, footers or comments.
    text = trafilatura.extract(html, include_comments=False, include_tables=False) or ""
    # Hand back the three parts.
    return {"title": (meta.title if meta else "") or "", "date": (meta.date if meta else "") or "", "text": text}


# Guess a release's type from its title (a hint for Bruno's review only).
def guess_type(title: str) -> str:
    # Lower case, so the word tests ignore capitals.
    t = title.lower()
    # Fund closes mention a close and a fund.
    if re.search(r"\bclos", t) and "fund" in t:
        # A fund close.
        return "fund close"
    # Sales and exits.
    if re.search(r"\bsale\b|\bsell|\bsold|\bexit|divest", t):
        # An exit.
        return "exit"
    # A portfolio company buying another: an add-on.
    if re.search(r"acquires|to acquire|merge|combine|join forces", t) and not re.search(r"\b(hg|apax|bridgepoint)\b.*\b(acquire|acquisition)", t):
        # An add-on (to check).
        return "add-on?"
    # Everything else that got this far is a new investment.
    return "deal"


# Fetch every candidate release for one sponsor; returns one summary row per release.
def sponsor_candidates(client: httpx.Client, sponsor: str) -> list[dict]:
    # This sponsor's site settings.
    site = SITES[sponsor]
    # The release links found, in the order the site lists them.
    links = []
    # Each news-list page.
    for i, path in enumerate(site["lists"]):
        # Fetch it (cached as list_<n>.json).
        env = cached_get(client, CACHE_DIR / sponsor / f"list_{i}.json", site["base"] + path)
        # Each release link on that page.
        for link in re.findall(site["link"], env["html"]):
            # Keep it once, if it looks like a deal and not like an opinion piece.
            if link not in links and DEAL_WORDS.search(link) and not NOT_DEAL_WORDS.search(link):
                # Add it.
                links.append(link)
    # The summary rows.
    rows = []
    # Each candidate link.
    for link in links:
        # A safe file name from the link, e.g. "auditboard-agrees-to-be-acquired-by-hg".
        slug = link.strip("/").split("/")[-1]
        # Fetch the release (cached).
        env = cached_get(client, CACHE_DIR / sponsor / f"{slug}.json", site["base"] + link)
        # Pull out its title, date and text.
        info = extract(env["html"])
        # Skip releases before the date window (they're older than 2025).
        if info["date"] and info["date"] < EARLIEST:
            # Stop here: the lists run newest first, so everything after this is older too.
            break
        # One summary row.
        rows.append({"sponsor": sponsor, "date": info["date"], "title": info["title"].split(" | ")[0],
                     # Our guesses, for Bruno to check.
                     "type": guess_type(info["title"]), "uk": "yes?" if UK_WORDS.search(info["text"][:1500]) else "",
                     # Where it came from.
                     "url": env["url"], "slug": slug})
    # Hand back the rows.
    return rows


# Build the candidate list for Hg and Apax and write it for Bruno.
def main() -> None:
    # The rows for every sponsor.
    rows = []
    # One web connection, reused, introducing ourselves; 30 seconds before giving up.
    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=30) as client:
        # Each sponsor we can fetch.
        for sponsor in SITES:
            # Its candidates.
            found = sponsor_candidates(client, sponsor)
            # Say how many.
            print(f"{sponsor}: {len(found)} candidate releases since {EARLIEST}")
            # Add them.
            rows += found
    # The report's opening lines.
    L = ["# News release candidates (generated; for Bruno to approve, D-081)", "",
         # How to read it.
         "Type and UK are **guesses** from the title and the first paragraph; Bruno checks them. Bridgepoint is missing: its pages sit behind a bot challenge (F39).", "",
         # The table header.
         "| # | Sponsor | Date | Type (guess) | UK? (guess) | Title |", "|---|---|---|---|---|---|"]
    # One table row per candidate.
    for i, r in enumerate(rows, start=1):
        # The row, with the title linked to the release.
        L.append(f"| {i} | {r['sponsor']} | {r['date']} | {r['type']} | {r['uk']} | [{r['title']}]({r['url']}) |")
    # Save the report.
    REPORT_PATH.write_text("\n".join(L) + "\n", encoding="utf-8")
    # Say where it is.
    print(f"Candidates: {REPORT_PATH.relative_to(PROJECT_ROOT)}")


# Run main() when this file is run directly, not when it is imported.
if __name__ == "__main__":
    # Start.
    main()
