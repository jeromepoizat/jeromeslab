"""The source adapter requests cursor pages and rejects malformed responses."""

import json
from typing import Self
from urllib.parse import parse_qs, urlparse
from urllib.request import Request

import pytest

from jeromes_laboratory.sources import europe_pmc


class FakeHTTPResponse:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self, limit: int) -> bytes:
        assert limit == 20_000_001
        return self.content


def test_source_client_requests_core_cursor_page(monkeypatch: pytest.MonkeyPatch) -> None:
    requested: list[str] = []
    raw = json.dumps({
        "hitCount": 2, "nextCursorMark": "cursor-next",
        "resultList": {"result": [{"source": "MED", "id": "1"}]},
    }).encode()

    def fake_urlopen(request: Request, timeout: int) -> FakeHTTPResponse:
        requested.append(request.full_url)
        assert timeout == 45
        return FakeHTTPResponse(raw)

    monkeypatch.setattr(europe_pmc, "urlopen", fake_urlopen)
    page = europe_pmc.EuropePMCClient().fetch('TITLE_ABS:("myostatin" AND peptid*)', "*", 100)
    params = parse_qs(urlparse(requested[0]).query)
    assert params["query"] == ['TITLE_ABS:("myostatin" AND peptid*)']
    assert params["cursorMark"] == ["*"]
    assert params["pageSize"] == ["100"]
    assert params["resultType"] == ["core"]
    assert page.raw == raw
    assert page.next_cursor_mark == "cursor-next"
    assert page.records[0]["id"] == "1"


def test_source_client_rejects_malformed_page(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        europe_pmc, "urlopen", lambda *_args, **_kwargs: FakeHTTPResponse(b"{}")
    )
    with pytest.raises(europe_pmc.SourceSearchError, match="invalid search response"):
        europe_pmc.EuropePMCClient().fetch("myostatin", "*")
