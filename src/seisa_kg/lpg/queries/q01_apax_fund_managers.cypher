// SUMMARY: Investor question 1 in Cypher (placeholder draft, D-058); the same question as q01_apax_fund_managers.rq.
// QUESTION: Which companies does GLEIF say manage Apax's funds, and how many fund vehicles does each one manage?
// WHY: An investor needs to know which legal entity acts for a fund: who signs, and who the counterparty is.
// TYPE: several links (sponsor -> scope decision -> fund -> manager), then counting.
// KEY: manager|managerName
// VALUE: funds
// NOTE: GLEIF's "fund manager" can be a GP company or a management company (F4, D-027), so the answer says "manager per GLEIF", not "GP".

// A scope decision saying the fund belongs to Apax...
MATCH (d:ScopeDecision {verdict: 'In'})-[:FOR]->(:Sponsor {key: 'apax'})
// ...that no hand decision has replaced (D-037, D-052).
WHERE NOT EXISTS { (:ScopeDecision)-[:REVISES]->(d) }
// The fund the decision is about.
MATCH (d)-[:ABOUT]->(fund:LegalEntity)
// GLEIF's fund-manager link from the fund to its manager.
MATCH (fund)-[m:MANAGED_BY]->(manager:LegalEntity)
// The receipt(s) the link came from: the link lists their IDs (D-063).
MATCH (fund)-[:STATED_IN]->(r:SourceRecord) WHERE r.id IN m.sources
// One group per manager: how many funds, the receipts' web addresses, the latest fetch.
WITH manager, count(DISTINCT fund) AS funds, collect(DISTINCT r.url) AS urls, max(r.retrievedAt) AS latestFetch
// The answer columns, matching the SPARQL version; the addresses joined with spaces.
RETURN manager.lei AS manager, manager.legalName AS managerName, funds,
       // Join the list of addresses into one text, separated by spaces.
       reduce(s = head(urls), u IN tail(urls) | s + ' ' + u) AS sources, latestFetch
// Biggest managers first.
ORDER BY funds DESC, managerName
