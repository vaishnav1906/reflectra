"""Confidence interval fusion service for Persona Mirror control."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
from typing import Dict, List
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BehavioralInsight, ExternalInput, Message, ReflectionLog, UserPersonaMetric

SOURCE_WEIGHTS: Dict[str, float] = {
    "conversations": 0.40,
    "traits": 0.20,
    "timeline_reflections": 0.15,
    "reflection_summaries": 0.15,
    "external_inputs": 0.10,
}

logger = logging.getLogger(__name__)


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
    timeline_recency_override: Dict[str, float | bool]


async def compute_confidence_interval(
    db: AsyncSession,
    user_id: UUID,
    message_text: str,
) -> ConfidenceIntervalResult:
    """Fuse all mandatory sources into a confidence interval and generation controls."""
    timeline_score, timeline_details = await _score_timeline_with_details(db, user_id)
    source_scores = {
        "conversations": await _score_conversations(db, user_id),
        "traits": await _score_traits(db, user_id),
        "timeline_reflections": timeline_score,
        "reflection_summaries": await _score_reflections(db, user_id),
        "external_inputs": await _score_external_inputs(db, user_id, message_text),
    }

    center = 0.0
    source_contributions: Dict[str, float] = {}
    for source, weight in SOURCE_WEIGHTS.items():
        contribution = source_scores[source] * weight
        source_contributions[source] = contribution
        center += contribution

    scores = list(source_scores.values())
    disagreement = statistics.pstdev(scores) if len(scores) > 1 else 0.0
    evidence_density = sum(1 for v in scores if v >= 0.4) / max(len(scores), 1)
    uncertainty = 0.32 + (0.45 * disagreement) - (0.20 * evidence_density)
    uncertainty = _clamp(uncertainty, 0.08, 0.45)

    lower = _clamp(center - (uncertainty / 2.0), 0.0, 1.0)
    upper = _clamp(center + (uncertainty / 2.0), 0.0, 1.0)

    tier = tier_from_confidence_lower(lower)
    controls = controls_for_tier(tier)

    return ConfidenceIntervalResult(
        center=round(center, 4),
        lower=round(lower, 4),
        upper=round(upper, 4),
        tier=tier,
        source_scores={k: round(v, 4) for k, v in source_scores.items()},
        source_weights=SOURCE_WEIGHTS.copy(),
        phrase_usage_frequency=controls["phrase_usage_frequency"],
        tone_strength=controls["tone_strength"],
        reaction_accuracy_threshold=controls["reaction_accuracy_threshold"],
        style_enforcement_intensity=controls["style_enforcement_intensity"],
        include_uncertainty_note=controls["include_uncertainty_note"],
        source_contributions={k: round(v, 4) for k, v in source_contributions.items()},
        timeline_recency_override=timeline_details,
    )


async def build_confidence_explainability(
    db: AsyncSession,
    user_id: UUID,
    message_text: str,
) -> Dict[str, object]:
    """Return explainability payload for confidence interval source contributions."""
    result = await compute_confidence_interval(db=db, user_id=user_id, message_text=message_text)
    return {
        "center": result.center,
        "interval": {
            "lower": result.lower,
            "upper": result.upper,
        },
        "tier": result.tier,
        "source_scores": result.source_scores,
        "source_weights": result.source_weights,
        "source_contributions": result.source_contributions,
        "timeline_recency_override": result.timeline_recency_override,
        "controls": {
            "phrase_usage_frequency": result.phrase_usage_frequency,
            "tone_strength": result.tone_strength,
            "reaction_accuracy_threshold": result.reaction_accuracy_threshold,
            "style_enforcement_intensity": result.style_enforcement_intensity,
            "include_uncertainty_note": result.include_uncertainty_note,
        },
    }


async def _score_conversations(db: AsyncSession, user_id: UUID) -> float:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=45)

    stmt = (
        select(Message.content, Message.created_at)
        .where(
            Message.user_id == user_id,
            Message.role == "user",
            Message.created_at >= cutoff,
        )
        .order_by(Message.created_at.desc())
        .limit(120)
    )
    result = await db.execute(stmt)
    rows = result.all()

    if not rows:
        return 0.05

    count_score = _clamp(len(rows) / 120.0, 0.0, 1.0)

    slang_markers = ["idk", "tbh", "ngl", "bro", "not gonna lie", "kinda", "man"]
    hits = 0
    lengths: List[int] = []

    for content, created_at in rows:
        text = (content or "").lower()
        if any(marker in text for marker in slang_markers):
            hits += 1
        lengths.append(len(text.split()))

    slang_consistency = hits / max(len(rows), 1)
    length_stability = 1.0
    if len(lengths) > 1:
        mean_len = sum(lengths) / len(lengths)
        variance = statistics.pvariance(lengths)
        cv = math.sqrt(variance) / max(mean_len, 1.0)
        length_stability = _clamp(1.0 - cv, 0.0, 1.0)

    return _clamp((0.50 * count_score) + (0.30 * slang_consistency) + (0.20 * length_stability), 0.0, 1.0)


async def _score_traits(db: AsyncSession, user_id: UUID) -> float:
    stmt = select(UserPersonaMetric.confidence, UserPersonaMetric.last_updated).where(UserPersonaMetric.user_id == user_id)
    result = await db.execute(stmt)
    rows = result.all()

    if not rows:
        return 0.05

    avg_conf = statistics.mean(float(row[0] or 0.0) for row in rows)
    now = datetime.now(timezone.utc)
    recency_weights: List[float] = []
    for _, updated_at in rows:
        if updated_at is None:
            recency_weights.append(0.5)
            continue
        age_days = max((now - _ensure_utc(updated_at)).days, 0)
        recency_weights.append(math.exp(-age_days / 30.0))

    recency = statistics.mean(recency_weights) if recency_weights else 0.5
    return _clamp((0.75 * avg_conf) + (0.25 * recency), 0.0, 1.0)


async def _score_timeline_with_details(db: AsyncSession, user_id: UUID) -> tuple[float, Dict[str, float | bool]]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    stmt = (
        select(BehavioralInsight.confidence, BehavioralInsight.created_at)
        .where(
            BehavioralInsight.user_id == user_id,
            BehavioralInsight.created_at >= cutoff,
        )
        .order_by(BehavioralInsight.created_at.desc())
        .limit(80)
    )
    result = await db.execute(stmt)
    rows = result.all()

    if not rows:
        return 0.05, {
            "applied": False,
            "recent_avg": 0.0,
            "older_avg": 0.0,
            "override_strength": 0.0,
        }

    conf_avg = statistics.mean(float(row[0] or 0.6) for row in rows)
    density = _clamp(len(rows) / 80.0, 0.0, 1.0)

    now = datetime.now(timezone.utc)
    recent_bucket: List[float] = []
    older_bucket: List[float] = []
    for confidence, created_at in rows:
        value = float(confidence or 0.6)
        if created_at is None:
            older_bucket.append(value)
            continue
        age_days = max((now - _ensure_utc(created_at)).days, 0)
        if age_days <= 7:
            recent_bucket.append(value)
        else:
            older_bucket.append(value)

    recent_avg = statistics.mean(recent_bucket) if recent_bucket else conf_avg
    older_avg = statistics.mean(older_bucket) if older_bucket else conf_avg
    delta = recent_avg - older_avg
    # Recency override: recent shifts dominate when there is meaningful change.
    override_strength = _clamp(abs(delta) * 1.8, 0.0, 0.45)
    recency_blend = _clamp(0.55 + (0.35 if recent_bucket else 0.0), 0.0, 0.9)
    recency_weighted = (recent_avg * recency_blend) + (older_avg * (1.0 - recency_blend))

    base_score = _clamp((0.65 * conf_avg) + (0.35 * density), 0.0, 1.0)
    overridden = _clamp((base_score * (1.0 - override_strength)) + (recency_weighted * override_strength), 0.0, 1.0)

    return overridden, {
        "applied": bool(recent_bucket and older_bucket and abs(delta) > 0.06),
        "recent_avg": round(recent_avg, 4),
        "older_avg": round(older_avg, 4),
        "override_strength": round(override_strength, 4),
    }


async def _score_reflections(db: AsyncSession, user_id: UUID) -> float:
    cutoff = datetime.now(timezone.utc) - timedelta(days=45)
    stmt = (
        select(ReflectionLog.sentiment, ReflectionLog.created_at)
        .where(
            ReflectionLog.user_id == user_id,
            ReflectionLog.created_at >= cutoff,
        )
        .order_by(ReflectionLog.created_at.desc())
        .limit(60)
    )
    result = await db.execute(stmt)
    rows = result.all()

    if not rows:
        return 0.05

    density = _clamp(len(rows) / 60.0, 0.0, 1.0)
    sentiment_defined = sum(1 for sentiment, _ in rows if sentiment is not None) / max(len(rows), 1)
    return _clamp((0.60 * density) + (0.40 * sentiment_defined), 0.0, 1.0)


async def _score_external_inputs(db: AsyncSession, user_id: UUID, message_text: str) -> float:
    cutoff = datetime.now(timezone.utc) - timedelta(days=60)
    stmt = (
        select(ExternalInput.content, ExternalInput.created_at, ExternalInput.confidence_weight)
        .where(
            ExternalInput.user_id == user_id,
            ExternalInput.created_at >= cutoff,
        )
        .order_by(ExternalInput.created_at.desc())
        .limit(40)
    )
    try:
        result = await db.execute(stmt)
        rows = result.all()
    except Exception as exc:
        # External input memory is optional; return conservative score if table is unavailable.
        logger.warning("Skipping external input scoring: %s", exc)
        await db.rollback()
        return 0.05

    if not rows:
        return 0.05

    density = _clamp(len(rows) / 40.0, 0.0, 1.0)
    avg_weight = statistics.mean(float(weight or 0.1) for _, _, weight in rows)

    msg_tokens = set((message_text or "").lower().split())
    overlap_scores: List[float] = []
    for content, _, _ in rows[:12]:
        ext_tokens = set((content or "").lower().split())
        if not ext_tokens:
            continue
        overlap_scores.append(len(msg_tokens & ext_tokens) / len(ext_tokens))

    overlap = statistics.mean(overlap_scores) if overlap_scores else 0.0
    return _clamp((0.45 * density) + (0.30 * avg_weight) + (0.25 * overlap), 0.0, 1.0)


def tier_from_confidence_lower(lower: float) -> str:
    pct = lower * 100.0
    if pct <= 20.0:
        return "very_low"
    if pct <= 50.0:
        return "partial"
    if pct <= 75.0:
        return "moderate"
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


async def _score_timeline(db: AsyncSession, user_id: UUID) -> float:
    score, _ = await _score_timeline_with_details(db, user_id)
    return score


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))
