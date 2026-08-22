"""The transparent, frameless window Glitch is drawn in.

This window renders and forwards input. It holds no behavioural logic: where
Glitch is and what it is doing are decided by the pet engine.
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QWidget

from core.utils.logger import get_logger

log = get_logger("window")

# Pixels below which a pixel counts as transparent for hit-testing.
_ALPHA_HIT_THRESHOLD = 12


class PetWindow(QWidget):
    """Frameless translucent sprite surface."""

    def __init__(self, always_on_top: bool = True) -> None:
        super().__init__(None)
        self._pixmap: QPixmap | None = None
        self._always_on_top = always_on_top
        self._click_through = False

        # Callbacks wired by the interaction layer.
        self.on_press: Callable[[QPoint], None] | None = None
        self.on_move: Callable[[QPoint], None] | None = None
        self.on_release: Callable[[QPoint], None] | None = None
        self.on_double_click: Callable[[QPoint], None] | None = None
        self.on_context_menu: Callable[[QPoint], None] | None = None

        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_AlwaysStackOnTop, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setCursor(Qt.OpenHandCursor)
        self._apply_flags()

    # ---------------------------------------------------------------- flags
    def _apply_flags(self) -> None:
        flags = (
            Qt.FramelessWindowHint
            | Qt.Tool  # keeps Glitch out of the taskbar and alt-tab
            | Qt.NoDropShadowWindowHint
            | Qt.WindowDoesNotAcceptFocus
        )
        if self._always_on_top:
            flags |= Qt.WindowStaysOnTopHint
        if self._click_through:
            flags |= Qt.WindowTransparentForInput
        was_visible = self.isVisible()
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, self._click_through)
        if was_visible:
            self.show()

    def set_always_on_top(self, enabled: bool) -> None:
        if enabled == self._always_on_top:
            return
        self._always_on_top = bool(enabled)
        self._apply_flags()

    def set_click_through(self, enabled: bool) -> None:
        if enabled == self._click_through:
            return
        self._click_through = bool(enabled)
        self._apply_flags()

    @property
    def click_through(self) -> bool:
        return self._click_through

    # --------------------------------------------------------------- render
    def render_frame(self, pixmap: QPixmap, x: float, y: float) -> None:
        """Update sprite and position in one step, repainting only if needed."""
        moved = self.x() != int(x) or self.y() != int(y)
        resized = self._pixmap is None or self._pixmap.size() != pixmap.size()
        changed = self._pixmap is not pixmap

        self._pixmap = pixmap
        if resized:
            self.resize(pixmap.size())
        if moved:
            self.move(int(x), int(y))
        if changed or resized:
            self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if self._pixmap is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.drawPixmap(0, 0, self._pixmap)

    # ---------------------------------------------------------- hit testing
    def _is_opaque_at(self, pos: QPoint) -> bool:
        """Clicks landing on transparent pixels should not grab the pet."""
        if self._pixmap is None:
            return False
        if not self._pixmap.rect().contains(pos):
            return False
        image = self._pixmap.toImage()
        return image.pixelColor(pos).alpha() >= _ALPHA_HIT_THRESHOLD

    # ---------------------------------------------------------------- input
    def mousePressEvent(self, event) -> None:  # noqa: N802
        pos = event.position().toPoint()
        if not self._is_opaque_at(pos):
            event.ignore()
            return
        if event.button() == Qt.RightButton:
            if self.on_context_menu:
                self.on_context_menu(event.globalPosition().toPoint())
            event.accept()
            return
        if event.button() == Qt.LeftButton:
            self.setCursor(Qt.ClosedHandCursor)
            if self.on_press:
                self.on_press(event.globalPosition().toPoint())
            event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self.on_move:
            self.on_move(event.globalPosition().toPoint())
        event.accept()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.setCursor(Qt.OpenHandCursor)
            if self.on_release:
                self.on_release(event.globalPosition().toPoint())
            event.accept()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        pos = event.position().toPoint()
        if event.button() == Qt.LeftButton and self._is_opaque_at(pos):
            if self.on_double_click:
                self.on_double_click(event.globalPosition().toPoint())
            event.accept()
