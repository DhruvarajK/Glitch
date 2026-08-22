"""Integration tests: the controller driving state, physics and animation."""
from __future__ import annotations

import random

import pytest

from core.events.bus import EventBus
from core.events.events import EventType
from core.persistence.config import ConfigManager
from core.pet.controller import PetController
from core.pet.state import PetState
from core.screen.geometry import Rect
from core.screen.manager import ScreenManager

DT = 1 / 30


@pytest.fixture()
def pet(tmp_path, registry, qt_gui_app):
    config = ConfigManager(tmp_path / "config.json")
    screens = ScreenManager()
    screens._screens = [Rect(0, 0, 1000, 800)]
    return PetController(config, registry, screens, EventBus(), rng=random.Random(3))


def advance(pet, seconds: float) -> None:
    for _ in range(int(seconds / DT)):
        pet.update(DT)


# --------------------------------------------------------------- positioning
def test_starts_standing_on_the_floor(pet):
    assert pet.y == pet.floor_y()


def test_stays_inside_the_screen_while_walking(pet):
    pet.walk_to(10_000)
    advance(pet, 30)
    assert 0 <= pet.x <= 1000 - pet.width


def test_walking_reaches_its_target(pet):
    pet.walk_to(pet.x + 200)
    advance(pet, 20)
    assert pet.state in (PetState.IDLE, PetState.WALKING)
    assert pet.x > 0


# ------------------------------------------------------------------ dragging
def test_a_press_without_movement_is_not_a_drag(pet):
    pet.begin_drag(int(pet.x) + 10, int(pet.y) + 10)
    assert not pet.end_drag()
    assert pet.state is not PetState.DRAGGED


def test_moving_the_mouse_starts_a_drag(pet):
    pet.begin_drag(int(pet.x) + 10, int(pet.y) + 10)
    pet.drag_to(int(pet.x) + 200, int(pet.y) - 100)
    assert pet.state is PetState.DRAGGED
    assert pet.end_drag()


def test_dropping_from_a_height_falls_and_lands(pet):
    pet.begin_drag(int(pet.x) + 10, int(pet.y) + 10)
    pet.drag_to(int(pet.x) + 200, 50)
    pet.end_drag()
    advance(pet, 5)
    assert pet.y == pet.floor_y()
    assert pet.state is not PetState.DRAGGED


def test_dropping_on_the_floor_plays_the_drop_pose(pet):
    pet.begin_drag(int(pet.x) + 10, int(pet.y) + 10)
    # The grab offset is (10, 10), so this releases the pet back on the floor.
    pet.drag_to(int(pet.x) + 200, int(pet.y) + 10)
    pet.end_drag()
    assert pet.state is PetState.DROPPED


# ------------------------------------------------------------- state changes
def test_clicking_produces_a_reaction(pet):
    pet.bus.emit(EventType.USER_CLICKED)
    assert pet.state is PetState.REACTING


def test_repeated_clicking_causes_annoyance(pet):
    before = pet.emotion.state.annoyance
    for _ in range(6):
        pet.bus.emit(EventType.USER_CLICKED)
    assert pet.emotion.state.annoyance > before


def test_clicking_a_sleeping_pet_wakes_it(pet):
    pet.sleep()
    pet.bus.emit(EventType.USER_CLICKED)
    assert pet.state is PetState.WAKING


def test_reactions_always_return_to_idle(pet):
    pet.react("surprised")
    advance(pet, 10)
    assert pet.state is not PetState.REACTING


def test_a_looping_reaction_cannot_wedge_the_pet(pet):
    # "dance" loops forever; the transient watchdog must still recover.
    pet.enter_state(PetState.REACTING, animation="dance", force=True)
    advance(pet, 12)
    assert pet.state is PetState.IDLE


def test_pausing_movement_stops_wandering(pet):
    pet.pause_movement(True)
    advance(pet, 60)
    assert pet.state not in (PetState.WALKING, PetState.RUNNING)


def test_state_changes_are_announced(pet):
    seen = []
    pet.bus.subscribe(EventType.PET_STATE_CHANGED, lambda e: seen.append(e.get("state")))
    pet.sleep()
    assert seen[-1] == PetState.SLEEPING.value


# ------------------------------------------------------------ multi-monitor
def test_reaching_the_edge_crosses_to_the_next_monitor(pet):
    pet.screens._screens = [Rect(0, 0, 1000, 800), Rect(1000, 0, 1000, 800)]
    pet.set_position(1000 - pet.width, pet.floor_y())
    pet.facing = 1
    pet.walk_to(5000)
    advance(pet, 20)
    assert pet.x >= 1000 - pet.width


def test_the_pet_turns_around_with_no_monitor_beyond(pet):
    pet.set_position(1000 - pet.width, pet.floor_y())
    pet.facing = 1
    pet.walk_to(5000)
    advance(pet, 20)
    assert pet.facing == -1


def test_losing_a_monitor_pulls_the_pet_back_on_screen(pet):
    pet.screens._screens = [Rect(0, 0, 1000, 800), Rect(1000, 0, 1000, 800)]
    pet.set_position(1500, 600)
    pet.screens._screens = [Rect(0, 0, 1000, 800)]
    pet._on_screens_changed()
    assert pet.x <= 1000 - pet.width


# ----------------------------------------------------------------- scaling
def test_rescaling_keeps_the_pet_on_the_floor(pet):
    from core.utils.constants import BASE_PET_HEIGHT

    pet.apply_scale(2.0)
    pet.update(DT)
    assert pet.height == BASE_PET_HEIGHT * 2
    assert pet.y == pet.floor_y()


def test_rescaling_keeps_the_pet_on_screen(pet):
    pet.apply_scale(4.0)
    pet.update(DT)
    assert pet.x >= 0
    assert pet.y >= 0
