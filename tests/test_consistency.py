"""Guards that keep the package easy to maintain."""

import json
from pathlib import Path
import re

from custom_components.daily_goals.binary_sensor import ACHIEVED, PERFECT_DAY
from custom_components.daily_goals.const import DailyReset, Direction
from custom_components.daily_goals.messages import MESSAGES
from custom_components.daily_goals.sensor import PROGRESS, SENSORS

ROOT = Path(__file__).parents[1] / "custom_components" / "daily_goals"
CARD = ROOT / "frontend" / "daily-goals-card.js"
PLATFORM_KEYS = {
    "sensor": {d.key for d in SENSORS} | {PROGRESS.key},
    "binary_sensor": {PERFECT_DAY.key, ACHIEVED.key},
}


def _keys(node, prefix=""):
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _keys(value, f"{prefix}.{key}")
    else:
        yield prefix


def _json(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def test_integration_translations_have_same_keys() -> None:
    assert set(_keys(_json("translations/en.json"))) == set(_keys(_json("translations/it.json")))


def test_placeholders_match() -> None:
    english, italian = _json("translations/en.json"), _json("translations/it.json")
    for key in _keys(english):
        en_value, it_value = english, italian
        for part in key.strip(".").split("."):
            en_value, it_value = en_value[part], it_value[part]
        assert set(re.findall(r"\{\w+\}", en_value)) == set(re.findall(r"\{\w+\}", it_value)), key


def test_every_entity_has_a_name_and_an_icon() -> None:
    names, icons = _json("translations/en.json")["entity"], _json("icons.json")["entity"]
    for platform, keys in PLATFORM_KEYS.items():
        assert set(names[platform]) == keys, platform
        assert set(icons[platform]) == keys, platform


def test_selectors_are_translated() -> None:
    selectors = _json("translations/en.json")["selector"]
    assert set(selectors["direction"]["options"]) == {d.value for d in Direction}
    assert set(selectors["daily_reset"]["options"]) == {r.value for r in DailyReset}


def test_card_translations_have_same_keys() -> None:
    english, italian = re.search(
        r"const STRINGS = \{\n  en: \{(.*?)\n  \},\n  it: \{(.*?)\n  \}\n\};", CARD.read_text(encoding="utf-8"), re.S
    ).groups()
    keys = [set(re.findall(r"^    (\w+):", block, re.M)) for block in (english, italian)]
    assert keys[0] and keys[0] == keys[1]


def test_card_siblings_exist() -> None:
    siblings = re.search(r"const SIBLINGS = \{(.*?)\n\};", CARD.read_text(encoding="utf-8"), re.S).group(1)
    for key in re.findall(r"^  (\w+):", siblings, re.M):
        assert key in PLATFORM_KEYS["sensor"], key


def test_notification_texts_have_same_keys() -> None:
    assert set(MESSAGES["en"]) == set(MESSAGES["it"])
    for key, value in MESSAGES["en"].items():
        assert set(re.findall(r"\{\w+\}", value)) == set(re.findall(r"\{\w+\}", MESSAGES["it"][key])), key


def test_version_lives_only_in_the_manifest() -> None:
    version = _json("manifest.json")["version"]
    assert re.fullmatch(r"\d+\.\d+\.\d+", version)
    for path in [*ROOT.glob("*.py"), CARD]:
        assert version not in path.read_text(encoding="utf-8"), f"hard-coded version in {path.name}"
