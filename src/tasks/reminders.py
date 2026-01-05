"""Reminder scheduling and notification service."""

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal, QTimer

from src.tasks.models import Task, Reminder

if TYPE_CHECKING:
    from src.tasks.store import TaskStore


class ReminderService(QObject):
    """Background service for task reminders."""

    reminder_due = Signal(object, object)  # Task, Reminder

    CHECK_INTERVAL_MS = 60_000  # Check every minute

    def __init__(self, store: "TaskStore"):
        super().__init__()
        self._store = store
        self._timer: QTimer | None = None
        self._running = False

    def start(self) -> None:
        """Start the reminder service."""
        if self._timer is not None:
            return

        self._timer = QTimer()
        self._timer.timeout.connect(self._check_reminders)
        self._timer.start(self.CHECK_INTERVAL_MS)
        self._running = True

        # Initial check
        self._check_reminders()

    def stop(self) -> None:
        """Stop the reminder service."""
        if self._timer:
            self._timer.stop()
            self._timer = None
        self._running = False

    def is_running(self) -> bool:
        """Check if service is running."""
        return self._running

    def _check_reminders(self) -> None:
        """Check for due reminders and emit signals."""
        now = datetime.now()
        pending = self._store.get_pending_reminders(before=now)

        for reminder, task in pending:
            # Emit signal
            self.reminder_due.emit(task, reminder)

            # Mark as sent
            self._store.mark_reminder_sent(reminder.id)

            # Handle recurring reminders
            if reminder.reminder_type == "daily":
                next_time = reminder.remind_at + timedelta(days=1)
                self._store.create_reminder(
                    task_id=task.id,
                    remind_at=next_time,
                    reminder_type="daily"
                )
            elif reminder.reminder_type == "weekly":
                next_time = reminder.remind_at + timedelta(weeks=1)
                self._store.create_reminder(
                    task_id=task.id,
                    remind_at=next_time,
                    reminder_type="weekly"
                )

    def schedule_reminder(
        self,
        task_id: int,
        remind_at: datetime,
        reminder_type: str = "once"
    ) -> Reminder:
        """Schedule a new reminder for a task."""
        return self._store.create_reminder(
            task_id=task_id,
            remind_at=remind_at,
            reminder_type=reminder_type
        )

    def schedule_reminder_before_due(
        self,
        task_id: int,
        minutes_before: int = 30
    ) -> Reminder | None:
        """Schedule a reminder X minutes before the task's due date."""
        task = self._store.get_task(task_id)
        if task is None or task.due_date is None:
            return None

        remind_at = task.due_date - timedelta(minutes=minutes_before)
        if remind_at <= datetime.now():
            return None

        return self._store.create_reminder(
            task_id=task_id,
            remind_at=remind_at,
            reminder_type="once"
        )
