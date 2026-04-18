import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Float, Integer, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import (
    BehavioralInsight,
    Message,
    MirrorLog,
    PersonaSnapshot,
    ScheduleContext,
)
from app.services.confidence_interval_service import build_confidence_explainability

router = APIRouter()
logger = logging.getLogger(__name__)

TIMELINE_RANGE_DAYS = {
    "7d": 7,
    "30d": 30,
    "90d": 90,
}

TRACKED_BEHAVIOR_TRAITS = [
    "communication_style",
    "emotional_expressiveness",
    "decision_framing",
    "reflection_depth",
]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _range_start(range_value: str) -> datetime:
    days = TIMELINE_RANGE_DAYS.get(range_value, 7)
    return _utc_now() - timedelta(days=days)


def _relative_period_label(now: datetime, created_at: datetime) -> str:
    now = _ensure_utc(now) or now
    created_at = _ensure_utc(created_at) or created_at
    delta_days = (now.date() - created_at.date()).days
    if delta_days <= 0:
        return "Today"
    if delta_days == 1:
        return "Yesterday"
    if delta_days < 7:
        return "This week"
    if delta_days < 14:
        return "Last week"
    weeks = max(2, delta_days // 7)
    return f"{weeks} weeks ago"


def _clamp_confidence(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return max(0.0, min(1.0, round(float(value), 3)))


def _trend_from_delta(delta: float, threshold: float = 0.08) -> str:
    if delta > threshold:
        return "up"
    if delta < -threshold:
        return "down"
    return "stable"


def _event_score(event: Dict) -> float:
    confidence = event.get("confidence") or 0.5
    severity = event.get("severity") or 1
    trend_bonus = 0.2 if event.get("trend") in {"up", "down"} else 0.0
    return round((confidence * 0.7) + (severity * 0.2) + trend_bonus, 4)


def _normalize_event(event: Dict, now: datetime) -> Dict:
    created_at = _ensure_utc(event["created_at"])
    if created_at is None:
        created_at = _utc_now()
    return {
        "id": event["id"],
        "period": _relative_period_label(now, created_at),
        "observation": event["observation"],
        "trend": event.get("trend", "stable"),
        "context": event.get("context"),
        "created_at": created_at.isoformat(),
        "source": event.get("source", "unknown"),
        "confidence": _clamp_confidence(event.get("confidence")),
        "tags": event.get("tags", []),
        "severity": int(event.get("severity", 1)),
    }


def _dedupe_and_rank(events: List[Dict], now: datetime, max_items: int = 8) -> List[Dict]:
    ordered = sorted(
        events,
        key=lambda evt: (
            _event_score(evt),
            _ensure_utc(evt["created_at"]) or _utc_now(),
        ),
        reverse=True,
    )

    unique = []
    seen = set()
    for event in ordered:
        dedupe_key = (event["source"], event["observation"].strip().lower())
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        unique.append(_normalize_event(event, now))
        if len(unique) >= max_items:
            break

    unique.sort(key=lambda evt: _ensure_utc(datetime.fromisoformat(evt["created_at"])) or _utc_now(), reverse=True)
    return unique


def _build_overview(events: List[Dict], range_value: str) -> str:
    if not events:
        return "Not enough recent interaction data yet to infer reliable patterns."

    top = events[:3]
    statements = [evt["observation"] for evt in top]
    if len(statements) == 1:
        return f"In the last {range_value}, the clearest pattern is: {statements[0]}."
    if len(statements) == 2:
        return f"In the last {range_value}, two recurring themes stand out: {statements[0]}; {statements[1]}."
    return (
        f"In the last {range_value}, the strongest recurring signals are: "
        f"{statements[0]}; {statements[1]}; and {statements[2]}."
    )


def _extract_trait_score(snapshot: PersonaSnapshot, trait_name: str) -> Optional[float]:
    profile = (snapshot.persona_vector or {}).get("behavioral_profile", {})
    trait_payload = profile.get(trait_name)
    if not isinstance(trait_payload, dict):
        return None
    score = trait_payload.get("score")
    if score is None:
        return None
    try:
        return float(score)
    except (TypeError, ValueError):
        return None


def _trait_display_name(trait_name: str) -> str:
    return trait_name.replace("_", " ")


async def _build_timeline_events(
    db: AsyncSession,
    user_id: UUID,
    start_date: datetime,
    end_date: datetime,
    allowed_sources: Optional[set],
) -> List[Dict]:
    events: List[Dict] = []

    def include_source(source: str) -> bool:
        if not allowed_sources:
            return True
        return source in allowed_sources

    # Source 1: Behavioral insights.
    if include_source("insight"):
        insights_stmt = (
            select(BehavioralInsight)
            .where(
                BehavioralInsight.user_id == user_id,
                BehavioralInsight.created_at >= start_date,
            )
            .order_by(BehavioralInsight.created_at.desc())
            .limit(6)
        )
        insights_result = await db.execute(insights_stmt)
        insights = insights_result.scalars().all()

        for insight in insights:
            text_lower = insight.insight_text.lower()
            trend = "stable"
            if any(token in text_lower for token in ["higher", "increase", "more"]):
                trend = "up"
            elif any(token in text_lower for token in ["lower", "decrease", "less"]):
                trend = "down"

            events.append(
                {
                    "id": f"insight-{insight.id}",
                    "created_at": _ensure_utc(insight.created_at) or _utc_now(),
                    "observation": insight.insight_text,
                    "trend": trend,
                    "context": "Derived from recurring reflection signals.",
                    "source": "insight",
                    "confidence": float(insight.confidence) if insight.confidence is not None else 0.65,
                    "tags": insight.tags or [],
                    "severity": 2,
                }
            )

    # Source 2: Persona trait shift from snapshots (conversation-derived traits).
    if include_source("persona"):
        snapshots_stmt = (
            select(PersonaSnapshot)
            .where(PersonaSnapshot.user_id == user_id)
            .order_by(PersonaSnapshot.created_at.desc())
            .limit(6)
        )
        snapshots_result = await db.execute(snapshots_stmt)
        snapshots = snapshots_result.scalars().all()

        if len(snapshots) >= 2:
            latest = snapshots[0]

            baseline = None
            for candidate in reversed(snapshots):
                candidate_created_at = _ensure_utc(candidate.created_at)
                if candidate_created_at and candidate_created_at <= start_date:
                    baseline = candidate
                    break

            if baseline is None:
                baseline = snapshots[-1]

            for trait_name in TRACKED_BEHAVIOR_TRAITS:
                latest_score = _extract_trait_score(latest, trait_name)
                baseline_score = _extract_trait_score(baseline, trait_name)
                if latest_score is None or baseline_score is None:
                    continue

                delta = latest_score - baseline_score
                trend = _trend_from_delta(delta)
                if trend == "stable":
                    continue

                direction = "increased" if trend == "up" else "decreased"
                display_name = _trait_display_name(trait_name)
                events.append(
                    {
                        "id": f"persona-{trait_name}-{latest.id}",
                        "created_at": _ensure_utc(latest.created_at) or _utc_now(),
                        "observation": f"{display_name.capitalize()} has {direction} versus earlier sessions",
                        "trend": trend,
                        "context": (
                            f"Current score {latest_score:.2f} compared with baseline {baseline_score:.2f}."
                        ),
                        "source": "persona",
                        "confidence": min(0.95, 0.55 + abs(delta)),
                        "tags": [trait_name, "trait-drift"],
                        "severity": 3,
                    }
                )

    # Source 3: Schedule context effect.
    if include_source("schedule"):
        schedule_stmt = select(ScheduleContext).where(ScheduleContext.user_id == user_id)
        schedule_result = await db.execute(schedule_stmt)
        schedule = schedule_result.scalar_one_or_none()

        if schedule:
            first_half_end = start_date + (end_date - start_date) / 2
            first_half_stmt = select(func.avg(Message.reflection_depth)).where(
                Message.user_id == user_id,
                Message.role == "user",
                Message.created_at >= start_date,
                Message.created_at < first_half_end,
                Message.reflection_depth.is_not(None),
            )
            second_half_stmt = select(func.avg(Message.reflection_depth)).where(
                Message.user_id == user_id,
                Message.role == "user",
                Message.created_at >= first_half_end,
                Message.created_at <= end_date,
                Message.reflection_depth.is_not(None),
            )

            first_half_result = await db.execute(first_half_stmt)
            second_half_result = await db.execute(second_half_stmt)
            first_depth = first_half_result.scalar_one_or_none()
            second_depth = second_half_result.scalar_one_or_none()

            if schedule.stress_level >= 0.7 and first_depth is not None and second_depth is not None:
                delta = float(second_depth) - float(first_depth)
                trend = _trend_from_delta(delta, threshold=0.05)
                if trend != "stable":
                    context_line = (
                        "High stress context appears to coincide with deeper reflection."
                        if trend == "up"
                        else "High stress context appears to coincide with shallower reflection."
                    )
                    events.append(
                        {
                            "id": f"schedule-stress-{schedule.user_id}",
                            "created_at": _ensure_utc(schedule.updated_at) or _utc_now(),
                            "observation": "Reflection depth shifted during elevated stress periods",
                            "trend": trend,
                            "context": context_line,
                            "source": "schedule",
                            "confidence": 0.7,
                            "tags": ["stress", "workload", "schedule-context"],
                            "severity": 2,
                        }
                    )

            if schedule.is_exam_period or schedule.has_deadlines:
                events.append(
                    {
                        "id": f"schedule-workload-{schedule.user_id}",
                        "created_at": _ensure_utc(schedule.updated_at) or _utc_now(),
                        "observation": "Workload calendar indicates active pressure windows",
                        "trend": "up",
                        "context": "Deadlines or exam period can amplify hesitation and shorter responses.",
                        "source": "schedule",
                        "confidence": 0.6,
                        "tags": ["deadlines", "exam-period", "workload"],
                        "severity": 1,
                    }
                )

    # Source 4: Mirror observability trends.
    if include_source("mirror"):
        midpoint = start_date + (end_date - start_date) / 2

        mirror_first_stmt = select(
            func.avg(cast(MirrorLog.realism_score, Float)),
            func.sum(cast(MirrorLog.fallback_triggered, Integer)),
            func.count(MirrorLog.id),
        ).where(
            MirrorLog.user_id == user_id,
            MirrorLog.created_at >= start_date,
            MirrorLog.created_at < midpoint,
        )
        mirror_second_stmt = select(
            func.avg(cast(MirrorLog.realism_score, Float)),
            func.sum(cast(MirrorLog.fallback_triggered, Integer)),
            func.count(MirrorLog.id),
        ).where(
            MirrorLog.user_id == user_id,
            MirrorLog.created_at >= midpoint,
            MirrorLog.created_at <= end_date,
        )

        first_result = await db.execute(mirror_first_stmt)
        second_result = await db.execute(mirror_second_stmt)
        first_avg, first_fallbacks, first_count = first_result.one()
        second_avg, second_fallbacks, second_count = second_result.one()

        if first_count and second_count and first_avg is not None and second_avg is not None:
            realism_delta = float(second_avg) - float(first_avg)
            trend = _trend_from_delta(realism_delta, threshold=0.04)
            if trend != "stable":
                events.append(
                    {
                        "id": f"mirror-reliability-{user_id}",
                        "created_at": _ensure_utc(end_date) or _utc_now(),
                        "observation": "Mirror response consistency changed across recent sessions",
                        "trend": trend,
                        "context": (
                            f"Realism score shifted from {float(first_avg):.2f} to {float(second_avg):.2f}."
                        ),
                        "source": "mirror",
                        "confidence": 0.65,
                        "tags": ["mirror", "realism"],
                        "severity": 1,
                    }
                )

            first_fallback_rate = float(first_fallbacks or 0.0) / max(first_count, 1)
            second_fallback_rate = float(second_fallbacks or 0.0) / max(second_count, 1)
            fallback_delta = second_fallback_rate - first_fallback_rate
            fallback_trend = _trend_from_delta(-fallback_delta, threshold=0.1)
            if abs(fallback_delta) >= 0.1:
                events.append(
                    {
                        "id": f"mirror-fallback-{user_id}",
                        "created_at": _ensure_utc(end_date) or _utc_now(),
                        "observation": "Mirror fallback frequency shifted",
                        "trend": fallback_trend,
                        "context": (
                            f"Fallback rate moved from {first_fallback_rate:.0%} to {second_fallback_rate:.0%}."
                        ),
                        "source": "mirror",
                        "confidence": 0.6,
                        "tags": ["mirror", "fallback"],
                        "severity": 1,
                    }
                )

    return events

@router.get("/metrics/{user_id}")
async def get_behavioral_metrics(
    user_id: UUID,
    view: str = Query("week", description="Timeframe view: day, week, month"),
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
    else: # default week
        start_date = now - timedelta(days=7)
        trunc_period = "day"
        
    date_trunc_expr = func.date_trunc(trunc_period, Message.created_at)

    stmt = select(
        date_trunc_expr.label("period"),
        func.count(Message.id).label("message_count"),
        func.sum(Message.token_count).label("total_tokens"),
        func.avg(Message.emotional_intensity).label("avg_emotional_intensity"),
        func.avg(Message.reflection_depth).label("avg_reflection_depth"),
        func.avg(Message.response_delay_ms).label("avg_delay_ms"),
    ).where(
        Message.user_id == user_id,
        Message.role == "user",
        Message.created_at >= start_date
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
        "start_date": start_date.isoformat(),
        "totals": totals,
        "timeline": data,
    }

@router.get("/reflections/{user_id}")
async def get_user_reflections(
    user_id: UUID,
    range: str = Query("30d", description="Timeframe range: 1d, 2d, 3d, 7d, 30d, 90d"),
    db: AsyncSession = Depends(get_db)
):
    """
    Fetch behavioral insights/reflections for a user within a specific time range.
    """
    now = _utc_now()
    
    if range == "1d":
        start_date = now - timedelta(days=1)
    elif range == "2d":
        start_date = now - timedelta(days=2)
    elif range == "3d":
        start_date = now - timedelta(days=3)
    elif range == "7d":
        start_date = now - timedelta(days=7)
    elif range == "90d":
        start_date = now - timedelta(days=90)
    else: # Default 30d
        start_date = now - timedelta(days=30)
        
    stmt = select(BehavioralInsight).where(
        BehavioralInsight.user_id == user_id,
        BehavioralInsight.created_at >= start_date
    ).order_by(BehavioralInsight.created_at.desc())
    
    result = await db.execute(stmt)
    insights = result.scalars().all()
    
    return [
        {
            "id": str(insight.id),
            "text": insight.insight_text,
            "tags": insight.tags,
            "confidence": float(insight.confidence) if insight.confidence else None,
            "created_at": insight.created_at.isoformat()
        }
        for insight in insights
    ]

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


@router.get("/timeline/{user_id}")
async def get_timeline_patterns(
    user_id: UUID,
    range: str = Query("7d", description="Timeframe range: 7d, 30d, 90d"),
    sources: Optional[List[str]] = Query(
        None,
        description="Optional source filter: insight, persona, schedule, mirror",
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate deterministic timeline events from conversations, persona, schedule,
    behavioral insights, and mirror observability data.
    """
    normalized_range = range if range in TIMELINE_RANGE_DAYS else "7d"
    end_date = _utc_now()
    start_date = _range_start(normalized_range)

    allowed_sources = None
    if sources:
        valid_sources = {"insight", "persona", "schedule", "mirror"}
        allowed_sources = {source for source in sources if source in valid_sources}

    try:
        raw_events = await _build_timeline_events(
            db=db,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            allowed_sources=allowed_sources,
        )
    except Exception as exc:
        logger.exception("Timeline generation failed for user %s: %s", user_id, exc)
        raw_events = []

    ranked_events = _dedupe_and_rank(raw_events, end_date, max_items=8)
    overview = _build_overview(ranked_events, normalized_range)

    return {
        "range": normalized_range,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "overview": overview,
        "events": ranked_events,
    }


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