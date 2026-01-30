"""Tests for the Task model."""

import pytest
from pathlib import Path
import tempfile

from vibecoder.core.task import Task, TaskStatus


class TestTask:
    """Test cases for the Task model."""

    def test_create_task(self):
        """Test creating a task."""
        task = Task.create(
            name="Test Task",
            description="Test description",
            requirements=["req1", "req2"],
            verification_commands=["pytest"],
            working_directory="/tmp",
        )

        assert task.id is not None
        assert task.name == "Test Task"
        assert task.description == "Test description"
        assert task.requirements == ["req1", "req2"]
        assert task.verification_commands == ["pytest"]
        assert task.working_directory == "/tmp"
        assert task.status == TaskStatus.PENDING
        assert task.current_iteration == 0
        assert task.max_iterations == 10

    def test_task_to_dict(self):
        """Test converting task to dictionary."""
        task = Task.create(
            name="Test Task",
            description="Test description",
            requirements=["req1"],
            verification_commands=["pytest"],
            working_directory="/tmp",
        )

        data = task.to_dict()

        assert data["id"] == task.id
        assert data["name"] == "Test Task"
        assert data["status"] == "pending"
        assert isinstance(data["created_at"], str)

    def test_task_from_dict(self):
        """Test creating task from dictionary."""
        data = {
            "id": "test-id",
            "name": "Test Task",
            "description": "Test description",
            "requirements": ["req1"],
            "verification_commands": ["pytest"],
            "working_directory": "/tmp",
            "status": "running",
            "current_iteration": 3,
        }

        task = Task.from_dict(data)

        assert task.id == "test-id"
        assert task.name == "Test Task"
        assert task.status == TaskStatus.RUNNING
        assert task.current_iteration == 3

    def test_task_from_yaml(self):
        """Test creating task from YAML file."""
        yaml_content = """
name: "YAML Test Task"
description: |
  Test description from YAML
requirements:
  - requirement 1
  - requirement 2
verification_commands:
  - pytest tests/
working_directory: /tmp
max_iterations: 5
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(yaml_content)
            yaml_path = f.name

        try:
            task = Task.from_yaml(yaml_path)

            assert task.name == "YAML Test Task"
            assert "Test description from YAML" in task.description
            assert len(task.requirements) == 2
            assert task.max_iterations == 5
        finally:
            Path(yaml_path).unlink()

    def test_add_message(self):
        """Test adding messages to conversation history."""
        task = Task.create(
            name="Test",
            description="",
            requirements=[],
            verification_commands=[],
            working_directory="/tmp",
        )

        task.add_message("user", "Hello")
        task.add_message("assistant", "Hi there!")

        assert len(task.conversation_history) == 2
        assert task.conversation_history[0]["role"] == "user"
        assert task.conversation_history[0]["content"] == "Hello"

    def test_add_artifact(self):
        """Test adding artifacts."""
        task = Task.create(
            name="Test",
            description="",
            requirements=[],
            verification_commands=[],
            working_directory="/tmp",
        )

        task.add_artifact("/tmp/file1.py")
        task.add_artifact("/tmp/file2.py")
        task.add_artifact("/tmp/file1.py")  # Duplicate

        assert len(task.artifacts) == 2  # No duplicates

    def test_increment_iteration(self):
        """Test incrementing iteration counter."""
        task = Task.create(
            name="Test",
            description="",
            requirements=[],
            verification_commands=[],
            working_directory="/tmp",
        )

        assert task.current_iteration == 0

        task.increment_iteration()
        assert task.current_iteration == 1

        task.increment_iteration()
        assert task.current_iteration == 2

    def test_has_iterations_remaining(self):
        """Test checking for remaining iterations."""
        task = Task.create(
            name="Test",
            description="",
            requirements=[],
            verification_commands=[],
            working_directory="/tmp",
            max_iterations=3,
        )

        assert task.has_iterations_remaining()

        task.current_iteration = 2
        assert task.has_iterations_remaining()

        task.current_iteration = 3
        assert not task.has_iterations_remaining()

    def test_get_prompt_context(self):
        """Test generating prompt context."""
        task = Task.create(
            name="Test Task",
            description="Build something",
            requirements=["req1", "req2"],
            verification_commands=["pytest", "mypy"],
            working_directory="/project",
        )

        context = task.get_prompt_context()

        assert "Test Task" in context
        assert "Build something" in context
        assert "req1" in context
        assert "pytest" in context
        assert "/project" in context
