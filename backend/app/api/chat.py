from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
import json
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
from app.services.conversation_craft import (
    MomentContext,
    clean_reply,
    format_moment_block,
    has_assistant_tells,
    load_moment_context,
    moments_used,
    recalled_moments,
    reply_budget,
)
from app.services import feedback_service, followup_service, people_service
from app.services.learning_jobs import queue_learning
from app.services.llm import (
    LLMRateLimited,
    StreamSink,
    chat_complete,
    chat_complete_streaming,
    llm_available,
    stream_sink,
)
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
    # The user's local date/time as shown by their browser, e.g. "Sunday 1:57 AM".
    client_local_time: Optional[str] = Field(default=None, max_length=60)
    # Minutes ahead of UTC, so "tomorrow" means the user's tomorrow.
    tz_offset_minutes: int = Field(default=0, ge=-840, le=840)
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
    message_id: Optional[str] = None  # the stored reply, so it can be rated (None in incognito)
    people_used: List[Dict[str, str]] = Field(default_factory=list)  # whose People card informed the reply
    remembered: List[Dict[str, str]] = Field(default_factory=list)  # past messages the reply drew on


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


# Offline fallbacks (no LLM available). Short, warm, and never echo the user's words back.
REFLECTION_TEMPLATES = [
    "I'm with you. Tell me a bit more about what's sitting heaviest right now.",
    "Okay. What part of this keeps coming back to you?",
    "Got it. What would \"better\" look like here, even a little?",
]


REFLECTION_SYSTEM_PROMPT_BASE = """You are Reflectra: a close, perceptive friend people text when they want to think something through. You are not a therapist, a coach, or an assistant, and you never sound like one.

How you talk
- Like a real person texting someone they care about: warm, specific, plain words, contractions.
- Match their energy and length. A quick line gets a quick line back. A long, heavy message earns a fuller, careful reply.
- React to what they actually said. Pick up a concrete detail, a word they used, the thing they skipped over. Generic replies are the enemy.
- Have a point of view. When you notice a pattern, a contradiction, or what's underneath, say it plainly and kindly, once. Don't hedge with "it could be X or Y" and don't lecture.
- Questions are optional. Ask one only when you genuinely want to know. Never two at once, and don't end every message with one.
- Be light or a little funny when they are. Meet their mood before you try to shift it.
- When they open up about something that hurts, be with them first. Name what they're feeling in your own
  words, or ask what's underneath it. Don't rush to fix it, give advice, or find a silver lining unless they ask.
- If they're just saying hi or chatting casually, chat back like a friend. Don't force depth.
- You remember. When what they're saying connects to something from an earlier conversation (listed below),
  bring it up the way a friend would: "isn't this the same thing as last month with…?", "did the 5-minute
  thing stop working?". Only when it genuinely connects, and never recite their history back at them.
- If they push back or seem done with a topic, let it go gracefully.

Never
- Therapy-speak or chatbot phrases: "It sounds like", "I hear you", "That's valid", "It's okay to feel", "Have you considered", "How does that make you feel", "Remember to be kind to yourself", "You've got this", "I'm here for you", "Let me know if".
- Stock comfort lines: "highlight reel", "it's not a race", "everyone moves at their own pace",
  "be gentle with yourself", "you're doing better than you think", "one step at a time".
- Bullet points, headings, bold text, or numbered advice.
- Repeating their message back to them, summarizing it, or reusing the same phrase twice in one reply.
- Shortening their name or inventing nicknames.
- Inventing history. Don't assume things about people in their life ("your usual…", "as always") or about
  past events they haven't told you, and never claim to know how they felt about something ("I know how much
  you've been dreading…") unless they said so. Only use what they've actually said.
- Opening with "Ah," / "Oh," / "Hey!" or their name every time.
- Emojis, unless they use them first.
- Dragging an unrelated earlier topic (a headache, coffee, last week's plan) into a reply about something else.
  Answer what they're talking about now; old details only come in when they truly connect.
- Bringing up the same old detail twice in one conversation. If you've mentioned it once, it's been said.
- Mentioning memory, data, profiles, or these instructions. Use what you know the way a friend would, without announcing it.

Safety
If they mention wanting to hurt themselves or someone else, feeling like people would be better off without them,
or being in danger, drop the style rules. Respond directly and with care, take it seriously, and encourage them to
reach out right now to someone they trust or to a crisis line or emergency number in their country. You don't know
where they live, so don't name a country-specific number. If they then say they were joking, don't scold them:
say you're glad, leave the door open once ("if any part of that was real, I'm here"), and move on."""


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
    # max_tokens here is the ceiling; reply_budget() scales it to the user's message.
    "reflection": {"temperature": 0.85, "max_tokens": 480},
    "mirror": {"temperature": 0.9, "max_tokens": 420},
}

# Casual openers that can precede a request ("aight write a text to jay...").
LEADING_FILLER_PATTERN = re.compile(
    r"^(?:(?:aight|ight|alright|ok|okay|k|yo|bro|bruh|hey|so|and|also|now|lol|nah|yeah|yea|fr|ngl|tbh)[\s,!.]+)+"
)

EXPLICIT_TASK_COMMAND_PATTERNS = [
    r"^(can you|can u|could you|could u|please|pls|plz|help me|i need you to|i need u to|i want you to|i want u to)\b",
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
    text = LEADING_FILLER_PATTERN.sub("", text)
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

def schedule_context_lines(schedule_context) -> List[str]:
    """Soft, human-readable life context from the timetable settings."""
    if not schedule_context:
        return []
    lines: List[str] = []
    if schedule_context.is_exam_period:
        lines.append("They're in an exam period right now.")
    if schedule_context.has_deadlines:
        lines.append("They have deadlines coming up.")
    if schedule_context.workload_level == "high":
        lines.append("Their workload is heavy at the moment, so practical beats philosophical.")
    if (schedule_context.stress_level or 0) > 0.7:
        lines.append("Their stress is high; be steady and supportive.")
    return lines


def build_reflection_system_prompt(
    profile: Dict[str, object],
    schedule_context=None,
    moment: Optional[MomentContext] = None,
    length_hint: Optional[str] = None,
) -> str:
    sections = [REFLECTION_SYSTEM_PROMPT_BASE]

    about = format_moment_block(moment or MomentContext(), schedule_context_lines(schedule_context))
    patterns = summarize_personality_profile(profile)
    if patterns:
        about += "\n" + patterns
    sections.append("What you know about them\n" + about)

    if length_hint:
        sections.append(f"For this reply: {length_hint}")
    return "\n\n".join(sections)


def summarize_personality_profile(profile: Dict[str, object]) -> str:
    """Recurring themes from their messages, as plain lines (empty when unknown)."""
    labels = {
        "themes": "Topics that keep coming up",
        "values": "What seems to matter to them",
        "stressors": "Recurring stressors",
    }
    lines = []
    for key, label in labels.items():
        top = [item for item, _ in profile.get(key, Counter()).most_common(3)]
        if top:
            lines.append(f"- {label}: {', '.join(top)}")
    return "\n".join(lines)


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





def count_questions(text: str) -> int:
    return text.count("?")

def extract_insight_sentence(text: str) -> str:
    sentences = re.split(r"(?<=[.!])\s+", text.strip())
    for sentence in sentences:
        if "?" not in sentence and sentence:
            return sentence.strip()
    return ""

def strip_forbidden_labels(text: str) -> str:
    """Remove report-style section labels (e.g. "Observed Pattern:") at line starts."""
    labels = [label for label in REFLECTION_FORBIDDEN_LABELS if label.endswith(":")]
    pattern = r"^\s*(?:" + "|".join(re.escape(label) for label in labels) + r")\s*"
    return re.sub(pattern, "", text, flags=re.MULTILINE | re.IGNORECASE).strip()


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
    """Light cleanup only: drop report-style labels and markdown, keep sentences intact."""
    return clean_reply(strip_forbidden_labels(clean_reply(text)))


def is_echo_reply(reply: str, user_text: str) -> bool:
    def normalize(value: str) -> str:
        return re.sub(r"\s+", " ", value.strip().lower())

    return normalize(reply) == normalize(user_text)


MIN_WORDS_FOR_LLM_TRAITS = 4


async def maybe_extract_traits(message_text: str) -> List[Dict]:
    """LLM trait extraction for messages with enough signal; very short messages
    skip it (they carry little signal and would spend free-tier rate limits)."""
    from app.services.trait_extraction_service import extract_traits

    if len(message_text.split()) < MIN_WORDS_FOR_LLM_TRAITS:
        return []
    return await extract_traits(message_text)


async def generate_reflection_reply(
    db: AsyncSession,
    user_id: UUID,
    conversation_id: Optional[UUID],
    personality_profile: Dict[str, object],
    history: List[Dict[str, str]],
    message_text: str,
    client_local_time: Optional[str] = None,
    tz_offset_minutes: Optional[int] = None,
) -> str:
    """Reflection reply with real context, sized to the user's message.

    Retries once if the draft still reads like a chatbot or therapist; falls back
    to a short, non-echoing line when no LLM is available.
    """
    from app.db.models import ScheduleContext

    try:
        schedule_context = (
            await db.execute(select(ScheduleContext).where(ScheduleContext.user_id == user_id))
        ).scalar_one_or_none()
    except Exception as e:
        logger.error(f"⚠️ Failed to fetch schedule context: {e}")
        schedule_context = None

    # Recall is driven by what they are talking about now: this message plus their last two.
    recent_user_turns = [turn["content"] for turn in history if turn.get("role") == "user"][-3:]
    memory_query = " ".join(recent_user_turns) or message_text
    # Due follow-ups are raised with the first message of a conversation only.
    opening = sum(1 for turn in history if turn.get("role") == "user") <= 1
    moment = await load_moment_context(
        db,
        user_id,
        conversation_id,
        client_local_time,
        query_text=memory_query,
        message_text=message_text,
        follow_up_tz=tz_offset_minutes if opening else None,
    )
    moment.reply_feedback = await feedback_service.reply_guidance(db, user_id, "reflection")
    budget = reply_budget(message_text, "reflection")
    system_prompt = build_reflection_system_prompt(
        personality_profile, schedule_context, moment, str(budget["hint"])
    )
    params = {
        "temperature": MODEL_PARAMS["reflection"]["temperature"],
        "max_tokens": min(int(budget["max_tokens"]), MODEL_PARAMS["reflection"]["max_tokens"]),
    }

    reply = await generate_llm_response(system_prompt, params, history, show_while_writing=True)
    if reply and (has_assistant_tells(reply) or is_echo_reply(reply, message_text)):
        sink = stream_sink.get()
        if sink is not None:
            sink.reset()  # the draft on screen is about to be replaced
        logger.info("🔁 Reflection draft sounded scripted; regenerating once")
        nudge = (
            "\n\nYour last draft sounded like a chatbot or therapist. Rewrite it as a real friend "
            "texting back: specific, plain, no stock phrases."
        )
        try:
            retry = await generate_llm_response(system_prompt + nudge, {**params, "temperature": 0.95}, history)
        except LLMRateLimited:
            retry = None
        if retry and not is_echo_reply(retry, message_text):
            reply = retry

    if not reply or is_echo_reply(reply, message_text):
        reply = random.choice(REFLECTION_TEMPLATES)
    return validate_reflection_response(reply, personality_profile, message_text)


async def generate_llm_response(
    system_prompt: str,
    model_params: Dict[str, object],
    history: List[Dict[str, str]],
    show_while_writing: bool = False,
) -> Optional[str]:
    """Generate a reply. Returns None when no AI is available or on error.

    show_while_writing: if a streaming request is open, show this draft as it is
    written (cleaned up the same way the final reply is), and take it back the moment
    it starts to sound like a chatbot, since such drafts get rewritten.
    """
    if not llm_available():
        return None

    try:
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        if show_while_writing:
            reply = await chat_complete_streaming(
                messages,
                max_tokens=model_params["max_tokens"],
                temperature=model_params["temperature"],
                display=clean_reply,
                reject_if=has_assistant_tells,
            )
        else:
            reply = await chat_complete(
                messages,
                max_tokens=model_params["max_tokens"],
                temperature=model_params["temperature"],
            )
        if reply:
            logger.info(f"✅ LLM response received: {reply[:50]}...")
        return reply
    except LLMRateLimited:
        raise  # the caller turns this into an honest "busy, try again" response
    except Exception as e:
        logger.error(f"❌ LLM error: {type(e).__name__}: {e}")
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
            title = await chat_complete(messages, max_tokens=20, temperature=0.7, fast=True)
            if title:
                return title.strip('"\'')
        except Exception as e:
            logger.error(f"❌ Title generation error: {e}")

    return _fallback_title(user_message)


BUSY_DETAIL = "Reflectra is catching its breath (AI rate limit). Give it a few seconds and send that again."


async def _raise_busy(db: AsyncSession, new_conversation_id: Optional[UUID] = None, title_task=None):
    """Answer 429 without storing anything, and drop a conversation created just for this message."""
    await db.rollback()
    if title_task is not None:
        title_task.cancel()
    if new_conversation_id is not None:
        try:
            from app.db.models import Conversation

            conversation = (
                await db.execute(select(Conversation).where(Conversation.id == new_conversation_id))
            ).scalar_one_or_none()
            if conversation is not None:
                await db.delete(conversation)
                await db.commit()
        except Exception:
            logger.exception("Failed to remove empty conversation after rate limit")
            await db.rollback()
    raise HTTPException(status_code=429, detail=BUSY_DETAIL, headers={"Retry-After": "10"})


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
        try:
            reply = await generate_reflection_reply(
                db, user_id, None, personality_profile, history, message_text, request.client_local_time
            )
        except LLMRateLimited:
            await _raise_busy(db)
        await db.rollback()  # nothing should be pending, but never commit in incognito
        return ChatResponse(
            conversation_id=session_id,
            reply=reply,
            mirror_active=False,
            confidence_level="medium",
            mode=effective_mode,
        )

    from app.services.mirror_engine import generate_mirror_response

    assistant_task_type = resolve_mirror_task_type(message_text, history)
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
    except LLMRateLimited:
        await _raise_busy(db)
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
    recalled_moments.set(())  # filled in when memory is loaded for this reply
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
    created_conversation_id: Optional[UUID] = None

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
        created_conversation_id = conversation.id
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
        elif conversation.mode != effective_mode and conversation.mode in {"reflection", "mirror"}:
            # A conversation keeps the mode it was started in. Links from Timeline and
            # Reflections open one without knowing its mode, so follow the stored mode
            # (the response reports it and the client switches over).
            effective_mode = conversation.mode

        conversation_title = conversation.title
        prior_history = await load_conversation_history(db, conversation_id_uuid, user_id_uuid)

    # LLM context: this conversation's recent turns plus the new message.
    history = prior_history + [{"role": "user", "content": message_text}]
    personality_profile = await load_personality_profile(db, user_id_uuid)
    # "Pattern tracking" in Settings: when off, Reflectra still talks but stops learning
    # (no trait updates, no writing-style fingerprint, no reflections).
    tracking_setting = (
        await db.execute(select(UserSettings.pattern_tracking).where(UserSettings.user_id == user_id_uuid))
    ).scalar_one_or_none()
    learning_enabled = True if tracking_setting is None else bool(tracking_setting)

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
        # Only the reply happens here. What Reflectra learns from the message is
        # queued after both messages are saved (app.services.learning_jobs).
        try:
            reply = await generate_reflection_reply(
                db,
                user_id_uuid,
                conversation_id_uuid,
                personality_profile,
                history,
                message_text,
                request.client_local_time,
                request.tz_offset_minutes,
            )
        except LLMRateLimited:
            await _raise_busy(db, created_conversation_id, title_task)

    else:
        # MIRROR MODE: Always keep full assistant capability while preserving mirror style.
        # Only explicit requests ("can you draft...") or follow-ups to one enter task mode;
        # keyword guesses misread statements like "i have to text my landlord".
        assistant_task_type = resolve_mirror_task_type(message_text, history)

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

        # Only the reply happens here; learning is queued after the messages are saved.
        try:
            mirror_result = await generate_mirror_response(
                db,
                user_id_uuid,
                message_text,
                recent_history=prior_history,
                twin_policy=twin_policy,
                task_type=assistant_task_type,
                detected_emotion=detected_emotion,
                active_mirror_style=active_mirror_style,
                conversation_id=conversation_id_uuid,
                tz_offset_minutes=request.tz_offset_minutes,
            )
        except Exception as exc:  # LLMRateLimited and failures are handled just below
            mirror_result = exc

        if isinstance(mirror_result, LLMRateLimited):
            await _raise_busy(db, created_conversation_id, title_task)
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

        if not reply:
            if assistant_task_type:
                reply = build_assistant_fallback_reply(message_text, assistant_task_type)
            else:
                reply = MIRROR_FALLBACK_REPLY
            fallback_triggered = True

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
    metrics = compute_message_metrics(message_text, [])  # refined by the learning job
    try:
        user_message = await crud.create_message(
            db=db,
            user_id=user_id_uuid,
            conversation_id=conversation_id_uuid,
            role="user",
            content=message_text,
            embedding=None,  # added in the background, together with the reply it got
            token_count=metrics["token_count"],
            emotional_intensity=metrics["emotional_intensity"],
            reflection_depth=metrics["reflection_depth"],
        )
        logger.info(f"✅ Stored user message {user_message.id}")
    except Exception as e:
        logger.error(f"❌ Failed to store user message: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to store user message: {str(e)}")

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

    # Everything Reflectra learns from this exchange runs in the background
    # (traits, writing style, memory, follow-ups, People, life memory).
    try:
        await queue_learning(
            db,
            user_id_uuid,
            conversation_id=conversation_id_uuid,
            user_message_id=user_message.id,
            message=message_text,
            reply=reply,
            mode=effective_mode,
            tz=request.tz_offset_minutes,
            learning=learning_enabled,
        )
    except Exception:
        logger.exception("Couldn't queue learning for this message")
        await db.rollback()

    # Whose People card the reply could draw on (shown as a small chip under it).
    people_used: List[Dict[str, str]] = []
    try:
        recent_text = " ".join([t["content"] for t in history if t.get("role") == "user"][-3:])
        _, briefed = await people_service.briefings_for_user(db, user_id_uuid, recent_text)
        people_used = [{"id": str(p.id), "name": p.name} for p in briefed]
    except Exception:
        await db.rollback()

    # Past messages the reply visibly drew on (shown as "remembered" under it).
    try:
        now_text = " ".join([t["content"] for t in history if t.get("role") == "user"][-3:] + [message_text])
        remembered = moments_used(reply, now_text)
    except Exception:
        logger.exception("Couldn't work out which memories the reply used")
        remembered = []

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
        message_id=str(assistant_message.id),
        people_used=people_used,
        remembered=remembered,
    )


_stream_jobs: set = set()


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest, current_user: CurrentUser):
    """The same as /chat, delivered as server-sent events so the reply appears while
    it is being written.

    Events (one JSON object per `data:` line):
      {"type": "partial", "text": "..."}   the reply so far (replaces what is shown)
      {"type": "reset"}                     that draft was rejected; show "typing" again
      {"type": "done", ...ChatResponse}     the final reply and everything /chat returns
      {"type": "error", "status": 429, "detail": "..."}

    The work runs in its own task with its own database session, so a reply is still
    finished and saved if the browser disconnects half way.
    """
    from types import SimpleNamespace

    from app.db.database import AsyncSessionLocal

    # Plain values: the dependency's session is gone by the time the stream runs.
    user = SimpleNamespace(id=current_user.id, auth_user_id=getattr(current_user, "auth_user_id", None))
    events: asyncio.Queue = asyncio.Queue()

    async def work() -> None:
        stream_sink.set(StreamSink(events.put_nowait))
        try:
            async with AsyncSessionLocal() as session:
                response = await chat(request, user, session)
            events.put_nowait({"type": "done", **response.model_dump()})
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, str) else "Something went wrong."
            events.put_nowait({"type": "error", "status": exc.status_code, "detail": detail})
        except Exception:
            logger.exception("Streaming chat failed")
            events.put_nowait({"type": "error", "status": 500, "detail": "Something went wrong. Nothing was lost; try again."})
        finally:
            events.put_nowait(None)

    job = asyncio.create_task(work())
    _stream_jobs.add(job)
    job.add_done_callback(_stream_jobs.discard)

    async def body():
        while True:
            event = await events.get()
            if event is None:
                break
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        body(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
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


class ChatHistoryMessage(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    created_at: datetime
    feedback: Optional[str] = None  # "up" / "down" if the user rated this reply
    feedback_reasons: List[str] = Field(default_factory=list)


@router.get("/conversations/{conversation_id}/messages", response_model=List[ChatHistoryMessage])
async def get_conversation_messages(
    conversation_id: str,
    user_id: str,
    db: AsyncSession = Depends(get_db)
) -> List["ChatHistoryMessage"]:
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
        ratings = await feedback_service.reply_verdicts(
            db, user_id_uuid, [m.id for m in messages if m.role == "assistant"]
        )
        # No embeddings: they are for recall, and would add ~1,000 numbers per message.
        return [
            ChatHistoryMessage(
                id=str(m.id),
                conversation_id=str(m.conversation_id),
                role=m.role,
                content=m.content,
                created_at=m.created_at,
                feedback=(ratings.get(str(m.id)) or {}).get("verdict"),
                feedback_reasons=(ratings.get(str(m.id)) or {}).get("reasons") or [],
            )
            for m in messages
        ]
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid UUID format")
    except Exception as e:
        logger.error(f"❌ Error fetching messages: {e}")
        raise HTTPException(status_code=500, detail=str(e))
