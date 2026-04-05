from sqlalchemy import text, select
import logging
from typing import Dict
from uuid import UUID
from app.db.models import PersonaSnapshot

logger = logging.getLogger(__name__)

async def retrieve_memories(db, user_id, embedding, limit=5):
    if embedding is None:
        print("⚠️ Skipping memory retrieval (no embedding)")
        return []

    query = text("""
        SELECT content, similarity
        FROM match_messages(
            :query_embedding,
            0.75,
            :limit,
            :user_id
        )
    """)

    vector_string = "[" + ",".join(map(str, embedding)) + "]"

    result = await db.execute(
        query,
        {
            "query_embedding": vector_string,
            "limit": limit,
            "user_id": str(user_id)
        }
    )

    rows = result.fetchall()

    memories = list(dict.fromkeys(row[0] for row in rows))
    print("🧠 Retrieved memories:", memories)

    return memories


async def check_and_recalibrate_drift(db, user_id: UUID) -> None:
    """
    Checks for behavioral drift against the Deep Historical Anchor.
    If drift > threshold, re-anchors passing traits toward their original state.
    """
    logger.info(f"🔍 Checking drift recalibration for user {user_id}")
    
    # Fetch active snapshot vs anchor
    active_stmt = select(PersonaSnapshot).where(
        PersonaSnapshot.user_id == user_id,
        PersonaSnapshot.is_historical_anchor == False
    ).order_by(PersonaSnapshot.created_at.desc()).limit(1)
    
    anchor_stmt = select(PersonaSnapshot).where(
        PersonaSnapshot.user_id == user_id,
        PersonaSnapshot.is_historical_anchor == True
    ).order_by(PersonaSnapshot.created_at.desc()).limit(1)
    
    active_res = await db.execute(active_stmt)
    anchor_res = await db.execute(anchor_stmt)
    
    active_snap = active_res.scalar_one_or_none()
    anchor_snap = anchor_res.scalar_one_or_none()
    
    if not active_snap or not anchor_snap:
        # Cannot compare if we lack an anchor
        logger.debug(f"ℹ️ Skipping recalibration for {user_id}, missing anchor or active snapshot.")
        return
        
    active_traits = active_snap.behavioral_traits or {}
    anchor_traits = anchor_snap.behavioral_traits or {}

    if not active_traits or not anchor_traits:
        return
        
    drift_score = 0.0
    drift_count = 0
    drift_threshold = 0.3  # Allow up to 30% drift before recalibrating
    
    for key, anchor_val in anchor_traits.items():
        if key in active_traits:
            active_val = active_traits[key]
            if isinstance(anchor_val, (int, float)) and isinstance(active_val, (int, float)):
                drift = abs(active_val - anchor_val)
                drift_score += drift
                drift_count += 1
                
    if drift_count > 0:
        avg_drift = drift_score / drift_count
        if avg_drift > drift_threshold:
            # Re-anchor
            logger.info(f"🌊 Drift detected ({avg_drift:.2f} > {drift_threshold}). Recalibrating toward anchor...")
            for key, anchor_val in anchor_traits.items():
                if key in active_traits and isinstance(anchor_val, (int, float)):
                    # Smooth 50% back towards the anchor
                    active_traits[key] = (active_traits[key] + anchor_val) / 2
                    
            active_snap.behavioral_traits = active_traits
            await db.commit()
            
            # We don't necessarily update `PersonaSnapshot.persona_vector` mapping
            # for `UserPersonaMetric` yet, but behavioral_traits is re-anchored.
            logger.info(f"✅ Deep drift recalibration complete for {user_id}")
