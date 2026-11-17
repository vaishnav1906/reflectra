"""Meaning vectors for memory.

A message's embedding is a list of numbers that places it near other messages about
the same thing, whatever words were used ("finals are killing me" lands next to
"exam stress"). Recall uses these alongside keyword matching.

Gemini only: its embedding model returns vectors of whatever length is asked for,
so the length is read from the `messages.embedding` column itself (databases
created at different times hold 1024 or 1536). With any other provider, or on any
failure, every function here returns None and recall quietly stays keyword-only.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import math
import os
from collections import OrderedDict
from typing import Dict, List, Optional, Sequence
from uuid import UUID

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Message
from app.services import llm

logger = logging.getLogger(__name__)

DEFAULT_EMBEDDING_MODEL = "gemini-embedding-001"
DEFAULT_DIMENSIONS = 1536  # what the migrations create; the live column is checked on first use
EMBED_BATCH = 64  # texts per request
MAX_CHARS = 2000  # plenty for a chat message; keeps requests small
MIN_WORDS_TO_EMBED = 5  # same bar recall uses: shorter messages carry no memory
QUERY_TIMEOUT_SECONDS = 2.5  # recall must never hold a reply up for long

_cache: "OrderedDict[str, List[float]]" = OrderedDict()
_CACHE_SIZE = 512
_dimensions: Optional[int] = None


def dimensions() -> int:
    return _dimensions or DEFAULT_DIMENSIONS


async def ensure_dimensions(db: AsyncSession) -> int:
    """Read the embedding column's real length once per process."""
    global _dimensions
    if _dimensions is None:
        try:
            found = (
                await db.execute(
                    text(
                        "SELECT atttypmod FROM pg_attribute "
                        "WHERE attrelid = 'messages'::regclass AND attname = 'embedding'"
                    )
                )
            ).scalar()
            _dimensions = int(found) if found and int(found) > 0 else DEFAULT_DIMENSIONS
        except Exception as exc:
            logger.warning("Could not read the embedding column size (%s); assuming %s", str(exc)[:120], DEFAULT_DIMENSIONS)
            await db.rollback()
            _dimensions = DEFAULT_DIMENSIONS
    return _dimensions


def embeddings_available() -> bool:
    return llm.active_provider() == "gemini"


def _model() -> str:
    return os.getenv("GEMINI_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)


def _key(text: str) -> str:
    return hashlib.sha1(f"{_model()}|{dimensions()}|{text}".encode("utf-8")).hexdigest()


def _prepare(text: str) -> str:
    return " ".join((text or "").split())[:MAX_CHARS]


def normalize(vector: Sequence[float]) -> List[float]:
    """Unit length, so a dot product is the cosine similarity."""
    norm = math.sqrt(sum(x * x for x in vector))
    if norm == 0:
        return [0.0 for _ in vector]
    return [x / norm for x in vector]


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def worth_embedding(text: str) -> bool:
    return len((text or "").split()) >= MIN_WORDS_TO_EMBED


def cached_embedding(text: str) -> Optional[List[float]]:
    """The vector for `text` if it was embedded recently in this process (no API call)."""
    prepared = _prepare(text)
    return _cache.get(_key(prepared)) if prepared else None


def _remember(text: str, vector: List[float]) -> None:
    _cache[_key(text)] = vector
    _cache.move_to_end(_key(text))
    while len(_cache) > _CACHE_SIZE:
        _cache.popitem(last=False)


async def _request(texts: List[str], timeout: float) -> List[List[float]]:
    response = await llm._http().post(
        f"{llm.GEMINI_BASE_URL}/embeddings",
        json={"model": _model(), "input": texts, "dimensions": dimensions()},
        headers={"Authorization": f"Bearer {llm._gemini_key()}"},
        timeout=timeout,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"embedding HTTP {response.status_code}: {response.text[:200]}")
    data = sorted(response.json().get("data") or [], key=lambda item: item.get("index", 0))
    vectors = [normalize(item["embedding"]) for item in data]
    if len(vectors) != len(texts) or any(len(v) != dimensions() for v in vectors):
        raise RuntimeError("embedding response did not match the request")
    return vectors


async def embed_texts(texts: Sequence[str], timeout: float = 20.0) -> Optional[List[List[float]]]:
    """One vector per text, in order. None if embeddings are unavailable or the call fails."""
    if not embeddings_available():
        return None
    prepared = [_prepare(text) for text in texts]
    if not prepared or any(not text for text in prepared):
        return None

    missing = [text for text in dict.fromkeys(prepared) if _key(text) not in _cache]
    try:
        for start in range(0, len(missing), EMBED_BATCH):
            batch = missing[start : start + EMBED_BATCH]
            for text, vector in zip(batch, await _request(batch, timeout)):
                _remember(text, vector)
    except Exception as exc:  # timeouts, rate limits, provider errors: recall degrades, chat does not
        logger.warning("Embeddings unavailable right now (%s); recall stays keyword-only", str(exc)[:160])
        return None
    return [_cache[_key(text)] for text in prepared]


async def embed_for_recall(query_text: str) -> Optional[List[float]]:
    """Vector for the recall query, or None if it cannot be had quickly."""
    try:
        vectors = await asyncio.wait_for(
            embed_texts([query_text], timeout=QUERY_TIMEOUT_SECONDS), QUERY_TIMEOUT_SECONDS + 0.5
        )
    except asyncio.TimeoutError:
        return None
    return vectors[0] if vectors else None


def exchange_text(user_text: str, reply: str = "") -> str:
    """What gets embedded for a memory: what they said plus the reply it got.

    Measured on real history, the pair is found far more reliably than the message
    alone ("what should I have before hitting the gym" only says *food* in the reply).
    """
    said = " ".join((user_text or "").split())[:1200]
    answer = " ".join((reply or "").split())[:400]
    return f"{said}\n{answer}".strip()


async def semantic_matches(
    db: AsyncSession,
    user_id: UUID,
    query_vector: Sequence[float],
    exclude_conversation_id: Optional[UUID] = None,
    limit: int = 40,
) -> Dict[UUID, Dict[str, float]]:
    """The user's past exchanges closest in meaning to the query.

    Returns {message id: {"similarity": cosine, "standout": z}} where `standout` is how
    many standard deviations above this user's average similarity the match sits. A
    person's messages all resemble each other somewhat, so standing out from their own
    baseline is what marks a real match.
    """
    if len(query_vector) != await ensure_dimensions(db):
        return {}
    distance = Message.embedding.cosine_distance(list(query_vector))
    inner = select(Message.id.label("id"), distance.label("distance")).where(
        Message.user_id == user_id, Message.role == "user", Message.embedding.is_not(None)
    )
    if exclude_conversation_id is not None:
        inner = inner.where(Message.conversation_id != exclude_conversation_id)
    scored = inner.subquery()
    stmt = (
        select(
            scored.c.id,
            scored.c.distance,
            func.avg(scored.c.distance).over().label("mean"),
            func.stddev_pop(scored.c.distance).over().label("spread"),
            func.count().over().label("total"),
        )
        .order_by(scored.c.distance)
        .limit(limit)
    )
    try:
        rows = (await db.execute(stmt)).all()
    except Exception as exc:
        logger.warning("Semantic recall query failed (%s)", str(exc)[:160])
        await db.rollback()
        return {}
    matches: Dict[UUID, Dict[str, float]] = {}
    for message_id, dist, mean, spread, total in rows:
        spread = float(spread or 0.0)
        # With only a handful of memories there is no baseline to stand out from.
        standout = (float(mean) - float(dist)) / spread if spread > 1e-6 and int(total) >= 8 else 0.0
        matches[message_id] = {"similarity": 1.0 - float(dist), "standout": standout}
    return matches


async def backfill_embeddings(db: AsyncSession, user_id: UUID, limit: int = 24) -> int:
    """Embed up to `limit` of the user's exchanges that have no vector yet. Returns how many."""
    if not embeddings_available():
        return 0
    await ensure_dimensions(db)
    rows = (
        await db.execute(
            select(Message.id, Message.content, Message.conversation_id)
            .where(
                Message.user_id == user_id,
                Message.role == "user",
                Message.embedding.is_(None),
                func.length(Message.content) >= 20,
            )
            .order_by(Message.created_at.desc())
            .limit(limit * 2)
        )
    ).all()
    todo = [row for row in rows if worth_embedding(row[1])][:limit]
    if not todo:
        return 0

    # The reply each message got, to embed the exchange rather than the message alone.
    conversations = {row[2] for row in todo}
    thread = (
        await db.execute(
            select(Message.id, Message.role, Message.content, Message.conversation_id)
            .where(Message.user_id == user_id, Message.conversation_id.in_(conversations))
            .order_by(Message.conversation_id, Message.created_at)
        )
    ).all()
    reply_for: Dict[UUID, str] = {}
    for index, (message_id, role, _, conversation_id) in enumerate(thread):
        if role != "user":
            continue
        for _, next_role, next_content, next_conversation in thread[index + 1 : index + 3]:
            if next_conversation == conversation_id and next_role == "assistant":
                reply_for[message_id] = next_content or ""
                break

    vectors = await embed_texts([exchange_text(content, reply_for.get(message_id, "")) for message_id, content, _ in todo])
    if not vectors:
        return 0
    for (message_id, _, _), vector in zip(todo, vectors):
        await db.execute(update(Message).where(Message.id == message_id).values(embedding=vector))
    await db.commit()
    return len(todo)


async def clear_embeddings(db: AsyncSession, user_id: UUID) -> None:
    """Forget every stored vector for a user (they are rebuilt in the background)."""
    await db.execute(update(Message).where(Message.user_id == user_id).values(embedding=None))
    await db.commit()


_backfilling: set = set()
_background_tasks: set = set()


def schedule_backfill(user_id: UUID, limit: int = 24) -> None:
    """Embed a batch of the user's older messages in the background, after a reply has
    gone out. Uses its own database session; one run per user at a time."""
    if not embeddings_available() or user_id in _backfilling:
        return

    async def run() -> None:
        from app.db.database import AsyncSessionLocal

        try:
            await asyncio.sleep(3)  # let the request that scheduled this commit its messages
            async with AsyncSessionLocal() as session:
                done = await backfill_embeddings(session, user_id, limit)
                if done:
                    logger.info("Embedded %s older messages for recall", done)
        except Exception as exc:
            logger.warning("Background embedding skipped (%s)", str(exc)[:160])
        finally:
            _backfilling.discard(user_id)

    _backfilling.add(user_id)
    task = asyncio.create_task(run())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def count_embedded(db: AsyncSession, user_id: UUID) -> int:
    return int(
        (
            await db.execute(
                select(func.count(Message.id)).where(
                    Message.user_id == user_id, Message.role == "user", Message.embedding.is_not(None)
                )
            )
        ).scalar()
        or 0
    )
