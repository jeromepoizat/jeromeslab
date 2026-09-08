"""Add the first persistent job, LLM-call, and artifact records.

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create durable execution and provenance storage."""
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("started_at", sa.String(32), nullable=True),
        sa.Column("completed_at", sa.String(32), nullable=True),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("model", sa.String(255), nullable=False),
        sa.Column("scientific_question_snapshot", sa.Text(), nullable=False),
        sa.Column("prompt_snapshot", sa.Text(), nullable=False),
        sa.Column("prompt_template_id", sa.String(128), nullable=False),
        sa.Column("prompt_template_version", sa.String(32), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'awaiting_response', 'completed', 'failed', 'cancelled')",
            name="ck_jobs_status",
        ),
    )
    op.create_index("ix_jobs_queue", "jobs", ["status", "created_at"])
    op.create_index("ix_jobs_project", "jobs", ["project_id", "created_at"])

    op.create_table(
        "llm_calls",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id"), nullable=False, unique=True),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("model", sa.String(255), nullable=False),
        sa.Column("reported_model", sa.String(255), nullable=True),
        sa.Column("operation", sa.String(64), nullable=False),
        sa.Column("purpose", sa.String(128), nullable=False),
        sa.Column("prompt_template_id", sa.String(128), nullable=False),
        sa.Column("prompt_template_version", sa.String(32), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("input_content", sa.Text(), nullable=False),
        sa.Column("request_json", sa.Text(), nullable=False),
        sa.Column("raw_response", sa.Text(), nullable=True),
        sa.Column("parsed_output_json", sa.Text(), nullable=True),
        sa.Column("provider_request_id", sa.String(255), nullable=True),
        sa.Column("started_at", sa.String(32), nullable=False),
        sa.Column("completed_at", sa.String(32), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("usage_json", sa.Text(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("cached_input_tokens", sa.Integer(), nullable=True),
        sa.Column("reasoning_tokens", sa.Integer(), nullable=True),
        sa.Column("provider_metadata_json", sa.Text(), nullable=True),
        sa.Column("generation_settings_json", sa.Text(), nullable=False),
        sa.Column("pricing_snapshot_json", sa.Text(), nullable=True),
        sa.Column("estimated_cost", sa.String(64), nullable=True),
        sa.Column("provider_reported_cost", sa.String(64), nullable=True),
        sa.Column("currency", sa.String(16), nullable=True),
        sa.Column("cost_status", sa.String(32), nullable=False),
        sa.CheckConstraint(
            "status IN ('started', 'completed', 'failed')", name="ck_llm_calls_status"
        ),
        sa.CheckConstraint(
            "cost_status IN ('unavailable', 'estimated', 'reported')",
            name="ck_llm_calls_cost_status",
        ),
    )

    op.create_table(
        "artifact_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("llm_call_id", sa.String(36), sa.ForeignKey("llm_calls.id"), nullable=False),
        sa.Column("kind", sa.String(128), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=False),
        sa.Column("content_json", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("creator_type", sa.String(32), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.UniqueConstraint(
            "job_id", "kind", "version_number", name="uq_artifact_job_kind_version"
        ),
    )


def downgrade() -> None:
    """Remove first-step execution storage."""
    op.drop_table("artifact_versions")
    op.drop_table("llm_calls")
    op.drop_index("ix_jobs_project", table_name="jobs")
    op.drop_index("ix_jobs_queue", table_name="jobs")
    op.drop_table("jobs")
