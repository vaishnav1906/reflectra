"""Talk to Reflectra from the terminal to tune how it sounds.

Runs scripted multi-turn conversations through the real reply pipeline
(generate_reflection_reply / generate_mirror_response) using a real account's
context: name, earlier messages, texting style, persona. It is READ-ONLY:
nothing is written and the session is rolled back at the end.

Usage (from the repo root):
    .venv/Scripts/python scripts/backend/converse.py                # both modes
    .venv/Scripts/python scripts/backend/converse.py reflection
    .venv/Scripts/python scripts/backend/converse.py mirror
Optional: REFLECTRA_TEST_USER_EMAIL=<email> to pick the account.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND / ".env", override=True)

from sqlalchemy import select  # noqa: E402

from app.api.chat import (  # noqa: E402
    generate_reflection_reply,
    get_adaptive_mirror_style,
    load_personality_profile,
    resolve_mirror_task_type,
)
from app.db.database import AsyncSessionLocal  # noqa: E402
from app.db.models import User, UserSettings  # noqa: E402
from app.services.llm import LLMRateLimited  # noqa: E402
from app.services.mirror_engine import generate_mirror_response  # noqa: E402
from app.services.twin_policy import resolve_twin_settings  # noqa: E402

PAUSE_SECONDS = float(os.getenv("CONVERSE_PAUSE", "8"))  # stay under free-tier rate limits

SCRIPTS = {
    "reflection": [
        "hey",
        "long day. had my thesis review and my guide basically tore apart chapter 3",
        "idk, i spent like 3 weeks on it. maybe i'm just not cut out for research",
        "lol ok fair. but how do i even start fixing it",
        "thanks. gonna sleep on it",
    ],
    "mirror": [
        "ugh i have to text my landlord about the rent being late and i keep putting it off",
        "i know i know. it's just awkward",
        "can you draft the message for me",
        "ok sending it tomorrow morning lol",
        "also i need to write 2 pages of my thesis today and i haven't even opened the doc",
    ],
    "heavy": [
        "i don't really know why i'm typing this. everyone around me seems to have their life figured out and i just feel behind all the time",
        "like my friends are getting jobs and i'm still stuck on the same thesis chapter",
        "yeah maybe. i just wish i felt proud of something for once",
    ],
}


async def pick_user(db):
    email = os.getenv("REFLECTRA_TEST_USER_EMAIL")
    stmt = select(User)
    stmt = stmt.where(User.email == email.lower()) if email else stmt.where(User.auth_user_id.is_not(None))
    user = (await db.execute(stmt.limit(1))).scalar_one_or_none()
    if not user:
        raise SystemExit("No matching user found.")
    return user


async def run_mode(db, user, mode: str) -> None:
    script = SCRIPTS[mode]
    mode = "mirror" if mode.startswith("mirror") else "reflection"  # e.g. "heavy" runs as reflection
    print(f"\n=== {mode.upper()} ===")
    profile = await load_personality_profile(db, user.id)
    settings = (await db.execute(select(UserSettings).where(UserSettings.user_id == user.id))).scalar_one_or_none()
    twin_policy = resolve_twin_settings(settings)
    history: list[dict] = []

    for message in script:
        for attempt in range(3):
            started = time.time()
            try:
                if mode == "reflection":
                    reply = await generate_reflection_reply(
                        db, user.id, None, profile, history + [{"role": "user", "content": message}], message,
                        client_local_time="Sunday 11:48 PM",
                    )
                    extra = ""
                else:
                    task = resolve_mirror_task_type(message, history + [{"role": "user", "content": message}])
                    prior_user = [t["content"] for t in history if t["role"] == "user"]
                    style, emotion = get_adaptive_mirror_style(message, profile, prior_user)
                    reply, meta = await generate_mirror_response(
                        db, user.id, message, recent_history=history, twin_policy=twin_policy,
                        task_type=task, detected_emotion=emotion, active_mirror_style=style, persist=False,
                    )
                    extra = f"  [task={task} style={style} emotion={emotion} tier={meta.get('confidence_tier')} fallback={meta.get('fallback_triggered')}]"
                break
            except LLMRateLimited:
                print(f"      [AI busy (rate limit); waiting 30s, attempt {attempt + 1}/3]")
                await db.rollback()
                await asyncio.sleep(30)
        else:
            print(f"\nYOU:  {message}\nBOT:  <no reply: still rate-limited>")
            continue

        print(f"\nYOU:  {message}")
        print(f"BOT:  {reply}")
        print(f"      ({time.time() - started:.1f}s){extra}")
        history += [{"role": "user", "content": message}, {"role": "assistant", "content": reply}]
        await asyncio.sleep(PAUSE_SECONDS)


async def main() -> None:
    modes = sys.argv[1:] or ["reflection", "mirror"]
    async with AsyncSessionLocal() as db:
        try:
            user = await pick_user(db)
            for mode in modes:
                await run_mode(db, user, mode)
        finally:
            await db.rollback()  # read-only by design


if __name__ == "__main__":
    asyncio.run(main())
