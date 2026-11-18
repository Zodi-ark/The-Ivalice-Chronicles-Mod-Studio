"""
(16 November 2026; Mod Studio Framework 2.0.0 in the making) A mod's units of
any battle, and its buried treasures.

Zodi's points of 16 November. His third: "The ENTD only supports a limited
amount of override slots, can we overcome this and allow users to override
every single 16 unit slot for every battle. Furthermore in Mod Studio we
currently do not display all 16 slots per battle in Encounters, the empty
slots are missing I believe." And of his first, War of the Lions' items (and,
his answer, a mod's own): "can be used in Encounters page and modders new
Battles and for Treasure Hunter".

**The file** is `ModStudioBattles.json` at a mod's root, read here as Mod
Studio Framework reads it (`helper/ModStudioEventSetup/BattleFile.cs`), each
problem said in its words:

    { "Format": "Mod Studio battles", "Version": 1,
      "Units": [ { "Battle": 387, "Unit": 5,
                   "Mask": "<80 hex digits>", "Values": "<80 hex digits>",
                   "Job": "Battlemage", "Head": 293, "RightHand": "Moon Sword" } ],
      "Treasures": [ { "Map": 74, "Tile": 2, "Rare": 262, "Common": "Moon Sword" } ] }

- **A unit** is one of a battle's 16 places (`Battle`: its number in the
  game's battle files, 0 to 4095; `Unit`: 1 to 16). `Mask` and `Values` are
  its 40 bytes as the mod has them: where a bit of Mask is set, the unit's
  bit is Values'. The framework writes them after the game's own changes
  (its OverrideEntryData rows), so a unit the game's table has no row for,
  and a place the battle file leaves empty, are units like any other. `Job`
  is one of the mod's own jobs by its Name. `Head`, `Body`, `Accessory`,
  `RightHand` and `LeftHand` are an item past the 255 a byte holds: its
  number (256 to 315: the game's own five and War of the Lions') or the Name
  of one of the mod's own items.
- **A treasure** is one of a map's four buried ones (`Map`: 0 to 127;
  `Tile`: 1 to 4); its `Rare` and `Common` an item past 255 the same way.

**What Mod Studio keeps** (`state.battle_units`, `state.battle_treasures`):
`{(battle, place 0 to 15): UnitEdit}` and `{(map, tile 0 to 3): {"Rare":
..., "Common": ...}}`.

**A field that differs is given its whole mask** (`edit_between`): a level
5 made 10 over another mod's 21 must come out 10, so the mask of a changed
field is every bit of the field, not only the bits that differ. A field put
back as the battle file has it is no change (its bits leave the mask), as an
edit equal to the game's is no edit on any page. **A unit made in an empty
place is a whole unit**: every bit of its 40 bytes is the mod's, so nothing
of another mod's unit there shows through.

**An empty place** is one whose sprite set is 0 (`is_empty`): measured in
his program, the game's making of a battle's units (`0x27128C`) reads an
entry's first byte and makes no unit where it is 0 (`cmp byte ptr [rsi], 0`
at `0x2713D1`). 2,881 of the four files' 8,192 places are so, and 827 of the
add on file's 1,232.

Nothing here imports Qt.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Optional

from . import entd
from . import helper_json as hj
from . import mod_items as mi

#: The file at a mod's root, and what it says it is (the helper's `BattleFile`).
FILE = "ModStudioBattles.json"
FORMAT = "Mod Studio battles"
VERSION = 1
#: A battle's units and a unit's bytes; the last battle a mod may name (the quests' own are numbered from 0x1000);
#: the maps and a map's buried treasures.
UNITS = entd.UNITS_PER_EVENT
ENTRY = entd.UNIT_BYTES
LAST_BATTLE = 0x0FFF
MAPS, TILES = 128, 4
#: The five places a unit wears an item, as the file names them, in the helper's order; each one's words; each
#: one's field of a unit (`entd.BYTE_FIELDS`).
PLACES = ("Head", "Body", "Accessory", "RightHand", "LeftHand")
PLACE_WORDS = ("head", "body", "accessory", "right hand", "left hand")
PLACE_FIELDS = dict(zip(PLACES, ("head", "body", "accessory", "right_hand", "left_hand")))
#: A treasure's two items, as the file names them.
RARE, COMMON = "Rare", "Common"
TREASURE_KEYS = (RARE, COMMON)
#: The first item a byte can't hold and the last a file may name by its number (the game's own five, 256 to 260,
#: then War of the Lions', 261 to 315: `WotLItems.Last`).
FIRST_WIDE, LAST_WIDE = 256, 315
#: The game's own last item (Ring of Aptitude): a number past it is one of War of the Lions'.
LAST_GAME = mi.MOST_GAME_ITEM
#: A job's Name's most characters (the helper's `JobFile.NameMost`).
JOB_NAME_MOST = 40
#: Every bit of a unit.
WHOLE = bytes([0xFF]) * ENTRY
NONE = bytes(ENTRY)


def field_mask(name: str) -> bytes:
    """The bits of a unit's 40 bytes one of its fields is (`entd.WRITABLE_FIELDS`): a byte, two for a 16-bit one,
    a flag's one bit, the team's two, the facing's seven."""
    mask = bytearray(ENTRY)
    if name in entd.FLAG_FIELDS:
        offset, bit = entd.FLAG_FIELDS[name]
        mask[offset] = bit
    elif name == "team":
        mask[entd.TEAM_OFFSET] = entd.TEAM_MASK
    elif name == "facing":
        mask[entd.FACING_OFFSET] = entd.FACING_MASK
    elif name in entd.USHORT_FIELDS:
        mask[entd.USHORT_FIELDS[name]] = mask[entd.USHORT_FIELDS[name] + 1] = 0xFF
    elif name in entd.BYTE_FIELDS and name in entd.WRITABLE_FIELDS:
        mask[entd.BYTE_FIELDS[name]] = 0xFF
    else:
        raise ValueError(f"a unit has no field {name}")
    return bytes(mask)


#: `{field: its bits}` for every field a unit is written by. Together they are every bit of the 40 bytes, each once.
FIELD_MASKS = {name: field_mask(name) for name in entd.WRITABLE_FIELDS}


def _and(a: bytes, b: bytes) -> bytes:
    return bytes(x & y for x, y in zip(a, b))


def _or(a: bytes, b: bytes) -> bytes:
    return bytes(x | y for x, y in zip(a, b))


@dataclass(frozen=True)
class UnitEdit:
    """One of a battle's units as the mod has it: `mask` and `values` over its 40 bytes (see the module's notes),
    `job` one of the mod's own jobs by its Name ("" none), `items` its items past 255 by the place each is worn
    (`PLACES`): a number (256 to 315) or the Name of one of the mod's own items."""
    mask: bytes = NONE
    values: bytes = NONE
    job: str = ""
    items: tuple = ()

    def worn(self) -> dict:
        """`{place: its item past 255}`."""
        return dict(self.items)

    def changes(self) -> bool:
        """Whether it changes anything (a bit of its mask, a job, an item): one that doesn't isn't kept or written."""
        return any(self.mask) or bool(self.job) or bool(self.items)


def is_empty(entry: bytes) -> bool:
    """Whether a place's 40 bytes make no unit: its sprite set (its first byte) is 0 (see the module's notes)."""
    return not entry[0]


def unit_bytes(base: bytes, edit: Optional[UnitEdit]) -> bytes:
    """A unit's 40 bytes as the game is given them: the battle file's (`base`) with the mod's bits over them."""
    if len(base) != ENTRY:
        raise ValueError(f"a unit is {ENTRY} bytes, got {len(base)}")
    if edit is None:
        return bytes(base)
    return bytes((b & ~m & 0xFF) | (v & m) for b, m, v in zip(base, edit.mask, edit.values))


def edit_between(base: bytes, new: bytes) -> tuple:
    """(mask, values) that make the battle file's unit `base` the unit `new`: each field that differs its whole
    mask; every bit where `base` is an empty place and `new` a unit."""
    if len(base) != ENTRY or len(new) != ENTRY:
        raise ValueError(f"a unit is {ENTRY} bytes")
    if is_empty(base) and not is_empty(new):
        return WHOLE, bytes(new)
    mask = NONE
    for bits in FIELD_MASKS.values():
        if _and(base, bits) != _and(new, bits):
            mask = _or(mask, bits)
    return mask, _and(new, mask)


def changed_fields(base: bytes, edit: Optional[UnitEdit]) -> list:
    """The fields of a unit the mod changes, by their names in a unit's order of bytes: those any bit of its mask
    is in whose value isn't the battle file's."""
    if edit is None:
        return []
    new = unit_bytes(base, edit)
    return [name for name, bits in FIELD_MASKS.items()
            if any(_and(edit.mask, bits)) and _and(base, bits) != _and(new, bits)]


def _kept(edit: UnitEdit) -> Optional[UnitEdit]:
    return edit if edit.changes() else None


def with_unit(base: bytes, edit: Optional[UnitEdit], new: bytes) -> Optional[UnitEdit]:
    """The mod's unit after its 40 bytes are made `new` (its job and items as they were); None when nothing of it
    is the mod's any more."""
    mask, values = edit_between(base, new)
    return _kept(replace(edit or UnitEdit(), mask=mask, values=values))


def with_field(base: bytes, edit: Optional[UnitEdit], name: str, value) -> Optional[UnitEdit]:
    """The mod's unit after one of its fields is set (`entd.unit_with`'s names and values)."""
    return with_unit(base, edit, entd.unit_with(unit_bytes(base, edit), **{name: value}))


def with_fields(base: bytes, edit: Optional[UnitEdit], **changes) -> Optional[UnitEdit]:
    """The same for several fields at once."""
    return with_unit(base, edit, entd.unit_with(unit_bytes(base, edit), **changes))


#: The game's generic jobs a mod's own job is based on (74 the Squire to 93), and the job level a unit put in one is
#: given where its own isn't 1 to 8 (`quest_edits.SAMPLE_JOB_LEVEL`).
FIRST_GENERIC_JOB = 74
JOB_LEVEL = 2


def with_job(base: bytes, edit: Optional[UnitEdit], job: str, like: int) -> Optional[UnitEdit]:
    """The mod's unit put in one of the mod's own jobs (`job`, its Name), as a quest's unit is
    (`quest_edits.set_unit_job`): its file's job the game's job its job is based on (`like`, 74 to 93), its career
    job that job, at the job level it has where that is 1 to 8 (else 2)."""
    now = entd.read_unit(unit_bytes(base, edit)).values
    level = now["prereq_job_level"]
    made = with_fields(base, edit, main_job=like, prereq_job=like - FIRST_GENERIC_JOB,
                       prereq_job_level=level if 1 <= level <= 8 else JOB_LEVEL)
    return _kept(replace(made or UnitEdit(), job=job))


def without_job(edit: Optional[UnitEdit]) -> Optional[UnitEdit]:
    """The mod's unit in no job of the mod's own (its main job changed on its card: its file's job is its job)."""
    return _kept(replace(edit, job="")) if edit is not None else None


def good_item(ref) -> bool:
    """Whether `ref` names an item past 255 as the file may: its number (256 to 315) or a mod's item's Name."""
    if isinstance(ref, bool):
        return False
    if isinstance(ref, int):
        return FIRST_WIDE <= ref <= LAST_WIDE
    return mi.good_name(ref)


def ref_key(ref) -> str:
    """An item past 255 as a dropdown keeps it beside the game's items' numbers: "#293" for a number, "=Moon Sword"
    for a mod's item's Name (words, so that it is never taken for an item a byte holds)."""
    return f"#{int(ref)}" if isinstance(ref, int) and not isinstance(ref, bool) else f"={ref}"


def key_ref(key: str):
    """The item a dropdown's key names (`ref_key`)."""
    return int(key[1:]) if key.startswith("#") else key[1:]


#: A place's field of a unit (`entd.BYTE_FIELDS`) by the name the file gives the place, and the other way.
FIELD_PLACES = {field: place for place, field in PLACE_FIELDS.items()}


def with_item(edit: Optional[UnitEdit], place: str, ref) -> Optional[UnitEdit]:
    """The mod's unit wearing an item past 255 at `place` (`PLACES`), or none there (`ref` None)."""
    if place not in PLACES:
        raise ValueError(f"a unit wears no item at {place}")
    if ref is not None and not good_item(ref):
        raise ValueError(f"{ref!r} isn't an item past 255 by its number ({FIRST_WIDE} to {LAST_WIDE}) or a name")
    worn = (edit or UnitEdit()).worn()
    if ref is None:
        worn.pop(place, None)
    else:
        worn[place] = ref
    return _kept(replace(edit or UnitEdit(), items=tuple((p, worn[p]) for p in PLACES if p in worn)))


def copied_unit(entries: list, source: int) -> Optional[bytes]:
    """
    A copy of one of a battle's units for another of its places (`entries`:
    its 16 units' 40 bytes as they now are; `source`: the place copied, or,
    where that one is empty, the battle's first unit), with a unit id no
    other unit of the battle has, as a quest battle's Add a unit gives one
    (`quest_edits.unit_added`). None for a battle with no unit to copy.
    """
    units = [(n, e) for n, e in enumerate(entries) if not is_empty(e)]
    found = next((e for n, e in units if n == source), None) or next((e for _, e in units), None)
    if found is None:
        return None
    at = entd.BYTE_FIELDS["unit_id"]
    taken = {e[at] for _, e in units}
    return entd.unit_with(found, unit_id=next((n for n in range(0x80, 0xFF) if n not in taken), found[at]))


# =============================================================================
# The file
# =============================================================================

def _hex(data: bytes) -> str:
    return bytes(data).hex().upper()


def battles_json(units: dict, treasures: dict) -> dict:
    """The file's fields for the mod's units and treasures, in their battles', places', maps' and tiles' order."""
    out = {"Format": FORMAT, "Version": VERSION}
    listed = []
    for (battle, slot) in sorted(units):
        edit = units[(battle, slot)]
        if edit is None or not edit.changes():
            continue
        entry = {"Battle": int(battle), "Unit": int(slot) + 1}
        if any(edit.mask):
            entry["Mask"] = _hex(edit.mask)
            entry["Values"] = _hex(_and(edit.values, edit.mask))
        if edit.job:
            entry["Job"] = edit.job
        entry.update(edit.worn())
        listed.append(entry)
    if listed:
        out["Units"] = listed
    buried = []
    for (map_number, tile) in sorted(treasures):
        items = {key: ref for key, ref in (treasures[(map_number, tile)] or {}).items()
                 if key in TREASURE_KEYS and ref is not None}
        if items:
            buried.append({"Map": int(map_number), "Tile": int(tile) + 1,
                           **{key: items[key] for key in TREASURE_KEYS if key in items}})
    if buried:
        out["Treasures"] = buried
    return out


def has_any(units: Optional[dict], treasures: Optional[dict]) -> bool:
    """Whether the mod has a unit or a treasure the file would hold."""
    made = battles_json(units or {}, treasures or {})
    return "Units" in made or "Treasures" in made


def battles_text(units: dict, treasures: dict) -> str:
    """The file's text, as Mod Studio writes it: a unit a line, a treasure a line."""
    made = battles_json(units, treasures)
    lines = ["{", f'  "Format": {json.dumps(made["Format"])},']
    parts = [f'  "Version": {made["Version"]}']
    for key in ("Units", "Treasures"):
        if key in made:
            rows = ",\n".join("    " + json.dumps(entry, ensure_ascii=False) for entry in made[key])
            parts.append(f'  "{key}": [\n{rows}\n  ]')
    return "\n".join(lines) + "\n" + ",\n".join(parts) + "\n}\n"


def _whole(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _raw(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def _entry_bytes(entry: dict, key: str) -> Optional[bytes]:
    text = hj.get(entry, key)
    if not isinstance(text, str) or len(text) != 2 * ENTRY:
        return None
    try:
        return bytes(int(text[2 * i:2 * i + 2], 16) for i in range(ENTRY))
    except ValueError:
        return None


def _good_job(text) -> bool:
    """A job's Name as the helper takes one (`JobFile.GoodJobName`)."""
    return (isinstance(text, str) and 0 < hj.units(text) <= JOB_NAME_MOST
            and not any(ch < " " or "\x7f" <= ch <= "\x9f" for ch in text) and len(text.encode("utf-8")) < 1024)


def _read_item(entry: dict, key: str, what: str, problems: list):
    """(whether it can be used, the item) of an entry's item under `key`: (True, None) where it names none."""
    if not hj.has(entry, key) or hj.get(entry, key) is None:
        return True, None
    value = hj.get(entry, key)
    if good_item(value):
        return True, value
    problems.append(f"{what}'s {key} is an item past the 255 a byte holds by its number ({FIRST_WIDE} to "
                    f"{LAST_WIDE}) or the Name of one of its mod's own items, not {_raw(value)}")
    return False, None


def _read_unit(entry, place: int, problems: list):
    battle, unit = (hj.get(entry, "Battle"), hj.get(entry, "Unit")) if isinstance(entry, dict) else (None, None)
    if not _whole(battle) or not 0 <= battle <= LAST_BATTLE or not _whole(unit) or not 1 <= unit <= UNITS:
        problems.append(f"its unit {place} names no unit of a battle (Battle: 0 to {LAST_BATTLE}; Unit: 1 to {UNITS})")
        return None
    what = f"unit {unit} of battle {battle}"
    mask, values = NONE, NONE
    if hj.has(entry, "Mask") or hj.has(entry, "Values"):
        mask, values = _entry_bytes(entry, "Mask"), _entry_bytes(entry, "Values")
        if mask is None or values is None:
            problems.append(f"{what}: its Mask and Values are each an entry's {ENTRY} bytes in hex ({2 * ENTRY} "
                            "digits)")
            return None
        for i in range(ENTRY):
            if values[i] & ~mask[i] & 0xFF:
                problems.append(f"{what}: its Values has a bit its Mask doesn't (byte {i})")
                return None
    job = ""
    if hj.has(entry, "Job") and hj.get(entry, "Job") is not None:
        job = hj.get(entry, "Job")
        if not _good_job(job):
            problems.append(f"{what}: its Job isn't a job's Name: 1 to {JOB_NAME_MOST} characters, none a control "
                            "character")
            return None
    worn = []
    for key in PLACES:
        good, item = _read_item(entry, key, what, problems)
        if not good:
            return None
        if item is not None:
            worn.append((key, item))
    edit = UnitEdit(mask=mask, values=values, job=job, items=tuple(worn))
    if not edit.changes():
        problems.append(f"{what} changes nothing (no bit of Mask, no Job, no item)")
        return None
    return (battle, unit - 1), edit


def _read_treasure(entry, place: int, problems: list):
    map_number, tile = (hj.get(entry, "Map"), hj.get(entry, "Tile")) if isinstance(entry, dict) else (None, None)
    if not _whole(map_number) or not 0 <= map_number < MAPS or not _whole(tile) or not 1 <= tile <= TILES:
        problems.append(f"its treasure {place} names no treasure of a map (Map: 0 to {MAPS - 1}; Tile: 1 to {TILES})")
        return None
    what = f"treasure {tile} of map {map_number}"
    items = {}
    for key in TREASURE_KEYS:
        good, item = _read_item(entry, key, what, problems)
        if not good:
            return None
        if item is not None:
            items[key] = item
    if not items:
        problems.append(f"{what} names no item ({RARE}, {COMMON})")
        return None
    return (map_number, tile - 1), items


def read_text(text: str) -> tuple:
    """
    (`{(battle, place): UnitEdit}`, `{(map, tile): {"Rare": ..., "Common":
    ...}}`, problems) from the file's text, as the helper reads it
    (`BattleFile.Read`): the whole file left out for a problem of its own, a
    unit or a treasure with a problem of its own left out, each said in the
    helper's words (after the mod's and the file's names).
    """
    try:
        top = hj.loads(text)
    except ValueError as exc:
        return {}, {}, [f"it isn't JSON ({exc})"]
    if not isinstance(top, dict) or hj.get(top, "Format") != FORMAT:
        return {}, {}, [f"its Format isn't \"{FORMAT}\""]
    version = hj.get(top, "Version")
    if not _whole(version) or version != VERSION:
        return {}, {}, [f"its Version isn't {VERSION}"]
    units, treasures, problems = {}, {}, []
    if hj.has(top, "Units"):
        listed = hj.get(top, "Units")
        if not isinstance(listed, list):
            problems.append("its Units isn't a list")
        else:
            for place, entry in enumerate(listed, 1):
                found = _read_unit(entry, place, problems)
                if found is None:
                    continue
                if found[0] in units:
                    problems.append(f"it gives unit {found[0][1] + 1} of battle {found[0][0]} twice")
                    continue
                units[found[0]] = found[1]
    if hj.has(top, "Treasures"):
        listed = hj.get(top, "Treasures")
        if not isinstance(listed, list):
            problems.append("its Treasures isn't a list")
        else:
            for place, entry in enumerate(listed, 1):
                found = _read_treasure(entry, place, problems)
                if found is None:
                    continue
                if found[0] in treasures:
                    problems.append(f"it gives treasure {found[0][1] + 1} of map {found[0][0]} twice")
                    continue
                treasures[found[0]] = found[1]
    return units, treasures, problems


def read(mod_root) -> tuple:
    """A mod's units and treasures (`FILE` at its root), read as the helper reads them: ({}, {}, []) when it has
    none."""
    path = Path(mod_root) / FILE
    if not path.is_file():
        return {}, {}, []
    try:
        text = hj.read_text(path)
    except OSError as exc:
        return {}, {}, [f"it can't be read ({exc})"]
    return read_text(text)


def write(mod_root, units: dict, treasures: dict) -> list:
    """The file written into the mod (or taken away when the mod has no unit and no treasure). Returns the paths
    written."""
    path = Path(mod_root) / FILE
    if not has_any(units, treasures):
        if path.is_file():
            path.unlink()
        return []
    path.write_text(battles_text(units, treasures), encoding="utf-8")
    return [FILE]


# =============================================================================
# The items and jobs they name
# =============================================================================

def items_named(units: Optional[dict], treasures: Optional[dict]) -> list:
    """Every item past 255 the mod's units wear and its treasures hold: numbers and Names, each once, in order."""
    found = []
    for key in sorted(units or {}):
        edit = units[key]
        found.extend(ref for _place, ref in (edit.items if edit is not None else ()))
    for key in sorted(treasures or {}):
        found.extend(ref for name, ref in sorted((treasures[key] or {}).items()) if name in TREASURE_KEYS
                     and ref is not None)
    seen, out = set(), []
    for ref in found:
        if (type(ref), ref) not in seen:
            seen.add((type(ref), ref))
            out.append(ref)
    return out


def lion_items(refs) -> list:
    """Those of `refs` that are War of the Lions' items by their numbers (261 to 315), in order."""
    return sorted({ref for ref in refs if _whole(ref) and LAST_GAME < ref <= LAST_WIDE})


def jobs_named(units: Optional[dict]) -> list:
    """The mod's own jobs its units are put in, each once, by name."""
    return sorted({edit.job for edit in (units or {}).values() if edit is not None and edit.job})


def _renamed_items(items, old: str, new: Optional[str]):
    return tuple((place, new if ref == old and isinstance(ref, str) else ref) for place, ref in items
                 if not (new is None and isinstance(ref, str) and ref == old))


def item_renamed(units: dict, treasures: dict, old: str, new: Optional[str]) -> None:
    """One of the mod's own items given another name (or, `new` None, taken out of the mod): every unit that wears
    it and every treasure that holds it follows (or holds it no more), in place."""
    for key in list(units):
        edit = units[key]
        if edit is None:
            continue
        kept = _kept(replace(edit, items=_renamed_items(edit.items, old, new)))
        if kept is None:
            del units[key]
        else:
            units[key] = kept
    for key in list(treasures):
        items = dict(_renamed_items(tuple((treasures[key] or {}).items()), old, new))
        if items:
            treasures[key] = items
        else:
            del treasures[key]


def job_renamed(units: dict, old: str, new: Optional[str]) -> None:
    """One of the mod's own jobs given another name (or, `new` None, taken out of the mod: its units stay in the
    game's job it was based on), in place."""
    for key in list(units):
        edit = units[key]
        if edit is None or edit.job != old:
            continue
        kept = _kept(replace(edit, job=new or ""))
        if kept is None:
            del units[key]
        else:
            units[key] = kept
