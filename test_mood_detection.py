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

SLANG_HYPE_WORDS = ["lmaooo", "brooo", "yooo", "yoooo", "frfr", "fr fr", "omfg", "yasss", "yaaas"]

GREETING_PATTERNS = [
    r"\b(hi|hello|hey|good morning|good afternoon|good evening|greetings)\b",
    r"how('s| is) (your|the) (day|morning|evening|afternoon)",
    r"how are you",
    r"what('s| is) up",
    r"hope you('re| are) (doing )?(well|good|okay)",
]

def detect_emotional_tone(text: str) -> str:
    """Detect emotional tone with strict intensity markers"""
    lower = text.lower()
    original_text = text
    
    # === STEP 1: Check for polite greetings/conversational openers ===
    is_greeting = False
    for pattern in GREETING_PATTERNS:
        if re.search(pattern, lower):
            is_greeting = True
            logger.info(f"🔍 Message: '{original_text}' | Markers: [greeting_detected] | Classification: neutral (polite greeting)")
            return "neutral"
    
    # === STEP 2: Detect intensity markers ===
    # Detect elongated characters (3+ repeating letters)
    has_elongation = bool(re.search(r"([a-z])\1{2,}", lower))
    
    # Detect MULTIPLE exclamation marks (3+) - single or double is casual
    multiple_exclamations = bool(re.search(r"!{3,}", text))
    
    # Detect repeated question marks (2+)
    multiple_questions = bool(re.search(r"\?{2,}", text))
    
    # Detect slang hype words (stricter - only elongated/repeated slang)
    has_slang_hype = any(word in lower for word in SLANG_HYPE_WORDS)
    
    # Detect caps emphasis (must be 4+ chars for emphasis, not just initials)
    has_caps = bool(re.search(r"[A-Z]{4,}", text))
    
    # Additional markers
    has_question = "?" in text
    word_count = len(text.split())
    
    # Count intensity markers
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
    
    # === STEP 3: Count emotional markers ===
    emotion_scores = {emotion: 0 for emotion in EMOTIONAL_MARKERS.keys()}
    
    for emotion, markers in EMOTIONAL_MARKERS.items():
        for marker in markers:
            if marker in lower:
                emotion_scores[emotion] += 1
    
    # === STEP 4: Apply intensity marker boosts (ONLY if 2+ markers) ===
    # Require MULTIPLE intensity markers to classify as excitement/playful
    if intensity_marker_count >= 2:
        emotion_scores["excitement"] += 3
        emotion_scores["playful"] += 2
        logger.info(f"⚡ Boosting excitement/playful (intensity_markers={intensity_marker_count})")
    
    # Linguistic analysis for additional signals
    if has_caps and (multiple_exclamations or multiple_questions):
        emotion_scores["anger"] += 2
    
    if has_question and word_count < 10 and intensity_marker_count == 0:
        emotion_scores["insecurity"] += 1
    
    if (multiple_exclamations or multiple_questions) and any(marker in lower for marker in ["lol", "lmao", "haha"]):
        emotion_scores["playful"] += 2
    
    # Check for contradictory tone (sarcasm indicator)
    positive_words = ["great", "wonderful", "perfect", "amazing"]
    if any(word in lower for word in positive_words) and (multiple_exclamations or "..." in text):
        emotion_scores["sarcasm"] += 2
    
    # === STEP 5: Determine final classification ===
    max_score = max(emotion_scores.values())
    
    if max_score == 0:
        logger.info(f"🔍 Message: '{original_text}' | Markers: {detected_markers} | Classification: neutral (no emotional markers)")
        return "neutral"
    
    # Return the emotion with highest score
    for emotion, score in emotion_scores.items():
        if score == max_score:
            logger.info(f"🔍 Message: '{original_text}' | Markers: {detected_markers} | Classification: {emotion} (score={score})")
            return emotion
    
    logger.info(f"🔍 Message: '{original_text}' | Markers: {detected_markers} | Classification: neutral (fallback)")
    return "neutral"


# Test cases
test_cases = [
    # ===== CRITICAL TEST: Should be NEUTRAL, NOT chaotic =====
    "Hi there! How's your day?",
    
    # ===== Polite greetings (should be neutral) =====
    "Hello, how are you?",
    "Hey! What's up?",
    "Good morning!",
    "Hope you're doing well!",
    
    # ===== Friendly but calm (should be neutral or happiness) =====
    "I'm doing well, thanks!",
    "That sounds nice!",
    
    # ===== TRUE excitement (multiple intensity markers) =====
    "Yoooo!!!",  # elongation + triple exclamation
    "NOOOO WAY!!!!",  # caps + elongation + multiple exclamations
    "lmaooo that's crazy!!!",  # slang hype + triple exclamation
    "LET'S GOOO!!!",  # caps + elongation + triple exclamation
    
    # ===== TRUE playful (exaggeration/slang) =====
    "bruh that's wild lmaooo",  # multiple slang markers
    "yooo what's good",  # slang hype
    
    # ===== Other emotions =====
    "I'm so happy!",  # happiness marker
    "This is great...",  # sarcasm
    "I don't know what to do",  # insecurity
    "I'm so stressed out",  # stress
    "This is fucking ridiculous",  # anger
    "haha that's funny",  # playful markers
    "ok",  # neutral
    "Yeah sure, that's just perfect.",  # sarcasm
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
