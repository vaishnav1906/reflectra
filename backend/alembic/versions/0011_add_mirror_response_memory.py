"""add_mirror_response_memory

Revision ID: 0011
Revises: 0010
Create Date: 2026-04-18T00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mirror_response_memories",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("response_hash", sa.String(length=64), nullable=False),
        sa.Column("response_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mirror_response_memories_user_id"), "mirror_response_memories", ["user_id"], unique=False)
    op.create_index(op.f("ix_mirror_response_memories_response_hash"), "mirror_response_memories", ["response_hash"], unique=False)
    op.create_index(
        "ix_mirror_response_memories_user_created_at",
        "mirror_response_memories",
        ["user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_mirror_response_memories_user_created_at", table_name="mirror_response_memories")
    op.drop_index(op.f("ix_mirror_response_memories_response_hash"), table_name="mirror_response_memories")
    op.drop_index(op.f("ix_mirror_response_memories_user_id"), table_name="mirror_response_memories")
    op.drop_table("mirror_response_memories")
