# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Crawlify-kleine-anfragen ingests "Kleine Anfragen" (parliamentary questions) from the German Bundestag DIP-API, normalizes them into SQLite, generates semantic embeddings, and provides search/export functionality.

## Commands

### Setup
```bash
pip install -e .                      # Core install
pip install -e ".[dev]"               # + pytest
pip install -e ".[embeddings]"        # + sentence-transformers
pip install -e ".[browser]"           # + playwright for bot protection
playwright install chromium           # Required if using browser
```

### Environment
```bash
export DIP_API_KEY="..."              # Required for API access
```

### Update (empfohlen)
```bash
python scripts/update_db.py           # Holt neue Vorgänge + Drucksachen
python scripts/update_db.py --limit 100  # Mehr Drucksachen
python scripts/update_db.py --skip-vorgang  # Nur Drucksachen nachladen
```

### CLI (Einzelbefehle)
```bash
crawlify fetch-vorgang
crawlify normalize-vorgang
crawlify fetch-drucksache
crawlify normalize-drucksache
crawlify fetch-drucksache-text
crawlify normalize-drucksache-text
crawlify embed-vorgang
crawlify search-vorgang "query"
crawlify solve-challenge              # Bot protection
crawlify clear-cookies
```

### Testing
```bash
pytest                                # Run all tests
pytest tests/test_dip_client.py       # Run single test file
pytest -k test_pagination             # Run tests matching pattern
```

## Architecture

### Data Flow
1. **Fetch** (DIP-API → raw JSON files): `dip_client.py`, `ingest.py`
2. **Normalize** (raw JSON → SQLite): `normalize.py`, `db.py`
3. **Embed** (SQLite → vectors stored in SQLite): `embeddings.py`
4. **Search** (query → cosine similarity): `search.py`

### Core Modules (src/crawlify/)
- `cli.py` - Entry point and all subcommands
- `dip_client.py` - DIP-API client with cursor pagination, retry/backoff, Enodia challenge handling
- `db.py` - SQLite schema (`vorgang`, `drucksache`, `drucksache_text`) and upsert logic
- `normalize.py` - Maps DIP-API fields to canonical schema
- `embeddings.py` - `SentenceTransformerProvider` using `intfloat/multilingual-e5-small`
- `browser.py` - Playwright-based Enodia bot challenge solver
- `config.py` - Environment-based configuration (DIP_API_KEY, timeouts, retries)

### Data Schema
Three main tables in SQLite:
- `vorgang` - Kleine Anfragen (id, titel, datum, beratungsstand, embeddings...)
- `drucksache` - Dokumente (Anfrage + Antwort) linked to vorgänge
- `drucksache_text` - Volltexte der Drucksachen

**Status-Feld:** `beratungsstand` zeigt ob beantwortet ("Beantwortet", "Noch nicht beantwortet", etc.)

### State Files
- `state/vorgang_cursor.json` - Cursor for resumable vorgang fetching
- `state/cookies.json` - Cached Enodia challenge cookies
- `data/raw/` - Raw JSON pages from DIP-API
- `data/db/crawlify.sqlite` - Normalized data + embeddings

## Key Patterns

- Cursor-based pagination: DIP-API returns max 100 items per request with cursor for continuation
- Idempotent upserts: All database operations use `ON CONFLICT ... DO UPDATE`
- Bot protection: DIP-API uses Enodia challenges; auto-solved via Playwright or manually
- Embedding text: Combines titel + abstrakt + volltext (truncated to 8000 chars)
