from core.pet.state import PetState
from core.pet.state_machine import PetStateMachine


def test_starts_idle():
    machine = PetStateMachine()
    assert machine.state is PetState.IDLE
    assert machine.time_in_state == 0.0


def test_ongoing_states_can_always_be_left():
    machine = PetStateMachine(PetState.WALKING)
    assert machine.transition(PetState.IDLE)
    assert machine.state is PetState.IDLE


def test_transient_state_blocks_lower_priority():
    machine = PetStateMachine()
    machine.transition(PetState.REACTING)
    assert not machine.transition(PetState.WALKING)
    assert machine.state is PetState.REACTING


def test_transient_state_yields_to_higher_priority():
    machine = PetStateMachine()
    machine.transition(PetState.REACTING)
    assert machine.transition(PetState.DRAGGED)
    assert machine.state is PetState.DRAGGED


def test_force_overrides_priority():
    machine = PetStateMachine()
    machine.transition(PetState.DROPPED)
    assert machine.transition(PetState.IDLE, force=True)
    assert machine.state is PetState.IDLE


def test_transition_to_same_state_is_a_no_op():
    machine = PetStateMachine(PetState.SLEEPING)
    assert not machine.transition(PetState.SLEEPING, force=True)


def test_resume_returns_to_the_interrupted_state():
    machine = PetStateMachine(PetState.WALKING)
    machine.transition(PetState.THINKING, resume_after=True)
    assert machine.resume() is PetState.WALKING
    assert machine.state is PetState.WALKING


def test_resume_falls_back_when_nothing_was_stored():
    machine = PetStateMachine(PetState.REACTING)
    assert machine.resume(PetState.SITTING) is PetState.SITTING


def test_change_callback_reports_both_states():
    machine = PetStateMachine()
    seen = []
    machine.on_change = lambda before, after: seen.append((before, after))
    machine.transition(PetState.WALKING)
    assert seen == [(PetState.IDLE, PetState.WALKING)]


def test_time_in_state_resets_on_transition():
    machine = PetStateMachine()
    machine.update(2.0)
    assert machine.time_in_state == 2.0
    machine.transition(PetState.WALKING)
    assert machine.time_in_state == 0.0
