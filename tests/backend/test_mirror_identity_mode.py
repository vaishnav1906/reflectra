#!/usr/bin/env python3
"""Regression tests for full-capability mirror identity behavior."""

import asyncio
import sys
import unittest
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.api.chat import detect_emotional_tone, map_emotion_to_mirror_style
from app.services.mirror_engine import (
    ASSISTANT_FALLBACK_TASK_TYPES,
    _hash_response_text,
    _is_recent_duplicate,
    _normalize_response_text,
    build_mirror_system_prompt,
)


class _DummyScalarResult:
    def __init__(self, payload):
        self._payload = payload

    def scalar_one_or_none(self):
        return self._payload


class _DummyAsyncDB:
    def __init__(self, payload):
        self.payload = payload

    async def execute(self, *_args, **_kwargs):
        return _DummyScalarResult(self.payload)


class MirrorIdentityContractTests(unittest.TestCase):
    def test_emotion_to_style_mapping_stays_deterministic(self):
        profile = {"themes": {}, "traits": {}, "values": {}, "stressors": {}, "insight_notes": []}
        emotion = detect_emotional_tone("i am overwhelmed and stressed with deadlines", profile)
        self.assertEqual(emotion, "stressed")
        self.assertEqual(map_emotion_to_mirror_style(emotion), "calm")

    def test_prompt_enforces_full_capability(self):
        prompt = build_mirror_system_prompt(
            sampled_profile={
                "communication_style": 0.72,
                "emotional_expressiveness": 0.66,
                "decision_framing": 0.71,
                "reflection_depth": 0.63,
            },
            stability_index=0.52,
            message_style={
                "avg_sentence_length": 10.0,
                "punctuation_intensity": 1,
                "has_slang": True,
                "emotional_markers": 2,
                "caps_intensity": 0.0,
                "has_questions": False,
            },
            task_type="generic",
            confidence_tier="moderate",
            detected_emotion="playful",
            active_mirror_style="chaotic",
            behavioral_signals=["User asks for concise drafts under stress"],
            linguistic_fingerprint="Characteristic phrases: lowkey this, real talk.",
        )

        # The mirror is the user talking back in their own voice, carrying the
        # detected mood/archetype and recent signals, and never sounding like an AI.
        self.assertIn("You ARE the user", prompt)
        self.assertIn("They seem playful", prompt)
        self.assertIn("Match playful, high-energy momentum", prompt)
        self.assertIn("User asks for concise drafts under stress", prompt)
        self.assertIn("Likes to explain and elaborate.", prompt)
        self.assertIn("Never", prompt)
        self.assertIn("Sound like an AI, assistant or therapist", prompt)

    def test_normalization_and_hash_are_stable(self):
        left = "  Same   Reply  Text "
        right = "same reply text"
        self.assertEqual(_normalize_response_text(left), _normalize_response_text(right))
        self.assertEqual(_hash_response_text(left), _hash_response_text(right))

    def test_recent_duplicate_helper_false_when_missing(self):
        db = _DummyAsyncDB(payload=None)
        is_dup = asyncio.run(_is_recent_duplicate(db, UUID("00000000-0000-0000-0000-000000000001"), "same answer"))
        self.assertFalse(is_dup)

    def test_assistant_fallback_task_set_excludes_generic_qa(self):
        self.assertIn("email_draft", ASSISTANT_FALLBACK_TASK_TYPES)
        self.assertNotIn("generic", ASSISTANT_FALLBACK_TASK_TYPES)


if __name__ == "__main__":
    unittest.main()
