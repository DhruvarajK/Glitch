"""Running a recognised instruction and deciding what Glitch says about it.

Every branch here answers locally. Nothing in this module reaches the network,
so the whole action layer costs nothing to run and works with no API key.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from core.tools.activity import ActivityTracker
from core.tools.intents import ToolCall
from core.tools.launcher import AppLauncher
from core.tools.reminders import ReminderService, describe_delay
from core.utils.logger import get_logger

log = get_logger("tools")


@dataclass(frozen=True)
class ToolResult:
    """What the pet should say and do, having carried out an instruction."""

    message: str
    animation: str = "happy"
    emotion: dict[str, float] | None = None


_REMINDER_ACKS = (
    "Got it. {delay} from now: {text}.",
    "Noted. I'll nag you about {text} in {delay}.",
    "{delay}. {text}. I won't forget.",
)


class ToolRunner:
    """Dispatches a ToolCall to the thing that carries it out."""

    def __init__(
        self,
        reminders: ReminderService,
        launcher: AppLauncher,
        activity: ActivityTracker,
        *,
        on_quiet: "callable | None" = None,
        rng: random.Random | None = None,
    ) -> None:
        self.reminders = reminders
        self.launcher = launcher
        self.activity = activity
        self.on_quiet = on_quiet
        self.rng = rng or random.Random()

    def run(self, call: ToolCall) -> ToolResult | None:
        """Carry out `call`, or None when the instruction is not one of ours."""
        handler = getattr(self, f"_run_{call.name}", None)
        if handler is None:
            log.debug("No handler for tool %r", call.name)
            return None
        try:
            return handler(call)
        except Exception:
            log.exception("Tool %r failed", call.name)
            return ToolResult("That went wrong on my end.", animation="confused")

    # ------------------------------------------------------------- handlers
    def _run_remind(self, call: ToolCall) -> ToolResult:
        subject = call.text.strip() or "that thing"
        reminder = self.reminders.add(subject, call.minutes)
        if reminder is None:
            return ToolResult(
                "I can't keep reminders right now - my storage isn't working.",
                animation="sad",
            )
        template = self.rng.choice(_REMINDER_ACKS)
        return ToolResult(
            template.format(delay=describe_delay(call.minutes), text=subject),
            animation="smug",
            emotion={"happiness": 0.04, "curiosity": 0.02},
        )

    def _run_remind_needs_time(self, call: ToolCall) -> ToolResult:
        subject = call.text.strip()
        about = f" about {subject}" if subject else ""
        return ToolResult(
            f"When? Tell me{about} again with a time, like 'in 20 minutes'.",
            animation="confused",
        )

    def _run_open_app(self, call: ToolCall) -> ToolResult:
        result = self.launcher.launch(call.text)
        return ToolResult(
            result.message,
            animation="excited" if result.ok else "confused",
            emotion={"energy": 0.04} if result.ok else None,
        )

    def _run_stats(self, call: ToolCall) -> ToolResult:
        current = self.activity.current()
        summary = self.activity.summary()
        message = f"Right now: {current}. {summary}" if current else summary
        return ToolResult(message, animation="think")

    def _run_quiet(self, call: ToolCall) -> ToolResult:
        minutes = max(1.0, call.minutes)
        if self.on_quiet:
            self.on_quiet(minutes)
        return ToolResult(
            f"Fine. Quiet for {describe_delay(minutes)}.",
            animation="deadpan",
            emotion={"annoyance": 0.05, "happiness": -0.02},
        )

    def _run_unquiet(self, call: ToolCall) -> ToolResult:
        if self.on_quiet:
            self.on_quiet(0.0)
        return ToolResult(
            "Finally. I had so much to say.",
            animation="excited",
            emotion={"happiness": 0.06, "energy": 0.05},
        )
