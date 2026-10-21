// SUMMARY: Investor question 12 in Cypher (the twin of rdf/queries/q12_shared_advisers.rq).
// QUESTION: Which banks or law firms advised on deals for more than one of our sponsors?
// WHY: Shared advisers show who sits at the centre of the sponsors' dealmaking, and where information or conflicts could cross between sponsors.
// TYPE: counting across sponsors (a "more than one" question: count, then filter on the count).
// KEY: adviser
// VALUE: sponsors
// NOTE: advisers are matched by their name as written, in capitals (e.g. "Kirkland & Ellis LLP" and "Kirkland & Ellis" would count as two); advisers are not linked to registry entities (D-104). The sponsor is the release's publisher.

// A deal, one of its advisers, and the sponsor that published the deal's release.
MATCH (adv:Adviser)<-[:HAS_ADVISER]-(deal:Deal)-[:ANNOUNCED_IN]->(:Release)-[:PUBLISHED_BY]->(sponsor:Sponsor)
// The adviser's name is a list on every Adviser (rule 3: one adviser has two names); one row per name, like RDF's one triple per name.
UNWIND adv.name AS name
// The receipt to the sentence this exact name came from (the receipt's lists line up: properties[i] goes with values[i]).
MATCH (adv)-[receipt:DERIVED_FROM]->(sentence:SourceRecord)
// Same property, same value.
WHERE any(i IN range(0, size(receipt.properties) - 1) WHERE receipt.properties[i] = "name" AND receipt.values[i] = name)
// Count per adviser name in capitals (Cypher groups by the other columns automatically).
WITH toUpper(name) AS adviser, count(DISTINCT sponsor) AS sponsors,
     // The sponsors' names.
     collect(DISTINCT sponsor.label) AS sponsorNames,
     // How many deals.
     count(DISTINCT deal) AS deals,
     // Every sentence naming the adviser.
     collect(DISTINCT sentence.id) AS sources
// Only advisers that worked for more than one sponsor (filter after counting: WITH ... WHERE, Cypher's HAVING).
WHERE sponsors > 1
// One row per adviser.
RETURN adviser, sponsors, sponsorNames, deals, sources
// Most deals first, then by name.
ORDER BY deals DESC, adviser
