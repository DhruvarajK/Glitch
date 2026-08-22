"""Wires every subsystem together and owns the runtime loop."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication

from core.animation.registry import AnimationRegistry
from core.events.bus import EventBus
from core.events.events import EventType
from core.pet.controller import PetController
from core.pet.state import PetState
from core.persistence.config import ConfigManager
from core.screen.manager import ScreenManager
from core.utils.constants import APP_NAME, BASE_PET_HEIGHT, DATA_DIR
from core.utils.logger import get_logger
from core.utils.timers import Clock
from ui.pet_window import PetWindow
from ui.tray import TrayController

log = get_logger("app")

TICK_INTERVAL_MS = 16  # ~60 Hz; animation and movement share one timer


class GlitchApplication:
    """Owns the object graph and the tick that drives it."""

    def __init__(self, qt_app: QApplication, config: ConfigManager | None = None) -> None:
        self.qt_app = qt_app
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        self.config = config or ConfigManager()
        self.bus = EventBus()
        self.screens = ScreenManager()

        scale = float(self.config.get("pet_scale", 1.0))
        self.registry = AnimationRegistry(target_height=int(BASE_PET_HEIGHT * scale))
        self.registry.preload(["idle", "walk"])

        self.pet = PetController(self.config, self.registry, self.screens, self.bus)

        self.window = PetWindow(always_on_top=bool(self.config.get("always_on_top")))
        self.window.set_click_through(bool(self.config.get("click_through")))
        self._connect_window()

        self.tray = TrayController(self.config)
        self.tray.on_exit = self.shutdown
        self.tray.on_toggle_visibility = self.set_pet_visible
        self.tray.on_pause_movement = self.pet.pause_movement
        self.tray.on_wake = self.pet.wake

        self.bus.subscribe(
            EventType.PET_WENT_TO_SLEEP, lambda e: self.tray.set_pet_asleep(True)
        )
        self.bus.subscribe(
            EventType.PET_WOKE_UP, lambda e: self.tray.set_pet_asleep(False)
        )
        self.config.on_change(self._on_config_changed)

        self._clock = Clock()
        self._timer = QTimer()
        self._timer.setTimerType(Qt.PreciseTimer)
        self._timer.timeout.connect(self._tick)

    # ------------------------------------------------------------ lifecycle
    def start(self) -> None:
        self.pet.enter_state(PetState.WAKING, force=True)
        self.window.render_frame(
            self.pet.animation.current_pixmap(), self.pet.x, self.pet.y
        )
        self.window.show()
        self.tray.show()
        self._clock.reset()
        self._timer.start(TICK_INTERVAL_MS)
        log.info("%s started", APP_NAME)

    def shutdown(self) -> None:
        log.info("Shutting down")
        self._timer.stop()
        self.bus.emit(EventType.APP_SHUTDOWN)
        self.pet.remember_position()
        self.config.save()
        self.tray.hide()
        self.window.close()
        self.qt_app.quit()

    def set_pet_visible(self, visible: bool) -> None:
        if visible:
            self.window.show()
            self._clock.reset()
            if not self._timer.isActive():
                self._timer.start(TICK_INTERVAL_MS)
        else:
            self.window.hide()
            self._timer.stop()  # nothing to animate while hidden
        self.tray.set_pet_visible(visible)

    # ----------------------------------------------------------------- tick
    def _tick(self) -> None:
        dt = self._clock.tick()
        self.pet.update(dt)
        self.window.render_frame(
            self.pet.animation.current_pixmap(), self.pet.x, self.pet.y
        )

    # ----------------------------------------------------------- connections
    def _connect_window(self) -> None:
        self.window.on_press = lambda pos: self.pet.begin_drag(pos.x(), pos.y())
        self.window.on_move = lambda pos: self.pet.drag_to(pos.x(), pos.y())
        self.window.on_release = self._on_release
        self.window.on_double_click = lambda pos: self.bus.emit(
            EventType.USER_DOUBLE_CLICKED
        )
        self.window.on_context_menu = lambda pos: self.tray.menu.popup(pos)

    def _on_release(self, pos) -> None:
        # A press that never moved is a click; the interaction layer decides
        # how Glitch feels about it.
        if not self.pet.end_drag():
            self.bus.emit(EventType.USER_CLICKED)

    def _on_config_changed(self, key: str, value: object) -> None:
        if key == "always_on_top":
            self.window.set_always_on_top(bool(value))
        elif key == "click_through":
            self.window.set_click_through(bool(value))
        self.bus.emit(EventType.CONFIG_CHANGED, key=key, value=value)
