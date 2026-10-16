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
  - The password is still Neo4j's default, `neo4j`/`neo4j`. Bruno sets his own on first login, so the password never passes through the AI tools.
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
- [ ] **Bruno:** set the Neo4j password at `http://localhost:7474`, and connect Neo4j Desktop to `bolt://localhost:7687`
- [ ] Look up the reporting-exception reasons for a sample of entities (`NON_CONSOLIDATING`, `NATURAL_PERSONS`, …), to inform the RDF schema
- [ ] Check that each chosen sponsor has enough public news releases (about 10 each)
- [ ] Sunday: sketch the RDF schema

### End of day (Friday 16 Oct)
- The Companies House API key is registered. Bruno holds it.
- The Neo4j password is set by Bruno in the browser, so it never passes through the AI tools.
- `.env` is created by Bruno (`cp .env.example .env`); he types in the Companies House key and the Neo4j password himself (D-021).
- Neo4j is stopped at the end of the session with `make neo4j-stop`.

### TODO for Sunday
- [ ] `make neo4j-start`, and check that Neo4j Desktop connects to `bolt://localhost:7687`
- [ ] Sample GLEIF's reporting-exception reasons for the three sponsors
- [ ] Check there are about 10 public news releases per sponsor
- [ ] Sketch the RDF schema together (RDF-star provenance, D-015)
- [ ] Build the cached GLEIF downloader for Hg, Bridgepoint and Apax
