"""Persona update service with gradual weighted moving average."""

import logging
import statistics
from typing import Dict, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repository.persona_repository import PersonaRepository
from app.constants import (
    ALIGNMENT_DISTANCE,
    CONFLICT_DISTANCE,
    CONFIDENCE_INCREASE_RATE,
    CONFIDENCE_DECREASE_RATE,
    SCORE_INERTIA,
    MIN_CONFIDENCE,
    MAX_CONFIDENCE,
    MAX_STRENGTH_PER_MESSAGE,
    EVIDENCE_COUNT_FOR_DRIFT_CHECK,
    MIN_EVIDENCE_FOR_RETENTION,
    LOW_CONFIDENCE_THRESHOLD,
    EXTREME_SCORE_MIN,
    EXTREME_SCORE_MAX,
    DRIFT_SMOOTHING_FACTOR,
)

logger = logging.getLogger(__name__)


def compute_trait_update(
    old_score: float,
    old_confidence: float,
    signal: float,
    strength: float,
) -> tuple[float, float]:
    """Pure trait-update rule. Returns (new_score, new_confidence).

    Score: an exponential moving average whose step size is the nudge strength,
    damped by existing confidence. A single message can move a trait at most
    `strength` (<= 0.2) of the way toward its signal, never most of the way.

    Confidence: grows when the signal agrees with the current score, shrinks
    when it clearly contradicts it, and is unchanged for in-between evidence.
    Both directions saturate, so confidence approaches its bounds smoothly.
    """
    strength = max(0.0, min(MAX_STRENGTH_PER_MESSAGE, float(strength)))
    signal = max(0.0, min(1.0, float(signal)))
    old_confidence = max(MIN_CONFIDENCE, min(MAX_CONFIDENCE, float(old_confidence)))

    alpha = strength * (1.0 - SCORE_INERTIA * old_confidence)
    new_score = max(0.0, min(1.0, old_score + alpha * (signal - old_score)))

    distance = abs(signal - old_score)
    if distance <= ALIGNMENT_DISTANCE:
        new_confidence = old_confidence + CONFIDENCE_INCREASE_RATE * strength * (1.0 - old_confidence)
    elif distance >= CONFLICT_DISTANCE:
        new_confidence = old_confidence - CONFIDENCE_DECREASE_RATE * strength * old_confidence
    else:
        new_confidence = old_confidence

    new_confidence = max(MIN_CONFIDENCE, min(MAX_CONFIDENCE, new_confidence))
    return new_score, new_confidence


async def update_traits(
    db: AsyncSession, user_id: UUID, extracted_traits: List[Dict]
) -> Dict[str, float]:
    """
    Update user's personality traits gradually (see compute_trait_update).

    - Each nudge moves a trait at most `strength` (<= 0.2) toward its signal.
    - Confidence grows with consistent evidence and shrinks with contradictions.
    
    Args:
        db: Database session
        user_id: User UUID
        extracted_traits: List of dicts with keys: name, signal, strength
        
    Returns:
        Dict with keys: stability_index, traits_updated
    """
    if not extracted_traits:
        logger.info(f"ℹ️ No traits extracted for user {user_id}")
        return {"stability_index": 0.5, "traits_updated": 0}
    
    # Initialize missing traits first
    await PersonaRepository.initialize_missing_traits(db, user_id)
    evidence_before = await PersonaRepository.get_total_evidence_count(db, user_id)
    
    traits_updated = 0
    
    for trait_data in extracted_traits:
        trait_name = trait_data["name"]
        signal = trait_data["signal"]
        strength = trait_data["strength"]
        
        # Fetch existing metric
        metric = await PersonaRepository.get_metric(db, user_id, trait_name)
        
        if not metric:
            # Create new metric (shouldn't happen after initialization, but handle it)
            logger.warning(f"⚠️ Creating missing trait {trait_name} for user {user_id}")
            metric = await PersonaRepository.create_metric(
                db, user_id, trait_name
            )
        
        old_score = metric.score
        old_confidence = metric.confidence
        new_score, new_confidence = compute_trait_update(old_score, old_confidence, signal, strength)

        # Update metric
        await PersonaRepository.update_metric(
            db, metric, new_score, new_confidence, signal
        )
        
        traits_updated += 1
        logger.info(
            f"✅ Updated {trait_name}: "
            f"score {old_score:.3f}→{new_score:.3f} "
            f"(Δ{new_score - old_score:+.3f}), "
            f"confidence {old_confidence:.3f}→{new_confidence:.3f}"
        )
    
    await db.commit()
    
    # Compute stability index
    all_metrics = await PersonaRepository.get_all_metrics(db, user_id)
    if all_metrics:
        avg_confidence = statistics.mean([m.confidence for m in all_metrics])
        logger.info(f"📊 Stability index: {avg_confidence:.3f}")
    else:
        avg_confidence = 0.5
    
    # Check if drift prevention is needed
    total_evidence = await PersonaRepository.get_total_evidence_count(db, user_id)
    # Evidence grows by 1-4 per message, so check whether a multiple of the
    # interval was crossed rather than hit exactly (the old `% == 0` check
    # silently skipped most drift checks).
    if total_evidence // EVIDENCE_COUNT_FOR_DRIFT_CHECK > evidence_before // EVIDENCE_COUNT_FOR_DRIFT_CHECK:
        logger.info(f"🔄 Running drift prevention (evidence count: {total_evidence})")
        await apply_drift_prevention(db, user_id)
    
    return {
        "stability_index": avg_confidence,
        "traits_updated": traits_updated,
    }


async def apply_drift_prevention(db: AsyncSession, user_id: UUID) -> None:
    """
    Apply drift prevention measures to prevent extreme trait locking.
    
    Steps:
    1. Remove traits with low confidence and insufficient evidence
    2. Apply drift smoothing to prevent locking at 0 or 1
    3. Clamp extreme scores
    """
    # Remove low-confidence, low-evidence traits
    removed_count = await PersonaRepository.remove_low_confidence_traits(
        db,
        user_id,
        min_evidence=MIN_EVIDENCE_FOR_RETENTION,
        min_confidence=LOW_CONFIDENCE_THRESHOLD,
    )
    
    if removed_count > 0:
        logger.info(f"🗑️ Removed {removed_count} low-confidence traits")
    
    # Apply drift smoothing and clamp extreme scores
    all_metrics = await PersonaRepository.get_all_metrics(db, user_id)
    smoothed_count = 0
    
    for metric in all_metrics:
        old_score = metric.score
        
        # ============================================================
        # DRIFT SMOOTHING
        # ============================================================
        # Prevents traits from locking at extreme values (0 or 1)
        # Formula: score = score * 0.98 + 0.01
        # Effect: Gently pulls extreme values toward center
        # - If score = 1.0 → 0.99
        # - If score = 0.0 → 0.01
        # - If score = 0.5 → 0.5 (minimal effect at center)
        # ============================================================
        
        # Apply smoothing if score is very extreme
        if metric.score < 0.1 or metric.score > 0.9:
            metric.score = metric.score * DRIFT_SMOOTHING_FACTOR + (1 - DRIFT_SMOOTHING_FACTOR) * 0.5
            if abs(metric.score - old_score) > 0.001:
                smoothed_count += 1
                logger.debug(f"🌊 Drift smoothing {metric.trait_name}: {old_score:.3f} → {metric.score:.3f}")
        
        # Clamp to absolute extremes
        if metric.score < EXTREME_SCORE_MIN:
            logger.info(f"📌 Clamping {metric.trait_name} score from {metric.score:.3f} to {EXTREME_SCORE_MIN}")
            metric.score = EXTREME_SCORE_MIN
        elif metric.score > EXTREME_SCORE_MAX:
            logger.info(f"📌 Clamping {metric.trait_name} score from {metric.score:.3f} to {EXTREME_SCORE_MAX}")
            metric.score = EXTREME_SCORE_MAX
    
    await db.commit()
    
    if smoothed_count > 0:
        logger.info(f"🌊 Applied drift smoothing to {smoothed_count} traits")
    
    logger.info("✅ Drift prevention complete")
