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
            detail=f"Failed to process login: {str(e)}"
        )
