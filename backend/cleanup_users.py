import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from dotenv import load_dotenv

async def cleanup_users():
    load_dotenv()
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("No DATABASE_URL found.")
        return

    try:
        engine = create_async_engine(db_url, echo=False)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        async with async_session() as session:
            # Delete all from users table
            await session.execute(text("TRUNCATE TABLE users CASCADE;"))
            await session.commit()
            print("✅ Successfully cleared all local users. You can now sign up!")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(cleanup_users())