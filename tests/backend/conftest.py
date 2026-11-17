"""Pytest configuration for backend tests."""

import os

# Unit tests never touch a real database, but importing the app needs a URL.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")

# These two are live-database scripts (not unit tests) and currently contain
# unresolved merge-conflict markers, so they cannot be imported.
collect_ignore = ["test_conversations.py", "test_past_conversations.py"]
