"""SUMMARY: Pipeline stage 4 (build) for the Neo4j property graph. Reads the
same shared fact list as the RDF builder (data/interim/facts.jsonl, D-012),
rebuilds the project's own Neo4j database from scratch, and checks it.

The design (D-063, "receipt boxes"):
- (:LegalEntity {lei, ...latest values}): one per LEI; its properties are the
  latest values (D-051), a convenience copy for easy querying;
- (:SourceRecord {id, source, url, retrievedAt, ...values that reply gave}):
  one per GLEIF reply, linked by (entity)-[:STATED_IN]->(record), so history
  is kept (D-042) and every fact has a visible path to its source;
- (:LegalEntity)-[:MANAGED_BY | DIRECT_PARENT | ULTIMATE_PARENT {details, sources}]->(:LegalEntity);
- our judgements as nodes: (:ScopeDecision {verdict, reason}) with ABOUT,
  FOR and MADE_BY (and REVISES for hand decisions); (:Sponsor), (:Rule).

The checks, any of which stops the build:
- the graph is not empty;
- the node and relationship counts match the fact list (same data in both graphs);
- every source fact in the list is on its receipt (SourceRecord) node, and every
  value on a receipt is a source fact (checked both ways);
- every entity has at least one receipt, and every relationship has a source.

Needs the Neo4j server running (make neo4j-start); settings come from .env.
Run it with:  make neo4j-build
"""

# Groups things into lists by a key, and counts things.
from collections import Counter, defaultdict
# Reads environment settings (the Neo4j address and login).
import os
# Lets the program stop with an error code when a check fails.
import sys

# Loads the settings in .env into the environment, without printing them.
from dotenv import load_dotenv
# The official Neo4j connector.
from neo4j import GraphDatabase

# Reading the shared fact list.
from seisa_kg.facts.model import FACTS_PATH, PROJECT_ROOT, read_facts

# The link predicates that become relationships, and the relationship type each becomes.
LINKS = {"fundManagedBy": "MANAGED_BY", "directParent": "DIRECT_PARENT", "ultimateParent": "ULTIMATE_PARENT"}
# Predicates that can hold several values at once, stored as lists.
MULTI = {"otherName", "searchTerm"}


# Turn a short name into a plain ID: "lei:ABC" -> "ABC", "ex:sponsor/apax" -> "apax", "ex:In" -> "In".
def bare(short: str) -> str:
    # Keep only what comes after the last "/" or the first ":".
    return short.split(":", 1)[1].rsplit("/", 1)[-1]


# A row's object as a plain value: the ID for a link, the text for a value.
def value(row: dict) -> str:
    # Links become their bare ID; values stay as they are.
    return bare(row["object"]["iri"]) if "iri" in row["object"] else row["object"]["value"]


# Sort the fact rows into the nodes and relationships of the property graph.
def shape(rows: list[dict]) -> dict:
    # Source records: id -> {properties, the entity it describes}.
    records = {}
    # Each entity's values by predicate, newest record last: lei -> predicate -> [(fetch time, value)].
    history = defaultdict(lambda: defaultdict(list))
    # Relationships: (type, from, to) -> {details, sources}.
    links = {}
    # Our own nodes (sponsors, rules, scope decisions): subject -> predicate -> value or list.
    ours = defaultdict(lambda: defaultdict(list))
    # Go through every row.
    for r in rows:
        # A fact from a source (GLEIF).
        if r["origin"]["kind"] == "source":
            # The entity's LEI.
            lei = bare(r["subject"])
            # The origin block.
            o = r["origin"]
            # The record's node, created the first time it's seen.
            rec = records.setdefault(o["record"], {"lei": lei, "props": {"id": o["record"], "source": o["source"],
                                                                          # Where and when.
                                                                          "url": o["url"], "retrievedAt": o["retrieved_at"]}})
            # The type row only says "this is a legal entity"; the label covers it.
            if r["predicate"] == "type":
                # Nothing more to store.
                continue
            # A link: one relationship, with its details and the record as a source.
            if r["predicate"] in LINKS:
                # The relationship's key.
                key = (LINKS[r["predicate"]], lei, value(r))
                # Created the first time it's seen.
                link = links.setdefault(key, {"props": {k: v["value"] for k, v in r["details"].items()}, "sources": []})
                # Add this record as a source.
                link["sources"].append(o["record"])
            # The record also keeps what it said (for links, the other entity's LEI).
            if r["predicate"] in MULTI:
                # Several values: a list.
                rec["props"].setdefault(r["predicate"], []).append(value(r))
            # One value.
            else:
                # Store it under the predicate's name.
                rec["props"][r["predicate"]] = value(r)
            # Remember the value with its fetch time, to pick the latest later.
            history[lei][r["predicate"]].append((o["retrieved_at"], o["record"], value(r)))
        # One of our own facts (D-029): sponsors, rules and scope decisions.
        else:
            # Collect it under its subject.
            ours[r["subject"]][r["predicate"]].append(value(r))
    # Each entity's latest values (D-051): for each predicate, the value(s) from its most recent record.
    entities = {}
    # Each entity.
    for lei, preds in history.items():
        # Start with its LEI.
        props = {"lei": lei}
        # Each predicate, skipping links (they are relationships, not properties).
        for pred, seen in preds.items():
            # Links live on relationships.
            if pred in LINKS:
                # Skip.
                continue
            # The most recent record that stated this predicate.
            newest = max((t, rec) for t, rec, _ in seen)[1]
            # Its value(s).
            vals = [v for _, rec, v in seen if rec == newest]
            # A list for multi-valued predicates, otherwise the single value.
            props[pred] = sorted(set(vals)) if pred in MULTI else vals[0]
        # Keep the entity.
        entities[lei] = props
    # Hand back everything, sorted into its kind.
    return {"entities": entities, "records": records, "links": links, "ours": ours}


# Write everything to Neo4j, replacing whatever was there.
def write(session, g: dict) -> None:
    # Start from an empty database: the graph is always rebuilt from the fact list.
    session.run("MATCH (n) DETACH DELETE n")
    # One uniqueness rule per kind of node, so each ID exists once (also speeds up lookups).
    for label, prop in [("LegalEntity", "lei"), ("SourceRecord", "id"), ("Sponsor", "key"), ("Rule", "id"), ("ScopeDecision", "id")]:
        # Create the rule if it isn't there yet.
        session.run(f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE")
    # The entities, with their latest values.
    session.run("UNWIND $rows AS e CREATE (n:LegalEntity) SET n = e", rows=list(g["entities"].values()))
    # The receipts, each linked to the entity it describes.
    session.run("UNWIND $rows AS r MATCH (e:LegalEntity {lei: r.lei}) "
                # Create the receipt and the link.
                "CREATE (e)-[:STATED_IN]->(s:SourceRecord) SET s = r.props",
                # One row per record.
                rows=list(g["records"].values()))
    # The relationships, one type at a time (Cypher can't take a relationship type as a parameter).
    for rel_type in LINKS.values():
        # This type's relationships.
        rows = [{"from": f, "to": t, "props": {**v["props"], "sources": v["sources"]}}
                # Every link of this type.
                for (kind, f, t), v in g["links"].items() if kind == rel_type]
        # Create them between the two entities.
        session.run(f"UNWIND $rows AS x MATCH (a:LegalEntity {{lei: x.from}}), (b:LegalEntity {{lei: x.to}}) "
                    # The relationship, with its details and sources.
                    f"CREATE (a)-[r:{rel_type}]->(b) SET r = x.props", rows=rows)
    # Our own nodes, sorted by kind from their names.
    ours = g["ours"]
    # Rules: id and plain-English label.
    session.run("UNWIND $rows AS r CREATE (:Rule {id: r.id, label: r.label})",
                # Every subject named ex:rule/...
                rows=[{"id": bare(s), "label": p["label"][0]} for s, p in ours.items() if s.startswith("ex:rule/")])
    # Sponsors: key, name and search words, linked to the rule that chose them (D-040).
    session.run("UNWIND $rows AS r MATCH (rule:Rule {id: 'D-023'}) "
                # The sponsor node and its link to the rule.
                "CREATE (s:Sponsor {key: r.key, name: r.name, searchTerms: r.terms})-[:MADE_BY]->(rule)",
                # Every subject named ex:sponsor/...
                rows=[{"key": bare(s), "name": p["label"][0], "terms": p["searchTerm"]} for s, p in ours.items() if s.startswith("ex:sponsor/")])
    # Scope decisions: verdict and reason, linked to the entity, the sponsor and the rule (D-036).
    decisions = [{"id": s.split(":", 1)[1], "verdict": p["verdict"][0], "reason": p["reason"][0],
                  # The entity, sponsor and rule it points to.
                  "lei": p["entity"][0], "sponsor": p["sponsor"][0], "rule": p["wasGeneratedBy"][0],
                  # The automatic decision it revises, for hand decisions only.
                  "revises": p["wasRevisionOf"][0].split("/", 1)[1] if p.get("wasRevisionOf") else None,
                  # The date Bruno decided it, for hand decisions only.
                  "decidedOn": p["decidedOn"][0] if p.get("decidedOn") else None}
                 # Every subject named ex:scope/...
                 for s, p in ours.items() if s.startswith("ex:scope/")]
    # Create them and their three links.
    session.run("UNWIND $rows AS d MATCH (e:LegalEntity {lei: d.lei}), (s:Sponsor {key: d.sponsor}), (r:Rule {id: d.rule}) "
                # The decision node.
                "CREATE (x:ScopeDecision {id: d.id, verdict: d.verdict, reason: d.reason, decidedOn: d.decidedOn}) "
                # Its links.
                "CREATE (x)-[:ABOUT]->(e), (x)-[:FOR]->(s), (x)-[:MADE_BY]->(r)", rows=decisions)
    # Hand decisions point to the automatic decision they revise (D-037).
    session.run("UNWIND $rows AS d MATCH (x:ScopeDecision {id: d.id}), (old:ScopeDecision {id: d.revises}) "
                # The link.
                "CREATE (x)-[:REVISES]->(old)", rows=[d for d in decisions if d["revises"]])


# Run the checks. Returns a list of problems; empty means the graph passed.
def check(session, g: dict, rows: list[dict]) -> list[str]:
    # A helper: run a query that returns one number.
    one = lambda q: session.run(q).single()[0]
    # The problems found so far.
    problems = []
    # The graph must not be empty (F12).
    if one("MATCH (n) RETURN count(n)") == 0:
        # Nothing else is worth checking.
        return ["the Neo4j graph is empty"]
    # Node counts must match the fact list.
    expected = {"LegalEntity": len(g["entities"]), "SourceRecord": len(g["records"]),
                # Our own nodes.
                "ScopeDecision": sum(1 for s in g["ours"] if s.startswith("ex:scope/")),
                # Sponsors and rules.
                "Sponsor": sum(1 for s in g["ours"] if s.startswith("ex:sponsor/")), "Rule": sum(1 for s in g["ours"] if s.startswith("ex:rule/"))}
    # Compare each.
    for label, n in expected.items():
        # Count in Neo4j.
        got = one(f"MATCH (n:{label}) RETURN count(n)")
        # Report a mismatch.
        if got != n:
            # The problem.
            problems.append(f"{label}: expected {n}, found {got}")
    # Relationship counts must match too.
    for rel_type in LINKS.values():
        # Expected from the fact list.
        n = sum(1 for k in g["links"] if k[0] == rel_type)
        # Found in Neo4j.
        got = one(f"MATCH ()-[r:{rel_type}]->() RETURN count(r)")
        # Report a mismatch.
        if got != n:
            # The problem.
            problems.append(f"{rel_type}: expected {n}, found {got}")
    # Every source fact must be on its receipt, and every value on a receipt must be a source fact (D-012).
    # Compared in both directions: a one-way check misses invented values (found by damaging the graph on purpose).
    expected = {(r["origin"]["record"], r["predicate"], value(r)) for r in rows
                # Only source facts; the type rows are covered by the node label.
                if r["origin"]["kind"] == "source" and r["predicate"] != "type"}
    # What Neo4j actually holds on its receipts.
    actual = set()
    # Each receipt node.
    for rec in session.run("MATCH (s:SourceRecord) RETURN s"):
        # Its properties.
        props = dict(rec["s"])
        # Each property except the receipt's own description.
        for k, v in props.items():
            # Skip the id, source, address and fetch time.
            if k in ("id", "source", "url", "retrievedAt"):
                # Not a fact.
                continue
            # A list holds several values; each counts once.
            for item in (v if isinstance(v, list) else [v]):
                # One fact held in Neo4j.
                actual.add((props["id"], k, item))
    # Facts in the list but not in Neo4j.
    if expected - actual:
        # The problem.
        problems.append(f"{len(expected - actual)} source facts are missing from their receipt nodes")
    # Values in Neo4j that no source stated.
    if actual - expected:
        # The problem.
        problems.append(f"{len(actual - expected)} values on receipt nodes match no source fact")
    # Every entity has at least one receipt.
    orphans = one("MATCH (e:LegalEntity) WHERE NOT (e)-[:STATED_IN]->(:SourceRecord) RETURN count(e)")
    # Report them.
    if orphans:
        # The problem.
        problems.append(f"{orphans} entities have no receipt")
    # Every relationship names at least one source.
    unsourced = one("MATCH ()-[r:MANAGED_BY|DIRECT_PARENT|ULTIMATE_PARENT]->() WHERE size(coalesce(r.sources, [])) = 0 RETURN count(r)")
    # Report them.
    if unsourced:
        # The problem.
        problems.append(f"{unsourced} relationships have no source")
    # Hand back the problems.
    return problems


# Connect to Neo4j using the settings in .env.
def connect():
    # Load .env into the environment (values are never printed).
    load_dotenv(PROJECT_ROOT / ".env")
    # Open a connection with the address, user and password from .env.
    return GraphDatabase.driver(os.environ["NEO4J_URI"], auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]),
                                # Hide "unrecognised name" warnings: REVISES only exists once Bruno makes a hand decision (D-052).
                                notifications_disabled_classifications=["UNRECOGNIZED"])


# Build, check and report.
def main() -> None:
    # Read the shared fact list.
    rows = read_facts(FACTS_PATH)
    # Sort it into nodes and relationships.
    g = shape(rows)
    # Connect, and make sure the connection closes at the end.
    with connect() as driver:
        # Fail early, with a clear message, if the server isn't running.
        try:
            # Ask the server to confirm it is reachable.
            driver.verify_connectivity()
        # Any connection problem.
        except Exception as e:
            # Explain what to do.
            sys.exit(f"Can't reach Neo4j ({type(e).__name__}). Start it with: make neo4j-start")
        # One session for the whole build.
        with driver.session() as session:
            # Write the graph.
            write(session, g)
            # Count what was written.
            nodes = session.run("MATCH (n) RETURN count(n)").single()[0]
            # Count the relationships too.
            rels = session.run("MATCH ()-[r]->() RETURN count(r)").single()[0]
            # Say how big it is.
            print(f"Built the Neo4j graph: {len(rows)} facts -> {nodes} nodes, {rels} relationships")
            # Run the checks.
            problems = check(session, g, rows)
    # If anything failed, list it and stop with an error code, so `make` stops too.
    if problems:
        # One line per problem.
        for p in problems:
            # Print to the error stream.
            print("CHECK FAILED:", p, file=sys.stderr)
        # Exit with an error.
        sys.exit(1)
    # Every check passed.
    print("All checks passed: not empty; counts match the fact list; every source fact found on its receipt; every entity and link sourced")


# Run main() when this file is run directly, not when it is imported.
if __name__ == "__main__":
    # Start.
    main()
