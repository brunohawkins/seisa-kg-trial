"""SUMMARY: Builds the property graph in Neo4j from data/interim/facts.jsonl
(pipeline stage 4b; schema in docs/schema/lpg-schema.md).

Built step by step with Bruno (D-067). So far:
- Step 1: connect, empty the database, and add one uniqueness rule per label,
  so a node's id can never appear twice (a rebuild can't make duplicates).
- Step 2: the nodes and their values (D-112, five rules):
  1. the type becomes a label (a GLEIF company is :Company:Gleif);
  2. dates and true/false become real types; text stays exactly as given;
  3. a fact kind that ever has several values on one node is a list on every node;
  4. other and previous names become :Name nodes (D-112a);
  5. a detail on a single value becomes a companion property (legalNameLanguage).
  Source records (and sentences) become :SourceRecord nodes. The scope decision
  isn't a node: it becomes a relationship in step 3 (D-112c).
  Check: each label's count equals the type count in the fact list.

Every node gets an `id` property: its name in the fact list (e.g.
"lei:213800KFNMVI8PDZX472"), so both graphs use the same names.

Run with: uv run python -m seisa_kg.lpg.build
"""

# Groups things into lists and counts them.
from collections import Counter, defaultdict
# Turns "2026-06-29" into a real date, and fetch times into real date-times.
from datetime import date, datetime
# Reads the Neo4j address, user and password from the environment.
import os

# Loads the secret settings from .env without printing them.
from dotenv import load_dotenv
# The official Neo4j driver for Python.
from neo4j import GraphDatabase

# The fact list and the project folder (where .env lives).
from seisa_kg.facts.model import PROJECT_ROOT, read_facts

# Every label that has its own nodes; each gets a uniqueness rule on `id` (schema section 2).
# Company covers both registers (:Company:Gleif and :Company:CompaniesHouse); SourceRecord covers sentences too.
KEY_LABELS = ["Company", "NewsOnlyCompany", "Sponsor", "Stake", "Appointment", "Person", "Name", "Release",
              # The news and matching nodes, and the provenance nodes.
              "Deal", "Adviser", "FundClose", "Mention", "Match", "SourceRecord", "Rule"]
# Types that don't become nodes: a scope decision becomes a relationship in step 3 (D-112c).
NOT_NODES = {"ex:ScopeDecision"}
# Fact kinds whose values become :Name nodes instead of properties (D-112a), and the link each gets in step 3.
NAME_PREDICATES = {"otherName": "HAS_OTHER_NAME", "previousName": "HAS_PREVIOUS_NAME"}
# Details that belong to the receipt (step 4), not to the node: the quote, the model, and why a value is "unknown".
RECEIPT_DETAILS = {"quote", "extractedBy", "why"}
# How many nodes to send to Neo4j in one go.
BATCH = 5000


# Open a connection to Neo4j using the settings in .env.
def connect():
    # Read .env into the environment (the values are never printed).
    load_dotenv(PROJECT_ROOT / ".env")
    # The driver: address, plus user and password.
    driver = GraphDatabase.driver(os.environ["NEO4J_URI"], auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]))
    # Fail now, with a clear error, if Neo4j isn't running or the password is wrong.
    driver.verify_connectivity()
    # Hand back the open connection.
    return driver


# Delete every node and relationship, in batches so a big graph doesn't run out of memory.
def empty(driver) -> None:
    # A session (batched deletes need one of their own), closed when done.
    with driver.session() as session:
        # Delete 10,000 nodes (with their relationships) per transaction until none are left.
        session.run("MATCH (n) CALL (n) { DETACH DELETE n } IN TRANSACTIONS OF 10000 ROWS").consume()


# Add one uniqueness rule per label: no two nodes with that label may share an id.
def add_constraints(driver) -> None:
    # Each label.
    for label in KEY_LABELS:
        # e.g. "CREATE CONSTRAINT company_id IF NOT EXISTS FOR (n:Company) REQUIRE n.id IS UNIQUE".
        driver.execute_query(f"CREATE CONSTRAINT {label.lower()}_id IF NOT EXISTS FOR (n:{label}) REQUIRE n.id IS UNIQUE")


# Rule 1: the labels for a node, from its type in the fact list.
def labels_for(subject: str, type_iri: str) -> tuple[str, ...]:
    # A registered company: :Company plus which register it's from.
    if type_iri == "ex:LegalEntity":
        # lei: nodes come from GLEIF, ch: nodes from Companies House.
        return ("Company", "Gleif") if subject.startswith("lei:") else ("Company", "CompaniesHouse")
    # Everything else: the type's own name, e.g. "ex:Deal" -> ("Deal",).
    return (type_iri.removeprefix("ex:"),)


# Rule 2: a fact's value as the right Neo4j type (text stays exactly as given).
def typed(obj: dict):
    # The value and its datatype, if any.
    value, datatype = obj["value"], obj.get("datatype")
    # A date, e.g. "2026-06-29" -> date(2026, 6, 29).
    if datatype == "date":
        # A real date, so Cypher can compare and sort it.
        return date.fromisoformat(value)
    # A date and time, e.g. a fetch time.
    if datatype == "dateTime":
        # A real date-time.
        return datetime.fromisoformat(value)
    # True or false.
    if datatype == "boolean":
        # A real boolean.
        return value == "true"
    # Text: unchanged.
    return value


# Rule 3: the fact kinds that ever have more than one distinct value on one node, so they're lists everywhere.
def list_predicates(values: list[dict]) -> set[str]:
    # Each (node, fact kind) and its distinct values.
    seen = defaultdict(set)
    # Each value fact.
    for r in values:
        # Remember the value.
        seen[(r["subject"], r["predicate"])].add(r["object"]["value"])
    # The fact kinds with two or more values somewhere.
    return {p for (_, p), vs in seen.items() if len(vs) > 1}


# Step 2a: every node as {"labels": (...), "props": {...}}, keyed by its id.
def build_nodes(rows: list[dict]) -> dict[str, dict]:
    # Each subject's type, from its "type" fact.
    types = {r["subject"]: r["object"]["iri"] for r in rows if r["predicate"] == "type"}
    # The nodes, keyed by id.
    nodes = {}
    # One node per typed subject (except the scope decisions; step 3 makes those relationships).
    for subject, t in types.items():
        # Skip the types that become relationships.
        if t not in NOT_NODES:
            # Its labels, and its id as the first property.
            nodes[subject] = {"labels": labels_for(subject, t), "props": {"id": subject}}
    # One :SourceRecord per record named in any origin, with where and when it was fetched.
    for r in rows:
        # Only source origins (rule origins point to :Rule nodes, which are typed facts already).
        o = r["origin"]
        # A record we haven't made yet.
        if o["kind"] == "source" and o["record"] not in nodes:
            # A sentence's record (src:news/<release>/sNN) is also a :Sentence.
            labels = ("SourceRecord", "Sentence") if o["record"].count("/") == 2 and o["record"].startswith("src:news/") else ("SourceRecord",)
            # Its source, address and fetch time.
            nodes[o["record"]] = {"labels": labels, "props": {"id": o["record"], "source": o["source"], "url": o["url"],
                                                               # The fetch (or hand-save) time, as a real date-time.
                                                               "retrievedAt": datetime.fromisoformat(o["retrieved_at"])}}
    # The value facts (not links), on nodes we made.
    values = [r for r in rows if "value" in r["object"] and r["subject"] in nodes]
    # Rule 3: which fact kinds are lists.
    lists = list_predicates(values)
    # Each value fact.
    for r in values:
        # The node's properties, the fact kind and the typed value.
        props, p, v = nodes[r["subject"]]["props"], r["predicate"], typed(r["object"])
        # Rule 4: names with their own details become :Name nodes.
        if p in NAME_PREDICATES:
            # The Name node's id: its company, the kind of name, and the name itself (one node per distinct name).
            name_id = f"{r['subject']}#{p}:{r['object']['value']}"
            # Its properties: the name, and each detail (type, language, dates) as a plain value.
            name_props = {"id": name_id, "value": v, "kind": p, **{k: typed(d) for k, d in r["details"].items()}}
            # Kept once (the same name from two fetch dates is one node).
            nodes.setdefault(name_id, {"labels": ("Name",), "props": name_props})
            # On to the next fact.
            continue
        # Rule 3: a list fact kind: add the value if it isn't there yet (the same value from two dates counts once).
        if p in lists:
            # Add to the list.
            if v not in props.setdefault(p, []):
                # Keep it.
                props[p].append(v)
        # A single value: set it.
        else:
            # The property.
            props[p] = v
        # Rule 5: a detail on a single value becomes a companion property, e.g. legalName + legalNameLanguage.
        for k, d in r["details"].items():
            # Quotes, the model and "why" go on the receipt in step 4.
            if k not in RECEIPT_DETAILS:
                # e.g. "legalName" + "language" -> "legalNameLanguage".
                props[p + k[0].upper() + k[1:]] = typed(d)
    # Hand back every node.
    return nodes


# Step 2b: write the nodes to Neo4j, in batches, one batch per set of labels.
def write_nodes(driver, nodes: dict[str, dict]) -> None:
    # The nodes grouped by their labels, because Cypher needs the labels written into the query.
    groups = defaultdict(list)
    # Each node.
    for n in nodes.values():
        # Grouped by its label set, e.g. ("Company", "Gleif").
        groups[n["labels"]].append(n["props"])
    # Each group.
    for labels, props in groups.items():
        # e.g. ":Company:Gleif" (our own fixed names, never outside input).
        tag = "".join(f":{l}" for l in labels)
        # In batches.
        for i in range(0, len(props), BATCH):
            # Create one node per row and copy all its properties onto it.
            driver.execute_query(f"UNWIND $rows AS row CREATE (n{tag}) SET n = row", rows=props[i:i + BATCH])


# Step 2c: check each label's count against the fact list. Returns True if every count matches.
def check_nodes(driver, rows: list[dict], nodes: dict[str, dict]) -> bool:
    # What the fact list says: each type's count of DISTINCT nodes, as the label it becomes. Not the count of
    # type facts: one node can be typed by several records (GLEIF on two dates; an officer listed by 24 companies).
    typed_nodes = {(r["subject"], r["object"]["iri"]) for r in rows if r["predicate"] == "type" and r["object"]["iri"] not in NOT_NODES}
    # Count every label each node gets (a GLEIF company counts for Company and Gleif).
    expected = Counter(label for subject, t in typed_nodes for label in labels_for(subject, t))
    # Plus the nodes made from origins and names, counted from what we built.
    for n in nodes.values():
        # Source records, sentences and names.
        if n["labels"][0] in ("SourceRecord", "Name"):
            # Count each of its labels.
            expected.update(n["labels"])
    # What Neo4j actually holds, per label.
    found = {r["label"]: r["n"] for r in driver.execute_query(
        # Each label and how many nodes carry it.
        "MATCH (n) UNWIND labels(n) AS label RETURN label, count(*) AS n").records}
    # Print the table.
    print(f"  {'label':<18}{'fact list':>10}{'Neo4j':>8}")
    # Each label, in a fixed order.
    for label in sorted(expected):
        # A tick or a cross.
        mark = "ok" if expected[label] == found.get(label, 0) else "MISMATCH"
        # e.g. "  Deal                    30      30  ok".
        print(f"  {label:<18}{expected[label]:>10}{found.get(label, 0):>8}  {mark}")
    # True only if every label matches and Neo4j has no extra labels.
    return dict(expected) == found


# Steps 1 and 2: empty, rules, nodes, check.
def main() -> None:
    # The fact list.
    rows = read_facts()
    # Open the connection.
    with connect() as driver:
        # Step 1: start from nothing, then the uniqueness rules.
        empty(driver)
        # The rules.
        add_constraints(driver)
        # Step 2: build the nodes in memory.
        nodes = build_nodes(rows)
        # Write them.
        write_nodes(driver, nodes)
        # Say how many.
        print(f"Step 2: wrote {len(nodes)} nodes. Check, per label:")
        # Compare with the fact list.
        ok = check_nodes(driver, rows, nodes)
        # The verdict.
        print("All node counts match the fact list." if ok else "Node counts DIFFER from the fact list.")


# Run main() when the file is run directly.
if __name__ == "__main__":
    # Go.
    main()
