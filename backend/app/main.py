from dotenv import load_dotenv
from pathlib import Path
import asyncio
import os
from contextlib import asynccontextmanager

# Load environment variables before importing modules that read them.
load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")

from fastapi import Depends, FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from app.api.analytics import router as analytics_router  # noqa: E402
from app.api.auth import router as auth_router  # noqa: E402
from app.api.chat import router as chat_router  # noqa: E402
from app.api.dbms import router as db_router  # noqa: E402
from app.api.feedback import router as feedback_router  # noqa: E402
from app.api.life import router as life_router  # noqa: E402
from app.api.deps import require_user_scope  # noqa: E402
from app.api.mirror import router as mirror_router  # noqa: E402
from app.api.notifications import router as notifications_router  # noqa: E402
from app.api.people import router as people_router  # noqa: E402
from app.api.persona import router as persona_router  # noqa: E402
from app.api.schedule import router as schedule_router  # noqa: E402
from app.api.transcribe import router as transcribe_router  # noqa: E402
from app.api.user import router as user_router  # noqa: E402

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Run the background job worker alongside the API (turn off with REFLECTRA_WORKER=0
    when it runs as its own process: python -m app.worker)."""
    from app.db.database import AsyncSessionLocal
    from app.services.job_service import worker_enabled, worker_loop
    from app.services.reminders import reminder_tick

    stop = asyncio.Event()
    task = asyncio.create_task(worker_loop(AsyncSessionLocal, stop, ticks=[reminder_tick])) if worker_enabled() else None
    try:
        yield
    finally:
        stop.set()
        if task is not None:
            task.cancel()


app = FastAPI(title="Reflectra Backend", version="1.0.0", lifespan=lifespan)

# CORS: explicit origins only. Auth uses Bearer tokens (no cookies), so
# credentials are not needed. Set ALLOWED_ORIGINS to a comma-separated list
# for deployed frontends.
DEFAULT_ALLOWED_ORIGINS = "http://localhost:8080,http://localhost:5173"
allowed_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", DEFAULT_ALLOWED_ORIGINS).split(",")
    if origin.strip() and origin.strip() != "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)

# Every data route requires a valid Supabase access token, and any user_id in
# the path or query must be the caller's own (see app.api.deps).
protected = [Depends(require_user_scope)]

app.include_router(auth_router)  # /auth/me authenticates itself
app.include_router(chat_router, dependencies=protected)
app.include_router(db_router, dependencies=protected)
app.include_router(persona_router, dependencies=protected)
app.include_router(mirror_router, dependencies=protected)
app.include_router(schedule_router, dependencies=protected)
app.include_router(user_router, dependencies=protected)
app.include_router(analytics_router, prefix="/analytics", tags=["analytics"], dependencies=protected)
app.include_router(transcribe_router, dependencies=protected)
app.include_router(feedback_router, dependencies=protected)
app.include_router(people_router, dependencies=protected)
app.include_router(life_router, dependencies=protected)
app.include_router(notifications_router, dependencies=protected)


@app.get("/")
def health():
    """Root endpoint with API information"""
    mistral_configured = bool(os.getenv("MISTRAL_API_KEY"))

    return {
        "status": "✅ Reflectra backend running",
        "version": "1.0.0",
        "llm_available": mistral_configured,
        "llm_provider": "Mistral AI" if mistral_configured else None,
        "endpoints": {
            "health": "/",
            "health_check": "/health",
            "docs": "/docs",
            "chat": "/chat",
            "transcribe": "/transcribe",
            "persona": "/persona",
            "mirror": "/mirror"
        }
    }


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "reflectra-backend",
        "llm_configured": bool(os.getenv("MISTRAL_API_KEY"))
    }
