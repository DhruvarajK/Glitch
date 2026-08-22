"""Recognising an instruction without asking a model to read it.

Every phrasing matched here is an API request that never happens. The pet is
asked the same handful of things constantly - set a reminder, open something,
be quiet, what have I been doing - and none of it needs a language model.

Anything not matched falls through to the brain as ordinary conversation, so a
missed phrasing costs nothing but a normal reply.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Longest units first, so "minutes" is never matched as "m" plus leftovers.
_UNITS: tuple[tuple[str, float], ...] = (
    ("hours", 60.0),
    ("hour", 60.0),
    ("hrs", 60.0),
    ("hr", 60.0),
    ("minutes", 1.0),
    ("minute", 1.0),
    ("mins", 1.0),
    ("min", 1.0),
    ("seconds", 1.0 / 60.0),
    ("second", 1.0 / 60.0),
    ("secs", 1.0 / 60.0),
    ("sec", 1.0 / 60.0),
    ("h", 60.0),
    ("m", 1.0),
)

_WORD_NUMBERS = {
    "a": 1.0, "an": 1.0, "one": 1.0, "two": 2.0, "three": 3.0, "four": 4.0,
    "five": 5.0, "ten": 10.0, "fifteen": 15.0, "twenty": 20.0, "thirty": 30.0,
    "forty": 40.0, "sixty": 60.0,
}

_DURATION = re.compile(
    r"\b(?P<amount>\d+(?:\.\d+)?|"
    + "|".join(re.escape(word) for word in sorted(_WORD_NUMBERS, key=len, reverse=True))
    + r")\s*(?P<unit>"
    + "|".join(unit for unit, _ in _UNITS)
    + r")\b",
    re.IGNORECASE,
)

# Everyday phrasings rewritten into something the duration pattern can read.
# Without this, "half an hour" parses as half of one hour's *unit* and the
# leftover words end up in the reminder text.
_PHRASES: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r"\ban?\s+hour\s+and\s+a\s+half\b", re.IGNORECASE), "90 minutes"),
    (re.compile(r"\bhalf\s+an?\s+hour\b", re.IGNORECASE), "30 minutes"),
    (re.compile(r"\bhalf\s+an?\s+minute\b", re.IGNORECASE), "30 seconds"),
    (re.compile(r"\bquarter\s+of\s+an?\s+hour\b", re.IGNORECASE), "15 minutes"),
    (re.compile(r"\ba\s+couple\s+(?:of\s+)?(minutes|hours)\b", re.IGNORECASE), r"2 \1"),
    (re.compile(r"\ba\s+few\s+(minutes|hours)\b", re.IGNORECASE), r"3 \1"),
)

# "remind me in 20 minutes to stretch", "remind me to stand up in half an hour"
_REMIND = re.compile(
    r"^\s*(?:hey\s+|please\s+|can you\s+|could you\s+)*remind me\b(?P<rest>.*)$",
    re.IGNORECASE | re.DOTALL,
)
_REMIND_SPLIT = re.compile(r"\b(?:to|that|about)\b", re.IGNORECASE)

# "open spotify", "launch vs code", "start notepad for me"
_OPEN = re.compile(
    r"^\s*(?:hey\s+|please\s+|can you\s+|could you\s+)*"
    r"(?:open|launch|start|run)\s+(?:up\s+)?(?P<target>.+?)"
    r"(?:\s+for me)?\s*[.!?]*$",
    re.IGNORECASE,
)

# "be quiet for an hour", "shut up", "stop talking for 30 minutes"
_QUIET = re.compile(
    r"^\s*(?:hey\s+|please\s+)*(?:be\s+quiet|shut\s+up|stop\s+talking|"
    r"leave\s+me\s+alone|quiet\s+mode|be\s+silent)\b(?P<rest>.*)$",
    re.IGNORECASE | re.DOTALL,
)
_UNQUIET = re.compile(
    r"^\s*(?:hey\s+|please\s+)*(?:you\s+can\s+)?(?:talk\s+again|speak\s+again|"
    r"stop\s+being\s+quiet|unmute|come\s+back)\b",
    re.IGNORECASE,
)

# "what am I doing", "how long have I been coding", "what did I do today"
_STATS = re.compile(
    r"^\s*(?:hey\s+)?(?:what|how long|how much)\b.*\b"
    r"(?:am i doing|have i been|did i do|i been doing|have i spent|"
    r"was i doing|am i up to)\b",
    re.IGNORECASE | re.DOTALL,
)

# Phrases that read like "open X" but are about Glitch, not about an app.
_NOT_APPS = frozenset({"settings", "the settings", "your settings", "chat", "up"})


@dataclass(frozen=True)
class ToolCall:
    """An instruction recognised locally, ready to run."""

    name: str
    text: str = ""
    minutes: float = 0.0
    data: dict = field(default_factory=dict)


def normalise(text: str) -> str:
    """Rewrite "half an hour" and friends into plain numbers and units."""
    for pattern, replacement in _PHRASES:
        text = pattern.sub(replacement, text)
    return text


def parse_duration(text: str) -> float | None:
    """Minutes described anywhere in `text`, or None when it names no duration."""
    match = _DURATION.search(normalise(text))
    if match is None:
        return None
    raw = match.group("amount").lower()
    amount = _WORD_NUMBERS.get(raw)
    if amount is None:
        try:
            amount = float(raw)
        except ValueError:
            return None
    unit = match.group("unit").lower()
    scale = next(scale for name, scale in _UNITS if name == unit)
    minutes = amount * scale
    return minutes if minutes > 0 else None


def _strip_duration(text: str) -> str:
    """Remove the "in 20 minutes" part, leaving what the reminder is about."""
    cleaned = _DURATION.sub("", text, count=1)
    cleaned = re.sub(r"\b(?:in|after|within)\s*$", "", cleaned.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"^\s*(?:in|after|within)\b", "", cleaned.strip(), flags=re.IGNORECASE)
    return re.sub(r"\s{2,}", " ", cleaned).strip(" ,.!?-")


def parse(message: str) -> ToolCall | None:
    """The instruction in `message`, or None when it is just conversation."""
    text = (message or "").strip()
    if not text:
        return None

    if _UNQUIET.match(text):
        return ToolCall("unquiet")

    quiet = _QUIET.match(text)
    if quiet:
        minutes = parse_duration(quiet.group("rest")) or 60.0
        return ToolCall("quiet", minutes=minutes)

    remind = _REMIND.match(text)
    if remind:
        rest = normalise(remind.group("rest"))
        minutes = parse_duration(rest)
        subject = _strip_duration(rest)
        # "remind me to X" - drop the connector, keep X.
        parts = _REMIND_SPLIT.split(subject, maxsplit=1)
        subject = (parts[1] if len(parts) > 1 else parts[0]).strip(" ,.:-")
        if minutes is None:
            return ToolCall("remind_needs_time", text=subject)
        return ToolCall("remind", text=subject, minutes=minutes)

    if _STATS.match(text):
        return ToolCall("stats")

    opened = _OPEN.match(text)
    if opened:
        target = opened.group("target").strip(" .!?")
        if target.lower() in _NOT_APPS:
            return None
        return ToolCall("open_app", text=target)

    return None
