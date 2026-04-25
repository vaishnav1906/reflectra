"""Task routing and twin-aware prompt construction for assistant mode."""

import re
from typing import Any, Dict, Optional


TASK_PROMPT_NOTES = {
    "email_draft": "Draft a complete email with a concise subject line and clear CTA.",
    "message_draft": "Draft a message suitable for chat or DM with context-aware brevity.",
    "rewrite": "Rewrite the provided text while preserving meaning and improving clarity.",
    "summarize": "Summarize content into key points and action items when relevant.",
    "brainstorm": "Provide diverse, practical options and short rationale for each.",
    "planning": "Produce a step-by-step plan with prioritization and time-aware sequencing.",
    "qa": "Answer directly, then add a compact explanation or example when useful.",
    "generic": "Provide a direct, useful response tailored to the request.",
}


def classify_assistant_task(message: str) -> str:
    """Heuristic task classifier for assistant mode routing."""
    text = (message or "").strip().lower()
    if not text:
        return "generic"

    if any(token in text for token in ["in my tone", "my tone", "my voice", "sound like me", "write like me"]):
        return "rewrite"
    if any(token in text for token in ["subject:", "dear ", "sincerely", "regards", "email", "mail"]):
        return "email_draft"
    if any(token in text for token in ["dm", "text", "message", "msg", "whatsapp", "slack"]):
        return "message_draft"
    if any(token in text for token in ["rewrite", "rephrase", "paraphrase", "make this sound", "edit this"]):
        return "rewrite"
    if re.search(r"\b(generate|create)\b", text):
        return "message_draft"
    if re.search(r"\b(write|draft|compose)\b", text):
        return "message_draft"
    if any(token in text for token in ["summarize", "summary", "tl;dr", "tldr", "condense"]):
        return "summarize"
    if any(token in text for token in ["brainstorm", "ideas", "suggest options", "possible approaches"]):
        return "brainstorm"
    if any(token in text for token in ["plan", "roadmap", "schedule", "steps", "timeline"]):
        return "planning"
    if "?" in text or any(token in text for token in ["what is", "how to", "why does", "explain"]):
        return "qa"

    return "generic"


def _mirror_style_note(intensity: float) -> str:
    if intensity <= 0.35:
        return "Apply subtle style matching. Prioritize correctness over voice mimicry."
    if intensity <= 0.7:
        return "Apply balanced style matching. Keep the user's voice without overfitting quirks."
    return "Apply strong style matching. Preserve cadence, phrasing tendencies, and social tone."


def build_twin_assistant_system_prompt(
    task_type: str,
    twin_policy: Dict[str, Any],
    communication_summary: str,
    personality_summary: str,
    snapshot_summary: Optional[str] = None,
) -> str:
    """Build assistant prompt that combines general capability with twin identity constraints."""
    digital_twin_enabled = bool(twin_policy.get("digital_twin_enabled", True))
    persona_mirroring = bool(twin_policy.get("persona_mirroring", True))
    autonomy_mode = str(twin_policy.get("twin_autonomy_mode", "draft_only"))
    require_approval = bool(twin_policy.get("twin_require_approval", True))
    mirror_intensity = float(twin_policy.get("twin_mirror_intensity", 0.8))

    task_note = TASK_PROMPT_NOTES.get(task_type, TASK_PROMPT_NOTES["generic"])
    style_note = _mirror_style_note(mirror_intensity)

    if not digital_twin_enabled:
        twin_behavior = (
            "Digital twin is disabled. Operate as a standard high-quality assistant with no personal mirroring."
        )
    elif not persona_mirroring:
        twin_behavior = (
            "Persona mirroring is disabled. Keep outputs clear and useful, avoid user-style imitation."
        )
    else:
        twin_behavior = (
            "Digital twin mode is active. Match the user's communication style and behavioral tendencies while remaining accurate."
        )

    approval_note = (
        "Outputs must be approval-ready drafts. Do not imply autonomous external actions were executed."
        if require_approval
        else "You may suggest executable next actions, but do not claim real-world execution."
    )

    snapshot_block = f"Latest persona snapshot: {snapshot_summary}" if snapshot_summary else "Latest persona snapshot: unavailable"

    return f"""You are Mirror Assistant, a general-purpose productivity assistant with digital twin behavior.

Core objective:
- Solve the user's task correctly.
- When allowed by policy, express the solution in the user's authentic communication style.

Policy controls:
- Twin enabled: {digital_twin_enabled}
- Persona mirroring: {persona_mirroring}
- Autonomy mode: {autonomy_mode}
- Approval required: {require_approval}
- Mirror intensity: {mirror_intensity:.2f}

Twin behavior:
{twin_behavior}
{style_note}

Task route:
- Task type: {task_type}
- Task instruction: {task_note}

Safety and execution constraints:
- Never claim an external action was completed.
- Avoid fabricated facts, references, or outcomes.
- If the request lacks required context, ask one concise clarification.
- {approval_note}

Persona grounding signals:
Communication profile:
{communication_summary}

Personality profile:
{personality_summary}

{snapshot_block}

STRICT PRIORITY ORDER:
1. Understand and execute the explicit user task exactly as requested.
2. Preserve the requested topic, purpose, and output format.
3. Apply persona style adaptation only after task correctness is satisfied.

Response format guidance:
- Keep the answer practical and directly usable.
- For drafting tasks, return a polished final draft first.
- For Q/A tasks, answer first then concise supporting detail.
- For planning tasks, return ordered steps with priorities.
- If the request is ambiguous, ask one concise clarification question.
"""


def _title_case_name(value: str) -> str:
    parts = re.split(r"\s+", value.strip())
    normalized = []
    for part in parts:
        token = part.strip()
        if not token:
            continue
        lowered = token.lower().rstrip(".")
        if lowered in {"mr", "mrs", "ms", "dr"}:
            normalized.append(lowered.title() + ".")
        else:
            normalized.append(token[:1].upper() + token[1:])
    return " ".join(normalized)


def _clean_recipient_phrase(value: str) -> str:
    tokens = re.split(r"\s+", (value or "").strip())
    stop_tokens = {"that", "who", "which", "because", "about"}
    while tokens and tokens[-1].lower().rstrip(".,") in stop_tokens:
        tokens.pop()
    return " ".join(tokens).strip()


def _extract_email_context(message: str) -> Dict[str, Optional[str]]:
    text = (message or "").strip()
    lowered = text.lower()

    recipient = None
    titled_match = re.search(r"\bto\s+((?:mr|mrs|ms|dr)\.?\s+[a-z]+(?:\s+[a-z]+)?)", text, flags=re.IGNORECASE)
    if titled_match:
        recipient = _title_case_name(_clean_recipient_phrase(titled_match.group(1)))
    else:
        named_match = re.search(r"\bto\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", text)
        if named_match:
            recipient = _clean_recipient_phrase(named_match.group(1))

    reason = None
    reason_match = re.search(r"\bdue to\s+(.+?)(?:[.?!]|$)", text, flags=re.IGNORECASE)
    if reason_match:
        reason = reason_match.group(1).strip()

    event = "meeting"
    event_match = re.search(r"\b(meeting|class|session|call|appointment|event)\b", lowered)
    if event_match:
        event = event_match.group(1)

    cannot_attend = bool(
        re.search(
            r"\b(will not attend|won't attend|cannot attend|can't attend|unable to attend|not be attending)\b",
            lowered,
        )
    )

    return {
        "recipient": recipient,
        "reason": reason,
        "event": event,
        "cannot_attend": "yes" if cannot_attend else None,
    }


def build_assistant_fallback_reply(message: str, task_type: str) -> str:
    """Deterministic fallback reply when model response is unavailable."""
    trimmed = (message or "").strip()
    if task_type == "email_draft":
        context = _extract_email_context(trimmed)
        recipient = context.get("recipient")
        reason = context.get("reason")
        event = context.get("event") or "meeting"

        subject = f"Unable to Attend the {event.title()}"
        salutation = f"Hi {recipient}," if recipient else "Hi,"
        reason_clause = f" due to {reason}" if reason else ""

        return (
            f"Subject: {subject}\n\n"
            f"{salutation}\n\n"
            f"I wanted to let you know that I will not be attending the {event}{reason_clause}. "
            "I apologize for the inconvenience.\n\n"
            "Best regards,"
        )
    if task_type == "message_draft":
        target_match = re.search(r"\bto\s+(.+?)\s+that\s+(.+)$", trimmed, flags=re.IGNORECASE)
        if target_match:
            target = _clean_recipient_phrase(target_match.group(1))
            content = target_match.group(2).strip()
            if content and content[-1] not in ".!?":
                content = content + "."
            if target:
                return f"Here is a ready-to-send draft: Hi {target}, {content[:1].upper() + content[1:]}"

        cleaned = re.sub(
            r"^(can you|could you|please|help me|i need you to|i want you to)\s+",
            "",
            trimmed,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"^(draft|write|compose)\s+(me\s+)?(an?\s+)?(message|text|dm)?\s*(saying)?\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        ).strip(" :")
        if cleaned:
            if cleaned[-1] not in ".!?":
                cleaned = cleaned + "."
            return f"Here is a ready-to-send draft: {cleaned[:1].upper() + cleaned[1:]}"
        return "Here is a clean draft you can send: I wanted to check in and align on next steps."
    if task_type == "rewrite":
        return "I can rewrite this in your style. Paste the exact text you want rewritten."
    if task_type == "summarize":
        return "Please share the text or notes to summarize, and I will return key points plus action items."
    if task_type == "planning":
        return "Plan: 1) Define outcome, 2) Break into steps, 3) Prioritize by impact and deadline, 4) Execute first step today."
    if task_type == "brainstorm":
        return "Options: 1) Fast pragmatic approach, 2) High-quality deep approach, 3) Hybrid approach balancing speed and quality."
    if task_type == "qa":
        return "I can answer this directly. Share any missing context, and I will give a precise answer."

    if trimmed:
        return "I can draft this now. Share audience, goal, and preferred tone (or say 'use a neutral professional tone')."
    return "Tell me what you want to accomplish, and I will draft it in your style."
