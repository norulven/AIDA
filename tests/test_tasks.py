import tempfile
from pathlib import Path

from src.memory.database import MemoryDatabase
from src.tasks.store import TaskStore
from src.tasks.models import Priority

def test_create_task_with_string_priority():
    """Test creating a task with string priority (regression test)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = MemoryDatabase(db_path)
        store = TaskStore(db)

        # Test creating with string "high"
        task = store.create_task(title="Test Task", priority="high")
        
        assert task.priority == Priority.HIGH
        assert isinstance(task.priority, Priority)
        
        # Test creating with string "medium"
        task_med = store.create_task(title="Test Task 2", priority="medium")
        assert task_med.priority == Priority.MEDIUM

        # Test creating with Enum (standard case)
        task_enum = store.create_task(title="Test Task 3", priority=Priority.LOW)
        assert task_enum.priority == Priority.LOW

        db.close()
