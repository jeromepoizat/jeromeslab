"""Adopt therapeutic peptide discovery prompts for unconsumed stages.

Revision ID: 0018
Revises: 0017
Create Date: 2026-09-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from jeromes_laboratory.workflow.intent_clarification import load_intent_clarification_prompt
from jeromes_laboratory.workflow.research_charter import load_research_charter_prompt
from jeromes_laboratory.workflow.scope_clarification import load_scope_clarification_prompt
from jeromes_laboratory.workflow.scope_readiness import load_scope_readiness_prompt

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Update only defaults that have not been consumed by their stage."""
    connection = op.get_bind()
    updates = (
        (
            "intent_clarification_prompt",
            "intent_clarification_prompt_version",
            "intent_clarification",
            "2",
            "3",
            load_intent_clarification_prompt("3"),
        ),
        (
            "scope_clarification_prompt",
            "scope_clarification_prompt_version",
            "scope_clarification_round_1",
            "4",
            "5",
            load_scope_clarification_prompt("5"),
        ),
        (
            "scope_readiness_prompt",
            "scope_readiness_prompt_version",
            "scope_readiness",
            "4",
            "5",
            load_scope_readiness_prompt("5"),
        ),
        (
            "research_charter_prompt",
            "research_charter_prompt_version",
            "research_charter",
            "1",
            "2",
            load_research_charter_prompt("2"),
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
