"""Shared FastAPI dependencies: the authenticated user and ownership checks."""

from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import User
from app.services.auth_service import AuthError, claims_from_payload, decode_access_token, resolve_user

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(_bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        claims = claims_from_payload(decode_access_token(credentials.credentials))
        return await resolve_user(db, claims)
    except AuthError as exc:
        headers = {"WWW-Authenticate": "Bearer"} if exc.status == 401 else None
        raise HTTPException(status_code=exc.status, detail=exc.detail, headers=headers) from exc


CurrentUser = Annotated[User, Depends(get_current_user)]


def ensure_self(requested_user_id: Optional[object], current_user: User) -> UUID:
    """Return the current user's id, rejecting requests that name a different user.

    Routes keep their existing `user_id` path/query/body fields for compatibility,
    but the identity always comes from the access token.
    """
    if requested_user_id not in (None, ""):
        try:
            requested = requested_user_id if isinstance(requested_user_id, UUID) else UUID(str(requested_user_id))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid user_id format")
        if requested != current_user.id:
            raise HTTPException(status_code=403, detail="You can only access your own data")
    return current_user.id


async def require_user_scope(request: Request, current_user: CurrentUser) -> User:
    """Router-level guard: authenticate, and reject any `user_id` path or query
    parameter that is not the caller's own id. Body fields are checked in the
    route handlers with `ensure_self`."""
    ensure_self(request.path_params.get("user_id"), current_user)
    ensure_self(request.query_params.get("user_id"), current_user)
    return current_user
