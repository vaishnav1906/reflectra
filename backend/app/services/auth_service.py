"""Supabase Auth integration: access-token verification and user resolution.

Configuration (backend/.env):
  SUPABASE_URL                 https://<project-ref>.supabase.co   (required)
  SUPABASE_JWT_SECRET          legacy HS256 JWT secret             (only for projects
                               still signing with the shared secret)
  SUPABASE_SERVICE_ROLE_KEY    optional; lets account deletion also delete the
                               Supabase Auth user
  AUTH_REQUIRE_VERIFIED_EMAIL  default "true"

Tokens signed with asymmetric keys (ES256/RS256) are verified against the
project's JWKS endpoint; HS256 tokens use SUPABASE_JWT_SECRET.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, Optional
from uuid import UUID

import jwt
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User

logger = logging.getLogger(__name__)

AUDIENCE = "authenticated"


class AuthError(Exception):
    """Raised when a request cannot be authenticated. `status` is the HTTP code to return."""

    def __init__(self, detail: str, status: int = 401):
        super().__init__(detail)
        self.detail = detail
        self.status = status


@dataclass
class AuthClaims:
    auth_user_id: UUID
    email: str
    email_verified: bool
    display_name: Optional[str]


def _supabase_url() -> str:
    url = (os.getenv("SUPABASE_URL") or "").rstrip("/")
    if not url:
        raise AuthError("Authentication is not configured on the server (SUPABASE_URL missing)", status=500)
    return url


def _require_verified_email() -> bool:
    return os.getenv("AUTH_REQUIRE_VERIFIED_EMAIL", "true").strip().lower() not in {"0", "false", "no"}


@lru_cache(maxsize=4)
def _jwks_client(jwks_url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(jwks_url, cache_keys=True, lifespan=3600)


def decode_access_token(token: str) -> Dict[str, Any]:
    """Verify a Supabase access token and return its claims."""
    if not token:
        raise AuthError("Missing access token")

    base_url = _supabase_url()
    issuer = f"{base_url}/auth/v1"

    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise AuthError("Malformed access token") from exc

    algorithm = header.get("alg")
    try:
        if algorithm == "HS256":
            secret = os.getenv("SUPABASE_JWT_SECRET")
            if not secret:
                raise AuthError("Server cannot verify HS256 tokens (SUPABASE_JWT_SECRET missing)", status=500)
            key: Any = secret
        elif algorithm in {"ES256", "RS256", "EdDSA"}:
            key = _jwks_client(f"{issuer}/.well-known/jwks.json").get_signing_key_from_jwt(token).key
        else:
            raise AuthError("Unsupported token algorithm")

        return jwt.decode(
            token,
            key=key,
            algorithms=[algorithm],
            audience=AUDIENCE,
            issuer=issuer,
            options={"require": ["exp", "sub", "aud", "iss"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("Access token expired") from exc
    except jwt.PyJWTError as exc:
        raise AuthError("Invalid access token") from exc


def claims_from_payload(payload: Dict[str, Any]) -> AuthClaims:
    try:
        auth_user_id = UUID(str(payload["sub"]))
    except (KeyError, ValueError) as exc:
        raise AuthError("Access token has no valid subject") from exc

    if payload.get("is_anonymous"):
        raise AuthError("Anonymous sessions are not supported", status=403)

    email = str(payload.get("email") or "").strip().lower()
    if not email:
        raise AuthError("Access token has no email", status=403)

    user_metadata = payload.get("user_metadata") or {}
    display_name = user_metadata.get("display_name") or user_metadata.get("full_name") or user_metadata.get("name")
    return AuthClaims(
        auth_user_id=auth_user_id,
        email=email,
        email_verified=bool(user_metadata.get("email_verified")),
        display_name=str(display_name).strip() if display_name else None,
    )


async def resolve_user(db: AsyncSession, claims: AuthClaims) -> User:
    """Return the app user for these claims, linking or creating the users row.

    1. A row already linked to this Supabase user wins.
    2. Otherwise a row with the same email is linked, but only when the email is
       verified, so nobody can take over an existing account by signing up with
       someone else's address.
    3. Otherwise a new row is created.
    """
    user = (
        await db.execute(select(User).where(User.auth_user_id == claims.auth_user_id))
    ).scalar_one_or_none()
    if user is not None:
        return user

    if _require_verified_email() and not claims.email_verified:
        raise AuthError("Please confirm your email address before signing in.", status=403)

    user = (
        await db.execute(select(User).where(func.lower(User.email) == claims.email))
    ).scalar_one_or_none()

    if user is not None:
        if user.auth_user_id is not None and user.auth_user_id != claims.auth_user_id:
            raise AuthError("This email is already linked to a different sign-in.", status=409)
        user.auth_user_id = claims.auth_user_id
        if not user.display_name and claims.display_name:
            user.display_name = claims.display_name
        logger.info("🔗 Linked existing user %s to Supabase auth user", user.id)
    else:
        user = User(
            email=claims.email,
            display_name=claims.display_name or claims.email.split("@", 1)[0],
            auth_user_id=claims.auth_user_id,
        )
        db.add(user)
        logger.info("🆕 Created user for new Supabase auth user")

    await db.commit()
    await db.refresh(user)
    return user


async def delete_supabase_auth_user(auth_user_id: Optional[UUID]) -> bool:
    """Best-effort deletion of the Supabase Auth user (needs SUPABASE_SERVICE_ROLE_KEY)."""
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not auth_user_id or not service_key:
        return False

    import httpx

    url = f"{_supabase_url()}/auth/v1/admin/users/{auth_user_id}"
    headers = {"apikey": service_key, "Authorization": f"Bearer {service_key}"}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.delete(url, headers=headers)
        if response.status_code in (200, 204, 404):
            return True
        logger.warning("Supabase auth user deletion failed: HTTP %s", response.status_code)
    except Exception as exc:
        logger.warning("Supabase auth user deletion failed: %s", exc)
    return False
