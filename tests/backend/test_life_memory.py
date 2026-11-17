"""Life memory: what gets kept, how it changes, and what replies are told."""

import json
import unittest
from datetime import date
from types import SimpleNamespace

from app.services import life_memory_service as lm
from app.services.conversation_craft import MomentContext, format_moment_block


def fact(statement, kind="situation", last_seen="2026-11-10", status="active", pinned=False, mentions=1):
    return SimpleNamespace(statement=statement, kind=kind, last_seen=last_seen, status=status, pinned=pinned, mention_count=mentions)


class Extraction(unittest.TestCase):
    MESSAGE = "exams are finally over!! now i just need to find an internship before january"

    def test_new_facts_need_exact_words_and_a_known_kind(self):
        raw = json.dumps({"new": [
            {"kind": "goal", "text": "Find an internship before January", "quote": "now i just need to find an internship before january"},
            {"kind": "goal", "text": "Become a doctor", "quote": "i want to be a doctor"},
            {"kind": "mood", "text": "Relieved", "quote": "exams are finally over"},
        ], "updates": []})
        new, _ = lm.parse_extraction(raw, self.MESSAGE, [])
        self.assertEqual([n["text"] for n in new], ["Find an internship before January"])

    def test_updates_point_at_real_facts(self):
        exams = fact("Has exams in the first week of December")
        raw = json.dumps({"new": [], "updates": [{"number": 1, "status": "resolved"}, {"number": 5, "status": "resolved"}, {"number": 1, "status": "maybe"}]})
        _, updates = lm.parse_extraction(raw, self.MESSAGE, [exams])
        self.assertEqual(updates, [(exams, "resolved")])

    def test_text_is_tidied(self):
        self.assertEqual(lm.clean_text("they lives in a hostel in pune."), "Lives in a hostel in pune")
        with self.assertRaises(lm.LifeMemoryError):
            lm.clean_text("   ")

    def test_same_fact_in_other_words(self):
        self.assertTrue(lm.is_same_fact("Lives in a hostel in Pune", "Lives in the Pune hostel"))
        self.assertFalse(lm.is_same_fact("Lives in a hostel in Pune", "Wants to study in Germany"))


class Summary(unittest.TestCase):
    TODAY = date(2026, 11, 17)

    def test_only_active_and_recent_facts_reach_replies_pinned_first(self):
        facts = [
            fact("Has exams coming up", status="resolved"),
            fact("Used to play football", kind="about", last_seen="2025-01-01"),
            fact("Final-year engineering student", kind="about", pinned=True, last_seen="2025-01-01"),
            fact("Job hunting", last_seen="2026-11-16", mentions=4),
        ]
        lines = lm.summary_lines(facts, self.TODAY)
        self.assertEqual(lines[0], "About you: Final-year engineering student")  # pinned survives staleness
        self.assertIn("Going on now: Job hunting", lines)
        self.assertNotIn("Going on now: Has exams coming up", lines)
        self.assertFalse(any("football" in line for line in lines))

    def test_facts_about_what_they_are_saying_rank_higher(self):
        facts = [fact("Learning guitar", kind="goal", last_seen="2026-11-16"), fact("Hates mornings", kind="preference", last_seen="2026-11-16")]
        lines = lm.summary_lines(facts, self.TODAY, query="ugh mornings are the worst", limit=1)
        self.assertEqual(lines, ["Likes and dislikes: Hates mornings"])

    def test_summary_reaches_the_reply_prompt(self):
        block = format_moment_block(MomentContext(life=["Going on now: Job hunting"]))
        self.assertIn("What you know about their life", block)
        self.assertIn("Job hunting", block)


if __name__ == "__main__":
    unittest.main()
