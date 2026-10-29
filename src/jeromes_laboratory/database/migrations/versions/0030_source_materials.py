"""Resumable source acquisition with immutable resource attempts."""

import sqlalchemy as sa
from alembic import op

revision: str = "0030"
down_revision: str | None = "0029"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "source_material_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False, unique=True),
        sa.Column("filter_run_id", sa.String(36), sa.ForeignKey("relevance_score_filters.run_id"), nullable=False),
        sa.Column("selection_sha256", sa.String(64), nullable=False),
        sa.Column("policy_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("stop_requested", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("completed_at", sa.String(32)),
    )
    op.create_table(
        "source_material_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("source_material_runs.id"), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("source_record_id", sa.String(255), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.Column("metadata_sha256", sa.String(64), nullable=False),
        sa.Column("has_abstract", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("run_id", "source", "source_record_id"),
    )
    op.create_table(
        "source_material_resources",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("record_id", sa.String(36), sa.ForeignKey("source_material_records.id"), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.UniqueConstraint("record_id", "kind"),
    )
    op.create_table(
        "source_material_attempts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("resource_id", sa.String(36), sa.ForeignKey("source_material_resources.id"), nullable=False),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("request_url", sa.Text(), nullable=False),
        sa.Column("http_status", sa.Integer()),
        sa.Column("retrieved_at", sa.String(32), nullable=False),
        sa.Column("raw_path", sa.Text()),
        sa.Column("raw_sha256", sa.String(64)),
        sa.Column("raw_byte_size", sa.Integer()),
        sa.Column("content_type", sa.Text()),
        sa.Column("details_json", sa.Text(), nullable=False),
        sa.Column("error", sa.Text()),
        sa.UniqueConstraint("resource_id", "job_id"),
    )
    op.create_index("ix_material_records_run", "source_material_records", ["run_id", "ordinal"])
    op.create_index("ix_material_resources_record", "source_material_resources", ["record_id"])
    op.create_index("ix_material_attempts_resource", "source_material_attempts", ["resource_id"])
    op.create_table(
        "source_material_job_tasks",
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id"), primary_key=True),
        sa.Column("resource_id", sa.String(36), sa.ForeignKey("source_material_resources.id"), primary_key=True),
        sa.Column("ordinal", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("source_material_job_tasks")
    op.drop_table("source_material_attempts")
    op.drop_table("source_material_resources")
    op.drop_table("source_material_records")
    op.drop_table("source_material_runs")
