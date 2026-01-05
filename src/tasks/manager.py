"""High-level task management API."""

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

from src.tasks.models import Task, Project, Priority, TaskStatus
from src.tasks.store import TaskStore

if TYPE_CHECKING:
    from src.memory.database import MemoryDatabase


class TaskManager(QObject):
    """Unified interface for task management."""

    task_reminder = Signal(object)  # Task

    def __init__(self, db: "MemoryDatabase"):
        super().__init__()

        self._db = db
        self._store = TaskStore(db)
        self._reminder_service = None

    @property
    def store(self) -> TaskStore:
        """Access the task store directly."""
        return self._store

    def start_reminder_service(self) -> None:
        """Start the background reminder service."""
        if self._reminder_service is not None:
            return

        from src.tasks.reminders import ReminderService
        self._reminder_service = ReminderService(self._store)
        self._reminder_service.reminder_due.connect(self._on_reminder_due)
        self._reminder_service.start()

    def stop_reminder_service(self) -> None:
        """Stop the reminder service."""
        if self._reminder_service:
            self._reminder_service.stop()
            self._reminder_service = None

    def _on_reminder_due(self, task: Task, reminder) -> None:
        """Handle reminder from service."""
        self.task_reminder.emit(task)

    # === Quick Actions ===

    def add_task(
        self,
        title: str,
        priority: Priority | None = None,
        due_date: datetime | None = None,
        project: str | None = None,
        reminder: datetime | None = None,
        sync_to_ha: str | None = None,
    ) -> Task:
        """Add a new task with optional properties."""
        # Get or create project if specified
        project_id = None
        if project:
            proj = self._store.get_project_by_name(project)
            if proj is None:
                proj = self._store.create_project(project)
            project_id = proj.id

        # Create the task
        task = self._store.create_task(
            title=title,
            priority=priority or Priority.MEDIUM,
            due_date=due_date,
            reminder_at=reminder,
            project_id=project_id,
            ha_list_name=sync_to_ha,
        )

        # Create reminder if specified
        if reminder:
            self._store.create_reminder(task.id, reminder)

        return task

    def complete_task(
        self,
        task_id: int | None = None,
        title: str | None = None
    ) -> Task | None:
        """Complete a task by ID or fuzzy title match."""
        if task_id:
            return self._store.complete_task(task_id)

        if title:
            task = self._store.find_task_by_title(title)
            if task:
                return self._store.complete_task(task.id)

        return None

    def list_tasks(
        self,
        project: str | None = None,
        priority: Priority | None = None,
        include_completed: bool = False,
    ) -> list[Task]:
        """Get tasks with optional filters."""
        if priority:
            tasks = self._store.get_tasks_by_priority(priority)
        elif project:
            proj = self._store.get_project_by_name(project)
            if proj:
                tasks = self._store.get_pending_tasks(project_id=proj.id)
            else:
                tasks = []
        else:
            tasks = self._store.get_pending_tasks()

        if not include_completed:
            tasks = [t for t in tasks if t.status != TaskStatus.COMPLETED]

        return tasks

    # === Speech Output ===

    def get_task_summary(self) -> str:
        """Get a spoken summary of tasks."""
        pending = self._store.get_pending_tasks()
        overdue = self._store.get_overdue_tasks()
        due_soon = self._store.get_tasks_due_soon(within_hours=24)

        if not pending:
            return "You have no pending tasks. Your todo list is empty."

        parts = []

        # Overdue tasks
        if overdue:
            if len(overdue) == 1:
                parts.append(f"You have 1 overdue task: {overdue[0].title}")
            else:
                parts.append(f"You have {len(overdue)} overdue tasks")

        # Due soon
        due_soon_not_overdue = [t for t in due_soon if t not in overdue]
        if due_soon_not_overdue:
            if len(due_soon_not_overdue) == 1:
                parts.append(f"1 task due in the next 24 hours: {due_soon_not_overdue[0].title}")
            else:
                parts.append(f"{len(due_soon_not_overdue)} tasks due in the next 24 hours")

        # High priority
        high_priority = [t for t in pending if t.priority == Priority.HIGH]
        if high_priority:
            if len(high_priority) == 1:
                parts.append(f"1 high priority task: {high_priority[0].title}")
            else:
                parts.append(f"{len(high_priority)} high priority tasks")

        # Total count
        total = len(pending)
        if total == 1:
            parts.append(f"You have 1 task total")
        else:
            parts.append(f"You have {total} tasks total")

        # List first few tasks
        if pending:
            top_tasks = pending[:3]
            task_list = self.format_tasks_for_speech(top_tasks)
            if len(pending) > 3:
                parts.append(f"Your top tasks are: {task_list}... and {len(pending) - 3} more")
            else:
                parts.append(f"Your tasks: {task_list}")

        return ". ".join(parts)

    def format_tasks_for_speech(self, tasks: list[Task]) -> str:
        """Format task list for TTS output."""
        if not tasks:
            return "no tasks"

        parts = []
        for task in tasks:
            text = task.title
            if task.priority == Priority.HIGH:
                text += " (important)"
            if task.due_date:
                text += f", due {self._format_due_date(task.due_date)}"
            parts.append(text)

        if len(parts) == 1:
            return parts[0]
        elif len(parts) == 2:
            return f"{parts[0]} and {parts[1]}"
        else:
            return ", ".join(parts[:-1]) + f", and {parts[-1]}"

    def _format_due_date(self, dt: datetime) -> str:
        """Format a due date for speech."""
        now = datetime.now()
        diff = dt - now

        if diff.days < 0:
            return "overdue"
        elif diff.days == 0:
            if diff.seconds < 3600:
                return "in less than an hour"
            else:
                hours = diff.seconds // 3600
                return f"in {hours} hour{'s' if hours > 1 else ''}"
        elif diff.days == 1:
            return "tomorrow"
        elif diff.days < 7:
            return dt.strftime("%A")  # Day name
        else:
            return dt.strftime("%B %d")  # Month Day

    # === Projects ===

    def create_project(self, name: str, description: str | None = None) -> Project:
        """Create a new project."""
        return self._store.create_project(name, description)

    def list_projects(self) -> list[Project]:
        """List all active projects."""
        return self._store.list_projects()

    # === Statistics ===

    def get_stats(self) -> dict:
        """Get task statistics."""
        return {
            "total": self._store.get_task_count(),
            "pending": self._store.get_task_count(TaskStatus.PENDING),
            "completed": self._store.get_task_count(TaskStatus.COMPLETED),
            "overdue": len(self._store.get_overdue_tasks()),
            "due_soon": len(self._store.get_tasks_due_soon(24)),
        }

    # === Cleanup ===

    def cleanup(self) -> None:
        """Clean up resources."""
        self.stop_reminder_service()
