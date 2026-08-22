"""Row types for the SQLite store."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Message:
    id: int | None
    conversation_id: int
    role: str  # "user" | "assistant" | "system"
    content: str
    created_at: datetime

    def as_chat_message(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass
class Memory:
    id: int | None
    category: str  # e.g. "preference", "fact", "project"
    content: str
    importance: float
    created_at: datetime
    updated_at: datetime


@dataclass
class UsageRecord:
    id: int | None
    model: str
    input_tokens: int
    output_tokens: int
    duration_ms: int
    success: bool
    error: str | None
    created_at: datetime
