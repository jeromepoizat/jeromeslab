"""Batch scoring is reproducible, resumable, and validates exact identities."""

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, cast

import httpx
import pytest
from test_jobs import MemoryCredentialStore
from test_scope_clarification import ScopeGateway
from test_source_retrieval import FakeEuropePMCClient, _approved_query_job

from jeromes_laboratory.api.main import create_app
from jeromes_laboratory.database.scoring import ScoringError, ScoringRepository
from jeromes_laboratory.jobs.worker import JobWorker
from jeromes_laboratory.llm.generation import GenerationResult, PreparedGeneration
from jeromes_laboratory.llm.settings import LLMSettingsService
from jeromes_laboratory.storage.workspace import WorkspaceService
from jeromes_laboratory.workflow.relevance import (
    DEFAULT_PROMPT_GENERATION_INSTRUCTIONS,
    RelevanceError,
    parse_scoring_batch,
    parse_scoring_batch_slots,
    scoring_slot_schema,
)


class ScoringGateway(ScopeGateway):
    def execute(self, prepared: PreparedGeneration, api_key: str) -> GenerationResult:
        assert self.prepared_input is not None
        records = json.loads(self.prepared_input.split("\n\n", 1)[1])["records"]
        if records[0].get("slot"):
            self._output_text = json.dumps({
                "schema_version": 2,
                "scores": {record["slot"]: {"outcome": 4,
                           "reason": "Directly relevant peptide metadata."}
                           for record in records},
            })
        else:
            self._output_text = json.dumps({
                "schema_version": 1,
                "scores": [{"source": record["source"],
                            "source_record_id": record["source_record_id"],
                            "outcome": 4, "reason": "Directly relevant peptide metadata."}
                           for record in records],
            })
        return super().execute(prepared, api_key)


def _ready_scoring(tmp_path: Path) -> tuple[ScoringRepository, str, str, str, WorkspaceService]:
    database_path, repository, retrieval_id, service = _approved_query_job(tmp_path)
    assert JobWorker(
        service, MemoryCredentialStore(), ScopeGateway("unused"),
        europe_pmc_client=FakeEuropePMCClient(),
    ).run_once()
    with sqlite3.connect(database_path) as connection:
        project_id = str(connection.execute(
            "SELECT project_id FROM jobs WHERE id = ?", (retrieval_id,),
        ).fetchone()[0])
        page_id, run_id = connection.execute(
            "SELECT pages.id, pages.run_id FROM search_pages pages JOIN search_runs runs "
            "ON runs.id = pages.run_id WHERE runs.job_id = ? LIMIT 1", (retrieval_id,),
        ).fetchone()
        for index in range(12):
            source = "PMC" if index % 2 else "MED"
            connection.execute(
                "INSERT INTO publication_source_records "
                "(id, run_id, page_id, item_index, source, source_record_id, title) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (f"extra-{index}", run_id, page_id, index + 1, source,
                 f"extra-{index}", f"Peptide study {index}"),
            )
    preview = repository.relevance_preparation(
        project_id, retrieval_id, scoring_limit=None, calibration_count=2,
        seed=42, instructions=DEFAULT_PROMPT_GENERATION_INSTRUCTIONS,
    )
    prompt_job = repository.enqueue_relevance_prompt_generation(
        project_id, retrieval_id, provider="openai", model="gpt-6-luna",
        scoring_limit=None, calibration_count=2, seed=42,
        instructions=DEFAULT_PROMPT_GENERATION_INSTRUCTIONS,
        expected_manifest_sha256=cast(str, preview["selected_manifest_sha256"]),
    )
    prompt = (
        "Score title and abstract relevance to peptide discovery only. "
        "Use 0 unrelated, 1 remote, 2 tangential, 3 useful, 4 direct, 5 central; "
        "not_assessable means insufficient saved metadata. Do not judge quality."
    )
    output = {"schema_version": 1, "scoring_prompt": prompt,
              "sample_observations": ["The records contain peptide titles."]}
    assert JobWorker(
        service, MemoryCredentialStore(), ScopeGateway(json.dumps(output)),
    ).run_once()
    assert repository.get_job(prompt_job.id).status == "completed"
    return ScoringRepository(database_path), project_id, retrieval_id, prompt_job.id, service


def test_batch_parser_rejects_missing_extra_and_duplicate_ids() -> None:
    expected = [("MED", "1"), ("PMC", "2")]
    base = {"source": "MED", "source_record_id": "1", "outcome": 4,
            "reason": "A relevant peptide record."}
    for scores in ([base], [base, base], [base, {**base, "source": "PMC", "source_record_id": "3"}]):
        with pytest.raises(RelevanceError, match="exactly"):
            parse_scoring_batch(json.dumps({"schema_version": 1, "scores": scores}), expected)
    with pytest.raises(RelevanceError, match="Invalid"):
        parse_scoring_batch(json.dumps({"schema_version": 1, "scores": [{**base, "outcome": 8}]}), [("MED", "1")])


def test_slot_schema_requires_each_record_and_maps_to_frozen_identity() -> None:
    records: list[dict[str, object]] = [
        {"slot": "r1", "source": "MED", "source_record_id": "1"},
        {"slot": "r2", "source": "PAT", "source_record_id": "2"},
    ]
    schema = scoring_slot_schema(records)
    assert schema["required"] == ["schema_version", "scores"]
    scores_schema = cast(dict[str, Any], cast(dict[str, Any], schema["properties"])["scores"])
    assert scores_schema["required"] == ["r1", "r2"]
    assert scores_schema["additionalProperties"] is False
    assert scores_schema["properties"]["r1"]["required"] == ["outcome", "reason"]
    output: dict[str, Any] = {"schema_version": 2, "scores": {
        "r1": {"outcome": 0, "reason": "Unrelated metadata."},
        "r2": {"outcome": "not_assessable", "reason": "Insufficient metadata."},
    }}
    parsed = parse_scoring_batch_slots(json.dumps(output), records)
    assert cast(list[dict[str, object]], parsed["scores"]) == [
        {"source": "MED", "source_record_id": "1", **output["scores"]["r1"]},
        {"source": "PAT", "source_record_id": "2", **output["scores"]["r2"]},
    ]
    for scores in ({"r1": output["scores"]["r1"]},
                   {**output["scores"], "r3": output["scores"]["r1"]}):
        with pytest.raises(RelevanceError, match="record slots"):
            parse_scoring_batch_slots(json.dumps({"schema_version": 2, "scores": scores}), records)


def test_bounded_run_pauses_resumes_and_preserves_scores(tmp_path: Path) -> None:
    scoring, project_id, retrieval_id, prompt_job_id, service = _ready_scoring(tmp_path)
    plan = scoring.preview(project_id, retrieval_id, prompt_job_id, 12, 123)
    assert plan == scoring.preview(project_id, retrieval_id, prompt_job_id, 12, 123)
    assert plan["selected_count"] == 12
    assert plan["batch_sizes"] == [10, 2]
    run_id = scoring.start(
        project_id, retrieval_id, prompt_job_id, 12, 123, "openai", "gpt-6-luna",
        cast(str, plan["manifest_sha256"]), cast(str, plan["prompt_artifact_id"]),
    )
    with sqlite3.connect(scoring.database_path) as connection:
        first_snapshot = json.loads(connection.execute(
            "SELECT jobs.workflow_input_snapshot_json FROM relevance_scoring_batch_jobs links "
            "JOIN jobs ON jobs.id = links.job_id WHERE links.run_id = ? AND links.batch_index = 0",
            (run_id,),
        ).fetchone()[0])
    assert first_snapshot["schema_version"] == 2
    assert [record["slot"] for record in first_snapshot["records"]] == [
        f"r{index}" for index in range(1, 11)
    ]
    worker = JobWorker(service, MemoryCredentialStore(), ScoringGateway())
    assert worker.run_once()
    with sqlite3.connect(scoring.database_path) as connection:
        request = json.loads(connection.execute(
            "SELECT calls.request_json FROM llm_calls calls "
            "JOIN relevance_scoring_batch_jobs links ON links.job_id = calls.job_id "
            "WHERE links.run_id = ? AND links.batch_index = 0", (run_id,),
        ).fetchone()[0])
    assert request["text"]["format"]["strict"] is True
    assert request["text"]["format"]["schema"]["properties"]["scores"]["required"] == [
        f"r{index}" for index in range(1, 11)
    ]
    progress = scoring.progress(project_id)[0]
    assert progress["scored_count"] == 10
    assert progress["completed_batches"] == 1
    by_score = cast(dict[str, dict[str, object]], progress["by_score"])
    samples = cast(list[dict[str, str]], by_score["4"]["samples"])
    assert len(samples) == 6
    assert all(sample["title"] for sample in samples)
    with pytest.raises(ScoringError, match="already has a scoring run"):
        scoring.preview(project_id, retrieval_id, prompt_job_id, 1, 123)
    scoring.pause(run_id, project_id)
    assert scoring.progress(project_id)[0]["status"] == "paused"
    assert not worker.run_once()
    scoring.resume(run_id, project_id)
    assert worker.run_once()
    progress = scoring.progress(project_id)[0]
    assert progress["status"] == "completed"
    assert progress["scored_count"] == 12
    assert progress["remaining_batches"] == 0
    by_score = cast(dict[str, dict[str, object]], progress["by_score"])
    assert by_score["4"]["count"] == 12
    assert sum(cast(dict[str, int], by_score["4"]["sources"]).values()) == 12
    with pytest.raises(ScoringError, match="already has a scoring run"):
        scoring.preview(project_id, retrieval_id, prompt_job_id, 100, 123)


def test_invalid_batch_retries_once_then_pauses_with_preserved_history(tmp_path: Path) -> None:
    scoring, project_id, retrieval_id, prompt_job_id, service = _ready_scoring(tmp_path)
    plan = scoring.preview(project_id, retrieval_id, prompt_job_id, 1, 25)
    run_id = scoring.start(
        project_id, retrieval_id, prompt_job_id, 1, 25, "openai", "gpt-6-luna",
        cast(str, plan["manifest_sha256"]), cast(str, plan["prompt_artifact_id"]),
    )
    # A run created before this change has a version-1 failed attempt. Resume
    # must retain that attempt while enqueuing a new version-2 slot request.
    with sqlite3.connect(scoring.database_path) as connection:
        old = connection.execute(
            "SELECT jobs.id, jobs.workflow_input_snapshot_json FROM relevance_scoring_batch_jobs links "
            "JOIN jobs ON jobs.id = links.job_id WHERE links.run_id = ?", (run_id,),
        ).fetchone()
        old_snapshot = json.loads(old[1])
        old_snapshot["schema_version"] = 1
        old_snapshot["records"] = [
            {key: value for key, value in record.items() if key != "slot"}
            for record in old_snapshot["records"]
        ]
        connection.execute(
            "UPDATE jobs SET workflow_input_snapshot_json = ?, prompt_template_version = '1' "
            "WHERE id = ?", (json.dumps(old_snapshot), old[0]),
        )
    failed_worker = JobWorker(
        service, MemoryCredentialStore(), ScopeGateway(json.dumps({
            "schema_version": 1, "scores": [],
        })),
    )
    assert failed_worker.run_once()
    failed = scoring.progress(project_id)[0]
    assert failed["status"] == "running"
    assert failed["scored_count"] == 0
    with sqlite3.connect(scoring.database_path) as connection:
        call = connection.execute(
            "SELECT status, total_tokens, cost_status, raw_response FROM llm_calls "
            "WHERE job_id = ?", (cast(list[dict[str, object]], failed["jobs"])[0]["id"],),
        ).fetchone()
    assert call[0:3] == ("failed", 240, "estimated")
    assert json.loads(json.loads(call[3])["output"])["scores"] == []
    assert failed_worker.run_once()
    assert scoring.progress(project_id)[0]["status"] == "paused"
    assert not failed_worker.run_once()
    with pytest.raises(ScoringError, match="at least one"):
        scoring.confirm(run_id, project_id)
    scoring.resume(run_id, project_id)
    assert JobWorker(service, MemoryCredentialStore(), ScoringGateway()).run_once()
    completed = scoring.progress(project_id)[0]
    assert completed["status"] == "completed"
    assert completed["scored_count"] == 1
    assert [job["status"] for job in cast(list[dict[str, object]], completed["jobs"])] == [
        "failed", "failed", "completed",
    ]
    with sqlite3.connect(scoring.database_path) as connection:
        versions = connection.execute(
            "SELECT jobs.prompt_template_version, jobs.workflow_input_snapshot_json "
            "FROM relevance_scoring_batch_jobs links JOIN jobs ON jobs.id = links.job_id "
            "WHERE links.run_id = ? ORDER BY jobs.created_at", (run_id,),
        ).fetchall()
        retry_counts = connection.execute(
            "SELECT calls.retry_count FROM llm_calls calls JOIN jobs ON jobs.id = calls.job_id "
            "JOIN relevance_scoring_batch_jobs links ON links.job_id = jobs.id "
            "WHERE links.run_id = ? ORDER BY jobs.rowid", (run_id,),
        ).fetchall()
    assert [version for version, _ in versions] == ["1", "2", "2"]
    assert [json.loads(snapshot)["schema_version"] for _, snapshot in versions] == [1, 2, 2]
    assert [row[0] for row in retry_counts] == [0, 1, 0]
    assert json.loads(versions[1][1])["retry_of_job_id"] == old[0]


def test_pause_requested_during_call_stops_before_next_batch(tmp_path: Path) -> None:
    scoring, project_id, retrieval_id, prompt_job_id, service = _ready_scoring(tmp_path)
    plan = scoring.preview(project_id, retrieval_id, prompt_job_id, 12, 123)
    run_id = scoring.start(
        project_id, retrieval_id, prompt_job_id, 12, 123, "openai", "gpt-6-luna",
        cast(str, plan["manifest_sha256"]), cast(str, plan["prompt_artifact_id"]),
    )

    class PauseDuringCall(ScoringGateway):
        def execute(self, prepared: PreparedGeneration, api_key: str) -> GenerationResult:
            scoring.pause(run_id, project_id)
            return super().execute(prepared, api_key)

    worker = JobWorker(service, MemoryCredentialStore(), PauseDuringCall())
    assert worker.run_once()
    paused = scoring.progress(project_id)[0]
    assert paused["status"] == "paused"
    assert paused["scored_count"] == 10
    assert len(cast(list[object], paused["jobs"])) == 1
    assert not worker.run_once()
    confirmation = scoring.confirm(run_id, project_id)
    assert confirmation["scored_count"] == 10
    with sqlite3.connect(scoring.database_path) as connection:
        content = json.loads(connection.execute(
            "SELECT content_json FROM relevance_scoring_confirmations WHERE run_id = ?",
            (run_id,),
        ).fetchone()[0])
    assert content["planned_count"] == 12
    assert content["unscored_selected_count"] == 2
    assert len(content["scores"]) == 10
    with pytest.raises(ScoringError, match="locked"):
        scoring.resume(run_id, project_id)
    assert not worker.run_once()


def test_retry_success_continues_and_user_pause_suppresses_retry(tmp_path: Path) -> None:
    scoring, project_id, retrieval_id, prompt_job_id, service = _ready_scoring(tmp_path)
    plan = scoring.preview(project_id, retrieval_id, prompt_job_id, 12, 123)
    run_id = scoring.start(
        project_id, retrieval_id, prompt_job_id, 12, 123, "openai", "gpt-6-luna",
        cast(str, plan["manifest_sha256"]), cast(str, plan["prompt_artifact_id"]),
    )
    failed_worker = JobWorker(
        service, MemoryCredentialStore(), ScopeGateway('{"schema_version":1,"scores":[]}'),
    )
    assert failed_worker.run_once()
    assert scoring.progress(project_id)[0]["status"] == "running"
    assert JobWorker(service, MemoryCredentialStore(), ScoringGateway()).run_once()
    assert scoring.progress(project_id)[0]["scored_count"] == 10

    class PauseAndFail(ScopeGateway):
        def execute(self, prepared: PreparedGeneration, api_key: str) -> GenerationResult:
            scoring.pause(run_id, project_id)
            with pytest.raises(ScoringError, match="pause scoring"):
                scoring.confirm(run_id, project_id)
            return super().execute(prepared, api_key)

    paused_worker = JobWorker(
        service, MemoryCredentialStore(), PauseAndFail('{"schema_version":1,"scores":[]}'),
    )
    assert paused_worker.run_once()
    paused = scoring.progress(project_id)[0]
    assert paused["status"] == "paused"
    assert paused["scored_count"] == 10
    assert len(cast(list[object], paused["jobs"])) == 3
    assert not paused_worker.run_once()
    assert scoring.confirm(run_id, project_id)["scored_count"] == 10


def test_completed_run_extends_same_seed_then_confirms_exact_scores(tmp_path: Path) -> None:
    scoring, project_id, retrieval_id, prompt_job_id, service = _ready_scoring(tmp_path)
    plan = scoring.preview(project_id, retrieval_id, prompt_job_id, 2, 123)
    run_id = scoring.start(
        project_id, retrieval_id, prompt_job_id, 2, 123, "openai", "gpt-6-luna",
        cast(str, plan["manifest_sha256"]), cast(str, plan["prompt_artifact_id"]),
    )
    worker = JobWorker(service, MemoryCredentialStore(), ScoringGateway())
    assert worker.run_once()
    before = scoring.progress(project_id)[0]
    assert before["status"] == "completed"
    assert before["scored_count"] == 2
    assert cast(int, before["available_unscored"]) > 0
    old_job_ids = [job["id"] for job in cast(list[dict[str, object]], before["jobs"])]
    with pytest.raises(ScoringError, match="Only"):
        scoring.extend(run_id, project_id, cast(int, before["available_unscored"]) + 1)
    assert scoring.extend(run_id, project_id, 3) == 3
    during = scoring.progress(project_id)[0]
    assert during["status"] == "running"
    assert during["seed"] == 123
    assert during["selected_count"] == 5
    assert during["scored_count"] == 2
    assert during["batch_sizes"] == [2, 3]
    assert [job["id"] for job in cast(list[dict[str, object]], during["jobs"])[:1]] == old_job_ids
    with pytest.raises(ScoringError, match="Finish all"):
        scoring.confirm(run_id, project_id)
    assert worker.run_once()
    completed = scoring.progress(project_id)[0]
    assert completed["status"] == "completed"
    assert completed["scored_count"] == 5
    confirmation = scoring.confirm(run_id, project_id)
    assert confirmation["scored_count"] == 5
    assert scoring.progress(project_id)[0]["confirmed_at"] == confirmation["confirmed_at"]
    with sqlite3.connect(scoring.database_path) as connection:
        row = connection.execute(
            "SELECT content_json, content_sha256 FROM relevance_scoring_confirmations "
            "WHERE run_id = ?", (run_id,),
        ).fetchone()
        extension = connection.execute(
            "SELECT previous_count, added_count FROM relevance_scoring_extensions "
            "WHERE run_id = ?", (run_id,),
        ).fetchone()
    assert extension == (2, 3)
    assert len(json.loads(row[0])["scores"]) == 5
    assert row[1] == confirmation["content_sha256"]
    assert row[1] == hashlib.sha256(row[0].encode("utf-8")).hexdigest()
    with pytest.raises(ScoringError, match="locked"):
        scoring.extend(run_id, project_id, 1)
    with pytest.raises(ScoringError, match="already been confirmed"):
        scoring.confirm(run_id, project_id)


@pytest.mark.asyncio
async def test_scoring_api_previews_starts_and_pauses_without_provider_call(tmp_path: Path) -> None:
    scoring, project_id, retrieval_id, prompt_job_id, service = _ready_scoring(tmp_path)
    settings = LLMSettingsService(tmp_path / "llm-config")
    settings.cache_models("openai", ["gpt-6-luna"])
    settings.select("openai", "gpt-6-luna")
    app = create_app(
        static_directory=None, workspace_service=service, llm_settings_service=settings,
        credential_store=MemoryCredentialStore(), start_job_worker=False,
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver",
    ) as client:
        token = (await client.get("/api/setup")).json()["setup_token"]
        path = f"/api/projects/{project_id}/relevance/scoring"
        payload = {"retrieval_job_id": retrieval_id, "prompt_job_id": prompt_job_id,
                   "count": 1, "seed": 77}
        assert (await client.post(f"{path}/preview", json=payload)).status_code == 403
        headers = {"X-Jeromes-Lab-Setup-Token": token}
        response = await client.post(f"{path}/preview", json=payload, headers=headers)
        assert response.status_code == 200, response.text
        preview = response.json()
        assert preview["selected_count"] == 1
        assert preview["batch_sizes"] == [1]
        assert preview["cost"]["status"] == "estimated"
        invalid = await client.post(f"{path}/runs", json={
            **payload, "expected_manifest_sha256": preview["manifest_sha256"],
            "expected_prompt_artifact_id": preview["prompt_artifact_id"],
            "expected_provider": preview["provider"], "expected_model": preview["model"],
            "parallel_batches": 9,
        }, headers=headers)
        assert invalid.status_code == 422
        start = await client.post(f"{path}/runs", json={
            **payload, "expected_manifest_sha256": preview["manifest_sha256"],
            "expected_prompt_artifact_id": preview["prompt_artifact_id"],
            "expected_provider": preview["provider"], "expected_model": preview["model"],
            "parallel_batches": 2,
        }, headers=headers)
        assert start.status_code == 201, start.text
        run_id = start.json()["id"]
        assert (await client.get(f"{path}/runs")).json()[0]["status"] == "running"
        assert (await client.get(f"{path}/runs")).json()[0]["parallel_batches"] == 2
        paused = await client.post(f"{path}/runs/{run_id}/pause", headers=headers)
        assert paused.status_code == 200
        assert scoring.progress(project_id)[0]["status"] == "paused"
        second_start = await client.post(f"{path}/runs", json={
            **payload, "expected_manifest_sha256": preview["manifest_sha256"],
            "expected_prompt_artifact_id": preview["prompt_artifact_id"],
            "expected_provider": preview["provider"], "expected_model": preview["model"],
        }, headers=headers)
        assert second_start.status_code == 422
        assert "already has a scoring run" in second_start.json()["detail"]


@pytest.mark.asyncio
async def test_scoring_api_extends_then_confirms_one_run(tmp_path: Path) -> None:
    scoring, project_id, retrieval_id, prompt_job_id, service = _ready_scoring(tmp_path)
    plan = scoring.preview(project_id, retrieval_id, prompt_job_id, 1, 7)
    run_id = scoring.start(
        project_id, retrieval_id, prompt_job_id, 1, 7, "openai", "gpt-6-luna",
        cast(str, plan["manifest_sha256"]), cast(str, plan["prompt_artifact_id"]),
    )
    worker = JobWorker(service, MemoryCredentialStore(), ScoringGateway())
    assert worker.run_once()
    app = create_app(
        static_directory=None, workspace_service=service,
        credential_store=MemoryCredentialStore(), start_job_worker=False,
    )
    base = f"/api/projects/{project_id}/relevance/scoring/runs/{run_id}"
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver",
    ) as client:
        token = (await client.get("/api/setup")).json()["setup_token"]
        headers = {"X-Jeromes-Lab-Setup-Token": token}
        assert (await client.post(f"{base}/extend", json={"additional_count": 2})).status_code == 403
        extended = await client.post(
            f"{base}/extend", json={"additional_count": 2}, headers=headers,
        )
        assert extended.status_code == 200, extended.text
        assert extended.json()["added_count"] == 2
        assert (await client.post(f"{base}/confirm", headers=headers)).status_code == 409
        assert worker.run_once()
        confirmed = await client.post(f"{base}/confirm", headers=headers)
        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json()["scored_count"] == 3
        runs = (await client.get(f"/api/projects/{project_id}/relevance/scoring/runs")).json()
        assert runs[0]["confirmed_at"]
        assert runs[0]["available_unscored"] > 0
        assert (await client.post(
            f"{base}/extend", json={"additional_count": 1}, headers=headers,
        )).status_code == 409
