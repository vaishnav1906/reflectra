"""Mirror engine for generating personalized responses."""

import logging
import os
import re
from typing import Dict, Optional, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repository.persona_repository import PersonaRepository
from app.constants import (
    STABILITY_THRESHOLD_UNSTABLE,
    STABILITY_THRESHOLD_STABLE,
)

logger = logging.getLogger(__name__)

# Initialize Mistral client
MISTRAL_AVAILABLE = False
mistral_client = None

try:
    from mistralai import Mistral
    api_key = os.getenv("MISTRAL_API_KEY")
    if api_key:
        mistral_client = Mistral(api_key=api_key)
        MISTRAL_AVAILABLE = True
        logger.info("✅ Mistral client initialized for mirror engine")
except Exception as e:
    logger.warning(f"⚠️ Mistral not available for mirror engine: {e}")


# Cache for latest snapshots (user_id -> snapshot)
_snapshot_cache: Dict[str, Dict] = {}


async def generate_mirror_response(
    db: AsyncSession, user_id: UUID, message: str
) -> str:
    """
    Generate a mirror response based on user's personality profile.
    
    Args:
        db: Database session
        user_id: User UUID
        message: User's message
        
    Returns:
        Mirror response string
    """
    if not MISTRAL_AVAILABLE or not mistral_client:
        return "Mirror functionality requires LLM configuration."
    
    logger.info(f"🪞 Generating mirror response for user {user_id}")
    
    # Get latest snapshot (with caching)
    snapshot = await get_cached_snapshot(db, user_id)
    
    if not snapshot:
        logger.warning(f"⚠️ No snapshot found for user {user_id}, creating baseline")
        return await generate_baseline_mirror_response(message)
    
    # Analyze current message style
    message_style = analyze_message_style(message)
    logger.info(f"📊 Message style: {message_style}")
    
    # Build mirror system prompt with personality baseline and live style analysis
    system_prompt = build_mirror_system_prompt(
        snapshot.persona_vector,
        snapshot.stability_index,
        message_style,
    )
    
    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ]
        
        response = mistral_client.chat.complete(
            model="mistral-small-latest",
            messages=messages,
            max_tokens=300,
            temperature=0.7,
        )
        
        reply = response.choices[0].message.content.strip()
        logger.info(f"✅ Mirror response generated: {reply[:50]}...")
        return reply
        
    except Exception as e:
        logger.error(f"❌ Mirror response error: {e}")
        logger.exception("Full traceback:")
        return "I'm having trouble generating a response right now. Please try again."


async def get_cached_snapshot(db: AsyncSession, user_id: UUID):
    """Get snapshot from cache or database."""
    cache_key = str(user_id)
    
    # Check cache first
    if cache_key in _snapshot_cache:
        logger.debug(f"📦 Using cached snapshot for user {user_id}")
        # Return a simple dict-like object for cached data
        cached = _snapshot_cache[cache_key]
        # Fetch fresh from DB to ensure we have the model object
        snapshot = await PersonaRepository.get_latest_snapshot(db, user_id)
        return snapshot
    
    # Fetch from database
    snapshot = await PersonaRepository.get_latest_snapshot(db, user_id)
    
    if snapshot:
        # Cache it
        _snapshot_cache[cache_key] = {
            "persona_vector": snapshot.persona_vector,
            "stability_index": snapshot.stability_index,
        }
        logger.debug(f"💾 Cached snapshot for user {user_id}")
    
    return snapshot


def invalidate_snapshot_cache(user_id: UUID) -> None:
    """Invalidate cached snapshot for a user."""
    cache_key = str(user_id)
    if cache_key in _snapshot_cache:
        del _snapshot_cache[cache_key]
        logger.debug(f"🗑️ Invalidated snapshot cache for user {user_id}")


def analyze_message_style(message: str) -> Dict[str, any]:
    """
    Analyze the current message style for live mirroring.
    
    Returns dict with:
        - avg_sentence_length: Average words per sentence
        - punctuation_intensity: Exclamation/question marks count
        - has_slang: Boolean for casual language
        - emotional_markers: Count of emotional words/emojis
        - caps_intensity: Ratio of caps words
        - has_questions: Whether message contains questions
    """
    # Split into sentences
    sentences = re.split(r'[.!?]+', message)
    sentences = [s.strip() for s in sentences if s.strip()]
    
    # Calculate average sentence length
    if sentences:
        words_per_sentence = [len(s.split()) for s in sentences]
        avg_sentence_length = sum(words_per_sentence) / len(words_per_sentence)
    else:
        avg_sentence_length = len(message.split())
    
    # Count punctuation
    exclamation_count = message.count('!')
    question_count = message.count('?')
    punctuation_intensity = exclamation_count + question_count
    
    # Detect slang/casual language
    slang_markers = ['gonna', 'wanna', 'gotta', 'kinda', 'sorta', 'yeah', 'nah', 'like', 'just', 'really']
    lower_message = message.lower()
    has_slang = any(marker in lower_message for marker in slang_markers)
    
    # Detect emotional markers
    emotional_words = ['love', 'hate', 'happy', 'sad', 'angry', 'excited', 'worried', 'anxious', 'stressed', 'amazing', 'terrible', 'awesome']
    emotional_markers = sum(1 for word in emotional_words if word in lower_message)
    
    # Emojis or emotional punctuation
    if '!' in message or '?' in message or any(c in message for c in ['😊', '😂', '😢', '😠', '🥺', '💀', '🔥']):
        emotional_markers += 1
    
    # Caps intensity
    words = message.split()
    if words:
        caps_words = sum(1 for word in words if word.isupper() and len(word) > 1)
        caps_intensity = caps_words / len(words)
    else:
        caps_intensity = 0.0
    
    # Has questions
    has_questions = '?' in message
    
    return {
        "avg_sentence_length": round(avg_sentence_length, 1),
        "punctuation_intensity": punctuation_intensity,
        "has_slang": has_slang,
        "emotional_markers": emotional_markers,
        "caps_intensity": round(caps_intensity, 2),
        "has_questions": has_questions,
    }


def extract_key_traits(persona_vector: Dict) -> Dict[str, float]:
    """
    Extract key traits for mirroring from persona vector.
    
    Returns:
        emotional_intensity, emotional_stability, directness,
        expressiveness, analytical_thinking, decision_confidence
    """
    key_traits = {
        "emotional_intensity": 0.5,
        "emotional_stability": 0.5,
        "directness": 0.5,
        "expressiveness": 0.5,
        "analytical_thinking": 0.5,
        "decision_confidence": 0.5,
    }
    
    # Extract from persona vector
    for group_name, traits in persona_vector.items():
        for trait_name, trait_data in traits.items():
            if trait_name in key_traits:
                # Only use if confidence is reasonable
                if trait_data.get("confidence", 0) > 0.2:
                    key_traits[trait_name] = trait_data.get("score", 0.5)
    
    return key_traits


def build_mirror_system_prompt(
    persona_vector: Dict, 
    stability_index: float,
    message_style: Dict[str, any]
) -> str:
    """
    Build mirror system prompt with personality baseline and live style analysis.
    
    This creates "the user talking back to themselves at 110% clarity."
    
    Args:
        persona_vector: Structured personality traits
        stability_index: Overall profile stability
        message_style: Live message style analysis
        
    Returns:
        System prompt string
    """
    # Extract key traits
    traits = extract_key_traits(persona_vector)
    
    # Determine mirroring intensity based on stability
    if stability_index < STABILITY_THRESHOLD_UNSTABLE:
        mirror_strength = "light"
        stability_note = "Baseline emerging - mirror subtly"
    elif stability_index > STABILITY_THRESHOLD_STABLE:
        mirror_strength = "strong"
        stability_note = "Baseline stable - mirror confidently"
    else:
        mirror_strength = "moderate"
        stability_note = "Baseline developing - balanced mirroring"
    
    # Build trait profile description
    trait_profile = f"""Stored Personality Baseline:
• Emotional Intensity: {format_trait_score(traits['emotional_intensity'])} - DO NOT EXCEED THIS LEVEL
• Emotional Stability: {format_trait_score(traits['emotional_stability'])}
• Directness: {format_trait_score(traits['directness'])}
• Expressiveness: {format_trait_score(traits['expressiveness'])}
• Analytical Thinking: {format_trait_score(traits['analytical_thinking'])}
• Decision Confidence: {format_trait_score(traits['decision_confidence'])}

Stability Index: {stability_index:.2f} → {stability_note}"""
    
    # Build message style analysis
    style_description = f"""Current Message Style Analysis:
• Sentence Length: {message_style['avg_sentence_length']} words/sentence
• Punctuation: {message_style['punctuation_intensity']} marks
• Casual Language: {'Yes' if message_style['has_slang'] else 'No'}
• Emotional Markers: {message_style['emotional_markers']}
• Caps Usage: {int(message_style['caps_intensity'] * 100)}%
• Contains Questions: {'Yes' if message_style['has_questions'] else 'No'}"""
    
    # Build mirroring rules based on style
    style_rules = []
    
    if message_style['avg_sentence_length'] < 5:
        style_rules.append("• Match short, punchy sentences")
    elif message_style['avg_sentence_length'] > 15:
        style_rules.append("• Match longer, flowing sentences")
    else:
        style_rules.append("• Match moderate sentence rhythm")
    
    if message_style['has_slang']:
        style_rules.append("• Use casual, conversational language")
    else:
        style_rules.append("• Maintain clean, clear language")
    
    if message_style['punctuation_intensity'] > 2:
        style_rules.append("• Match their punctuation energy")
    
    if message_style['caps_intensity'] > 0.1:
        style_rules.append("• Use caps for emphasis where they do")
    
    if traits['analytical_thinking'] > 0.6 and message_style['avg_sentence_length'] > 10:
        style_rules.append("• Match analytical depth when they show it")
    
    if not message_style['has_questions']:
        style_rules.append("• Do NOT ask reflection-style questions unless they do")
    
    style_rules_text = "\n".join(style_rules)
    
    # Build complete mirror prompt
    prompt = f"""SYSTEM ROLE:
You are a Persona Mirror. You do NOT assist, guide, advise, or improve the user.

Your only job is to simulate what the USER themselves would say in this situation.

INPUT SOURCES:
1. Persona Profile (from Reflection Mode)
{trait_profile}

2. Current Message & Mood Style
{style_description}

OBJECTIVE:
Generate a response that is indistinguishable from something the user would naturally say.

STRICT RULES:

1. NO INTELLIGENCE INJECTION
- Do NOT add advice, suggestions, or solutions unless the user would naturally do so
- Do NOT improve the response quality beyond the user's typical behavior

2. BEHAVIORAL ACCURACY > RESPONSE QUALITY
- Match how the user ACTUALLY speaks, not how they SHOULD speak
- If the user is casual, blunt, confused, or imperfect → reflect that
{style_rules_text}
- Avoid generic AI phrasing

3. MIRROR, DON'T FIX
- Do NOT make responses more logical, structured, or helpful than the user typically would
- Preserve imperfections, hesitation, or lack of clarity if present in persona

4. MOOD INFLUENCE
- Reflect emotional state (e.g., stressed → shorter, reactive responses)
- Do NOT stabilize or correct mood

5. NO EXPLANATION MODE
- Do NOT explain reasoning
- Do NOT justify answers
- Just respond as the user

6. RESPONSE LENGTH MATCHING
- Match user's natural response length tendency based on input
- Avoid over-explaining

7. FORBIDDEN OUTPUTS:
- Advice ("you should...", "try this...")
- Structured guidance
- Teaching tone
- AI-like clarity improvements
- Empty philosophical filler

8. VALIDATION CHECK:
Before output, verify:
- "Would the user realistically type this?"
If NO → regenerate

OUTPUT STYLE:
- Raw, natural, human
- Slightly imperfect if needed
- Feels like the user, not an assistant
"""
    
    return prompt


def format_trait_score(score: float) -> str:
    """Format trait score with level and numeric value."""
    if score < 0.25:
        level = "Very Low"
    elif score < 0.4:
        level = "Low"
    elif score < 0.6:
        level = "Moderate"
    elif score < 0.75:
        level = "High"
    else:
        level = "Very High"
    
    return f"{level} ({score:.2f})"


def get_trait_level(score: float) -> str:
    """Convert score to level label."""
    if score < 0.25:
        return "Very Low"
    elif score < 0.4:
        return "Low"
    elif score < 0.6:
        return "Moderate"
    elif score < 0.75:
        return "High"
    else:
        return "Very High"


async def generate_baseline_mirror_response(message: str) -> str:
    """Generate a basic mirror response without personality data."""
    if not MISTRAL_AVAILABLE or not mistral_client:
        return "I'm still learning your style. Keep talking to me and I'll start mirroring you more accurately."
    
    # Analyze message style even without persona
    message_style = analyze_message_style(message)
    
    try:
        # Build a minimal mirror prompt
        style_note = ""
        if message_style['avg_sentence_length'] < 5:
            style_note = "Keep sentences short and direct."
        elif message_style['has_slang']:
            style_note = "Use casual, natural language."
        else:
            style_note = "Be clear and authentic."
        
        system_prompt = f"""You are mirroring the user's communication style. Their personality baseline is still developing.

Match their:
- Sentence rhythm ({message_style['avg_sentence_length']} words/sentence)
- Emotional tone (detected: {message_style['emotional_markers']} markers)
- Casual vs formal style ({'casual' if message_style['has_slang'] else 'neutral'})

{style_note}

Do NOT ask reflection questions unless they do.
Respond as if you're them talking back to themselves.
Keep it natural and concise."""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ]
        
        response = mistral_client.chat.complete(
            model="mistral-small-latest",
            messages=messages,
            max_tokens=200,
            temperature=0.7,
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        logger.error(f"❌ Baseline mirror error: {e}")
        return "Got it. What else?"
