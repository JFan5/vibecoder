"""Abstract base class for AI providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class FileOperation:
    """Represents a file operation requested by the AI."""

    operation: str  # "write", "read", "delete"
    path: str
    content: Optional[str] = None


@dataclass
class AIResponse:
    """Response from an AI provider."""

    # The main text response
    text: str

    # Any file operations the AI wants to perform
    file_operations: list[FileOperation] = field(default_factory=list)

    # Raw response data for debugging
    raw_response: Optional[dict] = None

    # Token usage
    input_tokens: int = 0
    output_tokens: int = 0

    # Whether the AI indicates it's done
    is_complete: bool = False

    # Any error that occurred
    error: Optional[str] = None


class AIProvider(ABC):
    """Abstract base class for AI providers."""

    @abstractmethod
    async def generate(
        self,
        messages: list[dict],
        system_prompt: str,
        max_tokens: int = 4096,
    ) -> AIResponse:
        """Generate a response from the AI.

        Args:
            messages: Conversation history in format [{"role": "user/assistant", "content": "..."}]
            system_prompt: The system prompt to use
            max_tokens: Maximum tokens in the response

        Returns:
            AIResponse containing the result
        """
        pass

    @abstractmethod
    async def generate_with_tools(
        self,
        messages: list[dict],
        system_prompt: str,
        tools: list[dict],
        max_tokens: int = 4096,
    ) -> AIResponse:
        """Generate a response with tool use capability.

        Args:
            messages: Conversation history
            system_prompt: The system prompt to use
            tools: List of tool definitions
            max_tokens: Maximum tokens in the response

        Returns:
            AIResponse containing the result and any tool calls
        """
        pass
