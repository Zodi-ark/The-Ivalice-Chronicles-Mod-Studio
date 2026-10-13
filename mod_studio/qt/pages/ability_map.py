"""
The Abilities page's map: the ability played out on map 116, on a loop.

Zodi, 12 October: "Redesign the abilities page, so that the map viewer
displays the unit animations for the ability on map 116 and after it
completes then show the ability effect on the map, take note that some
abilities target themselves or a different unit or units at different
ranges, then make the whole thing loop", with "Being able to toggle through
all the sprites that use that ability" and, for abilities 265 to 356, the
monster that uses it. For the effect: "Do it completly now the emitters,
timing, camera, and sound as well as everything else that is possible".
Agreed from a mock-up the same day.

- **The loop**: the unit charging (when the ability has a charge time),
  its animation for the ability, the effect, a short pause; then again.
  The chips under the map say which part is playing.
- **Who**: the unit stands on tile 2, 5 facing east, and is whoever "Shown
  by" picks: every job and monster whose commands hold the ability
  (`ability_preview.ability_users`), Previous and Next stepping through
  them. An ability nobody has is used by a stand-in.
- **Where**: its range in blue, its effect area in gold, aimed as far as it
  reaches straight ahead, or at the unit itself; up to three stand-ins on
  the tiles it hits, which flinch (or raise their hands, for a heal) when
  the effect says it hits them.
- **The effect** (`effect_player`, `effect_drawing`): its particles, the
  backdrop's colours, the map's, the user's and the targets' colours, its
  camera ("Effect camera") and its sounds ("Sound", `effect_sound`).

The page supplies what the ability is (`AbilityShow`), its pending edits
included. Everything else is read from the unpacked game: map 116 and the
unit sprites with the Textures unpack, the effects from `fftpack/effect`,
the sounds from `system/ffto/fftpack.en.bin`.
"""
from __future__ import annotations

import bisect
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (
    QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPolygonF, QVector3D,
)
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
    QVBoxLayout, QWidget,
)

from ... import ability_preview as ap
from ... import effect_files as ef
from ... import effect_player as ep
from ... import entd
from ... import map_classic as mc
from ... import map_enhanced as me
from ... import unit_sprites as us
from .. import effect_drawing as ed
from .. import map_scene as ms
from .. import theme
from ..map_render import Camera
from ..widgets import map_view as mv
from ..widgets.flow_layout import FlowLayout
from ..widgets.map_view import MapView
from ..workers import Worker, run_in_thread
from . import map_editor as me_page
from .encounter_map import (
    FLY_BOB, FLY_HEIGHT, FLY_SECONDS, RING_H, RING_W, TEAM_COLOURS, WORLD_PER_HD_PIXEL,
)

#: The map abilities are played out on, where the unit stands and which way it faces.
MAP_NUMBER = 116
CASTER_TILE, CASTER_FACING = (2, 5), 3
#: Who stands in: for an ability nobody has, and on the tiles it hits.
STAND_IN_CASTER = (96, 0)
STAND_IN_TARGET = (96, 3)
MOST_TARGETS = 3
#: How long the parts of the loop take that the files don't time, in seconds.
CHARGE_SECONDS = 1.5
PAUSE_SECONDS = 0.8
NO_ANIMATION_SECONDS = 0.5
#: The least the unit's animation is given, so a one-frame one is seen.
LEAST_CAST_SECONDS = 0.4
#: The parts of the loop.
CHARGING, CASTING, EFFECT, PAUSE = "Charging", "Casting", "Effect", "Pause"
STAGES = (CHARGING, CASTING, EFFECT, PAUSE)
#: How often the loop moves on, in milliseconds.
TICK = 33
#: The least the map and the Shown by box take, so the page fits the window
#: at its narrowest (`shell.MIN_WIDTH`) beside the list and the fields.
MAP_LEAST, SHOWN_BY_LEAST = 140, 130
#: The PlayStation camera at the usual zoom (4096) shows this many world
#: units above and below the middle of the screen.
PSX_HALF_HEIGHT = 176.4
#: An effect's action bit for "the target reacts": it is hit.
HIT = 0x10
#: The tiles' colours: range blue, effect area gold.
RANGE_EDGE, RANGE_FILL = QColor(92, 160, 255, 210), QColor(70, 140, 255, 62)
AREA_EDGE, AREA_FILL = QColor(255, 206, 64, 235), QColor(255, 196, 40, 105)
#: The unit's ring and the targets'.
CASTER_RING, TARGET_RING = TEAM_COLOURS[0], TEAM_COLOURS[1]

HINT = ("The ability plays on map 116 on a loop: the unit charging, its animation, then the effect "
        "on its targets. Shown by picks the unit: every job and monster whose commands have it. "
        "Drag to turn the map, Shift and drag to move it, and use the wheel to zoom.")
NO_GAME = "No game files yet. Unpack your game on General Setup to see abilities played out here."
NO_MAP = "Map 116 isn't in the game's files, so the ability can't be played out on it."
PICK_AN_ABILITY = "Pick an ability in the list to see it played out here."
NOBODY = "No job's or monster's commands have this ability, so a stand-in uses it."
NO_EFFECT = "This ability has no effect (Effect ID {}), so only the unit's animation plays."
MISSING_EFFECT = "Effect {:03d} isn't in the game's effect folder, so only the unit's animation plays."
BAD_EFFECT = "Effect {:03d} couldn't be played: {}"
NO_NUMPY = ("Effects are drawn with numpy, which isn't installed ({}), so only the unit's "
            "animation plays.")
CALLBACKS = ("Effect {:03d} also draws shapes the game makes in code (rings, beams and the like), "
             "which aren't drawn here.")
SOUND_GAPS = ("Some of its sounds play on {} instrument{} The Ivalice Chronicles' copy of the "
              "PlayStation sounds has no sample for, so they are quieter or silent here.")
NO_SOUND = "Its sounds can't be played: {}"
NO_SPRITES = "Units are drawn as rings: their sprites need the Textures unpack ({})."
NO_CAST = "The unit's sprite has no animation {} ({}), so it stands still for it."
NO_TILE = "Map 116 has no tile 2, 5 for the unit to stand on, so the ability can't be played out on it."


@dataclass
class AbilityShow:
    """What the page says an ability is, its pending edits included."""
    key: int
    title: str
    effect: int                     # an `fftpack/effect` file's number, or below 0 for none
    charge_time: int
    charge_type: int
    charge_name: str
    animation: int
    animation_name: str
    reach: ap.Reach
    #: The targets' reaction to a hit: `ability_preview.TAKING_DAMAGE`,
    #: `RECEIVE_HEAL`, or None for none.
    reaction: Optional[int] = None


def _qimage(picture: us.Picture) -> QImage:
    return QImage(picture.rgba, picture.width, picture.height, picture.width * 4,
                  QImage.Format_RGBA8888).copy()


def _stamp(path: Path) -> Optional[tuple]:
    try:
        found = path.stat()
    except OSError:
        return None
    return (str(path), found.st_size, found.st_mtime_ns)


def classic_lights(game_dir, number: int) -> Optional[mc.Lights]:
    """Map `number`'s lights from its classic files: the backdrop's colours among them."""
    try:
        folder = Path(game_dir) / mc.MAP_FOLDER
        sources = mc.read_gns(folder, number).sources(mc.State())
        if "lights" not in sources:
            return None
        return mc.read_mesh((folder / sources["lights"].file_name).read_bytes()).lights
    except (OSError, ValueError, mc.MapError):
        return None


def psx_camera(renderer, angles, position, zoom: float, width: int, height: int) -> Camera:
    """
    The map view's camera for the PlayStation's: `angles` (pitch, yaw, roll;
    4096 a turn), looking at `position` (PlayStation units, y down) at
    `zoom` (4096 usual). The game's yaw 3584 is the view's 225, its usual
    south-west corner; its zoom 4096 shows `PSX_HALF_HEIGHT` world units
    above and below the middle.
    """
    # A turn and a bit (effect 242 reaches 4398), or below the ground (452,
    # 453): wrapped into a half turn either way, then kept where the view goes.
    turned = (angles[0] + 2048.0) % 4096.0 - 2048.0
    pitch = min(ms.TOP_PITCH, max(mv.LOWEST_PITCH, turned * 360.0 / 4096.0))
    yaw = (angles[1] * 360.0 / 4096.0 - 90.0) % 360.0
    camera = Camera(yaw, pitch, 1.0, (0.0, 0.0))
    fit = renderer.half_height(camera, width / max(1, height))
    wanted = PSX_HALF_HEIGHT * ep.DEFAULT_ZOOM / max(1.0, float(zoom))
    camera.zoom = min(mv.ZOOM_MAX, max(mv.ZOOM_MIN, fit / wanted))
    _proj, view = renderer.matrices(camera, width, height)
    seen = view.map(QVector3D(-position[0], -position[1], position[2]))
    camera.pan = (-seen.x(), seen.y())
    return camera


# =============================================================================
# Off the GUI thread
# =============================================================================

class AbilitySceneWorker(ms.SceneWorker):
    """Map 116 as the Encounters page reads its maps, and its backdrop's colours."""

    def run(self):
        token, scene, error = super().run()
        lights = None
        if scene is not None:
            lights = scene.lights or classic_lights(self.game_dir, self.number)
        return token, scene, error, lights


class SpritesJob(Worker):
    """
    Draws units' animations: `({(sprite, palette): ({animation id: {"front":
    [(QImage, stand x, stand y, Step)], "back": [...]}}, flying, ids asked)},
    problem)`; an animation the sprite hasn't is left out.
    """

    def __init__(self, sprites: us.UnitSprites, wanted: dict):
        super().__init__()
        self.sprites, self.wanted = sprites, {key: set(ids) for key, ids in wanted.items()}

    def run(self):
        made = {}
        for (sprite, palette), ids in sorted(self.wanted.items()):
            moving, flying = ap.sprite_animations(self.sprites, sprite, palette, ids)
            animations = {}
            for animation_id, found in moving.items():
                animations[animation_id] = {
                    side: [(_qimage(p), p.stand_x, p.stand_y, step) for p, step in pictures]
                    for side, pictures in (("front", found.front), ("back", found.back))}
            made[(sprite, palette)] = (animations, flying, ids)
        return made, self.sprites.problem


class SoundBank:
    """The PlayStation sample bank of one unpacked game, read when first asked for."""

    def __init__(self, game_dir):
        self.game_dir = game_dir
        self._instruments = None

    def instruments(self) -> list:
        if self._instruments is None:
            from ... import effect_sound as es
            self._instruments = es.read_waveset(es.waveset_bytes(self.game_dir))
        return self._instruments


class EffectJob(Worker):
    """Plays an effect for the targets, and mixes its sounds:
    `(token, effect or None, Playback, EffectSounds or None, what went wrong)`."""

    def __init__(self, token, game_dir, number, targets, caster_place, map_size, bank):
        super().__init__()
        self.token, self.game_dir, self.number = token, game_dir, number
        self.targets, self.caster_place, self.map_size = targets, caster_place, map_size
        self.bank = bank

    def run(self):
        try:
            effect = ef.load_effect(self.game_dir, self.number)
        except (OSError, ef.EffectError) as exc:
            return (self.token, None, None, None, str(exc) or exc.__class__.__name__)
        playback = ep.play(effect, targets=self.targets, seed=1, caster_place=self.caster_place,
                           map_size=self.map_size)
        sounds, problem = None, ""
        if playback.sounds:
            try:
                from ... import effect_sound as es
                sounds = es.render_effect(effect.feds, self.bank.instruments(), playback.sounds,
                                          [frame.seconds for frame in playback.frames])
            except Exception as exc:                          # noqa: BLE001
                problem = str(exc) or exc.__class__.__name__
        return (self.token, effect, playback, sounds, problem)


# =============================================================================
# The map
# =============================================================================

@dataclass
class Moment:
    """Where the loop is: its part, the seconds into it, and the effect's frame."""
    stage: str
    seconds: float
    frame: Optional[int] = None


class AbilityMap(QWidget):
    """The map column of the Abilities page (see the module's notes)."""

    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(6)

        # The controls and the chips wrap (`FlowLayout`) and the map can be
        # small, so the page fits the window at its narrowest beside the
        # list and the fields' column: in one row each, the map alone came
        # to 514 wide at least, and the page to 1,470 (the window's least
        # is 1,345 with the sidebar).
        head = QHBoxLayout()
        head.setSpacing(8)
        self.title = QLabel("")
        self.title.setStyleSheet("font-weight: 600; font-size: 12pt;")
        self.title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        head.addWidget(self.title, 1)
        controls = QWidget()
        flow = FlowLayout(controls, spacing=8)
        self.shown_by_label = QLabel("Shown by")
        flow.addWidget(self.shown_by_label)
        self.shown_by = QComboBox()
        self.shown_by.setMinimumWidth(SHOWN_BY_LEAST)
        self.shown_by.setToolTip("Who uses the ability: every job and monster whose commands have it.")
        self.shown_by.activated.connect(self._user_chosen)
        flow.addWidget(self.shown_by)
        self.previous_button = QPushButton("Previous")
        self.previous_button.setToolTip("The one before in Shown by")
        self.previous_button.clicked.connect(lambda: self.step_user(-1))
        flow.addWidget(self.previous_button)
        self.next_button = QPushButton("Next")
        self.next_button.setToolTip("The next one in Shown by")
        self.next_button.clicked.connect(lambda: self.step_user(1))
        flow.addWidget(self.next_button)
        self.pause_button = QPushButton("Pause")
        self.pause_button.setToolTip("Stop the loop where it is, or play it on")
        self.pause_button.clicked.connect(self.toggle_pause)
        flow.addWidget(self.pause_button)
        head.addWidget(controls)
        column.addLayout(head)

        self.view = MapView()
        self.view.show_info = False
        self.view.transparent = True
        self.view.overlay = self.paint_frame
        self.view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.view.setMinimumSize(MAP_LEAST, MAP_LEAST)
        self.view.camera_changed.connect(self._camera_moved)
        column.addWidget(self.view, 1)

        # One wrapping row: the chips, then the two switches. Kept apart
        # (the switches at the right), the row could be no narrower than a
        # chip and a switch side by side, and the page then came 32 over.
        row = QWidget()
        chips = FlowLayout(row, spacing=6)
        self.chips = {}
        for number, stage in enumerate(STAGES, 1):
            chip = QLabel(f"{number} {stage}")
            chip.setAlignment(Qt.AlignCenter)
            self.chips[stage] = chip
            chips.addWidget(chip)
        self.sound_box = QCheckBox("Sound")
        self.sound_box.setChecked(True)
        self.sound_box.setToolTip("Play the effect's sounds")
        self.sound_box.toggled.connect(self._sound_toggled)
        chips.addWidget(self.sound_box)
        self.camera_box = QCheckBox("Effect camera")
        self.camera_box.setChecked(True)
        self.camera_box.setToolTip("Let the effect move the camera, as it does in the game")
        self.camera_box.toggled.connect(self._camera_toggled)
        chips.addWidget(self.camera_box)
        column.addWidget(row)

        self.legend = QLabel("")
        self.legend.setTextFormat(Qt.RichText)
        self.legend.setWordWrap(True)
        column.addWidget(self.legend)
        #: Said only when there is something to say.
        self.note = QLabel("")
        self.note.setProperty("role", "muted")
        self.note.setWordWrap(True)
        self.note.setVisible(False)
        column.addWidget(self.note)
        self.hint = QLabel(HINT)
        self.hint.setProperty("role", "muted")
        self.hint.setWordWrap(True)
        column.addWidget(self.hint)

        #: What is shown: the ability, who uses it, and the tiles.
        self.show_data: Optional[AbilityShow] = None
        self.users: list = []
        self.user: Optional[ap.User] = None
        self.places: Optional[dict] = None
        #: The map: read once a game, again when what it's drawn from changes.
        self.lights = None
        self._token = 0
        self._reading = False
        self._scene_key = None
        self._wanted_key = None
        #: The game's files, read again when they change.
        self._sprites = None
        self._sprites_key = None
        self._job_sprites = None
        self._job_sprites_key = None
        self._bank = None
        #: `{(sprite, palette): {"animations": {id: sides}, "flying": bool, "asked": set}}`.
        self._pictures: dict = {}
        self._pending: dict = {}
        self._sprite_job = None
        self.sprite_problem = ""
        #: The effect: `{"key", "effect", "playback", "sounds", "pictures", "times", "hits",
        #: "problem"}`, the one asked for, and whether one is being played.
        self.effect = None
        self._effect_wanted = None
        self._effect_token = 0
        self._effect_busy = False
        #: The loop's clock: seconds from its start, held while paused.
        self.clock = time.monotonic
        self._loop_started = self.clock()
        self._paused_at: Optional[float] = None
        self.moment = Moment(PAUSE, 0.0)
        self._ticker = QTimer(self)
        self._ticker.setInterval(TICK)
        self._ticker.timeout.connect(self.tick)
        #: The camera the person set, kept while the effect moves the view's.
        self._own_camera: Optional[Camera] = None
        self._moving_camera = False
        #: The map picture as the effect colours it, and the range and area
        #: tiles drawn for a camera: `(what it was made for, QImage)`.
        self._tinted_map = None
        self._tiles_picture = None
        self._reading_for = None
        self._effect_asked = None
        #: The person turned or zoomed the map while the effect moved the
        #: camera: theirs until the next effect.
        self._camera_taken = False
        self._player = None
        self._sounding = None
        self._refresh_chips()
        self._update_buttons()

    # -- the game's files -----------------------------------------------------------

    def game_dir(self) -> Optional[Path]:
        root = getattr(self.state, "nxd_unpack_dir", None)
        return Path(root) if root and Path(root).is_dir() else None

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

    def job_sprites(self, jobs: dict) -> dict:
        """job -> {sprite: units} from the game's battles, read once a game."""
        game = self.game_dir()
        key = (str(game),) + tuple(_stamp(p) for p in entd.find_entd_files(game)) if game else None
        if key != self._job_sprites_key:
            tables = entd.EntdTables.from_folder(game) if game is not None else None
            self._job_sprites, self._job_sprites_key = ap.entd_job_sprites(tables, jobs), key
        return self._job_sprites or {}

    def bank(self) -> Optional[SoundBank]:
        game = self.game_dir()
        if game is None:
            return None
        if self._bank is None or self._bank.game_dir != game:
            self._bank = SoundBank(game)
        return self._bank

    # -- who uses it ------------------------------------------------------------------

    def jobs(self) -> dict:
        """job id -> its fields, the mod's edits over the game's."""
        out = {}
        edits = getattr(self.state, "edits", {}) or {}
        for record in getattr(self.state, "job_records", None) or []:
            values = dict(record.values)
            values.update(edits.get(record.job_id, {}))
            out[record.job_id] = values
        return out

    def commands(self) -> dict:
        """skillset id -> its abilities, the mod's edits over the game's."""
        out = {}
        edits = getattr(self.state, "job_command_edits", {}) or {}
        for record in getattr(self.state, "job_command_records", None) or []:
            ids = list(record.ability_ids)
            changed = edits.get(record.command_id, {})
            for slot in range(len(ids)):
                if f"AbilityId{slot + 1}" in changed:
                    try:
                        ids[slot] = int(str(changed[f"AbilityId{slot + 1}"]).strip())
                    except ValueError:
                        pass
            out[record.command_id] = ids
        return out

    def users_of(self, ability: int) -> list:
        jobs = self.jobs()
        names = {record.job_id: record.name for record in getattr(self.state, "job_records", None) or []
                 if record.name}
        return ap.ability_users(ability, jobs, self.commands(), names, self.job_sprites(jobs))

    # -- what is shown ----------------------------------------------------------------

    def show(self, show: Optional[AbilityShow]) -> None:
        """Plays `show` out, from the top of the loop when it is a different ability."""
        previous = self.show_data
        self.show_data = show
        self.title.setText(show.title if show is not None else "")
        if show is None:
            self.users, self.user = [], None
        else:
            kept = (self.user.job, self.user.sprite, self.user.palette) if self.user else None
            self.users = self.users_of(show.key)
            chosen = next((u for u in self.users if (u.job, u.sprite, u.palette) == kept), None)
            if previous is None or previous.key != show.key or chosen is None:
                chosen = self.users[0] if self.users else None
            self.user = chosen
        self._fill_shown_by()
        if previous is None or show is None or previous.key != show.key:
            self.restart()
        self.refresh()

    def _fill_shown_by(self) -> None:
        self.shown_by.blockSignals(True)
        self.shown_by.clear()
        count = len(self.users)
        for n, user in enumerate(self.users, 1):
            self.shown_by.addItem(f"{user.label}  ({n} of {count})")
        if not self.users:
            self.shown_by.addItem("A stand-in")
        index = self.users.index(self.user) if self.user in self.users else 0
        self.shown_by.setCurrentIndex(index)
        self.shown_by.blockSignals(False)
        self._update_buttons()

    def _update_buttons(self) -> None:
        many = len(self.users) > 1
        self.previous_button.setEnabled(many)
        self.next_button.setEnabled(many)
        self.shown_by.setEnabled(bool(self.users))
        self.pause_button.setText("Play" if self._paused_at is not None else "Pause")

    def _user_chosen(self, index: int) -> None:
        if 0 <= index < len(self.users) and self.users[index] is not self.user:
            self.user = self.users[index]
            self.restart()
            self.refresh()

    def step_user(self, step: int) -> None:
        """Shows the next (or previous) one in Shown by, round to the first."""
        if len(self.users) < 2:
            return
        index = (self.users.index(self.user) + step) % len(self.users) if self.user in self.users else 0
        self.shown_by.setCurrentIndex(index)
        self._user_chosen(index)

    def caster_sprite(self) -> tuple:
        if self.user is not None:
            return self.user.sprite, self.user.palette
        return STAND_IN_CASTER

    def cast_id(self) -> int:
        """The animation the unit plays for the ability (`ability_preview.cast_animation`)."""
        monster = bool(self.user is not None and self.user.monster)
        return ap.cast_animation(self.show_data.animation, monster) if self.show_data else ap.WALK

    def refresh(self) -> None:
        """Reads the map if what it is drawn from changed, then places everything again."""
        game = self.game_dir()
        if game is None:
            self._no_map(NO_GAME)
            return
        if self.show_data is None:
            self._no_map(PICK_AN_ABILITY)
            return
        key = self._look_key(game)
        if key is None:
            self._no_map(NO_MAP)
            return
        if key != self._scene_key or self.view.scene is None:
            if key != self._wanted_key:
                self._wanted_key = key
                self._token += 1
                self.view.set_message(f"Reading map {MAP_NUMBER:03d}...")
                if not self._reading:
                    self._start_reading()
            return
        self._placed()

    def _look_key(self, game: Path) -> Optional[tuple]:
        """What map 116 is drawn from (Treasure Hunter's and the Encounters page's rules), or None without it."""
        try:
            if not mc.read_gns(game / mc.MAP_FOLDER, MAP_NUMBER).states():
                return None
        except (OSError, mc.MapError):
            return None
        enhanced = me.mesh_path(game, MAP_NUMBER).is_file()
        mesh, pictures = me_page.mod_look(self.state, MAP_NUMBER) if enhanced else (None, {})
        rows = me_page.mod_rows(self.state, MAP_NUMBER) if enhanced else {}
        edits = {key: dict(found) for key, found in (getattr(self.state, "map_edits", {}) or {}).items()}
        return (str(game), ms.ENHANCED if enhanced else ms.CLASSIC, mesh, tuple(sorted(pictures.items())),
                repr(sorted((t, sorted(f.items())) for t, f in rows.items())), repr(sorted(edits.items())))

    def _start_reading(self) -> None:
        game, key, token = self.game_dir(), self._wanted_key, self._token
        if game is None or key is None:
            return
        look = key[1]
        mesh, pictures = me_page.mod_look(self.state, MAP_NUMBER)
        self._reading = True
        worker = AbilitySceneWorker(
            token, game, MAP_NUMBER, look, mc.State(), getattr(self.state, "nxd_sqlite_path", None),
            mesh if look == ms.ENHANCED else None, pictures if look == ms.ENHANCED else {}, 0,
            me_page.mod_rows(self.state, MAP_NUMBER) if look == ms.ENHANCED else {})
        self._reading_for = key
        run_in_thread(worker, on_finished=self._scene_ready, on_failed=self._scene_failed)

    def _scene_ready(self, result) -> None:
        self._reading = False
        token, scene, error, lights = result
        if token != self._token or self._reading_for != self._wanted_key:
            self._start_reading()
            return
        if scene is None:
            self._no_map(f"Map {MAP_NUMBER:03d} could not be drawn: {error}")
            return
        edits = (getattr(self.state, "map_edits", {}) or {}).get(scene.grid_key, {}) if scene.grid_key else {}
        tiles = ([me_page.as_edited(t, edits.get((t.x, t.z, t.level), {})) for t in scene.terrain.tiles]
                 if scene.terrain is not None else [])
        self._scene_key, self.lights = self._reading_for, lights
        self._tinted_map = None
        self.view.set_message(" ".join(scene.notes))
        self.view.set_scene(scene, tiles, ())
        self._placed()

    def _scene_failed(self, message: str) -> None:
        self._reading = False
        self._no_map(f"This map could not be drawn: {message}")

    def _no_map(self, message: str) -> None:
        self._scene_key = self._wanted_key = None
        self.places = None
        self.view.set_scene(None)
        self.view.set_message(message)
        self._stop_sound()
        self._update_ticker()
        self._update_legend()
        self._say_note()

    # -- where everything stands --------------------------------------------------------

    def map_size(self) -> tuple:
        tiles = self.view.tiles
        if not tiles:
            return (0, 0)
        return (max(t.x for t in tiles) + 1, max(t.z for t in tiles) + 1)

    def ground(self, place) -> Optional[tuple]:
        """The middle of tile `place` (x, z) in world units, on its surface; None off the map."""
        tile = self.view.tile((place[0], place[1], 0))
        if tile is None or not ms.shows(tile):
            return None
        corners = ms.tile_corners(tile, 0.0)
        return tuple(sum(c[i] for c in corners) / 4 for i in range(3))

    def _placed(self) -> None:
        """Works out the tiles, the stand-ins and the effect's targets, then asks for what they need."""
        show = self.show_data
        if show is None or self.view.scene is None:
            self.places = None
            self._update_legend()
            self._say_note()
            return
        size = self.map_size()
        caster, facing, reach = CASTER_TILE, CASTER_FACING, show.reach
        aimed = ap.aim(caster, facing, reach, size)
        area = ap.area_tiles(caster, aimed, facing, reach, size)
        reached = ap.range_tiles(caster, reach, size)
        stand = ap.stand_ins(aimed, area, caster, MOST_TARGETS)
        hit_tiles = ([caster] if aimed == caster else []) + stand
        if not hit_tiles:
            hit_tiles = [aimed]
        caster_world = self.ground(caster)
        if caster_world is None:
            self.places = None
            self.view.set_message(NO_TILE)
            self._update_ticker()
            self._update_legend()
            self._say_note()
            return
        targets = []
        for tile in hit_tiles:
            world = self.ground(tile) or caster_world
            targets.append(((caster_world[0] - world[0]) / mc.TILE_SIZE,
                            (world[1] - caster_world[1]) / mc.TILE_SIZE,
                            (world[2] - caster_world[2]) / mc.TILE_SIZE))
        self.places = {
            "caster": caster, "facing": facing, "aimed": aimed, "area": area, "range": reached,
            "stand_ins": stand, "hit": hit_tiles, "targets": targets, "world": caster_world,
            "caster_place": (-caster_world[0] / mc.TILE_SIZE, caster_world[1] / mc.TILE_SIZE,
                             caster_world[2] / mc.TILE_SIZE),
            "size": size,
        }
        self._want_sprites()
        self._want_effect()
        self._update_legend()
        self._say_note()
        self._update_ticker()
        self.view.update()

    # -- sprites ------------------------------------------------------------------------

    def animation_ids(self) -> set:
        show = self.show_data
        ids = {ap.WALK}
        if show is not None:
            ids |= set(ap.charge_pose(show.charge_name))
            ids.add(self.cast_id())
        return ids

    def _want_sprites(self) -> None:
        sprites = self.unit_sprites()
        if sprites is None or self.show_data is None:
            return
        wanted = {self.caster_sprite(): self.animation_ids()}
        reactions = {ap.WALK} | ({self.show_data.reaction} if self.show_data.reaction is not None else set())
        wanted.setdefault(STAND_IN_TARGET, set()).update(reactions)
        missing = {}
        for key, ids in wanted.items():
            asked = set(self._pictures.get(key, {}).get("asked", set())) | self._pending.get(key, set())
            if ids - asked:
                missing[key] = ids - asked
        if not missing or self._sprite_job is not None:
            return
        for key, ids in missing.items():
            self._pending.setdefault(key, set()).update(ids)
        self._sprite_job = SpritesJob(sprites, missing)
        run_in_thread(self._sprite_job, on_finished=self._sprites_ready, on_failed=self._sprites_failed)

    def _sprites_ready(self, result) -> None:
        made, problem = result
        self._sprite_job = None
        for key, (animations, flying, asked) in made.items():
            entry = self._pictures.setdefault(key, {"animations": {}, "flying": False, "asked": set()})
            entry["animations"].update(animations)
            entry["flying"] = entry["flying"] or flying
            entry["asked"] |= asked
            pending = self._pending.get(key, set()) - asked
            if pending:
                self._pending[key] = pending
            else:
                self._pending.pop(key, None)
        drawn = any(entry["animations"] for entry in self._pictures.values())
        self.sprite_problem = "" if drawn or not problem else problem
        self._say_note()
        self.view.update()
        self._want_sprites()

    def _sprites_failed(self, message: str) -> None:
        self._sprite_job = None
        for key, ids in self._pending.items():
            entry = self._pictures.setdefault(key, {"animations": {}, "flying": False, "asked": set()})
            entry["asked"] |= ids
        self._pending.clear()
        self.sprite_problem = message
        self._say_note()

    def frames_of(self, key: tuple, animation_id: int) -> Optional[dict]:
        entry = self._pictures.get(key)
        return entry["animations"].get(animation_id) if entry else None

    def flying(self, key: tuple) -> bool:
        entry = self._pictures.get(key)
        return bool(entry and entry["flying"])

    # -- the effect ---------------------------------------------------------------------

    def _effect_key(self) -> Optional[tuple]:
        show, places = self.show_data, self.places
        if show is None or places is None or show.effect < 0:
            return None
        return (str(self.game_dir()), show.effect, tuple(places["targets"]),
                places["caster_place"], places["size"])

    def _want_effect(self) -> None:
        key = self._effect_key()
        if key is None:
            self.effect = None
            self._effect_wanted = None
            return
        if self.effect is not None and self.effect["key"] == key:
            return
        self._effect_wanted = key
        missing = ed.numpy_missing()
        if missing:
            # The window builds without numpy; the effect can't be drawn.
            self.effect = {"key": key, "effect": None, "playback": None, "sounds": None,
                           "problem": NO_NUMPY.format(missing)}
            return
        if self._effect_busy:
            return
        game = self.game_dir()
        if not ef.effect_path(game, key[1]).is_file():
            self.effect = {"key": key, "effect": None, "playback": None, "sounds": None,
                           "problem": MISSING_EFFECT.format(key[1])}
            return
        self._effect_busy = True
        self._effect_token += 1
        self._effect_asked = key
        job = EffectJob(self._effect_token, game, key[1], list(key[2]), key[3], key[4], self.bank())
        run_in_thread(job, on_finished=self._effect_ready, on_failed=self._effect_failed)

    def _effect_ready(self, result) -> None:
        self._effect_busy = False
        token, effect, playback, sounds, problem = result
        key = self._effect_asked
        if key != self._effect_wanted:
            self._want_effect()
            return
        if effect is None:
            self.effect = {"key": key, "effect": None, "playback": None, "sounds": None,
                           "problem": BAD_EFFECT.format(key[1], problem)}
        else:
            times = [0.0]
            for frame in playback.frames:
                times.append(times[-1] + frame.seconds)
            hits = {}
            for frame in playback.frames:
                for event in frame.events:
                    if event[0] == "action" and event[1] & HIT:
                        hits.setdefault(event[3], []).append(times[frame.number])
            if not hits and playback.length:
                hits = {i: [times[min(playback.after_start, playback.length - 1)]]
                        for i in range(len(key[2]))}
            self.effect = {"key": key, "effect": effect, "playback": playback, "sounds": sounds,
                           "pictures": ed.EffectPictures(effect), "times": times, "hits": hits,
                           "problem": "", "sound_problem": problem}
        self._stop_sound()
        self._say_note()
        self._update_legend()
        self.view.update()

    def _effect_failed(self, message: str) -> None:
        self._effect_busy = False
        key = self._effect_asked
        if key != self._effect_wanted:
            self._want_effect()
            return
        self.effect = {"key": key, "effect": None, "playback": None, "sounds": None,
                       "problem": BAD_EFFECT.format(key[1], message)}
        self._say_note()

    def playback(self) -> Optional[ep.Playback]:
        return self.effect.get("playback") if self.effect else None

    # -- the loop ---------------------------------------------------------------------

    def durations(self) -> dict:
        """How long each part of the loop lasts, in seconds."""
        show = self.show_data
        charge = CHARGE_SECONDS if show is not None and show.charge_time > 0 else 0.0
        cast = NO_ANIMATION_SECONDS
        if show is not None:
            frames = self.frames_of(self.caster_sprite(), self.cast_id())
            if frames and frames.get("front"):
                cast = max(LEAST_CAST_SECONDS, _seconds(frames))
        playback = self.playback()
        effect = playback.seconds if playback is not None else 0.0
        return {CHARGING: charge, CASTING: cast, EFFECT: effect, PAUSE: PAUSE_SECONDS}

    def loop_seconds(self) -> float:
        now = self._paused_at if self._paused_at is not None else self.clock()
        return max(0.0, now - self._loop_started)

    def moment_at(self, seconds: float) -> Moment:
        durations = self.durations()
        total = sum(durations.values())
        if total <= 0:
            return Moment(PAUSE, 0.0)
        t = seconds % total
        for stage in STAGES:
            if t < durations[stage]:
                frame = None
                if stage == EFFECT and self.effect and self.effect.get("times"):
                    times = self.effect["times"]
                    frame = max(0, min(len(times) - 2, bisect.bisect_right(times, t) - 1))
                return Moment(stage, t, frame)
            t -= durations[stage]
        return Moment(PAUSE, durations[PAUSE])

    def restart(self) -> None:
        """The loop from its top."""
        self._loop_started = self.clock()
        if self._paused_at is not None:
            self._paused_at = self._loop_started
        self._stop_sound()
        self._give_camera_back()

    def toggle_pause(self) -> None:
        if self._paused_at is None:
            self._paused_at = self.clock()
            self._stop_sound()
        else:
            self._loop_started += self.clock() - self._paused_at
            self._paused_at = None
            if self.moment.stage == EFFECT:
                self._play_sound(self.moment.seconds)
        self._update_buttons()
        self._update_ticker()

    @property
    def paused(self) -> bool:
        return self._paused_at is not None

    def tick(self) -> None:
        """Moves the loop on: its part, the effect's camera and sound, and a new picture."""
        window = self.window()
        if not self.isVisible() or (window is not None and window.isMinimized()):
            return
        before = self.moment
        self.moment = self.moment_at(self.loop_seconds())
        if self.moment.stage != before.stage:
            self._refresh_chips()
            if self.moment.stage == EFFECT:
                self._camera_taken = False
                if not self.paused:
                    self._play_sound(self.moment.seconds)
            if before.stage == EFFECT:
                self._give_camera_back()
        if before.stage == EFFECT and self.moment.stage == EFFECT and self.moment.seconds < before.seconds:
            self._play_sound(self.moment.seconds)        # the loop came round in one tick
        if self._follow_camera():
            return                                         # drawn with the camera moved
        self.view.update()

    def _update_ticker(self) -> None:
        wanted = (self.isVisible() and self.view.scene is not None and self.places is not None
                  and not self.paused)
        if wanted and not self._ticker.isActive():
            self._ticker.start()
        elif not wanted and self._ticker.isActive():
            self._ticker.stop()

    def showEvent(self, event):                                   # noqa: N802
        super().showEvent(event)
        self._update_ticker()

    def hideEvent(self, event):                                   # noqa: N802
        super().hideEvent(event)
        self._update_ticker()
        self._stop_sound()
        self._give_camera_back()

    def _refresh_chips(self) -> None:
        colours = theme.current()
        durations = self.durations() if self.show_data is not None else {}
        for stage, chip in self.chips.items():
            on = self.moment.stage == stage and self.places is not None
            empty = durations.get(stage, 1.0) <= 0
            if on:
                style = (f"background: {colours['accent']}; color: #1b1e24; border-radius: 9px; "
                         "padding: 2px 10px; font-weight: 600;")
            else:
                style = (f"background: {colours['surface']}; color: "
                         f"{colours['text_muted'] if empty else colours['text']}; "
                         f"border: 1px solid {colours['border']}; border-radius: 9px; padding: 1px 9px;")
            chip.setStyleSheet(style)
            chip.setToolTip({CHARGING: "No charge time" if empty else "The unit charging",
                             CASTING: "The unit's animation for the ability",
                             EFFECT: "No effect" if empty else "The ability's effect",
                             PAUSE: "A moment before it starts again"}[stage])

    # -- the effect's camera --------------------------------------------------------------

    def _follow_camera(self) -> bool:
        """Puts the view's camera where the effect has it: True when the map was drawn again."""
        playback = self.playback()
        if (not self.camera_box.isChecked() or self.moment.stage != EFFECT or playback is None
                or self.moment.frame is None or self.view.scene is None or self._camera_taken):
            return False
        frame = playback.frames[self.moment.frame]
        if frame.angles is None or frame.position is None:
            return False
        camera = psx_camera(self.view.renderer, frame.angles, frame.position,
                            frame.zoom or ep.DEFAULT_ZOOM, self.view.width(), self.view.height())
        now = self.view.camera
        if self._own_camera is not None and _same_camera(camera, now):
            return False                                   # where it already is
        if self._own_camera is None:
            self._own_camera = now.copy()
        self._moving_camera = True
        try:
            self.view.camera = camera
            self.view.camera_changed.emit()
        finally:
            self._moving_camera = False
        self.view.render_now()
        return True

    def _give_camera_back(self) -> None:
        if self._own_camera is not None:
            camera, self._own_camera = self._own_camera, None
            self._moving_camera = True
            try:
                self.view.set_camera(camera)
            finally:
                self._moving_camera = False
            if self.view.isVisible():
                self.view.render_now()                     # the map and what's over it agree

    def _camera_moved(self) -> None:
        """The person turned or zoomed the map: their camera from now on, until the next effect."""
        if not self._moving_camera:
            if self._own_camera is not None:
                self._own_camera = None
            if self.moment.stage == EFFECT:
                self._camera_taken = True

    def _camera_toggled(self, on: bool) -> None:
        if not on:
            self._give_camera_back()
            self.view.update()

    # -- sound ----------------------------------------------------------------------------

    def sounds(self):
        return self.effect.get("sounds") if self.effect else None

    def _play_sound(self, seconds: float) -> None:
        sounds = self.sounds()
        if not self.sound_box.isChecked() or sounds is None or not sounds.frames:
            return
        from ... import effect_sound as es
        from ...sound_data import Pcm16
        start = int(seconds * es.RATE)
        if start >= sounds.frames:
            return
        if self._player is None:
            from ..audio_output import LoopPlayer
            self._player = LoopPlayer(self)
        self._player.play(Pcm16(es.RATE, 2, sounds.pcm), start)
        self._sounding = sounds

    def _stop_sound(self) -> None:
        if self._player is not None:
            self._player.stop()
        self._sounding = None

    def _sound_toggled(self, on: bool) -> None:
        if not on:
            self._stop_sound()
        elif self.moment.stage == EFFECT and not self.paused:
            self._play_sound(self.moment.seconds)

    # -- what is said under the map ---------------------------------------------------------

    def _update_legend(self) -> None:
        show = self.show_data
        if show is None or self.view.scene is None:
            self.legend.setVisible(False)
            return
        reach = show.reach
        if reach.self_only:
            reached = "Range: the unit itself"
        elif reach.weapon:
            reached = f"Range: the weapon's ({reach.reach} shown)"
        else:
            reached = f"Range {reach.range}"
        if "linearAttack" in reach.flags:
            area = f"Effect area: a line of {max(reach.area, reach.reach)}, vertical {reach.vertical}"
        elif reach.area >= max(self.map_size()):
            area = f"Effect area {reach.area}: the whole map, vertical {reach.vertical}"
        else:
            area = f"Effect area {reach.area}, vertical {reach.vertical}"
        parts = [f'<span style="color:{RANGE_EDGE.name()};">&#9632;</span>&nbsp;{reached}',
                 f'<span style="color:{AREA_EDGE.name()};">&#9632;</span>&nbsp;{area}']
        if show.charge_time > 0:
            parts.append(f"Charge time {show.charge_time} ({show.charge_name or show.charge_type})")
        else:
            parts.append("No charge time")
        if show.animation == ap.WEAPON_ATTACK:
            parts.append(f"Unit animation {show.animation} (the weapon's attack, shown as a sword's swing)")
        else:
            parts.append(f"Unit animation {show.animation}" +
                         (f" ({show.animation_name})" if show.animation_name else ""))
        parts.append(f"Effect {show.effect:03d}" if show.effect >= 0 else "No effect")
        self.legend.setText("&nbsp;&nbsp;&nbsp;".join(parts))
        self.legend.setVisible(True)
        self._refresh_chips()

    def notes(self) -> list:
        show = self.show_data
        if show is None or self.view.scene is None:
            return []
        notes = []
        if not self.users:
            notes.append(NOBODY)
        if show.effect < 0:
            notes.append(NO_EFFECT.format(show.effect))
        elif self.effect is not None:
            if self.effect.get("problem"):
                notes.append(self.effect["problem"])
            playback = self.effect.get("playback")
            if playback is not None and playback.callbacks:
                notes.append(CALLBACKS.format(show.effect))
            sounds = self.effect.get("sounds")
            if self.effect.get("sound_problem"):
                notes.append(NO_SOUND.format(self.effect["sound_problem"]))
            elif sounds is not None and sounds.missing:
                count = len(sounds.missing)
                notes.append(SOUND_GAPS.format(count, "" if count == 1 else "s"))
        entry = self._pictures.get(self.caster_sprite())
        cast = self.cast_id()
        if entry is not None and cast in entry["asked"] and \
                cast not in entry["animations"] and entry["animations"]:
            notes.append(NO_CAST.format(show.animation, show.animation_name or "unnamed"))
        if self.sprite_problem:
            notes.append(NO_SPRITES.format(self.sprite_problem))
        return notes

    def _say_note(self) -> None:
        notes = self.notes()
        self.note.setText(" ".join(notes))
        self.note.setVisible(bool(notes))

    # -- drawing --------------------------------------------------------------------------

    def _projection(self):
        view = self.view
        width, height = view.width(), view.height()
        proj, seen = view.renderer.matrices(view.camera, width, height)
        whole = proj * seen

        def point(world):
            v = whole.map(QVector3D(*world))
            return ((v.x() + 1) / 2 * width, (1 - v.y()) / 2 * height,
                    seen.map(QVector3D(*world)).z())
        ppu = height / max(1e-6, 2 * view.renderer.half_height(view.camera, width / max(1, height)))
        return ed.Projection(point, ppu)

    def backdrop(self, frame: Optional[int]) -> tuple:
        """The backdrop's top and bottom colours (0-1 floats): the map's, as the effect colours them."""
        if self.lights is not None:
            top = tuple(c / 255.0 for c in self.lights.background_top)
            bottom = tuple(c / 255.0 for c in self.lights.background_bottom)
        else:
            colour = QColor(theme.current()["surface_alt"])
            top = bottom = (colour.redF(), colour.greenF(), colour.blueF())
        playback = self.playback()
        if playback is not None and frame is not None:
            return playback.screen(frame, top, bottom)
        return top, bottom

    def tint(self, surface: str, frame: Optional[int]) -> Optional[tuple]:
        """`(scale, bias)` the effect colours `surface` by on `frame`, or None when it leaves it."""
        playback = self.playback()
        if playback is None or frame is None:
            return None
        scale, bias = ed.affine_of(lambda colour: playback.tint(surface, frame, colour))
        return None if ed.is_identity(scale, bias) else (scale, bias)

    def map_picture(self, frame: Optional[int]) -> QImage:
        image = self.view.image
        colours = self.tint("affected", frame)
        if colours is None:
            return image
        key = (image.cacheKey(), tuple(round(v, 3) for v in colours[0] + colours[1]))
        if self._tinted_map is None or self._tinted_map[0] != key:
            self._tinted_map = (key, ed.tint_image(image, *colours))
        return self._tinted_map[1]

    def tiles_picture(self, screen) -> QImage:
        """The range's tiles and the effect area's over them, drawn once a camera."""
        view, places = self.view, self.places
        camera = view.camera
        key = (camera.yaw, camera.pitch, camera.zoom, tuple(camera.pan), view.image.size().toTuple(),
               view.image.devicePixelRatio(), tuple(places["range"]), tuple(places["area"]),
               id(view.scene), len(view.tiles))
        if self._tiles_picture is not None and self._tiles_picture[0] == key:
            return self._tiles_picture[1]
        picture = QImage(view.image.size(), QImage.Format_ARGB32_Premultiplied)
        picture.setDevicePixelRatio(view.image.devicePixelRatio())
        picture.fill(0)
        q = QPainter(picture)
        q.setRenderHint(QPainter.Antialiasing)
        for tiles, edge, fill in ((places["range"], RANGE_EDGE, RANGE_FILL),
                                  (places["area"], AREA_EDGE, AREA_FILL)):
            path = QPainterPath()
            for x, z in tiles:
                tile = view.tile((x, z, 0))
                if tile is not None and ms.shows(tile):
                    path.addPolygon(QPolygonF([screen(c) for c in ms.tile_corners(tile, 0.4)]))
                    path.closeSubpath()
            q.setPen(QPen(edge, 1.4))
            q.setBrush(fill)
            q.drawPath(path)
        q.end()
        self._tiles_picture = (key, picture)
        return picture

    def paint_frame(self, p: QPainter) -> None:
        view = self.view
        if view.image is None or self.places is None:
            return
        moment = self.moment
        frame = moment.frame if moment.stage == EFFECT else None
        picture = QImage(view.image.size(), QImage.Format_ARGB32_Premultiplied)
        picture.setDevicePixelRatio(view.image.devicePixelRatio())
        canvas = ed.Canvas(picture, QPainter.Antialiasing)
        try:
            self._paint_on(canvas, moment, frame)
        finally:
            canvas.end()
        p.drawImage(QPointF(0, 0), picture)

    def _paint_on(self, canvas: ed.Canvas, moment: Moment, frame: Optional[int]) -> None:
        view, places = self.view, self.places
        q = canvas.painter
        width, height = view.width(), view.height()
        top, bottom = self.backdrop(frame)
        gradient = QLinearGradient(0, 0, 0, height)
        gradient.setColorAt(0.0, QColor.fromRgbF(*top))
        gradient.setColorAt(1.0, QColor.fromRgbF(*bottom))
        q.fillRect(QRectF(0, 0, width, height), gradient)
        q.drawImage(QPointF(0, 0), self.map_picture(frame))
        projection = self._projection()

        def screen(world) -> QPointF:
            x, y, _near = projection.point(world)
            return QPointF(x, y)

        q.drawImage(QPointF(0, 0), self.tiles_picture(screen))
        # The units' rings, then the units and the effect's particles, the farthest first.
        units = self.units(moment)
        for unit in units:
            ring = QColor(unit["ring"])
            ring.setAlpha(230)
            q.setPen(QPen(ring, 1.8))
            fill = QColor(unit["ring"])
            fill.setAlpha(55)
            q.setBrush(fill)
            q.drawEllipse(screen(unit["world"]), RING_W * projection.ppu, RING_H * projection.ppu)
        items = []
        for n, unit in enumerate(units):
            near = projection.point(unit["world"])[2] - 1.0
            items.append((near, (-10 ** 9, n), self._unit_drawer(unit, projection, frame)))
        playback = self.playback()
        if playback is not None and frame is not None and self.effect.get("pictures") is not None:
            items += ed.effect_items(self.effect["pictures"], playback.frames[frame], places["world"],
                                     projection)
        items.sort(key=lambda item: (item[0], item[1]))
        for _near, _order, draw in items:
            draw(canvas)

    def units(self, moment: Moment) -> list:
        """The units on the map at `moment`: the user and the stand-ins, with what each shows."""
        places, show = self.places, self.show_data
        out = []
        caster_key = self.caster_sprite()
        out.append({"key": caster_key, "tile": places["caster"], "facing": places["facing"],
                    "world": self.ground(places["caster"]), "ring": CASTER_RING, "surface": "caster",
                    "pose": self._caster_pose(moment)})
        for n, tile in enumerate(places["stand_ins"]):
            world = self.ground(tile)
            if world is None:
                continue
            index = n + (1 if places["aimed"] == places["caster"] else 0)
            out.append({"key": STAND_IN_TARGET, "tile": tile, "world": world, "ring": TARGET_RING,
                        "facing": _facing_towards(tile, places["caster"]), "surface": "target",
                        "pose": self._target_pose(moment, index)})
        return out

    def _caster_pose(self, moment: Moment) -> tuple:
        """`(animation id, seconds into it, loops)` the user shows at `moment`."""
        show = self.show_data
        key = self.caster_sprite()
        if moment.stage == CHARGING:
            ids = ap.charge_pose(show.charge_name)
            if len(ids) > 1:
                first = self.frames_of(key, ids[0])
                lasting = _seconds(first)
                if moment.seconds < lasting:
                    return (ids[0], moment.seconds, False)
                return (ids[1], moment.seconds - lasting, True)
            return (ids[0], moment.seconds, True)
        if moment.stage == CASTING:
            return (self.cast_id(), moment.seconds, False)
        if moment.stage == EFFECT:
            return (self.cast_id(), 1e9, False)
        return (ap.WALK, moment.seconds, True)

    def _target_pose(self, moment: Moment, index: int) -> tuple:
        show = self.show_data
        reaction = show.reaction if show is not None else None
        if moment.stage == EFFECT and reaction is not None and self.effect:
            frames = self.frames_of(STAND_IN_TARGET, reaction)
            lasting = _seconds(frames)
            for at in self.effect.get("hits", {}).get(index, []):
                if at <= moment.seconds < at + max(lasting, 0.3):
                    return (reaction, moment.seconds - at, False)
        return (ap.WALK, self.loop_seconds() + 0.37 * index, True)

    def _unit_drawer(self, unit: dict, projection: ed.Projection, frame: Optional[int]):
        def draw(canvas: ed.Canvas) -> None:
            self._paint_unit(canvas.painter, unit, projection, frame)
        return draw

    def _paint_unit(self, p: QPainter, unit: dict, projection: ed.Projection,
                    frame: Optional[int]) -> None:
        animation_id, seconds, loops = unit["pose"]
        frames = self.frames_of(unit["key"], animation_id) or self.frames_of(unit["key"], ap.WALK)
        if not frames:
            return
        side, mirrored = self._view_of(unit["facing"], unit["world"], projection)
        pictures = frames.get(side) or frames.get("front") or frames.get("back")
        if not pictures:
            return
        image, stand_x, stand_y, step = _picture_at(pictures, seconds, loops)
        world = _moved(unit["world"], unit["facing"], step)
        x, y, _near = projection.point(world)
        lift = 0.0
        if self.flying(unit["key"]):
            beat = self.loop_seconds()
            lift = (FLY_HEIGHT + FLY_BOB * math.sin(2 * math.pi * beat / FLY_SECONDS)) * projection.ppu
        colours = self.tint(unit["surface"], frame)
        if colours is not None:
            image = ed.tint_image(image, *colours)
        size = WORLD_PER_HD_PIXEL * projection.ppu
        left = x - ((image.width() - stand_x) if mirrored else stand_x) * size
        rect = QRectF(left, y - stand_y * size - lift, image.width() * size, image.height() * size)
        p.save()
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        if mirrored:
            p.translate(rect.center())
            p.scale(-1, 1)
            p.translate(-rect.center())
        p.drawImage(rect, image)
        p.restore()

    def _view_of(self, facing: int, world, projection: ed.Projection) -> tuple:
        """`("front" or "back", mirrored)`: which way the camera sees a unit facing `facing`."""
        dx, dz = ap.FACING_STEPS.get(facing & 3, (0, -1))
        a = projection.point(world)
        b = projection.point((world[0] - dx * 14.0, world[1], world[2] + dz * 14.0))
        across, down = b[0] - a[0], b[1] - a[1]
        return ("front" if down > 0 else "back"), across > 0


def _same_camera(a: Camera, b: Camera) -> bool:
    return (abs(a.yaw - b.yaw) < 1e-6 and abs(a.pitch - b.pitch) < 1e-6 and abs(a.zoom - b.zoom) < 1e-9
            and abs(a.pan[0] - b.pan[0]) < 1e-6 and abs(a.pan[1] - b.pan[1]) < 1e-6)


def _seconds(frames: Optional[dict]) -> float:
    if not frames or not frames.get("front"):
        return 0.0
    return sum(step.delay for _i, _x, _y, step in frames["front"]) / 60.0


def _picture_at(pictures: list, seconds: float, loops: bool) -> tuple:
    """The picture an animation shows `seconds` in: `(QImage, stand x, stand y, Step)`."""
    total = sum(step.delay for _i, _x, _y, step in pictures)
    tick = int(seconds * 60)
    if loops and total > 0:
        tick %= total
    for picture in pictures:
        if tick < picture[3].delay:
            return picture
        tick -= picture[3].delay
    return pictures[-1]


def _moved(world, facing: int, step: ap.Step) -> tuple:
    """`world` moved by an animation step: forward the way the unit faces, up, and to its right."""
    dx, dz = ap.FACING_STEPS.get(facing & 3, (0, -1))
    forward = (-dx, 0.0, dz)
    right = (-dz, 0.0, -dx)
    return (world[0] + forward[0] * step.forward + right[0] * step.right,
            world[1] + step.up,
            world[2] + forward[2] * step.forward + right[2] * step.right)


def _facing_towards(tile: tuple, other: tuple) -> int:
    """The facing (0 south, 1 west, 2 north, 3 east) from `tile` towards `other`."""
    dx, dz = other[0] - tile[0], other[1] - tile[1]
    if abs(dx) >= abs(dz):
        return 3 if dx > 0 else 1
    return 2 if dz > 0 else 0
