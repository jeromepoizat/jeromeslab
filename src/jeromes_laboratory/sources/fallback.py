"""Bounded official full-text routes, never arbitrary publisher scraping."""

from __future__ import annotations

import base64
import json
import re
import time
from collections.abc import Callable
from dataclasses import replace
from typing import Any
from urllib.parse import quote, urlparse
from xml.etree import ElementTree as ET

import httpx

from jeromes_laboratory.sources.materials import MaterialResponse, parse_material

FALLBACK_POLICY: dict[str, object] = {
    "version": "official-full-text-fallback-v1", "xml_byte_limit": 20_000_000,
    "metadata_byte_limit": 2_000_000, "max_redirects": 3, "attempts_per_request": 2,
    "request_deadline_seconds": 60, "socket_timeout_seconds": 20,
    "request_spacing_seconds": 0.4,
    "routes": ["PMC BioC", "bioRxiv JATS", "medRxiv JATS"],
    "arbitrary_urls": False, "pdfs": False,
}
HOSTS = {"www.ncbi.nlm.nih.gov", "api.biorxiv.org", "www.biorxiv.org", "www.medrxiv.org"}
BIOC_ACCESS_RULE_VERSION = "pmc-bioc-no-result-v1"
BIOC_PARSER_VERSION = "pmc-bioc-identity-v2"
PREPRINT_ROUTE_VERSION = "publisher-doi-route-v2"


def preprint_server(metadata: dict[str, Any]) -> str | None:
    """Publisher identifies the server; DOI registrant prefixes can change."""
    book = metadata.get("bookOrReportDetails")
    publisher = str(book.get("publisher", "") if isinstance(book, dict) else "").lower()
    doi = str(metadata.get("doi") or "").lower().strip()
    return publisher if publisher in {"biorxiv", "medrxiv"} and re.fullmatch(r"10\.[0-9]{4,9}/[a-z0-9._-]+", doi) else None


def bioc_no_result(raw: bytes) -> bool:
    """Recognize only the explicit BioC absence message, not generic HTML errors."""
    return re.match(br"\s*\[Error\]\s*:\s*No result can be found\.\s*(?:<BR\s*/?>|$)",
                    raw[:512], re.IGNORECASE) is not None


def interpret_bioc(response: MaterialResponse, pmcid: str) -> MaterialResponse:
    """Accept canonical/numeric PMCID forms, never infer identity from body text."""
    raw = response.raw or b""
    details = {**response.details, "parser_version": BIOC_PARSER_VERSION,
               "provider": "PMC BioC", "format": "BioC XML"}
    if bioc_no_result(raw):
        return replace(response, status="unavailable", details={**details, "access_rule_version": BIOC_ACCESS_RULE_VERSION},
                       error="PMC BioC explicitly reports no full text for this identifier.")
    try:
        if b"\x00" in raw or re.search(br"<!ENTITY\s", raw, re.IGNORECASE):
            raise ValueError("Unsupported XML entities or encoding.")
        root = ET.fromstring(raw)
        documents = root.findall("document") if root.tag == "collection" else []
        if len(documents) != 1:
            raise ValueError("Expected exactly one BioC document.")
        document = documents[0]
        identifiers = []
        document_id = (document.findtext("id") or "").strip()
        declared = [document_id] if document_id.lower() not in {"", "unknown"} else []
        declared += [(node.text or "").strip() for node in document.findall(".//infon")
                     if node.get("key") in {"article-id_pmc", "article-id_pmcid", "article-id_pmcaid"}
                     and (node.text or "").strip()]
        for value in declared:
            match = re.fullmatch(r"(?:PMC)?([0-9]+)", value)
            if match is None:
                raise ValueError("Unrecognized declared PMC identifier.")
            identifiers.append("PMC" + match[1])
        if not identifiers or any(identifier != pmcid for identifier in identifiers):
            raise ValueError("BioC identity cannot be verified or conflicts with the retained record.")
        body = [p for p in document.findall("passage") if p.findtext("infon[@key='section_type']")
                not in {None, "TITLE", "ABSTRACT", "REF"} and (p.findtext("text") or "").strip()]
        if not body:
            raise ValueError("No full-text body passages could be verified.")
        return replace(response, status="saved", error=None, details={**details,
            "identity_evidence": identifiers, "body_passages": len(body),
            "license_statements": [n.text or "" for n in root.findall(".//infon[@key='license']")]})
    except (ValueError, ET.ParseError):
        return replace(response, status="needs_review", details=details,
                       error="Saved response needs review: its document identity, XML or full-text body could not be verified. It is not confirmed unavailable.")


def safe_url(url: str) -> bool:
    parsed = urlparse(url)
    try:
        return (parsed.scheme == "https" and parsed.hostname in HOSTS and parsed.port in {None, 443}
                and not parsed.username and not parsed.password and not parsed.fragment)
    except ValueError:
        return False


class FullTextResolver:
    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        self.transport = transport

    def _download(self, url: str, limit: int) -> MaterialResponse:
        history: list[dict[str, Any]] = []
        for attempt in range(2):
            current = url
            try:
                # Stay well below public API rate ceilings, including retries.
                time.sleep(0.4)
                # No environment proxies, cookies, credentials, or cross-host auth.
                with httpx.Client(transport=self.transport, trust_env=False, timeout=20,
                                  headers={"User-Agent": "JeromesLaboratory/0.1"}) as client:
                    deadline = time.monotonic() + 60
                    for hop in range(4):
                        if not safe_url(current):
                            raise ValueError("Unsupported fallback URL or redirect.")
                        with client.stream("GET", current) as response:
                            history.append({"url": current, "http_status": response.status_code, "attempt": attempt + 1})
                            if response.is_redirect:
                                if hop == 3 or "location" not in response.headers:
                                    raise ValueError("Fallback redirect limit exceeded.")
                                current = str(response.url.join(response.headers["location"]))
                                continue
                            if response.status_code in {401, 403, 404, 410}:
                                return MaterialResponse("unavailable", current, response.status_code,
                                                        details={"requests": history})
                            response.raise_for_status()
                            chunks: list[bytes] = []
                            size = 0
                            for chunk in response.iter_bytes(65536):
                                size += len(chunk)
                                if size > limit:
                                    return MaterialResponse("skipped_limit", current, response.status_code,
                                                            details={"requests": history}, error="Fallback response exceeds its size limit.")
                                if time.monotonic() > deadline:
                                    raise TimeoutError("Fallback time limit.")
                                chunks.append(chunk)
                            return MaterialResponse("saved", current, response.status_code, b"".join(chunks),
                                                    response.headers.get("content-type"), {"requests": history})
            except (httpx.HTTPError, TimeoutError) as error:
                code = error.response.status_code if isinstance(error, httpx.HTTPStatusError) else None
                if attempt == 0 and (code is None or code in {429, 500, 502, 503, 504, 529}):
                    retry = error.response.headers.get("retry-after", "") if isinstance(error, httpx.HTTPStatusError) else ""
                    time.sleep(min(30, int(retry)) if retry.isdigit() else 5)
                    continue
                status = "failed" if code is None or code in {429, 500, 502, 503, 504, 529} else "needs_review"
                return MaterialResponse(status, current, code, details={"requests": history},
                                        error="Fallback service failed or timed out.")
            except ValueError:
                return MaterialResponse("needs_review", current, details={"requests": history},
                                        error="Unsupported fallback URL or redirect.")
        return MaterialResponse("failed", url, details={"requests": history})

    def resolve(self, metadata: dict[str, Any], stopped: Callable[[], bool] = lambda: False) -> MaterialResponse:
        routes: list[dict[str, Any]] = []
        pmcid = str(metadata.get("pmcid") or "")
        doi = str(metadata.get("doi") or "").lower().strip()
        candidates: list[tuple[str, str, str]] = []
        if re.fullmatch(r"PMC\d+", pmcid):
            candidates.append(("PMC BioC", f"https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_xml/{pmcid}/unicode", "bioc"))
        server = preprint_server(metadata)
        if server:
            candidates.append((server, f"https://api.biorxiv.org/details/{server}/{quote(doi, safe='/')}/na/json", "jats"))
        for provider, url, format_name in candidates:
            if stopped():
                return MaterialResponse("blocked", "", details={"routes": routes}, error="Fallback paused before the next route.")
            result = self._download(url, 2_000_000 if format_name == "jats" else 20_000_000)
            discovery: dict[str, Any] | None = None
            details: dict[str, Any]
            try:
                if result.status == "saved" and format_name == "bioc":
                    result = interpret_bioc(result, pmcid)
                if result.status == "saved" and format_name == "jats":
                    payload = json.loads(result.raw or b"")
                    discovery = {"url": result.request_url, "response": payload,
                                 "raw_base64": base64.b64encode(result.raw or b"").decode("ascii"),
                                 "requests": result.details.get("requests", [])}
                    versions = [entry for entry in payload.get("collection", []) if entry.get("doi", "").lower() == doi]
                    # Never silently substitute a newer preprint or its journal article.
                    date = metadata.get("firstPublicationDate")
                    matches = [entry for entry in versions if entry.get("date") == date]
                    if len(matches) != 1:
                        raise LookupError("No unambiguous preprint version matches the retained publication date.")
                    target = matches[0].get("jatsxml", "")
                    if not safe_url(target) or urlparse(target).hostname != f"www.{provider}.org":
                        raise ValueError("Unsupported JATS link.")
                    if stopped():
                        return MaterialResponse("blocked", "", details={"routes": routes, "discovery": discovery}, error="Fallback paused before text download.")
                    result = self._download(target, 20_000_000)
                    if result.status == "saved" and not urlparse(result.request_url).path.endswith(urlparse(target).path.removeprefix("/content")):
                        raise ValueError("The preprint text redirect changed the version path.")
                if result.status == "saved":
                    raw = result.raw or b""
                    if b"\x00" in raw or re.search(br"<!ENTITY\s", raw, re.IGNORECASE):
                        raise ValueError("Unsupported entities.")
                    root = ET.fromstring(raw)
                    if format_name == "bioc":
                        details = result.details
                    else:
                        details = parse_material("full_text", raw)
                        ids = [item["value"].lower() for item in details["article_ids"] if item["type"] == "doi"]
                        if doi not in ids or not any(n.tag.rsplit("}", 1)[-1] == "body" and "".join(n.itertext()).strip() for n in root.iter()):
                            raise ValueError("JATS DOI/body does not match the retained preprint.")
                    return replace(result, details={**result.details, **details, "provider": provider,
                        "format": "BioC XML" if format_name == "bioc" else "JATS XML", "resolver_policy": FALLBACK_POLICY,
                        "discovery": discovery, "earlier_routes": routes})
            except LookupError as error:
                result = replace(result, status="needs_review", error=str(error))
            except (ValueError, TypeError, AttributeError, KeyError, ET.ParseError):
                result = replace(result, status="needs_review", error="Fallback returned unsupported material or a different document; review is required, not a blind retry.")
            routes.append({"provider": provider, "url": result.request_url, "status": result.status,
                           "error": result.error, "http_status": result.http_status,
                           "requests": result.details.get("requests", []), "discovery": discovery})
            if "access_rule_version" in result.details:
                routes[-1]["access_rule_version"] = result.details["access_rule_version"]
        status = next((status for status in ("failed", "needs_review", "skipped_limit", "unsupported")
                       if any(r["status"] == status for r in routes)), "unavailable") if routes else "unsupported"
        outcome_error = ("No enabled full-text route or usable identifier; availability elsewhere is unknown."
                 if not routes else next((route["error"] for route in routes if route["status"] == status and route["error"]),
                                         "No full text recovered through the checked routes."))
        return MaterialResponse(status, routes[-1]["url"] if routes else "", http_status=result.http_status if candidates else None,
                                raw=result.raw if candidates else None, content_type=result.content_type if candidates else None,
                                details={"routes": routes, "resolver_policy": FALLBACK_POLICY},
                                error=outcome_error)
