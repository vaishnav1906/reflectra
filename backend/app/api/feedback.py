"""Feedback endpoints: rate a reply, a trait reading or a reflection.

The user is always the signed-in user; nothing here takes a user id.
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.db.database import get_db
from app.services import feedback_service as fb

router = APIRouter(prefix="/feedback", tags=["feedback"])


class ReplyFeedback(BaseModel):
    verdict: str = Field(pattern="^(up|down|clear)$")
    reasons: List[str] = Field(default_factory=list, max_length=6)


class TraitFeedback(BaseModel):
    verdict: str = Field(pattern="^(agree|disagree)$")
    self_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    dry_run: bool = False


class ReflectionFeedback(BaseModel):
    verdict: str = Field(pattern="^(agree|disagree)$")
    note: Optional[str] = Field(default=None, max_length=500)


def _refuse(exc: fb.FeedbackError):
    raise HTTPException(status_code=404 if "exist" in str(exc) else 422, detail=str(exc))


@router.get("/options")
async def reply_reason_options():
    """The reasons a user can give for a reply that missed, per mode."""
    return {
        mode: [{"reason": r, "label": fb.REPLY_REASONS[r]["label"]} for r in reasons]
        for mode, reasons in fb.REASONS_BY_MODE.items()
    }


@router.post("/reply/{message_id}")
async def rate_reply(message_id: UUID, body: ReplyFeedback, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    try:
        return await fb.rate_reply(db, current_user.id, message_id, body.verdict, body.reasons)
    except fb.FeedbackError as exc:
        _refuse(exc)


@router.post("/trait/{trait}")
async def rate_trait(trait: str, body: TraitFeedback, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    try:
        return await fb.rate_trait(db, current_user.id, trait, body.verdict, body.self_score, body.dry_run)
    except fb.FeedbackError as exc:
        _refuse(exc)


@router.post("/reflection/{reflection_id}")
async def rate_reflection(
    reflection_id: UUID, body: ReflectionFeedback, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
):
    try:
        return await fb.rate_reflection(db, current_user.id, reflection_id, body.verdict, body.note)
    except fb.FeedbackError as exc:
        _refuse(exc)


@router.get("/summary")
async def feedback_summary(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    return await fb.summary(db, current_user.id)
