"""Shared colours for Glitch's own chrome.

The bubble and chat input are frameless translucent windows, so they paint
themselves rather than inheriting a widget style. This module keeps that
painting in one place and follows the system light/dark setting.
"""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QColor, QGuiApplication, QPalette


@dataclass(frozen=True)
class Theme:
    surface: QColor
    surface_raised: QColor
    border: QColor
    text: QColor
    muted: QColor
    accent: QColor
    on_accent: QColor
    shadow: QColor


# Cyan is taken from the sprite itself so the chrome reads as part of Glitch.
DARK = Theme(
    surface=QColor(20, 24, 33, 244),
    surface_raised=QColor(31, 37, 49, 255),
    border=QColor(60, 72, 92, 220),
    text=QColor(233, 240, 250),
    muted=QColor(132, 145, 163),
    accent=QColor(53, 224, 232),
    on_accent=QColor(8, 20, 26),
    shadow=QColor(0, 0, 0, 90),
)

LIGHT = Theme(
    surface=QColor(255, 255, 255, 246),
    surface_raised=QColor(243, 246, 250, 255),
    border=QColor(207, 214, 224, 235),
    text=QColor(18, 23, 31),
    muted=QColor(112, 122, 136),
    accent=QColor(10, 160, 176),
    on_accent=QColor(255, 255, 255),
    shadow=QColor(15, 23, 42, 45),
)


def is_dark() -> bool:
    """True when the system is using a dark colour scheme."""
    app = QGuiApplication.instance()
    if app is None:
        return True
    scheme = getattr(app.styleHints(), "colorScheme", None)
    if scheme is not None:
        from PySide6.QtCore import Qt

        value = scheme()
        if value == Qt.ColorScheme.Dark:
            return True
        if value == Qt.ColorScheme.Light:
            return False
    # Older Qt builds: fall back to how bright the window colour is.
    window = app.palette().color(QPalette.Window)
    return window.lightness() < 128


def current() -> Theme:
    return DARK if is_dark() else LIGHT
