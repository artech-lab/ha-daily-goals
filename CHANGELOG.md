# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

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
