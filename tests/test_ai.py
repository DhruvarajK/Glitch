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


def test_every_offered_emotion_and_action_maps_to_a_real_clip():
    """The model can only pick what the sprite sheets can actually show."""
    import json

    from core.ai.models import (
        ACTION_ANIMATION,
        ACTIONS,
        EMOTION_ANIMATION,
        EMOTION_EFFECTS,
        EMOTIONS,
        RESPONSE_JSON_SCHEMA,
    )
    from core.utils.constants import ANIMATION_MANIFEST

    clips = set(json.loads(ANIMATION_MANIFEST.read_text(encoding="utf-8"))["animations"])
    for emotion in EMOTIONS:
        assert emotion in EMOTION_ANIMATION, emotion
        assert emotion in EMOTION_EFFECTS, emotion
        assert EMOTION_ANIMATION[emotion] in clips, emotion
    for action in ACTIONS:
        assert action in ACTION_ANIMATION, action
        assert ACTION_ANIMATION[action] in clips, action

    # The schema handed to the model must offer exactly the same choices.
    properties = RESPONSE_JSON_SCHEMA["schema"]["properties"]
    assert properties["emotion"]["enum"] == list(EMOTIONS)
    assert properties["action"]["enum"] == list(ACTIONS)


def test_the_widened_emotions_are_accepted():
    for emotion, clip in (
        ("smug", "smug"),
        ("affectionate", "love"),
        ("mischievous", "mischievous"),
        ("amazed", "mindblown"),
        ("upset", "crying"),
    ):
        response = AIResponse(message="hi", emotion=emotion, action="talk")
        assert response.animation() == clip


def test_glitch_is_told_it_can_sense_the_app_but_not_the_content():
    """The old contract denied every sense, so it answered "I cannot see"."""
    prompt = build_system_prompt("default", PromptContext(focus="coding"))
    assert "see nothing about their screen" not in prompt
    assert "which kind of app is in front" in prompt
    assert "What you cannot sense is content" in prompt


def test_the_prompt_says_what_the_user_is_in_front_of():
    prompt = build_system_prompt("default", PromptContext(focus="coding"))
    assert "Right now the user is coding" in prompt


def test_unprompted_situation_reaches_the_prompt():
    prompt = build_system_prompt(
        "default", PromptContext(situation="the user just opened a code editor")
    )
    assert "spoke first" in prompt.lower() or "Nobody asked" in prompt
    assert "just opened a code editor" in prompt


# ------------------------------------------------- the full feeling vocabulary
def test_every_emotion_and_action_has_a_cue():
    """A new emotion is useless to the model until it is described."""
    from core.ai.models import ACTION_CUES, ACTIONS, EMOTION_CUES, EMOTIONS

    for emotion in EMOTIONS:
        assert EMOTION_CUES.get(emotion), emotion
    for action in ACTIONS:
        assert ACTION_CUES.get(action), action
    assert set(EMOTION_CUES) == set(EMOTIONS)
    assert set(ACTION_CUES) == set(ACTIONS)


def test_the_prompt_teaches_every_emotion_it_offers():
    from core.ai.models import ACTION_CUES, ACTIONS, EMOTION_CUES, EMOTIONS

    prompt = build_system_prompt("default", PromptContext())
    for emotion in EMOTIONS:
        assert emotion in prompt, emotion
        assert EMOTION_CUES[emotion] in prompt, emotion
    for action in ACTIONS:
        assert ACTION_CUES[action] in prompt, action


def test_the_prompt_says_to_pick_the_feeling_before_the_line():
    prompt = build_system_prompt("default", PromptContext())
    assert "before you write the line" in prompt


def test_emotion_is_generated_before_the_message():
    """Order is load-bearing: the pet reacts while the line is still coming."""
    from core.ai.models import RESPONSE_JSON_SCHEMA

    schema = RESPONSE_JSON_SCHEMA["schema"]
    assert schema["required"] == ["emotion", "intensity", "action", "message"]
    assert list(schema["properties"]) == ["emotion", "intensity", "action", "message"]


def test_animation_for_matches_the_response_it_came_from():
    from core.ai.models import animation_for

    for emotion, action in (("happy", "talk"), ("sad", "laugh"), ("bored", "think")):
        response = AIResponse(message="hi", emotion=emotion, action=action)
        assert animation_for(emotion, action) == response.animation()


# ------------------------------------------------------------ prompt caching
def test_only_the_tail_of_the_prompt_moves_between_requests():
    """The fixed half must stay byte-identical or no prefix cache can hit."""
    from core.ai.emotion import EmotionState
    from core.ai.prompts import static_prefix

    quiet = build_system_prompt("default", PromptContext())
    busy = build_system_prompt(
        "default",
        PromptContext(
            state="walking",
            mood="annoyed",
            emotion=EmotionState(annoyance=0.9, happiness=0.1),
            focus="coding",
            memories=["User prefers concise answers"],
        ),
    )
    prefix = static_prefix("default")
    assert quiet.startswith(prefix)
    assert busy.startswith(prefix)
    # The fixed half is the bulk of it, which is the point.
    assert len(prefix) > 0.5 * len(quiet)


def test_only_the_traits_that_have_moved_are_sent():
    from core.ai.emotion import EmotionState
    from core.ai.prompts import _felt_traits

    assert "nothing pulling strongly" in _felt_traits(EmotionState())
    felt = _felt_traits(EmotionState(annoyance=0.85, happiness=0.15))
    assert "very annoyance" in felt
    assert "low happiness" in felt
    assert "curiosity" not in felt


# ------------------------------------------------ reacting mid-stream
def test_early_fields_are_unavailable_until_the_message_key_arrives():
    from core.ai.brain import extract_early_fields

    assert extract_early_fields('{"emotion":"smug","intensity":0.8') is None
    assert extract_early_fields("") is None


def test_early_fields_are_readable_once_the_message_key_arrives():
    from core.ai.brain import extract_early_fields

    early = extract_early_fields(
        '{"emotion":"smug","intensity":0.8,"action":"laugh","message":"ha'
    )
    assert early == {"emotion": "smug", "intensity": 0.8, "action": "laugh"}


def test_early_fields_survive_a_whole_response():
    from core.ai.brain import extract_early_fields

    raw = json.dumps(
        {"emotion": "curious", "intensity": 0.4, "action": "think", "message": "hm?"}
    )
    assert extract_early_fields(raw)["emotion"] == "curious"


def test_early_fields_give_up_quietly_on_nonsense():
    from core.ai.brain import extract_early_fields

    assert extract_early_fields('{"emotion":,"message"') is None
