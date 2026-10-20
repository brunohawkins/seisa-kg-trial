# Decision diary

A chronological diary of every decision made in this project, what was done, and why. One entry per working session, newest at the bottom. Each entry closes with a TODO list for next time; boxes are ticked when a later session completes them.

**Who decides:**
- Bruno makes every decision.
- Claude Code (the builder, working in the repo) proposes options with a recommendation.
- GPT 5.6 luna is used as an independent reviewer and examiner.
- Where a tool shaped a decision, the entry says so.

**Decision IDs (D-001, D-002, …)** are permanent, so the plan, the code and the demo can refer to them. A decision that is changed later gets a new ID that says which one it replaces.

---

## Entry 1 · Friday 16 Oct 2026 · Planning

### What we did
- Read the brief, both primers (knowledge graphs, private markets) and the candidate-pack README in full.
- GPT 5.6 luna wrote a first plan. Claude Code reviewed it against the brief and found it had been written without the brief:
  - it built the property graph first (the brief says RDF first)
  - it assumed a hand-made dataset (the brief needs real public data)
  - it said "don't assume a graph database" (Neo4j is required)
  - it left out most of the deliverables: LLM extraction, entity matching, investor questions, the three-way comparison, the write-up.
- Claude Code wrote a refined plan (`PLAN.md` v2). Bruno accepted all its recommendations.
- Agreed how to use the two AI tools:
  - Claude Code builds.
  - GPT 5.6 luna reviews designs and code, writes its own queries to cross-check ours, and quizzes Bruno for the explain-back.
  - Only one tool ever edits the repo.

### Decisions
- **D-001 · Keep a chronological log of all decisions.**
  - The brief asks for one; the demo and explain-back are built around it.
  - Alternative: full ADRs (architecture decision records). Rejected as heavier than the brief's "short log".
- **D-002 · Build the RDF graph and the property graph in isolation first; the translation layer comes after.**
  - Each model has to be understood and tested on its own before converting between them means anything.
- **D-003 · Make the project visual, with a GUI.**
  - Structure and provenance are easier to show than describe, and the brief requires visual views.
- **D-004 · Every line of code gets a plain-English comment; every file opens with a plain-English summary.**
  - The explain-back happens without code open.
  - Applies to Python, SPARQL, Cypher, TOML, YAML, shell scripts, Makefiles and config.
- **D-005 · Bruno makes every decision; the agent proposes options with a recommendation.**
  - The brief makes the candidate responsible for understanding everything handed in.
- **D-006 · Use `uv` with Python 3.12 and a lockfile.**
  - A reviewer can rebuild the identical environment with one command. 3.12 is the safest version for library support.
  - Alternative: `venv` + `pip` + `requirements.txt`.
- **D-007 · Use Neo4j Desktop, not AuraDB Free.** *(Revised in D-018.)*
  - AuraDB Free caps node and relationship counts, which matters for the large-data timing run. Desktop has Bloom and can run the n10s RDF plugin.
- **D-008 · Focus on UK sponsors, using GLEIF + Companies House.**
  - One register to learn; the PSC records (people with significant control) give ownership links.
  - Alternative: US sponsors with EDGAR.
  - Would revisit if the sponsor check finds too little UK coverage.
- **D-009 · Monday goal: a thin slice that can be explained completely, plus the plan, then ask to continue.**
  - The brief weights the explain-back above coverage, and has no fixed end date.
- **D-010 · Build the GUI on a graph-drawing library, so it counts as the brief's "one other tool".**
  - The add-on then meets a requirement as well.
  - Fallback if Seisa says it doesn't count: a small yFiles view.
- **D-011 · Keep the brief documents out of the repo.**
  - Brief rule: "no Seisa code or data". Covers `brief/` and the extracted text in `docs/brief_text/`.
- **D-012 · Build both graphs from one shared list of facts.**
  - Makes "the same data in two graphs" checkable, and keeps each builder small.
  - Alternative: build the property graph by converting the RDF graph. Rejected because the brief asks for both to be *designed*.
- **D-013 · Tools:**
  - pyoxigraph, with rdflib where it helps
  - our own namespace, plus PROV-O and GLEIF ontology terms
  - a few SHACL rules, checked with pyshacl
  - LLM extraction guided by a schema, with every quote checked against its sentence
  - Neo4j's vector index or local embeddings
  - `make build` as the single command.
- **D-014 · Use the file structure in PLAN.md §4.**
  - Clear separation by pipeline stage.
- **D-015 · The RDF graph records where each fact came from using RDF-star annotations.**
  - Each fact carries its source, record ID and retrieval date (plus the sentence, for facts taken from text).
  - Why: the fact itself stays a plain triple that is easy to query, while still saying where it came from.
  - Alternatives: a named graph per source record; a "claim" resource per fact (one extra hop in every query).
  - Still open: how the property graph records sources. To be decided when it is designed.
- **D-016 · The translation layer is an extension, built after the core task is done.**
  - The two graph builders stay separate, each built from the shared fact list (D-012), with no conversion between them.
  - The extension can then compare an automatic translation against the hand-designed property graph.

### TODO for next time
- [x] Set up the repo, the Python environment and the brief extraction
- [x] Start this decision log
- [ ] Register for a Companies House API key
- [x] Install Neo4j
- [ ] Sponsor check: choose 3 UK sponsors

---

## Entry 2 · Friday 16 Oct 2026 · Setup, part 1

### What we did
- **Repo:** created a git repo in the project folder. The folder had been sitting inside a git repo covering the whole home folder; that repo is left untouched.
- **`.gitignore`:** keeps out the environment (`.venv/`), secrets (`.env`), data (`data/`), the brief (`brief/`, `docs/brief_text/`), Neo4j's program files (`tools/`) and tool caches.
- **Python environment:** Python 3.12.14 via `uv`, with every library from the plan installed. Exact versions are pinned in `uv.lock`; key ones:
  - pyoxigraph 0.5.11
  - rdflib 7.6.0
  - neo4j driver 6.4.1
  - pymupdf 1.28.2
- **Files added:**
  - `pyproject.toml`: the project's list of dependencies
  - `.env.example`: a template naming the secrets we will need
  - `README.md`: setup instructions for someone else
  - `src/seisa_kg/__init__.py`: makes our code importable
- **`scripts/extract_brief.py`:** converts all 5 brief documents to text in `docs/brief_text/`, with a page marker before each PDF page.
- **`tests/test_environment.py`:** 10 tests, all passing.
  - 7 check that each library loads.
  - 3 check that RDF-star works in pyoxigraph.

### Decisions
- **D-017 · The project gets its own git repo.**
  - The brief needs a standalone repo to share with Seisa.

### Findings
- **pyoxigraph 0.5.11 uses the newer RDF 1.2 form of RDF-star.**
  - Annotating a fact creates a hidden *reifier* node, linked to the fact by `rdf:reifies`. The source and date attach to that node.
  - A fact backed by two sources therefore gets two reifiers, each with its own provenance. That suits facts that conflict or repeat.
  - We will read and write RDF-star with pyoxigraph, not rdflib.
  - `tests/test_environment.py` pins this behaviour, so an upgrade that changes it will be noticed.
- **The PDF library prints harmless "deprecation" warnings during tests.** They come from inside the library, not from our code.

### TODO for next time
- [ ] Register for a Companies House API key
- [x] Install Neo4j
- [ ] Sponsor check: choose 3 UK sponsors

---

## Entry 3 · Friday 16 Oct 2026 · Setup, part 2

### What we did
- **Neo4j server inside the project:**
  - `scripts/install_neo4j.sh` downloads Neo4j Community 2026.09.0 into `tools/neo4j/`. It checks the download against Neo4j's published SHA-256 fingerprint before unpacking it.
  - The database and log files live in `data/neo4j/`, so the database is inside the project.
  - The server only accepts connections from this computer.
- **Makefile:** added short commands:
  - `make setup`, `make test`, `make brief`
  - `make neo4j-install`, `make neo4j-start`, `make neo4j-stop`, `make neo4j-status`
- **Started the server:**
  - It runs on Java 25, at `http://127.0.0.1:7474` (browser) and `bolt://127.0.0.1:7687` (code).
  - The password is still Neo4j's default, `neo4j`/`neo4j`. Bruno sets a new one on first login, so the password never passes through the AI tools.
- **Neo4j Desktop:** installed Neo4j Desktop 2 (2.2.1) through Homebrew, for viewing only: Bloom/Explore, connected to the project's server.
- **Decision log:** rewritten as this diary, with bullet points and a TODO list at the end of every entry.
- **GitHub:** made the first commit and pushed it to the private repo `seisa-kg-trial`.

### Decisions
- **D-018 · Run Neo4j as a server inside the project, with Neo4j Desktop installed only as a viewer.** *(Replaces D-007.)*
  - Why:
    - the database lives in the repo folder
    - a reviewer can recreate it with `make neo4j-install`
    - the build can start and stop it from scripts
    - Desktop still gives us Bloom for the brief's required visual view.
  - Alternatives:
    - the server only, without Bloom
    - Desktop only, where the database lives in the app's own folder rather than the project.
  - Would revisit if Desktop can't connect to the project's server for Bloom.
- **D-019 · Host the code in a private GitHub repo called `seisa-kg-trial`, under Bruno's account.**
  - The brief asks for a repo under our own account, shared with Seisa for review. Private until it is shared.
- **D-020 · Commits never list Claude as a co-author or contributor.**
- **D-021 · Create the `.env` file only when a key or password is first needed.**
  - Bruno holds the LLM key and will share it when the extraction work starts.
- **D-022 · Keep this file as a diary: one entry per session, bullet points, a TODO list at the end of each entry.**

### Findings
- **Neo4j rejects folder paths that contain `..`** ("not a normalized path"). The install script now writes the project's full path into Neo4j's settings instead.
- **Neo4j 2026.09.0 runs on the Java 25 already installed** on this Mac, so no extra Java install was needed.

### TODO for next time
- [ ] **Bruno:** register for a Companies House API key (steps in the chat)
- [ ] **Bruno:** open `http://localhost:7474`, log in as `neo4j`/`neo4j`, and choose a new password
- [ ] **Bruno:** in Neo4j Desktop, add a connection to `bolt://localhost:7687` and check that Explore (Bloom) opens
- [ ] When the first key is needed: `cp .env.example .env` and fill it in
- [ ] Sponsor check: search GLEIF for candidate UK sponsors, count entities and parent links, choose 3
- [ ] Sunday: design the RDF schema, starting from the sponsor-check results

---

## Entry 4 · Friday 16 Oct 2026 · Sponsor check

### What we did
- Wrote `scripts/sponsor_check.py`. For 6 candidate UK sponsors it:
  - searches GLEIF by name
  - caches every reply in `data/raw/gleif/sponsor_check/`
  - counts what the records say.
- Results are saved in `docs/sponsor-check.md`.
- Ran it against GLEIF's data for 16 Oct 2026. It made 9 requests, all paced under GLEIF's limit of 60 per minute.

### Findings

| Sponsor | Entities | Funds | With a Companies House number | Report a parent | Give a reason for no parent | Fund-manager links | Main countries |
|---|---|---|---|---|---|---|---|
| Permira | 147 | 35 | 7 | 5 | 141 | 16 | LU, GG, GB |
| Cinven | 66 | 5 | 15 | 1 | 65 | 3 | GG, GB, LU |
| Hg | 104 | 3 | 81 | 0 | 104 | 1 | GB, GG, LU |
| Bridgepoint | 202 | 14 | 66 | 1 | 193 | 5 | LU, GB, IE |
| Apax | 177 | 70 | 14 | 2 | 173 | 65 | GG, LU, GB |
| Inflexion | 57 | 2 | 2 | 2 | 55 | 2 | GG, GB, KY |

- **GLEIF records almost no parent links for sponsor entities:** 0–5 per sponsor. Nearly all of them give a *reporting exception*, a stated reason for naming no parent.
  - This matches the brief's warning, and the primer's point that funds don't consolidate the companies they own.
  - Consequence: the ownership structure has to come from **Companies House PSC records**, **GLEIF fund-manager links** and **news releases**, not from GLEIF parent links.
  - The exceptions themselves must be stored as facts.
- **Name search finds some look-alikes:** 2–17 per sponsor, e.g. US property LLCs in the Bridgepoint search.
  - Some look-alikes are actually useful: deal vehicles that matched on an address or another field, e.g. "ACORN BIDCO LIMITED" in the Hg search.
- **Each sponsor's strength:**
  - Hg (81) and Bridgepoint (66) have the most UK Companies House entities.
  - Apax has the most fund-manager links (65), so GLEIF itself shows its fund → manager structure.
  - Permira and Inflexion are mostly offshore (Luxembourg, Guernsey), with little in Companies House.

### Decisions
- **D-023 · The project's three sponsors are Hg, Bridgepoint and Apax** (about 480 GLEIF entities before cleaning).
  - Decided by Bruno, on Claude Code's recommendation from the sponsor check.
  - Hg and Bridgepoint give Companies House depth.
  - Apax gives GLEIF fund-manager structure.
  - Together they show both the strengths and the gaps of each source.
  - Alternative considered: swap Apax for Cinven (about 370 entities). Not chosen, because Cinven has few fund-manager links.
  - Would revisit if: any of the three has too few public news releases, or the entity count proves too large to check by hand.

### TODO for next time
- [x] **Bruno:** choose the 3 sponsors (D-023)
- [x] **Bruno:** register for a Companies House API key (done; the key is kept out of git and out of the chat)
- [x] **Bruno:** set the Neo4j password at `http://localhost:7474` (done; the password is in `.env`, and the Python driver logs in successfully)
- [x] **Bruno:** connect Neo4j Desktop to `bolt://localhost:7687` (done)
- [ ] Look up the reporting-exception reasons for a sample of entities (`NON_CONSOLIDATING`, `NATURAL_PERSONS`, …), to inform the RDF schema
- [ ] Check that each chosen sponsor has enough public news releases (about 10 each)
- [ ] Sunday: sketch the RDF schema

### End of day (Friday 16 Oct)

**Secrets and access, all in `.env`, which git ignores (D-021):**
- **Companies House API key:** registered by Bruno, and typed into `.env` by Bruno.
- **Neo4j password:**
  - Set by Bruno at `http://localhost:7474`; the Python driver logs in with it successfully.
  - Bruno later pasted it into the Claude Code chat to check its format, so it has passed through an AI tool.
  - The risk is low, because Neo4j only accepts connections from this computer. Change it if it is reused anywhere else.
  - Format note: the value starts with `#`. That works in `.env`, but there must be no space after the `=`, or the value is read as a comment.
- **Gemini key:** see D-024 below.

**Neo4j Desktop:**
- Connected to the project's server at `bolt://localhost:7687`. This confirms the set-up in D-018 works.
- Explore (Bloom) has not been opened yet.

**Decisions:**
- **D-024 · The LLM provider is Google Gemini.**
  - The key came from the earlier exercise's `.env` (`~/Downloads/excel-kg-exercise`, where it was named `LLM_GOOGLE_API_KEY`).
  - Claude Code copied it into this project's `.env` as `LLM_API_KEY`, without printing it; it was never committed.
  - **Checked:**
    - the key can list 46 text models, including `gemini-2.5-flash`, `gemini-3.5-flash` and `gemini-3.1-pro-preview`
    - a one-line test prompt to `gemini-2.5-flash` worked (6 tokens).
  - Which model to use for extraction is decided when extraction starts.
  - **Still to confirm with Seisa:** that this key is meant for this trial, and what its spending limit is.

**State at close:**
- 9 commits pushed (counting this correction) to the private repo `brunohawkins/seisa-kg-trial`, all under Bruno's name only (D-020).
- 10 setup tests passing.
- Neo4j is stopped with `make neo4j-stop`.

### TODO for Sunday
- [ ] `make neo4j-start`, and open Explore (Bloom) in Neo4j Desktop once to check it works
- [ ] Confirm with Seisa: is the Gemini key meant for this trial, and what is its spending limit?
- [ ] Sample GLEIF's reporting-exception reasons for Hg, Bridgepoint and Apax
- [ ] Check there are about 10 public news releases per sponsor
- [ ] Sketch the RDF schema together (RDF-star provenance, D-015)
- [ ] Build the cached GLEIF downloader for the three sponsors
- [ ] Fix the `.env.example` comments, which still describe Neo4j Desktop as the database (D-018 changed this)

---

## Entry 5 · Sunday 18 Oct 2026 · Data sources and pipeline (1pm session)

### What we did
- **`.env` is complete:** all 5 settings are filled in, checked without displaying any values.
- **Revised today's plan for the 4 hours available** (1pm–5pm, instead of the ~10 planned):
  - the goal is one thin slice, from start to finish, using GLEIF only
  - Companies House PSC data moves to Monday.
  - Timeline knock-on: the brief is now expected around **Thu 22 Oct**, and the GUI and translation layer around **Mon 26 Oct**.
- **Bruno studied the three data sources** (GLEIF, Companies House, press releases) and wrote them up as a mind map in a notebook.
  - Corrected: we use Companies House, not EDGAR. EDGAR is the US register, ruled out by D-008.
- **Agreed the pipeline stages** below, as a shared reference.
  - Bruno keeps dated, hand-drawn schematics of the pipeline in a notebook, so the workflow itself is snapshotted over time.

### Pipeline stages (v1, 18 Oct)
0. **Configure:** the sponsors and their search words.
1. **Fetch:** download from each source and cache the raw replies in `data/raw/`.
2. **Parse:** turn the raw replies into the shared fact list (D-012), with provenance on every fact.
3. **Link:** decide which records describe the same entity.
   - by identifier first (D-025)
   - then by name, for the news releases.
4. **Build:** the RDF graph (RDF-star, checked with SHACL) and the Neo4j graph, each built separately from the fact list.
5. **Query:** the investor questions in SPARQL and in Cypher, with answers, sources and timings.
6. **Ask:** text-to-SPARQL, text-to-Cypher and vector search, scored against the answers from stage 5.
7. **Show:** Bloom, the GUI and the write-up.
- *Extension (D-016):* a translation layer between the two graphs built in stage 4.

### Decisions
- **D-025 · Link GLEIF and Companies House records by registration number, not by name.** *(Bruno's realisation.)*
  - **The rule:** two records are the same entity when the GLEIF record's register is Companies House (`registeredAt.id = RA000585`) **and** its `registeredAs` equals the Companies House company number.
  - **Why both conditions:**
    - Registration numbers are only unique *within one register*. Luxembourg also uses numbers like `B281103`.
    - An exact identifier match avoids the over-merging that name matching risks.
  - **Linking, not merging:**
    - Both sources' facts attach to one entity, and each fact keeps its own source.
    - Values that disagree are kept side by side, never overwritten. Example: GLEIF's `HG SATURN A L.P.` against a differently capitalised name in Companies House.
  - **Checked against our cached GLEIF data:** 185 sponsor entities are registered at Companies House, all with properly formatted 8-character numbers:
    - 140 `LP…` (English limited partnerships, i.e. mostly funds)
    - 38 ordinary companies
    - 5 `OC…` (LLPs)
    - 2 `SL…` (Scottish LPs).
    - All already zero-padded, so no reformatting is needed. We still normalise (upper case, pad to 8) as a safety check.
  - **Limits:**
    - Only UK entities that also have an LEI.
    - Companies House entities with no LEI (many BidCos and portfolio companies) are identified by their company number alone.
    - Offshore entities are identified by their LEI alone.
  - **Bonus:** the companies that Companies House lists as owners in PSC records come with their own registration numbers, so ownership links can be resolved by identifier too.
  - **Would revisit if:** numbers turn out to be missing or inconsistent once the Companies House data is downloaded.

### Findings
- **Most UK fund vehicles are English limited partnerships** (`LP…`, 140 of the 185).
  - To check on Monday: English LPs have historically filed very little with Companies House, and may have no PSC records.
  - If so, the ownership chains will come from the *companies* (TopCo, BidCo, …) rather than from the funds.

### TODO for next time (today, after the schematic)
- [x] Warm-up: fix the `.env.example` comments; sample GLEIF's reasons for "no parent" and its fund-manager links (done; see below)
- [ ] Bruno: open Explore (Bloom) in Neo4j Desktop once to check it works
- [ ] RDF schema sketch together (`docs/schema/rdf-schema.md`)
- [ ] GLEIF downloader → shared fact list → RDF builder with SHACL checks
- [ ] Bruno: write the first 3 investor questions; answer them in SPARQL with sources
- [ ] Property-graph schema, including how it records sources (still open); Neo4j builder; the same 3 questions in Cypher
- [ ] `make build`; one Bloom view tracing a fact to its source; diary entry; commit
- [ ] Monday: Companies House downloader, linked by D-025; check PSC coverage for English LPs

### Warm-up (about 2pm)

#### What we did
- **Pipeline stage 0:** `config/sponsors.toml` lists Hg, Bridgepoint and Apax with their search words. Python reads it with its built-in TOML reader, so no extra library is needed.
- **Pipeline stage 1:** `src/seisa_kg/sources/gleif.py` is the reusable GLEIF fetcher.
  - It caches every reply in `data/raw/gleif/` inside an envelope: `url`, `retrieved_at`, `status`, `body`.
  - It saves "not found" replies too, so the same question is never asked twice.
  - It stays under GLEIF's limit of 60 requests per minute.
  - This is the start of Monday's full downloader.
- **`scripts/gleif_warmup.py`:**
  - samples up to 20 "no parent" reasons per sponsor
  - fetches every actual parent
  - fetches every fund-manager relationship, and each manager's name.
  - It took about 3 minutes; the report is in `docs/gleif-warmup.md`.
- **`docs/data-sources.md`:** the data-source notes, findings F1–F8, and what they mean for the schema.
- **`.env.example`:** comments fixed, so they now describe the project's own Neo4j server (D-018).

#### Findings (details in `docs/data-sources.md`)
- **F3 · Why there's no parent:** of 60 sampled, 50 are `NON_CONSOLIDATING`, 7 `NO_KNOWN_PERSON` and 3 `NATURAL_PERSONS`. Only 3 actual parents across all three sponsors.
- **F4 · GLEIF's "fund manager" mixes two roles:** GP companies (e.g. Apax Digital II GP Co., 35 funds) and regulated management companies (e.g. Apax Management Luxembourg). Don't assume "fund manager = GP".
- **F5 · Outside companies:** some Bridgepoint and Hg funds are managed by outside companies (Yacktman, Amchor, Gen II, Universal-Investment). These are look-alikes or outsourced managers, so we need a rule for which entities belong to a sponsor.
- **F6 · Time and quality:** relationships carry start dates, a status and a corroboration level. One start date (1974) looks wrong; we store it as given.
- **F7 · GLEIF changes daily:** Hg had 104 entities on Friday and 105 today.
- **F8 · Hg's structure** must come from Companies House.

#### Decisions
- None yet. The findings feed the schema session, where Bruno decides.

#### TODO (next: schema session)
- [ ] Bruno: open Explore (Bloom) once
- [ ] Decide how "no parent, for reason X" is stored
- [ ] Decide how GP and manager roles are assigned (F4)
- [ ] Decide the rule for which entities belong to a sponsor (F5)
- [ ] Sketch the shared fact format and the RDF schema in `docs/schema/rdf-schema.md`

### Schema session, part 1 (about 2:30pm)

#### The strategy for the warm-up issues (proposed by Claude Code; **confirmed by Bruno as D-029**)
- **The issues are not bugs to fix.** They are what the sources actually say.
- **Principle:**
  - Record exactly what each source says, with its source and the date it was fetched.
  - Never silently "correct" a source.
  - Our own judgements (scope, roles, matches) are **separate facts**, labelled as ours, each with its reason.
- **Why:**
  - Every fact stays traceable.
  - Mistakes in our own judgement can be undone without touching the source facts.
  - The explain-back can separate "the register says" from "we concluded".

#### Decisions
- **D-026 · "No parent" is stored as a fact on the entity:** *reason, source, date fetched.*
  - Example: "Fund A: no reported direct parent; reason `NON_CONSOLIDATING`; source: GLEIF record; fetched 18 Oct 2026".
  - **Why:** the information stays in the graph rather than becoming a silent gap, as the brief asks ("represent these gaps openly").
  - **Why:** if GLEIF later changes the reason, a re-fetch adds a new fact with a new date. The old one stays, so we have the before and after.
  - **Refinements:**
    - Store direct and ultimate parents separately; GLEIF reports each one.
    - Store whatever reason code GLEIF gives, rather than a fixed list, so new codes still work.
  - In the RDF graph, the source and date go in RDF-star annotations (D-015).
- **D-027 · No roles (GP, manager) until Companies House or the news confirms them.**
  - **Why:** GLEIF's "fund manager" mixes GP companies and regulated management companies (F4). Guessing a role risks a wrong fact.
  - **Why:** a role confirmed by two sources is richer and more defensible.
  - **Refinement (confirmed by Bruno):** still store GLEIF's own link exactly as GLEIF states it ("managed by, per GLEIF", with its start date, status and corroboration level), but *not* as a role.
    - Why: it is a real, sourced fact; leaving it out would lose information.
    - Roles are added later as separate facts, each with its own source.

#### Findings
- **F9 · What the name search actually caught** (GLEIF searches for the three sponsors, 18 Oct):
  - **Name contains the sponsor:** Hg 99 of 105, Bridgepoint 185 of 202, Apax 140 of 177.
  - **Name contains the sponsor, but managed by an outside company:** 4 in total. These look like *feeder or access funds* that outside platforms run into the sponsor's funds:
    - Nucleus HG GENESIS 10 (Universal-Investment)
    - BRIDGEPOINT PRIVATE EQUITY FCR (Amchor)
    - BRIDGEPOINT DIRECT LENDING I (Gen II)
    - APAX DEVELOPMENT FUND II BY PEQAN (Peqan).
  - **Name doesn't contain the sponsor:** 60 in total, matched on another field:
    - **"Care of" the sponsor's address (48):** includes **real deal vehicles**:
      - ACORN BIDCO LIMITED, c/o HgCapital
      - Janus Topco / Midco / Bidco Limited, c/o Apax: a classic acquisition chain
      - Moon Founder GP Co. Limited
      - Nyudden Invest AB, c/o Bridgepoint AB.
    - **Look-alikes:** US LLCs at "225 Bridgepoint **Drive**"; a Greek company named ΑΠΑΞ.
    - **A former or other name (10):** e.g. SEVEN2 (formerly Apax Partners France, now a separate firm), ASPER RENEWABLE POWER PARTNERS (formerly Hg), CAMELOT BIDCO and MAPIL BIDCO (former Bridgepoint names).
  - **Lesson:** a rule that only checks names would throw away the acquisition chains we most want.
- **F10 · Infrastructure problem: the project sits in an iCloud-synced Desktop.**
  - iCloud marks files in `.venv` as *hidden*, and Python 3.12 skips hidden `.pth` files. So `import seisa_kg` fails at random, whenever the package is rebuilt.
  - iCloud is also syncing the **live Neo4j database** in `data/neo4j/`, which risks corruption. The database is still empty, so nothing is lost.
  - Work-around for now: `PYTHONPATH=src`. Fix: Bruno to decide (see the TODO list below).

#### The rule for which entities belong to a sponsor (**confirmed by Bruno as D-028**)
- Every entity gets an explicit **scope fact**: *in*, *review* or *out*, with the reason.
- **In:**
  - the legal name contains the sponsor's name, **or**
  - the address is "care of" a sponsor entity (e.g. "c/o Apax Partners", "HgCapital, 2 More London").
- **Review** (Bruno decides by hand; about 16 entities):
  - managed by an outside company (4)
  - matched only on a former or other name (10)
  - matched on some other field (2).
- **Out:** the sponsor's word appears only in a street name ("Bridgepoint Drive"), or the match is unrelated (ΑΠΑΞ).
- **Why:**
  - It keeps the acquisition chains.
  - It drops obvious noise.
  - It sends borderline cases to a person (the primer: "merge conservatively, record the evidence, send borderline cases to a person, make it reversible").
  - Every decision can be explained and undone.

#### TODO
- [x] Bruno: confirm the strategy principle above (D-029)
- [x] Bruno: confirm the D-027 refinement (store GLEIF's link as stated, without a role)
- [x] Bruno: decide the scope rule (D-028)
- [x] Bruno: decide the iCloud fix (F10): the project is moved out of iCloud (D-030)
- [ ] Bruno: open Explore (Bloom) once
- [ ] Then: shared fact format and RDF schema sketch (`docs/schema/rdf-schema.md`)

### Schema session, part 2: decisions confirmed and the project moved (about 2:45pm)

#### Decisions
- **D-027 refinement accepted: store GLEIF's fund-manager link exactly as GLEIF states it, but not as a role.**
  - What it records: "managed by, per GLEIF", with its start date, status and corroboration level as annotations.
  - Why: it is a real, sourced fact, and leaving it out would lose information.
  - Why: a role (GP or manager) is only added once Companies House or the news confirms it, as a separate fact with its own source.
- **D-028 · Every entity gets a scope fact (in, review or out) with a reason.**
  - **In:** the legal name contains the sponsor's name, or the address is "care of" a sponsor entity.
  - **Review:** borderline cases, about 16, decided by Bruno by hand:
    - managed by an outside company
    - matched only on a former or other name
    - matched on some other field.
  - **Out:** the sponsor's word appears only in a street name, or the match is unrelated.
  - Why: a name-only rule would throw away the acquisition chains we most want (e.g. Janus Topco / Midco / Bidco, c/o Apax).
  - Why: it drops obvious noise without hiding any decision, since each one is stored with its reason.
  - Why: borderline cases go to a person, the primer's standard practice ("merge conservatively, record the evidence, send borderline cases to a person, make merges reversible").
  - Why: every decision can be explained in the demo and undone later.
- **D-029 · Strategy: record exactly what each source says; never silently correct it; our own judgements are separate, labelled facts.**
  - "Our own judgements" covers scope, roles and matches.
  - Why: every fact stays traceable to its source.
  - Why: our own mistakes can be undone without touching the source facts.
  - Why: in the explain-back, "the register says" stays clearly separate from "we concluded".
- **D-030 · Move the project out of iCloud, to `~/Projects/seisa-kg-trial`, with a shortcut at the old location.**
  - The shortcut is a symbolic link at `~/Desktop/Work/Seisa/Starting project`.
  - Why: iCloud was hiding files in the Python environment, which broke imports at random (F10).
  - Why: iCloud was also syncing the live Neo4j database, which risks corrupting it.
  - Why the home folder: iCloud only syncs Desktop and Documents, so `~/Projects` is never uploaded.
  - Why that name: it matches the GitHub repo, and has no spaces in the path.
  - Why the shortcut: the work stays reachable from the Work folder on the Desktop. iCloud does not follow the shortcut, so nothing in the project is uploaded.
  - Backup: GitHub, not iCloud.

#### What we did (the move)
- Stopped Neo4j, moved the folder, and created the shortcut.
- Cleared the "hidden" flags iCloud had set on the project's files.
- Rebuilt `.venv` from `uv.lock` in the new location.
- Updated Neo4j's two folder paths in `tools/neo4j/conf/neo4j.conf` to the new location.
  - `scripts/install_neo4j.sh` now uses `pwd -P`, so a fresh install always records the real location, never the shortcut.
- **Checked:**
  - `import seisa_kg` works with no work-around
  - all 10 tests pass
  - Neo4j starts, and accepts the password from `.env`
  - the GitHub remote is unchanged.
- **Note:** `.env` (with the keys) sat in the iCloud-synced folder from 16 to 18 Oct. It is Bruno's own private iCloud, so the risk is low. iCloud may keep old copies in its version history.

#### TODO
- [x] Bruno: reopen VS Code at `~/Projects/seisa-kg-trial` (superseded by D-031; now open at `~/Work Projects`)
- [ ] Bruno: open Explore (Bloom) once
- [ ] Bruno: decide the ~16 "review" entities once the scope step lists them
- [ ] Next: the shared fact format and the RDF schema sketch (`docs/schema/rdf-schema.md`)

### Folder layout, revised (about 3pm)

#### Decisions
- **D-031 · The real working folder is `~/Work Projects`. The Desktop's `Work` is now a shortcut to it.** *(Updates D-030.)*
  - The project lives at `~/Work Projects/seisa-kg-trial`.
  - `~/Desktop/Work` is a symbolic link to `~/Work Projects`.
  - Why: Bruno wants one "Work" entry point on the Desktop for all work projects, while keeping the files out of iCloud.
  - Why a shortcut: clicking `Work` on the Desktop opens the real folder, and iCloud does not follow shortcuts, so nothing inside is uploaded.
  - Trade-off: everything in `~/Work Projects` is local only. The code is backed up on GitHub; anything else there (notes, PDFs) needs Time Machine or another backup.

#### What we did
- Bruno renamed `~/Projects` to `~/Work Projects`, which broke the earlier shortcut and the stored paths.
- **Fixed the paths:**
  - Stopped Neo4j, and pointed its two folder paths at `~/Work Projects/seisa-kg-trial`.
  - Rebuilt `.venv` in place with `uv venv --clear` + `uv sync`. `uv`'s command files now start with `#!/bin/sh` rather than a fixed path, so the environment survives future renames.
- **Desktop:**
  - Moved the old `Desktop/Work` folder to the Bin as "Work (old Desktop folder, 18 Oct)". It held only the broken shortcut, an empty "Starting project 2" folder and the custom folder icon.
  - Put a `Work` shortcut in its place.
- **Left in place:** `~/Projects` still exists as an ordinary folder, holding only Claude Code's placeholder file `seisa-kg-trial/.claude-placeholder`.
  - Claude Code created it to get its shell working again after the rename.
  - A safety check blocked Claude Code from deleting it while the session was using it as its working folder, so Bruno deletes it by hand.
  - Nothing else is in it.
- **Checked:**
  - all 10 tests pass
  - `import seisa_kg` works
  - Neo4j starts and accepts the password
  - the GitHub remote is unchanged.

#### Findings
- **F11 · Renaming the project folder breaks two things**, which then need updating:
  - the Neo4j paths in `tools/neo4j/conf/neo4j.conf`
  - the Python environment (fixed for good by the rebuild).
  - Rule from now on: **rename or move the project only via Claude Code, or tell it first.**

#### TODO
- [x] Bruno: delete the `~/Projects` folder in Finder. It only holds Claude Code's placeholder file.
- [ ] Bruno: if wanted, re-apply the custom Work icon to `~/Work Projects` (Finder → Get Info → paste the icon onto the folder icon)
- [x] Bruno: reopen VS Code at `~/Work Projects/seisa-kg-trial` (or through Desktop → Work)
- [ ] Next: RDF schema sketch

### Handover set-up (about 3:10pm)

#### Decisions
- **D-032 · Add a `CLAUDE.md` to the repo, and copy Claude Code's memory notes to the new folder's memory store.**
  - Why: this chat is filed under the old folder name, so a new Claude Code session in `~/Work Projects/seisa-kg-trial` would not see it.
  - Why: the memory notes were stored under the home folder, back when the whole home folder was one git repo, so a new session would not load them either.
  - Why: `CLAUDE.md` is read automatically in this folder. It carries the working rules, and points every new session to the diary and the plan.
  - Why it is in the repo: Seisa will see it. That is fine, because the brief encourages AI tools, and the file shows how they were used.

#### TODO
- [x] Bruno: keep this VS Code window open for the rest of today; start the next session from Desktop → Work → `seisa-kg-trial`
- [ ] Next: RDF schema sketch (`docs/schema/rdf-schema.md`)

### RDF schema decisions (afternoon, new session in `~/Work Projects`)

#### Decisions
- **D-033 · The shared fact list is one row per fact, all with the same fields.** *(Details D-012 left open.)*
  - Fields: subject, predicate, object, extra details (e.g. start date, status), and origin.
  - The origin is either a **source record** (URL, date fetched) or **one of our rules** (e.g. D-028).
  - Why: both builders loop over one list, so each stays small.
  - Why: "the same data in both graphs" becomes a count per predicate.
  - Alternative not chosen: one Python class per kind of fact. Easier to read one kind at a time, but more code and no single loop.
- **D-034 · Entities are named by their identifier: `lei:<LEI>` or `ch:<company number>`.**
  - The D-025 match between an LEI and a Companies House number is a **separate link**, labelled as made by our rule D-025.
  - Why: D-029 counts matches as our own judgement, so a wrong match can be undone without renaming anything.
  - Cost: questions that span both sources need one extra hop.
  - Today only GLEIF data exists, so this starts to matter on Monday.
  - Alternative not chosen: one node per real-world entity holding both identifiers. Simpler queries, but the match is baked into the graph.
- **D-035 · Each fact's RDF-star annotation points to a `SourceRecord` node.** *(Refines D-015.)*
  - The node holds the source, the URL and the date fetched. Every fact from the same GLEIF record shares it.
  - Why: fact → source record is a path you can see and draw, which the brief asks for.
  - Why: it matches the planned `SourceRecord` node in Neo4j, so the two graphs tell the same story.
  - Why: you can ask "what did this one record tell us?"
  - Alternative not chosen: the URL and date written directly on every annotation. Fewer nodes, but repeated values and nothing to query.
- **D-036 · Our scope judgements (D-028) are `ScopeDecision` nodes.**
  - Each node holds the entity, the sponsor, the verdict (in, review or out), the reason, and "made by rule D-028".
  - Why: it is a statement about five things, not two.
  - **General rule from this:** a fact between two things is a triple with an RDF-star annotation; a fact about several things is a node. Deals (buyer, target, date, advisers) will be nodes for the same reason.
  - Alternative not chosen: a "belongs to sponsor" triple carrying the verdict. A "belongs to" triple with the verdict "out" contradicts itself.

#### TODO
- [x] Bruno: read `docs/schema/rdf-schema.md` and confirm or change the points marked **Proposed** (all confirmed: D-037)
- [ ] Bruno: open Explore (Bloom) once
- [ ] Next: GLEIF data → shared fact list → RDF builder (check first whether SHACL can see RDF-star annotations; see the sketch's risks)
- [ ] Bruno: write the first 3 investor questions
- [ ] Bruno: decide the ~16 "review" entities once the scope step lists them

#### Decisions (later the same afternoon)
- **D-037 · Bruno confirmed the four points marked Proposed in the RDF schema sketch.**
  - **Names:** our own namespace, `https://seisa-kg.example/…` (`ex:`, `lei:`, `ch:`, `src:`); one `SourceRecord` per LEI, per kind of reply, per fetch date.
    - Why: `.example` is reserved, so it can never clash with a real site, and it is easy to change.
  - **No `ex:Fund` class:** GLEIF's `FUND` / `GENERAL` category is a sourced value, `ex:gleifCategory`.
    - Why: "this is a fund" is GLEIF's claim, not ours (D-029).
    - Real example: *Apax XII USD GP L.P. Inc* has "GP" in its name, but GLEIF's category for it is `FUND`. A class would have hidden that tension.
  - **Address as one line of text** for now.
    - Why: the only use so far is the "care of" scope test (D-028), which reads it as text.
  - **Hand decisions on "review" entities** create a new `ScopeDecision` (made by `ex:rule/manual-review`) linked to the automatic one by `prov:wasRevisionOf`.
    - Why: the history stays visible, and the change can be undone.

#### TODO
- [ ] Bruno: copy the schema, one example per type, into the notebook
- [ ] Bruno: open Explore (Bloom) once
- [x] Test SHACL on RDF-star annotations first (done: see F12)
- [ ] Next: GLEIF data → shared fact list → RDF builder
- [ ] Bruno: write the first 3 investor questions

### RDF schema at a glance: one example per type (for the notebook)

All the examples are real Apax entities from the GLEIF cache (fetched 18 Oct 2026). The full sketch is in `docs/schema/rdf-schema.md`.

#### The two rules everything follows
1. **A fact between two things is a triple with an annotation. A fact about several things is a node.** (D-036)
2. **Every fact says where it came from** (D-029):
   - from a source: `prov:wasDerivedFrom` → a **SourceRecord**
   - from us: `prov:wasGeneratedBy` → one of our **Rules**.

#### A. The things (nodes)

**1. LegalEntity**
```
lei:<LEI>  a ex:LegalEntity
e.g. lei:894500C7AD948MWIA623      (Apax Digital II GP Co. Limited)
```
- Why: it's named by its identifier, not its name (D-034). Names differ between sources; identifiers don't.
- The node itself holds almost nothing. Everything about it is a sourced fact (see B).
- From Monday, a Companies House number becomes its own node `ch:<number>`. Our rule D-025 links it to the LEI node, so a wrong match can be undone.

**2. Sponsor**
```
ex:sponsor/<key>  a ex:Sponsor ;  label ;  search terms
e.g. ex:sponsor/apax   "Apax"   searched with "Apax"
```
- Why: a sponsor is a brand, not a legal entity. "Apax" has no single LEI, so it gets its own type.
- Entities connect to a sponsor only through a ScopeDecision (5).

**3. SourceRecord**
```
src:gleif/<LEI>/<kind>/<date>  a ex:SourceRecord ;  source ;  url ;  retrievedAt
e.g. src:gleif/894500AOGUG91SHOC845/direct-parent-exception/20261018
       source  GLEIF
       url     https://api.gleif.org/api/v1/lei-records/894500AOGUG91SHOC845/direct-parent-reporting-exception
       fetched 2026-10-18 13:03 UTC
```
- Why (D-035): one node is shared by every fact from that reply. So "fact → source" is a path you can see and draw, which the brief asks for.
- It has the same shape as the planned SourceRecord in Neo4j.
- Why the date is in the name: GLEIF changes daily (F7). A re-fetch makes a new record, and the old one stays, so you keep both the before and the after.

**4. Rule**
```
ex:rule/<D-id>  a ex:Rule ;  label ;  description
e.g. ex:rule/D-028   "Scope rule: in / review / out"
```
- Why: our own judgements need an origin too. Pointing at a named rule keeps "the register says" separate from "we concluded", and the rule's own text sits in the graph.

**5. ScopeDecision**
```
ex:scope/<sponsor>/<LEI>  a ex:ScopeDecision
    entity · sponsor · verdict (In/Review/Out) · reason · generatedBy rule
e.g. ex:scope/apax/894500H5QJCD6LESMR63
       entity   lei:894500H5QJCD6LESMR63   (Apax Digital II Co-Investment L.P.)
       sponsor  ex:sponsor/apax
       verdict  ex:In
       reason   "legal name contains 'Apax'"
       made by  ex:rule/D-028
```
- Why (D-036): this fact involves five things, not two, so it's a node.
- A "belongs to sponsor" triple carrying the verdict "Out" would contradict itself.
- When Bruno decides a Review case by hand: a new decision is made by `ex:rule/manual-review` and linked back with `prov:wasRevisionOf`. The history stays visible (D-037).

#### B. The facts (triple + annotation → SourceRecord)

**6. Value fact: a property with a plain value**
```
lei:894500AOGUG91SHOC845  ex:legalName      "Apax XII USD GP L.P. Inc"  {| from src:…/record/20261018 |}
lei:894500AOGUG91SHOC845  ex:gleifCategory  "FUND"                      {| from src:…/record/20261018 |}
```
- Why no `Fund` class (D-037): this entity has "GP" in its name, but GLEIF's category for it is `FUND`.
  - With a class, the graph would just say "it's a fund", as if we had decided it.
  - As a sourced value, it reads "GLEIF says FUND", and the tension stays visible.

**7. Link fact: a relationship between two entities**
```
lei:894500H5QJCD6LESMR63  ex:fundManagedBy  lei:894500C7AD948MWIA623
   {| from src:…/fund-manager/20261018 ;
      startDate 2021-01-17 ;  status ACTIVE ;  corroboration FULLY_CORROBORATED |}
(Apax Digital II Co-Investment L.P.  →  Apax Digital II GP Co. Limited)
```
- Why a triple: it links two things.
- Why the details go on the annotation (RDF-star, D-015): the start date, status and corroboration describe *the link*, not either entity.
- Why there's no "GP" role (D-027): the manager's name says "GP Co.", but GLEIF only says "fund manager". The role waits for a second source.

**8. Gap fact: "no parent, for this reason"**
```
lei:894500AOGUG91SHOC845  ex:directParentException  "NON_CONSOLIDATING"
   {| from src:gleif/894500AOGUG91SHOC845/direct-parent-exception/20261018 |}
```
- Why (D-026): the brief asks for gaps to be shown openly. A missing edge says nothing; this fact says why there's no parent and who said so.
- The reason code is stored as given, so new codes still work.

#### Still open
- Where the Sponsor nodes' facts say they came from. They come from our config file, not a source. Suggestion: point them at the rule for the sponsor choice, `ex:rule/D-023`. Decide at the builder step.

### Builder step, part 1: checking the risk and starting the download

#### Findings
- **F12 · rdflib 7.6 can't read RDF 1.2 annotations, so pyshacl can't check them.**
  - rdflib rejects the RDF-star syntax, in both Turtle and N-Triples.
  - **It fails silently:** pyshacl was handed an empty graph and reported "Conforms: True", because an empty graph breaks no rule.
  - Oxigraph's SPARQL sees the annotations: a test query found the one annotation we had planted with no source.
  - Lesson for the explain-back: **a check that passes on nothing is worse than no check.**
- **The search replies already say what to fetch.** Each cached GLEIF search record links to either its parent's relationship record or its reporting exception. So the downloader follows GLEIF's own links and never guesses.
  - 484 unique entities across the three sponsors.
  - **Direct parent:** 3 actual parents, 471 exceptions, 10 with no link at all.
  - **Ultimate parent:** 5 actual parents, 469 exceptions, 10 with no link at all.
  - 71 fund-manager links.
  - The 10 with no link at all are a third case, different from "no parent, for reason X". To be looked at once the data is in (F13).

#### Decisions
- **D-038 · Checks: SHACL for the parts it can see, plus one SPARQL check for the annotations.** *(Adjusts D-013.)*
  - pyshacl checks the parts with no annotations: entities have a name; SourceRecords and ScopeDecisions have all their fields.
  - A SPARQL query in Oxigraph checks that every annotation has a source.
  - The build also fails if the graph is empty, so the silent pass in F12 can't happen.
  - Why: it keeps SHACL (D-013) wherever it works, and the tool's limit becomes an honest finding for the write-up.
  - Alternatives not chosen: every check in SPARQL (simpler, but drops SHACL); a Java SHACL engine (a second language, for an optional check).
- **D-039 · Download GLEIF Level 2 for all three sponsors today, not a sample.**
  - 1,019 replies, 131 already cached, so 888 to fetch, about 16 minutes at GLEIF's 60 per minute, run in the background.
  - Why: the scope rule (D-028) and the investor questions need all three sponsors anyway.
  - Why not only the cache: just 60 entities had their exception cached. The other 424 would have looked as if they had no information, which is the silent gap D-026 avoids.
  - Command: `make fetch-gleif` (`src/seisa_kg/sources/gleif_fetch.py`). Re-running reads from the cache and costs nothing.
- **D-040 · The Sponsor nodes' facts come from our rule D-023, not from a source.**
  - Why: choosing Hg, Bridgepoint and Apax was our decision (D-023). Under D-029, our decisions point to a Rule, not to a SourceRecord.
- **D-041 · The shared fact list is a JSON Lines file: `data/interim/facts.jsonl`, one fact per line.**
  - Why: each row can hold its nested details and origin, it can be read in any editor, and lines can be counted with grep.
  - Alternatives not chosen: CSV (nested fields would have to be squashed into text); Parquet (can't be read by eye, and needs another library).

#### TODO
- [ ] Download finishes (`make fetch-gleif`); look at the 10 entities with no parent link at all (F13)
- [ ] Parser: GLEIF cache → `data/interim/facts.jsonl` (stage 2)
- [ ] RDF builder: facts → Oxigraph, then the D-038 checks (stage 4)
- [ ] Bruno: write the first 3 investor questions
- [ ] Bruno: open Explore (Bloom) once

### Builder step, part 2: the first end-to-end slice (GLEIF → fact list → RDF)

#### What we did
- **Stage 1, fetch:** `src/seisa_kg/sources/gleif_fetch.py` (`make fetch-gleif`). It follows GLEIF's own links for each entity, then fetches the records of outside parents and managers, so every entity in the graph has a name.
- **Stage 2, parse:** `src/seisa_kg/facts/` (`make facts`), which writes `data/interim/facts.jsonl`.
  - `model.py`: the row format (D-033) and how rows are saved, sorted so that re-runs give identical files.
  - `gleif_parse.py`: the GLEIF cache becomes rows. It reads the cache only and never downloads.
  - `sponsors.py`: the sponsor rows, with origin rule D-023 (D-040).
  - "This is a legal entity" is a row of its own, so that fact also has an origin (the GLEIF record), rather than being added by the builder with no source.
- **Stage 4, build:** `src/seisa_kg/rdf/build.py` (`make rdf`, which runs `make facts` first). It writes `data/output/graph.ttl` (Turtle 1.2).
  - Checks (D-038): the graph is not empty; one annotation per row for every predicate; every annotation has an origin (`checks/annotation_without_origin.rq`, in SPARQL); SHACL shapes 1–3 (`shapes.ttl`).
  - Any failed check stops the build.
- **Tests:** `tests/test_rdf_build.py`. Each check is tested by **breaking the graph on purpose** and confirming the check catches it (the lesson of F12). All 16 tests pass.
- **First run, on the partial cache:** 4,805 facts → 18,583 triples. All checks passed.
- **pyshacl added** to the project's libraries (chosen in D-013).
- **Schema sketch updated** to match: start dates keep GLEIF's time, e.g. `2021-01-17T23:00:00Z`. Cutting it to a date would be a silent change, because 23:00 UTC is already the next day in Luxembourg.

#### Decisions
- **D-042 · An entity found in several GLEIF replies gets its Level 1 facts from every one of them.** *(Bruno's call, against the "first reply only" suggestion.)*
  - Why (Bruno): Level 1 facts can change depending on the date of the fetch (F7), so each reply is a separate, dated observation, not a duplicate to throw away.
  - Why: if two replies ever disagree (a renamed entity, a new address), both values stay side by side, each with its own source and date, as D-025 and D-029 ask.
  - Knock-on: source records are now named **per reply**, not per kind of reply: `src:gleif/<LEI>/search-apax_p1/20261018`. *(Adjusts the D-037 naming.)* Two replies fetched on the same day would otherwise share a name.
  - Effect today: 5 entities appear in two search replies; some entities also have a separately fetched LEI record from the warm-up. Facts: 4,805 → 5,187.
- **D-043 · GLEIF's language code for a name is stored as a detail on its annotation, not as an RDF language tag.**
  - Why: a query for the plain name "Apax Digital III SCSp" still finds it. A tagged name (`"…"@fr-LU`) only matches a query that has the tag too, an easy trap for text-to-SPARQL later.
  - Why: the language is still recorded, as GLEIF states it.
- **D-044 · The one-line address starts with GLEIF's "care of" field (`mailRouting`) when there is one.**
  - Why: the D-028 scope rule tests for "care of" a sponsor, and would miss entities whose c/o is only in that field.
- **D-045 · Annotation nodes stay anonymous (blank nodes) in today's prototype. Naming them is a TODO for after today.**
  - **Why left out today (for Anish, if asked):**
    - Nothing outside the graph needs to point at an annotation yet. The first thing that will is the translation layer (D-016), which comes after both graphs exist.
    - Anonymous annotations are the standard RDF-star form (what Turtle's `{| … |}` makes), so there's nothing extra to explain or test today.
    - Adding names later is a change to the builder only. The fact list, the schema and the queries don't change, so leaving it out costs nothing to undo.
    - It keeps today's slice small enough to explain completely (D-009).
  - **What naming would give:** a stable address per annotation (e.g. `ex:fact/<fingerprint of the row>`) that Neo4j and the translation layer could share, so the same fact can be matched across both graphs by ID.

#### TODO
- [x] Download finishes; rebuild; look at the 10 entities with no parent link at all (F13)
- [x] Bruno: decide whether the 16 Oct search replies (`data/raw/gleif/sponsor_check/`) also count as observations under D-042 (yes)
- [ ] After today: give annotation nodes stable names (D-045)
- [ ] Bruno: write the first 3 investor questions
- [ ] Bruno: open Explore (Bloom) once

### Builder step, part 3: full GLEIF data in, 16 Oct replies added

#### Decisions
- **D-042 extended · The 16 Oct sponsor-check searches count as observations too.** *(Bruno.)*
  - Why: the same reasoning as D-042. Each reply is a dated observation, and keeping both dates lets the graph show what changed between fetches.
  - Only our three sponsors' search words are parsed; the Cinven, Inflexion and Permira replies stay out.
  - **Their web address:** the 16 Oct files were saved in an older format, with the fetch time but no address. The address is taken from GLEIF's own list of page links inside each reply, so it's GLEIF's statement, not one we rebuilt.

#### What we did
- **Download finished:** 1,019 Level 2 replies for all 484 entities, plus the records of 5 outside parents or managers. No linked reply came back "not found".
- **Full build:** 10,110 facts → 35,361 triples. All checks pass; all 16 tests pass.
  - Facts now include 471 direct and 469 ultimate "no parent" reasons, 3 direct and 5 ultimate actual parents, and 71 fund-manager links.

#### Findings
- **F13 · 10 entities have no Level 2 link at all, and each one has a reason in GLEIF's own data:**
  - 4 have a **retired** LEI (the entity is inactive), e.g. Apax Funds Nominees Ltd, Bridgepoint Portfolio Services.
  - 5 have a **lapsed** LEI (not renewed), e.g. BridgePoint Bible Church, Bridgepoint Business Center I LLC.
  - 1 is a **branch**, not a separate legal entity: Bridgepoint Fund Management S.à r.l., Sucursal.
  - So the gap is not missing data: GLEIF stops asking for Level 2 once an LEI is retired or lapsed, and doesn't ask branches for parents.
  - **Gap in our facts:** GLEIF's registration status (ISSUED, LAPSED, RETIRED) is not stored yet, and it is what explains this case. Decision pending (see TODO).
- **F14 · Between 16 and 18 Oct, no Level 1 fact changed** for the 483 entities in both sets of replies.
  - The only difference: one entity new on 18 Oct, **HG MERCURY 4 FUSION L.P.** (the new Hg entity behind F7).
  - The cost of D-042: most Level 1 facts now have two sources, one per date (about 5,200 → 9,800 Level 1 rows).
  - It makes "when did this entity first appear?" answerable from the graph.

#### TODO
- [x] Bruno: decide whether to store GLEIF's registration status (F13): yes, D-046
- [ ] Next: the D-028 scope step (ScopeDecision nodes), producing the list of about 16 "review" entities for Bruno
- [ ] Bruno: write the first 3 investor questions
- [ ] Bruno: open Explore (Bloom) once
- [ ] After today: give annotation nodes stable names (D-045)

#### Decisions
- **D-046 · Store GLEIF's registration status (`ex:registrationStatus`: ISSUED, LAPSED, RETIRED) as a Level 1 fact, as given.**
  - Why: it explains the 10 entities with no parent information (F13) from GLEIF's own data, not from a note of ours.
  - Why: a LAPSED LEI means GLEIF hasn't re-checked the data, which matters to an investor reading any fact about that entity.
  - Alternative not chosen: also an explicit "no Level 2 information" fact. GLEIF doesn't say that, so it would be our own judgement, and a query finds the same thing (no parent and no exception).
  - **Effect:** of the 489 entities, at the latest fetch 401 are ISSUED, **59 LAPSED**, 28 RETIRED and 1 PENDING_ARCHIVAL. So about 1 entity in 5 has data GLEIF no longer keeps up to date.

#### Findings
- **F14 corrected · One fact did change between 16 and 18 Oct**, which the first comparison missed because registration status wasn't parsed yet:
  - ΑΠΑΞ ΚΑΤΑΣΚΕΥΑΣΤΙΚΗ (the Greek look-alike, out of scope under D-028): **PENDING_TRANSFER** on 16 Oct → **PENDING_ARCHIVAL** on 18 Oct.
  - Both values are in the graph side by side, each with its own source record and date. This is the case D-042 was chosen for.
  - Lesson: "nothing changed" only holds for the fields you looked at.

### Scope step, detail 1: how a sponsor's name is matched

#### Findings
- **F15 · The name rule (D-028 "In") needs care in two directions:**
  - **It can miss real entities.** "Hg" as a whole word misses 45 of Hg's entities, all named **HGCAPITAL …**: HGCAPITAL LLP (Hg's own manager), HGCAPITAL TRUST PLC, and the HGCAPITAL 5–8 fund vehicles. Matching "hg" anywhere in the name catches them, but only works because GLEIF's search narrowed the list first; it would also match words like "BIRCHGROVE".
  - **It can let in look-alikes.** About 40 name matches sit outside the UK, Guernsey, Luxembourg, Jersey and Ireland. Some are clearly unrelated: BridgePoint Bible Church (Texas), BridgePoint Business Center LLCs, CSC Bridgepoint Realty, APAX CONSULTING LTD. (Marshall Islands), APAX AUTO COMPS INDIA. Some are real but run by outside companies: HQT Bridgepoint Europe V–VIII (HQ Trust feeders), NEWBURY BRIDGEPOINT. Some are real and historical: Apax's former French arm (now Seven2, F9).
  - Under D-028 as written, all of those would be **In**. To be handled once detail 2 ("care of") is settled, since that's the obvious second signal.
  - For Bridgepoint and Apax, whole-word and anywhere-in-the-name matching give identical results; only Hg differs.

#### Decisions
- **D-047 · The scope rule matches a list of name forms per sponsor, each as a whole word, ignoring case.** *(Refines D-028.)*
  - Name forms, in `config/sponsors.toml`: **Hg** → Hg, HgCapital; **Bridgepoint** → Bridgepoint; **Apax** → Apax.
  - Why: it catches the 45 HGCAPITAL entities on purpose, not by luck. Each listed form is a visible judgement that can be explained and changed.
  - Why whole words: a form can't match by accident inside another word.
  - Result: 100 Hg, 185 Bridgepoint and 140 Apax name matches.
  - **"HGT" (HgCapital Trust's ticker) is not a name form.** HGT SATURN 4 L.P. goes to Review for Bruno to decide.
    - Why: a three-letter ticker is a weaker signal than a name, and the primer says borderline cases go to a person. It costs one decision.

#### TODO
- [x] Scope detail 2: what counts as "care of" a sponsor (D-048 to D-050; it can't be F15's second signal, see F16)
- [ ] Scope detail 3: which date's facts the rule reads
- [ ] Then: build the scope step and produce the review list

### Scope step, detail 2: what counts as "care of" a sponsor

#### Findings
- **F16 · How sponsor addresses really appear (latest GLEIF replies):**
  - **"Care of" catches the acquisition chains.** E.g. 30 Apax entities are `c/o Apax Digital II GP Co. Limited, …`.
  - **Care-of is often not written "c/o".** The address simply starts with the sponsor company's name:
    - Janus Topco / Midco / Bidco: `Apax Partners Guernsey Limited, Third Floor, Royal Bank Place, …`
    - ACORN BIDCO: `HGCAPITAL, 2 MORE LONDON RIVERSIDE, …`
  - **Street and building names:** `225 Bridgepoint Drive` (4 Minnesota property companies; first counted as 6 by mistake), `Bridgepoint Parkway` and `Bridgepoint Plaza II` (Austin).
  - **An unrelated namesake:** `C/O BRIDGEPOINT GROUP ACCOUNTING PTY LTD`, an Australian accounting firm (2 companies).
  - **Care of sponsor companies with no LEI in our data:** Apax Partners Guernsey Limited (about 21 entities, including the Janus chain), Apax Partners Holdings Ltd, Bridgepoint AB.
  - **Some care-of lines are only in the headquarters address:** BPSF2, the Edmond de Rothschild LBO funds (c/o Bridgepoint Portfolio Services), the A12 EUR feeder.
  - **A likely data error:** Tembo Capital Mining Fund III LP (a different firm) gives its address as c/o Apax Digital II GP Co. Any address rule marks it In; the review list will flag it.
  - **Care-of can't be the second signal for name matches (F15):** only 13 of Bridgepoint's 185 name matches and none of Hg's 99 have a care-of address. F15 needs a different fix.

#### Decisions
- **D-048 · "Care of a sponsor company" means the c/o part, or the first part of the address, names a sponsor company: one that is In by name, or a name Bruno has approved.**
  - The care-of part is the text after "c/o" (up to the next comma); if there is no "c/o", it's the address's first part when that starts with a name.
  - **Care-of names not in our data go to a review list of names, not of companies** (about 7, e.g. "Apax Partners Guernsey Limited", "Bridgepoint Group Accounting Pty Ltd"). Bruno decides each name once, and the answer applies to every company using it.
  - Bruno's answers are stored as approved or rejected names, each with a reason: our judgement, labelled as ours (D-029).
  - Why: it catches the Janus chain, which has no "c/o" and no LEI behind its care-of name.
  - Why: it keeps out the Australian accountants, which "any sponsor word after c/o" would let in.
  - Why decide names, not companies: one decision about "Apax Partners Guernsey Limited" settles about 21 companies at once.
  - Alternatives not chosen: any sponsor word in the care-of part (lets in the namesake); only companies already in our data (loses the Janus chain).
- **D-049 · A sponsor word that appears only in a street or building name gives Out, with the reason.** *(Confirms D-028's "Out" for this case.)*
  - The test: the part names a street or building (Drive, Parkway, Plaza, Street, Road, …), or starts with a house number.
  - Why: these are clearly unrelated (Minnesota property companies, Austin offices). About 10 hand decisions on obvious cases would waste review time.
- **D-050 · Store GLEIF's headquarters address too (`ex:headquartersAddress`), as given, one line; the care-of check reads both addresses.**
  - Why: the scope rule only reads facts that are in the graph, so every decision traces back to a source.
  - Why: without it, BPSF2, the Edmond de Rothschild funds and the A12 feeder would be missed.

#### TODO
- [x] Scope detail 3: which date's facts the rule reads (D-051)
- [x] F15: a different fix for name-matched look-alikes (D-053)
- [x] Then: build the scope step; produce the two review lists (entities, and care-of names)

### Scope step, detail 3: which date, and keeping it simple

#### The point of the exercise (re-checked, at Bruno's request)
- Scope exists so investor questions ("what does Apax own?") have a defensible answer to "which companies count as Apax?". That is all it does.
- Test for every piece: can Bruno explain it in one sentence, and does an investor question need it? If not, leave it out.
- **History is already kept, in the facts (D-042).** Every reply is stored with its date and nothing is overwritten. A run on any later day adds that day's facts alongside the old ones. So the scope labels don't need a history of their own.
- **Requirement from Bruno:** the programme will be run on different days in future and must work whenever it is run. Most recent information is preferred, with history kept.

#### Decisions
- **D-051 · The scope rule reads each entity's latest observation; the labels are worked out afresh on every run.**
  - "Latest" = the most recent GLEIF reply that contains the entity.
  - Why: one sentence to explain ("scope uses the latest thing GLEIF told us"), and it works whatever day it runs.
  - Why: history stays in the facts, so a past label can always be recomputed from that day's facts.
  - An entity GLEIF later drops keeps a label based on its last known facts.
  - Alternatives not chosen: a label per observation date (multiplies labels; no question needs past verdicts); "In if any observation matches" (hides changes).
- **D-052 · Bruno's hand decisions live in `config/scope_reviews.toml` and are applied on every run.**
  - One entry per decision: the entity (or care-of name), the sponsor, In or Out, Bruno's reason, the date.
  - New entities on later days land in Review automatically; earlier decisions stay.
  - Why: readable, survives rebuilds, and git keeps the file's history for free, so no extra code for history.
  - In the graph, a hand decision is a second ScopeDecision linked to the automatic one by `prov:wasRevisionOf` (D-037).
- **D-053 · F15 look-alikes: keep the name rule; Bruno marks the clear look-alikes Out by hand; the precision is reported honestly.**
  - A one-off list of name matches outside each sponsor's usual countries (UK, Guernsey, Jersey, Luxembourg, Ireland) is produced for Bruno to skim. It is a review aid, not a rule.
  - Why: no new rule to explain, and an honest measurement (roughly 8 wrong out of 425 name matches) is what the brief rewards.
  - Alternatives not chosen: a country rule (about 40 extra reviews, and the country list is itself a judgement: Bridgepoint really is in Spain, France and the US); requiring a second signal (care-of can't be it, F16).

### Scope step built

#### What we did
- **`src/seisa_kg/facts/scope.py`**, run inside `make facts`. It reads only the fact list, takes each entity's latest observation (D-051), and runs the tests in order: name (D-047) → care-of (D-048, D-050) → street (D-049) → former name → anything else goes to Review.
  - The "managed by an outside company" test (D-028) sits inside the name test: a name match whose GLEIF fund manager doesn't carry the sponsor's name goes to Review.
  - Care-of names are compared by **exact** match after tidying case, accents and punctuation, never by "starts with". Otherwise an entity simply called "Bridgepoint" would quietly approve "Bridgepoint Group Accounting".
  - When an address line runs on with no comma ("Apax Partners Guernsey Limited Third Floor …"), the care-of name is cut after its legal-form word (Limited, Ltd, LLP, S.à r.l., AB …).
- **Hand decisions** come from `config/scope_reviews.toml` (D-052). It's empty for now, with commented examples.
- **Rule nodes** are now in the graph (D-023, D-028, manual-review), each with a plain-English label. This settles the D-040 open point: our rules' facts point to the rule itself.
- **`docs/scope-review.md`** is regenerated on every run: the counts, the entities to review, the care-of names to review, and two lists to skim.
- **Build:** 15,006 facts → 49,042 triples. All checks pass; all 16 tests pass.

#### Results (18 Oct)
| Sponsor | In | Review | Out |
|---|---|---|---|
| Hg | 98 | 7 | 0 |
| Bridgepoint | 186 | 9 | 7 |
| Apax | 160 | 17 | 0 |

- **6 care-of names to decide.** They settle 17 of the 33 Review entities at once. "Apax Partners Guernsey Limited" alone covers 11, including the Janus Topco / Midco / Bidco chain.
- **16 Review entities** remain to decide one by one. This matches D-028's estimate of about 16.
- The 4 "managed by an outside company" cases match F9's 4 exactly (Nucleus HG GENESIS 10, BRIDGEPOINT PRIVATE EQUITY FCR, BRIDGEPOINT DIRECT LENDING I, APAX DEVELOPMENT FUND II BY PEQAN).
- All 7 Outs are street or building names: 4 Minnesota companies at 225 Bridgepoint Drive, Emerald Bay Fund (Bridgepoint Parkway), and 2 Austin companies (Bridgepoint Plaza II).
- **Interesting case:** BP VERAISON BUYER, LLC. Its headquarters address is `BRIDGEPOINT, 10 E 53rd St, New York` (Bridgepoint's New York office), but GLEIF's address lines split it so the care-of name reads "BRIDGEPOINT 10 E". It's on the care-of list.

#### TODO
- [ ] *(Optional, any time; not needed for the prototype, D-056)* Bruno: decide the 6 care-of names and any Review entities in `config/scope_reviews.toml`, using `docs/scope-review.md`
- [ ] *(Optional, any time)* Bruno: skim lists 3 and 4 in `docs/scope-review.md`; mark look-alikes Out (D-053), and check Tembo Capital (F16)
- [ ] Bruno: write the first 3 investor questions
- [ ] Bruno: open Explore (Bloom) once
- [ ] Tests for the scope rules (one per test, with a made-up entity each)
- [ ] After today: give annotation nodes stable names (D-045)

### Scope step: made fully automatic

#### Decisions
- **D-056 · The scope step is fully automatic. "Review" is a valid final label, and hand review is an optional side loop, not a pipeline step.** *(Bruno: "isn't the whole point that this is an automatic process?")*
  - `make rdf` runs end to end with no stop for review, on any day.
  - "Review" means "the rules couldn't tell". It is stored with its reason; investor questions count In and can say how many are uncertain.
  - `config/scope_reviews.toml` stays for optional corrections, read on whichever run follows them.
  - Why: the goal today is a runnable end-to-end prototype, and the system must run unattended on future days.
  - Why: general patterns belong in rules, which apply on every future run, not in hand decisions, which only cover today's entities.
- **D-054 · Only a former legal name matches → Out: "a past link, not a current one".** *(Turns principle A into a rule.)*
  - "Belongs to a sponsor" means **belongs now**. A previous legal name shows a past link only.
  - It fires only when **every** matching other name is a `PREVIOUS_LEGAL_NAME`. A current other name (e.g. a trading name) still gives Review: ALTAROC matches through its trading name "APAX PARTNERS & CIE GESTION".
  - The reason quotes the old name, so the history stays visible.
  - Affects: SEVEN2 and SEVEN2 MIDMARKET X SPV (ex-Apax France), the 4 ASPER funds (ex-HgCapital Renewable Power), CAMELOT and MAPIL BIDCO (ex-Bridgepoint bidcos), BBTPS NOMINEES.
  - **Knock-on:** HGT SATURN 4 L.P. was previously "HG 2024 HGT L.P.", so it is now Out, not Review (D-047). If it should count as Hg's, that is a one-line hand correction.
- **D-055 · A sponsor-named fund that GLEIF says is run by an outside company → Out: "run by an outside company".** *(Turns principle B into a rule; changes D-028's "Review" for this case.)*
  - These are feeder or access funds that outside platforms run and that invest *into* the sponsor's funds. The sponsor doesn't control them; they are closer to LPs than to sponsor entities.
  - Why: it is what GLEIF itself says (the fund-manager link, D-027).
  - Affects: Nucleus HG GENESIS 10, APAX DEVELOPMENT FUND II BY PEQAN, BRIDGEPOINT PRIVATE EQUITY FCR (Amchor), BRIDGEPOINT DIRECT LENDING I (Gen II).
  - Limit: feeders with no GLEIF manager link (e.g. HQT Bridgepoint Europe V–VIII) stay In by name. That is measured error, to report.
- **D-048 kept (Bruno):** care-of names not in our data stay **Review**. So, until a hand decision is made, the Janus Topco / Midco / Bidco chain and the other entities care of "Apax Partners Guernsey Limited" are counted as uncertain, not as Apax's.

#### Results (18 Oct, after D-054 and D-055)
| Sponsor | In | Review | Out |
|---|---|---|---|
| Hg | 98 | 1 | 6 |
| Bridgepoint | 186 | 4 | 12 |
| Apax | 160 | 14 | 3 |

- 19 Review in total: 17 come from the 6 unknown care-of names, plus ALTAROC and ΑΠΑΞ.
- Build: all checks pass; all 16 tests pass.

### RDF explained, and today's goal narrowed

#### What we did
- Bruno asked for the RDF format to be explained from the ground up. It's now built up in seven layers (1–3: the facts; 4–6: where they came from; 7: our own decisions).
- A visual page with three diagrams, for copying into the notebook: [Reading the RDF Graph](https://claude.ai/artifact/8r5D58sm6ZndQnYjrV9wfb) (private to Bruno).
- Researched what makes a good investor question; the sources are listed in the chat of 18 Oct. Summary:
  - Questions are requirements written before the schema and used to test it ("competency questions", Grüninger & Fox 1995).
  - Good ones are atomic, clear, domain-relevant and testable (Sefidbari & Castro, CEUR 2026, quoting Grüninger & Fox).
  - Mix the types: several links, counting, time-based, unanswerable (LC-QuAD 2.0, QALD).
  - The valuable ones cross sources and show gaps and conflicts (Seisa primer §3.2–3.3).

#### Decisions
- **D-057 · Today's goal: a runnable end-to-end pipeline in RDF only. Neo4j and Cypher move to tomorrow (19 Oct).**
  - Why: Bruno wants to understand the RDF side fully before building the second graph, and a finished slice beats two half-finished ones (D-009).
- **D-058 · Stage 5 is built with three placeholder questions (Claude Code's drafts), one SPARQL file each. Bruno tweaks the wording tomorrow.**
  - Q1, several links: which companies GLEIF says manage Apax's funds, and how many funds each manages.
  - Q2, counting gaps: per sponsor, how many companies report no parent, and why.
  - Q3, time and data quality: which sponsor companies have a lapsed or retired LEI, and when GLEIF last told us so.
  - Why: they test the three things the runner must handle (following links, counting, reading a fact's source and date). Changing a question later touches only its own file.

### The RDF pipeline runs end to end (`make build`)

#### What we did
- **Stage 5, query:** `src/seisa_kg/rdf/ask.py` (`make query`).
  - It loads the saved graph (`data/output/graph.ttl`). This also proves the file on disk loads back complete: 49,042 triples in about 0.15 s.
  - It runs every question in `src/seisa_kg/rdf/queries/*.rq`, timing each one (median of 5 runs, after one untimed warm-up).
  - Each answer is saved with every source: `data/output/answers/rdf/<question>.json`.
  - A readable report: `docs/answers-rdf.md` (long source lists shortened to the first one plus a count).
  - A question that returns no rows is flagged, never passed silently (F12).
- **The three placeholder questions (D-058),** one file each, every line commented:
  - `q01_apax_fund_managers.rq`: **9 managers**. Apax Digital II GP Co. Limited manages 31 of Apax's In funds, and Apax Management Luxembourg S.à r.l. manages 9. 1 ms.
  - `q02_no_parent_reasons.rq`: **15 rows**, mostly `NON_CONSOLIDATING` (Apax 124, Bridgepoint 118, Hg 89). The totals match the In counts exactly (160, 186, 98), so every In company is counted once. 108 ms.
  - `q03_lapsed_leis.rq`: **72 lapsed or retired** In companies, each with when GLEIF last said so and the source. 3 ms.
  - Every answer row carries its sources: the GLEIF web addresses and fetch times, read from the RDF-star notes.
- **`make build`:** the single command. fetch (cached) → facts → scope → RDF graph → checks → questions. **7.5 seconds** from the cache. A first run on an empty cache downloads from GLEIF (about 16 minutes at the rate limit).
- **Tests:** `tests/test_rdf_questions.py`. Every question file must parse as SPARQL and carry QUESTION, WHY and TYPE lines; an empty folder fails. **23 tests pass.**

#### Findings
- **F17 · A "/" can't appear in a SPARQL short name.** `ex:sponsor/apax` is read as a path ("follow ex:sponsor, then apax"), not as one name. Sponsors now get their own prefix in queries (`sponsor:apax`). The new test catches this kind of mistake before a build.
- **F18 · Two reason codes we hadn't seen in the warm-up sample:** `NON_PUBLIC` (4 Bridgepoint companies) and `NO_LEI` (1). D-026 stores whatever code GLEIF gives, so they came through with no code change.
- **F19 · Q2 is about 100 times slower than Q1 and Q3** (108 ms against 1–3 ms). It's the only one with OPTIONAL blocks around the RDF-star notes. Worth a line in the timing write-up once the larger dataset exists.

#### TODO for tomorrow (19 Oct)
- [ ] Bruno: tweak the three questions (wording, or swap in the alternatives Q1b, Q3b or the "unanswerable" probe), then add more, towards the brief's 10–12
- [x] Property-graph schema, including how it records sources (D-063)
- [ ] The "what changed between RDF and the property graph" note (`docs/schema/what-changed.md`) and `docs/schema/lpg-schema.md`
- [ ] Neo4j builder from the same fact list; the same questions in Cypher; both in `make build` *(removed; redo together on 19 Oct)*
- [ ] Timings on a smaller and a larger dataset (brief §3)
- [ ] One Bloom view tracing a fact to its source; Bruno: open Explore (Bloom) once
- [ ] Tests for the scope rules (one per test, with a made-up entity each)
- [ ] README: how someone else runs `make build`
- [ ] *(Optional, any time)* Bruno: hand decisions in `config/scope_reviews.toml` (the 6 care-of names, the look-alikes, HGT SATURN 4, Tembo Capital)
- [ ] After Monday: give annotation nodes stable names (D-045)

### Evaluation: how answers are scored (about 4:15pm)

The brief (§6) asks for each answer to be scored "for whether it is correct and whether its cited sources support it". The primer adds that automated judges "must be calibrated against domain experts". Bruno wants graded scores, not yes or no.

#### Decisions
- **D-059 · Correctness is graded 0–1 by overlap with the reference answer.**
  - Each question has a **reference answer** from its hand-written query (the "gold set").
  - **Precision:** of the items the candidate gave, how much is right. **Recall:** of the reference items, how much it found. **Correctness = F1** of the two.
  - **Counts get partial credit by closeness:** 1 − |candidate − reference| ÷ reference (e.g. 118 against 124 scores 0.95).
  - **"Not in the data" questions** score 1 if the answer says so, and 0 if it invents items.
  - Why: it's the standard in question-answering benchmarks (QALD reports per-question precision, recall and F1), fully automatic, and it uses the same precision and recall terms as the brief's matching task.
  - Alternatives not chosen: a 0–3 rubric judged by the language model (needs calibration against a person; may still be added for free-text vector-search answers); both together (most to build and explain).
- **D-060 · Citation is graded 0–1 from two fractions.**
  - **Support:** of the sources the answer cites, the fraction that really state the fact, checked against our own provenance (the RDF-star notes).
  - **Coverage:** of the answer's items, the fraction with at least one supporting source.
  - **Citation score = F1** of support and coverage.
  - Why: it catches both invented sources (low support) and unsourced claims (low coverage). An answer that cites nothing scores 0, not a perfect score.
- **D-061 · Overall score = (correctness + citation) ÷ 2, always shown beside both parts.**
  - Why: one number to rank the approaches by, while the parts show *why* an answer scored low. Equal weights need no defending.
  - Alternatives not chosen: correctness × citation (hides partial credit); no overall number.
- **D-062 · The gold set starts with the 3 placeholder questions (D-058). Bruno writes the rest tomorrow, after the chat with Anish.**
  - Why: the brief says "questions of your own", and Bruno will defend them in the explain-back. The scorer reads questions as data, so adding them later needs no code change.

#### What we did
- **The scorer:** `src/seisa_kg/evaluation/score.py`. It matches a candidate's items to the reference's **by value, not by column name** (a generated query names its own columns), and returns correctness, precision, recall, citation, support, coverage and overall, plus what went wrong: missed items, invented items, numbers off, unsupported citations, uncited items.
- **Scoring keys** added to each question file: `# KEY:` (the columns that identify one item) and `# VALUE:` (the column holding a count).
- **Tests:** `tests/test_score.py`, 7 hand-worked cases (e.g. missing one of two items gives correctness 0.667; a count of 8 against 10 gives 0.8 for that item). **30 tests pass.**
  - Two tests failed at first and **caught a real bug**: our own entity addresses (`https://seisa-kg.example/lei/…`) were being counted as cited sources, so an answer with no sources got full citation marks. Fixed: only real source addresses count.
- **Demonstration:** `make score-demo` writes `docs/scoring-demo.md`. Each reference answer is damaged one mistake at a time and scored. Q1 example: two items missed 0.938; one invented 0.944; counts 10% low 0.977; no sources 0.5; sources swapped 0.5; "not available" 0.

#### Findings
- **F20 · A citation is only as precise as its source record.** In Q3, swapping sources between items still scores 0.93 on citation. That's because Q3's facts come from GLEIF **search pages**, and one page holds up to 200 companies, so the swapped page usually does state the other company's fact as well. The scorer is right; the evidence is coarse.
  - For the write-up: citing a search page is weaker evidence than citing the single LEI record. A finer source (one record per LEI) would make citation checks sharper.
  - Q1's facts come from per-LEI fund-manager records, so the same swap scores 0 there.

#### TODO
- [ ] Neo4j: the property-graph schema (D-063), the builder and the 3 questions in Cypher *(built, then removed at Bruno's request: to be done together, step by step, on 19 Oct)*
- [ ] Tomorrow, after the chat with Anish: Bruno writes the remaining questions (D-062)
- [ ] The text-to-SPARQL and text-to-Cypher candidates (Gemini), scored with this scorer; vector search once the news releases exist

### Neo4j: how the property graph records sources

#### Decisions
- **D-063 · Neo4j records sources with "receipt boxes": each GLEIF reply is a `SourceRecord` node holding what that reply said, linked to its entity by `STATED_IN`.** *(Settles the plan's open item, "provenance in the property graph".)*
  - **The problem:** in a property graph a node holds its values inside itself, and relationships can hold properties. But you can't attach a note to a single value, and a relationship can't point to another relationship or to a node. So RDF-star's "note → receipt" has no direct equivalent.
  - **The design:**
    - `(:LegalEntity)-[:STATED_IN]->(:SourceRecord {source, url, retrievedAt, …the values that reply gave})`, one per reply, so history is kept (D-042).
    - The entity node also carries its **latest** values as properties, for easy querying (D-051's "latest observation"). This is a convenience copy; the facts come from the records.
    - Links are direct relationships (`MANAGED_BY`, `DIRECT_PARENT`, `ULTIMATE_PARENT`) carrying their details (start date, status, corroboration) and a `sources` list of record IDs as properties.
    - Our judgements stay nodes: `(:ScopeDecision {verdict, reason})` with `ABOUT` → entity, `FOR` → sponsor, `MADE_BY` → rule, and `REVISES` for hand decisions.
  - Why: the fact → source path stays visible in Bloom (the brief requires it), history is kept, and queries stay simple: values on nodes, direct relationships.
  - **What changed from RDF (for the "what changed" note):** a relationship's source becomes a property, not a path, and sources are recorded per reply rather than per fact. But every RDF note points to a per-reply record anyway, so little is lost.
  - Alternatives not chosen: properties only (no path to the source; history lost); every fact a node (copies RDF-star exactly, but every question needs an extra hop, and it's RDF in disguise rather than a designed property graph).

### Neo4j built; both graphs answer the same questions identically (about 5pm)

#### What we did
- **Neo4j builder:** `src/seisa_kg/lpg/build.py` (`make neo4j-build`). It reads the same fact list as the RDF builder (D-012) and **rebuilds our own Neo4j database from scratch on every run**, as the RDF build does.
  - Result: 15,006 facts → **2,991 nodes and 3,546 relationships** (RDF: 49,042 triples).
  - Checks (any failure stops the build): not empty; node and relationship counts match the fact list; **every source fact is on its receipt node, and every value on a receipt is a source fact, checked both ways**; every entity has a receipt; every relationship names a source.
  - **The checks were tested by damaging the graph on purpose.** The first version caught only 1 of 2 faults: it looked for missing facts but not invented ones. After making it two-way, it caught all 4 kinds of damage (a deleted relationship, a changed value, an invented value, an entity with no receipt).
- **The 3 questions in Cypher:** `src/seisa_kg/lpg/queries/*.cypher`, same filenames and header lines as the SPARQL versions.
- **Cypher runner:** `src/seisa_kg/lpg/ask.py` (`make query-lpg`). It shares the RDF runner's report format (`docs/answers-lpg.md`) and **scores every Cypher answer against the RDF answer** with the answer scorer. **All three agree fully: 1.0.**
- **`make build`** now runs everything: fetch (cached) → facts → scope → both graphs → their checks → questions in SPARQL and Cypher → agreement scores. **9 seconds.** Neo4j must be running first (`make neo4j-start`).
- **31 tests pass.**

#### Findings
- **F21 · Cross-checking the two graphs found a bug in the RDF reference query.** Q2 first agreed at only 0.964. Both answers were identical, but RDF cited 1,051 sources for the "(no Level 2 information)" rows, where Neo4j correctly cited none.
  - Cause: when a company had no record, the SPARQL step that looks up a record's address ran with nothing to look up, so it matched *every* record in the graph. Fixed by doing the lookup inside each OPTIONAL block.
  - Lesson for the write-up: two independently built graphs answering the same question is a strong test. It caught an error that each graph's own checks could not.
  - It also exposed a gap in the scorer: an item whose true answer has no source (an absence) was penalised for citing nothing. **Refinement to D-060 (Claude Code's; Bruno to confirm):** such items are left out of coverage, and with no citations needed, support is full. A test pins this down.
- **F19 corrected.** Q2's slowness (108 ms) wasn't caused by the OPTIONAL blocks, as first guessed. It was the F21 bug, which made the query look up every record. Fixed, it takes 5 ms.
- **F22 · First size and speed comparison** (the same 15,006 facts):
  - Size: RDF has **49,042 triples**; Neo4j has **2,991 nodes + 3,546 relationships**. RDF needs one note (reifier) per fact; Neo4j keeps values inside nodes and puts sources on per-reply receipts.
  - Speed: RDF answers in 1–5 ms and Neo4j in 3–8 ms. **Not a fair comparison yet:** Oxigraph runs in memory inside the same program, while Neo4j is a separate server reached over a network connection. To be set up properly with the small and large datasets.

#### TODO
- [x] Bruno: confirm the D-060 refinement (an item whose true answer has no source isn't penalised for citing nothing): confirmed, D-064
- [ ] `docs/schema/lpg-schema.md`, and the "what changed between RDF and the property graph" note (brief deliverable)
- [ ] One Bloom view tracing a fact to its receipt; Bruno: open Explore (Bloom) once
- [ ] Tomorrow, after the chat with Anish: Bruno writes the remaining questions (D-062), each in SPARQL and Cypher
- [ ] Text-to-SPARQL and text-to-Cypher with Gemini, scored with the scorer; vector search once the news releases exist
- [ ] Timings on a smaller and a larger dataset, done fairly (F22)
- [ ] Tests for the scope rules; README

### Neo4j removed, to be built together tomorrow (about 5:15pm)

#### What happened
- The whole Neo4j side (builder, Cypher questions, runner) was built in one go after a single design question (D-063). Bruno hadn't worked through it, and needs to explain it with no code open.
- **At Bruno's request, it has been removed**, to be built together step by step on 19 Oct:
  - deleted: `src/seisa_kg/lpg/`, `docs/answers-lpg.md`, `data/output/answers/lpg/`, and the `make neo4j-build` / `make query-lpg` targets;
  - the Neo4j database emptied (0 nodes) and the 5 uniqueness rules the builder created dropped;
  - the RDF runner's Neo4j-only additions undone (reading `//` header lines; the "agreement with RDF" line).
  - **Kept:** the Neo4j server itself (installed 16 Oct; `make neo4j-start` etc.), and everything RDF.
  - The removed code stays in git history (commit 723f6f2), for reference only. Tomorrow starts from the design, not from that code.
- **Checked:** `make build` runs the RDF pipeline end to end (fetch → facts → scope → RDF graph → checks → questions); `make score-demo` runs; **31 tests pass**.

#### Decisions
- **D-063 reopened.** Bruno chose "receipt boxes" for how Neo4j records sources, but it will be walked through together before any code: the concept, then the schema, then the builder, then the queries, one at a time.
- **D-064 · The D-060 refinement is confirmed (Bruno: "fine").** An answer line whose correct answer has no source (an absence, e.g. "no Level 2 information") isn't marked down for citing nothing. Lines whose true answer has a source, and invented lines, still need citations.

#### Still true from the removed build
- **F21 stands:** the cross-check found a real bug in the RDF query Q2 (it cited all 1,051 records for lines with no record). The fix stays in the SPARQL, and the F19 correction stands (Q2 now takes about 5 ms).
- **F22 (sizes and speeds)** was measured on the removed build. Re-measure once the Neo4j graph is rebuilt.

#### TODO for tomorrow (19 Oct)
- [ ] Neo4j together, step by step: concept (property graph vs RDF) → schema sketch (`docs/schema/lpg-schema.md`) → builder → the questions in Cypher → `make build`
- [ ] The "what changed between RDF and the property graph" note
- [ ] Bruno writes the remaining questions after the chat with Anish (D-062)
- [ ] Text-to-SPARQL (and later text-to-Cypher), scored with the scorer
- [ ] Fair timings on a smaller and a larger dataset; Bloom view; scope-rule tests; README

### Text-to-SPARQL: started, paused for the day (about 5:30pm)

#### What we did
- Bruno confirmed "the SQL thing" means **text-to-SPARQL**: Gemini reads a plain-English question, writes a SPARQL query, we run it on the RDF graph, and the scorer marks it (pipeline stage 6, "Ask"). It's the one stage the RDF side doesn't have yet.
- **Step 1 explained (no code yet):**
  - What the model is given: the question, a description of our graph (the schema), and instructions.
  - Why it needs the schema: it has never seen our names, our scope decisions or our RDF-star notes.
  - Typical mistakes on our graph, and the score column each shows up in:
    - an invented name gives 0 rows
    - bad syntax (like F17) means the query doesn't run
    - ignoring the scope rule invents items
    - forgetting sources gives citation 0
    - fumbling the RDF-star syntax gives wrong sources
    - the F21 blank-lookup trap gives low support.
  - Safety: only read-only `SELECT` queries are accepted, run on an in-memory copy.
- Paused here at Bruno's request (tired).

#### TODO: pick up here tomorrow (19 Oct)
- [ ] **Text-to-SPARQL step 2, Bruno's decisions:** (1) how much schema the model sees; (2) whether to give one or two worked examples (never the question being tested); (3) which Gemini model; (4) one retry with the error message when a query fails, or none. Then step 3 (the call to Gemini) and step 4 (run it on the 3 questions and score), checking in after each step.
- [ ] Neo4j together, step by step (see the list above)
- [ ] Bruno writes the remaining questions after the chat with Anish (D-062)

### Study guide for the meeting with Anish (evening, 18 Oct)
- Bruno meets Anish at the office at 1pm on 19 Oct to talk through the work so far.
- Produced a 33-page study guide PDF, built for a 60–90 minute read: a core path of about 66 minutes (marked CORE), "if time" parts, a self-test, and appendices listing every decision and finding.
- **Saved outside the repo**, at `~/Work Projects/Seisa study guide - 19 Oct 2026.pdf`, because it holds Bruno's meeting preparation, which shouldn't be in the code Seisa reviews.

### Demo check and visualisation options (late evening, 18 Oct)
- **Demo check:** `make build` ran end to end in about 7 seconds. All checks passed, the three answers were unchanged (9, 15 and 72 rows), and all 31 tests pass.
  - It needs **no internet**: every GLEIF reply is read from the cache in `data/raw/gleif/`.
  - Each run changes only the timings in `docs/answers-rdf.md`.
- **Visualising the RDF graph: options put to Bruno, not yet decided.**
  - Drawing the whole graph (49,042 triples) is unreadable. Useful views show one slice, e.g. one company and everything said about it.
  - Most RDF viewers can't draw RDF-star, so they lose the sources on each fact. This is a point for Anish, and part of why Neo4j Bloom is on the plan.
  - **A (recommended):** a small script that pulls one company's or sponsor's slice with SPARQL and saves an interactive web page, with source and date shown on each arrow.
  - **B:** Oxigraph's own server, with a browser query page. Answers come as tables, not pictures.
  - **C:** a dedicated RDF tool such as GraphDB Free. A heavy install, and RDF-star support varies.
  - **D:** wait for Neo4j Bloom, which comes with the property-graph work.

#### TODO (after the meeting with Anish, 19 Oct)
- [ ] Bruno picks a visualisation option (A recommended); build it together, step by step
- [ ] Then the TODOs above: Neo4j step by step, text-to-SPARQL step 2, Bruno's remaining questions

## 19 Oct 2026 (Monday)

### After the meeting with Anish: his pointers
- **What makes a good triple, and what counts as one?** Bruno is to work out his own criteria and be able to defend them.
- **Why is our pipeline doing the right thing?** Bruno needs evidence that the rules are correct (fact-making, scope), not just that they run.
- **The way Bruno and Claude work together.** Bruno wants to become the expert on architecture and data format, not offload it.
  - Bruno's view: Claude is mostly for coding and note-taking, plus decision suggestions backed by facts or sources that explain the why.
  - A workflow was proposed (below). Bruno accepted it as D-067, and it is now in CLAUDE.md.

#### The workflow (D-067, accepted)
1. **Bruno thinks first.** For each design question, Claude gives the questions to consider and the sources to read. Bruno writes a first answer before seeing Claude's.
2. **Claude reviews with evidence.** It agrees or pushes back, citing a source or a finding from our own data, and labels which parts are fact and which are opinion.
3. **Bruno decides,** and writes the why in his own words. Claude logs it here.
4. **Claude codes in small pieces,** commented line by line. Bruno runs each piece and reads the output.
5. **Explain-back before moving on.** Bruno explains the step without code open, and Claude asks the questions Anish might ask.

#### TODO
- [x] Bruno confirms or changes the workflow; then add it to CLAUDE.md's working rules (D-067)
- [ ] Bruno drafts his own "what makes a good triple" criteria; then review them against the sources
- [ ] Decide how to prove the pipeline is right (e.g. a hand-checked sample of scope verdicts, measured for precision and recall)
- [ ] Carried over: visualisation option (A–D), Neo4j step by step, text-to-SPARQL step 2, Bruno's remaining questions

### New deadline and plan v3 (3pm)
- **D-065 · Finish by Wednesday 21 Oct, and present on Thursday 22 Oct.**
  - Bruno works Mon 15:00–18:00, then Tue and Wed 10:00–18:00, about 19 hours.
  - PLAN.md §6 is rewritten as a day-by-day plan (v3).
  - Why: a fixed date makes the scope honest. With Bruno thinking first, the work is slower, so some breadth has to go.
- **D-066 · Drop the extensions; keep Companies House and about 30 news releases.**
  - Dropped: the translation layer and the custom GUI. They're Bruno's own add-ons, not in the brief. They become "next steps" in the write-up.
  - Visualisation: use the **standard** ways of viewing knowledge graphs (Neo4j Bloom plus one other standard tool). Build a simple GUI only if those fall short.
  - Kept: Companies House (UK control records) and about 30 news releases, the brief's number.
  - Why: spend the time on what the brief asks for. Standard tools are what a reviewer expects, and easier to defend than a home-made viewer.
  - Honest budget: the plan is now about 3 hours over the time available. PLAN.md §6 has a "drop in this order if behind" list, and Bruno decides at the time.
- **D-067 · The way of working is now a standing rule in CLAUDE.md.**
  - Bruno thinks first, then Claude reviews with sources. Bruno decides, Claude codes in small pieces, and Bruno explains each step back.
  - Why: Anish's advice. Bruno must own the reasoning, because the explain-back is done with no code open.

### What makes a good triple (Bruno's answers, reviewed together)
Bruno answered seven questions first; Claude reviewed each one against sources and our data (D-067).
- **D-068 · The parent arrows are renamed to GLEIF's own words.**
  - `directParent` → `directlyConsolidatedBy`, and `ultimateParent` → `ultimatelyConsolidatedBy`. GLEIF calls these `IS_DIRECTLY_CONSOLIDATED_BY` and `IS_ULTIMATELY_CONSOLIDATED_BY`.
  - Why: "parent" reads as "owns me", but GLEIF means "adds me into its accounts". Companies House brings a second kind of parent (whoever controls more than 25%), and the two must not be confused. Using the source's own word also follows D-029.
  - The exception arrows keep their names (`directParentException`), because GLEIF itself calls them "parent reporting exceptions".
  - The answers are unchanged, and 31 tests pass.
- **D-069 · Addresses stay as one line of text, not a node.**
  - Why (Bruno): a shared address would link unrelated companies.
  - Evidence: 414 of our companies share an address with another. Some shared addresses mix In and Out companies, e.g. 1 Royal Plaza, St Peter Port (57 companies, Hg In and Out) and 5 Marble Arch (57, Bridgepoint In and Out). These are probably administrators' offices.
  - The same building is also spelt two ways ("ST PETER PORT" / "ST. PETER PORT"), so a node wouldn't merge reliably anyway.
  - The lesson: **sharing a value is not a relationship.** Country stays as text for the same reason, and because no question needs facts about a country.
- **D-070 · Keep facts that come straight from the source record, even if no question uses them yet.**
  - This covers e.g. `gleifCategory`, `legalForm` and `registeredAt`.
  - Why (Bruno): the questions will change. These cost almost nothing, they're recorded as given, and `legalForm` may help tell funds (LPs) from GP companies.
  - The limit: we don't **invent** derived facts that no question needs. The schema the LLM sees (text-to-SPARQL) can leave out unused arrows if they confuse it.
- **The LEI as the name of each company: confirmed.**
  - It's permanent (ISO 17442), never reused, and stays the same when the name changes. A merged company's LEI is retired and points to its successor.
  - **Bruno's finding:** a Companies House number doesn't mean a company has an LEI (e.g. Seisa AI has none). Most UK companies don't, and many portfolio companies in the news won't either.
  - So an **identity rule** is needed before Companies House goes in (Tuesday): the LEI if there is one; otherwise the Companies House number (`ch:`); otherwise our own ID, marked unresolved. A company with both stays one node.
- **Missing facts.** A source saying "no" (e.g. NON_CONSOLIDATING) is a fact, and is stored. A source saying nothing is **unknown, not false**: RDF's "open world" assumption. Another source (e.g. Companies House) may fill the gap.

#### TODO (rest of Monday, until 6pm)
- [x] Good-triple criteria: Bruno drafts answers to the seven questions; then review against the sources (D-068 to D-070)
- [ ] Tuesday, before Companies House: decide the identity rule (LEI → Companies House number → our own unresolved ID)
- [ ] Bruno writes the 10–12 investor questions
- [ ] Decide how to prove the pipeline is right
- [ ] Commit and push

### The 12 investor questions chosen, and the source study begins (4pm)
- **D-071 · Bruno's 12 investor questions.** Anish liked Q1–Q3, so they stay. Bruno's themes: where data comes from; duplicated or deleted data; "why" questions.
  1. Which companies manage Apax's funds, and how many funds does each run?
  2. For each sponsor, how many companies report no parent, and why?
  3. Which sponsor companies have a lapsed or retired LEI, and when were we told?
  4. For company X, every fact we hold and the exact record or sentence each came from.
  5. Where do two sources disagree about the same company (name, status, parent), and what does each say?
  6. Which companies have a retired LEI that points to a successor, so they could be counted twice? *(needs a new GLEIF fact)*
  7. What changed between our fetches: new companies, changed names or status, ones no longer returned?
  8. Which companies did each sponsor buy or sell in 2025–26, and what reason did the announcement give?
  9. Which buys were add-ons (merged into an existing portfolio company), and what reason was given?
  10. For a deal in the news, trace fund → holding companies → the company bought, with a source for each link.
  11. Which funds did each sponsor close, how big were they, and when?
  12. Which banks or law firms advised on deals for more than one of our sponsors?
  - **Dropped:** "who controls UK company X" and the unanswerable LP question. Without the latter, no question tests whether a method says "not available". It can be added back.
  - **Why the "why" questions are worded as "what reason did the announcement give":** a graph can store the stated reason, tied to its sentence, but never the true reason.
- **D-072 · Companies House and the news both come in. The RDF system is completed first; Neo4j comes after.**
  - Each new source gets a **source study first**: real records, looked at together; what it provides, its structure, limits and traps. Then the fact design, then the pipeline.
  - Why: Bruno wants to understand each source before it's piped in, and to check that the sources fit the UK case study.
  - The cost: Neo4j, text-to-Cypher and Bloom all move to Wednesday, which is tight.
- **Companies House source study: findings F23–F33** in `docs/data-sources.md`. The headlines:
  - most fund vehicles are offshore (F23)
  - English LPs have no control records (F24)
  - ordinary companies' control chains climb cleanly (F26)
  - control comes in kinds and bands (F27)
  - history is kept (F28)
  - chains can loop (F29)
  - registration numbers are messy (F30)
  - a stated "no controller" exists (F31).

#### TODO
- [ ] Bruno reviews F23–F33 and explains them back; then decide the Companies House fact design (which questions are open is listed in the chat)
- [ ] Tuesday morning: news source study (2–3 real releases), then the identity rule

### Sources settled; Companies House design under review (5pm)
- **D-073 · Stay with three sources: GLEIF, Companies House and the news. The gaps become talking points.**
  - Why: the brief says *"Expect the data to be imperfect … represent these gaps openly"* and *"report … what did not work"*.
  - Richer data (fund investors, exact stakes) is private, and only paid databases have it. EDGAR would cover only about 15 US vehicles. Wikidata is a fallback for unworkable sources only.
  - The talking points are collected in `docs/talking-points.md`, for the write-up and the discussion with Anish.
- **Officers' fields as given** (checked on real records): name, role, appointment date, nationality, country of residence, **month and year** of birth, and a **service address** (usually the office, e.g. 5 Marble Arch), plus a stable officer ID link. **No email or phone.** The officer list is paged (35 per page by default; 96 in total for Bridgepoint Advisers Ltd).
- **D-074 · People: keep the details that best tell people apart.**
  - Keep: name, role, appointment and end dates, the officer ID (officers only), month and year of birth, nationality, and country of residence.
  - Why (Bruno): so two different people with similar names are never merged by mistake.
  - This is also the data-protection answer: each field kept serves a stated purpose (telling people apart). That is what data minimisation asks (UK GDPR Art. 5(1)(c)).
  - Companies House gives no email or phone.
  - Bruno's question swap (a question about people) is still to choose.
- **D-075 · Control is a "stake" node, not a note on an arrow.**
  - A stake links the company and its controller. It carries the share band, the vote band, the right to appoint directors, other kinds of control, and its start and end dates.
  - Why (Bruno): a stake is a **fact about the world**, not metadata about where a fact came from, so it doesn't belong in an RDF-star note. Shares, votes and board rights are **different kinds of power**: equity and control aren't the same thing, so each needs its own field.
  - The stake's own source and fetch date still go on RDF-star notes, as for every fact.
  - Open point (Bruno's rule applied to what exists): `fundManagedBy` keeps its status and start date on the note. Are those facts, too? Revisit when the Companies House schema is sketched.
- **D-076 · Queries use tidy values; the as-given values stay in the graph.**
  - Each number or name is stored as the source gave it (with its source), plus a tidy version made by a named rule.
  - Queries use the tidy version. Every tidying failure (e.g. a missing number) goes into a short report.
  - Why (Bruno): the raw value is how any answer is traced back to what the source actually said; the tidy value is what makes queries work.

### Companies House: schema approved; the build starts (4:40pm)
- **The schema is approved:** section 9 of `docs/schema/rdf-schema.md`, drawn at https://claude.ai/artifact/Eai2LvKuvt9XM4h8Gxbfgt (private).
  - Bruno's summary: Companies House adds control, people and status to GLEIF's identity, and every fact points to its source.
  - The only value both sources share is the Companies House number. GLEIF records it as `registeredAs`, and D-025 uses it to draw the `sameEntityAs` link.
- **D-077 · Officers: current and past.** Why: history with dates fits Q7 ("what changed") and costs little. Some officers are companies (corporate LLP members, nominee secretaries); they get the same as-given name plus a tidy link as a stake's holder (D-076).
- **D-078 · Companies reached only by climbing a control chain are fetched as "related", with no verdict.**
  - The climb goes up to 4 steps, UK companies only, and stops at loops (F29).
  - Why: the same as GLEIF's outside parents. The chain is Companies House's main value, but the scope rule was designed for name-search results.
- **Built:**
  - `src/seisa_kg/facts/ch_tidy.py`: the number-tidying rule (D-076, F30). "1899316" → 01899316, "Oc301825" → OC301825, and "B263996" (Luxembourg) is refused.
  - `src/seisa_kg/sources/companies_house.py`, run with `make fetch-ch`. It is now part of `make build`.
- **News source study: findings F34–F38** in `docs/data-sources.md`.
- **D-079 · Which releases: about 10 per sponsor, UK first.**
  - Per sponsor: about 6 deals (buys and add-ons), 2 exits and 2 fund closes, from 2025–26.
  - Prefer UK-based target companies; fill up with others if a sponsor is short.
  - Why: the questions need a mix of announcement types (Q8–Q12). UK targets let Companies House climb from the bought company up to the fund (Q10). Equal numbers keep the sponsors comparable.
- **D-080 · Bridgepoint's releases are found by web search, then downloaded from Bridgepoint's own site.** Why: their news list needs JavaScript (F34). This keeps all three sponsors on the same kind of source, their own website.
- **D-081 · Claude lists about 40 candidates (title, date, type, the target's country); Bruno approves the final 30 before they are downloaded for good.**
- **D-082 · Bridgepoint's releases are saved by hand by Bruno, from his browser, into `data/raw/news/bridgepoint/`.**
  - Their provenance is recorded honestly: "saved by hand from bridgepointgroup.com", with the save date.
  - Why: the site's bot challenge (F39) refuses programs, and getting around it would be wrong. A person reading the site is its intended use, and the source stays the sponsor's own website.

### News: approved releases, sentences, and the extraction design (5pm)
- **The approved 30 are in `config/news_releases.toml`:** 10 per sponsor.
  - Bruno saved Kayne Anderson Real Estate instead of GBA Group. That's a deal by Bridgepoint Group plc itself, not by a fund, and it stays as an interesting contrast.
  - Fund closes outside 2025–26 were allowed for Hg (Saturn 1, 2023) and Apax (Apax XI, 2024), because there were none in the window (F40).
- **Sentences:** `src/seisa_kg/extraction/sentences.py` gives about 1,000 numbered sentences (e.g. `apax-08#s05`) in `data/interim/news/`. Each release records how it was obtained (by the program, or saved by hand, D-082).
- **D-083 · The extraction design (approved):**
  - Gemini returns Deals (kind, target, buyers, sellers, funds, stake, value, status, stated reasons, advisers), FundCloses (fund, size, close type, date) and Mentions (people and organisations named).
  - **Every field carries a sentence ID and an exact quote.** Code checks the quote against that sentence; the model is not trusted to do this.
  - Names stay as written; matching them to LEI and `ch:` nodes comes later.
  - In the graph, a Deal or FundClose is a node (as D-036 and D-075). Its facts point to their sentence, and the sentence points to the release: fact → sentence → release → website.
- **D-084 · Model: `gemini-2.5-pro`, a pinned stable version, for the first version.**
  - It's built so the model is a one-word switch. Bruno plans to compare it with `gemini-3.8-flash` later (newer and likely more capable), using the same scorer.
  - Why pinned: results stay reproducible and explainable; a moving "latest" alias could change underneath us.
- **D-085 · A field whose quote doesn't match its sentence is rejected and logged, not retried.** The rest of the release still loads. The log is part of the honest results ("what didn't work").
- **First extraction run (gemini-2.5-pro):** 30 releases, 29 deals, 5 fund closes, 426 mentions; **36 fields rejected** by the quote check; about 195k tokens.
  - **F41:** Gemini rewrote amounts ("$1.393 billion" → "1393000000") despite "as written", and the check caught them.
  - **F42:** a whole release (Zuto) was lost, because Gemini wrote sentence IDs as "s01".
  - **F43:** adviser names and roles were sometimes paraphrased.
  - **F44:** the Helio exit was dropped, because only its kind failed.
- **Bruno's spot-check of 3 UK deals (Street Group, Foods Connected, mydentist), and his decisions:**
  - **D-086 · Price and valuation are separate fields.**
    - `price` is what the buyer agreed to pay; `valuation` is what the company is said to be worth, which nobody necessarily paid.
    - Whether a price has actually been paid is read from the deal's status. Why (Bruno): a valuation is theoretical until money moves.
  - **D-087 · Status is "completed" only when the text says completed, closed or has acquired.** "Secures", "to acquire" and "agreed" mean **agreed** (pending).
    - Why (Bruno): a secured deal can still fall through. Another source (e.g. a new Companies House controller) may later confirm completion.
  - **D-088 · The buyer is kept exactly as written (e.g. "funds advised by Bridgepoint"), plus a separate `sponsor` field.**
    - Why (Bruno): an adviser isn't necessarily the buyer. This is the sponsor-versus-fund distinction.
  - **D-089 · Short sentence IDs ("s01") are accepted when they can only mean this release's sentence.** This is a fixed code rule, and each use is counted.
  - **D-090 · A required field that fails the check is kept as "unknown", labelled with why, not dropped.**
    - Why (Bruno): dropping loses information. "Unknown" keeps the question visible, and can be filled in when another source answers it.
- **Second extraction run, with D-086 to D-090:** 30 releases, **30 deals**, 5 fund closes, 438 mentions; **9 fields rejected** (down from 36); about 202k tokens.
  - Zuto and Helio are recovered. Street Group now shows price "not disclosed", valuation "more than £200m" and status agreed. mydentist's buyer is "funds advised by Bridgepoint", with sponsor "Bridgepoint".
  - The remaining rejections are paraphrased adviser names (J.P. Morgan, Baird), two "agreed" quotes, and two buyers in one Hg release.
- **The graph now holds all three sources:** GLEIF, Companies House and the news. **31,437 facts → 104,304 triples, and every check passes.**
  - One query follows the full trail: deal → stated reason → exact quote and model → sentence → release → website.
- **Spotted for the next spot-check:**
  - Helio's `sponsor` came out as ECI Partners (the buyer's sponsor), but Bridgepoint is the selling sponsor. The sponsor field needs defining for exits.
  - Zuto says "completed": check it against D-087.

#### TODO (Tuesday 20 Oct, 10:00–18:00)
- [x] Companies House: fetched, parsed, in the RDF graph (D-074 to D-078)
- [x] News: 30 releases approved, sentences, Gemini extraction with quote checks, in the RDF graph (D-079 to D-090)
- [ ] Spot-check more extractions (at least one per sponsor per type); define `sponsor` for exits; check Zuto's status
- [ ] **Entity matching:** release names → LEI / `ch:` nodes, with 50 pairs hand-checked, precision and recall (brief deliverable)
- [ ] Questions Q4–Q12 in SPARQL, with sources and timings (the RDF system complete, D-072)
- [ ] Then Neo4j step by step (D-063 reopened), the "what changed" note, the questions in Cypher
- [ ] Text-to-SPARQL step 2 (Bruno's four choices), scored; later text-to-Cypher and vector search over the news sentences
- [ ] Compare `gemini-3.8-flash` with `gemini-2.5-pro` on extraction (D-084)
- [ ] Bruno's people question, and which question it replaces (D-074)
- [ ] Open point: should `fundManagedBy`'s status and start date move off the note (D-075)?
- [ ] Tests for the number-tidying rule and the quote check; README

### Fitting the sources together (5:30pm)
- **D-091 · One arrow per concept across sources, merging only where it's clearly the same idea (Bruno: "be conservative, but where it's obvious, do it").**
  - Merged: Companies House's registered office → `legalAddress`, and its company status → `entityStatus`. These are the same ideas as GLEIF's fields, with values kept as given.
  - Kept separate:
    - `registrationStatus`: about the LEI, not the company
    - `otherName` vs `previousName`: GLEIF's other names include trading names and translations
    - news `name`: as written in a release, not a legal name
  - Why: with one arrow and each value on its own sourced note, Q5 ("where do sources disagree?") becomes one simple query.
- **What the merge shows straight away (for Q5):**
  - **F45 · Names agree for all 153 linked companies.** Addresses agree for **none**, but only because of formatting ("5 MARBLE ARCH, LONDON, GB-LND, W1H 7EJ, GB" vs "5 Marble Arch, London, W1H 7EJ, United Kingdom"). Q5 needs a tidy comparison rule for addresses (like D-076), or every pair looks like a conflict.
  - **F46 · Status differs for 12 linked companies.** 5 are GLEIF INACTIVE vs Companies House dissolved: the same meaning in different words, which needs a value mapping. **7 are GLEIF INACTIVE vs Companies House active: real disagreements**, and exactly what Q5 is for.
- **`make build` now runs all three sources:** GLEIF → Companies House → news sentences and Gemini extraction (cached) → facts → graph → checks → questions. About 20 seconds from the cache.
- **SHACL checks 5–10 added:** Stake, Appointment, Person, Release, Deal and FundClose. All pass.
- **Schema doc section 10 written:** the news nodes, arrows and trail.
- Small note: the extraction report's token count includes cached answers, so it shows the cost of the original calls, not of the re-run.
- **D-092 · Status comparison through a mapping table (rule, for comparing only).**
  - Companies House "active", and the insolvency states in which the company still exists, count as ACTIVE. "dissolved", "removed", "closed" and "converted-closed" count as INACTIVE. An unknown word gets no key.
  - The original words stay in the graph.
- **D-093 · Address comparison by postcode plus building number, after tidying (rule, for comparing only).** The building is the first all-digit word before the postcode, wherever it sits (care-of lines and floors vary in order).
- **D-094 · Fresh data comes in through an explicit `make refresh`, which fetches a new dated snapshot and keeps the old one.** `make build` always uses saved data, so it stays fast and repeatable. **Decided; to be built Tuesday** (it touches every downloader and the GLEIF parser's folders).
- **Q5 (first version: status and address) runs: 15 disagreements**, in `src/seisa_kg/rdf/queries/q05_source_disagreements.rq`.
  - **7 status conflicts:** GLEIF INACTIVE vs Companies House active (Apax Europe V funds, HgCapital 6 D, Bridgepoint Credit II "D").
  - **6 real address conflicts**, e.g. Bridgepoint Credit at 95 Wigmore Street (GLEIF) vs 5 Marble Arch (Companies House).
  - **F47 · 2 are false alarms from a typo in Companies House itself** ("1royal Plaza"): the rule can't see the building number. That's a known limit, and a good "what didn't work" example.

#### TODO (Tuesday 20 Oct), updated
- [ ] **First: entity matching** (news names → `lei:` / `ch:`). Bruno thinks about the approach first; then 50 pairs hand-checked, with precision and recall. Example of the difficulty: "mydentist" is a brand, and its legal name differs.
- [ ] Build `make refresh` with dated snapshots (D-094)
- [ ] Q5: add names and parents to the comparison; Q4 and Q6–Q12 in SPARQL
- [ ] Then the earlier list: spot-checks (Helio's sponsor, Zuto's status), Neo4j step by step, text-to-SPARQL, 3.8-flash comparison, people question, tests, README

### End of day (6pm)
- **D-095 · Tuesday's goal: the whole MVP, including the labelled property graph (LPG, Neo4j).**
  - Morning: finish the RDF system (matching, `make refresh`, the remaining SPARQL questions).
  - Afternoon: the LPG, step by step (concept → schema sketch → "what changed" note → builder → Cypher questions → Bloom).
  - Why (Bruno): Seisa works with property graphs, so the LPG must be solid, not rushed into Wednesday.
  - PLAN.md §6 is updated to match.
- **A study guide for Tuesday morning** (1.5–2 hours of reading) covers the whole pipeline from scratch, today's changes, tomorrow's TODOs and questions for the team. It's saved outside the repo, like the first one.
- **Numbers at the end of the day:**
  - 32,538 facts → 107,615 lines of `graph.ttl` (107,607 triples); 10 SHACL checks plus 3 code checks pass; 33 tests pass.
  - Nodes: 1,152 company nodes (GLEIF and Companies House), 51 stakes, 880 appointments, 839 people, 30 releases, 968 sentences, 30 deals, 105 advisers, 5 fund closes, 438 mentions.

## 20 Oct 2026 (Tuesday)

### Entity matching: design (morning)
- **Evidence first:** the news holds 206 names (30 targets, 33 buyers, 38 sellers, 105 advisers). An exact match on legal name links only **1** ("Bridgepoint Group plc").
  - The news mostly names **families**, not single legal entities: "Saturn Fund" fits **28** of our entities, "Apax Digital Funds" 13, "Bridgepoint Direct Lending II" 11, "Bridgepoint Advisers" 6. "Apax Partners LLP" fits exactly 1.
  - Most bought or sold companies (Zuto, mydentist, IRIS…) have **no node** in our graph: it holds the sponsors' own structure, not their portfolio companies.
- **D-096 · Matching links news names only to nodes we already have (option A). No new Companies House records for portfolio companies (option B).**
  - Why (Bruno): a trial project should stay contained and explainable to the team; too many moving parts would make it confusing.
  - The cost: the bought companies stay unlinked ("unresolved"). Adding them (B) is named in the write-up as the next step, e.g. Companies House search checked by a rule plus Gemini.
- **D-097 · Two kinds of link.**
  - `sameEntityAs`: the name is exactly one of our legal entities.
  - `refersToGroup`: the name points at a sponsor or a fund family (e.g. "Funds advised by Apax", "Saturn Fund"), not at one company. True, but vaguer, and the arrow says so.
  - Why: "funds advised by Apax" and Apax's legal entities are different legal things (GP vs sponsor), so `sameEntityAs` would be a wrong link.
- **D-098 · Strict rule: link only when exactly one candidate fits.** Two or more candidates: record "ambiguous" with the candidates, and pick none.
  - Why (Bruno): a wrong link is worse than a missing one; private equity and finance demand that strictness. The Seisa primer also calls a wrong merge "the most damaging" error.
- **D-099 · Every name gets exactly one outcome:** linked (`sameEntityAs` or `refersToGroup`), ambiguous (with candidates), out of scope, non-entity (with its kind), or unresolved.
  - **Out of scope:** a real company that our graph doesn't cover (e.g. "KKR"); recorded with that reason.
  - **Non-entity kinds:** unnamed group of people ("angel investors"), unnamed holders ("OneStream shareholders"), unnamed vehicle ("a newly formed continuation vehicle"), named person ("Gordon Hawes").
  - Why (Bruno): negative information is still information; the kind says what sort of non-entity it is. A code rule can't tell "KKR" from "Zuto", so Claude lists the labels and Bruno approves them.
- **D-100 · Q10 reworded to fit D-096:** "For a deal in the news, trace the buyer named in the release to our legal entities and up to the sponsor, with a source (sentence or registry record) for each link."
  - Why: the old wording ended at the bought company, which isn't in the graph under option A.
- **Open:** whether an LLM may help with ambiguous names (Bruno asked which verification methods exist).
- **D-101 · No LLM for ambiguous names in the MVP: they stay "ambiguous" with their candidates.**
  - Why (Bruno): easy to explain, and the time goes on finishing the whole system rather than going deep here. The system should report well when it knows the answer and when it doesn't. The main thing is to avoid hallucinated links and keep everything verifiable from a source.
  - Methods named for the write-up as the next step: closed choice from the candidate list, the quote check we already use, a clue check in code (e.g. "Saturn 3"), agreement between runs or models, a date sanity rule, human sign-off.
  - Fact behind it: in our data the ambiguity comes from the text not containing the deciding clue ("Saturn Fund": 28 candidates), and no method can recover what isn't there.
- **Step 1 built: `src/seisa_kg/matching/candidates.py`** writes `docs/matching-candidates.md` (253 names: 206 deal and adviser names, plus 47 sponsor and fund names). It decides nothing.
  - Findings: the only exact matches ("Apax Partners LLP", "Bridgepoint Group plc") each hit a `ch:` and a `lei:` node that are already the same company (D-025). A sponsor word fits 91–252 entities. The family search alone gave a false match ("Rothschild & Co" → two "Edmond de Rothschild" funds).
- **D-102 · A `ch:` and `lei:` pair joined by `sameEntityAs` counts as one company when counting candidates.** Both nodes stay; nothing is merged.
  - Why: D-025 already says they are the same company; counting them as two would make the strict rule refuse every link.
- **D-103 · Sponsor word alone → `refersToGroup` that sponsor. Sponsor word plus a fund family (e.g. "Apax Digital Funds", 13 entities) → `refersToGroup` the sponsor, with the family listed as "possible, none picked".** A family with no sponsor word ("Saturn Fund") stays ambiguous.
  - Why (Bruno): we're sure of the sponsor and keep what we found, but only link to one entity when the match is very clear.
- **D-104 · Every adviser is out of scope by one rule** ("an outside adviser; our graph covers the sponsors' own companies").
  - Why: all 105 are banks, law firms or consultants, and none contains a sponsor word. One rule is explainable and saves labelling 105 names by hand. Risk: a sponsor company that advised would be mislabelled.
- **Step 2 built: `src/seisa_kg/matching/outcomes.py`** writes `docs/matching-report.md`. 253 names: out of scope 144, `refersToGroup` 59, unresolved 30, non-entity 9, `sameEntityAs` 6, ambiguous 5. Nothing added to the graph yet.
- **D-105 · The label list (`config/match_labels.toml`, 39 names) is approved** as drafted. Bruno read the matching report and found nothing wrong (still learning, so the hand-check is the real test).
- **For the write-up:** "BDC V" (Bridgepoint Development Capital V) is unresolved because it contains no sponsor word. It's a real miss, and the cost of choosing precision over recall.
- **D-106 · The 50-pair hand-check uses a random sample** of distinct names, with a fixed seed so it can be repeated.

#### TODO (after the project is finished): improve performance
- [ ] Extraction: "commitments from Bridgepoint Direct Lending II" came out as a deal *target*; it's a fund commitment.
- [ ] Matching: "Hg Saturn 1 Fund" and "Apax Digital Fund I" get no "possible" list, because "1" and "I" appear in no legal name (roman and arabic numerals aren't treated as the same).
- [ ] Matching: abbreviations such as "BDC V" are missed.
- [ ] Matching: the LLM methods named in D-101.
- **D-107 · The hand-check sample is stratified, not plain random (replaces D-106).** 50 distinct names: every `sameEntityAs` (2) and ambiguous (2) name, then 15 `refersToGroup`, 5 non-entity, 8 unresolved and 18 out of scope, picked at random within each group with a fixed seed.
  - Why: only 31 of the 184 distinct names are links, so a plain random 50 would hold about 8 links, which is too few to measure precision. Stratifying keeps the randomness but guarantees each outcome is tested.
  - The cost: recall must be **weighted** by each group's real size, because the sample over-represents links. The group sizes are saved with the sample.
  - Bruno judges each name **blind**, seeing the sentence but not the code's answer, to avoid anchoring.
- **Bruno's concern:** checking by hand doesn't scale to hundreds or thousands of names. It's fine for this trial, but evaluation needs an automated method. That work comes after the whole pipeline is finished.

#### TODO (after the pipeline is finished): evaluation at scale
- [ ] Find ways to check matching without a person checking every name. Ideas to study:
  - names that carry an identifier (a company number or LEI in the text) as free answer keys
  - agreement between sources
  - an LLM as judge, with a small human audit of the judge
  - the hand-checked 50 kept as a regression test
- **D-108 · Matches go into the graph as Match nodes (option 1).** Each name in the news gets one `ex:Match` node, holding the name as written, the outcome, the reason and the rule. A link (`sameEntityAs`, `refersToGroup`) or candidates hang off it. The news node points to it with `<role>Match`, e.g. `buyerMatch`.
  - Why (Bruno): notes (RDF-star) are for metadata about a fact only. A match is a judgement in its own right, so it's a node.
  - Also: every outcome, including the non-links, gets the same explicit home. It carries straight over to the property graph this afternoon.
- **Reminder:** fill in the hand-check sheet at about 4:30pm (it's on the TODO list).
- **Matching is in the graph.** `src/seisa_kg/matching/facts.py` adds the Match nodes in `make facts`, with SHACL check 11 and schema section 11.
  - 34,180 facts → 112,533 triples; every check passes; 39 tests pass (6 new ones, in `tests/test_matching.py`, pin the strict rules).
  - Tested end to end in SPARQL: deal → `buyerMatch` → Match → `sameEntityAs` → `lei:213800KFNMVI8PDZX472` (BRIDGEPOINT GROUP PLC), with the sentence returned through the note.

#### TODO (Tuesday 20 Oct), updated at 12:20
- [x] Entity matching: design (D-096 to D-108), candidates, outcomes, Match nodes in the graph, check, tests, schema section 11
- [ ] **Bruno: fill in `eval/matching-sample.csv` at about 4:30pm** (50 names, blind), then Claude scores precision, weighted recall and agreement. *(Moved to Wednesday, D-116.)*
- [x] Bruno explains matching back, with no code open (D-067 step 5)
- [x] **From 1pm: the property graph (Neo4j)**, step by step
- [ ] After the property graph: `make refresh` (D-094); Q4, Q6–Q12 in SPARQL (Q10 as reworded in D-100); Q5 names and parents. *(Questions moved to Wednesday; `make refresh` dropped, D-115.)*

### Bought companies get a node (about 1pm)
- **D-109 · Every deal target with no other match gets a `NewsOnlyCompany` node: one per name (after tidying), connected through its Match.** The Match outcome changes from "unresolved" to **"news-only"**, with a link Match → `namedCompany` → `ex:newsonlycompany/<name>`. Targets only, for now.
  - **What "NewsOnlyCompany" means (Bruno's wording for the team):** a company known only from the news. It has no registry ID and nothing about it is verified. It's a different type from the `lei:`/`ch:` companies, so it's never mistaken for one.
  - Why a node (Bruno): the bought company should at least be logged as a company and connected, even without all its information. Q8 and Q9 return companies, and a property graph wants a company node at the end of a deal.
  - Why one node per name (Bruno): it's tidy, and it lets someone see what other deals involved the same company. It's for illustration only and can't be verified yet.
  - The risk: two different companies with the same name would share one node. That's a match by name, so the node says so (rule D-109). Today no target name repeats, so nothing is merged yet.
  - Refines D-096: still no new Companies House records. If we ever look a target up (option B), the link goes on this node.
  - No separate `acquired`/`sold` arrow: the deal's `dealKind` says what happened (one arrow per concept, D-091). It isn't called "portfolio company" either, because that's only true for some deal kinds (after an exit it no longer is one).
- **For later:** the other companies named in the news (sellers, trade buyers), and advisers as nodes for Q12.
- **Built:** 29 NewsOnlyCompany nodes. Outcomes now: out of scope 144, `refersToGroup` 59, news-only 29, non-entity 9, `sameEntityAs` 6, ambiguous 5, unresolved 1 ("BDC V"). 34,269 facts → 112,800 triples; SHACL check 12 added; every check passes; 41 tests pass.
  - **A bug was caught and fixed:** the standalone report scripts read the fact list, which now holds the Match rows' own `sameEntityAs` links. Those confused the "joined pair counts once" lookup, and the report briefly showed 0 `sameEntityAs`. The graph itself was never affected (`make facts` matches before the Match rows exist). The lookup now only counts `lei:` → `ch:` pairs, and a new test pins it.
  - The hand-check sheet was regenerated with a news-only group (7 names) and an unresolved group (1 name). Bruno hadn't started filling it.

### Property graph: provenance input from Seisa (about 1:30pm)
- **Pablo (founding engineer), on how Seisa thinks about it:**
  - **Access control (ACL) is the most important thing.** Whether it lives in metadata (properties) or as explicit nodes depends on the design, and it varies.
  - **The schema is judged on:** cost, retrieval (latency and accuracy), and what you want to expose (ACL).
  - **More metadata as properties makes a property graph faster and smaller,** but it's a trade-off.
- **Facts checked (Claude):**
  - Our Neo4j is the **Community** distribution (2026.09.0), which has no role-based security, so every user sees everything.
  - Fine-grained access control (by label, relationship type or property name) is documented as an **Enterprise** feature.
  - So for the trial, ACL is a **design consideration** (shape the graph so it *could* be locked down), not something we enforce.
- **Sizing on our data (34,269 facts):**
  - 23,757 value facts, 6,199 link facts and 4,313 type facts
  - 3,241 source records and 14 rules
  - 7,758 distinct (node, record-or-rule) pairs behind the value facts
  - 2,607 facts with extra details (quotes, dates)
- **D-110 · Provenance in the property graph: option C, receipt relationships.**
  - Values are plain properties on their node. Each node has one `DERIVED_FROM` relationship per source record (or `GENERATED_BY` per rule), saying which of its properties that record backs, plus any quotes or details as flat lists.
  - A link (relationship) is one fact, so its source sits on the link itself as properties.
  - Records, sentences, rules and people are their own labelled nodes.
  - Why, in Pablo's terms:
    - **Cost:** about 7,800 extra relationships, against about 100,000 extra elements for a node per fact (option B).
    - **Retrieval:** a value is read straight off its node (fast), and its source is exactly one hop away (accurate).
    - **Exposure (ACL):** anything that might need hiding (people, raw text, our judgements) sits behind its own label, which is what Neo4j's access rules grip onto.
    - It keeps the RDF promise that every fact traces to its source, with the same facts in both graphs.
  - Evidence:
    - The Neo4j modelling guide: relationship properties are for per-connection data, and a value repeated across many relationships belongs in its own node (one source record backs about 10 facts).
    - Neo4j properties can't hold nested maps, so the receipts use flat lists.
  - Weakness, for the write-up: a value that changes between fetches keeps only its latest value as a property. History needs a decision with `make refresh` (Q7).
  - (Bruno to restate the why in his own words after lunch.)
- **D-111 · GLEIF and Companies House companies: Bruno's rule is "one node only if every value on it is linked to a clear source; otherwise separate them."**
  - Applying the rule (Claude, for Bruno to confirm):
    - Where the two registers **agree**, a merged node could back one value with two receipts.
    - Where they **disagree** (Q5: 15 cases, on status, address and name), one property can't hold both values with their sources, so a merged node would have to pick one. That would silently correct a source (D-029).
    - So the rule gives **two nodes**, joined by `SAME_ENTITY_AS {rule: "D-025"}`, as in RDF.
- **Drafted during Bruno's lunch: `docs/schema/lpg-schema.md`** (for review; nothing built in Neo4j). It covers labels, relationships, the provenance mapping, the reconciliation checks, a first "what changed" note, and 4 open points.

#### TODO (Tuesday afternoon, after lunch)
- [x] Bruno: restate D-110's why in his own words; confirm D-111 (two nodes)
- [x] Bruno: review the draft property graph schema and decide its 4 open points (details on names, list properties, scope as a relationship, history)
- [x] Then the builder, step by step: constraints → nodes → relationships → receipts → reconciliation checks
- [ ] Cypher questions; Bloom view *(moved to Wednesday)*
- [ ] 4:27pm: the hand-check sheet *(moved to Wednesday, D-116)*

### Property graph: decisions confirmed and the build starts (about 2pm)
- **D-110's why, in Bruno's words:** "Receipt relationships, so the source is obvious on the graph itself. The values are plain properties that can be queried fast and cheaply. These links can be hidden if need be."
  - Claude's precision note: Neo4j's access rules hide **relationships by their type** (e.g. all `DERIVED_FROM`) and **nodes by their label** (e.g. all `SourceRecord`). Both are possible, in Enterprise.
- **D-111 confirmed:** GLEIF and Companies House companies stay two nodes, joined by `SAME_ENTITY_AS {rule: "D-025"}`.
- **D-112 · The four open points in the schema draft (Claude's recommendations, accepted by Bruno):**
  - a. Names with their own details (`otherName`, `previousName`; 224) become small `:Name` nodes. Why: each name is a thing with its own details, and a list property can't hold details per item.
  - b. Several values of one kind (`statedReason`, `sicCode`) are list properties for now. Why: Q8 only reads them out; nodes would help only if reasons were shared or grouped.
  - c. The scope decision becomes a relationship, `IN_SCOPE_OF {verdict, reason, rule}`. Why: it links exactly two things and has its own details.
  - d. History (a value changing between fetches) is parked until `make refresh`, and named in the write-up.
- **Neo4j checked before building:** the project's own server is running, version 2026.09.0 **Community**; the database was empty (0 nodes, no constraints).
- **Property graph step 1 built** (`src/seisa_kg/lpg/build.py`): connect, empty the database, and 15 uniqueness rules on `id` (one per label).
- **Step 2 built: nodes and their values, by the five rules** (type → label; real dates and booleans; list properties where a fact kind ever has several values; `:Name` nodes; companion properties such as `legalNameLanguage`). 6,334 nodes; every label's count matches the fact list.
- **Correction (found by step 2's own check): the node counts we quoted since Monday were counts of *type facts*, not of distinct nodes.**
  - One node can be typed by several records: GLEIF states each entity on two fetch dates, and one officer appears in the officer lists of up to 24 companies, so they're typed 24 times.
  - **The true counts, confirmed in RDF with `COUNT(DISTINCT ?s)`:**
    - **648 companies (489 GLEIF + 159 Companies House)**, not 1,152 (993 + 159)
    - **466 people**, not 839
  - The other counts were right: 880 appointments, 51 stakes, 30 deals, 105 advisers, 438 mentions, 153 GLEIF ⇄ Companies House pairs.
  - Corrected in the recap page and the property graph schema. The 19 Oct numbers above and the study guide PDF still show the old figures.
  - The first step 2 check made the same mistake. It now counts distinct nodes, and the RDF graph agrees.
  - A talking point: the reconciliation check caught a wrong number in our own reporting on its first run.
- **D-113 · A link that points to a company we never fetched keeps a stub node labelled `:NotFetched`, holding only its id** (e.g. `ch:04572042`).
  - Why (Bruno): it's the most honest option. In Neo4j a relationship needs a node at both ends; without a stub, 11 links (corporate officers and holders whose records our climbing rule didn't fetch) would silently disappear.
  - It mirrors RDF, where those links end at a bare id. It's not labelled `:Company`, so the company count still matches RDF (648).
- **D-114 · Relationship names follow Neo4j's convention:** the fact name in capitals (`fundManagedBy` → `FUND_MANAGED_BY`), with four renames where a bare noun reads badly as a verb:
  - `company` → `OF_COMPANY`
  - `holder` and `officer` → `HELD_BY` (one concept, one name, as in D-091)
  - `adviser` → `HAS_ADVISER`
  - the scope decision node → `IN_SCOPE_OF {verdict, reason, rule}`
  - Every relationship carries its source (`record` or `rule`, D-110) and any details from the fact list (e.g. GLEIF's `startDate`).
- **Fact:** the 4,263 link facts are all distinct (no link is stated twice), so each becomes exactly one relationship.
- **Step 3 built: relationships.** 4,888 relationships of 24 types, plus 7 `:NotFetched` stubs. Every type's count matches the fact list.
  - Traced in Cypher: deal → `BUYER_MATCH` → Match → `SAME_ENTITY_AS {rule: D-098}` → BRIDGEPOINT GROUP PLC → `SAME_ENTITY_AS {rule: D-025}` → `ch:11443992`; `IN_SCOPE_OF {verdict: In}` → Bridgepoint.
- **Code review before committing (Bruno asked for a double check). Three fixes:**
  1. The step 2 node check counted source records, sentences and names **from the builder's own output**, so it could never catch a builder bug there. It now works them out from the fact list, as the relationship check already did.
  2. A fact kind with several values *and* per-value details would have silently overwritten its companion property. None exists today (`otherName` and `previousName` are `:Name` nodes), but the build now stops with a clear message instead of guessing.
  3. The same link stated by two records would have become **two** relationships, where RDF holds one triple with two notes. None exists today, but `make refresh` (D-094) will create them. The build now stops with a message, so the decision (one relationship with a list of records) is made then, not by accident.
  - 6 new tests in `tests/test_lpg_build.py` pin the builder's rules (no Neo4j needed); 47 tests pass.

### The schedule to Thursday, and step 4 (about 3pm)
- **D-115 · New schedule (Bruno):**
  - **Wednesday:**
    - 10:00–13:00 building (11:00–11:30 is Bruno's EF interview): remaining questions, a small three-way comparison, timings
    - 13:00–15:00 README and write-up, then freeze at 15:00
    - 15:00–18:00 review and rehearsal with no code open
  - **Thursday:** morning review, presenting early afternoon.
  - Why: the explain-back is scored highest, but the three-way comparison is a brief deliverable, so the morning goes on building and the afternoon on review. Thursday morning adds a final rehearsal.
  - Dropped for time (Claude's proposal from the plan's drop list; confirm at the freeze): `make refresh` and Q7, and the gemini-3.8-flash comparison. Each is named in the write-up as next work.
  - PLAN.md §6 is updated to match.
- **Bruno's use of Claude Code, rated (Bruno asked):** about 7/10. Strengths: he set a working agreement and sticks to it; he asked Pablo for evidence; he originates ideas (NewsOnlyCompany, "notes are metadata only", D-111's principle); he asks for verification. To improve: say one way a recommendation could be wrong before accepting it; run each step himself and read the output; keep a one-page "in my own words" sheet.
- **A second data-loss bug, found while preparing step 4 (in step 2's `:Name` nodes).** `ch:01899316` had the **same** former name in two periods (1989–1997, then 3 days in 1997). One node per name kept only the first period's dates. The node check didn't catch it, because it made the same assumption.
  - Fix: a `:Name` node's id now includes its details (dates, type), so the same name in two periods is two nodes. The checks count the same way.
- **Found in the data:** 198 fact rows are exact repeats (the same person listed twice in one officer list, e.g. two appointments to one company). They're the same fact and get one receipt entry. (RDF also stores them once.)
- **Step 4 built: receipts (D-110).** 6,545 receipts (`DERIVED_FROM` to source records and sentences, `GENERATED_BY` to rules). Every value and label fact is listed in exactly one receipt. Bruno ran it and inspected the Kayne Anderson deal in Neo4j Desktop:
  - the valuation's quote sits on the arrow to sentence s01, not on the Deal node
  - the 7 stated reasons each point to their own sentence
  - the aligned lists (`properties` / `values` / `quotes`) are read by position
  - Facts with no receipt on purpose: a sentence's own text and a rule's own label (they *are* the source).
- **Step 5 built: one command builds both graphs, and they're proven to agree.**
  - `make lpg` (after `make rdf`) builds the property graph; `make build` now runs both graphs end to end in about 24 seconds from the cache.
  - New direct check: the RDF file vs Neo4j. 14 node types (distinct nodes per type) and 22 relationship types (distinct link triples per kind) are all equal.
  - Any failed check (nodes, relationships, receipts, RDF vs Neo4j) stops the build with an error, so it can't finish with graphs that disagree.
  - Neo4j must be running first (`make neo4j-start`).
- **Property graph totals:** 6,342 nodes (6,335 plus 7 `:NotFetched` stubs); 4,889 relationships (one more `HAS_PREVIOUS_NAME` since the two-period name fix) plus 6,545 receipts.
- **Finding: why each of the 9 extraction rejections failed** (read one by one for Anish's page):
  - **The model's (3):**
    - an inferred name: "Tom Staff" from "Tom and Heather Staff", caught by check 3
    - a shortened quote with "..." (Klass Capital, Salem Partners), caught by check 2
  - **Ours (6):**
    - our sentence splitter cut at initials, "Robert W." | "Baird" and "J.P." | "Morgan" (4 fields)
    - apax-04's own teaser line on the page stops mid-word ("to acqui"), and Gemini quoted the full words from the next sentence (2 fields)
  - So the quote check catches errors in our own text preparation, not only the model's.
- **Page for Anish:** https://claude.ai/artifact/2ccEV9MtsnDwL1J2GWZepn (the extraction and the quote check, with a real example and the 9 rejections).
- [ ] *(after the project)* Fix the sentence splitter so it doesn't split at initials ("W.", "J.P.").
- **The hand-check stays (it's required: Trial brief task 5, "around fifty pairs", and the deliverables list). It's timeboxed to 15 minutes at 5:15pm.** Bruno questioned its value ("Anish cares about learning the system, not menial work"). The answer: judging the names *is* learning the matching rules, and Seisa's primer says automated judges "must be calibrated against domain experts", so the 50 are the reference any scaled-up evaluation would need.
- **Found in Seisa's primer, for D-110:** "Access rules must therefore apply during traversal". That's Seisa's written position on access control, matching Pablo's advice.
- **Finding (while building the Cypher crash course):** rule 3 (a fact kind with several values on one node becomes a list) applies per fact kind *across all node types*. Some people have two spellings ("GRANT, Hamish Thomas" and "…, Mr."), so `name` is a list on every node, even an adviser's (`["EY"]`). Queries read it with `name[0]`.
  - [ ] *(after the project)* Consider applying rule 3 per (label, fact kind).
- **Cypher crash course for Bruno:** https://claude.ai/artifact/41DXx1yC9Yt6bTFdhyhn71 (9 lessons on our own graph, every query and result checked live, a SPARQL phrasebook, 5 exercises, and Q1 left as his task).
- **D-116 · The hand-check moves to Wednesday morning, first thing (15 min).** The rest of Tuesday goes on understanding SPARQL and Cypher.
  - Why (Bruno): no headspace for it today; understanding the two query languages is the best value for the rest of the day.
  - It's still required (brief, task 5). PLAN.md Wednesday is updated.
- **SPARQL practice tool:** `scripts/sparql.py` runs any query (or `.rq` file) against `graph.ttl` and prints a table with the time taken. It adds the usual prefixes for practice queries. (Oxigraph has no query window like Neo4j Desktop.)
- **SPARQL crash course for Bruno:** https://claude.ai/artifact/4NhJguTLGHQ8C8tmjPt7EG (9 lessons matching the Cypher course, every query checked on our graph).
  - Findings noted in it: SPARQL property paths count start–end *pairs* (77) while Cypher counts *routes* (81).
  - Our IRIs contain "/", so `ex:rule/D-025` must be written `ex:rule\/D-025` or as a full IRI in a query.
  - Bridgepoint's legal name has two notes (fetched 16 and 18 Oct), which duplicates rows when joining through notes.

### End of day (6pm)
**What Tuesday built:**
- **Entity matching (D-096 to D-109).**
  - Strict rules: link only when exactly one company fits; a sponsor's name links to its group; every name gets exactly one outcome.
  - Match nodes in the graph; bought companies get `NewsOnlyCompany` nodes.
  - 8 tests pin the rules.
  - The stratified 50-name hand-check sheet is ready. Scoring waits for Bruno's answers (Wednesday, D-116).
- **The property graph (D-110 to D-114), built step by step, with Bruno running each step:**
  - uniqueness rules → nodes → relationships → receipts → a direct RDF-vs-Neo4j check
  - `make build` now builds **both graphs in about 24 seconds**, and stops with an error if any check fails.
- **Three bugs and one wrong number, all caught by checks or by review, and all fixed:**
  - the "1,152 companies / 839 people" counts were counts of type facts; the true figures are **648 / 466**
  - a node check that trusted the builder's own output
  - a `:Name` node that lost a second period of the same former name
  - Match links leaking into the "pair counts once" lookup
- **Learning material for Bruno:**
  - the recap page: https://claude.ai/artifact/CGvQgMeZi2wpGvAYQxNRdR
  - the extraction page for Anish: https://claude.ai/artifact/2ccEV9MtsnDwL1J2GWZepn
  - the Cypher crash course: https://claude.ai/artifact/41DXx1yC9Yt6bTFdhyhn71
  - the SPARQL crash course: https://claude.ai/artifact/4NhJguTLGHQ8C8tmjPt7EG
  - the SPARQL practice tool: `scripts/sparql.py`
- **Seisa input:**
  - Pablo said access control matters most, and a schema is judged on cost, retrieval and exposure.
  - The primer says "access rules must apply during traversal". Both back D-110.

**Numbers at the end of the day:**
- Fact list: 34,269 facts. RDF: 112,800 triples; 12 SHACL checks plus 3 code checks pass.
- Property graph: 6,342 nodes (incl. 7 `:NotFetched`), 4,889 relationships and 6,545 receipts. Every count matches the fact list and the RDF graph.
- Companies: 648 (489 GLEIF + 159 Companies House, 153 joined). People: 466. Matches: 253 (out of scope 144, `refersToGroup` 59, news-only 29, non-entity 9, `sameEntityAs` 6, ambiguous 5, unresolved 1).
- 47 tests pass.

#### TODO (Wednesday 21 Oct; D-115, D-116)
- [ ] **10:00 · the hand-check, first (15 min):** Bruno fills `eval/matching-sample.csv` blind. Claude scores precision, weighted recall and agreement, then goes through each disagreement.
- [ ] **Cypher questions:** Bruno sketches Q1 first (the crash course's last section). Then Q1–Q3 and Q5 in Cypher, with a runner that saves `docs/answers-lpg.md`, compares each answer with SPARQL, and times both (median of several runs).
- [ ] **The remaining questions in SPARQL and Cypher:** Q4, Q6, Q8–Q12 (Q10 as reworded in D-100; Bruno has a Q11 SPARQL exercise).
- [ ] **A small three-way comparison:** text-to-SPARQL vs text-to-Cypher vs vector search over the news sentences, on about 10 questions, scored for correctness and citations.
- [ ] **Visualisations:** a Bloom view of fact → source, plus one other.
- [ ] *(11:00–11:30: Bruno's EF interview)*
- [ ] **13:00–15:00:** README (one command builds both graphs; Neo4j must be running) and the ~2-page write-up, including the talking points.
- [ ] **15:00 freeze:** `make build` from a clean copy, tests, commit, push.
- [ ] **15:00 · flashcard deck:** Claude builds an interactive deck from the diary, using the plan agreed on Tuesday evening (14 decks, about 100 cards, written as Seisa's likely questions).
- [ ] **15:00–18:00 · review with no code open:** the decisions Bruno *accepted* first (D-102 to D-104, D-112, the label list, the naming renames), then Seisa's expected questions; Claude quizzes.
- Dropped for time (D-115): `make refresh` and Q7, and the gemini-3.8-flash comparison. Both are named in the write-up as next work.

- **Vector search crash course for Bruno:** https://claude.ai/artifact/A2STSy95grjHFVG6SuZswB
  - Built from a real demo run: 12 news sentences and 6 questions embedded with `gemini-embedding-001` (3,072 numbers per sentence), at negligible cost; the run is kept in the scratchpad, not the repo.
  - Findings for the write-up and tomorrow's comparison:
    - right answers scored 0.76–0.82 and wrong ones 0.61–0.74, so **no score threshold separates them**
    - "How many deals did Hg do?" can't be counted, and its top hit is a fund close
    - "Which company manages Apax's funds?" returns a plausible but wrong sentence (0.70); the answer is only in GLEIF
    - the splitter's "J.P." cut also degrades search
  - Tomorrow's decisions for Bruno (D-067): embedding model, chunk size, k, where the vectors live (in memory vs Neo4j's vector index), and whether to allow "not found".
