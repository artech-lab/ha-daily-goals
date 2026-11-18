# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project: Daily Goals

Home Assistant custom integration (`custom_components/daily_goals`) that turns any numeric entity into a
daily goal: progress, achievement once a day, points, rewards, perfect days and streaks, notifications
and events. It bundles a dashboard card. Distributed through HACS (category `integration`; from Home
Assistant 2026.11 HACS is built in as the Marketplace).

Answer the maintainer in the language they write in. Code, comments, commit messages, entity IDs and the
README stay in English. User-facing strings exist in English and Italian.

## Commands

```bash
python -m venv .venv && . .venv/bin/activate && pip install -r requirements_test.txt   # once (Python 3.13)
scripts/check.sh                   # everything CI runs: ruff, card syntax, pytest
scripts/check.sh -k midnight       # extra arguments go to pytest
python scripts/screenshots.py      # rebuilds images/*.png and the brand icons (needs playwright, rsvg-convert)
```

`screenshots.py` uses Playwright's Chromium; set `BROWSER_CHANNEL=chrome` to use an installed Chrome.

Slash commands: `/publish` (first publication) and `/release X.Y.Z` (later versions).

## Layout

| Path | Content |
| --- | --- |
| `const.py` | Every constant: config keys, directions, daily reset modes, streak milestones, events |
| `goals.py` | Pure Python: `Goal` (from a subentry), progress and achievement, linked groups, number format, notification pictures |
| `tracker.py` | `GoalTracker`: source states -> value of today -> achievements latched for the day -> points, streak, events, notifications; midnight rollover, restart recovery, storage |
| `messages.py` | Notification texts (en/it) |
| `entity.py`, `sensor.py`, `binary_sensor.py` | Thin entities reading the tracker; they hold no logic |
| `config_flow.py` | Setup form (notifications, perfect-day reward), options form, and the `goal` subentry flow (add and reconfigure, with the sections *Reward* and *Appearance*, stored flat) |
| `services.yaml` | The `set_statistics` action, registered in `__init__.py` on the sensors of the integration |
| `frontend/daily-goals-card.js` | The card: one dependency-free ES module, no build step |
| `translations/en.json`, `it.json` | Integration strings (the card has its own `STRINGS` table) |
| `tests/` | `test_goals.py` (pure), `test_tracker.py` (end to end on a real Home Assistant core: states in, achievements, notifications and events out; midnight with freezegun), `test_config_flow.py`, `test_consistency.py` |
| `scripts/preview.html` | The card with fictional demo values, used for the README images |

## Rules that keep it maintainable

- **One version**: `manifest.json` -> `version`. The integration appends it to the card URL
  (`?v=`), the card reads it from `import.meta.url`. Never hard-code it elsewhere (a test checks).
- **One release step**: pushing a new manifest version to `main` makes the `Release` job of
  `.github/workflows/validate.yml` create the tag and the GitHub release after all checks pass.
- **Goals are config subentries** (type `goal`). Adding, changing or removing one reloads the entry; the
  entities of a goal belong to its subentry, so they disappear with it. A goal ID is its subentry ID.
- **Achievements are latched for the day** and notified once. Silent on purpose: goals met at the
  midnight rollover, and values coming back from `unavailable`/`unknown` or restored at startup. A
  "new value" goal counts a reading only when the value differs from the last one seen (`last_seen`,
  persisted). Keep these rules: they are what prevents duplicate or midnight notifications.
- **Logic only in `goals.py` and `tracker.py`**. The card displays what the integration computes: the
  goals come from the `goals` attribute of the achieved sensor (unrecorded), streak and points from
  sibling entities discovered through the device (`translation_key` -> role in `SIBLINGS`).
- **Translations**: a new string goes in both `en.json` and `it.json`, in both languages of `STRINGS` in
  the card, or in both languages of `messages.py` (tests compare the key sets and the placeholders).
  Entity IDs are always English: `entity.py` sets them from the entry title, the goal name and the
  description key.
- A new entity needs: a description in its platform file, a name in both translation files and an icon
  in `icons.json` (a test checks both) and, if the card shows it, an entry in the card's `SIBLINGS`.
- Options: do not add new ones without a strong reason.
- Notification pictures: only services that answer with an image, without account or key, and without
  third-party characters or brands.
- No personal data in the repository (names, e-mail addresses, entity IDs or device names of a real
  installation). Demo values are fictional; images carry no metadata.
- License: GPL-3.0-or-later. New source files start with `# SPDX-License-Identifier: GPL-3.0-or-later`.
