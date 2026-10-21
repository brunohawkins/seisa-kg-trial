"""SUMMARY: The second visualisation (brief: "Bloom plus one other tool, showing
the path from a fact back to its source"). Bloom draws the path in Neo4j; this
draws the same path from the RDF graph, as Mermaid diagrams (a text-to-diagram
tool that GitHub and many viewers render), so both graphs are shown side by side.

Everything is read from data/output/graph.ttl by SPARQL, so the picture is the
graph itself, not a drawing of it:
    fact (a triple) <- its RDF-star note (details: quote, model, dates)
                    -> the source record (web address, fetch time, sentence text)
                       or the rule that made it (our own judgement)
                    -> for a news sentence: its release and the sponsor that published it

Two examples, the same ones as the Bloom scenes:
1. a registry company: Bridgepoint Group plc (its GLEIF and Companies House records);
2. a news deal: Hg's OneStream deal (ex:deal/hg-06-d1).

Output: docs/provenance-rdf.md
Run with: uv run python -m seisa_kg.rdf.provenance_view
"""

# A tidy way of working with file paths.
from pathlib import Path

# The RDF database.
import pyoxigraph as ox

# The RDF graph's file and our short prefixes.
from seisa_kg.rdf.build import OUTPUT_PATH, PREFIXES

# The project's top folder.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
# The page this writes.
OUT_PATH = PROJECT_ROOT / "docs" / "provenance-rdf.md"
# Our vocabulary's address.
EX = PREFIXES["ex"]
# The registry example: Bridgepoint Group plc's GLEIF record, and which of its facts to draw (kept to a readable few).
COMPANY = "https://seisa-kg.example/lei/213800KFNMVI8PDZX472"
# Facts from a source, facts from our rules, and a name with dates on its note.
COMPANY_FACTS = ("legalName", "jurisdiction", "statusGroup", "sameEntityAs", "previousName")
# The news example: Hg's OneStream deal, and which of its facts to draw.
DEAL = "https://seisa-kg.example/def/deal/hg-06-d1"
# Its target, its kind, and its status.
DEAL_FACTS = ("targetName", "dealKind", "dealStatus")


# A short, readable name for a term: our prefix form, cut to a length.
def short(term, limit: int = 60) -> str:
    # A literal: its text.
    text = term.value
    # A named node: our prefix form if we have one.
    if isinstance(term, ox.NamedNode):
        # Each prefix, longest address first.
        for prefix, base in sorted(PREFIXES.items(), key=lambda kv: -len(kv[1])):
            # This one fits.
            if text.startswith(base):
                # The short form.
                text = f"{prefix}:{text[len(base):]}"
                # Stop looking.
                break
    # Cut long text, and make it safe inside a Mermaid label (no double quotes or angle brackets).
    text = text if len(text) <= limit else text[:limit - 1] + "…"
    # Safe characters only.
    return text.replace('"', "'").replace("<", "‹").replace(">", "›")


# Draw one subject's chosen facts back to their sources, as Mermaid lines. Returns the lines.
def diagram(store: ox.Store, subjects: list[str], predicates: tuple, prefix: str) -> list[str]:
    # A left-to-right flowchart.
    L = ["```mermaid", "flowchart LR"]
    # Every node drawn so far (so a shared record or rule is drawn once).
    drawn = set()
    # A Mermaid node id for any term.
    ids = {}
    # Give a term a short id, e.g. "r3".
    nid = lambda key, kind: ids.setdefault(key, f"{prefix}{kind}{len(ids)}")
    # The two provenance links a note can have.
    HOW = ("http://www.w3.org/ns/prov#wasDerivedFrom", "http://www.w3.org/ns/prov#wasGeneratedBy")
    # Each subject.
    for s in subjects:
        # Each chosen fact about it, every note on it, and everything each note says (one query, so a note's blank
        # node keeps one identity; its label can't be put back into another query, where SPARQL reads it as a wildcard).
        q = f"""SELECT ?p ?o ?note ?k ?v WHERE {{ VALUES ?s {{ <{s}> }} ?s ?p ?o .
                FILTER (?p IN ({", ".join(f"<{EX}{p}>" for p in predicates)}))
                ?note <http://www.w3.org/1999/02/22-rdf-syntax-ns#reifies> <<( ?s ?p ?o )>> ; ?k ?v .
                FILTER (?k != <http://www.w3.org/1999/02/22-rdf-syntax-ns#reifies>) }} ORDER BY ?p ?o"""
        # Notes in order: note -> (its fact's predicate and value, its (property, value) pairs).
        notes = {}
        # Each row.
        for r in store.query(q):
            # Group the note's properties under the note.
            notes.setdefault(str(r["note"]), (r["p"], r["o"], []))[2].append((r["k"], r["v"]))
        # Each note.
        for key, (pred, obj, pairs) in notes.items():
            # The fact's box: subject, predicate, value.
            fact = nid(f"{s}|{pred.value}|{obj.value}", "f")
            # Drawn once.
            if fact not in drawn:
                # A rectangle with the triple in it.
                L.append(f'  {fact}["{short(ox.NamedNode(s), 30)}<br/>{short(pred)}<br/>{short(obj, 45)}"]')
                # Remember it.
                drawn.add(fact)
            # The note's own id.
            note = nid(key, "n")
            # Its details: everything except where the fact came from.
            details = [f"{short(k)}: {short(v, 40)}" for k, v in pairs if k.value not in HOW]
            # The note as a rounded box, with its details.
            L.append(f'  {note}("RDF-star note' + "".join(f"<br/>{d}" for d in details) + '")')
            # The note points at the fact (rdf:reifies).
            L.append(f"  {note} -- reifies --> {fact}")
            # Where the fact came from: a source record, or one of our rules.
            for how, src in ((k, v) for k, v in pairs if k.value in HOW):
                # The record's or rule's node.
                origin = nid(src.value, "s")
                # The arrow from the note, named by how (derived from a record, or generated by a rule).
                L.append(f"  {note} -- {short(how)} --> {origin}")
                # Drawn once.
                if origin in drawn:
                    # Already drawn.
                    continue
                # Remember it.
                drawn.add(origin)
                # A rule: its label.
                if "/rule/" in src.value:
                    # The rule's label.
                    label = next(iter(store.query(f"SELECT ?l WHERE {{ <{src.value}> <http://www.w3.org/2000/01/rdf-schema#label> ?l }}")), None)
                    # A hexagon for our own judgement.
                    L.append(f'  {origin}{{{{"{short(src)}<br/>{short(label["l"], 50) if label else ""}"}}}}')
                    # Next origin.
                    continue
                # A source record: its web address, fetch time, sentence text and release, where it has them.
                info = {short(i["k"]): i["v"] for i in store.query(f"SELECT ?k ?v WHERE {{ <{src.value}> ?k ?v }}")}
                # Its box: id, then what it says about itself.
                lines = [short(src), f"url: {short(info['ex:url'], 50)}" if "ex:url" in info else "",
                         # When it was fetched.
                         f"fetched: {info['ex:retrievedAt'].value[:10]}" if "ex:retrievedAt" in info else "",
                         # A sentence's own words.
                         f"text: {short(info['ex:text'], 50)}" if "ex:text" in info else ""]
                # A record as a box with a double border.
                L.append(f'  {origin}[["' + "<br/>".join(x for x in lines if x) + '"]]')
                # A news sentence: its release, and who published the release.
                if "ex:inRelease" in info:
                    # The release's node.
                    rel = nid(info["ex:inRelease"].value, "s")
                    # The sentence is in the release.
                    L.append(f"  {origin} -- inRelease --> {rel}")
                    # Drawn once.
                    if rel not in drawn:
                        # Remember it.
                        drawn.add(rel)
                        # The release's publisher.
                        pub = next(iter(store.query(f"SELECT ?sp WHERE {{ <{info['ex:inRelease'].value}> <{EX}publishedBy> ?sp }}")), None)
                        # The release's box.
                        L.append(f'  {rel}["{short(info["ex:inRelease"])}"]')
                        # And who published it.
                        if pub:
                            # The sponsor's node.
                            sp = nid(pub["sp"].value, "s")
                            # The arrow.
                            L.append(f'  {rel} -- publishedBy --> {sp}["{short(pub["sp"])}"]')
    # Close the diagram.
    return L + ["```"]


# Write the page with both diagrams.
def main() -> None:
    # Load the graph.
    store = ox.Store()
    # From the saved file.
    store.bulk_load(path=str(OUTPUT_PATH), format=ox.RdfFormat.TURTLE)
    # The Companies House record our rule D-025 links to the GLEIF one.
    ch = [r["c"].value for r in store.query(f"SELECT ?c WHERE {{ <{COMPANY}> <{EX}sameEntityAs> ?c }}")]
    # The page's opening.
    L = ["# Fact to source, drawn from the RDF graph (generated by `uv run python -m seisa_kg.rdf.provenance_view`)", "",
         "The second visualisation (the first is Neo4j Bloom: `docs/images/`). Every box below is read from `data/output/graph.ttl` by SPARQL.",
         "Read each arrow from the RDF-star note: the note **reifies** (points at) the fact, and says where the fact came from: "
         "**wasDerivedFrom** a source record (with its web address and fetch time), or **wasGeneratedBy** one of our rules (D-029).", "",
         "## 1. A registry company: Bridgepoint Group plc (GLEIF and Companies House)", "",
         "The same name is stated by GLEIF on two fetch dates, so that one fact has two notes (D-042). "
         "The status group and the GLEIF–Companies House link are our own judgements, so their notes point to a rule. "
         "A previous name carries its dates on its note.", ""]
    # The registry diagram: the GLEIF record and the Companies House record.
    L += diagram(store, [COMPANY] + ch, COMPANY_FACTS, "a")
    # The news example's heading.
    L += ["", "## 2. A news fact: Hg's OneStream deal", "",
          "Each fact's note carries the exact quote and the model that extracted it; the note points to the sentence, "
          "the sentence to its release, and the release to the sponsor that published it.", ""]
    # The news diagram.
    L += diagram(store, [DEAL], DEAL_FACTS, "b")
    # Save it.
    OUT_PATH.write_text("\n".join(L) + "\n", encoding="utf-8")
    # Say where it is.
    print(f"Wrote {OUT_PATH.relative_to(PROJECT_ROOT)}")


# Run main() when this file is run directly.
if __name__ == "__main__":
    # Go.
    main()
