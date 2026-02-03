from __future__ import annotations

import json
import logging
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional, Tuple

import requests

from .config import Config

logger = logging.getLogger(__name__)

RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
ENODIA_CHALLENGE_PATH = "/.enodia/challenge"


@dataclass
class Page:
    items: List[Dict[str, Any]]
    cursor: Optional[str]
    raw: Dict[str, Any]


class EmptyResponseError(Exception):
    """Raised when API returns empty documents but numFound > 0 (likely auth issue)."""
    pass


class DipClient:
    def __init__(
        self,
        cfg: Config,
        session: Optional[requests.Session] = None,
        cookie_state_path: Optional[Path] = None,
        auto_solve_challenge: bool = True,
    ) -> None:
        if not cfg.dip_api_key:
            raise ValueError("DIP_API_KEY is required")
        self.cfg = cfg
        self.session = session or requests.Session()
        self.cookie_state_path = cookie_state_path or Path("state/cookies.json")
        self.auto_solve_challenge = auto_solve_challenge
        self._challenge_solved = False

        # Try to load existing cookies on init
        self._load_cached_cookies()

    def _load_cached_cookies(self) -> bool:
        """Load cached cookies from state file if they exist and are fresh."""
        from .browser import load_cookies, cookies_are_fresh

        cookie_data = load_cookies(self.cookie_state_path)
        if cookie_data and cookies_are_fresh(cookie_data):
            self._inject_cookies(cookie_data.cookies, domain=cookie_data.domain)
            logger.info(f"Loaded {len(cookie_data.cookies)} cached cookies")
            return True
        return False

    def _inject_cookies(self, cookies: Dict[str, str], domain: str = "search.dip.bundestag.de") -> None:
        """Inject cookies into the requests session."""
        for name, value in cookies.items():
            self.session.cookies.set(name, value, domain=domain)

    def _handle_challenge(self, challenge_url: str) -> None:
        """Solve Enodia challenge and inject cookies."""
        from .browser import solve_enodia_challenge, save_cookies

        logger.info("Detected Enodia bot challenge, solving...")
        cookie_data = solve_enodia_challenge(challenge_url)
        self._inject_cookies(cookie_data.cookies, domain=cookie_data.domain)
        save_cookies(cookie_data, self.cookie_state_path)
        self._challenge_solved = True

    def fetch_vorgang_kleine_anfrage_pages(
        self, cursor: Optional[str] = None, fail_on_empty: bool = True
    ) -> Iterator[Page]:
        params = {
            "f.vorgangstyp": "Kleine Anfrage",
            "apikey": self.cfg.dip_api_key,
            "size": str(self.cfg.page_size),
        }

        next_cursor = cursor
        while True:
            if next_cursor:
                params["cursor"] = next_cursor
            else:
                params.pop("cursor", None)

            data = self._get_json("/vorgang", params=params)
            items = _extract_items(data)
            next_cursor = _extract_cursor(data)

            # Validate response - empty documents with numFound > 0 indicates auth issue
            num_found = data.get("numFound", 0)
            if fail_on_empty and not items and num_found > 0:
                raise EmptyResponseError(
                    f"API returned empty documents but numFound={num_found}. "
                    "This usually means the Enodia cookie is invalid or expired. "
                    "Run: crawlify solve-challenge --visible"
                )

            yield Page(items=items, cursor=next_cursor, raw=data)

            if not next_cursor:
                break

    def fetch_drucksache_pages(
        self, params: Dict[str, str], cursor: Optional[str] = None, fail_on_empty: bool = True
    ) -> Iterator[Page]:
        base_params = {
            "apikey": self.cfg.dip_api_key,
            "size": str(self.cfg.page_size),
        }
        base_params.update(params)

        next_cursor = cursor
        while True:
            if next_cursor:
                base_params["cursor"] = next_cursor
            else:
                base_params.pop("cursor", None)

            data = self._get_json("/drucksache", params=base_params)
            items = _extract_items(data)
            next_cursor = _extract_cursor(data)

            # Validate response
            num_found = data.get("numFound", 0)
            if fail_on_empty and not items and num_found > 0:
                raise EmptyResponseError(
                    f"API returned empty documents but numFound={num_found}. "
                    "Run: crawlify solve-challenge --visible"
                )

            yield Page(items=items, cursor=next_cursor, raw=data)

            if not next_cursor:
                break

    def fetch_drucksache_text_pages(
        self, params: Dict[str, str], cursor: Optional[str] = None, fail_on_empty: bool = True
    ) -> Iterator[Page]:
        base_params = {
            "apikey": self.cfg.dip_api_key,
            "size": str(self.cfg.page_size),
        }
        base_params.update(params)

        next_cursor = cursor
        while True:
            if next_cursor:
                base_params["cursor"] = next_cursor
            else:
                base_params.pop("cursor", None)

            data = self._get_json("/drucksache-text", params=base_params)
            items = _extract_items(data)
            next_cursor = _extract_cursor(data)

            # Validate response
            num_found = data.get("numFound", 0)
            if fail_on_empty and not items and num_found > 0:
                raise EmptyResponseError(
                    f"API returned empty documents but numFound={num_found}. "
                    "Run: crawlify solve-challenge --visible"
                )

            yield Page(items=items, cursor=next_cursor, raw=data)

            if not next_cursor:
                break

    def _get_json(self, path: str, params: Dict[str, str]) -> Dict[str, Any]:
        url = f"{self.cfg.dip_base_url.rstrip('/')}{path}"
        last_err: Optional[Exception] = None

        for attempt in range(self.cfg.max_retries + 1):
            try:
                resp = self.session.get(
                    url, params=params, timeout=self.cfg.request_timeout_s
                )

                # Check if we got redirected to an Enodia challenge
                if ENODIA_CHALLENGE_PATH in resp.url:
                    if not self.auto_solve_challenge:
                        raise RuntimeError(
                            f"Enodia bot challenge detected at {resp.url}. "
                            "Run 'crawlify solve-challenge' to solve it manually, "
                            "or enable auto_solve_challenge."
                        )
                    if self._challenge_solved:
                        # Already tried solving once this session, don't loop
                        raise RuntimeError(
                            "Enodia challenge persists after solving. "
                            "The challenge may require manual intervention."
                        )
                    self._handle_challenge(resp.url)
                    # Retry the request with new cookies
                    continue

                if resp.status_code in RETRY_STATUS_CODES:
                    raise requests.HTTPError(
                        f"retryable status: {resp.status_code}", response=resp
                    )
                resp.raise_for_status()
                return resp.json()
            except (requests.RequestException, ValueError) as err:
                last_err = err
                if attempt >= self.cfg.max_retries:
                    break
                _sleep_backoff(self.cfg.backoff_base_s, attempt)

        raise RuntimeError("DIP request failed") from last_err


def _sleep_backoff(base_s: float, attempt: int) -> None:
    # exponential backoff with jitter
    jitter = random.random() * 0.2
    delay = base_s * (2**attempt) + jitter
    time.sleep(delay)


def _extract_items(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    # DIP payloads may evolve; try common keys first.
    for key in ("documents", "vorgang", "results", "data", "items"):
        val = payload.get(key)
        if isinstance(val, list):
            return val
    # Fallback: find first list in top-level values
    for val in payload.values():
        if isinstance(val, list):
            return val
    return []


def _extract_cursor(payload: Dict[str, Any]) -> Optional[str]:
    # Common cursor keys in API payloads
    for key in ("cursor", "next_cursor", "nextCursor", "next"):
        val = payload.get(key)
        if isinstance(val, str) and val:
            return val
    return None


def write_page_raw(page: Page, out_dir: Path, index: int, prefix: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{prefix}_page_{index:05d}.json"
    path.write_text(json.dumps(page.raw, ensure_ascii=True, indent=2))
    return path
