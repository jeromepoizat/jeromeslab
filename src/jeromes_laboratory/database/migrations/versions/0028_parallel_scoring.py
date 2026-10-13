"""Bounded parallel execution for a single logical scoring run."""

import sqlalchemy as sa
from alembic import op

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("relevance_scoring_runs", sa.Column(
        "parallel_batches", sa.Integer(), nullable=False, server_default="1",
    ))


def downgrade() -> None:
    op.drop_column("relevance_scoring_runs", "parallel_batches")
