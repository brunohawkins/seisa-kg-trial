// SUMMARY: Investor question 2 in Cypher (placeholder draft, D-058); the same question as q02_no_parent_reasons.rq.
// QUESTION: For each sponsor, how many of its companies report no parent to GLEIF, and for what reason?
// WHY: It shows where the public register cannot reveal ownership, and why (funds don't consolidate what they own), so an investor knows where the data stops.
// TYPE: counting, grouped; shows gaps openly (D-026, primer section 3.3).
// KEY: sponsorName, reason
// VALUE: companies
// NOTE: companies that do report a parent, or give no Level 2 information at all (F13), are counted too, so every In company appears exactly once.

// A scope decision saying the company belongs to a sponsor...
MATCH (d:ScopeDecision {verdict: 'In'})-[:FOR]->(s:Sponsor)
// ...that no hand decision has replaced.
WHERE NOT EXISTS { (:ScopeDecision)-[:REVISES]->(d) }
// The company the decision is about.
MATCH (d)-[:ABOUT]->(e:LegalEntity)
// A receipt giving GLEIF's reason for no direct parent, if there is one.
OPTIONAL MATCH (e)-[:STATED_IN]->(xr:SourceRecord) WHERE xr.directParentException IS NOT NULL
// An actual direct parent, if there is one.
OPTIONAL MATCH (e)-[p:DIRECT_PARENT]->()
// The receipt for that parent link, if there is one.
OPTIONAL MATCH (e)-[:STATED_IN]->(pr:SourceRecord) WHERE pr.id IN p.sources
// The answer's category: GLEIF's reason, or "reports a parent", or "no Level 2 information"; and whichever receipt applies.
WITH s, e, coalesce(xr.directParentException, CASE WHEN p IS NULL THEN '(no Level 2 information)' ELSE '(reports a parent)' END) AS reason,
     // The receipt: the exception's, else the parent link's.
     coalesce(xr, pr) AS r
// One group per sponsor and reason: how many companies, the receipts' addresses, the latest fetch.
WITH s.name AS sponsorName, reason, count(DISTINCT e) AS companies, collect(DISTINCT r.url) AS urls, max(r.retrievedAt) AS latestFetch
// The answer columns, matching the SPARQL version; the addresses joined with spaces.
RETURN sponsorName, reason, companies, reduce(t = head(urls), u IN tail(urls) | t + ' ' + u) AS sources, latestFetch
// Sponsors alphabetically, the commonest reasons first.
ORDER BY sponsorName, companies DESC
