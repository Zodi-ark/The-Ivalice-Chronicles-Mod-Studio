"""
Edit Game Data / UI Layouts.

Where every box, picture and line of text sits on the game's menu screens -
the 252 `.uib` files under `ui/` - drawn the way the game draws them, with
the numbers of the box you pick beside the picture: its position, size,
scale, colour and opacity and, for text, its font size. A box can be dragged
on the picture, and a picture's part - the rectangle of its texture sheet
it is cut from, kept in a `.utexpt` part list - edited, with the sheet shown
and every part of it outlined.

Asked for after an in-game test showed an edited layout loads from a mod:
"that page, with position, size, scale and text size, saved into your mod
the same way textures are". The shape follows the mock-up he approved:
screens on the left, as the Textures page lists textures; the screen drawn
with its real pictures; the screen's boxes in a list; the selected box's
numbers with tick boxes, as on every other page.

What the page does with an edit:

- **It stores the box's new values** in `state.uib_edits`, and nothing
  else. Export applies them to the game's own copy of the file, numbers
  overwritten where they sit (`uib.apply_edits`), which is what the in-game
  test did.
- **A move carries the box's animation keys** and a scale scales them, so
  the box still slides in to where you put it; a colour or opacity change
  carries the keys that restate it (`uib`'s notes have the rules and the
  numbers behind them). The note under the numbers says, for the box
  picked, which keys follow and which stay.
- **The tick box decides what reaches the mod**, as on every page: typing a
  number ticks it, looking at a box ticks nothing, and unticking puts the
  game's value back. A drag is typing a new position.
- **A part list is shared**, often by many screens, so its edits are kept on
  their own (`state.utexpt_edits`), not under the screen they were made
  from, and the note says how many screens a change reaches.

A mod opened with layout files of its own gets them back as edits here when
they are the kind this page makes (see `uib.edits_between`); any other copy
is carried into the export untouched, and this page shows that screen but
will not edit it.
"""
from __future__ import annotations

import dataclasses
import struct
from pathlib import Path

from PySide6.QtCore import QLocale, QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDoubleSpinBox, QGroupBox, QHBoxLayout, QLabel,
    QMenu, QLineEdit, QPushButton, QSpinBox, QSplitter, QTabWidget, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from ... import paths
from ... import uib
from .. import layout_preview as lp
from .. import layout_textures as lt
from ..models.texture_tree import TextureTreeModel
from ..widgets import actions
from ..widgets.layout_canvas import LayoutCanvas
from ..widgets.marked_tree import MarkedTreeView
from ..widgets.status_line import StatusLine
from ..workers import run_in_thread
from .textures import TexturePathFilter, TreePaneSizer

#: The screen tree's width on first show. The longest layout name in the
#: game is 38 characters (`ffto_battle_menu_instruction_message_02.uib`)
#: three folders down.
LAYOUT_TREE_WIDTH = 330

#: The box list and the numbers beside the picture.
SIDE_WIDTH = 360

#: How long the picture waits for typing to stop before it is redrawn.
REDRAW_DELAY_MS = 120

INTRO = ("Where every box, picture and line of text sits on the game's menu "
         "screens. Pick a screen, click a box, then drag it or change its "
         "numbers, colour, opacity, animation or the part of the texture it "
         "shows.")

#: The most characters a note under a box's numbers, or a key's, may have.
#: Zodi's limit: longer notes were being skimmed past.
NOTE_LIMIT = 220

def fit_note(sentences, limit: int = NOTE_LIMIT) -> str:
    """
    A note of at most `limit` characters from `(priority, text)` sentences,
    one per line in the order given: the lowest priority numbers are kept
    first, and a sentence that no longer fits is left out rather than cut.
    """
    kept, used = set(), 0
    for index in sorted(range(len(sentences)), key=lambda i: (sentences[i][0], i)):
        cost = len(sentences[index][1]) + (1 if kept else 0)
        if used + cost <= limit:
            kept.add(index)
            used += cost
    return "\n".join(sentences[i][1] for i in sorted(kept))


#: Words for the kinds of box, in the list beside the picture.
KIND_WORDS = {
    "Layer": "Group", "Reference": "Piece", "Image": "Picture", "Text": "Text",
    "Ninegrid": "Frame", "Rect": "Colour box", "Collision": "Click area",
    "Mask": "Mask", "Bezier": "Line", "Ellipse": "Ellipse", "Counter": "Counter",
    "Effect": "Effect", "Model": "Model",
}

_KEY_ROLE = Qt.UserRole + 10
#: On the list's rows for a whole piece (and the screen's own row): its name.
_COMPONENT_ROLE = Qt.UserRole + 11


def shortest_scale_text(value: float) -> str:
    """
    The fewest significant digits (up to 9, which any 32-bit float needs)
    that read back as the same 32-bit float: "1", "0.86875", "1.2099999".

    Never in exponent form, and never cut short to get out of it: the
    0.000010000001 that 16 boxes rest at (an opacity) is written out in full.
    Eight decimals used to make it 0.00001, a different float.
    """
    target = struct.unpack("<f", struct.pack("<f", value))[0]
    for digits in range(1, 10):
        text = f"{value:.{digits}g}"
        if struct.unpack("<f", struct.pack("<f", float(text)))[0] == target:
            break
    if "e" in text:
        mantissa, exponent = text.split("e")
        after = len(mantissa.split(".")[1]) if "." in mantissa else 0
        text = f"{float(text):.{max(0, after - int(exponent))}f}"
    return text


class LayoutTreeModel(TextureTreeModel):
    """The texture tree's model, saying "edited" where it says "replaced"."""

    def data(self, index, role=Qt.DisplayRole):
        value = super().data(index, role)
        if role == Qt.DisplayRole and isinstance(value, str):
            return value.replace(" replaced)", " edited)")
        return value


class ScaleSpinBox(QDoubleSpinBox):
    """
    A scale exactly as the file holds it, shown as briefly as it can be.

    The file holds 32-bit floats, and twelve of the game's scales are not
    short decimals - 1.2099999 sits beside 1.21. Eight decimals keep every
    one of them exactly, so ticking a row without typing writes back the
    game's own number and not a rounded neighbour of it (a rounded 1.21
    rewrote sixteen bytes of a file whose box nobody moved). Shown with the
    fewest digits that still mean the same float: 1 reads "1", 0.86875
    reads "0.86875".
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDecimals(8)
        # The text above is always written with a full stop, so it is read
        # back the same way whatever the computer's own decimal mark is.
        self.setLocale(QLocale.c())

    def textFromValue(self, value: float) -> str:                  # noqa: N802
        return shortest_scale_text(value)


class PairRow(QWidget):
    """
    `[x] Position  X [ 100 ]  Y [ 170 ]`

    The same three behaviours as `field_rows.NumericFieldRow`, for a field
    that is two numbers: typing ticks the box, `load()` ticks nothing, and
    `edited` fires only for the person's own changes.
    """

    edited = Signal()

    def __init__(self, label: str, first: str, second: str, decimals: int = 0,
                 minimum: float = -10000, maximum: float = 10000, parent=None):
        super().__init__(parent)
        self._loading = False
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 1, 0, 1)
        row.setSpacing(6)
        self.include = QCheckBox(label)
        self.include.setToolTip(
            "Tick to write this into your mod. Unticked, the game's own "
            "value is left alone.")
        self.include.setMinimumWidth(96)
        self.include.toggled.connect(self._on_include_toggled)
        row.addWidget(self.include)
        self.values = []
        for name in (first, second):
            row.addWidget(QLabel(name))
            box = ScaleSpinBox() if decimals else QSpinBox()
            if decimals:
                box.setSingleStep(0.05)
            box.setRange(minimum, maximum)
            box.setFixedWidth(84)
            box.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            box.valueChanged.connect(self._on_value_changed)
            row.addWidget(box)
            self.values.append(box)
        row.addStretch(1)

    @property
    def included(self) -> bool:
        return self.include.isChecked()

    def value(self) -> list:
        return [box.value() for box in self.values]

    def load(self, value, included: bool) -> None:
        self._loading = True
        try:
            for box, v in zip(self.values, value):
                box.setValue(v)
            self.include.setChecked(bool(included))
        finally:
            self._loading = False

    def set_value(self, value) -> None:
        """
        A value set whole, as the person's own change - a box dragged, a
        colour picked: the row ticks and `edited` fires once, not once per
        number (each firing stores the edit and asks for a redraw).
        """
        self._loading = True
        try:
            for box, v in zip(self.values, value):
                box.setValue(v)
        finally:
            self._loading = False
        if not self.include.isChecked():
            self.include.setChecked(True)     # emits edited via the toggle
        else:
            self.edited.emit()

    def _on_value_changed(self, _value) -> None:
        if self._loading:
            return
        if not self.include.isChecked():
            self.include.setChecked(True)     # emits edited via the toggle
            return
        self.edited.emit()

    def _on_include_toggled(self, _on) -> None:
        if not self._loading:
            self.edited.emit()


class SingleRow(PairRow):
    """`[x] Text size  [ 44 ]` - one number, the same behaviour."""

    def __init__(self, label: str, minimum: int, maximum: int, parent=None):
        QWidget.__init__(self, parent)
        self._loading = False
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 1, 0, 1)
        row.setSpacing(6)
        self.include = QCheckBox(label)
        self.include.setToolTip(
            "Tick to write this into your mod. Unticked, the game's own "
            "value is left alone.")
        self.include.setMinimumWidth(96)
        self.include.toggled.connect(self._on_include_toggled)
        row.addWidget(self.include)
        box = QSpinBox()
        box.setRange(minimum, maximum)
        box.setFixedWidth(84)
        box.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        box.valueChanged.connect(self._on_value_changed)
        row.addWidget(box)
        row.addStretch(1)
        self.values = [box]

    def value(self):
        return self.values[0].value()

    def load(self, value, included: bool) -> None:
        super().load([value], included)


class ColourRow(PairRow):
    """
    `[x] Colour  [swatch]`
    `            R [167]  G [154]  B [131]  A [255]`

    The box's colour as the file keeps it: red, green, blue, and alpha (how
    solid), each 0-255. The swatch opens a colour picker, alpha included;
    what it picks goes into the four numbers as one change, ticking the box
    once. The same three behaviours as every row: typing or picking ticks
    it, `load()` ticks nothing, `edited` fires only for the person's own
    changes.
    """

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self._loading = False
        rows = QVBoxLayout(self)
        rows.setContentsMargins(0, 1, 0, 1)
        rows.setSpacing(2)
        top = QHBoxLayout()
        top.setSpacing(6)
        self.include = QCheckBox("Colour")
        self.include.setToolTip(
            "Tick to write this into your mod. Unticked, the game's own "
            "value is left alone.")
        self.include.setMinimumWidth(96)
        self.include.toggled.connect(self._on_include_toggled)
        top.addWidget(self.include)
        self.swatch = QPushButton("")
        self.swatch.setFixedSize(84, 22)
        self.swatch.setToolTip("Choose a colour")
        self.swatch.clicked.connect(self.choose)
        top.addWidget(self.swatch)
        top.addStretch(1)
        rows.addLayout(top)
        numbers = QHBoxLayout()
        numbers.setSpacing(4)
        numbers.addSpacing(22)
        self.values = []
        for letter, word in (("R", "Red"), ("G", "Green"), ("B", "Blue"),
                             ("A", "Alpha, how solid it is: 0 is not seen, 255 is solid")):
            label = QLabel(letter)
            label.setToolTip(word)
            numbers.addWidget(label)
            box = QSpinBox()
            box.setRange(0, 255)
            # No arrows: four boxes with arrows do not fit beside the
            # picture, and a colour is typed or picked, not stepped.
            box.setButtonSymbols(QSpinBox.NoButtons)
            # ...and so none of the room the theme keeps for them.
            box.setStyleSheet("QSpinBox { padding: 2px 4px; }")
            box.setFixedWidth(46)
            box.setToolTip(word)
            box.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            box.valueChanged.connect(self._on_value_changed)
            numbers.addWidget(box)
            self.values.append(box)
        numbers.addStretch(1)
        rows.addLayout(numbers)

    def load(self, value, included: bool) -> None:
        super().load(value, included)
        self._paint_swatch()

    def _on_value_changed(self, _value) -> None:
        self._paint_swatch()
        super()._on_value_changed(_value)

    def _paint_swatch(self) -> None:
        red, green, blue, alpha = self.value()
        self.swatch.setStyleSheet(
            f"QPushButton {{ background-color: rgba({red}, {green}, {blue}, {alpha}); "
            f"border: 1px solid palette(mid); border-radius: 3px; }}")

    def choose(self) -> None:
        red, green, blue, alpha = self.value()
        picked = QColorDialog.getColor(QColor(red, green, blue, alpha), self, "Colour",
                                       QColorDialog.ShowAlphaChannel)
        if picked.isValid():
            self.pick((picked.red(), picked.green(), picked.blue(), picked.alpha()))

    def pick(self, rgba) -> None:
        """A colour chosen whole: set as one change, not four."""
        self.set_value([int(v) for v in rgba])
        self._paint_swatch()


class OpacitySpinBox(ScaleSpinBox):
    """
    An opacity, 0-1, exactly as the file holds it. Twelve decimals, not the
    scale's eight: 5 of the game's 65 opacities need more than eight to come
    back as the same float (16 boxes rest at 0.000010000001).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDecimals(12)
        self.setRange(0.0, 1.0)
        self.setSingleStep(0.05)


class OpacityRow(SingleRow):
    """`[x] Opacity  [ 0.5 ]  0 not seen - 1 solid` - one number, the same behaviour."""

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self._loading = False
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 1, 0, 1)
        row.setSpacing(6)
        self.include = QCheckBox("Opacity")
        self.include.setToolTip(
            "Tick to write this into your mod. Unticked, the game's own "
            "value is left alone.")
        self.include.setMinimumWidth(96)
        self.include.toggled.connect(self._on_include_toggled)
        row.addWidget(self.include)
        box = OpacitySpinBox()
        box.setFixedWidth(84)
        box.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        box.valueChanged.connect(self._on_value_changed)
        row.addWidget(box)
        hint = QLabel("0 not seen, 1 solid")
        hint.setProperty("role", "muted")
        row.addWidget(hint)
        row.addStretch(1)
        self.values = [box]


class PartRow(PairRow):
    """
    `[x] Part      Ramza_color_09 - part 1 of 3`
    `    Top-left      X [   1]  Y [   1]`
    `    Bottom-right  X [ 115]  Y [ 191]`

    Where a picture's piece is cut from its texture sheet: the part's
    corners, in the sheet's pixels - corners, not a size (Ramza's
    `1, 1, 115, 191` is shown 114 x 190). The same three behaviours as every
    row.
    """

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self._loading = False
        rows = QVBoxLayout(self)
        rows.setContentsMargins(0, 1, 0, 1)
        rows.setSpacing(2)
        top = QHBoxLayout()
        top.setSpacing(6)
        self.include = QCheckBox("Part")
        self.include.setToolTip(
            "Tick to write this into your mod. Unticked, the game's own "
            "value is left alone.")
        self.include.setMinimumWidth(96)
        self.include.toggled.connect(self._on_include_toggled)
        top.addWidget(self.include)
        self.part_name = QLabel("")
        self.part_name.setProperty("role", "muted")
        top.addWidget(self.part_name, 1)
        rows.addLayout(top)
        self.values = []
        for corner in ("Top left", "Bottom right"):
            line = QHBoxLayout()
            line.setSpacing(6)
            label = QLabel(corner)
            label.setFixedWidth(96)
            line.addWidget(label)
            for axis in ("X", "Y"):
                line.addWidget(QLabel(axis))
                box = QSpinBox()
                box.setRange(0, 100000)
                box.setFixedWidth(84)
                box.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                box.valueChanged.connect(self._on_value_changed)
                line.addWidget(box)
                self.values.append(box)
            line.addStretch(1)
            rows.addLayout(line)


#: What each kind of animation key sets, in the list's words.
KEY_WORDS = {uib.KEY_POSITION: "Position", uib.KEY_SIZE: "Size", uib.KEY_SCALE: "Scale",
             uib.KEY_COLOUR: "Colour", uib.KEY_OPACITY: "Opacity",
             uib.KEY_CHILD_TIMELINE: "Plays a piece's animation"}

_KEY_ID_ROLE = Qt.UserRole + 12

KEY_NOTE = ("Keys can only be changed, not added or removed. A key changed here "
            "keeps its value when its box moves. Easing numbers aren't decoded, "
            "and 1 is the commonest.")
#: Said for a key with a value: measured on all 252 files (45,740 keys).
MOMENT_NOTE = "Every key like this in the game lasts 0 frames."


class KeyEditor(QWidget):
    """
    `[x] Change this key`
    `Starts at frame [  0]  Lasts [ 10] frames   Easing [  1]`
    `Value  X [ 744]  Y [ 170]` (or a scale, a colour, an opacity)

    One tick box for the whole key. The same three behaviours as every row:
    typing ticks it, `load()` ticks nothing, `edited` fires only for the
    person's own changes.
    """

    edited = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._loading = False
        self.kind = None
        rows = QVBoxLayout(self)
        rows.setContentsMargins(0, 1, 0, 1)
        rows.setSpacing(4)
        self.include = QCheckBox("Change this key")
        self.include.setToolTip(
            "Tick to write this into your mod. Unticked, the game's own "
            "key is left alone.")
        self.include.toggled.connect(self._on_include_toggled)
        rows.addWidget(self.include)
        timing = QHBoxLayout()
        timing.setSpacing(6)
        timing.addWidget(self._label("Start frame"))
        self.frame = self._spin(0, 100000)
        timing.addWidget(self.frame)
        timing.addWidget(QLabel("Length"))
        self.frames = self._spin(0, 100000)
        timing.addWidget(self.frames)
        timing.addStretch(1)
        rows.addLayout(timing)
        easing = QHBoxLayout()
        easing.setSpacing(6)
        self.easing_label = self._label("Easing")
        easing.addWidget(self.easing_label)
        self.easing = self._spin(-100000, 100000)
        easing.addWidget(self.easing)
        easing.addStretch(1)
        rows.addLayout(easing)
        value = QHBoxLayout()
        value.setSpacing(4)
        self.value_label = self._label("Value")
        value.addWidget(self.value_label)
        # Every kind's inputs are made once; `load` shows the ones its key uses.
        self.pair_int = [self._spin(-100000, 100000) for _ in range(2)]
        self.pair_float = []
        for _ in range(2):
            box = ScaleSpinBox()
            box.setRange(-50, 50)
            box.setSingleStep(0.05)
            box.setFixedWidth(80)
            box.valueChanged.connect(self._on_value_changed)
            self.pair_float.append(box)
        self.rgba = []
        for _ in range(4):
            box = self._spin(0, 255)
            box.setButtonSymbols(QSpinBox.NoButtons)
            box.setStyleSheet("QSpinBox { padding: 2px 4px; }")
            box.setFixedWidth(46)
            self.rgba.append(box)
        self.fade = OpacitySpinBox()
        self.fade.setFixedWidth(84)
        self.fade.valueChanged.connect(self._on_value_changed)
        self.plays = QLabel("")
        self.plays.setProperty("role", "muted")
        for widget in self.pair_int + self.pair_float + self.rgba + [self.fade, self.plays]:
            value.addWidget(widget)
        value.addStretch(1)
        rows.addLayout(value)

    @staticmethod
    def _label(text: str) -> QLabel:
        label = QLabel(text)
        label.setFixedWidth(76)
        return label

    def _spin(self, low, high):
        box = QSpinBox()
        box.setRange(low, high)
        box.setFixedWidth(72)
        box.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        box.valueChanged.connect(self._on_value_changed)
        return box

    def _value_boxes(self) -> list:
        return {uib.KEY_POSITION: self.pair_int, uib.KEY_SIZE: self.pair_int,
                uib.KEY_SCALE: self.pair_float, uib.KEY_COLOUR: self.rgba,
                uib.KEY_OPACITY: [self.fade]}.get(self.kind, [])

    @property
    def included(self) -> bool:
        return self.include.isChecked()

    def load(self, key: uib.Key, included: bool) -> None:
        """Shows `key` (a key of the screen as edited), ticked or not."""
        self._loading = True
        try:
            self.kind = key.kind
            # Inside its animation, as every key in the game is.
            self.frame.setMaximum(key.last_frame)
            self.frames.setMaximum(key.last_frame)
            self.frame.setValue(key.frame)
            self.frames.setValue(key.frames)
            has_value = key.kind in uib.KEY_VALUE_FORMATS
            self.easing.setVisible(has_value)
            self.easing_label.setVisible(has_value)
            if has_value:
                self.easing.setValue(key.easing)
            shown = self._value_boxes()
            for box in self.pair_int + self.pair_float + self.rgba + [self.fade]:
                box.setVisible(box in shown)
            for box, v in zip(shown, key.values):
                box.setValue(v)
            self.plays.setVisible(key.kind == uib.KEY_CHILD_TIMELINE)
            self.plays.setText(f"plays {key.values[0] or '(the game chooses)'}"
                               if key.kind == uib.KEY_CHILD_TIMELINE and key.values else "")
            self.value_label.setVisible(bool(shown) or key.kind == uib.KEY_CHILD_TIMELINE)
            self.include.setChecked(bool(included))
        finally:
            self._loading = False

    def edit(self, key: uib.Key) -> dict:
        """The key edit these numbers make, for `key` (which says which key it was made on)."""
        made = {"kind": key.kind, "target": key.target, "was_frame": key.frame,
                "frame": self.frame.value(), "frames": self.frames.value()}
        if key.kind in uib.KEY_VALUE_FORMATS:
            made["easing"] = self.easing.value()
            made["value"] = [box.value() for box in self._value_boxes()]
        return made

    def _on_value_changed(self, _value) -> None:
        if self._loading:
            return
        if not self.include.isChecked():
            self.include.setChecked(True)     # emits edited via the toggle
            return
        self.edited.emit()

    def _on_include_toggled(self, _on) -> None:
        if not self._loading:
            self.edited.emit()


class UiLayoutsPage(QWidget):
    edits_changed = Signal()
    #: A texture's path, or a folder's, for the Textures page to open at.
    jump_to_texture = Signal(str)

    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state
        self.current_rel = ""
        self.layout_obj = None          # the current screen, edits applied
        self.game_layout = None         # the game's own copy of it
        self.selected_key = ""
        self.read_only = False
        self._drawn_component = None
        self._draw_token = 0
        self._draw_busy = False
        self._pending_draw = None
        #: The drawing on its thread, so a newer request can stop it.
        self._running_draw = None
        self.draws_started = 0
        #: Drawings asked to stop because a newer one was wanted.
        self.draws_cancelled = 0
        self.last_result = None
        self._tree = None
        #: Components the screen's root places, directly or through pieces.
        self._placed = set()
        #: Swapped by the suites, which cannot run FF16Tools.
        self.decode = None
        self.decode_replacement = None
        #: The part list whose sheet the picture shows, when it shows one.
        self._drawn_sheet = None
        #: `layout_textures.part_list_users`, read once per game folder.
        self._users = None

        self._redraw_timer = QTimer(self)
        self._redraw_timer.setSingleShot(True)
        self._redraw_timer.setInterval(REDRAW_DELAY_MS)
        self._redraw_timer.timeout.connect(self._start_pending_draw)

        self.model = LayoutTreeModel()
        self.proxy = TexturePathFilter()
        self.proxy.setSourceModel(self.model)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 10, 24, 20)
        outer.setSpacing(10)
        outer.addLayout(actions.page_intro(INTRO))
        self.counter = QLabel("")
        self.counter.setProperty("role", "ok")
        outer.addWidget(self.counter)

        split = QSplitter(Qt.Horizontal)
        split.setHandleWidth(14)
        self.split = split

        # -- left: the screens ----------------------------------------------
        left = QVBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search by name or folder")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._on_filter)
        left.addWidget(self.search)
        self.tree = MarkedTreeView()
        self.tree.setModel(self.proxy)
        self.tree.setUniformRowHeights(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.setMinimumWidth(240)
        self.tree.selectionModel().currentChanged.connect(self._on_tree_selection)
        left.addWidget(self.tree, 1)
        self.empty_note = QLabel(
            "No game files yet.\n\nGo to General Setup and either unpack your "
            "game, or point at a folder you have already unpacked. Its menu "
            "screens will appear here.")
        self.empty_note.setProperty("role", "muted")
        self.empty_note.setWordWrap(True)
        self.empty_note.setAlignment(Qt.AlignTop)
        left.addWidget(self.empty_note, 1)

        # -- right: the screen, its boxes, the selected box -----------------
        right = QVBoxLayout()
        self.selected_label = QLabel("Select a screen")
        self.selected_label.setStyleSheet("font-weight: 600; font-size: 12pt;")
        self.selected_label.setWordWrap(True)
        right.addWidget(self.selected_label)

        state_row = QHBoxLayout()
        state_row.setSpacing(8)
        self.state_label = QLabel("Show the screen:")
        state_row.addWidget(self.state_label)
        self.timeline = QComboBox()
        self.timeline.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.timeline.setToolTip(
            "Screens animate as they open and change. The picture shows the "
            "screen at the end of this animation.")
        self.timeline.currentTextChanged.connect(self._on_timeline)
        state_row.addWidget(self.timeline)
        self.sheet_button = QPushButton("Show its texture sheet")
        self.sheet_button.setCheckable(True)
        self.sheet_button.setToolTip(
            "Show the texture sheet the picked picture is cut from, with every "
            "part of it outlined and the picture's own part picked out.")
        self.sheet_button.toggled.connect(self._on_sheet_toggled)
        state_row.addWidget(self.sheet_button)
        self.status = StatusLine()
        state_row.addWidget(self.status, 1)
        right.addLayout(state_row)

        # The picture and the box's panel, with a divider between them that
        # drags - as the one beside the screen list does. Zodi asked for
        # the panel to be widened the same way.
        body = QSplitter(Qt.Horizontal)
        body.setHandleWidth(14)
        body.setChildrenCollapsible(False)
        self.body_split = body
        self.canvas = LayoutCanvas()
        self.canvas.box_clicked.connect(self.select_box)
        # Dragging the picked box moves it - the same edit as typing a new
        # position (see `_on_box_dragged`).
        self.canvas.box_dragged.connect(self._on_box_dragged)
        # Right-click a box, on the picture or in the list: open its texture
        # in Textures (see `box_menu`).
        self.canvas.setContextMenuPolicy(Qt.CustomContextMenu)
        self.canvas.customContextMenuRequested.connect(self._canvas_menu)
        body.addWidget(self.canvas)

        side = QVBoxLayout()
        side.setSpacing(8)
        self.boxes_label = QLabel("Boxes on this screen")
        side.addWidget(self.boxes_label)
        self.box_list = QTreeWidget()
        self.box_list.setColumnCount(2)
        self.box_list.setHeaderLabels(["Box", "Kind"])
        self.box_list.setAlternatingRowColors(True)
        self.box_list.setColumnWidth(0, 210)
        self.box_list.currentItemChanged.connect(self._on_box_item)
        self.box_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.box_list.customContextMenuRequested.connect(self._list_menu)
        # The list gives way to the numbers under it, down to a few rows.
        self.box_list.setMinimumHeight(120)
        side.addWidget(self.box_list, 1)

        self.fields = QGroupBox("Click a box")
        fields = QVBoxLayout(self.fields)
        fields.setSpacing(4)
        self.origin_row = PairRow("Position", "X", "Y")
        # Not floored at 0: one box in the game is 1920 x -250 (a colour
        # box drawn upwards), and a floor showed and wrote its height as 0.
        self.size_row = PairRow("Size", "W", "H")
        self.scale_row = PairRow("Scale", "X", "Y", decimals=5, minimum=-50, maximum=50)
        self.font_row = SingleRow("Text size", 1, 400)
        self.colour_row = ColourRow()
        self.opacity_row = OpacityRow()
        self.rows = {uib.FIELD_ORIGIN: self.origin_row, uib.FIELD_SIZE: self.size_row,
                     uib.FIELD_SCALE: self.scale_row, uib.FIELD_FONT_SIZE: self.font_row,
                     uib.FIELD_COLOUR: self.colour_row, uib.FIELD_OPACITY: self.opacity_row}
        for field_name, row in self.rows.items():
            row.edited.connect(lambda f=field_name: self._on_field_edited(f))
            fields.addWidget(row)
        # Not one of `rows`: a part is not a field of the box but of the
        # part list its picture is cut from, stored on its own.
        self.part_row = PartRow()
        self.part_row.edited.connect(self._on_part_edited)
        fields.addWidget(self.part_row)
        self.box_note = QLabel("")
        self.box_note.setProperty("role", "muted")
        self.box_note.setWordWrap(True)
        fields.addWidget(self.box_note)
        # The picked box's animation keys, on a tab of their own beside its
        # numbers: there can be dozens.
        self.keys_panel = QWidget()
        keys_layout = QVBoxLayout(self.keys_panel)
        keys_layout.setContentsMargins(4, 6, 4, 4)
        self.keys_tree = QTreeWidget()
        self.keys_tree.setColumnCount(3)
        self.keys_tree.setHeaderLabels(["Animation / key", "Frame", "Value"])
        self.keys_tree.setColumnWidth(0, 150)
        self.keys_tree.setColumnWidth(1, 60)
        self.keys_tree.currentItemChanged.connect(self._on_key_item)
        keys_layout.addWidget(self.keys_tree, 1)
        self.key_group = QGroupBox("Click a key")
        key_rows = QVBoxLayout(self.key_group)
        self.key_editor = KeyEditor()
        self.key_editor.edited.connect(self._on_key_edited)
        key_rows.addWidget(self.key_editor)
        self.key_note = QLabel(KEY_NOTE)
        self.key_note.setProperty("role", "muted")
        self.key_note.setWordWrap(True)
        key_rows.addWidget(self.key_note)
        keys_layout.addWidget(self.key_group)
        self.side_tabs = QTabWidget()
        self.side_tabs.addTab(self.fields, "Box")
        self.side_tabs.addTab(self.keys_panel, "Animation")
        side.addWidget(self.side_tabs)
        side_holder = QWidget()
        side_holder.setLayout(side)
        # Never narrower than it was built for (its rows need that much),
        # and as much wider as the divider is dragged.
        side_holder.setMinimumWidth(SIDE_WIDTH)
        self.side_holder = side_holder
        body.addWidget(side_holder)
        # A wider window goes to the picture; the panel keeps its width.
        body.setStretchFactor(0, 1)
        body.setStretchFactor(1, 0)
        self._side_sizer = TreePaneSizer(body, SIDE_WIDTH, last=True)
        right.addWidget(body, 1)

        left_holder = QWidget()
        left_holder.setLayout(left)
        right_holder = QWidget()
        right_holder.setLayout(right)
        split.addWidget(left_holder)
        split.addWidget(right_holder)
        split.setChildrenCollapsible(False)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        self._tree_sizer = TreePaneSizer(split, LAYOUT_TREE_WIDTH)
        outer.addWidget(split, 1)

        self._show_box(None)
        self.refresh_tree()

    # -- the screen tree -------------------------------------------------------

    def _game_dir(self):
        folder = getattr(self.state, "nxd_unpack_dir", None)
        return Path(folder) if folder else None

    def _scan_tree(self):
        """
        The screens in the unpacked game, or None when there are none.

        Scanned afresh on every refresh rather than kept in the state: 252
        files in 23 folders under `ui/` take milliseconds, and a cached copy
        is one more thing an opened mod would have to remember to clear.
        """
        game = self._game_dir()
        if game is None:
            return None
        try:
            tree = uib.scan_layout_tree(game)
        except Exception:                                      # noqa: BLE001
            return None
        return tree if tree.children else None

    def _marked(self) -> dict:
        """Every screen your mod changes: edited here, or carried through whole."""
        marked = {rel: True for rel, boxes in self.state.uib_edits.items() if boxes}
        for rel in self._carried_layouts():
            marked[rel] = True
        return marked

    def _carried_layouts(self) -> dict:
        """
        `{path: file}` for the screens the opened mod carries whole, keyed
        by the game's own spelling of the path. A mod's `UI/...` is the
        game's `ui/...` on Windows: a screen carried under either spelling
        must show as carried and not be editable, or export would write the
        carried copy over the edits made here.
        """
        spelled = ({rel.lower(): rel for rel in uib.layout_paths(self._tree)}
                   if self._tree is not None else {})
        carried = {}
        for rel, source in (getattr(self.state, "other_file_replacements", {}) or {}).items():
            if rel.lower().endswith(uib.LAYOUT_EXTENSION):
                carried[spelled.get(rel.lower(), rel)] = source
        return carried

    @staticmethod
    def shown_root(tree):
        """
        Where the list starts: past every folder that holds nothing but one
        other folder.

        All 252 of the game's screens are under `ui/ffto/`, so the list used
        to open on a single `ffto` row that had to be opened before anything
        else showed. Zodi asked for it to start inside `ffto`. It does so
        because `ffto` is the only thing there, not because of its name: a
        game update that adds a screen anywhere else stops the skipping at
        the folder where the two part, and both show.

        Only the rows change. Every path the page, its edits and its jumps
        use is still the whole `ui/ffto/...` path; the model takes the
        starting folder's own path off before it looks one up.
        """
        node = tree
        while node is not None and len(node.children) == 1 and not node.children[0].is_file:
            node = node.children[0]
        return node

    def refresh_tree(self) -> None:
        """
        Rebuilds the screen list and re-reads the edit store.

        Re-read, not kept: opening a mod REPLACES `state.uib_edits` with a
        new dict, and a page holding the old one would show and save the
        previous mod's edits - the fault the Textures page's `refresh_tree`
        records.
        """
        tree = self._scan_tree()
        self._tree = tree
        self._users = None
        self.model.set_root(self.shown_root(tree))
        self.model.set_edits(self._marked())
        self.empty_note.setVisible(tree is None)
        self.tree.setVisible(tree is not None)
        self.search.setEnabled(tree is not None)
        self._update_counter()
        if self.current_rel:
            self._load_screen(self.current_rel, keep_selection=True)

    def _update_counter(self) -> None:
        total = uib.count_layouts(self._tree) if self._tree is not None else 0
        edited = len(self._marked())
        lists = self.state.edited_utexpt_file_count()
        text = actions.edit_counter_text(edited, total, "screens") if total else ""
        if text and lists:
            text += f", and {lists} texture part list{'s' if lists != 1 else ''}"
        self.counter.setText(text)

    def _on_filter(self, text: str) -> None:
        self.proxy.setFilterFixedString(text)
        if text.strip():
            self.tree.expandAll()
        else:
            self.tree.collapseAll()

    def select_record(self, relative_path) -> bool:
        """Selects a screen by its path - what a jump from another tab carries."""
        index = self.model.index_for_path(str(relative_path))
        if not index.isValid():
            return False
        mapped = self.proxy.mapFromSource(index)
        if not mapped.isValid():
            self.search.clear()
            mapped = self.proxy.mapFromSource(index)
            if not mapped.isValid():
                return False
        self.tree.setCurrentIndex(mapped)
        self.tree.scrollTo(mapped)
        return True

    def _on_tree_selection(self, current, _previous) -> None:
        node = self.proxy.data(current, Qt.UserRole + 1) if current.isValid() else None
        if node is None or not getattr(node, "is_file", False):
            return
        self._load_screen(node.relative_path)

    # -- one screen ----------------------------------------------------------------

    def _carried_copy(self, rel: str):
        source = self._carried_layouts().get(rel)
        return Path(source) if source else None

    def _load_screen(self, rel: str, keep_selection: bool = False) -> None:
        game = self._game_dir()
        previous_key = self.selected_key if keep_selection else ""
        self.current_rel = rel
        self.selected_label.setText(rel.rsplit("/", 1)[-1])
        self.read_only = False
        self.game_layout = self.layout_obj = None
        # A piece the last screen was showing on its own is not this one's.
        self._drawn_component = None
        try:
            game_bytes = (game / rel).read_bytes()
            self.game_layout = uib.Layout(game_bytes)
            carried = self._carried_copy(rel)
            if carried is not None:
                # A mod's own copy this page could not take over: shown as
                # it is, not editable here.
                self.layout_obj = uib.Layout(carried.read_bytes())
                self.read_only = True
            else:
                data, problems = uib.apply_edits(game_bytes, self.state.uib_edits.get(rel, {}))
                self.layout_obj = uib.Layout(data)
        except Exception as exc:                               # noqa: BLE001
            # Anything at all: a damaged file is one screen that can't be
            # shown, not a page that stops working.
            self.game_layout = self.layout_obj = None
            # A drawing asked for by the last screen must not arrive under
            # this one's name.
            self._draw_token += 1
            self._pending_draw = None
            self._redraw_timer.stop()
            if self._running_draw is not None:
                self._running_draw.cancel()
                self.draws_cancelled += 1
                self._running_draw = None
            self.last_result = None
            self.canvas.draggable = False
            self.status.say(f"This screen could not be read: {exc}", "danger")
            self.canvas.clear()
            self.box_list.clear()
            # Emptying the list announces a new animation, which asks for a
            # drawing - refused by `request_draw`, as there is no screen.
            self.timeline.clear()
            self._show_box(None)
            return
        self.canvas.draggable = not self.read_only
        if self.read_only:
            self.status.say("Your mod has its own copy of this screen, made "
                            "another way. It goes into your mod as it is, so "
                            "it can't be edited here.", "attention")
        else:
            self.status.clear()
        self._fill_timelines()
        self._fill_box_list()
        key = previous_key if previous_key in self.layout_obj.boxes else ""
        self._show_box(key or None)
        self.request_draw()

    def _fill_timelines(self) -> None:
        root = self.layout_obj.root
        names = list(dict.fromkeys(root.timelines)) if root is not None else []
        current = self.timeline.currentText()
        self.timeline.blockSignals(True)
        self.timeline.clear()
        self.timeline.addItems(names)
        if current in names:
            self.timeline.setCurrentText(current)
        elif "Show" in names:
            self.timeline.setCurrentText("Show")
        elif "HomePosition" in names:
            self.timeline.setCurrentText("HomePosition")
        self.timeline.blockSignals(False)
        self.timeline.setEnabled(bool(names))

    def _fill_box_list(self) -> None:
        """
        The screen's boxes as it places them: the root component first, a
        piece from this file opened up where it is placed, then every
        component the root never places - which is most of a shared file
        like `ffto_common_window`, whose pieces other screens use.
        """
        self.box_list.blockSignals(True)
        self.box_list.clear()
        lay = self.layout_obj
        placed = set()

        def add(parent_item, boxes, stack):
            for box in boxes:
                words = KIND_WORDS.get(box.kind, box.kind)
                if box.kind == "Reference" and box.reference_file:
                    words += f" from {box.reference_file.rsplit('/', 1)[-1]}"
                elif box.kind == "Reference" and not box.reference_name:
                    words += " filled in by the game"
                item = QTreeWidgetItem([box.name, words])
                actions.mark_edited(item, self._box_edited(box.key))
                item.setData(0, _KEY_ROLE, box.key)
                item.setToolTip(0, box.key)
                parent_item.addChild(item) if parent_item is not None else self.box_list.addTopLevelItem(item)
                add(item, box.children, stack)
                if box.kind == "Reference" and not box.reference_file \
                        and box.reference_name in lay.components \
                        and box.reference_name not in stack:
                    placed.add(box.reference_name)
                    add(item, lay.components[box.reference_name].boxes,
                        stack | {box.reference_name})

        root = lay.root
        if root is not None:
            top = QTreeWidgetItem([root.name, "Screen"])
            top.setData(0, _COMPONENT_ROLE, root.name)
            self.box_list.addTopLevelItem(top)
            placed.add(root.name)
            add(top, root.boxes, {root.name})
            top.setExpanded(True)
        # What the screen itself shows, taken before the other pieces are
        # listed: opening those up adds the pieces THEY place, which the
        # screen does not draw - and a box in one of those would then be
        # "on the screen" and never outlined (40 screens have one).
        self._placed = set(placed)
        others = [c for name, c in lay.components.items() if name not in placed]
        if others:
            group = QTreeWidgetItem(["Other pieces in this file", ""])
            self.box_list.addTopLevelItem(group)
            for comp in others:
                item = QTreeWidgetItem([comp.name, "Piece"])
                item.setData(0, _COMPONENT_ROLE, comp.name)
                group.addChild(item)
                add(item, comp.boxes, {comp.name})
        self.box_list.expandToDepth(2)
        self.box_list.blockSignals(False)

    def _box_edited(self, key: str) -> bool:
        """A box's own numbers edited, or any of its animation keys."""
        screen = self.state.uib_edits.get(self.current_rel, {})
        if screen.get(key):
            return True
        box = self.game_layout.boxes.get(key) if self.game_layout is not None else None
        return box is not None and any(
            edit.get("target") == box.name and key_id.startswith(box.component + "/")
            for key_id, edit in (screen.get(uib.ANIMATION_KEYS) or {}).items())

    def _on_timeline(self, _text) -> None:
        self.request_draw()

    # -- choosing a box ----------------------------------------------------------

    def _on_box_item(self, current, _previous) -> None:
        key = current.data(0, _KEY_ROLE) if current is not None else None
        if key:
            self._show_box(key)
            self._redraw_if_component_changed()

    def select_box(self, key: str) -> bool:
        """Picks a box by its "Component/Path" key, in the list and the picture."""
        if self.layout_obj is None or key not in self.layout_obj.boxes:
            return False
        item = self._item_for(key)
        if item is not None:
            self.box_list.blockSignals(True)
            self.box_list.setCurrentItem(item)
            self.box_list.scrollToItem(item)
            self.box_list.blockSignals(False)
        self._show_box(key)
        self._redraw_if_component_changed()
        return True

    def _item_for(self, key: str):
        stack = [self.box_list.topLevelItem(i) for i in range(self.box_list.topLevelItemCount())]
        while stack:
            item = stack.pop(0)
            if item.data(0, _KEY_ROLE) == key:
                return item
            stack.extend(item.child(i) for i in range(item.childCount()))
        return None

    def _box(self, key):
        return self.layout_obj.boxes.get(key) if (self.layout_obj and key) else None

    def _show_box(self, key) -> None:
        """Loads the selected box's numbers into the rows, ticking only what the mod changes."""
        self.selected_key = key or ""
        box = self._box(key)
        game_box = self.game_layout.boxes.get(key) if (self.game_layout and key) else None
        self._show_part(box if game_box is not None else None)
        self._fill_keys(box if game_box is not None else None)
        self.canvas.set_selected(self._canvas_key())
        if box is None or game_box is None:
            self.fields.setTitle("Click a box")
            for row in self.rows.values():
                row.setEnabled(False)
                row.include.blockSignals(True)
                row.include.setChecked(False)
                row.include.blockSignals(False)
            self.box_note.setText("Click a box in the picture, or pick one from the list.")
            return
        edits = self.state.uib_edits.get(self.current_rel, {}).get(key, {})
        self.fields.setTitle(f"{KIND_WORDS.get(box.kind, box.kind)} {box.name}")
        for field_name, row in self.rows.items():
            applies = field_name in box.editable_fields()
            value = box.value(field_name) if applies else None
            row.setVisible(applies or field_name != uib.FIELD_FONT_SIZE)
            # A text box with no text settings in the file has no size to
            # show - none of the game's do, but a damaged copy could.
            row.setEnabled(applies and value is not None and not self.read_only)
            if value is None:
                continue
            row.load(list(value) if isinstance(value, tuple) else value, field_name in edits)
        self.box_note.setText(self._note_for(box, game_box, edits))

    def _note_for(self, box, game_box, edits) -> str:
        """
        The note under a box's numbers: at most `NOTE_LIMIT` characters,
        whatever the box, the most important sentences kept (`fit_note`).

        Every sentence is `(priority, text)`, in the order it is read; a
        lower priority is kept first. Why the box can't be edited comes
        first, then why its part can't be, then what the game has for the
        numbers you changed, then which animation keys follow it, then who
        else its part list reaches, and last what kind of box it is.
        """
        sentences = []
        if self.read_only:
            sentences.append((0, "Not editable, as your mod has its own copy of this screen."))
        info = self._part_info(box)
        if info is not None and info["why"]:
            sentences.append((1, info["why"]))
        game_values = self._game_values(game_box, edits)
        if game_values:
            sentences.append((3, game_values))
        sentences += self._key_sentences(game_box)
        if info is not None and not info["why"]:
            sentences += self._part_sentences(info)
        sentences += self._kind_sentences(box)
        return fit_note(sentences)

    @staticmethod
    def _game_values(game_box, edits) -> str:
        """What the game has for each number you changed, in one sentence."""
        values = []
        if uib.FIELD_SIZE in edits:
            values.append(f"size {game_box.size[0]} by {game_box.size[1]}")
        if uib.FIELD_SCALE in edits:
            values.append(f"scale {shortest_scale_text(game_box.scale[0])} by "
                          f"{shortest_scale_text(game_box.scale[1])}")
        if uib.FIELD_FONT_SIZE in edits:
            values.append(f"text size {game_box.font_size}")
        if uib.FIELD_COLOUR in edits:
            values.append("colour " + ", ".join(str(v) for v in game_box.colour))
        if uib.FIELD_OPACITY in edits:
            values.append(f"opacity {shortest_scale_text(game_box.opacity)}")
        listed = (", ".join(values[:-1]) + " and " + values[-1]) if len(values) > 1 else \
            (values[0] if values else "")
        if uib.FIELD_ORIGIN in edits:
            at = f"In the game it is at X {game_box.origin[0]}, Y {game_box.origin[1]}"
            return at + (f", with {listed}." if listed else ".")
        return f"In the game it has {listed}." if listed else ""

    def _key_sentences(self, game_box) -> list:
        """
        Which of the box's animation keys follow a change to it, and which
        stay - the rules in `uib`'s notes, said for this box.
        """
        layout = self.game_layout
        following, staying = [], []
        moves = len(layout.keys_for(game_box, uib.KEY_POSITION))
        if moves:
            following.append(f"{moves} position")
        for kind, words, pair, axes in ((uib.KEY_SIZE, "size", game_box.size, ("width", "height")),
                                        (uib.KEY_SCALE, "scale", game_box.scale, ("X", "Y"))):
            count = len(layout.keys_for(game_box, kind))
            if not count:
                continue
            zero = [axis for axis, value in zip(axes, pair) if value == 0]
            if len(zero) < 2:
                following.append(f"{count} {words}")
            if zero:
                staying.append(f"Its {words} keys keep their {' and '.join(zero)}, "
                               f"as the box rests at 0 there.")
        tints = [tuple(k.values) for k in layout.keys_for(game_box, uib.KEY_COLOUR)]
        same = tints.count(game_box.colour)
        if same:
            following.append(f"{same} colour")
        if len(tints) > same:
            others = len(tints) - same
            staying.append(f"{others} colour key{'s' if others != 1 else ''} for "
                           f"another colour {'stay' if others != 1 else 'stays'}.")
        fades = len(layout.keys_for(game_box, uib.KEY_OPACITY))
        if fades and game_box.opacity > 0:
            following.append(f"{fades} opacity")
        elif fades:
            staying.append(f"It rests unseen, so its {fades} opacity "
                           f"{'keys stay' if fades != 1 else 'key stays'}.")
        sentences = []
        if following:
            listed = (", ".join(following[:-1]) + " and " + following[-1]) \
                if len(following) > 1 else following[0]
            only_one = len(following) == 1 and following[0].startswith("1 ")
            sentences.append((4, f"Its {listed} {'key changes' if only_one else 'keys change'} "
                                 f"with it."))
        sentences += [(6, text) for text in staying]
        return sentences

    def _part_sentences(self, info) -> list:
        """Who else a picture's part list reaches, and what the game had for its corners."""
        edited = bool(self.state.utexpt_edits.get(info["list"], {}).get(info["index"]))
        users = self._part_list_users().get(info["list"], [])
        name = info["list"].rsplit("/", 1)[-1]
        sentences = [(2 if edited else 5,
                      f"It is cut from {name}, which {len(users)} screens share, so new "
                      f"corners show on all of them." if len(users) > 1
                      else f"It is cut from {name}, which no other screen uses.")]
        if edited:
            x1, y1, x2, y2 = info["game_rect"]
            sentences.append((2, f"The game's corners are {x1}, {y1} and {x2}, {y2}."))
        replaced = (getattr(self.state, "texture_edits", {}) or {}).get(info["texture"])
        game_size = lp.tex_size(self._game_dir() / info["texture"]) if replaced else None
        if replaced and game_size:
            sentences.append((5, f"Your mod replaces its sheet, so corners count in the game "
                                 f"sheet's pixels, {game_size[0]} by {game_size[1]}."))
        return sentences

    @staticmethod
    def _kind_sentences(box) -> list:
        """What kind of box it is, where that changes what you see."""
        sentences = []
        if box.kind == "Reference" and box.reference_file:
            source = uib.layout_path_for(box.reference_file).rsplit("/", 1)[-1]
            sentences.append((7, f"Its colour and opacity also apply to what is inside "
                                 f"it, which is edited on {source}."))
        elif box.kind in ("Layer", "Reference"):
            sentences.append((7, "Its colour and opacity also apply to what is inside it."))
        elif box.kind == "Collision":
            sentences.append((7, "A click area is never drawn, so its colour and opacity "
                                 "show nothing."))
        if box.kind == "Reference" and not box.reference_file and not box.reference_name:
            sentences.append((7, "The game fills this in while it runs, so the picture "
                                 "shows nothing here."))
        if box.kind == "Text":
            sentences.append((7, "The picture shows its name where the game writes words."))
        return sentences

    # -- the part a picture is cut from ------------------------------------------

    def _carried_part_list(self, rel: str) -> bool:
        """Whether the opened mod carries its own copy of this part list whole."""
        carried = getattr(self.state, "other_file_replacements", {}) or {}
        return rel.lower() in {c.lower() for c in carried}

    def _part_list_users(self) -> dict:
        if self._users is None:
            game = self._game_dir()
            self._users = lt.part_list_users(game) if game is not None else {}
        return self._users

    def _part_info(self, box):
        """
        What a picture box is cut from, or None for a box with no picture:
        `{"list", "index", "name", "count", "texture", "rect" (this mod's
        corners), "game_rect", "why"}` - `why` saying, when it says anything,
        why the corners can't be edited here.
        """
        if box is None or not box.textures or not box.textures[0].uri:
            return None
        ref = box.textures[0]
        info = {"list": ref.part_list_path, "index": ref.part, "name": "", "count": 0,
                "texture": "", "rect": None, "game_rect": None, "why": ""}
        try:
            data = (self._game_dir() / info["list"]).read_bytes()
            game_parts = uib.read_part_list(data)
            mine = uib.read_part_list(uib.apply_part_edits(
                data, self.state.utexpt_edits.get(info["list"], {}))[0])
        except (OSError, TypeError, uib.UibError):
            info["why"] = "Its part list isn't in your unpacked game."
            return info
        info["texture"], info["count"] = game_parts.texture_path, len(game_parts.parts) - 1
        if not 0 <= ref.part < len(game_parts.parts):
            info["why"] = "It names a part its part list doesn't have."
            return info
        info["name"] = game_parts.parts[ref.part].name
        info["rect"] = list(mine.parts[ref.part].rect)
        info["game_rect"] = list(game_parts.parts[ref.part].rect)
        if ref.part == 0:
            # Part 0 is out of date in 4 of the tavern's 9 part lists, and
            # the game shows those pictures whole anyway.
            info["why"] = ("It shows its whole sheet, part 0, which isn't offered as the "
                           "game doesn't use its numbers as they are.")
        elif self._carried_part_list(info["list"]):
            info["why"] = ("Your mod has its own copy of this part list, so its parts "
                           "can't be edited here.")
        elif self.read_only:
            info["why"] = "Its part can't be edited on a screen your mod carries whole."
        return info

    def _show_part(self, box) -> None:
        """The part row, and whether the sheet can be shown, for the picked box."""
        info = self._part_info(box)
        self.part_row.setVisible(info is not None)
        self.sheet_button.setEnabled(bool(info and info["texture"]))
        if not self.sheet_button.isEnabled() and self.sheet_button.isChecked():
            self.sheet_button.setChecked(False)           # back to the screen
        if info is None:
            return
        stored = self.state.utexpt_edits.get(info["list"], {}).get(info["index"])
        self.part_row.part_name.setText(
            f"{info['name']}, part {info['index']} of {info['count']}" if info["name"] else "")
        if info["rect"] is not None:
            self.part_row.load(stored["rect"] if stored else info["rect"], stored is not None)
        self.part_row.setEnabled(info["rect"] is not None and not info["why"])
        if self.sheet_button.isChecked() and info["list"] != self._drawn_sheet:
            self.request_draw()

    def _on_part_edited(self) -> None:
        info = self._part_info(self._box(self.selected_key))
        if info is None or info["why"]:
            return
        parts = self.state.utexpt_edits.setdefault(info["list"], {})
        if self.part_row.included:
            parts[info["index"]] = {"name": info["name"], "rect": self.part_row.value()}
        else:
            parts.pop(info["index"], None)
        if not parts:
            self.state.utexpt_edits.pop(info["list"], None)
        self._after_change()

    def _on_sheet_toggled(self, on) -> None:
        self.sheet_button.setText("Back to the screen" if on else "Show its texture sheet")
        self.canvas.set_selected(self._canvas_key())
        self.request_draw()

    def _sheet_to_draw(self):
        """The part list whose sheet to show instead of the screen, or None."""
        if not self.sheet_button.isChecked():
            return None
        info = self._part_info(self._box(self.selected_key))
        return info["list"] if info and info["texture"] else None

    def _canvas_key(self) -> str:
        """What the picture outlines: the picked box, or on a sheet its part."""
        if self._drawn_sheet:
            info = self._part_info(self._box(self.selected_key))
            if info and info["list"] == self._drawn_sheet:
                return f"part/{info['index']}"
            return ""
        return self.selected_key

    # -- right-click: open a box's texture in Textures ---------------------------

    def _canvas_menu(self, point) -> None:
        """
        The box under the pointer is picked first, as a left click would -
        acting on a box you right-clicked while another is picked is how the
        wrong one gets changed - then its menu opens there.
        """
        if self.canvas.image is None:
            return
        key = self.canvas.box_at(self.canvas.to_canvas(QPointF(point)))
        if not key or not self.select_box(key):
            return
        self.box_menu(key).exec(self.canvas.mapToGlobal(point))

    def _list_menu(self, point) -> None:
        item = self.box_list.itemAt(point)
        if item is None:
            return
        key = item.data(0, _KEY_ROLE)
        component = item.data(0, _COMPONENT_ROLE)
        if not key and not component:
            return
        self.box_list.setCurrentItem(item)
        self.box_menu(key or None, component=None if key else component).exec(
            self.box_list.viewport().mapToGlobal(point))

    def texture_targets(self, key=None, component=None):
        """What box `key` - or the whole piece `component` - draws from."""
        game = self._game_dir()
        if game is None or self.layout_obj is None:
            return lt.TextureTargets(nothing="no screen is open")
        return lt.targets_for(game, self.layout_obj, key, component)

    def box_menu(self, key=None, component=None):
        """
        The right-click menu for a box, or a whole piece of the screen.

        - A box drawn from one texture: that texture, landed on in Textures.
          When the folder also holds textures named like it but for their
          number, the folder is offered beside it: the game swaps such
          pictures while it runs (measured on the tavern, whose layout names
          `ui_bar_bg_00` while the game shows `bg_00`, `bg_01` or `bg_02` by
          chapter), so the one the file names may not be the one you see.
        - A group or piece drawing from several textures: their folder when
          they share one (each folder when they don't), and every texture
          one by one beneath.
        - A box with no picture - text, a colour box, a click area, a slot
          the game fills in - has the entry greyed out, saying why.
        """
        menu = QMenu(self)
        targets = self.texture_targets(key, component)
        game = self._game_dir()
        sheets = targets.sheets

        def jump(path):
            return lambda _checked=False, p=path: self.jump_to_texture.emit(p)

        if len(sheets) == 1:
            sheet = sheets[0]
            menu.addAction(f"Open {sheet.rsplit('/', 1)[-1]} in Textures").triggered.connect(
                jump(sheet))
            siblings = lt.swapped_siblings(game, sheet) if game is not None else []
            if siblings:
                if len(siblings) <= 3:
                    others = " or ".join(siblings)
                else:
                    others = f"any of {len(siblings)} others named like it"
                menu.addAction(f"Open its folder in Textures as the game may show {others} "
                               f"here instead").triggered.connect(jump(lt.folder_of(sheet)))
        elif sheets:
            folders = {}
            for sheet in sheets:
                folders.setdefault(lt.folder_of(sheet), []).append(sheet)
            if len(folders) == 1:
                folder = next(iter(folders))
                menu.addAction(f"Open their folder in Textures as its pictures come from "
                               f"{len(sheets)} textures there").triggered.connect(jump(folder))
            else:
                sub = menu.addMenu(f"Open a folder in Textures as its pictures come from "
                                   f"{len(sheets)} textures in {len(folders)} folders")
                for folder, inside in sorted(folders.items()):
                    sub.addAction(f"{folder}  ({len(inside)})").triggered.connect(jump(folder))
            sub = menu.addMenu("Open one of its textures in Textures")
            for sheet in sheets:
                sub.addAction(sheet.rsplit("/", 1)[-1] if len(folders) == 1 else sheet) \
                    .triggered.connect(jump(sheet))
        else:
            menu.addAction(f"No texture to open as {targets.nothing}").setEnabled(False)
        for missing in targets.absent[:3]:
            menu.addAction(f"Not in your unpacked game: {missing}").setEnabled(False)
        return menu

    # -- editing -------------------------------------------------------------------

    def _on_box_dragged(self, key: str, dx: int, dy: int) -> None:
        """
        A box dragged on the picture: its position moved by (dx, dy), done
        exactly as typing it would be - through the Position row, so the row
        ticks, the edit stored is the same, and its animation keys move with
        it.
        """
        if self.canvas.file != self.current_rel or not self.origin_row.isEnabled():
            # The picture still shows the screen before, while this one
            # draws; or the box can't be moved here (a carried screen).
            return
        box = self._box(key)
        self.origin_row.set_value([box.origin[0] + dx, box.origin[1] + dy])

    # -- animation keys ------------------------------------------------------------

    def _keys_of(self, box) -> list:
        """The keys setting `box`, in its component's animations, in file order."""
        if box is None or self.layout_obj is None:
            return []
        component = self.layout_obj.components.get(box.component)
        return [k for k in component.keys if k.target == box.name] if component else []

    def _key_edits(self) -> dict:
        return self.state.uib_edits.get(self.current_rel, {}).get(uib.ANIMATION_KEYS) or {}

    def _fill_keys(self, box) -> None:
        """The picked box's keys, grouped by animation, in the Animation tab."""
        keys = self._keys_of(box)
        chosen = self.keys_tree.currentItem()
        chosen_id = chosen.data(0, _KEY_ID_ROLE) if chosen is not None else None
        self.keys_tree.blockSignals(True)
        self.keys_tree.clear()
        edited = self._key_edits()
        groups, select = {}, None
        for key in keys:
            group = groups.get(key.timeline)
            if group is None:
                group = groups[key.timeline] = QTreeWidgetItem([key.timeline, "", ""])
                self.keys_tree.addTopLevelItem(group)
            if key.kind in uib.EDITABLE_KEY_KINDS:
                words = KEY_WORDS[key.kind]
            else:
                words = f"Not read here ({key.kind})"
            if key.kind in uib.KEY_VALUE_FORMATS:
                value = ", ".join(shortest_scale_text(v) if isinstance(v, float) else str(v)
                                  for v in key.values)
            elif key.kind == uib.KEY_CHILD_TIMELINE and key.values:
                value = key.values[0]
            else:
                value = ""
            # A moment (every value key in the game) by its frame; a span
            # (a piece's animation playing) by where it starts and ends.
            frames = str(key.frame) if not key.frames else f"{key.frame}-{key.frame + key.frames}"
            item = QTreeWidgetItem([words, frames, value])
            item.setData(0, _KEY_ID_ROLE, key.id)
            item.setToolTip(0, key.id)
            # Marked first: unmarking clears the text colour, and a key of a
            # kind not read here is greyed after that, or it never shows grey.
            actions.mark_edited(item, key.id in edited)
            if key.kind not in uib.EDITABLE_KEY_KINDS:
                item.setForeground(0, self.palette().placeholderText())
            group.addChild(item)
            if key.id == chosen_id:
                select = item
        self.keys_tree.expandAll()
        self.keys_tree.blockSignals(False)
        self.side_tabs.setTabText(1, f"Animation ({len(keys)})" if keys else "Animation")
        if select is not None:
            self.keys_tree.setCurrentItem(select)
        else:
            self._show_key(None)

    def _on_key_item(self, current, _previous) -> None:
        key_id = current.data(0, _KEY_ID_ROLE) if current is not None else None
        self._show_key(key_id)
        # The picture shows the end of an animation: this key's, where the
        # screen has one of that name.
        key = self.layout_obj.keys.get(key_id) if (key_id and self.layout_obj) else None
        if key is not None and key.timeline != self.timeline.currentText() \
                and self.timeline.findText(key.timeline) >= 0:
            self.timeline.setCurrentText(key.timeline)

    def select_key(self, key_id: str) -> bool:
        """Picks one of the picked box's keys by its id - for the suites, and a jump."""
        for i in range(self.keys_tree.topLevelItemCount()):
            group = self.keys_tree.topLevelItem(i)
            for j in range(group.childCount()):
                if group.child(j).data(0, _KEY_ID_ROLE) == key_id:
                    self.keys_tree.setCurrentItem(group.child(j))
                    return True
        return False

    def _show_key(self, key_id) -> None:
        key = self.layout_obj.keys.get(key_id) if (key_id and self.layout_obj) else None
        if key is None:
            self.key_group.setTitle("Click a key")
            self.key_editor.setEnabled(False)
            return
        self.key_group.setTitle(f"{key.timeline}, key {key.index}, "
                                f"{KEY_WORDS.get(key.kind, 'not read here').lower()}")
        stored = self._key_edits().get(key.id)
        if stored:
            # As typed: a refused edit (out of order, say) is not written.
            key = dataclasses.replace(
                key, frame=stored.get("frame", key.frame), frames=stored.get("frames", key.frames),
                easing=stored.get("easing", key.easing),
                values=tuple(stored.get("value", key.values)))
        self.key_editor.load(key, bool(stored))
        self.key_editor.setEnabled(key.kind in uib.EDITABLE_KEY_KINDS and not self.read_only)
        self.key_note.setText(KEY_NOTE + (" " + MOMENT_NOTE if key.kind in uib.KEY_VALUE_FORMATS
                                          else ""))

    def _on_key_edited(self) -> None:
        item = self.keys_tree.currentItem()
        key_id = item.data(0, _KEY_ID_ROLE) if item is not None else None
        key = self.game_layout.keys.get(key_id) if (key_id and self.game_layout) else None
        if key is None or self.read_only or key.kind not in uib.EDITABLE_KEY_KINDS:
            return
        screen = self.state.uib_edits.setdefault(self.current_rel, {})
        keys = screen.setdefault(uib.ANIMATION_KEYS, {})
        if self.key_editor.included:
            keys[key_id] = self.key_editor.edit(key)
        else:
            keys.pop(key_id, None)
        if not keys:
            screen.pop(uib.ANIMATION_KEYS, None)
        if not screen:
            self.state.uib_edits.pop(self.current_rel, None)
        self._after_change()

    def _on_field_edited(self, field_name: str) -> None:
        box = self._box(self.selected_key)
        game_box = self.game_layout.boxes.get(self.selected_key) if self.game_layout else None
        if box is None or game_box is None or self.read_only:
            return
        row = self.rows[field_name]
        screen = self.state.uib_edits.setdefault(self.current_rel, {})
        fields = screen.setdefault(self.selected_key, {})
        if row.included:
            fields[field_name] = row.value()
        else:
            # The row shows the game's value again when `_after_change`
            # reloads the box from the store, which no longer has this field.
            fields.pop(field_name, None)
        if not fields:
            screen.pop(self.selected_key, None)
        if not screen:
            self.state.uib_edits.pop(self.current_rel, None)
        self._after_change()

    def _say_problems(self, problems: list) -> None:
        """
        An edit the file can't take, said as soon as it is made - not first
        at export. The edit stays stored, as typed, so it can be put right.
        """
        if problems:
            more = f" (and {len(problems) - 1} more)" if len(problems) > 1 else ""
            self.status.say(f"{problems[0]}{more}", "danger")
            self._problems_said = True
        elif getattr(self, "_problems_said", False):
            self.status.clear()
            self._problems_said = False

    def _after_change(self) -> None:
        rel, key = self.current_rel, self.selected_key
        data, problems = uib.apply_edits(self.game_layout.data,
                                         self.state.uib_edits.get(rel, {}))
        info = self._part_info(self._box(key))
        if info is not None and info["list"] in self.state.utexpt_edits:
            try:
                problems += uib.apply_part_edits((self._game_dir() / info["list"]).read_bytes(),
                                                 self.state.utexpt_edits[info["list"]])[1]
            except (OSError, uib.UibError):
                pass
        self._say_problems(problems)
        self.layout_obj = uib.Layout(data)
        self.model.set_edits(self._marked(), rel)
        self._update_counter()
        item = self._item_for(key)
        if item is not None:
            actions.mark_edited(item, self._box_edited(key))
        self._show_box(key)
        self.edits_changed.emit()
        self.request_draw()

    # -- drawing -------------------------------------------------------------------

    def _component_to_draw(self):
        """
        None for the whole screen; a component's name when the selected box
        is in a piece the screen itself never places. Shared files such as
        `ffto_common_window` are mostly such pieces, and a box you cannot
        see cannot be placed.
        """
        box = self._box(self.selected_key)
        if box is None:
            return self._drawn_component
        return None if box.component in self._placed else box.component

    def _redraw_if_component_changed(self) -> None:
        wanted = self._component_to_draw()
        if wanted != self._drawn_component:
            self.request_draw(component=wanted)

    def request_draw(self, component="current") -> None:
        # No screen, no drawing: a screen that failed to load has none.
        if not self.current_rel or self._game_dir() is None or self.layout_obj is None:
            return
        if component == "current":
            component = self._component_to_draw()
        self._draw_token += 1
        sheet = self._sheet_to_draw()
        self._pending_draw = (self._draw_token, self.current_rel,
                              self.timeline.currentText() or "Show", component, sheet)
        # The drawing already on its way is for something no longer wanted.
        # It stops at its next box instead of finishing the whole
        # screen first, so the one wanted now starts sooner.
        if self._running_draw is not None:
            self._running_draw.cancel()
            self.draws_cancelled += 1
            self._running_draw = None
        self.canvas.set_message("Drawing its texture sheet..." if sheet
                                else "Drawing the screen...")
        self._redraw_timer.start()

    def _decoders(self):
        cli = getattr(self.state, "ff16tools_cli_path", None)
        cache = paths.local_data_dir() / "texture_preview_cache"
        decode = self.decode or lp.default_decoder(cli, cache)
        replacement = self.decode_replacement or self.decode or \
            lp.default_replacement_decoder(cli, cache)
        return decode, replacement

    def _worker(self):
        token, rel, timeline, component, sheet = self._pending_draw
        decode, replacement = self._decoders()
        overrides = self._carried_layouts()
        worker = lp.DrawWorker(token, self._game_dir(), rel, self.state.uib_edits,
                               getattr(self.state, "texture_edits", {}), timeline,
                               component, decode, replacement, overrides,
                               part_edits=self.state.utexpt_edits, sheet=sheet)
        return worker

    def _start_pending_draw(self) -> None:
        if self._pending_draw is None or self._draw_busy:
            return
        worker = self._worker()
        self._pending_draw = None
        self._draw_busy = True
        self.draws_started += 1
        self._running_draw = worker
        run_in_thread(worker, on_finished=self._drawn, on_failed=self._draw_failed)

    def flush_pending_draw(self) -> None:
        """Draws now, on this thread. For the suites; the page itself uses the worker."""
        self._redraw_timer.stop()
        if self._pending_draw is None:
            return
        worker = self._worker()
        self._pending_draw = None
        self.draws_started += 1
        try:
            payload = worker.run()
        except Exception as exc:                               # noqa: BLE001
            # As the worker thread reports it, so the suites see what a
            # person would.
            self._draw_failed(str(exc) or exc.__class__.__name__)
            return
        self._drawn(payload, from_thread=False)

    def _draw_finished(self) -> None:
        self._draw_busy = False
        self._running_draw = None
        if self._pending_draw is not None:
            QTimer.singleShot(0, self._start_pending_draw)

    def _drawn(self, payload: dict, from_thread: bool = True) -> None:
        if from_thread:
            self._draw_finished()
        if payload.get("token") != self._draw_token:
            return
        # A drawing that was stopped never gets here: it is only ever stopped
        # for a newer one, so its token is already out of date.
        result = payload["result"]
        self.last_result = result
        sheet = payload.get("sheet")
        self._drawn_sheet = sheet
        # A sheet has its parts outlined, and nothing on it moves.
        self.canvas.outline_all = bool(sheet)
        self.canvas.draggable = not sheet and not self.read_only
        self.timeline.setEnabled(not sheet and self.timeline.count() > 0)
        if sheet:
            self.canvas.set_drawing(result.image, result.boxes, sheet)
        else:
            root = self.layout_obj.root if self.layout_obj is not None else None
            self._drawn_component = None if (root is not None and result.component == root.name) \
                else result.component
            self.canvas.set_drawing(result.image, result.boxes, self.current_rel)
        self.canvas.set_selected(self._canvas_key())
        if result.missing and not self.read_only:
            count = len(result.missing)
            self.status.say(f"{count} picture{'s' if count != 1 else ''} or "
                            f"piece{'s' if count != 1 else ''} couldn't be "
                            f"loaded and {'are' if count != 1 else 'is'} left out.",
                            "muted")

    def _draw_failed(self, message: str) -> None:
        self._draw_finished()
        self.canvas.clear()
        self.status.say(f"The screen could not be drawn: {message}", "danger")
