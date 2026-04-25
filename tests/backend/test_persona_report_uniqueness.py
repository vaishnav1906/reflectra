#!/usr/bin/env python3

import asyncio
import os
import sys
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from sqlalchemy import delete

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

load_dotenv(BACKEND_DIR / ".env")

from app.db.database import AsyncSessionLocal
from app.db.models import PersonalityProfile, User
from app.db.crud import create_user, upsert_personality_profile
from app.repository.persona_repository import PersonaRepository
from app.services.persona_report_service import _build_payload, build_persona_report_pdf

DATABASE_URL = os.getenv("DATABASE_URL")


async def _seed_user(db, email: str, display_name: str, profile_data: dict) -> User:
    user = await create_user(db, email=email, display_name=display_name)
    await upsert_personality_profile(db, user.id, profile_data)
    for trait_name in (
        "communication_style",
        "emotional_expressiveness",
        "decision_framing",
        "reflection_depth",
    ):
        await PersonaRepository.create_metric(db, user.id, trait_name, score=0.55, confidence=0.35)
    await db.commit()
    return user


async def main() -> bool:
    if not DATABASE_URL:
        print("DATABASE_URL is not set.")
        return False

    async with AsyncSessionLocal() as db:
        seeded_users: list[User] = []
        try:
            user_a = await _seed_user(
                db,
                email=f"persona-report-a-{uuid4()}@example.com",
                display_name="Profile Alpha",
                profile_data={
                    "openness": 0.82,
                    "conscientiousness": 0.91,
                    "extraversion": 0.28,
                    "agreeableness": 0.35,
                    "neuroticism": 0.18,
                    "themes": {"clarity": 4, "planning": 2},
                    "traits": {"analytical": 5, "decisive": 3},
                    "values": {"precision": 4, "efficiency": 2},
                    "stressors": {"overload": 1},
                },
            )
            seeded_users.append(user_a)

            user_b = await _seed_user(
                db,
                email=f"persona-report-b-{uuid4()}@example.com",
                display_name="Profile Beta",
                profile_data={
                    "openness": 0.31,
                    "conscientiousness": 0.46,
                    "extraversion": 0.84,
                    "agreeableness": 0.71,
                    "neuroticism": 0.62,
                    "themes": {"creativity": 5, "expression": 3},
                    "traits": {"empathetic": 4, "collaborative": 3},
                    "values": {"connection": 4, "exploration": 3},
                    "stressors": {"overcontrol": 2},
                },
            )
            seeded_users.append(user_b)

            payload_a = await _build_payload(db, user_a.id)
            payload_b = await _build_payload(db, user_b.id)

            assert payload_a.display_name == "Profile Alpha"
            assert payload_b.display_name == "Profile Beta"
            assert payload_a.personality_dimensions != payload_b.personality_dimensions
            assert payload_a.communication_traits != payload_b.communication_traits
            assert payload_a.profile_highlights != payload_b.profile_highlights
            assert payload_a.interests_distribution != payload_b.interests_distribution
            assert payload_a.overall_score != payload_b.overall_score or payload_a.archetype_name != payload_b.archetype_name

            pdf_a = await build_persona_report_pdf(db, user_a.id)
            pdf_b = await build_persona_report_pdf(db, user_b.id)
            assert pdf_a != pdf_b

            print("Persona report uniqueness check passed.")
            print(f"Alpha score: {payload_a.overall_score} | archetype: {payload_a.archetype_name}")
            print(f"Beta score: {payload_b.overall_score} | archetype: {payload_b.archetype_name}")
            return True
        finally:
            for user in seeded_users:
                await db.execute(delete(PersonalityProfile).where(PersonalityProfile.user_id == user.id))
                await db.execute(delete(User).where(User.id == user.id))
            await db.commit()


def test_persona_report_uniqueness() -> None:
    assert asyncio.run(main())


if __name__ == "__main__":
    raise SystemExit(0 if asyncio.run(main()) else 1)
