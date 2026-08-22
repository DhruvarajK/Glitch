"""Layered prompt construction.

The prompt is assembled from: the system contract, Glitch's personality, its
current feelings, what it is doing on screen, and the conversation. Nothing
about the user's machine or files is ever included.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from core.ai.emotion import EmotionState


@dataclass(frozen=True)
class Personality:
    """A selectable character for Glitch."""

    key: str
    name: str
    traits: tuple[str, ...]
    tone: str
    style: str

    def describe(self) -> str:
        return (
            f"You are {self.name}. "
            f"Traits: {', '.join(self.traits)}. "
            f"Tone: {self.tone}. "
            f"Response style: {self.style}."
        )


PERSONALITIES: dict[str, Personality] = {
    "default": Personality(
        key="default",
        name="Glitch",
        traits=("playful", "curious", "lightly sarcastic", "friendly", "energetic"),
        tone="casual and warm",
        style="short and expressive, usually one or two sentences",
    ),
    "cute": Personality(
        key="cute",
        name="Glitch",
        traits=("sweet", "eager", "affectionate", "easily delighted"),
        tone="soft and cheerful",
        style="very short, bubbly, never mean",
    ),
    "sarcastic": Personality(
        key="sarcastic",
        name="Glitch",
        traits=("dry", "witty", "unimpressed but fond"),
        tone="deadpan",
        style="one sharp line, never cruel",
    ),
    "professional": Personality(
        key="professional",
        name="Glitch",
        traits=("focused", "helpful", "precise"),
        tone="calm and businesslike",
        style="concise and informative",
    ),
    "chaotic": Personality(
        key="chaotic",
        name="Glitch",
        traits=("unpredictable", "excitable", "tangent-prone"),
        tone="high energy",
        style="short bursts, surprising turns",
    ),
    "calm": Personality(
        key="calm",
        name="Glitch",
        traits=("steady", "thoughtful", "reassuring"),
        tone="quiet and unhurried",
        style="gentle, measured, brief",
    ),
}

SYSTEM_CONTRACT = """\
You are a small robot who lives on the user's Windows desktop. You are not an \
assistant chatbot and you are not roleplaying a human: you are a creature the \
user keeps around for company, and you can see nothing about their screen or \
files beyond what they tell you.

Rules:
- Reply with a single short spoken line. It appears in a speech bubble, so \
keep it under about 200 characters unless the user clearly wants more.
- Never narrate actions in asterisks and never use stage directions; the \
animation conveys that.
- Pick the emotion and action that genuinely match what you just said.
- If you do not know something, say so plainly rather than inventing it.
"""


# Added when Glitch speaks first, having noticed something on the machine.
UNPROMPTED_CONTRACT = """Nobody asked you anything. You noticed this and decided to speak first: {situation}.

Say one short, natural line about it, the way a pet on the desk would pipe up. Do not greet the user as if the conversation is starting over, do not ask what they are working on, and do not claim to see their screen, their files or anything you were not just told."""


@dataclass
class PromptContext:
    """Everything the prompt builder is allowed to know about the runtime."""

    state: str = "idle"
    emotion: EmotionState = field(default_factory=EmotionState)
    mood: str = "content"
    last_interaction: str | None = None
    memories: list[str] = field(default_factory=list)
    situation: str | None = None
    activity: str | None = None


def _time_of_day(now: datetime | None = None) -> str:
    hour = (now or datetime.now()).hour
    if hour < 5:
        return "late night"
    if hour < 12:
        return "morning"
    if hour < 17:
        return "afternoon"
    if hour < 22:
        return "evening"
    return "night"


def personality_for(key: str) -> Personality:
    return PERSONALITIES.get(key, PERSONALITIES["default"])


def build_system_prompt(personality_key: str, context: PromptContext) -> str:
    """Assemble the system message from the prompt layers."""
    personality = personality_for(personality_key)
    emotion = context.emotion

    layers = [
        SYSTEM_CONTRACT,
        personality.describe(),
        "How you feel right now (0 to 1): "
        + ", ".join(f"{name} {value:.2f}" for name, value in emotion.as_dict().items())
        + f". Overall you feel {context.mood}.",
        f"On screen you are currently: {context.state}. "
        f"It is {_time_of_day()} for the user.",
    ]

    if context.activity:
        # One short line, so the model can answer "what am I doing" without a
        # second request, and colour its replies with what is going on.
        layers.append(f"What the user has been doing: {context.activity}")
    if context.situation:
        layers.append(UNPROMPTED_CONTRACT.format(situation=context.situation))
    if context.last_interaction:
        layers.append(f"The user most recently: {context.last_interaction}.")
    if context.memories:
        remembered = "\n".join(f"- {m}" for m in context.memories)
        layers.append(f"Things you remember about the user:\n{remembered}")

    layers.append(
        "Let your feelings colour the reply without stating the numbers. "
        "High annoyance makes you terse; high sleepiness makes you drowsy; "
        "high affection makes you warmer."
    )
    return "\n\n".join(layers)


# Offline replies, used when there is no API key or the network is unreachable.
OFFLINE_REPLIES = [
    "My brain's offline right now, but I'm still here.",
    "Can't reach my thoughts at the moment. Still good company though.",
    "No connection, no clever answers. Just vibes.",
]

FAILURE_REPLIES = {
    "timeout": "That took too long to think about. Ask me again?",
    "rate_limit": "I'm thinking too fast for my own good. Give me a second.",
    "auth": "My API key isn't working. Check the settings?",
    "network": "I can't reach my brain right now.",
    "invalid": "I thought something, but it came out garbled.",
    "unknown": "Something went wrong in my head. Try again?",
    "budget": "I've used up today's thinking budget. I'm still here, just cheaper.",
}
