"""
A job's own sprite made from a classic one: Zodi's 8th note of 14 November ("the community has created sprites for a
long time and have requested that their sprites that they made could be made compatible with the new Sprite format/
size", "Mod Studio should be able to ideally scale them to the correct The Ivalice Chronicles format for both .bmp files
and .spr files", and "Sprites for humans have two kinds that the community refers to as Type1 and Type2"), and his
picks: "Tell it, modder can change", "Smooth, plain if asked". What it rests on is measured in
claude/classic-sprites-research.md:

- **A classic sheet** is 256 by 488 color numbers (0 to 15): rows 0 to 255 its first part, 256 to 455 the rest, 456 to
  487 the small portrait. A **.spr** (the game's own sprites' format; the facts from FFTPatcher's ShishiSpriteEditor,
  Glain and contributors, GPL-3, read for facts only) holds 16 palettes of 16 colors (15 bits; the top bit the
  PlayStation's semi-transparency), the rows 0 to 255 and the portrait's 32 at 4 bits a pixel (the left pixel in a
  byte's low four bits), then the rows 256 to 455 packed (`read_spr`). A **.bmp** (or any picture of numbered colors)
  of 256 by 488 holds the color numbers and its palette's colors, 16 a palette (`read_picture`).
- **The Ivalice Chronicles' sheet is the classic one doubled**, 512 by 976, color number for color number: its upper
  texture the first 512 rows, its lower the other 464 (`textures`). Doubled by Scale2x (Andrea Mazzoleni's published
  algorithm: each pixel four, each taking a neighbour's color where two neighbours meet across a corner, so only colors
  already in the sprite) it is nearer the game's own HD sheets than doubled plainly, for every one of the game's 30
  sheets measured; plainly doubled, every pixel is a block of 2 by 2 (`doubled`).
- **The palettes the game wants** (`team_colors`): a figure wears palette 0 to 4 by its team (0 the player's units');
  only a palette's first color is see through (the game shows every other, black too), written "#000000" as the game's
  own are; a color is 5 bits each of red, green and blue, kept as the game shows it; a sprite with fewer than five
  palettes has its first copied into the rest, so no team draws it in another sprite's colors. Palettes 5 to 7 and the
  small portrait's (8 to 15) aren't used: the Enhanced look's portraits are the job's face pictures.
- **Type 1 and Type 2**, the frames a sheet is drawn for, told from the sheet (`told_frames`): its share of colored
  pixels in each cell of 8 by 8 (the portrait's rows left out), held to the mean of the game's own human sheets of each
  kind over the cells where the two kinds' means differ by more than a quarter (`game_kinds`, from the modder's own
  game). Measured: all 23 told right (the game's 21 human sheets on hand, each against the other 20, and Zodi's two),
  and the game's HD sheets halved too (`halved`). A sheet colored far more or far less than a sprite's is not told
  (`TOLD_SHARE`): its frames stay the job's.

Nothing here imports Qt; Pillow and numpy are imported where they are needed.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import unit_sprites as us

#: A classic sheet: its size, its parts' rows (the first part, the packed rest, the small portrait).
WIDTH, HEIGHT = 256, 488
TOP_ROWS, PACKED_ROWS, PORTRAIT_ROWS = 256, 200, 32
#: A .spr's palettes (16 of 16 colors, 2 bytes each) and its unpacked rows (the first part's and the portrait's).
PALETTE_BYTES = 512
RAW_BYTES = (TOP_ROWS + PORTRAIT_ROWS) * WIDTH // 2
#: The palettes a figure wears (one a team's), the palettes a sheet's figure may give (the first 8 of 16), colors each.
TEAM_PALETTES, FIGURE_PALETTES, PALETTE_COLORS = 5, 8, 16
#: The game's sheet: twice the classic's each way; its upper texture's rows.
SCALE, UPPER_ROWS = 2, 512
#: The two kinds of human frames (the framework's Look Frames: 1 and 2), and the game's generic jobs drawn for each
#: (Mod Studio Framework's SpriteRoom.FramesJob: the Squire's attributes and the Chemist's).
TYPE1, TYPE2 = 1, 2
FRAMES_JOBS = {TYPE1: 74, TYPE2: 75}
#: The game's shape files of the two kinds (`unit_sprites.UnitSprites.shape`).
SHAPES = {TYPE1: "type1", TYPE2: "type2"}
#: Where a frame is composed to see what lies past a piece's edge (`cleared_edges`): a canvas big enough for every
#: frame of the two kinds, and where the unit stands on it (classic pixels).
FRAME_CANVAS, FRAME_ORIGIN = (160, 128), (64, 112)
#: Telling the frames: the cells' size, the rows told (the portrait's left out), the least difference of the two kinds'
#: means in a cell told by, and the share of colored pixels a sheet is told within (the game's own human sheets color
#: 0.155 to 0.274 of those rows, Zodi's two 0.177 and 0.261: a sheet far outside isn't a sprite's layout).
CELL, TOLD_ROWS, TOLD_LEAST = 8, TOP_ROWS + PACKED_ROWS, 0.25
TOLD_SHARE = (0.05, 0.5)
SPR_SUFFIX = ".spr"

# Words a user sees (HANDOFF's "Words to sign off" lists them).
SPR_SHORT = ("This .spr file is {n:,} bytes: a classic sprite's file is at least 37,376 (its palettes and its first "
             "288 rows).")
CLASSIC_SIZE_BAD = "A classic sprite's sheet is 256 by 488 pixels: this one is {w} by {h}."
NOT_NUMBERED = ("This image's colors aren't numbered (it was saved with true colors, as a screenshot or a JPG is): a "
                "classic sprite's sheet is an indexed image of 16 or 256 colors, as .bmp sprites are.")
NO_FIRST_PALETTE = "This sprite's first palette has no colors."


class ClassicError(ValueError):
    """A file that can't be read as a classic sprite; the message says why, in words."""


@dataclass
class Classic:
    """A classic sprite as read: its sheet's color numbers (WIDTH * HEIGHT, 0 to 15), the figure's palettes it gives (8,
    each 16 "#RRGGBB" as the game shows them, or None where it gives none), and how many of the figure's pixels (the
    portrait's rows left out) were numbered past 15 in its picture (each taken as its place in a palette of 16)."""
    pixels: bytes
    palettes: list = field(default_factory=lambda: [None] * FIGURE_PALETTES)
    past: int = 0

    def given(self) -> int:
        """How many of the figure's palettes it gives."""
        return sum(1 for p in self.palettes if p)


# =============================================================================
# Reading
# =============================================================================

def game_color(value: int) -> str:
    """One of the game's 15 bit colors as "#RRGGBB", as the game shows it (the top bit, the semi-transparency, left out)."""
    r, g, b = value & 31, (value >> 5) & 31, (value >> 10) & 31
    return "#%02X%02X%02X" % ((r << 3) | (r >> 2), (g << 3) | (g >> 2), (b << 3) | (b >> 2))


def snapped(rgb) -> str:
    """A color (red, green, blue, 0 to 255) as "#RRGGBB", as the game shows it: each part's top five bits."""
    r, g, b = (max(0, min(255, int(v))) >> 3 for v in tuple(rgb)[:3])
    return "#%02X%02X%02X" % ((r << 3) | (r >> 2), (g << 3) | (g >> 2), (b << 3) | (b >> 2))


def _unpacked(stream: bytes, want: int) -> bytearray:
    """A .spr's packed rows unpacked: 4 bit numbers, a byte's high one first; a number past 0 a pixel; a 0 and then s:
    s 7, a count in the next two numbers (the low first), s 8 in the next three, s 0 in the next one, any other s the
    count, of see through pixels. Then each pair of pixels swapped (the sheet's left pixel is a byte's low four bits).
    Short of `want`, the rest see through."""
    nibbles = bytearray(len(stream) * 2)
    nibbles[0::2] = bytes(b >> 4 for b in stream)
    nibbles[1::2] = bytes(b & 15 for b in stream)
    out = bytearray()
    i, n = 0, len(nibbles)
    while i < n and len(out) < want:
        v = nibbles[i]
        if v:
            out.append(v)
            i += 1
            continue
        if i + 1 >= n:
            break
        s = nibbles[i + 1]
        i += 2
        if s == 7:
            if i + 1 >= n:
                break
            count = nibbles[i] | (nibbles[i + 1] << 4)
            i += 2
        elif s == 8:
            if i + 2 >= n:
                break
            count = nibbles[i] | (nibbles[i + 1] << 4) | (nibbles[i + 2] << 8)
            i += 3
        elif s == 0:
            if i >= n:
                break
            count = nibbles[i]
            i += 1
        else:
            count = s
        out.extend(bytes(count))
    out = out[:want] + bytes(max(0, want - len(out)))
    swapped = bytearray(want)
    swapped[0::2] = out[1::2]
    swapped[1::2] = out[0::2]
    return swapped


def read_spr(data: bytes) -> Classic:
    """A classic sprite's file (.spr): its sheet and the figure's palettes (a palette given where a color of it is more
    than its semi-transparency bit)."""
    if len(data) < PALETTE_BYTES + RAW_BYTES:
        raise ClassicError(SPR_SHORT.format(n=len(data)))
    raw = data[PALETTE_BYTES:PALETTE_BYTES + RAW_BYTES]
    numbers = bytearray(len(raw) * 2)
    numbers[0::2] = bytes(b & 15 for b in raw)
    numbers[1::2] = bytes(b >> 4 for b in raw)
    pixels = bytearray(WIDTH * HEIGHT)
    pixels[:TOP_ROWS * WIDTH] = numbers[:TOP_ROWS * WIDTH]
    pixels[(TOP_ROWS + PACKED_ROWS) * WIDTH:] = numbers[TOP_ROWS * WIDTH:]
    pixels[TOP_ROWS * WIDTH:(TOP_ROWS + PACKED_ROWS) * WIDTH] = _unpacked(data[PALETTE_BYTES + RAW_BYTES:],
                                                                         PACKED_ROWS * WIDTH)
    palettes = []
    for k in range(FIGURE_PALETTES):
        values = struct.unpack_from("<16H", data, 2 * PALETTE_COLORS * k)
        palettes.append([game_color(v) for v in values] if any(v & 0x7FFF for v in values) else None)
    return Classic(bytes(pixels), palettes)


def is_classic_picture(image) -> bool:
    """Whether a picture (Pillow) is a classic sheet's size, 256 pixels wide (the game's are 512)."""
    return image.size[0] == WIDTH


def read_picture(image) -> Classic:
    """A classic sprite's sheet as a picture of numbered colors (a .bmp of 16 or 256 colors, or a PNG): 256 by 488, each
    pixel a color number. A number past 15 is taken as its place in a palette of 16 (an 8 bit .bmp's portrait is
    numbered in its own palettes, 8 and on); those of the figure are counted. Its palette's colors 16 at a time are the
    figure's palettes, each given where a color of it isn't black."""
    width, height = image.size
    if (width, height) != (WIDTH, HEIGHT):
        raise ClassicError(CLASSIC_SIZE_BAD.format(w=width, h=height))
    if image.mode != "P":
        raise ClassicError(NOT_NUMBERED)
    data = image.tobytes()
    figure = data[:TOLD_ROWS * WIDTH]
    past = sum(1 for v in figure if v > 15)
    pixels = bytes(v & 15 for v in data)
    flat = list(image.getpalette() or [])
    colors = len(flat) // 3
    palettes = []
    for k in range(FIGURE_PALETTES):
        if colors < PALETTE_COLORS * (k + 1):
            palettes.append(None)
            continue
        rgb = [tuple(flat[3 * (PALETTE_COLORS * k + i):3 * (PALETTE_COLORS * k + i) + 3]) for i in range(PALETTE_COLORS)]
        palettes.append([snapped(c) for c in rgb] if any(any(c) for c in rgb) else None)
    return Classic(pixels, palettes, past)


def read_file(path) -> Classic:
    """A classic sprite from a file: a .spr by its name, else a picture of numbered colors (Pillow opens it)."""
    path = Path(path)
    if path.suffix.lower() == SPR_SUFFIX:
        return read_spr(path.read_bytes())
    from PIL import Image
    with Image.open(path) as image:
        image.load()
        return read_picture(image)


# =============================================================================
# The game's size, and its palettes
# =============================================================================

def doubled(pixels: bytes, smooth: bool = True, width: int = WIDTH, height: int = HEIGHT) -> bytes:
    """A sheet of color numbers twice the size each way: by Scale2x (`smooth`; past the sheet's edges its edge's own
    pixels), or every pixel a block of 2 by 2."""
    import numpy as np
    p = np.frombuffer(bytes(pixels), dtype=np.uint8).reshape(height, width)
    if not smooth:
        return p.repeat(SCALE, axis=0).repeat(SCALE, axis=1).tobytes()
    b = np.vstack([p[:1], p[:-1]])
    h = np.vstack([p[1:], p[-1:]])
    d = np.hstack([p[:, :1], p[:, :-1]])
    f = np.hstack([p[:, 1:], p[:, -1:]])
    corner = (b != h) & (d != f)
    out = np.empty((SCALE * height, SCALE * width), dtype=np.uint8)
    out[0::2, 0::2] = np.where(corner & (d == b), d, p)
    out[0::2, 1::2] = np.where(corner & (b == f), f, p)
    out[1::2, 0::2] = np.where(corner & (d == h), d, p)
    out[1::2, 1::2] = np.where(corner & (h == f), f, p)
    return out.tobytes()


def packed(numbers: bytes) -> bytes:
    """Color numbers a byte a pixel to 4 bits a pixel, the left pixel in a byte's low four bits."""
    import numpy as np
    n = np.frombuffer(bytes(numbers), dtype=np.uint8)
    return (n[0::2] | (n[1::2] << 4)).astype(np.uint8).tobytes()


def textures(classic: Classic, smooth: bool = True) -> tuple:
    """The game's two textures of a classic sprite (as g2d.dat keeps a sprite's): its sheet doubled, the upper texture
    its first 512 rows (131,072 bytes), the lower the other 464 (118,784 bytes, as the game's own)."""
    data = packed(doubled(classic.pixels, smooth))
    split = UPPER_ROWS * WIDTH * SCALE // 2
    return data[:split], data[split:]


def team_colors(classic: Classic) -> list:
    """The five palettes a figure of the sprite wears, as the game wants them: its own first five, each palette it
    doesn't give its first's; each palette's first color "#000000" (see through); every color as the game shows it."""
    first = classic.palettes[0] if classic.palettes else None
    if not first:
        raise ClassicError(NO_FIRST_PALETTE)
    out = []
    for k in range(TEAM_PALETTES):
        palette = classic.palettes[k] if k < len(classic.palettes) and classic.palettes[k] else first
        out.append(["#000000"] + [str(c).upper() for c in list(palette)[1:PALETTE_COLORS]])
    return out


# =============================================================================
# Type 1 and Type 2
# =============================================================================

@dataclass
class Kinds:
    """The game's own human sheets' mean share of colored pixels in each cell, a kind's ({TYPE1: [...], TYPE2: [...]}),
    the cells a sheet is told by, and how many sheets of each kind the means are of."""
    means: dict
    cells: list
    sheets: dict


def cell_shares(pixels: bytes, width: int = WIDTH) -> list:
    """A classic sheet's share of colored pixels in each cell of CELL by CELL, its rows 0 to 455, row by row."""
    import numpy as np
    p = np.frombuffer(bytes(pixels), dtype=np.uint8)[:TOLD_ROWS * width].reshape(TOLD_ROWS, width) != 0
    return p.reshape(TOLD_ROWS // CELL, CELL, width // CELL, CELL).mean(axis=(1, 3)).ravel().tolist()


def kinds_from(sheets) -> Optional[Kinds]:
    """The kinds' means from sheets as `(kind, pixels)`; None unless both kinds have one."""
    shares = {TYPE1: [], TYPE2: []}
    for kind, pixels in sheets:
        shares[kind].append(cell_shares(pixels))
    if not shares[TYPE1] or not shares[TYPE2]:
        return None
    means = {k: [sum(column) / len(rows) for column in zip(*rows)] for k, rows in shares.items()}
    cells = [c for c in range(len(means[TYPE1])) if abs(means[TYPE1][c] - means[TYPE2][c]) > TOLD_LEAST]
    return Kinds(means, cells, {k: len(rows) for k, rows in shares.items()})


_KINDS: dict = {}


def game_kinds(sprites: us.UnitSprites) -> Optional[Kinds]:
    """The kinds' means from the modder's own game: every human sprite of its table (BATTLE.BIN's attributes TYPE1 or
    TYPE2) whose classic file is there, each file once. Made once a game; None where it can't be (no game, or no sheet
    of a kind)."""
    if sprites is None or sprites.game_dir is None:
        return None
    key = str(sprites.game_dir)
    if key not in _KINDS:
        attributes = sprites.attributes()
        seen, sheets = set(), []
        for number, entry in sorted(sprites.table.items()):
            a = attributes.get(number)
            kind = {"type1": TYPE1, "type2": TYPE2}.get(a.shape) if a is not None else None
            if kind is None or entry.name in seen:
                continue
            seen.add(entry.name)
            data = sprites._unit_file(entry.name, "spr")
            if not data:
                continue
            try:
                sheets.append((kind, read_spr(data).pixels))
            except ClassicError:
                continue
        _KINDS[key] = kinds_from(sheets)
    return _KINDS[key]


def colored_share(pixels: bytes) -> float:
    """A classic sheet's share of colored pixels in its rows 0 to 455."""
    figure = bytes(pixels)[:TOLD_ROWS * WIDTH]
    return (len(figure) - figure.count(0)) / len(figure) if figure else 0.0


def told_frames(pixels: bytes, kinds: Optional[Kinds]) -> Optional[int]:
    """The frames a classic sheet is drawn for (TYPE1 or TYPE2), told from where it has art against the game's own
    sheets of each kind (`kinds`); None where it can't be told (no kinds, or a sheet colored far more or less than a
    sprite's: TOLD_SHARE)."""
    if kinds is None or not TOLD_SHARE[0] <= colored_share(pixels) <= TOLD_SHARE[1]:
        return None
    shares = cell_shares(pixels)
    one, two = kinds.means[TYPE1], kinds.means[TYPE2]
    score = sum((shares[c] - (one[c] + two[c]) / 2) * (one[c] - two[c]) for c in kinds.cells)
    return TYPE1 if score > 0 else TYPE2


@dataclass
class Edges:
    """What `cleared_edges` did to a sprite's textures: the pixels of the game's size it cleared, how many of them a
    frame showed as a piece's own (its first row or column, which those frames lose), and the pixels past an edge it
    kept because a frame shows them inside a piece's art."""
    cleared: int = 0
    trimmed: int = 0
    kept: int = 0


def _composed_tops(frame, sheet, scale: int):
    """A frame drawn from a sheet at `scale` times the classic size, as the game draws its pieces (each piece's
    rectangle, flipped where the frame says, a later piece over an earlier): the canvas, and for each drawn pixel the
    sheet pixel it came from and whether that pixel is inside its piece past the piece's first row and column (its own
    art drawn whole)."""
    import numpy as np
    height, width = FRAME_CANVAS[1] * scale, FRAME_CANVAS[0] * scale
    canvas = np.zeros((height, width), dtype=np.uint8)
    from_r = np.full((height, width), -1, dtype=np.int32)
    from_c = np.full((height, width), -1, dtype=np.int32)
    whole = np.zeros((height, width), dtype=bool)
    for t in frame:
        sx, sy, w, h = t.sheet_x * scale, t.sheet_y * scale, t.width * scale, t.height * scale
        part = sheet[sy:sy + h, sx:sx + w]
        rs, cs_ = np.mgrid[sy:sy + h, sx:sx + w]
        rs, cs_ = rs[:part.shape[0], :part.shape[1]], cs_[:part.shape[0], :part.shape[1]]
        inner = (rs - sy >= scale) & (cs_ - sx >= scale)
        if t.flip_x:
            part, rs, cs_, inner = part[:, ::-1], rs[:, ::-1], cs_[:, ::-1], inner[:, ::-1]
        if t.flip_y:
            part, rs, cs_, inner = part[::-1], rs[::-1], cs_[::-1], inner[::-1]
        dx, dy = (t.x + FRAME_ORIGIN[0]) * scale, (t.y + FRAME_ORIGIN[1]) * scale
        dh, dw = part.shape
        if dx < 0 or dy < 0 or dx + dw > width or dy + dh > height:
            continue
        drawn = part != 0
        canvas[dy:dy + dh, dx:dx + dw][drawn] = part[drawn]
        from_r[dy:dy + dh, dx:dx + dw][drawn] = rs[drawn]
        from_c[dy:dy + dh, dx:dx + dw][drawn] = cs_[drawn]
        whole[dy:dy + dh, dx:dx + dw][drawn] = inner[drawn]
    return canvas, from_r, from_c, whole


def cleared_edges(upper: bytes, lower: bytes, frames: list) -> tuple:
    """A sprite's two textures (as g2d.dat keeps a sprite's) with the lines the game would draw under or beside its
    poses taken out: `(upper, lower, Edges)`. `frames` are the frames it is drawn with (the game's shape file of its
    kind, `unit_sprites.read_shape`).

    Measured in Zodi's program (claude/dark-onion-knight-research.md, test 124's report): the menus' figure routine
    draws each piece of a frame from its texture with the piece's rectangle taken from half a classic pixel in (its
    corners `(x + 0.5) / 256` and `(x + width + 0.5) / 256`, the same down) and the texture filtered, so the game's size's
    two rows just past a piece's bottom edge and two columns just past its right edge show along that edge, and nothing
    above its top or left of its left. The game's own generic jobs' classic sheets, doubled as Mod Studio doubles one,
    leave those rows and columns empty wherever a frame shows them over nothing (its story characters' have a few
    places of their own, and its own textures of the game's size a few pixels a sheet: 12 to 43 where measured, most of
    them a piece's first row that other poses use); a sheet drawn for the PlayStation (where no piece draws past its
    edge) may not, and the game then draws a thin line there (his Dark Knight's and Onion Knight's bars, tests 123 and
    124).

    So each pixel of those rows and columns that has a color and lands over nothing in a frame is cleared; but not one a
    frame shows inside a piece's own art past that piece's first row and column (clearing it would make a hole in the
    figure; the game's own sprites keep a few such specks too). One a frame shows as a piece's first row or column is
    cleared, and that piece loses it there (`Edges.trimmed`). A piece in the upper texture draws nothing of the lower.

    Done again until it clears nothing: a piece's first row or column cleared can leave a pixel past another piece's
    edge over nothing, which the game would then show in turn (a sheet colored everywhere, the tests' stripes, lost
    112 more on a second pass). So nothing of the result would show as a line, and Export writes the same textures
    again from the ones it wrote. `Edges` counts every pass's cleared and trimmed pixels and the last pass's kept."""
    import numpy as np
    width = WIDTH * SCALE
    numbers = np.frombuffer(bytes(us.colour_numbers(bytes(upper) + bytes(lower))), dtype=np.uint8)
    rows = len(numbers) // width
    sheet = numbers[:rows * width].reshape(rows, width).copy()
    split = len(upper) * 2 // width
    edges = Edges()
    while True:
        done = _cleared_once(sheet, split, frames)
        edges.cleared += done.cleared
        edges.trimmed += done.trimmed
        edges.kept = done.kept
        if not done.cleared:
            break
    data = packed(sheet.tobytes())
    cut = len(upper)
    return data[:cut], data[cut:], edges


def cleared_bigger(upper: bytes, lower: bytes, scale: int, frames: list) -> tuple:
    """(17 November 2026) A sprite's two textures at `scale` times the game's size with the same lines taken out:
    `(upper, lower, Edges)`, for a figure given bigger (`mod_jobs.JobArt.big`), which Mod Studio Framework shows in
    the game's place through the same routines.

    The game takes a piece's rectangle from the same fractions of the texture whatever its size, so what shows past a
    piece's bottom and right edges is the same place of the sheet: the block of `scale` by `scale` pixels that stands
    for each of the game's. So the rule is `cleared_edges`' own, held over the game's pixels: each of them counts as
    colored where any pixel of its block is, the same passes are run over that sheet until one clears nothing, and
    every pixel they clear is cleared as its whole block. Written again from what it wrote it changes nothing, as
    `cleared_edges` doesn't. `Edges` counts the game's pixels (blocks), not the bigger sheet's."""
    import numpy as np
    width = WIDTH * SCALE
    wide = width * scale
    numbers = np.frombuffer(bytes(us.colour_numbers(bytes(upper) + bytes(lower))), dtype=np.uint8)
    rows = len(numbers) // wide // scale
    big = numbers[:rows * scale * wide].reshape(rows * scale, wide)
    sheet = big.reshape(rows, scale, width, scale).max(axis=(1, 3))
    before = sheet != 0
    split = len(upper) * 2 // wide // scale
    edges = Edges()
    while True:
        done = _cleared_once(sheet, split, frames)
        edges.cleared += done.cleared
        edges.trimmed += done.trimmed
        edges.kept = done.kept
        if not done.cleared:
            break
    gone = before & (sheet == 0)
    if not gone.any():
        return bytes(upper), bytes(lower), edges
    big = big.copy()
    big[np.repeat(np.repeat(gone, scale, axis=0), scale, axis=1)] = 0
    data = packed(big.tobytes())
    cut = len(upper)
    return data[:cut], data[cut:] + bytes(lower)[len(data) - cut:], edges


def _cleared_once(sheet, split: int, frames: list) -> Edges:
    """One pass of `cleared_edges` over a sheet of the game's size (a color number a pixel; changed in place), its
    upper texture's rows `split`: what it cleared, trimmed and kept."""
    import numpy as np
    rows, width = sheet.shape
    candidates, kept_inside, shown = set(), np.zeros(sheet.shape, dtype=bool), np.zeros(sheet.shape, dtype=bool)
    for frame in frames:
        canvas, from_r, from_c, whole = _composed_tops(frame, sheet, SCALE)
        drawn = canvas != 0
        shown[from_r[drawn], from_c[drawn]] = True
        inside = drawn & whole
        kept_inside[from_r[inside], from_c[inside]] = True
        height, cwidth = canvas.shape
        for t in frame:
            sx, sy, w, h = t.sheet_x * SCALE, t.sheet_y * SCALE, t.width * SCALE, t.height * SCALE
            dx, dy = (t.x + FRAME_ORIGIN[0]) * SCALE, (t.y + FRAME_ORIGIN[1]) * SCALE
            if dx < 0 or dy < 0 or dx + w > cwidth or dy + h > height:
                continue
            last_row = split if sy < split else rows
            for k in range(SCALE):
                r = sy + h + k
                if r < last_row:
                    for j in range(min(w, width - sx)):
                        c = sx + j
                        cy = dy - 1 - k if t.flip_y else dy + h + k
                        cx = dx + (w - 1 - j if t.flip_x else j)
                        if sheet[r, c] and not (0 <= cy < height and 0 <= cx < cwidth and canvas[cy, cx]):
                            candidates.add((r, c))
                c = sx + w + k
                if c < width:
                    for i in range(min(h, last_row - sy)):
                        r = sy + i
                        cx = dx - 1 - k if t.flip_x else dx + w + k
                        cy = dy + (h - 1 - i if t.flip_y else i)
                        if sheet[r, c] and not (0 <= cy < height and 0 <= cx < cwidth and canvas[cy, cx]):
                            candidates.add((r, c))
    edges = Edges()
    for r, c in candidates:
        if kept_inside[r, c]:
            edges.kept += 1
            continue
        sheet[r, c] = 0
        edges.cleared += 1
        edges.trimmed += int(shown[r, c])
    return edges


def halved(numbers: bytes, width: int = WIDTH * SCALE) -> bytes:
    """A sheet of the game's size (a color number a pixel, `width` wide) as a classic sheet's art: each block of 2 by 2
    colored (1) where any of its pixels is, for telling its frames."""
    import numpy as np
    rows = len(numbers) // width
    rows -= rows % 2
    p = np.frombuffer(bytes(numbers), dtype=np.uint8)[:rows * width].reshape(rows // 2, 2, width // 2, 2) != 0
    half = p.any(axis=(1, 3)).astype(np.uint8)
    out = np.zeros((HEIGHT, WIDTH), dtype=np.uint8)
    h = min(HEIGHT, half.shape[0])
    out[:h, :min(WIDTH, half.shape[1])] = half[:h, :WIDTH]
    return out.tobytes()
