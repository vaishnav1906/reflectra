"""Importing your own texts: every export format is read correctly, only your own
messages are kept, and nothing private or unusable slips through."""

import json
import unittest

from app.services import voice_import_service as vi

IPHONE = """[12/03/24, 10:15:32 PM] Asha Rao: yo you up
[12/03/24, 10:15:40 PM] Vaish: yeah whats up
[12/03/24, 10:16:02 PM] Asha Rao: ‎image omitted
[12/03/24, 10:16:30 PM] Vaish: lmaooo no way
that is actually insane
[12/03/24, 10:17:01 PM] Vaish: send me the link https://example.com/x?y=1
[12/03/24, 10:17:20 PM] Asha Rao: call me on +91 98765 43210
[12/03/24, 10:18:00 PM] Vaish: ok
[13/03/24, 9:01:11 AM] Vaish: bro i overslept again fml
"""

ANDROID = """12/03/2024, 22:15 - Messages and calls are end-to-end encrypted. No one outside of this chat can read them.
12/03/2024, 22:15 - Asha Rao: yo you up
12/03/2024, 22:16 - Vaish: yeah whats up
12/03/2024, 22:16 - Vaish: <Media omitted>
12/03/2024, 22:17 - Asha Rao added Kiran
12/03/2024, 22:18 - Vaish: nah im not coming today
too tired fr
12/03/2024, 22:19 - Kiran: who is this
12/03/2024, 22:20 - Vaish: This message was deleted
"""


def many(prefix="msg", n=20):
    return "\n".join(f"12/03/2024, 22:{i:02d} - Vaish: {prefix} number {i} and some words\n12/03/2024, 22:{i:02d} - Asha: reply {i} from her" for i in range(n))


class Parsing(unittest.TestCase):
    def test_iphone_export_is_split_by_sender_with_multiline_messages(self):
        parsed = vi.parse_export(IPHONE)
        self.assertEqual(parsed.format, "whatsapp")
        self.assertEqual(set(parsed.senders), {"Asha Rao", "Vaish"})
        self.assertIn("lmaooo no way\nthat is actually insane", parsed.senders["Vaish"])
        self.assertEqual(len(parsed.senders["Vaish"]), 5)

    def test_android_export_skips_system_lines(self):
        parsed = vi.parse_export(ANDROID)
        self.assertEqual(set(parsed.senders), {"Asha Rao", "Vaish", "Kiran"})
        self.assertIn("nah im not coming today\ntoo tired fr", parsed.senders["Vaish"])
        self.assertNotIn("Messages and calls are end-to-end encrypted", " ".join(sum(parsed.senders.values(), [])))
        # "Asha Rao added Kiran" must not be glued onto the message before it
        self.assertFalse(any("added Kiran" in m for m in sum(parsed.senders.values(), [])))

    def test_chatgpt_export_keeps_only_what_the_user_typed(self):
        export = [
            {
                "title": "x",
                "mapping": {
                    "a": {"message": {"author": {"role": "system"}, "content": {"parts": ["You are ChatGPT"]}}},
                    "b": {"message": {"author": {"role": "user"}, "create_time": 2, "content": {"parts": ["second thing i asked"]}}},
                    "c": {"message": {"author": {"role": "assistant"}, "content": {"parts": ["Sure! Here is"]}}},
                    "d": {"message": {"author": {"role": "user"}, "create_time": 1, "content": {"parts": ["first thing i asked"]}}},
                    "e": {"message": None},
                },
            }
        ]
        parsed = vi.parse_export(json.dumps(export))
        self.assertEqual(parsed.format, "chatgpt")
        self.assertEqual(parsed.senders, {"You": ["first thing i asked", "second thing i asked"]})

    def test_telegram_export(self):
        export = {
            "name": "Asha",
            "messages": [
                {"type": "service", "from": "Asha", "text": "joined"},
                {"type": "message", "from": "Vaish", "text": "bro where are you"},
                {"type": "message", "from": "Asha", "text": ["on my way ", {"type": "link", "text": "maps.app/x"}]},
            ],
        }
        parsed = vi.parse_export(json.dumps(export))
        self.assertEqual(parsed.format, "telegram")
        self.assertEqual(parsed.senders["Vaish"], ["bro where are you"])
        self.assertEqual(parsed.senders["Asha"], ["on my way maps.app/x"])

    def test_plain_lines_count_as_your_own_messages(self):
        parsed = vi.parse_export("ngl that was wild\n\nidk what to do about it\n")
        self.assertEqual(parsed.format, "lines")
        self.assertEqual(parsed.senders, {"You": ["ngl that was wild", "idk what to do about it"]})

    def test_empty_upload_is_refused(self):
        with self.assertRaises(vi.VoiceImportError):
            vi.parse_export("   \n ")

    def test_garbage_json_falls_back_to_lines_instead_of_crashing(self):
        self.assertEqual(vi.parse_export('{"not": "a chat"}').format, "lines")
        self.assertEqual(vi.parse_export("[1, 2, 3]").format, "lines")


class Cleaning(unittest.TestCase):
    def test_media_deleted_and_system_stubs_are_dropped(self):
        for stub in ("<Media omitted>", "‎image omitted", "sticker omitted", "This message was deleted", "You deleted this message", "Missed voice call"):
            self.assertIsNone(vi.clean_message(stub), stub)

    def test_links_emails_and_phone_numbers_are_removed(self):
        self.assertEqual(vi.clean_message("send me the link https://example.com/x?y=1 pls"), "send me the link pls")
        self.assertEqual(vi.clean_message("mail it to sam.k@example.com ok bro"), "mail it to ok bro")
        self.assertEqual(vi.clean_message("call me on +91 98765 43210 tonight"), "call me on tonight")
        self.assertIsNone(vi.clean_message("https://example.com/only-a-link"))

    def test_one_word_replies_and_essays_are_dropped(self):
        self.assertIsNone(vi.clean_message("ok"))
        self.assertIsNone(vi.clean_message("word " * 100))
        self.assertIsNone(vi.clean_message("123 456"))
        self.assertEqual(vi.clean_message("  lmaooo   no way  "), "lmaooo no way")

    def test_selection_keeps_the_most_recent_distinct_messages_in_order(self):
        messages = [f"message number {i} here" for i in range(50)] + ["message number 49 here", "ok"]
        picked = vi.select_samples(messages, limit=10)
        self.assertEqual(len(picked), 10)
        self.assertEqual(picked[-1], "message number 49 here")
        self.assertEqual(picked[0], "message number 40 here")
        self.assertEqual(len(set(picked)), 10)


class Upload(unittest.TestCase):
    def test_other_peoples_messages_are_never_kept(self):
        result = vi.read_upload(many(), "Vaish", None)
        self.assertEqual(result["samples"], 20)
        self.assertTrue(all("from her" not in sample for sample in result["_samples"]))
        self.assertTrue(all(sample.startswith("msg number") for sample in result["_samples"]))

    def test_sender_is_guessed_from_the_account_name(self):
        self.assertEqual(vi.read_upload(many(), None, "vaish k")["sender"], "Vaish")
        self.assertEqual(vi.read_upload(many(), None, "Vaish")["sender"], "Vaish")

    def test_asks_who_you_are_when_it_cannot_tell(self):
        result = vi.read_upload(many(), None, "Somebody Else")
        self.assertTrue(result["needs_sender"])
        self.assertEqual({s["name"] for s in result["senders"]}, {"Vaish", "Asha"})
        self.assertNotIn("_samples", result)

    def test_a_sender_not_in_the_chat_is_not_trusted(self):
        self.assertTrue(vi.read_upload(many(), "Mallory", None)["needs_sender"])

    def test_too_little_to_learn_from_is_refused_with_a_reason(self):
        with self.assertRaises(vi.VoiceImportError) as caught:
            vi.read_upload(IPHONE, "Vaish", None)
        self.assertIn("at least", str(caught.exception))

    def test_summary_describes_the_voice(self):
        lines = "\n".join(f"bro this is lowercase line number {i} lol" for i in range(30))
        result = vi.read_upload(lines, None, None)
        self.assertEqual(result["format"], "lines")
        self.assertEqual(result["sender"], "You")
        self.assertIn("lowercase", result["description"])
        self.assertGreater(len(result["examples"]), 0)


class Blend(unittest.TestCase):
    def test_import_carries_mirror_only_while_little_is_written_here(self):
        self.assertEqual(vi.imported_share(0, 12), 8)
        self.assertEqual(vi.imported_share(20, 12), 6)
        self.assertEqual(vi.imported_share(300, 12), 4)


if __name__ == "__main__":
    unittest.main()
