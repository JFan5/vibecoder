"""Database operations for VibeCoder."""

import json
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ..config import config
from .models import Base, TaskModel, IterationModel, PermissionModel, LogModel


class Database:
    """Database manager for VibeCoder."""

    def __init__(self, database_url: Optional[str] = None) -> None:
        """Initialize database connection."""
        self.database_url = database_url or config.database_url

        # Ensure the database directory exists
        if self.database_url.startswith("sqlite:///"):
            db_path = Path(self.database_url.replace("sqlite:///", ""))
            db_path.parent.mkdir(parents=True, exist_ok=True)

        self.engine = create_engine(self.database_url, echo=False)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def init_db(self) -> None:
        """Create all database tables."""
        Base.metadata.create_all(self.engine)

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """Get a database session."""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # Task operations
    def create_task(
        self,
        task_id: str,
        name: str,
        description: str,
        requirements: list[str],
        verification_commands: list[str],
        working_directory: str,
        max_iterations: int = 10,
        timeout_per_iteration: int = 300,
    ) -> TaskModel:
        """Create a new task."""
        with self.get_session() as session:
            task = TaskModel(
                id=task_id,
                name=name,
                description=description,
                working_directory=working_directory,
                max_iterations=max_iterations,
                timeout_per_iteration=timeout_per_iteration,
                status="pending",
                current_iteration=0,
            )
            task.set_requirements(requirements)
            task.set_verification_commands(verification_commands)
            task.set_conversation_history([])
            task.set_artifacts([])
            session.add(task)
            session.flush()
            # Refresh to get the full object
            session.refresh(task)
            return task

    def get_task(self, task_id: str) -> Optional[TaskModel]:
        """Get a task by ID."""
        with self.get_session() as session:
            task = session.query(TaskModel).filter(TaskModel.id == task_id).first()
            if task:
                session.expunge(task)
            return task

    def list_tasks(
        self, status: Optional[str] = None, limit: int = 100
    ) -> list[TaskModel]:
        """List tasks, optionally filtered by status."""
        with self.get_session() as session:
            query = session.query(TaskModel)
            if status:
                query = query.filter(TaskModel.status == status)
            tasks = query.order_by(TaskModel.created_at.desc()).limit(limit).all()
            for task in tasks:
                session.expunge(task)
            return tasks

    def update_task(self, task_id: str, **kwargs) -> Optional[TaskModel]:
        """Update a task."""
        with self.get_session() as session:
            task = session.query(TaskModel).filter(TaskModel.id == task_id).first()
            if not task:
                return None

            for key, value in kwargs.items():
                if key in ("requirements", "verification_commands", "artifacts"):
                    # Handle JSON array fields
                    setattr(task, key, json.dumps(value) if value else None)
                elif key == "conversation_history":
                    task.set_conversation_history(value)
                else:
                    setattr(task, key, value)

            task.updated_at = datetime.utcnow()
            session.flush()
            session.refresh(task)
            session.expunge(task)
            return task

    def delete_task(self, task_id: str) -> bool:
        """Delete a task and all related data."""
        with self.get_session() as session:
            task = session.query(TaskModel).filter(TaskModel.id == task_id).first()
            if not task:
                return False

            # Delete related records
            session.query(IterationModel).filter(
                IterationModel.task_id == task_id
            ).delete()
            session.query(PermissionModel).filter(
                PermissionModel.task_id == task_id
            ).delete()
            session.query(LogModel).filter(LogModel.task_id == task_id).delete()
            session.delete(task)
            return True

    # Iteration operations
    def create_iteration(
        self,
        task_id: str,
        iteration_number: int,
        ai_request: str,
        ai_response: str,
        files_modified: list[str],
        verification_output: str,
        verification_passed: bool,
        feedback_generated: Optional[str] = None,
    ) -> IterationModel:
        """Create a new iteration record."""
        with self.get_session() as session:
            iteration = IterationModel(
                task_id=task_id,
                iteration_number=iteration_number,
                ai_request=ai_request,
                ai_response=ai_response,
                verification_output=verification_output,
                verification_passed=verification_passed,
                feedback_generated=feedback_generated,
            )
            iteration.set_files_modified(files_modified)
            session.add(iteration)
            session.flush()
            session.refresh(iteration)
            session.expunge(iteration)
            return iteration

    def get_iterations(self, task_id: str) -> list[IterationModel]:
        """Get all iterations for a task."""
        with self.get_session() as session:
            iterations = (
                session.query(IterationModel)
                .filter(IterationModel.task_id == task_id)
                .order_by(IterationModel.iteration_number)
                .all()
            )
            for iteration in iterations:
                session.expunge(iteration)
            return iterations

    # Permission operations
    def create_permission(
        self,
        task_id: str,
        action_type: str,
        description: str,
        details: dict,
    ) -> PermissionModel:
        """Create a new permission request."""
        with self.get_session() as session:
            permission = PermissionModel(
                task_id=task_id,
                action_type=action_type,
                description=description,
                status="pending",
            )
            permission.set_details(details)
            session.add(permission)
            session.flush()
            session.refresh(permission)
            session.expunge(permission)
            return permission

    def get_pending_permissions(
        self, task_id: Optional[str] = None
    ) -> list[PermissionModel]:
        """Get pending permission requests."""
        with self.get_session() as session:
            query = session.query(PermissionModel).filter(
                PermissionModel.status == "pending"
            )
            if task_id:
                query = query.filter(PermissionModel.task_id == task_id)
            permissions = query.order_by(PermissionModel.created_at).all()
            for perm in permissions:
                session.expunge(perm)
            return permissions

    def resolve_permission(
        self, permission_id: int, status: str, resolved_by: str
    ) -> Optional[PermissionModel]:
        """Resolve a permission request."""
        with self.get_session() as session:
            permission = (
                session.query(PermissionModel)
                .filter(PermissionModel.id == permission_id)
                .first()
            )
            if not permission:
                return None

            permission.status = status
            permission.resolved_by = resolved_by
            permission.resolved_at = datetime.utcnow()
            session.flush()
            session.refresh(permission)
            session.expunge(permission)
            return permission

    # Log operations
    def create_log(
        self,
        level: str,
        message: str,
        task_id: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> LogModel:
        """Create a log entry."""
        with self.get_session() as session:
            log = LogModel(
                task_id=task_id,
                level=level,
                message=message,
            )
            if details:
                log.set_details(details)
            session.add(log)
            session.flush()
            session.refresh(log)
            session.expunge(log)
            return log

    def get_logs(
        self,
        task_id: Optional[str] = None,
        level: Optional[str] = None,
        limit: int = 100,
    ) -> list[LogModel]:
        """Get logs, optionally filtered."""
        with self.get_session() as session:
            query = session.query(LogModel)
            if task_id:
                query = query.filter(LogModel.task_id == task_id)
            if level:
                query = query.filter(LogModel.level == level)
            logs = query.order_by(LogModel.created_at.desc()).limit(limit).all()
            for log in logs:
                session.expunge(log)
            return logs


# Global database instance
_db: Optional[Database] = None


def get_db() -> Database:
    """Get the global database instance."""
    global _db
    if _db is None:
        _db = Database()
        _db.init_db()
    return _db
