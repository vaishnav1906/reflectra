"""API routes for personality reflection system."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services.trait_extraction_service import extract_traits
from app.services.persona_update_service import update_traits
from app.services.snapshot_service import generate_persona_snapshot
from app.services.mirror_engine import invalidate_snapshot_cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/persona", tags=["persona"])


class ResetPersonaRequest(BaseModel):
    user_id: str

@router.post("/reset")
async def reset_persona(
    request: ResetPersonaRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        user_uuid = UUID(request.user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id format")

    from app.db.models import PersonaSnapshot, UserPersonaMetric, BehavioralInsight
    from sqlalchemy import delete
    
    # Delete persona data
    await db.execute(delete(PersonaSnapshot).where(PersonaSnapshot.user_id == user_uuid))
    await db.execute(delete(UserPersonaMetric).where(UserPersonaMetric.user_id == user_uuid))
    await db.execute(delete(BehavioralInsight).where(BehavioralInsight.user_id == user_uuid))
    await db.commit()
    
    # Initialize fresh
    await generate_persona_snapshot(db, user_uuid)
    invalidate_snapshot_cache(user_uuid)
    
    return {"status": "persona_reset_success"}


class ReflectionRequest(BaseModel):
    user_id: str
    message: str


class ReflectionResponse(BaseModel):
    traits: dict
    stability: float
    summary: str


@router.post("/reflection", response_model=ReflectionResponse)
async def process_reflection(
    request: ReflectionRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Process a reflection message to update personality traits.
    
    Flow:
    1. Extract traits from message
    2. Update trait metrics
    3. Generate updated snapshot
    4. Return summary
    """
    try:
        user_id = UUID(request.user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id format")
    
    logger.info(f"📝 Processing reflection for user {user_id}")
    
    # Step 1: Extract traits
    extracted_traits = await extract_traits(request.message)
    logger.info(f"🔍 Extracted {len(extracted_traits)} traits")
    
    # Step 2: Update traits
    update_result = await update_traits(db, user_id, extracted_traits)
    
    # Step 3: Generate snapshot
    snapshot = await generate_persona_snapshot(db, user_id)
    
    # Invalidate cache since we have a new snapshot
    invalidate_snapshot_cache(user_id)
    
    logger.info(f"✅ Reflection processing complete for user {user_id}")
    
    # Extract traits from the snapshot's persona vector
    traits = snapshot.persona_vector.get("behavioral_profile", {})
    
    return ReflectionResponse(
        traits=traits,
        stability=round(snapshot.stability_index, 2),
        summary=snapshot.summary_text
    )


@router.get("/profile/{user_id}")
async def get_user_profile(
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get the latest personality profile for a user."""
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id format")
    
    from app.repository.persona_repository import PersonaRepository
    from app.db.models import ScheduleContext
    from sqlalchemy import select
    
    snapshot = await PersonaRepository.get_latest_snapshot(db, user_uuid)
    
    if not snapshot:
        raise HTTPException(status_code=404, detail="No personality profile found")
    
    traits = snapshot.persona_vector.get("behavioral_profile", {})
    
    # Apply dynamic context injection based on schedule config
    sched_result = await db.execute(select(ScheduleContext).where(ScheduleContext.user_id == user_uuid))
    context_record = sched_result.scalar_one_or_none()
    
    if context_record and traits:
        stress = context_record.stress_level
        
        # Deep copy traits so we don't accidentally mutate dict elements improperly
        import copy
        traits = copy.deepcopy(traits)
        
        if stress > 0.7:
            # High stress
            if "reflection_depth" in traits:
                traits["reflection_depth"]["score"] = max(0.0, traits["reflection_depth"]["score"] - 0.2)
            if "emotional_expressiveness" in traits:
                # Assuming emotional_support maps to expressiveness
                traits["emotional_expressiveness"]["score"] = min(1.0, traits["emotional_expressiveness"]["score"] + 0.3)
            if "decision_framing" in traits:
                traits["decision_framing"]["score"] = max(0.0, traits["decision_framing"]["score"] - 0.15) # hesitant under stress
        elif stress < 0.2:
            # Low stress
            if "reflection_depth" in traits:
                traits["reflection_depth"]["score"] = min(1.0, traits["reflection_depth"]["score"] + 0.1)
    
    return {
        "traits": traits,
        "stability": round(snapshot.stability_index, 2),
        "summary": snapshot.summary_text
    }


@router.get("/metrics/{user_id}")
async def get_user_metrics(
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get all trait metrics for a user."""
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id format")
    
    from app.repository.persona_repository import PersonaRepository
    
    metrics = await PersonaRepository.get_all_metrics(db, user_uuid)
    
    return {
        "user_id": user_id,
        "metrics": [
            {
                "trait_name": m.trait_name,
                "score": round(m.score, 3),
                "confidence": round(m.confidence, 3),
                "evidence_count": m.evidence_count,
                "last_signal": round(m.last_signal, 3) if m.last_signal else None,
                "last_updated": m.last_updated.isoformat(),
            }
            for m in metrics
        ],
    }
