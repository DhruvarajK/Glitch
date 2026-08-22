"""Validated shapes for everything the model is allowed to tell us.

Free-form text is never trusted: the model returns JSON matching this schema,
and anything that fails validation is replaced by a safe fallback.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

# Emotions the model may pick from. Each maps onto an animation in the manifest.
EMOTIONS = (
    "neutral",
    "happy",
    "amused",
    "sad",
    "angry",
    "confused",
    "surprised",
    "sleepy",
    "excited",
    "curious",
)

# Actions the model may request of the pet runtime.
ACTIONS = ("talk", "idle", "laugh", "look", "celebrate", "sleep")

Emotion = Literal[
    "neutral", "happy", "amused", "sad", "angry",
    "confused", "surprised", "sleepy", "excited", "curious",
]
Action = Literal["talk", "idle", "laugh", "look", "celebrate", "sleep"]

# How each emotion and action maps onto the animation manifest.
EMOTION_ANIMATION: dict[str, str] = {
    "neutral": "idle",
    "happy": "happy",
    "amused": "amused",
    "sad": "sad",
    "angry": "angry",
    "confused": "confused",
    "surprised": "surprised",
    "sleepy": "yawn",
    "excited": "excited",
    "curious": "curious",
}

ACTION_ANIMATION: dict[str, str] = {
    "talk": "talk",
    "idle": "idle",
    "laugh": "laughing",
    "look": "look",
    "celebrate": "excited",
    "sleep": "sleep",
}

# Deltas applied to the emotional state when the model reports a feeling.
EMOTION_EFFECTS: dict[str, dict[str, float]] = {
    "happy": {"happiness": 0.06, "affection": 0.02},
    "amused": {"happiness": 0.05, "energy": 0.02},
    "sad": {"happiness": -0.06},
    "angry": {"annoyance": 0.10, "happiness": -0.04},
    "confused": {"curiosity": 0.05},
    "surprised": {"curiosity": 0.06, "energy": 0.03},
    "sleepy": {"sleepiness": 0.08, "energy": -0.04},
    "excited": {"happiness": 0.07, "energy": 0.08},
    "curious": {"curiosity": 0.08},
    "neutral": {},
}


class AIResponse(BaseModel):
    """A single structured reply from Glitch's brain."""

    message: str = Field(min_length=1, max_length=1200)
    emotion: Emotion = "neutral"
    intensity: float = Field(default=0.5, ge=0.0, le=1.0)
    action: Action = "talk"

    @field_validator("message")
    @classmethod
    def _strip(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("message is empty")
        return cleaned

    def animation(self) -> str:
        """The clip to play: the action wins when it is more specific."""
        if self.action in ("laugh", "celebrate", "look", "sleep"):
            return ACTION_ANIMATION[self.action]
        return EMOTION_ANIMATION.get(self.emotion, "talk")

    def emotion_deltas(self) -> dict[str, float]:
        effects = EMOTION_EFFECTS.get(self.emotion, {})
        return {k: v * max(0.2, self.intensity) for k, v in effects.items()}

    @classmethod
    def fallback(cls, message: str, emotion: str = "confused") -> "AIResponse":
        return cls(message=message, emotion=emotion, intensity=0.4, action="talk")


# JSON schema handed to the API so the model is constrained at generation time.
RESPONSE_JSON_SCHEMA: dict = {
    "name": "glitch_reply",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["message", "emotion", "intensity", "action"],
        "properties": {
            "message": {
                "type": "string",
                "description": "What Glitch says out loud. Short and conversational.",
            },
            "emotion": {"type": "string", "enum": list(EMOTIONS)},
            "intensity": {
                "type": "number",
                "description": "How strongly the emotion is felt, from 0 to 1.",
            },
            "action": {"type": "string", "enum": list(ACTIONS)},
        },
    },
}
