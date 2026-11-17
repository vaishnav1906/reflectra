"""Run Reflectra's background jobs on their own.

The API server runs a worker too (unless REFLECTRA_WORKER=0), which is enough for
one server. With several servers, or on serverless hosting where background tasks
are killed, run this as its own long-lived process instead:

    python -m app.worker
"""

from __future__ import annotations

import asyncio
import logging
import signal

from app.db.database import AsyncSessionLocal
from app.services.job_service import worker_loop


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:  # Windows: Ctrl+C raises KeyboardInterrupt instead
            pass
    from app.services.reminders import reminder_tick

    await worker_loop(AsyncSessionLocal, stop, ticks=[reminder_tick])


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
