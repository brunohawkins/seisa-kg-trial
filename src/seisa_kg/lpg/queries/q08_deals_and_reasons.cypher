// SUMMARY: Investor question 8 in Cypher (the twin of rdf/queries/q08_deals_and_reasons.rq).
// QUESTION: Which companies did each sponsor buy or sell in 2025–26, and what reason did the announcement give?
// WHY: It is the sponsor's recent dealmaking in one table, each deal with the reasons the sponsor itself gave and the sentences that say so.
// TYPE: news extraction, read out with sources; "why" answered only as "what reason the announcement gave" (D-071).
// KEY: sponsorName, target, side
// NOTE: the sponsor is the release's publisher. "sold" means the sponsor is on the seller side (a seller name linked to its group, or to one of its In companies); everything else counts as "bought" (including add-ons). The "commitments from Bridgepoint Direct Lending II" row is an extraction flaw (a non-company read as a target), kept visible on purpose.

// A deal, the release that announced it, and the sponsor that published the release.
MATCH (deal:Deal)-[:ANNOUNCED_IN]->(release:Release)-[:PUBLISHED_BY]->(sponsor:Sponsor)
// Only 2025 and 2026 (publishedOn is a real date, rule 2).
WHERE release.publishedOn >= date("2025-01-01")
// "sold" if the sponsor is on the seller side; otherwise "bought".
WITH deal, release, sponsor,
     // A seller name linked to the sponsor's group...
     CASE WHEN EXISTS { MATCH (deal)-[:SELLER_MATCH]->(:Match)-[:REFERS_TO_GROUP]->(sponsor) }
               // ...or to one company the scope rule says is the sponsor's.
               OR EXISTS { MATCH (deal)-[:SELLER_MATCH]->(:Match)-[:SAME_ENTITY_AS]->(:Company)-[s:IN_SCOPE_OF]->(sponsor) WHERE s.verdict = "In" }
          THEN "sold" ELSE "bought" END AS side
// The receipts from the deal to the sentences behind the target name or the reasons.
MATCH (deal)-[receipt:DERIVED_FROM]->(sentence:SourceRecord)
// Only those receipts.
WHERE "targetName" IN receipt.properties OR "statedReason" IN receipt.properties
// One row per deal: sponsor, target, bought or sold, the kind of deal, when, the reasons, and the sentences behind them.
RETURN sponsor.label AS sponsorName, deal.targetName AS target, side, deal.dealKind AS kind, release.publishedOn AS published,
       // The reasons (a list property, rule 3), joined with " | ".
       reduce(text = "", reason IN coalesce(deal.statedReason, []) | text + CASE WHEN text = "" THEN "" ELSE " | " END + reason) AS reasons,
       // Every sentence they came from.
       collect(DISTINCT sentence.id) AS sources
// Sponsors alphabetically, then by date.
ORDER BY sponsorName, published, target
