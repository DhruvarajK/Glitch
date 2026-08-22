import asyncio
import json

import pytest

from core.ai.models import AIResponse
from core.ai.brain import classify_error, extract_partial_message
from core.ai.prompts import PromptContext, build_system_prompt


# ------------------------------------------------------- partial JSON parsing
def test_partial_message_before_the_key_arrives():
    assert extract_partial_message('{"emo') == ""


def test_partial_message_mid_string():
    assert extract_partial_message('{"message":"Hello wo') == "Hello wo"


def test_partial_message_is_complete_once_closed():
    raw = '{"message":"Hi there","emotion":"happy"}'
    assert extract_partial_message(raw) == "Hi there"


def test_partial_message_decodes_escapes():
    assert extract_partial_message(r'{"message":"line\none \"quoted\""') == (
        'line\none "quoted"'
    )


def test_partial_message_ignores_a_half_received_escape():
    # A lone trailing backslash is an escape whose second half has not arrived.
    assert extract_partial_message('{"message":"done\\') == "done"


def test_partial_message_decodes_a_complete_backslash_escape():
    assert extract_partial_message(r'{"message":"a\\b') == "a\\b"


def test_partial_message_decodes_unicode_escapes():
    assert extract_partial_message(r'{"message":"café') == "café"


def test_partial_message_waits_for_a_half_received_unicode_escape():
    assert extract_partial_message(r'{"message":"caf\u00') == "caf"


# -------------------------------------------------------- response validation
def test_valid_response_round_trips():
    response = AIResponse.model_validate_json(
        json.dumps(
            {
                "message": "  Hey!  ",
                "emotion": "amused",
                "intensity": 0.7,
                "action": "talk",
            }
        )
    )
    assert response.message == "Hey!"
    assert response.animation() == "amused"


def test_action_wins_over_emotion_when_more_specific():
    response = AIResponse(message="hi", emotion="happy", action="laugh")
    assert response.animation() == "laughing"


def test_unknown_emotion_is_rejected():
    with pytest.raises(Exception):
        AIResponse(message="hi", emotion="smitten")


def test_empty_message_is_rejected():
    with pytest.raises(Exception):
        AIResponse(message="   ")


def test_intensity_is_bounded():
    with pytest.raises(Exception):
        AIResponse(message="hi", intensity=5.0)


def test_emotion_deltas_scale_with_intensity():
    strong = AIResponse(message="hi", emotion="excited", intensity=1.0).emotion_deltas()
    weak = AIResponse(message="hi", emotion="excited", intensity=0.2).emotion_deltas()
    assert strong["happiness"] > weak["happiness"]


def test_fallback_produces_a_usable_response():
    response = AIResponse.fallback("something broke")
    assert response.message == "something broke"
    assert response.action == "talk"


# ----------------------------------------------------------- error handling
@pytest.mark.parametrize(
    "exc, expected",
    [
        (asyncio.TimeoutError(), "timeout"),
        (RuntimeError("Error code: 429 rate limit reached"), "rate_limit"),
        (RuntimeError("Incorrect API key provided"), "auth"),
        (ConnectionError("getaddrinfo failed"), "network"),
        (json.JSONDecodeError("bad", "doc", 0), "invalid"),
        (RuntimeError("something else entirely"), "unknown"),
    ],
)
def test_errors_are_classified(exc, expected):
    assert classify_error(exc) == expected


# ------------------------------------------------------------------ prompts
def test_system_prompt_includes_personality_and_state():
    prompt = build_system_prompt("sarcastic", PromptContext(state="walking", mood="curious"))
    assert "deadpan" in prompt
    assert "walking" in prompt
    assert "curious" in prompt


def test_system_prompt_includes_memories():
    context = PromptContext(memories=["User prefers concise answers"])
    assert "User prefers concise answers" in build_system_prompt("default", context)


def test_unknown_personality_falls_back_to_default():
    assert "Glitch" in build_system_prompt("does-not-exist", PromptContext())
