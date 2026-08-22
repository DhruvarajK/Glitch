"""Glitch's optional intelligence layer.

Network work runs on a dedicated asyncio thread and never touches the Qt GUI
thread. Results come back as Qt signals, which Qt delivers to the GUI thread
for us. Every failure path ends in a signal, so the pet can always recover.
"""
from __future__ import annotations

import asyncio
import json
import threading
import time
import uuid
from typing import Any

from PySide6.QtCore import QObject, Signal

from core.ai.conversation import ConversationManager
from core.ai.models import RESPONSE_JSON_SCHEMA, AIResponse
from core.ai.prompts import FAILURE_REPLIES, PromptContext, build_system_prompt
from core.persistence.config import ConfigManager
from core.persistence.credentials import get_api_key
from core.persistence.database import Database
from core.utils.logger import get_logger

log = get_logger("brain")

REQUEST_TIMEOUT = 45.0
MAX_OUTPUT_TOKENS = 400


def extract_partial_message(raw: str) -> str:
    """Pull the `message` value out of a partially received JSON object.

    Streaming a structured response means the bubble would otherwise stay empty
    until the final token. This decodes as much of the string as has arrived,
    ignoring an escape sequence that is still mid-flight.
    """
    key = raw.find('"message"')
    if key == -1:
        return ""
    quote = raw.find('"', key + len('"message"') + 1)
    if quote == -1:
        return ""

    out: list[str] = []
    index = quote + 1
    length = len(raw)
    while index < length:
        char = raw[index]
        if char == "\\":
            if index + 1 >= length:
                break  # escape not fully received yet
            escape = raw[index + 1]
            mapping = {
                "n": "\n", "t": "\t", "r": "\r", '"': '"',
                "\\": "\\", "/": "/", "b": "\b", "f": "\f",
            }
            if escape == "u":
                if index + 6 > length:
                    break
                try:
                    out.append(chr(int(raw[index + 2 : index + 6], 16)))
                except ValueError:
                    pass
                index += 6
                continue
            out.append(mapping.get(escape, escape))
            index += 2
            continue
        if char == '"':
            break  # end of the string value
        out.append(char)
        index += 1
    return "".join(out)


def classify_error(exc: BaseException) -> str:
    """Map an exception onto one of the FAILURE_REPLIES keys."""
    name = type(exc).__name__.lower()
    text = str(exc).lower()
    if isinstance(exc, asyncio.TimeoutError) or "timeout" in name or "timed out" in text:
        return "timeout"
    if "ratelimit" in name or "rate limit" in text or "429" in text:
        return "rate_limit"
    if "authentication" in name or "permission" in name or "api key" in text or "401" in text:
        return "auth"
    if "connection" in name or "network" in text or "getaddrinfo" in text:
        return "network"
    if isinstance(exc, (json.JSONDecodeError, ValueError)):
        return "invalid"
    return "unknown"


class _AsyncRunner(threading.Thread):
    """A background thread owning one asyncio event loop."""

    def __init__(self) -> None:
        super().__init__(name="glitch-ai", daemon=True)
        self.loop = asyncio.new_event_loop()
        self._ready = threading.Event()

    def run(self) -> None:
        asyncio.set_event_loop(self.loop)
        self._ready.set()
        self.loop.run_forever()

    def start(self) -> None:
        super().start()
        self._ready.wait(timeout=5.0)

    def submit(self, coro) -> asyncio.Future:
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def stop(self) -> None:
        if self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)
        self.join(timeout=2.0)


class AIBrain(QObject):
    """Turns a user message into a validated, animated reply.

    Signals carry the request id so a late response from a superseded request
    can be ignored by the UI.
    """

    request_started = Signal(str)
    token_received = Signal(str, str)      # request_id, message text so far
    response_received = Signal(str, object)  # request_id, AIResponse
    request_failed = Signal(str, str, str)   # request_id, kind, user-facing text
    request_cancelled = Signal(str)

    def __init__(
        self,
        config: ConfigManager,
        conversation: ConversationManager,
        database: Database | None = None,
    ) -> None:
        super().__init__()
        self.config = config
        self.conversation = conversation
        self.db = database

        self._runner = _AsyncRunner()
        self._runner.start()
        self._client: Any = None
        self._client_key: str | None = None
        self._current: asyncio.Future | None = None
        self._current_id: str | None = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------ readiness
    @property
    def available(self) -> bool:
        """True when Glitch could actually reach a model right now."""
        return bool(self.config.get("ai_enabled", True)) and bool(get_api_key())

    @property
    def busy(self) -> bool:
        return self._current is not None and not self._current.done()

    def _get_client(self):
        key = get_api_key()
        if not key:
            raise RuntimeError("No API key configured")
        if self._client is None or key != self._client_key:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(api_key=key, timeout=REQUEST_TIMEOUT, max_retries=1)
            self._client_key = key
        return self._client

    def invalidate_client(self) -> None:
        """Force a new client on the next request, e.g. after a key change."""
        self._client = None
        self._client_key = None

    # --------------------------------------------------------------- asking
    def ask(self, message: str, context: PromptContext) -> str | None:
        """Start a request. Any request already in flight is cancelled."""
        message = (message or "").strip()
        if not message:
            return None
        if not self.config.get("ai_enabled", True):
            return None

        self.cancel()
        request_id = uuid.uuid4().hex[:12]
        with self._lock:
            self._current_id = request_id

        if not get_api_key():
            self.request_failed.emit(request_id, "auth", FAILURE_REPLIES["auth"])
            return request_id

        self.conversation.add_user_message(message)
        self.request_started.emit(request_id)
        future = self._runner.submit(self._run(request_id, message, context))
        with self._lock:
            self._current = future
        return request_id

    def cancel(self) -> None:
        with self._lock:
            future, request_id = self._current, self._current_id
            self._current = None
        if future is not None and not future.done():
            future.cancel()
            if request_id:
                self.request_cancelled.emit(request_id)

    def shutdown(self) -> None:
        self.cancel()
        self._runner.stop()

    # ------------------------------------------------------------ the request
    def _build_messages(self, context: PromptContext) -> list[dict[str, str]]:
        context.memories = context.memories or self.conversation.memories()
        system = build_system_prompt(str(self.config.get("personality", "default")), context)
        return [{"role": "system", "content": system}, *self.conversation.context()]

    async def _run(self, request_id: str, message: str, context: PromptContext) -> None:
        model = str(self.config.get("ai_model", "gpt-4o-mini"))
        started = time.monotonic()
        input_tokens = output_tokens = 0
        try:
            client = self._get_client()
            messages = self._build_messages(context)
            raw, input_tokens, output_tokens = await asyncio.wait_for(
                self._stream(client, model, messages, request_id),
                timeout=REQUEST_TIMEOUT,
            )
            response = self._parse(raw)
            self.conversation.add_assistant_message(response.message)
            self._record_usage(model, input_tokens, output_tokens, started, True)
            self.response_received.emit(request_id, response)
        except asyncio.CancelledError:
            self._record_usage(model, input_tokens, output_tokens, started, False, "cancelled")
            raise
        except Exception as exc:  # every failure still reaches the UI
            kind = classify_error(exc)
            log.warning("AI request %s failed (%s): %s", request_id, kind, exc)
            self._record_usage(model, input_tokens, output_tokens, started, False, kind)
            self.request_failed.emit(request_id, kind, FAILURE_REPLIES[kind])
        finally:
            with self._lock:
                if self._current_id == request_id:
                    self._current = None

    async def _stream(
        self, client, model: str, messages: list[dict[str, str]], request_id: str
    ) -> tuple[str, int, int]:
        """Stream one completion, emitting the message text as it arrives."""
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
            "max_completion_tokens": MAX_OUTPUT_TOKENS,
            "response_format": {"type": "json_schema", "json_schema": RESPONSE_JSON_SCHEMA},
            "temperature": float(self.config.get("ai_temperature", 0.8)),
        }

        try:
            stream = await client.chat.completions.create(**kwargs)
        except Exception as exc:
            # Some models reject a custom temperature; retry once with theirs.
            if "temperature" not in str(exc).lower():
                raise
            log.info("Model %s rejected temperature; retrying with the default", model)
            kwargs.pop("temperature")
            stream = await client.chat.completions.create(**kwargs)

        raw = ""
        emitted = ""
        input_tokens = output_tokens = 0
        async for chunk in stream:
            if chunk.usage is not None:
                input_tokens = chunk.usage.prompt_tokens or 0
                output_tokens = chunk.usage.completion_tokens or 0
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            piece = getattr(delta, "content", None)
            if not piece:
                continue
            raw += piece
            partial = extract_partial_message(raw)
            if partial and partial != emitted:
                emitted = partial
                self.token_received.emit(request_id, partial)
        return raw, input_tokens, output_tokens

    def _parse(self, raw: str) -> AIResponse:
        """Validate the model's JSON, salvaging the text if the shape is wrong."""
        try:
            return AIResponse.model_validate_json(raw)
        except Exception:
            log.warning("Structured response failed validation; salvaging text")
            salvaged = extract_partial_message(raw).strip() or raw.strip()
            if not salvaged:
                raise ValueError("empty response")
            return AIResponse.fallback(salvaged[:1200], emotion="neutral")

    def _record_usage(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        started: float,
        success: bool,
        error: str | None = None,
    ) -> None:
        if self.db is None or not self.db.available:
            return
        self.db.record_usage(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            duration_ms=int((time.monotonic() - started) * 1000),
            success=success,
            error=error,
        )
