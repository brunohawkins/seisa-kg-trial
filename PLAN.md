# Seisa trial: project plan (v3)

**Status:** v3 (19 Oct 2026): the timeline (§6) is rewritten for finishing on Wednesday 21 Oct and presenting on Thursday 22 Oct; the cuts in §6 await Bruno. Earlier: v2.2. On 16 Oct 2026 Bruno accepted every recommendation in this plan, chose RDF-star for RDF provenance (D-015), and made the translation layer a post-task extension (D-016). Items marked **[Decided: D-0xx]** are settled. **The full log now lives in [docs/decision-log.md](docs/decision-log.md)**, which is the source of truth from here on. Sponsors chosen: Hg, Bridgepoint and Apax (D-023). Still open: provenance in the property graph.
**Sources:** Trial brief, Knowledge graph primer, Private markets primer, Candidate pack README (all read in full on 16 Oct 2026).

---

## 0. What changed from the first draft

The first draft was written before the brief was read, so it planned a generic graph project. The main corrections:

| # | First draft said | The brief actually says | Change |
|---|---|---|---|
| 1 | Property graph first, then RDF | **"RDF first, then property graph"**, plus a note on what changed in your thinking between them | Order flipped. The "what changed" note becomes a deliverable |
| 2 | Build a hand-made fixture dataset | **Real public data**: GLEIF, Companies House or EDGAR, ~30 news releases, a few hundred entities around 3–5 PE sponsors | Fixtures are kept for unit tests only. The real data is the project |
| 3 | "Don't assume a graph database" | **Neo4j** (AuraDB Free or Desktop) and **RDFLib/Oxigraph** are required | The stack is mostly fixed by the brief |
| 4 | No language-model work | An LLM extracts facts from news releases, each linked to its exact sentence | New workstream |
| 5 | — | Entity matching, checked by hand on ~50 pairs, with precision and recall reported | New workstream |
| 6 | "Required queries" | 10–12 investor questions **of your own**, each in both SPARQL and Cypher, with sources, and with timings on a small and a large dataset | New workstream |
| 7 | — | Three-way comparison (text-to-Cypher, text-to-SPARQL, vector search), scored | New workstream |
| 8 | A custom GUI | **Neo4j Bloom/NVL plus one other tool**, showing the path from a fact back to its source | The required views come first. Your GUI is an add-on, or it can be the "other tool" (see 3.7) |
| 9 | — | A ~2-page write-up, including how each model would take on a new kind of fact (e.g. the start and end dates of a stake) | New deliverable |
| 10 | A six-field decision record per decision | "A **short** log of the decisions you make and why" | Lighter format (see section 8) |
| 11 | Comments "while keeping maintainable" (watered down) | Your rule: every line commented | Your rule is kept exactly as stated |
| 12 | Built in horizontal layers (all of graph A, then all of graph B) | Time is short, and the explain-back carries the most weight | Build one **thin end-to-end slice** first, then widen it |

**Kept from the first draft:** the translation layer waits until both graphs exist and are tested on their own; the GUI is a viewing layer only, with no graph logic in it; translation tests compare normalised facts, not file text; lossy mappings are written down.

---

## 1. What we are judged on

**The explain-back (45 minutes, no code open) carries the most weight.** You need to be able to explain:

1. How a fact travels from a public source into **both** graphs, and how every fact traces back to the exact record or sentence it came from.
2. How each graph answers realistic questions.
3. How an LLM adds facts taken from ordinary text.
4. Using your own measurements, when you would choose RDF, a property graph, or vector search.

**Questions to expect:**
- How does a fact stay attached to the right company?
- Why did you design each link the way you did?
- How would each model take on a new kind of fact?
- How did you score the answers?
- What would change in a real deployment?

**They will also check:**
- That you use *sponsor, fund, GP, LP* and *portfolio company* accurately.
- That you report what did not work.

> "A smaller system that you can explain completely, with honest measurements, is worth more than a larger one you cannot."

So every design choice below should be defensible in one sentence.

---

## 2. Deliverables checklist (brief §4)

- [x] Decision log (kept up to date in docs/decision-log.md)
- [ ] A repo with **one command** that builds both graphs from scratch, and a README that lets someone else run it
- [ ] A schema sketch for the RDF graph (done: docs/schema/rdf-schema.md) and for the property graph, plus the "what changed between them" note
- [ ] 10–12 investor questions, each with why it matters, the SPARQL and Cypher queries, the answers, the sources, and timings at a small and a large data size
- [ ] The facts extracted from news releases, the 50-pair hand-checked matching sample, precision and recall, and an explanation of the errors
- [ ] The results of the three-way comparison, and how they were scored
- [ ] The visualisations (Bloom/NVL plus one other tool) and the ~2-page write-up

**Your add-ons**, started once the items above are showable:
- An RDF ↔ property-graph translation layer
- Your own GUI

---

## 3. Key design ideas

### 3.1 One shared list of facts that both graphs are built from **[Decided: D-012]**

```
download (cached raw files) → parse into one source-neutral list of facts, each carrying its provenance
                                   ├──→ build the RDF graph   (Oxigraph/RDFLib)
                                   └──→ build the property graph (Neo4j)
```

**Why:**
- It makes "the same data in two graphs" literally true.
- The single build command stays simple.
- Each graph builder stays small enough to explain line by line.
- Counting the facts in each graph against the list is a cheap correctness test.

**Alternative:** build the property graph by converting the RDF graph.
- That would make the property graph an automatic translation rather than a design, and the brief asks you to *design both*.
- It is, however, exactly what your translation layer explores later. Comparing the auto-translated graph with your hand-designed one makes a strong write-up point (see 3.7).

### 3.2 Provenance is the central design decision **[RDF decided: D-015, RDF-star. Property graph still open]**

> **Setup finding (D-015):** pyoxigraph 0.5 uses the RDF 1.2 form of RDF-star. Each annotation becomes a hidden *reifier* node, linked to the fact by `rdf:reifies`, and the source hangs off that node. A fact with two sources gets two reifiers. This is pinned by `tests/test_environment.py`.

Every fact carries:
- its source (GLEIF, Companies House or news)
- the record or document ID
- the retrieval date
- for text facts, the sentence ID and the exact sentence text.

| | Options | Trade-off |
|---|---|---|
| **RDF** | (a) RDF-star: attach the source to the triple itself · (b) a named graph per source record · (c) a "claim" resource: the fact becomes a thing with a subject, a value and a source | (a) is the neatest and is supported by Oxigraph (RDFLib's support is weak). (c) is the most explicit and handles conflicting facts, but every link in a query costs one extra hop |
| **Property graph** | Provenance as properties on the relationship, or a `Source`/`Sentence` **node** that the fact links to | A property can't be drawn as a path in Bloom, and the brief wants the *path from fact to source* to be visible. Neo4j also can't point an edge at another edge |

**Starting recommendation** (our starting point for the sketch, not yet final):
- **Registry facts** (GLEIF parents, Companies House PSCs) become direct edges with provenance properties, plus a link to a `SourceRecord` node.
- **News facts** become **event nodes** (`Acquisition`, `FundClose`) that link to `Sentence` → `Document`.
- Deals are naturally multi-party (buyer, target, date, advisers), so they need to be nodes anyway. This gives a visible path to the evidence in both models.

**Represent gaps openly (brief §2):**
- A GLEIF *reporting exception* (e.g. `NON_CONSOLIDATING`, `NATURAL_PERSONS`, `NO_KNOWN_PERSON`) becomes a stored fact that says "no parent reported, for reason X", rather than a missing edge.
- When sources disagree on a name or a date, keep both values side by side, each with its source, rather than overwriting one (primer §3.3).

### 3.3 Time

The write-up asks how each model would take on the start and end dates of a stake.
- **Now:** store a date for each event (e.g. the deal date) and a `retrieved_at` for each record, so there is a natural place for time in both models.
- **Not now:** a full two-timeline model. The write-up describes how you would add one. GLEIF relationship records already carry relationship periods with start dates, which makes a concrete example.

### 3.4 Domain model: industry terms to get right

| Term | What it is in the data |
|---|---|
| **Sponsor** | The PE firm as a brand (e.g. "Permira"). Usually a *group* of legal entities, not one |
| **Manager / adviser entity** | The legal entity that manages the funds (e.g. "… Advisers LLP") |
| **GP** | The legal entity that acts as *general partner* of a fund. It is a different entity from the manager |
| **Fund** | Usually a limited partnership. One "Fund VII" is often several vehicles: main, parallel, feeder and co-invest |
| **LP** | The investors in a fund. Mostly **not public**, so we will have few or none. Say so openly rather than inventing any |
| **Holding companies** | TopCo → MidCo → BidCo, the chain between a fund and the company it bought |
| **Portfolio company** | The company that was bought |
| **Adviser (deal)** | The banks and law firms named in news releases |

**Data traps to plan for (worth mentioning in the explain-back):**

1. **Funds usually don't consolidate their portfolio companies** in their accounts, under the investment-entity rule. So GLEIF parent chains often stop at a holding company or show an exception. The fund → portfolio company link will mostly come from **news releases and Companies House PSC records**, not from GLEIF.
2. **"Fund VII" and "Fund VIII" differ by one character.** A name cleaner that strips numbers or Roman numerals will wrongly merge them. This is a classic over-merge, the error the primer calls the most damaging.
3. **Offshore and US vehicles** (Jersey, Guernsey, Luxembourg, Delaware) are not in Companies House. GLEIF does cover them.
4. **GLEIF records hold a registration number and a registration-authority code** (Companies House is `RA000585`). That gives an **identifier match** between an LEI and a Companies House number, which is far stronger than matching on names.
5. GLEIF also has fund relationship types (`IS_FUND-MANAGED_BY`, `IS_SUBFUND_OF`, `IS_FEEDER_TO`). Their coverage still needs checking in the spike.

### 3.5 Choosing sponsors **[Decided: D-008, UK. The spike picks which 3 sponsors]**

| | Option | Pros | Cons |
|---|---|---|---|
| **A (chosen)** | 3 UK-headquartered sponsors with UK-heavy portfolios: GLEIF + Companies House only. Candidates: Permira, Cinven, Hg, Bridgepoint, Apax, Inflexion | One register to learn; PSC data gives ownership; free API | Many fund vehicles sit offshore (GLEIF covers them) |
| B | US sponsors (KKR, Blackstone, Carlyle): GLEIF + EDGAR | Form D filings give fund offering sizes | Entity counts are enormous; filings are harder to parse |

**Pick on evidence:** for each candidate, count the LEIs we can reach, check how many have parent relationships recorded in GLEIF (Level 2), and count the press releases available.

### 3.6 Tools **[Decided: D-006, D-007, D-013]**

| Area | Chosen | Why | Alternative (not chosen) |
|---|---|---|---|
| Python environment | `uv` + Python 3.12, with a lockfile | Fast and reproducible ("someone else can run it"). 3.12 is the safest version for library wheels (your system Python is 3.14) | `venv` + `pip` + `requirements.txt` |
| RDF store | **pyoxigraph** for storing and querying, rdflib only where it helps | Fast enough for the large-data timings; supports RDF-star | rdflib only: simpler, but slow at larger sizes |
| Neo4j | **Neo4j Desktop** (local) | No AuraDB Free cap (~200k nodes / 400k relationships, which matters for the large timing run). Bloom is included. Can run the **n10s** RDF plugin, a useful reference for the translation layer | AuraDB Free: nothing to install, but it has the caps and no n10s |
| Vocabulary | Our own small namespace, **PROV-O** for provenance, and GLEIF ontology terms where they fit | Small enough to explain; reused terms are easy to defend | FIBO: thorough, but huge and hard to explain |
| SHACL | Yes, a handful of shapes via `pyshacl` (e.g. "every fund has a manager", "every fact has a source") | Cheap, and makes a good explain-back point | Skip it (it's optional) |
| LLM extraction | Seisa's key (provider to be confirmed); JSON output matched against our schema | The primer's recommended middle approach: "model extraction against a schema" | Open extraction (the primer warns against it) |
| Vector search | Neo4j's built-in vector index, or local embeddings + numpy | Few moving parts | Chroma / FAISS |
| Single command | `make build` → one Python CLI | Standard and readable | `python -m seisa_kg build` |

**Guard against invented evidence in extraction:**
- Split each release into sentences with stable IDs (`doc12#s07`) *before* the model sees it.
- The model must return the sentence ID and an exact quote for each fact.
- Code checks that the quote really appears in that sentence. Any fact that fails the check is rejected and logged, not loaded.

### 3.7 Where your GUI and translation layer fit

**GUI** **[Decided: D-010]**
- Build it on a graph-drawing library (e.g. Streamlit with a vis-network/Cytoscape component, or Neo4j's NVL in a small page) so it **counts as the brief's "one other tool"**. Your add-on then satisfies a requirement instead of adding work.
- If you're unsure it counts, add a small yFiles Jupyter view as a backup.
- The must-have screen: click a fact → see the path back to its source record or sentence.
- All graph logic stays outside the GUI.

**Translation layer** (only once both graphs work on their own; your rule, D-002):
1. **Automatic RDF → property-graph mapping, compared with your hand-designed property graph.** What does an automatic mapping lose? For example: RDF-star annotations, datatypes, multi-valued properties, global IRIs versus Neo4j's internal IDs. This feeds the write-up directly.
2. **Parity check.** Both graphs, normalised to plain facts, should match the shared fact list from 3.1. That is a strong test that "the same data" really is in both.
3. Optionally, compare the output against n10s as a reference.

---

## 4. File structure **[Decided: D-014]**

```
seisa-kg-trial/              ← ~/Work Projects/seisa-kg-trial, its own git repo (D-030, D-031; Desktop/Work is a shortcut)
├── README.md                how to install and run, for someone else
├── PLAN.md                  this file
├── Makefile                 `make build` = the single command
├── pyproject.toml / uv.lock pinned dependencies
├── .env.example             names of secrets (real .env is gitignored)
├── config/
│   └── sponsors.yaml        chosen sponsors and their seed LEIs
├── docs/
│   ├── decision-log.md
│   ├── schema/              rdf-schema.md, lpg-schema.md (+ diagrams), what-changed.md
│   ├── questions.md         investor questions, why each matters, answers, timings
│   ├── matching-report.md   50-pair sample, precision/recall, error analysis
│   ├── comparison-report.md three-way results and scoring rubric
│   └── write-up.md          the ~2-page document
├── data/                    gitignored (large and re-downloadable)
│   ├── raw/                 cached API responses and news text, never re-downloaded
│   ├── interim/             the shared fact list (3.1)
│   └── output/              graph.ttl, extracted facts, timing results
├── src/seisa_kg/
│   ├── sources/             gleif.py, companies_house.py, news.py  (download + cache)
│   ├── facts/               the shared fact and provenance format
│   ├── rdf/                 build.py, ontology.ttl, shapes.ttl, queries/*.rq
│   ├── lpg/                 build.py, constraints.cypher, queries/*.cypher
│   ├── extraction/          sentence splitting, LLM prompts, quote checking
│   ├── matching/            name → LEI resolution, evaluation
│   ├── qa/                  text_to_sparql, text_to_cypher, vector_search, scoring
│   ├── translation/         later (3.7)
│   └── ui/                  later (3.7)
├── scripts/                 extract_brief.py and other one-off helpers
└── tests/                   small hand-made fixtures, used for tests only
```

---

## 5. Working rules

- **Every file** opens with a plain-English summary, and **every line** has a plain-English comment. This includes SPARQL (`#`), Cypher (`//`), the Makefile and YAML. *(Your rule, D-004.)*
- **Secrets** go in `.env` (gitignored). The Seisa LLM key never goes in the repo (brief §6).
- **Downloads are cached** in `data/raw/` and never fetched twice. Each request identifies us, and we stay within rate limits:
  - Companies House: ~600 requests per 5 minutes
  - SEC: 10 requests per second, with a declared User-Agent
- **The brief PDFs stay out of the repo** *(D-011)*. They are Seisa material, and the brief's rule is "no Seisa code or data".
- **Agent role:** I propose options, each with a recommendation; you decide; the decision gets logged before code is written.

---

## 6. Timeline (v3, 19 Oct): finish Wednesday, present Thursday

**Hours:**
- Mon 19 Oct, 15:00–18:00 (3 h)
- Tue 20 Oct, 10:00–18:00 (8 h)
- Wed 21 Oct, 10:00–18:00 (8 h)

That's about 19 hours, or about 16 of real work after breaks. **Thu 22 Oct: present.**

**Way of working (D-067, 19 Oct, after the meeting with Anish; also in CLAUDE.md):**
- Bruno thinks first; Claude reviews with sources.
- Bruno decides; Claude codes in small pieces.
- Bruno explains each step back before moving on.

This is slower than Claude building alone, so the plan below cuts the extensions (D-066).

> The earlier timeline (16–18 Oct: thin slice, then widen) is done or replaced. It stays in git history.

### Where we are (Mon 19 Oct, 3pm)
**Done:**
- GLEIF fetch: 3 sponsors, 993 companies
- shared fact list: 15,006 facts
- automatic scope step: In / Review / Out, with reasons
- RDF graph: 49,042 triples, with RDF-star sources and SHACL checks
- 3 questions in SPARQL, with sources and timings
- graded scorer
- `make build`, about 7 seconds, offline
- 31 tests

**Not started:**
- Neo4j (deleted 18 Oct, to be built together)
- news releases
- entity matching
- text-to-SPARQL, text-to-Cypher, vector search
- visualisation
- timings at two sizes
- README
- write-up

### Scope for Wednesday (D-066, Bruno, 19 Oct)
| | Decision | Notes |
|---|---|---|
| **Dropped** | The translation layer and the custom GUI (Bruno's extensions) | Listed as next steps in the write-up |
| **Visualisation** | The **standard** ways of viewing knowledge graphs: Neo4j Bloom, plus one other standard tool for the brief's "one other tool" (chosen on Wednesday) | A simple GUI only if those tools fall short |
| **Kept** | Companies House (UK control records, PSCs), joined through GLEIF's `registeredAs` number | Gives "who controls whom" for UK companies |
| **Kept** | About 30 news releases (the brief's number) | |

> **Honest budget:** with Companies House and 30 releases kept, the days below add up to about **3 hours more than the time available**. The "drop in this order" list at the end is how we absorb that.

### Monday 19 Oct, 15:00–18:00: think and decide (no new pipeline code)
1. Confirm the way of working (10 min).
2. **What makes a good triple.** Bruno drafts his criteria from the seven questions, then Claude reviews them against the sources. Apply them to our graph and list any triples to change (1 h).
3. **Bruno writes the 10–12 investor questions** (1 h). These are the "competency questions": they also justify which triples we keep.
4. **Proving the pipeline is right.** Decide the method, e.g. Bruno hand-labels a sample of scope verdicts and we measure precision and recall (45 min).
5. Diary, commit, push (15 min).

### Monday 19 Oct: what actually happened (beyond plan)
- Done: the way of working (D-067), good-triple criteria (D-068 to D-070), 12 questions (D-071), Companies House **and** news **and** Gemini extraction, all in the RDF graph; `make build` runs all three sources; Q5 runs. See the diary, 19 Oct.

### Tuesday 20 Oct, 10:00–18:00 (D-095): the whole MVP, including the property graph
**Morning (10:00–13:00): finish the RDF system**
1. Read the study guide (Bruno, before 10:00 or first thing).
2. **Entity matching** (news names → `lei:` / `ch:`): Bruno's approach first, then the build, then 50 pairs hand-checked, with precision and recall (1.5 h).
3. `make refresh` with dated snapshots (D-094) (30 min).
4. The remaining questions in SPARQL: Q4, Q6–Q12 (1 h).

**Afternoon (14:00–18:00): the labelled property graph (Neo4j), step by step (D-063 reopened)**
1. Concept: property graph vs RDF, and provenance options (the "receipt boxes" idea) (30 min).
2. The schema sketch (`docs/schema/lpg-schema.md`) and the "what changed" note (45 min).
3. The builder: `facts.jsonl` → Neo4j, with checks that both graphs hold the same facts (1 h).
4. The 12 questions in Cypher, scored against the SPARQL answers (1.25 h).
5. A Bloom view of fact → source (30 min).

### Wednesday 21 Oct, revised (D-117): learn in the morning, build from 14:00
**Morning: learning only** (study guide 3, the Cypher, SPARQL and vector search courses, flashcards). No new pipeline work.
**From 14:00: the pipeline again, starting with the matching hand-check.** The rest of the day and Thursday morning are being re-planned (see the diary, D-117); the D-115 plan below is kept for reference.

#### Superseded plan (D-115)
**10:00–13:00: build** (11:00–11:30 blocked: Bruno's EF interview)
0. **First (15 min): the 50-name matching hand-check** (`eval/matching-sample.csv`), then Claude scores precision, weighted recall and agreement (moved from Tuesday, D-116).
1. The questions in Cypher (Q1–Q3 and Q5 first, compared with SPARQL and timed), then the remaining questions in both: Q4, Q6, Q8–Q12 (Q10 as reworded in D-100). A Bloom view of fact → source.
2. A small three-way comparison: text-to-SPARQL vs text-to-Cypher vs vector search over the news sentences, on about 10 questions, scored.
3. Timings on the current data size (large-data timings: describe the method instead).

**13:00–15:00: write, then freeze**
4. README (one command builds both graphs) and the ~2-page write-up, including the talking points.
5. **15:00 freeze:** `make build` from a clean copy, all tests, commit, push. No more code after this.

**15:00–18:00: review and rehearsal, with no code open**
6. The decisions Bruno *accepted* (rather than originated) first, then the expected questions in §1. Claude quizzes as Seisa.

**Dropped for time (D-115, from the drop list below):** `make refresh` and Q7, and the gemini-3.8-flash comparison. Each is named in the write-up as next work.

### Thursday 22 Oct: review in the morning, present early afternoon
- Morning: a final review and rehearsal of the explain-back, with no code open, using the expected questions in §1.
- Early afternoon: present.

### If we fall behind, drop in this order (proposed; Bruno decides at the time)
1. Large-data timings: describe the method instead.
2. News down to 15 releases.
3. Companies House narrowed to the In-scope UK companies that appear in our questions.
4. Vector search, as a last resort: compare text-to-SPARQL and text-to-Cypher only, and say so.

**Never drop:**
- both graphs answering the questions, with sources
- news extraction with quote checks
- the 50-pair matching sample
- the write-up

---

## 7. Risks

| Risk | Mitigation |
|---|---|
| GLEIF has gaps for funds and portfolio companies | Expected (brief §2). Store them as reporting exceptions; take ownership links from news and PSC records |
| Collecting news releases by hand is slow | Start with 10; record the URL and retrieval date for each |
| LLM provider and spending limit unknown | Keep extraction behind one small function; record cost per run |
| Scope: there are eight parts | Protect depth for the explain-back; cut breadth first, and log every cut |
| Wrong merges in matching | Merge conservatively, record the evidence for each match, keep "unresolved" as a valid outcome |

---

## 8. Decision log: format and the first entries

**Format:**
```
## D-006 · 2026-10-16 · <short title>
Decision:          what we chose
Why:               the reason, in one or two sentences
Alternatives:      what else we considered
Would revisit if:  what would change our mind
```

**Decisions you've already made:**

| ID | Decision |
|---|---|
| D-001 | Keep a chronological log of all decisions |
| D-002 | Build the RDF and property graphs in isolation first; the translation layer only after both exist and are tested |
| D-003 | Make the project visual, with a GUI |
| D-004 | Every line of code gets a plain-English comment, and every file opens with a plain-English summary |
| D-005 | Bruno makes every decision; the agent proposes options with a recommendation |

**Decisions made on 16 Oct 2026** (Bruno accepted the plan's recommendations):

| ID | Decision | Why | Would revisit if |
|---|---|---|---|
| D-006 | `uv` + Python 3.12, with a lockfile | Reproducible for a reviewer; 3.12 is the safest version for library wheels | A library we need doesn't support 3.12 |
| D-007 | Neo4j Desktop (local), not AuraDB Free | No node/relationship cap for the large timing run; includes Bloom; can run n10s | Seisa needs to reach the database online |
| D-008 | UK-focused sponsors: GLEIF + Companies House | One register to learn; PSC data gives ownership | The spike finds too little UK coverage |
| D-009 | Monday goal: a thin slice explained completely, plus the plan, then ask to continue | The explain-back is weighted above coverage | The slice is finished early |
| D-010 | Your GUI is built on a graph library so it counts as the brief's "one other tool" | The add-on also meets a requirement | Seisa says it doesn't count (fallback: a small yFiles view) |
| D-011 | Brief PDFs stay out of the repo | Brief rule: no Seisa code or data | — |
| D-012 | Both graphs are built from one shared fact list | "Same data in two graphs" becomes checkable; each builder stays small | The shared format can't express something one model needs |
| D-013 | Tools: pyoxigraph (+ rdflib where it helps); own namespace + PROV-O + GLEIF ontology terms; a few SHACL shapes via pyshacl; schema-guided LLM extraction with quote checking; Neo4j vector index or local embeddings; `make build` as the single command | See the table in 3.6 | Timings or a library's limits force a change |
| D-014 | The file structure in section 4 | Clear separation by stage of the pipeline | It gets in the way once code exists |

---

## 9. Still open

| # | Decision | When |
|---|---|---|
| 1 | Provenance design in each model (3.2) | Sketched together before the first builder is written (Sunday morning) |
| 2 | ~~Which 3 UK sponsors~~ | **Decided (D-023): Hg, Bridgepoint, Apax** |
| 3 | Your 10–12 investor questions | Yours to write; the first 3 are needed for the Sunday thin slice |

*Investor questions must be your own (brief §3.3). Some example shapes to get you started:*
- "Which portfolio companies does sponsor X control, and through which chain of holding companies?" (follows several links in a row)
- "Which deal advisers have worked for more than one of our sponsors?"
- "Which entities report no parent in GLEIF, and for what reason?"
- "Where does a news release disagree with the register?"
- "Show every source behind company Y's ownership chain."
