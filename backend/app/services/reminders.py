"""Reminders: the few good reasons Reflectra reaches out.

Checked every minute by the worker, for users who turned notifications on:

  birthday       someone in your People has a birthday tomorrow (10:00-21:00)
  follow_up      something you said you'd do is due ("how did the gym go?") (10:00-20:30)
  weekly_digest  Sunday evening, your week in reflection (18:00-21:00)
  check_in       your daily question, at the time you picked (up to 45 min after)

At most one a day (whichever matters most), never in quiet hours, each thing at
most once, and the lock screen never says what you talked about. Opening one starts
a conversation where Reflectra asks the actual question.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import List, Optional, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import NotificationSent, Person, PushSubscription, User, UserSettings
from app.services.notification_prefs import merged_prefs

logger = logging.getLogger(__name__)

PRIORITY = ("birthday", "follow_up", "weekly_digest", "check_in")
WINDOWS = {
    "birthday": (time(10, 0), time(21, 0)),
    "follow_up": (time(10, 0), time(20, 30)),
    "weekly_digest": (time(18, 0), time(21, 0)),
}
CHECK_IN_GRACE = timedelta(minutes=45)
TITLE = "Reflectra"


@dataclass
class Nudge:
    kind: str
    ref: str
    body: str  # lock-screen text: never about what they said
    opener: Optional[str]  # what Reflectra says first in the app
    url: str


def _parse(value: str, fallback: time) -> time:
    try:
        hours, minutes = (int(x) for x in value.split(":"))
        return time(hours, minutes)
    except (ValueError, AttributeError):
        return fallback


def in_quiet_hours(now: time, start: time, end: time) -> bool:
    if start == end:
        return False
    if start < end:
        return start <= now < end
    return now >= start or now < end  # wraps past midnight


def in_window(now: time, kind: str) -> bool:
    start, end = WINDOWS[kind]
    return start <= now <= end


def check_in_due(now: datetime, at: time) -> bool:
    target = now.replace(hour=at.hour, minute=at.minute, second=0, microsecond=0)
    return target <= now <= target + CHECK_IN_GRACE


def choose(
    candidates: Sequence[Nudge], prefs: dict, local_now: datetime, sent_today: int, already: set
) -> Optional[Nudge]:
    """The one nudge to send now, or None. Pure, so it can be tested."""
    if not prefs.get("enabled") or sent_today > 0:
        return None
    if in_quiet_hours(local_now.time(), _parse(prefs["quiet_start"], time(22, 30)), _parse(prefs["quiet_end"], time(8, 0))):
        return None
    allowed = {
        "birthday": prefs.get("birthdays"),
        "follow_up": prefs.get("follow_ups"),
        "weekly_digest": prefs.get("weekly_digest"),
        "check_in": prefs.get("daily_check_in"),
    }
    for kind in PRIORITY:
        if not allowed.get(kind):
            continue
        for nudge in candidates:
            if nudge.kind != kind or (nudge.kind, nudge.ref) in already:
                continue
            if kind == "check_in":
                if check_in_due(local_now, _parse(prefs["check_in_time"], time(21, 0))):
                    return nudge
            elif kind == "weekly_digest":
                if local_now.weekday() == 6 and in_window(local_now.time(), kind):
                    return nudge
            elif in_window(local_now.time(), kind):
                return nudge
    return None


# --------------------------------------------------------------------------- candidates


async def _candidates(db: AsyncSession, user_id: UUID, local_now: datetime, tz: int) -> List[Nudge]:
    from app.services import followup_service, people_service

    today = local_now.date()
    out: List[Nudge] = []

    tomorrow = today + timedelta(days=1)
    for person in await people_service.all_people(db, user_id):
        if person.birthday and person.birthday[-5:] == tomorrow.strftime("%m-%d"):
            out.append(
                Nudge(
                    "birthday",
                    f"{person.id}:{tomorrow.year}",
                    "Someone in your People has a birthday tomorrow.",
                    f"{person.name}'s birthday is tomorrow. Got anything planned, or want help with a message?",
                    "/app/chat?mode=reflection",
                )
            )

    for row in await followup_service._open_rows(db, user_id):
        state = followup_service.due_state(followup_service._meta(row), today)
        if state["askable"]:
            out.append(
                Nudge(
                    "follow_up",
                    str(row.id),
                    "A quick question about something you mentioned.",
                    f"Last time you said you'd {row.title}. How did it go?",
                    "/app/chat?mode=reflection",
                )
            )

    iso = today.isocalendar()
    out.append(Nudge("weekly_digest", f"{iso.year}-W{iso.week:02d}", "Your week in reflection is ready.", None, "/app/week?play=1"))
    out.append(Nudge("check_in", today.isoformat(), "Got a minute? One question for today.", None, "/app/chat?mode=reflection"))
    return out


async def _check_in_question(db: AsyncSession, user_id: UUID) -> str:
    """One short, specific question drawn from what's going on in their life."""
    from app.services import life_memory_service
    from app.services.llm import chat_complete, llm_available

    facts = await life_memory_service.prompt_lines(db, user_id)
    fallback = "How's today actually going?"
    if not llm_available() or not facts:
        return fallback
    try:
        raw = await chat_complete(
            [
                {
                    "role": "system",
                    "content": "Write ONE short, casual check-in question (under 15 words) a close friend would text, "
                    "about one of these things in their life. No greeting, no emoji, lowercase is fine. Just the question.",
                },
                {"role": "user", "content": "\n".join(facts[:8])},
            ],
            max_tokens=40,
            temperature=0.8,
            fast=True,
        )
    except Exception:
        return fallback
    question = " ".join((raw or "").split()).strip('"')
    return question if 3 <= len(question.split()) <= 20 else fallback


async def send_nudge(db: AsyncSession, user_id: UUID, nudge: Nudge, local_date: str) -> NotificationSent:
    from app.services import followup_service, push_service

    opener = nudge.opener
    if nudge.kind == "check_in":
        opener = await _check_in_question(db, user_id)
    record = NotificationSent(
        user_id=user_id, kind=nudge.kind, ref=nudge.ref, local_date=local_date,
        title=TITLE, body=nudge.body, opener=opener, url=nudge.url,
    )
    db.add(record)
    await db.flush()
    if nudge.kind == "follow_up":
        # Counts as asking, so the chat doesn't ask the same thing again.
        await followup_service.mark_asked(db, user_id, nudge.ref, local_date)
    payload = {"title": TITLE, "body": nudge.body, "url": f"/app/open/{record.id}", "tag": f"reflectra-{nudge.kind}"}
    record.delivered = await push_service.deliver(db, user_id, payload)
    await db.commit()
    return record


async def tick_user(db: AsyncSession, user_id: UUID, prefs: dict, now_utc: datetime) -> Optional[NotificationSent]:
    tz = int(prefs.get("tz_offset_minutes") or 0)
    local_now = now_utc + timedelta(minutes=tz)
    local_date = local_now.date().isoformat()
    sent = (
        await db.execute(
            select(NotificationSent.kind, NotificationSent.ref, NotificationSent.local_date).where(
                NotificationSent.user_id == user_id, NotificationSent.local_date >= (local_now.date() - timedelta(days=8)).isoformat()
            )
        )
    ).all()
    sent_today = sum(1 for _, _, day in sent if day == local_date)
    already = {(kind, ref) for kind, ref, _ in sent}
    nudge = choose(await _candidates(db, user_id, local_now.replace(tzinfo=None), tz), prefs, local_now.replace(tzinfo=None), sent_today, already)
    if nudge is None:
        return None
    return await send_nudge(db, user_id, nudge, local_date)


async def reminder_tick() -> None:
    """Called by the worker every minute."""
    from app.db.database import AsyncSessionLocal

    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                select(UserSettings.user_id, UserSettings.notifications)
                .join(PushSubscription, PushSubscription.user_id == UserSettings.user_id)
                .where(UserSettings.notifications["enabled"].astext == "true")
                .distinct()
            )
        ).all()
    for user_id, stored in rows:
        prefs = {**merged_prefs(stored), "tz_offset_minutes": (stored or {}).get("tz_offset_minutes", 0)}
        try:
            async with AsyncSessionLocal() as db:
                sent = await tick_user(db, user_id, prefs, now)
                if sent is not None:
                    logger.info("Reminder %s sent to %s device(s)", sent.kind, sent.delivered)
        except Exception:
            logger.exception("Reminder check failed for a user")


async def open_nudge(db: AsyncSession, user_id: UUID, nudge_id: UUID) -> dict:
    """Opening a nudge starts a conversation with Reflectra's question already asked."""
    from app.db import crud

    record = (
        await db.execute(select(NotificationSent).where(NotificationSent.id == nudge_id, NotificationSent.user_id == user_id))
    ).scalar_one_or_none()
    if record is None:
        return {"url": "/app/chat?mode=reflection"}
    if record.opener is None:
        return {"url": record.url or "/app/chat?mode=reflection"}
    if record.conversation_id is None:
        titles = {"follow_up": "Checking in", "birthday": "A birthday tomorrow", "check_in": "Today's question"}
        conversation = await crud.create_conversation(
            db=db, user_id=user_id, title=titles.get(record.kind, "Checking in"), mode="reflection", metadata={"nudge": str(record.id)}
        )
        await crud.create_message(
            db=db, user_id=user_id, conversation_id=conversation.id, role="assistant", content=record.opener, embedding=None, token_count=len(record.opener.split())
        )
        record.conversation_id = conversation.id
    record.opened_at = record.opened_at or datetime.now(timezone.utc)
    await db.commit()
    return {"url": f"/app/chat?conversation_id={record.conversation_id}&mode=reflection"}
