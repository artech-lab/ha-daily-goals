# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed

- A perfect day reached with the goals configured so far is revoked when more goals are added the same day
  (streak and best streak go back).

## [1.0.1] - 2026-11-19

### Fixed

- Entities disappeared after adding goals on recent Home Assistant versions (2026.10 and later): every goal
  now has its own device, linked to the device of the set of goals. Goal entities are named *Progress* and
  *Achieved* (the goal name is the device name).

### Changed

- CI runs on Python 3.14.

## [1.0.0] - 2026-11-18

First public release.

- Goals from any numeric entity, added one by one from the integration page (config subentries): target,
  direction (reach at least / stay under), what counts after midnight (a new value, or the current value),
  goals that must be completed together.
- Achievements latched for the day; no duplicate notifications after restarts or at midnight.
- Points, rewards per goal and for a perfect day, perfect-day streak with milestones and personal best.
- Notifications to any `notify` action (pictures, tags and tap action on the companion app) and
  persistent notifications dismissed at midnight.
- Events `daily_goals_goal_achieved` and `daily_goals_perfect_day`; action `daily_goals.set_statistics`.
- Bundled `daily-goals-card` dashboard card, loaded automatically, with a visual editor.
- English and Italian.
