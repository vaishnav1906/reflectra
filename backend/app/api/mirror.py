"""API routes for mirror response system."""

import logging
import re
from typing import Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import UserSettings
from app.services.mirror_engine import generate_mirror_response
from app.services.mirror_engine import invalidate_snapshot_cache
from app.services.persona_update_service import update_traits
from app.services.snapshot_service import generate_persona_snapshot
from app.services.trait_extraction_service import extract_traits
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


def _derive_fallback_traits(user_text: str) -> List[Dict[str, float]]:
    """Deterministic fallback extraction used when mirror trait extraction returns empty."""
    words = re.findall(r"[A-Za-z']+", user_text.lower())
    lower_text = user_text.lower()
    word_count = len(words)

    traits: List[Dict[str, float]] = []

    communication_signal = max(0.0, min(1.0, (word_count - 4) / 24.0))
    traits.append(
        {
            "name": "communication_style",
            "signal": communication_signal,
            "strength": min(0.16, 0.07 + (min(word_count, 40) / 500.0)),
        }
    )

    emotional_keywords = {
        "feel",
        "felt",
        "sad",
        "happy",
        "anxious",
        "worried",
        "stressed",
        "overwhelmed",
        "excited",
        "frustrated",
        "angry",
    }
    emotion_hits = sum(1 for word in words if word in emotional_keywords)
    exclamations = user_text.count("!")
    if emotion_hits > 0 or exclamations > 0:
        express_signal = max(0.0, min(1.0, 0.25 + (emotion_hits * 0.15) + (exclamations * 0.08)))
        traits.append(
            {
                "name": "emotional_expressiveness",
                "signal": express_signal,
                "strength": min(0.18, 0.08 + (emotion_hits * 0.02) + (exclamations * 0.01)),
            }
        )

    hedge_phrases = ["maybe", "perhaps", "i think", "kind of", "sort of", "not sure"]
    decisive_words = {"definitely", "certain", "will", "must", "clear", "decided"}
    hedge_hits = sum(1 for phrase in hedge_phrases if phrase in lower_text)
    decisive_hits = sum(1 for word in words if word in decisive_words)
    if hedge_hits > 0 or decisive_hits > 0:
        decision_signal = max(0.0, min(1.0, 0.5 + (decisive_hits * 0.12) - (hedge_hits * 0.14)))
        traits.append(
            {
                "name": "decision_framing",
                "signal": decision_signal,
                "strength": min(0.17, 0.08 + ((hedge_hits + decisive_hits) * 0.02)),
            }
        )

    depth_markers = {
        "why",
        "because",
        "realize",
        "pattern",
        "meaning",
        "reflect",
        "thinking",
        "understand",
    }
    depth_hits = sum(1 for word in words if word in depth_markers)
    if depth_hits > 0:
        depth_signal = max(0.0, min(1.0, 0.2 + (depth_hits * 0.14)))
        traits.append(
            {
                "name": "reflection_depth",
                "signal": depth_signal,
                "strength": min(0.18, 0.08 + (depth_hits * 0.02)),
            }
        )

    return [
        trait
        for trait in traits
        if abs(trait["signal"] - 0.5) >= 0.08 or trait["name"] == "communication_style"
    ]


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
