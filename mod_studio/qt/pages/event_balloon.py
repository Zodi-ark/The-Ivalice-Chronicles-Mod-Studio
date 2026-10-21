"""
The Event Editor's speech balloon and face, drawn as the game draws them:
from the game's own pictures, laid out by the game's own layout files.

Zodi, 19 October, with event 045 in the game beside the page: "Why are we
not using that for the event editor", of the talk window UI Layouts shows,
and the balloons' pictures sent with it. The first build drew a parchment
box of its own measured off one screenshot; this one uses the game's.

**The pictures** (`ui/ffto/event/texture/`, each with its part list under
`textureparts/`, the mod's copy first): `ui_event_balloon_normal_uitx`,
`_round_` and `_spike_` are the box, stretched across as a nine grid;
`_tail_` holds the tails (part 4 pointing down, 6 up; 8 and 9 the spiky
ones; 12 to 17 a thought's bubbles) and the name's shadow (10);
`_mask_face_` the shapes the face is cut to at the box's end (1 normal,
2 round, 3 spike).

**The layout** is `ui/ffto/event/ffto_event.uib`'s `Balloon`, 900 by 210,
read once from Zodi's copy and written below as numbers: the box's nine
grid 7 left of it and 23 above, 17 wider; the face's (`FaceRight`) 169 in
from its right end and 8 down, inside `FaceMaskBalloon` of
`ui/ffto/common/face/ffto_facial_animation.uib` (the mask 25 left and 47
above it, the face 1.1 times its size); the words (`ScrollText_EnFrDe`,
English, French and German) 41 in and 24 down, 42 pixels with 12 between
lines, in brown (70, 51, 39); the name's board 18 in and 31 above the top;
the tail below (31, 189) or above (23, -60) its layer.

**How wide** (`SizeDefine` in the same file): the words measured at the
42 pixels they are drawn at, kept between 310 (`TextWidthMin`) and 1,234
(`TextWidthMax`), and 245 more for the margins and the face (74 without a
face, the `LayerNone` words being 826 of the 900). Zodi's screenshots
measure 555 for "I-I don't know." and 1,479 for Dycedarg's two lines, the
least and the most, and 541 for event 008's "All right, everybody, fall
in!" without a face: 469 at 42 pixels (the first build measured at the 44
`SizeDefine` names, 492, and made that box 566).

**The letters** are the game's own: the English balloons' font, Bouwsma Text
(`game_fonts.BALLOON_FONT`, Zodi, 19 October: "The font that the speech
bubbles use in English is ffto_bouwsmatext-master_font"), read from the
unpacked game and drawn from its atlas (`qt/game_text.py`), the words
measured with it too: "I-I don't know." is 256 at 42 pixels, under the 310
of the least box, as his screenshot has it. The name over the box is drawn
in it too, outlined. Without the font (a game unpacked without it) a serif
stands in (`SERIF`: Georgia on Windows), which is wider: that line comes out
304 in DejaVu Serif, still under the least.

**Where**, as the game's dialog thread places a box (the decompilation's
`message_dialog_thread`), in the remaster's pixels, measured on Zodi's five
screenshots with the map laid over each (events 008 twice, 034, 045 and
069, 19 October; the Event Editor's camera frames them as the game does,
`event_map.event_camera`):

- A box with a tail sits **above its speaker** (window 1), its bottom 92
  over the top of their picture, or **below** them (window 2), its top 120
  under their feet; its tail points down or up.
- **The face** is at the end the speaker looks from, looking the way they
  face: at the left end, turned, when they face right across the screen
  (the captain, Wiegraf), at the right end when they face left (Dycedarg,
  the Swordsman), as they face when the box opens.
- **Across**, its middle is by the speaker: 50 right of them when the face
  is at its right end, else 34 left of them (the screenshots give 21 and 80
  for the first, 36, 36 and 27 for the second, the last two Ramza's box
  without a face and Wiegraf's below him).
- It is **kept on the screen**, 193 from its sides and between 99 and 1,026
  down (the PlayStation's 22 and 228 of its 240 lines), the tail staying
  where it pointed as the box moves.
- **The node's numbers** are the remaster's pixels: Move the box across
  moves it right (and its tail with it), Up or down moves it up (event
  008's Northern Sky Captain's -260 takes his box down to the floor, where
  the game has it; the first build moved it up, off the screen: Zodi, 19
  October, "extream cases where I can not even see the text of the balloon
  at all"), and the arrow moves the tail alone. The box is kept on the
  screen before it is moved and again after, as the PlayStation does.
- A box without a tail goes across the middle, at the top (window 1), the
  bottom (2) or the middle (3), then moved.

The screen is the largest 16 by 9 picture that fits the map's view.

**The face** (`Face` in `ffto_facial_animation.uib`): two parts of
`wldface_<sprite>_08_uitx`, the eyes (`Eye00` to `Eye02`) over the mouth
(`Mouth00` to `Mouth03`), each 128 by 192 and drawn 1.25 times as wide.
`All` is the whole face, which the first build should have shown and
showed `Eye00` instead: the top half alone. The file's animations, as
numbers below: `Blink` every 180 frames, the eyes half shut, shut, half
shut over 11; `Talk_A` and `Talk_B`, 78 and 76 frames of mouths, played
while the words are read, three frames a letter (the engine's rate for a
box), up to a `<stoplip>` mark.

**Opening** (`ShowSpeedNormal`): the box grows from 0.4 of its size to
1.02 in 10 frames and settles at 1 by the 20th.

Without the pictures (a game unpacked without Textures) the box is drawn
plainly in the same place and size, and the face still from its parts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QColor, QFont, QFontMetricsF, QImage, QPainter, QPainterPath, QPen,
                           QTextBlockFormat, QTextCharFormat, QTextCursor, QTextDocument, QTextOption)

from ... import game_fonts as gf
from ..workers import Worker

# -- the game's screen, and where a box goes on it -----------------------------
SCREEN_W, SCREEN_H = 1920.0, 1080.0
#: How far a box is kept from the screen's sides, and the highest its top and
#: lowest its bottom go (see the module's notes).
SIDE_MARGIN = 193.0
TOP_MOST, BOTTOM_MOST = 99.0, 1026.0
#: A box above its speaker has its bottom this far over the top of their
#: picture; one below them, its top this far under their feet.
OVER_HEAD, UNDER_FEET = 92.0, 120.0
#: Where a box's middle is across from its speaker: with the face at its
#: right end, and otherwise (the face at its left end, or no face).
ACROSS_FACE_RIGHT, ACROSS_OTHER = 50.0, -34.0

# -- the box: ffto_event.uib's Balloon ----------------------------------------
BOX_W, BOX_H = 900.0, 210.0
TEXT_LEAST, TEXT_MOST = 310.0, 1234.0
#: The words are measured at the size they are drawn at (`TEXT_PX`).
MEASURE_PX = 42
FACE_MARGIN, PLAIN_MARGIN = 245.0, 74.0
#: Each kind's nine grid: where it starts against the box, how much wider and
#: how tall it is, its fixed ends (left, right), and the face mask's part.
NINE = {
    "normal": ((-7.0, -23.0), 17.0, 256.0, (90, 44), 1),
    "round": ((-6.0, -24.0), 15.0, 256.0, (110, 110), 2),
    "spike": ((-64.0, -56.0), 131.0, 320.0, (220, 210), 3),
}
#: The tails: the part pointing down (below the box) and up (above it), and
#: where each sits against the box, its layer included.
TAILS = {"normal": (4, 6), "spike": (8, 9)}
TAIL_SIZE = (82.0, 80.0)
TAIL_DOWN_Y, TAIL_UP_Y = 189.0, -60.0
#: A thought's bubbles: (part, y in the tail's place, height), down then up.
BUBBLES_DOWN = ((15, 0.0, 36.0), (16, 36.0, 22.0), (17, 58.0, 22.0))
BUBBLES_UP = ((14, 0.0, 22.0), (13, 22.0, 22.0), (12, 44.0, 36.0))
#: The tail is kept this far inside the box's ends (and clear of the face).
TAIL_INSET = 60.0
# The words.
TEXT_AT = (41.0, 24.0)
TEXT_PX, TEXT_GAP = 42, 12
INK = QColor(70, 51, 39)
# The name, on its board over the top left edge.
NAME_AT = (18.0, -31.0)
NAME_BOARD_H = 52.0
NAME_PX = 35
NAME_FILL, NAME_EDGE = QColor(235, 221, 204), QColor(56, 40, 28)
NAME_SHADOW_PART = 10
# The face: FaceRight in the box, FaceMaskBalloon around it.
FACE_FROM_RIGHT, FACE_TOP = 169.0, 8.0
#: `FaceLeft`: the face 12 in from the box's left end, turned to face the
#: other way, the words then 208 in (`ScrollText_EnFrDeLeft`).
FACE_FROM_LEFT, TEXT_AFTER_FACE = 12.0, 208.0
FACE_BOX = (160.0, 192.0)
MASK_AT, MASK_SIZE = (-25.0, -47.0), (254.0, 286.0)
FACE_AT, FACE_SCALE = (3.0, 1.0), 1.1
# The plain box, without the game's pictures.
PLAIN_FILL, PLAIN_EDGE = QColor("#efe7d4"), QColor("#7d6a4f")

# -- the face's parts and animations: ffto_facial_animation.uib ---------------
FACE_PARTS = ("Eye00", "Eye01", "Eye02", "Mouth00", "Mouth01", "Mouth02", "Mouth03", "All")
#: Where each part is on a face sheet when its part list isn't there (every
#: face's list in the game and WotL's are these).
FACE_RECTS = {"Eye00": (1, 1, 129, 193), "Eye01": (131, 1, 259, 193), "Eye02": (261, 1, 389, 193),
              "Mouth00": (1, 195, 129, 387), "Mouth01": (131, 195, 259, 387),
              "Mouth02": (261, 195, 389, 387), "Mouth03": (391, 195, 519, 387), "All": (391, 1, 519, 193)}
#: The animations' keys, (frame, part index): parts 1 to 3 the eyes, 4 to 7 the mouths.
BLINK = ((0, 1), (2, 2), (4, 3), (7, 3), (9, 2), (11, 1))
BLINK_EVERY = 180
#: A box's first blink comes this far into it, not as it opens.
BLINK_FIRST = 60
TALK_A = ((0, 4), (8, 5), (16, 6), (23, 7), (30, 5), (37, 6), (45, 5), (54, 4), (62, 5), (69, 7), (77, 4))
TALK_A_LONG = 78
TALK_B = ((0, 4), (7, 6), (15, 5), (23, 6), (32, 4), (40, 5), (48, 4), (57, 5), (66, 6), (75, 4))
TALK_B_LONG = 76
#: How long a box's words are read: the engine's three frames a letter.
FRAMES_A_LETTER = 3
# -- opening: ShowSpeedNormal --------------------------------------------------
OPENING = ((0, 0.4), (10, 1.02), (20, 1.0))

# The pictures' files.
BALLOON_FOLDER = "ui/ffto/event"
BALLOON_SHEETS = ("normal", "round", "spike", "tail", "mask_face")
#: The font the words are in, and the name's outline (pixels) in it.
BALLOON_FONT = gf.BALLOON_FONT
NAME_OUTLINE = 2.5


def balloon_relative(sheet: str) -> tuple:
    """Where one of the balloon's pictures and its part list are, under the unpacked game."""
    stem = f"ui_event_balloon_{sheet}_uitx"
    return f"{BALLOON_FOLDER}/texture/{stem}.tex", f"{BALLOON_FOLDER}/textureparts/{stem}.utexpt"


# =============================================================================
# Reading the pictures
# =============================================================================

#: Where a `.tex` read for a picture is kept as a `.dds`: the Textures and UI
#: Layouts pages' own cache, so a face read on one is read once.
PREVIEW_CACHE = "texture_preview_cache"


def read_picture(path, cli_path=None):
    """
    A picture as an RGBA PIL image, read as the Textures page reads it: a
    `.tex` here where this program can, else through FF16Tools (`cli_path`);
    any other picture (a mod's PNG) as it is.
    """
    from ... import paths
    from ... import texture_data as td
    cache = paths.local_data_dir() / PREVIEW_CACHE
    return td.load_replacement_preview(Path(path), cli_path, cache).convert("RGBA")


def to_qimage(picture) -> QImage:
    rgba = picture.convert("RGBA")
    return QImage(rgba.tobytes(), rgba.width, rgba.height, rgba.width * 4, QImage.Format_RGBA8888).copy()


def cut_parts(picture, parts_path) -> dict:
    """`{part index: QImage}` of a sheet, by its part list (`.utexpt`); part 0 the whole sheet."""
    from ... import uib
    whole = to_qimage(picture)
    out = {0: whole}
    if parts_path is not None and Path(parts_path).is_file():
        listed = uib.read_part_list(Path(parts_path).read_bytes())
        for index, part in enumerate(listed.parts[1:], 1):
            x1, y1, x2, y2 = part.rect
            out[index] = whole.copy(x1, y1, max(1, x2 - x1), max(1, y2 - y1))
    return out


@dataclass
class FacePieces:
    """A speaker's face sheet cut into its parts (`FACE_PARTS`), by index 1 to 8."""
    parts: dict = field(default_factory=dict)

    def part(self, index: int) -> Optional[QImage]:
        return self.parts.get(index)


def cut_face(picture, parts_path) -> FacePieces:
    """A face sheet's parts, by its part list when there is one, else where the game puts them."""
    from ... import uib
    whole = to_qimage(picture)
    rects = dict(FACE_RECTS)
    if parts_path is not None and Path(parts_path).is_file():
        for part in uib.read_part_list(Path(parts_path).read_bytes()).parts:
            if part.name in rects:
                rects[part.name] = part.rect
    pieces = FacePieces()
    for index, name in enumerate(FACE_PARTS, 1):
        x1, y1, x2, y2 = rects[name]
        if x2 > x1 and y2 > y1 and x2 <= whole.width() and y2 <= whole.height():
            pieces.parts[index] = whole.copy(x1, y1, x2 - x1, y2 - y1)
    return pieces


class PiecesJob(Worker):
    """
    Reads balloon sheets and faces off the GUI thread.

    `sources`: `{key: (picture path, part list path or None)}`, a key being a
    balloon sheet's name or `("face", sprite)`. Hands back `({key: pieces or
    None}, problem)`: a sheet as `{part: QImage}`, a face as `FacePieces`.
    """

    def __init__(self, sources: dict, cli_path=None):
        super().__init__()
        self.sources = dict(sources)
        self.cli_path = cli_path

    def run(self):
        from .. import game_text
        made, problem = {}, ""
        for key, (picture_path, parts_path) in self.sources.items():
            try:
                picture = read_picture(picture_path, self.cli_path)
                if isinstance(key, tuple) and key[0] == "font":
                    # A font: its atlas, and its file where a part list would be.
                    made[key] = game_text.load(parts_path, picture)
                else:
                    made[key] = (cut_face(picture, parts_path) if isinstance(key, tuple)
                                 else cut_parts(picture, parts_path))
            except Exception as exc:                                  # noqa: BLE001
                made[key] = None
                problem = str(exc) or exc.__class__.__name__
        return made, problem


# =============================================================================
# The face's animation
# =============================================================================

def _keyed(keys, frame: int) -> int:
    value = keys[0][1]
    for at, part in keys:
        if frame >= at:
            value = part
    return value


def eye_part(since_open: float) -> int:
    """The eyes' part `since_open` frames after the box opened: open, but for a blink every 180."""
    t = int(since_open) - BLINK_FIRST
    if t < 0:
        return 1
    return _keyed(BLINK, t % BLINK_EVERY)


def mouth_part(since_open: float, talking: float) -> int:
    """The mouth's part: Talk_A then Talk_B, over and over, for `talking` frames; shut after."""
    t = int(since_open)
    if t < 0 or t >= talking:
        return 4
    t %= TALK_A_LONG + TALK_B_LONG
    return _keyed(TALK_A, t) if t < TALK_A_LONG else _keyed(TALK_B, t - TALK_A_LONG)


def talking_frames(letters: int, lips_until: Optional[int]) -> int:
    """How long the mouth moves: while the words are read, to a stoplip mark."""
    spoken = letters if lips_until is None else min(letters, lips_until)
    return max(0, spoken) * FRAMES_A_LETTER


def opening_scale(since_open: float) -> float:
    t = max(0.0, float(since_open))
    for (a, va), (b, vb) in zip(OPENING, OPENING[1:]):
        if t < b:
            return va + (vb - va) * (t - a) / (b - a)
    return OPENING[-1][1]


# =============================================================================
# Size and place
# =============================================================================

def measure_font() -> QFont:
    font = QFont()
    font.setFamilies(SERIF)
    font.setPixelSize(MEASURE_PX)
    return font


SERIF = ["Georgia", "Palatino Linotype", "Book Antiqua", "Times New Roman", "DejaVu Serif", "serif"]


def box_width(words: str, face: bool, text=None) -> float:
    """The box's width for `words`: its widest line at 42 pixels, between the least and the most,
    measured in the game's font (`text`, a `game_text.GameText`) when there is one."""
    if text is not None:
        widest = text.width(words or "", MEASURE_PX)
    else:
        metrics = QFontMetricsF(measure_font())
        widest = max((metrics.horizontalAdvance(line) for line in (words or "").split("\n")), default=0.0)
    return max(TEXT_LEAST, min(TEXT_MOST, widest)) + (FACE_MARGIN if face else PLAIN_MARGIN)


def screen_rect(width: float, height: float) -> QRectF:
    """The game's screen in the view: the largest 16 by 9 picture that fits, centred."""
    scale = min(width / SCREEN_W, height / SCREEN_H)
    w, h = SCREEN_W * scale, SCREEN_H * scale
    return QRectF((width - w) / 2, (height - h) / 2, w, h)


@dataclass
class Placed:
    """Where a box is, in the game's screen pixels."""
    x: float
    y: float
    width: float
    tail: Optional[str]          # "down", "up" or None
    tail_x: float = 0.0          # the tail's tip, across the screen
    face_left: bool = False      # the face at the box's left end, turned (`FaceLeft`)


@dataclass
class Speaker:
    """A box's speaker on the game's screen, in its pixels: the top of their
    picture, the point they stand on, and whether they face right across it."""
    head: tuple
    ground: tuple
    faces_right: bool = False


def place(width: float, window: int, speaker: Optional[Speaker], dx: float = 0.0, dy: float = 0.0,
          arrow: float = 0.0, tail: bool = True, face: bool = True) -> Placed:
    """
    A box of `width` on the screen, as the game's dialog thread places it
    (see the module's notes). With a tail and a `speaker`: window 1 above
    them, 2 below (0 above unless they stand off the top of the screen, 3 at
    the middle); across, by them and its face's end, the face at the end
    they look from; kept on the screen,
    moved `dx` right and `dy` up and kept on it again, the tail staying
    where it pointed, moved `arrow` across, and kept inside the box's ends
    and clear of the face. Without either: across the middle, window 1 at
    the top, 2 at the bottom, 3 (or 0) in the middle, then moved.
    """
    left_most, right_most = SIDE_MARGIN, SCREEN_W - SIDE_MARGIN

    def kept(x: float, tail_off: float) -> tuple:
        """The box kept off the screen's sides, and its tail moved back by as much."""
        if width > right_most - left_most:
            centred = (SCREEN_W - width) / 2
            return centred, tail_off + x - centred
        if x < left_most:
            return left_most, tail_off + x - left_most
        if x + width > right_most:
            return right_most - width, tail_off + x + width - right_most
        return x, tail_off

    def kept_down(y: float) -> float:
        return max(TOP_MOST, min(BOTTOM_MOST - BOX_H, y))
    if speaker is None or not tail:
        x, _ = kept((SCREEN_W - width) / 2 + dx, 0.0)
        y = {1: TOP_MOST, 2: BOTTOM_MOST - BOX_H}.get(window, (SCREEN_H - BOX_H) / 2)
        return Placed(x, kept_down(y - dy), width, None)
    face_left = face and speaker.faces_right
    across = ACROSS_FACE_RIGHT if face and not face_left else ACROSS_OTHER
    x, tail_off = kept(speaker.ground[0] + across - width / 2, 0.0)
    x, tail_off = kept(x + dx, tail_off)
    tail_off += arrow
    if window == 0:
        window = 2 if speaker.ground[1] < 0 else 1
    if window == 2:
        y = speaker.ground[1] + UNDER_FEET
    elif window == 1:
        y = speaker.head[1] - OVER_HEAD - BOX_H
    else:
        y = (SCREEN_H - BOX_H) / 2
    y = kept_down(y - dy)
    way = "up" if window == 2 or (window == 3 and speaker.head[1] < y) else "down"
    # The tail kept 60 in from the box's ends, and clear of the face.
    left, right = x + TAIL_INSET, x + width - TAIL_INSET
    if face and face_left:
        left += FACE_FROM_LEFT + FACE_BOX[0] + 30.0
    elif face:
        right -= FACE_FROM_RIGHT + 30.0
    tip = max(left, min(right, x + width / 2 + tail_off))
    return Placed(x, y, width, way, tip, face_left)


# =============================================================================
# Drawing
# =============================================================================

def _nine(p: QPainter, image: QImage, target: QRectF, ends: tuple) -> None:
    """`image` stretched across `target`, its ends as they are (a nine grid fixed top to bottom)."""
    left, right = ends
    w, h = image.width(), image.height()
    left = min(left, w // 2)
    right = min(right, w - left - 1)
    scale_y = target.height() / max(1, h)
    end_l, end_r = left * scale_y, right * scale_y
    middle = max(0.0, target.width() - end_l - end_r)
    p.drawImage(QRectF(target.left(), target.top(), end_l, target.height()), image, QRectF(0, 0, left, h))
    p.drawImage(QRectF(target.left() + end_l, target.top(), middle, target.height()), image,
                QRectF(left, 0, w - left - right, h))
    p.drawImage(QRectF(target.left() + end_l + middle, target.top(), end_r, target.height()), image,
                QRectF(w - right, 0, right, h))


_TIPS: dict = {}


def _tip_x(image: QImage, down: bool) -> float:
    """Where a tail's tip is across its picture: its lowest (or highest) solid pixels' middle."""
    key = (image.cacheKey(), down)
    if key not in _TIPS:
        found = image.width() / 2.0
        rows = range(image.height() - 1, -1, -1) if down else range(image.height())
        for y in rows:
            xs = [x for x in range(image.width()) if image.pixelColor(x, y).alpha() > 128]
            if xs:
                found = (xs[0] + xs[-1]) / 2.0
                break
        _TIPS[key] = found
    return _TIPS[key]


def face_image(face: FacePieces, eye: int, mouth: int) -> Optional[QImage]:
    """The face shown: the eyes' part over the mouth's, 128 by 192."""
    top, bottom = face.part(eye), face.part(mouth)
    if top is None or bottom is None:
        return face.part(8)
    out = QImage(top.width(), top.height(), QImage.Format_ARGB32_Premultiplied)
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.drawImage(QRectF(0, 0, out.width(), out.height()), bottom)
    p.drawImage(QRectF(0, 0, out.width(), out.height()), top)
    p.end()
    return out


def masked_face(face: QImage, mask: Optional[QImage]) -> QImage:
    """The face as FaceMaskBalloon draws it: 1.25 times as wide, 1.1 times its size, cut to the mask."""
    out = QImage(int(MASK_SIZE[0]), int(MASK_SIZE[1]), QImage.Format_ARGB32_Premultiplied)
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.SmoothPixmapTransform, False)
    w, h = FACE_BOX[0] * FACE_SCALE, FACE_BOX[1] * FACE_SCALE
    centre_x = FACE_AT[0] - MASK_AT[0] + FACE_BOX[0] / 2
    centre_y = FACE_AT[1] - MASK_AT[1] + FACE_BOX[1] / 2
    p.drawImage(QRectF(centre_x - w / 2, centre_y - h / 2, w, h), face)
    if mask is not None and not mask.isNull():
        p.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        p.drawImage(QRectF(0, 0, MASK_SIZE[0], MASK_SIZE[1]), mask)
    p.end()
    return out


def text_document(rich: str, width: float) -> QTextDocument:
    """The words laid out as the box lays them out: 42 pixels, 12 between lines, in its brown."""
    document = QTextDocument()
    font = QFont()
    font.setFamilies(SERIF)
    font.setPixelSize(TEXT_PX)
    document.setDefaultFont(font)
    document.setDocumentMargin(0)
    option = QTextOption(Qt.AlignLeft)
    option.setWrapMode(QTextOption.WordWrap)
    document.setDefaultTextOption(option)
    document.setHtml(rich)
    document.setTextWidth(max(10.0, width))
    cursor = QTextCursor(document)
    cursor.select(QTextCursor.Document)
    block = QTextBlockFormat()
    fixed = QTextBlockFormat.LineHeightTypes.FixedHeight
    block.setLineHeight(TEXT_PX + TEXT_GAP, getattr(fixed, "value", fixed))
    cursor.mergeBlockFormat(block)
    char = QTextCharFormat()
    char.setForeground(INK)
    cursor.mergeCharFormat(char)
    return document


@dataclass
class Drawn:
    """What `draw` put where, in the view's pixels: for the page and its checks."""
    box: QRectF                 # the box itself (900 by 210 at width 900)
    tail_tip: Optional[QPointF]
    face: Optional[QRectF]      # the face's mask, round the face
    text: QRectF
    name: Optional[QRectF]
    kind: str
    pictures: bool              # the game's pictures, or the plain box


#: Around the box in its kept picture: room for the nine grids' overhang and the name.
PAD_SIDE, PAD_TOP, PAD_BOTTOM = 80, 64, 64
#: Kept pictures of boxes, by what they show (`_box_image`): drawing words at
#: 42 pixels each frame of an event playing would be slow.
_KEPT: dict = {}
KEEP_MOST = 48


def _sheet_key(sheets: dict) -> tuple:
    return tuple(sorted((name, tuple(sorted((part, image.cacheKey()) for part, image in (parts or {}).items())))
                        for name, parts in sheets.items()))


def _box_image(kind: str, width: float, sheets: dict, rich: str, name: Optional[str],
               face: bool, face_left: bool = False, text=None, runs=None) -> tuple:
    """
    `(picture, text rect, name rect)`: the box with its words and name drawn
    at the game's size, the box's top left at (PAD_SIDE, PAD_TOP), and where
    the words and the name went. The words in the game's font (`text`, from
    `runs`, the line's words in pieces) when there is one. Kept: the same box
    is drawn once.
    """
    key = (kind, round(width, 1), rich, name, face, face and face_left, _sheet_key(sheets),
           id(text) if text is not None else None, tuple(runs or ()))
    if key in _KEPT:
        return _KEPT[key]
    nine = NINE.get(kind, NINE["normal"])
    box_sheet = sheets.get(kind) or sheets.get("normal")
    tail_sheet = sheets.get("tail") or {}
    pictures = bool(box_sheet and box_sheet.get(0) is not None)
    image = QImage(int(width + 2 * PAD_SIDE + 0.5), int(BOX_H + PAD_TOP + PAD_BOTTOM),
                   QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    p = QPainter(image)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)
    p.translate(PAD_SIDE, PAD_TOP)
    (off_x, off_y), wider, tall, ends, _mask = nine
    if pictures:
        _nine(p, box_sheet[0], QRectF(off_x, off_y, width + wider, tall), ends)
    else:
        p.setPen(QPen(PLAIN_EDGE, 3))
        p.setBrush(PLAIN_FILL)
        p.drawRoundedRect(QRectF(0, 0, width, BOX_H), 22, 22)
    text_width = width - (FACE_MARGIN if face else PLAIN_MARGIN)
    text_x = TEXT_AFTER_FACE if face and face_left else TEXT_AT[0]
    if text is not None:
        drawn = text.draw(p, runs if runs is not None else [(rich, False)], text_x, TEXT_AT[1], text_width,
                          TEXT_PX, TEXT_PX + TEXT_GAP, INK)
        text_rect = QRectF(text_x, TEXT_AT[1], text_width, drawn.height())
    else:
        document = text_document(rich, text_width)
        p.save()
        p.translate(text_x, TEXT_AT[1])
        document.drawContents(p)
        p.restore()
        text_rect = QRectF(text_x, TEXT_AT[1], text_width, document.size().height())
    name_rect = None
    if name and text is not None:
        size = NAME_PX
        name_w = text.width(name, size)
        shadow = tail_sheet.get(NAME_SHADOW_PART)
        if shadow is not None:
            _name_shadow(p, shadow, name_w)
        # The line (its ascent over its descent) centred on the board.
        top = NAME_AT[1] + NAME_BOARD_H / 2 - (text.font.ascent - text.font.descent) * size / gf.EM / 2
        text.draw(p, [(name, False)], NAME_AT[0], top, None, size, size, NAME_FILL, (NAME_EDGE, NAME_OUTLINE))
        name_rect = QRectF(NAME_AT[0], NAME_AT[1], name_w, NAME_BOARD_H)
    elif name:
        font = QFont()
        font.setFamilies(SERIF)
        font.setPixelSize(NAME_PX)
        metrics = QFontMetricsF(font)
        name_w = metrics.horizontalAdvance(name)
        shadow = tail_sheet.get(NAME_SHADOW_PART)
        if shadow is not None:
            _name_shadow(p, shadow, name_w)
        baseline = NAME_AT[1] + NAME_BOARD_H / 2 + (metrics.ascent() - metrics.descent()) / 2
        path = QPainterPath()
        path.addText(QPointF(NAME_AT[0], baseline), font, name)
        p.setPen(QPen(NAME_EDGE, 5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
        p.setPen(Qt.NoPen)
        p.setBrush(NAME_FILL)
        p.drawPath(path)
        name_rect = QRectF(NAME_AT[0], NAME_AT[1], name_w, NAME_BOARD_H)
    p.end()
    if len(_KEPT) >= KEEP_MOST:
        _KEPT.pop(next(iter(_KEPT)))
    _KEPT[key] = (image, text_rect, name_rect)
    return _KEPT[key]


def _name_shadow(p: QPainter, shadow: QImage, name_w: float) -> None:
    """The soft shadow behind the name (the tails' sheet's part 10), darkened."""
    dark = shadow.convertToFormat(QImage.Format_ARGB32_Premultiplied)
    tint = QPainter(dark)
    tint.setCompositionMode(QPainter.CompositionMode_SourceIn)
    tint.fillRect(dark.rect(), QColor(0, 0, 0))
    tint.end()
    p.save()
    p.setOpacity(0.15)
    p.drawImage(QRectF(NAME_AT[0] - 13, NAME_AT[1] - 3, name_w + 26, NAME_BOARD_H + 6), dark)
    p.restore()


def draw(p: QPainter, screen: QRectF, placed: Placed, kind: str, sheets: dict, rich: str, name: Optional[str],
         face: Optional[QImage], since_open: float, text=None, runs=None) -> Drawn:
    """
    One box, at `placed` on the game's screen shown as `screen` in the view:
    the game's pictures where `sheets` has them (`{sheet name: {part: QImage}}`),
    else plainly; `face` the face as it is this frame (`face_image`), or None.
    The box with its words and name (kept, `_box_image`), then the tail, then
    the face, as `Balloon` lists them (its first in front, as in every layout:
    the face, the tails, then the box at the back). The tail's root is a band
    of parchment that lies over the box's edge, so the tail comes out of the
    box with no edge across it (Zodi, 19 October: "the boundary where the
    speech balloon and its tail overlap does not match the game"; the first
    build drew the box over the tail, its edge across the tail's root).
    """
    scale = screen.height() / SCREEN_H
    grow = opening_scale(since_open)
    width = placed.width
    face_shown = face is not None
    nine = NINE.get(kind, NINE["normal"])
    box_sheet = sheets.get(kind) or sheets.get("normal")
    tail_sheet = sheets.get("tail") or {}
    mask_sheet = sheets.get("mask_face") or {}
    pictures = bool(box_sheet and box_sheet.get(0) is not None)

    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    # Game pixels from here on, the box's top left at 0, 0, grown from its middle.
    p.translate(screen.left() + placed.x * scale, screen.top() + placed.y * scale)
    p.scale(scale, scale)
    p.translate(width / 2, BOX_H / 2)
    p.scale(grow, grow)
    p.translate(-width / 2, -BOX_H / 2)
    if since_open < 1:
        p.setOpacity(0.0)

    face_left = face_shown and placed.face_left
    picture, text_rect, name_rect = _box_image(kind, width, sheets, rich, name, face_shown, face_left, text, runs)
    p.drawImage(QRectF(-PAD_SIDE, -PAD_TOP, picture.width(), picture.height()), picture)

    tail_view = None
    if placed.tail is not None:
        down = placed.tail == "down"
        tip_x = placed.tail_x - placed.x
        if kind == "round":
            for part, y, h in (BUBBLES_DOWN if down else BUBBLES_UP):
                image = tail_sheet.get(part)
                top = (TAIL_DOWN_Y if down else TAIL_UP_Y) + y
                if image is not None:
                    p.drawImage(QRectF(tip_x - TAIL_SIZE[0] / 2, top, TAIL_SIZE[0], h), image)
            tip_y = TAIL_DOWN_Y + TAIL_SIZE[1] if down else TAIL_UP_Y
        else:
            down_part, up_part = TAILS.get(kind, TAILS["normal"])
            image = tail_sheet.get(down_part if down else up_part)
            top = TAIL_DOWN_Y if down else TAIL_UP_Y
            if image is not None:
                at = _tip_x(image, down) * TAIL_SIZE[0] / max(1, image.width())
                p.drawImage(QRectF(tip_x - at, top, TAIL_SIZE[0], TAIL_SIZE[1]), image)
            else:
                path = QPainterPath()
                edge = BOX_H - 6 if down else 6
                end = top + TAIL_SIZE[1] if down else top
                path.moveTo(tip_x + 8, edge)
                path.lineTo(tip_x, end)
                path.lineTo(tip_x + 40, edge)
                path.closeSubpath()
                p.setPen(QPen(PLAIN_EDGE, 3))
                p.setBrush(PLAIN_FILL)
                p.drawPath(path)
            tip_y = top + TAIL_SIZE[1] if down else top
        tail_view = (tip_x, tip_y)

    face_rect = None
    if face_shown:
        mask = mask_sheet.get(nine[4])
        cut = masked_face(face, mask if pictures else None)
        if face_left:
            # `FaceLeft` is `FaceRight` turned about its own middle: the mask
            # too, so it is cut to the box's left end.
            left = FACE_FROM_LEFT + FACE_BOX[0] - MASK_AT[0] - MASK_SIZE[0]
        else:
            left = width - FACE_FROM_RIGHT + MASK_AT[0]
        face_rect = QRectF(left, FACE_TOP + MASK_AT[1], MASK_SIZE[0], MASK_SIZE[1])
        p.save()
        if not pictures:
            clip = QPainterPath()
            clip.addRoundedRect(QRectF(0, 0, width, BOX_H), 22, 22)
            p.setClipPath(clip)
        if face_left:
            p.translate(face_rect.center())
            p.scale(-1, 1)
            p.translate(-face_rect.center())
        p.drawImage(face_rect, cut)
        p.restore()

    transform = p.transform()
    p.restore()

    def view_rect(r: Optional[QRectF]) -> Optional[QRectF]:
        return transform.mapRect(r) if r is not None else None
    tip = transform.map(QPointF(*tail_view)) if tail_view is not None else None
    return Drawn(view_rect(QRectF(0, 0, width, BOX_H)), tip, view_rect(face_rect), view_rect(text_rect),
                 view_rect(name_rect), kind, pictures)
