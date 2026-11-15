"""Behavioral memory: the user's linguistic fingerprint and recurring reaction openers.

Everything stored here is derived from the USER's own messages. The style layer
(style_enforcement_service) only reuses slang, emojis and openers that appear here,
so the mirror never adds verbal habits the user does not actually have.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import LinguisticFingerprint, ReactionPattern

KNOWN_ABBREVIATIONS = (
    "idk", "tbh", "ngl", "imo", "imho", "fr", "brb", "btw",
    "bro", "lol", "lmao", "kinda", "gonna", "wanna", "lowkey", "deadass",
)
EMOJI_REGEX = re.compile(r"[\U0001F300-\U0001FAFF☀-➿]")
PHRASE_STOPWORDS = {
    "i", "a", "an", "the", "to", "of", "and", "or", "in", "on", "it", "is", "am", "are",
    "was", "be", "my", "me", "that", "this", "for", "with", "at", "so", "but",
}
MAX_TRACKED_PHRASES = 80
MAX_TRACKED_EMOJIS = 20
MIN_PHRASE_COUNT = 2
REACTION_OPENER_MAX_WORDS = 4
REACTION_CONFIDENCE_DECAY = 0.7  # confidence = 1 - 0.7^frequency


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z']+", (text or "").lower())


def _top_counts(counts: Dict[str, int], limit: int) -> Dict[str, int]:
    return dict(Counter(counts).most_common(limit))


def _is_content_phrase(phrase: str) -> bool:
    return any(word not in PHRASE_STOPWORDS for word in phrase.split())


async def get_linguistic_fingerprint(db: AsyncSession, user_id: UUID) -> Optional[LinguisticFingerprint]:
    result = await db.execute(select(LinguisticFingerprint).where(LinguisticFingerprint.user_id == user_id))
    return result.scalar_one_or_none()


async def update_linguistic_fingerprint(db: AsyncSession, user_id: UUID, user_text: str) -> None:
    text = (user_text or "").strip()
    if not text:
        return

    tokens = _tokenize(text)
    if not tokens:
        return

    record = await get_linguistic_fingerprint(db, user_id)

    abbrev_counter = Counter(token for token in tokens if token in KNOWN_ABBREVIATIONS)
    bigrams = Counter(f"{tokens[i]} {tokens[i + 1]}" for i in range(len(tokens) - 1))
    emojis = Counter(EMOJI_REGEX.findall(text))

    sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()]
    sentence_count = max(len(sentences), 1)
    fragment_ratio = min(1.0, sum(1 for s in sentences if 0 < len(s.split()) <= 4) / sentence_count)
    punctuation_cadence = {
        "exclamation": text.count("!"),
        "question": text.count("?"),
        "ellipsis": text.count("..."),
    }

    if record is None:
        record = LinguisticFingerprint(
            user_id=user_id,
            characteristic_phrases=[],
            abbreviation_stats={},
            sentence_patterns={},
            sample_count=0,
            confidence=0.1,
        )
        db.add(record)

    sample_count = int(record.sample_count or 0) + 1
    previous = dict(record.sentence_patterns or {})

    abbreviations: Dict[str, int] = dict(record.abbreviation_stats or {})
    for key, value in abbrev_counter.items():
        abbreviations[key] = int(abbreviations.get(key, 0)) + int(value)

    phrase_counts: Dict[str, int] = dict(previous.get("phrase_counts") or {})
    for phrase, count in bigrams.items():
        phrase_counts[phrase] = int(phrase_counts.get(phrase, 0)) + count
    phrase_counts = _top_counts(phrase_counts, MAX_TRACKED_PHRASES)

    emoji_counts: Dict[str, int] = dict(previous.get("emoji_counts") or {})
    for emoji, count in emojis.items():
        emoji_counts[emoji] = int(emoji_counts.get(emoji, 0)) + count
    emoji_counts = _top_counts(emoji_counts, MAX_TRACKED_EMOJIS)
    emoji_messages = int(previous.get("emoji_messages", 0)) + (1 if emojis else 0)

    prev_fragment = float(previous.get("fragment_ratio", fragment_ratio))
    prev_len = float(previous.get("avg_sentence_length", len(tokens) / sentence_count))

    # Characteristic phrases: recurring bigrams that carry some content.
    record.characteristic_phrases = [
        phrase
        for phrase, count in Counter(phrase_counts).most_common()
        if count >= MIN_PHRASE_COUNT and _is_content_phrase(phrase)
    ][:12]
    record.abbreviation_stats = abbreviations
    record.sentence_patterns = {
        "fragment_ratio": round(((prev_fragment * (sample_count - 1)) + fragment_ratio) / sample_count, 3),
        "avg_sentence_length": round(((prev_len * (sample_count - 1)) + (len(tokens) / sentence_count)) / sample_count, 2),
        "punctuation_cadence": punctuation_cadence,
        "phrase_counts": phrase_counts,
        "emoji_counts": emoji_counts,
        "emoji_messages": emoji_messages,
    }
    record.sample_count = sample_count
    record.confidence = min(1.0, 0.1 + 0.9 * (1 - 0.97 ** sample_count))
    record.updated_at = datetime.now(timezone.utc)
    await db.flush()


def extract_reaction_opener(user_text: str) -> Optional[str]:
    """Return the user's short leading reaction (e.g. "idk man", "honestly", "nah fr").

    Only the first clause counts, and only when it is 1-4 words, so we capture
    verbal habits rather than whole sentences.
    """
    text = (user_text or "").strip()
    if not text:
        return None

    first_clause = re.split(r"[,.!?;:\n]|\s[-—]\s", text, maxsplit=1)[0].strip()
    words = first_clause.split()
    if not 1 <= len(words) <= REACTION_OPENER_MAX_WORDS:
        return None

    opener = " ".join(words).lower()
    if len(words) == 1 and len(opener) <= 1:
        return None
    return opener


def reaction_confidence(frequency: int) -> float:
    return round(1.0 - (REACTION_CONFIDENCE_DECAY ** max(frequency, 0)), 3)


async def record_user_reaction(db: AsyncSession, user_id: UUID, user_text: str) -> None:
    """Remember how the user opens messages under a given stimulus (doubt, pressure, ...).

    Confidence rises with repetition, so a reaction is only reused by the mirror
    once it is a real habit (e.g. ~6 occurrences at the lowest confidence tier).
    """
    from app.services.style_enforcement_service import detect_stimulus_tag

    opener = extract_reaction_opener(user_text)
    if not opener:
        return

    stimulus_tag = detect_stimulus_tag(user_text)
    stmt = select(ReactionPattern).where(
        ReactionPattern.user_id == user_id,
        ReactionPattern.stimulus_tag == stimulus_tag,
        ReactionPattern.response_template == opener,
    )
    record = (await db.execute(stmt)).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    style_signature = {
        "contains_slang": any(tok in opener.split() for tok in KNOWN_ABBREVIATIONS),
        "word_count": len(opener.split()),
    }

    if record is None:
        db.add(
            ReactionPattern(
                user_id=user_id,
                stimulus_tag=stimulus_tag,
                response_template=opener,
                phrase_bank=[opener],
                style_signature=style_signature,
                confidence=reaction_confidence(1),
                frequency=1,
                last_seen_at=now,
            )
        )
    else:
        record.frequency = int(record.frequency or 0) + 1
        record.confidence = reaction_confidence(record.frequency)
        record.last_seen_at = now
        record.style_signature = style_signature
    await db.flush()
