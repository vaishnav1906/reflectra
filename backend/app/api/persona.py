"""API routes for personality reflection system."""

from typing import Optional
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, ensure_self
from app.db.database import get_db
from app.services.trait_extraction_service import extract_traits
from app.services.persona_update_service import update_traits
from app.services.snapshot_service import generate_persona_snapshot
from app.services.mirror_engine import invalidate_snapshot_cache
from app.repository.persona_repository import PersonaRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/persona", tags=["persona"])


class ResetPersonaRequest(BaseModel):
    user_id: Optional[str] = None  # ignored: identity comes from the access token

@router.post("/reset")
async def reset_persona(
    request: ResetPersonaRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    try:
        user_uuid = ensure_self(request.user_id, current_user)
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
    await generate_persona_snapshot(db, user_uuid, force_new=True)
    invalidate_snapshot_cache(user_uuid)
    
    return {"status": "persona_reset_success"}


class ReflectionRequest(BaseModel):
    user_id: Optional[str] = None  # ignored: identity comes from the access token
    message: str


class ReflectionResponse(BaseModel):
    traits: dict
    stability: float
    summary: str


class BootstrapRequest(BaseModel):
    user_id: Optional[str] = None  # ignored: identity comes from the access token
    summary_text: str
    # dry_run=True analyses the text and returns what WOULD change, without saving.
    dry_run: bool = False


class VoiceImportRequest(BaseModel):
    # A chat export (WhatsApp .txt, Telegram or ChatGPT .json) or one message per line.
    text: str = Field(max_length=3_500_000)
    sender: Optional[str] = Field(default=None, max_length=80)  # which person in the chat is the user
    dry_run: bool = True


@router.get("/voice-import")
async def get_voice_import(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    """Whether the user has imported their own texts, and what was learned from them."""
    from app.services import voice_import_service

    return {"imported": await voice_import_service.current_import(db, current_user.id)}


@router.post("/voice-import")
async def import_voice(request: VoiceImportRequest, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    """Learn how the user writes from messages they wrote elsewhere.

    Only the chosen sender's messages are kept; everyone else's are discarded.
    dry_run=True returns what would be learned without saving anything.
    """
    from sqlalchemy import select

    from app.db.models import User
    from app.services import voice_import_service

    display_name = (
        await db.execute(select(User.display_name).where(User.id == current_user.id))
    ).scalar_one_or_none()
    try:
        result = voice_import_service.read_upload(request.text, request.sender, display_name)
    except voice_import_service.VoiceImportError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    samples = result.pop("_samples", None)
    result["saved"] = False
    if samples and not request.dry_run:
        await voice_import_service.save_import(db, current_user.id, samples, str(result["format"]))
        invalidate_snapshot_cache(str(current_user.id))
        result["saved"] = True
    return result


@router.delete("/voice-import")
async def delete_voice_import(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    from app.services import voice_import_service

    await voice_import_service.remove_import(db, current_user.id)
    return {"imported": None}


@router.post("/bootstrap")
async def bootstrap_persona(
    request: BootstrapRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Seed the persona from a description of the user (e.g. a summary another AI wrote).

    Each trait reading must be backed by a verbatim quote from the text; traits the
    text does not cover are left alone, and existing learning is blended, not replaced.
    See app.services.persona_bootstrap_service for the rules.
    """
    from app.constants import DEFAULT_TRAIT_CONFIDENCE, DEFAULT_TRAIT_SCORE, TRAIT_LIST
    from app.db.models import ExternalInput
    from app.services.persona_bootstrap_service import (
        BootstrapInputError,
        BootstrapUnavailable,
        merge_trait,
        read_summary,
        validate_summary,
    )

    user_id = ensure_self(request.user_id, current_user)

    try:
        summary_text = validate_summary(request.summary_text)
    except BootstrapInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    try:
        readings, notes = await read_summary(summary_text)
    except BootstrapUnavailable as exc:
        logger.warning("Bootstrap unavailable: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="The AI couldn't read that right now. Nothing was changed. Try again in a minute.",
        )

    existing = {m.trait_name: m for m in await PersonaRepository.get_all_metrics(db, user_id)}
    changes = []
    for reading in readings:
        metric = existing.get(reading.trait)
        changes.append(
            merge_trait(
                previous_score=float(metric.score) if metric else DEFAULT_TRAIT_SCORE,
                previous_confidence=float(metric.confidence) if metric else DEFAULT_TRAIT_CONFIDENCE,
                evidence_count=int(metric.evidence_count or 0) if metric else 0,
                reading=reading,
            )
        )

    applied_any = any(change.applied for change in changes)
    payload = {
        "dry_run": request.dry_run,
        "saved": False,
        "traits": [change.to_dict() for change in changes],
        "notes": notes,
        "recognised": sum(1 for change in changes if change.applied),
        "total_traits": len(TRAIT_LIST),
    }

    if request.dry_run or not applied_any:
        return payload

    await PersonaRepository.initialize_missing_traits(db, user_id)
    for change in changes:
        if not change.applied:
            continue
        metric = await PersonaRepository.get_metric(db, user_id, change.trait)
        if metric:
            await PersonaRepository.update_metric(
                db, metric, change.new_score, change.new_confidence, change.imported_score
            )

    # Keep the source text and the facts taken from it, so conversations can use them.
    db.add(
        ExternalInput(
            user_id=user_id,
            source="persona_bootstrap",
            content=summary_text,
            extracted_markers={"notes": notes, "traits": payload["traits"]},
            confidence_weight=0.4,
        )
    )
    await db.commit()

    snapshot = await generate_persona_snapshot(db, user_id)
    invalidate_snapshot_cache(user_id)

    payload["saved"] = True
    payload["stability"] = round(snapshot.stability_index, 2)
    payload["summary"] = snapshot.summary_text
    return payload


@router.post("/reflection", response_model=ReflectionResponse)
async def process_reflection(
    request: ReflectionRequest,
    current_user: CurrentUser,
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
        user_id = ensure_self(request.user_id, current_user)
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


@router.get("/portrait/{user_id}")
async def get_portrait(
    user_id: str,
    tz_offset_minutes: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """Everything the Persona page shows, from the same data as the PDF report:
    trait readings with confidence, how they moved, rhythm, voice and how Reflectra adapts."""
    from dataclasses import asdict

    from app.services.persona_report_service import (
        TRAIT_META,
        adaptation_lines,
        collect_report_data,
        confidence_label,
        headline,
        side,
    )

    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id format")

    data = await collect_report_data(db, user_uuid, tz_offset_minutes)
    payload = asdict(data)
    payload["generated_at"] = data.generated_at.isoformat()
    payload["headline"] = headline(data.traits)
    payload["adaptation"] = adaptation_lines(data.traits, data.voice)
    from app.services.feedback_service import trait_verdicts

    verdicts = await trait_verdicts(db, user_uuid)
    payload["traits"] = [
        {
            "key": t.key,
            "name": TRAIT_META[t.key]["name"],
            "low": TRAIT_META[t.key]["low"],
            "high": TRAIT_META[t.key]["high"],
            "score": round(t.score, 3),
            "confidence": round(t.confidence, 3),
            "confidence_label": confidence_label(t.confidence),
            "evidence_count": t.evidence_count,
            "reading": TRAIT_META[t.key][f"read_{side(t.score)}"],
            "feedback": verdicts.get(t.key),
        }
        for t in data.traits
    ]
    voice = dict(data.voice)
    voice["abbreviations"] = [{"word": w, "count": c} for w, c in voice.get("abbreviations", [])]
    payload["voice"] = voice
    return payload

