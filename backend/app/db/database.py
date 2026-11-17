import os

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")

# Serverless instances (Vercel) each keep their own pool, and the free Supabase pooler
# has few connections, so keep each instance's share small there.
_SERVERLESS = bool(os.getenv("VERCEL"))
engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=2 if _SERVERLESS else 5,
    max_overflow=3 if _SERVERLESS else 10,
    pool_recycle=300 if _SERVERLESS else -1,
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
