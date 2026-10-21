// SUMMARY: Investor question 3 in Cypher (the twin of rdf/queries/q03_lapsed_leis.rq).
// QUESTION: Which of each sponsor's companies have a lapsed or retired LEI, and when did GLEIF last tell us so?
// WHY: A lapsed LEI means GLEIF no longer re-checks the company's data: a red flag for counterparty checks and for any fact about that company.
// TYPE: time and data quality; the answer reads each fact's own source and fetch date (D-046, D-042).
// KEY: sponsorName, entity|name, status

// Every company the scope rule says is In for a sponsor.
MATCH (company:Company)-[scope:IN_SCOPE_OF]->(sponsor:Sponsor)
// Only the In verdicts.
WHERE scope.verdict = "In"
// The registration status is a list on every node (rule 3: one company had two statuses across fetches); one row per status.
UNWIND company.registrationStatus AS status
// Only the lapsed or retired ones.
WITH sponsor, company, status WHERE status IN ["LAPSED", "RETIRED"]
// Every receipt from the company to a GLEIF record...
MATCH (company)-[receipt:DERIVED_FROM]->(record:SourceRecord)
// ...that vouches for this exact status (the receipt's lists line up: properties[i] goes with values[i]).
WHERE any(i IN range(0, size(receipt.properties) - 1)
          // Same property, same value.
          WHERE receipt.properties[i] = "registrationStatus" AND receipt.values[i] = status)
// One row per company and status: who, which status, when GLEIF last said so, and where.
RETURN sponsor.label AS sponsorName, company.id AS entity, company.legalName AS name, status,
       // The latest fetch that stated it.
       max(record.retrievedAt) AS lastToldUs,
       // Every GLEIF web address that stated it.
       collect(DISTINCT record.url) AS sources
// Sponsors alphabetically, then retired before lapsed, then by name.
ORDER BY sponsorName, status DESC, name
