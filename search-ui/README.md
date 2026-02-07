# Kleine Anfragen Search UI

A modern semantic search interface for German parliamentary questions (Kleine Anfragen).

## Architecture

```
search-ui/
├── backend/               # FastAPI backend (separate API)
│   ├── main.py            # API endpoints + JWT auth
│   ├── models.py          # Pydantic models
│   ├── search_service.py  # Search logic
│   ├── admin_service.py   # Admin data access
│   └── config.py          # Configuration
└── frontend/              # Preact + Vite frontend
    ├── index.html         # Search UI entry
    ├── admin.html         # Admin UI entry
    ├── src/               # Preact source
    └── dist/              # Vite build output (generated)
```

## Features

- **Semantic Search**: Uses embeddings for intelligent, meaning-based search
- **Chat Interface**: Conversational search with refinement suggestions
- **Card-based Results**: Visual display with relevance scores and highlights
- **Separate Backend API**: Can be used by web UI, Telegram bots, or any client
- **Admin Dashboard**: JWT-protected admin panel for database visualization
- **Docker Support**: Single-container deployment with docker compose

## Setup

### 1. Ensure Database Exists

Make sure you have run the crawlify update scripts:

```bash
python scripts/update_db.py
crawlify embed-vorgang
```

### 2. Run the Server

```bash
./run.sh
# Or manually:
cd search-ui/backend
pip install -r requirements.txt
python main.py
```

Or with uvicorn directly (for development with auto-reload):

```bash
cd search-ui/backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Open the UI

Visit http://localhost:8000 in your browser.

## Docker

Build and run with Docker Compose:

```bash
docker compose build
docker compose up -d
```

The app will be accessible at http://localhost:8000.

Data, state, and logs directories are mounted as volumes so the database persists across container restarts. Set environment variables in `.env` or pass them directly.

## API Endpoints

All endpoints can be used by external clients (Telegram bot, etc.):

### Search

```bash
# POST - full control
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Klimaschutz", "limit": 10}'

# GET - simple queries
curl "http://localhost:8000/api/search?q=Klimaschutz&limit=10"
```

### Chat Interface

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Welche Anfragen gibt es zu erneuerbaren Energien?"}'
```

### Get Detail

```bash
curl http://localhost:8000/api/vorgang/12345
```

### Statistics

```bash
curl http://localhost:8000/api/stats
```

## Admin Dashboard

Access the admin panel at http://localhost:8000/admin

### Authentication

Admin uses JWT tokens. Log in via the web form or obtain a token via API:

```bash
# Get a JWT token
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "anfragen2024"}'

# Use the token for admin endpoints
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/admin/overview
```

### Default Credentials

- Username: `admin`
- Password: `anfragen2024`

### Features

- **Overview**: Database statistics, charts by ressort/status/year
- **Vorgaenge**: Browse, search, filter, and sort all Vorgaenge
- **Drucksachen**: View documents with full-text preview
- **SQL Query**: Execute read-only SQL queries directly

### Admin API Endpoints

All admin endpoints require a JWT Bearer token:

```bash
# Overview stats
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/admin/overview

# Paginated vorgaenge
curl -H "Authorization: Bearer <token>" "http://localhost:8000/api/admin/vorgaenge?limit=50&offset=0"

# Drucksachen for a vorgang
curl -H "Authorization: Bearer <token>" "http://localhost:8000/api/admin/drucksachen?vorgang_id=12345"

# Full text
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/admin/drucksache-text/67890

# SQL query
curl -H "Authorization: Bearer <token>" -X POST "http://localhost:8000/api/admin/query?query=SELECT%20COUNT(*)%20FROM%20vorgang"
```

## Configuration

Environment variables:

- `API_HOST`: Host to bind to (default: 0.0.0.0)
- `API_PORT`: Port to bind to (default: 8000)
- `ADMIN_USERNAME`: Admin username (default: admin)
- `ADMIN_PASSWORD`: Admin password (default: anfragen2024)
- `JWT_SECRET`: Secret key for JWT signing (change in production!)
- `JWT_EXPIRATION_HOURS`: Token validity in hours (default: 24)
- `DB_PATH`: Override database path (useful for Docker)

## Development

The frontend uses Preact with Vite. Build the UI before serving from FastAPI.
CSS uses CSS custom properties for easy theming.

### Frontend Development

```bash
cd search-ui/frontend
npm install
npm run dev
```

For production/local FastAPI serving:

```bash
cd search-ui/frontend
npm install
npm run build
```
