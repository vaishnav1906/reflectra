"""Life memory endpoints: what Reflectra knows about your life, editable by you."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.db.database import get_db
from app.db.models import Job, LifeFact
from app.services import life_memory_service as lm
from app.services.job_service import enqueue

router = APIRouter(prefix="/life", tags=["life"])


class FactIn(BaseModel):
    kind: str = Field(pattern="^(about|situation|goal|preference|routine|place)$")
    text: str = Field(min_length=1, max_length=200)


class FactPatch(BaseModel):
    kind: Optional[str] = Field(default=None, pattern="^(about|situation|goal|preference|routine|place)$")
    text: Optional[str] = Field(default=None, min_length=1, max_length=200)
    status: Optional[str] = Field(default=None, pattern="^(active|resolved|outdated)$")
    pinned: Optional[bool] = None


async def _get(db: AsyncSession, user_id: UUID, fact_id: UUID) -> LifeFact:
    fact = (await db.execute(select(LifeFact).where(LifeFact.id == fact_id, LifeFact.user_id == user_id))).scalar_one_or_none()
    if fact is None:
        raise HTTPException(status_code=404, detail="That isn't in your life memory any more.")
    return fact


@router.get("")
async def list_facts(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    facts = await lm.facts_for(db, current_user.id)
    reading = (
        await db.execute(
            select(Job.id).where(Job.user_id == current_user.id, Job.kind == "life_memory_backfill", Job.status.in_(["queued", "running"]))
        )
    ).first()
    today = datetime.now(timezone.utc).date()
    return {
        "facts": [lm.serialize(f) for f in facts],
        "kinds": [{"kind": k, "label": lm.KIND_LABEL[k]} for k in lm.KINDS],
        "in_replies": lm.summary_lines(facts, today),
        "reading_history": reading is not None,
    }


@router.post("")
async def add_fact(body: FactIn, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    try:
        text_ = lm.clean_text(body.text)
    except lm.LifeMemoryError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    today = datetime.now(timezone.utc).date().isoformat()
    fact = LifeFact(
        user_id=current_user.id, kind=body.kind, statement=text_, source="you", status=lm.ACTIVE,
        pinned=False, mention_count=1, first_seen=today, last_seen=today,
    )
    db.add(fact)
    await db.commit()
    await db.refresh(fact)
    return lm.serialize(fact)


@router.patch("/{fact_id}")
async def edit_fact(fact_id: UUID, body: FactPatch, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    fact = await _get(db, current_user.id, fact_id)
    fields = body.model_dump(exclude_unset=True)
    try:
        if fields.get("text") is not None:
            fact.statement = lm.clean_text(fields["text"])
            fact.source = "you" if fact.source == "you" else fact.source
    except lm.LifeMemoryError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if fields.get("kind"):
        fact.kind = fields["kind"]
    if fields.get("status"):
        fact.status = fields["status"]
        if fact.status == lm.ACTIVE:
            fact.last_seen = datetime.now(timezone.utc).date().isoformat()
    if fields.get("pinned") is not None:
        fact.pinned = bool(fields["pinned"])
    fact.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(fact)
    return lm.serialize(fact)


@router.delete("/{fact_id}")
async def delete_fact(fact_id: UUID, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    fact = await _get(db, current_user.id, fact_id)
    await db.delete(fact)
    await db.commit()
    return {"id": str(fact_id), "deleted": True}


@router.post("/read-history")
async def read_history(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    """Read past chats once (in the background) to fill in the picture."""
    queued = await enqueue(db, current_user.id, "life_memory_backfill", {"limit": 160}, dedupe_key=f"life-backfill:{current_user.id}")
    return {"queued": queued}
