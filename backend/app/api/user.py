import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, ensure_self
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
    MirrorLog,
    MirrorResponseMemory,
    LinguisticFingerprint,
    ReactionPattern,
    ExternalInput,
    Feedback,
    Person,
    Job,
    LifeFact,
    NotificationSent,
    PushSubscription,
)
from app.services.auth_service import delete_supabase_auth_user
from app.services.twin_policy import (
    DEFAULT_TWIN_SETTINGS,
    resolve_twin_settings,
    validate_twin_autonomy_mode,
)

router = APIRouter(prefix="/user", tags=["User"])
logger = logging.getLogger(__name__)

# Everything "Erase what Reflectra knows" removes. Children before parents
# (messages before conversations). A new per-user table must be added here;
# tests/backend/test_settings_data.py fails if one is missing.
ERASABLE_MODELS = (
    Job,  # first: queued learning must not run again after an erase
    Message,
    MirrorResponseMemory,
    MirrorLog,
    ReactionPattern,
    Conversation,
    PersonalityProfile,
    UserPersonaMetric,
    PersonaSnapshot,
    BehavioralInsight,
    ReflectionLog,
    LinguisticFingerprint,
    ExternalInput,
    Feedback,
    Person,
    LifeFact,
    NotificationSent,
    ScheduleContext,
)
# Devices stay subscribed (a preference, like settings); the record of what was sent is erased.
KEPT_ON_ERASE = (UserSettings, PushSubscription)


def _ensure_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

class UserRequest(BaseModel):
    user_id: Optional[str] = None  # ignored: identity comes from the access token


class UserSettingsUpdateRequest(BaseModel):
    user_id: Optional[str] = None  # ignored: identity comes from the access token
    persona_mirroring: bool
    pattern_tracking: bool
    daily_reflections: bool
    digital_twin_enabled: Optional[bool] = None
    twin_autonomy_mode: Optional[str] = None
    twin_mirror_intensity: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    twin_require_approval: Optional[bool] = None

    @model_validator(mode="after")
    def validate_mode(self):
        if self.twin_autonomy_mode is not None:
            self.twin_autonomy_mode = validate_twin_autonomy_mode(self.twin_autonomy_mode)
        return self


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
            persona_mirroring=DEFAULT_TWIN_SETTINGS["persona_mirroring"],
            pattern_tracking=DEFAULT_TWIN_SETTINGS["pattern_tracking"],
            daily_reflections=DEFAULT_TWIN_SETTINGS["daily_reflections"],
            digital_twin_enabled=DEFAULT_TWIN_SETTINGS["digital_twin_enabled"],
            twin_autonomy_mode=DEFAULT_TWIN_SETTINGS["twin_autonomy_mode"],
            twin_mirror_intensity=DEFAULT_TWIN_SETTINGS["twin_mirror_intensity"],
            twin_require_approval=DEFAULT_TWIN_SETTINGS["twin_require_approval"],
        )
        db.add(settings_record)
        await db.commit()
        await db.refresh(settings_record)

    effective_settings = resolve_twin_settings(settings_record)

    return {
        "user_id": str(settings_record.user_id),
        "settings": effective_settings,
        "updated_at": settings_record.updated_at.isoformat() if settings_record.updated_at else None,
    }


@router.post("/settings/update")
async def update_user_settings(
    request: UserSettingsUpdateRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    try:
        user_uuid = ensure_self(request.user_id, current_user)
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
            digital_twin_enabled=(
                request.digital_twin_enabled
                if request.digital_twin_enabled is not None
                else DEFAULT_TWIN_SETTINGS["digital_twin_enabled"]
            ),
            twin_autonomy_mode=(
                request.twin_autonomy_mode
                if request.twin_autonomy_mode is not None
                else DEFAULT_TWIN_SETTINGS["twin_autonomy_mode"]
            ),
            twin_mirror_intensity=(
                request.twin_mirror_intensity
                if request.twin_mirror_intensity is not None
                else DEFAULT_TWIN_SETTINGS["twin_mirror_intensity"]
            ),
            twin_require_approval=(
                request.twin_require_approval
                if request.twin_require_approval is not None
                else DEFAULT_TWIN_SETTINGS["twin_require_approval"]
            ),
        )
        db.add(settings_record)
    else:
        settings_record.persona_mirroring = request.persona_mirroring
        settings_record.pattern_tracking = request.pattern_tracking
        settings_record.daily_reflections = request.daily_reflections
        if request.digital_twin_enabled is not None:
            settings_record.digital_twin_enabled = request.digital_twin_enabled
        if request.twin_autonomy_mode is not None:
            settings_record.twin_autonomy_mode = request.twin_autonomy_mode
        if request.twin_mirror_intensity is not None:
            settings_record.twin_mirror_intensity = request.twin_mirror_intensity
        if request.twin_require_approval is not None:
            settings_record.twin_require_approval = request.twin_require_approval

    await db.commit()
    await db.refresh(settings_record)

    effective_settings = resolve_twin_settings(settings_record)

    return {
        "status": "success",
        "user_id": str(settings_record.user_id),
        "settings": effective_settings,
        "updated_at": settings_record.updated_at.isoformat() if settings_record.updated_at else None,
    }


@router.get("/export-persona-report")
async def export_persona_report(
    user_id: str = Query(..., description="User UUID"),
    tz_offset_minutes: int = Query(0, description="Viewer's UTC offset in minutes"),
    db: AsyncSession = Depends(get_db),
):
    """A PDF portrait of the user, built only from their stored conversations."""
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id format")

    await _assert_user_exists(db, user_uuid)

    from app.services.persona_report_service import build_persona_report_pdf

    try:
        pdf_bytes = await build_persona_report_pdf(db, user_uuid, tz_offset_minutes)
    except Exception:
        import logging

        logging.getLogger(__name__).exception("Persona report generation failed")
        raise HTTPException(status_code=500, detail="Couldn't build the report. Try again in a moment.")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="reflectra-portrait.pdf"'},
    )


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

    # One overall confidence everywhere: the same number "How it works" breaks down.
    from app.services.confidence_interval_service import compute_confidence_interval

    overall = await compute_confidence_interval(db, user_uuid)
    confidence_pct = round(overall.center * 100, 1)

    cycle_days = 7
    now = datetime.now(timezone.utc)
    learning_active = bool(
        last_inference and (now - last_inference) <= timedelta(days=cycle_days)
    )

    # What the sidebar actually shows: how much of the user Reflectra has read,
    # and whether the "Keep learning about me" switch is on.
    messages = int(
        (
            await db.execute(
                select(func.count(Message.id)).where(Message.user_id == user_uuid, Message.role == "user")
            )
        ).scalar_one()
        or 0
    )
    tracking = (
        await db.execute(select(UserSettings.pattern_tracking).where(UserSettings.user_id == user_uuid))
    ).scalar_one_or_none()

    return {
        "last_inference": last_inference.isoformat() if last_inference else None,
        "memory_count": memory_count,
        "confidence": confidence_pct,
        "confidence_range": [round(overall.lower * 100), round(overall.upper * 100)],
        "confidence_tier": overall.tier,
        "learning_active": learning_active,
        "cycle_days": cycle_days,
        "messages": messages,
        "learning_enabled": True if tracking is None else bool(tracking),
    }

@router.post("/clear-data")
async def clear_user_data(request: UserRequest, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    """Erase everything Reflectra has stored or learned about the user; keep the account.

    Settings are preferences, not learned data, so they survive: someone who turned
    learning off should not have it silently switched back on by an erase.
    """
    try:
        try:
            user_uuid = ensure_self(request.user_id, current_user)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid user_id format")

        # One transaction: either all of it goes or none of it does.
        for model in ERASABLE_MODELS:
            await db.execute(delete(model).where(model.user_id == user_uuid))

        await db.commit()
        return {"status": "success", "message": "All user data cleared."}
    except HTTPException:
        raise
    except Exception:
        await db.rollback()
        logger.exception("clear-data failed")
        raise HTTPException(status_code=500, detail="Couldn't erase your data. Nothing was changed.")

@router.delete("/delete-account")
async def delete_user_account(request: UserRequest, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    """Hard Reset: Deletes the user entirely and cascades."""
    try:
        try:
            user_uuid = ensure_self(request.user_id, current_user)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid user_id format")

        auth_user_id = current_user.auth_user_id

        # Delete user - ON DELETE CASCADE will handle the rest automatically
        await db.execute(delete(User).where(User.id == user_uuid))
        await db.commit()
        auth_deleted = await delete_supabase_auth_user(auth_user_id)
        return {
            "status": "success",
            "message": "User account and all data completely deleted.",
            "auth_account_deleted": auth_deleted,
        }
    except HTTPException:
        raise
    except Exception:
        await db.rollback()
        logger.exception("delete-account failed")
        raise HTTPException(status_code=500, detail="Couldn't delete your account. Nothing was changed.")


# --------------------------------------------------------------------------- About you


class ProfilePatch(BaseModel):
    display_name: Optional[str] = Field(default=None, max_length=60)
    birth_date: Optional[str] = Field(default=None, max_length=10)  # "" clears it
    notifications: Optional[dict] = None
    theme: Optional[dict] = None  # {"hue", "saturation"}; {} resets to the default


async def _profile(db: AsyncSession, user: User, tz_offset_minutes: int = 0) -> dict:
    from app.services.notification_prefs import age_on, merged_prefs

    settings_row = (await db.execute(select(UserSettings).where(UserSettings.user_id == user.id))).scalar_one_or_none()
    today = (datetime.now(timezone.utc) + timedelta(minutes=tz_offset_minutes)).date()
    return {
        "display_name": user.display_name or user.email.split("@", 1)[0],
        "email": user.email,
        "birth_date": user.birth_date.isoformat() if user.birth_date else None,
        "age": age_on(user.birth_date, today),
        "notifications": merged_prefs(settings_row.notifications if settings_row else None),
        "theme": (settings_row.theme if settings_row else None) or None,
        "member_since": user.created_at.isoformat() if user.created_at else None,
    }


@router.get("/profile")
async def get_profile(
    current_user: CurrentUser,
    tz_offset_minutes: int = Query(0, ge=-840, le=840),
    db: AsyncSession = Depends(get_db),
):
    """Name, date of birth (and the age it gives) and notification switches."""
    user = (await db.execute(select(User).where(User.id == current_user.id))).scalar_one()
    return await _profile(db, user, tz_offset_minutes)


@router.patch("/profile")
async def update_profile(
    body: ProfilePatch,
    current_user: CurrentUser,
    tz_offset_minutes: int = Query(0, ge=-840, le=840),
    db: AsyncSession = Depends(get_db),
):
    from app.services import notification_prefs as prefs

    user = (await db.execute(select(User).where(User.id == current_user.id))).scalar_one()
    today = (datetime.now(timezone.utc) + timedelta(minutes=tz_offset_minutes)).date()
    fields = body.model_dump(exclude_unset=True)
    try:
        if "display_name" in fields and fields["display_name"] is not None:
            user.display_name = prefs.clean_display_name(fields["display_name"])
        if "birth_date" in fields:
            user.birth_date = prefs.clean_birth_date(fields["birth_date"], today)
        if fields.get("theme") is not None:
            theme_row = (await db.execute(select(UserSettings).where(UserSettings.user_id == user.id))).scalar_one_or_none()
            if theme_row is None:
                theme_row = UserSettings(user_id=user.id)
                db.add(theme_row)
            theme_row.theme = prefs.clean_theme(fields["theme"]) if fields["theme"] else None
        if fields.get("notifications") is not None:
            settings_row = (
                await db.execute(select(UserSettings).where(UserSettings.user_id == user.id))
            ).scalar_one_or_none()
            if settings_row is None:
                settings_row = UserSettings(user_id=user.id)
                db.add(settings_row)
            settings_row.notifications = prefs.clean_prefs(fields["notifications"], settings_row.notifications)
            # Reminders go out by the user's own clock, so remember where that is.
            settings_row.notifications = {**settings_row.notifications, "tz_offset_minutes": tz_offset_minutes}
    except prefs.ProfileError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    await db.commit()
    await db.refresh(user)
    return await _profile(db, user, tz_offset_minutes)
