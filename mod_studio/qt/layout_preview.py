"""
Draws a UI layout (.uib) the way the game would show it, for the UI
Layouts page.

Every box goes where the file puts it, and each picture is the real texture
piece: the `.utexpt` names the rectangle, the `.tex` is decoded the same way
the Textures page decodes it (FF16Tools, cached on disk). Checked against
Zodi's in-game screenshots of the tavern and Rumors screens - the panels
land within a few pixels of the game's, and the tavern background exactly.

What the preview cannot know, and does not pretend to:

- **Text.** What a text box says comes from the game's text tables or its
  code. The preview writes the box's own name in it, at its font size and
  alignment, so the size and place are right and the words are obviously a
  stand-in. They are in the game's own letters (Zodi, 19 October: "use them
  in the UI Layouts page"): the menus' English font, Zilvertype Pro Bold
  (`MENU_FONT`, as his screenshots of the tavern's rumors and the units,
  status and equipment screens show), and the talk window's and the event
  balloon's, Bouwsma Text (`words_font`), read from the unpacked game
  (`Pictures.game_text`), lines broken and placed as the game's are
  (`game_text`). Which font set each box uses isn't in the layout file, so
  a box the game draws in another (Jura SemiBold, for the gil and a unit's
  level) is drawn in that one too. A game unpacked without the fonts has a
  serif stand in.
- **Blur.** The game blurs what is behind a few overlays (`BGBlur`,
  `ffto_common_black_blur`). In the file those are plain rectangles - white,
  in the tavern's case - so drawing them as written would whiten the whole
  screen. Anything whose name says "blur" is left out.
- **What code decides.** Which background a chapter uses, how many list
  rows there are, and what fills an empty slot are all chosen while the
  game runs. The file's own values are drawn. But for one:
- **The menus' talk window** (`ffto_common_talk_window.uib`'s TalkWindow,
  on the tavern, the shops, the guilds and more) is as wide as the game
  makes it while it runs, not as the file places it (Zodi, 19 October:
  "it is noticeably longer and the portrait is further to the right in
  game"): its words as wide as the screen's `SizeDefine` allows
  (`TextWidthMax`, 1,234 measured at its 44 pixel letters), at the window's
  own English letters (`ScrollText_EnFrDe`, 34), so 954, and its margins
  (213); its parchment centred where the file centres the piece; the
  words' boxes as wide, the face at the window's right end
  (`talk_window`). Measured on his screenshot of the tavern: the parchment
  335 to 1,588 across and 105 to 309 down, drawn here 335 to 1,587 and 106
  to 309; the face's right edge at the parchment's, as in the game. Every
  one of the 18 screens placing it (the tavern's, the shops', the guilds',
  the Poachers' Den's, the Brave Story's, status, removing a unit) has a
  `SizeDefine` of 1,234. The game may make it narrower for a short line,
  as it does the event balloon; both screenshots of the tavern have it at
  the most, and the picture has no words to measure, so it is drawn so.
- **Masks** are not applied, and Bezier, ellipse and counter boxes are not
  drawn; they are still listed and selectable.

**A piece placed at another size** (`fitted_sizes`). 868 of the 3,516
references in the game's 252 layouts place a component at a size not its
own: the common window, 600 by 600, at 800 by 584 on the BGM screen, its
tab buttons, 280 wide, at 396. The game lays the piece out at the
reference's size - Zodi's screenshot of that screen has the window 800 by
584 and each tab's highlight and title across 396 - by stretching what
spans the piece: a box from its left edge (or before) to its right (or
past) grows with its width, one from its top to its bottom with its
height, and a group that grows lays its own boxes out the same way. Boxes
that don't span it keep their place and size. The files hold no anchoring
for this, so what the game does with a box at one edge only is not known;
it is drawn where the file puts it. Drawn at the component's own size, as
before 5 October, the window behind the BGM list was too small for it.

The screen is drawn in one of its states: each component's `HomePosition`
keys, then the chosen timeline's (usually `Show`) at their last frame -
position, scale, opacity and colour. That is close to how a screen looks
once it has finished opening.

Drawing happens on a worker thread, onto a QImage, which Qt allows.
"""
from __future__ import annotations

import struct
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QTransform

from .. import game_fonts as gf
from .. import texture_data as td
from .. import uib
from . import game_text
from .workers import Worker

#: Blend modes the preview can reproduce, by the file's number.
_COMPOSITION = {
    1: QPainter.CompositionMode_Darken,
    2: QPainter.CompositionMode_Multiply,
    3: QPainter.CompositionMode_ColorBurn,
    5: QPainter.CompositionMode_Lighten,
    6: QPainter.CompositionMode_Screen,
    7: QPainter.CompositionMode_ColorDodge,
    8: QPainter.CompositionMode_Plus,
    9: QPainter.CompositionMode_Overlay,
    10: QPainter.CompositionMode_SoftLight,
    11: QPainter.CompositionMode_HardLight,
}

#: Decoded sheets kept between drawings, by total size. Editing a number
#: redraws the screen, and decoding a .tex means running FF16Tools - so a
#: sheet is decoded once per session, not once per keystroke.
SHEET_CACHE_BYTES = 600 * 1024 * 1024

_DEPTH_LIMIT = 16


@dataclass
class DrawnBox:
    """Where one box ended up on the canvas, for clicking and outlining."""
    key: str                  # "Component/Path" in the file the box is from
    file: str                 # that file's path under the unpacked game
    kind: str
    rect: QRectF              # bounding rectangle in canvas pixels
    visible: bool             # False when fully transparent in this state
    owner: str                # the box in the SCREEN BEING EDITED this was reached through
    effect: bool = False      # drawn by a component that blends (a filter, a glow)
    #: Where the box's position is measured from, mapped onto the canvas:
    #: everything above the box - groups, the piece it is in, the pieces
    #: placing that - scaled, turned and moved. A drag on the canvas is
    #: turned back through it into a change of the box's own position.
    parent: QTransform = field(default_factory=QTransform)


@dataclass
class DrawResult:
    image: QImage
    component: str            # the component drawn
    boxes: list = field(default_factory=list)       # DrawnBox, back to front
    missing: dict = field(default_factory=dict)     # picture -> why it isn't shown
    empty_slots: list = field(default_factory=list)  # keys of pieces the game fills in


class SheetCache:
    """Decoded texture sheets as QImages, least recently used first out."""

    def __init__(self, limit: int = SHEET_CACHE_BYTES):
        self.limit = limit
        self._items = OrderedDict()
        self._bytes = 0
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            image = self._items.get(key)
            if image is not None:
                self._items.move_to_end(key)
            return image

    def put(self, key, image: QImage) -> None:
        with self._lock:
            if key in self._items:
                return
            self._items[key] = image
            self._bytes += image.sizeInBytes()
            while self._bytes > self.limit and len(self._items) > 1:
                _old_key, old = self._items.popitem(last=False)
                self._bytes -= old.sizeInBytes()

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
            self._bytes = 0


SHEETS = SheetCache()


def pil_to_qimage(image) -> QImage:
    # The decoders already hand back RGBA; converting again copied the whole
    # sheet once more for nothing.
    rgba = image if image.mode == "RGBA" else image.convert("RGBA")
    data = rgba.tobytes("raw", "RGBA")
    return QImage(data, rgba.width, rgba.height, rgba.width * 4,
                  QImage.Format_RGBA8888).copy()


def tex_size(path: Path) -> Optional[tuple]:
    """A .tex's width and height from its header, without decoding it."""
    try:
        with open(path, "rb") as f:
            head = f.read(0x36)
        return struct.unpack_from("<HH", head, 0x32) if len(head) >= 0x36 else None
    except OSError:
        return None


class DrawCancelled(Exception):
    """A newer drawing was asked for, so this one stops where it is."""


#: The game's fonts made ready, by their files: each read once, a few kept.
_FONTS: "OrderedDict" = OrderedDict()
_FONTS_LOCK = threading.Lock()
FONTS_KEPT = 4


class Pictures:
    """
    Finds and decodes the texture pieces a layout names.

    `decode(path) -> PIL.Image` is swappable, so the suites can stand in for
    FF16Tools, which cannot run on the machines they run on.

    `cancelled() -> bool` says a drawing is no longer wanted. The painter
    asks it before each box - a box decodes at most one sheet, the slow
    step - so a drawing nobody is waiting for stops at its next box.
    """

    def __init__(self, game_dir: Path, texture_edits: dict | None = None,
                 decode: Optional[Callable] = None,
                 decode_replacement: Optional[Callable] = None,
                 cache: SheetCache = SHEETS,
                 cancelled: Optional[Callable] = None,
                 part_edits: dict | None = None):
        self.game_dir = Path(game_dir)
        self.texture_edits = dict(texture_edits or {})
        #: This mod's part list edits (`state.utexpt_edits`): pieces are cut
        #: where the mod puts their corners, so the picture follows them.
        self.part_edits = part_edits or {}
        self.decode = decode
        self.decode_replacement = decode_replacement or decode
        self.cache = cache
        self.cancelled = cancelled or (lambda: False)
        self._parts = {}
        self.missing = {}

    def part_list(self, rel: str):
        if rel not in self._parts:
            path = self.game_dir / rel
            try:
                data = path.read_bytes()
                if self.part_edits.get(rel):
                    data, _problems = uib.apply_part_edits(data, self.part_edits[rel])
                self._parts[rel] = uib.read_part_list(data)
            except (OSError, uib.UibError) as exc:
                self._parts[rel] = None
                self.missing[rel] = f"its part list could not be read ({exc})"
        return self._parts[rel]

    def sheet(self, texture_rel: str) -> Optional[QImage]:
        replacement = (self.texture_edits.get(texture_rel) or {}).get("source_path")
        path = Path(replacement) if replacement else self.game_dir / texture_rel
        try:
            stat = path.stat()
            key = (str(path), stat.st_size, int(stat.st_mtime))
        except OSError:
            self.missing[texture_rel] = "the texture file isn't there"
            return None
        image = self.cache.get(key)
        if image is None:
            decode = self.decode_replacement if replacement else self.decode
            try:
                image = pil_to_qimage(decode(path))
            except Exception as exc:                              # noqa: BLE001
                self.missing[texture_rel] = str(exc) or exc.__class__.__name__
                return None
            self.cache.put(key, image)
        return image

    def game_text(self, name: str):
        """
        The game's font `name` made ready (`game_text.GameText`): its file
        from the unpacked game, its atlas the mod's replacement or the game's,
        decoded as the sheets are. None when the game hasn't it (a serif then
        stands in).
        """
        font_path = gf.find_file(self.game_dir, gf.font_relative(name))
        wanted = gf.atlas_relative(name).lower()
        replacement = next(((entry or {}).get("source_path") for rel, entry in self.texture_edits.items()
                            if str(rel).replace("\\", "/").lower() == wanted), None)
        atlas_path = Path(replacement) if replacement else gf.find_file(self.game_dir, gf.atlas_relative(name))
        if font_path is None or atlas_path is None:
            return None
        try:
            key = tuple((str(path), path.stat().st_size, int(path.stat().st_mtime))
                        for path in (Path(font_path), Path(atlas_path)))
        except OSError:
            return None
        with _FONTS_LOCK:
            if key in _FONTS:
                _FONTS.move_to_end(key)
                return _FONTS[key]
        decode = self.decode_replacement if replacement else self.decode
        try:
            text = game_text.load(font_path, decode(atlas_path))
        except Exception as exc:                                      # noqa: BLE001
            self.missing[gf.font_relative(name)] = str(exc) or exc.__class__.__name__
            text = None
        with _FONTS_LOCK:
            _FONTS[key] = text
            while len(_FONTS) > FONTS_KEPT:
                _FONTS.popitem(last=False)
        return text

    def piece(self, ref: uib.TextureRef) -> Optional[QImage]:
        if not ref.uri:
            return None
        parts = self.part_list(ref.part_list_path)
        if parts is None:
            return None
        sheet = self.sheet(parts.texture_path)
        if sheet is None:
            return None
        if ref.part == 0 or ref.part >= len(parts.parts):
            # Part 0 means the whole sheet; its own rectangle is stale in
            # some files and the game does not use it literally.
            return sheet
        x1, y1, x2, y2 = self.on_sheet(parts, ref.part, sheet)
        return sheet.copy(x1, y1, max(1, x2 - x1), max(1, y2 - y1))

    def on_sheet(self, parts, index: int, sheet: QImage) -> tuple:
        """
        Part `index`'s corners on `sheet` as decoded. They are in the game
        sheet's pixels; on a replacement at another resolution they are
        scaled to it. Whether the GAME scales them like this is not known -
        see the research notes' 2x question.
        """
        x1, y1, x2, y2 = parts.parts[index].rect
        game_size = tex_size(self.game_dir / parts.texture_path)
        if game_size and game_size[0] and game_size[1] and \
                (sheet.width(), sheet.height()) != tuple(game_size):
            fx, fy = sheet.width() / game_size[0], sheet.height() / game_size[1]
            x1, x2, y1, y2 = round(x1 * fx), round(x2 * fx), round(y1 * fy), round(y2 * fy)
        return x1, y1, x2, y2


class Layouts:
    """
    The screen being drawn, and any other layout files it places pieces
    from - each with this mod's edits applied, or the mod's own copy where
    it carries one whole (`overrides`).
    """

    def __init__(self, game_dir: Path, uib_edits: dict | None = None,
                 overrides: dict | None = None):
        self.game_dir = Path(game_dir)
        self.uib_edits = uib_edits or {}
        self.overrides = overrides or {}
        self._loaded = {}

    def get(self, rel: str) -> Optional[uib.Layout]:
        if rel not in self._loaded:
            try:
                if rel in self.overrides:
                    data = Path(self.overrides[rel]).read_bytes()
                else:
                    data = (self.game_dir / rel).read_bytes()
                    edits = self.uib_edits.get(rel)
                    if edits:
                        data, _problems = uib.apply_edits(data, edits)
                self._loaded[rel] = uib.Layout(data)
            except (OSError, uib.UibError):
                self._loaded[rel] = None
        return self._loaded[rel]


def resting_state(component: uib.Component, timeline: str) -> dict:
    """
    `{box name: {"origin", "size", "scale", "opacity", "colour"}}` after
    the component's HomePosition keys and then `timeline`'s, each at its
    last frame.
    """
    state = {}
    for name in ("HomePosition", timeline):
        if name not in component.timelines:
            continue
        for key in sorted((k for k in component.keys if k.timeline == name),
                          key=lambda k: k.frame):
            if not key.target or not key.values:
                continue
            entry = state.setdefault(key.target, {})
            if key.kind == uib.KEY_POSITION:
                entry["origin"] = key.values
            elif key.kind == uib.KEY_SIZE:
                entry["size"] = key.values
            elif key.kind == uib.KEY_SCALE:
                entry["scale"] = key.values
            elif key.kind == uib.KEY_OPACITY:
                entry["opacity"] = key.values[0]
            elif key.kind == uib.KEY_COLOUR:
                entry["colour"] = key.values
    return state


def _is_blur(name: str) -> bool:
    return "blur" in (name or "").lower()


_WHITE = (255, 255, 255, 255)


def _times(outer, inner) -> tuple:
    """
    Two colours multiplied channel by channel: how a group's colour tints
    what is inside it. A group or a placed component has nothing of its own
    to draw, so its colour can only mean this - and the game gives 377 of
    its 5,158 a colour that is not white, 41 of those black (a shadow drawn
    as a darkened copy). Inferred, like the rest of the drawing; not yet
    checked in the game.
    """
    if tuple(outer) == _WHITE:
        return tuple(inner)
    if tuple(inner) == _WHITE:
        return tuple(outer)
    return tuple(round(a * b / 255) for a, b in zip(outer, inner))


def _qcolour(rgba) -> QColor:
    """A box colour - red, green, blue, alpha, the order the file keeps them in."""
    red, green, blue, alpha = rgba
    return QColor(red, green, blue, alpha)


def _nine_slice(painter: QPainter, piece: QImage, w: float, h: float, margins) -> None:
    pw, ph = piece.width(), piece.height()
    left, top, right, bottom = margins
    left, right = min(left, pw // 2), min(right, pw // 2)
    top, bottom = min(top, ph // 2), min(bottom, ph // 2)
    xs_src = [0, left, pw - right, pw]
    ys_src = [0, top, ph - bottom, ph]
    xs_dst = [0, left, max(left, w - right), w]
    ys_dst = [0, top, max(top, h - bottom), h]
    for i in range(3):
        for j in range(3):
            src = QRectF(xs_src[i], ys_src[j], xs_src[i + 1] - xs_src[i], ys_src[j + 1] - ys_src[j])
            dst = QRectF(xs_dst[i], ys_dst[j], xs_dst[i + 1] - xs_dst[i], ys_dst[j + 1] - ys_dst[j])
            if src.width() > 0 and src.height() > 0 and dst.width() > 0 and dst.height() > 0:
                painter.drawImage(dst, piece, src)


def _tinted(piece: QImage, rgba) -> QImage:
    """The piece multiplied by the box's colour, the way the game tints it."""
    red, green, blue, _alpha = rgba
    if (red, green, blue) == (255, 255, 255):
        return piece
    tinted = piece.convertToFormat(QImage.Format_ARGB32_Premultiplied)
    p = QPainter(tinted)
    p.setCompositionMode(QPainter.CompositionMode_Multiply)
    p.fillRect(tinted.rect(), QColor(red, green, blue))
    p.setCompositionMode(QPainter.CompositionMode_DestinationIn)
    p.drawImage(0, 0, piece)
    p.end()
    return tinted


_TEXT_H = {1: Qt.AlignHCenter, 2: Qt.AlignRight}
_TEXT_V = {1: Qt.AlignVCenter, 2: Qt.AlignBottom}


def fitted_sizes(boxes, state: dict, frame: tuple, size: tuple, out: Optional[dict] = None) -> dict:
    """
    `{box key: (width, height)}` for the boxes of a piece laid out at `size`
    rather than its own `frame` (see the module's notes): each box spanning
    the frame across grows or shrinks with its width, each spanning it down
    with its height, and a group that changes size lays its own boxes out
    the same way, in its own frame. Sizes as `state` (the drawn state's
    keys) leaves them.
    """
    out = {} if out is None else out
    fw, fh = frame
    dw, dh = size[0] - fw, size[1] - fh
    if not (dw or dh) or fw <= 0 or fh <= 0:
        return out
    for box in boxes:
        s = state.get(box.name, {})
        x, y = s.get("origin", box.origin)
        w, h = s.get("size", box.size)
        grow_w = dw if x <= 0 and x + w >= fw else 0
        grow_h = dh if y <= 0 and y + h >= fh else 0
        if not (grow_w or grow_h):
            continue
        new = (max(0, w + grow_w), max(0, h + grow_h))
        out[box.key] = new
        if box.kind == "Layer":
            fitted_sizes(box.children, state, (w, h), new, out)
    return out


#: The menus' talk window (see the module's notes): the file and piece, its
#: boxes that move with its right end, and those whose width grows with it.
#: The English font of the game's menus' words. Zodi's screenshots (19
#: October, 16:40) of the tavern's rumors and the units, status and
#: equipment screens: the rumor's title, 294 pixels of ink at its box's 36,
#: and the list's names, 261 at 32, are Zilvertype Pro Bold's 295 and 262
#: (Bunyan Pro's, which UI Layouts drew in before, 304 and 270), and its
#: letters and its old style figures (HP 999/999) are his screenshots'. The
#: commonest English font of the game's font sets too (`UIFontSet`: 56 of
#: 100, `UIFontType` 5). The gil, the party's count and a unit's level are
#: in Jura SemiBold (6), which the layout file doesn't tell apart.
MENU_FONT = "FFTO_Zilvertype Pro Bold"
#: The layouts whose words are a balloon's, in the balloons' font (Bouwsma
#: Text, `game_fonts.BALLOON_FONT`, Zodi: "The font that the speech bubbles
#: use in English is ffto_bouwsmatext-master_font").
BALLOON_LAYOUTS = frozenset({"ffto_common_talk_window.uib", "ffto_event_balloon.uib"})


def words_font(file_rel: str) -> str:
    """The game's font a layout's words are drawn in: the balloons' for a balloon's layout, else the menus'."""
    name = str(file_rel).replace("\\", "/").rsplit("/", 1)[-1].lower()
    return gf.BALLOON_FONT if name in BALLOON_LAYOUTS else MENU_FONT


TALK_WINDOW = ("ui/ffto/common/ffto_common_talk_window.uib", "TalkWindow")
TALK_RIGHT = frozenset({"Face"})
TALK_GROW = frozenset({"ScrollText_EnFrDe", "ScrollText"})
#: The talk window's words in English, French and German (the game's Ja
#: and EnFrDe animations show one or the other).
TALK_WORDS = "ScrollText_EnFrDe"


def _walk(boxes):
    for box in boxes:
        yield box
        yield from _walk(box.children)


def talk_window(screen: uib.Layout, talk: uib.Layout) -> Optional[float]:
    """
    How wide the game makes the talk window on `screen`: its words as wide as
    the screen's `SizeDefine` allows, at the window's own letters, and its
    margins. None when either file hasn't what it takes.
    """
    size_define = screen.components.get("SizeDefine")
    window = talk.components.get(TALK_WINDOW[1])
    if size_define is None or window is None:
        return None
    widest = next((b for b in _walk(size_define.boxes) if b.name == "TextWidthMax"), None)
    words = next((b for b in _walk(window.boxes) if b.name == TALK_WORDS), None)
    piece = talk.components.get(words.reference_name) if words is not None else None
    letters = next((b for b in _walk(piece.boxes) if b.kind == "Text"), None) if piece is not None else None
    if widest is None or not widest.font_size or letters is None or not letters.font_size:
        return None
    return widest.size[0] * letters.font_size / widest.font_size + (window.size[0] - words.size[0])


class _Painter:
    """One drawing of one screen. See `draw_layout`."""

    def __init__(self, layouts: Layouts, pictures: Pictures, timeline: str,
                 image: QImage, result: DrawResult):
        self.layouts, self.pictures, self.timeline = layouts, pictures, timeline
        self.image, self.result = image, result
        #: How many blending components the box being placed is inside.
        self._effects = 0

    def _layer(self) -> tuple:
        layer = QImage(self.image.size(), QImage.Format_ARGB32_Premultiplied)
        layer.fill(Qt.transparent)
        lp = QPainter(layer)
        lp.setRenderHint(QPainter.SmoothPixmapTransform, True)
        lp.setRenderHint(QPainter.Antialiasing, True)
        lp.setRenderHint(QPainter.TextAntialiasing, True)
        return layer, lp

    @staticmethod
    def _composite(p: QPainter, layer: QImage, mode=None) -> None:
        p.save()
        p.resetTransform()
        p.setOpacity(1.0)
        if mode is not None:
            p.setCompositionMode(mode)
        p.drawImage(0, 0, layer)
        p.restore()

    def component(self, p: QPainter, file_rel: str, lay: uib.Layout, c: uib.Component,
                  transform: QTransform, opacity: float, owner: Optional[str],
                  depth: int, record: bool = True, paint: bool = True,
                  tint: tuple = _WHITE, size: Optional[tuple] = None, talk: bool = False) -> None:
        """
        A component drawn at `transform`; at `size`, the placing box's, laid
        out to it. `talk`: a talk window at the width the game gives it, its
        face at its right end and its words as wide (see the module's notes).
        """
        state = resting_state(c, self.timeline)
        sizes = fitted_sizes(c.boxes, state, tuple(c.size), tuple(size)) if size else {}
        if talk and size:
            grown = size[0] - c.size[0]
            for box in _walk(c.boxes):
                if box.name in TALK_RIGHT:
                    s = state.setdefault(box.name, {})
                    x, y = s.get("origin", box.origin)
                    s["origin"] = (x + grown, y)
                elif box.name in TALK_GROW:
                    w, h = sizes.get(box.key, state.get(box.name, {}).get("size", box.size))
                    sizes[box.key] = (w + grown, h)
        mode = _COMPOSITION.get(c.blend)
        self._effects += c.blend != 0
        try:
            if mode is not None and depth > 0 and paint:
                layer, lp = self._layer()
                try:
                    self.boxes(lp, file_rel, lay, c.boxes, state, transform, opacity, owner,
                               depth, record, tint=tint, sizes=sizes)
                finally:
                    # Ended even when the drawing stops part-way: a layer
                    # thrown away while its painter is still open is freed
                    # under that painter.
                    lp.end()
                self._composite(p, layer, mode)
            else:
                self.boxes(p, file_rel, lay, c.boxes, state, transform, opacity, owner, depth,
                           record, paint, tint, sizes=sizes)
        finally:
            self._effects -= c.blend != 0

    def boxes(self, p, file_rel, lay, boxes, state, parent, parent_opacity, owner, depth,
              record, paint=True, tint=_WHITE, sizes=None):
        """
        One list of sibling boxes. A Mask box hides the siblings listed after
        it (up to the next mask) outside its shape; that is how the file
        orders them in every one of the 198 masks in the game.

        With `paint` off nothing is drawn, but every box's place is still
        recorded - a box hidden in this state can still be picked from the
        list, and its outline shows where it would be.
        """
        runs, mask, current = [], None, []
        for box in boxes:
            if box.kind == "Mask":
                runs.append((mask, current))
                mask, current = box, []
            else:
                current.append(box)
        runs.append((mask, current))
        # The first box in a list is drawn in front, so drawing starts at
        # the back. Measured on the tavern: its background is listed last.
        sizes = sizes or {}
        for mask, run in reversed(runs):
            if mask is None:
                for box in reversed(run):
                    self.box(p, file_rel, lay, box, state, parent, parent_opacity, owner, depth,
                             record, paint, tint, sizes)
                continue
            m_transform, m_alpha, m_rect = self.geometry(mask, state, parent, parent_opacity, sizes)
            if record:
                self.result.boxes.append(DrawnBox(mask.key, file_rel, mask.kind, m_rect,
                                                  False, owner or mask.key, parent=parent))
            if not run:
                continue
            if not paint:
                for box in reversed(run):
                    self.box(p, file_rel, lay, box, state, parent, parent_opacity, owner, depth,
                             record, False, sizes=sizes)
                continue
            layer, lp = self._layer()
            try:
                for box in reversed(run):
                    self.box(lp, file_rel, lay, box, state, parent, parent_opacity, owner, depth,
                             record, tint=tint, sizes=sizes)
            finally:
                lp.end()
            shape, sp = self._layer()
            try:
                self.mask_shape(sp, file_rel, lay, mask, m_transform, owner, depth,
                                self.size_of(mask, state, sizes))
            finally:
                sp.end()
            cut = QPainter(layer)
            cut.setCompositionMode(QPainter.CompositionMode_DestinationIn)
            cut.drawImage(0, 0, shape)
            cut.end()
            self._composite(p, layer)

    def mask_shape(self, p, file_rel, lay, mask, transform, owner, depth, size) -> None:
        """
        Draws what a mask lets through: its texture piece if it has one (40
        masks), else the component it names drawn in place (157 - often a
        text box, so text shows through a coloured bar), else its own box.
        """
        w, h = size
        piece = self.pictures.piece(mask.textures[0]) if mask.textures else None
        if piece is not None:
            p.save()
            p.setTransform(transform)
            p.drawImage(QRectF(0, 0, w, h), piece)
            p.restore()
        elif mask.mask_name in lay.components and depth < _DEPTH_LIMIT:
            self.component(p, file_rel, lay, lay.components[mask.mask_name], transform,
                           1.0, owner, depth + 1, record=False, size=size)
        else:
            p.save()
            p.setTransform(transform)
            p.fillRect(QRectF(0, 0, w, h), QColor(255, 255, 255))
            p.restore()

    @staticmethod
    def size_of(box, state, sizes=None) -> tuple:
        """
        The box's size in this state: as the piece it is in is laid out
        (`fitted_sizes`), else a size key's, else the file's.
        """
        fitted = (sizes or {}).get(box.key)
        return fitted if fitted is not None else state.get(box.name, {}).get("size", box.size)

    @staticmethod
    def geometry(box, state, parent: QTransform, parent_opacity: float, sizes=None) -> tuple:
        s = state.get(box.name, {})
        ox, oy = s.get("origin", box.origin)
        sx, sy = s.get("scale", box.scale)
        ax, ay = box.anchor
        fitted = (sizes or {}).get(box.key)
        if fitted is not None:
            # Its pivot keeps its place in it: half way stays half way.
            w0, h0 = s.get("size", box.size)
            ax = ax * fitted[0] / w0 if w0 else ax
            ay = ay * fitted[1] / h0 if h0 else ay
        local = QTransform()
        local.translate(ox + ax, oy + ay)
        if box.rotation:
            local.rotateRadians(box.rotation)
        local.scale(sx, sy)
        local.translate(-ax, -ay)
        transform = local * parent
        own = s.get("opacity", box.opacity)
        if own != own:                        # NaN in a file reads as hidden
            own = 0.0
        alpha = parent_opacity * max(0.0, min(1.0, own))
        w, h = fitted if fitted is not None else s.get("size", box.size)
        rect = transform.mapRect(QRectF(0, 0, w, h))
        return transform, alpha, rect

    def _game_words(self, p, file_rel, box, transform, alpha, colour, w, h) -> bool:
        """
        A Text box's words (its name) in the game's font for its layout
        (`words_font`): at its size, its lines `line_height` further apart
        than that, broken to its width, aligned as it says. False when the
        game's font isn't to be had.
        """
        text = self.pictures.game_text(words_font(file_rel))
        if text is None:
            return False
        size = max(1, int(box.font_size or 24))
        pitch = size + max(0, int(box.line_height or 0))
        lines = text.layout([(box.name, False)], size, w)
        tall = text.height(len(lines), size, pitch)
        top = {1: (h - tall) / 2, 2: h - tall}.get(box.v_align, 0.0)
        p.save()
        p.setTransform(transform)
        p.setOpacity(alpha)
        p.setClipRect(QRectF(0, 0, w, h))
        text.draw(p, None, 0.0, top, w, size, pitch, _qcolour(colour), align=box.h_align, lines=lines)
        p.restore()
        return True

    def box(self, p, file_rel, lay, box, state, parent, parent_opacity, owner, depth, record,
            paint=True, tint=_WHITE, sizes=None) -> None:
        if self.pictures.cancelled():
            raise DrawCancelled()
        if _is_blur(box.name) or (box.kind == "Reference" and _is_blur(box.reference_name)):
            return
        transform, alpha, rect = self.geometry(box, state, parent, parent_opacity, sizes)
        s = state.get(box.name, {})
        # A colour key's four bytes and the box's own are in the same order
        # (red, green, blue, alpha), so either is used as it is.
        colour = _times(tint, s.get("colour", box.colour))
        w, h = self.size_of(box, state, sizes)
        this_owner = owner or box.key
        visible = paint and alpha > 0.01
        if record:
            self.result.boxes.append(DrawnBox(box.key, file_rel, box.kind, rect,
                                              visible, this_owner, self._effects > 0,
                                              parent=parent))
        if not visible:
            # Nothing of it is drawn; its boxes are still placed, so they
            # can be outlined when picked from the list.
            if record and box.kind == "Layer":
                self.boxes(p, file_rel, lay, box.children, state, transform, 0.0, owner,
                           depth, record, False, sizes=sizes)
            elif record and box.kind == "Reference" and not box.reference_file \
                    and box.reference_name in lay.components and depth < _DEPTH_LIMIT:
                self.component(p, file_rel, lay, lay.components[box.reference_name],
                               transform, 0.0, owner, depth + 1, record, False, size=(w, h))
            return
        if box.kind == "Layer":
            self.boxes(p, file_rel, lay, box.children, state, transform, alpha, owner, depth, record,
                       tint=colour, sizes=sizes)
        elif box.kind == "Reference":
            if depth >= _DEPTH_LIMIT:
                return
            if box.reference_file:
                other_rel = uib.layout_path_for(box.reference_file)
                other = self.layouts.get(other_rel)
                target = other.components.get(box.reference_name) if other else None
                if other is None:
                    self.pictures.missing[other_rel] = "the layout file isn't there"
                    return
                if target is None:
                    if record:
                        self.result.empty_slots.append(box.key)
                    return
                if (other_rel, box.reference_name) == TALK_WINDOW:
                    wide = talk_window(lay, other)
                    if wide is not None:
                        # As wide as the game makes it, the window's parchment
                        # (its nine grid, which overhangs the piece more on the
                        # left) centred where the file centres the piece.
                        nine = next((b for b in _walk(target.boxes) if b.kind == "Ninegrid"), None)
                        off = (nine.origin[0] + nine.size[0] / 2 - target.size[0] / 2) if nine else 0.0
                        moved = QTransform()
                        moved.translate(-(wide - w) / 2 - off, 0)
                        self.component(p, other_rel, other, target, moved * transform, alpha,
                                       this_owner, depth + 1, record, tint=colour, size=(wide, h),
                                       talk=True)
                        return
                self.component(p, other_rel, other, target, transform, alpha,
                               this_owner, depth + 1, record, tint=colour, size=(w, h))
            elif box.reference_name in lay.components:
                self.component(p, file_rel, lay, lay.components[box.reference_name],
                               transform, alpha, owner, depth + 1, record, tint=colour, size=(w, h))
            elif record:
                self.result.empty_slots.append(box.key)
        elif box.kind in ("Image", "Ninegrid"):
            piece = self.pictures.piece(box.textures[0]) if box.textures else None
            if piece is None:
                return
            piece = _tinted(piece, colour)
            p.save()
            p.setTransform(transform)
            p.setOpacity(alpha * (colour[3] / 255))
            if box.kind == "Ninegrid":
                _nine_slice(p, piece, w, h, box.margins)
            else:
                p.drawImage(QRectF(0, 0, w, h), piece)
            p.restore()
        elif box.kind == "Rect":
            p.save()
            p.setTransform(transform)
            p.setOpacity(alpha)
            p.fillRect(QRectF(0, 0, w, h), _qcolour(colour))
            p.restore()
        elif box.kind == "Text" and w > 2 and h > 2 and self._game_words(p, file_rel, box, transform, alpha, colour,
                                                                           w, h):
            pass
        elif box.kind == "Text" and w > 2 and h > 2:
            p.save()
            p.setTransform(transform)
            p.setOpacity(alpha)
            font = QFont()
            font.setStyleHint(QFont.Serif)
            font.setFamilies(["Georgia", "Times New Roman", "DejaVu Serif", "serif"])
            font.setPixelSize(max(1, int(box.font_size or 24)))
            p.setFont(font)
            p.setPen(QPen(_qcolour(colour)))
            flags = _TEXT_H.get(box.h_align, Qt.AlignLeft) | _TEXT_V.get(box.v_align, Qt.AlignTop)
            p.setClipRect(QRectF(0, 0, w, h))
            p.drawText(QRectF(0, 0, w, h), int(flags) | int(Qt.TextWordWrap), box.name)
            p.restore()


def draw_layout(layouts: Layouts, pictures: Pictures, rel: str, timeline: str = "Show",
                component: Optional[str] = None) -> DrawResult:
    """
    Draws `rel`'s root component - or `component`, when the box being edited
    belongs to one the root never places - in the state `timeline` leaves it.
    """
    layout = layouts.get(rel)
    if layout is None:
        raise uib.UibError(f"{rel} could not be read as a UI layout")
    comp = layout.components.get(component) if component else layout.root
    if comp is None:
        comp = layout.root
    width, height = (max(1, comp.size[0]), max(1, comp.size[1]))
    image = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
    image.fill(QColor(0, 0, 0))
    result = DrawResult(image=image, component=comp.name)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.TextAntialiasing, True)
    try:
        _Painter(layouts, pictures, timeline, image, result).component(
            painter, rel, layout, comp, QTransform(), 1.0, None, 0)
    finally:
        # Ended whatever happens, a cancelled drawing included: a painter
        # left open on an image that is then thrown away is a Qt warning at
        # best.
        painter.end()
    result.missing = dict(pictures.missing)
    return result


def draw_sheet(pictures: Pictures, part_list: str) -> DrawResult:
    """
    A part list's texture sheet as the picture, with each of its parts as a
    box (`part/<n>`) - the page's view of the sheet a picture is cut from.
    Part 0, the whole sheet, is not a box. Parts are placed as pieces are cut
    (`Pictures.on_sheet`), so on a replacement of another size they are
    scaled to it.
    """
    parts = pictures.part_list(part_list)
    if parts is None:
        raise uib.UibError(f"{part_list} could not be read")
    sheet = pictures.sheet(parts.texture_path)
    if sheet is None:
        raise uib.UibError(f"its texture sheet could not be loaded: "
                           f"{pictures.missing.get(parts.texture_path, parts.texture_path)}")
    result = DrawResult(image=sheet, component=part_list)
    for index in range(1, len(parts.parts)):
        x1, y1, x2, y2 = pictures.on_sheet(parts, index, sheet)
        result.boxes.append(DrawnBox(f"part/{index}", part_list, "Part",
                                     QRectF(x1, y1, x2 - x1, y2 - y1), True, f"part/{index}"))
    return result


def default_decoder(cli_path, cache_dir) -> Callable:
    def decode(path: Path):
        return td.load_game_texture_preview(Path(path), cli_path, cache_dir)
    return decode


def default_replacement_decoder(cli_path, cache_dir) -> Callable:
    def decode(path: Path):
        return td.load_replacement_preview(Path(path), cli_path, cache_dir)
    return decode


class DrawWorker(Worker):
    """
    One drawing of one screen, off the interface thread.

    **It can be stopped.** A screen with many sheets to decode takes a while
    to draw the first time, and someone moving through the list does not
    wait for it: the page asks the drawing it no longer wants to stop
    (`cancel`), and it does, at its next box. It used to run to
    the end - every sheet of a screen already left behind - while the one
    landed on waited its turn. `_RunningThreads.stop_all` asks too, so
    closing the window mid-drawing does not wait out a whole screen.
    """

    def __init__(self, token, game_dir, rel, uib_edits, texture_edits, timeline,
                 component, decode, decode_replacement, overrides=None,
                 part_edits=None, sheet=None):
        super().__init__()
        self._stop = threading.Event()
        self.token = token
        self.game_dir, self.rel = Path(game_dir), rel
        # Copies: the page's stores keep changing while this runs.
        self.uib_edits = {r: {k: dict(v) for k, v in boxes.items()}
                          for r, boxes in (uib_edits or {}).items()}
        self.part_edits = {r: {i: {"name": e["name"], "rect": list(e["rect"])}
                               for i, e in parts.items()}
                           for r, parts in (part_edits or {}).items()}
        #: A part list's path: draw its sheet (`draw_sheet`), not the screen.
        self.sheet = sheet
        self.texture_edits = {r: dict(v) for r, v in (texture_edits or {}).items()}
        self.overrides = dict(overrides or {})
        self.timeline, self.component = timeline, component
        self.decode, self.decode_replacement = decode, decode_replacement

    def cancel(self) -> None:
        """Asks the drawing to stop at its next box. Safe from any thread."""
        self._stop.set()

    def run(self):
        pictures = Pictures(self.game_dir, self.texture_edits, self.decode,
                            self.decode_replacement, cancelled=self._stop.is_set,
                            part_edits=self.part_edits)
        if self.sheet:
            return {"token": self.token, "result": draw_sheet(pictures, self.sheet),
                    "sheet": self.sheet}
        try:
            result = draw_layout(Layouts(self.game_dir, self.uib_edits, self.overrides),
                                 pictures, self.rel, self.timeline, self.component)
        except DrawCancelled:
            # Reported as finished, not failed: stopping is not an error, and
            # the page turns this away by its out-of-date token.
            return {"token": self.token, "result": None, "cancelled": True}
        return {"token": self.token, "result": result}
