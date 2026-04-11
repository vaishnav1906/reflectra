"""add_digital_twin_controls

Revision ID: 0008
Revises: 0007
Create Date: 2026-04-08T00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column("digital_twin_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.add_column(
        "user_settings",
        sa.Column("twin_autonomy_mode", sa.String(length=32), server_default=sa.text("'draft_only'"), nullable=False),
    )
    op.add_column(
        "user_settings",
        sa.Column("twin_mirror_intensity", sa.Float(), server_default=sa.text("0.8"), nullable=False),
    )
    op.add_column(
        "user_settings",
        sa.Column("twin_require_approval", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("user_settings", "twin_require_approval")
    op.drop_column("user_settings", "twin_mirror_intensity")
    op.drop_column("user_settings", "twin_autonomy_mode")
    op.drop_column("user_settings", "digital_twin_enabled")
