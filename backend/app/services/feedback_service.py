"""Letting the user correct Reflectra, and making the corrections count.

Three things can be rated, and each rating changes behaviour:

  reply       up / down, with optional reasons ("too long", "doesn't sound like me").
              Recent reasons become instructions for the next replies; Mirror replies
              rated up become examples of the user's voice.
  trait       "Is this you?" agree, or disagree with where they'd put themselves.
              Agreeing makes Reflectra more sure. Disagreeing moves the trait toward
              their own rating, weighted like SELF_RATING_MESSAGES of their messages,
              and makes it less sure, so what they say in chat still decides.
  reflection  "Spot on" raises its confidence; "not really" hides it and tells the next
              rewrite not to say it again (with their note on what was off).

All of it is also counted, which is the only real measure of whether Reflectra is
reading people right (shown on How it works).
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import MAX_CONFIDENCE, MIN_CONFIDENCE, TRAIT_LIST
from app.db.models import BehavioralInsight, Conversation, Feedback, Message, UserPersonaMetric

REPLY, TRAIT, REFLECTION = "reply", "trait", "reflection"

# A person's view of themselves is evidence, not the truth: worth about this many messages.
SELF_RATING_MESSAGES = 15
AGREE_CONFIDENCE_GAIN = 0.15  # share of the remaining doubt removed by "yes, that's me"
AGREEMENT_BAND = 0.15  # a self-rating this close to the reading counts as agreeing
REFLECTION_CONFIRM_GAIN = 0.1
REFLECTION_CONFIRM_CEILING = 0.95
REJECTED_REFLECTION = "reflection_rejected"

GUIDANCE_WINDOW = timedelta(days=30)
GUIDANCE_LOOKBACK = 12  # most recent rated replies considered
MAX_APPROVED_EXAMPLES = 3

# Reasons the user can give for a reply that missed, and what the next replies are told.
REPLY_REASONS: Dict[str, Dict[str, str]] = {
    "too_long": {"label": "Too long", "line": "Keep replies shorter than you'd think: they've said recent ones ran long."},
    "missed_point": {"label": "Missed the point", "line": "Answer exactly what they said; they felt recent replies missed the point."},
    "wrong_about_me": {
        "label": "Got me wrong",
        "line": "Don't assume things about them or their situation; recent replies got them wrong.",
    },
    "too_preachy": {
        "label": "Too preachy",
        "line": "No advice or lessons unless they ask; they found recent replies preachy.",
    },
    "unrelated": {
        "label": "Brought up old stuff",
        "line": "Leave earlier topics out unless they raise them; they didn't like old things being dragged in.",
    },
    "not_my_voice": {
        "label": "Doesn't sound like me",
        "line": "Recent replies didn't sound like them: copy the real samples more closely, and drop phrases they never use.",
    },
}
REASONS_BY_MODE = {
    "reflection": ["too_long", "missed_point", "wrong_about_me", "too_preachy", "unrelated"],
    "mirror": ["not_my_voice", "too_long", "missed_point", "wrong_about_me", "unrelated"],
}


class FeedbackError(ValueError):
    """Bad input; the message is safe to show."""


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


# --------------------------------------------------------------------------- pure rules


def apply_trait_agreement(score: float, confidence: float) -> Tuple[float, float]:
    """'Yes, that's me': same reading, a good deal more sure."""
    return score, _clamp(confidence + AGREE_CONFIDENCE_GAIN * (1.0 - confidence), MIN_CONFIDENCE, MAX_CONFIDENCE)


def apply_self_rating(score: float, confidence: float, evidence_count: int, self_score: float) -> Tuple[float, float]:
    """'Not quite, I'm more like here': move toward their view and become less sure.

    Their rating counts like SELF_RATING_MESSAGES messages, so with little evidence it
    mostly decides, and after hundreds of messages it nudges. Confidence drops in
    proportion to how far off the reading was; a rating within the agreement band is
    treated as agreeing.
    """
    self_score = _clamp(self_score)
    distance = abs(self_score - score)
    if distance <= AGREEMENT_BAND:
        share = SELF_RATING_MESSAGES / (max(0, evidence_count) + SELF_RATING_MESSAGES)
        _, gained = apply_trait_agreement(score, confidence)
        return _clamp(score + (self_score - score) * share), gained
    share = SELF_RATING_MESSAGES / (max(0, evidence_count) + SELF_RATING_MESSAGES)
    new_score = score + (self_score - score) * share
    new_confidence = confidence * (1.0 - min(0.6, distance))
    return _clamp(new_score), _clamp(new_confidence, MIN_CONFIDENCE, MAX_CONFIDENCE)


def guidance_from_reasons(reason_lists: Iterable[Sequence[str]], mode: str) -> List[str]:
    """Instruction lines for the next replies, most-mentioned first (at most 3)."""
    allowed = set(REASONS_BY_MODE.get(mode, REASONS_BY_MODE["reflection"]))
    counts = Counter(reason for reasons in reason_lists for reason in (reasons or []) if reason in allowed)
    return [REPLY_REASONS[reason]["line"] for reason, _ in counts.most_common(3)]


def clean_reasons(reasons: Optional[Sequence[str]], mode: str) -> List[str]:
    allowed = REASONS_BY_MODE.get(mode, REASONS_BY_MODE["reflection"])
    return [r for r in allowed if r in set(reasons or [])]


# --------------------------------------------------------------------------- storage


async def _existing(db: AsyncSession, user_id: UUID, target_type: str, target_id: str) -> Optional[Feedback]:
    return (
        await db.execute(
            select(Feedback).where(
                Feedback.user_id == user_id, Feedback.target_type == target_type, Feedback.target_id == target_id
            )
        )
    ).scalar_one_or_none()


async def _save(
    db: AsyncSession,
    user_id: UUID,
    target_type: str,
    target_id: str,
    verdict: str,
    *,
    reasons: Optional[List[str]] = None,
    note: Optional[str] = None,
    value: Optional[float] = None,
    details: Optional[Dict[str, object]] = None,
) -> Feedback:
    row = await _existing(db, user_id, target_type, target_id)
    if row is None:
        row = Feedback(user_id=user_id, target_type=target_type, target_id=target_id)
        db.add(row)
    row.verdict = verdict
    row.reasons = list(reasons or [])
    row.note = (note or "").strip()[:500] or None
    row.value = value
    row.details = {**(row.details or {}), **(details or {})}
    row.updated_at = datetime.now(timezone.utc)
    return row


# --------------------------------------------------------------------------- replies


async def rate_reply(
    db: AsyncSession, user_id: UUID, message_id: UUID, verdict: str, reasons: Optional[Sequence[str]] = None
) -> Dict[str, object]:
    if verdict not in ("up", "down", "clear"):
        raise FeedbackError("verdict must be up, down or clear")
    found = (
        await db.execute(
            select(Message, Conversation.mode)
            .join(Conversation, Conversation.id == Message.conversation_id)
            .where(Message.id == message_id, Message.user_id == user_id)
        )
    ).first()
    if found is None or found[0].role != "assistant":
        raise FeedbackError("That reply doesn't exist.")
    message, mode = found
    mode = "mirror" if mode in ("mirror", "assistant") else "reflection"
    if verdict == "clear":
        row = await _existing(db, user_id, REPLY, str(message_id))
        if row is not None:
            await db.delete(row)
        await db.commit()
        return {"message_id": str(message_id), "verdict": None, "reasons": []}
    kept = clean_reasons(reasons, mode) if verdict == "down" else []
    await _save(
        db,
        user_id,
        REPLY,
        str(message_id),
        verdict,
        reasons=kept,
        details={"mode": mode, "conversation_id": str(message.conversation_id), "text": (message.content or "")[:400]},
    )
    await db.commit()
    return {"message_id": str(message_id), "verdict": verdict, "reasons": kept}


async def reply_verdicts(db: AsyncSession, user_id: UUID, message_ids: Sequence[UUID]) -> Dict[str, Dict[str, object]]:
    ids = [str(m) for m in message_ids]
    if not ids:
        return {}
    rows = (
        await db.execute(
            select(Feedback.target_id, Feedback.verdict, Feedback.reasons).where(
                Feedback.user_id == user_id, Feedback.target_type == REPLY, Feedback.target_id.in_(ids)
            )
        )
    ).all()
    return {target: {"verdict": verdict, "reasons": list(reasons or [])} for target, verdict, reasons in rows}


async def reply_guidance(db: AsyncSession, user_id: UUID, mode: str) -> List[str]:
    """What recent thumbs-down reasons say the next replies should do differently."""
    since = datetime.now(timezone.utc) - GUIDANCE_WINDOW
    try:
        rows = (
            await db.execute(
                select(Feedback.verdict, Feedback.reasons, Feedback.details)
                .where(Feedback.user_id == user_id, Feedback.target_type == REPLY, Feedback.updated_at >= since)
                .order_by(Feedback.updated_at.desc())
                .limit(GUIDANCE_LOOKBACK * 2)
            )
        ).all()
    except Exception:
        await db.rollback()
        return []
    same_mode = [r for r in rows if (r[2] or {}).get("mode", "reflection") == mode][:GUIDANCE_LOOKBACK]
    return guidance_from_reasons((reasons for verdict, reasons, _ in same_mode if verdict == "down"), mode)


async def approved_mirror_replies(db: AsyncSession, user_id: UUID, limit: int = MAX_APPROVED_EXAMPLES) -> List[str]:
    """Mirror replies the user rated up: they said these sound like them."""
    try:
        rows = (
            await db.execute(
                select(Feedback.details)
                .where(Feedback.user_id == user_id, Feedback.target_type == REPLY, Feedback.verdict == "up")
                .order_by(Feedback.updated_at.desc())
                .limit(limit * 3)
            )
        ).scalars().all()
    except Exception:
        await db.rollback()
        return []
    texts = [str(d.get("text")) for d in rows if isinstance(d, dict) and d.get("mode") == "mirror" and d.get("text")]
    return texts[:limit]


# --------------------------------------------------------------------------- traits


async def rate_trait(
    db: AsyncSession,
    user_id: UUID,
    trait: str,
    verdict: str,
    self_score: Optional[float] = None,
    dry_run: bool = False,
) -> Dict[str, object]:
    if trait not in TRAIT_LIST:
        raise FeedbackError("Unknown trait.")
    if verdict not in ("agree", "disagree"):
        raise FeedbackError("verdict must be agree or disagree")
    if verdict == "disagree" and self_score is None:
        raise FeedbackError("Say where you'd put yourself.")
    metric = (
        await db.execute(
            select(UserPersonaMetric).where(UserPersonaMetric.user_id == user_id, UserPersonaMetric.trait_name == trait)
        )
    ).scalar_one_or_none()
    if metric is None or not metric.evidence_count:
        raise FeedbackError("Reflectra hasn't read this trait yet. Chat a little first.")

    before_score, before_conf = float(metric.score), float(metric.confidence)
    previous = await _existing(db, user_id, TRAIT, trait)
    recently_agreed = (
        previous is not None
        and previous.verdict == "agree"
        and previous.updated_at is not None
        and datetime.now(timezone.utc) - previous.updated_at < timedelta(days=1)
    )
    if verdict == "agree":
        # Saying yes again the same day doesn't make it twice as sure.
        new_score, new_conf = (before_score, before_conf) if recently_agreed else apply_trait_agreement(before_score, before_conf)
    else:
        new_score, new_conf = apply_self_rating(before_score, before_conf, int(metric.evidence_count), float(self_score))

    result = {
        "trait": trait,
        "verdict": verdict,
        "self_score": None if self_score is None else round(_clamp(self_score), 3),
        "previous_score": round(before_score, 3),
        "previous_confidence": round(before_conf, 3),
        "new_score": round(new_score, 3),
        "new_confidence": round(new_conf, 3),
        "counts_as_messages": SELF_RATING_MESSAGES,
        "saved": False,
    }
    if dry_run:
        return result

    metric.score = new_score
    metric.confidence = new_conf
    metric.last_updated = datetime.now(timezone.utc)
    await _save(
        db,
        user_id,
        TRAIT,
        trait,
        verdict,
        value=None if self_score is None else _clamp(self_score),
        details={"before": [before_score, before_conf], "after": [new_score, new_conf]},
    )
    await db.commit()
    result["saved"] = True
    return result


async def trait_verdicts(db: AsyncSession, user_id: UUID) -> Dict[str, Dict[str, object]]:
    rows = (
        await db.execute(
            select(Feedback).where(Feedback.user_id == user_id, Feedback.target_type == TRAIT)
        )
    ).scalars().all()
    return {
        row.target_id: {
            "verdict": row.verdict,
            "self_score": row.value,
            "on": row.updated_at.isoformat() if row.updated_at else None,
        }
        for row in rows
    }


# --------------------------------------------------------------------------- reflections


async def rate_reflection(
    db: AsyncSession, user_id: UUID, reflection_id: UUID, verdict: str, note: Optional[str] = None
) -> Dict[str, object]:
    if verdict not in ("agree", "disagree"):
        raise FeedbackError("verdict must be agree or disagree")
    row = (
        await db.execute(
            select(BehavioralInsight).where(
                BehavioralInsight.id == reflection_id,
                BehavioralInsight.user_id == user_id,
                BehavioralInsight.kind.in_(["reflection", "reflection_archive", REJECTED_REFLECTION]),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise FeedbackError("That reflection no longer exists.")

    previous = await _existing(db, user_id, REFLECTION, str(reflection_id))
    details: Dict[str, object] = {"title": row.title, "insight": (row.insight_text or "")[:400]}
    if verdict == "agree":
        if previous is None or previous.verdict != "agree":
            row.confidence = min(REFLECTION_CONFIRM_CEILING, float(row.confidence or 0.6) + REFLECTION_CONFIRM_GAIN)
        if row.kind == REJECTED_REFLECTION:
            row.kind = (previous.details or {}).get("kind_before", "reflection") if previous else "reflection"
    else:
        details["kind_before"] = row.kind if row.kind != REJECTED_REFLECTION else (previous.details or {}).get("kind_before", "reflection") if previous else "reflection"
        row.kind = REJECTED_REFLECTION
    await _save(db, user_id, REFLECTION, str(reflection_id), verdict, note=note, details=details)
    await db.commit()
    return {"reflection_id": str(reflection_id), "verdict": verdict}


async def reflection_verdicts(db: AsyncSession, user_id: UUID) -> Dict[str, str]:
    rows = (
        await db.execute(
            select(Feedback.target_id, Feedback.verdict).where(
                Feedback.user_id == user_id, Feedback.target_type == REFLECTION
            )
        )
    ).all()
    return {target: verdict for target, verdict in rows}


async def reflection_guidance(db: AsyncSession, user_id: UUID) -> Dict[str, List[str]]:
    """Titles the user confirmed, and ones they said were wrong (with what was off)."""
    rows = (
        await db.execute(
            select(Feedback.verdict, Feedback.note, Feedback.details)
            .where(Feedback.user_id == user_id, Feedback.target_type == REFLECTION)
            .order_by(Feedback.updated_at.desc())
            .limit(30)
        )
    ).all()
    confirmed, rejected = [], []
    for verdict, note, details in rows:
        title = str((details or {}).get("title") or "").strip()
        if not title:
            continue
        if verdict == "agree":
            confirmed.append(title)
        else:
            rejected.append(f'"{title}"' + (f" (they said: {note})" if note else ""))
    return {"confirmed": confirmed[:8], "rejected": rejected[:12]}


# --------------------------------------------------------------------------- summary


async def summary(db: AsyncSession, user_id: UUID) -> Dict[str, object]:
    rows = (
        await db.execute(
            select(Feedback.target_type, Feedback.verdict, Feedback.reasons, Feedback.details).where(
                Feedback.user_id == user_id
            )
        )
    ).all()
    replies = {"reflection": {"up": 0, "down": 0}, "mirror": {"up": 0, "down": 0}}
    reasons: Counter = Counter()
    traits = {"agree": 0, "disagree": 0}
    reflections = {"agree": 0, "disagree": 0}
    for target_type, verdict, why, details in rows:
        if target_type == REPLY and verdict in ("up", "down"):
            mode = (details or {}).get("mode", "reflection")
            replies.setdefault(mode, {"up": 0, "down": 0})[verdict] += 1
            reasons.update(why or [])
        elif target_type == TRAIT and verdict in traits:
            traits[verdict] += 1
        elif target_type == REFLECTION and verdict in reflections:
            reflections[verdict] += 1
    return {
        "replies": replies,
        "reasons": [{"reason": r, "label": REPLY_REASONS[r]["label"], "count": c} for r, c in reasons.most_common() if r in REPLY_REASONS],
        "traits": traits,
        "reflections": reflections,
    }
