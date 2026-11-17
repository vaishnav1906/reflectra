"""Does follow-up detection catch real commitments and leave everything else alone?

Sends labelled messages (slang included) through the same prompt and validation the
app uses. Writes nothing.

    .venv/Scripts/python scripts/backend/followup_eval.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND / ".env", override=True)

from app.services import followup_service as fu  # noqa: E402
from app.services.llm import chat_complete  # noqa: E402

OPEN = ["text landlord about the late rent", "go to the gym in the mornings"]

# (message, expect a new commitment?, expected due days or None for "any", expected updates)
CASES = [
    ("ugh fine i'll text my landlord about the rent tomorrow morning", True, 1, []),
    ("gonna start hitting the gym from monday fr fr", True, 6, []),
    ("i need to submit the internship form by friday or im cooked", True, 3, []),
    ("ima finish chapter 3 tonight no cap", True, 0, []),
    ("aight bet, booking the dentist this week", True, None, []),
    ("i should really exercise more ngl", False, None, []),
    ("i need to get my life together bro", False, None, []),
    ("i'll tell u later what happened", False, None, []),
    ("tomorrow is gonna be so boring", False, None, []),
    ("what if i just dropped out and started a business lol", False, None, []),
    ("wassup gang, do u think u gonna slide or some shii ukwim", False, None, []),
    ("my friend said he's gonna move to pune next month", False, None, []),
    ("i already sent the assignment yesterday", False, None, []),
    ("finally texted the landlord, he was chill about it", False, None, [(1, "done")]),
    ("nah im not doing the morning gym thing anymore, not for me", False, None, [(2, "dropped")]),
    ("went to the gym at 6 today lets goo, and i'll call mom tonight", True, 0, [(2, "done")]),
]


async def run_case(message: str, with_open: bool):
    listing = "\n\nOpen items:\n" + "\n".join(f"{i}. {t}" for i, t in enumerate(OPEN, start=1)) if with_open else ""
    raw = await chat_complete(
        [
            {"role": "system", "content": fu.EXTRACTION_PROMPT},
            {"role": "user", "content": f"Today is Tuesday.\n<message>\n{message}\n</message>{listing}"},
        ],
        max_tokens=220,
        temperature=0.0,
        fast=True,
    )
    return fu.parse_extraction(raw or "{}", message, open_titles=OPEN if with_open else [])


async def main() -> None:
    correct = 0
    gate_misses = 0
    for message, expect_new, expect_due, expect_updates in CASES:
        gate = fu.looks_like_intention(message) or fu.looks_like_update(message)
        if not gate:
            parsed = {"commitment": None, "updates": []}  # the app would not even call the model
        else:
            try:
                parsed = await run_case(message, with_open=True)
            except Exception as exc:
                print(f"ERR  {message[:60]!r}: {str(exc)[:80]}")
                continue
            await asyncio.sleep(1.5)
        found = parsed["commitment"]
        updates = sorted((u["number"], u["status"]) for u in parsed["updates"])
        ok = (found is not None) == expect_new and updates == sorted(expect_updates)
        if ok and expect_new and expect_due is not None:
            ok = found["days_until_due"] == expect_due
        if (expect_new or expect_updates) and not gate:
            gate_misses += 1
        correct += ok
        detail = f"{found['what']!r} due+{found['days_until_due']}" if found else "none"
        print(f"{'ok  ' if ok else 'MISS'} {message[:58]:<58} -> {detail}{' | ' + str(updates) if updates else ''}")
    print(f"\n{correct}/{len(CASES)} correct, {gate_misses} blocked by the pre-filter")


if __name__ == "__main__":
    asyncio.run(main())
