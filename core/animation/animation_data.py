"""Data types describing animations, kept free of playback logic."""
from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtGui import QPixmap

# Priority bands used across the runtime. Higher wins.
PRIORITY_IDLE = 10
PRIORITY_WALK = 20
PRIORITY_SLEEP = 50
PRIORITY_TALK = 60
PRIORITY_REACTION = 70
PRIORITY_THINK = 80
PRIORITY_DROP = 90
PRIORITY_DRAG = 100


@dataclass(frozen=True)
class AnimationSpec:
    """Metadata for one playable animation, loaded from the manifest."""

    name: str
    clip: str
    fps: float | None = None  # None -> use the durations baked into the sheet
    loop: bool = True
    priority: int = PRIORITY_IDLE
    interruptible: bool = True
    next_animation: str | None = None  # played automatically when this finishes


@dataclass
class LoadedClip:
    """Decoded, display-sized frames for one sprite sheet."""

    name: str
    frames: list[QPixmap]
    durations: list[float]  # seconds per frame, from the sheet metadata
    width: int
    height: int
    flipped: list[QPixmap] = field(default_factory=list)

    @property
    def frame_count(self) -> int:
        return len(self.frames)

    def frame(self, index: int, mirrored: bool = False) -> QPixmap:
        source = self.flipped if (mirrored and self.flipped) else self.frames
        return source[index % len(source)]
