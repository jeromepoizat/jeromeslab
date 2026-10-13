"""Bounded batch reads and immutable retrieval-count cache for scoring progress."""

import sqlalchemy as sa
from alembic import op

revision: str = "0029"
down_revision: str | None = "0028"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("relevance_scoring_runs", sa.Column(
        "retrieved_record_count", sa.Integer(), nullable=False, server_default="0",
    ))
    op.create_table(
        "relevance_scoring_batch_inputs",
        sa.Column("run_id", sa.String(36), sa.ForeignKey("relevance_scoring_runs.id"), primary_key=True),
        sa.Column("batch_index", sa.Integer(), primary_key=True),
        sa.Column("records_json", sa.Text(), nullable=False),
    )
    op.execute(
        "INSERT INTO relevance_scoring_batch_inputs (run_id, batch_index, records_json) "
        "SELECT runs.id, CAST(batch.key AS INTEGER), batch.value "
        "FROM relevance_scoring_runs runs, json_each(runs.batches_json) batch"
    )
    op.execute(
        "UPDATE relevance_scoring_runs SET retrieved_record_count = (SELECT COUNT(*) FROM "
        "(SELECT DISTINCT records.source, records.source_record_id FROM publication_source_records records "
        "JOIN search_runs searches ON searches.id = records.run_id "
        "WHERE searches.job_id = relevance_scoring_runs.retrieval_job_id))"
    )


def downgrade() -> None:
    op.drop_table("relevance_scoring_batch_inputs")
    op.drop_column("relevance_scoring_runs", "retrieved_record_count")
