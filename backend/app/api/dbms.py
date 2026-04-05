from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.db import crud
from app.db.database import get_db
from app.schemas.db import (
    ConversationCreate,
    ConversationHistoryOut,
    ConversationOut,
    MessageCreate,
    MessageOut,
    PersonalityProfileOut,
    PersonalityProfileUpdate,
)

router = APIRouter(prefix="/db", tags=["db"])


@router.post("/conversations", response_model=ConversationOut)
async def create_conversation(payload: ConversationCreate, db: AsyncSession = Depends(get_db)) -> ConversationOut:
    conversation = await crud.create_conversation(
        db,
        user_id=payload.user_id,
        title=payload.title,
        mode=payload.mode,
        metadata=payload.metadata,
    )
    return conversation


@router.post("/messages", response_model=MessageOut)
async def save_message(payload: MessageCreate, db: AsyncSession = Depends(get_db)) -> MessageOut:
    try:
        message = await crud.create_message(
            db,
            user_id=payload.user_id,
            conversation_id=payload.conversation_id,
            role=payload.role,
            content=payload.content,
            embedding=payload.embedding,
            token_count=payload.token_count,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return message


@router.get("/conversations/{conversation_id}/history", response_model=ConversationHistoryOut)
async def fetch_conversation_history(
    conversation_id: str,
    user_id: str,
    db: AsyncSession = Depends(get_db),
) -> ConversationHistoryOut:
    try:
        conversation_id_uuid = UUID(conversation_id)
        user_id_uuid = UUID(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid UUID format") from exc

    messages = await crud.get_conversation_history(
        db,
        user_id=user_id_uuid,
        conversation_id=conversation_id_uuid,
    )
    if not messages:
        raise HTTPException(status_code=404, detail="No messages found for conversation")
    return ConversationHistoryOut(conversation_id=conversation_id, messages=messages)


@router.put("/personality-profile/{user_id}", response_model=PersonalityProfileOut)
async def update_personality_profile(
    user_id: str,
    payload: PersonalityProfileUpdate,
    db: AsyncSession = Depends(get_db),
) -> PersonalityProfileOut:
    profile = await crud.upsert_personality_profile(db, user_id=user_id, data=payload.model_dump())
    return profile


@router.get("/mirror-telemetry/{user_id}")
async def get_mirror_telemetry(
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Fetch observability metrics for the mirror engine."""
    from sqlalchemy import select, func, cast, Integer
    from app.db.models import MirrorLog
    
    try:
        user_uuid = UUID(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid user_id format") from exc

    # Query metrics
    stmt = select(
        func.count(MirrorLog.id).label("total_generations"),
        func.avg(MirrorLog.inference_duration_ms).label("avg_latency_ms"),
        func.avg(MirrorLog.realism_score).label("avg_realism_score"),
        func.sum(func.cast(MirrorLog.fallback_triggered, Integer)).label("total_fallbacks")
    ).where(MirrorLog.user_id == user_uuid)
    
    result = await db.execute(stmt)
    row = result.first()
    
    if not row or row.total_generations == 0:
        return {
            "total_generations": 0,
            "avg_latency_ms": 0,
            "avg_realism_score": 0.0,
            "total_fallbacks": 0,
            "success_rate": 0.0
        }
        
    return {
        "total_generations": row.total_generations,
        "avg_latency_ms": round(float(row.avg_latency_ms or 0), 2),
        "avg_realism_score": round(float(row.avg_realism_score or 0), 3),
        "total_fallbacks": row.total_fallbacks or 0,
        "success_rate": round(100.0 * (1 - (row.total_fallbacks or 0) / row.total_generations), 1)
    }
