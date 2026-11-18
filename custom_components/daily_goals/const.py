# SPDX-License-Identifier: GPL-3.0-or-later
"""Constants for the Daily Goals integration."""

from __future__ import annotations

from enum import StrEnum
from typing import Final

DOMAIN: Final = "daily_goals"
DEFAULT_NAME: Final = "Daily goals"

# Bundled dashboard card
CARD_FILENAME: Final = "daily-goals-card.js"
CARD_URL: Final = f"/{DOMAIN}/{CARD_FILENAME}"

# Config subentry type: one subentry per goal
SUBENTRY_GOAL: Final = "goal"


class Direction(StrEnum):
    """Which side of the target counts as achieved."""

    ABOVE = "above"  # reach at least the target (steps, sleep score)
    BELOW = "below"  # stay at or under the target (blood pressure, resting heart rate)


class DailyReset(StrEnum):
    """Which values count after midnight."""

    NEW_VALUE = "new_value"  # only values the source reports today (counters, measurements, tests)
    CURRENT_VALUE = "current_value"  # the current value, whenever it was reported (averages, trends)


# Entry keys (setup and options)
CONF_NOTIFY_SERVICES: Final = "notify_services"
CONF_PERSISTENT_NOTIFICATION: Final = "persistent_notification"
CONF_NOTIFICATION_IMAGES: Final = "notification_images"
CONF_OPEN_ON_TAP: Final = "open_on_tap"
CONF_PERFECT_DAY_REWARD: Final = "perfect_day_reward"

# Goal subentry keys
CONF_SOURCE: Final = "source_entity"
CONF_TARGET: Final = "target"
CONF_DIRECTION: Final = "direction"
CONF_DAILY_RESET: Final = "daily_reset"
CONF_LINK: Final = "complete_with"
CONF_ICON: Final = "icon"
CONF_COLOR: Final = "color"
CONF_UNIT: Final = "unit"
CONF_DECIMALS: Final = "decimals"
CONF_WAITING_TEXT: Final = "waiting_text"
CONF_POINTS: Final = "points"
CONF_REWARD: Final = "reward"
CONF_NOTIFY: Final = "notify"
# Form sections of the goal subentry (their fields are stored flat)
SECTION_APPEARANCE: Final = "appearance"
SECTION_REWARD: Final = "reward_section"

DEFAULT_POINTS: Final = 10
MAX_POINTS: Final = 1000
MAX_DECIMALS: Final = 2
DEFAULT_ICON: Final = "mdi:target"

# Domains a goal can follow: anything with a numeric state.
SOURCE_DOMAINS: Final = ["sensor", "number", "input_number", "counter"]

# Streak lengths (perfect days in a row) celebrated in the perfect-day notification.
STREAK_MILESTONES: Final = (3, 7, 14, 21, 30, 50, 100, 150, 200, 365)

STORAGE_VERSION: Final = 1

# Events fired on the bus, for automations that hand out real-world rewards.
EVENT_GOAL_ACHIEVED: Final = f"{DOMAIN}_goal_achieved"
EVENT_PERFECT_DAY: Final = f"{DOMAIN}_perfect_day"

SERVICE_SET_STATISTICS: Final = "set_statistics"
ATTR_STREAK: Final = "streak"
ATTR_BEST_STREAK: Final = "best_streak"
ATTR_TOTAL_POINTS: Final = "total_points"
