"""Versioned JSON configuration with defaults, validation and migration."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Callable

from core.utils.constants import CONFIG_PATH
from core.utils.logger import get_logger

log = get_logger("config")

CONFIG_VERSION = 1

DEFAULTS: dict[str, Any] = {
    "version": CONFIG_VERSION,
    # Appearance
    "pet_scale": 1.0,
    "animation_speed": 1.0,
    # Window behaviour
    "always_on_top": True,
    "click_through": False,
    "start_with_windows": False,
    # Movement
    "movement_speed": 80.0,
    "autonomous_movement": True,
    "multi_monitor_roaming": True,
    # Stand on the top edges of open windows, not just the desktop.
    "window_walking": True,
    # Behaviour tuning
    "reaction_frequency": 1.0,
    "sleep_enabled": True,
    "sounds_enabled": False,
    "sound_volume": 0.4,
    "idle_seconds_before_sleep": 300.0,
    # AI
    "ai_enabled": True,
    "ai_model": "gpt-4o-mini",
    "ai_temperature": 0.8,
    "conversation_memory": 12,
    "personality": "default",
    # Cost ceilings. Both are per day and count every request Glitch makes,
    # unprompted ones included. Zero means no limit.
    "daily_request_limit": 60,
    "daily_token_limit": 120_000,
    # Actions
    "app_whitelist": {},
    # Awareness. Glitch watches process names only unless titles are opted in.
    "awareness_enabled": True,
    "awareness_ai_replies": False,
    "awareness_read_window_titles": False,
    "proactive_cooldown_seconds": 240.0,
    "proactive_daily_limit": 20,
    # Advanced
    "debug": False,
    "logging_level": "INFO",
    "onboarded": False,
    # Last known position, restored on launch.
    "last_position": None,
}

# Validators clamp/coerce values loaded from disk. A value that cannot be
# coerced falls back to its default rather than breaking startup.
_VALIDATORS: dict[str, Callable[[Any], Any]] = {
    "pet_scale": lambda v: min(max(float(v), 0.3), 4.0),
    "animation_speed": lambda v: min(max(float(v), 0.25), 3.0),
    "always_on_top": bool,
    "click_through": bool,
    "start_with_windows": bool,
    "movement_speed": lambda v: min(max(float(v), 10.0), 400.0),
    "autonomous_movement": bool,
    "multi_monitor_roaming": bool,
    "window_walking": bool,
    "reaction_frequency": lambda v: min(max(float(v), 0.0), 3.0),
    "sleep_enabled": bool,
    "sounds_enabled": bool,
    "sound_volume": lambda v: min(max(float(v), 0.0), 1.0),
    "idle_seconds_before_sleep": lambda v: min(max(float(v), 10.0), 7200.0),
    "ai_enabled": bool,
    "ai_model": str,
    "ai_temperature": lambda v: min(max(float(v), 0.0), 2.0),
    "conversation_memory": lambda v: min(max(int(v), 2), 100),
    "personality": str,
    "daily_request_limit": lambda v: max(int(v), 0),
    "daily_token_limit": lambda v: max(int(v), 0),
    "app_whitelist": lambda v: {
        str(name).strip().lower(): str(command).strip()
        for name, command in dict(v).items()
        if str(name).strip() and str(command).strip()
    },
    "awareness_enabled": bool,
    "awareness_ai_replies": bool,
    "awareness_read_window_titles": bool,
    "proactive_cooldown_seconds": lambda v: min(max(float(v), 60.0), 21600.0),
    "proactive_daily_limit": lambda v: min(max(int(v), 0), 100),
    "debug": bool,
    "onboarded": bool,
    "logging_level": lambda v: str(v).upper(),
}


class ConfigManager:
    """Loads, validates, migrates and saves user preferences."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else CONFIG_PATH
        self._data: dict[str, Any] = dict(DEFAULTS)
        self._listeners: list[Callable[[str, Any], None]] = []
        self.load()

    # ------------------------------------------------------------------ load
    def load(self) -> None:
        raw: dict[str, Any] = {}
        if self.path.exists():
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                if not isinstance(raw, dict):
                    raise ValueError("config root is not an object")
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                log.error("Config unreadable (%s); restoring defaults", exc)
                self._quarantine()
                raw = {}

        raw = self._migrate(raw)
        merged = dict(DEFAULTS)
        for key, value in raw.items():
            if key not in DEFAULTS:
                continue  # drop unknown keys instead of carrying them forever
            merged[key] = self._validate(key, value)
        merged["version"] = CONFIG_VERSION
        self._data = merged

    def _quarantine(self) -> None:
        """Keep a copy of a corrupt config so the user can inspect it."""
        try:
            shutil.copy2(self.path, self.path.with_suffix(".json.bak"))
        except OSError:
            pass

    def _validate(self, key: str, value: Any) -> Any:
        validator = _VALIDATORS.get(key)
        if validator is None:
            return value
        try:
            return validator(value)
        except (TypeError, ValueError):
            log.warning("Invalid value for %r (%r); using default", key, value)
            return DEFAULTS[key]

    def _migrate(self, raw: dict[str, Any]) -> dict[str, Any]:
        version = raw.get("version", 0)
        if version == CONFIG_VERSION:
            return raw
        if version > CONFIG_VERSION:
            log.warning("Config is from a newer version (%s); using defaults", version)
            return {}
        # No historical migrations yet; future steps chain from here.
        log.info("Migrating config from version %s to %s", version, CONFIG_VERSION)
        return raw

    # ------------------------------------------------------------------ save
    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
            tmp.replace(self.path)
        except OSError as exc:
            log.error("Could not save config: %s", exc)

    # -------------------------------------------------------------- accessors
    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, DEFAULTS.get(key, default))

    def set(self, key: str, value: Any, *, save: bool = True) -> None:
        value = self._validate(key, value)
        if self._data.get(key) == value:
            return
        self._data[key] = value
        for listener in list(self._listeners):
            try:
                listener(key, value)
            except Exception:  # a bad listener must not break settings
                log.exception("Config listener failed for %r", key)
        if save:
            self.save()

    def update(self, values: dict[str, Any]) -> None:
        for key, value in values.items():
            self.set(key, value, save=False)
        self.save()

    def reset(self) -> None:
        self._data = dict(DEFAULTS)
        self.save()

    def as_dict(self) -> dict[str, Any]:
        return dict(self._data)

    def on_change(self, listener: Callable[[str, Any], None]) -> None:
        self._listeners.append(listener)

    def __getitem__(self, key: str) -> Any:
        return self.get(key)
