"""
The per-field opt-in row: the core interaction of the whole tool.

Every editable field carries a checkbox, and **only ticked fields are
written into the mod**. That is what stops two mods conflicting: a mod that
changes a job's Move value says nothing about its HP growth, so another mod
is free to change that instead. Nothing else in the interface matters as
much as this behaving exactly as it always has.

Three behaviours here are easy to lose in a rewrite because none of them is
obvious from looking at the screen:

- **Typing a value ticks the box.** Nobody wants to type 8, then hunt for a
  checkbox to confirm they meant it. Four lines in a trace callback in the
  Tkinter version, and the difference between the interaction feeling
  natural and feeling bureaucratic.
- **Loading a record must not tick anything.** The same value arrives
  programmatically when you click a job, and if that counted as an edit,
  merely browsing would fill a mod with every field you happened to look at.
  Guarded by a suppression flag, not by hoping.
- **Unticking discards the value.** The row keeps showing the game's
  original number, so unticking reads as "leave this alone" rather than
  "set it to whatever was in the box".

Field notes state their confidence tier - confirmed, inferred, or genuinely
unknown - and the two view toggles hide notes and unknown fields. That
honesty is the project's convention and is carried through here rather than
tidied away.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QPlainTextEdit, QPushButton, QSizePolicy, QSpinBox,
    QToolButton, QVBoxLayout, QWidget,
)

from .field_widths import (
    LONG_TEXT_ROWS, is_long_text, long_text_height, short_text_width,
)


class LongTextEdit(QPlainTextEdit):
    """
    A multi-line box that answers to `QLineEdit`'s names, and sizes itself.

    `TextFieldRow.value` is reached into from pages and from three test
    suites - `.text()`, `.setText()`, `.cursorPosition()` - and which kind
    of box a given column gets is decided inside the row from the column's
    name. If the two kinds had different APIs, every caller would have to
    learn that distinction and would get it wrong for exactly the columns
    nobody thought about. Same rule as the widgets themselves: a new one
    matches the one beside it.

    `setTabChangesFocus` because this sits in a form. Tab moving focus is
    what every other field on the page does, and a text area that swallows
    it strands keyboard users in the middle of a job's stats.

    **The height follows the text at the width it is actually drawn at**,
    between `min_rows` and `max_rows`. A fixed row count cannot be right,
    because how many lines a description takes depends on how wide the box
    is, and that changes with the window:

        a 261-character description   1100px wide -> 3 lines
                                      1420px      -> 2
                                      2060px      -> 1

    Three was chosen from the English worst case and clipped German. Five
    was then chosen from the German worst case at the 1100px minimum, and
    left three empty lines under a two-line description on a maximised
    1080p monitor - correct at the bottom of the range and wasteful at the
    top, which is what any single number does here.

    The floor of two keeps the box visibly a text area rather than
    something that looks like a one-line field. The ceiling stops a pasted
    essay from pushing the rest of the form off the page; past it the box
    scrolls, which is the normal behaviour of a text area that is full.
    """

    def __init__(self, parent=None, min_rows: int = 2, max_rows: int = 6):
        super().__init__(parent)
        self._min_rows = max(1, int(min_rows))
        self._max_rows = max(self._min_rows, int(max_rows))
        self._sizing = False
        self.textChanged.connect(self._resize_to_content)

    def text(self) -> str:
        return self.toPlainText()

    def setText(self, value: str) -> None:                    # noqa: N802
        self.setPlainText(value)

    def cursorPosition(self) -> int:                          # noqa: N802
        return self.textCursor().position()

    def rows_shown(self) -> int:
        """How many lines of text the box is currently tall enough for."""
        spacing = max(1, self.fontMetrics().lineSpacing())
        return max(1, self.viewport().height() // spacing)

    def _resize_to_content(self) -> None:
        """Set the height to the wrapped line count, clamped."""
        # `_sizing` because setting the height triggers a resize, which asks
        # to be sized again. Without the guard that is an infinite loop on
        # the first keystroke.
        if self._sizing:
            return
        document = self.document()
        # The document has to be told the width it is wrapping at, or it
        # reports the unwrapped single-line height and every box collapses
        # to the floor - which looks exactly like the feature not working.
        document.setTextWidth(max(1, self.viewport().width()))
        lines = int(document.size().height())
        lines = max(self._min_rows, min(self._max_rows, lines))
        target = long_text_height(self.fontMetrics(), lines)
        if target == self.height():
            return
        self._sizing = True
        try:
            self.setFixedHeight(target)
            self.updateGeometry()      # the column form re-lays out
        finally:
            self._sizing = False

    def resizeEvent(self, event):                             # noqa: N802
        super().resizeEvent(event)
        # A narrower window wraps the same text onto more lines, so the
        # height has to be recomputed on resize and not only on edit.
        self._resize_to_content()

    def setCursorPosition(self, position: int) -> None:       # noqa: N802
        cursor = self.textCursor()
        cursor.setPosition(max(0, int(position)))
        self.setTextCursor(cursor)
        # Scroll back as well as move the caret. `setPlainText` leaves the
        # viewport wherever the caret ended up, and moving the caret alone
        # left a 261-character job description still showing its last line -
        # the exact fault `setCursorPosition(0)` was added to fix on the
        # single-line box.
        self.moveCursor(QTextCursor.Start)
        self.ensureCursorVisible()


class FieldNoteLabel(QLabel):
    """
    A field note that ends in an ellipsis when it does not fit.

    The note is deliberately unwrapped and horizontally `Ignored`, for a
    measured reason recorded on `NumericFieldRow`: a wrapped note took a
    quarter of the row at the 1100px minimum and ran to five lines, so five
    text fields were taller than the twelve stat rows under them, and a long
    note could widen the whole form.

    What that left was a note cut off mid-word with nothing to say it had
    been - on Job Commands, "A second description. Only one row uses it in m".
    A reader cannot tell that from a note whose author simply stopped typing.

    Eliding keeps the constraint and fixes the tell: the text is shortened to
    the width actually available and marked with an ellipsis, and the full
    text stays in the tooltip, where it already was. Elided on every resize,
    because the width this gets depends on the window and on what the value
    beside it is using.
    """

    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        self._full_text = text or ""
        self.setWordWrap(False)
        super().setText(self._full_text)

    def setText(self, text: str) -> None:                     # noqa: N802
        self._full_text = text or ""
        self._elide()

    def text(self) -> str:
        """
        The note, not the abbreviation of it currently on screen.

        Overridden deliberately. Eliding is a DISPLAY detail, and a caller
        asking a label for its text wants the note - three suites read this
        to check what a field says, and against the inherited `text()` they
        got whatever happened to fit the window they were run at, which is
        both wrong and intermittent. `painted_text()` is there for the one
        caller that really does want the visible string.
        """
        return self._full_text

    def painted_text(self) -> str:
        """What is actually drawn, ellipsis and all."""
        return super().text()

    def full_text(self) -> str:
        """The unabridged note. Kept as an alias; `text()` now agrees."""
        return self._full_text

    def is_elided(self) -> bool:
        return super().text() != self._full_text

    def _elide(self) -> None:
        if not self._full_text:
            super().setText("")
            return
        # Wrapping and eliding are two answers to the same question, and
        # running both means the elide wins silently: it rewrites the text
        # to one line's worth, so `setWordWrap(True)` appears to do nothing
        # and the note stays a single truncated line. Whichever the caller
        # asked for, only that one runs.
        if self.wordWrap():
            super().setText(self._full_text)
            return
        metrics = self.fontMetrics()
        available = max(0, self.width())
        # With no width yet - during construction, before the first layout -
        # show the whole thing. Eliding against a width of zero would set
        # every note to a bare ellipsis and the first paint would flash.
        if available <= 0:
            super().setText(self._full_text)
            return
        super().setText(metrics.elidedText(self._full_text, Qt.ElideRight,
                                           available))

    def resizeEvent(self, event):                             # noqa: N802
        super().resizeEvent(event)
        self._elide()


class NumericFieldRow(QWidget):
    """
    `[x] Label  [ 12 ]  help text`

    Emits `edited` whenever the user changes something, and never when
    `load()` does.
    """

    edited = Signal()

    def __init__(self, field_name: str, label: str, minimum: int, maximum: int,
                 note: str = "", unknown: bool = False, parent=None):
        super().__init__(parent)
        self.field_name = field_name
        self.is_unknown = unknown
        self._loading = False

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 1, 0, 1)
        row.setSpacing(8)

        self.include = QCheckBox()
        self.include.setToolTip(
            "Tick to write this field into your mod. Unticked fields are "
            "left alone, so other mods can change them.")
        self.include.toggled.connect(self._on_include_toggled)
        row.addWidget(self.include)

        # Fixed, not minimum. With a minimum the label absorbed leftover
        # space on any row whose note was empty, which pushed the spin box
        # right and made those rows look like a different control entirely -
        # a checkbox, a centred label, and the number off at the far edge.
        self.label = QLabel(label)
        self.label.setFixedWidth(200)
        row.addWidget(self.label)

        self.value = QSpinBox()
        self.value.setRange(minimum, maximum)
        # Compact, matching the Tkinter field. The native spin buttons take
        # about 16px off the right of this.
        self.value.setFixedWidth(84)
        # Left, like the Tkinter field. This was AlignRight, which put the
        # digits hard against the up/down buttons - and with the buttons now
        # drawn properly, right-aligned numbers read as if they are touching
        # them. One call, not two: an earlier fix added a left-align above
        # the range and the original right-align five lines below quietly
        # won.
        self.value.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        # `valueChanged` fires for programmatic changes too, which is why
        # `load()` sets the suppression flag rather than disconnecting.
        self.value.valueChanged.connect(self._on_value_changed)
        row.addWidget(self.value)

        # The note is ALWAYS in the layout, even when it is empty. Hiding it
        # removed it from the row, and every row without a note then laid
        # itself out differently from every row with one.
        #
        # Ignored horizontally so a long note cannot widen the form. Left to
        # ask for its full width, one 70-character note put a horizontal
        # scroll bar under the whole editor.
        self._note_text = note
        self.note = FieldNoteLabel(note)
        self.note.setProperty("role", "muted")
        self.note.setWordWrap(False)
        self.note.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        # Clipped rather than elided at narrow widths, so the full text goes
        # in a tooltip. These notes carry real information - "131/132 are
        # special (innate Fly/Float-tier jump)" is the sort of thing someone
        # needs before typing a number - and losing the end of it silently
        # is worse than not showing it at all.
        self.note.setToolTip(note)
        row.addWidget(self.note, 1)

        # Read by the two view toggles. Properties rather than a Python
        # attribute so a stylesheet can reach them too.
        self.setProperty("fieldRow", True)
        self.setProperty("unknownField", bool(unknown))

    # -- state --------------------------------------------------------------

    def set_note(self, text: str) -> None:
        """
        Replaces the note beside the field, tooltip and all.

        For notes that depend on the value rather than on the field - the
        item a Poaching id points at changes as the number is typed. Kept
        here rather than done by the caller reaching into `self.note`, so
        the tooltip cannot drift away from the visible text; the note is
        clipped rather than elided, and the tooltip is where the rest of it
        lives.
        """
        self._note_text = text
        self.note.setText(text)
        self.note.setToolTip(text)

    @property
    def included(self) -> bool:
        return self.include.isChecked()

    def get_value_str(self) -> str:
        return str(self.value.value())

    def load(self, raw_value, included: bool) -> None:
        """
        Shows a value without it counting as an edit.

        Called when a record is selected. `included` is True only when this
        field is already in the mod.
        """
        self._loading = True
        try:
            try:
                self.value.setValue(int(str(raw_value).strip() or 0))
            except (TypeError, ValueError):
                self.value.setValue(self.value.minimum())
            self.include.setChecked(bool(included))
        finally:
            self._loading = False

    # -- interaction --------------------------------------------------------

    def _on_value_changed(self, _value) -> None:
        if self._loading:
            return
        # Typing a number means you want it. Ticking the box yourself is
        # busywork the tool can do for you.
        if not self.include.isChecked():
            self.include.setChecked(True)     # emits edited via the toggle
            return
        self.edited.emit()

    def _on_include_toggled(self, _on) -> None:
        if self._loading:
            return
        self.edited.emit()

    # -- view toggles -------------------------------------------------------

    def apply_display(self, hide_notes: bool, hide_unknown: bool) -> None:
        """
        The two view toggles.

        The Tkinter version walked the whole widget tree, unpacking matching
        widgets and stashing their geometry so it could be restored. Qt
        layouts reflow on their own, so this is a visibility change and
        nothing else - there is no position to put back.
        """
        # Emptied rather than hidden, so every row keeps the same shape
        # whether or not it has a note and whether or not notes are on.
        self.note.setText("" if hide_notes else self._note_text)
        self.note.setToolTip("" if hide_notes else self._note_text)
        self.setVisible(not (hide_unknown and self.is_unknown))


class TextFieldRow(QWidget):
    """
    `[x] Label [ text ]  help text` - the same opt-in rule, for a string.

    Clearing the box is an edit, not an absence. Blanking a name is how a
    mod hides a UI element, and the engine treats an empty string as a
    deliberate value; a row that quietly dropped it would silently change
    what the mod does.

    It lived in `pages/poaching.py` and was imported from there by
    Abilities, Items and Encounters - three pages reaching into a fourth
    page for a widget none of them has anything to do with. It is here with
    every other row now, and `poaching` re-exports the name so nothing that
    already imports it has to change.

    `note` and `unknown` behave exactly as they do on `NumericFieldRow`, so
    a text field whose meaning is unconfirmed hides with the Hide-unknown
    toggle like any other. Before, this row ignored both: it hardcoded
    `is_unknown = False` and its `apply_display` did nothing, so an unknown
    STRING column could not be hidden while an unknown NUMBER could.

    **The box is sized to what the column holds.** One `QLineEdit` used to
    serve every string, so a nine-character job name got a box the full
    width of a 1440p monitor and a 261-character description got the same
    single line. Both are false signifiers: the size of a field tells a
    person what to type into it whether or not anyone meant it to.
    `field_widths.py` carries the counts this is based on and the reasoning;
    the short case is capped at 28 characters and the long case becomes a
    real text area.

    That second half is also a correctness fix. 142 of 258 item
    descriptions contain a newline the game uses, and a line edit can
    neither draw one nor let you type one - Return in a `QLineEdit` does
    not insert a character - so those descriptions could be read back but
    never authored.
    """

    edited = Signal()

    def __init__(self, field_name: str, label: str, note: str = "",
                 unknown: bool = False, parent=None, long: bool | None = None,
                 multiline: bool = False, max_value_width: int = 0,
                 rows: int = 0, stacked: bool = False):
        super().__init__(parent)
        self.field_name = field_name
        self.is_unknown = unknown
        self._note_text = note
        self._loading = False
        # `multiline` is a ROLLOUT GATE, and it is temporary.
        #
        # A three-line description is taller than a one-line one, and that
        # height is only affordable on a page whose rows have been reflowed
        # into columns to pay it back. Measured, not assumed: switching
        # every page at once took Job Commands from 20 visible fields to 18
        # and its scroll from 51px to 132px, because it got the cost of the
        # taller box without the benefit of the columns. Jobs, which has
        # both, went from 18 visible to 21 and from 341px of scroll to 66.
        #
        # So a page opts in when it adopts `ColumnFormBody`, and this
        # argument disappears when the last one has. The WIDTH half of the
        # sizing is not gated - it costs no height, and it makes this row
        # match the capped spin box and dropdown beside it instead of being
        # the only control on the page that stretched to the window edge.
        self._long_column = (is_long_text(field_name, label) if long is None
                             else bool(long))
        self.is_long = self._long_column and multiline

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 1, 0, 1)
        row.setSpacing(8)

        self.include = QCheckBox()
        self.include.setToolTip(
            "Tick to write this field into your mod. Unticked fields are "
            "left alone, so other mods can change them.")
        self.include.toggled.connect(self._on_include)
        # Top, not centred. Against a three-line text area a vertically
        # centred checkbox floats beside the middle line and stops reading
        # as belonging to the row at all.
        row.addWidget(self.include, 0, Qt.AlignTop)

        self.label = QLabel(label)
        self.label.setFixedWidth(200)
        row.addWidget(self.label, 0, Qt.AlignTop)

        if self.is_long:
            # `rows` is now a CEILING, not a fixed height. The box sizes
            # itself to what it holds at the width it is drawn at - see
            # LongTextEdit - so a two-line description on a maximised 1080p
            # window is a two-line box, and the same text at the 1100px
            # minimum, where it wraps to five, is a five-line box.
            #
            # This replaced a fixed `rows` count that could only be right at
            # one window size. Three was picked from the longest English
            # description and clipped German; five was picked from the
            # longest German at the 1100px minimum and left three empty
            # lines under an English description on a 1080p monitor.
            self.value = LongTextEdit(min_rows=2,
                                      max_rows=rows or LONG_TEXT_ROWS)
            self.value.setTabChangesFocus(True)
            self.value.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        else:
            self.value = QLineEdit()
            if max_value_width:
                # A caller capping the box has to cap it THROUGH the row,
                # not by reaching into `row.value` afterwards. All Game
                # Data did the latter, and the row went on believing its
                # value could expand - so the box could not take the slack
                # and QBoxLayout distributed it instead, pushing the whole
                # row 550px right. Its label sat at x=902 while the three
                # numeric rows above and below it sat at x=352. Pre-dates
                # the column work; found by looking at a screenshot,
                # measured rather than eyeballed.
                self.value.setMaximumWidth(int(max_value_width))
            if not self._long_column and not max_value_width:
                # Capped, not fixed: it still shrinks at the 1100 minimum,
                # it just stops growing once it can show more than any
                # value in the column. Below the cap nothing about this row
                # changed.
                #
                # A PROSE column is left alone here, and the screenshot is
                # what caught why. Capping the width is free only when the
                # height compensates: on a page that has not adopted the
                # column form yet, `Description` stayed one line AND became
                # 28 characters wide, so an item description went from
                # showing about 200 characters to showing 28. Narrower with
                # nothing paying for it. A prose column keeps its width
                # until its page can give it the rows instead.
                self.value.setMaximumWidth(
                    short_text_width(self.value.fontMetrics()))
        self.value.textChanged.connect(self._on_text)
        # Three to one against the note. A text row's VALUE is the point of
        # it - a job name or a description is what someone came here to
        # type - and an even split gave the note half the row. At the 1100
        # minimum that left the name box about 150px while a two-line note
        # sat beside it.
        row.addWidget(self.value, 3)

        # Same shape as NumericFieldRow's, down to the size policy, because
        # the two sit in the same column on the Jobs page and any
        # difference shows.
        #
        # Not wrapped, and Ignored horizontally, for the reason recorded on
        # that row: a long note must not be able to widen the form. Wrapped
        # and Preferred - which is what this row had first - gave the note
        # a quarter of the row at the 1100 minimum and wrapped it to five
        # lines, so five text fields occupied more height than the twelve
        # stat rows underneath them. The full text is in the tooltip.
        self._note_text = note
        self.note = FieldNoteLabel(note)
        self.note.setProperty("role", "muted")
        self.note.setWordWrap(False)
        self.note.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.note.setToolTip(note)
        # Stretch only when there IS a note.
        #
        # Unlike NumericFieldRow, whose value is a fixed-width spin box, a
        # text row's value is elastic - so an empty note holding a share of
        # the row takes that width straight off the box. Every page that
        # used this row before Jobs passes no note at all (Poaching, Items,
        # Abilities, Encounters), and giving the empty label a quarter of
        # the row shortened every one of their name and description boxes
        # by a quarter for nothing.
        # `stacked` says this row is one of a few in a single-column
        # section, and TWO things follow from that.
        #
        # 1. The note column is held even on rows that have no note. The
        #    rule above - an empty note surrenders its share - is right for
        #    a form of many columns and wrong for a stacked one. In the Jobs
        #    Name and Description section three of the five rows have notes,
        #    so Description, which needs none, drew 265px wider than
        #    Description (feminine) immediately below it. In three columns
        #    that never showed, because they were never side by side.
        #
        # 2. The note WRAPS instead of eliding. The no-wrap rule was
        #    measured on a form of twelve-plus rows at the 1100px minimum,
        #    where a wrapped note ran to five lines and made five text
        #    fields taller than the twelve stat rows under them. A stacked
        #    prose section is four rows, and the cost of a second line there
        #    is one line.
        #
        #    Eliding was the fix when the note could not have more room; it
        #    is the wrong answer when it can. Job Commands' "A second
        #    description..." needed 683px and the 3:1 split gave it 337, so
        #    it elided at every window size the tool supports - a note that
        #    is never readable is not a note.
        if stacked:
            self.note.setWordWrap(True)
            self.note.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        row.addWidget(self.note, 1 if (note or stacked) else 0, Qt.AlignTop)
        if not note and (not self._long_column or max_value_width):
            # The SHORT box is capped, so on a wide row the leftover has to
            # go somewhere. Without this Qt hands it to the only item with
            # stretch - the value - which cannot take it, and the row's
            # contents drift apart.
            #
            # Not for a prose column, and not when there is a note. A prose
            # box is the one control here that genuinely wants every pixel
            # left: with this stretch competing, a 261-character job
            # description got a box about 190px wide and scrolled
            # internally through three lines, which is the fault the
            # multi-line box was added to fix, reproduced one layer out.
            row.addStretch(1)

        self.setProperty("unknownField", bool(unknown))

    @property
    def included(self) -> bool:
        return self.include.isChecked()

    def get_value_str(self) -> str:
        return self.value.text()

    def load(self, raw_value, included: bool) -> None:
        self._loading = True
        try:
            self.value.setText("" if raw_value is None else str(raw_value))
            # Back to the start. After setText the cursor sits at the end, so
            # a description longer than the box showed its TAIL - the field
            # read "o. Used to produce a tuft of phoenix down." with the
            # beginning scrolled out of sight.
            self.value.setCursorPosition(0)
            self.include.setChecked(bool(included))
        finally:
            self._loading = False

    def _on_text(self, _text: str = "") -> None:
        # Defaulted, because the two boxes emit differently: `QLineEdit`'s
        # `textChanged` carries the new string and `QPlainTextEdit`'s
        # carries nothing. The argument was never read, so the default is
        # the whole fix - without it every keystroke in a description
        # raised a TypeError inside a signal handler, which Qt swallows,
        # and the edit would have been dropped silently.
        if self._loading:
            return
        if not self.include.isChecked():
            self.include.setChecked(True)
            return
        self.edited.emit()

    def _on_include(self, _on) -> None:
        if not self._loading:
            self.edited.emit()

    def apply_display(self, hide_notes: bool, hide_unknown: bool) -> None:
        self.note.setText("" if hide_notes else self._note_text)
        self.note.setToolTip("" if hide_notes else self._note_text)
        self.setVisible(not (hide_unknown and self.is_unknown))


class NamedNumberRow(QWidget):
    """
    `[x] Label  [ 012 - Curaga ]` - a NUMBER, chosen by name.

    Distinct from `DropdownFieldRow`, which points at another record and
    whose names come from a loaded table. These names come from an editable
    `data/*.txt` list (`reference_names.py`) and annotate a field that is
    numeric in the XML: the value written is still `12`, and the list only
    decides what a human sees.

    **Whether a field can be a picker at all is a question about the data,
    and it is not the same answer for all three lists.** Counted against the
    bundled tables:

        ChargeEffectType   19 distinct vanilla values, every one named
        AnimationId        54 distinct vanilla values, every one named
        EffectId          360 distinct values over -1..2333, 17 unnamed,
                          across 80 rows

    So the first two round-trip the game's own data through a list and the
    third cannot. `EffectId` keeps a spin box with the name shown beside it,
    which is what `reference_names.py`'s docstring argues for - that
    reasoning is right about `EffectId` and turned out not to be right about
    the other two.

    **An unlisted value is shown, never snapped.** The lists cover 0-48 and
    0-125 while the fields are bytes, so a mod may legitimately hold an id
    with no name. Falling back to index 0 would silently rewrite that mod's
    animation to whatever happens to be first - the same class of quiet
    data loss as a label reaching the file in place of its value. An
    unlisted id gets its own entry instead, exactly as `DropdownFieldRow`
    already does for an unnamed record id.
    """

    edited = Signal()

    def __init__(self, field_name: str, label: str, names: dict,
                 note: str = "", unknown: bool = False, parent=None):
        super().__init__(parent)
        self.field_name = field_name
        self.is_unknown = unknown
        self._loading = False
        self._id_to_index: dict[int, int] = {}

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 1, 0, 1)
        row.setSpacing(8)

        self.include = QCheckBox()
        self.include.setToolTip(
            "Tick to write this field into your mod. Unticked fields are "
            "left alone, so other mods can change them.")
        self.include.toggled.connect(self._on_include_toggled)
        row.addWidget(self.include)

        self.label = QLabel(label)
        self.label.setFixedWidth(200)
        row.addWidget(self.label)

        self.combo = QComboBox()
        # The same bounded-expanding shape as DropdownFieldRow, and for the
        # same reason: uncapped, a wide monitor drew a 2000px control for a
        # 20-character name.
        self.combo.setMinimumWidth(160)
        self.combo.setMaximumWidth(360)
        self.combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.combo.currentIndexChanged.connect(self._on_index_changed)
        row.addWidget(self.combo, 1)

        self._note_text = note
        self.note = FieldNoteLabel(note)
        self.note.setProperty("role", "muted")
        self.note.setWordWrap(False)
        self.note.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.note.setToolTip(note)
        row.addWidget(self.note, 1)

        self.setProperty("fieldRow", True)
        self.setProperty("unknownField", bool(unknown))

        self.set_choices(names)

    # -- choices ------------------------------------------------------------

    def set_choices(self, names: dict) -> None:
        current = self.current_id()
        self._loading = True
        try:
            self.combo.clear()
            self._id_to_index = {}
            for index, (value_id, name) in enumerate(sorted(names.items())):
                self.combo.addItem(f"{value_id:03d} - {name}", value_id)
                self._id_to_index[value_id] = index
            if current in self._id_to_index:
                self.combo.setCurrentIndex(self._id_to_index[current])
        finally:
            self._loading = False

    def current_id(self) -> int:
        data = self.combo.currentData()
        return int(data) if data is not None else 0

    # -- state --------------------------------------------------------------

    @property
    def included(self) -> bool:
        return self.include.isChecked()

    def get_value_str(self) -> str:
        return str(self.current_id())

    def load(self, raw_value, included: bool) -> None:
        self._loading = True
        try:
            try:
                value_id = int(str(raw_value).strip() or 0)
            except (TypeError, ValueError):
                value_id = 0
            if value_id not in self._id_to_index:
                self.combo.addItem(f"{value_id:03d} - (unnamed)", value_id)
                self._id_to_index[value_id] = self.combo.count() - 1
            self.combo.setCurrentIndex(self._id_to_index[value_id])
            self.include.setChecked(bool(included))
        finally:
            self._loading = False

    # -- interaction --------------------------------------------------------

    def _on_index_changed(self, _index) -> None:
        if self._loading:
            return
        if not self.include.isChecked():
            self.include.setChecked(True)
            return
        self.edited.emit()

    def _on_include_toggled(self, _on) -> None:
        if self._loading:
            return
        self.edited.emit()

    def apply_display(self, hide_notes: bool, hide_unknown: bool) -> None:
        self.note.setText("" if hide_notes else self._note_text)
        self.note.setToolTip("" if hide_notes else self._note_text)
        self.setVisible(not (hide_unknown and self.is_unknown))


class AnnotatedNumberRow(NumericFieldRow):
    """
    A spin box with the current id's name shown beside it, live.

    For `EffectId`, where a picker is not possible: 17 of its vanilla values
    have no name and one of them is -1, which 64 abilities use. The number
    stays typeable and the name follows it, which is what
    `reference_names.describe` was written for.
    """

    def __init__(self, field_name: str, label: str, minimum: int, maximum: int,
                 names: dict, note: str = "", parent=None):
        super().__init__(field_name, label, minimum, maximum, note,
                         parent=parent)
        self._names = names or {}
        self.name_label = QLabel("")
        self.name_label.setProperty("role", "muted")
        # Inserted straight after the spin box, before the note, so the name
        # reads as part of the value rather than as part of the help text.
        self.layout().insertWidget(3, self.name_label)
        self.value.valueChanged.connect(lambda _v: self._sync_name())
        self._sync_name()

    def _sync_name(self) -> None:
        from ... import reference_names
        self.name_label.setText(
            reference_names.describe(self._names, self.value.value()))

    def load(self, raw_value, included: bool) -> None:
        super().load(raw_value, included)
        self._sync_name()


class CollapsibleSection(QWidget):
    """
    A header you click to open, with a body underneath.

    Used instead of a second row of tabs inside the page. The Tkinter Jobs
    tab put its six groups behind sub-tabs, which made reaching a field
    three navigation levels deep - sidebar, tab, sub-tab - and meant you had
    to already know which sub-tab a field lived in. Sections put everything
    in one scroll: collapsed they are one line each, and two can be open at
    once, which sub-tabs cannot do.
    """

    def __init__(self, title: str, body: QWidget, expanded: bool = False,
                 parent=None):
        super().__init__(parent)
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 6, 0, 0)
        column.setSpacing(2)

        self.header = QToolButton()
        self.header.setText(title)
        self.header.setCheckable(True)
        self.header.setChecked(expanded)
        self.header.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.header.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        self.header.setProperty("role", "section")
        self.header.setCursor(Qt.PointingHandCursor)
        self.header.toggled.connect(self._on_toggled)
        column.addWidget(self.header)

        self.body = body
        self.body.setVisible(expanded)
        column.addWidget(self.body)

    def _on_toggled(self, on: bool) -> None:
        self.header.setArrowType(Qt.DownArrow if on else Qt.RightArrow)
        self.body.setVisible(on)

    def set_expanded(self, on: bool) -> None:
        self.header.setChecked(on)


class FlagFieldPanel(QWidget):
    """
    `[x] Label [Clear]` over a grid of grouped checkboxes.

    Same opt-in rule as a numeric field, and the same reasoning: ticking any
    flag ticks the include box, because having chosen which weapons a job
    can equip you clearly want that written. `load()` suppresses it so
    selecting a job never counts as a choice.

    All/None also tick include. Pressing "None" is a deliberate statement -
    "this job equips nothing" - and it has to be distinguishable from never
    having touched the field. `format_flag_value(set())` writes "None" for
    exactly that reason, and this panel must not quietly turn it back into
    "unedited".
    """

    edited = Signal()

    def __init__(self, field_name: str, label: str, groups: dict,
                 columns: int = 4, parent=None):
        super().__init__(parent)
        self.field_name = field_name
        self.is_unknown = False
        self._loading = False
        self.boxes: dict[str, QCheckBox] = {}

        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(4)

        header = QHBoxLayout()
        self.include = QCheckBox()
        self.include.setToolTip(
            "Tick to write this field into your mod. Unticked fields are "
            "left alone, so other mods can change them.")
        self.include.toggled.connect(self._on_include_toggled)
        header.addWidget(self.include)
        name = QLabel(label)
        name.setStyleSheet("font-weight: 600;")
        header.addWidget(name)
        header.addSpacing(10)
        # Sized to their text rather than to a guessed pixel width. 56px
        # looked ample for "None" and clipped it to "one" once the button's
        # own padding was taken into account - the third clipped control in
        # this project's history, after two buttons in the Tkinter
        # interface. A guessed width is a clipped label waiting to happen.
        # No "All" button.
        #
        # It set every flag at once, which is meaningful for a status or
        # equipment mask and meaningless for something like a map trap -
        # no vanilla row sets more than two of the five, and setting all
        # five is not a state the game has. "Clear" stays, because emptying
        # a field IS a real edit and 160 of 512 vanilla trap rows are empty.
        none_button = QPushButton("Clear")
        none_button.setMinimumWidth(none_button.sizeHint().width() + 8)
        none_button.clicked.connect(lambda: self._set_all(False))
        header.addWidget(none_button)
        header.addStretch(1)
        column.addLayout(header)

        grid = QGridLayout()
        grid.setSpacing(6)
        for i, (group_name, flags) in enumerate(groups.items()):
            # "&" in a Qt label is a keyboard mnemonic, so "Shields &
            # Headgear" renders as "Shields _Headgear" with the H
            # underlined. The group names come from the engine's own
            # constants and are meant to be read literally, so the
            # ampersand is escaped rather than the constant reworded -
            # changing engine data to suit a display quirk would be the
            # wrong way round.
            box = QGroupBox(group_name.replace("&", "&&"))
            inner = QVBoxLayout(box)
            inner.setContentsMargins(8, 4, 8, 6)
            inner.setSpacing(1)
            for flag in flags:
                # The LABEL is spaced; the key stays the exact flag name.
                # `DisableTrap` and `SleepingGas` are how the game's own
                # enum spells them and how they must be written back, but
                # nobody reading a UI should have to decode run-together
                # words. `self.boxes` is still keyed by the real name, so
                # nothing downstream sees the prettier version.
                check = QCheckBox(split_words(flag))
                check.toggled.connect(self._on_flag_toggled)
                self.boxes[flag] = check
                inner.addWidget(check)
            grid.addWidget(box, i // columns, i % columns, Qt.AlignTop)
        column.addLayout(grid)

    # -- state --------------------------------------------------------------

    @property
    def included(self) -> bool:
        return self.include.isChecked()

    def get_value_str(self) -> str:
        from ... import xml_io
        return xml_io.format_flag_value(
            {name for name, box in self.boxes.items() if box.isChecked()})

    def load(self, raw_value, included: bool) -> None:
        from ... import xml_io
        self._loading = True
        try:
            flags = xml_io.parse_flag_value(str(raw_value or ""))
            for name, box in self.boxes.items():
                box.setChecked(name in flags)
            self.include.setChecked(bool(included))
        finally:
            self._loading = False

    # -- interaction --------------------------------------------------------

    def _on_flag_toggled(self, _on) -> None:
        if self._loading:
            return
        if not self.include.isChecked():
            self.include.setChecked(True)
            return
        self.edited.emit()

    def _on_include_toggled(self, _on) -> None:
        if self._loading:
            return
        self.edited.emit()

    def _set_all(self, on: bool) -> None:
        self._loading = True
        try:
            for box in self.boxes.values():
                box.setChecked(on)
        finally:
            self._loading = False
        # Emphatically an edit, including "None" - see the class docstring.
        if not self.include.isChecked():
            self.include.setChecked(True)
        else:
            self.edited.emit()

    def apply_display(self, hide_notes: bool, hide_unknown: bool) -> None:
        """Flag panels carry no notes and are never unknown fields."""
        return


def split_words(name: str) -> str:
    """
    `DisableTrap` -> `Disable Trap`, for a checkbox or dropdown label.

    Display only. Every caller keys its own data by the original name,
    because that is what gets written back to the game's enum.

    **Underscores are word breaks too.** They were not, and the result was
    visible in two places at once: `ShopAvailability` rendered
    `Chapter1_EnterIgros` as "Chapter1_ Enter Igros", and the ability AI
    flag `CheckCT_Target` came out "Check CT_ Target" - a stray underscore
    hanging off the end of a word in both. Splitting on them as well gives
    "Chapter1 Enter Igros" and "Check CT Target".

    Runs of capitals are kept together, so `CT` stays `CT` rather than
    becoming `C T`.
    """
    out = []
    for index, letter in enumerate(name):
        if letter == "_":
            # Collapsed, not doubled - "A__B" and "A_B" both read the same,
            # and a label should never show the gap where a separator was.
            if out and out[-1] != " ":
                out.append(" ")
            continue
        if (index and letter.isupper() and not name[index - 1].isupper()
                and name[index - 1] != "_"):
            out.append(" ")
        out.append(letter)
    return "".join(out).strip()


class DropdownFieldRow(QWidget):
    """
    `[x] Label  [ 003 - Fire ]`

    For fields that hold an ID pointing at another record - an ability slot,
    a skillset. The stored value is the ID as a string; the dropdown shows
    `"003 - Fire"` so nobody has to remember that 3 is Fire.

    Same opt-in rule as every other row, and the same reason for it:
    choosing an ability from a list means you want it, so choosing ticks the
    box. Loading a record never does.

    `0` is "(None / Unset)" and is a real choice, not an absence - clearing
    an ability slot is a deliberate edit. It is registered like any other so
    it can be picked, and `included` is what decides whether it reaches the
    mod.

    Choices arrive AFTER construction. Ability and skillset names come from
    tables fetched during setup, which do not exist when the editor is
    first built, so `set_choices()` is called whenever that data changes
    rather than being read once in __init__.

    **Every row that points at another record can carry its own jump
    button.** Pass `jump_label` and the row grows an `Edit ->` beside the
    dropdown, emitting `jump_requested` with the selected ID.

    That belongs here rather than on the page because of what the Qt
    rewrite did without it. The Tkinter Job Commands tab gives all 22 slots
    their own button; the Qt page had a single "Edit the ability in slot 1"
    above the form, which can only ever reach one of the 22 and requires
    knowing that slot 1 is special, which it isn't. Putting the button on
    the row means the count follows the rows - sixteen ability slots get
    sixteen buttons - instead of a page deciding how many jumps it feels
    like offering.

    The button is disabled while the slot reads `(None)`, because there is
    nothing to jump to. `_sync_jump` is called from every path that can
    change the value, including `load()`, so browsing to a record with an
    empty slot leaves the button correctly dead.
    """

    edited = Signal()
    jump_requested = Signal(int)

    def __init__(self, field_name: str, label: str, parent=None,
                 jump_label: str | None = None, jump_tooltip: str = ""):
        super().__init__(parent)
        self.field_name = field_name
        self.is_unknown = False
        self._loading = False
        self._id_to_index: dict[int, int] = {}

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 1, 0, 1)
        row.setSpacing(8)

        self.include = QCheckBox()
        self.include.setToolTip(
            "Tick to write this field into your mod. Unticked fields are "
            "left alone, so other mods can change them.")
        self.include.toggled.connect(self._on_include_toggled)
        row.addWidget(self.include)

        self.label = QLabel(label)
        self.label.setFixedWidth(200)
        row.addWidget(self.label)

        self.combo = QComboBox()
        # 160, not the 260 this had when the row ended at the combo box. A
        # jump button now sits after it, and at the 1100 minimum the editor
        # pane is about 540px wide - a 260px floor plus a 200px label plus a
        # checkbox left the button nothing and Qt clipped it. The combo
        # still expands into whatever space there is; only the floor moved.
        self.combo.setMinimumWidth(160)
        # Capped, and NOT expanding.
        #
        # It used to stretch to whatever the window was, which on a wide
        # monitor made a 2000px-long dropdown for a 20-character skillset
        # name - and pushed the `Edit ->` button beside it to the far right
        # edge, so reaching it meant dragging the mouse across the whole
        # screen. The stretch goes on the row instead, after the button, so
        # the pair stays together on the left where the labels are.
        self.combo.setMaximumWidth(360)
        # Expanding, but bounded: it grows to 360 where there is room and
        # shrinks to 160 at the 1100 minimum, and the stretch after the
        # button absorbs everything beyond that.
        self.combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.combo.currentIndexChanged.connect(self._on_index_changed)
        row.addWidget(self.combo, 1)

        self.jump_button = None
        if jump_label is not None:
            # Short text - "Edit ->", not "Edit this Ability ->". The
            # Tkinter version learned that at 16 repetitions the fuller
            # label clips against the panel width.
            #
            # **The width is not set here.** A first attempt sized the
            # button to `fontMetrics().horizontalAdvance(label) + 24`, which
            # shipped 22 buttons all reading ":dit". Two reasons, and the
            # second is the general one: the theme adds `padding: 5px 14px`
            # plus a border, and - the part worth remembering - the
            # stylesheet is applied to the QApplication AFTER every page has
            # been constructed. Any width computed in __init__ is measured
            # against an unstyled button and is wrong by however much the
            # theme later adds.
            #
            # Letting Qt size the button at layout time gets this right
            # without anyone having to predict the theme.
            self.jump_button = QPushButton(jump_label)
            self.jump_button.setToolTip(jump_tooltip)
            self.jump_button.setEnabled(False)
            self.jump_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            self.jump_button.clicked.connect(self._emit_jump)
            row.addWidget(self.jump_button)
        # Both the combo and this share the leftover space, so the combo
        # grows until it hits its 360 cap and everything past that lands
        # here. A stretch alone would take all of it and leave the combo at
        # its 160 minimum on every screen size.
        row.addStretch(1)

        self.set_choices({0: "(None / Unset)"})

    # -- choices ------------------------------------------------------------

    def set_choices(self, id_to_name: dict) -> None:
        """
        Replaces the list, keeping whatever was selected if it still exists.

        Rebuilding the list fires currentIndexChanged, which without the
        suppression flag would register as the user picking something - so
        merely fetching a newer ability table would silently mark fields as
        edited across every record.
        """
        current = self.current_id()
        self._loading = True
        try:
            self.combo.clear()
            self._id_to_index = {}
            for index, (value_id, name) in enumerate(sorted(id_to_name.items())):
                display = name if value_id == 0 else f"{value_id:03d} - {name}"
                self.combo.addItem(display, value_id)
                self._id_to_index[value_id] = index
            if current in self._id_to_index:
                self.combo.setCurrentIndex(self._id_to_index[current])
        finally:
            self._loading = False
        self._sync_jump()

    def current_id(self) -> int:
        data = self.combo.currentData()
        return int(data) if data is not None else 0

    # -- state --------------------------------------------------------------

    @property
    def included(self) -> bool:
        return self.include.isChecked()

    def get_value_str(self) -> str:
        return str(self.current_id())

    def load(self, raw_value, included: bool) -> None:
        self._loading = True
        try:
            try:
                value_id = int(str(raw_value).strip() or 0)
            except (TypeError, ValueError):
                value_id = 0
            if value_id not in self._id_to_index:
                # An ID the current table has no name for. Shown as itself
                # rather than silently becoming 0 - a mod that points at
                # something this tool cannot name is still pointing at it,
                # and rewriting that to "None" would quietly break the mod.
                self.combo.addItem(f"{value_id:03d} - (unknown)", value_id)
                self._id_to_index[value_id] = self.combo.count() - 1
            self.combo.setCurrentIndex(self._id_to_index[value_id])
            self.include.setChecked(bool(included))
        finally:
            self._loading = False
        self._sync_jump()

    # -- jumping ------------------------------------------------------------

    def _sync_jump(self) -> None:
        """Nothing to jump to while the slot reads (None)."""
        if self.jump_button is not None:
            self.jump_button.setEnabled(bool(self.current_id()))

    def _emit_jump(self) -> None:
        target = self.current_id()
        if target:
            self.jump_requested.emit(target)

    # -- interaction --------------------------------------------------------

    def _on_index_changed(self, _index) -> None:
        self._sync_jump()
        if self._loading:
            return
        if not self.include.isChecked():
            self.include.setChecked(True)
            return
        self.edited.emit()

    def _on_include_toggled(self, _on) -> None:
        if self._loading:
            return
        self.edited.emit()

    def apply_display(self, hide_notes: bool, hide_unknown: bool) -> None:
        return
