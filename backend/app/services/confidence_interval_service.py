"""How sure Reflectra is that it knows someone.

One overall confidence (0-1), a range around it, and the level that range puts the
user in. Mirror mode acts on the cautious end of the range.

Four kinds of evidence go in. Each is a plain, checkable quantity:

  traits         How settled the four trait readings are: the average of the
                 per-trait confidences, which rise when new messages agree with the
                 current reading and fall when they contradict it.
  conversations  How much the user has said (depth), over how many separate days
                 (breadth), and how long ago they last spoke (freshness).
  voice          How many usable samples of their writing exist for Mirror to copy.
                 Imported real texts count for half.
  reflections    Patterns that survived quote verification, by their confidence.

Rules the numbers must obey (tests/backend/test_confidence_logic.py):
  - more evidence never lowers confidence; an import never lowers it either,
    because imports only reach confidence through the traits and voice they add to;
  - a source with nothing in it is left out, not counted as zero, but its absence
    widens the range;
  - the range is wide when there is little to go on or when the sources disagree,
    and narrows as messages accumulate.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence
from uuid import UUID

from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BehavioralInsight, ExternalInput, Message, UserPersonaMetric

SOURCE_WEIGHTS: Dict[str, float] = {
    "traits": 0.40,
    "conversations": 0.25,
    "voice": 0.20,
    "reflections": 0.15,
}

# conversations
DEPTH_MESSAGES = 50.0  # 50 messages -> 63% of full depth, 150 -> 95%
BREADTH_DAYS = 6.0  # 6 separate days -> 63% of full breadth, 18 -> 95%
ONE_DAY_WORTH = 0.4  # everything said in a single day counts 40%: one mood is not a person
FRESH_FOR_DAYS = 30  # no decay for a month
STALE_HALF_LIFE_DAYS = 180.0  # after that, what it knows loses half its weight every 6 months

# voice
VOICE_MESSAGES = 25.0  # 25 usable messages -> 63%, 75 -> 95%
VOICE_MIN_CHARS = 12  # shorter than this ("ok", "lol") says little about how someone writes
IMPORTED_TEXT_WORTH = 0.5  # texts written elsewhere count half: different audience, older habits
VOICE_IMPORT_SOURCE = "voice_import"

# reflections
REFLECTIONS_FULL_SET = 3

# range
MIN_HALF_WIDTH = 0.03
MAX_HALF_WIDTH = 0.25
THIN_EVIDENCE_WIDTH = 0.12  # extra half-width with no messages at all...
THIN_EVIDENCE_MESSAGES = 40.0  # ...fading as messages accumulate
DISAGREEMENT_WIDTH = 0.35  # times the spread between the sources
MISSING_SOURCE_WIDTH = 0.10  # times the share of weight that has no data

TIER_BOUNDS = (("very_low", 20), ("partial", 50), ("moderate", 75), ("high", 100))


@dataclass
class ConfidenceIntervalResult:
    center: float
    lower: float
    upper: float
    tier: str
    source_scores: Dict[str, float]
    source_weights: Dict[str, float]
    phrase_usage_frequency: float
    tone_strength: float
    reaction_accuracy_threshold: float
    style_enforcement_intensity: float
    include_uncertainty_note: bool
    source_contributions: Dict[str, float]
    facts: Dict[str, float] = field(default_factory=dict)
    # Kept so stored Mirror telemetry keeps its shape; nothing overrides anything any more.
    timeline_recency_override: Dict[str, float | bool] = field(default_factory=dict)


# --------------------------------------------------------------------------- pure scoring


def _saturate(amount: float, scale: float) -> float:
    """0 at nothing, 63% at `scale`, 95% at three times `scale`, never quite 1."""
    return 1.0 - math.exp(-max(0.0, float(amount)) / scale)


def score_traits(confidences: Sequence[float], evidence_total: int) -> Optional[float]:
    """Average per-trait confidence. None until at least one message has been read for traits."""
    values = [float(c) for c in confidences if c is not None]
    if not values or evidence_total <= 0:
        return None
    return _clamp(sum(values) / len(values))


def freshness(days_since_last: Optional[float]) -> float:
    if days_since_last is None or days_since_last <= FRESH_FOR_DAYS:
        return 1.0
    return 0.5 ** ((days_since_last - FRESH_FOR_DAYS) / STALE_HALF_LIFE_DAYS)


def score_conversations(messages: int, active_days: int, days_since_last: Optional[float]) -> Optional[float]:
    """How much the user has said, scaled by how many days it is spread over, discounted if old."""
    if messages <= 0:
        return None
    depth = _saturate(messages, DEPTH_MESSAGES)
    breadth = _saturate(active_days, BREADTH_DAYS)
    spread_over_days = ONE_DAY_WORTH + (1.0 - ONE_DAY_WORTH) * breadth
    return _clamp(depth * spread_over_days * freshness(days_since_last))


def score_voice(own_usable: int, imported: int = 0) -> Optional[float]:
    """How much real writing Mirror has to copy from."""
    amount = max(0, own_usable) + IMPORTED_TEXT_WORTH * max(0, imported)
    if amount <= 0:
        return None
    return _clamp(_saturate(amount, VOICE_MESSAGES))


def score_reflections(confidences: Sequence[float]) -> Optional[float]:
    """Quote-verified patterns: how many of a full set exist, times how sure they are."""
    values = [_clamp(float(c)) for c in confidences if c is not None]
    if not values:
        return None
    return _clamp(min(1.0, len(values) / REFLECTIONS_FULL_SET) * (sum(values) / len(values)))


def fuse_source_scores(raw_scores: Dict[str, Optional[float]], messages: int = 0) -> Dict[str, object]:
    """Combine the source scores into a centre and a range.

    Centre: weighted average over the sources that have data.
    Half-width: a floor, plus a thin-evidence term that fades with messages, plus the
    spread between the sources, plus a penalty for sources with no data.
    """
    available = {k: _clamp(float(v)) for k, v in raw_scores.items() if v is not None and k in SOURCE_WEIGHTS}
    source_scores = {k: round(float(available.get(k, 0.0)), 4) for k in SOURCE_WEIGHTS}
    contributions: Dict[str, float] = {k: 0.0 for k in SOURCE_WEIGHTS}

    if not available:
        return {
            "center": 0.0,
            "lower": 0.0,
            "upper": 0.0,
            "half_width": 0.0,
            "source_scores": source_scores,
            "source_contributions": contributions,
        }

    coverage = sum(SOURCE_WEIGHTS[k] for k in available)
    center = 0.0
    for source, score in available.items():
        share = SOURCE_WEIGHTS[source] / coverage
        contributions[source] = round(score * share, 4)
        center += score * share

    spread = math.sqrt(
        sum((SOURCE_WEIGHTS[k] / coverage) * (score - center) ** 2 for k, score in available.items())
    )
    half_width = (
        MIN_HALF_WIDTH
        + THIN_EVIDENCE_WIDTH * math.exp(-max(0, messages) / THIN_EVIDENCE_MESSAGES)
        + DISAGREEMENT_WIDTH * spread
        + MISSING_SOURCE_WIDTH * (1.0 - coverage)
    )
    half_width = _clamp(half_width, MIN_HALF_WIDTH, MAX_HALF_WIDTH)

    return {
        "center": center,
        "lower": _clamp(center - half_width),
        "upper": _clamp(center + half_width),
        "half_width": half_width,
        "source_scores": source_scores,
        "source_contributions": contributions,
    }


def tier_from_confidence_lower(lower: float) -> str:
    pct = lower * 100.0
    for tier, up_to in TIER_BOUNDS:
        if pct <= up_to:
            return tier
    return "high"


def controls_for_tier(tier: str) -> Dict[str, float | bool]:
    if tier == "very_low":
        return {
            "phrase_usage_frequency": 0.10,
            "tone_strength": 0.20,
            "reaction_accuracy_threshold": 0.85,
            "style_enforcement_intensity": 0.15,
            "include_uncertainty_note": True,
        }
    if tier == "partial":
        return {
            "phrase_usage_frequency": 0.30,
            "tone_strength": 0.40,
            "reaction_accuracy_threshold": 0.70,
            "style_enforcement_intensity": 0.35,
            "include_uncertainty_note": False,
        }
    if tier == "moderate":
        return {
            "phrase_usage_frequency": 0.55,
            "tone_strength": 0.65,
            "reaction_accuracy_threshold": 0.55,
            "style_enforcement_intensity": 0.60,
            "include_uncertainty_note": False,
        }
    return {
        "phrase_usage_frequency": 0.80,
        "tone_strength": 0.85,
        "reaction_accuracy_threshold": 0.40,
        "style_enforcement_intensity": 0.85,
        "include_uncertainty_note": False,
    }


def build_result(
    trait_confidences: Sequence[float],
    trait_evidence: int,
    messages: int,
    active_days: int,
    days_since_last: Optional[float],
    voice_own: int,
    voice_imported: int,
    reflection_confidences: Sequence[float],
) -> ConfidenceIntervalResult:
    """Everything from plain numbers, so the whole rule can be tested without a database."""
    fused = fuse_source_scores(
        {
            "traits": score_traits(trait_confidences, trait_evidence),
            "conversations": score_conversations(messages, active_days, days_since_last),
            "voice": score_voice(voice_own, voice_imported),
            "reflections": score_reflections(reflection_confidences),
        },
        messages=messages,
    )
    tier = tier_from_confidence_lower(float(fused["lower"]))
    controls = controls_for_tier(tier)
    return ConfidenceIntervalResult(
        center=round(float(fused["center"]), 4),
        lower=round(float(fused["lower"]), 4),
        upper=round(float(fused["upper"]), 4),
        tier=tier,
        source_scores=dict(fused["source_scores"]),  # type: ignore[arg-type]
        source_weights=SOURCE_WEIGHTS.copy(),
        phrase_usage_frequency=float(controls["phrase_usage_frequency"]),
        tone_strength=float(controls["tone_strength"]),
        reaction_accuracy_threshold=float(controls["reaction_accuracy_threshold"]),
        style_enforcement_intensity=float(controls["style_enforcement_intensity"]),
        include_uncertainty_note=bool(controls["include_uncertainty_note"]),
        source_contributions=dict(fused["source_contributions"]),  # type: ignore[arg-type]
        facts={
            "messages": messages,
            "active_days": active_days,
            "days_since_last": round(days_since_last, 1) if days_since_last is not None else -1,
            "freshness": round(freshness(days_since_last), 3),
            "voice_messages": voice_own,
            "voice_imported": voice_imported,
            "reflections": len(list(reflection_confidences)),
            "half_width": round(float(fused["half_width"]), 4),
        },
    )


# --------------------------------------------------------------------------- database


async def compute_confidence_interval(
    db: AsyncSession,
    user_id: UUID,
    message_text: str = "",  # unused; kept for callers
) -> ConfidenceIntervalResult:
    metrics = (
        await db.execute(
            select(UserPersonaMetric.confidence, UserPersonaMetric.evidence_count).where(
                UserPersonaMetric.user_id == user_id
            )
        )
    ).all()

    own = (Message.user_id == user_id) & (Message.role == "user")
    messages, active_days, last_at = (
        await db.execute(
            select(
                func.count(Message.id),
                func.count(func.distinct(cast(Message.created_at, Date))),
                func.max(Message.created_at),
            ).where(own)
        )
    ).one()
    voice_own = (
        await db.execute(select(func.count(Message.id)).where(own, func.length(Message.content) >= VOICE_MIN_CHARS))
    ).scalar() or 0

    voice_imported = 0
    imports = (
        await db.execute(
            select(ExternalInput.extracted_markers).where(
                ExternalInput.user_id == user_id, ExternalInput.source == VOICE_IMPORT_SOURCE
            )
        )
    ).scalars().all()
    for markers in imports:
        if isinstance(markers, dict):
            voice_imported += int(markers.get("sample_count") or 0)

    reflection_confidences: List[float] = [
        float(value if value is not None else 0.6)
        for value in (
            await db.execute(
                select(BehavioralInsight.confidence).where(
                    BehavioralInsight.user_id == user_id, BehavioralInsight.kind == "reflection"
                )
            )
        ).scalars().all()
    ]

    days_since_last: Optional[float] = None
    if last_at is not None:
        days_since_last = max(0.0, (datetime.now(timezone.utc) - _ensure_utc(last_at)).total_seconds() / 86400.0)

    return build_result(
        trait_confidences=[float(row[0] or 0.0) for row in metrics],
        trait_evidence=sum(int(row[1] or 0) for row in metrics),
        messages=int(messages or 0),
        active_days=int(active_days or 0),
        days_since_last=days_since_last,
        voice_own=int(voice_own),
        voice_imported=voice_imported,
        reflection_confidences=reflection_confidences,
    )


async def build_confidence_explainability(
    db: AsyncSession,
    user_id: UUID,
    message_text: str = "",
) -> Dict[str, object]:
    """The same result as a plain dict, for the API."""
    result = await compute_confidence_interval(db=db, user_id=user_id)
    return {
        "center": result.center,
        "interval": {"lower": result.lower, "upper": result.upper},
        "tier": result.tier,
        "source_scores": result.source_scores,
        "source_weights": result.source_weights,
        "source_contributions": result.source_contributions,
        "facts": result.facts,
        "controls": {
            "phrase_usage_frequency": result.phrase_usage_frequency,
            "tone_strength": result.tone_strength,
            "reaction_accuracy_threshold": result.reaction_accuracy_threshold,
            "style_enforcement_intensity": result.style_enforcement_intensity,
            "include_uncertainty_note": result.include_uncertainty_note,
        },
    }


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))
