#!/usr/bin/env python3
"""Regression tests for persona confidence updates in direct /mirror/chat endpoint."""

import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.api.mirror import MirrorRequest, mirror_chat


class _DummyExecuteResult:
    def scalar_one_or_none(self):
        return None


class _DummyAsyncDB:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    async def execute(self, *_args, **_kwargs):
        return _DummyExecuteResult()

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


class MirrorConfidenceUpdateTests(unittest.IsolatedAsyncioTestCase):
    async def test_mirror_chat_updates_persona_metrics(self):
        db = _DummyAsyncDB()
        request = MirrorRequest(user_id="00000000-0000-0000-0000-000000000001", message="I feel overwhelmed")

        with patch("app.api.mirror.generate_mirror_response", new=AsyncMock(return_value=("reply", {}))), \
             patch("app.api.mirror.resolve_twin_settings", return_value={"digital_twin_enabled": True, "persona_mirroring": True}), \
             patch("app.api.mirror.extract_traits", new=AsyncMock(return_value=[{"name": "communication_style", "signal": 0.7, "strength": 0.1}])), \
             patch("app.api.mirror.update_traits", new=AsyncMock()) as update_traits_mock, \
             patch("app.api.mirror.generate_persona_snapshot", new=AsyncMock()) as snapshot_mock, \
             patch("app.api.mirror.invalidate_snapshot_cache", new=MagicMock()) as invalidate_mock, \
             patch("app.repository.persona_repository.PersonaRepository.get_latest_snapshot", new=AsyncMock(return_value=object())):
            response = await mirror_chat(request, db)

        self.assertTrue(response.success)
        self.assertEqual(response.response, "reply")
        update_traits_mock.assert_awaited_once()
        snapshot_mock.assert_awaited_once()
        invalidate_mock.assert_called_once()
        self.assertEqual(db.commits, 1)
        self.assertEqual(db.rollbacks, 0)


if __name__ == "__main__":
    unittest.main()
