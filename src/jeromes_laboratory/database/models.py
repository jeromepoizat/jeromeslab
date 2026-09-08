"""SQLAlchemy metadata for the local application database."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all application tables."""


class ApplicationMetadata(Base):
    """Small schema-owned values reserved for application-level metadata."""

    __tablename__ = "application_metadata"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class Project(Base):
    """The durable root record for one scientific research project."""

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tag: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    scientific_question: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)
    question_detailing_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    question_detailing_prompt_version: Mapped[str] = mapped_column(String(32), nullable=False)


class Job(Base):
    """Persistent sequential work with immutable enqueue-time inputs."""

    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'awaiting_response', 'completed', 'failed', 'cancelled')",
            name="ck_jobs_status",
        ),
        Index("ix_jobs_queue", "status", "created_at"),
        Index("ix_jobs_project", "project_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[str | None] = mapped_column(String(32))
    completed_at: Mapped[str | None] = mapped_column(String(32))
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    scientific_question_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_template_id: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_template_version: Mapped[str] = mapped_column(String(32), nullable=False)
    error: Mapped[str | None] = mapped_column(Text)


class LLMCall(Base):
    """Secret-free provenance for one provider API attempt."""

    __tablename__ = "llm_calls"
    __table_args__ = (
        CheckConstraint("status IN ('started', 'completed', 'failed')", name="ck_llm_calls_status"),
        CheckConstraint(
            "cost_status IN ('unavailable', 'estimated', 'reported')",
            name="ck_llm_calls_cost_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), nullable=False, unique=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    reported_model: Mapped[str | None] = mapped_column(String(255))
    operation: Mapped[str] = mapped_column(String(64), nullable=False)
    purpose: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_template_id: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_template_version: Mapped[str] = mapped_column(String(32), nullable=False)
    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    input_content: Mapped[str] = mapped_column(Text, nullable=False)
    request_json: Mapped[str] = mapped_column(Text, nullable=False)
    raw_response: Mapped[str | None] = mapped_column(Text)
    parsed_output_json: Mapped[str | None] = mapped_column(Text)
    provider_request_id: Mapped[str | None] = mapped_column(String(255))
    started_at: Mapped[str] = mapped_column(String(32), nullable=False)
    completed_at: Mapped[str | None] = mapped_column(String(32))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    usage_json: Mapped[str | None] = mapped_column(Text)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    total_tokens: Mapped[int | None] = mapped_column(Integer)
    cached_input_tokens: Mapped[int | None] = mapped_column(Integer)
    reasoning_tokens: Mapped[int | None] = mapped_column(Integer)
    provider_metadata_json: Mapped[str | None] = mapped_column(Text)
    generation_settings_json: Mapped[str] = mapped_column(Text, nullable=False)
    pricing_snapshot_json: Mapped[str | None] = mapped_column(Text)
    estimated_cost: Mapped[str | None] = mapped_column(String(64))
    provider_reported_cost: Mapped[str | None] = mapped_column(String(64))
    currency: Mapped[str | None] = mapped_column(String(16))
    cost_status: Mapped[str] = mapped_column(String(32), nullable=False)


class ArtifactVersion(Base):
    """One immutable content representation emitted by a workflow job."""

    __tablename__ = "artifact_versions"
    __table_args__ = (
        UniqueConstraint("job_id", "kind", "version_number", name="uq_artifact_job_kind_version"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), nullable=False)
    llm_call_id: Mapped[str] = mapped_column(ForeignKey("llm_calls.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(128), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    content_json: Mapped[str] = mapped_column(Text, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    creator_type: Mapped[str] = mapped_column(String(32), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)


class ArtifactEffectiveVersion(Base):
    """The explicitly selected version consumed by later workflow steps."""

    __tablename__ = "artifact_effective_versions"

    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), primary_key=True)
    artifact_version_id: Mapped[str] = mapped_column(
        ForeignKey("artifact_versions.id"), nullable=False
    )
    selected_at: Mapped[str] = mapped_column(String(32), nullable=False)
    selection_reason: Mapped[str] = mapped_column(String(64), nullable=False)
