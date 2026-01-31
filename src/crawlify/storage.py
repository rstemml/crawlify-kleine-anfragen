from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class CursorState:
    cursor: Optional[str]


def load_cursor_state(path: Path) -> CursorState:
    if not path.exists():
        return CursorState(cursor=None)
    data = json.loads(path.read_text())
    return CursorState(cursor=data.get("cursor"))


def save_cursor_state(path: Path, state: CursorState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"cursor": state.cursor}
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2))
