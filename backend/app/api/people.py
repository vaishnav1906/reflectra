"""People endpoints: the friends and family a user tells Reflectra about.

Always the signed-in user's own people; nothing here takes a user id.
"""

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.db.database import get_db
from app.db.models import Person
from app.services import people_service as ps

router = APIRouter(prefix="/people", tags=["people"])


class PersonIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    relationship: Optional[str] = Field(default=None, max_length=80)
    description: Optional[str] = Field(default=None, max_length=1000)
    aliases: List[str] = Field(default_factory=list, max_length=12)
    birthday: Optional[str] = Field(default=None, max_length=10)


class PersonPatch(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=60)
    relationship: Optional[str] = Field(default=None, max_length=80)
    description: Optional[str] = Field(default=None, max_length=1000)
    aliases: Optional[List[str]] = Field(default=None, max_length=12)
    birthday: Optional[str] = Field(default=None, max_length=10)


class NoteIn(BaseModel):
    text: str = Field(min_length=1, max_length=240)


def _bad(exc: ps.PeopleError):
    raise HTTPException(status_code=422, detail=str(exc))


async def _get(db: AsyncSession, user_id: UUID, person_id: UUID) -> Person:
    person = (
        await db.execute(select(Person).where(Person.id == person_id, Person.user_id == user_id))
    ).scalar_one_or_none()
    if person is None:
        raise HTTPException(status_code=404, detail="That person isn't in your People.")
    return person


def _apply(person: Person, fields: dict) -> None:
    if "name" in fields and fields["name"] is not None:
        person.name = ps.clean_name(fields["name"])
        person.name_key = ps.name_key(person.name)
    if "relationship" in fields:
        person.relationship_label = (" ".join((fields["relationship"] or "").split()) or None)
    if "description" in fields:
        person.description = (fields["description"] or "").strip() or None
    if "aliases" in fields and fields["aliases"] is not None:
        person.aliases = ps.clean_aliases(fields["aliases"], person.name)
    if "birthday" in fields:
        person.birthday = ps.clean_birthday(fields["birthday"])
    person.updated_at = datetime.now(timezone.utc)


@router.get("")
async def list_people(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    everyone = await ps.all_people(db, current_user.id, (ps.ACTIVE, ps.SUGGESTED))
    active = sorted(
        (p for p in everyone if p.status == ps.ACTIVE),
        key=lambda p: (p.last_mentioned_at or p.created_at or datetime.min.replace(tzinfo=timezone.utc)),
        reverse=True,
    )
    suggestions = sorted(
        (p for p in everyone if ps.worth_suggesting(p)), key=lambda p: int(p.mention_count or 0), reverse=True
    )
    return {"people": [ps.serialize(p) for p in active], "suggestions": [ps.serialize(p) for p in suggestions[:8]]}


@router.post("")
async def add_person(body: PersonIn, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    try:
        key = ps.name_key(ps.clean_name(body.name))
    except ps.PeopleError as exc:
        _bad(exc)
    existing = (
        await db.execute(select(Person).where(Person.user_id == current_user.id, Person.name_key == key))
    ).scalar_one_or_none()
    if existing is not None and existing.status == ps.ACTIVE:
        raise HTTPException(status_code=409, detail=f"{existing.name} is already in your People.")
    person = existing or Person(user_id=current_user.id, notes=[], aliases=[], mention_count=0)
    try:
        _apply(person, body.model_dump())
    except ps.PeopleError as exc:
        _bad(exc)
    person.status = ps.ACTIVE  # a suggestion with this name keeps what was noticed about them
    if existing is None:
        db.add(person)
    await db.commit()
    await db.refresh(person)
    return ps.serialize(person)


@router.patch("/{person_id}")
async def edit_person(person_id: UUID, body: PersonPatch, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    person = await _get(db, current_user.id, person_id)
    fields = body.model_dump(exclude_unset=True)
    if fields.get("name"):
        key = ps.name_key(fields["name"])
        clash = (
            await db.execute(
                select(Person.id).where(Person.user_id == current_user.id, Person.name_key == key, Person.id != person.id)
            )
        ).scalar_one_or_none()
        if clash is not None:
            raise HTTPException(status_code=409, detail="Someone with that name is already in your People.")
    try:
        _apply(person, fields)
    except ps.PeopleError as exc:
        _bad(exc)
    await db.commit()
    await db.refresh(person)
    return ps.serialize(person)


@router.post("/{person_id}/accept")
async def accept_suggestion(person_id: UUID, body: PersonPatch, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    person = await _get(db, current_user.id, person_id)
    try:
        _apply(person, body.model_dump(exclude_unset=True))
    except ps.PeopleError as exc:
        _bad(exc)
    person.status = ps.ACTIVE
    await db.commit()
    await db.refresh(person)
    return ps.serialize(person)


@router.post("/{person_id}/dismiss")
async def dismiss_suggestion(person_id: UUID, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    """Not someone to keep track of: it won't be suggested again, and its notes are dropped."""
    person = await _get(db, current_user.id, person_id)
    person.status = ps.DISMISSED
    person.notes = []
    person.description = None
    await db.commit()
    return {"id": str(person.id), "status": person.status}


@router.delete("/{person_id}")
async def delete_person(person_id: UUID, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    """Forget them completely: card, nicknames and every note."""
    person = await _get(db, current_user.id, person_id)
    await db.delete(person)
    await db.commit()
    return {"id": str(person_id), "deleted": True}


@router.post("/{person_id}/notes")
async def add_note(person_id: UUID, body: NoteIn, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    person = await _get(db, current_user.id, person_id)
    ps.add_note(person, body.text, None, datetime.now(timezone.utc).date().isoformat(), None, source="you")
    await db.commit()
    await db.refresh(person)
    return ps.serialize(person)


@router.delete("/{person_id}/notes/{note_id}")
async def delete_note(person_id: UUID, note_id: str, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    person = await _get(db, current_user.id, person_id)
    person.notes = [n for n in (person.notes or []) if n.get("id") != note_id]
    await db.commit()
    await db.refresh(person)
    return ps.serialize(person)
