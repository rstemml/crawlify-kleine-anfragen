from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from .config import load_config
from .dip_client import DipClient, EmptyResponseError, Page, write_page_raw
from .storage import CursorState, load_cursor_state, save_cursor_state

# Callback type: (page_index, page, total_from_api) -> None
ProgressCallback = Callable[[int, Page, Optional[int]], None]


def ingest_vorgang_kleine_anfrage(
    raw_dir: Path,
    state_path: Path,
    start_cursor: Optional[str] = None,
    on_progress: Optional[ProgressCallback] = None,
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

        # Report progress
        if on_progress:
            total_from_api = page.raw.get("numFound")
            on_progress(idx, page, total_from_api)

    return total_pages
