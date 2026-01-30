"""Task API routes."""

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...core.engine import get_engine
from ...core.task import TaskStatus


router = APIRouter()


class TaskCreate(BaseModel):
    """Request body for creating a task."""

    name: str
    description: str = ""
    requirements: list[str] = []
    verification_commands: list[str] = []
    working_directory: str = "."
    max_iterations: int = 10
    timeout_per_iteration: int = 300
    auto_queue: bool = True


class TaskResponse(BaseModel):
    """Task response model."""

    id: str
    name: str
    description: str
    requirements: list[str]
    verification_commands: list[str]
    working_directory: str
    max_iterations: int
    timeout_per_iteration: int
    status: str
    current_iteration: int
    artifacts: list[str]


@router.post("/", response_model=TaskResponse)
async def create_task(task_data: TaskCreate):
    """Create a new task."""
    engine = get_engine()

    # Resolve working directory
    working_dir = task_data.working_directory
    if working_dir == ".":
        working_dir = str(Path.cwd())

    task = engine.create_task(
        name=task_data.name,
        description=task_data.description,
        requirements=task_data.requirements,
        verification_commands=task_data.verification_commands,
        working_directory=working_dir,
        max_iterations=task_data.max_iterations,
        timeout_per_iteration=task_data.timeout_per_iteration,
        auto_queue=task_data.auto_queue,
    )

    return TaskResponse(
        id=task.id,
        name=task.name,
        description=task.description,
        requirements=task.requirements,
        verification_commands=task.verification_commands,
        working_directory=task.working_directory,
        max_iterations=task.max_iterations,
        timeout_per_iteration=task.timeout_per_iteration,
        status=task.status.value,
        current_iteration=task.current_iteration,
        artifacts=task.artifacts,
    )


@router.get("/", response_model=list[TaskResponse])
async def list_tasks(status: Optional[str] = None, limit: int = 100):
    """List all tasks."""
    engine = get_engine()
    tasks = engine.list_tasks(status=status, limit=limit)

    return [
        TaskResponse(
            id=t.id,
            name=t.name,
            description=t.description,
            requirements=t.requirements,
            verification_commands=t.verification_commands,
            working_directory=t.working_directory,
            max_iterations=t.max_iterations,
            timeout_per_iteration=t.timeout_per_iteration,
            status=t.status.value,
            current_iteration=t.current_iteration,
            artifacts=t.artifacts,
        )
        for t in tasks
    ]


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    """Get a specific task."""
    engine = get_engine()
    task = engine.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return TaskResponse(
        id=task.id,
        name=task.name,
        description=task.description,
        requirements=task.requirements,
        verification_commands=task.verification_commands,
        working_directory=task.working_directory,
        max_iterations=task.max_iterations,
        timeout_per_iteration=task.timeout_per_iteration,
        status=task.status.value,
        current_iteration=task.current_iteration,
        artifacts=task.artifacts,
    )


@router.post("/{task_id}/cancel")
async def cancel_task(task_id: str):
    """Cancel a task."""
    engine = get_engine()

    if engine.cancel_task(task_id):
        return {"status": "cancelled"}

    raise HTTPException(status_code=404, detail="Task not found")


@router.delete("/{task_id}")
async def delete_task(task_id: str):
    """Delete a task."""
    engine = get_engine()

    if engine.delete_task(task_id):
        return {"status": "deleted"}

    raise HTTPException(status_code=404, detail="Task not found")


@router.get("/{task_id}/iterations")
async def get_iterations(task_id: str):
    """Get iteration history for a task."""
    engine = get_engine()

    task = engine.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    iterations = engine.get_iterations(task_id)

    return [
        {
            "id": it.id,
            "iteration_number": it.iteration_number,
            "files_modified": it.get_files_modified(),
            "verification_passed": it.verification_passed,
            "verification_output": it.verification_output,
            "feedback_generated": it.feedback_generated,
            "created_at": it.created_at.isoformat() if it.created_at else None,
        }
        for it in iterations
    ]


@router.post("/{task_id}/queue")
async def queue_task(task_id: str):
    """Add a task to the queue."""
    engine = get_engine()

    task = engine.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    engine.queue.add_task(task_id)
    return {"status": "queued"}
