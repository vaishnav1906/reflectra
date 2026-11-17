"""Feedback: what the user says about replies, trait readings and reflections

One row per thing they rated; changing their mind updates the row. Row Level
Security is enabled like every other public table (see 0013): the backend
connects as the owner, and the Supabase Data API gets no access.

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_type", sa.String(length=16), nullable=False),
        sa.Column("target_id", sa.String(length=64), nullable=False),
        sa.Column("verdict", sa.String(length=16), nullable=False),
        sa.Column("reasons", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "target_type", "target_id", name="uq_feedback_target"),
    )
    op.create_index("ix_feedback_user_type", "feedback", ["user_id", "target_type", "updated_at"])
    op.execute("ALTER TABLE public.feedback ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_index("ix_feedback_user_type", table_name="feedback")
    op.drop_table("feedback")
