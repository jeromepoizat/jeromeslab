"""Bounded, secret-free acquisition of known Europe PMC resources (no LLM)."""

from __future__ import annotations

import http.client
import io
import json
import re
import time
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
from xml.etree import ElementTree as ET

BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest"
MATERIAL_ADAPTER_VERSION = "europe-pmc-materials-v1"
LIMITS = {"metadata": 2_000_000, "full_text": 20_000_000,
          "supplements": 50_000_000, "data_links": 2_000_000}
POLICY: dict[str, object] = {
    "adapter_version": MATERIAL_ADAPTER_VERSION, "byte_limits": LIMITS,
    "supplement_uncompressed_limit": 200_000_000, "supplement_file_limit": 1000,
    "data_links_page_size": 1000, "recursive_fetch": False,
    "formats": ["Europe PMC XML", "supplement ZIP", "data-link JSON"],
}

XML_ACCESS_RULE_VERSION = "europe-pmc-xml-access-v1"


def xml_access_limitation(metadata: dict[str, Any]) -> str | None:
    """Source-specific eligibility, not a claim about access at other publishers."""
    if metadata.get("inEPMC") == "N":
        return "Europe PMC metadata reports no hosted full text. It may be accessible at the publisher or another repository."
    if metadata.get("isOpenAccess") == "N":
        return "This record is outside Europe PMC's supported open-access XML subset. It may be readable elsewhere."
    # Missing or contradictory availability cannot turn a server failure into
    # a no-access decision. Let the endpoint resolve unknown availability.
    return None


@dataclass(frozen=True)
class MaterialResponse:
    status: str
    request_url: str
    http_status: int | None = None
    raw: bytes | None = None
    content_type: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class MaterialClient(Protocol):
    def fetch(self, kind: str, source: str, source_id: str) -> MaterialResponse: ...


class SafeRedirect(HTTPRedirectHandler):
    """Only official HTTPS hosts; never follow source-supplied arbitrary URLs."""

    def redirect_request(
        self, req: Request, fp: Any, code: int, msg: str, headers: Any, newurl: str,
    ) -> Request | None:
        url = urlparse(newurl)
        if url.scheme != "https" or url.hostname not in {"www.ebi.ac.uk", "europepmc.org", "www.europepmc.org"}:
            raise ValueError("The source redirected outside supported HTTPS hosts.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def parse_material(kind: str, raw: bytes) -> dict[str, Any]:
    """Validate expected formats without executing files or fetching external entities."""
    if kind == "full_text":
        # Europe PMC JATS includes external DTD declarations. ElementTree does
        # not fetch these; reject internal entities rather than expanding them.
        if b"\x00" in raw or re.search(br"<!ENTITY\s", raw, re.IGNORECASE):
            raise ValueError("XML entity declarations are not supported.")
        root = ET.fromstring(raw)
        if root.tag.rsplit("}", 1)[-1] not in {"article", "book", "book-part"}:
            raise ValueError("The source did not return article XML.")
        licenses = [" ".join(node.itertext()).strip() for node in root.iter()
                    if node.tag.rsplit("}", 1)[-1] == "license"]
        license_urls = [value for node in root.iter()
                        if node.tag.rsplit("}", 1)[-1] == "license"
                        for key, value in node.attrib.items() if key.endswith("href")]
        article_ids = [{"type": node.get("pub-id-type", ""), "value": "".join(node.itertext()).strip()}
                       for node in root.iter() if node.tag.rsplit("}", 1)[-1] == "article-id"]
        return {"license_statements": licenses, "license_urls": license_urls, "article_ids": article_ids,
                "has_supplements": any(node.tag.rsplit("}", 1)[-1] == "supplementary-material"
                                       for node in root.iter())}
    if kind == "supplements":
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries = archive.infolist()
            if len(entries) > 1000 or sum(entry.file_size for entry in entries) > 200_000_000:
                raise OverflowError("Supplement archive exceeds the file-count or expanded-size limit.")
            files = []
            for entry in entries:
                name = entry.filename.replace("\\", "/")
                if PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts or ":" in name:
                    raise ValueError("Supplement archive contains an unsafe filename.")
                if entry.flag_bits & 1:
                    raise ValueError("Encrypted supplementary files are not supported.")
                if not entry.is_dir():
                    files.append({"name": name, "bytes": entry.file_size,
                                  "compressed_bytes": entry.compress_size, "crc32": entry.CRC})
            if not files:
                raise ValueError("The supplement archive is empty.")
            # Store the original ZIP only. Inventory is not CRC/content validation;
            # individual file parsing and verification belong to extraction.
            return {"files": files, "file_count": len(files), "archive_extracted": False}
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise TypeError("The source did not return a JSON object.")
    if kind == "metadata":
        # The article endpoint returns `result`; search returns `resultList`.
        records = [payload["result"]] if isinstance(payload.get("result"), dict) else payload.get("resultList", {}).get("result", [])
        if len(records) != 1 or not isinstance(records[0], dict):
            raise ValueError("The source did not return one matching metadata record.")
        return {"record": records[0]}
    count = payload.get("hitCount")
    if type(count) is not int or count < 0:
        raise ValueError("The data-link response has no valid count.")
    links: list[dict[str, Any]] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            if "Target" in value and "Source" in value:
                if not isinstance(value["Target"], dict) or not isinstance(value["Source"], dict):
                    raise TypeError("The data-link entry is malformed.")
                links.append(value)
            else:
                for child in value.values():
                    visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(payload.get("dataLinkList", {}))
    if count > 0 and not links:
        raise ValueError("The data-link response contains no usable link entries.")
    return {"reported_count": count, "links": links,
            "inventory_partial": len(links) < count, "linked_content_fetched": False}


class EuropePMCMaterialClient:
    def fetch(self, kind: str, source: str, source_id: str) -> MaterialResponse:
        if kind not in LIMITS:
            raise ValueError("Unsupported source material.")
        if not re.fullmatch(r"[A-Z0-9_]{1,32}", source) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,254}", source_id):
            return MaterialResponse("unsupported", "", error="The source identifier has an unsupported format; a different adapter or identifier is needed.")
        identifier = quote(source_id, safe="")
        collection = quote(source, safe="")
        if kind == "metadata":
            path = f"article/{collection}/{identifier}?resultType=core&format=json"
        elif kind == "data_links":
            path = f"{collection}/{identifier}/datalinks?format=json&pageSize=1000"
        else:
            path = f"{identifier}/{'fullTextXML' if kind == 'full_text' else 'supplementaryFiles'}"
        url = f"{BASE_URL}/{path}"
        opener = build_opener(SafeRedirect())
        history: list[dict[str, Any]] = []

        def outcome(
            status: str, code: int | None = None, raw: bytes | None = None,
            mime: str | None = None, details: dict[str, Any] | None = None,
            error: str | None = None,
        ) -> MaterialResponse:
            return MaterialResponse(status, url, code, raw, mime,
                                    {**(details or {}), "http_attempts": history}, error)

        for attempt in range(3):
            history.append({"requested_at": datetime.now(UTC).isoformat(), "attempt": attempt + 1})
            raw: bytes | None = None
            code: int | None = None
            mime: str | None = None
            try:
                request = Request(url, headers={"User-Agent": "JeromesLaboratory/0.1 (local research app)"})
                with opener.open(request, timeout=30) as response:
                    code = response.status
                    history[-1]["http_status"] = code
                    mime = response.headers.get("Content-Type")
                    limit = LIMITS[kind]
                    size = response.headers.get("Content-Length", "")
                    if size.isdigit() and int(size) > limit:
                        return outcome("skipped_limit", code, error="Source material exceeds the download size limit.")
                    chunks: list[bytes] = []
                    downloaded = 0
                    deadline = time.monotonic() + 90
                    while True:
                        if time.monotonic() > deadline:
                            raise TimeoutError("The source download exceeded its time budget.")
                        chunk = response.read(min(65536, limit + 1 - downloaded))
                        if not chunk:
                            break
                        chunks.append(chunk)
                        downloaded += len(chunk)
                        if downloaded > limit:
                            return outcome("skipped_limit", code, error="Source material exceeds the download size limit.")
                    raw = b"".join(chunks)
                details = parse_material(kind, raw)
                if kind == "metadata":
                    record = details["record"]
                    if str(record.get("id")) != source_id or record.get("source") != source:
                        raise ValueError("Metadata identity does not match the retained record.")
                if kind == "full_text" and source_id.startswith("PMC"):
                    declared = [item["value"].removeprefix("PMC") for item in details["article_ids"]
                                if item["type"] in {"pmc", "pmcid"}]
                    if declared and source_id.removeprefix("PMC") not in declared:
                        raise ValueError("The full-text identifier does not match the requested record.")
                return outcome("saved", code, raw, mime, details)
            except HTTPError as error:
                history[-1]["http_status"] = error.code
                if error.code in {404, 410, 403, 401}:
                    return outcome("unavailable", error.code, error="Material is not available through this supported endpoint.")
                if error.code not in {429, 500, 502, 503, 504, 529}:
                    return outcome("needs_review", error.code, error=f"Europe PMC returned HTTP {error.code}; review the request before retrying.")
                if attempt == 2:
                    return outcome("failed", error.code, error=f"Europe PMC returned HTTP {error.code}.")
                retry_after = error.headers.get("Retry-After", "")
                time.sleep(min(10, int(retry_after)) if retry_after.isdigit() else 2 ** attempt)
            except (URLError, TimeoutError, OSError, http.client.HTTPException):
                history[-1]["error"] = "Source network failure or timeout."
                if attempt == 2:
                    return outcome("failed", error="Europe PMC could not be reached after three attempts.")
                time.sleep(2 ** attempt)
            except OverflowError as error:
                return outcome("skipped_limit", code, raw, mime, error=str(error))
            except (ValueError, TypeError, KeyError, AttributeError, ET.ParseError, zipfile.BadZipFile, RecursionError):
                return outcome("needs_review", code, raw, mime, error="The source response is malformed, unsupported or has a different identity. Review is needed, not a blind retry.")
        return outcome("failed", error="Source acquisition failed.")
