"""Reading the desktop's open windows so Glitch has something to stand on.

Everything Win32-specific lives here. Without pywin32, or on a machine whose
monitors cannot be matched up, the source reports no platforms at all and
Glitch walks on the desktop exactly as it did before.
"""
from __future__ import annotations

import ctypes
import os
import time
from ctypes import wintypes

from PySide6.QtGui import QGuiApplication

from core.screen.geometry import Rect
from core.screen.manager import ScreenManager
from core.screen.platforms import Platform
from core.utils.logger import get_logger

log = get_logger("platforms")

try:  # pragma: no cover - import availability is environment-specific
    import win32api
    import win32con
    import win32gui
    import win32process
except ImportError:  # pragma: no cover
    win32api = win32con = win32gui = win32process = None  # type: ignore[assignment]

try:  # pragma: no cover - present on every supported Windows, absent elsewhere
    _dwmapi = ctypes.windll.dwmapi  # type: ignore[attr-defined]
except (AttributeError, OSError):  # pragma: no cover
    _dwmapi = None

# Window is present but not being composited: the other virtual desktops, and
# suspended UWP apps, both look ordinary to every other Win32 call.
DWMWA_CLOAKED = 14
# The rectangle the user actually sees. GetWindowRect includes the invisible
# resize border, which would leave Glitch standing a few pixels off the edge.
DWMWA_EXTENDED_FRAME_BOUNDS = 9

# Shell surfaces that are windows only in the technical sense.
EXCLUDED_CLASSES = frozenset(
    {
        "Shell_TrayWnd",
        "Shell_SecondaryTrayWnd",
        "Progman",
        "WorkerW",
        "Button",
        "DV2ControlHost",
        "Windows.UI.Core.CoreWindow",
        "ApplicationManager_DesktopShellWindow",
        "Xaml_WindowedPopupClass",
        "ForegroundStaging",
        "TaskListThumbnailWnd",
        "MultitaskingViewFrame",
    }
)

# Anything smaller is a tooltip or a splash screen, not somewhere to stand.
MIN_PLATFORM_WIDTH = 160
MIN_PLATFORM_HEIGHT = 100
# Only the front of the stack can be stood on, and the cap bounds the cost of
# the occlusion test in core.screen.platforms.
MAX_PLATFORMS = 40
# Windows move while being dragged, so this is refreshed often enough to keep
# up without rescanning the desktop on every one of the 30 frames per second.
REFRESH_SECONDS = 0.15


class WindowPlatformSource:
    """Lists the window top edges Glitch can currently stand on."""

    def __init__(self, screens: ScreenManager) -> None:
        self.screens = screens
        self._own_pid = os.getpid()
        self._monitors: list[tuple[Rect, Rect]] = []
        self._cache: list[Platform] = []
        self._cached_at = 0.0

        self._refresh_monitors()
        screens.configuration_changed.connect(self._refresh_monitors)

    @property
    def available(self) -> bool:
        """False when this machine cannot be read, or read reliably."""
        return win32gui is not None and bool(self._monitors)

    # ------------------------------------------------------------- monitors
    def _refresh_monitors(self) -> None:
        """Pair each physical monitor rect with Qt's logical one.

        Win32 reports window positions in physical pixels while the pet engine
        works in Qt's logical coordinates, and the two differ by one scale
        factor per monitor. Qt does not expose which HMONITOR a screen came
        from, and the names the two APIs use do not match, so the pairing goes
        by arrangement: both APIs lay monitors out in the same order, so
        sorting each list and zipping them lines them up. Every pair is then
        checked against the screen's own scale factor, and a set that does not
        agree is discarded rather than guessed at.
        """
        self._monitors = []
        self._cache = []
        self._cached_at = 0.0
        if win32api is None:
            return

        screens = sorted(
            (
                (
                    Rect(
                        screen.geometry().x(),
                        screen.geometry().y(),
                        screen.geometry().width(),
                        screen.geometry().height(),
                    ),
                    float(screen.devicePixelRatio()),
                )
                for screen in QGuiApplication.screens()
            ),
            key=lambda pair: (pair[0].top, pair[0].left),
        )
        physical = sorted(self._physical_monitors(), key=lambda r: (r.top, r.left))

        if not physical or len(physical) != len(screens):
            log.info(
                "Found %d monitor(s) for %d Qt screen(s); window walking off",
                len(physical),
                len(screens),
            )
            return

        pairs: list[tuple[Rect, Rect]] = []
        for monitor, (logical, ratio) in zip(physical, screens):
            # A pair only makes sense if the physical size really is the
            # logical size at that screen's scale; rounding costs a pixel or two.
            if (
                abs(monitor.width - logical.width * ratio) > 2
                or abs(monitor.height - logical.height * ratio) > 2
            ):
                log.info(
                    "Monitor %s does not match Qt screen %s at %.2fx; window walking off",
                    monitor,
                    logical,
                    ratio,
                )
                return
            pairs.append((monitor, logical))
        self._monitors = pairs

    def _physical_monitors(self) -> list[Rect]:
        try:
            handles = win32api.EnumDisplayMonitors()
        except Exception as exc:  # pragma: no cover - driver dependent
            log.debug("Could not enumerate monitors: %s", exc)
            return []

        found: list[Rect] = []
        for entry in handles:
            try:
                left, top, right, bottom = win32api.GetMonitorInfo(entry[0])["Monitor"]
            except Exception:  # a monitor can be detached mid-enumeration
                continue
            if right > left and bottom > top:
                found.append(Rect(left, top, right - left, bottom - top))
        return found

    def _monitor_for(self, x: float, y: float) -> tuple[Rect, Rect]:
        for physical, logical in self._monitors:
            if physical.contains_point(x, y):
                return physical, logical
        return min(
            self._monitors,
            key=lambda pair: (pair[0].center_x - x) ** 2
            + (pair[0].y + pair[0].height / 2 - y) ** 2,
        )

    def _to_logical(self, left: int, top: int, right: int, bottom: int) -> Rect:
        physical, logical = self._monitor_for((left + right) / 2, top)
        scale_x = logical.width / physical.width
        scale_y = logical.height / physical.height
        lx = logical.left + (left - physical.left) * scale_x
        ly = logical.top + (top - physical.top) * scale_y
        rx = logical.left + (right - physical.left) * scale_x
        ry = logical.top + (bottom - physical.top) * scale_y
        return Rect(round(lx), round(ly), round(rx - lx), round(ry - ly))

    # --------------------------------------------------------------- scanning
    def platforms(self) -> list[Platform]:
        """The current platforms, front to back, rescanned at most every tick."""
        if not self.available:
            return []
        now = time.monotonic()
        if now - self._cached_at < REFRESH_SECONDS:
            return self._cache
        self._cache = self._scan()
        self._cached_at = now
        return self._cache

    def invalidate(self) -> None:
        """Force the next call to rescan, whatever the cache says."""
        self._cached_at = 0.0

    def _scan(self) -> list[Platform]:
        found: list[Platform] = []

        def visit(handle: int, _: object) -> bool:
            # Raising inside an EnumWindows callback aborts the scan, so every
            # failure is swallowed here and simply costs one window.
            try:
                platform = self._platform_for(handle)
            except Exception:
                return True
            if platform is not None:
                found.append(platform)
            return len(found) < MAX_PLATFORMS

        try:
            win32gui.EnumWindows(visit, None)
        except Exception as exc:
            # pywin32 re-raises the callback's early stop as an error.
            log.debug("Window scan ended early: %s", exc)
        return found

    def _platform_for(self, handle: int) -> Platform | None:
        if not win32gui.IsWindowVisible(handle) or win32gui.IsIconic(handle):
            return None
        _, pid = win32process.GetWindowThreadProcessId(handle)
        if pid == self._own_pid:
            return None  # Glitch's own window, bubble and settings
        if win32gui.GetWindowLong(handle, win32con.GWL_EXSTYLE) & win32con.WS_EX_TOOLWINDOW:
            return None
        if win32gui.GetClassName(handle) in EXCLUDED_CLASSES:
            return None
        if not win32gui.GetWindowText(handle):
            return None
        if self._cloaked(handle):
            return None

        rect = self._to_logical(*self._frame_bounds(handle))
        if rect.width < MIN_PLATFORM_WIDTH or rect.height < MIN_PLATFORM_HEIGHT:
            return None
        return Platform(handle=handle, rect=rect)

    def _frame_bounds(self, handle: int) -> tuple[int, int, int, int]:
        if _dwmapi is not None:
            bounds = wintypes.RECT()
            try:
                status = _dwmapi.DwmGetWindowAttribute(
                    wintypes.HWND(handle),
                    ctypes.c_uint(DWMWA_EXTENDED_FRAME_BOUNDS),
                    ctypes.byref(bounds),
                    ctypes.sizeof(bounds),
                )
            except Exception:  # pragma: no cover
                status = -1
            if status == 0:
                return bounds.left, bounds.top, bounds.right, bounds.bottom
        return win32gui.GetWindowRect(handle)

    def _cloaked(self, handle: int) -> bool:
        if _dwmapi is None:
            return False
        value = ctypes.c_int(0)
        try:
            status = _dwmapi.DwmGetWindowAttribute(
                wintypes.HWND(handle),
                ctypes.c_uint(DWMWA_CLOAKED),
                ctypes.byref(value),
                ctypes.sizeof(value),
            )
        except Exception:  # pragma: no cover
            return False
        return status == 0 and value.value != 0


def create_platform_source(screens: ScreenManager) -> WindowPlatformSource | None:
    """A source for this machine, or None when windows cannot be read."""
    source = WindowPlatformSource(screens)
    if not source.available:
        log.info("Window walking unavailable; Glitch will stay on the desktop")
        return None
    log.info("Window walking enabled")
    return source
