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
