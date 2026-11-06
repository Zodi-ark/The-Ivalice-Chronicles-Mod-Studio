"""
A quest's own maps (Zodi, 27 October, after his test 32: "Yes, start with
test 33"; Mod Studio Framework 1.10.0).

**A quest map** is a folder of its own in a mod, `ModStudioMaps/<map>/`,
holding `map.json` (`map_text`) and its own PlayStation files. It is made
from one of the game's maps, its `Base` (0 to 127): what the map doesn't
give is that map's. A modder never chooses its number (his rule): the
helper (`helper/ModStudioEventSetup/MapFile.cs` reads this same file and
says the same problems, word for word) gives it one from 129 to 255 as the
game starts, the same every time, and a quest's event setup names it by its
folder's name (`"Map": "Sunken Ruins"`).

**What it gives**:
- `Rows`: its rows in the six tables the game keys by a map (`TABLES`:
  `Map`, `RefinedBgTexture`, `RefinedBgSystemTexture`, `RefinedBgMeshNode`,
  `RefinedBgAnim`, `RefinedBgMeshPolygon`), whole, each as Mod Studio's
  database holds a row (its keys after the map's: `Key2`, `Key3`; its list
  columns as lists); the helper adds them at its number as the tables load.
  The pictures they name are looked for in its Base's folder
  (`bg/textures/NNN/`): the game's own there, and the mod's, which take
  names of their own (`own_texture_name`).
- `Mesh` and `Anims`: its enhanced mesh and anims, at paths of the mod's own
  under `bg/meshes/` and `bg/anims/` (`own_mesh_path`, `own_anims_path`), in
  its `FFTIVC/data/enhanced/`; without them, its Base's.
- `Grid`: its own PlayStation files (its battle grid's), each by its place
  among its Base's numbered files (the place its Base's GNS records name a
  file by: the numbered files in number order), a file in its folder.
- `Title`: its name where the game shows a map's (else its Base's, from its
  `Map` row).

Nothing here imports Qt.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from mod_studio import helper_json as hj

FOLDER = "ModStudioMaps"
FILE_NAME = "map.json"
FORMAT = "Mod Studio quest map"
VERSION = 1
#: The game's maps a quest map may be made from.
GAME_MAPS = 128
#: A file's place among its Base's numbered files (the game's maps have at most 40).
PLACES = 64
#: The most a PlayStation file of a quest map may be (a map's largest, a texture, is 131,072).
MOST_FILE = 1 << 20
MOST_PATH = 200
MOST_TITLE = 64
#: The numbers the helper gives quest maps: past the game's 128 and the one more its Map table has a row for (128).
FIRST_MAP, LAST_MAP = 129, 255

INT, FLOAT, SHORT, BYTE, TEXT, INTS, TEXTS, VARIANTS = "int", "float", "short", "byte", "text", "ints", "texts", "variants"
#: Each table: its keys after the map's, its fixed bytes, its columns (name, kind) in their order (the helper's
#: `MapRows.Tables`).
TABLES = {
    "Map": ((), 0x20, (("DLCFlags", INT), ("Comment", TEXT), ("Unknown8", INT), ("UnknownC", INT),
                       ("Unknown10", INT), ("Unknown14", VARIANTS), ("Unknown1C", INT))),
    "RefinedBgTexture": (("Key2", "Key3"), 0x28, (("DLCFlags", INT), ("Comment", TEXT), ("Unknown8", TEXTS),
                                                  ("Unknown10", INTS), ("Unknown18", TEXTS), ("Unknown20", INTS))),
    "RefinedBgSystemTexture": (("Key2", "Key3"), 0x18, (("DLCFlags", INT), ("Comment", TEXT), ("Unknown8", TEXTS),
                                                        ("Unknown10", TEXTS))),
    "RefinedBgMeshNode": (("Key2", "Key3"), 0x1C, (("DLCFlags", INT), ("Comment", TEXT), ("Unknown8", INT),
                                                   ("UnknownC", INT), ("Unknown10", INT), ("Unknown14", BYTE),
                                                   ("Unknown15", BYTE), ("Unknown16", BYTE), ("Unknown17", BYTE),
                                                   ("Unknown18", BYTE))),
    "RefinedBgAnim": (("Key2",), 0xC, (("Unknown0", INT), ("Unknown4", INT), ("Unknown8", INT))),
    "RefinedBgMeshPolygon": (("Key2",), 0x18, (("DLCFlags", INT), ("Unknown4", INT), ("Unknown8", INT),
                                               ("UnknownC", INT), ("RefinedBgMeshPolygonCondId", INT),
                                               ("Unknown14", INT))),
}
#: A Map variant's 24 numbers (the layout's UnknownMapStruct).
VARIANT_KINDS = (INT,) * 8 + (FLOAT,) + (INT,) * 3 + (FLOAT, FLOAT) + (SHORT,) * 6 + (BYTE,) * 4
MOST_LIST, MOST_TEXT = 256, 255
INT_RANGE = (-(1 << 31), (1 << 32) - 1)
RANGES = {INT: INT_RANGE, SHORT: (-(1 << 15), (1 << 16) - 1), BYTE: (-128, 255)}


@dataclass
class QuestMap:
    """A quest map: its Base, Title, mesh and anims paths ("" for its Base's), its own files by their places, its
    rows by table (each a dict of its keys and columns)."""
    base: int
    title: str = ""
    mesh: str = ""
    anims: str = ""
    grid: dict = field(default_factory=dict)          # place -> file name in its folder
    rows: dict = field(default_factory=dict)          # table -> [row dict]


def _what(kind: str) -> str:
    return {INT: "a 32-bit number", FLOAT: "a number", SHORT: "a 16-bit number", BYTE: "a byte",
            TEXT: "a text or null", INTS: f"a list of up to {MOST_LIST} 32-bit numbers",
            TEXTS: f"a list of up to {MOST_LIST} texts"}.get(kind, "a list of variants of 24 numbers")


def _whole(value, low: int, high: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and low <= value <= high


def _number(value, kind: str) -> bool:
    if kind == FLOAT:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return False
        try:
            return math.isfinite(float(value))
        except OverflowError:
            return False
    low, high = RANGES[kind]
    return _whole(value, low, high)


def _text(value) -> bool:
    return isinstance(value, str) and len(value.encode("utf-8")) <= MOST_TEXT


def _value(value, kind: str) -> bool:
    if kind == TEXT:
        return value is None or _text(value)
    if kind in (INTS, TEXTS):
        return (isinstance(value, list) and len(value) <= MOST_LIST
                and all(_text(v) if kind == TEXTS else _number(v, INT) for v in value))
    if kind == VARIANTS:
        return (isinstance(value, list) and len(value) <= MOST_LIST
                and all(isinstance(v, list) and len(v) == len(VARIANT_KINDS)
                        and all(_number(x, k) for x, k in zip(v, VARIANT_KINDS)) for v in value))
    return _number(value, kind)


def _row(name: str, row, where: str, problems: list) -> Optional[dict]:
    keys, _, columns = TABLES[name]
    if not isinstance(row, dict):
        problems.append(f"{where} isn't a list of fields")
        return None
    before = len(problems)
    kinds = dict(columns)
    out = {}
    given = set()
    for key, value in hj.pairs(row):
        if key in given:
            problems.append(f"{where} gives {key} twice")
            continue
        given.add(key)
        if key == "Key":
            problems.append(f"{where} gives Key: the map's number is the helper's to give")
        elif key in keys:
            if not _whole(value, 0, (1 << 31) - 1):
                problems.append(f"{where}'s {key} isn't 0 to {(1 << 31) - 1}")
            else:
                out[key] = value
        elif key not in kinds:
            problems.append(f"{where} has no column {key}")
        elif not _value(value, kinds[key]):
            problems.append(f"{where}'s {key} isn't {_what(kinds[key])}")
        else:
            out[key] = value
    for key in keys:
        if key not in row:
            problems.append(f"{where} gives no {key}")
    return None if len(problems) > before else out


def read_rows(given: dict, problems: list) -> dict:
    """A map.json's Rows by table, what is wrong in `problems` (the helper's `MapRows.Read`)."""
    rows = {}
    for name, value in hj.pairs(given):
        if name not in TABLES:
            problems.append(f"its Rows have no table {name}")
            continue
        if name in rows:
            problems.append(f"its Rows give {name} twice")
            continue
        listed = rows[name] = []
        keys = TABLES[name][0]
        if not keys:
            row = _row(name, value, f"its Rows' {name}", problems)
            if row is not None:
                listed.append(row)
            continue
        if not isinstance(value, list):
            problems.append(f"its Rows' {name} isn't a list of rows")
            continue
        seen = set()
        for n, item in enumerate(value, 1):
            row = _row(name, item, f"its Rows' {name} row {n}", problems)
            if row is None:
                continue
            at = ", ".join(str(row[k]) for k in keys)
            if at in seen:
                problems.append(f"its Rows' {name} has two rows at {at}")
            else:
                seen.add(at)
                listed.append(row)
    if not rows.get("Map"):
        problems.append("its Rows have no Map row")
    return rows


def good_path(path, under: str) -> bool:
    """A path of the mod's own under `under` (the helper's `GoodPath`)."""
    return (isinstance(path, str) and path.startswith(under) and path.endswith(".bin") and len(path) <= MOST_PATH
            and len(path) > len(under) + 4 and "//" not in path and ".." not in path
            and re.fullmatch(r"[a-z0-9_\-/.]+", path) is not None)


def good_title(title) -> bool:
    """A title (the helper's `GoodTitle`): 1 to MOST_TITLE characters, none a control character, no space at
    either end."""
    return (isinstance(title, str) and 0 < hj.units(title) <= MOST_TITLE and title.strip() == title
            and not any(ord(c) < 32 or 0x7F <= ord(c) <= 0x9F for c in title))


_get, _has = hj.get, hj.has


def read_map_text(text: str, read_file: Callable[[str], bytes]) -> tuple:
    """(the quest map, problems) from a `map.json`'s text, checked as the helper checks it, word for word;
    `read_file` reads one of its folder's files by name. The quest map is None when it can't be used."""
    problems = []
    try:
        data = hj.loads(text)
    except ValueError as exc:
        problems.append(f"its {FILE_NAME} isn't JSON ({exc})")
        return None, problems
    if not isinstance(data, dict):
        problems.append(f"its {FILE_NAME} isn't a list of fields")
        return None, problems
    if hj.broken_text(data):
        problems.append(f"its {FILE_NAME} {hj.BROKEN_TEXT}")
        return None, problems
    version = _get(data, "Version")
    if _get(data, "Format") != FORMAT or not _whole(version, -(1 << 31), (1 << 31) - 1) or version != VERSION:
        problems.append(f"its {FILE_NAME} isn't a \"{FORMAT}\" file of version {VERSION}")
        return None, problems
    base = _get(data, "Base")
    if not _whole(base, 0, GAME_MAPS - 1):
        problems.append(f"its Base isn't one of the game's maps 0 to {GAME_MAPS - 1}")
    title = ""
    if _has(data, "Title"):
        title = _get(data, "Title")
        if not good_title(title):
            problems.append(f"its Title isn't 1 to {MOST_TITLE} characters, none of them a control character, "
                            "without a space at either end")
            title = ""
    paths = {}
    for name, under in (("Mesh", "bg/meshes/"), ("Anims", "bg/anims/")):
        if not _has(data, name):
            continue
        path = _get(data, name)
        if not good_path(path, under):
            problems.append(f"its {name} isn't a path under {under} of lowercase letters, digits, _ and -, ending "
                            f".bin, {MOST_PATH} characters at most")
        else:
            paths[name] = path
    grid = {}
    if _has(data, "Grid"):
        given = _get(data, "Grid")
        if not isinstance(given, dict):
            problems.append("its Grid isn't a list of files by their places")
        else:
            for key, file in hj.pairs(given):
                if not re.fullmatch(r"[0-9]+", key) or str(int(key)) != key or not 0 <= int(key) < PLACES:
                    problems.append(f"its Grid's place {key} isn't 0 to {PLACES - 1}")
                    continue
                place = int(key)
                if not isinstance(file, str) or not file or ".." in file or "/" in file or "\\" in file or ":" in file:
                    problems.append(f"its Grid's place {place} names no file in its folder")
                    continue
                try:
                    size = len(read_file(file))
                except OSError as exc:
                    problems.append(f"its Grid's file {file} can't be read ({exc})")
                    continue
                if not 0 < size <= MOST_FILE:
                    problems.append(f"its Grid's file {file} is {size} bytes; a map's file is 1 to {MOST_FILE}")
                else:
                    grid[place] = file
    given_rows = _get(data, "Rows")
    rows = {}
    if not isinstance(given_rows, dict):
        problems.append("it has no Rows")
    else:
        rows = read_rows(given_rows, problems)
    if problems:
        return None, problems
    return QuestMap(base, title, paths.get("Mesh", ""), paths.get("Anims", ""), grid, rows), problems


def map_text(quest_map: QuestMap) -> str:
    """
    The quest map's `map.json`, as the helper reads it: its fields one a
    line, then its Rows, each table's rows one a line (`Map` its one row),
    in the order the quest map holds them.
    """
    def one(value) -> str:
        return json.dumps(value, ensure_ascii=False)
    head = {"Format": FORMAT, "Version": VERSION, "Base": quest_map.base}
    if quest_map.title:
        head["Title"] = quest_map.title
    if quest_map.mesh:
        head["Mesh"] = quest_map.mesh
    if quest_map.anims:
        head["Anims"] = quest_map.anims
    if quest_map.grid:
        head["Grid"] = {str(place): name for place, name in sorted(quest_map.grid.items())}
    lines = ["{"] + [f" {one(key)}: {one(value)}," for key, value in head.items()] + [' "Rows": {']
    tables = list(quest_map.rows.items())
    for n, (name, rows) in enumerate(tables):
        last = "" if n == len(tables) - 1 else ","
        if name in TABLES and not TABLES[name][0]:
            row = rows[0] if isinstance(rows, list) and len(rows) == 1 else rows
            lines.append(f"  {one(name)}: {one(row)}{last}")
        elif not rows:
            lines.append(f"  {one(name)}: []{last}")
        else:
            lines.append(f"  {one(name)}: [")
            lines += [f"   {one(row)}" + ("," if m < len(rows) - 1 else "") for m, row in enumerate(rows)]
            lines.append(f"  ]{last}")
    lines += [" }", "}"]
    return "\n".join(lines) + "\n"


#: A quest map's folder's name: letters, digits, spaces, _ and -, 1 to 64 of them (as a quest's, the helper's
#: `QuestFile.GoodName`).
good_name = hj.good_name


def _safe(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "x"


def same_files(one: str, other: str) -> bool:
    """Whether two quest maps' names give their own files the same names (`own_mesh_path`, `own_texture_name`:
    lowercase letters and digits, each run of anything else one underscore), as two of one mod's mustn't: "Old
    Town" and "old_town"."""
    return _safe(one) == _safe(other)


def own_mesh_path(mod_id: str, folder: str) -> str:
    """Where a quest map's own mesh goes: in the game's folder of meshes, under a name of the mod and the map."""
    return f"bg/meshes/msq_{_safe(mod_id)}_{_safe(folder)}_mesh.bin"


def own_anims_path(mod_id: str, folder: str) -> str:
    return f"bg/anims/msq_{_safe(mod_id)}_{_safe(folder)}_anim.bin"


def own_texture_name(mod_id: str, folder: str, name: str) -> str:
    """A picture of the quest map's own (a game picture it changes, or a new one): its rows name it so, and it goes
    in its Base's folder of pictures under that name (with .tga), apart from the game's and other mods'."""
    return f"msq_{_safe(mod_id)}_{_safe(folder)}_{name}"


def texture_file(base: int, name: str) -> str:
    """The mod's file for a picture its rows name: `FFTIVC/data/enhanced/` + its Base's folder + the name + .tga."""
    return f"FFTIVC/data/enhanced/bg/textures/{base:03d}/{name}.tga"


def write_map(mod_folder, folder: str, quest_map: QuestMap, files: dict) -> list:
    """Writes a quest map into `<mod_folder>/ModStudioMaps/<folder>/`: its file and its own PlayStation files
    (`files`: name to bytes). Returns the paths written."""
    if not good_name(folder):
        raise ValueError(f"a quest map's folder is named as a quest's: {folder!r}")
    root = Path(mod_folder) / FOLDER / folder
    root.mkdir(parents=True, exist_ok=True)
    written = []
    for name, data in files.items():
        path = root / name
        path.write_bytes(data)
        written.append(path)
    path = root / FILE_NAME
    path.write_text(map_text(quest_map), encoding="utf-8")
    written.append(path)
    return written


def read_mod_maps(mod_folder) -> list:
    """Every quest map of a mod, in its folders' order: (folder, the quest map or None, problems)."""
    root = Path(mod_folder) / FOLDER
    out = []
    if not root.is_dir():
        return out
    for sub in sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.name):
        file = sub / FILE_NAME
        if not file.is_file():
            continue
        if not good_name(sub.name):
            out.append((sub.name, None, ["its folder's name isn't a name (letters, digits, spaces, _ and -, 1 to 64 "
                                         "of them)"]))
            continue
        try:
            text = hj.read_text(file)
        except OSError as exc:
            out.append((sub.name, None, [f"it can't be read ({exc})"]))
            continue
        quest_map, problems = read_map_text(text, lambda n, s=sub: (s / n).read_bytes())
        out.append((sub.name, quest_map, problems))
    return out


def map_names(mod_folder) -> list:
    """The names of a mod's quest maps (its folders with a map.json): what a quest's setup may name (the helper's
    `MapFile.NamesIn`)."""
    root = Path(mod_folder) / FOLDER
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir() if p.is_dir() and (p / FILE_NAME).is_file())


def table_rows_json(rows: dict) -> list:
    """Mod Studio's database rows of a table (`map_package.table_rows`: `{(map, key2, ...): {column: value}}`, list
    columns as JSON text) as a quest map's Rows give them: keys after the map's as Key2 and Key3, lists as lists."""
    out = []
    for key, fields in sorted(rows.items(), key=lambda kv: kv[0] if isinstance(kv[0], tuple) else (kv[0],)):
        row = {}
        if isinstance(key, tuple):
            for name, value in zip(("Key2", "Key3"), key[1:]):
                row[name] = value
        for name, value in fields.items():
            if isinstance(value, str) and value[:1] == "[":
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    pass
            row[name] = value
        out.append(row)
    return out
