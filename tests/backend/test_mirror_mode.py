#!/usr/bin/env python3
"""
Test the new Mirror Mode system prompt.

This demonstrates how the mirror engine analyzes both:
1. Stored personality traits
2. Live message style
"""

import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from app.services.mirror_engine import (
    analyze_message_style,
    extract_key_traits,
    format_trait_score,
)

print("=" * 80)
print("MIRROR MODE - MESSAGE STYLE ANALYSIS TEST")
print("=" * 80)

# Test different message styles
test_messages = [
    {
        "name": "Short & Direct",
        "message": "I'm done. Not doing this anymore. Moving on."
    },
    {
        "name": "Casual & Slang",
        "message": "Yeah I'm kinda worried about this whole thing tbh, like it's just a lot you know?"
    },
    {
        "name": "Analytical & Long",
        "message": "I've been analyzing this situation from multiple angles, and while I understand the logical framework, I'm still uncertain about the optimal decision path given the current constraints."
    },
    {
        "name": "Excited & Punctuation",
        "message": "OMG this is amazing!!! I can't believe it!! So excited!!!"
    },
    {
        "name": "Question-heavy",
        "message": "What should I do? Is this the right choice? Am I making a mistake?"
    },
]

for test in test_messages:
    print(f"\n{'-' * 80}")
    print(f"Message Type: {test['name']}")
    print(f"Message: \"{test['message']}\"")
    print(f"{'-' * 80}")
    
    style = analyze_message_style(test['message'])
    
    print(f"\nStyle Analysis:")
    print(f"  • Avg Sentence Length: {style['avg_sentence_length']} words")
    print(f"  • Punctuation Intensity: {style['punctuation_intensity']}")
    print(f"  • Has Slang: {'Yes' if style['has_slang'] else 'No'}")
    print(f"  • Emotional Markers: {style['emotional_markers']}")
    print(f"  • Caps Intensity: {int(style['caps_intensity'] * 100)}%")
    print(f"  • Has Questions: {'Yes' if style['has_questions'] else 'No'}")
    
    print(f"\nMirroring Instructions:")
    if style['avg_sentence_length'] < 5:
        print(f"  → Match short, punchy sentences")
    elif style['avg_sentence_length'] > 15:
        print(f"  → Match longer, flowing sentences")
    
    if style['has_slang']:
        print(f"  → Use casual, conversational language")
    
    if style['has_questions']:
        print(f"  → Questions detected - can mirror with questions")
    else:
        print(f"  → NO reflection-style questions allowed")
    
    if style['punctuation_intensity'] > 2:
        print(f"  → HIGH energy - match their punctuation")

print(f"\n{'=' * 80}")
print("TRAIT EXTRACTION TEST")
print(f"{'=' * 80}")

# Mock persona vector
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

print(f"\nExtracted Key Traits for Mirroring:")
for trait_name, score in traits.items():
    print(f"  • {trait_name.replace('_', ' ').title()}: {format_trait_score(score)}")

print(f"\n{'=' * 80}")
print("KEY DIFFERENCES FROM REFLECTION MODE")
print(f"{'=' * 80}")

print("""
REFLECTION MODE:
  ❌ Asks probing questions
  ❌ Explains emotions back to user
  ❌ Performs analytical breakdowns
  ❌ Acts like therapist/coach
  ❌ Encourages deeper exploration

MIRROR MODE:
  ✅ Responds as user would respond to themselves
  ✅ Matches their exact communication style
  ✅ Stays within their emotional intensity bounds
  ✅ NO questions unless they ask questions
  ✅ "You talking back to yourself at 110% clarity"
  ✅ Direct, authentic, natural

EXAMPLE:
  User: "I'm stressed about this deadline."
  
  Reflection: "What specifically about the deadline is causing stress? 
              How do you typically handle time pressure?"
  
  Mirror: "Yeah, this deadline is tight. Need to just tackle it."
          (Matches their directness and intensity)
""")

print(f"{'=' * 80}")
print("✅ TEST COMPLETE")
print(f"{'=' * 80}\n")
