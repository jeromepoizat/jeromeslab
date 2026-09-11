"""Prevent readiness follow-ups from retrying answered scope questions.

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from jeromes_laboratory.workflow.scope_readiness import load_scope_readiness_prompt

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCOPE_READINESS_PROMPT_VERSION = "2"
DEFAULT_SCOPE_READINESS_PROMPT = load_scope_readiness_prompt(SCOPE_READINESS_PROMPT_VERSION)


def upgrade() -> None:
    """Update only the default readiness prompt that no job has consumed."""
    op.execute(
        sa.text(
            "UPDATE projects SET scope_readiness_prompt = :prompt, "
            "scope_readiness_prompt_version = :version "
            "WHERE scope_readiness_prompt_version = '1' "
            "AND NOT EXISTS (SELECT 1 FROM jobs WHERE jobs.project_id = projects.id "
            "AND jobs.kind = 'scope_readiness')"
        ).bindparams(
            prompt=DEFAULT_SCOPE_READINESS_PROMPT,
            version=SCOPE_READINESS_PROMPT_VERSION,
        )
    )


def downgrade() -> None:
    """Keep prompt snapshots unchanged when rolling back application schema."""
