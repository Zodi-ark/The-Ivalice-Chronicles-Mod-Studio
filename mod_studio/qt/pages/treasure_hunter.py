"""
Treasure Hunter, on the battle map.

Zodi, 5 October: "Can we redesign the Treasure Hunter page so that it uses
our Map Viewer in a functional way so that the Treasure Hunter Tiles are
highlighted on the map and clicking on them will bring up menu allowing the
user to edit it. Also simply being able to click and drag the tile on the
map to change the x and y positions would be a nice touch. If the user has
the sprite textures unpacked that are used on the items page, it would also
be a nice touch to have the rare item and common item float up and down
next to each other over their respective tile. If the item is set to 0 then
you do should not display the sprite texture. There are maps where all four
tile placements are at x 0 and y 0 so be aware of that."

A map's treasure (`MapTrapFormationData.xml`, its row numbered as the map)
is four tiles, each an X and a Y (0 to 15: the battle grid's x and z; the
row holds no level, so the ground's tile is used), a rare item, a common
item and a trap. So:

- **The map** is the Map Editor's view of it (`MapView`): the enhanced look
  where the game has one, the classic one where not, its grid as the mod
  has it, the mod's own model and textures drawn.
- **Each treasure tile is marked** on it in its own colour, with its
  number. Tiles sharing a place (all four at 0, 0 on many maps) share one
  mark, their numbers side by side; a tile with neither item is faint.
- **Clicking a mark** shows that tile's fields beside the map; where
  several share it, a menu says which. **Dragging a mark** to another tile
  moves it there: its X and Y, as if typed. A drag anywhere else turns the
  map, as in the Map Editor.
- **Each tile's two items float over it**, rare on the left and common on
  the right, from their sprite textures (`ei_s_NNN_uitx.tex`, the Items
  page's Sprite Texture) where those are unpacked, or replaced in the mod.
  An item of 0 has none.

The record list, the fields and the edit store are `TableEditorPage`'s, as
before the map: they write `state.item_table_edits["map_trap"]`.
"""
from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QIcon, QImage, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import (
    QButtonGroup, QHBoxLayout, QLabel, QMenu, QPushButton, QSizePolicy, QStackedWidget,
    QVBoxLayout, QWidget,
)

from ... import constants as c
from ... import map_classic as mc
from ... import map_enhanced as me
from ... import paths
from ... import texture_data as td
from .. import map_scene as ms
from ..widgets.field_rows import DropdownFieldRow, FlagFieldPanel, NumericFieldRow
from ..widgets.map_view import MapView
from ..workers import Worker, run_in_thread
from . import map_editor as me_page
from .table_editor import TableEditorPage, _groups_for, _range_for, flag_choices

BLURB = ("Traps and buried treasure on each map. Click a treasure tile on the map to edit it, or "
         "drag it to another tile.")

#: Where and what before the trap, which is the order somebody fills a
#: treasure tile in. `MAPTRAP_SLOT_FIELD_LABELS` has Trap third, between the
#: coordinates and the items - correct as a description of the columns,
#: wrong as a reading order.
SLOT_FIELD_ORDER = ["X", "Y", "RareItemId", "CommonItemId", "TrapFlags"]

#: The narrowest a tile's item dropdown may be: its widest entry, "000 -
#: Featherweave Cloak", needs 210px (measured; reported from real use).
TILE_COMBO_WIDTH = 210

#: The fields beside the map, and their labels' width ("Common Item" the
#: longest): the rows' usual 200 left the item names clipped in a panel
#: beside a map.
SIDE_WIDTH, LABEL_WIDTH = 380, 104

#: Each treasure tile's colour on the map and on its button: gold, blue,
#: green, rose, apart on the grid's own green and grey.
SLOT_COLOURS = {1: "#f2b53c", 2: "#4fb4f2", 3: "#9be06a", 4: "#ec72b8"}

#: The items' sprites over a tile: their size on screen, how far above the
#: tile's middle, how far they float up and down, and how long one float
#: takes. A tile's sprites float in turn, a quarter of a float apart.
SPRITE_SIZE, SPRITE_LIFT, BOB_HEIGHT, BOB_SECONDS = 40, 34, 5.0, 1.6
#: Each number's disc on a mark, and the room between two side by side.
BADGE_RADIUS, BADGE_STEP = 10.0, 23.0

HINT = ("Click a treasure tile to edit it, or drag it to another tile. Drag anywhere else to turn "
        "the map, Shift and drag to move it, and use the wheel to zoom.")
NO_GAME = "No game files yet. Unpack your game on General Setup to see its maps here."


class SpriteWorker(Worker):
    """
    Decodes items' sprite textures off the GUI thread: a `.tex` may go
    through FF16Tools. Returns `{item id: PIL image, or None}`.
    """

    def __init__(self, wanted: dict, cli_path, cache_dir):
        super().__init__()
        #: `{item id: (game texture or None, replacement or None)}`
        self.wanted = dict(wanted)
        self.cli_path, self.cache_dir = cli_path, cache_dir

    def run(self):
        out = {}
        for item_id, (game, replacement) in self.wanted.items():
            image = None
            try:
                if replacement is not None:
                    image = td.load_replacement_preview(Path(replacement), self.cli_path, self.cache_dir)
                elif game is not None:
                    image = td.load_game_texture_preview(Path(game), self.cli_path, self.cache_dir)
            except Exception:                                  # noqa: BLE001
                image = None
            if image is not None:
                image = image.convert("RGBA")
                image.thumbnail((128, 128))
            out[item_id] = image
        return out


def _qimage(image) -> QImage:
    data = image.tobytes("raw", "RGBA")
    return QImage(data, image.width, image.height, image.width * 4, QImage.Format_RGBA8888).copy()


def _dot(colour: str, size: int = 12) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor(colour))
    painter.setPen(QPen(QColor(0, 0, 0, 160), 1))
    painter.drawEllipse(QRectF(1, 1, size - 2, size - 2))
    painter.end()
    return QIcon(pixmap)


class TreasureHunterPage(TableEditorPage):
    """The Treasure Hunter tab: a map's treasure tiles on its map (see the module's notes)."""

    def __init__(self, state, title: str = "Treasure Hunter", blurb: str = BLURB, parent=None):
        super().__init__(state, "map_trap", title, blurb, parent)

    # -- building -----------------------------------------------------------------

    def build_own_form(self, form, scroll, holder, right, split, outer) -> bool:
        #: Which tile's fields show, 1 to 4.
        self.slot = c.MAPTRAP_SLOTS[0]
        self.sections = []
        #: Each tile's fields, and its heading ("Tile 1").
        self.tiles, self.tile_headings = [], []
        self.stack = QStackedWidget()
        for slot in c.MAPTRAP_SLOTS:
            body = QWidget()
            column = QVBoxLayout(body)
            column.setContentsMargins(0, 0, 0, 0)
            column.setSpacing(2)
            heading = QLabel(f"Tile {slot}")
            heading.setStyleSheet("font-weight: 600;")
            column.addWidget(heading)
            ordered = sorted(c.MAPTRAP_SLOT_FIELD_LABELS.items(),
                             key=lambda pair: SLOT_FIELD_ORDER.index(pair[0])
                             if pair[0] in SLOT_FIELD_ORDER else len(SLOT_FIELD_ORDER))
            for base, label in ordered:
                field_name = f"{base}{slot}"
                choices = flag_choices(field_name, self.spec.entry_tag)
                if choices:
                    widget = FlagFieldPanel(field_name, label, _groups_for(field_name, choices),
                                            columns=2)
                elif base in ("RareItemId", "CommonItemId"):
                    widget = DropdownFieldRow(field_name, label)
                    widget.combo.setMinimumWidth(TILE_COMBO_WIDTH)
                    widget.set_choices(self._item_choices())
                    self.item_dropdowns.append(widget)
                else:
                    low, high = _range_for(field_name)
                    if base in ("X", "Y"):
                        low, high = c.MAPTRAP_XY_MIN, c.MAPTRAP_XY_MAX
                    widget = NumericFieldRow(field_name, label, low, high)
                if hasattr(widget, "label"):
                    # Beside the map, a narrower panel: the labels are short.
                    widget.label.setFixedWidth(LABEL_WIDTH)
                widget.edited.connect(self._on_field_edited)
                self.rows[field_name] = widget
                column.addWidget(widget)
            column.addStretch(1)
            self.tile_headings.append(heading)
            self.tiles.append(body)
            self.stack.addWidget(body)

        # A button a tile, in its colour on the map.
        chips = QHBoxLayout()
        chips.setSpacing(6)
        self.chip_group = QButtonGroup(self)
        self.chip_group.setExclusive(True)
        self.chips = {}
        for slot in c.MAPTRAP_SLOTS:
            chip = QPushButton(f"Tile {slot}")
            chip.setCheckable(True)
            chip.setIcon(_dot(SLOT_COLOURS[slot]))
            chip.setToolTip(f"Tile {slot}'s fields. On the map, its mark is this colour.")
            chip.clicked.connect(lambda _on=False, s=slot: self.show_slot(s))
            self.chip_group.addButton(chip)
            self.chips[slot] = chip
            chips.addWidget(chip)
        chips.addStretch(1)
        self.chips[self.slot].setChecked(True)

        form.addWidget(self.stack)
        form.addStretch(1)
        scroll.setWidget(holder)
        self.scroll = scroll
        #: Where the tile shown is, said under its fields: on the map's grid
        #: or off it.
        self.place_note = QLabel("")
        self.place_note.setProperty("role", "muted")
        self.place_note.setWordWrap(True)

        side = QWidget()
        side.setFixedWidth(SIDE_WIDTH)
        side_column = QVBoxLayout(side)
        side_column.setContentsMargins(0, 0, 0, 0)
        side_column.setSpacing(8)
        side_column.addLayout(chips)
        side_column.addWidget(scroll, 1)
        side_column.addWidget(self.place_note)
        self.side = side

        self.view = MapView()
        self.view.show_info = False
        self.view.overlay = self._paint_treasure
        self.view.grabber = self
        self.view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.hint = QLabel(HINT)
        self.hint.setProperty("role", "muted")
        self.hint.setWordWrap(True)
        map_column = QVBoxLayout()
        map_column.setSpacing(6)
        map_column.addWidget(self.view, 1)
        map_column.addWidget(self.hint)

        body = QHBoxLayout()
        body.setSpacing(14)
        body.addLayout(map_column, 1)
        body.addWidget(side)
        right.addLayout(body, 1)
        split.addLayout(right, 1)
        outer.addLayout(split, 1)

        #: The map shown, and how it was read (`_look_of`), so a change made
        #: elsewhere (the Map Editor's tiles or model) reads it again.
        self.shown_map = None
        self._shown_look = None
        self._token = 0
        self._reading = False
        #: A drag of a mark in progress: the tiles under it, the one moving,
        #: where it started and where it is now.
        self._grab = None
        #: `{item id: QImage or None}`, and the ids being decoded.
        self._sprites = {}
        self._sprites_pending = set()
        self._sprite_job = None
        self._started = time.monotonic()
        return True

    # -- the tile shown --------------------------------------------------------

    def show_slot(self, slot: int) -> None:
        """Shows tile `slot`'s fields, and marks it on the map."""
        self.slot = slot
        self.chips[slot].setChecked(True)
        self.stack.setCurrentIndex(c.MAPTRAP_SLOTS.index(slot))
        self._say_place()
        self.view.update()

    def slots(self) -> dict:
        """
        `{slot: {"x", "y", "rare", "common", "trap"}}`: each tile as the
        fields beside the map say, edits and all.
        """
        out = {}
        for slot in c.MAPTRAP_SLOTS:
            out[slot] = {
                "x": self.rows[f"X{slot}"].value.value(),
                "y": self.rows[f"Y{slot}"].value.value(),
                "rare": self.rows[f"RareItemId{slot}"].current_id(),
                "common": self.rows[f"CommonItemId{slot}"].current_id(),
                "trap": self.rows[f"TrapFlags{slot}"].get_value_str(),
            }
        return out

    def at(self, x: int, y: int) -> list:
        """The treasure tiles at X `x`, Y `y`, in number order."""
        return [slot for slot, info in self.slots().items() if (info["x"], info["y"]) == (x, y)]

    def move_slot(self, slot: int, x: int, y: int) -> None:
        """Puts tile `slot` at X `x`, Y `y`, as typing them would."""
        x = min(c.MAPTRAP_XY_MAX, max(c.MAPTRAP_XY_MIN, int(x)))
        y = min(c.MAPTRAP_XY_MAX, max(c.MAPTRAP_XY_MIN, int(y)))
        record = {r.item_id: r for r in self.records()}.get(self.current_id)
        game = getattr(record, "values", {}) if record is not None else {}
        for base, value in (("X", x), ("Y", y)):
            field_name = f"{base}{slot}"
            self.rows[field_name].load(value, str(value) != str(game.get(field_name, "")))
        self._on_field_edited()

    def _say_place(self) -> None:
        info = self.slots()[self.slot]
        if self.view.scene is None:
            self.place_note.setText("")
            return
        if self.view.tile((info["x"], info["y"], 0)) is None:
            self.place_note.setText(f"Tile {self.slot} is at {info['x']}, {info['y']}, off this map's "
                                    f"grid, so it isn't marked on the map.")
        else:
            others = [s for s in self.at(info["x"], info["y"]) if s != self.slot]
            shared = (f" Tile {', '.join(map(str, others))} {'is' if len(others) == 1 else 'are'} there "
                      f"too.") if others else ""
            self.place_note.setText(f"Tile {self.slot} is at {info['x']}, {info['y']}.{shared}")

    # -- the record --------------------------------------------------------------

    def load_record(self, record_id: int) -> None:
        super().load_record(record_id)
        if self.current_id is None:
            return
        self._show_map(self.current_id)
        self._treasure_changed()

    def _on_field_edited(self) -> None:
        super()._on_field_edited()
        self._treasure_changed()

    def _treasure_changed(self) -> None:
        """What the fields say changed: the marks, the note and the sprites follow."""
        self._say_place()
        self._want_sprites()
        self.view.update()

    # -- the map -------------------------------------------------------------------

    def game_dir(self) -> Optional[Path]:
        root = getattr(self.state, "nxd_unpack_dir", None)
        return Path(root) if root and Path(root).is_dir() else None

    def _look_of(self, number: int) -> tuple:
        """
        What map `number` is drawn from: its look, the mod's model and
        textures for it, its rows and its grid's edits. Read again when any
        of it changes.
        """
        game = self.game_dir()
        enhanced = game is not None and me.mesh_path(game, number).is_file()
        mesh, pictures = me_page.mod_look(self.state, number) if enhanced else (None, {})
        rows = me_page.mod_rows(self.state, number) if enhanced else {}
        edits = {key: dict(found) for key, found in (getattr(self.state, "map_edits", {}) or {}).items()}
        return (ms.ENHANCED if enhanced else ms.CLASSIC, mesh, tuple(sorted(pictures.items())),
                repr(sorted((t, sorted(f.items())) for t, f in rows.items())), repr(sorted(edits.items())))

    def _show_map(self, number: int) -> None:
        game = self.game_dir()
        if game is None:
            self.shown_map = None
            self.view.set_scene(None)
            self.view.set_message(NO_GAME)
            return
        try:
            has_map = bool(mc.read_gns(game / mc.MAP_FOLDER, number).states())
        except (OSError, mc.MapError):
            has_map = False
        if not has_map:
            # 126 and 127 have a GNS and no files; most numbers have neither.
            self.shown_map = None
            self.view.set_scene(None)
            self.view.set_message(f"Map {number:03d} has no battle map in the game's files.")
            return
        look = self._look_of(number)
        if number == self.shown_map and look == self._shown_look and self.view.scene is not None:
            return
        self._token += 1
        self.view.set_message(f"Reading map {number:03d}...")
        if not self._reading:
            self._start_reading()

    def _start_reading(self) -> None:
        number, token = self.current_id, self._token
        game = self.game_dir()
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
        number, asked, look = self._reading_for
        if token != self._token or number != self.current_id:
            self._start_reading()            # another map was asked for since
            return
        if scene is None:
            self.shown_map = None
            self.view.set_scene(None)
            self.view.set_message(f"Map {number:03d} could not be drawn: {error}")
            return
        edits = (getattr(self.state, "map_edits", {}) or {}).get(scene.grid_key, {}) if scene.grid_key else {}
        tiles = ([me_page.as_edited(t, edits.get((t.x, t.z, t.level), {})) for t in scene.terrain.tiles]
                 if scene.terrain is not None else [])
        self.shown_map, self._shown_look = number, look
        self.view.set_message(" ".join(scene.notes))
        self.view.set_scene(scene, tiles, ())
        self._treasure_changed()

    def _scene_failed(self, message: str) -> None:
        self._reading = False
        self.shown_map = None
        self.view.set_scene(None)
        self.view.set_message(f"This map could not be drawn: {message}")

    # -- the marks, and the items over them ------------------------------------------

    def marks(self) -> list:
        """
        `[(tiles there, corners, {tile: its number's centre})]`: each place
        on the map with treasure, as drawn now (a tile being dragged, where
        it is being dragged to), in the view's pixels. A place off the
        map's grid isn't drawn.
        """
        view = self.view
        if view.scene is None:
            return []
        w, h = view.width(), view.height()
        slots = self.slots()
        if self._grab is not None and self._grab.get("to") is not None:
            moving = self._grab["slot"]
            slots[moving] = dict(slots[moving], x=self._grab["to"][0], y=self._grab["to"][1])
        places = {}
        for slot, info in slots.items():
            places.setdefault((info["x"], info["y"]), []).append(slot)
        out = []
        for (x, y), members in sorted(places.items()):
            tile = view.tile((x, y, 0))
            if tile is None:
                continue
            corners = [QPointF(*view.renderer.project(corner, view.camera, w, h))
                       for corner in ms.tile_corners(tile, 1.0)]
            middle = QPointF(sum(pt.x() for pt in corners) / 4, sum(pt.y() for pt in corners) / 4)
            badges = {slot: QPointF(middle.x() + (i - (len(members) - 1) / 2) * BADGE_STEP, middle.y())
                      for i, slot in enumerate(members)}
            out.append((members, corners, badges))
        return out

    def _paint_treasure(self, p: QPainter) -> None:
        view = self.view
        slots = self.slots()
        if self._grab is not None and self._grab.get("to") is not None:
            moving = self._grab["slot"]
            slots[moving] = dict(slots[moving], x=self._grab["to"][0], y=self._grab["to"][1])
        p.setRenderHint(QPainter.Antialiasing)
        seconds = time.monotonic() - self._started
        marks = self.marks()
        # Every mark first, then every tile's items, then the numbers: a
        # tile's items float above it, often over the next tile's mark, and
        # drawn mark by mark the next one covered them (048's tiles 1 and 2).
        # The numbers, what a click lands on, stay in front.
        for members, corners, _badges in marks:
            lead = self.slot if self.slot in members else members[0]
            empty = all(not slots[s]["rare"] and not slots[s]["common"] for s in members)
            colour = QColor(SLOT_COLOURS[lead])
            fill = QColor(colour)
            fill.setAlpha(40 if empty else 95)
            pen = QPen(colour, 3.2 if self.slot in members else 2.0)
            if empty:
                pen.setStyle(Qt.DashLine)
            p.setPen(pen)
            p.setBrush(QBrush(fill))
            p.drawPolygon(QPolygonF(corners))
        floating = False
        for _members, _corners, badges in marks:
            for slot, centre in badges.items():
                floating |= self._paint_items(p, centre, slot, slots[slot], seconds)
        for _members, _corners, badges in marks:
            for slot, centre in badges.items():
                self._paint_badge(p, centre, slot, slots[slot])
        if floating != view.overlay_moves:
            view.overlay_moves = floating
            view.update_overlay_ticker()

    def _paint_badge(self, p: QPainter, centre: QPointF, slot: int, info: dict) -> None:
        colour = QColor(SLOT_COLOURS[slot])
        if not info["rare"] and not info["common"]:
            colour.setAlpha(150)
        p.setPen(QPen(QColor(20, 20, 20, 220), 1.5 if slot != self.slot else 2.5))
        p.setBrush(colour)
        p.drawEllipse(centre, BADGE_RADIUS, BADGE_RADIUS)
        font = QFont(self.font())
        font.setBold(True)
        font.setPixelSize(13)
        p.setFont(font)
        p.setPen(QColor(20, 20, 20))
        p.drawText(QRectF(centre.x() - BADGE_RADIUS, centre.y() - BADGE_RADIUS, 2 * BADGE_RADIUS,
                          2 * BADGE_RADIUS), int(Qt.AlignCenter), str(slot))

    def sprite_rects(self, centre: QPointF, slot: int, info: dict, seconds: float) -> list:
        """
        `[(rect, item id)]`: where a tile's items float at `seconds`, rare
        on the left and common on the right, over its number at `centre`.
        Only items with a sprite to draw: an item of 0 has none.
        """
        out = []
        for side, item_id in ((-1, info["rare"]), (1, info["common"])):
            if not item_id or self._sprites.get(item_id) is None:
                continue
            phase = 2 * math.pi * (seconds / BOB_SECONDS + slot / 4 + (0.12 if side > 0 else 0))
            top = centre.y() - SPRITE_LIFT - SPRITE_SIZE - BOB_HEIGHT * math.sin(phase)
            left = centre.x() + (side - 1) * SPRITE_SIZE / 2 + side * 2
            out.append((QRectF(left, top, SPRITE_SIZE, SPRITE_SIZE), item_id))
        return out

    def _paint_items(self, p: QPainter, centre: QPointF, slot: int, info: dict, seconds: float) -> bool:
        """A tile's rare and common items over it, floating; whether any was drawn."""
        rects = self.sprite_rects(centre, slot, info, seconds)
        for rect, item_id in rects:
            p.drawImage(rect, self._sprites[item_id])
        return bool(rects)

    # -- sprites ---------------------------------------------------------------------

    def sprite_paths(self, item_id: int) -> tuple:
        """`(the game's sprite texture or None, the mod's replacement or None)` for an item."""
        rel = td.item_sprite_texture_path(item_id)
        game = self.game_dir()
        source = game / rel if game is not None and (game / rel).is_file() else None
        staged = (getattr(self.state, "texture_edits", {}) or {}).get(rel)
        replacement = staged.get("source_path") if isinstance(staged, dict) else None
        if replacement is not None and not Path(replacement).is_file():
            replacement = None
        return source, replacement

    def _want_sprites(self) -> None:
        """Decodes the sprites the tiles' items need that aren't to hand yet."""
        wanted = {}
        for info in self.slots().values():
            for item_id in (info["rare"], info["common"]):
                if item_id and item_id not in self._sprites and item_id not in self._sprites_pending:
                    source, replacement = self.sprite_paths(item_id)
                    if source is None and replacement is None:
                        self._sprites[item_id] = None
                        continue
                    wanted[item_id] = (source, replacement)
        if not wanted or self._sprite_job is not None:
            return
        self._sprites_pending |= set(wanted)
        self._sprite_job = SpriteWorker(wanted, getattr(self.state, "ff16tools_cli_path", None),
                                        paths.local_data_dir() / "texture_preview_cache")
        run_in_thread(self._sprite_job, on_finished=self._sprites_ready, on_failed=self._sprites_failed)

    def _sprites_ready(self, found: dict) -> None:
        self._sprite_job = None
        for item_id, image in found.items():
            self._sprites[item_id] = _qimage(image) if image is not None else None
            self._sprites_pending.discard(item_id)
        self.view.update()
        self._want_sprites()

    def _sprites_failed(self, _message: str) -> None:
        for item_id in list(self._sprites_pending):
            self._sprites[item_id] = None
        self._sprites_pending.clear()
        self._sprite_job = None

    def forget_sprites(self) -> None:
        """The game folder or the mod's textures changed: the sprites are decoded again."""
        self._sprites.clear()
        self._want_sprites()

    # -- clicking and dragging the marks ------------------------------------------------

    def press(self, point) -> bool:
        """
        The map view's grabber: a press on a treasure tile's number is that
        tile's, and one elsewhere on a place with treasure is theirs (a
        menu says which, where they are several). Anywhere else, the map's.
        """
        for members, _corners, badges in self.marks():
            for slot, centre in badges.items():
                if (point.x() - centre.x()) ** 2 + (point.y() - centre.y()) ** 2 <= BADGE_RADIUS ** 2:
                    info = self.slots()[slot]
                    self._grab = {"members": [slot], "from": (info["x"], info["y"]), "to": None,
                                  "slot": slot}
                    return True
        key = self.view.tile_at(point)
        members = self.at(key[0], key[1]) if key is not None else []
        if not members:
            return False
        self._grab = {"members": members, "from": (key[0], key[1]), "to": None,
                      "slot": self.slot if self.slot in members else members[0]}
        return True

    def move(self, point) -> None:
        key = self.view.tile_at(point)
        if self._grab is not None:
            self._grab["to"] = (key[0], key[1]) if key is not None else None
        self.view.update()

    def release(self, point, moved: bool) -> None:
        grab, self._grab = self._grab, None
        if grab is None:
            return
        if not moved:
            members = grab["members"]
            chosen = members[0] if len(members) == 1 else self._choose(members, point)
            if chosen is not None:
                self.show_slot(chosen)
            return
        if grab["to"] is not None and grab["to"] != grab["from"]:
            self.move_slot(grab["slot"], *grab["to"])
            self.show_slot(grab["slot"])
        self.view.update()

    def _choose(self, members: list, point) -> Optional[int]:
        """Which of the treasure tiles sharing a place to edit: a menu of them, at the click."""
        menu = QMenu(self)
        names = self._item_choices()
        slots = self.slots()
        for slot in members:
            info = slots[slot]
            items = [names.get(i, f"{i:03d}") for i in (info["rare"], info["common"]) if i]
            text = f"Tile {slot}" + (f"  ({', '.join(items)})" if items else "  (no items)")
            action = menu.addAction(_dot(SLOT_COLOURS[slot]), text)
            action.setData(slot)
        chosen = menu.exec(self.view.mapToGlobal(QPointF(point).toPoint()))
        return chosen.data() if chosen is not None else None
