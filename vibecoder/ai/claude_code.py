"""Claude Code CLI integration for VibeCoder."""

import asyncio
import json
import os
import subprocess
from pathlib import Path
from typing import Optional

from ..storage.logger import logger
from .base import AIProvider, AIResponse, FileOperation


class ClaudeCodeProvider(AIProvider):
    """AI provider that uses Claude Code CLI."""

    def __init__(self, working_directory: Optional[str] = None) -> None:
        """Initialize the Claude Code provider.

        Args:
            working_directory: Directory to run Claude Code in
        """
        self.working_directory = working_directory or os.getcwd()

    async def generate(
        self,
        messages: list[dict],
        system_prompt: str,
        max_tokens: int = 4096,
    ) -> AIResponse:
        """Generate a response using Claude Code CLI.

        Args:
            messages: Conversation history
            system_prompt: The system prompt to use
            max_tokens: Maximum tokens in the response (not used with CLI)

        Returns:
            AIResponse containing the result
        """
        # Build the prompt from messages
        prompt = self._build_prompt(messages, system_prompt)

        try:
            # Run Claude Code with the prompt
            result = await self._run_claude_code(prompt)
            return AIResponse(
                text=result,
                file_operations=[],
            )
        except Exception as e:
            logger.error(f"Claude Code error: {e}", exc_info=True)
            return AIResponse(
                text="",
                error=str(e),
            )

    async def generate_with_tools(
        self,
        messages: list[dict],
        system_prompt: str,
        tools: Optional[list[dict]] = None,
        max_tokens: int = 4096,
    ) -> AIResponse:
        """Generate a response with Claude Code handling file operations.

        Claude Code handles file operations directly, so we just pass the prompt
        and let it do its thing.

        Args:
            messages: Conversation history
            system_prompt: The system prompt to use
            tools: Tool definitions (not used - Claude Code has its own tools)
            max_tokens: Maximum tokens (not used with CLI)

        Returns:
            AIResponse containing the result
        """
        # Build the prompt
        prompt = self._build_prompt(messages, system_prompt)

        # Add instruction for Claude Code to handle file operations
        prompt += "\n\nPlease implement the required changes directly. Create or modify files as needed."

        try:
            result = await self._run_claude_code(prompt)

            # Check for completion indicators
            is_complete = self._check_completion(result)

            return AIResponse(
                text=result,
                file_operations=[],  # Claude Code handles files directly
                is_complete=is_complete,
            )
        except Exception as e:
            logger.error(f"Claude Code error: {e}", exc_info=True)
            return AIResponse(
                text="",
                error=str(e),
            )

    async def _run_claude_code(self, prompt: str) -> str:
        """Run Claude Code CLI with the given prompt.

        Args:
            prompt: The prompt to send to Claude Code

        Returns:
            The response text from Claude Code
        """
        # Use claude CLI with --print flag to get output without interactive mode
        # and --dangerously-skip-permissions to allow file operations
        cmd = [
            "claude",
            "--print",
            "--dangerously-skip-permissions",
            "-p", prompt,
        ]

        logger.debug(f"Running Claude Code in {self.working_directory}")

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.working_directory,
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode("utf-8", errors="replace")
            raise RuntimeError(f"Claude Code failed: {error_msg}")

        return stdout.decode("utf-8", errors="replace")

    def _build_prompt(self, messages: list[dict], system_prompt: str) -> str:
        """Build a prompt string from messages and system prompt.

        Args:
            messages: Conversation history
            system_prompt: The system prompt

        Returns:
            Combined prompt string
        """
        parts = [system_prompt, ""]

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                parts.append(f"User: {content}")
            elif role == "assistant":
                parts.append(f"Assistant: {content}")

        return "\n\n".join(parts)

    def _check_completion(self, text: str) -> bool:
        """Check if the response indicates task completion.

        Args:
            text: Response text

        Returns:
            True if task appears complete
        """
        completion_phrases = [
            "implementation is complete",
            "all requirements are met",
            "verification should pass",
            "task is complete",
            "finished implementing",
            "successfully created",
            "successfully implemented",
        ]
        text_lower = text.lower()
        return any(phrase in text_lower for phrase in completion_phrases)
