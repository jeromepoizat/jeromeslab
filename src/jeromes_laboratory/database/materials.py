"""Collect the exact validated inclusion pool without changing research decisions."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import sqlite3
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from jeromes_laboratory.database.connections import connect_database
from jeromes_laboratory.sources.fallback import (
    BIOC_ACCESS_RULE_VERSION,
    BIOC_PARSER_VERSION,
    FALLBACK_POLICY,
    PREPRINT_ROUTE_VERSION,
    FullTextResolver,
    interpret_bioc,
    preprint_server,
)
from jeromes_laboratory.sources.materials import (
    POLICY,
    XML_ACCESS_RULE_VERSION,
    MaterialClient,
    MaterialResponse,
    xml_access_limitation,
)

KINDS = ("metadata", "full_text", "supplements", "data_links")


class MaterialError(ValueError):
    pass


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def recover_material_runs(connection: sqlite3.Connection) -> None:
    """Called by queue cancellation/failure/restart; never replay a network request."""
    if connection.execute("SELECT 1 FROM sqlite_master WHERE name = 'source_material_runs'").fetchone() is None:
        return
    connection.execute(
        "UPDATE source_material_runs SET status = 'paused', stop_requested = 1 "
        "WHERE status IN ('pending', 'running') AND NOT EXISTS (SELECT 1 FROM jobs "
        "WHERE kind = 'source_material_collection' AND status IN ('pending', 'awaiting_response') "
        "AND json_extract(workflow_input_snapshot_json, '$.run_id') = source_material_runs.id)"
    )


class MaterialRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def _connect(self) -> sqlite3.Connection:
        connection = connect_database(self.database_path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _enqueue(connection: sqlite3.Connection, run_id: str, project_id: str,
                 local_only: bool = False, claimed: bool = False) -> str:
        job_id = str(uuid4())
        run = connection.execute("SELECT * FROM source_material_runs WHERE id = ?", (run_id,)).fetchone()
        project = connection.execute("SELECT scientific_question FROM projects WHERE id = ?", (project_id,)).fetchone()
        assert run is not None and project is not None
        covered = ("EXISTS (SELECT 1 FROM source_material_resources fallback WHERE fallback.record_id = resources.record_id "
                   "AND fallback.kind = 'full_text_fallback' AND fallback.status = 'saved')")
        condition = ("((resources.kind IN ('full_text', 'supplements') AND resources.status IN ('pending', 'failed', 'blocked') AND "
                     + covered + ") OR (resources.kind = 'full_text_fallback' AND ((resources.status = 'failed' AND latest.raw_path IS NOT NULL) "
                     "OR (resources.status = 'unavailable' AND json_array_length(latest.details_json, '$.routes') = 0) "
                     "OR (resources.status = 'needs_review' AND latest.raw_path IS NULL "
                     "AND json_extract(latest.details_json, '$.preprint_route_version') IS NULL))))"
                     if local_only else "resources.status IN ('pending', 'failed', 'blocked')")
        tasks = [row[0] for row in connection.execute(
            "SELECT resources.id FROM source_material_resources resources JOIN source_material_records records "
            "ON records.id = resources.record_id LEFT JOIN source_material_attempts latest ON latest.id = "
            "(SELECT id FROM source_material_attempts WHERE resource_id = resources.id ORDER BY rowid DESC LIMIT 1) "
            "WHERE records.run_id = ? AND " + condition + " ORDER BY "
            "CASE resources.kind WHEN 'data_links' THEN 1 WHEN 'supplements' THEN 2 ELSE 0 END, "
            "records.ordinal, CASE resources.kind WHEN 'metadata' THEN 0 WHEN 'full_text' THEN 1 ELSE 2 END, resources.rowid", (run_id,),
        )]
        if local_only and not tasks:
            raise MaterialError("No saved responses need local recovery.")
        snapshot = _json({"schema_version": 1, "run_id": run_id,
                          "selection_sha256": run["selection_sha256"],
                          "policy": json.loads(run["policy_json"]), "resource_count": len(tasks),
                          "xml_access_rule_version": XML_ACCESS_RULE_VERSION,
                          "fallback_policy": FALLBACK_POLICY,
                          "scheduling_version": "full-text-first-v1",
                          "bioc_access_rule_version": BIOC_ACCESS_RULE_VERSION,
                          "bioc_parser_version": BIOC_PARSER_VERSION, "local_only": local_only,
                          "outcome_rules_version": "material-outcomes-v2",
                          "preprint_route_version": PREPRINT_ROUTE_VERSION,
                          "coverage_resolution_version": "fallback-covers-primary-v1",
                          "resource_manifest_sha256": hashlib.sha256(_json(tasks).encode()).hexdigest()})
        connection.execute(
            "INSERT INTO jobs (id, project_id, kind, status, created_at, provider, model, "
            "scientific_question_snapshot, prompt_snapshot, prompt_template_id, "
            "prompt_template_version, workflow_input_snapshot_json) "
            "VALUES (?, ?, 'source_material_collection', 'pending', ?, 'europe_pmc', "
            "'materials-v1', ?, '', 'source-material-collection', '1', ?)",
            (job_id, project_id, _now(), project[0], snapshot),
        )
        connection.executemany("INSERT INTO source_material_job_tasks (job_id, resource_id, ordinal) VALUES (?, ?, ?)",
                               [(job_id, resource_id, ordinal) for ordinal, resource_id in enumerate(tasks)])
        connection.execute("UPDATE source_material_runs SET status = 'pending', stop_requested = 0, "
                           "completed_at = NULL WHERE id = ?", (run_id,))
        if claimed:
            connection.execute("UPDATE jobs SET status = 'awaiting_response', started_at = ? WHERE id = ?", (_now(), job_id))
        return job_id

    def reconcile_saved(self, project_id: str, run_id: str) -> str:
        """Claim an offline-only repair job atomically, preserving all historical attempts."""
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            run = connection.execute("SELECT * FROM source_material_runs WHERE id = ? AND project_id = ?",
                                     (run_id, project_id)).fetchone()
            if run is None:
                raise MaterialError("The source-material run does not belong to this project.")
            if connection.execute("SELECT 1 FROM jobs WHERE status IN ('pending', 'awaiting_response') LIMIT 1").fetchone():
                raise MaterialError("Pause other research operations before recovering saved material.")
            self._prepare_fallback_guard(connection, run)
            return self._enqueue(connection, run_id, project_id, local_only=True, claimed=True)

    def start(self, project_id: str, filter_run_id: str, expected_sha256: str) -> dict[str, Any]:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            selection = connection.execute(
                "SELECT * FROM relevance_score_filters WHERE run_id = ? AND project_id = ?",
                (filter_run_id, project_id),
            ).fetchone()
            if selection is None:
                raise MaterialError("Validate the relevance selection before collecting source material.")
            if selection["content_sha256"] != expected_sha256 or hashlib.sha256(
                selection["content_json"].encode()
            ).hexdigest() != expected_sha256:
                raise MaterialError("The retained selection does not match its saved digest. Reload before continuing.")
            existing = connection.execute("SELECT id FROM source_material_runs WHERE project_id = ?", (project_id,)).fetchone()
            if existing is None:
                run_id = str(uuid4())
                retained = json.loads(selection["content_json"])["included_records"]
                if not retained:
                    raise MaterialError("The retained selection is empty.")
                connection.execute(
                    "INSERT INTO source_material_runs (id, project_id, filter_run_id, selection_sha256, "
                    "policy_json, status, created_at) VALUES (?, ?, ?, ?, ?, 'pending', ?)",
                    (run_id, project_id, filter_run_id, expected_sha256, _json(POLICY), _now()),
                )
                retrieval_id = connection.execute("SELECT retrieval_job_id FROM relevance_scoring_runs WHERE id = ?",
                                                  (filter_run_id,)).fetchone()[0]
                # Only the exact saved selection is consumed, not current scores.
                for ordinal, identity in enumerate(retained):
                    row = connection.execute(
                        "SELECT records.* FROM publication_source_records records JOIN search_runs searches "
                        "ON searches.id = records.run_id WHERE searches.job_id = ? "
                        "AND records.source = ? AND records.source_record_id = ? ORDER BY records.rowid LIMIT 1",
                        (retrieval_id, identity["source"], identity["source_record_id"]),
                    ).fetchone()
                    if row is None:
                        raise MaterialError("A retained source record is missing from its original retrieval.")
                    record_id = str(uuid4())
                    metadata = _json(dict(row))
                    connection.execute(
                        "INSERT INTO source_material_records (id, run_id, ordinal, source, source_record_id, "
                        "title, metadata_json, metadata_sha256, has_abstract) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (record_id, run_id, ordinal, identity["source"], identity["source_record_id"],
                         row["title"] or "Untitled record", metadata, hashlib.sha256(metadata.encode()).hexdigest(),
                         bool((row["abstract_text"] or "").strip())),
                    )
                    connection.executemany("INSERT INTO source_material_resources (id, record_id, kind) VALUES (?, ?, ?)",
                                           [(str(uuid4()), record_id, kind) for kind in (*KINDS, "full_text_fallback")])
                self._enqueue(connection, run_id, project_id)
        return self.state(project_id, filter_run_id)

    @staticmethod
    def _prepare_fallback_guard(connection: sqlite3.Connection, run: sqlite3.Row) -> None:
        if run["status"] in {"pending", "running"}:
            raise MaterialError("Pause collection before preparing fallback retrieval.")
        if connection.execute("SELECT 1 FROM jobs WHERE kind = 'source_material_collection' "
                              "AND status IN ('pending', 'awaiting_response') "
                              "AND json_extract(workflow_input_snapshot_json, '$.run_id') = ?", (run["id"],)).fetchone():
            raise MaterialError("Pause collection before preparing fallback retrieval.")
        if connection.execute("SELECT 1 FROM jobs WHERE project_id = ? AND kind != 'source_material_collection' "
                              "AND created_at > ? LIMIT 1", (run["project_id"], run["created_at"])).fetchone():
            raise MaterialError("Downstream work exists. Change source material in a fork instead.")

    @staticmethod
    def _prepare_fallback(connection: sqlite3.Connection, run: sqlite3.Row) -> int:
        MaterialRepository._prepare_fallback_guard(connection, run)
        records = connection.execute(
            "SELECT records.id FROM source_material_records records WHERE records.run_id = ? "
            "AND NOT EXISTS (SELECT 1 FROM source_material_resources r WHERE r.record_id = records.id "
            "AND r.kind IN ('full_text', 'full_text_fallback') AND r.status = 'saved') "
            "AND NOT EXISTS (SELECT 1 FROM source_material_resources r WHERE r.record_id = records.id "
            "AND r.kind = 'full_text_fallback')", (run["id"],),
        ).fetchall()
        connection.executemany("INSERT INTO source_material_resources (id, record_id, kind) VALUES (?, ?, 'full_text_fallback')",
                               [(str(uuid4()), row[0]) for row in records])
        return len(records)

    def prepare_fallback(self, project_id: str, run_id: str) -> int:
        """Explicit local upgrade: append missing tasks, without enqueuing network work."""
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            run = connection.execute("SELECT * FROM source_material_runs WHERE id = ? AND project_id = ?",
                                     (run_id, project_id)).fetchone()
            if run is None:
                raise MaterialError("The source-material run does not belong to this project.")
            return self._prepare_fallback(connection, run)

    def control(self, project_id: str, run_id: str, action: str) -> dict[str, Any]:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            run = connection.execute("SELECT * FROM source_material_runs WHERE id = ? AND project_id = ?",
                                     (run_id, project_id)).fetchone()
            if run is None:
                raise MaterialError("The source-material run does not belong to this project.")
            if action == "pause":
                if run["status"] in {"pending", "running"}:
                    connection.execute("UPDATE source_material_runs SET stop_requested = 1 WHERE id = ?", (run_id,))
                    connection.execute("UPDATE jobs SET status = 'cancelled', completed_at = ? "
                                       "WHERE kind = 'source_material_collection' AND status = 'pending' "
                                       "AND json_extract(workflow_input_snapshot_json, '$.run_id') = ?", (_now(), run_id))
                    recover_material_runs(connection)
            elif action in {"resume", "fallback"}:
                if action == "fallback":
                    self._prepare_fallback(connection, run)
                if run["status"] in {"pending", "running"}:
                    if run["stop_requested"]:
                        raise MaterialError("Wait for the current source request to finish pausing.")
                else:
                    if connection.execute("SELECT 1 FROM jobs WHERE project_id = ? "
                                          "AND kind != 'source_material_collection' AND created_at > ? LIMIT 1",
                                          (project_id, run["created_at"])).fetchone():
                        raise MaterialError("Downstream work exists. Change source material in a fork instead.")
                    tasks = connection.execute("SELECT 1 FROM source_material_resources resources "
                                               "JOIN source_material_records records ON records.id = resources.record_id "
                                               "WHERE records.run_id = ? AND resources.status IN ('pending', 'failed', 'blocked') LIMIT 1",
                                               (run_id,)).fetchone()
                    if tasks is None:
                        raise MaterialError("No unfinished or failed material remains to collect.")
                    self._enqueue(connection, run_id, project_id)
            else:
                raise MaterialError("Unknown acquisition action.")
        return self.state(project_id, str(run["filter_run_id"]))

    def state(self, project_id: str, filter_run_id: str, offset: int = 0) -> dict[str, Any]:
        with self._connect() as connection:
            selection = connection.execute("SELECT content_sha256 FROM relevance_score_filters "
                                           "WHERE project_id = ? AND run_id = ?", (project_id, filter_run_id)).fetchone()
            if selection is None:
                raise MaterialError("Validate the relevance selection first.")
            run = connection.execute("SELECT * FROM source_material_runs WHERE project_id = ? AND filter_run_id = ?",
                                     (project_id, filter_run_id)).fetchone()
            if run is None:
                return {"run": None, "selection_sha256": selection[0], "policy": POLICY}
            jobs = [dict(row) for row in connection.execute(
                "SELECT id, status, error FROM jobs WHERE project_id = ? AND kind = 'source_material_collection' "
                "AND json_extract(workflow_input_snapshot_json, '$.run_id') = ? ORDER BY created_at DESC, rowid DESC",
                (project_id, run["id"]),
            )]
            latest_job_id = jobs[0]["id"] if jobs else None
            remaining_resources = connection.execute(
                "SELECT COUNT(*) FROM source_material_job_tasks tasks WHERE tasks.job_id = ? "
                "AND NOT EXISTS (SELECT 1 FROM source_material_attempts attempts "
                "WHERE attempts.resource_id = tasks.resource_id AND attempts.job_id = tasks.job_id)",
                (latest_job_id,),
            ).fetchone()[0]
            next_task = connection.execute(
                "SELECT resources.kind FROM source_material_job_tasks tasks "
                "JOIN source_material_resources resources ON resources.id = tasks.resource_id "
                "WHERE tasks.job_id = ? AND NOT EXISTS (SELECT 1 FROM source_material_attempts attempts "
                "WHERE attempts.resource_id = tasks.resource_id AND attempts.job_id = tasks.job_id) "
                "ORDER BY tasks.ordinal LIMIT 1", (latest_job_id,),
            ).fetchone()
            phase = None if next_task is None else {
                "metadata": "Collecting metadata and full text", "full_text": "Collecting full text",
                "full_text_fallback": "Checking full-text fallbacks", "data_links": "Collecting linked-data inventories",
                "supplements": "Collecting deferred supplements",
            }.get(next_task[0])
            retrying = connection.execute(
                "SELECT 1 FROM source_material_job_tasks tasks JOIN source_material_attempts attempts "
                "ON attempts.resource_id = tasks.resource_id WHERE tasks.job_id = ? "
                "AND attempts.job_id != tasks.job_id AND attempts.status = 'failed' LIMIT 1",
                (latest_job_id,),
            ).fetchone() is not None
            counts = {f"{row['kind']}:{row['status']}": row["n"] for row in connection.execute(
                "SELECT resources.kind, resources.status, COUNT(*) n FROM source_material_resources resources "
                "JOIN source_material_records records ON records.id = resources.record_id "
                "WHERE records.run_id = ? GROUP BY resources.kind, resources.status", (run["id"],),
            )}
            overview = connection.execute(
                "SELECT COUNT(*) total, SUM(CASE WHEN NOT EXISTS (SELECT 1 FROM source_material_resources r "
                "WHERE r.record_id = records.id AND (r.status = 'pending' OR (EXISTS "
                "(SELECT 1 FROM source_material_job_tasks tasks WHERE tasks.resource_id = r.id AND tasks.job_id = ?) "
                "AND NOT EXISTS (SELECT 1 FROM source_material_attempts attempts "
                "WHERE attempts.resource_id = r.id AND attempts.job_id = ?)))) THEN 1 ELSE 0 END) processed, "
                "SUM(CASE WHEN records.has_abstract = 1 AND NOT EXISTS (SELECT 1 FROM source_material_resources r "
                "WHERE r.record_id = records.id AND r.kind IN ('full_text', 'full_text_fallback') AND r.status = 'saved') "
                "THEN 1 ELSE 0 END) abstract_only FROM source_material_records records WHERE run_id = ?",
                (latest_job_id, latest_job_id, run["id"]),
            ).fetchone()
            assert overview is not None
            full_text_saved = connection.execute(
                "SELECT COUNT(DISTINCT r.record_id) FROM source_material_resources r "
                "JOIN source_material_records records ON records.id = r.record_id WHERE records.run_id = ? "
                "AND r.kind IN ('full_text', 'full_text_fallback') AND r.status = 'saved'", (run["id"],),
            ).fetchone()[0]
            fallback_eligible = connection.execute(
                "SELECT COUNT(*) FROM source_material_records records WHERE records.run_id = ? "
                "AND NOT EXISTS (SELECT 1 FROM source_material_resources r WHERE r.record_id = records.id "
                "AND ((r.kind IN ('full_text', 'full_text_fallback') AND r.status = 'saved') OR r.kind = 'full_text_fallback'))",
                (run["id"],),
            ).fetchone()[0]
            records = []
            for row in connection.execute("SELECT id, source, source_record_id, title FROM source_material_records "
                                          "WHERE run_id = ? ORDER BY ordinal LIMIT 25 OFFSET ?", (run["id"], offset)):
                resources = [dict(item) for item in connection.execute(
                    "SELECT r.kind, r.status, a.error, a.details_json, a.raw_byte_size, a.retrieved_at "
                    "FROM source_material_resources r LEFT JOIN source_material_attempts a ON a.id = "
                    "(SELECT id FROM source_material_attempts WHERE resource_id = r.id ORDER BY rowid DESC LIMIT 1) "
                    "WHERE r.record_id = ? ORDER BY r.rowid", (row["id"],),
                )]
                for item in resources:
                    if item["kind"] == "full_text" and item["status"] == "recovered":
                        recovery = connection.execute(
                            "SELECT a.id, a.details_json FROM source_material_resources r "
                            "JOIN source_material_attempts a ON a.id = (SELECT id FROM source_material_attempts "
                            "WHERE resource_id = r.id ORDER BY rowid DESC LIMIT 1) "
                            "WHERE r.record_id = ? AND r.kind = 'full_text_fallback' AND r.status = 'saved'", (row["id"],),
                        ).fetchone()
                        if recovery:
                            item["details_json"] = _json({**json.loads(item["details_json"] or "{}"),
                                "resolved_by_attempt_id": recovery["id"],
                                "recovery_provider": json.loads(recovery["details_json"]).get("provider", "supported fallback")})
                records.append({**dict(row), "resources": [
                    {key: value for key, value in item.items() if key != "details_json"} |
                    {"details": self._public_details(json.loads(item["details_json"] or "{}"))}
                    for item in resources
                ]})
        return {"run": {key: run[key] for key in ("id", "status", "stop_requested", "created_at", "completed_at")} |
                {"total": overview["total"], "processed": overview["processed"], "abstract_only": overview["abstract_only"],
                 "counts": counts, "records": records, "offset": offset, "jobs": jobs,
                 "retrying": retrying, "remaining_resources": remaining_resources,
                 "full_text_saved": full_text_saved, "fallback_eligible": fallback_eligible, "phase": phase},
                "selection_sha256": selection[0], "policy": json.loads(run["policy_json"])}

    @staticmethod
    def _public_details(details: dict[str, Any]) -> dict[str, Any]:
        # Bounded read model. Exact responses and complete inventories stay on disk.
        links = []
        for link in details.get("links", [])[:10]:
            target = link.get("Target", {})
            title = target.get("Title")
            identifier = target.get("Identifier", {})
            identifier = identifier if isinstance(identifier, dict) else {}
            links.append({"Target": {"Title": title[:1000] if isinstance(title, str) else None,
                                     "Identifier": {"ID": str(identifier.get("ID", ""))[:1000]}}})
        return {key: details[key] for key in ("file_count", "reported_count", "inventory_partial", "provider", "format", "resolved_by_attempt_id", "recovery_provider") if key in details} | {
            "license_statements": [str(value)[:2000] for value in details.get("license_statements", [])[:5]],
            "license_urls": [str(value)[:1000] for value in details.get("license_urls", [])[:5]],
            "files": details.get("files", [])[:10], "links": links,
        }

    def run_job(self, job_id: str, client: MaterialClient, stopped: Callable[[], bool] = lambda: False,
                resolver: FullTextResolver | None = None) -> None:
        with self._connect() as connection:
            job = connection.execute("SELECT * FROM jobs WHERE id = ? AND kind = 'source_material_collection' "
                                     "AND status = 'awaiting_response'", (job_id,)).fetchone()
            if job is None:
                raise MaterialError("The acquisition job is no longer active.")
            snapshot = json.loads(job["workflow_input_snapshot_json"])
            run_id = snapshot["run_id"]
            if snapshot["policy"] != POLICY:
                raise MaterialError("This run uses a different acquisition policy. It cannot silently resume with changed limits.")
            if "fallback_policy" in snapshot and snapshot["fallback_policy"] != FALLBACK_POLICY:
                raise MaterialError("The saved fallback policy differs. This attempt cannot silently change routes.")
            resource_ids = [row[0] for row in connection.execute(
                "SELECT resource_id FROM source_material_job_tasks WHERE job_id = ? ORDER BY ordinal", (job_id,),
            )]
            if hashlib.sha256(_json(resource_ids).encode()).hexdigest() != snapshot["resource_manifest_sha256"]:
                raise MaterialError("The acquisition task manifest does not match its saved digest.")
            connection.execute("UPDATE source_material_runs SET status = 'running' WHERE id = ?", (run_id,))
        paused = False
        for resource_id in resource_ids:
            with self._connect() as connection:
                run = connection.execute("SELECT stop_requested FROM source_material_runs WHERE id = ?", (run_id,)).fetchone()
                if stopped() or run[0]:
                    paused = True
                    break
                resource = connection.execute(
                    "SELECT r.id resource_id, r.kind, r.status, records.* FROM source_material_resources r "
                    "JOIN source_material_records records ON records.id = r.record_id "
                    "WHERE r.id = ? AND records.run_id = ?", (resource_id, run_id),
                ).fetchone()
                eligible_statuses = {"pending", "failed", "blocked", "unavailable", "needs_review"} if snapshot.get("local_only") else {"pending", "failed", "blocked"}
                if resource is None or resource["status"] not in eligible_statuses:
                    continue
                metadata = json.loads(resource["metadata_json"])
                if hashlib.sha256(resource["metadata_json"].encode()).hexdigest() != resource["metadata_sha256"]:
                    raise MaterialError("A source snapshot does not match its saved digest.")
                siblings = {row["kind"]: row for row in connection.execute(
                    "SELECT r.kind, r.status, a.id attempt_id, a.details_json FROM source_material_resources r "
                    "LEFT JOIN source_material_attempts a ON a.id = (SELECT id FROM source_material_attempts "
                    "WHERE resource_id = r.id ORDER BY rowid DESC LIMIT 1) WHERE r.record_id = ?", (resource["id"],),
                )}
            latest_metadata = json.loads(siblings["metadata"]["details_json"] or "{}").get("record", {})
            full_text_id = latest_metadata.get("pmcid") or metadata.get("pmcid")
            if not full_text_id and resource["source"] in {"PMC", "PPR"}:
                full_text_id = resource["source_record_id"]
            kind = resource["kind"]
            fallback_saved = "full_text_fallback" in siblings and siblings["full_text_fallback"]["status"] == "saved"
            limitation = xml_access_limitation(latest_metadata)
            if kind == "full_text_fallback":
                if siblings["full_text"]["status"] == "saved":
                    response = MaterialResponse("not_applicable", "", error="Europe PMC full text is already saved.")
                else:
                    if "fallback_policy" not in snapshot:
                        raise MaterialError("This job has no frozen fallback policy. Queue a new explicit retry.")
                    def stop_fallback() -> bool:
                        with self._connect() as current:
                            flag = current.execute("SELECT stop_requested FROM source_material_runs WHERE id = ?", (run_id,)).fetchone()
                        return stopped() or bool(flag[0])
                    cached = self._saved_bioc_response(resource_id, str(full_text_id))
                    if cached and cached.status != "saved" and preprint_server(latest_metadata):
                        # A cached PMC absence must not suppress another eligible route.
                        cached = None
                    if snapshot.get("local_only"):
                        if cached is None and preprint_server(latest_metadata):
                            with self._connect() as previous:
                                parent = previous.execute("SELECT id FROM source_material_attempts WHERE resource_id = ? ORDER BY rowid DESC LIMIT 1", (resource_id,)).fetchone()
                            response = MaterialResponse("pending", "", details={"preprint_route_version": PREPRINT_ROUTE_VERSION,
                                "prior_attempt_id": parent[0] if parent else None},
                                error="A supported preprint route is now identified. Resume collection to fetch this material.")
                        else:
                            response = cached or MaterialResponse("needs_review", "", error="Saved response could not be safely recovered. No download was attempted.")
                    else:
                        response = cached or (resolver or FullTextResolver()).resolve({**metadata, **latest_metadata,
                            "pmcid": full_text_id, "firstPublicationDate": latest_metadata.get("firstPublicationDate")}, stop_fallback)
                    response = MaterialResponse(response.status, response.request_url, response.http_status,
                        response.raw, response.content_type, {**response.details,
                        "metadata_attempt_id": siblings["metadata"]["attempt_id"]}, response.error)
            elif kind == "full_text" and fallback_saved:
                fallback = siblings["full_text_fallback"]
                fallback_details = json.loads(fallback["details_json"] or "{}")
                response = MaterialResponse("recovered", "", details={
                    "coverage_resolution_version": "fallback-covers-primary-v1",
                    "resolved_by_attempt_id": fallback["attempt_id"],
                    "recovery_provider": fallback_details.get("provider", "supported fallback"),
                }, error="Primary XML endpoint is not retried: verified full text is already saved through a fallback.")
            elif kind == "full_text" and limitation:
                response = MaterialResponse("unavailable", "", details={
                    "access_rule_version": XML_ACCESS_RULE_VERSION,
                    "metadata_attempt_id": siblings["metadata"]["attempt_id"],
                    "isOpenAccess": latest_metadata.get("isOpenAccess"),
                    "inEPMC": latest_metadata.get("inEPMC"),
                    "access_scope": "Europe PMC XML endpoint only",
                }, error=limitation)
            elif kind == "supplements" and latest_metadata.get("hasSuppl") == "N" and siblings["full_text"]["status"] != "saved":
                response = MaterialResponse("not_applicable", "", details={
                    "metadata_attempt_id": siblings["metadata"]["attempt_id"], "hasSuppl": "N",
                }, error="The source metadata explicitly reports no supplementary material.")
            elif kind == "supplements" and siblings["full_text"]["status"] != "saved" and fallback_saved:
                response = MaterialResponse("unsupported", "", details={
                    "resolved_by_attempt_id": siblings["full_text_fallback"]["attempt_id"],
                }, error="Full text is recovered, but supplementary discovery still requires Europe PMC article XML. Supplement availability is unknown, not confirmed absent; the same retry cannot resolve this adapter limitation.")
            elif kind in {"full_text", "supplements"} and not full_text_id:
                missing_status = "blocked" if siblings["metadata"]["status"] in {"failed", "blocked", "pending"} else "needs_review" if siblings["metadata"]["status"] == "needs_review" else "unsupported"
                response = MaterialResponse(missing_status,
                                            "", error="No supported full-text identifier is available through Europe PMC.")
            elif kind == "supplements" and siblings["full_text"]["status"] != "saved":
                # Dependency failure is not another failed external request.
                parent_status = siblings["full_text"]["status"]
                status = "blocked" if parent_status in {"failed", "blocked", "pending"} else "unavailable" if parent_status == "unavailable" else "unsupported" if parent_status == "unsupported" else "needs_review"
                response = MaterialResponse(status, "", error="Full text has not been collected; supplements were not requested.")
            elif kind == "supplements" and not json.loads(siblings["full_text"]["details_json"] or "{}").get("has_supplements"):
                response = MaterialResponse("not_applicable", "", error="The article XML declares no supplementary material.")
            else:
                response = client.fetch(kind, resource["source"], str(full_text_id) if kind in {"full_text", "supplements"}
                                        else resource["source_record_id"])
            if kind == "supplements" and response.status == "saved":
                full_text_details = json.loads(siblings["full_text"]["details_json"] or "{}")
                response = MaterialResponse(response.status, response.request_url, response.http_status,
                                            response.raw, response.content_type, {
                    **response.details, "article_license_statements": full_text_details.get("license_statements", []),
                    "license_scope": "Article license recorded as context, not assumed to license every supplement.",
                }, response.error)
            self._save(resource_id, job_id, response, kind)
            if not snapshot.get("local_only"):
                time.sleep(0.2)
        with self._connect() as connection:
            connection.execute("UPDATE source_material_runs SET status = ?, stop_requested = ?, completed_at = ? WHERE id = ?",
                               ("paused" if paused else "completed", int(paused), None if paused else _now(), run_id))
            connection.execute("UPDATE jobs SET status = 'completed', completed_at = ? WHERE id = ? AND status = 'awaiting_response'",
                               (_now(), job_id))

    def _saved_bioc_response(self, resource_id: str, pmcid: str) -> MaterialResponse | None:
        """Append a corrected outcome on resume, without modifying or refetching old raw evidence."""
        with self._connect() as connection:
            attempt = connection.execute("SELECT * FROM source_material_attempts WHERE resource_id = ? ORDER BY rowid DESC LIMIT 1",
                                         (resource_id,)).fetchone()
        expected_url = f"https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_xml/{pmcid}/unicode"
        if attempt is not None and attempt["status"] == "unavailable":
            details = json.loads(attempt["details_json"])
            if details.get("routes") == [] and details.get("resolver_policy"):
                return MaterialResponse("unsupported", "", details={
                    "prior_attempt_id": attempt["id"], "reused_saved_response": True,
                    "classification_version": "material-outcomes-v2",
                }, error="No enabled full-text route or supported identifier. Availability elsewhere is unknown; repeating this request cannot help.")
        if attempt is None or attempt["status"] != "failed" or attempt["request_url"] != expected_url or attempt["http_status"] not in {None, 200}:
            return None
        if not attempt["raw_path"] or not attempt["raw_byte_size"] or attempt["raw_byte_size"] > 20_000_000:
            return None
        routes = json.loads(attempt["details_json"] or "{}").get("routes", [])
        if attempt["http_status"] is None and not any(route.get("url") == expected_url and route.get("http_status") == 200 for route in routes):
            return None
        root = (self.database_path.parent / "artifacts").resolve()
        path = (root / attempt["raw_path"]).resolve()
        if not path.is_relative_to(root):
            raise MaterialError("The saved fallback response is outside the artifact directory.")
        try:
            with path.open("rb") as saved:
                raw = saved.read(20_000_001)
        except OSError:
            return None
        if len(raw) != attempt["raw_byte_size"] or hashlib.sha256(raw).hexdigest() != attempt["raw_sha256"]:
            raise MaterialError("The saved fallback response does not match its digest.")
        return interpret_bioc(MaterialResponse("saved", expected_url, 200, raw, attempt["content_type"], {
            "prior_attempt_id": attempt["id"],
            "prior_raw_sha256": attempt["raw_sha256"], "access_scope": "PMC BioC endpoint only",
            "reused_saved_response": True,
        }), pmcid)

    def _save(self, resource_id: str, job_id: str, response: MaterialResponse, kind: str) -> None:
        attempt_id = str(uuid4())
        details = json.loads(_json(response.details))
        details["outcome_rules_version"] = "material-outcomes-v2"
        details["preprint_route_version"] = PREPRINT_ROUTE_VERSION
        discoveries = [details.get("discovery"), *[route.get("discovery") for route in details.get("routes", [])]]
        for index, discovery in enumerate(discoveries):
            if not isinstance(discovery, dict) or "raw_base64" not in discovery:
                continue
            content = base64.b64decode(discovery.pop("raw_base64"), validate=True)
            discovery_path = f"source-material/{attempt_id}/discovery-{index}.json"
            target = self.database_path.parent / "artifacts" / discovery_path
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as output:
                output.write(content)
                output.flush()
                os.fsync(output.fileno())
            discovery.update(raw_path=discovery_path, raw_sha256=hashlib.sha256(content).hexdigest(), raw_byte_size=len(content))
        relative: str | None = None
        digest: str | None = None
        size: int | None = None
        if response.raw is not None:
            filename = {"metadata": "metadata.json", "full_text": "fulltext.xml", "full_text_fallback": "fallback-fulltext.xml",
                        "supplements": "supplements.zip", "data_links": "data-links.json"}[kind]
            relative = f"source-material/{attempt_id}/{filename}"
            path = self.database_path.parent / "artifacts" / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            # Unique attempts never overwrite an earlier response.
            temporary = path.with_suffix(".tmp")
            try:
                with temporary.open("xb") as output:
                    output.write(response.raw)
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)
            digest, size = hashlib.sha256(response.raw).hexdigest(), len(response.raw)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute("SELECT 1 FROM jobs WHERE id = ? AND status = 'awaiting_response'", (job_id,)).fetchone() is None:
                raise MaterialError("The acquisition attempt is no longer active.")
            if kind == "full_text_fallback" and response.status == "saved":
                primary = connection.execute(
                    "SELECT primary_resource.id, a.id attempt_id FROM source_material_resources primary_resource "
                    "LEFT JOIN source_material_attempts a ON a.id = (SELECT id FROM source_material_attempts "
                    "WHERE resource_id = primary_resource.id ORDER BY rowid DESC LIMIT 1) "
                    "WHERE primary_resource.record_id = (SELECT record_id FROM source_material_resources WHERE id = ?) "
                    "AND primary_resource.kind = 'full_text' AND primary_resource.status IN ('pending', 'failed', 'blocked')",
                    (resource_id,),
                ).fetchone()
                if primary:
                    details.update(covered_primary_resource_id=primary["id"], prior_primary_attempt_id=primary["attempt_id"],
                                   coverage_resolution_version="fallback-covers-primary-v1")
                    # This mutable cursor is resolved by the new immutable fallback
                    # attempt, not by overwriting its earlier failed HTTP response.
                    connection.execute("UPDATE source_material_resources SET status = 'recovered' WHERE id = ?", (primary["id"],))
            connection.execute(
                "INSERT INTO source_material_attempts (id, resource_id, job_id, status, request_url, http_status, "
                "retrieved_at, raw_path, raw_sha256, raw_byte_size, content_type, details_json, error) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (attempt_id, resource_id, job_id, response.status, response.request_url, response.http_status,
                 _now(), relative, digest, size, response.content_type, _json(details), response.error),
            )
            connection.execute("UPDATE source_material_resources SET status = ? WHERE id = ? AND status IN ('pending', 'failed', 'blocked', 'unavailable', 'needs_review')",
                               (response.status, resource_id))
