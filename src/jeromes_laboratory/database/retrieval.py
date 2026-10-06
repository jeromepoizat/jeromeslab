"""Durable Europe PMC retrieval with exact query and raw-page provenance."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from pathlib import Path
from uuid import uuid4

from jeromes_laboratory.literature.identity import ArticleMetadata, summarize_article_matches
from jeromes_laboratory.sources.europe_pmc import (
    ADAPTER_VERSION,
    MAX_RECORDS_PER_QUERY,
    PAGE_SIZE,
    SearchPage,
    SourceSearchClient,
    SourceSearchError,
)


def _timestamp() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()


def _optional_text(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


class RetrievalRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def runs_for_job(self, job_id: str) -> list[dict[str, object]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT query_id, query_title, status, total_hits, retrieved_count, "
                "truncated, started_at, completed_at, error FROM search_runs "
                "WHERE job_id = ? ORDER BY rowid", (job_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def summary_for_job(self, job_id: str) -> dict[str, object]:
        """Aggregate saved discoveries without loading article text into the API response.

        A distinct source record is a (source, source_record_id) pair. It is not
        yet a canonical publication: different source identities can describe
        the same paper, which later identity resolution must address.
        """
        with self._connect() as connection:
            job = connection.execute(
                "SELECT status FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
            runs = connection.execute(
                "SELECT query_id, query_title, status, total_hits, retrieved_count, "
                "truncated, started_at, completed_at, error FROM search_runs "
                "WHERE job_id = ? ORDER BY rowid", (job_id,),
            ).fetchall()
            identities = connection.execute(
                "SELECT records.source, records.source_record_id, "
                "COUNT(*) AS occurrences, COUNT(DISTINCT runs.query_id) AS query_count, "
                "MIN(runs.query_id) AS first_query_id, "
                "MAX(CASE WHEN records.abstract_text IS NOT NULL "
                "AND TRIM(records.abstract_text) != '' THEN 1 ELSE 0 END) AS has_abstract, "
                "MAX(records.title) AS title, MAX(records.doi) AS doi, "
                "MAX(records.pmid) AS pmid, MAX(records.pmcid) AS pmcid, "
                "MAX(records.author_string) AS author_string, "
                "MAX(records.journal_title) AS journal_title, "
                "MAX(records.publication_date) AS publication_date "
                "FROM publication_source_records AS records "
                "JOIN search_runs AS runs ON runs.id = records.run_id "
                "WHERE runs.job_id = ? "
                "GROUP BY records.source, records.source_record_id", (job_id,),
            ).fetchall()
        source_counts: dict[str, dict[str, int]] = {}
        unique_to_query: dict[str, int] = {}
        for identity in identities:
            source = str(identity["source"])
            counts = source_counts.setdefault(source, {"unique_records": 0, "raw_records": 0})
            counts["unique_records"] += 1
            counts["raw_records"] += int(identity["occurrences"])
            if identity["query_count"] == 1:
                query_id = str(identity["first_query_id"])
                unique_to_query[query_id] = unique_to_query.get(query_id, 0) + 1
        raw_saved = sum(int(identity["occurrences"]) for identity in identities)
        article_matches = summarize_article_matches([
            ArticleMetadata(
                source=str(identity["source"]),
                source_record_id=str(identity["source_record_id"]),
                title=_optional_text(identity["title"]),
                doi=_optional_text(identity["doi"]),
                pmid=_optional_text(identity["pmid"]),
                pmcid=_optional_text(identity["pmcid"]),
                author_string=_optional_text(identity["author_string"]),
                journal_title=_optional_text(identity["journal_title"]),
                publication_date=_optional_text(identity["publication_date"]),
            )
            for identity in identities
        ]) if job is not None and job["status"] == "completed" else None
        return {
            "runs": [
                {**dict(run), "unique_to_query": unique_to_query.get(str(run["query_id"]), 0)}
                for run in runs
            ],
            "reported_hits": sum(int(run["total_hits"] or 0) for run in runs),
            "raw_saved_records": raw_saved,
            "distinct_source_records": len(identities),
            "repeat_discoveries": raw_saved - len(identities),
            "records_in_multiple_queries": sum(
                int(identity["query_count"] > 1) for identity in identities
            ),
            "distinct_records_with_abstract": sum(
                int(identity["has_abstract"]) for identity in identities
            ),
            "provisional_record_groups": (
                article_matches.provisional_record_groups if article_matches else None
            ),
            "additional_source_ids_grouped": (
                article_matches.additional_ids_in_groups if article_matches else None
            ),
            "groups_with_metadata_differences": (
                article_matches.groups_with_metadata_differences if article_matches else None
            ),
            "sources": [
                {"source": source, **counts}
                for source, counts in sorted(
                    source_counts.items(), key=lambda item: -item[1]["unique_records"]
                )
            ],
        }

    def run_job(self, job_id: str, client: SourceSearchClient) -> None:
        with self._connect() as connection:
            job = connection.execute(
                "SELECT workflow_input_snapshot_json FROM jobs WHERE id = ? "
                "AND kind = 'source_retrieval' AND status = 'awaiting_response'",
                (job_id,),
            ).fetchone()
            if job is None:
                raise SourceSearchError("The retrieval job is no longer active.")
            snapshot = json.loads(job["workflow_input_snapshot_json"])
            queries = [query for query in snapshot["query_set"]["queries"] if query["included"]]
        for query in queries:
            run_id = str(uuid4())
            with self._connect() as connection:
                connection.execute(
                    "INSERT INTO search_runs (id, job_id, query_id, query_title, query_text, "
                    "source, adapter_version, status, started_at) "
                    "VALUES (?, ?, ?, ?, ?, 'europe_pmc', ?, 'running', ?)",
                    (run_id, job_id, query["id"], query["title"], query["query_text"],
                     ADAPTER_VERSION, _timestamp()),
                )
            try:
                self._run_query(run_id, query["query_text"], client)
            except Exception as error:
                message = str(error) if isinstance(error, SourceSearchError) else "The source retrieval stopped unexpectedly."
                with self._connect() as connection:
                    connection.execute(
                        "UPDATE search_runs SET status = 'failed', completed_at = ?, error = ? "
                        "WHERE id = ?", (_timestamp(), message, run_id),
                    )
                raise SourceSearchError(message) from error
        with self._connect() as connection:
            connection.execute(
                "UPDATE jobs SET status = 'completed', completed_at = ? "
                "WHERE id = ? AND status = 'awaiting_response'", (_timestamp(), job_id),
            )

    def _run_query(self, run_id: str, query_text: str, client: SourceSearchClient) -> None:
        cursor = "*"
        page_number = 0
        seen_cursors = {cursor}
        retrieved = 0
        while True:
            page = client.fetch(query_text, cursor, min(PAGE_SIZE, MAX_RECORDS_PER_QUERY - retrieved))
            page_number += 1
            self._save_page(run_id, page_number, cursor, page)
            retrieved += len(page.records)
            if retrieved >= page.total_hits or not page.records:
                truncated = False
                break
            if retrieved >= MAX_RECORDS_PER_QUERY:
                truncated = True
                break
            next_cursor = page.next_cursor_mark
            if not next_cursor or next_cursor in seen_cursors:
                raise SourceSearchError("Europe PMC pagination stopped before all results were retrieved.")
            seen_cursors.add(next_cursor)
            cursor = next_cursor
            time.sleep(0.2)
        with self._connect() as connection:
            connection.execute(
                "UPDATE search_runs SET status = 'completed', truncated = ?, "
                "completed_at = ? WHERE id = ?", (int(truncated), _timestamp(), run_id),
            )

    def _save_page(self, run_id: str, page_number: int, cursor: str, page: SearchPage) -> None:
        page_id = str(uuid4())
        relative = Path("search-runs") / run_id / f"page-{page_number:05d}.json"
        destination = self.database_path.parent / "artifacts" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(destination.name + f".{uuid4()}.tmp")
        try:
            with temporary.open("xb") as output:
                output.write(page.raw)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO search_pages (id, run_id, page_number, request_url, cursor_mark, "
                "next_cursor_mark, retrieved_at, raw_path, raw_sha256, raw_byte_size, record_count) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (page_id, run_id, page_number, page.request_url, cursor,
                 page.next_cursor_mark, _timestamp(), relative.as_posix(),
                 hashlib.sha256(page.raw).hexdigest(), len(page.raw), len(page.records)),
            )
            for index, record in enumerate(page.records):
                source = _optional_text(record.get("source"))
                source_id = _optional_text(record.get("id"))
                if source is None or source_id is None:
                    raise SourceSearchError("Europe PMC returned a record without source identity.")
                preprint: bool | None = None
                if record.get("isPreprint") in {"Y", "N"}:
                    preprint = record["isPreprint"] == "Y"
                connection.execute(
                    "INSERT INTO publication_source_records "
                    "(id, run_id, page_id, item_index, source, source_record_id, title, "
                    "author_string, journal_title, publication_date, doi, pmid, pmcid, "
                    "abstract_text, is_preprint) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (str(uuid4()), run_id, page_id, index, source, source_id,
                     _optional_text(record.get("title")),
                     _optional_text(record.get("authorString")),
                     _optional_text(record.get("journalTitle")),
                     _optional_text(record.get("firstPublicationDate")),
                     _optional_text(record.get("doi")),
                     _optional_text(record.get("pmid")),
                     _optional_text(record.get("pmcid")),
                     _optional_text(record.get("abstractText")), preprint),
                )
            connection.execute(
                "UPDATE search_runs SET total_hits = ?, retrieved_count = retrieved_count + ? "
                "WHERE id = ?", (page.total_hits, len(page.records), run_id),
            )
