"""Select effective versions for confirmed research intents.

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Select existing intent confirmations without changing their content."""
    op.execute(
        sa.text(
            "INSERT INTO artifact_effective_versions "
            "(job_id, artifact_version_id, selected_at, selection_reason) "
            "SELECT artifact.job_id, artifact.id, artifact.created_at, 'confirmed_intent' "
            "FROM artifact_versions artifact "
            "WHERE artifact.kind = 'intent_clarification_selection' "
            "AND artifact.version_number = 1 "
            "AND NOT EXISTS (SELECT 1 FROM artifact_effective_versions effective "
            "WHERE effective.job_id = artifact.job_id)"
        )
    )


def downgrade() -> None:
    """Remove intent selections while leaving their immutable artifacts intact."""
    op.execute(
        sa.text(
            "DELETE FROM artifact_effective_versions WHERE artifact_version_id IN "
            "(SELECT id FROM artifact_versions "
            "WHERE kind = 'intent_clarification_selection')"
        )
    )
