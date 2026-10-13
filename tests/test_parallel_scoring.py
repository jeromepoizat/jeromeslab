"""Parallel batches preserve identity, pause boundaries and recovery provenance."""

import json
import threading
import time
from pathlib import Path
from typing import cast

import pytest
from test_jobs import MemoryCredentialStore
from test_relevance_scoring import _ready_scoring

from jeromes_laboratory.database.jobs import JobRepository
from jeromes_laboratory.database.scoring import ScoringError, ScoringRepository
from jeromes_laboratory.jobs.worker import JobWorker
from jeromes_laboratory.llm.generation import (
    GenerationError,
    GenerationResult,
    PreparedGeneration,
    ProviderGenerationGateway,
)
from jeromes_laboratory.storage.workspace import WorkspaceService


def _parallel_run(tmp_path: Path) -> tuple[ScoringRepository, str, str, WorkspaceService]:
    scoring, project_id, retrieval_id, prompt_id, service = _ready_scoring(tmp_path)
    plan = scoring.preview(project_id, retrieval_id, prompt_id, 12, 123)
    run_id = scoring.start(
        project_id, retrieval_id, prompt_id, 12, 123, "openai", "gpt-6-luna",
        cast(str, plan["manifest_sha256"]), cast(str, plan["prompt_artifact_id"]),
        parallel_batches=2,
    )
    return scoring, project_id, run_id, service


class StatelessGateway(ProviderGenerationGateway):
    def execute(self, prepared: PreparedGeneration, api_key: str) -> GenerationResult:
        records = json.loads(str(prepared.request_body["input"]).split("\n\n", 1)[1])["records"]
        output = json.dumps({"schema_version": 2, "scores": {
            record["slot"]: {"outcome": 4, "reason": "Relevant fixture metadata."}
            for record in records
        }})
        return GenerationResult(
            raw_response=output, output_text=output, provider_request_id="fixture",
            reported_model="gpt-6-luna", usage={"input_tokens": 80, "output_tokens": 160},
            input_tokens=80, output_tokens=160, total_tokens=240,
            cached_input_tokens=0, reasoning_tokens=0, provider_metadata={},
        )


@pytest.mark.parametrize("fail_slow", [False, True])
def test_background_parallel_out_of_order_pause_and_validation(
    tmp_path: Path, fail_slow: bool,
) -> None:
    scoring, project_id, run_id, service = _parallel_run(tmp_path)
    release = threading.Event()
    entered = threading.Event()

    class ControlledGateway(StatelessGateway):
        def execute(self, prepared: PreparedGeneration, api_key: str) -> GenerationResult:
            records = json.loads(str(prepared.request_body["input"]).split("\n\n", 1)[1])["records"]
            if len(records) == 10:
                entered.set()
                assert release.wait(15), "The test did not release the slow batch."
                if fail_slow:
                    raise GenerationError("Fixture failure after user pause.")
            return super().execute(prepared, api_key)

    worker = JobWorker(service, MemoryCredentialStore(), ControlledGateway(), poll_interval=.05)
    worker.start()
    try:
        assert entered.wait(10)
        deadline = time.monotonic() + 10
        while scoring.progress(project_id)[0]["scored_count"] != 2 and time.monotonic() < deadline:
            time.sleep(.05)
        progress = scoring.progress(project_id)[0]
        assert progress["scored_count"] == 2  # Batch 1 finishes before batch 0.
        assert progress["completed_batches"] == 1
        assert progress["remaining_batches"] == 1
        assert progress["parallel_batches"] == 2
        assert progress["active_batch_indices"] == [0]
        scoring.pause(run_id, project_id)
        assert scoring.progress(project_id)[0]["status"] == "running"
        with pytest.raises(ScoringError):
            scoring.confirm(run_id, project_id)
        release.set()
        deadline = time.monotonic() + 10
        while scoring.progress(project_id)[0]["status"] != "paused" and time.monotonic() < deadline:
            time.sleep(.05)
        assert scoring.progress(project_id)[0]["status"] == "paused"
        expected = 2 if fail_slow else 12
        assert scoring.confirm(run_id, project_id)["scored_count"] == expected
        assert len(cast(list[object], scoring.progress(project_id)[0]["jobs"])) == 2
        assert scoring.filter_state(run_id, project_id)["scored_count"] == expected
    finally:
        release.set()
        worker.stop()


def test_claim_limit_retry_and_resume_are_idempotent(tmp_path: Path) -> None:
    scoring, project_id, run_id, _ = _parallel_run(tmp_path)
    repository = JobRepository(scoring.database_path)
    first = repository.claim_next()
    second = repository.claim_next()
    assert first and second
    assert repository.claim_next() is None
    repository.fail(first.id, None, "Fixture error")
    assert scoring.progress(project_id)[0]["status"] == "running"
    previous_jobs = len(cast(list[object], scoring.progress(project_id)[0]["jobs"]))
    repository.fail(first.id, None, "Duplicate notification")
    assert repository.get_job(first.id).error == "Fixture error"
    assert len(cast(list[object], scoring.progress(project_id)[0]["jobs"])) == previous_jobs
    retry = repository.claim_next()
    assert retry and retry.id != first.id
    assert json.loads(retry.workflow_input_snapshot_json or "{}")["batch_index"] == 0
    assert repository.claim_next() is None
    repository.fail(retry.id, None, "Second fixture error")
    assert scoring.progress(project_id)[0]["status"] == "running"  # Other request still in flight.
    repository.fail(second.id, None, "Failure while pausing")
    assert scoring.progress(project_id)[0]["status"] == "paused"
    assert scoring.progress(project_id)[0]["pause_error"] == "Second fixture error"
    scoring.resume(run_id, project_id, parallel_batches=1)
    jobs_before = cast(list[object], scoring.progress(project_id)[0]["jobs"])
    scoring.resume(run_id, project_id, parallel_batches=1)
    assert len(cast(list[object], scoring.progress(project_id)[0]["jobs"])) == len(jobs_before)
    assert scoring.progress(project_id)[0]["parallel_batches"] == 1
    assert repository.claim_next()
    assert repository.claim_next() is None


def test_parallel_window_refills_and_counts_each_batch_once(tmp_path: Path) -> None:
    scoring, project_id, retrieval_id, prompt_id, service = _ready_scoring(tmp_path)
    plan = scoring.preview(project_id, retrieval_id, prompt_id, 1, 123)
    run_id = scoring.start(
        project_id, retrieval_id, prompt_id, 1, 123, "openai", "gpt-6-luna",
        cast(str, plan["manifest_sha256"]), cast(str, plan["prompt_artifact_id"]),
    )
    worker = JobWorker(service, MemoryCredentialStore(), StatelessGateway())
    assert worker.run_once()
    # Three new five-record-or-smaller batches, but only two are queued at once.
    assert scoring.extend(run_id, project_id, 12, parallel_batches=2) == 12
    progress = scoring.progress(project_id)[0]
    jobs = cast(list[dict[str, object]], progress["jobs"])
    assert sum(job["status"] == "pending" for job in jobs) == 2
    assert worker.run_once()
    progress = scoring.progress(project_id)[0]
    jobs = cast(list[dict[str, object]], progress["jobs"])
    assert sum(job["status"] == "pending" for job in jobs) == 2
    assert worker.run_once()
    assert worker.run_once()
    # The fixture retrieval contains thirteen records; all are now scored.
    progress = scoring.progress(project_id)[0]
    assert progress["status"] == "completed"
    assert progress["scored_count"] == 13
    assert progress["completed_batches"] == 4
    assert sum(cast(list[int], progress["batch_sizes"])) == 13
    with pytest.raises(ScoringError, match="1–8"):
        scoring.resume(run_id, project_id, parallel_batches=9)


def test_cancel_pending_batch_does_not_fail_other_running_jobs(tmp_path: Path) -> None:
    scoring, project_id, _, _ = _parallel_run(tmp_path)
    repository = JobRepository(scoring.database_path)
    first = repository.claim_next()
    assert first
    jobs = cast(list[dict[str, object]], scoring.progress(project_id)[0]["jobs"])
    repository.cancel(cast(str, jobs[1]["id"]))
    progress = scoring.progress(project_id)[0]
    assert progress["status"] == "running"
    assert progress["stop_requested"] is True
    assert repository.get_job(first.id).status == "awaiting_response"
    assert repository.claim_next() is None


def test_interruption_recovery_and_preparation_failure_do_not_strand_run(tmp_path: Path) -> None:
    scoring, project_id, run_id, service = _parallel_run(tmp_path)
    repository = JobRepository(scoring.database_path)
    assert repository.claim_next()
    repository.fail_interrupted_jobs()
    assert scoring.progress(project_id)[0]["status"] == "paused"
    scoring.resume(run_id, project_id, parallel_batches=1)

    class BrokenPreparation(StatelessGateway):
        def prepare(self, *args: object, **kwargs: object) -> PreparedGeneration:
            raise RuntimeError("Fixture preparation error")

    worker = JobWorker(service, MemoryCredentialStore(), BrokenPreparation())
    assert worker.run_once()
    assert worker.run_once()  # Retry, not a dead worker or an orphaned request.
    assert scoring.progress(project_id)[0]["status"] == "paused"
    scoring.resume(run_id, project_id)
    recovered = JobWorker(service, MemoryCredentialStore(), StatelessGateway())
    assert recovered.run_once()
    assert recovered.run_once()
    assert scoring.progress(project_id)[0]["status"] == "completed"
