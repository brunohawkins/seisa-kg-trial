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
- [ ] Bruno: reopen VS Code at `~/Projects/seisa-kg-trial` (or through the Desktop shortcut)
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
- [ ] Bruno: delete the `~/Projects` folder in Finder. It only holds Claude Code's placeholder file.
- [ ] Bruno: if wanted, re-apply the custom Work icon to `~/Work Projects` (Finder → Get Info → paste the icon onto the folder icon)
- [ ] Bruno: reopen VS Code at `~/Work Projects/seisa-kg-trial` (or through Desktop → Work)
- [ ] Next: RDF schema sketch
