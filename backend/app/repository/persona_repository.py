"""Repository layer for persona-related database operations."""

import logging
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from app.db.models import UserPersonaMetric, PersonaSnapshot
from app.constants import DEFAULT_TRAIT_SCORE, DEFAULT_TRAIT_CONFIDENCE, TRAIT_LIST

logger = logging.getLogger(__name__)


class PersonaRepository:
    """Repository for persona metrics and snapshots."""

    @staticmethod
    async def get_metric(
        db: AsyncSession, user_id: UUID, trait_name: str
    ) -> Optional[UserPersonaMetric]:
        """Get a specific trait metric for a user."""
        stmt = select(UserPersonaMetric).where(
            UserPersonaMetric.user_id == user_id,
            UserPersonaMetric.trait_name == trait_name,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_all_metrics(
        db: AsyncSession, user_id: UUID
    ) -> List[UserPersonaMetric]:
        """Get all trait metrics for a user."""
        stmt = select(UserPersonaMetric).where(UserPersonaMetric.user_id == user_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def create_metric(
        db: AsyncSession,
        user_id: UUID,
        trait_name: str,
        score: float = DEFAULT_TRAIT_SCORE,
        confidence: float = DEFAULT_TRAIT_CONFIDENCE,
    ) -> UserPersonaMetric:
        """Create a new trait metric."""
        metric = UserPersonaMetric(
            user_id=user_id,
            trait_name=trait_name,
            score=score,
            confidence=confidence,
            evidence_count=0,
            last_signal=None,
        )
        db.add(metric)
        await db.flush()
        return metric

    @staticmethod
    async def update_metric(
        db: AsyncSession,
        metric: UserPersonaMetric,
        score: float,
        confidence: float,
        last_signal: float,
    ) -> UserPersonaMetric:
        """Update an existing trait metric."""
        metric.score = score
        metric.confidence = confidence
        metric.last_signal = last_signal
        metric.evidence_count += 1
        metric.last_updated = datetime.utcnow()
        await db.flush()
        return metric

    @staticmethod
    async def initialize_missing_traits(
        db: AsyncSession, user_id: UUID
    ) -> List[UserPersonaMetric]:
        """Initialize any missing traits for a user."""
        existing_metrics = await PersonaRepository.get_all_metrics(db, user_id)
        existing_trait_names = {m.trait_name for m in existing_metrics}
        
        missing_traits = [t for t in TRAIT_LIST if t not in existing_trait_names]
        
        if not missing_traits:
            return existing_metrics
        
        # Bulk insert missing traits
        new_metrics = []
        for trait_name in missing_traits:
            metric = await PersonaRepository.create_metric(
                db, user_id, trait_name
            )
            new_metrics.append(metric)
            logger.info(f"Initialized missing trait '{trait_name}' for user {user_id}")
        
        await db.commit()
        return existing_metrics + new_metrics

    @staticmethod
    async def get_total_evidence_count(db: AsyncSession, user_id: UUID) -> int:
        """Get total evidence count across all traits for a user."""
        stmt = select(func.sum(UserPersonaMetric.evidence_count)).where(
            UserPersonaMetric.user_id == user_id
        )
        result = await db.execute(stmt)
        total = result.scalar_one_or_none()
        return total or 0

    @staticmethod
    async def remove_low_confidence_traits(
        db: AsyncSession, user_id: UUID, min_evidence: int, min_confidence: float
    ) -> int:
        """Remove traits with low confidence and insufficient evidence."""
        stmt = delete(UserPersonaMetric).where(
            UserPersonaMetric.user_id == user_id,
            UserPersonaMetric.confidence < min_confidence,
            UserPersonaMetric.evidence_count < min_evidence,
        )
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount

    @staticmethod
    async def create_snapshot(
        db: AsyncSession,
        user_id: UUID,
        persona_vector: Dict,
        stability_index: float,
        summary_text: str,
    ) -> PersonaSnapshot:
        """Create a persona snapshot."""
        snapshot = PersonaSnapshot(
            user_id=user_id,
            persona_vector=persona_vector,
            stability_index=stability_index,
            summary_text=summary_text,
        )
        db.add(snapshot)
        await db.commit()
        await db.refresh(snapshot)
        return snapshot

    @staticmethod
    async def get_latest_snapshot(
        db: AsyncSession, user_id: UUID
    ) -> Optional[PersonaSnapshot]:
        """Get the latest persona snapshot for a user."""
        stmt = (
            select(PersonaSnapshot)
            .where(PersonaSnapshot.user_id == user_id)
            .order_by(PersonaSnapshot.created_at.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_snapshots(
        db: AsyncSession, user_id: UUID, limit: int = 10
    ) -> List[PersonaSnapshot]:
        """Get recent persona snapshots for a user."""
        stmt = (
            select(PersonaSnapshot)
            .where(PersonaSnapshot.user_id == user_id)
            .order_by(PersonaSnapshot.created_at.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())
