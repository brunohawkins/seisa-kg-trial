# Talking points: for the write-up and the discussion with Anish

Points Bruno wants to raise once everything is finished. Each one gives the evidence behind it, so it can be defended. New points get added as we go.

## 1. What public data can't tell an investor, and how the graph shows that openly (D-073)
We deliberately stayed with three sources (GLEIF, Companies House, news). The gaps are part of the result, not a failure. The brief says: *"Expect the data to be imperfect … Your model should represent these gaps openly."*

| Gap | Why it exists | How the graph shows it |
|---|---|---|
| **Who controls most fund vehicles** | 124 of our 153 Companies House companies are English LPs, which the law doesn't require to report controllers (F24). Most other funds are offshore: Apax 101 of 160 in Guernsey, Bridgepoint 87 of 186 in Luxembourg (F23) | Companies House's "not found" is recorded; GLEIF's reason for no parent is stored as a fact (D-026) |
| **No parent in GLEIF** | GLEIF only records a parent that **consolidates** the company in its accounts, and funds usually aren't consolidated | `directParentException` facts, e.g. NON_CONSOLIDATING; Q2 counts them per sponsor |
| **Stated "no controller"** | Companies House allows a statement that there is no registrable controller (e.g. Group Holdco 1 Ltd, F31) | Stored as a stated absence, like GLEIF's exceptions |
| **The sources disagree** | Different tests: GLEIF = accounting consolidation; Companies House = 25%+ control. E.g. Bridgepoint Advisers Ltd: GLEIF says "NO_KNOWN_PERSON", while Companies House says 75–100% owned by Bridgepoint Advisers Holdings | Both kept, each with its source (D-029); Q5 lists the disagreements |
| **Exact stakes** | Companies House gives bands (25–50 / 50–75 / 75–100%) only (F27) | The band is stored as given, never turned into a made-up number |
| **Fund investors (LPs), deal prices** | Private by nature; only paid databases have them | Not stored. Said openly rather than guessed |
| **Offshore chains** | Companies House stops at non-UK companies (e.g. Lux Topco 1 Sàrl, F32) | The chain ends at the offshore company; GLEIF may continue it if the company has an LEI |

**The one-line version:** "The graph doesn't just answer questions; it shows where public data runs out, and why."

## 2. The three-way comparison: what it showed (D-124, D-125)
Ten investor questions, each answered three ways from the plain-English question alone, scored against the hand-written answers by the same scorer (`docs/comparison.md`).

| Method | Overall | Correctness | Citation | Didn't run | Said "not found" |
|---|---|---|---|---|---|
| text-to-SPARQL | 0.44 | 0.41 | 0.47 | 3 | 0 |
| text-to-Cypher | 0.30 | 0.33 | 0.28 | 3 | 0 |
| vector search | 0.00 | 0.00 | 0.00 | 0 | 8 |

**What to say about it:**
- **The LLM understands the question; it trips on the graph's specifics.** Both translators got some questions exactly right (SPARQL: Q3, Q11, 0.95 on Q8; Cypher: Q1, Q11). They failed on escaping, list properties, receipts and how sources are written: the conventions of *our* graph, not the logic of the question.
- **The best single example, Q1:** Gemini's SPARQL is almost word for word our own query, but it wrote `ex:sponsor/apax` without escaping the "/", so it never ran. That's the trap the phrasebook warns about, and the one we hit ourselves. Its Cypher for the same question was perfect, because a sponsor in Neo4j is just `{id: "ex:sponsor/apax"}`, a string.
- **Silent failure is the dangerous kind.** Some queries ran and returned nothing (Cypher Q9, Q12) or far too much (Cypher Q5 with 145 invented rows, Q10 with 165). An error is easy to catch; a plausible wrong table is not. That's why every answer is checked against a hand-written answer key.
- **Vector search can't answer structured questions.** It said "not found" on 8 of 10, and its 2 answers scored 0. For registry questions the answer isn't in any sentence (the Apax fund managers exist only in GLEIF). For news questions, 5 sentences can't hold a list of 28 deals, a count, or a trail across sources. Its similarity scores bunch together (Q11: 0.691–0.702 for right and wrong sentences alike), so the 5 slots fill with near-misses. Its one strength: it said "not found" instead of inventing.
- **Even when it finds the right sentence, the wording differs:** for Q11 it found "Apax holds final close for eleventh global buyout fund", not "Apax XI fund", so the scorer can't match it. A graph stores one agreed name; text doesn't.
- **The design that made it trustworthy is the same as extraction's: the model proposes, the code checks.** Blocked words and made-up names are rejected before anything runs, the query runs read-only with a 10-second limit, and there are no retries, so the failure rate is honest.

**Honesty about the method (say it before they ask):**
- Ten questions, one model, one run: a small sample. It shows where each method breaks, not a precise ranking.
- Four fixes on our side were made after the first run, each because it scored a right answer as wrong (D-125): the Cypher name check, citations by web address, Q4's wording, and Q8's "bought/sold" wording. After them, the hand-written answers still score 1.0 through the same path. Q4 was asked again after its wording changed, and did worse.
- The phrasebook was written by us, from our schema docs; a better phrasebook (more examples, the escaping rule earlier) would likely raise both translators' scores. That's a fair next step.

**The one-line version:** "An LLM can write a good query, but only a graph with explicit structure and an answer key lets you know when it hasn't."
