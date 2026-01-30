"""Tests for the TaskQueue."""

import pytest

from vibecoder.core.queue import TaskQueue, QueueStatus


class TestTaskQueue:
    """Test cases for the TaskQueue."""

    def test_add_task(self):
        """Test adding a task to the queue."""
        queue = TaskQueue()

        queue.add_task("task-1")
        queue.add_task("task-2")

        stats = queue.get_status()
        assert stats.pending_count == 2

    def test_add_duplicate_task(self):
        """Test that duplicate tasks are not added."""
        queue = TaskQueue()

        queue.add_task("task-1")
        queue.add_task("task-1")

        stats = queue.get_status()
        assert stats.pending_count == 1

    def test_remove_task(self):
        """Test removing a task from the queue."""
        queue = TaskQueue()

        queue.add_task("task-1")
        queue.add_task("task-2")

        result = queue.remove_task("task-1")

        assert result is True
        stats = queue.get_status()
        assert stats.pending_count == 1

    def test_remove_nonexistent_task(self):
        """Test removing a task that doesn't exist."""
        queue = TaskQueue()

        result = queue.remove_task("nonexistent")

        assert result is False

    def test_get_queue_order(self):
        """Test getting the queue order."""
        queue = TaskQueue()

        queue.add_task("task-1")
        queue.add_task("task-2")
        queue.add_task("task-3")

        order = queue.get_queue_order()

        assert order == ["task-1", "task-2", "task-3"]

    def test_reorder_task(self):
        """Test reordering a task."""
        queue = TaskQueue()

        queue.add_task("task-1")
        queue.add_task("task-2")
        queue.add_task("task-3")

        queue.reorder_task("task-3", 0)

        order = queue.get_queue_order()
        assert order == ["task-3", "task-1", "task-2"]

    def test_stop(self):
        """Test stopping the queue."""
        queue = TaskQueue()

        queue.stop()

        stats = queue.get_status()
        assert stats.status == QueueStatus.STOPPED

    def test_pause_resume(self):
        """Test pausing and resuming the queue."""
        queue = TaskQueue()

        queue.pause()
        stats = queue.get_status()
        assert stats.status == QueueStatus.PAUSED

        queue.resume()
        stats = queue.get_status()
        # After resuming from paused, status becomes running (queue assumes it should run)
        # This is the expected behavior - resume means "go back to running"
        assert stats.status == QueueStatus.RUNNING

    def test_callbacks(self):
        """Test callbacks are stored."""
        completed_tasks = []
        failed_tasks = []

        def on_complete(task):
            completed_tasks.append(task)

        def on_failed(task, reason):
            failed_tasks.append((task, reason))

        queue = TaskQueue(
            on_task_complete=on_complete,
            on_task_failed=on_failed,
        )

        assert queue.on_task_complete is not None
        assert queue.on_task_failed is not None
