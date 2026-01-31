from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class DbConfig:
    path: Path


def connect(cfg: DbConfig) -> sqlite3.Connection:
    cfg.path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(cfg.path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS vorgang (
            vorgang_id TEXT PRIMARY KEY,
            vorgangstyp TEXT NOT NULL,
            titel TEXT,
            datum TEXT,
            beratungsstand TEXT,
            legislature TEXT,
            initiatoren_json TEXT,
            ressort TEXT,
            schlagworte_json TEXT,
            abstrakt TEXT,
            quelle TEXT NOT NULL,
            embedding_text TEXT,
            embedding_json TEXT,
            embedding_version TEXT,
            raw_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS drucksache (
            drucksache_id TEXT PRIMARY KEY,
            vorgang_id TEXT NOT NULL,
            titel TEXT,
            drucksachetyp TEXT,
            drucksache_nummer TEXT,
            datum TEXT,
            dok_url TEXT,
            dokument_typ TEXT,
            raw_json TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (vorgang_id) REFERENCES vorgang(vorgang_id)
        );

        CREATE TABLE IF NOT EXISTS drucksache_text (
            drucksache_id TEXT PRIMARY KEY,
            volltext TEXT,
            text_format TEXT,
            raw_json TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (drucksache_id) REFERENCES drucksache(drucksache_id)
        );
        """
    )
    conn.commit()


def upsert_vorgang(conn: sqlite3.Connection, row: Dict[str, Any]) -> None:
    payload = row.copy()
    payload["initiatoren_json"] = _json_or_none(payload.get("initiatoren_json"))
    payload["schlagworte_json"] = _json_or_none(payload.get("schlagworte_json"))
    payload["raw_json"] = json.dumps(payload.get("raw_json") or {}, ensure_ascii=True)

    conn.execute(
        """
        INSERT INTO vorgang (
            vorgang_id, vorgangstyp, titel, datum, beratungsstand, legislature,
            initiatoren_json, ressort, schlagworte_json, abstrakt, quelle,
            embedding_text, embedding_json, embedding_version, raw_json, updated_at
        ) VALUES (
            :vorgang_id, :vorgangstyp, :titel, :datum, :beratungsstand, :legislature,
            :initiatoren_json, :ressort, :schlagworte_json, :abstrakt, :quelle,
            :embedding_text, :embedding_json, :embedding_version, :raw_json, :updated_at
        )
        ON CONFLICT(vorgang_id) DO UPDATE SET
            vorgangstyp=excluded.vorgangstyp,
            titel=excluded.titel,
            datum=excluded.datum,
            beratungsstand=excluded.beratungsstand,
            legislature=excluded.legislature,
            initiatoren_json=excluded.initiatoren_json,
            ressort=excluded.ressort,
            schlagworte_json=excluded.schlagworte_json,
            abstrakt=excluded.abstrakt,
            quelle=excluded.quelle,
            embedding_text=excluded.embedding_text,
            embedding_json=excluded.embedding_json,
            embedding_version=excluded.embedding_version,
            raw_json=excluded.raw_json,
            updated_at=excluded.updated_at
        """,
        payload,
    )
    conn.commit()


def upsert_drucksache(conn: sqlite3.Connection, row: Dict[str, Any]) -> None:
    payload = row.copy()
    payload["raw_json"] = json.dumps(payload.get("raw_json") or {}, ensure_ascii=True)

    conn.execute(
        """
        INSERT INTO drucksache (
            drucksache_id, vorgang_id, titel, drucksachetyp, drucksache_nummer,
            datum, dok_url, dokument_typ, raw_json, updated_at
        ) VALUES (
            :drucksache_id, :vorgang_id, :titel, :drucksachetyp, :drucksache_nummer,
            :datum, :dok_url, :dokument_typ, :raw_json, :updated_at
        )
        ON CONFLICT(drucksache_id) DO UPDATE SET
            vorgang_id=excluded.vorgang_id,
            titel=excluded.titel,
            drucksachetyp=excluded.drucksachetyp,
            drucksache_nummer=excluded.drucksache_nummer,
            datum=excluded.datum,
            dok_url=excluded.dok_url,
            dokument_typ=excluded.dokument_typ,
            raw_json=excluded.raw_json,
            updated_at=excluded.updated_at
        """,
        payload,
    )
    conn.commit()


def upsert_drucksache_text(conn: sqlite3.Connection, row: Dict[str, Any]) -> None:
    payload = row.copy()
    payload["raw_json"] = json.dumps(payload.get("raw_json") or {}, ensure_ascii=True)

    conn.execute(
        """
        INSERT INTO drucksache_text (
            drucksache_id, volltext, text_format, raw_json, updated_at
        ) VALUES (
            :drucksache_id, :volltext, :text_format, :raw_json, :updated_at
        )
        ON CONFLICT(drucksache_id) DO UPDATE SET
            volltext=excluded.volltext,
            text_format=excluded.text_format,
            raw_json=excluded.raw_json,
            updated_at=excluded.updated_at
        """,
        payload,
    )
    conn.commit()


def _json_or_none(value: Optional[Any]) -> Optional[str]:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=True)
