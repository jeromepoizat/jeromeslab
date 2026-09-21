"""Adopt investigation terminology for unconsumed workflow prompts.

Revision ID: 0019
Revises: 0018
Create Date: 2026-09-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from jeromes_laboratory.workflow.intent_clarification import load_intent_clarification_prompt
from jeromes_laboratory.workflow.research_charter import load_research_charter_prompt
from jeromes_laboratory.workflow.scope_clarification import load_scope_clarification_prompt
from jeromes_laboratory.workflow.scope_readiness import load_scope_readiness_prompt

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Update only defaults that their corresponding stage has not consumed."""
    connection = op.get_bind()
    updates = (
        (
            "intent_clarification_prompt",
            "intent_clarification_prompt_version",
            "intent_clarification",
            "3",
            "4",
            load_intent_clarification_prompt("4"),
        ),
        (
            "scope_clarification_prompt",
            "scope_clarification_prompt_version",
            "scope_clarification_round_1",
            "5",
            "6",
            load_scope_clarification_prompt("6"),
        ),
        (
            "scope_readiness_prompt",
            "scope_readiness_prompt_version",
            "scope_readiness",
            "5",
            "6",
            load_scope_readiness_prompt("6"),
        ),
        (
            "research_charter_prompt",
            "research_charter_prompt_version",
            "research_charter",
            "2",
            "3",
            load_research_charter_prompt("3"),
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
