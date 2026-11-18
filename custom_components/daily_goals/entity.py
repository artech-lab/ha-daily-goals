# SPDX-License-Identifier: GPL-3.0-or-later
"""Base entity for Daily Goals."""

from __future__ import annotations

from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.util import slugify

from .const import DOMAIN
from .goals import Goal
from .tracker import GoalTracker


class DailyGoalsEntity(Entity):
    """Common behaviour: one device per entry, English entity IDs, push updates.

    Summary entities have no goal; goal entities carry their goal and belong
    to its subentry, so removing the goal removes them.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self, tracker: GoalTracker, description: EntityDescription, platform: str, goal: Goal | None = None
    ) -> None:
        """Initialise the entity."""
        self.tracker = tracker
        self.goal = goal
        self.entity_description = description
        entry = tracker.entry
        self._attr_translation_key = description.key
        if goal is None:
            self._attr_unique_id = f"{entry.entry_id}_{description.key}"
            # Explicit English object IDs, independent of the UI language.
            self.entity_id = f"{platform}.{tracker.slug}_{description.key}"
        else:
            self._attr_unique_id = f"{entry.entry_id}_{goal.id}_{description.key}"
            self.entity_id = f"{platform}.{tracker.slug}_{slugify(goal.name) or 'goal'}_{description.key}"
            self._attr_translation_placeholders = {"goal": goal.name}
            self._attr_icon = goal.icon if description.key == "progress" else None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Daily Goals",
            model="Daily goals",
            sw_version=tracker.version,
            entry_type=DeviceEntryType.SERVICE,
        )
        self._written: Any = None

    async def async_added_to_hass(self) -> None:
        """Subscribe to tracker updates."""
        self.async_on_remove(async_dispatcher_connect(self.hass, self.tracker.signal, self._on_update))

    @callback
    def _on_update(self) -> None:
        """Write the state only when it actually changed (the tracker notifies often)."""
        current = (self.state, self.extra_state_attributes, self.available)
        if current != self._written:
            self._written = current
            self.async_write_ha_state()
