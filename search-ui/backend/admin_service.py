"""Admin service for database visualization."""
import json
import sqlite3
from typing import List, Dict, Any, Optional
from config import DB_PATH


class AdminService:
    """Service for admin database operations."""

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        return conn

    def get_vorgaenge(
        self,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "datum",
        sort_order: str = "desc",
        filter_ressort: Optional[str] = None,
        filter_status: Optional[str] = None,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get paginated list of Vorgaenge."""
        conn = self._get_connection()

        # Build query
        where_clauses = []
        params = []

        if filter_ressort:
            where_clauses.append("ressort = ?")
            params.append(filter_ressort)

        if filter_status:
            where_clauses.append("beratungsstand = ?")
            params.append(filter_status)

        if search:
            where_clauses.append("(titel LIKE ? OR abstrakt LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        # Validate sort column
        allowed_sort = ["vorgang_id", "titel", "datum", "ressort", "beratungsstand", "updated_at"]
        if sort_by not in allowed_sort:
            sort_by = "datum"
        sort_dir = "DESC" if sort_order.lower() == "desc" else "ASC"

        # Count total
        count_sql = f"SELECT COUNT(*) FROM vorgang {where_sql}"
        total = conn.execute(count_sql, params).fetchone()[0]

        # Get data
        query = f"""
            SELECT vorgang_id, vorgangstyp, titel, datum, beratungsstand,
                   legislature, ressort, abstrakt, initiatoren_json, schlagworte_json,
                   embedding_version, updated_at
            FROM vorgang
            {where_sql}
            ORDER BY {sort_by} {sort_dir}
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        rows = conn.execute(query, params).fetchall()
        conn.close()

        items = []
        for row in rows:
            item = dict(row)
            item["initiatoren"] = json.loads(item["initiatoren_json"]) if item["initiatoren_json"] else None
            item["schlagworte"] = json.loads(item["schlagworte_json"]) if item["schlagworte_json"] else None
            del item["initiatoren_json"]
            del item["schlagworte_json"]
            items.append(item)

        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "pages": (total + limit - 1) // limit
        }

    def get_drucksachen(
        self,
        limit: int = 50,
        offset: int = 0,
        vorgang_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get paginated list of Drucksachen."""
        conn = self._get_connection()

        where_sql = ""
        params = []
        if vorgang_id:
            where_sql = "WHERE d.vorgang_id = ?"
            params.append(vorgang_id)

        count_sql = f"SELECT COUNT(*) FROM drucksache d {where_sql}"
        total = conn.execute(count_sql, params).fetchone()[0]

        query = f"""
            SELECT d.drucksache_id, d.vorgang_id, d.titel, d.drucksachetyp,
                   d.drucksache_nummer, d.datum, d.dok_url, d.dokument_typ, d.updated_at,
                   CASE WHEN dt.volltext IS NOT NULL THEN 1 ELSE 0 END as has_text,
                   LENGTH(dt.volltext) as text_length
            FROM drucksache d
            LEFT JOIN drucksache_text dt ON d.drucksache_id = dt.drucksache_id
            {where_sql}
            ORDER BY d.datum DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        rows = conn.execute(query, params).fetchall()
        conn.close()

        return {
            "items": [dict(row) for row in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
            "pages": (total + limit - 1) // limit
        }

    def get_drucksache_text(self, drucksache_id: str) -> Optional[Dict[str, Any]]:
        """Get full text of a Drucksache."""
        conn = self._get_connection()
        row = conn.execute("""
            SELECT drucksache_id, volltext, text_format, updated_at
            FROM drucksache_text
            WHERE drucksache_id = ?
        """, (drucksache_id,)).fetchone()
        conn.close()

        if not row:
            return None
        return dict(row)

    def get_overview_stats(self) -> Dict[str, Any]:
        """Get detailed database statistics for admin."""
        conn = self._get_connection()

        stats = {}

        # Basic counts
        stats["vorgaenge_total"] = conn.execute("SELECT COUNT(*) FROM vorgang").fetchone()[0]
        stats["drucksachen_total"] = conn.execute("SELECT COUNT(*) FROM drucksache").fetchone()[0]
        stats["drucksache_texts_total"] = conn.execute("SELECT COUNT(*) FROM drucksache_text").fetchone()[0]

        # Embedding stats
        stats["with_embeddings"] = conn.execute(
            "SELECT COUNT(*) FROM vorgang WHERE embedding_json IS NOT NULL"
        ).fetchone()[0]
        stats["without_embeddings"] = stats["vorgaenge_total"] - stats["with_embeddings"]

        # By ressort
        stats["by_ressort"] = [
            {"name": r[0] or "Unbekannt", "count": r[1]}
            for r in conn.execute("""
                SELECT ressort, COUNT(*) as cnt FROM vorgang
                GROUP BY ressort ORDER BY cnt DESC
            """).fetchall()
        ]

        # By status
        stats["by_status"] = [
            {"name": b[0] or "Unbekannt", "count": b[1]}
            for b in conn.execute("""
                SELECT beratungsstand, COUNT(*) as cnt FROM vorgang
                GROUP BY beratungsstand ORDER BY cnt DESC
            """).fetchall()
        ]

        # By year
        stats["by_year"] = [
            {"year": y[0], "count": y[1]}
            for y in conn.execute("""
                SELECT substr(datum, 1, 4) as year, COUNT(*) as cnt
                FROM vorgang
                WHERE datum IS NOT NULL
                GROUP BY year ORDER BY year DESC
            """).fetchall()
        ]

        # Drucksache types
        stats["drucksache_types"] = [
            {"type": d[0] or "Unbekannt", "count": d[1]}
            for d in conn.execute("""
                SELECT drucksachetyp, COUNT(*) as cnt FROM drucksache
                GROUP BY drucksachetyp ORDER BY cnt DESC
            """).fetchall()
        ]

        # Text coverage
        stats["text_coverage"] = {
            "with_text": conn.execute("""
                SELECT COUNT(DISTINCT d.drucksache_id)
                FROM drucksache d
                INNER JOIN drucksache_text dt ON d.drucksache_id = dt.drucksache_id
            """).fetchone()[0],
            "without_text": stats["drucksachen_total"] - conn.execute("""
                SELECT COUNT(DISTINCT d.drucksache_id)
                FROM drucksache d
                INNER JOIN drucksache_text dt ON d.drucksache_id = dt.drucksache_id
            """).fetchone()[0]
        }

        # Recent updates
        stats["recent_vorgaenge"] = [
            dict(r) for r in conn.execute("""
                SELECT vorgang_id, titel, datum, updated_at
                FROM vorgang ORDER BY updated_at DESC LIMIT 10
            """).fetchall()
        ]

        conn.close()
        return stats

    def execute_query(self, query: str, limit: int = 100) -> Dict[str, Any]:
        """Execute a read-only SQL query (for advanced admin use)."""
        # Basic safety check - only allow SELECT
        query_upper = query.strip().upper()
        if not query_upper.startswith("SELECT"):
            return {"error": "Only SELECT queries are allowed"}

        conn = self._get_connection()
        try:
            # Add limit if not present
            if "LIMIT" not in query_upper:
                query = f"{query.rstrip(';')} LIMIT {limit}"

            cursor = conn.execute(query)
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            conn.close()

            return {
                "columns": columns,
                "rows": [list(row) for row in rows],
                "count": len(rows)
            }
        except Exception as e:
            conn.close()
            return {"error": str(e)}


admin_service = AdminService()
