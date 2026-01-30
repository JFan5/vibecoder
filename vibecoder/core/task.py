"""Task model and status management."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import yaml


class TaskStatus(str, Enum):
    """Task status enumeration."""

    PENDING = "pending"
    RUNNING = "running"
    NEEDS_APPROVAL = "needs_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """Task definition and runtime state."""

    # Core definition
    id: str
    name: str
    description: str
    requirements: list[str]
    verification_commands: list[str]
    working_directory: str

    # Configuration
    max_iterations: int = 10
    timeout_per_iteration: int = 300

    # Runtime state
    status: TaskStatus = TaskStatus.PENDING
    current_iteration: int = 0
    conversation_history: list[dict] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    @classmethod
    def create(
        cls,
        name: str,
        description: str,
        requirements: list[str],
        verification_commands: list[str],
        working_directory: str,
        max_iterations: int = 10,
        timeout_per_iteration: int = 300,
    ) -> "Task":
        """Create a new task with a generated ID."""
        return cls(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            requirements=requirements,
            verification_commands=verification_commands,
            working_directory=working_directory,
            max_iterations=max_iterations,
            timeout_per_iteration=timeout_per_iteration,
        )

    @classmethod
    def from_yaml(cls, yaml_path: str | Path) -> "Task":
        """Create a task from a YAML file."""
        with open(yaml_path, "r") as f:
            data = yaml.safe_load(f)

        return cls.create(
            name=data["name"],
            description=data.get("description", ""),
            requirements=data.get("requirements", []),
            verification_commands=data.get("verification_commands", []),
            working_directory=data.get("working_directory", str(Path.cwd())),
            max_iterations=data.get("max_iterations", 10),
            timeout_per_iteration=data.get("timeout_per_iteration", 300),
        )

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        """Create a task from a dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data["name"],
            description=data.get("description", ""),
            requirements=data.get("requirements", []),
            verification_commands=data.get("verification_commands", []),
            working_directory=data.get("working_directory", str(Path.cwd())),
            max_iterations=data.get("max_iterations", 10),
            timeout_per_iteration=data.get("timeout_per_iteration", 300),
            status=TaskStatus(data.get("status", "pending")),
            current_iteration=data.get("current_iteration", 0),
            conversation_history=data.get("conversation_history", []),
            artifacts=data.get("artifacts", []),
        )

    def to_dict(self) -> dict:
        """Convert task to a dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "requirements": self.requirements,
            "verification_commands": self.verification_commands,
            "working_directory": self.working_directory,
            "max_iterations": self.max_iterations,
            "timeout_per_iteration": self.timeout_per_iteration,
            "status": self.status.value,
            "current_iteration": self.current_iteration,
            "conversation_history": self.conversation_history,
            "artifacts": self.artifacts,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the conversation history."""
        self.conversation_history.append(
            {
                "role": role,
                "content": content,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
        self.updated_at = datetime.utcnow()

    def add_artifact(self, file_path: str) -> None:
        """Add an artifact to the task."""
        if file_path not in self.artifacts:
            self.artifacts.append(file_path)
            self.updated_at = datetime.utcnow()

    def increment_iteration(self) -> None:
        """Increment the current iteration counter."""
        self.current_iteration += 1
        self.updated_at = datetime.utcnow()

    def has_iterations_remaining(self) -> bool:
        """Check if the task has iterations remaining."""
        return self.current_iteration < self.max_iterations

    def get_prompt_context(self) -> str:
        """Generate the context string for the AI prompt."""
        requirements_str = "\n".join(
            f"- {req}" for req in self.requirements
        )
        verification_str = "\n".join(
            f"- {cmd}" for cmd in self.verification_commands
        )

        return f"""Task: {self.name}

Description:
{self.description}

Requirements:
{requirements_str}

Verification Commands (these will be run to verify success):
{verification_str}

Working Directory: {self.working_directory}

Current Iteration: {self.current_iteration + 1}/{self.max_iterations}
"""

    def __str__(self) -> str:
        """String representation of the task."""
        return f"Task({self.id[:8]}, {self.name}, {self.status.value})"
