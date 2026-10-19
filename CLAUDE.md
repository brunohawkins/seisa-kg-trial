# Seisa trial: instructions for Claude Code

Claude Code reads this file automatically when it opens in this folder. It holds the working rules for this project, so every new session starts with them.

## What this project is
- A trial task for a founding-engineer role at Seisa. The brief is in `brief/` (gitignored; Seisa material).
- **The task:** public data about three private equity sponsors (**Hg, Bridgepoint, Apax**), stored in two graphs.
  - **RDF first** (Oxigraph, with RDF-star for sources), **then** a Neo4j property graph.
  - Investor questions answered in both SPARQL and Cypher.
  - LLM (Gemini) extraction from news releases.
  - Entity matching, with precision and recall.
  - A comparison of text-to-Cypher, text-to-SPARQL and vector search.
  - Visualisations and a write-up.
- **Bruno's own extensions** (a translation layer, a GUI) were **dropped on 19 Oct (D-066)** to finish by Wednesday 21 Oct and present on Thursday 22 Oct. Visualisation uses the standard tools: Neo4j Bloom plus one other.
- **What matters most:** the explain-back, which Bruno does with no code open. Depth and understanding beat coverage.

## Read these first, every session
1. `docs/decision-log.md`: the decision diary. Start from the **latest entry and its TODO list**.
2. `PLAN.md`: the overall plan. The diary is the source of truth wherever the two differ.
3. `docs/data-sources.md`: what each source contains, and findings F1–F11.

## Working rules
- **Bruno makes every decision.** Propose options with a recommendation and the reasons, then wait. Never make a design choice silently.
- **Bruno becomes the expert; Claude codes and takes notes (D-067).** For every design question:
  1. **Bruno thinks first.** Claude gives the questions to consider and the sources to read, not the answer. Bruno writes a first answer.
  2. **Claude reviews it with evidence:** a cited source (W3C spec, paper, docs) or a finding from our own data. Label what's fact and what's opinion.
  3. **Bruno decides,** and writes the why in his own words. Claude logs it.
  4. **Claude codes in small pieces.** Bruno runs each one and reads the output.
  5. **Bruno explains the step back** with no code open, and Claude asks the questions Seisa might ask, before moving on.
- **Log every decision** in `docs/decision-log.md`.
  - One dated entry per session, in bullet points, with permanent IDs (D-0xx).
  - Give the **why** for each decision, in short sentences Bruno can copy into a notebook.
  - **Close every entry with a TODO list**, and tick earlier TODOs when they are done.
- **Comment every line of code in plain English**, and open every file with a plain-English summary.
  - This applies to Python, SPARQL, Cypher, shell, Makefile, TOML and YAML.
- **Strategy (D-029):** record exactly what each source says, with its source and the date fetched. Never silently correct a source. Our own judgements (scope, roles, matches) are separate, labelled facts, each with its reason.
- **Never display or commit secrets.**
  - Keys and the Neo4j password live in `.env`, which is gitignored.
  - Check values without printing them.
- **Commits:** author Bruno only. **No Claude co-author or contributor line.**
- **Don't assume pronouns** for Bruno. Use the name.
- **Cache every download** in `data/raw/`, and respect rate limits: GLEIF 60 per minute; Companies House 600 per 5 minutes.

## Environment
- **Location:** `~/Work Projects/seisa-kg-trial`. The Desktop's `Work` is a shortcut to `~/Work Projects` (D-030, D-031). Kept out of iCloud on purpose.
- **Don't rename or move the project folder** without updating the two `server.directories.*` paths at the bottom of `tools/neo4j/conf/neo4j.conf` (finding F11).
- **Python:** 3.12 via `uv`.
  - `make setup` installs the environment; `make test` runs the tests.
  - Run scripts with `uv run python scripts/<name>.py`.
- **Neo4j:**
  - `make neo4j-start` / `make neo4j-stop` / `make neo4j-status`.
  - It is the project's own Community server in `tools/neo4j`, with its database in `data/neo4j`.
  - Neo4j Desktop is used for viewing only.
- **Code layout:**
  - `src/seisa_kg/sources/`: one cached downloader per source
  - `scripts/`: one-off helpers
  - `config/sponsors.toml`: the sponsors and their search words
  - `docs/`: everything written up.
