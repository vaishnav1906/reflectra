from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete
from typing import Dict, Any
from pydantic import BaseModel
from uuid import UUID

from app.db.database import get_db
from app.db.models import (
    User,
    Conversation,
    Message,
    PersonalityProfile,
    BehavioralInsight,
    ReflectionLog,
    UserPersonaMetric,
    PersonaSnapshot,
    ScheduleContext
)

router = APIRouter(prefix="/user", tags=["User"])

class UserRequest(BaseModel):
    user_id: str

@router.post("/clear-data")
async def clear_user_data(request: UserRequest, db: AsyncSession = Depends(get_db)):
    """Soft Reset: Clears all user data except the user account itself."""
    
    try:
        try:
            user_uuid = UUID(request.user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid user_id format")

        # delete messages
        await db.execute(delete(Message).where(Message.user_id == user_uuid))
        
        # delete conversations
        await db.execute(delete(Conversation).where(Conversation.user_id == user_uuid))
        
        # delete persona profiles
        await db.execute(delete(PersonalityProfile).where(PersonalityProfile.user_id == user_uuid))
        
        # delete persona traits / metrics
        await db.execute(delete(UserPersonaMetric).where(UserPersonaMetric.user_id == user_uuid))
        
        # delete snapshots
        await db.execute(delete(PersonaSnapshot).where(PersonaSnapshot.user_id == user_uuid))
        
        # delete insights
        await db.execute(delete(BehavioralInsight).where(BehavioralInsight.user_id == user_uuid))
        
        # delete reflections
        await db.execute(delete(ReflectionLog).where(ReflectionLog.user_id == user_uuid))
        
        # delete schedule context
        await db.execute(delete(ScheduleContext).where(ScheduleContext.user_id == user_uuid))
        
        await db.commit()
        return {"status": "success", "message": "All user data cleared."}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/delete-account")
async def delete_user_account(request: UserRequest, db: AsyncSession = Depends(get_db)):
    """Hard Reset: Deletes the user entirely and cascades."""
    try:
        try:
            user_uuid = UUID(request.user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid user_id format")

        # Delete user - ON DELETE CASCADE will handle the rest automatically
        await db.execute(delete(User).where(User.id == user_uuid))
        await db.commit()
        return {"status": "success", "message": "User account and all data completely deleted."}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
