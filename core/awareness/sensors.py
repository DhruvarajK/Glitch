"""Reading the machine.

Everything Windows-specific is confined to this module and every call is
optional: if `pywin32` or `psutil` is missing, or a call is refused, the sensor
degrades to a snapshot full of Nones and the pet simply notices less.
"""
from __future__ import annotations

import time
from datetime import date, datetime

from core.awareness.signals import Snapshot
from core.utils.logger import get_logger

log = get_logger("awareness")

try:  # pragma: no cover - import availability is environment-specific
    import psutil
except ImportError:  # pragma: no cover
    psutil = None  # type: ignore[assignment]

try:  # pragma: no cover
    import win32api
    import win32con
    import win32gui
    import win32process
except ImportError:  # pragma: no cover
    win32api = win32con = win32gui = win32process = None  # type: ignore[assignment]

# Processes never worth reporting: the shell, and Glitch itself.
IGNORED_PROCESSES = frozenset(
    {"explorer.exe", "searchhost.exe", "shellexperiencehost.exe",
     "applicationframehost.exe", "textinputhost.exe", "python.exe", "glitch.exe"}
)


class Sensor:
    """Base sensor: knows the clock and nothing else."""

    #: True when this sensor can see more than the time of day.
    detailed = False

    def snapshot(self) -> Snapshot:
        now = datetime.now()
        return Snapshot(at=time.monotonic(), day=now.date().toordinal(), hour=now.hour)

    def close(self) -> None:
        """Release anything held open. The base sensor holds nothing."""


class WindowsSensor(Sensor):
    """Foreground app, running processes, input idle time and battery."""

    detailed = True

    def __init__(self, *, read_titles: bool = False) -> None:
        self.read_titles = read_titles
        # Scanning every process is the expensive part, so it runs less often
        # than the poll interval; launches are noticed within ~10 seconds.
        self._process_cache: frozenset[str] = frozenset()
        self._process_cache_at = 0.0
        self._process_cache_ttl = 10.0

    def snapshot(self) -> Snapshot:
        now = datetime.now()
        foreground, title, fullscreen = self._foreground()
        return Snapshot(
            at=time.monotonic(),
            day=now.date().toordinal(),
            hour=now.hour,
            foreground=foreground,
            foreground_title=title if self.read_titles else None,
            running=self._running(),
            idle_seconds=self._idle_seconds(),
            battery_percent=self._battery()[0],
            battery_charging=self._battery()[1],
            fullscreen=fullscreen,
        )

    # ----------------------------------------------------------- foreground
    def _foreground(self) -> tuple[str | None, str | None, bool]:
        if win32gui is None:
            return None, None, False
        try:
            handle = win32gui.GetForegroundWindow()
            if not handle:
                return None, None, False
            _, pid = win32process.GetWindowThreadProcessId(handle)
            name = self._process_name(pid)
            title = win32gui.GetWindowText(handle) or None
            return name, title, self._is_fullscreen(handle)
        except Exception as exc:  # a foreground window can vanish mid-call
            log.debug("Foreground window unreadable: %s", exc)
            return None, None, False

    def _process_name(self, pid: int) -> str | None:
        if psutil is None or not pid:
            return None
        try:
            name = psutil.Process(pid).name().lower()
        except Exception:
            return None
        return None if name in IGNORED_PROCESSES else name

    def _is_fullscreen(self, handle: int) -> bool:
        """True when the focused window covers its whole monitor.

        Games and presentations are the cases that matter, and both look the
        same from here: a borderless window the size of the screen.
        """
        if win32gui is None or win32api is None or win32con is None:
            return False
        try:
            monitor = win32api.MonitorFromWindow(handle, win32con.MONITOR_DEFAULTTONEAREST)
            bounds = win32api.GetMonitorInfo(monitor)["Monitor"]
            window = win32gui.GetWindowRect(handle)
            return (
                window[0] <= bounds[0] and window[1] <= bounds[1]
                and window[2] >= bounds[2] and window[3] >= bounds[3]
            )
        except Exception:
            return False

    # ------------------------------------------------------------ processes
    def _running(self) -> frozenset[str]:
        if psutil is None:
            return frozenset()
        now = time.monotonic()
        if now - self._process_cache_at < self._process_cache_ttl:
            return self._process_cache
        try:
            names = {
                (process.info["name"] or "").lower()
                for process in psutil.process_iter(["name"])
            }
        except Exception as exc:
            log.debug("Process scan failed: %s", exc)
            return self._process_cache
        self._process_cache = frozenset(names - IGNORED_PROCESSES - {""})
        self._process_cache_at = now
        return self._process_cache

    # ----------------------------------------------------------------- idle
    def _idle_seconds(self) -> float:
        """Seconds since the last keyboard or mouse input, system-wide."""
        if win32api is None:
            return 0.0
        try:
            last_input = win32api.GetLastInputInfo()
            ticks = win32api.GetTickCount()
            return max(0.0, (ticks - last_input) / 1000.0)
        except Exception:
            return 0.0

    # -------------------------------------------------------------- battery
    def _battery(self) -> tuple[float | None, bool | None]:
        if psutil is None:
            return None, None
        try:
            battery = psutil.sensors_battery()
        except Exception:
            return None, None
        if battery is None:
            return None, None  # a desktop with no battery at all
        return float(battery.percent), bool(battery.power_plugged)


def create_sensor(*, read_titles: bool = False) -> Sensor:
    """The best sensor this machine supports."""
    if win32gui is None and psutil is None:
        log.info("No environment sensors available; awareness limited to the clock")
        return Sensor()
    return WindowsSensor(read_titles=read_titles)
