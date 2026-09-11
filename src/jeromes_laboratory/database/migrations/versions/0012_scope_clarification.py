"""Add first-round scope-clarification prompt and input snapshots.

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from jeromes_laboratory.workflow.scope_clarification import load_scope_clarification_prompt

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCOPE_CLARIFICATION_PROMPT_VERSION = "1"
DEFAULT_SCOPE_CLARIFICATION_PROMPT = load_scope_clarification_prompt(
    SCOPE_CLARIFICATION_PROMPT_VERSION
)


def upgrade() -> None:
    """Add versioned scope prompts and generic structured job-input snapshots."""
    op.add_column("projects", sa.Column("scope_clarification_prompt", sa.Text(), nullable=True))
    op.add_column(
        "projects", sa.Column("scope_clarification_prompt_version", sa.String(32), nullable=True)
    )
    op.execute(
        sa.text(
            "UPDATE projects SET scope_clarification_prompt = :prompt, "
            "scope_clarification_prompt_version = :version"
        ).bindparams(
            prompt=DEFAULT_SCOPE_CLARIFICATION_PROMPT,
            version=SCOPE_CLARIFICATION_PROMPT_VERSION,
        )
    )
    with op.batch_alter_table("projects") as batch:
        batch.alter_column("scope_clarification_prompt", nullable=False)
        batch.alter_column("scope_clarification_prompt_version", nullable=False)
    op.add_column("jobs", sa.Column("workflow_input_snapshot_json", sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove scope prompt and structured input snapshot fields."""
    with op.batch_alter_table("jobs") as batch:
        batch.drop_column("workflow_input_snapshot_json")
    with op.batch_alter_table("projects") as batch:
        batch.drop_column("scope_clarification_prompt_version")
        batch.drop_column("scope_clarification_prompt")
