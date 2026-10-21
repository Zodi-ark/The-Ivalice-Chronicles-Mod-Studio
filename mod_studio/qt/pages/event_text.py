"""
The Event Editor's words on the screen without a balloon: a line said by no
one the screen shows (a box of kind 0), and the place's name as a scene
begins (the remaster's captions). Drawn as the game draws them, from its own
layout files, measured on Zodi's screenshots (20 October).

**A box of kind 0** (a DisplayMessage's box type 0x00 to 0x0F, the
decompilation's `DIALOG_BOX_TYPE_CENTERED`): the remaster draws its words
alone, centred across the screen, in Zilvertype Pro Bold with a soft shadow,
not in a balloon (Zodi, 20 October: event 002's prayer "does not appear in a
speech bubble in game", and event 008's narration "appears in game like this
test on screen"). 50 of the game's boxes are of this kind. The look is `ui/ffto/event/ffto_event.uib`'s
`BalloonTextOnly`, in one of two styles, and the box's last number but one
(`options`) says which: it is a `MessageWindowAnimationType` row, whose
animations are the layout's `ShowNormalfont` (10), `ShowDefault` (11),
`ShowNormalfontSlow` (12) and `ShowDefaultSlow` (13).

- **Normalfont** (002's prayer, 10): its words (`TextBoardTextOnlyNormalFont`)
  at 42 pixels, 2 more between letters, 30 more between lines (72 from
  baseline to baseline), across 160 to 1,760, their top 131 down (the board
  at 326, the layer moved up 195).
- **Default** (008's narration, 13; any other number too): its words
  (`TextBoardTextOnly`) placed as 36 pixels' are, 66 from baseline to
  baseline, their top 410 down, but drawn 1.4 times as big, at 50.4, as the
  screenshot measures them: two lines whose ink is 1,445 and 741 wide (50.4
  makes them 1,449 and 742 from pen to pen, the ink a little less; 36 would
  make 1,072), capitals 35 high (Zilvertype's are 0.70 of the size).

In both, the first line's baseline is 0.775 of the board's size below its
top (32.5 at 42, 27.5 at 36, and the caption's 51.5 at 66, measured), the
box's numbers move it as a balloon's do (up for more, right for more: 002's
-45 takes the prayer 45 down, its first baseline from 163.5 to 208.5 as the
screenshot has it), and it fades in over the style's frames (10, 45 for the
slow ones; from 0.35, `LEAST_SHOWN`, not from nothing as in the game, so
that the node that opens it shows its words when it is picked).

**A caption** (the remaster's instruction E7: event 002 begins with
"Orbonne Monastery" on a black screen, Zodi, 20 October) is
`ui/ffto/event/ffto_event_caption.uib`'s `Caption`: its words (`Text00`) at
66 pixels, in the same letters and colour, their top 641 down and 100 in,
sliding in from 200 to the left over 200 frames while they fade in over the
first 60, and fading out over 60 at the end (`event_scripts.CaptionShown`);
a second line (`Text01`, 46 pixels) under a rule (`Rect00`), as `Line2`
shows them. The screenshot's "Orbonne Monastery" measures 547 across and its
capitals 46 high: Zilvertype Pro Bold's 551 and 46 at 66. The words are the
database's (`event_scripts.caption_words`).

Without the game's font (a game unpacked without it), a serif stands in.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPainterPath

from ... import game_fonts as gf
from . import event_balloon as eb

#: The font of the words without a balloon and of the captions (`UIFontType` 5).
TEXT_FONT = "FFTO_Zilvertype Pro Bold"
#: Their colour (the layouts' 221, 216, 198), and their shadow's.
INK = QColor(221, 216, 198)
SHADOW = QColor(12, 9, 6, 150)
#: The shadow: grown this many pixels round each letter and moved down and right this far.
SHADOW_GROW, SHADOW_SHIFT = 3.0, 2.0
#: How far below a text board's top its first baseline is, for its size (see the notes).
FIRST_BASELINE = 0.775
#: A box of kind 0: its type's 0x70 bits.
TEXT_ONLY_KIND = 0x00
#: How opaque words are as they begin to fade in: the game's start from nothing, but a
#: node that opens a box or a caption is shown from its first frame, which would show none.
LEAST_SHOWN = 0.35


def is_text_only(box: int) -> bool:
    """Whether a DisplayMessage's box type is drawn as words alone (kind 0)."""
    return box & 0x70 == TEXT_ONLY_KIND


@dataclass(frozen=True)
class TextStyle:
    """One of `BalloonTextOnly`'s looks: the letters' size and the board's (its lines are
    placed by it), the space between baselines and after each letter, the first baseline
    with no move, and the frames it fades in over."""
    name: str
    size: float
    board_size: float
    pitch: float
    spacing: float
    first: float
    fade_in: int

    @property
    def board_top(self) -> float:
        return self.first - FIRST_BASELINE * self.board_size


#: Across: the boards' left and width (centred on the screen's 960).
BOARD_LEFT, BOARD_WIDTH = 160.0, 1600.0
NORMALFONT = TextStyle("Normalfont", 42.0, 42.0, 72.0, 2.0, 131.0 + FIRST_BASELINE * 42.0, 10)
NORMALFONT_SLOW = TextStyle("Normalfont, slow", 42.0, 42.0, 72.0, 2.0, 131.0 + FIRST_BASELINE * 42.0, 45)
#: Default's letters are drawn this many times its board's size (see the notes).
DEFAULT_GROWN = 1.4
DEFAULT = TextStyle("Default", 36.0 * DEFAULT_GROWN, 36.0, 66.0, 2.0, 410.0 + FIRST_BASELINE * 36.0, 10)
DEFAULT_SLOW = TextStyle("Default, slow", 36.0 * DEFAULT_GROWN, 36.0, 66.0, 2.0, 410.0 + FIRST_BASELINE * 36.0, 45)
#: `MessageWindowAnimationType` rows that are a box of words alone's.
STYLES = {10: NORMALFONT, 11: DEFAULT, 12: NORMALFONT_SLOW, 13: DEFAULT_SLOW}


def text_style(options: int) -> TextStyle:
    """The look of a box of kind 0 with `options` (its `MessageWindowAnimationType`)."""
    return STYLES.get(int(options or 0), DEFAULT)


def _fading_in(part: float) -> float:
    """How opaque words are `part` of the way through fading in (from `LEAST_SHOWN`)."""
    part = min(1.0, max(0.0, part))
    return LEAST_SHOWN + (1.0 - LEAST_SHOWN) * part


def _serif(size: float) -> QFont:
    font = QFont()
    font.setFamilies(eb.SERIF)
    font.setPixelSize(max(1, round(size)))
    return font


def _draw_lines(p: QPainter, text, runs, left: float, first_baseline: float, width: Optional[float],
                size: float, pitch: float, spacing: float, align: int, opacity: float) -> QRectF:
    """
    Words in the game's letters (`text`, a `game_text.GameText`) or a serif,
    their first baseline at `first_baseline`, with the shadow under them; all
    in the view's pixels. Returns where they are.
    """
    if opacity <= 0.001:
        return QRectF()
    p.save()
    p.setOpacity(max(0.0, min(1.0, opacity)))
    if text is not None:
        lines = text.layout(runs, size, width, spacing)
        top = first_baseline - text.font.ascent * size / gf.EM
        shift = SHADOW_SHIFT * size / 42.0
        grow = SHADOW_GROW * size / 42.0
        text.draw(p, runs, left + shift, top + shift, width, size, pitch, SHADOW, (SHADOW, grow), align,
                  lines, spacing)
        drawn = text.draw(p, runs, left, top, width, size, pitch, INK, None, align, lines, spacing)
        if align == 1 and width is not None:
            widest = drawn.width()
            drawn = QRectF(left + (width - widest) / 2, drawn.top(), widest, drawn.height())
        p.restore()
        return drawn
    font = _serif(size)
    metrics = QFontMetricsF(font)
    words = "".join(str(w) for w, _italic in runs)
    rows = []
    for paragraph in words.split("\n"):
        line = ""
        for word in paragraph.split(" "):
            trial = (line + " " + word) if line else word
            if width is not None and line and metrics.horizontalAdvance(trial) > width:
                rows.append(line)
                line = word
            else:
                line = trial
        rows.append(line)
    widest = 0.0
    for row, line in enumerate(rows):
        across = metrics.horizontalAdvance(line)
        widest = max(widest, across)
        x = left + ((width - across) / 2 if align == 1 and width is not None else 0.0)
        path = QPainterPath()
        path.addText(QPointF(x, first_baseline + row * pitch), font, line)
        p.setPen(Qt.NoPen)
        p.setBrush(SHADOW)
        p.drawPath(path.translated(2.0, 2.0))
        p.setBrush(INK)
        p.drawPath(path)
    p.restore()
    x0 = left + ((width - widest) / 2 if align == 1 and width is not None else 0.0)
    return QRectF(x0, first_baseline - metrics.ascent(), widest, metrics.height() + pitch * (len(rows) - 1))


def draw_text_only(p: QPainter, screen: QRectF, text, runs, options: int, dx: float, dy: float,
                   since: float) -> QRectF:
    """
    A box of kind 0's words (`runs`) on the game's `screen` (the view's
    rectangle for its 1,920 by 1,080), in the look its `options` say, moved
    `dx` right and `dy` up (the game's pixels), `since` frames after it
    opened. Returns where they are, in the view's pixels.
    """
    style = text_style(options)
    scale = screen.height() / eb.SCREEN_H
    opacity = 1.0 if style.fade_in <= 0 else _fading_in(since / style.fade_in)
    left = screen.left() + (BOARD_LEFT + dx) * scale
    first = screen.top() + (style.first - dy) * scale
    return _draw_lines(p, text, runs, left, first, BOARD_WIDTH * scale, style.size * scale,
                       style.pitch * scale, style.spacing * scale, 1, opacity)


# -- captions --------------------------------------------------------------------------

#: `Caption`'s words: their size, where their box's top and left come to rest, how far
#: left they start, and the frames they slide in, fade in and fade out over.
CAPTION_SIZE = 66.0
CAPTION_LEFT, CAPTION_TOP = 100.0, 641.0
CAPTION_FROM = -200.0
CAPTION_SLIDE, CAPTION_FADE_IN, CAPTION_FADE_OUT = 200.0, 60.0, 60.0
#: A caption's second line (`Text01`, shown with `Line2`): its size and the middle of its
#: box, and the rule over it (`Rect00`): its top, length and thickness.
CAPTION_SECOND_SIZE, CAPTION_SECOND_MIDDLE = 46.0, 765.0
CAPTION_RULE_TOP, CAPTION_RULE_LONG, CAPTION_RULE_THICK = 721.0, 1000.0, 2.0
#: A line centred up and down has its baseline this much of its size below the middle
#: (half a capital's height: Zilvertype's capitals are 0.70 of the size).
CENTRED_BASELINE = 0.35


def caption_place(since: float, left: float) -> tuple:
    """`(how far left of its place, how opaque)`: a caption `since` frames after it began
    with `left` to go. Its slide slows as it ends."""
    t = min(1.0, max(0.0, since) / CAPTION_SLIDE)
    eased = 1.0 - (1.0 - t) ** 3
    opacity = min(_fading_in(since / CAPTION_FADE_IN), max(0.0, left) / CAPTION_FADE_OUT)
    return CAPTION_FROM * (1.0 - eased), opacity


def draw_caption(p: QPainter, screen: QRectF, text, words: str, since: float, left: float) -> QRectF:
    """
    A caption's `words` on the game's `screen`, `since` frames after it began
    with `left` to go: its first line, and a second (after a new line) smaller
    under a rule, as `Line2` shows them. Returns where the words are.
    """
    shift, opacity = caption_place(since, left)
    scale = screen.height() / eb.SCREEN_H
    first_line, _, second_line = str(words).partition("\n")
    x = screen.left() + (CAPTION_LEFT + shift) * scale
    first = screen.top() + (CAPTION_TOP + FIRST_BASELINE * CAPTION_SIZE) * scale
    drawn = _draw_lines(p, text, [(first_line, False)], x, first, None, CAPTION_SIZE * scale,
                        CAPTION_SIZE * scale, 0.0, 0, opacity)
    if second_line.strip() and opacity > 0.001:
        p.save()
        p.setOpacity(opacity)
        p.fillRect(QRectF(screen.left() + shift * scale, screen.top() + CAPTION_RULE_TOP * scale,
                          CAPTION_RULE_LONG * scale, CAPTION_RULE_THICK * scale), INK)
        p.restore()
        size = CAPTION_SECOND_SIZE * scale
        baseline = screen.top() + (CAPTION_SECOND_MIDDLE + CENTRED_BASELINE * CAPTION_SECOND_SIZE) * scale
        drawn = drawn.united(_draw_lines(p, text, [(second_line.replace("\n", " "), False)], x, baseline,
                                         None, size, size, 0.0, 0, opacity))
    return drawn
