# SPDX-License-Identifier: GPL-3.0-or-later
"""Binary sensors: perfect day, and whether each goal was achieved today."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DailyGoalsConfigEntry
from .entity import DailyGoalsEntity

PERFECT_DAY = BinarySensorEntityDescription(key="perfect_day")
ACHIEVED = BinarySensorEntityDescription(key="achieved")


async def async_setup_entry(
    hass: HomeAssistant, entry: DailyGoalsConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Set up the perfect day sensor and one achieved sensor per goal."""
    tracker = entry.runtime_data
    async_add_entities([PerfectDaySensor(tracker, PERFECT_DAY, "binary_sensor")])
    for goal in tracker.goals.values():
        async_add_entities([GoalAchievedSensor(tracker, ACHIEVED, "binary_sensor", goal)], config_subentry_id=goal.id)


class PerfectDaySensor(DailyGoalsEntity, BinarySensorEntity):
    """On once every goal has been achieved today; off again at midnight."""

    @property
    def is_on(self) -> bool:
        """Whether today is a perfect day."""
        return self.tracker.perfect


class GoalAchievedSensor(DailyGoalsEntity, BinarySensorEntity):
    """On once the goal has been achieved today (with its linked goals); off again at midnight."""

    @property
    def is_on(self) -> bool:
        """Whether the goal was achieved today."""
        assert self.goal is not None
        return self.goal.id in self.tracker.achieved
