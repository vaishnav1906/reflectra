import os
from uuid import uuid4

from dotenv import load_dotenv
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")

SUPABASE_POOLER_SUFFIX = ".pooler.supabase.com"
SESSION_PORT, TRANSACTION_PORT = 5432, 6543


def serverless_database_url(url: str) -> str:
    """The connection string to use on serverless hosting.

    Supabase's pooler has two modes on the same host. Session mode (port 5432) gives each
    client its own server connection and allows only a handful at once (15 on the free
    plan); every serverless instance holds its own, so they run out and requests fail with
    "max clients reached". Transaction mode (port 6543) lends a connection per transaction,
    which is what many short-lived instances need. Other databases are left as they are.
    """
    parsed = make_url(url)
    if parsed.host and parsed.host.endswith(SUPABASE_POOLER_SUFFIX) and parsed.port in (None, SESSION_PORT):
        parsed = parsed.set(port=TRANSACTION_PORT)
    # A transaction pooler can't keep prepared statements between transactions.
    parsed = parsed.update_query_dict({"prepared_statement_cache_size": "0"})
    return parsed.render_as_string(hide_password=False)


_SERVERLESS = bool(os.getenv("VERCEL"))

if _SERVERLESS:
    # No pool of our own: each request borrows a pooler connection and gives it straight
    # back, so idle instances hold nothing. Statement names are unique per connection so
    # two clients sharing a server connection never collide.
    engine = create_async_engine(
        serverless_database_url(DATABASE_URL),
        poolclass=NullPool,
        connect_args={
            "statement_cache_size": 0,
            "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4()}__",
        },
    )
else:
    engine = create_async_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )

AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)

Base = declarative_base()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
