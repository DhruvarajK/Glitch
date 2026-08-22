"""SQLite storage for the things that grow: conversations, memories, usage.

Transient runtime data (position, velocity, the current frame) never comes near
this file. Every method is guarded so a database failure degrades Glitch to a
session with no history rather than stopping it.
"""
from __future__ import annotations

import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from core.persistence.models import Memory, Message, UsageRecord
from core.utils.constants import DATABASE_PATH
from core.utils.logger import get_logger

log = get_logger("database")

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  TEXT NOT NULL,
    ended_at    TEXT,
    summary     TEXT
);

CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL,
    content         TEXT NOT NULL,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_conversation
    ON messages(conversation_id, id);

CREATE TABLE IF NOT EXISTS memories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    category    TEXT NOT NULL,
    content     TEXT NOT NULL UNIQUE,
    importance  REAL NOT NULL DEFAULT 0.5,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS emotion_state (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    traits      TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS usage (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    model         TEXT NOT NULL,
    input_tokens  INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    duration_ms   INTEGER NOT NULL DEFAULT 0,
    success       INTEGER NOT NULL DEFAULT 1,
    error         TEXT,
    created_at    TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _parse(value: str | None) -> datetime:
    try:
        return datetime.fromisoformat(value) if value else datetime.now()
    except ValueError:
        return datetime.now()


class Database:
    """A small, thread-safe wrapper around one SQLite file."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else DATABASE_PATH
        self._lock = threading.RLock()
        self._connection: sqlite3.Connection | None = None
        self.available = False
        self._connect()

    def _connect(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            # The AI worker thread writes usage rows, so the connection is
            # shared across threads and every access takes the lock.
            self._connection = sqlite3.connect(
                self.path, check_same_thread=False, timeout=5.0
            )
            self._connection.row_factory = sqlite3.Row
            with self._lock:
                self._connection.execute("PRAGMA journal_mode=WAL")
                self._connection.execute("PRAGMA foreign_keys=ON")
                self._connection.executescript(SCHEMA)
                self._connection.execute(
                    f"PRAGMA user_version={SCHEMA_VERSION}"
                )
                self._connection.commit()
            self.available = True
            log.info("Database ready at %s", self.path)
        except (sqlite3.Error, OSError) as exc:
            log.error("Database unavailable (%s); running without history", exc)
            self._connection = None
            self.available = False

    # ------------------------------------------------------------- internals
    def _execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor | None:
        if self._connection is None:
            return None
        try:
            with self._lock:
                cursor = self._connection.execute(sql, params)
                self._connection.commit()
                return cursor
        except sqlite3.Error as exc:
            log.error("Query failed (%s): %s", exc, sql.split("\n", 1)[0])
            return None

    def _query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        if self._connection is None:
            return []
        try:
            with self._lock:
                return list(self._connection.execute(sql, params).fetchall())
        except sqlite3.Error as exc:
            log.error("Query failed (%s): %s", exc, sql.split("\n", 1)[0])
            return []

    def close(self) -> None:
        with self._lock:
            if self._connection is not None:
                try:
                    self._connection.commit()
                    self._connection.close()
                except sqlite3.Error:
                    pass
                self._connection = None
                self.available = False

    # --------------------------------------------------------- conversations
    def start_conversation(self) -> int | None:
        cursor = self._execute(
            "INSERT INTO conversations (started_at) VALUES (?)", (_now(),)
        )
        return cursor.lastrowid if cursor else None

    def end_conversation(self, conversation_id: int, summary: str | None = None) -> None:
        self._execute(
            "UPDATE conversations SET ended_at = ?, summary = ? WHERE id = ?",
            (_now(), summary, conversation_id),
        )

    def latest_conversation(self) -> int | None:
        rows = self._query("SELECT id FROM conversations ORDER BY id DESC LIMIT 1")
        return rows[0]["id"] if rows else None

    def conversation_summaries(self, limit: int = 5) -> list[str]:
        rows = self._query(
            "SELECT summary FROM conversations "
            "WHERE summary IS NOT NULL ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return [row["summary"] for row in rows]

    # -------------------------------------------------------------- messages
    def add_message(self, conversation_id: int, role: str, content: str) -> int | None:
        cursor = self._execute(
            "INSERT INTO messages (conversation_id, role, content, created_at) "
            "VALUES (?, ?, ?, ?)",
            (conversation_id, role, content, _now()),
        )
        return cursor.lastrowid if cursor else None

    def recent_messages(self, conversation_id: int, limit: int = 20) -> list[Message]:
        rows = self._query(
            "SELECT * FROM (SELECT * FROM messages WHERE conversation_id = ? "
            "ORDER BY id DESC LIMIT ?) ORDER BY id ASC",
            (conversation_id, limit),
        )
        return [
            Message(
                id=row["id"],
                conversation_id=row["conversation_id"],
                role=row["role"],
                content=row["content"],
                created_at=_parse(row["created_at"]),
            )
            for row in rows
        ]

    def message_count(self, conversation_id: int) -> int:
        rows = self._query(
            "SELECT COUNT(*) AS n FROM messages WHERE conversation_id = ?",
            (conversation_id,),
        )
        return int(rows[0]["n"]) if rows else 0

    def clear_conversations(self) -> None:
        self._execute("DELETE FROM messages")
        self._execute("DELETE FROM conversations")

    # -------------------------------------------------------------- memories
    def remember(self, category: str, content: str, importance: float = 0.5) -> None:
        self._execute(
            "INSERT INTO memories (category, content, importance, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(content) DO UPDATE SET "
            "importance = MAX(importance, excluded.importance), updated_at = excluded.updated_at",
            (category, content.strip(), float(importance), _now(), _now()),
        )

    def memories(self, limit: int = 10) -> list[Memory]:
        rows = self._query(
            "SELECT * FROM memories ORDER BY importance DESC, updated_at DESC LIMIT ?",
            (limit,),
        )
        return [
            Memory(
                id=row["id"],
                category=row["category"],
                content=row["content"],
                importance=row["importance"],
                created_at=_parse(row["created_at"]),
                updated_at=_parse(row["updated_at"]),
            )
            for row in rows
        ]

    def forget(self, memory_id: int) -> None:
        self._execute("DELETE FROM memories WHERE id = ?", (memory_id,))

    def clear_memories(self) -> None:
        self._execute("DELETE FROM memories")

    # --------------------------------------------------------- emotion state
    def save_emotion(self, traits_json: str) -> None:
        self._execute(
            "INSERT INTO emotion_state (id, traits, updated_at) VALUES (1, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET traits = excluded.traits, "
            "updated_at = excluded.updated_at",
            (traits_json, _now()),
        )

    def load_emotion(self) -> str | None:
        rows = self._query("SELECT traits FROM emotion_state WHERE id = 1")
        return rows[0]["traits"] if rows else None

    # ----------------------------------------------------------------- usage
    def record_usage(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        duration_ms: int,
        success: bool,
        error: str | None = None,
    ) -> None:
        self._execute(
            "INSERT INTO usage (model, input_tokens, output_tokens, duration_ms, "
            "success, error, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                model,
                int(input_tokens),
                int(output_tokens),
                int(duration_ms),
                1 if success else 0,
                error,
                _now(),
            ),
        )

    def usage_totals(self) -> dict[str, int]:
        rows = self._query(
            "SELECT COUNT(*) AS requests, "
            "COALESCE(SUM(input_tokens), 0) AS input_tokens, "
            "COALESCE(SUM(output_tokens), 0) AS output_tokens, "
            "COALESCE(SUM(success), 0) AS successes FROM usage"
        )
        if not rows:
            return {"requests": 0, "input_tokens": 0, "output_tokens": 0, "successes": 0}
        return {key: int(rows[0][key]) for key in rows[0].keys()}

    def recent_usage(self, limit: int = 20) -> list[UsageRecord]:
        rows = self._query("SELECT * FROM usage ORDER BY id DESC LIMIT ?", (limit,))
        return [
            UsageRecord(
                id=row["id"],
                model=row["model"],
                input_tokens=row["input_tokens"],
                output_tokens=row["output_tokens"],
                duration_ms=row["duration_ms"],
                success=bool(row["success"]),
                error=row["error"],
                created_at=_parse(row["created_at"]),
            )
            for row in rows
        ]
