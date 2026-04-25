#!/usr/bin/env python3
"""Unit tests for mirror realism validator trait and continuity scoring."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.services.realism_validator import score_mirror_candidate  # noqa: E402


class MirrorRealismValidatorTests(unittest.TestCase):
    def test_decisive_profile_penalizes_hedging(self):
        profile = {
            "communication_style": 0.6,
            "emotional_expressiveness": 0.5,
            "decision_framing": 0.85,
            "reflection_depth": 0.5,
            "reasoning_visibility": "low",
            "structure_preference": "loose",
        }

        hedged_score = score_mirror_candidate(
            candidate="maybe we should probably wait and see.",
            sampled_profile=profile,
            recent_outputs=[],
            source_message="Should I send this now?",
        )
        decisive_score = score_mirror_candidate(
            candidate="Send it now and keep it clear.",
            sampled_profile=profile,
            recent_outputs=[],
            source_message="Should I send this now?",
        )

        self.assertLess(hedged_score, decisive_score)

    def test_continuity_penalizes_unrelated_response(self):
        profile = {
            "communication_style": 0.6,
            "emotional_expressiveness": 0.5,
            "decision_framing": 0.5,
            "reflection_depth": 0.5,
            "reasoning_visibility": "low",
            "structure_preference": "loose",
        }

        unrelated = score_mirror_candidate(
            candidate="let me know if you need anything else",
            sampled_profile=profile,
            recent_outputs=[],
            source_message="I need to finalize the budget deck before tomorrow's leadership review.",
        )
        related = score_mirror_candidate(
            candidate="Lock the budget deck tonight so tomorrow's leadership review is clean.",
            sampled_profile=profile,
            recent_outputs=[],
            source_message="I need to finalize the budget deck before tomorrow's leadership review.",
        )

        self.assertLess(unrelated, related)

    def test_generic_filler_is_heavily_penalized(self):
        profile = {
            "communication_style": 0.5,
            "emotional_expressiveness": 0.5,
            "decision_framing": 0.5,
            "reflection_depth": 0.5,
            "reasoning_visibility": "low",
            "structure_preference": "loose",
        }

        score = score_mirror_candidate(
            candidate="ok",
            sampled_profile=profile,
            recent_outputs=[],
            source_message="How do I phrase this message to my manager?",
        )

        self.assertLess(score, 0.5)

    def test_external_second_person_is_penalized_more_than_self_flow(self):
        profile = {
            "communication_style": 0.5,
            "emotional_expressiveness": 0.5,
            "decision_framing": 0.5,
            "reflection_depth": 0.5,
            "reasoning_visibility": "low",
            "structure_preference": "loose",
        }

        monologue_score = score_mirror_candidate(
            candidate="I can see the pattern now and the move is clear.",
            sampled_profile=profile,
            recent_outputs=[],
            source_message="I keep delaying the same decision.",
        )
        question_score = score_mirror_candidate(
            candidate="Should you just do it now?",
            sampled_profile=profile,
            recent_outputs=[],
            source_message="I keep delaying the same decision.",
        )

        self_flow_score = score_mirror_candidate(
            candidate="I'm still circling this, but the direction is finally getting clearer.",
            sampled_profile=profile,
            recent_outputs=[],
            source_message="I keep delaying the same decision.",
        )

        self.assertLess(question_score, monologue_score)
        self.assertGreater(self_flow_score, question_score)


if __name__ == "__main__":
    unittest.main()
