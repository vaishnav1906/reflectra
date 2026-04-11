"""migrate_assistant_mode_to_mirror

Revision ID: 0009
Revises: 0008
Create Date: 2026-04-09T00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE conversations SET mode = 'mirror' WHERE mode = 'assistant';")


def downgrade() -> None:
    # Irreversible data migration.
    pass
