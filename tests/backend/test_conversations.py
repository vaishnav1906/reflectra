#!/usr/bin/env python3
<<<<<<< HEAD
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
=======
"""
Test script to verify conversations in the database
"""
import asyncio
import os
from dotenv import load_dotenv
from pathlib import Path
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Load environment
import sys
backend_dir = Path(__file__).resolve().parent.parent.parent / "backend"
sys.path.insert(0, str(backend_dir))
env_path = backend_dir / ".env"
>>>>>>> 2e802b708e180667c3c686074a7dcd5835c21525
load_dotenv(env_path)

DATABASE_URL = os.getenv("DATABASE_URL")

<<<<<<< HEAD

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

=======
async def test_conversations():
    """Check conversations and messages in the database"""
    print(f"🔌 Connecting to database...")
    print(f"📍 Database URL: {DATABASE_URL[:50]}...")
    
    engine = create_async_engine(DATABASE_URL, echo=False)
    AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    
    async with AsyncSessionLocal() as session:
        # Import models
        from app.db.models import User, Conversation, Message
        
        # Count users
        result = await session.execute(select(func.count(User.id)))
        user_count = result.scalar()
        print(f"\n👥 Total users: {user_count}")
        
        # List users
        result = await session.execute(select(User))
        users = result.scalars().all()
        for user in users:
            print(f"  - User: {user.id} | {user.email} | {user.display_name}")
        
        # Count conversations
        result = await session.execute(select(func.count(Conversation.id)))
        conv_count = result.scalar()
        print(f"\n💬 Total conversations: {conv_count}")
        
        # List conversations with details
        result = await session.execute(
            select(Conversation)
            .order_by(Conversation.created_at.desc())
            .limit(20)
        )
        conversations = result.scalars().all()
        
        for conv in conversations:
            print(f"  - Conv {conv.id}:")
            print(f"    User: {conv.user_id}")
            print(f"    Title: {conv.title}")
            print(f"    Mode: {conv.mode}")
            print(f"    Created: {conv.created_at}")
            
            # Count messages
            msg_result = await session.execute(
                select(func.count(Message.id))
                .where(Message.conversation_id == conv.id)
            )
            msg_count = msg_result.scalar()
            print(f"    Messages: {msg_count}")
        
        # Count messages
        result = await session.execute(select(func.count(Message.id)))
        msg_count = result.scalar()
        print(f"\n📨 Total messages: {msg_count}")
        
        # Show recent messages
        result = await session.execute(
            select(Message)
            .order_by(Message.created_at.desc())
            .limit(5)
        )
        messages = result.scalars().all()
        
        print("\n📝 Recent messages:")
        for msg in messages:
            content_preview = msg.content[:50] + "..." if len(msg.content) > 50 else msg.content
            print(f"  - {msg.role}: {content_preview} (conv: {msg.conversation_id})")
    
    print("\n✅ Test complete!")
>>>>>>> 2e802b708e180667c3c686074a7dcd5835c21525

if __name__ == "__main__":
    asyncio.run(test_conversations())
