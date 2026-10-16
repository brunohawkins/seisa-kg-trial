# Seisa trial: the same data in two graphs

Public data about private equity sponsors, their funds and the companies they own, stored in an **RDF graph** (Oxigraph) and a **labelled property graph** (Neo4j). Every fact is traceable to its source record or sentence.

> Work in progress. See [PLAN.md](PLAN.md) for the plan and [docs/decision-log.md](docs/decision-log.md) for every decision made so far.

## Setup

You need [uv](https://docs.astral.sh/uv/). It downloads the right Python version (3.12) for you.

1. **Install everything** into a private `.venv` folder:
   ```bash
   uv sync
   ```
2. **Add your secret keys:** copy the template and fill in the values.
   ```bash
   cp .env.example .env
   ```
3. **Check the setup works:**
   ```bash
   uv run pytest
   ```

## Building the graphs

Not built yet. This will be a single command, `make build`.
