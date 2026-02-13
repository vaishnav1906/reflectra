from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import models


async def create_conversation(
    db: AsyncSession,
    user_id,
    title: Optional[str],
    mode: str,
    metadata: dict,
) -> models.Conversation:
    conversation = models.Conversation(
        user_id=user_id,
        title=title,
        mode=mode,
        metadata_=metadata,
    )
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation


async def create_message(
    db: AsyncSession,
    user_id,
    conversation_id,
    role: str,
    content: str,
    embedding: Optional[List[float]],
    token_count: Optional[int],
) -> models.Message:
    conversation_result = await db.execute(
        select(models.Conversation).where(
            models.Conversation.id == conversation_id,
            models.Conversation.user_id == user_id,
        )
    )
    conversation = conversation_result.scalar_one_or_none()
    if not conversation:
        raise ValueError("Conversation not found for user")

    message = models.Message(
        user_id=user_id,
        conversation_id=conversation_id,
        role=role,
        content=content,
        embedding=embedding,
        token_count=token_count,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message


async def get_conversation_history(
    db: AsyncSession,
    user_id,
    conversation_id,
) -> List[models.Message]:
    result = await db.execute(
        select(models.Message)
        .where(
            models.Message.conversation_id == conversation_id,
            models.Message.user_id == user_id,
        )
        .order_by(models.Message.created_at.asc())
    )
    return result.scalars().all()


async def upsert_personality_profile(
    db: AsyncSession,
    user_id,
    data: dict,
) -> models.PersonalityProfile:
    result = await db.execute(
        select(models.PersonalityProfile).where(models.PersonalityProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()
    if profile:
        for key, value in data.items():
            if value is not None:
                setattr(profile, key, value)
    else:
        profile = models.PersonalityProfile(user_id=user_id, **data)
        db.add(profile)

    await db.commit()
    await db.refresh(profile)
    return profile
