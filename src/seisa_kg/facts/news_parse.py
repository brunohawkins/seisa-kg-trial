"""SUMMARY: Turns the checked Gemini extractions into fact rows (pipeline
stage 2, parse, for the news; D-083).

What it makes:
- A Release node per news release (ex:release/<id>): title, publication
  date, sponsor, address, and how it was obtained (by the program, or saved
  by hand, D-082).
- A source record per sentence (src:news/<id>/sNN), holding the sentence's
  exact text and the release it belongs to. Every news fact points to one.
- A Deal, FundClose or Mention node per extracted item, with each field as
  a fact. Names stay as written (matching comes later).
- Each fact's note (RDF-star) points to its sentence (prov:wasDerivedFrom)
  and carries the exact quote and the model that extracted it, so an LLM's
  output is never mistaken for the text itself (D-029).

Trail: fact → sentence → release → the sponsor's website.
"""

# Reads the extracted files and the sentence files.
import json
# A tidy way of working with file and folder paths.
from pathlib import Path

# The shared fact format.
from seisa_kg.facts.model import PROJECT_ROOT, fact, iri, literal

# The numbered sentences, one file per release.
NEWS_DIR = PROJECT_ROOT / "data" / "interim" / "news"
# The checked extractions, one folder per model.
EXTRACTED_DIR = PROJECT_ROOT / "data" / "interim" / "extracted"
# The model whose extractions go into the graph (D-084; one setting).
GRAPH_MODEL = "gemini-2.5-pro"
# Each extracted field name, and the predicate it becomes in the graph.
PREDICATES = {"kind": "dealKind", "target": "targetName", "buyers": "buyerName", "sellers": "sellerName", "funds": "fundName",
              # The rest of a deal.
              "stake": "stake", "price": "price", "valuation": "valuation", "status": "dealStatus", "reasons": "statedReason", "sponsor": "sponsorName",
              # A fund close.
              "fund_name": "fundName", "size": "fundSize", "close_type": "closeType", "date": "closeDate",
              # A mention or an adviser.
              "name": "name", "title": "title", "organisation": "organisation", "role": "adviserRole", "advising": "advising"}


# The origin block for one sentence (D-035): the sentence is the source record.
def sentence_origin(doc: dict, sid: str) -> dict:
    # e.g. "hg-01#s04" -> "src:news/hg-01/s04".
    record = "src:news/" + sid.replace("#", "/")
    # The record, the source, and the release's address and fetch (or save) time.
    return {"kind": "source", "record": record, "source": "News", "url": doc["url"], "retrieved_at": doc["retrieved_at"]}


# The facts for one extracted field (or list of fields) on a node.
def field_rows(node: str, name: str, value, doc: dict, model: str) -> list[dict]:
    # A list of fields: one row each.
    if isinstance(value, list):
        # Flatten the rows of each item.
        return [r for v in value for r in field_rows(node, name, v, doc, model)]
    # A missing field: no rows.
    if not value:
        # Nothing.
        return []
    # An explicit "unknown" (D-090): our judgement, saying why, not a quote from the text.
    if value.get("sid") is None:
        # Labelled as made by rule D-090, with the reason on its note.
        return [fact(node, PREDICATES[name], literal("unknown"), {"kind": "rule", "rule": "D-090"}, {"why": literal(value.get("why", ""))})]
    # One fact: the value as written, from its sentence, with the quote and the model on its note.
    return [fact(node, PREDICATES[name], literal(value["value"]), sentence_origin(doc, value["sid"]),
                 # The note's details: the exact quote and who extracted it.
                 {"quote": literal(value["quote"]), "extractedBy": literal(model)})]


# Turn one release's checked extraction into rows.
def release_rows(doc: dict, ext: dict, model: str) -> list[dict]:
    # The release's node.
    rel = f"ex:release/{doc['id']}"
    # The release's own source record (the page as a whole).
    org = {"kind": "source", "record": f"src:news/{doc['id']}", "source": "News", "url": doc["url"], "retrieved_at": doc["retrieved_at"]}
    # "This is a release", its title, sponsor and how it was obtained.
    rows = [fact(rel, "type", iri("ex:Release"), org), fact(rel, "title", literal(doc["title"]), org),
            # The sponsor whose website it came from, and how it was obtained (D-082).
            fact(rel, "publishedBy", iri(f"ex:sponsor/{doc['sponsor']}"), org), fact(rel, "obtained", literal(doc["obtained"]), org)]
    # The publication date, if known.
    if doc.get("published"):
        # A proper date.
        rows.append(fact(rel, "publishedOn", literal(doc["published"], "date"), org))
    # Each sentence: its exact text and its release, recorded on the sentence's own source record.
    for s in doc["sentences"]:
        # The sentence's origin (itself).
        so = sentence_origin(doc, s["sid"])
        # Its text and its release.
        rows += [fact(so["record"], "text", literal(s["text"]), so), fact(so["record"], "inRelease", iri(rel), so)]
    # Each deal.
    for i, d in enumerate(ext["deals"], start=1):
        # The deal's node.
        node = f"ex:deal/{doc['id']}-d{i}"
        # The sentence that best anchors the deal: its target's, or its kind's, or the release's first.
        anchor = d["target"]["sid"] or d["kind"]["sid"] or doc["sentences"][0]["sid"]
        # "This is a deal" and its release, sourced to that sentence.
        rows += [fact(node, "type", iri("ex:Deal"), sentence_origin(doc, anchor)),
                 # Which release announced it.
                 fact(node, "announcedIn", iri(rel), sentence_origin(doc, anchor))]
        # Each field except the advisers.
        for name in ("kind", "target", "buyers", "sponsor", "sellers", "funds", "stake", "price", "valuation", "status", "reasons"):
            # Its rows.
            rows += field_rows(node, name, d.get(name), doc, model)
        # Each adviser: its own node (several parts: name, role, client; D-036).
        for k, a in enumerate(d.get("advisers", []), start=1):
            # The adviser's node.
            adv = f"ex:adviser/{doc['id']}-d{i}-a{k}"
            # The link from the deal, and the adviser's type, from the sentence that names it.
            rows += [fact(node, "adviser", iri(adv), sentence_origin(doc, a["name"]["sid"])), fact(adv, "type", iri("ex:Adviser"), sentence_origin(doc, a["name"]["sid"]))]
            # Its name, role and client.
            for name in ("name", "role", "advising"):
                # Their rows.
                rows += field_rows(adv, name, a.get(name), doc, model)
    # Each fund close.
    for i, fc in enumerate(ext["fund_closes"], start=1):
        # The fund close's node.
        node = f"ex:fundclose/{doc['id']}-f{i}"
        # "This is a fund close" and its release.
        rows += [fact(node, "type", iri("ex:FundClose"), sentence_origin(doc, fc["fund_name"]["sid"])), fact(node, "announcedIn", iri(rel), sentence_origin(doc, fc["fund_name"]["sid"]))]
        # Its fields.
        for name in ("fund_name", "size", "close_type", "date"):
            # Their rows.
            rows += field_rows(node, name, fc.get(name), doc, model)
    # Each mention.
    for i, m in enumerate(ext["mentions"], start=1):
        # The mention's node.
        node = f"ex:mention/{doc['id']}-m{i}"
        # "This is a mention", its kind (person or organisation) and its release.
        rows += [fact(node, "type", iri("ex:Mention"), sentence_origin(doc, m["name"]["sid"])), fact(node, "mentionKind", literal(m["kind"]), sentence_origin(doc, m["name"]["sid"])),
                 # Which release names it.
                 fact(node, "mentionedIn", iri(rel), sentence_origin(doc, m["name"]["sid"]))]
        # Its fields.
        for name in ("name", "title", "organisation"):
            # Their rows.
            rows += field_rows(node, name, m.get(name), doc, model)
    # Hand back the rows.
    return rows


# Parse every release that has a checked extraction for the graph's model. Returns the rows.
def parse_all(model: str = GRAPH_MODEL) -> list[dict]:
    # The rows.
    rows = []
    # Each checked extraction for this model.
    for path in sorted((EXTRACTED_DIR / model).glob("*.json")):
        # The extraction.
        ext = json.loads(path.read_text(encoding="utf-8"))
        # Its release's sentences and provenance.
        doc = json.loads((NEWS_DIR / path.name).read_text(encoding="utf-8"))
        # Its rows.
        rows += release_rows(doc, ext, model)
    # The rule behind every "unknown" (D-090), so a reader can see what it says.
    if any(r["origin"].get("rule") == "D-090" for r in rows):
        # "This is a rule", and its label.
        rows += [fact("ex:rule/D-090", "type", iri("ex:Rule"), {"kind": "rule", "rule": "D-090"}),
                 # Its plain-English label.
                 fact("ex:rule/D-090", "label", literal("A required field that failed the quote check is kept as unknown, saying why"), {"kind": "rule", "rule": "D-090"})]
    # Hand back the rows.
    return rows
