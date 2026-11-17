"""People: who a message is about, what replies are told, and what gets remembered."""

import json
import unittest
import uuid
from datetime import date
from types import SimpleNamespace

from app.services import people_service as ps
from app.services.conversation_craft import MomentContext, format_moment_block


def person(name, relationship=None, aliases=(), description=None, notes=None, birthday=None):
    return SimpleNamespace(
        id=uuid.uuid4(), name=name, relationship_label=relationship, aliases=list(aliases),
        description=description, notes=list(notes or []), birthday=birthday,
    )


class Mentions(unittest.TestCase):
    def setUp(self):
        self.kev = person("Kev", "roommate", ["Kevin"])
        self.jay = person("Jay Shah", "best friend")
        self.asha = person("Asha", "mom")
        self.will = person("Will", "coworker")
        self.riya = person("Riya", "sister")
        self.people = [self.kev, self.jay, self.asha, self.will, self.riya]

    def names(self, text):
        return [p.name for p in ps.find_mentions(text, self.people)]

    def test_names_nicknames_and_possessives_in_slang(self):
        self.assertEqual(self.names("nah bro the function at kev's tn"), ["Kev"])
        self.assertEqual(self.names("Kevin ate my food again"), ["Kev"])
        self.assertEqual(self.names("gonna text jay later"), ["Jay Shah"])  # first name alone

    def test_family_roles_find_the_one_person_with_that_role(self):
        self.assertEqual(self.names("my mom keeps calling lol"), ["Asha"])
        self.assertEqual(self.names("mum said no"), ["Asha"])
        self.assertEqual(self.names("my roommate ate my food"), ["Kev"])

    def test_a_role_shared_by_two_people_is_not_guessed(self):
        people = self.people + [person("Meera", "sister")]
        self.assertEqual([p.name for p in ps.find_mentions("my sister called", people)], [])

    def test_names_that_are_words_need_a_capital(self):
        self.assertEqual(self.names("i will text him"), [])
        self.assertEqual(self.names("Will is so annoying at work"), ["Will"])

    def test_general_words_are_not_people(self):
        self.assertEqual(self.names("he is like a brother to me"), [])
        self.assertEqual(self.names("bro idk"), [])
        self.assertEqual(self.names("kevlar vest lol"), [])  # no partial words

    def test_order_follows_the_message(self):
        self.assertEqual(self.names("riya and kev are coming"), ["Riya", "Kev"])


class Briefings(unittest.TestCase):
    def test_briefing_has_role_their_words_latest_notes_and_birthday(self):
        jay = person(
            "Jay", "best friend", description="chill, always late, would do anything for me",
            notes=[
                {"text": "Moving to Pune next month", "date": "2026-11-10"},
                {"text": "Had a fight over the trip", "date": "2026-11-15"},
                {"text": "Old note", "date": "2026-01-01"},
                {"text": "Oldest note", "date": "2025-01-01"},
            ],
            birthday="11-20",
        )
        text = ps.briefing(jay, today=date(2026, 11, 17))
        self.assertIn("Jay (best friend)", text)
        self.assertIn("always late", text)
        self.assertLess(text.index("fight"), text.index("Pune"))  # newest first
        self.assertNotIn("Oldest note", text)  # only the latest three
        self.assertIn("birthday is in 3 days", text)

    def test_birthday_only_mentioned_within_a_week(self):
        self.assertIsNone(ps.birthday_note("12-25", today=date(2026, 11, 17)))
        self.assertEqual(ps.birthday_note("2001-11-17", today=date(2026, 11, 17)), "It's their birthday today.")
        self.assertEqual(ps.birthday_note("01-02", today=date(2026, 12, 30)), "Their birthday is in 3 days.")

    def test_briefings_reach_the_reply_prompt_with_the_fairness_rule(self):
        block = format_moment_block(MomentContext(people=["Jay (best friend); in their words: always late"]))
        self.assertIn("Jay (best friend)", block)
        self.assertIn("don't judge", block)


class Notes(unittest.TestCase):
    def test_repeats_are_not_added_twice(self):
        jay = person("Jay")
        self.assertTrue(ps.add_note(jay, "Moving to Pune next month", "he's moving to pune", "2026-11-17", None))
        self.assertFalse(ps.add_note(jay, "Jay is moving to Pune next month", None, "2026-11-18", None))
        self.assertEqual(len(jay.notes), 1)
        self.assertEqual(jay.notes[0]["source"], "chat")

    def test_notes_are_capped(self):
        jay = person("Jay")
        for i in range(ps.MAX_NOTES + 10):
            ps.add_note(jay, f"alpha{i} bravo{i} charlie{i}", None, "2026-11-17", None)
        self.assertEqual(len(jay.notes), ps.MAX_NOTES)


class Extraction(unittest.TestCase):
    MESSAGE = "my roommate kev is moving out next month and ngl im kinda sad about it"

    def test_facts_need_their_exact_words(self):
        raw = json.dumps({"people": [
            {"name": "Kev", "known": None, "relationship": "roommate", "fact": "Moving out next month", "quote": "kev is moving out next month"},
            {"name": "Sam", "known": None, "relationship": None, "fact": "Is his boss", "quote": "Sam is his boss"},
        ]})
        found = ps.parse_extraction(raw, self.MESSAGE, [])
        self.assertEqual(found[0]["fact"], "Moving out next month")
        self.assertIsNone(found[1]["fact"])  # quote not in the message: fact dropped

    def test_known_people_are_matched_by_number_and_bad_numbers_ignored(self):
        kev = person("Kev")
        raw = json.dumps({"people": [{"name": "Kev", "known": 1}, {"name": "X", "known": 9}]})
        found = ps.parse_extraction(raw, self.MESSAGE, [kev])
        self.assertIs(found[0]["person"], kev)
        self.assertIsNone(found[1]["person"])

    def test_gate_skips_messages_without_people(self):
        self.assertFalse(ps.looks_like_people_talk("ngl today was mid"))
        self.assertTrue(ps.looks_like_people_talk("went out with Kev and the boys"))
        self.assertTrue(ps.looks_like_people_talk("my roommate ate my food again"))


class Inputs(unittest.TestCase):
    def test_names_and_birthdays_are_checked(self):
        with self.assertRaises(ps.PeopleError):
            ps.clean_name("   ")
        with self.assertRaises(ps.PeopleError):
            ps.clean_birthday("next tuesday")
        self.assertEqual(ps.clean_birthday("03-14"), "03-14")
        self.assertEqual(ps.clean_birthday("2001-03-14"), "2001-03-14")

    def test_aliases_drop_duplicates_and_the_name_itself(self):
        self.assertEqual(ps.clean_aliases(["kev", "Kevin", "kevin ", "K"], "Kev"), ["Kevin", "K"])

    def test_groups(self):
        self.assertEqual(ps.group_of("mom"), "family")
        self.assertEqual(ps.group_of("best friend"), "friends")
        self.assertEqual(ps.group_of("my manager"), "work")
        self.assertEqual(ps.group_of("girlfriend"), "partner")
        self.assertEqual(ps.group_of(None), "other")


if __name__ == "__main__":
    unittest.main()
