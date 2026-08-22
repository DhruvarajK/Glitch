"""Settings dialog.

Changes are written straight to the config manager, which notifies the running
pet: sliders and toggles take effect immediately rather than on close.
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.ai.prompts import PERSONALITIES
from core.persistence import credentials
from core.persistence.config import ConfigManager
from core.persistence.database import Database
from core.utils.constants import APP_NAME
from core.utils.logger import get_logger

log = get_logger("settings")

MODELS = ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1"]


def _slider(minimum: int, maximum: int, value: int) -> QSlider:
    slider = QSlider(Qt.Horizontal)
    slider.setRange(minimum, maximum)
    slider.setValue(value)
    return slider


class SettingsWindow(QDialog):
    """Tabbed preferences for the pet, its brain and its behaviour."""

    def __init__(
        self,
        config: ConfigManager,
        database: Database | None = None,
        on_clear_memory: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(None)
        self.config = config
        self.db = database
        self.on_clear_memory = on_clear_memory

        self.setWindowTitle(f"{APP_NAME} Settings")
        self.setMinimumWidth(420)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)

        tabs = QTabWidget(self)
        tabs.addTab(self._general_tab(), "General")
        tabs.addTab(self._ai_tab(), "AI")
        tabs.addTab(self._behaviour_tab(), "Behaviour")
        tabs.addTab(self._appearance_tab(), "Appearance")
        tabs.addTab(self._advanced_tab(), "Advanced")

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(close_button)

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addLayout(buttons)

    # ------------------------------------------------------------------ tabs
    def _general_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)

        speed = QSpinBox()
        speed.setRange(10, 400)
        speed.setSuffix(" px/s")
        speed.setValue(int(self.config.get("movement_speed", 80)))
        speed.valueChanged.connect(lambda v: self.config.set("movement_speed", float(v)))
        form.addRow("Movement speed", speed)

        for key, label in (
            ("always_on_top", "Always on top"),
            ("click_through", "Click through"),
            ("start_with_windows", "Start with Windows"),
        ):
            box = QCheckBox()
            box.setChecked(bool(self.config.get(key)))
            box.toggled.connect(lambda checked, k=key: self._set_toggle(k, checked))
            form.addRow(label, box)
        return page

    def _ai_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)

        enabled = QCheckBox()
        enabled.setChecked(bool(self.config.get("ai_enabled", True)))
        enabled.toggled.connect(lambda v: self.config.set("ai_enabled", v))
        form.addRow("Enable AI", enabled)

        self.key_field = QLineEdit()
        self.key_field.setEchoMode(QLineEdit.Password)
        self.key_field.setPlaceholderText(
            credentials.masked_api_key() or "sk-..."
        )
        save_key = QPushButton("Save")
        save_key.clicked.connect(self._save_api_key)
        clear_key = QPushButton("Clear")
        clear_key.clicked.connect(self._clear_api_key)

        key_row = QHBoxLayout()
        key_row.addWidget(self.key_field, 1)
        key_row.addWidget(save_key)
        key_row.addWidget(clear_key)
        form.addRow("API key", key_row)

        self.key_status = QLabel(self._key_status_text())
        self.key_status.setStyleSheet("color: #888;")
        form.addRow("", self.key_status)

        model = QComboBox()
        model.setEditable(True)
        model.addItems(MODELS)
        model.setCurrentText(str(self.config.get("ai_model", "gpt-4o-mini")))
        model.currentTextChanged.connect(lambda v: self.config.set("ai_model", v.strip()))
        form.addRow("Model", model)

        temperature = QDoubleSpinBox()
        temperature.setRange(0.0, 2.0)
        temperature.setSingleStep(0.1)
        temperature.setValue(float(self.config.get("ai_temperature", 0.8)))
        temperature.valueChanged.connect(lambda v: self.config.set("ai_temperature", v))
        form.addRow("Temperature", temperature)

        memory = QSpinBox()
        memory.setRange(2, 100)
        memory.setSuffix(" messages")
        memory.setValue(int(self.config.get("conversation_memory", 20)))
        memory.valueChanged.connect(lambda v: self.config.set("conversation_memory", v))
        form.addRow("Conversation memory", memory)

        personality = QComboBox()
        for key, value in PERSONALITIES.items():
            personality.addItem(key.replace("_", " ").title(), key)
        current = str(self.config.get("personality", "default"))
        index = personality.findData(current)
        personality.setCurrentIndex(max(0, index))
        personality.currentIndexChanged.connect(
            lambda i: self.config.set("personality", personality.itemData(i))
        )
        form.addRow("Personality", personality)

        if self.db is not None and self.db.available:
            totals = self.db.usage_totals()
            usage = QLabel(
                f"{totals['requests']} requests - "
                f"{totals['input_tokens']} in / {totals['output_tokens']} out tokens"
            )
            usage.setStyleSheet("color: #888;")
            form.addRow("Usage", usage)
        return page

    def _behaviour_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)

        autonomous = QCheckBox()
        autonomous.setChecked(bool(self.config.get("autonomous_movement", True)))
        autonomous.toggled.connect(lambda v: self.config.set("autonomous_movement", v))
        form.addRow("Autonomous movement", autonomous)

        frequency = _slider(0, 30, int(float(self.config.get("reaction_frequency", 1.0)) * 10))
        frequency.valueChanged.connect(
            lambda v: self.config.set("reaction_frequency", v / 10.0)
        )
        form.addRow("Reaction frequency", frequency)

        sleep_enabled = QCheckBox()
        sleep_enabled.setChecked(bool(self.config.get("sleep_enabled", True)))
        sleep_enabled.toggled.connect(lambda v: self.config.set("sleep_enabled", v))
        form.addRow("Sleep when idle", sleep_enabled)

        sleep_after = QSpinBox()
        sleep_after.setRange(10, 7200)
        sleep_after.setSuffix(" s")
        sleep_after.setValue(int(float(self.config.get("idle_seconds_before_sleep", 300))))
        sleep_after.valueChanged.connect(
            lambda v: self.config.set("idle_seconds_before_sleep", float(v))
        )
        form.addRow("Idle before sleep", sleep_after)
        return page

    def _appearance_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)

        scale = _slider(30, 400, int(float(self.config.get("pet_scale", 1.0)) * 100))
        scale_label = QLabel(f"{scale.value() / 100:.2f}x")
        scale.valueChanged.connect(
            lambda v: (
                self.config.set("pet_scale", v / 100.0),
                scale_label.setText(f"{v / 100:.2f}x"),
            )
        )
        scale_row = QHBoxLayout()
        scale_row.addWidget(scale, 1)
        scale_row.addWidget(scale_label)
        form.addRow("Pet size", scale_row)

        animation_speed = _slider(25, 300, int(float(self.config.get("animation_speed", 1.0)) * 100))
        animation_speed.valueChanged.connect(
            lambda v: self.config.set("animation_speed", v / 100.0)
        )
        form.addRow("Animation speed", animation_speed)
        return page

    def _advanced_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFormLayout()

        debug = QCheckBox()
        debug.setChecked(bool(self.config.get("debug", False)))
        debug.toggled.connect(self._set_debug)
        form.addRow("Debug logging", debug)
        layout.addLayout(form)

        reset = QPushButton("Reset configuration")
        reset.clicked.connect(self._reset_config)
        layout.addWidget(reset)

        clear = QPushButton("Clear conversations and memory")
        clear.clicked.connect(self._clear_memory)
        layout.addWidget(clear)

        layout.addStretch(1)
        return page

    # ------------------------------------------------------------- handlers
    def _set_toggle(self, key: str, value: bool) -> None:
        self.config.set(key, value)
        if key == "start_with_windows":
            from ui.autostart import set_autostart

            if not set_autostart(value):
                QMessageBox.warning(
                    self, APP_NAME, "Could not update the Windows startup entry."
                )

    def _set_debug(self, enabled: bool) -> None:
        self.config.set("debug", enabled)
        from core.utils.logger import setup_logging

        setup_logging(debug=enabled)

    def _key_status_text(self) -> str:
        masked = credentials.masked_api_key()
        return f"Stored securely ({masked})" if masked else "No API key stored"

    def _save_api_key(self) -> None:
        key = self.key_field.text().strip()
        if not key:
            return
        if credentials.set_api_key(key):
            self.key_field.clear()
            self.key_field.setPlaceholderText(credentials.masked_api_key())
            self.key_status.setText(self._key_status_text())
        else:
            QMessageBox.warning(
                self, APP_NAME, "Could not save the API key to the credential store."
            )

    def _clear_api_key(self) -> None:
        credentials.delete_api_key()
        self.key_field.clear()
        self.key_field.setPlaceholderText("sk-...")
        self.key_status.setText(self._key_status_text())

    def _reset_config(self) -> None:
        confirm = QMessageBox.question(
            self, APP_NAME, "Reset every setting to its default?"
        )
        if confirm == QMessageBox.Yes:
            self.config.reset()
            QMessageBox.information(
                self, APP_NAME, "Settings reset. Restart Glitch to apply them all."
            )

    def _clear_memory(self) -> None:
        confirm = QMessageBox.question(
            self, APP_NAME, "Delete all conversations and remembered facts?"
        )
        if confirm != QMessageBox.Yes:
            return
        if self.db is not None and self.db.available:
            self.db.clear_conversations()
            self.db.clear_memories()
        if self.on_clear_memory:
            self.on_clear_memory()
        QMessageBox.information(self, APP_NAME, "Conversations and memory cleared.")
