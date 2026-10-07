"""Durable bounded relevance scoring runs and exact per-source decisions.

Revision ID: 0025
Revises: 0024
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "relevance_scoring_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("retrieval_job_id", sa.String(36), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("prompt_artifact_id", sa.String(36), sa.ForeignKey("artifact_versions.id"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("model", sa.String(255), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("algorithm_version", sa.String(64), nullable=False),
        sa.Column("manifest_sha256", sa.String(64), nullable=False),
        sa.Column("batches_json", sa.Text(), nullable=False),
        sa.Column("batch_sizes_json", sa.Text(), nullable=False),
        sa.Column("selected_count", sa.Integer(), nullable=False),
        sa.Column("estimated_input_tokens", sa.Integer(), nullable=False),
        sa.Column("estimated_output_tokens", sa.Integer(), nullable=False),
        sa.Column("estimate_method", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("stop_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("next_batch_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("completed_at", sa.String(32)),
    )
    op.create_index("ix_relevance_runs_project", "relevance_scoring_runs", ["project_id", "created_at"])
    op.create_table(
        "relevance_scoring_batch_jobs",
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id"), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("relevance_scoring_runs.id"), nullable=False),
        sa.Column("batch_index", sa.Integer(), nullable=False),
    )
    op.create_index("ix_relevance_batch_run", "relevance_scoring_batch_jobs", ["run_id", "batch_index"])
    op.create_table(
        "relevance_scores",
        sa.Column("run_id", sa.String(36), sa.ForeignKey("relevance_scoring_runs.id"), nullable=False),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("source_record_id", sa.String(255), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("run_id", "source", "source_record_id"),
    )


def downgrade() -> None:
    op.drop_table("relevance_scores")
    op.drop_index("ix_relevance_batch_run", table_name="relevance_scoring_batch_jobs")
    op.drop_table("relevance_scoring_batch_jobs")
    op.drop_index("ix_relevance_runs_project", table_name="relevance_scoring_runs")
    op.drop_table("relevance_scoring_runs")
