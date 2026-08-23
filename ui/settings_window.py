"""Settings dialog.

Changes are written straight to the config manager, which notifies the running
pet: sliders and toggles take effect immediately rather than on close.
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
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
        reminders=None,
    ) -> None:
        super().__init__(None)
        self.config = config
        self.db = database
        self.on_clear_memory = on_clear_memory
        self.reminders = reminders

        self.setWindowTitle(f"{APP_NAME} Settings")
        self.setMinimumWidth(420)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)

        tabs = QTabWidget(self)
        tabs.addTab(self._general_tab(), "General")
        tabs.addTab(self._ai_tab(), "AI")
        tabs.addTab(self._behaviour_tab(), "Behaviour")
        tabs.addTab(self._awareness_tab(), "Awareness")
        tabs.addTab(self._actions_tab(), "Actions")
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

        requests = QSpinBox()
        requests.setRange(0, 10_000)
        requests.setSpecialValueText("no limit")
        requests.setSuffix(" per day")
        requests.setValue(int(self.config.get("daily_request_limit", 60)))
        requests.valueChanged.connect(lambda v: self.config.set("daily_request_limit", v))
        form.addRow("Request limit", requests)

        tokens = QSpinBox()
        tokens.setRange(0, 10_000_000)
        tokens.setSingleStep(10_000)
        tokens.setSpecialValueText("no limit")
        tokens.setSuffix(" tokens per day")
        tokens.setValue(int(self.config.get("daily_token_limit", 120_000)))
        tokens.valueChanged.connect(lambda v: self.config.set("daily_token_limit", v))
        form.addRow("Token limit", tokens)

        if self.db is not None and self.db.available:
            today = self.db.usage_today()
            spent = QLabel(
                f"{today['requests']} requests, "
                f"{today['input_tokens'] + today['output_tokens']} tokens"
            )
            spent.setStyleSheet("color: #888;")
            form.addRow("Spent today", spent)

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

        roaming = QCheckBox()
        roaming.setChecked(bool(self.config.get("multi_monitor_roaming", True)))
        roaming.toggled.connect(lambda v: self.config.set("multi_monitor_roaming", v))
        form.addRow("Roam across monitors", roaming)

        window_walking = QCheckBox()
        window_walking.setChecked(bool(self.config.get("window_walking", True)))
        window_walking.toggled.connect(lambda v: self.config.set("window_walking", v))
        form.addRow("Walk on windows", window_walking)

        sounds = QCheckBox()
        sounds.setChecked(bool(self.config.get("sounds_enabled", False)))
        sounds.toggled.connect(lambda v: self.config.set("sounds_enabled", v))
        form.addRow("Sound effects", sounds)

        volume = _slider(0, 100, int(float(self.config.get("sound_volume", 0.4)) * 100))
        volume.valueChanged.connect(lambda v: self.config.set("sound_volume", v / 100.0))
        form.addRow("Sound volume", volume)
        return page

    def _awareness_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFormLayout()

        enabled = QCheckBox()
        enabled.setChecked(bool(self.config.get("awareness_enabled", True)))
        enabled.toggled.connect(lambda v: self.config.set("awareness_enabled", v))
        form.addRow("Notice what I'm doing", enabled)

        ai_replies = QCheckBox()
        ai_replies.setChecked(bool(self.config.get("awareness_ai_replies", False)))
        ai_replies.toggled.connect(lambda v: self.config.set("awareness_ai_replies", v))
        form.addRow("Write these lines with AI", ai_replies)

        cooldown = QSpinBox()
        cooldown.setRange(60, 21600)
        cooldown.setSingleStep(60)
        cooldown.setSuffix(" s")
        cooldown.setValue(int(float(self.config.get("proactive_cooldown_seconds", 600))))
        cooldown.valueChanged.connect(
            lambda v: self.config.set("proactive_cooldown_seconds", float(v))
        )
        form.addRow("Quiet time between remarks", cooldown)

        daily = QSpinBox()
        daily.setRange(0, 100)
        daily.setSuffix(" per day")
        daily.setValue(int(self.config.get("proactive_daily_limit", 6)))
        daily.valueChanged.connect(lambda v: self.config.set("proactive_daily_limit", v))
        form.addRow("Most remarks a day", daily)

        titles = QCheckBox()
        titles.setChecked(bool(self.config.get("awareness_read_window_titles", False)))
        titles.toggled.connect(self._set_read_titles)
        form.addRow("Read window titles", titles)
        layout.addLayout(form)

        note = QLabel(
            "Glitch only ever looks at which apps are running and which one is "
            "in front, plus how long you have been away. Window titles are off "
            "by default and are never sent anywhere. Setting the daily limit to "
            "0 keeps Glitch silent while still letting it react with a face."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #888;")
        layout.addWidget(note)
        layout.addStretch(1)
        return page

    def _actions_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        layout.addWidget(QLabel("Apps Glitch may open when asked"))
        self.whitelist_table = QTableWidget(0, 2)
        self.whitelist_table.setHorizontalHeaderLabels(["Say this", "Runs this"])
        self.whitelist_table.setEditTriggers(QAbstractItemView.AllEditTriggers)
        self.whitelist_table.horizontalHeader().setStretchLastSection(True)
        self._load_whitelist()
        layout.addWidget(self.whitelist_table)

        add = QPushButton("Add")
        add.clicked.connect(lambda: self.whitelist_table.insertRow(
            self.whitelist_table.rowCount()
        ))
        remove = QPushButton("Remove")
        remove.clicked.connect(self._remove_whitelist_row)
        save = QPushButton("Save apps")
        save.clicked.connect(self._save_whitelist)
        row = QHBoxLayout()
        row.addWidget(add)
        row.addWidget(remove)
        row.addStretch(1)
        row.addWidget(save)
        layout.addLayout(row)

        note = QLabel(
            "Glitch will only start something listed here, and runs it directly "
            "rather than through a command line. Notepad, calculator and paint "
            "work without being listed."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #888;")
        layout.addWidget(note)

        layout.addWidget(QLabel("Pending reminders"))
        self.reminder_list = QListWidget()
        self._load_reminders()
        layout.addWidget(self.reminder_list)

        clear_reminders = QPushButton("Cancel all reminders")
        clear_reminders.clicked.connect(self._clear_reminders)
        layout.addWidget(clear_reminders)
        return page

    def _load_whitelist(self) -> None:
        entries = dict(self.config.get("app_whitelist", {}) or {})
        self.whitelist_table.setRowCount(len(entries))
        for row, (name, command) in enumerate(sorted(entries.items())):
            self.whitelist_table.setItem(row, 0, QTableWidgetItem(str(name)))
            self.whitelist_table.setItem(row, 1, QTableWidgetItem(str(command)))

    def _remove_whitelist_row(self) -> None:
        row = self.whitelist_table.currentRow()
        if row >= 0:
            self.whitelist_table.removeRow(row)

    def _save_whitelist(self) -> None:
        entries: dict[str, str] = {}
        for row in range(self.whitelist_table.rowCount()):
            name = self.whitelist_table.item(row, 0)
            command = self.whitelist_table.item(row, 1)
            if name and command and name.text().strip() and command.text().strip():
                entries[name.text().strip().lower()] = command.text().strip()
        self.config.set("app_whitelist", entries)
        self._load_whitelist()
        QMessageBox.information(self, APP_NAME, f"{len(entries)} app(s) saved.")

    def _load_reminders(self) -> None:
        self.reminder_list.clear()
        pending = self.reminders.pending() if self.reminders is not None else []
        for reminder in pending:
            due = reminder.due_at.strftime("%H:%M")
            self.reminder_list.addItem(f"{due} - {reminder.text}")
        if not pending:
            self.reminder_list.addItem("Nothing pending.")

    def _clear_reminders(self) -> None:
        if self.reminders is None:
            return
        cancelled = self.reminders.cancel_all()
        self._load_reminders()
        QMessageBox.information(self, APP_NAME, f"{cancelled} reminder(s) cancelled.")

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

        if self.db is not None and self.db.available:
            stored = QLabel(f"{len(self.db.memories(limit=1000))} remembered fact(s)")
            stored.setStyleSheet("color: #888;")
            layout.addWidget(stored)

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

    def _set_read_titles(self, enabled: bool) -> None:
        if enabled:
            confirm = QMessageBox.question(
                self,
                APP_NAME,
                "Let Glitch read the title of the window you are using?\n\n"
                "Titles often contain file names, document names and page "
                "titles. They stay on this machine unless AI replies are also "
                "on, in which case they may be sent to the model.",
            )
            if confirm != QMessageBox.Yes:
                self.config.set("awareness_read_window_titles", False)
                return
        self.config.set("awareness_read_window_titles", enabled)

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
