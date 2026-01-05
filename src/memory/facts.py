"""User facts and preferences storage for AIDA."""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

if TYPE_CHECKING:
    from src.memory.database import MemoryDatabase


@dataclass
class UserFact:
    """A fact about the user."""

    id: int
    category: str
    key: str
    value: str
    confidence: float
    source_message_id: int | None
    created_at: datetime
    updated_at: datetime


class UserFactsStore(QObject):
    """Stores and retrieves facts about the user."""

    fact_added = Signal(str, str)
    fact_updated = Signal(str, str)

    # Fact categories
    CATEGORY_PERSONAL = "personal"
    CATEGORY_PREFERENCE = "preference"
    CATEGORY_HABIT = "habit"
    CATEGORY_CONTEXT = "context"
    CATEGORY_WORK = "work"

    def __init__(self, db: "MemoryDatabase"):
        super().__init__()
        self.db = db

    def set_fact(
        self,
        category: str,
        key: str,
        value: str,
        confidence: float = 1.0,
        source_message_id: int | None = None
    ) -> UserFact:
        """Set or update a user fact."""
        now = datetime.now()

        existing = self.get_fact(category, key)

        if existing:
            # Update existing fact
            self.db.execute(
                """UPDATE user_facts
                   SET value = ?, confidence = ?, source_message_id = ?, updated_at = ?
                   WHERE category = ? AND key = ?""",
                (value, confidence, source_message_id, now, category, key)
            )
            self.fact_updated.emit(category, key)

            return UserFact(
                id=existing.id,
                category=category,
                key=key,
                value=value,
                confidence=confidence,
                source_message_id=source_message_id,
                created_at=existing.created_at,
                updated_at=now
            )
        else:
            # Insert new fact
            with self.db.connection() as conn:
                cursor = conn.execute(
                    """INSERT INTO user_facts
                       (category, key, value, confidence, source_message_id, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (category, key, value, confidence, source_message_id, now, now)
                )
                fact_id = cursor.lastrowid

            self.fact_added.emit(category, key)

            return UserFact(
                id=fact_id,
                category=category,
                key=key,
                value=value,
                confidence=confidence,
                source_message_id=source_message_id,
                created_at=now,
                updated_at=now
            )

    def get_fact(self, category: str, key: str) -> UserFact | None:
        """Get a specific fact."""
        row = self.db.fetchone(
            "SELECT * FROM user_facts WHERE category = ? AND key = ?",
            (category, key)
        )

        if row is None:
            return None

        return UserFact(
            id=row["id"],
            category=row["category"],
            key=row["key"],
            value=row["value"],
            confidence=row["confidence"],
            source_message_id=row["source_message_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )

    def get_facts_by_category(self, category: str) -> list[UserFact]:
        """Get all facts in a category."""
        rows = self.db.fetchall(
            "SELECT * FROM user_facts WHERE category = ? ORDER BY key",
            (category,)
        )

        return [
            UserFact(
                id=row["id"],
                category=row["category"],
                key=row["key"],
                value=row["value"],
                confidence=row["confidence"],
                source_message_id=row["source_message_id"],
                created_at=row["created_at"],
                updated_at=row["updated_at"]
            )
            for row in rows
        ]

    def get_all_facts(self) -> dict[str, list[UserFact]]:
        """Get all facts grouped by category."""
        rows = self.db.fetchall(
            "SELECT * FROM user_facts ORDER BY category, key"
        )

        facts: dict[str, list[UserFact]] = {}
        for row in rows:
            fact = UserFact(
                id=row["id"],
                category=row["category"],
                key=row["key"],
                value=row["value"],
                confidence=row["confidence"],
                source_message_id=row["source_message_id"],
                created_at=row["created_at"],
                updated_at=row["updated_at"]
            )
            if fact.category not in facts:
                facts[fact.category] = []
            facts[fact.category].append(fact)

        return facts

    def delete_fact(self, category: str, key: str) -> bool:
        """Delete a fact."""
        with self.db.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM user_facts WHERE category = ? AND key = ?",
                (category, key)
            )
            return cursor.rowcount > 0

    def clear_all_facts(self) -> None:
        """Delete all facts."""
        self.db.execute("DELETE FROM user_facts")

    def format_facts_for_context(self) -> str:
        """Format all facts as text for LLM system prompt injection."""
        facts = self.get_all_facts()

        if not facts:
            return ""

        lines = []

        # Personal info
        if self.CATEGORY_PERSONAL in facts:
            personal = facts[self.CATEGORY_PERSONAL]
            if personal:
                lines.append("About the user:")
                for fact in personal:
                    lines.append(f"- {fact.key}: {fact.value}")

        # Preferences
        if self.CATEGORY_PREFERENCE in facts:
            prefs = facts[self.CATEGORY_PREFERENCE]
            if prefs:
                lines.append("\nPreferences:")
                for fact in prefs:
                    lines.append(f"- {fact.key}: {fact.value}")

        # Habits
        if self.CATEGORY_HABIT in facts:
            habits = facts[self.CATEGORY_HABIT]
            if habits:
                lines.append("\nHabits and routines:")
                for fact in habits:
                    lines.append(f"- {fact.key}: {fact.value}")

        # Work/projects
        if self.CATEGORY_WORK in facts:
            work = facts[self.CATEGORY_WORK]
            if work:
                lines.append("\nWork and projects:")
                for fact in work:
                    lines.append(f"- {fact.key}: {fact.value}")

        # Context
        if self.CATEGORY_CONTEXT in facts:
            context = facts[self.CATEGORY_CONTEXT]
            if context:
                lines.append("\nContext:")
                for fact in context:
                    lines.append(f"- {fact.key}: {fact.value}")

        return "\n".join(lines)

    def extract_facts_from_message(
        self,
        message: str,
        source_message_id: int | None = None
    ) -> list[tuple[str, str, str]]:
        """
        Extract potential facts from a user message using patterns.

        Returns list of (category, key, value) tuples.
        """
        extracted: list[tuple[str, str, str]] = []
        message_lower = message.lower()

        # Name patterns
        name_patterns = [
            r"(?:my name is|i'm|i am|call me) ([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)(?:\s+and|\s*[,.]|$)",
            r"(?:jeg heter|kall meg) ([A-ZÆØÅ][a-zæøå]+(?:\s+[A-ZÆØÅ][a-zæøå]+)?)(?:\s+og|\s*[,.]|$)",
        ]
        for pattern in name_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                if name.lower() not in ["i", "a", "the"]:
                    extracted.append((self.CATEGORY_PERSONAL, "name", name))
                    break

        # Location patterns
        location_patterns = [
            r"(?:i live in|i'm from|i am from) ([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
            r"(?:jeg bor i|jeg er fra) ([A-ZÆØÅ][a-zæøå]+(?:\s+[A-ZÆØÅ][a-zæøå]+)*)",
        ]
        for pattern in location_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                location = match.group(1).strip()
                extracted.append((self.CATEGORY_PERSONAL, "location", location))
                break

        # Job/occupation patterns
        job_patterns = [
            r"(?:i work as|i am a|i'm a|my job is) (?:a |an )?([a-z]+(?:\s+[a-z]+)*)",
            r"(?:jeg jobber som|jeg er) (?:en )?([a-zæøå]+(?:\s+[a-zæøå]+)*)",
        ]
        for pattern in job_patterns:
            match = re.search(pattern, message_lower)
            if match:
                job = match.group(1).strip()
                # Filter out common non-job phrases
                if job not in ["here", "there", "good", "fine", "ok", "sure"]:
                    extracted.append((self.CATEGORY_WORK, "occupation", job))
                    break

        # Preference patterns (likes)
        like_patterns = [
            r"(?:i (?:really )?(?:like|love|enjoy|prefer)) ([a-z]+(?:\s+[a-z]+)*)",
            r"(?:jeg (?:liker|elsker)) ([a-zæøå]+(?:\s+[a-zæøå]+)*)",
        ]
        for pattern in like_patterns:
            match = re.search(pattern, message_lower)
            if match:
                thing = match.group(1).strip()
                if len(thing) > 2 and thing not in ["it", "that", "this"]:
                    extracted.append((self.CATEGORY_PREFERENCE, f"likes_{thing}", thing))
                    break

        # Preference patterns (dislikes)
        dislike_patterns = [
            r"(?:i (?:don't|do not|hate|dislike)) ([a-z]+(?:\s+[a-z]+)*)",
            r"(?:jeg (?:liker ikke|hater)) ([a-zæøå]+(?:\s+[a-zæøå]+)*)",
        ]
        for pattern in dislike_patterns:
            match = re.search(pattern, message_lower)
            if match:
                thing = match.group(1).strip()
                if len(thing) > 2 and thing not in ["it", "that", "this"]:
                    extracted.append((self.CATEGORY_PREFERENCE, f"dislikes_{thing}", thing))
                    break

        # Store extracted facts
        for category, key, value in extracted:
            self.set_fact(
                category=category,
                key=key,
                value=value,
                confidence=0.8,
                source_message_id=source_message_id
            )

        return extracted

    def get_fact_count(self) -> int:
        """Get total number of stored facts."""
        row = self.db.fetchone("SELECT COUNT(*) as count FROM user_facts")
        return row["count"] if row else 0
