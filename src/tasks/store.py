"""SQLite storage for tasks."""

from datetime import datetime
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

from src.tasks.models import Task, Project, Reminder, Priority, TaskStatus

if TYPE_CHECKING:
    from src.memory.database import MemoryDatabase


class TaskStore(QObject):
    """CRUD operations for tasks in SQLite."""

    task_created = Signal(int)
    task_updated = Signal(int)
    task_completed = Signal(int)
    task_deleted = Signal(int)
    project_created = Signal(int)

    def __init__(self, db: "MemoryDatabase"):
        super().__init__()
        self.db = db

    # === Task CRUD ===

    def create_task(
        self,
        title: str,
        description: str | None = None,
        priority: Priority = Priority.MEDIUM,
        project_id: int | None = None,
        due_date: datetime | None = None,
        reminder_at: datetime | None = None,
        ha_list_name: str | None = None,
    ) -> Task:
        """Create a new task."""
        if not isinstance(priority, Priority):
            priority = Priority(priority)

        now = datetime.now()

        with self.db.connection() as conn:
            cursor = conn.execute(
                """INSERT INTO tasks
                   (title, description, priority, project_id, due_date,
                    reminder_at, ha_list_name, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (title, description, priority.value, project_id, due_date,
                 reminder_at, ha_list_name, now, now)
            )
            task_id = cursor.lastrowid

        task = Task(
            id=task_id,
            title=title,
            description=description,
            priority=priority,
            project_id=project_id,
            due_date=due_date,
            reminder_at=reminder_at,
            ha_list_name=ha_list_name,
            created_at=now,
            updated_at=now,
        )

        self.task_created.emit(task_id)
        return task

    def get_task(self, task_id: int) -> Task | None:
        """Get a task by ID."""
        row = self.db.fetchone(
            """SELECT t.*, p.name as project_name
               FROM tasks t
               LEFT JOIN projects p ON t.project_id = p.id
               WHERE t.id = ?""",
            (task_id,)
        )

        if row is None:
            return None

        return self._row_to_task(row)

    def update_task(self, task_id: int, **kwargs) -> Task | None:
        """Update a task's fields."""
        if not kwargs:
            return self.get_task(task_id)

        # Convert Priority enum to string if present
        if "priority" in kwargs and isinstance(kwargs["priority"], Priority):
            kwargs["priority"] = kwargs["priority"].value
        if "status" in kwargs and isinstance(kwargs["status"], TaskStatus):
            kwargs["status"] = kwargs["status"].value

        kwargs["updated_at"] = datetime.now()

        set_clause = ", ".join(f"{k} = ?" for k in kwargs.keys())
        values = list(kwargs.values()) + [task_id]

        self.db.execute(
            f"UPDATE tasks SET {set_clause} WHERE id = ?",
            tuple(values)
        )

        self.task_updated.emit(task_id)
        return self.get_task(task_id)

    def delete_task(self, task_id: int) -> bool:
        """Delete a task."""
        with self.db.connection() as conn:
            cursor = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            deleted = cursor.rowcount > 0

        if deleted:
            self.task_deleted.emit(task_id)

        return deleted

    def complete_task(self, task_id: int) -> Task | None:
        """Mark a task as completed."""
        now = datetime.now()

        self.db.execute(
            """UPDATE tasks
               SET status = ?, completed_at = ?, updated_at = ?
               WHERE id = ?""",
            (TaskStatus.COMPLETED.value, now, now, task_id)
        )

        self.task_completed.emit(task_id)
        return self.get_task(task_id)

    # === Task Queries ===

    def get_pending_tasks(self, project_id: int | None = None) -> list[Task]:
        """Get all pending tasks, optionally filtered by project."""
        if project_id is not None:
            rows = self.db.fetchall(
                """SELECT t.*, p.name as project_name
                   FROM tasks t
                   LEFT JOIN projects p ON t.project_id = p.id
                   WHERE t.status = 'pending' AND t.project_id = ?
                   ORDER BY
                       CASE t.priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
                       t.due_date ASC NULLS LAST,
                       t.created_at ASC""",
                (project_id,)
            )
        else:
            rows = self.db.fetchall(
                """SELECT t.*, p.name as project_name
                   FROM tasks t
                   LEFT JOIN projects p ON t.project_id = p.id
                   WHERE t.status = 'pending'
                   ORDER BY
                       CASE t.priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
                       t.due_date ASC NULLS LAST,
                       t.created_at ASC"""
            )

        return [self._row_to_task(row) for row in rows]

    def get_tasks_by_priority(self, priority: Priority) -> list[Task]:
        """Get tasks by priority level."""
        rows = self.db.fetchall(
            """SELECT t.*, p.name as project_name
               FROM tasks t
               LEFT JOIN projects p ON t.project_id = p.id
               WHERE t.priority = ? AND t.status = 'pending'
               ORDER BY t.due_date ASC NULLS LAST, t.created_at ASC""",
            (priority.value,)
        )
        return [self._row_to_task(row) for row in rows]

    def get_tasks_due_soon(self, within_hours: int = 24) -> list[Task]:
        """Get tasks due within the specified hours."""
        from datetime import timedelta
        deadline = datetime.now() + timedelta(hours=within_hours)

        rows = self.db.fetchall(
            """SELECT t.*, p.name as project_name
               FROM tasks t
               LEFT JOIN projects p ON t.project_id = p.id
               WHERE t.status = 'pending'
                 AND t.due_date IS NOT NULL
                 AND t.due_date <= ?
               ORDER BY t.due_date ASC""",
            (deadline,)
        )
        return [self._row_to_task(row) for row in rows]

    def get_overdue_tasks(self) -> list[Task]:
        """Get all overdue tasks."""
        now = datetime.now()

        rows = self.db.fetchall(
            """SELECT t.*, p.name as project_name
               FROM tasks t
               LEFT JOIN projects p ON t.project_id = p.id
               WHERE t.status = 'pending'
                 AND t.due_date IS NOT NULL
                 AND t.due_date < ?
               ORDER BY t.due_date ASC""",
            (now,)
        )
        return [self._row_to_task(row) for row in rows]

    def search_tasks(self, query: str) -> list[Task]:
        """Search tasks by title."""
        rows = self.db.fetchall(
            """SELECT t.*, p.name as project_name
               FROM tasks t
               LEFT JOIN projects p ON t.project_id = p.id
               WHERE t.title LIKE ?
               ORDER BY t.status ASC, t.created_at DESC
               LIMIT 20""",
            (f"%{query}%",)
        )
        return [self._row_to_task(row) for row in rows]

    def find_task_by_title(self, title: str) -> Task | None:
        """Find a task by fuzzy title match."""
        # Try exact match first
        row = self.db.fetchone(
            """SELECT t.*, p.name as project_name
               FROM tasks t
               LEFT JOIN projects p ON t.project_id = p.id
               WHERE LOWER(t.title) = LOWER(?) AND t.status = 'pending'""",
            (title,)
        )

        if row:
            return self._row_to_task(row)

        # Try partial match
        row = self.db.fetchone(
            """SELECT t.*, p.name as project_name
               FROM tasks t
               LEFT JOIN projects p ON t.project_id = p.id
               WHERE LOWER(t.title) LIKE LOWER(?) AND t.status = 'pending'
               ORDER BY t.created_at DESC
               LIMIT 1""",
            (f"%{title}%",)
        )

        if row:
            return self._row_to_task(row)

        return None

    # === Project CRUD ===

    def create_project(
        self,
        name: str,
        description: str | None = None,
        color: str | None = None
    ) -> Project:
        """Create a new project."""
        now = datetime.now()

        with self.db.connection() as conn:
            cursor = conn.execute(
                "INSERT INTO projects (name, description, color, created_at) VALUES (?, ?, ?, ?)",
                (name, description, color, now)
            )
            project_id = cursor.lastrowid

        project = Project(
            id=project_id,
            name=name,
            description=description,
            color=color,
            created_at=now,
        )

        self.project_created.emit(project_id)
        return project

    def get_project(self, project_id: int) -> Project | None:
        """Get a project by ID."""
        row = self.db.fetchone("SELECT * FROM projects WHERE id = ?", (project_id,))
        if row is None:
            return None
        return self._row_to_project(row)

    def get_project_by_name(self, name: str) -> Project | None:
        """Get a project by name."""
        row = self.db.fetchone(
            "SELECT * FROM projects WHERE LOWER(name) = LOWER(?)",
            (name,)
        )
        if row is None:
            return None
        return self._row_to_project(row)

    def list_projects(self, include_archived: bool = False) -> list[Project]:
        """List all projects."""
        if include_archived:
            rows = self.db.fetchall("SELECT * FROM projects ORDER BY name")
        else:
            rows = self.db.fetchall(
                "SELECT * FROM projects WHERE archived = 0 ORDER BY name"
            )
        return [self._row_to_project(row) for row in rows]

    def delete_project(self, project_id: int) -> bool:
        """Delete a project (tasks will have project_id set to NULL)."""
        with self.db.connection() as conn:
            cursor = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            return cursor.rowcount > 0

    # === Reminder Operations ===

    def create_reminder(
        self,
        task_id: int,
        remind_at: datetime,
        reminder_type: str = "once"
    ) -> Reminder:
        """Create a reminder for a task."""
        now = datetime.now()

        with self.db.connection() as conn:
            cursor = conn.execute(
                """INSERT INTO task_reminders (task_id, remind_at, reminder_type, created_at)
                   VALUES (?, ?, ?, ?)""",
                (task_id, remind_at, reminder_type, now)
            )
            reminder_id = cursor.lastrowid

        return Reminder(
            id=reminder_id,
            task_id=task_id,
            remind_at=remind_at,
            reminder_type=reminder_type,
            created_at=now,
        )

    def get_pending_reminders(self, before: datetime) -> list[tuple[Reminder, Task]]:
        """Get reminders due before the specified time."""
        rows = self.db.fetchall(
            """SELECT r.*, t.title, t.description, t.priority, t.status,
                      t.project_id, t.due_date, t.ha_list_name, t.created_at as task_created_at
               FROM task_reminders r
               JOIN tasks t ON r.task_id = t.id
               WHERE r.sent = 0 AND r.remind_at <= ? AND t.status = 'pending'
               ORDER BY r.remind_at ASC""",
            (before,)
        )

        results = []
        for row in rows:
            reminder = Reminder(
                id=row["id"],
                task_id=row["task_id"],
                remind_at=row["remind_at"],
                reminder_type=row["reminder_type"],
                sent=bool(row["sent"]),
                created_at=row["created_at"],
            )
            task = Task(
                id=row["task_id"],
                title=row["title"],
                description=row["description"],
                priority=Priority(row["priority"]),
                status=TaskStatus(row["status"]),
                project_id=row["project_id"],
                due_date=row["due_date"],
                ha_list_name=row["ha_list_name"],
                created_at=row["task_created_at"],
            )
            results.append((reminder, task))

        return results

    def mark_reminder_sent(self, reminder_id: int) -> None:
        """Mark a reminder as sent."""
        self.db.execute(
            "UPDATE task_reminders SET sent = 1 WHERE id = ?",
            (reminder_id,)
        )

    # === HA Sync Helpers ===

    def get_tasks_by_ha_list(self, list_name: str) -> list[Task]:
        """Get all tasks synced to a specific HA list."""
        rows = self.db.fetchall(
            """SELECT t.*, p.name as project_name
               FROM tasks t
               LEFT JOIN projects p ON t.project_id = p.id
               WHERE t.ha_list_name = ?
               ORDER BY t.created_at DESC""",
            (list_name,)
        )
        return [self._row_to_task(row) for row in rows]

    def update_ha_sync_status(
        self,
        task_id: int,
        ha_item_id: str | None = None
    ) -> None:
        """Update HA sync status for a task."""
        now = datetime.now()
        self.db.execute(
            "UPDATE tasks SET ha_item_id = ?, ha_synced_at = ? WHERE id = ?",
            (ha_item_id, now, task_id)
        )

    # === Statistics ===

    def get_task_count(self, status: TaskStatus | None = None) -> int:
        """Get count of tasks, optionally filtered by status."""
        if status:
            row = self.db.fetchone(
                "SELECT COUNT(*) as count FROM tasks WHERE status = ?",
                (status.value,)
            )
        else:
            row = self.db.fetchone("SELECT COUNT(*) as count FROM tasks")

        return row["count"] if row else 0

    # === Helper Methods ===

    def _row_to_task(self, row) -> Task:
        """Convert a database row to a Task object."""
        return Task(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            priority=Priority(row["priority"]),
            status=TaskStatus(row["status"]),
            project_id=row["project_id"],
            project_name=row["project_name"] if "project_name" in row.keys() else None,
            due_date=row["due_date"],
            reminder_at=row["reminder_at"],
            reminder_sent=bool(row["reminder_sent"]),
            ha_list_name=row["ha_list_name"],
            ha_item_id=row["ha_item_id"],
            ha_synced_at=row["ha_synced_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            completed_at=row["completed_at"],
        )

    def _row_to_project(self, row) -> Project:
        """Convert a database row to a Project object."""
        return Project(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            color=row["color"],
            created_at=row["created_at"],
            archived=bool(row["archived"]),
        )
