# Data sources

What each source is, what it gives us, how the sources link up, and what we have learned from the real data. Written 18 Oct 2026, and updated as we learn more.

**The one-line version:** the **LEI is the anchor**. Every fact attaches to an entity, and entities are identified by their LEI wherever possible.

```
GLEIF (who is who; who manages which fund)
   │  register code RA000585 + company number  (D-025)
   ▼
Companies House (who controls whom, in the UK) ──▶ our two graphs ◀── Press releases (deals, fund closes)
                                                                       names matched to LEIs (entity matching)
```

---

## 1. GLEIF (Global Legal Entity Identifier Foundation)

- **What it is:** a non-profit that publishes every LEI in the world. The data is free and updated daily.
- **The LEI:** a 20-character code, one per *legal entity*, not per brand. A sponsor such as Apax is a group of many entities.
- **Level 1, "who is who":**
  - legal name and other names
  - addresses
  - country of registration
  - legal form
  - category (`FUND` or `GENERAL`)
  - status
  - **register code + registration number** (Companies House = `RA000585`).
- **Level 2, "who owns whom":**
  - the direct and ultimate *accounting* parent: only reported when the parent consolidates the entity in its accounts
  - otherwise a **reporting exception**: a stated reason for naming no parent.
- **Fund relationships:** `IS_FUND-MANAGED_BY`, `IS_SUBFUND_OF`, `IS_FEEDER_TO`. Each is a full relationship record with a status, start dates and a corroboration level.
- **Access:** `api.gleif.org`, max 60 requests per minute. The fetcher is `src/seisa_kg/sources/gleif.py`, which caches every reply in `data/raw/gleif/` with its URL and the date it was fetched.

## 2. Companies House (UK)

- **What it is:** the UK government's register of companies, LLPs and limited partnerships.
- **The identifier:** an 8-character company number. The prefix gives the type:
  - digits only: an ordinary company
  - `OC`: an LLP
  - `LP`: an English limited partnership
  - `SL`: a Scottish limited partnership
  - `SC`: a Scottish company.
- **What it gives us:**
  - **Company profile.**
  - **Officers:** directors, with their appointment dates.
  - **PSC (people with significant control):** whoever holds more than 25% of the shares or votes, can appoint the board, or has significant influence.
- **PSC can name a company, not just a person.** Following PSC → PSC climbs the ownership chain (BidCo → MidCo → TopCo → fund). **This fills GLEIF's gap.**
- **Limits:**
  - UK entities only.
  - Ownership is shown in bands (25–50%, 50–75%, 75%+), not exact percentages.
- **Access:** free API with a key, max 600 requests per 5 minutes. *(Downloader: Monday.)*

## 3. Press releases

- **Where from:** the sponsors' own websites, and newswires.
- **What they announce:**
  - fund closes: name, size, date
  - acquisitions: buyer, target, seller, date, sometimes the price
  - advisers
  - exits.
- **Why they matter:** they're the only source that says "Fund X bought Company Y" in plain words.
- **How we use them:**
  - The LLM (Gemini) extracts facts against our schema.
  - Every fact is tied to its exact sentence, and its quote is checked by code.
  - Names are matched to LEIs (entity matching), and 50 pairs are checked by hand.

## What no source gives us (to be said openly)

- LPs (fund investors) are mostly private.
- Deal prices are often undisclosed.
- Exact ownership percentages aren't given.
- Offshore entities (Guernsey, Luxembourg, Cayman) appear in GLEIF only.

## Industry terms → where each shows up

| Term | Where |
|---|---|
| Sponsor | A brand, not a single entity; its name appears in entity names and in the news |
| GP / manager | GLEIF fund-manager links (but see finding F3); Companies House LLPs |
| Fund | GLEIF category `FUND`; fund-close news |
| Holding companies | Companies House PSC chains |
| Portfolio company | Companies House; acquisition news |
| LP | Mostly missing |

---

## Findings from the real data

### Sponsor check (16 Oct): `docs/sponsor-check.md`

- **F1 · GLEIF records almost no parents for sponsor entities.** Nearly all give a reporting exception instead.
- **F2 · 185 entities are registered at Companies House**, all with clean 8-character numbers:
  - 140 `LP…`
  - 38 ordinary companies
  - 5 `OC…`
  - 2 `SL…`.

### Warm-up (18 Oct): `docs/gleif-warmup.md`

- **F3 · Why there's no parent:** of 60 entities sampled (20 per sponsor):
  - **50 `NON_CONSOLIDATING`**: the owner doesn't consolidate the entity in its accounts. This fits the investment-entity rule: funds don't consolidate what they own.
  - **7 `NO_KNOWN_PERSON`**
  - **3 `NATURAL_PERSONS`**
  - Only **3 actual parents** across all three sponsors, e.g. APAX PARTNERS WORLDWIDE HOLDINGS LTD → APAX PARTNERS LLP, and BRIDGEPOINT FUND MANAGEMENT S.À R.L. → BRIDGEPOINT GROUP PLC.
- **F4 · GLEIF's "fund manager" is not always a GP:**
  - **Apax:** 65 relationships. Mostly to **GP companies** in Guernsey (e.g. Apax Digital II GP Co. Limited, 35 funds), but also to a **regulated management company** (Apax Management Luxembourg S.à r.l., 9 funds).
  - GLEIF doesn't separate the two roles, so the schema must not assume "fund manager = GP". A role should come only from evidence.
- **F5 · Some funds are run by outside companies:**
  - **Bridgepoint:** 5 relationships, 3 of them to outside companies (Yacktman Asset Management, US; Amchor, Spain; Gen II, Luxembourg).
  - **Hg:** its only relationship is to Universal-Investment-Luxembourg.
  - These are either **look-alike funds** (not the sponsor's) or **outsourced management companies**.
  - We need a rule for which entities belong to a sponsor (see the schema session).
- **F6 · The relationships carry time and quality information:**
  - Every Apax and Bridgepoint relationship has a **start date**, a **status** (all `ACTIVE`) and a **corroboration level** (most are `FULLY_CORROBORATED`; a few are `ENTITY_SUPPLIED_ONLY`).
  - One start date, **1974-10-17**, looks wrong. We store it as given, with its source, rather than "fixing" it.
- **F7 · GLEIF changes daily.** Hg had 104 entities on 16 Oct and 105 on 18 Oct. So the date each reply was fetched is part of every fact's provenance.
- **F8 · Hg has almost no GLEIF structure** (1 fund-manager link, 0 parents). Its structure will have to come from Companies House, where 81 of its entities are registered.

### Builder step (18 Oct)

- **F12 · rdflib 7.6 can't read RDF 1.2 annotations, so pyshacl can't check them.** It fails silently: an empty graph "conforms". Oxigraph's SPARQL does see them. Handled by D-038.

- **F13 · 10 entities have no Level 2 link at all:** 4 retired LEIs, 5 lapsed LEIs and 1 branch. GLEIF stops asking for Level 2 data in those cases, so the gap is explained by GLEIF's own registration status.
- **F14 · Between 16 and 18 Oct, no Level 1 fact changed** for the 483 entities in both sets of replies. The only change is one new entity, HG MERCURY 4 FUSION L.P.

### What the findings mean for the schema (to decide in the schema session)

- "No parent, for reason X" becomes a **stored fact** with its reason code and its source, not a missing link.
- A fund-manager relationship becomes a link carrying **RDF-star annotations**: the source record, the date fetched, the start date, the status and the corroboration level. This is a natural fit for D-015, and a direct answer to the brief's question about how each model handles a new kind of fact with dates.
- The roles **GP** and **manager** are only assigned on evidence (finding F4).
- We need a **rule for which entities belong to a sponsor** (finding F5).
