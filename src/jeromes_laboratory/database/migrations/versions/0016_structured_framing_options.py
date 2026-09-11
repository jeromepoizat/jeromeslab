"""Require explicit independent or cumulative framing options.

Revision ID: 0016
Revises: 0015
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from jeromes_laboratory.workflow.scope_clarification import load_scope_clarification_prompt
from jeromes_laboratory.workflow.scope_readiness import load_scope_readiness_prompt

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCOPE_PROMPT_VERSION = "4"
READINESS_PROMPT_VERSION = "4"


def upgrade() -> None:
    """Update only framing prompts that their corresponding jobs have not consumed."""
    connection = op.get_bind()
    updates = (
        (
            "scope_clarification_prompt",
            "scope_clarification_prompt_version",
            "scope_clarification_round_1",
            "3",
            SCOPE_PROMPT_VERSION,
            load_scope_clarification_prompt(SCOPE_PROMPT_VERSION),
        ),
        (
            "scope_readiness_prompt",
            "scope_readiness_prompt_version",
            "scope_readiness",
            "3",
            READINESS_PROMPT_VERSION,
            load_scope_readiness_prompt(READINESS_PROMPT_VERSION),
        ),
    )
    for prompt_column, version_column, job_kind, old_version, new_version, prompt in updates:
        connection.execute(
            sa.text(
                f"UPDATE projects SET {prompt_column} = :prompt, "
                f"{version_column} = :new_version "
                f"WHERE {version_column} = :old_version "
                "AND NOT EXISTS (SELECT 1 FROM jobs WHERE jobs.project_id = projects.id "
                "AND jobs.kind = :job_kind)"
            ),
            {
                "prompt": prompt,
                "new_version": new_version,
                "old_version": old_version,
                "job_kind": job_kind,
            },
        )


def downgrade() -> None:
    """Keep prompt snapshots unchanged when rolling back application schema."""
