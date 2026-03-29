from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db import crud

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    display_name: str
    
    @field_validator('display_name')
    @classmethod
    def validate_display_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError('Display name cannot be empty')
        return v


class LoginResponse(BaseModel):
    id: str
    display_name: str
    email: str


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login endpoint - gets or creates user with validated email"""
    try:
        # Clean and normalize inputs
        email = str(request.email).strip().lower()
        display_name = request.display_name.strip()
        
        # Get or create user (prevents duplicates)
        user = await crud.get_or_create_user(
            db=db,
            email=email,
            display_name=display_name,
        )
        
        return LoginResponse(
            id=str(user.id),
            display_name=user.display_name,
            email=user.email,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Login failed: {str(e)}"
        )


class DeleteUserRequest(BaseModel):
    user_id: str

@router.delete("/delete-all")
async def delete_all_user_data(
    request: DeleteUserRequest,
    db: AsyncSession = Depends(get_db)
):
    """Irreversibly delete all user data"""
    from uuid import UUID
    from sqlalchemy import delete
    from app.db.models import (
        User, Conversation, Message, PersonalityProfile, 
        BehavioralInsight, ReflectionLog, UserPersonaMetric, 
        PersonaSnapshot, ScheduleContext
    )
    from app.services.mirror_engine import invalidate_snapshot_cache
    
    try:
        user_uuid = UUID(request.user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id format")

    try:
        # Since ondelete="CASCADE" is set on the foreign keys for most tables,
        # deleting the User should cascade properly. However, to be perfectly safe
        # and explicit as requested, we run explicit deletes in order.
        
        # 1. Delete derived/child tables
        await db.execute(delete(Message).where(Message.user_id == user_uuid))
        await db.execute(delete(Conversation).where(Conversation.user_id == user_uuid))
        await db.execute(delete(PersonalityProfile).where(PersonalityProfile.user_id == user_uuid))
        await db.execute(delete(BehavioralInsight).where(BehavioralInsight.user_id == user_uuid))
        await db.execute(delete(ReflectionLog).where(ReflectionLog.user_id == user_uuid))
        await db.execute(delete(UserPersonaMetric).where(UserPersonaMetric.user_id == user_uuid))
        await db.execute(delete(PersonaSnapshot).where(PersonaSnapshot.user_id == user_uuid))
        
        # We need to catch sqlalchemy.exc.InvalidRequestError if ScheduleContext hasn't been migrated yet,
        # but since we already edited models.py and migrated it, this is safe.
        await db.execute(delete(ScheduleContext).where(ScheduleContext.user_id == user_uuid))
        
        # 2. Clear from vector cache or anything else?
        invalidate_snapshot_cache(user_uuid)
        
        # 3. Delete the user
        await db.execute(delete(User).where(User.id == user_uuid))
        
        await db.commit()
        return {"status": "user_deleted"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete user: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process login: {str(e)}"
        )
