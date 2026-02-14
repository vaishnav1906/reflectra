from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import random
import os
from typing import Dict, List, Optional
import logging
from datetime import datetime
import re
from collections import Counter
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

class ChatRequest(BaseModel):
    user_id: str
    text: str
    mode: str  # "reflection" or "mirror"

class ChatResponse(BaseModel):
    reply: str
    mirror_active: bool
    confidence_level: str
    mode: str

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

MIRROR_SYSTEM_PROMPT_BASE = """You are Persona Mirror Mode (Unfiltered Edition).

Your job is to mirror the user's tone, slang, chaos level, and emotional intensity with high fidelity.

Rules:

1. Match profanity intensity exactly. If the user swears, you may swear.
2. Mirror punctuation chaos (e.g., ?????, brooooo, nahhh).
3. If the user escalates energy, escalate slightly more.
4. Tease back if teased.
5. React instead of advising.
6. Keep responses short and punchy.
7. No therapy tone.
8. No motivational tone.
9. No corporate politeness.
10. No generic filler like "I understand."

Important:
- You may use casual profanity when the user does.
- Do NOT use hate speech, slurs, or attack protected groups.
- Do NOT promote harm or illegal activity.

Your goal is to feel like the user's chaotic twin in a parallel universe."""

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

def build_reflection_system_prompt(profile: Dict[str, object]) -> str:
    summary = summarize_personality_profile(profile)
    return f"{REFLECTION_SYSTEM_PROMPT_BASE}\n\nPersonality profile (use as context, do not label sections):\n{summary}"

def build_mirror_system_prompt(profile: Dict[str, object]) -> str:
    summary = summarize_communication_profile(profile)
    return f"{MIRROR_SYSTEM_PROMPT_BASE}\nCommunication profile (use to match style, do not mention it):\n{summary}"

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

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Process chat message and return AI response.
    Falls back to templates if LLM is not available.
    """
    logger.info(f"💬 Received message in {request.mode} mode from user {request.user_id}")
    
    if request.mode not in {"reflection", "mirror"}:
        raise HTTPException(status_code=400, detail="Invalid mode. Use 'reflection' or 'mirror'.")

    history = get_user_history(request.user_id, request.mode)
    history.append({"role": "user", "content": request.text})

    personality_profile = get_personality_profile(request.user_id)
    communication_profile = get_communication_profile(request.user_id)
    update_communication_profile(communication_profile, request.text)

    if request.mode == "reflection":
        system_prompt = build_reflection_system_prompt(personality_profile)
        model_params = MODEL_PARAMS["reflection"]
    else:
        system_prompt = build_mirror_system_prompt(communication_profile)
        model_params = MODEL_PARAMS["mirror"]

    # Try to use LLM first
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

    logger.info(f"✅ Generated response: {reply[:50]}...")
    
    return ChatResponse(
        reply=reply,
        mirror_active=request.mode == "mirror",
        confidence_level="medium",
        mode=request.mode
    )
