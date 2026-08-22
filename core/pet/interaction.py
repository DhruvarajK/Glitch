"""Turns raw user input into pet responses and emotional consequences."""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

from core.ai.emotion import EmotionEngine
from core.events.bus import EventBus
from core.events.events import EventType
from core.pet.state import PetState
from core.utils.logger import get_logger

if TYPE_CHECKING:  # avoids a circular import at runtime
    from core.pet.controller import PetController

log = get_logger("interaction")

# Clicks landing closer together than this count as pestering.
SPAM_WINDOW = 1.2
SPAM_THRESHOLD = 4


class InteractionController:
    """Owns the user-facing half of the pet's behaviour."""

    def __init__(self, pet: "PetController", emotion: EmotionEngine, bus: EventBus) -> None:
        self.pet = pet
        self.emotion = emotion
        self.bus = bus
        self._last_interaction = time.monotonic()
        self._recent_clicks: list[float] = []

        bus.subscribe(EventType.USER_CLICKED, lambda e: self.on_click())
        bus.subscribe(EventType.USER_DRAG_STARTED, lambda e: self.on_drag_started())
        bus.subscribe(EventType.USER_DRAG_ENDED, lambda e: self.on_drag_ended())
        bus.subscribe(EventType.USER_DOUBLE_CLICKED, lambda e: self.on_double_click())
        bus.subscribe(EventType.USER_MESSAGE, lambda e: self.notice())

    # -------------------------------------------------------------- activity
    def notice(self) -> None:
        """Record that the user did something, whatever it was."""
        self._last_interaction = time.monotonic()

    @property
    def seconds_since_interaction(self) -> float:
        return time.monotonic() - self._last_interaction

    def _is_spam(self) -> bool:
        now = time.monotonic()
        self._recent_clicks = [t for t in self._recent_clicks if now - t <= SPAM_WINDOW]
        self._recent_clicks.append(now)
        return len(self._recent_clicks) >= SPAM_THRESHOLD

    # --------------------------------------------------------------- handlers
    def on_click(self) -> None:
        self.notice()
        if self.pet.state is PetState.SLEEPING:
            self.pet.wake()
            return

        if self._is_spam():
            self.emotion.apply("click_spam")
            self.pet.react("annoyed" if self.emotion.state.annoyance > 0.5 else "dizzy")
            return

        self.emotion.apply("clicked")
        self.pet.react(self.emotion.reaction_animation())

    def on_double_click(self) -> None:
        self.notice()
        if self.pet.state is PetState.SLEEPING:
            self.pet.wake()

    def on_drag_started(self) -> None:
        self.notice()
        self.pet.enter_state(PetState.DRAGGED, force=True)

    def on_drag_ended(self) -> None:
        # The controller decides when the drop pose starts: immediately if
        # Glitch was released on the floor, otherwise once it lands.
        self.notice()
        self.emotion.apply("dragged")

    # ------------------------------------------------------------------ tick
    def update(self, dt: float) -> None:
        """Drift toward sleep when the user has been away long enough."""
        if not self.pet.config.get("sleep_enabled", True):
            return
        if self.pet.state in (PetState.SLEEPING, PetState.DRAGGED, PetState.THINKING):
            return
        threshold = float(self.pet.config.get("idle_seconds_before_sleep", 300.0))
        if self.seconds_since_interaction >= threshold and self.emotion.state.sleepiness > 0.4:
            log.debug("No interaction for %.0fs; going to sleep", self.seconds_since_interaction)
            self.pet.sleep()
