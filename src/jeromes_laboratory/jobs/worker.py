"""Durable research execution with bounded parallel batches within one scoring run."""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import replace
from pathlib import Path

from jeromes_laboratory.database.jobs import JobRecord, JobRepository, provider_input_for_job
from jeromes_laboratory.database.materials import MaterialRepository
from jeromes_laboratory.database.retrieval import RetrievalRepository
from jeromes_laboratory.llm.generation import GenerationError, GenerationGateway
from jeromes_laboratory.security.credentials import CredentialStore, CredentialStoreError
from jeromes_laboratory.sources.europe_pmc import (
    EuropePMCClient,
    SourceSearchClient,
    SourceSearchError,
)
from jeromes_laboratory.sources.materials import EuropePMCMaterialClient, MaterialClient
from jeromes_laboratory.storage.workspace import (
    DATABASE_FILE_NAME,
    WorkspaceLocationError,
    WorkspaceService,
)
from jeromes_laboratory.workflow.relevance import scoring_slot_schema


class JobWorker:
    """Poll one workspace queue; only batches of one scoring run may overlap."""

    def __init__(
        self,
        workspace_service: WorkspaceService,
        credential_store: CredentialStore,
        generation_gateway: GenerationGateway,
        *,
        poll_interval: float = 0.5,
        europe_pmc_client: SourceSearchClient | None = None,
        material_client: MaterialClient | None = None,
    ) -> None:
        self._workspace_service = workspace_service
        self._credential_store = credential_store
        self._generation_gateway = generation_gateway
        self._poll_interval = poll_interval
        self._europe_pmc_client = europe_pmc_client or EuropePMCClient()
        self._material_client = material_client or EuropePMCMaterialClient()
        self._stop_event = threading.Event()
        self._threads: list[threading.Thread] = []
        self._recovered_database: Path | None = None
        self._recovery_lock = threading.Lock()

    def start(self) -> None:
        if any(thread.is_alive() for thread in self._threads):
            return
        self._stop_event.clear()
        # Daemon slots preserve bounded app shutdown even if a remote request
        # is still outstanding. Restart marks such requests interrupted.
        self._threads = [threading.Thread(
            target=self._run, name=f"research-batch-{slot}", daemon=True,
        ) for slot in range(8)]
        for thread in self._threads:
            thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        deadline = time.monotonic() + 2
        for thread in self._threads:
            thread.join(timeout=max(0, deadline - time.monotonic()))

    def run_once(self) -> bool:
        repository = self._repository()
        if repository is None:
            return False
        with self._recovery_lock:
            if self._recovered_database != repository.database_path:
                repository.fail_interrupted_jobs()
                self._recovered_database = repository.database_path
        job = repository.claim_next()
        if job is None:
            return False
        try:
            self._execute(repository, job)
        except Exception:  # noqa: BLE001 - preparation/persistence must not kill the worker.
            if repository.get_job(job.id).status == "awaiting_response":
                repository.fail(job.id, None, "An unexpected error stopped job preparation or storage.")
        return True

    def _execute(self, repository: JobRepository, job: JobRecord) -> bool:
        if job.kind == "source_material_collection":
            try:
                MaterialRepository(repository.database_path).run_job(
                    job.id, self._material_client, self._stop_event.is_set,
                )
            except Exception:  # noqa: BLE001 - files and completed attempts remain preserved.
                repository.fail(job.id, None, "Source collection stopped unexpectedly. Resume from saved resources.")
            return True
        if job.kind == "source_retrieval":
            try:
                RetrievalRepository(repository.database_path).run_job(
                    job.id, self._europe_pmc_client
                )
            except SourceSearchError as error:
                repository.fail(job.id, None, str(error))
            except Exception:  # noqa: BLE001 - preserve the durable worker without leaking internals.
                repository.fail(job.id, None, "An unexpected error stopped source retrieval.")
            return True
        if job.provider == "europe_pmc":
            repository.fail(job.id, None, "A source provider cannot execute an LLM job.")
            return True
        input_content = provider_input_for_job(job)
        prepared = self._generation_gateway.prepare(
            job.provider,
            job.model,
            job.prompt_snapshot,
            input_content,
        )
        if job.kind == "relevance_scoring_batch" and job.provider == "openai":
            snapshot = json.loads(job.workflow_input_snapshot_json or "{}")
            if snapshot.get("schema_version") == 2:
                response_format = {
                    "type": "json_schema", "name": "relevance_scoring_batch_v2",
                    "strict": True, "schema": scoring_slot_schema(snapshot["records"]),
                }
                prepared = replace(
                    prepared,
                    request_body={**prepared.request_body, "text": {"format": response_format}},
                    generation_settings={**prepared.generation_settings,
                                         "response_format": "relevance_scoring_batch_v2"},
                )
        call_id = repository.begin_llm_call(job, prepared)
        api_key: str | None = None
        try:
            api_key = self._credential_store.get_api_key(job.provider)
            if api_key is None:
                raise GenerationError("The saved provider API key is no longer available.")
            result = self._generation_gateway.execute(prepared, api_key)
        except (CredentialStoreError, GenerationError) as error:
            raw_response = error.raw_response if isinstance(error, GenerationError) else None
            if api_key is not None and raw_response is not None:
                raw_response = raw_response.replace(api_key, "[REDACTED]")
            repository.fail(job.id, call_id, str(error), raw_response)
        except Exception:  # noqa: BLE001 - keep the durable worker alive and redact unknown errors.
            repository.fail(job.id, call_id, "An unexpected error stopped the provider call.")
        else:
            if api_key in result.raw_response:
                result = replace(
                    result,
                    raw_response=result.raw_response.replace(api_key, "[REDACTED]"),
                )
            try:
                repository.complete(job.id, call_id, result)
            except ValueError as error:
                repository.fail(job.id, call_id, str(error), result.raw_response, result=result)
            except Exception:  # noqa: BLE001 - keep response/usage even if artifact storage fails.
                repository.fail(job.id, call_id, "Could not save the provider output.",
                                result.raw_response, result=result)
        return True

    def _run(self) -> None:
        # SQL claims enforce one logical research operation. Only batches of the
        # same scoring run may overlap, within its persisted concurrency limit.
        while not self._stop_event.is_set():
            try:
                self.run_once()
            except Exception:  # noqa: BLE001 - sanitized; continue after temporary storage errors.
                logging.getLogger(__name__).warning("Research worker encountered a storage error.")
            self._stop_event.wait(self._poll_interval)

    def _repository(self) -> JobRepository | None:
        try:
            availability = self._workspace_service.workspace_availability()
        except WorkspaceLocationError:
            return None
        if availability.kind != "available" or availability.path is None:
            return None
        return JobRepository(availability.path / DATABASE_FILE_NAME)
