"""People: friends and family the user describes, so replies know who's who

Row Level Security on, like every public table (see 0013).

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "people",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("name_key", sa.String(length=80), nullable=False),
        sa.Column("aliases", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("relationship_label", sa.String(length=80), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("birthday", sa.String(length=10), nullable=True),
        sa.Column("notes", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("status", sa.String(length=16), server_default=sa.text("'active'"), nullable=False),
        sa.Column("mention_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_mentioned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "name_key", name="uq_people_user_name"),
    )
    op.create_index("ix_people_user_status", "people", ["user_id", "status"])
    op.execute("ALTER TABLE public.people ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_index("ix_people_user_status", table_name="people")
    op.drop_table("people")
