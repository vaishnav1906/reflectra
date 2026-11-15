from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, model_validator
import asyncio
import random
from typing import Any, Dict, List, Optional
import logging
from datetime import datetime, timezone
import re
from collections import Counter
from dotenv import load_dotenv
from pathlib import Path
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, ensure_self
from app.db.database import get_db
from app.db import crud
from app.db.models import Message, PersonalityProfile, ReflectionLog, UserSettings
from app.schemas.db import ConversationListItem, ConversationListOut, MessageOut
from app.services.llm import chat_complete, llm_available
from app.services.message_signals import (
    compute_message_metrics,
    derive_fallback_traits,
    simple_sentiment,
)
from app.services.twin_assistant_service import (
    build_assistant_fallback_reply,
    classify_assistant_task,
)
from app.services.twin_policy import resolve_twin_settings

# Load environment variables
load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

class ChatRequest(BaseModel):
    user_id: Optional[str] = None  # ignored: identity comes from the access token
    conversation_id: Optional[str] = None
    message: Optional[str] = None
    text: Optional[str] = Field(default=None, description="Deprecated alias for message")
    mode: str  # "reflection" or "mirror" ("assistant" accepted as deprecated alias)
    external_input_text: Optional[str] = None
    external_input_source: Optional[str] = "pasted_prompt"
    # Incognito: nothing is stored server-side. The client keeps the transcript
    # and sends recent turns as `history` so replies keep their context.
    is_incognito: bool = False
    incognito_session_id: Optional[str] = None
    history: Optional[List["HistoryTurn"]] = Field(default=None, max_length=40)

    @model_validator(mode="after")
    def validate_message_field(self):
        # Accept both legacy `text` and canonical `message` payloads.
        payload = self.message if self.message is not None else self.text
        if payload is None or not payload.strip():
            raise ValueError("message is required")
        self.message = payload.strip()
        return self


class HistoryTurn(BaseModel):
    role: str
    content: str = Field(max_length=8000)


ChatRequest.model_rebuild()

class ChatResponse(BaseModel):
    conversation_id: str
    title: Optional[str] = None
    reply: str
    mirror_active: bool
    confidence_level: str
    mode: str
    assistant_task_type: Optional[str] = None
    active_mirror_style: Optional[str] = None  # Currently active mirror style
    detected_emotion: Optional[str] = None  # Detected emotional tone
    twin_policy: Optional[Dict[str, Any]] = None
    confidence_interval: Optional[Dict[str, float]] = None
    style_strength: Optional[float] = None
    reaction_source: Optional[str] = None


# ============================================================================
# PERSISTENT CONVERSATION CONTEXT
# ============================================================================
# History, the keyword personality profile and recent insight notes all come
# from the database, scoped to the conversation/user, so context never leaks
# between conversations and survives restarts or multiple server instances.

HISTORY_MESSAGE_LIMIT = 16
PROFILE_COUNTER_FIELDS = ("themes", "traits", "values", "stressors")


async def load_conversation_history(
    db: AsyncSession,
    conversation_id: UUID,
    user_id: UUID,
    limit: int = HISTORY_MESSAGE_LIMIT,
) -> List[Dict[str, str]]:
    """Return the last `limit` messages of a conversation, oldest first."""
    stmt = (
        select(Message.role, Message.content)
        .where(Message.conversation_id == conversation_id, Message.user_id == user_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    return [
        {"role": role, "content": content}
        for role, content in reversed(rows)
        if role in {"user", "assistant"} and content
    ]


def _counter_from_json(value: Any) -> Counter:
    counter: Counter = Counter()
    if isinstance(value, dict):
        for key, count in value.items():
            if isinstance(count, (int, float)):
                counter[str(key)] += int(count)
    return counter


async def load_personality_profile(db: AsyncSession, user_id: UUID) -> Dict[str, object]:
    """Load the keyword personality profile plus the latest reflection insight notes."""
    record = (
        await db.execute(select(PersonalityProfile).where(PersonalityProfile.user_id == user_id))
    ).scalar_one_or_none()

    profile: Dict[str, object] = {
        field: _counter_from_json(getattr(record, field, None) if record else None)
        for field in PROFILE_COUNTER_FIELDS
    }

    recent_responses = (
        await db.execute(
            select(ReflectionLog.response)
            .where(ReflectionLog.user_id == user_id)
            .order_by(ReflectionLog.created_at.desc())
            .limit(6)
        )
    ).scalars().all()
    notes = [extract_insight_sentence(text) for text in reversed(recent_responses) if text]
    profile["insight_notes"] = [note for note in notes if note]
    profile["updated_at"] = None
    return profile


async def save_personality_profile(db: AsyncSession, user_id: UUID, profile: Dict[str, object]) -> None:
    """Persist the keyword counters to personality_profile (flushed, not committed)."""
    record = (
        await db.execute(select(PersonalityProfile).where(PersonalityProfile.user_id == user_id))
    ).scalar_one_or_none()
    if record is None:
        record = PersonalityProfile(user_id=user_id)
        db.add(record)
    for field in PROFILE_COUNTER_FIELDS:
        # Assign a fresh dict so SQLAlchemy detects the JSONB change.
        setattr(record, field, dict(profile[field]))
    record.updated_at = datetime.now(timezone.utc)
    await db.flush()


# Reflection mode responses - adaptive pattern recognition
REFLECTION_TEMPLATES = [
    "You keep circling back to {text}. That usually means there's something unresolved underneath. What's the real question here?",
    "There's a thread here: you frame {text} in a way that puts you outside the system. What changes if you see yourself as part of it?",
    "The pattern with {text} seems to be about control—or the lack of it. Where does that tension come from?",
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


MODEL_PARAMS = {
    "reflection": {"temperature": 0.6, "max_tokens": 280},  # Increased for structured pattern synthesis
    "mirror": {"temperature": 0.85, "max_tokens": 150},  # Higher temp for unhinged chaos
}

EXPLICIT_TASK_COMMAND_PATTERNS = [
    r"^(can you|could you|please|help me|i need you to|i want you to)\b",
    r"^(draft|write|compose|rewrite|rephrase|edit|summarize|summarise|brainstorm|plan|outline|create|generate)\b",
    r"\b(draft|rewrite|rephrase|summarize|summarise|brainstorm|plan|outline|compose)\b.*\b(this|that|for me|for us)\b",
]

MIRROR_FALLBACK_REPLY = "Got it. Give me a little more context and I will respond in your tone."
TASK_FOLLOWUP_MARKERS = [
    "help me write",
    "write in my tone",
    "in my tone",
    "make it sound",
    "make this better",
    "polish this",
    "tighten this",
    "continue this",
    "finish this",
    "make it shorter",
    "make it longer",
    "version 2",
    "another option",
    "try again",
    "redo this",
]
CONTEXTUAL_TASK_TYPES = {
    "email_draft",
    "message_draft",
    "rewrite",
    "summarize",
    "brainstorm",
    "planning",
}




def split_sentences(text: str) -> List[str]:
    raw = re.split(r"[.!?]+", text)
    return [segment.strip() for segment in raw if segment.strip()]

def extract_words(text: str) -> List[str]:
    return re.findall(r"\b\w+\b", text.lower())


def normalize_interaction_mode(mode: Optional[str]) -> Optional[str]:
    """Normalize deprecated aliases so runtime only uses reflection/mirror modes."""
    if mode is None:
        return None

    cleaned = mode.strip().lower()
    if cleaned == "assistant":
        return "mirror"
    return cleaned


def detect_explicit_task_command(message: str) -> Optional[str]:
    """Return task type only when user gives an explicit task command."""
    text = (message or "").strip().lower()
    if not text:
        return None

    if not any(re.search(pattern, text) for pattern in EXPLICIT_TASK_COMMAND_PATTERNS):
        return None

    task_type = classify_assistant_task(text)
    # Keep mirror conversational by default; do not route generic/QA into task mode.
    if task_type in {"qa", "generic"}:
        return None

    return task_type


def resolve_mirror_task_type(message: str, history: Optional[List[Dict[str, str]]] = None) -> Optional[str]:
    """Resolve mirror task type using explicit commands first, then contextual follow-up cues."""
    text = (message or "").strip()
    if not text:
        return None

    text_lower = text.lower()
    explicit_task = detect_explicit_task_command(text_lower)
    followup_hint = any(marker in text_lower for marker in TASK_FOLLOWUP_MARKERS)
    imperative_hint = bool(
        re.search(
            r"^(help me|can you|could you|please|write|draft|compose|rewrite|rephrase|summarize|summarise|plan|outline|brainstorm|polish|tighten|continue|finish|redo|try again)\b",
            text_lower,
        )
    )
    style_hint = any(token in text_lower for token in ["in my tone", "my tone", "my voice", "sound like me", "write like me"])
    should_probe_history = followup_hint or imperative_hint or style_hint

    if explicit_task and not (followup_hint or style_hint):
        return explicit_task

    if history and should_probe_history:
        user_turns = [
            (turn.get("content") or "").strip()
            for turn in history
            if turn.get("role") == "user" and (turn.get("content") or "").strip()
        ]
        if user_turns and user_turns[-1].lower() == text_lower:
            user_turns = user_turns[:-1]

        for prior_text in reversed(user_turns[-10:]):
            prior_explicit = detect_explicit_task_command(prior_text)
            if prior_explicit in CONTEXTUAL_TASK_TYPES:
                return prior_explicit

            prior_inferred = classify_assistant_task(prior_text.lower())
            if prior_inferred in CONTEXTUAL_TASK_TYPES:
                return prior_inferred

    if explicit_task in CONTEXTUAL_TASK_TYPES:
        return explicit_task

    inferred_task = classify_assistant_task(text_lower)
    if inferred_task in CONTEXTUAL_TASK_TYPES and should_probe_history:
        return inferred_task

    return None

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

def get_adaptive_mirror_style(
    user_text: str,
    profile: Dict[str, object],
    prior_user_messages: Optional[List[str]] = None,
) -> tuple[str, str]:
    """
    Determine mirror archetype adaptively based on emotional detection.
    Returns: (selected_style, detected_emotion)

    Consistency rule: if the two previous user messages in this conversation
    showed the same emotion and the current message differs, keep that
    established archetype for one more turn instead of flipping immediately.
    The emotion history is derived from the conversation itself, so it is
    scoped per conversation and survives restarts.
    """
    detected_emotion = detect_emotional_tone(user_text, profile)
    suggested_style = map_emotion_to_mirror_style(detected_emotion)

    recent = [detect_emotional_tone(text, profile) for text in (prior_user_messages or [])[-2:]]
    if len(recent) == 2 and recent[0] == recent[1] and detected_emotion != recent[-1]:
        suggested_style = map_emotion_to_mirror_style(recent[-1])

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



def is_echo_reply(reply: str, user_text: str) -> bool:
    def normalize(value: str) -> str:
        return re.sub(r"\s+", " ", value.strip().lower())

    return normalize(reply) == normalize(user_text)


async def generate_llm_response(system_prompt: str, model_params: Dict[str, object], history: List[Dict[str, str]]) -> Optional[str]:
    """Generate response using Mistral AI. Returns None when unavailable or on error."""
    if not llm_available():
        return None

    try:
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        reply = await chat_complete(
            messages,
            max_tokens=model_params["max_tokens"],
            temperature=model_params["temperature"],
        )
        if reply:
            logger.info(f"✅ Mistral response received: {reply[:50]}...")
        return reply
    except Exception as e:
        logger.error(f"❌ Mistral error: {type(e).__name__}: {e}")
        return None


def _fallback_title(user_message: str) -> str:
    return user_message[:40] + ("..." if len(user_message) > 40 else "")


async def generate_conversation_title(user_message: str) -> str:
    """Generate a 3-5 word summary title for a conversation"""
    if llm_available():
        try:
            system_prompt = "You are a helpful assistant that creates very short conversation titles. Generate a 3-5 word title that summarizes the topic. Return ONLY the title, nothing else."
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Create a 3-5 word title for this message: {user_message}"}
            ]
            title = await chat_complete(messages, max_tokens=20, temperature=0.7)
            if title:
                return title.strip('"\'')
        except Exception as e:
            logger.error(f"❌ Title generation error: {e}")

    return _fallback_title(user_message)


INCOGNITO_HISTORY_LIMIT = 16


def _sanitize_client_history(turns: Optional[List["HistoryTurn"]]) -> List[Dict[str, str]]:
    cleaned = [
        {"role": turn.role, "content": turn.content.strip()}
        for turn in (turns or [])
        if turn.role in {"user", "assistant"} and turn.content and turn.content.strip()
    ]
    return cleaned[-INCOGNITO_HISTORY_LIMIT:]


async def _incognito_chat(
    request: ChatRequest,
    effective_mode: str,
    user_id: UUID,
    db: AsyncSession,
) -> ChatResponse:
    """Answer without writing anything: no conversation, messages, traits, insights,
    logs, fingerprint or telemetry. The persona is read (so replies stay personal)
    but never updated from incognito messages."""
    message_text = request.message or ""
    prior_history = _sanitize_client_history(request.history)
    history = prior_history + [{"role": "user", "content": message_text}]
    personality_profile = await load_personality_profile(db, user_id)
    session_id = request.incognito_session_id or "incognito"

    if effective_mode == "reflection":
        from app.db.models import ScheduleContext

        schedule_context = (
            await db.execute(select(ScheduleContext).where(ScheduleContext.user_id == user_id))
        ).scalar_one_or_none()
        reply = await generate_llm_response(
            build_reflection_system_prompt(personality_profile, schedule_context),
            MODEL_PARAMS["reflection"],
            history,
        )
        if not reply or is_echo_reply(reply, message_text):
            sanitized = re.sub(r"[?]+", "", message_text).strip()
            reply = random.choice(REFLECTION_TEMPLATES).format(text=sanitized)
        reply = validate_reflection_response(reply, personality_profile, message_text)
        await db.rollback()  # nothing should be pending, but never commit in incognito
        return ChatResponse(
            conversation_id=session_id,
            reply=reply,
            mirror_active=False,
            confidence_level="medium",
            mode=effective_mode,
        )

    from app.services.mirror_engine import generate_mirror_response

    assistant_task_type = resolve_mirror_task_type(message_text, history) or classify_assistant_task(message_text.lower())
    prior_user_messages = [turn["content"] for turn in prior_history if turn["role"] == "user"]
    active_mirror_style, detected_emotion = get_adaptive_mirror_style(
        message_text, personality_profile, prior_user_messages
    )
    settings_record = (
        await db.execute(select(UserSettings).where(UserSettings.user_id == user_id))
    ).scalar_one_or_none()
    twin_policy = resolve_twin_settings(settings_record)

    try:
        reply, metadata = await generate_mirror_response(
            db,
            user_id,
            message_text,
            recent_history=prior_history,
            twin_policy=twin_policy,
            task_type=assistant_task_type,
            detected_emotion=detected_emotion,
            active_mirror_style=active_mirror_style,
            persist=False,
        )
    except Exception:
        logger.exception("⚠️ Incognito mirror generation failed")
        reply, metadata = None, {}
    finally:
        await db.rollback()

    if not reply:
        reply = (
            build_assistant_fallback_reply(message_text, assistant_task_type)
            if assistant_task_type
            else MIRROR_FALLBACK_REPLY
        )

    return ChatResponse(
        conversation_id=session_id,
        reply=reply,
        mirror_active=bool(metadata) and not metadata.get("fallback_triggered", False),
        confidence_level=str(metadata.get("confidence_tier", "very_low")),
        mode=effective_mode,
        assistant_task_type=assistant_task_type,
        active_mirror_style=active_mirror_style,
        detected_emotion=detected_emotion,
        twin_policy=twin_policy,
        confidence_interval={
            "lower": float(metadata.get("confidence_lower", 0.0)),
            "upper": float(metadata.get("confidence_upper", 0.0)),
        },
        style_strength=float(metadata.get("style_enforcement_strength", 0.0)),
        reaction_source=str(metadata.get("stimulus_tag", "general")),
    )


@router.delete("/chat/incognito-history/{session_id}", status_code=204)
async def clear_incognito_history(session_id: str) -> None:
    """Incognito chats are never stored server-side, so there is nothing to delete.
    Kept so the frontend's cleanup call succeeds."""
    return None


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, current_user: CurrentUser, db: AsyncSession = Depends(get_db)) -> ChatResponse:
    """
    Process chat message and return AI response.
    Creates new conversation if conversation_id is None.
    Stores all messages in database.
    Falls back to templates if LLM is not available.

    Independent LLM calls (reply generation, trait extraction, title) run
    concurrently; conversation history and profile context come from the database.
    """
    effective_mode = normalize_interaction_mode(request.mode)
    logger.info(
        "💬 /chat payload received: user_id=%s conversation_id=%s requested_mode=%s effective_mode=%s message_len=%s",
        request.user_id,
        request.conversation_id,
        request.mode,
        effective_mode,
        len(request.message or ""),
    )

    if request.mode.strip().lower() == "assistant":
        logger.warning("⚠️ Deprecated mode alias 'assistant' received; routing as mirror mode")

    if effective_mode not in {"reflection", "mirror"}:
        raise HTTPException(status_code=400, detail="Invalid mode. Use 'reflection' or 'mirror'.")

    try:
        user_id_uuid = ensure_self(request.user_id, current_user)
        conversation_id_uuid = UUID(request.conversation_id) if request.conversation_id else None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid UUID in request: {str(e)}")

    if request.is_incognito:
        return await _incognito_chat(request, effective_mode, user_id_uuid, db)

    message_text = request.message or ""
    conversation_title = None
    title_task: Optional[asyncio.Task] = None
    prior_history: List[Dict[str, str]] = []

    # Handle conversation creation or retrieval
    if conversation_id_uuid is None:
        # Title generation runs in the background while the reply is generated.
        title_task = asyncio.create_task(generate_conversation_title(message_text))
        metadata_payload = {}
        if request.external_input_text:
            metadata_payload["external_input_source"] = request.external_input_source or "pasted_prompt"

        conversation = await crud.create_conversation(
            db=db,
            user_id=user_id_uuid,
            title=_fallback_title(message_text),
            mode=effective_mode,
            metadata=metadata_payload,
        )
        conversation_id_uuid = conversation.id
        logger.info(f"✅ Created conversation {conversation_id_uuid} with mode: {effective_mode}")
    else:
        conversation = await crud.get_conversation_by_id(
            db=db,
            conversation_id=conversation_id_uuid,
            user_id=user_id_uuid,
        )
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Validate that conversation mode matches request mode
        if conversation.mode == "assistant" and effective_mode == "mirror":
            logger.info("🔁 Upgrading existing assistant conversation to mirror mode")
            conversation.mode = "mirror"
            await db.flush()
        elif conversation.mode != effective_mode:
            raise HTTPException(
                status_code=400,
                detail=f"Conversation mode '{conversation.mode}' does not match request mode '{effective_mode}'"
            )

        conversation_title = conversation.title
        prior_history = await load_conversation_history(db, conversation_id_uuid, user_id_uuid)

    # LLM context: this conversation's recent turns plus the new message.
    history = prior_history + [{"role": "user", "content": message_text}]
    personality_profile = await load_personality_profile(db, user_id_uuid)

    # Track active mirror style and detected emotion
    active_mirror_style = None
    detected_emotion = None
    reply = None
    twin_policy = None
    assistant_task_type = None
    mirror_runtime_active = effective_mode == "mirror"
    confidence_interval = None
    style_strength = None
    reaction_source = None
    reaction_match_score = 0.0
    extracted_traits: List[Dict] = []

    from app.services.trait_extraction_service import extract_traits
    from app.services.persona_update_service import update_traits
    from app.services.snapshot_service import generate_persona_snapshot

    if effective_mode == "reflection":
        try:
            from app.db.models import ScheduleContext
            sched_result = await db.execute(select(ScheduleContext).where(ScheduleContext.user_id == user_id_uuid))
            schedule_context = sched_result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"⚠️ Failed to fetch schedule context: {e}")
            schedule_context = None

        system_prompt = build_reflection_system_prompt(personality_profile, schedule_context)
        model_params = MODEL_PARAMS["reflection"]

        # Reply and trait extraction are independent LLM calls: run them together.
        reply, extracted_traits = await asyncio.gather(
            generate_llm_response(system_prompt, model_params, history),
            extract_traits(message_text),
        )
        if reply and is_echo_reply(reply, message_text):
            logger.warning("⚠️ LLM reply echoed user input; falling back to templates")
            reply = None

        if not reply:
            logger.info("📝 Using template response (LLM not available)")
            sanitized = re.sub(r"[?]+", "", message_text).strip()
            reply = random.choice(REFLECTION_TEMPLATES).format(text=sanitized)

        reply = validate_reflection_response(reply, personality_profile, message_text)
        update_personality_profile(personality_profile, message_text, reply)

        try:
            await save_personality_profile(db, user_id_uuid, personality_profile)
            db.add(
                ReflectionLog(
                    user_id=user_id_uuid,
                    conversation_id=conversation_id_uuid,
                    prompt=message_text,
                    response=reply,
                    sentiment=simple_sentiment(message_text),
                )
            )
            await db.commit()
        except Exception as e:
            logger.warning(f"⚠️ Failed to persist reflection profile/log: {e}")
            await db.rollback()

        try:
            from app.db.models import BehavioralInsight

            if not extracted_traits:
                extracted_traits = derive_fallback_traits(message_text)
                logger.info(f"🔁 Using fallback trait extraction: {len(extracted_traits)} traits")

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

            await update_traits(db, user_id_uuid, extracted_traits)
            await generate_persona_snapshot(db, user_id_uuid)
            logger.info("✅ Persona updated from reflection message")
        except Exception as e:
            logger.error(f"⚠️ Failed to update persona: {e}")
            await db.rollback()

    else:
        # MIRROR MODE: Always keep full assistant capability while preserving mirror style.
        explicit_task_type = resolve_mirror_task_type(message_text, history)
        inferred_task_type = classify_assistant_task(message_text.lower())
        assistant_task_type = explicit_task_type or inferred_task_type

        prior_user_messages = [turn["content"] for turn in prior_history if turn["role"] == "user"]
        active_mirror_style, detected_emotion = get_adaptive_mirror_style(
            message_text,
            personality_profile,
            prior_user_messages,
        )

        logger.info(
            "🪞 Using mirror_engine service | task=%s | style=%s | emotion=%s",
            assistant_task_type or "none",
            active_mirror_style,
            detected_emotion,
        )

        from app.services.mirror_engine import generate_mirror_response
        from app.services.memory_service import check_and_recalibrate_drift

        settings_result = await db.execute(select(UserSettings).where(UserSettings.user_id == user_id_uuid))
        settings_record = settings_result.scalar_one_or_none()
        twin_policy = resolve_twin_settings(settings_record)

        # The mirror reply and trait extraction run concurrently. Trait extraction
        # does not touch the DB session, so sharing it with the mirror engine is safe.
        mirror_result, traits_result = await asyncio.gather(
            generate_mirror_response(
                db,
                user_id_uuid,
                message_text,
                recent_history=prior_history,
                twin_policy=twin_policy,
                task_type=assistant_task_type,
                detected_emotion=detected_emotion,
                active_mirror_style=active_mirror_style,
                conversation_id=conversation_id_uuid,
            ),
            extract_traits(message_text),
            return_exceptions=True,
        )
        extracted_traits = traits_result if isinstance(traits_result, list) else []

        if isinstance(mirror_result, BaseException):
            logger.error("⚠️ Mirror generation failed", exc_info=mirror_result)
            await db.rollback()
            if assistant_task_type:
                reply = build_assistant_fallback_reply(message_text, assistant_task_type)
            else:
                reply = MIRROR_FALLBACK_REPLY
            inference_duration_ms = 0
            realism_score = 0.0
            retries_used = 0
            fallback_triggered = True
            mirror_runtime_active = False
            confidence_lower = 0.0
            confidence_upper = 0.0
            confidence_tier = "very_low"
            style_strength = 0.0
            reaction_match_score = 0.0
            source_weights = {}
            reaction_source = "general"
            confidence_interval = {"lower": 0.0, "upper": 0.0}
        else:
            reply, metadata = mirror_result
            inference_duration_ms = metadata.get("inference_duration_ms", 0)
            realism_score = metadata.get("realism_score", 0.0)
            retries_used = metadata.get("retries_used", 0)
            fallback_triggered = metadata.get("fallback_triggered", False)
            confidence_lower = float(metadata.get("confidence_lower", 0.0))
            confidence_upper = float(metadata.get("confidence_upper", 0.0))
            confidence_tier = str(metadata.get("confidence_tier", "very_low"))
            style_strength = float(metadata.get("style_enforcement_strength", 0.0))
            reaction_match_score = float(metadata.get("reaction_match_score", 0.0))
            source_weights = metadata.get("source_weights", {})
            reaction_source = str(metadata.get("stimulus_tag", "general"))
            confidence_interval = {"lower": confidence_lower, "upper": confidence_upper}
            mirror_runtime_active = not bool(
                fallback_triggered and metadata.get("policy_mode") in {"disabled", "persona_mirroring_disabled"}
            )
            logger.info(
                "✅ Mirror engine response: %s... | Realism: %s | Time: %sms",
                (reply or "")[:50],
                realism_score,
                inference_duration_ms,
            )

        # Never overwrite a valid mirror reply due to recalibration failures.
        try:
            await check_and_recalibrate_drift(db, user_id_uuid)
        except Exception:
            logger.exception("⚠️ Drift recalibration failed; keeping generated mirror reply")
            await db.rollback()

        if not reply:
            if assistant_task_type:
                reply = build_assistant_fallback_reply(message_text, assistant_task_type)
            else:
                reply = MIRROR_FALLBACK_REPLY
            fallback_triggered = True

        # Mirror messages also grow persona confidence.
        try:
            if not extracted_traits:
                extracted_traits = derive_fallback_traits(message_text)
                logger.info(f"🔁 Using fallback trait extraction (mirror): {len(extracted_traits)} traits")

            if extracted_traits:
                await update_traits(db, user_id_uuid, extracted_traits)
                await generate_persona_snapshot(db, user_id_uuid)
                logger.info("✅ Persona updated from mirror message")
        except Exception as e:
            logger.warning(f"⚠️ Failed to update persona from mirror message: {e}")
            await db.rollback()

        if request.external_input_text:
            from app.db.models import ExternalInput
            try:
                db.add(
                    ExternalInput(
                        user_id=user_id_uuid,
                        conversation_id=conversation_id_uuid,
                        source=request.external_input_source or "pasted_prompt",
                        content=request.external_input_text,
                        extracted_markers={},
                        confidence_weight=0.1,
                    )
                )
                await db.flush()
            except Exception as ext_err:
                # External input persistence is optional and should not break chat flow.
                logger.warning("⚠️ Skipping external input persistence: %s", ext_err)
                await db.rollback()

    # Store user message (with per-message analytics) in database
    metrics = compute_message_metrics(message_text, extracted_traits)
    try:
        user_message = await crud.create_message(
            db=db,
            user_id=user_id_uuid,
            conversation_id=conversation_id_uuid,
            role="user",
            content=message_text,
            embedding=None,
            token_count=metrics["token_count"],
            emotional_intensity=metrics["emotional_intensity"],
            reflection_depth=metrics["reflection_depth"],
        )
        logger.info(f"✅ Stored user message {user_message.id}")
    except Exception as e:
        logger.error(f"❌ Failed to store user message: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to store user message: {str(e)}")

    try:
        from app.services.behavioral_memory_service import (
            record_user_reaction,
            update_linguistic_fingerprint,
        )

        await update_linguistic_fingerprint(db, user_id_uuid, message_text)
        await record_user_reaction(db, user_id_uuid, message_text)
        await db.commit()
    except Exception as fingerprint_err:
        # Behavioral memory persistence is optional and should not break main chat flow.
        logger.warning("⚠️ Skipping behavioral memory update: %s", fingerprint_err)
        await db.rollback()

    # Store AI response in database
    try:
        assistant_message = await crud.create_message(
            db=db,
            user_id=user_id_uuid,
            conversation_id=conversation_id_uuid,
            role="assistant",
            content=reply,
            embedding=None,
            token_count=len(reply.split()),
        )
        logger.info(f"✅ Stored assistant message {assistant_message.id}")
    except Exception as e:
        logger.error(f"❌ Failed to store assistant message: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to store assistant message: {str(e)}")

    # Log mirror telemetry in a best-effort manner so missing optional schema never breaks chat.
    if effective_mode == "mirror":
        try:
            from app.db.models import MirrorLog

            db.add(
                MirrorLog(
                    user_id=user_id_uuid,
                    conversation_id=conversation_id_uuid,
                    message_id=assistant_message.id,
                    inference_duration_ms=inference_duration_ms,
                    realism_score=realism_score,
                    retries_used=retries_used,
                    fallback_triggered=fallback_triggered,
                    confidence_lower=confidence_lower,
                    confidence_upper=confidence_upper,
                    confidence_tier=confidence_tier,
                    style_enforcement_strength=style_strength,
                    reaction_match_score=reaction_match_score,
                    source_weights=source_weights,
                )
            )
            await db.commit()
            logger.info("📊 Saved Mirror Observability Log")
        except Exception as telemetry_err:
            logger.warning("⚠️ Skipping mirror telemetry persistence: %s", telemetry_err)
            await db.rollback()

    # Apply the AI-generated title for new conversations.
    if title_task is not None:
        conversation_title = await title_task
        try:
            await crud.update_conversation_title(db, conversation_id_uuid, conversation_title)
        except Exception as title_err:
            logger.warning("⚠️ Failed to store conversation title: %s", title_err)
            await db.rollback()

    logger.info(f"✅ Generated response and stored 2 messages for conversation {conversation_id_uuid}")

    return ChatResponse(
        conversation_id=str(conversation_id_uuid),
        title=conversation_title,
        reply=reply,
        mirror_active=mirror_runtime_active,
        confidence_level=(confidence_tier if effective_mode == "mirror" else "medium"),
        mode=effective_mode,
        assistant_task_type=assistant_task_type,
        active_mirror_style=active_mirror_style,
        detected_emotion=detected_emotion,
        twin_policy=twin_policy,
        confidence_interval=confidence_interval,
        style_strength=style_strength,
        reaction_source=reaction_source,
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
        effective_mode = normalize_interaction_mode(mode)
        if mode and effective_mode not in {"reflection", "mirror"}:
            raise HTTPException(status_code=400, detail="Invalid mode filter. Use 'reflection' or 'mirror'.")

        user_id_uuid = UUID(user_id)
        logger.info(f"🔍 Converted user_id string to UUID: {user_id_uuid}")
        logger.info(f"📊 UUID type: {type(user_id_uuid)}")
        
        conversations = await crud.get_user_conversations(
            db=db, 
            user_id=user_id_uuid,
            mode=effective_mode
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
