"""Browser automation for solving Enodia bot protection challenges."""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

ENODIA_CHALLENGE_PATH = "/.enodia/challenge"


@dataclass
class CookieData:
    """Cookie data with optional expiry tracking."""

    cookies: Dict[str, str]
    domain: str
    extracted_at: float  # Unix timestamp

    def to_dict(self) -> dict:
        return {
            "cookies": self.cookies,
            "domain": self.domain,
            "extracted_at": self.extracted_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CookieData":
        return cls(
            cookies=data["cookies"],
            domain=data["domain"],
            extracted_at=data["extracted_at"],
        )


def is_challenge_url(url: str) -> bool:
    """Check if URL is an Enodia challenge redirect."""
    return ENODIA_CHALLENGE_PATH in url


def solve_enodia_challenge(
    challenge_url: str,
    timeout_ms: int = 60000,
    headless: bool = True,
) -> CookieData:
    """
    Solve Enodia bot protection challenge using Playwright.

    Opens the challenge URL in a browser, waits for the challenge to be solved
    (detected by URL changing away from the challenge path), then extracts cookies.

    Args:
        challenge_url: The full challenge URL (including redirect parameter)
        timeout_ms: Maximum time to wait for challenge resolution
        headless: Whether to run browser in headless mode

    Returns:
        CookieData with extracted cookies

    Raises:
        ImportError: If playwright is not installed
        TimeoutError: If challenge is not solved within timeout
        RuntimeError: If challenge solving fails
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError
    except ImportError:
        raise ImportError(
            "playwright is required for challenge solving. "
            "Install with: pip install 'crawlify-kleine-anfragen[browser]' && playwright install chromium"
        )

    logger.info(f"Solving Enodia challenge: {challenge_url[:80]}...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()

        try:
            # Navigate to challenge URL
            page.goto(challenge_url, timeout=timeout_ms)

            # Wait for URL to change away from challenge path
            # This indicates the challenge was solved and we're redirected
            logger.info("Waiting for challenge to be solved...")

            start_time = time.time()
            while ENODIA_CHALLENGE_PATH in page.url:
                if (time.time() - start_time) * 1000 > timeout_ms:
                    raise TimeoutError(
                        f"Challenge not solved within {timeout_ms}ms. "
                        "The challenge may require manual interaction."
                    )
                page.wait_for_timeout(500)  # Check every 500ms

            logger.info(f"Challenge solved, redirected to: {page.url[:80]}...")

            # Extract cookies from browser context
            browser_cookies = context.cookies()
            cookies_dict = {c["name"]: c["value"] for c in browser_cookies}

            # Extract domain from URL
            from urllib.parse import urlparse

            parsed = urlparse(challenge_url)
            domain = parsed.netloc

            cookie_data = CookieData(
                cookies=cookies_dict,
                domain=domain,
                extracted_at=time.time(),
            )

            logger.info(f"Extracted {len(cookies_dict)} cookies from {domain}")
            return cookie_data

        except PWTimeoutError as e:
            raise TimeoutError(f"Playwright timeout: {e}")
        finally:
            browser.close()


def save_cookies(cookie_data: CookieData, path: Path) -> None:
    """Save cookies to JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cookie_data.to_dict(), indent=2))
    logger.info(f"Saved cookies to {path}")


def load_cookies(path: Path) -> Optional[CookieData]:
    """Load cookies from JSON file if exists."""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        return CookieData.from_dict(data)
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning(f"Failed to load cookies from {path}: {e}")
        return None


def cookies_are_fresh(cookie_data: CookieData, max_age_seconds: float = 3600) -> bool:
    """Check if cookies are still fresh (not too old)."""
    age = time.time() - cookie_data.extracted_at
    return age < max_age_seconds
