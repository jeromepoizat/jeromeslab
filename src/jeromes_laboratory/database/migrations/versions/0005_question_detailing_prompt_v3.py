"""Update unused default question-detailing prompts to version 3.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from jeromes_laboratory.workflow.question_detailing import load_question_detailing_prompt

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _replace_default_prompt(from_version: str, to_version: str) -> None:
    op.execute(
        sa.text(
            "UPDATE projects SET question_detailing_prompt = :prompt, "
            "question_detailing_prompt_version = :to_version "
            "WHERE question_detailing_prompt_version = :from_version"
        ).bindparams(
            prompt=load_question_detailing_prompt(to_version),
            to_version=to_version,
            from_version=from_version,
        )
    )


def upgrade() -> None:
    """Apply the flexible JSON-envelope prompt only to default v2 projects."""
    _replace_default_prompt("2", "3")


def downgrade() -> None:
    """Restore default v2 while leaving custom prompts untouched."""
    _replace_default_prompt("3", "2")
