"""API routes for mirror response system."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import UserSettings
from app.services.mirror_engine import generate_mirror_response
from app.services.twin_policy import resolve_twin_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mirror", tags=["mirror"])


class MirrorRequest(BaseModel):
    user_id: str
    message: str


class MirrorResponse(BaseModel):
    success: bool
    response: str
    mirroring_active: bool
    policy_applied: dict


@router.post("/chat", response_model=MirrorResponse)
async def mirror_chat(
    request: MirrorRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate a mirror response based on user's personality profile.
    
    Flow:
    1. Fetch latest persona snapshot
    2. Generate response using mirror engine
    3. Return mirrored response
    """
    try:
        user_id = UUID(request.user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id format")
    
    logger.info(f"🪞 Mirror chat request for user {user_id}")

    settings_result = await db.execute(select(UserSettings).where(UserSettings.user_id == user_id))
    settings_record = settings_result.scalar_one_or_none()
    twin_policy = resolve_twin_settings(settings_record)
    
    # Generate mirror response
    response_tuple = await generate_mirror_response(
        db,
        user_id,
        request.message,
        twin_policy=twin_policy,
    )
    response_text = response_tuple[0]
    
    # Check if we have a snapshot to determine if mirroring is active
    from app.repository.persona_repository import PersonaRepository
    snapshot = await PersonaRepository.get_latest_snapshot(db, user_id)
    mirroring_active = bool(snapshot is not None and twin_policy.get("digital_twin_enabled") and twin_policy.get("persona_mirroring"))
    
    logger.info(f"✅ Mirror response generated (active={mirroring_active})")
    
    return MirrorResponse(
        success=True,
        response=response_text,
        mirroring_active=mirroring_active,
        policy_applied=twin_policy,
    )
