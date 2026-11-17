"""Notification endpoints: subscribe a device, send a test, open a nudge."""

from datetime import datetime, timezone
from typing import Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.db.database import get_db
from app.db.models import UserSettings
from app.services import push_service, reminders
from app.services.notification_prefs import merged_prefs

router = APIRouter(prefix="/notifications", tags=["notifications"])


class SubscriptionIn(BaseModel):
    endpoint: str = Field(min_length=10, max_length=2000)
    keys: Dict[str, str] = Field(default_factory=dict)
    platform: str = Field(default="web", pattern="^(web|android|ios)$")


class UnsubscribeIn(BaseModel):
    endpoint: str = Field(min_length=10, max_length=2000)


@router.get("/vapid-key")
async def vapid_key():
    """The public key a browser needs to subscribe to Web Push."""
    return {"public_key": push_service.vapid_keys()[0]}


@router.post("/subscribe")
async def subscribe(
    body: SubscriptionIn,
    current_user: CurrentUser,
    tz_offset_minutes: int = Query(0, ge=-840, le=840),
    user_agent: Optional[str] = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    if body.platform == "web" and not ({"p256dh", "auth"} <= set(body.keys)):
        raise HTTPException(status_code=422, detail="This browser didn't send the keys Web Push needs.")
    await push_service.save_subscription(db, current_user.id, body.endpoint, body.keys, body.platform, user_agent or "")
    settings_row = (await db.execute(select(UserSettings).where(UserSettings.user_id == current_user.id))).scalar_one_or_none()
    if settings_row is not None:
        # Reminders go out by the user's own clock.
        settings_row.notifications = {**(settings_row.notifications or {}), "tz_offset_minutes": tz_offset_minutes}
        await db.commit()
    return {"subscribed": True, "devices": len(await push_service.subscriptions_for(db, current_user.id))}


@router.post("/unsubscribe")
async def unsubscribe(body: UnsubscribeIn, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    await push_service.remove_subscription(db, current_user.id, body.endpoint)
    return {"subscribed": False}


@router.get("/status")
async def status(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    settings_row = (await db.execute(select(UserSettings).where(UserSettings.user_id == current_user.id))).scalar_one_or_none()
    devices = await push_service.subscriptions_for(db, current_user.id)
    return {
        "prefs": merged_prefs(settings_row.notifications if settings_row else None),
        "devices": [{"platform": d.platform, "since": d.created_at.isoformat() if d.created_at else None} for d in devices],
    }


@router.post("/test")
async def send_test(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    """Send a harmless test to every device of this user, right now."""
    if not await push_service.subscriptions_for(db, current_user.id):
        raise HTTPException(status_code=409, detail="Turn on notifications in this browser first.")
    nudge = reminders.Nudge("test", "test", "Notifications are working. This is what they'll look like.", None, "/app/settings")
    record = await reminders.send_nudge(db, current_user.id, nudge, datetime.now(timezone.utc).date().isoformat())
    if not record.delivered:
        raise HTTPException(status_code=502, detail="The browser's push service didn't accept it. Try turning notifications off and on.")
    return {"delivered": record.delivered}


@router.post("/open/{nudge_id}")
async def open_nudge(nudge_id: UUID, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    """Where tapping a notification leads: a chat that opens with Reflectra's question."""
    return await reminders.open_nudge(db, current_user.id, nudge_id)
