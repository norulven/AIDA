"""Data models for task management."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Priority(str, Enum):
    """Task priority levels."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TaskStatus(str, Enum):
    """Task status values."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class Project:
    """A project/category for grouping tasks."""

    id: int
    name: str
    description: str | None = None
    color: str | None = None
    created_at: datetime | None = None
    archived: bool = False


@dataclass
class Task:
    """A task/todo item."""

    id: int
    title: str
    description: str | None = None
    priority: Priority = Priority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING
    project_id: int | None = None
    project_name: str | None = None
    due_date: datetime | None = None
    reminder_at: datetime | None = None
    reminder_sent: bool = False
    ha_list_name: str | None = None
    ha_item_id: str | None = None
    ha_synced_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    completed_at: datetime | None = None

    @property
    def is_overdue(self) -> bool:
        """Check if task is overdue."""
        if self.due_date is None or self.status == TaskStatus.COMPLETED:
            return False
        return datetime.now() > self.due_date

    @property
    def is_completed(self) -> bool:
        """Check if task is completed."""
        return self.status == TaskStatus.COMPLETED


@dataclass
class Reminder:
    """A reminder for a task."""

    id: int
    task_id: int
    remind_at: datetime
    reminder_type: str = "once"  # once, daily, weekly
    sent: bool = False
    created_at: datetime | None = None
