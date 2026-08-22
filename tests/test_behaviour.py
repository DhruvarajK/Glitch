import random

import pytest

from core.ai.emotion import EmotionEngine, EmotionState
from core.events.bus import EventBus
from core.events.events import EventType
from core.persistence.config import ConfigManager
from core.pet.behavior import BehaviorController
from core.pet.state import PetState


@pytest.fixture()
def config(tmp_path):
    return ConfigManager(tmp_path / "config.json")


@pytest.fixture()
def behavior(config):
    return BehaviorController(config, rng=random.Random(1))


# ----------------------------------------------------------------- weighting
def test_energy_increases_the_urge_to_walk(behavior):
    lively = behavior.weights_for(EmotionState(energy=1.0))
    flat = behavior.weights_for(EmotionState(energy=0.0))
    assert lively["walk"] > flat["walk"]


def test_sleepiness_increases_resting(behavior):
    tired = behavior.weights_for(EmotionState(sleepiness=1.0))
    fresh = behavior.weights_for(EmotionState(sleepiness=0.0))
    assert tired["sleep"] > fresh["sleep"]
    assert tired["sit"] > fresh["sit"]


def test_annoyance_suppresses_play(behavior):
    cross = behavior.weights_for(EmotionState(annoyance=1.0))
    calm = behavior.weights_for(EmotionState(annoyance=0.0))
    assert cross["play"] < calm["play"]


def test_disabling_movement_removes_walking(behavior, config):
    config.set("autonomous_movement", False)
    assert behavior.weights_for(EmotionState())["walk"] == 0.0


def test_disabling_sleep_removes_sleeping(behavior, config):
    config.set("sleep_enabled", False)
    assert behavior.weights_for(EmotionState())["sleep"] == 0.0


# ----------------------------------------------------------------- decisions
def test_no_decision_before_the_interval_elapses(behavior):
    assert behavior.update(0.1, PetState.IDLE, EmotionState()) is None


def test_pausing_stops_all_decisions(behavior):
    behavior.paused = True
    for _ in range(200):
        assert behavior.update(0.1, PetState.IDLE, EmotionState()) is None


def test_walking_is_not_re_rolled_into_another_walk(behavior):
    for _ in range(50):
        intent = behavior.decide(PetState.WALKING, EmotionState())
        assert intent is None or intent.action == "stop"


def test_a_rested_pet_wakes_itself(behavior):
    intent = behavior.decide(PetState.SLEEPING, EmotionState(sleepiness=0.0, energy=0.9))
    assert intent is not None and intent.action == "wake"


def test_a_tired_pet_stays_asleep(behavior):
    assert behavior.decide(PetState.SLEEPING, EmotionState(sleepiness=0.9, energy=0.1)) is None


def test_decisions_stay_within_the_known_actions(behavior):
    known = {"walk", "stop", "sit", "look", "stretch", "yawn", "react", "sleep", "wake"}
    for _ in range(500):
        intent = behavior.decide(PetState.IDLE, EmotionState())
        assert intent is None or intent.action in known


# ------------------------------------------------------------------ emotions
def test_traits_are_clamped_to_the_unit_range():
    engine = EmotionEngine()
    engine.adjust({"happiness": 5.0})
    assert engine.state.happiness == 1.0
    engine.adjust({"happiness": -5.0})
    assert engine.state.happiness == 0.0


def test_being_dragged_causes_annoyance():
    engine = EmotionEngine()
    before = engine.state.annoyance
    engine.apply("dragged")
    assert engine.state.annoyance > before


def test_an_unknown_reaction_changes_nothing():
    engine = EmotionEngine()
    before = engine.state.as_dict()
    engine.apply("does-not-exist")
    assert engine.state.as_dict() == before


def test_staying_awake_accumulates_sleepiness():
    engine = EmotionEngine()
    engine.update(600.0)
    assert engine.state.sleepiness > 0.5


def test_sleeping_clears_sleepiness():
    engine = EmotionEngine(EmotionState(sleepiness=1.0))
    engine.update(120.0, asleep=True)
    assert engine.state.sleepiness < 0.1


def test_traits_drift_back_toward_baseline():
    engine = EmotionEngine(EmotionState(annoyance=1.0))
    engine.update(300.0)
    assert engine.state.annoyance < 0.5


def test_mood_reflects_the_dominant_trait():
    assert EmotionEngine(EmotionState(sleepiness=0.9)).mood() == "sleepy"
    assert EmotionEngine(EmotionState(annoyance=0.9)).mood() == "annoyed"
    assert EmotionEngine(EmotionState(happiness=0.9, energy=0.9)).mood() == "excited"


def test_every_mood_maps_to_a_reaction():
    for state in (
        EmotionState(sleepiness=0.9),
        EmotionState(annoyance=0.9),
        EmotionState(happiness=0.1),
        EmotionState(curiosity=0.9),
        EmotionState(energy=0.1),
        EmotionState(),
    ):
        assert EmotionEngine(state).reaction_animation()


# ---------------------------------------------------------------- event bus
def test_handlers_receive_their_events():
    bus = EventBus()
    seen = []
    bus.subscribe(EventType.USER_CLICKED, seen.append)
    bus.emit(EventType.USER_CLICKED, x=1)
    assert seen[0].get("x") == 1


def test_a_failing_handler_does_not_block_the_others():
    bus = EventBus()
    seen = []

    def boom(event):
        raise RuntimeError("handler exploded")

    bus.subscribe(EventType.USER_CLICKED, boom)
    bus.subscribe(EventType.USER_CLICKED, seen.append)
    bus.emit(EventType.USER_CLICKED)
    assert len(seen) == 1


def test_unsubscribing_stops_delivery():
    bus = EventBus()
    seen = []
    unsubscribe = bus.subscribe(EventType.USER_CLICKED, seen.append)
    unsubscribe()
    bus.emit(EventType.USER_CLICKED)
    assert seen == []


def test_wildcard_handlers_see_everything():
    bus = EventBus()
    seen = []
    bus.subscribe_all(seen.append)
    bus.emit(EventType.USER_CLICKED)
    bus.emit(EventType.PET_WOKE_UP)
    assert len(seen) == 2
