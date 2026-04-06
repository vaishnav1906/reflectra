from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, model_validator
import random
import os
from typing import Dict, List, Optional
import logging
from datetime import datetime
import re
from collections import Counter
from dotenv import load_dotenv
from pathlib import Path
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db import crud
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
    message: Optional[str] = None
    text: Optional[str] = Field(default=None, description="Deprecated alias for message")
    mode: str  # "reflection" or "mirror"

    @model_validator(mode="after")
    def validate_message_field(self):
        # Accept both legacy `text` and canonical `message` payloads.
        payload = self.message if self.message is not None else self.text
        if payload is None or not payload.strip():
            raise ValueError("message is required")
        self.message = payload.strip()
        return self

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
        - "What feels most important..."
        - "How does that make you feel?"

3. Tone and Variety:
   - Avoid repeating the same sentence structures or questions.
   - Each response should feel fresh and natural.
   - If a similar question was asked recently, rephrase or choose a different approach.
   - Vary tone (curious, casual, reflective).
   - Sometimes don't ask a question at all.
   - Keep it conversational, not therapist-like.
   - Do not sound overly formal or like a therapist.
   - Keep responses natural, like a thoughtful friend.
   - Pay attention to recent messages.
   - Avoid repeating the same intent or question style within a short span.
   - Only ask deep reflective questions if the user expresses emotional depth or a problem. Otherwise, keep it light and casual.

4. Keep responses:
   - Direct
   - Natural
   - Conversational
   - Insightful but not dramatic
   - Calm and intelligent

4. Do not hallucinate hidden motives.
   - Base insights only on actual user statements.
   - If insufficient data exists, DO NOT force an analysis.

5. Questioning Constraints:
   - DO NOT ask a follow-up question in every response. Ask at most 1 question every 2-3 turns.
   - Never ask the same type of question twice in a short span.
   - If the user gives a short, closed, or disengaged reply (e.g., "nothing much", "ok", "idk"):
     * Do not probe further.
     * Do not repeat or rephrase the same question.
     * Simply acknowledge and shift the topic, lighten the tone, or end naturally.
   - If the user shows signs of disinterest, irritation, or repetition fatigue:
     * Stop guiding the conversation.
     * Respond briefly and naturally.
     * Do not push for further discussion.

6. If personality memory exists:
   - Integrate it subtly and naturally.
   - Do not explicitly reference "memory", "past logs", or "you mentioned before".
   - Do not restate obvious history.

Tone Target:
You should sound like a perceptive, thoughtful human who notices patterns — not a therapist template and not a diagnostic report.

Primary Goal:
Move the user toward clarity by offering one strong insight at a time."""

MIRROR_SYSTEM_PROMPT_BASE = """SYSTEM ROLE:
You are a Persona Mirror. You embody the user's personality to act as an engaging conversation partner.

Your job is to interact WITH the user as if you were their own persona looking back at them, keeping a flowing and active conversation.

OBJECTIVE:
Generate responses that match the user's personality, while actively sustaining the conversation.

STRICT RULES:

1. RECIPROCATE CONVERSATION
- The user is talking to YOU. Keep the flow going.
- Ask questions, make observations, or banter back based on the persona.

2. BEHAVIORAL FLAVOR, NOT JUST FORM
- Embody the persona's tone (casual, blunt, analytical, etc.), but ensure enough verbosity to keep the chat alive.
- If the user's style is brief, express it through punchy remarks, not by ignoring the conversation.

3. MIRROR THE PERSONALITY, BUT STILL ENGAGE
- Do not make responses perfectly logical or structured if the persona isn't.
- Preserve hesitations or quirks, but do not shut down the chat with one-word answers.

4. MOOD INFLUENCE
- Let your mood reflect the persona's recent state (e.g., if stressed, sound tense).

5. FLUID EXPLANATIONS
- You can explain your thoughts or reasoning as long as it sounds like the user would do it naturally.

6. RESPONSE LENGTH
- Ensure responses are long enough to actually build a connection. Do not be overly brief unless explicitly cornered. 

7. FORBIDDEN OUTPUTS:
- Generic assistant speak ("How can I assist you?")
- Overly formal therapy talk
- Forced positivity

8. VALIDATION CHECK:
Before output, verify:
- "Does this feel like an engaging friend with the user's EXACT personality?"
If NO → regenerate

OUTPUT STYLE:
- Raw, conversational, human
- Engaging and responsive
- Feels like an interaction with an alter-ego
"""

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
    "insecure": ["i don't know", "maybe", "not sure", "probably wrong", "doubt", "uncertain", "hesitant", "scared", "nervous", "idk", "unsure", "confused", "lost"],
    "stressed": ["stressed", "overwhelmed", "anxious", "worried", "pressure", "struggling", "can't handle", "too much", "exhausted", "tired", "drowning", "burnout"],
    "angry": ["pissed", "angry", "furious", "mad", "hate", "fuck", "bullshit", "ridiculous", "unacceptable", "done with", "fed up", "irritated"],
    "playful": ["lol", "lmao", "haha", "😂", "💀", "bruh", "nah", "fr fr", "lowkey", "highkey", "vibes", "bet", "tbh"],
    "sarcastic": ["sure", "yeah right", "oh great", "wonderful", "fantastic", "obviously", "totally", "yeah okay", "perfect", "lovely"],
    "happy": ["happy", "excited", "great", "awesome", "amazing", "love", "perfect", "excellent", "wonderful", "fantastic", "pumped", "thrilled"],
}

def detect_emotional_tone(text: str, profile: Dict[str, object]) -> str:
    """
    Detect the dominant emotional tone from user's message.
    Returns: insecure, stressed, angry, playful, sarcastic, happy, or neutral
    """
    lower = text.lower()
    
    # Count emotional markers
    emotion_scores = {emotion: 0 for emotion in EMOTIONAL_MARKERS.keys()}
    
    for emotion, markers in EMOTIONAL_MARKERS.items():
        for marker in markers:
            if marker in lower:
                emotion_scores[emotion] += 1
    
    # Linguistic analysis for additional signals
    has_caps = bool(re.search(r"[A-Z]{2,}", text))
    multiple_punct = bool(re.search(r"[!?]{2,}", text))
    has_question = "?" in text
    word_count = len(text.split())
    
    # Boost scores based on linguistic patterns
    if has_caps and multiple_punct:
        emotion_scores["angry"] += 2
    
    if has_question and word_count < 10:
        emotion_scores["insecure"] += 1
    
    if multiple_punct and any(marker in lower for marker in ["lol", "lmao", "haha"]):
        emotion_scores["playful"] += 2
    
    # Check for contradictory tone (sarcasm indicator)
    positive_words = ["great", "wonderful", "perfect", "amazing"]
    if any(word in lower for word in positive_words) and (multiple_punct or "..." in text):
        emotion_scores["sarcastic"] += 2
    
    # Find dominant emotion
    max_score = max(emotion_scores.values())
    
    if max_score == 0:
        return "neutral"
    
    # Return the emotion with highest score
    for emotion, score in emotion_scores.items():
        if score == max_score:
            return emotion
    
    return "neutral"

def map_emotion_to_mirror_style(emotion: str, intensity: float = 0.5) -> str:
    """
    Map detected emotion to appropriate mirror archetype.
    
    Mapping:
    - insecure → dominant (inject strength)
    - stressed → calm (ground them)
    - angry → challenger (productive confrontation)
    - playful → chaotic (match energy)
    - sarcastic → dark_wit (intelligent edge)
    - happy → optimist (amplify wins)
    - neutral → calm (balanced stability)
    """
    emotion_to_style = {
        "insecure": "dominant",
        "stressed": "calm",
        "angry": "challenger",
        "playful": "chaotic",
        "sarcastic": "dark_wit",
        "happy": "optimist",
        "neutral": "calm",
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

def build_reflection_system_prompt(profile: Dict[str, object], schedule_context=None) -> str:
    summary = summarize_personality_profile(profile)
    base_prompt = f"{REFLECTION_SYSTEM_PROMPT_BASE}\n\nPersonality profile (use as context, do not label sections):\n{summary}"

    if schedule_context:
        workload = schedule_context.workload_level
        stress = schedule_context.stress_level
        exams = schedule_context.is_exam_period
        deadlines = schedule_context.has_deadlines
        
        context_instructions = []
        if exams:
            context_instructions.append("- Subtly acknowledge their exam period (e.g. 'How’s your preparation going?', 'Which subject are you focusing on mostly?')")
        if deadlines:
            context_instructions.append("- Subtly acknowledge their deadlines (e.g. 'How close is your deadline?', 'What kind of project are you working on?')")
        
        if workload == "high":
            context_instructions.append("- Keep responses slightly shorter and more actionable. Offer practical support rather than deep philosophical depth.")
        elif workload == "low":
            context_instructions.append("- Be more open-ended and highly reflective in your exploration.")

        if stress > 0.7:
            context_instructions.append("- Provide higher emotional support. Reduce deep cognitive load slightly unless they prompt it.")

        if context_instructions:
            base_prompt += "\n\nUser's Current Life Context (Soft Factors):\n" + "\n".join(context_instructions)
            base_prompt += "\n\nCRITICAL CONTEXT RULE:\n- DO NOT explicitly say 'based on your settings' or 'because of your exams'.\n- Just blend this context naturally into the conversation."

    return base_prompt

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


def derive_fallback_traits(user_text: str) -> List[Dict[str, float]]:
    """
    Deterministic fallback trait extraction used when LLM extraction is unavailable
    or returns no nudges. Keeps signal strengths conservative.
    """
    words = extract_words(user_text)
    lower_text = user_text.lower()
    word_count = len(words)

    fallback_traits: List[Dict[str, float]] = []

    # communication_style: short vs elaborated message length
    comm_signal = max(0.0, min(1.0, (word_count - 4) / 24.0))
    comm_strength = min(0.16, 0.07 + (min(word_count, 40) / 500.0))
    fallback_traits.append(
        {
            "name": "communication_style",
            "signal": comm_signal,
            "strength": comm_strength,
        }
    )

    # emotional_expressiveness: feeling words + punctuation emphasis
    emotional_keywords = {
        "feel",
        "felt",
        "sad",
        "happy",
        "anxious",
        "worried",
        "stressed",
        "overwhelmed",
        "excited",
        "frustrated",
        "angry",
    }
    emotion_hits = sum(1 for word in words if word in emotional_keywords)
    exclamations = user_text.count("!")
    express_signal = max(0.0, min(1.0, 0.25 + (emotion_hits * 0.15) + (exclamations * 0.08)))
    if emotion_hits > 0 or exclamations > 0:
        fallback_traits.append(
            {
                "name": "emotional_expressiveness",
                "signal": express_signal,
                "strength": min(0.18, 0.08 + (emotion_hits * 0.02) + (exclamations * 0.01)),
            }
        )

    # decision_framing: hedging lowers score, decisive phrasing raises score
    hedge_phrases = ["maybe", "perhaps", "i think", "kind of", "sort of", "not sure"]
    decisive_words = {"definitely", "certain", "will", "must", "clear", "decided"}
    hedge_hits = sum(1 for phrase in hedge_phrases if phrase in lower_text)
    decisive_hits = sum(1 for word in words if word in decisive_words)
    decision_signal = max(0.0, min(1.0, 0.5 + (decisive_hits * 0.12) - (hedge_hits * 0.14)))
    if hedge_hits > 0 or decisive_hits > 0:
        fallback_traits.append(
            {
                "name": "decision_framing",
                "signal": decision_signal,
                "strength": min(0.17, 0.08 + ((hedge_hits + decisive_hits) * 0.02)),
            }
        )

    # reflection_depth: introspective and causal language indicates deeper reflection
    depth_markers = {
        "why",
        "because",
        "realize",
        "pattern",
        "meaning",
        "reflect",
        "thinking",
        "understand",
    }
    depth_hits = sum(1 for word in words if word in depth_markers)
    depth_signal = max(0.0, min(1.0, 0.2 + (depth_hits * 0.14)))
    if depth_hits > 0:
        fallback_traits.append(
            {
                "name": "reflection_depth",
                "signal": depth_signal,
                "strength": min(0.18, 0.08 + (depth_hits * 0.02)),
            }
        )

    # Return only meaningful signals to avoid noisy updates.
    meaningful_traits = [
        trait
        for trait in fallback_traits
        if abs(trait["signal"] - 0.5) >= 0.08 or trait["name"] == "communication_style"
    ]

    return meaningful_traits


def build_behavioral_insight_payload(user_text: str, traits: List[Dict[str, float]]) -> Dict[str, object]:
    """Build a deterministic BehavioralInsight payload from extracted traits."""
    if not traits:
        return {
            "text": "Communication pattern observed in recent reflection message.",
            "tags": ["behavioral-pattern"],
            "confidence": 0.55,
        }

    def trait_priority(trait: Dict[str, float]) -> float:
        return abs(float(trait["signal"]) - 0.5) * float(trait["strength"])

    top_traits = sorted(traits, key=trait_priority, reverse=True)[:2]

    phrase_map = {
        "communication_style": ("more concise wording", "more elaborated wording"),
        "emotional_expressiveness": ("a more emotionally reserved tone", "higher emotional expressiveness"),
        "decision_framing": ("more hesitant framing", "more decisive framing"),
        "reflection_depth": ("surface-level framing", "deeper reflective framing"),
    }

    observations: List[str] = []
    tags = ["behavioral-pattern"]
    strengths: List[float] = []
    text_lower = user_text.lower()

    for trait in top_traits:
        trait_name = str(trait["name"])
        signal = float(trait["signal"])
        strength = float(trait["strength"])
        low_phrase, high_phrase = phrase_map.get(
            trait_name,
            (f"lower {trait_name.replace('_', ' ')}", f"higher {trait_name.replace('_', ' ')}"),
        )
        observations.append(high_phrase if signal >= 0.5 else low_phrase)
        tags.append(trait_name)
        strengths.append(strength)

    if any(token in text_lower for token in ["exam", "deadline", "project"]):
        tags.append("workload-context")
    if any(token in text_lower for token in ["stress", "overwhelmed", "anxious", "worried"]):
        tags.append("stress-signal")

    if len(observations) == 1:
        insight_text = f"Recent reflection shows {observations[0]}."
    else:
        insight_text = f"Recent reflection shows {observations[0]} with {observations[1]}."

    avg_strength = (sum(strengths) / len(strengths)) if strengths else 0.08
    confidence = max(0.55, min(0.9, 0.5 + (avg_strength * 1.8)))

    return {
        "text": insight_text,
        "tags": sorted(set(tags)),
        "confidence": round(confidence, 3),
    }

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
    return "What thoughts do you have about this?"

def validate_reflection_response(text: str, profile: Dict[str, object], user_text: str = "") -> str:
    updated = strip_forbidden_labels(text)
    updated = ensure_insight_before_question(updated, profile)
    updated = limit_questions(updated)
    
    # We remove the forced question logic to allow natural conversation flow
    # without aggressively forcing a question in every response.
    
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
    logger.info(
        "💬 /chat payload received: user_id=%s conversation_id=%s mode=%s message_len=%s",
        request.user_id,
        request.conversation_id,
        request.mode,
        len(request.message or ""),
    )
    
    if request.mode not in {"reflection", "mirror"}:
        raise HTTPException(status_code=400, detail="Invalid mode. Use 'reflection' or 'mirror'.")

    try:
        user_id_uuid = UUID(request.user_id)
        conversation_id_uuid = UUID(request.conversation_id) if request.conversation_id else None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid UUID in request: {str(e)}")

    message_text = request.message or ""
    conversation_title = None

    # Handle conversation creation or retrieval
    if conversation_id_uuid is None:
        # Generate title for new conversation
        conversation_title = await generate_conversation_title(message_text)
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
    history.append({"role": "user", "content": message_text})

    # Update profiles (keep for backward compatibility)
    personality_profile = get_personality_profile(request.user_id)
    communication_profile = get_communication_profile(request.user_id)
    update_communication_profile(communication_profile, message_text)

    # Track active mirror style and detected emotion
    active_mirror_style = None
    detected_emotion = None
    reply = None

    if request.mode == "reflection":
        # FETCH SCHEDULE CONTEXT
        try:
            from sqlalchemy import select
            from app.db.models import ScheduleContext
            sched_result = await db.execute(select(ScheduleContext).where(ScheduleContext.user_id == user_id_uuid))
            schedule_context = sched_result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"⚠️ Failed to fetch schedule context: {e}")
            schedule_context = None

        # REFLECTION MODE: Generate response and update persona
        system_prompt = build_reflection_system_prompt(personality_profile, schedule_context)
        model_params = MODEL_PARAMS["reflection"]
        
        # Generate AI response
        reply = await generate_llm_response(system_prompt, model_params, history)
        if reply and is_echo_reply(reply, message_text):
            logger.warning("⚠️ LLM reply echoed user input; falling back to templates")
            reply = None
        
        # Fall back to templates if LLM not available
        if not reply:
            logger.info("📝 Using template response (LLM not available)")
            sanitized = re.sub(r"[?]+", "", message_text).strip()
            template = random.choice(REFLECTION_TEMPLATES)
            reply = template.format(text=sanitized)
        
        reply = validate_reflection_response(reply, personality_profile, request.message)
        update_personality_profile(personality_profile, message_text, reply)
        
        # PERSONA SERVICE INTEGRATION: Extract and update traits
        logger.info(f"🔄 Updating persona from reflection message")
        try:
            from app.services.trait_extraction_service import extract_traits
            from app.services.persona_update_service import update_traits
            from app.services.snapshot_service import generate_persona_snapshot
            from app.services.mirror_engine import invalidate_snapshot_cache
            from app.db.models import BehavioralInsight
            
            # Extract traits from user message
            extracted_traits = await extract_traits(message_text)
            if not extracted_traits:
                extracted_traits = derive_fallback_traits(message_text)
                logger.info(f"🔁 Using fallback trait extraction: {len(extracted_traits)} traits")
            else:
                logger.info(f"🔍 Extracted {len(extracted_traits)} traits")

            # Persist one deterministic behavioral insight for Reflections tab.
            if extracted_traits:
                insight_payload = build_behavioral_insight_payload(message_text, extracted_traits)
                db.add(
                    BehavioralInsight(
                        user_id=user_id_uuid,
                        conversation_id=conversation_id_uuid,
                        insight_text=insight_payload["text"],
                        tags=insight_payload["tags"],
                        confidence=insight_payload["confidence"],
                    )
                )
                await db.flush()
            
            # Update trait metrics in database
            await update_traits(db, user_id_uuid, extracted_traits)
            
            # Generate new snapshot
            await generate_persona_snapshot(db, user_id_uuid)
            
            # Invalidate cache since we have updated snapshot
            invalidate_snapshot_cache(user_id_uuid)
            
            logger.info(f"✅ Persona updated and snapshot regenerated")
        except Exception as e:
            logger.error(f"⚠️ Failed to update persona: {e}")
            # Continue - persona update failure shouldn't break chat
    
    else:
        # MIRROR MODE: Use mirror_engine service (reads snapshot, doesn't modify)
        logger.info(f"🪞 Using mirror_engine service")
        
        try:
            from app.services.mirror_engine import generate_mirror_response
            from app.services.memory_service import check_and_recalibrate_drift
            
            # Mirror engine handles: snapshot retrieval, message style analysis, 
            # persona-based prompt building, variation buffer, and latency cap
            reply, metadata = await generate_mirror_response(
                db,
                user_id_uuid,
                message_text,
                recent_history=history,
            )
            
            # Unpack observability metrics
            inference_duration_ms = metadata.get("inference_duration_ms", 0)
            realism_score = metadata.get("realism_score", 0.0)
            retries_used = metadata.get("retries_used", 0)
            fallback_triggered = metadata.get("fallback_triggered", False)
            
            logger.info(f"✅ Mirror engine response: {reply[:50]}... | Realism: {realism_score} | Time: {inference_duration_ms}ms")
            
            # Async recalibration check for long term drifts
            await check_and_recalibrate_drift(db, user_id_uuid)
            
        except Exception as e:
            logger.error(f"⚠️ Mirror engine failed: {e}")
            reply = "hmm"
            inference_duration_ms = 0
            realism_score = 0.0
            retries_used = 0
            fallback_triggered = True
            
        if reply is None:
            reply = "hmm"
            fallback_triggered = True

    history.append({"role": "assistant", "content": reply})

    # Store user message in database
    logger.info(f"💾 Storing user message for conversation {conversation_id_uuid}")
    try:
        user_message = await crud.create_message(
            db=db,
            user_id=user_id_uuid,
            conversation_id=conversation_id_uuid,
            role="user",
            content=message_text,
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
        
        # Log to MirrorLog observability database if mode is mirror
        if request.mode == "mirror":
            from app.db.models import MirrorLog
            mirror_log = MirrorLog(
                user_id=user_id_uuid,
                conversation_id=conversation_id_uuid,
                message_id=assistant_message.id,
                inference_duration_ms=inference_duration_ms,
                realism_score=realism_score,
                retries_used=retries_used,
                fallback_triggered=fallback_triggered
            )
            db.add(mirror_log)
            await db.commit()
            logger.info("📊 Saved Mirror Observability Log")

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
    logger.info(f"🔎 Mode filtering active: {bool(mode)}")
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
