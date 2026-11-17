"""Follow-ups: things the user said they would do.

When someone says "i'll text my landlord tomorrow", Reflectra notes it, and the next
time they open a conversation after it was due, it can ask how it went. Once, like a
friend would, not like a task manager.

Stored in `behavioral_insights` (no new table):
    kind          "commitment" (open) | "commitment_done" | "commitment_dropped"
    title         what they said they'd do, in a few words
    insight_text  their exact words (verified to appear in the message)
    evidence      [{"date", "due", "asked_at", "asked_count", "closed_at", "closed_by"}]

Rules:
  - Only concrete intentions about their own life count; vague wishes do not.
  - The quote must really appear in their message, or nothing is saved.
  - Asked about at most twice, at least three days apart, and only at the start of a
    conversation. Never asked about before it is due.
  - Left open for three weeks, it is dropped quietly.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BehavioralInsight
from app.services.llm import chat_complete, llm_available
from app.services.persona_bootstrap_service import _extract_json, verify_quote

logger = logging.getLogger(__name__)

KIND_OPEN = "commitment"
KIND_DONE = "commitment_done"
KIND_DROPPED = "commitment_dropped"
ALL_KINDS = (KIND_OPEN, KIND_DONE, KIND_DROPPED)

MAX_OPEN = 8
MAX_ASKS = 2
DAYS_BETWEEN_ASKS = 3
EXPIRE_AFTER_DAYS = 21
DEFAULT_DUE_DAYS = 1  # "i'll do it" with no time given: fair to ask from the next day
MAX_DUE_DAYS = 60
SURFACED_PER_CONVERSATION = 2

# Cheap gate before any model call. Loose on purpose: the model makes the real decision.
INTENTION_PATTERN = re.compile(
    r"\b(i'?ll|i will|i'?m going to|im going to|i'?m gonna|im gonna|gonna|imma|ima|i need to|i have to|i gotta|gotta|"
    r"i should|i plan to|planning to|i want to start|starting (?:tomorrow|monday|today|next)|"
    r"tomorrow|tonight|today|this week|this weekend|this month|next week|later|in the morning|after (?:class|work|college|school)|by (?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|tomorrow|tonight|eod))\b",
    re.IGNORECASE,
)
UPDATE_PATTERN = re.compile(
    r"\b(did|done|sent|finished|submitted|finally|completed|went|started|called|texted|told|asked|paid|booked|"
    r"didn'?t|did not|never|forgot|gave up|not doing|skipped|couldn'?t|haven'?t|nah|nope|cancel+ed)\b",
    re.IGNORECASE,
)

EXTRACTION_PROMPT = """You read one chat message from a person and decide two things. Reply with JSON only.

1. "commitment": did they say they will do a specific thing in their own life?
   Count it only if all of these hold:
   - it is something THEY will do (not you, not someone else);
   - it is concrete enough that you could later ask "did you do it?" (texting a person,
     finishing a chapter, going to the gym tomorrow, booking an appointment);
   - it is in the future, not something already done.
   Do NOT count: vague wishes or self-criticism ("i should really exercise more",
   "i need to get my life together"), things they will tell or ask YOU ("i'll update you
   later"), hypotheticals, jokes, or plans they are only asking about.
   If it counts, give:
     "what": the thing in 3 to 9 plain words, no pronouns ("text landlord about the late rent")
     "quote": their exact words for it, copied character for character from the message
     "days_until_due": whole days from today until it should be done (today = 0,
        tomorrow = 1, "this week"/"soon" = 4, "next week" = 8; for a named weekday count
        from the "Today is ..." line), or null if they gave no time.
   Otherwise "commitment": null.

2. "updates": if a list of open items is given, did this message say any of them is now
   done, or that they have given up on it? List only items the message is clearly about:
     {"number": <item number>, "status": "done" | "dropped"}
   "done" means the message says it has ALREADY happened. Saying they will do it, are
   about to do it, or repeating the plan is NOT an update: leave it out.
   Not sure, or no list: "updates": [].

Output exactly: {"commitment": null | {"what": "...", "quote": "...", "days_until_due": 1}, "updates": []}"""

_STOP = {"the", "a", "an", "my", "to", "of", "and", "about", "for", "on", "in", "at", "it", "with", "that", "this", "some"}
_background: set = set()


def looks_like_intention(text: str) -> bool:
    return bool(INTENTION_PATTERN.search(text or "")) and len((text or "").split()) >= 4


def looks_like_update(text: str) -> bool:
    return bool(UPDATE_PATTERN.search(text or ""))


def _words(text: str) -> set:
    return {w for w in re.findall(r"[a-z0-9']+", (text or "").lower()) if w not in _STOP and len(w) > 2}


def is_same_commitment(a: str, b: str) -> bool:
    """Two phrasings of the same thing ("text landlord about rent" / "message the landlord re: rent")."""
    wa, wb = _words(a), _words(b)
    if not wa or not wb:
        return False
    return len(wa & wb) / min(len(wa), len(wb)) >= 0.6


def mentions(message: str, title: str) -> bool:
    """Does the message share a real word with the item ("texted the landlord" / "text landlord about rent")?"""
    said, item = _words(message), _words(title)
    return any(a[:4] == b[:4] for a in said for b in item)


def parse_extraction(raw: str, message: str, open_titles: Sequence[str] = ()) -> Dict[str, object]:
    """Validate the model's answer against the message itself.

    A new commitment needs a quote that really appears in the message. An update needs
    the message to share a word with the item it closes: wrongly closing something is
    worse than leaving it open, since an open item just gets asked about later.
    """
    open_count = len(open_titles)
    data = _extract_json(raw)
    result: Dict[str, object] = {"commitment": None, "updates": []}

    found = data.get("commitment")
    if isinstance(found, dict):
        what = " ".join(str(found.get("what") or "").split())[:120]
        quote = " ".join(str(found.get("quote") or "").split())[:300]
        if what and len(what.split()) >= 2 and verify_quote(quote, message):
            due = found.get("days_until_due")
            try:
                due_days = None if due is None else max(0, min(MAX_DUE_DAYS, int(due)))
            except (TypeError, ValueError):
                due_days = None
            result["commitment"] = {"what": what, "quote": quote, "days_until_due": due_days}

    for update in data.get("updates") or []:
        if not isinstance(update, dict):
            continue
        try:
            number = int(update.get("number"))
        except (TypeError, ValueError):
            continue
        status = str(update.get("status") or "").lower()
        if (
            1 <= number <= open_count
            and status in ("done", "dropped")
            and mentions(message, open_titles[number - 1])
        ):
            result["updates"].append({"number": number, "status": status})  # type: ignore[union-attr]
    return result


def local_today(tz_offset_minutes: int = 0, now: Optional[datetime] = None) -> date:
    return ((now or datetime.now(timezone.utc)) + timedelta(minutes=tz_offset_minutes)).date()


def _meta(row: BehavioralInsight) -> Dict[str, object]:
    evidence = row.evidence if isinstance(row.evidence, list) and row.evidence else [{}]
    return dict(evidence[0]) if isinstance(evidence[0], dict) else {}


def _parse_date(value: object) -> Optional[date]:
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


def due_state(meta: Dict[str, object], today: date) -> Dict[str, object]:
    """Whether a follow-up may be asked about today, and how to describe its timing."""
    made = _parse_date(meta.get("date")) or today
    due = _parse_date(meta.get("due")) or (made + timedelta(days=DEFAULT_DUE_DAYS))
    asked = _parse_date(meta.get("asked_at"))
    asked_count = int(meta.get("asked_count") or 0)
    days_open = (today - made).days
    overdue_by = (today - due).days
    return {
        "made": made,
        "due": due,
        "days_open": days_open,
        "overdue_by": overdue_by,
        "expired": days_open > EXPIRE_AFTER_DAYS,
        # "due today" is not askable yet: they still have the day to do it.
        "askable": overdue_by >= 1
        and asked_count < MAX_ASKS
        and (asked is None or (today - asked).days >= DAYS_BETWEEN_ASKS),
    }


def describe_for_prompt(title: str, quote: str, state: Dict[str, object]) -> str:
    days = int(state["days_open"])
    when = "yesterday" if days == 1 else f"{days} days ago" if days < 14 else f"{days // 7} weeks ago"
    return f'{when} they said they would {title} (their words: "{quote[:160]}")'


def serialize(row: BehavioralInsight, today: date) -> Dict[str, object]:
    meta = _meta(row)
    state = due_state(meta, today)
    status = {KIND_OPEN: "open", KIND_DONE: "done", KIND_DROPPED: "dropped"}.get(row.kind, "open")
    return {
        "id": str(row.id),
        "what": row.title or "",
        "quote": row.insight_text or "",
        "status": status,
        "said_on": str(state["made"]),
        "due": str(state["due"]),
        "overdue_by_days": max(0, int(state["overdue_by"])) if status == "open" else 0,
        "closed_on": str(meta.get("closed_at") or "")[:10] or None,
        "closed_by": meta.get("closed_by"),
        "conversation_id": str(row.conversation_id) if row.conversation_id else None,
    }


# --------------------------------------------------------------------------- database


async def _open_rows(db: AsyncSession, user_id: UUID) -> List[BehavioralInsight]:
    return list(
        (
            await db.execute(
                select(BehavioralInsight)
                .where(BehavioralInsight.user_id == user_id, BehavioralInsight.kind == KIND_OPEN)
                .order_by(BehavioralInsight.created_at.asc())
            )
        ).scalars().all()
    )


def _close(row: BehavioralInsight, status: str, by: str, today: date) -> None:
    meta = _meta(row)
    meta.update({"closed_at": str(today), "closed_by": by})
    row.evidence = [meta]
    row.kind = KIND_DONE if status == "done" else KIND_DROPPED


async def expire_stale(db: AsyncSession, user_id: UUID, today: date) -> int:
    expired = 0
    for row in await _open_rows(db, user_id):
        if due_state(_meta(row), today)["expired"]:
            _close(row, "dropped", "expired", today)
            expired += 1
    if expired:
        await db.flush()
    return expired


async def process_message(
    db: AsyncSession,
    user_id: UUID,
    conversation_id: Optional[UUID],
    message: str,
    tz_offset_minutes: int = 0,
) -> Dict[str, int]:
    """Note a new commitment and/or close ones the message says are finished. Commits."""
    outcome = {"added": 0, "closed": 0}
    if not llm_available():
        return outcome
    today = local_today(tz_offset_minutes)
    open_rows = await _open_rows(db, user_id)

    wants_new = looks_like_intention(message)
    wants_update = bool(open_rows) and looks_like_update(message)
    if not wants_new and not wants_update:
        return outcome

    listing = ""
    if open_rows:
        listing = "\n\nOpen items:\n" + "\n".join(f"{i}. {row.title}" for i, row in enumerate(open_rows, start=1))
    raw = await chat_complete(
        [
            {"role": "system", "content": EXTRACTION_PROMPT},
            {
                "role": "user",
                "content": f"Today is {today.strftime('%A')}.\n<message>\n{message[:1500]}\n</message>{listing}",
            },
        ],
        max_tokens=220,
        temperature=0.0,
        fast=True,
    )
    if not raw:
        return outcome
    try:
        parsed = parse_extraction(raw, message, open_titles=[row.title or "" for row in open_rows])
    except (ValueError, json.JSONDecodeError):
        logger.info("Follow-ups: unreadable model output, skipping")
        return outcome

    for update in parsed["updates"]:  # type: ignore[union-attr]
        row = open_rows[update["number"] - 1]
        if row.kind == KIND_OPEN:
            _close(row, update["status"], "said_in_chat", today)
            outcome["closed"] += 1

    found = parsed["commitment"]
    still_open = [row for row in open_rows if row.kind == KIND_OPEN]
    if isinstance(found, dict) and len(still_open) < MAX_OPEN:
        if not any(is_same_commitment(found["what"], row.title or "") for row in still_open):
            due_days = found["days_until_due"]
            db.add(
                BehavioralInsight(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    kind=KIND_OPEN,
                    title=found["what"],
                    insight_text=found["quote"],
                    tags=["follow-up"],
                    evidence=[
                        {
                            "date": str(today),
                            "due": str(today + timedelta(days=DEFAULT_DUE_DAYS if due_days is None else due_days)),
                            "asked_at": None,
                            "asked_count": 0,
                        }
                    ],
                )
            )
            outcome["added"] += 1

    if outcome["added"] or outcome["closed"]:
        await db.commit()
    return outcome


def schedule_processing(user_id: UUID, conversation_id: Optional[UUID], message: str, tz_offset_minutes: int = 0) -> None:
    """Run process_message after the reply has gone out, in its own database session."""
    if not llm_available() or not (looks_like_intention(message) or looks_like_update(message)):
        return

    async def run() -> None:
        from app.db.database import AsyncSessionLocal

        try:
            async with AsyncSessionLocal() as session:
                outcome = await process_message(session, user_id, conversation_id, message, tz_offset_minutes)
                if outcome["added"] or outcome["closed"]:
                    logger.info("Follow-ups: %s noted, %s closed", outcome["added"], outcome["closed"])
        except Exception as exc:  # never let this disturb a conversation
            logger.warning("Follow-ups skipped (%s)", str(exc)[:160])

    task = asyncio.create_task(run())
    _background.add(task)
    task.add_done_callback(_background.discard)


async def due_for_asking(
    db: AsyncSession,
    user_id: UUID,
    tz_offset_minutes: int = 0,
    mark_asked: bool = True,
) -> List[str]:
    """Lines for the reply prompt about follow-ups that are due. Marks them as asked."""
    today = local_today(tz_offset_minutes)
    await expire_stale(db, user_id, today)
    lines: List[str] = []
    for row in await _open_rows(db, user_id):
        meta = _meta(row)
        state = due_state(meta, today)
        if not state["askable"]:
            continue
        lines.append(describe_for_prompt(row.title or "", row.insight_text or "", state))
        if mark_asked:
            meta.update({"asked_at": str(today), "asked_count": int(meta.get("asked_count") or 0) + 1})
            row.evidence = [meta]
        if len(lines) >= SURFACED_PER_CONVERSATION:
            break
    if lines and mark_asked:
        await db.flush()
    return lines


async def list_followups(db: AsyncSession, user_id: UUID, tz_offset_minutes: int = 0) -> Dict[str, object]:
    """Open follow-ups, recently closed ones, and how often the user follows through."""
    today = local_today(tz_offset_minutes)
    if await expire_stale(db, user_id, today):
        await db.commit()
    rows = (
        await db.execute(
            select(BehavioralInsight)
            .where(BehavioralInsight.user_id == user_id, BehavioralInsight.kind.in_(ALL_KINDS))
            .order_by(BehavioralInsight.created_at.desc())
            .limit(200)
        )
    ).scalars().all()
    items = [serialize(row, today) for row in rows]
    done = sum(1 for item in items if item["status"] == "done")
    dropped = sum(1 for item in items if item["status"] == "dropped")
    closed = done + dropped
    return {
        "open": [item for item in items if item["status"] == "open"],
        "closed": [item for item in items if item["status"] != "open"][:12],
        "stats": {
            "done": done,
            "dropped": dropped,
            # Only meaningful once a few have been settled either way.
            "follow_through": round(done / closed, 3) if closed >= 3 else None,
        },
    }


async def set_status(db: AsyncSession, user_id: UUID, followup_id: UUID, status: str, tz_offset_minutes: int = 0) -> bool:
    row = (
        await db.execute(
            select(BehavioralInsight).where(
                BehavioralInsight.id == followup_id,
                BehavioralInsight.user_id == user_id,
                BehavioralInsight.kind.in_(ALL_KINDS),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return False
    today = local_today(tz_offset_minutes)
    if status == "open":
        meta = _meta(row)
        meta.pop("closed_at", None)
        meta.pop("closed_by", None)
        row.evidence = [meta]
        row.kind = KIND_OPEN
    else:
        _close(row, status, "you", today)
    await db.commit()
    return True
