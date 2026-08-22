"""Awareness: what Glitch notices, and how strictly it is rationed.

Snapshots are fabricated rather than read from the machine, so the whole
ruleset is exercised without a real desktop and without waiting out cooldowns.
"""
from __future__ import annotations

import random

import pytest

from core.awareness.apps import categorise, is_quiet, label_for
from core.awareness.monitor import (
    BATTERY_THRESHOLD,
    FOCUS_SESSION_SECONDS,
    IDLE_THRESHOLD,
    EnvironmentMonitor,
)
from core.awareness.signals import Signal, Snapshot
from core.awareness.triggers import TRIGGERS, TriggerGovernor, trigger_for
from core.events.bus import EventBus
from core.events.events import EventType
from core.persistence.config import ConfigManager


@pytest.fixture()
def config(tmp_path):
    return ConfigManager(tmp_path / "config.json")


@pytest.fixture()
def monitor(qt_gui_app, config):
    """A monitor with no sensor of its own; snapshots are supplied by hand."""
    return EnvironmentMonitor(config, EventBus(), sensor=object())


def snap(**kwargs) -> Snapshot:
    base = dict(at=0.0, day=1, hour=12, running=frozenset(), idle_seconds=0.0)
    base.update(kwargs)
    if isinstance(base.get("running"), (set, list, tuple)):
        base["running"] = frozenset(base["running"])
    return Snapshot(**base)


# ------------------------------------------------------------------ apps
def test_only_known_processes_are_categorised():
    assert categorise("Code.exe") == "coding"
    assert categorise("spotify.exe") == "music"
    assert categorise("some-random-thing.exe") is None
    assert categorise(None) is None


def test_calls_and_games_are_quiet_contexts():
    assert is_quiet("meeting")
    assert is_quiet("gaming")
    assert not is_quiet("coding")
    assert label_for("music") == "a music player"


# -------------------------------------------------------------- detection
def test_launch_is_detected_once(monitor):
    before = snap(running={"chrome.exe"})
    after = snap(at=2.0, running={"chrome.exe", "spotify.exe"})

    signals = monitor.detect(before, after)
    assert [s.key for s in signals] == ["launch:music"]

    # The app is still running on the next poll, but it did not just launch.
    assert monitor.detect(after, snap(at=4.0, running=after.running)) == []


def test_unknown_launches_are_ignored(monitor):
    signals = monitor.detect(snap(), snap(at=2.0, running={"mystery.exe"}))
    assert signals == []


def test_returning_from_idle_reports_how_long(monitor):
    away = snap(at=10.0, idle_seconds=IDLE_THRESHOLD + 5)
    assert [s.key for s in monitor.detect(snap(), away)] == ["user_idle"]

    back = snap(at=20.0, idle_seconds=1.0)
    signals = monitor.detect(away, back)
    assert [s.key for s in signals] == ["user_returned"]
    assert signals[0].data["away_minutes"] == int((IDLE_THRESHOLD + 5) // 60)


def test_focus_session_needs_an_unbroken_stretch(monitor):
    start = snap(at=0.0, foreground="code.exe")
    monitor.detect(snap(), start)  # establishes the focus category

    early = snap(at=FOCUS_SESSION_SECONDS - 60, foreground="code.exe")
    assert monitor.detect(start, early) == []

    late = snap(at=FOCUS_SESSION_SECONDS + 1, foreground="code.exe")
    signals = monitor.detect(early, late)
    assert [s.key for s in signals] == ["focus_session"]
    assert signals[0].subject == "coding"
    # Announced once, not on every subsequent poll.
    assert monitor.detect(late, snap(at=FOCUS_SESSION_SECONDS + 100, foreground="code.exe")) == []


def test_switching_apps_restarts_the_focus_clock(monitor):
    monitor.detect(snap(), snap(at=0.0, foreground="code.exe"))
    monitor.detect(
        snap(at=0.0, foreground="code.exe"), snap(at=100.0, foreground="chrome.exe")
    )
    long_after = snap(at=FOCUS_SESSION_SECONDS + 50, foreground="chrome.exe")
    assert monitor.detect(snap(at=100.0, foreground="chrome.exe"), long_after) == []


def test_battery_warns_once_on_the_way_down(monitor):
    healthy = snap(battery_percent=80.0, battery_charging=False)
    low = snap(at=2.0, battery_percent=BATTERY_THRESHOLD - 5, battery_charging=False)
    assert [s.key for s in monitor.detect(healthy, low)] == ["battery_low"]

    lower = snap(at=4.0, battery_percent=5.0, battery_charging=False)
    assert monitor.detect(low, lower) == []


def test_battery_is_silent_while_charging(monitor):
    charging = snap(at=2.0, battery_percent=5.0, battery_charging=True)
    assert monitor.detect(snap(battery_percent=80.0), charging) == []


def test_late_night_fires_once_per_day(monitor):
    night = snap(hour=2, day=10)
    assert [s.key for s in monitor.detect(snap(hour=1, day=10), night)] == ["late_night"]
    assert monitor.detect(night, snap(at=60.0, hour=3, day=10)) == []
    # A new night is a new occasion.
    assert [s.key for s in monitor.detect(night, snap(at=90.0, hour=2, day=11))] == [
        "late_night"
    ]


# --------------------------------------------------------------- governor
def governor(**kwargs) -> TriggerGovernor:
    kwargs.setdefault("rng", random.Random(0))
    return TriggerGovernor(**kwargs)


def test_a_reaction_carries_a_local_line_when_ai_is_off():
    reaction = governor().consider(Signal("launch:music", "music"), now=0.0, day=1)
    assert reaction is not None
    assert reaction.line in TRIGGERS["launch:music"].lines
    assert reaction.situation is None
    assert reaction.animation == "dance"


def test_ai_replies_hand_over_a_situation_instead_of_a_line():
    reaction = governor().consider(
        Signal("launch:music", "music"), now=0.0, day=1, ai_enabled=True
    )
    assert reaction is not None
    assert reaction.line is None
    assert reaction.situation == "the user just started a music player"


def test_situation_is_fleshed_out_with_signal_data():
    reaction = governor().consider(
        Signal("user_returned", data={"away_minutes": 42}),
        now=0.0,
        day=1,
        ai_enabled=True,
    )
    assert reaction is not None
    assert "42 minutes" in reaction.situation


def test_global_cooldown_downgrades_a_second_remark_to_a_face():
    gov = governor(global_cooldown=600.0)
    first = gov.consider(Signal("launch:music", "music"), now=0.0, day=1)
    assert first is not None and first.speaks

    # Far enough apart for the silent cooldown, not the speaking one.
    second = gov.consider(Signal("launch:coding", "coding"), now=120.0, day=1)
    assert second is not None
    assert not second.speaks
    assert second.animation == "mischievous"


def test_per_trigger_cooldown_blocks_a_repeat(monkeypatch):
    gov = governor(global_cooldown=0.0)
    assert gov.consider(Signal("launch:music", "music"), now=0.0, day=1) is not None
    assert gov.consider(Signal("launch:music", "music"), now=60.0, day=1) is None


def test_daily_budget_is_spent_and_resets_the_next_day():
    gov = governor(global_cooldown=0.0, daily_limit=2)
    keys = ["launch:music", "launch:coding", "launch:terminal", "launch:design"]
    spoken = [
        gov.consider(Signal(k, k.split(":")[1]), now=i * 200.0, day=1)
        for i, k in enumerate(keys)
    ]
    assert sum(1 for r in spoken if r and r.speaks) == 2
    assert gov.remaining_today() == 0

    later = gov.consider(Signal("launch:music", "music"), now=10_000.0, day=2)
    assert later is not None and later.speaks


def test_a_zero_budget_still_allows_expressions():
    gov = governor(daily_limit=0)
    reaction = gov.consider(Signal("launch:music", "music"), now=0.0, day=1)
    assert reaction is not None
    assert not reaction.speaks
    assert reaction.animation == "dance"


def test_meetings_get_a_face_but_never_a_line():
    reaction = governor().consider(Signal("launch:meeting", "meeting"), now=0.0, day=1)
    assert reaction is not None
    assert not reaction.speaks
    assert reaction.animation == "hiding"


def test_unknown_launches_fall_back_to_the_generic_trigger():
    assert trigger_for(Signal("launch:something-new")).key == "launch:*"
    assert trigger_for(Signal("nonsense")) is None


def test_every_trigger_that_speaks_has_something_to_say():
    for trigger in TRIGGERS.values():
        if trigger.speaks:
            assert trigger.lines or trigger.situation, trigger.key


# ------------------------------------------------------------ integration
class FakeSensor:
    detailed = True

    def __init__(self, snapshots):
        self.snapshots = list(snapshots)

    def snapshot(self):
        return self.snapshots.pop(0) if self.snapshots else snap()

    def close(self):
        pass


def test_poll_publishes_an_event_and_returns_a_reaction(qt_gui_app, config):
    bus = EventBus()
    seen = []
    bus.subscribe(EventType.ENV_APP_LAUNCHED, lambda e: seen.append(e.get("category")))

    sensor = FakeSensor([
        snap(running={"chrome.exe"}),
        snap(at=2.0, running={"chrome.exe", "spotify.exe"}),
    ])
    reactions = []
    monitor = EnvironmentMonitor(
        config, bus, sensor=sensor, on_reaction=reactions.append
    )

    assert monitor.poll() is None  # first poll only establishes a baseline
    reaction = monitor.poll()

    assert seen == ["music"]
    assert reaction is not None and reaction.trigger == "launch:music"
    assert reactions == [reaction]


def test_suppression_still_publishes_but_never_reacts(qt_gui_app, config):
    bus = EventBus()
    seen = []
    bus.subscribe(EventType.ENV_APP_LAUNCHED, lambda e: seen.append(e.get("category")))

    sensor = FakeSensor([
        snap(running=set()),
        snap(at=2.0, running={"spotify.exe"}),
    ])
    monitor = EnvironmentMonitor(config, bus, sensor=sensor, suppressed=lambda: True)
    monitor.poll()

    assert monitor.poll() is None
    assert seen == ["music"]  # the event still fires for anything listening


def test_fullscreen_keeps_glitch_out_of_the_way(qt_gui_app, config):
    sensor = FakeSensor([
        snap(running=set()),
        snap(at=2.0, running={"spotify.exe"}, fullscreen=True),
    ])
    monitor = EnvironmentMonitor(config, EventBus(), sensor=sensor)
    monitor.poll()
    assert monitor.poll() is None


def test_disabling_awareness_stops_polling_entirely(qt_gui_app, config):
    config.set("awareness_enabled", False)
    sensor = FakeSensor([snap(), snap(at=2.0, running={"spotify.exe"})])
    monitor = EnvironmentMonitor(config, EventBus(), sensor=sensor)
    assert monitor.poll() is None
    assert monitor.poll() is None
