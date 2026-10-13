"""
Effect files: the pictures, particles, timing, camera moves, colour
flashes and sound of an ability's effect, read from the game's own files.
Asked for by Zodi on 12 October, for the Abilities page: "show the ability
effect on the map", then "Do it completly now the emitters, timing,
camera, and sound as well as everything else that is possible".

The files are `fftpack/effect/efc_eNNNdat_data.bin`, 400 of them (000 to
486 with gaps, and 509; 510 has only the code half, `effect_e510_bin.bin`),
and they are the data half of the PlayStation's `EFFECT/E###.BIN`: the
header starts at the first byte. Every section was
read against the ExMateria effects addon (timbermania, MIT, Copyright (c)
2026 timbermania - github.com/timbermania/TacticsTemplateG, branch
`pr-upstream-wip`, `addons/exmateria_effects/file_model`), which measured
them on the PlayStation game; its offsets and conversions are kept as it
gives them, and measured again here on all 400 of the game's files
(`dev/test_effect_files.py`). The playing of them is `effect_player.py`.

- **The header**: ten u32 offsets, in this order - frames, animations,
  script, particles, curves, time scale (0 when there is none), flags,
  timeline, sound and texture. Each section runs to the next one's start.
- **Frames**: framesets in groups. A byte at the start says how many
  groups; a u16 for each says where its offset table starts; the tables
  run on until an entry points below the first frameset. A frameset is
  a u16 of flags and a u16 frame count, then 24 bytes a frame: its colour
  line and depth (byte 0: palette 0-15, bit 4 the second colour block,
  bits 5-6 the blend, bit 7 eight bits a pixel), whether it is see-through
  (byte 1 bit 1), the texture page, the rectangle on the sheet (u, v,
  width, height, the last two signed when byte 1 says so: a negative one
  draws it mirrored), and the four corners in PlayStation units (top left,
  top right, bottom left, bottom right; y grows downwards).
- **Animations**: a u32 count, then u16 offsets from just after the count.
  Steps: a byte under 0x80 shows that frameset (of the emitter's group)
  for a number of 60ths of a second and at a depth; 0x81 repeats; 0x82
  sets the picture's offset (two s16); 0x83 moves it (two s8). Three zero
  bytes end one.
- **Script**: 16-bit words, the instruction in the low 9 bits. Read for
  the two things playing needs: whether it runs "for each target" (40)
  and which special drawings (callbacks, 6) it loads.
- **Particles**: a 20-byte header (gravity, the inertia threshold and how
  many emitters), then 196 bytes an emitter: where its particles appear,
  how they spread, fly, slow and home in, how long they live, how many
  appear and how often, which animation they play, and which emitter's
  particles they leave behind when they die or while they live. Lengths
  are turned into tiles (28 units a tile, y up) and angles into radians,
  as ExMateria does; inertia and weight stay as the game's numbers.
- **Curves**: a u32 count and 160 bytes each, the shape a value takes
  over time (a frame's value is byte / 255).
- **Time scale**: 600 frames of slow motion steps, two to a byte, for the
  frames before the targets and for each target.
- **Flags**: a byte (8: lift by the ground's height; 0x20 and 0x40: the
  time scale's two halves are used), and from 8 on four sound "containers".
- **Timeline**: 6,280 bytes. The particles' five lanes for the three
  parts of an effect (before the targets, for each target, after them),
  the screen's colour, the units' and map's colour, the camera's moves and
  the sound's moments - each a list of keyframes at fixed places.
- **Sound**: the effect's own sound program ("feds"), pairs of channels
  in the music files' language, played with the PlayStation's samples.
- **Texture**: two 512-byte colour blocks, a 4-byte upload header and the
  picture's pixels, 4 or 8 bits each.

Pure Python: nothing here imports Qt.
"""
from __future__ import annotations

import math
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

#: The folder, relative to the unpacked game.
EFFECT_FOLDER = "fftpack/effect"
#: The header's offsets, in their order.
SECTIONS = ("frames", "animations", "script", "particles", "curves", "time_scale",
            "flags", "timeline", "sound", "texture")
HEADER_SIZE = 40

#: Frames.
FRAME_SIZE = 24
FRAMESET_HEAD = 4
MAX_FRAMESETS = 500
MAX_FRAMES = 100
#: A frame's blend, by bits 5-6 of its first byte.
BLENDS = ("half", "add", "subtract", "quarter")
HALF, ADD, SUBTRACT, QUARTER = range(4)

#: Animations.
ANIMATION_LOOP, ANIMATION_SET_OFFSET, ANIMATION_MOVE = 0x81, 0x82, 0x83
MAX_ANIMATIONS = 256
MAX_ANIMATION_BYTES = 1000

#: Script instructions and their sizes in bytes (ExMateria's EffectReadScript).
SCRIPT_SIZES = {0: 4, 1: 4, 2: 4, 3: 2, 4: 2, 5: 2, 6: 4, 7: 4, 8: 8, 9: 2, 10: 2, 11: 8,
                12: 2, 13: 2, 14: 8, 15: 2, 16: 4, 17: 6, 18: 6, 19: 6, 20: 6, 21: 6, 22: 6,
                23: 6, 24: 6, 25: 6, 26: 4, 27: 4, 28: 6, 29: 4, 30: 4, 31: 4, 32: 2, 33: 2,
                34: 4, 35: 4, 36: 2, 37: 2, 38: 2, 39: 2, 40: 2, 41: 4, 42: 2, 43: 2, 44: 2,
                45: 2}
SCRIPT_END, SCRIPT_LOAD_CALLBACK, SCRIPT_FOR_EACH = 4, 6, 40

#: Particles.
PARTICLE_HEAD = 20
EMITTER_SIZE = 0xC4
MAX_EMITTERS = 64
#: PlayStation units a tile, and the divisors ExMateria turns the rest by.
UNITS_PER_TILE = 28.0
ACCEL_DIVISOR = 4096.0 * 28.0
RADIAL_DIVISOR = 14336.0
ANGLE_UNIT = math.tau / 4096.0
#: A lifetime of 65535 or more: the particle lives until its animation ends.
ANIMATION_DRIVEN = 65535
#: An emitter's "no child" number.
NO_CHILD = 255
#: Where an emitter's particles appear from, by bits 1-3 of byte 3.
ANCHORS = ("world", "cursor", "origin", "target", "parent", "camera", "tracked")
#: What its particles home in on, by bits 5-7 of byte 2.
HOMING_ANCHORS = ("world", "world", "camera", "origin", "target", "parent", "world", "world")
#: Which curve drives which value: (byte, shift, mask) in the eight curve bytes at 8.
CURVE_NIBBLES = {
    "position": (0, 0, 0x0F), "spread": (0, 4, 0x0F),
    "angle": (1, 0, 0x0F), "angle_spread": (1, 4, 0x0F),
    "inertia": (2, 0, 0x0F), "weight": (3, 0, 0x0F), "radial": (3, 4, 0x0F),
    "acceleration": (4, 0, 0x0F), "drag": (4, 4, 0x0F),
    "lifetime": (5, 0, 0x0F), "target_offset": (5, 4, 0x0F),
    "count": (6, 4, 0x0F), "interval": (7, 0, 0x0F),
    "homing": (7, 4, 0x03), "homing_blend": (7, 6, 0x03),
}

#: Curves.
CURVE_LENGTH = 160

#: Time scale.
TIME_SCALE_FRAMES = 600
TIME_SCALE_BYTES = 300

#: Flags.
FLAG_GROUND_HEIGHT, FLAG_SOUND_FADE = 0x08, 0x10
FLAG_TIME_SCALE_BEFORE, FLAG_TIME_SCALE_EACH = 0x20, 0x40
CONTAINERS_AT, CONTAINER_COUNT = 8, 4

#: The timeline section and its parts, as offsets from its start. "each"
#: (the part played for each target) is 8 bytes later than the table says
#: for the particles, screen and palette, and not for the camera or sound's
#: phase lanes (ExMateria's EffectBinLayout).
TIMELINE_SIZE = 6280
PHASES = ("before", "each", "after")
EACH_BIAS = 8
PARTICLE_LANES = {"each": (0x0004, 0x0084, 0x0104, 0x0184, 0x0204),
                  "before": (0x082A, 0x08AA, 0x092A, 0x09AA, 0x0A2A),
                  "after": (0x0AAA, 0x0B2A, 0x0BAA, 0x0C2A, 0x0CAA)}
PARTICLE_LANE_SIZE, PARTICLE_KEYS = 128, 25
#: Screen: (data, where its last keyframe's number is, None = at the lane's end).
SCREEN_LANES = {"each": (0x057E, 0x06A8), "before": (0x1036, None), "after": (0x13BA, None)}
SCREEN_KEYS, SCREEN_LANE_BYTES = 33, 300
#: Palette: the map and units hit, the caster, the target.
PALETTE_LANES = {"each": {"affected": 0x0326, "caster": 0x03EE, "target": 0x04B6},
                 "before": {"affected": 0x0DDE, "caster": 0x0EA6, "target": 0x0F6E},
                 "after": {"affected": 0x1162, "caster": 0x122A, "target": 0x12F2}}
PALETTE_KEYS, PALETTE_LANE_SIZE = 33, 198
#: Camera: (end frames, angles, positions, zooms, commands, last keyframe, keyframes).
CAMERA_TABLES = {"before": (0x14E6, 0x1510, 0x158E, 0x160C, 0x168A, 0x16B4, 21),
                 "each": (0x06B2, 0x06D4, 0x073A, 0x07A0, 0x0806, 0x0828, 17),
                 "after": (0x16B6, 0x16E0, 0x175E, 0x17DC, 0x185A, 0x1884, 21)}
#: A camera command: which of angle (1), position (2) and zoom (4) it moves,
#: what it moves them towards, and how.
CAMERA_SOURCES = {0x000: "target", 0x020: "offset", 0x040: "direct", 0x060: "origin",
                  0x080: "effect centre", 0x0C0: "map", 0x100: "saved", 0x140: "caster",
                  0x180: "all targets", 0x1C0: "cursor"}
CAMERA_MOVES = {0x0200: "jump", 0x0400: "ease", 0x0600: "ease", 0x0800: "straight",
                0x0A00: "ease", 0x0C00: "add", 0x0E00: "add", 0x1000: "shake fading",
                0x1200: "shake", 0x1400: "shake fading"}
#: Sound: three lanes a phase. Before and after: 9 keyframes in 30 bytes,
#: each: 17 in 54 (from the timeline's start + 8).
SOUND_LANES = {"before": (0xD2A, 0xD48, 0xD66), "after": (0xD84, 0xDA2, 0xDC0),
               "each": (0x284, 0x2BA, 0x2F0)}
SOUND_SHAPES = {"before": (9, 28), "after": (9, 28), "each": (17, 52)}
#: What a particle keyframe's action bits ask for: bits 0-2 a callback
#: slot, then the target's hit reaction, the tile refresh, the ability's
#: reaction (ExMateria's EffectManager signals).
ACTION_CALLBACK, HIT_REACTION, REFRESH_TILE, ABILITY_REACTION = 0x07, 0x10, 0x20, 0x40

#: Texture.
CLUT_BYTES = 0x200
UPLOAD_HEADER = 0x400
PIXELS_AT = 0x404


class EffectError(ValueError):
    """A file that isn't the shape this module reads."""


def effect_file_name(number: int) -> str:
    return f"efc_e{number:03d}dat_data.bin"


def effect_path(game_dir, number: int) -> Path:
    return Path(game_dir) / EFFECT_FOLDER / effect_file_name(number)


def effect_numbers(game_dir) -> list:
    """The effect numbers whose files the unpacked game has, in order."""
    folder = Path(game_dir) / EFFECT_FOLDER
    numbers = []
    if folder.is_dir():
        for path in folder.glob("efc_e*dat_data.bin"):
            digits = path.name[5:8]
            if digits.isdigit():
                numbers.append(int(digits))
    return sorted(numbers)


# =============================================================================
# The pieces
# =============================================================================

@dataclass
class Frame:
    """One quad of a frameset."""
    palette: int            # 0-15: the 16-colour line, at 4 bits a pixel
    second_clut: bool       # the second 512-byte colour block
    blend: int              # HALF, ADD, SUBTRACT or QUARTER
    eight_bit: bool
    see_through: bool       # blended by `blend`; otherwise drawn solid
    page: int               # the PlayStation texture page word
    u: int
    v: int
    width: int              # negative: drawn mirrored
    height: int
    corners: tuple          # ((x, y) top left, top right, bottom left, bottom right)


@dataclass
class Frameset:
    flags: int
    frames: list


@dataclass
class Emitter:
    """One emitter, its lengths in tiles (y up) and angles in radians."""
    index: int
    anim_index: int
    anim_param: int         # its frameset group
    motion: int             # byte 2
    anim_target: int        # byte 3
    flags_lo: int
    flags_hi: int
    curves: dict            # name -> curve number, or -1 for none
    colour_curves: tuple    # (r, g, b) curve numbers, used when colour_curve_on
    position: tuple         # (start, end), each (x, y, z)
    spread: tuple
    angle: tuple
    angle_spread: tuple
    inertia: tuple          # (min start, max start, min end, max end), the game's numbers
    weight: tuple
    radial: tuple
    acceleration: tuple     # four (x, y, z): min start, max start, min end, max end
    drag: tuple
    lifetime: tuple         # four ints, -1 = until its animation ends
    target_offset: tuple
    count: tuple            # (start, end)
    interval: tuple
    homing: tuple
    child_on_death: int     # -1 for none
    child_mid_life: int

    @property
    def align_to_velocity(self) -> bool:
        return bool(self.motion & 0x02)

    @property
    def homing_anchor(self) -> str:
        return HOMING_ANCHORS[(self.motion & 0xE0) >> 5]

    @property
    def box_spread(self) -> bool:
        return bool(self.anim_target & 0x01)

    @property
    def anchor(self) -> str:
        mode = (self.anim_target >> 1) & 0x07
        return ANCHORS[mode] if mode < len(ANCHORS) else "world"

    @property
    def colour_curve_on(self) -> bool:
        return bool(self.flags_lo & 0x40)

    @property
    def inward(self) -> bool:
        return bool(self.flags_lo & 0x10)

    @property
    def child_death_on(self) -> bool:
        return bool(self.flags_lo & 0x03)

    @property
    def child_mid_life_on(self) -> bool:
        return bool(self.flags_lo & 0x0C)

    @property
    def align_to_facing(self) -> bool:
        return bool(self.flags_hi & 0x04)

    @property
    def homing_arrival(self) -> int:
        return self.flags_hi & 0x03


@dataclass
class ParticleLane:
    index: int
    keys: list              # [(time, emitter id (0 none, n = emitter n - 1), action bits)]
    last: int               # the last keyframe used


@dataclass
class ScreenKey:
    time: int
    start: tuple            # (r, g, b) bytes: the top colour, or the blend's signed amounts
    end: tuple              # the bottom colour
    ctrl: int               # bit 7: a blend (else the colours are set); low 7: the blend mode

    @property
    def frames(self) -> int:
        return self.time * 8 if self.time > 0 else 1

    @property
    def blends(self) -> bool:
        return self.ctrl >= 128

    @property
    def mode(self) -> int:
        return self.ctrl & 0x7F


@dataclass
class ScreenLane:
    keys: list
    last: int


@dataclass
class PaletteKey:
    time: int
    rgb: tuple              # bytes, read as signed amounts
    ctrl: int               # bit 7: on; low 7: the blend mode (0-10)

    @property
    def frames(self) -> int:
        return self.time * 8 if self.time > 0 else 1

    @property
    def on(self) -> bool:
        return self.ctrl >= 128

    @property
    def mode(self) -> int:
        return self.ctrl & 0x7F


@dataclass
class PaletteLane:
    keys: list
    last: int


@dataclass
class CameraKey:
    end_frame: int
    angle: tuple            # (pitch, yaw, roll), 4096 a turn
    position: tuple         # PlayStation units, y down
    zoom: tuple             # zoom[0]: 4096 = as near as usual
    command: int

    @property
    def channels(self) -> int:
        return self.command & 0x07

    @property
    def source(self) -> str:
        return CAMERA_SOURCES.get(self.command & 0x01E0, "unknown")

    @property
    def move(self) -> str:
        return CAMERA_MOVES.get(self.command & 0x1E00, "none")


@dataclass
class CameraTable:
    keys: list
    last: int


@dataclass
class SoundLane:
    index: int
    keys: list              # [(frames, sound number)]
    last: int


@dataclass
class Timeline:
    raw_head: tuple         # the six s16 at its start
    particles: dict         # phase -> [ParticleLane]
    screen: dict            # phase -> ScreenLane
    palette: dict           # phase -> {"affected"|"caster"|"target": PaletteLane}
    camera: dict            # phase -> CameraTable
    sound: dict             # phase -> [SoundLane]

    @property
    def before_frames(self) -> int:
        """How long the part before the targets lasts (phase 1)."""
        return self.raw_head[2]

    @property
    def target_gap(self) -> int:
        """Frames between one target's part and the next (the spawn delay)."""
        return self.raw_head[3]

    @property
    def after_delay(self) -> int:
        """Frames after the first target's part starts that the after part starts."""
        return self.raw_head[5]


@dataclass
class Texture:
    cluts: bytes            # the two 512-byte colour blocks
    stride_flag: int
    size_field: int
    pixels: bytes

    def width(self, eight_bit: bool) -> int:
        row = 256 if self.stride_flag else 128
        return row if eight_bit else row * 2

    def height(self, eight_bit: bool) -> int:
        combined = self.size_field & 0xFFFF
        rows = combined >> (8 if self.stride_flag else 7)
        if rows == 0:
            row = 256 if eight_bit else 128
            rows = len(self.pixels) // row
        return rows

    def colours(self, eight_bit: bool, second_clut: bool, palette: int) -> list:
        """The 16-bit colour words a frame paints through (256 at 8 bits, else 16)."""
        base = CLUT_BYTES if second_clut else 0
        count = 256 if eight_bit else 16
        if not eight_bit:
            base += max(palette, 0) * 32
        words = []
        for i in range(count):
            at = base + 2 * i
            words.append(self.cluts[at] | (self.cluts[at + 1] << 8) if at + 2 <= len(self.cluts) else 0)
        return words


@dataclass
class EffectFile:
    number: int
    size: int
    header: tuple                       # the ten offsets
    framesets: list                     # Frameset, or None where the table's entry is no frameset
    group_sizes: list                   # framesets in each group
    animations: list                    # [[step]]: ("frame", frameset, duration, depth), ("offset", x, y), ("move", dx, dy), ("loop",)
    script: list                        # [(offset, instruction, flags, args)]
    gravity: tuple                      # tiles, y up
    inertia_threshold: int
    emitters: list
    curves: list                        # [[160 bytes]]
    time_scale: Optional[tuple]         # (before, each), 600 steps each, or None
    flags: int
    containers: list                    # [(mode, a, b, c)] x 4
    timeline: Optional[Timeline]
    feds: Optional[bytes]
    texture: Optional[Texture]

    def group_offset(self, group: int) -> int:
        """Where a frameset group starts among all the framesets."""
        if group < 0 or group >= len(self.group_sizes):
            return 0
        return sum(self.group_sizes[:group])

    @property
    def runs_for_each_target(self) -> bool:
        return any(step[1] == SCRIPT_FOR_EACH for step in self.script)

    @property
    def callbacks(self) -> list:
        """The special drawings the script loads: [(slot, callback number)]."""
        return [(flags // 2, args[0]) for _offset, op, flags, args in self.script
                if op == SCRIPT_LOAD_CALLBACK and args]

    @property
    def ground_height(self) -> bool:
        return bool(self.flags & FLAG_GROUND_HEIGHT)

    def curve(self, index: int) -> Optional[list]:
        return self.curves[index] if 0 <= index < len(self.curves) else None


# =============================================================================
# Reading
# =============================================================================

def _u16(data, at):
    return struct.unpack_from("<H", data, at)[0]


def _s16(data, at):
    return struct.unpack_from("<h", data, at)[0]


def _s16_or_zero(data, at):
    return struct.unpack_from("<h", data, at)[0] if at + 2 <= len(data) else 0


def _vec3(data, at):
    return struct.unpack_from("<3h", data, at)


def _section_end(header, index, size):
    """Where a section ends: the next section's start that comes after it."""
    start = header[index]
    later = [offset for offset in header if offset > start]
    return min(later) if later else size


def _read_frame(data, at) -> Frame:
    b0, b1, page, u, v, width, height = struct.unpack_from("<BBHBBBB", data, at)
    if b1 & 0x10 and width > 127:
        width -= 256
    if b1 & 0x20 and height > 127:
        height -= 256
    xy = struct.unpack_from("<8h", data, at + 8)
    corners = ((xy[0], xy[1]), (xy[2], xy[3]), (xy[4], xy[5]), (xy[6], xy[7]))
    return Frame(b0 & 0x0F, bool(b0 & 0x10), (b0 >> 5) & 0x03, bool(b0 & 0x80),
                 bool(b1 & 0x02), page, u, v, width, height, corners)


def _read_frames(data, start, end) -> tuple:
    size = min(end, len(data)) - start
    if start <= 0 or size < 8:
        return [], []
    groups = data[start]
    table = 4 + 2 * groups
    if table >= size:
        return [], []
    group_starts = [_u16(data, start + 4 + 2 * g) for g in range(groups)]
    first = _u16(data, start + table)
    most = (first + 4 - table) // 2
    if most <= 0 or most > MAX_FRAMESETS:
        return [], []
    group_sizes = []
    for g in range(groups):
        stop = group_starts[g + 1] if g + 1 < groups else first
        group_sizes.append((stop - group_starts[g]) // 2)
    offsets = []
    for i in range(most):
        at = start + table + 2 * i
        if at + 2 > start + size:
            break
        value = _u16(data, at)
        if value < first:
            break
        offsets.append(value)
    framesets = []
    for value in offsets:
        at = start + value + 4
        if at + FRAMESET_HEAD > len(data):
            framesets.append(None)
            continue
        flags, count = struct.unpack_from("<HH", data, at)
        if count <= 0 or count > MAX_FRAMES:
            framesets.append(None)
            continue
        frames = []
        for f in range(count):
            frame_at = at + FRAMESET_HEAD + f * FRAME_SIZE
            if frame_at + FRAME_SIZE > len(data):
                break
            frames.append(_read_frame(data, frame_at))
        framesets.append(Frameset(flags, frames))
    return framesets, group_sizes


def _read_animation(data, at) -> list:
    steps = []
    stop = min(at + MAX_ANIMATION_BYTES, len(data))
    while at < stop:
        op = data[at]
        if op <= 0x7F:
            if at + 3 > stop:
                break
            duration, depth = data[at + 1], data[at + 2]
            steps.append(("frame", op, duration, depth))
            at += 3
            if op == 0 and duration == 0 and depth == 0:
                break
        elif op == ANIMATION_LOOP:
            steps.append(("loop",))
            break
        elif op == ANIMATION_SET_OFFSET:
            if at + 5 > stop:
                break
            steps.append(("offset", _s16(data, at + 1), _s16(data, at + 3)))
            at += 5
        elif op == ANIMATION_MOVE:
            if at + 3 > stop:
                break
            dx, dy = struct.unpack_from("<bb", data, at + 1)
            steps.append(("move", dx, dy))
            at += 3
        else:
            break
    return steps


def _read_animations(data, start, end) -> list:
    if start <= 0 or start + 4 > len(data) or min(end, len(data)) - start < 4:
        return []
    count = struct.unpack_from("<I", data, start)[0]
    if count == 0 or count > MAX_ANIMATIONS:
        return []
    out = []
    for i in range(count):
        at = start + 4 + 2 * i
        if at + 2 > end:
            break
        begin = start + 4 + _u16(data, at)
        if begin >= len(data):
            break
        out.append(_read_animation(data, begin))
    return out


def _read_script(data, start, end) -> list:
    out = []
    at = start
    while 0 < at < min(end, len(data)) - 1:
        word = _u16(data, at)
        op, flags = word & 0x1FF, (word >> 9) & 0x7F
        size = SCRIPT_SIZES.get(op, 2)
        args = tuple(_s16(data, at + 2 + 2 * k) for k in range((size - 2) // 2)
                     if at + 4 + 2 * k <= len(data))
        out.append((at - start, op, flags, args))
        at += size
        if op == SCRIPT_END:
            break
    return out


def _tiles(xyz) -> tuple:
    return (xyz[0] / UNITS_PER_TILE, -xyz[1] / UNITS_PER_TILE, xyz[2] / UNITS_PER_TILE)


def _accel(xyz) -> tuple:
    return (xyz[0] / ACCEL_DIVISOR, -xyz[1] / ACCEL_DIVISOR, xyz[2] / ACCEL_DIVISOR)


def _angles(xyz) -> tuple:
    return tuple(value * ANGLE_UNIT for value in xyz)


def _read_emitter(data, at, index) -> Emitter:
    curve_bytes = data[at + 8:at + 16]
    curves = {}
    for name, (byte, shift, mask) in CURVE_NIBBLES.items():
        raw = (curve_bytes[byte] >> shift) & mask
        curves[name] = raw - 1 if raw > 0 else -1

    def vec(offset):
        return _vec3(data, at + offset)

    def spaced(a, b, c):
        return (_s16(data, at + a), _s16(data, at + b), _s16(data, at + c))

    def four(first):
        return struct.unpack_from("<4h", data, at + first)

    lifetime = tuple(-1 if value >= ANIMATION_DRIVEN else value
                     for value in struct.unpack_from("<4H", data, at + 0x94))
    child_death, child_mid = data[at + 0xC0], data[at + 0xC1]
    return Emitter(
        index=index, anim_index=data[at + 1], anim_param=data[at + 4],
        motion=data[at + 2], anim_target=data[at + 3],
        flags_lo=data[at + 6], flags_hi=data[at + 7], curves=curves,
        colour_curves=(data[at + 0x10] & 0x0F, data[at + 0x10] >> 4, data[at + 0x11] & 0x0F),
        position=(_tiles(vec(0x14)), _tiles(vec(0x1A))),
        spread=(_tiles(vec(0x20)), _tiles(vec(0x26))),
        angle=(_angles(vec(0x2C)), _angles(vec(0x32))),
        angle_spread=(_angles(vec(0x38)), _angles(vec(0x3E))),
        inertia=four(0x44), weight=four(0x54),
        radial=tuple(value / RADIAL_DIVISOR for value in four(0x5C)),
        acceleration=(_accel(spaced(0x64, 0x68, 0x6C)), _accel(spaced(0x66, 0x6A, 0x6E)),
                      _accel(spaced(0x70, 0x74, 0x78)), _accel(spaced(0x72, 0x76, 0x7A))),
        drag=(_accel(spaced(0x7C, 0x80, 0x84)), _accel(spaced(0x7E, 0x82, 0x86)),
              _accel(spaced(0x88, 0x8C, 0x90)), _accel(spaced(0x8A, 0x8E, 0x92))),
        lifetime=lifetime,
        target_offset=(_tiles(vec(0x9C)), _tiles(vec(0xA2))),
        count=struct.unpack_from("<2H", data, at + 0xB0),
        interval=struct.unpack_from("<2H", data, at + 0xB4),
        homing=tuple(value / ACCEL_DIVISOR for value in four(0xB8)),
        child_on_death=-1 if child_death >= NO_CHILD else child_death,
        child_mid_life=-1 if child_mid >= NO_CHILD else child_mid)


def _read_particles(data, start) -> tuple:
    if start <= 0 or start + PARTICLE_HEAD > len(data):
        return (0.0, 0.0, 0.0), 512, []
    count = _u16(data, start + 2)
    gravity = _accel(struct.unpack_from("<3i", data, start + 4))
    threshold = struct.unpack_from("<I", data, start + 0x10)[0]
    if count > MAX_EMITTERS or start + PARTICLE_HEAD + count * EMITTER_SIZE > len(data):
        return gravity, threshold, []
    emitters = [_read_emitter(data, start + PARTICLE_HEAD + i * EMITTER_SIZE, i)
                for i in range(count)]
    return gravity, threshold, emitters


def _read_curves(data, start, end) -> list:
    if start <= 0 or start + 4 > len(data) or end - start < 4:
        return []
    count = struct.unpack_from("<I", data, start)[0]
    out = []
    for i in range(count):
        at = start + 4 + i * CURVE_LENGTH
        if at + CURVE_LENGTH > len(data):
            break
        out.append(list(data[at:at + CURVE_LENGTH]))
    return out


def _read_time_scale(data, start) -> Optional[tuple]:
    if start <= 0 or start + 2 * TIME_SCALE_BYTES > len(data):
        return None

    def region(at):
        return [(data[at + (f >> 1)] >> (4 * (f & 1))) & 0x0F for f in range(TIME_SCALE_FRAMES)]
    return region(start), region(start + TIME_SCALE_BYTES)


def _read_timeline(data, start) -> Optional[Timeline]:
    if start <= 0 or start + TIMELINE_SIZE > len(data):
        return None
    head = struct.unpack_from("<6h", data, start)

    particles = {}
    for phase, lanes in PARTICLE_LANES.items():
        base = start + (EACH_BIAS if phase == "each" else 0)
        particles[phase] = []
        for index, offset in enumerate(lanes):
            at = base + offset
            keys = [(_s16(data, at + 2 * k), data[at + 0x31 + k], _u16(data, at + 0x4A + 2 * k))
                    for k in range(PARTICLE_KEYS)]
            particles[phase].append(ParticleLane(index, keys, _s16(data, at + 0x7E)))

    screen = {}
    for phase, (offset, last_at) in SCREEN_LANES.items():
        base = start + (EACH_BIAS if phase == "each" else 0)
        at = base + offset
        keys = [ScreenKey(_s16(data, at + 2 * k), tuple(data[at + 0x42 + 3 * k:at + 0x45 + 3 * k]),
                          tuple(data[at + 0xA5 + 3 * k:at + 0xA8 + 3 * k]), data[at + 0x108 + k])
                for k in range(SCREEN_KEYS)]
        last = _s16(data, base + last_at if last_at is not None else at + 298)
        screen[phase] = ScreenLane(keys, last)

    palette = {}
    for phase, lanes in PALETTE_LANES.items():
        base = start + (EACH_BIAS if phase == "each" else 0)
        palette[phase] = {}
        for name, offset in lanes.items():
            at = base + offset
            last = _s16(data, at + PALETTE_LANE_SIZE)
            if last < 0 or last >= PALETTE_KEYS:
                last = 0
            keys = [PaletteKey(_s16(data, at + 2 * k), tuple(data[at + 0x42 + 3 * k:at + 0x45 + 3 * k]),
                               data[at + 0xA5 + k]) for k in range(PALETTE_KEYS)]
            palette[phase][name] = PaletteLane(keys, last)

    camera = {}
    for phase, (ends, angles, positions, zooms, commands, last_at, count) in CAMERA_TABLES.items():
        last = _s16_or_zero(data, start + last_at)
        if last < 0 or last >= count:
            last = 0
        keys = []
        for k in range(count):
            keys.append(CameraKey(_s16_or_zero(data, start + ends + 2 * k),
                                  _vec3(data, start + angles + 6 * k),
                                  _vec3(data, start + positions + 6 * k),
                                  _vec3(data, start + zooms + 6 * k),
                                  _u16(data, start + commands + 2 * k)))
        camera[phase] = CameraTable(keys, last)

    sound = {}
    for phase, lanes in SOUND_LANES.items():
        base = start + (EACH_BIAS if phase == "each" else 0)
        count, last_at = SOUND_SHAPES[phase]
        sound[phase] = []
        for index, offset in enumerate(lanes):
            at = base + offset
            keys = [(_s16(data, at + 2 * k), data[at + 2 * count + k]) for k in range(count)]
            sound[phase].append(SoundLane(index, keys, _s16(data, at + last_at)))

    return Timeline(head, particles, screen, palette, camera, sound)


def _read_texture(data, start) -> Optional[Texture]:
    if start <= 0 or start + PIXELS_AT > len(data):
        return None
    size_field = data[start + UPLOAD_HEADER] | (data[start + UPLOAD_HEADER + 1] << 8) | \
        (data[start + UPLOAD_HEADER + 2] << 16)
    return Texture(bytes(data[start:start + 2 * CLUT_BYTES]), data[start + 0x403], size_field,
                   bytes(data[start + PIXELS_AT:]))


def read_effect(data: bytes, number: int = -1) -> EffectFile:
    """Reads one `efc_eNNNdat_data.bin`. Raises EffectError when it isn't one."""
    data = bytes(data)
    if len(data) < HEADER_SIZE:
        raise EffectError("it is too short to be an effect file")
    header = struct.unpack_from("<10I", data, 0)
    frames_at, animations_at, script_at, particles_at, curves_at, time_scale_at, \
        flags_at, timeline_at, sound_at, texture_at = header
    if frames_at != HEADER_SIZE or not all(o == 0 or HEADER_SIZE <= o <= len(data) for o in header):
        raise EffectError("its header doesn't point inside it the way an effect file's does")
    size = len(data)
    framesets, group_sizes = _read_frames(data, frames_at, _section_end(header, 0, size))
    animations = _read_animations(data, animations_at, _section_end(header, 1, size))
    script = _read_script(data, script_at, _section_end(header, 2, size))
    gravity, threshold, emitters = _read_particles(data, particles_at)
    curves = _read_curves(data, curves_at, _section_end(header, 4, size))
    time_scale = _read_time_scale(data, time_scale_at)
    flags = data[flags_at] if 0 < flags_at < size else 0
    containers = []
    for c in range(CONTAINER_COUNT):
        at = flags_at + CONTAINERS_AT + 4 * c
        containers.append(tuple(data[at:at + 4]) if 0 < flags_at and at + 4 <= size else (0, 0, 0, 0))
    timeline = _read_timeline(data, timeline_at)
    feds = None
    if 0 < sound_at < texture_at <= size and data[sound_at:sound_at + 4] == b"feds":
        feds = data[sound_at:texture_at]
    texture = _read_texture(data, texture_at)
    return EffectFile(number, size, header, framesets, group_sizes, animations, script,
                      gravity, threshold, emitters, curves, time_scale, flags, containers,
                      timeline, feds, texture)


def load_effect(game_dir, number: int) -> EffectFile:
    path = effect_path(game_dir, number)
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise EffectError(f"{path.name} couldn't be read: {exc}") from exc
    return read_effect(data, number)


# =============================================================================
# The texture as colours
# =============================================================================

#: A texel's kind, as the PlayStation draws it: not at all (colour word 0),
#: solid (the word's top bit clear), or blended when its quad is see-through
#: (top bit set; drawn solid otherwise).
CLEAR, SOLID, BLENDED = 0, 1, 2


def colour_of(word: int) -> tuple:
    """A 15-bit colour word as 8-bit (r, g, b), each 5 bits widened."""
    def widen(v):
        return (v << 3) | (v >> 2)
    return widen(word & 0x1F), widen((word >> 5) & 0x1F), widen((word >> 10) & 0x1F)


def sheet_texels(texture: Texture, eight_bit: bool) -> tuple:
    """`(width, height, indices)`: the sheet's colour numbers, row by row."""
    width, height = texture.width(eight_bit), texture.height(eight_bit)
    pixels = texture.pixels
    if eight_bit:
        indices = bytearray(pixels[:width * height])
    else:
        indices = bytearray(2 * min(len(pixels), width * height // 2))
        for i, byte in enumerate(pixels[:width * height // 2]):
            indices[2 * i] = byte & 0x0F
            indices[2 * i + 1] = byte >> 4
    indices.extend(bytes(width * height - len(indices)))
    return width, height, bytes(indices)


def sheet_rgba(texture: Texture, eight_bit: bool, second_clut: bool, palette: int) -> tuple:
    """
    `(width, height, rgba, kinds)`: the sheet in one colour line, as RGBA
    bytes (alpha 0 where nothing is drawn, else 255), and each texel's kind
    (CLEAR, SOLID or BLENDED).
    """
    width, height, indices = sheet_texels(texture, eight_bit)
    words = texture.colours(eight_bit, second_clut, palette)
    lookup = []
    kinds_of = []
    for word in words:
        r, g, b = colour_of(word)
        if word == 0:
            lookup.append(b"\0\0\0\0")
            kinds_of.append(CLEAR)
        else:
            lookup.append(bytes((r, g, b, 255)))
            kinds_of.append(BLENDED if word & 0x8000 else SOLID)
    mask = len(words) - 1
    rgba = b"".join(lookup[i & mask] for i in indices)
    kinds = bytes(kinds_of[i & mask] for i in indices)
    return width, height, rgba, kinds


def frame_uv(frame: Frame, texture: Optional[Texture] = None) -> tuple:
    """
    `(u, v, width, height)` on the decoded sheet. A frame's page says which
    128-byte column of the sheet's VRAM upload (at x 384) it reads: at 8
    bits a pixel the sheet's second column starts at texel 128.
    """
    u = frame.u
    if texture is not None and frame.eight_bit and texture.stride_flag:
        column = (frame.page & 0x0F) - 6
        if column > 0:
            u += 128 * column
    v = frame.v + (256 if frame.page & 0x10 else 0)
    return u, v, frame.width, frame.height
