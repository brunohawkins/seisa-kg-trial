// SUMMARY: Investor question 4 in Cypher (the twin of rdf/queries/q04_every_fact_about_a_company.rq).
// QUESTION: For Bridgepoint Group plc, what is every fact we hold, and which record or rule did each one come from?
// WHY: It is the audit view: nothing in the graph is unsourced, and an investor can check any fact against the exact record (or see that it is our own judgement, and which rule made it).
// TYPE: provenance; one company's two records (GLEIF and Companies House, joined by D-025), every fact with its source.
// KEY: node, fact, value
// NOTE: facts made by our own rules (status groups, address keys, the GLEIF-Companies House link) cite the rule, not a record. Types are left out.
// In Neo4j a fact lives in one of three places, so the answer has three parts joined by UNION: values (sourced by receipts), links (sourced on the link), and names (their own nodes).

// Part 1, values: the company's GLEIF node and the Companies House node D-025 links it to...
MATCH (start:Company {id: "lei:213800KFNMVI8PDZX472"})
// ...the Companies House node, if any.
OPTIONAL MATCH (start)-[:SAME_ENTITY_AS]->(other:Company)
// Both nodes, one row each (dropping a missing one).
UNWIND [start, other] AS node
// Each receipt from the node to a source record or one of our rules.
MATCH (node)-[receipt:DERIVED_FROM|GENERATED_BY]->(source) WHERE node IS NOT NULL
// One row per property the receipt vouches for (its lists line up: properties[i] with values[i]).
UNWIND range(0, size(receipt.properties) - 1) AS i
// The fact and its value, leaving out the label (the type).
WITH node, receipt.properties[i] AS fact, receipt.values[i] AS value, source WHERE fact <> "_label"
// One row per fact, with every record or rule behind it.
RETURN node.id AS node, fact, value, collect(DISTINCT source.id) AS sources

// Part 2, links from the company to other nodes: each carries its source (record) or rule on itself.
UNION
// The two nodes again.
MATCH (start:Company {id: "lei:213800KFNMVI8PDZX472"})
// The Companies House node, if any.
OPTIONAL MATCH (start)-[:SAME_ENTITY_AS]->(other:Company)
// One row each.
UNWIND [start, other] AS node
// Every link out, except receipts, names (part 3) and scope decisions (a decision about the company, not a fact about it).
MATCH (node)-[link]->(target) WHERE node IS NOT NULL AND NOT type(link) IN ["DERIVED_FROM", "GENERATED_BY", "HAS_OTHER_NAME", "HAS_PREVIOUS_NAME", "IN_SCOPE_OF"]
// The link's name written the RDF way, e.g. SAME_ENTITY_AS -> sameEntityAs (lower case, then each later word capitalised).
WITH node, link, target, reduce(name = "", word IN split(toLower(type(link)), "_") |
                                name + CASE WHEN name = "" THEN word ELSE toUpper(left(word, 1)) + substring(word, 1) END) AS fact
// One row per link, with its record, or its rule written as the rule's id.
RETURN node.id AS node, fact, target.id AS value, collect(DISTINCT coalesce(link.record, "ex:rule/" + link.rule)) AS sources

// Part 3, other and previous names: each is its own :Name node, sourced by its receipt.
UNION
// The two nodes again.
MATCH (start:Company {id: "lei:213800KFNMVI8PDZX472"})
// The Companies House node, if any.
OPTIONAL MATCH (start)-[:SAME_ENTITY_AS]->(other:Company)
// One row each.
UNWIND [start, other] AS node
// Each name and the receipt for its value.
MATCH (node)-[:HAS_OTHER_NAME|HAS_PREVIOUS_NAME]->(name:Name)-[receipt:DERIVED_FROM]->(source) WHERE node IS NOT NULL AND "value" IN receipt.properties
// One row per name (the same name in two periods counts once, as in RDF), with its records.
RETURN node.id AS node, name.kind AS fact, name.value AS value, collect(DISTINCT source.id) AS sources
