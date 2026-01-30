"""Task queue management for VibeCoder."""

import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Optional

from ..storage.database import get_db
from ..storage.logger import logger
from .task import Task, TaskStatus


class QueueStatus(str, Enum):
    """Queue status."""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"


@dataclass
class QueueStats:
    """Statistics about the queue."""

    status: QueueStatus
    pending_count: int
    running_count: int
    completed_count: int
    failed_count: int
    total_processed: int = 0
    start_time: Optional[datetime] = None


class TaskQueue:
    """Manages the queue of tasks to process."""

    def __init__(
        self,
        max_concurrent: int = 1,
        on_task_complete: Optional[Callable[[Task], None]] = None,
        on_task_failed: Optional[Callable[[Task, str], None]] = None,
    ) -> None:
        """Initialize the task queue.

        Args:
            max_concurrent: Maximum concurrent tasks
            on_task_complete: Callback when a task completes
            on_task_failed: Callback when a task fails
        """
        self.max_concurrent = max_concurrent
        self.on_task_complete = on_task_complete
        self.on_task_failed = on_task_failed

        self.db = get_db()
        self._queue: deque[str] = deque()  # Queue of task IDs
        self._running: set[str] = set()  # Currently running task IDs
        self._status = QueueStatus.IDLE
        self._stats = QueueStats(
            status=QueueStatus.IDLE,
            pending_count=0,
            running_count=0,
            completed_count=0,
            failed_count=0,
        )
        self._stop_event = asyncio.Event()
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # Not paused initially

    def add_task(self, task_id: str) -> None:
        """Add a task to the queue.

        Args:
            task_id: ID of the task to add
        """
        if task_id not in self._queue and task_id not in self._running:
            self._queue.append(task_id)
            self._stats.pending_count += 1
            logger.info(f"Task added to queue: {task_id}")

    def remove_task(self, task_id: str) -> bool:
        """Remove a task from the queue.

        Args:
            task_id: ID of the task to remove

        Returns:
            True if task was removed, False if not found
        """
        try:
            self._queue.remove(task_id)
            self._stats.pending_count -= 1
            logger.info(f"Task removed from queue: {task_id}")
            return True
        except ValueError:
            return False

    def get_status(self) -> QueueStats:
        """Get current queue status and statistics."""
        self._stats.status = self._status
        self._stats.pending_count = len(self._queue)
        self._stats.running_count = len(self._running)
        return self._stats

    async def start(self) -> None:
        """Start processing the queue."""
        if self._status == QueueStatus.RUNNING:
            logger.warning("Queue is already running")
            return

        self._status = QueueStatus.RUNNING
        self._stats.start_time = datetime.utcnow()
        self._stop_event.clear()
        logger.info("Queue processing started")

        try:
            await self._process_loop()
        except Exception as e:
            logger.error(f"Queue processing error: {e}", exc_info=True)
        finally:
            self._status = QueueStatus.STOPPED
            logger.info("Queue processing stopped")

    def stop(self) -> None:
        """Stop processing the queue."""
        logger.info("Stopping queue processing")
        self._stop_event.set()
        self._status = QueueStatus.STOPPED

    def pause(self) -> None:
        """Pause queue processing."""
        logger.info("Pausing queue processing")
        self._pause_event.clear()
        self._status = QueueStatus.PAUSED

    def resume(self) -> None:
        """Resume queue processing."""
        logger.info("Resuming queue processing")
        self._pause_event.set()
        if self._status == QueueStatus.PAUSED:
            self._status = QueueStatus.RUNNING

    async def _process_loop(self) -> None:
        """Main processing loop."""
        while not self._stop_event.is_set():
            # Wait if paused
            await self._pause_event.wait()

            # Check for available slots and pending tasks
            if (
                len(self._running) < self.max_concurrent
                and self._queue
            ):
                task_id = self._queue.popleft()
                self._stats.pending_count -= 1

                # Start task in background
                asyncio.create_task(self._process_task(task_id))

            # Small delay to prevent busy waiting
            await asyncio.sleep(0.1)

    async def _process_task(self, task_id: str) -> None:
        """Process a single task.

        Args:
            task_id: ID of the task to process
        """
        self._running.add(task_id)
        self._stats.running_count += 1

        try:
            # Load task from database
            task_model = self.db.get_task(task_id)
            if not task_model:
                logger.error(f"Task not found: {task_id}")
                return

            # Convert to Task object
            task = Task(
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

            # Update status to running
            task.status = TaskStatus.RUNNING
            self.db.update_task(task_id, status=TaskStatus.RUNNING.value)
            logger.task_started(task_id, task.name)

            # Run the iteration loop
            from .iteration import IterationManager

            manager = IterationManager(task)
            success = await manager.run_loop()

            # Update database with final state
            self.db.update_task(
                task_id,
                status=task.status.value,
                current_iteration=task.current_iteration,
                conversation_history=task.conversation_history,
                artifacts=task.artifacts,
            )

            # Update stats and call callbacks
            self._stats.total_processed += 1
            if success:
                self._stats.completed_count += 1
                if self.on_task_complete:
                    self.on_task_complete(task)
            else:
                self._stats.failed_count += 1
                if self.on_task_failed:
                    reason = "Max iterations reached" if task.status == TaskStatus.FAILED else "Needs approval"
                    self.on_task_failed(task, reason)

        except Exception as e:
            logger.error(f"Error processing task {task_id}: {e}", exc_info=True)
            self.db.update_task(task_id, status=TaskStatus.FAILED.value)
            self._stats.failed_count += 1

        finally:
            self._running.discard(task_id)
            self._stats.running_count -= 1

    def load_pending_tasks(self) -> int:
        """Load pending tasks from database into the queue.

        Returns:
            Number of tasks loaded
        """
        tasks = self.db.list_tasks(status=TaskStatus.PENDING.value)
        count = 0
        for task in tasks:
            if task.id not in self._queue and task.id not in self._running:
                self._queue.append(task.id)
                count += 1

        self._stats.pending_count = len(self._queue)
        logger.info(f"Loaded {count} pending tasks from database")
        return count

    def get_queue_order(self) -> list[str]:
        """Get the current queue order.

        Returns:
            List of task IDs in queue order
        """
        return list(self._queue)

    def reorder_task(self, task_id: str, position: int) -> bool:
        """Move a task to a different position in the queue.

        Args:
            task_id: ID of the task to move
            position: New position (0-indexed)

        Returns:
            True if task was moved, False if not found
        """
        try:
            self._queue.remove(task_id)
            # Insert at position (clamped to valid range)
            position = max(0, min(position, len(self._queue)))
            self._queue.insert(position, task_id)
            logger.info(f"Task {task_id} moved to position {position}")
            return True
        except ValueError:
            return False
