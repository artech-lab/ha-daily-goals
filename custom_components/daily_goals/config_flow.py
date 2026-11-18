# SPDX-License-Identifier: GPL-3.0-or-later
"""Config flow (notifications and rewards), options flow, and one subentry flow per goal."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers import selector
from homeassistant.util import slugify
import voluptuous as vol

from .const import (
    CONF_COLOR,
    CONF_DAILY_RESET,
    CONF_DECIMALS,
    CONF_DIRECTION,
    CONF_ICON,
    CONF_LINK,
    CONF_NOTIFICATION_IMAGES,
    CONF_NOTIFY,
    CONF_NOTIFY_SERVICES,
    CONF_OPEN_ON_TAP,
    CONF_PERFECT_DAY_REWARD,
    CONF_PERSISTENT_NOTIFICATION,
    CONF_POINTS,
    CONF_REWARD,
    CONF_SOURCE,
    CONF_TARGET,
    CONF_UNIT,
    CONF_WAITING_TEXT,
    DEFAULT_NAME,
    DEFAULT_POINTS,
    DOMAIN,
    MAX_DECIMALS,
    MAX_POINTS,
    SECTION_APPEARANCE,
    SECTION_REWARD,
    SOURCE_DOMAINS,
    SUBENTRY_GOAL,
    DailyReset,
    Direction,
)

APPEARANCE_KEYS = (CONF_ICON, CONF_COLOR, CONF_UNIT, CONF_DECIMALS, CONF_WAITING_TEXT)
REWARD_KEYS = (CONF_POINTS, CONF_REWARD, CONF_NOTIFY)


def _suggested(current: dict[str, Any], key: str) -> dict[str, Any]:
    return {"suggested_value": current.get(key)}


def _box(minimum: float, maximum: float, step: float | str = 1) -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(min=minimum, max=maximum, step=step, mode=selector.NumberSelectorMode.BOX)
    )


def _choice(options: list[str], key: str) -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(options=options, translation_key=key, mode=selector.SelectSelectorMode.LIST)
    )


def _notify_services(hass: HomeAssistant) -> list[str]:
    services = hass.services.async_services_for_domain("notify")
    return sorted(f"notify.{name}" for name in services if name not in ("send_message", "persistent_notification"))


def _notification_fields(hass: HomeAssistant, current: dict[str, Any]) -> dict[Any, Any]:
    """Fields shared by the setup and the options form."""
    return {
        vol.Optional(CONF_NOTIFY_SERVICES, default=current.get(CONF_NOTIFY_SERVICES, [])): selector.SelectSelector(
            selector.SelectSelectorConfig(options=_notify_services(hass), multiple=True, custom_value=True)
        ),
        vol.Required(
            CONF_PERSISTENT_NOTIFICATION, default=current.get(CONF_PERSISTENT_NOTIFICATION, True)
        ): selector.BooleanSelector(),
        vol.Required(
            CONF_NOTIFICATION_IMAGES, default=current.get(CONF_NOTIFICATION_IMAGES, True)
        ): selector.BooleanSelector(),
        vol.Optional(CONF_OPEN_ON_TAP, description=_suggested(current, CONF_OPEN_ON_TAP)): selector.TextSelector(),
        vol.Optional(CONF_PERFECT_DAY_REWARD, description=_suggested(current, CONF_PERFECT_DAY_REWARD)): (
            selector.TextSelector()
        ),
    }


def _clean(user_input: dict[str, Any]) -> dict[str, Any]:
    """An optional text cleared in the form must be cleared in the entry too."""
    user_input.setdefault(CONF_OPEN_ON_TAP, "")
    user_input.setdefault(CONF_PERFECT_DAY_REWARD, "")
    return user_input


class DailyGoalsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Initial setup: a name, the notifications and the perfect-day reward. Goals come next."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Single setup form."""
        if user_input is not None:
            name = (user_input.pop(CONF_NAME, None) or DEFAULT_NAME).strip()
            await self.async_set_unique_id(slugify(name))
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=name, data=_clean(user_input))
        schema = vol.Schema(
            {
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): selector.TextSelector(),
                **_notification_fields(self.hass, {}),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> DailyGoalsOptionsFlow:
        """Return the options flow."""
        return DailyGoalsOptionsFlow()

    @classmethod
    @callback
    def async_get_supported_subentry_types(cls, config_entry: ConfigEntry) -> dict[str, type[ConfigSubentryFlow]]:
        """Goals are subentries: added, changed and removed one by one."""
        return {SUBENTRY_GOAL: GoalSubentryFlow}


class DailyGoalsOptionsFlow(OptionsFlow):
    """Change the notifications and the perfect-day reward."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Single options form."""
        if user_input is not None:
            return self.async_create_entry(data=_clean(user_input))
        current = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(step_id="init", data_schema=vol.Schema(_notification_fields(self.hass, current)))


class GoalSubentryFlow(ConfigSubentryFlow):
    """Add or change one goal."""

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Add a goal."""
        return await self._async_goal_form("user", user_input, None)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Change a goal."""
        return await self._async_goal_form("reconfigure", user_input, self._get_reconfigure_subentry().subentry_id)

    async def _async_goal_form(
        self, step_id: str, user_input: dict[str, Any] | None, goal_id: str | None
    ) -> SubentryFlowResult:
        entry = self._get_entry()
        others = {
            subentry_id: subentry.title
            for subentry_id, subentry in entry.subentries.items()
            if subentry.subentry_type == SUBENTRY_GOAL and subentry_id != goal_id
        }
        errors: dict[str, str] = {}
        if user_input is not None:
            title, data = self._flatten(user_input)
            if title.casefold() in {name.casefold() for name in others.values()}:
                errors[CONF_NAME] = "name_exists"
            elif data[CONF_DIRECTION] == Direction.ABOVE and data[CONF_TARGET] <= 0:
                errors[CONF_TARGET] = "target_not_positive"
            elif goal_id is None:
                return self.async_create_entry(title=title, data=data)
            else:
                return self.async_update_and_abort(entry, self._get_reconfigure_subentry(), title=title, data=data)
            current = user_input
        elif goal_id is not None:
            subentry = self._get_reconfigure_subentry()
            current = self._nest({**subentry.data, CONF_NAME: subentry.title})
        else:
            current = {}
        return self.async_show_form(step_id=step_id, data_schema=self._schema(current, others), errors=errors)

    def _flatten(self, user_input: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """Store the sections flat, without empty values; the name defaults to the source's."""
        flat = {k: v for k, v in user_input.items() if k not in (SECTION_APPEARANCE, SECTION_REWARD)}
        flat.update(user_input.get(SECTION_APPEARANCE) or {})
        flat.update(user_input.get(SECTION_REWARD) or {})
        title = str(flat.pop(CONF_NAME, "") or "").strip()
        if not title:
            state = self.hass.states.get(flat[CONF_SOURCE])
            title = state.name if state else flat[CONF_SOURCE]
        data = {k: v for k, v in flat.items() if v not in (None, "", [])}
        data[CONF_TARGET] = float(data[CONF_TARGET])
        data[CONF_POINTS] = int(data.get(CONF_POINTS, 0))
        data[CONF_NOTIFY] = bool(data.get(CONF_NOTIFY, False))
        if CONF_DECIMALS in data:
            data[CONF_DECIMALS] = int(data[CONF_DECIMALS])
        return title, data

    @staticmethod
    def _nest(flat: dict[str, Any]) -> dict[str, Any]:
        """Stored data -> form values, with the sections."""
        current = {k: v for k, v in flat.items() if k not in APPEARANCE_KEYS + REWARD_KEYS}
        current[SECTION_APPEARANCE] = {k: flat[k] for k in APPEARANCE_KEYS if k in flat}
        current[SECTION_REWARD] = {k: flat[k] for k in REWARD_KEYS if k in flat}
        return current

    def _schema(self, current: dict[str, Any], others: dict[str, str]) -> vol.Schema:
        look = current.get(SECTION_APPEARANCE) or {}
        prize = current.get(SECTION_REWARD) or {}
        fields: dict[Any, Any] = {
            vol.Required(CONF_SOURCE, default=current.get(CONF_SOURCE, vol.UNDEFINED)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=SOURCE_DOMAINS)
            ),
            vol.Optional(CONF_NAME, description=_suggested(current, CONF_NAME)): selector.TextSelector(),
            vol.Required(CONF_TARGET, default=current.get(CONF_TARGET, vol.UNDEFINED)): _box(-1e9, 1e9, "any"),
            vol.Required(CONF_DIRECTION, default=current.get(CONF_DIRECTION, Direction.ABOVE.value)): _choice(
                [d.value for d in Direction], CONF_DIRECTION
            ),
            vol.Required(CONF_DAILY_RESET, default=current.get(CONF_DAILY_RESET, DailyReset.NEW_VALUE.value)): _choice(
                [r.value for r in DailyReset], CONF_DAILY_RESET
            ),
        }
        if others:
            fields[vol.Optional(CONF_LINK, description=_suggested(current, CONF_LINK))] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[selector.SelectOptionDict(value=k, label=v) for k, v in others.items()],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )
        fields[vol.Required(SECTION_REWARD)] = section(
            vol.Schema(
                {
                    vol.Required(CONF_POINTS, default=prize.get(CONF_POINTS, DEFAULT_POINTS)): _box(0, MAX_POINTS),
                    vol.Optional(CONF_REWARD, description=_suggested(prize, CONF_REWARD)): selector.TextSelector(),
                    vol.Required(CONF_NOTIFY, default=prize.get(CONF_NOTIFY, True)): selector.BooleanSelector(),
                }
            ),
            {"collapsed": False},
        )
        fields[vol.Required(SECTION_APPEARANCE)] = section(
            vol.Schema(
                {
                    vol.Optional(CONF_ICON, description=_suggested(look, CONF_ICON)): selector.IconSelector(),
                    vol.Optional(CONF_COLOR, description=_suggested(look, CONF_COLOR)): selector.ColorRGBSelector(),
                    vol.Optional(CONF_UNIT, description=_suggested(look, CONF_UNIT)): selector.TextSelector(),
                    vol.Required(CONF_DECIMALS, default=look.get(CONF_DECIMALS, 0)): _box(0, MAX_DECIMALS),
                    vol.Optional(CONF_WAITING_TEXT, description=_suggested(look, CONF_WAITING_TEXT)): (
                        selector.TextSelector()
                    ),
                }
            ),
            {"collapsed": True},
        )
        return vol.Schema(fields)
