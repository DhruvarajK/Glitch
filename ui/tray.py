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
        self.on_chat: Callable[[], None] | None = None
        self.on_settings: Callable[[], None] | None = None
        self.on_toggle_visibility: Callable[[bool], None] | None = None
        self.on_pause_movement: Callable[[bool], None] | None = None
        self.on_wake: Callable[[], None] | None = None
        self.on_react_now: Callable[[], None] | None = None
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

        action_chat = QAction("Chat", self.menu)
        action_chat.triggered.connect(lambda: self.on_chat and self.on_chat())
        self.menu.addAction(action_chat)

        action_react = QAction("React to What I'm Doing", self.menu)
        action_react.triggered.connect(
            lambda: self.on_react_now and self.on_react_now()
        )
        self.menu.addAction(action_react)

        self.action_pause = QAction("Pause Movement", self.menu, checkable=True)
        self.action_pause.toggled.connect(
            lambda checked: self.on_pause_movement and self.on_pause_movement(checked)
        )
        self.menu.addAction(self.action_pause)

        self.action_wake = QAction("Wake Up", self.menu)
        self.action_wake.triggered.connect(lambda: self.on_wake and self.on_wake())
        self.action_wake.setEnabled(False)
        self.menu.addAction(self.action_wake)

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

        action_settings = QAction("Settings...", self.menu)
        action_settings.triggered.connect(lambda: self.on_settings and self.on_settings())
        self.menu.addAction(action_settings)

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

    def set_pet_asleep(self, asleep: bool) -> None:
        self.action_wake.setEnabled(asleep)
        self.tray.setToolTip(f"{APP_NAME} - asleep" if asleep else APP_NAME)

    def set_pet_visible(self, visible: bool) -> None:
        self.action_show.setText("Hide Glitch" if visible else "Show Glitch")

    def _toggle_visibility(self) -> None:
        if self.on_toggle_visibility:
            self.on_toggle_visibility(self.action_show.text().startswith("Show"))

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.DoubleClick and self.on_chat:
            self.on_chat()
        elif reason == QSystemTrayIcon.Trigger and self.on_toggle_visibility:
            self.on_toggle_visibility(True)
