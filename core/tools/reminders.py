"""Reminders: the one thing a desk pet is genuinely well placed to do.

Reminders live in the database rather than in memory, so closing Glitch does
not quietly drop them. Anything that came due while it was shut is delivered
on the next launch instead of vanishing.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable

from PySide6.QtCore import QObject, QTimer

from core.persistence.database import Database
from core.persistence.models import Reminder
from core.utils.logger import get_logger

log = get_logger("reminders")

# Reminders are minutes apart at best, so a coarse tick is plenty.
CHECK_INTERVAL_MS = 15_000
# Refuse anything past this; it is a desk pet, not a calendar.
MAX_MINUTES = 24 * 60
MIN_MINUTES = 1.0 / 60.0
MAX_TEXT_CHARS = 200


def describe_delay(minutes: float) -> str:
    """"20 minutes", "1 hour", "2 hours 30 minutes"."""
    total = int(round(minutes))
    if total < 1:
        return f"{int(round(minutes * 60))} seconds"
    hours, remainder = divmod(total, 60)
    parts = []
    if hours:
        parts.append(f"{hours} hour" + ("s" if hours != 1 else ""))
    if remainder:
        parts.append(f"{remainder} minute" + ("s" if remainder != 1 else ""))
    return " ".join(parts)


class ReminderService(QObject):
    """Stores reminders and delivers them when they come due."""

    def __init__(
        self,
        database: Database | None,
        on_due: Callable[[Reminder], None] | None = None,
    ) -> None:
        super().__init__()
        self.db = database
        self.on_due = on_due
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.check)

    @property
    def available(self) -> bool:
        return self.db is not None and self.db.available

    def start(self) -> None:
        self._timer.start(CHECK_INTERVAL_MS)

    def stop(self) -> None:
        self._timer.stop()

    # ------------------------------------------------------------- creating
    def add(self, text: str, minutes: float) -> Reminder | None:
        """Schedule a reminder, or None when it cannot be stored."""
        text = (text or "").strip()[:MAX_TEXT_CHARS]
        minutes = max(MIN_MINUTES, min(float(minutes), MAX_MINUTES))
        if not self.available:
            log.warning("No database; reminder not stored")
            return None
        due_at = datetime.now() + timedelta(minutes=minutes)
        reminder_id = self.db.add_reminder(text, due_at)  # type: ignore[union-attr]
        if reminder_id is None:
            return None
        log.info("Reminder %s set for %s", reminder_id, due_at.isoformat(timespec="minutes"))
        return Reminder(
            id=reminder_id, text=text, due_at=due_at, created_at=datetime.now()
        )

    # -------------------------------------------------------------- reading
    def pending(self) -> list[Reminder]:
        return self.db.pending_reminders() if self.available else []

    def cancel_all(self) -> int:
        outstanding = len(self.pending())
        if self.available:
            self.db.clear_reminders()  # type: ignore[union-attr]
        return outstanding

    def cancel(self, reminder_id: int) -> None:
        if self.available:
            self.db.delete_reminder(reminder_id)  # type: ignore[union-attr]

    # ------------------------------------------------------------ delivering
    def check(self, now: datetime | None = None) -> list[Reminder]:
        """Deliver everything now due, including anything missed while shut."""
        now = now or datetime.now()
        due = [reminder for reminder in self.pending() if reminder.is_due(now)]
        for reminder in due:
            if reminder.id is not None:
                self.db.mark_reminder_fired(reminder.id)  # type: ignore[union-attr]
            log.info("Reminder %s due", reminder.id)
            if self.on_due:
                self.on_due(reminder)
        return due
