"""Small timing helpers shared by the runtime loops."""
from __future__ import annotations

import time


class Clock:
    """Monotonic delta-time source with a cap to survive suspend/resume."""

    def __init__(self, max_delta: float = 0.25) -> None:
        self._last = time.monotonic()
        self._max_delta = max_delta

    def tick(self) -> float:
        now = time.monotonic()
        delta = now - self._last
        self._last = now
        return min(delta, self._max_delta)

    def reset(self) -> None:
        self._last = time.monotonic()


class Cooldown:
    """Returns True at most once per `interval` seconds."""

    def __init__(self, interval: float) -> None:
        self.interval = interval
        self._elapsed = 0.0

    def update(self, dt: float) -> bool:
        self._elapsed += dt
        if self._elapsed >= self.interval:
            self._elapsed = 0.0
            return True
        return False

    def reset(self) -> None:
        self._elapsed = 0.0
