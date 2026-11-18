"""
A unit's sprite on the Textures page (Zodi's second point of 16 November
2026: "On the Textures page of Mod Studio, not only should we be able to view
Sprite textures there and replace them like in the new Jobs page (we
currently can not), but also be able to replace the ... files with those of
higher resolution"; his choice of that day: "a group of their own in the
page's tree, each sprite by its name").

`SpritePane` is what the page shows in its right half while a sprite of the
group "Unit sprites" is picked: the sprite's sheet in one of its palettes
(stepped through, as the Jobs tab's figure is), Replace..., Export as PNG...
and As the game has it. The sheet is the mod's own picture where it has one
(`state.sprite_art`, `sprite_textures.SpriteArt`: at the game's size, or a
bigger one), else the game's (`unit_sprites.UnitSprites`, from the unpacked
game's g2d.dat and its classic sprite file's palettes).

What Replace... takes (`replace`): an image of the sheet at the game's size
or 2 to 8 times it (`sprite_textures.from_image`: numbered colors kept, any
other the nearest of the palette shown), or a classic sprite (a .spr, or a
.bmp of 256 by 488, doubled as the Jobs tab doubles one:
`classic_sprites.textures`). A bigger picture needs Mod Studio Framework in
the game, and the pane says so. (The thirtieth session) An image whose colors
aren't all the shown palette's keeps its own colors for that palette (his
choice of 17 November, "Keep its colors"), up to 4 times the game's size; the
pane draws them in that palette (and in any other the palette's colors, as the
game does) and says so, and Export as PNG... writes them.

The pane can't import the Textures page at its top (the page imports the
pane): the page's picture view is imported where the pane is made.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ... import classic_sprites as cs
from ... import job_looks as jl
from ... import sprite_textures as st
from ... import unit_sprites as us
from .. import export_dialogs
from ..widgets.status_line import StatusLine

#: The group's name in the page's tree, and the start of each of its rows' paths.
GROUP = "Unit sprites"

#: (The thirty third session) The notes shortened, his ask of 17 November: "some of these notes on the Textures page are
#: really long ... can you shorten these notes on the Textures page even the one after replacing".
GAME_NOTE = "The game's own sprite, {w} by {h} pixels, in the palettes of {file}."
OWN_NOTE = "The mod's own picture at the game's size, {w} by {h} pixels."
BIG_NOTE = "The mod's own picture at {n} times the game's size, {w} by {h} pixels. It needs Mod Studio Framework."
#: (The thirtieth session) Said after the note above where the picture has colors of its own. (Mod Studio Framework
#: 2.0.2, the thirty second session: his answer of 17 November, "The full colors should stay through the highlight with
#: what ever appropriate tints applied to them", a status's tints with it) The game's tints of that palette keep them.
OWN_NOTE_MORE = " Its own colors show in this palette, tinted as the game tints it, and the nearest colors in others."
UNREAD_NOTE = ("The game's own sprite can't be read here: {why}. A picture of the mod's own can still be given and "
               "exported.")
TAKES_NOTE = "Replace... takes an image 512 pixels wide (513 to 1,024 tall) or 2 to 8 times that, or a classic .spr or .bmp."
PALETTE_LABEL = "Palette {n} of {of}"
REPLACED = "Replaced with {file}."
REPLACED_OFF = " {n} of its pixels took the nearest of this palette's colors; to keep every one, start from Export as PNG."
#: (The thirtieth session) What Replace... did with an image's own colors.
REPLACED_OWN = " {n} of its pixels keep their own colors in this palette, with Mod Studio Framework."
REPLACED_OWN_BIG = " {n} of its pixels took the nearest of this palette's colors: own colors are kept up to 4 times the game's size."
NOT_REPLACED = "{file} can't be this sprite's sheet: {why}"
EXPORTED = "Exported to {path}"
NOT_EXPORTED = "Couldn't export: {why}"
OPEN_FILTER = "A sprite's sheet (*.png *.bmp *.gif *.tga *.webp *.spr);;All files (*)"
#: The colors a sheet is drawn in where the game's palettes can't be read: 16 greys, the first see through.
GREYS = [0] + [(n * 2) | ((n * 2) << 5) | ((n * 2) << 10) for n in range(1, 16)]


#: (The thirtieth session) Each of a palette's 16 numbers' opacity as the page draws a sheet: the first see through,
#: every other drawn.
SEEN = [0] + [255] * 15


def own_image(art: st.SpriteArt, sheet: us.Sheet) -> QImage:
    """(The thirtieth session) A picture of more colors in its own colors, the first number see through."""
    data = art.own_rgba(SEEN)
    return QImage(data, sheet.width, sheet.height, sheet.width * 4, QImage.Format_RGBA8888).convertToFormat(
        QImage.Format_ARGB32)


def sheet_image(sheet: us.Sheet, colors16: list) -> QImage:
    """A sheet as a picture in a palette's colors, the first see through."""
    image = QImage(bytes(sheet.pixels), sheet.width, sheet.height, sheet.width, QImage.Format_Indexed8)
    table = []
    for k in range(16):
        r, g, b = us.rgba((colors16[k] if k < len(colors16) else 0) | 0x8000)[:3]
        table.append(0 if k == 0 else (0xFF << 24) | (r << 16) | (g << 8) | b)
    image.setColorTable(table)
    return image.convertToFormat(QImage.Format_ARGB32)


def own_png(art: st.SpriteArt, sheet: us.Sheet) -> bytes:
    """(The thirtieth session) A picture of more colors as a PNG of its own colors, what Replace... reads back."""
    import io
    from PIL import Image
    out = io.BytesIO()
    Image.frombytes("RGBA", (sheet.width, sheet.height), art.own_rgba(SEEN)).save(out, format="PNG")
    return out.getvalue()


class SpritePane(QWidget):
    """The Textures page's right half over one of the game's unit sprites."""

    #: The mod's picture of a sprite was given, changed or taken off: the sprite's number.
    changed = Signal(int)

    def __init__(self, state, parent=None):
        super().__init__(parent)
        from .textures import PreviewView                      # the page imports this pane: see the note at the top
        self.state = state
        self.number = None
        self.palette = 0
        self._palettes = [GREYS]
        self._table = us.read_table()
        self._sprites = None
        self._sprites_of = None

        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(8)
        self.title = QLabel("")
        self.title.setStyleSheet("font-weight: 600; font-size: 12pt;")
        self.title.setWordWrap(True)
        column.addWidget(self.title)
        self.note = QLabel("")
        self.note.setProperty("role", "muted")
        self.note.setWordWrap(True)
        column.addWidget(self.note)
        self.takes = QLabel(TAKES_NOTE)
        self.takes.setProperty("role", "muted")
        self.takes.setWordWrap(True)
        column.addWidget(self.takes)

        self.view = PreviewView()
        column.addWidget(self.view, 1)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.previous_button = QPushButton("Previous palette")
        self.previous_button.clicked.connect(lambda: self.step_palette(-1))
        self.next_button = QPushButton("Next palette")
        self.next_button.clicked.connect(lambda: self.step_palette(1))
        self.palette_label = QLabel("")
        row.addWidget(self.previous_button)
        row.addWidget(self.next_button)
        row.addWidget(self.palette_label)
        row.addStretch(1)
        column.addLayout(row)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.replace_button = QPushButton("Replace...")
        self.replace_button.clicked.connect(lambda: self.choose_replacement())
        self.export_button = QPushButton("Export as PNG...")
        self.export_button.clicked.connect(lambda: self.export_png())
        self.game_button = QPushButton("As the game has it")
        self.game_button.setToolTip("Takes the mod's picture off this sprite")
        self.game_button.clicked.connect(lambda: self.as_game())
        for button in (self.replace_button, self.export_button, self.game_button):
            row.addWidget(button)
        row.addStretch(1)
        column.addLayout(row)
        self.status = StatusLine()
        column.addWidget(self.status)

    # -- what is shown ---------------------------------------------------------

    def _game(self):
        """The unpacked game's sprites, read once for the folder the state names."""
        unpacked = getattr(self.state, "nxd_unpack_dir", None)
        if self._sprites is None or self._sprites_of != unpacked:
            self._sprites_of = unpacked
            try:
                self._sprites = us.UnitSprites(unpacked, self._table) if unpacked else None
            except Exception:                                  # noqa: BLE001
                self._sprites = None
        return self._sprites

    def own(self):
        """The mod's own picture of the sprite shown, or None."""
        return (getattr(self.state, "sprite_art", None) or {}).get(self.number)

    def sheet(self):
        """The sheet shown: the mod's own (its bigger one where it has one), else the game's; None where neither
        can be read."""
        own = self.own()
        if own is not None:
            return own.big_sheet() or own.sheet()
        return self._game_sheet()

    def _game_sheet(self):
        entry, game = self._table.get(self.number), self._game()
        if entry is None or game is None:
            return None
        try:
            return game.sheet(entry)
        except Exception:                                      # noqa: BLE001
            return None

    def colors(self) -> list:
        """The palette the sheet is drawn in now."""
        return self._palettes[min(self.palette, len(self._palettes) - 1)]

    def show_sprite(self, number: int, name: str) -> None:
        """Shows a sprite by its number, under the name the page lists it by."""
        if number != self.number:
            self.palette = 0
            self.status.clear()
        self.number = number
        self.title.setText(name)
        entry, game = self._table.get(number), self._game()
        found = None
        if entry is not None and game is not None:
            try:
                found = game.palettes(entry)
            except Exception:                                  # noqa: BLE001
                found = None
        shown = [palette for palette in (found or []) if not us.is_blank(palette)]
        self._palettes = shown or [GREYS]
        self.refresh()

    def shows_own(self) -> bool:
        """(The thirtieth session) Whether the sheet is drawn in its own colors: the mod's picture has them, and the
        palette shown is the one they were given in."""
        own = self.own()
        return own is not None and own.has_own and list(self.colors())[:16] == list(own.tied)

    def refresh(self) -> None:
        """Draws the sheet again and says what it is."""
        own, sheet = self.own(), self.sheet()
        entry = self._table.get(self.number)
        more = OWN_NOTE_MORE if own is not None and own.has_own else ""
        if own is not None and own.is_big:
            self.note.setText(BIG_NOTE.format(n=own.scale, w=f"{sheet.width:,}", h=f"{sheet.height:,}") + more)
        elif own is not None:
            self.note.setText(OWN_NOTE.format(w=sheet.width, h=sheet.height) + more)
        elif sheet is not None:
            self.note.setText(GAME_NOTE.format(w=sheet.width, h=sheet.height,
                                               file=f"battle_{entry.name}_spr.bin" if entry else "its sprite file"))
        else:
            self.note.setText(UNREAD_NOTE.format(
                why="the game isn't unpacked yet" if self._game() is None
                else "its textures aren't in the unpacked game's g2d.dat"))
        if sheet is not None and self.shows_own():
            self.view.set_native(QPixmap.fromImage(own_image(own, sheet)))
        elif sheet is not None:
            self.view.set_native(QPixmap.fromImage(sheet_image(sheet, self.colors())))
        else:
            self.view.clear_native("")
        several = len(self._palettes) > 1
        self.palette_label.setText(PALETTE_LABEL.format(n=min(self.palette, len(self._palettes) - 1) + 1,
                                                        of=len(self._palettes)))
        self.previous_button.setEnabled(several)
        self.next_button.setEnabled(several)
        self.export_button.setEnabled(sheet is not None)
        self.game_button.setEnabled(own is not None)

    def step_palette(self, by: int) -> None:
        self.palette = (self.palette + by) % len(self._palettes)
        self.refresh()

    # -- what it does ----------------------------------------------------------

    def choose_replacement(self, path: str | None = None) -> None:
        """`path` is for the checks, which can't open a file dialog."""
        if self.number is None:
            return
        if path is None:
            path = export_dialogs.open_file(self, "Choose a sprite's sheet", OPEN_FILTER)
        if path:
            self.replace(Path(path))

    def replace(self, path: Path) -> bool:
        """The mod's picture of the sprite shown made from a file; False, and why in the status line, where the
        file can't be one."""
        off = 0
        try:
            classic = None
            if path.suffix.lower() == ".spr":
                classic = cs.read_file(path)
            else:
                from PIL import Image
                with Image.open(path) as opened:
                    image = opened.copy()
                if cs.is_classic_picture(image):
                    classic = cs.read_picture(image)
            if classic is not None:
                art = st.from_textures(*cs.textures(classic))
            else:
                art, off = st.from_image(image, self.colors())
        except (st.SpriteTextureError, cs.ClassicError, OSError, ValueError) as exc:
            self.status.say(NOT_REPLACED.format(file=path.name, why=exc), "error")
            return False
        if getattr(self.state, "sprite_art", None) is None:
            self.state.sprite_art = {}
        self.state.sprite_art[self.number] = art
        if art.has_own:
            told = REPLACED_OWN.format(n=f"{art.own_count:,}")
        elif art.own_dropped:
            told = REPLACED_OWN_BIG.format(n=f"{art.own_count:,}")
        else:
            told = REPLACED_OFF.format(n=f"{off:,}") if off else ""
        self.status.say(REPLACED.format(file=path.name) + told, "plain")
        self.refresh()
        self.changed.emit(self.number)
        return True

    def as_game(self) -> None:
        """The mod's picture taken off the sprite shown."""
        if self.own() is None:
            return
        self.state.sprite_art.pop(self.number, None)
        self.status.clear()
        self.refresh()
        self.changed.emit(self.number)

    def export_png(self, path: str | None = None) -> None:
        """The sheet shown written as a PNG of numbered colors, in the palette shown: what Replace... reads back
        number for number."""
        sheet = self.sheet()
        if sheet is None:
            return
        entry = self._table.get(self.number)
        if path is None:
            path = export_dialogs.save_file(self, "Export the sprite's sheet",
                                            f"{entry.name if entry else self.number}.png", "PNG image (*.png)")
        if not path:
            return
        try:
            if self.shows_own():
                Path(path).write_bytes(own_png(self.own(), sheet))
            else:
                Path(path).write_bytes(jl.sheet_png(sheet, self.colors()))
        except OSError as exc:
            self.status.say(NOT_EXPORTED.format(why=exc), "error")
            return
        self.status.say(EXPORTED.format(path=path), "plain")
