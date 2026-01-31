from __future__ import annotations

from pathlib import Path
from typing import Optional

from .config import load_config
from .dip_client import DipClient, write_page_raw
from .storage import CursorState, load_cursor_state, save_cursor_state


def ingest_vorgang_kleine_anfrage(
    raw_dir: Path, state_path: Path, start_cursor: Optional[str] = None
) -> int:
    cfg = load_config()
    client = DipClient(cfg)

    state = load_cursor_state(state_path)
    cursor = start_cursor or state.cursor

    total_pages = 0
    for idx, page in enumerate(client.fetch_vorgang_kleine_anfrage_pages(cursor=cursor)):
        write_page_raw(page, raw_dir, idx, prefix="vorgang")
        save_cursor_state(state_path, CursorState(cursor=page.cursor))
        total_pages += 1

    return total_pages
