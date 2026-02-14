from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["auth"])

class LoginRequest(BaseModel):
    email: str
    display_name: str

class LoginResponse(BaseModel):
    id: str
    display_name: str
    email: str

@router.post("/login", response_model=LoginResponse)
def login(request: LoginRequest):
    """Simple login endpoint - returns user info"""
    # For now, use email as ID (in production, you'd check against a DB)
    user_id = request.email.split("@")[0]  # Simple ID from email
    
    return LoginResponse(
        id=user_id,
        display_name=request.display_name,
        email=request.email
    )
