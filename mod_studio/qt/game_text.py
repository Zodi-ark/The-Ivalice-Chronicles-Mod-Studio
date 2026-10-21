"""
Words drawn in the game's own letters (`game_fonts`): each glyph cut from its
font's atlas, a signed distance field, at the size asked, edged where the
field says the glyph's edge is, in the colour asked.

**Laid out** as the game's text boxes lay words: lines broken at spaces to
fit the box, and at line ends; each glyph after the one before it by its
advance and the font's kerning, and the box's letter spacing (a text box's
`spacing`, pixels: the event's words without a balloon have 2); the first
line's baseline the font's ascent down from the top, each next line a set
distance below (the layout's font size and line gap). A character the font
hasn't leaves a space's room.

**Edged** with a pixel's softening, and **outlined** (the balloon's name) by
drawing the glyph grown by the outline's width under it, which a distance
field gives for nothing. **Italics** (WotL Restoration's `<i>`) slant the
glyphs, the font having no italic of its own.

The pictures are cut on whichever thread asks (a job's, for a balloon) and
kept, `KEEP_MOST` of them, by glyph, size, colour and outline.
"""
from __future__ import annotations

import math
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor, QImage, QPainter, QTransform

from .. import game_fonts as gf

#: How far an italic glyph leans: across, for each pixel up.
SLANT = 0.2
#: Glyph pictures kept, by what they show.
KEEP_MOST = 4096


@dataclass
class Placed:
    """A glyph laid out: its index in the font, where its pen is on its line, and whether it leans."""
    index: int
    x: float
    italic: bool


@dataclass
class Line:
    glyphs: list
    width: float


class GameText:
    """A font made ready to draw: `font` (`game_fonts.GameFont`) and its atlas as a grey picture."""

    def __init__(self, font: gf.GameFont, atlas: QImage):
        import numpy as np
        self.font = font
        grey = atlas.convertToFormat(QImage.Format_Grayscale8)
        width, height = grey.width(), grey.height()
        rows = np.frombuffer(grey.constBits(), np.uint8, count=grey.bytesPerLine() * height)
        self.field = rows.reshape(height, grey.bytesPerLine())[:, :width].astype(np.float32)
        #: The atlas's pixels to one of its units (its glyphs' places are given in units).
        self.scale = width / max(1, font.atlas_width)
        self._kept: dict = {}
        # UI Layouts draws on a worker's thread, more than one at a time.
        self._lock = threading.Lock()

    # -- measuring and laying out ---------------------------------------------------------

    def width(self, text: str, size: float) -> float:
        return self.font.width(text, size)

    def layout(self, runs, size: float, width: Optional[float], spacing: float = 0.0) -> list:
        """
        `runs` (`[(words, italic)]`, "\\n" a new line) as lines no wider than
        `width` pixels at `size` (None: never broken but at "\\n"), `spacing`
        pixels more after each letter: `[Line]`. A line is broken at the last
        space that lets it fit; a word wider than the line by itself is left
        whole on a line of its own.
        """
        font = self.font
        unit = size / gf.EM
        lines, glyphs, x, before = [], [], 0.0, 0
        last_space = None                  # (index in glyphs, pen after it)

        def finish():
            nonlocal glyphs, x, before, last_space
            end = glyphs[-1].x + font.glyphs[glyphs[-1].index].advance * unit if glyphs else 0.0
            lines.append(Line(glyphs, end))
            glyphs, x, before, last_space = [], 0.0, 0, None

        for words, italic in runs:
            for char in str(words):
                if char == "\n":
                    finish()
                    continue
                index = font.index(char)
                known = 0 < index < len(font.glyphs)
                if not known:
                    index = font.index(" ")
                advance = (font.glyphs[index].advance if 0 < index < len(font.glyphs) else gf.EM / 4) * unit
                advance += spacing
                if known and before:
                    x += font.kern(before, index) * unit
                if char == " ":
                    glyphs.append(Placed(index, x, italic))
                    x += advance
                    last_space = (len(glyphs) - 1, x)
                    before = 0
                    continue
                if width is not None and glyphs and x + advance > width + 0.01 and last_space is not None:
                    # Broken at the last space: what came after it starts the next line.
                    at, pen = last_space
                    carried = glyphs[at + 1:]
                    rest = x - pen
                    glyphs = glyphs[:at]
                    finish()
                    for placed in carried:
                        glyphs.append(Placed(placed.index, placed.x - pen, placed.italic))
                    x = rest
                    before = carried[-1].index if carried else 0
                glyphs.append(Placed(index, x, italic))
                x += advance
                before = index if known else 0
        finish()
        return lines

    # -- drawing --------------------------------------------------------------------------

    def height(self, lines: int, size: float, pitch: float) -> float:
        """How tall `lines` lines are at `size`, `pitch` apart: the first's ascent to the last's descent."""
        return max(0, lines - 1) * pitch + (self.font.ascent - self.font.descent) * size / gf.EM

    def draw(self, p: QPainter, runs, left: float, top: float, width: Optional[float], size: float,
             pitch: float, colour: QColor, outline: Optional[tuple] = None, align: int = 0,
             lines: Optional[list] = None, spacing: float = 0.0) -> QRectF:
        """
        Draws `runs` laid out in `width` from (`left`, `top`) at `size`
        pixels, `pitch` from one line's baseline to the next, `spacing` more
        after each letter, in `colour`; `outline` (`(colour, pixels)`) drawn
        round every glyph first; each line to the left (`align` 0), centred
        (1) or to the right (2) of `width`. `lines` are the runs laid out
        already, if they are. Returns where the words are: their lines' extent.
        """
        lines = lines if lines is not None else self.layout(runs, size, width, spacing)
        ascent = self.font.ascent * size / gf.EM
        passes = ([(QColor(outline[0]), float(outline[1]))] if outline else []) + [(QColor(colour), 0.0)]
        for paint, grow in passes:
            for row, line in enumerate(lines):
                baseline = top + ascent + row * pitch
                shift = 0.0
                if width is not None and align in (1, 2):
                    shift = (width - line.width) / (2 if align == 1 else 1)
                for placed in line.glyphs:
                    cut = self.glyph_image(placed.index, size, paint, grow)
                    if cut is None:
                        continue
                    image, dx, dy = cut
                    pen = QPointF(left + shift + placed.x, baseline)
                    if placed.italic:
                        p.save()
                        p.setTransform(QTransform(1, 0, -SLANT, 1, SLANT * pen.y(), 0), True)
                        p.drawImage(QPointF(pen.x() + dx, pen.y() + dy), image)
                        p.restore()
                    else:
                        p.drawImage(QPointF(pen.x() + dx, pen.y() + dy), image)
        widest = max((line.width for line in lines), default=0.0)
        return QRectF(left, top, widest, self.height(len(lines), size, pitch))

    def glyph_image(self, index: int, size: float, colour: QColor, grow: float = 0.0) -> Optional[tuple]:
        """
        `(picture, left, top)`: glyph `index` at `size` pixels in `colour`,
        grown by `grow` pixels all round, and where its picture goes from the
        pen on the line (pixels, whole: the picture is drawn at whole pixels
        so the glyph stays sharp). None for a glyph with nothing to draw.
        """
        import numpy as np
        if not 0 < index < len(self.font.glyphs):
            return None
        glyph = self.font.glyphs[index]
        if not glyph.has_picture:
            return None
        key = (index, round(size, 2), colour.rgba(), round(grow, 2))
        with self._lock:
            if key in self._kept:
                return self._kept[key]
        unit = size / gf.EM
        # The picture's units to the font's: the atlas's to the em is twice its pixels to the em.
        to_units = gf.EM / (gf.ATLAS_PER_EM / self.scale) if self.scale else 1.0
        left, top = glyph.left * unit, glyph.top * unit
        wide, high = glyph.width * to_units * unit, glyph.height * to_units * unit
        x0, y0 = math.floor(left), math.floor(top)
        columns = max(1, math.ceil(left + wide) - x0)
        rows = max(1, math.ceil(top + high) - y0)
        # Each pixel's middle, where it falls in the atlas.
        per_pixel_x = glyph.width * self.scale / wide
        per_pixel_y = glyph.height * self.scale / high
        xs = glyph.x * self.scale + ((np.arange(columns) + x0 + 0.5) - left) * per_pixel_x - 0.5
        ys = glyph.y * self.scale + ((np.arange(rows) + y0 + 0.5) - top) * per_pixel_y - 0.5
        values = _bilinear(self.field, xs, ys)
        # Edged over a pixel: the field changes FIELD_PER_PIXEL for each of the
        # atlas's pixels, and one of these is per_pixel of them.
        per = gf.FIELD_PER_PIXEL * max(per_pixel_x, 1e-6)
        alpha = np.clip((values - gf.EDGE + grow * per) / per + 0.5, 0.0, 1.0)
        if not alpha.any():
            with self._lock:
                self._kept[key] = None
            return None
        out = np.empty((rows, columns, 4), np.uint8)
        a = alpha * colour.alphaF()
        out[..., 0] = np.round(a * colour.blue()).astype(np.uint8)
        out[..., 1] = np.round(a * colour.green()).astype(np.uint8)
        out[..., 2] = np.round(a * colour.red()).astype(np.uint8)
        out[..., 3] = np.round(a * 255).astype(np.uint8)
        image = QImage(out.data, columns, rows, columns * 4, QImage.Format_ARGB32_Premultiplied).copy()
        made = (image, float(x0), float(y0))
        with self._lock:
            if len(self._kept) >= KEEP_MOST:
                self._kept.pop(next(iter(self._kept)))
            self._kept[key] = made
        return made


def _bilinear(field, xs, ys):
    """`field` (rows by columns) read between its pixels at every (`ys`, `xs`), clamped at its sides."""
    import numpy as np
    height, width = field.shape
    x = np.clip(xs, 0, width - 1)
    y = np.clip(ys, 0, height - 1)
    x0 = np.floor(x).astype(np.int64)
    y0 = np.floor(y).astype(np.int64)
    x1 = np.minimum(x0 + 1, width - 1)
    y1 = np.minimum(y0 + 1, height - 1)
    fx = (x - x0)[None, :]
    fy = (y - y0)[:, None]
    top = field[y0][:, x0] * (1 - fx) + field[y0][:, x1] * fx
    bottom = field[y1][:, x0] * (1 - fx) + field[y1][:, x1] * fx
    return top * (1 - fy) + bottom * fy


def load(font_path, atlas_picture) -> GameText:
    """A font's file and its atlas (an RGBA PIL picture, read as the Textures page reads it) made ready."""
    font = gf.read_font(Path(font_path).read_bytes(), Path(font_path).stem)
    grey = atlas_picture.convert("L")
    image = QImage(grey.tobytes(), grey.width, grey.height, grey.width, QImage.Format_Grayscale8).copy()
    return GameText(font, image)
