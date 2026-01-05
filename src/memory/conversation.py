"""Conversation history storage for AIDA."""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

if TYPE_CHECKING:
    from src.memory.database import MemoryDatabase


@dataclass
class Session:
    """A conversation session."""

    id: str
    title: str | None
    created_at: datetime
    updated_at: datetime
    is_active: bool = False


@dataclass
class StoredMessage:
    """A stored message in a conversation."""

    id: int
    session_id: str
    role: str
    content: str
    images: list[str] = field(default_factory=list)
    timestamp: datetime | None = None
    embedding_id: int | None = None


class ConversationStore(QObject):
    """Manages conversation sessions and message history."""

    session_created = Signal(str)
    session_loaded = Signal(str)
    message_added = Signal(int)

    def __init__(self, db: "MemoryDatabase"):
        super().__init__()
        self.db = db

    def create_session(self, title: str | None = None) -> Session:
        """Create a new conversation session."""
        session_id = str(uuid.uuid4())
        now = datetime.now()

        # Deactivate other sessions
        self.db.execute("UPDATE sessions SET is_active = 0 WHERE is_active = 1")

        # Create new session
        self.db.execute(
            """INSERT INTO sessions (id, title, created_at, updated_at, is_active)
               VALUES (?, ?, ?, ?, 1)""",
            (session_id, title, now, now)
        )

        session = Session(
            id=session_id,
            title=title,
            created_at=now,
            updated_at=now,
            is_active=True
        )

        self.session_created.emit(session_id)
        return session

    def get_session(self, session_id: str) -> Session | None:
        """Get a session by ID."""
        row = self.db.fetchone(
            "SELECT * FROM sessions WHERE id = ?",
            (session_id,)
        )

        if row is None:
            return None

        return Session(
            id=row["id"],
            title=row["title"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            is_active=bool(row["is_active"])
        )

    def get_active_session(self) -> Session | None:
        """Get the currently active session."""
        row = self.db.fetchone(
            "SELECT * FROM sessions WHERE is_active = 1"
        )

        if row is None:
            return None

        return Session(
            id=row["id"],
            title=row["title"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            is_active=True
        )

    def set_active_session(self, session_id: str) -> None:
        """Set a session as active (deactivates others)."""
        self.db.execute("UPDATE sessions SET is_active = 0 WHERE is_active = 1")
        self.db.execute(
            "UPDATE sessions SET is_active = 1 WHERE id = ?",
            (session_id,)
        )
        self.session_loaded.emit(session_id)

    def list_sessions(self, limit: int = 50, offset: int = 0) -> list[Session]:
        """List recent sessions."""
        rows = self.db.fetchall(
            """SELECT * FROM sessions
               ORDER BY updated_at DESC
               LIMIT ? OFFSET ?""",
            (limit, offset)
        )

        return [
            Session(
                id=row["id"],
                title=row["title"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                is_active=bool(row["is_active"])
            )
            for row in rows
        ]

    def delete_session(self, session_id: str) -> None:
        """Delete a session and all its messages."""
        self.db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))

    def update_session_title(self, session_id: str, title: str) -> None:
        """Update a session's title."""
        self.db.execute(
            "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
            (title, datetime.now(), session_id)
        )

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        images: list[str] | None = None
    ) -> StoredMessage:
        """Add a message to a session."""
        now = datetime.now()
        images_json = json.dumps(images) if images else None

        with self.db.connection() as conn:
            cursor = conn.execute(
                """INSERT INTO messages (session_id, role, content, images, timestamp)
                   VALUES (?, ?, ?, ?, ?)""",
                (session_id, role, content, images_json, now)
            )
            message_id = cursor.lastrowid

            # Update session updated_at
            conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (now, session_id)
            )

        message = StoredMessage(
            id=message_id,
            session_id=session_id,
            role=role,
            content=content,
            images=images or [],
            timestamp=now
        )

        self.message_added.emit(message_id)
        return message

    def get_messages(
        self,
        session_id: str,
        limit: int | None = None
    ) -> list[StoredMessage]:
        """Get all messages for a session."""
        query = """SELECT * FROM messages
                   WHERE session_id = ?
                   ORDER BY timestamp ASC"""
        params: tuple = (session_id,)

        if limit is not None:
            query += " LIMIT ?"
            params = (session_id, limit)

        rows = self.db.fetchall(query, params)

        return [
            StoredMessage(
                id=row["id"],
                session_id=row["session_id"],
                role=row["role"],
                content=row["content"],
                images=json.loads(row["images"]) if row["images"] else [],
                timestamp=row["timestamp"],
                embedding_id=row["embedding_id"]
            )
            for row in rows
        ]

    def get_recent_messages(
        self,
        session_id: str,
        count: int = 20
    ) -> list[StoredMessage]:
        """Get the N most recent messages from a session."""
        rows = self.db.fetchall(
            """SELECT * FROM (
                   SELECT * FROM messages
                   WHERE session_id = ?
                   ORDER BY timestamp DESC
                   LIMIT ?
               ) ORDER BY timestamp ASC""",
            (session_id, count)
        )

        return [
            StoredMessage(
                id=row["id"],
                session_id=row["session_id"],
                role=row["role"],
                content=row["content"],
                images=json.loads(row["images"]) if row["images"] else [],
                timestamp=row["timestamp"],
                embedding_id=row["embedding_id"]
            )
            for row in rows
        ]

    def search_messages(
        self,
        query: str,
        session_id: str | None = None
    ) -> list[StoredMessage]:
        """Full-text search across messages."""
        search_pattern = f"%{query}%"

        if session_id:
            rows = self.db.fetchall(
                """SELECT * FROM messages
                   WHERE session_id = ? AND content LIKE ?
                   ORDER BY timestamp DESC
                   LIMIT 50""",
                (session_id, search_pattern)
            )
        else:
            rows = self.db.fetchall(
                """SELECT * FROM messages
                   WHERE content LIKE ?
                   ORDER BY timestamp DESC
                   LIMIT 50""",
                (search_pattern,)
            )

        return [
            StoredMessage(
                id=row["id"],
                session_id=row["session_id"],
                role=row["role"],
                content=row["content"],
                images=json.loads(row["images"]) if row["images"] else [],
                timestamp=row["timestamp"],
                embedding_id=row["embedding_id"]
            )
            for row in rows
        ]

    def update_embedding_id(self, message_id: int, embedding_id: int) -> None:
        """Update the embedding ID for a message."""
        self.db.execute(
            "UPDATE messages SET embedding_id = ? WHERE id = ?",
            (embedding_id, message_id)
        )

    def get_message_count(self, session_id: str) -> int:
        """Get the number of messages in a session."""
        row = self.db.fetchone(
            "SELECT COUNT(*) as count FROM messages WHERE session_id = ?",
            (session_id,)
        )
        return row["count"] if row else 0

    def generate_session_title(self, session_id: str) -> str | None:
        """Generate a title from the first user message."""
        row = self.db.fetchone(
            """SELECT content FROM messages
               WHERE session_id = ? AND role = 'user'
               ORDER BY timestamp ASC
               LIMIT 1""",
            (session_id,)
        )

        if row is None:
            return None

        content = row["content"]
        # Take first 50 chars or first sentence
        if len(content) <= 50:
            title = content
        else:
            # Find first sentence end
            for end in [". ", "? ", "! "]:
                pos = content.find(end)
                if 0 < pos < 50:
                    title = content[:pos + 1]
                    break
            else:
                title = content[:47] + "..."

        self.update_session_title(session_id, title)
        return title
