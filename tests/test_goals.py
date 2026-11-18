"""Pure goal logic: no Home Assistant needed."""

import itertools
import random

import pytest

from custom_components.daily_goals.const import DailyReset, Direction
from custom_components.daily_goals.goals import (
    IMAGE_THEMES,
    Goal,
    effective,
    format_number,
    is_met,
    link_groups,
    notification_image,
    numeric,
    progress,
)


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("12.5", 12.5),
        ("0", 0.0),
        ("-3", -3.0),
        ("unknown", None),
        ("unavailable", None),
        ("", None),
        (None, None),
        ("abc", None),
        ("nan", None),
        ("inf", None),
    ],
)
def test_numeric(state, expected) -> None:
    assert numeric(state) == expected


def test_above() -> None:
    assert progress(3750, 7500, Direction.ABOVE) == 0.5
    assert progress(9000, 7500, Direction.ABOVE) == 1.0
    assert progress(-5, 7500, Direction.ABOVE) == 0.0
    assert is_met(7500, 7500, Direction.ABOVE)
    assert not is_met(7499.9, 7500, Direction.ABOVE)
    assert progress(None, 7500, Direction.ABOVE) is None
    assert not is_met(None, 7500, Direction.ABOVE)


def test_below() -> None:
    assert is_met(135, 135, Direction.BELOW)
    assert progress(120, 135, Direction.BELOW) == 1.0
    assert progress(150, 100, Direction.BELOW) == pytest.approx(0.5)
    assert progress(250, 100, Direction.BELOW) == 0.0
    # Target zero or negative (a weight trend): the span is 1 unit.
    assert is_met(-0.2, 0, Direction.BELOW)
    assert progress(0.4, 0, Direction.BELOW) == pytest.approx(0.6)


def test_link_groups_are_symmetric_and_merge_chains() -> None:
    groups = link_groups({"a": "b", "b": None, "c": "b", "d": None, "e": "missing", "f": "f"})
    assert groups["a"] == groups["b"] == groups["c"] == frozenset("abc")
    assert groups["d"] == frozenset("d")
    assert groups["e"] == frozenset("e")
    assert groups["f"] == frozenset("f")


def test_effective_needs_the_whole_group() -> None:
    groups = link_groups({"sys": "dia", "dia": None, "steps": None})
    assert effective({"sys": True, "dia": False, "steps": True}, groups) == {"sys": False, "dia": False, "steps": True}
    assert effective({"sys": True, "dia": True, "steps": False}, groups) == {"sys": True, "dia": True, "steps": False}


@pytest.mark.parametrize(
    ("value", "decimals", "language", "expected"),
    [
        (7500, 0, "en", "7,500"),
        (7500, 0, "it", "7500"),
        (12345, 0, "it", "12.345"),
        (29.46, 1, "it-IT", "29,5"),
        (-0.25, 2, "en-GB", "-0.25"),
        (1234567.891, 2, "it", "1.234.567,89"),
    ],
)
def test_format_number(value, decimals, language, expected) -> None:
    assert format_number(value, decimals, language) == expected


def test_image_rotation() -> None:
    rng = random.Random(1)
    same_day = {notification_image(100, offset, rng).split("/")[2] for offset in range(len(IMAGE_THEMES))}
    assert len(same_day) == len(IMAGE_THEMES)  # different goals, different themes
    hosts = [notification_image(day, 0, rng).split("/")[2] for day in range(1, 30)]
    assert all(a != b for a, b in itertools.pairwise(hosts))  # never the same theme two days in a row
    assert all(notification_image(d, 3).startswith("https://") for d in range(10))


def test_goal_from_subentry_defaults() -> None:
    goal = Goal.from_subentry("id1", "Steps", {"source_entity": "sensor.steps", "target": 7500})
    assert goal.direction is Direction.ABOVE
    assert goal.daily_reset is DailyReset.NEW_VALUE
    assert goal.points == 10 and goal.notify and goal.link is None and goal.color is None
    goal = Goal.from_subentry(
        "id2",
        "Fat",
        {
            "source_entity": "sensor.fat",
            "target": 29,
            "direction": "below",
            "decimals": 7,
            "color": [255, 167, 38],
            "points": 0,
            "notify": False,
        },
    )
    assert goal.decimals == 2 and goal.color == (255, 167, 38) and goal.points == 0 and not goal.notify
