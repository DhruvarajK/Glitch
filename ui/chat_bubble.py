"""The speech bubble Glitch talks through.

It tracks the pet, resizes to its content, flips below the pet when there is no
room above, and never intercepts mouse events so the pet stays draggable.
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

# Bubble geometry, in logical pixels.
MAX_WIDTH = 320
MIN_WIDTH = 70
PADDING_X = 14
PADDING_Y = 11
RADIUS = 12
TAIL_WIDTH = 18
TAIL_HEIGHT = 10
GAP = 6  # space between the bubble tail and the sprite

# Palette, picked to sit with the sprite's cyan without competing with it.
BACKGROUND = QColor(18, 22, 31, 242)
BORDER = QColor(53, 224, 232, 210)
TEXT_COLOR = QColor(234, 246, 255)

# Reading time: a base plus a per-character allowance, clamped.
BASE_VISIBLE_MS = 2200
MS_PER_CHARACTER = 48
MAX_VISIBLE_MS = 14000


class ChatBubble(QWidget):
    """A self-sizing, self-dismissing speech bubble."""

    def __init__(self) -> None:
        super().__init__(None)
        self._text = ""
        self._tail_below = False  # True when the bubble sits under the pet
        self._tail_x = 0.0

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.Tool
            | Qt.WindowStaysOnTopHint
            | Qt.NoDropShadowWindowHint
            | Qt.WindowDoesNotAcceptFocus
            | Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        font = QFont()
        font.setPointSizeF(9.5)
        self.setFont(font)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.dismiss)

    # ----------------------------------------------------------------- text
    def show_text(self, text: str, *, sticky: bool = False) -> None:
        """Display `text`. Sticky bubbles stay until told otherwise."""
        text = (text or "").strip()
        if not text:
            self.dismiss()
            return
        self._text = text
        self._resize_to_text()
        if not self.isVisible():
            self.show()
        self.update()

        self._hide_timer.stop()
        if not sticky:
            duration = min(
                MAX_VISIBLE_MS, BASE_VISIBLE_MS + len(text) * MS_PER_CHARACTER
            )
            self._hide_timer.start(duration)

    def hold(self, text: str) -> None:
        """Show text that stays put, used while a reply is still streaming."""
        self.show_text(text, sticky=True)

    def release(self) -> None:
        """Let a sticky bubble start its dismissal countdown."""
        if self.isVisible() and self._text:
            self.show_text(self._text)

    def dismiss(self) -> None:
        self._hide_timer.stop()
        self._text = ""
        self.hide()

    @property
    def text(self) -> str:
        return self._text

    # ------------------------------------------------------------- geometry
    def _text_rect(self) -> QRectF:
        metrics = QFontMetrics(self.font())
        available = MAX_WIDTH - PADDING_X * 2
        bounds = metrics.boundingRect(
            0, 0, available, 10_000, Qt.TextWordWrap, self._text
        )
        width = max(MIN_WIDTH - PADDING_X * 2, bounds.width())
        return QRectF(0, 0, width, bounds.height())

    def _resize_to_text(self) -> None:
        rect = self._text_rect()
        self.resize(
            int(rect.width()) + PADDING_X * 2,
            int(rect.height()) + PADDING_Y * 2 + TAIL_HEIGHT,
        )

    def follow(self, pet_x: float, pet_y: float, pet_width: int, pet_height: int,
               screen_left: float, screen_right: float,
               screen_top: float, screen_bottom: float) -> None:
        """Place the bubble relative to the pet, kept inside the given screen."""
        if not self.isVisible():
            return

        pet_center = pet_x + pet_width / 2
        x = pet_center - self.width() / 2
        y = pet_y - self.height() + TAIL_HEIGHT - GAP
        self._tail_below = False

        if y < screen_top:
            # No room above: sit below the pet and flip the tail.
            y = pet_y + pet_height + GAP
            self._tail_below = True
        y = min(y, screen_bottom - self.height())

        x = max(screen_left, min(x, screen_right - self.width()))

        # The tail keeps pointing at the pet even when the body was pushed aside.
        tail_x = pet_center - x
        self._tail_x = max(RADIUS + TAIL_WIDTH, min(tail_x, self.width() - RADIUS - TAIL_WIDTH))

        self.move(QPoint(int(x), int(y)))
        self.update()

    # --------------------------------------------------------------- render
    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if not self._text:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        body_top = TAIL_HEIGHT if self._tail_below else 0
        body_height = self.height() - TAIL_HEIGHT
        body = QRectF(0.5, body_top + 0.5, self.width() - 1.0, body_height - 1.0)

        path = QPainterPath()
        path.addRoundedRect(body, RADIUS, RADIUS)

        tail = QPainterPath()
        if self._tail_below:
            tail.moveTo(self._tail_x - TAIL_WIDTH / 2, body.top())
            tail.lineTo(self._tail_x, body.top() - TAIL_HEIGHT)
            tail.lineTo(self._tail_x + TAIL_WIDTH / 2, body.top())
        else:
            tail.moveTo(self._tail_x - TAIL_WIDTH / 2, body.bottom())
            tail.lineTo(self._tail_x, body.bottom() + TAIL_HEIGHT)
            tail.lineTo(self._tail_x + TAIL_WIDTH / 2, body.bottom())
        tail.closeSubpath()
        path = path.united(tail)

        painter.setPen(QPen(BORDER, 1.2))
        painter.setBrush(BACKGROUND)
        painter.drawPath(path)

        painter.setPen(TEXT_COLOR)
        text_area = body.adjusted(PADDING_X, PADDING_Y, -PADDING_X, -PADDING_Y)
        painter.drawText(text_area, Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignVCenter, self._text)
