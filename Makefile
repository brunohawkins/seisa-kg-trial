# SUMMARY: Short, memorable commands for running the project.
# Type `make <name>` in the project folder, e.g. `make test`.
# `make build` is the single command that runs the whole pipeline from scratch
# (the RDF graph for now; the Neo4j graph is to be built with Bruno, step by step).

# Where the project's own copy of Neo4j lives (see scripts/install_neo4j.sh).
NEO4J := tools/neo4j/bin/neo4j

# Tell make these names are commands, not files to be created.
.PHONY: setup test brief build fetch-gleif facts rdf query score-demo neo4j-install neo4j-start neo4j-stop neo4j-status

# Install every Python library into the project's private environment.
setup:
	# uv reads pyproject.toml and uv.lock and installs the exact versions listed.
	uv sync

# Run all the automated tests.
test:
	# Run pytest inside the project's environment, with short output.
	uv run pytest -q

# Turn the Seisa brief documents into searchable text files.
brief:
	# Run the extraction script inside the project's environment.
	uv run python scripts/extract_brief.py

# Download GLEIF data for all three sponsors (pipeline stage 1; cached, so re-runs are quick).
fetch-gleif:
	# Run the GLEIF downloader inside the project's environment.
	uv run python -m seisa_kg.sources.gleif_fetch

# Build the shared fact list, data/interim/facts.jsonl, from the cache (pipeline stage 2).
facts:
	# Run the parsers inside the project's environment.
	uv run python -m seisa_kg.facts

# Build and check the RDF graph from the fact list, saving data/output/graph.ttl (pipeline stage 4).
rdf: facts
	# Run the RDF builder inside the project's environment.
	uv run python -m seisa_kg.rdf.build

# Run every investor question against the RDF graph; saves answers, sources and timings (pipeline stage 5).
query: rdf
	# Run the question runner inside the project's environment.
	uv run python -m seisa_kg.rdf.ask

# Show the scorer at work: damage each reference answer on purpose and score it (D-059 to D-061).
score-demo: query
	# Run the scoring demonstration inside the project's environment.
	uv run python -m seisa_kg.evaluation.demo

# The single command (brief §4): fetch (cached) -> facts -> scope -> RDF graph -> checks -> questions.
build: fetch-gleif query
	# Say the whole pipeline finished.
	@echo "Build complete: data/output/graph.ttl, docs/answers-rdf.md"

# Download and set up the project's own Neo4j server (only needed once).
neo4j-install:
	# Run the install script, which checks the download's fingerprint.
	bash scripts/install_neo4j.sh

# Start the Neo4j server in the background.
neo4j-start:
	# Start Neo4j; it then listens on this computer only (bolt://localhost:7687).
	$(NEO4J) start

# Stop the Neo4j server.
neo4j-stop:
	# Ask Neo4j to shut down cleanly.
	$(NEO4J) stop

# Check whether the Neo4j server is running.
neo4j-status:
	# Print Neo4j's current state.
	$(NEO4J) status
