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
