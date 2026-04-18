"""add_confidence_controlled_mirror_models

Revision ID: 0010
Revises: 0009
Create Date: 2026-04-11T00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("mirror_logs", sa.Column("confidence_lower", sa.Float(), nullable=True))
    op.add_column("mirror_logs", sa.Column("confidence_upper", sa.Float(), nullable=True))
    op.add_column("mirror_logs", sa.Column("confidence_tier", sa.String(length=32), nullable=True))
    op.add_column("mirror_logs", sa.Column("style_enforcement_strength", sa.Float(), nullable=True))
    op.add_column("mirror_logs", sa.Column("reaction_match_score", sa.Float(), nullable=True))
    op.add_column(
        "mirror_logs",
        sa.Column("source_weights", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    )

    op.create_table(
        "linguistic_fingerprints",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("characteristic_phrases", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("abbreviation_stats", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("sentence_patterns", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("sample_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("confidence", sa.Float(), server_default=sa.text("0.1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(op.f("ix_linguistic_fingerprints_user_id"), "linguistic_fingerprints", ["user_id"], unique=True)

    op.create_table(
        "reaction_patterns",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stimulus_tag", sa.String(length=64), nullable=False),
        sa.Column("response_template", sa.Text(), nullable=False),
        sa.Column("phrase_bank", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("style_signature", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("confidence", sa.Float(), server_default=sa.text("0.3"), nullable=False),
        sa.Column("frequency", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "stimulus_tag", "response_template", name="uq_reaction_pattern_user_stimulus_template"),
    )
    op.create_index(op.f("ix_reaction_patterns_user_id"), "reaction_patterns", ["user_id"], unique=False)
    op.create_index(op.f("ix_reaction_patterns_stimulus_tag"), "reaction_patterns", ["stimulus_tag"], unique=False)

    op.create_table(
        "external_inputs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source", sa.String(length=64), server_default=sa.text("'pasted_prompt'"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("extracted_markers", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("confidence_weight", sa.Float(), server_default=sa.text("0.1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_external_inputs_user_id"), "external_inputs", ["user_id"], unique=False)



def downgrade() -> None:
    op.drop_index(op.f("ix_external_inputs_user_id"), table_name="external_inputs")
    op.drop_table("external_inputs")

    op.drop_index(op.f("ix_reaction_patterns_stimulus_tag"), table_name="reaction_patterns")
    op.drop_index(op.f("ix_reaction_patterns_user_id"), table_name="reaction_patterns")
    op.drop_table("reaction_patterns")

    op.drop_index(op.f("ix_linguistic_fingerprints_user_id"), table_name="linguistic_fingerprints")
    op.drop_table("linguistic_fingerprints")

    op.drop_column("mirror_logs", "source_weights")
    op.drop_column("mirror_logs", "reaction_match_score")
    op.drop_column("mirror_logs", "style_enforcement_strength")
    op.drop_column("mirror_logs", "confidence_tier")
    op.drop_column("mirror_logs", "confidence_upper")
    op.drop_column("mirror_logs", "confidence_lower")
