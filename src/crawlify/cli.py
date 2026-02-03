from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, Iterator, List, Optional

from .config import load_config
from .db import (
    DbConfig,
    connect,
    init_db,
    upsert_drucksache,
    upsert_drucksache_text,
    upsert_vorgang,
)
from .dip_client import DipClient, EmptyResponseError, write_page_raw
from .embeddings import SentenceTransformerProvider
from .ingest import ingest_vorgang_kleine_anfrage
from .progress import FetchProgress, NormalizeProgress
from .normalize import (
    normalize_drucksache,
    normalize_drucksache_text,
    normalize_vorgang,
)
from .search import load_embeddings, rank_by_similarity


def _iter_raw_items(raw_dir: Path, pattern: str, keys: Iterable[str]) -> Iterator[dict]:
    for path in sorted(raw_dir.glob(pattern)):
        payload = json.loads(path.read_text())
        items: Optional[list] = None
        for key in keys:
            val = payload.get(key)
            if isinstance(val, list):
                items = val
                break
        if items is None:
            for val in payload.values():
                if isinstance(val, list):
                    items = val
                    break
        if items is None:
            items = []
        for item in items:
            yield item


def _iter_raw_files_with_items(
    raw_dir: Path, pattern: str, keys: Iterable[str]
) -> Iterator[tuple[Path, list]]:
    """Iterate over files and their items (for progress tracking)."""
    for path in sorted(raw_dir.glob(pattern)):
        payload = json.loads(path.read_text())
        items: Optional[list] = None
        for key in keys:
            val = payload.get(key)
            if isinstance(val, list):
                items = val
                break
        if items is None:
            for val in payload.values():
                if isinstance(val, list):
                    items = val
                    break
        if items is None:
            items = []
        yield path, items


def _iter_vorgang_ids(db_path: Path) -> List[str]:
    conn = connect(DbConfig(path=db_path))
    init_db(conn)
    rows = conn.execute("SELECT vorgang_id FROM vorgang").fetchall()
    return [row["vorgang_id"] for row in rows]


def _iter_drucksache_ids(db_path: Path) -> List[str]:
    conn = connect(DbConfig(path=db_path))
    init_db(conn)
    rows = conn.execute("SELECT drucksache_id FROM drucksache").fetchall()
    return [row["drucksache_id"] for row in rows]


def cmd_fetch_vorgang(args: argparse.Namespace) -> None:
    progress = FetchProgress()

    def on_progress(idx, page, total_from_api):
        progress.update(len(page.items), total_from_api)
        progress.print_status()

    try:
        total = ingest_vorgang_kleine_anfrage(
            raw_dir=Path(args.raw_dir),
            state_path=Path(args.state_path),
            start_cursor=args.start_cursor,
            on_progress=on_progress,
        )
        progress.print_summary()
    except EmptyResponseError as e:
        print(f"\n\nError: {e}")
        print("\nTo fix this:")
        print("  1. Run: crawlify solve-challenge --visible")
        print("  2. Solve the captcha in the browser")
        print("  3. Run fetch-vorgang again")
        raise SystemExit(1)


def cmd_fetch_drucksache(args: argparse.Namespace) -> None:
    cfg = load_config()
    client = DipClient(cfg)
    progress = FetchProgress()

    vorgang_ids = _iter_vorgang_ids(Path(args.db_path))
    total_vorgaenge = len(vorgang_ids)

    try:
        total_pages = 0
        for v_idx, vorgang_id in enumerate(vorgang_ids):
            params = {args.filter_key: vorgang_id}
            for idx, page in enumerate(client.fetch_drucksache_pages(params, cursor=None)):
                write_page_raw(
                    page, Path(args.raw_dir), total_pages + idx, prefix="drucksache"
                )
                total_pages += 1
                progress.update(len(page.items))
                # Show vorgang progress in status
                progress.print_status()
                print(f" | Vorgang {v_idx + 1}/{total_vorgaenge}", end="", flush=True)

        progress.print_summary()
    except EmptyResponseError as e:
        print(f"\n\nError: {e}")
        print("\nRun: crawlify solve-challenge --visible")
        raise SystemExit(1)


def cmd_fetch_drucksache_text(args: argparse.Namespace) -> None:
    cfg = load_config()
    client = DipClient(cfg)
    progress = FetchProgress()

    drucksache_ids = _iter_drucksache_ids(Path(args.db_path))
    total_drucksachen = len(drucksache_ids)

    try:
        total_pages = 0
        for d_idx, drucksache_id in enumerate(drucksache_ids):
            params = {args.filter_key: drucksache_id}
            for idx, page in enumerate(
                client.fetch_drucksache_text_pages(params, cursor=None)
            ):
                write_page_raw(
                    page, Path(args.raw_dir), total_pages + idx, prefix="drucksache_text"
                )
                total_pages += 1
                progress.update(len(page.items))
                progress.print_status()
                print(f" | Drucksache {d_idx + 1}/{total_drucksachen}", end="", flush=True)

        progress.print_summary()
    except EmptyResponseError as e:
        print(f"\n\nError: {e}")
        print("\nRun: crawlify solve-challenge --visible")
        raise SystemExit(1)


def cmd_normalize_vorgang(args: argparse.Namespace) -> None:
    raw_dir = Path(args.raw_dir)
    db_path = Path(args.db_path)

    conn = connect(DbConfig(path=db_path))
    init_db(conn)

    # Count files for progress
    files = list(raw_dir.glob("vorgang_page_*.json"))
    progress = NormalizeProgress(total_files=len(files))

    for path, items in _iter_raw_files_with_items(
        raw_dir,
        "vorgang_page_*.json",
        keys=("documents", "vorgang", "results", "data", "items"),
    ):
        new_count = 0
        for item in items:
            row = normalize_vorgang(item)
            if not row["vorgang_id"] or not row["vorgangstyp"]:
                progress.update(skipped=1)
                continue
            upsert_vorgang(conn, row)
            new_count += 1
        progress.update(new=new_count)
        progress.file_done()
        progress.print_status()

    progress.print_summary()


def cmd_normalize_drucksache(args: argparse.Namespace) -> None:
    raw_dir = Path(args.raw_dir)
    db_path = Path(args.db_path)

    conn = connect(DbConfig(path=db_path))
    init_db(conn)

    # Count files for progress
    files = list(raw_dir.glob("drucksache_page_*.json"))
    progress = NormalizeProgress(total_files=len(files))

    for path, items in _iter_raw_files_with_items(
        raw_dir,
        "drucksache_page_*.json",
        keys=("documents", "drucksache", "results", "data", "items"),
    ):
        new_count = 0
        for item in items:
            vorgang_id = item.get("vorgang_id") or item.get("vorgangId") or item.get(
                "vorgang"
            ) or ""
            if not vorgang_id:
                progress.update(skipped=1)
                continue
            row = normalize_drucksache(item, vorgang_id=vorgang_id)
            if not row["drucksache_id"]:
                progress.update(skipped=1)
                continue
            upsert_drucksache(conn, row)
            new_count += 1
        progress.update(new=new_count)
        progress.file_done()
        progress.print_status()

    progress.print_summary()


def cmd_normalize_drucksache_text(args: argparse.Namespace) -> None:
    raw_dir = Path(args.raw_dir)
    db_path = Path(args.db_path)

    conn = connect(DbConfig(path=db_path))
    init_db(conn)

    # Count files for progress
    files = list(raw_dir.glob("drucksache_text_page_*.json"))
    progress = NormalizeProgress(total_files=len(files))

    for path, items in _iter_raw_files_with_items(
        raw_dir,
        "drucksache_text_page_*.json",
        keys=("documents", "drucksache_text", "results", "data", "items"),
    ):
        new_count = 0
        for item in items:
            row = normalize_drucksache_text(item)
            if not row["drucksache_id"]:
                progress.update(skipped=1)
                continue
            upsert_drucksache_text(conn, row)
            new_count += 1
        progress.update(new=new_count)
        progress.file_done()
        progress.print_status()

    progress.print_summary()


def cmd_list_vorgang_ids(args: argparse.Namespace) -> None:
    conn = connect(DbConfig(path=Path(args.db_path)))
    init_db(conn)

    rows = conn.execute(
        """
        SELECT vorgang_id, titel, datum
        FROM vorgang
        ORDER BY datum DESC
        LIMIT ?
        """,
        (args.limit,),
    ).fetchall()

    for row in rows:
        titel = row["titel"] or ""
        datum = row["datum"] or ""
        print(f"{row['vorgang_id']} | {datum} | {titel}")


def cmd_embed_vorgang(args: argparse.Namespace) -> None:
    import time

    conn = connect(DbConfig(path=Path(args.db_path)))
    init_db(conn)

    rows = conn.execute(
        """
        SELECT vorgang_id, titel, abstrakt
        FROM vorgang
        WHERE embedding_json IS NULL OR embedding_version IS NULL
        LIMIT ?
        """,
        (args.limit,),
    ).fetchall()

    if not rows:
        print("no rows to embed")
        return

    print(f"Loading model: {args.model}...")
    start_time = time.time()
    provider = SentenceTransformerProvider(args.model)
    print(f"Model loaded in {time.time() - start_time:.1f}s")

    print("Preparing texts...")
    prepared = []
    for row in rows:
        text = _build_embedding_text(conn, row)
        if text.strip():
            prepared.append((row, text))

    if not prepared:
        print("no non-empty texts to embed")
        return

    print(f"Embedding {len(prepared)} texts...")
    start_time = time.time()
    texts = [item[1] for item in prepared]
    result = provider.embed(texts)
    embed_time = time.time() - start_time

    print(f"Saving to database...")
    for (row, text), vec in zip(prepared, result.vectors):
        conn.execute(
            """
            UPDATE vorgang
            SET embedding_json = ?, embedding_version = ?, embedding_text = ?
            WHERE vorgang_id = ?
            """,
            (
                json.dumps(vec, ensure_ascii=True),
                result.model,
                text,
                row["vorgang_id"],
            ),
        )
    conn.commit()

    rate = len(prepared) / embed_time if embed_time > 0 else 0
    print(f"Done: {len(prepared)} embeddings in {embed_time:.1f}s ({rate:.1f} texts/s)")


def cmd_search_vorgang(args: argparse.Namespace) -> None:
    conn = connect(DbConfig(path=Path(args.db_path)))
    init_db(conn)

    items = load_embeddings(conn)
    if not items:
        print("no embeddings found; run crawlify embed-vorgang first")
        return

    provider = SentenceTransformerProvider(args.model)
    result = provider.embed([args.query])
    query_vec = result.vectors[0]

    results = rank_by_similarity(query_vec, items, limit=args.limit)
    for vorgang_id, score, meta in results:
        title = meta.get("titel") or ""
        datum = meta.get("datum") or ""
        print(f"{score:0.4f} | {vorgang_id} | {datum} | {title}")


def cmd_debug_dip_filters(args: argparse.Namespace) -> None:
    cfg = load_config()
    client = DipClient(cfg)

    keys = [k.strip() for k in args.keys.split(",") if k.strip()]
    for key in keys:
        params = {key: args.id}
        if args.endpoint == "drucksache":
            pages = client.fetch_drucksache_pages(params, cursor=None)
        else:
            pages = client.fetch_drucksache_text_pages(params, cursor=None)

        try:
            page = next(pages)
        except StopIteration:
            print(f"{key}: no pages")
            continue
        count = len(page.items)
        cursor = page.cursor
        print(f"{key}: items={count} cursor={bool(cursor)}")


def cmd_solve_challenge(args: argparse.Namespace) -> None:
    """Manually solve Enodia bot challenge and save cookies."""
    from .browser import solve_enodia_challenge, save_cookies, load_cookies

    state_path = Path(args.state_path)

    # Build challenge URL if not provided
    if args.url:
        challenge_url = args.url
    else:
        # Construct a default challenge URL for the vorgang endpoint
        cfg = load_config()
        base = cfg.dip_base_url.rstrip("/")
        # Use urllib to properly encode the redirect URL
        from urllib.parse import quote

        redirect_path = f"/api/v1/vorgang?f.vorgangstyp=Kleine+Anfrage&apikey={cfg.dip_api_key}&size=1"
        challenge_url = f"{base.replace('/api/v1', '')}/.enodia/challenge?redirect={quote(redirect_path)}"

    print(f"Solving challenge: {challenge_url[:80]}...")

    try:
        cookie_data = solve_enodia_challenge(
            challenge_url,
            timeout_ms=args.timeout * 1000,
            headless=not args.visible,
        )
        save_cookies(cookie_data, state_path)
        print(f"Successfully solved challenge!")
        print(f"Extracted {len(cookie_data.cookies)} cookies, saved to {state_path}")
    except ImportError as e:
        print(f"Error: {e}")
        print("Install playwright: pip install 'crawlify-kleine-anfragen[browser]'")
        print("Then run: playwright install chromium")
        raise SystemExit(1)
    except TimeoutError as e:
        print(f"Timeout: {e}")
        print("Try running with --visible to see the browser and solve manually if needed.")
        raise SystemExit(1)


def cmd_clear_cookies(args: argparse.Namespace) -> None:
    """Clear cached cookies."""
    state_path = Path(args.state_path)
    if state_path.exists():
        state_path.unlink()
        print(f"Cleared cookies at {state_path}")
    else:
        print(f"No cookies file at {state_path}")


def _build_embedding_text(conn, row, max_chars: int = 8000) -> str:
    parts = []
    if row["titel"]:
        parts.append(row["titel"])
    if row["abstrakt"]:
        parts.append(row["abstrakt"])

    texts = conn.execute(
        """
        SELECT dt.volltext
        FROM drucksache_text dt
        JOIN drucksache d ON d.drucksache_id = dt.drucksache_id
        WHERE d.vorgang_id = ?
        """,
        (row["vorgang_id"],),
    ).fetchall()

    for t in texts:
        if not t["volltext"]:
            continue
        parts.append(t["volltext"])
        if sum(len(p) for p in parts) >= max_chars:
            break

    text = "\n\n".join(parts)
    return text[:max_chars]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="crawlify")
    subparsers = parser.add_subparsers(dest="command", required=True)

    cmd = subparsers.add_parser("fetch-vorgang", help="Fetch vorgang pages")
    cmd.add_argument("--raw-dir", default="data/raw/vorgang")
    cmd.add_argument("--state-path", default="state/vorgang_cursor.json")
    cmd.add_argument("--start-cursor", default=None)
    cmd.set_defaults(func=cmd_fetch_vorgang)

    cmd = subparsers.add_parser("fetch-drucksache", help="Fetch drucksache pages")
    cmd.add_argument("--db-path", default="data/db/crawlify.sqlite")
    cmd.add_argument("--raw-dir", default="data/raw/drucksache")
    cmd.add_argument(
        "--filter-key",
        default="f.vorgang_id",
        help="DIP filter key to link drucksache to vorgang (e.g. f.vorgang_id)",
    )
    cmd.set_defaults(func=cmd_fetch_drucksache)

    cmd = subparsers.add_parser(
        "fetch-drucksache-text", help="Fetch drucksache text pages"
    )
    cmd.add_argument("--db-path", default="data/db/crawlify.sqlite")
    cmd.add_argument("--raw-dir", default="data/raw/drucksache_text")
    cmd.add_argument(
        "--filter-key",
        default="f.drucksache_id",
        help="DIP filter key to link drucksache text to drucksache (e.g. f.drucksache_id)",
    )
    cmd.set_defaults(func=cmd_fetch_drucksache_text)

    cmd = subparsers.add_parser("normalize-vorgang", help="Normalize vorgang JSON")
    cmd.add_argument("--raw-dir", default="data/raw/vorgang")
    cmd.add_argument("--db-path", default="data/db/crawlify.sqlite")
    cmd.set_defaults(func=cmd_normalize_vorgang)

    cmd = subparsers.add_parser(
        "normalize-drucksache", help="Normalize drucksache JSON"
    )
    cmd.add_argument("--raw-dir", default="data/raw/drucksache")
    cmd.add_argument("--db-path", default="data/db/crawlify.sqlite")
    cmd.set_defaults(func=cmd_normalize_drucksache)

    cmd = subparsers.add_parser(
        "normalize-drucksache-text", help="Normalize drucksache text JSON"
    )
    cmd.add_argument("--raw-dir", default="data/raw/drucksache_text")
    cmd.add_argument("--db-path", default="data/db/crawlify.sqlite")
    cmd.set_defaults(func=cmd_normalize_drucksache_text)

    cmd = subparsers.add_parser(
        "list-vorgang-ids", help="List vorgang IDs from the database"
    )
    cmd.add_argument("--db-path", default="data/db/crawlify.sqlite")
    cmd.add_argument("--limit", type=int, default=20)
    cmd.set_defaults(func=cmd_list_vorgang_ids)

    cmd = subparsers.add_parser("embed-vorgang", help="Embed vorgang entries")
    cmd.add_argument("--db-path", default="data/db/crawlify.sqlite")
    cmd.add_argument("--model", default="intfloat/multilingual-e5-small")
    cmd.add_argument("--limit", type=int, default=1000)
    cmd.set_defaults(func=cmd_embed_vorgang)

    cmd = subparsers.add_parser("search-vorgang", help="Search by embedding")
    cmd.add_argument("query")
    cmd.add_argument("--db-path", default="data/db/crawlify.sqlite")
    cmd.add_argument("--model", default="intfloat/multilingual-e5-small")
    cmd.add_argument("--limit", type=int, default=10)
    cmd.set_defaults(func=cmd_search_vorgang)

    cmd = subparsers.add_parser(
        "debug-dip-filters", help="Try filter keys for a DIP endpoint"
    )
    cmd.add_argument(
        "--endpoint",
        choices=["drucksache", "drucksache-text"],
        required=True,
    )
    cmd.add_argument("--id", required=True, help="vorgang_id or drucksache_id")
    cmd.add_argument(
        "--keys",
        default="f.vorgang_id,f.vorgangId,f.drucksache_id,f.drucksacheId",
        help="Comma-separated list of filter keys to try",
    )
    cmd.set_defaults(func=cmd_debug_dip_filters)

    cmd = subparsers.add_parser(
        "solve-challenge", help="Solve Enodia bot challenge and save cookies"
    )
    cmd.add_argument(
        "--url",
        default=None,
        help="Challenge URL (auto-generated if not provided)",
    )
    cmd.add_argument(
        "--state-path",
        default="state/cookies.json",
        help="Path to save cookies",
    )
    cmd.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Timeout in seconds for challenge solving",
    )
    cmd.add_argument(
        "--visible",
        action="store_true",
        help="Show browser window (for debugging or manual solving)",
    )
    cmd.set_defaults(func=cmd_solve_challenge)

    cmd = subparsers.add_parser("clear-cookies", help="Clear cached cookies")
    cmd.add_argument(
        "--state-path",
        default="state/cookies.json",
        help="Path to cookies file",
    )
    cmd.set_defaults(func=cmd_clear_cookies)

    return parser


def main(argv: Optional[list[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
