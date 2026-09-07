"""Snapshot the question-detailing prompt for each project.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from jeromes_laboratory.workflow.question_detailing import (
    DEFAULT_QUESTION_DETAILING_PROMPT,
    QUESTION_DETAILING_PROMPT_VERSION,
)

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Preserve the exact effective prompt despite later application updates."""
    op.add_column("projects", sa.Column("question_detailing_prompt", sa.Text(), nullable=True))
    op.add_column("projects", sa.Column("question_detailing_prompt_version", sa.String(32), nullable=True))
    op.execute(
        sa.text(
            "UPDATE projects SET question_detailing_prompt = :prompt, "
            "question_detailing_prompt_version = :version"
        ).bindparams(prompt=DEFAULT_QUESTION_DETAILING_PROMPT, version=QUESTION_DETAILING_PROMPT_VERSION)
    )
    with op.batch_alter_table("projects") as batch:
        batch.alter_column("question_detailing_prompt", nullable=False)
        batch.alter_column("question_detailing_prompt_version", nullable=False)


def downgrade() -> None:
    """Remove the prompt snapshot fields."""
    with op.batch_alter_table("projects") as batch:
        batch.drop_column("question_detailing_prompt_version")
        batch.drop_column("question_detailing_prompt")
