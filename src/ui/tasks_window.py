"""Task management window for Aida."""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QLineEdit,
    QLabel,
    QComboBox,
    QInputDialog,
    QMessageBox,
)
from PySide6.QtCore import Qt

from src.tasks.models import Task, Priority
from src.tasks.store import TaskStore


class TasksWindow(QDialog):
    """Window for viewing and managing tasks."""

    def __init__(self, store: TaskStore, parent=None):
        super().__init__(parent)
        self.store = store

        self.setWindowTitle("Tasks")
        self.setMinimumWidth(450)
        self.setMinimumHeight(400)

        self._setup_ui()
        self._connect_signals()
        self._refresh_tasks()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Task list
        layout.addWidget(QLabel("Your Tasks:"))

        self._task_list = QListWidget()
        self._task_list.setAlternatingRowColors(True)
        layout.addWidget(self._task_list)

        # Action buttons
        button_layout = QHBoxLayout()

        self._done_btn = QPushButton("Mark Done")
        self._done_btn.clicked.connect(self._mark_done)
        button_layout.addWidget(self._done_btn)

        self._edit_btn = QPushButton("Edit")
        self._edit_btn.clicked.connect(self._edit_task)
        button_layout.addWidget(self._edit_btn)

        self._delete_btn = QPushButton("Delete")
        self._delete_btn.clicked.connect(self._delete_task)
        button_layout.addWidget(self._delete_btn)

        layout.addLayout(button_layout)

        # Quick add section
        layout.addWidget(QLabel("Quick Add:"))

        add_layout = QHBoxLayout()

        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText("Task title...")
        self._title_edit.returnPressed.connect(self._add_task)
        add_layout.addWidget(self._title_edit)

        self._priority_combo = QComboBox()
        self._priority_combo.addItem("Medium", Priority.MEDIUM)
        self._priority_combo.addItem("High", Priority.HIGH)
        self._priority_combo.addItem("Low", Priority.LOW)
        self._priority_combo.setFixedWidth(80)
        add_layout.addWidget(self._priority_combo)

        self._add_btn = QPushButton("Add")
        self._add_btn.clicked.connect(self._add_task)
        add_layout.addWidget(self._add_btn)

        layout.addLayout(add_layout)

        # Close button
        close_layout = QHBoxLayout()
        close_layout.addStretch()
        self._close_btn = QPushButton("Close")
        self._close_btn.clicked.connect(self.accept)
        close_layout.addWidget(self._close_btn)
        layout.addLayout(close_layout)

    def _connect_signals(self) -> None:
        """Connect store signals for auto-refresh."""
        self.store.task_created.connect(self._refresh_tasks)
        self.store.task_updated.connect(self._refresh_tasks)
        self.store.task_completed.connect(self._refresh_tasks)
        self.store.task_deleted.connect(self._refresh_tasks)

        # UI signals
        self._task_list.itemSelectionChanged.connect(self._update_button_states)

    def _update_button_states(self) -> None:
        """Update the enabled state of action buttons."""
        has_selection = self._task_list.currentRow() >= 0
        self._done_btn.setEnabled(has_selection)
        self._edit_btn.setEnabled(has_selection)
        self._delete_btn.setEnabled(has_selection)

    def _refresh_tasks(self) -> None:
        """Refresh the task list."""
        self._task_list.clear()

        tasks = self.store.get_pending_tasks()

        for task in tasks:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, task.id)

            # Build display text
            text = task.title

            if task.priority == Priority.HIGH:
                text = f"[HIGH] {text}"
            elif task.priority == Priority.LOW:
                text = f"[low] {text}"

            if task.due_date:
                due_str = task.due_date.strftime("%b %d")
                text += f"  (due: {due_str})"

            if task.is_overdue:
                text += " - OVERDUE!"

            item.setText(text)

            # Color coding
            if task.priority == Priority.HIGH:
                item.setForeground(Qt.GlobalColor.red)
            elif task.is_overdue:
                item.setForeground(Qt.GlobalColor.darkRed)

            self._task_list.addItem(item)

        self._update_button_states()

    def _get_selected_task_id(self) -> int | None:
        """Get the ID of the selected task."""
        current = self._task_list.currentItem()
        if current:
            return current.data(Qt.ItemDataRole.UserRole)
        return None

    def _mark_done(self) -> None:
        """Mark the selected task as done."""
        task_id = self._get_selected_task_id()
        if task_id:
            self.store.complete_task(task_id)

    def _edit_task(self) -> None:
        """Edit the selected task."""
        task_id = self._get_selected_task_id()
        if not task_id:
            return

        task = self.store.get_task(task_id)
        if not task:
            return

        # Simple edit dialog - just title for now
        new_title, ok = QInputDialog.getText(
            self,
            "Edit Task",
            "Task title:",
            text=task.title
        )

        if ok and new_title.strip():
            self.store.update_task(task_id, title=new_title.strip())

    def _delete_task(self) -> None:
        """Delete the selected task."""
        task_id = self._get_selected_task_id()
        if not task_id:
            return

        task = self.store.get_task(task_id)
        if not task:
            return

        reply = QMessageBox.question(
            self,
            "Delete Task",
            f"Delete '{task.title}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.store.delete_task(task_id)

    def _add_task(self) -> None:
        """Add a new task."""
        title = self._title_edit.text().strip()
        if not title:
            return

        priority = self._priority_combo.currentData()

        self.store.create_task(title=title, priority=priority)

        self._title_edit.clear()
        self._priority_combo.setCurrentIndex(0)  # Reset to Medium
