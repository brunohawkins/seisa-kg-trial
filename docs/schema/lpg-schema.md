# Property graph schema (Neo4j) — v1, 20 Oct (decisions D-110 to D-112)

Built from the same fact list as the RDF graph (`data/interim/facts.jsonl`, D-012), so both graphs hold the same facts. Provenance follows **option C, receipt relationships (D-110)**. GLEIF and Companies House companies stay **two nodes** (D-111).

Naming follows the Neo4j Cypher style guide: labels `CamelCase`, relationship types `UPPER_SNAKE_CASE`, properties `camelCase`.

## 1. The idea in one picture
```
(:SourceRecord {id, url, retrievedAt})                       (:Rule {id: "D-025", label})
        ▲                                                            ▲
        │ DERIVED_FROM {properties: ["legalName","entityStatus",…]}  │ GENERATED_BY {properties: ["statusGroup","addressKey"]}
        │                                                            │
(:Company:Gleif {lei, legalName, entityStatus, …}) ──SAME_ENTITY_AS {rule: "D-025"}──▶ (:Company:CompaniesHouse {companyNumber, …})
        ▲
        │ SAME_ENTITY_AS {rule: "D-098", reason}     ← a link carries its own source or rule as properties
(:Match {nameAsWritten, outcome, reason}) ◀──BUYER_MATCH── (:Deal {valuation, dealStatus, …}) ──ANNOUNCED_IN──▶ (:Release)
                                                                │
                                                                └─DERIVED_FROM {properties: ["valuation","dealStatus"],
                                                                                quotes: ["approximately $1.393 billion","to acquire"],
                                                                                extractedBy: "gemini-2.5-pro"}──▶ (:Sentence {sid, text})
```
Three rules of thumb (Neo4j modelling guide):
- **A thing with its own identity or many connections → node.** (A deal touches a buyer, sponsor, target, release and up to 8 advisers, so it's a node, not a relationship.)
- **A plain value → property.**
- **A link between exactly two things → relationship**, with its details and source as properties.

## 2. Nodes (labels)
| Label | From RDF | Count | Key property | Sensitive? (ACL, D-110) |
|---|---|---|---|---|
| `Company:Gleif` | `lei:` LegalEntity | 489 | `lei` | |
| `Company:CompaniesHouse` | `ch:` LegalEntity | 159 | `companyNumber` | |
| `NewsOnlyCompany` | NewsOnlyCompany (D-109) | 29 | `id` | |
| `Sponsor` | Sponsor | 3 | `id` (hg, bridgepoint, apax) | |
| `Stake` | Stake (D-075) | 51 | `id` | |
| `Name` | otherName / previousName (D-112a) | 141 distinct names | `id` | |
| `Appointment` | Appointment (D-074) | 880 | `id` | |
| `Person` | Person | 466 | `id` | **yes: personal data** |
| `Release` | Release | 30 | `id` | |
| `Sentence` | sentence source record | 968 | `sid` | yes: raw text |
| `Deal`, `Adviser`, `FundClose`, `Mention` | same | 30, 105, 5, 438 | `id` | |
| `Match` | Match (D-108) | 253 | `id` | yes: our judgement |
| `SourceRecord` | SourceRecord | 3,241 (incl. sentences) | `id` | yes: raw source |
| `Rule` | Rule | 14 | `id` (e.g. "D-025") | |

Every key property gets a **uniqueness constraint**, so a rebuild can't create duplicates.

## 3. Relationships
| Type | From → To | From RDF predicate | Properties |
|---|---|---|---|
| `SAME_ENTITY_AS` | Gleif → CompaniesHouse | `sameEntityAs` (D-025) | `rule` |
| `FUND_MANAGED_BY`, `DIRECTLY_CONSOLIDATED_BY`, `ULTIMATELY_CONSOLIDATED_BY` | Company → Company | same | `startDate`, `status`, `corroboration`, `gleifRelationshipId`, `record` |
| `IN_SCOPE_OF` | Company → Sponsor | ScopeDecision node (D-028) | `verdict` (In / Review / Out), `reason`, `rule` |
| `HAS_STAKE` / `HOLDER` | Company → Stake → Company or Person | `company` / `holder` | `record` |
| `HAS_APPOINTMENT` / `OFFICER` | Company → Appointment → Person or Company | `company` / `officer` | `record` |
| `ANNOUNCED_IN`, `MENTIONED_IN` | Deal, FundClose / Mention → Release | same | `record` |
| `PUBLISHED_BY` | Release → Sponsor | same | `record` |
| `IN_RELEASE` | Sentence → Release | `inRelease` | |
| `HAS_ADVISER` | Deal → Adviser | `adviser` | `record` |
| `TARGET_MATCH`, `BUYER_MATCH`, `SELLER_MATCH`, `SPONSOR_MATCH`, `FUND_MATCH`, `ADVISER_MATCH` | Deal / FundClose / Adviser → Match | same | `rule` |
| `SAME_ENTITY_AS`, `REFERS_TO_GROUP`, `NAMED_COMPANY`, `CANDIDATE`, `POSSIBLE_ENTITY` | Match → Company / Sponsor / NewsOnlyCompany | same | `rule` |
| `DERIVED_FROM` | any node → SourceRecord or Sentence | the RDF-star notes | `properties` (list), plus `quotes`, `extractedBy` for news |
| `GENERATED_BY` | any node → Rule | the RDF-star notes | `properties` (list), plus `why` for "unknown" values (D-090) |

`record` on a relationship is the id of its `SourceRecord`, so a link's source is on the link itself; the record node holds the URL and fetch date once.

## 4. Provenance (D-110): how each kind of RDF note maps
| RDF | Property graph |
|---|---|
| A value fact's note → source record | The value is a property; `DERIVED_FROM {properties: [...]}` to the record lists it |
| A value fact's note → rule | The value is a property; `GENERATED_BY {properties: [...]}` to the rule lists it |
| A link fact's note | `record` or `rule` as a property on the relationship |
| A news value's quote and model | `quotes` and `extractedBy` on the `DERIVED_FROM` to its sentence, as lists in the same order as `properties` |
| A type fact (`a ex:Deal`) | The label; the receipt lists `"_label"` so its source is kept too |

## 5. Open points for Bruno
1. **Values with their own details.**
   - `legalName` has a language: proposed companion property `legalNameLanguage`.
   - Several names each with details (`otherName` with type and language; `previousName` with dates; 224 in all): proposed small `:Name` nodes (an intermediate node per Neo4j's guide), because a list property can't hold details per item.
2. **Several values from one fact kind** (`sicCode`, `statedReason`, `otherName`): list properties. Is that acceptable, or do reasons deserve nodes (Q8 asks for them)?
3. **The scope decision becomes a relationship** (`IN_SCOPE_OF {verdict, reason, rule}`) instead of a node. It's simpler to query; does it lose anything you care about?
4. **History:** a value that changes between fetches keeps only its latest value (D-110 weakness); to decide with `make refresh`.

## 6. Checks (reconciliation): both graphs must hold the same facts
After every build, compare with `facts.jsonl`:
1. **Value facts:** each fact kind's count = the number of values held as properties (list items counted one by one).
2. **Receipts:** each value fact appears in exactly one receipt's `properties` list for its record or rule.
3. **Link facts:** each link predicate's count = the number of relationships of its type.
4. **Nodes:** each label's count = the RDF type count (table in section 2).
5. **Answers:** each investor question gives the same answer in SPARQL and Cypher.

**Built (20 Oct):** checks 1–4 run in `python -m seisa_kg.lpg.build` against the fact list, which is worked out independently and never taken from the builder's own output. Step 5 also compares the **RDF file and Neo4j directly**: 14 node types and 22 relationship types, all equal. Any failed check stops `make build` with an error.

## 7. What changed between the two graphs (the brief's "what changed" note, first draft)
- **Notes on facts → receipt relationships.** RDF puts a note on every triple (RDF-star). Neo4j properties can't carry notes, so each node points to its source records once, listing which properties each record backs (D-110).
- **Type triples → labels.** `a ex:Deal` becomes the `:Deal` label.
- **Links with details → relationship properties.** GLEIF's `startDate` and `status` sit on the `FUND_MANAGED_BY` relationship itself.
- **Some nodes → relationships.** The scope decision (a company, a sponsor and a verdict) becomes `IN_SCOPE_OF {verdict}`.
- **Unchanged on purpose:** the GLEIF / Companies House twins stay two nodes (D-111). The Match nodes stay nodes (D-108). The sources' values are kept exactly as given (D-029).
