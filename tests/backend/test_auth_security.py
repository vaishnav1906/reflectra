#!/usr/bin/env python3
"""Tests for Supabase token verification, user linking, per-route ownership
enforcement and incognito chats not writing anything."""

import asyncio
import os
import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/none")

import jwt  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import ec  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.api import deps  # noqa: E402
from app.db.database import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services import auth_service  # noqa: E402
from app.services.auth_service import AuthClaims, AuthError, claims_from_payload, decode_access_token, resolve_user  # noqa: E402

SUPABASE_URL = "https://example-ref.supabase.co"
ISSUER = f"{SUPABASE_URL}/auth/v1"
SECRET = "test-secret-with-enough-length-for-hs256-0123456789"


def _payload(**overrides):
    now = int(time.time())
    payload = {
        "sub": str(uuid4()),
        "aud": "authenticated",
        "iss": ISSUER,
        "exp": now + 3600,
        "iat": now,
        "email": "Person@Example.com",
        "role": "authenticated",
        "user_metadata": {"email_verified": True, "display_name": "Person"},
    }
    payload.update(overrides)
    return payload


class TokenVerificationTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"SUPABASE_URL": SUPABASE_URL, "SUPABASE_JWT_SECRET": SECRET})
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def test_valid_hs256_token(self):
        token = jwt.encode(_payload(), SECRET, algorithm="HS256")
        claims = claims_from_payload(decode_access_token(token))
        self.assertEqual(claims.email, "person@example.com")
        self.assertTrue(claims.email_verified)
        self.assertEqual(claims.display_name, "Person")

    def test_rejects_expired_wrong_audience_wrong_issuer_and_bad_signature(self):
        bad_tokens = {
            "expired": jwt.encode(_payload(exp=int(time.time()) - 10), SECRET, algorithm="HS256"),
            "audience": jwt.encode(_payload(aud="anon"), SECRET, algorithm="HS256"),
            "issuer": jwt.encode(_payload(iss="https://evil.example/auth/v1"), SECRET, algorithm="HS256"),
            "signature": jwt.encode(_payload(), "another-secret-of-sufficient-length-000000", algorithm="HS256"),
        }
        for name, token in bad_tokens.items():
            with self.subTest(name), self.assertRaises(AuthError) as ctx:
                decode_access_token(token)
            self.assertEqual(ctx.exception.status, 401)

    def test_rejects_unsigned_token(self):
        token = jwt.encode(_payload(), None, algorithm="none")
        with self.assertRaises(AuthError):
            decode_access_token(token)

    def test_asymmetric_token_verified_with_jwks_key(self):
        private_key = ec.generate_private_key(ec.SECP256R1())
        token = jwt.encode(_payload(), private_key, algorithm="ES256", headers={"kid": "k1"})
        fake_client = MagicMock()
        fake_client.get_signing_key_from_jwt.return_value = SimpleNamespace(key=private_key.public_key())
        with patch.object(auth_service, "_jwks_client", return_value=fake_client) as jwks:
            payload = decode_access_token(token)
        jwks.assert_called_once_with(f"{ISSUER}/.well-known/jwks.json")
        self.assertEqual(payload["email"], "Person@Example.com")

    def test_anonymous_session_rejected(self):
        with self.assertRaises(AuthError) as ctx:
            claims_from_payload(_payload(is_anonymous=True))
        self.assertEqual(ctx.exception.status, 403)


class _Result:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeDB:
    def __init__(self, *results):
        self.results = list(results)
        self.added = []
        self.commits = 0

    async def execute(self, *_args, **_kwargs):
        return _Result(self.results.pop(0) if self.results else None)

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1

    async def refresh(self, _obj):
        return None


def _claims(verified=True):
    return AuthClaims(auth_user_id=uuid4(), email="person@example.com", email_verified=verified, display_name="Person")


class ResolveUserTests(unittest.TestCase):
    def test_returns_already_linked_user(self):
        linked = SimpleNamespace(id=uuid4())
        db = _FakeDB(linked)
        self.assertIs(asyncio.run(resolve_user(db, _claims())), linked)
        self.assertEqual(db.commits, 0)

    def test_links_existing_email_account_when_verified(self):
        existing = SimpleNamespace(id=uuid4(), auth_user_id=None, display_name="Old")
        claims = _claims()
        db = _FakeDB(None, existing)
        user = asyncio.run(resolve_user(db, claims))
        self.assertIs(user, existing)
        self.assertEqual(existing.auth_user_id, claims.auth_user_id)
        self.assertEqual(db.commits, 1)

    def test_unverified_email_cannot_link_or_create(self):
        db = _FakeDB(None, SimpleNamespace(id=uuid4(), auth_user_id=None, display_name=None))
        with self.assertRaises(AuthError) as ctx:
            asyncio.run(resolve_user(db, _claims(verified=False)))
        self.assertEqual(ctx.exception.status, 403)

    def test_email_linked_to_other_auth_user_conflicts(self):
        existing = SimpleNamespace(id=uuid4(), auth_user_id=uuid4(), display_name="Old")
        with self.assertRaises(AuthError) as ctx:
            asyncio.run(resolve_user(_FakeDB(None, existing), _claims()))
        self.assertEqual(ctx.exception.status, 409)

    def test_creates_new_user(self):
        db = _FakeDB(None, None)
        user = asyncio.run(resolve_user(db, _claims()))
        self.assertEqual(db.added, [user])
        self.assertEqual(user.email, "person@example.com")


class _NoopSession:
    """Stands in for the DB session in routing tests; any query returns nothing."""

    def __init__(self):
        self.writes = 0

    async def execute(self, *_args, **_kwargs):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        result.scalars.return_value.all.return_value = []
        result.all.return_value = []
        return result

    def add(self, _obj):
        self.writes += 1

    async def flush(self):
        self.writes += 1

    async def commit(self):
        self.writes += 1

    async def rollback(self):
        return None


class RouteProtectionTests(unittest.TestCase):
    def setUp(self):
        self.user = SimpleNamespace(id=uuid4(), auth_user_id=uuid4(), email="me@example.com", display_name="Me")
        self.session = _NoopSession()

        async def _db():
            yield self.session

        app.dependency_overrides[get_db] = _db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def _login(self):
        app.dependency_overrides[deps.get_current_user] = lambda: self.user

    def test_requires_token(self):
        for method, url in [
            ("get", f"/persona/profile/{self.user.id}"),
            ("get", f"/conversations?user_id={self.user.id}"),
            ("get", f"/analytics/metrics/{self.user.id}"),
            ("get", "/auth/me"),
        ]:
            with self.subTest(url=url):
                self.assertEqual(getattr(self.client, method)(url).status_code, 401)

    def test_health_stays_public(self):
        self.assertEqual(self.client.get("/health").status_code, 200)

    def test_other_users_ids_are_forbidden(self):
        self._login()
        other = uuid4()
        cases = [
            ("get", f"/persona/profile/{other}", None),
            ("get", f"/conversations?user_id={other}", None),
            ("get", f"/analytics/timeline/{other}", None),
            ("get", f"/user/settings?user_id={other}", None),
            ("post", "/user/clear-data", {"user_id": str(other)}),
            ("delete", "/user/delete-account", {"user_id": str(other)}),
            ("post", "/chat", {"user_id": str(other), "message": "hi", "mode": "reflection"}),
        ]
        for method, url, body in cases:
            with self.subTest(url=url):
                if method == "get":
                    response = self.client.get(url)
                else:
                    response = self.client.request(method.upper(), url, json=body)
                self.assertEqual(response.status_code, 403, response.text)
        self.assertEqual(self.session.writes, 0)

    def test_me_returns_current_user(self):
        self._login()
        response = self.client.get("/auth/me")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], str(self.user.id))

    def test_email_only_login_is_gone(self):
        response = self.client.post("/auth/login", json={"email": "x@example.com", "display_name": "x"})
        self.assertIn(response.status_code, {404, 405})

    def test_incognito_chat_writes_nothing(self):
        self._login()
        with patch("app.api.chat.generate_llm_response", new=AsyncMock(return_value="A thoughtful reply.")), \
             patch("app.api.chat.crud.create_conversation", new=AsyncMock()) as create_conv, \
             patch("app.api.chat.crud.create_message", new=AsyncMock()) as create_msg:
            response = self.client.post(
                "/chat",
                json={
                    "message": "I keep avoiding my essay",
                    "mode": "reflection",
                    "is_incognito": True,
                    "incognito_session_id": "abc",
                    "history": [{"role": "user", "content": "earlier"}, {"role": "assistant", "content": "ok"}],
                },
            )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["conversation_id"], "abc")
        create_conv.assert_not_awaited()
        create_msg.assert_not_awaited()
        self.assertEqual(self.session.writes, 0)

    def test_incognito_cleanup_route_exists(self):
        self._login()
        self.assertEqual(self.client.delete("/chat/incognito-history/abc").status_code, 204)

    def test_cors_does_not_allow_arbitrary_origins(self):
        response = self.client.options(
            "/health",
            headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
        )
        self.assertNotEqual(response.headers.get("access-control-allow-origin"), "*")
        self.assertNotEqual(response.headers.get("access-control-allow-origin"), "https://evil.example")


if __name__ == "__main__":
    unittest.main()
