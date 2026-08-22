"""The vocabulary the awareness layer speaks.

A `Snapshot` is one reading of the machine. A `Signal` is a *change* between
two readings, which is the only thing worth reacting to.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Snapshot:
    """One reading of the environment. Cheap enough to take every few seconds.

    `foreground_title` is None unless the user has explicitly enabled window
    titles, so the rest of the pipeline cannot leak what it never received.
    """

    at: float = 0.0                       # monotonic seconds
    day: int = 0                          # date.toordinal(), for daily budgets
    hour: int = 12                        # local hour, 0-23
    foreground: str | None = None         # process name, lowercased
    foreground_title: str | None = None
    running: frozenset[str] = frozenset()
    idle_seconds: float = 0.0
    battery_percent: float | None = None
    battery_charging: bool | None = None
    fullscreen: bool = False


@dataclass(frozen=True)
class Signal:
    """Something changed. `key` selects a trigger; `data` colours the reaction."""

    key: str
    subject: str | None = None            # a category, never a raw process name
    data: dict[str, Any] = field(default_factory=dict)
