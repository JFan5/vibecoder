"""Tests for the iteration module."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from vibecoder.core.task import Task, TaskStatus
from vibecoder.core.iteration import IterationManager, IterationResult
from vibecoder.ai.base import AIResponse, FileOperation
from vibecoder.verification.runner import CommandResult


class TestIterationResult:
    """Test cases for IterationResult."""

    def test_summary_passed(self):
        """Test summary for passed iteration."""
        result = IterationResult(
            iteration_number=1,
            ai_response=AIResponse(text="Done"),
            files_modified=["file1.py", "file2.py"],
            verification_results=[],
            verification_passed=True,
        )

        summary = result.summary
        assert "1" in summary
        assert "PASSED" in summary
        assert "2" in summary

    def test_summary_failed(self):
        """Test summary for failed iteration."""
        result = IterationResult(
            iteration_number=3,
            ai_response=AIResponse(text="Done"),
            files_modified=["file1.py"],
            verification_results=[],
            verification_passed=False,
        )

        summary = result.summary
        assert "3" in summary
        assert "FAILED" in summary


class TestIterationManager:
    """Test cases for IterationManager."""

    def create_test_task(self) -> Task:
        """Create a task for testing."""
        return Task.create(
            name="Test Task",
            description="Test description",
            requirements=["req1"],
            verification_commands=["echo 'test'"],
            working_directory="/tmp",
            max_iterations=5,
        )

    @pytest.mark.asyncio
    async def test_run_iteration_success(self):
        """Test running a successful iteration."""
        task = self.create_test_task()

        # Mock AI provider
        mock_ai = AsyncMock()
        mock_ai.generate_with_tools.return_value = AIResponse(
            text="Implementation complete",
            file_operations=[
                FileOperation(operation="write", path="test.py", content="print('hello')")
            ],
            is_complete=True,
        )

        # Mock permission system
        mock_permissions = MagicMock()
        mock_permissions.check_file_write.return_value = None

        # Patch database before creating manager
        with patch('vibecoder.core.iteration.get_db') as mock_db:
            mock_db.return_value.create_iteration = MagicMock()

            with patch.object(IterationManager, '_apply_file_operations', new_callable=AsyncMock) as mock_apply:
                mock_apply.return_value = ["/tmp/test.py"]

                manager = IterationManager(
                    task=task,
                    ai_provider=mock_ai,
                    permission_system=mock_permissions,
                )

                # Mock the runner
                manager.runner = MagicMock()
                manager.runner.run_verification_commands = AsyncMock(
                    return_value=[
                        CommandResult("echo 'test'", 0, "test", "")
                    ]
                )
                manager.runner.get_verification_summary = MagicMock(
                    return_value=(True, "1. [PASS] echo 'test'")
                )

                result = await manager.run_iteration()

        assert result.verification_passed
        assert task.current_iteration == 1

    @pytest.mark.asyncio
    async def test_run_iteration_failure(self):
        """Test running a failed iteration."""
        task = self.create_test_task()

        # Mock AI provider
        mock_ai = AsyncMock()
        mock_ai.generate_with_tools.return_value = AIResponse(
            text="Implementation attempt",
            file_operations=[],
        )

        # Mock permission system
        mock_permissions = MagicMock()

        with patch('vibecoder.core.iteration.get_db') as mock_db:
            mock_db.return_value.create_iteration = MagicMock()

            with patch.object(IterationManager, '_apply_file_operations', new_callable=AsyncMock) as mock_apply:
                mock_apply.return_value = []

                manager = IterationManager(
                    task=task,
                    ai_provider=mock_ai,
                    permission_system=mock_permissions,
                )

                # Mock the runner to return failure
                manager.runner = MagicMock()
                manager.runner.run_verification_commands = AsyncMock(
                    return_value=[
                        CommandResult("echo 'test'", 1, "", "error")
                    ]
                )
                manager.runner.get_verification_summary = MagicMock(
                    return_value=(False, "1. [FAIL] echo 'test'")
                )

                result = await manager.run_iteration()

        assert not result.verification_passed
        assert result.feedback is not None

    def test_build_messages_empty(self):
        """Test building messages from empty history."""
        task = self.create_test_task()

        # Patch all dependencies
        with patch('vibecoder.core.iteration.get_db'), \
             patch('vibecoder.core.iteration.ClaudeProvider') as mock_claude:
            # Make ClaudeProvider not require API key
            mock_claude.return_value = MagicMock()
            manager = IterationManager(task=task, ai_provider=MagicMock())
            messages = manager._build_messages()

        assert messages == []

    def test_build_messages_with_history(self):
        """Test building messages from conversation history."""
        task = self.create_test_task()
        task.add_message("user", "Hello")
        task.add_message("assistant", "Hi")

        with patch('vibecoder.core.iteration.get_db'), \
             patch('vibecoder.core.iteration.ClaudeProvider') as mock_claude:
            mock_claude.return_value = MagicMock()
            manager = IterationManager(task=task, ai_provider=MagicMock())
            messages = manager._build_messages()

        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
