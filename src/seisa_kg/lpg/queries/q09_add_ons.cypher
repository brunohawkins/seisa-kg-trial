// SUMMARY: Investor question 9 in Cypher (the twin of rdf/queries/q09_add_ons.rq).
// QUESTION: Which buys were add-ons (merged into an existing portfolio company), and what reason was given?
// WHY: Add-ons show a sponsor's buy-and-build strategy: which portfolio companies it is growing by acquisition, and the reasons it gives.
// TYPE: news extraction, filtered by deal kind; the existing portfolio company is the buyer named in the release.
// KEY: sponsorName, target
// NOTE: the deal kind "add-on" is Gemini's reading of the release, checked against its quote (D-085). The buyer is the portfolio company as named (e.g. WGSN), not linked to a registry entity.

// A deal Gemini read as an add-on, the release that announced it, and the sponsor that published the release.
MATCH (deal:Deal {dealKind: "add-on"})-[:ANNOUNCED_IN]->(release:Release)-[:PUBLISHED_BY]->(sponsor:Sponsor)
// The receipts to the sentences behind the target, the buyer and the reasons.
MATCH (deal)-[receipt:DERIVED_FROM]->(sentence:SourceRecord)
// Only those receipts.
WHERE any(p IN ["targetName", "buyerName", "statedReason"] WHERE p IN receipt.properties)
// One row per add-on: sponsor, the company bought, the portfolio company that bought it, when, the reasons, and the sentences.
RETURN sponsor.label AS sponsorName, deal.targetName AS target,
       // The buyer names (a list property, rule 3), joined with " | ".
       reduce(text = "", b IN coalesce(deal.buyerName, []) | text + CASE WHEN text = "" THEN "" ELSE " | " END + b) AS buyer,
       // When it was announced.
       release.publishedOn AS published,
       // The reasons (a list property), joined with " | ".
       reduce(text = "", r IN coalesce(deal.statedReason, []) | text + CASE WHEN text = "" THEN "" ELSE " | " END + r) AS reasons,
       // Every sentence they came from.
       collect(DISTINCT sentence.id) AS sources
// Sponsors alphabetically, then by date.
ORDER BY sponsorName, published
