"""Logs API routes."""

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from ...core.engine import get_engine


router = APIRouter()


class LogResponse(BaseModel):
    """Log entry response model."""

    id: int
    task_id: Optional[str]
    level: str
    message: str
    details: dict
    created_at: str


@router.get("/", response_model=list[LogResponse])
async def get_logs(
    task_id: Optional[str] = None,
    level: Optional[str] = None,
    limit: int = 100,
):
    """Get logs."""
    engine = get_engine()
    logs = engine.get_logs(task_id=task_id, level=level, limit=limit)

    return [
        LogResponse(
            id=log.id,
            task_id=log.task_id,
            level=log.level,
            message=log.message,
            details=log.get_details(),
            created_at=log.created_at.isoformat() if log.created_at else "",
        )
        for log in logs
    ]
