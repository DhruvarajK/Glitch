"""A tiny synchronous publish/subscribe bus.

Subsystems talk through this instead of holding references to one another, so
the pet engine never has to import the AI layer to react to it. A handler that
raises is logged and skipped: one broken subscriber cannot stop an event from
reaching the rest.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Callable

from core.events.events import Event, EventType
from core.utils.logger import get_logger

log = get_logger("events")

Handler = Callable[[Event], None]


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[EventType, list[Handler]] = defaultdict(list)
        self._wildcard: list[Handler] = []

    def subscribe(self, event_type: EventType, handler: Handler) -> Callable[[], None]:
        """Register `handler`; returns a callable that unsubscribes it."""
        self._handlers[event_type].append(handler)
        return lambda: self.unsubscribe(event_type, handler)

    def subscribe_all(self, handler: Handler) -> Callable[[], None]:
        self._wildcard.append(handler)
        return lambda: self._wildcard.remove(handler)

    def unsubscribe(self, event_type: EventType, handler: Handler) -> None:
        try:
            self._handlers[event_type].remove(handler)
        except ValueError:
            pass

    def emit(self, event_type: EventType, **data: object) -> Event:
        event = Event(event_type, dict(data))
        self.dispatch(event)
        return event

    def dispatch(self, event: Event) -> None:
        for handler in list(self._handlers.get(event.type, ())) + list(self._wildcard):
            try:
                handler(event)
            except Exception:
                log.exception("Event handler failed for %s", event.type.value)

    def clear(self) -> None:
        self._handlers.clear()
        self._wildcard.clear()
