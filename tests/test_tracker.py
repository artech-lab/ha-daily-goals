"""End-to-end tests on a real Home Assistant core: source states in, achievements and rewards out."""

from datetime import datetime, timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigSubentry, ConfigSubentryData
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.daily_goals.const import DOMAIN, EVENT_GOAL_ACHIEVED, EVENT_PERFECT_DAY

GOALS = [
    ("steps", "Steps", {"source_entity": "sensor.phone_steps", "target": 7500, "reward": "A coffee in the sun"}),
    (
        "sys",
        "Systolic",
        {
            "source_entity": "sensor.bp_systolic",
            "target": 135,
            "direction": "below",
            "complete_with": "dia",
            "points": 5,
        },
    ),
    ("dia", "Diastolic", {"source_entity": "sensor.bp_diastolic", "target": 85, "direction": "below", "points": 5}),
    (
        "hrv",
        "HRV",
        {"source_entity": "sensor.hrv_7_day_average", "target": 40, "daily_reset": "current_value", "decimals": 1},
    ),
]
DATA = {
    "notify_services": ["notify.mobile_app_phone"],
    "persistent_notification": True,
    "notification_images": True,
    "open_on_tap": "/lovelace/health",
    "perfect_day_reward": "Movie night",
}
ACHIEVED = "sensor.daily_goals_achieved"


def local(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 3, day, hour, minute, tzinfo=dt_util.get_default_time_zone())


def make_entry(goals=GOALS) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Daily goals",
        data=DATA,
        subentries_data=[
            ConfigSubentryData(
                data={"notify": True, **data}, subentry_id=goal_id, subentry_type="goal", title=title, unique_id=None
            )
            for goal_id, title, data in goals
        ],
    )


@pytest.fixture
async def setup(hass: HomeAssistant, freezer: FrozenDateTimeFactory):
    await hass.config.async_set_time_zone("Europe/Rome")
    freezer.move_to(local(10, 9))
    hass.states.async_set("sensor.hrv_7_day_average", "38.0", {"unit_of_measurement": "ms"})
    notify = async_mock_service(hass, "notify", "mobile_app_phone")
    entry = make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry, notify


async def set_state(hass: HomeAssistant, entity_id: str, state: str, unit: str | None = None) -> None:
    hass.states.async_set(entity_id, state, {"unit_of_measurement": unit} if unit else {})
    await hass.async_block_till_done()


def goal(hass: HomeAssistant, goal_id: str) -> dict:
    return next(g for g in hass.states.get(ACHIEVED).attributes["goals"] if g["id"] == goal_id)


async def test_entities_and_card_data(hass: HomeAssistant, setup) -> None:
    for entity_id in (
        "sensor.daily_goals_achieved",
        "sensor.daily_goals_completion",
        "sensor.daily_goals_streak",
        "sensor.daily_goals_best_streak",
        "sensor.daily_goals_points_today",
        "sensor.daily_goals_total_points",
        "binary_sensor.daily_goals_perfect_day",
        "sensor.daily_goals_steps_progress",
        "binary_sensor.daily_goals_steps_achieved",
        "sensor.daily_goals_hrv_progress",
    ):
        assert hass.states.get(entity_id) is not None, entity_id
    state = hass.states.get(ACHIEVED)
    assert state.state == "0"
    assert state.attributes["total"] == 4
    steps = goal(hass, "steps")
    assert steps["waiting"] and steps["value"] is None and steps["reward"] == "A coffee in the sun"
    hrv = goal(hass, "hrv")
    assert not hrv["waiting"] and hrv["value"] == 38.0 and hrv["progress"] == 95 and hrv["unit"] == "ms"
    assert hass.states.get("sensor.daily_goals_hrv_progress").state == "95"
    assert hass.states.get("sensor.daily_goals_steps_progress").state == "unknown"


async def test_every_goal_has_its_own_device(hass: HomeAssistant, setup, caplog: pytest.LogCaptureFixture) -> None:
    """A device belongs to one subentry: sharing it made recent Home Assistant drop goal entities."""
    entry, _ = setup
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    def subentry_of(device: dr.DeviceEntry) -> str | None:
        if hasattr(device, "config_subentry_id"):  # Home Assistant 2026.10+
            return device.config_subentry_id
        return next(iter(device.config_entries_subentries[entry.entry_id]))

    entities = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    assert len(entities) == 7 + 2 * len(GOALS)
    for entity in entities:
        assert hass.states.get(entity.entity_id) is not None, entity.entity_id

    devices = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    main = next(d for d in devices if (DOMAIN, entry.entry_id) in d.identifiers)
    assert subentry_of(main) is None
    for goal_id, title, _ in GOALS:
        device = next(d for d in devices if (DOMAIN, f"{entry.entry_id}_{goal_id}") in d.identifiers)
        assert device.name == title
        assert device.via_device_id == main.id
        assert subentry_of(device) == goal_id
    assert len(devices) == 1 + len(GOALS)

    by_device = {d.id: subentry_of(d) for d in devices}
    for entity in entities:
        assert by_device[entity.device_id] == entity.config_subentry_id, entity.entity_id
    assert "different config subentry" not in caplog.text


async def test_goal_achieved_notifies_once_with_reward(hass: HomeAssistant, setup) -> None:
    _, notify = setup
    events = async_capture_events(hass, EVENT_GOAL_ACHIEVED)
    await set_state(hass, "sensor.phone_steps", "5000", "steps")
    assert hass.states.get("sensor.daily_goals_steps_progress").state == "67"
    assert not notify
    await set_state(hass, "sensor.phone_steps", "7800", "steps")
    await set_state(hass, "sensor.phone_steps", "9100", "steps")
    assert len(notify) == 1
    call = notify[0].data
    assert call["title"] == "🏆 Goal achieved: Steps!"
    assert "7,800 steps — target of 7,500 steps reached." in call["message"]
    assert "A coffee in the sun" in call["message"] and "+10 points" in call["message"]
    assert call["data"]["clickAction"] == "/lovelace/health" and call["data"]["image"].startswith("https://")
    assert hass.states.get("binary_sensor.daily_goals_steps_achieved").state == "on"
    assert hass.states.get("sensor.daily_goals_points_today").state == "10"
    assert hass.states.get("sensor.daily_goals_total_points").state == "10"
    assert [e.data["goal"] for e in events] == ["Steps"]


async def test_linked_goals_complete_together(hass: HomeAssistant, setup) -> None:
    _, notify = setup
    await set_state(hass, "sensor.bp_systolic", "128", "mmHg")
    assert hass.states.get("binary_sensor.daily_goals_systolic_achieved").state == "off"
    await set_state(hass, "sensor.bp_diastolic", "91", "mmHg")
    assert not notify
    await set_state(hass, "sensor.bp_diastolic", "82", "mmHg")
    assert hass.states.get("binary_sensor.daily_goals_systolic_achieved").state == "on"
    assert hass.states.get("binary_sensor.daily_goals_diastolic_achieved").state == "on"
    assert len(notify) == 1
    assert notify[0].data["title"] == "🏆 Goal achieved: Systolic + Diastolic!"
    assert "within the limit of 135 mmHg" in notify[0].data["message"]
    assert "+10 points" in notify[0].data["message"]


async def test_perfect_day_streak_and_midnight(hass: HomeAssistant, setup, freezer: FrozenDateTimeFactory) -> None:
    _, notify = setup
    perfect = async_capture_events(hass, EVENT_PERFECT_DAY)
    await set_state(hass, "sensor.phone_steps", "8000", "steps")
    await set_state(hass, "sensor.bp_systolic", "120", "mmHg")
    await set_state(hass, "sensor.bp_diastolic", "80", "mmHg")
    await set_state(hass, "sensor.hrv_7_day_average", "41.5", "ms")
    assert hass.states.get("binary_sensor.daily_goals_perfect_day").state == "on"
    assert hass.states.get("sensor.daily_goals_streak").state == "1"
    assert hass.states.get("sensor.daily_goals_completion").state == "100"
    assert len(perfect) == 1 and perfect[0].data["reward"] == "Movie night" and not perfect[0].data["silent"]
    assert notify[-1].data["title"] == "🌟 Perfect day!"
    assert "Movie night" in notify[-1].data["message"]
    sent = len(notify)

    # Midnight: a new day. Steps still show yesterday's value: they wait for a new one.
    freezer.move_to(local(11, 0))
    async_fire_time_changed(hass, local(11, 0))
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.daily_goals_perfect_day").state == "off"
    assert hass.states.get("sensor.daily_goals_streak").state == "1"
    assert goal(hass, "steps")["waiting"]
    # The 7-day average is still above the target: achieved at once, silently.
    assert goal(hass, "hrv")["achieved"]
    assert len(notify) == sent
    assert hass.states.get(ACHIEVED).state == "1"

    await set_state(hass, "sensor.phone_steps", "0", "steps")
    await set_state(hass, "sensor.phone_steps", "8200", "steps")
    await set_state(hass, "sensor.bp_systolic", "125", "mmHg")
    await set_state(hass, "sensor.bp_diastolic", "79", "mmHg")
    assert hass.states.get("sensor.daily_goals_streak").state == "2"
    assert "Streak: 2 perfect days in a row." in notify[-1].data["message"]
    assert "New personal best" in notify[-1].data["message"]

    # A day that is not perfect breaks the streak at the next midnight.
    freezer.move_to(local(12, 0))
    async_fire_time_changed(hass, local(12, 0))
    await hass.async_block_till_done()
    assert hass.states.get("sensor.daily_goals_streak").state == "2"
    freezer.move_to(local(13, 0))
    async_fire_time_changed(hass, local(13, 0))
    await hass.async_block_till_done()
    assert hass.states.get("sensor.daily_goals_streak").state == "0"
    assert hass.states.get("sensor.daily_goals_best_streak").state == "2"
    # 30 + 30, then the 7-day average alone on the next two days
    assert hass.states.get("sensor.daily_goals_total_points").state == "80"


async def test_adding_a_goal_revokes_todays_perfect_day(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """A perfect day reached with the goals configured so far does not survive a new goal."""
    await hass.config.async_set_time_zone("Europe/Rome")
    freezer.move_to(local(10, 9))
    async_mock_service(hass, "notify", "mobile_app_phone")
    hass.states.async_set("sensor.phone_steps", "9000")
    entry = make_entry(GOALS[:1])
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.daily_goals_perfect_day").state == "on"
    assert hass.states.get("sensor.daily_goals_streak").state == "1"

    hass.config_entries.async_add_subentry(
        entry,
        ConfigSubentry(
            data={"source_entity": "sensor.hrv_7_day_average", "target": 40},
            subentry_type="goal",
            title="HRV",
            unique_id=None,
        ),
    )
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.daily_goals_perfect_day").state == "off"
    assert hass.states.get("sensor.daily_goals_streak").state == "0"
    assert hass.states.get("sensor.daily_goals_best_streak").state == "0"
    assert hass.states.get("binary_sensor.daily_goals_steps_achieved").state == "on"


async def test_restart_keeps_the_day_without_duplicates(hass: HomeAssistant, setup) -> None:
    entry, notify = setup
    await set_state(hass, "sensor.phone_steps", "8000", "steps")
    assert len(notify) == 1
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.daily_goals_steps_achieved").state == "on"
    # The source comes back after the restart with the same value: not a new reading.
    await set_state(hass, "sensor.phone_steps", STATE_UNAVAILABLE)
    await set_state(hass, "sensor.phone_steps", "8000", "steps")
    assert len(notify) == 1
    assert goal(hass, "steps")["value"] == 8000
    assert hass.states.get("sensor.daily_goals_total_points").state == "10"


async def test_restored_state_is_not_a_new_reading(hass: HomeAssistant, setup, freezer) -> None:
    _entry, _notify = setup
    await set_state(hass, "sensor.bp_diastolic", "80", "mmHg")
    freezer.move_to(local(11, 0))
    async_fire_time_changed(hass, local(11, 0))
    await hass.async_block_till_done()
    assert goal(hass, "dia")["waiting"]
    await set_state(hass, "sensor.bp_diastolic", STATE_UNAVAILABLE)
    await set_state(hass, "sensor.bp_diastolic", "80", "mmHg")
    assert goal(hass, "dia")["waiting"]
    await set_state(hass, "sensor.bp_diastolic", "78", "mmHg")
    assert goal(hass, "dia")["value"] == 78


async def test_current_value_back_from_unavailable_is_silent(hass: HomeAssistant, setup) -> None:
    _, notify = setup
    events = async_capture_events(hass, EVENT_GOAL_ACHIEVED)
    await set_state(hass, "sensor.hrv_7_day_average", STATE_UNAVAILABLE)
    await set_state(hass, "sensor.hrv_7_day_average", "45", "ms")
    assert goal(hass, "hrv")["achieved"]
    assert not notify
    assert events[0].data["silent"]


async def test_italian_notification(hass: HomeAssistant, setup) -> None:
    _, notify = setup
    hass.config.language = "it"
    await set_state(hass, "sensor.phone_steps", "12345", "passi")
    assert notify[0].data["title"] == "🏆 Obiettivo raggiunto: Steps!"
    assert "12.345 passi — traguardo di 7500 passi raggiunto." in notify[0].data["message"]
    assert "Il tuo premio: A coffee in the sun" in notify[0].data["message"]


async def test_set_statistics_action(hass: HomeAssistant, setup) -> None:
    await hass.services.async_call(
        DOMAIN,
        "set_statistics",
        {"streak": 12, "total_points": 2450},
        target={"entity_id": "sensor.daily_goals_streak"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get("sensor.daily_goals_streak").state == "12"
    assert hass.states.get("sensor.daily_goals_best_streak").state == "12"
    assert hass.states.get("sensor.daily_goals_total_points").state == "2450"


async def test_missed_midnight_while_stopped(hass: HomeAssistant, setup, freezer) -> None:
    entry, _ = setup
    for entity_id, value in (
        ("sensor.phone_steps", "9000"),
        ("sensor.bp_systolic", "120"),
        ("sensor.bp_diastolic", "80"),
        ("sensor.hrv_7_day_average", "45"),
    ):
        await set_state(hass, entity_id, value)
    assert hass.states.get("sensor.daily_goals_streak").state == "1"
    await hass.config_entries.async_unload(entry.entry_id)
    freezer.move_to(local(12, 8))  # two days later
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.daily_goals_streak").state == "0"
    assert hass.states.get("sensor.daily_goals_best_streak").state == "1"


async def test_unload(hass: HomeAssistant, setup) -> None:
    entry, _ = setup
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.now() + timedelta(days=1))
