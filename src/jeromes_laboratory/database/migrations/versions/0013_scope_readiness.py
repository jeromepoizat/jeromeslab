"""Add scope readiness and improve unused first-round scope prompts.

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from jeromes_laboratory.workflow.scope_clarification import load_scope_clarification_prompt
from jeromes_laboratory.workflow.scope_readiness import load_scope_readiness_prompt

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCOPE_CLARIFICATION_PROMPT_VERSION = "2"
DEFAULT_SCOPE_CLARIFICATION_PROMPT = load_scope_clarification_prompt(
    SCOPE_CLARIFICATION_PROMPT_VERSION
)
SCOPE_READINESS_PROMPT_VERSION = "1"
DEFAULT_SCOPE_READINESS_PROMPT = load_scope_readiness_prompt(SCOPE_READINESS_PROMPT_VERSION)


def upgrade() -> None:
    """Add readiness prompts and update only unconsumed scope defaults to v2."""
    op.execute(
        sa.text(
            "UPDATE projects SET scope_clarification_prompt = :prompt, "
            "scope_clarification_prompt_version = :version "
            "WHERE scope_clarification_prompt_version = '1' "
            "AND NOT EXISTS (SELECT 1 FROM jobs WHERE jobs.project_id = projects.id "
            "AND jobs.kind = 'scope_clarification_round_1')"
        ).bindparams(
            prompt=DEFAULT_SCOPE_CLARIFICATION_PROMPT,
            version=SCOPE_CLARIFICATION_PROMPT_VERSION,
        )
    )
    op.add_column("projects", sa.Column("scope_readiness_prompt", sa.Text(), nullable=True))
    op.add_column(
        "projects", sa.Column("scope_readiness_prompt_version", sa.String(32), nullable=True)
    )
    op.execute(
        sa.text(
            "UPDATE projects SET scope_readiness_prompt = :prompt, "
            "scope_readiness_prompt_version = :version"
        ).bindparams(
            prompt=DEFAULT_SCOPE_READINESS_PROMPT,
            version=SCOPE_READINESS_PROMPT_VERSION,
        )
    )
    with op.batch_alter_table("projects") as batch:
        batch.alter_column("scope_readiness_prompt", nullable=False)
        batch.alter_column("scope_readiness_prompt_version", nullable=False)


def downgrade() -> None:
    """Remove readiness prompts; consumed scope prompt history remains untouched."""
    with op.batch_alter_table("projects") as batch:
        batch.drop_column("scope_readiness_prompt_version")
        batch.drop_column("scope_readiness_prompt")
