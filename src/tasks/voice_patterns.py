"""Voice command patterns for task management."""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from src.tasks.models import Priority


@dataclass
class ParsedTaskCommand:
    """Result of parsing a task-related voice command."""

    action: str  # add, complete, list, delete
    title: str | None = None
    priority: Priority | None = None
    due_date: datetime | None = None
    project: str | None = None
    reminder: datetime | None = None
    ha_list: str | None = None
    filter_priority: Priority | None = None


class TaskVoiceParser:
    """Parse natural language task commands."""

    # Add task patterns (English and Norwegian)
    ADD_PATTERNS = [
        r"(?:add|create|new) (?:a )?task (?:to )?(?:do )?(.+)",
        r"(?:add|put) (.+?) (?:to|on) (?:my )?(?:todo|task|shopping|grocery)(?:s| list)?",
        r"(?:add) (.+?) to (?:the )?(?:shopping|grocery) list",
        r"(?:remind me to|i need to|don't forget to|gotta) (.+)",
        r"(?:legg til|ny) (?:oppgave )?(.+)",  # Norwegian
        r"(?:husk meg på|ikke glem) (.+)",  # Norwegian
    ]

    # Complete task patterns
    COMPLETE_PATTERNS = [
        r"(?:complete|finish|done(?: with)?|mark (?:as )?(?:done|complete)|check off) (?:task )?(.+)",
        r"(?:i (?:finished|completed|did|done)) (.+)",
        r"(?:ferdig med|fullført) (.+)",  # Norwegian
    ]

    # List task patterns
    LIST_PATTERNS = [
        r"(?:what(?:'s| is) on my|show(?: me)?(?: my)?|list(?: my)?|read(?: my)?) ?(?:todo|task|to-do)(?:s| list)?",
        r"what (?:do i (?:need|have) to do|are my tasks)",
        r"(?:hva (?:er|skal|må) jeg (?:gjøre|huske)|vis (?:mine )?oppgaver)",  # Norwegian
    ]

    # Priority keywords
    PRIORITY_HIGH = [
        "high priority", "important", "urgent", "asap", "critical",
        "høy prioritet", "viktig", "haster",
    ]
    PRIORITY_LOW = [
        "low priority", "not important", "whenever", "eventually",
        "lav prioritet", "ikke viktig", "når som helst",
    ]

    # Time patterns with their delta functions
    TIME_PATTERNS = [
        (r"\btoday\b|\bi dag\b", lambda: _end_of_day(0)),
        (r"\btomorrow\b|\bi morgen\b", lambda: _end_of_day(1)),
        (r"\bnext week\b|\bneste uke\b", lambda: datetime.now() + timedelta(weeks=1)),
        (r"\bthis weekend\b", lambda: _next_weekend()),
        (r"\bin an? hour\b|\bom en time\b", lambda: datetime.now() + timedelta(hours=1)),
        (r"\bin (\d+) minutes?\b|\bom (\d+) minutt(?:er)?\b", lambda m: datetime.now() + timedelta(minutes=int(m))),
        (r"\bin (\d+) hours?\b|\bom (\d+) time(?:r)?\b", lambda m: datetime.now() + timedelta(hours=int(m))),
        (r"\bin (\d+) days?\b|\bom (\d+) dag(?:er)?\b", lambda m: datetime.now() + timedelta(days=int(m))),
    ]

    # Shopping/grocery list keywords -> HA Handleliste
    SHOPPING_KEYWORDS = [
        "shopping list", "grocery", "groceries", "handleliste", "handle",
        "buy", "kjøp", "butikk",
    ]

    # Daily tasks keywords -> HA Dag til dag
    DAILY_KEYWORDS = [
        "daily", "dag til dag", "today's list", "dagens",
    ]

    def parse(self, message: str) -> ParsedTaskCommand | None:
        """Parse a message for task commands."""
        message_lower = message.lower()

        # Try list patterns first (most specific)
        for pattern in self.LIST_PATTERNS:
            if re.search(pattern, message_lower):
                cmd = ParsedTaskCommand(action="list")
                # Check for priority filter
                if any(kw in message_lower for kw in ["high priority", "viktig", "important"]):
                    cmd.filter_priority = Priority.HIGH
                elif any(kw in message_lower for kw in ["low priority", "lav"]):
                    cmd.filter_priority = Priority.LOW
                return cmd

        # Try complete patterns
        for pattern in self.COMPLETE_PATTERNS:
            match = re.search(pattern, message_lower)
            if match:
                title = match.group(1).strip()
                return ParsedTaskCommand(action="complete", title=title)

        # Try add patterns
        for pattern in self.ADD_PATTERNS:
            match = re.search(pattern, message_lower)
            if match:
                return self._parse_add_command(match.group(1), message)

        return None

    def _parse_add_command(self, raw_title: str, full_message: str) -> ParsedTaskCommand:
        """Parse an add task command with optional modifiers."""
        title = raw_title.strip()
        message_lower = full_message.lower()

        cmd = ParsedTaskCommand(action="add", title=title)

        # Extract priority
        if any(kw in message_lower for kw in self.PRIORITY_HIGH):
            cmd.priority = Priority.HIGH
        elif any(kw in message_lower for kw in self.PRIORITY_LOW):
            cmd.priority = Priority.LOW

        # Extract time/deadline
        for pattern, time_func in self.TIME_PATTERNS:
            match = re.search(pattern, message_lower)
            if match:
                groups = [g for g in match.groups() if g is not None] if match.groups() else []
                if groups:
                    cmd.due_date = time_func(groups[0])
                else:
                    cmd.due_date = time_func()

                # If "remind" is in message, also set reminder
                if "remind" in message_lower or "husk" in message_lower:
                    cmd.reminder = cmd.due_date
                break

        # Extract project (e.g., "for project X", "in project X")
        project_match = re.search(r"(?:for|in|til) (?:project|prosjekt) (\w+)", message_lower)
        if project_match:
            cmd.project = project_match.group(1)

        # Extract HA list
        if any(kw in message_lower for kw in self.SHOPPING_KEYWORDS):
            cmd.ha_list = "Handleliste"
            # Clean up title - remove shopping keywords
            title = re.sub(r"\b(?:to )?(?:the )?shopping list\b", "", title, flags=re.IGNORECASE)
            title = re.sub(r"\b(?:på )?handleliste(?:n)?\b", "", title, flags=re.IGNORECASE)
            cmd.title = title.strip()

        elif any(kw in message_lower for kw in self.DAILY_KEYWORDS):
            cmd.ha_list = "Dag til dag"

        # Clean up title - remove time phrases and priority phrases
        clean_title = cmd.title
        for pattern, _ in self.TIME_PATTERNS:
            clean_title = re.sub(pattern, "", clean_title, flags=re.IGNORECASE)
        for phrase in self.PRIORITY_HIGH + self.PRIORITY_LOW:
            clean_title = re.sub(rf"\b{phrase}\b", "", clean_title, flags=re.IGNORECASE)
        clean_title = re.sub(r"\s+", " ", clean_title).strip()

        if clean_title:
            cmd.title = clean_title

        return cmd


def _end_of_day(days_from_now: int) -> datetime:
    """Get end of day (23:59) for N days from now."""
    target = datetime.now() + timedelta(days=days_from_now)
    return target.replace(hour=23, minute=59, second=59, microsecond=0)


def _next_weekend() -> datetime:
    """Get next Saturday."""
    now = datetime.now()
    days_ahead = 5 - now.weekday()  # Saturday is 5
    if days_ahead <= 0:
        days_ahead += 7
    return (now + timedelta(days=days_ahead)).replace(hour=12, minute=0, second=0, microsecond=0)
