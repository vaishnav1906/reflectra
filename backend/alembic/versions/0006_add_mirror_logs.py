"""add_mirror_logs

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-05T07:22:25.542029

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0006'
down_revision: Union[str, None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'mirror_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('message_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('inference_duration_ms', sa.Integer(), nullable=False),
        sa.Column('realism_score', sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column('retries_used', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('fallback_triggered', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_mirror_logs_user_id'), 'mirror_logs', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_mirror_logs_user_id'), table_name='mirror_logs')
    op.drop_table('mirror_logs')
