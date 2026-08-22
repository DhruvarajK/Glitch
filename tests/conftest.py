"""Shared fixtures. Qt tests run offscreen so the suite needs no display."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qt_gui_app():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    return app


@pytest.fixture()
def registry(qt_gui_app):
    from core.animation.registry import AnimationRegistry

    return AnimationRegistry(target_height=64)
