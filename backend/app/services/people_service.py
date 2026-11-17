"""People: the friends and family in someone's life, so replies know who's who.

The user describes a person (name, nicknames, role, a few words about them). When
that person comes up in a chat, the reply gets a short briefing about them: who
they are to the user, what the user said they're like, and the latest things the
user has told Reflectra about them.

Reflectra also listens for people it doesn't know yet. Someone mentioned twice (or
introduced with a role, "my roommate Kev") is suggested for the user to confirm; it
never adds anyone silently. For people already known, new facts the user shares are
added to that person's notes, each with the user's exact words, and the user can
edit or delete any of it.

These are people who never signed up, so: everything is private to the user and
deletable, notes record only what the user said (no guesses about anyone's health,
private life or motives), and replies treat it as "from what you've told me".
"""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Person
from app.services.llm import chat_complete, llm_available
from app.services.persona_bootstrap_service import _extract_json, verify_quote

logger = logging.getLogger(__name__)

ACTIVE, SUGGESTED, DISMISSED = "active", "suggested", "dismissed"
MAX_PEOPLE = 200
MAX_NOTES = 40
NOTES_IN_BRIEFING = 3
MAX_BRIEFED = 4
SUGGEST_AFTER_MENTIONS = 2
NAME_MAX = 60

# Family roles people refer to without a name ("my mom"). Applied to a person only
# when their relationship says so and nobody else has the same role.
ROLE_ALIASES: Dict[str, List[str]] = {
    "mom": ["mom", "mum", "mother", "mommy", "mummy", "maa", "amma", "mama"],
    "dad": ["dad", "father", "papa", "daddy", "pops", "appa"],
    "sister": ["sister", "sis"],
    "brother": ["brother"],
    "grandma": ["grandma", "grandmother", "nani", "dadi", "granny"],
    "grandpa": ["grandpa", "grandfather", "nana", "dadu", "dada"],
    "wife": ["wife"],
    "husband": ["husband"],
    "girlfriend": ["girlfriend", "gf"],
    "boyfriend": ["boyfriend", "bf"],
    "roommate": ["roommate", "flatmate"],
    "boss": ["boss", "manager"],
}
ROLE_KEYWORDS: Dict[str, List[str]] = {
    "mom": ["mom", "mum", "mother"],
    "dad": ["dad", "father"],
    "sister": ["sister"],
    "brother": ["brother"],
    "grandma": ["grandma", "grandmother"],
    "grandpa": ["grandpa", "grandfather"],
    "wife": ["wife"],
    "husband": ["husband"],
    "girlfriend": ["girlfriend"],
    "boyfriend": ["boyfriend"],
    "roommate": ["roommate", "flatmate"],
    "boss": ["boss", "manager"],
}

# Names that are also ordinary words only count when written with a capital letter.
WORD_NAMES = frozenset(
    """will may june april august grace hope joy faith mark bill pat rose sky art max jack ray sunny rich bob
    rob sue dawn summer autumn amber ruby pearl harmony honey ace chase hunter hunter page mercy angel
    destiny star rain storm river ash buck chip dean frank gene glen guy hank jean lee les lily
    victor violet holly heather ivy iris dash""".split()
)

GROUPS = {
    "family": ["mom", "mum", "mother", "dad", "father", "sister", "brother", "grand", "aunt", "uncle", "cousin",
               "son", "daughter", "niece", "nephew", "family", "parent", "sibling", "in-law", "wife", "husband"],
    "partner": ["girlfriend", "boyfriend", "partner", "fiance", "fiancé", "crush", "spouse", "bae", "ex"],
    "work": ["boss", "manager", "coworker", "co-worker", "colleague", "teammate", "client", "mentor", "intern",
             "professor", "prof", "teacher", "hod", "advisor", "guide", "classmate", "lab"],
    "friends": ["friend", "bestie", "bff", "roommate", "flatmate", "buddy", "homie", "pal", "bro"],
}

EXTRACTION_PROMPT = """You read one message a person wrote to a companion app, plus the people already in their life.
Reply with JSON only.

Find the people THEY KNOW PERSONALLY that the message mentions, by name or by role ("my mom", "my boss").
Leave out: the person themself, the app, celebrities, streamers, creators, athletes, fictional characters,
and groups ("everyone", "my friends", "people").

For each person:
  "name": what they called them ("Kev", "Mom"). For a role-only mention, the role, capitalized.
  "known": the number of the matching person from the list below, or null if not on it.
  "relationship": who they are to the person, if the message says it ("roommate", "best friend"), else null.
  "fact": one thing the message says about this person or about how the person feels about them, worth
          remembering for weeks, in plain words ("Moving to Pune next month", "They had a falling out
          over the trip"). Call the person writing "you" ("You had a falling out over the trip").
          Nothing worth keeping (they just said hi, a passing mention): null.
          Never guess about anyone's health, sexuality, motives or private life beyond what is said.
  "quote": the exact words from the message the fact comes from, copied character for character, or null.

Output exactly: {"people": [{"name": "", "known": null, "relationship": null, "fact": null, "quote": null}]}"""

ROLE_WORDS = sorted({alias for aliases in ROLE_ALIASES.values() for alias in aliases if len(alias) > 2}, key=len, reverse=True)
CANDIDATE_PATTERN = re.compile(
    r"(?:\bmy\s+(?:" + "|".join(map(re.escape, ROLE_WORDS)) + r"|friend|bestie|best friend|cousin|aunt|uncle|coworker|colleague|prof|professor|teacher|neighbou?r)\b)"
    r"|(?:\b(?:with|to|from|text|texted|call|called|told|tell|ask|asked|met|meet|and)\s+[A-Za-z][a-z]{1,15}\b)"
    r"|(?:\b[a-z]{2,15}(?:'s|’s)\b)"
    r"|(?:(?<=[a-z,] )[A-Z][a-z]{1,15}\b)",
)

_background: set = set()


class PeopleError(ValueError):
    """Bad input; the message is safe to show."""


# --------------------------------------------------------------------------- matching


def name_key(name: str) -> str:
    return " ".join((name or "").strip().lower().split())[:NAME_MAX]


def clean_name(name: str) -> str:
    cleaned = " ".join((name or "").strip().split())[:NAME_MAX]
    if not cleaned or not re.search(r"[^\W\d_]", cleaned):
        raise PeopleError("A person needs a name.")
    return cleaned


def role_of(relationship: Optional[str]) -> Optional[str]:
    text = (relationship or "").lower()
    for role, words in ROLE_KEYWORDS.items():
        if any(re.search(rf"\b{re.escape(w)}\b", text) for w in words):
            return role
    return None


def group_of(relationship: Optional[str]) -> str:
    text = (relationship or "").lower()
    for group, words in GROUPS.items():
        if any(w in text for w in words):
            return group
    return "other"


def mention_terms(people: Sequence[Person]) -> Dict[UUID, List[str]]:
    """Every way each person can be referred to: name, first name, nicknames, and a
    family role when exactly one person has it."""
    roles: Dict[str, List[Person]] = {}
    for person in people:
        role = role_of(person.relationship_label)
        if role:
            roles.setdefault(role, []).append(person)
    terms: Dict[UUID, List[str]] = {}
    for person in people:
        words = [person.name, *(person.aliases or [])]
        first = (person.name or "").split()[0] if person.name else ""
        if first and first.lower() != (person.name or "").lower() and len(first) > 2:
            words.append(first)
        role = role_of(person.relationship_label)
        if role and len(roles.get(role, [])) == 1:
            words.extend(ROLE_ALIASES[role])
        seen, unique = set(), []
        for word in words:
            key = name_key(word)
            if key and key not in seen:
                seen.add(key)
                unique.append(word.strip())
        terms[person.id] = unique
    return terms


def _term_pattern(term: str) -> re.Pattern:
    return re.compile(r"(?<![\w'’])" + re.escape(term) + r"(?:'s|’s)?(?![\w'’])", re.IGNORECASE)


def find_mentions(text: str, people: Sequence[Person]) -> List[Person]:
    """The people the text mentions, in the order they first appear."""
    if not text or not people:
        return []
    terms = mention_terms(people)
    found: List[tuple] = []
    for person in people:
        first_at = None
        for term in terms.get(person.id, []):
            role_word = term.lower() in {a for aliases in ROLE_ALIASES.values() for a in aliases}
            for match in _term_pattern(term).finditer(text):
                written = match.group(0)
                if term.lower() in WORD_NAMES and not role_word and not written[:1].isupper():
                    continue  # "will", "may": only a name when capitalized
                if role_word and not re.search(r"\b(?:my|our|ur|your)\s+$", text[max(0, match.start() - 6):match.start()], re.IGNORECASE) and term.lower() in {"brother", "sister", "boss", "manager", "father", "mother"}:
                    continue  # "brother" alone is too often slang or general; needs "my brother"
                first_at = match.start() if first_at is None else min(first_at, match.start())
                break
        if first_at is not None:
            found.append((first_at, person))
    found.sort(key=lambda pair: pair[0])
    return [person for _, person in found]


def looks_like_people_talk(text: str) -> bool:
    """Cheap gate before asking the model who a message mentions."""
    return bool(text) and len(text.split()) >= 4 and bool(CANDIDATE_PATTERN.search(text))


# --------------------------------------------------------------------------- briefing


def _when(day: Optional[str], today: Optional[date] = None) -> str:
    try:
        then = date.fromisoformat(str(day)[:10])
    except (TypeError, ValueError):
        return "earlier"
    days = ((today or datetime.now(timezone.utc).date()) - then).days
    if days <= 0:
        return "today"
    if days == 1:
        return "yesterday"
    if days < 14:
        return f"{days} days ago"
    if days < 60:
        return f"{days // 7} weeks ago"
    return f"{days // 30} months ago"


def birthday_note(birthday: Optional[str], today: Optional[date] = None) -> Optional[str]:
    """'Their birthday is in 3 days' when it's within a week, else None."""
    if not birthday:
        return None
    today = today or datetime.now(timezone.utc).date()
    try:
        month, day = (int(x) for x in birthday[-5:].split("-"))
        upcoming = date(today.year, month, day)
    except (ValueError, TypeError):
        return None
    if upcoming < today:
        upcoming = date(today.year + 1, month, day)
    days = (upcoming - today).days
    if days == 0:
        return "It's their birthday today."
    if days <= 7:
        return f"Their birthday is in {days} day{'s' if days > 1 else ''}."
    return None


def briefing(person: Person, today: Optional[date] = None) -> str:
    """What a reply should know about this person, in a couple of lines."""
    head = person.name
    if person.relationship_label:
        head += f" ({person.relationship_label})"
    parts = [head]
    if person.description:
        parts.append(f"in their words: {person.description.strip()[:300]}")
    lines = ["; ".join(parts)]
    notes = sorted(person.notes or [], key=lambda n: str(n.get("date") or ""), reverse=True)[:NOTES_IN_BRIEFING]
    for note in notes:
        lines.append(f"  {_when(note.get('date'), today)}: {str(note.get('text') or '')[:200]}")
    soon = birthday_note(person.birthday, today)
    if soon:
        lines.append(f"  {soon}")
    return "\n".join(lines)


def briefings_for(text: str, people: Sequence[Person], today: Optional[date] = None) -> List[str]:
    return [briefing(p, today) for p in find_mentions(text, people)[:MAX_BRIEFED]]


# --------------------------------------------------------------------------- notes


def _note_words(text: str) -> set:
    return {w for w in re.findall(r"[a-z0-9']+", (text or "").lower()) if len(w) > 3}


def is_same_note(a: str, b: str) -> bool:
    wa, wb = _note_words(a), _note_words(b)
    if not wa or not wb:
        return a.strip().lower() == b.strip().lower()
    return len(wa & wb) / min(len(wa), len(wb)) >= 0.6


def add_note(
    person: Person, text: str, quote: Optional[str], day: str, conversation_id: Optional[UUID], source: str = "chat"
) -> bool:
    """Add a note unless it repeats one already there. Returns True if added."""
    text = " ".join((text or "").split())[:240]
    if not text:
        return False
    notes = list(person.notes or [])
    if any(is_same_note(text, str(n.get("text") or "")) for n in notes):
        return False
    notes.append(
        {
            "id": uuid.uuid4().hex[:12],
            "text": text,
            "quote": (" ".join((quote or "").split())[:300] or None),
            "date": day,
            "conversation_id": str(conversation_id) if conversation_id else None,
            "source": source,
        }
    )
    person.notes = notes[-MAX_NOTES:]
    return True


# --------------------------------------------------------------------------- storage


async def all_people(db: AsyncSession, user_id: UUID, statuses: Iterable[str] = (ACTIVE,)) -> List[Person]:
    try:
        return list(
            (
                await db.execute(
                    select(Person).where(Person.user_id == user_id, Person.status.in_(list(statuses))).limit(MAX_PEOPLE)
                )
            ).scalars().all()
        )
    except Exception:
        await db.rollback()
        return []


async def briefings_for_user(db: AsyncSession, user_id: UUID, text: str) -> tuple[List[str], List[Person]]:
    people = await all_people(db, user_id)
    mentioned = find_mentions(text, people)[:MAX_BRIEFED]
    return [briefing(p) for p in mentioned], mentioned


def parse_extraction(raw: str, message: str, known: Sequence[Person]) -> List[Dict[str, object]]:
    data = _extract_json(raw)
    out: List[Dict[str, object]] = []
    for item in data.get("people") or []:
        if not isinstance(item, dict):
            continue
        name = " ".join(str(item.get("name") or "").split())[:NAME_MAX]
        if not name or not re.search(r"[^\W\d_]", name):
            continue
        index = item.get("known")
        person = None
        if isinstance(index, int) and 1 <= index <= len(known):
            person = known[index - 1]
        fact = " ".join(str(item.get("fact") or "").split())[:240] or None
        quote = " ".join(str(item.get("quote") or "").split())[:300] or None
        if fact and not (quote and verify_quote(quote, message)):
            fact, quote = None, None  # facts must come from what they actually said
        relationship = " ".join(str(item.get("relationship") or "").split())[:80] or None
        out.append({"name": name, "person": person, "relationship": relationship, "fact": fact, "quote": quote})
    return out


async def process_message(
    db: AsyncSession, user_id: UUID, conversation_id: Optional[UUID], message: str, tz_offset_minutes: int = 0
) -> Dict[str, int]:
    """Count mentions, add notes about known people, and suggest new ones. Commits."""
    outcome = {"mentioned": 0, "notes": 0, "suggested": 0}
    everyone = await all_people(db, user_id, (ACTIVE, SUGGESTED, DISMISSED))
    active = [p for p in everyone if p.status == ACTIVE]
    now = datetime.now(timezone.utc)
    today = (now + timedelta(minutes=tz_offset_minutes)).date().isoformat()

    touched: Dict[UUID, Person] = {}
    for person in find_mentions(message, active):
        touched[person.id] = person

    if llm_available() and (touched or looks_like_people_talk(message)):
        known = [p for p in everyone if p.status != DISMISSED][:60]
        listing = "\n".join(
            f"{i}. {p.name}" + (f" ({p.relationship_label})" if p.relationship_label else "") for i, p in enumerate(known, 1)
        ) or "(nobody yet)"
        try:
            raw = await chat_complete(
                [
                    {"role": "system", "content": EXTRACTION_PROMPT},
                    {"role": "user", "content": f"<message>\n{message[:1500]}\n</message>\n\nPeople already in their life:\n{listing}"},
                ],
                max_tokens=400,
                temperature=0.0,
                fast=True,
            )
            found = parse_extraction(raw or "{}", message, known)
        except Exception as exc:
            logger.info("People: extraction skipped (%s)", str(exc)[:120])
            found = []

        by_key = {name_key(p.name): p for p in everyone}
        for alias_owner in everyone:
            for alias in alias_owner.aliases or []:
                by_key.setdefault(name_key(alias), alias_owner)
        for item in found:
            person = item["person"] or by_key.get(name_key(str(item["name"])))
            if person is None:
                if len(everyone) >= MAX_PEOPLE:
                    continue
                written = str(item["name"])
                display = written.title() if written.islower() else written  # "riya" -> "Riya"
                person = Person(
                    user_id=user_id,
                    name=display,
                    name_key=name_key(display),
                    relationship_label=item["relationship"],
                    status=SUGGESTED,
                    notes=[],
                    aliases=[],
                    mention_count=0,
                )
                db.add(person)
                everyone.append(person)
                by_key[person.name_key] = person
                outcome["suggested"] += 1
            if person.status == DISMISSED:
                continue
            if not person.relationship_label and item["relationship"]:
                person.relationship_label = str(item["relationship"])
            if item["fact"] and add_note(person, str(item["fact"]), item["quote"], today, conversation_id):
                outcome["notes"] += 1
            touched[person.id or uuid.uuid4()] = person

    for person in touched.values():
        person.mention_count = int(person.mention_count or 0) + 1
        person.last_mentioned_at = now
    outcome["mentioned"] = len(touched)
    if touched or outcome["suggested"]:
        await db.commit()
    return outcome


def schedule_processing(user_id: UUID, conversation_id: Optional[UUID], message: str, tz_offset_minutes: int = 0) -> None:
    """process_message after the reply has gone out, in its own database session."""

    async def run() -> None:
        from app.db.database import AsyncSessionLocal

        try:
            await asyncio.sleep(1.5)
            async with AsyncSessionLocal() as session:
                outcome = await process_message(session, user_id, conversation_id, message, tz_offset_minutes)
                if any(outcome.values()):
                    logger.info("People: %s", outcome)
        except Exception as exc:  # never let this disturb a conversation
            logger.warning("People update skipped (%s)", str(exc)[:160])

    task = asyncio.create_task(run())
    _background.add(task)
    task.add_done_callback(_background.discard)


# --------------------------------------------------------------------------- API helpers


def serialize(person: Person) -> Dict[str, object]:
    notes = sorted(person.notes or [], key=lambda n: str(n.get("date") or ""), reverse=True)
    return {
        "id": str(person.id),
        "name": person.name,
        "aliases": list(person.aliases or []),
        "relationship": person.relationship_label,
        "group": group_of(person.relationship_label),
        "description": person.description,
        "birthday": person.birthday,
        "birthday_note": birthday_note(person.birthday),
        "notes": notes,
        "status": person.status,
        "mention_count": int(person.mention_count or 0),
        "last_mentioned_at": person.last_mentioned_at.isoformat() if person.last_mentioned_at else None,
        "created_at": person.created_at.isoformat() if person.created_at else None,
    }


def worth_suggesting(person: Person) -> bool:
    return person.status == SUGGESTED and (
        int(person.mention_count or 0) >= SUGGEST_AFTER_MENTIONS or bool(person.relationship_label) or bool(person.notes)
    )


def clean_aliases(aliases: Optional[Sequence[str]], name: str) -> List[str]:
    seen = {name_key(name)}
    out = []
    for alias in aliases or []:
        cleaned = " ".join(str(alias).split())[:NAME_MAX]
        key = name_key(cleaned)
        if cleaned and key not in seen:
            seen.add(key)
            out.append(cleaned)
    return out[:12]


def clean_birthday(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%m-%d"):
        try:
            datetime.strptime(value if fmt == "%Y-%m-%d" else f"2000-{value}", "%Y-%m-%d")
            return value
        except ValueError:
            continue
    raise PeopleError("Birthday should look like 2001-03-14 or 03-14.")
