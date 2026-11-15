"""Deterministic, LLM-free signals derived from a single user message.

Used as a fallback when LLM trait extraction is unavailable, and to fill the
per-message analytics columns (token_count, emotional_intensity, reflection_depth)
and the reflection-log sentiment.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

EMOTIONAL_KEYWORDS = {
    "feel", "felt", "sad", "happy", "anxious", "worried", "stressed",
    "overwhelmed", "excited", "frustrated", "angry",
}
HEDGE_PHRASES = ["maybe", "perhaps", "i think", "kind of", "sort of", "not sure"]
DECISIVE_WORDS = {"definitely", "certain", "will", "must", "clear", "decided"}
DEPTH_MARKERS = {
    "why", "because", "realize", "pattern", "meaning", "reflect", "thinking", "understand",
}

POSITIVE_WORDS = {
    "good", "great", "happy", "glad", "excited", "love", "awesome", "amazing", "calm",
    "proud", "grateful", "better", "relieved", "fun", "enjoy", "enjoyed", "hopeful",
}
NEGATIVE_WORDS = {
    "bad", "sad", "angry", "upset", "stressed", "anxious", "worried", "tired", "hate",
    "awful", "terrible", "overwhelmed", "frustrated", "lonely", "scared", "worse", "lost",
}


def _words(text: str) -> List[str]:
    return re.findall(r"[a-z']+", (text or "").lower())


def _emotional_signal(words: List[str], text: str) -> tuple[float, int, int]:
    emotion_hits = sum(1 for word in words if word in EMOTIONAL_KEYWORDS)
    exclamations = text.count("!")
    signal = max(0.0, min(1.0, 0.25 + (emotion_hits * 0.15) + (exclamations * 0.08)))
    return signal, emotion_hits, exclamations


def _depth_signal(words: List[str]) -> tuple[float, int]:
    depth_hits = sum(1 for word in words if word in DEPTH_MARKERS)
    return max(0.0, min(1.0, 0.2 + (depth_hits * 0.14))), depth_hits


def derive_fallback_traits(user_text: str) -> List[Dict[str, float]]:
    """Conservative keyword/length trait nudges used when LLM extraction returns nothing."""
    text = user_text or ""
    words = _words(text)
    lower_text = text.lower()
    word_count = len(words)

    traits: List[Dict[str, float]] = [
        {
            "name": "communication_style",
            "signal": max(0.0, min(1.0, (word_count - 4) / 24.0)),
            "strength": min(0.16, 0.07 + (min(word_count, 40) / 500.0)),
        }
    ]

    express_signal, emotion_hits, exclamations = _emotional_signal(words, text)
    if emotion_hits > 0 or exclamations > 0:
        traits.append(
            {
                "name": "emotional_expressiveness",
                "signal": express_signal,
                "strength": min(0.18, 0.08 + (emotion_hits * 0.02) + (exclamations * 0.01)),
            }
        )

    hedge_hits = sum(1 for phrase in HEDGE_PHRASES if phrase in lower_text)
    decisive_hits = sum(1 for word in words if word in DECISIVE_WORDS)
    if hedge_hits > 0 or decisive_hits > 0:
        traits.append(
            {
                "name": "decision_framing",
                "signal": max(0.0, min(1.0, 0.5 + (decisive_hits * 0.12) - (hedge_hits * 0.14))),
                "strength": min(0.17, 0.08 + ((hedge_hits + decisive_hits) * 0.02)),
            }
        )

    depth_signal, depth_hits = _depth_signal(words)
    if depth_hits > 0:
        traits.append(
            {
                "name": "reflection_depth",
                "signal": depth_signal,
                "strength": min(0.18, 0.08 + (depth_hits * 0.02)),
            }
        )

    # Keep only meaningful signals to avoid noisy updates.
    return [
        trait
        for trait in traits
        if abs(trait["signal"] - 0.5) >= 0.08 or trait["name"] == "communication_style"
    ]


def compute_message_metrics(user_text: str, nudges: Optional[List[Dict]] = None) -> Dict[str, Optional[float]]:
    """Per-message analytics values. Prefers the LLM nudge signal, falls back to keyword heuristics."""
    text = user_text or ""
    words = _words(text)
    by_name = {str(n.get("name")): float(n.get("signal", 0.5)) for n in (nudges or []) if n.get("name")}

    emotional = by_name.get("emotional_expressiveness")
    if emotional is None:
        emotional, _, _ = _emotional_signal(words, text)

    depth = by_name.get("reflection_depth")
    if depth is None:
        depth, _ = _depth_signal(words)

    return {
        "token_count": len(text.split()),
        "emotional_intensity": round(emotional, 3),
        "reflection_depth": round(depth, 3),
    }


def simple_sentiment(text: str) -> float:
    """Lexicon sentiment in [-1, 1]; 0.0 when no sentiment words are present."""
    words = _words(text)
    positive = sum(1 for word in words if word in POSITIVE_WORDS)
    negative = sum(1 for word in words if word in NEGATIVE_WORDS)
    total = positive + negative
    if total == 0:
        return 0.0
    return round((positive - negative) / total, 3)
