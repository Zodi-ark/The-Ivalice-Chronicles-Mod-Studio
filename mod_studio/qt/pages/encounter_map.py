"""
The Encounters page's map: a battle's units standing on the map it is
fought on, drawn as the game draws them.

Zodi, 12 October: "Redesign the encounters page to use the map viewer
similar to the treasure Hunter page you can click and drag units to change
their x and y position on the map. Also take note of their direction from
the entd. To correctly draw the sprites of the units and correctly draw
their idle walking or floating in place animations ... Using the entd
information if the unit has a random chance of appearing that should be
indicated. Be aware that multiple units can be on the same tile with the
random chance of appearing so consider what to do there." Agreed from a
mock-up the same day.

- **Which map**: the maps the game's own tables fight the battle on
  (`battle_maps`), the first of them shown; the Map box offers the others,
  and every map for a battle the tables don't place. A choice is kept for
  the battle while Mod Studio runs.
- **Each unit** stands on its tile (`unit_sprites`: the HD sheet in the
  game's own colours), walking in place as units wait in a battle, facing
  the way it faces: the front or back of the sprite, mirrored for the right,
  as the camera turns, and a small wedge on its tile pointing the same way.
  A unit that flies floats up and down. A ring under its feet is its team's
  colour (byte 24's two bits: blue, red, green, light blue).
- **Randomly present** units are faded, with a question mark over them.
  **Units sharing a tile** stand side by side on it, a little smaller, the
  tile outlined, so each can still be clicked and dragged. A unit its row
  disables is drawn grey.
- **Click** a unit to edit it: the page selects its slot, and its tile is
  gold. **Drag** it to another tile to move it: its Position X and Y (and
  Higher Elevation, onto or off a tile's upper level) are set as if typed.
  A unit with no override row can't be moved, and the note under the map
  says so; Trade a row is beside it. A drag anywhere else turns the map, as
  in the Map Editor.

The page supplies the units (`units_of`): their place, facing and sprite
are its effective values, pending edits included. Everything is read from
the unpacked game; without the Textures unpack there is no map, as on
Treasure Hunter.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QMenu, QSizePolicy, QVBoxLayout, QWidget,
)

from ... import battle_maps as bmaps
from ... import map_classic as mc
from ... import map_enhanced as me
from ... import unit_sprites as us
from .. import map_scene as ms
from ..widgets.map_view import MapView
from ..workers import Worker, run_in_thread
from . import map_editor as me_page

HINT = ("Click a unit to edit it, or drag it to another tile. Units sharing a tile stand side by "
        "side. Drag anywhere else to turn the map, Shift and drag to move it, and use the wheel to "
        "zoom.")
NO_GAME = "No game files yet. Unpack your game on General Setup to see its maps here."
NO_MAP = ("The game's files don't say which map this encounter is fought on. Pick one under Map "
          "to place its units.")
PICK_A_MAP = "Pick a map"
PICK_AN_ENCOUNTER = "Pick an encounter in the list to see its battle here."
NO_SPRITES = "Units are drawn as rings: their sprites need the Textures unpack ({})."
CANT_MOVE = ("{} has no override row, so it can't be moved here. Trade a row for its slot "
             "first.")
OFF_GRID = "{} stands at {}, {}, off this map's grid, so it isn't on the map."
EMPTY = "{} has no sprite set, so the map has nothing to draw for it."
UNKNOWN_SPRITE = "Which sprite {} wears isn't known, so it is drawn as a ring."
NO_PICTURE = "{}'s sprite ({}) couldn't be read from the game's files, so it is drawn as a ring."

#: Each team's colour (byte 24's two team bits), and its name in the legend.
TEAM_COLOURS = {0: "#4f9cf2", 1: "#ec5a5a", 2: "#62d27a", 3: "#8fe0f0"}
TEAM_NAMES = {0: "Blue team", 1: "Red team", 2: "Green team", 3: "Light blue team"}
DISABLED_COLOUR = "#9a9a9a"
PICKED_EDGE, PICKED_FILL = QColor(255, 219, 51), QColor(255, 199, 31, 110)

#: Where a facing points on the grid: 0 south (towards lower Y), 1 west
#: (lower X), 2 north, 3 east, as the ENTD names them (FFTPatcher's
#: `Facing`). Measured on the battles: in Mandalia Plains (389) the units
#: round Argath face him from every side by these, and the two sides of
#: The Siedge Weald (384) face each other.
FACING_STEPS = {0: (0, -1), 1: (-1, 0), 2: (0, 1), 3: (1, 0)}
#: A PlayStation pixel is a world unit: a person is about 40 tall, a tile
#: 28 across.
WORLD_PER_HD_PIXEL = 1.0 / us.SCALE
#: The sprites that wear the palette their ENTD slot names: the generic
#: jobs' (96 to 133), and only its first six (the decompilation's
#: `unit_init`).
WEARS_ENTD_PALETTE, ENTD_PALETTES = range(us.FIRST_GENERIC_SPRITE, us.MONSTER_SPRITE_BASE + 1), 6


def drawn_palette(sprite, sprite_set: int, entd_palette: int, monster_palette: int = 0) -> int:
    """
    The palette a unit is drawn in, as the game picks it (the
    decompilation's `unit_init`): a generic job's sprite in its ENTD slot's
    palette, a monster in its job's MonsterPalette, every other sprite (a
    story character's) in its first, whatever the slot says. Zodi, 19
    October: Dycedarg's gloves were blue in event 045, his slot's palette 1;
    the game draws him in his first, the gloves red.
    """
    if sprite_set == us.GENERIC_MONSTER:
        wanted = monster_palette
    elif sprite is not None and sprite in WEARS_ENTD_PALETTE:
        wanted = entd_palette
    else:
        return 0
    return wanted if 0 <= wanted < ENTD_PALETTES else 0
#: Units sharing a tile: how far apart they stand, in tiles, and their size.
SHARED_STEP, SHARED_SCALE = 0.42, 0.8
#: How high a flying unit floats over its tile and how far it bobs, in world
#: units, and how long a bob takes.
FLY_HEIGHT, FLY_BOB, FLY_SECONDS = 6.0, 3.0, 1.6
#: A unit's ring: its half width and height, in world units.
RING_W, RING_H = 12.0, 6.0
#: How faded a randomly present unit is, and a disabled one.
RANDOM_OPACITY, DISABLED_OPACITY = 0.55, 0.3
#: The question mark's disc, in pixels.
BADGE_RADIUS = 8.0
#: The animations run at the game's 60 steps a second.
TICKS_A_SECOND = 60
#: The least the map and its Map box take, so the page fits the window at
#: its narrowest (`shell.MIN_WIDTH`) beside the list and the fields' column:
#: with the map at its usual 320 and the box at 240, the page came to 1,248
#: and the window to 1,468 on a battle (the window's least is 1,345).
MAP_LEAST, MAP_BOX_LEAST = 140, 120


@dataclass
class MapUnit:
    """One unit as the map draws it, from the page's effective values."""
    address: tuple             # where it sits in the list: (battle, slot)
    editable: bool             # whether an override row is behind it
    x: int
    y: int
    upper: bool                # on its tile's upper level
    facing: int                # 0 south, 1 west, 2 north, 3 east
    sprite: Optional[int]      # `unit_sprites.sprite_number`, None when unknown
    palette: int
    team: int
    randomly_present: bool
    disabled: bool
    label: str                 # "Zalmour · Level 24"
    #: No sprite set at all: a named slot with nothing in it. Not drawn.
    empty: bool = False


class SpriteWorker(Worker):
    """Draws units' waiting animations off the GUI thread: `({(sprite, palette): Idle or None}, problem)`."""

    def __init__(self, sprites: us.UnitSprites, wanted):
        super().__init__()
        self.sprites, self.wanted = sprites, sorted(wanted)

    def run(self):
        made = {key: self.sprites.idle(*key) for key in self.wanted}
        return made, self.sprites.problem


def _qimage(picture: us.Picture) -> QImage:
    return QImage(picture.rgba, picture.width, picture.height, picture.width * 4,
                  QImage.Format_RGBA8888).copy()


def _stamp(path: Path) -> Optional[tuple]:
    try:
        found = path.stat()
    except OSError:
        return None
    return (str(path), found.st_size, found.st_mtime_ns)


class EncounterMap(QWidget):
    """The map column of the Encounters page (see the module's notes)."""

    #: A unit was clicked: its `(battle, slot)`.
    unit_picked = Signal(tuple)
    #: A unit was dropped on another tile: its `(battle, slot)`, then X, Y and level.
    unit_moved = Signal(tuple, int, int, int)

    def __init__(self, state, units_of: Callable[[int], list], name_of: Callable[[int], str],
                 parent=None):
        super().__init__(parent)
        self.state = state
        self.units_of, self.name_of = units_of, name_of
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(6)

        head = QHBoxLayout()
        head.setSpacing(10)
        self.title = QLabel("")
        self.title.setStyleSheet("font-weight: 600; font-size: 12pt;")
        self.title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        head.addWidget(self.title, 1)
        self.map_label = QLabel("Map")
        head.addWidget(self.map_label)
        self.map_box = QComboBox()
        self.map_box.setMinimumWidth(MAP_BOX_LEAST)
        self.map_box.setToolTip("The map this encounter is drawn on. The game's own maps for it "
                                "come first.")
        self.map_box.activated.connect(self._map_chosen)
        head.addWidget(self.map_box)
        column.addLayout(head)

        self.view = MapView()
        self.view.show_info = False
        self.view.overlay = self.paint_units
        self.view.grabber = self
        self.view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.view.setMinimumSize(MAP_LEAST, MAP_LEAST)
        column.addWidget(self.view, 1)

        self.legend = QLabel("")
        self.legend.setTextFormat(Qt.RichText)
        self.legend.setWordWrap(True)
        column.addWidget(self.legend)
        #: Said under the map only when there is something to say: a unit
        #: that can't be moved, sprites that can't be drawn.
        self.note = QLabel("")
        self.note.setProperty("role", "muted")
        self.note.setWordWrap(True)
        self.note.setVisible(False)
        column.addWidget(self.note)
        self.hint = QLabel(HINT)
        self.hint.setProperty("role", "muted")
        self.hint.setWordWrap(True)
        column.addWidget(self.hint)

        #: The battle shown, its units, the slot picked, and the map drawn.
        self.battle = None
        self.units: list = []
        self.selected = None
        self.shown_map = None
        self._shown_look = None
        self._wanted_map = None
        self._token = 0
        self._reading = False
        self._reading_for = None
        #: `{battle: map number}` chosen in the Map box this session.
        self.chosen: dict = {}
        #: The battle maps and unit sprites of one unpacked game, read again
        #: when its files change.
        self._maps = None
        self._maps_key = None
        self._sprites = None
        self._sprites_key = None
        #: `{(sprite, palette): {"front": [(QImage, stand x, stand y, 60ths)], "back": ..., "flying": bool}}`,
        #: None where it can't be drawn, and what is being drawn.
        self._pictures: dict = {}
        self._pending: set = set()
        self._sprite_job = None
        self.sprite_problem = ""
        #: A unit being dragged: its address, where it started and the tile it is over.
        self._grab = None
        #: What the last paint drew: `[(address, sprite rectangle, ground point)]`, topmost last,
        #: and `{address: the tip of the wedge on its tile}`.
        self.drawn: list = []
        self.wedge_tips: dict = {}
        #: The time the animations count from; the checks hold it still.
        self.clock = time.monotonic
        self._started = self.clock()
        self._refuse_note = ""

    # -- the game's files -----------------------------------------------------------

    def game_dir(self) -> Optional[Path]:
        root = getattr(self.state, "nxd_unpack_dir", None)
        return Path(root) if root and Path(root).is_dir() else None

    def battle_maps(self) -> Optional[bmaps.BattleMaps]:
        game = self.game_dir()
        if game is None:
            return None
        key = (str(game), _stamp(game / bmaps.SCENARIO_FILE), _stamp(game / bmaps.RANDOM_FILE))
        if key != self._maps_key:
            self._maps, self._maps_key = bmaps.read_battle_maps(game), key
        return self._maps

    def unit_sprites(self) -> Optional[us.UnitSprites]:
        game = self.game_dir()
        if game is None:
            return None
        key = (str(game), _stamp(game / us.G2D_FILE), _stamp(game / us.BATTLE_BIN))
        if key != self._sprites_key:
            self._sprites, self._sprites_key = us.UnitSprites(game), key
            self._pictures.clear()
            self.sprite_problem = ""
        return self._sprites

    def maps_for(self, battle: int) -> list:
        """The maps the game's tables fight `battle` on, in their order."""
        maps = self.battle_maps()
        return maps.of(battle) if maps is not None else []

    # -- what is shown --------------------------------------------------------------

    def show_unit(self, address) -> None:
        """Shows the battle `address` is in, its unit at `address` picked."""
        address = tuple(address) if address is not None else None
        if address is not None and address[0] != self.battle:
            self.show_battle(address[0])
        self.selected = address
        self.refresh_units()

    def show_battle(self, battle: int) -> None:
        self.battle = battle
        self._grab = None
        self.title.setText(self.name_of(battle) if battle is not None else "")
        self.map_label.setVisible(battle is not None)
        self.map_box.setVisible(battle is not None)
        self._fill_map_box()
        self.refresh()

    def _fill_map_box(self) -> None:
        own = self.maps_for(self.battle) if self.battle is not None else []
        names = me_page.map_names(self.state)
        self.map_box.blockSignals(True)
        self.map_box.clear()
        if not own:
            self.map_box.addItem(PICK_A_MAP, None)
        for number in own:
            self.map_box.addItem(me_page.map_label(number, names.get(number, "")), number)
        others = [n for n in sorted(names) if n not in own]
        if others:
            self.map_box.insertSeparator(self.map_box.count())
            for number in others:
                self.map_box.addItem(me_page.map_label(number, names.get(number, "")), number)
        wanted = self.chosen.get(self.battle, own[0] if own else None)
        index = self.map_box.findData(wanted) if wanted is not None else 0
        self.map_box.setCurrentIndex(max(0, index))
        self.map_box.blockSignals(False)

    def map_number(self) -> Optional[int]:
        """The map drawn for the battle shown: chosen in the box, or the game's first."""
        if self.battle is None:
            return None
        own = self.maps_for(self.battle)
        return self.chosen.get(self.battle, own[0] if own else None)

    def _map_chosen(self, index: int) -> None:
        number = self.map_box.itemData(index)
        if number is None or self.battle is None:
            return
        self.chosen[self.battle] = number
        self.refresh()

    def choose_map(self, number: int) -> None:
        """Picks a map in the Map box, as a click would."""
        index = self.map_box.findData(number)
        if index >= 0:
            self.map_box.setCurrentIndex(index)
            self._map_chosen(index)

    def refresh(self) -> None:
        """Reads the map again if what it is drawn from changed, and the units."""
        self.refresh_units()
        game = self.game_dir()
        number = self.map_number()
        if game is None:
            self._no_map(NO_GAME)
            return
        if self.battle is None:
            self._no_map(PICK_AN_ENCOUNTER)
            return
        if number is None:
            self._no_map(NO_MAP)
            return
        try:
            has_map = bool(mc.read_gns(game / mc.MAP_FOLDER, number).states())
        except (OSError, mc.MapError):
            has_map = False
        if not has_map:
            self._no_map(f"Map {number:03d} has no battle map in the game's files.")
            return
        look = self._look_of(number)
        if number == self.shown_map and look == self._shown_look and self.view.scene is not None:
            return
        self._token += 1
        self._wanted_map = number
        self.view.set_message(f"Reading map {number:03d}...")
        if not self._reading:
            self._start_reading()

    def _no_map(self, message: str) -> None:
        self.shown_map = None
        self._wanted_map = None
        self.view.set_scene(None)
        self.view.set_message(message)
        self._update_legend()

    def _look_of(self, number: int) -> tuple:
        """What map `number` is drawn from: its look, the mod's model, rows and grid edits (Treasure Hunter's)."""
        game = self.game_dir()
        enhanced = game is not None and me.mesh_path(game, number).is_file()
        mesh, pictures = me_page.mod_look(self.state, number) if enhanced else (None, {})
        rows = me_page.mod_rows(self.state, number) if enhanced else {}
        edits = {key: dict(found) for key, found in (getattr(self.state, "map_edits", {}) or {}).items()}
        return (ms.ENHANCED if enhanced else ms.CLASSIC, mesh, tuple(sorted(pictures.items())),
                repr(sorted((t, sorted(f.items())) for t, f in rows.items())), repr(sorted(edits.items())))

    def _start_reading(self) -> None:
        number, token, game = self._wanted_map, self._token, self.game_dir()
        if number is None or game is None:
            return
        look = self._look_of(number)
        mesh, pictures = me_page.mod_look(self.state, number)
        self._reading = True
        self._reading_for = (number, token, look)
        worker = ms.SceneWorker(token, game, number, look[0], mc.State(),
                                getattr(self.state, "nxd_sqlite_path", None),
                                mesh if look[0] == ms.ENHANCED else None,
                                pictures if look[0] == ms.ENHANCED else {}, 0,
                                me_page.mod_rows(self.state, number) if look[0] == ms.ENHANCED else {})
        run_in_thread(worker, on_finished=self._scene_ready, on_failed=self._scene_failed)

    def _scene_ready(self, result) -> None:
        self._reading = False
        token, scene, error = result
        number, _asked, look = self._reading_for
        if token != self._token or number != self._wanted_map:
            self._start_reading()            # another map was asked for since
            return
        if scene is None:
            self._no_map(f"Map {number:03d} could not be drawn: {error}")
            return
        edits = (getattr(self.state, "map_edits", {}) or {}).get(scene.grid_key, {}) if scene.grid_key else {}
        tiles = ([me_page.as_edited(t, edits.get((t.x, t.z, t.level), {})) for t in scene.terrain.tiles]
                 if scene.terrain is not None else [])
        self.shown_map, self._shown_look = number, look
        self.view.set_message(" ".join(scene.notes))
        self.view.set_scene(scene, tiles, ())
        self._units_changed()

    def _scene_failed(self, message: str) -> None:
        self._reading = False
        self._no_map(f"This map could not be drawn: {message}")

    # -- the units --------------------------------------------------------------------

    def refresh_units(self) -> None:
        """Reads the battle's units from the page again: after an edit, a trade or a refresh."""
        self.units = list(self.units_of(self.battle)) if self.battle is not None else []
        self._units_changed()

    def _units_changed(self) -> None:
        self._want_sprites()
        self._update_legend()
        self._say_note()
        moving = bool(self.units) and self.view.scene is not None
        if moving != self.view.overlay_moves:
            self.view.overlay_moves = moving
            self.view.update_overlay_ticker()
        self.view.update()

    def unit_at_address(self, address) -> Optional[MapUnit]:
        for unit in self.units:
            if unit.address == tuple(address):
                return unit
        return None

    def _update_legend(self) -> None:
        shown = [u for u in self.units if not u.empty]
        if self.view.scene is None or not shown:
            self.legend.setText("")
            self.legend.setVisible(False)
            return
        parts = [f'<span style="color:{TEAM_COLOURS[team]};">&#9679;</span>&nbsp;{TEAM_NAMES[team]}'
                 for team in sorted({u.team for u in shown})]
        if any(u.randomly_present for u in shown):
            parts.append("<b>?</b>&nbsp;Randomly present: may not appear in the battle")
        if any(u.disabled for u in shown):
            parts.append(f'<span style="color:{DISABLED_COLOUR};">&#9679;</span>&nbsp;Grey: disabled by '
                         f'its row')
        self.legend.setText("&nbsp;&nbsp;&nbsp;&nbsp;".join(parts))
        self.legend.setVisible(True)

    def _say_note(self) -> None:
        notes = []
        if self._refuse_note:
            notes.append(self._refuse_note)
        picked = self.unit_at_address(self.selected) if self.selected is not None else None
        if picked is not None:
            where = f"{picked.address[0]}/{picked.address[1]}"
            if picked.empty:
                notes.append(EMPTY.format(where))
            elif self.view.scene is not None and self._ground(picked)[0] is None:
                notes.append(OFF_GRID.format(where, picked.x, picked.y))
            elif picked.sprite is None:
                notes.append(UNKNOWN_SPRITE.format(where))
            elif (self._pictures.get((picked.sprite, picked.palette), True) is None
                  and not self.sprite_problem):
                notes.append(NO_PICTURE.format(where, picked.sprite))
        if self.sprite_problem and self.units:
            notes.append(NO_SPRITES.format(self.sprite_problem))
        self.note.setText(" ".join(notes))
        self.note.setVisible(bool(notes))

    # -- sprites ------------------------------------------------------------------------

    def _want_sprites(self) -> None:
        sprites = self.unit_sprites()
        if sprites is None:
            return
        wanted = {(u.sprite, u.palette) for u in self.units if u.sprite is not None}
        wanted -= set(self._pictures) | self._pending
        if not wanted or self._sprite_job is not None:
            return
        self._pending |= wanted
        self._sprite_job = SpriteWorker(sprites, wanted)
        run_in_thread(self._sprite_job, on_finished=self._sprites_ready, on_failed=self._sprites_failed)

    def _sprites_ready(self, result) -> None:
        made, problem = result
        self._sprite_job = None
        for key, idle in made.items():
            self._pending.discard(key)
            if idle is None:
                self._pictures[key] = None
                continue
            self._pictures[key] = {
                side: [(_qimage(p), p.stand_x, p.stand_y, delay) for p, delay in getattr(idle, side)]
                for side in ("front", "back")}
            self._pictures[key]["flying"] = idle.flying
        self.sprite_problem = problem if any(v is None for v in self._pictures.values()) else ""
        self._say_note()
        self.view.update()
        self._want_sprites()

    def _sprites_failed(self, message: str) -> None:
        self._sprite_job = None
        for key in list(self._pending):
            self._pictures[key] = None
        self._pending.clear()
        self.sprite_problem = message
        self._say_note()

    def pictures_for(self, unit: MapUnit) -> Optional[dict]:
        return self._pictures.get((unit.sprite, unit.palette)) if unit.sprite is not None else None

    # -- where things are on screen -----------------------------------------------------

    def _ground(self, unit: MapUnit, at=None) -> tuple:
        """
        `(world point, tile)` where `unit` stands (or would, at `(x, y,
        level)`), or (None, None) off the map. A unit on the upper level
        where the tile has none stands on the ground: most maps fill their
        upper level with places for nothing (no cursor, height 0), and two of
        Lake Poescas North 3's units (207) stand on the upper level of one.
        """
        if self.view.scene is None:
            return None, None
        x, y, level = at if at is not None else (unit.x, unit.y, int(unit.upper))
        tile = self.view.tile((x, y, level))
        if level and (tile is None or not ms.shows(tile) or tile.no_cursor):
            tile = self.view.tile((x, y, 0))
        if tile is None or not ms.shows(tile):
            return None, None
        corners = ms.tile_corners(tile, 0.0)
        return tuple(sum(c[i] for c in corners) / 4 for i in range(3)), tile

    def _project(self, point) -> QPointF:
        view = self.view
        return QPointF(*view.renderer.project(point, view.camera, view.width(), view.height()))

    def pixels_per_unit(self) -> float:
        view = self.view
        return view.height() / max(1e-6, 2 * view.renderer.half_height(
            view.camera, view.width() / max(1, view.height())))

    def view_of(self, unit: MapUnit, world) -> tuple:
        """`("front" or "back", mirrored)`: which way the camera sees `unit` facing."""
        dx, dz = FACING_STEPS.get(unit.facing & 3, (0, -1))
        a = self._project(world)
        b = self._project((world[0] - dx * 14.0, world[1], world[2] + dz * 14.0))
        across, down = b.x() - a.x(), b.y() - a.y()
        return ("front" if down > 0 else "back"), across > 0

    # -- painting -------------------------------------------------------------------------

    def placed_units(self) -> list:
        """`[(unit, world point, tile, place in its tile, units on its tile)]`, a dragged one where it is going."""
        places = {}
        for unit in self.units:
            if unit.empty:
                continue
            at = None
            if self._grab is not None and self._grab["address"] == unit.address and self._grab.get("to"):
                at = self._grab["to"]
            world, tile = self._ground(unit, at)
            if world is None:
                continue
            key = (tile.x, tile.z, tile.level)
            places.setdefault(key, []).append((unit, world, tile))
        out = []
        for members in places.values():
            for n, (unit, world, tile) in enumerate(members):
                out.append((unit, world, tile, n, len(members)))
        return out

    def paint_units(self, p: QPainter) -> None:
        view = self.view
        p.setRenderHint(QPainter.Antialiasing)
        ppu = self.pixels_per_unit()
        ticks = int((self.clock() - self._started) * TICKS_A_SECOND)
        placed = self.placed_units()
        drawn = []
        # The tiles first: the picked one gold, shared ones outlined.
        shared = {}
        for unit, world, tile, n, count in placed:
            shared.setdefault((tile.x, tile.z, tile.level), (tile, count))
        picked_tile = None
        for unit, world, tile, n, count in placed:
            if unit.address == self.selected:
                picked_tile = tile
        for key, (tile, count) in shared.items():
            corners = QPolygonF([self._project(c) for c in ms.tile_corners(tile, 0.4)])
            if picked_tile is not None and (tile.x, tile.z, tile.level) == (
                    picked_tile.x, picked_tile.z, picked_tile.level):
                p.setPen(QPen(PICKED_EDGE, 2.6))
                p.setBrush(PICKED_FILL)
                p.drawPolygon(corners)
            elif count > 1:
                pen = QPen(QColor(235, 235, 235, 200), 1.6)
                pen.setStyle(Qt.DashLine)
                p.setPen(pen)
                p.setBrush(QColor(255, 255, 255, 28))
                p.drawPolygon(corners)
        if self._grab is not None and self._grab.get("to"):
            tile = view.tile(self._grab["to"])
            if tile is not None:
                p.setPen(QPen(PICKED_EDGE, 2.0, Qt.DashLine))
                p.setBrush(Qt.NoBrush)
                p.drawPolygon(QPolygonF([self._project(c) for c in ms.tile_corners(tile, 0.4)]))
        # Then the units, the farthest first.
        order = []
        for unit, world, tile, n, count in placed:
            ground = self._project(world)
            spread = (n - (count - 1) / 2) * SHARED_STEP * mc.TILE_SIZE * ppu if count > 1 else 0.0
            order.append((ground.y(), ground.x() + spread, unit, world, QPointF(ground.x() + spread, ground.y()),
                          SHARED_SCALE if count > 1 else 1.0, count))
        order.sort(key=lambda o: (o[0], o[1]))
        wedges = []
        for _y, _x, unit, world, ground, scale, count in order:
            colour = QColor(DISABLED_COLOUR if unit.disabled else TEAM_COLOURS.get(unit.team, TEAM_COLOURS[0]))
            ring = QColor(colour)
            ring.setAlpha(150 if (unit.randomly_present or unit.disabled) else 230)
            pen = QPen(ring, 2.4 if unit.address == self.selected else 1.8)
            if unit.randomly_present:
                pen.setStyle(Qt.DashLine)
            p.setPen(pen)
            fill = QColor(colour)
            fill.setAlpha(55)
            p.setBrush(fill)
            p.drawEllipse(ground, RING_W * ppu * scale, RING_H * ppu * scale)
            rect = self._paint_sprite(p, unit, world, ground, ppu * scale, ticks)
            if rect is None:
                rect = QRectF(ground.x() - RING_W * ppu * scale, ground.y() - RING_H * ppu * scale,
                              2 * RING_W * ppu * scale, 2 * RING_H * ppu * scale)
            if unit.randomly_present:
                self._paint_badge(p, QPointF(rect.right() - BADGE_RADIUS, rect.top() + BADGE_RADIUS))
            drawn.append((unit.address, rect, ground))
            if count == 1 or unit.address == self.selected:
                wedges.append((unit, world, colour))
        tips = {}
        for unit, world, colour in wedges:
            tip = self._paint_wedge(p, unit, world, colour)
            if tip is not None:
                tips[unit.address] = tip
        self.drawn = drawn
        self.wedge_tips = tips

    def _paint_sprite(self, p: QPainter, unit: MapUnit, world, ground: QPointF, ppu: float,
                      ticks: int) -> Optional[QRectF]:
        pictures = self.pictures_for(unit)
        if not pictures:
            return None
        side, mirrored = self.view_of(unit, world)
        frames = pictures.get(side) or pictures.get("front") or pictures.get("back")
        if not frames:
            return None
        total = sum(f[3] for f in frames)
        tick = (ticks + 9 * unit.address[1]) % max(1, total)
        image, stand_x, stand_y = frames[-1][:3]
        for frame in frames:
            if tick < frame[3]:
                image, stand_x, stand_y = frame[:3]
                break
            tick -= frame[3]
        lift = 0.0
        if pictures.get("flying"):
            seconds = ticks / TICKS_A_SECOND
            lift = (FLY_HEIGHT + FLY_BOB * math.sin(2 * math.pi * seconds / FLY_SECONDS)) * ppu
        size = WORLD_PER_HD_PIXEL * ppu
        width, height = image.width() * size, image.height() * size
        left = ground.x() - ((image.width() - stand_x) if mirrored else stand_x) * size
        top = ground.y() - stand_y * size - lift
        rect = QRectF(left, top, width, height)
        p.save()
        if unit.disabled:
            p.setOpacity(DISABLED_OPACITY)
        elif unit.randomly_present:
            p.setOpacity(RANDOM_OPACITY)
        if mirrored:
            p.translate(rect.center())
            p.scale(-1, 1)
            p.translate(-rect.center())
        p.drawImage(rect, image)
        p.restore()
        return rect

    def _paint_badge(self, p: QPainter, centre: QPointF) -> None:
        p.setPen(QPen(QColor(20, 20, 20, 220), 1.2))
        p.setBrush(QColor(245, 245, 245, 235))
        p.drawEllipse(centre, BADGE_RADIUS, BADGE_RADIUS)
        font = QFont(self.font())
        font.setBold(True)
        font.setPixelSize(12)
        p.setFont(font)
        p.setPen(QColor(20, 20, 20))
        p.drawText(QRectF(centre.x() - BADGE_RADIUS, centre.y() - BADGE_RADIUS, 2 * BADGE_RADIUS,
                          2 * BADGE_RADIUS), int(Qt.AlignCenter), "?")

    def _paint_wedge(self, p: QPainter, unit: MapUnit, world, colour: QColor) -> Optional[QPointF]:
        """A small wedge on the unit's tile, from its middle towards the edge it faces: its tip."""
        _point, tile = self._ground(unit)
        if tile is None:
            return None
        corners = ms.tile_corners(tile, 0.6)
        middle = tuple(sum(c[i] for c in corners) / 4 for i in range(3))
        # The tile's corners are (x0, z0), (x1, z0), (x1, z1), (x0, z1): its
        # south edge is the first two, west the last and first, north the
        # last two, east the middle two.
        a, b = {0: (0, 1), 1: (3, 0), 2: (2, 3), 3: (1, 2)}[unit.facing & 3]
        edge = tuple((corners[a][i] + corners[b][i]) / 2 for i in range(3))
        towards = tuple(edge[i] - middle[i] for i in range(3))
        across = tuple((corners[b][i] - corners[a][i]) * 0.16 for i in range(3))
        tip = tuple(middle[i] + towards[i] * 0.95 for i in range(3))
        base = tuple(middle[i] + towards[i] * 0.55 for i in range(3))
        points = [self._project(tip), self._project(tuple(base[i] + across[i] for i in range(3))),
                  self._project(tuple(base[i] - across[i] for i in range(3)))]
        fill = QColor(PICKED_EDGE) if unit.address == self.selected else QColor(colour)
        fill.setAlpha(245 if unit.address == self.selected else 140)
        p.setPen(QPen(QColor(20, 20, 20, 170), 1))
        p.setBrush(fill)
        p.drawPolygon(QPolygonF(points))
        return points[0]

    # -- clicking and dragging units --------------------------------------------------------

    def units_at(self, point) -> list:
        """The units under `point`, topmost first: their drawn sprites, then their tile."""
        hits = [address for address, rect, _ground in reversed(self.drawn) if rect.contains(point)]
        if hits:
            return hits
        key = self.view.tile_at(point)
        if key is None:
            return []
        return [u.address for u in self.units
                if not u.empty and (u.x, u.y) == (key[0], key[1]) and self._ground(u)[1] is not None
                and (self._ground(u)[1].level == key[2])]

    def press(self, point) -> bool:
        """The map view's grabber: a press on a unit is that unit's; anywhere else, the map's."""
        found = self.units_at(point)
        if not found:
            return False
        self._grab = {"address": found[0], "members": found, "to": None}
        return True

    def move(self, point) -> None:
        if self._grab is not None:
            self._grab["to"] = self.view.tile_at(point)
        self.view.update()

    def release(self, point, moved: bool) -> None:
        grab, self._grab = self._grab, None
        if grab is None:
            return
        if not moved:
            members = grab["members"]
            chosen = members[0] if len(members) == 1 or self._sprite_hit(point) else self._choose(members, point)
            if chosen is not None:
                self._refuse_note = ""
                self.unit_picked.emit(tuple(chosen))
            self.view.update()
            return
        unit = self.unit_at_address(grab["address"])
        target = grab.get("to")
        if unit is None or target is None:
            self.view.update()
            return
        if (target[0], target[1], target[2]) == (unit.x, unit.y, int(unit.upper)):
            self.view.update()
            return
        if not unit.editable:
            self._refuse_note = CANT_MOVE.format(f"{unit.address[0]}/{unit.address[1]}")
            self._say_note()
            self.unit_picked.emit(tuple(unit.address))
            self.view.update()
            return
        self._refuse_note = ""
        self.unit_moved.emit(tuple(unit.address), int(target[0]), int(target[1]), int(target[2]))
        self.view.update()

    def _sprite_hit(self, point) -> bool:
        return any(rect.contains(point) for _address, rect, _ground in self.drawn)

    def _choose(self, members: list, point) -> Optional[tuple]:
        """Which of the units sharing a tile: a menu of them, at the click."""
        menu = QMenu(self)
        for address in members:
            unit = self.unit_at_address(address)
            text = f"{address[0]}/{address[1]}  ·  {unit.label if unit else ''}"
            action = menu.addAction(text)
            action.setData(tuple(address))
        chosen = menu.exec(self.view.mapToGlobal(QPointF(point).toPoint()))
        return tuple(chosen.data()) if chosen is not None else None
