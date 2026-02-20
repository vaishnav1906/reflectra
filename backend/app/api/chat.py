from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import random
import os
from typing import Dict, List, Optional
import logging
from datetime import datetime, timedelta
import re
from collections import Counter
from dotenv import load_dotenv
from pathlib import Path
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.database import get_db
from app.db import crud
from app.db.models import Message, BehavioralInsight
from app.schemas.db import ConversationListItem, ConversationListOut, MessageOut

# Load environment variables
load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

class ChatRequest(BaseModel):
    user_id: str
    conversation_id: Optional[str] = None
    text: str
    mode: str  # "reflection" or "mirror"

class ChatResponse(BaseModel):
    conversation_id: str
    title: Optional[str] = None
    reply: str
    mirror_active: bool
    confidence_level: str
    mode: str
    active_mirror_style: Optional[str] = None  # Currently active mirror style
    detected_emotion: Optional[str] = None  # Detected emotional tone

def init_mistral_client() -> None:
    global MISTRAL_AVAILABLE, mistral_client
    try:
        from mistralai import Mistral
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            raise ValueError("MISTRAL_API_KEY not found in environment")

        mistral_client = Mistral(api_key=api_key)
        MISTRAL_AVAILABLE = True
        logger.info(f"✅ Mistral client initialized with key: {api_key[:8]}...{api_key[-4:]}")
    except Exception as e:
        MISTRAL_AVAILABLE = False
        mistral_client = None
        logger.warning(f"⚠️ Mistral not available: {e}")


MISTRAL_AVAILABLE = False
mistral_client = None
init_mistral_client()

# Reflection mode responses - adaptive pattern recognition
REFLECTION_TEMPLATES = [
    "You keep circling back to {text}. That usually means there's something unresolved underneath. What's the real question here?",
    "There's a thread here: you frame {text} in a way that puts you outside the system. What changes if you see yourself as part of it?",
    "The pattern with {text} seems to be about control—or the lack of it. Where does that tension come from?",
]

# Mirror mode responses - unhinged personality mirroring
MIRROR_TEMPLATES = [
    "bruh {text}",
    "fr fr {text}",
    "nah but {text}",
    "lmao {text}",
]

REFLECTION_SYSTEM_PROMPT_BASE = """You are Reflection Mode in a personality-aware AI system.

Your goal is to provide sharp, insight-driven reflection — not generic emotional validation and not mechanical psychological analysis.

Core Behavior:

1. Adapt depth to context.
   - If the user message is short or neutral (e.g., "Hi", "ok", "thanks"), respond naturally and lightly.
   - Do NOT force pattern analysis without sufficient context.
   - Only perform deeper reflection if the user expresses emotion, confusion, contradiction, or recurring behavior.

2. When enough context exists:
   - Identify ONE meaningful behavioral or cognitive pattern.
   - Explain the mechanism behind it clearly (cause → behavior → consequence).
   - Avoid listing multiple possible causes.
   - Avoid sounding like a therapist or academic article.
   - Avoid phrases like:
        - "It's possible that…"
        - "Have you considered…"
        - "It could be that…"
        - "There may be…"
        - "It sounds like…"
        - "What I'm hearing is…"

3. Keep responses:
   - Direct
   - Natural
   - Conversational
   - Insightful but not dramatic
   - Calm and intelligent

4. Do not hallucinate hidden motives.
   - Base insights only on actual user statements.
   - If insufficient data exists, ask one simple clarifying question instead of analyzing.

5. End with at most ONE reflective question — only if it meaningfully advances insight.

6. If personality memory exists:
   - Integrate it subtly and naturally.
   - Do not explicitly reference "memory", "past logs", or "you mentioned before".
   - Do not restate obvious history.

Tone Target:
You should sound like a perceptive, thoughtful human who notices patterns — not a therapist template and not a diagnostic report.

Primary Goal:
Move the user toward clarity by offering one strong insight at a time."""

MIRROR_SYSTEM_PROMPT_BASE = """You are Persona Mirror — an amplified version of the user.

Your role is NOT to give generic advice.
Your role is to reflect the user's identity back to them through a specific personality lens.

You must:
- Speak AS the user would, but enhanced.
- Maintain the selected mirror style consistently.
- Never break character.
- Never mention you are an AI.
- Never describe your style explicitly.
- Never explain what you are doing.

You are not roleplaying a fictional character.
You are the user — intensified through a selected psychological tone.

Behavior Constraints:
- Stay coherent and intelligent.
- Do not overdo slang or exaggeration.
- Do not become repetitive.
- Avoid forced edginess.
- Adapt naturally to what the user says.
- If the user is serious, reduce exaggeration.
- If the user is joking, increase energy naturally.
- Always feel grounded in reality.

Your job is to mirror identity, not act like a cartoon."""

# Mirror Archetype Definitions
MIRROR_STYLES = {
    "dominant": {
        "name": "Dominant",
        "rules": """Tone:
- Confident
- Assertive
- Strong presence
- Direct but not toxic
- Controlled intensity

Speech Pattern:
- Short to medium sentences
- Punchy emphasis when needed
- Minimal filler words

Energy:
- Strong and commanding
- Radiates certainty
- No insecurity

Behavior:
- Turn doubt into power
- Reframe hesitation into action
- Never beg for validation
- Strengthen without dismissing feelings"""
    },
    "calm": {
        "name": "Calm Anchor",
        "rules": """Tone:
- Grounded
- Stable
- Emotionally regulated
- Clear and composed

Speech Pattern:
- Smooth flow
- Thoughtful pacing
- No slang

Energy:
- Low but steady
- Emotionally intelligent
- Slows down chaos

Behavior:
- De-escalate stress
- Provide clarity
- Encourage reflection
- Avoid hype language"""
    },
    "challenger": {
        "name": "Challenger",
        "rules": """Tone:
- Intense
- Blunt
- No nonsense
- Firm but not insulting

Speech Pattern:
- Direct
- Crisp
- No sugarcoating

Energy:
- Confrontational but productive
- Pushes accountability

Behavior:
- Call out excuses
- Challenge avoidance
- Confront behavior, not identity
- Attack behavior, not person"""
    },
    "chaotic": {
        "name": "Chaotic Energy",
        "rules": """Tone:
- High energy
- Playful unpredictability
- Dynamic and bold

Speech Pattern:
- Mixed sentence lengths
- Occasional emphasis
- Controlled spontaneity

Energy:
- Fast-moving
- Motivational surge
- Slightly dramatic but smart

Behavior:
- Amplify excitement
- Challenge boredom
- Keep logic intact
- Stay coherent despite intensity"""
    },
    "dark_wit": {
        "name": "Dark Wit",
        "rules": """Tone:
- Intelligent sarcasm
- Dry wit
- Sharp observations
- Psychological edge

Speech Pattern:
- Clever phrasing
- Controlled irony

Energy:
- Calm surface
- Subtle intensity

Behavior:
- Use humor to expose truth
- Sharp but controlled
- Never offensive or hateful
- Keep it psychologically sharp"""
    },
    "optimist": {
        "name": "Uplifted Optimist",
        "rules": """Tone:
- Encouraging
- Positive reinforcement
- Energizing
- Light

Speech Pattern:
- Warm
- Positive phrasing

Energy:
- High but stable
- Not childish

Behavior:
- Highlight strengths and wins
- Reinforce confidence
- Avoid fake positivity"""
    }
}

REFLECTION_FORBIDDEN_LABELS = [
    "Observed Pattern:",
    "What It Might Indicate:",
    "Reflective Challenge:",
    "One Focused Question:",
    "It's possible that",
    "It could be that",
    "There may be",
    "Have you considered",
    "You might want to",
    "It sounds like",
    "What I'm hearing is",
    "That's completely valid",
    "That's a valid concern",
    "Many people experience",
    "It's natural to feel",
]

MIRROR_BANNED_PHRASES = [
    "you tend to",
    "this suggests",
    "it seems that",
    "you seem",
    "it looks like",
    "what this indicates",
    "observed pattern",
    "what it might indicate",
    "reflective challenge",
    "it sounds like you're",
    "what I'm hearing",
    "that must be",
    "that must feel",
    "I can see how",
    "it makes sense that",
    "have you considered",
    "you might want to",
    "let me ask you",
    "what if you tried",
    "the thing is",
]

MODEL_PARAMS = {
    "reflection": {"temperature": 0.6, "max_tokens": 280},  # Increased for structured pattern synthesis
    "mirror": {"temperature": 0.85, "max_tokens": 150},  # Higher temp for unhinged chaos
}

# In-memory storage (swap with database for persistence).
PERSONALITY_PROFILES: Dict[str, Dict[str, object]] = {}
COMMUNICATION_PROFILES: Dict[str, Dict[str, object]] = {}
CONVERSATION_HISTORY: Dict[str, Dict[str, List[Dict[str, str]]]] = {}
EMOTIONAL_STATE_HISTORY: Dict[str, List[str]] = {}  # Track recent emotional states per user

def get_personality_profile(user_id: str) -> Dict[str, object]:
    return PERSONALITY_PROFILES.setdefault(user_id, {
        "themes": Counter(),
        "traits": Counter(),
        "values": Counter(),
        "stressors": Counter(),
        "insight_notes": [],
        "updated_at": None,
    })

def get_communication_profile(user_id: str) -> Dict[str, object]:
    return COMMUNICATION_PROFILES.setdefault(user_id, {
        "avg_sentence_length": 0.0,
        "tone": "neutral",
        "tone_counts": Counter(),
        "emotional_intensity": 0.0,
        "directness_level": 0.0,
        "logical_depth": 0.0,
        "question_frequency": 0.0,
        "common_phrases": [],
        "phrase_counts": Counter(),
        "sample_count": 0,
        "updated_at": None,
    })

def split_sentences(text: str) -> List[str]:
    raw = re.split(r"[.!?]+", text)
    return [segment.strip() for segment in raw if segment.strip()]

def extract_words(text: str) -> List[str]:
    return re.findall(r"\b\w+\b", text.lower())

# ============================================================================
# ADAPTIVE PERSONA MIRROR SYSTEM
# ============================================================================
# This system automatically detects the user's emotional state and selects
# the appropriate mirror archetype to reflect their identity in a strengthening way.
#
# Flow:
# 1. Detect emotional tone from user's message
# 2. Map emotion to appropriate mirror archetype:
#    - Insecurity → Dominant (inject strength, not pity)
#    - Stress/Overwhelm → Calm Anchor (ground them)
#    - Anger → Challenger (productive confrontation)
#    - Playfulness → Chaotic Energy (match energy)
#    - Sarcasm/Irony → Dark Wit (intelligent edge)
#    - Happiness/Excitement → Uplifted Optimist (amplify wins)
#    - Neutral → Balanced version of previous archetype
# 3. Maintain consistency unless emotional shift is significant
# 4. Apply selected archetype without announcing it
#
# Manual style selection is DISABLED - only auto-detection is used.
# ============================================================================

EMOTIONAL_MARKERS = {
    "insecurity": ["i don't know", "maybe", "not sure", "probably wrong", "doubt", "uncertain", "hesitant", "scared", "nervous", "idk", "unsure", "confused", "lost"],
    "stress": ["stressed", "overwhelmed", "anxious", "worried", "pressure", "struggling", "can't handle", "too much", "exhausted", "tired", "drowning", "burnout"],
    "anger": ["pissed", "angry", "furious", "mad", "hate", "fuck", "bullshit", "ridiculous", "unacceptable", "done with", "fed up", "irritated"],
    "playful": ["lol", "lmao", "haha", "😂", "💀", "bruh", "nah", "lowkey", "highkey", "vibes", "bet", "tbh"],
    "sarcasm": ["sure", "yeah right", "oh great", "wonderful", "fantastic", "obviously", "totally", "yeah okay", "perfect", "lovely"],
    "excitement": ["yay", "woohoo", "omg", "yes", "let's go", "pumped", "thrilled", "can't wait", "hyped", "stoked"],
    "happiness": ["happy", "great", "awesome", "amazing", "love", "excellent", "wonderful"],
}

# Slang hype words for excitement/playful detection
SLANG_HYPE_WORDS = ["yo", "bruh", "lmao", "lmaooo", "brooo", "yooo", "yoooo", "fr", "frfr", "fr fr", "omfg"]

def detect_emotional_tone(text: str, profile: Dict[str, object]) -> str:
    """
    You are an emotion classifier.

    Analyze the user's message and classify its emotional tone into ONE of the following categories:

    - insecurity
    - stress
    - anger
    - playful
    - sarcasm
    - excitement
    - happiness
    - neutral

    Rules:

    - Detect intensity markers:
      * Elongated words (e.g., "Yoooo", "Noooo")
      * Multiple punctuation (!!!, ???)
      * Slang energy ("bruh", "yo", "lmaooo")
      * Caps emphasis

    - Short messages CAN still carry high emotional energy.
    - If the message shows enthusiasm or hype → classify as excitement.
    - If playful tone or exaggerated vowel stretching → classify as playful.
    - If sarcastic phrasing → classify as sarcasm.
    - Only classify as neutral if truly flat and emotionless.

    Return ONLY the label. No explanation.
    """
    lower = text.lower()
    original_text = text
    
    # === PREPROCESSING: Detect intensity markers ===
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
    
    # === BOOST LOGIC: Apply intensity marker boosts ===
    # If elongation OR slang hype OR multiple exclamations detected:
    # Boost probability toward excitement or playful
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

def map_emotion_to_mirror_style(emotion: str, intensity: float = 0.5) -> str:
    """
    Map detected emotion to appropriate mirror archetype.
    
    Mapping:
    - insecurity → dominant (inject strength)
    - stress → calm (ground them)
    - anger → challenger (productive confrontation)
    - playful → chaotic (match energy)
    - sarcasm → dark_wit (intelligent edge)
    - excitement → chaotic (amplify energy)
    - happiness → optimist (amplify wins)
    - neutral → neutral (balanced)
    """
    emotion_to_style = {
        "insecurity": "dominant",
        "stress": "calm",
        "anger": "challenger",
        "playful": "chaotic",
        "sarcasm": "dark_wit",
        "excitement": "chaotic",
        "happiness": "optimist",
        "neutral": "calm",  # Keep calm for neutral to maintain stability
    }
    
    return emotion_to_style.get(emotion, "calm")

def get_adaptive_mirror_style(user_id: str, user_text: str, profile: Dict[str, object]) -> tuple[str, str]:
    """
    Determine mirror archetype adaptively based on emotional detection.
    Returns: (selected_style, detected_emotion)
    
    Manual selection is disabled - only auto-detection is used.
    Maintains consistency unless emotional shift is significant.
    """
    # Detect current emotion
    detected_emotion = detect_emotional_tone(user_text, profile)
    suggested_style = map_emotion_to_mirror_style(detected_emotion)
    
    # Get emotional history for this user
    emotion_history = EMOTIONAL_STATE_HISTORY.setdefault(user_id, [])
    
    # Maintain consistency: only switch if emotion is different from recent pattern
    if len(emotion_history) >= 2:
        recent_emotions = emotion_history[-2:]
        # If recent emotions are consistent and different from current, require stronger signal
        if all(e == recent_emotions[0] for e in recent_emotions) and detected_emotion != recent_emotions[0]:
            # Keep previous style unless current emotion appears twice in a row
            if len(emotion_history) >= 1 and detected_emotion != emotion_history[-1]:
                # Use previous style for consistency
                previous_emotion = emotion_history[-1]
                suggested_style = map_emotion_to_mirror_style(previous_emotion)
    
    # Update emotional history (keep last 5)
    emotion_history.append(detected_emotion)
    if len(emotion_history) > 5:
        emotion_history.pop(0)
    
    return (suggested_style, detected_emotion)

def build_reflection_system_prompt(profile: Dict[str, object]) -> str:
    summary = summarize_personality_profile(profile)
    return f"{REFLECTION_SYSTEM_PROMPT_BASE}\n\nPersonality profile (use as context, do not label sections):\n{summary}"

def build_mirror_system_prompt(profile: Dict[str, object], style: str = "dominant") -> str:
    """Build mirror system prompt with specific archetype style"""
    summary = summarize_communication_profile(profile)
    
    # Get style rules, default to dominant if invalid
    style_config = MIRROR_STYLES.get(style, MIRROR_STYLES["dominant"])
    style_name = style_config["name"]
    style_rules = style_config["rules"]
    
    return f"""{MIRROR_SYSTEM_PROMPT_BASE}

User Profile:
{summary}

Mirror Archetype: {style_name}

Archetype Rules:
{style_rules}

Adaptation Rule:
If the user's emotional state shifts significantly, subtly adapt intensity while preserving the core archetype behavior.
"""

def get_user_history(user_id: str, mode: str) -> List[Dict[str, str]]:
    user_bucket = CONVERSATION_HISTORY.setdefault(user_id, {})
    return user_bucket.setdefault(mode, [])

def summarize_personality_profile(profile: Dict[str, object]) -> str:
    themes = ", ".join([item for item, _ in profile["themes"].most_common(3)])
    traits = ", ".join([item for item, _ in profile["traits"].most_common(3)])
    values = ", ".join([item for item, _ in profile["values"].most_common(3)])
    stressors = ", ".join([item for item, _ in profile["stressors"].most_common(3)])
    notes = profile["insight_notes"][-2:]
    note_text = " | ".join(notes)
    return (
        f"Themes: {themes or 'unknown'}\n"
        f"Traits: {traits or 'unknown'}\n"
        f"Values: {values or 'unknown'}\n"
        f"Stressors: {stressors or 'unknown'}\n"
        f"Recent insight notes: {note_text or 'none'}"
    )

def summarize_communication_profile(profile: Dict[str, object]) -> str:
    common_phrases = ", ".join(profile["common_phrases"][:5])
    return (
        f"avg_sentence_length: {profile['avg_sentence_length']:.1f}\n"
        f"tone: {profile['tone']}\n"
        f"emotional_intensity: {profile['emotional_intensity']:.2f}\n"
        f"directness_level: {profile['directness_level']:.2f}\n"
        f"logical_depth: {profile['logical_depth']:.2f}\n"
        f"question_frequency: {profile['question_frequency']:.2f}\n"
        f"common_phrases: {common_phrases or 'none'}"
    )

def update_personality_profile(profile: Dict[str, object], user_text: str, reply: str) -> None:
    theme_keywords = {
        "identity": ["who i am", "identity", "self"],
        "purpose": ["purpose", "meaning", "why"],
        "control": ["control", "power", "decide"],
        "relationships": ["relationship", "people", "family", "friend"],
        "work": ["work", "career", "job"],
        "growth": ["change", "growth", "improve"],
    }
    trait_keywords = {
        "introspective": ["reflect", "introspect", "think a lot"],
        "driven": ["ambition", "driven", "goal"],
        "anxious": ["anxious", "worried", "overthink"],
        "independent": ["independent", "alone", "self-reliant"],
        "structured": ["plan", "schedule", "routine"],
        "adaptive": ["flexible", "adapt", "pivot"],
    }
    value_keywords = {
        "authenticity": ["authentic", "real", "honest"],
        "stability": ["stable", "security", "certainty"],
        "freedom": ["freedom", "autonomy", "choice"],
        "connection": ["connection", "belong", "community"],
        "achievement": ["achievement", "success", "win"],
    }
    stressor_keywords = {
        "uncertainty": ["uncertain", "unknown", "unclear"],
        "conflict": ["conflict", "argument", "tension"],
        "pressure": ["pressure", "overwhelmed", "stress"],
        "rejection": ["rejection", "excluded", "ignored"],
    }

    lower_text = user_text.lower()
    for theme, keywords in theme_keywords.items():
        if any(kw in lower_text for kw in keywords):
            profile["themes"][theme] += 1
    for trait, keywords in trait_keywords.items():
        if any(kw in lower_text for kw in keywords):
            profile["traits"][trait] += 1
    for value, keywords in value_keywords.items():
        if any(kw in lower_text for kw in keywords):
            profile["values"][value] += 1
    for stressor, keywords in stressor_keywords.items():
        if any(kw in lower_text for kw in keywords):
            profile["stressors"][stressor] += 1

    insight = extract_insight_sentence(reply)
    if insight:
        profile["insight_notes"].append(insight)
        profile["insight_notes"] = profile["insight_notes"][-6:]

    profile["updated_at"] = datetime.utcnow().isoformat() + "Z"

def update_communication_profile(profile: Dict[str, object], user_text: str) -> None:
    sentences = split_sentences(user_text)
    words = extract_words(user_text)
    sentence_count = max(len(sentences), 1)
    word_count = max(len(words), 1)
    lower_text = user_text.lower()

    avg_sentence_length = word_count / sentence_count
    question_frequency = user_text.count("?") / sentence_count

    intensity_markers = sum(1 for ch in user_text if ch == "!")
    intensity_words = sum(1 for word in words if word in {"very", "really", "super", "extremely"})
    emotional_intensity = min(1.0, (intensity_markers + intensity_words) / 5.0)

    hedge_phrases = ["maybe", "perhaps", "sorta", "kind of", "i think"]
    directive_words = {"need", "must", "should", "tell", "do", "fix"}
    hedge_count = sum(1 for phrase in hedge_phrases if phrase in lower_text)
    directive_count = sum(1 for word in words if word in directive_words)
    directness = min(1.0, max(0.0, (directive_count - hedge_count + 1) / 5.0))

    logical_markers = {"because", "therefore", "since", "so", "thus", "however", "although", "while", "whereas"}
    logical_depth = min(1.0, sum(1 for word in words if word in logical_markers) / 5.0)

    tone = "neutral"
    if any(token in user_text.lower() for token in ["lol", "gonna", "kinda", "nah", "yeah"]):
        tone = "casual"
    if any(token in user_text.lower() for token in ["therefore", "furthermore", "however", "thus"]):
        tone = "formal"
    if intensity_markers >= 2 or any(word.isupper() and len(word) > 3 for word in user_text.split()):
        tone = "intense"

    sample_count = profile["sample_count"]
    profile["avg_sentence_length"] = (profile["avg_sentence_length"] * sample_count + avg_sentence_length) / (sample_count + 1)
    profile["question_frequency"] = (profile["question_frequency"] * sample_count + question_frequency) / (sample_count + 1)
    profile["emotional_intensity"] = (profile["emotional_intensity"] * sample_count + emotional_intensity) / (sample_count + 1)
    profile["directness_level"] = (profile["directness_level"] * sample_count + directness) / (sample_count + 1)
    profile["logical_depth"] = (profile["logical_depth"] * sample_count + logical_depth) / (sample_count + 1)

    profile["tone_counts"][tone] += 1
    profile["tone"] = profile["tone_counts"].most_common(1)[0][0]

    bigrams = [f"{words[i]} {words[i + 1]}" for i in range(len(words) - 1)]
    for phrase in bigrams:
        profile["phrase_counts"][phrase] += 1
    profile["common_phrases"] = [item for item, _ in profile["phrase_counts"].most_common(5)]

    profile["sample_count"] = sample_count + 1
    profile["updated_at"] = datetime.utcnow().isoformat() + "Z"

def count_questions(text: str) -> int:
    return text.count("?")

def extract_insight_sentence(text: str) -> str:
    sentences = re.split(r"(?<=[.!])\s+", text.strip())
    for sentence in sentences:
        if "?" not in sentence and sentence:
            return sentence.strip()
    return ""

def strip_forbidden_labels(text: str) -> str:
    updated = text
    for label in REFLECTION_FORBIDDEN_LABELS:
        updated = updated.replace(label, "").strip()
    return updated

def limit_questions(text: str) -> str:
    seen = 0
    output = []
    for char in text:
        if char == "?":
            if seen == 0:
                output.append(char)
                seen += 1
            else:
                output.append(".")
        else:
            output.append(char)
    return "".join(output).strip()

def ensure_insight_before_question(text: str, profile: Dict[str, object]) -> str:
    if "?" not in text:
        return text
    question_index = text.find("?")
    pre_question = text[:question_index].strip()
    has_sentence_break = any(punct in pre_question for punct in [".", "!", "\n"])
    if pre_question and (len(pre_question) > 40 or has_sentence_break):
        return text

    fallback = build_default_insight(profile)
    return f"{fallback} {text}".strip()

def build_default_insight(profile: Dict[str, object]) -> str:
    themes = [item for item, _ in profile["themes"].most_common(1)]
    traits = [item for item, _ in profile["traits"].most_common(1)]
    if themes:
        return f"A recurring thread in your reflections centers on {themes[0]}, which still feels active for you."
    if traits:
        return f"There is a consistent tone in how you approach this, and it seems connected to your {traits[0]} side."
    return "There is a consistent thread in how you describe this, and it still feels active for you."

def build_default_question(profile: Dict[str, object]) -> str:
    values = [item for item, _ in profile["values"].most_common(1)]
    stressors = [item for item, _ in profile["stressors"].most_common(1)]
    if values:
        return f"How does this connect to your need for {values[0]}?"
    if stressors:
        return f"What part of the {stressors[0]} feels most present right now?"
    return "What feels most important to understand about this right now?"

def validate_reflection_response(text: str, profile: Dict[str, object]) -> str:
    updated = strip_forbidden_labels(text)
    updated = ensure_insight_before_question(updated, profile)
    updated = limit_questions(updated)
    if count_questions(updated) == 0:
        updated = f"{updated} {build_default_question(profile)}".strip()
    updated = limit_questions(updated)
    return updated

def validate_mirror_response(text: str, user_text: str, profile: Dict[str, object]) -> str:
    if violates_mirror_rules(text):
        return local_mirror_reply(user_text, profile)
    return text

def violates_mirror_rules(text: str) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in MIRROR_BANNED_PHRASES)

def is_echo_reply(reply: str, user_text: str) -> bool:
    def normalize(value: str) -> str:
        return re.sub(r"\s+", " ", value.strip().lower())

    return normalize(reply) == normalize(user_text)

def local_mirror_reply(user_text: str, profile: Dict[str, object]) -> str:
    """Generate unhinged personality-mirrored response matching chaos and energy"""
    text = user_text.strip()
    if not text:
        return "..."

    lower = text.lower()
    intensity = float(profile.get("emotional_intensity", 0.0))
    directness = float(profile.get("directness_level", 0.0))

    # Detect style markers
    has_elongation = bool(re.search(r"([a-z])\1{2,}", lower))
    has_profanity = any(word in lower for word in ["fuck", "shit", "damn", "hell", "ass", "bitch", "wtf", "omg"])
    has_caps = bool(re.search(r"[A-Z]{2,}", text))
    multiple_punct = bool(re.search(r"[!?]{2,}", text))
    has_ellipsis = "..." in text
    ends_with_punct = bool(re.search(r"[.!?]+$", text))
    is_mostly_lower = sum(1 for ch in text if ch.isalpha() and ch.islower()) >= sum(1 for ch in text if ch.isalpha()) * 0.7

    # Detect conversational energy
    is_playful = any(word in lower for word in ["lol", "lmao", "haha", "😂", "💀", "omg", "bruh"])
    is_very_chaotic = (has_caps and multiple_punct) or (has_elongation and multiple_punct)
    is_chaotic = has_caps or multiple_punct or has_elongation
    is_blunt = directness > 0.7 or (len(text.split()) < 8 and not lower.endswith("?"))
    is_teasing = any(word in lower for word in ["jk", "kidding", "tho", "but like", "nah but"])
    is_hyped = has_caps or multiple_punct or intensity > 0.7

    # Unhinged reactive starters - match and escalate
    if is_very_chaotic:
        leads = ["YO", "YOOO", "NAH FR", "BROOOO", "WAIT", "LMAOOOO"]
        lead = random.choice(leads)
    elif is_playful and has_profanity:
        leads = ["lmao fr", "nah bro", "bruh fr", "deadass", "fr tho"]
        lead = random.choice(leads)
    elif is_playful:
        leads = ["lmao", "bruh", "nah fr", "fr fr", "honestly"]
        lead = random.choice(leads)
    elif is_chaotic:
        leads = ["YO", "FR", "NAH", "BRO", "WAIT"]
        lead = random.choice(leads)
    elif is_blunt and has_profanity:
        leads = ["yeah", "nah", "fr", "bruh", "facts"]
        lead = random.choice(leads)
    elif is_blunt:
        leads = ["yeah", "nah", "fr", "true"]
        lead = random.choice(leads)
    elif is_teasing:
        leads = ["lol ok but", "nah fr tho", "bruh", "okay but"]
        lead = random.choice(leads)
    else:
        leads = ["yeah", "fr", "nah", "honestly", "true"]
        lead = random.choice(leads)

    # Build punchy reactive response
    if lower.endswith("?"):
        # Questions - answer directly with their energy
        if is_very_chaotic or has_profanity:
            base = random.choice(["absolutely", "hell yeah", "probably lol", "idk honestly", "maybe fr"])
        elif is_playful:
            base = random.choice(["probably lmao", "idk fr", "maybe", "honestly yeah"])
        elif is_blunt:
            base = random.choice(["yeah", "nah", "maybe", "depends"])
        else:
            base = random.choice(["yeah probably", "idk maybe", "could be"])
    elif any(lower.startswith(prefix) for prefix in ["i feel", "i'm feel", "im feel", "feeling"]):
        # Emotion sharing - mirror intensity, don't validate
        if has_profanity or intensity > 0.7:
            base = random.choice(["same tbh", "felt", "big mood fr", "relatable af"])
        elif is_playful:
            base = random.choice(["mood", "fr same", "felt that", "honestly same"])
        else:
            base = random.choice(["mood", "same", "felt"])
    elif any(lower.startswith(prefix) for prefix in ["i ", "im ", "i'm "]):
        # Personal statements - punchy reactions
        if has_profanity:
            base = random.choice(["same energy", "felt", "real", "facts", "based"])
        else:
            base = random.choice(["real", "facts", "fair", "makes sense", "true"])
    elif has_profanity or is_hyped:
        # High energy - match it
        base = random.choice(["FACTS", "fr fr", "real", "felt", "honestly", "same"])
    else:
        # General - short reactive
        base = random.choice(["true", "fair", "yeah", "fr", "facts"])

    # Add profanity if they used it (mirror intensity)
    if has_profanity and random.random() > 0.6:
        if "fuck" in lower or "wtf" in lower:
            base = f"{base} lmao"
        elif "shit" in lower or "damn" in lower:
            base = f"{base} fr"

    # Escalate playfulness
    if is_playful and random.random() > 0.6:
        emojis = ["😭", "💀", "😂"]
        base = f"{base} {random.choice(emojis)}"

    # Chaos punctuation - match and escalate
    if multiple_punct:
        if "!" in text:
            ending = "!" * random.randint(1, 3)
        elif "?" in text:
            ending = "?" * random.randint(1, 2)
        else:
            ending = "!"
    elif has_ellipsis:
        ending = "..."
    elif is_hyped or is_very_chaotic:
        ending = "!" if random.random() > 0.4 else "!!"
    elif is_playful:
        ending = "" if random.random() > 0.6 else "!"
    else:
        ending = ""

    # Build reply
    reply = f"{lead} {base}{ending}".strip()

    # Match elongations (escalate slightly)
    if has_elongation:
        # Find elongated words and mirror them
        elongate_targets = ["yeah", "no", "so", "fr", "bro", "nah", "yo"]
        for target in elongate_targets:
            if target in reply.lower():
                extra = random.choice(["o", "oo", "ooo"])
                reply = re.sub(rf"\b{target}\b", f"{target}{extra}", reply, flags=re.IGNORECASE)
                break

    # Match capitalization chaos
    if is_very_chaotic and has_caps:
        # Keep high caps for chaos
        pass
    elif is_mostly_lower and not is_very_chaotic:
        reply = reply.lower()

    # Remove punctuation if they didn't use it
    if not ends_with_punct and not ending and not is_chaotic:
        reply = reply.rstrip(".!?")

    return reply

async def generate_llm_response(system_prompt: str, model_params: Dict[str, object], history: List[Dict[str, str]]) -> Optional[str]:
    """Generate response using Mistral AI"""
    
    if MISTRAL_AVAILABLE and os.getenv("MISTRAL_API_KEY"):
        try:
            logger.info("🤖 Using Mistral AI for response generation")
            
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(history)
            
            response = mistral_client.chat.complete(
                model="mistral-small-latest",
                messages=messages,
                max_tokens=model_params["max_tokens"],
                temperature=model_params["temperature"],
            )
            
            reply = response.choices[0].message.content.strip()
            logger.info(f"✅ Mistral response received: {reply[:50]}...")
            return reply
            
        except Exception as e:
            logger.error(f"❌ Mistral error: {e}")
            logger.error(f"Full error details: {type(e).__name__}: {str(e)}")
    
    return None


async def generate_conversation_title(user_message: str) -> str:
    """Generate a 3-5 word summary title for a conversation"""
    if MISTRAL_AVAILABLE and os.getenv("MISTRAL_API_KEY"):
        try:
            logger.info("📝 Generating conversation title with AI")
            
            system_prompt = "You are a helpful assistant that creates very short conversation titles. Generate a 3-5 word title that summarizes the topic. Return ONLY the title, nothing else."
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Create a 3-5 word title for this message: {user_message}"}
            ]
            
            response = mistral_client.chat.complete(
                model="mistral-small-latest",
                messages=messages,
                max_tokens=20,
                temperature=0.7,
            )
            
            title = response.choices[0].message.content.strip()
            # Remove quotes if present
            title = title.strip('"\'')
            logger.info(f"✅ Generated title: {title}")
            return title
            
        except Exception as e:
            logger.error(f"❌ Title generation error: {e}")
    
    # Fallback: use first 40 characters
    return user_message[:40] + ("..." if len(user_message) > 40 else "")

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)) -> ChatResponse:
    """
    Process chat message and return AI response.
    Creates new conversation if conversation_id is None.
    Stores all messages in database.
    Falls back to templates if LLM is not available.
    """
    logger.info(f"💬 Received message in {request.mode} mode from user {request.user_id}")
    
    if request.mode not in {"reflection", "mirror"}:
        raise HTTPException(status_code=400, detail="Invalid mode. Use 'reflection' or 'mirror'.")

    user_id_uuid = UUID(request.user_id)
    conversation_id_uuid = UUID(request.conversation_id) if request.conversation_id else None
    conversation_title = None

    # Handle conversation creation or retrieval
    if conversation_id_uuid is None:
        # Generate title for new conversation
        conversation_title = await generate_conversation_title(request.text)
        logger.info(f"📝 Creating new conversation with title: {conversation_title}")
        
        # Create new conversation
        conversation = await crud.create_conversation(
            db=db,
            user_id=user_id_uuid,
            title=conversation_title,
            mode=request.mode,
            metadata={},
        )
        conversation_id_uuid = conversation.id
        logger.info(f"✅ Created conversation {conversation_id_uuid} with mode: {request.mode}")
    else:
        # Get existing conversation
        conversation = await crud.get_conversation_by_id(
            db=db,
            conversation_id=conversation_id_uuid,
            user_id=user_id_uuid,
        )
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Validate that conversation mode matches request mode
        if conversation.mode != request.mode:
            raise HTTPException(
                status_code=400, 
                detail=f"Conversation mode '{conversation.mode}' does not match request mode '{request.mode}'"
            )
        
        conversation_title = conversation.title
        logger.info(f"✅ Using existing conversation {conversation_id_uuid} with mode: {conversation.mode}")

    # Get conversation history from in-memory storage (for AI context)
    history = get_user_history(request.user_id, request.mode)
    history.append({"role": "user", "content": request.text})

    # Update profiles
    personality_profile = get_personality_profile(request.user_id)
    communication_profile = get_communication_profile(request.user_id)
    update_communication_profile(communication_profile, request.text)

    # Track active mirror style and detected emotion
    active_mirror_style = None
    detected_emotion = None

    if request.mode == "reflection":
        system_prompt = build_reflection_system_prompt(personality_profile)
        model_params = MODEL_PARAMS["reflection"]
    else:
        # Adaptive Mirror Mode: auto-detect emotion and select appropriate archetype
        # Manual selection is disabled - only auto-detection is used
        active_mirror_style, detected_emotion = get_adaptive_mirror_style(
            user_id=request.user_id,
            user_text=request.text,
            profile=communication_profile
        )
        
        logger.info(f"🎭 Mirror Mode - Detected: {detected_emotion} → Archetype: {active_mirror_style}")
        
        system_prompt = build_mirror_system_prompt(communication_profile, style=active_mirror_style)
        model_params = MODEL_PARAMS["mirror"]

    # Generate AI response
    reply = await generate_llm_response(system_prompt, model_params, history)
    if reply and is_echo_reply(reply, request.text):
        logger.warning("⚠️ LLM reply echoed user input; falling back to templates")
        reply = None
    
    # Fall back to templates if LLM not available
    if not reply:
        logger.info("📝 Using template response (LLM not available)")
        if request.mode == "mirror":
            reply = local_mirror_reply(request.text, communication_profile)
        else:  # reflection mode
            sanitized = re.sub(r"[?]+", "", request.text).strip()
            template = random.choice(REFLECTION_TEMPLATES)
            reply = template.format(text=sanitized)
        
    if request.mode == "reflection":
        reply = validate_reflection_response(reply, personality_profile)
        update_personality_profile(personality_profile, request.text, reply)
    else:
        reply = validate_mirror_response(reply, request.text, communication_profile)

    history.append({"role": "assistant", "content": reply})

    # Store user message in database
    logger.info(f"💾 Storing user message for conversation {conversation_id_uuid}")
    try:
        user_message = await crud.create_message(
            db=db,
            user_id=user_id_uuid,
            conversation_id=conversation_id_uuid,
            role="user",
            content=request.text,
            embedding=None,
            token_count=None,
        )
        logger.info(f"✅ Stored user message {user_message.id}")
    except Exception as e:
        logger.error(f"❌ Failed to store user message: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to store user message: {str(e)}")

    # Store AI response in database
    logger.info(f"💾 Storing assistant message for conversation {conversation_id_uuid}")
    try:
        assistant_message = await crud.create_message(
            db=db,
            user_id=user_id_uuid,
            conversation_id=conversation_id_uuid,
            role="assistant",
            content=reply,
            embedding=None,
            token_count=None,
        )
        logger.info(f"✅ Stored assistant message {assistant_message.id}")
    except Exception as e:
        logger.error(f"❌ Failed to store assistant message: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to store assistant message: {str(e)}")

    logger.info(f"✅ Generated response and stored 2 messages for conversation {conversation_id_uuid}")
    
    return ChatResponse(
        conversation_id=str(conversation_id_uuid),
        title=conversation_title,
        reply=reply,
        mirror_active=request.mode == "mirror",
        confidence_level="medium",
        mode=request.mode,
        active_mirror_style=active_mirror_style,
        detected_emotion=detected_emotion
    )


@router.get("/conversations", response_model=ConversationListOut)
async def list_conversations(
    user_id: str, 
    mode: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
) -> ConversationListOut:
    """Get list of conversations for a user, optionally filtered by mode"""
    logger.info(f"\n{'='*60}")
    logger.info(f"📋 GET /conversations endpoint called")
    logger.info(f"📥 Request params: user_id={user_id}, mode={mode}")
    logger.info(f"⚠️ MODE FILTERING TEMPORARILY DISABLED FOR DEBUGGING")
    logger.info(f"{'='*60}")
    
    try:
        user_id_uuid = UUID(user_id)
        logger.info(f"🔍 Converted user_id string to UUID: {user_id_uuid}")
        logger.info(f"📊 UUID type: {type(user_id_uuid)}")
        
        conversations = await crud.get_user_conversations(
            db=db, 
            user_id=user_id_uuid,
            mode=mode  # Passed but ignored in crud function
        )
        
        logger.info(f"\n📊 Retrieved {len(conversations)} conversations from database")
        
        # Log conversation details for debugging
        for idx, conv in enumerate(conversations, 1):
            logger.info(f"  {idx}. Conversation:")
            logger.info(f"     - id: {conv.id}")
            logger.info(f"     - user_id: {conv.user_id}")
            logger.info(f"     - mode: {conv.mode}")
            logger.info(f"     - title: '{conv.title}'")
            logger.info(f"     - created_at: {conv.created_at}")
        
        conversation_list = [
            ConversationListItem(
                id=str(conv.id),
                title=conv.title,
                created_at=str(conv.created_at),
            )
            for conv in conversations
        ]
        
        logger.info(f"\n✅ Returning {len(conversation_list)} conversations to client")
        logger.info(f"📤 Response structure: ConversationListOut with {len(conversation_list)} items")
        logger.info(f"{'='*60}\n")
        
        return ConversationListOut(conversations=conversation_list)
    
    except ValueError as e:
        logger.error(f"❌ Invalid UUID format for user_id '{user_id}': {e}")
        raise HTTPException(status_code=400, detail=f"Invalid user_id format: {str(e)}")
    except Exception as e:
        logger.error(f"❌ Error fetching conversations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageOut])
async def get_conversation_messages(
    conversation_id: str,
    user_id: str,
    db: AsyncSession = Depends(get_db)
) -> List[MessageOut]:
    """Get all messages for a specific conversation"""
    logger.info(f"📨 Fetching messages for conversation {conversation_id}")
    
    try:
        conversation_id_uuid = UUID(conversation_id)
        user_id_uuid = UUID(user_id)
        
        # Verify conversation belongs to user
        conversation = await crud.get_conversation_by_id(
            db=db,
            conversation_id=conversation_id_uuid,
            user_id=user_id_uuid,
        )
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Get messages
        messages = await crud.get_conversation_history(
            db=db,
            user_id=user_id_uuid,
            conversation_id=conversation_id_uuid,
        )
        
        logger.info(f"✅ Found {len(messages)} messages")
        return messages
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid UUID format")
    except Exception as e:
        logger.error(f"❌ Error fetching messages: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class SystemStateResponse(BaseModel):
    last_inference: Optional[str] = None
    memory_count: int
    confidence: float
    learning_active: bool
    cycle_days: int = 7


@router.get("/system-state", response_model=SystemStateResponse)
async def get_system_state(
    user_id: str,
    db: AsyncSession = Depends(get_db)
) -> SystemStateResponse:
    """Get system state metrics for a user"""
    logger.info(f"📊 Fetching system state for user {user_id}")
    
    try:
        user_id_uuid = UUID(user_id)
        
        # 1. memory_count: Count total messages from messages table
        memory_count_result = await db.execute(
            select(func.count(Message.id)).where(Message.user_id == user_id_uuid)
        )
        memory_count = memory_count_result.scalar() or 0
        
        # 2. last_inference: Get latest assistant message timestamp
        last_inference_result = await db.execute(
            select(func.max(Message.created_at))
            .where(Message.user_id == user_id_uuid)
            .where(Message.role == "assistant")
        )
        last_inference_datetime = last_inference_result.scalar()
        last_inference = last_inference_datetime.isoformat() if last_inference_datetime else None
        
        # 3. confidence: Average behavioral_insights.confidence for user
        confidence_result = await db.execute(
            select(func.avg(BehavioralInsight.confidence))
            .where(BehavioralInsight.user_id == user_id_uuid)
            .where(BehavioralInsight.confidence.isnot(None))
        )
        avg_confidence = confidence_result.scalar()
        confidence = float(avg_confidence * 100) if avg_confidence is not None else 0.0
        
        # 4. learning_active: True if latest behavioral_insights.created_at is within last 7 days
        learning_active = False
        latest_insight_result = await db.execute(
            select(func.max(BehavioralInsight.created_at))
            .where(BehavioralInsight.user_id == user_id_uuid)
        )
        latest_insight_datetime = latest_insight_result.scalar()
        if latest_insight_datetime:
            seven_days_ago = datetime.now() - timedelta(days=7)
            learning_active = latest_insight_datetime >= seven_days_ago
        
        logger.info(f"✅ System state fetched: memory_count={memory_count}, confidence={confidence:.1f}%, learning_active={learning_active}")
        
        return SystemStateResponse(
            last_inference=last_inference,
            memory_count=memory_count,
            confidence=confidence,
            learning_active=learning_active,
            cycle_days=7
        )
    
    except ValueError as e:
        logger.error(f"❌ Invalid UUID format for user_id '{user_id}': {e}")
        raise HTTPException(status_code=400, detail=f"Invalid user_id format: {str(e)}")
    except Exception as e:
        logger.error(f"❌ Error fetching system state: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
