"""Preserve a validated score-threshold selection of the frozen scoring pool."""

import sqlalchemy as sa
from alembic import op

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "relevance_score_filters",
        sa.Column("run_id", sa.String(36),
                  sa.ForeignKey("relevance_scoring_confirmations.run_id"), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("content_json", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.String(32), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("relevance_score_filters")
