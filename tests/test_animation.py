import json

import pytest

from core.animation.controller import AnimationController
from core.animation.registry import AnimationRegistry


# ------------------------------------------------------------------ registry
def test_manifest_declares_the_core_animations(registry):
    for name in ("idle", "walk", "run", "think", "talk", "sleep", "wake", "drag", "drop"):
        assert registry.has(name), name


def test_unknown_animation_falls_back(registry):
    assert registry.spec("no-such-animation").name == registry.fallback


def test_clips_load_at_the_requested_height(registry):
    clip = registry.clip_for("idle")
    assert clip.height == 64
    assert clip.frame_count > 1
    assert not clip.frames[0].isNull()


def test_clips_are_cached(registry):
    assert registry.clip_for("idle") is registry.clip_for("idle")


def test_changing_scale_reloads_at_the_new_size(registry):
    first = registry.clip_for("idle")
    registry.set_target_height(96)
    second = registry.clip_for("idle")
    assert first is not second
    assert second.height == 96


def test_mirrored_clips_carry_flipped_frames(registry):
    clip = registry.clip_for("walk")
    assert clip.flipped
    assert clip.frame(0, mirrored=True) is not clip.frame(0)


def test_a_broken_clip_degrades_to_the_fallback(registry, tmp_path):
    import shutil

    # Everything is present except the clip being asked for.
    shutil.copytree(registry.animations_dir / "idle", tmp_path / "idle")
    registry.animations_dir = tmp_path
    registry.clear_cache()

    clip = registry.clip("run")
    assert clip.name == registry.spec(registry.fallback).clip


def test_a_missing_fallback_is_fatal(registry, tmp_path):
    registry.animations_dir = tmp_path  # nothing on disk at all
    registry.clear_cache()
    with pytest.raises(RuntimeError):
        registry.clip("run")


def test_an_unreadable_manifest_is_fatal(tmp_path, qt_gui_app):
    broken = tmp_path / "animations.json"
    broken.write_text("{ not json", encoding="utf-8")
    with pytest.raises(RuntimeError):
        AnimationRegistry(manifest_path=broken)


def test_manifest_entries_are_well_formed(registry):
    data = json.loads(registry.manifest_path.read_text(encoding="utf-8"))
    for name, entry in data["animations"].items():
        assert "clip" in entry, name
        assert entry.get("fps", 1) > 0, name
        # A one-shot animation must not loop, or it could never finish.
        if entry.get("loop") is False:
            assert entry.get("interruptible", False) in (True, False)


def test_no_transient_animation_loops_forever(registry):
    """Reaction animations must terminate; a looping one would wedge a state."""
    from core.pet.state import STATE_ANIMATION, TRANSIENT_STATES

    for state in TRANSIENT_STATES:
        spec = registry.spec(STATE_ANIMATION[state])
        assert not spec.loop or spec.next_animation, spec.name


# ---------------------------------------------------------------- controller
def test_controller_starts_on_the_fallback(registry):
    assert AnimationController(registry).current == registry.fallback


def test_looping_animation_never_finishes(registry):
    controller = AnimationController(registry)
    controller.play("idle", force=True)
    for _ in range(600):
        controller.update(1 / 30)
    assert not controller.finished
    assert controller.current == "idle"


def test_one_shot_animation_finishes_and_notifies(registry):
    controller = AnimationController(registry)
    seen = []
    controller.on_finished = seen.append
    controller.play("surprised", force=True)
    for _ in range(300):
        controller.update(1 / 30)
    assert controller.finished
    assert seen == ["surprised"]


def test_a_finished_animation_holds_its_last_frame(registry):
    controller = AnimationController(registry)
    controller.play("surprised", force=True)
    for _ in range(300):
        controller.update(1 / 30)
    clip = registry.clip_for("surprised")
    assert controller.current_pixmap() is clip.frames[clip.frame_count - 1]


def test_lower_priority_cannot_interrupt_a_reaction(registry):
    controller = AnimationController(registry)
    controller.play("surprised", force=True)
    assert not controller.play("idle")
    assert controller.current == "surprised"


def test_higher_priority_interrupts_a_reaction(registry):
    controller = AnimationController(registry)
    controller.play("surprised", force=True)
    assert controller.play("drag")
    assert controller.current == "drag"


def test_interruptible_animations_yield(registry):
    controller = AnimationController(registry)
    controller.play("idle", force=True)
    assert controller.play("walk")
    assert controller.current == "walk"


def test_follow_on_animation_plays_automatically(registry):
    controller = AnimationController(registry)
    controller.play("wake", force=True)
    for _ in range(300):
        controller.update(1 / 30)
    assert controller.current == registry.spec("wake").next_animation


def test_speed_scales_playback(registry):
    fast = AnimationController(registry, speed=4.0)
    slow = AnimationController(registry, speed=0.25)
    for controller in (fast, slow):
        controller.play("surprised", force=True)
    for _ in range(30):
        fast.update(1 / 30)
        slow.update(1 / 30)
    assert fast.finished
    assert not slow.finished
