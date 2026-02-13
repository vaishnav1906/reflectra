from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

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
    messages = await crud.get_conversation_history(db, user_id=user_id, conversation_id=conversation_id)
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
