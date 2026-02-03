"""Search service that wraps the crawlify search functionality."""
import json
import sqlite3
import re
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path

from config import DB_PATH, EMBEDDING_MODEL


class SearchService:
    """Semantic search service for Kleine Anfragen."""

    def __init__(self):
        self._embedding_model = None
        self._embeddings_cache: Optional[List[Tuple[str, List[float], Dict[str, Any]]]] = None

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        return conn

    def _get_embedding_model(self):
        """Lazy load embedding model."""
        if self._embedding_model is None:
            from sentence_transformers import SentenceTransformer
            self._embedding_model = SentenceTransformer(EMBEDDING_MODEL)
        return self._embedding_model

    def _load_embeddings(self, conn: sqlite3.Connection) -> List[Tuple[str, List[float], Dict[str, Any]]]:
        """Load all embeddings from database."""
        if self._embeddings_cache is not None:
            return self._embeddings_cache

        rows = conn.execute("""
            SELECT vorgang_id, embedding_json, titel, datum, ressort,
                   beratungsstand, abstrakt, initiatoren_json, schlagworte_json
            FROM vorgang
            WHERE embedding_json IS NOT NULL
        """).fetchall()

        items = []
        for row in rows:
            vector = json.loads(row["embedding_json"])
            meta = {
                "titel": row["titel"],
                "datum": row["datum"],
                "ressort": row["ressort"],
                "beratungsstand": row["beratungsstand"],
                "abstrakt": row["abstrakt"],
                "initiatoren": json.loads(row["initiatoren_json"]) if row["initiatoren_json"] else None,
                "schlagworte": json.loads(row["schlagworte_json"]) if row["schlagworte_json"] else None,
            }
            items.append((row["vorgang_id"], vector, meta))

        self._embeddings_cache = items
        return items

    def _cosine_sim(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity."""
        import math
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)

    def _extract_highlight(self, text: str, query: str, max_length: int = 200) -> Optional[str]:
        """Extract relevant snippet from text based on query terms."""
        if not text:
            return None

        # Simple keyword matching for highlight
        query_terms = query.lower().split()
        text_lower = text.lower()

        best_pos = 0
        best_score = 0

        # Find position with most query term matches nearby
        for i in range(0, len(text), 50):
            window = text_lower[i:i+max_length]
            score = sum(1 for term in query_terms if term in window)
            if score > best_score:
                best_score = score
                best_pos = i

        # Extract snippet
        start = max(0, best_pos - 20)
        end = min(len(text), start + max_length)
        snippet = text[start:end]

        # Clean up snippet
        if start > 0:
            snippet = "..." + snippet
        if end < len(text):
            snippet = snippet + "..."

        return snippet.strip()

    def search(
        self,
        query: str,
        limit: int = 20,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Perform semantic search.

        Args:
            query: Search query text
            limit: Maximum results to return
            filters: Optional filters (ressort, beratungsstand, datum_from, datum_to)

        Returns:
            Dict with results, suggestions, etc.
        """
        conn = self._get_connection()

        # Embed query
        model = self._get_embedding_model()
        query_vec = model.encode([query], normalize_embeddings=True).tolist()[0]

        # Load all embeddings
        items = self._load_embeddings(conn)

        # Calculate similarities
        scored = []
        for vorgang_id, vec, meta in items:
            # Apply filters
            if filters:
                if filters.get("ressort") and meta.get("ressort") != filters["ressort"]:
                    continue
                if filters.get("beratungsstand") and meta.get("beratungsstand") != filters["beratungsstand"]:
                    continue

            score = self._cosine_sim(query_vec, vec)
            scored.append((vorgang_id, score, meta))

        # Sort by score
        scored.sort(key=lambda x: x[1], reverse=True)
        top_results = scored[:limit]

        # Get drucksachen for top results
        results = []
        for vorgang_id, score, meta in top_results:
            # Fetch drucksachen
            drucksachen = conn.execute("""
                SELECT drucksache_id, titel, drucksachetyp, drucksache_nummer, datum, dok_url
                FROM drucksache
                WHERE vorgang_id = ?
            """, (vorgang_id,)).fetchall()

            drucksachen_list = [dict(d) for d in drucksachen]

            # Extract highlight
            highlight_text = meta.get("abstrakt") or meta.get("titel") or ""
            highlight = self._extract_highlight(highlight_text, query)

            results.append({
                "vorgang_id": vorgang_id,
                "titel": meta.get("titel"),
                "datum": meta.get("datum"),
                "ressort": meta.get("ressort"),
                "beratungsstand": meta.get("beratungsstand"),
                "abstrakt": meta.get("abstrakt"),
                "initiatoren": meta.get("initiatoren"),
                "schlagworte": meta.get("schlagworte"),
                "score": round(score, 4),
                "highlight": highlight,
                "drucksachen": drucksachen_list,
            })

        conn.close()

        # Generate refinement suggestions
        suggestions = self._generate_refinement_suggestions(query, results)

        return {
            "query": query,
            "results": results,
            "total_found": len(scored),
            "refinement_suggestions": suggestions,
        }

    def _generate_refinement_suggestions(
        self,
        query: str,
        results: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate suggestions to refine the search."""
        suggestions = []

        if not results:
            suggestions.append("Versuchen Sie allgemeinere Suchbegriffe")
            return suggestions

        # Collect common ressorts and schlagworte from results
        ressorts = {}
        schlagworte = {}

        for r in results[:10]:
            if r.get("ressort"):
                ressorts[r["ressort"]] = ressorts.get(r["ressort"], 0) + 1
            if r.get("schlagworte"):
                for s in r["schlagworte"]:
                    schlagworte[s] = schlagworte.get(s, 0) + 1

        # Suggest filtering by common ressort
        if ressorts:
            top_ressort = max(ressorts.items(), key=lambda x: x[1])[0]
            suggestions.append(f"Ergebnisse auf '{top_ressort}' eingrenzen?")

        # Suggest related keywords
        if schlagworte:
            top_keywords = sorted(schlagworte.items(), key=lambda x: x[1], reverse=True)[:3]
            for kw, _ in top_keywords:
                if kw.lower() not in query.lower():
                    suggestions.append(f"Auch nach '{kw}' suchen?")

        # Suggest status filter
        suggestions.append("Nur beantwortete Anfragen anzeigen?")

        return suggestions[:4]

    def get_vorgang_detail(self, vorgang_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific Vorgang."""
        conn = self._get_connection()

        row = conn.execute("""
            SELECT vorgang_id, vorgangstyp, titel, datum, beratungsstand,
                   legislature, ressort, abstrakt, initiatoren_json, schlagworte_json
            FROM vorgang
            WHERE vorgang_id = ?
        """, (vorgang_id,)).fetchone()

        if not row:
            conn.close()
            return None

        # Get drucksachen with text
        drucksachen = conn.execute("""
            SELECT d.drucksache_id, d.titel, d.drucksachetyp, d.drucksache_nummer,
                   d.datum, d.dok_url, dt.volltext
            FROM drucksache d
            LEFT JOIN drucksache_text dt ON d.drucksache_id = dt.drucksache_id
            WHERE d.vorgang_id = ?
        """, (vorgang_id,)).fetchall()

        conn.close()

        return {
            "vorgang_id": row["vorgang_id"],
            "vorgangstyp": row["vorgangstyp"],
            "titel": row["titel"],
            "datum": row["datum"],
            "beratungsstand": row["beratungsstand"],
            "legislature": row["legislature"],
            "ressort": row["ressort"],
            "abstrakt": row["abstrakt"],
            "initiatoren": json.loads(row["initiatoren_json"]) if row["initiatoren_json"] else None,
            "schlagworte": json.loads(row["schlagworte_json"]) if row["schlagworte_json"] else None,
            "drucksachen": [dict(d) for d in drucksachen],
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        conn = self._get_connection()

        total_vorgaenge = conn.execute("SELECT COUNT(*) FROM vorgang").fetchone()[0]
        total_drucksachen = conn.execute("SELECT COUNT(*) FROM drucksache").fetchone()[0]
        total_with_embeddings = conn.execute(
            "SELECT COUNT(*) FROM vorgang WHERE embedding_json IS NOT NULL"
        ).fetchone()[0]

        ressorts = conn.execute("""
            SELECT ressort, COUNT(*) as count
            FROM vorgang
            WHERE ressort IS NOT NULL
            GROUP BY ressort
            ORDER BY count DESC
        """).fetchall()

        beratungsstaende = conn.execute("""
            SELECT beratungsstand, COUNT(*) as count
            FROM vorgang
            WHERE beratungsstand IS NOT NULL
            GROUP BY beratungsstand
            ORDER BY count DESC
        """).fetchall()

        conn.close()

        return {
            "total_vorgaenge": total_vorgaenge,
            "total_drucksachen": total_drucksachen,
            "total_with_embeddings": total_with_embeddings,
            "ressorts": [{"name": r[0], "count": r[1]} for r in ressorts],
            "beratungsstaende": [{"name": b[0], "count": b[1]} for b in beratungsstaende],
        }

    def invalidate_cache(self):
        """Invalidate the embeddings cache."""
        self._embeddings_cache = None


# Singleton instance
search_service = SearchService()
