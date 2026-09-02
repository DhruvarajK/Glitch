"""The cues are easy to break silently: an inaudible pet raises no error."""
from __future__ import annotations

from pathlib import Path

import pytest

from core.persistence.config import DEFAULTS, ConfigManager
from core.utils.constants import SOUNDS_DIR
from core.utils.sounds import CUES, SoundPlayer


@pytest.fixture()
def config(tmp_path):
    return ConfigManager(tmp_path / "config.json")


def test_every_cue_ships_a_wav_file():
    missing = [cue for cue in CUES if not (SOUNDS_DIR / f"{cue}.wav").exists()]
    assert not missing


def test_build_spec_bundles_the_sounds_directory():
    spec = Path(__file__).resolve().parents[1] / "glitch.spec"
    assert '"assets" / "sounds"' in spec.read_text(encoding="utf-8")


def test_sounds_are_on_by_default():
    assert DEFAULTS["sounds_enabled"] is True


def test_a_v1_config_that_predates_the_wav_files_gets_sound_back(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"version": 1, "sounds_enabled": false}', encoding="utf-8")
    assert ConfigManager(path)["sounds_enabled"] is True


def test_turning_sound_off_survives_a_reload(tmp_path):
    path = tmp_path / "config.json"
    ConfigManager(path).set("sounds_enabled", False)
    assert ConfigManager(path)["sounds_enabled"] is False


def test_every_cue_loads(qt_gui_app, config):
    player = SoundPlayer(config)
    if not player._effects:
        pytest.skip("QtMultimedia unavailable")
    assert sorted(player._effects) == sorted(CUES)


def test_a_volume_set_before_loading_is_applied_to_the_cues(qt_gui_app, tmp_path):
    config = ConfigManager(tmp_path / "config.json")
    config.set("sounds_enabled", False)
    player = SoundPlayer(config)
    player.set_volume(0.9)
    player.set_enabled(True)
    if not player._effects:
        pytest.skip("QtMultimedia unavailable")
    assert all(e.volume() == pytest.approx(0.9) for e in player._effects.values())


def test_playing_an_unknown_cue_is_a_no_op(qt_gui_app, config):
    SoundPlayer(config).play("nope")
