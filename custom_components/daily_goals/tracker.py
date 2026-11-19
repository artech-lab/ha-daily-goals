# SPDX-License-Identifier: GPL-3.0-or-later
"""GoalTracker: source values -> goals achieved today -> points, streak, rewards and notifications."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import date, datetime
import logging
from typing import Any

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util, slugify

from .const import (
    CONF_NOTIFICATION_IMAGES,
    CONF_NOTIFY_SERVICES,
    CONF_OPEN_ON_TAP,
    CONF_PERFECT_DAY_REWARD,
    CONF_PERSISTENT_NOTIFICATION,
    DOMAIN,
    EVENT_GOAL_ACHIEVED,
    EVENT_PERFECT_DAY,
    STORAGE_VERSION,
    SUBENTRY_GOAL,
    DailyReset,
    Direction,
)
from .goals import (
    Goal,
    effective,
    format_number,
    is_met,
    link_groups,
    new_milestone,
    notification_image,
    numeric,
    progress as goal_progress,
)
from .messages import text

_LOGGER = logging.getLogger(__name__)

PERFECT_KEY = "perfect_day"


class GoalTracker:
    """Follows the source of every goal and keeps the score of the day."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, version: str) -> None:
        """Initialise from the config entry and its goal subentries."""
        self.hass = hass
        self.entry = entry
        self.version = version
        self.slug = slugify(entry.title) or DOMAIN
        self.signal = f"{DOMAIN}_{entry.entry_id}"
        self.goals: dict[str, Goal] = {
            subentry_id: Goal.from_subentry(subentry_id, subentry.title, subentry.data)
            for subentry_id, subentry in entry.subentries.items()
            if subentry.subentry_type == SUBENTRY_GOAL
        }
        self.groups = link_groups({goal.id: goal.link for goal in self.goals.values()})
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}")
        self._unsubs: list[Callable[[], None]] = []
        self._tasks: set[Any] = set()
        # State of the day (persisted)
        self.day: date | None = None
        self.achieved: set[str] = set()  # goals achieved at least once today
        self.perfect = False
        self.reported: dict[str, float] = {}  # "new value" goals: value reported today
        self.last_seen: dict[str, float] = {}  # last valid value of each source, to spot restored states
        # Long-term statistics (persisted)
        self.streak = 0
        self.best_streak = 0
        self.best_before_perfect = 0  # best streak before today's perfect day, to revoke it
        self.total_points = 0

    # ------------------------------------------------------------ configuration
    @property
    def config(self) -> dict[str, Any]:
        """Setup data overridden by the options."""
        return {**self.entry.data, **self.entry.options}

    @property
    def language(self) -> str:
        """Language of the notifications."""
        return self.hass.config.language

    def unit(self, goal: Goal) -> str:
        """Unit of a goal: its own, or the one of its source."""
        if goal.unit:
            return goal.unit
        state = self.hass.states.get(goal.source)
        return str((state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) if state else None) or "")

    def value(self, goal: Goal) -> float | None:
        """The value that counts today (None while a "new value" goal waits for today's reading)."""
        if goal.daily_reset is DailyReset.NEW_VALUE:
            return self.reported.get(goal.id)
        state = self.hass.states.get(goal.source)
        return numeric(state.state if state else None)

    def progress(self, goal: Goal) -> float | None:
        """Live progress towards the target, 0-1."""
        return goal_progress(self.value(goal), goal.target, goal.direction)

    def waiting(self, goal: Goal) -> bool:
        """Whether a "new value" goal has no reading today yet."""
        return goal.daily_reset is DailyReset.NEW_VALUE and goal.id not in self.reported

    @property
    def points_today(self) -> int:
        """Points of the goals achieved today."""
        return sum(self.goals[goal_id].points for goal_id in self.achieved if goal_id in self.goals)

    @property
    def completion(self) -> int:
        """Average progress of the day, 0-100 (an achieved goal counts as complete)."""
        if not self.goals:
            return 0
        total = 0.0
        for goal in self.goals.values():
            total += 1.0 if goal.id in self.achieved else (self.progress(goal) or 0.0)
        return round(100 * total / len(self.goals))

    # ------------------------------------------------------------ lifecycle
    async def async_load(self) -> None:
        """Restore the state of the day and the statistics."""
        data = await self._store.async_load() or {}
        try:
            self.day = date.fromisoformat(data["day"]) if data.get("day") else None
        except ValueError:
            self.day = None
        self.achieved = {goal_id for goal_id in data.get("achieved", []) if goal_id in self.goals}
        self.perfect = bool(data.get("perfect", False))
        self.reported = {k: float(v) for k, v in data.get("reported", {}).items() if k in self.goals}
        self.last_seen = {k: float(v) for k, v in data.get("last_seen", {}).items() if k in self.goals}
        self.streak = int(data.get("streak", 0))
        self.best_streak = int(data.get("best_streak", 0))
        self.best_before_perfect = int(data.get("best_before_perfect", self.best_streak))
        self.total_points = int(data.get("total_points", 0))

    @callback
    def async_start(self) -> None:
        """Catch up with the date and the sources, then follow them."""
        today = dt_util.now().date()
        if self.day != today:
            self._rollover(today)
        elif self.perfect and not self.achieved >= set(self.goals):
            # Goals added after today's perfect day: the day is no longer perfect. The goals
            # already achieved and their points stay.
            self.perfect = False
            self.streak = max(0, self.streak - 1)
            self.best_streak = self.best_before_perfect
            persistent_notification.async_dismiss(self.hass, self._notification_id(PERFECT_KEY))
        silent: set[str] = set()
        for goal in self.goals.values():
            state = self.hass.states.get(goal.source)
            if state is not None and self._update(goal, None, state):
                silent.add(goal.id)
        self._evaluate(silent)
        sources = sorted({goal.source for goal in self.goals.values()})
        if sources:
            self._unsubs.append(async_track_state_change_event(self.hass, sources, self._on_source))
        self._unsubs.append(async_track_time_change(self.hass, self._on_midnight, hour=0, minute=0, second=0))
        self._changed()

    async def async_stop(self) -> None:
        """Stop listening and write the state."""
        while self._unsubs:
            self._unsubs.pop()()
        await self._store.async_save(self._data())

    def _data(self) -> dict[str, Any]:
        return {
            "day": self.day.isoformat() if self.day else None,
            "achieved": sorted(self.achieved),
            "perfect": self.perfect,
            "reported": self.reported,
            "last_seen": self.last_seen,
            "streak": self.streak,
            "best_streak": self.best_streak,
            "best_before_perfect": self.best_before_perfect,
            "total_points": self.total_points,
        }

    def _save(self) -> None:
        self._store.async_delay_save(self._data, 1)

    def _changed(self) -> None:
        self._save()
        async_dispatcher_send(self.hass, self.signal)

    # ------------------------------------------------------------ day
    @callback
    def _on_midnight(self, now: datetime) -> None:
        self._rollover(dt_util.as_local(now).date())
        self._changed()

    def _rollover(self, today: date) -> None:
        """Start a new day: the streak survives only if yesterday was perfect."""
        if self.day is not None and not (self.perfect and (today - self.day).days == 1):
            self.streak = 0
        self.day = today
        self.achieved = set()
        self.perfect = False
        self.reported = {}
        for key in [*self.goals, PERFECT_KEY]:
            persistent_notification.async_dismiss(self.hass, self._notification_id(key))
        # Goals already met by their current value count at once, without a notification.
        self._evaluate(silent=set(self.goals))

    # ------------------------------------------------------------ sources
    @callback
    def _on_source(self, event: Event[EventStateChangedData]) -> None:
        entity_id = event.data["entity_id"]
        silent: set[str] = set()
        for goal in self.goals.values():
            if goal.source == entity_id and self._update(goal, event.data["old_state"], event.data["new_state"]):
                silent.add(goal.id)
        self._evaluate(silent)
        self._changed()

    def _update(self, goal: Goal, old_state: State | None, new_state: State | None) -> bool:
        """Take a new state of the source. True when a resulting achievement must stay silent."""
        value = numeric(new_state.state if new_state else None)
        old_value = numeric(old_state.state if old_state else None)
        if value is None:
            return True
        previous = old_value if old_value is not None else self.last_seen.get(goal.id)
        self.last_seen[goal.id] = value
        if goal.daily_reset is DailyReset.CURRENT_VALUE:
            # Back from unavailable or restored at startup: not a fresh achievement.
            return old_value is None
        # "New value": a reading counts when the value differs from the last one seen, so a
        # state restored at startup (or after the source was unavailable) is not a new reading.
        if value != previous:
            self.reported[goal.id] = value
        return False

    # ------------------------------------------------------------ achievements
    def _evaluate(self, silent: set[str]) -> None:
        """Latch the goals achieved now; award points, fire events, notify."""
        met = {goal.id: is_met(self.value(goal), goal.target, goal.direction) for goal in self.goals.values()}
        newly = [goal_id for goal_id, ok in effective(met, self.groups).items() if ok and goal_id not in self.achieved]
        if not newly:
            return
        for goal_id in newly:
            goal = self.goals[goal_id]
            self.achieved.add(goal_id)
            self.total_points += goal.points
            self.hass.bus.async_fire(
                EVENT_GOAL_ACHIEVED,
                {
                    "entry_id": self.entry.entry_id,
                    "name": self.entry.title,
                    "goal_id": goal_id,
                    "goal": goal.name,
                    "value": self.value(goal),
                    "target": goal.target,
                    "unit": self.unit(goal),
                    "points": goal.points,
                    "reward": goal.reward,
                    "silent": goal_id in silent,
                },
            )
        # One notification per group of linked goals.
        done: set[frozenset[str]] = set()
        for goal_id in newly:
            group = self.groups[goal_id]
            if group in done:
                continue
            done.add(group)
            members = [self.goals[g] for g in self.goals if g in group and g in newly]
            if all(m.id in silent for m in members) or not any(m.notify for m in members):
                continue
            self._notify_goal(members)

        if self.goals and not self.perfect and self.achieved >= set(self.goals):
            self.perfect = True
            self.best_before_perfect = self.best_streak
            self.streak += 1
            record = self.streak > self.best_streak and self.streak > 1
            self.best_streak = max(self.best_streak, self.streak)
            reward = self.config.get(CONF_PERFECT_DAY_REWARD) or ""
            quiet = all(goal_id in silent for goal_id in newly)
            self.hass.bus.async_fire(
                EVENT_PERFECT_DAY,
                {
                    "entry_id": self.entry.entry_id,
                    "name": self.entry.title,
                    "streak": self.streak,
                    "best_streak": self.best_streak,
                    "points_today": self.points_today,
                    "reward": reward,
                    "silent": quiet,
                },
            )
            if not quiet:
                self._notify_perfect(record, reward)

    # ------------------------------------------------------------ notifications
    def _fmt(self, goal: Goal, value: float | None) -> str:
        if value is None:
            return "–"
        return f"{format_number(value, goal.decimals, self.language)} {self.unit(goal)}".strip()

    def _notify_goal(self, members: list[Goal]) -> None:
        lang = self.language
        lines = [
            text(
                lang,
                "goal_below" if goal.direction is Direction.BELOW else "goal_above",
                name=goal.name,
                value=self._fmt(goal, self.value(goal)),
                target=self._fmt(goal, goal.target),
            )
            for goal in members
        ]
        lines += [text(lang, "reward", reward=goal.reward) for goal in members if goal.reward]
        points = sum(goal.points for goal in members)
        lines.append(text(lang, "closing_points", points=points) if points else text(lang, "closing"))
        title = text(lang, "goal_title", name=" + ".join(goal.name for goal in members))
        key = min(self.groups[members[0].id])
        self._send(key, title, lines, list(self.goals).index(members[0].id))

    def _notify_perfect(self, record: bool, reward: str) -> None:
        lang = self.language
        lines = [text(lang, "perfect_body", count=len(self.goals))]
        lines.append(text(lang, "streak", streak=self.streak) if self.streak > 1 else text(lang, "streak_first"))
        if new_milestone(self.streak):
            lines.append(text(lang, "milestone", streak=self.streak))
        if record:
            lines.append(text(lang, "record"))
        if reward:
            lines.append(text(lang, "reward", reward=reward))
        self._send(PERFECT_KEY, text(lang, "perfect_title"), lines, len(self.goals))

    def _notification_id(self, key: str) -> str:
        return f"{DOMAIN}_{self.entry.entry_id}_{key}"

    def _send(self, key: str, title: str, lines: Iterable[str], image_offset: int) -> None:
        config = self.config
        message = "\n".join(lines)
        if config.get(CONF_PERSISTENT_NOTIFICATION, True):
            persistent_notification.async_create(self.hass, message, title, self._notification_id(key))
        services = config.get(CONF_NOTIFY_SERVICES) or []
        if not services:
            return
        extra: dict[str, Any] = {
            "tag": f"{DOMAIN}_{self.slug}_{key}",
            "group": f"{DOMAIN}_{self.slug}",
            "channel": text(self.language, "channel"),
            "notification_icon": "mdi:trophy",
        }
        if config.get(CONF_NOTIFICATION_IMAGES, True):
            extra["image"] = notification_image(dt_util.now().timetuple().tm_yday, image_offset)
        if url := (config.get(CONF_OPEN_ON_TAP) or "").strip():
            extra["clickAction"] = url  # Android
            extra["url"] = url  # iOS
        for service in services:
            domain, _, name = service.partition(".")
            if not name:
                domain, name = "notify", domain
            data: dict[str, Any] = {"title": title, "message": message}
            # Only the companion app understands images, tags and channels.
            if domain == "notify" and name.startswith("mobile_app_"):
                data["data"] = extra
            task = self.hass.async_create_background_task(
                self._async_call(domain, name, data), f"{DOMAIN} notify {service}"
            )
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

    async def _async_call(self, domain: str, service: str, data: dict[str, Any]) -> None:
        try:
            await self.hass.services.async_call(domain, service, data, blocking=True)
        except (HomeAssistantError, ValueError) as err:
            _LOGGER.warning("Notification through %s.%s failed: %s", domain, service, err)

    # ------------------------------------------------------------ actions
    def set_statistics(
        self, streak: int | None = None, best_streak: int | None = None, total_points: int | None = None
    ) -> None:
        """Set the statistics by hand (to carry them over from another setup)."""
        if streak is not None:
            self.streak = streak
        if best_streak is not None:
            self.best_streak = best_streak
        if total_points is not None:
            self.total_points = total_points
        self.best_streak = max(self.best_streak, self.streak)
        self._changed()

    # ------------------------------------------------------------ card and diagnostics
    def card_data(self) -> list[dict[str, Any]]:
        """Everything the card shows about each goal, in the order they were added."""
        out = []
        for goal in self.goals.values():
            value = self.value(goal)
            live = self.progress(goal)
            out.append(
                {
                    "id": goal.id,
                    "name": goal.name,
                    "icon": goal.icon,
                    "color": list(goal.color) if goal.color else None,
                    "unit": self.unit(goal),
                    "decimals": goal.decimals,
                    "target": goal.target,
                    "direction": goal.direction.value,
                    "value": value,
                    "progress": None if live is None else round(100 * live),
                    "achieved": goal.id in self.achieved,
                    "waiting": self.waiting(goal),
                    "waiting_text": goal.waiting_text,
                    "points": goal.points,
                    "reward": goal.reward,
                    "source": goal.source,
                }
            )
        return out

    def diagnostics(self) -> dict[str, Any]:
        """State for the diagnostics download (no notification targets)."""
        return {
            "version": self.version,
            **self._data(),
            "groups": sorted(sorted(group) for group in set(self.groups.values()) if len(group) > 1),
            "goals": [
                {
                    "id": goal.id,
                    "direction": goal.direction.value,
                    "daily_reset": goal.daily_reset.value,
                    "target": goal.target,
                    "value": self.value(goal),
                    "source_state": (state.state if (state := self.hass.states.get(goal.source)) else None),
                    "achieved": goal.id in self.achieved,
                }
                for goal in self.goals.values()
            ],
        }
