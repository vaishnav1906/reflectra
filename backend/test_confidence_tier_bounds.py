#!/usr/bin/env python3
"""Deterministic tests for confidence tiers and context policy behavior."""

import asyncio
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import sys

backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from app.services.confidence_interval_service import controls_for_tier, tier_from_confidence_lower
from app.services.context_policy_service import apply_context_policy_gates, classify_response_context
from app.services.style_enforcement_service import enforce_style


class DummyResult:
    def scalar_one_or_none(self):
        return None


class DummyDB:
    async def execute(self, *_args, **_kwargs):
        return DummyResult()


class ConfidenceTierBoundaryTests(unittest.TestCase):
    def test_tier_boundaries_exact_ranges(self):
        cases = [
            (0.00, "very_low"),
            (0.20, "very_low"),
            (0.2001, "partial"),
            (0.50, "partial"),
            (0.5001, "moderate"),
            (0.75, "moderate"),
            (0.7501, "high"),
            (1.00, "high"),
        ]
        for lower, expected in cases:
            with self.subTest(lower=lower, expected=expected):
                self.assertEqual(tier_from_confidence_lower(lower), expected)

    def test_controls_monotonic_by_tier(self):
        very_low = controls_for_tier("very_low")
        partial = controls_for_tier("partial")
        moderate = controls_for_tier("moderate")
        high = controls_for_tier("high")

        self.assertLess(very_low["phrase_usage_frequency"], partial["phrase_usage_frequency"])
        self.assertLess(partial["phrase_usage_frequency"], moderate["phrase_usage_frequency"])
        self.assertLess(moderate["phrase_usage_frequency"], high["phrase_usage_frequency"])

        self.assertLess(very_low["tone_strength"], partial["tone_strength"])
        self.assertLess(partial["tone_strength"], moderate["tone_strength"])
        self.assertLess(moderate["tone_strength"], high["tone_strength"])

        self.assertTrue(very_low["include_uncertainty_note"])
        self.assertFalse(partial["include_uncertainty_note"])
        self.assertFalse(moderate["include_uncertainty_note"])
        self.assertFalse(high["include_uncertainty_note"])


class TierBehaviorOutputTests(unittest.TestCase):
    def _run_async(self, coro):
        return asyncio.run(coro)

    def test_very_low_includes_uncertainty_prefix(self):
        db = DummyDB()
        with patch("app.services.style_enforcement_service.random.random", return_value=1.0):
            result = self._run_async(
                enforce_style(
                    db=db,
                    user_id=uuid4(),
                    draft="I am not sure",
                    original_message="I am unsure",
                    phrase_usage_frequency=0.0,
                    tone_strength=0.2,
                    style_intensity=0.15,
                    reaction_threshold=0.85,
                    include_uncertainty_note=True,
                    professional_context=False,
                    allow_slang=False,
                    allow_imperfect_grammar=False,
                )
            )
        self.assertIn("This might not fully match your style yet", result.text)

    def test_partial_does_not_include_uncertainty_prefix(self):
        db = DummyDB()
        with patch("app.services.style_enforcement_service.random.random", return_value=1.0):
            result = self._run_async(
                enforce_style(
                    db=db,
                    user_id=uuid4(),
                    draft="I am not sure",
                    original_message="idk maybe",
                    phrase_usage_frequency=0.0,
                    tone_strength=0.4,
                    style_intensity=0.35,
                    reaction_threshold=0.7,
                    include_uncertainty_note=False,
                    professional_context=False,
                    allow_slang=True,
                    allow_imperfect_grammar=True,
                )
            )
        self.assertNotIn("This might not fully match your style yet", result.text)

    def test_moderate_applies_style_rewrites(self):
        db = DummyDB()
        with patch("app.services.style_enforcement_service.random.random", return_value=0.0):
            result = self._run_async(
                enforce_style(
                    db=db,
                    user_id=uuid4(),
                    draft="I am not sure. This seems incorrect.",
                    original_message="this feels weird",
                    phrase_usage_frequency=0.0,
                    tone_strength=0.65,
                    style_intensity=0.6,
                    reaction_threshold=0.55,
                    include_uncertainty_note=False,
                    professional_context=False,
                    allow_slang=True,
                    allow_imperfect_grammar=True,
                )
            )
        self.assertIn("idk man", result.text.lower())

    def test_high_professional_context_cleans_slang(self):
        db = DummyDB()
        with patch("app.services.style_enforcement_service.random.random", return_value=0.0):
            result = self._run_async(
                enforce_style(
                    db=db,
                    user_id=uuid4(),
                    draft="idk man this feels off tbh bro",
                    original_message="Please draft a formal message",
                    phrase_usage_frequency=0.8,
                    tone_strength=0.85,
                    style_intensity=0.85,
                    reaction_threshold=0.4,
                    include_uncertainty_note=False,
                    professional_context=True,
                    allow_slang=False,
                    allow_imperfect_grammar=False,
                )
            )
        self.assertNotIn("idk", result.text.lower())
        self.assertNotIn("bro", result.text.lower())


class ContextPolicyTests(unittest.TestCase):
    def test_context_classifier_detects_professional(self):
        self.assertEqual(classify_response_context("Subject: Follow-up regarding proposal", None), "professional")
        self.assertEqual(classify_response_context("Please draft an email", "email_draft"), "professional")

    def test_context_classifier_detects_casual(self):
        self.assertEqual(classify_response_context("idk bro this is kinda weird", None), "casual")

    def test_professional_policy_is_stricter(self):
        decision = apply_context_policy_gates(
            context_mode="professional",
            phrase_usage_frequency=0.8,
            tone_strength=0.85,
            style_enforcement_intensity=0.85,
            confidence_tier="moderate",
        )
        self.assertLessEqual(decision.phrase_usage_frequency, 0.08)
        self.assertLessEqual(decision.tone_strength, 0.55)
        self.assertLessEqual(decision.style_enforcement_intensity, 0.35)
        self.assertFalse(decision.allow_imperfect_grammar)


if __name__ == "__main__":
    unittest.main()
