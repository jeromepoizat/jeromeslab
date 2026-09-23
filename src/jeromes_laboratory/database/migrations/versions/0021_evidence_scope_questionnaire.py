"""Add the evidence-search scope questionnaire prompt.

Revision ID: 0021
Revises: 0020
Create Date: 2026-09-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from jeromes_laboratory.workflow.evidence_scope import DEFAULT_EVIDENCE_SCOPE_PROMPT

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add one versioned project prompt without changing consumed history."""
    op.add_column("projects", sa.Column("evidence_scope_prompt", sa.Text(), nullable=True))
    op.add_column(
        "projects", sa.Column("evidence_scope_prompt_version", sa.String(32), nullable=True)
    )
    op.execute(
        sa.text(
            "UPDATE projects SET evidence_scope_prompt = :prompt, "
            "evidence_scope_prompt_version = '1'"
        ).bindparams(prompt=DEFAULT_EVIDENCE_SCOPE_PROMPT)
    )
    with op.batch_alter_table("projects") as batch:
        batch.alter_column("evidence_scope_prompt", nullable=False)
        batch.alter_column("evidence_scope_prompt_version", nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("projects") as batch:
        batch.drop_column("evidence_scope_prompt_version")
        batch.drop_column("evidence_scope_prompt")
