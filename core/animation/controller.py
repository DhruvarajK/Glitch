"""Frame playback. Decides how an animation plays, never why it plays."""
from __future__ import annotations

from typing import Callable

from PySide6.QtGui import QPixmap

from core.animation.animation_data import AnimationSpec, LoadedClip
from core.animation.registry import AnimationRegistry
from core.utils.logger import get_logger

log = get_logger("animation")


class AnimationController:
    """Advances frames for the current animation and honours priorities."""

    def __init__(self, registry: AnimationRegistry, speed: float = 1.0) -> None:
        self.registry = registry
        self.speed = max(0.05, float(speed))
        self.mirrored = False

        self._spec: AnimationSpec = registry.spec(registry.fallback)
        self._frame = 0
        self._elapsed = 0.0
        self._finished = False

        self.on_finished: Callable[[str], None] | None = None
        self.on_started: Callable[[str], None] | None = None

        self.play(registry.fallback, force=True)

    # ---------------------------------------------------------------- state
    @property
    def current(self) -> str:
        return self._spec.name

    @property
    def spec(self) -> AnimationSpec:
        return self._spec

    @property
    def finished(self) -> bool:
        return self._finished

    @property
    def priority(self) -> int:
        return self._spec.priority

    def can_interrupt(self, priority: int) -> bool:
        """A running animation yields if it is interruptible, done, or outranked."""
        if self._finished or self._spec.interruptible:
            return True
        return priority > self._spec.priority

    # --------------------------------------------------------------- control
    def play(self, name: str, *, force: bool = False, restart: bool = False) -> bool:
        spec = self.registry.spec(name)
        if not force and not self.can_interrupt(spec.priority):
            return False
        if spec.name == self._spec.name and not restart and not self._finished:
            return True

        self._spec = spec
        self._frame = 0
        self._elapsed = 0.0
        self._finished = False
        log.debug("Animation -> %s", spec.name)
        if self.on_started:
            self.on_started(spec.name)
        return True

    def set_speed(self, speed: float) -> None:
        self.speed = max(0.05, float(speed))

    def set_mirrored(self, mirrored: bool) -> None:
        self.mirrored = bool(mirrored)

    # ----------------------------------------------------------------- tick
    def update(self, dt: float) -> None:
        if self._finished:
            return
        clip = self.registry.clip_for(self._spec.name)
        if clip.frame_count <= 1:
            self._finished = not self._spec.loop
            return

        self._elapsed += dt * self.speed
        while self._elapsed >= self._frame_duration(clip):
            self._elapsed -= self._frame_duration(clip)
            self._frame += 1
            if self._frame < clip.frame_count:
                continue
            if self._spec.loop:
                self._frame = 0
            else:
                self._frame = clip.frame_count - 1
                self._finished = True
                self._emit_finished()
                return

    def _frame_duration(self, clip: LoadedClip) -> float:
        if self._spec.fps:
            return 1.0 / float(self._spec.fps)
        index = min(self._frame, len(clip.durations) - 1)
        return clip.durations[index]

    def _emit_finished(self) -> None:
        name = self._spec.name
        follow_up = self._spec.next_animation
        if self.on_finished:
            self.on_finished(name)
        if follow_up and self._spec.name == name:
            self.play(follow_up, force=True)

    # --------------------------------------------------------------- output
    def current_pixmap(self) -> QPixmap:
        clip = self.registry.clip_for(self._spec.name)
        return clip.frame(self._frame, mirrored=self.mirrored)

    def current_size(self) -> tuple[int, int]:
        clip = self.registry.clip_for(self._spec.name)
        return clip.width, clip.height
