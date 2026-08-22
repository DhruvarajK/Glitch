"""How long the user has spent with each kind of app today.

Fed by the awareness layer, which already knows what is in front. Only the
category and a running total of seconds are stored - never an app name, never
a window title - so the history cannot say more than "four hours of coding".

Keeping this locally is also what makes "how long have I been at this?"
answerable without an API request.
"""
from __future__ import annotations

from datetime import date, datetime

from core.awareness.apps import CATEGORY_LABELS
from core.persistence.database import Database
from core.utils.logger import get_logger

log = get_logger("activity")

# Time is banked in chunks rather than on every tick, to keep writes rare.
FLUSH_SECONDS = 60.0
# A gap longer than this means the machine slept; do not bank it as work.
MAX_CREDITED_GAP = 120.0

# Category names as they read in a sentence.
SPOKEN = {
    "coding": "coding",
    "terminal": "in a terminal",
    "browser": "in the browser",
    "music": "listening to music",
    "gaming": "gaming",
    "meeting": "in calls",
    "chat": "chatting",
    "design": "designing",
    "writing": "writing",
    "office": "in documents",
    "video": "watching things",
}


def humanise(seconds: float) -> str:
    """"25 minutes", "3 hours", "1 hour 40 minutes"."""
    minutes = int(seconds // 60)
    if minutes < 1:
        return "under a minute"
    hours, remainder = divmod(minutes, 60)
    if not hours:
        return f"{minutes} minute" + ("s" if minutes != 1 else "")
    if not remainder:
        return f"{hours} hour" + ("s" if hours != 1 else "")
    return f"{hours}h {remainder}m"


class ActivityTracker:
    """Banks foreground time per category, one row per day."""

    def __init__(self, database: Database | None) -> None:
        self.db = database
        self._category: str | None = None
        self._pending = 0.0
        self._last_at: float | None = None

    @property
    def available(self) -> bool:
        return self.db is not None and self.db.available

    # --------------------------------------------------------------- feeding
    def observe(self, category: str | None, at: float) -> None:
        """Credit the time since the last observation to the previous app."""
        if self._last_at is not None and self._category:
            elapsed = at - self._last_at
            if 0 < elapsed <= MAX_CREDITED_GAP:
                self._pending += elapsed
        if category != self._category:
            self.flush()
            self._category = category
        self._last_at = at
        if self._pending >= FLUSH_SECONDS:
            self.flush()

    def flush(self) -> None:
        """Write the banked seconds out."""
        if self._pending <= 0 or not self._category or not self.available:
            self._pending = 0.0
            return
        self.db.add_activity(  # type: ignore[union-attr]
            date.today().isoformat(), self._category, self._pending
        )
        self._pending = 0.0

    # --------------------------------------------------------------- reading
    def today(self) -> dict[str, float]:
        """Seconds per category so far today, banked plus pending."""
        totals = dict(self.db.activity_for(date.today().isoformat())) if self.available else {}
        if self._category and self._pending:
            totals[self._category] = totals.get(self._category, 0.0) + self._pending
        return dict(sorted(totals.items(), key=lambda item: item[1], reverse=True))

    def seconds_on(self, category: str) -> float:
        return self.today().get(category, 0.0)

    def summary(self, limit: int = 3) -> str:
        """A spoken summary of the day, for the bubble and for the prompt."""
        totals = self.today()
        if not totals:
            return "I haven't been watching long enough to say."
        parts = [
            f"{humanise(seconds)} {SPOKEN.get(category, CATEGORY_LABELS.get(category, category))}"
            for category, seconds in list(totals.items())[:limit]
            if seconds >= 60
        ]
        if not parts:
            return "Barely anything so far today."
        if len(parts) == 1:
            return f"Today: {parts[0]}."
        return "Today: " + ", ".join(parts[:-1]) + f" and {parts[-1]}."

    def current(self) -> str | None:
        """What is happening right now, as a phrase."""
        if not self._category:
            return None
        return SPOKEN.get(self._category, self._category)
