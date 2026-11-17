"""Jobs: background learning queued by requests and run by the worker

Revision ID: 0018
Revises: 0017
Create Date: 2026-11-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("status", sa.String(length=12), server_default=sa.text("'queued'"), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("dedupe_key", sa.String(length=120), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("run_after", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_jobs_user_id", "jobs", ["user_id"])
    # The worker's claim query: waiting jobs in run order.
    op.create_index("ix_jobs_waiting", "jobs", ["run_after"], postgresql_where=sa.text("status = 'queued'"))
    op.create_index("ix_jobs_dedupe", "jobs", ["dedupe_key"], postgresql_where=sa.text("status IN ('queued', 'running')"))
    op.execute("ALTER TABLE public.jobs ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_index("ix_jobs_dedupe", table_name="jobs")
    op.drop_index("ix_jobs_waiting", table_name="jobs")
    op.drop_index("ix_jobs_user_id", table_name="jobs")
    op.drop_table("jobs")
