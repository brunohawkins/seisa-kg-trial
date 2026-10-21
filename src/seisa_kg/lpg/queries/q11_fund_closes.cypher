// SUMMARY: Investor question 11 in Cypher (the twin of rdf/queries/q11_fund_closes.rq).
// QUESTION: Which funds did each sponsor close, how big were they, and when?
// WHY: Fund size and timing show how much capital a sponsor has to deploy, and how recently investors backed it.
// TYPE: news extraction, read out with sources; sizes and dates exactly as written (never converted, F41).
// KEY: sponsorName, fund, closeType
// NOTE: only 5 fund closes were published in our releases (F40). The fund's name is linked to the sponsor's group, not to one legal entity (D-103: a fund is many vehicles).

// A fund close, the release that announced it, and the sponsor that published the release.
MATCH (close:FundClose)-[:ANNOUNCED_IN]->(release:Release)-[:PUBLISHED_BY]->(sponsor:Sponsor)
// Every receipt from the close to a news sentence (a sentence's id has two slashes after "src:news/").
MATCH (close)-[receipt:DERIVED_FROM]->(sentence:SourceRecord) WHERE sentence.id =~ "src:news/[^/]+/[^/]+"
// One row per fund close: sponsor, fund, kind of close, size and date as written, when announced, and the sentences behind it.
RETURN sponsor.label AS sponsorName, close.fundName AS fund, close.closeType AS closeType, close.fundSize AS size,
       // The date as written, and the release's publication date.
       close.closeDate AS closeDate, release.publishedOn AS published,
       // Every sentence the facts came from.
       collect(DISTINCT sentence.id) AS sources
// Sponsors alphabetically, then by publication date.
ORDER BY sponsorName, published
