import json

import pytest

from core.persistence.config import CONFIG_VERSION, DEFAULTS, ConfigManager


@pytest.fixture()
def config_path(tmp_path):
    return tmp_path / "config.json"


def test_defaults_apply_when_no_file_exists(config_path):
    config = ConfigManager(config_path)
    assert config["pet_scale"] == DEFAULTS["pet_scale"]
    assert config["version"] == CONFIG_VERSION


def test_values_round_trip(config_path):
    ConfigManager(config_path).set("movement_speed", 123.0)
    assert ConfigManager(config_path)["movement_speed"] == 123.0


def test_out_of_range_values_are_clamped(config_path):
    config = ConfigManager(config_path)
    config.set("pet_scale", 99.0)
    assert config["pet_scale"] == 4.0
    config.set("pet_scale", 0.0)
    assert config["pet_scale"] == 0.3


def test_uncoercible_values_fall_back_to_the_default(config_path):
    config = ConfigManager(config_path)
    config.set("movement_speed", "not a number")
    assert config["movement_speed"] == DEFAULTS["movement_speed"]


def test_corrupt_file_is_quarantined_and_defaults_restored(config_path):
    config_path.write_text("{not json", encoding="utf-8")
    config = ConfigManager(config_path)
    assert config["pet_scale"] == DEFAULTS["pet_scale"]
    assert config_path.with_suffix(".json.bak").exists()


def test_unknown_keys_are_dropped(config_path):
    config_path.write_text(
        json.dumps({"version": CONFIG_VERSION, "legacy_key": 1}), encoding="utf-8"
    )
    assert "legacy_key" not in ConfigManager(config_path).as_dict()


def test_older_versions_keep_their_values(config_path):
    config_path.write_text(
        json.dumps({"version": 0, "movement_speed": 150.0}), encoding="utf-8"
    )
    config = ConfigManager(config_path)
    assert config["movement_speed"] == 150.0
    assert config["version"] == CONFIG_VERSION


def test_newer_versions_fall_back_to_defaults(config_path):
    config_path.write_text(
        json.dumps({"version": CONFIG_VERSION + 5, "movement_speed": 150.0}),
        encoding="utf-8",
    )
    assert ConfigManager(config_path)["movement_speed"] == DEFAULTS["movement_speed"]


def test_listeners_are_notified_on_change(config_path):
    config = ConfigManager(config_path)
    seen = []
    config.on_change(lambda key, value: seen.append((key, value)))
    config.set("always_on_top", False)
    assert seen == [("always_on_top", False)]


def test_listeners_are_not_notified_when_nothing_changes(config_path):
    config = ConfigManager(config_path)
    seen = []
    config.on_change(lambda key, value: seen.append(key))
    config.set("always_on_top", config["always_on_top"])
    assert seen == []


def test_a_failing_listener_does_not_block_the_change(config_path):
    config = ConfigManager(config_path)

    def boom(key, value):
        raise RuntimeError("listener exploded")

    config.on_change(boom)
    config.set("debug", True)
    assert config["debug"] is True


def test_reset_restores_defaults(config_path):
    config = ConfigManager(config_path)
    config.set("movement_speed", 300.0)
    config.reset()
    assert config["movement_speed"] == DEFAULTS["movement_speed"]
