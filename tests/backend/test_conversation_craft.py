#!/usr/bin/env python3
"""Tests for the human-feel helpers: reply sizing, cleanup, voice matching and prompts."""

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from collections import Counter  # noqa: E402

from app.api.chat import build_reflection_system_prompt, validate_reflection_response  # noqa: E402
from app.services.conversation_craft import (  # noqa: E402
    MomentContext,
    _gap_note,
    apply_voice_surface,
    clean_reply,
    describe_voice,
    has_assistant_tells,
    reply_budget,
    voice_stats,
)


class ReplyBudgetTests(unittest.TestCase):
    def test_short_message_gets_short_reply(self):
        self.assertLess(reply_budget("hey", "reflection")["max_tokens"], reply_budget(" ".join(["word"] * 60), "reflection")["max_tokens"])
        self.assertIn("short", str(reply_budget("hey", "reflection")["hint"]).lower())


class CleanupTests(unittest.TestCase):
    def test_strips_markdown_but_keeps_sentences(self):
        text = "## Observed Pattern:\n**You** keep waiting for permission. Why wait? What's the cost?"
        cleaned = validate_reflection_response(text, {})
        self.assertNotIn("#", cleaned)
        self.assertNotIn("**", cleaned)
        self.assertNotIn("Observed Pattern", cleaned)
        # Questions are no longer rewritten into periods.
        self.assertIn("Why wait? What's the cost?", cleaned)

    def test_detects_chatbot_phrases(self):
        self.assertTrue(has_assistant_tells("It sounds like you're overwhelmed."))
        self.assertFalse(has_assistant_tells("ugh, three deadlines in one week is brutal."))

    def test_clean_reply_drops_speaker_label(self):
        self.assertEqual(clean_reply("Reflectra: hey you"), "hey you")

    def test_clean_reply_removes_machine_punctuation(self):
        self.assertEqual(
            clean_reply("That is a lot of effort; you can rest now — seriously."),
            "That is a lot of effort. You can rest now, seriously.",
        )

    def test_fake_familiarity_counts_as_a_tell(self):
        self.assertTrue(has_assistant_tells("I know how much you've been dreading the review."))

    def test_drafts_get_proper_capitalization(self):
        from app.services.mirror_engine import _tidy_draft_capitalization

        self.assertEqual(
            _tidy_draft_capitalization("hi, rent will be late. sorry, ill pay by [date]. i appreciate it"),
            "Hi, rent will be late. Sorry, I'll pay by [date]. I appreciate it",
        )


class VoiceMatchingTests(unittest.TestCase):
    samples = [
        "ngl today was a lot",
        "ok but why does this keep happening",
        "idk man i just want to sleep",
        "lowkey proud of myself tho",
        "yeah that makes sense",
    ]

    def test_stats_capture_lowercase_and_no_final_punctuation(self):
        stats = voice_stats(self.samples)
        self.assertEqual(stats.lowercase_ratio, 1.0)
        self.assertEqual(stats.no_end_punct_ratio, 1.0)
        self.assertEqual(stats.emoji_ratio, 0.0)
        self.assertIn("lowercase", describe_voice(stats))

    def test_surface_matches_user_habits(self):
        stats = voice_stats(self.samples)
        self.assertEqual(apply_voice_surface("Honestly? Just Start It Tonight.", stats), "honestly? just start it tonight")

    def test_surface_leaves_text_alone_without_enough_samples(self):
        stats = voice_stats(self.samples[:2])
        self.assertEqual(apply_voice_surface("Start Tonight.", stats), "Start Tonight.")


class ReflectionPromptTests(unittest.TestCase):
    def test_prompt_carries_moment_and_memory(self):
        moment = MomentContext(
            display_name="Vaishnav",
            local_time="Sunday 1:57 AM",
            gap_note="Last time you talked was 3 days ago.",
            earlier_shares=["my exam is on monday and i haven't started physics"],
        )
        profile = {"themes": Counter({"work": 2}), "values": Counter(), "stressors": Counter({"pressure": 1})}
        prompt = build_reflection_system_prompt(profile, None, moment, "Keep it short.")
        self.assertIn("Their name is Vaishnav", prompt)
        self.assertIn("Sunday 1:57 AM", prompt)
        self.assertIn("3 days ago", prompt)
        self.assertIn("haven't started physics", prompt)
        self.assertIn("Recurring stressors: pressure", prompt)
        self.assertIn("For this reply: Keep it short.", prompt)
        self.assertIn("crisis", prompt)  # safety guidance stays in

    def test_gap_notes(self):
        self.assertIsNone(_gap_note(datetime.now(timezone.utc) - timedelta(minutes=10)))
        self.assertIn("yesterday", _gap_note(datetime.now(timezone.utc) - timedelta(hours=30)))
        self.assertIn("first time", _gap_note(None))


if __name__ == "__main__":
    unittest.main()
