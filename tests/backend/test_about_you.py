"""About you: names, dates of birth and notification switches are checked."""

import unittest
from datetime import date

from app.services import notification_prefs as np
from app.services.conversation_craft import MomentContext, format_moment_block


class AboutYou(unittest.TestCase):
    TODAY = date(2026, 11, 17)

    def test_age_counts_whole_years(self):
        self.assertEqual(np.age_on(date(2004, 11, 18), self.TODAY), 21)  # birthday tomorrow
        self.assertEqual(np.age_on(date(2004, 11, 17), self.TODAY), 22)  # birthday today

    def test_birth_dates_are_checked(self):
        self.assertEqual(np.clean_birth_date("2004-03-14", self.TODAY), date(2004, 3, 14))
        self.assertIsNone(np.clean_birth_date("", self.TODAY))
        for bad in ("14/03/2004", "2030-01-01", "2020-01-01", "1890-01-01"):
            with self.assertRaises(np.ProfileError, msg=bad):
                np.clean_birth_date(bad, self.TODAY)

    def test_names_are_checked(self):
        self.assertEqual(np.clean_display_name("  Vaish   K "), "Vaish K")
        with self.assertRaises(np.ProfileError):
            np.clean_display_name("123")

    def test_notifications_are_off_until_turned_on(self):
        self.assertFalse(np.merged_prefs({})["enabled"])
        prefs = np.clean_prefs({"enabled": True, "check_in_time": "08:30"}, {})
        self.assertTrue(prefs["enabled"])
        self.assertEqual(prefs["check_in_time"], "08:30")
        self.assertTrue(prefs["weekly_digest"])  # untouched defaults survive

    def test_bad_notification_values_are_refused(self):
        for change in ({"enabled": "yes"}, {"check_in_time": "9pm"}, {"spam": True}):
            with self.assertRaises(np.ProfileError, msg=change):
                np.clean_prefs(change, {})

    def test_age_and_birthday_reach_the_reply_prompt(self):
        lines = np.about_lines(date(2004, 11, 17), self.TODAY)
        self.assertEqual(lines[0], "They're 22.")
        self.assertIn("birthday today", lines[1])
        block = format_moment_block(MomentContext(about=lines))
        self.assertIn("They're 22.", block)
        self.assertEqual(np.about_lines(None, self.TODAY), [])


if __name__ == "__main__":
    unittest.main()


class Colour(unittest.TestCase):
    def test_theme_is_checked_and_tidied(self):
        self.assertEqual(np.clean_theme({"hue": 370.4, "saturation": 64.6}), {"hue": 10, "saturation": 65})
        self.assertIsNone(np.clean_theme(None))
        for bad in ({"hue": "red"}, {"hue": 10, "saturation": 5}, {"saturation": 50}):
            with self.assertRaises(np.ProfileError, msg=bad):
                np.clean_theme(bad)
