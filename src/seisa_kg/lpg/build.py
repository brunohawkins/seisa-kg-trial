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
- Step 3: the relationships (D-113, D-114). Each link fact becomes one
  relationship named in Neo4j's style (fundManagedBy -> FUND_MANAGED_BY, with
  four renames), carrying its source (`record` or `rule`) and its details.
  Scope decisions become IN_SCOPE_OF {verdict, reason, rule}; names get
  HAS_OTHER_NAME / HAS_PREVIOUS_NAME. A link to a company we never fetched
  ends at a :NotFetched stub that holds only its id (D-113).
  Check: each relationship type's count equals the link facts that map to it.
- Step 4: the receipts (D-110). Each node gets one DERIVED_FROM per source
  record (or GENERATED_BY per rule) behind its values and labels, listing
  exactly which ones: aligned lists `properties`, `values`, and for news
  `quotes` plus `extractedBy`; for "unknown" values, `whys` (D-090). A record's
  own text and a rule's own label need no receipt (they are the source).
  Check: every value and label fact is listed in exactly one receipt.
- Step 5: the two graphs compared directly (each type's distinct nodes and each
  kind of link, in the RDF file vs Neo4j), and any failed check stops the build
  with an error, so `make build` can't finish with graphs that disagree.

Every node gets an `id` property: its name in the fact list (e.g.
"lei:213800KFNMVI8PDZX472"), so both graphs use the same names.

Run with: uv run python -m seisa_kg.lpg.build
"""

# Turns camelCase fact names into UPPER_SNAKE relationship names.
import re
# Writes a fact's details as text, to tell two facts apart.
import json
# Groups things into lists and counts them.
from collections import Counter, defaultdict
# Turns "2026-06-29" into a real date, and fetch times into real date-times.
from datetime import date, datetime
# Reads the Neo4j address, user and password from the environment.
import os

# Loads the secret settings from .env without printing them.
from dotenv import load_dotenv
# Reads the RDF graph file, for step 5's direct comparison.
import pyoxigraph as ox
# The official Neo4j driver for Python.
from neo4j import GraphDatabase

# The fact list and the project folder (where .env lives).
from seisa_kg.facts.model import PROJECT_ROOT, read_facts

# Every label that has its own nodes; each gets a uniqueness rule on `id` (schema section 2).
# Company covers both registers (:Company:Gleif and :Company:CompaniesHouse); SourceRecord covers sentences too.
KEY_LABELS = ["Company", "NewsOnlyCompany", "Sponsor", "Stake", "Appointment", "Person", "Name", "Release",
              # The news and matching nodes, and the provenance nodes.
              "Deal", "Adviser", "FundClose", "Mention", "Match", "SourceRecord", "Rule", "NotFetched"]
# Types that don't become nodes: a scope decision becomes a relationship in step 3 (D-112c).
NOT_NODES = {"ex:ScopeDecision"}
# Fact kinds whose values become :Name nodes instead of properties (D-112a), and the link each gets in step 3.
NAME_PREDICATES = {"otherName": "HAS_OTHER_NAME", "previousName": "HAS_PREVIOUS_NAME"}
# Details that belong to the receipt (step 4), not to the node: the quote, the model, and why a value is "unknown".
RECEIPT_DETAILS = {"quote", "extractedBy", "why"}
# Fact names that read badly as relationship verbs, and their names in the property graph (D-114).
RENAMES = {"company": "OF_COMPANY", "holder": "HELD_BY", "officer": "HELD_BY", "adviser": "HAS_ADVISER"}
# The RDF graph file the RDF builder saves (step 5 compares it with Neo4j).
RDF_PATH = PROJECT_ROOT / "data" / "output" / "graph.ttl"
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


# A :Name node's id, e.g. "ch:01899316#previousName:COUNTY NATWEST … |1997-09-26|1989-12-12" (details in key order).
def name_node_id(r: dict) -> str:
    # The details' values, in a fixed order, so the same name in two periods gets two ids.
    details = "|".join(str(r["details"][k]["value"]) for k in sorted(r["details"]))
    # Owner, kind, name, details.
    return f"{r['subject']}#{r['predicate']}:{r['object']['value']}|{details}"


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
            # The Name node's id: its company, the kind of name, the name, and its details (the same name can recur in two periods).
            name_id = name_node_id(r)
            # Its properties: the name, and each detail (type, language, dates) as a plain value.
            name_props = {"id": name_id, "value": v, "kind": p, **{k: typed(d) for k, d in r["details"].items()}}
            # Kept once (the same name from two fetch dates is one node).
            nodes.setdefault(name_id, {"labels": ("Name",), "props": name_props})
            # On to the next fact.
            continue
        # A list fact kind can't have per-value details as companion properties (they'd overwrite each other): stop loudly.
        if p in lists and any(k not in RECEIPT_DETAILS for k in r["details"]):
            # Needs a decision (e.g. :Name-style nodes, D-112a), not a silent guess.
            raise ValueError(f"{p} has several values with their own details; decide how to model it (see D-112a)")
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


# Every distinct name fact as (owner, kind, name, details), worked out from the fact list (used by the checks).
def distinct_names(rows: list[dict]) -> set[tuple]:
    # The details as sorted text, so two periods of one name differ.
    return {(r["subject"], r["predicate"], r["object"]["value"], json.dumps(r["details"], sort_keys=True)) for r in rows if r["predicate"] in NAME_PREDICATES}


# Step 2c: check each label's count against the fact list. Returns True if every count matches.
def check_nodes(driver, rows: list[dict], nodes: dict[str, dict]) -> bool:
    # What the fact list says: each type's count of DISTINCT nodes, as the label it becomes. Not the count of
    # type facts: one node can be typed by several records (GLEIF on two dates; an officer listed by 24 companies).
    typed_nodes = {(r["subject"], r["object"]["iri"]) for r in rows if r["predicate"] == "type" and r["object"]["iri"] not in NOT_NODES}
    # Count every label each node gets (a GLEIF company counts for Company and Gleif).
    expected = Counter(label for subject, t in typed_nodes for label in labels_for(subject, t))
    # Plus the nodes made from origins and names, worked out from the fact list itself, never from the builder's
    # own output (a check that trusts the builder can't catch the builder's bugs).
    records = {r["origin"]["record"] for r in rows if r["origin"]["kind"] == "source"}
    # Every record is a :SourceRecord.
    expected["SourceRecord"] = len(records)
    # Sentence records look like src:news/<release>/sNN.
    expected["Sentence"] = sum(1 for rec in records if rec.startswith("src:news/") and rec.count("/") == 2)
    # One :Name per distinct (owner, kind of name, name, details): the same name in two periods is two names.
    expected["Name"] = len(distinct_names(rows))
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


# A fact name as a relationship type (D-114): a rename, or the name in capitals, e.g. fundManagedBy -> FUND_MANAGED_BY.
def rel_type(predicate: str) -> str:
    # A rename if there is one; otherwise put "_" before each capital letter and capitalise everything.
    return RENAMES.get(predicate) or re.sub(r"(?<!^)(?=[A-Z])", "_", predicate).upper()


# A detail's value for a relationship property: a link detail becomes its id as text; a value is typed (rule 2).
def detail_value(d: dict):
    # A link inside a detail (rare) is kept as its id.
    return d["iri"] if "iri" in d else typed(d)


# A fact's origin as relationship properties (D-110): the record it came from, or the rule that made it.
def origin_props(origin: dict) -> dict:
    # e.g. {"record": "src:gleif/2138…/fund-manager/20261018"} or {"rule": "D-025"}.
    return {"record": origin["record"]} if origin["kind"] == "source" else {"rule": origin["rule"]}


# Step 3a: every relationship as {"type", "from", "to", "props"}, plus the :NotFetched stubs it needs (D-113).
def build_relationships(rows: list[dict], nodes: dict[str, dict]) -> tuple[list[dict], dict[str, dict]]:
    # The relationships.
    rels = []
    # The links seen so far, to catch one link stated twice.
    seen = set()
    # Each link fact (an object that is a link, not a value), except types and the scope decisions' own parts.
    for r in rows:
        # Skip values, types and scope-decision parts (handled below).
        if "iri" not in r["object"] or r["predicate"] == "type" or r["subject"].startswith("ex:scope/"):
            # Next fact.
            continue
        # The link's identity: from, kind, to.
        link = (r["subject"], r["predicate"], r["object"]["iri"])
        # The same link from two records (e.g. two fetch dates) would make two relationships where RDF has one triple: stop loudly.
        if link in seen:
            # Needs a decision when it first happens (likely with make refresh, D-094): one relationship with a list of records.
            raise ValueError(f"link stated twice: {link}; decide how to merge (see D-094, D-110)")
        # Remember it.
        seen.add(link)
        # Its details, typed, plus where it came from.
        props = {**{k: detail_value(d) for k, d in r["details"].items()}, **origin_props(r["origin"])}
        # One relationship, in the same direction as in RDF.
        rels.append({"type": rel_type(r["predicate"]), "from": r["subject"], "to": r["object"]["iri"], "props": props})
    # The scope decisions: gather each one's parts (entity, sponsor, verdict, reason) from its facts.
    scope = defaultdict(dict)
    # Each fact about a scope decision.
    for r in rows:
        # Only scope-decision facts.
        if r["subject"].startswith("ex:scope/") and r["predicate"] != "type":
            # The part's value: a link's id, or a text value.
            scope[r["subject"]][r["predicate"]] = r["object"].get("iri") or r["object"].get("value")
    # One IN_SCOPE_OF per decision: company -> sponsor, with the verdict, the reason and the rule (D-112c).
    for parts in scope.values():
        # e.g. verdict "ex:In" -> "In", rule "ex:rule/D-028" -> "D-028".
        props = {"verdict": parts["verdict"].removeprefix("ex:"), "reason": parts.get("reason", ""), "rule": parts["wasGeneratedBy"].removeprefix("ex:rule/")}
        # The relationship.
        rels.append({"type": "IN_SCOPE_OF", "from": parts["entity"], "to": parts["sponsor"], "props": props})
    # Each :Name node is linked from its owner (its id is "<owner>#<kind>:<name>").
    for n in nodes.values():
        # Only Name nodes.
        if n["labels"] == ("Name",):
            # e.g. HAS_PREVIOUS_NAME from ch:01525583.
            rels.append({"type": NAME_PREDICATES[n["props"]["kind"]], "from": n["props"]["id"].split("#", 1)[0], "to": n["props"]["id"], "props": {}})
    # D-113: any end that isn't a node gets a :NotFetched stub with only its id.
    stubs = {}
    # Each relationship's two ends.
    for rel in rels:
        # Both ends.
        for end in (rel["from"], rel["to"]):
            # Not a node yet.
            if end not in nodes and end not in stubs:
                # The stub.
                stubs[end] = {"labels": ("NotFetched",), "props": {"id": end}}
    # Hand back both.
    return rels, stubs


# Step 3b: write the relationships, in batches, grouped by type and by the key labels of their two ends.
def write_relationships(driver, rels: list[dict], nodes: dict[str, dict]) -> None:
    # Groups: (type, from label, to label) -> rows.
    groups = defaultdict(list)
    # Each relationship.
    for rel in rels:
        # The first label of each end is the one with the uniqueness rule, so Neo4j finds it by index, not by scanning.
        key = (rel["type"], nodes[rel["from"]]["labels"][0], nodes[rel["to"]]["labels"][0])
        # Grouped.
        groups[key].append({"from": rel["from"], "to": rel["to"], "props": rel["props"]})
    # Each group.
    for (t, a, b), rows in groups.items():
        # In batches.
        for i in range(0, len(rows), BATCH):
            # Find both ends by id, join them, and copy the properties onto the relationship.
            driver.execute_query(f"UNWIND $rows AS row MATCH (a:{a} {{id: row.from}}) MATCH (b:{b} {{id: row.to}}) "
                                 # The new relationship.
                                 f"CREATE (a)-[r:{t}]->(b) SET r = row.props", rows=rows[i:i + BATCH])


# Step 3c: check each relationship type's count against the fact list. Returns True if every count matches.
def check_relationships(driver, rows: list[dict]) -> bool:
    # What the fact list says, worked out independently of build_relationships: the link facts by type.
    expected = Counter(rel_type(r["predicate"]) for r in rows
                       # Links only, not types, not scope-decision parts.
                       if "iri" in r["object"] and r["predicate"] != "type" and not r["subject"].startswith("ex:scope/"))
    # One IN_SCOPE_OF per scope decision.
    expected["IN_SCOPE_OF"] = len({r["subject"] for r in rows if r["subject"].startswith("ex:scope/")})
    # One name link per distinct name (owner, kind, name, details).
    names = distinct_names(rows)
    # Counted by kind.
    for _, p, _, _ in names:
        # e.g. HAS_PREVIOUS_NAME.
        expected[NAME_PREDICATES[p]] += 1
    # What Neo4j holds, per relationship type.
    found = {r["t"]: r["n"] for r in driver.execute_query("MATCH ()-[r]->() RETURN type(r) AS t, count(*) AS n").records}
    # Print the table.
    print(f"  {'relationship':<28}{'fact list':>10}{'Neo4j':>8}")
    # Each type, in a fixed order.
    for t in sorted(expected):
        # A tick or a cross.
        mark = "ok" if expected[t] == found.get(t, 0) else "MISMATCH"
        # e.g. "  FUND_MANAGED_BY                    71      71  ok".
        print(f"  {t:<28}{expected[t]:>10}{found.get(t, 0):>8}  {mark}")
    # True only if every type matches and Neo4j has no extra types.
    return dict(expected) == found


# The facts a receipt covers: values and types on nodes, each distinct fact once (some sources repeat a row exactly).
def receipt_facts(rows: list[dict], node_ids: set[str]) -> list[dict]:
    # Distinct facts seen so far.
    seen = set()
    # The facts kept.
    out = []
    # Each fact.
    for r in rows:
        # Values and types only (a link's source is on the link itself, step 3), on subjects that are nodes.
        if not ("value" in r["object"] or r["predicate"] == "type") or r["subject"] not in node_ids:
            # Next fact.
            continue
        # The fact's source: a record, or a rule's node.
        target = r["origin"]["record"] if r["origin"]["kind"] == "source" else "ex:rule/" + r["origin"]["rule"]
        # A record's own text, or a rule's own label and type: it *is* the source, so it needs no receipt.
        if target == r["subject"]:
            # Next fact.
            continue
        # The fact's identity: everything about it.
        key = json.dumps([r["subject"], r["predicate"], r["object"], r["origin"], r["details"]], sort_keys=True)
        # Kept once.
        if key not in seen:
            # Remember it.
            seen.add(key)
            # Keep it, with its target.
            out.append({**r, "target": target})
    # Hand back the facts.
    return out


# Step 4a: the receipts: one per (node, record or rule), listing the facts it backs in aligned lists (D-110).
def build_receipts(facts: list[dict], nodes: dict[str, dict]) -> list[dict]:
    # (from node, kind, target) -> the receipt's lists.
    receipts = {}
    # Each fact.
    for r in facts:
        # A name's receipt starts at its :Name node; every other fact's at its own node.
        start = name_node_id(r) if r["predicate"] in NAME_PREDICATES else r["subject"]
        # A source gives DERIVED_FROM; a rule gives GENERATED_BY.
        kind = "DERIVED_FROM" if r["origin"]["kind"] == "source" else "GENERATED_BY"
        # The receipt for this node and source, made on first use.
        rec = receipts.setdefault((start, kind, r["target"]), {"properties": [], "values": [], "quotes": [], "whys": [], "models": set()})
        # The property it backs: "_label" for a type, "value" on a :Name, otherwise the fact's own name.
        rec["properties"].append("_label" if r["predicate"] == "type" else "value" if r["predicate"] in NAME_PREDICATES else r["predicate"])
        # The value it backs, as text (a type's label name, e.g. "Deal").
        rec["values"].append(labels_for(r["subject"], r["object"]["iri"])[-1] if r["predicate"] == "type" else str(r["object"]["value"]))
        # The exact quote, for news values ("" when there's none, so the lists stay aligned).
        rec["quotes"].append(r["details"].get("quote", {}).get("value", ""))
        # Why a value is "unknown" (D-090), or "".
        rec["whys"].append(r["details"].get("why", {}).get("value", ""))
        # The model that extracted it, if any.
        if "extractedBy" in r["details"]:
            # Remember it.
            rec["models"].add(r["details"]["extractedBy"]["value"])
    # The relationships, keeping only the lists that say something.
    out = []
    # Each receipt.
    for (start, kind, target), rec in receipts.items():
        # Always: which properties, which values.
        props = {"properties": rec["properties"], "values": rec["values"]}
        # Quotes, only if any.
        if any(rec["quotes"]):
            # Aligned with properties.
            props["quotes"] = rec["quotes"]
        # Reasons for "unknown", only if any.
        if any(rec["whys"]):
            # Aligned with properties.
            props["whys"] = rec["whys"]
        # The model, if any (one per receipt; more would need a decision).
        if rec["models"]:
            # Exactly one model.
            if len(rec["models"]) > 1:
                # Stop loudly.
                raise ValueError(f"two models behind one receipt: {start} -> {target}")
            # e.g. "gemini-2.5-pro".
            props["extractedBy"] = rec["models"].pop()
        # The relationship.
        out.append({"type": kind, "from": start, "to": target, "props": props})
    # Hand back the receipts.
    return out


# Step 4c: every value and label fact must appear in exactly one receipt. Returns True if the counts match.
def check_receipts(driver, rows: list[dict]) -> bool:
    # The node ids, worked out from the fact list: typed subjects (not scope decisions) and records.
    node_ids = {r["subject"] for r in rows if r["predicate"] == "type" and r["object"]["iri"] not in NOT_NODES}
    # Plus every record.
    node_ids |= {r["origin"]["record"] for r in rows if r["origin"]["kind"] == "source"}
    # The facts that need a receipt, split by kind of source.
    facts = receipt_facts(rows, node_ids)
    # Expected entries: source-backed facts and rule-made facts.
    expected = {"DERIVED_FROM": sum(r["origin"]["kind"] == "source" for r in facts), "GENERATED_BY": sum(r["origin"]["kind"] == "rule" for r in facts)}
    # What Neo4j holds: the number of entries listed across all receipts of each kind.
    found = {r["t"]: r["n"] for r in driver.execute_query(
        # Each receipt kind and the total length of its properties lists.
        "MATCH ()-[r:DERIVED_FROM|GENERATED_BY]->() RETURN type(r) AS t, sum(size(r.properties)) AS n").records}
    # Each kind.
    for t in sorted(expected):
        # e.g. "  DERIVED_FROM   facts 21,000   listed in receipts 21,000  ok".
        print(f"  {t:<14} facts needing one {expected[t]:>7,}   listed in receipts {found.get(t, 0):>7,}  {'ok' if expected[t] == found.get(t, 0) else 'MISMATCH'}")
    # True only if both match.
    return all(expected[t] == found.get(t, 0) for t in expected)


# Step 5: compare the RDF graph file with Neo4j directly: each type's distinct nodes, and each kind of link.
# Returns True if every count matches. (Steps 2–4 compare Neo4j with the fact list; this compares the two graphs.)
def check_against_rdf(driver, rows: list[dict]) -> bool:
    # Read the RDF graph saved by the RDF builder.
    store = ox.Store()
    # Load it from the file.
    store.bulk_load(path=str(RDF_PATH), format=ox.RdfFormat.TURTLE)
    # Our vocabulary's address, and where scope decisions live (they're relationships in Neo4j, not nodes).
    ex, scope = "https://seisa-kg.example/def/", "https://seisa-kg.example/def/scope/"
    # Pairs to compare: (what, RDF count, Neo4j count).
    pairs = []
    # Node types: distinct subjects per RDF type vs nodes per label (LegalEntity is :Company in Neo4j).
    for rec in store.query(f"SELECT ?t (COUNT(DISTINCT ?s) AS ?n) WHERE {{ ?s a ?t }} GROUP BY ?t"):
        # The type's short name, e.g. "Deal".
        t = rec["t"].value.removeprefix(ex)
        # Scope decisions aren't nodes in Neo4j (D-112c); they're checked as IN_SCOPE_OF below.
        if t == "ScopeDecision":
            # Skip.
            continue
        # The label it becomes.
        label = "Company" if t == "LegalEntity" else t
        # Neo4j's count for that label.
        n = driver.execute_query(f"MATCH (n:{label}) RETURN count(n) AS n").records[0]["n"]
        # Remember the pair.
        pairs.append((f":{label}", int(rec["n"].value), n))
    # Link kinds: every link predicate in the fact list, counted as distinct RDF triples, grouped by relationship type.
    rdf_links = Counter()
    # Each distinct link predicate (not types, not scope parts).
    for p in sorted({r["predicate"] for r in rows if "iri" in r["object"] and r["predicate"] != "type" and not r["subject"].startswith("ex:scope/")}):
        # RDF triples with that predicate pointing at a node, outside scope decisions.
        q = f"SELECT (COUNT(*) AS ?n) WHERE {{ ?s <{ex}{p}> ?o FILTER(isIRI(?o)) FILTER(!STRSTARTS(STR(?s), '{scope}')) }}"
        # Added to its relationship type (holder and officer both become HELD_BY).
        rdf_links[rel_type(p)] += int(next(iter(store.query(q)))["n"].value)
    # Scope decisions: one per scope node in RDF, one IN_SCOPE_OF in Neo4j.
    rdf_links["IN_SCOPE_OF"] = int(next(iter(store.query(f"SELECT (COUNT(DISTINCT ?s) AS ?n) WHERE {{ ?s a <{ex}ScopeDecision> }}")))["n"].value)
    # Each relationship type's Neo4j count.
    for t, n in sorted(rdf_links.items()):
        # Neo4j's count.
        found = driver.execute_query(f"MATCH ()-[r:{t}]->() RETURN count(r) AS n").records[0]["n"]
        # Remember the pair.
        pairs.append((t, n, found))
    # Print the table.
    print(f"  {'node label / relationship':<28}{'RDF':>8}{'Neo4j':>8}")
    # Each pair.
    for what, a, b in pairs:
        # e.g. "  :Deal                            30      30  ok".
        print(f"  {what:<28}{a:>8}{b:>8}  {'ok' if a == b else 'MISMATCH'}")
    # True only if every pair matches.
    return all(a == b for _, a, b in pairs)


# Steps 1 to 5: empty, rules, nodes, relationships, receipts, all checks; fail the build if any check fails.
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
        # Every check's result, so the build can fail at the end if any failed (step 5).
        results = {"nodes": ok}
        # The verdict.
        print("All node counts match the fact list." if ok else "Node counts DIFFER from the fact list.")
        # Step 3: the relationships, and the stubs they need.
        rels, stubs = build_relationships(rows, nodes)
        # The stubs first, so every relationship has both ends.
        write_nodes(driver, stubs)
        # Every node, stubs included, so each end's label is known.
        nodes.update(stubs)
        # The relationships.
        write_relationships(driver, rels, nodes)
        # Say how many.
        print(f"Step 3: wrote {len(rels)} relationships and {len(stubs)} :NotFetched stubs (D-113). Check, per type:")
        # Compare with the fact list.
        ok = check_relationships(driver, rows)
        # Remember it.
        results["relationships"] = ok
        # The verdict.
        print("All relationship counts match the fact list." if ok else "Relationship counts DIFFER from the fact list.")
        # Step 4: the receipts, from the facts on the nodes we built.
        receipts = build_receipts(receipt_facts(rows, set(nodes)), nodes)
        # Written like any relationship.
        write_relationships(driver, receipts, nodes)
        # Say how many.
        print(f"Step 4: wrote {len(receipts)} receipts (D-110). Check, every value and label listed exactly once:")
        # Compare with the fact list.
        ok = check_receipts(driver, rows)
        # Remember it.
        results["receipts"] = ok
        # The verdict.
        print("Every value and label has its receipt." if ok else "Receipts DIFFER from the fact list.")
        # Step 5: compare the two graphs directly, node types and links (RDF file vs Neo4j).
        print("Step 5: the RDF graph and the property graph, compared directly:")
        # The result.
        results["rdf vs neo4j"] = check_against_rdf(driver, rows)
    # Step 5: any failed check fails the whole build, so `make build` can't finish with graphs that disagree.
    failed = [name for name, passed in results.items() if not passed]
    # Something failed.
    if failed:
        # Say which, and stop with an error code (make then stops too).
        raise SystemExit(f"Property graph checks FAILED: {', '.join(failed)}")
    # All good.
    print("All property graph checks passed: nodes, relationships, receipts, and RDF vs Neo4j.")


# Run main() when the file is run directly.
if __name__ == "__main__":
    # Go.
    main()
