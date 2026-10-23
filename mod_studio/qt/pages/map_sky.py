"""
The Map Editor's Sky colors window (Zodi's list after shaping, 21 October:
"sky colours"): the colors the game draws behind a map in a battle, top and
bottom, for each of the map's variants (`map_variants`): its story
lightings' and its random battles'.

A row a variant; its battles said as the page works them out (the events
set on the map that meet it, `MapEditorPage.lighting_events`). A color
changed goes into the mod at once as the map's `Map` row
(`MapEditorPage.set_sky`), and the map behind it is drawn with the shown
lighting's colors. **Game's** puts a row back.

A row the game's table gives no colors shows the map's own (Zodi, 22
October: "some maps that have skys in game but they do not appear in mod
studio"): the sky of the map's classic look the game draws for each
battle's time and weather (`MapEditorPage.own_sky`), marked **Own**.
"""
from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QColorDialog, QDialog, QGridLayout, QHBoxLayout, QLabel, QPushButton,
                               QVBoxLayout)

from ... import map_classic as mc
from ... import map_battles as mb
from .map_light import SWATCH, ColourButton

#: The window's words, for a person changing a sky's colors, not how the
#: game keeps them (Zodi, 22 October: "they just want to simply change the
#: color of the sky. If there is critical information they should know say
#: it there but keep it short and understandable to non developers").
SKY_INTRO = ("Click a color to change it. The sky fades from the top color down to the bottom one, and each row is "
             "the sky for the battles it names. Own is the map's usual sky, which can change with a battle's time "
             "and weather: pick a color to use your own.")
NONE_WORD = "None"
#: A swatch of the map's own sky (a row the game's table gives no colors:
#: the game draws its classic look's sky for each battle's time and weather,
#: the one most of the row's battles have shown), and what it says pointed at.
OWN_WORD = "Own"
OWN_TIP = "{title}: the map's usual sky, {red}, {green}, {blue} {battle}. Pick a color to use your own."
GAME_BUTTON = "Game's"
GAME_TIP = "Puts back the game's colors for this row."


def battle_words(night: int, weather: int, events=()) -> str:
    """ "by day in strong weather, for events 53 and 54": a battle's time and weather, and its events if any."""
    words = "at night" if night else "by day"
    if weather:
        name = mc.WEATHERS[weather] if 0 <= weather < len(mc.WEATHERS) else f"weather {weather}"
        words += f" in {name.lower()} weather"
    events = sorted(events)
    if events:
        words += f", for event{'s' if len(events) != 1 else ''} {mb.runs(events)}"
    return words


class SkyButton(ColourButton):
    """
    A sky's color; where the row names none, the map's own (`own`, `(r, g,
    b)`, with `battle` the words for whose it is), marked Own, or None.
    """

    def __init__(self, colour, title: str, own=None, battle: str = ""):
        super().__init__((0, 0, 0), title)
        self.own = tuple(own) if own is not None else None
        self.battle = battle
        self.set_sky(colour)

    def set_sky(self, colour) -> None:
        if colour is not None:
            self.setText("")
            self.set_colour(colour)
            return
        self.colour = None
        if self.own is None:
            self.setStyleSheet("")
            self.setText(NONE_WORD)
            self.setToolTip(f"{self.title}: none")
            return
        red, green, blue = self.own
        ink = "black" if (299 * red + 587 * green + 114 * blue) / 1000 > 140 else "white"
        self.setStyleSheet(f"QPushButton#{SWATCH} {{ background-color: rgb({red}, {green}, {blue}); color: {ink}; "
                           f"border: 1px dashed palette(mid); border-radius: 3px; min-height: 20px; }}")
        self.setText(OWN_WORD)
        self.setToolTip(OWN_TIP.format(title=self.title, red=red, green=green, blue=blue, battle=self.battle))

    def choose(self) -> None:
        if self.colour is not None:
            super().choose()
            return
        # The map's own as the color window's start; nothing changes when it's closed without a pick.
        picked = QColorDialog.getColor(QColor(*(self.own or (128, 128, 128))), self.window(), self.title)
        if picked.isValid():
            self.set_sky((picked.red(), picked.green(), picked.blue()))


class SkyDialog(QDialog):
    """Map `page.number`'s sky colors, a row for each of its variants."""

    def __init__(self, page):
        super().__init__(page)
        self.page = page
        self.number = page.number
        self.setWindowTitle(f"Map {self.number:03d}'s sky colors")
        self.setModal(False)
        layout = QVBoxLayout(self)
        intro = QLabel(SKY_INTRO)
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(14)
        for column, word in enumerate(("", "Top", "Bottom")):
            if word:
                self.grid.addWidget(QLabel(word), 0, column)
        layout.addLayout(self.grid)
        #: `{variant index: (label, top button, bottom button, Game's button)}`.
        self.rows = {}
        self.fill()
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        bottom.addWidget(close)
        layout.addLayout(bottom)

    def fill(self) -> None:
        """A row for each variant, as the mod has it."""
        variants = self.page.variants(self.number)
        game = {v.index: v for v in self.page.game_variants(self.number)}
        for row, variant in enumerate(variants, start=1):
            label = QLabel(self.page.variant_label(variant, self.number))
            label.setWordWrap(True)
            own = self.page.own_sky(variant) if self.number == self.page.number else None
            battle = battle_words(own[2][0], own[2][1], own[3]) if own else ""
            top = SkyButton(variant.sky_top, "Top color", own[0] if own else None, battle)
            bottom = SkyButton(variant.sky_bottom, "Bottom color", own[1] if own else None, battle)
            back = QPushButton(GAME_BUTTON)
            back.setToolTip(GAME_TIP)
            index = variant.index
            top.clicked.connect(lambda _c=False, i=index: self._changed(i))
            bottom.clicked.connect(lambda _c=False, i=index: self._changed(i))
            back.clicked.connect(lambda _c=False, i=index: self._put_back(i))
            for column, widget in enumerate((label, top, bottom, back)):
                self.grid.addWidget(widget, row, column)
            mine = game.get(index)
            back.setEnabled(mine is None or (mine.sky_top, mine.sky_bottom)
                            != (variant.sky_top, variant.sky_bottom))
            self.rows[index] = (label, top, bottom, back)

    def _changed(self, index: int) -> None:
        _label, top, bottom, back = self.rows[index]
        if top.colour is None and bottom.colour is None:
            return          # the color window closed with nothing picked
        # One color picked for a row with none: the other is the map's own
        # as drawn, or where there is none, takes the one picked too.
        top_colour = top.colour if top.colour is not None else (top.own or bottom.colour)
        bottom_colour = bottom.colour if bottom.colour is not None else (bottom.own or top.colour)
        top.set_sky(top_colour)
        bottom.set_sky(bottom_colour)
        self.page.set_sky(index, top_colour, bottom_colour)
        self._update_back(index)

    def _put_back(self, index: int) -> None:
        game = {v.index: v for v in self.page.game_variants(self.number)}
        mine = game.get(index)
        top, bottom = (mine.sky_top, mine.sky_bottom) if mine is not None else (None, None)
        self.page.set_sky(index, top, bottom)
        _label, top_button, bottom_button, _back = self.rows[index]
        top_button.set_sky(top)
        bottom_button.set_sky(bottom)
        self._update_back(index)

    def _update_back(self, index: int) -> None:
        game = {v.index: v for v in self.page.game_variants(self.number)}
        mine = {v.index: v for v in self.page.variants(self.number)}
        a, b = game.get(index), mine.get(index)
        same = a is not None and b is not None and (a.sky_top, a.sky_bottom) == (b.sky_top, b.sky_bottom)
        self.rows[index][3].setEnabled(not same)
