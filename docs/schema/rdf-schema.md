# RDF schema sketch (v1, 18 Oct 2026)

The shape of the RDF graph for the first slice: **GLEIF data only, three sponsors**. Companies House and the news releases are added later, and get their own sections then.

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
