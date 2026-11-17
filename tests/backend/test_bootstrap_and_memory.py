#!/usr/bin/env python3
"""Tests for Persona Bootstrap validation/merging and for conversation memory recall."""

import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.api.chat import resolve_mirror_task_type  # noqa: E402
from app.services.conversation_craft import rank_memories  # noqa: E402
from app.services.persona_bootstrap_service import (  # noqa: E402
    BootstrapInputError,
    TraitReading,
    merge_trait,
    parse_bootstrap_response,
    validate_summary,
    verify_quote,
)

SUMMARY = (
    "This user is extremely brief. Messages are usually one line. They almost never talk about how they feel. "
    "They make decisions fast and rarely second-guess."
)


def _response(traits, kind="description", notes=None):
    return json.dumps({"kind": kind, "traits": traits, "notes": notes or []})


class QuoteVerificationTests(unittest.TestCase):
    def test_real_quote_passes_ignoring_case_and_spacing(self):
        self.assertTrue(verify_quote("messages are   usually ONE line", SUMMARY))

    def test_invented_quote_fails(self):
        self.assertFalse(verify_quote("writes long detailed essays", SUMMARY))


class ParseTests(unittest.TestCase):
    def test_unverified_evidence_is_dropped(self):
        raw = _response({
            "communication_style": {"score": 0.1, "strength": "strong", "evidence": "This user is extremely brief."},
            "emotional_expressiveness": {"score": 0.9, "strength": "strong", "evidence": "cries at every movie"},
            "decision_framing": {"score": None, "strength": "none", "evidence": ""},
            "reflection_depth": {"score": 0.5, "strength": "weak", "evidence": ""},
        })
        readings, _ = parse_bootstrap_response(raw, SUMMARY)
        by_trait = {r.trait: r for r in readings}
        self.assertEqual(by_trait["communication_style"].score, 0.1)
        self.assertIsNone(by_trait["emotional_expressiveness"].score)  # quote not in the text
        self.assertIsNone(by_trait["decision_framing"].score)
        self.assertIsNone(by_trait["reflection_depth"].score)  # no evidence given

    def test_unrelated_text_learns_nothing(self):
        raw = _response(
            {"communication_style": {"score": 0.2, "strength": "strong", "evidence": "This user is extremely brief."}},
            kind="other",
            notes=["Likes pasta a lot"],
        )
        readings, notes = parse_bootstrap_response(raw, SUMMARY)
        self.assertTrue(all(r.score is None for r in readings))
        self.assertEqual(notes, [])

    def test_writing_sample_is_capped_at_weak(self):
        raw = _response(
            {"communication_style": {"score": 0.2, "strength": "strong", "evidence": "Messages are usually one line."}},
            kind="own_writing",
        )
        readings, _ = parse_bootstrap_response(raw, SUMMARY)
        self.assertEqual({r.trait: r for r in readings}["communication_style"].strength, "weak")

    def test_json_wrapped_in_code_fence_is_read(self):
        raw = "```json\n" + _response({}) + "\n```"
        readings, _ = parse_bootstrap_response(raw, SUMMARY)
        self.assertEqual(len(readings), 4)


class MergeTests(unittest.TestCase):
    reading = TraitReading("communication_style", 0.1, "strong", "This user is extremely brief.", True)

    def test_unobserved_trait_takes_imported_score(self):
        change = merge_trait(0.5, 0.1, 0, self.reading)
        self.assertTrue(change.applied)
        self.assertAlmostEqual(change.new_score, 0.1)
        self.assertLess(change.new_confidence, 0.6)  # hearsay never beats observed behaviour

    def test_existing_learning_is_blended_not_overwritten(self):
        change = merge_trait(0.8, 0.7, 40, self.reading)
        self.assertLess(change.new_score, 0.8)
        self.assertGreater(change.new_score, 0.6)  # 40 real messages outweigh a description worth 12
        self.assertLess(change.new_confidence, 0.7)  # disagreement lowers confidence

    def test_description_pull_shrinks_as_real_evidence_grows(self):
        moves = [0.8 - merge_trait(0.8, 0.7, n, self.reading).new_score for n in (2, 12, 60, 300)]
        self.assertEqual(moves, sorted(moves, reverse=True))
        self.assertGreater(moves[0], 0.55)  # new user: the description decides
        self.assertAlmostEqual(moves[1], 0.35, places=2)  # 12 messages vs worth 12: meets halfway
        self.assertLess(moves[3], 0.03)  # 300 messages: barely a nudge

    def test_weaker_claims_pull_less(self):
        strong = merge_trait(0.8, 0.7, 20, self.reading)
        weak = merge_trait(0.8, 0.7, 20, TraitReading("communication_style", 0.1, "weak", "x", True))
        self.assertLess(strong.new_score, weak.new_score)

    def test_thin_profile_gains_confidence_from_an_agreeing_description(self):
        change = merge_trait(0.15, 0.1, 2, self.reading)
        self.assertGreater(change.new_confidence, 0.4)

    def test_established_profile_keeps_its_confidence(self):
        change = merge_trait(0.12, 0.8, 200, self.reading)
        self.assertGreaterEqual(change.new_confidence, 0.8)
        self.assertLess(change.new_confidence, 0.82)

    def test_no_evidence_changes_nothing(self):
        change = merge_trait(0.8, 0.7, 40, TraitReading("decision_framing", None, "none", "", False))
        self.assertFalse(change.applied)
        self.assertEqual((change.new_score, change.new_confidence), (0.8, 0.7))


class ValidationTests(unittest.TestCase):
    def test_too_short_is_rejected(self):
        with self.assertRaises(BootstrapInputError):
            validate_summary("I am a quiet person.")


class MemoryRecallTests(unittest.TestCase):
    def setUp(self):
        now = datetime.now(timezone.utc)
        self.exchanges = [
            {"user": "I keep grabbing my phone the moment work gets hard", "assistant": "Try the 5-minute rule: just start.", "created_at": now - timedelta(days=200), "conversation_id": "a"},
            {"user": "what should I eat before hitting the gym", "assistant": "A banana with peanut butter works.", "created_at": now - timedelta(days=190), "conversation_id": "b"},
            {"user": "the weather is so hot today I can't think", "assistant": "Brutal. Drink water.", "created_at": now - timedelta(days=180), "conversation_id": "c"},
            {"user": "my presentation is tomorrow and I have stage fear", "assistant": "Nerves mean you care.", "created_at": now - timedelta(days=170), "conversation_id": "d"},
        ] + [
            {"user": f"random chat number {i} about nothing in particular", "assistant": "ok", "created_at": now - timedelta(days=100 - i), "conversation_id": f"x{i}"}
            for i in range(30)
        ]

    def test_recalls_the_related_conversation(self):
        top = rank_memories("bruh sat down to work and was on my phone in two minutes again", self.exchanges)
        self.assertTrue(top)
        self.assertIn("phone", top[0]["user"])

    def test_gym_question_recalls_gym_chat(self):
        top = rank_memories("thinking of hitting the gym later, what do i eat", self.exchanges)
        self.assertIn("gym", top[0]["user"])

    def test_greeting_recalls_nothing(self):
        self.assertEqual(rank_memories("wassup gang", self.exchanges), [])


class SlangTaskDetectionTests(unittest.TestCase):
    def test_slang_openers_still_count_as_requests(self):
        self.assertEqual(resolve_mirror_task_type("aight write a text to my boy jay telling him im not pulling up tn", []), "message_draft")
        self.assertEqual(resolve_mirror_task_type("yo can u draft an email to my prof", []), "email_draft")

    def test_statements_are_not_requests(self):
        self.assertIsNone(resolve_mirror_task_type("i have to text my landlord about rent", []))
        self.assertIsNone(resolve_mirror_task_type("bro i need to write my thesis", []))


if __name__ == "__main__":
    unittest.main()


class HybridRecallTests(unittest.TestCase):
    """Meaning-based recall, with made-up similarities standing in for the embedding API."""

    def setUp(self):
        now = datetime.now(timezone.utc)
        self.gym = {"id": "gym", "embedded": True, "user": "what should I have before hitting the gym", "assistant": "A banana with peanut butter.", "created_at": now - timedelta(days=200), "conversation_id": "a"}
        self.hello = {"id": "hello", "embedded": True, "user": "Hello, how are you? What's good with you today", "assistant": "What's up with you?", "created_at": now - timedelta(days=190), "conversation_id": "b"}
        self.finals = {"id": "finals", "embedded": True, "user": "these last days of the semester kill me a lot", "assistant": "Semester-end is a sprint.", "created_at": now - timedelta(days=180), "conversation_id": "c"}
        self.old = {"id": "old", "embedded": False, "user": "my workout plan needs more fuel honestly", "assistant": "Eat more.", "created_at": now - timedelta(days=300), "conversation_id": "d"}
        self.exchanges = [self.gym, self.hello, self.finals, self.old] + [
            {"id": f"x{i}", "embedded": True, "user": f"random chat number {i} about nothing in particular", "assistant": "ok", "created_at": now - timedelta(days=100 - i), "conversation_id": f"x{i}"}
            for i in range(30)
        ]

    @staticmethod
    def _match(similarity, standout):
        return {"similarity": similarity, "standout": standout}

    def test_meaning_finds_what_keywords_cannot(self):
        query = "should i eat something before i go lift"
        self.assertEqual(rank_memories(query, self.exchanges), [])  # no words in common
        found = rank_memories(query, self.exchanges, similarities={"gym": self._match(0.71, 7.0)})
        self.assertEqual([e["id"] for e in found], ["gym"])

    def test_close_but_not_standing_out_is_not_recalled(self):
        # Everything this person says is a bit similar; 0.64 at +1.2 is just their baseline.
        found = rank_memories("finals are killing me", self.exchanges, similarities={"finals": self._match(0.64, 1.2)})
        self.assertEqual(found, [])

    def test_standing_out_but_not_close_is_not_recalled(self):
        found = rank_memories("finals are killing me", self.exchanges, similarities={"finals": self._match(0.55, 4.0)})
        self.assertEqual(found, [])

    def test_keyword_coincidence_is_dropped_when_meaning_disagrees(self):
        query = "what's good fuel before a workout today"
        similarities = {"gym": self._match(0.75, 7.7), "hello": self._match(0.41, -0.8)}
        ids = [e["id"] for e in rank_memories(query, self.exchanges, similarities=similarities)]
        self.assertIn("gym", ids)
        self.assertNotIn("hello", ids)

    def test_keyword_match_without_a_vector_is_kept(self):
        # Older messages may not be embedded yet; keywords still count for them.
        ids = [e["id"] for e in rank_memories("need better fuel for my workout plan", self.exchanges, similarities={"gym": self._match(0.7, 6.0)})]
        self.assertIn("old", ids)
        self.assertIn("gym", ids)

    def test_found_by_both_ranks_first(self):
        query = "what do i eat before hitting the gym"
        similarities = {"gym": self._match(0.8, 8.0), "finals": self._match(0.7, 3.0)}
        ids = [e["id"] for e in rank_memories(query, self.exchanges, similarities=similarities)]
        self.assertEqual(ids[0], "gym")
        self.assertIn("finals", ids)

    def test_greetings_never_trigger_recall(self):
        self.assertEqual(rank_memories("hey", self.exchanges, similarities={"gym": self._match(0.9, 9.0)}), [])

    def test_filler_words_are_not_keywords(self):
        from app.services.conversation_craft import _memory_tokens

        self.assertEqual(_memory_tokens("what's up, i keep getting kinda stressed tonight"), ["stress"])
        self.assertEqual(_memory_tokens("stopping planned"), ["stop", "plan"])
