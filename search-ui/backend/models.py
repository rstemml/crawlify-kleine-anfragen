"""Pydantic models for API requests and responses."""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class SearchRequest(BaseModel):
    """Search request model - can be used by web UI, Telegram bot, etc."""
    query: str = Field(..., min_length=1, description="Search query text")
    limit: int = Field(default=20, ge=1, le=100, description="Max results to return")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Optional filters")
    conversation_id: Optional[str] = Field(default=None, description="Conversation ID for chat context")


class SearchResultItem(BaseModel):
    """Single search result item."""
    vorgang_id: str
    titel: str
    datum: Optional[str]
    ressort: Optional[str]
    beratungsstand: Optional[str]
    abstrakt: Optional[str]
    initiatoren: Optional[List[str]]
    schlagworte: Optional[List[str]]
    score: float = Field(..., description="Similarity score 0-1")
    highlight: Optional[str] = Field(default=None, description="Highlighted relevant text snippet")
    drucksachen: Optional[List[Dict[str, Any]]] = Field(default=None, description="Related documents")


class SearchResponse(BaseModel):
    """Search response model."""
    query: str
    results: List[SearchResultItem]
    total_found: int
    refinement_suggestions: Optional[List[str]] = Field(
        default=None,
        description="Suggested questions to refine the search"
    )
    conversation_id: Optional[str] = Field(default=None, description="Conversation ID for follow-up")


class ChatMessage(BaseModel):
    """Single chat message."""
    role: str = Field(..., description="'user' or 'assistant'")
    content: str
    timestamp: Optional[datetime] = None
    search_results: Optional[List[SearchResultItem]] = None


class ChatRequest(BaseModel):
    """Chat-style search request."""
    message: str = Field(..., min_length=1, description="User message")
    conversation_id: Optional[str] = Field(default=None, description="Conversation ID to continue")
    history: Optional[List[ChatMessage]] = Field(default=None, description="Previous messages")


class ChatResponse(BaseModel):
    """Chat-style response with results and follow-up."""
    message: str = Field(..., description="Assistant response")
    results: Optional[List[SearchResultItem]] = None
    refinement_questions: Optional[List[str]] = None
    conversation_id: str


class VorgangDetail(BaseModel):
    """Detailed view of a single Vorgang."""
    vorgang_id: str
    vorgangstyp: str
    titel: str
    datum: Optional[str]
    beratungsstand: Optional[str]
    legislature: Optional[str]
    ressort: Optional[str]
    abstrakt: Optional[str]
    initiatoren: Optional[List[str]]
    schlagworte: Optional[List[str]]
    drucksachen: List[Dict[str, Any]]


class StatsResponse(BaseModel):
    """Database statistics."""
    total_vorgaenge: int
    total_drucksachen: int
    total_with_embeddings: int
    ressorts: List[Dict[str, int]]
    beratungsstaende: List[Dict[str, int]]
