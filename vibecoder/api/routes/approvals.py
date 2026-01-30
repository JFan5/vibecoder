"""Approval API routes."""

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...core.engine import get_engine


router = APIRouter()


class ApprovalResponse(BaseModel):
    """Approval response model."""

    id: int
    task_id: str
    action_type: str
    description: str
    details: dict
    status: str
    created_at: str


@router.get("/", response_model=list[ApprovalResponse])
async def list_approvals(task_id: Optional[str] = None):
    """List pending approvals."""
    engine = get_engine()
    approvals = engine.get_pending_approvals(task_id)

    return [
        ApprovalResponse(
            id=a.id,
            task_id=a.task_id,
            action_type=a.action_type.value,
            description=a.description,
            details=a.details,
            status=a.status.value,
            created_at=a.created_at.isoformat(),
        )
        for a in approvals
    ]


@router.post("/{approval_id}/approve")
async def approve(approval_id: int, approved_by: str = "api"):
    """Approve an action."""
    engine = get_engine()

    if engine.approve(approval_id, approved_by):
        return {"status": "approved"}

    raise HTTPException(status_code=404, detail="Approval not found")


@router.post("/{approval_id}/deny")
async def deny(approval_id: int, denied_by: str = "api"):
    """Deny an action."""
    engine = get_engine()

    if engine.deny(approval_id, denied_by):
        return {"status": "denied"}

    raise HTTPException(status_code=404, detail="Approval not found")
