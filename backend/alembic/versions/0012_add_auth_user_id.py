"""Link users to Supabase Auth

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("auth_user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index(op.f("ix_users_auth_user_id"), "users", ["auth_user_id"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_users_auth_user_id"), table_name="users")
    op.drop_column("users", "auth_user_id")
