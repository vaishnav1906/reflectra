"""Corrections: what each kind of feedback is allowed to change, and by how much."""

import unittest

from app.services import feedback_service as fb
from app.services.conversation_craft import MomentContext, format_moment_block
from app.services.reflection_service import feedback_instructions


class TraitCorrections(unittest.TestCase):
    def test_agreeing_makes_it_more_sure_but_never_certain(self):
        score, confidence = fb.apply_trait_agreement(0.37, 0.65)
        self.assertEqual(score, 0.37)
        self.assertAlmostEqual(confidence, 0.65 + 0.15 * 0.35)
        for _ in range(100):
            score, confidence = fb.apply_trait_agreement(score, confidence)
        self.assertLessEqual(confidence, 0.98)

    def test_your_own_view_decides_while_little_is_known(self):
        score, confidence = fb.apply_self_rating(0.5, 0.2, evidence_count=3, self_score=0.1)
        self.assertLess(score, 0.2)  # 15 vs 3: mostly your call
        self.assertLess(confidence, 0.2)  # and it knows it was off

    def test_your_own_view_nudges_once_much_is_known(self):
        score, confidence = fb.apply_self_rating(0.37, 0.65, evidence_count=133, self_score=0.1)
        self.assertAlmostEqual(score, 0.37 - 0.27 * 15 / 148, places=6)  # about 3 points
        self.assertLess(confidence, 0.65 * 0.75)  # 27 points off: noticeably less sure

    def test_the_further_off_the_less_sure(self):
        _, near = fb.apply_self_rating(0.5, 0.7, 100, 0.3)
        _, far = fb.apply_self_rating(0.5, 0.7, 100, 0.0)
        self.assertLess(far, near)
        self.assertGreaterEqual(far, 0.7 * 0.4)  # never wiped out by one rating

    def test_a_rating_close_to_the_reading_counts_as_agreeing(self):
        score, confidence = fb.apply_self_rating(0.5, 0.6, 100, 0.58)
        self.assertGreater(confidence, 0.6)
        self.assertGreater(score, 0.5)
        self.assertLess(score, 0.52)


class ReplyGuidance(unittest.TestCase):
    def test_most_mentioned_reasons_come_first_and_at_most_three(self):
        lines = fb.guidance_from_reasons(
            [["too_long"], ["too_long", "too_preachy"], ["missed_point"], ["unrelated"], ["too_long"]], "reflection"
        )
        self.assertEqual(len(lines), 3)
        self.assertIn("shorter", lines[0])

    def test_reasons_only_apply_to_their_own_mode(self):
        self.assertEqual(fb.guidance_from_reasons([["not_my_voice"]], "reflection"), [])
        self.assertIn("didn't sound like them", fb.guidance_from_reasons([["not_my_voice"]], "mirror")[0])

    def test_unknown_reasons_are_dropped(self):
        self.assertEqual(fb.clean_reasons(["too_long", "<script>", "not_my_voice"], "reflection"), ["too_long"])

    def test_every_reason_has_a_label_and_an_instruction(self):
        for mode, reasons in fb.REASONS_BY_MODE.items():
            for reason in reasons:
                self.assertTrue(fb.REPLY_REASONS[reason]["label"], (mode, reason))
                self.assertTrue(fb.REPLY_REASONS[reason]["line"], (mode, reason))

    def test_guidance_reaches_the_reply_prompt(self):
        block = format_moment_block(MomentContext(reply_feedback=[fb.REPLY_REASONS["too_long"]["line"]]))
        self.assertIn("rated some of your recent replies", block)
        self.assertIn("shorter", block)
        self.assertNotIn("rated", format_moment_block(MomentContext()))


class ReflectionRewrites(unittest.TestCase):
    def test_rejected_and_confirmed_patterns_reach_the_rewrite(self):
        text = feedback_instructions(
            {"rejected": ['"You avoid conflict" (they said: it is my boss, not me)'], "confirmed": ["You reach for your phone"]}
        )
        self.assertIn("were wrong about them", text)
        self.assertIn("it is my boss, not me", text)
        self.assertIn("spot on", text)
        self.assertIn("You reach for your phone", text)

    def test_nothing_rated_adds_nothing(self):
        self.assertEqual(feedback_instructions({"rejected": [], "confirmed": []}), "")


if __name__ == "__main__":
    unittest.main()
