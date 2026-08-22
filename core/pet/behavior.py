"""Autonomous behaviour: what Glitch decides to do when left alone.

Decisions here are cheap, local and made a few times a second at most. No
language model is involved — this is what keeps the pet alive offline.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from core.ai.emotion import EmotionState
from core.persistence.config import ConfigManager
from core.pet.state import PetState
from core.utils.logger import get_logger

log = get_logger("behavior")

# Base weights, before emotional modulation. Configurable via reaction_frequency.
BASE_WEIGHTS: dict[str, float] = {
    "stay": 44.0,   # keep doing whatever is happening
    "blink": 25.0,  # idle clip already blinks; this is a deliberate no-op
    "look": 10.0,
    "walk": 8.0,
    "sit": 5.0,
    "stretch": 3.0,
    "play": 2.0,
    "yawn": 2.0,
    "sleep": 1.0,
}

# How long a decision is committed to before the next roll, in seconds.
DECISION_INTERVAL = (1.5, 5.0)


@dataclass
class BehaviorIntent:
    """What the behaviour engine would like to happen next."""

    action: str
    data: dict = field(default_factory=dict)


class BehaviorController:
    """Rolls weighted decisions, biased by the current emotional state."""

    def __init__(self, config: ConfigManager, rng: random.Random | None = None) -> None:
        self.config = config
        self.rng = rng or random.Random()
        self._next_decision = self.rng.uniform(*DECISION_INTERVAL)
        self._elapsed = 0.0
        self.paused = False

    # -------------------------------------------------------------- weights
    def weights_for(self, emotion: EmotionState) -> dict[str, float]:
        """Modulate the base table by how Glitch feels right now."""
        frequency = float(self.config.get("reaction_frequency", 1.0))
        weights = dict(BASE_WEIGHTS)

        # Energy drives movement; tiredness drives resting.
        weights["walk"] *= 0.4 + emotion.energy * 2.0
        weights["play"] *= 0.3 + emotion.energy * 1.8
        weights["stretch"] *= 0.5 + emotion.energy

        weights["sit"] *= 0.5 + emotion.sleepiness * 2.5
        weights["yawn"] *= 0.2 + emotion.sleepiness * 4.0
        weights["sleep"] *= 0.05 + emotion.sleepiness * 6.0

        # Curiosity makes Glitch look around and wander further.
        weights["look"] *= 0.4 + emotion.curiosity * 2.0
        weights["walk"] *= 0.7 + emotion.curiosity * 0.8

        # Annoyance suppresses playfulness.
        weights["play"] *= max(0.1, 1.0 - emotion.annoyance)

        # Reaction frequency scales everything except staying put.
        for key in list(weights):
            if key not in ("stay", "blink"):
                weights[key] *= frequency

        if not self.config.get("autonomous_movement", True):
            weights["walk"] = 0.0
        if not self.config.get("sleep_enabled", True):
            weights["sleep"] = 0.0
        return weights

    # ------------------------------------------------------------- decisions
    def update(
        self, dt: float, state: PetState, emotion: EmotionState
    ) -> BehaviorIntent | None:
        """Advance the decision timer; returns an intent when one is due."""
        if self.paused:
            return None
        self._elapsed += dt
        if self._elapsed < self._next_decision:
            return None

        self._elapsed = 0.0
        self._next_decision = self.rng.uniform(*DECISION_INTERVAL)
        return self.decide(state, emotion)

    def decide(self, state: PetState, emotion: EmotionState) -> BehaviorIntent | None:
        weights = self.weights_for(emotion)

        # Already asleep: only a strong reason wakes Glitch on its own.
        if state is PetState.SLEEPING:
            if emotion.sleepiness < 0.15 or emotion.energy > 0.8:
                return BehaviorIntent("wake")
            return None

        # Walking is a commitment; let it finish rather than re-rolling.
        if state in (PetState.WALKING, PetState.RUNNING):
            if self.rng.random() < 0.15:
                return BehaviorIntent("stop")
            return None

        choices = [k for k, v in weights.items() if v > 0]
        if not choices:
            return None
        action = self.rng.choices(choices, weights=[weights[k] for k in choices])[0]

        if action in ("stay", "blink"):
            return None
        if action == "walk":
            return BehaviorIntent(
                "walk",
                {
                    "run": emotion.energy > 0.8 and self.rng.random() < 0.3,
                    "distance": self.rng.uniform(0.15, 0.75),
                    "direction": self.rng.choice((-1, 1)),
                },
            )
        if action == "play":
            return BehaviorIntent("react", {"animation": self._playful_animation(emotion)})
        log.debug("Behaviour chose %s", action)
        return BehaviorIntent(action)

    def _playful_animation(self, emotion: EmotionState) -> str:
        pool = ["excited", "mischievous", "laughing", "smug", "amazed"]
        if emotion.affection > 0.7:
            pool.append("love")
        if emotion.curiosity > 0.7:
            pool.append("suspicious")
        return self.rng.choice(pool)

    def force_decision_soon(self, seconds: float = 0.5) -> None:
        """Shorten the wait before the next roll, e.g. after an interaction."""
        self._elapsed = 0.0
        self._next_decision = seconds
