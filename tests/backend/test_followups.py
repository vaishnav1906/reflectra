"""Follow-ups: what counts, when it may be asked about, and when it lapses."""

import json
import unittest
from datetime import date, datetime, timezone

from app.services import followup_service as fu


class Gate(unittest.TestCase):
    def test_intentions_in_slang_pass_the_gate(self):
        for text in (
            "ugh fine i'll text my landlord tomorrow",
            "ima finish chapter 3 tonight no cap",
            "gonna start gym from monday",
            "aight bet, booking the dentist this week",
            "i gotta call my mom after class",
        ):
            self.assertTrue(fu.looks_like_intention(text), text)

    def test_small_talk_does_not_call_the_model(self):
        for text in ("lol", "wassup gang", "that makes sense", "bro what", "i feel weird about it"):
            self.assertFalse(fu.looks_like_intention(text), text)

    def test_updates_are_recognised(self):
        self.assertTrue(fu.looks_like_update("finally texted him"))
        self.assertTrue(fu.looks_like_update("nah didn't go"))
        self.assertFalse(fu.looks_like_update("what even is this"))


class Parsing(unittest.TestCase):
    MESSAGE = "ugh fine i'll text my landlord about the rent tomorrow morning"

    def _raw(self, **commitment):
        return json.dumps({"commitment": commitment or None, "updates": []})

    def test_valid_commitment_is_kept(self):
        parsed = fu.parse_extraction(
            self._raw(
                what="text landlord about the rent",
                quote="i'll text my landlord about the rent tomorrow morning",
                days_until_due=1,
            ),
            self.MESSAGE,
        )
        self.assertEqual(parsed["commitment"]["what"], "text landlord about the rent")
        self.assertEqual(parsed["commitment"]["days_until_due"], 1)

    def test_invented_quote_is_rejected(self):
        parsed = fu.parse_extraction(
            self._raw(what="email the landlord", quote="I will email my landlord first thing", days_until_due=1),
            self.MESSAGE,
        )
        self.assertIsNone(parsed["commitment"])

    def test_due_date_is_bounded(self):
        parsed = fu.parse_extraction(
            self._raw(what="text landlord about rent", quote="i'll text my landlord", days_until_due=9999), self.MESSAGE
        )
        self.assertEqual(parsed["commitment"]["days_until_due"], fu.MAX_DUE_DAYS)

    def test_updates_must_point_at_a_real_open_item(self):
        raw = json.dumps(
            {
                "commitment": None,
                "updates": [
                    {"number": 1, "status": "done"},
                    {"number": 7, "status": "done"},
                    {"number": 2, "status": "maybe"},
                ],
            }
        )
        titles = ["text landlord about the late rent", "go to the gym"]
        said = "finally texted the landlord"
        self.assertEqual(fu.parse_extraction(raw, said, open_titles=titles)["updates"], [{"number": 1, "status": "done"}])
        self.assertEqual(fu.parse_extraction(raw, said, open_titles=[])["updates"], [])

    def test_an_update_must_actually_mention_the_item(self):
        raw = json.dumps({"commitment": None, "updates": [{"number": 1, "status": "done"}]})
        titles = ["text landlord about the late rent"]
        self.assertEqual(fu.parse_extraction(raw, "i already sent the assignment yesterday", open_titles=titles)["updates"], [])
        self.assertEqual(len(fu.parse_extraction(raw, "texted my landlord, done", open_titles=titles)["updates"]), 1)

    def test_same_thing_said_twice_is_one_commitment(self):
        self.assertTrue(fu.is_same_commitment("text landlord about the late rent", "text my landlord about rent"))
        self.assertFalse(fu.is_same_commitment("text landlord about the late rent", "finish chapter 3"))


class Timing(unittest.TestCase):
    TODAY = date(2026, 11, 17)

    def _state(self, **meta):
        return fu.due_state(meta, self.TODAY)

    def test_never_asked_before_it_is_due(self):
        self.assertFalse(self._state(date="2026-11-17", due="2026-11-18")["askable"])  # due tomorrow
        self.assertFalse(self._state(date="2026-11-16", due="2026-11-17")["askable"])  # due today: still has the day

    def test_asked_the_day_after_it_was_due(self):
        self.assertTrue(self._state(date="2026-11-15", due="2026-11-16")["askable"])

    def test_no_time_given_means_ask_from_two_days_on(self):
        self.assertFalse(self._state(date="2026-11-16")["askable"])
        self.assertTrue(self._state(date="2026-11-15")["askable"])

    def test_not_nagged(self):
        base = dict(date="2026-11-01", due="2026-11-02")
        self.assertFalse(self._state(**base, asked_at="2026-11-16", asked_count=1)["askable"])  # asked yesterday
        self.assertTrue(self._state(**base, asked_at="2026-11-13", asked_count=1)["askable"])  # second and last ask
        self.assertFalse(self._state(**base, asked_at="2026-11-05", asked_count=2)["askable"])  # twice: let it go

    def test_lapses_after_three_weeks(self):
        self.assertFalse(self._state(date="2026-10-28")["expired"])
        self.assertTrue(self._state(date="2026-10-20")["expired"])

    def test_local_date_follows_the_users_clock(self):
        late_utc = datetime(2026, 11, 17, 20, 0, tzinfo=timezone.utc)
        self.assertEqual(fu.local_today(330, late_utc), date(2026, 11, 18))  # already tomorrow in India
        self.assertEqual(fu.local_today(-480, late_utc), date(2026, 11, 17))

    def test_prompt_line_uses_their_words(self):
        line = fu.describe_for_prompt(
            "text landlord about rent",
            "i'll text my landlord tomorrow",
            self._state(date="2026-11-15", due="2026-11-16"),
        )
        self.assertIn("2 days ago", line)
        self.assertIn("i'll text my landlord tomorrow", line)


class PromptBlock(unittest.TestCase):
    def test_follow_ups_reach_the_reply_prompt_with_the_no_nagging_rule(self):
        from app.services.conversation_craft import MomentContext, format_moment_block

        block = format_moment_block(
            MomentContext(follow_ups=["yesterday they said they would text landlord (their words: \"i'll text him\")"])
        )
        self.assertIn("text landlord", block)
        self.assertIn("once", block)
        self.assertIn("drop it", block)
        self.assertNotIn("follow up", format_moment_block(MomentContext()))


if __name__ == "__main__":
    unittest.main()
