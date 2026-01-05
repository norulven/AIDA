"""SQLite database for AIDA memory storage."""

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA_VERSION = 2

SCHEMA = """
-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

-- Conversation sessions
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    title TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active INTEGER DEFAULT 0
);

-- Messages within sessions
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    images TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    embedding_id INTEGER
);

-- User facts and preferences
CREATE TABLE IF NOT EXISTS user_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    source_message_id INTEGER REFERENCES messages(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(category, key)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_facts_category ON user_facts(category);
CREATE INDEX IF NOT EXISTS idx_facts_key ON user_facts(key);
CREATE INDEX IF NOT EXISTS idx_sessions_active ON sessions(is_active);
"""

TASK_SCHEMA = """
-- Projects/Categories for grouping tasks
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    color TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    archived INTEGER DEFAULT 0
);

-- Main tasks table
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    priority TEXT DEFAULT 'medium' CHECK (priority IN ('high', 'medium', 'low')),
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed', 'cancelled')),
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    due_date TIMESTAMP,
    reminder_at TIMESTAMP,
    reminder_sent INTEGER DEFAULT 0,
    ha_list_name TEXT,
    ha_item_id TEXT,
    ha_synced_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- Task reminders for recurring/multiple reminders
CREATE TABLE IF NOT EXISTS task_reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    remind_at TIMESTAMP NOT NULL,
    reminder_type TEXT DEFAULT 'once' CHECK (reminder_type IN ('once', 'daily', 'weekly')),
    sent INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- HA sync log
CREATE TABLE IF NOT EXISTS ha_sync_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ha_list_name TEXT NOT NULL,
    last_sync_at TIMESTAMP NOT NULL,
    sync_direction TEXT CHECK (sync_direction IN ('pull', 'push', 'both')),
    items_synced INTEGER DEFAULT 0
);

-- Task indexes
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority);
CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks(due_date);
CREATE INDEX IF NOT EXISTS idx_tasks_reminder ON tasks(reminder_at, reminder_sent);
CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_tasks_ha_list ON tasks(ha_list_name);
CREATE INDEX IF NOT EXISTS idx_reminders_task ON task_reminders(task_id);
CREATE INDEX IF NOT EXISTS idx_reminders_time ON task_reminders(remind_at, sent);
"""


class MemoryDatabase:
    """Thread-safe SQLite database for AIDA memory."""

    def __init__(self, db_path: Path | None = None):
        """Initialize database.

        Args:
            db_path: Path to database file. Defaults to ~/.local/share/aida/memory.db
        """
        if db_path is None:
            db_path = Path.home() / ".local/share/aida/memory.db"

        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._local = threading.local()
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, "connection"):
            self._local.connection = sqlite3.connect(
                self.db_path,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
                check_same_thread=False,
            )
            self._local.connection.row_factory = sqlite3.Row
            self._local.connection.execute("PRAGMA foreign_keys = ON")
        return self._local.connection

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """Get a connection context manager."""
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def _init_schema(self) -> None:
        """Initialize database schema."""
        with self.connection() as conn:
            # Check current schema version
            try:
                cursor = conn.execute("SELECT version FROM schema_version")
                row = cursor.fetchone()
                current_version = row["version"] if row else 0
            except sqlite3.OperationalError:
                current_version = 0

            if current_version < SCHEMA_VERSION:
                # Apply base schema (memory system)
                conn.executescript(SCHEMA)

                # Version 2: Add task management tables
                if current_version < 2:
                    conn.executescript(TASK_SCHEMA)

                conn.execute(
                    "INSERT OR REPLACE INTO schema_version (version) VALUES (?)",
                    (SCHEMA_VERSION,)
                )

    def execute(
        self,
        query: str,
        params: tuple = ()
    ) -> sqlite3.Cursor:
        """Execute a query with parameters."""
        with self.connection() as conn:
            return conn.execute(query, params)

    def executemany(
        self,
        query: str,
        params_list: list[tuple]
    ) -> None:
        """Execute a query with multiple parameter sets."""
        with self.connection() as conn:
            conn.executemany(query, params_list)

    def fetchone(
        self,
        query: str,
        params: tuple = ()
    ) -> sqlite3.Row | None:
        """Execute query and fetch one result."""
        with self.connection() as conn:
            cursor = conn.execute(query, params)
            return cursor.fetchone()

    def fetchall(
        self,
        query: str,
        params: tuple = ()
    ) -> list[sqlite3.Row]:
        """Execute query and fetch all results."""
        with self.connection() as conn:
            cursor = conn.execute(query, params)
            return cursor.fetchall()

    def close(self) -> None:
        """Close the database connection."""
        if hasattr(self._local, "connection"):
            self._local.connection.close()
            del self._local.connection
