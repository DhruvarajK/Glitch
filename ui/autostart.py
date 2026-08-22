"""Windows "start with Windows" support via the per-user Run key.

Only the current user's registry is touched, and only when the user asks for
it from settings.
"""
from __future__ import annotations

import sys
from pathlib import Path

from core.utils.constants import APP_NAME
from core.utils.logger import get_logger

log = get_logger("autostart")

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _launch_command() -> str:
    """The command Windows should run at logon."""
    executable = Path(sys.executable)
    if executable.stem.lower() not in ("python", "pythonw"):
        return f'"{executable}"'  # frozen build: the exe launches itself
    script = Path(sys.argv[0]).resolve()
    # pythonw keeps the console window from appearing at logon.
    windowless = executable.with_name("pythonw.exe")
    runner = windowless if windowless.exists() else executable
    return f'"{runner}" "{script}"'


def set_autostart(enabled: bool) -> bool:
    """Add or remove the logon entry. Returns False if the registry refused."""
    if sys.platform != "win32":
        log.info("Autostart is only supported on Windows")
        return False
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            if enabled:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _launch_command())
                log.info("Autostart enabled")
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                    log.info("Autostart disabled")
                except FileNotFoundError:
                    pass  # already absent
        return True
    except OSError:
        log.exception("Could not update the autostart entry")
        return False


def is_autostart_enabled() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, APP_NAME)
            return True
    except (OSError, FileNotFoundError):
        return False
