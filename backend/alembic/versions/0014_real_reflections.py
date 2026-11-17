"""Evidence-backed reflections

Adds a title, supporting quotes and a kind to behavioral_insights so the
Reflections page can show real cross-conversation patterns ("reflection")
instead of the old per-message templated lines ("signal").

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("behavioral_insights", sa.Column("kind", sa.String(length=32), server_default=sa.text("'signal'"), nullable=False))
    op.add_column("behavioral_insights", sa.Column("title", sa.Text(), nullable=True))
    op.add_column(
        "behavioral_insights",
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    )
    op.create_index("ix_behavioral_insights_user_kind", "behavioral_insights", ["user_id", "kind", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_behavioral_insights_user_kind", table_name="behavioral_insights")
    op.drop_column("behavioral_insights", "evidence")
    op.drop_column("behavioral_insights", "title")
    op.drop_column("behavioral_insights", "kind")
