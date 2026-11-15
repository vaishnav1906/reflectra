"""API routes for mirror response system."""

from typing import Optional
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, ensure_self
from app.db.database import get_db
from app.db.models import UserSettings
from app.services.mirror_engine import generate_mirror_response
from app.services.message_signals import derive_fallback_traits
from app.services.mirror_engine import invalidate_snapshot_cache
from app.services.persona_update_service import update_traits
from app.services.snapshot_service import generate_persona_snapshot
from app.services.trait_extraction_service import extract_traits
from app.services.twin_policy import resolve_twin_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mirror", tags=["mirror"])


class MirrorRequest(BaseModel):
    user_id: Optional[str] = None  # ignored: identity comes from the access token
    message: str


class MirrorResponse(BaseModel):
    success: bool
    response: str
    mirroring_active: bool
    policy_applied: dict


_derive_fallback_traits = derive_fallback_traits


@router.post("/chat", response_model=MirrorResponse)
async def mirror_chat(
    request: MirrorRequest,
    current_user: CurrentUser,
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
        user_id = ensure_self(request.user_id, current_user)
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

    logger.info("🔄 Updating persona from mirror chat message")
    try:
        extracted_traits = await extract_traits(request.message)
        if not extracted_traits:
            extracted_traits = _derive_fallback_traits(request.message)
            logger.info("🔁 Using fallback trait extraction (mirror endpoint): %s traits", len(extracted_traits))
        else:
            logger.info("🔍 Extracted %s traits (mirror endpoint)", len(extracted_traits))

        if extracted_traits:
            await update_traits(db, user_id, extracted_traits)
            await generate_persona_snapshot(db, user_id)
            invalidate_snapshot_cache(user_id)
            await db.commit()
            logger.info("✅ Persona updated from /mirror/chat message")
    except Exception as update_err:
        logger.warning("⚠️ Mirror endpoint persona update failed: %s", update_err)
        await db.rollback()
    
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
