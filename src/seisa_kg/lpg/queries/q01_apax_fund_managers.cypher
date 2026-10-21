// SUMMARY: Investor question 1 in Cypher (the twin of rdf/queries/q01_apax_fund_managers.rq).
// QUESTION: Which companies does GLEIF say manage Apax's funds, and how many fund vehicles does each one manage?
// WHY: An investor needs to know which legal entity acts for a fund: who signs, and who the counterparty is.
// TYPE: several links (sponsor -> scope decision -> fund -> manager), then counting.
// KEY: manager|managerName
// VALUE: funds
// NOTE: GLEIF's "fund manager" can be a GP company or a management company (F4, D-027), so the answer says "manager per GLEIF", not "GP".

// A company the scope rule says is Apax's (the scope decision is a relationship here, D-112c)...
MATCH (fund:Company)-[scope:IN_SCOPE_OF]->(:Sponsor {id: "ex:sponsor/apax"})
// ...with the verdict In. (No hand decision has replaced any scope decision yet; RDF checks that with prov:wasRevisionOf.)
WHERE scope.verdict = "In"
// GLEIF's fund-manager link from the fund to its manager; the link carries its own source record.
MATCH (fund)-[managed:FUND_MANAGED_BY]->(manager:Company)
// That source record's node, for its web address and fetch time.
MATCH (record:SourceRecord {id: managed.record})
// One row per manager: its name, how many Apax funds it manages, the GLEIF records behind those links, the latest fetch.
RETURN manager.id AS manager, manager.legalName AS managerName, count(DISTINCT fund) AS funds,
       // Every GLEIF web address the links came from.
       collect(DISTINCT record.url) AS sources,
       // The most recent fetch among those records.
       max(record.retrievedAt) AS latestFetch
// Biggest managers first.
ORDER BY funds DESC, managerName
