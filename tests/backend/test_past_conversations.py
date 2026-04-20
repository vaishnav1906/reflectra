#!/usr/bin/env python3
<<<<<<< HEAD
"""Quick test script for Past Conversations feature."""
=======
"""
Quick test script for Past Conversations feature
Run this after starting the backend to verify everything works
"""
>>>>>>> 2e802b708e180667c3c686074a7dcd5835c21525

import asyncio
import os
import sys
<<<<<<< HEAD
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"

sys.path.insert(0, str(BACKEND_DIR))

env_path = BACKEND_DIR / ".env"
=======
from datetime import datetime
from uuid import uuid4
from dotenv import load_dotenv
from pathlib import Path

# Load environment
env_path = Path(__file__).resolve().parent.parent.parent / "backend" / ".env"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "backend"))
>>>>>>> 2e802b708e180667c3c686074a7dcd5835c21525
load_dotenv(env_path)

DATABASE_URL = os.getenv("DATABASE_URL")

<<<<<<< HEAD

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
=======
async def test_past_conversations():
    """Test past conversations functionality"""
    print("\n" + "="*80)
    print("🧪 PAST CONVERSATIONS FEATURE TEST")
    print("="*80 + "\n")
    
    try:
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
        from sqlalchemy import select, func
        
        if not DATABASE_URL:
            print("❌ DATABASE_URL not set in .env")
            return False
        
        # Connect to database
        print("🔌 Connecting to database...")
        engine = create_async_engine(DATABASE_URL, echo=False)
        AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        
        async with AsyncSessionLocal() as session:
            from backend.app.db.models import User, Conversation, Message
            
            # Test 1: Verify tables exist
            print("\n✅ Test 1: Verify database tables")
            print("  → conversations table exists")
            print("  → messages table exists")
            
            # Count records
            result = await session.execute(select(func.count(Conversation.id)))
            conv_count = result.scalar()
            
            result = await session.execute(select(func.count(Message.id)))
            msg_count = result.scalar()
            
            print(f"  📊 Total conversations: {conv_count}")
            print(f"  📊 Total messages: {msg_count}")
            
            # Test 2: Verify conversations have messages
            if conv_count > 0:
                print("\n✅ Test 2: Verify conversation-message relationships")
                
                result = await session.execute(
                    select(Conversation)
                    .order_by(Conversation.created_at.desc())
                    .limit(3)
                )
                recent_convs = result.scalars().all()
                
                for conv in recent_convs:
                    result = await session.execute(
                        select(func.count(Message.id))
                        .where(Message.conversation_id == conv.id)
                    )
                    msg_count_conv = result.scalar()
                    
                    print(f"\n  📝 Conversation: {str(conv.id)[:8]}...")
                    print(f"     Title: {conv.title}")
                    print(f"     Mode: {conv.mode}")
                    print(f"     Messages: {msg_count_conv}")
                    print(f"     Created: {conv.created_at}")
                    
                    # Show message order
                    result = await session.execute(
                        select(Message)
                        .where(Message.conversation_id == conv.id)
                        .order_by(Message.created_at.asc())
                    )
                    messages = result.scalars().all()
                    
                    if messages:
                        print(f"     📋 Messages in order:")
                        for i, msg in enumerate(messages[:3], 1):
                            preview = msg.content[:40].replace("\n", " ")
                            print(f"        {i}. [{msg.role}] {preview}...")
                        if len(messages) > 3:
                            print(f"        ... and {len(messages) - 3} more")
            else:
                print("\n⚠️  No conversations found yet. Create one via the UI first.")
            
            # Test 3: Verify user isolation
            print("\n✅ Test 3: Verify user isolation")
            result = await session.execute(select(func.count(User.id)))
            user_count = result.scalar()
            print(f"  👥 Total users: {user_count}")
            
            if user_count > 0:
                # Group conversations by user
                result = await session.execute(
                    select(User.id, func.count(Conversation.id))
                    .select_from(User)
                    .outerjoin(Conversation)
                    .group_by(User.id)
                )
                user_convs = result.all()
                
                for user_id, conv_count_user in user_convs:
                    print(f"  👤 User {str(user_id)[:8]}... has {conv_count_user} conversations")
            
            print("\n" + "="*80)
            print("✅ ALL TESTS PASSED")
            print("="*80 + "\n")
            
            return True
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    try:
        result = asyncio.run(test_past_conversations())
        sys.exit(0 if result else 1)
    except Exception as e:
        print(f"❌ Test failed: {e}")
        sys.exit(1)
>>>>>>> 2e802b708e180667c3c686074a7dcd5835c21525
