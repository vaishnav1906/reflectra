"""Delivering notifications: Web Push to browsers (Android and iOS apps can add their
own senders for platform "android" / "ios" later, against the same table).

Web Push needs a VAPID key pair: the public half goes to the browser when it
subscribes, the private half signs every push. Set VAPID_PUBLIC_KEY and
VAPID_PRIVATE_KEY in production; in development a pair is generated on first use
and kept in backend/.vapid.json (git-ignored).

A notification never says what the user talked about: the lock screen shows a
neutral line, and the real question appears inside the app.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PushSubscription

logger = logging.getLogger(__name__)

KEY_FILE = Path(__file__).resolve().parents[2] / ".vapid.json"
MAX_FAILURES = 3
# Who to contact about these pushes (required by the push services). The project's
# public page, not anyone's personal address.
DEFAULT_SUBJECT = "https://github.com/vaishnav1906/reflectra"

_keys: Optional[Tuple[str, str]] = None


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def vapid_keys() -> Tuple[str, str]:
    """(public key for browsers, private key for signing), both base64url."""
    global _keys
    if _keys:
        return _keys
    public, private = os.getenv("VAPID_PUBLIC_KEY", "").strip(), os.getenv("VAPID_PRIVATE_KEY", "").strip()
    if public and private:
        _keys = (public, private)
        return _keys
    if KEY_FILE.exists():
        stored = json.loads(KEY_FILE.read_text(encoding="utf-8"))
        _keys = (stored["public"], stored["private"])
        return _keys
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    key = ec.generate_private_key(ec.SECP256R1())
    private = _b64url(key.private_numbers().private_value.to_bytes(32, "big"))
    public = _b64url(key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint))
    KEY_FILE.write_text(json.dumps({"public": public, "private": private}), encoding="utf-8")
    logger.info("Generated Web Push keys in %s (set VAPID_* env vars in production)", KEY_FILE)
    _keys = (public, private)
    return _keys


def _send_web_push(subscription: Dict[str, object], payload: Dict[str, object]) -> int:
    """Blocking send; returns the push service's status code (0 on a network error)."""
    from pywebpush import WebPushException, webpush

    _, private = vapid_keys()
    try:
        response = webpush(
            subscription_info=subscription,
            data=json.dumps(payload),
            vapid_private_key=private,
            vapid_claims={"sub": os.getenv("VAPID_SUBJECT", DEFAULT_SUBJECT)},
            ttl=12 * 3600,
        )
        return int(getattr(response, "status_code", 201) or 201)
    except WebPushException as exc:
        return int(getattr(exc.response, "status_code", 0) or 0)
    except Exception:
        logger.exception("Web Push failed")
        return 0


async def save_subscription(
    db: AsyncSession, user_id: UUID, endpoint: str, keys: Dict[str, str], platform: str = "web", user_agent: str = ""
) -> PushSubscription:
    row = (await db.execute(select(PushSubscription).where(PushSubscription.endpoint == endpoint))).scalar_one_or_none()
    if row is None:
        row = PushSubscription(endpoint=endpoint)
        db.add(row)
    row.user_id = user_id  # a browser can only belong to whoever subscribed it last
    row.platform = platform
    row.keys = {k: str(v) for k, v in (keys or {}).items() if k in ("p256dh", "auth")}
    row.user_agent = (user_agent or "")[:200]
    row.failures = 0
    await db.commit()
    return row


async def remove_subscription(db: AsyncSession, user_id: UUID, endpoint: str) -> None:
    await db.execute(delete(PushSubscription).where(PushSubscription.user_id == user_id, PushSubscription.endpoint == endpoint))
    await db.commit()


async def subscriptions_for(db: AsyncSession, user_id: UUID) -> List[PushSubscription]:
    return list((await db.execute(select(PushSubscription).where(PushSubscription.user_id == user_id))).scalars().all())


async def deliver(db: AsyncSession, user_id: UUID, payload: Dict[str, object]) -> int:
    """Send to every device the user has; returns how many accepted it. Devices that
    are gone (404/410) or keep failing are forgotten."""
    delivered = 0
    for sub in await subscriptions_for(db, user_id):
        if sub.platform != "web":
            continue  # the phone apps will deliver through their own services
        status = await asyncio.to_thread(_send_web_push, {"endpoint": sub.endpoint, "keys": sub.keys or {}}, payload)
        if 200 <= status < 300:
            delivered += 1
            sub.failures = 0
            sub.last_sent_at = datetime.now(timezone.utc)
        elif status in (404, 410):
            await db.delete(sub)
        else:
            sub.failures = int(sub.failures or 0) + 1
            if sub.failures >= MAX_FAILURES:
                await db.delete(sub)
    await db.commit()
    return delivered
