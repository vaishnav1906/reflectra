"""Post-draft style enforcement and reaction mapping for Persona Mirror.

Every stylistic addition is grounded in the user's own linguistic fingerprint:
- slang/abbreviation rewrites only use abbreviations the user has typed,
- reaction openers come from the user's own recurring openers (ReactionPattern),
- emojis are only added for users who use emojis, picked from their own set.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
import logging
from typing import Dict, Optional, Set

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import LinguisticFingerprint, ReactionPattern

logger = logging.getLogger(__name__)

EMOJI_REGEX = re.compile(r"[\U0001F300-\U0001FAFF☀-➿]")
MIN_ABBREVIATION_USES = 2  # an abbreviation must appear at least this often to be reused

# (pattern, replacement, abbreviation the user must already use)
SLANG_REWRITES = [
    (r"\bI am not sure\b", "idk", "idk"),
    (r"\bI'm not sure\b", "idk", "idk"),
    (r"\bI do not know\b", "idk", "idk"),
    (r"\bI don't know\b", "idk", "idk"),
    (r"\bto be honest\b", "tbh", "tbh"),
    (r"\bnot going to lie\b", "ngl", "ngl"),
    (r"\bkind of\b", "kinda", "kinda"),
    (r"\bgoing to\b", "gonna", "gonna"),
    (r"\bwant to\b", "wanna", "wanna"),
]

FORMAL_REWRITES = [
    (r"\bidk\b", "I am not sure"),
    (r"\btbh\b", "to be honest"),
    (r"\bngl\b", "to be honest"),
    (r"\bbro\b", ""),
]


@dataclass
class StyleEnforcementResult:
    text: str
    reaction_match_score: float
    stimulus_tag: str


@dataclass
class UserStyleProfile:
    abbreviations: Set[str]
    emoji_rate: float
    emojis: list


def detect_stimulus_tag(message: str) -> str:
    text = (message or "").lower()

    if any(token in text for token in ["idk", "not sure", "maybe", "confused", "doubt"]):
        return "doubt"
    if any(token in text for token in ["disagree", "wrong", "off", "doesn't make sense", "no way"]):
        return "disagreement"
    if any(token in text for token in ["cool", "interesting", "nice", "love this", "excited"]):
        return "interest"
    if any(token in text for token in ["deadline", "exam", "urgent", "pressure", "stressed"]):
        return "pressure"
    return "general"


def build_user_style_profile(fingerprint: Optional[LinguisticFingerprint]) -> UserStyleProfile:
    if fingerprint is None:
        return UserStyleProfile(abbreviations=set(), emoji_rate=0.0, emojis=[])

    abbreviation_stats: Dict[str, int] = dict(fingerprint.abbreviation_stats or {})
    abbreviations = {
        key for key, count in abbreviation_stats.items()
        if isinstance(count, (int, float)) and count >= MIN_ABBREVIATION_USES
    }

    patterns = dict(fingerprint.sentence_patterns or {})
    samples = max(int(fingerprint.sample_count or 0), 1)
    emoji_rate = min(1.0, float(patterns.get("emoji_messages", 0)) / samples)
    emoji_counts = dict(patterns.get("emoji_counts") or {})
    emojis = [emoji for emoji, _ in sorted(emoji_counts.items(), key=lambda kv: kv[1], reverse=True)][:5]
    return UserStyleProfile(abbreviations=abbreviations, emoji_rate=emoji_rate, emojis=emojis)


async def _load_user_style_profile(db: AsyncSession, user_id) -> UserStyleProfile:
    try:
        result = await db.execute(select(LinguisticFingerprint).where(LinguisticFingerprint.user_id == user_id))
        fingerprint = result.scalar_one_or_none()
    except Exception as exc:
        logger.warning("Skipping fingerprint lookup: %s", exc)
        await db.rollback()
        fingerprint = None
    return build_user_style_profile(fingerprint)


async def select_reaction_prefix(
    db: AsyncSession,
    user_id,
    stimulus_tag: str,
    threshold: float,
) -> tuple[Optional[str], float]:
    """Return the user's own established opener for this stimulus, if any."""
    stmt = (
        select(ReactionPattern)
        .where(
            ReactionPattern.user_id == user_id,
            ReactionPattern.stimulus_tag == stimulus_tag,
            ReactionPattern.confidence >= threshold,
        )
        .order_by(desc(ReactionPattern.confidence), desc(ReactionPattern.frequency), desc(ReactionPattern.last_seen_at))
        .limit(1)
    )
    try:
        result = await db.execute(stmt)
        pattern = result.scalar_one_or_none()
    except Exception as exc:
        logger.warning("Skipping reaction pattern lookup: %s", exc)
        await db.rollback()
        pattern = None

    if pattern and pattern.response_template:
        return pattern.response_template.strip(), float(pattern.confidence or 0.0)
    return None, 0.0


async def enforce_style(
    db: AsyncSession,
    user_id,
    draft: str,
    original_message: str,
    phrase_usage_frequency: float,
    tone_strength: float,
    style_intensity: float,
    reaction_threshold: float,
    include_uncertainty_note: bool,
    professional_context: bool,
    allow_slang: bool = True,
    allow_imperfect_grammar: bool = True,
) -> StyleEnforcementResult:
    """Apply light, user-grounded style adjustments to a drafted reply.

    `include_uncertainty_note` is accepted for API compatibility; low-confidence
    framing is handled in the generation prompt rather than by prepending a
    fixed disclaimer to every reply.
    """
    text = (draft or "").strip()
    if not text:
        text = "I'm not sure what to say."

    style_profile = await _load_user_style_profile(db, user_id)
    stimulus_tag = detect_stimulus_tag(original_message)
    reaction_prefix, reaction_score = await select_reaction_prefix(
        db=db,
        user_id=user_id,
        stimulus_tag=stimulus_tag,
        threshold=reaction_threshold,
    )

    # Reduce personality intensity for professional contexts while preserving identity.
    context_multiplier = 0.45 if professional_context else 1.0
    effective_phrase_frequency = phrase_usage_frequency * context_multiplier
    effective_style_intensity = style_intensity * context_multiplier

    text = _apply_rewrites(
        text,
        effective_style_intensity,
        allow_slang=allow_slang,
        allow_imperfect_grammar=allow_imperfect_grammar,
        user_abbreviations=style_profile.abbreviations,
    )

    if allow_slang and reaction_prefix and random.random() < effective_phrase_frequency:
        text = _inject_prefix(text, reaction_prefix)

    if tone_strength < 0.3:
        text = _clean_aggressive_slang(text, keep=style_profile.abbreviations)

    if not professional_context:
        text = _prefer_reaction_over_explanation(text)
        text = _inject_natural_emoji(
            text=text,
            tone_strength=tone_strength,
            user_emoji_rate=style_profile.emoji_rate,
            user_emojis=style_profile.emojis,
        )

    if professional_context:
        text = _professional_cleanup(text)

    text = _normalize_spacing(text)

    return StyleEnforcementResult(
        text=text,
        reaction_match_score=round(reaction_score, 3),
        stimulus_tag=stimulus_tag,
    )


def _inject_prefix(text: str, prefix: str) -> str:
    lower = text.lower()
    if lower.startswith(prefix.lower()):
        return text
    if not text:
        return prefix
    return f"{prefix}, {text[0].lower() + text[1:] if len(text) > 1 else text.lower()}"


def _apply_rewrites(
    text: str,
    style_intensity: float,
    allow_slang: bool,
    allow_imperfect_grammar: bool,
    user_abbreviations: Optional[Set[str]] = None,
) -> str:
    out = text
    if allow_slang:
        known = user_abbreviations or set()
        for pattern, replacement, required in SLANG_REWRITES:
            if required not in known:
                continue
            # Grammar-relaxing rewrites (kinda/gonna/wanna) also need imperfect grammar allowed.
            if required in {"kinda", "gonna", "wanna"} and not allow_imperfect_grammar:
                continue
            if random.random() <= style_intensity:
                out = re.sub(pattern, replacement, out, flags=re.IGNORECASE)
    else:
        for pattern, replacement in FORMAL_REWRITES:
            if random.random() <= style_intensity:
                out = re.sub(pattern, replacement, out, flags=re.IGNORECASE)
    return out


def _clean_aggressive_slang(text: str, keep: Optional[Set[str]] = None) -> str:
    out = text
    for token in ("bro", "fr", "deadass"):
        if keep and token in keep:
            continue
        out = re.sub(rf"\b{re.escape(token)}\b", "", out, flags=re.IGNORECASE)
    return _normalize_spacing(out)


def _normalize_spacing(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip(" ,")


def _professional_cleanup(text: str) -> str:
    cleaned = text
    replacements = {
        r"\bidk man\b": "I am not sure",
        r"\bidk\b": "I am not sure",
        r"\bthis feels off tbh\b": "this seems off",
        r"\btbh\b": "to be honest",
        r"\bngl\b": "to be honest",
        r"\bbro\b": "",
    }
    for pattern, replacement in replacements.items():
        cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
    return _normalize_spacing(cleaned)


def _prefer_reaction_over_explanation(text: str) -> str:
    """Nudge casual outputs away from assistant-like explanatory openers."""
    out = text.strip()
    rewrites = [
        (r"^(here(?:'s| is) what .*?:\s*)", ""),
        (r"^(let me explain\s*)", ""),
        (r"^(to clarify,\s*)", ""),
    ]
    for pattern, replacement in rewrites:
        out = re.sub(pattern, replacement, out, flags=re.IGNORECASE)

    return _normalize_spacing(out)


def _inject_natural_emoji(
    text: str,
    tone_strength: float,
    user_emoji_rate: float,
    user_emojis: list,
) -> str:
    """Add one of the user's own emojis, roughly as often as the user uses emojis."""
    if not text or not user_emojis or user_emoji_rate <= 0:
        return text

    if EMOJI_REGEX.search(text):
        return text

    if "http://" in text or "https://" in text:
        return text

    probability = min(0.6, user_emoji_rate * (0.5 + tone_strength))
    if random.random() > probability:
        return text

    return f"{text} {random.choice(user_emojis)}"
