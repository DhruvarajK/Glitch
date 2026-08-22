"""Conversation context: what Glitch remembers of the current exchange.

Only a bounded window of recent turns is sent to the model. Older turns stay
in the database and are represented, if at all, by a short summary.
"""
from __future__ import annotations

from collections import deque

from core.persistence.config import ConfigManager
from core.persistence.database import Database
from core.utils.logger import get_logger

log = get_logger("conversation")

# Hard ceiling regardless of configuration, so context can never run away.
MAX_WINDOW = 40
# Characters kept from any single message when building context.
MAX_MESSAGE_CHARS = 1200


class ConversationManager:
    """Maintains the rolling window and persists every turn."""

    def __init__(self, config: ConfigManager, database: Database | None = None) -> None:
        self.config = config
        self.db = database
        self._window: deque[dict[str, str]] = deque(maxlen=self._limit())
        self.conversation_id: int | None = None
        self._start()

    def _limit(self) -> int:
        return min(int(self.config.get("conversation_memory", 20)), MAX_WINDOW)

    def _start(self) -> None:
        if self.db is None or not self.db.available:
            return
        self.conversation_id = self.db.latest_conversation() or self.db.start_conversation()
        if self.conversation_id is None:
            return
        for message in self.db.recent_messages(self.conversation_id, self._limit()):
            self._window.append(message.as_chat_message())
        if self._window:
            log.info("Restored %d messages of context", len(self._window))

    # -------------------------------------------------------------- mutation
    def add_user_message(self, content: str) -> None:
        self._append("user", content)

    def add_assistant_message(self, content: str) -> None:
        self._append("assistant", content)

    def _append(self, role: str, content: str) -> None:
        content = content.strip()
        if not content:
            return
        self._resize()
        self._window.append({"role": role, "content": content[:MAX_MESSAGE_CHARS]})
        if self.db is not None and self.conversation_id is not None:
            self.db.add_message(self.conversation_id, role, content)

    def _resize(self) -> None:
        limit = self._limit()
        if self._window.maxlen != limit:
            self._window = deque(self._window, maxlen=limit)

    # --------------------------------------------------------------- reading
    def context(self) -> list[dict[str, str]]:
        """The recent turns, oldest first, ready to send to the model."""
        return list(self._window)

    def summaries(self) -> list[str]:
        if self.db is None or not self.db.available:
            return []
        return self.db.conversation_summaries(limit=3)

    def memories(self) -> list[str]:
        if self.db is None or not self.db.available:
            return []
        return [memory.content for memory in self.db.memories(limit=8)]

    def is_empty(self) -> bool:
        return not self._window

    # ------------------------------------------------------------- lifecycle
    def new_conversation(self) -> None:
        """Close the current thread and begin a fresh one."""
        if self.db is not None and self.db.available and self.conversation_id is not None:
            self.db.end_conversation(self.conversation_id)
            self.conversation_id = self.db.start_conversation()
        self._window.clear()

    def clear(self) -> None:
        self._window.clear()
        if self.db is not None and self.db.available:
            self.db.clear_conversations()
            self.conversation_id = self.db.start_conversation()
