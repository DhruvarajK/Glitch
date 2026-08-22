"""End-to-end brain tests against a fake OpenAI client.

These exercise the real threading and signal path: the request runs on the AI
thread and results are delivered back through Qt.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer

from core.ai.brain import AIBrain
from core.ai.conversation import ConversationManager
from core.ai.prompts import PromptContext
from core.persistence.config import ConfigManager


@pytest.fixture(scope="module")
def qt_app():
    app = QCoreApplication.instance() or QCoreApplication([])
    yield app


@pytest.fixture()
def config(tmp_path):
    config = ConfigManager(tmp_path / "config.json")
    config.set("ai_model", "fake-model")
    return config


def _chunk(content: str | None, usage=None):
    delta = SimpleNamespace(content=content)
    choices = [SimpleNamespace(delta=delta)] if content is not None else []
    return SimpleNamespace(choices=choices, usage=usage)


class FakeStream:
    def __init__(self, pieces, usage):
        self._pieces = pieces
        self._usage = usage

    def __aiter__(self):
        async def generator():
            for piece in self._pieces:
                yield _chunk(piece)
            yield _chunk(None, usage=self._usage)

        return generator()


class FakeClient:
    """Replays a scripted response, or raises to simulate a failure."""

    def __init__(self, pieces=None, error: Exception | None = None):
        self.pieces = pieces or []
        self.error = error
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return FakeStream(self.pieces, SimpleNamespace(prompt_tokens=11, completion_tokens=7))


def _split(payload: dict, size: int = 7) -> list[str]:
    raw = json.dumps(payload)
    return [raw[i : i + size] for i in range(0, len(raw), size)]


def run_request(qt_app, brain, message="hello", timeout_ms=5000) -> dict:
    """Drive the Qt loop until the request settles; collect what was emitted."""
    seen: dict = {"tokens": [], "response": None, "failure": None}
    loop = QEventLoop()

    brain.token_received.connect(lambda _id, text: seen["tokens"].append(text))
    brain.response_received.connect(
        lambda _id, response: (seen.update(response=response), loop.quit())
    )
    brain.request_failed.connect(
        lambda _id, kind, text: (seen.update(failure=(kind, text)), loop.quit())
    )
    QTimer.singleShot(timeout_ms, loop.quit)

    brain.ask(message, PromptContext())
    loop.exec()
    return seen


@pytest.fixture()
def brain(config, monkeypatch):
    conversation = ConversationManager(config, database=None)
    brain = AIBrain(config, conversation, database=None)
    monkeypatch.setattr(
        "core.ai.brain.get_api_key", lambda: "sk-test", raising=True
    )
    yield brain
    brain.shutdown()


def test_streamed_response_is_parsed_and_emitted(qt_app, brain):
    payload = {
        "message": "Hey, nice to see you.",
        "emotion": "happy",
        "intensity": 0.8,
        "action": "talk",
    }
    brain._get_client = lambda: FakeClient(_split(payload))

    seen = run_request(qt_app, brain)

    assert seen["failure"] is None
    assert seen["response"].message == payload["message"]
    assert seen["response"].emotion == "happy"
    # The bubble must fill in progressively, not arrive all at once.
    assert len(seen["tokens"]) > 1
    assert seen["tokens"][-1] == payload["message"]
    assert seen["tokens"] == sorted(seen["tokens"], key=len)


def test_conversation_records_both_turns(qt_app, brain):
    payload = {"message": "Sure.", "emotion": "neutral", "intensity": 0.4, "action": "talk"}
    brain._get_client = lambda: FakeClient(_split(payload))

    run_request(qt_app, brain, message="can you hear me")

    context = brain.conversation.context()
    assert context[-2] == {"role": "user", "content": "can you hear me"}
    assert context[-1] == {"role": "assistant", "content": "Sure."}


def test_malformed_json_is_salvaged_into_a_reply(qt_app, brain):
    brain._get_client = lambda: FakeClient(['{"message":"half a thou'])

    seen = run_request(qt_app, brain)

    assert seen["failure"] is None
    assert seen["response"].message == "half a thou"


def test_network_failure_reaches_the_ui(qt_app, brain):
    brain._get_client = lambda: FakeClient(error=ConnectionError("getaddrinfo failed"))

    seen = run_request(qt_app, brain)

    assert seen["response"] is None
    assert seen["failure"][0] == "network"
    assert seen["failure"][1]


def test_missing_api_key_fails_immediately(qt_app, brain, monkeypatch):
    monkeypatch.setattr("core.ai.brain.get_api_key", lambda: None)

    seen = run_request(qt_app, brain)

    assert seen["failure"][0] == "auth"


def test_a_rejected_temperature_is_retried_without_it(qt_app, brain):
    payload = {"message": "Fine.", "emotion": "neutral", "intensity": 0.5, "action": "talk"}
    client = FakeClient(_split(payload))
    calls: list[dict] = []

    async def create(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise RuntimeError("Unsupported value: 'temperature' is not supported")
        return FakeStream(_split(payload), None)

    client.chat.completions.create = create
    brain._get_client = lambda: client

    seen = run_request(qt_app, brain)

    assert seen["response"].message == "Fine."
    assert "temperature" in calls[0]
    assert "temperature" not in calls[1]


def test_request_uses_the_structured_schema(qt_app, brain):
    payload = {"message": "Ok.", "emotion": "neutral", "intensity": 0.5, "action": "talk"}
    client = FakeClient(_split(payload))
    brain._get_client = lambda: client

    run_request(qt_app, brain)

    kwargs = client.calls[0]
    assert kwargs["stream"] is True
    assert kwargs["response_format"]["type"] == "json_schema"
    assert kwargs["messages"][0]["role"] == "system"


def test_ai_disabled_never_starts_a_request(qt_app, brain, config):
    config.set("ai_enabled", False)
    assert brain.ask("hello", PromptContext()) is None
