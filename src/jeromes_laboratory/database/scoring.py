"""Frozen relevance selections and between-call batch scheduling."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path
from typing import cast
from uuid import uuid4

from jeromes_laboratory.database.relevance import distinct_source_records
from jeromes_laboratory.llm.pricing import estimate_standard_cost
from jeromes_laboratory.workflow.relevance import (
    SAMPLE_ALGORITHM_VERSION,
    _balanced_order,
    estimate_text_tokens,
    scoring_batches,
)

BATCH_INSTRUCTIONS = files("jeromes_laboratory.workflow.prompts").joinpath(
    "relevance_batch_v2.txt"
).read_text(encoding="utf-8").strip()


class ScoringError(ValueError):
    pass


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def _has_downstream_work(connection: sqlite3.Connection, project_id: str) -> bool:
    first = connection.execute(
        "SELECT MIN(jobs.rowid) AS first_rowid FROM relevance_scoring_batch_jobs links "
        "JOIN jobs ON jobs.id = links.job_id JOIN relevance_scoring_runs runs "
        "ON runs.id = links.run_id WHERE runs.project_id = ?",
        (project_id,),
    ).fetchone()
    if first is None or first["first_rowid"] is None:
        return False
    return connection.execute(
        "SELECT 1 FROM jobs WHERE project_id = ? AND rowid > ? "
        "AND kind != 'relevance_scoring_batch' LIMIT 1",
        (project_id, first["first_rowid"]),
    ).fetchone() is not None


def enqueue_next_batch(connection: sqlite3.Connection, run_id: str) -> str | None:
    """Called only inside a write transaction; never enqueue across a pause."""
    run = connection.execute(
        "SELECT * FROM relevance_scoring_runs WHERE id = ?", (run_id,),
    ).fetchone()
    if run is None or run["stop_requested"] or run["status"] != "running":
        return None
    batches = json.loads(run["batches_json"])
    index = int(run["next_batch_index"])
    if index >= len(batches):
        connection.execute(
            "UPDATE relevance_scoring_runs SET status = 'completed', completed_at = ? WHERE id = ?",
            (_now(), run_id),
        )
        return None
    active = connection.execute(
        "SELECT 1 FROM relevance_scoring_batch_jobs links JOIN jobs ON jobs.id = links.job_id "
        "WHERE links.run_id = ? AND links.batch_index = ? "
        "AND jobs.status IN ('pending', 'awaiting_response', 'completed') LIMIT 1",
        (run_id, index),
    ).fetchone()
    if active is not None:
        return None
    prompt = connection.execute(
        "SELECT content_json FROM artifact_versions WHERE id = ?", (run["prompt_artifact_id"],),
    ).fetchone()
    project = connection.execute(
        "SELECT scientific_question FROM projects WHERE id = ?", (run["project_id"],),
    ).fetchone()
    if prompt is None or project is None:
        raise ScoringError("The frozen prompt or project is unavailable.")
    rules = str(json.loads(prompt["content_json"])["scoring_prompt"])
    job_id = str(uuid4())
    snapshot = {
        "schema_version": 2, "run_id": run_id, "batch_index": index,
        "prompt_artifact_id": run["prompt_artifact_id"],
        "records": [{**record, "slot": f"r{position}"}
                    for position, record in enumerate(batches[index], start=1)],
    }
    connection.execute(
        "INSERT INTO jobs (id, project_id, kind, status, created_at, provider, model, "
        "scientific_question_snapshot, prompt_snapshot, prompt_template_id, "
        "prompt_template_version, workflow_input_snapshot_json) "
        "VALUES (?, ?, 'relevance_scoring_batch', 'pending', ?, ?, ?, ?, ?, "
        "'relevance-scoring-batch', '2', ?)",
        (job_id, run["project_id"], _now(), run["provider"], run["model"],
         project["scientific_question"], rules + "\n\n" + BATCH_INSTRUCTIONS, _json(snapshot)),
    )
    connection.execute(
        "INSERT INTO relevance_scoring_batch_jobs (job_id, run_id, batch_index) VALUES (?, ?, ?)",
        (job_id, run_id, index),
    )
    return job_id


class ScoringRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def preview(
        self, project_id: str, retrieval_job_id: str, prompt_job_id: str,
        count: int, seed: int,
    ) -> dict[str, object]:
        if not 1 <= count <= 100_000 or not 0 <= seed <= 2_147_483_647:
            raise ScoringError("Choose 1–100,000 records and a nonnegative seed.")
        with self._connect() as connection:
            retrieval = connection.execute(
                "SELECT 1 FROM jobs WHERE id = ? AND project_id = ? "
                "AND kind = 'source_retrieval' AND status = 'completed'",
                (retrieval_job_id, project_id),
            ).fetchone()
            prompt = connection.execute(
                "SELECT versions.id, versions.content_json FROM jobs "
                "JOIN artifact_effective_versions selected ON selected.job_id = jobs.id "
                "JOIN artifact_versions versions ON versions.id = selected.artifact_version_id "
                "WHERE jobs.id = ? AND jobs.project_id = ? "
                "AND jobs.kind = 'relevance_prompt_generation' AND jobs.status = 'completed' "
                "AND versions.kind = 'relevance_prompt_generation_output'",
                (prompt_job_id, project_id),
            ).fetchone()
            existing_run = connection.execute(
                "SELECT 1 FROM relevance_scoring_runs WHERE project_id = ? LIMIT 1",
                (project_id,),
            ).fetchone()
            if retrieval is None or prompt is None:
                raise ScoringError("Complete retrieval and generate a scoring prompt first.")
            if existing_run is not None:
                raise ScoringError(
                    "This project already has a scoring run. Resume it if paused or failed; "
                    "a second scoring run is not allowed."
                )
        records = distinct_source_records(self.database_path, retrieval_job_id)
        if not records:
            raise ScoringError("This retrieval has no saved distinct source records to score.")
        selected = _balanced_order(records, seed)[:min(count, len(records))]
        rules = str(json.loads(prompt["content_json"])["scoring_prompt"])
        batches = scoring_batches(selected, rules + "\n\n" + BATCH_INSTRUCTIONS)
        manifest = [{"source": row["source"], "source_record_id": row["source_record_id"]}
                    for row in selected]
        input_tokens = sum(estimate_text_tokens(rules + BATCH_INSTRUCTIONS + _json(batch)) + 250
                           for batch in batches)
        output_tokens = len(selected) * 100 + len(batches) * 50
        return {
            "available_unscored": len(records), "selected_count": len(selected),
            "seed": seed, "algorithm_version": SAMPLE_ALGORITHM_VERSION,
            "manifest_sha256": hashlib.sha256(_json(manifest).encode("utf-8")).hexdigest(),
            "prompt_artifact_id": prompt["id"], "batches": batches,
            "batch_sizes": [len(batch) for batch in batches],
            "estimated_input_tokens": input_tokens, "estimated_output_tokens": output_tokens,
        }

    def start(
        self, project_id: str, retrieval_job_id: str, prompt_job_id: str,
        count: int, seed: int, provider: str, model: str,
        expected_manifest_sha256: str, expected_prompt_artifact_id: str,
    ) -> str:
        plan = self.preview(project_id, retrieval_job_id, prompt_job_id, count, seed)
        if (plan["manifest_sha256"] != expected_manifest_sha256
                or plan["prompt_artifact_id"] != expected_prompt_artifact_id):
            raise ScoringError("The scoring selection or prompt changed. Review the selection again.")
        run_id = str(uuid4())
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute(
                "SELECT 1 FROM relevance_scoring_runs WHERE project_id = ? LIMIT 1",
                (project_id,),
            ).fetchone():
                raise ScoringError("This project already has a scoring run; a second is not allowed.")
            effective = connection.execute(
                "SELECT artifact_version_id FROM artifact_effective_versions WHERE job_id = ?",
                (prompt_job_id,),
            ).fetchone()
            if effective is None or effective["artifact_version_id"] != plan["prompt_artifact_id"]:
                raise ScoringError("The scoring prompt changed. Review the selection again.")
            connection.execute(
                "INSERT INTO relevance_scoring_runs (id, project_id, retrieval_job_id, "
                "prompt_artifact_id, provider, model, seed, algorithm_version, "
                "manifest_sha256, batches_json, batch_sizes_json, selected_count, "
                "estimated_input_tokens, estimated_output_tokens, estimate_method, "
                "status, stop_requested, next_batch_index, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'utf8-bytes-div-4-v1', "
                "'running', 0, 0, ?)",
                (run_id, project_id, retrieval_job_id, plan["prompt_artifact_id"],
                 provider, model, seed, plan["algorithm_version"], plan["manifest_sha256"],
                 _json(plan["batches"]), _json(plan["batch_sizes"]), plan["selected_count"],
                 plan["estimated_input_tokens"], plan["estimated_output_tokens"], _now()),
            )
            enqueue_next_batch(connection, run_id)
        return run_id

    def pause(self, run_id: str, project_id: str) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            run = connection.execute(
                "SELECT status FROM relevance_scoring_runs WHERE id = ? AND project_id = ?",
                (run_id, project_id),
            ).fetchone()
            if run is None or run["status"] != "running":
                raise ScoringError("Only a running scoring run can be paused.")
            connection.execute(
                "UPDATE relevance_scoring_runs SET stop_requested = 1 WHERE id = ?", (run_id,),
            )
            connection.execute(
                "UPDATE jobs SET status = 'cancelled', completed_at = ? WHERE id IN "
                "(SELECT links.job_id FROM relevance_scoring_batch_jobs links "
                "WHERE links.run_id = ?) AND status = 'pending'", (_now(), run_id),
            )
            if connection.execute(
                "SELECT 1 FROM relevance_scoring_batch_jobs links JOIN jobs ON jobs.id = links.job_id "
                "WHERE links.run_id = ? AND jobs.status = 'awaiting_response'", (run_id,),
            ).fetchone() is None:
                connection.execute(
                    "UPDATE relevance_scoring_runs SET status = 'paused' WHERE id = ?", (run_id,),
                )

    def resume(self, run_id: str, project_id: str) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            run = connection.execute(
                "SELECT status FROM relevance_scoring_runs WHERE id = ? AND project_id = ?",
                (run_id, project_id),
            ).fetchone()
            if run is None or run["status"] not in {"paused", "failed"}:
                raise ScoringError("Only a paused or failed scoring run can be resumed.")
            if _has_downstream_work(connection, project_id):
                raise ScoringError("Later work exists; resume scoring in a fork instead.")
            connection.execute(
                "UPDATE relevance_scoring_runs SET status = 'running', stop_requested = 0 WHERE id = ?",
                (run_id,),
            )
            enqueue_next_batch(connection, run_id)

    def progress(self, project_id: str) -> list[dict[str, object]]:
        with self._connect() as connection:
            runs = connection.execute(
                "SELECT * FROM relevance_scoring_runs WHERE project_id = ? ORDER BY created_at DESC",
                (project_id,),
            ).fetchall()
            result: list[dict[str, object]] = []
            for run in runs:
                batch_sizes = json.loads(run["batch_sizes_json"])
                scores = connection.execute(
                    "SELECT source, outcome, COUNT(*) AS count FROM relevance_scores "
                    "WHERE run_id = ? GROUP BY source, outcome", (run["id"],),
                ).fetchall()
                by_score: dict[str, dict[str, object]] = {}
                for row in scores:
                    item = by_score.setdefault(str(row["outcome"]), {"count": 0, "sources": {}})
                    item["count"] = cast(int, item["count"]) + int(row["count"])
                    cast(dict[str, int], item["sources"])[str(row["source"])] = int(row["count"])
                sample_rows = connection.execute(
                    "SELECT sample.outcome, sample.source, sample.source_record_id, "
                    "(SELECT records.title FROM publication_source_records records "
                    "JOIN search_runs searches ON searches.id = records.run_id "
                    "WHERE searches.job_id = ? AND records.source = sample.source "
                    "AND records.source_record_id = sample.source_record_id "
                    "AND records.title IS NOT NULL "
                    "ORDER BY searches.rowid, records.rowid LIMIT 1) AS title "
                    "FROM (SELECT outcome, source, source_record_id, "
                    "ROW_NUMBER() OVER (PARTITION BY outcome ORDER BY rowid) AS sample_rank "
                    "FROM relevance_scores WHERE run_id = ?) sample "
                    "WHERE sample.sample_rank <= 3 ORDER BY sample.outcome, sample.sample_rank",
                    (run["retrieval_job_id"], run["id"]),
                ).fetchall()
                for sample in sample_rows:
                    item = by_score[str(sample["outcome"])]
                    cast(list[dict[str, str]], item.setdefault("samples", [])).append({
                        "source": str(sample["source"]),
                        "source_record_id": str(sample["source_record_id"]),
                        "title": str(sample["title"] or "Untitled record"),
                    })
                jobs = connection.execute(
                    "SELECT jobs.id, jobs.status, links.batch_index, jobs.error, calls.total_tokens, "
                    "calls.estimated_cost, calls.input_tokens, calls.output_tokens FROM relevance_scoring_batch_jobs links "
                    "JOIN jobs ON jobs.id = links.job_id LEFT JOIN llm_calls calls ON calls.job_id = jobs.id "
                    "WHERE links.run_id = ? ORDER BY links.batch_index, jobs.created_at", (run["id"],),
                ).fetchall()
                completed = int(run["next_batch_index"])
                remaining_records = sum(batch_sizes[completed:])
                actual_input = sum(int(job["input_tokens"] or 0) for job in jobs if job["status"] == "completed")
                actual_output = sum(int(job["output_tokens"] or 0) for job in jobs if job["status"] == "completed")
                completed_records = sum(batch_sizes[:completed])
                if completed_records:
                    remaining_input = round(actual_input * remaining_records / completed_records)
                    remaining_output = round(actual_output * remaining_records / completed_records)
                else:
                    remaining_input = int(run["estimated_input_tokens"])
                    remaining_output = int(run["estimated_output_tokens"])
                remaining_cost = estimate_standard_cost(
                    str(run["provider"]), str(run["model"]), remaining_input,
                    remaining_output, aggregate_batches=True,
                )
                result.append({
                    "id": run["id"], "status": run["status"], "stop_requested": bool(run["stop_requested"]),
                    "provider": run["provider"], "model": run["model"], "seed": run["seed"],
                    "selected_count": int(run["selected_count"]),
                    "scored_count": sum(cast(int, value["count"]) for value in by_score.values()),
                    "batch_count": len(batch_sizes), "completed_batches": completed,
                    "remaining_batches": len(batch_sizes) - completed,
                    "batch_sizes": batch_sizes,
                    "by_score": by_score,
                    "jobs": [dict(job) for job in jobs],
                    "total_tokens": sum(int(job["total_tokens"] or 0) for job in jobs),
                    "estimated_cost_usd": sum(float(job["estimated_cost"] or 0) for job in jobs),
                    "remaining_token_estimate": remaining_input + remaining_output,
                    "remaining_cost": remaining_cost,
                })
        return result
