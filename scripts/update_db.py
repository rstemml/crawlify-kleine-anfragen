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

Exit Codes:
    0   Success
    1   General error
    2   Already running (lockfile exists)
    3   Authentication error (Enodia cookie invalid)
"""

import argparse
import atexit
import fcntl
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from crawlify.config import load_config
from crawlify.db import DbConfig, connect, init_db, upsert_vorgang, upsert_drucksache, upsert_drucksache_text
from crawlify.dip_client import DipClient, EmptyResponseError, write_page_raw
from crawlify.ingest import ingest_vorgang_kleine_anfrage
from crawlify.normalize import normalize_vorgang, normalize_drucksache, normalize_drucksache_text
from crawlify.progress import FetchProgress
from crawlify.storage import CursorState, load_cursor_state, save_cursor_state

# Paths
BASE_DIR = Path(__file__).parent.parent
RAW_DIR = BASE_DIR / "data" / "raw" / "vorgang"
DB_PATH = BASE_DIR / "data" / "db" / "crawlify.sqlite"
STATE_PATH = BASE_DIR / "state" / "vorgang_cursor.json"
LOCK_PATH = BASE_DIR / "state" / "update_db.lock"

# Configure logging
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "update_db.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class LockFile:
    """Context manager for file-based locking to prevent concurrent runs."""
    
    def __init__(self, lock_path: Path):
        self.lock_path = lock_path
        self.lock_file = None
    
    def __enter__(self):
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_file = open(self.lock_path, 'w')
        try:
            fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.lock_file.write(str(sys.argv))
            self.lock_file.flush()
            return self
        except BlockingIOError:
            self.lock_file.close()
            raise RuntimeError("Another instance is already running")
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.lock_file:
            fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)
            self.lock_file.close()
            try:
                self.lock_path.unlink()
            except FileNotFoundError:
                pass


def fetch_and_normalize_vorgaenge(client: DipClient, conn, raw_dir: Path, state_path: Path) -> int:
    """Fetch new vorgänge and normalize them into the database."""
    logger.info("=== 1. Fetching new Vorgänge ===")

    state = load_cursor_state(state_path)
    cursor = state.cursor

    if cursor:
        logger.info(f"Resuming from cursor: {cursor[:50]}...")
    else:
        logger.info("Starting fresh (no cursor)")

    total_items = 0
    page_idx = 0
    progress = FetchProgress()

    try:
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

            # Progress tracking
            total_from_api = page.raw.get("numFound")
            progress.update(len(page.items), total_from_api)
            progress.print_status()

            page_idx += 1

            if not page.cursor:
                break

        progress.print_summary()
        conn.commit()
        logger.info(f"Fetched and normalized {total_items} vorgänge")
        return total_items

    except EmptyResponseError as e:
        logger.error(f"\nAPI Error: {e}")
        logger.error("Run: crawlify solve-challenge --visible")
        raise


def fetch_drucksachen_for_vorgaenge(client: DipClient, conn, vorgang_ids: list) -> int:
    """Fetch drucksachen for given vorgänge using drucksachetyp filter."""
    logger.info(f"=== 2. Fetching Drucksachen for {len(vorgang_ids)} Vorgänge ===")

    target_set = set(str(v) for v in vorgang_ids)
    total_saved = 0
    progress = FetchProgress()

    try:
        for doc_type in ["Kleine Anfrage", "Antwort"]:
            logger.info(f"  Fetching {doc_type}...")

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
                num_found = data.get("numFound", 0)

                # Validate response
                if not items and num_found > 0:
                    raise EmptyResponseError(
                        f"API returned empty documents but numFound={num_found}. "
                        "Run: crawlify solve-challenge --visible"
                    )

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

                progress.update(len(items))
                progress.print_status()
                print(f" | {doc_type}", end="", flush=True)

                page_num += 1
                if not cursor:
                    break

            logger.info(f"\n    Found {len(found_vorgaenge)} vorgänge, saved {total_saved} drucksachen")

        conn.commit()
        return total_saved

    except EmptyResponseError as e:
        logger.error(f"\nAPI Error: {e}")
        logger.error("Run: crawlify solve-challenge --visible")
        raise


def fetch_drucksache_texts(client: DipClient, conn) -> int:
    """Fetch full text for drucksachen that don't have it yet."""
    logger.info("=== 3. Fetching Drucksache Texts ===")

    # Get drucksachen without text
    rows = conn.execute("""
        SELECT d.drucksache_id
        FROM drucksache d
        LEFT JOIN drucksache_text dt ON d.drucksache_id = dt.drucksache_id
        WHERE dt.drucksache_id IS NULL
    """).fetchall()

    drucksache_ids = [r["drucksache_id"] for r in rows]
    logger.info(f"  {len(drucksache_ids)} drucksachen without text")

    if not drucksache_ids:
        return 0

    total_saved = 0
    progress = FetchProgress(total_expected=len(drucksache_ids))

    try:
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
                    num_found = data.get("numFound", 0)
                    items = data.get("documents", [])

                    # Validate response (only if numFound > 0)
                    if not items and num_found > 0:
                        raise EmptyResponseError(
                            f"API returned empty documents but numFound={num_found}. "
                            "Run: crawlify solve-challenge --visible"
                        )

                    if items:
                        row = normalize_drucksache_text(items[0])
                        if row["drucksache_id"] and row["volltext"]:
                            upsert_drucksache_text(conn, row)
                            total_saved += 1
                            logger.debug(f"    {ds_id}: {len(row['volltext'])} chars")

            except EmptyResponseError:
                raise  # Re-raise auth errors
            except Exception as e:
                logger.warning(f"    {ds_id}: Error - {e}")

            progress.update(1)
            progress.print_status()

        progress.print_summary()
        conn.commit()
        logger.info(f"  Saved {total_saved} texts")
        return total_saved

    except EmptyResponseError as e:
        logger.error(f"\nAPI Error: {e}")
        logger.error("Run: crawlify solve-challenge --visible")
        raise


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


def log_summary(conn):
    """Log database summary."""
    logger.info("=== Datenbank-Übersicht ===")
    for table in ["vorgang", "drucksache", "drucksache_text"]:
        count = conn.execute(f"SELECT COUNT(*) as c FROM {table}").fetchone()["c"]
        logger.info(f"  {table}: {count}")


def main() -> int:
    """Main entry point. Returns exit code."""
    parser = argparse.ArgumentParser(description="Update crawlify database")
    parser.add_argument("--full", action="store_true", help="Fetch drucksachen for ALL vorgänge")
    parser.add_argument("--limit", type=int, default=50, help="Limit vorgänge for drucksache fetch")
    parser.add_argument("--skip-vorgang", action="store_true", help="Skip vorgang fetch")
    parser.add_argument("--skip-drucksache", action="store_true", help="Skip drucksache fetch")
    parser.add_argument("--skip-text", action="store_true", help="Skip text fetch")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        with LockFile(LOCK_PATH):
            logger.info("=" * 50)
            logger.info("Crawlify Update Script started")
            logger.info("=" * 50)

            # Setup
            cfg = load_config()
            client = DipClient(cfg)

            RAW_DIR.mkdir(parents=True, exist_ok=True)
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            STATE_PATH.parent.mkdir(parents=True, exist_ok=True)

            conn = connect(DbConfig(path=DB_PATH))
            init_db(conn)

            log_summary(conn)

            # 1. Fetch and normalize vorgänge
            if not args.skip_vorgang:
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
                    logger.info("=== 2. No new vorgänge need drucksachen ===")

            # 3. Fetch texts
            if not args.skip_text:
                fetch_drucksache_texts(client, conn)

            logger.info("=" * 50)
            logger.info("Update complete!")
            log_summary(conn)
            return 0

    except RuntimeError as e:
        if "already running" in str(e).lower():
            logger.error(f"Cannot start: {e}")
            return 2
        logger.exception("Runtime error occurred")
        return 1
    except EmptyResponseError as e:
        logger.error(f"\nAuthentication Error: {e}")
        logger.error("\nTo fix this:")
        logger.error("  1. Run: crawlify solve-challenge --visible")
        logger.error("  2. Solve the captcha in the browser")
        logger.error("  3. Run this script again")
        return 3
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
