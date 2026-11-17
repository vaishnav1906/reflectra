import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import Message
from app.services import followup_service
from app.services.confidence_interval_service import build_confidence_explainability
from app.services.reflection_service import ReflectionUnavailable, generate_reflections, get_reflections
from app.services.timeline_service import build_timeline

router = APIRouter()
logger = logging.getLogger(__name__)

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@router.get("/metrics/{user_id}")
async def get_behavioral_metrics(
    user_id: UUID,
    view: str = Query("week", description="Timeframe view: day, week, month, all"),
    db: AsyncSession = Depends(get_db),
):
    """
    Fetch aggregated behavioral metrics over time for Activity Rings and Line Charts.
    """
    now = _utc_now()

    if view == "day":
        start_date = now - timedelta(days=1)
        trunc_period = "hour"
    elif view == "month":
        start_date = now - timedelta(days=30)
        trunc_period = "day"
    elif view == "all":
        start_date = None
        trunc_period = "day"
    else: # default week
        start_date = now - timedelta(days=7)
        trunc_period = "day"
        
    date_trunc_expr = func.date_trunc(trunc_period, Message.created_at)

    filters = [
        Message.user_id == user_id,
        Message.role == "user",
    ]
    if start_date is not None:
        filters.append(Message.created_at >= start_date)

    stmt = select(
        date_trunc_expr.label("period"),
        func.count(Message.id).label("message_count"),
        func.sum(Message.token_count).label("total_tokens"),
        func.avg(Message.emotional_intensity).label("avg_emotional_intensity"),
        func.avg(Message.reflection_depth).label("avg_reflection_depth"),
        func.avg(Message.response_delay_ms).label("avg_delay_ms"),
    ).where(
        *filters
    ).group_by(date_trunc_expr).order_by(date_trunc_expr)

    result = await db.execute(stmt)
    rows = result.all()

    data = []
    
    # Totals for the ring activity baselines
    totals = {
        "message_count": 0,
    }
    
    for row in rows:
        data.append({
            "timestamp": row.period.isoformat(),
            "message_count": row.message_count,
            "total_tokens": row.total_tokens or 0,
            "emotional_intensity": float(row.avg_emotional_intensity) if row.avg_emotional_intensity else None,
            "reflection_depth": float(row.avg_reflection_depth) if row.avg_reflection_depth else None,
            "response_delay_ms": int(row.avg_delay_ms) if row.avg_delay_ms else None,
        })
        totals["message_count"] += row.message_count

    return {
        "view": view,
        "start_date": start_date.isoformat() if start_date is not None else "all",
        "totals": totals,
        "timeline": data,
    }

@router.get("/followups/{user_id}")
async def get_followups(
    user_id: UUID,
    tz_offset_minutes: int = Query(0, ge=-840, le=840),
    db: AsyncSession = Depends(get_db),
):
    """Things the user said they'd do: open ones, recently settled ones, and their follow-through rate."""
    return await followup_service.list_followups(db, user_id, tz_offset_minutes)


@router.post("/followups/{user_id}/{followup_id}")
async def update_followup(
    user_id: UUID,
    followup_id: UUID,
    status: str = Query(..., pattern="^(done|dropped|open)$"),
    tz_offset_minutes: int = Query(0, ge=-840, le=840),
    db: AsyncSession = Depends(get_db),
):
    """Mark a follow-up done, dropped, or open again."""
    if not await followup_service.set_status(db, user_id, followup_id, status, tz_offset_minutes):
        raise HTTPException(status_code=404, detail="That follow-up no longer exists.")
    return await followup_service.list_followups(db, user_id, tz_offset_minutes)


@router.get("/reflections/{user_id}")
async def get_user_reflections(user_id: UUID, db: AsyncSession = Depends(get_db)):
    """
    Evidence-backed reflections: patterns across the user's conversations, each with
    the quotes that support it, plus whether a fresh set can be generated.
    """
    return await get_reflections(db, user_id)


@router.post("/reflections/{user_id}/generate")
async def generate_user_reflections(
    user_id: UUID,
    force: bool = Query(False, description="Re-read the same messages even if nothing new was said"),
    db: AsyncSession = Depends(get_db),
):
    """Read the user's recent messages and write a fresh set of reflections."""
    try:
        return await generate_reflections(db, user_id, force=force)
    except ReflectionUnavailable as exc:
        raise HTTPException(status_code=exc.status, detail=exc.reason)


@router.get("/heatmap/{user_id}")
async def get_activity_heatmap(
    user_id: UUID,
    days: int = Query(30, description="Days to track back"),
    db: AsyncSession = Depends(get_db),
):
    """
    Fetch message frequency by hour of the day and day of week.
    Returns array where index 0 is Sunday, index 6 is Saturday.
    """
    start_date = _utc_now() - timedelta(days=days)

    from sqlalchemy import extract
    
    # Extract Dow (0-6) and Hour (0-23)
    stmt = select(
        extract('dow', Message.created_at).label('day_of_week'),
        extract('hour', Message.created_at).label('hour_of_day'),
        func.count(Message.id).label('message_count')
    ).where(
        Message.user_id == user_id,
        Message.role == "user",
        Message.created_at >= start_date
    ).group_by(
        extract('dow', Message.created_at),
        extract('hour', Message.created_at)
    )

    result = await db.execute(stmt)
    rows = result.all()

    # Initialize empty 7x24 grid (Sunday=0 to Saturday=6)
    heatmap = [[0 for _ in range(24)] for _ in range(7)]
    
    for row in rows:
        day = int(row.day_of_week)
        hour = int(row.hour_of_day)
        count = row.message_count
        heatmap[day][hour] = count

    return {
        "range_days": days,
        "heatmap": heatmap
    }


TIMELINE_RANGES = {"30d": 30, "90d": 90, "1y": 365, "all": None}


@router.get("/timeline/{user_id}")
async def get_timeline(
    user_id: UUID,
    range: str = Query("all", description="30d, 90d, 1y or all"),
    tz_offset_minutes: int = Query(0, description="Viewer's UTC offset in minutes, so days match their calendar"),
    db: AsyncSession = Depends(get_db),
):
    """
    Day-by-day history: conversations, message counts, mood, depth, a highlight per day,
    daily trait scores and milestones. All computed from stored rows.
    """
    normalized = range if range in TIMELINE_RANGES else "all"
    payload = await build_timeline(db, user_id, TIMELINE_RANGES[normalized], tz_offset_minutes)
    payload["range"] = normalized
    return payload


@router.get("/confidence-explainability/{user_id}")
async def get_confidence_explainability(
    user_id: UUID,
    message: Optional[str] = Query(None, description="Optional message text for per-request explainability"),
    db: AsyncSession = Depends(get_db),
):
    """Expose confidence interval source contributions for explainability."""
    message_text = (message or "").strip()
    if not message_text:
        latest_stmt = (
            select(Message.content)
            .where(
                Message.user_id == user_id,
                Message.role == "user",
            )
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        latest_result = await db.execute(latest_stmt)
        message_text = (latest_result.scalar_one_or_none() or "")

    payload = await build_confidence_explainability(
        db=db,
        user_id=user_id,
        message_text=message_text,
    )
    payload["message_used"] = message_text
    return payload


@router.get("/system/{user_id}")
async def get_system_facts(user_id: UUID, db: AsyncSession = Depends(get_db)):
    """How Reflectra works, in real numbers: the rules it runs on (read from the code's
    constants) and this user's live figures. Powers the "How it works" page."""
    import os

    from sqlalchemy import Integer

    from app import constants
    from app.db.models import Conversation, MirrorLog, UserPersonaMetric
    from app.services import llm
    from app.services.confidence_interval_service import SOURCE_WEIGHTS, controls_for_tier
    from app.services import conversation_craft as craft
    from app.services import embedding_service
    from app.services.conversation_craft import load_voice_samples
    from app.services.persona_bootstrap_service import STRENGTH_CONFIDENCE, STRENGTH_MESSAGE_EQUIVALENT
    from app.services.reflection_service import MIN_MESSAGES_TO_REFLECT, SOURCE_MESSAGE_LIMIT, get_reflections
    from app.services.snapshot_service import SNAPSHOT_MIN_INTERVAL

    message_count = int(
        (await db.execute(select(func.count(Message.id)).where(Message.user_id == user_id, Message.role == "user"))).scalar() or 0
    )
    conversation_count = int(
        # Conversations you actually said something in: the same count Persona and Timeline show.
        (
            await db.execute(
                select(func.count(func.distinct(Message.conversation_id))).where(
                    Message.user_id == user_id, Message.role == "user"
                )
            )
        ).scalar()
        or 0
    )
    metrics = (await db.execute(select(UserPersonaMetric).where(UserPersonaMetric.user_id == user_id))).scalars().all()

    telemetry = (
        await db.execute(
            select(
                func.count(MirrorLog.id),
                func.avg(MirrorLog.inference_duration_ms),
                func.sum(func.cast(MirrorLog.fallback_triggered, Integer)),
            ).where(MirrorLog.user_id == user_id)
        )
    ).first()
    mirror_replies = int(telemetry[0] or 0)

    latest_message = (
        await db.execute(
            select(Message.content)
            .where(Message.user_id == user_id, Message.role == "user")
            .order_by(Message.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none() or ""
    confidence = await build_confidence_explainability(db=db, user_id=user_id, message_text=latest_message)
    reflections = await get_reflections(db, user_id)
    voice_samples = await load_voice_samples(db, user_id)
    remembered_by_meaning = await embedding_service.count_embedded(db, user_id)
    recallable = int(
        (
            await db.execute(
                select(func.count(Message.id)).where(
                    Message.user_id == user_id, Message.role == "user", func.length(Message.content) >= 20
                )
            )
        ).scalar()
        or 0
    )
    if remembered_by_meaning < recallable:
        embedding_service.schedule_backfill(user_id, limit=48)  # catch up in the background

    provider = llm.active_provider()
    return {
        "rules": {
            "traits": {
                "count": len(constants.TRAIT_LIST),
                "max_step_per_message": constants.MAX_STRENGTH_PER_MESSAGE,
                "inertia": constants.SCORE_INERTIA,
                "confidence_gain": constants.CONFIDENCE_INCREASE_RATE,
                "confidence_loss": constants.CONFIDENCE_DECREASE_RATE,
                "agree_within": constants.ALIGNMENT_DISTANCE,
                "conflict_beyond": constants.CONFLICT_DISTANCE,
                "confidence_floor": constants.MIN_CONFIDENCE,
                "confidence_ceiling": constants.MAX_CONFIDENCE,
                "snapshot_hours": SNAPSHOT_MIN_INTERVAL.total_seconds() / 3600,
            },
            "memory": {
                "messages_searched": 1200,
                "related_recalled": 4,
                "recent_recalled": 4,
                "turns_in_context": 16,
                "by_meaning": embedding_service.embeddings_available(),
                "meaning_min_similarity": craft.SEMANTIC_MIN_SIMILARITY,
                "meaning_min_standout": craft.SEMANTIC_MIN_STANDOUT,
            },
            "mirror": {"voice_samples": 12, "max_attempts": 2},
            "confidence": {
                "source_weights": SOURCE_WEIGHTS,
                "tiers": [
                    {"tier": "very_low", "up_to": 20, **controls_for_tier("very_low")},
                    {"tier": "partial", "up_to": 50, **controls_for_tier("partial")},
                    {"tier": "moderate", "up_to": 75, **controls_for_tier("moderate")},
                    {"tier": "high", "up_to": 100, **controls_for_tier("high")},
                ],
            },
            "reflections": {"messages_read": SOURCE_MESSAGE_LIMIT, "min_messages": MIN_MESSAGES_TO_REFLECT, "min_quotes": 2},
            "bootstrap": {"confidence_by_evidence": STRENGTH_CONFIDENCE, "counts_as_messages": STRENGTH_MESSAGE_EQUIVALENT},
            "ai": {
                "provider": provider,
                "reply_model": (os.getenv("GEMINI_MODEL") or llm.DEFAULT_GEMINI_MODEL) if provider == "gemini" else (os.getenv("MISTRAL_MODEL") or llm.DEFAULT_MISTRAL_MODEL) if provider == "mistral" else None,
                "fast_model": llm._fast_model() if provider == "gemini" else None,
                "hedge_seconds": float(os.getenv("GEMINI_HEDGE_SECONDS", llm.DEFAULT_GEMINI_HEDGE_SECONDS)) if provider == "gemini" else None,
            },
        },
        "you": {
            "messages": message_count,
            "conversations": conversation_count,
            "memory": {"by_meaning": remembered_by_meaning, "recallable": recallable},
            "traits": [
                {
                    "key": m.trait_name,
                    "score": round(float(m.score), 3),
                    "confidence": round(float(m.confidence), 3),
                    "evidence_count": int(m.evidence_count or 0),
                }
                for m in sorted(metrics, key=lambda m: constants.TRAIT_LIST.index(m.trait_name) if m.trait_name in constants.TRAIT_LIST else 99)
            ],
            "confidence": confidence,
            "voice_samples_available": len(voice_samples),
            "mirror": {
                "replies_measured": mirror_replies,
                "avg_seconds": round(float(telemetry[1] or 0) / 1000, 1) if mirror_replies else None,
                "fallback_rate": round(float(telemetry[2] or 0) / mirror_replies, 3) if mirror_replies else None,
            },
            "reflections": len(reflections["reflections"]),
        },
    }

