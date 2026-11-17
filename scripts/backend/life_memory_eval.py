"""What would life memory pick out of a real account's history? Read-only.

Runs the same batch prompt and checks the backfill uses, on the most recent
messages, and prints the facts it would keep. Nothing is saved.

    .venv/Scripts/python scripts/backend/life_memory_eval.py [how_many_messages]
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND / ".env", override=True)

from sqlalchemy import select  # noqa: E402

from app.db.database import AsyncSessionLocal  # noqa: E402
from app.db.models import Message, User  # noqa: E402
from app.services import life_memory_service as lm  # noqa: E402
from app.services.llm import chat_complete  # noqa: E402
from app.services.persona_bootstrap_service import _extract_json, verify_quote  # noqa: E402


async def main() -> None:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 75
    async with AsyncSessionLocal() as db:
        email = os.getenv("REFLECTRA_TEST_USER_EMAIL")
        stmt = select(User.id)
        stmt = stmt.where(User.email == email.lower()) if email else stmt.where(User.auth_user_id.is_not(None))
        user_id = (await db.execute(stmt.limit(1))).scalar_one()
        rows = (
            await db.execute(
                select(Message.content, Message.created_at)
                .where(Message.user_id == user_id, Message.role == "user")
                .order_by(Message.created_at.desc())
                .limit(limit)
            )
        ).all()
    messages = [r for r in reversed(rows) if len((r[0] or "").split()) >= lm.MIN_WORDS]
    kept, dropped = [], 0
    for start in range(0, len(messages), 25):
        chunk = messages[start : start + 25]
        listing = "\n".join(f"[{i}] ({str(m[1])[:10]}) {' '.join(m[0].split())[:500]}" for i, m in enumerate(chunk))
        raw = await chat_complete(
            [{"role": "system", "content": lm.BACKFILL_PROMPT}, {"role": "user", "content": f"<messages>\n{listing}\n</messages>"}],
            max_tokens=900,
            temperature=0.0,
            fast=True,
        )
        for item in _extract_json(raw or "{}").get("facts") or []:
            try:
                source = chunk[int(item.get("id"))]
                text = lm.clean_text(str(item.get("text") or ""))
            except Exception:
                dropped += 1
                continue
            quote = " ".join(str(item.get("quote") or "").split())
            if item.get("kind") in lm.KINDS and quote and verify_quote(quote, source[0]):
                if not any(lm.is_same_fact(text, k[1]) for k in kept):
                    kept.append((item["kind"], text, quote, str(source[1])[:10]))
            else:
                dropped += 1
    print(f"read {len(messages)} messages; would keep {len(kept)} facts ({dropped} dropped by the checks)\n")
    for kind, text, quote, day in kept:
        print(f"  [{lm.KIND_LABEL[kind]}] {text}   <- {day}: \"{quote[:80]}\"")


if __name__ == "__main__":
    asyncio.run(main())
