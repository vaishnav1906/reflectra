"""Post-draft style enforcement and reaction mapping for Persona Mirror."""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
import logging
from typing import Dict

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ReactionPattern

logger = logging.getLogger(__name__)

EMOJI_CANDIDATES = ["😂", "😅", "😭", "🔥", "💀", "😮", "🤝", "😬"]
EMOJI_REGEX = re.compile(r"[\U0001F300-\U0001FAFF]")


@dataclass
class StyleEnforcementResult:
    text: str
    reaction_match_score: float
    stimulus_tag: str


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


async def select_reaction_prefix(
    db: AsyncSession,
    user_id,
    stimulus_tag: str,
    threshold: float,
) -> tuple[str, float]:
    stmt = (
        select(ReactionPattern)
        .where(
            ReactionPattern.user_id == user_id,
            ReactionPattern.stimulus_tag == stimulus_tag,
            ReactionPattern.confidence >= threshold,
        )
        .order_by(desc(ReactionPattern.last_seen_at), desc(ReactionPattern.confidence), desc(ReactionPattern.frequency))
        .limit(1)
    )
    try:
        result = await db.execute(stmt)
        pattern = result.scalar_one_or_none()
    except Exception as exc:
        logger.warning("Skipping reaction pattern lookup: %s", exc)
        await db.rollback()
        pattern = None

    if pattern:
        return pattern.response_template.strip(), float(pattern.confidence or 0.5)

    fallback = {
        "doubt": "idk man",
        "disagreement": "this feels off tbh",
        "interest": "this is kinda cool ngl",
        "pressure": "nah this is a lot tbh",
        "general": "tbh",
    }
    return fallback.get(stimulus_tag, "tbh"), 0.35


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
    text = (draft or "").strip()
    if not text:
        text = "say more"

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
    )

    if allow_slang and random.random() < effective_phrase_frequency:
        text = _inject_prefix(text, reaction_prefix)

    if tone_strength < 0.3:
        text = _clean_aggressive_slang(text)

    if include_uncertainty_note and not professional_context:
        uncertainty = "This might not fully match your style yet, but "
        if not text.lower().startswith("this might not fully match"):
            text = f"{uncertainty}{text[0].lower() + text[1:] if len(text) > 1 else text.lower()}"

    if not professional_context:
        text = _prefer_reaction_over_explanation(text)
        text = _inject_natural_emoji(
            text=text,
            tone_strength=tone_strength,
            phrase_usage_frequency=effective_phrase_frequency,
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
) -> str:
    if allow_slang:
        rewrites = [
            (r"\bI am not sure\b", "idk man"),
            (r"\bI'm not sure\b", "idk man"),
            (r"\bI do not know\b", "idk"),
            (r"\bI don't know\b", "idk"),
            (r"\bThis seems incorrect\b", "this feels off tbh"),
            (r"\bThis is incorrect\b", "this feels off tbh"),
            (r"\bto be honest\b", "tbh"),
            (r"\bnot going to lie\b", "ngl"),
        ]
    else:
        rewrites = [
            (r"\bidk\b", "I am not sure"),
            (r"\btbh\b", "to be honest"),
            (r"\bngl\b", "to be honest"),
            (r"\bbro\b", ""),
        ]

    out = text
    for pattern, replacement in rewrites:
        if random.random() <= style_intensity:
            out = re.sub(pattern, replacement, out, flags=re.IGNORECASE)

    # Slight grammar relaxation for high confidence and non-professional contexts.
    if allow_imperfect_grammar and style_intensity >= 0.75:
        out = re.sub(r"\bkind of\b", "kinda", out, flags=re.IGNORECASE)
        out = re.sub(r"\bgoing to\b", "gonna", out, flags=re.IGNORECASE)
    return out


def _clean_aggressive_slang(text: str) -> str:
    replacements = {
        "bro": "",
        "fr": "",
        "deadass": "",
    }
    out = text
    for token, replacement in replacements.items():
        out = re.sub(rf"\b{re.escape(token)}\b", replacement, out, flags=re.IGNORECASE)
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
        (r"^(i would recommend\s*)", "lowkey "),
        (r"^(you should\s*)", "honestly "),
    ]
    for pattern, replacement in rewrites:
        out = re.sub(pattern, replacement, out, flags=re.IGNORECASE)

    return _normalize_spacing(out)


def _inject_natural_emoji(text: str, tone_strength: float, phrase_usage_frequency: float) -> str:
    """Add a casual emoji when tone suggests it and text does not already have one."""
    if not text:
        return text

    if EMOJI_REGEX.search(text):
        return text

    if "http://" in text or "https://" in text:
        return text

    probability = min(0.45, max(0.06, (0.12 + (0.28 * tone_strength) + (0.20 * phrase_usage_frequency))))
    if random.random() > probability:
        return text

    emoji = random.choice(EMOJI_CANDIDATES)
    if text.endswith(("!", "?", ".")):
        return f"{text} {emoji}"
    return f"{text} {emoji}"
