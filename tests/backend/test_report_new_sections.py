"""The PDF covers the newer features: Your life, People, your corrections and your colour."""

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.persona_report_service import (  # noqa: E402
    ReportData,
    TraitReading,
    feedback_adaptation,
    order_life_facts,
    palette_for,
    render_report,
)
from app.services.persona_report_service import DEFAULT_PALETTE, _luminance  # noqa: E402

TRAITS = [
    TraitReading("communication_style", 0.37, 0.65, 133),
    TraitReading("emotional_expressiveness", 0.74, 0.67, 95),
    TraitReading("decision_framing", 0.43, 0.51, 81),
    TraitReading("reflection_depth", 0.72, 0.66, 64),
]


def full_report(**overrides) -> ReportData:
    data = dict(
        name="Vaish",
        generated_at=datetime(2026, 11, 17, tzinfo=timezone.utc),
        first_date="2026-03-29",
        last_date="2026-11-17",
        active_days=15,
        user_messages=351,
        conversations=52,
        traits=TRAITS,
        voice={"messages": 351, "median_words": 9, "lowercase_share": 0.41, "question_share": 0.2, "emoji_share": 0.0},
        trait_feedback={"communication_style": {"verdict": "agree"}, "decision_framing": {"verdict": "disagree", "self_score": 0.6}},
        feedback={
            "replies": {"reflection": {"up": 4, "down": 2}, "mirror": {"up": 1, "down": 0}},
            "reasons": [{"reason": "too_long", "label": "Too long", "count": 2}],
            "traits": {"agree": 1, "disagree": 1},
            "reflections": {"agree": 1, "disagree": 0},
        },
        life_facts=[
            {"kind": "about", "text": "Final-year engineering student in Pune", "quote": "im in my final year of engg", "pinned": True},
            {"kind": "goal", "text": "Wants to get an internship before March", "quote": None, "pinned": False},
            {"kind": "situation", "text": "Has exams in December", "quote": "exams start dec 5", "pinned": False},
        ],
        loose_ends=[{"what": "Go to the gym tomorrow morning", "due": "2026-11-18"}],
        people=[
            {"name": "Riya", "relationship": "best friend", "description": "Always honest with me, even when it stings.", "mention_count": 7, "last_mentioned_at": "2026-11-16T10:00:00+00:00"},
            {"name": "Mom", "relationship": "mother", "description": "", "notes": [{"text": "Worries when I skip meals"}], "mention_count": 3},
        ],
        voice_import={"samples": 420, "format": "whatsapp"},
        theme={"hue": 150, "saturation": 60},
    )
    data.update(overrides)
    return ReportData(**data)


class NewSectionsTests(unittest.TestCase):
    def test_full_report_renders_with_the_new_sections(self):
        pdf = render_report(full_report())
        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertGreaterEqual(pdf.count(b"/Type /Page\n") + pdf.count(b"/Type /Page "), 6)

    def test_new_user_with_nothing_in_the_new_sections_still_renders(self):
        empty = ReportData(name="You", generated_at=datetime(2026, 11, 17, tzinfo=timezone.utc))
        self.assertTrue(render_report(empty).startswith(b"%PDF-"))

    def test_lots_of_people_and_facts_spill_onto_more_pages(self):
        facts = [{"kind": "about", "text": f"Fact number {i} about a long and winding life story", "pinned": False} for i in range(30)]
        people = [{"name": f"Person {i}", "relationship": "friend", "description": "Kind. " * 30, "mention_count": i} for i in range(14)]
        self.assertTrue(render_report(full_report(life_facts=facts, people=people)).startswith(b"%PDF-"))

    def test_pinned_facts_come_first_then_the_most_mentioned(self):
        ordered = order_life_facts([
            {"text": "a", "pinned": False, "mention_count": 1},
            {"text": "b", "pinned": False, "mention_count": 5},
            {"text": "c", "pinned": True, "mention_count": 0},
        ])
        self.assertEqual([f["text"] for f in ordered], ["c", "b", "a"])

    def test_thumbs_down_reasons_become_plain_lines_for_the_reader(self):
        lines = feedback_adaptation({"reasons": [{"reason": "too_long"}, {"reason": "nonsense"}, {"reason": "too_preachy"}]})
        self.assertEqual(len(lines), 2)
        self.assertIn("shorter", lines[0])
        self.assertEqual(feedback_adaptation({}), [])


class PaletteTests(unittest.TestCase):
    def test_default_colours_when_no_theme_or_the_default_one(self):
        self.assertIs(palette_for(None), DEFAULT_PALETTE)
        self.assertIs(palette_for({"hue": 252, "saturation": 92}), DEFAULT_PALETTE)

    def test_a_theme_moves_the_colours_with_it(self):
        forest = palette_for({"hue": 150, "saturation": 60})
        self.assertNotEqual(forest.violet.hexval(), DEFAULT_PALETTE.violet.hexval())
        self.assertGreater(forest.violet.green, forest.violet.blue)  # green, not violet

    def test_pale_themes_are_darkened_enough_to_read_on_paper(self):
        for hue in range(0, 360, 15):
            colour = palette_for({"hue": hue, "saturation": 100}).violet
            self.assertLessEqual(_luminance(colour), 0.25, f"hue {hue} too pale")


if __name__ == "__main__":
    unittest.main()
