"""The rules deciding which window Glitch is standing on."""
from __future__ import annotations

from core.screen.geometry import Rect
from core.screen.platforms import MAX_RIDE_UP, Platform, find_floor

PET_HEIGHT = 100
DESKTOP_FLOOR = 900.0  # a 1000px-tall screen with a 100px pet


def window(handle: int, x: int, y: int, width: int = 400, height: int = 300) -> Platform:
    return Platform(handle=handle, rect=Rect(x, y, width, height))


def floor(
    platforms: list[Platform],
    *,
    foot_x: float = 200.0,
    reference_y: float = DESKTOP_FLOOR,
    standing_on: int | None = None,
) -> tuple[float, int | None]:
    return find_floor(
        foot_x=foot_x,
        pet_height=PET_HEIGHT,
        reference_y=reference_y,
        desktop_floor=DESKTOP_FLOOR,
        platforms=platforms,
        standing_on=standing_on,
    )


# ------------------------------------------------------------------- fallback
def test_an_empty_desktop_falls_back_to_the_floor():
    assert floor([]) == (DESKTOP_FLOOR, None)


def test_a_window_below_the_desktop_floor_is_ignored():
    assert floor([window(1, 0, 950)]) == (DESKTOP_FLOOR, None)


# -------------------------------------------------------------------- landing
def test_falling_onto_a_window_lands_on_its_top_edge():
    assert floor([window(1, 0, 600)], reference_y=100.0) == (500.0, 1)


def test_a_window_above_the_pet_is_passed_through():
    # Glitch is on the desktop floor; a window higher up must not yank it up.
    assert floor([window(1, 0, 600)], reference_y=DESKTOP_FLOOR) == (DESKTOP_FLOOR, None)


def test_the_first_surface_on_the_way_down_wins():
    high = window(1, 0, 300)
    low = window(2, 0, 600)
    # Dropped from the top, Glitch stops on the higher of the two.
    assert floor([high, low], reference_y=100.0) == (200.0, 1)


def test_walking_past_the_end_of_a_window_drops_to_the_desktop():
    perch = window(1, 0, 600, width=400)
    assert floor([perch], foot_x=500.0, standing_on=1) == (DESKTOP_FLOOR, None)


def test_a_window_that_closes_drops_the_pet():
    assert floor([], reference_y=500.0, standing_on=1) == (DESKTOP_FLOOR, None)


# ------------------------------------------------------------------ occlusion
def test_a_hidden_top_edge_is_not_a_platform():
    # Glitch rests at 400 on the window behind. The one in front covers that
    # spot, and its own edge is above Glitch, so there is nothing left to hold.
    front = window(1, 0, 450, width=800, height=500)
    behind = window(2, 0, 500)
    assert floor([front, behind], reference_y=400.0, standing_on=2) == (DESKTOP_FLOOR, None)


def test_a_front_window_beside_the_pet_does_not_hide_the_edge():
    front = window(1, 700, 450, width=400, height=500)  # right of foot_x=200
    behind = window(2, 0, 500)
    assert floor([front, behind], reference_y=400.0, standing_on=2) == (400.0, 2)


# --------------------------------------------------------------------- riding
def test_the_pet_follows_a_window_that_moves_up_beneath_it():
    moved = window(1, 0, 500)  # was at 600, so its rest line rose by 100
    assert floor([moved], reference_y=500.0, standing_on=1) == (400.0, 1)


def test_a_window_that_jumps_too_far_up_drops_the_pet():
    jumped = window(1, 0, int(500 - MAX_RIDE_UP - 50))
    assert floor([jumped], reference_y=500.0, standing_on=1) == (DESKTOP_FLOOR, None)


def test_a_window_that_moves_down_is_still_landed_on():
    moved = window(1, 0, 700)
    assert floor([moved], reference_y=500.0, standing_on=1) == (600.0, 1)


# ------------------------------------------------------------------ selection
def test_the_front_window_wins_a_tie():
    assert floor([window(1, 0, 600), window(2, 0, 600)], reference_y=100.0) == (500.0, 1)


def test_only_windows_under_the_pet_count():
    assert floor([window(1, 600, 400)], reference_y=100.0) == (DESKTOP_FLOOR, None)
