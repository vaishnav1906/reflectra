"""What Reflectra learns from a message, run as background jobs after the reply.

  learn_from_message  traits (read by the AI, or a simple fallback), the per-message
                      metrics, the conversation profile and reflection log, the
                      writing-style fingerprint and reactions, Mirror drift checks.
  follow_ups          things the user said they'd do (followup_service).
  people              mentions, notes and suggestions (people_service).
  index_memories      meaning vectors for older messages (embedding_service).
  life_memory         lasting facts about the user's life (life_memory_service).

The chat endpoint queues these; app.worker runs them.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Message, ReflectionLog
from app.services.job_service import enqueue, handler

logger = logging.getLogger(__name__)


@handler("learn_from_message")
async def learn_from_message(db: AsyncSession, user_id: UUID, payload: dict) -> None:
    from app.api.chat import (
        load_personality_profile,
        maybe_extract_traits,
        save_personality_profile,
        update_personality_profile,
    )
    from app.services.behavioral_memory_service import record_user_reaction, update_linguistic_fingerprint
    from app.services.message_signals import compute_message_metrics, derive_fallback_traits, simple_sentiment
    from app.services.persona_update_service import update_traits
    from app.services.snapshot_service import generate_persona_snapshot

    message = str(payload.get("message") or "")
    reply = str(payload.get("reply") or "")
    mode = payload.get("mode") or "reflection"
    learning = bool(payload.get("learning", True))
    conversation_id = UUID(payload["conversation_id"]) if payload.get("conversation_id") else None
    message_id = UUID(payload["user_message_id"]) if payload.get("user_message_id") else None

    traits = await maybe_extract_traits(message) if learning else []
    if learning and not traits:
        traits = derive_fallback_traits(message)

    if message_id is not None:
        metrics = compute_message_metrics(message, traits)
        await db.execute(
            update(Message)
            .where(Message.id == message_id, Message.user_id == user_id)
            .values(emotional_intensity=metrics["emotional_intensity"], reflection_depth=metrics["reflection_depth"])
        )

    if mode == "reflection":
        profile = await load_personality_profile(db, user_id)
        update_personality_profile(profile, message, reply)
        await save_personality_profile(db, user_id, profile)
        db.add(
            ReflectionLog(
                user_id=user_id,
                conversation_id=conversation_id,
                prompt=message,
                response=reply,
                sentiment=simple_sentiment(message),
            )
        )
    await db.commit()

    if not learning:
        return

    if traits:
        await update_traits(db, user_id, traits)
        await generate_persona_snapshot(db, user_id)
    await update_linguistic_fingerprint(db, user_id, message)
    await record_user_reaction(db, user_id, message)
    await db.commit()

    if mode == "mirror":
        from app.services.memory_service import check_and_recalibrate_drift

        try:
            await check_and_recalibrate_drift(db, user_id)
        except Exception:
            logger.exception("Drift recalibration failed")
            await db.rollback()


@handler("follow_ups")
async def follow_ups(db: AsyncSession, user_id: UUID, payload: dict) -> None:
    from app.services import followup_service

    if followup_service.looks_like_intention(payload.get("message", "")) or followup_service.looks_like_update(payload.get("message", "")):
        await followup_service.process_message(
            db, user_id, _uuid(payload.get("conversation_id")), payload.get("message", ""), int(payload.get("tz", 0))
        )


@handler("people")
async def people(db: AsyncSession, user_id: UUID, payload: dict) -> None:
    from app.services import people_service

    await people_service.process_message(
        db, user_id, _uuid(payload.get("conversation_id")), payload.get("message", ""), int(payload.get("tz", 0))
    )


@handler("index_memories")
async def index_memories(db: AsyncSession, user_id: UUID, payload: dict) -> None:
    from app.services import embedding_service

    done = await embedding_service.backfill_embeddings(db, user_id, int(payload.get("limit", 48)))
    if done and done >= int(payload.get("limit", 48)):
        # More left: come back for the next batch shortly (quota-friendly pacing).
        await enqueue(db, user_id, "index_memories", {"limit": payload.get("limit", 48)}, dedupe_key=f"index:{user_id}", delay_seconds=30)


@handler("life_memory")
async def life_memory(db: AsyncSession, user_id: UUID, payload: dict) -> None:
    from app.services import life_memory_service

    await life_memory_service.process_message(
        db, user_id, _uuid(payload.get("conversation_id")), payload.get("message", ""), int(payload.get("tz", 0))
    )


@handler("life_memory_backfill")
async def life_memory_backfill(db: AsyncSession, user_id: UUID, payload: dict) -> None:
    from app.services import life_memory_service

    outcome = await life_memory_service.backfill(db, user_id, int(payload.get("limit", 160)))
    logger.info("Life memory backfill: %s", outcome)


async def queue_learning(
    db: AsyncSession,
    user_id: UUID,
    *,
    conversation_id: UUID,
    user_message_id: UUID,
    message: str,
    reply: str,
    mode: str,
    tz: int,
    learning: bool,
) -> None:
    """Everything to learn from one exchange, queued in a single commit."""
    base = {"conversation_id": str(conversation_id), "message": message, "tz": tz}
    await enqueue(
        db,
        user_id,
        "learn_from_message",
        {**base, "user_message_id": str(user_message_id), "reply": reply, "mode": mode, "learning": learning},
        commit=False,
    )
    if learning:
        await enqueue(db, user_id, "follow_ups", base, commit=False)
        await enqueue(db, user_id, "people", base, commit=False)
        await enqueue(db, user_id, "life_memory", {**base, "user_message_id": str(user_message_id)}, commit=False)
        await enqueue(db, user_id, "index_memories", {"limit": 48}, dedupe_key=f"index:{user_id}", delay_seconds=5, commit=False)
    await db.commit()


def _uuid(value):
    return UUID(value) if value else None
