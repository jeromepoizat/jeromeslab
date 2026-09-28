"""Add versioned strategy prompt and exact-version strategy approvals.

Revision ID: 0022
Revises: 0021
Create Date: 2026-09-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from jeromes_laboratory.workflow.evidence_strategy import DEFAULT_EVIDENCE_STRATEGY_PROMPT

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("evidence_strategy_prompt", sa.Text(), nullable=True))
    op.add_column(
        "projects", sa.Column("evidence_strategy_prompt_version", sa.String(32), nullable=True)
    )
    op.execute(
        sa.text(
            "UPDATE projects SET evidence_strategy_prompt = :prompt, "
            "evidence_strategy_prompt_version = '1'"
        ).bindparams(prompt=DEFAULT_EVIDENCE_STRATEGY_PROMPT)
    )
    with op.batch_alter_table("projects") as batch:
        batch.alter_column("evidence_strategy_prompt", nullable=False)
        batch.alter_column("evidence_strategy_prompt_version", nullable=False)
    op.create_table(
        "evidence_strategy_approvals",
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
    op.drop_table("evidence_strategy_approvals")
    with op.batch_alter_table("projects") as batch:
        batch.drop_column("evidence_strategy_prompt_version")
        batch.drop_column("evidence_strategy_prompt")
