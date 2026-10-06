"""Add Europe PMC query-draft prompt and exact-version approvals.

Revision ID: 0023
Revises: 0022
Create Date: 2026-10-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from jeromes_laboratory.workflow.source_queries import DEFAULT_SOURCE_QUERIES_PROMPT

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("source_queries_prompt", sa.Text(), nullable=True))
    op.add_column(
        "projects", sa.Column("source_queries_prompt_version", sa.String(32), nullable=True)
    )
    op.execute(
        sa.text(
            "UPDATE projects SET source_queries_prompt = :prompt, "
            "source_queries_prompt_version = '1'"
        ).bindparams(prompt=DEFAULT_SOURCE_QUERIES_PROMPT)
    )
    with op.batch_alter_table("projects") as batch:
        batch.alter_column("source_queries_prompt", nullable=False)
        batch.alter_column("source_queries_prompt_version", nullable=False)
    op.create_table(
        "source_queries_approvals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column(
            "artifact_version_id",
            sa.String(36),
            sa.ForeignKey("artifact_versions.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("approved_at", sa.String(32), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("source_queries_approvals")
    with op.batch_alter_table("projects") as batch:
        batch.drop_column("source_queries_prompt_version")
        batch.drop_column("source_queries_prompt")
