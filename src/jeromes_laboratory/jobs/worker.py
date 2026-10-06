"""One sequential background worker for persistent research jobs."""

from __future__ import annotations

import threading
from dataclasses import replace
from pathlib import Path

from jeromes_laboratory.database.jobs import JobRepository, provider_input_for_job
from jeromes_laboratory.database.retrieval import RetrievalRepository
from jeromes_laboratory.llm.generation import GenerationError, GenerationGateway
from jeromes_laboratory.security.credentials import CredentialStore, CredentialStoreError
from jeromes_laboratory.sources.europe_pmc import (
    EuropePMCClient,
    SourceSearchClient,
    SourceSearchError,
)
from jeromes_laboratory.storage.workspace import (
    DATABASE_FILE_NAME,
    WorkspaceLocationError,
    WorkspaceService,
)


class JobWorker:
    """Poll one workspace queue and execute no more than one job at a time."""

    def __init__(
        self,
        workspace_service: WorkspaceService,
        credential_store: CredentialStore,
        generation_gateway: GenerationGateway,
        *,
        poll_interval: float = 0.5,
        europe_pmc_client: SourceSearchClient | None = None,
    ) -> None:
        self._workspace_service = workspace_service
        self._credential_store = credential_store
        self._generation_gateway = generation_gateway
        self._poll_interval = poll_interval
        self._europe_pmc_client = europe_pmc_client or EuropePMCClient()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._recovered_database: Path | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="research-job-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2)

    def run_once(self) -> bool:
        repository = self._repository()
        if repository is None:
            return False
        if self._recovered_database != repository.database_path:
            repository.fail_interrupted_jobs()
            self._recovered_database = repository.database_path
        job = repository.claim_next()
        if job is None:
            return False
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
                repository.fail(job.id, call_id, str(error), result.raw_response)
        return True

    def _run(self) -> None:
        while not self._stop_event.is_set():
            self.run_once()
            self._stop_event.wait(self._poll_interval)

    def _repository(self) -> JobRepository | None:
        try:
            availability = self._workspace_service.workspace_availability()
        except WorkspaceLocationError:
            return None
        if availability.kind != "available" or availability.path is None:
            return None
        return JobRepository(availability.path / DATABASE_FILE_NAME)
