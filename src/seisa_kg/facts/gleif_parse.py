"""SUMMARY: Pipeline stage 2 (parse) for GLEIF. Turns the cached GLEIF replies
in data/raw/gleif/ into rows of the shared fact list (D-033).

It reads the cache only and never downloads, so parsing is fast and always
gives the same result for the same cache.

What it produces, all stated exactly as GLEIF gives them (D-029):
- Level 1 facts for each entity: legal name, other names, category, legal
  form, jurisdiction, status, legal and headquarters addresses (one line each,
  D-037, D-050), registration
  authority and registration number, and the LEI's registration status (D-046). These come from our search replies, or
  from a single LEI record for parents and managers our search didn't find.
- Level 2 facts: the direct and ultimate parent, or GLEIF's stated reason for
  reporting none (D-026); and the fund-manager link as GLEIF states it, with
  its start date, status and corroboration level (D-027).

Every row's origin names its source record: one per LEI, per reply, per
fetch date (D-035, D-042), e.g. src:gleif/<LEI>/search-apax_p1/20261018.
An entity found in several replies gets its Level 1 facts from every one of
them (D-042): each reply is a separate dated observation, and Level 1 data
can change between fetches (F7). This includes the 16 Oct sponsor-check
searches, saved in an older format without the web address; for those, the
address is taken from GLEIF's own list of page links in the reply.
"""

# Reads the cached JSON replies.
import json
# Python's built-in reader for TOML settings files.
import tomllib
# A tidy way of working with file and folder paths.
from pathlib import Path

# The shared fact format: helpers to build rows.
from seisa_kg.facts.model import fact, iri, literal

# The project's top folder: this file's folder, then up three levels (facts → seisa_kg → src → project).
PROJECT_ROOT = Path(__file__).resolve().parents[3]
# Where the GLEIF cache lives.
CACHE_DIR = PROJECT_ROOT / "data" / "raw" / "gleif"
# The folders holding search replies: the 16 Oct sponsor check and the 18 Oct searches (D-042).
SEARCH_DIRS = ("sponsor_check", "search")
# The sponsor settings file, which lists the search words whose replies we parse.
CONFIG_PATH = PROJECT_ROOT / "config" / "sponsors.toml"
# The Level 2 reply files we turn into facts, and the predicate each one produces.
LEVEL2_PARTS = {
    # An actual direct parent.
    "direct-parent-relationship": "directParent",
    # An actual ultimate parent.
    "ultimate-parent-relationship": "ultimateParent",
    # The stated reason for reporting no direct parent (D-026).
    "direct-parent-reporting-exception": "directParentException",
    # The stated reason for reporting no ultimate parent (D-026).
    "ultimate-parent-reporting-exception": "ultimateParentException",
    # The fund-manager link, as GLEIF states it (D-027).
    "fund-manager-relationship": "fundManagedBy",
}


# Build the origin for a fact: which source record it came from, with the reply's address and fetch time.
def origin(lei: str, kind: str, envelope: dict) -> dict:
    # The fetch date as digits, e.g. "2026-10-18T13:03:16+00:00" -> "20261018".
    day = envelope["retrieved_at"][:10].replace("-", "")
    # The origin block: a source record, named per LEI, per reply, per fetch date (D-035, D-042).
    return {"kind": "source", "record": f"src:gleif/{lei}/{kind}/{day}", "source": "GLEIF",
            # The exact web address the reply came from, and when we fetched it.
            "url": envelope["url"], "retrieved_at": envelope["retrieved_at"]}


# Turn an address into one line of text, keeping GLEIF's own words and order (D-037).
def one_line_address(addr: dict) -> str:
    # The parts in reading order: "care of" line, street lines, number, city, region, postcode, country.
    parts = [addr.get("mailRouting"), *addr.get("addressLines", []), addr.get("addressNumber"),
             # The rest of the address, from town to country.
             addr.get("city"), addr.get("region"), addr.get("postalCode"), addr.get("country")]
    # Join the parts that are filled in, separated by commas.
    return ", ".join(p for p in parts if p)


# Turn one GLEIF LEI record into Level 1 fact rows.
def level1_facts(rec: dict, org: dict) -> list[dict]:
    # The entity's LEI, used as its name in the graph (D-034).
    subject = f"lei:{rec['id']}"
    # The "entity" section of the record, which holds the Level 1 data.
    ent = rec["attributes"]["entity"]
    # The legal name's language, kept as a detail rather than changing the name itself.
    name_lang = ent["legalName"].get("language")
    # Start with "this is a legal entity": GLEIF issuing it an LEI is the evidence, so the record is its origin.
    rows = [fact(subject, "type", iri("ex:LegalEntity"), org)]
    # Then the legal name, adding its language as a detail if GLEIF gives one.
    rows += [fact(subject, "legalName", literal(ent["legalName"]["name"]), org,
                 # The language GLEIF gives for the name, e.g. "en" or "fr-LU".
                 {"language": literal(name_lang)} if name_lang else None)]
    # Each other name (e.g. a previous legal name), with its type and language as details.
    for other in ent.get("otherNames") or []:
        # The details: what kind of name it is, plus its language when given.
        details = {"nameType": literal(other["type"])}
        # Add the language only if GLEIF gives one.
        if other.get("language"):
            # The language as a detail.
            details["language"] = literal(other["language"])
        # Add the row.
        rows.append(fact(subject, "otherName", literal(other["name"]), org, details))
    # The simple single-value fields: our predicate name, then GLEIF's value.
    simple = {
        # FUND or GENERAL, as given (D-037: a value, not a class).
        "gleifCategory": ent.get("category"),
        # The legal-form code, e.g. "U8KA".
        "legalForm": (ent.get("legalForm") or {}).get("id"),
        # The country (or region) code of the jurisdiction.
        "jurisdiction": ent.get("jurisdiction"),
        # The entity's status, e.g. ACTIVE.
        "entityStatus": ent.get("status"),
        # The registration authority code, e.g. RA000585 for Companies House.
        "registeredAt": (ent.get("registeredAt") or {}).get("id"),
        # The registration number at that authority, as given.
        "registeredAs": ent.get("registeredAs"),
        # The LEI's own registration status, e.g. ISSUED, LAPSED or RETIRED (D-046, explains F13).
        "registrationStatus": (rec["attributes"].get("registration") or {}).get("status"),
    }
    # Add a row for each field GLEIF actually fills in (an empty field states nothing, so no row).
    for predicate, value in simple.items():
        # Skip fields GLEIF left empty.
        if value:
            # Add the row.
            rows.append(fact(subject, predicate, literal(value), org))
    # The legal address as one line, if there is one.
    if ent.get("legalAddress"):
        # Add the row.
        rows.append(fact(subject, "legalAddress", literal(one_line_address(ent["legalAddress"])), org))
    # The headquarters address as one line, if there is one; some "care of" lines appear only here (D-050).
    if ent.get("headquartersAddress"):
        # Add the row.
        rows.append(fact(subject, "headquartersAddress", literal(one_line_address(ent["headquartersAddress"])), org))
    # Hand back every Level 1 row for this entity.
    return rows


# Turn one Level 2 reply (a relationship or a reporting exception) into a fact row, or None.
def level2_fact(lei: str, part: str, data: dict, org: dict) -> dict | None:
    # The predicate for this kind of reply.
    predicate = LEVEL2_PARTS[part]
    # A reporting exception: store GLEIF's reason code as given (D-026).
    if data["type"] == "reporting-exceptions":
        # One row: entity -> reason.
        return fact(f"lei:{lei}", predicate, literal(data["attributes"]["reason"]), org)
    # Otherwise it is a relationship record.
    rel = data["attributes"]["relationship"]
    # The details GLEIF gives about the link itself: its status, quality and GLEIF's own ID.
    details = {"status": literal(rel["status"]),
               # How well GLEIF checked the link, e.g. FULLY_CORROBORATED.
               "corroboration": literal(data["attributes"]["registration"]["corroborationLevel"]),
               # GLEIF's own ID for this relationship record.
               "gleifRelationshipId": literal(data["id"])}
    # Look through the link's periods for when the relationship started.
    for period in rel.get("periods") or []:
        # Only the relationship's own period counts, and only if it has a start date.
        if period.get("type") == "RELATIONSHIP_PERIOD" and period.get("startDate"):
            # Kept exactly as given, time and all: "2021-01-17T23:00:00Z" is not silently cut to a date.
            details["startDate"] = literal(period["startDate"], "dateTime")
    # One row: entity -> the other entity, with the details.
    return fact(f"lei:{lei}", predicate, iri(f"lei:{rel['endNode']['id']}"), org, details)


# Read one cached search page as an envelope {"url", "retrieved_at", "body"}, whichever format it was saved in.
def read_search_envelope(path: Path) -> dict:
    # Read the saved file.
    saved = json.loads(path.read_text(encoding="utf-8"))
    # The 18 Oct format is already an envelope.
    if "body" in saved:
        # Use it as it is.
        return saved
    # The 16 Oct format is GLEIF's reply plus our "_retrieved_at", with no web address saved.
    # The page number, from the file name, e.g. "apax_p1" -> "1".
    number = path.stem.rsplit("_p", 1)[1]
    # GLEIF's own reply lists the addresses of its pages; take the one for this page (GLEIF's words, not ours).
    url = next(u for u in saved["links"].values() if f"page%5Bnumber%5D={number}&" in u)
    # Wrap it in the same envelope shape as the newer files.
    return {"url": url, "retrieved_at": saved["_retrieved_at"], "body": saved}


# Read every cached search reply for our sponsors' words.
# Returns {LEI: [(record, envelope, reply name), ...]}: every reply that contains the entity (D-042).
def search_records() -> dict[str, list[tuple[dict, dict, str]]]:
    # Open the settings file in binary mode, as tomllib requires.
    with CONFIG_PATH.open("rb") as f:
        # Turn the TOML text into Python data.
        config = tomllib.load(f)
    # Every search word, across all sponsors, in a fixed order.
    terms = sorted(t for s in config["sponsors"].values() for t in s["search_terms"])
    # The records found so far.
    found = {}
    # Go through each word.
    for term in terms:
        # The file-name form of the word, as the downloader saves it, e.g. "hg_pooled".
        slug = term.lower().replace(" ", "_")
        # Every cached page for that word, from both search folders (16 and 18 Oct), in a fixed order.
        for page in sorted(p for d in SEARCH_DIRS for p in (CACHE_DIR / d).glob(f"{slug}_p*.json")):
            # Read the saved envelope, converting the older 16 Oct format if needed.
            envelope = read_search_envelope(page)
            # The reply's name for its source record, e.g. "search-apax_p1".
            reply = f"search-{page.stem}"
            # Go through each record on the page.
            for rec in envelope["body"]["data"]:
                # Keep every reply that contains this entity, each as its own observation (D-042).
                found.setdefault(rec["id"], []).append((rec, envelope, reply))
    # Hand back the records, each with the reply it came from.
    return found


# Parse the whole GLEIF cache into fact rows. Returns (rows, counts of anything unusual).
def parse_all() -> tuple[list[dict], dict]:
    # All the rows produced.
    rows = []
    # Counts of unusual cases, reported rather than hidden.
    unusual = {"linked reply said not found": 0}
    # The entities our sponsor searches found.
    searched = search_records()
    # Level 1 facts for each searched entity, from every search reply that contains it (D-042).
    for lei, replies in searched.items():
        # Each reply that contains it.
        for rec, envelope, reply in replies:
            # Add its rows, with this reply as their source record.
            rows += level1_facts(rec, origin(lei, reply, envelope))
    # Level 1 facts from single LEI records: outside parents and managers, plus any searched entity
    # whose own record was also fetched (another dated observation, D-042).
    for path in sorted((CACHE_DIR / "lei-records").glob("*/record.json")):
        # The LEI is the folder name.
        lei = path.parent.name
        # Read the saved envelope.
        envelope = json.loads(path.read_text(encoding="utf-8"))
        # Only if GLEIF found the record.
        if envelope["body"]:
            # Add its rows.
            rows += level1_facts(envelope["body"]["data"], origin(lei, "record", envelope))
    # Level 2 facts for each searched entity, from each kind of cached reply.
    for lei in searched:
        # Each kind of Level 2 reply.
        for part in LEVEL2_PARTS:
            # Where that reply would be cached.
            path = CACHE_DIR / "lei-records" / lei / f"{part}.json"
            # Not every entity has every kind (GLEIF gives either a parent or an exception).
            if not path.exists():
                # Nothing to parse for this kind.
                continue
            # Read the saved envelope.
            envelope = json.loads(path.read_text(encoding="utf-8"))
            # GLEIF linked to this reply but then said "not found": count it rather than hide it.
            if envelope["body"] is None:
                # Count the case.
                unusual["linked reply said not found"] += 1
                # Nothing to parse.
                continue
            # The useful part of the reply (sometimes a one-item list).
            data = envelope["body"]["data"]
            # Unwrap a list to its first item.
            data = data[0] if isinstance(data, list) else data
            # Short name for the kind of reply, used in the source record's name, e.g. "direct-parent-exception".
            kind = part.replace("-reporting-exception", "-exception").replace("-relationship", "")
            # Add the row.
            rows.append(level2_fact(lei, part, data, origin(lei, kind, envelope)))
    # Hand back the rows and the counts.
    return rows, unusual
