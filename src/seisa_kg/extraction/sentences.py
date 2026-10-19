"""SUMMARY: Turns each approved news release into numbered sentences
(PLAN 3.6: "split each release into sentences with stable IDs before the
model sees it").

For each release in config/news_releases.toml (D-079 to D-082):
- Hg and Apax: the page is downloaded once by the program (cached in
  data/raw/news/<sponsor>/<slug>.json, with its address and fetch time).
- Bridgepoint: the page Bruno saved by hand from his browser (D-082); its
  "fetch time" is the file's save time, and its provenance says so.
- The main text is pulled out (trafilatura), split into paragraphs and then
  sentences, and each sentence gets an ID like "hg-01#s07".
- A sentence repeated word for word (e.g. Apax's teaser paragraph, F35) is
  kept once.
- The result is saved as data/interim/news/<release id>.json, which is what
  the extraction step reads and what every news fact points back to.

Run it with:  make sentences
"""

# Reads and writes JSON.
import json
# Pattern matching, used to split sentences.
import re
# Reads the approved release list.
import tomllib
# Turns a file's save time into a date and time.
from datetime import datetime, timezone
# A tidy way of working with file and folder paths.
from pathlib import Path

# The library we use to send web requests.
import httpx

# The news downloader: its cache, its polite fetcher, its text extractor and how it introduces itself.
from seisa_kg.sources.news import CACHE_DIR, USER_AGENT, cached_get, extract

# The project's top folder: this file's folder, then up three levels (extraction → seisa_kg → src → project).
PROJECT_ROOT = Path(__file__).resolve().parents[3]
# The approved release list.
CONFIG_PATH = PROJECT_ROOT / "config" / "news_releases.toml"
# Where the numbered sentences are saved, one file per release.
OUT_DIR = PROJECT_ROOT / "data" / "interim" / "news"
# Short words ending in a full stop that don't end a sentence.
ABBREVIATIONS = ("Inc.", "Ltd.", "Co.", "Corp.", "Mr.", "Ms.", "Mrs.", "Dr.", "St.", "No.", "Jr.", "Sr.", "c.", "approx.", "e.g.", "i.e.", "vs.", "U.S.", "U.K.", "L.P.", "S.A.", "N.V.", "B.V.")
# Lines that are page furniture, not content (e.g. "• 3 minute read").
FURNITURE = re.compile(r"^\W*\d+ minute read\W*$|^share this|^back to|^download", re.I)


# Split one paragraph into sentences, keeping each sentence's exact words.
def split_sentences(paragraph: str) -> list[str]:
    # First cut after ., ! or ? (and any closing quote) when followed by a space and a capital, digit or opening quote.
    pieces = re.split(r'(?:(?<=[.!?])|(?<=[.!?]["”’)]))\s+(?=[A-Z0-9"“(‘])', paragraph.strip())
    # The sentences, after gluing back pieces that were cut at an abbreviation.
    out = []
    # Each piece.
    for piece in pieces:
        # If the previous sentence ended with an abbreviation (e.g. "Ltd."), this piece belongs to it.
        if out and out[-1].endswith(ABBREVIATIONS):
            # Glue it back on, with the space that was removed.
            out[-1] = f"{out[-1]} {piece}"
        # Otherwise it is a new sentence.
        else:
            # Add it.
            out.append(piece)
    # Hand back the non-empty sentences.
    return [s.strip() for s in out if s.strip()]


# Load one release's page and provenance: (html, url, retrieved_at, how it was obtained).
def load_page(client: httpx.Client, rel: dict) -> tuple[str, str, str, str]:
    # Bridgepoint: the page Bruno saved by hand (D-082).
    if "file" in rel:
        # The saved file.
        path = CACHE_DIR / rel["sponsor"] / rel["file"]
        # Its save time, in UTC, stands in for the fetch time.
        saved = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
        # The page, its official address, the save time, and how it was obtained.
        return path.read_text(encoding="utf-8", errors="replace"), rel["url"], saved, "saved by hand from the sponsor's website in a browser (D-082)"
    # Hg and Apax: the program's cached download (fetched now if missing).
    slug = rel["url"].rstrip("/").split("/")[-1]
    # Fetch or read from the cache.
    env = cached_get(client, CACHE_DIR / rel["sponsor"] / f"{slug}.json", rel["url"])
    # The page, the address reached, the fetch time, and how it was obtained.
    return env["html"], env["url"], env["retrieved_at"], "downloaded by the program from the sponsor's website"


# Build and save the numbered sentences for every approved release.
def main() -> None:
    # Read the approved list.
    with CONFIG_PATH.open("rb") as fh:
        # The releases.
        releases = tomllib.load(fh)["release"]
    # Make sure the output folder exists.
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # One web connection for any missing pages, introducing ourselves.
    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=30) as client:
        # Each release.
        for rel in releases:
            # Its page and provenance.
            html, url, when, how = load_page(client, rel)
            # Its title, date and main text.
            info = extract(html)
            # The sentences so far, and the exact texts already seen (to drop repeats, F35).
            sentences, seen = [], set()
            # Each paragraph of the main text.
            for para in info["text"].split("\n"):
                # Skip page furniture.
                if FURNITURE.search(para.strip()):
                    # Next paragraph.
                    continue
                # Each sentence in it.
                for s in split_sentences(para):
                    # Keep it once.
                    if s not in seen:
                        # Remember it.
                        seen.add(s)
                        # Give it its ID, e.g. "hg-01#s07".
                        sentences.append({"sid": f"{rel['id']}#s{len(sentences) + 1:02d}", "text": s})
            # The release's record: who, where from, when, how, and its sentences.
            doc = {"id": rel["id"], "sponsor": rel["sponsor"], "type": rel["type"], "target_country": rel["target_country"],
                   # Title and publication date as the page gives them.
                   "title": info["title"].split(" | ")[0].split(" - Bridgepoint")[0], "published": info["date"],
                   # Provenance.
                   "url": url, "retrieved_at": when, "obtained": how,
                   # The numbered sentences.
                   "sentences": sentences}
            # Save it.
            (OUT_DIR / f"{rel['id']}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
            # One line per release.
            print(f"{rel['id']:15} {len(sentences):3} sentences  {doc['published']}  {doc['title'][:60]}")


# Run main() when this file is run directly, not when it is imported.
if __name__ == "__main__":
    # Start.
    main()
