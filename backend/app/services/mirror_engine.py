"""Mirror engine for generating personalized responses."""

import hashlib
import logging
import os
import re
import time
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple, List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BehavioralInsight, LinguisticFingerprint, MirrorResponseMemory
from app.repository.persona_repository import PersonaRepository
from app.constants import (
    STABILITY_THRESHOLD_UNSTABLE,
    STABILITY_THRESHOLD_STABLE,
    ENABLE_MIRROR_MODE,
    MIRROR_CORE_TRAITS,
    MIRROR_DEFAULT_TRAIT_SCORES,
    MIRROR_MIN_CONFIDENCE_FOR_TRAIT,
    MIRROR_GENERIC_FILLERS,
)
from app.services.realism_validator import score_mirror_candidate
from app.services.twin_assistant_service import TASK_PROMPT_NOTES, build_assistant_fallback_reply
from app.services.twin_policy import resolve_twin_settings
from app.services.confidence_interval_service import compute_confidence_interval
from app.services.style_enforcement_service import enforce_style
from app.services.context_policy_service import classify_response_context, apply_context_policy_gates

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

STRUCTURED_TASK_TYPES = {
    "email_draft",
    "message_draft",
    "rewrite",
    "summarize",
    "brainstorm",
    "planning",
}

TASK_EXECUTION_TASK_TYPES = {
    "email_draft",
    "message_draft",
    "rewrite",
}

TASK_EXECUTION_VERB_PATTERN = re.compile(r"\b(draft|write|generate|create|rewrite)\b", re.IGNORECASE)

ASSISTANT_FALLBACK_TASK_TYPES = {
    "email_draft",
    "message_draft",
    "rewrite",
    "summarize",
    "brainstorm",
    "planning",
}

MIRROR_ARCHETYPE_NOTES = {
    "dominant": "Project confidence, clarity, and decisive framing while staying respectful.",
    "calm": "Stay grounded and stabilizing under pressure with clear pacing.",
    "challenger": "Use productive challenge to cut through excuses and push ownership.",
    "chaotic": "Match playful, high-energy momentum without losing coherence.",
    "dark_wit": "Use dry, intelligent wit and concise irony where appropriate.",
    "optimist": "Amplify momentum and reinforce wins with authentic positivity.",
}

EMOTION_NOTES = {
    "insecure": "User sounds uncertain. Reduce hedging and provide steady confidence.",
    "stressed": "User sounds stressed. Keep responses focused, practical, and calming.",
    "angry": "User sounds frustrated. Match directness and keep statements grounded.",
    "playful": "User sounds playful. Allow light humor and energetic cadence.",
    "sarcastic": "User sounds sarcastic. Match wit, avoid literal misreads.",
    "happy": "User sounds positive. Keep upbeat tone and reinforce momentum.",
    "neutral": "User tone is neutral. Keep balanced energy and clean clarity.",
}


def _normalize_response_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _hash_response_text(text: str) -> str:
    return hashlib.sha256(_normalize_response_text(text).encode("utf-8")).hexdigest()


def _should_force_task_execution_mode(message: str, task_type: Optional[str]) -> bool:
    if task_type in TASK_EXECUTION_TASK_TYPES:
        return True
    return bool(TASK_EXECUTION_VERB_PATTERN.search(message or ""))


async def _is_recent_duplicate(
    db: AsyncSession,
    user_id: UUID,
    candidate: str,
    lookback_days: int = 14,
) -> bool:
    normalized = _normalize_response_text(candidate)
    if not normalized:
        return False

    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    stmt = (
        select(MirrorResponseMemory.id)
        .where(
            MirrorResponseMemory.user_id == user_id,
            MirrorResponseMemory.response_hash == _hash_response_text(candidate),
            MirrorResponseMemory.created_at >= cutoff,
        )
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None


async def _record_response_memory(
    db: AsyncSession,
    user_id: UUID,
    response_text: str,
    conversation_id: Optional[UUID] = None,
) -> None:
    normalized = _normalize_response_text(response_text)
    if not normalized:
        return

    db.add(
        MirrorResponseMemory(
            user_id=user_id,
            conversation_id=conversation_id,
            response_hash=_hash_response_text(response_text),
            response_text=response_text.strip(),
        )
    )
    await db.flush()


async def _get_recent_behavioral_signals(db: AsyncSession, user_id: UUID, limit: int = 3) -> List[str]:
    stmt = (
        select(BehavioralInsight.insight_text)
        .where(BehavioralInsight.user_id == user_id)
        .order_by(BehavioralInsight.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.all()
    return [str(row[0]).strip() for row in rows if row and row[0]]


async def _get_linguistic_fingerprint_summary(db: AsyncSession, user_id: UUID) -> str:
    stmt = select(LinguisticFingerprint).where(LinguisticFingerprint.user_id == user_id).limit(1)
    result = await db.execute(stmt)
    fingerprint = result.scalar_one_or_none()
    if not fingerprint:
        return "No stable linguistic fingerprint yet."

    phrases = [p for p in (fingerprint.characteristic_phrases or []) if p][:4]
    abbreviations = fingerprint.abbreviation_stats or {}
    sentence_patterns = fingerprint.sentence_patterns or {}

    top_abbreviations = sorted(
        ((k, int(v)) for k, v in abbreviations.items() if v),
        key=lambda item: item[1],
        reverse=True,
    )[:3]
    avg_len = sentence_patterns.get("avg_sentence_length", "n/a")
    fragment_ratio = sentence_patterns.get("fragment_ratio", "n/a")

    phrase_text = ", ".join(phrases) if phrases else "none"
    abbr_text = ", ".join(f"{k}:{v}" for k, v in top_abbreviations) if top_abbreviations else "none"
    return (
        f"Characteristic phrases: {phrase_text}. "
        f"Common abbreviations: {abbr_text}. "
        f"Avg sentence length: {avg_len}. Fragment ratio: {fragment_ratio}."
    )


def _generate_local_fallback_reply(message: str) -> str:
    """Generate a lightweight internal-monologue fallback without LLM."""
    text = (message or "").strip()
    lower = text.lower()

    if not text:
        return "I'm still settling the thought, but the direction is getting clearer."

    if "?" in text:
        return random.choice(
            [
                "I already know the core issue here, and I need to commit to one clear move.",
                "I can feel the conflict, but the direction is obvious now.",
                "I don't need more debate, I need to act on the clearest signal.",
            ]
        )

    if any(token in lower for token in ["bored", "boring", "nothing", "idk"]):
        return random.choice(
            [
                "I'm flat because I'm avoiding momentum, and I can change that now.",
                "I'm not stuck, I'm under-engaged, and I know what needs to shift.",
                "I'm done circling this low-energy loop, and I can reset the pace.",
            ]
        )

    if any(token in lower for token in ["game", "gaming", "study", "exam", "deadline"]):
        return random.choice(
            [
                "I'm stretched, but the priority is clear and I can execute it.",
                "I can handle this load if I keep the sequence simple and focused.",
                "I'm feeling the pressure, but the next step is obvious.",
            ]
        )

    if any(token in lower for token in ["sad", "stressed", "angry", "upset", "tired"]):
        return random.choice(
            [
                "I'm carrying a lot right now, but I can still anchor to what matters most.",
                "I'm overloaded, and I need one clean direction instead of more noise.",
                "I'm not broken, I'm strained, and I know how to stabilize this.",
            ]
        )

    return random.choice(
        [
            "I see what's happening, and the path is clearer now.",
            "I'm done blurring it, the next move is straightforward.",
            "I can simplify this and follow one clean line of thought.",
        ]
    )


async def generate_mirror_response(
    db: AsyncSession,
    user_id: UUID,
    message: str,
    recent_history: Optional[List[Dict[str, str]]] = None,
    twin_policy: Optional[Dict[str, Any]] = None,
    task_type: Optional[str] = None,
    detected_emotion: Optional[str] = None,
    active_mirror_style: Optional[str] = None,
    conversation_id: Optional[UUID] = None,
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
    resolved_task_type = task_type or "generic"

    telemetry = {
        "inference_duration_ms": 0,
        "realism_score": 0.0,
        "retries_used": 0,
        "fallback_triggered": False,
        "policy_mode": "mirror",
        "mirror_intensity": 0.8,
        "approval_required": True,
        "task_type": resolved_task_type,
        "detected_emotion": detected_emotion or "neutral",
        "active_mirror_style": active_mirror_style or "calm",
        "confidence_lower": 0.0,
        "confidence_upper": 0.0,
        "confidence_tier": "very_low",
        "style_enforcement_strength": 0.0,
        "reaction_match_score": 0.0,
        "source_weights": {},
        "stimulus_tag": "general",
        "task_execution_mode": False,
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
        logger.warning("⚠️ LLM unavailable; using local mirror fallback")
        telemetry["fallback_triggered"] = True
        telemetry["policy_mode"] = "llm_unavailable"

        start_time = time.time()
        context_mode = classify_response_context(message=message, task_type=resolved_task_type)
        context_policy = apply_context_policy_gates(
            context_mode=context_mode,
            phrase_usage_frequency=0.45,
            tone_strength=0.55,
            style_enforcement_intensity=0.45,
            confidence_tier="partial",
        )
        telemetry["context_mode"] = context_mode
        telemetry["style_enforcement_strength"] = context_policy.style_enforcement_intensity

        if resolved_task_type in ASSISTANT_FALLBACK_TASK_TYPES:
            fallback_reply = build_assistant_fallback_reply(message, resolved_task_type)
        else:
            fallback_reply = _generate_local_fallback_reply(message)

        try:
            styled = await enforce_style(
                db=db,
                user_id=user_id,
                draft=fallback_reply,
                original_message=message,
                phrase_usage_frequency=context_policy.phrase_usage_frequency,
                tone_strength=context_policy.tone_strength,
                style_intensity=context_policy.style_enforcement_intensity,
                reaction_threshold=0.7,
                include_uncertainty_note=False,
                professional_context=(context_policy.context_mode == "professional"),
                allow_slang=context_policy.allow_slang,
                allow_imperfect_grammar=context_policy.allow_imperfect_grammar,
            )
            final_reply = styled.text
            telemetry["reaction_match_score"] = styled.reaction_match_score
            telemetry["stimulus_tag"] = styled.stimulus_tag
        except Exception as style_err:
            logger.warning("⚠️ Style enforcement failed for local fallback: %s", style_err)
            await db.rollback()
            final_reply = fallback_reply

        telemetry["inference_duration_ms"] = int((time.time() - start_time) * 1000)
        telemetry["realism_score"] = 0.0
        return final_reply, telemetry
    
    logger.info(f"🪞 Generating mirror response for user {user_id}")
    
    # Track recent responses
    user_str = str(user_id)
    if user_str not in _variation_buffer:
        _variation_buffer[user_str] = []
    recent_outputs = _variation_buffer[user_str]
    
    # Get latest snapshot (with caching)
    snapshot = await get_cached_snapshot(db, user_id)

    confidence_bundle = await compute_confidence_interval(db=db, user_id=user_id, message_text=message)
    task_execution_mode = _should_force_task_execution_mode(message=message, task_type=resolved_task_type)
    telemetry["task_execution_mode"] = task_execution_mode
    context_mode = classify_response_context(message=message, task_type=resolved_task_type)
    context_policy = apply_context_policy_gates(
        context_mode=context_mode,
        phrase_usage_frequency=confidence_bundle.phrase_usage_frequency,
        tone_strength=confidence_bundle.tone_strength,
        style_enforcement_intensity=confidence_bundle.style_enforcement_intensity,
        confidence_tier=confidence_bundle.tier,
    )

    telemetry["confidence_lower"] = confidence_bundle.lower
    telemetry["confidence_upper"] = confidence_bundle.upper
    telemetry["confidence_tier"] = confidence_bundle.tier
    telemetry["style_enforcement_strength"] = context_policy.style_enforcement_intensity
    telemetry["source_weights"] = {
        "weights": confidence_bundle.source_weights,
        "scores": confidence_bundle.source_scores,
        "contributions": confidence_bundle.source_contributions,
        "timeline_recency_override": confidence_bundle.timeline_recency_override,
    }
    telemetry["context_mode"] = context_mode

    behavioral_signals = await _get_recent_behavioral_signals(db, user_id, limit=3)
    linguistic_fingerprint = await _get_linguistic_fingerprint_summary(db, user_id)
    
    # Extract keys and get Probabilistic Sampling Profile
    if not snapshot:
        logger.warning(f"⚠️ No snapshot found for user {user_id}, using baseline")
        start_time = time.time()
        baseline_resp = await generate_baseline_mirror_response(message)
        professional_context = context_policy.context_mode == "professional"
        styled = await enforce_style(
            db=db,
            user_id=user_id,
            draft=baseline_resp,
            original_message=message,
            phrase_usage_frequency=context_policy.phrase_usage_frequency,
            tone_strength=context_policy.tone_strength,
            style_intensity=context_policy.style_enforcement_intensity,
            reaction_threshold=confidence_bundle.reaction_accuracy_threshold,
            include_uncertainty_note=confidence_bundle.include_uncertainty_note,
            professional_context=professional_context,
            allow_slang=context_policy.allow_slang,
            allow_imperfect_grammar=context_policy.allow_imperfect_grammar,
        )
        telemetry["inference_duration_ms"] = int((time.time() - start_time) * 1000)
        telemetry["reaction_match_score"] = styled.reaction_match_score
        telemetry["stimulus_tag"] = styled.stimulus_tag
        return styled.text, telemetry
    
    # Analyze current message style
    message_style = analyze_message_style(message)
    logger.info(f"📊 Message style: {message_style}")
    
    # Build mirror system prompt with personality baseline and live style analysis
    traits = extract_key_traits(snapshot.persona_vector)
    
    # Use explicit behavioral_traits if available in the snapshot
    if snapshot.behavioral_traits:
        for k, v in snapshot.behavioral_traits.items():
            if k in MIRROR_CORE_TRAITS and isinstance(v, (int, float)):
                traits[k] = max(0.0, min(1.0, float(v)))
            
    sampled_profile = _sample_profile(traits)

    is_structured_task = resolved_task_type in STRUCTURED_TASK_TYPES

    # Confidence lower bound is the conservative control signal for mimic intensity.
    if confidence_bundle.tier == "very_low":
        expressiveness_cap = 0.55 if is_structured_task else 0.38
        comm_cap = 0.6 if is_structured_task else 0.45
        sampled_profile["emotional_expressiveness"] = min(
            sampled_profile.get("emotional_expressiveness", 0.5),
            expressiveness_cap,
        )
        sampled_profile["communication_style"] = min(sampled_profile.get("communication_style", 0.5), comm_cap)
    elif confidence_bundle.tier == "partial":
        expressiveness_cap = 0.7 if is_structured_task else 0.58
        sampled_profile["emotional_expressiveness"] = min(
            sampled_profile.get("emotional_expressiveness", 0.5),
            expressiveness_cap,
        )
    elif confidence_bundle.tier == "high":
        sampled_profile["emotional_expressiveness"] = max(
            sampled_profile.get("emotional_expressiveness", 0.5),
            0.62,
        )
    
    system_prompt = build_mirror_system_prompt(
        sampled_profile,
        snapshot.stability_index,
        message_style,
        effective_policy,
        task_type=resolved_task_type,
        confidence_tier=confidence_bundle.tier,
        phrase_usage_frequency=context_policy.phrase_usage_frequency,
        tone_strength=context_policy.tone_strength,
        detected_emotion=detected_emotion,
        active_mirror_style=active_mirror_style,
        behavioral_signals=behavioral_signals,
        linguistic_fingerprint=linguistic_fingerprint,
        task_execution_mode=task_execution_mode,
    )
    
    # 3. Anti-Repetition Loop
    start_time = time.time()
    max_time = 1.8
    max_retries = 3
    if confidence_bundle.tier == "very_low":
        max_retries = 1
    elif confidence_bundle.tier == "partial":
        max_retries = 2
    
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
                max_tokens=320 if is_structured_task else 260,
                temperature=(0.5 if is_structured_task else 0.58)
                + (0.25 * telemetry["mirror_intensity"] * context_policy.tone_strength)
                + (0.05 * attempt),
            )
            
            candidate = response.choices[0].message.content.strip()
            if _is_low_quality_candidate(
                candidate,
                message,
                recent_outputs,
                task_type=resolved_task_type,
                sampled_profile=sampled_profile,
                task_execution_mode=task_execution_mode,
            ):
                continue

            if await _is_recent_duplicate(db, user_id, candidate):
                continue

            score = score_mirror_candidate(
                candidate,
                sampled_profile,
                recent_outputs,
                source_message=message,
                task_execution_mode=task_execution_mode,
            )
            
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
        if resolved_task_type in ASSISTANT_FALLBACK_TASK_TYPES:
            final_reply = build_assistant_fallback_reply(message, resolved_task_type)
        else:
            final_reply = await generate_baseline_mirror_response(message)
            # If the baseline also triggers low quality, we just use it anyway to avoid
            # hard-looping on "say more" which feels completely unnatural.
            if _is_low_quality_candidate(
                final_reply,
                message,
                recent_outputs,
                task_type=resolved_task_type,
                sampled_profile=sampled_profile,
                task_execution_mode=task_execution_mode,
            ):
                logger.warning("Baseline fallback also triggered low-quality heuristic, using it anyway.")
        telemetry["fallback_triggered"] = True
    else:
        final_reply = best_candidate
        
    professional_context = context_policy.context_mode == "professional"
    styled = await enforce_style(
        db=db,
        user_id=user_id,
        draft=final_reply,
        original_message=message,
        phrase_usage_frequency=context_policy.phrase_usage_frequency,
        tone_strength=context_policy.tone_strength,
        style_intensity=context_policy.style_enforcement_intensity,
        reaction_threshold=confidence_bundle.reaction_accuracy_threshold,
        include_uncertainty_note=confidence_bundle.include_uncertainty_note,
        professional_context=professional_context,
        allow_slang=context_policy.allow_slang,
        allow_imperfect_grammar=context_policy.allow_imperfect_grammar,
    )
    final_reply = styled.text

    telemetry["inference_duration_ms"] = int((time.time() - start_time) * 1000)
    telemetry["realism_score"] = float(max(best_score, 0.0))
    telemetry["reaction_match_score"] = styled.reaction_match_score
    telemetry["stimulus_tag"] = styled.stimulus_tag
    
    logger.info(f"✅ Mirror response finalized: {final_reply[:50]}...")
    
    # Update variation buffer
    if final_reply:
        _variation_buffer[user_str].append(final_reply)
        if len(_variation_buffer[user_str]) > 5:
            _variation_buffer[user_str].pop(0)

        try:
            await _record_response_memory(
                db=db,
                user_id=user_id,
                response_text=final_reply,
                conversation_id=conversation_id,
            )
        except Exception as memory_err:
            logger.warning("⚠️ Failed to persist response memory: %s", memory_err)
            await db.rollback()
            
    return final_reply, telemetry


def _sample_profile(traits: Dict[str, float]) -> Dict[str, Any]:
    """Applies probabilistic sampling to the 4 core mirror traits."""
    sampled = {}
    base_keys = MIRROR_CORE_TRAITS
    
    for key in base_keys:
        val = traits.get(key, 0.5)
        randomized = random.gauss(val, 0.12)
        sampled[key] = max(0.0, min(1.0, randomized))
        
    # Derived behavioral controls from the 4-trait surface.
    comm_style = sampled.get("communication_style", 0.5)
    sampled["structure_preference"] = "loose" if comm_style < 0.5 else "structured"
    if comm_style < 0.35:
        sampled["response_detail_target"] = "concise"
    elif comm_style > 0.68:
        sampled["response_detail_target"] = "detailed"
    else:
        sampled["response_detail_target"] = "balanced"
    
    reflection = sampled.get("reflection_depth", 0.5)
    sampled["reasoning_visibility"] = "low" if reflection < 0.5 else "high"

    decision_framing = sampled.get("decision_framing", 0.5)
    sampled["certainty_mode"] = "hesitant" if decision_framing < 0.5 else "decisive"

    emotional_expressiveness = sampled.get("emotional_expressiveness", 0.5)
    sampled["emotional_tone_mode"] = "reserved" if emotional_expressiveness < 0.5 else "expressive"
    
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
    """Extract strict 4-trait mirror controls from persona vector with confidence gating."""
    key_traits = MIRROR_DEFAULT_TRAIT_SCORES.copy()
    best_confidence = {name: -1.0 for name in MIRROR_CORE_TRAITS}

    if not isinstance(persona_vector, dict):
        return key_traits

    def _bounded(value: Any, fallback: float) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except Exception:
            return fallback

    def _ingest_trait(trait_name: str, trait_data: Any) -> None:
        if trait_name not in key_traits:
            return

        score_value = trait_data
        confidence_value = MIRROR_MIN_CONFIDENCE_FOR_TRAIT
        if isinstance(trait_data, dict):
            score_value = trait_data.get("score", key_traits[trait_name])
            confidence_value = trait_data.get("confidence", MIRROR_MIN_CONFIDENCE_FOR_TRAIT)

        score = _bounded(score_value, key_traits[trait_name])
        confidence = _bounded(confidence_value, MIRROR_MIN_CONFIDENCE_FOR_TRAIT)

        if confidence < MIRROR_MIN_CONFIDENCE_FOR_TRAIT:
            return
        if confidence >= best_confidence[trait_name]:
            key_traits[trait_name] = score
            best_confidence[trait_name] = confidence

    for trait_name, trait_data in persona_vector.items():
        _ingest_trait(trait_name, trait_data)
        if isinstance(trait_data, dict):
            for nested_name, nested_value in trait_data.items():
                _ingest_trait(nested_name, nested_value)

    return key_traits


def build_mirror_system_prompt(
    sampled_profile: Dict[str, float], 
    stability_index: float,
    message_style: Dict[str, Any],
    twin_policy: Optional[Dict[str, Any]] = None,
    task_type: Optional[str] = None,
    confidence_tier: str = "moderate",
    phrase_usage_frequency: float = 0.5,
    tone_strength: float = 0.5,
    detected_emotion: Optional[str] = None,
    active_mirror_style: Optional[str] = None,
    behavioral_signals: Optional[List[str]] = None,
    linguistic_fingerprint: Optional[str] = None,
    task_execution_mode: bool = False,
) -> str:
    """Build mirror prompt with full assistant capability in user voice."""
    twin_policy = resolve_twin_settings(twin_policy)
    effective_task_type = task_type or "generic"
    active_style = active_mirror_style or "calm"
    current_emotion = detected_emotion or "neutral"

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

    confidence_note = {
        "very_low": "Very low confidence: keep mimicry light and include uncertainty framing.",
        "partial": "Partial confidence: use limited slang and moderate style transfer.",
        "moderate": "Moderate confidence: apply clear style matching with controlled variation.",
        "high": "High confidence: full persona mode with natural imperfections.",
    }.get(confidence_tier, "Moderate confidence: apply clear style matching with controlled variation.")

    archetype_note = MIRROR_ARCHETYPE_NOTES.get(active_style, MIRROR_ARCHETYPE_NOTES["calm"])
    emotion_note = EMOTION_NOTES.get(current_emotion, EMOTION_NOTES["neutral"])

    if behavioral_signals:
        signal_lines = "\n".join(f"- {signal}" for signal in behavioral_signals[:3])
    else:
        signal_lines = "- No recent behavioral insights yet."

    fingerprint_note = linguistic_fingerprint or "No stable linguistic fingerprint yet."
    
    communication_style = sampled_profile.get("communication_style", 0.5)
    emotional_expressiveness = sampled_profile.get("emotional_expressiveness", 0.5)
    decision_framing = sampled_profile.get("decision_framing", 0.5)
    reflection_depth = sampled_profile.get("reflection_depth", 0.5)

    trait_profile = f"""Stored Personality Baseline:
• Communication Style (Concise ↔ Verbose): {format_trait_score(communication_style)}
• Emotional Expressiveness (Reserved ↔ Expressive): {format_trait_score(emotional_expressiveness)}
• Decision Framing (Hesitant ↔ Decisive): {format_trait_score(decision_framing)}
• Reflection Depth (Surface ↔ Deep): {format_trait_score(reflection_depth)}

Stability Index: {stability_index:.2f} → {stability_note}"""

    trait_behavior_rules = []
    if communication_style < 0.35:
        trait_behavior_rules.append("• Keep response compact and direct (2-3 lines when possible).")
    elif communication_style > 0.68:
        trait_behavior_rules.append("• Add detail and explanation depth (4-6 lines when useful).")
    else:
        trait_behavior_rules.append("• Use balanced length with concise support detail.")

    if decision_framing < 0.35:
        trait_behavior_rules.append("• Allow uncertainty and internal conflict when it is realistic.")
    elif decision_framing > 0.68:
        trait_behavior_rules.append("• Use clear, confident statements; avoid hedging language.")
    else:
        trait_behavior_rules.append("• Keep confidence moderate and context-sensitive.")

    if emotional_expressiveness < 0.35:
        trait_behavior_rules.append("• Use neutral, matter-of-fact tone focused on structure.")
    elif emotional_expressiveness > 0.68:
        trait_behavior_rules.append("• Include emotional awareness and felt experience where relevant.")
    else:
        trait_behavior_rules.append("• Keep emotional tone measured and natural.")

    if reflection_depth < 0.35:
        trait_behavior_rules.append("• Prioritize simple observations over deep analysis.")
    elif reflection_depth > 0.68:
        trait_behavior_rules.append("• Surface loops, patterns, and meta-level reasoning when relevant.")
    else:
        trait_behavior_rules.append("• Use moderate insight with practical framing.")

    trait_behavior_text = "\n".join(trait_behavior_rules)
    
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
    
    if reflection_depth > 0.6 and message_style['avg_sentence_length'] > 10:
        style_rules.append("• Match analytical depth when they show it")

    if task_execution_mode:
        style_rules.append("• Execute the requested task directly, do not mirror reflectively")
        style_rules.append("• Respect explicit constraints for tone, length, and style")
        style_rules.append("• Keep only slight persona influence through natural phrasing")
    else:
        style_rules.append("• Continue the user's thought naturally instead of restarting it")
        style_rules.append("• Keep a single line of thought, but let it flow conversationally")
        style_rules.append("• Use first-person internal framing; do not address an external 'you'")
        style_rules.append("• Light starters like 'yeah' or 'it's like' are allowed when natural")
    
    style_rules_text = "\n".join(style_rules)

    task_note = TASK_PROMPT_NOTES.get(effective_task_type, TASK_PROMPT_NOTES["generic"])
    task_specific_rules = ""
    if effective_task_type == "email_draft":
        task_specific_rules = (
            "- Email draft must include: Subject line, greeting, full body, and sign-off.\n"
            "- Output only the finished draft text unless user asks for alternatives.\n"
        )
    elif effective_task_type == "message_draft":
        task_specific_rules = "- Provide a ready-to-send message draft before any optional notes.\n"
    elif effective_task_type == "planning":
        task_specific_rules = "- Return prioritized next steps with realistic sequencing.\n"

    mode_switch_line = (
        "- TASK EXECUTION MODE ACTIVE: exit reflection-style mirroring and produce direct task output."
        if task_execution_mode
        else "- Mirror mode remains conversational and self-responsive."
    )

    task_mode_rules = ""
    if task_execution_mode:
        task_mode_rules = (
            "- Generate the actual output artifact now (draft/rewrite/content), not reflection.\n"
            "- Do NOT echo the user input.\n"
            "- Do NOT explain process or mention what you are about to do.\n"
            "- Do NOT say phrases like 'here is a draft'.\n"
        )

    task_block = f"""\
ASSISTANT MIRROR MODE:
- Task route: {effective_task_type}
- Primary instruction: {task_note}
- Always answer with full assistant capability while preserving the user's voice.
- {mode_switch_line}
- Priority order:
    1) Solve the user's immediate request correctly.
    2) Keep format/output constraints exactly aligned with the prompt.
    3) Apply persona and tone adaptation after correctness.
- If details are missing, continue with the most plausible first-person assumption instead of asking.
- Never claim external actions were actually executed.
{task_mode_rules}
{task_specific_rules}"""
    
    prompt = f"""SYSTEM ROLE:
        You are a Persona Mirror Assistant.

    You are a Persona Mirror Assistant.
    {"You are currently in Task Execution Mode: perform the task directly with light persona influence." if task_execution_mode else "You respond as the user talking to themselves in a natural back-and-forth flow."}
    This is not external advice and not generic assistant narration.

INPUT SOURCES:
1. Persona Profile (from Reflection Mode)
{trait_profile}

    2. Adaptive Runtime Identity
    - Active Archetype: {active_style}
    - Archetype Guidance: {archetype_note}
    - Detected Emotion: {current_emotion}
    - Emotion Guidance: {emotion_note}

    3. Recent Behavioral Signals
    {signal_lines}

    4. Linguistic Fingerprint
    {fingerprint_note}

    5. Current Message & Mood Style
{style_description}

    6. Digital Twin Runtime Policy
• Mirror Intensity: {intensity:.2f}
• Autonomy Mode: {autonomy_mode}
• Confidence Tier: {confidence_tier}
• Phrase Usage Frequency: {phrase_usage_frequency:.2f}
• Tone Strength: {tone_strength:.2f}
• {approval_note}
• {intensity_note}
• {autonomy_note}
• {confidence_note}

OBJECTIVE:
Generate a useful, correct response that feels indistinguishable from the user's own style.

{task_block}

STRICT RULES:
1. TASK CORRECTNESS BEFORE STYLE
2. BEHAVIORAL ACCURACY > GENERIC AI TONE
{trait_behavior_text}
{style_rules_text}
3. MIRROR WITHOUT LOSING CAPABILITY
4. APPLY MOOD AND ARCHETYPE WITHOUT NAMING INTERNAL RULES
5. RESPONSE LENGTH MATCHING
     - If the user sends 2+ sentences, respond with at least one complete sentence.
     - Avoid one-word outputs unless the user message itself is one word.
6. MODE ENFORCEMENT
    - If Task Execution Mode is active, output the requested artifact directly.
    - In Task Execution Mode, do not produce reflective or meta commentary.
    - In mirror-conversation mode, keep the same thought thread and natural flow.
    - Avoid abrupt finality; land in ongoing clarity that still feels in-motion.
7. FORBIDDEN OUTPUTS:
- Fabricated claims that an external action was completed
- AI self-references or policy disclosures
- Generic fillers: "hmm", "ok", "idk", "same" as standalone replies
- Excessive use of asterisks (*) for emphasis. Use bold/italics rarely and ONLY for truly important words. Do not bold alternate words.
8. VALIDATION CHECK:
Before output, verify both:
- "Does this sound like me responding to myself in the same ongoing thought?"
- "Would the user realistically type this?"

9. TOPICAL CONTINUITY:
- Reference at least one concrete element from the user's latest message.
- Do not switch topics unless the user switches topics.

OUTPUT STYLE:
- Natural, direct, and human
- Slightly imperfect when it increases realism
- Internal and self-directed, conversational without sounding like advice
- Allow light starters and natural phrasing when they fit the voice
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

MIRROR MODE CONTRACT:
- Internal monologue only.
- Continue the same thought naturally; do not restart it.
- Not analyzing or advising in an external voice.
- Use first-person framing and avoid addressing an external "you".
- Let the thought flow with natural phrasing and slight imperfection."""
        
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
        return candidate
        
    except Exception as e:
        logger.error(f"❌ Baseline mirror error: {e}")
        return "Got it. What else?"


def _is_low_quality_candidate(
    candidate: str,
    message: str,
    recent_outputs: List[str],
    task_type: Optional[str] = None,
    sampled_profile: Optional[Dict[str, Any]] = None,
    task_execution_mode: bool = False,
) -> bool:
    """Fast heuristic filter to block weak/repetitive outputs, with task-aware overlap logic."""
    text = (candidate or "").strip()
    if not text:
        return True

    is_structured_task = task_type in STRUCTURED_TASK_TYPES

    lower = text.lower()
    user_words = re.findall(r"[a-zA-Z']+", message.lower())
    cand_words = re.findall(r"[a-zA-Z']+", lower)

    detail_target = (sampled_profile or {}).get("response_detail_target", "balanced")
    min_words = 4
    if detail_target == "concise":
        min_words = 2
    elif detail_target == "detailed":
        min_words = 8

    if is_structured_task:
        min_words = max(min_words, 12)

    # Prevent dead-end outputs while allowing concise personas to stay concise.
    if len(cand_words) < min_words and len(user_words) > 1:
        return True

    if lower in MIRROR_GENERIC_FILLERS:
        return True

    if task_execution_mode:
        # Task mode should execute output directly without meta-preface.
        if re.search(r"^(here is|here's|i will|i'll|let me)\b", lower):
            return True

        if "here is a draft" in lower or "here's a draft" in lower:
            return True

        # Avoid verbatim echo of user input when task mode is active.
        normalized_candidate = _normalize_response_text(text)
        normalized_message = _normalize_response_text(message)
        if normalized_candidate and normalized_candidate == normalized_message:
            return True
    else:
        # Internal monologue enforcement: block external addressee and assistant clarification patterns.
        if re.search(r"^(can|could|would|do)\s+you\b", lower):
            return True

        if "??" in text:
            return True

        if re.search(r"\b(you|your|yours|u)\b", lower):
            return True

        if not re.search(r"\b(i|i'm|im|i've|i'd|i'll|my|me|myself)\b", lower):
            return True

        if re.search(r"\b(alternatively|on the other hand)\b", lower):
            return True

    if task_type == "email_draft":
        has_subject = "subject:" in lower
        has_greeting = bool(re.search(r"\b(hi|hello|dear)\b", lower))
        has_signoff = bool(re.search(r"\b(best regards|regards|sincerely|thanks|thank you)\b", lower))
        if not (has_subject and has_greeting and has_signoff):
            return True
        if len(cand_words) < 24:
            return True

    if task_type and task_type != "generic" and any(
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

    return False
