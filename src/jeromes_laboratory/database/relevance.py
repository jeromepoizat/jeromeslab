"""Load immutable retrieval appearances as distinct source-record inputs."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def distinct_source_records(database_path: Path, retrieval_job_id: str) -> list[dict[str, object]]:
    """Collapse query appearances by exact source identity, not tentative article groups."""
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            "SELECT records.source, records.source_record_id, records.title, "
            "records.abstract_text, records.publication_date, "
            "records.author_string, records.journal_title, records.doi, "
            "records.pmid, records.pmcid, runs.query_id, "
            "runs.query_title FROM publication_source_records records "
            "JOIN search_runs runs ON runs.id = records.run_id "
            "WHERE runs.job_id = ? ORDER BY runs.rowid, records.rowid",
            (retrieval_job_id,),
        ).fetchall()
    finally:
        connection.close()
    identities: dict[tuple[str, str], dict[str, object]] = {}
    for row in rows:
        key = (str(row["source"]), str(row["source_record_id"]))
        record = identities.setdefault(key, {
            "source": key[0], "source_record_id": key[1], "title": None,
            "abstract": None, "publication_date": None, "author_string": None,
            "journal_title": None, "doi": None, "pmid": None, "pmcid": None,
            "queries": [],
        })
        for field, column in (
            ("title", "title"), ("abstract", "abstract_text"),
            ("publication_date", "publication_date"),
            ("author_string", "author_string"), ("journal_title", "journal_title"),
            ("doi", "doi"), ("pmid", "pmid"), ("pmcid", "pmcid"),
        ):
            if record[field] is None and row[column]:
                record[field] = str(row[column])
        query = {"id": str(row["query_id"]), "title": str(row["query_title"])}
        queries = record["queries"]
        assert isinstance(queries, list)
        if query not in queries:
            queries.append(query)
    return [identities[key] for key in sorted(identities)]
