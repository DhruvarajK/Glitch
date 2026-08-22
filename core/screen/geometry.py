"""Pure geometry helpers, independent of Qt, so they can be unit tested."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

    @property
    def left(self) -> int:
        return self.x

    @property
    def top(self) -> int:
        return self.y

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    @property
    def center_x(self) -> float:
        return self.x + self.width / 2

    def contains_point(self, px: float, py: float) -> bool:
        return self.left <= px < self.right and self.top <= py < self.bottom

    def united(self, other: "Rect") -> "Rect":
        left = min(self.left, other.left)
        top = min(self.top, other.top)
        right = max(self.right, other.right)
        bottom = max(self.bottom, other.bottom)
        return Rect(left, top, right - left, bottom - top)


def clamp(value: float, low: float, high: float) -> float:
    if low > high:
        return low
    return max(low, min(high, value))
