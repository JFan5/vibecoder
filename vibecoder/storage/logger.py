"""Structured logging for VibeCoder."""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from rich.console import Console
from rich.logging import RichHandler

from ..config import config


class StructuredLogger:
    """Logger that writes to both console and database."""

    def __init__(self, name: str = "vibecoder") -> None:
        """Initialize the logger."""
        self.name = name
        self.console = Console()
        self._db = None  # Lazy initialization to avoid circular imports

        # Set up Python logger with Rich handler
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, config.log_level))

        if not self.logger.handlers:
            # Rich console handler
            console_handler = RichHandler(
                console=self.console,
                show_time=True,
                show_path=False,
            )
            console_handler.setLevel(getattr(logging, config.log_level))
            self.logger.addHandler(console_handler)

            # File handler for JSON logs
            log_file = config.logs_dir / f"{name}.jsonl"
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(JsonFormatter())
            file_handler.setLevel(logging.DEBUG)
            self.logger.addHandler(file_handler)

    @property
    def db(self):
        """Get database instance lazily."""
        if self._db is None:
            from .database import get_db

            self._db = get_db()
        return self._db

    def _log(
        self,
        level: str,
        message: str,
        task_id: Optional[str] = None,
        details: Optional[dict] = None,
        exc_info: bool = False,
    ) -> None:
        """Log a message."""
        extra = {
            "task_id": task_id,
            "details": details or {},
        }

        log_level = getattr(logging, level.upper())
        self.logger.log(log_level, message, extra=extra, exc_info=exc_info)

        # Also log to database
        try:
            self.db.create_log(
                level=level.upper(),
                message=message,
                task_id=task_id,
                details=details,
            )
        except Exception:
            # Don't fail if database logging fails
            pass

    def debug(
        self,
        message: str,
        task_id: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> None:
        """Log a debug message."""
        self._log("debug", message, task_id, details)

    def info(
        self,
        message: str,
        task_id: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> None:
        """Log an info message."""
        self._log("info", message, task_id, details)

    def warning(
        self,
        message: str,
        task_id: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> None:
        """Log a warning message."""
        self._log("warning", message, task_id, details)

    def error(
        self,
        message: str,
        task_id: Optional[str] = None,
        details: Optional[dict] = None,
        exc_info: bool = False,
    ) -> None:
        """Log an error message."""
        self._log("error", message, task_id, details, exc_info=exc_info)

    def task_started(self, task_id: str, task_name: str) -> None:
        """Log task started event."""
        self.info(f"Task started: {task_name}", task_id=task_id)

    def task_completed(self, task_id: str, task_name: str, iterations: int) -> None:
        """Log task completed event."""
        self.info(
            f"Task completed: {task_name}",
            task_id=task_id,
            details={"iterations": iterations},
        )

    def task_failed(
        self, task_id: str, task_name: str, reason: str, iterations: int
    ) -> None:
        """Log task failed event."""
        self.error(
            f"Task failed: {task_name}",
            task_id=task_id,
            details={"reason": reason, "iterations": iterations},
        )

    def iteration_started(self, task_id: str, iteration: int) -> None:
        """Log iteration started event."""
        self.info(f"Iteration {iteration} started", task_id=task_id)

    def iteration_completed(
        self, task_id: str, iteration: int, passed: bool
    ) -> None:
        """Log iteration completed event."""
        status = "passed" if passed else "failed"
        self.info(
            f"Iteration {iteration} {status}",
            task_id=task_id,
            details={"passed": passed},
        )

    def permission_requested(
        self, task_id: str, action_type: str, description: str
    ) -> None:
        """Log permission request event."""
        self.warning(
            f"Permission requested: {action_type}",
            task_id=task_id,
            details={"description": description},
        )

    def permission_resolved(
        self, task_id: str, action_type: str, approved: bool
    ) -> None:
        """Log permission resolution event."""
        status = "approved" if approved else "denied"
        self.info(
            f"Permission {status}: {action_type}",
            task_id=task_id,
            details={"approved": approved},
        )


class JsonFormatter(logging.Formatter):
    """JSON log formatter."""

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }

        # Add extra fields
        if hasattr(record, "task_id") and record.task_id:
            log_data["task_id"] = record.task_id
        if hasattr(record, "details") and record.details:
            log_data["details"] = record.details

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


# Global logger instance
logger = StructuredLogger()
