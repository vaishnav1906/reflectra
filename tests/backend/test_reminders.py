"""Reminders: when one goes out, and when it must not."""

import unittest
from datetime import datetime, time

from app.services import reminders as r
from app.services.notification_prefs import merged_prefs


def prefs(**overrides):
    return {**merged_prefs({"enabled": True, "daily_check_in": True}), **overrides}


def nudges():
    return [
        r.Nudge("check_in", "2026-11-17", "Got a minute?", None, "/app/chat"),
        r.Nudge("follow_up", "f1", "A quick question.", "Last time you said you'd go to the gym. How did it go?", "/app/chat"),
        r.Nudge("weekly_digest", "2026-W47", "Your week.", None, "/app/week"),
        r.Nudge("birthday", "p1:2026", "Someone has a birthday tomorrow.", "Jay's birthday is tomorrow.", "/app/chat"),
    ]


TUESDAY_NOON = datetime(2026, 11, 17, 12, 0)
SUNDAY_7PM = datetime(2026, 11, 22, 19, 0)


class Choose(unittest.TestCase):
    def test_nothing_while_switched_off(self):
        self.assertIsNone(r.choose(nudges(), prefs(enabled=False), TUESDAY_NOON, 0, set()))

    def test_birthdays_come_first_then_follow_ups(self):
        self.assertEqual(r.choose(nudges(), prefs(), TUESDAY_NOON, 0, set()).kind, "birthday")
        self.assertEqual(r.choose(nudges(), prefs(birthdays=False), TUESDAY_NOON, 0, set()).kind, "follow_up")

    def test_at_most_one_a_day(self):
        self.assertIsNone(r.choose(nudges(), prefs(), TUESDAY_NOON, 1, set()))

    def test_never_the_same_thing_twice(self):
        already = {("birthday", "p1:2026"), ("follow_up", "f1")}
        self.assertIsNone(r.choose(nudges(), prefs(daily_check_in=False), TUESDAY_NOON, 0, already))

    def test_quiet_hours_wrap_past_midnight(self):
        self.assertTrue(r.in_quiet_hours(time(23, 30), time(22, 30), time(8, 0)))
        self.assertTrue(r.in_quiet_hours(time(7, 59), time(22, 30), time(8, 0)))
        self.assertFalse(r.in_quiet_hours(time(8, 0), time(22, 30), time(8, 0)))
        self.assertTrue(r.in_quiet_hours(time(13, 0), time(12, 0), time(14, 0)))
        late = datetime(2026, 11, 17, 23, 0)
        self.assertIsNone(r.choose(nudges(), prefs(check_in_time="23:00"), late, 0, set()))

    def test_follow_ups_and_birthdays_wait_for_daytime(self):
        early = datetime(2026, 11, 17, 9, 0)
        self.assertIsNone(r.choose(nudges(), prefs(quiet_end="07:00", daily_check_in=False), early, 0, set()))

    def test_weekly_digest_only_on_sunday_evening(self):
        only_digest = prefs(birthdays=False, follow_ups=False, daily_check_in=False)
        self.assertIsNone(r.choose(nudges(), only_digest, TUESDAY_NOON, 0, set()))
        self.assertEqual(r.choose(nudges(), only_digest, SUNDAY_7PM, 0, set()).kind, "weekly_digest")

    def test_check_in_at_the_chosen_time_with_some_grace(self):
        only_check_in = prefs(birthdays=False, follow_ups=False, weekly_digest=False, check_in_time="12:00")
        self.assertEqual(r.choose(nudges(), only_check_in, TUESDAY_NOON, 0, set()).kind, "check_in")
        self.assertEqual(r.choose(nudges(), only_check_in, datetime(2026, 11, 17, 12, 40), 0, set()).kind, "check_in")
        self.assertIsNone(r.choose(nudges(), only_check_in, datetime(2026, 11, 17, 13, 0), 0, set()))
        self.assertIsNone(r.choose(nudges(), only_check_in, datetime(2026, 11, 17, 11, 59), 0, set()))

    def test_lock_screen_text_never_carries_what_they_said(self):
        for nudge in nudges():
            self.assertNotIn("gym", nudge.body)
            self.assertNotIn("Jay", nudge.body)


class Keys(unittest.TestCase):
    def test_vapid_keys_have_the_right_shape(self):
        import base64
        import os
        from unittest.mock import patch

        from app.services import push_service

        with patch.dict(os.environ, {"VAPID_PUBLIC_KEY": "", "VAPID_PRIVATE_KEY": ""}), patch.object(push_service, "_keys", None), \
                patch.object(push_service, "KEY_FILE", push_service.KEY_FILE.with_name(".vapid.test.json")):
            try:
                public, private = push_service.vapid_keys()
                raw_public = base64.urlsafe_b64decode(public + "==")
                raw_private = base64.urlsafe_b64decode(private + "==")
                self.assertEqual(len(raw_public), 65)  # uncompressed P-256 point
                self.assertEqual(raw_public[0], 4)
                self.assertEqual(len(raw_private), 32)
            finally:
                push_service.KEY_FILE.with_name(".vapid.test.json").unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
