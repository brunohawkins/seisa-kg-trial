# Seisa trial: the same data in two graphs

Public data about three UK private equity sponsors (**Hg, Bridgepoint, Apax**), their funds and the companies they own, stored in an **RDF graph** (Oxigraph, with RDF-star for sources) and a **labelled property graph** (Neo4j). Every fact is traceable to its source record, or to the exact sentence it came from, or to the rule that made it.

- **Sources:** GLEIF (legal entities, fund managers, parents), Companies House (companies, officers, people with significant control), and 30 sponsor news releases read by Gemini.
- **One command builds both graphs from scratch:** `make build`.
- **Decisions and why:** [docs/decision-log.md](docs/decision-log.md). **The write-up:** [docs/write-up.md](docs/write-up.md).

## Setup (once)

You need [uv](https://docs.astral.sh/uv/) (it installs Python 3.12 for you), a recent Java for Neo4j (built and tested on Java 25) and `make`.

1. **Install the Python environment:**
   ```bash
   make setup
   ```
2. **Add your keys:** copy the template and fill in the values (never commit `.env`).
   ```bash
   cp .env.example .env
   ```
   - `LLM_API_KEY`: a Google Gemini key (extraction and the comparison).
   - `COMPANIES_HOUSE_API_KEY`: a free key from developer.company-information.service.gov.uk.
   - `NEO4J_PASSWORD`: the password you choose in step 3.
3. **Install and start the project's own Neo4j server** (Community edition, kept in `tools/neo4j`, data in `data/neo4j`):
   ```bash
   make neo4j-install
   make neo4j-start
   ```
   Open http://localhost:7474 once, log in as `neo4j` / `neo4j`, and set the password you put in `.env`.
4. **Check everything works:**
   ```bash
   make test
   ```

## Build

```bash
make neo4j-start   # if it isn't running
make build
```

Every download and every language-model answer is cached (in `data/raw/`), so a rebuild is fast and repeatable; a first run fetches from GLEIF and Companies House within their rate limits. Each stage checks its own output and **stops the build if a check fails**.

**From the handoff zip:** the zip includes `data/` (every download and every Gemini answer, cached; the fact list; the RDF graph file; every answer). So you can read every result without running anything, and `make build` rebuilds both graphs identically **without calling Gemini or Companies House**: put any placeholder text for `LLM_API_KEY` and `COMPANIES_HOUSE_API_KEY` in `.env` (the code reads them at start, but never uses them when the answer is cached). Neo4j still needs steps 3 and 4 of the setup. `make handoff` makes the zip from the last commit and checks it contains no key.

| Stage | Command | What it does | Output |
|---|---|---|---|
| 1. Fetch | `make fetch-gleif`, `make fetch-ch` | Downloads and caches every GLEIF and Companies House record | `data/raw/` |
| 2. Extract | `make extract` | Splits each release into numbered sentences; Gemini extracts deals, fund closes and names; code checks every quote against its sentence | `docs/extraction-report.md` |
| 3. Facts | `make facts` | Turns every source record, extracted fact and our own judgement (scope, matching) into one list of fact cards | `data/interim/facts.jsonl` |
| 4a. RDF | `make rdf` | Builds the RDF graph (sources on RDF-star notes) and checks it with SHACL | `data/output/graph.ttl` |
| 4b. Neo4j | `make lpg` | Builds the property graph, checks it against the fact cards and against the RDF graph | Neo4j |
| 5. Questions | `make query`, `make query-lpg` | Answers the 10 investor questions in SPARQL and in Cypher, checks the two agree, times both; draws the RDF provenance view | `docs/answers-rdf.md`, `docs/answers-lpg.md`, `docs/provenance-rdf.md` |
| 6. Comparison | `make compare` | Answers the same questions by text-to-SPARQL, text-to-Cypher and vector search, scored against the hand-written answers | `docs/comparison.md` |

## Where each deliverable is

| The brief asks for | Here |
|---|---|
| A short log of decisions and why | [docs/decision-log.md](docs/decision-log.md) |
| A sketch of each schema | [docs/schema/rdf-schema.md](docs/schema/rdf-schema.md), [docs/schema/lpg-schema.md](docs/schema/lpg-schema.md) |
| Investor questions, why each matters, SPARQL and Cypher, answers, sources, timings | [docs/answers-rdf.md](docs/answers-rdf.md), [docs/answers-lpg.md](docs/answers-lpg.md); queries in `src/seisa_kg/rdf/queries/` and `src/seisa_kg/lpg/queries/` |
| Facts extracted from the news | [docs/extraction-report.md](docs/extraction-report.md); in both graphs |
| The hand-checked matching sample, precision and recall, the errors explained | [eval/matching-sample.csv](eval/matching-sample.csv), [docs/matching-eval.md](docs/matching-eval.md) |
| The three-way comparison and how it was scored | [docs/comparison.md](docs/comparison.md); the scorer in `src/seisa_kg/evaluation/score.py`, demonstrated in [docs/scoring-demo.md](docs/scoring-demo.md) |
| Visualisations | Neo4j Bloom scenes: [docs/images/](docs/images/); the RDF provenance view: [docs/provenance-rdf.md](docs/provenance-rdf.md) (drawn by GitHub), or [docs/provenance-rdf.html](docs/provenance-rdf.html) in any browser |
| The write-up | [docs/write-up.md](docs/write-up.md) |
| What the sources contain, and what we found in them | [docs/data-sources.md](docs/data-sources.md) |

## Seeing the path from a fact to its source

- **In Neo4j (Bloom / Explore in Neo4j Desktop):** connect to `bolt://localhost:7687` and run, for a registry company:
  ```cypher
  MATCH p = (c:Company {id: "lei:213800KFNMVI8PDZX472"})-[:SAME_ENTITY_AS*0..1]->(n)-[:DERIVED_FROM|GENERATED_BY]->(src)
  RETURN p
  ```
  and for a news fact:
  ```cypher
  MATCH p = (d:Deal {id: "ex:deal/hg-06-d1"})-[:DERIVED_FROM]->(s:Sentence)-[:IN_RELEASE]->(r:Release)-[:PUBLISHED_BY]->(sp:Sponsor)
  RETURN p
  ```
- **In the RDF graph:** [docs/provenance-rdf.md](docs/provenance-rdf.md) draws the same two examples from `graph.ttl` (fact ← RDF-star note → record or rule). To query it yourself: `uv run python scripts/sparql.py "<a SPARQL query>"`.

## Code layout

| Folder | What's in it |
|---|---|
| `src/seisa_kg/sources/` | One cached downloader per source |
| `src/seisa_kg/extraction/` | Sentence splitting and Gemini extraction with the quote check |
| `src/seisa_kg/facts/` | Source records and judgements → fact cards |
| `src/seisa_kg/matching/` | News names → our legal entities (rules, outcomes, the hand-check sample and its scoring) |
| `src/seisa_kg/rdf/` | The RDF builder, SHACL shapes, the SPARQL questions and their runner |
| `src/seisa_kg/lpg/` | The Neo4j builder, the Cypher questions and their runner |
| `src/seisa_kg/evaluation/` | The answer scorer (correctness and citation) |
| `src/seisa_kg/comparison/` | The three-way comparison and its phrasebooks |
| `config/` | The sponsors and their search words, the approved match labels, the releases used |
| `tests/` | `make test` |

Every file opens with a plain-English summary, and every line of code carries a plain-English comment.

## Known limits (said openly)

- Three public sources only: no fund investors (LPs), no deal prices beyond what releases state, and Companies House stops at non-UK companies.
- Timings are measured on this dataset only; a larger dataset would need a generated or wider sample (method in the write-up).
- The comparison uses 10 questions, one model and one run: it shows where each method breaks, not a precise ranking.
- Fine-grained access control by label or property needs Neo4j Enterprise; this build uses Community.
