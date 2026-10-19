"""SUMMARY: Asks Gemini to extract deals, fund closes and mentions from each
news release, then checks every field against its sentence in code
(D-083 to D-085).

How it works, per release (data/interim/news/<id>.json, made by sentences.py):
1. The numbered sentences are sent to Gemini with our instructions and a
   fixed answer shape (a JSON schema), so the answer is structured data.
2. Gemini's raw answer is saved in data/raw/llm/<model>/<id>.json with the
   model, the time, the token counts and a fingerprint of the prompt. A
   release is never sent twice for the same model and prompt (like every
   other download, brief rule).
3. Every field must carry a sentence ID and an exact quote. The quote check
   (in code, not trusted to the model):
   - the sentence ID must exist in this release;
   - the quote must appear word for word in that sentence (only spaces and
     curly/straight quote marks are evened out);
   - for names and amounts, the value itself must appear in the quote.
   A field that fails is rejected and logged (D-085); the rest still load.
4. The checked results go to data/interim/extracted/<model>/<id>.json, and a
   summary with every rejection goes to docs/extraction-report.md.

The model is one setting (D-084): pass --model to compare, e.g.
    uv run python -m seisa_kg.extraction.gemini_extract --model gemini-3.8-flash

Run it with:  make extract
"""

# Reads the command-line options (e.g. --model).
import argparse
# Makes the prompt fingerprint.
import hashlib
# Reads and writes JSON.
import json
# Reads the API key from the environment.
import os
# Pattern matching, used to even out spaces and quote marks.
import re
# Runs several releases at once.
from concurrent.futures import ThreadPoolExecutor
# The current date and time, used to stamp each answer.
from datetime import datetime, timezone
# A tidy way of working with file and folder paths.
from pathlib import Path
# Declares which fields may be missing.
from typing import Literal, Optional

# Loads the secret values in .env into the environment.
from dotenv import load_dotenv
# Google's library for Gemini.
from google import genai
# Google's settings types for a request.
from google.genai import types
# Declares the answer's shape, which Gemini is told to follow.
from pydantic import BaseModel

# The project's top folder: this file's folder, then up three levels (extraction → seisa_kg → src → project).
PROJECT_ROOT = Path(__file__).resolve().parents[3]
# The numbered sentences, one file per release.
NEWS_DIR = PROJECT_ROOT / "data" / "interim" / "news"
# Gemini's raw answers (cached; they are a download like any other).
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "llm"
# The checked results.
OUT_DIR = PROJECT_ROOT / "data" / "interim" / "extracted"
# The summary for Bruno.
REPORT_PATH = PROJECT_ROOT / "docs" / "extraction-report.md"
# The model used unless another is asked for (D-084).
DEFAULT_MODEL = "gemini-2.5-pro"
# How many releases to send at once.
PARALLEL = 4


# One extracted value, with where it is stated: the sentence ID and an exact quote from it.
class Field(BaseModel):
    # The value, e.g. "Nourish Care" or "majority stake".
    value: str
    # The sentence that states it, e.g. "hg-01#s04".
    sid: str
    # Words copied exactly from that sentence that state the value.
    quote: str


# An adviser named on a deal.
class Adviser(BaseModel):
    # The adviser's name, as written.
    name: Field
    # Financial, legal or other.
    role: Optional[Field] = None
    # Whom it advised, as written.
    advising: Optional[Field] = None


# One deal announced in a release.
class Deal(BaseModel):
    # acquisition, investment, add-on, exit or other.
    kind: Field
    # The company bought, invested in or sold.
    target: Field
    # Who is buying or investing, exactly as written, e.g. "funds advised by Bridgepoint" (D-088).
    buyers: list[Field] = []
    # The sponsor named as advising or managing the buying funds, e.g. "Bridgepoint" (D-088).
    sponsor: Optional[Field] = None
    # Who is selling, as written.
    sellers: list[Field] = []
    # Any funds named as making the deal.
    funds: list[Field] = []
    # The size of the stake, as written (e.g. "majority stake").
    stake: Optional[Field] = None
    # What the buyer agreed to pay, as written, or "not disclosed" (D-086).
    price: Optional[Field] = None
    # What the company is said to be worth, as written (not a price; D-086).
    valuation: Optional[Field] = None
    # agreed or completed.
    status: Optional[Field] = None
    # The reasons the release gives for the deal.
    reasons: list[Field] = []
    # The advisers named.
    advisers: list[Adviser] = []


# One fund close announced in a release.
class FundClose(BaseModel):
    # The fund's name, as written.
    fund_name: Field
    # Its size, as written.
    size: Optional[Field] = None
    # final, first or other.
    close_type: Optional[Field] = None
    # The close date, as written.
    date: Optional[Field] = None


# A person or organisation named in the release.
class Mention(BaseModel):
    # person or organisation.
    kind: Literal["person", "organisation"]
    # The name, as written.
    name: Field
    # A person's title, as written.
    title: Optional[Field] = None
    # A person's organisation, as written.
    organisation: Optional[Field] = None


# Everything extracted from one release.
class Extraction(BaseModel):
    # The deals.
    deals: list[Deal] = []
    # The fund closes.
    fund_closes: list[FundClose] = []
    # The people and organisations named.
    mentions: list[Mention] = []


# Our instructions to Gemini.
INSTRUCTIONS = """You extract facts from one private-equity press release.
The release is given as numbered sentences, one per line: [sentence id] text.
Return JSON in the given schema. Rules:
1. Extract only what the text states. Never infer, and never use outside knowledge.
2. Every field has: value; sid (the id of the sentence that states it); quote (words copied
   exactly, character for character, from that one sentence, that state the value; keep it short
   but include the value's words).
3. Write names exactly as they appear in the text.
4. deals.kind is one of: acquisition (a sponsor's funds buy a company or a controlling stake),
   investment (a growth or minority investment), add-on (a portfolio company buys another company),
   exit (a sponsor sells all or part of a company), other.
   deals.status is "completed" ONLY if the text says the deal has completed, closed or that they have
   acquired; otherwise (secures, to acquire, will, agreed, signed) it is "agreed".
   deals.buyers: write the buyer exactly as the text puts it, e.g. "funds advised by Bridgepoint", not just
   "Bridgepoint". deals.sponsor: the private-equity firm named as advising or managing the buying funds.
   deals.price: what the buyer pays or agreed to pay (or "not disclosed"). deals.valuation: what the company is
   said to be worth (e.g. "at a valuation of", "enterprise value"). Never put a valuation in price.
   Copy amounts exactly as written (e.g. "$1.393 billion"), never as plain digits.
5. deals.reasons: each reason the release gives for the deal, as a short exact quote.
6. advisers: banks, law firms and consultants named as advising on the deal, with role
   (financial, legal or other) and whom they advised.
7. fund_closes only for announcements of a fund raising money; close_type is final, first or other.
8. mentions: every person named (with title and organisation if stated) and every organisation named.
9. If something is not stated, leave it out. Do not guess."""
# The fields whose value is a category we chose, not words from the text (so the value isn't looked for in the quote).
CATEGORY_FIELDS = {"kind", "status", "close_type", "role"}


# Even out spaces and quote marks, so an exact quote isn't rejected for typography alone.
def even(text: str) -> str:
    # Curly quotes become straight ones, dashes become hyphens, runs of spaces become one space.
    return re.sub(r"\s+", " ", text.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'").replace("–", "-").replace("—", "-")).strip()


# Check one field against its sentence; returns the reason it fails, or None if it passes.
def check_field(name: str, f: dict, sentences: dict[str, str]) -> str | None:
    # The sentence must exist in this release (short IDs like "s01" were already expanded, D-089).
    if f["sid"] not in sentences:
        # Explain the failure.
        return f"sentence {f['sid']} does not exist"
    # The quote must appear word for word in that sentence.
    if even(f["quote"]) not in even(sentences[f["sid"]]):
        # Explain the failure.
        return "quote not found in its sentence"
    # For names and amounts, the value itself must appear in the quote.
    if name not in CATEGORY_FIELDS and even(f["value"]).lower() not in even(f["quote"]).lower():
        # Explain the failure.
        return "value not found in its quote"
    # Passed.
    return None


# Expand short sentence IDs like "s01" to "<release>#s01" everywhere in an answer (D-089); returns how many.
def expand_short_ids(node, doc_id: str) -> int:
    # How many were expanded.
    n = 0
    # A field (it has a "sid"): expand its ID if it is the short form.
    if isinstance(node, dict) and isinstance(node.get("sid"), str) and re.fullmatch(r"s\d+", node["sid"]):
        # e.g. "s01" -> "bridgepoint-03#s01".
        node["sid"] = f"{doc_id}#{node['sid']}"
        # Count it.
        n += 1
    # Look inside dictionaries and lists for more fields.
    for child in (node.values() if isinstance(node, dict) else node if isinstance(node, list) else []):
        # Expand inside the child.
        n += expand_short_ids(child, doc_id)
    # Hand back the count.
    return n


# An explicit "unknown" for a required field that failed its check (D-090), saying why.
def unknown(problem: str) -> dict:
    # No sentence or quote: the value is unknown because the check failed.
    return {"value": "unknown", "sid": None, "quote": None, "why": problem}


# Walk an extracted answer and drop every field that fails its check; returns (clean answer, rejections).
def verify(data: dict, sentences: dict[str, str], doc_id: str) -> tuple[dict, list[dict]]:
    # The rejections found.
    rejected = []

    # Check one field or list of fields under a name; returns the passing part (or None / a shorter list).
    def keep(name, value, where):
        # A list: keep only the items that pass.
        if isinstance(value, list):
            # Each item checked in turn.
            return [v for v in (keep(name, item, where) for item in value) if v is not None]
        # A missing field: nothing to check.
        if value is None:
            # Stays missing.
            return None
        # One field: check it.
        problem = check_field(name, value, sentences)
        # Failed: log it and drop it.
        if problem:
            # One rejection record.
            rejected.append({"release": doc_id, "where": where, "field": name, "value": value["value"], "sid": value["sid"], "quote": value["quote"], "problem": problem})
            # Dropped.
            return None
        # Passed: keep it.
        return value

    # The clean answer, built as we go.
    clean = {"deals": [], "fund_closes": [], "mentions": []}
    # Each deal.
    for i, d in enumerate(data.get("deals", []), start=1):
        # Where it is, for the log.
        where = f"deal {i}"
        # The deal with every field checked (advisers below).
        out = {k: keep(k, v, where) for k, v in d.items() if k != "advisers"}
        # Required fields that failed are kept as an explicit "unknown", saying why (D-090).
        for req in ("target", "kind"):
            # Failed (or missing): mark it unknown.
            if out.get(req) is None:
                # The reason, from the last rejection of this field here, if any.
                why = next((r["problem"] for r in reversed(rejected) if r["where"] == where and r["field"] == req), "not given")
                # Unknown, with why.
                out[req] = unknown(why)
        # Each adviser: its name must pass; its role and client are checked too.
        out["advisers"] = [{"name": a["name"], "role": keep("role", a.get("role"), where), "advising": keep("advising", a.get("advising"), where)}
                           # Only advisers whose name passes.
                           for a in d.get("advisers", []) if keep("name", a["name"], where) is not None]
        # Keep the deal.
        clean["deals"].append(out)
    # Each fund close: the fund's name is required.
    for i, fc in enumerate(data.get("fund_closes", []), start=1):
        # Where it is, for the log.
        where = f"fund close {i}"
        # Without a passing name, the close is dropped.
        if keep("fund_name", fc["fund_name"], where) is None:
            # Dropped.
            continue
        # The close with every field checked.
        clean["fund_closes"].append({k: keep(k, v, where) for k, v in fc.items()})
    # Each mention: the name is required.
    for i, m in enumerate(data.get("mentions", []), start=1):
        # Where it is, for the log.
        where = f"mention {i}"
        # Without a passing name, the mention is dropped.
        if keep("name", m["name"], where) is None:
            # Dropped.
            continue
        # The mention with its other fields checked.
        clean["mentions"].append({k: (v if k == "kind" else keep(k, v, where)) for k, v in m.items()})
    # Hand back the clean answer and the rejections.
    return clean, rejected


# Ask Gemini about one release (or read its cached answer); returns the saved answer record.
def ask(client: genai.Client, model: str, doc: dict) -> dict:
    # The release as numbered lines, e.g. "[hg-01#s04] Hg will acquire ...".
    text = "\n".join(f"[{s['sid']}] {s['text']}" for s in doc["sentences"])
    # A fingerprint of exactly what is sent, so a changed prompt is never mixed up with an old answer.
    fingerprint = hashlib.sha256((model + INSTRUCTIONS + text).encode("utf-8")).hexdigest()[:16]
    # Where this answer is cached.
    cache = RAW_DIR / model / f"{doc['id']}.json"
    # Reuse it if it was made from exactly the same prompt.
    if cache.exists():
        # The saved answer.
        saved = json.loads(cache.read_text(encoding="utf-8"))
        # Same prompt: reuse it.
        if saved["prompt_fingerprint"] == fingerprint:
            # Hand it back.
            return saved
    # Send the request: our instructions, the release, JSON out in our schema, and no randomness.
    response = client.models.generate_content(model=model, contents=text, config=types.GenerateContentConfig(
        # Our rules.
        system_instruction=INSTRUCTIONS,
        # Answer in JSON...
        response_mime_type="application/json",
        # ...in exactly this shape.
        response_schema=Extraction,
        # As repeatable as the model allows.
        temperature=0))
    # The saved record: the answer with its provenance (which model, when, what it cost).
    saved = {"release": doc["id"], "model": model, "asked_at": datetime.now(timezone.utc).isoformat(),
             # The prompt fingerprint and token counts.
             "prompt_fingerprint": fingerprint, "input_tokens": response.usage_metadata.prompt_token_count,
             # Output tokens (including any thinking).
             "output_tokens": (response.usage_metadata.candidates_token_count or 0) + (response.usage_metadata.thoughts_token_count or 0),
             # Gemini's answer, as JSON text.
             "answer": response.text}
    # Make sure the folder exists.
    cache.parent.mkdir(parents=True, exist_ok=True)
    # Save it.
    cache.write_text(json.dumps(saved, ensure_ascii=False, indent=1), encoding="utf-8")
    # Hand it back.
    return saved


# Extract, check and save one release; returns its summary numbers and rejections.
def process(client: genai.Client, model: str, path: Path) -> dict:
    # The release's sentences.
    doc = json.loads(path.read_text(encoding="utf-8"))
    # The sentence texts by ID.
    sentences = {s["sid"]: s["text"] for s in doc["sentences"]}
    # Gemini's answer (cached or new).
    saved = ask(client, model, doc)
    # Its structured data.
    data = json.loads(saved["answer"])
    # Expand short sentence IDs (D-089), counting them for the report.
    short_ids = expand_short_ids(data, doc["id"])
    # Every field checked against its sentence.
    clean, rejected = verify(data, sentences, doc["id"])
    # The checked result, with the release's provenance carried along.
    out = {"release": doc["id"], "model": model, "asked_at": saved["asked_at"], **clean}
    # Make sure the folder exists.
    (OUT_DIR / model).mkdir(parents=True, exist_ok=True)
    # Save it.
    (OUT_DIR / model / f"{doc['id']}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    # The summary numbers.
    return {"release": doc["id"], "short_ids": short_ids, "deals": len(clean["deals"]), "fund_closes": len(clean["fund_closes"]), "mentions": len(clean["mentions"]),
            # Tokens, for the cost note.
            "tokens": saved["input_tokens"] + saved["output_tokens"], "rejected": rejected}


# Run every release through Gemini and the check, and write the report.
def main() -> None:
    # The command-line options.
    parser = argparse.ArgumentParser(description="Extract facts from the news releases with Gemini.")
    # Which model (D-084).
    parser.add_argument("--model", default=DEFAULT_MODEL)
    # Read them.
    args = parser.parse_args()
    # Load .env so the key is available (its value is never printed).
    load_dotenv(PROJECT_ROOT / ".env")
    # The Gemini client, using the project's key.
    client = genai.Client(api_key=os.environ["LLM_API_KEY"])
    # Every release's sentence file, in name order.
    paths = sorted(NEWS_DIR.glob("*.json"))
    # Run several at once.
    with ThreadPoolExecutor(PARALLEL) as pool:
        # One summary per release, in order.
        results = list(pool.map(lambda p: process(client, args.model, p), paths))
    # All rejections.
    rejected = [r for res in results for r in res["rejected"]]
    # The report's opening lines.
    L = [f"# Extraction report: {args.model} (generated by `make extract`; do not edit by hand)", "",
         # The totals.
         f"{len(results)} releases · {sum(r['deals'] for r in results)} deals · {sum(r['fund_closes'] for r in results)} fund closes · "
         # More totals.
         f"{sum(r['mentions'] for r in results)} mentions · **{len(rejected)} fields rejected** by the quote check (D-085) · {sum(r['tokens'] for r in results):,} tokens", "",
         # The per-release table.
         f"Short sentence IDs expanded (D-089): {sum(r['short_ids'] for r in results)}.", "",
         # The per-release table header.
         "| Release | Deals | Fund closes | Mentions | Rejected |", "|---|---|---|---|---|"]
    # One row per release.
    L += [f"| {r['release']} | {r['deals']} | {r['fund_closes']} | {r['mentions']} | {len(r['rejected'])} |" for r in results]
    # The rejections, each with its reason.
    L += ["", "## Rejected fields", "", "| Release | Where | Field | Value | Sentence | Problem |", "|---|---|---|---|---|---|"]
    # One row per rejection.
    L += [f"| {r['release']} | {r['where']} | {r['field']} | {r['value'][:60]} | {r['sid']} | {r['problem']} |" for r in rejected]
    # Save the report.
    REPORT_PATH.write_text("\n".join(L) + "\n", encoding="utf-8")
    # Say what happened.
    print(L[2].replace("**", "")); print(L[4])
    # Say where the report is.
    print(f"Report: {REPORT_PATH.relative_to(PROJECT_ROOT)}")


# Run main() when this file is run directly, not when it is imported.
if __name__ == "__main__":
    # Start.
    main()
