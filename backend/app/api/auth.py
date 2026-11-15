"""Auth routes.

Sign-up, sign-in, email confirmation and password reset are handled by Supabase
Auth in the frontend. The backend only verifies the Supabase access token
(see app.api.deps.get_current_user) and maps it to the app's `users` row.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, ensure_self
from app.db.database import get_db
from app.db.models import User
from app.services.auth_service import delete_supabase_auth_user

router = APIRouter(prefix="/auth", tags=["auth"])


class MeResponse(BaseModel):
    id: str
    display_name: str
    email: str


@router.get("/me", response_model=MeResponse)
async def me(current_user: CurrentUser) -> MeResponse:
    """Return the app user for the caller's access token (created/linked on first call)."""
    return MeResponse(
        id=str(current_user.id),
        display_name=current_user.display_name or current_user.email.split("@", 1)[0],
        email=current_user.email,
    )


class DeleteUserRequest(BaseModel):
    user_id: Optional[str] = None  # ignored: identity comes from the access token


@router.delete("/delete-all")
async def delete_all_user_data(
    request: DeleteUserRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Irreversibly delete the caller's account and all their data."""
    user_uuid = ensure_self(request.user_id, current_user)
    auth_user_id = current_user.auth_user_id

    try:
        # Every user-owned table has ON DELETE CASCADE to users.id.
        await db.execute(delete(User).where(User.id == user_uuid))
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete user: {str(e)}")

    auth_deleted = await delete_supabase_auth_user(auth_user_id)
    return {"status": "user_deleted", "auth_account_deleted": auth_deleted}
