"""Deciding what Glitch is standing on.

Open windows are treated as one-way platforms: Glitch lands on the top edge of
a window it falls onto, walks along it, and drops off once it runs out. Nothing
here touches Win32 or Qt, so the rules are plain geometry and unit testable.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from core.screen.geometry import Rect

# Surfaces within this many pixels above Glitch still count as underfoot, which
# absorbs the rounding that creeps in while standing still.
LAND_TOLERANCE = 2.0
# How far Glitch follows a window that moves up beneath it. Riding a window as
# it is dragged or resized looks right; a jump larger than this is more likely
# a window swapping places, so Glitch falls off instead of teleporting.
MAX_RIDE_UP = 240.0


@dataclass(frozen=True)
class Platform:
    """A window top edge Glitch can stand on, in virtual desktop coordinates."""

    handle: int
    rect: Rect


class PlatformSource(Protocol):
    """Whatever can tell the pet engine which windows are open right now."""

    def platforms(self) -> Sequence[Platform]:
        ...


def _covered(platforms: Sequence[Platform], index: int, x: float, y: float) -> bool:
    """True when a window nearer the front hides the point on this top edge."""
    return any(other.rect.contains_point(x, y) for other in platforms[:index])


def find_floor(
    *,
    foot_x: float,
    pet_height: int,
    reference_y: float,
    desktop_floor: float,
    platforms: Sequence[Platform],
    standing_on: int | None = None,
) -> tuple[float, int | None]:
    """The surface Glitch rests on, and the window it belongs to.

    `platforms` runs front to back, as the window manager stacks them.
    `reference_y` is where Glitch was at the start of the frame: surfaces above
    it are ignored so it rises through windows instead of being snapped onto
    them. `standing_on` is the window it was already on, which it keeps
    following even when that window moves upward.

    The desktop floor is always the fallback, so Glitch can never fall forever.
    """
    floor = desktop_floor
    handle: int | None = None

    for index, platform in enumerate(platforms):
        rect = platform.rect
        if not (rect.left <= foot_x < rect.right):
            continue  # Glitch is past the end of this window
        rest = rect.top - pet_height
        if rest >= floor:
            continue  # nothing above what has already been found
        if platform.handle == standing_on:
            if reference_y - rest > MAX_RIDE_UP:
                continue  # moved too far in one step to still be the same perch
        elif rest < reference_y - LAND_TOLERANCE:
            continue  # above Glitch, so it passes straight through
        if _covered(platforms, index, foot_x, rect.top):
            continue  # this stretch of the edge is behind another window
        floor, handle = rest, platform.handle

    return floor, handle
