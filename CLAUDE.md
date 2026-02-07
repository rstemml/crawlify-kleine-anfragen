# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Crawlify-kleine-anfragen ingests "Kleine Anfragen" (parliamentary questions) from the German Bundestag DIP-API, normalizes them into SQLite, generates semantic embeddings, and provides search via CLI and a web UI.

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

### Update (recommended workflow)
```bash
python scripts/update_db.py           # Fetch new Vorgänge + Drucksachen
python scripts/update_db.py --limit 100  # More Drucksachen per run
python scripts/update_db.py --skip-vorgang  # Only reload Drucksachen
python scripts/update_db.py --full    # Full initial load
```

### CLI (individual steps)
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

### Search UI
```bash
cd search-ui && ./run.sh              # Start FastAPI + frontend on :8000
# Or for development with auto-reload:
cd search-ui/backend && uvicorn main:app --reload --host 0.0.0.0 --port 8000
# Frontend dev server:
cd search-ui/frontend && npm install && npm run dev
```

### Docker
```bash
docker compose build                  # Build image (multi-stage: Preact frontend + Python backend)
docker compose up -d                  # Run on :8000 with volume mounts for data/state/logs
```

## Architecture

### Data Flow (pipeline must run in this order)
1. **Fetch** (DIP-API → raw JSON in `data/raw/`): `dip_client.py`, `ingest.py`
2. **Normalize** (raw JSON → SQLite in `data/db/crawlify.sqlite`): `normalize.py`, `db.py`
3. **Embed** (SQLite text → vectors stored in SQLite): `embeddings.py`
4. **Search** (query → cosine similarity): `search.py`
5. **Serve** (FastAPI web UI): `search-ui/backend/`

### Core Modules (`src/crawlify/`)
- `cli.py` — Entry point; orchestrates all subcommands (fetch, normalize, embed, search)
- `dip_client.py` — DIP-API HTTP client with cursor pagination, exponential backoff (retries on 429/5xx), and Enodia challenge auto-detection
- `db.py` — SQLite schema (3 tables) and idempotent upsert logic (`ON CONFLICT ... DO UPDATE`)
- `normalize.py` — Maps DIP-API JSON fields to canonical schema; handles API field name variations defensively
- `embeddings.py` — `SentenceTransformerProvider` using `intfloat/multilingual-e5-small`
- `search.py` — Cosine similarity ranking over stored embedding vectors
- `browser.py` — Playwright-based Enodia bot challenge solver with 1-hour cookie caching
- `config.py` — `Config` dataclass from environment (DIP_API_KEY, timeouts, retries)
- `ingest.py` — High-level fetch orchestration with cursor state save/restore
- `storage.py` — Cursor state persistence to `state/vorgang_cursor.json`
- `progress.py` — CLI progress display with ETA calculation

### Search UI (`search-ui/`)
- `backend/main.py` — FastAPI app: `/api/search` (POST/GET), `/api/chat`, `/api/vorgang/{id}`, `/api/stats`, `/api/auth/login` (JWT), admin endpoints (JWT Bearer Auth)
- `backend/search_service.py` — Loads embeddings into memory, performs cosine similarity search
- `backend/admin_service.py` — Admin data access and SQL query execution
- `backend/config.py` — API settings, DB_PATH override, JWT configuration
- `frontend/` — Preact + Vite app; build with `npm run build` for FastAPI static serving
- `Dockerfile` — Multi-stage build: node (frontend) → python (backend + embedded model)
- `docker-compose.yml` — Single-service deployment with volume mounts

### Data Schema (SQLite)
- `vorgang` — Kleine Anfragen metadata (PK: `vorgang_id`), includes `embedding_json` for vectors
- `drucksache` — Documents linked to Vorgänge (PK: `drucksache_id`, FK: `vorgang_id`); types are "Kleine Anfrage" (question) and "Antwort" (government response)
- `drucksache_text` — Full text extracted from PDFs (PK/FK: `drucksache_id`)

**`beratungsstand` field:** Status of the Vorgang — "Beantwortet", "Noch nicht beantwortet", "Zurückgezogen", "Erledigt durch Ablauf der Wahlperiode"

### State Files
- `state/vorgang_cursor.json` — Cursor for resumable vorgang fetching
- `state/cookies.json` — Cached Enodia challenge cookies (1-hour TTL)
- `data/raw/` — Raw JSON pages from DIP-API
- `data/db/crawlify.sqlite` — Normalized data + embeddings

### Orchestration Script (`scripts/update_db.py`)
- Runs the full fetch→normalize pipeline with file-based locking (prevents concurrent runs)
- Exit codes: 0=success, 1=error, 2=already running, 3=auth error
- Logs to `logs/update_db.log`
- Deployed via systemd timer (daily at 3:00 AM) — see `systemd/`

## Key Patterns

- **Cursor-based pagination:** DIP-API returns max 100 items per request with cursor for continuation; cursor state is persisted between runs for incremental updates
- **Idempotent upserts:** All database operations use `ON CONFLICT ... DO UPDATE`, making re-runs safe
- **Bot protection:** DIP-API uses Enodia challenges; auto-solved via Playwright or manually via `crawlify solve-challenge --visible`
- **Embedding text:** Combines titel + abstrakt + drucksache volltext (truncated to 8000 chars)
- **Defensive normalization:** `normalize.py` tries multiple field name variations to handle DIP-API evolution
- **Retry with backoff:** `dip_client.py` retries on 429/500/502/503/504 with exponential backoff and jitter

## Conventions

- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`
- Python style: PEP 8
- Tests use mock-based unit testing (FakeSession/FakeResponse pattern in `tests/test_dip_client.py`)
