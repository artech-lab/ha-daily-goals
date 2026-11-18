"""Config flow, options flow and the goal subentry flow."""

from homeassistant import config_entries
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.daily_goals.const import DOMAIN


async def test_user_flow(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "Daily goals", "persistent_notification": True, "notification_images": False}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Daily goals"
    assert result["data"] == {
        "persistent_notification": True,
        "notification_images": False,
        "notify_services": [],
        "open_on_tap": "",
        "perfect_day_reward": "",
    }
    # Same name twice: aborted.
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"name": "daily goals"})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, title="Daily goals", data={"perfect_day_reward": "Pizza"})
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"notify_services": ["notify.mobile_app_phone"], "persistent_notification": False, "notification_images": True},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["notify_services"] == ["notify.mobile_app_phone"]
    assert entry.options["perfect_day_reward"] == ""  # cleared in the form


async def test_add_and_edit_goals(hass: HomeAssistant) -> None:
    hass.states.async_set("sensor.phone_steps", "120", {"friendly_name": "Phone steps", "unit_of_measurement": "steps"})
    entry = MockConfigEntry(domain=DOMAIN, title="Daily goals", data={})
    entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init((entry.entry_id, "goal"), context={"source": "user"})
    assert result["type"] is FlowResultType.FORM
    assert "complete_with" not in {str(k) for k in result["data_schema"].schema}
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            "source_entity": "sensor.phone_steps",
            "target": 7500,
            "direction": "above",
            "daily_reset": "new_value",
            "reward_section": {"points": 15, "reward": "A coffee", "notify": True},
            "appearance": {"icon": "mdi:walk", "decimals": 0},
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    steps_id, steps = next(iter(entry.subentries.items()))
    assert steps.title == "Phone steps"  # the name of the sensor by default
    assert steps.data == {
        "source_entity": "sensor.phone_steps",
        "target": 7500.0,
        "direction": "above",
        "daily_reset": "new_value",
        "points": 15,
        "reward": "A coffee",
        "notify": True,
        "icon": "mdi:walk",
        "decimals": 0,
    }

    # A second goal: can be linked to the first; names must differ; a target to reach must be > 0.
    result = await hass.config_entries.subentries.async_init((entry.entry_id, "goal"), context={"source": "user"})
    assert "complete_with" in {str(k) for k in result["data_schema"].schema}
    user_input = {
        "source_entity": "sensor.phone_steps",
        "name": "phone STEPS",
        "target": 0,
        "direction": "above",
        "daily_reset": "new_value",
        "complete_with": steps_id,
        "reward_section": {"points": 0, "notify": False},
        "appearance": {"decimals": 0},
    }
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], user_input)
    assert result["errors"] == {"name": "name_exists"}
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {**user_input, "name": "Walk"})
    assert result["errors"] == {"target": "target_not_positive"}
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {**user_input, "name": "Walk", "target": 5}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    walk = next(s for s in entry.subentries.values() if s.title == "Walk")
    assert walk.data["complete_with"] == steps_id and walk.data["points"] == 0 and walk.data["notify"] is False

    # Edit the first goal: current values are shown, cleared fields are removed.
    result = await entry.start_subentry_reconfigure_flow(hass, steps_id)
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "reconfigure"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            "source_entity": "sensor.phone_steps",
            "name": "Steps",
            "target": 8000,
            "direction": "above",
            "daily_reset": "new_value",
            "reward_section": {"points": 10, "notify": True},
            "appearance": {"decimals": 0},
        },
    )
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "reconfigure_successful"
    steps = entry.subentries[steps_id]
    assert steps.title == "Steps" and steps.data["target"] == 8000 and "reward" not in steps.data


async def test_goal_entities_follow_the_subentries(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Daily goals",
        data={},
        subentries_data=[
            ConfigSubentryData(
                data={"source_entity": "sensor.a", "target": 1},
                subentry_id="a",
                subentry_type="goal",
                title="Water",
                unique_id=None,
            )
        ],
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.daily_goals_water_progress") is not None
    hass.config_entries.async_remove_subentry(entry, "a")
    await hass.async_block_till_done()
    assert hass.states.get("sensor.daily_goals_water_progress") is None
    assert hass.states.get(sensor := "sensor.daily_goals_achieved") is not None, sensor
    assert hass.states.get("sensor.daily_goals_achieved").attributes["total"] == 0


async def test_action_is_described(hass: HomeAssistant) -> None:
    from homeassistant.helpers.service import async_get_all_descriptions
    from homeassistant.setup import async_setup_component

    assert await async_setup_component(hass, DOMAIN, {})
    descriptions = await async_get_all_descriptions(hass)
    fields = descriptions[DOMAIN]["set_statistics"]["fields"]
    assert set(fields) == {"streak", "best_streak", "total_points"}
