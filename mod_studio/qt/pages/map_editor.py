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
  while the map turns: `map_scene.corner_weights`).
- **The tiles, with each tile's height and surface when the pointer is on
  it**, and a switch for the card that says them. Both switches are
  remembered between sessions (`ui_settings`).
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
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMenu, QPushButton, QRadioButton, QSizePolicy, QSpinBox,
    QSplitter, QVBoxLayout, QWidget,
)

from ... import constants as c
from ... import map_classic as mc
from ... import map_enhanced as me
from ... import map_package as mpk
from ... import paths, ui_settings, xml_io
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


def as_edited(tile: mc.Tile, changes: dict) -> mc.Tile:
    return mc.Tile(tile.x, tile.z, tile.level, mc.tile_with(tile.raw, changes)) if changes else tile


def _value(tile: mc.Tile, name: str) -> int:
    return int(tile.get(name))


class PackageSaveWorker(Worker):
    """Writes a map's enhanced look as a package, off the GUI thread: its textures take seconds."""

    def __init__(self, game_dir, number, folder, sqlite_path, mesh_file, picture_files,
                 rows=None, tiles=None, grid_file=None):
        super().__init__()
        self.args = (game_dir, number, folder, sqlite_path, mesh_file, picture_files)
        self.rows = {table: dict(found) for table, found in (rows or {}).items()}
        self.tiles, self.grid_file = (dict(tiles) if tiles else None), grid_file

    def run(self):
        game_dir, number, folder, sqlite_path, mesh_file, picture_files = self.args
        try:
            return mpk.export_package(game_dir, number, folder, sqlite_path, mesh_file, picture_files,
                                      rows=self.rows, tiles=self.tiles, grid_file=self.grid_file)
        except (OSError, ValueError) as exc:
            raise RuntimeError(str(exc)) from exc


class PackageLoadWorker(Worker):
    """
    Builds a package, off the GUI thread, and works out where the tiles
    under its model's ground go (`map_package.ground_under_tiles`). Returns
    `(folder, Built, mesh file or None, Ground or None)`.
    """

    def __init__(self, folder, game_dir=None):
        super().__init__()
        self.folder, self.game_dir = folder, game_dir

    def run(self):
        try:
            built = mpk.build(self.folder)
        except mpk.PackageError as exc:
            raise RuntimeError(str(exc)) from exc
        mesh_file = mpk.write_built(self.folder, built) if built.changed else None
        ground = None
        if built.changed and self.game_dir is not None:
            try:
                ground = mpk.ground_under_tiles(self.folder, built, self.game_dir)
            except (OSError, ValueError, mc.MapError):
                ground = None               # the tiles are offered nothing, the model still goes in
        return (self.folder, built, mesh_file, ground)


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


def mod_rows(state, number) -> dict:
    """
    `{table: {key: fields}}`: map `number`'s rows among a mod's table edits
    (`unmodelled_table_edits`) in `RefinedBgTexture` and `RefinedBgMeshNode`:
    the texture groups and parts it adds, and parts it draws another way.
    """
    store = getattr(state, "unmodelled_table_edits", None) or {}
    out = {}
    for table in (mpk.TEXTURE_TABLE, mpk.NODE_TABLE):
        found = {key: fields for key, fields in (store.get(table) or {}).items()
                 if isinstance(key, tuple) and len(key) == 3 and key[0] == number}
        if found:
            out[table] = found
    return out


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
    """The picked tile's fields. Says `edited(field, value)` when one is changed."""

    edited = Signal(str, int)
    put_back = Signal()

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

        use = QGroupBox("Units and the cursor")
        use_rows = QVBoxLayout(use)
        self.stand = QCheckBox("Units can stand here")
        self.cursor = QCheckBox("The cursor can stop here")
        self.cross = QCheckBox("Units cross it without stopping")
        self.cross.setToolTip("A tile units pass over on their way, as the game's own maps mark "
                              "some edges.")
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

        self.put_back_button = QPushButton("Put back the game's tile")
        self.put_back_button.clicked.connect(self.put_back.emit)
        self.put_back_button.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        column.addWidget(self.put_back_button)
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
                self.stand, self.cursor, self.cross, self.shading, self.put_back_button]

    def show_tile(self, tile, game=None, changed=(), count: int = 0, note: str = "",
                  names: dict = None) -> None:
        """
        Fills the fields from `tile` (as edited), `game` being the game's own;
        `changed` names the fields that differ. None empties the panel.
        """
        self._loading = True
        enabled = tile is not None
        for control in self.controls():
            control.setEnabled(enabled)
        if tile is None:
            self.title.setText("Click a tile")
            self.where.setText("Pick a tile on the map to see and change it. Ctrl and click "
                               "picks more than one.")
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
        """An edited field's label in the edited colour and bold, the game's value on hover."""
        font = widget.font()
        if font.bold() != edited:
            font.setBold(edited)
            widget.setFont(font)
        if isinstance(widget, QLabel) and (widget.property("role") == "ok") != edited:
            widget.setProperty("role", "ok" if edited else None)
            widget.style().unpolish(widget)
            widget.style().polish(widget)
        widget.setToolTip(tip)


class MapEditorPage(QWidget):
    edits_changed = Signal()
    #: A picture's path in the game, for the Textures page to open at.
    jump_to_texture = Signal(str)

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
        self.turn_left.setToolTip("To the next of the game's four camera corners.")
        self.turn_right.setToolTip("To the next of the game's four camera corners.")
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
        camera_row.addWidget(_together(self.show_tiles, self.show_info))
        centre.addLayout(camera_row)

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
        self.put_back_look_button.setToolTip("Takes this map's model and textures out of your mod.")
        self.put_back_look_button.clicked.connect(lambda: self.put_back_look())
        model_row.addWidget(_together(QLabel("Model and textures"), self.save_package_button,
                                      self.load_package_button))
        model_row.addWidget(self.put_back_look_button)
        #: Offered after Load edited when the model's ground moved: the tiles
        #: under it follow, so units stand on it (`ground`).
        self.follow_ground_button = QPushButton("Move the tiles to the model")
        self.follow_ground_button.setToolTip(
            "Raises or lowers each tile whose ground moved in the model you loaded, as far as "
            "the ground did, so units stand on it. Put back undoes a tile.")
        self.follow_ground_button.clicked.connect(lambda: self.follow_ground())
        self.follow_ground_button.setVisible(False)
        model_row.addWidget(self.follow_ground_button)
        centre.addLayout(model_row)

        self.view = MapView()
        self.view.show_grid = self.show_tiles.isChecked()
        self.view.show_info = self.show_info.isChecked()
        self.view.describe = self.describe
        self.view.tile_clicked.connect(self._on_tile_clicked)
        self.view.customContextMenuRequested.connect(self._view_menu)
        centre.addWidget(self.view, 1)
        self.hint = QLabel("Drag to turn the map, Shift and drag to move it, and use the wheel to "
                           "zoom. Ctrl and click picks more than one tile.")
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
        self.panel = TilePanel()
        self.panel.edited.connect(self._on_field)
        self.panel.put_back.connect(self.put_back)
        self.panel.setMinimumWidth(300)
        split.addWidget(self.panel)
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
        else:
            # The store may be a new one (a mod opened, or cleared).
            self._grid_changed()

    def _forget_map(self) -> None:
        self.number = None
        self.index = None
        self.scene = None
        self.game_tiles = {}
        self.picked = []
        self.view.set_scene(None)
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

    def _mark_list(self) -> None:
        edited = set(self.state.edited_map_numbers())
        for i in range(self.map_list.count()):
            item = self.map_list.item(i)
            actions.mark_edited(item, item.data(Qt.UserRole) in edited)

    def _update_counter(self) -> None:
        listed = set(self.numbers)
        edited = len([n for n in self.state.edited_map_numbers() if n in listed])
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
        names = map_names(self.state)
        self.title.setText(f"Map {number:03d}, {names[number]}" if names.get(number)
                           else f"Map {number:03d}")
        has_enhanced = number in self.enhanced_numbers
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
        for i, word in enumerate(lighting_words(lightings)):
            self.lighting_box.addItem(word, i)
        if lightings:
            self.lighting_box.setCurrentIndex(self.scene.lighting)
        self.lighting_box.blockSignals(False)
        self._show_variant_boxes()

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

    def _start_reading(self) -> None:
        self._running = True
        self._token = self._wanted
        mesh_file, picture_files = self.mod_look(self.number)
        worker = ms.SceneWorker(self._token, self.game_dir(), self.number, self.shown_look,
                                self.map_state(), getattr(self.state, "nxd_sqlite_path", None),
                                mesh_file, picture_files, self.lighting, self.mod_rows(self.number))
        run_in_thread(worker, on_finished=self._scene_ready, on_failed=self._reading_failed)

    def _reading_failed(self, message: str) -> None:
        self._running = False
        if self._token != self._wanted:
            self._start_reading()
            return
        self._scene_failed(message)

    def _scene_ready(self, result) -> None:
        self._running = False
        token, scene, error = result
        if token != self._wanted:
            self._start_reading()       # another map or variant was asked for since
            return
        if scene is None:
            self._scene_failed(error)
            return
        old_key = self.scene.grid_key if self.scene is not None else None
        self.scene = scene
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
        if scene.look == ms.ENHANCED:
            self._fill_lightings()
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
        for button in (self.save_package_button, self.load_package_button):
            button.setEnabled(enhanced and not self._package_busy)
        self.put_back_look_button.setVisible(bool(mesh or pictures or self.mod_rows(self.number)))
        self.put_back_look_button.setEnabled(not self._package_busy)
        offered = self.ground is not None and self.ground[0] == self.number
        self.follow_ground_button.setVisible(offered)
        self.follow_ground_button.setEnabled(offered and not self._package_busy)

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
                                   self.mod_rows(self.number), tiles, grid_file)
        run_in_thread(worker, on_finished=self._package_saved, on_failed=self._package_failed)

    def _package_saved(self, done) -> None:
        self._package_busy = False
        self._update_look_buttons()
        missing = done.get("missing") or []
        text = (f"Saved for editing in {done['folder']}: {done['faces']:,} faces in "
                f"{done['objects']} parts, and {done['pictures']} textures, with a guide to where "
                f"each face is on its texture. Change map.obj and the textures (its README says "
                f"how), then Load edited.")
        if missing:
            text += f" {len(missing)} textures aren't in the game folder and were left out."
        self.last_package = Path(done["folder"])
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
        run_in_thread(PackageLoadWorker(folder, self.game_dir()), on_finished=self._package_loaded,
                      on_failed=self._package_load_failed)

    def _package_loaded(self, result) -> None:
        folder, built, mesh_file, ground = result
        self._package_busy = False
        number = built.number
        replaced = self.state.other_file_replacements
        rel = mpk.mesh_relative_path(number)
        if mesh_file is not None:
            replaced[rel] = mesh_file
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
            self.state.texture_edits[path] = {"source_path": Path(source), "is_face_texture": False}
        self._put_rows(number, built.table_rows)
        what = []
        if mesh_file is not None:
            counts = built.counts
            what.append(f"its model ({counts.get('new', 0)} new faces, {counts.get('moved', 0)} "
                        f"changed, {counts.get('gone', 0)} gone)")
        if built.pictures:
            what.append(f"{len(built.pictures)} texture{'s' if len(built.pictures) != 1 else ''}")
        rows = sum(len(found) for found in built.table_rows.values())
        if rows:
            what.append(f"{rows} table row{'s' if rows != 1 else ''} for its texture groups and parts")
        if what:
            text = (f"Map {number:03d} is drawn from {folder} now: " + ", ".join(what[:-1])
                    + (" and " if len(what) > 1 else "") + what[-1] + " go into your mod."
                    + "".join(f" {n}." for n in built.notes[:3]))
        else:
            text = f"Nothing in {folder} differs from the map as it was."
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

    def _added_textures(self, number) -> list:
        """The texture files of the groups map `number`'s rows in the mod add."""
        names = []
        for (_map, _group, kind), fields in self.mod_rows(number).get(mpk.TEXTURE_TABLE, {}).items():
            if fields.get(mpk.ADDED_ROW) and kind in (0, 1, 2):
                for listed in ("Unknown8", "Unknown18"):
                    for stem in mpk._json_list(fields.get(listed)):
                        if stem and f"{stem}.tga" not in names:
                            names.append(f"{stem}.tga")
        return names

    def _put_rows(self, number, rows: dict) -> None:
        """
        A built package's table rows into the mod's: the rows it adds take the
        place of those map `number` added before, and its changed rows go
        over the mod's edits, less what is the game's own already.
        """
        store = self.state.unmodelled_table_edits
        game = {table: mpk.map_rows(getattr(self.state, "nxd_sqlite_path", None), table, number)[0]
                for table in (mpk.TEXTURE_TABLE, mpk.NODE_TABLE)}
        for table in (mpk.TEXTURE_TABLE, mpk.NODE_TABLE):
            found = store.setdefault(table, {})
            for key in [k for k, f in found.items() if isinstance(k, tuple) and len(k) == 3
                        and k[0] == number and f.get(mpk.ADDED_ROW)]:
                found.pop(key)
            for key, fields in (rows or {}).get(table, {}).items():
                if fields.get(mpk.ADDED_ROW):
                    found[key] = dict(fields)
                    continue
                changes = dict(found.get(key, {}))
                changes.update(fields)
                own = game[table].get(key[1:], {})
                changes = {k: v for k, v in changes.items() if own.get(k) != v}
                if changes:
                    found[key] = changes
                else:
                    found.pop(key, None)
            if not found:
                store.pop(table, None)

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

    def put_back_look(self) -> None:
        """Takes this map's model and textures out of the mod."""
        if self.number is None:
            return
        self.state.other_file_replacements.pop(mpk.mesh_relative_path(self.number), None)
        prefix = mpk.picture_relative_path(self.number, "").lower()
        for rel in [r for r in self.state.texture_edits if r.lower().startswith(prefix)]:
            self.state.texture_edits.pop(rel, None)
        store = getattr(self.state, "unmodelled_table_edits", None) or {}
        for table, found in self.mod_rows(self.number).items():
            for key in found:
                store.get(table, {}).pop(key, None)
            if not store.get(table):
                store.pop(table, None)
        self.ground = None
        self._say_look(f"Map {self.number:03d} has the game's model and textures again.", "ok")
        self.edits_changed.emit()
        self._load()
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
        """The card's two lines for a tile: its surface, then its height and place."""
        surface = tile.get("surface")
        where = f"Tile {tile.x}, {tile.z}" + (", upper level" if tile.level else "")
        return (self.surface_name.get(surface) or f"Surface {surface}",
                f"Height {self.shown_height(tile)}    {where}")

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
                             note=self._grid_note(), names=self.surface_name)
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

    def put_back(self) -> None:
        """The picked tiles as the game has them."""
        if self.scene is None or not self.scene.grid_key or self.read_only:
            return
        store = self.state.map_edits.get(self.scene.grid_key, {})
        for key in self.picked:
            store.pop(key, None)
        if not store:
            self.state.map_edits.pop(self.scene.grid_key, None)
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

    def _view_menu(self, point) -> None:
        menu = QMenu(self)
        for label, path in self.picture_paths(point):
            menu.addAction(label).triggered.connect(lambda _c=False, p=path: self.jump_to_texture.emit(p))
        key = self.view.tile_at(QPointF(point))
        if key is not None and key in self.edited_keys():
            def put_back_one(_checked=False, k=key):
                self.pick([k])
                self.put_back()
            menu.addAction("Put back the game's tile").triggered.connect(put_back_one)
        if not menu.isEmpty():
            menu.exec(self.view.mapToGlobal(point))
