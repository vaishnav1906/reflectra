from datetime import datetime, timedelta
from typing import List, Optional

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import Message, BehavioralInsight

router = APIRouter()

@router.get("/metrics/{user_id}")
async def get_behavioral_metrics(
    user_id: UUID,
    view: str = Query("week", description="Timeframe view: day, week, month"),
    db: AsyncSession = Depends(get_db),
):
    """
    Fetch aggregated behavioral metrics over time for Activity Rings and Line Charts.
    """
    now = datetime.utcnow()
    
    if view == "day":
        start_date = now - timedelta(days=1)
        trunc_period = "hour"
    elif view == "month":
        start_date = now - timedelta(days=30)
        trunc_period = "day"
    else: # default week
        start_date = now - timedelta(days=7)
        trunc_period = "day"
        
    date_trunc_expr = func.date_trunc(trunc_period, Message.created_at)

    from sqlalchemy import select
    
    stmt = select(
        date_trunc_expr.label("period"),
        func.count(Message.id).label("message_count"),
        func.sum(Message.token_count).label("total_tokens"),
        func.avg(Message.emotional_intensity).label("avg_emotional_intensity"),
        func.avg(Message.reflection_depth).label("avg_reflection_depth"),
        func.avg(Message.response_delay_ms).label("avg_delay_ms"),
    ).where(
        Message.user_id == user_id,
        Message.role == "user",
        Message.created_at >= start_date
    ).group_by(date_trunc_expr).order_by(date_trunc_expr)

    result = await db.execute(stmt)
    rows = result.all()

    data = []
    
    # Totals for the ring activity baselines
    totals = {
        "message_count": 0,
    }
    
    for row in rows:
        data.append({
            "timestamp": row.period.isoformat(),
            "message_count": row.message_count,
            "total_tokens": row.total_tokens or 0,
            "emotional_intensity": float(row.avg_emotional_intensity) if row.avg_emotional_intensity else None,
            "reflection_depth": float(row.avg_reflection_depth) if row.avg_reflection_depth else None,
            "response_delay_ms": int(row.avg_delay_ms) if row.avg_delay_ms else None,
        })
        totals["message_count"] += row.message_count

    return {
        "view": view,
        "start_date": start_date.isoformat(),
        "totals": totals,
        "timeline": data,
    }

@router.get("/reflections/{user_id}")
async def get_user_reflections(
    user_id: UUID,
    range: str = Query("30d", description="Timeframe range: 1d, 2d, 3d, 7d, 30d, 90d"),
    db: AsyncSession = Depends(get_db)
):
    """
    Fetch behavioral insights/reflections for a user within a specific time range.
    """
    now = datetime.utcnow()
    
    if range == "1d":
        start_date = now - timedelta(days=1)
    elif range == "2d":
        start_date = now - timedelta(days=2)
    elif range == "3d":
        start_date = now - timedelta(days=3)
    elif range == "7d":
        start_date = now - timedelta(days=7)
    elif range == "90d":
        start_date = now - timedelta(days=90)
    else: # Default 30d
        start_date = now - timedelta(days=30)
        
    from sqlalchemy import select
    
    stmt = select(BehavioralInsight).where(
        BehavioralInsight.user_id == user_id,
        BehavioralInsight.created_at >= start_date
    ).order_by(BehavioralInsight.created_at.desc())
    
    result = await db.execute(stmt)
    insights = result.scalars().all()
    
    return [
        {
            "id": str(insight.id),
            "text": insight.insight_text,
            "tags": insight.tags,
            "confidence": float(insight.confidence) if insight.confidence else None,
            "created_at": insight.created_at.isoformat()
        }
        for insight in insights
    ]

@router.get("/heatmap/{user_id}")
async def get_activity_heatmap(
    user_id: UUID,
    days: int = Query(30, description="Days to track back"),
    db: AsyncSession = Depends(get_db),
):
    """
    Fetch message frequency by hour of the day and day of week.
    Returns array where index 0 is Sunday, index 6 is Saturday.
    """
    start_date = datetime.utcnow() - timedelta(days=days)
    
    from sqlalchemy import select, extract
    
    # Extract Dow (0-6) and Hour (0-23)
    stmt = select(
        extract('dow', Message.created_at).label('day_of_week'),
        extract('hour', Message.created_at).label('hour_of_day'),
        func.count(Message.id).label('message_count')
    ).where(
        Message.user_id == user_id,
        Message.role == "user",
        Message.created_at >= start_date
    ).group_by(
        extract('dow', Message.created_at),
        extract('hour', Message.created_at)
    )

    result = await db.execute(stmt)
    rows = result.all()

    # Initialize empty 7x24 grid (Sunday=0 to Saturday=6)
    heatmap = [[0 for _ in range(24)] for _ in range(7)]
    
    for row in rows:
        day = int(row.day_of_week)
        hour = int(row.hour_of_day)
        count = row.message_count
        heatmap[day][hour] = count

    return {
        "range_days": days,
        "heatmap": heatmap
    }