from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import (
    User,
    Conversation,
    Message,
    PersonalityProfile,
    BehavioralInsight,
    ReflectionLog,
    UserPersonaMetric,
    PersonaSnapshot,
    ScheduleContext,
    UserSettings,
)

router = APIRouter(prefix="/user", tags=["User"])


def _ensure_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

class UserRequest(BaseModel):
    user_id: str


class UserSettingsUpdateRequest(BaseModel):
    user_id: str
    persona_mirroring: bool
    pattern_tracking: bool
    daily_reflections: bool


async def _assert_user_exists(db: AsyncSession, user_uuid: UUID) -> None:
    result = await db.execute(select(User.id).where(User.id == user_uuid))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="User not found")


@router.get("/settings")
async def get_user_settings(
    user_id: str = Query(..., description="User UUID"),
    db: AsyncSession = Depends(get_db),
):
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id format")

    await _assert_user_exists(db, user_uuid)

    result = await db.execute(select(UserSettings).where(UserSettings.user_id == user_uuid))
    settings_record = result.scalar_one_or_none()

    if settings_record is None:
        settings_record = UserSettings(
            user_id=user_uuid,
            persona_mirroring=True,
            pattern_tracking=True,
            daily_reflections=True,
        )
        db.add(settings_record)
        await db.commit()
        await db.refresh(settings_record)

    return {
        "user_id": str(settings_record.user_id),
        "settings": {
            "persona_mirroring": bool(settings_record.persona_mirroring),
            "pattern_tracking": bool(settings_record.pattern_tracking),
            "daily_reflections": bool(settings_record.daily_reflections),
        },
        "updated_at": settings_record.updated_at.isoformat() if settings_record.updated_at else None,
    }


@router.post("/settings/update")
async def update_user_settings(
    request: UserSettingsUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        user_uuid = UUID(request.user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id format")

    await _assert_user_exists(db, user_uuid)

    result = await db.execute(select(UserSettings).where(UserSettings.user_id == user_uuid))
    settings_record = result.scalar_one_or_none()

    if settings_record is None:
        settings_record = UserSettings(
            user_id=user_uuid,
            persona_mirroring=request.persona_mirroring,
            pattern_tracking=request.pattern_tracking,
            daily_reflections=request.daily_reflections,
        )
        db.add(settings_record)
    else:
        settings_record.persona_mirroring = request.persona_mirroring
        settings_record.pattern_tracking = request.pattern_tracking
        settings_record.daily_reflections = request.daily_reflections

    await db.commit()
    await db.refresh(settings_record)

    return {
        "status": "success",
        "user_id": str(settings_record.user_id),
        "settings": {
            "persona_mirroring": bool(settings_record.persona_mirroring),
            "pattern_tracking": bool(settings_record.pattern_tracking),
            "daily_reflections": bool(settings_record.daily_reflections),
        },
        "updated_at": settings_record.updated_at.isoformat() if settings_record.updated_at else None,
    }


@router.get("/system-state")
async def get_system_state(
    user_id: str = Query(..., description="User UUID"),
    db: AsyncSession = Depends(get_db),
):
    """Get per-user runtime state for the sidebar System State card."""
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id format")

    # Last inference timestamp from trait metric updates.
    last_inference_stmt = select(func.max(UserPersonaMetric.last_updated)).where(
        UserPersonaMetric.user_id == user_uuid
    )
    last_inference_result = await db.execute(last_inference_stmt)
    last_inference = _ensure_utc(last_inference_result.scalar_one_or_none())

    # Memory count composed from insight, reflection, and snapshot stores.
    insight_count_stmt = select(func.count(BehavioralInsight.id)).where(
        BehavioralInsight.user_id == user_uuid
    )
    reflection_count_stmt = select(func.count(ReflectionLog.id)).where(
        ReflectionLog.user_id == user_uuid
    )
    snapshot_count_stmt = select(func.count(PersonaSnapshot.id)).where(
        PersonaSnapshot.user_id == user_uuid
    )

    insight_count_result = await db.execute(insight_count_stmt)
    reflection_count_result = await db.execute(reflection_count_stmt)
    snapshot_count_result = await db.execute(snapshot_count_stmt)

    memory_count = (
        int(insight_count_result.scalar_one() or 0)
        + int(reflection_count_result.scalar_one() or 0)
        + int(snapshot_count_result.scalar_one() or 0)
    )

    # Overall confidence from trait metrics.
    confidence_stmt = select(func.avg(UserPersonaMetric.confidence)).where(
        UserPersonaMetric.user_id == user_uuid
    )
    confidence_result = await db.execute(confidence_stmt)
    avg_confidence = confidence_result.scalar_one_or_none()
    confidence_pct = round(float(avg_confidence) * 100, 1) if avg_confidence is not None else 0.0

    cycle_days = 7
    now = datetime.now(timezone.utc)
    learning_active = bool(
        last_inference and (now - last_inference) <= timedelta(days=cycle_days)
    )

    return {
        "last_inference": last_inference.isoformat() if last_inference else None,
        "memory_count": memory_count,
        "confidence": confidence_pct,
        "learning_active": learning_active,
        "cycle_days": cycle_days,
    }

@router.post("/clear-data")
async def clear_user_data(request: UserRequest, db: AsyncSession = Depends(get_db)):
    """Soft Reset: Clears all user data except the user account itself."""
    
    try:
        try:
            user_uuid = UUID(request.user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid user_id format")

        # delete messages
        await db.execute(delete(Message).where(Message.user_id == user_uuid))
        
        # delete conversations
        await db.execute(delete(Conversation).where(Conversation.user_id == user_uuid))
        
        # delete persona profiles
        await db.execute(delete(PersonalityProfile).where(PersonalityProfile.user_id == user_uuid))
        
        # delete persona traits / metrics
        await db.execute(delete(UserPersonaMetric).where(UserPersonaMetric.user_id == user_uuid))
        
        # delete snapshots
        await db.execute(delete(PersonaSnapshot).where(PersonaSnapshot.user_id == user_uuid))
        
        # delete insights
        await db.execute(delete(BehavioralInsight).where(BehavioralInsight.user_id == user_uuid))
        
        # delete reflections
        await db.execute(delete(ReflectionLog).where(ReflectionLog.user_id == user_uuid))
        
        # delete schedule context
        await db.execute(delete(ScheduleContext).where(ScheduleContext.user_id == user_uuid))

        # delete user settings
        await db.execute(delete(UserSettings).where(UserSettings.user_id == user_uuid))
        
        await db.commit()
        return {"status": "success", "message": "All user data cleared."}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/delete-account")
async def delete_user_account(request: UserRequest, db: AsyncSession = Depends(get_db)):
    """Hard Reset: Deletes the user entirely and cascades."""
    try:
        try:
            user_uuid = UUID(request.user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid user_id format")

        # Delete user - ON DELETE CASCADE will handle the rest automatically
        await db.execute(delete(User).where(User.id == user_uuid))
        await db.commit()
        return {"status": "success", "message": "User account and all data completely deleted."}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
