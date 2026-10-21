"""
Unit sprites: the pictures The Ivalice Chronicles draws a unit with on the
battlefield, ready for a page to paint. Asked for by Zodi on 12 October,
for the Encounters page's map: "correctly draw the sprites of the units and
correctly draw their idle walking or floating in place animations".

Where each piece comes from, measured on the game's own files (12 October
2026):

- **The HD sheets** are in `system/ffto/g2d.dat`, which starts "YOX": a
  u32 at 8 says where its index is and a u32 at 12 how many entries it has;
  an entry is 16 bytes (a u32 offset, a 3 byte size, then 6 and zeros), and
  at each offset 16 bytes more ("YOX", a u32 that is 2 when the data is zlib
  packed and 0 when not, a u32 of its size unpacked, and 0) come before the
  data. A character's sheets are 4 bits a pixel, 512 pixels wide, the left
  pixel in the low 4 bits: one of 512 rows, and its other rows in the next
  entry. Zodi's `extract_g2d.py` reads them the same way.
- **They are the PlayStation sheets drawn at twice the size**, colour
  numbers and all: over the first 256 rows, 60 to 88 percent of each
  classic sprite's coloured pixels have the same colour number at the same
  place in its HD sheet, scaled down, against under 25 percent for any other
  sprite's sheet (`dev/make_unit_sprites.py` measures it). So the classic
  palettes colour them, and the classic frame layouts cut them at twice the
  scale.
- **The palettes** are the first 512 bytes of the classic sprite file,
  `fftpack/unit/battle_<name>_spr.bin`: 16 palettes of 16 colours, 5 bits
  each, red lowest. As on the PlayStation, a colour whose 16 bits are all 0
  is see-through.
- **Frames** (`fftpack/unit/battle_<kind>_shp.bin`) and **animations**
  (`battle_<kind>_seq.bin`) are the PlayStation's files byte for byte, the
  same bytes FFTPatcher ships, and are read as FFTPatcher's
  ShishiSpriteEditor reads them (Glain and the FFTPatcher contributors,
  GPL-3, github.com/Glain/FFTPatcher: `Shape.cs`, `Frame.cs`, `Tile.cs`,
  `Sequence.cs`). A frame is a list of tiles, each a rectangle of the sheet
  placed relative to where the unit stands, drawn last first; an animation
  is a list of frames, each held for a number of 60ths of a second.
- **Which frames and animations a sprite uses, and whether it flies**: 4
  bytes a sprite at 0x2D748 of `fftpack/battle_bin.en.bin`, the
  PlayStation's BATTLE.BIN (ShishiSpriteEditor's `AllSpriteAttributes`).
  The animation byte does not number the files the way the frame byte
  does: its 1 is TYPE3's animations, not TYPE2's (`SEQUENCE_KINDS`;
  TacticsEngineG's `spr.gd` says so, and its list calls TYPE2's unused).
  The 66 sprites with TYPE2 frames have it, and TYPE2's animations show
  them turning their backs while they charge a spell (Zodi, 18 October).
- **Which file and which sheets each sprite number uses**:
  `data/UnitSprites.txt`, made by `dev/make_unit_sprites.py` (the sprite
  table in the same BATTLE.BIN points at the files by PlayStation disc
  position, and FFTPatcher's PlayStation file list names them).
- **Which sprite a unit uses**: an ENTD sprite set of 1 to 127 is that
  sprite. 128 and 129 (a generic man or woman) take their job's: 96 + 2 x
  (job - 74) for the jobs 74 to 90, one more for a woman, then the Bard (91)
  130, the Dancer (92) 131 and the Mime (93) 132 and 133, which is the order
  of the jobs' own files in the sprite table. 130 (a monster) takes its
  job's `MonsterGraphic`: sprite 133 + it, coloured by its `MonsterPalette`.

A unit waiting on the battlefield walks in place: animation 6 seen from the
front, 7 from behind, both facing left; facing right is the same picture
mirrored.

**An event's own animations** (Dycedarg sitting in his chair in event 045,
Zodi, 19 October: "you have my ok"): the PlayStation's EVTCHR.BIN, the
remaster's `fftpack/event_evtchr_bin.bin`, is blocks of 0x7800 bytes, laid
out as the decompilation's `evtchr_file_record_t` (`include/fft/gfx.h`): 64
sequence offsets (s32, -1 the start) and 0x400 bytes of sequences, 40 frame
offsets and 0x1E0 bytes of frames, 16 palettes, and a 256 by 200 picture at
4 bits. An event loads a block into one of two slots (`event_scripts`); an
animation from 500 is sequence n of slot 0's block (500 + n), from 600 slot
1's, the same from the front and behind (`animation.h`); a frame from 210
(`SPRITE_SHP_FRAME_EVTCHR_FIRST`) is the block's frame less 210, cut from its
picture, one below it the unit's own (`sprite_frame_select_unit_shp`), and
both are coloured with the unit's palette (`sprite_frame_load_parts`). The
HD pictures are g2d.dat entries 512 wide, the blocks' pictures at twice the
size colour for colour; which is which block's is `data/EvtchrSheets.txt`,
measured by `dev/make_evtchr_sheets.py`.

Pure Python (zlib and struct): nothing here imports Qt, numpy or Pillow.
"""
from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import paths

#: The files, relative to the unpacked game.
G2D_FILE = "system/ffto/g2d.dat"
UNIT_FOLDER = "fftpack/unit"
BATTLE_BIN = "fftpack/battle_bin.en.bin"
#: Each sprite's frame kind, animation kind, whether it flies, its height.
ATTRIBUTES_AT = 0x2D748
ATTRIBUTE_COUNT = 159
#: The frame kinds, in the order the attribute bytes number them (ShishiSpriteEditor's `SpriteType`).
KINDS = ("type1", "type2", "cyoko", "mon", "other", "ruka", "arute", "kanzen")
#: The animation kinds, in the order the attribute bytes number them: TYPE2's
#: frames play TYPE3's animations (see the module's notes).
SEQUENCE_KINDS = ("type1", "type3", "cyoko", "mon", "other", "ruka", "arute", "kanzen")
#: RUKA has animations of its own and no frames: ShishiSpriteEditor cuts it with MON's.
SHAPE_OF = {"ruka": "mon"}

#: The idle animations: walking, from the front and from behind.
WALK_FRONT, WALK_BACK = 6, 7
#: HD pixels to a PlayStation pixel.
SCALE = 2
#: Where the unit stands within a frame, in PlayStation pixels: a tile's
#: place is relative to this (ShishiSpriteEditor's `Location = x + 53, y + 118`).
STAND_X, STAND_Y = 53, 118
#: A character sheet's width in pixels.
SHEET_WIDTH = 512

#: A tile's size, by the four bits at 10 of its flags (`Tile.cs`).
TILE_SIZES = ((8, 8), (16, 8), (16, 16), (16, 24), (24, 8), (24, 16), (24, 24), (32, 8),
              (32, 16), (32, 24), (32, 32), (32, 40), (48, 16), (40, 32), (48, 48), (56, 56))
#: An animation's instructions (`0xFF` and a code) and how many bytes follow
#: each, beyond its own two (`Sequence.Jumps`). The rest take none. 0xC4
#: (where a unit holds an item: 2) and 0xFD (holding a weapon: 1) are from
#: TacticsEngineG's `opcodeParameters.txt`: without them the two bytes of an
#: item's place were read as a frame (in MON's item use, frame 0 for 216 60ths).
SEQUENCE_ARGUMENTS = {192: 1, 198: 1, 211: 1, 212: 1, 214: 1, 215: 1, 216: 1, 226: 1, 238: 1,
                      239: 1, 240: 1, 246: 1, 253: 1, 193: 2, 196: 2, 217: 2, 242: 2, 252: 2, 250: 3}

#: The ENTD sprite sets that take their sprite from the job.
GENERIC_MAN, GENERIC_WOMAN, GENERIC_MONSTER = 128, 129, 130
#: The jobs whose units wear a generic sprite, and where theirs start.
FIRST_GENERIC_JOB, LAST_PAIRED_JOB, FIRST_GENERIC_SPRITE = 74, 90, 96
#: The three generic jobs after them: the Bard (men only), the Dancer
#: (women only) and the Mime (both).
LATE_JOBS = {(91, 0): 130, (92, 1): 131, (93, 0): 132, (93, 1): 133}
#: A monster's sprite is this plus its job's `MonsterGraphic`.
MONSTER_SPRITE_BASE = 133

#: Where the bundled table lives, and its name.
TABLE_NAME = "UnitSprites.txt"

#: The event animations' file, a block's size, where its parts are, and the
#: first frame and animation numbers that are a slot's (see the module's notes).
EVTCHR_FILE = "fftpack/event_evtchr_bin.bin"
EVTCHR_BLOCK = 0x7800
EVTCHR_SEQUENCES_AT, EVTCHR_SEQUENCE_BYTES = 0x100, 0x400
EVTCHR_FRAMES_AT, EVTCHR_FRAME_OFFSETS, EVTCHR_FRAME_BYTES = 0x5A0, 40, 0x1E0
EVTCHR_PALETTES_AT, EVTCHR_PIXELS_AT = 0x780, 0x980
EVTCHR_WIDTH, EVTCHR_HEIGHT = 256, 200
EVTCHR_FRAME_FIRST = 210
EVTCHR_SLOT_ANIMATIONS = (500, 600)
#: The instruction a block's sequence ends with (0xFF 0xFF): of the game's
#: 5,091, 4,933 end at it with the next right after, a block's last (143)
#: have only zeros after it, and the other 15 loop (0xFF 0xD5) or run on to
#: the next one.
EVTCHR_END = 0xFF
EVTCHR_TABLE_NAME = "EvtchrSheets.txt"


class SpriteError(ValueError):
    """A file that isn't the shape this module reads."""


# =============================================================================
# g2d.dat
# =============================================================================

class G2d:
    """The HD sheets file, its index read once and its entries on demand."""

    def __init__(self, path):
        self.path = Path(path)
        with self.path.open("rb") as handle:
            head = handle.read(16)
            if len(head) < 16 or head[:3] != b"YOX":
                raise SpriteError(f"{self.path.name} doesn't start with YOX")
            at, count = struct.unpack_from("<II", head, 8)
            handle.seek(at)
            index = handle.read(16 * count)
        if len(index) < 16 * count:
            raise SpriteError(f"{self.path.name}'s index runs past its end")
        #: `[(offset, size)]`, one per entry.
        self.entries = [(struct.unpack_from("<I", index, 16 * i)[0],
                         int.from_bytes(index[16 * i + 4:16 * i + 7], "little"))
                        for i in range(count)]

    def __len__(self) -> int:
        return len(self.entries)

    def entry(self, number: int) -> Optional[bytes]:
        """Entry `number`'s data, unpacked; None for no such entry or one that can't be read."""
        if not 0 <= number < len(self.entries):
            return None
        offset, size = self.entries[number]
        if size < 16:
            return None
        with self.path.open("rb") as handle:
            handle.seek(offset)
            raw = handle.read(size)
        if len(raw) < size or raw[:3] != b"YOX":
            return None
        packed, unpacked = struct.unpack_from("<II", raw, 4)
        body = raw[16:]
        if packed == 2:
            try:
                body = zlib.decompress(body)
            except zlib.error:
                return None
        return body if not unpacked or len(body) == unpacked else None


# =============================================================================
# Sheets and palettes
# =============================================================================

#: A byte's two pixels, low 4 bits first.
_LOW = bytes(b & 0x0F for b in range(256))
_HIGH = bytes(b >> 4 for b in range(256))


def colour_numbers(data: bytes) -> bytearray:
    """4 bits a pixel to a byte a pixel, the low 4 bits of each byte first."""
    out = bytearray(len(data) * 2)
    out[0::2] = data.translate(_LOW)
    out[1::2] = data.translate(_HIGH)
    return out


@dataclass
class Sheet:
    """A sprite's sheets, one above the other, as a colour number a pixel."""
    width: int
    height: int
    pixels: bytearray

    def row(self, y: int, x: int, width: int) -> bytes:
        """`width` pixels of row `y` from `x`, 0 (see-through) beyond the sheet."""
        if not 0 <= y < self.height:
            return bytes(width)
        start = y * self.width
        inside = bytes(self.pixels[start + max(0, x): start + min(self.width, x + width)])
        return bytes(max(0, -x)) + inside + bytes(width - max(0, -x) - len(inside))


def join_sheets(parts) -> Optional[Sheet]:
    """Sheets of 4 bits a pixel, `SHEET_WIDTH` wide, one above the other."""
    rows = bytearray()
    for data in parts:
        if not data:
            return None
        rows += colour_numbers(data)
    if not rows:
        return None
    return Sheet(SHEET_WIDTH, len(rows) // SHEET_WIDTH, rows)


def read_palettes(sprite_file: bytes) -> list:
    """The 16 palettes at a classic sprite's start: each 16 colours, as their 16 bit values."""
    if len(sprite_file) < 512:
        raise SpriteError(f"a sprite file starts with 512 bytes of palettes; this is {len(sprite_file)}")
    values = struct.unpack_from("<256H", sprite_file, 0)
    return [list(values[16 * p:16 * p + 16]) for p in range(16)]


def is_blank(palette) -> bool:
    """Whether a palette is every colour see-through: a slot the sprite doesn't fill."""
    return not any(palette)


def rgba(value: int) -> tuple:
    """A 16 bit colour as red, green, blue and opacity, 0 to 255. A value of 0 is see-through."""
    if not value:
        return (0, 0, 0, 0)
    r, g, b = value & 31, (value >> 5) & 31, (value >> 10) & 31
    return ((r << 3) | (r >> 2), (g << 3) | (g >> 2), (b << 3) | (b >> 2), 255)


# =============================================================================
# Frames (SHP) and animations (SEQ)
# =============================================================================

@dataclass(frozen=True)
class Tile:
    """A rectangle of the sheet drawn at a place: PlayStation pixels."""
    x: int          # where its left edge goes, from where the unit stands
    y: int          # ...and its top
    sheet_x: int
    sheet_y: int
    width: int
    height: int
    flip_x: bool
    flip_y: bool


def _frame_at(data: bytes, at: int, second_half: bool) -> list:
    if at + 2 > len(data):
        raise SpriteError("a frame starts past the end of its file")
    count = data[at] | (data[at + 1] << 8)
    tiles = []
    for i in range(count + 1):
        o = at + 2 + 4 * i
        if o + 4 > len(data):
            raise SpriteError("a frame's tiles run past the end of its file")
        x, y = struct.unpack_from("<bb", data, o)
        flags = data[o + 2] | (data[o + 3] << 8)
        width, height = TILE_SIZES[(flags >> 10) & 0x0F]
        tiles.append(Tile(x, y, (flags & 0x1F) * 8, ((flags >> 5) & 0x1F) * 8 + (256 if second_half else 0),
                          width, height, bool(flags & 0x4000), bool(flags & 0x8000)))
    tiles.reverse()          # drawn last first: the file's first tile ends on top
    return tiles


def read_shape(data: bytes) -> list:
    """
    A shape file's frames, each `[Tile]` in drawing order (`Shape.cs`).

    A u32 at 0 says where a second list of frames starts (8 or less: none),
    and the u16 at 4 from which frame on the tiles come from the sheet's
    lower 256 rows. The first list's offsets are u32s from 0x0C up to a 0,
    frames at 0x40A plus each, the first at 0x40A itself; the second's from
    the second list's start + 4, frames at that start + 0x402 plus each.
    """
    if len(data) < 0x40C:
        raise SpriteError("a shape file is at least 0x40C bytes")
    jump = struct.unpack_from("<I", data, 0)[0]
    second = data[4] | (data[5] << 8)

    def offsets(at):
        found = [0]
        while at + 4 <= len(data):
            value = struct.unpack_from("<I", data, at)[0]
            if not value:
                break
            found.append(value)
            at += 4
        return found

    frames = [_frame_at(data, 0x40A + o, n >= second) for n, o in enumerate(offsets(0x0C))]
    if jump > 8:
        frames += [_frame_at(data, jump + 0x402 + o, n >= second)
                   for n, o in enumerate(offsets(jump + 4))]
    return frames


def read_sequences(data: bytes) -> list:
    """
    A sequence file's animations (`Sequence.cs`): each a list of
    `(frame, 60ths of a second)` and `("op", code, arguments)` steps.

    Up to 256 u32 offsets from 4, ending at 0xFFFFFFFF; each animation runs
    from 0x406 plus its offset to the next one's. A step is two bytes, a
    frame and how long it shows, or `0xFF` and an instruction, some of which
    take the bytes after them (`SEQUENCE_ARGUMENTS`).
    """
    if len(data) < 0x406:
        raise SpriteError("a sequence file is at least 0x406 bytes")
    offsets = []
    for i in range(256):
        value = struct.unpack_from("<I", data, 4 + 4 * i)[0]
        if value == 0xFFFFFFFF:
            break
        offsets.append(value)
    animations = []
    for n, start in enumerate(offsets):
        end = offsets[n + 1] if n + 1 < len(offsets) else len(data) - 0x406
        raw = data[0x406 + start:0x406 + max(start, end)]
        steps, i = [], 0
        while i < len(raw) - 1:
            if raw[i] != 0xFF:
                steps.append((raw[i], raw[i + 1]))
                i += 2
            else:
                code = raw[i + 1]
                extra = SEQUENCE_ARGUMENTS.get(code, 0)
                steps.append(("op", code, tuple(raw[i + 2:i + 2 + extra])))
                i += 2 + extra
        animations.append(steps)
    return animations


def frames_of(animation) -> list:
    """An animation's frames: `[(frame, 60ths of a second)]`, its instructions left out."""
    return [step for step in animation if step[0] != "op"]


def _steps(raw: bytes) -> list:
    """A sequence's bytes as `read_sequences` steps."""
    steps, i = [], 0
    while i < len(raw) - 1:
        if raw[i] != 0xFF:
            steps.append((raw[i], raw[i + 1]))
            i += 2
        else:
            code = raw[i + 1]
            extra = SEQUENCE_ARGUMENTS.get(code, 0)
            steps.append(("op", code, tuple(raw[i + 2:i + 2 + extra])))
            i += 2 + extra
    return steps


@dataclass
class Evtchr:
    """One block of the event animations' file (see the module's notes)."""
    sequences: list         # each `read_sequences`' steps
    frames: list            # each `[Tile]`, in drawing order
    palettes: list          # 16 palettes of 16 colours
    pixels: bytes           # the 256 by 200 picture, a colour number a pixel


def _ended(steps: list) -> list:
    """A block's sequence up to its end instruction (`EVTCHR_END`), the zeros after a block's last left out."""
    for k, step in enumerate(steps):
        if step[0] == "op" and step[1] == EVTCHR_END:
            return steps[:k + 1]
    return steps


def read_evtchr(block: bytes) -> Evtchr:
    """
    A block of `EVTCHR_FILE`: its sequences, each running from its offset
    to its end instruction (or the next one along, or the sequences' end),
    its frames (a byte of part count less one and rotation, a byte of
    flags, then 4 bytes a part: its place from where the unit stands, s8
    each, and its tile, size and flips as a unit frame's), its palettes
    and its picture.
    """
    if len(block) < EVTCHR_BLOCK:
        raise SpriteError(f"an event animation block is {EVTCHR_BLOCK} bytes; this is {len(block)}")

    def offsets(at, count, limit):
        found = []
        for k in range(count):
            value = struct.unpack_from("<i", block, at + 4 * k)[0]
            found.append(0 if value == -1 or not 0 <= value < limit else value)
        return found

    sequence_data = block[EVTCHR_SEQUENCES_AT:EVTCHR_SEQUENCES_AT + EVTCHR_SEQUENCE_BYTES]
    starts = offsets(0, 64, EVTCHR_SEQUENCE_BYTES)
    ends = sorted(set(starts) | {EVTCHR_SEQUENCE_BYTES})
    sequences = [_ended(_steps(sequence_data[start:next(e for e in ends if e > start)])) for start in starts]
    frame_data = block[EVTCHR_FRAMES_AT:EVTCHR_FRAMES_AT + EVTCHR_FRAME_BYTES]
    frames = []
    for start in offsets(0x500, EVTCHR_FRAME_OFFSETS, EVTCHR_FRAME_BYTES):
        tiles = []
        count = (frame_data[start] & 7) + 1 if start < len(frame_data) else 0
        for k in range(count):
            at = start + 2 + 4 * k
            if at + 4 > len(frame_data):
                break
            x, y = struct.unpack_from("<bb", frame_data, at)
            flags = frame_data[at + 2] | (frame_data[at + 3] << 8)
            width, height = TILE_SIZES[(flags >> 10) & 0x0F]
            tiles.append(Tile(x, y, (flags & 0x1F) * 8, ((flags >> 5) & 0x1F) * 8, width, height,
                              bool(flags & 0x4000), bool(flags & 0x8000)))
        tiles.reverse()          # drawn last first, as a unit's frames are
        frames.append(tiles)
    values = struct.unpack_from("<256H", block, EVTCHR_PALETTES_AT)
    palettes = [list(values[16 * p:16 * p + 16]) for p in range(16)]
    pixels = bytes(colour_numbers(block[EVTCHR_PIXELS_AT:EVTCHR_PIXELS_AT + EVTCHR_WIDTH * EVTCHR_HEIGHT // 2]))
    return Evtchr(sequences, frames, palettes, pixels)


def evtchr_slot(animation: int) -> Optional[int]:
    """The slot an animation number plays from (0 or 1), or None for a unit's own animation."""
    first, second = EVTCHR_SLOT_ANIMATIONS
    if animation >= second:
        return 1
    if animation >= first:
        return 0
    return None


def read_evtchr_table(path=None) -> dict:
    """`{block: g2d entry}` from `data/EvtchrSheets.txt` (`block|entry`)."""
    found = {}
    try:
        text = Path(path or (paths.bundled_data_dir() / EVTCHR_TABLE_NAME)).read_text(encoding="utf-8")
    except OSError:
        return found
    for line in text.splitlines():
        parts = [part.strip() for part in line.split("|")]
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            found[int(parts[0])] = int(parts[1])
    return found


# =============================================================================
# Pictures
# =============================================================================

@dataclass
class Picture:
    """
    A frame drawn: `width` x `height` pixels, 4 bytes each (red, green,
    blue, opacity), and where in it the unit stands, in HD pixels.
    """
    width: int
    height: int
    rgba: bytes
    stand_x: int
    stand_y: int


def draw_frame(sheet: Sheet, tiles, palette, scale: int = SCALE) -> Optional[Picture]:
    """
    One frame, cut from `sheet` and coloured with `palette` (16 bit values),
    as small as its tiles allow. None for a frame with no tiles.

    The tiles are drawn in order, each over those before it where it isn't
    see-through. Colour numbers whose colour is 0 are see-through.
    """
    if not tiles:
        return None
    places = [((t.x + STAND_X) * scale, (t.y + STAND_Y) * scale, t.width * scale, t.height * scale)
              for t in tiles]
    left = min(p[0] for p in places)
    top = min(p[1] for p in places)
    width = max(p[0] + p[2] for p in places) - left
    height = max(p[1] + p[3] for p in places) - top
    # Each pixel is its colour number + 1, and 0 where nothing is drawn, so
    # a see-through colour leaves what is under it.
    shown = bytes((n + 1) if palette[n] else 0 for n in range(16)) + bytes(240)
    canvas = bytearray(width * height)
    for tile, (x, y, w, h) in zip(tiles, places):
        for row in range(h):
            source_y = tile.sheet_y * scale + ((h - 1 - row) if tile.flip_y else row)
            line = sheet.row(source_y, tile.sheet_x * scale, w).translate(shown)
            if tile.flip_x:
                line = line[::-1]
            at = (y - top + row) * width + (x - left)
            under = canvas[at:at + w]
            canvas[at:at + w] = bytes(a or b for a, b in zip(line, under)) if 0 in line else line
    colours = [(0, 0, 0, 0)] + [rgba(v) for v in palette]
    out = bytearray(width * height * 4)
    for channel in range(4):
        table = bytes(colours[n][channel] if n < 17 else 0 for n in range(256))
        out[channel::4] = canvas.translate(table)
    return Picture(width, height, bytes(out), STAND_X * scale - left, STAND_Y * scale - top)


# =============================================================================
# Which sprite, which files
# =============================================================================

@dataclass(frozen=True)
class SpriteEntry:
    """A sprite number's classic file (`battle_<name>_spr.bin`) and its HD sheets."""
    number: int
    name: str
    sheets: tuple


def table_path() -> Path:
    return paths.bundled_data_dir() / TABLE_NAME


def read_table(path=None) -> dict:
    """`{sprite number: SpriteEntry}` from `data/UnitSprites.txt` (`number|name|sheets`)."""
    found = {}
    try:
        text = Path(path or table_path()).read_text(encoding="utf-8")
    except OSError:
        return found
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) != 3 or not parts[0].isdigit():
            continue
        try:
            sheets = tuple(int(s) for s in parts[2].split(",") if s.strip())
        except ValueError:
            continue
        found[int(parts[0])] = SpriteEntry(int(parts[0]), parts[1].lower(), sheets)
    return found


@dataclass(frozen=True)
class Attributes:
    """A sprite's frame kind, animation kind, whether it flies, and its height."""
    shape: str
    sequence: str
    flying: bool
    height: int


def read_attributes(battle_bin: bytes) -> dict:
    """`{sprite number: Attributes}` from BATTLE.BIN's table at `ATTRIBUTES_AT`."""
    out = {}
    end = ATTRIBUTES_AT + 4 * ATTRIBUTE_COUNT
    if len(battle_bin) < end:
        raise SpriteError(f"BATTLE.BIN ends at {len(battle_bin):#x}, before its sprite table does")
    for number in range(ATTRIBUTE_COUNT):
        shape, sequence, flying, height = battle_bin[ATTRIBUTES_AT + 4 * number:
                                                     ATTRIBUTES_AT + 4 * number + 4]
        if shape < len(KINDS) and sequence < len(SEQUENCE_KINDS):
            out[number] = Attributes(KINDS[shape], SEQUENCE_KINDS[sequence], bool(flying), height)
    return out


def sprite_number(sprite_set: int, job: int, monster_graphic: int = 0) -> Optional[int]:
    """
    The sprite a unit is drawn with: its ENTD sprite set, or for the three
    generic sets its job's (see the module's notes). None when nothing says.
    """
    if 0 < sprite_set < GENERIC_MAN:
        return sprite_set
    if sprite_set in (GENERIC_MAN, GENERIC_WOMAN):
        woman = sprite_set - GENERIC_MAN
        if FIRST_GENERIC_JOB <= job <= LAST_PAIRED_JOB:
            return FIRST_GENERIC_SPRITE + 2 * (job - FIRST_GENERIC_JOB) + woman
        return LATE_JOBS.get((job, woman))
    if sprite_set == GENERIC_MONSTER and monster_graphic > 0:
        return MONSTER_SPRITE_BASE + monster_graphic
    return None


@dataclass
class Idle:
    """A sprite's waiting animation: `[(Picture, 60ths of a second)]` from the front and from behind."""
    front: list
    back: list
    flying: bool
    height: int


class UnitSprites:
    """
    What one unpacked game draws its units with. Each file is read once,
    and each sprite's pictures made once a palette. `problem` says what is
    missing when nothing can be drawn.
    """

    def __init__(self, game_dir, table: Optional[dict] = None, evtchr_table: Optional[dict] = None):
        self.game_dir = Path(game_dir) if game_dir else None
        self.table = read_table() if table is None else table
        self.evtchr_table = read_evtchr_table() if evtchr_table is None else evtchr_table
        self.problem = ""
        self._g2d = None
        self._attributes = None
        self._shapes, self._sequences, self._sheets, self._palettes, self._idle = {}, {}, {}, {}, {}
        self._evtchr_file = None
        self._evtchr, self._evtchr_sheets = {}, {}

    def _file(self, relative: str) -> Path:
        return self.game_dir / relative

    def g2d(self) -> Optional[G2d]:
        if self._g2d is None and self.game_dir is not None:
            try:
                self._g2d = G2d(self._file(G2D_FILE))
            except (OSError, SpriteError) as exc:
                self.problem = f"{G2D_FILE} couldn't be read ({exc})"
                self._g2d = False
        return self._g2d or None

    def attributes(self) -> dict:
        if self._attributes is None:
            try:
                self._attributes = read_attributes(self._file(BATTLE_BIN).read_bytes())
            except (OSError, SpriteError) as exc:
                self.problem = f"{BATTLE_BIN} couldn't be read ({exc})"
                self._attributes = {}
        return self._attributes

    def _unit_file(self, name: str, kind: str) -> Optional[bytes]:
        try:
            return self._file(f"{UNIT_FOLDER}/battle_{name}_{kind}.bin").read_bytes()
        except OSError:
            return None

    def shape(self, kind: str) -> Optional[list]:
        kind = SHAPE_OF.get(kind, kind)
        if kind not in self._shapes:
            data = self._unit_file(kind, "shp")
            try:
                self._shapes[kind] = read_shape(data) if data else None
            except SpriteError:
                self._shapes[kind] = None
        return self._shapes[kind]

    def sequences(self, kind: str) -> Optional[list]:
        if kind not in self._sequences:
            data = self._unit_file(kind, "seq")
            try:
                self._sequences[kind] = read_sequences(data) if data else None
            except SpriteError:
                self._sequences[kind] = None
        return self._sequences[kind]

    def sheet(self, entry: SpriteEntry) -> Optional[Sheet]:
        if entry.name not in self._sheets:
            g2d = self.g2d()
            self._sheets[entry.name] = (join_sheets([g2d.entry(n) for n in entry.sheets])
                                        if g2d is not None and entry.sheets else None)
        return self._sheets[entry.name]

    def palettes(self, entry: SpriteEntry) -> Optional[list]:
        if entry.name not in self._palettes:
            data = self._unit_file(entry.name, "spr")
            try:
                self._palettes[entry.name] = read_palettes(data) if data else None
            except SpriteError:
                self._palettes[entry.name] = None
        return self._palettes[entry.name]

    def evtchr(self, block: int) -> Optional[Evtchr]:
        """Block `block` of the event animations' file, or None when it can't be read."""
        if block not in self._evtchr:
            if self._evtchr_file is None and self.game_dir is not None:
                try:
                    self._evtchr_file = self._file(EVTCHR_FILE).read_bytes()
                except OSError as exc:
                    self.problem = self.problem or f"{EVTCHR_FILE} couldn't be read ({exc})"
                    self._evtchr_file = b""
            data = self._evtchr_file or b""
            chunk = data[block * EVTCHR_BLOCK:(block + 1) * EVTCHR_BLOCK] if block >= 0 else b""
            try:
                self._evtchr[block] = read_evtchr(chunk) if len(chunk) == EVTCHR_BLOCK else None
            except SpriteError:
                self._evtchr[block] = None
        return self._evtchr[block]

    def evtchr_sheet(self, block: int) -> Optional[Sheet]:
        """A block's HD picture (`data/EvtchrSheets.txt`'s entry in g2d.dat), else its own
        picture at twice the size."""
        if block not in self._evtchr_sheets:
            sheet = None
            g2d, entry = self.g2d(), self.evtchr_table.get(block)
            if g2d is not None and entry is not None:
                sheet = join_sheets([g2d.entry(entry)])
            if sheet is None:
                found = self.evtchr(block)
                if found is not None:
                    rows = bytearray()
                    for y in range(EVTCHR_HEIGHT):
                        line = bytes(found.pixels[y * EVTCHR_WIDTH:(y + 1) * EVTCHR_WIDTH])
                        doubled = bytes(b for b in line for _ in range(2))
                        rows += doubled + bytes(SHEET_WIDTH - len(doubled))
                        rows += doubled + bytes(SHEET_WIDTH - len(doubled))
                    sheet = Sheet(SHEET_WIDTH, 2 * EVTCHR_HEIGHT, rows)
            self._evtchr_sheets[block] = sheet
        return self._evtchr_sheets[block]

    def evtchr_animation(self, number: Optional[int], palette: int, block: int, animation: int,
                         colours: Optional[tuple] = None) -> Optional[list]:
        """
        Animation `animation` (500 up) of sprite `number`, coloured by its
        palette `palette` (or, `colours` given, by palette `colours[1]` of
        block `colours[0]`, as EVTCHR palette colours a unit), from event
        animation block `block`: `[(Picture or None, step)]`, its
        `read_sequences` steps with each frame drawn; None when it can't be.
        A frame from `EVTCHR_FRAME_FIRST` is the block's, below it the
        sprite's own.
        """
        slot = evtchr_slot(animation)
        found = self.evtchr(block)
        if slot is None or found is None or number is None:
            return None
        index = animation - EVTCHR_SLOT_ANIMATIONS[slot]
        if not 0 <= index < len(found.sequences):
            return None
        entry, attributes = self.table.get(number), self.attributes().get(number)
        colours_block = self.evtchr(colours[0]) if colours else None
        if colours_block is not None and 0 <= colours[1] < len(colours_block.palettes) \
                and not is_blank(colours_block.palettes[colours[1]]):
            colours = colours_block.palettes[colours[1]]
        else:
            colours = self.palette(number, palette)
        if entry is None or attributes is None or colours is None:
            return None
        own_sheet, shape = self.sheet(entry), self.shape(attributes.shape)
        event_sheet = self.evtchr_sheet(block)
        out = []
        for step in found.sequences[index]:
            if step[0] == "op":
                out.append((None, step))
                continue
            frame = step[0]
            picture = None
            if frame >= EVTCHR_FRAME_FIRST:
                k = frame - EVTCHR_FRAME_FIRST
                if event_sheet is not None and k < len(found.frames):
                    picture = draw_frame(event_sheet, found.frames[k], colours)
            elif own_sheet is not None and shape and frame < len(shape):
                picture = draw_frame(own_sheet, shape[frame], colours)
            out.append((picture, step))
        return out

    def palette(self, number: int, wanted: int) -> Optional[list]:
        """Palette `wanted` of sprite `number`, or its first where that one is blank."""
        entry = self.table.get(number)
        palettes = self.palettes(entry) if entry is not None else None
        if not palettes:
            return None
        chosen = palettes[wanted % 16]
        return palettes[0] if is_blank(chosen) else chosen

    def idle(self, number: Optional[int], palette: int = 0) -> Optional[Idle]:
        """Sprite `number`'s waiting animation in palette `palette`, or None when it can't be drawn."""
        if number is None:
            return None
        key = (number, palette)
        if key in self._idle:
            return self._idle[key]
        made = None
        entry = self.table.get(number)
        attributes = self.attributes().get(number)
        if entry is None:
            self.problem = self.problem or f"sprite {number} isn't in {TABLE_NAME}"
        elif attributes is not None:
            sheet, colours = self.sheet(entry), self.palette(number, palette)
            shape, animations = self.shape(attributes.shape), self.sequences(attributes.sequence)
            if sheet is not None and colours is not None and shape and animations:
                sides = {}
                for side, which in (("front", WALK_FRONT), ("back", WALK_BACK)):
                    pictures = []
                    for frame, delay in frames_of(animations[which] if which < len(animations) else []):
                        picture = draw_frame(sheet, shape[frame], colours) if frame < len(shape) else None
                        if picture is not None:
                            pictures.append((picture, max(1, delay)))
                    sides[side] = pictures
                if sides["front"] or sides["back"]:
                    made = Idle(sides["front"], sides["back"], attributes.flying, attributes.height)
        self._idle[key] = made
        return made
