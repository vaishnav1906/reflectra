#!/usr/bin/env python3

import asyncio
import sys
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
OUTPUT_FILE = ROOT / "data" / "test_output_2.pdf"

sys.path.insert(0, str(BACKEND_DIR))

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
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_FILE, "wb") as f:
            f.write(pdf)
        print(f"Generated {OUTPUT_FILE}")


if __name__ == "__main__":
    asyncio.run(main())
