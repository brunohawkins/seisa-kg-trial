"""SUMMARY: The hand-check sample for matching (D-107): 50 distinct news names,
stratified by the code's outcome, for Bruno to judge blind.

It writes two files:
- eval/matching-sample.csv: what Bruno sees. Each row has the name, its role and
  the sentence it came from, plus empty columns for his answer. The code's answer
  is NOT in it, so he isn't anchored by it.
- data/interim/matching-sample-key.json: the code's answers and each group's real
  size (needed to weight recall), kept apart until Bruno has finished.

Run with: uv run python -m seisa_kg.matching.sample
"""

# Writes the sheet as a spreadsheet-friendly CSV.
import csv
# Writes the hidden answer key.
import json
# Random picking with a fixed seed, so the same sample comes out every time.
import random

# The shared fact list and the project folder.
from seisa_kg.facts.model import PROJECT_ROOT, read_facts
# Step 2: every name's outcome.
from seisa_kg.matching.outcomes import match_all

# How many names to take from each outcome group (D-107; news-only added by D-109); 50 in total.
QUOTAS = {"sameEntityAs": 2, "ambiguous": 2, "refersToGroup": 15, "news-only": 7, "non-entity": 5, "unresolved": 1, "out-of-scope": 18}
# The seed: today's date, so the pick can be repeated exactly.
SEED = 20261020
# The sheet Bruno fills in (kept in git: it becomes the answer set).
SHEET_PATH = PROJECT_ROOT / "eval" / "matching-sample.csv"
# The code's answers, kept out of sight until the sheet is filled.
KEY_PATH = PROJECT_ROOT / "data" / "interim" / "matching-sample-key.json"


# One entry per distinct (role, name): the first time it appears, with its outcome.
def distinct_names(results: list[dict]) -> list[dict]:
    # Seen (role, name) pairs.
    seen = {}
    # Each name, in the fixed order step 2 gives.
    for r in results:
        # Keep the first appearance only.
        seen.setdefault((r["role"], r["name"]), r)
    # The distinct entries.
    return list(seen.values())


# Pick the stratified sample. Returns the picked entries and each group's real size.
def pick(entries: list[dict]) -> tuple[list[dict], dict]:
    # The random picker with the fixed seed.
    rng = random.Random(SEED)
    # The picked entries.
    picked = []
    # Each group's real size.
    sizes = {}
    # Each outcome group.
    for outcome, quota in QUOTAS.items():
        # The group's members.
        group = [e for e in entries if e["outcome"] == outcome]
        # Its size, for weighting recall later.
        sizes[outcome] = len(group)
        # A random pick of up to the quota.
        picked += rng.sample(group, min(quota, len(group)))
    # Shuffle, so the sheet's order gives no hint of the outcome.
    rng.shuffle(picked)
    # Hand back both.
    return picked, sizes


# Each sentence record's text, e.g. {"src:news/hg-01/s07": "Hg has agreed..."}.
def sentence_texts(rows: list[dict]) -> dict[str, str]:
    # Every "text" fact on a sentence record.
    return {r["subject"]: r["object"]["value"] for r in rows if r["predicate"] == "text" and r["subject"].startswith("src:news/")}


# Build the sample and write both files.
def main() -> None:
    # The fact list.
    rows = read_facts()
    # The distinct names with their outcomes.
    entries = distinct_names(match_all(rows))
    # The sample and the group sizes.
    picked, sizes = pick(entries)
    # The sentences.
    texts = sentence_texts(rows)
    # Make sure eval/ exists.
    SHEET_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Write the sheet.
    with SHEET_PATH.open("w", newline="", encoding="utf-8") as f:
        # A CSV writer.
        w = csv.writer(f)
        # The header: the last three columns are Bruno's.
        w.writerow(["id", "role", "name", "sentence", "your_outcome", "your_target", "your_note"])
        # One row per picked name.
        for i, e in enumerate(picked, start=1):
            # The name, its role and its sentence; Bruno's columns empty.
            w.writerow([i, e["role"], e["name"], texts.get(e["record"], ""), "", "", ""])
    # The hidden key: the code's outcome and target for each row, and the group sizes.
    key = {"seed": SEED, "group_sizes": sizes, "quotas": QUOTAS,
           # Each row's code answer.
           "rows": [{"id": i, "role": e["role"], "name": e["name"], "outcome": e["outcome"], "to": e["to"], "why": e["why"]}
                    # Numbered as on the sheet.
                    for i, e in enumerate(picked, start=1)]}
    # Save the key.
    KEY_PATH.write_text(json.dumps(key, indent=1, ensure_ascii=False), encoding="utf-8")
    # Say where things went.
    print(f"{len(picked)} names; sheet: {SHEET_PATH.relative_to(PROJECT_ROOT)}; group sizes: {sizes}")


# Run main() when the file is run directly.
if __name__ == "__main__":
    # Go.
    main()
