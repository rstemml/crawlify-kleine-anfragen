"""
Kleine Anfragen Search API

A FastAPI-based backend for semantic search of German parliamentary questions.
Can be used by web UI, Telegram bots, or any other client.
"""
import os
import secrets
import uuid
from typing import Dict, Optional
from fastapi import FastAPI, HTTPException, Query, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pathlib import Path

from models import (
    SearchRequest, SearchResponse, SearchResultItem,
    ChatRequest, ChatResponse, ChatMessage,
    VorgangDetail, StatsResponse
)
from search_service import search_service
from admin_service import admin_service
from config import API_HOST, API_PORT

# Admin credentials from environment (or defaults for development)
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "anfragen2024")

security = HTTPBasic()

app = FastAPI(
    title="Kleine Anfragen Search API",
    description="Semantic search API for German parliamentary questions (Kleine Anfragen)",
    version="1.0.0",
)

# CORS for frontend and external clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory conversation storage (for production, use Redis or similar)
conversations: Dict[str, list] = {}


# --- API Endpoints ---

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/api/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    """
    Perform semantic search.

    This endpoint can be used by:
    - Web UI for interactive search
    - Telegram bot for command-based search
    - Any other client

    Args:
        request: SearchRequest with query, limit, and optional filters

    Returns:
        SearchResponse with results and refinement suggestions
    """
    try:
        result = search_service.search(
            query=request.query,
            limit=request.limit,
            filters=request.filters
        )

        return SearchResponse(
            query=result["query"],
            results=[SearchResultItem(**r) for r in result["results"]],
            total_found=result["total_found"],
            refinement_suggestions=result["refinement_suggestions"],
            conversation_id=request.conversation_id or str(uuid.uuid4()),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/search")
async def search_get(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(default=20, ge=1, le=100),
    ressort: Optional[str] = Query(default=None),
    beratungsstand: Optional[str] = Query(default=None),
):
    """
    GET endpoint for search - useful for simple integrations.
    """
    filters = {}
    if ressort:
        filters["ressort"] = ressort
    if beratungsstand:
        filters["beratungsstand"] = beratungsstand

    request = SearchRequest(
        query=q,
        limit=limit,
        filters=filters if filters else None
    )
    return await search(request)


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Chat-style search interface.

    Allows conversational refinement of search queries.
    Perfect for interactive UIs or chatbots.

    Args:
        request: ChatRequest with message and optional conversation history

    Returns:
        ChatResponse with assistant message, results, and follow-up questions
    """
    conversation_id = request.conversation_id or str(uuid.uuid4())

    # Get or create conversation history
    if conversation_id not in conversations:
        conversations[conversation_id] = []

    history = conversations[conversation_id]

    # Add user message
    history.append({"role": "user", "content": request.message})

    # Perform search
    result = search_service.search(request.message, limit=20)

    # Generate response message
    if result["results"]:
        count = len(result["results"])
        total = result["total_found"]
        response_msg = f"Ich habe {total} relevante Kleine Anfragen gefunden. Hier sind die {count} besten Treffer:"

        if result["refinement_suggestions"]:
            response_msg += "\n\nMoechten Sie die Suche eingrenzen?"
    else:
        response_msg = "Leider konnte ich keine passenden Kleine Anfragen finden. Versuchen Sie es mit anderen Suchbegriffen."

    # Add assistant response to history
    history.append({"role": "assistant", "content": response_msg})

    # Keep only last 20 messages
    if len(history) > 20:
        history = history[-20:]
    conversations[conversation_id] = history

    return ChatResponse(
        message=response_msg,
        results=[SearchResultItem(**r) for r in result["results"]] if result["results"] else None,
        refinement_questions=result["refinement_suggestions"],
        conversation_id=conversation_id,
    )


@app.get("/api/vorgang/{vorgang_id}", response_model=VorgangDetail)
async def get_vorgang(vorgang_id: str):
    """
    Get detailed information about a specific Vorgang.
    """
    result = search_service.get_vorgang_detail(vorgang_id)
    if not result:
        raise HTTPException(status_code=404, detail="Vorgang not found")
    return VorgangDetail(**result)


@app.get("/api/stats", response_model=StatsResponse)
async def get_stats():
    """
    Get database statistics.

    Useful for showing stats in UI or monitoring.
    """
    result = search_service.get_stats()
    return StatsResponse(**result)


@app.post("/api/cache/invalidate")
async def invalidate_cache():
    """
    Invalidate embeddings cache.

    Call this after updating the database to refresh search results.
    """
    search_service.invalidate_cache()
    return {"status": "ok", "message": "Cache invalidated"}


# --- Admin Authentication ---

def verify_admin(credentials: HTTPBasicCredentials = Depends(security)):
    """Verify admin credentials."""
    is_username_correct = secrets.compare_digest(
        credentials.username.encode("utf8"),
        ADMIN_USERNAME.encode("utf8")
    )
    is_password_correct = secrets.compare_digest(
        credentials.password.encode("utf8"),
        ADMIN_PASSWORD.encode("utf8")
    )
    if not (is_username_correct and is_password_correct):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


# --- Admin API Endpoints ---

@app.get("/api/admin/overview")
async def admin_overview(username: str = Depends(verify_admin)):
    """Get detailed database overview for admin."""
    return admin_service.get_overview_stats()


@app.get("/api/admin/vorgaenge")
async def admin_vorgaenge(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="datum"),
    sort_order: str = Query(default="desc"),
    ressort: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    username: str = Depends(verify_admin)
):
    """Get paginated list of Vorgaenge for admin."""
    return admin_service.get_vorgaenge(
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order,
        filter_ressort=ressort,
        filter_status=status,
        search=search
    )


@app.get("/api/admin/drucksachen")
async def admin_drucksachen(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    vorgang_id: Optional[str] = Query(default=None),
    username: str = Depends(verify_admin)
):
    """Get paginated list of Drucksachen for admin."""
    return admin_service.get_drucksachen(
        limit=limit,
        offset=offset,
        vorgang_id=vorgang_id
    )


@app.get("/api/admin/drucksache-text/{drucksache_id}")
async def admin_drucksache_text(
    drucksache_id: str,
    username: str = Depends(verify_admin)
):
    """Get full text of a Drucksache."""
    result = admin_service.get_drucksache_text(drucksache_id)
    if not result:
        raise HTTPException(status_code=404, detail="Text not found")
    return result


@app.post("/api/admin/query")
async def admin_query(
    query: str = Query(..., description="SQL SELECT query"),
    limit: int = Query(default=100, ge=1, le=1000),
    username: str = Depends(verify_admin)
):
    """Execute a read-only SQL query (admin only)."""
    return admin_service.execute_query(query, limit)


# --- Static Files & Frontend ---

# Serve frontend static files
frontend_path = Path(__file__).parent.parent / "frontend"
frontend_dist = frontend_path / "dist"
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")

    @app.get("/")
    async def serve_frontend():
        """Serve the frontend application."""
        return FileResponse(str(frontend_dist / "index.html"))

    @app.get("/admin")
    async def serve_admin():
        """Serve the admin dashboard (authentication required via API calls)."""
        return FileResponse(str(frontend_dist / "admin.html"))


# --- Main ---

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=API_HOST, port=API_PORT)
