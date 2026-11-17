"""Learn someone's voice from messages they wrote elsewhere.

Mirror mode copies how a person writes from real samples of their writing. A new
user has none, so this lets them hand over a chat export (WhatsApp, Telegram,
ChatGPT) or just a pile of their own messages, and Mirror has their voice on day one.

Privacy rules:
  - Only the chosen sender's messages are kept. Everything other people wrote in the
    chat is read to find the message boundaries and then thrown away.
  - Media placeholders, links, phone numbers and e-mail addresses are dropped.
  - At most MAX_SAMPLES messages are stored, and "Erase" removes them.

What it changes: the samples Mirror imitates, and the "voice" part of overall
confidence (imported texts count half). It does not touch traits; those come from
conversations here.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ExternalInput

SOURCE = "voice_import"
MAX_INPUT_CHARS = 3_000_000
MAX_SAMPLES = 400
MIN_SAMPLES = 15
MAX_SAMPLE_CHARS = 280
SELF_SENDER = "You"

# "[12/03/24, 10:15:32 PM] Asha: hi"   (iPhone)
# "12/03/2024, 22:15 - Asha: hi"        (Android)
_WHATSAPP_LINE = re.compile(
    r"^[‎‏﻿]*\[?"
    r"(\d{1,4}[./-]\d{1,2}[./-]\d{1,4}),?\s+"
    r"(\d{1,2}[:.]\d{2}(?:[:.]\d{2})?(?:\s?[APap]\.?\s?[Mm]\.?)?)"
    r"\]?\s*(?:-\s*)?"
    r"([^:\n]{1,60}?):\s(.*)$"
)
_WHATSAPP_ANY_HEADER = re.compile(
    r"^[‎‏﻿]*\[?\d{1,4}[./-]\d{1,2}[./-]\d{1,4},?\s+\d{1,2}[:.]\d{2}"
)
_NOT_WRITING = re.compile(
    r"(<media omitted>|\b(?:image|video|audio|sticker|gif|document|contact card) omitted\b|<attached:|"
    r"this message was deleted|you deleted this message|message was edited|missed (?:voice|video) call|"
    r"^null$|waiting for this message|end-to-end encrypted|live location|\(file attached\))",
    re.IGNORECASE,
)
_URL = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_PHONE = re.compile(r"(?<!\w)\+?\d[\d\s().-]{7,}\d(?!\w)")


class VoiceImportError(ValueError):
    """The upload can't be used; the message is safe to show to the user."""


@dataclass
class ParsedExport:
    format: str  # "whatsapp" | "telegram" | "chatgpt" | "lines"
    senders: Dict[str, List[str]] = field(default_factory=dict)  # sender -> their messages, oldest first

    def sender_counts(self) -> List[Dict[str, object]]:
        ranked = sorted(self.senders.items(), key=lambda item: len(item[1]), reverse=True)
        return [{"name": name, "messages": len(messages)} for name, messages in ranked]


# --------------------------------------------------------------------------- parsing


def _parse_whatsapp(text: str) -> Optional[ParsedExport]:
    lines = text.splitlines()
    headers = sum(1 for line in lines[:400] if _WHATSAPP_LINE.match(line))
    if headers < 3:
        return None
    senders: Dict[str, List[str]] = {}
    current: Optional[List[str]] = None
    for line in lines:
        match = _WHATSAPP_LINE.match(line)
        if match:
            sender = match.group(3).strip().lstrip("~").strip()
            current = senders.setdefault(sender, [])
            current.append(match.group(4))
        elif _WHATSAPP_ANY_HEADER.match(line):
            current = None  # a system line ("Asha added you"): belongs to nobody
        elif current is not None and line.strip():
            current[-1] = f"{current[-1]}\n{line}"  # a message that ran onto another line
    return ParsedExport("whatsapp", senders) if senders else None


def _telegram_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):  # mixed plain strings and {"type": "link", "text": "..."} pieces
        return "".join(part if isinstance(part, str) else str(part.get("text", "")) for part in value if part)
    return ""


def _parse_json(text: str) -> Optional[ParsedExport]:
    stripped = text.lstrip()
    if not stripped or stripped[0] not in "[{":
        return None
    try:
        data = json.loads(stripped)
    except (json.JSONDecodeError, RecursionError):
        return None

    # Telegram: {"messages": [{"type": "message", "from": "Asha", "text": ...}]}
    if isinstance(data, dict) and isinstance(data.get("messages"), list):
        senders: Dict[str, List[str]] = {}
        for item in data["messages"]:
            if isinstance(item, dict) and item.get("type", "message") == "message" and item.get("from"):
                body = _telegram_text(item.get("text"))
                if body:
                    senders.setdefault(str(item["from"]), []).append(body)
        return ParsedExport("telegram", senders) if senders else None

    # ChatGPT: [{"mapping": {id: {"message": {"author": {"role": "user"}, "content": {"parts": [...]}}}}}]
    conversations = data if isinstance(data, list) else [data]
    mine: List[tuple] = []
    for conversation in conversations:
        mapping = conversation.get("mapping") if isinstance(conversation, dict) else None
        if not isinstance(mapping, dict):
            continue
        for node in mapping.values():
            message = node.get("message") if isinstance(node, dict) else None
            if not isinstance(message, dict) or (message.get("author") or {}).get("role") != "user":
                continue
            parts = (message.get("content") or {}).get("parts") or []
            body = " ".join(part for part in parts if isinstance(part, str)).strip()
            if body:
                mine.append((message.get("create_time") or 0, body))
    if mine:
        mine.sort(key=lambda pair: pair[0])
        return ParsedExport("chatgpt", {SELF_SENDER: [body for _, body in mine]})
    return None


def parse_export(text: str) -> ParsedExport:
    """Work out what kind of export this is and split it by sender."""
    if not text or not text.strip():
        raise VoiceImportError("That file is empty.")
    if len(text) > MAX_INPUT_CHARS:
        text = text[-MAX_INPUT_CHARS:]  # the most recent part is what matters
    parsed = _parse_json(text) or _parse_whatsapp(text)
    if parsed:
        return parsed
    # Anything else: treat each line as one message the user wrote themselves.
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return ParsedExport("lines", {SELF_SENDER: lines})


# --------------------------------------------------------------------------- cleaning


def clean_message(raw: str) -> Optional[str]:
    """One message, made safe to keep: no media stubs, links, e-mails or phone numbers."""
    text = (raw or "").replace("‎", "").replace("‏", "").strip()
    if not text or _NOT_WRITING.search(text):
        return None
    text = _URL.sub("", text)
    text = _EMAIL.sub("", text)
    text = _PHONE.sub("", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s*\n\s*", "\n", text).strip()
    if len(text) > MAX_SAMPLE_CHARS or len(text.split()) < 2:
        return None  # essays and one-word replies say little about everyday texting
    if not re.search(r"[^\W\d_]", text):
        return None  # only digits, punctuation or emoji
    return text


def select_samples(messages: Sequence[str], limit: int = MAX_SAMPLES) -> List[str]:
    """The most recent distinct, usable messages, oldest first."""
    kept: List[str] = []
    seen = set()
    for raw in reversed(list(messages)):
        cleaned = clean_message(raw)
        if not cleaned or cleaned.lower() in seen:
            continue
        seen.add(cleaned.lower())
        kept.append(cleaned)
        if len(kept) >= limit:
            break
    kept.reverse()
    return kept


def guess_sender(parsed: ParsedExport, display_name: Optional[str]) -> Optional[str]:
    """Which sender is the user? Only answers when it is obvious."""
    names = list(parsed.senders)
    if len(names) == 1:
        return names[0]
    wanted = (display_name or "").strip().lower()
    if wanted:
        first = wanted.split()[0]
        matches = [n for n in names if n.lower() == wanted or n.lower().split()[0:1] == [first]]
        if len(matches) == 1:
            return matches[0]
    return None


def summarize(samples: Sequence[str]) -> Dict[str, object]:
    from app.services.conversation_craft import describe_voice, voice_stats

    stats = voice_stats(list(samples))
    examples = [s for s in samples if 3 <= len(s.split()) <= 18][-6:]
    return {
        "samples": len(samples),
        "description": describe_voice(stats) if samples else "",
        "avg_words": round(stats.avg_words, 1),
        "lowercase_share": round(stats.lowercase_ratio, 3),
        "emoji_share": round(stats.emoji_ratio, 3),
        "examples": examples,
    }


def read_upload(text: str, sender: Optional[str], display_name: Optional[str]) -> Dict[str, object]:
    """Everything the preview needs. Raises VoiceImportError with a message for the user."""
    parsed = parse_export(text)
    chosen = sender if sender in parsed.senders else guess_sender(parsed, display_name)
    result: Dict[str, object] = {
        "format": parsed.format,
        "senders": parsed.sender_counts()[:12],
        "sender": chosen,
        "needs_sender": chosen is None,
    }
    if chosen is None:
        return result
    samples = select_samples(parsed.senders[chosen])
    if len(samples) < MIN_SAMPLES:
        raise VoiceImportError(
            f"Only {len(samples)} usable messages from {chosen} in there. Reflectra needs at least {MIN_SAMPLES} to learn a voice."
        )
    result.update(summarize(samples))
    result["_samples"] = samples
    return result


# --------------------------------------------------------------------------- storage


async def current_import(db: AsyncSession, user_id: UUID) -> Optional[Dict[str, object]]:
    row = (
        await db.execute(
            select(ExternalInput)
            .where(ExternalInput.user_id == user_id, ExternalInput.source == SOURCE)
            .order_by(ExternalInput.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    markers = row.extracted_markers if isinstance(row.extracted_markers, dict) else {}
    return {
        "samples": int(markers.get("sample_count") or 0),
        "format": markers.get("format"),
        "description": markers.get("description"),
        "imported_at": row.created_at.isoformat() if row.created_at else None,
    }


async def save_import(db: AsyncSession, user_id: UUID, samples: Sequence[str], fmt: str) -> None:
    """Replace any earlier voice import with this one."""
    summary = summarize(samples)
    await db.execute(delete(ExternalInput).where(ExternalInput.user_id == user_id, ExternalInput.source == SOURCE))
    db.add(
        ExternalInput(
            user_id=user_id,
            source=SOURCE,
            content=f"{len(samples)} of the user's own messages, imported to learn their voice.",
            extracted_markers={
                "sample_count": len(samples),
                "format": fmt,
                "description": summary["description"],
                "samples": list(samples),
            },
            confidence_weight=0.5,
        )
    )
    await db.commit()


async def remove_import(db: AsyncSession, user_id: UUID) -> None:
    await db.execute(delete(ExternalInput).where(ExternalInput.user_id == user_id, ExternalInput.source == SOURCE))
    await db.commit()


async def load_imported_samples(db: AsyncSession, user_id: UUID) -> List[str]:
    try:
        markers = (
            await db.execute(
                select(ExternalInput.extracted_markers)
                .where(ExternalInput.user_id == user_id, ExternalInput.source == SOURCE)
                .order_by(ExternalInput.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
    except Exception:
        await db.rollback()
        return []
    samples = markers.get("samples") if isinstance(markers, dict) else None
    return [str(s) for s in samples if s] if isinstance(samples, list) else []


def imported_share(own_candidates: int, limit: int) -> int:
    """How many of Mirror's `limit` samples may come from the import.

    With little written here, the import carries Mirror (up to two thirds). Once there
    is plenty, it keeps a third: texts to friends are often the truest sample of a voice.
    """
    if own_candidates < 10:
        return (limit * 2) // 3
    if own_candidates < 40:
        return limit // 2
    return limit // 3
