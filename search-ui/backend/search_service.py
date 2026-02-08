"""Search service — uses SQL text search (no embedding model required)."""
import json
import sqlite3
from typing import List, Optional, Dict, Any
from pathlib import Path

from config import DB_PATH


class SearchService:

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        return conn

    def _extract_highlight(self, text: str, query: str, max_length: int = 200) -> Optional[str]:
        if not text:
            return None

        query_terms = query.lower().split()
        text_lower = text.lower()

        best_pos = 0
        best_score = 0

        for i in range(0, len(text), 50):
            window = text_lower[i:i + max_length]
            score = sum(1 for term in query_terms if term in window)
            if score > best_score:
                best_score = score
                best_pos = i

        start = max(0, best_pos - 20)
        end = min(len(text), start + max_length)
        snippet = text[start:end]

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
        conn = self._get_connection()

        where_clauses = []
        params: list = []

        for term in query.split():
            where_clauses.append("(v.titel LIKE ? OR v.abstrakt LIKE ?)")
            like = f"%{term}%"
            params.extend([like, like])

        filter_sql = ""
        if filters:
            if filters.get("ressort"):
                where_clauses.append("v.ressort = ?")
                params.append(filters["ressort"])
            if filters.get("beratungsstand"):
                where_clauses.append("v.beratungsstand = ?")
                params.append(filters["beratungsstand"])

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        rows = conn.execute(f"""
            SELECT v.vorgang_id, v.titel, v.datum, v.ressort,
                   v.beratungsstand, v.abstrakt, v.initiatoren_json, v.schlagworte_json
            FROM vorgang v
            WHERE {where_sql}
            ORDER BY v.datum DESC
            LIMIT ?
        """, params + [limit]).fetchall()

        count_row = conn.execute(f"""
            SELECT COUNT(*) FROM vorgang v WHERE {where_sql}
        """, params).fetchone()
        total_found = count_row[0]

        results = []
        for row in rows:
            drucksachen = conn.execute("""
                SELECT drucksache_id, titel, drucksachetyp, drucksache_nummer, datum, dok_url
                FROM drucksache
                WHERE vorgang_id = ?
            """, (row["vorgang_id"],)).fetchall()

            highlight_text = row["abstrakt"] or row["titel"] or ""
            highlight = self._extract_highlight(highlight_text, query)

            results.append({
                "vorgang_id": row["vorgang_id"],
                "titel": row["titel"],
                "datum": row["datum"],
                "ressort": row["ressort"],
                "beratungsstand": row["beratungsstand"],
                "abstrakt": row["abstrakt"],
                "initiatoren": json.loads(row["initiatoren_json"]) if row["initiatoren_json"] else None,
                "schlagworte": json.loads(row["schlagworte_json"]) if row["schlagworte_json"] else None,
                "score": 1.0,
                "highlight": highlight,
                "drucksachen": [dict(d) for d in drucksachen],
            })

        conn.close()

        suggestions = self._generate_refinement_suggestions(query, results)

        return {
            "query": query,
            "results": results,
            "total_found": total_found,
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
