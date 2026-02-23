"""Persona update service with gradual weighted moving average."""

import logging
import statistics
from typing import Dict, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repository.persona_repository import PersonaRepository
from app.constants import (
    CONFIDENCE_INCREASE_RATE,
    CONFIDENCE_DECREASE_RATE,
    MIN_CONFIDENCE,
    MAX_CONFIDENCE,
    EVIDENCE_COUNT_FOR_DRIFT_CHECK,
    MIN_EVIDENCE_FOR_RETENTION,
    LOW_CONFIDENCE_THRESHOLD,
    EXTREME_SCORE_MIN,
    EXTREME_SCORE_MAX,
    DRIFT_SMOOTHING_FACTOR,
)

logger = logging.getLogger(__name__)


async def update_traits(
    db: AsyncSession, user_id: UUID, extracted_traits: List[Dict]
) -> Dict[str, float]:
    """
    Update user's personality traits using gradual weighted moving average.
    
    Implements the algorithm:
    - new_score = (old_score * old_confidence + signal * strength) / (old_confidence + strength)
    - Confidence increases if signal aligns with trend, decreases if conflicting
    - Ensures slow convergence and no abrupt changes
    
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
        
        # ============================================================
        # GRADUAL WEIGHTED MOVING AVERAGE ALGORITHM
        # ============================================================
        # Formula: new_score = (old_score * old_confidence + signal * strength) / (old_confidence + strength)
        # This ensures:
        # - Higher confidence scores resist change more
        # - Stronger signals have more influence
        # - No single message can drastically shift the trait
        # ============================================================
        
        numerator = (old_score * old_confidence) + (signal * strength)
        denominator = old_confidence + strength
        new_score = numerator / denominator if denominator > 0 else old_score
        
        # Clamp score to [0, 1]
        new_score = max(0.0, min(1.0, new_score))
        
        # ============================================================
        # DIRECTIONAL CONFIDENCE LOGIC
        # ============================================================
        # If signal direction aligns with current score:
        #   → Increase confidence (reinforcing pattern)
        # If signal direction conflicts with current score:
        #   → Decrease confidence (uncertain/changing pattern)
        # ============================================================
        
        # Check alignment: does signal push in same direction as current score?
        signal_delta = signal - old_score
        
        if abs(signal_delta) < 0.05:
            # Signal very close to current score - slight confidence boost
            new_confidence = min(MAX_CONFIDENCE, old_confidence + CONFIDENCE_INCREASE_RATE * strength * 0.5)
            logger.debug(f"📊 {trait_name}: Signal aligned (neutral)")
        elif (signal > 0.5 and old_score > 0.5) or (signal < 0.5 and old_score < 0.5):
            # Signal and score on same side of neutral - increase confidence
            new_confidence = min(MAX_CONFIDENCE, old_confidence + CONFIDENCE_INCREASE_RATE * strength)
            logger.debug(f"📈 {trait_name}: Signal aligned (same direction)")
        else:
            # Signal pulls in opposite direction - decrease confidence
            new_confidence = max(MIN_CONFIDENCE, old_confidence - CONFIDENCE_DECREASE_RATE * strength)
            logger.debug(f"📉 {trait_name}: Signal conflicting (different direction)")
        
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
    if total_evidence > 0 and total_evidence % EVIDENCE_COUNT_FOR_DRIFT_CHECK == 0:
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
