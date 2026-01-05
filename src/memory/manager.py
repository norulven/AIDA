"""Unified memory manager for AIDA."""

import threading
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from src.memory.database import MemoryDatabase
from src.memory.conversation import ConversationStore, Session
from src.memory.facts import UserFactsStore
from src.memory.embeddings import EmbeddingStore
from src.memory.context import ContextBuilder, MemoryContext


class MemoryManager(QObject):
    """Unified interface for all memory operations."""

    memory_ready = Signal()
    memory_error = Signal(str)

    def __init__(
        self,
        data_dir: Path | None = None,
        cache_dir: Path | None = None
    ):
        super().__init__()

        if data_dir is None:
            data_dir = Path.home() / ".local/share/aida"
        if cache_dir is None:
            cache_dir = Path.home() / ".cache/aida"

        self.data_dir = data_dir
        self.cache_dir = cache_dir

        # Initialize database
        self._db = MemoryDatabase(data_dir / "memory.db")

        # Initialize stores
        self._conversations = ConversationStore(self._db)
        self._facts = UserFactsStore(self._db)
        self._embeddings = EmbeddingStore(
            db=self._db,
            data_dir=data_dir / "embeddings",
            cache_dir=cache_dir / "embedding_model"
        )

        # Initialize context builder
        self._context = ContextBuilder(
            conversation_store=self._conversations,
            facts_store=self._facts,
            embedding_store=self._embeddings
        )

        # Current session
        self._current_session_id: str | None = None

        # Background thread for embeddings
        self._embedding_queue: list[tuple[int, str, str]] = []
        self._embedding_lock = threading.Lock()

        self.memory_ready.emit()

    @property
    def conversations(self) -> ConversationStore:
        """Access conversation store."""
        return self._conversations

    @property
    def facts(self) -> UserFactsStore:
        """Access facts store."""
        return self._facts

    @property
    def embeddings(self) -> EmbeddingStore:
        """Access embedding store."""
        return self._embeddings

    @property
    def context(self) -> ContextBuilder:
        """Access context builder."""
        return self._context

    @property
    def current_session_id(self) -> str | None:
        """Get current active session ID."""
        return self._current_session_id

    def start_session(self, title: str | None = None) -> str:
        """Start a new conversation session."""
        session = self._conversations.create_session(title=title)
        self._current_session_id = session.id
        return session.id

    def resume_session(self, session_id: str) -> bool:
        """Resume an existing session."""
        session = self._conversations.get_session(session_id)
        if session is None:
            return False

        self._conversations.set_active_session(session_id)
        self._current_session_id = session_id
        return True

    def get_or_create_session(self) -> str:
        """Get active session or create new one."""
        active = self._conversations.get_active_session()
        if active:
            self._current_session_id = active.id
            return active.id

        return self.start_session()

    def add_interaction(
        self,
        user_message: str,
        assistant_response: str,
        images: list[str] | None = None
    ) -> None:
        """Record a complete interaction."""
        if self._current_session_id is None:
            self.get_or_create_session()

        # Store user message
        user_msg = self._conversations.add_message(
            session_id=self._current_session_id,
            role="user",
            content=user_message,
            images=images
        )

        # Store assistant response
        assistant_msg = self._conversations.add_message(
            session_id=self._current_session_id,
            role="assistant",
            content=assistant_response
        )

        # Extract facts from user message
        self._facts.extract_facts_from_message(
            message=user_message,
            source_message_id=user_msg.id
        )

        # Generate title if first message
        msg_count = self._conversations.get_message_count(self._current_session_id)
        if msg_count <= 2:
            self._conversations.generate_session_title(self._current_session_id)

        # Queue embeddings for background processing
        self._queue_embedding(user_msg.id, self._current_session_id, user_message)
        self._queue_embedding(assistant_msg.id, self._current_session_id, assistant_response)

    def _queue_embedding(self, message_id: int, session_id: str, content: str) -> None:
        """Queue a message for embedding generation."""
        if not self._embeddings.is_available():
            return

        with self._embedding_lock:
            self._embedding_queue.append((message_id, session_id, content))

        # Process in background
        threading.Thread(target=self._process_embedding_queue, daemon=True).start()

    def _process_embedding_queue(self) -> None:
        """Process queued embeddings."""
        with self._embedding_lock:
            if not self._embedding_queue:
                return
            items = self._embedding_queue.copy()
            self._embedding_queue.clear()

        for message_id, session_id, content in items:
            try:
                from datetime import datetime
                embedding_id = self._embeddings.add_embedding(
                    message_id=message_id,
                    session_id=session_id,
                    content=content,
                    timestamp=datetime.now()
                )
                self._conversations.update_embedding_id(message_id, embedding_id)
            except Exception as e:
                self.memory_error.emit(f"Embedding error: {e}")

    def get_context_for_message(
        self,
        message: str,
        include_facts: bool = True,
        include_semantic: bool = True,
        max_semantic_results: int = 3
    ) -> str:
        """Get memory context to inject into LLM prompt."""
        context = self._context.build_context(
            current_message=message,
            session_id=self._current_session_id,
            include_facts=include_facts,
            include_semantic=include_semantic,
            max_semantic_results=max_semantic_results
        )

        if context.is_empty():
            return ""

        return context.to_system_prompt_addition()

    def list_recent_sessions(self, limit: int = 20) -> list[Session]:
        """List recent conversation sessions."""
        return self._conversations.list_sessions(limit=limit)

    def search_memory(
        self,
        query: str,
        include_facts: bool = True,
        include_conversations: bool = True
    ) -> dict:
        """Search across all memory types."""
        results = {
            "facts": [],
            "messages": [],
            "semantic": []
        }

        # Search facts
        if include_facts:
            all_facts = self._facts.get_all_facts()
            for category, facts in all_facts.items():
                for fact in facts:
                    if query.lower() in fact.value.lower() or query.lower() in fact.key.lower():
                        results["facts"].append({
                            "category": category,
                            "key": fact.key,
                            "value": fact.value
                        })

        # Search conversation content
        if include_conversations:
            messages = self._conversations.search_messages(query)
            results["messages"] = [
                {
                    "session_id": msg.session_id,
                    "role": msg.role,
                    "content": msg.content[:200],
                    "timestamp": msg.timestamp.isoformat() if msg.timestamp else None
                }
                for msg in messages[:10]
            ]

        # Semantic search
        if include_conversations and self._embeddings.is_available():
            try:
                semantic = self._embeddings.search(query, k=5)
                results["semantic"] = [
                    {
                        "session_id": r.session_id,
                        "content": r.content,
                        "score": r.score,
                        "timestamp": r.timestamp.isoformat() if r.timestamp else None
                    }
                    for r in semantic
                ]
            except Exception:
                pass

        return results

    def get_user_summary(self) -> str:
        """Get a summary of what AIDA knows about the user."""
        facts_str = self._facts.format_facts_for_context()

        session_count = len(self._conversations.list_sessions(limit=1000))
        fact_count = self._facts.get_fact_count()
        embedding_count = self._embeddings.get_embedding_count()

        summary = f"Memory statistics:\n"
        summary += f"- {session_count} conversation sessions\n"
        summary += f"- {fact_count} stored facts\n"
        summary += f"- {embedding_count} semantic embeddings\n"

        if facts_str:
            summary += f"\n{facts_str}"

        return summary

    def clear_all_memory(self) -> None:
        """Clear all stored memory."""
        # Delete all sessions (cascades to messages)
        sessions = self._conversations.list_sessions(limit=10000)
        for session in sessions:
            self._conversations.delete_session(session.id)

        # Clear facts
        self._facts.clear_all_facts()

        # Rebuild empty index
        if self._embeddings.is_available():
            self._embeddings.rebuild_index()

        self._current_session_id = None

    def cleanup(self) -> None:
        """Clean up resources, save pending data."""
        self._embeddings.cleanup()
        self._db.close()
