"""Context builder for LLM memory injection."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.memory.conversation import ConversationStore
    from src.memory.embeddings import EmbeddingStore
    from src.memory.facts import UserFactsStore


@dataclass
class MemoryContext:
    """Context to inject into LLM prompts."""

    user_facts: str
    relevant_history: str
    session_summary: str

    def to_system_prompt_addition(self) -> str:
        """Format as system prompt addition."""
        parts = []

        if self.user_facts:
            parts.append(self.user_facts)

        if self.relevant_history:
            parts.append(f"\nRelevant past conversations:\n{self.relevant_history}")

        if self.session_summary:
            parts.append(f"\nCurrent conversation summary:\n{self.session_summary}")

        return "\n".join(parts)

    def is_empty(self) -> bool:
        """Check if context is empty."""
        return not (self.user_facts or self.relevant_history or self.session_summary)


class ContextBuilder:
    """Builds context from memory for LLM injection."""

    def __init__(
        self,
        conversation_store: "ConversationStore",
        facts_store: "UserFactsStore",
        embedding_store: "EmbeddingStore"
    ):
        self.conversations = conversation_store
        self.facts = facts_store
        self.embeddings = embedding_store

    def build_context(
        self,
        current_message: str,
        session_id: str | None = None,
        include_facts: bool = True,
        include_semantic: bool = True,
        max_semantic_results: int = 3,
        min_score: float = 0.4
    ) -> MemoryContext:
        """Build context for the current message."""
        user_facts = ""
        relevant_history = ""
        session_summary = ""

        # Get user facts
        if include_facts:
            user_facts = self.facts.format_facts_for_context()

        # Get semantically relevant past messages
        if include_semantic and self.embeddings.is_available():
            try:
                results = self.embeddings.search(
                    query=current_message,
                    k=max_semantic_results,
                    min_score=min_score
                )

                # Filter out messages from current session
                if session_id:
                    results = [r for r in results if r.session_id != session_id]

                if results:
                    lines = []
                    for r in results:
                        timestamp_str = ""
                        if r.timestamp:
                            timestamp_str = f" ({r.timestamp.strftime('%Y-%m-%d')})"
                        lines.append(f"- {r.content[:200]}...{timestamp_str}")

                    relevant_history = "\n".join(lines)
            except Exception:
                pass

        return MemoryContext(
            user_facts=user_facts,
            relevant_history=relevant_history,
            session_summary=session_summary
        )

    def get_conversation_history(
        self,
        session_id: str,
        max_messages: int = 20
    ) -> list[dict]:
        """Get formatted conversation history for LLM."""
        messages = self.conversations.get_recent_messages(
            session_id=session_id,
            count=max_messages
        )

        return [
            {
                "role": msg.role,
                "content": msg.content,
                "images": msg.images if msg.images else None
            }
            for msg in messages
        ]

    def summarize_session(self, session_id: str) -> str:
        """Create a summary of a session for context.

        This is a simple implementation that takes key messages.
        Could be enhanced with LLM-based summarization.
        """
        messages = self.conversations.get_messages(session_id)

        if len(messages) <= 4:
            return ""

        # Take first and last few messages
        summary_parts = []

        # First user message (topic)
        for msg in messages:
            if msg.role == "user":
                summary_parts.append(f"Started with: {msg.content[:100]}")
                break

        # Last exchange
        last_messages = messages[-4:]
        for msg in last_messages:
            if msg.role == "user":
                summary_parts.append(f"Recently discussed: {msg.content[:100]}")
                break

        return " | ".join(summary_parts)
