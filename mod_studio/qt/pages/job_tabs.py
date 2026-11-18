"""
The New Content page's Jobs and Abilities tabs (Zodi's order of 13 November:
"the Jobs page"; his choices of 14 November: "Build it as shown", "it might
make more sense to split New Jobs and New Abilities onto two different
pages", and "What unlocks it" for what the design called "What opens it").

One rule for the New Content page: the list on the left, what it looks like
in the middle, its fields in the card on the right; but (his notes of 14
November: "removed the Card and just let the user edit everything directly on
the main window") the Jobs tab has no card, and a job's fields are boxes of
its middle beside Its look and What unlocks it. For a job the middle
is the job as the game shows it (his note of 14 November: these tabs "do not
really need the world map in the center of the screen"), for a new ability it
is the ability played out on the Abilities page's own map.

`JobTabs` is the part of `side_quests.SideQuestsPage` that holds the two
tabs; the engine is `mod_studio/mod_jobs.py` (a job's and an ability's file,
read and written as Mod Studio Framework reads them), and a quest unit's job
of the mod's own is `quest_edits.set_unit_job`.

The build's first part: the list, New job, New ability, both cards, what
unlocks a job, its skillset, a new ability on the map, a quest unit's job,
Export and opening a mod. Its second part, a job's look and art (the engine
`mod_studio/job_looks.py`): the middle draws the job as the game would (its
figures in the frames of the job it is based on, its look's sheet or its own
textures, in its own colors or its look's), a color is changed by clicking it,
and a right click on a figure, a portrait, an icon or the job screen art
replaces it with an image of the modder's own, puts it back, or exports it as
a PNG (as the item card's textures); the card's Look section chooses which of
the game's jobs drawn in the same frames it wears the look of.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QEvent, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFontMetricsF, QImage, QPalette, QPixmap
from PySide6.QtWidgets import (QBoxLayout, QCheckBox, QDialog, QDialogButtonBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMenu, QMessageBox, QPlainTextEdit, QPushButton,
                               QScrollArea, QSizePolicy, QStyle, QStyledItemDelegate, QVBoxLayout, QWidget,
                               QApplication)

from ... import ability_preview as ap
from ... import classic_sprites as cs
from ... import constants as c
from ... import job_looks as jl
from ... import mod_battles as mb
from ... import mod_jobs as mj
from ... import nxd_data
from ... import quest_edits as qx
from ... import reference_names
from ... import unit_sprites as us
from .. import theme
from ..widgets.field_rows import split_words
from ..widgets.layout_settle import retire, settle_layout
from .ability_map import AbilityMap, AbilityShow

# =============================================================================
# The words (every one a user sees; HANDOFF's "Words to sign off" lists them)
# =============================================================================

JOBS_TAB, ABILITIES_TAB = "Jobs", "Abilities"
JOB_SEARCH = "Search jobs, by name"
ABILITY_SEARCH = "Search abilities, by name"
NEW_JOB, NEW_ABILITY = "New job", "New ability"
#: (His note of 14 November, 19:10) A job's line in the list: what unlocks it, no longer the job it is based on.
JOB_LINE_NEEDS = "Unlocked by {needs}"
JOB_LINE_OPEN = "Unlocked for every unit"
NEED_WORDS = "{job} {level}"
ABILITY_LINE = "A new ability, in {skillsets}"
ABILITY_LINE_NONE = "A new ability, in no skillset yet"
#: `{owner}` a name in the possessive (`side_quests.possessive`: "Knight's", "Black Magicks'").
SKILLSET_OF = "{owner} {skillset}"
NO_GAME_JOBS = "Making a job needs the game's program, found from General Setup's folder of .pac files: {problem}."
NO_GAME_ABILITIES = ("Making an ability needs the game's program, found from General Setup's folder of .pac files: "
                     "{problem}.")
JOB_NAME_BAD = "A job's name is 1 to 40 characters."
JOB_TAKEN = "Your mod has a job named {name} already."
ABILITY_NAME_BAD = "An ability's name is 1 to 40 characters."
ABILITY_TAKEN = "Your mod has an ability named {name} already."
MOST_JOBS = "The game has room for {n} new jobs among every mod, and your mod has that many."
MOST_ABILITIES = "The game has room for {n} new abilities among every mod, and your mod has that many."
JOB_REMOVE_ASK = "Take the job {name} out of your mod?"
JOB_REMOVE_NEEDED = " {jobs} will no longer need it."
JOB_REMOVE_UNITS = " The units of your quests in it go back to {job}."
ABILITY_REMOVE_ASK = "Take the ability {name} out of your mod?"
ABILITY_REMOVE_SKILLSETS = " It leaves {skillsets}."
ABILITY_ONLY_ACTION = ("{name} is the only action ability of {skillsets}. A skillset has one at the least: give it "
                       "another first.")

NEW_ABILITY_NOTE = "It starts as {ability}: its numbers, its effect and its sound."

JOB_BAND, JOB_COLOR = "JOB", "#d77fb4"
NAME, DESCRIPTION, BASED_ON = "Name", "Description", "Based on"
NAME_TIP = "Up to 40 characters."
JOB_DESCRIPTION_TIP = "Up to 300 characters, on three lines at the most. The job screen shows it."
SUMMARY = "Job Summary"
SUMMARY_PLACEHOLDER = "Left empty, Job Summary shows the description."
SUMMARY_TIP = "The words Job Summary shows for the job, up to 4,000 characters."
SECTIONS = ("Skillset", "Stats", "Equipment", "Innate abilities", "Statuses and elements", "What unlocks it", "Look")
SKILLSET, STATS, EQUIPMENT, INNATE, STATUSES, UNLOCKS, LOOK = SECTIONS
ACTIONS = "Action abilities, {n} of 16"
OTHERS = "Reaction, support and movement abilities, {n} of 6"
ADD_ABILITY, TAKE_OUT = "Add an ability", "Take out"
ABILITIES_TIP = ("Drag one to move it. Once your mod is out, keep their order: a save keeps what a unit has learned "
                 "by its place in this list.")
OWN_ABILITY = "{ability} (your mod's own)"
OWN_JOB = "{job} (your mod's own)"
ABILITY_NUMBERED = "{name} ({n})"
TICKED_LINE, TICKED_NONE, CHANGE = "{label}: {names}", "nothing", "Change"
TICKS_TITLE = "{name}: {label}"
STATUS_INTRO = "Tick each status."
ELEMENT_INTRO = "Tick each element."
FLAGS_INTRO = "Tick each flag."
NEEDS_NONE = "Unlocked for every unit."
NEEDS_TIP = ("Up to 6 jobs, each at a level of 1 to 8 or mastered: the game's jobs or other jobs of your mod. A unit "
             "can take the job once it has every one of them.")
ADD_NEED = "Add a job"
LEVEL = "Level {n}"
#: (His answer of 16 November: "yes build both mastered job line and yes a job also be able to need one of your own
#: mod's jobs mastered") The level box's last choice: the job needed mastered (every ability of it learned); in the list's
#: line and on the card, the word for it in place of a level.
LEVEL_MASTERED = "Mastered"
NEED_MASTERED = "Mastered"
SHEET_NEEDED_MASTERED = "{job} needs it mastered"
#: His word of 14 November: "Male and Female instead of Man and Women".
MAN, WOMAN = "Male", "Female"
#: (The second part) The look's note, under the figures.
LOOK_NOTE = ("Click a color to change it, or a palette's small figure to see the job in that palette. Right click a "
             "figure, a portrait, an icon or the job screen art to use an image of your own.")
#: A combo's choice of a job's own icon or skillset icon (its art's, not one of the game's).
OWN_ART = "own"

#: The middle's title: the job's name alone (his note of 14 November, 23:31: no ", as the game shows it"; and no green
#: "Ready." under it, `JobFoot`).
SHEET_TITLE = "{job}"
#: (His notes of 14 November: "removed the Card and just let the user edit everything directly on the main window")
#: The Jobs tab's boxes beside Its look and What unlocks it: the card's groups before.
SHEET_JOB, SHEET_SKILLSET = "The job", "Its skillset"
#: (His notes of 14 November, 19:10) Its skillset's rows: all 16 and all 6 shown, each this high, an empty one clicked to
#: add; Job Summary's lines shown; the Equipment box's columns of ticks.
ROW_HEIGHT, SUMMARY_LINES, EQUIPMENT_COLUMNS = 22, 12, 3
SKILLSET_HINT = "Click an empty row to add an ability; drag one to move it."
#: (His note of 14 November, 19:10) A new job starts with the Squire's job screen art, the game's own, as its own.
SQUIRE_PICTURES = {"Man": "jv_01_m_uitx.tex", "Woman": "jv_01_f_uitx.tex"}
#: (His note of 14 November: "cycle through the palettes") The palette a male or a female is shown in.
PALETTE_PREVIOUS, PALETTE_NEXT = "Previous", "Next"
PALETTE_SHOWN_TIP = "Click to see the job in this palette: its figure and its portrait."
SHEET_LOOK = "Its look"
SHEET_PALETTE = "Palette {n}"
SHEET_NEEDED_BY = "{job} needs it at level {n}"
SHEET_JP = "{n} JP"
#: (The second part) The middle's look: its art's panels, their menus (as the item card's textures') and dialogs.
SHEET_JOB_ICON, SHEET_SKILLSET_ICON = "Job icon", "Skillset icon"
SHEET_PORTRAIT, SHEET_ART = "Portrait", "Job screen art"
NO_ART = "No art"
REPLACE_ART, USE_LOOKS, USE_GAME_ICON, EXPORT_ART = "Replace...", "Use its look's", "Use the game's icon", "Export as PNG..."
COLOR_TIP, SEE_THROUGH_TIP = "Color {k}", "Color 0, see through"
COLOR_TITLE = "{job}: {who} palette {n}, color {k}"
ART_PARTS = {("figure", "Man"): "the male figure", ("figure", "Woman"): "the female figure",
             ("portrait", "Man"): "the male portrait", ("portrait", "Woman"): "the female portrait",
             ("picture", "Man"): "the male job screen art", ("picture", "Woman"): "the female job screen art",
             ("icon", ""): "its job icon", ("command", ""): "its skillset's icon"}
REPLACE_TITLE = "An image for {job}: {part}"
EXPORT_TITLE = "Export {part} of {job} as PNG"
EXPORT_NAME = "{job} {part}.png"
PNG_FILES = "PNG image (*.png)"
FIGURE_NEAREST = "{n} pixels of the image weren't palette 0's colors: each was made the nearest of them."
#: (17 November 2026; his second point of 16 November: "New Jobs sprites should be able to have this as well") What is
#: said once a figure 2 to 8 times the game's size is given, and what its frames' line says of it.
FIGURE_BIGGER = ("A bigger texture, {n} times the game's size: Mod Studio Framework shows it in the game at the same "
                 "size on the screen as the game's.")
FRAMES_SHOWN_BIG = "Type {n} frames, {s} times the game's size"
#: (The thirtieth session; his choices of 17 November: tied to one palette, up to 4 times, Replace... keeps an image's
#: own colors) What is said once a figure with colors of its own is given, or past 4 times the size, and its frames'
#: line's words for it. The figure here is drawn in palette 0's colors, as the game draws it without the framework.
FIGURE_OWN = ("{n} pixels of the image have colors of their own, kept for palette 0: Mod Studio Framework shows them in "
              "the game where the job wears palette 0, tinted as the game tints it, and elsewhere each is the nearest "
              "of the palette's colors. The figure here is drawn in palette 0's colors.")
FIGURE_OWN_BIG = ("{n} pixels of the image have colors of their own, which were made the nearest of palette 0's colors: "
                  "a texture of more colors is up to 4 times the game's size.")
FRAMES_SHOWN_OWN = ", in more colors"
#: (His 8th note of 14 November, Type 1 and Type 2, and classic sprites; his picks "Tell it, modder can change" and
#: "Smooth, plain if asked") A figure's frames, under it and in its menu; Replace...'s files for a figure; what is said
#: once a classic sprite or the game's size of texture is given; Smooth the edges.
FRAMES_SHOWN = "Type {n} frames"
FRAMES_PICK = ("Type 1 frames", "Type 2 frames")
SMOOTH_EDGES = "Smooth the edges"
FIGURE_FILES = "Images and classic sprites (*.png *.bmp *.spr *.jpg *.jpeg *.gif *.tga *.webp);;All files (*)"
CLASSIC_MADE = "A classic sprite, doubled to the game's size{smooth}: its {n} palettes are the {who}'s colors now."
CLASSIC_SMOOTHED, CLASSIC_PLAIN = " with its edges smoothed", ""
CLASSIC_PALETTE = "A classic sprite, doubled to the game's size{smooth}: its palette is the {who}'s colors now."
CLASSIC_PAST = "{n} of its pixels were numbered past 15: each was taken as that color of a palette of 16."
FRAMES_TOLD = "Told from the sheet: it is drawn for Type {n} frames (right click the figure to change)."
FRAMES_UNTOLD = ("Its frames couldn't be told from the sheet: it is drawn for Type {n} frames, as the job it is based "
                 "on (right click the figure to change).")

ABILITY_BAND, ABILITY_COLOR = "ABILITY", "#8f9be8"
#: (His note of 14 November, 19:10: no card for the Abilities tab) Its middle's title, its first box, and the box of
#: the map that plays it, the map at least this tall. (His note of 14 November, 23:31) The title the ability's name alone.
ABILITY_SHEET_TITLE = "{ability}"
SHEET_ABILITY = "The ability"
ABILITY_ON_MAP = "On the map"
ABILITY_MAP_LEAST = 480
ABILITY_DESCRIPTION_TIP = "Up to 300 characters, on three lines at the most."
ABILITY_BASED_TIP = "The game's ability it is based on: its effect, how its user moves and its sound."
JP_COST, MP_COST = "JP Cost", "MP Cost"
ABILITY_SECTIONS = ("What it does", "How it is aimed", "Flags", "For units the game moves")
DOES, AIMED, FLAGS, MOVED = ABILITY_SECTIONS
FORMULA, INFLICT, ELEMENTS = "Formula", "Inflict Status", "Elements"
CHANCE, AI_FLAGS = "Chance to Learn", "AI Behavior Flags"
USED_BY = "In the skillsets of"
USED_BY_NONE = "No skillset yet: add it to a job's skillset on the Jobs tab."

#: A quest unit's Main Job's choice of one of the mod's jobs (the unit card's).
UNIT_OWN_JOB = "{job} (your mod's own)"

#: Where the tabs are among the page's, and the middle's parts they show.
JOBS_INDEX, ABILITIES_INDEX = 3, 4


def _page():
    """The page's own module (its small parts: `muted`, `combo`, `CardPane`), imported late: it imports this one."""
    from . import side_quests
    return side_quests


def _box(layout_cls=QVBoxLayout, margins=(0, 0, 0, 0), spacing=6) -> tuple:
    holder = QWidget()
    layout = layout_cls(holder)
    layout.setContentsMargins(*margins)
    layout.setSpacing(spacing)
    return holder, layout


def _panel(title: str = "") -> tuple:
    """A framed part of the middle: its title over its body's layout."""
    colours = theme.current()
    frame = QFrame()
    frame.setObjectName("sheetPanel")
    frame.setStyleSheet(f"#sheetPanel {{ border: 1px solid {colours['border']}; border-radius: 6px; }}")
    column = QVBoxLayout(frame)
    column.setContentsMargins(12, 10, 12, 12)
    column.setSpacing(8)
    if title:
        label = QLabel(title)
        label.setStyleSheet("font-weight: 600;")
        column.addWidget(label)
    return frame, column


class Turning(QWidget):
    """Parts side by side while they fit the width, one under the other when they don't (a narrow window): the
    middle is never cut off at its right."""

    def __init__(self, spacing: int = 10):
        super().__init__()
        self.across = QBoxLayout(QBoxLayout.LeftToRight, self)
        self.across.setContentsMargins(0, 0, 0, 0)
        self.across.setSpacing(spacing)
        self.parts: list = []

    def add(self, widget: QWidget, stretch: int = 1) -> None:
        self.parts.append(widget)
        self.across.addWidget(widget, stretch)

    def needed(self) -> int:
        """The width its parts take side by side."""
        return (sum(max(w.minimumSizeHint().width(), w.minimumWidth()) for w in self.parts)
                + self.across.spacing() * max(0, len(self.parts) - 1))

    def fit(self, width: int) -> None:
        """Side by side where `width` holds its parts so, else one under the other."""
        wanted = QBoxLayout.LeftToRight if width >= self.needed() else QBoxLayout.TopToBottom
        if self.across.direction() != wanted:
            self.across.setDirection(wanted)


#: An ability's JP in words, kept on its row of a skillset's list (`JpDelegate`).
JP_ROLE = Qt.UserRole + 1


class JpDelegate(QStyledItemDelegate):
    """A skillset's list of abilities with each one's JP at its row's right (his note of 14 November: the abilities
    edited where they are listed, "with their JP cost still to their Right")."""

    def paint(self, painter, option, index):                          # noqa: D401
        super().paint(painter, option, index)
        words = index.data(JP_ROLE)
        if not words:
            return
        painter.save()
        selected = bool(option.state & QStyle.State_Selected)
        painter.setPen(option.palette.color(QPalette.HighlightedText if selected else QPalette.Text))
        painter.drawText(option.rect.adjusted(0, 0, -8, 0), int(Qt.AlignRight | Qt.AlignVCenter), str(words))
        painter.restore()


class JobFoot:
    """What Mod Studio Framework would say of the job, the ability or the item, under the middle's title (the card's
    foot before: these tabs have no card, his notes of 14 November); nothing, the line hidden, while it would say
    nothing (his note of 14 November, 23:31: no green "Ready."). Its label is in the sheet before it says anything,
    so it is never shown as a window of its own."""

    def __init__(self, label: QLabel):
        self.status_label = label

    def status(self, problems: list, ready: Optional[str] = None, plain: list = ()) -> None:
        page = _page()
        page.CardPane.status(self, problems, "" if ready is None else ready, plain)
        shown = bool(self.status_label.text())
        if not shown or self.status_label.parent() is not None:
            self.status_label.setVisible(shown)


class Swatch(QLabel):
    """One color of a palette in the middle: `clicked` called on a left click (none for the see through color)."""

    def __init__(self, clicked=None):
        super().__init__()
        self._clicked = clicked
        if clicked is not None:
            self.setCursor(Qt.PointingHandCursor)

    def click(self) -> None:
        if self._clicked is not None:
            self._clicked()

    def mousePressEvent(self, event):                                 # noqa: N802
        if event.button() == Qt.LeftButton and self._clicked is not None:
            self._clicked()
            return
        super().mousePressEvent(event)


class SheetScroll(QScrollArea):
    """The middle's scrolling part: its `Turning` parts fitted to the width it shows as that changes (each with what
    of the width its frame takes)."""

    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.turnings: list = []

    def fit(self) -> None:
        for turning, inset in self.turnings:
            turning.fit(self.viewport().width() - inset)

    def resizeEvent(self, event):                                     # noqa: N802
        super().resizeEvent(event)
        self.fit()


class LinesBox(QPlainTextEdit):
    """A box of text as tall as `lines` lines of its font, all of them shown with nothing to scroll (Job Summary's
    twelve: his note of 14 November, 19:10). Measured again whenever its font or style changes: a box gets the page's
    font only once it is on the page, so its height worked out as it is made is a line short or more."""

    def __init__(self, text: str, lines: int):
        super().__init__(text)
        self._lines = lines
        self._fit()

    def _fit(self) -> None:
        import math
        # A line as QPlainTextEdit lays one out (its height rounded up); its margin above and below; the pixel
        # QPlainTextEdit keeps clear at the bottom before it counts a line shown; its frame.
        line = math.ceil(QFontMetricsF(self.font()).lineSpacing())
        margins = self.contentsMargins()
        self.setFixedHeight(line * self._lines + math.ceil(2 * self.document().documentMargin()) + 1
                            + margins.top() + margins.bottom() + self.viewportMargins().top()
                            + self.viewportMargins().bottom())

    def event(self, event):                                           # noqa: D401
        done = super().event(event)
        if event.type() in (QEvent.Polish, QEvent.FontChange, QEvent.StyleChange):
            self._fit()
        return done


def settle_sheet(sheet: QWidget) -> None:
    """A middle's sheet just put in a shown page, laid out now (his note of 14 November: "the whole main window seems
    to refresh and jitter with elements out of position and then fix itself"). Shown at once: Qt would show it on its
    next trip round the event loop, and only then size its scroll area, when its side by side parts turn (the scroll
    area's resize, sent as it shows, fits them); then every layout under it done, twice (a part that turns lays out
    again)."""
    sheet.show()
    scroll = sheet.findChild(SheetScroll)
    for _round in range(2):
        settle_layout(scroll.widget() if scroll is not None and scroll.widget() is not None else sheet)
        QApplication.sendPostedEvents(None, QEvent.LayoutRequest)


def _narrow(card) -> None:
    """Nothing in a card asks for more width than the card has."""
    for kind in (QPlainTextEdit, QLineEdit, QListWidget):
        for w in card.findChildren(kind):
            w.setMinimumWidth(40)
            w.setSizePolicy(QSizePolicy.Ignored, w.sizePolicy().verticalPolicy())
    for w in card.findChildren(QLabel):
        if w.wordWrap():
            w.setMinimumWidth(40)


class PickDialog(QDialog):
    """One thing picked from a list, with a box to search it by name: an ability for a skillset, a job to need."""

    def __init__(self, parent, title: str, search_words: str, choices: list):
        super().__init__(parent)
        self.setWindowTitle(title)
        column = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setPlaceholderText(search_words)
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter)
        column.addWidget(self.search)
        self.listing = QListWidget()
        self.listing.setAlternatingRowColors(True)
        for data, words in choices:
            entry = QListWidgetItem(str(words))
            entry.setData(Qt.UserRole, data)
            self.listing.addItem(entry)
        if self.listing.count():
            self.listing.setCurrentRow(0)
        self.listing.itemDoubleClicked.connect(lambda _item: self.accept())
        column.addWidget(self.listing, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        column.addWidget(buttons)
        self.resize(380, 480)

    def _filter(self, text: str) -> None:
        wanted = text.strip().lower()
        first = None
        for n in range(self.listing.count()):
            entry = self.listing.item(n)
            hidden = bool(wanted) and wanted not in entry.text().lower()
            entry.setHidden(hidden)
            if not hidden and first is None:
                first = n
        if first is not None:
            self.listing.setCurrentRow(first)

    def answer(self):
        entry = self.listing.currentItem()
        return entry.data(Qt.UserRole) if entry is not None and not entry.isHidden() else None


class NewDialog(QDialog):
    """New job, New ability: its name and the game's one it is based on, with what it starts with said under them.
    (His word of 14 November: a new job asks its name alone and starts as the Squire, `pick=False`; what it is based
    on is changed once it is made.)"""

    def __init__(self, parent, title: str, name: str, choices: list, based, note: str, tip: str, problem,
                 pick: bool = True):
        super().__init__(parent)
        page = _page()
        self.setWindowTitle(title)
        self._note, self._problem = note, problem
        column = QVBoxLayout(self)
        column.addWidget(page.caption(NAME))
        self.name = QLineEdit(name)
        self.name.setMaxLength(mj.NAME_MOST)
        self.name.setToolTip(NAME_TIP)
        self.name.selectAll()
        column.addWidget(self.name)
        self._based, self.based = based, None
        if pick:
            column.addWidget(page.caption(BASED_ON))
            self.based = page.combo(choices, based)
            self.based.setToolTip(tip)
            self.based.currentIndexChanged.connect(self._show_note)
            column.addWidget(self.based)
        self.note = page.muted("")
        column.addWidget(self.note)
        self.said = QLabel("")
        self.said.setWordWrap(True)
        self.said.setStyleSheet(f"color: {theme.current()['danger']};")
        self.said.setVisible(False)
        column.addWidget(self.said)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        column.addWidget(buttons)
        self.setMinimumWidth(420)
        self._names = dict(choices)
        self._show_note()

    def _chosen(self):
        return self.based.currentData() if self.based is not None else self._based

    def _show_note(self, _index=None) -> None:
        words = str(self._names.get(self._chosen(), ""))
        # "Fire (16)": the note names it without its number.
        words = words.rsplit(" (", 1)[0] if words.endswith(")") else words
        # (His note of 14 November, 19:10) New job's dialog has none.
        text = self._note.format(owner=_page().possessive(words), ability=words) if self._note else ""
        self.note.setText(text)
        self.note.setVisible(bool(text))

    def answer(self) -> tuple:
        return self.name.text().strip(), self._chosen()

    def _accept(self) -> None:
        said = self._problem(self.name.text().strip())
        if said:
            self.said.setText(said)
            self.said.setVisible(True)
            return
        self.accept()


class NewAbilityMap(AbilityMap):
    """The Abilities page's own map, playing a new ability of the mod's: shown by the mod's jobs whose skillsets
    hold it (`own_users`), or, while none does, by whoever uses the game's ability it is based on."""

    def __init__(self, state, parent=None):
        super().__init__(state, parent)
        self.own_users: list = []

    def users_of(self, ability: int) -> list:
        return list(self.own_users) or super().users_of(ability)


class JobTabs:
    """The part of the New Content page that holds its Jobs and Abilities tabs (see the module's notes)."""

    # =========================================================================
    # Built with the page
    # =========================================================================

    def _build_job_tabs(self) -> None:
        """The two tabs' lists (the page's left) and what the middle shows for them, added to the page's stacks."""
        page = _page()
        #: The job and the ability picked (their folders), or None.
        self.job_pick: Optional[str] = None
        self.ability_pick: Optional[str] = None
        self._job_sprites = None
        self._job_sprites_key = None
        self._ability_map: Optional[NewAbilityMap] = None
        #: (His note of 14 November, 19:10: no card for the Abilities tab) The ability's sheet in the middle, what
        #: Mod Studio Framework would say of it under its title, its words that follow typing, and what it was made for
        #: (as the job's sheet: the ability picked, its edit, `_jobs_version`) with its fields.
        self.ability_sheet: Optional[QWidget] = None
        self.ability_foot: Optional[JobFoot] = None
        self.ability_sheet_widgets: dict = {}
        self._ability_made_for = None
        self._ability_fields: dict = {}
        self._ability_sheet_was = None
        #: (His notes of 14 November) The palette each of a job's male and female is shown in (`show_palette`), what
        #: Mod Studio Framework would say of the job (under the middle's title) and the middle's words of the job
        #: that follow typing (`_refresh_job_words`).
        self.shown_palettes: dict = {"Man": 0, "Woman": 0}
        self.job_foot: Optional[JobFoot] = None
        self.job_sheet_widgets: dict = {}
        self._sheet_was = None
        #: (His note of 14 November: switching between the tabs was slow) What the middle's sheet was made for: the
        #: job picked, its edit and the count of changes then (`_jobs_version`, one more at each `_jobs_changed`). A
        #: sheet still the job's as it is is shown again as it was, not made again; its fields kept with it.
        self._jobs_version = 0
        self._sheet_made_for = None
        self._sheet_fields: dict = {}
        self._sheet_timer = QTimer(self)
        self._sheet_timer.setSingleShot(True)
        self._sheet_timer.setInterval(350)
        self._sheet_timer.timeout.connect(self._sheet_follows)
        for kind in ("job", "ability"):
            left, column = _box()
            search = QLineEdit()
            search.setPlaceholderText(JOB_SEARCH if kind == "job" else ABILITY_SEARCH)
            search.setClearButtonEnabled(True)
            column.addWidget(search)
            listing = QListWidget()
            listing.setAlternatingRowColors(True)
            listing.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            column.addWidget(listing, 1)
            message = page.muted("")
            message.setVisible(False)
            column.addWidget(message)
            new = QPushButton(NEW_JOB if kind == "job" else NEW_ABILITY)
            remove = QPushButton(page.REMOVE)
            column.addWidget(page.row(new, remove, stretch_first=False))
            self.left_stack.addWidget(left)
            if kind == "job":
                self.job_search, self.job_list, self.job_message = search, listing, message
                self.new_job_button, self.remove_job_button = new, remove
                search.textChanged.connect(lambda text: self._filter_list(self.job_list, text))
                listing.currentItemChanged.connect(self._job_list_picked)
                new.clicked.connect(self.new_job)
                remove.clicked.connect(self.remove_job)
            else:
                self.ability_search, self.ability_list, self.ability_message = search, listing, message
                self.new_ability_button, self.remove_ability_button = new, remove
                search.textChanged.connect(lambda text: self._filter_list(self.ability_list, text))
                listing.currentItemChanged.connect(self._ability_list_picked)
                new.clicked.connect(self.new_ability)
                remove.clicked.connect(self.remove_ability)
        # The middle: a job as the game shows it (made again as it changes), and the map a new ability is played on.
        self.job_sheet_holder, self._job_sheet_column = _box()
        self.job_sheet: Optional[QWidget] = None
        self.middle.addWidget(self.job_sheet_holder)
        # (His note of 14 November, 19:10) The ability's sheet holds the map now, beside its fields.
        self.ability_map_holder, self._ability_map_column = _box()
        self.middle.addWidget(self.ability_map_holder)

    # =========================================================================
    # The mod's jobs and abilities, and the game's
    # =========================================================================

    def jobs_store(self) -> dict:
        """The mod's own jobs as the Jobs tab has them (`state.mod_jobs`: `{folder: mod_jobs.JobEdit}`)."""
        jobs = getattr(self.state, "mod_jobs", None)
        if jobs is None:
            jobs = self.state.mod_jobs = {}
        return jobs

    def abilities_store(self) -> dict:
        """The mod's own abilities as the Abilities tab has them (`state.mod_abilities`)."""
        abilities = getattr(self.state, "mod_abilities", None)
        if abilities is None:
            abilities = self.state.mod_abilities = {}
        return abilities

    def in_jobs(self) -> bool:
        return self.tabs.currentIndex() == JOBS_INDEX

    def in_abilities(self) -> bool:
        return self.tabs.currentIndex() == ABILITIES_INDEX

    def show_jobs(self, folder: Optional[str] = None) -> None:
        """The Jobs tab shown, the job in `folder` picked when given."""
        if folder is not None:
            self.job_pick = folder
        if not self.in_jobs():
            self.tabs.setCurrentIndex(JOBS_INDEX)
        else:
            self._tab_changed(JOBS_INDEX)

    def show_abilities(self, folder: Optional[str] = None) -> None:
        """The Abilities tab shown, the ability in `folder` picked when given."""
        if folder is not None:
            self.ability_pick = folder
        if not self.in_abilities():
            self.tabs.setCurrentIndex(ABILITIES_INDEX)
        else:
            self._tab_changed(ABILITIES_INDEX)

    def _picked_job(self) -> Optional[mj.JobEdit]:
        return self.jobs_store().get(self.job_pick) if self.job_pick else None

    def _picked_ability(self) -> Optional[mj.AbilityEdit]:
        return self.abilities_store().get(self.ability_pick) if self.ability_pick else None

    def game_jobs(self) -> tuple:
        """(the game's jobs and abilities read from its program, `mod_jobs.GameJobs`, or None; why not, in words)."""
        path = self.find_program()
        if path is None:
            return None, _page().NO_PROGRAM
        try:
            return mj.game_jobs(path), ""
        except (OSError, mj.JobsError) as exc:
            return None, str(exc)

    def _game_names(self, key: str) -> dict:
        """`{number: name}` of one of the game's tables as the mod has it: "job", "job_command" or "ability"."""
        cache = self.__dict__.setdefault("_job_names", {})
        stamp = (key, str(getattr(self.state, "nxd_sqlite_path", None)))
        if stamp not in cache:
            cache[stamp] = {n: name for n, name in _page().nxd_names(self.state, key).items() if name}
        return cache[stamp]

    def _game_row(self, key: str, number: int) -> dict:
        """One of the game's tables' rows as the mod has it (in English), or {}."""
        try:
            return dict(nxd_data.effective_values(self.state, key, number, "en") or {})
        except Exception:                                             # noqa: BLE001
            return {}

    def job_word(self, number: int) -> str:
        return self._game_names("job").get(number) or f"job {number}"

    def skillset_word(self, number: int) -> str:
        return self._game_names("job_command").get(number) or f"skillset {number}"

    def ability_word(self, value) -> str:
        """An ability in words: one of the mod's own by its name, one of the game's by the game's."""
        if isinstance(value, str):
            return value
        return self._game_names("ability").get(value) or f"ability {value}"

    def _generic_jobs(self) -> list:
        return [(n, self.job_word(n)) for n in range(mj.FIRST_LIKE, mj.LAST_LIKE + 1)]

    def _action_choices(self) -> list:
        """The game's action abilities a new ability may be based on (1 to 367), by name."""
        names = self._game_names("ability")
        return [(n, ABILITY_NUMBERED.format(name=names[n], n=n)) for n in sorted(names)
                if mj.ABILITY_FIRST_LIKE <= n <= mj.ABILITY_LAST_LIKE]

    def own_job_choices(self) -> list:
        """The mod's jobs a quest unit may be put in: `[(the job's name, its words on the unit's card)]`."""
        return [(e.job.name, UNIT_OWN_JOB.format(job=e.job.name)) for e in self.jobs_store().values()]

    def own_job_like(self, name: str) -> Optional[int]:
        """The game's job one of the mod's jobs is based on, None when the mod has no job of that name."""
        edit = mj.job_named(self.jobs_store(), name)
        return edit.job.like if edit is not None else None

    # =========================================================================
    # The lists
    # =========================================================================

    def _need_words(self, need: mj.Need) -> str:
        return need.own if need.own else self.job_word(need.job)

    def _skillsets_holding(self, name: str) -> list:
        return [SKILLSET_OF.format(owner=_page().possessive(e.job.name), skillset=e.job.skillset_name)
                for e in mj.skillsets_with(self.jobs_store(), name)]

    def _fill_jobs(self) -> None:
        """The Jobs tab's list: the mod's jobs, each its name over what unlocks it."""
        page = _page()
        jobs = self.jobs_store()
        if self.job_pick not in jobs:
            self.job_pick = next(iter(jobs), None)
        self.job_list.blockSignals(True)
        self.job_list.clear()
        for folder, edit in jobs.items():
            needs = page._listed([NEED_WORDS.format(job=self._need_words(n), level=NEED_MASTERED if n.mastered else n.level)
                                  for n in edit.job.needs])
            line = JOB_LINE_NEEDS.format(needs=needs) if needs else JOB_LINE_OPEN
            entry = QListWidgetItem(f"{edit.job.name}\n{line}")
            entry.setData(Qt.UserRole, folder)
            self.job_list.addItem(entry)
            if folder == self.job_pick:
                self.job_list.setCurrentItem(entry)
        self.job_list.blockSignals(False)
        self.remove_job_button.setEnabled(self.job_pick is not None)
        self._filter_list(self.job_list, self.job_search.text())

    def _fill_abilities(self) -> None:
        """The Abilities tab's list: the mod's abilities, each its name over the skillsets that hold it."""
        page = _page()
        abilities = self.abilities_store()
        if self.ability_pick not in abilities:
            self.ability_pick = next(iter(abilities), None)
        self.ability_list.blockSignals(True)
        self.ability_list.clear()
        for folder, edit in abilities.items():
            held = self._skillsets_holding(edit.ability.name)
            line = ABILITY_LINE.format(skillsets=page._listed(held)) if held else ABILITY_LINE_NONE
            entry = QListWidgetItem(f"{edit.ability.name}\n{line}")
            entry.setData(Qt.UserRole, folder)
            self.ability_list.addItem(entry)
            if folder == self.ability_pick:
                self.ability_list.setCurrentItem(entry)
        self.ability_list.blockSignals(False)
        self.remove_ability_button.setEnabled(self.ability_pick is not None)
        self._filter_list(self.ability_list, self.ability_search.text())

    @staticmethod
    def _filter_list(listing: QListWidget, text: str) -> None:
        wanted = text.strip().lower()
        for n in range(listing.count()):
            entry = listing.item(n)
            entry.setHidden(bool(wanted) and wanted not in entry.text().lower())

    def _job_list_picked(self, entry, _previous=None) -> None:
        if entry is None:
            return
        self.job_pick = entry.data(Qt.UserRole)
        self.remove_job_button.setEnabled(True)
        self._say("")
        self._show_card()
        self._show_middle()

    def _ability_list_picked(self, entry, _previous=None) -> None:
        if entry is None:
            return
        self.ability_pick = entry.data(Qt.UserRole)
        self.remove_ability_button.setEnabled(True)
        self._say("")
        self._show_card()
        self._show_middle()

    def _jobs_changed(self, refill: bool = True, card: bool = True, middle: bool = True) -> None:
        """After a job or an ability changed: the lists, the card, the middle; Export's summary. (His notes of 14
        November) The Jobs tab has no card: its middle, which holds the job's fields, is made again once."""
        self._jobs_version += 1
        if refill:
            self._fill_jobs()
            self._fill_abilities()
        if self.in_jobs():
            if card or middle:
                self._show_middle()
        else:
            if card:
                self._show_card()
            if middle:
                self._show_middle()
        self.edits_changed.emit()

    def _job_status(self) -> None:
        """What Mod Studio Framework would say of the job or the ability shown, again, under the middle's title (his
        notes of 14 November: neither tab has a card)."""
        if self.in_jobs() and self._picked_job() is not None:
            if self.job_foot is not None:
                self.job_foot.status(self._job_problems(self._picked_job()))
        elif self.in_abilities() and self._picked_ability() is not None:
            if self.ability_foot is not None:
                self.ability_foot.status(mj.ability_problems(self.abilities_store(), self._picked_ability()))

    def _typed(self) -> None:
        """After a letter typed in a box of the middle: its foot now, the list and the middle's words (an ability's map)
        once the typing stops. A job's words typed (its skillset's name) may be what an ability's sheet says of it: that
        sheet is made again when next shown."""
        if self.in_jobs():
            self._ability_made_for = None
        self._job_status()
        self._sheet_timer.start()
        self.edits_changed.emit()

    def _sheet_follows(self) -> None:
        if self.in_jobs():
            # (His note of 14 November: the whole window jittered as a field changed) The list and the middle's words
            # follow; nothing is made again, so the box typed in keeps its place.
            self._fill_jobs()
            self._refresh_job_words()
        elif self.in_abilities():
            # (His note of 14 November, 19:10: no card) The list, the middle's words and the map follow; nothing is
            # made again, so the box typed in keeps its place.
            self._fill_abilities()
            self._refresh_ability_words()
            self._play_ability()

    def _refresh_job_words(self) -> None:
        """The middle's words of the job again where they show (its title, its name, its description, its skillset's
        name and description), nothing made again."""
        edit = self._picked_job()
        if edit is None or not self.job_sheet_widgets:
            return
        job = edit.job
        for key, words in (("title", SHEET_TITLE.format(job=job.name)), ("name", job.name),
                           ("description", job.description), ("skillset_name", job.skillset_name),
                           ("skillset_description", job.skillset_description)):
            label = self.job_sheet_widgets.get(key)
            if label is not None:
                label.setText(words)

    def _job_problems(self, edit: mj.JobEdit) -> list:
        """What Mod Studio Framework would say of the job as Export writes it; a file its Look or art names is taken
        as there when the mod carries it (`_job_file_size`)."""
        return mj.job_problems(self.jobs_store(), self.abilities_store(), edit, self._job_file_size)

    def _job_file_size(self, path: str):
        """A file of the mod's, by its path from the mod's folder, as the helper will find it: one the mod carries
        through (its own files, or a file of the game's it replaces), its size where it is one of its own."""
        own = getattr(self.state, "mod_own_files", None) or {}
        wanted = path.replace("\\", "/").lower()
        for rel, source in own.items():
            if str(rel).replace("\\", "/").lower() == wanted:
                try:
                    return source.stat().st_size if hasattr(source, "stat") else mj.ANY_SIZE
                except OSError:
                    return None
        data = "fftivc/data/enhanced/"
        if wanted.startswith(data):
            for kept in (getattr(self.state, "other_file_replacements", None) or {},
                         getattr(self.state, "texture_edits", None) or {},
                         getattr(self.state, "utexpt_edits", None) or {}):
                if any(str(k).replace("\\", "/").lower() == wanted[len(data):] for k in kept):
                    return mj.ANY_SIZE
        return None

    # =========================================================================
    # New job, New ability, Remove
    # =========================================================================

    def _job_name_problem(self, name: str, own: Optional[mj.JobEdit] = None) -> str:
        if not mj.good_name(name):
            return JOB_NAME_BAD
        if any(e is not own and e.job.name == name for e in self.jobs_store().values()):
            return JOB_TAKEN.format(name=name)
        return ""

    def _ability_name_problem(self, name: str, own: Optional[mj.AbilityEdit] = None) -> str:
        if not mj.good_name(name):
            return ABILITY_NAME_BAD
        if any(e is not own and e.ability.name == name for e in self.abilities_store().values()):
            return ABILITY_TAKEN.format(name=name)
        return ""

    def new_job(self) -> None:
        """New job: its name asked; it starts as the Squire (his word of 14 November: no Based on in the menu), ready
        as made (its record, its skillset's abilities in a skillset of its own, the game's words for both, and the
        Squire's Job Summary to start from)."""
        jobs = self.jobs_store()
        game, why = self.game_jobs()
        if game is None:
            self._say(NO_GAME_JOBS.format(problem=why))
            return
        if len(jobs) >= mj.MOST_JOBS:
            self._say(MOST_JOBS.format(n=mj.MOST_JOBS))
            return
        name = mj.free_name("New Job", [e.job.name for e in jobs.values()])
        dialog = NewDialog(self, NEW_JOB, name, [(mj.FIRST_LIKE, self.job_word(mj.FIRST_LIKE))], mj.FIRST_LIKE,
                           "", "", self._job_name_problem, pick=False)
        answer = self._ask("new_job", lambda: dialog.answer() if dialog.exec() == QDialog.Accepted else None)
        if not answer:
            return
        name, like = answer[0], int(answer[1])
        said = self._job_name_problem(name)
        if said:
            self._say(said)
            return
        try:
            skillset = game.job_record(like)[mj.SKILLSET_AT]
            if not mj.FIRST_SKILLSET <= skillset <= mj.LAST_SKILLSET:
                skillset = mj.FIRST_SKILLSET
            row = self._game_row("job", like)
            command = self._game_row("job_command", skillset)
            description = row.get("Description") or ""
            job = mj.copy_of_job(game, like, name,
                                 description if mj.good_description(description) else name,
                                 command.get("Name") if mj.good_name(command.get("Name")) else name,
                                 command.get("Description") if mj.good_description(command.get("Description"))
                                 else name)
        except mj.JobsError as exc:
            self._say(NO_GAME_JOBS.format(problem=exc))
            return
        # His word of 14 November: Job Summary starts from the job it is based on's, no button.
        job.summary = self._game_summary(like)
        folder = mj.free_folder(name, jobs)
        jobs[folder] = mj.JobEdit(folder, job)
        # (His note of 14 November, 19:10) The Squire's job screen art to start from, as its own: No art takes it off.
        jobs[folder].art.pictures.update(self._squire_pictures())
        self.job_pick = folder
        self._say("")
        self.show_jobs(folder)
        self._jobs_changed()

    def _squire_pictures(self) -> dict:
        """The game's job screen art of the Squire, a male's and a female's, each as a job's own picture (a PNG of 400
        by 652, as Replace... makes one): a new job starts with it (his note of 14 November, 19:10: "just have it display
        the squires art when creating a new job"; No art on the art's menu takes it off, and a job with none shows none
        in the game). A sex whose art the unpacked game hasn't is left without."""
        import io
        from PIL import Image
        from PySide6.QtCore import QBuffer, QIODevice
        pictures = {}
        for who, name in SQUIRE_PICTURES.items():
            image = self._game_art(f"{jl.PICTURE_TEXTURES}/{name}")
            if image is None or image.isNull():
                continue
            buffer = QBuffer()
            buffer.open(QIODevice.WriteOnly)
            image.save(buffer, "PNG")
            with Image.open(io.BytesIO(bytes(buffer.data()))) as picture:
                picture.load()
                pictures[who] = jl.png(jl.fitted(picture, jl.PICTURE_SIZE))
        return pictures

    def remove_job(self) -> None:
        """Remove: the job picked, asked first; no job of the mod needs it after, and the units of the mod's quests
        that wore it are left in the game's job it was based on."""
        page = _page()
        edit = self._picked_job()
        if edit is None:
            return
        needing = [e.job.name for e, _need in mj.needed_by(self.jobs_store(), edit.job.name)]
        wearing = qx.units_in_job(self.quests(), edit.job.name)
        question = JOB_REMOVE_ASK.format(name=edit.job.name)
        if needing:
            question += JOB_REMOVE_NEEDED.format(jobs=page._listed(needing))
        if wearing:
            question += JOB_REMOVE_UNITS.format(job=self.job_word(edit.job.like))
        sure = self._ask("remove_job",
                         lambda: QMessageBox.question(self, page.TITLE, question) == QMessageBox.Yes)
        if not sure:
            return
        mj.remove_job(self.jobs_store(), edit)
        qx.job_removed(self.quests(), edit.job.name)
        # (2.0.0) A unit of the game's battles put in it stays in the game's job it was based on.
        mb.job_renamed(self.state.battle_units, edit.job.name, None)
        # Its look's textures, which an opened mod carried in its folder, go with it.
        own = getattr(self.state, "mod_own_files", None) or {}
        prefix = f"{mj.FOLDER}/{edit.folder}/".lower()
        for rel in [r for r in own if str(r).replace("\\", "/").lower().startswith(prefix)]:
            own.pop(rel)
        self.job_pick = next(iter(self.jobs_store()), None)
        self._say("")
        self._jobs_changed()

    def new_ability(self) -> None:
        """New ability: its name and the game's action ability it is based on asked; it starts as that ability (its
        record, its action record, the game's description)."""
        abilities = self.abilities_store()
        game, why = self.game_jobs()
        if game is None:
            self._say(NO_GAME_ABILITIES.format(problem=why))
            return
        if len(abilities) >= mj.MOST_ABILITIES:
            self._say(MOST_ABILITIES.format(n=mj.MOST_ABILITIES))
            return
        name = mj.free_name("New Ability", [e.ability.name for e in abilities.values()])
        choices = self._action_choices() or [(n, str(n)) for n in range(mj.ABILITY_FIRST_LIKE,
                                                                        mj.ABILITY_LAST_LIKE + 1)]
        dialog = NewDialog(self, NEW_ABILITY, name, choices, choices[0][0], NEW_ABILITY_NOTE, ABILITY_BASED_TIP,
                           self._ability_name_problem)
        answer = self._ask("new_ability", lambda: dialog.answer() if dialog.exec() == QDialog.Accepted else None)
        if not answer:
            return
        name, like = answer[0], int(answer[1])
        said = self._ability_name_problem(name)
        if said:
            self._say(said)
            return
        try:
            description = self._game_row("ability", like).get("Description") or ""
            ability = mj.copy_of_ability(game, like, name, description if mj.good_description(description) else name)
        except mj.JobsError as exc:
            self._say(NO_GAME_ABILITIES.format(problem=exc))
            return
        folder = mj.free_folder(name, abilities)
        abilities[folder] = mj.AbilityEdit(folder, ability)
        self.ability_pick = folder
        self._say("")
        self.show_abilities(folder)
        self._jobs_changed()

    def remove_ability(self) -> None:
        """Remove: the ability picked, asked first; it leaves every skillset that holds it. Not while it is a
        skillset's only action ability (a skillset has one at the least): said, and nothing taken out."""
        page = _page()
        edit = self._picked_ability()
        if edit is None:
            return
        name = edit.ability.name
        only = mj.only_action_of(self.jobs_store(), name)
        if only:
            self._say(ABILITY_ONLY_ACTION.format(
                name=name, skillsets=page._listed([SKILLSET_OF.format(owner=page.possessive(e.job.name),
                                                                      skillset=e.job.skillset_name) for e in only])))
            return
        held = self._skillsets_holding(name)
        question = ABILITY_REMOVE_ASK.format(name=name)
        if held:
            question += ABILITY_REMOVE_SKILLSETS.format(skillsets=page._listed(held))
        sure = self._ask("remove_ability",
                         lambda: QMessageBox.question(self, page.TITLE, question) == QMessageBox.Yes)
        if not sure:
            return
        mj.remove_ability(self.jobs_store(), self.abilities_store(), edit)
        self.ability_pick = next(iter(self.abilities_store()), None)
        self._say("")
        self._jobs_changed()

    # =========================================================================
    # The job's card
    # =========================================================================

    def _ticked(self, key: str, label: str, said: list, change) -> QWidget:
        """A set in words with Change, which ticks it in a dialog."""
        page = _page()
        words = page.muted(TICKED_LINE.format(label=label, names=page._listed(said) or TICKED_NONE))
        button = QPushButton(CHANGE)
        button.clicked.connect(lambda _c=False: change())
        self.field_widgets[key] = words
        self.field_widgets[f"{key}_change"] = button
        return page.row(words, button)

    def set_job_equipment(self) -> None:
        """The job's equipment as its box's ticks say (his note of 14 November, 19:10); nothing made again."""
        edit = self._picked_job()
        if edit is None or self._building:
            return
        mj.set_equipment(edit.job, [key for key in c.EQUIP_ITEMS
                                    if self.field_widgets.get(f"equip_{key}") is not None
                                    and self.field_widgets[f"equip_{key}"].isChecked()])
        self._job_status()
        self.edits_changed.emit()

    def _ability_listing(self, key: str, entries: list, moved, game=None, most: int = 0, adder=None) -> QListWidget:
        """A skillset's abilities in their order, dragged to move one, each one's JP at its row's right. (His note of
        14 November, 19:10) Every place shown (`most` rows: 16 action abilities, 6 others), the empty ones after the
        abilities, no scroll bar; an empty row clicked adds one (`adder`: it goes after the last, as the game's
        skillset has no gaps); light and dark rows, as the Job Commands page's list."""
        listing = QListWidget()
        listing.setDragDropMode(QListWidget.InternalMove)
        listing.setDefaultDropAction(Qt.MoveAction)
        listing.setItemDelegate(JpDelegate(listing))
        listing.setAlternatingRowColors(True)
        listing.setUniformItemSizes(True)
        listing.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        listing.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._fill_slots(listing, entries, max(most, len(entries)), game)
        rows = max(most, len(entries), 1)
        listing.setFixedHeight(rows * ROW_HEIGHT + 2 * listing.frameWidth() + 2)
        listing.setToolTip(ABILITIES_TIP)
        listing.model().rowsMoved.connect(lambda *_a, box=listing, m=most, g=game: self._slots_moved(box, m, g, moved))
        if adder is not None:
            listing.itemClicked.connect(lambda item: adder() if item.data(Qt.UserRole) is None else None)
        self.field_widgets[key] = listing
        return listing

    def _fill_slots(self, listing: QListWidget, entries: list, most: int, game) -> None:
        """A skillset's list's rows: its abilities, then its empty places (none dragged, none dropped on)."""
        listing.clear()
        for value in entries:
            own = isinstance(value, str)
            entry = QListWidgetItem(OWN_ABILITY.format(ability=value) if own else self.ability_word(value))
            entry.setData(Qt.UserRole, value)
            entry.setData(JP_ROLE, self._jp_words(value, game))
            entry.setSizeHint(QSize(0, ROW_HEIGHT))
            entry.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled)
            if own:
                entry.setForeground(QColor(ABILITY_COLOR))
            listing.addItem(entry)
        for _empty in range(len(entries), most):
            entry = QListWidgetItem("")
            entry.setData(Qt.UserRole, None)
            entry.setSizeHint(QSize(0, ROW_HEIGHT))
            entry.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            listing.addItem(entry)

    def _slots_moved(self, listing: QListWidget, most: int, game, moved) -> None:
        """An ability dragged: the skillset's new order (the empty places left out), and the rows put back in order
        once the drop is over (an ability dropped among the empty places goes after the last)."""
        order = [listing.item(n).data(Qt.UserRole) for n in range(listing.count())
                 if listing.item(n).data(Qt.UserRole) is not None]
        moved(order)

        def tidy(box=listing, values=list(order)):
            try:
                self._fill_slots(box, values, max(most, len(values)), game)
            except RuntimeError:
                pass
        QTimer.singleShot(0, tidy)

    def _jp_words(self, value, game) -> str:
        """An ability's JP to learn in words ("150 JP"), "" where it can't be read."""
        if isinstance(value, str):
            own = mj.ability_named(self.abilities_store(), value)
            return SHEET_JP.format(n=mj.jp_cost(own.ability)) if own is not None else ""
        try:
            return SHEET_JP.format(n=game.jp_cost(value)) if game is not None else ""
        except mj.JobsError:
            return ""

    def _job_card(self):
        """(His notes of 14 November: "removed the Card and just let the user edit everything directly on the main
        window") The Jobs tab has no card: an empty one stands in its place, which the page hides with this tab
        (`side_quests.SideQuestsPage._show_card`); the job's fields are boxes of the middle (`_job_boxes`)."""
        card = _page().CardPane(JOB_BAND, "", JOB_COLOR, "", "")
        card.status([], "")
        return card

    def _sheet_box(self, title: str, *widgets) -> QFrame:
        """One of the middle's boxes: one of a card's groups before (a job's; his note of 14 November, 19:10, an
        item's and an ability's too)."""
        box, column = _panel(title)
        for w in widgets:
            column.addWidget(w)
        # Its fields at its top when the box beside it is the taller.
        column.addStretch(1)
        _narrow(box)
        self.field_widgets[f"section_{title}"] = box
        return box

    def _job_boxes(self, edit: mj.JobEdit) -> dict:
        """The job's fields, in a box for each of the card's groups before (his notes of 14 November): The job (its
        name, the job it is based on, its description, its words on Job Summary), its skillset with its abilities
        and each one's JP (edited where they are listed, his sixth note), its stats, equipment, innate abilities,
        statuses and elements, what unlocks it, and the look it wears (put in Its look)."""
        page = _page()
        job = edit.job
        boxes = {}

        # -- The job ----------------------------------------------------------------------------------------------
        name = QLineEdit(job.name)
        name.setMaxLength(mj.NAME_MOST)
        name.setToolTip(NAME_TIP)
        name.editingFinished.connect(lambda box=name: self.rename_job(box.text().strip()))
        description = QPlainTextEdit(job.description)
        description.setFixedHeight(64)
        description.setToolTip(JOB_DESCRIPTION_TIP)
        description.textChanged.connect(lambda box=description: self.set_job_words("description", box.toPlainText()))
        # (His note of 14 November, 19:10) Twelve lines shown.
        summary = LinesBox(job.summary, SUMMARY_LINES)
        summary.setPlaceholderText(SUMMARY_PLACEHOLDER)
        summary.setToolTip(SUMMARY_TIP)
        summary.textChanged.connect(lambda box=summary: self.set_job_words("summary", box.toPlainText()))
        self.field_widgets.update(job_name=name, job_description=description, job_summary=summary)
        boxes["job"] = self._sheet_box(SHEET_JOB, page.pair((NAME, name)), page.caption(DESCRIPTION), description,
                                     page.caption(SUMMARY), summary)

        # -- Its skillset: its abilities edited where they are listed, each one's JP at its right ------------------
        game, _why = self.game_jobs()
        set_name = QLineEdit(job.skillset_name)
        set_name.setMaxLength(mj.NAME_MOST)
        set_name.setToolTip(NAME_TIP)
        set_name.textChanged.connect(lambda text: self.set_job_words("skillset_name", text))
        set_description = QPlainTextEdit(job.skillset_description)
        set_description.setFixedHeight(48)
        set_description.setToolTip(ABILITY_DESCRIPTION_TIP)
        set_description.textChanged.connect(
            lambda box=set_description: self.set_job_words("skillset_description", box.toPlainText()))
        actions = self._ability_listing("job_actions", job.actions, self.set_actions, game, mj.MOST_ACTIONS,
                                        self.add_action)
        take_action = QPushButton(TAKE_OUT)
        take_action.setEnabled(len(job.actions) > 1)
        take_action.clicked.connect(lambda _c=False, box=actions: self.take_out_action(box.currentRow()))
        others = self._ability_listing("job_others", job.others, self.set_others, game, mj.MOST_OTHERS, self.add_other)
        take_other = QPushButton(TAKE_OUT)
        take_other.setEnabled(bool(job.others))
        take_other.clicked.connect(lambda _c=False, box=others: self.take_out_other(box.currentRow()))
        actions_caption = page.caption(ACTIONS.format(n=len(job.actions)))
        others_caption = page.caption(OTHERS.format(n=len(job.others)))
        hint = page.muted(SKILLSET_HINT)
        self.field_widgets.update(skillset_name=set_name, skillset_description=set_description,
                                  take_out_action=take_action, take_out_other=take_other, actions_caption=actions_caption,
                                  others_caption=others_caption, skillset_hint=hint)
        boxes["skillset"] = self._sheet_box(SHEET_SKILLSET, page.pair((NAME, set_name)), page.caption(DESCRIPTION),
                                          set_description, actions_caption, actions,
                                          page.row(QWidget(), take_action), others_caption, others,
                                          page.row(QWidget(), take_other), hint)

        # -- Stats ------------------------------------------------------------------------------------------------
        def stat(field: str) -> tuple:
            box = page.spin(mj.number(job, field))
            box.valueChanged.connect(lambda value, f=field: self.set_job_number(f, value))
            self.field_widgets[f"job_{field}"] = box
            return c.NUMERIC_FIELDS[field][2], box
        boxes["stats"] = self._sheet_box(STATS, page.pair(stat("Move"), stat("Jump")), page.pair(stat("CharacterEvasion")),
                                       page.pair(stat("HPGrowth"), stat("HPMultiplier")),
                                       page.pair(stat("MPGrowth"), stat("MPMultiplier")),
                                       page.pair(stat("SpeedGrowth"), stat("SpeedMultiplier")),
                                       page.pair(stat("PAGrowth"), stat("PAMultiplier")),
                                       page.pair(stat("MAGrowth"), stat("MAMultiplier")))

        # -- Equipment --------------------------------------------------------------------------------------------
        # (His note of 14 November, 19:10) Its ticks in its box, not in a dialog.
        ticks = QWidget()
        grid = QGridLayout(ticks)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(2)
        worn = set(mj.equipment(job))
        for n, key in enumerate(c.EQUIP_ITEMS):
            tick = QCheckBox(split_words(key))
            tick.setChecked(key in worn)
            tick.toggled.connect(lambda _on, k=key: self.set_job_equipment())
            self.field_widgets[f"equip_{key}"] = tick
            grid.addWidget(tick, n // EQUIPMENT_COLUMNS, n % EQUIPMENT_COLUMNS)
        self.field_widgets["job_equipment"] = ticks
        boxes["equipment"] = self._sheet_box(EQUIPMENT, page.caption(c.FLAG_FIELDS["EquippableItems"][1]), ticks)

        # -- Innate abilities -------------------------------------------------------------------------------------
        def innate(place: int) -> tuple:
            box = page.combo(list(c.INNATE_ABILITY_CHOICES), mj.innate(job)[place])
            if box.itemText(box.currentIndex()) == str(mj.innate(job)[place]):
                box.setItemText(box.currentIndex(), self.ability_word(mj.innate(job)[place]))
            box.currentIndexChanged.connect(lambda _i, b=box, p=place: self.set_job_innate(p, b.currentData()))
            self.field_widgets[f"job_innate_{place}"] = box
            return c.ABILITY_FIELD_LABELS[c.ABILITY_FIELD_NAMES[place]], box
        boxes["innate"] = self._sheet_box(INNATE, page.pair(innate(0), innate(1)), page.pair(innate(2), innate(3)))

        # -- Statuses and elements --------------------------------------------------------------------------------
        sets = []
        for field in mj.STATUS_SETS_AT:
            sets.append(self._ticked(f"job_{field}", c.FLAG_FIELDS[field][1], page._said(mj.statuses(job, field)),
                                     lambda f=field: self.change_job_ticks(f)))
        for field in mj.ELEMENT_SETS_AT:
            sets.append(self._ticked(f"job_{field}", c.FLAG_FIELDS[field][1], mj.elements(job, field),
                                     lambda f=field: self.change_job_ticks(f)))
        boxes["statuses"] = self._sheet_box(STATUSES, *sets)

        # -- What unlocks it, and which of the mod's jobs need it -------------------------------------------------
        rows = []
        free = mj.need_choices(self.jobs_store(), edit)
        for index, need in enumerate(job.needs):
            current = need.own if need.own else need.job
            choices = ([(v, OWN_JOB.format(job=v)) for v in [current] + free if isinstance(v, str)]
                       + [(v, self.job_word(v)) for v in sorted(v for v in [current] + free if not isinstance(v, str))])
            which = page.combo(choices, current)
            which.currentIndexChanged.connect(lambda _i, b=which, n=index: self.set_need_job(n, b.currentData()))
            # (His answer of 16 November) "Mastered" the level box's last choice.
            level = page.combo([(n, LEVEL.format(n=n)) for n in range(mj.LEAST_NEED_LEVEL, mj.MOST_NEED_LEVEL + 1)]
                               + [(mj.MASTERED_WORD, LEVEL_MASTERED)],
                               mj.MASTERED_WORD if need.mastered else need.level)
            level.currentIndexChanged.connect(lambda _i, b=level, n=index: self.set_need_level(n, b.currentData()))
            out = QPushButton(TAKE_OUT)
            out.clicked.connect(lambda _c=False, n=index: self.take_out_need(n))
            self.field_widgets[f"need_job_{index}"] = which
            self.field_widgets[f"need_level_{index}"] = level
            self.field_widgets[f"need_out_{index}"] = out
            rows.append(page.row(which, level, out))
        if not rows:
            rows.append(page.muted(NEEDS_NONE))
        add = QPushButton(ADD_NEED)
        add.setToolTip(NEEDS_TIP)
        add.setEnabled(len(job.needs) < mj.MOST_NEEDS and bool(free))
        add.clicked.connect(lambda _c=False: self.add_need())
        self.field_widgets["add_need"] = add
        needed_by = [page.muted(SHEET_NEEDED_MASTERED.format(job=other.job.name) if need.mastered
                                else SHEET_NEEDED_BY.format(job=other.job.name, n=need.level))
                     for other, need in mj.needed_by(self.jobs_store(), job.name)]
        # (His note of 14 November, 19:10) Add a job at the left.
        left, left_row = _box(QHBoxLayout)
        left_row.addWidget(add)
        left_row.addStretch(1)
        boxes["unlocks"] = self._sheet_box(UNLOCKS, *rows, left, *needed_by)

        # -- Under the figures (his notes of 14 November, 19:10: no Wears the look of, no Job icon, no notes of whose
        # colors it wears): how a color and an image of its own are given, the way to a look of its own.
        look_fields, look_column = _box(spacing=5)
        note = page.muted(LOOK_NOTE)
        self.field_widgets["look_note"] = note
        look_column.addWidget(note)
        _narrow(look_fields)
        boxes["look_fields"] = look_fields
        return boxes

    # -- what the job's card changes ----------------------------------------------------------------------------

    def rename_job(self, name: str) -> None:
        edit = self._picked_job()
        if edit is None or self._building or name == edit.job.name:
            return
        said = self._job_name_problem(name, edit)
        if said:
            self._say(said)
            box = self.field_widgets.get("job_name")
            if box is not None:
                box.setText(edit.job.name)
            return
        old = edit.job.name
        mj.rename_job(self.jobs_store(), edit, name)
        qx.job_renamed(self.quests(), old, name)
        mb.job_renamed(self.state.battle_units, old, name)
        self._say("")
        # An ability's sheet names the skillsets that hold it by their jobs: made again when next shown.
        self._ability_made_for = None
        # (His note of 14 November: renaming made the whole window jitter) The list, the middle's words and its foot
        # follow; nothing is made again.
        self._fill_jobs()
        self._fill_abilities()
        self._refresh_job_words()
        self._job_status()
        self.edits_changed.emit()

    def set_job_words(self, key: str, text: str) -> None:
        """One of the job's words: its description, its words on Job Summary, its skillset's name or description."""
        edit = self._picked_job()
        if edit is None or self._building:
            return
        setattr(edit.job, key, text)
        self._typed()

    def _game_summary(self, like: int) -> str:
        """The words Job Summary shows for the game's job `like`, "" where they can't be read or wouldn't be good
        (a new job starts from them: his word of 14 November, in place of the button "Start from the Squire's")."""
        row = self._game_row("job", like)
        text = self._game_row("ui_job_ability_help", row.get("uijobabilityhelp+Id")).get("Text") or ""
        return text if mj.good_summary(text) else ""

    def set_job_number(self, field: str, value: int) -> None:
        edit = self._picked_job()
        if edit is None or self._building:
            return
        mj.set_number(edit.job, field, int(value))
        self._job_status()
        self.edits_changed.emit()

    def set_job_innate(self, place: int, ability) -> None:
        edit = self._picked_job()
        if edit is None or self._building or ability is None:
            return
        mj.set_innate(edit.job, place, int(ability))
        self._job_status()
        self.edits_changed.emit()

    def change_job_ticks(self, field: str) -> None:
        """One of the job's sets ticked in a dialog: one of its three sets of statuses (a status the game names Unused
        kept as it was) or one of its four sets of elements (its equipment is ticked in its box: his note of 14
        November, 19:10)."""
        page = _page()
        edit = self._picked_job()
        if edit is None:
            return
        job = edit.job
        label = c.FLAG_FIELDS[field][1]
        if field in mj.STATUS_SETS_AT:
            keys = [n for n in c.STATUS_FLAGS if not n.startswith("Unused")]
            now, intro, columns = mj.statuses(job, field), STATUS_INTRO, 5
        else:
            keys, now, intro, columns = list(c.ELEMENT_FLAGS), mj.elements(job, field), ELEMENT_INTRO, 4
        words = {split_words(k): k for k in keys}
        dialog = page.TicksDialog(self, TICKS_TITLE.format(name=job.name, label=label), intro, list(words),
                                  [split_words(n) for n in now], columns)
        answer = self._ask("ticks", lambda: dialog.answer() if dialog.exec() == QDialog.Accepted else None)
        if answer is None:
            return
        ticked = [words.get(a, a) for a in answer]
        if field in mj.STATUS_SETS_AT:
            mj.set_statuses(job, field, set(ticked) | {n for n in now if n.startswith("Unused")})
            said = page._said(mj.statuses(job, field))
        else:
            mj.set_elements(job, field, ticked)
            said = mj.elements(job, field)
        shown = self.field_widgets.get(f"job_{field}")
        if shown is not None:
            shown.setText(TICKED_LINE.format(label=label, names=page._listed(said) or TICKED_NONE))
        self._job_status()
        self.edits_changed.emit()

    def set_actions(self, order: list) -> None:
        """The skillset's action abilities in a new order (one dragged)."""
        edit = self._picked_job()
        if edit is None or self._building or sorted(map(str, order)) != sorted(map(str, edit.job.actions)):
            return
        edit.job.actions = list(order)
        # The list dragged in is the middle's own: nothing to make again (and it isn't made again while it drops).
        self._job_status()
        self.edits_changed.emit()

    def set_others(self, order: list) -> None:
        edit = self._picked_job()
        if edit is None or self._building or sorted(order) != sorted(edit.job.others):
            return
        edit.job.others = list(order)
        self._job_status()
        self.edits_changed.emit()

    def action_choices(self, edit: mj.JobEdit) -> list:
        """What a skillset may still be given as an action ability: the mod's own abilities first, then the game's
        action abilities (1 to 421) by name, less those it holds."""
        held = set(edit.job.actions)
        names = self._game_names("ability")
        return ([(e.ability.name, OWN_ABILITY.format(ability=e.ability.name))
                 for e in self.abilities_store().values() if e.ability.name not in held]
                + [(n, ABILITY_NUMBERED.format(name=names[n], n=n)) for n in sorted(names)
                   if 1 <= n < mj.FIRST_OTHER and n not in held])

    def other_choices(self, edit: mj.JobEdit) -> list:
        """The game's reaction, support and movement abilities (422 to 511) a skillset doesn't hold yet."""
        names = self._game_names("ability")
        return [(n, ABILITY_NUMBERED.format(name=names[n], n=n)) for n in sorted(names)
                if mj.FIRST_OTHER <= n <= mj.LAST_ABILITY and n not in edit.job.others]

    def add_action(self) -> None:
        """Add an ability: one picked for the skillset's action abilities, put last."""
        edit = self._picked_job()
        if edit is None or len(edit.job.actions) >= mj.MOST_ACTIONS:
            return
        dialog = PickDialog(self, ADD_ABILITY, ABILITY_SEARCH, self.action_choices(edit))
        answer = self._ask("add_action", lambda: dialog.answer() if dialog.exec() == QDialog.Accepted else None)
        if answer is None or answer in edit.job.actions:
            return
        edit.job.actions.append(answer)
        self._jobs_changed()

    def take_out_action(self, place: int) -> None:
        edit = self._picked_job()
        if edit is None or not 0 <= place < len(edit.job.actions) or len(edit.job.actions) <= 1:
            return
        del edit.job.actions[place]
        self._jobs_changed()

    def add_other(self) -> None:
        edit = self._picked_job()
        if edit is None or len(edit.job.others) >= mj.MOST_OTHERS:
            return
        dialog = PickDialog(self, ADD_ABILITY, ABILITY_SEARCH, self.other_choices(edit))
        answer = self._ask("add_other", lambda: dialog.answer() if dialog.exec() == QDialog.Accepted else None)
        if answer is None or answer in edit.job.others:
            return
        edit.job.others.append(int(answer))
        self._jobs_changed(refill=False)

    def take_out_other(self, place: int) -> None:
        edit = self._picked_job()
        if edit is None or not 0 <= place < len(edit.job.others):
            return
        del edit.job.others[place]
        self._jobs_changed(refill=False)

    def add_need(self) -> None:
        """Add a job: one more the job needs, the job it is based on first when it doesn't need it yet, at level 2
        (as the game's Knight needs the Squire); changed on its row."""
        edit = self._picked_job()
        if edit is None or len(edit.job.needs) >= mj.MOST_NEEDS:
            return
        free = mj.need_choices(self.jobs_store(), edit)
        if not free:
            return
        value = edit.job.like if edit.job.like in free else free[0]
        edit.job.needs.append(mj.Need(0, value, 2) if isinstance(value, str) else mj.Need(value, "", 2))
        self._jobs_changed()

    def set_need_job(self, index: int, value) -> None:
        edit = self._picked_job()
        if edit is None or self._building or value is None or not 0 <= index < len(edit.job.needs):
            return
        need = edit.job.needs[index]
        need.job, need.own = (0, value) if isinstance(value, str) else (int(value), "")
        self._jobs_changed()

    def set_need_level(self, index: int, level) -> None:
        """A need's level, or (his answer of 16 November) the job needed mastered: written "Level": "Mastered"."""
        edit = self._picked_job()
        if edit is None or self._building or level is None or not 0 <= index < len(edit.job.needs):
            return
        need = edit.job.needs[index]
        need.mastered = level == mj.MASTERED_WORD
        need.level = mj.MOST_NEED_LEVEL if need.mastered else int(level)
        self._jobs_changed(card=False)

    def take_out_need(self, index: int) -> None:
        edit = self._picked_job()
        if edit is None or not 0 <= index < len(edit.job.needs):
            return
        del edit.job.needs[index]
        self._jobs_changed()

    # =========================================================================
    # The ability's card
    # =========================================================================

    def _inflict_choices(self) -> list:
        """The Inflict Status rows as the Items page names them."""
        from .table_editor import inflict_status_descriptor
        records = (getattr(self.state, "item_table_records", None) or {}).get("item_options", [])
        edits = (getattr(self.state, "item_table_edits", None) or {}).get("item_options", {})
        choices = [(r.item_id, f"{inflict_status_descriptor({**r.values, **edits.get(r.item_id, {})})} ({r.item_id})")
                   for r in records if 0 <= r.item_id <= 255]
        return choices or [(n, str(n)) for n in range(256)]

    def _ability_card(self):
        """(His note of 14 November, 19:10: "can the Item's and the Abilities tab get touched up to remove the card so
        users can make edits on the main window instead as we have done for the Jobs tab") The Abilities tab has no
        card: an empty one stands in its place, which the page hides with this tab; the ability's fields are boxes of
        the middle, beside the map that plays it (`_ability_sheet`)."""
        card = _page().CardPane(ABILITY_BAND, "", ABILITY_COLOR, "", "")
        card.status([], "")
        return card

    def _ability_boxes(self, edit: mj.AbilityEdit) -> dict:
        """The ability's fields, a box for each group of its card before (his note of 14 November, 19:10): The ability
        (its name, its description, the game's ability it is based on, its JP and MP costs), what it does, how it is
        aimed, its flags, what the units the game moves know of it, and the skillsets it is in."""
        page = _page()
        ability = edit.ability
        boxes = {}

        # -- The ability ------------------------------------------------------------------------------------------
        name = QLineEdit(ability.name)
        name.setMaxLength(mj.NAME_MOST)
        name.setToolTip(NAME_TIP)
        name.editingFinished.connect(lambda box=name: self.rename_ability(box.text().strip()))
        description = QPlainTextEdit(ability.description)
        description.setFixedHeight(64)
        description.setToolTip(ABILITY_DESCRIPTION_TIP)
        description.textChanged.connect(lambda box=description: self.set_ability_description(box.toPlainText()))
        based = page.combo(self._action_choices(), ability.like)
        based.setToolTip(ABILITY_BASED_TIP)
        based.currentIndexChanged.connect(lambda _i, box=based: self.set_ability_like(box.currentData()))
        jp = page.spin(mj.jp_cost(ability), 0, 9999)
        jp.valueChanged.connect(lambda value: self.set_ability_cost(value))

        def scalar(field: str):
            box = page.spin(mj.action_number(ability, field))
            box.valueChanged.connect(lambda value, f=field: self.set_ability_number(f, value))
            self.field_widgets[f"ability_{field}"] = box
            return c.OVERRIDE_SCALAR_FIELDS[field][2], box
        self.field_widgets.update(ability_name=name, ability_description=description, ability_based=based,
                                  ability_jp=jp)
        boxes["ability"] = self._sheet_box(SHEET_ABILITY, page.pair((NAME, name)), page.caption(DESCRIPTION),
                                           description, page.caption(BASED_ON), based,
                                           page.pair((JP_COST, jp), (MP_COST, scalar("MPCost")[1])))

        # -- What it does -----------------------------------------------------------------------------------------
        formulas = reference_names.formula_names()
        formula = page.combo([(n, f"{formulas[n]} ({n})") for n in sorted(formulas) if 0 <= n <= 255],
                             mj.action_number(ability, "Formula"))
        formula.currentIndexChanged.connect(lambda _i, b=formula: self.set_ability_number("Formula", b.currentData()))
        inflict = page.combo(self._inflict_choices(), mj.action_number(ability, "InflictStatus"))
        inflict.currentIndexChanged.connect(
            lambda _i, b=inflict: self.set_ability_number("InflictStatus", b.currentData()))
        elements, grid = _box(QGridLayout, spacing=3)
        grid.setHorizontalSpacing(10)
        ticks = []
        ticked = mj.action_elements(ability)
        for n, element in enumerate(c.ELEMENT_FLAGS):
            tick = QCheckBox(element)
            tick.setChecked(element in ticked)
            tick.toggled.connect(lambda _on: self.set_ability_elements([b.text() for b in ticks if b.isChecked()]))
            grid.addWidget(tick, n // 4, n % 4)
            ticks.append(tick)
        self.field_widgets.update(ability_formula=formula, ability_inflict=inflict, ability_elements=ticks)
        boxes["does"] = self._sheet_box(DOES, page.caption(FORMULA), formula, page.pair(scalar("X"), scalar("Y")),
                                        page.caption(INFLICT), inflict, page.caption(ELEMENTS), elements)

        # -- How it is aimed --------------------------------------------------------------------------------------
        boxes["aimed"] = self._sheet_box(AIMED, page.pair(scalar("Range"), scalar("EffectArea")),
                                         page.pair(scalar("Vertical"), scalar("CT")))

        # -- Flags ------------------------------------------------------------------------------------------------
        flags, flag_grid = _box(QGridLayout, spacing=3)
        flag_grid.setHorizontalSpacing(10)
        states = mj.action_flags(ability)
        shown = [d for d in c.ABILITY_FLAG_DEFS if not d[4]]
        for n, (flag_id, label, _group, _inverted, _blank) in enumerate(shown):
            tick = QCheckBox(label)
            tick.setChecked(bool(states.get(flag_id)))
            tick.toggled.connect(lambda on, f=flag_id: self.set_ability_flag(f, on))
            self.field_widgets[f"ability_flag_{flag_id}"] = tick
            flag_grid.addWidget(tick, n // 2, n % 2)
        boxes["flags"] = self._sheet_box(FLAGS, flags)

        # -- For units the game moves -----------------------------------------------------------------------------
        chance = page.spin(mj.chance(ability))
        chance.valueChanged.connect(lambda value: self.set_ability_chance(value))
        self.field_widgets["ability_chance"] = chance
        boxes["moved"] = self._sheet_box(MOVED, page.pair((CHANCE, chance)),
                                         self._ticked("ability_ai", AI_FLAGS,
                                                      [split_words(n) for n in mj.ai_flags(ability)],
                                                      self.change_ability_ai))

        # -- The skillsets it is in -------------------------------------------------------------------------------
        held = self._skillsets_holding(ability.name)
        used = page.muted(page._listed(held) + "." if held else USED_BY_NONE)
        self.field_widgets["ability_used_by"] = used
        boxes["used_by"] = self._sheet_box(USED_BY, used)
        return boxes

    def _ability_sheet(self, edit: mj.AbilityEdit) -> QWidget:
        """The middle for an ability (his note of 14 November, 19:10: no card for the Abilities tab): the ability played
        out on the Abilities page's own map, and everything of it edited there, in boxes, as the Jobs tab's: The
        ability beside the map; under them what it does beside how it is aimed (what the map shows of it), its flags
        beside what the units the game moves know of it, and the skillsets it is in. What Mod Studio Framework would
        say of it under the title."""
        ability = edit.ability
        holder, column = _box(spacing=8)
        title = QLabel(ABILITY_SHEET_TITLE.format(ability=ability.name))
        title.setStyleSheet("font-weight: 600; font-size: 12pt;")
        column.addWidget(title)
        foot = QLabel("")
        foot.setWordWrap(True)
        column.addWidget(foot)
        self.ability_foot = JobFoot(foot)
        scroll = SheetScroll()
        inside, sheet = _box(spacing=10)
        scroll.setWidget(inside)
        column.addWidget(scroll, 1)
        boxes = self._ability_boxes(edit)
        # The map, made once and kept from one sheet to the next (its camera, its sound, whom it is shown by).
        played, played_column = _panel(ABILITY_ON_MAP)
        self.field_widgets[f"section_{ABILITY_ON_MAP}"] = played
        if self._ability_map is None:
            self._ability_map = NewAbilityMap(self.state)
        self._ability_map.setMinimumHeight(ABILITY_MAP_LEAST)
        played_column.addWidget(self._ability_map, 1)
        self._ability_map.setVisible(True)
        top = Turning(10)
        top.add(boxes["ability"], 2)
        top.add(played, 3)
        sheet.addWidget(top)
        scroll.turnings.append((top, 0))
        for first, second in (("does", "aimed"), ("flags", "moved")):
            two = Turning(10)
            two.add(boxes[first], 1)
            two.add(boxes[second], 1)
            sheet.addWidget(two)
            scroll.turnings.append((two, 0))
        sheet.addWidget(boxes["used_by"])
        sheet.addStretch(1)
        self.ability_sheet_widgets = {"title": title, "foot": foot}
        self.ability_foot.status(mj.ability_problems(self.abilities_store(), edit))
        scroll.fit()
        return holder

    def _refresh_ability_words(self) -> None:
        """The middle's words of the ability again where they show (its title), nothing made again."""
        edit = self._picked_ability()
        label = self.ability_sheet_widgets.get("title")
        if edit is not None and label is not None:
            label.setText(ABILITY_SHEET_TITLE.format(ability=edit.ability.name))

    def _jobs_sheet_stale(self) -> None:
        """The ability shown changed where the Jobs tab's sheet shows it (its name, its JP): that sheet is made again
        when next shown; the ability's own kept as it is."""
        self._jobs_version += 1
        if self._ability_made_for is not None:
            self._ability_made_for = self._ability_made_for[:2] + (self._jobs_version,)

    # -- what the ability's card changes ------------------------------------------------------------------------

    def rename_ability(self, name: str) -> None:
        edit = self._picked_ability()
        if edit is None or self._building or name == edit.ability.name:
            return
        said = self._ability_name_problem(name, edit)
        if said:
            self._say(said)
            box = self.field_widgets.get("ability_name")
            if box is not None:
                box.setText(edit.ability.name)
            return
        mj.rename_ability(self.jobs_store(), edit, name)
        self._say("")
        # (His notes of 14 November: no jitter as a field changes) The lists, the middle's words and its map follow;
        # nothing of it is made again.
        self._jobs_sheet_stale()
        self._fill_jobs()
        self._fill_abilities()
        self._refresh_ability_words()
        self._job_status()
        self._play_ability()
        self.edits_changed.emit()

    def set_ability_description(self, text: str) -> None:
        edit = self._picked_ability()
        if edit is None or self._building:
            return
        edit.ability.description = text
        self._job_status()
        self.edits_changed.emit()

    def set_ability_like(self, like) -> None:
        """Based on: the game's ability whose effect, movement and sound the ability has (its numbers stay its own);
        the map plays it so, nothing made again."""
        edit = self._picked_ability()
        if edit is None or self._building or like is None or int(like) == edit.ability.like:
            return
        edit.ability.like = int(like)
        self._job_status()
        self._play_ability()
        self.edits_changed.emit()

    def set_ability_cost(self, value: int) -> None:
        edit = self._picked_ability()
        if edit is None or self._building:
            return
        mj.set_jp_cost(edit.ability, int(value))
        # The Jobs tab's sheet shows its JP in each skillset that holds it.
        self._jobs_sheet_stale()
        self._job_status()
        self.edits_changed.emit()

    def set_ability_number(self, field: str, value) -> None:
        """One of the action record's numbers; the map plays it again once the typing stops."""
        edit = self._picked_ability()
        if edit is None or self._building or value is None:
            return
        mj.set_action_number(edit.ability, field, int(value))
        self._typed()

    def set_ability_elements(self, ticked: list) -> None:
        edit = self._picked_ability()
        if edit is None or self._building:
            return
        mj.set_action_elements(edit.ability, ticked)
        self._job_status()
        self.edits_changed.emit()

    def set_ability_flag(self, flag: str, ticked: bool) -> None:
        edit = self._picked_ability()
        if edit is None or self._building:
            return
        mj.set_action_flag(edit.ability, flag, bool(ticked))
        self._typed()

    def set_ability_chance(self, value: int) -> None:
        edit = self._picked_ability()
        if edit is None or self._building:
            return
        mj.set_chance(edit.ability, int(value))
        self._job_status()
        self.edits_changed.emit()

    def change_ability_ai(self) -> None:
        """The flags the units the game moves read of the ability, ticked in a dialog."""
        page = _page()
        edit = self._picked_ability()
        if edit is None:
            return
        words = {split_words(k): k for k in c.ABILITY_AI_BEHAVIOR_FLAGS}
        dialog = page.TicksDialog(self, TICKS_TITLE.format(name=edit.ability.name, label=AI_FLAGS), FLAGS_INTRO,
                                  list(words), [split_words(n) for n in mj.ai_flags(edit.ability)], 3)
        answer = self._ask("ticks", lambda: dialog.answer() if dialog.exec() == QDialog.Accepted else None)
        if answer is None:
            return
        mj.set_ai_flags(edit.ability, [words.get(a, a) for a in answer])
        shown = self.field_widgets.get("ability_ai")
        if shown is not None:
            said = [split_words(n) for n in mj.ai_flags(edit.ability)]
            shown.setText(TICKED_LINE.format(label=AI_FLAGS, names=page._listed(said) or TICKED_NONE))
        self._job_status()
        self.edits_changed.emit()

    # =========================================================================
    # The middle
    # =========================================================================

    def _sprites_for_jobs(self) -> Optional[us.UnitSprites]:
        """What the unpacked game draws its units with, read once a game; None without it."""
        game = self.game_dir()
        key = str(game) if game is not None else None
        if key != self._job_sprites_key:
            self._job_sprites = us.UnitSprites(game) if game is not None else None
            self._job_sprites_key = key
        return self._job_sprites

    # -- the look (the build's second part) -------------------------------------------------------------------

    def _game_palettes(self, edit: mj.JobEdit, woman: int) -> list:
        """The five palettes of the game's look a man or a woman of the job wears (16 bit values; None each where the
        unpacked game's can't be read)."""
        sprites = self._sprites_for_jobs()
        if sprites is None:
            return [None] * mj.MOST_PALETTES
        return jl.look_palettes(sprites, jl.look_like(edit.job), woman)

    def _figure_image(self, edit: mj.JobEdit, woman: int, palette: int) -> Optional[QImage]:
        """A man or a woman of the job standing, as a battle draws it waiting: the frames of the job it is based on,
        its look's sheet or its own textures, in its palette `palette` (its own colors or its look's); None where it
        can't be drawn here."""
        sprites = self._sprites_for_jobs()
        if sprites is None:
            return None
        who = jl.WHO[woman]
        colors = jl.palettes(edit.job, who, self._game_palettes(edit, woman))[palette]
        sheet = jl.sheet_of(edit.art.textures[who]) if who in edit.art.textures else None
        try:
            picture = jl.standing(sprites, jl.frames_job(edit.job, edit.art, who), jl.look_like(edit.job), woman,
                                  colors, sheet)
        except Exception:                                             # noqa: BLE001
            picture = None
        if picture is None:
            return None
        return QImage(bytes(picture.rgba), picture.width, picture.height, picture.width * 4,
                      QImage.Format_RGBA8888).copy()

    def _figure_label(self, image: Optional[QImage], scale: int, clicked=None) -> QLabel:
        """A figure drawn: `scale` times its size (the big one), or fitted into a small figure's room (`scale` 1);
        `clicked` called on a left click where given (a palette's small figure)."""
        label = Swatch(clicked) if clicked is not None else QLabel()
        label.setAlignment(Qt.AlignCenter)
        self._draw_figure(label, image, scale)
        return label

    def _draw_figure(self, label: QLabel, image: Optional[QImage], scale: int) -> None:
        if image is None:
            label.setPixmap(QPixmap())
            label.setText(_page().NO_TEXTURE)
            label.setFixedSize(40 * scale, 46 * scale)
            return
        if scale != 1:
            shown = image.scaled(image.width() * scale, image.height() * scale, Qt.KeepAspectRatio,
                                 Qt.FastTransformation)
        else:
            shown = image.scaled(40, 46, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        label.setText("")
        label.setPixmap(QPixmap.fromImage(shown))
        label.setFixedSize(max(40 * scale, shown.width()), max(46 * scale, shown.height()))

    def _menu_on(self, widget: QWidget, make_menu) -> None:
        """A right click anywhere on `widget` (its pictures and words too) brings up the menu `make_menu` makes."""
        for source in [widget] + widget.findChildren(QLabel):
            source.setContextMenuPolicy(Qt.CustomContextMenu)
            source.customContextMenuRequested.connect(
                lambda point, s=source: make_menu().exec(s.mapToGlobal(point)))

    def _swatch(self, who: str, palette: int, index: int, colour: str) -> QLabel:
        """One color of a palette: clicked, it is changed (the first, see through, isn't)."""
        colours = theme.current()
        dot = Swatch(None if index == 0 else (lambda: self.pick_color(who, palette, index)))
        dot.setFixedSize(11, 16)
        if index == 0:
            dot.setToolTip(SEE_THROUGH_TIP)
            dot.setStyleSheet(f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #ffffff, stop:0.49 #ffffff, "
                              f"stop:0.5 #b0b0b0, stop:1 #b0b0b0); border: 1px solid {colours['border']};")
        else:
            dot.setToolTip(COLOR_TIP.format(k=index))
            dot.setStyleSheet(f"background: {colour}; border: 1px solid {colours['border']};")
        self.look_swatches[(who, palette, index)] = dot
        return dot

    def _art_panel(self, key: tuple, title: str, image: Optional[QImage], size: tuple, empty: str = "") -> QFrame:
        """A picture of the job's look in a frame, its name over it, fitted to `size`; its menu on a right click
        anywhere in it (`_art_menu`)."""
        page = _page()
        box = QFrame()
        box.setFrameShape(QFrame.StyledPanel)
        inner = QVBoxLayout(box)
        inner.setContentsMargins(6, 4, 6, 4)
        inner.setSpacing(2)
        inner.addWidget(page.caption(title))
        view = QLabel()
        view.setAlignment(Qt.AlignCenter)
        view.setFixedSize(*size)
        self._draw_art(view, image, empty)
        inner.addWidget(view, 0, Qt.AlignHCenter)
        self._menu_on(box, lambda: self._art_menu(*key))
        self.look_parts[key] = (box, view)
        return box

    def _draw_art(self, view: QLabel, image: Optional[QImage], empty: str = "") -> None:
        """A picture of the job's look fitted into its view (fixed in size), or what it says where there is none."""
        if image is not None and not image.isNull():
            view.setText("")
            view.setPixmap(QPixmap.fromImage(image.scaled(view.width(), view.height(), Qt.KeepAspectRatio,
                                                          Qt.SmoothTransformation)))
        else:
            view.setPixmap(QPixmap())
            view.setText(empty or _page().NO_TEXTURE)
            view.setWordWrap(True)

    def _game_number(self, key: str, number: int, field: str, fallback: int) -> int:
        """A number one of the game's rows holds (as the mod has it), or `fallback`."""
        try:
            return int(str(self._game_row(key, number).get(field)).strip())
        except (TypeError, ValueError):
            return fallback

    def _game_art(self, relative: str) -> Optional[QImage]:
        image, _why = self._game_texture(relative)
        return image

    def _game_face(self, job, who: str, palette: int) -> Optional[QImage]:
        """The game's face of the look a male or a female of the job wears, for palette `palette`'s team (the game's
        faces are numbered by team, 08 the player's units', 09 to 12 a battle's), its first team's where the game
        has none for that team."""
        path = jl.game_face_path(jl.look_like(job), jl.WHO.index(who))
        first = f"_{jl.FIRST_TEAM:02d}_uitx.tex"
        if palette and path.endswith(first):
            image = self._game_art(f"{path[:-len(first)]}_{jl.FIRST_TEAM + palette:02d}_uitx.tex")
            if image is not None:
                return image
        return self._game_art(path)

    def _own_image(self, data: bytes) -> Optional[QImage]:
        image = QImage.fromData(data) if data else QImage()
        return None if image.isNull() else image

    def _art_image(self, edit: mj.JobEdit, part: str, who: str = "", palette: int = 0) -> Optional[QImage]:
        """What the job shows of its art: its own, else the game's (a portrait its look's face, an icon the game's
        picked); its job screen art its own or none. A portrait is the one for palette `palette`'s team (his note of
        14 November: the portrait follows the palette shown): a job's own by their order, the first where it has
        fewer (as the game takes a team past the list's end), the game's face of that team, else its first team's."""
        art, job = edit.art, edit.job
        if part == "portrait":
            own = art.portraits.get(who) or []
            if own:
                sheet, parts = own[palette] if 0 <= palette < len(own) else own[0]
                image = self._own_image(sheet)
                rect = dict((n, tuple(r)) for n, r in parts).get("All", jl.FACE_PARTS[-1][1])
            else:
                image = self._game_face(job, who, palette)
                rect = jl.FACE_PARTS[-1][1]
            if image is not None and (image.width(), image.height()) == jl.FACE_SIZE:
                image = image.copy(rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1])
            return image
        if part == "picture":
            return self._own_image(art.pictures.get(who, b""))
        if part == "icon":
            if art.icon:
                return self._own_image(art.icon)
            shown = job.icon if isinstance(job.icon, int) else job.like
            return self._game_art(jl.game_icon_path(self._game_number("job", shown, "TexturePartsIndex", shown - 73)))
        if art.command:
            return self._own_image(art.command)
        shown = job.skillset_icon if isinstance(job.skillset_icon, int) else job.skillset_like
        return self._game_art(jl.game_command_path(self._game_number("job_command", shown, "IconId", shown - 4)))

    def _look_block(self, edit: mj.JobEdit, woman: int) -> QWidget:
        """A male or a female of the job: its figure, its five palettes (each a small figure and its 16 colors), its
        portrait and its job screen art. (His note of 14 November: "cycle through the palettes") The palette shown
        is cycled by Previous and Next under the figure, or chosen by clicking a palette's small figure: the figure
        is drawn in it and the portrait is its team's (`show_palette`)."""
        page = _page()
        who = jl.WHO[woman]
        one, one_column = _box(spacing=6)
        one_column.addWidget(page.caption((MAN, WOMAN)[woman]))
        line, line_row = _box(QHBoxLayout, spacing=10)
        shown = jl.shown_colors(edit.job, who, self._game_palettes(edit, woman))
        palette = self._palette_shown(who, shown)
        big = self._figure_label(self._figure_image(edit, woman, palette), 3)
        figure, figure_column = _box(spacing=4)
        figure_column.addWidget(big)
        self._menu_on(figure, lambda: self._art_menu("figure", who))
        self.look_parts[("figure", who)] = (figure, big)
        named = page.caption(SHEET_PALETTE.format(n=palette))
        named.setAlignment(Qt.AlignCenter)
        figure_column.addWidget(named)
        frames = page.caption(self._frames_words(edit, who))
        frames.setAlignment(Qt.AlignCenter)
        figure_column.addWidget(frames)
        self.field_widgets[f"frames_{who.lower()}"] = frames
        back, ahead = QPushButton(PALETTE_PREVIOUS), QPushButton(PALETTE_NEXT)
        several = sum(1 for colors in shown if colors is not None) > 1
        for button, step in ((back, -1), (ahead, 1)):
            button.setEnabled(several)
            button.clicked.connect(lambda _c=False, w=who, s=step: self.step_palette(w, s))
        figure_column.addWidget(page.row(back, ahead, stretch_first=False))
        self.look_parts[("palette", who)] = (figure, named)
        self.field_widgets[f"palette_back_{who.lower()}"] = back
        self.field_widgets[f"palette_next_{who.lower()}"] = ahead
        line_row.addWidget(figure, 0, Qt.AlignTop)
        palettes, rows_column = _box(spacing=3)
        for n in range(mj.MOST_PALETTES):
            if shown[n] is None:
                continue
            cell, cell_row = _box(QHBoxLayout, spacing=6)
            small = self._figure_label(self._figure_image(edit, woman, n), 1,
                                       lambda w=who, p=n: self.show_palette(w, p))
            small.setToolTip(PALETTE_SHOWN_TIP)
            self.look_parts[("small", who, n)] = (cell, small)
            cell_row.addWidget(small)
            swatches, swatch_row = _box(QHBoxLayout, spacing=1)
            for k, colour in enumerate(shown[n]):
                swatch_row.addWidget(self._swatch(who, n, k, colour))
            words_box, words_column = _box(spacing=1)
            words_column.addWidget(page.caption(SHEET_PALETTE.format(n=n)))
            words_column.addWidget(swatches)
            cell_row.addWidget(words_box)
            cell_row.addStretch(1)
            self._menu_on(cell, lambda w=who, p=n: self._palette_menu(w, p))
            rows_column.addWidget(cell)
        self._mark_palette(who, palette)
        line_row.addWidget(palettes, 1)
        one_column.addWidget(line)
        art, art_row = _box(QHBoxLayout, spacing=8)
        art_row.addWidget(self._art_panel(("portrait", who), SHEET_PORTRAIT,
                                          self._art_image(edit, "portrait", who, palette), (64, 96)))
        art_row.addWidget(self._art_panel(("picture", who), SHEET_ART, self._art_image(edit, "picture", who),
                                          (64, 104), NO_ART))
        art_row.addStretch(1)
        one_column.addWidget(art)
        return one

    @staticmethod
    def _frames_words(edit: mj.JobEdit, who: str) -> str:
        """The line under a figure: the frames it is drawn in, and how many times the game's size its own picture is
        where it was given bigger."""
        n = jl.frames_shown(edit.job, edit.art, who)
        more = FRAMES_SHOWN_OWN if jl.has_own(edit.art, who) else ""
        if who in edit.art.big and who in edit.art.textures:
            return FRAMES_SHOWN_BIG.format(n=n, s=edit.art.big[who][0]) + more
        return FRAMES_SHOWN.format(n=n) + more

    def _palette_shown(self, who: str, shown: list) -> int:
        """The palette a male or a female is shown in: the one chosen while it has colors, else its first."""
        n = self.shown_palettes.get(who, 0)
        if 0 <= n < len(shown) and shown[n] is not None:
            return n
        return next((k for k, colors in enumerate(shown) if colors is not None), 0)

    def _mark_palette(self, who: str, palette: int) -> None:
        """The palette shown marked: its small figure framed."""
        colours = theme.current()
        for key, (_cell, small) in self.look_parts.items():
            if key[0] == "small" and key[1] == who:
                small.setStyleSheet(f"border: 2px solid {colours['accent']}; border-radius: 3px;" if key[2] == palette
                                    else "border: 2px solid transparent;")

    def show_palette(self, who: str, palette: int) -> None:
        """(His note of 14 November) A male or a female of the job shown in palette `palette`: its figure drawn in
        it, its portrait that palette's team's (palette 0 the player's units', 1 to 4 a battle's teams': a job's own
        portraits by their order, the first where it has fewer; the game's faces by their team's number, the first
        team's where the game has none for it). Nothing else is made again."""
        edit = self._picked_job()
        if edit is None:
            return
        woman = jl.WHO.index(who)
        shown = jl.shown_colors(edit.job, who, self._game_palettes(edit, woman))
        if not 0 <= palette < len(shown) or shown[palette] is None:
            return
        self.shown_palettes[who] = palette
        figure = self.look_parts.get(("figure", who))
        if figure is not None:
            self._draw_figure(figure[1], self._figure_image(edit, woman, palette), 3)
        named = self.look_parts.get(("palette", who))
        if named is not None:
            named[1].setText(SHEET_PALETTE.format(n=palette))
        portrait = self.look_parts.get(("portrait", who))
        if portrait is not None:
            self._draw_art(portrait[1], self._art_image(edit, "portrait", who, palette))
        self._mark_palette(who, palette)

    def step_palette(self, who: str, step: int) -> None:
        """Previous (-1) or Next (1): the palette before or after the one shown, round from the last to the first."""
        edit = self._picked_job()
        if edit is None:
            return
        shown = jl.shown_colors(edit.job, who, self._game_palettes(edit, jl.WHO.index(who)))
        there = [n for n, colors in enumerate(shown) if colors is not None]
        if not there:
            return
        now = self._palette_shown(who, shown)
        at = there.index(now) if now in there else 0
        self.show_palette(who, there[(at + step) % len(there)])

    def _look_figures(self, edit: mj.JobEdit) -> QWidget:
        """A man and a woman of the job, side by side while they fit (`_look_block`)."""
        sexes = Turning(22)
        for woman in (0, 1):
            sexes.add(self._look_block(edit, woman))
        return sexes

    # -- the look's menus and what they do -------------------------------------------------------------------

    def _art_menu(self, part: str, who: str = "") -> QMenu:
        """A picture of the job's look's menu, as the item card's textures': Replace..., then Use its look's (a figure,
        a portrait), No art (job screen art) or Use the game's icon (an icon), then Export as PNG..."""
        edit = self._picked_job()
        art = edit.art if edit is not None else mj.JobArt()
        menu = QMenu(self)
        replace = menu.addAction(REPLACE_ART)
        replace.setEnabled(edit is not None and (part != "figure" or self._figure_colors(edit, who) is not None))
        replace.triggered.connect(lambda _c=False: self.replace_art(part, who))
        own = {"figure": who in art.textures, "portrait": bool(art.portraits.get(who)),
               "picture": bool(art.pictures.get(who)), "icon": bool(art.icon), "command": bool(art.command)}[part]
        back = menu.addAction({"figure": USE_LOOKS, "portrait": USE_LOOKS, "picture": NO_ART}.get(part, USE_GAME_ICON))
        back.setEnabled(edit is not None and own)
        back.triggered.connect(lambda _c=False: self.use_look_art(part, who))
        if part == "figure":
            # (His 8th note of 14 November) The frames its own textures are drawn for, and Smooth the edges where they
            # were made from a classic sprite this session.
            menu.addSeparator()
            shown = jl.frames_shown(edit.job, art, who) if edit is not None else cs.TYPE1
            for kind, words in zip((cs.TYPE1, cs.TYPE2), FRAMES_PICK):
                pick = menu.addAction(words)
                pick.setCheckable(True)
                pick.setChecked(shown == kind)
                pick.setEnabled(edit is not None and who in art.textures)
                pick.triggered.connect(lambda _c=False, k=kind: self.set_frames(who, k))
            if who in art.classic:
                smooth = menu.addAction(SMOOTH_EDGES)
                smooth.setCheckable(True)
                smooth.setChecked(bool(art.classic[who][1]))
                smooth.triggered.connect(lambda on=False: self.set_smooth(who, bool(on)))
        menu.addSeparator()
        export = menu.addAction(EXPORT_ART)
        export.setEnabled(edit is not None and self._export_data(edit, part, who) is not None)
        export.triggered.connect(lambda _c=False: self.export_art(part, who))
        return menu

    def _palette_menu(self, who: str, palette: int) -> QMenu:
        """A palette's menu: Use its look's (its look's colors again, where it has its own)."""
        edit = self._picked_job()
        menu = QMenu(self)
        back = menu.addAction(USE_LOOKS)
        game = self._game_palettes(edit, jl.WHO.index(who)) if edit is not None else []
        back.setEnabled(edit is not None and jl.palette_is_own(edit.job, who, palette, game))
        back.triggered.connect(lambda _c=False: self.use_look_palette(who, palette))
        return menu

    def _figure_colors(self, edit: mj.JobEdit, who: str) -> Optional[list]:
        """The palette a figure's texture is exported in and read back by (its first: the player's units')."""
        return jl.palettes(edit.job, who, self._game_palettes(edit, jl.WHO.index(who)))[0]

    def _export_data(self, edit: mj.JobEdit, part: str, who: str = ""):
        """What Export as PNG... writes of a picture of the job's look: a PNG's bytes, a QImage, or None for nothing."""
        art = edit.art
        if part == "figure":
            colors = self._figure_colors(edit, who)
            sprites = self._sprites_for_jobs()
            if who in art.textures and jl.has_own(art, who) and colors is not None:
                # (The thirtieth session) A figure of more colors is exported in its own colors at its size, which
                # Replace... reads back the same.
                return jl.own_png(art, who)
            if who in art.textures:
                # (17 November 2026) A figure given bigger is exported at its bigger size, which Replace... reads back.
                sheet = jl.big_sheet(art, who) or jl.sheet_of(art.textures[who])
            else:
                sheet = jl.look_sheet(sprites, jl.look_like(edit.job), jl.WHO.index(who)) if sprites else None
            return jl.sheet_png(sheet, colors) if sheet is not None and colors is not None else None
        if part == "portrait":
            if art.portraits.get(who):
                return art.portraits[who][0][0]
            return self._game_art(jl.game_face_path(jl.look_like(edit.job), jl.WHO.index(who)))
        if part == "picture":
            return art.pictures.get(who) or None
        if part in ("icon", "command") and getattr(art, part):
            return getattr(art, part)
        return self._art_image(edit, part, who)

    def replace_art(self, part: str, who: str = "") -> None:
        """Replace...: an image of the modder's own made the job's (a figure's two textures, a portrait, job screen
        art, an icon)."""
        from .. import export_dialogs
        from PIL import Image
        page = _page()
        edit = self._picked_job()
        if edit is None:
            return
        path = self._ask("art_image", lambda: export_dialogs.open_file(
            self, REPLACE_TITLE.format(job=edit.job.name, part=ART_PARTS[(part, who)]),
            FIGURE_FILES if part == "figure" else page.IMAGE_FILES))
        if not path:
            return
        art, said = edit.art, ""
        try:
            if part == "figure" and str(path).lower().endswith(cs.SPR_SUFFIX):
                self._classic_figure(edit, who, cs.read_spr(Path(path).read_bytes()))
                return
            with Image.open(path) as image:
                image.load()
                if part == "figure" and cs.is_classic_picture(image):
                    classic = cs.read_picture(image)
                elif part == "figure":
                    classic = None
                    colors = self._figure_colors(edit, who)
                    if colors is None:
                        return
                    # (17 November 2026) At the game's size, or 2 to 8 times it: a bigger picture is kept with the
                    # job's art and also made the game's size, which is the figure's two textures.
                    upper, lower, off, bigger, kept = jl.figure_from_image(image, colors)
                    art.textures[who] = (upper, lower)
                    art.classic.pop(who, None)
                    if bigger is None:
                        art.big.pop(who, None)
                    else:
                        art.big[who] = bigger
                    # (The thirtieth session) Its own colors, kept for palette 0 where it had them.
                    if kept.own is None:
                        art.own.pop(who, None)
                    else:
                        art.own[who] = kept.own
                    colored = (FIGURE_OWN.format(n=f"{kept.count:,}") if kept.own is not None
                               else FIGURE_OWN_BIG.format(n=f"{kept.count:,}") if kept.dropped
                               else FIGURE_NEAREST.format(n=f"{off:,}") if off else "")
                    told = jl.textures_frames(art.textures[who], cs.game_kinds(self._sprites_for_jobs()))
                    said = " ".join(w for w in (FIGURE_BIGGER.format(n=bigger[0]) if bigger else "", colored,
                                                self._frames_said(edit, who, told), self._edges_said(edit, who)) if w)
                elif part == "portrait":
                    art.portraits[who] = [jl.portrait_from(image)]
                elif part == "picture":
                    art.pictures[who] = jl.png(jl.fitted(image, jl.PICTURE_SIZE))
                elif part == "icon":
                    art.icon = jl.png(jl.fitted(image, jl.ICON_SIZE))
                else:
                    art.command = jl.png(jl.fitted(image, jl.COMMAND_SIZE))
            if part == "figure" and classic is not None:
                self._classic_figure(edit, who, classic)
                return
        except (jl.LookError, cs.ClassicError) as exc:
            self._say(str(exc))
            return
        except Exception as exc:                                      # noqa: BLE001
            self._say(page.CANT_READ_IMAGE.format(problem=exc))
            return
        jl.tidy_look(edit.job, art)
        self._say(said)
        self._jobs_changed(refill=False)

    def _frames_said(self, edit: mj.JobEdit, who: str, told: Optional[int]) -> str:
        """(His 8th note of 14 November) The frames told of a figure's own textures kept (or, not told, put aside: the job
        it is based on's), and what is said of them."""
        if told in (cs.TYPE1, cs.TYPE2):
            edit.art.frames[who] = told
            return FRAMES_TOLD.format(n=told)
        edit.art.frames.pop(who, None)
        return FRAMES_UNTOLD.format(n=jl.frames_of_job(edit.job.like))

    def _classic_figure(self, edit: mj.JobEdit, who: str, classic: cs.Classic) -> None:
        """(His 8th note of 14 November) A figure made from a classic sprite: doubled to the game's size with its edges
        smoothed (Scale2x), its palettes made the sex's colors as the game wants them, and its frames told from its
        sheet."""
        colors = cs.team_colors(classic)
        art = edit.art
        art.textures[who] = cs.textures(classic, True)
        art.classic[who] = (classic, True)
        art.big.pop(who, None)                                        # a classic sprite is the game's size
        art.own.pop(who, None)                                        # and in its own palettes' colors
        jl.set_classic_colors(edit.job, who, colors, art)
        told = cs.told_frames(classic.pixels, cs.game_kinds(self._sprites_for_jobs()))
        whose = (MAN, WOMAN)[jl.WHO.index(who)].lower()
        made = (CLASSIC_MADE.format(smooth=CLASSIC_SMOOTHED, n=classic.given(), who=whose) if classic.given() > 1
                else CLASSIC_PALETTE.format(smooth=CLASSIC_SMOOTHED, who=whose))
        past = CLASSIC_PAST.format(n=f"{classic.past:,}") if classic.past else ""
        frames = self._frames_said(edit, who, told)
        self._say(" ".join(w for w in (made, past, frames, self._edges_said(edit, who)) if w))
        self._jobs_changed(refill=False)

    def _edges_said(self, edit: mj.JobEdit, who: str) -> str:
        """(His answer of 16 November to test 124: "Mod Studio should fix it automatically") What Export clears of a
        figure's own textures for the frames it is drawn with (`job_looks.cleared`): the pixels the game would show as a
        thin line under or beside a pose; "" where it clears none or the game's frames can't be read."""
        edges = jl.cleared(edit, who, jl.frames_reader(self._sprites_for_jobs()))[2]
        if edges is None or not edges.cleared:
            return ""
        return jl.EDGES_SAID.format(n=f"{edges.cleared:,}") + (
            jl.EDGES_SAID_TRIMMED.format(m=f"{edges.trimmed:,}") if edges.trimmed else "")

    def set_frames(self, who: str, kind: int) -> None:
        """(His pick "Tell it, modder can change") Type 1 frames or Type 2 frames: the frames a figure's own textures are
        drawn for, picked."""
        edit = self._picked_job()
        if edit is None or who not in edit.art.textures or kind not in (cs.TYPE1, cs.TYPE2):
            return
        edit.art.frames[who] = kind
        self._say(self._edges_said(edit, who))
        self._jobs_changed(refill=False)

    def set_smooth(self, who: str, on: bool) -> None:
        """(His pick "Smooth, plain if asked") Smooth the edges: a figure made from a classic sprite this session doubled
        again, by Scale2x or every pixel a block of 2 by 2."""
        edit = self._picked_job()
        if edit is None or who not in edit.art.classic:
            return
        classic = edit.art.classic[who][0]
        edit.art.textures[who] = cs.textures(classic, on)
        edit.art.classic[who] = (classic, on)
        self._say(self._edges_said(edit, who))
        self._jobs_changed(refill=False)

    def use_look_art(self, part: str, who: str = "") -> None:
        """Use its look's (a figure's textures, a portrait), No art (job screen art), Use the game's icon (an icon):
        the job's own put aside."""
        edit = self._picked_job()
        if edit is None:
            return
        art = edit.art
        if part == "figure":
            jl.use_look_figure(edit.job, who, art)
        elif part == "portrait":
            art.portraits.pop(who, None)
        elif part == "picture":
            art.pictures.pop(who, None)
        else:
            setattr(art, part, b"")
        jl.tidy_look(edit.job, art)
        self._say("")
        self._jobs_changed(refill=False)

    def export_art(self, part: str, who: str = "") -> None:
        """Export as PNG...: what a picture of the job's look shows (a figure its whole texture, in its first palette's
        colors, numbered as Replace... reads it back), saved where asked."""
        from .. import export_dialogs
        edit = self._picked_job()
        if edit is None:
            return
        data = self._export_data(edit, part, who)
        if data is None:
            return
        words = ART_PARTS[(part, who)]
        path = self._ask("export_png", lambda: export_dialogs.save_file(
            self, EXPORT_TITLE.format(part=words, job=edit.job.name), EXPORT_NAME.format(job=edit.job.name, part=words),
            PNG_FILES))
        if not path:
            return
        if isinstance(data, QImage):
            data.save(str(path), "PNG")
        else:
            with open(path, "wb") as handle:
                handle.write(data)

    def pick_color(self, who: str, palette: int, index: int) -> None:
        """A color clicked: changed to one picked, as the game shows it (each part's top five bits)."""
        from PySide6.QtWidgets import QColorDialog
        edit = self._picked_job()
        if edit is None:
            return
        game = self._game_palettes(edit, jl.WHO.index(who))
        shown = jl.shown_colors(edit.job, who, game)[palette]
        if shown is None:
            return
        title = COLOR_TITLE.format(job=edit.job.name, who=(MAN, WOMAN)[jl.WHO.index(who)], n=palette, k=index)
        chosen = self._ask("color", lambda: QColorDialog.getColor(QColor(shown[index]), self, title))
        if isinstance(chosen, QColor):
            if not chosen.isValid():
                return
            chosen = chosen.name()
        if not chosen:
            return
        jl.set_color(edit.job, who, palette, index, str(chosen), game, edit.art)
        self._jobs_changed(refill=False)

    def use_look_palette(self, who: str, palette: int) -> None:
        """A palette's Use its look's: its look's colors again."""
        edit = self._picked_job()
        if edit is None:
            return
        jl.use_look_palette(edit.job, who, palette, self._game_palettes(edit, jl.WHO.index(who)), edit.art)
        self._jobs_changed(refill=False)

    def _job_sheet(self, edit: mj.JobEdit) -> QWidget:
        """The middle for a job: the job as the game shows it, and (his notes of 14 November: no card for the Jobs
        tab) everything of it edited there, in boxes: The job; Its look (its figures, palettes, portraits and art, and
        the look it wears); under it its skillset, its abilities edited where they are listed with each one's JP at
        its right, beside what unlocks it; then its stats, equipment, innate abilities, statuses and elements. What
        Mod Studio Framework would say of it under the title."""
        page = _page()
        job = edit.job
        holder, column = _box(spacing=8)
        title = QLabel(SHEET_TITLE.format(job=job.name))
        title.setStyleSheet("font-weight: 600; font-size: 12pt;")
        column.addWidget(title)
        foot = QLabel("")
        foot.setWordWrap(True)
        column.addWidget(foot)
        self.job_foot = JobFoot(foot)
        scroll = SheetScroll()
        inside, sheet = _box(spacing=10)
        scroll.setWidget(inside)
        column.addWidget(scroll, 1)
        boxes = self._job_boxes(edit)
        sheet.addWidget(boxes["job"])

        # -- its look ---------------------------------------------------------------------------------------------
        self.look_parts, self.look_swatches = {}, {}
        look, look_column = _panel(SHEET_LOOK)
        self.field_widgets[f"section_{SHEET_LOOK}"] = look
        head, head_row = _box(QHBoxLayout, spacing=12)
        name_box, name_column = _box(spacing=2)
        big = QLabel(job.name)
        big.setStyleSheet("font-weight: 600; font-size: 14pt;")
        name_column.addWidget(big)
        said = page.muted(job.description)
        name_column.addWidget(said)
        head_row.addWidget(self._art_panel(("icon", ""), SHEET_JOB_ICON, self._art_image(edit, "icon"), (48, 48)), 0,
                           Qt.AlignTop)
        head_row.addWidget(name_box, 1)
        set_box, set_column = _box(spacing=2)
        set_name = QLabel(job.skillset_name)
        set_name.setStyleSheet("font-weight: 600;")
        set_column.addWidget(set_name)
        set_said = page.muted(job.skillset_description)
        set_column.addWidget(set_said)
        head_row.addWidget(self._art_panel(("command", ""), SHEET_SKILLSET_ICON, self._art_image(edit, "command"),
                                           (48, 48)), 0, Qt.AlignTop)
        head_row.addWidget(set_box, 1)
        for label in name_box.findChildren(QLabel) + set_box.findChildren(QLabel):
            label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        look_column.addWidget(head)
        figures = self._look_figures(edit)
        look_column.addWidget(figures)
        look_column.addWidget(boxes["look_fields"])
        # Its frame's border and margins on both sides.
        scroll.turnings.append((figures, 26))
        sheet.addWidget(look)
        self.job_sheet_widgets = {"title": title, "foot": foot, "name": big, "description": said,
                                  "skillset_name": set_name, "skillset_description": set_said}

        # -- under it: its skillset (right below the figures, his sixth note) beside what unlocks it, then the rest -
        under = Turning(10)
        under.add(boxes["skillset"], 3)
        under.add(boxes["unlocks"], 2)
        sheet.addWidget(under)
        scroll.turnings.append((under, 0))
        for first, second in (("stats", "equipment"), ("innate", "statuses")):
            pair = Turning(10)
            pair.add(boxes[first], 1)
            pair.add(boxes[second], 1)
            sheet.addWidget(pair)
            scroll.turnings.append((pair, 0))
        sheet.addStretch(1)
        self.job_foot.status(self._job_problems(edit))
        scroll.fit()
        return holder

    def _show_job_middle(self) -> None:
        """The middle with the Jobs tab: the job picked as the game shows it, with its fields, or nothing while none
        is. (His note of 14 November: "the whole main window seems to refresh and jitter with elements out of
        position and then fix itself") Made with the window's painting held: the new sheet is laid out, the old one
        taken out and the scroll put back before anything is painted, so the one paint after is the finished one."""
        old = self.job_sheet
        edit = self._picked_job()
        made_for = (self.job_pick, edit, self._jobs_version)
        if edit is not None and old is not None and self._sheet_made_for is not None \
                and self._sheet_made_for[0] == made_for[0] and self._sheet_made_for[1] is edit \
                and self._sheet_made_for[2] == made_for[2]:
            # The job's sheet as it is already: shown again, with its fields, nothing made again.
            self.field_widgets = dict(self._sheet_fields)
            self.middle.setCurrentWidget(self.job_sheet_holder)
            self._job_status()
            return
        place = 0
        if old is not None and self._sheet_was == self.job_pick:
            scroll = old.findChild(QScrollArea)
            place = scroll.verticalScrollBar().value() if scroll is not None else 0
        self._sheet_was = self.job_pick
        window = self.window()
        window.setUpdatesEnabled(False)
        was = self._building
        try:
            self._building = True
            try:
                # The tab has no card: the fields shown are the middle's.
                self.field_widgets = {}
                self.job_sheet_widgets = {}
                self.job_foot = None
                self.job_sheet = self._job_sheet(edit) if edit is not None else QWidget()
                self._sheet_fields = dict(self.field_widgets)
                self._sheet_made_for = made_for if edit is not None else None
            finally:
                self._building = was
            self._job_sheet_column.addWidget(self.job_sheet)
            if old is not None:
                # Out of the middle at once (not only once Qt deletes it): one sheet shown, never two over each other,
                # and hidden before it loses its parent, so it never shows as a window of its own.
                self._job_sheet_column.removeWidget(old)
                retire(old)
            self.middle.setCurrentWidget(self.job_sheet_holder)
            settle_sheet(self.job_sheet)
            scroll = self.job_sheet.findChild(QScrollArea)
            if place and scroll is not None:
                bar = scroll.verticalScrollBar()
                bar.setValue(min(place, bar.maximum()))
                if bar.value() != place:
                    QTimer.singleShot(0, lambda b=bar, v=place: b.setValue(v))
        finally:
            window.setUpdatesEnabled(True)

    def ability_show(self, edit: mj.AbilityEdit) -> AbilityShow:
        """What the map plays for a new ability: its own range, effect area, vertical tolerance, flags and charge
        time, with the effect, the charge and the animation of the game's ability it is based on."""
        ability = edit.ability

        def table(key: str) -> dict:
            try:
                record = self.state.item_table_records_by_id(key).get(ability.like)
            except Exception:                                         # noqa: BLE001
                record = None
            values = dict(record.values) if record is not None else {}
            values.update((getattr(self.state, "item_table_edits", None) or {}).get(key, {}).get(ability.like, {}))
            return values

        def whole(value, default: int) -> int:
            try:
                return int(str(value).strip())
            except (TypeError, ValueError):
                return default

        animation_row = table("ability_animation")
        charge_type = whole(animation_row.get("ChargeEffectType"), 0)
        animation = whole(animation_row.get("AnimationId"), 0)
        formula_name = reference_names.formula_names().get(mj.action_number(ability, "Formula"), "")
        reaction = (ap.RECEIVE_HEAL if "Heal" in formula_name else ap.TAKING_DAMAGE if "Dmg" in formula_name
                    else None)
        flags = {flag for flag, on in mj.action_flags(ability).items() if on}
        return AbilityShow(
            key=ability.like, title=ability.name, effect=whole(table("ability_effect").get("EffectId"), -1),
            charge_time=mj.action_number(ability, "CT"), charge_type=charge_type,
            charge_name=reference_names.charge_effect_names().get(charge_type, ""), animation=animation,
            animation_name=reference_names.animation_names().get(animation, ""),
            reach=ap.Reach(mj.action_number(ability, "Range"), mj.action_number(ability, "EffectArea"),
                           mj.action_number(ability, "Vertical"), flags),
            reaction=reaction)

    def _own_users(self, name: str) -> list:
        """The mod's jobs whose skillsets hold the ability, as the map's Shown by lists who uses one: a man and a
        woman of each, in the look the job wears."""
        users = []
        for edit in mj.skillsets_with(self.jobs_store(), name):
            worn = (edit.job.look or {}).get("Like")
            look = worn if isinstance(worn, int) else edit.job.like
            for sprite_set, word in ((us.GENERIC_MAN, "male"), (us.GENERIC_WOMAN, "female")):
                try:
                    sprite = us.sprite_number(sprite_set, look)
                except Exception:                                     # noqa: BLE001
                    sprite = None
                if sprite is not None:
                    users.append(ap.User(look, edit.job.name, sprite, 0, f"{edit.job.name}, {word}"))
        return users

    def _show_ability_middle(self) -> None:
        """The middle with the Abilities tab (his note of 14 November, 19:10: no card): the ability picked, played out
        on the Abilities page's own map, with its fields (`_ability_sheet`), or nothing while none is. Made with the
        window's painting held, as the Jobs tab's (`_show_job_middle`); a sheet still the ability's as it is shown
        again as it was. The map plays it either way."""
        old = self.ability_sheet
        edit = self._picked_ability()
        made_for = (self.ability_pick, edit, self._jobs_version)
        if edit is not None and old is not None and self._ability_made_for is not None \
                and self._ability_made_for[0] == made_for[0] and self._ability_made_for[1] is edit \
                and self._ability_made_for[2] == made_for[2]:
            self.field_widgets = dict(self._ability_fields)
            self.middle.setCurrentWidget(self.ability_map_holder)
            self._job_status()
            self._play_ability()
            return
        place = 0
        if old is not None and self._ability_sheet_was == self.ability_pick:
            scroll = old.findChild(QScrollArea)
            place = scroll.verticalScrollBar().value() if scroll is not None else 0
        self._ability_sheet_was = self.ability_pick
        window = self.window()
        window.setUpdatesEnabled(False)
        was = self._building
        try:
            # The map is kept from one sheet to the next: out of the old one, hidden, before that one goes.
            if self._ability_map is not None:
                self._ability_map.hide()
                self._ability_map.setParent(self.ability_map_holder)
            self._building = True
            try:
                # The tab has no card: the fields shown are the middle's.
                self.field_widgets = {}
                self.ability_sheet_widgets = {}
                self.ability_foot = None
                self.ability_sheet = self._ability_sheet(edit) if edit is not None else QWidget()
                self._ability_fields = dict(self.field_widgets)
                self._ability_made_for = made_for if edit is not None else None
            finally:
                self._building = was
            self._ability_map_column.addWidget(self.ability_sheet)
            if old is not None:
                # Out of the middle at once, hidden before it loses its parent (`retire`).
                self._ability_map_column.removeWidget(old)
                retire(old)
            self.middle.setCurrentWidget(self.ability_map_holder)
            settle_sheet(self.ability_sheet)
            scroll = self.ability_sheet.findChild(QScrollArea)
            if place and scroll is not None:
                bar = scroll.verticalScrollBar()
                bar.setValue(min(place, bar.maximum()))
                if bar.value() != place:
                    QTimer.singleShot(0, lambda b=bar, v=place: b.setValue(v))
        finally:
            window.setUpdatesEnabled(True)
        self._play_ability()

    def _play_ability(self) -> None:
        """The map plays the ability picked as it is now, shown by the mod's jobs whose skillsets hold it (or whoever
        uses the game's ability it is based on); nothing while none is picked."""
        if self._ability_map is None:
            return
        edit = self._picked_ability()
        if edit is None:
            self._ability_map.own_users = []
            self._ability_map.show(None)
            return
        self._ability_map.own_users = self._own_users(edit.ability.name)
        self._ability_map.show(self.ability_show(edit))
