from __future__ import annotations

from typing import Dict, List

import requests

from crawlify.config import Config
from crawlify.dip_client import DipClient


class FakeResponse:
    def __init__(self, status_code: int, payload: Dict):
        self.status_code = status_code
        self._payload = payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)

    def json(self) -> Dict:
        return self._payload


class FakeSession:
    def __init__(self, responses: List[FakeResponse]):
        self._responses = responses
        self.calls = 0

    def get(self, url, params=None, timeout=None):
        resp = self._responses[self.calls]
        self.calls += 1
        return resp


def _cfg() -> Config:
    return Config(
        dip_base_url="https://example.test/api/v1",
        dip_api_key="test",
        request_timeout_s=1,
        max_retries=0,
        backoff_base_s=0.01,
        page_size=100,
    )


def test_pagination_cursor_stops() -> None:
    responses = [
        FakeResponse(200, {"documents": [{"id": 1}], "cursor": "abc"}),
        FakeResponse(200, {"documents": [{"id": 2}], "cursor": None}),
    ]
    client = DipClient(_cfg(), session=FakeSession(responses))
    pages = list(client.fetch_vorgang_kleine_anfrage_pages())
    assert len(pages) == 2
    assert pages[0].items[0]["id"] == 1
    assert pages[1].items[0]["id"] == 2


def test_retryable_status_raises_after_max_retries() -> None:
    responses = [FakeResponse(500, {"error": "fail"})]
    client = DipClient(_cfg(), session=FakeSession(responses))
    try:
        list(client.fetch_vorgang_kleine_anfrage_pages())
        assert False, "expected error"
    except RuntimeError:
        assert True
