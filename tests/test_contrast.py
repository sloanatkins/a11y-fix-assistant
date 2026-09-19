"""
Contrast Tests
==============
Checks the color math against values that are easy to verify.

Dependencies:
    - pytest
"""

import pytest

from app.contrast import contrast_ratio, hex_to_rgb, suggest_text_color


def test_black_on_white_is_21_to_1():
    assert contrast_ratio((0, 0, 0), (255, 255, 255)) == pytest.approx(21)


@pytest.mark.parametrize(
    "fg, bg, target",
    [("#bbbbbb", "#ffffff", 4.5), ("#777777", "#000000", 7), ("#ffcc00", "#ffffff", 3)],
)
def test_suggestion_reaches_the_target(fg, bg, target):
    color = suggest_text_color(fg, bg, target)
    assert contrast_ratio(hex_to_rgb(color), hex_to_rgb(bg)) >= target


def test_suggestion_stays_close_to_the_original():
    # gray on white should get a darker gray, not jump straight to black
    assert suggest_text_color("#bbbbbb", "#ffffff", 4.5) not in ("#000000", "#ffffff")


def test_impossible_target_returns_none():
    assert suggest_text_color("#777777", "#777777", 22) is None
