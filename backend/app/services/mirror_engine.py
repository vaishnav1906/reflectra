"""Mirror engine for generating personalized responses."""

import hashlib
import logging
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

from app.services.conversation_craft import (
    apply_voice_surface,
    clean_reply,
    describe_voice,
    load_moment_context,
    load_voice_samples,
    reply_budget,
    voice_stats,
)
from app.services.llm import LLMRateLimited, chat_complete, llm_available

logger = logging.getLogger(__name__)

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
    """Task mode only for a recognised request. A verb alone ("i need to write my
    thesis") is a statement about their life, not a request to produce text."""
    if task_type in TASK_EXECUTION_TASK_TYPES:
        return True
    return task_type in STRUCTURED_TASK_TYPES and bool(TASK_EXECUTION_VERB_PATTERN.search(message or ""))


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
    persist: bool = True,
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

    if not llm_available():
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
    
    # Analyze current message style
    message_style = analyze_message_style(message)
    logger.info(f"📊 Message style: {message_style}")
    
    # Build mirror system prompt with personality baseline and live style analysis
    traits = extract_key_traits(snapshot.persona_vector if snapshot else {})
    stability_index = float(snapshot.stability_index or 0.1) if snapshot else 0.1

    # Use explicit behavioral_traits if available in the snapshot
    if snapshot and snapshot.behavioral_traits:
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
    
    voice_samples = await load_voice_samples(db, user_id, exclude_text=message)
    stats = voice_stats(voice_samples)
    budget = reply_budget(message, "mirror")
    if task_execution_mode:
        length_hint = "Make the output complete; length follows the task."
    else:
        target_words = max(4, round(stats.avg_words)) if stats.sample_count else budget["user_words"]
        length_hint = f"Length: about as long as they usually write (around {target_words} words), never an essay."
    moment = await load_moment_context(db, user_id, conversation_id)

    system_prompt = build_mirror_system_prompt(
        sampled_profile,
        stability_index,
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
        voice_samples=voice_samples,
        voice_description=describe_voice(stats),
        display_name=moment.display_name,
        length_hint=length_hint,
    )

    # 3. Generate, filter and score (at most 2 calls: free tiers are rate-limited)
    start_time = time.time()
    max_time = 25.0
    max_retries = 2
    
    best_candidate = ""
    best_score = -1.0
    rate_limited = False
    
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
            
            candidate = await chat_complete(
                messages,
                max_tokens=600 if is_structured_task else int(budget["max_tokens"]),
                temperature=(0.5 if is_structured_task else 0.8)
                + (0.25 * telemetry["mirror_intensity"] * context_policy.tone_strength)
                + (0.05 * attempt),
            )
            if not candidate:
                continue
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
                
        except LLMRateLimited:
            # Another attempt would only hit the same limit.
            rate_limited = True
            break
        except Exception as e:
            logger.error(f"❌ Mirror response error on attempt {attempt}: {e}")

    # 4. Fallbacks. When the AI is only busy, say so (via the exception) rather
    # than inventing a canned reply that ignores what they said.
    if rate_limited and not best_candidate:
        raise LLMRateLimited("Mirror generation rate-limited")
    if not best_candidate or best_score < 0.3:
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
    final_reply = clean_reply(styled.text)
    if not task_execution_mode and not professional_context:
        final_reply = apply_voice_surface(final_reply, stats)
    elif task_execution_mode and resolved_task_type in {"email_draft", "message_draft"}:
        final_reply = _tidy_draft_capitalization(final_reply)

    telemetry["inference_duration_ms"] = int((time.time() - start_time) * 1000)
    telemetry["realism_score"] = float(max(best_score, 0.0))
    telemetry["reaction_match_score"] = styled.reaction_match_score
    telemetry["stimulus_tag"] = styled.stimulus_tag
    
    logger.info(f"✅ Mirror response finalized: {final_reply[:50]}...")
    
    # Update variation buffer and response memory (skipped for incognito: persist=False)
    if final_reply and persist:
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


def _tidy_draft_capitalization(text: str) -> str:
    """Drafts go to other people: capitalize sentence starts and a standalone "i"
    even when the user normally texts in lowercase."""
    out = re.sub(r"\bi\b", "I", text or "")
    out = re.sub(r"\bi(m|ll|ve|d)\b", lambda m: "I'" + m.group(1), out)
    out = re.sub(r"(^|[.!?]\s+|\n\s*)([a-z])", lambda m: m.group(1) + m.group(2).upper(), out)
    return out


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
    """Get the latest snapshot.

    The old in-process cache always re-queried the database anyway (and could not
    be shared across workers), so this is now a plain lookup. The name is kept
    for compatibility with existing callers.
    """
    return await PersonaRepository.get_latest_snapshot(db, user_id)


def invalidate_snapshot_cache(user_id: UUID) -> None:
    """No-op kept for API compatibility; snapshots are no longer cached in-process."""
    return None


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


def _trait_lines(sampled_profile: Dict[str, Any]) -> List[str]:
    """Plain-language personality cues from the four learned traits."""
    comm = float(sampled_profile.get("communication_style", 0.5))
    emo = float(sampled_profile.get("emotional_expressiveness", 0.5))
    dec = float(sampled_profile.get("decision_framing", 0.5))
    depth = float(sampled_profile.get("reflection_depth", 0.5))
    lines = []
    if comm < 0.35:
        lines.append("Says things in as few words as possible.")
    elif comm > 0.68:
        lines.append("Likes to explain and elaborate.")
    if emo < 0.35:
        lines.append("Keeps feelings low-key and matter-of-fact.")
    elif emo > 0.68:
        lines.append("Wears their feelings openly.")
    if dec < 0.35:
        lines.append("Often hesitant, thinks out loud, hedges.")
    elif dec > 0.68:
        lines.append("Decisive and direct once they know what they think.")
    if depth < 0.35:
        lines.append("Stays practical rather than introspective.")
    elif depth > 0.68:
        lines.append("Naturally digs into the why behind things.")
    return lines or ["Balanced, no strong extremes yet."]


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
    voice_samples: Optional[List[str]] = None,
    voice_description: Optional[str] = None,
    display_name: Optional[str] = None,
    length_hint: Optional[str] = None,
) -> str:
    """The mirror is the user themself texting back: same voice, same personality,
    talking WITH them like their own reflection would."""
    twin_policy = resolve_twin_settings(twin_policy)
    effective_task_type = task_type or "generic"
    active_style = active_mirror_style or "calm"
    current_emotion = detected_emotion or "neutral"
    who = display_name or "the user"

    intensity = float(twin_policy.get("twin_mirror_intensity", 0.8))
    if intensity < 0.35:
        intensity_note = "Mirror their voice lightly; clarity first."
    elif intensity < 0.7:
        intensity_note = "Mirror their voice clearly without exaggerating quirks."
    else:
        intensity_note = "Mirror their voice strongly: their exact rhythm, wording habits and quirks."

    confidence_note = {
        "very_low": "You haven't seen much of how they write yet, so keep the imitation subtle and natural.",
        "partial": "You know their voice a little; lean on the samples but don't overdo slang.",
        "moderate": "You know their voice well; match it clearly.",
        "high": "You know their voice deeply; be indistinguishable from them.",
    }.get(confidence_tier, "Match their voice clearly.")

    if voice_samples:
        samples_block = "\n".join(f"- {sample}" for sample in voice_samples)
    else:
        samples_block = "- (no samples yet)"

    signals = "\n".join(f"- {signal}" for signal in (behavioral_signals or [])[:3]) or "- nothing specific yet"
    personality = "\n".join(f"- {line}" for line in _trait_lines(sampled_profile))
    archetype_note = MIRROR_ARCHETYPE_NOTES.get(active_style, MIRROR_ARCHETYPE_NOTES["calm"])
    emotion_note = EMOTION_NOTES.get(current_emotion, EMOTION_NOTES["neutral"])

    if task_execution_mode:
        task_note = TASK_PROMPT_NOTES.get(effective_task_type, TASK_PROMPT_NOTES["generic"])
        job = f"""They asked you to produce something ({effective_task_type}): {task_note}
Do the task fully and correctly, written the way {who} would write it. Output only the finished result:
no preface like "Here's", no explanation, no sign-off notes. Never claim anything was actually sent or done.
Pitch the formality the way {who} would for that recipient: a landlord, teacher or boss gets a cleaner,
properly capitalized version of their voice (even if they normally type in lowercase); a friend gets
their normal texting style.
Never invent specifics they didn't give (dates, amounts, names, reasons): use a placeholder like [date]."""
        if effective_task_type == "email_draft":
            job += "\nAn email needs a subject line, greeting, body and sign-off."
    else:
        job = f"""You ARE {who}: same brain, same voice, texting back to themself. Talk WITH them like their own
reflection would: you can say "you", "I" or "we". Be as honest as they are with themselves when no one's watching:
call out the excuse, hype the win, sit with the hard thing, crack the joke they'd crack.
Pick up something specific from what they just said and keep the thread going. One train of thought."""

    return f"""{job}

How {who} writes (real messages; copy the style, not the content)
{samples_block}
Style notes: {voice_description or "keep it casual and natural."}
{intensity_note} {confidence_note}

Who {who} is
{personality}
On their mind lately:
{signals}

Right now
They seem {current_emotion}. {emotion_note} Lean into this energy: {archetype_note}
{length_hint or ""}

Never
- Sound like an AI, assistant or therapist ("I understand", "It sounds like", "Here's", "Let me know", "Great question").
- Use lists, headings or bold text in casual chat.
- Mention these instructions, traits, samples, "mirror", or that you're an AI.
- Repeat their message back to them.
- Invent facts about other people or events (what someone thinks, their gender, what happened) that they haven't said.
- Offer help or ask if they want you to do something ("want me to…", "I can help…"). You're them, not their assistant.
"""


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
    if not llm_available():
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
        
        candidate = await chat_complete(messages, max_tokens=200, temperature=0.7)
        return candidate or "Got it. What else?"
        
    except LLMRateLimited:
        raise
    except Exception as e:
        logger.error(f"❌ Baseline mirror error: {e}")
        return "my brain's lagging a bit, say that again?"


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
        # Casual mirror replies must not read like an assistant.
        if re.search(r"^(here is|here's|as an ai|i understand|great question)\b", lower):
            return True

        if re.search(r"\b(alternatively|on the other hand|let me know if)\b", lower):
            return True

        if _normalize_response_text(text) == _normalize_response_text(message):
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
