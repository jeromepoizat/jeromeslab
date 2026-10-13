"""Relevance selection consumes the validated pool, never changes its scores."""

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import cast

import httpx
import pytest
from test_jobs import MemoryCredentialStore
from test_relevance_scoring import _ready_scoring
from test_scope_clarification import ScopeGateway

from jeromes_laboratory.api.main import create_app
from jeromes_laboratory.database.scoring import ScoringError, ScoringRepository
from jeromes_laboratory.jobs.worker import JobWorker
from jeromes_laboratory.llm.generation import GenerationResult, PreparedGeneration
from jeromes_laboratory.storage.workspace import WorkspaceService


class MixedScoreGateway(ScopeGateway):
    def execute(self, prepared: PreparedGeneration, api_key: str) -> GenerationResult:
        assert self.prepared_input is not None
        records = json.loads(self.prepared_input.split("\n\n", 1)[1])["records"]
        outcomes = [0, 1, 2, 3, 4, 5, "not_assessable"]
        self._output_text = json.dumps({
            "schema_version": 2, "scores": {
                record["slot"]: {"outcome": outcomes[index % 7], "reason": "Fixture relevance."}
                for index, record in enumerate(records)
            },
        })
        return super().execute(prepared, api_key)


def _pool(
    tmp_path: Path, count: int = 7,
) -> tuple[ScoringRepository, str, str, WorkspaceService]:
    scoring, project_id, retrieval_id, prompt_id, service = _ready_scoring(tmp_path)
    plan = scoring.preview(project_id, retrieval_id, prompt_id, count, 123)
    run_id = scoring.start(
        project_id, retrieval_id, prompt_id, count, 123, "openai", "gpt-6-luna",
        cast(str, plan["manifest_sha256"]), cast(str, plan["prompt_artifact_id"]),
    )
    assert JobWorker(service, MemoryCredentialStore(), MixedScoreGateway()).run_once()
    if count > 10:
        scoring.pause(run_id, project_id)
    scoring.confirm(run_id, project_id)
    return scoring, project_id, run_id, service


@pytest.mark.parametrize(("threshold", "include_na", "included"), [
    (0, False, 6), (3, False, 3), (5, True, 2), (0, True, 7),
])
def test_threshold_filter_preserves_exact_pool_and_selection(
    tmp_path: Path, threshold: int, include_na: bool, included: int,
) -> None:
    scoring, project_id, run_id, _ = _pool(tmp_path)
    state = scoring.filter_state(run_id, project_id)
    assert state["scored_count"] == 7
    assert state["counts"] == dict.fromkeys([str(n) for n in range(6)] + ["not_assessable"], 1)
    assert state["selection"] is None
    saved = scoring.validate_filter(
        run_id, project_id, threshold, include_na, cast(str, state["confirmation_sha256"]),
    )
    assert saved["included_count"] == included
    assert saved["excluded_count"] == 7 - included
    assert scoring.filter_state(run_id, project_id)["selection"] == saved
    with sqlite3.connect(scoring.database_path) as connection:
        row = connection.execute(
            "SELECT content_json, content_sha256 FROM relevance_score_filters WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        original = json.loads(connection.execute(
            "SELECT content_json FROM relevance_scoring_confirmations WHERE run_id = ?", (run_id,),
        ).fetchone()[0])
        assert connection.execute(
            "SELECT COUNT(*) FROM relevance_scores WHERE run_id = ?", (run_id,),
        ).fetchone()[0] == 7
    assert hashlib.sha256(row[0].encode()).hexdigest() == row[1]
    content = json.loads(row[0])
    assert content["scoring_confirmation_sha256"] == state["confirmation_sha256"]
    expected = [{"source": score["source"], "source_record_id": score["source_record_id"]}
                for score in original["scores"]
                if (include_na if score["outcome"] == "not_assessable"
                    else int(score["outcome"]) >= threshold)]
    assert content["included_records"] == expected
    with pytest.raises(ScoringError, match="locked"):
        scoring.validate_filter(run_id, project_id, 0, True, cast(str, state["confirmation_sha256"]))


def test_filter_rejects_unvalidated_wrong_project_stale_empty_and_invalid(tmp_path: Path) -> None:
    scoring, project_id, run_id, _ = _pool(tmp_path, count=1)
    with pytest.raises(ScoringError, match="Validate scoring"):
        scoring.filter_state(run_id, "another-project")
    with pytest.raises(ScoringError, match="Validate scoring"):
        scoring.filter_state("missing-run", project_id)
    state = scoring.filter_state(run_id, project_id)
    digest = cast(str, state["confirmation_sha256"])
    with pytest.raises(ScoringError, match="changed"):
        scoring.validate_filter(run_id, project_id, 0, True, "a" * 64)
    with pytest.raises(ScoringError, match="at least one"):
        scoring.validate_filter(run_id, project_id, 5, False, digest)
    with pytest.raises(ScoringError, match="0 to 5"):
        scoring.validate_filter(run_id, project_id, 6, False, digest)
    assert scoring.filter_state(run_id, project_id)["selection"] is None


def test_paused_filter_uses_only_completed_pool(tmp_path: Path) -> None:
    scoring, project_id, run_id, _ = _pool(tmp_path, count=12)
    state = scoring.filter_state(run_id, project_id)
    assert state["scored_count"] == 10
    saved = scoring.validate_filter(run_id, project_id, 0, True,
                                    cast(str, state["confirmation_sha256"]))
    assert saved["included_count"] == 10
    assert saved["excluded_count"] == 0


def test_unvalidated_run_cannot_be_filtered(tmp_path: Path) -> None:
    scoring, project_id, retrieval_id, prompt_id, _ = _ready_scoring(tmp_path)
    plan = scoring.preview(project_id, retrieval_id, prompt_id, 1, 123)
    run_id = scoring.start(
        project_id, retrieval_id, prompt_id, 1, 123, "openai", "gpt-6-luna",
        cast(str, plan["manifest_sha256"]), cast(str, plan["prompt_artifact_id"]),
    )
    with pytest.raises(ScoringError, match="Validate scoring"):
        scoring.filter_state(run_id, project_id)
    with pytest.raises(ScoringError, match="Validate scoring"):
        scoring.validate_filter(run_id, project_id, 0, True, "a" * 64)


@pytest.mark.asyncio
async def test_score_filter_api_security_and_validation(tmp_path: Path) -> None:
    scoring, project_id, run_id, service = _pool(tmp_path)
    app = create_app(static_directory=None, workspace_service=service,
                     credential_store=MemoryCredentialStore(), start_job_worker=False)
    path = f"/api/projects/{project_id}/relevance/scoring/runs/{run_id}/filter"
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver",
    ) as client:
        token = (await client.get("/api/setup")).json()["setup_token"]
        headers = {"X-Jeromes-Lab-Setup-Token": token}
        state = (await client.get(path)).json()
        payload = {"minimum_score": 3, "include_not_assessable": False,
                   "expected_confirmation_sha256": state["confirmation_sha256"]}
        assert (await client.post(path, json=payload)).status_code == 403
        for invalid in (-1, 6, 3.5, True):
            assert (await client.post(path, json={**payload, "minimum_score": invalid},
                                      headers=headers)).status_code == 422
        saved = await client.post(path, json=payload, headers=headers)
        assert saved.status_code == 201, saved.text
        assert saved.json()["included_count"] == 3
        assert (await client.get(path)).json()["selection"] == saved.json()
        assert (await client.post(path, json=payload, headers=headers)).status_code == 409
    assert scoring.progress(project_id)[0]["scored_count"] == 7
