"""Add versioned intent-clarification input snapshots.

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from jeromes_laboratory.workflow.intent_clarification import (
    DEFAULT_INTENT_CLARIFICATION_PROMPT,
    INTENT_CLARIFICATION_PROMPT_VERSION,
)

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Snapshot the exact intent prompt for existing and future projects."""
    op.add_column("projects", sa.Column("intent_clarification_prompt", sa.Text(), nullable=True))
    op.add_column(
        "projects", sa.Column("intent_clarification_prompt_version", sa.String(32), nullable=True)
    )
    op.execute(
        sa.text(
            "UPDATE projects SET intent_clarification_prompt = :prompt, "
            "intent_clarification_prompt_version = :version"
        ).bindparams(
            prompt=DEFAULT_INTENT_CLARIFICATION_PROMPT,
            version=INTENT_CLARIFICATION_PROMPT_VERSION,
        )
    )
    with op.batch_alter_table("projects") as batch:
        batch.alter_column("intent_clarification_prompt", nullable=False)
        batch.alter_column("intent_clarification_prompt_version", nullable=False)


def downgrade() -> None:
    """Remove intent prompt snapshots without touching legacy workflow data."""
    with op.batch_alter_table("projects") as batch:
        batch.drop_column("intent_clarification_prompt_version")
        batch.drop_column("intent_clarification_prompt")
