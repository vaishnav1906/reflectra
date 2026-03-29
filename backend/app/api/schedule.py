"""API routes for schedule context system."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.db.models import ScheduleContext

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/schedule-context", tags=["schedule_context"])


class ScheduleContextUpdateRequest(BaseModel):
    user_id: str
    classes_per_day: int
    study_hours: int
    has_deadlines: bool
    is_exam_period: bool

class ScheduleContextResponse(BaseModel):
    user_id: str
    schedule_context: dict
    derived_context: dict
    updated_at: str

def calculate_derived_context(classes: int, study: int, deadlines: bool, exams: bool):
    # Calculate Workload Level
    total_hours = classes * 1.5 + study  # rough estimate
    if exams or total_hours >= 8 or classes > 4:
        workload_level = "high"
    elif deadlines or classes > 2 or total_hours >= 4:
        workload_level = "moderate"
    else:
        workload_level = "low"
    
    # Calculate Stress Level (0-1)
    stress = 0.0
    if exams:
        stress += 0.4
    if deadlines:
        stress += 0.3
    stress += min(0.3, total_hours / 30.0) # max 0.3 from hours
    
    stress_level = round(min(1.0, stress), 2)
    return workload_level, stress_level


@router.post("/update", response_model=ScheduleContextResponse)
async def update_schedule_context(
    request: ScheduleContextUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        user_uuid = UUID(request.user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id format")

    logger.info(f"📅 Updating schedule context for user {user_uuid}")

    workload_level, stress_level = calculate_derived_context(
        request.classes_per_day,
        request.study_hours,
        request.has_deadlines,
        request.is_exam_period
    )

    # Check if context exists
    result = await db.execute(select(ScheduleContext).where(ScheduleContext.user_id == user_uuid))
    context_record = result.scalar_one_or_none()

    if context_record:
        context_record.classes_per_day = request.classes_per_day
        context_record.study_hours = request.study_hours
        context_record.has_deadlines = request.has_deadlines
        context_record.is_exam_period = request.is_exam_period
        context_record.workload_level = workload_level
        context_record.stress_level = stress_level
    else:
        context_record = ScheduleContext(
            user_id=user_uuid,
            classes_per_day=request.classes_per_day,
            study_hours=request.study_hours,
            has_deadlines=request.has_deadlines,
            is_exam_period=request.is_exam_period,
            workload_level=workload_level,
            stress_level=stress_level
        )
        db.add(context_record)

    await db.commit()
    await db.refresh(context_record)

    return ScheduleContextResponse(
        user_id=str(user_uuid),
        schedule_context={
            "classes_per_day": context_record.classes_per_day,
            "study_hours": context_record.study_hours,
            "has_deadlines": context_record.has_deadlines,
            "is_exam_period": context_record.is_exam_period
        },
        derived_context={
            "workload_level": context_record.workload_level,
            "stress_level": context_record.stress_level
        },
        updated_at=context_record.updated_at.isoformat()
    )


@router.get("/{user_id}", response_model=ScheduleContextResponse)
async def get_schedule_context(
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id format")

    result = await db.execute(select(ScheduleContext).where(ScheduleContext.user_id == user_uuid))
    context_record = result.scalar_one_or_none()

    if not context_record:
        # Return default if none set yet
        return ScheduleContextResponse(
            user_id=str(user_uuid),
            schedule_context={
                "classes_per_day": 3,
                "study_hours": 4,
                "has_deadlines": False,
                "is_exam_period": False
            },
            derived_context={
                "workload_level": "low",
                "stress_level": 0.0
            },
            updated_at=""
        )

    return ScheduleContextResponse(
        user_id=str(user_uuid),
        schedule_context={
            "classes_per_day": context_record.classes_per_day,
            "study_hours": context_record.study_hours,
            "has_deadlines": context_record.has_deadlines,
            "is_exam_period": context_record.is_exam_period
        },
        derived_context={
            "workload_level": context_record.workload_level,
            "stress_level": context_record.stress_level
        },
        updated_at=context_record.updated_at.isoformat()
    )
