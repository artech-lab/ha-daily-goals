#!/usr/bin/env bash
# Every check CI runs, in one command: lint, format, card syntax, tests.
set -euo pipefail
cd "$(dirname "$0")/.."

# The integration depends on the frontend component: install the frontend
# package pinned by the installed Home Assistant version (no-op when present).
python - <<'PY'
import importlib.util, json, pathlib, subprocess, sys
if importlib.util.find_spec("hass_frontend") is None:
    import homeassistant.components.frontend as frontend
    manifest = json.loads((pathlib.Path(frontend.__file__).parent / "manifest.json").read_text())
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", manifest["requirements"][0]])
PY

ruff check .
ruff format --check .
# The card is an ES module: check its syntax as one.
cp custom_components/daily_goals/frontend/daily-goals-card.js "${TMPDIR:-/tmp}/daily-goals-card.mjs"
node --check "${TMPDIR:-/tmp}/daily-goals-card.mjs"
pytest -q "$@"
