from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    dip_base_url: str
    dip_api_key: str
    request_timeout_s: float
    max_retries: int
    backoff_base_s: float
    page_size: int


def load_config() -> Config:
    return Config(
        dip_base_url=os.getenv("DIP_BASE_URL", "https://search.dip.bundestag.de/api/v1"),
        dip_api_key=os.getenv("DIP_API_KEY", ""),
        request_timeout_s=float(os.getenv("DIP_TIMEOUT_S", "20")),
        max_retries=int(os.getenv("DIP_MAX_RETRIES", "5")),
        backoff_base_s=float(os.getenv("DIP_BACKOFF_BASE_S", "0.6")),
        page_size=int(os.getenv("DIP_PAGE_SIZE", "100")),
    )
