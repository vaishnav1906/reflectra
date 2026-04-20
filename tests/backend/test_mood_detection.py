#!/usr/bin/env python3
"""Test the improved mood detection system"""

import re
import logging

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

EMOTIONAL_MARKERS = {
    "insecurity": ["i don't know", "maybe", "not sure", "probably wrong", "doubt", "uncertain", "hesitant", "scared", "nervous", "idk", "unsure", "confused", "lost"],
    "stress": ["stressed", "overwhelmed", "anxious", "worried", "pressure", "struggling", "can't handle", "too much", "exhausted", "tired", "drowning", "burnout"],
    "anger": ["pissed", "angry", "furious", "mad", "hate", "fuck", "bullshit", "ridiculous", "unacceptable", "done with", "fed up", "irritated"],
    "playful": ["lol", "lmao", "haha", "😂", "💀", "bruh", "nah", "lowkey", "highkey", "vibes", "bet", "tbh"],
    "sarcasm": ["sure", "yeah right", "oh great", "wonderful", "fantastic", "obviously", "totally", "yeah okay", "perfect", "lovely"],
    "excitement": ["yay", "woohoo", "omg", "yes", "let's go", "pumped", "thrilled", "can't wait", "hyped", "stoked"],
    "happiness": ["happy", "great", "awesome", "amazing", "love", "excellent", "wonderful"],
}

SLANG_HYPE_WORDS = ["lmaooo", "brooo", "yooo", "yoooo", "frfr", "fr fr", "omfg", "yasss", "yaaas"]

GREETING_PATTERNS = [
    r"\b(hi|hello|hey|good morning|good afternoon|good evening|greetings)\b",
    r"how('s| is) (your|the) (day|morning|evening|afternoon)",
    r"how are you",
    r"what('s| is) up",
    r"hope you('re| are) (doing )?(well|good|okay)",
]


def detect_emotional_tone(text: str) -> str:
    """Detect emotional tone with strict intensity markers."""
    lower = text.lower()
    original_text = text

    for pattern in GREETING_PATTERNS:
        if re.search(pattern, lower):
            logger.info("Message: '%s' | Markers: [greeting_detected] | Classification: neutral", original_text)
            return "neutral"

    has_elongation = bool(re.search(r"([a-z])\1{2,}", lower))
    multiple_exclamations = bool(re.search(r"!{3,}", text))
    multiple_questions = bool(re.search(r"\?{2,}", text))
    has_slang_hype = any(word in lower for word in SLANG_HYPE_WORDS)
    has_caps = bool(re.search(r"[A-Z]{4,}", text))
    has_question = "?" in text
    word_count = len(text.split())

    detected_markers = []
    if has_elongation:
        detected_markers.append("elongated_words")
    if multiple_exclamations:
        detected_markers.append("triple_exclamations")
    if multiple_questions:
        detected_markers.append("multiple_questions")
    if has_slang_hype:
        detected_markers.append("slang_hype")
    if has_caps:
        detected_markers.append("caps_emphasis")

    intensity_marker_count = len(detected_markers)
    emotion_scores = {emotion: 0 for emotion in EMOTIONAL_MARKERS.keys()}

    for emotion, markers in EMOTIONAL_MARKERS.items():
        for marker in markers:
            if marker in lower:
                emotion_scores[emotion] += 1

    if intensity_marker_count >= 2:
        emotion_scores["excitement"] += 3
        emotion_scores["playful"] += 2

    if has_caps and (multiple_exclamations or multiple_questions):
        emotion_scores["anger"] += 2

    if has_question and word_count < 10 and intensity_marker_count == 0:
        emotion_scores["insecurity"] += 1

    if (multiple_exclamations or multiple_questions) and any(marker in lower for marker in ["lol", "lmao", "haha"]):
        emotion_scores["playful"] += 2

    positive_words = ["great", "wonderful", "perfect", "amazing"]
    if any(word in lower for word in positive_words) and (multiple_exclamations or "..." in text):
        emotion_scores["sarcasm"] += 2

    max_score = max(emotion_scores.values())
    if max_score == 0:
        logger.info("Message: '%s' | Markers: %s | Classification: neutral", original_text, detected_markers)
        return "neutral"

    for emotion, score in emotion_scores.items():
        if score == max_score:
            logger.info("Message: '%s' | Markers: %s | Classification: %s (score=%s)", original_text, detected_markers, emotion, score)
            return emotion

    return "neutral"


test_cases = [
    "Hi there! How's your day?",
    "Hello, how are you?",
    "Hey! What's up?",
    "Good morning!",
    "Hope you're doing well!",
    "I'm doing well, thanks!",
    "That sounds nice!",
    "Yoooo!!!",
    "NOOOO WAY!!!!",
    "lmaooo that's crazy!!!",
    "LET'S GOOO!!!",
    "bruh that's wild lmaooo",
    "yooo what's good",
    "I'm so happy!",
    "This is great...",
    "I don't know what to do",
    "I'm so stressed out",
    "This is fucking ridiculous",
    "haha that's funny",
    "ok",
    "Yeah sure, that's just perfect.",
]

if __name__ == "__main__":
    print("=" * 80)
    print("MOOD DETECTION TEST")
    print("=" * 80)
    for test_text in test_cases:
        print("\nTest:", repr(test_text))
        result = detect_emotional_tone(test_text)
        print("Result:", result)
    print("=" * 80)
    print("TEST COMPLETE")
