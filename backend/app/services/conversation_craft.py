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

import asyncio
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ExternalInput, Message, User

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
    earlier_shares: List[str] = field(default_factory=list)   # most recent things they said
    related_memories: List[str] = field(default_factory=list)  # past exchanges relevant to now
    background_notes: List[str] = field(default_factory=list)  # facts from an imported description
    follow_ups: List[str] = field(default_factory=list)       # things they said they'd do, now due


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


MEMORY_STOPWORDS = frozenset(
    """a about after again all also am an and any are aren as at be because been before being but by can cant could did
    didn do does doesn doing don dont down for from get got had has have having he her here hers him his how i id if ill im
    in into is isn it its ive just know like ll me more most my myself no nor not now of off on once only or other our out
    over own re really s same she should so some such t than that thats the their them then there these they thing things
    think this those through to too u under until up ur ve very was wasn we were what when where which while who why will
    with would y yeah you your yours yourself gonna wanna kinda lol idk tbh ngl bro man okay ok yes nah feel feeling today
    actually still much even make makes made want need going something anything everything one two time way
    hello hey hi sup whats tonight tomorrow yesterday good bad tell give new first right well thanks thank please help
    let lets say said see look come came back lot bit maybe sure fine cool nice great
    keep kept get gets getting sit stay start try put take took whenever always never every ever
    around while already yet soon later away
    lowkey highkey fr frfr bruh bro gang wassup yo ion ima imma finna tryna deadass lmao lmfao ong istg
    rn tn tmrw tmr ukwim iykyk shii shi shit fuck fucking damn dude bestie fam aight bet ight allat""".split()
)


def _memory_tokens(text: str) -> List[str]:
    """Content words, lightly stemmed, for lexical recall."""
    tokens = []
    for word in re.findall(r"[a-z0-9']+", (text or "").lower()):
        word = word.strip("'").split("'")[0]  # what's -> what, don't -> don
        if len(word) < 3 or word in MEMORY_STOPWORDS:
            continue
        for suffix in ("ing", "ed", "es", "s"):
            if word.endswith(suffix) and len(word) - len(suffix) >= 3:
                word = word[: -len(suffix)]
                if len(word) > 3 and word[-1] == word[-2] and word[-1] not in "aeiousl":
                    word = word[:-1]  # stopping -> stop, planned -> plan
                break
        if word not in MEMORY_STOPWORDS:  # thinking -> think, which is a stopword
            tokens.append(word)
    return tokens


RECENT_SHARE_WINDOW = timedelta(days=3)


def _aware(value: Optional[datetime]) -> datetime:
    if value is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _when(created_at: Optional[datetime]) -> str:
    if created_at is None:
        return "earlier"
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    days = (datetime.now(timezone.utc) - created_at).days
    if days <= 0:
        return "earlier today"
    if days == 1:
        return "yesterday"
    if days < 14:
        return f"{days} days ago"
    if days < 60:
        return f"{days // 7} weeks ago"
    return f"{days // 30} months ago"


# A past exchange counts as related in meaning only if it is both close to the query
# and stands out from this person's own baseline (everyone's messages resemble each
# other a little). Measured on real history with gemini-embedding-001: true matches
# sat at similarity 0.65-0.75 and 2.8-7.7 deviations above the person's average;
# scripts/backend/memory_eval.py re-measures it.
SEMANTIC_MIN_SIMILARITY = 0.62
SEMANTIC_MIN_STANDOUT = 2.5
# A keyword match whose meaning is no closer than the person's average is a coincidence
# of filler words ("what's up" matching "what's good fuel"), and is dropped.
LEXICAL_MIN_STANDOUT = 0.5
RANK_FUSION_K = 10.0  # reciprocal-rank fusion: score = sum of 1 / (K + rank in each list)


def lexical_ranking(query_text: str, exchanges: List[Dict[str, object]]) -> List[Dict[str, object]]:
    """Past exchanges sharing words with the query, best first.

    Rare shared words count for more (IDF), long exchanges are not favoured for
    their length, and an exchange must share at least one distinctive word or three
    ordinary ones.
    """
    query = set(_memory_tokens(query_text))
    if len(query) < 3 or not exchanges:
        return []  # greetings and one-liners don't call for recall

    doc_tokens = [set(_memory_tokens(f"{e.get('user', '')} {e.get('assistant', '')}")) for e in exchanges]
    total = len(exchanges)
    doc_freq: Dict[str, int] = {}
    for tokens in doc_tokens:
        for token in tokens:
            doc_freq[token] = doc_freq.get(token, 0) + 1

    scored = []
    for exchange, tokens in zip(exchanges, doc_tokens):
        shared = query & tokens
        if not shared:
            continue
        idf = {t: math.log(1 + total / doc_freq[t]) for t in shared}
        distinctive = sum(1 for t in shared if doc_freq[t] <= max(2, total * 0.03))
        if distinctive == 0 and len(shared) < 3:
            continue  # a couple of everyday words in common is coincidence
        # Squared so one rare shared word ("instagram") outweighs several common ones.
        score = sum(value * value for value in idf.values()) / math.sqrt(8 + len(tokens))
        scored.append((score, exchange))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [exchange for _, exchange in scored]


def semantic_ranking(
    query_text: str,
    exchanges: List[Dict[str, object]],
    similarities: Optional[Dict[object, Dict[str, float]]],
) -> List[Dict[str, object]]:
    """Past exchanges close in meaning to the query, best first, whatever words they used."""
    if not similarities or len(_memory_tokens(query_text)) < 2:
        return []
    close = []
    for exchange in exchanges:
        match = similarities.get(exchange.get("id"))
        if match and match["similarity"] >= SEMANTIC_MIN_SIMILARITY and match["standout"] >= SEMANTIC_MIN_STANDOUT:
            close.append((match["similarity"], exchange))
    close.sort(key=lambda pair: pair[0], reverse=True)
    return [exchange for _, exchange in close]


def _keyword_match_holds_up(exchange: Dict[str, object], similarities: Optional[Dict[object, Dict[str, float]]]) -> bool:
    """With meaning available, a keyword match must also be closer than average in meaning."""
    if not similarities or not exchange.get("embedded"):
        return True  # nothing to check it against
    match = similarities.get(exchange.get("id"))
    return bool(match) and match["standout"] >= LEXICAL_MIN_STANDOUT


def rank_memories(
    query_text: str,
    exchanges: List[Dict[str, object]],
    limit: int = 4,
    similarities: Optional[Dict[object, Dict[str, float]]] = None,
) -> List[Dict[str, object]]:
    """Pick the past exchanges most related to what the user is saying now.

    Two rankings are fused: shared words (always available) and closeness in
    meaning (when embeddings are). An exchange found by both rises to the top; one
    found by either still qualifies, so "exam stress" recalls "finals are killing me".
    """
    by_words = [e for e in lexical_ranking(query_text, exchanges) if _keyword_match_holds_up(e, similarities)]
    rankings = [by_words, semantic_ranking(query_text, exchanges, similarities)]
    fused: Dict[int, float] = {}
    by_key: Dict[int, Dict[str, object]] = {}
    for ranking in rankings:
        for rank, exchange in enumerate(ranking):
            key = id(exchange)
            by_key[key] = exchange
            fused[key] = fused.get(key, 0.0) + 1.0 / (RANK_FUSION_K + rank)

    picked: List[Dict[str, object]] = []
    seen_conversations: Dict[object, int] = {}
    for key in sorted(fused, key=lambda k: fused[k], reverse=True):
        exchange = by_key[key]
        # At most two memories per past conversation, so recall spans their history.
        conversation = exchange.get("conversation_id")
        if seen_conversations.get(conversation, 0) >= 2:
            continue
        seen_conversations[conversation] = seen_conversations.get(conversation, 0) + 1
        picked.append(exchange)
        if len(picked) >= limit:
            break
    return picked


def _format_memory(exchange: Dict[str, object]) -> str:
    said = " ".join(str(exchange.get("user") or "").split())[:240]
    line = f'{_when(exchange.get("created_at"))}, they said: "{said}"'
    reply = " ".join(str(exchange.get("assistant") or "").split())
    if reply:
        line += f' You replied: "{reply[:200]}"'
    return line


async def load_background_notes(db: AsyncSession, user_id: UUID) -> List[str]:
    """Facts about the user taken from their latest Persona Bootstrap import, if any."""
    try:
        markers = (
            await db.execute(
                select(ExternalInput.extracted_markers)
                .where(ExternalInput.user_id == user_id, ExternalInput.source == "persona_bootstrap")
                .order_by(ExternalInput.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
    except Exception:
        await db.rollback()
        return []
    notes = (markers or {}).get("notes") if isinstance(markers, dict) else None
    return [str(note)[:200] for note in (notes or []) if note][:6]


async def load_moment_context(
    db: AsyncSession,
    user_id: UUID,
    current_conversation_id: Optional[UUID],
    client_local_time: Optional[str] = None,
    query_text: str = "",
    share_limit: int = 4,
    history_window: int = 1200,
    message_text: str = "",
    use_meaning: bool = True,
    follow_up_tz: Optional[int] = None,
) -> MomentContext:
    """Who they are right now, plus memory of earlier conversations.

    Memory has two parts: the last few substantial things they said (recency)
    and past exchanges related to `query_text` (relevance), drawn from up to
    `history_window` earlier messages across all their conversations. Relevance
    uses shared words and, when embeddings are available, closeness in meaning.

    `follow_up_tz` (the user's UTC offset in minutes) is passed only for the first
    message of a conversation: that is when due follow-ups are raised, and marked asked.
    """
    from app.services import embedding_service

    # The embedding request runs while the database is read, so it costs little extra time.
    embed_task = None
    if use_meaning and query_text.strip() and embedding_service.embeddings_available():
        await embedding_service.ensure_dimensions(db)  # one tiny query, first time only
        embed_task = asyncio.create_task(embedding_service.embed_for_recall(query_text))

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()

    stmt = select(
        Message.role,
        Message.content,
        Message.created_at,
        Message.conversation_id,
        Message.id,
        Message.embedding.is_not(None).label("embedded"),
    ).where(Message.user_id == user_id)
    if current_conversation_id is not None:
        stmt = stmt.where(Message.conversation_id != current_conversation_id)
    rows = (await db.execute(stmt.order_by(Message.created_at.desc()).limit(history_window))).all()
    rows = list(reversed(rows))  # oldest first

    # Pair each user message with the reply that followed it in the same conversation.
    exchanges: List[Dict[str, object]] = []
    for index, (role, content, created_at, conversation_id, message_id, embedded) in enumerate(rows):
        if role != "user":
            continue
        cleaned = " ".join((content or "").split())
        if len(cleaned.split()) < 5:
            continue  # greetings and one-liners carry no memory
        reply = ""
        for next_role, next_content, _, next_conversation, _, _ in rows[index + 1 : index + 3]:
            if next_conversation == conversation_id and next_role == "assistant":
                reply = next_content or ""
                break
        exchanges.append(
            {
                "id": message_id,
                "embedded": bool(embedded),
                "user": cleaned,
                "assistant": reply,
                "created_at": created_at,
                "conversation_id": conversation_id,
            }
        )

    last_seen = next((created_at for role, _, created_at, _, _, _ in reversed(rows) if role == "user"), None)
    background_notes = await load_background_notes(db, user_id)
    # "Recent" means the last few days: a months-old message is a memory, not something on their mind.
    recent_since = datetime.now(timezone.utc) - RECENT_SHARE_WINDOW
    recent = [e for e in exchanges if _aware(e["created_at"]) >= recent_since][-share_limit:]

    similarities: Dict[object, Dict[str, float]] = {}
    if embed_task is not None:
        try:
            query_vector = await embed_task
        except Exception:
            query_vector = None
        if query_vector:
            similarities = await embedding_service.semantic_matches(db, user_id, query_vector, current_conversation_id)
    related = [e for e in rank_memories(query_text, exchanges, similarities=similarities) if e not in recent]

    follow_ups: List[str] = []
    if follow_up_tz is not None:
        from app.services import followup_service

        try:
            follow_ups = await followup_service.due_for_asking(db, user_id, follow_up_tz)
        except Exception:
            await db.rollback()

    return MomentContext(
        display_name=_first_name(user.display_name if user else None),
        local_time=(client_local_time or "").strip()[:60] or None,
        gap_note=_gap_note(last_seen),
        earlier_shares=[f'{_when(e["created_at"])}: "{str(e["user"])[:220]}"' for e in recent],
        related_memories=[_format_memory(e) for e in related],
        background_notes=background_notes,
        follow_ups=follow_ups,
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
    if ctx.background_notes:
        lines.append("- Background they've shared about themselves:")
        lines.extend(f"    {note}" for note in ctx.background_notes)
    if ctx.related_memories:
        lines.append("- From earlier conversations, related to what they're saying now:")
        lines.extend(f"    {memory}" for memory in ctx.related_memories)
    if ctx.earlier_shares:
        lines.append(
            "- Background only, what they talked about most recently (usually unrelated to now; "
            "don't bring any of it up unless they do or it plainly connects):"
        )
        lines.extend(f"    {share}" for share in ctx.earlier_shares)
    if ctx.follow_ups:
        lines.append(
            "- Something to follow up on. Unless they've come with something heavy, ask how ONE of these went, "
            "once, in passing, the way a friend who remembered would. No lecture if they didn't do it, "
            "and if they brush it off, drop it for good:"
        )
        lines.extend(f"    {item}" for item in ctx.follow_ups)
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
    """Pick real messages the user wrote that show how they write, varied in length.

    Mostly from their conversations here; if they imported their own texts from
    elsewhere, a share of the samples comes from those (most of them while there is
    little written here yet).
    """
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

    from app.services import voice_import_service

    imported = [
        text
        for text in reversed(await voice_import_service.load_imported_samples(db, user_id))  # newest first
        if text.lower() not in seen and text != (exclude_text or "").strip()
    ]
    from_import = min(len(imported), voice_import_service.imported_share(len(candidates), limit)) if imported else 0
    own = _spread_by_length(candidates, limit - from_import)
    borrowed = _spread_by_length(imported[:80], limit - len(own))  # also fills in when own messages run short
    return own + borrowed


def _spread_by_length(candidates: List[str], limit: int) -> List[str]:
    """Take from short / medium / long in turn so the model sees their whole range."""
    if limit <= 0:
        return []
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
