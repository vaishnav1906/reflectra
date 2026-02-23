#!/usr/bin/env python3
"""
Example usage of the Persona System.

This script demonstrates the full persona modeling pipeline:
1. Trait extraction from messages
2. Trait updates with weighted moving average
3. Snapshot generation
4. Mirror response generation
"""

import asyncio
import logging
from uuid import uuid4

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.db.models import Base
from app.services.trait_extraction_service import extract_traits
from app.services.persona_update_service import update_traits
from app.services.snapshot_service import generate_persona_snapshot
from app.services.mirror_engine import generate_mirror_response
from app.repository.persona_repository import PersonaRepository

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def demo_persona_system():
    """Demonstrate the complete persona system."""
    
    # Create in-memory SQLite database for demo
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False
    )
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session maker
    SessionLocal = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    # Create test user
    user_id = uuid4()
    logger.info(f"\n{'='*80}\n🎭 PERSONA SYSTEM DEMO\n{'='*80}\n")
    logger.info(f"Test User ID: {user_id}\n")
    
    # Test messages simulating a conversation
    test_messages = [
        "I'm really worried about this project. I don't know if I'm doing it right and keep second-guessing myself.",
        "Maybe I'm overthinking it... I mean, the deadline is coming up and I just can't seem to make a decision.",
        "I analyzed all the data thoroughly but I'm still uncertain about the best approach.",
        "This is ridiculous! Why is this so hard? I just want to make the right choice!",
        "Let me break this down logically - what are the pros and cons of each option?",
    ]
    
    for i, message in enumerate(test_messages, 1):
        logger.info(f"\n{'─'*80}")
        logger.info(f"📨 MESSAGE {i}: \"{message}\"")
        logger.info(f"{'─'*80}\n")
        
        async with SessionLocal() as session:
            # Step 1: Extract traits
            logger.info("Step 1: Extract traits from message")
            traits = await extract_traits(message)
            
            if traits:
                logger.info(f"✅ Extracted {len(traits)} traits:")
                for trait in traits:
                    logger.info(f"  - {trait['name']}: signal={trait['signal']:.2f}, strength={trait['strength']:.2f}")
            else:
                logger.info("ℹ️  No traits extracted (LLM may not be available)")
            
            # Step 2: Update traits
            logger.info("\nStep 2: Update trait metrics")
            result = await update_traits(session, user_id, traits)
            logger.info(f"✅ Updated {result['traits_updated']} traits")
            logger.info(f"📊 Stability Index: {result['stability_index']:.3f}")
            
            # Step 3: Generate snapshot
            logger.info("\nStep 3: Generate persona snapshot")
            snapshot = await generate_persona_snapshot(session, user_id)
            logger.info(f"✅ Snapshot created: {snapshot.id}")
            logger.info(f"📝 Summary: {snapshot.summary_text}")
            
            # Display current metrics
            logger.info("\nStep 4: Current trait metrics")
            metrics = await PersonaRepository.get_all_metrics(session, user_id)
            
            # Show top 5 traits by confidence
            sorted_metrics = sorted(metrics, key=lambda m: m.confidence, reverse=True)[:5]
            logger.info("Top 5 traits by confidence:")
            for metric in sorted_metrics:
                logger.info(
                    f"  - {metric.trait_name:25s}: "
                    f"score={metric.score:.3f}, "
                    f"confidence={metric.confidence:.3f}, "
                    f"evidence={metric.evidence_count}"
                )
        
        # Pause between messages
        if i < len(test_messages):
            await asyncio.sleep(0.5)
    
    # Final mirror test
    logger.info(f"\n{'='*80}")
    logger.info("🪞 MIRROR TEST")
    logger.info(f"{'='*80}\n")
    
    test_prompt = "What should I do about my confusion?"
    logger.info(f"User: \"{test_prompt}\"")
    
    async with SessionLocal() as session:
        mirror_response = await generate_mirror_response(session, user_id, test_prompt)
        logger.info(f"\nMirror: \"{mirror_response}\"")
    
    # Final summary
    logger.info(f"\n{'='*80}")
    logger.info("📊 FINAL SUMMARY")
    logger.info(f"{'='*80}\n")
    
    async with SessionLocal() as session:
        final_snapshot = await PersonaRepository.get_latest_snapshot(session, user_id)
        logger.info(f"Stability Index: {final_snapshot.stability_index:.3f}")
        logger.info(f"Summary: {final_snapshot.summary_text}")
        
        logger.info("\nPersona Vector:")
        for group, traits in final_snapshot.persona_vector.items():
            logger.info(f"\n  {group.replace('_', ' ').title()}:")
            for trait_name, values in traits.items():
                logger.info(
                    f"    - {trait_name.replace('_', ' ').title():25s}: "
                    f"score={values['score']:.3f}, "
                    f"confidence={values['confidence']:.3f}"
                )
    
    logger.info(f"\n{'='*80}")
    logger.info("✅ DEMO COMPLETE")
    logger.info(f"{'='*80}\n")
    
    await engine.dispose()


if __name__ == "__main__":
    print("\n🚀 Starting Persona System Demo...\n")
    print("Note: This demo uses in-memory SQLite for demonstration.")
    print("LLM features require MISTRAL_API_KEY to be set.\n")
    
    asyncio.run(demo_persona_system())
