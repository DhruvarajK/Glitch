"""System tray icon and menu.

The tray stays usable when Glitch is hidden, so it is the reliable way back to
the pet and to the exit command.
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from core.persistence.config import ConfigManager
from core.utils.constants import APP_NAME, ICONS_DIR
from core.utils.logger import get_logger

log = get_logger("tray")


class TrayController:
    """Builds the tray menu and reflects live configuration state."""

    def __init__(self, config: ConfigManager) -> None:
        self.config = config
        self.on_toggle_visibility: Callable[[bool], None] | None = None
        self.on_exit: Callable[[], None] | None = None

        icon_path = ICONS_DIR / "glitch.png"
        icon = QIcon(str(icon_path)) if icon_path.exists() else QIcon()
        self.tray = QSystemTrayIcon(icon)
        self.tray.setToolTip(APP_NAME)

        self.menu = QMenu()
        self._build_menu()
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._on_activated)

    # ----------------------------------------------------------------- menu
    def _build_menu(self) -> None:
        header = self.menu.addAction(APP_NAME)
        header.setEnabled(False)
        self.menu.addSeparator()

        self.action_show = QAction("Hide Glitch", self.menu)
        self.action_show.triggered.connect(self._toggle_visibility)
        self.menu.addAction(self.action_show)

        self.menu.addSeparator()

        self.action_on_top = QAction("Always on Top", self.menu, checkable=True)
        self.action_on_top.setChecked(bool(self.config.get("always_on_top")))
        self.action_on_top.toggled.connect(
            lambda checked: self.config.set("always_on_top", checked)
        )
        self.menu.addAction(self.action_on_top)

        self.action_click_through = QAction("Click Through", self.menu, checkable=True)
        self.action_click_through.setChecked(bool(self.config.get("click_through")))
        self.action_click_through.toggled.connect(
            lambda checked: self.config.set("click_through", checked)
        )
        self.menu.addAction(self.action_click_through)

        self.menu.addSeparator()

        action_exit = QAction("Exit", self.menu)
        action_exit.triggered.connect(lambda: self.on_exit and self.on_exit())
        self.menu.addAction(action_exit)

    # ------------------------------------------------------------- controls
    def show(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            log.warning("System tray unavailable; Glitch runs without a tray icon")
            return
        self.tray.show()

    def hide(self) -> None:
        self.tray.hide()

    def notify(self, title: str, message: str) -> None:
        if self.tray.isVisible():
            self.tray.showMessage(title, message, self.tray.icon(), 4000)

    def set_pet_visible(self, visible: bool) -> None:
        self.action_show.setText("Hide Glitch" if visible else "Show Glitch")

    def _toggle_visibility(self) -> None:
        if self.on_toggle_visibility:
            self.on_toggle_visibility(self.action_show.text().startswith("Show"))

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.Trigger and self.on_toggle_visibility:
            self.on_toggle_visibility(True)
