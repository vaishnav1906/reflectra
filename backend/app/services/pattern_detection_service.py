import re
from collections import Counter


EMOTION_KEYWORDS = {
    "stress": ["stress", "stressed", "pressure", "overwhelmed"],
    "anxiety": ["anxious", "worried", "panic", "nervous"],
    "sadness": ["sad", "down", "depressed"],
}

TRIGGER_KEYWORDS = {
    "exams": ["exam", "exams", "test", "deadline"],
    "work": ["work", "job", "office"],
    "relationships": ["relationship", "friend", "family"],
}


async def detect_patterns(memories):

    emotion_counts = Counter()
    trigger_counts = Counter()

    for memory in memories:
        text = memory.lower()

        # detect emotions
        for emotion, keywords in EMOTION_KEYWORDS.items():
            if any(word in text for word in keywords):
                emotion_counts[emotion] += 1

        # detect triggers
        for trigger, keywords in TRIGGER_KEYWORDS.items():
            if any(word in text for word in keywords):
                trigger_counts[trigger] += 1

    patterns = []

    # emotional state pattern
    for emotion, count in emotion_counts.items():
        if count >= 2:
            patterns.append(f"emotional_state → {emotion}")

    # trigger pattern
    for trigger, count in trigger_counts.items():
        if count >= 2:
            patterns.append(f"stress_trigger → {trigger}")

    # behavior loop detection
    if emotion_counts and sum(emotion_counts.values()) >= 3:
        patterns.append("behavior_loop → repeated emotional stress")

    return patterns