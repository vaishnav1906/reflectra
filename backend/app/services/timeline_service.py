"""Timeline: what the user actually talked about, day by day, and how the persona moved.

Everything here is computed from stored rows (conversations, messages, persona snapshots),
so every number on the Timeline page can be traced back to data:
  - days:      conversations held, message count, mood and depth of that day, one highlight
  - traits:    daily trait scores from persona snapshots
  - milestones: first conversation, busiest day, longest streak, trait shifts, imports
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import TRAIT_LIST
from app.db.models import BehavioralInsight, Conversation, ExternalInput, Message, PersonaSnapshot
from app.services.message_signals import compute_message_metrics, sentiment_counts

MIN_MOOD_WORDS = 3  # fewer feeling-words than this in a day is too little to call a mood

MAX_MESSAGES = 6000
TRAIT_LABELS = {
    "communication_style": ("concise", "elaborate"),
    "emotional_expressiveness": ("reserved", "open"),
    "decision_framing": ("hesitant", "decisive"),
    "reflection_depth": ("surface-level", "deep"),
}


def _local(dt: datetime, offset: timedelta) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc) + offset


def _longest_streak(days: List[date]) -> int:
    best = run = 0
    previous: Optional[date] = None
    for day in sorted(set(days)):
        run = run + 1 if previous is not None and day - previous == timedelta(days=1) else 1
        best = max(best, run)
        previous = day
    return best


def _trait_score(snapshot: PersonaSnapshot, trait: str) -> Optional[float]:
    profile = (snapshot.persona_vector or {}).get("behavioral_profile", {})
    value = profile.get(trait)
    if isinstance(value, dict) and value.get("score") is not None:
        try:
            return float(value["score"])
        except (TypeError, ValueError):
            return None
    return None


def _side(score: Optional[float]) -> int:
    if score is None:
        return 0
    return 1 if score >= 0.62 else -1 if score <= 0.38 else 0


def trait_milestones(series: List[Dict[str, object]]) -> List[Dict[str, object]]:
    """When each trait settled on the side it is still on today.

    Early readings swing while confidence is low, so a trait only gets a milestone
    if it currently sits clearly on one side, dated from when it last moved there.
    """
    milestones = []
    for trait in TRAIT_LIST:
        points = [(p["date"], p.get(trait)) for p in series if p.get(trait) is not None]
        if len(points) < 2:
            continue
        final_side = _side(points[-1][1])
        if final_side == 0:
            continue
        settled_index = len(points) - 1
        while settled_index > 0 and _side(points[settled_index - 1][1]) == final_side:
            settled_index -= 1
        low_label, high_label = TRAIT_LABELS[trait]
        milestones.append(
            {
                "date": points[settled_index][0],
                "kind": "trait",
                "text": (
                    f"Your {trait.replace('_', ' ')} settled on the "
                    f"{high_label if final_side > 0 else low_label} side and has stayed there "
                    f"(now {round(float(points[-1][1]) * 100)}/100)."
                ),
            }
        )
    return milestones


async def build_timeline(
    db: AsyncSession,
    user_id: UUID,
    range_days: Optional[int] = None,
    tz_offset_minutes: int = 0,
) -> Dict[str, object]:
    offset = timedelta(minutes=max(-840, min(840, tz_offset_minutes)))
    since = datetime.now(timezone.utc) - timedelta(days=range_days) if range_days else None

    message_stmt = select(
        Message.content,
        Message.created_at,
        Message.conversation_id,
        Message.emotional_intensity,
        Message.reflection_depth,
    ).where(Message.user_id == user_id, Message.role == "user")
    if since is not None:
        message_stmt = message_stmt.where(Message.created_at >= since)
    messages = (await db.execute(message_stmt.order_by(Message.created_at.asc()).limit(MAX_MESSAGES))).all()

    conversations = {
        row.id: row
        for row in (
            await db.execute(
                select(Conversation.id, Conversation.title, Conversation.mode).where(Conversation.user_id == user_id)
            )
        ).all()
    }

    by_day: Dict[date, Dict[str, object]] = defaultdict(
lambda: {"messages": 0, "positive": 0, "negative": 0, "depths": [], "conversations": defaultdict(int), "best": (-1.0, "")}
    )
    for content, created_at, conversation_id, emotional_intensity, reflection_depth in messages:
        day = _local(created_at, offset).date()
        bucket = by_day[day]
        bucket["messages"] += 1
        bucket["conversations"][conversation_id] += 1

        text = content or ""
        positive, negative = sentiment_counts(text)
        bucket["positive"] += positive
        bucket["negative"] += negative
        depth = reflection_depth
        if depth is None:
            depth = compute_message_metrics(text)["reflection_depth"]  # older rows predate stored metrics
        words = len(text.split())
        if words >= 4:
            bucket["depths"].append(float(depth))
        # Highlight: the most reflective, substantial thing they said that day.
        weight = float(depth) + min(words, 40) / 80.0
        if words >= 6 and weight > bucket["best"][0]:
            bucket["best"] = (weight, " ".join(text.split())[:220])

    days = []
    for day in sorted(by_day, reverse=True):
        bucket = by_day[day]
        depths = bucket["depths"]
        feeling_words = bucket["positive"] + bucket["negative"]
        mood = (
            round((bucket["positive"] - bucket["negative"]) / feeling_words, 2)
            if feeling_words >= MIN_MOOD_WORDS
            else None
        )
        day_conversations = sorted(bucket["conversations"].items(), key=lambda item: item[1], reverse=True)
        days.append(
            {
                "date": day.isoformat(),
                "user_messages": bucket["messages"],
                "mood": mood,  # -1 (all negative feeling-words) .. +1 (all positive); None = too few to say
                "depth": round(sum(depths) / len(depths), 2) if depths else None,
                "highlight": bucket["best"][1] or None,
                "conversations": [
                    {
                        "id": str(conversation_id),
                        "title": (conversations[conversation_id].title if conversation_id in conversations else None)
                        or "Untitled conversation",
                        "mode": conversations[conversation_id].mode if conversation_id in conversations else "reflection",
                        "user_messages": count,
                    }
                    for conversation_id, count in day_conversations[:6]
                ],
            }
        )

    # Trait series: the last snapshot of each day.
    snapshot_stmt = select(PersonaSnapshot).where(
        PersonaSnapshot.user_id == user_id, PersonaSnapshot.is_historical_anchor.is_(False)
    )
    if since is not None:
        snapshot_stmt = snapshot_stmt.where(PersonaSnapshot.created_at >= since)
    snapshots = (await db.execute(snapshot_stmt.order_by(PersonaSnapshot.created_at.asc()))).scalars().all()
    last_of_day: Dict[date, PersonaSnapshot] = {}
    for snapshot in snapshots:
        last_of_day[_local(snapshot.created_at, offset).date()] = snapshot
    trait_series = []
    for day in sorted(last_of_day):
        snapshot = last_of_day[day]
        point: Dict[str, object] = {"date": day.isoformat(), "stability": snapshot.stability_index}
        has_any = False
        for trait in TRAIT_LIST:
            score = _trait_score(snapshot, trait)
            point[trait] = score
            has_any = has_any or score is not None
        if has_any:
            trait_series.append(point)

    # Summary numbers.
    active_days = sorted(by_day)
    total_messages = sum(int(by_day[d]["messages"]) for d in active_days)
    busiest = max(active_days, key=lambda d: by_day[d]["messages"], default=None)
    conversation_ids = {cid for d in active_days for cid in by_day[d]["conversations"]}
    mode_counts: Dict[str, int] = defaultdict(int)
    for cid in conversation_ids:
        mode_counts[conversations[cid].mode if cid in conversations else "reflection"] += 1

    summary = {
        "first_date": active_days[0].isoformat() if active_days else None,
        "last_date": active_days[-1].isoformat() if active_days else None,
        "active_days": len(active_days),
        "user_messages": total_messages,
        "conversations": len(conversation_ids),
        "longest_streak": _longest_streak(active_days),
        "busiest_day": {"date": busiest.isoformat(), "user_messages": by_day[busiest]["messages"]} if busiest else None,
        "avg_messages_per_active_day": round(total_messages / len(active_days), 1) if active_days else 0,
        "conversations_by_mode": dict(mode_counts),
    }

    # Milestones.
    milestones: List[Dict[str, object]] = []
    if active_days:
        milestones.append({"date": active_days[0].isoformat(), "kind": "start", "text": "Your first conversation in this period."})
    if busiest and by_day[busiest]["messages"] >= 10:
        milestones.append(
            {
                "date": busiest.isoformat(),
                "kind": "activity",
                "text": f"Your most talkative day: {by_day[busiest]['messages']} messages.",
            }
        )
    milestones.extend(trait_milestones(trait_series))

    import_stmt = select(ExternalInput.created_at).where(
        ExternalInput.user_id == user_id, ExternalInput.source == "persona_bootstrap"
    )
    reflection_stmt = select(BehavioralInsight.created_at).where(
        BehavioralInsight.user_id == user_id, BehavioralInsight.kind.in_(["reflection", "reflection_archive"])
    )
    if since is not None:
        import_stmt = import_stmt.where(ExternalInput.created_at >= since)
        reflection_stmt = reflection_stmt.where(BehavioralInsight.created_at >= since)
    for created_at in (await db.execute(import_stmt)).scalars().all():
        milestones.append({"date": _local(created_at, offset).date().isoformat(), "kind": "import", "text": "You imported a persona description."})
    reflection_days = {_local(created_at, offset).date() for created_at in (await db.execute(reflection_stmt)).scalars().all()}
    for day in sorted(reflection_days):
        milestones.append({"date": day.isoformat(), "kind": "reflection", "text": "Reflectra wrote new reflections about you."})

    milestones.sort(key=lambda m: m["date"], reverse=True)
    return {
        "range_days": range_days,
        "summary": summary,
        "days": days,
        "trait_series": trait_series,
        "milestones": milestones,
    }
