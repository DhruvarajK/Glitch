"""Glitch's local emotional state.

This lives under `core/ai` because the AI layer reads and writes it, but it is
deliberately independent of it: emotions drift and respond to interaction with
no network involved.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Callable

from core.utils.logger import get_logger

log = get_logger("emotion")

# Value every trait drifts back toward when nothing is happening.
BASELINE = {
    "happiness": 0.6,
    "energy": 0.7,
    "curiosity": 0.5,
    "annoyance": 0.0,
    "sleepiness": 0.0,
    "affection": 0.4,
}

# How fast each trait returns to baseline, in units per second.
DRIFT_RATE = {
    "happiness": 0.004,
    "energy": 0.002,
    "curiosity": 0.006,
    "annoyance": 0.010,
    "sleepiness": 0.000,  # sleepiness is driven by activity, not drift
    "affection": 0.002,
}

# Sleepiness accrues while awake and clears while asleep.
SLEEPINESS_PER_SECOND = 0.0015
SLEEP_RECOVERY_PER_SECOND = 0.02

# Emotional responses to interaction, applied as deltas.
REACTIONS: dict[str, dict[str, float]] = {
    "clicked": {"happiness": 0.05, "affection": 0.03, "sleepiness": -0.05, "energy": 0.02},
    "click_spam": {"annoyance": 0.12, "happiness": -0.04},
    "dragged": {"annoyance": 0.10, "energy": -0.02},
    "dropped": {"annoyance": 0.05, "happiness": -0.02},
    "talked_to": {"happiness": 0.04, "curiosity": 0.05, "affection": 0.04, "sleepiness": -0.1},
    "ignored": {"happiness": -0.02, "curiosity": 0.02},
    "slept": {"annoyance": -0.2},
    "woke": {"energy": 0.25, "sleepiness": -0.6},
    "walked": {"energy": -0.01, "curiosity": -0.02},
    "played": {"happiness": 0.08, "energy": -0.05},
}


@dataclass
class EmotionState:
    """Six traits, each clamped to 0.0-1.0."""

    happiness: float = BASELINE["happiness"]
    energy: float = BASELINE["energy"]
    curiosity: float = BASELINE["curiosity"]
    annoyance: float = BASELINE["annoyance"]
    sleepiness: float = BASELINE["sleepiness"]
    affection: float = BASELINE["affection"]

    def as_dict(self) -> dict[str, float]:
        return {k: round(v, 3) for k, v in asdict(self).items()}

    @classmethod
    def trait_names(cls) -> list[str]:
        return [f.name for f in fields(cls)]


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


class EmotionEngine:
    """Applies deltas, drifts traits back to baseline and reports a mood."""

    def __init__(self, state: EmotionState | None = None) -> None:
        self.state = state or EmotionState()
        self.on_change: Callable[[EmotionState], None] | None = None
        self._since_notify = 0.0

    # -------------------------------------------------------------- updating
    def update(self, dt: float, *, asleep: bool = False) -> None:
        for name in EmotionState.trait_names():
            current = getattr(self.state, name)
            target = BASELINE[name]
            rate = DRIFT_RATE[name]
            if current > target:
                current = max(target, current - rate * dt)
            elif current < target:
                current = min(target, current + rate * dt)
            setattr(self.state, name, current)

        if asleep:
            self.state.sleepiness = _clamp(
                self.state.sleepiness - SLEEP_RECOVERY_PER_SECOND * dt
            )
            self.state.energy = _clamp(self.state.energy + SLEEP_RECOVERY_PER_SECOND * dt)
        else:
            self.state.sleepiness = _clamp(
                self.state.sleepiness + SLEEPINESS_PER_SECOND * dt
            )

        # Notify at most once a second; nothing needs sub-second resolution.
        self._since_notify += dt
        if self._since_notify >= 1.0:
            self._since_notify = 0.0
            if self.on_change:
                self.on_change(self.state)

    def apply(self, reaction: str, scale: float = 1.0) -> None:
        """Apply a named interaction, e.g. 'clicked' or 'dragged'."""
        deltas = REACTIONS.get(reaction)
        if deltas is None:
            log.debug("Unknown emotional reaction %r", reaction)
            return
        self.adjust({k: v * scale for k, v in deltas.items()})

    def adjust(self, deltas: dict[str, float]) -> None:
        for name, delta in deltas.items():
            if not hasattr(self.state, name):
                continue
            setattr(self.state, name, _clamp(getattr(self.state, name) + float(delta)))
        if self.on_change:
            self.on_change(self.state)

    def set_trait(self, name: str, value: float) -> None:
        if hasattr(self.state, name):
            setattr(self.state, name, _clamp(float(value)))

    # --------------------------------------------------------------- reading
    def mood(self) -> str:
        """A single word summarising the current blend, for prompts and logs."""
        s = self.state
        if s.sleepiness > 0.75:
            return "sleepy"
        if s.annoyance > 0.6:
            return "annoyed"
        if s.happiness > 0.75 and s.energy > 0.6:
            return "excited"
        if s.happiness > 0.65:
            return "happy"
        if s.happiness < 0.3:
            return "gloomy"
        if s.curiosity > 0.7:
            return "curious"
        if s.energy < 0.3:
            return "tired"
        return "content"

    def reaction_animation(self) -> str:
        """Pick a reaction clip that matches how Glitch currently feels."""
        return {
            "sleepy": "yawn",
            "annoyed": "annoyed",
            "excited": "excited",
            "happy": "happy",
            "gloomy": "sad",
            "curious": "curious",
            "tired": "deadpan",
            "content": "happy",
        }.get(self.mood(), "happy")
