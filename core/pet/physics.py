"""Lightweight desktop physics: gravity, friction, floors and edges.

Values are tuned empirically and exposed as attributes rather than baked into
the integration step, so they can be adjusted from configuration.
"""
from __future__ import annotations

from dataclasses import dataclass

GRAVITY = 1600.0        # px/s^2
MAX_FALL_SPEED = 1800.0  # px/s
GROUND_FRICTION = 6.0    # velocity decay per second while on the floor
AIR_DRAG = 0.6
BOUNCE_DAMPING = 0.35    # vertical energy kept when landing from a fall
MIN_BOUNCE_SPEED = 220.0  # below this, landings just stop
STOP_THRESHOLD = 4.0     # px/s treated as standing still


@dataclass
class PhysicsBody:
    """Position and motion of the pet in virtual desktop coordinates."""

    x: float = 0.0
    y: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    ax: float = 0.0
    ay: float = 0.0
    on_ground: bool = True

    def set_position(self, x: float, y: float) -> None:
        self.x, self.y = float(x), float(y)

    def stop(self) -> None:
        self.vx = self.vy = self.ax = self.ay = 0.0


class PhysicsController:
    """Integrates a body against the desktop floor and screen edges."""

    def __init__(self, gravity: float = GRAVITY) -> None:
        self.gravity = gravity
        self.body = PhysicsBody()
        self.enabled = True

    # ---------------------------------------------------------------- helpers
    def apply_impulse(self, vx: float = 0.0, vy: float = 0.0) -> None:
        self.body.vx += vx
        self.body.vy += vy
        if vy < 0:
            self.body.on_ground = False

    def walk(self, speed: float) -> None:
        """Set a horizontal cruising speed; sign selects the direction."""
        self.body.vx = speed

    def halt(self) -> None:
        self.body.vx = 0.0

    # -------------------------------------------------------------- stepping
    def update(
        self,
        dt: float,
        floor_y: float,
        left_bound: float,
        right_bound: float,
        *,
        gravity_enabled: bool = True,
        friction: bool = True,
    ) -> dict[str, bool]:
        """Advance one step. Returns which collisions happened this frame."""
        body = self.body
        events = {"landed": False, "hit_left": False, "hit_right": False}
        if not self.enabled or dt <= 0:
            return events

        if gravity_enabled and not body.on_ground:
            body.vy = min(body.vy + self.gravity * dt, MAX_FALL_SPEED)
            body.vx *= max(0.0, 1.0 - AIR_DRAG * dt)
        elif friction and body.on_ground:
            body.vx *= max(0.0, 1.0 - GROUND_FRICTION * dt)
            if abs(body.vx) < STOP_THRESHOLD:
                body.vx = 0.0

        body.x += body.vx * dt
        body.y += body.vy * dt

        # Floor
        if body.y >= floor_y:
            if not body.on_ground and body.vy > MIN_BOUNCE_SPEED:
                body.vy = -body.vy * BOUNCE_DAMPING
                body.y = floor_y
                events["landed"] = True
            else:
                body.y = floor_y
                body.vy = 0.0
                if not body.on_ground:
                    events["landed"] = True
                body.on_ground = True
        else:
            body.on_ground = False

        # Screen edges
        if body.x <= left_bound:
            body.x = left_bound
            if body.vx < 0:
                body.vx = 0.0
            events["hit_left"] = True
        elif body.x >= right_bound:
            body.x = right_bound
            if body.vx > 0:
                body.vx = 0.0
            events["hit_right"] = True

        return events

    def is_moving(self) -> bool:
        return abs(self.body.vx) > STOP_THRESHOLD or not self.body.on_ground
