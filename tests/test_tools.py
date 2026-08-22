"""Actions Glitch performs locally, and the cost ceilings around the brain.

The point of this layer is that none of it makes a request, so the tests care
as much about what is *not* called as about what is.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta

import pytest

from core.persistence.config import ConfigManager
from core.persistence.database import Database
from core.tools import intents
from core.tools.activity import ActivityTracker, humanise
from core.tools.launcher import DEFAULT_WHITELIST, AppLauncher
from core.tools.reminders import MAX_MINUTES, ReminderService, describe_delay
from core.tools.runner import ToolRunner


@pytest.fixture()
def config(tmp_path):
    return ConfigManager(tmp_path / "config.json")


@pytest.fixture()
def database(tmp_path):
    db = Database(tmp_path / "glitch.db")
    yield db
    db.close()


@pytest.fixture()
def runner(qt_gui_app, config, database):
    quieted: list[float] = []
    tools = ToolRunner(
        ReminderService(database),
        AppLauncher(config),
        ActivityTracker(database),
        on_quiet=quieted.append,
        rng=random.Random(0),
    )
    tools.quieted = quieted  # type: ignore[attr-defined]
    return tools


# ------------------------------------------------------------------ parsing
@pytest.mark.parametrize(
    "message, minutes, text",
    [
        ("remind me in 20 minutes to stretch", 20.0, "stretch"),
        ("remind me to check the oven in 5 min", 5.0, "check the oven"),
        ("hey can you remind me to stand up in half an hour", 30.0, "stand up"),
        ("remind me to rest in an hour and a half", 90.0, "rest"),
        ("remind me in quarter of an hour to look up", 15.0, "look up"),
        ("remind me in 2 hours to eat", 120.0, "eat"),
    ],
)
def test_reminder_phrasings(message, minutes, text):
    call = intents.parse(message)
    assert call is not None and call.name == "remind"
    assert call.minutes == pytest.approx(minutes)
    assert call.text == text


def test_a_reminder_with_no_time_asks_for_one():
    call = intents.parse("remind me to call mom")
    assert call is not None and call.name == "remind_needs_time"
    assert call.text == "call mom"


@pytest.mark.parametrize(
    "message, name",
    [
        ("open spotify", "open_app"),
        ("please start notepad", "open_app"),
        ("be quiet for an hour", "quiet"),
        ("shut up", "quiet"),
        ("you can talk again", "unquiet"),
        ("what am i doing", "stats"),
        ("how long have i been coding today", "stats"),
    ],
)
def test_instruction_phrasings(message, name):
    call = intents.parse(message)
    assert call is not None and call.name == name


@pytest.mark.parametrize(
    "message",
    [
        "hello how are you",
        "what do you think about python",
        "remember that i like dark mode",  # memory handles this one
        "open the settings",               # about Glitch, not an app
        "",
    ],
)
def test_conversation_is_left_to_the_brain(message):
    assert intents.parse(message) is None


def test_quiet_defaults_to_an_hour_when_no_time_is_given():
    assert intents.parse("shut up").minutes == 60.0
    assert intents.parse("be quiet for 10 minutes").minutes == 10.0


# ---------------------------------------------------------------- reminders
def test_a_reminder_is_stored_and_comes_due(qt_gui_app, database):
    service = ReminderService(database)
    reminder = service.add("stretch", minutes=10)
    assert reminder is not None
    assert [r.text for r in service.pending()] == ["stretch"]

    # Nothing is due yet.
    assert service.check(datetime.now()) == []
    # ...but it is, ten minutes from now.
    due = service.check(datetime.now() + timedelta(minutes=11))
    assert [r.text for r in due] == ["stretch"]
    # Delivered once only.
    assert service.check(datetime.now() + timedelta(minutes=12)) == []
    assert service.pending() == []


def test_a_reminder_missed_while_shut_is_delivered_on_return(qt_gui_app, database):
    delivered = []
    service = ReminderService(database, on_due=delivered.append)
    database.add_reminder("water the plants", datetime.now() - timedelta(hours=2))

    service.check()
    assert [r.text for r in delivered] == ["water the plants"]


def test_reminder_length_is_capped(qt_gui_app, database):
    service = ReminderService(database)
    reminder = service.add("x" * 500, minutes=MAX_MINUTES * 10)
    assert reminder is not None
    assert len(reminder.text) <= 200
    assert reminder.due_at <= datetime.now() + timedelta(minutes=MAX_MINUTES + 1)


def test_reminders_degrade_without_a_database(qt_gui_app):
    service = ReminderService(None)
    assert service.add("anything", 5) is None
    assert service.pending() == []


def test_delay_reads_naturally():
    assert describe_delay(20) == "20 minutes"
    assert describe_delay(60) == "1 hour"
    assert describe_delay(150) == "2 hours 30 minutes"


# ----------------------------------------------------------------- launcher
def test_only_whitelisted_apps_launch(config):
    launcher = AppLauncher(config)
    assert launcher.resolve("notepad") == DEFAULT_WHITELIST["notepad"]
    assert launcher.resolve("photoshop") is None


def test_the_user_can_approve_more_apps(config):
    config.set("app_whitelist", {"spotify": "spotify.exe"})
    launcher = AppLauncher(config)
    assert launcher.resolve("Spotify") == "spotify.exe"
    assert launcher.resolve("the spotify") == "spotify.exe"


def test_aliases_are_understood(config):
    config.set("app_whitelist", {"code": "code.exe"})
    launcher = AppLauncher(config)
    assert launcher.resolve("vs code") == "code.exe"
    assert launcher.resolve("visual studio code") == "code.exe"


def test_an_unapproved_app_is_refused_without_running_anything(config):
    result = AppLauncher(config).launch("rm -rf /")
    assert not result.ok
    assert "not allowed" in result.message


def test_a_command_string_is_never_shelled_out(config, monkeypatch):
    """The whitelist value must reach Popen as a vector, never as a shell line."""
    config.set("app_whitelist", {"thing": "thing.exe"})
    seen = {}

    def fake_popen(args, **kwargs):
        seen["args"] = args
        seen["shell"] = kwargs.get("shell")
        return object()

    monkeypatch.setattr("core.tools.launcher.shutil.which", lambda command: command)
    monkeypatch.setattr("core.tools.launcher.subprocess.Popen", fake_popen)

    assert AppLauncher(config).launch("thing").ok
    assert seen["args"] == ["thing.exe"]
    assert seen["shell"] is False


# ----------------------------------------------------------------- activity
def test_activity_accumulates_per_category(database):
    tracker = ActivityTracker(database)
    tracker.observe("coding", 0.0)
    tracker.observe("coding", 60.0)
    tracker.observe("browser", 90.0)
    tracker.flush()

    today = tracker.today()
    assert today["coding"] == pytest.approx(90.0)


def test_a_sleeping_machine_is_not_counted_as_work(database):
    tracker = ActivityTracker(database)
    tracker.observe("coding", 0.0)
    tracker.observe("coding", 10_000.0)  # the lid was shut
    tracker.flush()
    assert tracker.today().get("coding", 0.0) == 0.0


def test_activity_summary_reads_as_a_sentence(database):
    tracker = ActivityTracker(database)
    database.add_activity(datetime.now().date().isoformat(), "coding", 7200)
    assert "2 hours coding" in tracker.summary()


def test_humanise_durations():
    assert humanise(30) == "under a minute"
    assert humanise(60) == "1 minute"
    assert humanise(3600) == "1 hour"
    assert humanise(5400) == "1h 30m"


# ------------------------------------------------------------------- runner
def test_running_a_reminder_confirms_it(runner):
    result = runner.run(intents.parse("remind me in 20 minutes to stretch"))
    assert result is not None
    assert "20 minutes" in result.message and "stretch" in result.message
    assert [r.text for r in runner.reminders.pending()] == ["stretch"]


def test_running_quiet_reports_the_duration(runner):
    result = runner.run(intents.parse("be quiet for 30 minutes"))
    assert result is not None
    assert "30 minutes" in result.message
    assert runner.quieted == [30.0]


def test_unquiet_clears_it(runner):
    runner.run(intents.parse("you can talk again"))
    assert runner.quieted == [0.0]


def test_an_unknown_tool_is_not_handled(runner):
    assert runner.run(intents.ToolCall("nonsense")) is None


def test_a_failing_tool_does_not_escape(runner, monkeypatch):
    monkeypatch.setattr(
        runner.reminders, "add", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("nope"))
    )
    result = runner.run(intents.parse("remind me in 5 minutes to test"))
    assert result is not None and result.animation == "confused"


# ------------------------------------------------------------------- budget
def _brain(config, database):
    from core.ai.brain import AIBrain
    from core.ai.conversation import ConversationManager

    return AIBrain(config, ConversationManager(config, database), database)


def test_budget_starts_clear(qt_gui_app, config, database):
    brain = _brain(config, database)
    try:
        assert not brain.over_budget()
        assert brain.budget_state()["requests"] == 0
    finally:
        brain.shutdown()


def test_the_token_ceiling_stops_further_requests(qt_gui_app, config, database):
    config.set("daily_token_limit", 1000)
    brain = _brain(config, database)
    try:
        database.record_usage(
            model="m", input_tokens=900, output_tokens=200, duration_ms=1, success=True
        )
        assert brain.over_budget()
    finally:
        brain.shutdown()


def test_the_request_ceiling_stops_further_requests(qt_gui_app, config, database):
    config.set("daily_request_limit", 2)
    config.set("daily_token_limit", 0)
    brain = _brain(config, database)
    try:
        for _ in range(2):
            database.record_usage(
                model="m", input_tokens=1, output_tokens=1, duration_ms=1, success=True
            )
        assert brain.over_budget()
    finally:
        brain.shutdown()


def test_zero_means_no_limit(qt_gui_app, config, database):
    config.set("daily_request_limit", 0)
    config.set("daily_token_limit", 0)
    brain = _brain(config, database)
    try:
        for _ in range(50):
            database.record_usage(
                model="m", input_tokens=10_000, output_tokens=10_000,
                duration_ms=1, success=True,
            )
        assert not brain.over_budget()
    finally:
        brain.shutdown()


def test_an_over_budget_request_fails_without_calling_out(qt_gui_app, config, database):
    from core.ai.prompts import PromptContext

    config.set("daily_request_limit", 1)
    brain = _brain(config, database)
    failures = []
    brain.request_failed.connect(lambda rid, kind, message: failures.append(kind))
    try:
        database.record_usage(
            model="m", input_tokens=1, output_tokens=1, duration_ms=1, success=True
        )
        brain.ask("hello", PromptContext())
        assert failures == ["budget"]
        assert not brain.busy  # nothing was ever dispatched
    finally:
        brain.shutdown()
