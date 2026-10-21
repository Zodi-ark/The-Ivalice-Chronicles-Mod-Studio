"""
The game's own fonts (`system/graphics/font2/*.fnt` and their pictures), read
so that the Event Editor's balloons and UI Layouts' words are measured and
drawn in the game's letters (Zodi, 19 October: "they are available in the
unpacked game files but for whatever reason mod studio can not display them
... support these fonts in the textures page and use them in the UI Layouts
page and Event Editor page. The font that the speech bubbles use in English is
ffto_bouwsmatext-master_font").

**Which font is which.** The game's `UIFontType` table names each font's file
(11 is `FFTO_BouwsmaText-Master.fnt`, 0 `FFTO_BunyanPro-Regular.fnt`) and
`UIFontSet` picks one per language for each kind of words: the second of its
eight is the English one. Set 58's is 11, Bouwsma Text, the balloons' font as
Zodi says; set 0's, the first, is 0, Bunyan Pro, which UI Layouts uses for its
boxes' words (which set a box of a layout uses isn't in the layout file).

**The file**, worked out here from his fifteen (nothing published describes
it), every number little-endian:

    0x00  "FNT ", then the version (4)
    0x08  u32  the length of the two names after the header
    0x12  u16  how many glyphs;  0x14  u16  how many kerning entries
    0x18  f32  the line's height, the ascent and the descent (then the ink's
               highest and lowest), in units of 64 to the em
    0x2E  u16  the atlas's width and height in the units its glyphs' places
               are given in: twice its pixels, in all fifteen
    0x40  the atlas's name and the kerning file's
          (`system\\graphics\\font2\\FFTO_BouwsmaText-Master_font.tex`)
    then  65,536 u16: each character's glyph, by its code (0: none)
    then  32 bytes a glyph: u16, then how many kerning entries it has and the
          first of them (u16 each), u16; f32 where its picture starts from the
          pen across and down (negative: left of it and above the line), f32
          how far the pen goes on; u32 0; u16 x, y, width and height of its
          picture, in the atlas's units
    then  12 bytes a kerning entry: the last and the first glyph (u16 each)
          of those it is for when they come next, f32 how much closer, u32 0

**The units** are 64 to the em: the Latin fonts' capitals come out 0.68 to
0.70 of it (Bouwsma's H 44.9 high), as a typeface's do, and his screenshot's
"I-I don't know." measures 268 at the balloon's 44 pixels, under the 310 that
makes the smallest box, which his screenshot is. Each picture is a signed
distance field: 128 on the glyph's edge, more inside, less outside, 16 to the
atlas's pixel; drawn at 48 pixels to the em with 16 of field round every
glyph (21.33 of the units, the bearing of a glyph with no ink), its places
given at twice its pixels. Measured on four of the fonts, not assumed:
`dev/test_game_fonts.py`.

Nothing of the game's is in Mod Studio: the fonts are read from the unpacked
game (or the mod's copy) on the machine it runs on.
"""
from __future__ import annotations

import array
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

#: Where the game keeps its fonts, under the unpacked game.
FONT_FOLDER = "system/graphics/font2"
#: The English balloons' font (`UIFontType` 11, set 58's English one).
BALLOON_FONT = "FFTO_BouwsmaText-Master"
#: The English font of the game's other words (`UIFontType` 0, set 0's English one).
UI_FONT = "FFTO_BunyanPro-Regular"

#: A glyph's numbers are for a 64 pixel size: at `size` pixels, times size / 64.
EM = 64.0
#: The atlas's pixels to the em, and the field's value where a glyph's edge is
#: and how much it changes over one of them.
ATLAS_PER_EM = 48.0
EDGE = 128.0
FIELD_PER_PIXEL = 16.0

_HEADER = 0x40
_GLYPH = 32
_KERN = 12
_CHARACTERS = 65536


class FontError(ValueError):
    """A file that can't be read as one of the game's fonts."""


@dataclass(frozen=True)
class Glyph:
    """One glyph: where its picture is in the atlas (its units), where it goes
    from the pen and how far the pen goes on (units of 64 to the em)."""
    left: float
    top: float
    advance: float
    x: int
    y: int
    width: int
    height: int
    kern_count: int = 0
    kern_first: int = 0

    @property
    def has_picture(self) -> bool:
        return self.width > 0 and self.height > 0


@dataclass
class GameFont:
    """A font as the game's file has it (see the module's notes)."""
    name: str
    line_height: float
    ascent: float
    descent: float
    atlas_width: int
    atlas_height: int
    atlas_name: str
    glyphs: list
    kerning: list                                    # [(first, last, amount)]
    #: Each character's glyph, by its code (array of u16).
    characters: array.array = field(repr=False, default_factory=lambda: array.array("H"))

    def index(self, char: str) -> int:
        """The glyph of a character, 0 when the font hasn't it."""
        code = ord(char)
        return self.characters[code] if code < len(self.characters) else 0

    def glyph(self, char: str) -> Optional[Glyph]:
        index = self.index(char)
        return self.glyphs[index] if 0 < index < len(self.glyphs) else None

    def kern(self, left: int, right: int) -> float:
        """How much closer glyph `right` comes after glyph `left` (units, negative: closer)."""
        if not 0 < left < len(self.glyphs):
            return 0.0
        glyph = self.glyphs[left]
        for first, last, amount in self.kerning[glyph.kern_first:glyph.kern_first + glyph.kern_count]:
            if first <= right <= last:
                return amount
        return 0.0

    def line_width(self, text: str, size: float) -> float:
        """How wide one line of `text` is at `size` pixels, kerned (a character the font
        hasn't takes a space's room, as the game leaves one)."""
        total = 0.0
        before = 0
        blank = self.glyph(" ")
        for char in text:
            index = self.index(char)
            if 0 < index < len(self.glyphs):
                total += self.glyphs[index].advance + (self.kern(before, index) if before else 0.0)
                before = index
            else:
                total += blank.advance if blank is not None else EM / 4
                before = 0
        return total * size / EM

    def width(self, text: str, size: float) -> float:
        """The widest of `text`'s lines at `size` pixels."""
        return max((self.line_width(line, size) for line in str(text or "").split("\n")), default=0.0)


def read_font(data: bytes, name: str = "") -> GameFont:
    """A font file's contents; `FontError` for a file that isn't one, or is damaged."""
    if len(data) < _HEADER or data[:4] != b"FNT ":
        raise FontError("not one of the game's fonts (it does not start with FNT)")
    try:
        names = struct.unpack_from("<I", data, 8)[0]
        glyph_count, kern_count = struct.unpack_from("<HH", data, 0x12)
        line_height, ascent, descent = struct.unpack_from("<3f", data, 0x18)
        atlas_width, atlas_height = struct.unpack_from("<HH", data, 0x2E)
        characters_at = _HEADER + names
        glyphs_at = characters_at + 2 * _CHARACTERS
        kerning_at = glyphs_at + _GLYPH * glyph_count
        if kerning_at + _KERN * kern_count > len(data):
            raise FontError("the file is shorter than its glyphs and kerning need")
        end = data.find(b"\0", _HEADER, characters_at)
        atlas_name = data[_HEADER:end if end >= 0 else characters_at].decode("utf-8", "replace")
        characters = array.array("H")
        characters.frombytes(data[characters_at:glyphs_at])
        if sys.byteorder != "little":
            characters.byteswap()
        glyphs = []
        for k in range(glyph_count):
            at = glyphs_at + _GLYPH * k
            _a, count, first, _d = struct.unpack_from("<4H", data, at)
            left, top, advance = struct.unpack_from("<3f", data, at + 8)
            x, y, w, h = struct.unpack_from("<4H", data, at + 24)
            if first + count > kern_count:
                count = 0
            glyphs.append(Glyph(left, top, advance, x, y, w, h, count, first))
        kerning = []
        for k in range(kern_count):
            last, first, amount = struct.unpack_from("<HHf", data, kerning_at + _KERN * k)
            kerning.append((first, last, amount))
    except struct.error as exc:
        raise FontError(f"the file is damaged ({exc})") from None
    if not glyph_count or not atlas_width or not atlas_height:
        raise FontError("the file has no glyphs, or no atlas to draw them from")
    for char_glyph in set(characters):
        if char_glyph >= glyph_count:
            raise FontError("a character names a glyph the file hasn't")
    return GameFont(name, line_height, ascent, descent, atlas_width, atlas_height, atlas_name, glyphs, kerning,
                    characters)


def font_relative(name: str) -> str:
    """A font's file under the unpacked game, as the game names it."""
    return f"{FONT_FOLDER}/{name}.fnt"


def atlas_relative(name: str) -> str:
    """A font's picture under the unpacked game, as the game names it."""
    return f"{FONT_FOLDER}/{name}_font.tex"


def find_file(game_dir, relative: str, replacements: Optional[dict] = None) -> Optional[Path]:
    """
    A file of the game's: the mod's copy (`replacements`, by its path under the
    game) else the unpacked game's, found whatever the case of its letters (the
    game's tables write `FFTO_BouwsmaText-Master.fnt`, the unpacked file can be
    `ffto_bouwsmatext-master.fnt`, and only Windows doesn't mind).
    """
    wanted = relative.replace("\\", "/").lower()
    for rel, source in (replacements or {}).items():
        if str(rel).replace("\\", "/").lower() == wanted:
            path = Path(source["source_path"] if isinstance(source, dict) else source)
            if path.is_file():
                return path
    if not game_dir:
        return None
    path = Path(game_dir) / relative
    if path.is_file():
        return path
    folder = Path(game_dir)
    for part in wanted.split("/"):
        try:
            found = next((child for child in folder.iterdir() if child.name.lower() == part), None)
        except OSError:
            return None
        if found is None:
            return None
        folder = found
    return folder if folder.is_file() else None
