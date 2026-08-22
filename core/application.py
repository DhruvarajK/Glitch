"""Wires every subsystem together and owns the runtime loop."""
from __future__ import annotations

import json
import random

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication

from core.ai.brain import AIBrain
from core.ai.conversation import ConversationManager
from core.ai.memory import MemoryManager
from core.ai.models import AIResponse
from core.ai.prompts import OFFLINE_REPLIES, PromptContext
from core.animation.registry import AnimationRegistry
from core.events.bus import EventBus
from core.events.events import EventType
from core.persistence.config import ConfigManager
from core.persistence.database import Database
from core.pet.controller import PetController
from core.pet.state import PetState
from core.screen.manager import ScreenManager
from core.utils.constants import APP_NAME, BASE_PET_HEIGHT, DATA_DIR
from core.utils.logger import get_logger
from core.utils.sounds import SoundPlayer
from core.utils.timers import Clock
from ui.chat_bubble import ChatBubble
from ui.pet_window import PetWindow
from ui.settings_window import SettingsWindow
from ui.tray import TrayController
from ui.widgets.chat_input import ChatInput

log = get_logger("app")

# ~30 Hz. Animations top out at 16 fps, so a faster tick would only burn
# wakeups without changing what the user sees.
TICK_INTERVAL_MS = 33
PERSIST_INTERVAL_MS = 60_000


class GlitchApplication:
    """Owns the object graph and the tick that drives it."""

    def __init__(self, qt_app: QApplication, config: ConfigManager | None = None) -> None:
        self.qt_app = qt_app
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        self.config = config or ConfigManager()
        self.bus = EventBus()
        self.screens = ScreenManager()
        self.database = Database()

        scale = float(self.config.get("pet_scale", 1.0))
        self.registry = AnimationRegistry(target_height=int(BASE_PET_HEIGHT * scale))
        self.registry.preload(["idle", "walk"])

        self.pet = PetController(self.config, self.registry, self.screens, self.bus)

        self.memory = MemoryManager(self.database)
        self.sounds = SoundPlayer(self.config)
        self.conversation = ConversationManager(self.config, self.database)
        self.brain = AIBrain(self.config, self.conversation, self.database)
        self._active_request: str | None = None
        self._connect_brain()

        self.window = PetWindow(always_on_top=bool(self.config.get("always_on_top")))
        self.window.set_click_through(bool(self.config.get("click_through")))
        self.bubble = ChatBubble()
        self.chat_input = ChatInput(self.send_message)
        self.settings_window: SettingsWindow | None = None
        self._connect_window()

        self.tray = TrayController(self.config)
        self.tray.on_exit = self.shutdown
        self.tray.on_toggle_visibility = self.set_pet_visible
        self.tray.on_pause_movement = self.pet.pause_movement
        self.tray.on_wake = self.pet.wake
        self.tray.on_chat = self.open_chat
        self.tray.on_settings = self.open_settings

        self.bus.subscribe(
            EventType.PET_WENT_TO_SLEEP,
            lambda e: (self.tray.set_pet_asleep(True), self.sounds.play("sleep")),
        )
        self.bus.subscribe(
            EventType.PET_WOKE_UP,
            lambda e: (self.tray.set_pet_asleep(False), self.sounds.play("wake")),
        )
        self.bus.subscribe(EventType.USER_CLICKED, lambda e: self.sounds.play("click"))
        self.bus.subscribe(EventType.USER_DRAG_STARTED, lambda e: self.sounds.play("drag"))
        self.bus.subscribe(EventType.USER_DRAG_ENDED, lambda e: self.sounds.play("drop"))
        self.config.on_change(self._on_config_changed)

        self._clock = Clock()
        self._timer = QTimer()
        self._timer.setTimerType(Qt.PreciseTimer)
        self._timer.timeout.connect(self._tick)
        self._persist_timer = QTimer()
        self._persist_timer.timeout.connect(self._persist_state)

    # ------------------------------------------------------------ lifecycle
    def start(self) -> None:
        self._restore_emotion()
        self.pet.enter_state(PetState.WAKING, force=True)
        self.window.render_frame(
            self.pet.animation.current_pixmap(), self.pet.x, self.pet.y
        )
        self.window.show()
        self.tray.show()
        self._clock.reset()
        self._timer.start(TICK_INTERVAL_MS)
        self._persist_timer.start(PERSIST_INTERVAL_MS)
        QTimer.singleShot(1500, self._first_launch)
        log.info("%s started", APP_NAME)

    def _first_launch(self) -> None:
        """Introduce Glitch once, then never again."""
        if self.config.get("onboarded"):
            return
        self.config.set("onboarded", True)
        self.pet.react("happy")
        self.bubble.show_text(
            "Hi, I'm Glitch. Double-click me to talk. "
            "Add an API key in Settings if you want me to answer."
        )
        self.tray.notify(
            APP_NAME, "Glitch is running. Right-click the tray icon for settings."
        )

    def shutdown(self) -> None:
        log.info("Shutting down")
        self._timer.stop()
        self._persist_timer.stop()
        self.bus.emit(EventType.APP_SHUTDOWN)
        self.brain.shutdown()
        self._persist_state()
        self.pet.remember_position()
        self.config.save()
        self.database.close()
        self.tray.hide()
        self.bubble.close()
        self.chat_input.close()
        if self.settings_window is not None:
            self.settings_window.close()
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
            self.bubble.dismiss()
            self._timer.stop()  # nothing to animate while hidden
        self.tray.set_pet_visible(visible)

    # ----------------------------------------------------------------- tick
    def _tick(self) -> None:
        dt = self._clock.tick()
        self.pet.update(dt)
        self.window.render_frame(
            self.pet.animation.current_pixmap(), self.pet.x, self.pet.y
        )
        if self.bubble.isVisible():
            screen = self.screens.screen_at(
                self.pet.x + self.pet.width / 2, self.pet.y + self.pet.height / 2
            )
            self.bubble.follow(
                self.pet.x,
                self.pet.y,
                self.pet.width,
                self.pet.height,
                screen.left,
                screen.right,
                screen.top,
                screen.bottom,
            )

    # ----------------------------------------------------------- persistence
    def _persist_state(self) -> None:
        if self.database.available:
            self.database.save_emotion(json.dumps(self.pet.emotion.state.as_dict()))

    def _restore_emotion(self) -> None:
        if not self.database.available:
            return
        raw = self.database.load_emotion()
        if not raw:
            return
        try:
            for name, value in json.loads(raw).items():
                self.pet.emotion.set_trait(name, float(value))
            log.info("Restored emotional state")
        except (ValueError, TypeError, AttributeError):
            log.warning("Stored emotional state was unreadable; starting fresh")

    # ------------------------------------------------------------------ chat
    def open_chat(self) -> None:
        if self.pet.state is PetState.SLEEPING:
            self.pet.wake()
        screen = self.screens.screen_at(self.pet.x + self.pet.width / 2, self.pet.y)
        self.chat_input.open_near(
            int(self.pet.x + self.pet.width / 2),
            int(min(self.pet.y + self.pet.height + 8, screen.bottom - 48)),
            int(screen.left),
            int(screen.right),
        )

    def send_message(self, text: str) -> None:
        self.bus.emit(EventType.USER_MESSAGE, message=text)
        self.pet.emotion.apply("talked_to")

        # "Remember that ..." is handled locally: explicit, instant, no API call.
        acknowledgement = self.memory.capture(text)
        if acknowledgement is not None:
            self.conversation.add_user_message(text)
            self.conversation.add_assistant_message(acknowledgement)
            self.bubble.show_text(acknowledgement)
            self.pet.react("happy")
            return

        if not self.brain.available:
            self.bubble.show_text(random.choice(OFFLINE_REPLIES))
            self.pet.react("confused")
            return

        context = PromptContext(
            state=self.pet.state.value,
            emotion=self.pet.emotion.state,
            mood=self.pet.emotion.mood(),
            last_interaction="sent you a message",
            memories=self.memory.recall(),
        )
        self._active_request = self.brain.ask(text, context)

    def _connect_brain(self) -> None:
        self.brain.request_started.connect(self._on_ai_started)
        self.brain.token_received.connect(self._on_ai_token)
        self.brain.response_received.connect(self._on_ai_response)
        self.brain.request_failed.connect(self._on_ai_failed)
        self.brain.request_cancelled.connect(
            lambda request_id: self.bus.emit(
                EventType.AI_REQUEST_CANCELLED, id=request_id
            )
        )

    def _is_current(self, request_id: str) -> bool:
        """Ignore anything arriving from a request that has been superseded."""
        return self._active_request is None or request_id == self._active_request

    def _on_ai_started(self, request_id: str) -> None:
        self._active_request = request_id
        self.bus.emit(EventType.AI_REQUEST_STARTED, id=request_id)
        self.pet.enter_state(PetState.THINKING, force=True)

    def _on_ai_token(self, request_id: str, text: str) -> None:
        if not self._is_current(request_id):
            return
        if self.pet.state is not PetState.TALKING:
            self.pet.enter_state(PetState.TALKING, force=True)
        self.bubble.hold(text)
        self.bus.emit(EventType.AI_TOKEN_RECEIVED, id=request_id)

    def _on_ai_response(self, request_id: str, response: AIResponse) -> None:
        if not self._is_current(request_id):
            return
        self._active_request = None
        self.bubble.show_text(response.message)
        self.pet.emotion.adjust(response.emotion_deltas())
        if response.action == "sleep":
            self.pet.sleep()
        else:
            self.pet.react(response.animation())
        self.bus.emit(
            EventType.AI_RESPONSE_RECEIVED, id=request_id, emotion=response.emotion
        )

    def _on_ai_failed(self, request_id: str, kind: str, message: str) -> None:
        if not self._is_current(request_id):
            return
        self._active_request = None
        self.bubble.show_text(message)
        self.pet.react("confused")
        self.bus.emit(EventType.AI_REQUEST_FAILED, id=request_id, kind=kind)

    # -------------------------------------------------------------- settings
    def open_settings(self) -> None:
        if self.settings_window is None:
            self.settings_window = SettingsWindow(
                self.config,
                self.database,
                on_clear_memory=self._clear_memory,
            )
        self.settings_window.show()
        self.settings_window.raise_()
        self.settings_window.activateWindow()

    def _clear_memory(self) -> None:
        self.conversation.clear()
        self.memory.clear()

    # ----------------------------------------------------------- connections
    def _connect_window(self) -> None:
        self.window.on_press = lambda pos: self.pet.begin_drag(pos.x(), pos.y())
        self.window.on_move = lambda pos: self.pet.drag_to(pos.x(), pos.y())
        self.window.on_release = self._on_release
        self.window.on_double_click = self._on_double_click
        self.window.on_context_menu = lambda pos: self.tray.menu.popup(pos)

    def _on_release(self, pos) -> None:
        # A press that never moved is a click; the interaction layer decides
        # how Glitch feels about it.
        if not self.pet.end_drag():
            self.bus.emit(EventType.USER_CLICKED)

    def _on_double_click(self, pos) -> None:
        self.bus.emit(EventType.USER_DOUBLE_CLICKED)
        self.open_chat()

    def _on_config_changed(self, key: str, value: object) -> None:
        if key == "always_on_top":
            self.window.set_always_on_top(bool(value))
        elif key == "click_through":
            self.window.set_click_through(bool(value))
        elif key == "ai_enabled" and not value:
            self.brain.cancel()
        elif key == "sounds_enabled":
            self.sounds.set_enabled(bool(value))
        elif key == "sound_volume":
            self.sounds.set_volume(float(value))
        self.bus.emit(EventType.CONFIG_CHANGED, key=key, value=value)
