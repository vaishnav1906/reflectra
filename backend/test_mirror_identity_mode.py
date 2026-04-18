#!/usr/bin/env python3
"""Regression tests for full-capability mirror identity behavior."""

import asyncio
import sys
import unittest
from pathlib import Path
from uuid import UUID

backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from app.api.chat import detect_emotional_tone, map_emotion_to_mirror_style
from app.services.mirror_engine import (
    ASSISTANT_FALLBACK_TASK_TYPES,
    _hash_response_text,
    _is_recent_duplicate,
    _is_low_quality_candidate,
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
                "emotional_intensity": 0.6,
                "emotional_stability": 0.5,
                "directness": 0.7,
                "expressiveness": 0.6,
                "analytical_thinking": 0.55,
                "decision_confidence": 0.65,
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

        self.assertIn("Always answer with full assistant capability", prompt)
        self.assertIn("Active Archetype: chaotic", prompt)
        self.assertIn("Detected Emotion: playful", prompt)

    def test_normalization_and_hash_are_stable(self):
        left = "  Same   Reply  Text "
        right = "same reply text"
        self.assertEqual(_normalize_response_text(left), _normalize_response_text(right))
        self.assertEqual(_hash_response_text(left), _hash_response_text(right))

    def test_generic_mode_requires_topical_continuity(self):
        bad = _is_low_quality_candidate(
            candidate="Completely unrelated answer about weather and cooking.",
            message="Need help writing a project update for my manager",
            recent_outputs=[],
            task_type="generic",
        )
        self.assertTrue(bad)

    def test_email_draft_allows_structural_shift_when_valid(self):
        candidate = (
            "Subject: Project Update\n\n"
            "Hi Maya,\n\n"
            "I wanted to share a quick update on the release timeline. "
            "We completed integration testing and addressed two blockers this week. "
            "I will send the final status report by Friday afternoon.\n\n"
            "Best regards,\n"
            "Vaishnav"
        )
        bad = _is_low_quality_candidate(
            candidate=candidate,
            message="draft an email update",
            recent_outputs=[],
            task_type="email_draft",
        )
        self.assertFalse(bad)

    def test_assistant_fallback_task_set_excludes_generic_qa(self):
        self.assertIn("email_draft", ASSISTANT_FALLBACK_TASK_TYPES)
        self.assertIn("planning", ASSISTANT_FALLBACK_TASK_TYPES)
        self.assertNotIn("generic", ASSISTANT_FALLBACK_TASK_TYPES)
        self.assertNotIn("qa", ASSISTANT_FALLBACK_TASK_TYPES)

    def test_recent_duplicate_helper_true_when_record_exists(self):
        db = _DummyAsyncDB(payload=object())
        is_dup = asyncio.run(_is_recent_duplicate(db, UUID("00000000-0000-0000-0000-000000000001"), "same answer"))
        self.assertTrue(is_dup)

    def test_recent_duplicate_helper_false_when_missing(self):
        db = _DummyAsyncDB(payload=None)
        is_dup = asyncio.run(_is_recent_duplicate(db, UUID("00000000-0000-0000-0000-000000000001"), "same answer"))
        self.assertFalse(is_dup)


if __name__ == "__main__":
    unittest.main()
