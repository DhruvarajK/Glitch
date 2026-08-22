"""Launching an app, but only one the user has approved by name.

This is the only part of Glitch that starts another program, so it is the only
part that could be turned against the user. Two rules keep it safe:

* The requested name is looked up in a whitelist the user controls. Text from
  a chat message - or from a model that read a web page through the user - is
  never treated as a command, only as a key.
* The command is run as an argument vector with no shell, so quoting tricks in
  a whitelist entry cannot chain a second command.

An unknown name is refused and offers what is actually available.
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass

from core.persistence.config import ConfigManager
from core.utils.logger import get_logger

log = get_logger("launcher")

# Ships with Windows, so these work on any machine without configuration.
DEFAULT_WHITELIST: dict[str, str] = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "paint": "mspaint.exe",
}

# Names people use that do not match the whitelist key they mean.
ALIASES: dict[str, str] = {
    "calc": "calculator",
    "vs code": "code",
    "vscode": "code",
    "visual studio code": "code",
    "the calculator": "calculator",
    "notepad++": "notepad plus plus",
}


@dataclass(frozen=True)
class LaunchResult:
    ok: bool
    message: str


def _normalise(name: str) -> str:
    name = " ".join((name or "").lower().split())
    for prefix in ("the ", "my ", "up "):
        if name.startswith(prefix):
            name = name[len(prefix):]
    return ALIASES.get(name, name)


class AppLauncher:
    """Starts whitelisted applications, and nothing else."""

    def __init__(self, config: ConfigManager) -> None:
        self.config = config

    def whitelist(self) -> dict[str, str]:
        """The user's approved apps, merged over the built-in defaults."""
        configured = self.config.get("app_whitelist", {}) or {}
        if not isinstance(configured, dict):
            log.warning("app_whitelist is not a mapping; ignoring it")
            configured = {}
        merged = dict(DEFAULT_WHITELIST)
        for key, command in configured.items():
            if isinstance(key, str) and isinstance(command, str) and command.strip():
                merged[_normalise(key)] = command.strip()
        return merged

    def known_names(self) -> list[str]:
        return sorted(self.whitelist())

    def resolve(self, name: str) -> str | None:
        """The command for `name`, or None when it is not approved."""
        return self.whitelist().get(_normalise(name))

    def launch(self, name: str) -> LaunchResult:
        command = self.resolve(name)
        if command is None:
            known = self.known_names()
            listed = ", ".join(known[:6]) if known else "nothing yet"
            return LaunchResult(
                False,
                f"I'm not allowed to open that. I can open: {listed}. "
                "Add more in Settings.",
            )

        # A bare executable name has to exist on PATH; a full path has to exist.
        if not shutil.which(command):
            return LaunchResult(False, f"I couldn't find {name} on this machine.")

        try:
            # No shell: the command is a program plus arguments, never a string
            # the operating system re-parses.
            subprocess.Popen(
                [command],
                shell=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except (OSError, ValueError) as exc:
            log.error("Could not launch %r: %s", command, exc)
            return LaunchResult(False, f"That wouldn't open. ({exc.__class__.__name__})")

        log.info("Launched %s", command)
        return LaunchResult(True, f"Opening {name}.")
