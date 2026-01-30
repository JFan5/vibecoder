"""Permission and approval system for VibeCoder."""

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from ..config import config
from ..storage.database import get_db
from ..storage.logger import logger


class ActionType(str, Enum):
    """Types of actions that may require approval."""

    FILE_WRITE = "file_write"
    FILE_DELETE = "file_delete"
    SHELL_COMMAND = "shell_command"
    NETWORK_OPERATION = "network_operation"
    DATABASE_MODIFICATION = "database_modification"
    ITERATION_LIMIT = "iteration_limit"


class PermissionStatus(str, Enum):
    """Permission request status."""

    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"


@dataclass
class PermissionRequest:
    """A request for permission to perform an action."""

    task_id: str
    action_type: ActionType
    description: str
    details: dict

    # State
    id: Optional[int] = None
    status: PermissionStatus = PermissionStatus.PENDING
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "task_id": self.task_id,
            "action_type": self.action_type.value,
            "description": self.description,
            "details": self.details,
            "status": self.status.value,
            "resolved_by": self.resolved_by,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "created_at": self.created_at.isoformat(),
        }


class PermissionSystem:
    """System for managing permissions and approvals."""

    def __init__(self) -> None:
        """Initialize the permission system."""
        self.db = get_db()
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile dangerous command patterns."""
        self._dangerous_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in config.dangerous_patterns
        ]

    def check_file_write(
        self, task_id: str, file_path: str, working_directory: str
    ) -> Optional[PermissionRequest]:
        """Check if a file write requires permission.

        Returns a PermissionRequest if approval is needed, None otherwise.
        """
        file_path = Path(file_path).resolve()
        working_dir = Path(working_directory).resolve()

        # Check if file is outside working directory
        try:
            file_path.relative_to(working_dir)
            return None  # File is within working directory
        except ValueError:
            # File is outside working directory
            request = PermissionRequest(
                task_id=task_id,
                action_type=ActionType.FILE_WRITE,
                description=f"Write to file outside working directory: {file_path}",
                details={
                    "file_path": str(file_path),
                    "working_directory": str(working_dir),
                },
            )
            return self._create_request(request)

    def check_file_delete(
        self, task_id: str, file_path: str, working_directory: str
    ) -> Optional[PermissionRequest]:
        """Check if a file deletion requires permission."""
        file_path = Path(file_path).resolve()
        working_dir = Path(working_directory).resolve()

        # Always require approval for deletions outside working directory
        try:
            file_path.relative_to(working_dir)
            return None
        except ValueError:
            request = PermissionRequest(
                task_id=task_id,
                action_type=ActionType.FILE_DELETE,
                description=f"Delete file outside working directory: {file_path}",
                details={
                    "file_path": str(file_path),
                    "working_directory": str(working_dir),
                },
            )
            return self._create_request(request)

    def check_shell_command(
        self, task_id: str, command: str
    ) -> Optional[PermissionRequest]:
        """Check if a shell command requires permission.

        Returns a PermissionRequest if approval is needed, None otherwise.
        """
        # Check against dangerous patterns
        for pattern in self._dangerous_patterns:
            if pattern.search(command):
                request = PermissionRequest(
                    task_id=task_id,
                    action_type=ActionType.SHELL_COMMAND,
                    description=f"Potentially dangerous command detected: {command[:100]}",
                    details={
                        "command": command,
                        "matched_pattern": pattern.pattern,
                    },
                )
                return self._create_request(request)

        return None

    def check_iteration_limit(
        self, task_id: str, current_iteration: int, max_iterations: int
    ) -> Optional[PermissionRequest]:
        """Check if continuing past iteration limit requires permission."""
        if current_iteration >= max_iterations:
            request = PermissionRequest(
                task_id=task_id,
                action_type=ActionType.ITERATION_LIMIT,
                description=f"Task has reached iteration limit ({max_iterations}). Continue?",
                details={
                    "current_iteration": current_iteration,
                    "max_iterations": max_iterations,
                },
            )
            return self._create_request(request)
        return None

    def _create_request(self, request: PermissionRequest) -> PermissionRequest:
        """Create a permission request in the database."""
        perm = self.db.create_permission(
            task_id=request.task_id,
            action_type=request.action_type.value,
            description=request.description,
            details=request.details,
        )
        request.id = perm.id
        logger.permission_requested(
            request.task_id, request.action_type.value, request.description
        )
        return request

    def get_pending_requests(
        self, task_id: Optional[str] = None
    ) -> list[PermissionRequest]:
        """Get all pending permission requests."""
        perms = self.db.get_pending_permissions(task_id)
        return [
            PermissionRequest(
                id=p.id,
                task_id=p.task_id,
                action_type=ActionType(p.action_type),
                description=p.description,
                details=p.get_details(),
                status=PermissionStatus(p.status),
                created_at=p.created_at,
            )
            for p in perms
        ]

    def approve(self, permission_id: int, approved_by: str = "user") -> bool:
        """Approve a permission request."""
        perm = self.db.resolve_permission(permission_id, "approved", approved_by)
        if perm:
            logger.permission_resolved(
                perm.task_id, perm.action_type, approved=True
            )
            return True
        return False

    def deny(self, permission_id: int, denied_by: str = "user") -> bool:
        """Deny a permission request."""
        perm = self.db.resolve_permission(permission_id, "denied", denied_by)
        if perm:
            logger.permission_resolved(
                perm.task_id, perm.action_type, approved=False
            )
            return True
        return False

    def wait_for_approval(
        self, request: PermissionRequest, timeout: Optional[float] = None
    ) -> bool:
        """Wait for a permission request to be resolved.

        Returns True if approved, False if denied or timeout.
        This is a blocking call intended for CLI/synchronous use.
        """
        import time

        start_time = time.time()
        poll_interval = 1.0  # seconds

        while True:
            # Check if resolved
            perms = self.db.get_pending_permissions(request.task_id)
            matching = [p for p in perms if p.id == request.id]

            if not matching:
                # Request was resolved - check the final status
                with self.db.get_session() as session:
                    from ..storage.models import PermissionModel

                    perm = (
                        session.query(PermissionModel)
                        .filter(PermissionModel.id == request.id)
                        .first()
                    )
                    if perm:
                        return perm.status == "approved"
                return False

            # Check timeout
            if timeout and (time.time() - start_time) > timeout:
                return False

            time.sleep(poll_interval)
