"""Snapshot generation service for persona profiles."""

import logging
import statistics
from typing import Dict, List, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repository.persona_repository import PersonaRepository
from app.db.models import PersonaSnapshot
from app.constants import (
    TRAIT_GROUPS,
    STABILITY_THRESHOLD_UNSTABLE,
    STABILITY_THRESHOLD_STABLE,
)

logger = logging.getLogger(__name__)


async def generate_persona_snapshot(
    db: AsyncSession, user_id: UUID
) -> PersonaSnapshot:
    """
    Generate and store a persona snapshot.
    
    Args:
        db: Database session
        user_id: User UUID
        
    Returns:
        PersonaSnapshot object
    """
    logger.info(f"📸 Generating persona snapshot for user {user_id}")
    
    # Fetch all traits
    metrics = await PersonaRepository.get_all_metrics(db, user_id)
    
    if not metrics:
        logger.warning(f"⚠️ No metrics found for user {user_id}, creating default snapshot")
        return await PersonaRepository.create_snapshot(
            db=db,
            user_id=user_id,
            persona_vector={},
            stability_index=0.1,
            summary_text="Insufficient data to generate personality profile.",
        )
    
    # Convert metrics to dict
    metrics_dict = {m.trait_name: m for m in metrics}
    
    # Build grouped persona vector
    persona_vector = {}
    for group_name, trait_names in TRAIT_GROUPS.items():
        group_data = {}
        for trait_name in trait_names:
            if trait_name in metrics_dict:
                metric = metrics_dict[trait_name]
                group_data[trait_name] = {
                    "score": round(metric.score, 3),
                    "confidence": round(metric.confidence, 3),
                }
        persona_vector[group_name] = group_data
    
    # Compute stability index
    confidences = [m.confidence for m in metrics]
    stability_index = statistics.mean(confidences) if confidences else 0.1
    
    # Generate summary text
    summary_text = generate_summary_text(metrics, stability_index)
    
    # Create snapshot
    snapshot = await PersonaRepository.create_snapshot(
        db=db,
        user_id=user_id,
        persona_vector=persona_vector,
        stability_index=round(stability_index, 3),
        summary_text=summary_text,
    )
    
    logger.info(f"✅ Snapshot created: stability={stability_index:.3f}")
    return snapshot


def generate_summary_text(metrics: List, stability_index: float) -> str:
    """
    Generate deterministic summary text from metrics.
    
    Args:
        metrics: List of UserPersonaMetric objects
        stability_index: Overall stability index
        
    Returns:
        Descriptive summary paragraph
    """
    if not metrics:
        return "Insufficient data to generate personality profile."
    
    # Determine stability level
    if stability_index < STABILITY_THRESHOLD_UNSTABLE:
        stability_desc = "emerging"
    elif stability_index > STABILITY_THRESHOLD_STABLE:
        stability_desc = "well-established"
    else:
        stability_desc = "developing"
    
    # Find top 3 highest scoring traits
    sorted_by_score = sorted(metrics, key=lambda m: m.score, reverse=True)
    top_traits = sorted_by_score[:3]
    
    # Find lowest confidence traits (unstable areas)
    sorted_by_confidence = sorted(metrics, key=lambda m: m.confidence)
    low_confidence_traits = [
        m for m in sorted_by_confidence[:3] 
        if m.confidence < STABILITY_THRESHOLD_UNSTABLE
    ]
    
    # Build summary
    parts = []
    
    # Overall stability
    parts.append(f"This is a {stability_desc} personality profile.")
    
    # Top traits
    if top_traits:
        trait_descriptions = []
        for metric in top_traits:
            level = get_trait_level_description(metric.score)
            trait_label = format_trait_name(metric.trait_name)
            trait_descriptions.append(f"{level} {trait_label}")
        
        traits_text = ", ".join(trait_descriptions[:-1])
        if len(trait_descriptions) > 1:
            traits_text += f", and {trait_descriptions[-1]}"
        else:
            traits_text = trait_descriptions[0]
        
        parts.append(f"Key characteristics include {traits_text}.")
    
    # Low confidence areas
    if low_confidence_traits:
        unstable_names = [format_trait_name(m.trait_name) for m in low_confidence_traits]
        if len(unstable_names) == 1:
            parts.append(f"The profile shows variability in {unstable_names[0]}.")
        else:
            unstable_text = ", ".join(unstable_names[:-1]) + f", and {unstable_names[-1]}"
            parts.append(f"The profile shows variability in {unstable_text}.")
    
    return " ".join(parts)


def get_trait_level_description(score: float) -> str:
    """Convert score to descriptive level."""
    if score < 0.25:
        return "very low"
    elif score < 0.4:
        return "low"
    elif score < 0.6:
        return "moderate"
    elif score < 0.75:
        return "high"
    else:
        return "very high"


def format_trait_name(trait_name: str) -> str:
    """Convert snake_case trait name to readable format."""
    return trait_name.replace("_", " ")
