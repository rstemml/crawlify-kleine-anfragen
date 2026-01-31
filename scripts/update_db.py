#!/usr/bin/env python3
"""
Update-Script für crawlify-kleine-anfragen.

Holt neue Vorgänge, Drucksachen und Volltexte von der DIP-API
und aktualisiert die SQLite-Datenbank.

Usage:
    python scripts/update_db.py [--full] [--limit N]

Options:
    --full      Alle Drucksachen für alle Vorgänge holen (langsam!)
    --limit N   Nur für die N neuesten Vorgänge Drucksachen holen (default: 50)
"""

import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from crawlify.config import load_config
from crawlify.db import DbConfig, connect, init_db, upsert_drucksache, upsert_drucksache_text
from crawlify.dip_client import DipClient, write_page_raw
from crawlify.ingest import ingest_vorgang_kleine_anfrage
from crawlify.normalize import normalize_vorgang, normalize_drucksache, normalize_drucksache_text
from crawlify.storage import CursorState, load_cursor_state, save_cursor_state

# Paths
BASE_DIR = Path(__file__).parent.parent
RAW_DIR = BASE_DIR / "data" / "raw" / "vorgang"
DB_PATH = BASE_DIR / "data" / "db" / "crawlify.sqlite"
STATE_PATH = BASE_DIR / "state" / "vorgang_cursor.json"


def fetch_and_normalize_vorgaenge(client: DipClient, conn, raw_dir: Path, state_path: Path) -> int:
    """Fetch new vorgänge and normalize them into the database."""
    print("\n=== 1. Fetching new Vorgänge ===")

    state = load_cursor_state(state_path)
    cursor = state.cursor

    if cursor:
        print(f"Resuming from cursor: {cursor[:50]}...")
    else:
        print("Starting fresh (no cursor)")

    total_items = 0
    page_idx = 0

    for page in client.fetch_vorgang_kleine_anfrage_pages(cursor=cursor):
        # Save raw
        write_page_raw(page, raw_dir, page_idx, prefix="vorgang")

        # Normalize and upsert
        for item in page.items:
            row = normalize_vorgang(item)
            if row["vorgang_id"] and row["vorgangstyp"]:
                upsert_vorgang(conn, row)
                total_items += 1

        # Save cursor state
        save_cursor_state(state_path, CursorState(cursor=page.cursor))

        page_idx += 1
        print(f"  Page {page_idx}: {len(page.items)} items (total: {total_items})")

        if not page.cursor:
            break

    conn.commit()
    print(f"Fetched and normalized {total_items} vorgänge")
    return total_items


def fetch_drucksachen_for_vorgaenge(client: DipClient, conn, vorgang_ids: list) -> int:
    """Fetch drucksachen for given vorgänge using drucksachetyp filter."""
    print(f"\n=== 2. Fetching Drucksachen for {len(vorgang_ids)} Vorgänge ===")

    target_set = set(str(v) for v in vorgang_ids)
    total_saved = 0

    for doc_type in ["Kleine Anfrage", "Antwort"]:
        print(f"\n  Fetching {doc_type}...")

        url = f"{client.cfg.dip_base_url}/drucksache"
        params = {
            "apikey": client.cfg.dip_api_key,
            "size": "100",
            "f.drucksachetyp": doc_type
        }

        # Fetch pages until we've seen all target vorgänge or hit limit
        found_vorgaenge = set()
        page_num = 0
        cursor = None

        while len(found_vorgaenge) < len(target_set) and page_num < 50:
            if cursor:
                params["cursor"] = cursor

            resp = client.session.get(url, params=params, timeout=30)
            data = resp.json()
            items = data.get("documents", [])
            cursor = data.get("cursor")

            for item in items:
                vorgangsbezug = item.get("vorgangsbezug", [])
                for vb in vorgangsbezug:
                    vorgang_id = str(vb.get("id", ""))
                    if vorgang_id in target_set:
                        row = normalize_drucksache(item, vorgang_id=vorgang_id)
                        if row["drucksache_id"]:
                            upsert_drucksache(conn, row)
                            total_saved += 1
                            found_vorgaenge.add(vorgang_id)
                        break

            page_num += 1
            if not cursor:
                break

        print(f"    Found {len(found_vorgaenge)} vorgänge, saved {total_saved} drucksachen")

    conn.commit()
    return total_saved


def fetch_drucksache_texts(client: DipClient, conn) -> int:
    """Fetch full text for drucksachen that don't have it yet."""
    print("\n=== 3. Fetching Drucksache Texts ===")

    # Get drucksachen without text
    rows = conn.execute("""
        SELECT d.drucksache_id
        FROM drucksache d
        LEFT JOIN drucksache_text dt ON d.drucksache_id = dt.drucksache_id
        WHERE dt.drucksache_id IS NULL
    """).fetchall()

    drucksache_ids = [r["drucksache_id"] for r in rows]
    print(f"  {len(drucksache_ids)} drucksachen without text")

    if not drucksache_ids:
        return 0

    total_saved = 0
    for ds_id in drucksache_ids:
        url = f"{client.cfg.dip_base_url}/drucksache-text"
        params = {
            "apikey": client.cfg.dip_api_key,
            "f.id": ds_id  # Important: use f.id, not f.drucksache!
        }

        try:
            resp = client.session.get(url, params=params, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("numFound") == 1:
                    items = data.get("documents", [])
                    if items:
                        row = normalize_drucksache_text(items[0])
                        if row["drucksache_id"] and row["volltext"]:
                            upsert_drucksache_text(conn, row)
                            total_saved += 1
                            print(f"    {ds_id}: {len(row['volltext'])} chars")
        except Exception as e:
            print(f"    {ds_id}: Error - {e}")

    conn.commit()
    print(f"  Saved {total_saved} texts")
    return total_saved


def get_vorgaenge_without_drucksachen(conn, limit: int) -> list:
    """Get vorgang IDs that don't have any drucksachen yet."""
    rows = conn.execute("""
        SELECT v.vorgang_id
        FROM vorgang v
        LEFT JOIN drucksache d ON v.vorgang_id = d.vorgang_id
        WHERE d.drucksache_id IS NULL
        ORDER BY v.datum DESC
        LIMIT ?
    """, (limit,)).fetchall()
    return [r["vorgang_id"] for r in rows]


def print_summary(conn):
    """Print database summary."""
    print("\n=== Datenbank-Übersicht ===")
    for table in ["vorgang", "drucksache", "drucksache_text"]:
        count = conn.execute(f"SELECT COUNT(*) as c FROM {table}").fetchone()["c"]
        print(f"  {table}: {count}")


def main():
    parser = argparse.ArgumentParser(description="Update crawlify database")
    parser.add_argument("--full", action="store_true", help="Fetch drucksachen for ALL vorgänge")
    parser.add_argument("--limit", type=int, default=50, help="Limit vorgänge for drucksache fetch")
    parser.add_argument("--skip-vorgang", action="store_true", help="Skip vorgang fetch")
    parser.add_argument("--skip-drucksache", action="store_true", help="Skip drucksache fetch")
    parser.add_argument("--skip-text", action="store_true", help="Skip text fetch")
    args = parser.parse_args()

    # Setup
    cfg = load_config()
    client = DipClient(cfg)

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = connect(DbConfig(path=DB_PATH))
    init_db(conn)

    print("=" * 50)
    print("Crawlify Update Script")
    print("=" * 50)
    print_summary(conn)

    # 1. Fetch and normalize vorgänge
    if not args.skip_vorgang:
        from crawlify.db import upsert_vorgang
        fetch_and_normalize_vorgaenge(client, conn, RAW_DIR, STATE_PATH)

    # 2. Fetch drucksachen
    if not args.skip_drucksache:
        if args.full:
            vorgang_ids = [r["vorgang_id"] for r in conn.execute(
                "SELECT vorgang_id FROM vorgang"
            ).fetchall()]
        else:
            vorgang_ids = get_vorgaenge_without_drucksachen(conn, args.limit)

        if vorgang_ids:
            fetch_drucksachen_for_vorgaenge(client, conn, vorgang_ids)
        else:
            print("\n=== 2. No new vorgänge need drucksachen ===")

    # 3. Fetch texts
    if not args.skip_text:
        fetch_drucksache_texts(client, conn)

    print("\n" + "=" * 50)
    print("Update complete!")
    print_summary(conn)


if __name__ == "__main__":
    main()
