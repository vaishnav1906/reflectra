"""Context classification and strict style policy gates for mirror outputs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


PROFESSIONAL_TASK_TYPES = {
    "email_draft",
    "message_draft",
    "rewrite",
    "summarize",
    "planning",
}


@dataclass
class ContextPolicyDecision:
    context_mode: str
    phrase_usage_frequency: float
    tone_strength: float
    style_enforcement_intensity: float
    allow_slang: bool
    allow_imperfect_grammar: bool


def classify_response_context(message: str, task_type: Optional[str] = None) -> str:
    if task_type in PROFESSIONAL_TASK_TYPES:
        return "professional"

    text = (message or "").strip().lower()
    if not text:
        return "casual"

    professional_patterns = [
        r"\bsubject:\b",
        r"\bdear\s+[a-z]",
        r"\bregards\b",
        r"\bsincerely\b",
        r"\bproposal\b",
        r"\bmeeting\b",
        r"\bstakeholder\b",
        r"\bresume\b",
        r"\bcover letter\b",
        r"\bformal\b",
        r"\bprofessional\b",
    ]
    if any(re.search(pattern, text) for pattern in professional_patterns):
        return "professional"

    casual_markers = ["bro", "idk", "tbh", "ngl", "lol", "nah", "fr"]
    if any(marker in text for marker in casual_markers):
        return "casual"

    return "casual"


def apply_context_policy_gates(
    context_mode: str,
    phrase_usage_frequency: float,
    tone_strength: float,
    style_enforcement_intensity: float,
    confidence_tier: str,
) -> ContextPolicyDecision:
    if context_mode == "professional":
        # Stricter policy: cleaner output while preserving user identity cues.
        max_phrase = 0.08 if confidence_tier != "high" else 0.16
        return ContextPolicyDecision(
            context_mode="professional",
            phrase_usage_frequency=min(phrase_usage_frequency, max_phrase),
            tone_strength=min(tone_strength, 0.55),
            style_enforcement_intensity=min(style_enforcement_intensity, 0.35),
            allow_slang=(confidence_tier == "high"),
            allow_imperfect_grammar=False,
        )

    return ContextPolicyDecision(
        context_mode="casual",
        phrase_usage_frequency=phrase_usage_frequency,
        tone_strength=tone_strength,
        style_enforcement_intensity=style_enforcement_intensity,
        allow_slang=True,
        allow_imperfect_grammar=True,
    )
