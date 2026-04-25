#!/usr/bin/env python3
"""Unit tests for strict 4-trait Mirror Mode behavior."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.services.mirror_engine import (  # noqa: E402
    _is_low_quality_candidate,
    analyze_message_style,
    build_mirror_system_prompt,
    extract_key_traits,
)


class MirrorModeBehaviorTests(unittest.TestCase):
    def test_message_style_detects_slang_and_questions(self):
        style = analyze_message_style("yeah tbh this is wild... what should i do?")

        self.assertTrue(style["has_slang"])
        self.assertTrue(style["has_questions"])
        self.assertGreater(style["avg_sentence_length"], 2)

    def test_extract_key_traits_uses_core_trait_keys(self):
        persona_vector = {
            "behavioral_profile": {
                "communication_style": {"score": 0.77, "confidence": 0.64},
                "emotional_expressiveness": {"score": 0.22, "confidence": 0.75},
                "decision_framing": {"score": 0.81, "confidence": 0.66},
                "reflection_depth": {"score": 0.69, "confidence": 0.72},
            }
        }

        traits = extract_key_traits(persona_vector)

        self.assertEqual(set(traits.keys()), {
            "communication_style",
            "emotional_expressiveness",
            "decision_framing",
            "reflection_depth",
        })
        self.assertAlmostEqual(traits["communication_style"], 0.77)
        self.assertAlmostEqual(traits["emotional_expressiveness"], 0.22)

    def test_extract_key_traits_ignores_low_confidence_updates(self):
        persona_vector = {
            "behavioral_profile": {
                "communication_style": {"score": 0.9, "confidence": 0.05},
                "reflection_depth": {"score": 0.1, "confidence": 0.1},
            }
        }

        traits = extract_key_traits(persona_vector)

        self.assertAlmostEqual(traits["communication_style"], 0.5)
        self.assertAlmostEqual(traits["reflection_depth"], 0.5)

    def test_prompt_includes_four_trait_contract(self):
        prompt = build_mirror_system_prompt(
            sampled_profile={
                "communication_style": 0.72,
                "emotional_expressiveness": 0.31,
                "decision_framing": 0.75,
                "reflection_depth": 0.82,
            },
            stability_index=0.66,
            message_style={
                "avg_sentence_length": 11.0,
                "punctuation_intensity": 1,
                "has_slang": False,
                "emotional_markers": 1,
                "caps_intensity": 0.0,
                "has_questions": False,
            },
            task_type="generic",
            confidence_tier="moderate",
            detected_emotion="neutral",
            active_mirror_style="calm",
        )

        self.assertIn("Communication Style (Concise", prompt)
        self.assertIn("Emotional Expressiveness (Reserved", prompt)
        self.assertIn("Decision Framing (Hesitant", prompt)
        self.assertIn("Reflection Depth (Surface", prompt)
        self.assertIn("Keep mirror interpretation active even for task routes", prompt)
        self.assertIn("Continue the same thought thread", prompt)
        self.assertIn("Stay in first person", prompt)
        self.assertIn("Allow light starters", prompt)

    def test_quality_filter_allows_concise_when_profile_is_concise(self):
        is_low_quality = _is_low_quality_candidate(
            candidate="I need to do this now.",
            message="I need a quick response here about the meeting.",
            recent_outputs=[],
            task_type="generic",
            sampled_profile={"response_detail_target": "concise"},
        )

        self.assertFalse(is_low_quality)

    def test_quality_filter_rejects_generic_fillers(self):
        is_low_quality = _is_low_quality_candidate(
            candidate="ok",
            message="Can you help me decide what to send?",
            recent_outputs=[],
            task_type="generic",
            sampled_profile={"response_detail_target": "balanced"},
        )

        self.assertTrue(is_low_quality)

    def test_quality_filter_rejects_external_second_person_prompts(self):
        question_candidate = _is_low_quality_candidate(
            candidate="Should you do this now?",
            message="I need to settle this today.",
            recent_outputs=[],
            task_type="generic",
            sampled_profile={"response_detail_target": "balanced"},
        )

        second_person_candidate = _is_low_quality_candidate(
            candidate="You should move now.",
            message="I need to settle this today.",
            recent_outputs=[],
            task_type="generic",
            sampled_profile={"response_detail_target": "balanced"},
        )

        self_question_candidate = _is_low_quality_candidate(
            candidate="I'm still circling this, but why does this same pattern keep repeating?",
            message="I keep repeating this loop.",
            recent_outputs=[],
            task_type="generic",
            sampled_profile={"response_detail_target": "balanced"},
        )

        self.assertTrue(question_candidate)
        self.assertTrue(second_person_candidate)
        self.assertFalse(self_question_candidate)


if __name__ == "__main__":
    unittest.main()
