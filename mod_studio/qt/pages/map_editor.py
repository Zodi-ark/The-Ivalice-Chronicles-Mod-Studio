"""
Edit Game Data / Map Editor.

The game's maps, drawn from the unpacked game in either look with the
battle grid over them, and the grid's tiles changed by clicking them.
Asked for as a map viewer and made the Map Editor from Zodi's answers:

- **Both looks, the enhanced one first**, "as that is what the overwhelming
  majority of users play". The enhanced look is the FFTOMESH mesh and its
  pictures (`map_enhanced`), the classic one the PlayStation mesh, texture
  and palettes (`map_classic`).
- **Turned freely, and from the game's own camera corners.** Dragging turns
  it; Turn left and Turn right go to the four corners the game's camera
  stands at, which also decide which walls the game leaves out (they fade
  while the map turns: `map_scene.corner_weights`). With Show directions,
  N, E, S and W are marked round the grid, and the corner the camera is at
  is said ("Seen from the SW corner"): the names Light the map's compass
  and parts.txt's hide words use (Zodi's stress test of 20 October). Off
  until ticked (Zodi, 21 October: "for first time users it should start
  disabled").
- **The tiles, with each tile's height and surface when the pointer is on
  it**, and a switch for the card that says them. These switches, Show
  battles' and Show directions' are remembered between sessions
  (`ui_settings`).
- **The variants**: a map's arrangements, in the classic look its day and
  night and its weathers, and in the enhanced look its lightings
  (`map_enhanced.lightings`: the story battles' own, the random battles'
  six, a second lighting), asked for after the second in-game test.
- **"Map Editor", with all a map editor can offer.** What can be edited is
  the battle grid, tile by tile and several tiles at once. The enhanced
  look's pictures are textures, which the Textures page replaces; a right
  click on the map opens the one under the pointer there.
- **The enhanced look's model and pictures**, asked for after the first
  build: Save for editing writes the map as a package (`map_package`: an
  OBJ, PNGs and what they can't hold) for Blender, a script or an AI
  coworker; Load edited builds one back, and the map is drawn from it and
  goes into the mod (the mesh as a file carried through, the pictures as
  Textures replacements). The highlight panels follow the grid on export.

What the page does with an edit:

- **Only the fields changed are kept**, in `state.map_edits` under the
  grid's name (`map_classic.grid_key`), as the values chosen. A field set
  back to the game's value is taken out again, and so is a tile left with
  none.
- **Export writes them into the game's own files**, each field's bits
  overwritten where they sit (`map_classic.apply_tile_edits`), in every file
  of the map holding that grid (`map_classic.grid_files`), under the mod's
  `fftpack/map/`. A file keeps its size, which the mod loader needs.
- **An opened mod's map files come back as edits** when they are this
  page's kind (`map_classic.tile_edits_between`); any other copy is carried
  through untouched (Setup's `_take_over_maps`).
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QEvent, QObject, QPointF, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QFormLayout, QFrame, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMenu, QPushButton, QRadioButton, QScrollArea, QSizePolicy, QSpinBox,
    QSplitter, QVBoxLayout, QWidget,
)

from ... import constants as c
from ... import map_battles as mb
from ... import map_classic as mc
from ... import map_enhanced as me
from ... import map_package as mpk
from ... import map_variants as mv
from ... import game_install, paths, ui_settings, xml_io
from .. import export_dialogs
from .. import map_scene as ms
from ..map_render import Camera
from ..widgets import actions
from ..widgets.flow_layout import FlowLayout
from ..widgets.map_view import MapView
from ..widgets.number_boxes import FittedSpinBox
from ..workers import Worker, run_in_thread

INTRO = ("The game's maps, drawn from its own files. Pick a map, turn it with the mouse "
         "and point at a tile for its surface and height. Click tiles to change them, or right "
         "click a texture to replace it.")

#: The map list's width on first show: "048  Sal Ghidos Slumtown" and the
#: longest names beside it.
MAP_LIST_WIDTH = 300
#: The tile's panel, right of the map.
SIDE_WIDTH = 360

#: Words for a map's arrangements; a map has at most six.
ARRANGEMENTS = ("First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh", "Eighth")
#: The four shading values, as GaneshaDx names them.
SHADINGS = ("Normal", "Dark", "Darker", "Darkest")
#: How many surfaces the game's `Land` table has room for (6 bits).
SURFACES = 64

#: The tile fields the panel edits, in its order.
FIELDS = ("surface", "height", "slope", "slope_height", "depth", "thickness",
          "no_walk", "no_cursor", "pass_through", "shading")

NO_GAME = ("No game files yet.\n\nGo to General Setup and either unpack your game, or point at "
           "a folder you have already unpacked. Its battle maps will appear here.")


def arrangement_word(index: int) -> str:
    return ARRANGEMENTS[index] if 0 <= index < len(ARRANGEMENTS) else f"Number {index + 1}"


def lighting_word(lighting) -> str:
    """
    A lighting's name on the page (`map_enhanced.Lighting`), from what its
    pictures' names end with: "Usual", "Story B", "Random battle C",
    "Second lighting".
    """
    suffix = re.sub(r"_0$", "", lighting.suffix).lstrip("_")
    if lighting.kind == "random":
        letter = suffix[1:] if suffix.lower().startswith("r") else suffix
        return f"Random battle {letter.upper()}" if letter else f"Random battle {lighting.index + 1}"
    if lighting.kind == "second":
        rest = suffix[1:].lstrip("_") if suffix.startswith("2") else suffix
        return f"Second lighting {rest.upper()}".strip()
    if not suffix:
        return "Usual" if lighting.index == 0 else f"Story {lighting.index + 1}"
    return f"Story {suffix.upper()}"


def lighting_words(lightings) -> list:
    """Every lighting's name, one each: a name two would share gets their place in the game's list."""
    words = [lighting_word(lighting) for lighting in lightings]
    return [f"{w} ({lighting.index + 1})" if words.count(w) > 1 else w
            for w, lighting in zip(words, lightings)]


def lighting_tip(lighting, events: dict) -> str:
    """
    What the Lighting box says of a lighting pointed at: the events that use
    it (`events`, `{story index: [events]}`, over every story list it stands
    for), or what a random battles' or a second lighting is.
    """
    if lighting.kind == "random":
        return LIGHTING_RANDOM
    if lighting.kind == "second":
        return LIGHTING_SECOND
    found = sorted({e for kind, index in (lighting.same or (("story", lighting.index),)) if kind == "story"
                    for e in events.get(index, ())})
    if not found:
        return LIGHTING_NO_EVENT
    return (LIGHTING_EVENT if len(found) == 1 else LIGHTING_EVENTS).format(events=mb.runs(found))


def map_label(number: int, name: str) -> str:
    """A row of the map list: "048  Sal Ghidos Slumtown"."""
    return f"{number:03d}  {name}" if name else f"{number:03d}"


def map_names(state) -> dict:
    """
    `{map number: name}`: the names the Treasure Hunter page lists its maps
    by, the comments of `MapTrapFormationData.xml`, from the loaded table or
    else the bundled file.
    """
    records = (getattr(state, "item_table_records", None) or {}).get("map_trap") or []
    names = {r.item_id: r.name for r in records if getattr(r, "name", None)}
    if names:
        return names
    try:
        return xml_io.load_ability_names(paths.bundled_data_dir() / c.TABLE_FILENAMES["map_trap"])
    except (OSError, KeyError):
        return {}


def _table_rows(sqlite_path, table: str, columns: str) -> list:
    if not sqlite_path:
        return []
    try:
        con = sqlite3.connect(f"file:{Path(sqlite_path).as_posix()}?mode=ro", uri=True)
        try:
            return con.execute(f'SELECT {columns} FROM "{table}" ORDER BY Key').fetchall()
        finally:
            con.close()
    except sqlite3.Error:
        return []


def surface_names(sqlite_path, language: str) -> dict:
    """`{surface: name}` from the game's `Land-<language>`; the unnamed ones left out."""
    return {key: name for key, name in _table_rows(sqlite_path, f"Land-{language}", "Key, Name")
            if name}


def height_labels(sqlite_path, language: str) -> dict:
    """`{row: text}` from `LandscapeHeight-<language>`: "0", "0.5", "1" ..."""
    return {key: text for key, text in _table_rows(sqlite_path, f"LandscapeHeight-{language}",
                                                  "Key, Text") if text}


def languages_with_names(sqlite_path) -> list:
    """The languages the database has surface names in, English first."""
    if not sqlite_path:
        return []
    try:
        con = sqlite3.connect(f"file:{Path(sqlite_path).as_posix()}?mode=ro", uri=True)
        try:
            tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            con.close()
    except sqlite3.Error:
        return []
    return [lang for lang in actions.language_order() if f"Land-{lang}" in tables]


def names_language(sqlite_path) -> str:
    """
    The language the surface names and heights are read in: English, or
    the first the database has them in. (There was a picker; Zodi asked for
    it to go.)
    """
    have = languages_with_names(sqlite_path)
    return have[0] if have else "en"


def _together(*widgets) -> QWidget:
    """Widgets a wrapping row keeps on one line: a label and its box, a set of buttons."""
    holder = QWidget()
    row = QHBoxLayout(holder)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(8)
    for widget in widgets:
        row.addWidget(widget)
    holder.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    return holder


#: How many of a build's notes Load edited's note says; the rest go into
#: the folder's `built/notes.txt`, and the note says how many more.
NOTES_SHOWN, NOTES_FILE = 3, "notes.txt"


#: Add highlight panels' words (`MapEditorPage.add_panels`).
PANELS_BUTTON = "Add highlight panels"
PANELS_TIP = ("In a battle, the game shows where a unit can move or act on panels over the tiles, and "
              "this map's look has none: none of the game's battles is fought here. Adds one over every "
              "tile the cursor can stop on, made from the tiles, and they follow the tiles when you export.")
PANELS_ADDED = ("Map {number:03d} has highlight panels now, over its {count} tiles the cursor can stop on, "
                "in your mod's copy of its look. They follow the tiles when you export, and Put back the "
                "game's look takes them out.")
PANELS_THERE = "Map {number:03d}'s look has highlight panels already."

#: Copy this look to's words (`MapEditorPage.copy_look`). Zodi, 21 October:
#: "copying a map's look to a new map number (WotL Restoration's map 127 is
#: the reference)", for a battle on a map of its own.
COPY_BUTTON = "Copy this look to"
COPY_TIP = ("Puts this map's look, as your mod has it, on one of the game's spare map numbers: a battle "
            "grid with no look of its own, where none of the game's battles is fought. Its battle grid goes "
            "with it, so a battle you set there on the Event Editor's Setup card plays on this look.")
COPY_USED = "{label} (has map {source:03d}'s look)"
COPY_NONE = "The game has no spare map numbers to copy a look to."
COPY_DONE = ("Map {target:03d} has map {source:03d}'s look in your mod now: its model, {pictures} textures, "
             "{rows} table rows and its battle grid. Change its tiles here, and set an event's Map to "
             "{target:03d} on the Event Editor's Setup card to play a battle there.")
COPY_MISSING = (" {count} texture{s} its rows name {are} in neither your mod nor the game folder, so "
                "{they} {are}n't copied.")
COPY_NO_PANELS = (" Its look has no highlight panels, on which a battle shows where units can move: Add "
                  "highlight panels gives it some.")
#: Said when the source has doors an event opens and the target's files have
#: no room for the animations they are opened with (`animations_fit`).
COPY_NO_DOORS = (" Its doors won't open in an event on map {target:03d}: its files have no room for the "
                 "door animations. Maps 097 and 099 have room.")
COPY_NEEDS_DATABASE = ("Copying a look needs the game's database, which General Setup makes as it unpacks "
                       "the game: its tables say which textures the copy uses.")
COPY_NO_GRID = "Map {source:03d}'s look stands on no battle grid, so there is none to copy with it."
#: Said when lightings naming no sky were given the source's own as colors
#: (`MapEditorPage.copy_look`; his "go with your recommendation", 22 October).
COPY_SKY = (" Its lightings with no sky colors of their own get map {source:03d}'s sky as colors, so the copy "
            "has the sky the game draws behind the original.")
COPY_PUT_BACK = ("Map {target:03d} is as the game has it again: map {source:03d}'s look, the battle grid that "
                 "came with it and the tiles you changed on it are out of your mod.")
#: The title of a map with a copied look: "Map 097, ..., with map 048's look".
COPY_TITLE = ", with map {source:03d}'s look"

#: Put back the game's look's words: the tiles' heights go back with the look.
LOOK_PUT_BACK = "Map {number:03d} has the game's model and textures again."
SKY_PUT_BACK = " Its sky colors are the game's again too."
#: Sky colors (Zodi's list after shaping, 21 October: "sky colours"), the
#: `Map` table's colors behind the map in a battle (`map_variants`).
SKY_BUTTON = "Sky colors"
SKY_TIP = "Change the colors of the sky behind the map in a battle."
SKY_SET = ("Map {number:03d}'s sky colors go into your mod, in its row of the game's Map table (written with "
           "FF16Tools at export).")
SKY_GAME = "Map {number:03d}'s sky colors are the game's again."
#: What the Lighting box says of each lighting, pointed at.
LIGHTING_EVENTS = "Events {events} use it."
LIGHTING_EVENT = "Event {events} uses it."
LIGHTING_NO_EVENT = "No event uses it."
LIGHTING_RANDOM = "A random battles' lighting: the game picks one of these for a random battle here."
LIGHTING_SECOND = "A second lighting some of the map's texture groups have: when the game uses it isn't known."
HEIGHTS_PUT_BACK = (" The {count} tiles your mod had made higher or lower have the game's heights again too, "
                    "so units stand on the ground as it is drawn.")
HEIGHTS_PUT_BACK_ONE = (" The tile your mod had made higher or lower has the game's height again too, so units "
                        "stand on the ground as it is drawn.")
#: The tile fields that go back to the game's with its look.
HEIGHT_FIELDS = ("height", "slope", "slope_height")
#: Add an upper level's words (Zodi's list after shaping, 21 October: "an
#: upper level where a map has none"; `map_classic.upper_tile_fields`).
UPPER_BUTTON = "Add an upper level"
UPPER_TIP = ("Makes a tile on the upper level over each picked tile that has none there, for a bridge or a "
             "floor your model has over the ground: in a battle units stand on it, and on the ground under "
             "it. It starts {steps} height steps up, with the ground's surface (a Bridge over water); set its "
             "height and the rest here, as for any tile. Put back the game's tile takes it away again.")
UPPER_MADE = ("{count} upper level tile{s} made over the picked tile{s}, {steps} height steps up, and picked: "
              "give {them} the height of your model's floor there.")
UPPER_PANELS = " {They} {get} highlight panels when you export."
#: Said in the tile panel when a picked upper level tile leaves units no way
#: under it (`map_classic.can_go_under`): his test 11 (22 October), a bridge 4
#: high and 2 thick over Gariland's canal, which units stood on and none
#: could go under.
ROOM_ONE = ("Units can't go under this tile: its underside (its height less its thickness) must be at least "
            "{room} height steps over the ground under it, and over the lowest ground beside it, where units "
            "walk in. A height of {least} or more does that.")
ROOM_MANY = ("Units can't go under {count} of these tiles: a tile's underside (its height less its thickness) "
             "must be at least {room} height steps over the ground under it, and over the lowest ground beside "
             "it, where units walk in. A height of {least} or more does that.")


def upper_made_note(count: int, steps: int, panels: bool = True) -> str:
    """What Add an upper level says of the tiles it made; `panels`, the look has highlight panels."""
    one = count == 1
    words = dict(count=count, s="" if one else "s", steps=steps, them="it" if one else "them",
                 They="It" if one else "They", get="gets" if one else "get")
    return UPPER_MADE.format(**words) + (UPPER_PANELS.format(**words) if panels else "")


def heights_back_note(count: int) -> str:
    """What Put back the game's look adds when `count` tiles had other heights: nothing for none."""
    if not count:
        return ""
    return HEIGHTS_PUT_BACK_ONE if count == 1 else HEIGHTS_PUT_BACK.format(count=count)

def panels_file(number: int) -> Path:
    """Where Add highlight panels keeps map `number`'s look with its panels, for the mod to carry."""
    return paths.local_data_dir() / "map_panels" / f"map_{int(number):03d}" / f"map_{int(number):03d}_mesh.bin"


def copy_folder(number: int) -> Path:
    """Where Copy this look to keeps the model and anim file copied to map `number`, for the mod to carry."""
    return paths.local_data_dir() / "map_copies" / f"map_{int(number):03d}"


def light_file(number: int) -> Path:
    """
    Where Light the map keeps map `number`'s light (`map_light.light_folder`
    and `LIGHT_FILE`), named here so carrying it in a package needs no numpy.
    """
    return paths.local_data_dir() / "map_lighting" / f"map_{int(number):03d}" / "light.json"


def names_in(value) -> list:
    """The texture names a table row's column holds: a JSON list of them, or one name."""
    if not isinstance(value, str) or not value:
        return []
    try:
        found = json.loads(value)
    except ValueError:
        return [value]
    if isinstance(found, list):
        return [v for v in found if isinstance(v, str)]
    return [found] if isinstance(found, str) else []


def as_edited(tile: mc.Tile, changes: dict) -> mc.Tile:
    return mc.Tile(tile.x, tile.z, tile.level, mc.tile_with(tile.raw, changes)) if changes else tile


def _value(tile: mc.Tile, name: str) -> int:
    return int(tile.get(name))


class PackageSaveWorker(Worker):
    """Writes a map's enhanced look as a package, off the GUI thread: its textures take seconds."""

    def __init__(self, game_dir, number, folder, sqlite_path, mesh_file, picture_files,
                 rows=None, tiles=None, grid_file=None, anim_file=None):
        super().__init__()
        self.args = (game_dir, number, folder, sqlite_path, mesh_file, picture_files)
        self.rows = {table: dict(found) for table, found in (rows or {}).items()}
        self.tiles, self.grid_file = (dict(tiles) if tiles else None), grid_file
        self.anim_file = anim_file

    def run(self):
        game_dir, number, folder, sqlite_path, mesh_file, picture_files = self.args
        try:
            return mpk.export_package(game_dir, number, folder, sqlite_path, mesh_file, picture_files,
                                      rows=self.rows, tiles=self.tiles, grid_file=self.grid_file,
                                      anim_file=self.anim_file)
        except (OSError, ValueError) as exc:
            raise RuntimeError(str(exc)) from exc


def same_pixels(one, other) -> bool:
    """Whether two image files hold the same picture, pixel for pixel (a PNG and its TGA, say)."""
    from PIL import Image
    try:
        with Image.open(one) as a, Image.open(other) as b:
            return a.size == b.size and a.convert("RGBA").tobytes() == b.convert("RGBA").tobytes()
    except (OSError, ValueError, TypeError):
        return False


class PackageLoadWorker(Worker):
    """
    Builds a package, off the GUI thread, and works out where the tiles
    under its model's ground go (`map_package.ground_under_tiles`), and
    whether what it builds is the mod's look already (`mod_mesh` and
    `mod_pictures`, the mod's: the same model and the same pictures), and
    where its new faces stand over or cover the tiles (`map_battles.
    faces_over`). Returns `(folder, Built, mesh file or None, Ground or
    None, the same, {"stands", "covers"}, anim file or None)`: the anim
    file (`map_package.write_built_anim`) when the mod is to have one of
    its own, for new groups with frames.
    """

    def __init__(self, folder, game_dir=None, mod_mesh=None, mod_pictures=None, mod_anim=None):
        super().__init__()
        self.folder, self.game_dir = folder, game_dir
        self.mod_mesh, self.mod_anim = mod_mesh, mod_anim
        self.mod_pictures = {name.lower(): Path(path) for name, path in (mod_pictures or {}).items()}
        #: Its new faces over the tiles (`map_battles.faces_over`), on the
        #: grid it was saved with: `{"stands": ..., "covers": ...}`.
        self.over = {"stands": {}, "covers": {}}

    def run(self):
        try:
            built = mpk.build(self.folder)
        except mpk.PackageError as exc:
            raise RuntimeError(str(exc)) from exc
        # A package saved from the mod's own look is built from the mod's
        # model: built unchanged, that model is still the mod's, not the
        # game's (it was taken out of the mod until 12 October).
        try:
            base = json.loads((Path(self.folder) / mpk.METADATA).read_text(encoding="utf-8")).get("base", {})
        except (OSError, ValueError):
            base = {}
        from_mod = base.get("from") == mpk.FROM_MOD
        mesh_file = mpk.write_built(self.folder, built) if built.changed or from_mod else None
        ground = None
        if (built.changed or from_mod) and self.game_dir is not None:
            try:
                ground = mpk.ground_under_tiles(self.folder, built, self.game_dir)
            except (OSError, ValueError, mc.MapError):
                ground = None               # the tiles are offered nothing, the model still goes in
        if mesh_file is not None:
            try:
                meta = json.loads((Path(self.folder) / mpk.METADATA).read_text(encoding="utf-8"))
                base = me.read_mesh((Path(self.folder) / meta["base"]["file"]).read_bytes())
                self.over = mb.faces_over(me.read_mesh(built.mesh), mb.package_grid(meta), base)
            except (OSError, ValueError, KeyError):
                self.over = {"stands": {}, "covers": {}}
        anim_file = mpk.write_built_anim(self.folder, built)
        return (self.folder, built, mesh_file, ground, self._same_as_mod(built, mesh_file, anim_file), self.over,
                anim_file)

    def _same_as_mod(self, built, mesh_file, anim_file=None) -> bool:
        """Whether the model, anim file and textures built are the mod's own already (item 23 of 20 October's test)."""
        try:
            if (mesh_file is None) != (self.mod_mesh is None) or (anim_file is None) != (self.mod_anim is None):
                return False
            if mesh_file is not None and Path(mesh_file).read_bytes() != Path(self.mod_mesh).read_bytes():
                return False
            if anim_file is not None and Path(anim_file).read_bytes() != Path(self.mod_anim).read_bytes():
                return False
        except OSError:
            return False
        return all(name.lower() in self.mod_pictures and same_pixels(path, self.mod_pictures[name.lower()])
                   for name, path in built.pictures.items())


def mod_look(state, number) -> tuple:
    """
    `(mesh file or None, {texture name: image file})`: what of map
    `number`'s enhanced look a mod replaces - a mesh carried through
    (`other_file_replacements`), and textures on the Textures page.
    """
    if number is None:
        return None, {}
    replaced = getattr(state, "other_file_replacements", {}) or {}
    mesh = replaced.get(mpk.mesh_relative_path(number))
    prefix = mpk.picture_relative_path(number, "")
    pictures = {}
    for rel, info in (getattr(state, "texture_edits", {}) or {}).items():
        if rel.lower().startswith(prefix.lower()) and "/" not in rel[len(prefix):]:
            source = info.get("source_path") if isinstance(info, dict) else info
            if source:
                pictures[rel[len(prefix):]] = Path(source)
    return (Path(mesh) if mesh else None), pictures


def mod_anim(state, number) -> Optional[Path]:
    """The anim file a mod has for map `number` (new groups' frames: `other_file_replacements`), or None."""
    if number is None:
        return None
    found = (getattr(state, "other_file_replacements", {}) or {}).get(me.anim_relative_path(number))
    return Path(found) if found else None


#: The tables a map's look is found by: rows of a map's there are the Map
#: Editor's (Load edited and Put back the game's look add and take them).
LOOK_TABLES = (mpk.TEXTURE_TABLE, mpk.NODE_TABLE, mpk.SYSTEM_TABLE, mpk.ANIM_TABLE)
#: A texture Load edited put into the mod says so (`map_looks`).
LOOK_MARK = "map_look"
_MESH_FILE = re.compile(r"^bg/meshes/map_(\d{3})_mesh\.bin$", re.IGNORECASE)
_ANIM_FILE = re.compile(r"^bg/anims/map_(\d{3})_anim\.bin$", re.IGNORECASE)


def map_looks(state) -> dict:
    """
    `{map number: {"mesh": file or None, "anim": file or None, "textures":
    {relative path: file}, "rows": {table: {key: fields}}, "copied_from":
    map or None}}`: the enhanced looks a mod has from the Map Editor, for
    Mod Contents (Zodi, 12 October: name what the Map Editor added). A map
    is in it with a model (`other_file_replacements`), rows in
    `LOOK_TABLES`, or a texture Load edited put in (`LOOK_MARK`); its
    textures are those under its folder, as Put back the game's look takes.
    A look copied to it (`state.map_copies`) names its source, and has its
    polygons' and `Map` rows too (`copy_rows_of`).
    """
    numbers = set()
    for rel in (getattr(state, "other_file_replacements", {}) or {}):
        found = _MESH_FILE.match(str(rel).replace("\\", "/")) or _ANIM_FILE.match(str(rel).replace("\\", "/"))
        if found:
            numbers.add(int(found.group(1)))
    store = getattr(state, "unmodelled_table_edits", None) or {}
    for table in LOOK_TABLES:
        numbers.update(key[0] for key, fields in (store.get(table) or {}).items()
                       if isinstance(key, tuple) and len(key) == _key_length(table) and fields)
    for info in (getattr(state, "texture_edits", {}) or {}).values():
        if isinstance(info, dict) and isinstance(info.get(LOOK_MARK), int):
            numbers.add(info[LOOK_MARK])
    copies = getattr(state, "map_copies", None) or {}
    numbers.update(n for n in ((store.get(mpk.MAP_TABLE) or {})) if isinstance(n, int) and sky_row(state, n))
    out = {}
    for number in sorted(numbers):
        mesh, _pictures = mod_look(state, number)
        prefix = mpk.picture_relative_path(number, "").lower()
        textures = {rel: Path(info.get("source_path")) if isinstance(info, dict) and info.get("source_path")
                    else info for rel, info in (getattr(state, "texture_edits", {}) or {}).items()
                    if rel.lower().startswith(prefix)}
        rows = {t: {k: f for k, f in found.items() if f} for t, found in mod_rows(state, number).items()}
        # A look copied here (`copy_look`): its polygons' and `Map` rows too,
        # and the map it came from.
        if number in copies:
            for table, found in copy_rows_of(state, number).items():
                rows.setdefault(table, {}).update(found)
        elif sky_row(state, number):
            rows.setdefault(mpk.MAP_TABLE, {})[number] = sky_row(state, number)
        out[number] = {"mesh": mesh, "anim": mod_anim(state, number), "textures": textures,
                       "rows": rows, "copied_from": copies.get(number)}
    return out


def sky_row(state, number) -> dict:
    """
    `{column: value}`: map `number`'s sky colors in the mod (its `Map` row's
    variants, `map_variants.VARIANTS_COLUMN`), when the mod changes them and
    the map isn't a look's copy (whose `Map` row `copy_rows_of` has).
    """
    if number in (getattr(state, "map_copies", None) or {}):
        return {}
    row = ((getattr(state, "unmodelled_table_edits", None) or {}).get(mpk.MAP_TABLE) or {}).get(number) or {}
    return {mv.VARIANTS_COLUMN: row[mv.VARIANTS_COLUMN]} if mv.VARIANTS_COLUMN in row else {}


def look_rows(state) -> dict:
    """`{table: {key: fields}}`: the table edits that are maps' looks (`map_looks`), the Map Editor's."""
    out = {}
    for look in map_looks(state).values():
        for table, found in look["rows"].items():
            out.setdefault(table, {}).update(found)
    return out


def mod_rows(state, number) -> dict:
    """
    `{table: {key: fields}}`: map `number`'s rows among a mod's table edits
    (`unmodelled_table_edits`) in `LOOK_TABLES`: the texture groups and
    parts it adds, parts it draws another way, its units' lighting, and the
    frames that move (`RefinedBgAnim`, keyed by map and row).
    """
    store = getattr(state, "unmodelled_table_edits", None) or {}
    out = {}
    for table in LOOK_TABLES:
        found = {key: fields for key, fields in (store.get(table) or {}).items()
                 if isinstance(key, tuple) and len(key) == _key_length(table) and key[0] == number}
        if found:
            out[table] = found
    return out


def _key_length(table: str) -> int:
    """How many keys a look table's rows have: `RefinedBgAnim`'s two (map and row), the others' three."""
    return 2 if table == mpk.ANIM_TABLE else 3


def copy_rows_of(state, number) -> dict:
    """
    `{table: {key: fields}}`: the rows a look copied to map `number` has
    beyond `mod_rows`' (`map_package.copy_rows`): its polygons'
    (`POLYGON_TABLE`, keyed by map and row) and its `Map` row's names,
    lightings and sky (`MAP_COLUMNS`, the row keyed by the map alone).
    """
    store = getattr(state, "unmodelled_table_edits", None) or {}
    out = {}
    found = {key: fields for key, fields in (store.get(mpk.POLYGON_TABLE) or {}).items()
             if isinstance(key, tuple) and len(key) == 2 and key[0] == number and fields}
    if found:
        out[mpk.POLYGON_TABLE] = found
    row = {k: v for k, v in ((store.get(mpk.MAP_TABLE) or {}).get(number) or {}).items() if k in mpk.MAP_COLUMNS}
    if row:
        out[mpk.MAP_TABLE] = {number: row}
    return out


def has_look(state, game_dir, number) -> bool:
    """
    Whether map `number` has an enhanced look: the game's, or one a mod put
    there (a look copied to it: its model in `other_file_replacements`).
    """
    if number is None:
        return False
    if game_dir is not None and me.mesh_path(Path(game_dir), number).is_file():
        return True
    return mod_look(state, number)[0] is not None


def map_terrains(state) -> dict:
    """`state.map_terrains`: the battle grids a mod replaces whole, `{grid key: terrain part}`."""
    return dict(getattr(state, "map_terrains", None) or {})


def terrains_of(state, number) -> tuple:
    """Map `number`'s grids a mod replaces whole, as `((grid key, terrain part), ...)`: what a page redraws for."""
    out = []
    for key, part in sorted(map_terrains(state).items()):
        try:
            if int(key.lower().split("map_map")[1][:3]) == number and part:
                out.append((key, bytes(part)))
        except (IndexError, ValueError):
            continue
    return tuple(out)


def doors_of(records: Optional[bytes]) -> bool:
    """Whether a map's texture animation records (`map_classic.animation_records`) have any an event starts:
    its doors (`map_classic.started_records`)."""
    return bool(records) and bool(mc.started_records(records))


def animations_fit(game: Path, names) -> bool:
    """Whether every one of a grid's files (`names`) has room for texture animation records."""
    folder = Path(game) / mc.MAP_FOLDER
    try:
        for name in names:
            mc.animation_records((folder / name).read_bytes())
    except (OSError, mc.MapError):
        return False
    return bool(names)


def variants_of(state, number: int) -> list:
    """Map `number`'s variants, the mod's `Map` row over the game's (`map_variants.read_variants`)."""
    store = getattr(state, "unmodelled_table_edits", None) or {}
    return mv.read_variants(getattr(state, "nxd_sqlite_path", None), number, store.get(mpk.MAP_TABLE))


def lighting_of(lightings: list, variants: list, variant) -> int:
    """
    The place in `lightings` (`map_enhanced.lightings`) of the lighting a
    battle meeting `variant` is drawn with: a random battle's, else its
    story lighting (`map_variants.story_index`); 0 when none is listed.
    """
    if variant is None:
        return 0
    key = ("random", variant.random - 1) if variant.random else ("story", mv.story_index(variants, variant))
    for i, lighting in enumerate(lightings):
        if key in (lighting.same or ((lighting.kind, lighting.index),)):
            return i
    return 0


def battle_sky(variant, index, battle: tuple):
    """
    `((r, g, b), (r, g, b))`, top and bottom: the sky the game draws behind
    a battle meeting `variant`, `battle` being its `(night, weather,
    arrangement)`: the variant's colors, else the classic look's for the
    battle (`map_variants.classic_sky`, `index` the map's GNS). None for a
    map with neither.
    """
    if variant is None:
        return None
    if variant.sky_top is not None and variant.sky_bottom is not None:
        return variant.sky_top, variant.sky_bottom
    return mv.classic_sky(index, *battle)


def rows_text(rows: dict) -> str:
    """`mod_rows`' rows as a text that is the same for the same rows, whatever order they went in."""
    return json.dumps({table: sorted([list(key), fields] for key, fields in found.items())
                       for table, found in rows.items()}, sort_keys=True, default=str)


def package_folder(parent: Path, number: int) -> Path:
    """A new folder for map `number`'s package in `parent`: never one already there."""
    first = parent / f"map_{number:03d}"
    if not first.exists():
        return first
    n = 2
    while (parent / f"map_{number:03d} ({n})").exists():
        n += 1
    return parent / f"map_{number:03d} ({n})"


class _ThreePanes(QObject):
    """Sizes a three pane splitter once it has a real width: the sides theirs, the middle the rest."""

    def __init__(self, splitter, left: int, right: int):
        super().__init__(splitter)
        self._left, self._right, self._done = left, right, False
        splitter.installEventFilter(self)

    def eventFilter(self, watched, event):                        # noqa: N802
        if (not self._done and event.type() == QEvent.Resize
                and watched.width() > self._left + self._right + 200):
            self._done = True
            middle = watched.width() - self._left - self._right - 2 * watched.handleWidth()
            watched.setSizes([self._left, middle, self._right])
        return False


class TilePanel(QWidget):
    """
    The picked tile's fields. Says `edited(field, value)` when one is
    changed, and `pick_alike()` when "Pick every ... tile" is pressed. With
    no tile picked it shows no fields, only what to do (Zodi's stress test of
    20 October: the last tile's values stayed in it, greyed).
    """

    edited = Signal(str, int)
    put_back = Signal()
    pick_alike = Signal()
    add_upper = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._loading = False
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(8)
        self.title = QLabel("Click a tile")
        self.title.setStyleSheet("font-weight: 600; font-size: 12pt;")
        column.addWidget(self.title)
        self.where = QLabel("")
        self.where.setProperty("role", "muted")
        self.where.setWordWrap(True)
        column.addWidget(self.where)
        # Every tile of the grid with the picked one's surface, in one go: 20
        # October's tundra painted its 109 grass tiles snow by Ctrl and click.
        self.alike_button = QPushButton("")
        self.alike_button.setToolTip("Picks every tile of this map with the same surface, so a change goes "
                                     "to all of them.")
        self.alike_button.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.alike_button.clicked.connect(self.pick_alike.emit)
        column.addWidget(self.alike_button)

        self.labels = {}
        self.surface = QComboBox()
        self.height = self._spin("height")
        self.slope = QComboBox()
        self.slope_height = self._spin("slope_height")
        self.depth = self._spin("depth")
        self.thickness = self._spin("thickness")
        ground = QGroupBox("Ground")
        form = QFormLayout(ground)
        for name, text, control in (("surface", "Surface", self.surface), ("height", "Height", self.height),
                                    ("slope", "Slope", self.slope),
                                    ("slope_height", "Slope height", self.slope_height),
                                    ("depth", "Depth", self.depth), ("thickness", "Thickness", self.thickness)):
            label = QLabel(text)
            self.labels[name] = label
            form.addRow(label, control)
        self.surface.setToolTip("What the ground is: which abilities work here, and how units move on it.")
        self.height.setToolTip("How high the tile is, in the game's height steps: a unit's jump and "
                               "the game's h numbers count them.")
        self.slope.setToolTip("Which corners of the tile rise, by the slope height.")
        self.slope_height.setToolTip("How far the tile's raised corners are above its height, in "
                                     "height steps. The game names a slope by its middle.")
        self.depth.setToolTip("How deep the water or swamp on the tile is.")
        self.thickness.setToolTip("How far the tile reaches down, in height steps.")
        column.addWidget(ground)
        # Picked upper level tiles units can't go under (`ROOM_ONE`), under the
        # height and thickness that decide it: shown only then, in the color
        # the pages warn in.
        self.room = QLabel("")
        self.room.setProperty("role", "attention")
        self.room.setWordWrap(True)
        self.room.setVisible(False)
        column.addWidget(self.room)

        use = QGroupBox("Units and the cursor")
        use_rows = QVBoxLayout(use)
        self.stand = QCheckBox("Units can stand here")
        self.cursor = QCheckBox("The cursor can stop here")
        self.cross = QCheckBox("Units cross it without stopping")
        self.cross.setToolTip("Units can't stop on this tile, but can move past it to the tiles beyond "
                              "(seen in the game). None of the game's own tiles has it.")
        for box in (self.stand, self.cursor, self.cross):
            use_rows.addWidget(box)
        column.addWidget(use)

        look = QGroupBox("Appearance")
        look_rows = QFormLayout(look)
        self.shading = QComboBox()
        self.shading.addItems(SHADINGS)
        self.shading.setToolTip("How dark the game draws the tile's highlight.")
        label = QLabel("Shading")
        self.labels["shading"] = label
        look_rows.addRow(label, self.shading)
        column.addWidget(look)

        # A tile on the upper level over each picked one that has none there
        # (`MapEditorPage.add_upper_level`): shown only then.
        self.upper_button = QPushButton(UPPER_BUTTON)
        self.upper_button.setToolTip(UPPER_TIP.format(steps=mc.UPPER_STEPS))
        self.upper_button.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.upper_button.clicked.connect(self.add_upper.emit)
        column.addWidget(self.upper_button)
        self.put_back_button = QPushButton("Put back the game's tile")
        self.put_back_button.clicked.connect(self.put_back.emit)
        self.put_back_button.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        column.addWidget(self.put_back_button)
        #: What is shown only while a tile is picked.
        self.fields = (ground, use, look, self.put_back_button)
        self.note = QLabel("")
        self.note.setProperty("role", "muted")
        self.note.setWordWrap(True)
        column.addWidget(self.note)
        column.addStretch(1)

        for slope, (name, _corners) in mc.SLOPES.items():
            self.slope.addItem(name, slope)
        self.surface.currentIndexChanged.connect(lambda _i: self._say("surface"))
        self.slope.currentIndexChanged.connect(lambda _i: self._say("slope"))
        self.shading.currentIndexChanged.connect(lambda _i: self._say("shading"))
        for name in ("height", "slope_height", "depth", "thickness"):
            getattr(self, name).valueChanged.connect(lambda _v, n=name: self._say(n))
        self.stand.toggled.connect(lambda _on: self._say("no_walk"))
        self.cursor.toggled.connect(lambda _on: self._say("no_cursor"))
        self.cross.toggled.connect(lambda _on: self._say("pass_through"))
        self.show_tile(None)

    def _spin(self, name: str) -> QSpinBox:
        box = FittedSpinBox(90)
        low, high = mc.field_range(name)
        box.setRange(low, high)
        return box

    def set_surface_names(self, names: dict) -> None:
        self._loading = True
        current = self.surface.currentData()
        self.surface.clear()
        for key in range(SURFACES):
            self.surface.addItem(names.get(key) or f"Surface {key}", key)
        if current is not None:
            self.surface.setCurrentIndex(self.surface.findData(current))
        self._loading = False

    def value(self, name: str) -> int:
        if name == "surface":
            return int(self.surface.currentData() or 0)
        if name == "slope":
            return int(self.slope.currentData() or 0)
        if name == "shading":
            return self.shading.currentIndex()
        if name == "no_walk":
            return int(not self.stand.isChecked())
        if name == "no_cursor":
            return int(not self.cursor.isChecked())
        if name == "pass_through":
            return int(self.cross.isChecked())
        return getattr(self, name).value()

    def _say(self, name: str) -> None:
        if not self._loading:
            self.edited.emit(name, self.value(name))

    def controls(self) -> list:
        return [self.surface, self.height, self.slope, self.slope_height, self.depth, self.thickness,
                self.stand, self.cursor, self.cross, self.shading, self.upper_button, self.put_back_button]

    def show_tile(self, tile, game=None, changed=(), count: int = 0, note: str = "",
                  names: dict = None, alike: int = 0, upper: int = 0, room: str = "") -> None:
        """
        Fills the fields from `tile` (as edited), `game` being the game's own;
        `changed` names the fields that differ; `alike` is how many tiles of
        the grid have its surface (the "Pick every ... tile" button's);
        `upper` how many of the tiles picked have no upper level tile over
        them (Add an upper level's); `room` what to say of picked upper level
        tiles units can't go under ("" for none). None empties the panel: no
        fields, only what to do.
        """
        self._loading = True
        enabled = tile is not None
        for control in self.controls():
            control.setEnabled(enabled)
        for widget in self.fields:
            widget.setVisible(enabled)
        self.upper_button.setVisible(enabled and upper > 0)
        self.room.setText(room if enabled else "")
        self.room.setVisible(enabled and bool(room))
        surface_name = ((names or {}).get(tile.get("surface")) or f"Surface {tile.get('surface')}"
                        if tile is not None else "")
        self.alike_button.setText(f"Pick every {surface_name} tile ({alike})" if alike else "")
        self.alike_button.setVisible(enabled and alike > count)
        if tile is None:
            self.title.setText("Click a tile")
            self.where.setText("Pick a tile on the map to see and change it. Ctrl and click picks more "
                               "than one, and Ctrl and drag picks every tile in a box.")
            self.note.setText(note)
            for label in self.labels.values():
                self._mark(label, False, "")
            for box in (self.stand, self.cursor, self.cross):
                self._mark(box, False, "")
            self._loading = False
            return
        self.title.setText(f"Tile {tile.x}, {tile.z}" if count <= 1 else f"{count} tiles")
        level = "Upper level" if tile.level else "Lower level"
        self.where.setText(level + "." if count <= 1 else
                           f"A change goes to all {count}. Showing tile {tile.x}, {tile.z}, "
                           f"{level.lower()}.")
        self.surface.setCurrentIndex(self.surface.findData(tile.get("surface")))
        self.height.setValue(tile.get("height"))
        slope = tile.get("slope")
        if self.slope.findData(slope) < 0:
            self.slope.addItem(f"Other ({slope})", slope)
        self.slope.setCurrentIndex(self.slope.findData(slope))
        self.slope_height.setValue(tile.get("slope_height"))
        self.depth.setValue(tile.get("depth"))
        self.thickness.setValue(tile.get("thickness"))
        self.stand.setChecked(not tile.no_walk)
        self.cursor.setChecked(not tile.no_cursor)
        self.cross.setChecked(bool(tile.pass_through))
        self.shading.setCurrentIndex(tile.get("shading"))
        game = game or tile
        said = {"surface": lambda v: (names or {}).get(v) or f"Surface {v}",
                "slope": lambda v: mc.SLOPES.get(v, (f"Other ({v})",))[0],
                "shading": lambda v: SHADINGS[v]}
        for name, label in self.labels.items():
            was = game.get(name)
            self._mark(label, name in changed, f"The game has {said.get(name, str)(was)}."
                       if name in changed else "")
        for name, box in (("no_walk", self.stand), ("no_cursor", self.cursor),
                          ("pass_through", self.cross)):
            self._mark(box, name in changed, "The game has it the other way." if name in changed
                       else "")
        self.put_back_button.setEnabled(bool(changed) or count > 1)
        self.note.setText(note)
        self._loading = False

    @staticmethod
    def _mark(widget, edited: bool, tip: str) -> None:
        """
        An edited field's label in the edited colour and bold, the game's
        value on hover. The colour first: polishing the label for it gives
        it the style's font again, so a font set before was lost until the
        next time (Zodi's stress test of 20 October: the newest field
        changed was green, not bold).
        """
        if isinstance(widget, QLabel) and (widget.property("role") == "ok") != edited:
            widget.setProperty("role", "ok" if edited else None)
            widget.style().unpolish(widget)
            widget.style().polish(widget)
        font = widget.font()
        if font.bold() != edited:
            font.setBold(edited)
            widget.setFont(font)
        widget.setToolTip(tip)


class MapEditorPage(QWidget):
    edits_changed = Signal()
    #: A picture's path in the game, for the Textures page to open at.
    jump_to_texture = Signal(str)
    #: What the line under the map says: what the mouse does.
    TILE_HINT = ("Drag to turn the map, Shift and drag to move it, and use the wheel to zoom. Ctrl and "
                 "click picks more than one tile, and Ctrl and drag every tile in a box.")

    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state
        self.number = None
        #: The look chosen, and the one shown: a map with no enhanced files
        #: is shown classic without changing the choice, so the next map
        #: that has them comes back enhanced.
        self.look = ms.ENHANCED
        self.shown_look = ms.ENHANCED
        #: which of the map's lightings the enhanced look is drawn with
        self.lighting = 0
        self.scene = None
        #: The grid edits are made on, `{(x, z, level): Tile}`: the game's,
        #: or the opened mod's own copy when it carries one (`read_only`).
        self.game_tiles = {}
        #: `{file name: path}`: this grid's files the opened mod carries whole.
        self.carried = {}
        self.read_only = False
        #: The tiles picked, the first being the one the panel shows.
        self.picked = []
        self.index = None               # the map's `MapIndex`
        self.numbers = []               # the maps listed
        self.enhanced_numbers = set()
        self.surface_name = {}
        self.height_text = {}
        #: Readings asked for, and the one being made: one at a time, the
        #: latest wanted started when the one running is done.
        self._wanted = 0
        self._token = 0
        self._running = False
        self.scenes_loaded = 0
        self._game_dir = None
        #: The last folder Save for editing wrote.
        self.last_package = None
        #: `(map, grid key, {(x, z, level): {field: value}})`: where the tiles
        #: under the last model loaded go, while that is offered.
        self.ground = None
        #: `(map, grid key, {(x, z, level): {field: value}})`: the tiles a
        #: package loaded was saved with, offered when the mod has others.
        self.package_tiles = None
        #: `(map, {(x, z, level): [map_battles.TileUse]})`: the tiles the map
        #: shown's battles use, read when it is drawn (`battle_uses`).
        self._battles = None
        #: `((game folder, program), {event: setup record})`: the game's
        #: events, read once a game (`game_records`).
        self._records = None
        #: `look_inputs` of the scene asked for last, and of the scene shown.
        self._reading_inputs = self._shown_inputs = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 10, 24, 20)
        outer.setSpacing(10)
        outer.addLayout(actions.page_intro(INTRO))
        self.counter = QLabel("")
        self.counter.setProperty("role", "ok")
        outer.addWidget(self.counter)

        split = QSplitter(Qt.Horizontal)
        split.setHandleWidth(14)
        split.setChildrenCollapsible(False)
        self.split = split

        # -- left: the maps -------------------------------------------------
        left_box = QWidget()
        left = QVBoxLayout(left_box)
        left.setContentsMargins(0, 0, 0, 0)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search by number or name")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._on_filter)
        left.addWidget(self.search)
        self.map_list = QListWidget()
        self.map_list.setAlternatingRowColors(True)
        self.map_list.setUniformItemSizes(True)
        self.map_list.currentItemChanged.connect(self._on_map_item)
        left.addWidget(self.map_list, 1)
        left_box.setMinimumWidth(240)
        split.addWidget(left_box)

        # -- centre: the map and how it is seen -------------------------------
        centre_box = QWidget()
        centre = QVBoxLayout(centre_box)
        centre.setContentsMargins(0, 0, 0, 0)
        centre.setSpacing(8)
        self.title = QLabel("Pick a map")
        self.title.setStyleSheet("font-weight: 600; font-size: 12pt;")
        centre.addWidget(self.title)

        # The two rows over the map WRAP (`FlowLayout`), in groups that stay
        # together. At the window's 1345 minimum the map gets about 500 px,
        # and one line of the classic look's boxes, or of the camera's
        # buttons, is over 700: in a plain row they were squeezed until
        # "Turn right" read "urn righ".
        look_row = FlowLayout(spacing=18)
        self.look_group = QButtonGroup(self)
        self.enhanced_button = QRadioButton("Enhanced")
        self.classic_button = QRadioButton("Classic")
        self.enhanced_button.setChecked(True)
        for button in (self.enhanced_button, self.classic_button):
            self.look_group.addButton(button)
        look_row.addWidget(_together(QLabel("Look"), self.enhanced_button, self.classic_button))
        self.enhanced_button.toggled.connect(self._on_look)
        self.arrangement_label = QLabel("Arrangement")
        self.arrangement_box = QComboBox()
        self.arrangement_box.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.arrangement_box.setToolTip("Some maps are laid out more than one way, for different "
                                        "battles.")
        self.lighting_label = QLabel("Lighting")
        self.lighting_box = QComboBox()
        self.lighting_box.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.lighting_box.setToolTip("Some maps are lit more than one way: in different story "
                                     "battles, or in random battles.")
        self.lighting_group = _together(self.lighting_label, self.lighting_box)
        self.lighting_group.setVisible(False)
        self.time_label = QLabel("Time")
        self.time_box = QComboBox()
        self.weather_label = QLabel("Weather")
        self.weather_box = QComboBox()
        self.weather_box.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.arrangement_group = _together(self.arrangement_label, self.arrangement_box)
        self.time_group = _together(self.time_label, self.time_box)
        self.weather_group = _together(self.weather_label, self.weather_box)
        # The classic look's, shown when a map is drawn in it (Zodi's stress
        # test of 20 October: they showed in the enhanced look before a map
        # was picked).
        self.time_group.setVisible(False)
        self.weather_group.setVisible(False)
        for group in (self.arrangement_group, self.lighting_group, self.time_group, self.weather_group):
            look_row.addWidget(group)
        self.arrangement_box.currentIndexChanged.connect(self._on_arrangement)
        self.lighting_box.currentIndexChanged.connect(self._on_lighting)
        self.time_box.currentIndexChanged.connect(self._on_time)
        self.weather_box.currentIndexChanged.connect(self._on_variant)
        centre.addLayout(look_row)

        camera_row = FlowLayout(spacing=18)
        self.turn_left = QPushButton("Turn left")
        self.turn_right = QPushButton("Turn right")
        self.higher = QPushButton("Higher")
        self.lower = QPushButton("Lower")
        self.above = QPushButton("From above")
        self.turn_left.setToolTip("To the next of the game's four camera corners. The map says which it is.")
        self.turn_right.setToolTip("To the next of the game's four camera corners. The map says which it is.")
        self.higher.setToolTip("To the game's higher camera.")
        self.lower.setToolTip("To the game's lower camera.")
        self.above.setToolTip("Straight down on the map.")
        self.turn_left.clicked.connect(lambda: self.turn(1))
        self.turn_right.clicked.connect(lambda: self.turn(-1))
        self.higher.clicked.connect(lambda: self.tilt(1))
        self.lower.clicked.connect(lambda: self.tilt(-1))
        self.above.clicked.connect(self.from_above)
        camera_row.addWidget(_together(QLabel("Camera"), self.turn_left, self.turn_right))
        camera_row.addWidget(_together(self.higher, self.lower, self.above))
        # As the person left them last time, like the view toggles above the tabs.
        saved = ui_settings.load()
        self.show_tiles = QCheckBox("Show tiles")
        self.show_tiles.setChecked(bool(saved.get("map_show_tiles", True)))
        self.show_tiles.toggled.connect(self._on_show_tiles)
        self.show_info = QCheckBox("Show tile info")
        self.show_info.setChecked(bool(saved.get("map_show_tile_info", True)))
        self.show_info.setToolTip("The card beside the pointer, saying the surface and height of "
                                  "the tile it is on.")
        self.show_info.toggled.connect(self._on_show_info)
        #: The tiles this map's battles use (`map_battles`), asked for after
        #: Zodi's stress test of 20 October: nothing showed them.
        self.show_battles = QCheckBox("Show battles")
        self.show_battles.setChecked(bool(saved.get("map_show_battles", False)))
        self.show_battles.setToolTip("Marks the tiles this map's battles use: in blue the squares where "
                                     "the player places units, in amber where a battle's units start. "
                                     "Pointing at one says which.")
        self.show_battles.toggled.connect(self._on_show_battles)
        #: N, E, S and W round the grid and the camera's corner (Zodi's
        #: stress test of 20 October), off until ticked (Zodi, 21 October:
        #: "for first time users it should start disabled").
        self.show_directions = QCheckBox("Show directions")
        self.show_directions.setChecked(bool(saved.get("map_show_compass", False)))
        self.show_directions.setToolTip("Marks N, E, S and W round the map and says which corner it is seen "
                                        "from: the directions Light the map's sun goes by.")
        self.show_directions.toggled.connect(self._on_show_directions)
        # A row of their own: with Show directions the four no longer fit
        # beside the camera's buttons in a window 1920 wide.
        view_row = FlowLayout(spacing=18)
        view_row.addWidget(_together(self.show_tiles, self.show_info, self.show_battles,
                                     self.show_directions))
        centre.addLayout(camera_row)
        centre.addLayout(view_row)

        model_row = FlowLayout(spacing=18)
        self.save_package_button = QPushButton("Save for editing")
        self.save_package_button.setToolTip(
            "Writes the enhanced look's model and textures to a folder, for Blender or any 3D "
            "program: an OBJ, PNGs, and a README saying how to edit them.")
        self.save_package_button.clicked.connect(lambda: self.save_package())
        self.load_package_button = QPushButton("Load edited")
        self.load_package_button.setToolTip(
            "Builds a folder saved with Save for editing back into the map. It is drawn from it "
            "here and goes into your mod.")
        self.load_package_button.clicked.connect(lambda: self.load_package())
        self.put_back_look_button = QPushButton("Put back the game's look")
        self.put_back_look_button.setToolTip("Takes this map's model and textures out of your mod, and gives its "
                                             "tiles the game's heights again.")
        self.put_back_look_button.clicked.connect(lambda: self.put_back_look())
        #: Zodi, 12 October: the lighting textures, the border's and the
        #: units' lighting made from a sun, the sky and lamps (`map_light`).
        self.light_button = QPushButton("Light the map")
        self.light_button.setToolTip(
            "Makes the map's lighting textures, its border texture and its units' lighting from a "
            "sun, the sky and lamps you set.")
        self.light_button.clicked.connect(lambda: self.open_light())
        self.light_dialog = None
        #: `(map, {texture name: file}, {table: {key: fields}})` drawn in place
        #: of the mod's own while Light the map shows a preview.
        self.light_preview = None
        self.sky_button = QPushButton(SKY_BUTTON)
        self.sky_button.setToolTip(SKY_TIP)
        self.sky_button.clicked.connect(lambda: self.open_sky())
        self.sky_dialog = None
        model_row.addWidget(_together(QLabel("Model and textures"), self.save_package_button,
                                      self.load_package_button, self.light_button))
        # A widget of its own in the row, so it wraps there rather than
        # holding the map's pane wider at the window's narrowest.
        model_row.addWidget(self.sky_button)
        #: Zodi, 21 October: a look on a map number of its own, for a battle
        #: there (`copy_look`), one of the game's spare numbers
        #: (`map_package.copy_targets`), picked from its menu.
        self.copy_button = QPushButton(COPY_BUTTON)
        self.copy_button.setToolTip(COPY_TIP)
        self.copy_menu = QMenu(self.copy_button)
        self.copy_menu.aboutToShow.connect(self._fill_copy_menu)
        self.copy_button.setMenu(self.copy_menu)
        model_row.addWidget(self.copy_button)
        model_row.addWidget(self.put_back_look_button)
        #: For a look with no highlight panels (33 of the game's: no battle of
        #: the game's is fought on them), panels made from the tiles
        #: (`map_enhanced.with_grid_panels`), so a battle a mod puts there
        #: shows where units can move and act.
        self.panels_button = QPushButton(PANELS_BUTTON)
        self.panels_button.setToolTip(PANELS_TIP)
        self.panels_button.clicked.connect(lambda: self.add_panels())
        self.panels_button.setVisible(False)
        model_row.addWidget(self.panels_button)
        #: Offered after Load edited when the model's ground moved: the tiles
        #: under it follow, so units stand on it (`ground`).
        self.follow_ground_button = QPushButton("Move the tiles to the model")
        self.follow_ground_button.setToolTip(
            "Raises or lowers each tile whose ground moved in the model you loaded, as far as "
            "the ground did, so units stand on it. Put back undoes a tile.")
        self.follow_ground_button.clicked.connect(lambda: self.follow_ground())
        self.follow_ground_button.setVisible(False)
        model_row.addWidget(self.follow_ground_button)
        #: Offered after Load edited when the folder's tiles aren't the mod's
        #: (`package_tiles`): a mod with no tiles of its own takes them at once.
        self.use_tiles_button = QPushButton("Use the folder's tiles")
        self.use_tiles_button.setToolTip(
            "Gives this map the tiles the folder was saved with (their surfaces, heights and the "
            "rest), in place of the ones your mod has now.")
        self.use_tiles_button.clicked.connect(lambda: self.use_package_tiles())
        self.use_tiles_button.setVisible(False)
        model_row.addWidget(self.use_tiles_button)
        centre.addLayout(model_row)

        self.view = MapView()
        self.view.show_grid = self.show_tiles.isChecked()
        self.view.show_info = self.show_info.isChecked()
        # N, E, S and W round the grid, and the corner the camera is at: what
        # Light the map's compass and parts.txt's corners go by. Show directions.
        self.view.show_compass = self.show_directions.isChecked()
        self.view.describe = self.describe
        self.view.tile_clicked.connect(self._on_tile_clicked)
        self.view.box_select = True
        self.view.tiles_boxed.connect(self._on_tiles_boxed)
        self.view.customContextMenuRequested.connect(self._view_menu)
        centre.addWidget(self.view, 1)
        self.hint = QLabel(self.TILE_HINT)
        self.hint.setProperty("role", "muted")
        self.hint.setWordWrap(True)
        centre.addWidget(self.hint)
        #: What the model and texture buttons did, or why they couldn't.
        self.look_note = QLabel("")
        self.look_note.setWordWrap(True)
        self.look_note.setTextInteractionFlags(Qt.TextSelectableByMouse)
        centre.addWidget(self.look_note)
        self._package_busy = False
        split.addWidget(centre_box)
        self.centre_box = centre_box

        # -- right: the tile ---------------------------------------------------
        # Load edited, Light the map and Put back the game's look change a
        # map's look: counted and marked as tile edits are.
        self.edits_changed.connect(self._looks_changed)
        self.panel = TilePanel()
        self.panel.edited.connect(self._on_field)
        self.panel.put_back.connect(self.put_back)
        self.panel.add_upper.connect(self.add_upper_level)
        self.panel.pick_alike.connect(self.pick_alike)
        self.panel.setMinimumWidth(300)
        # Scrolled when the window is too short for it all, so it never holds
        # the window taller than the screen.
        self.panel_scroll = QScrollArea()
        self.panel_scroll.setWidgetResizable(True)
        self.panel_scroll.setFrameShape(QFrame.NoFrame)
        self.panel_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.panel_scroll.setWidget(self.panel)
        split.addWidget(self.panel_scroll)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setStretchFactor(2, 0)
        self._sizer = _ThreePanes(split, MAP_LIST_WIDTH, SIDE_WIDTH)
        outer.addWidget(split, 1)

        self.empty_note = QLabel(NO_GAME)
        self.empty_note.setProperty("role", "muted")
        self.empty_note.setWordWrap(True)
        self.empty_note.setAlignment(Qt.AlignTop)
        outer.addWidget(self.empty_note, 1)

        self.refresh_tree()

    # -- the shell's questions ---------------------------------------------------

    def view_toggles_used(self) -> tuple:
        """
        `(notes, unknown, comments)`: none of the three. The page has no field
        notes, unknown fields or comment rows for them to hide.
        """
        return (False, False, False)

    def select_record(self, number) -> bool:
        """Picks a map by its number: what a jump from another page carries."""
        return actions.select_list_row(self.map_list, int(number), self.search)

    # -- the maps ----------------------------------------------------------------------

    def game_dir(self):
        folder = getattr(self.state, "nxd_unpack_dir", None)
        return Path(folder) if folder else None

    def map_folder(self):
        game = self.game_dir()
        return game / mc.MAP_FOLDER if game is not None else None

    def refresh_tree(self) -> None:
        """
        Re-reads the game's maps and the edit store.

        Re-read, not kept: opening a mod REPLACES `state.map_edits`, and a
        page holding the old dict would show and save the last mod's tiles.
        """
        folder = self.map_folder()
        numbers = []
        if folder is not None and folder.is_dir():
            for n in mc.map_numbers(folder):
                try:
                    if mc.read_gns(folder, n).states():
                        numbers.append(n)
                except OSError:
                    continue
        game = self.game_dir()
        changed_game = game != self._game_dir
        self._game_dir = game
        self.numbers = numbers
        self.enhanced_numbers = set(me.mesh_numbers(game)) if game is not None else set()
        has_data = bool(numbers)
        actions.set_empty_state(self.empty_note, has_data, self.split, self.counter)
        self._read_names()
        names = map_names(self.state)
        current = self.number
        self.map_list.blockSignals(True)
        self.map_list.clear()
        for n in numbers:
            item = QListWidgetItem(map_label(n, names.get(n, "")))
            item.setData(Qt.UserRole, n)
            self.map_list.addItem(item)
        self.map_list.blockSignals(False)
        self._mark_list()
        self._update_counter()
        self._on_filter(self.search.text())
        if current not in numbers:
            self._forget_map()
            return
        self.map_list.blockSignals(True)
        actions.select_list_row(self.map_list, current)
        self.map_list.blockSignals(False)
        if changed_game:
            self.number = None          # another game's map of that number: read afresh
            self._open_map(current)
        elif self.scene is not None and self._shown_inputs != self.look_inputs(current):
            # The mod's look of the map shown changed under the page (a mod
            # opened, or Start a new mod: Zodi, 22 October, an edited map's
            # textures still drawn after it): read afresh.
            self._load()
        else:
            # The store may be a new one (a mod opened, or cleared).
            self._grid_changed()
        if self.sky_dialog is not None and self.sky_dialog.isVisible():
            self.sky_dialog.close()
        self.sky_dialog = None
        self._update_sky()
        self._update_look_buttons()

    def _forget_map(self) -> None:
        self.number = None
        self.index = None
        self.scene = None
        self.game_tiles = {}
        self.picked = []
        self.view.set_scene(None)
        self.view.set_sky(None)
        self.view.set_message("Pick a map on the left." if self.numbers else "")
        self.title.setText("Pick a map")
        self._show_panel()
        self._update_look_buttons()

    def _read_names(self) -> None:
        sqlite_path = getattr(self.state, "nxd_sqlite_path", None)
        language = names_language(sqlite_path)
        self.surface_name = surface_names(sqlite_path, language)
        self.height_text = height_labels(sqlite_path, language)
        self.panel.set_surface_names(self.surface_name)
        self._show_panel()
        self.view.update()

    def edited_numbers(self) -> set:
        """
        The maps the mod changes on this page: their tiles, or their look (a
        model, textures or rows Load edited or Light the map put in:
        `map_looks`). Until 20 October only tiles counted, so a map made
        with Load edited wasn't counted or marked (Zodi's stress test).
        """
        return set(self.state.edited_map_numbers()) | set(map_looks(self.state))

    def _looks_changed(self) -> None:
        self._mark_list()
        self._update_counter()

    def _mark_list(self) -> None:
        edited = self.edited_numbers()
        for i in range(self.map_list.count()):
            item = self.map_list.item(i)
            actions.mark_edited(item, item.data(Qt.UserRole) in edited)

    def _update_counter(self) -> None:
        listed = set(self.numbers)
        edited = len([n for n in self.edited_numbers() if n in listed])
        text = actions.edit_counter_text(edited, len(self.numbers), "maps") if self.numbers else ""
        tiles = self.state.edited_map_tile_count()
        if text and tiles:
            text += f", {tiles:,} tile{'s' if tiles != 1 else ''} in all"
        self.counter.setText(text)

    def _on_filter(self, text: str) -> None:
        needle = text.strip().lower()
        for i in range(self.map_list.count()):
            item = self.map_list.item(i)
            item.setHidden(bool(needle) and needle not in item.text().lower())

    def _on_map_item(self, current, _previous) -> None:
        if current is not None:
            self._open_map(current.data(Qt.UserRole))

    # -- one map ------------------------------------------------------------------------

    def _open_map(self, number: int) -> None:
        folder = self.map_folder()
        if folder is None:
            return
        new_map = number != self.number
        self.number = number
        try:
            self.index = mc.read_gns(folder, number)
        except OSError as exc:
            self.index = None
            self.view.set_message(f"This map could not be read: {exc}")
            return
        self.title.setText(self._title(number))
        # A look copied here (`copy_look`) is this map's enhanced one.
        has_enhanced = number in self.enhanced_numbers or self.mod_look(number)[0] is not None
        self.enhanced_button.setEnabled(has_enhanced)
        self.enhanced_button.setToolTip("" if has_enhanced else
                                        "This map has no enhanced look in the game's files.")
        if new_map:
            self.picked = []
            self.view.camera = Camera()
            # The new map's lightings come with its scene; until then, none.
            self.lighting = 0
            self.lighting_box.blockSignals(True)
            self.lighting_box.clear()
            self.lighting_box.blockSignals(False)
            self._fill_arrangements()
            self._say_look("")
        self.shown_look = self.look if has_enhanced else ms.CLASSIC
        if (self.shown_look == ms.CLASSIC) != self.classic_button.isChecked():
            self.enhanced_button.blockSignals(True)
            (self.classic_button if self.shown_look == ms.CLASSIC
             else self.enhanced_button).setChecked(True)
            self.enhanced_button.blockSignals(False)
        self._show_variant_boxes()
        self._load()

    def _title(self, number: int) -> str:
        """"Map 048, Sal Ghidos Slumtown", and the map whose look it has when one was copied there."""
        names = map_names(self.state)
        text = f"Map {number:03d}, {names[number]}" if names.get(number) else f"Map {number:03d}"
        source = (getattr(self.state, "map_copies", None) or {}).get(number)
        return text + (COPY_TITLE.format(source=source) if source is not None else "")

    def _fill_arrangements(self) -> None:
        arrangements = self.index.arrangements() if self.index else []
        self.arrangement_box.blockSignals(True)
        self.arrangement_box.clear()
        for a in arrangements:
            self.arrangement_box.addItem(arrangement_word(a), a)
        self.arrangement_box.blockSignals(False)
        self.arrangement_box.setEnabled(len(arrangements) > 1)
        self._fill_times()

    def _fill_times(self) -> None:
        arrangement = self.arrangement_box.currentData() or 0
        nights = sorted({s.night for s in (self.index.states() if self.index else [])
                         if s.arrangement == arrangement})
        chosen = self.time_box.currentData()
        self.time_box.blockSignals(True)
        self.time_box.clear()
        for night in nights:
            self.time_box.addItem("Night" if night else "Day", night)
        if chosen in nights:
            self.time_box.setCurrentIndex(nights.index(chosen))
        self.time_box.blockSignals(False)
        self.time_box.setEnabled(len(nights) > 1)
        self._fill_weathers()

    def _fill_weathers(self) -> None:
        arrangement = self.arrangement_box.currentData() or 0
        night = bool(self.time_box.currentData())
        weathers = sorted({s.weather for s in (self.index.states() if self.index else [])
                           if s.arrangement == arrangement and s.night == night})
        chosen = self.weather_box.currentData()
        self.weather_box.blockSignals(True)
        self.weather_box.clear()
        for w in weathers:
            self.weather_box.addItem(mc.WEATHERS[w] if w < len(mc.WEATHERS) else f"Weather {w}", w)
        if chosen in weathers:
            self.weather_box.setCurrentIndex(weathers.index(chosen))
        self.weather_box.blockSignals(False)
        self.weather_box.setEnabled(len(weathers) > 1)

    def _show_variant_boxes(self) -> None:
        classic = self.shown_look == ms.CLASSIC
        for group in (self.time_group, self.weather_group):
            group.setVisible(classic)
        self.lighting_group.setVisible(not classic and self.lighting_box.count() > 1)

    def _fill_lightings(self) -> None:
        """The lighting box: the shown map's lightings, when it has more than one."""
        lightings = self.scene.lightings if self.scene is not None else []
        self.lighting_box.blockSignals(True)
        self.lighting_box.clear()
        events = self.lighting_events() if len(lightings) > 1 else {}
        for i, word in enumerate(lighting_words(lightings)):
            self.lighting_box.addItem(word, i)
            self.lighting_box.setItemData(i, lighting_tip(lightings[i], events), Qt.ToolTipRole)
        if lightings:
            self.lighting_box.setCurrentIndex(self.scene.lighting)
        self.lighting_box.blockSignals(False)
        self._show_variant_boxes()
        self._update_sky()

    # -- the map's variants: the battles each lighting is for, and the sky ---------------

    def game_records(self) -> dict:
        """
        The game's events' setup records (`map_variants.game_records`): its
        program's, found beside the .pac files General Setup has, else the
        unpacked game's PlayStation table; read once a game.
        """
        program = game_install.find_program(ui_settings.load().get("game_data_folder") or None)
        key = (str(self.game_dir()), str(program))
        if self._records is None or self._records[0] != key:
            self._records = (key, mv.game_records(self.game_dir(), program))
        return self._records[1]

    def variants(self, number=None) -> list:
        """Map `number`'s variants (the shown one's by default), the mod's `Map` row over the game's."""
        number = self.number if number is None else number
        if number is None:
            return []
        store = getattr(self.state, "unmodelled_table_edits", None) or {}
        return mv.read_variants(getattr(self.state, "nxd_sqlite_path", None), number, store.get(mpk.MAP_TABLE))

    def game_variants(self, number=None) -> list:
        """
        Map `number`'s variants as the game has them: for a look copied there,
        as the game has them where it came from.
        """
        number = self.number if number is None else number
        if number is None:
            return []
        number = (getattr(self.state, "map_copies", None) or {}).get(number, number)
        return mv.read_variants(getattr(self.state, "nxd_sqlite_path", None), number)

    def lighting_events(self, number=None) -> dict:
        """
        `{story index: [events]}`: the events set on map `number` (the shown
        one's by default), with the mod's setup changes, by the story lighting
        each meets (`map_variants.events_by_story_index`).
        """
        number = self.number if number is None else number
        variants = self.variants(number)
        if not variants:
            return {}
        setups = mv.setups(self.game_records(), getattr(self.state, "setup_edits", None))
        sets = mv.event_sets(getattr(self.state, "nxd_sqlite_path", None))
        return mv.events_by_story_index(variants, setups, number, sets)

    def variant_events(self, number=None) -> dict:
        """
        `{variant index: [(event, night, weather, arrangement)]}`: the events
        set on map `number` (the shown one's by default), with the mod's
        setup changes, by the variant each meets (`map_variants.events_by_variant`).
        """
        number = self.number if number is None else number
        variants = self.variants(number)
        if not variants:
            return {}
        setups = mv.setups(self.game_records(), getattr(self.state, "setup_edits", None))
        sets = mv.event_sets(getattr(self.state, "nxd_sqlite_path", None))
        return mv.events_by_variant(variants, setups, number, sets)

    def own_sky(self, variant):
        """
        `(top, bottom, (night, weather, arrangement), events)`: the sky the
        game draws for `variant` of the map shown where it names no colors
        (Zodi, 22 October: "some maps that have skys in game but they do not
        appear in mod studio"): the map's classic look's for the battle most
        of its events are (`map_variants.sky_state`, `classic_sky`), with
        those events. None where the classic files have no lights for it.
        """
        if variant is None or self.index is None:
            return None
        met = self.variant_events().get(variant.index, [])
        battle = mv.sky_state(variant, met, self.arrangement_box.currentData() or 0)
        sky = mv.classic_sky(self.index, *battle)
        if sky is None:
            return None
        return sky[0], sky[1], battle, [m[0] for m in met if tuple(m[1:]) == battle]

    def variant_label(self, variant, number=None) -> str:
        """A variant's row in Sky colors: its lighting's name, and its events or its random battle."""
        number = self.number if number is None else number
        variants = self.variants(number)
        kind, index = ("random", variant.random - 1) if variant.random else ("story", mv.story_index(variants, variant))
        lightings = self.scene.lightings if self.scene is not None and number == self.number else []
        words = lighting_words(lightings)
        word = next((w for w, lighting in zip(words, lightings) if (kind, index) in (lighting.same or ())), None)
        if kind == "random":
            return word or f"Random battle {variant.random}"
        word = word or ("Usual" if index == 0 else f"Story {index + 1}")
        events = self.lighting_events(number).get(index, [])
        if not events:
            return f"{word}: no event"
        return f"{word}: event{'s' if len(events) != 1 else ''} {mb.runs(events)}"

    def shown_variant(self):
        """The variant of the lighting shown (its first, for a lighting several share), or None."""
        if self.scene is None or self.scene.look != ms.ENHANCED:
            return None
        variants = self.variants()
        if not variants:
            return None
        lightings = self.scene.lightings or []
        shown = lightings[self.scene.lighting] if 0 <= self.scene.lighting < len(lightings) else None
        kind, index = (shown.same[0] if shown.same else (shown.kind, shown.index)) if shown else ("story", 0)
        if kind == "random":
            return mv.random_variant(variants, index + 1) or variants[0]
        story = mv.story_variants(variants)
        return story[index] if kind == "story" and index < len(story) else variants[0]

    def _update_sky(self) -> None:
        """
        The shown lighting's sky behind the map: its colors, or where it
        names none the map's own, as the game draws it (`own_sky`). The
        classic look has the page's own background.
        """
        variant = self.shown_variant()
        top, bottom = (variant.sky_top, variant.sky_bottom) if variant is not None else (None, None)
        if variant is not None and (top is None or bottom is None):
            own = self.own_sky(variant)
            top, bottom = (own[0], own[1]) if own is not None else (None, None)
        self.view.set_sky((QColor(*top), QColor(*bottom)) if top and bottom else None)

    def set_sky(self, index: int, top, bottom) -> None:
        """
        Variant `index` of the map shown with these sky colors (`(r, g, b)`,
        or None: none named) in the mod's `Map` row; the column back to the
        game's when every variant is the game's again (a copy keeps its row).
        """
        number = self.number
        if number is None:
            return
        variants = mv.with_sky(self.variants(number), index, top, bottom)
        store = self.state.unmodelled_table_edits
        if store is None:
            store = self.state.unmodelled_table_edits = {}
        rows = store.setdefault(mpk.MAP_TABLE, {})
        row = dict(rows.get(number) or {})
        copied = number in (getattr(self.state, "map_copies", None) or {})
        game = [v.values for v in self.game_variants(number)]
        if [v.values for v in variants] == game and not copied:
            row.pop(mv.VARIANTS_COLUMN, None)
            said = SKY_GAME
        else:
            row[mv.VARIANTS_COLUMN] = mv.variants_text(variants)
            said = SKY_SET
        if row:
            rows[number] = row
        else:
            rows.pop(number, None)
        if not rows:
            store.pop(mpk.MAP_TABLE, None)
        self._say_look(said.format(number=number), "ok")
        self._update_sky()
        self._looks_changed()
        self._update_look_buttons()
        self.edits_changed.emit()

    def open_sky(self):
        """Opens Sky colors for the map shown, and returns it."""
        from .map_sky import SkyDialog
        if self.number is None:
            return None
        if self.sky_dialog is not None and self.sky_dialog.number != self.number:
            self.sky_dialog.close()
            self.sky_dialog = None
        if self.sky_dialog is None:
            self.sky_dialog = SkyDialog(self)
        self.sky_dialog.show()
        self.sky_dialog.raise_()
        return self.sky_dialog

    def _on_lighting(self, index) -> None:
        if index >= 0:
            self.lighting = int(self.lighting_box.itemData(index) or 0)
            self._load()

    def map_state(self) -> mc.State:
        """The variant shown: the enhanced look has its arrangement, by day and in no weather."""
        arrangement = self.arrangement_box.currentData() or 0
        if self.shown_look != ms.CLASSIC:
            ordered = [s for s in (self.index.states() if self.index else [])
                       if s.arrangement == arrangement]
            return ordered[0] if ordered else mc.State(arrangement)
        return mc.State(arrangement, bool(self.time_box.currentData()),
                        int(self.weather_box.currentData() or 0))

    def _on_look(self, _on) -> None:
        self.look = self.shown_look = (ms.ENHANCED if self.enhanced_button.isChecked()
                                       else ms.CLASSIC)
        self._show_variant_boxes()
        if self.number is not None:
            self._load()

    def _on_arrangement(self, _index) -> None:
        self._fill_times()
        self._load()

    def _on_time(self, _index) -> None:
        self._fill_weathers()
        self._load()

    def _on_variant(self, _index) -> None:
        self._load()

    def _load(self) -> None:
        """
        Reads the map in the look and variant chosen, on a worker thread.

        One reading at a time: going down the list with the arrow keys asks
        for a map per key, and each enhanced one decodes tens of megabytes
        of pictures. What arrives for a map no longer wanted is dropped and
        the latest one asked for is read next.
        """
        if self.game_dir() is None or self.number is None:
            return
        self._wanted += 1
        self.view.set_message(f"Reading map {self.number:03d}...")
        if not self._running:
            self._start_reading()

    def look_inputs(self, number) -> tuple:
        """
        What map `number`'s scene is drawn from in the mod: its model, its
        textures, its rows, its anim file and the grids it carries whole.
        Compared with the shown scene's (`_shown_inputs`) when the mod may
        have changed (`refresh_tree`).
        """
        mesh_file, picture_files = self.mod_look(number)
        return (str(mesh_file), tuple(sorted((str(k).lower(), str(v)) for k, v in (picture_files or {}).items())),
                rows_text(self.mod_rows(number)), str(mod_anim(self.state, number)), terrains_of(self.state, number))

    def _start_reading(self) -> None:
        self._running = True
        self._token = self._wanted
        self._reading_inputs = self.look_inputs(self.number)
        mesh_file, picture_files = self.mod_look(self.number)
        rows = self.mod_rows(self.number)
        if self.light_preview is not None and self.light_preview[0] == self.number:
            picture_files = {**picture_files, **self.light_preview[1]}
            rows = {table: {key: dict(fields) for key, fields in found.items()} for table, found in rows.items()}
            for table, found in self.light_preview[2].items():
                for key, fields in found.items():
                    rows.setdefault(table, {}).setdefault(key, {}).update(fields)
        worker = ms.SceneWorker(self._token, self.game_dir(), self.number, self.shown_look,
                                self.map_state(), getattr(self.state, "nxd_sqlite_path", None),
                                mesh_file, picture_files, self.lighting, rows,
                                anim_file=mod_anim(self.state, self.number),
                                terrains=map_terrains(self.state))
        run_in_thread(worker, on_finished=self._scene_ready, on_failed=self._reading_failed)

    def _look_changed_while_read(self) -> bool:
        """
        Whether the mod's look of the map changed while it was read (Start a
        new mod, or a mod opened, with the reading under way): what the
        reading brought is the old mod's, so the map is read again. Before
        (22 October), Start a new mod as a map edited in the old mod was
        being read left that map drawn as the old mod had it.
        """
        if self.number is None or self._reading_inputs == self.look_inputs(self.number):
            return False
        self._load()
        return True

    def _reading_failed(self, message: str) -> None:
        self._running = False
        if self._token != self._wanted:
            self._start_reading()
            return
        if self._look_changed_while_read():
            return
        self._scene_failed(message)

    def _scene_ready(self, result) -> None:
        self._running = False
        token, scene, error = result
        if token != self._wanted:
            self._start_reading()       # another map or variant was asked for since
            return
        if self._look_changed_while_read():
            return
        if scene is None:
            self._scene_failed(error)
            return
        old_key = self.scene.grid_key if self.scene is not None else None
        self.scene = scene
        self._shown_inputs = self._reading_inputs
        self.scenes_loaded += 1
        self.game_tiles = ({(t.x, t.z, t.level): t for t in scene.terrain.tiles}
                           if scene.terrain is not None else {})
        if scene.grid_key != old_key:
            self.picked = []
        self._take_carried_copy()
        # Said over the picture: what could not be drawn as the game draws it.
        self.view.set_message(" ".join(scene.notes))
        self.view.set_scene(scene, self.tiles(), self.edited_keys())
        self.view.set_picked(self.picked)
        self._update_marks(again=True)
        if scene.look == ms.ENHANCED:
            self._fill_lightings()
        self._update_sky()
        self._show_panel()
        self._update_look_buttons()

    def _take_carried_copy(self) -> None:
        """
        A grid the opened mod carries a copy of, made another way, is shown
        as the mod has it and can't be edited: export copies the mod's file
        through as it is, over anything written from edits here - the rule
        UI Layouts keeps for a screen carried whole.
        """
        self.carried = self.carried_copies()
        self.read_only = bool(self.carried)
        if not self.carried:
            return
        name = min(self.carried, key=mc.file_order)
        try:
            terrain = mc.read_mesh(self.carried[name].read_bytes()).terrain
        except (OSError, mc.MapError):
            terrain = None
        if terrain is not None:
            self.game_tiles = {(t.x, t.z, t.level): t for t in terrain.tiles}

    def carried_copies(self) -> dict:
        """`{file name: path}` for the files of this grid the opened mod carries whole."""
        if self.scene is None or not self.scene.grid_files:
            return {}
        prefix = mc.MAP_FOLDER + "/"
        carried = {rel[len(prefix):].lower(): source for rel, source
                   in (getattr(self.state, "other_file_replacements", {}) or {}).items()
                   if rel.lower().startswith(prefix)}
        return {name: Path(carried[name.lower()]) for name in self.scene.grid_files
                if name.lower() in carried}

    # -- the enhanced look's model and pictures ------------------------------------------

    def mod_look(self, number) -> tuple:
        """`mod_look` for this page's state."""
        return mod_look(self.state, number)

    def mod_rows(self, number) -> dict:
        """`mod_rows` for this page's state."""
        return mod_rows(self.state, number)

    def _update_look_buttons(self) -> None:
        enhanced = (self.scene is not None and self.scene.look == ms.ENHANCED
                    and self.number in self.enhanced_numbers)
        mesh, pictures = self.mod_look(self.number)
        for button in (self.save_package_button, self.load_package_button, self.light_button):
            button.setEnabled(enhanced and not self._package_busy)
        # Any enhanced look drawn, a copied one too (a copy of a copy).
        looked = self.scene is not None and self.scene.look == ms.ENHANCED and self.number is not None
        self.copy_button.setEnabled(looked and not self._package_busy)
        self.sky_button.setEnabled(looked and bool(self.variants()))
        self.put_back_look_button.setVisible(bool(mesh or pictures or self.mod_rows(self.number)
                                                  or sky_row(self.state, self.number)))
        self.put_back_look_button.setEnabled(not self._package_busy)
        # A copy of a look with none can be given them too: a battle there needs them.
        bare = looked and self.scene.panels == 0
        self.panels_button.setVisible(bare)
        self.panels_button.setEnabled(bare and not self._package_busy)
        offered = self.ground is not None and self.ground[0] == self.number
        self.follow_ground_button.setVisible(offered)
        self.follow_ground_button.setEnabled(offered and not self._package_busy)
        tiles = self.package_tiles is not None and self.package_tiles[0] == self.number
        self.use_tiles_button.setVisible(tiles)
        self.use_tiles_button.setEnabled(tiles and not self._package_busy)

    def _say_look(self, text: str, role: str = "muted") -> None:
        self.look_note.setText(text)
        self.look_note.setProperty("role", role)
        self.look_note.style().unpolish(self.look_note)
        self.look_note.style().polish(self.look_note)

    def save_package(self, parent_folder=None) -> None:
        """Writes this map's enhanced look, as the mod has it, into a new folder in `parent_folder`."""
        if self.number is None or self.game_dir() is None or self._package_busy:
            return
        if parent_folder is None:
            parent_folder = export_dialogs.choose_folder(
                self, f"Where to put map {self.number:03d} for editing")
            if not parent_folder:
                return
        folder = package_folder(Path(parent_folder), self.number)
        mesh_file, pictures = self.mod_look(self.number)
        self._package_busy = True
        self._update_look_buttons()
        self._say_look(f"Saving map {self.number:03d} for editing...")
        # The grid it stands on as edited, when it is the one shown; the
        # game's otherwise (`map_package.export_package`).
        tiles = grid_file = None
        if self.scene is not None and self.scene.grid_file and self.game_tiles:
            tiles = {(t.x, t.z, t.level): t for t in self.tiles()}
            grid_file = self.scene.grid_file
        worker = PackageSaveWorker(self.game_dir(), self.number, folder,
                                   getattr(self.state, "nxd_sqlite_path", None), mesh_file, pictures,
                                   self.mod_rows(self.number), tiles, grid_file, mod_anim(self.state, self.number))
        run_in_thread(worker, on_finished=self._package_saved, on_failed=self._package_failed)

    def _package_saved(self, done) -> None:
        self._package_busy = False
        self._update_look_buttons()
        missing = done.get("missing") or []
        folder = Path(done["folder"])
        number = self.number
        # The light Light the map last made for the map travels with it.
        light = light_file(number) if number is not None else None
        carried_light = False
        if light is not None and light.is_file():
            try:
                (folder / mpk.LIGHT).write_bytes(light.read_bytes())
                carried_light = True
            except OSError:
                carried_light = False
        tiles = done.get("tiles") or 0
        kept = []
        if tiles:
            kept.append(f"the {tiles} tile{'s' if tiles != 1 else ''} your mod changed")
        if carried_light:
            kept.append("the light you made with Light the map")
        text = (f"Saved for editing in {folder}: {done['faces']:,} faces in "
                f"{done['objects']} parts, and {done['pictures']} textures, with a guide to where "
                f"each face is on its texture"
                + (", and " + " and ".join(kept) if kept else "")
                + ". Change map.obj and the textures (its README says how), then Load edited.")
        if missing:
            text += (f" {len(missing)} texture{'s' if len(missing) != 1 else ''} "
                     f"{'aren' if len(missing) != 1 else 'isn'}'t in the game folder and "
                     f"{'were' if len(missing) != 1 else 'was'} left out.")
        self.last_package = folder
        self._say_look(text, "ok")

    def _package_failed(self, message: str) -> None:
        self._package_busy = False
        self._update_look_buttons()
        self._say_look(f"That didn't work: {message}", "danger")

    def load_package(self, folder=None) -> None:
        """Builds a package back, and the map is drawn from it and goes into the mod."""
        if self.number is None or self._package_busy:
            return
        if folder is None:
            folder = export_dialogs.choose_folder(self, "The folder saved for editing")
            if not folder:
                return
        folder = Path(folder)
        try:
            number = int(json.loads((folder / mpk.METADATA).read_text(encoding="utf-8"))["map"])
        except (OSError, ValueError, KeyError):
            self._say_look(f"{folder} isn't a folder saved with Save for editing: it has no "
                           f"{mpk.METADATA}.", "danger")
            return
        if number != self.number:
            self._say_look(f"That folder is map {number:03d}, and this is map {self.number:03d}. "
                           f"Pick map {number:03d} first.", "attention")
            return
        self._package_busy = True
        self._update_look_buttons()
        self._say_look(f"Building map {number:03d} from {folder}...")
        mod_mesh, mod_pictures = self.mod_look(number)
        run_in_thread(PackageLoadWorker(folder, self.game_dir(), mod_mesh, mod_pictures, mod_anim(self.state, number)),
                      on_finished=self._package_loaded,
                      on_failed=self._package_load_failed)

    def _package_loaded(self, result) -> None:
        folder, built, mesh_file, ground, same, over, anim_file = result
        self._package_busy = False
        number = built.number
        rows_before = rows_text(self.mod_rows(number))
        textures_before = set(self._added_textures(number))
        replaced = self.state.other_file_replacements
        for rel, path in ((mpk.mesh_relative_path(number), mesh_file), (me.anim_relative_path(number), anim_file)):
            if path is not None:
                replaced[rel] = path
            else:
                replaced.pop(rel, None)
        # The textures of groups the mod added before and the model no longer
        # uses go, with their rows; the changed and new ones come in.
        kept = {name.lower() for names in built.added_groups.values() for name in names}
        for name in self._added_textures(number):
            if name.lower() not in kept:
                self.state.texture_edits.pop(mpk.picture_relative_path(number, name), None)
        for name, source in built.pictures.items():
            path = mpk.picture_relative_path(number, name)
            self.state.texture_edits[path] = {"source_path": Path(source), "is_face_texture": False,
                                              LOOK_MARK: number}
        rows = self._put_rows(number, built.table_rows)
        what = []
        if mesh_file is not None and not built.changed:
            # Saved from a mod's own look, and built as it was: counted
            # against that model, nothing is new, which read as if nothing
            # came (the second tundra's rehearsal, 20 October).
            what.append("its model, as the folder holds it")
        elif mesh_file is not None:
            counts = built.counts
            new = counts.get('new', 0)
            what.append(f"its model ({new} new face{'s' if new != 1 else ''}, {counts.get('moved', 0)} "
                        f"changed, {counts.get('gone', 0)} gone)")
        if anim_file is not None:
            what.append("its anim file, for the frames that move")
        if built.pictures:
            what.append(f"{len(built.pictures)} texture{'s' if len(built.pictures) != 1 else ''}")
        if rows:
            what.append(f"{rows} table row{'s' if rows != 1 else ''} for its texture groups and parts")
        unchanged = (same and rows_before == rows_text(self.mod_rows(number))
                     and textures_before == set(self._added_textures(number)))
        if what and unchanged:
            text = f"Nothing in {folder} differs from your mod's look of map {number:03d}."
        elif what:
            text = (f"Map {number:03d} is drawn from {folder} now: " + ", ".join(what[:-1])
                    + (" and " if len(what) > 1 else "") + what[-1] + " go into your mod.")
        else:
            text = f"Nothing in {folder} differs from the map as it was."
        text += self._take_package_tiles(folder, number)
        text += self._take_package_light(folder, number)
        text += self._over_tiles_note(number, over or {})
        text += "".join(f" {n}." for n in built.notes[:NOTES_SHOWN])
        if len(built.notes) > NOTES_SHOWN:
            more = len(built.notes) - NOTES_SHOWN
            try:
                listed = Path(folder) / mpk.BUILT / NOTES_FILE
                listed.parent.mkdir(parents=True, exist_ok=True)
                listed.write_text("\n".join(built.notes) + "\n", encoding="utf-8")
                text += (f" And {more} more note{'s' if more != 1 else ''}: every one is in "
                         f"{mpk.BUILT}/{NOTES_FILE} in the folder.")
            except OSError:
                text += f" And {more} more note{'s' if more != 1 else ''}."
        self.ground = None
        offer = self._ground_offer(number, ground)
        if offer:
            self.ground = (number, offer[0], offer[1])
            moved = len(offer[1])
            text += (f" Its ground moved under {moved} tile{'s' if moved != 1 else ''}: Move the tiles "
                     f"to the model, and units stand on it.")
        if ground is not None and ground.lost:
            text += (f" {ground.lost} tile{'s have' if ground.lost != 1 else ' has'} no ground under "
                     f"{'them' if ground.lost != 1 else 'it'} in the model now.")
        self._say_look(text, "ok")
        self.edits_changed.emit()
        self._load()
        self._update_look_buttons()

    def _over_tiles_note(self, number, over: dict) -> str:
        """
        Load edited's warnings: new faces standing over tiles the map's
        battles use, and lying just over the tiles' move highlights
        (`map_battles.faces_over`; the stress test of 20 October).
        """
        def listed(keys) -> str:
            shown = ", ".join(f"({x}, {z})" for x, z, _level in keys[:4])
            return shown + (f" and {len(keys) - 4} more" if len(keys) > 4 else "")

        def parts_of(keys) -> str:
            names = sorted({name for key in keys for name in (over.get("parts") or {}).get(key, ())})
            return (" (" + ", ".join(names[:3]) + (f" and {len(names) - 3} more" if len(names) > 3 else "") + ")"
                    if names else "")

        text = ""
        uses = self.battle_uses(number)
        standing = sorted(key for key in (over.get("stands") or {}) if key in uses)
        if standing:
            text += (f" Careful: its new faces{parts_of(standing)} stand over {len(standing)} "
                     f"tile{'s' if len(standing) != 1 else ''} the map's battles use, {listed(standing)}: a unit "
                     f"there is hidden or can't reach it. Show battles marks them.")
        # Only where a unit can stand: a tile no unit stands on shows no move
        # highlight (the tundra's crystal icons lie over their rocks).
        covering = sorted(key for key in (over.get("covers") or {})
                          if self.tile(key) is not None and not self.tile(key).no_walk)
        if covering:
            text += (f" New faces{parts_of(covering)} lie just above {len(covering)} "
                     f"tile{'s' if len(covering) != 1 else ''} units can stand on, {listed(covering)}, over where "
                     f"the game draws a tile's move and target highlights ({mb.PANEL_LIFT:g} above it): they "
                     f"won't show there. Keep a face lying on tiles no more than 0.1 above them.")
        return text

    def _take_package_tiles(self, folder, number) -> str:
        """
        The tiles a loaded package was saved with (`map_package.package_tiles`)
        into the mod: at once when it has none of its own on that grid, else
        offered (`use_package_tiles`). Returns what to add to the note.
        """
        self.package_tiles = None
        grid_file, edits = mpk.package_tiles(folder)
        if not edits or not grid_file or self.game_dir() is None:
            return ""
        maps = self.game_dir() / mc.MAP_FOLDER
        key = mc.grid_key(maps, number, grid_file)
        carried = {rel.lower() for rel in (getattr(self.state, "other_file_replacements", {}) or {})}
        if key is None or any(f"{mc.MAP_FOLDER}/{name}".lower() in carried
                              for name in mc.grid_files(maps, number, grid_file)):
            return (" The tiles it was saved with weren't taken: your mod carries this map's grid "
                    "whole.")
        current = self.state.map_edits.get(key, {})
        count = len(edits)
        if current == edits:
            return ""
        if not current:
            self.state.map_edits[key] = {tile: dict(fields) for tile, fields in edits.items()}
            self._mark_list()
            self._update_counter()
            if count == 1:
                return " The 1 tile it was saved with is your mod's now (its surface, height and the rest)."
            return (f" The {count} tiles it was saved with are your mod's now (their surfaces, heights "
                    f"and the rest).")
        self.package_tiles = (number, key, edits)
        return (f" It was saved with {count} changed tile{'s' if count != 1 else ''}, and your mod "
                f"has others: Use the folder's tiles takes the folder's.")

    def use_package_tiles(self) -> None:
        """The tiles of the last package loaded, in place of the mod's on that grid."""
        if self.package_tiles is None or self.package_tiles[0] != self.number:
            return
        number, key, edits = self.package_tiles
        self.state.map_edits[key] = {tile: dict(fields) for tile, fields in edits.items()}
        self.package_tiles = None
        count = len(edits)
        self._say_look(f"Map {number:03d} has the {count} tile{'s' if count != 1 else ''} the folder "
                       f"was saved with now.", "ok")
        if self.scene is not None and self.scene.grid_key == key:
            self._after_edit()
        else:
            self._mark_list()
            self._update_counter()
            self.edits_changed.emit()
        self._update_look_buttons()

    def _take_package_light(self, folder, number) -> str:
        """A loaded package's light (`map_package.LIGHT`) as Light the map's for the map; the note's words."""
        source = Path(folder) / mpk.LIGHT
        if not source.is_file():
            return ""
        target = light_file(number)
        try:
            data = source.read_bytes()
            json.loads(data.decode("utf-8"))
            if target.is_file() and target.read_bytes() == data:
                return " Its light is Light the map's already: open it and Make to light the map."
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        except (OSError, ValueError):
            return ""
        if self.light_dialog is not None and self.light_dialog.number == number:
            self.light_dialog.close()
            self.light_dialog = None
        return " Its light came too: open Light the map, and Make lights the map with it."

    def _added_textures(self, number) -> list:
        """The texture files of the groups map `number`'s rows in the mod add, every frame of each."""
        names = []
        for (_map, _group, kind), fields in self.mod_rows(number).get(mpk.TEXTURE_TABLE, {}).items():
            if fields.get(mpk.ADDED_ROW) and kind in (0, 1, 2):
                counts = mpk._json_list(fields.get("Unknown10"))
                for listed in ("Unknown8", "Unknown18"):
                    for i, stem in enumerate(mpk._json_list(fields.get(listed))):
                        count = counts[i] if listed == "Unknown8" and i < len(counts) else (counts[0] if counts else 1)
                        for name in (me._frame_names(stem, int(count or 1)) if stem else []):
                            if name not in names:
                                names.append(name)
        return names

    def _put_rows(self, number, rows: dict) -> int:
        """
        A built package's table rows into the mod's: the rows it adds take the
        place of those map `number` added before, and its changed rows go
        over the mod's edits, less what is the game's own already. How many
        rows the mod has from it: a build states the game's own rows too (a
        map's moving textures' rows, written again in the anim file's order),
        and those aren't counted (the frames test's rehearsal, 21 October:
        "7 table rows" said, 3 in the mod).
        """
        count = 0
        store = self.state.unmodelled_table_edits
        sqlite_path = getattr(self.state, "nxd_sqlite_path", None)
        game = {table: mpk.map_rows(sqlite_path, table, number)[0] for table in (mpk.TEXTURE_TABLE, mpk.NODE_TABLE)}
        game[mpk.ANIM_TABLE] = mpk.anim_rows(sqlite_path, number)[0]
        for table in (mpk.TEXTURE_TABLE, mpk.NODE_TABLE, mpk.ANIM_TABLE):
            found = store.setdefault(table, {})
            for key in [k for k, f in found.items() if isinstance(k, tuple) and len(k) == _key_length(table)
                        and k[0] == number and f.get(mpk.ADDED_ROW)]:
                found.pop(key)
            for key, fields in (rows or {}).get(table, {}).items():
                if fields.get(mpk.ADDED_ROW):
                    found[key] = dict(fields)
                    count += 1
                    continue
                changes = dict(found.get(key, {}))
                changes.update(fields)
                own = game[table].get(key[1:], {})
                changes = {k: v for k, v in changes.items() if own.get(k) != v}
                if changes:
                    found[key] = changes
                    count += 1
                else:
                    found.pop(key, None)
            if not found:
                store.pop(table, None)
        return count

    def _ground_offer(self, number, ground) -> Optional[tuple]:
        """
        `(grid key, {(x, z, level): {field: value}})` for the tiles a loaded
        model's ground moved under that aren't there yet, or None: nothing
        moved, or the grid is one the mod carries whole (not edited here).
        """
        if ground is None or not ground.tiles or not ground.grid_file or self.game_dir() is None:
            return None
        folder = self.game_dir() / mc.MAP_FOLDER
        key = mc.grid_key(folder, number, ground.grid_file)
        carried = {rel.lower() for rel in (getattr(self.state, "other_file_replacements", {}) or {})}
        if any(f"{mc.MAP_FOLDER}/{name}".lower() in carried
               for name in mc.grid_files(folder, number, ground.grid_file)):
            return None
        try:
            terrain = mc.read_mesh((folder / ground.grid_file).read_bytes()).terrain
        except (OSError, mc.MapError):
            return None
        game = {(t.x, t.z, t.level): t for t in terrain.tiles} if terrain else {}
        edits = self.state.map_edits.get(key, {})
        moving = {}
        for tile_key, fields in ground.tiles.items():
            tile = game.get(tile_key)
            if tile is None:
                continue
            now = as_edited(tile, edits.get(tile_key, {}))
            if any(int(now.get(name)) != value for name, value in fields.items()):
                moving[tile_key] = fields
        return (key, moving) if moving else None

    def follow_ground(self) -> None:
        """The tiles under the loaded model's moved ground go where it did (`ground`)."""
        if self.ground is None or self.ground[0] != self.number or self.game_dir() is None:
            return
        number, key, tiles = self.ground
        folder = self.game_dir() / mc.MAP_FOLDER
        try:
            # A grid's key is the first of the files holding it (`grid_key`).
            terrain = mc.read_mesh((folder / key).read_bytes()).terrain
        except (OSError, mc.MapError):
            terrain = None
        game = {(t.x, t.z, t.level): t for t in terrain.tiles} if terrain else {}
        store = self.state.map_edits.setdefault(key, {})
        for tile_key, fields in tiles.items():
            tile = game.get(tile_key)
            if tile is None:
                continue
            changes = dict(store.get(tile_key, {}))
            for name, value in fields.items():
                if value == _value(tile, name):
                    changes.pop(name, None)
                else:
                    changes[name] = int(value)
            if changes:
                store[tile_key] = changes
            else:
                store.pop(tile_key, None)
        if not store:
            self.state.map_edits.pop(key, None)
        self.ground = None
        moved = len(tiles)
        self._say_look(f"{moved} tile{'s' if moved != 1 else ''} of map {number:03d} follow its model's "
                       f"ground now. Check them: a tile is whole steps high.", "ok")
        if self.scene is not None and self.scene.grid_key == key:
            self._after_edit()
        else:
            self._mark_list()
            self._update_counter()
            self.edits_changed.emit()
        self._update_look_buttons()

    def _package_load_failed(self, message: str) -> None:
        self._package_busy = False
        self._update_look_buttons()
        lines = message.splitlines()
        more = f" And {len(lines) - 4} more." if len(lines) > 4 else ""
        self._say_look("That folder can't be built: " + " ".join(lines[:4]) + more, "danger")

    # -- Light the map (map_light) -------------------------------------------------

    def open_light(self):
        """Opens Light the map for the map shown, and returns it."""
        try:
            from .map_light import LightDialog
        except ImportError as exc:
            self._say_look(f"Light the map needs numpy and Pillow, and one of them isn't installed ({exc}).",
                           "danger")
            return None
        if self.number is None:
            return None
        if self.light_dialog is not None and self.light_dialog.number != self.number:
            self.light_dialog.close()
            self.light_dialog = None
        if self.light_dialog is None:
            self.light_dialog = LightDialog(self)
        self.light_dialog.show()
        self.light_dialog.raise_()
        return self.light_dialog

    def light_arguments(self, number) -> Optional[dict]:
        """`map_lighting.light_map`'s arguments for map `number` as the mod has it, or None when not read."""
        if self.game_dir() is None or number != self.number:
            return None
        mesh_file, pictures = self.mod_look(number)
        tiles = {(t.x, t.z, t.level): t for t in self.tiles()} if self.game_tiles else None
        return {"game_dir": self.game_dir(), "number": number,
                "sqlite_path": getattr(self.state, "nxd_sqlite_path", None), "mesh_file": mesh_file,
                "picture_files": pictures, "rows": self.mod_rows(number), "tiles": tiles}

    def border_tint(self, number) -> tuple:
        """A border's colour for map `number`: its ground texture's, darkened (`map_lighting.ground_colour`)."""
        from PIL import Image
        from ... import map_lighting as ml
        _mesh, pictures = self.mod_look(number)
        entry = me.pictures(self.game_dir(), number, getattr(self.state, "nxd_sqlite_path", None),
                            self.mod_rows(number).get(mpk.TEXTURE_TABLE)).get(0)
        if entry is None or not entry.colour:
            return ml.ground_colour(None)
        name = entry.colour[0]
        try:
            with Image.open(pictures.get(name, me.texture_folder(self.game_dir(), number) / name)) as image:
                return ml.ground_colour(image)
        except (OSError, ValueError):
            return ml.ground_colour(None)

    def set_light_preview(self, number, files: dict, rows: dict, which=None) -> None:
        """Draws map `number` with Light the map's preview textures and rows, not in the mod."""
        self.light_preview = (number, {name: Path(path) for name, path in files.items()}, rows or {})
        if which is not None and number == self.number:
            self.lighting = int(which)
        self._load()

    def clear_light_preview(self) -> None:
        if self.light_preview is not None:
            self.light_preview = None
            if self.number is not None:
                self._load()

    def put_light(self, number, made, files: dict, which=None) -> None:
        """Light the map's textures and rows into the mod (`map_lighting.light_map`)."""
        for name, path in files.items():
            self.state.texture_edits[mpk.picture_relative_path(number, name)] = {
                "source_path": Path(path), "is_face_texture": False, LOOK_MARK: number}
        self._merge_rows(number, made.rows)
        self.light_preview = None
        rows = sum(len(found) for found in made.rows.values())
        dropped = self._drop_unnamed_light(number)
        self._say_look(f"Map {number:03d} is lit as you set: {len(files)} texture"
                       f"{'s' if len(files) != 1 else ''}" + (f" and {rows} table row{'s' if rows != 1 else ''}"
                                                            if rows else "")
                       + " go into your mod."
                       + (f" {dropped} texture{'s' if dropped != 1 else ''} made before, which no row names now, "
                          f"{'are' if dropped != 1 else 'is'} taken out of it." if dropped else ""), "ok")
        self.edits_changed.emit()
        if number == self.number:
            if which is not None:
                self.lighting = int(which)
            self._load()
            self._update_look_buttons()

    def _drop_unnamed_light(self, number) -> int:
        """
        Takes out of the mod the textures Light the map made for map
        `number` that no row of the map names now: after Make for every
        lighting, those made before for one (Zodi's stress test of 20
        October: a random battle's ten stayed in the mod, named by no row).
        Only Light the map's own (made in its folder): a texture a package
        gave stays. How many went.
        """
        sqlite_path = getattr(self.state, "nxd_sqlite_path", None)
        if not sqlite_path:
            return 0                     # no rows to read: nothing can be said to name none
        rows = self.mod_rows(number)
        named = set()
        for table in (mpk.TEXTURE_TABLE, mpk.SYSTEM_TABLE):
            current, _added = mpk.map_rows(sqlite_path, table, number, rows.get(table))
            for fields in current.values():
                for value in fields.values():
                    named.update(Path(name).stem.lower() for name in names_in(value))
        if not named:
            return 0
        made = light_file(number).parent
        prefix = mpk.picture_relative_path(number, "").lower()
        dropped = 0
        for rel, info in list(self.state.texture_edits.items()):
            if not rel.lower().startswith(prefix) or not isinstance(info, dict) or info.get(LOOK_MARK) != number:
                continue
            source = info.get("source_path")
            try:
                ours = source is not None and Path(source).resolve().is_relative_to(made.resolve())
            except (OSError, ValueError):
                ours = False
            if ours and Path(rel).stem.lower() not in named:
                self.state.texture_edits.pop(rel)
                dropped += 1
        return dropped

    def _merge_rows(self, number, rows: dict) -> None:
        """
        Rows whose columns changed into the mod's: over its own edits, less
        what is the game's already; a row the mod adds takes them as they are.
        """
        store = self.state.unmodelled_table_edits
        for table, found in (rows or {}).items():
            game = mpk.map_rows(getattr(self.state, "nxd_sqlite_path", None), table, number)[0]
            target = store.setdefault(table, {})
            for key, fields in found.items():
                existing = target.get(key)
                if existing and existing.get(mpk.ADDED_ROW):
                    existing.update(fields)
                    continue
                changes = dict(existing or {})
                changes.update(fields)
                own = game.get(key[1:], {})
                changes = {k: v for k, v in changes.items() if own.get(k) != v}
                if changes:
                    target[key] = changes
                else:
                    target.pop(key, None)
            if not target:
                store.pop(table, None)

    def add_panels(self) -> None:
        """
        Gives this map's look highlight panels made from its tiles
        (`map_enhanced.with_grid_panels`), into the mod as its model, with
        their `RefinedBgMeshNode` rows (`map_package.grid_panel_rows`). The
        game draws a tile's move and target highlights only on panels, and
        33 of its looks have none, as none of its battles is fought on
        them. Export makes them again from the tiles as they are then.
        """
        if self.number is None or self.game_dir() is None or self._package_busy:
            return
        number = self.number
        mesh_file, _pictures = self.mod_look(number)
        try:
            data = Path(mesh_file).read_bytes() if mesh_file else me.mesh_path(self.game_dir(), number).read_bytes()
            mesh = me.read_mesh(data)
            if me.has_panels(mesh):
                self._say_look(PANELS_THERE.format(number=number), "muted")
                return
            # On the grid a copied look brought, where it has one (`map_terrains`).
            tiles = mpk.grid_tiles(self.game_dir(), number, self.state.map_edits,
                                   getattr(self.state, "other_file_replacements", None), map_terrains(self.state))
            made, _count = me.with_grid_panels(mesh, list(tiles.values()))
        except (OSError, me.EnhancedMapError, mc.MapError) as exc:
            self._say_look(f"That didn't work: {exc}", "danger")
            return
        target = panels_file(number)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(me.write_mesh(made))
        except OSError as exc:
            self._say_look(f"That didn't work: {exc}", "danger")
            return
        self.state.other_file_replacements[mpk.mesh_relative_path(number)] = target
        store = self.state.unmodelled_table_edits
        rows = mpk.grid_panel_rows(getattr(self.state, "nxd_sqlite_path", None), number, made,
                                   store.get(mpk.NODE_TABLE))
        store.setdefault(mpk.NODE_TABLE, {}).update(rows)
        count = len(me.panel_tiles(tiles.values()))
        self._say_look(PANELS_ADDED.format(number=number, count=count), "ok")
        self.edits_changed.emit()
        self._load()
        self._update_look_buttons()

    def put_back_look(self) -> None:
        """
        Takes this map's model and textures out of the mod; a look copied here
        (`copy_look`) with everything that came with it (`_drop_look`). The
        tiles' heights and slopes go back to the game's with it, as the game's
        look is drawn for them (Zodi, 21 October: raised tiles stayed raised
        under the game's ground); their other changes stay.
        """
        if self.number is None:
            return
        number = self.number
        source = (getattr(self.state, "map_copies", None) or {}).get(number)
        sky = source is None and bool(sky_row(self.state, number))
        self._drop_look(number, grid=source is not None)
        heights = self._heights_back(number) if source is None else 0
        self.ground = None
        self.light_preview = None
        self.edits_changed.emit()
        if source is not None:
            # Its grid is the game's again, and its look none: drawn afresh.
            self.picked = []
            self._open_map(number)
            self._say_look(COPY_PUT_BACK.format(target=number, source=source), "ok")
        else:
            self._say_look(LOOK_PUT_BACK.format(number=number) + heights_back_note(heights)
                           + (SKY_PUT_BACK if sky else ""), "ok")
            self._load()
        self._update_look_buttons()

    def _heights_back(self, number: int) -> int:
        """
        Map `number`'s tiles given the game's height, slope and slope height
        again (`HEIGHT_FIELDS`, in every grid of the map), their other changes
        kept: how many tiles had other heights.
        """
        game = self.game_dir()
        grids = mc.map_grids(game / mc.MAP_FOLDER, number) if game is not None else {}
        count = 0
        for key in grids:
            tiles = self.state.map_edits.get(key)
            if not tiles:
                continue
            for tile_key, fields in list(tiles.items()):
                if not any(name in fields for name in HEIGHT_FIELDS):
                    continue
                count += 1
                kept = {name: value for name, value in fields.items() if name not in HEIGHT_FIELDS}
                if kept:
                    tiles[tile_key] = kept
                else:
                    tiles.pop(tile_key)
            if not tiles:
                self.state.map_edits.pop(key, None)
        return count

    def _drop_look(self, number: int, grid: bool = False) -> None:
        """
        Takes map `number`'s look out of the mod: its model and anim file,
        the textures under its folder, its rows in `LOOK_TABLES` and its sky
        colors (`sky_row`: its `Map` row's variants). With
        `grid` (a look copied there), what came with the copy too: its
        polygons' and `Map` rows (`copy_rows_of`; the `Map` row's other
        columns stay), the grid put there whole (`map_terrains`), the tiles
        changed on that grid (`map_edits`), the texture animation records
        that came with it (`map_animations`), the grid's files the mod
        carried whole, and `map_copies`' entry.
        """
        replaced = self.state.other_file_replacements
        replaced.pop(mpk.mesh_relative_path(number), None)
        replaced.pop(me.anim_relative_path(number), None)
        prefix = mpk.picture_relative_path(number, "").lower()
        for rel in [r for r in self.state.texture_edits if r.lower().startswith(prefix)]:
            self.state.texture_edits.pop(rel, None)
        store = self.state.unmodelled_table_edits
        if store is None:
            store = self.state.unmodelled_table_edits = {}
        rows = self.mod_rows(number)
        if grid:
            for table, found in copy_rows_of(self.state, number).items():
                rows.setdefault(table, {}).update(found)
        for table, found in rows.items():
            for key in found:
                if table == mpk.MAP_TABLE:
                    kept = {k: v for k, v in (store.get(table, {}).get(key) or {}).items()
                            if k not in mpk.MAP_COLUMNS}
                    if kept:
                        store[table][key] = kept
                        continue
                store.get(table, {}).pop(key, None)
            if not store.get(table):
                store.pop(table, None)
        if not grid:
            row = (store.get(mpk.MAP_TABLE) or {}).get(number)
            if row and mv.VARIANTS_COLUMN in row:
                row.pop(mv.VARIANTS_COLUMN)
                if not row:
                    store[mpk.MAP_TABLE].pop(number)
                if not store[mpk.MAP_TABLE]:
                    store.pop(mpk.MAP_TABLE)
            return
        game = self.game_dir()
        grids = mc.map_grids(game / mc.MAP_FOLDER, number) if game is not None else {}
        files = {f"{mc.MAP_FOLDER}/{name}".lower() for names in grids.values() for name in names}
        for rel in [r for r in replaced if str(r).replace("\\", "/").lower() in files]:
            replaced.pop(rel)
        for key in set(grids) | {key for key, _part in terrains_of(self.state, number)}:
            self.state.map_terrains.pop(key, None)
            self.state.map_edits.pop(key, None)
            self.state.map_animations.pop(key, None)
        self.state.map_copies.pop(number, None)

    # -- a look copied to another map number ------------------------------------

    def _fill_copy_menu(self) -> None:
        """
        Copy this look to's menu: the game's spare map numbers
        (`map_package.copy_targets`) but the map shown, one holding a copy
        already said and not offered (Put back the game's look there frees it).
        """
        self.copy_menu.clear()
        game = self.game_dir()
        targets = [n for n in (mpk.copy_targets(game) if game is not None else []) if n != self.number]
        if not targets:
            self.copy_menu.addAction(COPY_NONE).setEnabled(False)
            return
        names = map_names(self.state)
        copies = getattr(self.state, "map_copies", None) or {}
        for n in targets:
            label = map_label(n, names.get(n, ""))
            if n in copies:
                self.copy_menu.addAction(COPY_USED.format(label=label, source=copies[n])).setEnabled(False)
            else:
                action = self.copy_menu.addAction(label)
                action.setData(n)
                action.triggered.connect(lambda _checked=False, target=n: self.copy_look(target))

    def copy_look(self, target: int) -> None:
        """
        Puts this map's enhanced look, as the mod has it, on map `target`
        (`map_package.look_copy`): its model and anim file numbered as the
        target, kept in `copy_folder`; every texture its rows name, under the
        source's names in the target's folder (as WotL Restoration's 127 has
        066's); its rows keyed by the target; and the grid it stands on,
        whole, into the target's grids (`state.map_terrains`), the target's
        own tile edits and carried grid files gone with the grid they were
        made on. Then the target is opened, drawn from the copy.
        """
        if self.number is None or self.game_dir() is None or self._package_busy:
            return
        source, game = self.number, self.game_dir()
        if target == source or target in (getattr(self.state, "map_copies", None) or {}):
            return
        sqlite_path = getattr(self.state, "nxd_sqlite_path", None)
        if not sqlite_path:
            self._say_look(COPY_NEEDS_DATABASE, "attention")
            return
        mesh_file, pictures = self.mod_look(source)
        # A lighting naming no sky is drawn with the classic look's sky of the
        # number a battle is on: on the copy, the target's (097's clear blue
        # behind 062's black chapel). Such a lighting gets the source's own
        # (`own_sky`) as colors, so the copy looks as the source does.
        own_skies = {}
        for variant in self.variants(source):
            if variant.sky_top is None or variant.sky_bottom is None:
                own = self.own_sky(variant)
                if own is not None:
                    own_skies[variant.index] = (own[0], own[1])
        try:
            made = mpk.look_copy(game, source, target, sqlite_path, mesh_file, pictures,
                                 self.state.unmodelled_table_edits, mod_anim(self.state, source),
                                 self.state.map_edits, self.state.other_file_replacements,
                                 self.state.map_terrains, self.state.map_copies, self.state.map_animations)
        except (mpk.PackageError, OSError, me.EnhancedMapError, mc.MapError) as exc:
            self._say_look(f"That didn't work: {exc}", "danger")
            return
        if made.terrain is None:
            self._say_look(COPY_NO_GRID.format(source=source), "danger")
            return
        folder = copy_folder(target)
        mesh_target = folder / f"map_{target:03d}_mesh.bin"
        anim_target = folder / f"map_{target:03d}_anim.bin"
        try:
            folder.mkdir(parents=True, exist_ok=True)
            mesh_target.write_bytes(made.mesh)
            if made.anim is not None:
                anim_target.write_bytes(made.anim)
        except OSError as exc:
            self._say_look(f"That didn't work: {exc}", "danger")
            return
        self._drop_look(target, grid=True)
        replaced = self.state.other_file_replacements
        replaced[mpk.mesh_relative_path(target)] = mesh_target
        if made.anim is not None:
            replaced[me.anim_relative_path(target)] = anim_target
        # A texture the mod has for the source in the game's format already
        # (an opened mod's) goes as it is, as it would have.
        theirs = {rel.lower(): info for rel, info in self.state.texture_edits.items()
                  if rel.lower().startswith(mpk.picture_relative_path(source, "").lower())}
        for name, path in made.pictures.items():
            entry = {"source_path": Path(path), "is_face_texture": False, LOOK_MARK: target}
            info = theirs.get(mpk.picture_relative_path(source, name).lower())
            if isinstance(info, dict) and info.get("already_staged"):
                entry["already_staged"] = True
            self.state.texture_edits[mpk.picture_relative_path(target, name)] = entry
        store = self.state.unmodelled_table_edits
        for table, found in made.rows.items():
            rows = store.setdefault(table, {})
            for key, fields in found.items():
                if table == mpk.MAP_TABLE:
                    kept = {k: v for k, v in (rows.get(key) or {}).items() if k not in mpk.MAP_COLUMNS}
                    rows[key] = {**kept, **fields}
                else:
                    rows[key] = dict(fields)
        if own_skies:
            # The copy's variants: the source's (the copy's row has them when
            # they differ from the target's own, which they are otherwise).
            rows = store.setdefault(mpk.MAP_TABLE, {})
            row = dict(rows.get(target) or {})
            variants = (mv.parse_variants(row[mv.VARIANTS_COLUMN]) if mv.VARIANTS_COLUMN in row
                        else self.variants(source))
            for index, (top, bottom) in sorted(own_skies.items()):
                variants = mv.with_sky(variants, index, top, bottom)
            row[mv.VARIANTS_COLUMN] = mv.variants_text(variants)
            rows[target] = row
        doors_lost = False
        for key, names in mc.map_grids(game / mc.MAP_FOLDER, target).items():
            self.state.map_terrains[key] = made.terrain
            # The doors' records go where the target's files have room
            # for them (097's, 099's); elsewhere they can't open.
            if made.animations is not None:
                if animations_fit(game, names):
                    self.state.map_animations[key] = made.animations
                elif doors_of(made.animations):
                    doors_lost = True
        self.state.map_copies[target] = source
        count = sum(len(found) for found in made.rows.values())
        text = COPY_DONE.format(source=source, target=target, pictures=len(made.pictures), rows=count)
        if own_skies:
            text += COPY_SKY.format(source=source)
        if doors_lost:
            text += COPY_NO_DOORS.format(target=target)
        if not me.has_panels(me.read_mesh(made.mesh)):
            text += COPY_NO_PANELS
        if made.missing:
            many = len(made.missing) != 1
            text += COPY_MISSING.format(count=len(made.missing), s="s" if many else "", are="are" if many else "is",
                                        they="they" if many else "it")
        self.ground = None
        self.package_tiles = None
        self.edits_changed.emit()
        if not self.select_record(target):
            self._open_map(target)
        self._say_look(text, "ok")
        self._update_look_buttons()

    def _scene_failed(self, message: str) -> None:
        self.scene = None
        self.carried = {}
        self.read_only = False
        self.game_tiles = {}
        self.picked = []
        self.view.set_scene(None)
        self.view.set_message(f"This map could not be drawn: {message}")
        self._show_panel()
        self._update_look_buttons()

    # -- the grid and its edits ---------------------------------------------------------

    def edits(self) -> dict:
        """This grid's edits: `{(x, z, level): {field: value}}`."""
        key = self.scene.grid_key if self.scene is not None else None
        return self.state.map_edits.get(key, {}) if key and not self.read_only else {}

    def edited_keys(self) -> set:
        return {k for k, changes in self.edits().items() if changes}

    def tile(self, key):
        """A tile as edited, or None."""
        game = self.game_tiles.get(key)
        if game is None:
            return None
        return as_edited(game, self.edits().get(key, {}))

    def tiles(self) -> list:
        edits = self.edits()
        return [as_edited(t, edits.get(k, {})) for k, t in self.game_tiles.items()]

    def shown_height(self, tile) -> str:
        row = tile.shown_height_index()
        return self.height_text.get(row) or f"{row / 2:g}"

    def describe(self, tile) -> tuple:
        """
        The card's lines for a tile: its surface, then its height and place,
        and with Show battles on, the battles that use it.
        """
        surface = tile.get("surface")
        where = f"Tile {tile.x}, {tile.z}" + (", upper level" if tile.level else "")
        detail = f"Height {self.shown_height(tile)}    {where}"
        if self.show_battles.isChecked():
            for said in mb.uses_lines(self.battle_uses().get((tile.x, tile.z, tile.level), ())):
                detail += "\n" + said[0].upper() + said[1:]
        return (self.surface_name.get(surface) or f"Surface {surface}", detail)

    def _grid_note(self) -> str:
        if self.scene is None:
            return ""
        if not self.game_tiles:
            return "This map has no battle grid in this variant."
        files = self.scene.grid_files or ([self.scene.grid_file] if self.scene.grid_file else [])
        if not files:
            return ""
        if self.read_only:
            names = sorted(self.carried, key=mc.file_order)
            return (f"Your mod has its own copy of {', '.join(names)}, made another way. It goes "
                    f"into your mod as it is, so this grid is shown as your mod has it and "
                    f"can't be edited here.")
        if len(files) == 1:
            return f"Tile changes go into {files[0]} in your mod, the file this grid is in."
        return (f"Tile changes go into the {len(files)} files this grid is in, in your mod: "
                + ", ".join(files) + ".")

    def _show_panel(self) -> None:
        self.picked = [k for k in self.picked if k in self.game_tiles]
        if not self.picked:
            self.panel.show_tile(None, note=self._grid_note())
            return
        first = self.picked[0]
        tile = self.tile(first)
        changed = set(self.edits().get(first, {}))
        self.panel.show_tile(tile, self.game_tiles[first], changed, len(self.picked),
                             note=self._grid_note(), names=self.surface_name,
                             alike=len(self.alike_keys(first)), upper=len(self.upper_free()),
                             room=self.room_note())
        if self.read_only:
            for control in self.panel.controls():
                control.setEnabled(False)

    def _on_tile_clicked(self, key, add: bool) -> None:
        if key is None:
            if not add:
                self.picked = []
        elif add:
            if key in self.picked:
                self.picked.remove(key)
            else:
                self.picked.append(key)
        else:
            self.picked = [key]
        self.view.set_picked(self.picked)
        self._show_panel()

    def pick(self, keys) -> None:
        """Picks tiles by `(x, z, level)`, as clicking them would."""
        self.picked = [tuple(k) for k in keys if tuple(k) in self.game_tiles]
        self.view.set_picked(self.picked)
        self._show_panel()

    def alike_keys(self, key) -> list:
        """Every tile of the grid shown with the surface tile `key` has, as edited, it first."""
        tile = self.tile(key)
        if tile is None:
            return []
        surface = tile.get("surface")
        edits = self.edits()
        others = [k for k, game in self.game_tiles.items()
                  if k != key and ms.shows(game) and not game.is_blank
                  and as_edited(game, edits.get(k, {})).get("surface") == surface]
        return [key] + sorted(others)

    def pick_alike(self) -> None:
        """"Pick every ... tile": every tile with the first picked one's surface, so a change goes to all."""
        if self.picked:
            self.pick(self.alike_keys(self.picked[0]))

    def _on_tiles_boxed(self, keys) -> None:
        """Ctrl and a drag: the tiles in the box are added to those picked."""
        added = [k for k in keys if k in self.game_tiles and k not in self.picked]
        if added:
            self.picked.extend(added)
            self.view.set_picked(self.picked)
            self._show_panel()

    def _on_field(self, name: str, value: int) -> None:
        """A field was changed on the panel: it goes to every tile picked."""
        if self.scene is None or not self.scene.grid_key or not self.picked or self.read_only:
            return
        store = self.state.map_edits.setdefault(self.scene.grid_key, {})
        for key in self.picked:
            game = self.game_tiles.get(key)
            if game is None:
                continue
            changes = dict(store.get(key, {}))
            if value == _value(game, name):
                changes.pop(name, None)
            else:
                changes[name] = bool(value) if name in mc.BOOL_FIELDS else int(value)
            if changes:
                store[key] = changes
            else:
                store.pop(key, None)
        if not store:
            self.state.map_edits.pop(self.scene.grid_key, None)
        self._after_edit()

    def upper_free(self) -> list:
        """
        The picked tiles of the ground that have no tile on the upper level
        over them, as edited (`map_classic.has_no_tile`): Add an upper level's.
        """
        if self.scene is None or not self.scene.grid_key or self.read_only:
            return []
        out = []
        for x, z, level in self.picked:
            above = self.tile((x, z, 1)) if level == 0 else None
            if above is not None and mc.has_no_tile(above):
                out.append((x, z, level))
        return out

    def beside(self, x: int, z: int) -> list:
        """The ground tiles beside tile `x`, `z`, as edited, that units can stand on: where they walk in from."""
        out = []
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            tile = self.tile((x + dx, z + dz, 0))
            if tile is not None and not tile.is_blank and not tile.no_walk and not tile.no_cursor:
                out.append(tile)
        return out

    def no_way_under(self) -> list:
        """
        `[(key, least height)]`: the picked upper level tiles, over ground
        units can stand on, that units can't go under (`map_classic.can_go_under`),
        with the height that would let them (`least_upper_height`).
        """
        out = []
        for x, z, level in self.picked:
            if level != 1:
                continue
            upper, ground = self.tile((x, z, 1)), self.tile((x, z, 0))
            if upper is None or ground is None or mc.has_no_tile(upper):
                continue
            if ground.is_blank or ground.no_walk or ground.no_cursor:
                continue
            beside = self.beside(x, z)
            if not mc.can_go_under(upper, ground, beside):
                out.append(((x, z, 1), mc.least_upper_height(ground, beside, upper.get("thickness"))))
        return out

    def room_note(self) -> str:
        """What the tile panel says of picked upper level tiles units can't go under: "" for none."""
        short = self.no_way_under()
        if not short:
            return ""
        words = dict(count=len(short), room=mc.UNIT_ROOM // 2, least=max(least for _key, least in short))
        return (ROOM_ONE if len(short) == 1 and len(self.picked) == 1 else ROOM_MANY).format(**words)

    def add_upper_level(self) -> list:
        """
        A tile on the upper level over each picked tile of the ground with
        none there (`map_classic.upper_tile_fields`: its surface, a few steps
        over it), into the mod's edits as any tile change, and those picked
        then, for their height to be set. The new tiles' keys.
        """
        under = self.upper_free()
        if not under:
            return []
        store = self.state.map_edits.setdefault(self.scene.grid_key, {})
        made = []
        for x, z, _level in under:
            key = (x, z, 1)
            game = self.game_tiles[key]
            changes = dict(store.get(key, {}))
            for name, value in mc.upper_tile_fields(self.tile((x, z, 0))).items():
                if value == _value(game, name):
                    changes.pop(name, None)
                else:
                    changes[name] = bool(value) if name in mc.BOOL_FIELDS else int(value)
            if changes:
                store[key] = changes
            else:
                store.pop(key, None)
            made.append(key)
        if not store:
            self.state.map_edits.pop(self.scene.grid_key, None)
        self.picked = list(made)
        self.view.set_picked(self.picked)
        self._after_edit()
        self._say_look(upper_made_note(len(made), mc.UPPER_STEPS, bool(getattr(self.scene, "panels", 0))), "ok")
        return made

    def put_back(self) -> None:
        """The picked tiles as the game has them."""
        if self.scene is None or not self.scene.grid_key or self.read_only:
            return
        store = self.state.map_edits.get(self.scene.grid_key, {})
        for key in self.picked:
            store.pop(key, None)
        if not store:
            self.state.map_edits.pop(self.scene.grid_key, None)
        # An upper level tile Add an upper level made is no tile again: not picked.
        self.picked = [k for k in self.picked if k in self.game_tiles and ms.shows(self.tile(k))]
        self.view.set_picked(self.picked)
        self._after_edit()

    def _after_edit(self) -> None:
        self.view.set_tiles(self.tiles(), self.edited_keys())
        self._show_panel()
        self._mark_list()
        self._update_counter()
        self.edits_changed.emit()

    def _grid_changed(self) -> None:
        """
        The edit store was replaced, or the files carried through changed (a
        mod opened or cleared): the grid is read again from the game's files
        or the mod's, and drawn from the store.
        """
        if self.scene is not None:
            self.game_tiles = ({(t.x, t.z, t.level): t for t in self.scene.terrain.tiles}
                               if self.scene.terrain is not None else {})
            self._take_carried_copy()
            self.view.set_tiles(self.tiles(), self.edited_keys())
            self._update_marks(again=True)
        self._show_panel()

    # -- the camera -------------------------------------------------------------------

    def turn(self, step: int) -> None:
        """
        To the next of the game's camera corners: `step` 1 turns the map left,
        -1 right. The game's own view, so its height is the nearer of the
        game's two and the zoom and position are put back.
        """
        camera = self.view.camera.copy()
        corners = sorted(corner for corner, _bit in ms.CORNERS)
        now = camera.yaw % 360.0
        if step > 0:
            camera.yaw = next((c for c in corners if c > now + 1.0), corners[0])
        else:
            camera.yaw = next((c for c in reversed(corners) if c < now - 1.0), corners[-1])
        camera.pitch = min((ms.LOW_PITCH, ms.HIGH_PITCH), key=lambda p: abs(p - camera.pitch))
        camera.zoom, camera.pan = 1.0, (0.0, 0.0)
        self.view.set_camera(camera)

    def tilt(self, step: int) -> None:
        """To the game's higher camera (`step` 1) or its lower one (-1)."""
        camera = self.view.camera.copy()
        heights = (ms.LOW_PITCH, ms.HIGH_PITCH)
        if step > 0:
            camera.pitch = next((h for h in heights if h > camera.pitch + 0.5), camera.pitch)
        else:
            camera.pitch = next((h for h in reversed(heights) if h < camera.pitch - 0.5), camera.pitch)
        self.view.set_camera(camera)

    def from_above(self) -> None:
        camera = self.view.camera.copy()
        camera.pitch = ms.TOP_PITCH
        self.view.set_camera(camera)

    def _on_show_tiles(self, on: bool) -> None:
        self.view.show_grid = on
        self.view.schedule()
        ui_settings.save(map_show_tiles=on)

    def _on_show_info(self, on: bool) -> None:
        self.view.show_info = on
        self.view.update()
        ui_settings.save(map_show_tile_info=on)

    def _on_show_battles(self, on: bool) -> None:
        self._update_marks()
        self.view.update()
        ui_settings.save(map_show_battles=on)

    def _on_show_directions(self, on: bool) -> None:
        self.view.show_compass = on
        self.view.update()
        ui_settings.save(map_show_compass=on)

    # -- the battles on the map (map_battles) -------------------------------------------

    def battle_uses(self, number=None) -> dict:
        """
        `{(x, z, level): [map_battles.TileUse]}`: the tiles map `number`'s
        battles use (the map shown's by default), with the game's and the
        mod's encounter rows over its units: read when the map is drawn,
        and again when the page is shown (after the Encounters page, say).
        """
        number = self.number if number is None else number
        if number is None or self.game_dir() is None:
            return {}
        if self._battles is None or self._battles[0] != number:
            try:
                uses = mb.battle_tiles(self.game_dir(), number, getattr(self.state, "entry_records", None),
                                       getattr(self.state, "entry_edits", None))
            except (OSError, ValueError, IndexError):
                uses = {}
            self._battles = (number, uses)
        return self._battles[1]

    def _update_marks(self, again: bool = False) -> None:
        """The battles' tiles on the map while Show battles is on, none otherwise; `again` reads them afresh."""
        if again:
            self._battles = None
        if not self.show_battles.isChecked() or self.scene is None:
            self.view.set_marks({})
            return
        self.view.set_marks({key: {use.kind for use in uses} for key, uses in self.battle_uses().items()})

    def showEvent(self, event):                                   # noqa: N802
        super().showEvent(event)
        # The mod's encounters may have changed on their page since.
        self._update_marks(again=True)

    # -- right click: the picture under the pointer -----------------------------------------

    def picture_paths(self, point) -> list:
        """
        `[(label, path)]` for the pictures of the polygon under a point of the
        map, as the Textures page knows them: its colour picture (the first
        frame of an animated one) and its lighting. Empty in the classic look,
        whose texture is not a picture file.
        """
        if self.scene is None or self.scene.look != ms.ENHANCED:
            return []
        batch = self.view.batch_at(QPointF(point))
        if batch is None or batch.group is None:
            return []
        entry = self.scene.pictures.get(batch.group)
        if entry is None:
            return []
        out = []
        # A texture group the mod adds has textures the game hasn't, which
        # the Textures page can't open.
        game = self.game_dir()
        for label, name in (("Open its texture in Textures", entry.colour[0] if entry.colour else None),
                            ("Open its lighting in Textures", entry.lighting)):
            path = f"{self.scene.picture_folder}/{name}" if name else None
            if path and (game is None or (game / path).is_file()):
                out.append((label, path))
        return out

    def own_texture_files(self, point) -> list:
        """
        `[(label, file)]` for the textures of the polygon under a point that
        the mod has and the game hasn't (a group Load edited added: its PNG
        in the package's folder), which the Textures page can't open: the
        menu opens their folder instead (Zodi's stress test of 20 October:
        a right click on the new glacier showed no menu at all).
        """
        if self.scene is None or self.scene.look != ms.ENHANCED or self.number is None:
            return []
        batch = self.view.batch_at(QPointF(point))
        entry = self.scene.pictures.get(batch.group) if batch is not None and batch.group is not None else None
        if entry is None:
            return []
        game = self.game_dir()
        out = []
        for label, name in (("Open the folder of its texture, your mod's own", entry.colour[0] if entry.colour
                             else None), ("Open the folder of its lighting, your mod's own", entry.lighting)):
            path = f"{self.scene.picture_folder}/{name}" if name else None
            if not path or (game is not None and (game / path).is_file()):
                continue
            info = self.state.texture_edits.get(mpk.picture_relative_path(self.number, name))
            source = info.get("source_path") if isinstance(info, dict) else info
            if source and Path(source).is_file():
                out.append((label, Path(source)))
        return out

    def _open_texture_folder(self, path: Path) -> None:
        if not actions.reveal_in_file_manager(path.parent):
            self._say_look(f"Its texture is {path}.", "muted")

    def _view_menu(self, point) -> None:
        menu = QMenu(self)
        for label, path in self.picture_paths(point):
            menu.addAction(label).triggered.connect(lambda _c=False, p=path: self.jump_to_texture.emit(p))
        for label, path in self.own_texture_files(point):
            menu.addAction(label).triggered.connect(lambda _c=False, p=path: self._open_texture_folder(p))
        key = self.view.tile_at(QPointF(point))
        if key is not None and key in self.edited_keys():
            def put_back_one(_checked=False, k=key):
                self.pick([k])
                self.put_back()
            menu.addAction("Put back the game's tile").triggered.connect(put_back_one)
        if not menu.isEmpty():
            menu.exec(self.view.mapToGlobal(point))
