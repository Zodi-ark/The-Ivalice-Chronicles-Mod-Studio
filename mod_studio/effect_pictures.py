"""
An effect's picture as a mod replaces it, at the game's size (Zodi's second
point of 16 November 2026: "also be able to replace the effect sprites ...
files"; his choices of 17 November: both sizes, the game's size first, and for
the page "Continue on with your recommendations": a group of their own on the
Textures page, "Effects" (his ask of 17 November; first "Effect pictures"), each
effect by its number and name, with the unit sprites' three buttons).

What an effect's picture is, as the game keeps it (`effect_files.py`'s note;
`claude/texture-resolution-research.md`, "Measured in the twenty seventh
session"): the last section of the effect's own file,
`fftpack/effect/efc_eNNNdat_data.bin`. Two blocks of 256 colors (each a 16 bit
word: a word of 0 is never drawn, and a word's top bit says the color is
blended where its frame is see through), four bytes of size, then the sheet's
pixels. The game puts the pixels in its emulated video memory as they are, and
each of the effect's frames says how it reads them: at 8 bits a pixel through
the first block's 256 colors, or at 4 bits through one line of 16 colors of
either block. One way of reading is a `View`; `views` lists those an effect's
frames use, which are the palettes the page steps through.

What a mod's own picture becomes at Export (`write`): **the effect's file
written again** under `FFTIVC/data/enhanced/fftpack/effect/`, the game's own
byte for byte but for its texture section's pixels and, where the image
brought them, its colors (`written`). Its size is the game's file's: the game
asks for an effect's file by its size in whole sectors, and the mod loader
hands at most what is asked. No Mod Studio Framework is needed for it. **That
the mod loader hands the game a mod's effect file is an inference** from how
the game reads one (as it reads a map's file, which a mod's was shown to
replace in the game): only the game can show it.

A picture's pixels and colors (`from_image`): an image the size of the sheet
in the view it is given under. One whose colors are numbered (a PNG of 256
colors or fewer at 8 bits, of 16 or fewer at 4 bits, as `png` writes one)
keeps its numbers and **brings its colors**: each color of its palette that
isn't the one shown becomes the view's color at that number, blended as the
color it takes the place of was. In any other image a pixel left as the sheet
shows it keeps its number, and any other pixel takes the nearest of the view's
drawn colors, or a color that is never drawn where it is more than half see
through.

Opening a mod reads its pictures back (`read`): a file of the mod's effect
folder that is the game's own but for its texture section's colors and pixels
is the page's again; any other is left to be carried through as it is.

**A bigger picture** (the twenty ninth session; his choice of 17 November, once
the measure was put to him with its cost: "Yes, up to 4 times"): an image 2 to
4 times the sheet's size in the view it is given under (`SCALES`), its color
numbers the view's as at the game's size. It is also made the game's size
(every `scale`th pixel of every `scale`th row, from the middle of each block),
which is what the effect's file is written with, so the effect is the mod's
wherever Mod Studio Framework doesn't reach. Besides that file, Export names a
sheet of its color numbers in the mod's one `ModStudioTextures.json`
(`big_sheets`: `{"Effect": its number, "File":
"ModStudioTextures/effect_NNN.bin", "Picture": the effect's file}`; the sheet
"MSBT", version 1, 8 or 4 bits a pixel, the scale, its width and height, then
its rows), which `sprite_textures.files` writes with the unit sprites' and the
jobs'. Mod Studio Framework (`helper/ModStudioEventSetup/EffectTextures.cs`)
draws it through the game's own palette of the moment where the game makes the
effect's page's texture, at the bits it was given at (an effect whose frames
read its sheet both ways, one of the 400, is drawn at the game's size in the
other). The mod then needs Mod Studio Framework. Read back by `read` where the
file names it for a picture of the mod's that it fits.

**A picture of more colors** (the thirtieth session; his choices of 17
November: tied to one palette, up to 4 times, and Replace... keeps an image's
own colors): an image that isn't numbered and whose drawn pixels aren't all the
view's colors, five bits a part (`own_colors.own_of`), keeps its own colors for
that view (`EffectArt.own`, `own_view`), at the sheet's size or 2 to 4 times
it, besides its color numbers, which are as before (the nearest drawn colors).
Export writes the effect's file as before and names a sheet of more colors for
it in the same place a bigger picture's is (`own_colors.sheet_file`: "MSBT",
version 2, its palette the view's colors), which Mod Studio Framework draws in
its own colors where the game makes the effect's page in that palette, and in
the view's numbers through any other.

**The 16 summons** (the thirty fourth session; his Lich test of 17 November:
"In game the red line blue line and violet line do not appear on the texture";
`dev/research/sidequests/summon_sheets.py`, `claude/texture-resolution-
research-continued.md`, "The summons' remastered sheets, measured"): in the
enhanced look the game draws a summon (`SUMMONS`, the effects its table
RefinedVFXTexture marks) from a sheet of its own, g2d.dat's entry
`SUMMON_FIRST` plus two times its effect's number: 512 by 512 pixels, a byte a
pixel, the effect's file's sheet's layout at twice the size in its top left
corner, colored by the effect's first block of 256 colors, its color 0 see
through (the only one: a word of 0 elsewhere is drawn black there). The classic
look draws the effect's file's picture. So a summon's picture is its sheet
(`summon_from_image`): an image the size of the sheet's drawn part (twice the
effect's file's sheet) or twice that (`SUMMON_SCALES`), its numbers and colors
as any effect's, a pixel never drawn color 0. Export writes the sheet as the mod
loader replaces an entry (`summon_file`, `tex_<entry>.bin`, 262,144 bytes: no
Mod Studio Framework), the effect's file with it at half the size (`classic_of`:
each pixel the game's own where the sheet's two by two block over it is the
game's, else the block's first pixel that isn't), and where the picture is twice
the sheet's size or of more colors, besides the effect's bigger picture as
before, the sheet bigger or of more colors for Mod Studio Framework, named by
its entry in `ModStudioTextures.json`'s Sprites (`summon_sheets`), which the
framework draws where the game makes the summon's texture from that entry
(`BigTextures.cs`, a sheet of 8 bits). Opening the mod reads them back
(`read_summons`); a summon of an older mod, with no sheet of its own, has one
made from its picture.

Nothing here imports Qt; Pillow and numpy are imported where a picture is read.
"""
from __future__ import annotations

import io
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from . import effect_files as ef
from . import own_colors as oc
from .sprite_textures import packed

import json

#: Where a mod's own effect files go, from its folder: the game's path under the mod loader's data folder.
DATA = "FFTIVC/data/enhanced"
FOLDER = f"{DATA}/{ef.EFFECT_FOLDER}"
#: The top bit of a color's word: blended where its frame is see through.
BLENDED_BIT = 0x8000
#: Black that is drawn: a word of 0 is never drawn, so a solid black that isn't blended is the darkest grey (a blended
#: black is the word 0x8000, which is drawn).
DARKEST = 0x0421

SIZE_BAD = ("An effect's picture is an image the size of its sheet, {w} by {h} pixels in this palette, or 2 to 4 times "
            "that size for a bigger picture: this one is {iw} by {ih}. Export as PNG gives one to start from.")
NO_PICTURE = "this effect's file has no picture"
NOT_GAMES = "the picture isn't the size of the game's own"
#: (The twenty ninth session) How many times the sheet's size a bigger picture may be (Mod Studio Framework's
#: `EffectTextures.MinScale` and `MaxScale`), where its sheet goes from the mod's folder, and its file's header.
SCALES = (2, 3, 4)
BIG_FOLDER = "ModStudioTextures"
MAGIC = b"MSBT"
HEADER_BYTES = 16
SHEET_BAD = "its bigger picture {file} can't be read here ({why})"
#: (The thirtieth session) Why a picture of more colors read back isn't the page's.
NOT_A_VIEW = "its colors' palette isn't one the effect's frames draw it in"
#: (The thirty fourth session) The 16 summons, which the enhanced look draws from a sheet of their own (the game's
#: table RefinedVFXTexture's byte at + 0x18 set for these and no other, read by 0xD2AB8: `summon_sheets.py`).
SUMMONS = (63, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 76, 77, 78, 79, 80)
#: A summon's sheet is g2d.dat's entry `SUMMON_FIRST` plus two times its effect's number (0xD2C74), 512 by 512
#: pixels at a byte a pixel.
SUMMON_FIRST, SUMMON_SIDE = 1426, 512
SUMMON_BYTES = SUMMON_SIDE * SUMMON_SIDE
#: Where the unpacked game keeps g2d.dat, where the mod loader takes a replaced entry of it from, and the start of a
#: summon's sheet's name for Mod Studio Framework.
G2D_FILE = "system/ffto/g2d.dat"
G2D_FOLDER = f"{DATA}/system/ffto/g2d"
SUMMON_SHEET = "summon_"
#: How many times its sheet's drawn part a summon's picture may be: its own size, the game's (two times the effect's
#: file's sheet, no Mod Studio Framework), or twice that (four times the effect's file's, his "up to 4 times").
SUMMON_SCALES = (1, 2)
SUMMON_SIZE_BAD = ("A summon's picture is an image the size of its sheet, {w} by {h} pixels, or twice that size for a "
                   "bigger picture: this one is {iw} by {ih}. Export as PNG gives one to start from.")
SUMMON_BAD = "its sheet {file} can't be read here ({why})"


class EffectPictureError(ValueError):
    """A picture that can't be an effect's; its message is for the reader."""


@dataclass(frozen=True)
class View:
    """One way an effect's frames read its sheet: at 8 bits a pixel through a block of 256 colors, or at 4 bits
    through one line of 16 (`palette`, 0 at 8 bits) of the first block or the second."""
    eight_bit: bool
    second_clut: bool = False
    palette: int = 0

    @property
    def colors(self) -> int:
        return 256 if self.eight_bit else 16

    @property
    def colors_at(self) -> int:
        """Where the view's colors start in the two blocks' bytes."""
        return (ef.CLUT_BYTES if self.second_clut else 0) + (0 if self.eight_bit else self.palette * 32)


#: The view of a sheet no frame draws: the first block at 8 bits, as most are drawn.
PLAIN = View(True)


@dataclass
class EffectArt:
    """A mod's own picture of one of the game's effects: the effect's whole file as the mod has it, the game's own
    but for its texture section's colors and pixels; and (the twenty ninth session) where the picture given was
    bigger, its color numbers at `scale` times the sheet's size, a byte a pixel (`big`), read at 8 bits a pixel or at
    4 (`big_eight`); (the thirtieth session) where it was of more colors, its own colors at `scale` times the size
    (`own`, red, green and blue a pixel; `big` its numbers then, at the game's size too) and the view they were given
    in (`own_view`); (the thirty fourth session) for one of the 16 summons, its own sheet as the mod loader's file
    holds it (`remastered`: 512 by 512, a byte a pixel), its picture's `scale` then counted against the effect's file's
    sheet as any effect's is (2 the sheet's own size, 4 twice it)."""
    data: bytes
    scale: int = 1
    big: Optional[bytes] = None
    big_eight: bool = True
    own: Optional[bytes] = None
    own_view: Optional["View"] = None
    remastered: Optional[bytes] = None

    @property
    def is_big(self) -> bool:
        return self.scale > 1 and self.big is not None

    @property
    def has_own(self) -> bool:
        """(The thirtieth session) Whether it has colors of its own, tied to a view's colors."""
        return self.own is not None and self.own_view is not None and self.big is not None

    @property
    def is_summon(self) -> bool:
        """(The thirty fourth session) Whether it is a summon's picture with its own sheet."""
        return self.remastered is not None

    @property
    def times(self) -> int:
        """(The thirty fourth session) How many times the size the game draws it at the picture is: a summon's against
        its own sheet (twice the effect's file's), any other's against the effect's file's sheet."""
        if self.is_summon:
            return self.scale // 2 if self.big is not None and self.scale in (2, 4) else 1
        return self.scale if self.is_big else 1

    @property
    def needs_sheet(self) -> bool:
        """Whether Export names a sheet for it that Mod Studio Framework draws (bigger, or of more colors); (the
        thirty fourth session) a summon's picture at its sheet's own size needs none, the mod loader's file being
        that size."""
        if self.is_summon:
            return self.times > 1 or self.has_own
        return self.is_big or self.has_own

    def shows_own(self, view: "View") -> bool:
        """Whether a view shows its own colors: a view at its bits whose colors are those it was given in (Mod Studio
        Framework knows a palette by its colors)."""
        return self.has_own and view.eight_bit == self.own_view.eight_bit \
            and words(self.data, view) == words(self.data, self.own_view)


@dataclass
class Taken:
    """What `from_image` made of an image: the art, how many of its pixels weren't one of the view's colors and
    took the nearest, and how many of the view's colors the image brought its own for; (the thirtieth session) how
    many of its pixels kept colors of their own."""
    art: EffectArt
    off: int = 0
    brought: int = 0
    own: int = 0


def file_of(number: int) -> str:
    """A mod's own file for an effect, from the mod's folder."""
    return f"{FOLDER}/{ef.effect_file_name(number)}"


def texture_at(data: bytes) -> int:
    """Where an effect's file's texture section starts (its header's tenth offset); raises where it has none."""
    if len(data) < ef.HEADER_SIZE:
        raise EffectPictureError(NO_PICTURE)
    start = struct.unpack_from("<I", data, 36)[0]
    if start < ef.HEADER_SIZE or start + ef.PIXELS_AT > len(data):
        raise EffectPictureError(NO_PICTURE)
    return start


def texture_of(data: bytes) -> ef.Texture:
    """An effect's file's texture section as `effect_files` reads one."""
    start = texture_at(data)
    size = data[start + ef.UPLOAD_HEADER] | (data[start + ef.UPLOAD_HEADER + 1] << 8) \
        | (data[start + ef.UPLOAD_HEADER + 2] << 16)
    return ef.Texture(bytes(data[start:start + 2 * ef.CLUT_BYTES]), data[start + 0x403], size,
                      bytes(data[start + ef.PIXELS_AT:]))


def written(game: bytes, cluts: bytes, pixels: bytes) -> bytes:
    """The game's file of an effect with other colors and pixels: every other byte, and its size, the game's."""
    start = texture_at(game)
    if len(cluts) != 2 * ef.CLUT_BYTES or len(pixels) != len(game) - start - ef.PIXELS_AT:
        raise EffectPictureError(NOT_GAMES)
    return bytes(game[:start]) + bytes(cluts) + bytes(game[start + ef.UPLOAD_HEADER:start + ef.PIXELS_AT]) \
        + bytes(pixels)


def is_picture_of(mine: bytes, game: bytes) -> bool:
    """Whether a file is the game's file of an effect with other colors or pixels and nothing else changed."""
    try:
        start = texture_at(game)
    except EffectPictureError:
        return False
    return (len(mine) == len(game) and mine[:start] == game[:start]
            and mine[start + ef.UPLOAD_HEADER:start + ef.PIXELS_AT] == game[start + ef.UPLOAD_HEADER:start + ef.PIXELS_AT]
            and mine != game)


def views(data: bytes) -> list:
    """The ways an effect's frames read its sheet, each once: at 8 bits first, then each line of 16 colors by its
    block and its number. A sheet no frame draws has the one plain view."""
    try:
        effect = ef.read_effect(data)
    except ef.EffectError:
        return [PLAIN]
    found = set()
    for frameset in effect.framesets:
        for frame in (frameset.frames if frameset is not None else ()):
            found.add(View(frame.eight_bit, frame.second_clut, 0 if frame.eight_bit else frame.palette))
    return sorted(found, key=lambda v: (not v.eight_bit, v.second_clut, v.palette)) or [PLAIN]


def words(data: bytes, view: View) -> list:
    """A view's colors as the file's 16 bit words (256 at 8 bits, else 16)."""
    return texture_of(data).colours(view.eight_bit, view.second_clut, view.palette)


def shown(word: int) -> tuple:
    """A color's word as the page shows it, (r, g, b, a): see through where it is never drawn."""
    return (0, 0, 0, 0) if word == 0 else ef.colour_of(word) + (255,)


def sheet(data: bytes, view: View) -> tuple:
    """`(width, height, numbers)`: an effect's sheet as a view reads it, a color number a pixel."""
    return ef.sheet_texels(texture_of(data), view.eight_bit)


def png(data: bytes, view: View) -> bytes:
    """An effect's sheet in a view as a PNG of numbered colors, a color that is never drawn see through: what
    `from_image` reads back number for number and color for color."""
    width, height, numbers = sheet(data, view)
    return png_of(width, height, numbers, words(data, view))


def _most_blended(old: list) -> bool:
    drawn = [word for word in old if word]
    return 2 * sum(1 for word in drawn if word & BLENDED_BIT) >= len(drawn) if drawn else True


def word_for(color: tuple, old: int, blended: bool) -> int:
    """
    The word of a color an image brings, (r, g, b, a), for a place whose word
    was `old` and isn't shown so (`from_image` keeps a color shown as it was):
    never drawn where it is more than half see through; else its 15 bits,
    blended as the old color was (or, in a place that was never drawn, as
    `blended` says: as most of its palette's colors are). A solid black that isn't blended is
    the darkest grey, since a word of 0 is never drawn (a blended black,
    0x8000, is drawn as it is).
    """
    r, g, b, a = color
    if a < 128:
        return 0
    word = (r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10)
    word |= (old & BLENDED_BIT) if old else (BLENDED_BIT if blended else 0)
    return word or DARKEST


def _palette_of(image) -> list:
    """A numbered image's colors as (r, g, b, a), as many as its palette holds."""
    flat = image.getpalette() or []
    seen = image.info.get("transparency")
    colors = []
    for i in range(len(flat) // 3):
        if isinstance(seen, (bytes, bytearray)):
            alpha = seen[i] if i < len(seen) else 255
        else:
            alpha = 0 if seen == i else 255
        colors.append((flat[3 * i], flat[3 * i + 1], flat[3 * i + 2], alpha))
    return colors


def _same_color(color: tuple, word: int) -> bool:
    """Whether an image's color is what the page shows for a word."""
    return word == 0 if color[3] < 128 else (word != 0 and shown(word)[:3] == tuple(color[:3]))


def _nearest(image, numbers: bytes, old: list) -> tuple:
    """An image that isn't numbered as the view's color numbers: `(numbers, how many took the nearest)`."""
    import numpy as np
    rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    height, width = rgba.shape[:2]
    was = np.frombuffer(bytes(numbers), dtype=np.uint8).reshape(height, width)
    table = np.array([shown(word) for word in old], dtype=np.uint8)
    there = table[was]
    clear = rgba[..., 3] < 128
    same = np.where(clear, there[..., 3] == 0,
                    (there[..., 3] == 255) & (rgba[..., :3] == there[..., :3]).all(axis=-1))
    drawn = [i for i, word in enumerate(old) if word]
    never = next((i for i, word in enumerate(old) if not word), None)
    if drawn:
        colors, inverse = np.unique(rgba[..., :3].reshape(-1, 3), axis=0, return_inverse=True)
        have = table[drawn][:, :3].astype(np.int32)
        nearest = np.empty(len(colors), dtype=np.uint8)
        exact = np.empty(len(colors), dtype=bool)
        for at in range(0, len(colors), 4096):
            part = colors[at:at + 4096].astype(np.int32)
            apart = ((part[:, None, :] - have[None, :, :]) ** 2).sum(axis=-1)
            first = apart.argmin(axis=1)
            nearest[at:at + 4096] = np.array(drawn, dtype=np.uint8)[first]
            exact[at:at + 4096] = apart[np.arange(len(part)), first] == 0
        inverse = np.asarray(inverse).reshape(-1)
        taken, is_exact = nearest[inverse].reshape(height, width), exact[inverse].reshape(height, width)
    else:
        taken = np.full((height, width), never or 0, dtype=np.uint8)
        is_exact = np.zeros((height, width), dtype=bool)
    if never is not None:
        new = np.where(clear, np.uint8(never), taken)
        off = ~same & ~clear & ~is_exact
    else:
        new = taken
        off = ~same & (clear | ~is_exact)
    out = np.where(same, was, new).astype(np.uint8)
    return out.tobytes(), int(off.sum())


def scale_of(size: tuple, sheet_size: tuple) -> int:
    """How many times a sheet's size an image is: 1, or one of `SCALES` (the same both ways). Raises
    `EffectPictureError` saying why where it is neither."""
    (iw, ih), (width, height) = size, sheet_size
    for scale in (1,) + SCALES:
        if (iw, ih) == (width * scale, height * scale):
            return scale
    raise EffectPictureError(SIZE_BAD.format(w=width, h=height, iw=iw, ih=ih))


def _blocks(numbers: bytes, width: int, scale: int) -> bytes:
    """A sheet's color numbers with each pixel a block of `scale` by `scale`: what a bigger image is told against."""
    import numpy as np
    grid = np.frombuffer(bytes(numbers), dtype=np.uint8).reshape(-1, width)
    return np.repeat(np.repeat(grid, scale, axis=0), scale, axis=1).tobytes()


def _middles(numbers: bytes, width: int, scale: int) -> bytes:
    """A bigger picture made the game's size: every `scale`th pixel of every `scale`th row, from the middle of each
    block (as a unit sprite's bigger picture is, `sprite_textures.from_image`)."""
    middle = scale // 2
    rows = len(numbers) // width
    return b"".join(bytes(numbers[row * width + middle:(row + 1) * width:scale]) for row in range(middle, rows, scale))


def from_image(game: bytes, image, view: View, base: Optional[bytes] = None) -> Taken:
    """
    A mod's own picture of an effect from an image (Pillow) of its sheet in
    a view, at the sheet's size or (the twenty ninth session) 2 to 4 times it
    (`scale_of`): the game's file (`game`) written again with the image's
    pixels (a bigger image's made the game's size, `_middles`), and with the
    colors a numbered image brings; a bigger image's color numbers kept as
    the art's bigger picture. `base` is the effect's file as the mod has it
    already, whose other colors are kept and whose sheet is what "left as the
    sheet shows it" is told by; the game's own without one. Raises
    `EffectPictureError` saying why where the image can't be the sheet.
    """
    base = bytes(base) if base is not None else bytes(game)
    if not is_same_shape(base, game):
        base = bytes(game)
    texture = texture_of(base)
    width, height, numbers = sheet(base, view)
    scale = scale_of(image.size, (width, height))
    old = words(base, view)
    cluts = bytearray(texture.cluts)
    off = brought = 0
    numbered = image.mode == "P" and max(image.tobytes(), default=0) < view.colors
    if numbered:
        new_numbers = image.tobytes()
        blended = _most_blended(old)
        for i, color in enumerate(_palette_of(image)[:view.colors]):
            if _same_color(color, old[i]):
                continue
            struct.pack_into("<H", cluts, view.colors_at + 2 * i, word_for(color, old[i], blended))
            brought += 1
    else:
        told = numbers if scale == 1 else _blocks(numbers, width, scale)
        new_numbers, off = _nearest(image, told, old)
    small = bytes(new_numbers) if scale == 1 else _middles(new_numbers, width * scale, scale)
    pixels = small if view.eight_bit else packed(small)
    art = EffectArt(written(game, bytes(cluts), pixels))
    if scale > 1:
        art.scale, art.big, art.big_eight = scale, bytes(new_numbers), view.eight_bit
    own, count = None, 0
    if off:                                       # (a numbered image's pixels are its own numbers: none off)
        import numpy as np
        own, count = oc.own_of(np.asarray(image.convert("RGBA")), new_numbers, old)
    if own is not None and scale in oc.SCALES:
        art.scale, art.big, art.big_eight = scale, bytes(new_numbers), view.eight_bit
        art.own, art.own_view = own, view
    return Taken(art, off, brought, count)


def shown_sheet(art: Optional[EffectArt], data: bytes, view: View) -> tuple:
    """`(width, height, numbers, scale)`: the sheet the page shows in a view, the mod's bigger picture where it has one
    read at the view's bits (or, the thirtieth session, its picture of more colors' numbers in a view that shows
    them), else the file's sheet (`sheet`) at the game's size."""
    if art is not None and art.has_own and art.shows_own(view):
        width, height, _numbers = sheet(data, view)
        return width * art.scale, height * art.scale, art.big, art.scale
    if art is not None and art.is_big and art.big_eight == view.eight_bit:
        width, height, _numbers = sheet(data, view)
        return width * art.scale, height * art.scale, art.big, art.scale
    width, height, numbers = sheet(data, view)
    return width, height, numbers, 1


def png_of(width: int, height: int, numbers: bytes, colors: list) -> bytes:
    """Color numbers as a PNG of numbered colors (`colors`: the view's words), a color that is never drawn see
    through."""
    from PIL import Image
    image = Image.frombytes("P", (width, height), bytes(numbers))
    shown_colors = [shown(word) for word in colors]
    image.putpalette([part for color in shown_colors for part in color[:3]])
    out = io.BytesIO()
    image.save(out, format="PNG", transparency=bytes(color[3] for color in shown_colors))
    return out.getvalue()


def big_png(art: EffectArt, data: bytes, view: View) -> bytes:
    """The sheet the page shows in a view (`shown_sheet`) as a PNG of numbered colors: a bigger picture at its size,
    which Replace... reads back number for number and color for color; (the thirtieth session) a picture of more
    colors in a view that shows them as a PNG of its own colors, which Replace... reads back the same."""
    if art.has_own and art.shows_own(view):
        return own_png(art, data, view)
    width, height, numbers, _scale = shown_sheet(art, data, view)
    return png_of(width, height, numbers, words(data, view))


def own_rgba(art: EffectArt, data: bytes, view: View) -> bytes:
    """(The thirtieth session) A picture of more colors as the page shows it in a view that shows its own colors: red,
    green, blue and opacity a pixel at its size, a pixel whose number is never drawn see through."""
    return oc.drawn(art.big, art.own, [shown(word)[3] for word in words(data, view)])


def own_png(art: EffectArt, data: bytes, view: View) -> bytes:
    """(The thirtieth session) A picture of more colors as a PNG of its own colors (`own_rgba`)."""
    from PIL import Image
    width, height, _numbers, _scale = shown_sheet(art, data, view)
    out = io.BytesIO()
    Image.frombytes("RGBA", (width, height), own_rgba(art, data, view)).save(out, format="PNG")
    return out.getvalue()


def sheet_file(art: EffectArt, data: bytes) -> bytes:
    """A bigger picture's sheet as Mod Studio Framework reads one (`EffectTextures.Read`): "MSBT", version 1, 8 or 4
    bits a pixel, the scale, its width and height in pixels, then its rows (at 4 bits the left pixel in a byte's low
    four bits); (the thirtieth session) a picture of more colors' (`own_colors.sheet_file`, its palette the view's
    colors in the effect's file `data`)."""
    width, height, _numbers = sheet(data, View(art.big_eight))
    width, height = width * art.scale, height * art.scale
    if art.has_own:
        return oc.sheet_file(art.scale, width, height, art.big, art.own, words(data, art.own_view),
                             8 if art.own_view.eight_bit else 4)
    body = bytes(art.big) if art.big_eight else packed(bytes(art.big))
    return MAGIC + bytes((1, 8 if art.big_eight else 4)) + struct.pack("<HII", art.scale, width, height) + body


def read_own_sheet(raw: bytes, data: bytes) -> tuple:
    """(The thirtieth session) `(scale, numbers a byte a pixel, eight_bit, own colors, the view they were given in)` of
    a sheet of more colors for an effect's file (`data`); raises `EffectPictureError` saying why where it isn't one that
    fits the file's sheet in one of the views its frames draw it in."""
    try:
        own = oc.read_sheet_file(raw)
    except oc.OwnColorsError as exc:
        raise EffectPictureError(str(exc)) from None
    eight = own.number_bits == 8
    w, h, _numbers = sheet(data, View(eight))
    if (own.width, own.height) != (w * own.scale, h * own.scale):
        raise EffectPictureError("its size isn't the effect's sheet's at 1 to 4 times")
    view = next((one for one in views(data) if one.eight_bit == eight and words(data, one) == own.tied), None)
    if view is None:
        raise EffectPictureError(NOT_A_VIEW)
    return own.scale, own.numbers, eight, own.own, view


def read_sheet_file(raw: bytes, data: bytes) -> tuple:
    """`(scale, numbers a byte a pixel, eight_bit)` of a bigger picture's sheet for an effect's file (`data`); raises
    `EffectPictureError` saying why where it isn't one that fits the file's sheet."""
    if len(raw) < HEADER_BYTES or raw[:4] != MAGIC or raw[4] != 1 or raw[5] not in (4, 8):
        raise EffectPictureError("it isn't a bigger picture as Mod Studio writes one")
    eight = raw[5] == 8
    scale, width, height = struct.unpack_from("<HII", raw, 6)
    w, h, _numbers = sheet(data, View(eight))
    body = raw[HEADER_BYTES:]
    if scale not in SCALES or (width, height) != (w * scale, h * scale) \
            or len(body) != (width * height if eight else width * height // 2):
        raise EffectPictureError("its size isn't the effect's sheet's at 2 to 4 times")
    if eight:
        return scale, bytes(body), True
    import numpy as np
    packed_ = np.frombuffer(body, dtype=np.uint8)
    numbers = np.empty(packed_.size * 2, dtype=np.uint8)
    numbers[0::2], numbers[1::2] = packed_ & 0xF, packed_ >> 4
    return scale, numbers.tobytes(), False


def big_file(number: int) -> str:
    """A bigger picture's sheet for an effect, from the mod's folder."""
    return f"{BIG_FOLDER}/effect_{number:03d}.bin"


def has_big(art: Optional[dict]) -> bool:
    """Whether any of a mod's pictures of effects is bigger than the game's or (the thirtieth session) of more colors
    (the mod then needs Mod Studio Framework)."""
    return any(own is not None and own.needs_sheet for own in (art or {}).values())


def big_sheets(art: Optional[dict]) -> list:
    """What the mod's `ModStudioTextures.json` names of its effects' bigger pictures, as Mod Studio Framework reads
    it: `[({"Effect": its number, "File": its sheet's path, "Picture": the effect's file's path}, the sheet's file)]`,
    by number. `sprite_textures.files` writes them into the one file with the unit sprites' and the jobs'."""
    return [({"Effect": number, "File": big_file(number), "Picture": file_of(number)}, sheet_file(own, own.data))
            for number, own in sorted((art or {}).items()) if own is not None and own.needs_sheet]


def is_same_shape(mine: bytes, game: bytes) -> bool:
    """Whether a file is the game's file of an effect but, at most, for its colors and pixels."""
    return mine == game or is_picture_of(mine, game)


def files(art: dict) -> dict:
    """`{a file from the mod's folder: its bytes}` for a mod's own pictures of effects; (the thirty fourth session)
    with each summon's own sheet as the mod loader replaces an entry of g2d.dat (`summon_file`)."""
    out = {file_of(number): bytes(own.data) for number, own in sorted((art or {}).items()) if own is not None}
    for number, own in sorted((art or {}).items()):
        if own is not None and own.is_summon and is_summon(number):
            out[summon_file(number)] = bytes(own.remastered)
    return out


def written_before(mod_root) -> list:
    """The effect files a mod's folder holds, each from the mod's folder: Export takes away those it doesn't write
    now and the mod doesn't carry as its own."""
    folder = Path(mod_root) / FOLDER
    try:
        names = sorted(path.name for path in folder.iterdir() if path.is_file())
    except OSError:
        return []
    return [f"{FOLDER}/{name}" for name in names if _number_of(name) is not None]


def _number_of(name: str) -> Optional[int]:
    """The effect a file's name is for (`efc_eNNNdat_data.bin`), None where it isn't an effect's file."""
    low = name.lower()
    if len(low) == len("efc_e000dat_data.bin") and low.startswith("efc_e") and low.endswith("dat_data.bin") \
            and low[5:8].isdigit():
        return int(low[5:8])
    return None


def write(mod_root, art: dict, carried=()) -> list:
    """Writes a mod's own effect files (`files`) under its folder and takes away the effect files an earlier export
    wrote that aren't written now. A file the mod carries as its own (`carried`: one that isn't a picture's, kept
    as it is; paths from the mod's folder or from its data folder) is left alone. The files written, sorted."""
    root = Path(mod_root)
    made = files(art)
    kept = set()
    for rel in carried or ():
        low = str(rel).replace("\\", "/").lower()
        kept.add(low if low.startswith("fftivc/") else f"{DATA.lower()}/{low}")
    wanted = {rel.lower() for rel in made}
    # (The thirty fourth session) A summon's own sheet an earlier export wrote and this one doesn't goes too.
    stale = written_before(root) + [summon_file(number) for number in SUMMONS if (root / summon_file(number)).is_file()]
    for rel in stale:
        if rel.lower() not in wanted and rel.lower() not in kept:
            try:
                (root / rel).unlink()
            except OSError:
                pass
    for rel, data in made.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    for folder in (root / FOLDER, root / G2D_FOLDER, (root / G2D_FOLDER).parent, (root / G2D_FOLDER).parent.parent):
        try:
            if folder.is_dir() and not any(folder.iterdir()):
                folder.rmdir()
        except OSError:
            pass
    return sorted(made)


def read(mod_root, game_dir) -> tuple:
    """
    A mod's own pictures of effects read back from its folder: `({effect
    number: EffectArt}, [the files that are the pictures' now])`. A file is a
    picture's where the unpacked game has that effect's file and the mod's is
    the game's own but for its texture section's colors and pixels
    (`is_picture_of`); any other file of the folder is left to be carried
    through as it is.
    """
    root = Path(mod_root)
    art, taken = {}, []
    if not game_dir:
        return art, taken
    for rel in written_before(root):
        number = _number_of(Path(rel).name)
        try:
            mine = (root / rel).read_bytes()
            game = ef.effect_path(game_dir, number).read_bytes()
        except OSError:
            continue
        if is_picture_of(mine, game):
            art[number] = EffectArt(mine)
            taken.append(rel)
    return art, taken


def named_effects(mod_root) -> list:
    """What a mod's `ModStudioTextures.json` names of its effects' bigger pictures (`big_sheets`' entries): each
    `{"Effect", "File", "Picture"}` whose File is inside `ModStudioTextures/`, in the file's order."""
    from . import sprite_textures as st
    try:
        named = json.loads((Path(mod_root) / st.FILE).read_text(encoding="utf-8")).get("Effects", [])
    except (OSError, ValueError, AttributeError):
        return []
    out = []
    for one in named if isinstance(named, list) else []:
        if not isinstance(one, dict):
            continue
        number, rel, picture = one.get("Effect"), one.get("File"), one.get("Picture")
        if not isinstance(number, int) or isinstance(number, bool) or not isinstance(rel, str) \
                or not isinstance(picture, str):
            continue
        rel = rel.replace("\\", "/")
        if rel.startswith(BIG_FOLDER + "/") and ".." not in rel:
            out.append({"Effect": number, "File": rel, "Picture": picture.replace("\\", "/")})
    return out


def read_big(mod_root, art: dict, game_dir=None) -> tuple:
    """
    (The twenty ninth session) The bigger pictures of a mod's pictures of
    effects read back (`art`, as `read` gives it, is given them): `([the
    files that are theirs now], [what couldn't be read])`. One is taken where
    the mod's `ModStudioTextures.json` names it for an effect's file of the
    mod's, and its sheet fits that file's sheet at 8 or 4 bits and 2 to 4
    times its size; the file itself is then taken too. A bigger picture made
    the game's size may be the game's own sheet (its pixels only between the
    game's): its effect's file, the game's byte for byte, is then the
    picture's (`art` is given it; `game_dir` is the unpacked game).
    """
    from . import sprite_textures as st
    root = Path(mod_root)
    taken, problems = [], []
    for one in named_effects(root):
        number = one["Effect"]
        if one["Picture"].lower() != file_of(number).lower():
            continue
        own = (art or {}).get(number)
        if own is None and game_dir and art is not None:
            try:
                mine = (root / one["Picture"]).read_bytes()
                same = mine == ef.effect_path(game_dir, number).read_bytes()
            except OSError:
                same = False
            if not same:
                continue
            own = art[number] = EffectArt(mine)
            taken.append(one["Picture"])
        if own is None:
            continue
        try:
            raw = (root / one["File"]).read_bytes()
            if oc.is_own_file(raw):
                own.scale, own.big, own.big_eight, own.own, own.own_view = read_own_sheet(raw, own.data)
            else:
                own.scale, own.big, own.big_eight = read_sheet_file(raw, own.data)
        except (OSError, EffectPictureError) as exc:
            problems.append(SHEET_BAD.format(file=one["File"], why=exc))
            continue
        taken.append(one["File"])
    if taken:
        taken.append(st.FILE)
    return taken, problems


def effect_names(numbers, names: Optional[dict] = None) -> list:
    """`[(effect number, the name the page lists it by)]`, by number: its number and, where Mod Studio has one
    (`data/AbilityEffectNames.txt`), the name of the ability that plays it."""
    out = []
    for number in sorted(set(numbers or ())):
        known = (names or {}).get(number)
        out.append((number, f"{number:03d}  {known}" if known else f"{number:03d}"))
    return out


# =============================================================================
# (The thirty fourth session) The 16 summons' own sheets
# =============================================================================

def is_summon(number) -> bool:
    """Whether the enhanced look draws an effect from a sheet of its own (`SUMMONS`)."""
    return number in SUMMONS


def summon_entry(number: int) -> int:
    """The entry of g2d.dat a summon's sheet is."""
    return SUMMON_FIRST + 2 * number


def summon_file(number: int) -> str:
    """A summon's sheet as the mod loader replaces an entry of g2d.dat, from the mod's folder."""
    return f"{G2D_FOLDER}/tex_{summon_entry(number)}.bin"


def summon_big_file(number: int) -> str:
    """A summon's sheet bigger or of more colors, for Mod Studio Framework, from the mod's folder."""
    return f"{BIG_FOLDER}/{SUMMON_SHEET}{summon_entry(number)}.bin"


def game_summon(game_dir, number: int) -> Optional[bytes]:
    """A summon's own sheet as the unpacked game has it (512 by 512, a byte a pixel); None where the effect isn't a
    summon or the game's g2d.dat can't give it."""
    if not game_dir or not is_summon(number):
        return None
    from . import unit_sprites as us
    try:
        sheet_bytes = us.G2d(Path(game_dir) / G2D_FILE).entry(summon_entry(number))
    except (OSError, us.SpriteError):
        return None
    return bytes(sheet_bytes) if sheet_bytes is not None and len(sheet_bytes) == SUMMON_BYTES else None


def summon_size(data: bytes) -> tuple:
    """The drawn part of a summon's sheet, `(width, height)`: the effect's file's sheet at 8 bits a pixel at twice
    the size, the sheet's top left corner."""
    width, height, _numbers = sheet(data, PLAIN)
    return min(2 * width, SUMMON_SIDE), min(2 * height, SUMMON_SIDE)


def summon_words(data: bytes) -> list:
    """A summon's sheet's colors as the file's 16 bit words: the effect's first block, its color 0 never drawn (the
    game clears it there whatever its word)."""
    return [0] + words(data, PLAIN)[1:]


def summon_region(entry: bytes, size: tuple) -> bytes:
    """The top left `size` of a summon's sheet (512 wide), a byte a pixel."""
    width, height = size
    return b"".join(bytes(entry[row * SUMMON_SIDE:row * SUMMON_SIDE + width]) for row in range(height))


def with_region(entry: bytes, region: bytes, size: tuple) -> bytes:
    """A summon's sheet with its top left `size` other, the rest as it was."""
    width, height = size
    out = bytearray(entry)
    for row in range(height):
        out[row * SUMMON_SIDE:row * SUMMON_SIDE + width] = region[row * width:(row + 1) * width]
    return bytes(out)


def see_through(numbers: bytes, colors: list) -> bytes:
    """Color numbers as a summon's sheet keeps them: one whose color is never drawn made 0, the one number its sheet
    draws see through (`colors`: the effect's first block's words)."""
    table = bytes(0 if n >= len(colors) or not colors[n] else n for n in range(256))
    return bytes(numbers).translate(table)


def classic_of(game: bytes, game_region: bytes, region: bytes, colors: list) -> bytes:
    """
    The effect's file's sheet (a byte a pixel) made from a summon's sheet's
    drawn part `region` (`game_region` the game's own): each pixel the game's
    own where the two by two block of the sheet over it is the game's, else
    the first of the block's pixels that isn't (its middle first, as a bigger
    picture is made the game's size, then the others in reading order), so a
    line a pixel wide still shows; a see through one (0) the file's first
    color that is never drawn (`colors`: its first block's words).
    """
    import numpy as np
    width, height, numbers = sheet(game, PLAIN)
    mine = np.frombuffer(bytes(region), dtype=np.uint8).reshape(2 * height, 2 * width)
    theirs = np.frombuffer(bytes(game_region), dtype=np.uint8).reshape(2 * height, 2 * width)
    out = np.frombuffer(bytes(numbers), dtype=np.uint8).reshape(height, width).copy()
    never = next((n for n, word in enumerate(colors) if not word), 0)
    decided = np.zeros((height, width), dtype=bool)
    for dy, dx in ((1, 1), (0, 0), (0, 1), (1, 0)):
        here, there = mine[dy::2, dx::2], theirs[dy::2, dx::2]
        take = (here != there) & ~decided
        out[take] = np.where(here[take] == 0, never, here[take])
        decided |= take
    return out.tobytes()


def summon_scale_of(size: tuple, sheet_size: tuple) -> int:
    """How many times a summon's sheet's drawn part an image is: 1 or 2 (`SUMMON_SCALES`). Raises
    `EffectPictureError` saying why where it is neither."""
    (iw, ih), (width, height) = size, sheet_size
    for scale in SUMMON_SCALES:
        if (iw, ih) == (width * scale, height * scale):
            return scale
    raise EffectPictureError(SUMMON_SIZE_BAD.format(w=width, h=height, iw=iw, ih=ih))


def summon_from_image(game: bytes, game_sheet: bytes, image, base: Optional[EffectArt] = None) -> Taken:
    """
    A mod's own picture of a summon from an image (Pillow) of its sheet's
    drawn part (`summon_size`), at that size or twice it: its numbers and
    colors as `from_image` takes an effect's in the plain view (a numbered
    image keeps its numbers and brings its colors, color 0 being see through
    in the sheet whatever it is; any other keeps each pixel left as the sheet
    shows it, takes the nearest for the rest, and keeps its own colors where
    it has them), a pixel whose color is never drawn made 0. The sheet is the
    image at its size or made so (`_middles`), the rest of the entry the
    game's (`game_sheet`); the effect's file is written from it at half the
    size (`classic_of`). `base` is the mod's picture of the summon already,
    whose colors are kept and whose sheet is what "left as the sheet shows
    it" is told by. Raises `EffectPictureError` saying why where the image
    can't be the sheet.
    """
    base_data = bytes(base.data) if base is not None and is_same_shape(base.data, game) else bytes(game)
    base_sheet = bytes(base.remastered) if base is not None and base.remastered is not None \
        and len(base.remastered) == SUMMON_BYTES else bytes(game_sheet)
    size = summon_size(game)
    width, _height = size
    scale = summon_scale_of(image.size, size)
    old = summon_words(base_data)
    cluts = bytearray(texture_of(base_data).cluts)
    off = brought = 0
    if image.mode == "P" and max(image.tobytes(), default=0) < 256:
        new_numbers = image.tobytes()
        blended = _most_blended(old)
        for n, color in enumerate(_palette_of(image)[:256]):
            if n == 0 or _same_color(color, old[n]):
                continue
            struct.pack_into("<H", cluts, 2 * n, word_for(color, old[n], blended))
            brought += 1
    else:
        shown_part = summon_region(base_sheet, size)
        told = shown_part if scale == 1 else _blocks(shown_part, width, scale)
        new_numbers, off = _nearest(image, told, old)
    colors = list(struct.unpack_from("<256H", cluts, 0))
    new_numbers = see_through(new_numbers, [0] + colors[1:])
    region = new_numbers if scale == 1 else _middles(new_numbers, width * scale, scale)
    game_region = summon_region(game_sheet, size)
    art = EffectArt(written(game, bytes(cluts), classic_of(game, game_region, region, colors)),
                    remastered=with_region(game_sheet, region, size))
    art.scale, art.big, art.big_eight = 2 * scale, bytes(new_numbers), True
    count = 0
    if off:                                       # (a numbered image's pixels are its own numbers: none off)
        import numpy as np
        own, count = oc.own_of(np.asarray(image.convert("RGBA")), new_numbers, old)
        if own is not None:
            art.own, art.own_view = own, PLAIN
    return Taken(art, off, brought, count)


def is_games_summon(art: Optional[EffectArt], game: bytes, game_sheet: bytes) -> bool:
    """Whether a summon's picture leaves both its sheet and the effect's file as the game has them (no picture of the
    mod's: nothing to write)."""
    return art is not None and art.data == game and art.remastered == game_sheet and not art.has_own \
        and art.times == 1


def summon_shown(art: Optional[EffectArt], data: bytes, game_sheet: bytes) -> tuple:
    """`(width, height, numbers, times)`: the picture a page shows of a summon: the mod's at its size where it is the
    sheet's or twice it (`times` 1 or 2), else the sheet's drawn part, the mod's own (an older mod's picture's made
    so) or the game's."""
    width, height = summon_size(data)
    if art is not None and art.big is not None and art.scale in (2, 4):
        times = art.scale // 2
        return width * times, height * times, art.big, times
    entry = art.remastered if art is not None and art.remastered is not None else game_sheet
    return width, height, summon_region(entry, (width, height)), 1


def summon_shows_own(art: Optional[EffectArt]) -> bool:
    """Whether a summon's picture is shown in its own colors (one of more colors at its sheet's size or twice it)."""
    return art is not None and art.has_own and art.scale in (2, 4)


def summon_seen(data: bytes) -> list:
    """Each of a summon's sheet's numbers' opacity as a page shows it (0 see through, 255 drawn)."""
    return [shown(word)[3] for word in summon_words(data)]


def summon_rgba(art: EffectArt, data: bytes) -> bytes:
    """A summon's picture of more colors as a page shows it: red, green, blue and opacity a pixel at its size."""
    return oc.drawn(art.big, art.own, summon_seen(data))


def summon_png(art: Optional[EffectArt], data: bytes, game_sheet: bytes) -> bytes:
    """The picture a page shows of a summon (`summon_shown`) as a PNG: of numbered colors, color 0 see through, or of
    its own colors where it has them; what `summon_from_image` reads back number for number and color for color."""
    width, height, numbers, _times = summon_shown(art, data, game_sheet)
    if summon_shows_own(art):
        from PIL import Image
        out = io.BytesIO()
        Image.frombytes("RGBA", (width, height), summon_rgba(art, data)).save(out, format="PNG")
        return out.getvalue()
    return png_of(width, height, numbers, summon_words(data))


def remastered_of(art: EffectArt, game: bytes, game_sheet: bytes) -> bytes:
    """
    A summon's own sheet made from a picture of an older mod, which had none:
    from its picture at the sheet's size (twice the effect's file's) as it is,
    at twice that from the middle of each block, at three times the effect's
    file's from the pixel nearest each one's middle; from its effect's file
    alone, each of the file's pixels that isn't the game's a two by two block
    over the game's sheet. A number never drawn is 0.
    """
    import numpy as np
    size = summon_size(art.data)
    width, height = size
    colors = [0] + words(art.data, PLAIN)[1:]
    if art.big is not None and art.big_eight and art.scale == 2:
        region = bytes(art.big)
    elif art.big is not None and art.big_eight and art.scale == 4:
        region = _middles(art.big, 2 * width, 2)
    elif art.big is not None and art.big_eight and art.scale == 3:
        grid = np.frombuffer(bytes(art.big), dtype=np.uint8).reshape(3 * height // 2, 3 * width // 2)
        rows, columns = (6 * np.arange(height) + 3) // 4, (6 * np.arange(width) + 3) // 4
        region = grid[rows][:, columns].tobytes()
    else:
        cw, ch, mine = sheet(art.data, PLAIN)
        _w, _h, theirs = sheet(game, PLAIN)
        mine_grid = np.frombuffer(bytes(mine), dtype=np.uint8).reshape(ch, cw)
        changed = mine_grid != np.frombuffer(bytes(theirs), dtype=np.uint8).reshape(ch, cw)
        doubled = np.repeat(np.repeat(mine_grid, 2, axis=0), 2, axis=1)
        moved = np.repeat(np.repeat(changed, 2, axis=0), 2, axis=1)
        given = np.frombuffer(summon_region(game_sheet, size), dtype=np.uint8).reshape(height, width)
        region = np.where(moved, doubled, given).astype(np.uint8).tobytes()
    return with_region(game_sheet, see_through(region, colors), size)


def summon_sheet_file(art: EffectArt) -> bytes:
    """
    A summon's sheet bigger or of more colors as Mod Studio Framework reads
    one (`BigTextures.ReadSheet`), the whole entry at the picture's size
    against the sheet (1 or 2 times): "MSBT", version 1, 8 bits a pixel, its
    scale, its width and height, then its rows, a byte a pixel; or a sheet of
    more colors (`own_colors.sheet_file`, its color numbers 8 bits, its
    palette the effect's first block as the file has it).
    """
    import numpy as np
    times = art.times
    width, height = summon_size(art.data)
    side = SUMMON_SIDE * times
    numbers = np.zeros((side, side), dtype=np.uint8)
    numbers[:height * times, :width * times] = np.frombuffer(bytes(art.big), dtype=np.uint8) \
        .reshape(height * times, width * times)
    if art.has_own:
        own = np.zeros((side, side, 3), dtype=np.uint8)
        own[:height * times, :width * times] = np.frombuffer(bytes(art.own), dtype=np.uint8) \
            .reshape(height * times, width * times, 3)
        return oc.sheet_file(times, side, side, numbers.tobytes(), own.tobytes(), words(art.data, PLAIN), 8)
    return MAGIC + bytes((1, 8)) + struct.pack("<HII", times, side, side) + numbers.tobytes()


def summon_sheets(art: Optional[dict]) -> list:
    """What the mod's `ModStudioTextures.json` names of its summons' sheets for Mod Studio Framework, in its list of
    Sprites: `[({"Entry": the sheet's entry, "Effect": its number, "File": the file's path}, the file)]`, by number;
    a summon's picture at its sheet's own size in no more colors is the mod loader's file alone."""
    return [({"Entry": summon_entry(number), "Effect": number, "File": summon_big_file(number)}, summon_sheet_file(own))
            for number, own in sorted((art or {}).items())
            if own is not None and own.is_summon and is_summon(number) and own.needs_sheet]


def named_summons(mod_root) -> list:
    """What a mod's `ModStudioTextures.json` names of its summons' sheets: each of its Sprites `{"Entry", "File"}`
    whose Entry is a summon's and whose File is inside `ModStudioTextures/`, in the file's order."""
    from . import sprite_textures as st
    try:
        named = json.loads((Path(mod_root) / st.FILE).read_text(encoding="utf-8")).get("Sprites", [])
    except (OSError, ValueError, AttributeError):
        return []
    entries = {summon_entry(number) for number in SUMMONS}
    out = []
    for one in named if isinstance(named, list) else []:
        if not isinstance(one, dict):
            continue
        entry, rel = one.get("Entry"), one.get("File")
        if isinstance(entry, int) and not isinstance(entry, bool) and entry in entries and isinstance(rel, str):
            rel = rel.replace("\\", "/")
            if rel.startswith(BIG_FOLDER + "/") and ".." not in rel:
                out.append({"Entry": entry, "File": rel})
    return out


def read_summons(mod_root, art: dict, game_dir) -> tuple:
    """
    (The thirty fourth session) The summons' own sheets of a mod read back,
    after `read` and `read_big`: `([the files that are theirs now], [what
    couldn't be read])`; `art` is given them. A summon's sheet as the mod
    loader takes it (`summon_file`, 262,144 bytes) is the picture's where the
    mod has a picture of that effect, or its effect's file is the game's or
    absent (the picture is then made of the game's); one of an effect whose
    file the mod carries as it is stays carried too. A summon's picture with
    no sheet of its own (an older mod's) has one made of it (`remastered_of`).
    The framework's sheets `ModStudioTextures.json` names for them are the
    pictures' too (they are written again from the pictures).
    """
    root = Path(mod_root)
    taken, problems = [], []
    if not game_dir:
        return taken, problems
    named = {}
    for one in named_summons(root):
        named.setdefault(one["Entry"], one["File"])
    for number in SUMMONS:
        path = root / summon_file(number)
        if number not in art and not path.is_file():
            continue
        game_sheet = game_summon(game_dir, number)
        if game_sheet is None:
            continue
        own = art.get(number)
        if own is None:
            try:
                game = ef.effect_path(game_dir, number).read_bytes()
                mine = (root / file_of(number)).read_bytes() if (root / file_of(number)).is_file() else game
            except OSError:
                continue
            if mine != game:
                continue                          # the mod carries the effect's file as it is: its sheet too
            own = art[number] = EffectArt(mine)
            if (root / file_of(number)).is_file():
                taken.append(file_of(number))
        if path.is_file():
            try:
                raw = path.read_bytes()
            except OSError as exc:
                raw = b""
                problems.append(SUMMON_BAD.format(file=summon_file(number), why=exc))
            if len(raw) == SUMMON_BYTES:
                own.remastered = raw
            elif raw:
                problems.append(SUMMON_BAD.format(file=summon_file(number),
                                                  why=f"it holds {len(raw):,} bytes, and a summon's sheet "
                                                      f"{SUMMON_BYTES:,}"))
            taken.append(summon_file(number))     # (one that can't be read is made again from the picture)
        if own.remastered is None:
            try:
                game = ef.effect_path(game_dir, number).read_bytes()
            except OSError:
                continue
            own.remastered = remastered_of(own, game, game_sheet)
        if summon_entry(number) in named:
            taken.append(named[summon_entry(number)])
    return taken, problems
