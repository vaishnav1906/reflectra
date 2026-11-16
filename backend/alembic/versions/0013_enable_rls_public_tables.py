"""Enable Row Level Security on all public tables

Supabase exposes the `public` schema through its Data API, so with RLS off
anyone holding the (public) publishable/anon key could read and write every
table directly. Reflectra never uses the Data API for app data: the backend
connects as the table owner (which bypasses RLS) and the frontend only uses
Supabase for authentication. Enabling RLS with no policies therefore blocks
the Data API completely without affecting the app.

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-16

"""
from typing import Sequence, Union

from alembic import op


revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ENABLE_ALL = """
DO $$
DECLARE
    tbl record;
BEGIN
    FOR tbl IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', tbl.tablename);
    END LOOP;
END $$;
"""

DISABLE_ALL = """
DO $$
DECLARE
    tbl record;
BEGIN
    FOR tbl IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
        EXECUTE format('ALTER TABLE public.%I DISABLE ROW LEVEL SECURITY', tbl.tablename);
    END LOOP;
END $$;
"""


def upgrade() -> None:
    op.execute(ENABLE_ALL)


def downgrade() -> None:
    op.execute(DISABLE_ALL)
