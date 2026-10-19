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
- **F14 · Between 16 and 18 Oct, almost nothing changed** for the 483 entities in both sets of replies: one new entity (HG MERCURY 4 FUSION L.P.), and one registration status change (ΑΠΑΞ, a Greek look-alike: PENDING_TRANSFER → PENDING_ARCHIVAL). Both dates' values are kept (D-042).
- **Registration status (D-046):** at the latest fetch, 401 of 489 entities are ISSUED, 59 LAPSED, 28 RETIRED and 1 PENDING_ARCHIVAL.

- **F16 · How sponsor addresses appear:** care-of is often not written "c/o" (the address starts with the sponsor company's name); the sponsor's word appears in street names (Bridgepoint Drive, Parkway, Plaza); an unrelated namesake (Bridgepoint Group Accounting, Australia); some care-of names have no LEI in our data (Apax Partners Guernsey Limited). See D-048 to D-050.

### What the findings mean for the schema (to decide in the schema session)

- "No parent, for reason X" becomes a **stored fact** with its reason code and its source, not a missing link.
- A fund-manager relationship becomes a link carrying **RDF-star annotations**: the source record, the date fetched, the start date, the status and the corroboration level. This is a natural fit for D-015, and a direct answer to the brief's question about how each model handles a new kind of fact with dates.
- The roles **GP** and **manager** are only assigned on evidence (finding F4).
- We need a **rule for which entities belong to a sponsor** (finding F5).

### Source study: how UK-based our companies are, and Companies House (19 Oct)
Real records were fetched with `scripts/ch_sample.py` and cached in `data/raw/companies_house/`. There were five samples, one of each kind: an ordinary company, two LLPs, a Scottish LP and an English LP.

- **F23 · Our "UK" sponsors keep most of their fund vehicles offshore.** In-scope companies by country:
  - **Hg:** 79 GB, 10 GG, 7 LU, 2 US. Mostly UK.
  - **Bridgepoint:** 87 LU, 65 GB, 12 IE, and others.
  - **Apax:** 101 GG, 27 LU, 14 GB, and others.

  153 of the 444 In-scope companies are at Companies House: 124 English LPs, 25 ordinary companies, 2 LLPs and 2 Scottish LPs. So the "UK" part is the **sponsors' firms and their UK companies**; many funds are offshore and visible only in GLEIF.
- **F24 · English LPs have no control (PSC) record and no officers.**
  - HGCAPITAL 5, L.P. (LP010937): the PSC list says "not found", and so do the PSC statements.
  - So Companies House says almost nothing about **most of our UK fund vehicles** (124 of them).
- **F25 · Scottish LPs do have PSC records.**
  - HG SATURN FAF L.P. (SL032338) names Hg Pooled Management Ltd, HgCapital LLP, and a private individual (50–75% share of surplus assets).
- **F26 · For ordinary companies, the PSC chain climbs cleanly:**
  - Bridgepoint Advisers Ltd → Bridgepoint Advisers Holdings → Bridgepoint Advisers Group Ltd → Bridgepoint Group Holdings Ltd → Bridgepoint Op GP Ltd. Before 11 Oct 2024, the top was Bridgepoint Group plc.
  - Each step is "owns 75–100% of shares and votes, and can appoint the directors".
  - This is the "who controls whom" that GLEIF lacks.
- **F27 · Control comes in kinds and bands, not one "owns" arrow.**
  - Each controller has a list of "natures of control": shares 25–50 / 50–75 / 75–100%, votes, the right to appoint directors, or "significant influence".
  - Exact percentages are never given.
- **F28 · History is kept.**
  - Controllers have `ceased_on` dates (Bridgepoint Group plc ceased 2024-10-11; Lux Topco 1 Sàrl ceased 2022-10-31).
  - Previous names have date ranges (Bridgepoint Advisers Ltd was NatWest Private Equity Ltd, 1996–97).
  - This fits Q7 ("what changed") and the brief's question about start and end dates.
- **F29 · Chains can loop.**
  - Bridgepoint Group Holdings Ltd lists Bridgepoint Advisers Ltd (the company we started from) as having "significant influence".
  - Any chain-climbing query must guard against going round in circles.
- **F30 · Registration numbers in PSC records are typed by hand and messy:**
  - "1899316" (missing its leading zero)
  - "Oc301825" and "Sc257176" (lower case)
  - "B263996" (a Luxembourg number)
  - **none at all** for a UK company in one record (Group Holdco 1 Ltd), though another record has it (13868078).

  Store them as given (D-029); linking them to companies is a matching step.
- **F31 · A stated "no controller" exists, as in GLEIF.**
  - Group Holdco 1 Ltd's PSC statement is `no-individual-or-entity-with-signficant-control` (Companies House's own spelling, typo included).
  - That's a stated absence, like GLEIF's reporting exceptions (D-026).
  - This is why the HgCapital chain stops there: HgCapital LLP → Group Holdco 1 Ltd → "no registrable controller".
- **F32 · Chains end at people or offshore companies.**
  - Apax Partners LLP is controlled by two named individuals (members' appointment rights).
  - Hg's chain once led to Lux Topco 1 Sàrl in Luxembourg, which Companies House can't follow; GLEIF might.
- **F33 · Officers are numerous and mostly history:** Bridgepoint Advisers Ltd has 8 active and 88 resigned officers. They're personal data, and none of our 12 questions needs them.
- **Profile fields:** name, number, type (`ltd`, `llp`, `limited-partnership`), status, creation date, registered office (split into lines), SIC industry codes, previous names, accounts and filing dates, and flags (charges, insolvency).

### Source study: news releases (19 Oct)
Probed the three sponsors' news pages and two real deal releases: Apax's NextGen Security (9 Sep 2026) and Hg's A-LIGN (8 Jul 2025).
- **F34 · Hg and Apax list their releases in plain HTML; Bridgepoint's list is loaded by JavaScript.**
  - A program sees no article links on Bridgepoint's page.
  - Bridgepoint releases have to be found another way (a search engine or a newswire); the article pages themselves may still be plain HTML.
- **F35 · The text comes out cleanly** with a standard main-text extractor, including the title and publication date. One quirk: Apax repeats its first paragraph as a teaser, so the same sentence appears twice. De-duplicate sentences before extraction.
- **F36 · What a deal release contains** (both samples):
  - **buyer:** usually the sponsor as a brand ("Hg"), or its funds via the adviser entity: "Funds advised by Apax Partners LLP". Apax Partners LLP is our `ch:OC303117`.
  - **target:** NextGen Security, A-LIGN
  - **seller:** Dunes Point Capital, LP; Warburg Pincus (and FTV Capital thanked)
  - **stake:** "a majority stake" (Hg), or not said
  - **price:** "Financial terms … were not disclosed"
  - **date:** the publication date, plus the text's own (sometimes without a year: "July 8th")
  - **stated reasons:** "to accelerate its growth by … selective acquisitions", "accelerate its global expansion". These support Q8–Q9.
  - **people quoted:** the target's CEO and sponsor partners.
- **F37 · Both sample targets are US companies.** Companies House can't climb their chains. For the UK case study, choosing releases about UK companies matters (Bruno to decide).
- **F38 · Names in releases are brands and short forms** ("Hg", "Apax Funds", "the Company"), not legal names. Matching them to LEIs or Companies House numbers is the entity-matching step (50 pairs hand-checked).
