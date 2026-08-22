"""A small floating line-edit for talking to Glitch."""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLineEdit, QVBoxLayout, QWidget

STYLE = """
QWidget#chatInputPanel {
    background: rgba(18, 22, 31, 245);
    border: 1px solid rgba(53, 224, 232, 200);
    border-radius: 10px;
}
QLineEdit {
    background: transparent;
    border: none;
    color: #eaf6ff;
    selection-background-color: rgba(53, 224, 232, 120);
    padding: 6px 8px;
    font-size: 12px;
}
"""

WIDTH = 300


class ChatInput(QWidget):
    """Frameless prompt that closes on Escape and submits on Enter."""

    def __init__(self, on_submit: Callable[[str], None]) -> None:
        super().__init__(None)
        self._on_submit = on_submit

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setObjectName("chatInputPanel")
        self.setStyleSheet(STYLE)
        self.setFixedWidth(WIDTH)

        self.field = QLineEdit(self)
        self.field.setPlaceholderText("Say something to Glitch...")
        self.field.setMaxLength(500)
        self.field.returnPressed.connect(self._submit)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(self.field)

    def _submit(self) -> None:
        text = self.field.text().strip()
        self.field.clear()
        if text:
            self._on_submit(text)
        self.hide()

    def open_near(self, x: int, y: int, screen_left: int, screen_right: int) -> None:
        """Show the prompt near a point, kept on screen, with focus."""
        left = max(screen_left, min(int(x) - WIDTH // 2, screen_right - WIDTH))
        self.move(left, int(y))
        self.show()
        self.raise_()
        self.activateWindow()
        self.field.setFocus(Qt.OtherFocusReason)

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if event.key() == Qt.Key_Escape:
            self.hide()
            event.accept()
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, event) -> None:  # noqa: N802
        # Clicking away dismisses the prompt rather than leaving it floating.
        self.hide()
        super().focusOutEvent(event)
