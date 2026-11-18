"""
Pictures of more colors than a sheet's, tied to one palette (Zodi's second
point of 16 November 2026: "replace the effect sprites (this can apply to all
sprites as well) files with those of higher resolution and deeper color
depths. For instance using PPSSPP texture packs"; his choices of 17 November:
**tied to one palette**, PPSSPP's way, the close's recommended answer taken by
"Continue with your recommendations"; and, once the measure was put to him
with its cost, "Up to 4 times (Recommended)" and "Keep its colors
(Recommended)").

What the game does with a sheet's colors (`claude/texture-resolution-
research.md`, "Measured in the thirtieth session"): a unit sprite's or a job's
figure's sheet is a color number a pixel, 16 of them, and an effect's 16 or 256;
the game makes each texture from the numbers and the palette of that moment,
which for a unit is its team's palette, changed by a status, and for an effect
the line of colors its frame names, changed as it plays. A picture whose colors
aren't all its palette's can't be numbers alone.

What Mod Studio does with one (`own_of`): an image given in a palette whose
drawn pixels aren't all that palette's colors to five bits a part (what the
game's 15 bit colors hold) keeps its own colors besides its numbers (each pixel
the nearest of the palette's colors, which every other palette and the game
without Mod Studio Framework show). Mod Studio Framework shows each pixel's own
color where the game draws the sheet in the palette it was given in, and in any
other palette the numbers through that palette, so a team's colors and a
status's still work (`helper/ModStudioEventSetup/OwnColors.cs`). Such a picture
is 1 to 4 times the game's size (`SCALES`).

Its file (`sheet_file`, `read_sheet_file`), the bigger sheet's "MSBT" at its
version 2, which Mod Studio Framework reads (`OwnColors.Read`): "MSBT", 2, 32
(bits a pixel), the scale (two bytes), the width and the height in pixels (four
bytes each); then the color numbers' bits (4 or 8), 0, how many colors the
palette it was given in has (two bytes: 16 or 256) and their 15 bit words; then
the rows compressed (zlib), four bytes a pixel: its own red, green and blue
(red first) and its color number.

Pure Python but for numpy, imported where a picture is read.
"""
from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from typing import Optional

MAGIC = b"MSBT"
VERSION, BITS = 2, 32
HEADER_BYTES, HEAD = 16, 4
#: How many times the game's size a picture of more colors may be (Mod Studio Framework's `OwnColors.MinScale` and
#: `MaxScale`; his choice of 17 November).
SCALES = (1, 2, 3, 4)


class OwnColorsError(ValueError):
    """A file that isn't a sheet of more colors as Mod Studio writes one; its message is for the reader."""


@dataclass
class OwnSheet:
    """A sheet of more colors as its file holds it: `numbers` a byte a pixel, `own` its own colors (red, green and blue
    a pixel), `tied` the palette it was given in (15 bit words), `number_bits` 4 or 8."""
    scale: int
    width: int
    height: int
    numbers: bytes
    own: bytes
    tied: list
    number_bits: int


def parts(word: int) -> tuple:
    """A 15 bit color's three parts, five bits each, red first."""
    return word & 0x1F, (word >> 5) & 0x1F, (word >> 10) & 0x1F


def own_of(rgba, numbers: bytes, words: list) -> tuple:
    """
    An image's own colors, given in the palette `words` (15 bit words): `(its
    own colors as red, green and blue a pixel, how many of its pixels have a
    color of their own)`, or `(None, 0)` where every drawn pixel is the color
    of the number it was given (`numbers`, a byte a pixel), five bits a part,
    as the game holds a color. A pixel more than half see through is drawn by
    no number of its own and has no color of its own (black is kept for it).
    `rgba` is the image as an array of height by width by 4 (numpy).
    """
    import numpy as np
    rgba = np.asarray(rgba, dtype=np.uint8)
    height, width = rgba.shape[:2]
    table = np.array([parts(int(word)) for word in list(words)] + [(0, 0, 0)] * (256 - len(words)), dtype=np.uint8)
    given = table[np.frombuffer(bytes(numbers), dtype=np.uint8).reshape(height, width)]
    drawn = rgba[..., 3] >= 128
    apart = drawn & ((rgba[..., :3] >> 3) != given).any(axis=-1)
    count = int(apart.sum())
    if not count:
        return None, 0
    rgb = np.where(drawn[..., None], rgba[..., :3], 0).astype(np.uint8)
    return rgb.tobytes(), count


def sheet_file(scale: int, width: int, height: int, numbers: bytes, own: bytes, tied: list, number_bits: int) -> bytes:
    """A sheet of more colors' file as Mod Studio Framework reads one (the note at the top)."""
    import numpy as np
    count = 1 << number_bits
    words = (list(tied) + [0] * count)[:count]
    rgb = np.frombuffer(bytes(own), dtype=np.uint8).reshape(-1, 3)
    rows = np.empty((len(rgb), 4), dtype=np.uint8)
    rows[:, :3] = rgb
    rows[:, 3] = np.frombuffer(bytes(numbers), dtype=np.uint8)
    head = MAGIC + bytes((VERSION, BITS)) + struct.pack("<HII", scale, width, height)
    head += bytes((number_bits, 0)) + struct.pack("<H", count) + struct.pack(f"<{count}H", *words)
    return head + zlib.compress(rows.tobytes(), 6)


def is_own_file(raw: bytes) -> bool:
    """Whether a bigger sheet's file is a sheet of more colors (its version 2), read or not."""
    return len(raw) > 4 and raw[:4] == MAGIC and raw[4] == VERSION


def read_sheet_file(raw: bytes) -> OwnSheet:
    """A sheet of more colors' file read; raises `OwnColorsError` saying why where it isn't one as Mod Studio writes
    one (its size is for its caller to hold to what it is for)."""
    if len(raw) < HEADER_BYTES + HEAD or not is_own_file(raw) or raw[5] != BITS:
        raise OwnColorsError("it isn't a sheet of more colors as Mod Studio writes one")
    scale, width, height = struct.unpack_from("<HII", raw, 6)
    number_bits, zero, count = raw[HEADER_BYTES], raw[HEADER_BYTES + 1], struct.unpack_from("<H", raw, HEADER_BYTES + 2)[0]
    if number_bits not in (4, 8) or zero or count != 1 << number_bits or len(raw) < HEADER_BYTES + HEAD + 2 * count:
        raise OwnColorsError("its palette isn't one a sheet of more colors is given in")
    if scale not in SCALES:
        raise OwnColorsError("its size isn't 1 to 4 times the game's")
    tied = list(struct.unpack_from(f"<{count}H", raw, HEADER_BYTES + HEAD))
    try:
        body = zlib.decompressobj()
        rows = body.decompress(raw[HEADER_BYTES + HEAD + 2 * count:], width * height * 4 + 1)
        if not body.eof or body.unused_data or body.unconsumed_tail:
            raise OwnColorsError("its rows aren't its size")
    except zlib.error as exc:
        raise OwnColorsError(f"its rows can't be read ({exc})") from None
    if len(rows) != width * height * 4:
        raise OwnColorsError("its rows aren't its size")
    import numpy as np
    grid = np.frombuffer(rows, dtype=np.uint8).reshape(-1, 4)
    if int(grid[:, 3].max(initial=0)) >= 1 << number_bits:
        raise OwnColorsError("a color number is past its palette's")
    return OwnSheet(scale, width, height, grid[:, 3].tobytes(), grid[:, :3].tobytes(), tied, number_bits)


def drawn(numbers: bytes, own: bytes, seen: list) -> bytes:
    """A picture's own colors as red, green, blue and opacity a pixel, as a page shows it in the palette it was given
    in: each pixel its own color, see through where its number's color is (`seen`: each number's opacity, 0 or 255)."""
    import numpy as np
    rgb = np.frombuffer(bytes(own), dtype=np.uint8).reshape(-1, 3)
    alpha = np.array(list(seen) + [0] * (256 - len(seen)), dtype=np.uint8)[np.frombuffer(bytes(numbers), dtype=np.uint8)]
    out = np.empty((len(rgb), 4), dtype=np.uint8)
    out[:, :3] = np.where(alpha[:, None] > 0, rgb, 0)
    out[:, 3] = alpha
    return out.tobytes()

