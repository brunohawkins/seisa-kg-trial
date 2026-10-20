# RDF schema sketch (v1, 18 Oct 2026)

The shape of the RDF graph: GLEIF (sections 1–8), Companies House (section 9) and the news releases (section 10), for the three sponsors.

- **Settled by Bruno:** D-015, D-025, D-026, D-027, D-028, D-029, D-033, D-034, D-035, D-036, D-037.

---

## 1. The idea in one picture

```
              the fact                                     where it came from
lei:FUND ──ex:fundManagedBy──▶ lei:MANAGER
        └── annotation (RDF-star) ──prov:wasDerivedFrom──▶ src:… (SourceRecord) ──ex:url──▶ "https://api.gleif.org/…"
                │                                                    └──ex:retrievedAt──▶ 2026-10-18T…
                ├── ex:startDate      2021-01-17
                ├── ex:status         "ACTIVE"
                └── ex:corroboration  "FULLY_CORROBORATED"
```

- **Two kinds of origin** (D-029, D-033):
  - **What a source says:** the annotation points to a `SourceRecord` with `prov:wasDerivedFrom` (D-035).
  - **What we concluded:** the fact points to one of our `Rule`s with `prov:wasGeneratedBy` (D-028, D-025).
- **The general rule (D-036):**
  - a fact between **two** things is a triple with an RDF-star annotation
  - a fact about **several** things is a node.

## 2. Names (IRIs)

| Prefix | Stands for | Example | Status |
|---|---|---|---|
| `ex:` | our own vocabulary (classes and properties) | `ex:fundManagedBy` | **Confirmed (D-037):** base `https://seisa-kg.example/def/` |
| `lei:` | an entity, named by its LEI (D-034) | `lei:894500H5QJCD6LESMR63` | **Confirmed (D-037):** base `https://seisa-kg.example/lei/` |
| `ch:` | an entity, named by its Companies House number (D-034, from Monday) | `ch:LP012345` | **Confirmed (D-037):** base `https://seisa-kg.example/ch/` |
| `src:` | a source record (D-035) | `src:gleif/894500H5QJCD6LESMR63/fund-manager/20261018` | **Confirmed (D-037):** one per LEI, per kind of reply, per fetch date |
| `prov:` | the W3C provenance vocabulary (D-013) | `prov:wasDerivedFrom` | reused as is |

- **Why `.example`:** it is a domain reserved for examples, so it can never clash with a real website. It is easy to change later.
- **Alternative not chosen:** GLEIF's own published RDF names for LEIs. Could be added later as a link, without renaming anything.

## 3. Classes

| Class | What it is | Created when |
|---|---|---|
| `ex:LegalEntity` | anything with an LEI (and, from Monday, a Companies House number) | the identifier appears in a source |
| `ex:Sponsor` | Hg, Bridgepoint, Apax: a **brand**, not a legal entity | read from `config/sponsors.toml` |
| `ex:SourceRecord` | one fetched reply from a source (D-035) | each cached reply is parsed |
| `ex:Rule` | one of our rules, e.g. `ex:rule/D-028` | written once, with a plain-English description |
| `ex:ScopeDecision` | our in / review / out verdict for one entity and one sponsor (D-036) | the scope step runs |

- **Confirmed (D-037):** we do **not** create an `ex:Fund` class from GLEIF's category.
  - GLEIF's `FUND` / `GENERAL` is stored as a sourced value (`ex:gleifCategory`), like any other source fact (D-029).
  - Why: "this is a fund" is what GLEIF says. A class would quietly turn it into our own claim.
  - The cost: a query writes `?e ex:gleifCategory "FUND"` instead of `?e a ex:Fund`.

## 4. Facts from GLEIF (each with an RDF-star annotation → `SourceRecord`)

| Property | From GLEIF field | Value | Extra annotations |
|---|---|---|---|
| `rdf:type ex:LegalEntity` | the LEI record exists | — | — |
| `ex:legalName` | `entity.legalName` | text | `ex:language` (GLEIF's language code for the name) |
| `ex:otherName` | `entity.otherNames` | text | `ex:nameType` (e.g. `PREVIOUS_LEGAL_NAME`), `ex:language` |
| `ex:gleifCategory` | `entity.category` | text, as given | — |
| `ex:legalForm` | `entity.legalForm.id` | text code | — |
| `ex:jurisdiction` | `entity.jurisdiction` | text code | — |
| `ex:entityStatus` | `entity.status` | text, as given | — |
| `ex:legalAddress` | `entity.legalAddress` | one line of text: care-of line, street lines, number, city, region, postcode, country | — |
| `ex:headquartersAddress` | `entity.headquartersAddress` | one line of text, same layout (D-050) | — |
| `ex:registeredAt` | `entity.registeredAt.id` | text code (e.g. `RA000585`) | — |
| `ex:registeredAs` | `entity.registeredAs` | text, as given | — |
| `ex:registrationStatus` | `registration.status` | text, as given (e.g. `ISSUED`, `LAPSED`, `RETIRED`) (D-046) | — |
| `ex:directlyConsolidatedBy` / `ex:ultimatelyConsolidatedBy` | Level 2 parent: GLEIF's `IS_DIRECTLY_CONSOLIDATED_BY` / `IS_ULTIMATELY_CONSOLIDATED_BY`, meaning "adds me into its accounts", not "owns me" (D-068) | `lei:` IRI | same as `ex:fundManagedBy` |
| `ex:directParentException` / `ex:ultimateParentException` | Level 2 reporting exception (D-026) | the reason code, as given | — |
| `ex:fundManagedBy` | `IS_FUND-MANAGED_BY` relationship (D-027) | `lei:` IRI | `ex:startDate`, `ex:status`, `ex:corroboration`, `ex:gleifRelationshipId` |

- **Confirmed (D-037):** the address is kept as **one line of text** for now, not split into street, city and postcode.
  - Why: the only use so far is the "care of" scope test (D-028), and that reads the line as text.
- Every value is stored **as given**, including the 1974 start date (F6) and differently capitalised names (D-025).
- Start dates keep GLEIF's time, e.g. `2021-01-17T23:00:00Z`. Cutting it to a date would be a silent change: 23:00 UTC is already the next day in Luxembourg.
- No `ex:isGP` or `ex:isManager`: roles wait for a second source (D-027).

### Worked example (Turtle 1.2)

```turtle
# A fund and its manager, as GLEIF states it, with the source and the details as an annotation
lei:894500H5QJCD6LESMR63 ex:fundManagedBy lei:894500C7AD948MWIA623
    {| prov:wasDerivedFrom  src:gleif/894500H5QJCD6LESMR63/fund-manager/20261018 ;   # where it came from
       ex:startDate         "2021-01-17T23:00:00Z"^^xsd:dateTime ;                   # GLEIF's relationship start, as given (time included)
       ex:status            "ACTIVE" ;                                               # GLEIF's status, as given
       ex:corroboration     "FULLY_CORROBORATED" |} .                                # how well GLEIF checked it

# The record that the annotation points to
src:gleif/894500H5QJCD6LESMR63/fund-manager/20261018
    a                ex:SourceRecord ;                                               # it is a fetched reply
    ex:source        ex:GLEIF ;                                                      # which source
    ex:url           "https://api.gleif.org/api/v1/lei-records/894500H5QJCD6LESMR63/fund-manager-relationship" ;
    ex:retrievedAt   "2026-10-18T13:52:00Z"^^xsd:dateTime .                          # when we fetched it

# "No parent, for this reason" is a fact too (D-026)
lei:894500AOGUG91SHOC845 ex:directParentException "NON_CONSOLIDATING"
    {| prov:wasDerivedFrom src:gleif/894500AOGUG91SHOC845/direct-parent-exception/20261018 |} .
```

## 5. Our own judgements (each pointing to a `Rule`)

```turtle
# Our verdict on whether an entity belongs to a sponsor (D-028, D-036)
ex:scope/apax/213800ABC a ex:ScopeDecision ;                 # one decision, for one entity and one sponsor
    ex:entity           lei:213800ABC ;                       # which entity
    ex:sponsor          ex:sponsor/apax ;                     # which sponsor
    ex:verdict          ex:In ;                               # ex:In, ex:Review or ex:Out
    ex:reason           "address is c/o Apax Partners LLP" ;  # the evidence, in words
    prov:wasGeneratedBy ex:rule/D-028 .                       # made by our rule, not by a source

# The rule itself, so a reader can see what it says
ex:rule/D-028 a ex:Rule ;
    rdfs:label "Scope rule: in / review / out" ;
    rdfs:comment "In if the legal name contains the sponsor's name, or the address is care of a sponsor entity; ..." .
```

- **Review verdicts** that Bruno decides by hand: the verdict changes to `ex:In` or `ex:Out`, and `prov:wasGeneratedBy` points to `ex:rule/manual-review`, with Bruno's reason.
  - **Confirmed (D-037):** the earlier automatic `ex:Review` decision is kept, linked by `prov:wasRevisionOf`, so the history stays visible.
- From Monday, the D-025 match uses the same pattern:
  - `lei:X ex:sameEntityAs ch:Y {| prov:wasGeneratedBy ex:rule/D-025 |}`.

## 6. How it maps from the shared fact list (D-033)

- Each row becomes **one triple**, plus its annotation.
- **`origin.kind = "source"`:** the annotation gets `prov:wasDerivedFrom` → the row's `SourceRecord`.
- **`origin.kind = "rule"`:** we add `prov:wasGeneratedBy` → the rule.
- **`details`:** each entry becomes one more property on the annotation.
- A `ScopeDecision` is simply several rows with the same subject, `ex:scope/…`.
- The `SourceRecord` nodes are built from the cached envelopes (`url`, `retrieved_at`), not from rows.
- **Check:** the number of triples per predicate in Oxigraph must equal the number of rows per predicate in the list.

## 7. Checks (SHACL, D-013): proposed first set

1. Every `ex:LegalEntity` has at least one `ex:legalName`.
2. Every `ex:SourceRecord` has exactly one `ex:source`, `ex:url` and `ex:retrievedAt`.
3. Every `ex:ScopeDecision` has exactly one entity, sponsor, verdict (`ex:In` / `ex:Review` / `ex:Out`), reason and rule.
4. Every source fact's annotation has a `prov:wasDerivedFrom` that points to an `ex:SourceRecord`.

## 8. Risks and open points

- **SHACL and RDF-star:**
  - `pyshacl` runs on rdflib, whose RDF-star support is weak, so check 4 may not be expressible there.
  - Test this first in the builder step.
  - Fallback: write check 4 as a SPARQL query run in Oxigraph, and say so openly.
- **Many annotations:** every source fact gets its own hidden reifier node, so the graph is roughly 3× larger than the plain facts. That's fine at a few hundred entities; it is something to note in the timing runs.

---

## 9. Facts from Companies House (draft v2, 19 Oct, for Bruno's review)
Built from Bruno's decisions D-074 (people), D-075 (stake nodes) and D-076 (as-given plus tidy), and the earlier D-025, D-034 and D-036. Every source fact gets the usual RDF-star note → `src:ch/<number>/<part>/<date>`.

### The picture
```
ch:03220373 (Bridgepoint Advisers Ltd)                     ch:01899316 (Bridgepoint Advisers Holdings)
     ▲                                                              ▲
     │ ex:company                                                   │ ex:holder   (tidy link, rule D-076)
     │                                                              │
 ex:stake/03220373/<psc-id>  a ex:Stake ───────────────────────────┘
     ├─ ex:holderName               "Bridgepoint Advisers Holdings"      (as given)
     ├─ ex:holderRegistrationNumber "1899316"                            (as given)
     ├─ ex:natureOfControl          "ownership-of-shares-75-to-100-percent"   (as given; one per kind)
     ├─ ex:shareBand "75-100" · ex:voteBand "75-100" · ex:appointsDirectors true   (read from the codes)
     ├─ ex:notifiedOn 2016-04-06
     └─ ex:ceasedOn   (only if it has ended)

lei:XXXX ──ex:sameEntityAs──▶ ch:03220373        (rule D-025: register RA000585 + same number)
```

### Companies (from the profile)
| Arrow | From | Value |
|---|---|---|
| `rdf:type ex:LegalEntity` | any Companies House company | — |
| `ex:legalName` | `company_name` | text, as given |
| `ex:companyType` | `type` | e.g. `ltd`, `llp`, `limited-partnership` |
| `ex:entityStatus` | `company_status` | e.g. `active`, `dissolved`. **Same arrow as GLEIF's `entityStatus` (D-091)**; values kept as given |
| `ex:incorporatedOn` | `date_of_creation` | a date |
| `ex:legalAddress` | `registered_office_address` | one line of text (as D-069). **Same arrow as GLEIF's `legalAddress` (D-091)** |
| `ex:sicCode` | `sic_codes` | one per code |
| `ex:previousName` | `previous_company_names` | the name, with its from and to dates on the note (like GLEIF's `otherName`) |

### Control: the stake node (D-075, D-036)
- **One `ex:Stake` per PSC record:** `ex:stake/<company number>/<PSC id>`.
- **As given:** the controller's name, kind (company, person or legal person), registration number and country; each nature of control code; and the notified and ceased dates.
- **Read from the codes:** `shareBand`, `voteBand` and `appointsDirectors`.
  - These are simple readings of Companies House's fixed codes, e.g. `ownership-of-shares-75-to-100-percent` gives share band 75–100.
  - Marked as made by our rule `ex:rule/ch-natures`.
- **The tidy link `ex:holder`** (rule D-076) points to:
  - `ch:<number>`, when the controller is a UK company with a usable number (padded to 8 characters, upper case)
  - a **person** node, when the controller is a person
  - nothing, when it can't be resolved; this is then listed in the tidying report (e.g. Lux Topco 1 Sàrl, or a missing number).
- **A stated "no controller"** (F31) is stored like GLEIF's exceptions: `ch:13868078 ex:pscStatement "no-individual-or-entity-with-signficant-control"`.

### People (D-074)
- **An officer** is `ex:person/officer/<Companies House officer ID>`, holding name, month and year of birth, nationality and country of residence.
  - Each **appointment** is a node (D-036: a fact about several things): `ex:appointment/<company>/<officer ID>`, with person, company, role, appointed-on and resigned-on.
- **A PSC individual** has no Companies House ID. So each one is its **own** person node, `ex:person/psc/<company>/<PSC id>`, with the same details.
  - Linking them to an officer, or to each other, is a later matching step that compares every detail. No merges are made today, so two different people are never merged by mistake.

### Which companies are fetched
- Every In-scope company registered at Companies House (153; F23): profile, officers (all pages), PSC list and PSC statements.
- **Climbing:** for each controller that is a UK company, fetch that company too, up to 4 steps up, stopping at loops (F29).
- About 700 requests. At Companies House's limit this takes about 7 minutes, and only once (cached).

### Open points for Bruno
1. Officers: **current and past**, or current only? Past ones are history (88 of 96 at Bridgepoint Advisers Ltd).
2. The `fundManagedBy` note question raised by D-075: its status and start date are facts, so should they move? (Not today.)

---

## 10. Facts from the news releases (v1, 19 Oct; D-079 to D-090)
Built from Gemini's extractions (`gemini-2.5-pro`, D-084), after every field's quote has been checked against its sentence in code (D-085).

### The trail: fact → sentence → release → website
```
ex:deal/apax-01-d1  a ex:Deal
   ├─ ex:targetName   "Foods Connected" ──note──▶ prov:wasDerivedFrom src:news/apax-01/s01
   │                                             ex:quote       "Foods Connected"
   │                                             ex:extractedBy "gemini-2.5-pro"
   ├─ ex:buyerName    "The Apax Global Impact Fund"      (exactly as written, D-088)
   ├─ ex:sponsorName  "Apax Partners LLP"               (the adviser/manager of the buying funds, D-088)
   ├─ ex:price        "£22m" · ex:dealStatus "agreed"   (price vs valuation, D-086; agreed vs completed, D-087)
   ├─ ex:statedReason "accelerate its next phase of growth"   (one per reason)
   └─ ex:announcedIn  ex:release/apax-01

src:news/apax-01/s01  a ex:SourceRecord ; ex:text "…the exact sentence…" ; ex:inRelease ex:release/apax-01 ;
                      ex:url "https://www.apax.com/news-views/…" ; ex:retrievedAt …
ex:release/apax-01    a ex:Release ; ex:title … ; ex:publishedOn … ; ex:publishedBy ex:sponsor/apax ;
                      ex:obtained "downloaded by the program …" | "saved by hand … (D-082)"
```

### Nodes and arrows
| Node | Arrows (all values as written) |
|---|---|
| `ex:Release` | `title`, `publishedOn` (date), `publishedBy` → Sponsor, `obtained` |
| sentence (`src:news/<id>/sNN`) | `text` (the exact sentence), `inRelease` → Release, plus `url` and `retrievedAt` like any source record |
| `ex:Deal` | `dealKind` (acquisition, investment, add-on, exit, other), `targetName`, `buyerName`, `sponsorName`, `sellerName`, `fundName`, `stake`, `price`, `valuation`, `dealStatus` (agreed, completed), `statedReason`, `adviser` → Adviser, `announcedIn` → Release |
| `ex:Adviser` | `name`, `adviserRole` (financial, legal, other), `advising` |
| `ex:FundClose` | `fundName`, `fundSize`, `closeType` (final, first, other), `closeDate`, `announcedIn` → Release |
| `ex:Mention` | `mentionKind` (person, organisation), `name`, `title`, `organisation`, `mentionedIn` → Release |

### Rules that apply here
- **Every note carries the exact quote and the model** (`ex:quote`, `ex:extractedBy`), so an LLM's reading is never mistaken for the text itself (D-029).
- **"Unknown" is kept, not dropped (D-090):** a required field that failed its check becomes `"unknown"`. It is labelled as made by rule D-090, with `ex:why` on its note.
- **Short sentence IDs** ("s01") are expanded by code when they can only mean this release's sentence (D-089).
- **Names stay as text** (`targetName` and the others). Entity matching links them through separate Match nodes (section 11), so the text is never overwritten.

### Checks (SHACL 8–10)
- Every Release has one title and one sponsor.
- Every Deal has one release, a target and a kind (even if "unknown").
- Every FundClose has one release and a fund name.

## 11. Entity matching: Match nodes (v1, 20 Oct; D-096 to D-108)
Every name in the news (a deal's target, buyer, seller, sponsor or fund; an adviser) gets **one Match node**: a judgement with its own evidence (D-108). The name as written comes from its sentence; everything else is labelled with the rule that made it (D-029).

### Example
```
ex:deal/bridgepoint-06-d1 ──buyerMatch──▶ ex:match/bridgepoint-06-d1-buyer-1  a ex:Match
   ├─ ex:nameAsWritten "Bridgepoint Group plc"   ──note──▶ prov:wasDerivedFrom src:news/bridgepoint-06/s01
   ├─ ex:outcome       "sameEntityAs"            ──note──▶ prov:wasGeneratedBy ex:rule/D-098
   ├─ ex:reason        "the only company with this exact name (after tidying)"
   └─ ex:sameEntityAs  lei:213800KFNMVI8PDZX472  (BRIDGEPOINT GROUP PLC; its ch: twin via D-025)
```

### Outcomes (exactly one per Match; the rules are tried in this order)
| # | When | Outcome | Arrows | Rule |
|---|---|---|---|---|
| 1 | The name is an adviser's | `out-of-scope` | – | D-104 |
| 2 | Exactly one company has the name (a `ch:` + `lei:` pair counts once, D-102) | `sameEntityAs` | `sameEntityAs` → the `lei:` | D-098 |
| 3 | Two or more companies have the name | `ambiguous` | `candidate` → each (none picked) | D-098 |
| 4 | It contains one sponsor's name | `refersToGroup` | `refersToGroup` → `ex:sponsor/…`; `possibleEntity` → each family member, when the name says more than the sponsor's name | D-103 |
| 5 | A family shares its words, but it names no sponsor | `ambiguous` | `candidate` → each | D-103 |
| 6 | An approved label (`config/match_labels.toml`) | `out-of-scope` or `non-entity` | `nonEntityKind` for non-entities | D-099 |
| 7 | Nothing applies | `unresolved` | – | D-096 |

### Arrows from the news nodes
`targetMatch`, `buyerMatch`, `sellerMatch`, `sponsorMatch`, `fundMatch` (from a Deal or FundClose); `adviserMatch` (from an Adviser).

### Check (SHACL 11)
- Every Match has one name as written, one outcome from the fixed list, one reason, and at most one `sameEntityAs` and one `refersToGroup` link.

### Numbers (20 Oct)
253 names: out of scope 144, `refersToGroup` 59, unresolved 30, non-entity 9, `sameEntityAs` 6, ambiguous 5. Quality is measured on a 50-name stratified hand-check (D-107).

