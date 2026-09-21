"""Adopt a concise charter prompt for unconsumed charter stages.

Revision ID: 0020
Revises: 0019
Create Date: 2026-09-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from jeromes_laboratory.workflow.research_charter import load_research_charter_prompt

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Update only a default charter prompt that no charter job has consumed."""
    op.get_bind().execute(
        sa.text(
            "UPDATE projects SET research_charter_prompt = :prompt, "
            "research_charter_prompt_version = '4' "
            "WHERE research_charter_prompt_version = '3' "
            "AND NOT EXISTS (SELECT 1 FROM jobs WHERE jobs.project_id = projects.id "
            "AND jobs.kind = 'research_charter')"
        ),
        {"prompt": load_research_charter_prompt("4")},
    )


def downgrade() -> None:
    """Keep prompt snapshots unchanged when rolling back application schema."""
