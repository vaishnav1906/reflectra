import asyncio
import uuid
import sys
import logging
from sqlalchemy import select

from app.db.database import AsyncSessionLocal
from app.db.models import User
from app.services.persona_report_service import build_persona_report_pdf

async def main():
    async with AsyncSessionLocal() as db:
        user_result = await db.execute(select(User).limit(1))
        user = user_result.scalar_one_or_none()
        if not user:
            print("No users found.")
            return

        pdf = await build_persona_report_pdf(db, user.id)
        with open("test_output_2.pdf", "wb") as f:
            f.write(pdf)
        print("Generated test_output_2.pdf")

if __name__ == "__main__":
    asyncio.run(main())
