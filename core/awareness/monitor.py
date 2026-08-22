"""Turns readings of the machine into signals, and signals into one reaction.

Detection is deliberately pure: `detect()` compares two snapshots and returns
what changed, with no clock, no Qt and no side effects, so the whole ruleset is
testable by handing it fabricated snapshots.
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QObject, QTimer

from core.awareness.apps import categorise, is_quiet
from core.awareness.sensors import Sensor, create_sensor
from core.awareness.signals import Signal, Snapshot
from core.awareness.triggers import Reaction, TriggerGovernor
from core.events.bus import EventBus
from core.events.events import EventType
from core.persistence.config import ConfigManager
from core.utils.logger import get_logger

log = get_logger("awareness")

# How often the machine is read. Slow enough to be invisible in Task Manager.
POLL_INTERVAL_MS = 2000

# Away for this long counts as having left the desk.
IDLE_THRESHOLD = 300.0
# An unbroken stretch on one kind of app worth mentioning.
FOCUS_SESSION_SECONDS = 2700.0
# Below this, on battery, is worth a warning.
BATTERY_THRESHOLD = 15.0
# The small hours, for the late-night nudge.
LATE_NIGHT_HOURS = range(1, 5)

SIGNAL_EVENTS: dict[str, EventType] = {
    "focus_session": EventType.ENV_FOCUS_SESSION,
    "user_idle": EventType.ENV_USER_IDLE,
    "user_returned": EventType.ENV_USER_RETURNED,
    "late_night": EventType.ENV_LATE_NIGHT,
    "battery_low": EventType.ENV_BATTERY_LOW,
}


class EnvironmentMonitor(QObject):
    """Polls a sensor, detects change, and asks the governor what to do.

    The application supplies `suppressed` so the pet stays quiet while it is
    asleep, hidden, mid-conversation or already busy.
    """

    def __init__(
        self,
        config: ConfigManager,
        bus: EventBus,
        *,
        sensor: Sensor | None = None,
        governor: TriggerGovernor | None = None,
        on_reaction: Callable[[Reaction], None] | None = None,
        suppressed: Callable[[], bool] | None = None,
    ) -> None:
        super().__init__()
        self.config = config
        self.bus = bus
        self.on_reaction = on_reaction
        self.suppressed = suppressed or (lambda: False)

        self.sensor = sensor or create_sensor(
            read_titles=bool(config.get("awareness_read_window_titles", False))
        )
        self.governor = governor or TriggerGovernor(
            global_cooldown=float(config.get("proactive_cooldown_seconds", 600.0)),
            daily_limit=int(config.get("proactive_daily_limit", 6)),
        )

        self._previous: Snapshot | None = None
        self._focus_category: str | None = None
        self._focus_since: float | None = None
        self._focus_announced = False
        self._idle_since: float | None = None
        self._was_idle = False
        self._late_night_day: int | None = None

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.poll)
        config.on_change(self._on_config_changed)

    # ------------------------------------------------------------ lifecycle
    @property
    def enabled(self) -> bool:
        return bool(self.config.get("awareness_enabled", True))

    def start(self) -> None:
        if not self.enabled:
            log.info("Awareness is disabled")
            return
        # Prime the baseline so the apps already running are not reported as
        # having just launched the moment Glitch starts.
        self._previous = self._read()
        self._timer.start(POLL_INTERVAL_MS)
        log.info("Awareness started (detailed=%s)", self.sensor.detailed)

    def stop(self) -> None:
        self._timer.stop()
        self.sensor.close()

    def _on_config_changed(self, key: str, value: object) -> None:
        if key == "awareness_enabled":
            self.start() if value else self.stop()
        elif key == "proactive_cooldown_seconds":
            self.governor.global_cooldown = float(value)  # type: ignore[arg-type]
        elif key == "proactive_daily_limit":
            self.governor.daily_limit = int(value)  # type: ignore[arg-type]
        elif key == "awareness_read_window_titles":
            self.sensor.close()
            self.sensor = create_sensor(read_titles=bool(value))

    def _read(self) -> Snapshot:
        try:
            return self.sensor.snapshot()
        except Exception:
            log.exception("Sensor failed; skipping this reading")
            return Snapshot()

    # ----------------------------------------------------------------- poll
    def poll(self) -> Reaction | None:
        """One cycle: read, detect, publish, and maybe react."""
        if not self.enabled:
            return None
        current = self._read()
        previous, self._previous = self._previous, current
        if previous is None:
            return None

        signals = self.detect(previous, current)
        for signal in signals:
            self._publish(signal)

        if not signals or self.suppressed():
            return None
        # A fullscreen window means a game, a call or a presentation. Emoting
        # behind it is pointless and interrupting it is rude.
        if current.fullscreen or is_quiet(categorise(current.foreground)):
            return None

        for signal in signals:
            reaction = self.governor.consider(
                signal,
                current.at,
                current.day,
                ai_enabled=bool(self.config.get("awareness_ai_replies", False)),
            )
            if reaction is not None:
                log.info("Reacting to %s", reaction.trigger)
                if self.on_reaction:
                    self.on_reaction(reaction)
                return reaction  # one reaction per poll, at most
        return None

    def _publish(self, signal: Signal) -> None:
        event = SIGNAL_EVENTS.get(signal.key)
        if event is None and signal.key.startswith("launch:"):
            event = EventType.ENV_APP_LAUNCHED
        if event is None:
            return
        self.bus.emit(event, category=signal.subject, **signal.data)

    # ------------------------------------------------------------- detection
    def detect(self, previous: Snapshot, current: Snapshot) -> list[Signal]:
        """Everything that changed between two readings, most urgent first."""
        signals: list[Signal] = []
        signals.extend(self._detect_idle(previous, current))
        signals.extend(self._detect_launches(previous, current))
        signals.extend(self._detect_focus(previous, current))
        signals.extend(self._detect_battery(previous, current))
        signals.extend(self._detect_late_night(current))
        return signals

    def _detect_launches(self, previous: Snapshot, current: Snapshot) -> list[Signal]:
        started = current.running - previous.running
        signals: list[Signal] = []
        for process in sorted(started):
            category = categorise(process)
            if category is None:
                continue  # unrecognised apps are none of Glitch's business
            signals.append(Signal(f"launch:{category}", subject=category))
        return signals

    def _detect_focus(self, previous: Snapshot, current: Snapshot) -> list[Signal]:
        """Track how long one kind of app has held the foreground."""
        category = categorise(current.foreground)
        if category != self._focus_category:
            self._focus_category = category
            self._focus_since = current.at if category else None
            self._focus_announced = False
            if category:
                self.bus.emit(EventType.ENV_APP_FOCUSED, category=category)
            return []

        if category is None or self._focus_since is None or self._focus_announced:
            return []
        elapsed = current.at - self._focus_since
        if elapsed < FOCUS_SESSION_SECONDS:
            return []
        self._focus_announced = True
        return [
            Signal(
                "focus_session",
                subject=category,
                data={"minutes": int(elapsed // 60)},
            )
        ]

    def _detect_idle(self, previous: Snapshot, current: Snapshot) -> list[Signal]:
        idle_now = current.idle_seconds >= IDLE_THRESHOLD
        if idle_now and not self._was_idle:
            self._was_idle = True
            self._idle_since = current.at
            return [Signal("user_idle", data={"seconds": int(current.idle_seconds)})]
        if not idle_now and self._was_idle:
            self._was_idle = False
            away = previous.idle_seconds
            self._idle_since = None
            # A long focus stretch does not survive the user leaving the desk.
            self._focus_since = current.at if self._focus_category else None
            self._focus_announced = False
            return [
                Signal("user_returned", data={"away_minutes": int(away // 60)})
            ]
        return []

    def _detect_battery(self, previous: Snapshot, current: Snapshot) -> list[Signal]:
        if current.battery_percent is None or current.battery_charging:
            return []
        if current.battery_percent > BATTERY_THRESHOLD:
            return []
        was_fine = (
            previous.battery_percent is None
            or previous.battery_percent > BATTERY_THRESHOLD
            or bool(previous.battery_charging)
        )
        if not was_fine:
            return []  # already warned on the way down
        return [Signal("battery_low", data={"percent": current.battery_percent})]

    def _detect_late_night(self, current: Snapshot) -> list[Signal]:
        if current.hour not in LATE_NIGHT_HOURS:
            return []
        if self._late_night_day == current.day:
            return []
        self._late_night_day = current.day
        return [Signal("late_night", data={"hour": current.hour})]
