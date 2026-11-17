"""Is the confidence Reflectra reports actually right?

Two layers are checked:
  1. per-trait confidence (compute_trait_update), by simulating people whose true
     trait and consistency are known and checking the number tracks reality;
  2. overall confidence and its range (confidence_interval_service), by the rules
     it promises: evidence only helps, imports never hurt, thin or conflicting
     evidence widens the range, and every level is reachable.
"""

import random
import statistics
import unittest

from app.services.confidence_interval_service import (
    MAX_HALF_WIDTH,
    MIN_HALF_WIDTH,
    SOURCE_WEIGHTS,
    build_result,
    freshness,
    fuse_source_scores,
    score_conversations,
    score_reflections,
    score_traits,
    score_voice,
    tier_from_confidence_lower,
)
from app.services.persona_update_service import compute_trait_update


def simulate(true_value: float, noise: float, messages: int, seed: int):
    """A person whose messages show `true_value` plus random day-to-day noise."""
    rng = random.Random(seed)
    score, confidence = 0.5, 0.1
    for _ in range(messages):
        signal = min(1.0, max(0.0, rng.gauss(true_value, noise)))
        score, confidence = compute_trait_update(score, confidence, signal, rng.uniform(0.10, 0.18))
    return score, confidence


def population(noise: float, messages: int = 150, people: int = 60):
    rng = random.Random(int(noise * 1000) + messages)
    runs = []
    for person in range(people):
        truth = rng.uniform(0.15, 0.85)
        score, confidence = simulate(truth, noise, messages, seed=person * 7919 + int(noise * 100))
        runs.append((abs(score - truth), confidence))
    return runs


class TraitConfidenceCalibration(unittest.TestCase):
    def test_predictable_people_earn_more_confidence_than_erratic_ones(self):
        averages = [statistics.mean(c for _, c in population(noise)) for noise in (0.05, 0.15, 0.25, 0.40)]
        self.assertEqual(averages, sorted(averages, reverse=True))
        self.assertGreater(averages[0], 0.85)  # very consistent -> very sure
        self.assertLess(averages[-1], 0.6)  # all over the place -> never very sure

    def test_high_confidence_means_the_reading_is_close_to_the_truth(self):
        runs = [run for noise in (0.05, 0.15, 0.25, 0.40) for run in population(noise)]
        sure = [error for error, confidence in runs if confidence >= 0.75]
        unsure = [error for error, confidence in runs if confidence < 0.6]
        self.assertGreater(len(sure), 20)
        self.assertGreater(len(unsure), 20)
        self.assertLess(statistics.mean(sure), statistics.mean(unsure))
        self.assertLess(statistics.mean(sure), 0.06)  # within 6 points of the truth on average
        self.assertLess(max(sure), 0.2)  # and never badly wrong while claiming to be sure

    def test_confidence_estimates_how_often_the_next_message_fits(self):
        # The share of future messages landing within the agreement band should rise with confidence.
        def fit_rate(noise):
            rng = random.Random(42)
            fits = []
            for person in range(40):
                truth = rng.uniform(0.2, 0.8)
                score, _ = simulate(truth, noise, 150, seed=person)
                fits += [abs(min(1, max(0, rng.gauss(truth, noise))) - score) <= 0.2 for _ in range(50)]
            return sum(fits) / len(fits)

        rates = [fit_rate(noise) for noise in (0.05, 0.25, 0.40)]
        confidences = [statistics.mean(c for _, c in population(noise)) for noise in (0.05, 0.25, 0.40)]
        self.assertEqual(rates, sorted(rates, reverse=True))
        for rate, confidence in zip(rates, confidences):
            self.assertLess(abs(rate - confidence), 0.3)  # same ballpark, not an unrelated number

    def test_a_few_messages_are_never_enough_to_be_sure(self):
        for seed in range(20):
            _, confidence = simulate(0.8, 0.02, 8, seed)
            self.assertLess(confidence, 0.4)

    def test_a_real_change_in_the_person_lowers_confidence_then_recovers(self):
        rng = random.Random(3)
        score, confidence = 0.5, 0.1
        for _ in range(120):
            score, confidence = compute_trait_update(score, confidence, min(1, max(0, rng.gauss(0.2, 0.06))), 0.15)
        settled = confidence
        dipped = settled
        for _ in range(25):
            score, confidence = compute_trait_update(score, confidence, min(1, max(0, rng.gauss(0.8, 0.06))), 0.15)
            dipped = min(dipped, confidence)
        self.assertLess(dipped, settled - 0.15)
        for _ in range(200):
            score, confidence = compute_trait_update(score, confidence, min(1, max(0, rng.gauss(0.8, 0.06))), 0.15)
        self.assertAlmostEqual(score, 0.8, delta=0.06)
        self.assertGreater(confidence, 0.8)


def person(**overrides):
    base = dict(
        trait_confidences=[0.6, 0.6, 0.6, 0.6],
        trait_evidence=200,
        messages=120,
        active_days=10,
        days_since_last=1.0,
        voice_own=100,
        voice_imported=0,
        reflection_confidences=[0.6, 0.6, 0.6],
    )
    base.update(overrides)
    return build_result(**base)


class SourceScores(unittest.TestCase):
    def test_weights_add_up(self):
        self.assertAlmostEqual(sum(SOURCE_WEIGHTS.values()), 1.0)

    def test_nothing_in_means_no_score_not_zero(self):
        self.assertIsNone(score_traits([], 0))
        self.assertIsNone(score_traits([0.1, 0.1, 0.1, 0.1], 0))  # defaults, nothing read yet
        self.assertIsNone(score_conversations(0, 0, None))
        self.assertIsNone(score_voice(0, 0))
        self.assertIsNone(score_reflections([]))

    def test_trait_score_is_the_plain_average(self):
        self.assertAlmostEqual(score_traits([0.65, 0.67, 0.51, 0.66], 373), 0.6225)

    def test_conversations_grow_with_messages_and_days(self):
        by_messages = [score_conversations(n, 5, 0) for n in (1, 10, 50, 200, 1000)]
        by_days = [score_conversations(100, d, 0) for d in (1, 3, 7, 14, 60)]
        self.assertEqual(by_messages, sorted(by_messages))
        self.assertEqual(by_days, sorted(by_days))
        self.assertLess(score_conversations(200, 1, 0), score_conversations(200, 14, 0))  # one long night < two weeks

    def test_freshness_holds_for_a_month_then_halves_every_six_months(self):
        self.assertEqual(freshness(0), 1.0)
        self.assertEqual(freshness(30), 1.0)
        self.assertAlmostEqual(freshness(210), 0.5, places=3)
        self.assertAlmostEqual(freshness(390), 0.25, places=3)

    def test_imported_texts_help_voice_but_count_half(self):
        self.assertGreater(score_voice(5, 40), score_voice(5, 0))
        self.assertAlmostEqual(score_voice(0, 40), score_voice(20, 0))
        self.assertGreater(score_voice(40, 0), score_voice(0, 40))

    def test_reflections_need_a_full_set_and_real_confidence(self):
        self.assertLess(score_reflections([0.9]), score_reflections([0.9, 0.9, 0.9]))
        self.assertLess(score_reflections([0.4, 0.4, 0.4]), score_reflections([0.8, 0.8, 0.8]))
        self.assertAlmostEqual(score_reflections([0.6, 0.6, 0.6, 0.6]), 0.6)


class OverallConfidence(unittest.TestCase):
    def test_no_data_is_zero_and_very_low(self):
        result = build_result([], 0, 0, 0, None, 0, 0, [])
        self.assertEqual((result.center, result.lower, result.upper, result.tier), (0.0, 0.0, 0.0, "very_low"))

    def test_range_always_brackets_the_centre_and_stays_in_bounds(self):
        rng = random.Random(11)
        for _ in range(500):
            result = build_result(
                [rng.random() for _ in range(4)], rng.randint(0, 500), rng.randint(0, 800), rng.randint(0, 60),
                rng.choice([None, rng.uniform(0, 900)]), rng.randint(0, 600), rng.randint(0, 300),
                [rng.random() for _ in range(rng.randint(0, 5))],
            )
            self.assertLessEqual(0.0, result.lower)
            self.assertLessEqual(result.lower, result.center + 1e-9)
            self.assertLessEqual(result.center, result.upper + 1e-9)
            self.assertLessEqual(result.upper, 1.0)
            self.assertLessEqual(result.upper - result.lower, 2 * MAX_HALF_WIDTH + 1e-4)  # results are rounded

    def test_more_of_any_evidence_never_lowers_the_centre(self):
        base = person()
        self.assertGreaterEqual(person(messages=400).center, base.center)
        self.assertGreaterEqual(person(active_days=40).center, base.center)
        self.assertGreaterEqual(person(voice_own=400).center, base.center)
        self.assertGreaterEqual(person(trait_confidences=[0.8] * 4).center, base.center)
        self.assertGreaterEqual(person(reflection_confidences=[0.8] * 4).center, base.center)

    def test_an_import_never_lowers_confidence(self):
        for own in (0, 3, 30, 300):
            without = person(voice_own=own, messages=max(own, 1), voice_imported=0)
            with_import = person(voice_own=own, messages=max(own, 1), voice_imported=200)
            self.assertGreaterEqual(with_import.center, without.center)
            self.assertGreaterEqual(with_import.lower, without.lower - 1e-9)

    def test_range_narrows_as_messages_accumulate(self):
        same = {"traits": 0.6, "conversations": 0.6, "voice": 0.6, "reflections": 0.6}
        widths = [fuse_source_scores(same, messages=n)["half_width"] for n in (0, 3, 20, 80, 400)]
        self.assertEqual(widths, sorted(widths, reverse=True))
        self.assertGreater(widths[0], 0.14)  # nothing to go on: at least +-14 points
        self.assertAlmostEqual(widths[-1], MIN_HALF_WIDTH, places=3)  # plenty, all agreeing: +-3

    def test_disagreeing_sources_widen_the_range(self):
        agree = fuse_source_scores({"traits": 0.7, "conversations": 0.7, "voice": 0.7, "reflections": 0.7}, messages=300)
        clash = fuse_source_scores({"traits": 0.3, "conversations": 1.0, "voice": 1.0, "reflections": 0.4}, messages=300)
        self.assertAlmostEqual(agree["half_width"], MIN_HALF_WIDTH, places=3)
        self.assertGreater(clash["half_width"], agree["half_width"] + 0.05)

    def test_missing_sources_are_left_out_but_widen_the_range(self):
        full = fuse_source_scores({"traits": 0.7, "conversations": 0.7, "voice": 0.7, "reflections": 0.7}, messages=300)
        partial = fuse_source_scores({"traits": 0.7, "conversations": 0.7, "voice": 0.7, "reflections": None}, messages=300)
        self.assertAlmostEqual(partial["center"], 0.7)  # not dragged toward zero
        self.assertGreater(partial["half_width"], full["half_width"])

    def test_going_quiet_for_months_lowers_confidence(self):
        centres = [person(days_since_last=d).center for d in (1, 30, 120, 400, 900)]
        self.assertEqual(centres[0], centres[1])
        self.assertEqual(centres[1:], sorted(centres[1:], reverse=True))
        self.assertLess(centres[-1], centres[0] - 0.1)

    def test_every_level_is_reachable_by_a_realistic_person(self):
        brand_new = build_result([0.12] * 4, 4, 3, 1, 0, 2, 0, [])
        a_few_days = build_result([0.35] * 4, 60, 30, 3, 0, 24, 0, [])
        regular = build_result([0.62] * 4, 370, 350, 14, 1, 300, 0, [0.6, 0.55, 0.65, 0.6])
        long_term = build_result([0.9] * 4, 2500, 1500, 90, 0, 1300, 0, [0.9, 0.9, 0.85, 0.9])
        self.assertEqual(
            [brand_new.tier, a_few_days.tier, regular.tier, long_term.tier],
            ["very_low", "partial", "moderate", "high"],
        )

    def test_one_marathon_session_is_not_enough_for_the_top_level(self):
        binge = build_result([0.9] * 4, 300, 300, 1, 0, 280, 0, [])
        self.assertNotEqual(binge.tier, "high")

    def test_tier_bounds(self):
        self.assertEqual(
            [tier_from_confidence_lower(x) for x in (0.0, 0.2, 0.21, 0.5, 0.51, 0.75, 0.76, 1.0)],
            ["very_low", "very_low", "partial", "partial", "moderate", "moderate", "high", "high"],
        )


if __name__ == "__main__":
    unittest.main()
