# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure goal logic, without Home Assistant imports: progress, achievement, linked goals, images."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import math
import random
from typing import Any

from .const import (
    CONF_COLOR,
    CONF_DAILY_RESET,
    CONF_DECIMALS,
    CONF_DIRECTION,
    CONF_ICON,
    CONF_LINK,
    CONF_NOTIFY,
    CONF_POINTS,
    CONF_REWARD,
    CONF_SOURCE,
    CONF_TARGET,
    CONF_UNIT,
    CONF_WAITING_TEXT,
    DEFAULT_ICON,
    DEFAULT_POINTS,
    MAX_DECIMALS,
    STREAK_MILESTONES,
    DailyReset,
    Direction,
)

INVALID_STATES = ("unknown", "unavailable", "none", "")


@dataclass(frozen=True)
class Goal:
    """One goal, as configured in its subentry."""

    id: str
    name: str
    source: str
    target: float
    direction: Direction = Direction.ABOVE
    daily_reset: DailyReset = DailyReset.NEW_VALUE
    link: str | None = None
    icon: str = DEFAULT_ICON
    color: tuple[int, int, int] | None = None
    unit: str = ""
    decimals: int = 0
    waiting_text: str = ""
    points: int = DEFAULT_POINTS
    reward: str = ""
    notify: bool = True

    @classmethod
    def from_subentry(cls, goal_id: str, title: str, data: Mapping[str, Any]) -> Goal:
        """Build a goal from the data of its subentry (missing keys take their defaults)."""
        color = data.get(CONF_COLOR)
        return cls(
            id=goal_id,
            name=title,
            source=data[CONF_SOURCE],
            target=float(data[CONF_TARGET]),
            direction=Direction(data.get(CONF_DIRECTION, Direction.ABOVE)),
            daily_reset=DailyReset(data.get(CONF_DAILY_RESET, DailyReset.NEW_VALUE)),
            link=data.get(CONF_LINK) or None,
            icon=data.get(CONF_ICON) or DEFAULT_ICON,
            color=tuple(int(c) for c in color[:3]) if color else None,
            unit=data.get(CONF_UNIT) or "",
            decimals=max(0, min(MAX_DECIMALS, int(data.get(CONF_DECIMALS) or 0))),
            waiting_text=data.get(CONF_WAITING_TEXT) or "",
            points=int(data.get(CONF_POINTS, DEFAULT_POINTS) or 0),
            reward=data.get(CONF_REWARD) or "",
            notify=bool(data.get(CONF_NOTIFY, True)),
        )


def numeric(state: str | None) -> float | None:
    """The numeric value of a state string, or None."""
    if state is None or str(state).lower() in INVALID_STATES:
        return None
    try:
        value = float(state)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def is_met(value: float | None, target: float, direction: Direction) -> bool:
    """Whether a value achieves the target."""
    if value is None:
        return False
    return value <= target if direction is Direction.BELOW else value >= target


def progress(value: float | None, target: float, direction: Direction) -> float | None:
    """Progress towards the target, from 0 to 1 (None without a value).

    Above: value / target. Below: 1 when at or under the target, then it falls
    linearly and reaches 0 at twice the target (or target + 1 for targets <= 0).
    """
    if value is None:
        return None
    if is_met(value, target, direction):
        return 1.0
    if direction is Direction.BELOW:
        span = target if target > 0 else 1.0
        return max(0.0, min(1.0, 1 - (value - target) / span))
    if target <= 0:
        return 0.0
    return max(0.0, min(1.0, value / target))


def link_groups(links: Mapping[str, str | None]) -> dict[str, frozenset[str]]:
    """Group goals linked with "complete together with" (links count both ways, chains merge).

    Links to goals that do not exist are ignored. Every goal maps to its group
    (a goal without links is a group of one).
    """
    parent = {goal: goal for goal in links}

    def find(goal: str) -> str:
        while parent[goal] != goal:
            parent[goal] = parent[parent[goal]]
            goal = parent[goal]
        return goal

    for goal, other in links.items():
        if other and other in parent and other != goal:
            parent[find(goal)] = find(other)
    members: dict[str, set[str]] = {}
    for goal in links:
        members.setdefault(find(goal), set()).add(goal)
    return {goal: frozenset(members[find(goal)]) for goal in links}


def effective(met: Mapping[str, bool], groups: Mapping[str, frozenset[str]]) -> dict[str, bool]:
    """A goal counts as met only when every goal of its group is met at the same time."""
    return {goal: all(met.get(member, False) for member in groups.get(goal, {goal})) for goal in met}


def format_number(value: float, decimals: int, language: str) -> str:
    """A number formatted like the card does (Unicode CLDR rules, as in the browser).

    English groups thousands with a comma; Italian uses a decimal comma and groups
    with a dot only from five integer digits (7500, but 12.345).
    """
    if language.split("-")[0].lower() != "it":
        return f"{value:,.{decimals}f}"
    grouped = f"{value:,.{decimals}f}" if abs(value) >= 10000 else f"{value:.{decimals}f}"
    return grouped.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def new_milestone(streak: int) -> bool:
    """Whether a streak length is one of the celebrated milestones."""
    return streak in STREAK_MILESTONES


# Notification images: free services that answer with a picture, no account or key needed.
# One theme per day and goal, rotating (never the same theme two days in a row for a goal,
# different themes for different goals on the same day); the picture inside a theme is random.
IMAGE_THEMES: tuple[Callable[[random.Random], str], ...] = (
    lambda r: f"https://randomfox.ca/images/{r.randint(1, 122)}.jpg",
    lambda r: f"https://picsum.photos/seed/{r.randint(1, 99999)}/800/600",
    lambda r: f"https://cataas.com/cat?width=800&r={r.randint(1, 99999)}",
    lambda r: f"https://random-d.uk/api/randomimg?r={r.randint(1, 99999)}",
    lambda r: f"https://placedog.net/800/600?id={r.randint(1, 239)}",
    lambda r: f"https://robohash.org/{r.randint(1, 99999)}.png?size=800x600&set=set{r.randint(1, 3)}",
    lambda r: (
        f"https://loremflickr.com/800/600/{r.choice(('galaxy', 'nebula', 'aurora', 'mountains'))}"
        f"?lock={r.randint(1, 99999)}"
    ),
)


def notification_image(day_of_year: int, offset: int, rng: random.Random | None = None) -> str:
    """URL of the picture for a notification (offset = position of the goal)."""
    theme = IMAGE_THEMES[(day_of_year + offset) % len(IMAGE_THEMES)]
    return theme(rng or random.Random())
