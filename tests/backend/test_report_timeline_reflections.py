#!/usr/bin/env python3
"""Tests for the PDF report renderer, reflection validation and timeline helpers."""

import json
import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.persona_report_service import (  # noqa: E402
    ReportData,
    TraitReading,
    adaptation_lines,
    headline,
    pdf_safe,
    printable,
    render_report,
)
from app.services.reflection_service import validate_reflections  # noqa: E402
from app.services.timeline_service import _longest_streak, trait_milestones  # noqa: E402

TRAITS = [
    TraitReading("communication_style", 0.37, 0.65, 133),
    TraitReading("emotional_expressiveness", 0.74, 0.67, 95),
    TraitReading("decision_framing", 0.43, 0.51, 81),
    TraitReading("reflection_depth", 0.72, 0.66, 64),
]


class ReportTests(unittest.TestCase):
    def _data(self, **overrides):
        base = dict(
            name="Vaish",
            generated_at=datetime(2026, 11, 16, tzinfo=timezone.utc),
            first_date="2026-03-29",
            last_date="2026-11-16",
            active_days=14,
            user_messages=350,
            conversations=51,
            longest_streak=3,
            busiest_day={"date": "2026-04-14", "user_messages": 66},
            traits=TRAITS,
            trait_series=[
                {"date": "2026-03-29", "communication_style": 0.25, "emotional_expressiveness": 0.5, "decision_framing": 0.5, "reflection_depth": 0.5},
                {"date": "2026-04-14", "communication_style": 0.4, "emotional_expressiveness": 0.7, "decision_framing": 0.42, "reflection_depth": 0.72},
            ],
            milestones=[{"date": "2026-03-29", "kind": "start", "text": "Your first conversation in this period."}],
            reflections=[
                {
                    "title": "You reach for your phone when work gets hard",
                    "insight": "When a task pushes back you look for an exit, and the phone is the nearest one.",
                    "theme": "habits",
                    "confidence": 0.7,
                    "evidence": [
                        {"quote": "I usually switch to something easier like my phone", "date": "2026-04-14"},
                        {"quote": "नमस्ते दुनिया", "date": "2026-04-18"},
                    ],
                }
            ],
            reflections_read=160,
            hour_histogram=[0] * 18 + [40] + [0] * 5,
            weekday_histogram=[5, 9, 1, 2, 4, 7, 6],
            voice={"messages": 350, "median_words": 9, "longest_words": 80, "lowercase_share": 0.41, "question_share": 0.21, "emoji_share": 0.0, "no_period_share": 0.6, "abbreviations": [("idk", 4)], "phrases": ["hell yeah"]},
        )
        base.update(overrides)
        return ReportData(**base)

    def test_renders_a_multi_page_pdf(self):
        pdf = render_report(self._data())
        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertGreaterEqual(pdf.count(b"/Type /Page\n") + pdf.count(b"/Type /Page "), 1)
        self.assertGreater(len(pdf), 8000)

    def test_renders_for_a_brand_new_user(self):
        empty = ReportData(name="You", generated_at=datetime(2026, 11, 16, tzinfo=timezone.utc))
        self.assertTrue(render_report(empty).startswith(b"%PDF-"))

    def test_headline_uses_the_most_distinctive_traits(self):
        self.assertEqual(headline(TRAITS), "Open about feelings, and digs for the why.")
        self.assertEqual(headline([]), "Still getting to know you.")

    def test_adaptation_follows_traits_and_voice(self):
        lines = adaptation_lines(TRAITS, {"messages": 350, "emoji_share": 0.0, "lowercase_share": 0.8})
        self.assertIn("Keeps its replies short, because you do.", lines)
        self.assertIn("In Mirror mode it writes in lowercase, the way you do.", lines)
        self.assertIn("It leaves emojis out, since you don't use them.", lines)

    def test_text_outside_the_font_is_handled(self):
        self.assertEqual(pdf_safe("it’s fine — really"), "it's fine , really")
        self.assertFalse(printable("नमस्ते"))
        self.assertTrue(printable("ek second mai band kar dunga"))


class ReflectionValidationTests(unittest.TestCase):
    def setUp(self):
        self.messages = [
            {"index": 1, "content": "When I feel resistance towards work, I usually switch to something easier like my phone.", "created_at": datetime(2026, 4, 14, tzinfo=timezone.utc), "conversation_id": "a"},
            {"index": 2, "content": "I think I've trained myself to escape discomfort instead of pushing through it.", "created_at": datetime(2026, 4, 15, tzinfo=timezone.utc), "conversation_id": "b"},
            {"index": 3, "content": "what should I eat before hitting the gym today", "created_at": datetime(2026, 4, 16, tzinfo=timezone.utc), "conversation_id": "c"},
        ]

    def _raw(self, quotes, title="You escape discomfort through your phone"):
        return json.dumps({"reflections": [{
            "title": title,
            "insight": "When work pushes back you look for the nearest exit, and you have noticed it yourself.",
            "theme": "habits",
            "quotes": quotes,
        }]})

    def test_keeps_a_pattern_with_two_real_quotes(self):
        kept = validate_reflections(self._raw([
            {"id": 1, "text": "I usually switch to something easier like my phone"},
            {"id": 2, "text": "trained myself to escape discomfort"},
        ]), self.messages)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["confidence"], 0.7)  # two different days
        self.assertEqual([e["date"] for e in kept[0]["evidence"]], ["2026-04-14", "2026-04-15"])

    def test_wrong_message_id_is_recovered_by_search(self):
        kept = validate_reflections(self._raw([
            {"id": 3, "text": "I usually switch to something easier like my phone"},
            {"id": 3, "text": "trained myself to escape discomfort"},
        ]), self.messages)
        self.assertEqual(len(kept), 1)

    def test_drops_a_pattern_with_invented_quotes(self):
        kept = validate_reflections(self._raw([
            {"id": 1, "text": "I usually switch to something easier like my phone"},
            {"id": 2, "text": "I always procrastinate on everything in my whole life"},
        ]), self.messages)
        self.assertEqual(kept, [])

    def test_two_quotes_from_the_same_message_are_one_occasion(self):
        kept = validate_reflections(self._raw([
            {"id": 1, "text": "When I feel resistance towards work"},
            {"id": 1, "text": "switch to something easier like my phone"},
        ]), self.messages)
        self.assertEqual(kept, [])


class TimelineHelperTests(unittest.TestCase):
    def test_longest_streak(self):
        days = [date(2026, 4, 5), date(2026, 4, 6), date(2026, 4, 7), date(2026, 4, 9), date(2026, 4, 10)]
        self.assertEqual(_longest_streak(days), 3)
        self.assertEqual(_longest_streak([]), 0)

    def test_trait_milestone_only_when_it_stays_on_that_side(self):
        series = [
            {"date": "2026-03-29", "reflection_depth": 0.2},   # early swing, does not last
            {"date": "2026-04-05", "reflection_depth": 0.5},
            {"date": "2026-04-14", "reflection_depth": 0.7},
            {"date": "2026-04-21", "reflection_depth": 0.72},
        ]
        milestones = trait_milestones(series)
        self.assertEqual(len(milestones), 1)
        self.assertEqual(milestones[0]["date"], "2026-04-14")
        self.assertIn("deep side", milestones[0]["text"])

    def test_no_milestone_for_a_trait_that_ends_in_the_middle(self):
        series = [{"date": "2026-03-29", "decision_framing": 0.2}, {"date": "2026-04-05", "decision_framing": 0.45}]
        self.assertEqual(trait_milestones(series), [])


if __name__ == "__main__":
    unittest.main()
