"""Sound effects.

A WAV file for every cue below ships in assets/sounds/. Replacing one swaps
the cue; deleting one turns it into a no-op, so the rest of the runtime never
has to care whether a given sound exists.
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
        self._volume = self._clamp(config.get("sound_volume", 0.4))
        self._enabled = bool(config.get("sounds_enabled", True))
        if self._enabled:
            self._load()

    @staticmethod
    def _clamp(volume: object) -> float:
        try:
            return max(0.0, min(1.0, float(volume)))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0.4

    def _load(self) -> None:
        try:
            from PySide6.QtMultimedia import QSoundEffect
        except ImportError:
            log.info("QtMultimedia unavailable; sound cues disabled")
            self._enabled = False
            return

        missing = []
        for cue in CUES:
            path = SOUNDS_DIR / f"{cue}.wav"
            if not path.exists():
                missing.append(cue)
                continue
            effect = QSoundEffect()
            effect.setSource(QUrl.fromLocalFile(str(path)))
            effect.setVolume(self._volume)
            self._effects[cue] = effect
        log.info("Loaded %d sound cue(s) from %s", len(self._effects), SOUNDS_DIR)
        if missing:
            # Almost always a packaging slip rather than a deliberate deletion,
            # and an inaudible pet gives no other clue that it happened.
            log.warning("No WAV in %s for cue(s): %s", SOUNDS_DIR, ", ".join(missing))

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
        # Remembered as well as applied: cues loaded later must not silently
        # fall back to the volume the config held at startup.
        self._volume = self._clamp(volume)
        for effect in self._effects.values():
            effect.setVolume(self._volume)
