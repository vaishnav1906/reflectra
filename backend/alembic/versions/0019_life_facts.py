"""Life memory: lasting facts about the user's life, in their own words

Revision ID: 0019
Revises: 0018
Create Date: 2026-11-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "life_facts",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("quote", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=8), server_default=sa.text("'chat'"), nullable=False),
        sa.Column("status", sa.String(length=12), server_default=sa.text("'active'"), nullable=False),
        sa.Column("pinned", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("mention_count", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("first_seen", sa.String(length=10), nullable=True),
        sa.Column("last_seen", sa.String(length=10), nullable=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_life_facts_user_status", "life_facts", ["user_id", "status"])
    op.execute("ALTER TABLE public.life_facts ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_index("ix_life_facts_user_status", table_name="life_facts")
    op.drop_table("life_facts")
