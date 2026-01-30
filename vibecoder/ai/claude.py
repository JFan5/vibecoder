"""Claude API integration for VibeCoder."""

import asyncio
from typing import Any, Optional

import anthropic

from ..config import config
from ..storage.logger import logger
from .base import AIProvider, AIResponse, FileOperation
from .prompts import TOOL_DEFINITIONS


class ClaudeProvider(AIProvider):
    """Claude API provider implementation."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        """Initialize the Claude provider.

        Args:
            api_key: Anthropic API key (defaults to config)
            model: Model to use (defaults to config)
        """
        self.api_key = api_key or config.anthropic_api_key
        self.model = model or config.claude_model

        if not self.api_key:
            raise ValueError(
                "Anthropic API key not provided. Set ANTHROPIC_API_KEY environment variable."
            )

        self.client = anthropic.AsyncAnthropic(api_key=self.api_key)

    async def generate(
        self,
        messages: list[dict],
        system_prompt: str,
        max_tokens: int = 4096,
    ) -> AIResponse:
        """Generate a response from Claude.

        Args:
            messages: Conversation history
            system_prompt: The system prompt to use
            max_tokens: Maximum tokens in the response

        Returns:
            AIResponse containing the result
        """
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=messages,
            )

            text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    text += block.text

            return AIResponse(
                text=text,
                raw_response=response.model_dump(),
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )

        except anthropic.APIError as e:
            logger.error(f"Claude API error: {e}", exc_info=True)
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
        """Generate a response with tool use capability.

        Args:
            messages: Conversation history
            system_prompt: The system prompt to use
            tools: List of tool definitions (defaults to standard tools)
            max_tokens: Maximum tokens in the response

        Returns:
            AIResponse containing the result and any tool calls
        """
        tools = tools or TOOL_DEFINITIONS

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=messages,
                tools=tools,
            )

            text = ""
            file_operations = []

            for block in response.content:
                if hasattr(block, "text"):
                    text += block.text
                elif block.type == "tool_use":
                    # Extract file operations from tool calls
                    file_op = self._parse_tool_use(block)
                    if file_op:
                        file_operations.append(file_op)

            # Check if AI indicates completion
            is_complete = self._check_completion(text, response)

            return AIResponse(
                text=text,
                file_operations=file_operations,
                raw_response=response.model_dump(),
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                is_complete=is_complete,
            )

        except anthropic.APIError as e:
            logger.error(f"Claude API error: {e}", exc_info=True)
            return AIResponse(
                text="",
                error=str(e),
            )

    def _parse_tool_use(self, tool_block: Any) -> Optional[FileOperation]:
        """Parse a tool use block into a FileOperation."""
        tool_name = tool_block.name
        tool_input = tool_block.input

        if tool_name == "write_file":
            return FileOperation(
                operation="write",
                path=tool_input.get("path", ""),
                content=tool_input.get("content", ""),
            )
        elif tool_name == "read_file":
            return FileOperation(
                operation="read",
                path=tool_input.get("path", ""),
            )
        elif tool_name == "run_command":
            # We don't return shell commands as file operations
            # They're handled separately by the execution layer
            return None

        return None

    def _check_completion(self, text: str, response: Any) -> bool:
        """Check if the AI indicates the task is complete."""
        # Check stop reason
        if response.stop_reason == "end_turn":
            # Look for completion indicators in text
            completion_phrases = [
                "implementation is complete",
                "all requirements are met",
                "verification should pass",
                "task is complete",
                "finished implementing",
            ]
            text_lower = text.lower()
            return any(phrase in text_lower for phrase in completion_phrases)

        return False

    async def analyze_feedback(
        self,
        verification_output: str,
        task_context: str,
    ) -> str:
        """Analyze verification output and generate feedback.

        Args:
            verification_output: The output from verification commands
            task_context: Context about the current task

        Returns:
            Analysis and suggestions for fixing issues
        """
        from .prompts import SystemPrompts

        messages = [
            {
                "role": "user",
                "content": f"""Task Context:
{task_context}

Verification Output:
{verification_output}

Please analyze the verification output and provide specific suggestions for fixing the issues.""",
            }
        ]

        response = await self.generate(
            messages=messages,
            system_prompt=SystemPrompts.FEEDBACK_ANALYSIS.format(
                verification_output=verification_output
            ),
            max_tokens=2048,
        )

        return response.text if not response.error else f"Error analyzing feedback: {response.error}"
