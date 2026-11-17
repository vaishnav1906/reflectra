"""Background jobs: everything Reflectra learns happens after the reply is sent.

A reply only needs its context, the model, and the two messages saved. All the
learning (reading traits, updating the profile, snapshots, writing style, memory
indexing, follow-ups, People) is queued here as a job and run by the worker
(app.worker), which:

  - keeps jobs in Postgres, so a restart or deploy doesn't lose them;
  - retries with backoff when the AI is busy (20s, 1m, 3m, then gives up);
  - runs one job at a time per user, so two quick messages can't overwrite each
    other's trait updates;
  - requeues jobs a crashed worker left half-done.

Handlers are registered by name with @handler("kind").
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable, Dict, List, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Job

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 4
BACKOFF_SECONDS = (20, 60, 180)
STALE_AFTER = timedelta(minutes=10)
CLAIM_BATCH = 6
IDLE_POLL_SECONDS = 15.0
CONCURRENCY = 4

Handler = Callable[[AsyncSession, UUID, dict], Awaitable[None]]
_handlers: Dict[str, Handler] = {}
_wake = asyncio.Event()


def handler(kind: str):
    def register(fn: Handler) -> Handler:
        _handlers[kind] = fn
        return fn

    return register


def backoff(attempts: int) -> int:
    return BACKOFF_SECONDS[min(max(attempts, 1), len(BACKOFF_SECONDS)) - 1]


async def enqueue(
    db: AsyncSession,
    user_id: UUID,
    kind: str,
    payload: Optional[dict] = None,
    *,
    dedupe_key: Optional[str] = None,
    delay_seconds: float = 0,
    commit: bool = True,
) -> bool:
    """Queue a job. With a dedupe_key, nothing is added while an identical job is
    still waiting or running. Returns True if a job was added."""
    run_after = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
    if dedupe_key:
        exists = (
            await db.execute(
                text("SELECT 1 FROM jobs WHERE dedupe_key = :key AND status IN ('queued', 'running') LIMIT 1"),
                {"key": dedupe_key},
            )
        ).first()
        if exists:
            return False
    db.add(Job(user_id=user_id, kind=kind, payload=payload or {}, dedupe_key=dedupe_key, run_after=run_after))
    if commit:
        await db.commit()
    _wake.set()
    return True


CLAIM_SQL = text(
    """
    UPDATE jobs SET status = 'running', attempts = attempts + 1, started_at = now(), updated_at = now()
    WHERE id IN (
        SELECT id FROM jobs
        WHERE status = 'queued' AND run_after <= now()
        ORDER BY run_after
        LIMIT :limit
        FOR UPDATE SKIP LOCKED
    )
    RETURNING id, user_id, kind, payload, attempts
    """
)
REQUEUE_STALE_SQL = text(
    "UPDATE jobs SET status = 'queued', updated_at = now() WHERE status = 'running' AND started_at < :before"
)


async def claim(db: AsyncSession, limit: int = CLAIM_BATCH) -> List[dict]:
    await db.execute(REQUEUE_STALE_SQL, {"before": datetime.now(timezone.utc) - STALE_AFTER})
    rows = (await db.execute(CLAIM_SQL, {"limit": limit})).mappings().all()
    await db.commit()
    return [dict(r) for r in rows]


async def finish(db: AsyncSession, job_id: UUID, error: Optional[str] = None, attempts: int = 1, retry: bool = True) -> None:
    if error is None:
        await db.execute(text("UPDATE jobs SET status = 'done', last_error = NULL, updated_at = now() WHERE id = :id"), {"id": job_id})
    elif retry and attempts < MAX_ATTEMPTS:
        await db.execute(
            text(
                "UPDATE jobs SET status = 'queued', last_error = :error, run_after = now() + make_interval(secs => :wait), "
                "updated_at = now() WHERE id = :id"
            ),
            {"id": job_id, "error": error[:500], "wait": backoff(attempts)},
        )
    else:
        await db.execute(
            text("UPDATE jobs SET status = 'failed', last_error = :error, updated_at = now() WHERE id = :id"),
            {"id": job_id, "error": error[:500]},
        )
    await db.commit()


async def prune(db: AsyncSession, keep_days: int = 7) -> None:
    """Finished jobs are only kept for a week, for debugging."""
    await db.execute(
        text("DELETE FROM jobs WHERE status IN ('done', 'failed') AND updated_at < :before"),
        {"before": datetime.now(timezone.utc) - timedelta(days=keep_days)},
    )
    await db.commit()


# --------------------------------------------------------------------------- worker loop

_user_locks: Dict[UUID, asyncio.Lock] = {}


def _lock_for(user_id: UUID) -> asyncio.Lock:
    lock = _user_locks.get(user_id)
    if lock is None:
        lock = _user_locks[user_id] = asyncio.Lock()
    return lock


async def run_one(job: dict, session_factory) -> None:
    from app.services.llm import LLMRateLimited

    fn = _handlers.get(job["kind"])
    async with session_factory() as db:
        if fn is None:
            await finish(db, job["id"], f"no handler for {job['kind']}", job["attempts"], retry=False)
            return
        async with _lock_for(job["user_id"]):
            try:
                await fn(db, job["user_id"], dict(job["payload"] or {}))
            except LLMRateLimited as exc:
                await db.rollback()
                await finish(db, job["id"], f"AI busy: {exc}", job["attempts"])
                return
            except Exception as exc:  # a bug or outage: retried a few times, then parked as failed
                await db.rollback()
                logger.exception("Job %s (%s) failed", job["id"], job["kind"])
                await finish(db, job["id"], f"{type(exc).__name__}: {exc}", job["attempts"])
                return
        await finish(db, job["id"], None, job["attempts"])


async def worker_loop(session_factory, stop: asyncio.Event, ticks: Optional[List[Callable[[], Awaitable[None]]]] = None) -> None:
    """Run jobs until `stop` is set. `ticks` are periodic callbacks (e.g. reminders)."""
    import_handlers()
    semaphore = asyncio.Semaphore(CONCURRENCY)
    running: set = set()
    last_tick = 0.0
    last_prune = 0.0
    loop = asyncio.get_running_loop()
    logger.info("Job worker started")
    while not stop.is_set():
        try:
            if ticks and loop.time() - last_tick >= 60:
                last_tick = loop.time()
                for tick in ticks:
                    try:
                        await tick()
                    except Exception:
                        logger.exception("Periodic task failed")
            if loop.time() - last_prune >= 3600:
                last_prune = loop.time()
                async with session_factory() as db:
                    await prune(db)
            free = CONCURRENCY - len(running)
            jobs: List[dict] = []
            if free > 0:
                async with session_factory() as db:
                    jobs = await claim(db, min(free, CLAIM_BATCH))
            for job in jobs:
                async def guarded(j=job):
                    async with semaphore:
                        await run_one(j, session_factory)

                task = asyncio.create_task(guarded())
                running.add(task)
                task.add_done_callback(running.discard)
            if not jobs:
                _wake.clear()
                try:
                    await asyncio.wait_for(_wake.wait(), IDLE_POLL_SECONDS)
                except asyncio.TimeoutError:
                    pass
            else:
                await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Job worker hiccup; retrying shortly")
            await asyncio.sleep(5)
    for task in list(running):
        task.cancel()
    logger.info("Job worker stopped")


def worker_enabled() -> bool:
    return os.getenv("REFLECTRA_WORKER", "1").strip().lower() not in ("0", "false", "off", "no")


def import_handlers() -> None:
    """Make sure every module that registers handlers is loaded."""
    from app.services import learning_jobs  # noqa: F401
