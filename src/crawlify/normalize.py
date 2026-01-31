from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional


def normalize_vorgang(item: Dict[str, Any]) -> Dict[str, Any]:
    vorgang_id = _first_str(item, ["id", "vorgang_id", "vorgangId"])
    vorgangstyp = _first_str(item, ["vorgangstyp", "vorgangsTyp", "type"])
    titel = _first_str(item, ["titel", "title", "kurzbezeichnung"])
    datum = _first_str(item, ["datum", "date", "datum_aktualisierung"])
    beratungsstand = _first_str(item, ["beratungsstand", "status", "stand"])
    legislature = _first_str(item, ["wahlperiode", "legislature"])
    initiatoren = item.get("initiatoren") or item.get("initiator") or []
    ressort = _first_str(item, ["ressort", "zustandigkeit", "federfuehrung"])
    schlagworte = item.get("schlagworte") or item.get("keywords") or []
    abstrakt = _first_str(item, ["abstrakt", "abstract", "kurztext"])

    embedding_text = _join_non_empty([titel, abstrakt])

    return {
        "vorgang_id": vorgang_id or "",
        "vorgangstyp": vorgangstyp or "",
        "titel": titel,
        "datum": datum,
        "beratungsstand": beratungsstand,
        "legislature": legislature,
        "initiatoren_json": initiatoren if initiatoren else None,
        "ressort": ressort,
        "schlagworte_json": schlagworte if schlagworte else None,
        "abstrakt": abstrakt,
        "quelle": "DIP",
        "embedding_text": embedding_text,
        "embedding_json": None,
        "embedding_version": None,
        "raw_json": item,
        "updated_at": _now_iso(),
    }


def normalize_drucksache(item: Dict[str, Any], vorgang_id: str) -> Dict[str, Any]:
    drucksache_id = _first_str(item, ["id", "drucksache_id", "drucksacheId"])
    titel = _first_str(item, ["titel", "title"])
    drucksachetyp = _first_str(item, ["drucksachetyp", "dokumentart", "typ"])
    drucksache_nummer = _first_str(item, ["drucksache_nr", "drucksache_nummer", "dokumentnummer"])
    datum = _first_str(item, ["datum", "date"])
    dokument = item.get("dokument") or {}
    dok_url = _first_str(dokument, ["url", "dok_url", "link"])
    dokument_typ = _first_str(dokument, ["typ", "type", "mime"])

    return {
        "drucksache_id": drucksache_id or "",
        "vorgang_id": vorgang_id,
        "titel": titel,
        "drucksachetyp": drucksachetyp,
        "drucksache_nummer": drucksache_nummer,
        "datum": datum,
        "dok_url": dok_url,
        "dokument_typ": dokument_typ,
        "raw_json": item,
        "updated_at": _now_iso(),
    }


def normalize_drucksache_text(item: Dict[str, Any]) -> Dict[str, Any]:
    drucksache_id = _first_str(item, ["drucksache_id", "drucksacheId", "id"])
    volltext = _first_str(item, ["text", "volltext", "content"])
    text_format = _first_str(item, ["format", "text_format", "mime"])

    return {
        "drucksache_id": drucksache_id or "",
        "volltext": volltext,
        "text_format": text_format,
        "raw_json": item,
        "updated_at": _now_iso(),
    }


def _first_str(d: Dict[str, Any], keys: List[str]) -> Optional[str]:
    for key in keys:
        val = d.get(key)
        if isinstance(val, str) and val.strip():
            return val
    return None


def _join_non_empty(parts: Iterable[Optional[str]]) -> Optional[str]:
    cleaned = [p.strip() for p in parts if isinstance(p, str) and p.strip()]
    if not cleaned:
        return None
    return "\n\n".join(cleaned)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
