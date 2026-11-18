# SPDX-License-Identifier: GPL-3.0-or-later
"""Notification texts, in the language of Home Assistant (English fallback).

A notification is built from the lines below; placeholders are filled by
``text()``. Numbers arrive already formatted for the language.
"""

from __future__ import annotations

from typing import Final

MESSAGES: Final[dict[str, dict[str, str]]] = {
    "en": {
        "channel": "Daily goals",
        "goal_title": "🏆 Goal achieved: {name}!",
        "goal_above": "{name}: {value} — target of {target} reached.",
        "goal_below": "{name}: {value} — within the limit of {target}.",
        "reward": "🎁 Your reward: {reward}",
        "closing_points": "+{points} points, keep it up! 🎉",
        "closing": "Keep it up! 🎉",
        "perfect_title": "🌟 Perfect day!",
        "perfect_body": "All {count} goals achieved today.",
        "streak_first": "Day one of a new streak.",
        "streak": "Streak: {streak} perfect days in a row.",
        "milestone": "🔥 {streak}-day milestone!",
        "record": "🏅 New personal best!",
    },
    "it": {
        "channel": "Obiettivi giornalieri",
        "goal_title": "🏆 Obiettivo raggiunto: {name}!",
        "goal_above": "{name}: {value} — traguardo di {target} raggiunto.",
        "goal_below": "{name}: {value} — entro il limite di {target}.",
        "reward": "🎁 Il tuo premio: {reward}",
        "closing_points": "+{points} punti, continua così! 🎉",
        "closing": "Continua così! 🎉",
        "perfect_title": "🌟 Giornata perfetta!",
        "perfect_body": "Tutti i {count} obiettivi raggiunti oggi.",
        "streak_first": "Primo giorno di una nuova serie.",
        "streak": "Serie: {streak} giornate perfette di fila.",
        "milestone": "🔥 Traguardo dei {streak} giorni!",
        "record": "🏅 Nuovo record personale!",
    },
}


def language_code(language: str | None) -> str:
    """The table to use for a Home Assistant language (``it-IT`` -> ``it``)."""
    code = (language or "en").split("-")[0].lower()
    return code if code in MESSAGES else "en"


def text(language: str | None, key: str, **values: object) -> str:
    """One line of a notification."""
    return MESSAGES[language_code(language)][key].format(**values)
