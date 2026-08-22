"""The vocabulary of things Glitch can be doing."""
from __future__ import annotations

from enum import Enum


class PetState(str, Enum):
    IDLE = "idle"
    WALKING = "walking"
    RUNNING = "running"
    LOOKING = "looking"
    SITTING = "sitting"
    THINKING = "thinking"
    TALKING = "talking"
    REACTING = "reacting"
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    CONFUSED = "confused"
    SLEEPING = "sleeping"
    WAKING = "waking"
    DRAGGED = "dragged"
    DROPPED = "dropped"


# Higher priority states may interrupt lower ones. A state never interrupts
# itself or an equal-priority state unless the transition is forced.
STATE_PRIORITY: dict[PetState, int] = {
    PetState.IDLE: 10,
    PetState.SITTING: 15,
    PetState.WALKING: 20,
    PetState.RUNNING: 25,
    PetState.LOOKING: 30,
    PetState.SLEEPING: 50,
    PetState.TALKING: 60,
    PetState.REACTING: 70,
    PetState.HAPPY: 70,
    PetState.SAD: 70,
    PetState.ANGRY: 70,
    PetState.CONFUSED: 70,
    PetState.WAKING: 75,
    PetState.THINKING: 80,
    PetState.DROPPED: 90,
    PetState.DRAGGED: 100,
}

# Default animation for each state. Reactions carry their own animation and
# override this at transition time.
STATE_ANIMATION: dict[PetState, str] = {
    PetState.IDLE: "idle",
    PetState.WALKING: "walk",
    PetState.RUNNING: "run",
    PetState.LOOKING: "look",
    PetState.SITTING: "sit",
    PetState.THINKING: "think",
    PetState.TALKING: "talk",
    PetState.REACTING: "happy",
    PetState.HAPPY: "happy",
    PetState.SAD: "sad",
    PetState.ANGRY: "angry",
    PetState.CONFUSED: "confused",
    PetState.SLEEPING: "sleep",
    PetState.WAKING: "wake",
    PetState.DRAGGED: "drag",
    PetState.DROPPED: "drop",
}

# States that end on their own once the animation finishes.
TRANSIENT_STATES = frozenset(
    {
        PetState.LOOKING,
        PetState.REACTING,
        PetState.HAPPY,
        PetState.SAD,
        PetState.ANGRY,
        PetState.CONFUSED,
        PetState.WAKING,
        PetState.DROPPED,
    }
)

# States during which Glitch does not move under its own power.
STATIONARY_STATES = frozenset(
    {
        PetState.IDLE,
        PetState.SITTING,
        PetState.LOOKING,
        PetState.THINKING,
        PetState.TALKING,
        PetState.REACTING,
        PetState.HAPPY,
        PetState.SAD,
        PetState.ANGRY,
        PetState.CONFUSED,
        PetState.SLEEPING,
        PetState.WAKING,
        PetState.DRAGGED,
        PetState.DROPPED,
    }
)

# States the autonomous behaviour engine is allowed to interrupt.
BEHAVIOUR_STATES = frozenset(
    {PetState.IDLE, PetState.WALKING, PetState.RUNNING, PetState.SITTING}
)
