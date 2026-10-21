"""SUMMARY: The three-way comparison (brief §6; settings in D-124). Each
investor question that has a hand-written answer key (data/output/answers/rdf/)
is answered three ways, from the plain-English question alone:

1. text-to-SPARQL: Gemini writes a SPARQL query from the RDF phrasebook;
2. text-to-Cypher: Gemini writes a Cypher query from the Neo4j phrasebook;
3. vector search: the question is embedded, the 5 closest news sentences are
   found, and Gemini answers from those 5 sentences only.

The model proposes, the code checks (as in extraction, D-085):
- a generated query is rejected if it uses a blocked word (anything that could
  write or reach outside) or a name that doesn't exist in our graph; then it runs
  read-only (Oxigraph's query call can't write; Neo4j runs it in a read
  transaction), with a 10-second limit. No retries: the first attempt is scored.
- vector search's citations are kept only if they are among the 5 sentences it
  was given.

Every answer is scored by evaluation/score.py against the answer key, the same
way for all three. Every Gemini call is cached by a fingerprint of exactly what
was sent, so re-running costs nothing.

Outputs: data/output/comparison/<method>/<question>.json (each attempt in full)
and docs/comparison.md (the table, every failure with its reason, every query).

Run with: make compare   (Neo4j must be running)
"""

# Encodes the cached sentence vectors compactly.
import base64
# Makes the prompt fingerprints.
import hashlib
# Reads and writes JSON.
import json
# Square roots, for vector lengths.
import math
# Runs each SPARQL query in a separate process, so a runaway query can be stopped.
import multiprocessing as mp
# Reads the API key from the environment.
import os
# Pattern matching, for the checks.
import re
# Times each step.
import time
# A compact list of floating-point numbers (a sentence vector).
from array import array
# Asks Gemini several things at once.
from concurrent.futures import ThreadPoolExecutor
# Stamps each cached answer with the time it was made.
from datetime import datetime, timezone
# A tidy way of working with file paths.
from pathlib import Path

# The RDF database.
import pyoxigraph as ox
# Loads the secret values in .env into the environment.
from dotenv import load_dotenv
# Google's library for Gemini.
from google import genai
# Google's settings types for a request.
from google.genai import types
# Neo4j's read-only mode and transaction time limit.
from neo4j import READ_ACCESS, unit_of_work
# Declares the shape of a generated-query answer.
from pydantic import BaseModel

# The answer scorer, and how it recognises a web address.
from seisa_kg.evaluation.score import URL, score
# Turns a Neo4j value into text the way the answer key writes it.
from seisa_kg.lpg.ask import plain as neo4j_text
# The connection to Neo4j.
from seisa_kg.lpg.build import connect
# The answer keys' folder.
from seisa_kg.rdf.ask import ANSWERS_DIR as KEY_DIR
# The RDF graph's file and our prefixes.
from seisa_kg.rdf.build import OUTPUT_PATH, PREFIXES

# The project's top folder.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
# Where the phrasebooks and each attempt are saved.
OUT_DIR = PROJECT_ROOT / "data" / "output" / "comparison"
# Gemini's cached answers and the cached sentence vectors (a download like any other).
CACHE_DIR = PROJECT_ROOT / "data" / "raw" / "llm" / "comparison"
# The numbered news sentences, one file per release.
NEWS_DIR = PROJECT_ROOT / "data" / "interim" / "news"
# The readable report.
REPORT_PATH = PROJECT_ROOT / "docs" / "comparison.md"
# The translator and answerer (decision 1: the same pinned model as extraction).
MODEL = "gemini-2.5-pro"
# The embedding model (decision 7).
EMBED_MODEL = "gemini-embedding-001"
# How many sentences vector search hands to Gemini (decision 7).
TOP_K = 5
# Seconds a generated query may run (decision 9).
TIME_LIMIT = 10
# How many Gemini requests at once.
PARALLEL = 4
# Our vocabulary's address.
EX = PREFIXES["ex"]
# The three methods, in report order.
METHODS = ("text-to-SPARQL", "text-to-Cypher", "vector search")

# The SPARQL words the translator may use (decision 3, Bruno's idea).
SPARQL_ALLOWED = ("PREFIX, SELECT, DISTINCT, WHERE, OPTIONAL, FILTER, BIND, VALUES, UNION, MINUS, EXISTS, NOT EXISTS, "
                  "GROUP BY, HAVING, ORDER BY, LIMIT, AS, COUNT, SUM, MIN, MAX, AVG, SAMPLE, GROUP_CONCAT, STR, LCASE, "
                  "UCASE, CONTAINS, STRSTARTS, STRAFTER, REGEX, COALESCE, IF, BOUND, isIRI, isLITERAL, DATATYPE, <<( )>>")
# SPARQL words that could change the graph or reach outside it.
SPARQL_BLOCKED = ("INSERT", "DELETE", "LOAD", "CLEAR", "DROP", "CREATE", "ADD", "MOVE", "COPY", "SERVICE", "WITH")
# The Cypher words the translator may use.
CYPHER_ALLOWED = ("MATCH, OPTIONAL MATCH, WHERE, WITH, UNWIND, RETURN, DISTINCT, ORDER BY, SKIP, LIMIT, AS, "
                  "CASE WHEN THEN ELSE END, EXISTS { }, COUNT { }, count, collect, sum, min, max, avg, size, range, "
                  "any, all, none, reduce, coalesce, toUpper, toLower, toString, date, labels, type, keys")
# Cypher words that could change the graph or reach outside it.
CYPHER_BLOCKED = ("CREATE", "MERGE", "SET", "DELETE", "DETACH", "REMOVE", "FOREACH", r"LOAD\s+CSV", "CALL", "USE", "DROP")


# The shape Gemini must reply in when it writes a query.
class Generated(BaseModel):
    # The query, or "" if it says the graph can't answer.
    query: str
    # True if it says the graph can't answer the question (decision 8).
    not_found: bool


# The rules for a translator, for one language.
def translator_rules(language: str, allowed: str, blocked: tuple, phrasebook_kind: str) -> str:
    # The instruction text.
    return f"""You translate an investor's question into ONE read-only {language} query over the graph described in the {phrasebook_kind} phrasebook.
Rules:
1. Use only these words and functions: {allowed}. Never use: {", ".join(b.replace(r"\s+", " ") for b in blocked)}.
2. Use only the names (prefixes, types, labels, predicates, relationship types, properties) listed in the phrasebook. Never invent a name.
3. Return exactly the columns asked for, in that order, named exactly as given.
4. Every row must cite its sources in its source column(s): a registry fact by its record's web address (url), a news fact by its sentence record id (e.g. src:news/hg-06/s03). Put several sources in one cell, separated by spaces.
5. If the graph cannot answer the question, set not_found to true and leave query empty.
Reply as JSON: {{"query": "...", "not_found": false}}."""


# The rules for answering from retrieved sentences.
VECTOR_RULES = """You answer an investor's question using ONLY the numbered news sentences given. Use no other knowledge.
Reply as JSON: {"not_found": false, "rows": [{"<column>": "<value>", ...}, ...]}, with exactly the columns asked for, named exactly as given.
In the source column(s), cite the ids of the sentences that state each row (e.g. src:news/hg-06/s03), several separated by spaces.
If the sentences don't answer the question, reply {"not_found": true, "rows": []}."""


# Ask Gemini (or read its cached answer); returns the saved record with the answer text, tokens and time.
def ask_gemini(client: genai.Client, method: str, qid: str, system: str, prompt: str, schema=None) -> dict:
    # A fingerprint of exactly what is sent, so a changed prompt never reuses an old answer.
    fingerprint = hashlib.sha256((MODEL + system + prompt).encode("utf-8")).hexdigest()[:16]
    # Where this answer is cached.
    cache = CACHE_DIR / method.replace(" ", "-") / f"{qid}.json"
    # Reuse it if it was made from exactly the same prompt.
    if cache.exists():
        # The saved answer.
        saved = json.loads(cache.read_text(encoding="utf-8"))
        # Same prompt: reuse it.
        if saved["fingerprint"] == fingerprint:
            # Hand it back.
            return saved
    # The request's settings: our rules, JSON out (in a fixed shape if given), no randomness.
    config = types.GenerateContentConfig(system_instruction=system, response_mime_type="application/json",
                                         response_schema=schema, temperature=0)
    # Start the clock.
    start = time.perf_counter()
    # Send it.
    response = client.models.generate_content(model=MODEL, contents=prompt, config=config)
    # The record: the answer with its provenance (model, time, cost).
    saved = {"method": method, "question": qid, "model": MODEL, "asked_at": datetime.now(timezone.utc).isoformat(),
             # The fingerprint, the time taken and the token counts.
             "fingerprint": fingerprint, "seconds": round(time.perf_counter() - start, 1),
             # Input tokens.
             "input_tokens": response.usage_metadata.prompt_token_count,
             # Output tokens, including any thinking.
             "output_tokens": (response.usage_metadata.candidates_token_count or 0) + (response.usage_metadata.thoughts_token_count or 0),
             # Gemini's answer, as text.
             "answer": response.text or ""}
    # Make sure the folder exists.
    cache.parent.mkdir(parents=True, exist_ok=True)
    # Save it.
    cache.write_text(json.dumps(saved, ensure_ascii=False, indent=1), encoding="utf-8")
    # Hand it back.
    return saved


# Remove string literals, full IRIs and comments from a query, so the word checks only see the query's own words.
def strip_query(query: str, comment: str) -> str:
    # Full IRIs in angle brackets (they may contain "#" or words like "delete").
    text = re.sub(r"<[^<>\s]*>", "<>", query)
    # Text in double or single quotes.
    text = re.sub(r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'', '""', text)
    # Comments to the end of the line.
    return re.sub(comment + r"[^\n]*", "", text)


# Check a generated query: a blocked word, or a name our graph doesn't have. Returns the problem, or None if it passes.
def check_query(query: str, blocked: tuple, comment: str, unknown_names) -> str | None:
    # The query without strings, IRIs and comments.
    words = strip_query(query, comment)
    # Each blocked word.
    for word in blocked:
        # Found as a whole word, in any case.
        if re.search(rf"\b{word}\b", words, re.IGNORECASE):
            # Rejected.
            return f"blocked word: {word.replace(chr(92) + 's+', ' ')}"
    # Any name that doesn't exist in our graph.
    missing = unknown_names(query, words)
    # Rejected if there are any.
    return f"made-up name(s): {', '.join(sorted(missing))}" if missing else None


# Every name under our vocabulary's address in the RDF graph (types, predicates, sponsors, rules, ...).
def rdf_known_names(store: ox.Store) -> set[str]:
    # Any IRI in any position that starts with our vocabulary's address.
    q = f"""SELECT DISTINCT ?x WHERE {{ {{ ?x ?p ?o }} UNION {{ ?s ?x ?o }} UNION {{ ?s ?p ?x }}
            FILTER (isIRI(?x) && STRSTARTS(STR(?x), "{EX}")) }}"""
    # Their local names, e.g. "fundManagedBy", "sponsor/apax".
    return {r["x"].value[len(EX):] for r in store.query(q)}


# The names a SPARQL query uses under our vocabulary that the graph doesn't have.
def sparql_unknown(known: set[str]):
    # The check, for one query.
    def unknown(query: str, words: str) -> set[str]:
        # Short names like ex:fundManagedBy (a "\/" escape means "/").
        used = {m.replace("\\/", "/") for m in re.findall(r"\bex:((?:[A-Za-z0-9_\-]|\\/)+)", words)}
        # Full IRIs under our vocabulary, e.g. <https://seisa-kg.example/def/sponsor/apax>.
        used |= set(re.findall(re.escape("<" + EX) + r"([^>]+)>", query))
        # Those our graph doesn't have.
        return {"ex:" + u for u in used if u not in known}
    # Hand back the check.
    return unknown


# The names a Cypher query uses (labels, relationship types, properties) that the graph doesn't have.
def cypher_unknown(labels_and_types: set[str], properties: set[str]):
    # The check, for one query.
    def unknown(query: str, words: str) -> set[str]:
        # Labels and relationship types: a capitalised name after a colon, e.g. (:Company) or [:FUND_MANAGED_BY].
        used = {f":{n}" for n in re.findall(r":\s*`?([A-Z][A-Za-z0-9_]*)", words) if n not in labels_and_types}
        # Properties: a name after "variable.", e.g. c.legalName.
        used |= {f".{p}" for p in re.findall(r"\b[a-z_][A-Za-z0-9_]*\.([A-Za-z_][A-Za-z0-9_]*)", words) if p not in properties}
        # Those our graph doesn't have.
        return used
    # Hand back the check.
    return unknown


# Turn one RDF answer value into plain text (as the answer key writes it).
def rdf_text(term) -> str:
    # A missing value (OPTIONAL found nothing).
    if term is None:
        # Empty.
        return ""
    # A quoted triple has no single value; write it out.
    if isinstance(term, ox.Triple):
        # Its text form.
        return str(term)
    # Anything else: its value.
    return term.value


# Run one SPARQL query in a child process: load the graph, say so, run the query, send the result back.
def sparql_child(query: str, conn) -> None:
    # Load the graph.
    store = ox.Store()
    # From the saved file.
    store.bulk_load(path=str(OUTPUT_PATH), format=ox.RdfFormat.TURTLE)
    # Tell the parent the clock can start.
    conn.send(("loaded",))
    # Run it, catching any error (a syntax error, a wrong kind of query).
    try:
        # Start the clock.
        start = time.perf_counter()
        # Run the query (Oxigraph's query call can only read).
        result = store.query(query)
        # Only a SELECT gives rows.
        if not isinstance(result, ox.QuerySolutions):
            # Not a table.
            conn.send(("error", "not a SELECT query"))
            # Stop.
            return
        # The column names.
        columns = [v.value for v in result.variables]
        # Every row, as text.
        rows = [{c: rdf_text(r[c]) for c in columns} for r in result]
        # Send them back, with the time in milliseconds.
        conn.send(("ok", columns, rows, round((time.perf_counter() - start) * 1000, 1)))
    # Any error.
    except Exception as e:
        # Send its message back.
        conn.send(("error", f"{type(e).__name__}: {str(e)[:300]}"))


# Run a SPARQL query with the time limit; returns ("ok", columns, rows, ms) or (problem text,).
def run_sparql(query: str) -> tuple:
    # A two-way pipe to the child.
    parent, child = mp.Pipe()
    # The child process.
    proc = mp.Process(target=sparql_child, args=(query, child), daemon=True)
    # Start it.
    proc.start()
    # Wait for it to load the graph (a minute at most).
    if not parent.poll(60) or parent.recv()[0] != "loaded":
        # Stop it.
        proc.terminate()
        # Say what happened.
        return ("could not load the graph",)
    # Wait for the answer, up to the time limit.
    if not parent.poll(TIME_LIMIT):
        # Too slow: stop it.
        proc.terminate()
        # Say so.
        return (f"timeout: over {TIME_LIMIT} s",)
    # The answer.
    msg = parent.recv()
    # Tidy up the process.
    proc.join(1)
    # A result, or an error message.
    return msg if msg[0] == "ok" else (msg[1],)


# Run a Cypher query read-only with the time limit; returns ("ok", columns, rows, ms) or (problem text,).
def run_cypher(driver, query: str) -> tuple:
    # The unit of work, with Neo4j's own time limit.
    @unit_of_work(timeout=TIME_LIMIT)
    # Run the query and read every row.
    def work(tx):
        # Run it.
        result = tx.run(query)
        # Every record, and the column names.
        records = list(result)
        # Hand them back.
        return list(result.keys()), records
    # Catch any error (syntax, a write attempt, the time limit).
    try:
        # Start the clock.
        start = time.perf_counter()
        # A read-only session: Neo4j refuses any write in it.
        with driver.session(default_access_mode=READ_ACCESS) as session:
            # Run the unit of work as a read transaction.
            columns, records = session.execute_read(work)
        # The rows as text, and the time in milliseconds.
        return ("ok", columns, [{c: neo4j_text(r[c]) for c in columns} for r in records], round((time.perf_counter() - start) * 1000, 1))
    # Any error.
    except Exception as e:
        # Its message.
        return (f"{type(e).__name__}: {str(e)[:300]}",)


# Every news sentence, as (id, text), e.g. ("src:news/hg-06/s03", "Hg will acquire ...").
def news_sentences() -> list[tuple[str, str]]:
    # The sentences found.
    out = []
    # Each release file.
    for path in sorted(NEWS_DIR.glob("*.json")):
        # Each sentence: "hg-06#s03" becomes "src:news/hg-06/s03".
        out += [("src:news/" + s["sid"].replace("#", "/"), s["text"]) for s in json.loads(path.read_text(encoding="utf-8"))["sentences"]]
    # Hand them back.
    return out


# Embed texts with Gemini, in batches of 100; returns one vector per text.
def embed(client: genai.Client, texts: list[str], task: str) -> list[list[float]]:
    # The vectors.
    vectors = []
    # Each batch.
    for i in range(0, len(texts), 100):
        # Ask for this batch's vectors.
        result = client.models.embed_content(model=EMBED_MODEL, contents=texts[i:i + 100],
                                             config=types.EmbedContentConfig(task_type=task))
        # Keep them.
        vectors += [e.values for e in result.embeddings]
    # Hand them back.
    return vectors


# The sentence vectors: from the cache if the sentences haven't changed, otherwise embedded now and cached.
def sentence_vectors(client: genai.Client, sentences: list[tuple[str, str]]) -> list[list[float]]:
    # A fingerprint of the model and every sentence.
    fingerprint = hashlib.sha256((EMBED_MODEL + "".join(i + t for i, t in sentences)).encode("utf-8")).hexdigest()[:16]
    # Where they are cached.
    cache = CACHE_DIR / "embeddings" / f"{EMBED_MODEL}.json"
    # Reuse them if the sentences are the same.
    if cache.exists():
        # The saved vectors.
        saved = json.loads(cache.read_text(encoding="utf-8"))
        # Same sentences: decode and hand back.
        if saved["fingerprint"] == fingerprint:
            # Each vector, from its compact form.
            return [list(array("f", base64.b64decode(v))) for v in saved["vectors"]]
    # Embed every sentence as a document to be searched.
    vectors = embed(client, [t for _, t in sentences], "RETRIEVAL_DOCUMENT")
    # Make sure the folder exists.
    cache.parent.mkdir(parents=True, exist_ok=True)
    # Save them compactly (4 bytes per number).
    cache.write_text(json.dumps({"model": EMBED_MODEL, "fingerprint": fingerprint, "ids": [i for i, _ in sentences],
                                 # Each vector as base64 text.
                                 "vectors": [base64.b64encode(array("f", v).tobytes()).decode() for v in vectors]}), encoding="utf-8")
    # Hand them back.
    return vectors


# A question's vector: from the cache if this exact question was embedded before, otherwise embedded now and cached.
def question_vector(client: genai.Client, question: str) -> list[float]:
    # The cache file: question text -> vector, for this model.
    cache = CACHE_DIR / "embeddings" / f"{EMBED_MODEL}-questions.json"
    # The saved vectors so far.
    saved = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else {}
    # Not embedded yet: embed it as a search query and save it.
    if question not in saved:
        # Embed.
        saved[question] = embed(client, [question], "RETRIEVAL_QUERY")[0]
        # Make sure the folder exists.
        cache.parent.mkdir(parents=True, exist_ok=True)
        # Save.
        cache.write_text(json.dumps(saved), encoding="utf-8")
    # Hand it back.
    return saved[question]


# The cosine similarity of two vectors: 1 means the same direction (the same meaning, roughly).
def cosine(a: list[float], b: list[float]) -> float:
    # Dot product over the two lengths.
    return sum(x * y for x, y in zip(a, b)) / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


# Turn one value from Gemini's JSON answer into text.
def as_text(value) -> str:
    # A list (e.g. several sources): space-separated.
    if isinstance(value, list):
        # Each item as text.
        return " ".join(as_text(v) for v in value)
    # Missing: empty.
    return "" if value is None else str(value)


# Registry records' ids and web addresses, both ways, so a citation by either form counts (not news sentences).
def record_addresses(store: ox.Store) -> dict[str, set[str]]:
    # Each record's id and web address.
    q = f"SELECT ?r ?u WHERE {{ ?r a <{EX}SourceRecord> ; <{EX}url> ?u }}"
    # Id -> addresses and address -> ids.
    pairs = {}
    # Each record.
    for r in store.query(q):
        # Its short id, e.g. "src:gleif/.../20261018".
        rid = "src:" + r["r"].value[len(PREFIXES["src"]):]
        # News sentences cite themselves, not the release's address.
        if rid.startswith("src:news/"):
            # Skip.
            continue
        # Both directions.
        pairs.setdefault(rid, set()).add(r["u"].value)
        # The address maps back to every record fetched from it.
        pairs.setdefault(r["u"].value, set()).add(rid)
    # Hand them back.
    return pairs


# Add the other form of every cited registry record to a row, so "src:gleif/..." and its web address count alike.
def with_both_forms(row: dict, addresses: dict[str, set[str]]) -> dict:
    # All the row's text.
    text = " ".join(row.values())
    # Record ids cited (short, or written in full) and web addresses cited.
    cited = set(re.findall(r"\bsrc:\S+", text)) | {"src:" + s for s in re.findall(r"https://seisa-kg\.example/source/(\S+)", text)}
    # Plus web addresses.
    cited |= set(URL.findall(text))
    # Their other forms.
    extra = {x for c in cited for x in addresses.get(c, ()) if x not in cited}
    # The row, with the other forms in one extra cell.
    return {**row, "_otherForms": " ".join(sorted(extra))} if extra else row


# Answer one question by text-to-query (SPARQL or Cypher): ask, check, run. Returns the attempt.
def text_to_query(client, method: str, ref: dict, phrasebook: str, rules: str, check, run) -> dict:
    # The question's id, e.g. "q01_apax_fund_managers".
    qid = ref["file"].removesuffix(".rq")
    # The prompt: the phrasebook, the question, and the columns to return.
    prompt = f"{phrasebook}\n\n## Question\n{ref['QUESTION']}\n\n## Columns to return, in this order\n{', '.join(ref['columns'])}\n"
    # Ask Gemini (or read the cached answer).
    asked = ask_gemini(client, method, qid, rules, prompt, Generated)
    # The attempt so far.
    attempt = {"question": qid, "method": method, "seconds": asked["seconds"], "tokens": asked["input_tokens"] + asked["output_tokens"]}
    # Read Gemini's reply.
    try:
        # As the declared shape.
        reply = Generated.model_validate_json(asked["answer"])
    # Not valid JSON in that shape.
    except Exception as e:
        # A failure.
        return {**attempt, "status": f"unreadable reply: {str(e)[:120]}", "rows": []}
    # The generated query, kept for the report.
    attempt["query"] = reply.query
    # It says the graph can't answer.
    if reply.not_found or not reply.query.strip():
        # "Not found" (decision 8).
        return {**attempt, "status": "said not found", "rows": [], "not_found": True}
    # The code checks: blocked words and made-up names.
    problem = check(reply.query)
    # Rejected.
    if problem:
        # A failure, with its reason (no retry, decision 5).
        return {**attempt, "status": f"rejected: {problem}", "rows": []}
    # Run it read-only, with the time limit.
    result = run(reply.query)
    # An error or a timeout.
    if result[0] != "ok":
        # A failure, with its reason.
        return {**attempt, "status": result[0], "rows": []}
    # The rows and the run time.
    return {**attempt, "status": "ran" if result[2] else "ran: no rows", "rows": result[2], "query_ms": result[3]}


# Answer one question by vector search: embed it, take the 5 closest sentences, let Gemini answer from those. Returns the attempt.
def vector_search(client, ref: dict, sentences: list[tuple[str, str]], vectors: list[list[float]]) -> dict:
    # The question's id.
    qid = ref["file"].removesuffix(".rq")
    # Start the clock for retrieval.
    start = time.perf_counter()
    # Embed the question as a search query (cached).
    qvec = question_vector(client, ref["QUESTION"])
    # Every sentence's similarity to the question, closest first.
    ranked = sorted(((cosine(qvec, v), s) for v, s in zip(vectors, sentences)), key=lambda x: -x[0])[:TOP_K]
    # The retrieval time.
    retrieval_ms = round((time.perf_counter() - start) * 1000, 1)
    # The prompt: the question, the columns, and the 5 sentences with their ids.
    prompt = (f"## Question\n{ref['QUESTION']}\n\n## Columns to return, in this order\n{', '.join(ref['columns'])}\n\n"
              # The sentences, each with its id.
              "## Sentences\n" + "\n".join(f"[{sid}] {text}" for _, (sid, text) in ranked) + "\n")
    # Ask Gemini (or read the cached answer).
    asked = ask_gemini(client, "vector search", qid, VECTOR_RULES, prompt)
    # The attempt so far, with what was retrieved and how similar it was.
    attempt = {"question": qid, "method": "vector search", "seconds": asked["seconds"], "tokens": asked["input_tokens"] + asked["output_tokens"],
               # The retrieved sentences and their similarity scores.
               "retrieved": [{"id": sid, "score": round(sc, 3), "text": text} for sc, (sid, text) in ranked], "query_ms": retrieval_ms}
    # Read Gemini's reply.
    try:
        # As JSON.
        reply = json.loads(asked["answer"])
    # Not JSON.
    except Exception as e:
        # A failure.
        return {**attempt, "status": f"unreadable reply: {str(e)[:120]}", "rows": []}
    # It says the sentences don't answer the question.
    if reply.get("not_found") or not reply.get("rows"):
        # "Not found" (decision 8).
        return {**attempt, "status": "said not found", "rows": [], "not_found": True}
    # The ids it was given.
    given = {sid for _, (sid, _) in ranked}
    # How many citations were dropped.
    dropped = 0
    # The rows as text, keeping only citations of sentences it was given.
    rows = []
    # Each row.
    for row in reply["rows"]:
        # Each cell as text.
        cells = {str(k): as_text(v) for k, v in row.items()}
        # Each cell: drop sentence ids it wasn't given (like the quote check).
        for k, v in cells.items():
            # The sentence ids cited in this cell.
            ids = re.findall(r"\bsrc:news/\S+", v)
            # The ones it wasn't given.
            bad = [i for i in ids if i not in given]
            # Count them.
            dropped += len(bad)
            # Remove them.
            for i in bad:
                # Out of the cell.
                v = v.replace(i, "")
            # The cleaned cell.
            cells[k] = " ".join(v.split())
        # Keep the row.
        rows.append(cells)
    # The attempt.
    return {**attempt, "status": "answered" + (f" ({dropped} citation(s) dropped)" if dropped else ""), "rows": rows}


# Run every question through all three methods, score them, and write the report.
def main() -> None:
    # The API key, from .env (never printed).
    load_dotenv(PROJECT_ROOT / ".env")
    # The Gemini client.
    client = genai.Client(api_key=os.environ["LLM_API_KEY"])
    # Every answer key (the hand-written SPARQL answers), in name order.
    refs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(KEY_DIR.glob("q*.json"))]
    # The two phrasebooks.
    book = {k: (OUT_DIR / f"phrasebook-{k}.md").read_text(encoding="utf-8") for k in ("rdf", "lpg")}
    # The RDF graph, for the known names and the records' addresses.
    store = ox.Store()
    # Loaded from the saved file.
    store.bulk_load(path=str(OUTPUT_PATH), format=ox.RdfFormat.TURTLE)
    # Every name our RDF graph has under our vocabulary (worked out once).
    known = rdf_known_names(store)
    # The SPARQL check.
    sparql_check = lambda q: check_query(q, SPARQL_BLOCKED, "#", sparql_unknown(known))
    # The connection to Neo4j.
    driver = connect()
    # Neo4j's labels and relationship types.
    names = {r[0] for r in driver.execute_query("CALL db.labels() YIELD label RETURN label").records}
    # Plus relationship types.
    names |= {r[0] for r in driver.execute_query("CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType").records}
    # Neo4j's property names.
    props = {r[0] for r in driver.execute_query("CALL db.propertyKeys() YIELD propertyKey RETURN propertyKey").records}
    # The Cypher check.
    cypher_check = lambda q: check_query(q, CYPHER_BLOCKED, "//", cypher_unknown(names, props))
    # The rules for each translator.
    sparql_rules = translator_rules("SPARQL 1.2", SPARQL_ALLOWED, SPARQL_BLOCKED, "RDF")
    # The Cypher rules.
    cypher_rules = translator_rules("Cypher", CYPHER_ALLOWED, CYPHER_BLOCKED, "Neo4j")
    # The news sentences and their vectors (embedded once, then cached).
    sentences = news_sentences()
    # The vectors.
    vectors = sentence_vectors(client, sentences)
    # Ask Gemini for every generated query and every vector answer, a few at once (cached answers come straight back).
    with ThreadPoolExecutor(PARALLEL) as pool:
        # The SPARQL translations (asking only; running comes after).
        sq = [pool.submit(ask_gemini, client, "text-to-SPARQL", r["file"].removesuffix(".rq"), sparql_rules,
                          f"{book['rdf']}\n\n## Question\n{r['QUESTION']}\n\n## Columns to return, in this order\n{', '.join(r['columns'])}\n", Generated) for r in refs]
        # The Cypher translations.
        cq = [pool.submit(ask_gemini, client, "text-to-Cypher", r["file"].removesuffix(".rq"), cypher_rules,
                          f"{book['lpg']}\n\n## Question\n{r['QUESTION']}\n\n## Columns to return, in this order\n{', '.join(r['columns'])}\n", Generated) for r in refs]
        # Wait for them all (they are now cached for the steps below).
        [f.result() for f in sq + cq]
    # Every attempt.
    attempts = []
    # Each question.
    for ref in refs:
        # Text-to-SPARQL: check, then run in a separate process with the time limit.
        attempts.append(text_to_query(client, "text-to-SPARQL", ref, book["rdf"], sparql_rules, sparql_check, run_sparql))
        # Text-to-Cypher: check, then run read-only with the time limit.
        attempts.append(text_to_query(client, "text-to-Cypher", ref, book["lpg"], cypher_rules, cypher_check, lambda q: run_cypher(driver, q)))
        # Vector search.
        attempts.append(vector_search(client, ref, sentences, vectors))
        # Progress.
        print(f"{ref['file']}: " + "; ".join(f"{a['method']}: {a['status']}" for a in attempts[-3:]))
    # Close the connection.
    driver.close()
    # Registry records' two forms (id and web address).
    addresses = record_addresses(store)
    # The answer keys by question id.
    keys = {r["file"].removesuffix(".rq"): r for r in refs}
    # Score every attempt against its answer key.
    for a in attempts:
        # The candidate: its rows (with both forms of each cited record), or "not available".
        candidate = {"rows": [with_both_forms(r, addresses) for r in a["rows"]], "not_available": a.get("not_found", False)}
        # The scores and what went wrong.
        a["score"] = score(keys[a["question"]], candidate)
        # Save the attempt in full.
        path = OUT_DIR / a["method"].replace(" ", "-") / f"{a['question']}.json"
        # Make sure the folder exists.
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write it.
        path.write_text(json.dumps(a, ensure_ascii=False, indent=1), encoding="utf-8")
    # Write the report.
    write_report(refs, attempts)
    # Say where it is.
    print(f"Report: {REPORT_PATH.relative_to(PROJECT_ROOT)}")


# Write docs/comparison.md: the summary, the table, every failure, every query.
def write_report(refs: list[dict], attempts: list[dict]) -> None:
    # The attempts by (question, method).
    by = {(a["question"], a["method"]): a for a in attempts}
    # The question ids, in order.
    qids = [r["file"].removesuffix(".rq") for r in refs]
    # A mean of a list (0 if empty).
    mean = lambda xs: sum(xs) / len(xs) if xs else 0.0
    # The opening.
    L = ["# Three-way comparison (generated by `make compare`; do not edit by hand)", "",
         f"Each question was answered from the plain-English question alone, by text-to-SPARQL, text-to-Cypher and vector search "
         f"(settings: D-124). Every answer is scored against the hand-written answer key (`docs/answers-rdf.md`) by the same scorer: "
         f"**correctness** (right items, none missed or invented), **citation** (the right sources), **overall** (their average).", "",
         f"Translator and answerer: `{MODEL}`, temperature 0. Embeddings: `{EMBED_MODEL}`, one vector per news sentence, top {TOP_K}. "
         f"Generated queries: blocked words and made-up names rejected, run read-only, {TIME_LIMIT} s limit, no retries.", "",
         "## Summary", "", "| Method | Overall | Correctness | Citation | Ran or answered | Rejected / failed | Said not found |", "|---|---|---|---|---|---|---|"]
    # One summary line per method.
    for m in METHODS:
        # This method's attempts.
        mine = [by[(q, m)] for q in qids]
        # How many ran (or answered), failed, or said not found.
        ran = sum(1 for a in mine if a["status"].startswith(("ran", "answered")))
        # Said not found.
        nf = sum(1 for a in mine if a.get("not_found"))
        # The line.
        L.append(f"| {m} | {mean([a['score']['overall'] for a in mine]):.2f} | {mean([a['score']['correctness'] for a in mine]):.2f} | "
                 f"{mean([a['score']['citation'] for a in mine]):.2f} | {ran} | {len(mine) - ran - nf} | {nf} |")
    # The per-question table: overall score for each method.
    L += ["", "## By question (overall; correctness / citation)", "", "| Question | " + " | ".join(METHODS) + " |", "|---" * (len(METHODS) + 1) + "|"]
    # One line per question.
    for q in qids:
        # Each method's cell.
        cells = [f"{by[(q, m)]['score']['overall']:.2f} ({by[(q, m)]['score']['correctness']:.2f} / {by[(q, m)]['score']['citation']:.2f})" for m in METHODS]
        # The line.
        L.append(f"| {q} | " + " | ".join(cells) + " |")
    # Every attempt in detail: status, what went wrong, the query or the retrieved sentences.
    L += ["", "## Every attempt", ""]
    # Each question.
    for ref in refs:
        # Its id.
        q = ref["file"].removesuffix(".rq")
        # Its heading and wording.
        L += [f"### {q}", "", f"*{ref['QUESTION']}* ({len(ref['rows'])} items in the answer key)", ""]
        # Each method.
        for m in METHODS:
            # The attempt.
            a = by[(q, m)]
            # What went wrong, from the scorer (only the non-zero counts).
            errs = ", ".join(f"{k.replace('_', ' ')}: {v}" for k, v in a["score"].get("errors", {}).items() if v)
            # The heading line: method, status, rows, score.
            L += [f"**{m}**: {a['status']}; {len(a['rows'])} rows; overall {a['score']['overall']:.2f}" + (f"; {errs}" if errs else "") +
                  f"; {a['seconds']} s, {a['tokens']:,} tokens", ""]
            # The generated query, if there is one.
            if a.get("query"):
                # As a code block.
                L += ["```" + ("sparql" if "SPARQL" in m else "cypher"), a["query"].strip(), "```", ""]
            # The retrieved sentences, for vector search.
            if a.get("retrieved"):
                # One line each, with its similarity.
                L += [f"- {r['score']} `{r['id']}` {r['text'][:110]}" for r in a["retrieved"]] + [""]
    # Save it.
    REPORT_PATH.write_text("\n".join(L) + "\n", encoding="utf-8")


# Run main() when this file is run directly (the guard also keeps child processes from re-running it).
if __name__ == "__main__":
    # Go.
    main()
