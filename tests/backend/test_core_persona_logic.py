#!/usr/bin/env python3
"""Tests for the core persona-learning fixes: bounded trait updates, confidence
fusion over available sources, user-grounded style enforcement, reaction openers,
per-message metrics and conversation-scoped mirror archetype selection."""

import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.api.chat import get_adaptive_mirror_style  # noqa: E402
from app.services.behavioral_memory_service import extract_reaction_opener, reaction_confidence  # noqa: E402
from app.services.confidence_interval_service import fuse_source_scores, tier_from_confidence_lower  # noqa: E402
from app.services.message_signals import compute_message_metrics, derive_fallback_traits, simple_sentiment  # noqa: E402
from app.services.persona_update_service import compute_trait_update  # noqa: E402
from app.services.style_enforcement_service import build_user_style_profile, enforce_style  # noqa: E402

SOURCES = ["conversations", "traits", "timeline_reflections", "reflection_summaries", "external_inputs"]


class TraitUpdateTests(unittest.TestCase):
    def test_single_message_moves_at_most_strength_fraction(self):
        new_score, _ = compute_trait_update(0.5, 0.1, signal=1.0, strength=0.2)
        self.assertLessEqual(new_score - 0.5, 0.2 * 0.5 + 1e-9)
        self.assertGreater(new_score, 0.5)

    def test_strength_is_capped(self):
        capped, _ = compute_trait_update(0.5, 0.1, signal=1.0, strength=5.0)
        at_cap, _ = compute_trait_update(0.5, 0.1, signal=1.0, strength=0.2)
        self.assertAlmostEqual(capped, at_cap)

    def test_consistent_evidence_builds_confidence(self):
        score, confidence = 0.5, 0.1
        for _ in range(30):
            score, confidence = compute_trait_update(score, confidence, signal=0.8, strength=0.15)
        self.assertGreater(confidence, 0.6)
        self.assertAlmostEqual(score, 0.8, delta=0.05)

    def test_contradicting_signal_lowers_confidence(self):
        _, confidence = compute_trait_update(0.8, 0.7, signal=0.1, strength=0.2)
        self.assertLess(confidence, 0.7)

    def test_high_confidence_resists_change(self):
        low_conf_score, _ = compute_trait_update(0.5, 0.1, signal=1.0, strength=0.2)
        high_conf_score, _ = compute_trait_update(0.5, 0.9, signal=1.0, strength=0.2)
        self.assertLess(high_conf_score, low_conf_score)


class ConfidenceFusionTests(unittest.TestCase):
    def _tier(self, scores):
        result = fuse_source_scores({source: scores.get(source) for source in SOURCES})
        return tier_from_confidence_lower(result["lower"]), result

    def test_no_data_is_very_low(self):
        tier, result = self._tier({})
        self.assertEqual(tier, "very_low")
        self.assertEqual(result["center"], 0.0)

    def test_unused_sources_do_not_cap_confidence(self):
        tier, _ = self._tier(
            {"conversations": 0.9, "traits": 0.85, "timeline_reflections": 0.9, "reflection_summaries": 0.9}
        )
        self.assertEqual(tier, "high")

    def test_sparse_evidence_stays_conservative(self):
        tier, _ = self._tier({"conversations": 0.15, "traits": 0.3})
        self.assertEqual(tier, "very_low")


class _SequenceResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _SequenceDB:
    """Returns the queued values for successive execute() calls, then None."""

    def __init__(self, *values):
        self._values = list(values)

    async def execute(self, *_args, **_kwargs):
        return _SequenceResult(self._values.pop(0) if self._values else None)

    async def rollback(self):
        return None


def _fingerprint(abbreviations=None, emoji_messages=0, emoji_counts=None, samples=10):
    return SimpleNamespace(
        abbreviation_stats=abbreviations or {},
        sentence_patterns={"emoji_messages": emoji_messages, "emoji_counts": emoji_counts or {}},
        sample_count=samples,
    )


class StyleEnforcementGroundingTests(unittest.TestCase):
    def _enforce(self, db, draft):
        return asyncio.run(
            enforce_style(
                db=db,
                user_id=uuid4(),
                draft=draft,
                original_message="I'm not sure what to do about this",
                phrase_usage_frequency=1.0,
                tone_strength=1.0,
                style_intensity=1.0,
                reaction_threshold=0.4,
                include_uncertainty_note=True,
                professional_context=False,
            )
        )

    def test_no_fingerprint_means_no_invented_slang_or_emoji(self):
        with patch("app.services.style_enforcement_service.random.random", return_value=0.0):
            result = self._enforce(_SequenceDB(None, None), "I don't know what to do yet.")
        self.assertEqual(result.text, "I don't know what to do yet.")

    def test_user_abbreviations_and_emojis_are_reused(self):
        fingerprint = _fingerprint(abbreviations={"idk": 4}, emoji_messages=8, emoji_counts={"😅": 6})
        with patch("app.services.style_enforcement_service.random.random", return_value=0.0):
            result = self._enforce(_SequenceDB(fingerprint, None), "I don't know what to do yet.")
        self.assertIn("idk", result.text)
        self.assertTrue(result.text.endswith("😅"))

    def test_rarely_used_abbreviation_is_not_reused(self):
        profile = build_user_style_profile(_fingerprint(abbreviations={"tbh": 1}))
        self.assertNotIn("tbh", profile.abbreviations)

    def test_user_reaction_opener_is_used_as_prefix(self):
        pattern = SimpleNamespace(response_template="idk man", confidence=0.8)
        with patch("app.services.style_enforcement_service.random.random", return_value=0.0):
            result = self._enforce(_SequenceDB(None, pattern), "I need to pick one path.")
        self.assertTrue(result.text.startswith("idk man,"))
        self.assertEqual(result.reaction_match_score, 0.8)


class ReactionOpenerTests(unittest.TestCase):
    def test_extracts_short_leading_clause(self):
        self.assertEqual(extract_reaction_opener("idk man, this week was rough"), "idk man")
        self.assertEqual(extract_reaction_opener("Honestly. I need sleep"), "honestly")

    def test_ignores_long_first_clause(self):
        self.assertIsNone(extract_reaction_opener("I have been thinking about this all day long"))

    def test_confidence_grows_with_repetition(self):
        values = [reaction_confidence(n) for n in range(1, 7)]
        self.assertEqual(values, sorted(values))
        self.assertLess(values[0], 0.4)
        self.assertGreater(values[-1], 0.85)


class MessageSignalTests(unittest.TestCase):
    def test_metrics_prefer_llm_nudges(self):
        metrics = compute_message_metrics(
            "why do I keep doing this",
            [{"name": "reflection_depth", "signal": 0.9, "strength": 0.2}],
        )
        self.assertEqual(metrics["reflection_depth"], 0.9)
        self.assertEqual(metrics["token_count"], 6)
        self.assertIsNotNone(metrics["emotional_intensity"])

    def test_sentiment_sign(self):
        self.assertGreater(simple_sentiment("I feel great and proud today"), 0)
        self.assertLess(simple_sentiment("so stressed and tired"), 0)
        self.assertEqual(simple_sentiment("the meeting is at noon"), 0.0)

    def test_fallback_traits_always_include_communication_style(self):
        names = {trait["name"] for trait in derive_fallback_traits("ok")}
        self.assertIn("communication_style", names)


class AdaptiveMirrorStyleTests(unittest.TestCase):
    def test_established_emotion_holds_for_one_turn(self):
        stressed = "I'm so stressed and overwhelmed"
        style, emotion = get_adaptive_mirror_style("lol that's funny", {}, [stressed, stressed])
        self.assertEqual(emotion, "playful")
        self.assertEqual(style, "calm")

    def test_no_history_uses_current_emotion(self):
        style, emotion = get_adaptive_mirror_style("lol that's funny", {}, [])
        self.assertEqual((style, emotion), ("chaotic", "playful"))


if __name__ == "__main__":
    unittest.main()
