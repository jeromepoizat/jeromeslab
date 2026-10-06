"""Small, provider-independent boundary for Europe PMC publication search."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SEARCH_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
ADAPTER_VERSION = "1"
PAGE_SIZE = 1000
MAX_RECORDS_PER_QUERY = 5000


class SourceSearchError(ValueError):
    """A source request or response could not be used safely."""


@dataclass(frozen=True)
class SearchPage:
    request_url: str
    raw: bytes
    total_hits: int
    next_cursor_mark: str | None
    records: list[dict[str, Any]]


class SourceSearchClient(Protocol):
    def fetch(self, query: str, cursor_mark: str, page_size: int = PAGE_SIZE) -> SearchPage: ...


class EuropePMCClient:
    """Fetch one cursor page, retrying transient source errors without hidden searches."""

    def fetch(self, query: str, cursor_mark: str, page_size: int = PAGE_SIZE) -> SearchPage:
        request_url = SEARCH_URL + "?" + urlencode({
            "query": query,
            "format": "json",
            "resultType": "core",
            "pageSize": page_size,
            "cursorMark": cursor_mark,
        })
        request = Request(request_url, headers={"User-Agent": "JeromesLaboratory/0.1 (local research app)", "Accept": "application/json"})
        raw: bytes | None = None
        for attempt in range(3):
            try:
                with urlopen(request, timeout=45) as response:
                    raw = response.read(20_000_001)
                break
            except HTTPError as error:
                if error.code not in {429, 500, 502, 503, 504} or attempt == 2:
                    raise SourceSearchError(f"Europe PMC returned HTTP {error.code}.") from error
                retry_after = error.headers.get("Retry-After", "")
                delay = min(10.0, float(retry_after)) if retry_after.isdigit() else 2.0 ** attempt
                time.sleep(delay)
            except (URLError, TimeoutError) as error:
                if attempt == 2:
                    raise SourceSearchError("Europe PMC could not be reached after three attempts.") from error
                time.sleep(2.0 ** attempt)
        if raw is None or len(raw) > 20_000_000:
            raise SourceSearchError("Europe PMC returned an unexpectedly large or empty page.")
        try:
            payload = json.loads(raw)
            total_hits = payload["hitCount"]
            results = payload["resultList"]["result"]
            next_cursor = payload.get("nextCursorMark")
        except (ValueError, KeyError, TypeError) as error:
            raise SourceSearchError("Europe PMC returned an invalid search response.") from error
        if not isinstance(total_hits, int) or total_hits < 0 or not isinstance(results, list):
            raise SourceSearchError("Europe PMC returned invalid result counts or records.")
        if not all(isinstance(record, dict) for record in results):
            raise SourceSearchError("Europe PMC returned a malformed publication record.")
        if next_cursor is not None and not isinstance(next_cursor, str):
            raise SourceSearchError("Europe PMC returned an invalid page cursor.")
        return SearchPage(request_url, raw, total_hits, next_cursor, results)
