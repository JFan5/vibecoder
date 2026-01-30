"""SQLAlchemy models for VibeCoder."""

import json
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class TaskModel(Base):
    """Task database model."""

    __tablename__ = "tasks"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    requirements = Column(Text)  # JSON array
    verification_commands = Column(Text)  # JSON array
    working_directory = Column(String)
    max_iterations = Column(Integer, default=10)
    timeout_per_iteration = Column(Integer, default=300)
    status = Column(String, default="pending")
    current_iteration = Column(Integer, default=0)
    conversation_history = Column(Text)  # JSON array
    artifacts = Column(Text)  # JSON array
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    iterations = relationship("IterationModel", back_populates="task")
    permissions = relationship("PermissionModel", back_populates="task")

    def get_requirements(self) -> list[str]:
        """Get requirements as a list."""
        if self.requirements:
            return json.loads(self.requirements)
        return []

    def set_requirements(self, reqs: list[str]) -> None:
        """Set requirements from a list."""
        self.requirements = json.dumps(reqs)

    def get_verification_commands(self) -> list[str]:
        """Get verification commands as a list."""
        if self.verification_commands:
            return json.loads(self.verification_commands)
        return []

    def set_verification_commands(self, commands: list[str]) -> None:
        """Set verification commands from a list."""
        self.verification_commands = json.dumps(commands)

    def get_conversation_history(self) -> list[dict]:
        """Get conversation history as a list."""
        if self.conversation_history:
            return json.loads(self.conversation_history)
        return []

    def set_conversation_history(self, history: list[dict]) -> None:
        """Set conversation history from a list."""
        self.conversation_history = json.dumps(history)

    def get_artifacts(self) -> list[str]:
        """Get artifacts as a list."""
        if self.artifacts:
            return json.loads(self.artifacts)
        return []

    def set_artifacts(self, artifacts: list[str]) -> None:
        """Set artifacts from a list."""
        self.artifacts = json.dumps(artifacts)


class IterationModel(Base):
    """Iteration history model."""

    __tablename__ = "iterations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, ForeignKey("tasks.id"))
    iteration_number = Column(Integer)
    ai_request = Column(Text)
    ai_response = Column(Text)
    files_modified = Column(Text)  # JSON array
    verification_output = Column(Text)
    verification_passed = Column(Boolean)
    feedback_generated = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    task = relationship("TaskModel", back_populates="iterations")

    def get_files_modified(self) -> list[str]:
        """Get files modified as a list."""
        if self.files_modified:
            return json.loads(self.files_modified)
        return []

    def set_files_modified(self, files: list[str]) -> None:
        """Set files modified from a list."""
        self.files_modified = json.dumps(files)


class PermissionModel(Base):
    """Permission request model."""

    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, ForeignKey("tasks.id"))
    action_type = Column(String)
    description = Column(Text)
    details = Column(Text)  # JSON
    status = Column(String, default="pending")
    resolved_by = Column(String)
    resolved_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    task = relationship("TaskModel", back_populates="permissions")

    def get_details(self) -> dict:
        """Get details as a dict."""
        if self.details:
            return json.loads(self.details)
        return {}

    def set_details(self, details: dict) -> None:
        """Set details from a dict."""
        self.details = json.dumps(details)


class LogModel(Base):
    """Log entry model."""

    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String)
    level = Column(String)
    message = Column(Text)
    details = Column(Text)  # JSON
    created_at = Column(DateTime, default=datetime.utcnow)

    def get_details(self) -> dict:
        """Get details as a dict."""
        if self.details:
            return json.loads(self.details)
        return {}

    def set_details(self, details: dict) -> None:
        """Set details from a dict."""
        self.details = json.dumps(details)
