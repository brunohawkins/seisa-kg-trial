"""SUMMARY: Turns every matching outcome into fact rows: one Match node per
name in the news (D-108), so a match is a judgement with its own evidence.

For the buyer "Hg" on deal ex:deal/hg-01-d1 it makes:
    ex:deal/hg-01-d1  buyerMatch     ex:match/hg-01-d1-buyer-1
    ex:match/...      type           ex:Match
    ex:match/...      nameAsWritten  "Hg"              (origin: the sentence it came from)
    ex:match/...      outcome        "refersToGroup"   (origin: rule D-103)
    ex:match/...      reason         "names the sponsor"
    ex:match/...      refersToGroup  ex:sponsor/hg
Other outcomes use sameEntityAs (one company), candidate (ambiguous; none
picked), possibleEntity (a group's possible members) or nonEntityKind.
The name as written comes from the source; everything else is labelled with
the rule that made it (D-029).
"""

# Groups the names by node and role, to number them.
from collections import defaultdict

# The shared fact format.
from seisa_kg.facts.model import fact, iri, literal
# Step 2: every name's outcome.
from seisa_kg.matching.outcomes import match_all

# Each rule used by matching, with a plain-English label.
# (D-109's NewsOnlyCompany nodes are made here too: one per tidied target name.)
RULES = {"D-096": "Names that point outside our graph (option A) stay unresolved, never forced",
         # The strict rule.
         "D-098": "Link a name to a company only when exactly one company fits; otherwise list the candidates and pick none",
         # The labels.
         "D-099": "A name with no other evidence takes the label Bruno approved: out of scope, or a non-entity of a stated kind",
         # Sponsor words and families.
         "D-103": "A name with a sponsor's name refers to that sponsor's group; a fund family is listed as possible, none picked",
         # Advisers.
         "D-104": "Advisers are outside firms: out of scope",
         # Bought companies.
         "D-109": "A deal target with no other match gets a NewsOnlyCompany node, one per name: known only from the news, not verified"}


# The rows for one name's Match node.
def match_rows(m: dict, match: str) -> list[dict]:
    # The rule's origin, shared by every judgement row.
    rule = {"kind": "rule", "rule": m["rule"]}
    # The name's own origin: the same as the name fact's (its sentence; what the text says).
    said = m["origin"]
    # The link from the news node, the type, the name as written, the outcome and the reason.
    rows = [fact(m["node"], f"{m['role']}Match", iri(match), rule), fact(match, "type", iri("ex:Match"), rule),
            # The name exactly as the release wrote it.
            fact(match, "nameAsWritten", literal(m["name"]), said),
            # The outcome and why.
            fact(match, "outcome", literal(m["outcome"]), rule), fact(match, "reason", literal(m["why"]), rule)]
    # One company: the same entity.
    if m["outcome"] == "sameEntityAs":
        # The link.
        rows.append(fact(match, "sameEntityAs", iri(m["to"][0]), rule))
    # A group: the sponsor, plus any possible members (none picked).
    elif m["outcome"] == "refersToGroup":
        # The group link.
        rows.append(fact(match, "refersToGroup", iri(m["to"][0]), rule))
        # Each possible member.
        rows += [fact(match, "possibleEntity", iri(c), rule) for c in m.get("possible", [])]
    # Ambiguous: every candidate, none picked.
    elif m["outcome"] == "ambiguous":
        # One row per candidate.
        rows += [fact(match, "candidate", iri(c), rule) for c in m["to"]]
    # A bought company known only from the news (D-109): the link, plus the node itself.
    elif m["outcome"] == "news-only":
        # The link from the Match.
        rows.append(fact(match, "namedCompany", iri(m["to"][0]), rule))
        # "This is a NewsOnlyCompany" (made by our rule).
        rows.append(fact(m["to"][0], "type", iri("ex:NewsOnlyCompany"), rule))
        # Its name as written, from the sentence (what the text says).
        rows.append(fact(m["to"][0], "name", literal(m["name"]), m["origin"]))
    # A non-entity: what sort it is (from the approved label).
    elif m["outcome"] == "non-entity":
        # The kind, e.g. "unnamed group of people".
        rows.append(fact(match, "nonEntityKind", literal(m["why"]), rule))
    # Hand back the rows.
    return rows


# Every Match node's rows, for the whole fact list.
def match_facts(rows: list[dict]) -> list[dict]:
    # The outcome of every name.
    results = match_all(rows)
    # How many names each (node, role) has had so far, to number them.
    seen = defaultdict(int)
    # The new rows.
    out = []
    # Each name.
    for m in results:
        # Its number within its node and role (a deal can have several buyers).
        seen[(m["node"], m["role"])] += 1
        # e.g. "ex:match/hg-01-d1-buyer-1" (the news node's own ID, then the role and number).
        match = f"ex:match/{m['node'].split('/', 1)[1]}-{m['role']}-{seen[(m['node'], m['role'])]}"
        # Its rows.
        out += match_rows(m, match)
    # The same row can come from two deals naming one company (its type); keep each fact and origin once.
    out = list({(r["subject"], r["predicate"], str(r["object"]), str(r["origin"])): r for r in out}.values())
    # One Rule node per rule used, so a reader can see what each says.
    for name in sorted({m["rule"] for m in results}):
        # "This is a rule", and its label.
        out += [fact(f"ex:rule/{name}", "type", iri("ex:Rule"), {"kind": "rule", "rule": name}),
                # Its plain-English label.
                fact(f"ex:rule/{name}", "label", literal(RULES[name]), {"kind": "rule", "rule": name})]
    # Hand back the rows.
    return out
