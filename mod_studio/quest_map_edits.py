"""
A quest map in Mod Studio (Zodi, 28 October: "Edit quest maps directly"):
a map of a mod's own for its side quests' battles, listed under the game's
maps on the Map Editor and edited there with every tool a map has, apart
from the game's map it is made from. What it is in the game is
`quest_maps.py`'s (a folder `ModStudioMaps/<name>/` that Mod Studio
Framework gives a map number past the game's).

- **Its changes** (`QuestMapEdits`) are kept as a mod's changes to its Base
  are (`state.py`: `map_edits`, `map_terrains`, `map_animations`,
  `texture_edits`, `other_file_replacements`, `unmodelled_table_edits`,
  `map_copies`), keyed alike (the Base's grid keys, file paths and table
  keys), in stores of its own. While one is open the Map Editor works
  through `EditView`: the app's state, but for those stores, which are the
  quest map's. So every tool that changes a map changes a quest map the same
  way, and the game's map (and the mod's changes to it) not at all.
- **Made from a map** (`from_state`): the mod's changes to that map copied
  into a new quest map, and the files Mod Studio made for them in its own
  folder (`local_data`: Light the map's, Add highlight panels', Copy this
  look to's) copied into the quest map's own (`working_folder`), so changing
  either later changes neither.
- **Into the mod** (`parts`): its `map.json` (`quest_maps.QuestMap`): its
  Base's rows in the six tables with its own over them, from Mod Studio's
  database; each picture of its own made as Export makes a texture, under a
  name of its own in its Base's folder (`quest_maps.own_texture_name`), its
  rows naming it so; each place among its Base's numbered files that holds
  a grid it changes, the file the game reads there (`read_name`) with its
  changes, as Export writes a map's; its own model, or its Base's with the
  highlight panels moved for its tiles; its anims; its Title.
- **Out of a mod** (`from_quest_map`): what `parts` wrote, as the changes
  that write it again (a mod opened on General Setup).

Nothing here imports Qt.
"""
from __future__ import annotations

import copy
import json
import re
import shutil
import uuid
from pathlib import Path
from typing import Callable, Optional

from mod_studio import map_classic as mc
from mod_studio import map_enhanced as me
from mod_studio import map_package as mpk
from mod_studio import paths
from mod_studio import quest_maps as qm
from mod_studio.nxd_data import ADDED_ROW

#: Which file the game reads at a place among a map's numbered files that has a revised copy too
#: (`new_map_new_mapNNN_<n>.bin`): the revised copy at these places of each map, the numbered file at the rest. His
#: program's lists of each map's numbered files say so (`dev/research/sidequests/map_lists.py`, 28 October: 174 such
#: places among those the maps' GNS read, 71 the revised copy, the same in both packs). A quest map's own grid file
#: for a place is made from the file the game reads there.
REVISED_PLACES = {
    2: (1, 21), 3: (1,), 4: (1, 2, 3, 5, 7, 9, 11, 13, 15), 5: (1,), 12: (1,), 14: (1, 10, 12, 14, 16), 19: (1,),
    21: (1, 2, 9, 11, 13, 15), 22: (1,), 24: (1,), 27: (1,), 28: (1,), 29: (1,), 30: (1,), 31: (1,),
    34: (1, 2, 3, 4), 35: (1,), 40: (1,), 41: (0, 1, 3), 47: (1,), 50: (1,), 56: (18,), 63: (1,), 64: (1, 2, 3),
    71: (1,), 72: (1,), 73: (7,), 74: (1,), 75: (1,), 76: (1,), 77: (1,), 80: (1,), 83: (1, 12), 84: (1,), 85: (1,),
    87: (1,), 90: (1,), 91: (1,), 92: (1, 9), 94: (1, 3), 103: (1,), 104: (1, 2),
}

#: The stores a mod's changes to a map are kept in (`state.py`), each of which a quest map keeps its own of.
STORES = ("map_edits", "map_terrains", "map_animations", "texture_edits", "other_file_replacements",
          "unmodelled_table_edits", "map_copies")
#: What a quest map's own grid files are called in its folder: by their place.
GRID_FILE = "grid_{place}.bin"
_MAP_FILE = re.compile(r"^(?:map_|new_map_new_)map(\d{3})_\d+\.bin$", re.IGNORECASE)


def read_name(base: int, place: int, numbered: str) -> str:
    """The file the game reads at `place` of map `base`'s numbered files (`numbered`, `map_mapNNN_<n>.bin`): its
    revised copy where the game's lists name it (`REVISED_PLACES`), else the numbered file."""
    return mc.revised_name(numbered) if place in REVISED_PLACES.get(int(base), ()) else numbered


def numbered_files(folder: Path, base: int) -> list:
    """`[(place, numbered file name)]`: map `base`'s numbered files its GNS reads, by place."""
    index = mc.read_gns(Path(folder), base)
    return sorted({(r.index, r.file_name) for r in index.resources if r.file_name})


def working_folder(uid: str) -> Path:
    """Where Mod Studio keeps the files it makes for a quest map (its light, its panels' model), as it keeps a map's
    under `local_data`."""
    return paths.local_data_dir() / "quest_maps" / uid


class QuestMapEdits:
    """
    A quest map in Mod Studio: made from map `base`, its Title (empty: its
    Base's name), and its own changes in `STORES`, keyed as a mod's changes
    to its Base are. `uid` names its working folder for this session.
    """

    def __init__(self, base: int, title: str = "", uid: Optional[str] = None):
        self.base = int(base)
        self.title = title
        self.uid = uid or uuid.uuid4().hex[:12]
        self.map_edits = {}
        self.map_terrains = {}
        self.map_animations = {}
        self.texture_edits = {}
        self.other_file_replacements = {}
        self.unmodelled_table_edits = {}
        self.map_copies = {}

    # As the app's state has them (`state.py`), over its own stores.
    def edited_map_numbers(self) -> list:
        out = set()
        for name, tiles in list(self.map_edits.items()) + list(self.map_terrains.items()):
            if tiles:
                number = _grid_map(name)
                if number is not None:
                    out.add(number)
        return sorted(out)

    def edited_map_tile_count(self) -> int:
        return sum(len(tiles) for tiles in self.map_edits.values())

    def has_any_map_edits(self) -> bool:
        return self.edited_map_tile_count() > 0 or any(self.map_terrains.values())

    def folder(self) -> Path:
        return working_folder(self.uid)


class EditView:
    """
    The app's state as the Map Editor sees it while a quest map is open: its
    `STORES` (and the counts made of them) are the quest map's, everything
    else the state's. Setting a store sets the quest map's.
    """
    _OWN = STORES + ("edited_map_numbers", "edited_map_tile_count", "has_any_map_edits")

    def __init__(self, state, quest: QuestMapEdits):
        object.__setattr__(self, "_state", state)
        object.__setattr__(self, "_quest", quest)

    def __getattr__(self, name):
        if name in EditView._OWN:
            return getattr(object.__getattribute__(self, "_quest"), name)
        return getattr(object.__getattribute__(self, "_state"), name)

    def __setattr__(self, name, value):
        setattr(object.__getattribute__(self, "_quest" if name in STORES else "_state"), name, value)


def _grid_map(name) -> Optional[int]:
    """The map a grid key (`map_classic.grid_key`) or a map file's name is of."""
    found = _MAP_FILE.match(Path(str(name)).name)
    return int(found.group(1)) if found else None


def _file_map(relative_path: str) -> Optional[int]:
    """The map a file a mod carries is one of (its mesh, its anims, its numbered files), else None."""
    rel = str(relative_path).replace("\\", "/")
    for pattern in (r"^bg/meshes/map_(\d{3})_mesh\.bin$", r"^bg/anims/map_(\d{3})_anim\.bin$"):
        found = re.match(pattern, rel, re.IGNORECASE)
        if found:
            return int(found.group(1))
    if rel.lower().startswith(mc.MAP_FOLDER.lower() + "/"):
        return _grid_map(rel[len(mc.MAP_FOLDER) + 1:])
    return None


def _row_map(key) -> Optional[int]:
    first = key[0] if isinstance(key, tuple) and key else key
    return first if isinstance(first, int) else None


def _picture_name(base: int, relative_path: str) -> Optional[str]:
    """A picture's file name in map `base`'s folder of pictures (`gt_0_map022_map_color.tga`), else None."""
    prefix = mpk.picture_relative_path(base, "")
    rel = str(relative_path).replace("\\", "/")
    if rel.lower().startswith(prefix.lower()) and "/" not in rel[len(prefix):] and rel[len(prefix):]:
        return rel[len(prefix):]
    return None


def _source(info):
    return info.get("source_path") if isinstance(info, dict) else info


def _within(path, folder: Path) -> Optional[Path]:
    """`path` relative to `folder` when it is in it, else None."""
    try:
        return Path(path).resolve().relative_to(Path(folder).resolve())
    except (ValueError, OSError, RuntimeError, TypeError):
        return None


#: Where a quest map's working folder keeps the files of the mod it came from (`MOD_FILES` and their places in it).
MOD_FILES = "mod"


def _own_files(made: QuestMapEdits, local: Path, light_root: Path, mod_root: Optional[Path] = None,
               source: Optional[Path] = None) -> None:
    """The files Mod Studio made in its own folder (`local`) that `made`'s stores name, copied into `made`'s
    working folder at the same places in it (another quest map's working folder's, `source`, at their places in
    that), and named there; so are the files of the mod opened (`mod_root`), at their places in it under
    `MOD_FILES`, as an export may write them again or take them out; and its light's settings (Light the map's,
    under `light_root`). Files of the modder's own (a picture chosen, a folder Load edited read) stay where they
    are."""
    target = made.folder()

    def take(path) -> Optional[Path]:
        if _within(path, target) is not None:
            return None
        inside = _within(path, source) if source is not None else None
        if inside is None:
            inside = _within(path, local)
            if inside is not None and inside.parts[:1] == ("quest_maps",):
                inside = Path(*inside.parts[2:]) if len(inside.parts) > 2 else None
        if inside is None and mod_root is not None and _within(path, mod_root) is not None:
            inside = Path(MOD_FILES) / _within(path, mod_root)
        if inside is None:
            return None
        new = target / inside
        if Path(path).is_file():
            new.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, new)
            return new
        return None

    for rel, info in list(made.texture_edits.items()):
        new = take(_source(info))
        if new is not None:
            entry = dict(info) if isinstance(info, dict) else {"source_path": info}
            entry["source_path"] = new
            made.texture_edits[rel] = entry
    for rel, path in list(made.other_file_replacements.items()):
        new = take(path)
        if new is not None:
            made.other_file_replacements[rel] = new
    light = Path(light_root) / "map_lighting" / f"map_{made.base:03d}" / "light.json"
    if light.is_file():
        new = target / "map_lighting" / f"map_{made.base:03d}" / "light.json"
        new.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(light, new)


def from_state(state, base: int, title: str = "", local: Optional[Path] = None,
               light_root: Optional[Path] = None, source: Optional[Path] = None) -> QuestMapEdits:
    """
    A new quest map made from map `base` as the mod has it: the mod's changes
    to `base` (`state`'s stores: its tiles, a grid replaced whole and door
    records, its pictures, model, anims and grid files carried whole, its rows
    in the six tables, a look copied there) copied into the quest map's own,
    and the files of Mod Studio's own they name (in `local`, its `local_data`)
    and of the mod opened copied into its working folder. `state` may be
    another quest map's `EditView` (or a `QuestMapEdits`): a quest map made
    from a quest map, whose working folder is `source`.
    """
    base = int(base)
    local = Path(local) if local is not None else paths.local_data_dir()
    made = QuestMapEdits(base, title)
    for store in ("map_edits", "map_terrains", "map_animations"):
        for key, value in (getattr(state, store, None) or {}).items():
            if _grid_map(key) == base and value:
                getattr(made, store)[key] = copy.deepcopy(value)
    for rel, info in (getattr(state, "texture_edits", None) or {}).items():
        if _picture_name(base, rel) is not None:
            made.texture_edits[rel] = dict(info) if isinstance(info, dict) else {"source_path": info}
    for rel, path in (getattr(state, "other_file_replacements", None) or {}).items():
        if _file_map(rel) == base:
            made.other_file_replacements[rel] = path
    for table, rows in (getattr(state, "unmodelled_table_edits", None) or {}).items():
        if table not in qm.TABLES:
            continue
        for key, fields in (rows or {}).items():
            if _row_map(key) == base and fields:
                made.unmodelled_table_edits.setdefault(table, {})[key] = dict(fields)
    copied_from = (getattr(state, "map_copies", None) or {}).get(base)
    if copied_from is not None:
        made.map_copies[base] = copied_from
    mod_root = getattr(state, "loaded_mod_root", None)
    _own_files(made, local, Path(light_root) if light_root is not None else local,
               Path(mod_root) if mod_root else None, Path(source) if source is not None else None)
    return made


def forget(quest_maps: dict) -> None:
    """Takes out the working folders of quest maps no longer kept (`{name: QuestMapEdits}`: a mod's, as another is
    opened or a new one started, or one taken out on the Map Editor)."""
    for edits in list(quest_maps.values()):
        uid = getattr(edits, "uid", "")
        if uid and re.fullmatch(r"[0-9a-f]+", uid):
            shutil.rmtree(working_folder(uid), ignore_errors=True)


def copy_of(edits: QuestMapEdits, title: str = "", local: Optional[Path] = None) -> QuestMapEdits:
    """A new quest map made from another (`edits`): its changes, and the files in its working folder (and Mod
    Studio's own it names) copied into the new one's."""
    local = Path(local) if local is not None else paths.local_data_dir()
    return from_state(edits, edits.base, title, local, light_root=edits.folder(), source=edits.folder())


# -- Into the mod -------------------------------------------------------------------------------------------------

def _as_list(value):
    if isinstance(value, str) and value[:1] == "[":
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _renamed(value, names: dict):
    """A column's value with the picture names in `names` (lowercase to new) changed, at any depth of its lists."""
    if isinstance(value, list):
        return [_renamed(v, names) for v in value]
    if isinstance(value, str) and value.lower() in names:
        return names[value.lower()]
    return value


def rows_of(sqlite_path, edits: QuestMapEdits) -> dict:
    """`{table: [row]}`: the six tables' rows of its Base (`map_package.table_rows`: the game's, from Mod Studio's
    database, with the quest map's own over them), as a quest map's Rows give them (`quest_maps.table_rows_json`)."""
    out = {}
    for table in qm.TABLES:
        found = mpk.table_rows(sqlite_path, table, edits.base, edits.unmodelled_table_edits.get(table))
        if not qm.TABLES[table][0]:
            found = {(k,): v for k, v in found.items()}
        out[table] = qm.table_rows_json(found)
    return out


def parts(game_dir, sqlite_path, mod_id: str, folder: str, edits: QuestMapEdits,
          stage: Callable[[str, object], bytes]) -> tuple:
    """
    What a quest map writes into its mod (Export): `(quest map, {its own
    file's name: bytes}, {path under the mod's FFTIVC/data/enhanced: bytes},
    [problems])`. `stage(relative path, its texture_edits entry)` makes a
    picture's file as Export makes a texture's (the target's own format).
    See the module's notes.
    """
    game_dir = Path(game_dir)
    base = edits.base
    folder_ = game_dir / mc.MAP_FOLDER
    problems, own, data_files = [], {}, {}
    # Pictures of its own: each under a name of its own, in its Base's folder.
    names = {}
    for rel, info in sorted(edits.texture_edits.items()):
        name = _picture_name(base, rel)
        if name is None:
            continue
        stem = name[:-4] if name.lower().endswith(".tga") else name
        new = qm.own_texture_name(mod_id, folder, stem)
        try:
            data_files[f"bg/textures/{base:03d}/{new}.tga"] = stage(rel, info)
        except Exception as exc:                              # noqa: BLE001
            problems.append(f"its texture {name}: {exc}")
            continue
        names[stem.lower()] = new
    # Rows: its Base's with its own over them, its pictures named so.
    rows = rows_of(sqlite_path, edits)
    if names:
        rows = {table: [{c: _renamed(v, names) for c, v in row.items()} for row in found]
                for table, found in rows.items()}
    if not rows.get("Map"):
        problems.append(f"Mod Studio's database has no Map row {base}")
    quest_map = qm.QuestMap(base, edits.title, rows=rows)
    # Grid: each place whose file the game reads holds a grid it changes, or is a file it carries whole.
    carried = {str(rel).replace("\\", "/").lower(): path for rel, path in edits.other_file_replacements.items()}
    try:
        numbered = numbered_files(folder_, base)
    except OSError:
        numbered = []
        problems.append(f"the unpacked game has no GNS for map {base:03d}")
    for place, name in numbered:
        read = read_name(base, place, name)
        if not (folder_ / read).is_file():
            read = name
        whole = carried.get(mc.relative_path(read).lower())
        key = mc.grid_key(folder_, base, read)
        tiles = edits.map_edits.get(key) or {} if key else {}
        part = edits.map_terrains.get(key) if key else None
        records = edits.map_animations.get(key) if key else None
        if not (whole or tiles or part is not None or records is not None):
            continue
        try:
            data = Path(whole).read_bytes() if whole else (folder_ / read).read_bytes()
            if part is not None:
                data = mc.with_terrain(data, part)
            if records is not None:
                data = mc.with_animation_records(data, records)
            data, said = mc.apply_tile_edits(data, tiles)
            problems += [f"its grid file for place {place}: {p}" for p in said]
        except Exception as exc:                              # noqa: BLE001
            problems.append(f"its grid file for place {place}: {exc}")
            continue
        file = GRID_FILE.format(place=place)
        own[file] = data
        quest_map.grid[place] = file
    # Its model: its own, or its Base's with the highlight panels moved for its tiles; its anims.
    mesh_rel = mpk.mesh_relative_path(base)
    mesh = carried.get(mesh_rel.lower())
    data = Path(mesh).read_bytes() if mesh else None
    try:
        moved = _panels_moved(game_dir, edits, data)
    except Exception as exc:                                  # noqa: BLE001
        moved = None
        problems.append(f"its model's highlight panels: {exc}")
    if moved is not None:
        data = moved
    if data is not None:
        quest_map.mesh = qm.own_mesh_path(mod_id, folder)
        data_files[quest_map.mesh] = data
    anim = carried.get(me.anim_relative_path(base).lower())
    if anim:
        quest_map.anims = qm.own_anims_path(mod_id, folder)
        data_files[quest_map.anims] = Path(anim).read_bytes()
    return quest_map, own, data_files, problems


def _panels_moved(game_dir: Path, edits: QuestMapEdits, mesh: Optional[bytes]) -> Optional[bytes]:
    """Its model (its own, `mesh`, else its Base's) with the highlight panels on its tiles as it changes them, as
    Export moves a map's (`map_package.panels_for_tiles`); None when none moved."""
    base = edits.base
    folder_ = game_dir / mc.MAP_FOLDER
    grid = mpk.enhanced_grid_file(game_dir, base)
    if grid is None:
        return None
    key = mc.grid_key(folder_, base, grid)
    game_mesh = me.mesh_path(game_dir, base)
    copy_ = None
    if not game_mesh.is_file():
        if base not in edits.map_copies or mesh is None or key not in edits.map_terrains:
            return None
        copy_ = (edits.map_copies[base], edits.map_terrains[key])
    if not edits.map_edits.get(key) and mesh is None and key not in edits.map_terrains:
        return None
    tiles = mpk.grid_tiles(game_dir, base, edits.map_edits, edits.other_file_replacements, edits.map_terrains)
    given = mesh if mesh is not None else game_mesh.read_bytes()
    data, moved = mpk.panels_for_tiles(given, game_dir, base, tiles, copy=copy_)
    return data if moved else None


# -- Out of a mod -------------------------------------------------------------------------------------------------

def _stored(value):
    """A value of a quest map's row as Mod Studio's database holds it: lists as JSON text, as the game's tables'."""
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False) if isinstance(value, list) else value


def _same(one, other) -> bool:
    return _as_list(one) == _as_list(other)


def from_quest_map(game_dir, sqlite_path, mod_id: str, folder: str, quest_map: qm.QuestMap, map_folder: Path,
                   data_root: Path, keep: bool = True) -> tuple:
    """
    `(QuestMapEdits, [problems], [files of the mod it names])`: a quest map a
    mod has (its folder `map_folder`, its pictures, model and anims under the
    mod's `data_root`, its `FFTIVC/data/enhanced`) as the changes that write it
    again (`parts`): each of its rows that its Base's (the game's) differ from,
    the columns that differ, and those its Base hasn't, added; its own
    pictures, as the game's pictures they stand for (already made: export
    copies them as they are); its own model (unless it is only its Base's with
    the panels moved for its tiles, which export does again) and anims; each
    grid file as the tile edits that make it from the file the game reads
    there, else carried whole. The files it names are copied into its
    working folder (unless `keep` is False), and named there.
    """
    game_dir = Path(game_dir)
    base = quest_map.base
    made = QuestMapEdits(base, quest_map.title)
    problems, named = [], []
    prefix = qm.own_texture_name(mod_id, folder, "").lower()
    back = {}
    # Rows.
    for table, rows in quest_map.rows.items():
        keys = qm.TABLES[table][0]
        game = mpk.table_rows(sqlite_path, table, base)
        for row in rows:
            key = (base,) + tuple(row[k] for k in keys) if keys else base

            def back_name(value):
                if isinstance(value, list):
                    return [back_name(v) for v in value]
                if isinstance(value, str) and value.lower().startswith(prefix) and len(value) > len(prefix):
                    back[value] = value[len(prefix):]
                    return value[len(prefix):]
                return value
            fields = {c: _stored(back_name(v)) for c, v in row.items() if c not in keys}
            theirs = game.get(key)
            if theirs is None:
                made.unmodelled_table_edits.setdefault(table, {})[key] = {**fields, ADDED_ROW: True}
                continue
            changed = {c: v for c, v in fields.items() if not _same(theirs.get(c), v)}
            if changed:
                made.unmodelled_table_edits.setdefault(table, {})[key] = changed
    # Its pictures.
    for own_name, name in sorted(back.items()):
        file = Path(data_root) / "bg" / "textures" / f"{base:03d}" / f"{own_name}.tga"
        if not file.is_file():
            problems.append(f"its texture {own_name}.tga isn't in the mod")
            continue
        named.append(file)
        made.texture_edits[mpk.picture_relative_path(base, f"{name}.tga")] = {
            "source_path": file, "is_face_texture": False, "already_staged": True}
    # Its model and anims.
    mesh = Path(data_root) / quest_map.mesh if quest_map.mesh else None
    if mesh is not None:
        if not mesh.is_file():
            problems.append(f"its Mesh {quest_map.mesh} isn't in the mod")
        else:
            named.append(mesh)
            made.other_file_replacements[mpk.mesh_relative_path(base)] = mesh
    anims = Path(data_root) / quest_map.anims if quest_map.anims else None
    if anims is not None:
        if not anims.is_file():
            problems.append(f"its Anims {quest_map.anims} isn't in the mod")
        else:
            named.append(anims)
            made.other_file_replacements[me.anim_relative_path(base)] = anims
    # Its grid files.
    folder_ = game_dir / mc.MAP_FOLDER
    try:
        numbered = dict(numbered_files(folder_, base))
    except OSError:
        numbered = {}
        problems.append(f"the unpacked game has no GNS for map {base:03d}")
    found = {}
    for place, file in sorted(quest_map.grid.items()):
        path = Path(map_folder) / file
        name = numbered.get(place)
        if name is None:
            problems.append(f"its Grid's place {place} isn't one of map {base:03d}'s numbered files")
            continue
        read = read_name(base, place, name)
        if not (folder_ / read).is_file():
            read = name
        key = mc.grid_key(folder_, base, read)
        try:
            data = path.read_bytes()
            edits = mc.tile_edits_between((folder_ / read).read_bytes(), data) if key else None
        except OSError as exc:
            problems.append(f"its grid file {file} can't be read ({exc})")
            continue
        if edits is not None and (key not in found or found[key] == edits):
            found[key] = edits
            continue
        made.other_file_replacements[mc.relative_path(read)] = path
    for key, edits in found.items():
        if edits:
            made.map_edits[key] = edits
    # A model only moved for the tiles isn't carried: export moves its Base's panels again.
    if mesh is not None and mesh.is_file() and made.other_file_replacements.get(mpk.mesh_relative_path(base)):
        try:
            without = QuestMapEdits(base)
            for store in STORES:
                setattr(without, store, copy.copy(getattr(made, store)))
            without.other_file_replacements.pop(mpk.mesh_relative_path(base), None)
            again = _panels_moved(game_dir, without, None)
            if again is not None and again == mesh.read_bytes():
                made.other_file_replacements.pop(mpk.mesh_relative_path(base), None)
        except Exception:                                     # noqa: BLE001
            pass
    # Its files are its own: copied into its working folder, as an export may write the mod's again under other
    # names (the quest map renamed) or take them out.
    if keep:
        _own_files(made, paths.local_data_dir(), Path(map_folder), Path(data_root).parents[2])
    return made, problems, named


def summary(edits: QuestMapEdits) -> dict:
    """What a quest map changes, counted for the pages: `{"tiles", "grids", "textures", "model", "anims", "rows"}`."""
    return {
        "tiles": edits.edited_map_tile_count(),
        "grids": len([k for k, v in edits.map_terrains.items() if v]),
        "textures": len([r for r in edits.texture_edits if _picture_name(edits.base, r) is not None]),
        "model": mpk.mesh_relative_path(edits.base) in edits.other_file_replacements,
        "anims": me.anim_relative_path(edits.base) in edits.other_file_replacements,
        "rows": sum(len(v) for v in edits.unmodelled_table_edits.values()),
    }
