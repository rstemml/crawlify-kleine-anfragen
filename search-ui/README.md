# Kleine Anfragen Search UI

A modern semantic search interface for German parliamentary questions (Kleine Anfragen).

## Architecture

```
search-ui/
├── backend/               # FastAPI backend (separate API)
│   ├── main.py            # API endpoints
│   ├── models.py          # Pydantic models
│   ├── search_service.py  # Search logic
│   ├── admin_service.py   # Admin data access
│   └── config.py          # Configuration
└── frontend/              # React + Vite frontend
    ├── index.html         # Search UI entry
    ├── admin.html         # Admin UI entry
    ├── src/               # React source
    └── dist/              # Vite build output (generated)
```

## Features

- **Semantic Search**: Uses embeddings for intelligent, meaning-based search
- **Chat Interface**: Conversational search with refinement suggestions
- **Card-based Results**: Visual display with relevance scores and highlights
- **Separate Backend API**: Can be used by web UI, Telegram bots, or any client
- **Admin Dashboard**: Password-protected admin panel for database visualization

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

## Telegram Bot Integration

Example Python code for a Telegram bot:

```python
import requests

API_URL = "http://localhost:8000"

def search_anfragen(query: str, limit: int = 5):
    response = requests.post(
        f"{API_URL}/api/search",
        json={"query": query, "limit": limit}
    )
    return response.json()

def format_result(result):
    return f"""
*{result['titel']}*
Relevanz: {int(result['score'] * 100)}%
Datum: {result.get('datum', 'N/A')}
Status: {result.get('beratungsstand', 'N/A')}
"""
```

## Admin Dashboard

Access the admin panel at http://localhost:8000/admin

### Default Credentials

- Username: `admin`
- Password: `anfragen2024`

### Features

- **Overview**: Database statistics, charts by ressort/status/year
- **Vorgaenge**: Browse, search, filter, and sort all Vorgaenge
- **Drucksachen**: View documents with full-text preview
- **SQL Query**: Execute read-only SQL queries directly

### Admin API Endpoints

All admin endpoints require HTTP Basic Auth:

```bash
# Overview stats
curl -u admin:anfragen2024 http://localhost:8000/api/admin/overview

# Paginated vorgaenge
curl -u admin:anfragen2024 "http://localhost:8000/api/admin/vorgaenge?limit=50&offset=0"

# Drucksachen for a vorgang
curl -u admin:anfragen2024 "http://localhost:8000/api/admin/drucksachen?vorgang_id=12345"

# Full text
curl -u admin:anfragen2024 http://localhost:8000/api/admin/drucksache-text/67890

# SQL query
curl -u admin:anfragen2024 -X POST "http://localhost:8000/api/admin/query?query=SELECT%20COUNT(*)%20FROM%20vorgang"
```

## Configuration

Environment variables:

- `API_HOST`: Host to bind to (default: 0.0.0.0)
- `API_PORT`: Port to bind to (default: 8000)
- `ADMIN_USERNAME`: Admin username (default: admin)
- `ADMIN_PASSWORD`: Admin password (default: anfragen2024)

## Development

The frontend uses React with Vite. Build the UI before serving from FastAPI.
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

To modify the design:
- Colors: Edit CSS variables in `frontend/static/css/styles.css`
- Layout: Modify the HTML structure in `frontend/index.html`
- Behavior: Update `frontend/static/js/app.js`
