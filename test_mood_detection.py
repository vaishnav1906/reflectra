#!/usr/bin/env python3
"""Test the improved mood detection system"""

import re
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Copy the emotion detection logic from chat.py
EMOTIONAL_MARKERS = {
    "insecurity": ["i don't know", "maybe", "not sure", "probably wrong", "doubt", "uncertain", "hesitant", "scared", "nervous", "idk", "unsure", "confused", "lost"],
    "stress": ["stressed", "overwhelmed", "anxious", "worried", "pressure", "struggling", "can't handle", "too much", "exhausted", "tired", "drowning", "burnout"],
    "anger": ["pissed", "angry", "furious", "mad", "hate", "fuck", "bullshit", "ridiculous", "unacceptable", "done with", "fed up", "irritated"],
    "playful": ["lol", "lmao", "haha", "😂", "💀", "bruh", "nah", "lowkey", "highkey", "vibes", "bet", "tbh"],
    "sarcasm": ["sure", "yeah right", "oh great", "wonderful", "fantastic", "obviously", "totally", "yeah okay", "perfect", "lovely"],
    "excitement": ["yay", "woohoo", "omg", "yes", "let's go", "pumped", "thrilled", "can't wait", "hyped", "stoked"],
    "happiness": ["happy", "great", "awesome", "amazing", "love", "excellent", "wonderful"],
}

SLANG_HYPE_WORDS = ["yo", "bruh", "lmao", "lmaooo", "brooo", "yooo", "yoooo", "fr", "frfr", "fr fr", "omfg"]

def detect_emotional_tone(text: str) -> str:
    """Detect emotional tone with intensity markers"""
    lower = text.lower()
    original_text = text
    
    # Detect elongated characters (3+ repeating letters)
    has_elongation = bool(re.search(r"([a-z])\1{2,}", lower))
    
    # Detect multiple exclamation marks
    multiple_exclamations = bool(re.search(r"!{2,}", text))
    
    # Detect slang hype words
    has_slang_hype = any(word in lower for word in SLANG_HYPE_WORDS)
    
    # Detect caps emphasis
    has_caps = bool(re.search(r"[A-Z]{2,}", text))
    
    # Additional intensity markers
    multiple_punct = bool(re.search(r"[!?]{2,}", text))
    has_question = "?" in text
    word_count = len(text.split())
    
    # Log detected markers
    detected_markers = []
    if has_elongation:
        detected_markers.append("elongated_words")
    if multiple_exclamations:
        detected_markers.append("multiple_exclamations")
    if has_slang_hype:
        detected_markers.append("slang_hype")
    if has_caps:
        detected_markers.append("caps_emphasis")
    
    logger.info(f"🔍 Emotion detection - Original: '{original_text}' | Markers: {detected_markers}")
    
    # Count emotional markers
    emotion_scores = {emotion: 0 for emotion in EMOTIONAL_MARKERS.keys()}
    
    for emotion, markers in EMOTIONAL_MARKERS.items():
        for marker in markers:
            if marker in lower:
                emotion_scores[emotion] += 1
    
    # BOOST LOGIC: Apply intensity marker boosts
    if has_elongation or has_slang_hype or multiple_exclamations:
        emotion_scores["excitement"] += 3
        emotion_scores["playful"] += 2
        logger.info("⚡ Boosting excitement/playful due to intensity markers")
    
    # Linguistic analysis for additional signals
    if has_caps and multiple_punct:
        emotion_scores["anger"] += 2
    
    if has_question and word_count < 10:
        emotion_scores["insecurity"] += 1
    
    if multiple_punct and any(marker in lower for marker in ["lol", "lmao", "haha"]):
        emotion_scores["playful"] += 2
    
    # Check for contradictory tone (sarcasm indicator)
    positive_words = ["great", "wonderful", "perfect", "amazing"]
    if any(word in lower for word in positive_words) and (multiple_punct or "..." in text):
        emotion_scores["sarcasm"] += 2
    
    # Find dominant emotion
    max_score = max(emotion_scores.values())
    
    if max_score == 0:
        logger.info(f"😐 Classified as: neutral (no markers detected)")
        return "neutral"
    
    # Return the emotion with highest score
    for emotion, score in emotion_scores.items():
        if score == max_score:
            logger.info(f"🎯 Classified as: {emotion} (score: {score})")
            return emotion
    
    logger.info(f"😐 Classified as: neutral (fallback)")
    return "neutral"


# Test cases
test_cases = [
    "Yoooo",
    "yooo what's up",
    "Noooo way!!!",
    "bruh that's crazy",
    "lmaooo",
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
    print()
    
    for test_text in test_cases:
        print(f"\nTest: '{test_text}'")
        print("-" * 80)
        result = detect_emotional_tone(test_text)
        print(f"✅ Final result: {result}")
        print()
    
    print("=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)
