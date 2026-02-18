#!/usr/bin/env python3
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
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

DATABASE_URL = os.getenv("DATABASE_URL")

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

if __name__ == "__main__":
    asyncio.run(test_conversations())
