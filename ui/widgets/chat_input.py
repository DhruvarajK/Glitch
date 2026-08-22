"""The pill-shaped prompt used to talk to Glitch.

Enter sends. Shift+Enter starts a new line and the pill grows to fit, up to a
few lines, after which it scrolls. Escape or clicking away closes it.
"""
from __future__ import annotations

import math
from typing import Callable

from PySide6.QtCore import QEvent, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QAbstractButton,
    QHBoxLayout,
    QPlainTextEdit,
    QWidget,
)

from ui import theme

WIDTH = 340
SHADOW = 6
PADDING_X = 8
PADDING_Y = 7
BUTTON_SIZE = 30
MAX_LINES = 6


class SendButton(QAbstractButton):
    """A circular send button carrying a Phosphor-style arrow-up glyph."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(BUTTON_SIZE, BUTTON_SIZE)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setToolTip("Send")

    def sizeHint(self) -> QSize:  # noqa: N802 (Qt naming)
        return QSize(BUTTON_SIZE, BUTTON_SIZE)

    def paintEvent(self, event) -> None:  # noqa: N802
        palette = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        enabled = self.isEnabled()
        fill = palette.accent if enabled else palette.border
        if enabled and self.isDown():
            fill = fill.darker(115)
        elif enabled and self.underMouse():
            fill = fill.lighter(112)

        painter.setPen(Qt.NoPen)
        painter.setBrush(fill)
        painter.drawEllipse(self.rect().adjusted(0, 0, -1, -1))

        # Phosphor "arrow-up": a stem with a chevron head, rounded ends.
        centre_x = self.width() / 2
        centre_y = self.height() / 2
        reach = 6.0
        glyph = QPainterPath()
        glyph.moveTo(centre_x, centre_y + reach)
        glyph.lineTo(centre_x, centre_y - reach)
        glyph.moveTo(centre_x - 5.0, centre_y - reach + 5.0)
        glyph.lineTo(centre_x, centre_y - reach)
        glyph.lineTo(centre_x + 5.0, centre_y - reach + 5.0)

        colour = palette.on_accent if enabled else palette.muted
        pen = QPen(colour, 2.0)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(glyph)


class GrowingTextEdit(QPlainTextEdit):
    """A text area that reports the height its content needs."""

    submitted = Signal()
    dismissed = Signal()
    height_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameStyle(QPlainTextEdit.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.setTabChangesFocus(True)
        self.document().setDocumentMargin(0)
        self.setPlaceholderText("Say something to Glitch...")

        font = QFont()
        font.setPointSizeF(9.5)
        self.setFont(font)

        self.textChanged.connect(self.height_changed)

    def line_height(self) -> float:
        return self.fontMetrics().lineSpacing()

    def preferred_height(self) -> int:
        """Height for the current content, between one and MAX_LINES lines."""
        width = self.viewport().width()
        if width < 20:
            # Called before the first layout; estimate from the pill width.
            width = WIDTH - (SHADOW + PADDING_X) * 2 - BUTTON_SIZE - 14
        document = self.document()
        document.setTextWidth(width)
        lines = min(max(1.0, document.size().height()), float(MAX_LINES))
        return int(math.ceil(lines * self.line_height()) + 2)

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        key = event.key()
        if key == Qt.Key_Escape:
            self.dismissed.emit()
            event.accept()
            return
        if key in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() & Qt.ShiftModifier:
                super().keyPressEvent(event)  # Shift+Enter: new line, grow
                return
            self.submitted.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class ChatInput(QWidget):
    """Frameless pill containing the text area and the send button."""

    def __init__(self, on_submit: Callable[[str], None]) -> None:
        super().__init__(None)
        self._on_submit = on_submit
        self._screen_bounds = (0, 1920)
        self._anchor_bottom = 0

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedWidth(WIDTH)

        self.field = GrowingTextEdit(self)
        self.field.setStyleSheet("QPlainTextEdit { background: transparent; border: none; }")
        self.field.submitted.connect(self._submit)
        self.field.dismissed.connect(self.hide)
        self.field.height_changed.connect(self._reflow)

        self.send_button = SendButton(self)
        self.send_button.clicked.connect(self._submit)
        self.send_button.setEnabled(False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            SHADOW + PADDING_X + 6,
            SHADOW + PADDING_Y,
            SHADOW + PADDING_X,
            SHADOW + PADDING_Y,
        )
        layout.setSpacing(8)
        # One line sits centred against the button; longer text grows upward
        # from the button, which stays pinned to the bottom of the pill.
        layout.addWidget(self.field, 1, Qt.AlignVCenter)
        layout.addWidget(self.send_button, 0, Qt.AlignBottom)

        self._apply_colours()
        self._reflow()

    # ---------------------------------------------------------------- theme
    def _apply_colours(self) -> None:
        palette = theme.current()
        self.field.setStyleSheet(
            "QPlainTextEdit {"
            "  background: transparent;"
            "  border: none;"
            f" color: {palette.text.name()};"
            f" selection-background-color: rgba({palette.accent.red()},"
            f" {palette.accent.green()}, {palette.accent.blue()}, 110);"
            "}"
            "QScrollBar:vertical { width: 4px; background: transparent; }"
            "QScrollBar::handle:vertical {"
            f" background: {palette.border.name()}; border-radius: 2px;"
            "}"
            "QScrollBar::add-line, QScrollBar::sub-line { height: 0; }"
        )

    # ------------------------------------------------------------- geometry
    def _reflow(self) -> None:
        """Resize to the content, then keep the pill on screen."""
        has_text = bool(self.field.toPlainText().strip())
        self.send_button.setEnabled(has_text)

        text_height = self.field.preferred_height()
        self.field.setFixedHeight(text_height)
        total = max(text_height, BUTTON_SIZE) + (SHADOW + PADDING_Y) * 2
        if total != self.height():
            self.setFixedHeight(total)
            if self._anchor_bottom:
                # Grow upward so the pill stays clear of the screen edge.
                self.move(self.x(), self._anchor_bottom - total)
        self.update()

    def open_near(self, x: int, y: int, screen_left: int, screen_right: int) -> None:
        """Show the prompt near a point, kept on screen, with focus."""
        self._screen_bounds = (int(screen_left), int(screen_right))
        left = max(screen_left, min(int(x) - WIDTH // 2, screen_right - WIDTH))
        self._anchor_bottom = int(y) + self.height()
        self.move(left, int(y))
        self._apply_colours()
        self.show()
        self.raise_()
        self.activateWindow()
        self.field.setFocus(Qt.OtherFocusReason)

    # --------------------------------------------------------------- events
    def _submit(self) -> None:
        text = self.field.toPlainText().strip()
        self.field.clear()
        if text:
            self._on_submit(text)
        self.hide()

    def event(self, event) -> bool:
        # Clicking away dismisses the prompt rather than leaving it floating.
        if event.type() == QEvent.WindowDeactivate:
            self.hide()
        return super().event(event)

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().resizeEvent(event)
        self.update()

    # --------------------------------------------------------------- render
    def paintEvent(self, event) -> None:  # noqa: N802
        palette = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        body = QRectF(
            SHADOW + 0.5,
            SHADOW + 0.5,
            self.width() - SHADOW * 2 - 1,
            self.height() - SHADOW * 2 - 1,
        )
        # A pill while it is one line tall; softly rounded once it grows.
        radius = min(body.height() / 2, 20.0)

        painter.setBrush(Qt.NoBrush)
        for step in range(SHADOW, 0, -1):
            colour = palette.shadow
            colour.setAlpha(max(5, palette.shadow.alpha() // (step * 2)))
            painter.setPen(QPen(colour, step * 1.6))
            painter.drawRoundedRect(body, radius, radius)

        painter.setPen(QPen(palette.border, 1.1))
        painter.setBrush(palette.surface)
        painter.drawRoundedRect(body, radius, radius)
