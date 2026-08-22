"""Virtual-desktop awareness: monitors, floors and boundary clamping.

The desktop is treated as one virtual coordinate space that may include
negative coordinates and monitors of differing size and DPI. Nothing in the
runtime assumes the primary monitor is the only screen.
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QGuiApplication, QScreen

from core.screen.geometry import Rect, clamp
from core.utils.logger import get_logger

log = get_logger("screen")


class ScreenManager(QObject):
    """Reports available geometry and keeps the pet inside it."""

    configuration_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._screens: list[Rect] = []
        self.refresh()

        app = QGuiApplication.instance()
        if app is not None:
            app.screenAdded.connect(self._on_screens_changed)
            app.screenRemoved.connect(self._on_screens_changed)
            primary = app.primaryScreen()
            if primary is not None:
                primary.geometryChanged.connect(self._on_screens_changed)

    # ----------------------------------------------------------------- state
    def refresh(self) -> None:
        screens: list[Rect] = []
        for screen in QGuiApplication.screens():
            geo = screen.availableGeometry()
            screens.append(Rect(geo.x(), geo.y(), geo.width(), geo.height()))
        if not screens:
            screens = [Rect(0, 0, 1920, 1080)]
        self._screens = screens
        log.info("Detected %d screen(s): %s", len(screens), screens)

    def _on_screens_changed(self, *_: object) -> None:
        self.refresh()
        self.configuration_changed.emit()

    @property
    def screens(self) -> list[Rect]:
        return list(self._screens)

    def virtual_bounds(self) -> Rect:
        bounds = self._screens[0]
        for rect in self._screens[1:]:
            bounds = bounds.united(rect)
        return bounds

    # -------------------------------------------------------------- queries
    def screen_at(self, x: float, y: float) -> Rect:
        """Screen containing the point, or the nearest one by centre distance."""
        for rect in self._screens:
            if rect.contains_point(x, y):
                return rect
        return min(
            self._screens,
            key=lambda r: (r.center_x - x) ** 2 + (r.y + r.height / 2 - y) ** 2,
        )

    def primary(self) -> Rect:
        app = QGuiApplication.instance()
        screen: QScreen | None = app.primaryScreen() if app else None
        if screen is not None:
            geo = screen.availableGeometry()
            return Rect(geo.x(), geo.y(), geo.width(), geo.height())
        return self._screens[0]

    def floor_for(self, x: float, y: float, height: int) -> float:
        """Top-coordinate at which a sprite of `height` rests on the desktop."""
        return self.screen_at(x, y).bottom - height

    def clamp_position(
        self, x: float, y: float, width: int, height: int
    ) -> tuple[float, float]:
        """Keep the sprite's rect fully inside the screen it mostly occupies."""
        rect = self.screen_at(x + width / 2, y + height / 2)
        cx = clamp(x, rect.left, max(rect.left, rect.right - width))
        cy = clamp(y, rect.top, max(rect.top, rect.bottom - height))
        return cx, cy

    def adjacent_screen(self, rect: Rect, direction: int) -> Rect | None:
        """The screen continuing horizontally from `rect`, if there is one.

        Screens count as adjacent when they touch or overlap along the shared
        edge and their vertical ranges overlap, which covers stacked and
        offset arrangements as well as a simple side-by-side pair.
        """
        candidates = []
        for other in self._screens:
            if other == rect:
                continue
            if other.bottom <= rect.top or other.top >= rect.bottom:
                continue  # no vertical overlap; not walkable
            if direction > 0 and other.left >= rect.right - 1:
                candidates.append(other)
            elif direction < 0 and other.right <= rect.left + 1:
                candidates.append(other)
        if not candidates:
            return None
        # The nearest one wins, so Glitch steps onto the neighbour, not past it.
        return min(candidates, key=lambda r: abs(r.center_x - rect.center_x))

    def random_destination(
        self, x: float, y: float, width: int, chooser: Callable[[int, int], int]
    ) -> float:
        """Pick an x-coordinate on the screen currently under the pet."""
        rect = self.screen_at(x + width / 2, y)
        return float(chooser(rect.left, max(rect.left, rect.right - width)))
