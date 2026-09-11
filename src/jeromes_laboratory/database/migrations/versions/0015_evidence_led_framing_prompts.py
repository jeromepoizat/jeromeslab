"""Adopt evidence-led project framing for future workflow calls.

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from jeromes_laboratory.workflow.intent_clarification import load_intent_clarification_prompt
from jeromes_laboratory.workflow.scope_clarification import load_scope_clarification_prompt
from jeromes_laboratory.workflow.scope_readiness import load_scope_readiness_prompt

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INTENT_PROMPT_VERSION = "2"
SCOPE_PROMPT_VERSION = "3"
READINESS_PROMPT_VERSION = "3"


def upgrade() -> None:
    """Update defaults only when the corresponding prompt has not been consumed."""
    connection = op.get_bind()
    updates = (
        (
            "intent_clarification_prompt",
            "intent_clarification_prompt_version",
            "intent_clarification",
            "1",
            INTENT_PROMPT_VERSION,
            load_intent_clarification_prompt(INTENT_PROMPT_VERSION),
        ),
        (
            "scope_clarification_prompt",
            "scope_clarification_prompt_version",
            "scope_clarification_round_1",
            "2",
            SCOPE_PROMPT_VERSION,
            load_scope_clarification_prompt(SCOPE_PROMPT_VERSION),
        ),
        (
            "scope_readiness_prompt",
            "scope_readiness_prompt_version",
            "scope_readiness",
            "2",
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
