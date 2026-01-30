"""Main orchestration engine for VibeCoder."""

import asyncio
from pathlib import Path
from typing import Callable, Optional

from ..config import config
from ..storage.database import Database, get_db
from ..storage.logger import logger
from .permission import PermissionSystem
from .queue import TaskQueue, QueueStats, QueueStatus
from .task import Task, TaskStatus


class Engine:
    """Main orchestration engine for VibeCoder.

    Coordinates task queue, permission system, and provides the main API
    for managing the system.
    """

    def __init__(
        self,
        database: Optional[Database] = None,
        max_concurrent_tasks: int = 1,
    ) -> None:
        """Initialize the engine.

        Args:
            database: Database instance (uses global if not provided)
            max_concurrent_tasks: Maximum concurrent tasks to process
        """
        self.db = database or get_db()
        self.permissions = PermissionSystem()
        self.queue = TaskQueue(
            max_concurrent=max_concurrent_tasks,
            on_task_complete=self._on_task_complete,
            on_task_failed=self._on_task_failed,
        )

        # Event handlers
        self._on_complete_handlers: list[Callable[[Task], None]] = []
        self._on_failed_handlers: list[Callable[[Task, str], None]] = []
        self._on_approval_handlers: list[Callable[[Task], None]] = []

        # State
        self._running = False
        self._run_task: Optional[asyncio.Task] = None

    def on_task_complete(self, handler: Callable[[Task], None]) -> None:
        """Register a handler for task completion."""
        self._on_complete_handlers.append(handler)

    def on_task_failed(self, handler: Callable[[Task, str], None]) -> None:
        """Register a handler for task failure."""
        self._on_failed_handlers.append(handler)

    def on_approval_needed(self, handler: Callable[[Task], None]) -> None:
        """Register a handler for when approval is needed."""
        self._on_approval_handlers.append(handler)

    def _on_task_complete(self, task: Task) -> None:
        """Internal callback for task completion."""
        for handler in self._on_complete_handlers:
            try:
                handler(task)
            except Exception as e:
                logger.error(f"Error in completion handler: {e}")

    def _on_task_failed(self, task: Task, reason: str) -> None:
        """Internal callback for task failure."""
        for handler in self._on_failed_handlers:
            try:
                handler(task, reason)
            except Exception as e:
                logger.error(f"Error in failure handler: {e}")

    # Task management
    def create_task(
        self,
        name: str,
        description: str,
        requirements: list[str],
        verification_commands: list[str],
        working_directory: str,
        max_iterations: int = 10,
        timeout_per_iteration: int = 300,
        auto_queue: bool = True,
    ) -> Task:
        """Create a new task.

        Args:
            name: Task name
            description: Task description
            requirements: List of requirements
            verification_commands: Commands to verify success
            working_directory: Directory to work in
            max_iterations: Maximum iterations
            timeout_per_iteration: Timeout per iteration in seconds
            auto_queue: Automatically add to queue

        Returns:
            The created Task
        """
        # Create task object
        task = Task.create(
            name=name,
            description=description,
            requirements=requirements,
            verification_commands=verification_commands,
            working_directory=working_directory,
            max_iterations=max_iterations,
            timeout_per_iteration=timeout_per_iteration,
        )

        # Save to database
        self.db.create_task(
            task_id=task.id,
            name=task.name,
            description=task.description,
            requirements=task.requirements,
            verification_commands=task.verification_commands,
            working_directory=task.working_directory,
            max_iterations=task.max_iterations,
            timeout_per_iteration=task.timeout_per_iteration,
        )

        logger.info(f"Created task: {task.name}", task_id=task.id)

        # Add to queue if requested
        if auto_queue:
            self.queue.add_task(task.id)

        return task

    def create_task_from_yaml(
        self, yaml_path: str | Path, auto_queue: bool = True
    ) -> Task:
        """Create a task from a YAML file.

        Args:
            yaml_path: Path to the YAML file
            auto_queue: Automatically add to queue

        Returns:
            The created Task
        """
        task = Task.from_yaml(yaml_path)

        # Save to database
        self.db.create_task(
            task_id=task.id,
            name=task.name,
            description=task.description,
            requirements=task.requirements,
            verification_commands=task.verification_commands,
            working_directory=task.working_directory,
            max_iterations=task.max_iterations,
            timeout_per_iteration=task.timeout_per_iteration,
        )

        logger.info(f"Created task from YAML: {task.name}", task_id=task.id)

        if auto_queue:
            self.queue.add_task(task.id)

        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID.

        Args:
            task_id: Task ID

        Returns:
            Task if found, None otherwise
        """
        task_model = self.db.get_task(task_id)
        if not task_model:
            return None

        return Task(
            id=task_model.id,
            name=task_model.name,
            description=task_model.description or "",
            requirements=task_model.get_requirements(),
            verification_commands=task_model.get_verification_commands(),
            working_directory=task_model.working_directory or "",
            max_iterations=task_model.max_iterations or 10,
            timeout_per_iteration=task_model.timeout_per_iteration or 300,
            status=TaskStatus(task_model.status),
            current_iteration=task_model.current_iteration or 0,
            conversation_history=task_model.get_conversation_history(),
            artifacts=task_model.get_artifacts(),
        )

    def list_tasks(
        self, status: Optional[str] = None, limit: int = 100
    ) -> list[Task]:
        """List tasks.

        Args:
            status: Filter by status
            limit: Maximum number of tasks

        Returns:
            List of Tasks
        """
        task_models = self.db.list_tasks(status=status, limit=limit)
        return [
            Task(
                id=t.id,
                name=t.name,
                description=t.description or "",
                requirements=t.get_requirements(),
                verification_commands=t.get_verification_commands(),
                working_directory=t.working_directory or "",
                max_iterations=t.max_iterations or 10,
                timeout_per_iteration=t.timeout_per_iteration or 300,
                status=TaskStatus(t.status),
                current_iteration=t.current_iteration or 0,
                conversation_history=t.get_conversation_history(),
                artifacts=t.get_artifacts(),
            )
            for t in task_models
        ]

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a task.

        Args:
            task_id: Task ID

        Returns:
            True if cancelled, False if not found
        """
        # Remove from queue if present
        self.queue.remove_task(task_id)

        # Update status in database
        task = self.db.update_task(task_id, status=TaskStatus.CANCELLED.value)
        if task:
            logger.info(f"Task cancelled: {task_id}")
            return True
        return False

    def delete_task(self, task_id: str) -> bool:
        """Delete a task and all related data.

        Args:
            task_id: Task ID

        Returns:
            True if deleted, False if not found
        """
        # Remove from queue if present
        self.queue.remove_task(task_id)

        # Delete from database
        if self.db.delete_task(task_id):
            logger.info(f"Task deleted: {task_id}")
            return True
        return False

    # Queue management
    async def start(self) -> None:
        """Start the engine and queue processing."""
        if self._running:
            logger.warning("Engine is already running")
            return

        self._running = True
        logger.info("Engine started")

        # Load pending tasks from database
        self.queue.load_pending_tasks()

        # Start queue processing
        self._run_task = asyncio.create_task(self.queue.start())

    def stop(self) -> None:
        """Stop the engine and queue processing."""
        if not self._running:
            return

        self.queue.stop()
        self._running = False
        logger.info("Engine stopped")

    def pause(self) -> None:
        """Pause queue processing."""
        self.queue.pause()

    def resume(self) -> None:
        """Resume queue processing."""
        self.queue.resume()

    def get_status(self) -> QueueStats:
        """Get engine/queue status."""
        return self.queue.get_status()

    # Permission management
    def get_pending_approvals(self, task_id: Optional[str] = None) -> list:
        """Get pending approval requests.

        Args:
            task_id: Optional task ID to filter by

        Returns:
            List of PermissionRequest objects
        """
        return self.permissions.get_pending_requests(task_id)

    def approve(self, permission_id: int, approved_by: str = "user") -> bool:
        """Approve a permission request.

        Args:
            permission_id: Permission request ID
            approved_by: Who approved it

        Returns:
            True if approved, False if not found
        """
        return self.permissions.approve(permission_id, approved_by)

    def deny(self, permission_id: int, denied_by: str = "user") -> bool:
        """Deny a permission request.

        Args:
            permission_id: Permission request ID
            denied_by: Who denied it

        Returns:
            True if denied, False if not found
        """
        return self.permissions.deny(permission_id, denied_by)

    # Iteration history
    def get_iterations(self, task_id: str) -> list:
        """Get iteration history for a task.

        Args:
            task_id: Task ID

        Returns:
            List of iteration records
        """
        return self.db.get_iterations(task_id)

    # Logs
    def get_logs(
        self,
        task_id: Optional[str] = None,
        level: Optional[str] = None,
        limit: int = 100,
    ) -> list:
        """Get logs.

        Args:
            task_id: Optional task ID to filter by
            level: Optional log level to filter by
            limit: Maximum number of logs

        Returns:
            List of log entries
        """
        return self.db.get_logs(task_id=task_id, level=level, limit=limit)


# Global engine instance
_engine: Optional[Engine] = None


def get_engine() -> Engine:
    """Get the global engine instance."""
    global _engine
    if _engine is None:
        _engine = Engine()
    return _engine
