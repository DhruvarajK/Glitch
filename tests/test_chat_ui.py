"""Chat bubble and input geometry.

The bubble once measured its text with font metrics but painted into a
slightly smaller rectangle, so the text re-wrapped and clipped at the top and
bottom. These tests pin the invariant that the measured layout and the painted
area are the same.
"""
from __future__ import annotations

import pytest

from ui.chat_bubble import PADDING_X, PADDING_Y, SHADOW, TAIL_HEIGHT, ChatBubble
from ui.widgets.chat_input import BUTTON_SIZE, MAX_LINES, ChatInput

SHORT = "Nope."
LONG = (
    "I can't show feelings like that, but I can understand them! "
    "Is something bothering you?"
)
VERY_LONG = " ".join(["Glitch has quite a lot to say about this"] * 12)
UNBREAKABLE = "supercalifragilisticexpialidocious" * 4


@pytest.fixture()
def bubble(qt_gui_app):
    widget = ChatBubble()
    yield widget
    widget.close()


@pytest.fixture()
def chat_input(qt_gui_app):
    widget = ChatInput(lambda text: None)
    yield widget
    widget.close()


def text_area(bubble: ChatBubble):
    """The rectangle paintEvent draws the document into."""
    body = bubble._body_rect()
    return (
        body.width() - PADDING_X * 2,
        body.height() - PADDING_Y * 2,
    )


# ------------------------------------------------------------------- bubble
@pytest.mark.parametrize("text", [SHORT, LONG, VERY_LONG, UNBREAKABLE])
def test_the_text_always_fits_inside_the_bubble(bubble, text):
    bubble.show_text(text, sticky=True)
    document = bubble._document
    width, height = text_area(bubble)
    assert width >= document.textWidth()
    assert height >= document.size().height()


def test_a_short_message_gets_a_snug_bubble(bubble):
    bubble.show_text(SHORT, sticky=True)
    narrow = bubble.width()
    bubble.show_text(LONG, sticky=True)
    assert bubble.width() > narrow


def test_the_bubble_grows_taller_as_the_text_wraps(bubble):
    bubble.show_text(LONG, sticky=True)
    short_height = bubble.height()
    bubble.show_text(VERY_LONG, sticky=True)
    assert bubble.height() > short_height


def test_the_body_leaves_room_for_the_tail_and_shadow(bubble):
    bubble.show_text(LONG, sticky=True)
    body = bubble._body_rect()
    assert body.height() == bubble.height() - TAIL_HEIGHT - SHADOW * 2
    assert body.top() >= SHADOW


def test_streaming_text_keeps_fitting_at_every_length(bubble):
    for end in range(1, len(LONG) + 1, 7):
        bubble.hold(LONG[:end])
        width, height = text_area(bubble)
        assert height >= bubble._document.size().height()


def test_empty_text_dismisses_the_bubble(bubble):
    bubble.show_text(LONG, sticky=True)
    bubble.show_text("   ")
    assert not bubble.isVisible()


def test_the_tail_points_at_the_pet(bubble):
    bubble.show_text(SHORT, sticky=True)
    bubble.follow(500, 400, 190, 190, 0, 1920, 0, 1080)
    assert not bubble._tail_below
    pet_centre = 500 + 95
    assert abs((bubble.x() + bubble._tail_x) - pet_centre) <= 1


def test_the_bubble_flips_below_the_pet_when_short_of_room(bubble):
    bubble.show_text(VERY_LONG, sticky=True)
    bubble.follow(500, 0, 190, 190, 0, 1920, 0, 1080)
    assert bubble._tail_below
    assert bubble.y() >= 0


def test_the_bubble_stays_within_the_screen(bubble):
    bubble.show_text(LONG, sticky=True)
    bubble.follow(1900, 400, 190, 190, 0, 1920, 0, 1080)
    assert bubble.x() + bubble.width() <= 1920


# -------------------------------------------------------------------- input
def test_the_pill_starts_one_line_tall(chat_input):
    assert chat_input.height() == BUTTON_SIZE + (6 + 7) * 2


def test_the_send_button_is_disabled_until_there_is_text(chat_input):
    assert not chat_input.send_button.isEnabled()
    chat_input.field.setPlainText("hello")
    assert chat_input.send_button.isEnabled()


def test_whitespace_alone_does_not_enable_sending(chat_input):
    chat_input.field.setPlainText("    \n  ")
    assert not chat_input.send_button.isEnabled()


def test_the_pill_grows_with_extra_lines(chat_input):
    one_line = chat_input.height()
    chat_input.field.setPlainText("first\nsecond\nthird")
    assert chat_input.height() > one_line


def test_growth_stops_at_the_line_limit(chat_input):
    chat_input.field.setPlainText("\n".join(str(n) for n in range(40)))
    capped = chat_input.height()
    chat_input.field.setPlainText("\n".join(str(n) for n in range(200)))
    assert chat_input.height() == capped
    assert chat_input.field.height() <= MAX_LINES * chat_input.field.line_height() + 4


def test_growing_keeps_the_bottom_edge_anchored(chat_input):
    chat_input.open_near(600, 700, 0, 1920)
    bottom = chat_input.y() + chat_input.height()
    chat_input.field.setPlainText("first\nsecond\nthird\nfourth")
    assert chat_input.y() + chat_input.height() == bottom


def test_submitting_sends_the_text_and_closes(qt_gui_app):
    sent: list[str] = []
    widget = ChatInput(sent.append)
    widget.field.setPlainText("  hello there  ")
    widget._submit()
    assert sent == ["hello there"]
    assert widget.field.toPlainText() == ""
    assert not widget.isVisible()
    widget.close()


def test_the_prompt_opens_within_the_screen(chat_input):
    chat_input.open_near(10, 500, 0, 1920)
    assert chat_input.x() >= 0
    chat_input.open_near(1915, 500, 0, 1920)
    assert chat_input.x() + chat_input.width() <= 1920
