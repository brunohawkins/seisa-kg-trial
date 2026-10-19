"""SUMMARY: Tidy comparison keys, so Q5 ("where do sources disagree?") compares
like with like (D-092, D-093; findings F45, F46).

The values as given always stay in the graph. These rules add a separate,
labelled key next to them, used only for comparing:
- statusGroup (rule D-092): GLEIF's ACTIVE / INACTIVE and Companies House's
  words mapped to one scale. "active", and the insolvency states in which the
  company still legally exists (liquidation, administration...), count as
  ACTIVE; "dissolved", "removed", "closed" and "converted-closed" count as
  INACTIVE. An unknown word gets no key, so it is never silently matched.
- addressKey (rule D-093): the postcode plus the building number (the first
  all-digit word before the postcode, wherever it sits; else the first word),
  after tidying capitals and punctuation. "5 MARBLE ARCH, LONDON, GB-LND, W1H 7EJ, GB" and
  "5 Marble Arch, London, W1H 7EJ, United Kingdom" both become "W1H7EJ|5".
"""

# Pattern matching, used to find postcodes and numbers.
import re

# The shared fact format.
from seisa_kg.facts.model import fact, iri, literal

# Our two rules, with a plain-English label each.
RULES = {"D-092": "Map GLEIF and Companies House status words to one ACTIVE / INACTIVE scale, for comparing only",
         # The address rule.
         "D-093": "Compare addresses by postcode plus building number, after tidying, for comparing only"}
# Status words (in lower case) and the group each one belongs to.
STATUS_GROUPS = {"active": "ACTIVE", "liquidation": "ACTIVE", "administration": "ACTIVE", "receivership": "ACTIVE",
                 # More "still exists" states.
                 "insolvency-proceedings": "ACTIVE", "voluntary-arrangement": "ACTIVE", "open": "ACTIVE", "registered": "ACTIVE",
                 # The "no longer exists" states.
                 "inactive": "INACTIVE", "dissolved": "INACTIVE", "removed": "INACTIVE", "closed": "INACTIVE", "converted-closed": "INACTIVE"}
# A UK-style postcode (also used by Guernsey and Jersey), e.g. "W1H 7EJ" or "GY1 2HL".
POSTCODE = re.compile(r"\b([A-Z]{1,2}\d[A-Z\d]?)\s*(\d[A-Z]{2})\b")


# The comparison key for an address, or None if it has no recognisable postcode.
def address_key(address: str) -> str | None:
    # Capitals, with punctuation turned into spaces.
    text = re.sub(r"[^\w\s]", " ", address.upper())
    # The postcode, written without its space.
    m = POSTCODE.search(text)
    # No postcode: no key (so it is never silently matched).
    if not m:
        # Nothing.
        return None
    # The postcode without the space, e.g. "W1H7EJ".
    postcode = m.group(1) + m.group(2)
    # The words before the postcode (care-of names and floors included).
    words = text[:m.start()].split()
    # The building: the first word that is only digits (e.g. "1", "5"), wherever it sits; else the first word.
    building = next((w for w in words if w.isdigit()), words[0] if words else "")
    # The key, e.g. "W1H7EJ|5".
    return f"{postcode}|{building}"


# The comparison-key rows for every legalAddress and entityStatus in the fact list.
def compare_facts(rows: list[dict]) -> list[dict]:
    # The new rows.
    out = []
    # Each row.
    for r in rows:
        # A status: add its group, if the word is one we know.
        if r["predicate"] == "entityStatus" and r["object"]["value"].lower() in STATUS_GROUPS:
            # Labelled as made by rule D-092; the original word stays in its own fact.
            out.append(fact(r["subject"], "statusGroup", literal(STATUS_GROUPS[r["object"]["value"].lower()]), {"kind": "rule", "rule": "D-092"}))
        # An address: add its key, if it has a postcode.
        elif r["predicate"] == "legalAddress" and address_key(r["object"]["value"]):
            # Labelled as made by rule D-093.
            out.append(fact(r["subject"], "addressKey", literal(address_key(r["object"]["value"])), {"kind": "rule", "rule": "D-093"}))
    # One Rule node per rule, so a reader can see what each says.
    for name, label in RULES.items():
        # "This is a rule", and its label.
        out += [fact(f"ex:rule/{name}", "type", iri("ex:Rule"), {"kind": "rule", "rule": name}),
                # Its plain-English label.
                fact(f"ex:rule/{name}", "label", literal(label), {"kind": "rule", "rule": name})]
    # Duplicate keys (the same entity fetched on two dates) are kept once.
    seen, unique = set(), []
    # Each new row.
    for r in out:
        # Its identity: subject, predicate and value.
        k = (r["subject"], r["predicate"], r["object"].get("value") or r["object"].get("iri"))
        # Keep the first one only.
        if k not in seen:
            # Remember it.
            seen.add(k)
            # Keep it.
            unique.append(r)
    # Hand back the rows.
    return unique
