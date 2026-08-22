"""The speech bubble Glitch talks through.

It tracks the pet, sizes itself to its content, flips below the pet when there
is no room above, and never intercepts mouse events so the pet stays
draggable.

Layout and painting share one QTextDocument. Measuring with font metrics and
then painting into a slightly different rectangle is what made earlier text
re-wrap and clip against the edges of the bubble.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer
from PySide6.QtGui import (
    QAbstractTextDocumentLayout,
    QFont,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QTextDocument,
    QTextOption,
)
from PySide6.QtWidgets import QWidget

from ui import theme

# Bubble geometry, in logical pixels.
MAX_TEXT_WIDTH = 300
MIN_TEXT_WIDTH = 54
PADDING_X = 15
PADDING_Y = 12
RADIUS = 15
TAIL_WIDTH = 17
TAIL_HEIGHT = 9
GAP = 4  # space between the bubble tail and the sprite
SHADOW = 5  # transparent margin reserved for the drop shadow

# Reading time: a base plus a per-character allowance, clamped.
BASE_VISIBLE_MS = 2400
MS_PER_CHARACTER = 48
MAX_VISIBLE_MS = 16000


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

        self._document = QTextDocument()
        self._document.setDocumentMargin(0)
        self._document.setDefaultFont(font)
        options = QTextOption()
        options.setWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self._document.setDefaultTextOption(options)

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
        self._layout_text()
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
    def _layout_text(self) -> None:
        """Lay the text out once and size the window around the result."""
        document = self._document
        document.setDefaultFont(self.font())
        document.setPlainText(self._text)

        # Wrap at the maximum first, then shrink to what the text actually
        # needed, so short lines get a snug bubble instead of a wide one.
        document.setTextWidth(MAX_TEXT_WIDTH)
        width = min(MAX_TEXT_WIDTH, max(MIN_TEXT_WIDTH, math.ceil(document.idealWidth())))
        document.setTextWidth(width)
        height = math.ceil(document.size().height())

        self.resize(
            width + PADDING_X * 2 + SHADOW * 2,
            height + PADDING_Y * 2 + TAIL_HEIGHT + SHADOW * 2,
        )

    def _body_rect(self) -> QRectF:
        """The rounded panel, excluding the tail and the shadow margin."""
        top = SHADOW + (TAIL_HEIGHT if self._tail_below else 0)
        height = self.height() - TAIL_HEIGHT - SHADOW * 2
        return QRectF(SHADOW, top, self.width() - SHADOW * 2, height)

    def follow(
        self,
        pet_x: float,
        pet_y: float,
        pet_width: int,
        pet_height: int,
        screen_left: float,
        screen_right: float,
        screen_top: float,
        screen_bottom: float,
    ) -> None:
        """Place the bubble relative to the pet, kept inside the given screen."""
        if not self.isVisible():
            return

        pet_center = pet_x + pet_width / 2
        x = pet_center - self.width() / 2
        y = pet_y - self.height() + TAIL_HEIGHT + SHADOW - GAP
        self._tail_below = False

        if y < screen_top:
            # No room above: sit below the pet and flip the tail.
            y = pet_y + pet_height + GAP - SHADOW
            self._tail_below = True
        y = min(y, screen_bottom - self.height())

        x = max(screen_left, min(x, screen_right - self.width()))

        # The tail keeps pointing at the pet even when the body was pushed aside.
        limit_low = SHADOW + RADIUS + TAIL_WIDTH
        limit_high = self.width() - SHADOW - RADIUS - TAIL_WIDTH
        tail_x = pet_center - x
        self._tail_x = max(limit_low, min(tail_x, max(limit_low, limit_high)))

        self.move(QPoint(int(x), int(y)))
        self.update()

    # --------------------------------------------------------------- render
    def _shape(self) -> QPainterPath:
        body = self._body_rect()
        path = QPainterPath()
        path.addRoundedRect(body.adjusted(0.5, 0.5, -0.5, -0.5), RADIUS, RADIUS)

        tail = QPainterPath()
        half = TAIL_WIDTH / 2
        if self._tail_below:
            tail.moveTo(self._tail_x - half, body.top() + 1)
            tail.lineTo(self._tail_x, body.top() - TAIL_HEIGHT)
            tail.lineTo(self._tail_x + half, body.top() + 1)
        else:
            tail.moveTo(self._tail_x - half, body.bottom() - 1)
            tail.lineTo(self._tail_x, body.bottom() + TAIL_HEIGHT)
            tail.lineTo(self._tail_x + half, body.bottom() - 1)
        tail.closeSubpath()
        return path.united(tail)

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if not self._text:
            return
        palette = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        shape = self._shape()

        # A soft shadow, drawn as a few fading outlines rather than a blur.
        painter.setBrush(Qt.NoBrush)
        for step in range(SHADOW, 0, -1):
            colour = palette.shadow
            colour.setAlpha(max(6, palette.shadow.alpha() // (step * 2)))
            painter.setPen(QPen(colour, step * 1.6))
            painter.drawPath(shape)

        painter.setPen(QPen(palette.border, 1.1))
        painter.setBrush(palette.surface)
        painter.drawPath(shape)

        # Painting the same document that was measured keeps the text inside.
        body = self._body_rect()
        painter.save()
        painter.translate(body.left() + PADDING_X, body.top() + PADDING_Y)
        context = QAbstractTextDocumentLayout.PaintContext()
        context.palette.setColor(QPalette.Text, palette.text)
        self._document.documentLayout().draw(painter, context)
        painter.restore()
