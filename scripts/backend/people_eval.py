"""Does People extraction find the right people and leave everyone else out?

Labelled messages (slang included) go through the same prompt and validation the
app uses. Writes nothing.

    .venv/Scripts/python scripts/backend/people_eval.py
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

BACKEND = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND / ".env", override=True)

from app.services import people_service as ps  # noqa: E402
from app.services.llm import chat_complete  # noqa: E402

KNOWN = [
    SimpleNamespace(id=uuid.uuid4(), name="Kev", relationship_label="roommate", aliases=[], notes=[]),
    SimpleNamespace(id=uuid.uuid4(), name="Asha", relationship_label="mom", aliases=[], notes=[]),
]

# (message, expected names (lowercase), names whose fact should be kept)
CASES = [
    ("nah bro the function at kev's tn, everybody pulling up but ion feel it", {"kev"}, set()),
    ("my roommate kev is moving out next month and ngl im kinda sad about it", {"kev"}, {"kev"}),
    ("my mom found out i failed the test 💀 she's not talking to me", {"asha"}, {"asha"}),
    ("me n riya got into it over the trip, she thinks i bailed on her", {"riya"}, {"riya"}),
    ("my boss sanjay keeps giving me work at 9pm fr", {"sanjay"}, {"sanjay"}),
    ("watched nessie's stream all night lmao", set(), set()),
    ("drake dropped and its mid ngl", set(), set()),
    ("everyone at work is so fake", set(), set()),
    ("wassup gang, do u think u gonna slide or some shii ukwim", set(), set()),
    ("texted jay and he just left me on read", {"jay"}, {"jay"}),
]


async def main() -> None:
    listing = "\n".join(f"{i}. {p.name} ({p.relationship_label})" for i, p in enumerate(KNOWN, 1))
    right = 0
    for message, expected, with_fact in CASES:
        raw = await chat_complete(
            [
                {"role": "system", "content": ps.EXTRACTION_PROMPT},
                {"role": "user", "content": f"<message>\n{message}\n</message>\n\nPeople already in their life:\n{listing}"},
            ],
            max_tokens=400,
            temperature=0.0,
            fast=True,
        )
        found = ps.parse_extraction(raw or "{}", message, KNOWN)
        names = {(f["person"].name if f["person"] else str(f["name"])).lower() for f in found}
        facts = {(f["person"].name if f["person"] else str(f["name"])).lower() for f in found if f["fact"]}
        ok = names == expected and with_fact <= facts
        right += ok
        detail = ", ".join(
            f"{(f['person'].name if f['person'] else f['name'])}{' [known]' if f['person'] else ''}"
            + (f" ({f['relationship']})" if f["relationship"] else "")
            + (f": {f['fact']}" if f["fact"] else "")
            for f in found
        ) or "nobody"
        print(f"{'ok  ' if ok else 'MISS'} {message[:60]:<60} -> {detail}")
        await asyncio.sleep(1.2)
    print(f"\n{right}/{len(CASES)} correct")


if __name__ == "__main__":
    asyncio.run(main())
