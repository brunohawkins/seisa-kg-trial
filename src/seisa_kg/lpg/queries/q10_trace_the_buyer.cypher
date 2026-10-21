// SUMMARY: Investor question 10 in Cypher (the twin of rdf/queries/q10_trace_the_buyer.rq).
// QUESTION: For a deal in the news, trace the buyer named in the release to our legal entities and up to the sponsor, with a source (sentence or registry record) for each link.
// WHY: It joins the two worlds: what a press release says, and what the registers say. Each hop has its own evidence, so an investor can see exactly where the trail is solid and where it stops.
// TYPE: several links across sources (sentence -> match -> legal entity -> scope decision -> sponsor), every hop with its source or rule.
// KEY: deal, buyerAsWritten, outcome, linkedTo
// NOTE: names that can't be linked (ambiguous, out of scope, ...) are shown too, with an empty trail, so the answer says where tracing stops.

// A deal and one of its buyer names (each name has its own Match node, D-108).
MATCH (deal:Deal)-[:BUYER_MATCH]->(m:Match)
// Hop 1's evidence: the receipt to the sentence the name came from.
MATCH (m)-[nameReceipt:DERIVED_FROM]->(sentence:SourceRecord) WHERE "nameAsWritten" IN nameReceipt.properties
// Hop 2's evidence: the receipt to the rule that decided the outcome.
MATCH (m)-[ruleReceipt:GENERATED_BY]->(rule:Rule) WHERE "outcome" IN ruleReceipt.properties
// Linked to a sponsor's group, if so.
OPTIONAL MATCH (m)-[:REFERS_TO_GROUP]->(group:Sponsor)
// Linked to one legal entity, if so.
OPTIONAL MATCH (m)-[:SAME_ENTITY_AS]->(company:Company)
// The registry record(s) behind that company's legal name (its receipts).
OPTIONAL MATCH (company)-[nameSource:DERIVED_FROM]->(registry:SourceRecord) WHERE "legalName" IN nameSource.properties
// Up one more hop: the sponsor whose scope the company is In (the scope decision is a relationship, with its rule on it).
OPTIONAL MATCH (company)-[scope:IN_SCOPE_OF]->(owner:Sponsor) WHERE scope.verdict = "In"
// One row per deal and buyer name.
RETURN deal.id AS deal, m.nameAsWritten AS buyerAsWritten, collect(DISTINCT sentence.id) AS buyerSentence,
       // The match's outcome and the rule that decided it.
       m.outcome AS outcome, rule.id AS matchRule,
       // Where it links (one company, or the sponsor's group), and that company's legal name.
       coalesce(company.id, group.id) AS linkedTo, company.legalName AS legalName,
       // The registry records behind the legal name.
       collect(DISTINCT registry.id) AS registryRecords,
       // The sponsor at the end of the trail, and the rule that put the company in its scope.
       coalesce(group.label, owner.label) AS sponsorName, scope.rule AS scopeRule
// In deal order.
ORDER BY deal, buyerAsWritten
