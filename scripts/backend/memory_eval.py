"""Check recall-by-meaning against a real account.

1. Embeds any of the account's exchanges that have no meaning vector yet
   (the only thing this script writes; --reset rebuilds them all).
2. Measures how similar unrelated messages are to each other, which is what the
   SEMANTIC_MIN_SIMILARITY threshold has to sit above.
3. Runs queries through recall twice, keywords only and keywords + meaning, and
   prints what each brings back.

Usage (from the repo root):
    .venv/Scripts/python scripts/backend/memory_eval.py "query one" "query two"
    .venv/Scripts/python scripts/backend/memory_eval.py            # built-in queries
Optional: REFLECTRA_TEST_USER_EMAIL=<email> to pick the account.
"""

from __future__ import annotations

import asyncio
import os
import random
import statistics
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND / ".env", override=True)

from sqlalchemy import select  # noqa: E402

from app.db.database import AsyncSessionLocal  # noqa: E402
from app.db.models import Message, User  # noqa: E402
from app.services import conversation_craft as craft  # noqa: E402
from app.services import embedding_service as emb  # noqa: E402

DEFAULT_QUERIES = [
    "i keep getting distracted by instagram whenever i sit down to study",
    "what's good fuel before a workout",
    "exams are stressing me out so bad",
    "do u think im lazy or just scared of failing",
    "what should i cook for dinner tonight",
]


async def pick_user(db):
    email = os.getenv("REFLECTRA_TEST_USER_EMAIL")
    stmt = select(User)
    stmt = stmt.where(User.email == email.lower()) if email else stmt.where(User.auth_user_id.is_not(None))
    user = (await db.execute(stmt.limit(1))).scalar_one_or_none()
    if not user:
        raise SystemExit("No matching user found.")
    return user.id


async def main() -> None:
    queries = [arg for arg in sys.argv[1:] if not arg.startswith("--")] or DEFAULT_QUERIES
    async with AsyncSessionLocal() as db:
        user_id = await pick_user(db)

        if not emb.embeddings_available():
            raise SystemExit("Embeddings need a Gemini key.")
        await emb.ensure_dimensions(db)
        if "--reset" in sys.argv:
            if not await emb.embed_texts(["quota check"]):
                raise SystemExit("Embedding API is not answering (rate limit?). Nothing was cleared; try again later.")
            await emb.clear_embeddings(db, user_id)
            print("cleared stored vectors")
        total = 0
        while True:
            done = await emb.backfill_embeddings(db, user_id, limit=64)
            total += done
            if not done:
                break
        print(f"embedded now: {total} | messages with a vector: {await emb.count_embedded(db, user_id)}")

        rows = (
            await db.execute(
                select(Message.embedding)
                .where(Message.user_id == user_id, Message.role == "user", Message.embedding.is_not(None))
                .limit(400)
            )
        ).scalars().all()
        vectors = [list(v) for v in rows]
        rng = random.Random(7)
        pairs = [rng.sample(range(len(vectors)), 2) for _ in range(min(3000, len(vectors) * 8))] if len(vectors) > 2 else []
        sims = sorted(emb.cosine(vectors[a], vectors[b]) for a, b in pairs)
        if sims:
            pick = lambda q: sims[min(len(sims) - 1, int(q * len(sims)))]  # noqa: E731
            print(
                f"similarity between random pairs of their messages: median {statistics.median(sims):.3f}, "
                f"90th pct {pick(0.9):.3f}, 97th pct {pick(0.97):.3f}, 99th pct {pick(0.99):.3f} "
                f"| threshold in use {craft.SEMANTIC_MIN_SIMILARITY}"
            )

        for query in queries:
            print(f"\nQUERY: {query}")
            for label, use_meaning in (("keywords only   ", False), ("keywords+meaning", True)):
                moment = await craft.load_moment_context(db, user_id, None, query_text=query, use_meaning=use_meaning)
                print(f"  {label}: {len(moment.related_memories)} recalled")
                for memory in moment.related_memories:
                    print(f"      - {memory[:150]}")
            vector = (await emb.embed_texts([query]) or [None])[0]
            if vector:
                top = sorted((await emb.semantic_matches(db, user_id, vector)).values(), key=lambda m: -m["similarity"])[:5]
                print("  closest (similarity/standout):", " ".join(f"{m['similarity']:.3f}/{m['standout']:+.1f}" for m in top))


if __name__ == "__main__":
    asyncio.run(main())
