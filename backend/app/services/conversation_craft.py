"""What makes Reflectra's replies feel human.

Shared by both modes:
  - load_moment_context: who the user is, what time it is for them, how long
    since they last talked, and what they've shared in earlier chats.
  - reply_budget: how long a reply should be, from how much the user wrote.
  - clean_reply: strip assistant-style formatting without mangling sentences.

Mirror mode:
  - load_voice_samples / voice_stats: real messages the user wrote, so the
    mirror can copy their actual texting style instead of guessing it.
  - apply_voice_surface: deterministic casing/punctuation matching.

Everything here is read-only against the database.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Message, User

EMOJI_REGEX = re.compile(r"[\U0001F300-\U0001FAFF☀-➿]")

# Phrases that instantly make a reply sound like a chatbot or a therapist.
ASSISTANT_TELLS = [
    "as an ai", "i'm an ai", "i am an ai", "language model",
    "it sounds like", "i hear you", "that's completely valid", "that's valid",
    "it's okay to feel", "it's completely okay", "it's natural to feel",
    "have you considered", "how does that make you feel", "i'm here for you",
    "i'm here to help", "let me know if", "feel free to", "hope this helps",
    "remember to be kind to yourself", "you've got this", "great question",
    "highlight reel", "it's not a race", "be gentle with yourself", "everyone moves at their own pace",
    "you're doing better than you think",
    # Fake familiarity: claims about their past feelings they never shared.
    "i know how much you", "i know you've been", "as always", "like you always",
]


@dataclass
class MomentContext:
    display_name: Optional[str] = None
    local_time: Optional[str] = None
    gap_note: Optional[str] = None
    earlier_shares: List[str] = field(default_factory=list)


@dataclass
class VoiceStats:
    sample_count: int = 0
    lowercase_ratio: float = 0.0     # share of messages written without capital letters
    no_end_punct_ratio: float = 0.0  # share of messages that end without . ! ?
    emoji_ratio: float = 0.0         # share of messages containing an emoji
    avg_words: float = 0.0


def _first_name(display_name: Optional[str]) -> Optional[str]:
    if not display_name:
        return None
    first = display_name.strip().split()[0]
    return first[:1].upper() + first[1:] if first else None


def _gap_note(last_seen: Optional[datetime]) -> Optional[str]:
    if last_seen is None:
        return "This is the first time they've talked to you."
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    hours = (datetime.now(timezone.utc) - last_seen).total_seconds() / 3600
    if hours < 1:
        return None
    if hours < 20:
        return "You talked earlier today."
    days = int(hours // 24) or 1
    if days == 1:
        return "Last time you talked was yesterday."
    if days < 14:
        return f"Last time you talked was {days} days ago."
    return f"It's been a while ({days} days) since you last talked."


async def load_moment_context(
    db: AsyncSession,
    user_id: UUID,
    current_conversation_id: Optional[UUID],
    client_local_time: Optional[str] = None,
    share_limit: int = 8,
) -> MomentContext:
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()

    last_seen_stmt = select(Message.created_at).where(Message.user_id == user_id, Message.role == "user")
    if current_conversation_id is not None:
        last_seen_stmt = last_seen_stmt.where(Message.conversation_id != current_conversation_id)
    last_seen = (await db.execute(last_seen_stmt.order_by(Message.created_at.desc()).limit(1))).scalar_one_or_none()

    shares_stmt = select(Message.content).where(Message.user_id == user_id, Message.role == "user")
    if current_conversation_id is not None:
        shares_stmt = shares_stmt.where(Message.conversation_id != current_conversation_id)
    recent = (await db.execute(shares_stmt.order_by(Message.created_at.desc()).limit(40))).scalars().all()

    # Keep messages with some substance; skip greetings and one-word replies.
    earlier_shares: List[str] = []
    for text in recent:
        cleaned = " ".join((text or "").split())
        if len(cleaned.split()) >= 6:
            earlier_shares.append(cleaned[:220])
        if len(earlier_shares) >= share_limit:
            break

    return MomentContext(
        display_name=_first_name(user.display_name if user else None),
        local_time=(client_local_time or "").strip()[:60] or None,
        gap_note=_gap_note(last_seen),
        earlier_shares=list(reversed(earlier_shares)),
    )


def reply_budget(user_text: str, mode: str) -> Dict[str, object]:
    """Reply length guidance and token cap, scaled to how much the user wrote."""
    words = len((user_text or "").split())
    if words <= 6:
        hint = "Keep it short: one line, maybe two."
        max_tokens = 140
    elif words <= 40:
        hint = "Keep it to a few sentences at most."
        max_tokens = 260
    else:
        hint = "They wrote a lot, so a fuller reply is fine, but never more than two short paragraphs."
        max_tokens = 480
    if mode == "mirror":
        max_tokens = max(160, int(max_tokens * 0.9))
    return {"hint": hint, "max_tokens": max_tokens, "user_words": words}


def clean_reply(text: str) -> str:
    """Remove assistant-style formatting while leaving sentences intact."""
    out = (text or "").strip()
    out = re.sub(r"^#{1,6}\s*", "", out, flags=re.MULTILINE)  # markdown headings
    out = re.sub(r"\*\*(.+?)\*\*", r"\1", out)                 # bold
    out = re.sub(r"(?<!\w)\*(?!\s)(.+?)(?<!\s)\*(?!\w)", r"\1", out)  # italics
    out = re.sub(r"^(?:Reflectra|Mirror|Assistant)\s*:\s*", "", out, flags=re.IGNORECASE)
    out = re.sub(r"\s*[\u2014\u2013]\s*", ", ", out)  # em/en dashes look machine-written in chat
    out = re.sub(r",\s*([.!?])", r"\1", out)
    out = re.sub(r";\s+(\w)", lambda m: ". " + m.group(1).upper(), out)  # semicolons read as essay prose
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip().strip('"').strip()


def has_assistant_tells(text: str) -> bool:
    lower = (text or "").lower()
    return any(tell in lower for tell in ASSISTANT_TELLS)


def format_moment_block(ctx: MomentContext, schedule_lines: Optional[List[str]] = None) -> str:
    lines: List[str] = []
    if ctx.display_name:
        lines.append(f"- Their name is {ctx.display_name} (use it rarely, like a friend would).")
    if ctx.local_time:
        lines.append(f"- It's {ctx.local_time} where they are.")
    if ctx.gap_note:
        lines.append(f"- {ctx.gap_note}")
    for line in schedule_lines or []:
        lines.append(f"- {line}")
    if ctx.earlier_shares:
        lines.append("- Things they told you in earlier chats (oldest first):")
        lines.extend(f'    "{share}"' for share in ctx.earlier_shares)
    return "\n".join(lines) if lines else "- Nothing yet; this is a fresh start."


# ---------------------------------------------------------------------------
# Mirror mode: the user's real voice
# ---------------------------------------------------------------------------

async def load_voice_samples(
    db: AsyncSession,
    user_id: UUID,
    exclude_text: Optional[str] = None,
    limit: int = 12,
) -> List[str]:
    """Pick real user messages that show how they write, varied in length."""
    rows = (
        await db.execute(
            select(Message.content)
            .where(Message.user_id == user_id, Message.role == "user")
            .order_by(Message.created_at.desc())
            .limit(150)
        )
    ).scalars().all()

    seen = set()
    candidates: List[str] = []
    for text in rows:
        cleaned = (text or "").strip()
        key = cleaned.lower()
        if not cleaned or key in seen or cleaned == (exclude_text or "").strip():
            continue
        if len(cleaned) > 280 or len(cleaned.split()) < 2:
            continue
        seen.add(key)
        candidates.append(cleaned)

    # Spread across short / medium / long so the model sees their whole range.
    short = [c for c in candidates if len(c.split()) <= 6]
    medium = [c for c in candidates if 6 < len(c.split()) <= 20]
    long = [c for c in candidates if len(c.split()) > 20]
    picked: List[str] = []
    buckets = [medium, short, long]
    while len(picked) < limit and any(buckets):
        for bucket in buckets:
            if bucket and len(picked) < limit:
                picked.append(bucket.pop(0))
    return picked


def voice_stats(samples: List[str]) -> VoiceStats:
    if not samples:
        return VoiceStats()
    n = len(samples)
    lowercase = sum(1 for s in samples if not re.search(r"[A-Z]", s))
    no_end = sum(1 for s in samples if not re.search(r"[.!?…]\s*$", s))
    emoji = sum(1 for s in samples if EMOJI_REGEX.search(s))
    words = sum(len(s.split()) for s in samples)
    return VoiceStats(
        sample_count=n,
        lowercase_ratio=lowercase / n,
        no_end_punct_ratio=no_end / n,
        emoji_ratio=emoji / n,
        avg_words=words / n,
    )


def describe_voice(stats: VoiceStats) -> str:
    if stats.sample_count == 0:
        return "No samples yet: keep it natural, casual and short."
    parts = []
    if stats.lowercase_ratio >= 0.6:
        parts.append("writes almost entirely in lowercase")
    elif stats.lowercase_ratio <= 0.2:
        parts.append("uses normal capitalization")
    if stats.no_end_punct_ratio >= 0.6:
        parts.append("usually skips the final period")
    if stats.emoji_ratio >= 0.25:
        parts.append("uses emojis fairly often")
    elif stats.emoji_ratio == 0:
        parts.append("never uses emojis")
    parts.append(f"messages average about {round(stats.avg_words)} words")
    return "; ".join(parts) + "."


def apply_voice_surface(text: str, stats: VoiceStats) -> str:
    """Match casing and end punctuation to the user's habits (casual replies only)."""
    out = (text or "").strip()
    if not out or stats.sample_count < 4:
        return out
    if stats.lowercase_ratio >= 0.7:
        out = out.lower()
    if stats.no_end_punct_ratio >= 0.7 and out.endswith(".") and not out.endswith("..."):
        out = out[:-1]
    if stats.emoji_ratio == 0:
        out = EMOJI_REGEX.sub("", out).strip()
    return out
