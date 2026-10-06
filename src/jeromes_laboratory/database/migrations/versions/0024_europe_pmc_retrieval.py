"""Record immutable Europe PMC search runs, pages, and discovered records.

Revision ID: 0024
Revises: 0023
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "search_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("query_id", sa.String(100), nullable=False),
        sa.Column("query_title", sa.String(160), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("adapter_version", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("total_hits", sa.Integer(), nullable=True),
        sa.Column("retrieved_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("truncated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("started_at", sa.String(32), nullable=True),
        sa.Column("completed_at", sa.String(32), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.UniqueConstraint("job_id", "query_id", name="uq_search_run_job_query"),
    )
    op.create_table(
        "search_pages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("search_runs.id"), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("request_url", sa.Text(), nullable=False),
        sa.Column("cursor_mark", sa.Text(), nullable=False),
        sa.Column("next_cursor_mark", sa.Text(), nullable=True),
        sa.Column("retrieved_at", sa.String(32), nullable=False),
        sa.Column("raw_path", sa.Text(), nullable=False),
        sa.Column("raw_sha256", sa.String(64), nullable=False),
        sa.Column("raw_byte_size", sa.Integer(), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=False),
        sa.UniqueConstraint("run_id", "page_number", name="uq_search_page_run_number"),
    )
    op.create_table(
        "publication_source_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("search_runs.id"), nullable=False),
        sa.Column("page_id", sa.String(36), sa.ForeignKey("search_pages.id"), nullable=False),
        sa.Column("item_index", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("source_record_id", sa.String(255), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("author_string", sa.Text(), nullable=True),
        sa.Column("journal_title", sa.Text(), nullable=True),
        sa.Column("publication_date", sa.String(64), nullable=True),
        sa.Column("doi", sa.String(255), nullable=True),
        sa.Column("pmid", sa.String(64), nullable=True),
        sa.Column("pmcid", sa.String(64), nullable=True),
        sa.Column("abstract_text", sa.Text(), nullable=True),
        sa.Column("is_preprint", sa.Boolean(), nullable=True),
        sa.UniqueConstraint("page_id", "item_index", name="uq_publication_page_item"),
    )
    op.create_index("ix_publication_source_identity", "publication_source_records", ["source", "source_record_id"])
    op.create_index("ix_publication_source_run", "publication_source_records", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_publication_source_run", table_name="publication_source_records")
    op.drop_index("ix_publication_source_identity", table_name="publication_source_records")
    op.drop_table("publication_source_records")
    op.drop_table("search_pages")
    op.drop_table("search_runs")
