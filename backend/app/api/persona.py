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


class ReflectionRequest(BaseModel):
    user_id: str
    message: str


class ReflectionResponse(BaseModel):
    success: bool
    traits_extracted: int
    traits_updated: int
    stability_index: float
    snapshot_id: str
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
    
    return ReflectionResponse(
        success=True,
        traits_extracted=len(extracted_traits),
        traits_updated=update_result["traits_updated"],
        stability_index=round(update_result["stability_index"], 3),
        snapshot_id=str(snapshot.id),
        summary=snapshot.summary_text,
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
    
    snapshot = await PersonaRepository.get_latest_snapshot(db, user_uuid)
    
    if not snapshot:
        raise HTTPException(status_code=404, detail="No personality profile found")
    
    return {
        "snapshot_id": str(snapshot.id),
        "user_id": str(snapshot.user_id),
        "persona_vector": snapshot.persona_vector,
        "stability_index": snapshot.stability_index,
        "summary": snapshot.summary_text,
        "created_at": snapshot.created_at.isoformat(),
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
