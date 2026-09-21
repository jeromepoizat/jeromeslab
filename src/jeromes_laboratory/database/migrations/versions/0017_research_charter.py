"""Add current-cycle charter prompts and append-only approvals.

Revision ID: 0017
Revises: 0016
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from jeromes_laboratory.workflow.research_charter import load_research_charter_prompt

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("research_charter_prompt", sa.Text(), nullable=True))
    op.add_column(
        "projects", sa.Column("research_charter_prompt_version", sa.String(32), nullable=True)
    )
    op.execute(sa.text(
        "UPDATE projects SET research_charter_prompt = :prompt, "
        "research_charter_prompt_version = '1'"
    ).bindparams(prompt=load_research_charter_prompt("1")))
    with op.batch_alter_table("projects") as batch:
        batch.alter_column("research_charter_prompt", nullable=False)
        batch.alter_column("research_charter_prompt_version", nullable=False)
    op.create_table(
        "research_charter_approvals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("artifact_version_id", sa.String(36), sa.ForeignKey("artifact_versions.id"),
                  nullable=False, unique=True),
        sa.Column("approved_at", sa.String(32), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("research_charter_approvals")
    with op.batch_alter_table("projects") as batch:
        batch.drop_column("research_charter_prompt_version")
        batch.drop_column("research_charter_prompt")
