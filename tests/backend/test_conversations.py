#!/usr/bin/env python3
"""Verify conversations in the database."""

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"

env_path = BACKEND_DIR / ".env"
load_dotenv(env_path)

DATABASE_URL = os.getenv("DATABASE_URL")


async def test_conversations() -> None:
    print("Connecting to database...")
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set")

    engine = create_async_engine(DATABASE_URL, echo=False)
    AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with AsyncSessionLocal() as session:
        from app.db.models import Conversation, Message, User

        result = await session.execute(select(func.count(User.id)))
        user_count = result.scalar()
        print(f"Users: {user_count}")

        result = await session.execute(select(Conversation).order_by(Conversation.created_at.desc()).limit(20))
        conversations = result.scalars().all()

        for conv in conversations:
            msg_result = await session.execute(select(func.count(Message.id)).where(Message.conversation_id == conv.id))
            msg_count = msg_result.scalar()
            print(f"Conversation {conv.id} | mode={conv.mode} | messages={msg_count}")

        result = await session.execute(select(Message).order_by(Message.created_at.desc()).limit(5))
        messages = result.scalars().all()
        print("Recent messages:")
        for msg in messages:
            preview = msg.content[:50] + "..." if len(msg.content) > 50 else msg.content
            print(f"- {msg.role}: {preview}")


if __name__ == "__main__":
    asyncio.run(test_conversations())
