"""
Edit Game Data / Encounters.

516 rows of `OverrideEntryData` - the per-battle unit overrides that decide
who shows up, as what job, with what equipment. The most heavily documented
table in the tool and the one with the most honest uncertainty in it.

Three things here are unlike every other tab:

**A row's address is a PAIR.** `(Key, Key2)` together identify a row, not
`Key` alone. A list keyed on `Key` would silently collapse rows that differ
only in `Key2`.

**Inherit is per-field, and it is not one value.** `constants.
ENTRY_INHERIT_VALUES` gives each field its own:

    Spriteset    0   leave the unit's sprite set alone
    MainJob      0   leave the unit's job alone
    JobUnlock    20  leave job unlocks alone

Twenty. Not 0, not -1. Together with Poaching's "0 means none, -1 is
invalid" and the ability override layer's "-1 means inherit", that makes
three different conventions across three adjacent tables, each right for its
own. Anything that made them consistent would break at least two, so the
values come from `ENTRY_INHERIT_VALUES` and are never assumed.

**Field confidence is shown, not hidden.** Every field is confirmed,
inferred, or genuinely unknown, and the page says which. That is the
project's honesty convention: a field nobody has worked out is labelled as
such rather than given an invented meaning that reads as fact.

**Rows cannot be added, and the row COUNT is what matters.** Zodi
established this from in-game testing of Dark Knight Expansion: rows added
to `OverrideEntryData` are ignored by the game, so the published mod
*repurposed* ten existing rows into `(95, 0..9)` instead. Vanilla has 516
rows, the working mod has 516, and an earlier Mod Studio re-export had 526
- precisely `vanilla union mod`, with the ten vacated addresses coming back
from vanilla. That was the bug.

Worth being exact about what is and is not known: `Key 95` does not exist in
vanilla at all, so the mod DID introduce an address the game had never seen,
and it works. What it held constant was the count. Whether the real
constraint is the count, something about file size or offsets, or something
else is **not established**.

So moving a row is the primitive here, not adding or deleting one. Dropping
a row (`entry_dropped`) exists in the engine for recovery - it is how a mod
that vacated an address is read back - rather than as something to offer as
"delete this row", which would invite exactly the row-count change that does
not work.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from ... import constants as c
from ... import encounter_names
from ... import nxd_layouts
from ..widgets.actions import (
    page_intro,
    COPY_LANGUAGES_LABEL, COPY_LANGUAGES_NOTE, ViewToggles, apply_view_toggles,
    copy_edits_to_languages, ensure_language_loaded, mark_edited,
    language_order, set_empty_state, edit_counter_text)
from ..widgets.field_rows import CollapsibleSection, NumericFieldRow
from ..widgets.form_scroll import FormScrollArea
from ..widgets.visible_refresh import RefreshesWhenVisible
from .poaching import BoolFieldRow, TextFieldRow

# Read from Nenkai's layout, not restated. This one was already correct -
# CharaName really does have exactly Name and Comment as strings - but it
# is derived anyway, because being right today is what the other three
# lists were too, until the tables they described changed.
CHARA_TEXT_FIELDS = tuple(
    nxd_layouts.translated_columns("CharaName", c.CHARANAME_TEXT_FIELDS))

# Too long for the 200px label column, so the label says "Comment" and
# this says the rest.
COMMENT_TOOLTIP = (
    "FF16Tools writes this note into the converted table. It is not data the game reads, so editing it changes nothing in play - it is here because a mod that ships the row should ship the row as it found it.")

CONFIDENCE_SUFFIX = {
    "confirmed": "",
    "inferred": "  (inferred)",
    "unknown": "  (unknown)",
}


def field_label(field_name: str) -> str:
    """
    The label, with its confidence tier attached where it is not confirmed.

    An inferred field is one read from its name and the values real rows
    carry; an unknown one is genuinely not understood. Saying so in the
    label is the point - a mod author deciding whether to touch a field
    needs to know how much is actually known about it.
    """
    # Two places hold labels, and only one was being read.
    #
    # `ENTRY_FIELD_LABELS` covers the renamed fields - `Unknown4` is really
    # the unit name, `EntryUnknown1D` is the primary job command. Everything
    # numeric gets its label from `ENTRY_NUMERIC_FIELDS`, which already
    # spells them properly: "Job Level", "Job Unlock". Reading only the
    # first meant those two fell through to the raw column name and showed
    # as `JobLevel` and `JobUnlock`.
    label = c.ENTRY_FIELD_LABELS.get(field_name)
    if label is None:
        numeric = c.ENTRY_NUMERIC_FIELDS.get(field_name)
        # (min, max, label, help) - the label is the third item.
        label = numeric[2] if numeric and len(numeric) > 2 else field_name
    tier = c.ENTRY_FIELD_CONFIDENCE.get(field_name, "unknown")
    return label + CONFIDENCE_SUFFIX.get(tier, "")


def inherit_note(field_name: str) -> str:
    """The field's own 'leave this alone' value, straight from the engine."""
    entry = c.ENTRY_INHERIT_VALUES.get(field_name)
    if not entry:
        return ""
    value, explanation = entry
    return f"Inherit = {value}. {explanation}"


class EncountersPage(RefreshesWhenVisible, QWidget):
    edits_changed = Signal()

    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state
        self.current_address = None
        self._encounter_names = None
        self.rows: dict[str, QWidget] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 10, 24, 20)
        outer.setSpacing(10)

        outer.addLayout(page_intro(
            "Who turns up in each battle or event, as what job, with what "
            "equipment and so on."))

        # Every tab with field rows gets these, not just Jobs.
        self.view_toggles = ViewToggles()
        self.view_toggles.changed.connect(self._apply_view)
        # Hidden: the shell draws the one visible pair, above the tabs,
        # so it is in the same place on all ten. This instance still
        # receives the preference and still answers `state()`.
        self.view_toggles.follow_only()

        # No tab strip. `CharaName-xx` used to be a second tab in here and
        # is now its own sidebar page - see `unit_names.py` for why. What is
        # left is one table, one list, one counter, which is the shape every
        # other editing page has.
        entries_column = QVBoxLayout()
        # No top margin. The 8px was inset for the tab strip that used to
        # sit above this column; with the strip gone it was just a gap, and
        # it pushed the green counter to y=58 where every other tab has it
        # at y=50 - the "extra line between the description and the green
        # text" reported from real use.
        entries_column.setContentsMargins(0, 0, 0, 0)
        entries_column.setSpacing(10)
        outer.addLayout(entries_column, 1)

        self.counter = QLabel("")
        self.counter.setProperty("role", "ok")
        entries_column.addWidget(self.counter)

        split = QHBoxLayout()
        split.setSpacing(14)

        left = QVBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search by encounter or address")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter_list)
        left.addWidget(self.search)
        self.list = QListWidget()
        self.list.setFixedWidth(300)
        self.list.currentItemChanged.connect(self._on_selection)
        left.addWidget(self.list, 1)
        split.addLayout(left)

        right = QVBoxLayout()
        self.editing_label = QLabel("Select an encounter row")
        self.editing_label.setStyleSheet("font-weight: 600; font-size: 12pt;")
        right.addWidget(self.editing_label)

        self.empty_note = QLabel(
            # Reworded: there is no Convert button any more - unpacking
            # converts, and so does adopting a folder with no database.
            "No game data yet.\n\nGo to General Setup and unpack your game, "
            "or point at a folder you've already unpacked.")
        self.empty_note.setProperty("role", "muted")
        self.empty_note.setWordWrap(True)
        # Top-left, where the content it is standing in for would start.
        #
        # This was `AlignCenter` with a stretch, which put the message in the
        # dead centre of the window - a long way from the sidebar item that
        # was just clicked, and below the "Move this row to:" controls that
        # were still on screen. Textures and Sounds have always used
        # `AlignTop` and read correctly; the four master-detail pages had
        # each been given `AlignCenter` instead. This makes all six agree.
        self.empty_note.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        right.addWidget(self.empty_note)

        # Moving a row to a different address. Edits stay keyed by the row's
        # ORIGIN, so a row moved twice - or moved and moved back - keeps one
        # identity and one set of edits; `nxd_data.translate_entry_edits`
        # reconciles the two views at write time.
        # Two lines, not one. Two labels, two spin boxes and two buttons need
        # more width than the right-hand pane has at the minimum window size,
        # and a single row squeezed "Undo move" below its own text. Caught by
        # the page-wide clipping check rather than by a screenshot, which is
        # the first time that check has got there first.
        # All of it in one container, so the whole block goes away together
        # when there is nothing loaded.
        #
        # These used to be two bare layouts added straight to the column.
        # `refresh_records` hid the list, the search box, the editing label
        # and the form, but a layout has no `setVisible` and nothing owned
        # these - so with no game data the page showed "No game data yet"
        # floating in the middle and "Move this row to: [0] / [0] [Move]
        # [Undo move]" stranded at the very bottom, offering to move a row
        # that does not exist to an address in a table that has not loaded.
        self.move_controls = QWidget()
        move_column = QVBoxLayout(self.move_controls)
        move_column.setContentsMargins(0, 0, 0, 0)
        move_column.setSpacing(4)

        move_row = QHBoxLayout()
        move_row.addWidget(QLabel("Move this row to:"))
        self.move_key = QSpinBox()
        self.move_key.setRange(0, 65535)
        move_row.addWidget(self.move_key)
        move_row.addWidget(QLabel("/"))
        self.move_key2 = QSpinBox()
        self.move_key2.setRange(0, 65535)
        move_row.addWidget(self.move_key2)

        # The buttons sit BESIDE the boxes, not on a line of their own.
        #
        # They were on a second row underneath, which read as two separate
        # controls - a pair of numbers, and then some buttons that might act
        # on anything. Together they are one sentence: move this row to
        # here, do it. Reported from real use.
        #
        # The stretch goes AFTER the buttons rather than between the boxes
        # and them, so the whole sentence stays together at the left instead
        # of the verb drifting to the far side of a wide window.
        self.move_button = QPushButton("Move")
        self.move_button.clicked.connect(self.move_current_row)
        move_row.addSpacing(8)
        move_row.addWidget(self.move_button)

        self.undo_move_button = QPushButton("Undo move")
        self.undo_move_button.setEnabled(False)
        self.undo_move_button.clicked.connect(self.undo_move)
        move_row.addWidget(self.undo_move_button)
        move_row.addStretch(1)
        move_column.addLayout(move_row)

        # No trailing stretch. With one, the layout gave the leftover width
        # to the spacer and then squeezed "Undo move" to 91px against the
        # 105px it needs - caught by the page-wide clipping check, which is
        # the first time that check has found something before a screenshot
        # did.
        #
        # The two `setMinimumWidth(sizeHint().width() + 8)` calls that used
        # to sit on these buttons are gone. `__init__` runs before the
        # stylesheet reaches the QApplication, so both were measuring an
        # unstyled widget and pinning a minimum narrower than the button
        # actually needs. Qt sizes them correctly at layout time.

        self.move_note = QLabel("")
        self.move_note.setProperty("role", "muted")
        self.move_note.setWordWrap(True)
        move_column.addWidget(self.move_note)
        right.addWidget(self.move_controls)

        # No "deleting rows is still only in the old interface" note.
        #
        # It is not in the old interface either - it was taken out, because
        # the game ignores added `OverrideEntryData` rows and the count has
        # to stay at 516. Moving a row is the primitive; `entry_dropped` is
        # for recovery, not a delete button. The note pointed at a feature
        # that does not exist anywhere and never should.

        scroll = FormScrollArea()
        holder = QWidget()
        form = QVBoxLayout(holder)
        form.setContentsMargins(4, 4, 4, 4)
        form.setSpacing(2)

        # Sections come from the engine's own grouping, in its own order, so
        # a field moved between sections there moves here without this page
        # being touched.
        self.sections = []
        for index, (section_name, field_names) in enumerate(
                c.ENTRY_FIELD_SECTIONS.items()):
            body = QWidget()
            column = QVBoxLayout(body)
            column.setContentsMargins(0, 0, 0, 0)
            column.setSpacing(2)
            for field_name in field_names:
                row = self._build_row(field_name)
                if row is None:
                    continue
                row.edited.connect(self._on_field_edited)
                self.rows[field_name] = row
                column.addWidget(row)
            section = CollapsibleSection(section_name, body, expanded=index == 0)
            self.sections.append(section)
            form.addWidget(section)

        form.addStretch(1)
        scroll.setWidget(holder)
        self.scroll = scroll
        right.addWidget(scroll, 1)
        split.addLayout(right, 1)
        entries_column.addLayout(split, 1)

        self._apply_view(*self.view_toggles.state())
        self.refresh_records()

    # -- Unit Names (CharaName-xx) ----------------------------------------

    def _build_row(self, field_name: str):
        label = field_label(field_name)
        note = inherit_note(field_name)
        unknown = c.ENTRY_FIELD_CONFIDENCE.get(field_name) == "unknown"

        if field_name in c.ENTRY_ARRAY_FIELDS:
            # An array of bytes. Shown as text so it round-trips exactly,
            # rather than as a number it is not.
            return TextFieldRow(field_name, label)
        if field_name in c.ENTRY_BOOL_FIELDS:
            return BoolFieldRow(field_name, label, note)
        if c.ENTRY_COLUMN_TYPES.get(field_name) == "string":
            return TextFieldRow(field_name, label)
        # The floor is the field's OWN inherit value when that is negative.
        #
        # Sixteen of these fields use -1 to mean "leave the unit's own value
        # alone" - Reaction, Support, Movement, every equipment slot - and
        # the box could not hold it, so a row the nxd says is -1 read as 0.
        # 0 is a real and very different answer: for Head or Body it is an
        # actual item id, so the page was showing an equipped item where the
        # file says "unchanged".
        #
        # Taken from `ENTRY_INHERIT_VALUES`, which is where that fact already
        # lives and which the note under the field is already built from -
        # so the control and its own caption cannot disagree.
        floor = 0
        inherit = c.ENTRY_INHERIT_VALUES.get(field_name)
        if inherit and isinstance(inherit[0], int) and inherit[0] < 0:
            floor = inherit[0]
        row = NumericFieldRow(field_name, label, floor, 65535, note,
                              unknown=unknown)
        return row

    # -- records -----------------------------------------------------------------

    def records(self) -> list:
        return self.state.entry_records or []

    @staticmethod
    def address_of(record) -> tuple:
        """
        A row's identity is the PAIR. Keyed on `key` alone, rows differing
        only in `key2` would collapse into one another.
        """
        return (record.key, record.key2)

    def refresh_records(self) -> None:
        self.list.clear()
        records = self.records()
        for record in records:
            address = self.address_of(record)
            name = self._name_for(record)
            item = QListWidgetItem(f"{address[0]}/{address[1]} - {name}")
            item.setData(Qt.UserRole, address)
            self.list.addItem(item)
        has_data = bool(records)
        # The move controls go with everything else. They are the reason
        # this page needed the shared helper: they were the one block on any
        # tab that `refresh_records` did not know about, so they sat at the
        # bottom of an empty page offering to move a row that did not exist.
        set_empty_state(
            self.empty_note, has_data,
            self.scroll, self.search, self.list, self.editing_label,
            self.move_controls)
        self._mark_edited()
        self._update_counter()
        if self.list.count():
            self.list.setCurrentRow(0)

    def _name_for(self, record) -> str:
        """
        The encounter's real name, from `data/EncounterNames.txt`.

        This read `state.encounter_names`, which nothing ever populates, so
        every row in a 516-row list read "Encounter 12" - the id it already
        showed, twice. There is a whole engine module for this
        (`encounter_names`, sourced from FFTPatcher) and the Tkinter page
        has always used it.

        The table is loaded once and kept: it is read from disk and does
        not change while the tool runs.
        """
        if self._encounter_names is None:
            try:
                self._encounter_names = encounter_names.EncounterNames.load()
            except Exception:                                 # noqa: BLE001
                self._encounter_names = False     # tried and failed; don't retry
        if not self._encounter_names:
            return f"Encounter {record.key}"
        return (self._encounter_names.label_for(record.key)
                or f"Encounter {record.key}")

    def _filter_list(self, text: str) -> None:
        needle = text.strip().lower()
        for i in range(self.list.count()):
            item = self.list.item(i)
            item.setHidden(bool(needle) and needle not in item.text().lower())

    def _on_selection(self, current, _previous) -> None:
        if current is not None:
            self.load_record(tuple(current.data(Qt.UserRole)))

    def load_record(self, address: tuple) -> None:
        by_address = {self.address_of(r): r for r in self.records()}
        record = by_address.get(tuple(address))
        if record is None:
            return
        self.current_address = tuple(address)
        self.editing_label.setText(
            f"Editing: {address[0]}/{address[1]} - {self._name_for(record)}")

        moved = self.state.entry_rekeys.get(self.current_address)
        self.move_key.setValue(moved[0] if moved else address[0])
        self.move_key2.setValue(moved[1] if moved else address[1])
        self._refresh_move_state()

        already = self.state.entry_edits.get(self.current_address, {})
        for field_name, row in self.rows.items():
            if field_name in already:
                row.load(already[field_name], True)
            else:
                row.load(record.values.get(field_name, ""), False)

    # -- moving a row ---------------------------------------------------------

    def move_current_row(self) -> None:
        """
        Sends this row to a different address.

        The edits do NOT move with it in the store - they stay keyed by the
        row's origin, which is what lets a row be moved twice, or moved and
        moved back, without its edits splitting across two identities.
        """
        if self.current_address is None:
            return
        destination = (self.move_key.value(), self.move_key2.value())
        if destination == self.current_address:
            self.state.entry_rekeys.pop(self.current_address, None)
            self._refresh_move_state()
            self.move_note.setText("That's where it already is.")
            return

        taken = {tuple(v) for k, v in self.state.entry_rekeys.items()
                 if k != self.current_address}
        occupied = {self.address_of(r) for r in self.records()
                    if self.address_of(r) != self.current_address}
        if destination in taken or destination in occupied:
            # Refused rather than allowed to collide. Two rows at one address
            # is not something the game can express, and finding out at export
            # time would be much later than finding out now.
            self.move_note.setText(
                f"{destination[0]}/{destination[1]} is already taken.")
            return

        self.state.entry_rekeys[self.current_address] = destination
        self._refresh_move_state()
        self.edits_changed.emit()

    def undo_move(self) -> None:
        if self.current_address is None:
            return
        self.state.entry_rekeys.pop(self.current_address, None)
        self._refresh_move_state()
        self.edits_changed.emit()

    def _refresh_move_state(self) -> None:
        moved = self.state.entry_rekeys.get(self.current_address)
        self.undo_move_button.setEnabled(moved is not None)
        if moved:
            self.move_note.setText(
                f"This row will be written to {moved[0]}/{moved[1]}. Your "
                f"edits stay attached to it.")
        else:
            self.move_note.setText("")
        self._mark_edited()

    # -- editing ------------------------------------------------------------------

    def refresh_from_store(self) -> None:
        """
        Re-read the selected encounter row when this page comes back.

        One half now. It used to refresh two, because Unit Names sat behind
        a tab strip on this page where a stale half is invisible; that half
        is its own page and refreshes itself. See
        `widgets/visible_refresh.py`.
        """
        if self.current_address is None:
            return
        self.load_record(self.current_address)
        self._mark_edited()
        self._update_counter()

    def _on_field_edited(self) -> None:
        if self.current_address is None:
            return
        edits = self.state.entry_edits.setdefault(self.current_address, {})
        for field_name, row in self.rows.items():
            if row.included:
                edits[field_name] = row.get_value_str()
            elif field_name in edits:
                del edits[field_name]
        if not edits:
            self.state.entry_edits.pop(self.current_address, None)

        self._mark_edited()
        self._update_counter()
        self.edits_changed.emit()

    def _mark_edited(self) -> None:
        for i in range(self.list.count()):
            item = self.list.item(i)
            address = tuple(item.data(Qt.UserRole))
            mark_edited(item, bool(self.state.entry_edits.get(address))
                        or address in self.state.entry_rekeys)

    def _update_counter(self) -> None:
        total = self.list.count()
        if not total:
            self.counter.setText("")
            return
        edited = sum(1 for fields in self.state.entry_edits.values() if fields)
        self.counter.setText(edit_counter_text(edited, total, "encounters"))


    def _apply_view(self, hide_notes: bool, hide_unknown: bool,
                    hide_comments: bool) -> None:
        """
        One row container, now.

        This used to walk two and was once fixed for walking only one - the
        unit rows in `chara_rows` kept their notes with notes turned off,
        37 of 38 hiding, which looks exactly like it working. Those rows now
        live on `UnitNamesPage`, which walks its own. `audit_view_toggles`
        checks both pages.
        """
        apply_view_toggles(list(self.rows.values()),
                           hide_notes, hide_unknown, hide_comments)
