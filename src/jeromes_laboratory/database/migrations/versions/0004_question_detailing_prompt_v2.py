"""Update unused default question-detailing prompts to version 2.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from jeromes_laboratory.workflow.question_detailing import load_question_detailing_prompt

revision: str = "0004"
down_revision: str | None = "0003"
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
    """Apply the corrected wording only to projects still using default v1."""
    _replace_default_prompt("1", "2")


def downgrade() -> None:
    """Restore default v1 while leaving custom prompts untouched."""
    _replace_default_prompt("2", "1")
