"""Orchestrates Glitch's physical behaviour on the desktop.

The controller coordinates the state machine, behaviour engine, physics and
animation. It is the only place that decides what the pet does next, and it
knows nothing about OpenAI: everything here works offline.
"""
from __future__ import annotations

import random

from core.ai.emotion import EmotionEngine
from core.animation.controller import AnimationController
from core.animation.registry import AnimationRegistry
from core.events.bus import EventBus
from core.events.events import EventType
from core.persistence.config import ConfigManager
from core.pet.behavior import BehaviorController, BehaviorIntent
from core.pet.interaction import InteractionController
from core.pet.physics import PhysicsController
from core.pet.state import (
    BEHAVIOUR_STATES,
    STATE_ANIMATION,
    STATIONARY_STATES,
    TRANSIENT_STATES,
    PetState,
)
from core.pet.state_machine import PetStateMachine
from core.screen.manager import ScreenManager
from core.utils.constants import BASE_PET_HEIGHT
from core.utils.logger import get_logger

log = get_logger("pet")

# A press that moves less than this is a click, not a drag.
DRAG_THRESHOLD = 5.0
# How close to the target counts as arrived, in pixels.
ARRIVAL_TOLERANCE = 6.0
# A transient state never lasts longer than this, even if its animation loops
# forever because of a manifest mistake.
MAX_TRANSIENT_SECONDS = 8.0


class PetController:
    """Position, movement, state and animation selection for the pet."""

    def __init__(
        self,
        config: ConfigManager,
        registry: AnimationRegistry,
        screens: ScreenManager,
        bus: EventBus,
        emotion: EmotionEngine | None = None,
        rng: random.Random | None = None,
    ) -> None:
        self.config = config
        self.registry = registry
        self.screens = screens
        self.bus = bus
        self.rng = rng or random.Random()

        self.emotion = emotion or EmotionEngine()
        self.animation = AnimationController(
            registry, speed=float(config.get("animation_speed", 1.0))
        )
        self.animation.on_started = self._on_animation_started
        self.animation.on_finished = self._on_animation_finished

        self.states = PetStateMachine(PetState.IDLE)
        self.states.on_change = self._on_state_changed
        self.physics = PhysicsController()
        self.behavior = BehaviorController(config, rng=self.rng)
        self.interaction = InteractionController(self, self.emotion, bus)

        self.width, self.height = self.animation.current_size()
        x, y = self._initial_position()
        self.physics.body.set_position(x, y)
        self.facing = 1  # 1 = right, -1 = left

        self._walk_target: float | None = None
        self._pending_animation: str | None = None
        self._drag_offset = (0.0, 0.0)
        self._drag_origin = (0.0, 0.0)
        self._drag_pending = False
        self._dragging = False

        self.screens.configuration_changed.connect(self._on_screens_changed)
        config.on_change(self._on_config_changed)

    # ------------------------------------------------------------- position
    @property
    def x(self) -> float:
        return self.physics.body.x

    @property
    def y(self) -> float:
        return self.physics.body.y

    @property
    def state(self) -> PetState:
        return self.states.state

    @property
    def dragging(self) -> bool:
        return self._dragging

    def _initial_position(self) -> tuple[float, float]:
        saved = self.config.get("last_position")
        if isinstance(saved, (list, tuple)) and len(saved) == 2:
            try:
                return self.screens.clamp_position(
                    float(saved[0]), float(saved[1]), self.width, self.height
                )
            except (TypeError, ValueError):
                pass
        screen = self.screens.primary()
        return screen.center_x - self.width / 2, screen.bottom - self.height

    def set_position(self, x: float, y: float, *, clamp: bool = True) -> None:
        if clamp:
            x, y = self.screens.clamp_position(x, y, self.width, self.height)
        self.physics.body.set_position(x, y)

    def floor_y(self) -> float:
        return self.screens.floor_for(self.x + self.width / 2, self.y, self.height)

    def remember_position(self) -> None:
        self.config.set("last_position", [round(self.x), round(self.y)])

    # ---------------------------------------------------------------- states
    def enter_state(
        self, state: PetState, *, force: bool = False, animation: str | None = None
    ) -> bool:
        # Read synchronously by _on_state_changed during the transition.
        self._pending_animation = animation
        changed = self.states.transition(state, force=force)
        self._pending_animation = None
        return changed

    def _on_state_changed(self, previous: PetState, current: PetState) -> None:
        animation = self._pending_animation or STATE_ANIMATION.get(current, "idle")
        self.animation.play(animation, force=True)

        if current in STATIONARY_STATES:
            self.physics.halt()
            self._walk_target = None

        self.bus.emit(
            EventType.PET_STATE_CHANGED,
            previous=previous.value,
            state=current.value,
            animation=animation,
        )
        if current is PetState.SLEEPING:
            self.bus.emit(EventType.PET_WENT_TO_SLEEP)
        elif previous is PetState.SLEEPING:
            self.bus.emit(EventType.PET_WOKE_UP)

    # ------------------------------------------------------------ animation
    def play(self, name: str, *, force: bool = False) -> bool:
        return self.animation.play(name, force=force)

    def react(self, animation: str | None = None) -> None:
        """Play a one-shot reaction and return to whatever came before."""
        name = animation or self.emotion.reaction_animation()
        self.enter_state(PetState.REACTING, animation=name, force=True)

    def _on_animation_started(self, name: str) -> None:
        self.bus.emit(EventType.ANIMATION_STARTED, animation=name)

    def _on_animation_finished(self, name: str) -> None:
        self.bus.emit(EventType.ANIMATION_FINISHED, animation=name)
        if self.states.state in TRANSIENT_STATES and not self.animation.spec.next_animation:
            self.states.transition(PetState.IDLE, force=True)

    # ------------------------------------------------------------- lifecycle
    def sleep(self) -> None:
        if self.state is PetState.SLEEPING:
            return
        self.emotion.apply("slept")
        self.enter_state(PetState.SLEEPING, force=True)

    def wake(self) -> None:
        if self.state is not PetState.SLEEPING:
            return
        self.emotion.apply("woke")
        self.interaction.notice()
        self.enter_state(PetState.WAKING, force=True)

    def pause_movement(self, paused: bool) -> None:
        self.behavior.paused = paused
        if paused and self.state in (PetState.WALKING, PetState.RUNNING):
            self.enter_state(PetState.IDLE, force=True)

    # -------------------------------------------------------------- movement
    def walk_to(self, target_x: float, *, run: bool = False) -> None:
        if not self.config.get("autonomous_movement", True):
            return
        self._walk_target = float(target_x)
        state = PetState.RUNNING if run else PetState.WALKING
        if self.enter_state(state):
            self.emotion.apply("walked")

    def _update_movement(self, dt: float) -> None:
        if self.state not in (PetState.WALKING, PetState.RUNNING):
            return
        if self._walk_target is None:
            self.enter_state(PetState.IDLE)
            return

        speed = float(self.config.get("movement_speed", 80.0))
        if self.state is PetState.RUNNING:
            speed *= 2.2

        delta = self._walk_target - self.x
        if abs(delta) <= ARRIVAL_TOLERANCE:
            self.enter_state(PetState.IDLE)
            return

        direction = 1 if delta > 0 else -1
        self.facing = direction
        self.physics.walk(speed * direction)

    # ------------------------------------------------------------ behaviour
    def _apply_intent(self, intent: BehaviorIntent) -> None:
        action = intent.action
        if action == "walk":
            bounds = self.screens.screen_at(self.x + self.width / 2, self.y)
            span = max(1, bounds.width - self.width)
            distance = intent.data.get("distance", 0.4) * span
            target = self.x + intent.data.get("direction", 1) * distance
            target = max(bounds.left, min(target, bounds.right - self.width))
            self.walk_to(target, run=bool(intent.data.get("run")))
        elif action == "stop":
            self.enter_state(PetState.IDLE)
        elif action == "sit":
            self.enter_state(PetState.SITTING)
        elif action == "look":
            self.enter_state(PetState.LOOKING)
        elif action == "stretch":
            self.enter_state(PetState.REACTING, animation="stretch")
        elif action == "yawn":
            self.enter_state(PetState.REACTING, animation="yawn")
        elif action == "react":
            self.react(intent.data.get("animation"))
            self.emotion.apply("played")
        elif action == "sleep":
            self.sleep()
        elif action == "wake":
            self.wake()

    # ------------------------------------------------------------- dragging
    def begin_drag(self, global_x: int, global_y: int) -> None:
        self._drag_pending = True
        self._drag_offset = (global_x - self.x, global_y - self.y)
        self._drag_origin = (float(global_x), float(global_y))

    def drag_to(self, global_x: int, global_y: int) -> None:
        if not (self._drag_pending or self._dragging):
            return
        origin_x, origin_y = self._drag_origin
        if self._drag_pending:
            moved = abs(global_x - origin_x) + abs(global_y - origin_y)
            if moved <= DRAG_THRESHOLD:
                return
            self._drag_pending = False
            self._dragging = True
            self.bus.emit(EventType.USER_DRAG_STARTED)

        offset_x, offset_y = self._drag_offset
        # Dragging is deliberately unclamped so Glitch can cross monitors.
        self.physics.body.set_position(global_x - offset_x, global_y - offset_y)
        self.physics.body.stop()
        self.bus.emit(EventType.USER_DRAGGED, x=self.x, y=self.y)

    def end_drag(self) -> bool:
        """Finish a press. Returns True when it was a real drag, not a click."""
        self._drag_pending = False
        if not self._dragging:
            return False
        self._dragging = False
        self.set_position(self.x, self.y)
        self.physics.body.on_ground = abs(self.y - self.floor_y()) < 1.0
        self.bus.emit(EventType.USER_DRAG_ENDED, x=self.x, y=self.y)
        if self.physics.body.on_ground:
            self.enter_state(PetState.DROPPED, force=True)
        # Otherwise Glitch keeps the dragged pose until it lands.
        return True

    # ---------------------------------------------------------------- tick
    def update(self, dt: float) -> None:
        self.states.update(dt)
        if (
            self.state in TRANSIENT_STATES
            and self.states.time_in_state > MAX_TRANSIENT_SECONDS
        ):
            log.debug("Transient state %s overran; returning to idle", self.state.value)
            self.enter_state(PetState.IDLE, force=True)
        self.emotion.update(dt, asleep=self.state is PetState.SLEEPING)
        self.interaction.update(dt)

        if not self._dragging:
            if self.state in BEHAVIOUR_STATES or self.state is PetState.SLEEPING:
                intent = self.behavior.update(dt, self.state, self.emotion.state)
                if intent is not None:
                    self._apply_intent(intent)
            self._update_movement(dt)
            self._step_physics(dt)

        self._sync_size()
        self.animation.set_mirrored(self.facing < 0)
        self.animation.update(dt)

    def _step_physics(self, dt: float) -> None:
        bounds = self.screens.screen_at(self.x + self.width / 2, self.y + self.height / 2)
        events = self.physics.update(
            dt,
            floor_y=self.floor_y(),
            left_bound=bounds.left,
            right_bound=max(bounds.left, bounds.right - self.width),
        )
        if events["hit_left"] or events["hit_right"]:
            self._on_edge_reached()
        if events["landed"] and self.state is PetState.DRAGGED:
            self.enter_state(PetState.DROPPED, force=True)


    def _on_edge_reached(self) -> None:
        if self.state not in (PetState.WALKING, PetState.RUNNING):
            return
        if self._cross_to_adjacent_screen():
            return
        # Nowhere to go: turn around instead of grinding against the edge.
        self._walk_target = None
        self.facing *= -1
        self.enter_state(PetState.IDLE)

    def _cross_to_adjacent_screen(self) -> bool:
        """Step onto the neighbouring monitor when one continues this way."""
        if not self.config.get("multi_monitor_roaming", True):
            return False
        current = self.screens.screen_at(self.x + self.width / 2, self.y + self.height / 2)
        neighbour = self.screens.adjacent_screen(current, self.facing)
        if neighbour is None:
            return False

        if self.facing > 0:
            x = neighbour.left
            target = min(neighbour.right - self.width, x + self.width * 2)
        else:
            x = neighbour.right - self.width
            target = max(neighbour.left, x - self.width * 2)

        y = neighbour.bottom - self.height
        self.physics.body.set_position(x, y)
        self.physics.body.on_ground = True
        self._walk_target = target
        log.debug("Crossed onto the adjacent screen at x=%d", x)
        return True

    def _sync_size(self) -> None:
        width, height = self.animation.current_size()
        if (width, height) == (self.width, self.height):
            return
        # Keep the pet standing on the same floor line when its size changes.
        self.physics.body.y += self.height - height
        self.width, self.height = width, height

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
        self._walk_target = None
        self.bus.emit(EventType.SCREEN_CONFIGURATION_CHANGED)
