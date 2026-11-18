# SPDX-License-Identifier: GPL-3.0-or-later
"""Daily Goals: gamified daily goals from any sensor, with rewards, streaks and notifications."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration
import voluptuous as vol

from .const import (
    ATTR_BEST_STREAK,
    ATTR_STREAK,
    ATTR_TOTAL_POINTS,
    CARD_FILENAME,
    CARD_URL,
    DOMAIN,
    SERVICE_SET_STATISTICS,
)
from .tracker import GoalTracker

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type DailyGoalsConfigEntry = ConfigEntry[GoalTracker]

_COUNT = vol.All(vol.Coerce(int), vol.Range(min=0))


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Serve the bundled dashboard card, load it in every dashboard, register the actions.

    The version in ``manifest.json`` is the single source of truth: it is
    appended to the card URL, which busts the browser cache after an update
    and tells the card its own version.
    """
    version = str((await async_get_integration(hass, DOMAIN)).version)
    hass.data[DOMAIN] = version
    card = Path(__file__).parent / "frontend" / CARD_FILENAME
    await hass.http.async_register_static_paths([StaticPathConfig(CARD_URL, str(card), cache_headers=False)])
    add_extra_js_url(hass, f"{CARD_URL}?v={version}")

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_STATISTICS,
        entity_domain=SENSOR_DOMAIN,
        schema={
            vol.Optional(ATTR_STREAK): _COUNT,
            vol.Optional(ATTR_BEST_STREAK): _COUNT,
            vol.Optional(ATTR_TOTAL_POINTS): _COUNT,
        },
        func="async_set_statistics",
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: DailyGoalsConfigEntry) -> bool:
    """Set up a set of goals from a config entry."""
    tracker = GoalTracker(hass, entry, hass.data[DOMAIN])
    await tracker.async_load()
    entry.runtime_data = tracker

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    tracker.async_start()
    # Options and goals (subentries) changed: start again with the new configuration.
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DailyGoalsConfigEntry) -> bool:
    """Unload a config entry."""
    if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.async_stop()
    return unloaded


async def _async_reload(hass: HomeAssistant, entry: DailyGoalsConfigEntry) -> None:
    """Reload when the options or the goals change."""
    await hass.config_entries.async_reload(entry.entry_id)
