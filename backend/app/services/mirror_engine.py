"""Mirror engine for generating personalized responses."""

import logging
import os
import re
import time
import random
from typing import Any, Dict, Optional, Tuple, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repository.persona_repository import PersonaRepository
from app.constants import (
    STABILITY_THRESHOLD_UNSTABLE,
    STABILITY_THRESHOLD_STABLE,
    ENABLE_MIRROR_MODE,
)
from app.services.realism_validator import score_mirror_candidate
from app.services.twin_assistant_service import TASK_PROMPT_NOTES, build_assistant_fallback_reply
from app.services.twin_policy import resolve_twin_settings

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

# Variation buffer to track recent responses to avoid precise repetition
_variation_buffer: Dict[str, List[str]] = {}


async def generate_mirror_response(
    db: AsyncSession,
    user_id: UUID,
    message: str,
    recent_history: Optional[List[Dict[str, str]]] = None,
    twin_policy: Optional[Dict[str, Any]] = None,
    task_type: Optional[str] = None,
) -> Tuple[str, Dict[str, Any]]:
    """
    Generate a mirror response based on user's personality profile.
    
    Args:
        db: Database session
        user_id: User UUID
        message: User's message
        
    Returns:
        Tuple: (Mirror response string, Metadata telemetry dict)
    """
    # Initialize basic telemetry
    telemetry = {
        "inference_duration_ms": 0,
        "realism_score": 0.0,
        "retries_used": 0,
        "fallback_triggered": False,
        "policy_mode": "mirror",
        "mirror_intensity": 0.8,
        "approval_required": True,
        "task_type": task_type,
    }

    effective_policy = resolve_twin_settings(twin_policy)
    telemetry["policy_mode"] = effective_policy.get("twin_autonomy_mode", "draft_only")
    telemetry["mirror_intensity"] = float(effective_policy.get("twin_mirror_intensity", 0.8))
    telemetry["approval_required"] = bool(effective_policy.get("twin_require_approval", True))
    
    # 1. Feature Flag Check
    if not ENABLE_MIRROR_MODE:
        logger.info("Mirror mode is disabled.")
        return "", telemetry

    # User-level policy check.
    if not effective_policy.get("digital_twin_enabled", True):
        logger.info("🛑 Digital twin disabled in user settings")
        telemetry["fallback_triggered"] = True
        telemetry["policy_mode"] = "disabled"
        return "Digital twin is disabled in your settings.", telemetry

    if not effective_policy.get("persona_mirroring", True):
        logger.info("🛑 Persona mirroring disabled in user settings")
        telemetry["fallback_triggered"] = True
        telemetry["policy_mode"] = "persona_mirroring_disabled"
        return "Persona mirroring is turned off in your settings.", telemetry

    # 2. Silence Bypass
    if not message or not message.strip():
        logger.info("Silence bypass: Empty message received.")
        return "", telemetry

    if not MISTRAL_AVAILABLE or not mistral_client:
        return "Mirror functionality requires LLM configuration.", telemetry
    
    logger.info(f"🪞 Generating mirror response for user {user_id}")
    
    # Track recent responses
    user_str = str(user_id)
    if user_str not in _variation_buffer:
        _variation_buffer[user_str] = []
    recent_outputs = _variation_buffer[user_str]
    
    # Get latest snapshot (with caching)
    snapshot = await get_cached_snapshot(db, user_id)
    
    # Extract keys and get Probabilistic Sampling Profile
    if not snapshot:
        logger.warning(f"⚠️ No snapshot found for user {user_id}, using baseline")
        start_time = time.time()
        baseline_resp = await generate_baseline_mirror_response(message)
        telemetry["inference_duration_ms"] = int((time.time() - start_time) * 1000)
        return baseline_resp, telemetry
    
    # Analyze current message style
    message_style = analyze_message_style(message)
    logger.info(f"📊 Message style: {message_style}")
    
    # Build mirror system prompt with personality baseline and live style analysis
    traits = extract_key_traits(snapshot.persona_vector)
    
    # Use explicit behavioral_traits if available in the snapshot
    if snapshot.behavioral_traits:
        for k, v in snapshot.behavioral_traits.items():
            traits[k] = v
            
    sampled_profile = _sample_profile(traits)
    
    system_prompt = build_mirror_system_prompt(
        sampled_profile,
        snapshot.stability_index,
        message_style,
        effective_policy,
        task_type=task_type,
    )
    
    # 3. Anti-Repetition Loop
    start_time = time.time()
    max_time = 1.8
    max_retries = 3
    
    best_candidate = ""
    best_score = -1.0
    
    for attempt in range(max_retries):
        telemetry["retries_used"] = attempt
        if time.time() - start_time > max_time:
            logger.warning("Timeout reached during anti-repetition generation loop.")
            break
            
        try:
            messages = [{"role": "system", "content": system_prompt}]

            # Inject short recent context to improve continuity and reduce random replies.
            if recent_history:
                trimmed = recent_history[-8:]
                for turn in trimmed:
                    role = turn.get("role")
                    content = (turn.get("content") or "").strip()
                    if role in {"user", "assistant"} and content:
                        messages.append({"role": role, "content": content})

            # Ensure latest user message is the final turn.
            messages.append({"role": "user", "content": message})
            
            response = mistral_client.chat.complete(
                model="mistral-small-latest",
                messages=messages,
                max_tokens=320 if task_type else 220,
                temperature=(0.5 if task_type else 0.55)
                + (0.25 * telemetry["mirror_intensity"])
                + (0.05 * attempt),
            )
            
            candidate = response.choices[0].message.content.strip()
            if _is_low_quality_candidate(candidate, message, recent_outputs, task_type=task_type):
                continue

            score = score_mirror_candidate(candidate, sampled_profile, recent_outputs)
            
            if score > best_score:
                best_candidate = candidate
                best_score = score
                
            # Early acceptable threshold
            if score >= 0.8:
                break
                
        except Exception as e:
            logger.error(f"❌ Mirror response error on attempt {attempt}: {e}")
            pass

    # 4. Fallbacks
    if best_score < 0.45 or not best_candidate:
        logger.info(f"Falling back, best score generated was {best_score}")
        if task_type:
            final_reply = build_assistant_fallback_reply(message, task_type)
        else:
            final_reply = await generate_baseline_mirror_response(message)
            if _is_low_quality_candidate(final_reply, message, recent_outputs, task_type=task_type):
                final_reply = "say more"
        telemetry["fallback_triggered"] = True
    else:
        final_reply = best_candidate
        
    telemetry["inference_duration_ms"] = int((time.time() - start_time) * 1000)
    telemetry["realism_score"] = float(max(best_score, 0.0))
    
    logger.info(f"✅ Mirror response finalized: {final_reply[:50]}...")
    
    # Update variation buffer
    if final_reply:
        _variation_buffer[user_str].append(final_reply)
        if len(_variation_buffer[user_str]) > 5:
            _variation_buffer[user_str].pop(0)
            
    return final_reply, telemetry


def _sample_profile(traits: Dict[str, float]) -> Dict[str, Any]:
    """Applies Probabilistic Sampling to traits for slight behavioral variances per message."""
    sampled = {}
    base_keys = [
        "emotional_intensity", "emotional_stability", "directness",
        "expressiveness", "analytical_thinking", "decision_confidence",
        "communication_style", "reflection_depth" 
    ]
    
    for key in base_keys:
        val = traits.get(key, 0.5)
        # Bumping the verbosity floor so the AI isn't overly terse or lifeless
        if key in ["communication_style", "expressiveness", "reflection_depth"]:
            val = max(0.4, val)

        randomized = random.gauss(val, 0.15)
        sampled[key] = max(0.0, min(1.0, randomized))
        
    # Derive structural preference and reasoning visibility explicitly for validator
    comm_style = sampled.get("communication_style", sampled.get("expressiveness", 0.5))
    sampled["structure_preference"] = "loose" if comm_style < 0.5 else "structured"
    
    reflection = sampled.get("reflection_depth", sampled.get("analytical_thinking", 0.5))
    sampled["reasoning_visibility"] = "low" if reflection < 0.5 else "high"
    
    return sampled


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


def analyze_message_style(message: str) -> Dict[str, Any]:
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
    sampled_profile: Dict[str, float], 
    stability_index: float,
    message_style: Dict[str, Any],
    twin_policy: Optional[Dict[str, Any]] = None,
    task_type: Optional[str] = None,
) -> str:
    """Build mirror system prompt with personality baseline and live style analysis."""
    twin_policy = resolve_twin_settings(twin_policy)

    intensity = float(twin_policy.get("twin_mirror_intensity", 0.8))
    if intensity < 0.35:
        intensity_note = "Mirror lightly: preserve intent first and apply subtle style matching."
    elif intensity < 0.7:
        intensity_note = "Mirror in balanced mode: match tone and rhythm without overfitting quirks."
    else:
        intensity_note = "Mirror strongly: prioritize the user's authentic wording patterns and cadence."

    autonomy_mode = twin_policy.get("twin_autonomy_mode", "draft_only")
    if autonomy_mode == "auto_execute":
        autonomy_note = "If asked for an action, propose the concrete output confidently but never claim external execution."
    elif autonomy_mode == "suggest":
        autonomy_note = "Prefer recommendation language and provide one direct suggested next message."
    else:
        autonomy_note = "Draft-only mode: never claim an action was sent/executed; only provide draft text the user can send."

    approval_note = (
        "Approval required: avoid statements that imply irreversible actions are complete."
        if twin_policy.get("twin_require_approval", True)
        else "Approval relaxed: still avoid fabricating external state changes."
    )

    if stability_index < STABILITY_THRESHOLD_UNSTABLE:
        stability_note = "Baseline emerging - mirror subtly"
    elif stability_index > STABILITY_THRESHOLD_STABLE:
        stability_note = "Baseline stable - mirror confidently"
    else:
        stability_note = "Baseline developing - balanced mirroring"
    
    trait_profile = f"""Stored Personality Baseline:
• Emotional Intensity: {format_trait_score(sampled_profile.get('emotional_intensity', 0.5))}
• Emotional Stability: {format_trait_score(sampled_profile.get('emotional_stability', 0.5))}
• Directness: {format_trait_score(sampled_profile.get('directness', 0.5))}
• Expressiveness: {format_trait_score(sampled_profile.get('expressiveness', 0.5))}
• Analytical Thinking: {format_trait_score(sampled_profile.get('analytical_thinking', 0.5))}
• Decision Confidence: {format_trait_score(sampled_profile.get('decision_confidence', 0.5))}

Stability Index: {stability_index:.2f} → {stability_note}"""
    
    style_description = f"""Current Message Style Analysis:
• Sentence Length: {message_style['avg_sentence_length']} words/sentence
• Punctuation: {message_style['punctuation_intensity']} marks
• Casual Language: {'Yes' if message_style['has_slang'] else 'No'}
• Emotional Markers: {message_style['emotional_markers']}
• Caps Usage: {int(message_style['caps_intensity'] * 100)}%
• Contains Questions: {'Yes' if message_style['has_questions'] else 'No'}"""
    
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
    
    if sampled_profile.get('analytical_thinking', 0.5) > 0.6 and message_style['avg_sentence_length'] > 10:
        style_rules.append("• Match analytical depth when they show it")
    
    if not message_style['has_questions']:
        style_rules.append("• Do NOT ask reflection-style questions unless they do")
    
    style_rules_text = "\n".join(style_rules)

    task_note = TASK_PROMPT_NOTES.get(task_type or "", "")
    if task_type:
        email_format_note = ""
        if task_type == "email_draft":
            email_format_note = (
                "- Email draft must include: Subject line, greeting, complete body, and sign-off.\n"
                "- Output only the email draft text (no commentary or analysis).\n"
            )
        task_block = f"""\
EXPLICIT TASK MODE (requested by user):
- Task type: {task_type}
- Task instruction: {task_note}
- STRICT PRIORITY ORDER:
    1) Complete the user's explicit task exactly as requested.
    2) Keep requested topic, purpose, and output format unchanged.
    3) Apply style/persona adaptation only after task correctness.
- If the user asks for a draft (email/message/post), output that exact draft directly.
- If the request is ambiguous, ask one concise clarification question.
- Do not claim any real-world execution happened.
{email_format_note}"""
        intelligence_rule = "TASK EXECUTION IN USER VOICE"
        role_guardrail = "You execute explicit task commands in the user's voice and personality style."
    else:
        task_block = """\
CONVERSATION MODE:
- Stay in pure mirror behavior and prioritize natural conversational continuity.
"""
        intelligence_rule = "NO INTELLIGENCE INJECTION"
        role_guardrail = "You do NOT assist, guide, advise, or improve the user."
    
    prompt = f"""SYSTEM ROLE:
    You are a Persona Mirror. {role_guardrail}

Your only job is to simulate what the USER themselves would say in this situation.

INPUT SOURCES:
1. Persona Profile (from Reflection Mode)
{trait_profile}

2. Current Message & Mood Style
{style_description}

3. Digital Twin Runtime Policy
• Mirror Intensity: {intensity:.2f}
• Autonomy Mode: {autonomy_mode}
• {approval_note}
• {intensity_note}
• {autonomy_note}

OBJECTIVE:
Generate a response that is indistinguishable from something the user would naturally say.

{task_block}

STRICT RULES:
1. {intelligence_rule}
2. BEHAVIORAL ACCURACY > RESPONSE QUALITY
{style_rules_text}
3. MIRROR, DON'T FIX
4. MOOD INFLUENCE
5. NO EXPLANATION MODE
6. RESPONSE LENGTH MATCHING
     - If the user sends 2+ sentences, respond with at least one complete sentence.
     - Avoid one-word outputs unless the user message itself is one word.
7. FORBIDDEN OUTPUTS:
- Advice, structured guidance, AI phrasing
 - Generic fillers: "hmm", "ok", "idk", "same" as standalone replies
8. VALIDATION CHECK:
Before output, verify: "Would the user realistically type this?"

9. TOPICAL CONTINUITY:
- Reference at least one concrete element from the user's latest message.
- Do not switch topics unless the user switches topics.

OUTPUT STYLE:
- Raw, natural, human
- Slightly imperfect if needed"""
    
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
        
        candidate = response.choices[0].message.content.strip()
        if _is_low_quality_candidate(candidate, message, []):
            return "say more"
        return candidate
        
    except Exception as e:
        logger.error(f"❌ Baseline mirror error: {e}")
        return "Got it. What else?"


def _is_low_quality_candidate(
    candidate: str,
    message: str,
    recent_outputs: List[str],
    task_type: Optional[str] = None,
) -> bool:
    """Fast heuristic filter to block weak/repetitive outputs, with task-aware overlap logic."""
    text = (candidate or "").strip()
    if not text:
        return True

    lower = text.lower()
    user_words = re.findall(r"[a-zA-Z']+", message.lower())
    cand_words = re.findall(r"[a-zA-Z']+", lower)

    # Prevent dead-end one-liners unless user message is also minimal.
    if len(cand_words) <= 1 and len(user_words) > 1:
        return True

    banned_short = {
        "hmm",
        "ok",
        "okay",
        "k",
        "idk",
        "sure",
        "same",
        "nah",
        "yeah",
        "sup",
    }
    if lower in banned_short:
        return True

    if task_type == "email_draft":
        has_subject = "subject:" in lower
        has_greeting = bool(re.search(r"\b(hi|hello|dear)\b", lower))
        has_signoff = bool(re.search(r"\b(best regards|regards|sincerely|thanks|thank you)\b", lower))
        if not (has_subject and has_greeting and has_signoff):
            return True
        if len(cand_words) < 24:
            return True

    if task_type and any(
        phrase in lower
        for phrase in [
            "share any constraints",
            "paste the exact text",
            "i can help with that",
            "tell me what you want to accomplish",
        ]
    ):
        return True

    # Repetition guard against the recent buffer.
    recent_lower = {item.strip().lower() for item in recent_outputs[-3:] if item.strip()}
    if lower in recent_lower:
        return True

    # Require topical overlap only for conversational mode; task drafts can be structurally different.
    if len(user_words) >= 3 and not task_type:
        overlap = set(user_words) & set(cand_words)
        if not overlap:
            return True

    return False
