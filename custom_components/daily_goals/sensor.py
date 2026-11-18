# SPDX-License-Identifier: GPL-3.0-or-later
"""Sensors: achieved goals, completion, streak and points; progress of each goal."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DailyGoalsConfigEntry
from .const import CONF_PERFECT_DAY_REWARD
from .entity import DailyGoalsEntity
from .goals import Goal
from .tracker import GoalTracker


@dataclass(frozen=True, kw_only=True)
class DailyGoalsSensorDescription(SensorEntityDescription):
    """A summary sensor and how it reads the tracker."""

    value_fn: Callable[[GoalTracker], Any]


SENSORS: tuple[DailyGoalsSensorDescription, ...] = (
    DailyGoalsSensorDescription(
        key="achieved",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda t: len(t.achieved),
    ),
    DailyGoalsSensorDescription(
        key="completion",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda t: t.completion,
    ),
    DailyGoalsSensorDescription(
        key="streak",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda t: t.streak,
    ),
    DailyGoalsSensorDescription(
        key="best_streak",
        value_fn=lambda t: t.best_streak,
    ),
    DailyGoalsSensorDescription(
        key="points_today",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda t: t.points_today,
    ),
    DailyGoalsSensorDescription(
        key="total_points",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda t: t.total_points,
    ),
)

PROGRESS = SensorEntityDescription(
    key="progress",
    native_unit_of_measurement=PERCENTAGE,
    state_class=SensorStateClass.MEASUREMENT,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: DailyGoalsConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Set up the summary sensors and one progress sensor per goal."""
    tracker = entry.runtime_data
    async_add_entities(
        (AchievedSensor if description.key == "achieved" else SummarySensor)(tracker, description)
        for description in SENSORS
    )
    for goal in tracker.goals.values():
        async_add_entities([ProgressSensor(tracker, PROGRESS, goal)], config_subentry_id=goal.id)


class DailyGoalsSensor(DailyGoalsEntity, SensorEntity):
    """Base of every sensor: target of the set_statistics action."""

    async def async_set_statistics(self, **values: int) -> None:
        """Action daily_goals.set_statistics: streak, best streak and total points."""
        self.tracker.set_statistics(**values)


class SummarySensor(DailyGoalsSensor):
    """A figure of the day or of all days."""

    entity_description: DailyGoalsSensorDescription

    def __init__(self, tracker: GoalTracker, description: DailyGoalsSensorDescription) -> None:
        """Initialise the sensor."""
        super().__init__(tracker, description, "sensor")

    @property
    def native_value(self) -> Any:
        """Value from the tracker."""
        return self.entity_description.value_fn(self.tracker)


class AchievedSensor(SummarySensor):
    """Goals achieved today; its attributes carry everything the card shows."""

    # The card reads the goals from here; the recorder does not need them.
    _unrecorded_attributes = frozenset({"goals", "day"})

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Total, perfect day and the goals."""
        tracker = self.tracker
        return {
            "total": len(tracker.goals),
            "perfect_day": tracker.perfect,
            "perfect_day_reward": tracker.config.get(CONF_PERFECT_DAY_REWARD) or "",
            "day": tracker.day.isoformat() if tracker.day else None,
            "goals": tracker.card_data(),
        }


class ProgressSensor(DailyGoalsSensor):
    """Live progress of one goal towards its target."""

    def __init__(self, tracker: GoalTracker, description: SensorEntityDescription, goal: Goal) -> None:
        """Initialise the sensor."""
        super().__init__(tracker, description, "sensor", goal)

    @property
    def native_value(self) -> int | None:
        """Progress 0-100, unknown while waiting for today's value."""
        assert self.goal is not None
        value = self.tracker.progress(self.goal)
        return None if value is None else round(100 * value)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Value, target and direction."""
        assert self.goal is not None
        goal = self.goal
        return {
            "value": self.tracker.value(goal),
            "target": goal.target,
            "unit": self.tracker.unit(goal),
            "direction": goal.direction.value,
            "daily_reset": goal.daily_reset.value,
            "source": goal.source,
        }
