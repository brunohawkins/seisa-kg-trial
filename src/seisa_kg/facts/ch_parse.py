"""SUMMARY: Turns the cached Companies House replies into fact rows
(pipeline stage 2, parse, for Companies House; schema section 9).

What it makes, per company in data/raw/companies_house/<number>/:
- The company itself (ch:<number>, D-034): name, type, status, incorporation
  date, registered office (one line, as D-069), SIC codes, previous names.
- One Stake per control (PSC) record (D-075): the company, the controller as
  given (name, kind, registration number, country), each nature of control,
  and the notified and ceased dates. Our rule "ch-natures" reads the share
  band, vote band, surplus band and board rights out of Companies House's
  fixed codes.
- The tidy "holder" link (D-076): to ch:<tidy number> when the controller is
  a UK company, or to a Person node when it is a person. Anything that can't
  be resolved is listed in docs/ch-tidy-report.md.
- A stated "no controller" (F31) as a pscStatement fact.
- One Appointment per officer, current and past (D-077), linked to a Person
  node keyed by Companies House's officer ID (D-074), or, for a corporate
  officer, to ch:<tidy number> by rule D-076.
- The sameEntityAs link between a GLEIF LEI and a Companies House number,
  made by our rule D-025 (same register, same number).
Every row carries its origin: the Companies House reply it came from, or the
rule that made it (D-029).
"""

# Reads the cached replies.
import json
# Pattern matching, used to read the control codes.
import re
# A tidy way of working with file and folder paths.
from pathlib import Path

# The tidying rule for company numbers, and the UK test (D-076).
from seisa_kg.facts.ch_tidy import is_uk_registered, tidy_company_number
# The shared fact format.
from seisa_kg.facts.model import PROJECT_ROOT, fact, iri, literal

# Where the Companies House replies are cached.
CACHE_DIR = PROJECT_ROOT / "data" / "raw" / "companies_house"
# The tidying report for Bruno.
REPORT_PATH = PROJECT_ROOT / "docs" / "ch-tidy-report.md"
# The code GLEIF uses for the Companies House register.
CH_REGISTER = "RA000585"
# Our rules used here, with a plain-English label each.
RULES = {"D-025": "Link a GLEIF LEI to a Companies House number: register RA000585 and the same number",
         # The tidy links.
         "D-076": "Tidy a hand-typed company number and link to that company (the as-given value is kept)",
         # Reading the control codes.
         "ch-natures": "Read share, vote and surplus bands and board rights from Companies House's control codes"}


# The origin block for one Companies House reply (D-035): a source record per company, per part, per fetch date.
def origin(number: str, part: str, env: dict) -> dict:
    # The fetch date as digits, e.g. "2026-10-19T16:41:02+00:00" -> "20261019".
    day = env["retrieved_at"][:10].replace("-", "")
    # The record name, the source, the address and the fetch time.
    return {"kind": "source", "record": f"src:ch/{number}/{part}/{day}", "source": "CompaniesHouse",
            # Exactly where and when.
            "url": env["url"], "retrieved_at": env["retrieved_at"]}


# The origin block for one of our rules.
def rule(name: str) -> dict:
    # "Made by our rule <name>".
    return {"kind": "rule", "rule": name}


# Read one cached reply; returns the envelope, or None if the file doesn't exist.
def load(path: Path) -> dict | None:
    # Read and decode it if it's there.
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


# Read every page of a list (officers or PSCs); returns (items, envelope of page 1).
def pages(folder: Path, part: str) -> tuple[list[dict], dict | None]:
    # The items, and the first page's envelope (used as the origin).
    items, first = [], None
    # Each page file, in page order (p1, p2, ...).
    for path in sorted(folder.glob(f"{part}_p*.json"), key=lambda p: int(p.stem.split("_p")[1])):
        # Read it.
        env = load(path)
        # Keep the first page's envelope.
        first = first or env
        # Add this page's items, tagged with their own page's envelope.
        items += [(it, env) for it in ((env["body"] or {}).get("items", []))]
    # Hand back everything.
    return items, first


# Turn a Companies House address into one line, keeping its own words and order (as D-069).
def one_line(addr: dict | None) -> str:
    # No address: empty text.
    if not addr:
        # Nothing to join.
        return ""
    # The parts in reading order.
    keys = ["care_of", "po_box", "premises", "address_line_1", "address_line_2", "locality", "region", "postal_code", "country"]
    # Join the filled-in parts with commas.
    return ", ".join(addr[k].strip() for k in keys if addr.get(k))


# A date literal, or None if there is no date.
def date(value: str | None) -> dict | None:
    # Typed as xsd:date when present.
    return literal(value, "date") if value else None


# "Year-month" of birth as text, e.g. "1970-05", or None (Companies House gives month and year only).
def birth(dob: dict | None) -> str | None:
    # Both parts are needed.
    return f"{dob['year']}-{dob['month']:02d}" if dob and dob.get("year") and dob.get("month") else None


# The facts about one company's profile.
def profile_facts(number: str, env: dict) -> list[dict]:
    # The company's node (D-034).
    s = f"ch:{number}"
    # The profile, and its origin.
    p, org = env["body"], origin(number, "profile", env)
    # "This is a legal entity", its name, type and status.
    rows = [fact(s, "type", iri("ex:LegalEntity"), org), fact(s, "legalName", literal(p["company_name"]), org),
            # Type (e.g. ltd, llp, limited-partnership) and status (e.g. active), as given.
            fact(s, "companyType", literal(p.get("type", "")), org), fact(s, "companyStatus", literal(p.get("company_status", "")), org)]
    # The incorporation date, if given.
    if p.get("date_of_creation"):
        # A proper date.
        rows.append(fact(s, "incorporatedOn", date(p["date_of_creation"]), org))
    # The registered office, as one line of text, if given.
    if one_line(p.get("registered_office_address")):
        # One line, as D-069.
        rows.append(fact(s, "registeredOffice", literal(one_line(p["registered_office_address"])), org))
    # Each SIC industry code.
    for code in p.get("sic_codes", []):
        # One row per code.
        rows.append(fact(s, "sicCode", literal(code), org))
    # Each previous name, with its dates as details (like GLEIF's otherName).
    for prev in p.get("previous_company_names", []):
        # The dates it was used, where given.
        details = {k: v for k, v in (("effectiveFrom", date(prev.get("effective_from"))), ("ceasedOn", date(prev.get("ceased_on")))) if v}
        # The name, as given (trailing spaces trimmed).
        rows.append(fact(s, "previousName", literal(prev["name"].strip()), org, details))
    # Hand back the rows.
    return rows


# Read the bands and board rights out of the control codes (rule ch-natures).
def read_natures(codes: list[str]) -> dict[str, str]:
    # The readings found.
    out = {}
    # Each kind of band and the code pattern that carries it.
    for name, pat in (("shareBand", r"ownership-of-shares-(\d+)-to-(\d+)-percent"),
                      # Votes.
                      ("voteBand", r"voting-rights-(\d+)-to-(\d+)-percent"),
                      # A partnership's share of its surplus assets.
                      ("surplusBand", r"right-to-share-surplus-assets-(\d+)-to-(\d+)-percent")):
        # The first code that matches.
        m = next((re.search(pat, c) for c in codes if re.search(pat, c)), None)
        # Record the band as "low-high", e.g. "75-100".
        if m:
            # The band.
            out[name] = f"{m.group(1)}-{m.group(2)}"
    # The right to appoint the board (directors, or an LLP's members).
    if any(re.search(r"right-to-appoint-and-remove-(directors|members)", c) for c in codes):
        # Recorded as true.
        out["appointsBoard"] = "true"
    # Hand back the readings.
    return out


# The facts about one company's control records (Stakes, D-075), plus unresolved holders for the report.
def stake_facts(number: str, items: list) -> tuple[list[dict], list[str]]:
    # The rows, and the report lines.
    rows, unresolved = [], []
    # Each control record, with the page it came from.
    for it, env in items:
        # The record's own ID: the last part of its link, e.g. ".../corporate-entity/A4SLyy2...".
        pid = (it.get("links", {}).get("self") or "").rstrip("/").split("/")[-1] or f"n{len(rows)}"
        # The Stake's node.
        s = f"ex:stake/{number}/{pid}"
        # The record's origin.
        org = origin(number, "psc", env)
        # The controller's identification (companies only).
        ident = it.get("identification") or {}
        # "This is a stake", on which company, and the controller as given.
        rows += [fact(s, "type", iri("ex:Stake"), org), fact(s, "company", iri(f"ch:{number}"), org),
                 # The controller's name and kind, as given.
                 fact(s, "holderName", literal(it.get("name", "")), org), fact(s, "holderKind", literal(it.get("kind", "")), org)]
        # The controller's registration details, as given, where present.
        for key, pred in (("registration_number", "holderRegistrationNumber"), ("country_registered", "holderCountry"), ("place_registered", "holderPlaceRegistered")):
            # Only if given.
            if ident.get(key):
                # As given.
                rows.append(fact(s, pred, literal(ident[key]), org))
        # Each nature of control code, as given.
        for code in it.get("natures_of_control", []):
            # One row per code.
            rows.append(fact(s, "natureOfControl", literal(code), org))
        # The notified and ceased dates, where given.
        for key, pred in (("notified_on", "notifiedOn"), ("ceased_on", "ceasedOn")):
            # Only if given.
            if it.get(key):
                # A proper date.
                rows.append(fact(s, pred, date(it[key]), org))
        # The bands and board rights, read by our rule.
        for pred, value in read_natures(it.get("natures_of_control", [])).items():
            # Labelled as made by rule ch-natures.
            rows.append(fact(s, pred, literal(value, "boolean" if pred == "appointsBoard" else None), rule("ch-natures")))
        # The tidy holder link (D-076), by kind of controller.
        kind = it.get("kind", "")
        # A person: their own Person node (D-074), from the same record.
        if kind.startswith("individual"):
            # The person's node: one per record, never merged today.
            person = f"ex:person/psc/{number}/{pid}"
            # The link, and the person's details as given.
            rows += [fact(s, "holder", iri(person), org), fact(person, "type", iri("ex:Person"), org),
                     # Their name, as given.
                     fact(person, "name", literal(it.get("name", "")), org)]
            # The details that tell people apart (D-074), where given.
            for pred, value in (("birthYearMonth", birth(it.get("date_of_birth"))), ("nationality", it.get("nationality")), ("countryOfResidence", it.get("country_of_residence"))):
                # Only if given.
                if value:
                    # As given.
                    rows.append(fact(person, pred, literal(value), org))
        # A company: link it if it is a UK company with a usable number.
        elif kind.startswith("corporate") and is_uk_registered(ident) and tidy_company_number(ident.get("registration_number")):
            # The tidy number.
            tidy = tidy_company_number(ident.get("registration_number"))
            # Labelled as made by rule D-076; the as-given number stays above.
            rows.append(fact(s, "holder", iri(f"ch:{tidy}"), rule("D-076")))
            # Note the tidying when it changed the number.
            if tidy != ident.get("registration_number"):
                # One report line.
                unresolved.append(f"| {number} | {it.get('name')} | `{ident.get('registration_number')}` | tidied to `{tidy}` |")
        # Anything else (non-UK company, missing number, legal person): unresolved, for the report.
        else:
            # One report line, saying why.
            unresolved.append(f"| {number} | {it.get('name')} | `{ident.get('registration_number')}` | **unresolved**: {ident.get('country_registered') or kind} |")
    # Hand back the rows and the report lines.
    return rows, unresolved


# The facts about one company's officers: Appointments and Persons (D-074, D-077).
def officer_facts(number: str, items: list) -> tuple[list[dict], list[str]]:
    # The rows, and report lines for unresolved corporate officers.
    rows, unresolved = [], []
    # Appointment node names already used, to keep each one unique.
    used = set()
    # Each officer record, with the page it came from.
    for it, env in items:
        # The record's origin.
        org = origin(number, "officers", env)
        # Companies House's officer ID, from the officer's link, e.g. "/officers/AbC123/appointments".
        oid = (it.get("links", {}).get("officer", {}).get("appointments") or "").split("/")[2:3]
        # The ID itself, or a fallback.
        oid = oid[0] if oid else f"n{len(used)}"
        # The Appointment's node, unique even if the same person was appointed twice here.
        a = f"ex:appointment/{number}/{oid}"
        # Add a counter if this name was already used.
        if a in used:
            # e.g. ".../AbC123-2".
            a = f"{a}-{sum(1 for u in used if u.startswith(a))+1}"
        # Mark it as used.
        used.add(a)
        # "This is an appointment", at which company, the role and the name as given.
        rows += [fact(a, "type", iri("ex:Appointment"), org), fact(a, "company", iri(f"ch:{number}"), org),
                 # Role (e.g. director, llp-member) and the officer's name, as given.
                 fact(a, "role", literal(it.get("officer_role", "")), org), fact(a, "officerName", literal(it.get("name", "")), org)]
        # The appointment's dates, where given.
        for key, pred in (("appointed_on", "appointedOn"), ("resigned_on", "resignedOn")):
            # Only if given.
            if it.get(key):
                # A proper date.
                rows.append(fact(a, pred, date(it[key]), org))
        # A corporate officer (e.g. a corporate LLP member): a company, not a person.
        if it.get("officer_role", "").startswith("corporate"):
            # Its identification, if given.
            ident = it.get("identification") or {}
            # Its tidy number, if it is a UK company.
            tidy = tidy_company_number(ident.get("registration_number")) if is_uk_registered(ident) else None
            # Link it by rule D-076, or report it.
            if tidy:
                # The tidy link to the company.
                rows.append(fact(a, "officer", iri(f"ch:{tidy}"), rule("D-076")))
            # Not resolvable: report it.
            else:
                # One report line.
                unresolved.append(f"| {number} | {it.get('name')} (officer) | `{ident.get('registration_number')}` | **unresolved**: {ident.get('country_registered') or 'no UK number'} |")
        # A person: their Person node, keyed by the officer ID (D-074).
        else:
            # The person's node.
            person = f"ex:person/officer/{oid}"
            # The link, and the person's details as given.
            rows += [fact(a, "officer", iri(person), org), fact(person, "type", iri("ex:Person"), org),
                     # Their name, as given.
                     fact(person, "name", literal(it.get("name", "")), org)]
            # The details that tell people apart (D-074), where given.
            for pred, value in (("birthYearMonth", birth(it.get("date_of_birth"))), ("nationality", it.get("nationality")), ("countryOfResidence", it.get("country_of_residence"))):
                # Only if given.
                if value:
                    # As given.
                    rows.append(fact(person, pred, literal(value), org))
    # Hand back the rows and report lines.
    return rows, unresolved


# Parse every cached company, add the D-025 links, and write the tidying report. Returns the rows.
def parse_all(gleif_rows: list[dict]) -> list[dict]:
    # All rows, and all report lines.
    rows, report = [], []
    # The company numbers with a profile (the companies we have).
    have = set()
    # Each company folder, in number order.
    for folder in sorted(p for p in CACHE_DIR.iterdir() if p.is_dir()):
        # The company number is the folder name.
        number = folder.name
        # Its profile.
        prof = load(folder / "profile.json")
        # Only companies with a found profile become nodes.
        if prof and prof["body"]:
            # The profile facts.
            rows += profile_facts(number, prof)
            # Remember we have it.
            have.add(number)
        # The control records (every page).
        pscs, _ = pages(folder, "psc")
        # Their facts and report lines.
        r, u = stake_facts(number, pscs)
        # Add both.
        rows += r
        # Add the report lines.
        report += u
        # The PSC statements, e.g. "no registrable controller" (F31).
        st = load(folder / "psc_statements.json")
        # Each statement, if any.
        for item in ((st or {}).get("body") or {}).get("items", []):
            # Its end date as a detail, if it has ended.
            details = {"ceasedOn": date(item["ceased_on"])} if item.get("ceased_on") else None
            # The statement code, as given (Companies House's own spelling).
            rows.append(fact(f"ch:{number}", "pscStatement", literal(item.get("statement", "")), origin(number, "psc_statements", st), details))
        # The officers (every page).
        officers, _ = pages(folder, "officers")
        # Their facts and report lines.
        r, u = officer_facts(number, officers)
        # Add both.
        rows += r
        # Add the report lines.
        report += u
    # GLEIF's register and number for each LEI.
    reg_at = {r["subject"]: r["object"]["value"] for r in gleif_rows if r["predicate"] == "registeredAt"}
    # The number, as GLEIF gives it.
    reg_as = {r["subject"]: r["object"]["value"] for r in gleif_rows if r["predicate"] == "registeredAs"}
    # D-025: register is Companies House AND the number is one we have.
    links = sorted((lei, n) for lei, n in reg_as.items() if reg_at.get(lei) == CH_REGISTER and n in have)
    # One sameEntityAs row per match, labelled as our rule's.
    rows += [fact(lei, "sameEntityAs", iri(f"ch:{n}"), rule("D-025")) for lei, n in links]
    # One Rule node per rule used here.
    for name, label in RULES.items():
        # "This is a rule", and its label.
        rows += [fact(f"ex:rule/{name}", "type", iri("ex:Rule"), rule(name)), fact(f"ex:rule/{name}", "label", literal(label), rule(name))]
    # Write the report.
    write_report(report, len(have), len(links))
    # Hand back the rows.
    return rows


# Write the tidying report (D-076): every number tidied and every holder left unresolved.
def write_report(lines: list[str], companies: int, links: int) -> None:
    # The opening lines.
    L = ["# Companies House tidying report (generated by `make facts`; do not edit by hand)", "",
         # The summary.
         f"{companies} companies parsed; {links} linked to a GLEIF LEI by rule D-025.", "",
         # What the table holds.
         "Every controller or corporate officer whose number was tidied (rule D-076), or that couldn't be linked. The as-given value is always kept in the graph.", "",
         # The table header.
         "| Company | Controller / officer | As given | Result |", "|---|---|---|---|"]
    # Save the report.
    REPORT_PATH.write_text("\n".join(L + sorted(set(lines))) + "\n", encoding="utf-8")
