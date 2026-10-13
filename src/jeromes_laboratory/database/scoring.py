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

from jeromes_laboratory.database.connections import connect_database
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


def enqueue_next_batch(
    connection: sqlite3.Connection, run_id: str, *, retry_of_job_id: str | None = None,
    batch_index: int | None = None,
) -> str | None:
    """Called only inside a write transaction; never enqueue across a pause."""
    run = connection.execute(
        "SELECT id, project_id, prompt_artifact_id, provider, model, status, stop_requested, "
        "parallel_batches FROM relevance_scoring_runs WHERE id = ?", (run_id,),
    ).fetchone()
    if run is None or run["stop_requested"] or run["status"] != "running":
        return None
    if connection.execute(
        "SELECT 1 FROM relevance_scoring_confirmations WHERE run_id = ?", (run_id,),
    ).fetchone() is not None:
        return None
    total = int(connection.execute(
        "SELECT COUNT(*) FROM relevance_scoring_batch_inputs WHERE run_id = ?", (run_id,),
    ).fetchone()[0])
    existing = connection.execute(
        "SELECT links.batch_index, jobs.status FROM relevance_scoring_batch_jobs links "
        "JOIN jobs ON jobs.id = links.job_id WHERE links.run_id = ? "
        "AND jobs.status IN ('pending', 'awaiting_response', 'completed')", (run_id,),
    ).fetchall()
    blocked = {int(row["batch_index"]) for row in existing}
    if sum(row["status"] != "completed" for row in existing) >= int(run["parallel_batches"]):
        return None
    index = batch_index if batch_index is not None else next(
        (index for index in range(total) if index not in blocked), total,
    )
    if index in blocked or index >= total:
        return None
    batch = json.loads(connection.execute(
        "SELECT records_json FROM relevance_scoring_batch_inputs WHERE run_id = ? AND batch_index = ?",
        (run_id, index),
    ).fetchone()[0])
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
                    for position, record in enumerate(batch, start=1)],
        "automatic_retry_attempt": 1 if retry_of_job_id else 0,
        "retry_of_job_id": retry_of_job_id,
        "parallel_batches": int(run["parallel_batches"]),
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


def completed_batch_indices(connection: sqlite3.Connection, run_id: str) -> set[int]:
    return {int(row[0]) for row in connection.execute(
        "SELECT DISTINCT links.batch_index FROM relevance_scoring_batch_jobs links "
        "JOIN jobs ON jobs.id = links.job_id WHERE links.run_id = ? AND jobs.status = 'completed'",
        (run_id,),
    ).fetchall()}


def schedule_scoring_batches(connection: sqlite3.Connection, run_id: str) -> None:
    """Reconcile out-of-order completions and fill only the bounded execution window."""
    run = connection.execute(
        "SELECT status, stop_requested, batch_sizes_json, parallel_batches "
        "FROM relevance_scoring_runs WHERE id = ?", (run_id,),
    ).fetchone()
    if run is None:
        return
    total = len(json.loads(run["batch_sizes_json"]))
    completed = completed_batch_indices(connection, run_id)
    first_missing = next((index for index in range(total) if index not in completed), total)
    connection.execute(
        "UPDATE relevance_scoring_runs SET next_batch_index = ? WHERE id = ?",
        (first_missing, run_id),
    )
    if run["stop_requested"]:
        connection.execute(
            "UPDATE jobs SET status = 'cancelled', completed_at = ? WHERE status = 'pending' "
            "AND id IN (SELECT job_id FROM relevance_scoring_batch_jobs WHERE run_id = ?)",
            (_now(), run_id),
        )
        if connection.execute(
            "SELECT 1 FROM relevance_scoring_batch_jobs links JOIN jobs ON jobs.id = links.job_id "
            "WHERE links.run_id = ? AND jobs.status = 'awaiting_response'", (run_id,),
        ).fetchone() is None:
            connection.execute(
                "UPDATE relevance_scoring_runs SET status = 'paused' WHERE id = ?", (run_id,),
            )
        return
    if run["status"] != "running":
        return
    if len(completed) == total:
        connection.execute(
            "UPDATE relevance_scoring_runs SET status = 'completed', completed_at = ? WHERE id = ?",
            (_now(), run_id),
        )
        return
    for _ in range(int(run["parallel_batches"])):
        if enqueue_next_batch(connection, run_id) is None:
            break


class ScoringRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def _connect(self) -> sqlite3.Connection:
        return connect_database(self.database_path)

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
        parallel_batches: int = 1,
    ) -> str:
        if not 1 <= parallel_batches <= 8:
            raise ScoringError("Choose 1–8 parallel batches.")
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
                "status, stop_requested, next_batch_index, created_at, parallel_batches, "
                "retrieved_record_count) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'utf8-bytes-div-4-v1', "
                "'running', 0, 0, ?, ?, ?)",
                (run_id, project_id, retrieval_job_id, plan["prompt_artifact_id"],
                 provider, model, seed, plan["algorithm_version"], plan["manifest_sha256"],
                 _json(plan["batches"]), _json(plan["batch_sizes"]), plan["selected_count"],
                 plan["estimated_input_tokens"], plan["estimated_output_tokens"], _now(),
                 parallel_batches, plan["available_unscored"]),
            )
            connection.executemany(
                "INSERT INTO relevance_scoring_batch_inputs (run_id, batch_index, records_json) "
                "VALUES (?, ?, ?)",
                [(run_id, index, _json(batch)) for index, batch in enumerate(
                    cast(list[list[dict[str, object]]], plan["batches"]),
                )],
            )
            schedule_scoring_batches(connection, run_id)
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
            schedule_scoring_batches(connection, run_id)

    def resume(self, run_id: str, project_id: str, parallel_batches: int | None = None) -> None:
        if parallel_batches is not None and not 1 <= parallel_batches <= 8:
            raise ScoringError("Choose 1–8 parallel batches.")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            run = connection.execute(
                "SELECT status, parallel_batches, stop_requested FROM relevance_scoring_runs "
                "WHERE id = ? AND project_id = ?",
                (run_id, project_id),
            ).fetchone()
            if run is None or run["status"] not in {"paused", "failed"}:
                if (run is not None and run["status"] == "running" and not run["stop_requested"]
                        and parallel_batches in {None, run["parallel_batches"]}):
                    schedule_scoring_batches(connection, run_id)
                    return
                raise ScoringError("Only a paused or failed scoring run can be resumed.")
            if connection.execute(
                "SELECT 1 FROM relevance_scoring_confirmations WHERE run_id = ?", (run_id,),
            ).fetchone() is not None:
                raise ScoringError("The confirmed scored set is locked.")
            if _has_downstream_work(connection, project_id):
                raise ScoringError("Later work exists; resume scoring in a fork instead.")
            connection.execute(
                "UPDATE relevance_scoring_runs SET status = 'running', stop_requested = 0, "
                "parallel_batches = ? WHERE id = ?",
                (parallel_batches or run["parallel_batches"], run_id),
            )
            schedule_scoring_batches(connection, run_id)

    def extend(
        self, run_id: str, project_id: str, additional_count: int,
        parallel_batches: int | None = None,
    ) -> int:
        """Append new seeded, distinct-source records to the same completed run."""
        if not 1 <= additional_count <= 100_000:
            raise ScoringError("Choose 1–100,000 additional records.")
        if parallel_batches is not None and not 1 <= parallel_batches <= 8:
            raise ScoringError("Choose 1–8 parallel batches.")
        with self._connect() as connection:
            run = connection.execute(
                "SELECT * FROM relevance_scoring_runs WHERE id = ? AND project_id = ?",
                (run_id, project_id),
            ).fetchone()
            if run is None:
                raise ScoringError("The scoring run was not found.")
            retrieval_job_id = str(run["retrieval_job_id"])
        available = _balanced_order(
            distinct_source_records(self.database_path, retrieval_job_id), int(run["seed"]),
        )
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                "SELECT * FROM relevance_scoring_runs WHERE id = ? AND project_id = ?",
                (run_id, project_id),
            ).fetchone()
            if current is None or current["status"] != "completed":
                raise ScoringError("Finish the current scoring plan before adding records.")
            if current["algorithm_version"] != SAMPLE_ALGORITHM_VERSION:
                raise ScoringError("This run's selection algorithm cannot be extended safely.")
            if current["seed"] != run["seed"] or current["retrieval_job_id"] != retrieval_job_id:
                raise ScoringError("The scoring selection changed; review the run again.")
            if connection.execute(
                "SELECT 1 FROM relevance_scoring_confirmations WHERE run_id = ?", (run_id,),
            ).fetchone() is not None:
                raise ScoringError("The confirmed scored set is locked. Fork to investigate more records.")
            if _has_downstream_work(connection, project_id):
                raise ScoringError("Later work exists; extend scoring in a fork instead.")
            batches = json.loads(current["batches_json"])
            selected_keys = {
                (str(record["source"]), str(record["source_record_id"]))
                for batch in batches for record in batch
            }
            if len(selected_keys) != int(current["selected_count"]):
                raise ScoringError("The frozen scoring selection has duplicate identities.")
            scored_count = connection.execute(
                "SELECT COUNT(*) FROM relevance_scores WHERE run_id = ?", (run_id,),
            ).fetchone()[0]
            if int(scored_count) != int(current["selected_count"]):
                raise ScoringError("The completed score list is incomplete; extension is unsafe.")
            available_keys = {(str(record["source"]), str(record["source_record_id"]))
                              for record in available}
            if not selected_keys <= available_keys:
                raise ScoringError("The original retrieval records changed; extension is unsafe.")
            unselected = [record for record in available
                          if (str(record["source"]), str(record["source_record_id"])) not in selected_keys]
            if additional_count > len(unselected):
                raise ScoringError(f"Only {len(unselected)} unscored source records remain.")
            prompt = connection.execute(
                "SELECT content_json FROM artifact_versions WHERE id = ?",
                (current["prompt_artifact_id"],),
            ).fetchone()
            if prompt is None:
                raise ScoringError("The frozen scoring prompt is unavailable.")
            rules = str(json.loads(prompt["content_json"])["scoring_prompt"])
            added = unselected[:additional_count]
            new_batches = scoring_batches(added, rules + "\n\n" + BATCH_INSTRUCTIONS,
                                          max_records=5)
            manifest = [{"source": record["source"], "source_record_id": record["source_record_id"]}
                        for record in added]
            manifest_json = _json(manifest)
            connection.execute(
                "INSERT INTO relevance_scoring_extensions "
                "(id, run_id, previous_count, added_count, added_manifest_json, "
                "added_manifest_sha256, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (str(uuid4()), run_id, current["selected_count"], additional_count,
                 manifest_json, hashlib.sha256(manifest_json.encode("utf-8")).hexdigest(), _now()),
            )
            batch_sizes = json.loads(current["batch_sizes_json"])
            connection.executemany(
                "INSERT INTO relevance_scoring_batch_inputs (run_id, batch_index, records_json) "
                "VALUES (?, ?, ?)",
                [(run_id, len(batch_sizes) + index, _json(batch))
                 for index, batch in enumerate(new_batches)],
            )
            added_input = sum(estimate_text_tokens(rules + BATCH_INSTRUCTIONS + _json(batch)) + 250
                              for batch in new_batches)
            connection.execute(
                "UPDATE relevance_scoring_runs SET batches_json = ?, batch_sizes_json = ?, "
                "selected_count = selected_count + ?, estimated_input_tokens = estimated_input_tokens + ?, "
                "estimated_output_tokens = estimated_output_tokens + ?, status = 'running', "
                "completed_at = NULL, stop_requested = 0 WHERE id = ?",
                (_json(batches + new_batches),
                 _json(batch_sizes + [len(batch) for batch in new_batches]),
                 additional_count, added_input, additional_count * 100 + len(new_batches) * 50,
                 run_id),
            )
            if parallel_batches is not None:
                connection.execute(
                    "UPDATE relevance_scoring_runs SET parallel_batches = ? WHERE id = ?",
                    (parallel_batches, run_id),
                )
            schedule_scoring_batches(connection, run_id)
        return additional_count

    def confirm(self, run_id: str, project_id: str) -> dict[str, object]:
        """Freeze only completed scores, including a deliberately paused subset."""
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            run = connection.execute(
                "SELECT * FROM relevance_scoring_runs WHERE id = ? AND project_id = ?",
                (run_id, project_id),
            ).fetchone()
            if run is None or run["status"] not in {"completed", "paused"}:
                raise ScoringError("Finish all selected batches or pause scoring before validation.")
            if connection.execute(
                "SELECT 1 FROM relevance_scoring_batch_jobs links JOIN jobs ON jobs.id = links.job_id "
                "WHERE links.run_id = ? AND jobs.status IN ('pending', 'awaiting_response')",
                (run_id,),
            ).fetchone() is not None:
                raise ScoringError("Wait for the current request to finish before validation.")
            if connection.execute(
                "SELECT 1 FROM relevance_scoring_confirmations WHERE run_id = ?", (run_id,),
            ).fetchone() is not None:
                raise ScoringError("This scored set has already been confirmed.")
            if _has_downstream_work(connection, project_id):
                raise ScoringError("Later work exists; confirm scoring in a fork instead.")
            batches = json.loads(run["batches_json"])
            completed = completed_batch_indices(connection, run_id)
            expected = {(str(record["source"]), str(record["source_record_id"]))
                        for index, batch in enumerate(batches) if index in completed
                        for record in batch}
            scores = [dict(row) for row in connection.execute(
                "SELECT source, source_record_id, outcome, reason, job_id FROM relevance_scores "
                "WHERE run_id = ? ORDER BY source, source_record_id", (run_id,),
            ).fetchall()]
            actual = {(str(score["source"]), str(score["source_record_id"])) for score in scores}
            if not scores:
                raise ScoringError("Score at least one record before validation.")
            if len(scores) != len(expected) or actual != expected:
                raise ScoringError("The completed score list does not match the frozen selection.")
            extensions = [dict(row) for row in connection.execute(
                "SELECT id, previous_count, added_count, added_manifest_sha256 "
                "FROM relevance_scoring_extensions WHERE run_id = ? ORDER BY rowid", (run_id,),
            ).fetchall()]
            content = _json({
                "schema_version": 1, "run_id": run_id,
                "prompt_artifact_id": run["prompt_artifact_id"],
                "initial_manifest_sha256": run["manifest_sha256"],
                "seed": run["seed"], "algorithm_version": run["algorithm_version"],
                "parallel_batches": int(run["parallel_batches"]),
                "extensions": extensions, "scores": scores,
                "planned_count": run["selected_count"], "scored_count": len(scores),
                "unscored_selected_count": int(run["selected_count"]) - len(scores),
            })
            digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
            created_at = _now()
            connection.execute(
                "INSERT INTO relevance_scoring_confirmations "
                "(run_id, project_id, content_json, content_sha256, scored_count, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, project_id, content, digest, len(scores), created_at),
            )
        return {"run_id": run_id, "scored_count": len(scores),
                "content_sha256": digest, "confirmed_at": created_at}

    @staticmethod
    def _filter_pool(
        connection: sqlite3.Connection, run_id: str, project_id: str,
    ) -> tuple[sqlite3.Row, list[dict[str, object]], dict[str, int]]:
        confirmation = connection.execute(
            "SELECT * FROM relevance_scoring_confirmations WHERE run_id = ? AND project_id = ?",
            (run_id, project_id),
        ).fetchone()
        if confirmation is None:
            raise ScoringError("Validate scoring before selecting records for further work.")
        scores = cast(list[dict[str, object]], json.loads(confirmation["content_json"])["scores"])
        counts = dict.fromkeys([str(score) for score in range(6)] + ["not_assessable"], 0)
        for score in scores:
            counts[str(score["outcome"])] += 1
        return confirmation, scores, counts

    @staticmethod
    def _saved_filter(connection: sqlite3.Connection, run_id: str) -> dict[str, object] | None:
        row = connection.execute(
            "SELECT * FROM relevance_score_filters WHERE run_id = ?", (run_id,),
        ).fetchone()
        if row is None:
            return None
        content = json.loads(row["content_json"])
        return {key: content[key] for key in (
            "minimum_score", "include_not_assessable", "included_count", "excluded_count",
        )} | {"validated_at": row["created_at"], "content_sha256": row["content_sha256"]}

    def filter_state(self, run_id: str, project_id: str) -> dict[str, object]:
        with self._connect() as connection:
            confirmation, scores, counts = self._filter_pool(connection, run_id, project_id)
            return {
                "run_id": run_id, "scored_count": len(scores), "counts": counts,
                "confirmation_sha256": confirmation["content_sha256"],
                "selection": self._saved_filter(connection, run_id),
            }

    def validate_filter(
        self, run_id: str, project_id: str, minimum_score: int,
        include_not_assessable: bool, expected_confirmation_sha256: str,
    ) -> dict[str, object]:
        """Persist criteria and exact included identities against the validated pool."""
        if type(minimum_score) is not int or not 0 <= minimum_score <= 5:
            raise ScoringError("Choose a minimum relevance score from 0 to 5.")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            confirmation, scores, counts = self._filter_pool(connection, run_id, project_id)
            if confirmation["content_sha256"] != expected_confirmation_sha256:
                raise ScoringError("The validated scoring pool changed. Reload before continuing.")
            if self._saved_filter(connection, run_id) is not None:
                raise ScoringError("The score filter has already been validated and is locked.")
            if _has_downstream_work(connection, project_id):
                raise ScoringError("Later work exists; change the score filter in a fork instead.")
            included = [
                {"source": score["source"], "source_record_id": score["source_record_id"]}
                for score in scores
                if (include_not_assessable if score["outcome"] == "not_assessable"
                    else int(str(score["outcome"])) >= minimum_score)
            ]
            if not included:
                raise ScoringError("Include at least one scored record before validating the filter.")
            content = _json({
                "schema_version": 1, "run_id": run_id,
                "scoring_confirmation_sha256": confirmation["content_sha256"],
                "minimum_score": minimum_score, "include_not_assessable": include_not_assessable,
                "counts_by_score": counts, "included_records": included,
                "included_count": len(included), "excluded_count": len(scores) - len(included),
            })
            connection.execute(
                "INSERT INTO relevance_score_filters "
                "(run_id, project_id, content_json, content_sha256, created_at) VALUES (?, ?, ?, ?, ?)",
                (run_id, project_id, content,
                 hashlib.sha256(content.encode("utf-8")).hexdigest(), _now()),
            )
            saved = self._saved_filter(connection, run_id)
            assert saved is not None
            return saved

    def progress(self, project_id: str) -> list[dict[str, object]]:
        with self._connect() as connection:
            runs = connection.execute(
                "SELECT id, retrieval_job_id, batch_sizes_json, next_batch_index, "
                "estimated_input_tokens, estimated_output_tokens, provider, model, seed, "
                "status, stop_requested, parallel_batches, selected_count, retrieved_record_count "
                "FROM relevance_scoring_runs WHERE project_id = ? ORDER BY created_at DESC",
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
                    "(SELECT json_extract(record.value, '$.title') FROM jobs batch_job, "
                    "json_each(batch_job.workflow_input_snapshot_json, '$.records') record "
                    "WHERE batch_job.id = sample.job_id "
                    "AND json_extract(record.value, '$.source') = sample.source "
                    "AND json_extract(record.value, '$.source_record_id') = sample.source_record_id "
                    "LIMIT 1) AS title "
                    "FROM (SELECT outcome, source, source_record_id, job_id, "
                    "ROW_NUMBER() OVER (PARTITION BY outcome ORDER BY rowid) AS sample_rank "
                    "FROM relevance_scores WHERE run_id = ?) sample "
                    "WHERE sample.sample_rank <= 6 ORDER BY sample.outcome, sample.sample_rank",
                    (run["id"],),
                ).fetchall()
                for sample in sample_rows:
                    item = by_score[str(sample["outcome"])]
                    cast(list[dict[str, str]], item.setdefault("samples", [])).append({
                        "source": str(sample["source"]),
                        "source_record_id": str(sample["source_record_id"]),
                        "title": str(sample["title"] or "Untitled record"),
                    })
                jobs = connection.execute(
                    "SELECT jobs.id, jobs.status, links.batch_index, jobs.error, "
                    "json_extract(jobs.workflow_input_snapshot_json, '$.automatic_retry_attempt') "
                    "AS retry_attempt, calls.total_tokens, "
                    "calls.estimated_cost, calls.input_tokens, calls.output_tokens FROM relevance_scoring_batch_jobs links "
                    "JOIN jobs ON jobs.id = links.job_id LEFT JOIN llm_calls calls ON calls.job_id = jobs.id "
                    "WHERE links.run_id = ? ORDER BY links.batch_index, jobs.rowid", (run["id"],),
                ).fetchall()
                completed_indices = {int(job["batch_index"]) for job in jobs
                                     if job["status"] == "completed"}
                completed = len(completed_indices)
                latest_by_batch = {int(job["batch_index"]): job for job in jobs}
                pause_error = next((job["error"] for index, job in latest_by_batch.items()
                                    if index not in completed_indices and job["status"] == "failed"
                                    and int(job["retry_attempt"] or 0) >= 1), None)
                remaining_records = sum(size for index, size in enumerate(batch_sizes)
                                        if index not in completed_indices)
                actual_input = sum(int(job["input_tokens"] or 0) for job in jobs if job["status"] == "completed")
                actual_output = sum(int(job["output_tokens"] or 0) for job in jobs if job["status"] == "completed")
                completed_records = sum(batch_sizes[index] for index in completed_indices)
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
                total_available = int(run["retrieved_record_count"])
                confirmation = connection.execute(
                    "SELECT created_at, content_sha256 FROM relevance_scoring_confirmations "
                    "WHERE run_id = ?", (run["id"],),
                ).fetchone()
                result.append({
                    "id": run["id"], "status": run["status"], "stop_requested": bool(run["stop_requested"]),
                    "provider": run["provider"], "model": run["model"], "seed": run["seed"],
                    "parallel_batches": int(run["parallel_batches"]),
                    "pause_error": pause_error if run["stop_requested"] else None,
                    "active_batch_indices": [int(job["batch_index"]) for job in jobs
                                             if job["status"] == "awaiting_response"],
                    "selected_count": int(run["selected_count"]),
                    "scored_count": sum(cast(int, value["count"]) for value in by_score.values()),
                    "available_unscored": max(0, int(total_available) - int(run["selected_count"])),
                    "confirmed_at": confirmation["created_at"] if confirmation else None,
                    "confirmed_sha256": confirmation["content_sha256"] if confirmation else None,
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
