"""Long-term memory: a few explicit facts, kept separate from chat history.

Conversation turns are transcript; memories are things worth carrying into
future conversations. Version one keeps this deliberately explicit — the user
says what to remember, so nothing is inferred or silently retained.
"""
from __future__ import annotations

import re

from core.persistence.database import Database
from core.utils.logger import get_logger

log = get_logger("memory")

MAX_MEMORY_CHARS = 300

# "remember that I use dark mode", "remember: I use dark mode", "note that ..."
_REMEMBER = re.compile(
    r"^\s*(?:please\s+)?(?:remember|note|keep in mind)\b[\s:,-]*(?:that\s+)?(.+)$",
    re.IGNORECASE | re.DOTALL,
)
_FORGET_ALL = re.compile(
    r"^\s*(?:please\s+)?forget\s+(?:everything|it all|all of it|all your memories)\b",
    re.IGNORECASE,
)

# Rough categorisation, only to make the stored rows easier to read back.
_CATEGORY_HINTS = (
    ("preference", ("prefer", "like", "hate", "favourite", "favorite", "always", "never")),
    ("project", ("working on", "building", "project", "deadline", "shipping")),
    ("identity", ("my name is", "i am", "i'm a", "call me")),
)


def categorise(content: str) -> str:
    lowered = content.lower()
    for category, hints in _CATEGORY_HINTS:
        if any(hint in lowered for hint in hints):
            return category
    return "fact"


class MemoryManager:
    """Stores and retrieves the handful of facts Glitch carries forward."""

    def __init__(self, database: Database | None) -> None:
        self.db = database

    @property
    def available(self) -> bool:
        return self.db is not None and self.db.available

    # ------------------------------------------------------------- capturing
    def capture(self, message: str) -> str | None:
        """Store an explicit "remember ..." instruction.

        Returns what Glitch should say back, or None when the message was not
        a memory instruction at all.
        """
        if not message:
            return None

        if _FORGET_ALL.match(message):
            self.clear()
            return "Forgotten. Clean slate."

        match = _REMEMBER.match(message)
        if not match:
            return None

        content = match.group(1).strip().rstrip(".").strip()
        if len(content) < 3:
            return None
        content = content[:MAX_MEMORY_CHARS]

        if not self.available:
            log.info("Memory requested but no database is available")
            return "I'd remember that, but my memory isn't working right now."

        self.db.remember(categorise(content), content, importance=0.8)
        log.info("Remembered a fact from the user")
        return f"Got it. I'll remember that {content}."

    def remember(self, content: str, category: str = "fact", importance: float = 0.6) -> None:
        if self.available and content.strip():
            self.db.remember(category, content.strip()[:MAX_MEMORY_CHARS], importance)

    # -------------------------------------------------------------- reading
    def recall(self, limit: int = 8) -> list[str]:
        if not self.available:
            return []
        return [memory.content for memory in self.db.memories(limit)]

    def count(self) -> int:
        return len(self.recall(limit=1000))

    def clear(self) -> None:
        if self.available:
            self.db.clear_memories()
            log.info("All memories cleared")
