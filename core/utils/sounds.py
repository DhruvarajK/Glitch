"""Optional sound effects.

No sounds ship with Glitch. Drop WAV files named after the cues below into
assets/sounds/ and they start playing; until then every call is a no-op, so
the rest of the runtime does not need to care whether audio exists.
"""
from __future__ import annotations

from PySide6.QtCore import QUrl

from core.persistence.config import ConfigManager
from core.utils.constants import SOUNDS_DIR
from core.utils.logger import get_logger

log = get_logger("sounds")

# Cue name -> file stem expected in assets/sounds/.
CUES = ("click", "drag", "drop", "sleep", "wake", "talk", "react")


class SoundPlayer:
    """Plays short cues, silently doing nothing when a cue has no file."""

    def __init__(self, config: ConfigManager) -> None:
        self.config = config
        self._effects: dict[str, object] = {}
        self._enabled = bool(config.get("sounds_enabled", False))
        if self._enabled:
            self._load()

    def _load(self) -> None:
        try:
            from PySide6.QtMultimedia import QSoundEffect
        except ImportError:
            log.info("QtMultimedia unavailable; sound cues disabled")
            self._enabled = False
            return

        for cue in CUES:
            path = SOUNDS_DIR / f"{cue}.wav"
            if not path.exists():
                continue
            effect = QSoundEffect()
            effect.setSource(QUrl.fromLocalFile(str(path)))
            effect.setVolume(float(self.config.get("sound_volume", 0.4)))
            self._effects[cue] = effect
        if self._effects:
            log.info("Loaded %d sound cue(s)", len(self._effects))

    def play(self, cue: str) -> None:
        if not self._enabled:
            return
        effect = self._effects.get(cue)
        if effect is not None:
            effect.play()

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = bool(enabled)
        if self._enabled and not self._effects:
            self._load()

    def set_volume(self, volume: float) -> None:
        volume = max(0.0, min(1.0, float(volume)))
        for effect in self._effects.values():
            effect.setVolume(volume)
