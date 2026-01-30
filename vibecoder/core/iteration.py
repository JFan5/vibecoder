"""Iteration loop management for VibeCoder."""

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..ai.base import AIResponse, FileOperation
from ..ai.claude import ClaudeProvider
from ..ai.prompts import SystemPrompts, TOOL_DEFINITIONS
from ..storage.database import get_db
from ..storage.logger import logger
from ..verification.feedback import FeedbackGenerator, Feedback
from ..verification.runner import CommandRunner, CommandResult
from .permission import PermissionSystem
from .task import Task, TaskStatus


@dataclass
class IterationResult:
    """Result of a single iteration."""

    iteration_number: int
    ai_response: AIResponse
    files_modified: list[str]
    verification_results: list[CommandResult]
    verification_passed: bool
    feedback: Optional[Feedback] = None

    @property
    def summary(self) -> str:
        """Get a summary of the iteration."""
        status = "PASSED" if self.verification_passed else "FAILED"
        files = len(self.files_modified)
        return f"Iteration {self.iteration_number}: {status} ({files} files modified)"


class IterationManager:
    """Manages the iteration loop for a task."""

    def __init__(
        self,
        task: Task,
        ai_provider: Optional[ClaudeProvider] = None,
        permission_system: Optional[PermissionSystem] = None,
    ) -> None:
        """Initialize the iteration manager.

        Args:
            task: The task to iterate on
            ai_provider: AI provider to use
            permission_system: Permission system for approvals
        """
        self.task = task
        self.ai = ai_provider or ClaudeProvider()
        self.permissions = permission_system or PermissionSystem()
        self.db = get_db()
        self.feedback_generator = FeedbackGenerator()

        # Create command runner for the task's working directory
        self.runner = CommandRunner(
            working_directory=task.working_directory,
            timeout=task.timeout_per_iteration,
        )

    async def run_iteration(
        self,
        previous_feedback: Optional[str] = None,
    ) -> IterationResult:
        """Run a single iteration of the task.

        Args:
            previous_feedback: Feedback from the previous iteration

        Returns:
            IterationResult with the results
        """
        iteration_num = self.task.current_iteration + 1
        logger.iteration_started(self.task.id, iteration_num)

        # Build the prompt
        system_prompt = SystemPrompts.get_coding_prompt(
            task_context=self.task.get_prompt_context(),
            previous_feedback=previous_feedback,
        )

        # Build messages from conversation history
        messages = self._build_messages()

        # If this is the first iteration, add the initial request
        if iteration_num == 1:
            messages.append({
                "role": "user",
                "content": f"Please implement the following task:\n\n{self.task.get_prompt_context()}",
            })
        elif previous_feedback:
            messages.append({
                "role": "user",
                "content": previous_feedback,
            })

        # Get AI response with tools
        ai_response = await self.ai.generate_with_tools(
            messages=messages,
            system_prompt=system_prompt,
            tools=TOOL_DEFINITIONS,
        )

        if ai_response.error:
            logger.error(
                f"AI error in iteration {iteration_num}",
                task_id=self.task.id,
                details={"error": ai_response.error},
            )
            return IterationResult(
                iteration_number=iteration_num,
                ai_response=ai_response,
                files_modified=[],
                verification_results=[],
                verification_passed=False,
            )

        # Apply file operations
        files_modified = await self._apply_file_operations(ai_response.file_operations)

        # Update task artifacts
        for file_path in files_modified:
            self.task.add_artifact(file_path)

        # Add to conversation history
        self.task.add_message("assistant", ai_response.text)

        # Run verification commands
        verification_results = await self.runner.run_verification_commands(
            self.task.verification_commands
        )

        # Check if verification passed
        verification_passed = all(r.success for r in verification_results)

        # Generate feedback if verification failed
        feedback = None
        if not verification_passed:
            feedback = self.feedback_generator.generate(
                verification_results,
                task_context=self.task.get_prompt_context(),
            )

        # Log the iteration
        logger.iteration_completed(self.task.id, iteration_num, verification_passed)

        # Store iteration in database
        all_output = self.runner.get_verification_summary(verification_results)[1]
        self.db.create_iteration(
            task_id=self.task.id,
            iteration_number=iteration_num,
            ai_request=str(messages),
            ai_response=ai_response.text,
            files_modified=files_modified,
            verification_output=all_output,
            verification_passed=verification_passed,
            feedback_generated=feedback.to_text() if feedback else None,
        )

        # Increment iteration counter
        self.task.increment_iteration()

        return IterationResult(
            iteration_number=iteration_num,
            ai_response=ai_response,
            files_modified=files_modified,
            verification_results=verification_results,
            verification_passed=verification_passed,
            feedback=feedback,
        )

    async def run_loop(self) -> bool:
        """Run the full iteration loop until success or max iterations.

        Returns:
            True if verification passed, False otherwise
        """
        previous_feedback = None

        while self.task.has_iterations_remaining():
            result = await self.run_iteration(previous_feedback)

            if result.verification_passed:
                self.task.status = TaskStatus.COMPLETED
                logger.task_completed(
                    self.task.id,
                    self.task.name,
                    self.task.current_iteration,
                )
                return True

            # Check if we need approval to continue
            perm_request = self.permissions.check_iteration_limit(
                self.task.id,
                self.task.current_iteration,
                self.task.max_iterations,
            )

            if perm_request:
                self.task.status = TaskStatus.NEEDS_APPROVAL
                logger.info(
                    "Task needs approval to continue past iteration limit",
                    task_id=self.task.id,
                )
                # In async context, we return and let the caller handle approval
                return False

            # Prepare feedback for next iteration
            if result.feedback:
                previous_feedback = self.feedback_generator.generate_ai_prompt(
                    result.feedback,
                    self.task.current_iteration,
                    self.task.max_iterations,
                )

        # Max iterations reached without success
        self.task.status = TaskStatus.FAILED
        logger.task_failed(
            self.task.id,
            self.task.name,
            "Max iterations reached",
            self.task.current_iteration,
        )
        return False

    async def _apply_file_operations(
        self, operations: list[FileOperation]
    ) -> list[str]:
        """Apply file operations from the AI response.

        Args:
            operations: List of file operations to apply

        Returns:
            List of file paths that were modified
        """
        modified = []
        working_dir = Path(self.task.working_directory)

        for op in operations:
            try:
                # Resolve the path
                if Path(op.path).is_absolute():
                    file_path = Path(op.path)
                else:
                    file_path = working_dir / op.path

                # Check permissions for writes outside working directory
                if op.operation == "write":
                    perm_request = self.permissions.check_file_write(
                        self.task.id, str(file_path), self.task.working_directory
                    )
                    if perm_request:
                        logger.warning(
                            f"File write requires approval: {file_path}",
                            task_id=self.task.id,
                        )
                        continue  # Skip this operation

                    # Create parent directories
                    file_path.parent.mkdir(parents=True, exist_ok=True)

                    # Write the file
                    file_path.write_text(op.content or "")
                    modified.append(str(file_path))
                    logger.debug(
                        f"Wrote file: {file_path}",
                        task_id=self.task.id,
                    )

                elif op.operation == "delete":
                    perm_request = self.permissions.check_file_delete(
                        self.task.id, str(file_path), self.task.working_directory
                    )
                    if perm_request:
                        logger.warning(
                            f"File deletion requires approval: {file_path}",
                            task_id=self.task.id,
                        )
                        continue

                    if file_path.exists():
                        file_path.unlink()
                        modified.append(str(file_path))
                        logger.debug(
                            f"Deleted file: {file_path}",
                            task_id=self.task.id,
                        )

            except Exception as e:
                logger.error(
                    f"Error applying file operation: {e}",
                    task_id=self.task.id,
                    exc_info=True,
                )

        return modified

    def _build_messages(self) -> list[dict]:
        """Build messages list from conversation history."""
        messages = []
        for msg in self.task.conversation_history:
            messages.append({
                "role": msg["role"],
                "content": msg["content"],
            })
        return messages
