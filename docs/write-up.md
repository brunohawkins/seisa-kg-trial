# Two graphs and a text index: what I would choose, and why

> Numbers are from the build of 21 Oct 2026; each one points to where it is measured.

## What I built

Public data on three UK private equity sponsors (Hg, Bridgepoint, Apax): 648 legal entities from GLEIF and Companies House, and 30 of the sponsors' own news releases read by Gemini. Everything first becomes one list of **34,269 fact cards**, each recording what a source said, where and when, or which of our rules made it (D-029: never silently correct a source; our own judgements are separate, labelled facts). Both graphs are built from that one list, and the build checks them against it and against each other: the **RDF graph** (112,800 triples, sources on RDF-star notes, checked by SHACL) and the **Neo4j property graph** (6,342 nodes, 4,889 relationships, 6,545 receipts). Ten investor questions are answered in both SPARQL and Cypher, and **all ten give identical answers**, every row citing its sources in both (`docs/answers-lpg.md`; the check compares the answer columns row by row, not the sources, which the two databases write differently).

## When I would choose each

**RDF, when provenance and many sources are the point.** In RDF every fact can carry its own note, so "where did this come from?" has one answer pattern for every fact: `?note rdf:reifies <<( s p o )>> ; prov:wasDerivedFrom ?record`. Q4 ("every fact we hold about Bridgepoint Group plc, and its source") is one short SPARQL pattern; in Cypher it needs three parts joined by UNION, because values, links and names keep their sources in three different places. RDF also handled two sources stating the same fact well: the same triple from two GLEIF fetches is stored once (a graph is a set) with two notes, so nothing is double-counted. Standard vocabularies (PROV-O for sources, SHACL for checks) did real work. The costs were real too: about three triples per fact; sources reached through notes made some queries slower (Q11: 92 ms in SPARQL against 1.5 ms in Cypher); and naming conventions bite: a "/" in a name must be escaped, which is exactly where Gemini's otherwise correct Q1 query broke.

**A property graph, when the graph is explored, served and traversed.** Links carry their own properties, so a fund-manager link holds its start date and its source record directly. Bloom made the fact-to-source path visible in minutes. Cypher was easier for the LLM on our graph (it wrote a perfect Q1). But a property cannot carry its own source, so I designed **receipts**: one `DERIVED_FROM` relationship per node and source, listing exactly which values that source vouches for (D-110). They are cheap to query and can be hidden by relationship type. And the property graph needed discipline that RDF gives for free: global ids (an `id` property with uniqueness rules), de-duplication in code (Neo4j would store a link twice), and care with list properties (several questions needed `UNWIND`).

**Vector search, for finding passages, not for answering structured questions.** Over the 968 news sentences it scored **0.00** in the comparison: "not found" on 8 of 10 questions, and wrong on the other 2. The answers to registry questions are not in any sentence; five sentences cannot hold a list of 28 deals, a count, or a trail across sources; and the similarity scores of right and wrong sentences bunched together (0.69–0.70 on Q11). Its one strength was honesty: it never invented an answer. I would use it to find the passages an extraction step should read, as the first stage of building a graph, not as a replacement for one.

**My choice for this kind of work:** keep a provenance-first record of facts (here, the fact list and the RDF graph) as the system of record, generate the property graph from it for exploration and applications, and use text search only to feed extraction, whose every fact is checked word for word against its sentence.

## What changed in my thinking between the first graph and the second

- **Sources have to be designed in.** In RDF I could attach a source to any single fact with an RDF-star note. I expected Neo4j to work the same way, but a property can't carry its own source, so I designed receipts. Provenance has to be part of the model from the start, not added later.
- **RDF gave me things for free that Neo4j didn't.** A fact stated twice is stored once (a graph is a set), and everything has a global name. In Neo4j I had to add ids, uniqueness rules, and a check that stops the build if a link is stated twice.
- **Queries follow the shape.** "Every fact about this company, with its source" is one pattern in SPARQL but three joined parts in Cypher; following links and reading sources was faster in Neo4j (Q11: 92 ms against 1.5 ms).
- **How I worked.** Building the second graph sent me back to learn both query languages properly. I learned which parts I needed to understand in depth (the design, the checks, the scoring) and which I could leave to Claude Code to write, checking its output.

## A new kind of fact: when a stake began and ended

**What the source gives.** Companies House states, for each person with significant control, `notified_on` (51 of our stakes) and, once control ends, `ceased_on` (14). It does not give the date a stake *began*: 17 of the 51 show 6 April 2016, the day the register started, which means "already in control then", not "began then". So the facts are recorded as given (`notifiedOn`, `ceasedOn`), and any "began" date would be our own judgement, made by a named rule and labelled as such (D-029).

**In RDF.** A stake is already a node, because control comes in kinds and bands rather than one "owns" arrow. Adding a date is adding a triple, `?stake ex:ceasedOn "2024-10-11"^^xsd:date`, with its own RDF-star note pointing to the Companies House record. Nothing else changes: no migration, and every existing query still works. A SHACL shape would add the rules (a date, at most one, not before the notification). "Who controlled X on 1 January 2024?" becomes a filter: notified on or before that date, and either not ceased or ceased after it.

**In the property graph.** The same dates become properties on the Stake node, stored as real dates (build rule 2), and the receipts pick them up automatically, so their source is listed like any other value. One build check would be added, and an index on the dates if time queries became common. Had I modelled a stake as a relationship (`HOLDS`), the dates could sit on the relationship, but per-value sources would not fit there; that is one reason a stake is a node.

**In vector search.** Nothing to model, so nothing gained: the dates stay inside sentences, and "on this date" questions still cannot be answered.

**In our pipeline,** both builders are generic (fact cards in, graph out), so a new kind of fact on an existing node type is a parser change, a SHACL shape and a check, not a redesign.

## Results, candidly

| Area | Result | Where |
|---|---|---|
| Extraction | 30 releases; every field's quote checked against its sentence; 9 rejections, 3 the model's and 6 our pipeline's (a sentence splitter that cuts at initials, a truncated teaser) | `docs/extraction-report.md` |
| Matching (50 names, hand-checked) | Agreement 89% (weighted); recall of links 86%; strict precision 38%, because for named funds with a sponsor word the code links the sponsor (D-103) where I judged "ambiguous". Of the code's 17 links, 16 point at the right sponsor or company; 1 sits on a non-company read as a target. Partly judged with Claude's help, reported by group (D-119) | `docs/matching-eval.md` |
| Questions | 10 questions, identical answers in SPARQL and Cypher (answer columns compared row by row); every row cites its sources in both | `docs/answers-*.md` |
| Comparison (10 questions) | Overall: text-to-SPARQL 0.44, text-to-Cypher 0.30, vector search 0.00. The translators understood the questions but tripped on our graph's conventions (escaping, list properties, how sources are cited); some Cypher queries failed silently (no rows, or 145 invented rows) | `docs/comparison.md` |

**What did not work, or is missing:** timings on a larger dataset (the method: generate a scaled copy of the fact list, or widen the sponsor list, and re-run the same timed queries); a refresh that records what changed between fetches; matching for bought companies, which stay "news-only" until they are looked up in Companies House; four fixes to the comparison's own scoring after its first run, each disclosed with its reason (D-125).

**In a real deployment** I would add: scheduled refreshes with history; access rules by label and property (Neo4j Enterprise), which the receipts design already allows; entity matching at scale with an LLM proposing and a sampled human audit; and a larger question set with answer keys, since an answer key is the only way to know when a generated query is wrong.
