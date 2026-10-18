// SUMMARY: Investor question 3 in Cypher (placeholder draft, D-058); the same question as q03_lapsed_leis.rq.
// QUESTION: Which of each sponsor's companies have a lapsed or retired LEI, and when did GLEIF last tell us so?
// WHY: A lapsed LEI means GLEIF no longer re-checks the company's data: a red flag for counterparty checks and for any fact about that company.
// TYPE: time and data quality; the answer reads each fact's own receipt and fetch date (D-046, D-042, D-063).
// KEY: sponsorName, entity|name, status

// A scope decision saying the company belongs to a sponsor...
MATCH (d:ScopeDecision {verdict: 'In'})-[:FOR]->(s:Sponsor)
// ...that no hand decision has replaced.
WHERE NOT EXISTS { (:ScopeDecision)-[:REVISES]->(d) }
// The company the decision is about.
MATCH (d)-[:ABOUT]->(e:LegalEntity)
// Every receipt that gave its LEI status as lapsed or retired (one per fetch, D-042).
MATCH (e)-[:STATED_IN]->(r:SourceRecord) WHERE r.registrationStatus IN ['LAPSED', 'RETIRED']
// One group per company and status: when GLEIF last said so, and every receipt that said it.
WITH s.name AS sponsorName, e, r.registrationStatus AS status, max(r.retrievedAt) AS lastToldUs, collect(DISTINCT r.url) AS urls
// The answer columns, matching the SPARQL version; the addresses joined with spaces.
RETURN sponsorName, e.lei AS entity, e.legalName AS name, status, lastToldUs,
       // Join the list of addresses into one text, separated by spaces.
       reduce(t = head(urls), u IN tail(urls) | t + ' ' + u) AS sources
// Sponsors alphabetically, then retired before lapsed, then by name.
ORDER BY sponsorName, status DESC, name
