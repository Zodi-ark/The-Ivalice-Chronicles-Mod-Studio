"""
Human-readable names for numeric ids, loaded from plain "id|name" files in
data/.

Same idea and same file format as EncounterNames.txt, which came first: a
raw number in a field tells a user nothing, and every one of these lists is
published knowledge that just needed converting from hex to the decimal the
tables actually use.

Three lists live here:

  AbilityEffectNames.txt      Abilities -> Effect, "Effect ID"
  ChargeEffectTypeNames.txt   Abilities -> Unit Animations, "Charge Effect Type"
  AnimationIdNames.txt        Abilities -> Unit Animations, "Animation ID"

All three are editable by the user, all three degrade to "just the number"
if the file is missing or an id isn't in it, and none of them constrain what
can be typed - EffectId in particular legitimately holds -1 (64 vanilla
abilities use it) and values well past the end of the named list, so the
names annotate the field rather than replacing it with a picker.
"""
from __future__ import annotations

from pathlib import Path

from . import paths

EFFECT_NAMES_FILE = "AbilityEffectNames.txt"
CHARGE_EFFECT_NAMES_FILE = "ChargeEffectTypeNames.txt"
ANIMATION_NAMES_FILE = "AnimationIdNames.txt"

_cache: dict = {}


def load_name_file(path: Path) -> dict:
    """
    {id: name} from an "id|name" file. Blank lines and # comments ignored.

    Deliberately forgiving on every axis - missing file, unreadable file,
    malformed line, empty name. These lists are a nicety layered on top of a
    field that works fine without them, so a bad line should cost that one
    line and nothing else.
    """
    names: dict = {}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return names
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("|")
        if not sep:
            continue
        value = value.strip()
        if not value:
            continue
        try:
            names[int(key.strip(), 0)] = value
        except ValueError:
            continue
    return names


def _load(filename: str) -> dict:
    """Cached per filename - these are read once and never change at runtime."""
    if filename not in _cache:
        _cache[filename] = load_name_file(paths.bundled_data_dir() / filename)
    return _cache[filename]


def effect_names() -> dict:
    return _load(EFFECT_NAMES_FILE)


def charge_effect_names() -> dict:
    return _load(CHARGE_EFFECT_NAMES_FILE)


def animation_names() -> dict:
    return _load(ANIMATION_NAMES_FILE)


def describe(names: dict, value) -> str:
    """
    The annotation shown beside a numeric field: "-> Curaga", or "" when the
    id has no name. Empty rather than "(unknown)" on purpose - an unnamed id
    is normal (the lists don't cover every legal value), and a line of
    "(unknown)" under every such field would be noise.
    """
    try:
        name = names.get(int(value))
    except (TypeError, ValueError):
        return ""
    return f"\u2192 {name}" if name else ""
