"""Track the effective artifact version without changing immutable outputs.

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create an explicit mutable selection over immutable artifact versions."""
    op.create_table(
        "artifact_effective_versions",
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id"), primary_key=True),
        sa.Column(
            "artifact_version_id",
            sa.String(36),
            sa.ForeignKey("artifact_versions.id"),
            nullable=False,
        ),
        sa.Column("selected_at", sa.String(32), nullable=False),
        sa.Column("selection_reason", sa.String(64), nullable=False),
    )
    op.execute(
        sa.text(
            "INSERT INTO artifact_effective_versions "
            "(job_id, artifact_version_id, selected_at, selection_reason) "
            "SELECT job_id, id, created_at, 'original_output' FROM artifact_versions "
            "WHERE kind = 'question_detailing_output' AND version_number = 1"
        )
    )


def downgrade() -> None:
    """Remove effective selection while retaining all immutable versions."""
    op.drop_table("artifact_effective_versions")
