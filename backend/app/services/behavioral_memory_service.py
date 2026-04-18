"""Behavioral memory updaters for linguistic fingerprints and reaction patterns."""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone
from typing import Dict, List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import LinguisticFingerprint, ReactionPattern

KNOWN_ABBREVIATIONS = ("idk", "tbh", "ngl", "imo", "imho", "fr", "brb", "btw")


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z']+", (text or "").lower())


async def update_linguistic_fingerprint(db: AsyncSession, user_id: UUID, user_text: str) -> None:
    text = (user_text or "").strip()
    if not text:
        return

    stmt = select(LinguisticFingerprint).where(LinguisticFingerprint.user_id == user_id)
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()

    tokens = _tokenize(text)
    if not tokens:
        return

    abbrev_counter = Counter(token for token in tokens if token in KNOWN_ABBREVIATIONS)
    bigrams = [f"{tokens[i]} {tokens[i + 1]}" for i in range(len(tokens) - 1)]
    phrases = Counter(bigrams).most_common(6)

    sentence_count = max(len([s for s in re.split(r"[.!?]+", text) if s.strip()]), 1)
    fragment_ratio = 1.0 if sentence_count == 0 else min(1.0, sum(1 for s in re.split(r"[.!?]+", text) if 0 < len(s.split()) <= 4) / sentence_count)
    punctuation_cadence = {
        "exclamation": text.count("!"),
        "question": text.count("?"),
        "ellipsis": text.count("..."),
    }

    if record is None:
        record = LinguisticFingerprint(
            user_id=user_id,
            characteristic_phrases=[p for p, _ in phrases],
            abbreviation_stats={k: int(v) for k, v in abbrev_counter.items()},
            sentence_patterns={
                "fragment_ratio": round(fragment_ratio, 3),
                "avg_sentence_length": round(len(tokens) / sentence_count, 2),
                "punctuation_cadence": punctuation_cadence,
            },
            sample_count=1,
            confidence=0.2,
        )
        db.add(record)
        await db.flush()
        return

    existing_abbrev: Dict[str, int] = dict(record.abbreviation_stats or {})
    for key, value in abbrev_counter.items():
        existing_abbrev[key] = int(existing_abbrev.get(key, 0)) + int(value)

    phrase_bank = list(record.characteristic_phrases or [])
    for phrase, _ in phrases:
        if phrase not in phrase_bank:
            phrase_bank.append(phrase)
    phrase_bank = phrase_bank[-24:]

    sample_count = int(record.sample_count or 0) + 1
    previous_patterns = dict(record.sentence_patterns or {})
    prev_fragment = float(previous_patterns.get("fragment_ratio", 0.5))
    prev_len = float(previous_patterns.get("avg_sentence_length", 8.0))

    record.characteristic_phrases = phrase_bank
    record.abbreviation_stats = existing_abbrev
    record.sentence_patterns = {
        "fragment_ratio": round(((prev_fragment * (sample_count - 1)) + fragment_ratio) / sample_count, 3),
        "avg_sentence_length": round(((prev_len * (sample_count - 1)) + (len(tokens) / sentence_count)) / sample_count, 2),
        "punctuation_cadence": punctuation_cadence,
    }
    record.sample_count = sample_count
    record.confidence = min(1.0, float(record.confidence or 0.1) + 0.01)
    record.updated_at = datetime.now(timezone.utc)
    await db.flush()


async def upsert_reaction_pattern(
    db: AsyncSession,
    user_id: UUID,
    stimulus_tag: str,
    response_template: str,
    reaction_match_score: float,
) -> None:
    cleaned = (response_template or "").strip()
    if not cleaned or not stimulus_tag:
        return

    # Keep templates compact to avoid excessive cardinality.
    cleaned = " ".join(cleaned.split())[:180]

    stmt = select(ReactionPattern).where(
        ReactionPattern.user_id == user_id,
        ReactionPattern.stimulus_tag == stimulus_tag,
        ReactionPattern.response_template == cleaned,
    )
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()

    phrase_bank = [cleaned[:40]]
    style_signature = {
        "contains_slang": any(tok in cleaned.lower() for tok in ["idk", "tbh", "ngl", "bro"]),
        "word_count": len(cleaned.split()),
    }

    if record is None:
        db.add(
            ReactionPattern(
                user_id=user_id,
                stimulus_tag=stimulus_tag,
                response_template=cleaned,
                phrase_bank=phrase_bank,
                style_signature=style_signature,
                confidence=max(0.2, min(1.0, reaction_match_score)),
                frequency=1,
                last_seen_at=datetime.now(timezone.utc),
            )
        )
        await db.flush()
        return

    record.frequency = int(record.frequency or 0) + 1
    record.confidence = min(1.0, ((float(record.confidence or 0.3) * 0.8) + (reaction_match_score * 0.2)))
    record.last_seen_at = datetime.now(timezone.utc)

    existing_bank = list(record.phrase_bank or [])
    for phrase in phrase_bank:
        if phrase not in existing_bank:
            existing_bank.append(phrase)
    record.phrase_bank = existing_bank[-12:]
    record.style_signature = style_signature
    await db.flush()
