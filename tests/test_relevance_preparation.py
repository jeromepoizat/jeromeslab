"""Relevance preparation is distinct-source, repeatable, and a pilot only."""

import json
import sqlite3
from pathlib import Path
from typing import cast

import httpx
import pytest
from test_jobs import MemoryCredentialStore
from test_scope_clarification import ScopeGateway
from test_source_retrieval import FakeEuropePMCClient, _approved_query_job

from jeromes_laboratory.api.main import create_app
from jeromes_laboratory.database.jobs import JobError, provider_input_for_job
from jeromes_laboratory.database.relevance import distinct_source_records
from jeromes_laboratory.jobs.worker import JobWorker
from jeromes_laboratory.llm.pricing import estimate_standard_cost
from jeromes_laboratory.llm.settings import LLMSettingsService
from jeromes_laboratory.workflow.relevance import (
    DEFAULT_PROMPT_GENERATION_INSTRUCTIONS,
    DEFAULT_RELEVANCE_SCORING_PROMPT,
    RelevanceError,
    build_preview,
    estimate_scoring_per_1000_tokens,
    parse_calibration,
    parse_prompt_generation,
)


def test_source_identity_is_sampled_once_and_seed_is_repeatable(tmp_path: Path) -> None:
    database_path, repository, retrieval_id, service = _approved_query_job(tmp_path)
    assert JobWorker(
        service, MemoryCredentialStore(), ScopeGateway("unused"),
        europe_pmc_client=FakeEuropePMCClient(),
    ).run_once()
    prepared = build_preview(
        distinct_source_records(database_path, retrieval_id), retrieval_id,
        scoring_limit=10, calibration_count=1,
        seed=123, instructions=DEFAULT_RELEVANCE_SCORING_PROMPT,
    )
    again = build_preview(
        distinct_source_records(database_path, retrieval_id), retrieval_id,
        scoring_limit=10, calibration_count=1,
        seed=123, instructions=DEFAULT_RELEVANCE_SCORING_PROMPT,
    )
    assert prepared == again
    assert prepared["available_distinct_source_records"] == 1
    assert prepared["scoring_limit"] == 1
    assert prepared["selected_manifest"] == [{"source": "MED", "source_record_id": "123"}]
    records = cast(list[dict[str, object]], prepared["calibration_records"])
    assert len(cast(list[object], records[0]["queries"])) == 2
    assert sum(cast(int, row["count"]) for row in cast(list[dict[str, object]], prepared["selected_by_query"])) == 2
    assert repository.get_job(retrieval_id).status == "completed"
    clipped = build_preview(
        distinct_source_records(database_path, retrieval_id), retrieval_id,
        scoring_limit=1, calibration_count=2,
        seed=123, instructions=DEFAULT_RELEVANCE_SCORING_PROMPT,
    )
    assert clipped["calibration_count"] == 1


def test_seeded_sample_covers_query_and_collection_strata(tmp_path: Path) -> None:
    database_path, _, retrieval_id, service = _approved_query_job(tmp_path)
    assert JobWorker(
        service, MemoryCredentialStore(), ScopeGateway("unused"),
        europe_pmc_client=FakeEuropePMCClient(),
    ).run_once()
    with sqlite3.connect(database_path) as connection:
        pages = connection.execute(
            "SELECT pages.id, pages.run_id FROM search_pages pages "
            "JOIN search_runs runs ON runs.id = pages.run_id "
            "WHERE runs.job_id = ? ORDER BY runs.rowid", (retrieval_id,)
        ).fetchall()
        for query_index, (page_id, run_id) in enumerate(pages):
            for source_index, source in enumerate(("MED", "PMC")):
                record_id = f"sample-{query_index}-{source_index}"
                connection.execute(
                    "INSERT INTO publication_source_records "
                    "(id, run_id, page_id, item_index, source, source_record_id, title) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (record_id, run_id, page_id, source_index + 1, source,
                     record_id, f"Peptide study {record_id}"),
                )
    preview = build_preview(
        distinct_source_records(database_path, retrieval_id), retrieval_id,
        scoring_limit=4, calibration_count=4,
        seed=7, instructions=DEFAULT_RELEVANCE_SCORING_PROMPT,
    )
    sampled = cast(list[dict[str, object]], preview["calibration_records"])
    assert len(sampled) == 4
    assert len({(row["source"], row["source_record_id"]) for row in sampled}) == 4
    assert {row["source"] for row in sampled} == {"MED", "PMC"}
    assert len({cast(list[dict[str, str]], row["queries"])[0]["id"] for row in sampled}) == 2


def test_seed_changes_prompt_design_sample_reproducibly() -> None:
    records: list[dict[str, object]] = [
        {"source": "MED", "source_record_id": str(index), "title": f"Study {index}",
         "abstract": "Peptide abstract", "queries": [{"id": "q1", "title": "Peptides"}]}
        for index in range(40)
    ]
    def selected(seed: int) -> list[str]:
        preview = build_preview(
            records, "retrieval", scoring_limit=10, calibration_count=4,
            seed=seed, instructions=DEFAULT_PROMPT_GENERATION_INSTRUCTIONS,
        )
        return [str(record["source_record_id"])
                for record in cast(list[dict[str, object]], preview["calibration_records"])]
    assert selected(123) == selected(123)
    assert selected(123) != selected(456)


def test_preparation_without_run_limit_selects_only_prompt_design_sample() -> None:
    records: list[dict[str, object]] = [
        {"source": "MED", "source_record_id": str(index), "title": f"Study {index}",
         "abstract": "Peptide abstract", "queries": [{"id": "q1", "title": "Peptides"}]}
        for index in range(20)
    ]
    preview = build_preview(
        records, "retrieval", scoring_limit=None, calibration_count=4,
        seed=123, instructions=DEFAULT_PROMPT_GENERATION_INSTRUCTIONS,
    )
    assert preview["scoring_limit"] is None
    assert preview["calibration_count"] == 4
    assert len(cast(list[object], preview["selected_manifest"])) == 4
    assert preview == build_preview(
        records, "retrieval", scoring_limit=None, calibration_count=4,
        seed=123, instructions=DEFAULT_PROMPT_GENERATION_INSTRUCTIONS,
    )
    sample = cast(list[dict[str, object]], preview["calibration_records"])
    short_prompt = estimate_scoring_per_1000_tokens(sample, "Score relevance.")
    longer_prompt = estimate_scoring_per_1000_tokens(sample, "Score relevance. Explain context.")
    assert short_prompt[0] < longer_prompt[0]
    assert short_prompt[1] == longer_prompt[1] == 100_000


def test_calibration_snapshots_manifest_and_rejects_extra_ids(tmp_path: Path) -> None:
    database_path, repository, retrieval_id, service = _approved_query_job(tmp_path)
    assert JobWorker(
        service, MemoryCredentialStore(), ScopeGateway("unused"),
        europe_pmc_client=FakeEuropePMCClient(),
    ).run_once()
    with sqlite3.connect(database_path) as connection:
        project_id = connection.execute(
            "SELECT project_id FROM jobs WHERE id = ?", (retrieval_id,)
        ).fetchone()[0]
    preview = repository.relevance_preparation(
        project_id, retrieval_id, scoring_limit=1, calibration_count=1,
        seed=22, instructions="Score only relevance to the approved charter and plan.",
    )
    with pytest.raises(JobError, match="sample has changed"):
        repository.enqueue_relevance_calibration(
            project_id, retrieval_id, provider="openai", model="gpt-6-luna",
            scoring_limit=1, calibration_count=1, seed=22,
            instructions="Score only relevance to the approved charter and plan.",
            expected_manifest_sha256="0" * 64,
        )
    job = repository.enqueue_relevance_calibration(
        project_id, retrieval_id, provider="openai", model="gpt-6-luna",
        scoring_limit=1, calibration_count=1, seed=22,
        instructions="Score only relevance to the approved charter and plan.",
        expected_manifest_sha256=cast(str, preview["selected_manifest_sha256"]),
    )
    saved = json.loads(job.workflow_input_snapshot_json or "{}")
    assert saved["selected_manifest"] == [{"source": "MED", "source_record_id": "123"}]
    assert saved["approved_strategy"]["strategy_artifact_id"]
    assert "selected_manifest" not in provider_input_for_job(job)
    assert "Myostatin peptide study" in provider_input_for_job(job)
    with pytest.raises(JobError, match="already active"):
        repository.enqueue_relevance_calibration(
            project_id, retrieval_id, provider="openai", model="gpt-6-luna",
            scoring_limit=1, calibration_count=1, seed=22,
            instructions="Score only relevance to the approved charter and plan.",
            expected_manifest_sha256=cast(str, preview["selected_manifest_sha256"]),
        )
    result = {"schema_version": 1, "calibration": [{
        "source": "MED", "source_record_id": "123", "outcome": 4,
        "reason": "Direct peptide evidence relevant to the charter.",
    }]}
    assert JobWorker(
        service, MemoryCredentialStore(), ScopeGateway(json.dumps(result))
    ).run_once()
    assert repository.get_job(job.id).status == "completed"
    assert repository.get_relevance_calibration(job.id) == result
    completed = repository.get_job(job.id)
    assert completed.cost_status == "estimated"
    assert completed.estimated_cost == "8.8e-05"
    with sqlite3.connect(database_path) as connection:
        pricing = connection.execute(
            "SELECT pricing_snapshot_json FROM llm_calls WHERE job_id = ?", (job.id,)
        ).fetchone()[0]
    assert json.loads(pricing)["source_url"].endswith("/gpt-6-luna")
    with pytest.raises(RelevanceError, match="exactly"):
        parse_calibration(json.dumps({"schema_version": 1, "calibration": []}), [("MED", "123")])
    with pytest.raises(RelevanceError, match="Outcome"):
        parse_calibration(json.dumps({"schema_version": 1, "calibration": [{
            "source": "MED", "source_record_id": "123", "outcome": "4", "reason": "No",
        }]}), [("MED", "123")])


def test_pricing_is_exact_model_and_explicitly_unavailable() -> None:
    assert "not_assessable" in DEFAULT_RELEVANCE_SCORING_PROMPT
    assert "Do not judge study quality" in DEFAULT_RELEVANCE_SCORING_PROMPT
    estimate = estimate_standard_cost(
        "openai", "gpt-6-luna", 1_000_000, 1_000_000, aggregate_batches=True
    )
    assert estimate["usd"] == 0.6
    assert estimate["status"] == "estimated"
    cached = estimate_standard_cost("openai", "gpt-6-luna", 1000, 100, 500)
    assert cached["usd"] == 0.000105
    assert estimate_standard_cost("openai", "gpt-6-luna", 272_001, 100)["status"] == "unavailable"
    assert estimate_standard_cost("openai", "gpt-6-luna-unknown", 10, 10)["status"] == "unavailable"
    assert estimate_standard_cost("anthropic", "claude-example", 10, 10)["status"] == "unavailable"
    assert estimate_standard_cost("openai", "gpt-6-sol", 1_000_000, 1_000_000,
                                  aggregate_batches=True)["usd"] == 12.0
    assert estimate_standard_cost("openai", "gpt-6-sol", 10, 10)["captured_on"] == "2026-10-06"


def test_generated_prompt_uses_seeded_sample_and_preserves_edits(tmp_path: Path) -> None:
    database_path, repository, retrieval_id, service = _approved_query_job(tmp_path)
    assert JobWorker(
        service, MemoryCredentialStore(), ScopeGateway("unused"),
        europe_pmc_client=FakeEuropePMCClient(),
    ).run_once()
    with sqlite3.connect(database_path) as connection:
        project_id = connection.execute(
            "SELECT project_id FROM jobs WHERE id = ?", (retrieval_id,)
        ).fetchone()[0]
    starting = DEFAULT_PROMPT_GENERATION_INSTRUCTIONS
    preview = repository.relevance_preparation(
        project_id, retrieval_id, scoring_limit=None, calibration_count=1,
        seed=71, instructions=starting,
    )
    generated_job = repository.enqueue_relevance_prompt_generation(
        project_id, retrieval_id, provider="openai", model="gpt-6-luna",
        scoring_limit=None, calibration_count=1, seed=71, instructions=starting,
        expected_manifest_sha256=cast(str, preview["selected_manifest_sha256"]),
    )
    snapshot = json.loads(generated_job.workflow_input_snapshot_json or "{}")
    assert snapshot["seed"] == 71
    assert snapshot["scoring_limit"] is None
    assert snapshot["calibration_records"] == preview["calibration_records"]
    assert generated_job.prompt_snapshot == starting
    assert "selected_manifest" not in provider_input_for_job(generated_job)
    assert "approved_strategy" in provider_input_for_job(generated_job)
    prompt = (
        "Score title/abstract relevance to the current peptide investigation only. "
        "Use 0 unrelated, 1 remote, 2 tangential, 3 useful, 4 direct, 5 central; "
        "not_assessable means insufficient saved metadata. Do not judge quality."
    )
    output = {"schema_version": 1, "scoring_prompt": prompt,
              "sample_observations": ["The sample includes a peptide title and an abstract."]}
    assert JobWorker(
        service, MemoryCredentialStore(), ScopeGateway(json.dumps(output))
    ).run_once()
    assert repository.get_job(generated_job.id).status == "completed"
    assert repository.get_relevance_prompt_generation(generated_job.id) == output
    edited = prompt + " Negative findings can be relevant."
    job = repository.edit_relevance_prompt_generation(generated_job.id, edited, 1)
    assert job.effective_output_version == 2
    assert job.original_output_markdown == prompt
    assert repository.get_relevance_prompt_generation(generated_job.id) == {
        **output, "scoring_prompt": edited,
    }
    with pytest.raises(JobError, match="edited elsewhere"):
        repository.edit_relevance_prompt_generation(generated_job.id, prompt, 1)
    calibration = repository.enqueue_relevance_calibration(
        project_id, retrieval_id, provider="openai", model="gpt-6-luna",
        scoring_limit=None, calibration_count=1, seed=71, instructions=edited,
        expected_manifest_sha256=cast(str, preview["selected_manifest_sha256"]),
        prompt_generation_job_id=generated_job.id,
    )
    assert calibration.prompt_template_version == "2"
    compact_input = provider_input_for_job(calibration)
    assert edited in compact_input
    assert "approved_strategy" not in compact_input
    assert json.loads(calibration.workflow_input_snapshot_json or "{}")[
        "generated_prompt_source"
    ]["version"] == 2
    with pytest.raises(JobError, match="locked"):
        repository.edit_relevance_prompt_generation(generated_job.id, prompt, 2)
    with pytest.raises(JobError, match="generated prompt or sample changed"):
        repository.enqueue_relevance_calibration(
            project_id, retrieval_id, provider="openai", model="gpt-6-luna",
            scoring_limit=None, calibration_count=1, seed=71, instructions=prompt,
            expected_manifest_sha256=cast(str, preview["selected_manifest_sha256"]),
            prompt_generation_job_id=generated_job.id,
        )


def test_generated_prompt_parser_rejects_missing_rubric() -> None:
    with pytest.raises(RelevanceError, match="0–5"):
        parse_prompt_generation(json.dumps({
            "schema_version": 1,
            "scoring_prompt": "Only include strong candidates." * 8,
            "sample_observations": ["One topic was seen."],
        }))


@pytest.mark.asyncio
async def test_preview_api_is_read_only_and_shows_exact_model_cost(tmp_path: Path) -> None:
    database_path, repository, retrieval_id, service = _approved_query_job(tmp_path)
    assert JobWorker(
        service, MemoryCredentialStore(), ScopeGateway("unused"),
        europe_pmc_client=FakeEuropePMCClient(),
    ).run_once()
    with sqlite3.connect(database_path) as connection:
        project_id = connection.execute(
            "SELECT project_id FROM jobs WHERE id = ?", (retrieval_id,)
        ).fetchone()[0]
    settings = LLMSettingsService(tmp_path / "llm-config")
    settings.cache_models("openai", ["gpt-6-luna"])
    settings.select("openai", "gpt-6-luna")
    app = create_app(
        static_directory=None, workspace_service=service, llm_settings_service=settings,
        credential_store=MemoryCredentialStore(), start_job_worker=False,
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        token = (await client.get("/api/setup")).json()["setup_token"]
        defaults = (await client.get("/api/relevance/defaults")).json()
        assert defaults["relevance_scoring_prompt"] == DEFAULT_RELEVANCE_SCORING_PROMPT
        assert defaults["relevance_prompt_generation_prompt"] == DEFAULT_PROMPT_GENERATION_INSTRUCTIONS
        payload = {
            "retrieval_job_id": retrieval_id, "scoring_limit": 10,
            "calibration_count": 12, "seed": 101,
            "instructions": DEFAULT_RELEVANCE_SCORING_PROMPT,
        }
        denied = await client.post(f"/api/projects/{project_id}/relevance/preview", json=payload)
        assert denied.status_code == 403
        response = await client.post(
            f"/api/projects/{project_id}/relevance/preview", json=payload,
            headers={"X-Jeromes-Lab-Setup-Token": token},
        )
        assert response.status_code == 200, response.text
        preview = response.json()
        assert preview["scoring_limit"] == 1
        assert preview["calibration_count"] == 1
        assert preview["calibration_cost"]["status"] == "estimated"
        assert preview["selected_by_collection"] == [{"source": "MED", "count": 1}]
        assert preview["provider"] == "openai" and preview["model"] == "gpt-6-luna"
        assert preview["per_1000_input_tokens_estimate"] > 0
        assert preview["per_1000_output_tokens_estimate"] == 100_000
        assert [job.kind for job in repository.list_jobs()].count("relevance_calibration") == 0
        generated_request = {**payload,
            "instructions": DEFAULT_PROMPT_GENERATION_INSTRUCTIONS,
        }
        generated_preview_response = await client.post(
            f"/api/projects/{project_id}/relevance/preview", json=generated_request,
            headers={"X-Jeromes-Lab-Setup-Token": token},
        )
        assert generated_preview_response.status_code == 200
        generated_preview = generated_preview_response.json()
        sample_only_request = {key: value for key, value in generated_request.items()
                               if key != "scoring_limit"}
        sample_only_response = await client.post(
            f"/api/projects/{project_id}/relevance/preview", json=sample_only_request,
            headers={"X-Jeromes-Lab-Setup-Token": token},
        )
        assert sample_only_response.status_code == 200
        assert sample_only_response.json()["scoring_limit"] is None
        assert sample_only_response.json()["per_1000_cost"]["status"] == "estimated"
        queued = await client.post(
            f"/api/projects/{project_id}/relevance/prompt-generation/jobs",
            json={**generated_request,
                  "expected_manifest_sha256": generated_preview["selected_manifest_sha256"],
                  "expected_provider": "openai", "expected_model": "gpt-6-luna"},
            headers={"X-Jeromes-Lab-Setup-Token": token},
        )
        assert queued.status_code == 201, queued.text
        prompt_job_id = queued.json()["id"]
        prompt = (
            "Score relevance to the current investigation using saved metadata only: "
            "0 unrelated, 1 remote, 2 tangential, 3 useful, 4 direct, 5 central, "
            "not_assessable when insufficient. Do not score study quality."
        )
        output = {"schema_version": 1, "scoring_prompt": prompt,
                  "sample_observations": ["A sample title mentions the peptide target."]}
        assert JobWorker(
            service, MemoryCredentialStore(), ScopeGateway(json.dumps(output))
        ).run_once()
        got = await client.get(f"/api/jobs/{prompt_job_id}/relevance-prompt-generation")
        assert got.status_code == 200 and got.json() == output
        denied_edit = await client.patch(
            f"/api/jobs/{prompt_job_id}/relevance-prompt-generation",
            json={"scoring_prompt": prompt + " Negative results matter.", "base_version": 1},
        )
        assert denied_edit.status_code == 403
        edited = await client.patch(
            f"/api/jobs/{prompt_job_id}/relevance-prompt-generation",
            json={"scoring_prompt": prompt + " Negative results matter.", "base_version": 1},
            headers={"X-Jeromes-Lab-Setup-Token": token},
        )
        assert edited.status_code == 200, edited.text
        assert edited.json()["effective_output_version"] == 2
