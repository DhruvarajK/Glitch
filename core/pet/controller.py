"""Orchestrates Glitch's physical presence on the desktop.

The controller owns position, facing and the active animation, and is the only
place that decides what the pet does next. It knows nothing about OpenAI.
"""
from __future__ import annotations

import random

from core.animation.controller import AnimationController
from core.animation.registry import AnimationRegistry
from core.events.bus import EventBus
from core.events.events import EventType
from core.persistence.config import ConfigManager
from core.screen.manager import ScreenManager
from core.utils.constants import BASE_PET_HEIGHT
from core.utils.logger import get_logger

log = get_logger("pet")

# Reactions Glitch may play when clicked, weighted by how often they fit.
CLICK_REACTIONS = [
    "happy", "happy", "amused", "surprised", "love",
    "smug", "mischievous", "embarrassed", "curious",
]


class PetController:
    """Position, movement and animation selection for the pet."""

    def __init__(
        self,
        config: ConfigManager,
        registry: AnimationRegistry,
        screens: ScreenManager,
        bus: EventBus,
    ) -> None:
        self.config = config
        self.registry = registry
        self.screens = screens
        self.bus = bus

        self.animation = AnimationController(
            registry, speed=float(config.get("animation_speed", 1.0))
        )
        self.animation.on_started = self._on_animation_started
        self.animation.on_finished = self._on_animation_finished

        self.width, self.height = self.animation.current_size()
        self.x, self.y = self._initial_position()
        self.facing = 1  # 1 = right, -1 = left
        self.dragging = False
        self._drag_offset = (0.0, 0.0)
        self._drag_origin = (0.0, 0.0)

        self.screens.configuration_changed.connect(self._on_screens_changed)
        config.on_change(self._on_config_changed)

    # ------------------------------------------------------------- position
    def _initial_position(self) -> tuple[float, float]:
        saved = self.config.get("last_position")
        if isinstance(saved, (list, tuple)) and len(saved) == 2:
            try:
                x, y = float(saved[0]), float(saved[1])
                return self.screens.clamp_position(x, y, self.width, self.height)
            except (TypeError, ValueError):
                pass
        screen = self.screens.primary()
        return (
            screen.center_x - self.width / 2,
            screen.bottom - self.height,
        )

    def set_position(self, x: float, y: float, *, clamp: bool = True) -> None:
        if clamp:
            x, y = self.screens.clamp_position(x, y, self.width, self.height)
        self.x, self.y = x, y

    def floor_y(self) -> float:
        return self.screens.floor_for(self.x + self.width / 2, self.y, self.height)

    def remember_position(self) -> None:
        self.config.set("last_position", [round(self.x), round(self.y)])

    # ------------------------------------------------------------ animation
    def play(self, name: str, *, force: bool = False) -> bool:
        return self.animation.play(name, force=force)

    def _on_animation_started(self, name: str) -> None:
        self.bus.emit(EventType.ANIMATION_STARTED, animation=name)

    def _on_animation_finished(self, name: str) -> None:
        self.bus.emit(EventType.ANIMATION_FINISHED, animation=name)

    def react(self, animation: str | None = None) -> None:
        """Play a one-shot reaction, chosen at random when unspecified."""
        self.play(animation or random.choice(CLICK_REACTIONS))

    # ------------------------------------------------------------ dragging
    # A press that moves less than this is a click, not a drag.
    DRAG_THRESHOLD = 5.0

    def begin_drag(self, global_x: int, global_y: int) -> None:
        self.dragging = True
        self._drag_offset = (global_x - self.x, global_y - self.y)
        self._drag_origin = (float(global_x), float(global_y))
        self.bus.emit(EventType.USER_DRAG_STARTED)

    def drag_to(self, global_x: int, global_y: int) -> None:
        if not self.dragging:
            return
        offset_x, offset_y = self._drag_offset
        # Dragging is deliberately unclamped so Glitch can cross monitors.
        self.x = global_x - offset_x
        self.y = global_y - offset_y
        if self._drag_moved(global_x, global_y):
            self.play("drag", force=True)
            self.bus.emit(EventType.USER_DRAGGED, x=self.x, y=self.y)

    def _drag_moved(self, global_x: float, global_y: float) -> bool:
        origin_x, origin_y = self._drag_origin
        return abs(global_x - origin_x) + abs(global_y - origin_y) > self.DRAG_THRESHOLD

    def end_drag(self) -> bool:
        """Finish a press. Returns True when it was a real drag, not a click."""
        if not self.dragging:
            return False
        self.dragging = False
        was_drag = self.animation.current == "drag"
        self.set_position(self.x, self.y)
        if was_drag:
            self.play("drop", force=True)
            self.bus.emit(EventType.USER_DRAG_ENDED, x=self.x, y=self.y)
        return was_drag

    # ---------------------------------------------------------------- tick
    def update(self, dt: float) -> None:
        self.animation.update(dt)
        self.animation.set_mirrored(self.facing < 0)

        width, height = self.animation.current_size()
        if (width, height) != (self.width, self.height):
            # Keep the pet standing on the same floor line when size changes.
            self.y += self.height - height
            self.width, self.height = width, height

        if not self.dragging:
            floor = self.floor_y()
            if self.y < floor:
                self.y = min(floor, self.y + 900 * dt)
            elif self.y > floor:
                self.y = floor
            self.set_position(self.x, self.y)

    # -------------------------------------------------------------- config
    def _on_config_changed(self, key: str, value: object) -> None:
        if key == "animation_speed":
            self.animation.set_speed(float(value))
        elif key == "pet_scale":
            self.apply_scale(float(value))

    def apply_scale(self, scale: float) -> None:
        bottom = self.y + self.height
        self.registry.set_target_height(int(BASE_PET_HEIGHT * scale))
        self.width, self.height = self.animation.current_size()
        self.set_position(self.x, bottom - self.height)
        log.info("Pet scale set to %.2f (%dpx)", scale, self.height)

    def _on_screens_changed(self) -> None:
        self.set_position(self.x, self.y)
        self.bus.emit(EventType.SCREEN_CONFIGURATION_CHANGED)
