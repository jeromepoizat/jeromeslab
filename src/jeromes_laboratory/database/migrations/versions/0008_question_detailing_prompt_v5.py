"""Update only unused default question-detailing prompts to version 5.

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from jeromes_laboratory.workflow.question_detailing import load_question_detailing_prompt

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _replace_unused_default(from_version: str, to_version: str) -> None:
    op.execute(
        sa.text(
            "UPDATE projects SET question_detailing_prompt = :prompt, "
            "question_detailing_prompt_version = :to_version "
            "WHERE question_detailing_prompt_version = :from_version "
            "AND NOT EXISTS (SELECT 1 FROM jobs WHERE jobs.project_id = projects.id "
            "AND jobs.kind = 'question_detailing')"
        ).bindparams(
            prompt=load_question_detailing_prompt(to_version),
            to_version=to_version,
            from_version=from_version,
        )
    )


def upgrade() -> None:
    """Adopt the query-oriented prompt without rewriting consumed inputs."""
    _replace_unused_default("4", "5")


def downgrade() -> None:
    """Restore version 4 only where version 5 has not been consumed."""
    _replace_unused_default("5", "4")
