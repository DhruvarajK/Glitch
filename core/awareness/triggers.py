"""What Glitch does about what it noticed, and how often it is allowed to.

Two tiers of reaction:

* **Local** - a canned line and a clip. Free, instant, works offline.
* **AI** - the situation (never a window title) is handed to the brain, which
  writes the line. Rare by design, because every one costs a request.

The governor is the important half. An unprompted pet that speaks whenever it
can is unbearable within an hour, so speech is rationed by a global cooldown,
a per-trigger cooldown and a daily budget.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from core.awareness.apps import label_for
from core.awareness.signals import Signal

# Reactions that only emote are cheap; they get their own shorter cooldown.
SILENT_COOLDOWN = 90.0


@dataclass(frozen=True)
class Trigger:
    """A reaction template for one signal key."""

    key: str
    animation: str | None = None
    lines: tuple[str, ...] = ()
    situation: str | None = None          # what the AI is told, if AI is on
    cooldown: float = 3600.0              # per-trigger, in seconds
    speaks: bool = True
    emotion: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class Reaction:
    """A decision the governor approved. The application performs it."""

    trigger: str
    animation: str | None = None
    line: str | None = None               # a canned line, ready to show
    situation: str | None = None          # ask the brain instead, if set
    emotion: dict[str, float] = field(default_factory=dict)

    @property
    def speaks(self) -> bool:
        return bool(self.line or self.situation)


# --------------------------------------------------------------- the table
# Keys match Signal.key. Category-specific launches fall back to "launch:*".
TRIGGERS: dict[str, Trigger] = {
    "launch:coding": Trigger(
        key="launch:coding",
        animation="mischievous",
        lines=(
            "Oh, we are writing code today. I will be over here judging silently.",
            "Editor is open. Try not to break anything important.",
        ),
        situation="the user just opened a code editor",
        emotion={"curiosity": 0.06, "energy": 0.04},
    ),
    "launch:music": Trigger(
        key="launch:music",
        animation="dance",
        lines=("Music! Okay, I am dancing now, you cannot stop me.", "Ooh, is this a good one?"),
        situation="the user just started a music player",
        emotion={"happiness": 0.08, "energy": 0.06},
    ),
    "launch:gaming": Trigger(
        key="launch:gaming",
        animation="excited",
        lines=("Games? Excellent. Productivity was overrated.",),
        situation="the user just opened a game launcher",
        emotion={"happiness": 0.07, "energy": 0.07},
    ),
    "launch:terminal": Trigger(
        key="launch:terminal",
        animation="smug",
        lines=("A terminal. Very serious. Very cool.",),
        situation="the user just opened a terminal",
        emotion={"curiosity": 0.05},
    ),
    "launch:design": Trigger(
        key="launch:design",
        animation="amazed",
        lines=("Ooh, making something pretty?",),
        situation="the user just opened a design or video editing app",
        emotion={"curiosity": 0.08},
    ),
    "launch:meeting": Trigger(
        key="launch:meeting",
        animation="hiding",
        lines=(),  # a call is starting: emote, do not talk over it
        speaks=False,
        emotion={"energy": -0.03},
    ),
    "launch:writing": Trigger(
        key="launch:writing",
        animation="think",
        lines=("Writing something? I will keep quiet. Mostly.",),
        situation="the user just opened a writing app",
        emotion={"curiosity": 0.05},
    ),
    "launch:*": Trigger(
        key="launch:*",
        animation="curious",
        lines=(),
        speaks=False,
        cooldown=600.0,
        emotion={"curiosity": 0.03},
    ),
    "focus_session": Trigger(
        key="focus_session",
        animation="stretch",
        lines=(
            "You have been at that for a while. Blink? Water? Anything?",
            "Long stretch on this one. Stretch with me for a sec.",
        ),
        situation=(
            "the user has been focused on the same kind of app for a long "
            "stretch without a break - nudge them to rest their eyes, warmly "
            "and briefly, without nagging"
        ),
        cooldown=2700.0,
        emotion={"affection": 0.05},
    ),
    "user_returned": Trigger(
        key="user_returned",
        animation="love",
        lines=("You are back! I kept your seat warm.", "There you are. I got bored."),
        situation="the user just came back to the computer after being away a while",
        cooldown=1800.0,
        emotion={"happiness": 0.08, "affection": 0.06, "sleepiness": -0.1},
    ),
    "user_idle": Trigger(
        key="user_idle",
        animation="sit",
        lines=(),
        speaks=False,   # nobody is there to read it
        cooldown=1800.0,
        emotion={"energy": -0.04},
    ),
    "late_night": Trigger(
        key="late_night",
        animation="yawn",
        lines=("It is very late. I am not your parent, but... it is very late.",),
        situation="it is the small hours of the morning and the user is still up",
        cooldown=21600.0,
        emotion={"sleepiness": 0.15},
    ),
    "battery_low": Trigger(
        key="battery_low",
        animation="scared",
        lines=("Battery is getting low. I would rather not blink out of existence.",),
        situation="the laptop battery is nearly empty and is not charging",
        cooldown=1800.0,
        emotion={"energy": -0.05},
    ),
}


def trigger_for(signal: Signal) -> Trigger | None:
    """The trigger for a signal, falling back to the generic launch rule."""
    trigger = TRIGGERS.get(signal.key)
    if trigger is None and signal.key.startswith("launch:"):
        trigger = TRIGGERS.get("launch:*")
    return trigger


class TriggerGovernor:
    """Decides whether a signal is allowed to become a reaction, and how loud.

    Time is passed in rather than read from the clock so the rationing is
    testable without waiting an hour.
    """

    def __init__(
        self,
        *,
        global_cooldown: float = 600.0,
        daily_limit: int = 6,
        rng: random.Random | None = None,
    ) -> None:
        self.global_cooldown = global_cooldown
        self.daily_limit = daily_limit
        self.rng = rng or random.Random()
        self._last_spoke_at: float | None = None
        self._last_emoted_at: float | None = None
        self._fired_at: dict[str, float] = {}
        self._spoken_today = 0
        self._day: int | None = None

    # ------------------------------------------------------------- budgeting
    @property
    def spoken_today(self) -> int:
        return self._spoken_today

    def remaining_today(self) -> int:
        return max(0, self.daily_limit - self._spoken_today)

    def _roll_day(self, day: int) -> None:
        if self._day != day:
            self._day = day
            self._spoken_today = 0

    def _cooled_down(self, last: float | None, now: float, interval: float) -> bool:
        return last is None or now - last >= interval

    # -------------------------------------------------------------- decision
    def consider(
        self,
        signal: Signal,
        now: float,
        day: int,
        *,
        ai_enabled: bool = False,
    ) -> Reaction | None:
        """Approve at most one reaction, downgrading to silence when rationed."""
        self._roll_day(day)
        trigger = trigger_for(signal)
        if trigger is None:
            return None

        if not self._cooled_down(self._fired_at.get(trigger.key), now, trigger.cooldown):
            return None

        wants_to_speak = trigger.speaks and (bool(trigger.lines) or bool(trigger.situation))
        may_speak = (
            wants_to_speak
            and self.remaining_today() > 0
            and self._cooled_down(self._last_spoke_at, now, self.global_cooldown)
        )

        if not may_speak:
            # Still worth an expression: silent reactions are far cheaper, so
            # they only wait out the short cooldown.
            if trigger.animation is None:
                return None
            if not self._cooled_down(self._last_emoted_at, now, SILENT_COOLDOWN):
                return None
            self._fired_at[trigger.key] = now
            self._last_emoted_at = now
            return Reaction(
                trigger=trigger.key,
                animation=trigger.animation,
                emotion=dict(trigger.emotion),
            )

        line: str | None = None
        situation: str | None = None
        if ai_enabled and trigger.situation:
            situation = self._describe(trigger, signal)
        elif trigger.lines:
            line = self.rng.choice(list(trigger.lines))
        elif trigger.situation:
            situation = self._describe(trigger, signal)

        self._fired_at[trigger.key] = now
        self._last_spoke_at = now
        self._last_emoted_at = now
        self._spoken_today += 1
        return Reaction(
            trigger=trigger.key,
            animation=trigger.animation,
            line=line,
            situation=situation,
            emotion=dict(trigger.emotion),
        )

    def _describe(self, trigger: Trigger, signal: Signal) -> str:
        """Flesh out the situation with what the signal carried."""
        situation = trigger.situation or ""
        if signal.key == "user_returned":
            minutes = int(signal.data.get("away_minutes", 0))
            if minutes:
                situation += f" (about {minutes} minutes)"
        elif signal.key == "focus_session":
            minutes = int(signal.data.get("minutes", 0))
            if minutes:
                situation += f" ({minutes} minutes on {label_for(signal.subject)})"
        elif signal.key == "battery_low":
            percent = signal.data.get("percent")
            if percent is not None:
                situation += f" ({int(percent)}% left)"
        return situation

    def reset(self) -> None:
        self._last_spoke_at = None
        self._last_emoted_at = None
        self._fired_at.clear()
        self._spoken_today = 0
        self._day = None
