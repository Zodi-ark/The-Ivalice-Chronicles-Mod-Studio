"""
The Event Editor's map: an event played out on its map, frame by frame,
forwards or backwards (Zodi's Task 4, 12 October; built 19 October from the
second mock-up he answered "Yes build it" to).

- **What is drawn** is the engine's timeline (`event_scripts.play`): at each
  frame the units where the script has put them (walking, turning, shown,
  hidden, faded in by a teleport, in a pose), the speech boxes open, the
  screen's color (black until the map comes in), and with Event camera
  ticked the event's own camera, framed as the game frames it
  (`event_camera`).
- **The game's framing** (measured on Zodi's screenshots of events 008,
  034, 045 and 069, 19 October, the map laid over each: tiles, walls and
  units fall on the game's): its 1,080 lines show 240 of the world's units
  at zoom 4096 (the PlayStation's 240 lines, 4.5 pixels to a unit), the
  camera's point sits 40 of them below the middle (the PlayStation draws it
  at line 160, the decompilation's `camera_init_defaults`), and everything
  is drawn 8 to 7 wider across than up (the PlayStation's 256 dots across
  a 4:3 picture), the units too. The first build showed half as much again
  around the point, at the middle and square: Zodi, 19 October, "maybe the
  camera is not matching the right framing".
- **Backwards is a jump.** Every frame is worked out from the timeline,
  not by playing again from the start, so Play backward runs the clock
  down, and Back one and Forward one jump to the start of the node before
  or after.
- **The speech box is the game's** (`event_balloon`): its pictures, laid
  out by its own layout files, as wide as its words, over the speaker with
  its tail to them; the name over its top left edge (a `<speaker="...">`
  mark's, else the scene's), the words without their marks
  (`event_words.spoken`), the face at its right blinking and talking. The
  face is `ui/ffto/common/face/texture/wldface_<sprite>_08_uitx.tex`'s
  eyes over its mouth, from the mod's own copy if it has one: WotL
  Restoration's Argath, sprite set 165, ships `wldface_165_08`. A generic
  unit's is its job's sprite's (the Bard's and the Dancer's their own), a
  monster's in its colours, `_<8 + MonsterPalette>` (`face_of`).
- **Walls hide units**, as in the game (Zodi, 19 October: "we should not be
  able to see units through walls"): the map's depth is drawn with its
  picture (`MapRenderer.render_depth`), and what of a unit's picture the
  map is nearer than is left out (`_hidden`). The walls the game leaves out
  for the camera's turn are left out (`map_scene.psx_hiding`, from the
  event camera's `psx_yaw`; Zodi, 20 October: "a part of the map wall is
  blocking the view").
- **Voices**: with Voices ticked, playing forward, each box's line's
  recording plays as it opens or its words change (`voice_wanted`; the
  page plays it, `event_voices`); pausing, a jump or unticking stops it.
  The voices come first (Zodi, 19 October): Play forward waits until every
  recording the event says is ready (`forward_ready`, the note under the
  map saying how many are), the clock waits for a voice to end before its
  words go or any others are said (`_voice_hold`), and the face talks for
  as long as the voice speaks (`mouth_now`).
- **A click on a tile** gives the page that tile, for the node picked (a
  walk's or a place's tile). A drag turns the map, as everywhere.

The units' pictures are the Abilities map's (`ability_map.SpritesJob`):
an animation n is the sprite's sequences 2n and 2n + 1, the waiting walk in
place (the march) is 3, held where a pose ends. Which sequence, and whether
mirrored, is the game's rule from the camera's yaw and the unit's facing
(`standing_view`, `moving_view`): a standing unit is one of the sprite's
five standing sequences, 1 to 5, by the sixteenth of a turn it faces from
the camera (Zodi, 20 October: Simon "is also not correctly facing
Gafgarrion"). Units march at the start of a scene with squads and stand in
one without, as the engine plays it (`event_scripts.play`'s `marching`; Zodi,
20 October: "Ramza and the squire are marching when they do not in game"). An animation from 500 is the event's
own (Dycedarg in his chair in event 045; Zodi, 19 October: "you have my
ok"): a sequence of the event animations' block its slot held when it was
set (`Pose.evtchr`, `unit_sprites.evtchr_animation`), coloured by a block's
palette after an EVTCHR palette instruction (`Pose.colours`; the unit's own
frames keep their palette here). Without its block (loaded by an event
before this one) the unit stands.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QEvent, QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from PySide6.QtWidgets import (
    QBoxLayout, QCheckBox, QComboBox, QHBoxLayout, QLabel, QLayout, QPushButton, QSizePolicy, QVBoxLayout,
    QWidget,
)

from ... import event_scripts as es
from ... import game_fonts as gf
from ... import map_classic as mc
from ... import map_enhanced as me
from ... import paths
from ... import unit_sprites as us
from .. import map_scene as ms
from ..widgets.field_rows import FieldNoteLabel
from ..widgets.map_view import MapView
from ..workers import Worker, run_in_thread
from ... import ability_preview as ap
from . import ability_map as am
from . import encounter_map as em
from . import event_balloon as eb
from . import event_text as et
from . import event_words as words_
from . import map_editor as me_page

NO_GAME = "No game files yet. Unpack your game on General Setup to see its maps here."
NO_MAP = "Pick a map under Map to play this event on."
NO_EVENT = "Pick an event in the list to play it here."
PICK_A_MAP = "Pick a map"
HINT = ("Click a tile to give it to the node picked. Drag to turn the map, Shift and drag to move it, "
        "and use the wheel to zoom.")
SPEEDS = (("Normal speed", 1.0), ("Half speed", 0.5), ("Double speed", 2.0), ("Quarter speed", 0.25))
#: The least the map takes beside the list and the node: its row of controls is wider.
MAP_LEAST = 200
MAP_BOX_LEAST = 120
#: The least the clock's words are given in the transport's row before the
#: switches go under the buttons ("Node 24 of 98, at..." still says which node).
COUNTER_LEAST = 100
#: The clock's tick, in milliseconds.
TICK_MS = 16
#: How much nearer than a unit the map must be to hide it, in the map's units
#: (a tile is 28): the tile it stands on never does.
HIDE_SLACK = 6.0
#: Faces: the sheet under the game's (or the mod's) `ui/`.
FACE_FOLDER = "ui/ffto/common/face"
#: How far before a line's words go the clock waits for its voice, in frames,
#: and what the clock says meanwhile.
VOICE_HOLD_BEFORE = 0.5
WAITING_FOR_VOICE = ", waiting for the voice to end"
#: The game's framing (see the module's notes): world units above and below
#: the screen's middle at zoom 4096, how far below the middle the camera's
#: point is (a share of the screen's height), and how much wider across.
EVENT_HALF_HEIGHT = 120.0
EVENT_POINT_BELOW = 40.0 / 240.0
EVENT_STRETCH = 8.0 / 7.0


def event_camera(renderer, camera: es.Camera, width: int, height: int):
    """
    The view's camera for the event's `camera` in a view `width` by
    `height`: the game's screen in it (the largest 16 by 9 picture that
    fits, `event_balloon.screen_rect`) framed as the game frames it, the
    walls the game leaves out from its turn left out (`psx_yaw`).
    """
    screen = eb.screen_rect(float(width), float(height))
    scale = height / max(1e-6, screen.height())
    angles = (camera.tilt, camera.yaw, camera.roll)
    position = (camera.x / es.CAMERA_SCALE, camera.height / es.CAMERA_SCALE, camera.y / es.CAMERA_SCALE)
    made = am.psx_camera(renderer, angles, position, camera.zoom, width, height,
                         half=EVENT_HALF_HEIGHT * scale)
    half = renderer.half_height(made, width / max(1, height))
    made.pan = (made.pan[0], made.pan[1] + 2 * (half / scale) * EVENT_POINT_BELOW)
    made.stretch = EVENT_STRETCH
    made.psx_yaw = camera.yaw
    return made


#: Units' pictures in changed colours kept (`EventMap._tinted`).
TINTS_KEPT = 512


def tinted_image(image: QImage, change: tuple) -> QImage:
    """
    `image` in colours changed by `change` (`(matrix, offset)`, as
    `event_scripts.colour_change` gives it): each colour matrix x colour +
    offset, clamped; black left alone, as the game leaves a colour of 0.
    """
    import numpy as np
    source = image.convertToFormat(QImage.Format_RGBA8888)
    width, height = source.width(), source.height()
    rows = np.frombuffer(source.constBits(), np.uint8, count=source.bytesPerLine() * height)
    pixels = rows.reshape(height, source.bytesPerLine())[:, :width * 4].reshape(height, width, 4)
    colour = pixels[..., :3].astype(np.float32) / 255.0
    matrix, offset = change
    changed = np.clip(colour @ np.array(matrix, np.float32).reshape(3, 3).T + np.array(offset, np.float32),
                      0.0, 1.0)
    black = colour.max(axis=2) < 0.5 / 255.0
    changed[black] = colour[black]
    out = np.empty_like(pixels)
    out[..., :3] = np.round(changed * 255.0).astype(np.uint8)
    out[..., 3] = pixels[..., 3]
    out = np.ascontiguousarray(out)
    return QImage(out.data, width, height, width * 4, QImage.Format_RGBA8888).copy()


def game_yaw(camera) -> float:
    """The game's yaw (4,096ths) for a view's camera: the event's own, else the view's turned into it."""
    psx_yaw = getattr(camera, "psx_yaw", None)
    if psx_yaw is not None:
        return float(psx_yaw)
    return (camera.yaw + 90.0) * 4096.0 / 360.0


#: How the game draws a unit from where the camera is (the decompilation's
#: `animation_update_unit_wep_eff`): its direction is the camera's yaw and
#: its facing added (4,096ths). Standing, it is one of five standing
#: sequences, 1 to 5, by the sixteenth of a turn that is in, mirrored in
#: sixteenths 9 to 14; anything else is its animation's sequence from in
#: front or behind by the quarter, behind in quarters 1 and 2, mirrored in 2
#: and 3. A mirrored unit looks right across the screen.
STAND_BY_DIRECTION = (1, 2, 2, 3, 3, 4, 4, 5, 5, 4, 4, 3, 3, 2, 2, 1)
MIRRORED_STANDING = range(9, 15)
BEHIND_BY_QUARTER, MIRRORED_BY_QUARTER = (False, True, True, False), (False, False, True, True)
#: The animation that is a unit's waiting walk in place (its march).
MARCH = 3


def unit_direction(yaw: float, facing: float) -> int:
    """A unit's direction from the camera (4,096ths): the game's `yaw` and its `facing` (sixteenths)."""
    return (int(round(yaw)) + int(round(facing * 256.0))) & 0xFFF


def standing_view(direction: int) -> tuple:
    """`(sequence, mirrored)`: the standing sequence the game draws a unit in, from its direction."""
    sixteenth = (direction & 0xFFF) // 256
    return STAND_BY_DIRECTION[sixteenth], sixteenth in MIRRORED_STANDING


def moving_view(direction: int) -> tuple:
    """`(behind, mirrored)`: the side of an animation the game draws a unit from, from its direction."""
    quarter = (direction & 0xFFF) // 1024
    return BEHIND_BY_QUARTER[quarter], MIRRORED_BY_QUARTER[quarter]


@dataclass
class SpeakerAt:
    """A unit as its box is placed by, in the view's pixels: the top of its
    picture, the point it stands on, that point in the map, and the way it
    faces (sixteenths)."""
    head: QPointF
    ground: QPointF
    world: tuple
    facing: float


#: The PlayStation's box offsets (a classic script's) in the remaster's
#: pixels: 4.5 to a line, 8 to 7 wider across, and down where the
#: remaster's numbers go up.
CLASSIC_ACROSS, CLASSIC_DOWN = 4.5 * EVENT_STRETCH, -4.5


#: A face sheet's first colours: `wldface_<sheet>_08`; a monster's others follow.
FACE_COLOURS = 8
#: The Bard's and the Dancer's faces, a man's or a woman's alike.
BARD_JOB, DANCER_JOB, BARD_FACE, DANCER_FACE = 91, 92, 130, 131


def face_of(sprite_set: int, job: int, monster_graphic: int = 0, monster_palette: int = 0):
    """
    The face a unit's box shows, as the game's dialog thread picks it (the
    decompilation's `message_dialog_thread`): a story character's own sheet;
    a generic unit's its job's, the sheet its sprite is drawn from (the
    Northern Sky Captain's Knight, 100), the Bard's and the Dancer's whoever
    wears them; a monster's its sprite's in its colours, `(sheet, 8 + its
    MonsterPalette)`. None when nothing says.
    """
    if sprite_set in (us.GENERIC_MAN, us.GENERIC_WOMAN):
        if job == BARD_JOB:
            return BARD_FACE
        if job == DANCER_JOB:
            return DANCER_FACE
        return us.sprite_number(sprite_set, job)
    if sprite_set == us.GENERIC_MONSTER:
        sheet = us.sprite_number(sprite_set, job, monster_graphic)
        return None if sheet is None else (sheet, FACE_COLOURS + max(0, monster_palette))
    return us.sprite_number(sprite_set, job)


#: A box's portrait (DisplayMessage's and ChangeDialog's number, the
#: decompilation's `portrait_selector`), as the battle's dialog thread draws
#: it (`message_dialog_thread`, `menu_draw_active_window_frames`): 0 its
#: speaker's own face; 1 to 8 a slot (that number less one) of the event
#: faces the event last read ("Portraits read", 0x50, which loads one block
#: of 8 from EVTFACE.BIN, `script_opcode_50_portrait_col`); 9 and up none.
#: Zodi, 20 October: Barbaneth in event 014 showed Alma's face, the sprite
#: his unit borrows; his boxes ask for slot 0 of block 0, his own portrait.
OWN_FACE, EVENT_FACE_SLOTS = 0, 8
#: Which face sheet each event face is drawn from in the remaster (`data/EventFaces.txt`,
#: measured by `dev/make_event_faces.py`): `index|sheet|colours`, the index block x 8 + slot.
EVENT_FACES_TABLE = "EventFaces.txt"
_event_faces: Optional[dict] = None


def event_faces(path=None) -> dict:
    """`{index: (sheet, colours)}`: the face sheet each event face is drawn from; `{}` without the table."""
    global _event_faces
    if _event_faces is not None and path is None:
        return _event_faces
    found = {}
    try:
        text = Path(path or (paths.bundled_data_dir() / EVENT_FACES_TABLE)).read_text(encoding="utf-8")
    except OSError:
        text = ""
    for line in text.splitlines():
        parts = [part.strip() for part in line.split("#")[0].split("|")]
        if len(parts) == 3 and all(part.isdigit() for part in parts):
            found[int(parts[0])] = (int(parts[1]), int(parts[2]))
    if path is None:
        _event_faces = found
    return found


def box_face(selector: int, block: Optional[int], own):
    """
    The face a box shows for its portrait `selector`: `own` (its speaker's,
    `face_of`) for 0; for 1 to 8 the event face of that slot of `block` (the
    block the event read last), as `(sheet, colours)`; None (no face) for 9
    and up. A block no Portraits read of this event loaded (an earlier
    event's, 7 boxes of the game's) isn't known here: the speaker's own.
    """
    selector = int(selector or 0)
    if selector == OWN_FACE:
        return own
    if selector > EVENT_FACE_SLOTS:
        return None
    if block is None:
        return own
    return event_faces().get(int(block) * EVENT_FACE_SLOTS + selector - 1, own)


def face_relative(face) -> tuple:
    """Where a face's sheet and its part list are, under the unpacked game: `face` a sheet's
    number (its first colours) or `(sheet, colours)`."""
    sheet, colours = (face, FACE_COLOURS) if isinstance(face, int) else face
    stem = f"wldface_{int(sheet):03d}_{int(colours):02d}_uitx"
    return f"{FACE_FOLDER}/texture/{stem}.tex", f"{FACE_FOLDER}/textureparts/{stem}.utexpt"


class TransportRow(QWidget):
    """
    The row under the map: the transport's buttons, then the switches (Loop,
    Event camera, where the clock is, the speed), as `event_editor2.png` has
    them. One row wherever it fits; where the map is narrower than that, the
    switches go under the buttons, and the row's least is the wider of the
    two, so the map's pane can still narrow to its buttons at the window's
    narrowest (trap 63) instead of the row widening the window.
    """

    def __init__(self, buttons: QWidget, switches: QWidget, parent=None):
        super().__init__(parent)
        self.buttons, self.switches = buttons, switches
        self.box = QBoxLayout(QBoxLayout.LeftToRight, self)
        self.box.setContentsMargins(0, 0, 0, 0)
        self.box.setSpacing(8)
        # The row's least is `minimumSizeHint`'s, not the one row's the layout
        # would otherwise set on it: that is what lets the switches go under.
        self.box.setSizeConstraint(QLayout.SetNoConstraint)
        self.box.addWidget(buttons, 0)
        self.box.addWidget(switches, 1)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

    def one_row_width(self) -> int:
        """The least width that holds it all in one row, the clock's words at their least."""
        return self.buttons.sizeHint().width() + self.box.spacing() + self.switches.minimumSizeHint().width()

    def is_one_row(self) -> bool:
        return self.box.direction() == QBoxLayout.LeftToRight

    def minimumSizeHint(self) -> QSize:                               # noqa: N802
        b, s = self.buttons.minimumSizeHint(), self.switches.minimumSizeHint()
        width = max(b.width(), s.width())
        if self.is_one_row():
            return QSize(width, max(b.height(), s.height()))
        return QSize(width, b.height() + self.box.spacing() + s.height())

    def sizeHint(self) -> QSize:                                      # noqa: N802
        b, s = self.buttons.sizeHint(), self.switches.sizeHint()
        if self.is_one_row():
            return QSize(b.width() + self.box.spacing() + s.width(), max(b.height(), s.height()))
        return QSize(max(b.width(), s.width()), b.height() + self.box.spacing() + s.height())

    def arrange(self, width: int) -> None:
        """One row when `width` holds it, else the switches under the buttons."""
        wanted = QBoxLayout.LeftToRight if width >= self.one_row_width() else QBoxLayout.TopToBottom
        if self.box.direction() != wanted:
            self.box.setDirection(wanted)
            self.updateGeometry()

    def resizeEvent(self, event):                                     # noqa: N802
        super().resizeEvent(event)
        self.arrange(event.size().width())


def evtchr_key(animation: int, block: Optional[int], colours: Optional[tuple]) -> Optional[tuple]:
    """What an event's own animation is asked for and kept by, or None for a unit's own animation."""
    if animation < es.EVTCHR_ANIMATIONS[0] or block is None:
        return None
    return ("evtchr", block, animation, colours)


class EventSpritesJob(Worker):
    """
    The Abilities map's `SpritesJob`, and the event's own animations too: an
    id `evtchr_key(...)` is drawn from its block (`unit_sprites.evtchr_animation`),
    the same from the front and behind, as the game shows them.
    """

    def __init__(self, sprites: us.UnitSprites, wanted: dict):
        super().__init__()
        self.sprites, self.wanted = sprites, {key: set(ids) for key, ids in wanted.items()}

    def run(self):
        made = {}
        for (sprite, palette), ids in sorted(self.wanted.items()):
            own = {i for i in ids if isinstance(i, int)}
            moving, flying = ap.sprite_animations(self.sprites, sprite, palette, own)
            animations = {}
            for animation_id, found in moving.items():
                animations[animation_id] = {
                    side: [(am._qimage(p), p.stand_x, p.stand_y, step) for p, step in pictures]
                    for side, pictures in (("front", found.front), ("back", found.back))}
            for key in ids - own:
                _tag, block, animation, colours = key
                drawn = self.sprites.evtchr_animation(sprite, palette, block, animation, colours)
                if not drawn:
                    continue
                steps = ap.animation_steps([step for _picture, step in drawn])
                pictures = [picture for picture, step in drawn if step[0] != "op"]
                frames = [(am._qimage(picture), picture.stand_x, picture.stand_y, step)
                          for picture, step in zip(pictures, steps) if picture is not None]
                if frames:
                    animations[key] = {"front": frames, "back": frames}
            made[(sprite, palette)] = (animations, flying, ids)
        return made, self.sprites.problem


class EventMap(QWidget):
    """The map column of the Event Editor (see the module's notes)."""

    #: A tile was clicked: x, y, level.
    tile_clicked = Signal(int, int, int)
    #: The clock moved (the frame shown).
    frame_changed = Signal(float)
    #: A map was read and drawn, or none could be: the page plays the event on it again.
    map_ready = Signal()
    #: Another map or battle was picked in the boxes.
    map_chosen = Signal(int)
    battle_chosen = Signal(int)
    #: Playing forward with Voices ticked, a box opened: its `BoxShown`.
    voice_wanted = Signal(object)
    #: Paused, jumped or Voices unticked: what is playing stops.
    voices_stopped = Signal()
    #: Paused, jumped or Music unticked: the music stops.
    music_stopped = Signal()

    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(6)

        head = QHBoxLayout()
        head.setSpacing(8)
        self.title = QLabel("")
        self.title.setStyleSheet("font-weight: 600; font-size: 12pt;")
        self.title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        head.addWidget(self.title, 1)
        self.map_label = QLabel("Map")
        head.addWidget(self.map_label)
        self.map_box = QComboBox()
        self.map_box.setMinimumWidth(MAP_BOX_LEAST)
        self.map_box.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.map_box.setToolTip("The map the event is played on. The game's own map for it comes first.")
        self.map_box.activated.connect(self._map_picked)
        head.addWidget(self.map_box, 1)
        self.units_label = QLabel("Units from")
        head.addWidget(self.units_label)
        self.battle_box = QComboBox()
        self.battle_box.setMinimumWidth(MAP_BOX_LEAST)
        self.battle_box.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.battle_box.setToolTip("The battle whose units the event moves (its ENTD battle).")
        self.battle_box.activated.connect(self._battle_picked)
        head.addWidget(self.battle_box, 1)
        # The speakers' voices as their boxes open, off at first as the
        # Abilities map's Sound is (Zodi, 18 October).
        self.voices = QCheckBox("Voices")
        self.voices.setToolTip("Play the speakers' voices as their boxes open, playing forward")
        self.voices.toggled.connect(lambda on: None if on else self.voices_stopped.emit())
        head.addWidget(self.voices)
        # The event's music, playing forward (`event_music`; Zodi, 20 October).
        self.music = QCheckBox("Music")
        self.music.setToolTip("Play the event's music, playing forward")
        self.music.toggled.connect(lambda on: None if on else self.music_stopped.emit())
        head.addWidget(self.music)
        column.addLayout(head)

        self.view = MapView()
        self.view.show_info = False
        # Units behind the map's walls are hidden as in the game (`_hidden`).
        self.view.want_depth = True
        self.view.overlay = self.paint
        self.view.tile_clicked.connect(self._tile_clicked)
        self.view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.view.setMinimumSize(MAP_LEAST, 160)
        # The game's framing hangs on the screen's shape in the view: the
        # event's camera is worked out again when the view changes size.
        self.view.installEventFilter(self)
        column.addWidget(self.view, 1)

        # The transport, as the mock-up has it: the five buttons, then Loop,
        # Event camera, where the clock is and the speed, in one row under the
        # map (Zodi, 19 October: "the loop toggle and event camera toggle and
        # the speed dropdown menu should be to the right of the Forward one
        # button"). Where the map is too narrow for one row (the window at
        # its narrowest), the switches go under the buttons rather than the
        # row squeezing the map: `TransportRow`.
        buttons = QWidget()
        button_row = QHBoxLayout(buttons)
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(6)
        self.back_one = QPushButton("Back one")
        self.play_back = QPushButton("Play backward")
        self.pause_button = QPushButton("Pause")
        self.play_forward = QPushButton("Play forward")
        self.forward_one = QPushButton("Forward one")
        for button in (self.back_one, self.play_back, self.pause_button, self.play_forward, self.forward_one):
            button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            button_row.addWidget(button)
        # Packed to the left when the row has room to spare (the switches under them).
        button_row.addStretch(1)
        self.back_one.clicked.connect(lambda: self.step_node(-1))
        self.forward_one.clicked.connect(lambda: self.step_node(1))
        self.play_back.clicked.connect(lambda: self.play(-1))
        self.play_forward.clicked.connect(lambda: self.play(1))
        self.pause_button.clicked.connect(self.pause)
        switches = QWidget()
        switch_row = QHBoxLayout(switches)
        switch_row.setContentsMargins(0, 0, 0, 0)
        switch_row.setSpacing(8)
        self.loop = QCheckBox("Loop")
        switch_row.addWidget(self.loop)
        self.follow = QCheckBox("Event camera")
        self.follow.setChecked(True)
        self.follow.setToolTip("Look through the event's own camera as it plays. Untick it to turn the map "
                               "yourself.")
        self.follow.toggled.connect(lambda _on: self._show_frame())
        switch_row.addWidget(self.follow)
        # Where the clock is: shortened with an ellipsis when the row is tight.
        self.counter = FieldNoteLabel("")
        self.counter.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.counter.setMinimumWidth(COUNTER_LEAST)
        switch_row.addWidget(self.counter, 1)
        self.speed_box = QComboBox()
        for text, value in SPEEDS:
            self.speed_box.addItem(text, value)
        self.speed_box.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        switch_row.addWidget(self.speed_box)
        self.transport = TransportRow(buttons, switches)
        column.addWidget(self.transport)
        self.note = QLabel("")
        self.note.setProperty("role", "muted")
        self.note.setWordWrap(True)
        self.note.setVisible(False)
        column.addWidget(self.note)
        # What a click and a drag on the map do: on the map itself, not a line
        # under it (the mock-up has none there).
        self.view.setToolTip(HINT)
        self.view.set_message(NO_EVENT)

        #: The event shown: its timeline, units, names and words.
        self.timeline: Optional[es.Timeline] = None
        self.units: dict = {}
        self.sprites_of: dict = {}           # {unit id: (sprite, palette) or None}
        self.names: dict = {}
        self.words: Callable = lambda line: None
        self.speaker: Callable = lambda line: None
        self.face_sprite: Callable = lambda unit_id: None
        #: When the event reads a block of event faces ("Portraits read", 0x50):
        #: `[(frame, block)]` in order (the page sets it with the timeline).
        self.portrait_reads: list = []
        self.frame = 0.0
        #: The node shown: the one jumped to, or while playing the last to have
        #: started. Several nodes can start on one frame (an instruction takes
        #: no time), so a jump keeps the node it was to.
        self.node: Optional[int] = None
        self.direction = 0                   # 1 forward, -1 backward, 0 paused
        self.map_number: Optional[int] = None
        self._shown_map = None
        self._wanted_map = None
        self._token = 0
        self._reading = False
        self._reading_for = None
        self._sprites = None
        self._sprites_key = None
        self._pictures: dict = {}
        self._pending: set = set()
        self._sprite_job = None
        self.sprite_problem = ""
        #: Faces (`{sprite: event_balloon.FacePieces or None}`) and the balloon's
        #: sheets (`{sheet: {part: QImage} or None}`), read on a worker; each
        #: read again when its files change (`_read_from`: what it was read
        #: from), as a face replaced on the Textures page does.
        self._faces: dict = {}
        #: The game's fonts read, by name (`game_text.GameText`, None: not to be had).
        self._fonts: dict = {}
        #: The captions' words, by their `Caption` key (`event_scripts.caption_words`; the page sets them).
        self.caption_words: dict = {}
        self._sheets: dict = {}
        self._read_from: dict = {}
        self._asked: dict = {}
        self._pieces_pending: set = set()
        self._face_job = None
        #: What the last paint drew: `{unit id: sprite rectangle}` and the boxes.
        self.drawn: dict = {}
        self.heads: dict = {}
        self.speakers: dict = {}
        self.boxes_drawn: list = []
        self.balloons_drawn: list = []
        #: The caption drawn, `(its words, where)`, or None.
        self.caption_drawn = None
        #: Units' pictures in changed colours (`_tinted`), by picture and change.
        self._tints: dict = {}
        self._box_windows: dict = {}
        self._box_facings: dict = {}
        #: The scripts' look ("enhanced" or "classic"): a classic box's
        #: offsets are the PlayStation's pixels (`box_place`). The page sets it.
        self.mode = "enhanced"
        self.clock = time.monotonic
        self._last_tick = None
        #: Playing forward from a frame a box opens on: its line is said too
        #: (Play from here on a Speak node), at the first tick.
        self._said_from: Optional[float] = None
        #: The voices come first (`event_voices`; the page sets both):
        #: `forward_ready()` is `(whether Play forward may start, why not)`,
        #: `voice_now()` the line whose voice was asked for last, `(line, when
        #: it began on this clock or None while it is opened, whether it is
        #: still to end)`, or None. Playing forward, the clock waits at the end
        #: of a line's words until its voice has ended (`_voice_hold`), and the
        #: face talks for as long as the voice does.
        self.forward_ready: Callable[[], tuple] = lambda: (True, "")
        self.voice_now: Callable[[], Optional[tuple]] = lambda: None
        self.waiting_for_voice = False
        self._timer = QTimer(self)
        self._timer.setInterval(TICK_MS)
        self._timer.timeout.connect(self._tick)
        self._update_buttons()

    # -- the game's files -----------------------------------------------------------

    def game_dir(self) -> Optional[Path]:
        root = getattr(self.state, "nxd_unpack_dir", None)
        return Path(root) if root and Path(root).is_dir() else None

    def unit_sprites(self) -> Optional[us.UnitSprites]:
        game = self.game_dir()
        if game is None:
            return None
        key = (str(game), em._stamp(game / us.G2D_FILE), em._stamp(game / us.BATTLE_BIN))
        if key != self._sprites_key:
            self._sprites, self._sprites_key = us.UnitSprites(game), key
            self._pictures.clear()
            self.sprite_problem = ""
        return self._sprites

    # -- the boxes over the map -----------------------------------------------------

    def fill_maps(self, own: list, chosen: Optional[int]) -> None:
        """The Map box: the event's own maps first, then every other; `chosen` picked."""
        names = me_page.map_names(self.state)
        self.map_box.blockSignals(True)
        self.map_box.clear()
        if chosen is None and not own:
            self.map_box.addItem(PICK_A_MAP, None)
        for number in own:
            self.map_box.addItem(me_page.map_label(number, names.get(number, "")), number)
        others = [n for n in sorted(names) if n not in own]
        if others:
            if own:
                self.map_box.insertSeparator(self.map_box.count())
            for number in others:
                self.map_box.addItem(me_page.map_label(number, names.get(number, "")), number)
        index = self.map_box.findData(chosen) if chosen is not None else 0
        self.map_box.setCurrentIndex(max(0, index))
        self.map_box.blockSignals(False)

    def fill_battles(self, battles: list, chosen: Optional[int]) -> None:
        """The Units from box: `[(battle, words)]`, `chosen` picked."""
        self.battle_box.blockSignals(True)
        self.battle_box.clear()
        for battle, words in battles:
            self.battle_box.addItem(words, battle)
        index = self.battle_box.findData(chosen) if chosen is not None else -1
        self.battle_box.setCurrentIndex(max(0, index))
        self.battle_box.blockSignals(False)

    def _map_picked(self, index: int) -> None:
        number = self.map_box.itemData(index)
        if number is not None:
            self.map_chosen.emit(int(number))

    def _battle_picked(self, index: int) -> None:
        battle = self.battle_box.itemData(index)
        if battle is not None:
            self.battle_chosen.emit(int(battle))

    # -- the map ----------------------------------------------------------------------

    def show_map(self, number: Optional[int]) -> None:
        """Reads map `number` if it isn't the one drawn (None: no map), then says `map_ready`."""
        self.map_number = number
        game = self.game_dir()
        if game is None:
            self._no_map(NO_GAME)
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
        if (number, look) == self._shown_map and self.view.scene is not None:
            self.map_ready.emit()
            return
        self._token += 1
        self._wanted_map = number
        self.view.set_message(f"Reading map {number:03d}...")
        if not self._reading:
            self._start_reading()

    def _look_of(self, number: int) -> tuple:
        game = self.game_dir()
        enhanced = game is not None and me.mesh_path(game, number).is_file()
        mesh, pictures = me_page.mod_look(self.state, number) if enhanced else (None, {})
        return (ms.ENHANCED if enhanced else ms.CLASSIC, mesh, tuple(sorted(pictures.items())))

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
            self._start_reading()
            return
        if scene is None:
            self._no_map(f"Map {number:03d} could not be drawn: {error}")
            return
        edits = (getattr(self.state, "map_edits", {}) or {}).get(scene.grid_key, {}) if scene.grid_key else {}
        tiles = ([me_page.as_edited(t, edits.get((t.x, t.z, t.level), {})) for t in scene.terrain.tiles]
                 if scene.terrain is not None else [])
        self._shown_map = (number, look)
        self.view.set_message(" ".join(scene.notes))
        self.view.set_scene(scene, tiles, ())
        self.map_ready.emit()
        self._show_frame()

    def _scene_failed(self, message: str) -> None:
        self._reading = False
        self._no_map(f"This map could not be drawn: {message}")

    def _no_map(self, message: str) -> None:
        self._shown_map = None
        self._wanted_map = None
        self.view.set_scene(None)
        self.view.set_message(message)
        self.map_ready.emit()

    def map_tiles(self) -> Optional[set]:
        """`{(x, y)}`: the tiles of the map drawn, None with no map."""
        if self.view.scene is None:
            return None
        return {(t.x, t.z) for t in self.view.tiles if ms.shows(t)}

    def ground_view(self, x: float, y: float, level: int) -> Optional[tuple]:
        """The middle of tile x, y (fractional: between tiles), in the view's world units."""
        def one(tx, ty):
            tile = self.view.tile((tx, ty, level))
            if level and (tile is None or not ms.shows(tile) or tile.no_cursor):
                tile = self.view.tile((tx, ty, 0))
            if tile is None or not ms.shows(tile):
                return None
            corners = ms.tile_corners(tile, 0.0)
            return tuple(sum(c[i] for c in corners) / 4 for i in range(3))
        if self.view.scene is None:
            return None
        x0, y0 = math.floor(x), math.floor(y)
        here = one(int(x0), int(y0))
        if here is None:
            return None
        fx, fy = x - x0, y - y0
        if fx < 1e-6 and fy < 1e-6:
            return here
        there = one(int(x0) + (1 if fx >= 1e-6 else 0), int(y0) + (1 if fy >= 1e-6 else 0))
        if there is None:
            there = (here[0] - 28.0 * fx, here[1], here[2] + 28.0 * fy)
        part = max(fx, fy)
        return tuple(here[i] + (there[i] - here[i]) * part for i in range(3))

    def ground_psx(self, x: float, y: float, level: int) -> tuple:
        """A tile's middle in the game's world units (x, y down, z), as the timeline's Focus wants it."""
        found = self.ground_view(x, y, level)
        if found is None:
            return es.default_ground(x, y, level)
        return (-found[0], -found[1], found[2])

    # -- the event --------------------------------------------------------------------

    def set_event(self, timeline: Optional[es.Timeline], units: dict, sprites_of: dict, names: dict,
                  words: Callable, speaker: Callable, face_sprite: Callable, title: str = "") -> None:
        """A (new) timeline to play: its units' sprites, their names, the scene's words and faces."""
        self.timeline = timeline
        self.units, self.sprites_of, self.names = units, sprites_of, names
        self.words, self.speaker, self.face_sprite = words, speaker, face_sprite
        #: Where each box of the kind placed by facing goes (`box_window`), and
        #: the way each box's speaker faced as it opened (`box_facing`), worked out once.
        self._box_windows: dict = {}
        self._box_facings: dict = {}
        self.title.setText(title)
        if timeline is not None:
            self.frame = min(self.frame, float(timeline.frames))
            if self.node is not None and not 0 <= self.node < len(timeline.node_starts):
                self.node = None
        else:
            self.frame, self.direction, self.node = 0.0, 0, None
            self._timer.stop()
        self._want_sprites()
        self._want_faces()
        self._update_buttons()
        self._show_frame()

    def set_frame(self, frame: float, node: Optional[int] = None) -> None:
        """Shows `frame` (a jump: worked out from the timeline, not played to), at node `node` if given."""
        if self.timeline is None:
            return
        self.voices_stopped.emit()
        self.music_stopped.emit()
        self.frame = max(0.0, min(float(frame), float(self.timeline.frames)))
        self.node = node if node is not None else self.timeline.node_at(self.frame)
        self._show_frame()

    def play(self, direction: int) -> None:
        if self.timeline is None or not self.timeline.frames:
            return
        if direction > 0 and not self.forward_ready()[0]:
            # Voices ticked and not all ready yet: the note under the map says so.
            self._update_buttons()
            return
        if direction > 0 and self.frame >= self.timeline.frames:
            self.frame = 0.0
        if direction < 0 and self.frame <= 0:
            self.frame = float(self.timeline.frames)
        self.direction = direction
        self._said_from = self.frame - 0.5 if direction > 0 else None
        self._last_tick = self.clock()
        self._timer.start()
        self._update_buttons()

    def pause(self) -> None:
        if self.direction:
            self.voices_stopped.emit()
            self.music_stopped.emit()
        self.direction = 0
        self.waiting_for_voice = False
        self._timer.stop()
        self._update_buttons()

    def step_node(self, step: int) -> None:
        """Back one or Forward one: the start of the node before or after the one playing."""
        if self.timeline is None or not self.timeline.node_starts:
            return
        self.pause()
        starts = self.timeline.node_starts
        here = self.node if self.node is not None else self.timeline.node_at(self.frame)
        here = max(0, min(len(starts) - 1, here))
        if step < 0 and self.frame > starts[here] + 0.5:
            target = here
        else:
            target = max(0, min(len(starts) - 1, here + step))
        self.set_frame(starts[target], target)

    def speed(self) -> float:
        return float(self.speed_box.currentData() or 1.0)

    def _tick(self) -> None:
        now = self.clock()
        last, self._last_tick = self._last_tick, now
        if self.timeline is None or not self.direction:
            self._timer.stop()
            return
        elapsed = max(0.0, now - (last if last is not None else now))
        frame = self.frame + self.direction * elapsed * es.FRAMES_A_SECOND * self.speed()
        # A voice still speaking holds the clock where its words would go.
        hold = self._voice_hold()
        self.waiting_for_voice = hold is not None and frame >= hold
        if self.waiting_for_voice:
            frame = max(self.frame, hold)
        end = float(self.timeline.frames)
        if frame > end or frame < 0:
            if self.loop.isChecked():
                frame = frame % end if end else 0.0
            else:
                frame = max(0.0, min(end, frame))
                self.frame = frame
                self.node = self.timeline.node_at(frame)
                self.pause()
                self._show_frame()
                return
        before = self.frame
        self.frame = frame
        self.node = self.timeline.node_at(frame)
        after = self._said_from if self._said_from is not None else before
        self._said_from = None
        if self.direction > 0 and self.voices.isChecked() and frame > before:
            said = self.lines_said(after, frame)
            if said:
                self.voice_wanted.emit(said[-1])
        self._show_frame()

    def lines_said(self, after: float, until: float) -> list:
        """The lines a box began to say after frame `after` and by `until`, in
        order: a box opening, or new words in one open (as `BoxShown`s, each
        with the line it began to say)."""
        found = []
        for start, _end, box, changes in (self.timeline.boxes if self.timeline is not None else []):
            if after < start <= until:
                found.append((start, box))
            for when, line, _portrait in changes:
                if after < when <= until:
                    found.append((when, replace(box, line=line)))
        found.sort(key=lambda said: said[0])
        return [box for _when, box in found]

    def mouth_now(self, box: es.BoxShown, said) -> int:
        """
        The mouth's part a box's face shows now (`event_balloon.mouth_part`):
        talking while the words shown (`said`, `event_words.spoken`) are
        read, from the box's opening or from when new words were put in it;
        while their voice speaks, for as long as it does instead, the clock
        held or not (Zodi, 19 October: "the talking animation on the portrait
        should continue until that voice line ends").
        """
        talking = eb.talking_frames(len(said.words), said.lips_until)
        talked = self.frame - self.said_since(box)
        voice = self.voice_now() if self.voices.isChecked() else None
        if voice is not None and voice[0] == box.line and voice[1] is not None:
            talked = (self.clock() - voice[1]) * es.FRAMES_A_SECOND
            talking = float("inf") if voice[2] else 0.0
        return eb.mouth_part(talked, talking)

    def _voice_hold(self) -> Optional[float]:
        """
        Playing forward with Voices ticked, while the voice asked for last is
        still to end (playing, or being opened): the frame just before its
        line's words go (its box's words change, or the box closes) or any
        other words are said (another box opens, with a voice of its own),
        where the clock waits for it (Zodi, 19 October: "the voice line must
        finish before the event editor moves on to the next node"). None when
        there is nothing to wait for.
        """
        if self.direction <= 0 or not self.voices.isChecked() or self.timeline is None:
            return None
        now = self.voice_now()
        if now is None or not now[2]:
            return None
        line = now[0]
        frame = self.frame
        for start, end, box, changes in self.timeline.boxes:
            if not start <= frame < end:
                continue
            shown = box.line
            for when, new_line, _portrait in changes:
                if when <= frame:
                    shown = new_line
            if shown != line:
                continue
            goes = min([when for when, _l, _p in changes if when > frame] + [end])
            said_next = [s for s, _e, _b, _c in self.timeline.boxes if s > frame]
            said_next += [when for _s, _e, _b, other in self.timeline.boxes for when, _l, _p in other if when > frame]
            goes = min([goes] + said_next)
            return max(float(start), goes - VOICE_HOLD_BEFORE)
        return None

    def said_since(self, box: es.BoxShown) -> float:
        """When the words `box` shows began: its opening, or the last new words put in it by now."""
        began = float(box.opened)
        for start, _end, shown, changes in (self.timeline.boxes if self.timeline is not None else []):
            if shown.instruction == box.instruction and int(start) == box.opened:
                for when, line, _portrait in changes:
                    if when <= self.frame and line == box.line:
                        began = float(when)
                break
        return began

    def _update_buttons(self) -> None:
        has = self.timeline is not None and bool(self.timeline.frames)
        for button in (self.back_one, self.play_back, self.forward_one, self.play_forward):
            button.setEnabled(has)
        self.pause_button.setEnabled(has and bool(self.direction))
        # With Voices ticked, Play forward waits for all the event's voices.
        ready, why = self.forward_ready() if has else (True, "")
        self.play_forward.setEnabled(has and ready)
        self.note.setText(why if has else "")
        self.note.setVisible(bool(has and why))

    def _show_frame(self) -> None:
        timeline = self.timeline
        if timeline is None:
            self.counter.setText("")
            self.view.set_tint(None)
            self.view.update()
            return
        # The map's colours as the event has changed them (ColorField).
        self.view.set_tint(timeline.at(self.frame).field)
        node = self.node if self.node is not None else timeline.node_at(self.frame)
        waiting = WAITING_FOR_VOICE if self.waiting_for_voice and self.direction > 0 else ""
        self.counter.setText(f"Node {node + 1} of {len(timeline.node_starts)}, at "
                             f"{self.frame / es.FRAMES_A_SECOND:.1f} seconds{waiting}")
        self._follow_camera()
        self.view.update()
        self.frame_changed.emit(self.frame)

    def _follow_camera(self) -> None:
        """With Event camera ticked, the view looks through the event's camera at the frame shown."""
        if getattr(self, "timeline", None) is None or not self.follow.isChecked() or self.view.scene is None:
            return
        camera = self.timeline.at(self.frame).camera
        if camera is not None:
            width, height = max(1, self.view.width()), max(1, self.view.height())
            self.view.set_camera(event_camera(self.view.renderer, camera, width, height))

    def eventFilter(self, watched, event):                          # noqa: N802
        if watched is self.view and event.type() == QEvent.Resize:
            self._follow_camera()
        return super().eventFilter(watched, event)

    # -- sprites and faces --------------------------------------------------------------

    def _animations_wanted(self) -> dict:
        """`{(sprite, palette): {animation ids}}` the timeline's units play."""
        wanted = {}
        if self.timeline is None:
            return wanted
        for unit_id, track in self.timeline.tracks.items():
            key = self.sprites_of.get(unit_id)
            if key is None:
                continue
            # Standing (sequences 1 to 5) and marching, which every unit may do.
            ids = wanted.setdefault(key, {0, 1, 2, MARCH})
            if track.start.animation is not None:
                ids.add(track.start.animation)
            colours = track.start.colours
            # The event's own animation playing, `(animation, block)`: one
            # coloured anew while it plays (EVTCHR palette after it, as 37 of
            # the game's 136 are) is wanted in its new colours too.
            playing = None
            for _when, kind, data in track.changes:
                if kind == "set" and "colours" in data:
                    colours = data["colours"]
                    if playing is not None:
                        ids.add(evtchr_key(playing[0], playing[1], colours))
                if kind in ("set", "walk") and data.get("animation") is not None:
                    animation = int(data["animation"])
                    playing = None
                    if animation < es.EVTCHR_ANIMATIONS[0]:
                        ids.add(animation)
                    elif evtchr_key(animation, data.get("evtchr"), colours) is not None:
                        ids.add(evtchr_key(animation, data.get("evtchr"), colours))
                        playing = (animation, data.get("evtchr"))
        return wanted

    def _want_sprites(self) -> None:
        sprites = self.unit_sprites()
        if sprites is None or self._sprite_job is not None:
            return
        wanted = {}
        for key, ids in self._animations_wanted().items():
            have = self._pictures.get(key)
            missing = set(ids) - (set(have[2]) if have else set())
            if missing and key not in self._pending:
                wanted[key] = set(ids) | (set(have[2]) if have else set())
        if not wanted:
            return
        self._pending |= set(wanted)
        self._sprite_job = EventSpritesJob(sprites, wanted)
        run_in_thread(self._sprite_job, on_finished=self._sprites_ready, on_failed=self._sprites_failed)

    def _sprites_ready(self, result) -> None:
        made, problem = result
        self._sprite_job = None
        for key, found in made.items():
            self._pending.discard(key)
            self._pictures[key] = found
        self.sprite_problem = problem if any(not v[0] for v in made.values()) else ""
        self.view.update()
        self._want_sprites()

    def _sprites_failed(self, message: str) -> None:
        self._sprite_job = None
        for key in list(self._pending):
            self._pictures[key] = ({}, False, set())
        self._pending.clear()
        self.sprite_problem = message

    def _source(self, picture: str, parts: str) -> Optional[tuple]:
        """Where a picture and its part list are read from: the mod's copy, else the unpacked game's."""
        found_picture = found_parts = None
        for store in (getattr(self.state, "texture_edits", {}) or {},
                      getattr(self.state, "other_file_replacements", {}) or {}):
            entry = store.get(picture)
            if entry is not None:
                found_picture = Path(entry["source_path"] if isinstance(entry, dict) else entry)
            entry = store.get(parts)
            if entry is not None:
                found_parts = Path(entry["source_path"] if isinstance(entry, dict) else entry)
        game = self.game_dir()
        if found_picture is None and game is not None and (game / picture).is_file():
            found_picture = game / picture
        if found_parts is None and game is not None and (game / parts).is_file():
            found_parts = game / parts
        return (str(found_picture), str(found_parts) if found_parts else None) if found_picture else None

    def face_source(self, face) -> Optional[tuple]:
        """Where a face (`face_of`) is read from: the mod's copy, else the unpacked game's; a
        monster's in colours no sheet has, its first colours'."""
        found = self._source(*face_relative(face))
        if found is None and not isinstance(face, int):
            found = self._source(*face_relative(face[0]))
        return found

    def font_source(self, name: str) -> Optional[tuple]:
        """Where a font is read from, `(its atlas, its file)`: the mod's copies, else the unpacked
        game's, whatever the case of their names."""
        game = self.game_dir()
        others = getattr(self.state, "other_file_replacements", {}) or {}
        wanted = gf.atlas_relative(name).lower()
        atlas = next((Path(entry["source_path"] if isinstance(entry, dict) else entry)
                      for rel, entry in (getattr(self.state, "texture_edits", {}) or {}).items()
                      if str(rel).replace("\\", "/").lower() == wanted), None)
        if atlas is None:
            atlas = gf.find_file(game, gf.atlas_relative(name), others)
        font = gf.find_file(game, gf.font_relative(name), others)
        return (str(atlas), str(font)) if atlas is not None and font is not None else None

    @property
    def balloon_text(self):
        """The balloons' font made ready (`game_text.GameText`), or None: a serif stands in."""
        return self._fonts.get(eb.BALLOON_FONT)

    @property
    def screen_text(self):
        """The font of the words without a balloon and the captions (`event_text.TEXT_FONT`), or None."""
        return self._fonts.get(et.TEXT_FONT)

    def _wants_screen_text(self) -> bool:
        """Whether the event shows words without a balloon or a caption."""
        if self.timeline is None:
            return False
        return bool(self.timeline.captions) or any(et.is_text_only(box.box)
                                                   for _o, _c, box, _ch in self.timeline.boxes)

    def _keep_pieces(self, key, pieces) -> None:
        if isinstance(key, tuple) and key[0] == "font":
            self._fonts[key[1]] = pieces
        elif isinstance(key, tuple):
            self._faces[key[1]] = pieces
        else:
            self._sheets[key] = pieces

    def _want_faces(self) -> None:
        """
        Reads the balloon's sheets and the faces of the event's speakers:
        those not read yet, and those whose files changed since (a face
        replaced on the Textures page, the game unpacked again).
        """
        if self._face_job is not None:
            return
        keys = [(sheet, eb.balloon_relative(sheet)) for sheet in eb.BALLOON_SHEETS]
        keys.append((("font", eb.BALLOON_FONT), None))
        if self._wants_screen_text():
            keys.append((("font", et.TEXT_FONT), None))
        blocks = {block for _when, block in self.portrait_reads}
        for _o, _c, box, _ch in (self.timeline.boxes if self.timeline is not None else []):
            # Every face the box can show: its speaker's, and each event face its
            # portraits name in any block the event reads.
            own = self.face_sprite(box.unit)
            faces = set()
            for _when, selector in self.box_selectors(box):
                for block in blocks or {None}:
                    faces.add(box_face(selector, block, own))
            for face in sorted((f for f in faces if f is not None), key=str):
                keys.append((("face", face), face))
        wanted = {}
        for key, relative in keys:
            if key in wanted or key in self._pieces_pending:
                continue
            if relative is None:
                source = self.font_source(key[1])
            elif key[0] == "face":
                source = self.face_source(relative)
            else:
                source = self._source(*relative)
            stamp = None if source is None else tuple(em._stamp(Path(p)) if p else None for p in source)
            if key in self._read_from and self._read_from[key] == stamp:
                continue
            if source is None:
                self._keep_pieces(key, None)
                self._read_from[key] = None
                continue
            wanted[key] = source
            self._asked[key] = stamp
        if not wanted:
            return
        self._pieces_pending |= set(wanted)
        self._face_job = eb.PiecesJob(wanted, getattr(self.state, "ff16tools_cli_path", None))
        run_in_thread(self._face_job, on_finished=self._faces_ready, on_failed=self._faces_failed)

    def _faces_ready(self, result) -> None:
        made, _problem = result
        self._face_job = None
        for key, pieces in made.items():
            self._keep_pieces(key, pieces)
            self._read_from[key] = self._asked.pop(key, None)
        self._pieces_pending -= set(made)
        self.view.update()
        self._want_faces()

    def _faces_failed(self, _message: str) -> None:
        self._face_job = None
        for key in self._pieces_pending:
            self._keep_pieces(key, None)
            self._read_from[key] = self._asked.pop(key, None)
        self._pieces_pending.clear()

    # -- painting -----------------------------------------------------------------------

    def _project(self, point) -> QPointF:
        view = self.view
        return QPointF(*view.renderer.project(point, view.camera, view.width(), view.height()))

    def faces_right(self, facing: float, standing: bool = True) -> bool:
        """Whether a unit facing `facing` (sixteenths) looks right across the view, as the game
        draws it (mirrored), `standing` or not."""
        direction = unit_direction(game_yaw(self.view.camera), facing)
        return (standing_view if standing else moving_view)(direction)[1]

    def pixels_per_unit(self) -> float:
        view = self.view
        return view.height() / max(1e-6, 2 * view.renderer.half_height(
            view.camera, view.width() / max(1, view.height())))

    def paint(self, p: QPainter) -> None:
        timeline = self.timeline
        self.drawn, self.boxes_drawn, self.balloons_drawn = {}, [], []
        #: Where each unit's box points, by unit (`_paint_unit`): kept for the suites.
        self.heads: dict = {}
        #: Each unit placed, drawn or hidden, as its box is placed by (`SpeakerAt`).
        self.speakers: dict = {}
        if timeline is None or self.view.scene is None:
            return
        p.setRenderHint(QPainter.Antialiasing)
        shown = timeline.at(self.frame)
        ppu = self.pixels_per_unit()
        across = ppu * self.view.camera.stretch
        heads = self.heads
        order = []
        for pose in shown.units:
            world = self.ground_view(pose.x, pose.y, pose.level)
            if world is None:
                continue
            if any(pose.lift):
                world = (world[0] - pose.lift[0], world[1] - pose.lift[1], world[2] + pose.lift[2])
            ground = self._project(world)
            # A hidden unit's box still points at where it stands, as the
            # game's does (it finds the unit's place, seen or not).
            self.speakers[pose.unit_id] = SpeakerAt(QPointF(ground.x(), ground.y() - 40 * ppu), ground, world,
                                                    pose.facing)
            if pose.shown and pose.alpha > 0.01:
                order.append((ground.y(), pose, world, ground))
        order.sort(key=lambda o: o[0])
        for _y, pose, world, ground in order:
            painted = self._paint_unit(p, pose, world, ground, ppu)
            if painted is None:
                p.setPen(QPen(QColor(235, 235, 235, 220), 1.6))
                p.setBrush(QColor(255, 255, 255, 50))
                p.drawEllipse(ground, em.RING_W * across, em.RING_H * ppu)
                rect = QRectF(ground.x() - em.RING_W * across, ground.y() - 40 * ppu, 2 * em.RING_W * across,
                              40 * ppu)
                head = QPointF(ground.x(), rect.top())
            else:
                rect, head = painted
            self.drawn[pose.unit_id] = rect
            heads[pose.unit_id] = head
            self.speakers[pose.unit_id] = replace(self.speakers[pose.unit_id], head=head)
        for box in shown.boxes:
            if not et.is_text_only(box.box):
                self._paint_box(p, box, self.speakers.get(box.unit))
        red, green, blue, alpha = shown.screen
        if alpha > 0.001:
            p.fillRect(QRectF(0, 0, self.view.width(), self.view.height()),
                       QColor.fromRgbF(red, green, blue, min(1.0, alpha)))
        # Words alone and captions are over the screen's colour, as the game's are.
        for box in shown.boxes:
            if et.is_text_only(box.box):
                self._paint_words(p, box)
        self.caption_drawn = None
        if shown.caption is not None:
            words = self.caption_words.get(shown.caption.key) or f"Caption {shown.caption.key}"
            self.caption_drawn = (words, et.draw_caption(p, self.screen(), self.screen_text, words,
                                                         shown.caption.since, shown.caption.left))

    def _frames_for(self, pose: es.Pose) -> tuple:
        """
        `(pictures, loops, mirrored)`: the pictures `pose` shows from where the
        camera is, whether they loop, and whether they are drawn mirrored, by
        the game's rule (`standing_view`, `moving_view`). A unit marches
        (`MARCH`) walking and when no animation is set, as the scene's units
        begin in a scene with squads (`event_scripts.play`'s `marching`).
        """
        key = self.sprites_of.get(pose.unit_id)
        found = self._pictures.get(key) if key is not None else None
        if not found:
            return None, False, False
        animations = found[0]
        direction = unit_direction(game_yaw(self.view.camera), pose.facing)
        wanted = MARCH if pose.walking or pose.animation is None else pose.animation
        if wanted >= es.EVTCHR_ANIMATIONS[0]:
            # The event's own: held at its end, as its sequence pauses there;
            # without its block, standing.
            frames = animations.get(evtchr_key(wanted, pose.evtchr, pose.colours))
            if frames:
                behind, mirrored = moving_view(direction)
                return frames["back" if behind else "front"], False, mirrored
            wanted = es.STAND
        if wanted == es.STAND:
            sequence, mirrored = standing_view(direction)
            frames = animations.get(sequence // 2)
            pictures = frames.get("back" if sequence % 2 else "front") if frames else None
            if pictures:
                return pictures, False, mirrored
            # A sprite without the standing sequences: its march's first picture, held.
            frames = animations.get(MARCH)
            if not frames:
                return None, False, False
            behind, mirrored = moving_view(direction)
            return frames["back" if behind else "front"][:1], False, mirrored
        behind, mirrored = moving_view(direction)
        frames = animations.get(wanted)
        loops = wanted == MARCH or frames is None
        frames = frames or animations.get(MARCH)
        if not frames:
            return None, False, False
        return frames["back" if behind else "front"], loops, mirrored

    def _paint_unit(self, p: QPainter, pose: es.Pose, world, ground: QPointF, ppu: float) -> Optional[tuple]:
        """Draws a unit: `(its picture's rectangle, its head)`, or None without pictures.
        The head, where a box's tail points, is over its feet at the height of
        its animation's first picture: it stays put while the unit marches or
        talks, so a box over it doesn't float up and down (Zodi, 19 October)."""
        pictures, loops, mirrored = self._frames_for(pose)
        if not pictures:
            return None
        ticks = max(0, int(self.frame - pose.since))
        total = sum(max(1, f[3].delay) for f in pictures)
        tick = ticks % max(1, total) if loops else min(ticks, total - 1)
        image, stand_x, stand_y = pictures[-1][:3]
        for picture in pictures:
            if tick < max(1, picture[3].delay):
                image, stand_x, stand_y = picture[:3]
                break
            tick -= max(1, picture[3].delay)
        if pose.tint is not None:
            image = self._tinted(image, pose.tint)
        size = em.WORLD_PER_HD_PIXEL * ppu
        # Drawn wider across as the map is (the game's 8 to 7, `event_camera`).
        size_across = size * self.view.camera.stretch
        width, height = image.width() * size_across, image.height() * size
        left = ground.x() - ((image.width() - stand_x) if mirrored else stand_x) * size_across
        top = ground.y() - stand_y * size
        rect = QRectF(left, top, width, height)
        head = QPointF(ground.x(), ground.y() - pictures[0][2] * size)
        hidden = self._hidden(rect, world)
        p.save()
        p.setOpacity(max(0.0, min(1.0, pose.alpha)))
        if hidden is None:
            if mirrored:
                p.translate(rect.center())
                p.scale(-1, 1)
                p.translate(-rect.center())
            p.drawImage(rect, image)
        else:
            # Drawn on a picture of its own at the screen's pixels, with what
            # the map's walls hide taken out of it.
            area, mask = hidden
            ratio = self.view.devicePixelRatioF()
            cut = QImage(mask.width(), mask.height(), QImage.Format_ARGB32_Premultiplied)
            cut.fill(Qt.transparent)
            q = QPainter(cut)
            q.setRenderHint(QPainter.SmoothPixmapTransform, p.testRenderHint(QPainter.SmoothPixmapTransform))
            q.scale(ratio, ratio)
            q.translate(-area.left(), -area.top())
            if mirrored:
                q.translate(rect.center())
                q.scale(-1, 1)
                q.translate(-rect.center())
            q.drawImage(rect, image)
            q.resetTransform()
            q.setCompositionMode(QPainter.CompositionMode_DestinationIn)
            q.drawImage(0, 0, mask)
            q.end()
            p.drawImage(area, cut)
        p.restore()
        return rect, head

    def _tinted(self, image: QImage, change: tuple) -> QImage:
        """A unit's picture in colours changed by ColorUnit (`tinted_image`), kept for the next frame."""
        key = (image.cacheKey(), tuple(round(v, 4) for v in change[0]), tuple(round(v, 4) for v in change[1]))
        found = self._tints.get(key)
        if found is None:
            if len(self._tints) >= TINTS_KEPT:
                self._tints.pop(next(iter(self._tints)))
            found = self._tints[key] = tinted_image(image, change)
        return found

    def _hidden(self, rect: QRectF, world) -> Optional[tuple]:
        """
        What of a unit's picture the map hides, or None when nothing does:
        `(area, mask)`, the area in the view's pixels and a mask the size of
        its screen pixels, clear where the map is nearer than the unit.

        The unit is taken as the game draws it, a picture standing upright on
        its tile facing the camera: each of its rows is as far as the point
        of that height over the tile, and a pixel is hidden where the map
        there (`MapView.depth`, from `MapRenderer.render_depth`) is nearer by
        more than a few of the map's units.
        """
        depth = self.view.depth
        if depth is None:
            return None
        import numpy as np
        view = self.view
        ratio = view.devicePixelRatioF()
        rows, cols = depth.shape
        x0, y0 = max(0, int(math.floor(rect.left() * ratio))), max(0, int(math.floor(rect.top() * ratio)))
        x1, y1 = min(cols, int(math.ceil(rect.right() * ratio))), min(rows, int(math.ceil(rect.bottom() * ratio)))
        if x1 <= x0 or y1 <= y0:
            return None
        width, height = cols, rows
        camera, renderer = view.camera, view.renderer
        feet = renderer.project(world, camera, width, height)
        up = max(((world[0], world[1] + d, world[2]) for d in (28.0, -28.0)),
                 key=lambda point: feet[1] - renderer.project(point, camera, width, height)[1])
        head = renderer.project(up, camera, width, height)
        if abs(head[1] - feet[1]) < 1e-6:
            return None
        near_feet = renderer.depth_of(world, camera, width, height)
        near_head = renderer.depth_of(up, camera, width, height)
        per_row = (near_head - near_feet) / (head[1] - feet[1])
        ys = np.arange(y0, y1, dtype=np.float32)[:, None]
        unit = near_feet + (ys + 0.5 - feet[1]) * per_row
        slack = HIDE_SLACK * renderer.depth_per_unit(camera)
        shown = depth[y0:y1, x0:x1] >= unit - slack
        if shown.all():
            return None
        alpha = np.ascontiguousarray(np.where(shown, 255, 0).astype(np.uint8))
        mask = QImage(alpha.data, x1 - x0, y1 - y0, x1 - x0, QImage.Format_Alpha8).copy()
        area = QRectF(x0 / ratio, y0 / ratio, (x1 - x0) / ratio, (y1 - y0) / ratio)
        return area, mask

    def screen(self) -> QRectF:
        """The game's screen in the view: the largest 16 by 9 picture that fits it."""
        return eb.screen_rect(float(self.view.width()), float(self.view.height()))

    def portrait_block(self, frame: float) -> Optional[int]:
        """The block of event faces read last by `frame` (`portrait_reads`), None before any."""
        found = None
        for when, block in self.portrait_reads:
            if when <= frame:
                found = block
        return found

    def box_selectors(self, box: es.BoxShown) -> list:
        """`[(frame, portrait)]`: a box's portrait as it opened, then each ChangeDialog's
        (its 0, which the timeline keeps as None, is the speaker's own face again)."""
        if self.timeline is not None:
            for opened, _closed, first, changes in self.timeline.boxes:
                if first.instruction == box.instruction and opened == box.opened:
                    return [(float(opened), int(first.portrait or 0))] + [
                        (float(when), int(portrait or 0)) for when, _line, portrait in changes]
        return [(float(box.opened), int(box.portrait or 0))]

    def box_face_at(self, box: es.BoxShown, frame: Optional[float] = None):
        """The face a box shows at `frame` (`box_face`): its speaker's, an event face or None."""
        frame = self.frame if frame is None else frame
        selector = 0
        for when, portrait in self.box_selectors(box):
            if when <= frame:
                selector = portrait
        return box_face(selector, self.portrait_block(frame), self.face_sprite(box.unit))

    def _face_for(self, box: es.BoxShown):
        """The face pieces a box shows now (`box_face_at`), None for none."""
        face = self.box_face_at(box)
        return self._faces.get(face) if face is not None else None

    def box_place(self, box: es.BoxShown, speaker: Optional[SpeakerAt]) -> tuple:
        """
        `(placed, face pieces or None, spoken)`: where a speech box goes on the
        game's screen (`event_balloon.place`, as wide as its words), the face
        it shows, and its words without their marks. `speaker` is where its
        speaker is in the view (`SpeakerAt`), None for nowhere.
        """
        screen = self.screen()
        scale = screen.height() / eb.SCREEN_H
        text = self.words(box.line)
        said = words_.spoken(text if text is not None else f"Line {box.line}")
        face = self._face_for(box)
        at = None
        if speaker is not None:
            def game(point: QPointF) -> tuple:
                return ((point.x() - screen.left()) / scale, (point.y() - screen.top()) / scale)
            # The way they face as the box opens, as the game places it then.
            at = eb.Speaker(game(speaker.head), game(speaker.ground),
                            self.faces_right(self.box_facing(box, speaker.facing), self.box_standing(box)))
        width = eb.box_width(said.words, face is not None, self.balloon_text)
        dx, dy, arrow = box.dx, box.dy, box.arrow
        if self.mode == "classic":
            dx, dy, arrow = dx * CLASSIC_ACROSS, dy * CLASSIC_DOWN, arrow * CLASSIC_ACROSS
        placed = eb.place(width, self.box_window(box), at, dx, dy, arrow, tail=not box.box & es.NO_TAIL,
                          face=face is not None)
        return placed, face, said

    def _box_speaker(self, box: es.BoxShown) -> Optional[tuple]:
        """`(facing, standing)`: a box's speaker as it opened, worked out once; None without the unit."""
        if self.timeline is None:
            return None
        key = (box.instruction, box.opened)
        if key not in self._box_facings:
            opening = self.timeline.at(box.opened)
            found = next((u for u in opening.units if u.unit_id == box.unit), None)
            self._box_facings[key] = None if found is None else (
                found.facing, not found.walking and found.animation == es.STAND)
        return self._box_facings[key]

    def box_facing(self, box: es.BoxShown, now: float) -> float:
        """The way a box's speaker faced as it opened (sixteenths); `now` without the unit."""
        found = self._box_speaker(box)
        return now if found is None else found[0]

    def box_standing(self, box: es.BoxShown) -> bool:
        """Whether a box's speaker stood as it opened (drawn in a standing sequence), as most do."""
        found = self._box_speaker(box)
        return True if found is None else found[1]

    def box_window(self, box: es.BoxShown) -> int:
        """
        Where a box goes: its own window, or for the kind placed by facing
        (0x70, most of a battle's), above (1) or below (2) its speaker as
        they face the camera when it opens (`event_scripts.facing_window`,
        whose notes say "the top" and "the bottom": the windows' first
        reading, before the dialog thread's place for them was built).
        """
        if box.box & 0x70 != es.FACING_KIND or self.timeline is None:
            return box.window
        key = (box.instruction, box.opened)
        if key not in self._box_windows:
            shown = self.timeline.at(box.opened)
            speaker = next((u for u in shown.units if u.unit_id == box.unit), None)
            yaw = shown.camera.yaw if shown.camera is not None else 0.0
            self._box_windows[key] = es.facing_window(box.box, speaker.facing, yaw) if speaker is not None \
                else box.window
        return self._box_windows[key]

    def _paint_words(self, p: QPainter, box: es.BoxShown) -> None:
        """A box of kind 0: its words alone on the screen (`event_text`)."""
        text = self.words(box.line)
        said = words_.spoken(text if text is not None else f"Line {box.line}")
        dx, dy = box.dx, box.dy
        if self.mode == "classic":
            dx, dy = dx * CLASSIC_ACROSS, dy * CLASSIC_DOWN
        drawn = et.draw_text_only(p, self.screen(), self.screen_text, said.runs, box.options, dx, dy,
                                  self.frame - box.opened)
        self.boxes_drawn.append((box, drawn, None))

    def _paint_box(self, p: QPainter, box: es.BoxShown, speaker: Optional[SpeakerAt]) -> None:
        placed, pieces, said = self.box_place(box, speaker)
        since = self.frame - box.opened
        face = None
        if pieces is not None:
            face = eb.face_image(pieces, eb.eye_part(since), self.mouth_now(box, said))
        name = said.name or self.speaker(box.line) or self.names.get(box.unit)
        kind = "round" if box.box & 0x04 else "normal"
        drawn = eb.draw(p, self.screen(), placed, kind, self._sheets, said.rich, name, face, since,
                        self.balloon_text, said.runs)
        self.boxes_drawn.append((box, drawn.box, drawn.tail_tip))
        self.balloons_drawn.append(drawn)

    # -- clicking a tile ----------------------------------------------------------------

    def _tile_clicked(self, key, _add: bool) -> None:
        """A click (not a drag) on a tile: the page's, for the node picked."""
        if key is not None:
            self.tile_clicked.emit(int(key[0]), int(key[1]), int(key[2]))
