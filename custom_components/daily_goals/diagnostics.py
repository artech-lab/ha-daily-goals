# SPDX-License-Identifier: GPL-3.0-or-later
"""Diagnostics support for Daily Goals."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import DailyGoalsConfigEntry
from .const import CONF_NOTIFY_SERVICES, CONF_OPEN_ON_TAP, CONF_PERFECT_DAY_REWARD, CONF_REWARD


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: DailyGoalsConfigEntry) -> dict[str, Any]:
    """Return diagnostics for a config entry (without notification targets and personal rewards)."""
    redact = {CONF_NOTIFY_SERVICES, CONF_OPEN_ON_TAP, CONF_PERFECT_DAY_REWARD, CONF_REWARD}
    return {
        "config": async_redact_data({**entry.data, **entry.options}, redact),
        "goals": [async_redact_data(dict(subentry.data), redact) for subentry in entry.subentries.values()],
        "tracker": entry.runtime_data.diagnostics(),
    }
