"""Append-only scoring extensions and immutable scored-set confirmation.

Revision ID: 0026
Revises: 0025
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "relevance_scoring_extensions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("relevance_scoring_runs.id"), nullable=False),
        sa.Column("previous_count", sa.Integer(), nullable=False),
        sa.Column("added_count", sa.Integer(), nullable=False),
        sa.Column("added_manifest_json", sa.Text(), nullable=False),
        sa.Column("added_manifest_sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.String(32), nullable=False),
    )
    op.create_index("ix_relevance_extensions_run", "relevance_scoring_extensions", ["run_id"])
    op.create_table(
        "relevance_scoring_confirmations",
        sa.Column("run_id", sa.String(36), sa.ForeignKey("relevance_scoring_runs.id"), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("content_json", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("scored_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(32), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("relevance_scoring_confirmations")
    op.drop_index("ix_relevance_extensions_run", table_name="relevance_scoring_extensions")
    op.drop_table("relevance_scoring_extensions")
