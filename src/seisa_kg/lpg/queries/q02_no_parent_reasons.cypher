// SUMMARY: Investor question 2 in Cypher (the twin of rdf/queries/q02_no_parent_reasons.rq).
// QUESTION: For each sponsor, how many of its companies report no parent to GLEIF, and for what reason?
// WHY: It shows where the public register cannot reveal ownership, and why (funds don't consolidate what they own), so an investor knows where the data stops.
// TYPE: counting, grouped; shows gaps openly (D-026, primer section 3.3).
// KEY: sponsorName, reason
// VALUE: companies
// NOTE: companies that do report a parent, or give no Level 2 information at all (F13), are counted too, so every In company appears exactly once.

// Every company the scope rule says is In for a sponsor.
MATCH (company:Company)-[scope:IN_SCOPE_OF]->(sponsor:Sponsor)
// Only the In verdicts.
WHERE scope.verdict = "In"
// The receipt for GLEIF's stated "no parent" reason, if there is one (a value's source is on its receipt, D-110).
OPTIONAL MATCH (company)-[receipt:DERIVED_FROM]->(exceptionRecord:SourceRecord)
// Only receipts that vouch for the exception.
WHERE "directParentException" IN receipt.properties
// An actual direct parent, if there is one (a link carries its own source record).
OPTIONAL MATCH (company)-[parent:DIRECTLY_CONSOLIDATED_BY]->()
// That link's source record, if there is a link.
OPTIONAL MATCH (parentRecord:SourceRecord {id: parent.record})
// The answer's category: GLEIF's reason, or "reports a parent", or "no Level 2 information"; and whichever record applies.
WITH sponsor, company, coalesce(exceptionRecord, parentRecord) AS record,
     // GLEIF's reason first; otherwise say what we found instead.
     coalesce(company.directParentException,
              // A parent link means the company does report a parent.
              CASE WHEN parent IS NOT NULL THEN "(reports a parent)" ELSE "(no Level 2 information)" END) AS reason
// One row per sponsor and reason: how many companies, and the GLEIF records behind the answer.
RETURN sponsor.label AS sponsorName, reason, count(DISTINCT company) AS companies,
       // Every GLEIF web address the reasons came from (none for "no Level 2 information": there is no source for an absence).
       collect(DISTINCT record.url) AS sources,
       // The most recent fetch among those records.
       max(record.retrievedAt) AS latestFetch
// Sponsors alphabetically, the commonest reasons first.
ORDER BY sponsorName, companies DESC
