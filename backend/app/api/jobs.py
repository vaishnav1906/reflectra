"""Running background jobs where there is no background (serverless hosting).

  POST /jobs/run-mine    the signed-in user's queued jobs, called by the app right
                         after a reply so what it learned lands within seconds
  POST /internal/tick    everyone's due jobs plus reminders; called every few
                         minutes by a scheduled workflow with the CRON_SECRET

With a long-running server the in-process worker does all of this already, and these
endpoints simply find nothing left to do.
"""

import hmac
import logging
import os

from fastapi import APIRouter, Header, HTTPException

from app.api.deps import CurrentUser
from app.db.database import AsyncSessionLocal
from app.services import job_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])
internal_router = APIRouter(prefix="/internal", tags=["internal"])

USER_BUDGET_SECONDS = 20.0
TICK_BUDGET_SECONDS = 45.0


@router.post("/run-mine")
async def run_mine(current_user: CurrentUser):
    ran = await job_service.drain(AsyncSessionLocal, user_id=current_user.id, budget_seconds=USER_BUDGET_SECONDS)
    return {"ran": ran}


def _authorized(authorization: str | None) -> bool:
    secret = os.getenv("CRON_SECRET", "").strip()
    if not secret or not authorization or not authorization.startswith("Bearer "):
        return False
    return hmac.compare_digest(authorization[len("Bearer "):].strip(), secret)


@internal_router.post("/tick")
async def tick(authorization: str | None = Header(default=None)):
    if not _authorized(authorization):
        # Indistinguishable from a route that doesn't exist.
        raise HTTPException(status_code=404, detail="Not Found")

    from app.services.reminders import reminder_tick

    reminders_ok = True
    try:
        await reminder_tick()
    except Exception:
        reminders_ok = False
        logger.exception("Reminder tick failed")
    async with AsyncSessionLocal() as db:
        await job_service.prune(db)
    ran = await job_service.drain(AsyncSessionLocal, budget_seconds=TICK_BUDGET_SECONDS)
    return {"ran": ran, "reminders": reminders_ok}
