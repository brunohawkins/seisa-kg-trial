// SUMMARY: Investor question 5 in Cypher (the twin of rdf/queries/q05_source_disagreements.rq), first version: status and address only.
// QUESTION: Where do GLEIF and Companies House disagree about the same company's status or address, and what does each say?
// WHY: A disagreement flags a stale or wrong record before anyone relies on it; e.g. GLEIF calling a company INACTIVE while Companies House says it is active.
// TYPE: cross-source conflict; compares tidy keys (D-092, D-093) but shows each source's own words and record.
// KEY: company|name, field

// A GLEIF company linked to a Companies House company by rule D-025 (labels keep out the Match nodes' own SAME_ENTITY_AS links).
MATCH (gleif:Company:Gleif)-[:SAME_ENTITY_AS]->(ch:Company:CompaniesHouse)
// The two fields compared: each with its tidy key (made by our rules) and the value as the source gave it.
UNWIND [["status", "statusGroup", "entityStatus"], ["address", "addressKey", "legalAddress"]] AS pair
// Name the three parts.
WITH gleif, ch, pair[0] AS field, pair[1] AS tidyKey, pair[2] AS asGiven
// Only the real disagreements (both sides have the key, and the keys differ).
WHERE gleif[tidyKey] IS NOT NULL AND ch[tidyKey] IS NOT NULL AND gleif[tidyKey] <> ch[tidyKey]
// The GLEIF receipts that vouch for what GLEIF says.
MATCH (gleif)-[r1:DERIVED_FROM]->(gleifRecord:SourceRecord) WHERE asGiven IN r1.properties
// The Companies House receipts that vouch for what Companies House says.
MATCH (ch)-[r2:DERIVED_FROM]->(chRecord:SourceRecord) WHERE asGiven IN r2.properties
// One row per company and field: what each side says, and the records behind each side.
RETURN gleif.id AS company, gleif.legalName AS name, field, gleif[asGiven] AS gleifSays, ch[asGiven] AS chSays,
       // GLEIF's records (it may have said it on two dates) and Companies House's.
       collect(DISTINCT gleifRecord.url) AS gleifSources, collect(DISTINCT chRecord.url) AS chSources
// Grouped by field, then by name.
ORDER BY field, name
