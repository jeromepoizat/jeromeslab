"""Bounded scoring reads, closed SQLite contexts, and idle-worker contention."""

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import cast

import httpx
import pytest
from alembic import command
from alembic.config import Config
from test_jobs import MemoryCredentialStore, configured_workspace
from test_parallel_scoring import StatelessGateway, _parallel_run

from jeromes_laboratory.api.main import create_app
from jeromes_laboratory.database.connections import connect_database
from jeromes_laboratory.database.initialize import MIGRATIONS_DIRECTORY, database_url
from jeromes_laboratory.database.jobs import JobRepository
from jeromes_laboratory.database.scoring import ScoringRepository
from jeromes_laboratory.jobs.worker import JobWorker


def test_database_context_closes_and_rolls_back(tmp_path: Path) -> None:
    path = tmp_path / "contexts.sqlite3"
    with connect_database(path) as connection:
        connection.execute("CREATE TABLE example (value INTEGER)")
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connection.execute("SELECT 1")
    with pytest.raises(RuntimeError), connect_database(path) as failing:
        failing.execute("INSERT INTO example VALUES (1)")
        raise RuntimeError("Test rollback")
    with connect_database(path) as reader:
        assert reader.execute("SELECT COUNT(*) FROM example").fetchone()[0] == 0


def test_idle_claim_never_reserves_writer(tmp_path: Path) -> None:
    _, workspace = configured_workspace(tmp_path)
    statements: list[str] = []

    class TracedJobs(JobRepository):
        def _connect(self) -> sqlite3.Connection:
            connection = super()._connect()
            connection.set_trace_callback(statements.append)
            return connection

    repository = TracedJobs(workspace / "jeromes-laboratory.sqlite3")
    assert repository.claim_next() is None
    assert not any("BEGIN" in statement for statement in statements)


def test_scoring_status_stays_readable_with_eight_idle_executors(tmp_path: Path) -> None:
    scoring, project_id, _, service = _parallel_run(tmp_path)
    worker = JobWorker(service, MemoryCredentialStore(), StatelessGateway())
    assert worker.run_once()
    assert worker.run_once()
    repository = JobRepository(scoring.database_path)

    def poll() -> None:
        for _ in range(20):
            assert repository.claim_next() is None

    with ThreadPoolExecutor(max_workers=8) as pool:
        tasks = [pool.submit(poll) for _ in range(8)]
        for _ in range(20):
            assert scoring.progress(project_id)[0]["scored_count"] == 12
        for task in tasks:
            task.result(timeout=15)


def test_read_model_migration_preserves_original_batch_plan_and_scores(tmp_path: Path) -> None:
    scoring, project_id, run_id, service = _parallel_run(tmp_path)
    worker = JobWorker(service, MemoryCredentialStore(), StatelessGateway())
    assert worker.run_once()
    assert worker.run_once()
    with sqlite3.connect(scoring.database_path) as connection:
        plan, digest = connection.execute(
            "SELECT batches_json, manifest_sha256 FROM relevance_scoring_runs WHERE id = ?",
            (run_id,),
        ).fetchone()
        before = connection.execute(
            "SELECT * FROM relevance_scores WHERE run_id = ? ORDER BY source, source_record_id",
            (run_id,),
        ).fetchall()
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIRECTORY))
    config.set_main_option("sqlalchemy.url", database_url(scoring.database_path))
    command.downgrade(config, "0028")
    command.upgrade(config, "head")
    with sqlite3.connect(scoring.database_path) as connection:
        assert connection.execute(
            "SELECT batches_json, manifest_sha256 FROM relevance_scoring_runs WHERE id = ?",
            (run_id,),
        ).fetchone() == (plan, digest)
        assert connection.execute(
            "SELECT * FROM relevance_scores WHERE run_id = ? ORDER BY source, source_record_id",
            (run_id,),
        ).fetchall() == before
        rows = connection.execute(
            "SELECT records_json FROM relevance_scoring_batch_inputs WHERE run_id = ? "
            "ORDER BY batch_index", (run_id,),
        ).fetchall()
    assert [json.loads(row[0]) for row in rows] == json.loads(plan)
    progress = scoring.progress(project_id)[0]
    assert progress["scored_count"] == 12
    assert cast(int, progress["available_unscored"]) > 0


@pytest.mark.asyncio
async def test_busy_scoring_status_is_retryable_without_silent_loading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _ = configured_workspace(tmp_path)

    def busy(self: ScoringRepository, project_id: str) -> list[dict[str, object]]:
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(ScoringRepository, "progress", busy)
    app = create_app(static_directory=None, workspace_service=service,
                     credential_store=MemoryCredentialStore(), start_job_worker=False)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver",
    ) as client:
        response = await client.get("/api/projects/example/relevance/scoring/runs")
    assert response.status_code == 503
    assert "Retry" in response.json()["detail"]
    assert "have not been changed" in response.json()["detail"]
