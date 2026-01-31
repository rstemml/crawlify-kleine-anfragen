from __future__ import annotations

import json
import math
import sqlite3
from typing import Any, Dict, Iterable, List, Optional, Tuple


def load_embeddings(
    conn: sqlite3.Connection, embedding_version: Optional[str] = None
) -> List[Tuple[str, List[float], Dict[str, Any]]]:
    if embedding_version:
        rows = conn.execute(
            """
            SELECT vorgang_id, embedding_json, embedding_version, titel, datum, ressort
            FROM vorgang
            WHERE embedding_json IS NOT NULL AND embedding_version = ?
            """,
            (embedding_version,),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT vorgang_id, embedding_json, embedding_version, titel, datum, ressort
            FROM vorgang
            WHERE embedding_json IS NOT NULL
            """,
        ).fetchall()

    items = []
    for row in rows:
        vector = json.loads(row["embedding_json"])
        meta = {
            "titel": row["titel"],
            "datum": row["datum"],
            "ressort": row["ressort"],
            "embedding_version": row["embedding_version"],
        }
        items.append((row["vorgang_id"], vector, meta))
    return items


def cosine_sim(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def rank_by_similarity(
    query_vec: List[float],
    items: Iterable[Tuple[str, List[float], Dict[str, Any]]],
    limit: int = 10,
) -> List[Tuple[str, float, Dict[str, Any]]]:
    scored = []
    for vorgang_id, vec, meta in items:
        scored.append((vorgang_id, cosine_sim(query_vec, vec), meta))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:limit]
