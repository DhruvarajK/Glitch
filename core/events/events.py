"""Event vocabulary shared between subsystems."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EventType(str, Enum):
    # User interaction
    USER_CLICKED = "user.clicked"
    USER_DOUBLE_CLICKED = "user.double_clicked"
    USER_RIGHT_CLICKED = "user.right_clicked"
    USER_DRAG_STARTED = "user.drag_started"
    USER_DRAGGED = "user.dragged"
    USER_DRAG_ENDED = "user.drag_ended"
    USER_MESSAGE = "user.message"

    # AI
    AI_REQUEST_STARTED = "ai.request_started"
    AI_TOKEN_RECEIVED = "ai.token_received"
    AI_RESPONSE_RECEIVED = "ai.response_received"
    AI_REQUEST_FAILED = "ai.request_failed"
    AI_REQUEST_CANCELLED = "ai.request_cancelled"

    # Pet runtime
    PET_STATE_CHANGED = "pet.state_changed"
    PET_POSITION_CHANGED = "pet.position_changed"
    PET_WENT_TO_SLEEP = "pet.slept"
    PET_WOKE_UP = "pet.woke"
    PET_EMOTION_CHANGED = "pet.emotion_changed"

    # Animation
    ANIMATION_STARTED = "animation.started"
    ANIMATION_FINISHED = "animation.finished"

    # Awareness (what Glitch notices about the machine around it)
    ENV_APP_LAUNCHED = "env.app_launched"
    ENV_APP_FOCUSED = "env.app_focused"
    ENV_FOCUS_SESSION = "env.focus_session"
    ENV_USER_IDLE = "env.user_idle"
    ENV_USER_RETURNED = "env.user_returned"
    ENV_LATE_NIGHT = "env.late_night"
    ENV_BATTERY_LOW = "env.battery_low"
    PET_SPOKE_UNPROMPTED = "pet.spoke_unprompted"

    # Actions Glitch carried out locally
    TOOL_PERFORMED = "tool.performed"
    REMINDER_FIRED = "tool.reminder_fired"

    # Environment / app
    SCREEN_CONFIGURATION_CHANGED = "screen.configuration_changed"
    CONFIG_CHANGED = "app.config_changed"
    APP_SHUTDOWN = "app.shutdown"


@dataclass
class Event:
    """An event plus its payload. Handlers should treat payloads as read-only."""

    type: EventType
    data: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)
