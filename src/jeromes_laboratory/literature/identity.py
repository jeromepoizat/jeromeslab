"""Conservative, explainable candidate grouping of publication source records."""

from __future__ import annotations

import html
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class ArticleMetadata:
    """One source identity with available bibliographic metadata."""

    source: str
    source_record_id: str
    title: str | None
    doi: str | None
    pmid: str | None
    pmcid: str | None
    author_string: str | None
    journal_title: str | None
    publication_date: str | None


@dataclass(frozen=True)
class ArticleMatchSummary:
    """Provisional group counts; source records are never removed or rewritten."""

    provisional_record_groups: int
    additional_ids_in_groups: int
    groups_with_metadata_differences: int


def _normalized_text(value: str | None) -> str:
    if not value:
        return ""
    without_markup = re.sub(r"<[^>]+>", " ", html.unescape(value))
    normalized = unicodedata.normalize("NFKC", without_markup).casefold()
    return " ".join(re.findall(r"[^\W_]+", normalized, flags=re.UNICODE))


def _normalized_doi(value: str | None) -> str:
    if not value:
        return ""
    doi = value.strip().casefold()
    doi = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", doi)
    return doi.rstrip(" .")


def _normalized_identifier(value: str | None) -> str:
    return value.strip().upper() if value else ""


def _metadata_values(records: list[ArticleMetadata], field: str) -> set[str]:
    values: set[str] = set()
    for record in records:
        if field == "year":
            match = re.match(r"^\d{4}", record.publication_date or "")
            value = match.group(0) if match else ""
        elif field == "first_author":
            value = re.split(r"[,;]", record.author_string, maxsplit=1)[0] if record.author_string else ""
        elif field == "journal":
            value = record.journal_title or ""
        elif field == "doi":
            value = _normalized_doi(record.doi)
        elif field == "pmid":
            value = _normalized_identifier(record.pmid)
        else:
            value = _normalized_identifier(record.pmcid)
        normalized = _normalized_text(value) if field in {"year", "first_author", "journal"} else value
        if normalized:
            values.add(normalized)
    return values


def summarize_article_matches(records: Sequence[ArticleMetadata]) -> ArticleMatchSummary:
    """Group exact identifiers or normalized titles, flagging metadata differences.

    A shared title is intentionally treated as a provisional same-article match.
    Generic titles, different editions, and inconsistent metadata may therefore
    need human review before the grouping is used for screening.
    """
    parents = list(range(len(records)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parents[right_root] = left_root

    seen: dict[tuple[str, str], int] = {}
    for index, record in enumerate(records):
        keys = (
            ("doi", _normalized_doi(record.doi)),
            ("pmid", _normalized_identifier(record.pmid)),
            ("pmcid", _normalized_identifier(record.pmcid)),
            # Repeated patent titles often name distinct filings, not one article.
            ("title", _normalized_text(record.title) if record.source != "PAT" else ""),
        )
        for kind, value in keys:
            if not value:
                continue
            key = (kind, value)
            if key in seen:
                union(index, seen[key])
            else:
                seen[key] = index

    groups: dict[int, list[ArticleMetadata]] = {}
    for index, record in enumerate(records):
        groups.setdefault(find(index), []).append(record)
    differing = sum(
        1 for group in groups.values()
        if len(group) > 1 and any(
            len(_metadata_values(group, field)) > 1
            for field in ("year", "first_author", "journal", "doi", "pmid", "pmcid")
        )
    )
    return ArticleMatchSummary(
        provisional_record_groups=len(groups),
        additional_ids_in_groups=len(records) - len(groups),
        groups_with_metadata_differences=differing,
    )
