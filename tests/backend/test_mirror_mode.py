#!/usr/bin/env python3
"""Manual-style mirror mode behavior probe."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.services.mirror_engine import analyze_message_style, extract_key_traits, format_trait_score

print("=" * 80)
print("MIRROR MODE - MESSAGE STYLE ANALYSIS TEST")
print("=" * 80)

test_messages = [
    {"name": "Short & Direct", "message": "I'm done. Not doing this anymore. Moving on."},
    {"name": "Casual & Slang", "message": "Yeah I'm kinda worried about this whole thing tbh, like it's just a lot you know?"},
    {"name": "Question-heavy", "message": "What should I do? Is this the right choice? Am I making a mistake?"},
]

for test in test_messages:
    print(f"\n--- {test['name']} ---")
    style = analyze_message_style(test["message"])
    print(style)

mock_persona = {
    "emotional_profile": {
        "emotional_intensity": {"score": 0.75, "confidence": 0.8},
        "emotional_stability": {"score": 0.45, "confidence": 0.6},
    },
    "cognitive_profile": {
        "analytical_thinking": {"score": 0.82, "confidence": 0.9},
        "decision_confidence": {"score": 0.38, "confidence": 0.5},
    },
    "communication_profile": {
        "directness": {"score": 0.68, "confidence": 0.7},
        "expressiveness": {"score": 0.55, "confidence": 0.6},
    },
}

traits = extract_key_traits(mock_persona)
print("\nExtracted Key Traits:")
for trait_name, score in traits.items():
    print(f"- {trait_name}: {format_trait_score(score)}")

print("\nTEST COMPLETE")
