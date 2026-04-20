#!/usr/bin/env python3
"""Quick test script for Past Conversations feature."""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"

sys.path.insert(0, str(BACKEND_DIR))

env_path = BACKEND_DIR / ".env"
load_dotenv(env_path)

DATABASE_URL = os.getenv("DATABASE_URL")


async def test_past_conversations() -> bool:
    print("\n" + "=" * 80)
    print("PAST CONVERSATIONS FEATURE TEST")
    print("=" * 80 + "\n")

    try:
        from sqlalchemy import func, select
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

        from app.db.models import Conversation, Message, User

        if not DATABASE_URL:
            print("DATABASE_URL not set in backend/.env")
            return False

        print("Connecting to database...")
        engine = create_async_engine(DATABASE_URL, echo=False)
        AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

        async with AsyncSessionLocal() as session:
            result = await session.execute(select(func.count(Conversation.id)))
            conv_count = result.scalar()

            result = await session.execute(select(func.count(Message.id)))
            msg_count = result.scalar()

            print(f"Conversations: {conv_count}")
            print(f"Messages: {msg_count}")

            if conv_count and conv_count > 0:
                result = await session.execute(select(Conversation).order_by(Conversation.created_at.desc()).limit(3))
                recent_convs = result.scalars().all()

                for conv in recent_convs:
                    result = await session.execute(select(func.count(Message.id)).where(Message.conversation_id == conv.id))
                    msg_count_conv = result.scalar()
                    print(f"Conversation {str(conv.id)[:8]}... | mode={conv.mode} | messages={msg_count_conv}")
            else:
                print("No conversations found yet.")

            result = await session.execute(select(func.count(User.id)))
            user_count = result.scalar()
            print(f"Users: {user_count}")

        print("\nALL TESTS PASSED\n")
        return True

    except Exception as exc:
        print(f"ERROR: {exc}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    ok = asyncio.run(test_past_conversations())
    sys.exit(0 if ok else 1)
