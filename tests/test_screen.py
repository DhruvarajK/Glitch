import pytest

from core.screen.geometry import Rect, clamp
from core.screen.manager import ScreenManager


# ------------------------------------------------------------------ geometry
def test_rect_edges():
    rect = Rect(10, 20, 100, 50)
    assert (rect.left, rect.top, rect.right, rect.bottom) == (10, 20, 110, 70)
    assert rect.center_x == 60


def test_rect_contains_is_half_open():
    rect = Rect(0, 0, 10, 10)
    assert rect.contains_point(0, 0)
    assert not rect.contains_point(10, 5)


def test_rect_union_spans_both():
    united = Rect(0, 0, 100, 100).united(Rect(-50, 20, 100, 100))
    assert (united.left, united.top, united.right, united.bottom) == (-50, 0, 100, 120)


def test_clamp_handles_an_inverted_range():
    assert clamp(5, 10, 0) == 10


# ---------------------------------------------------- multi-monitor geometry
@pytest.fixture()
def manager(qt_gui_app, monkeypatch):
    """A manager with a scripted, negative-coordinate monitor layout."""
    manager = ScreenManager()
    manager._screens = [
        Rect(0, 0, 1920, 1040),        # primary
        Rect(1920, 0, 1280, 1024),     # to the right
        Rect(-1600, 100, 1600, 900),   # to the left, offset downward
    ]
    return manager


def test_virtual_bounds_cover_every_screen(manager):
    bounds = manager.virtual_bounds()
    assert bounds.left == -1600
    assert bounds.right == 3200


def test_screen_at_finds_the_containing_screen(manager):
    assert manager.screen_at(2000, 500).left == 1920
    assert manager.screen_at(-800, 500).left == -1600


def test_screen_at_falls_back_to_the_nearest(manager):
    # A point in the gap above the left monitor still resolves to a screen.
    assert manager.screen_at(-800, -5000) in manager.screens


def test_clamp_keeps_the_sprite_fully_on_screen(manager):
    x, y = manager.clamp_position(900, 1030, 190, 190)
    assert x == 900
    assert y == 1040 - 190


def test_clamp_resolves_a_straddling_sprite_onto_one_screen(manager):
    # Sitting across the seam, the sprite is pulled fully onto the screen its
    # centre falls on rather than being left half off both.
    x, y = manager.clamp_position(1900, 500, 190, 190)
    screen = manager.screen_at(x + 95, y + 95)
    assert screen.left <= x and x + 190 <= screen.right


def test_floor_sits_at_the_bottom_of_the_local_screen(manager):
    assert manager.floor_for(2000, 500, 190) == 1024 - 190


def test_adjacent_screen_to_the_right(manager):
    neighbour = manager.adjacent_screen(manager.screens[0], 1)
    assert neighbour is not None and neighbour.left == 1920


def test_adjacent_screen_to_the_left(manager):
    neighbour = manager.adjacent_screen(manager.screens[0], -1)
    assert neighbour is not None and neighbour.left == -1600


def test_no_neighbour_beyond_the_outermost_screen(manager):
    assert manager.adjacent_screen(manager.screens[1], 1) is None


def test_screens_without_vertical_overlap_are_not_adjacent(manager):
    manager._screens = [Rect(0, 0, 1920, 1000), Rect(1920, 2000, 1280, 1000)]
    assert manager.adjacent_screen(manager.screens[0], 1) is None


def test_a_single_screen_has_no_neighbours(manager):
    manager._screens = [Rect(0, 0, 1920, 1040)]
    assert manager.adjacent_screen(manager.screens[0], 1) is None
    assert manager.adjacent_screen(manager.screens[0], -1) is None
