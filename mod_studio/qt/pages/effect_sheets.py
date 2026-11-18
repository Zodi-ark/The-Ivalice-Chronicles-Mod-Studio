"""
An effect's picture on the Textures page (Zodi's second point of 16 November
2026: "also be able to replace the effect sprites ... files"; his choices of
17 November: the game's size first, and for the page's look "Continue on with
your recommendations": a group of their own, as Unit sprites has one, each
effect by its number and the name of the ability that plays it, with the unit
sprites' three buttons; his ask of 17 November: the group called "Effects",
first "Effect pictures").

`EffectPane` is what the page shows in its right half while an effect of the
group "Effects" is picked: the effect's sheet as its frames read it
(`effect_pictures.views`: at 8 bits a pixel in a palette of 256 colors, or at
4 bits in one of 16; stepped through where its frames use more than one),
Replace..., Export as PNG... and As the game has it. The sheet is the mod's
own picture where it has one (`state.effect_art`,
`effect_pictures.EffectArt`), else the game's (the unpacked game's
`fftpack/effect/` file).

What Replace... takes (`replace`): an image the size of the sheet as it is
shown, or (the twenty ninth session, his choice "Yes, up to 4 times") 2 to 4
times that size for a bigger picture (`effect_pictures.from_image`: an image
whose colors are numbered keeps its numbers and brings its colors; in any
other, a pixel that isn't as the sheet shows it takes the nearest of the
palette shown). The mod's picture is the effect's whole file written again, so
it needs the game's own file of the effect, and an image that leaves the file
as the game has it is no picture of the mod's unless it is bigger. A bigger
picture is drawn at its size and Export as PNG... writes it so; the mod needs
Mod Studio Framework for it, as a unit sprite's bigger picture does. (The
thirtieth session) An image whose colors aren't all the palette shown keeps
its own colors for it (his choice of 17 November, "Keep its colors"), as a
unit sprite's does: drawn in them in a palette of those colors, said, and
written by Export as PNG....

(The thirty fourth session; his Lich test of 17 November) **A summon** (one of
`effect_pictures.SUMMONS`) is drawn in the enhanced look from a sheet of its
own in g2d.dat, at twice its effect's file's size: the pane shows that sheet
(the mod's where it has one), Replace... takes an image the size of the sheet
or twice it (`effect_pictures.summon_from_image`), Export as PNG... writes it,
and its notes say where Export writes it (the mod loader's file of the sheet,
and the effect's file at half the size). Where the unpacked game has no g2d.dat
a summon's Replace... is off, said.

Its look is the unit sprites' pane's (`sprite_sheets.SpritePane`), nothing
more. The pane can't import the Textures page at its top (the page imports the
pane): the page's picture view is imported where the pane is made.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ... import effect_files as ef
from ... import effect_pictures as ep
from .. import export_dialogs
from ..widgets.status_line import StatusLine

#: The group's name in the page's tree, and the start of each of its rows' paths.
GROUP = "Effects"

#: (The thirty third session) The notes shortened, his ask of 17 November ("can you shorten these notes on the Textures
#: page even the one after replacing").
GAME_NOTE = "The game's own picture, {w} by {h} pixels in {colors} colors, from {file}."
OWN_NOTE = "The mod's own picture, {w} by {h} pixels in {colors} colors. Export writes it into {file}."
CARRIED_NOTE = ("The picture in the mod's own file, {w} by {h} pixels in {colors} colors. The file changes more than the "
                "picture, so Export keeps it as it is.")
#: (The twenty ninth session) A bigger picture, in the unit sprites' words (`sprite_sheets.BIG_NOTE`).
BIG_NOTE = ("The mod's own picture at {n} times the game's size, {w} by {h} pixels in {colors} colors. It needs Mod Studio "
            "Framework.")
#: (The thirtieth session) Said after the note above where the picture has colors of its own, in the unit sprites'
#: words (`sprite_sheets.OWN_NOTE_MORE`).
OWN_NOTE_MORE = " Its own colors show in the palette they were given in{shown}, and the nearest colors in others."
OWN_SHOWN = " (this one)"
UNREAD_NOTE = "This effect's picture can't be read here: {why}."
TAKES_NOTE = "Replace... takes an image the size of this sheet, or 2 to 4 times it for a bigger picture."
PALETTE_LABEL = "Palette {n} of {of}"
REPLACED = "Replaced with {file}."
REPLACED_OFF = " {n} of its pixels took the nearest of this palette's colors; to keep every one, start from Export as PNG."
REPLACED_BROUGHT = " {n} of this palette's colors are now the image's."
#: (The thirtieth session) What Replace... did with an image's own colors (`sprite_sheets.REPLACED_OWN`'s words).
REPLACED_OWN = " {n} of its pixels keep their own colors in this palette, with Mod Studio Framework."
SAME_AS_GAME = "{file} is the game's own picture: nothing is kept for this effect."
NOT_REPLACED = "{file} can't be this effect's picture: {why}"
NO_GAME_FILE = "the game's file of this effect isn't in the unpacked game"
EXPORTED = "Exported to {path}"
NOT_EXPORTED = "Couldn't export: {why}"
OPEN_FILTER = "An effect's picture (*.png *.bmp *.gif *.tga *.webp);;All files (*)"
#: (The thirty fourth session) A summon: its own sheet in g2d.dat, which the enhanced look draws.
SUMMON_GAME_NOTE = ("The game's own picture, {w} by {h} pixels in {colors} colors, from texture {entry} of g2d.dat. The "
                    "classic look draws {file}'s, half the size.")
SUMMON_OWN_NOTE = ("The mod's own picture, {w} by {h} pixels in {colors} colors. Export writes it into {tex} and, at half "
                   "the size, {file}.")
SUMMON_TAKES_NOTE = "Replace... takes an image the size of this sheet, or twice it for a bigger picture."
SUMMON_OFF_NOTE = "Replace... is off: the game draws this summon from g2d.dat, which isn't in the unpacked game."


def sheet_image(data: bytes, view: ep.View, art=None) -> QImage:
    """An effect's sheet in a view as a picture, a color that is never drawn see through: (the twenty ninth session)
    the mod's bigger picture at its size where `art` has one read at the view's bits (`effect_pictures.shown_sheet`);
    (the thirtieth session) its picture of more colors in its own colors where the view shows them."""
    width, height, numbers, _scale = ep.shown_sheet(art, data, view)
    if art is not None and art.shows_own(view):
        image = QImage(ep.own_rgba(art, data, view), width, height, width * 4, QImage.Format_RGBA8888)
        return image.convertToFormat(QImage.Format_ARGB32)
    return _numbered(numbers, width, height, ep.words(data, view))


def _numbered(numbers, width: int, height: int, words: list) -> QImage:
    """Color numbers as a picture through 16 bit words, a color that is never drawn see through."""
    image = QImage(bytes(numbers), width, height, width, QImage.Format_Indexed8)
    table = []
    for word in words:
        r, g, b, a = ep.shown(word)
        table.append((a << 24) | (r << 16) | (g << 8) | b)
    image.setColorTable(table + [0] * (256 - len(table)))
    return image.convertToFormat(QImage.Format_ARGB32)


def summon_image(data: bytes, art, game_sheet: bytes) -> QImage:
    """(The thirty fourth session) A summon's picture as the pane shows it (`effect_pictures.summon_shown`): its
    sheet's drawn part, the mod's or the game's, or the mod's picture twice its size, color 0 see through; in its own
    colors where it has them."""
    width, height, numbers, _times = ep.summon_shown(art, data, game_sheet)
    if ep.summon_shows_own(art):
        image = QImage(ep.summon_rgba(art, data), width, height, width * 4, QImage.Format_RGBA8888)
        return image.convertToFormat(QImage.Format_ARGB32)
    return _numbered(numbers, width, height, ep.summon_words(data))


class EffectPane(QWidget):
    """The Textures page's right half over one of the game's effects' pictures."""

    #: The mod's picture of an effect was given, changed or taken off: the effect's number.
    changed = Signal(int)

    def __init__(self, state, parent=None):
        super().__init__(parent)
        from .textures import PreviewView                      # the page imports this pane: see the note at the top
        self.state = state
        self.number = None
        self.palette = 0
        self._views = [ep.PLAIN]
        self._game = None
        self._game_of = None
        self._summon = None
        self._summon_of = None

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
        self.game_button.setToolTip("Takes the mod's picture off this effect")
        self.game_button.clicked.connect(lambda: self.as_game())
        for button in (self.replace_button, self.export_button, self.game_button):
            row.addWidget(button)
        row.addStretch(1)
        column.addLayout(row)
        self.status = StatusLine()
        column.addWidget(self.status)

    # -- what is shown ---------------------------------------------------------

    def game_file(self):
        """The unpacked game's own file of the effect shown, read once for the folder the state names and the
        effect; None where it can't be read."""
        unpacked = getattr(self.state, "nxd_unpack_dir", None)
        key = (str(unpacked) if unpacked else None, self.number)
        if self._game_of != key:
            self._game_of = key
            self._game = None
            if unpacked and self.number is not None:
                try:
                    data = ef.effect_path(unpacked, self.number).read_bytes()
                    ep.texture_of(data)
                    self._game = data
                except (OSError, ep.EffectPictureError):
                    self._game = None
        return self._game

    def game_summon(self):
        """(The thirty fourth session) The unpacked game's own sheet of the summon shown (g2d.dat's entry), read once
        for the folder the state names and the effect; None where the effect isn't a summon or it can't be read."""
        unpacked = getattr(self.state, "nxd_unpack_dir", None)
        key = (str(unpacked) if unpacked else None, self.number)
        if self._summon_of != key:
            self._summon_of = key
            self._summon = ep.game_summon(unpacked, self.number) if self.number is not None else None
        return self._summon

    def summon_shown(self) -> bool:
        """(The thirty fourth session) Whether the pane shows a summon's own sheet: a summon whose sheet the unpacked
        game has, whose effect's file the game has and the mod doesn't carry as it is."""
        return (ep.is_summon(self.number) and self.game_summon() is not None and self.game_file() is not None
                and self.carried_file() is None)

    def own(self):
        """The mod's own picture of the effect shown, or None."""
        return (getattr(self.state, "effect_art", None) or {}).get(self.number)

    def carried_file(self):
        """The mod's own file of the effect shown where the mod carries it through as it is (an opened mod's file
        that changes more of the effect than its picture), or None. A picture made from the game's file would write
        over it, so none is made for such an effect."""
        if self.number is None:
            return None
        name = f"{ef.EFFECT_FOLDER}/{ef.effect_file_name(self.number)}".lower()
        for rel, source in (getattr(self.state, "other_file_replacements", None) or {}).items():
            if str(rel).replace("\\", "/").lower() == name:
                try:
                    data = Path(source).read_bytes()
                    ep.texture_of(data)
                    return data
                except (OSError, ep.EffectPictureError):
                    return None
        return None

    def data(self):
        """The effect's file whose sheet is shown: the mod's own picture's where it has one, else the file the mod
        carries for it, else the game's; None where none can be read."""
        own = self.own()
        if own is not None:
            return own.data
        carried = self.carried_file()
        return carried if carried is not None else self.game_file()

    def shown_view(self) -> ep.View:
        """The palette the sheet is drawn in now."""
        return self._views[min(self.palette, len(self._views) - 1)]

    def show_effect(self, number: int, name: str) -> None:
        """Shows an effect by its number, under the name the page lists it by."""
        if number != self.number:
            self.palette = 0
            self.status.clear()
        self.number = number
        self.title.setText(name)
        self.refresh()

    def refresh(self) -> None:
        """Draws the sheet again and says what it is."""
        own, data, carried = self.own(), self.data(), self.carried_file()
        self._views = ep.views(data) if data is not None else [ep.PLAIN]
        view = self.shown_view()
        file = ef.effect_file_name(self.number) if self.number is not None else ""
        summon = self.summon_shown()
        off = ep.is_summon(self.number) and carried is None and self.game_summon() is None
        self.takes.setText(SUMMON_TAKES_NOTE if summon else SUMMON_OFF_NOTE if off else TAKES_NOTE)
        if summon:
            # (The thirty fourth session) A summon: its own sheet, which the enhanced look draws.
            game_sheet = self.game_summon()
            width, height, _numbers, times = ep.summon_shown(own, data, game_sheet)
            if times > 1:
                note = BIG_NOTE.format(n=times, w=f"{width:,}", h=f"{height:,}", colors=256)
            elif own is not None:
                note = SUMMON_OWN_NOTE.format(w=f"{width:,}", h=f"{height:,}", colors=256, file=file,
                                              tex=f"tex_{ep.summon_entry(self.number)}.bin")
            else:
                note = SUMMON_GAME_NOTE.format(w=f"{width:,}", h=f"{height:,}", colors=256, file=file,
                                               entry=ep.summon_entry(self.number))
            more = OWN_NOTE_MORE.format(shown=OWN_SHOWN) if ep.summon_shows_own(own) else ""
            self.note.setText(note + more)
            self.view.set_native(QPixmap.fromImage(summon_image(data, own, game_sheet)))
        elif data is not None:
            width, height, _numbers, scale = ep.shown_sheet(own, data, view)
            note = BIG_NOTE if scale > 1 else OWN_NOTE if own is not None \
                else CARRIED_NOTE if carried is not None else GAME_NOTE
            more = OWN_NOTE_MORE.format(shown=OWN_SHOWN if own.shows_own(view) else "") \
                if own is not None and own.has_own else ""
            self.note.setText(note.format(n=scale, w=f"{width:,}", h=f"{height:,}", colors=view.colors, file=file)
                              + more)
            self.view.set_native(QPixmap.fromImage(sheet_image(data, view, own)))
        else:
            self.note.setText(UNREAD_NOTE.format(
                why="the game isn't unpacked yet" if not getattr(self.state, "nxd_unpack_dir", None)
                else f"{file} isn't in the unpacked game"))
            self.view.clear_native("")
        several = len(self._views) > 1
        self.palette_label.setText(PALETTE_LABEL.format(n=min(self.palette, len(self._views) - 1) + 1,
                                                        of=len(self._views)))
        self.previous_button.setEnabled(several)
        self.next_button.setEnabled(several)
        self.replace_button.setEnabled(self.game_file() is not None and carried is None and not off)
        self.export_button.setEnabled(data is not None)
        self.game_button.setEnabled(own is not None)

    def step_palette(self, by: int) -> None:
        self.palette = (self.palette + by) % len(self._views)
        self.refresh()

    # -- what it does ----------------------------------------------------------

    def choose_replacement(self, path: str | None = None) -> None:
        """`path` is for the checks, which can't open a file dialog."""
        if self.number is None:
            return
        if path is None:
            path = export_dialogs.open_file(self, "Choose an effect's picture", OPEN_FILTER)
        if path:
            self.replace(Path(path))

    def replace(self, path: Path) -> bool:
        """The mod's picture of the effect shown made from a file; False, and why in the status line, where the
        file can't be one."""
        game = self.game_file()
        if self.carried_file() is not None:
            return False
        summon = self.summon_shown()
        if ep.is_summon(self.number) and not summon and game is not None:
            return False                          # (a summon whose sheet the unpacked game doesn't have: Replace... is off)
        try:
            if game is None:
                raise ep.EffectPictureError(NO_GAME_FILE)
            from PIL import Image
            with Image.open(path) as opened:
                image = opened.copy()
            own = self.own()
            if summon:
                taken = ep.summon_from_image(game, self.game_summon(), image, own)
            else:
                taken = ep.from_image(game, image, self.shown_view(), own.data if own is not None else None)
        except (ep.EffectPictureError, OSError, ValueError) as exc:
            self.status.say(NOT_REPLACED.format(file=path.name, why=exc), "error")
            return False
        if getattr(self.state, "effect_art", None) is None:
            self.state.effect_art = {}
        if ep.is_games_summon(taken.art, game, self.game_summon()) if summon \
                else (taken.art.data == game and not taken.art.needs_sheet):
            # The file as the game has it is no picture of the mod's: nothing to write, nothing to read back. The mod
            # changed only where it had a picture of this effect before. (A bigger picture is the mod's even where it
            # is the game's at the game's size: its pixels between the game's are its own; so, the thirtieth session,
            # are a picture's own colors.)
            changed = self.state.effect_art.pop(self.number, None) is not None
            self.status.say(SAME_AS_GAME.format(file=path.name), "plain")
        else:
            self.state.effect_art[self.number] = taken.art
            changed = True
            self.status.say(REPLACED.format(file=path.name)
                            + (REPLACED_OWN.format(n=f"{taken.own:,}") if taken.art.has_own
                               else REPLACED_OFF.format(n=f"{taken.off:,}") if taken.off else "")
                            + (REPLACED_BROUGHT.format(n=taken.brought) if taken.brought else ""), "plain")
        self.refresh()
        if changed:
            self.changed.emit(self.number)
        return True

    def as_game(self) -> None:
        """The mod's picture taken off the effect shown."""
        if self.own() is None:
            return
        self.state.effect_art.pop(self.number, None)
        self.status.clear()
        self.refresh()
        self.changed.emit(self.number)

    def export_png(self, path: str | None = None) -> None:
        """The sheet shown written as a PNG of numbered colors, in the palette shown, (the twenty ninth session) a
        bigger picture at its size: what Replace... reads back number for number and color for color."""
        data = self.data()
        if data is None:
            return
        if path is None:
            path = export_dialogs.save_file(self, "Export the effect's picture",
                                            f"effect_{self.number:03d}.png", "PNG image (*.png)")
        if not path:
            return
        try:
            own = self.own()
            if self.summon_shown():
                Path(path).write_bytes(ep.summon_png(own, data, self.game_summon()))
            else:
                Path(path).write_bytes(ep.big_png(own, data, self.shown_view()) if own is not None
                                       else ep.png(data, self.shown_view()))
        except OSError as exc:
            self.status.say(NOT_EXPORTED.format(why=exc), "error")
            return
        self.status.say(EXPORTED.format(path=path), "plain")
