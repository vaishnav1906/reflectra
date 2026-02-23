"""add persona tables

Revision ID: 0002_add_persona_tables
Revises: 0001_init_schema
Create Date: 2026-02-20

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_add_persona_tables"
down_revision = "0001_init_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create user_persona_metrics table
    op.create_table(
        "user_persona_metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trait_name", sa.String(128), nullable=False),
        sa.Column("score", sa.Float(), nullable=False, server_default=sa.text("0.5")),
        sa.Column("confidence", sa.Float(), nullable=False, server_default=sa.text("0.1")),
        sa.Column("evidence_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_signal", sa.Float()),
        sa.Column("last_updated", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "trait_name", name="uq_user_trait"),
    )
    op.create_index("idx_persona_metrics_user_id", "user_persona_metrics", ["user_id"])
    op.create_index("idx_persona_metrics_trait_name", "user_persona_metrics", ["trait_name"])

    # Create persona_snapshots table
    op.create_table(
        "persona_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("persona_vector", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("stability_index", sa.Float()),
        sa.Column("summary_text", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_persona_snapshots_user_id", "persona_snapshots", ["user_id"])
    op.create_index("idx_persona_snapshots_user_created", "persona_snapshots", ["user_id", sa.text("created_at desc")])


def downgrade() -> None:
    op.drop_index("idx_persona_snapshots_user_created", table_name="persona_snapshots")
    op.drop_index("idx_persona_snapshots_user_id", table_name="persona_snapshots")
    op.drop_table("persona_snapshots")
    
    op.drop_index("idx_persona_metrics_trait_name", table_name="user_persona_metrics")
    op.drop_index("idx_persona_metrics_user_id", table_name="user_persona_metrics")
    op.drop_table("user_persona_metrics")
