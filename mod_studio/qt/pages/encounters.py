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
    QPushButton, QScrollArea, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

from ... import constants as c
from ... import encounter_names
from ... import nxd_layouts
from ..widgets.actions import (
    page_intro,
    COPY_LANGUAGES_LABEL, COPY_LANGUAGES_NOTE, ViewToggles, apply_view_toggles,
    copy_edits_to_languages, ensure_language_loaded, mark_edited,
    language_order, set_empty_state)
from ..widgets.field_rows import CollapsibleSection, NumericFieldRow
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


class EncountersPage(QWidget):
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
            "Who turns up in each battle, as what job, with what equipment. "
            "Fields say how well understood they are - only the ones you tick "
            "are written into your mod."))

        # Every tab with field rows gets these, not just Jobs.
        self.view_toggles = ViewToggles()
        self.view_toggles.changed.connect(self._apply_view)
        # Hidden: the shell draws the one visible pair, above the tabs,
        # so it is in the same place on all ten. This instance still
        # receives the preference and still answers `state()`.
        self.view_toggles.follow_only()

        # Two tables, two lists, two sub-tabs.
        #
        # `OverrideEntryData` and `CharaName-xx` are both "encounters" to a
        # mod author but they are not two views of one record: one is keyed
        # by a `(Key, Key2)` pair and shared across languages, the other by
        # a plain key and stored once per language. They need separate
        # master-detail panes, which is why this is a tab strip rather than
        # the `CollapsibleSection` the rest of the interface uses for
        # grouping fields within a single record.
        #
        # The Tkinter tab has always been shaped this way. The Qt page only
        # ever built the first half - `chara_name_records` was in
        # `_LANGUAGE_TABLES` and read by nothing, so unit names could be
        # exported and migrated but never edited.
        self.tabs = QTabWidget()
        outer.addWidget(self.tabs, 1)

        entries_tab = QWidget()
        entries_column = QVBoxLayout(entries_tab)
        entries_column.setContentsMargins(0, 8, 0, 0)
        entries_column.setSpacing(10)
        self.tabs.addTab(entries_tab, "Encounters")

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

        self.move_button = QPushButton("Move")
        self.move_button.clicked.connect(self.move_current_row)
        move_row.addStretch(1)
        move_column.addLayout(move_row)

        move_buttons = QHBoxLayout()
        move_buttons.addWidget(self.move_button)

        self.undo_move_button = QPushButton("Undo move")
        self.undo_move_button.setEnabled(False)
        self.undo_move_button.clicked.connect(self.undo_move)
        move_buttons.addWidget(self.undo_move_button)
        move_buttons.addStretch(1)
        move_column.addLayout(move_buttons)

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

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
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

        self._build_names_tab()

        self._apply_view(*self.view_toggles.state())
        self.refresh_records()

    # -- Unit Names (CharaName-xx) ----------------------------------------

    def _build_names_tab(self) -> None:
        """
        The per-language unit name table, which the Qt page never read.

        `CharaName-xx` is what puts a name on a unit an encounter row
        summons, and `Unknown4` on the encounter row points into it - which
        is why `is_unknown_field` judges the label rather than the column
        name: that column holds a confirmed unit name.

        Loaded lazily through `ensure_language_loaded`, one language at a
        time, exactly as the other three per-language tables now do. Reading
        English only is the bug this project already fixed once, when every
        non-English language came up blank on pages that had the data
        available and never asked for it.
        """
        names_tab = QWidget()
        column = QVBoxLayout(names_tab)
        column.setContentsMargins(0, 8, 0, 0)
        column.setSpacing(10)
        self.tabs.addTab(names_tab, "Unit Names")

        self.chara_rows: dict[str, QWidget] = {}
        self.current_chara_key = None

        top = QHBoxLayout()
        self.chara_counter = QLabel("")
        self.chara_counter.setProperty("role", "ok")
        self.chara_counter.setWordWrap(True)
        top.addWidget(self.chara_counter, 1)
        top.addWidget(QLabel("Language:"))
        self.language_box = QComboBox()
        self.language_box.addItems(language_order())
        self.language_box.currentTextChanged.connect(self._on_language)
        top.addWidget(self.language_box)
        self.copy_button = QPushButton(COPY_LANGUAGES_LABEL)
        self.copy_button.setToolTip(COPY_LANGUAGES_NOTE)
        self.copy_button.clicked.connect(self.copy_current_to_languages)
        top.addWidget(self.copy_button)
        self.language_controls = QWidget()
        self.language_controls.setLayout(top)
        column.addWidget(self.language_controls)

        self.action_note = QLabel("")
        self.action_note.setProperty("role", "muted")
        self.action_note.setWordWrap(True)
        column.addWidget(self.action_note)

        split = QHBoxLayout()
        split.setSpacing(14)

        left = QVBoxLayout()
        self.chara_search = QLineEdit()
        self.chara_search.setPlaceholderText("Search by name or ID")
        self.chara_search.setClearButtonEnabled(True)
        self.chara_search.textChanged.connect(self._filter_chara_list)
        left.addWidget(self.chara_search)
        self.chara_list = QListWidget()
        self.chara_list.setFixedWidth(300)
        self.chara_list.currentItemChanged.connect(self._on_chara_selection)
        left.addWidget(self.chara_list, 1)
        split.addLayout(left)

        right = QVBoxLayout()
        self.chara_editing_label = QLabel("Select a unit name")
        self.chara_editing_label.setStyleSheet(
            "font-weight: 600; font-size: 12pt;")
        right.addWidget(self.chara_editing_label)

        self.chara_empty_note = QLabel(
            "No game data yet.\n\nGo to General Setup and unpack your game, "
            "or point at a folder you've already unpacked.")
        self.chara_empty_note.setProperty("role", "muted")
        self.chara_empty_note.setWordWrap(True)
        self.chara_empty_note.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        right.addWidget(self.chara_empty_note)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        holder = QWidget()
        form = QVBoxLayout(holder)
        form.setContentsMargins(4, 4, 4, 4)
        form.setSpacing(2)

        body = QWidget()
        body_column = QVBoxLayout(body)
        body_column.setContentsMargins(0, 0, 0, 0)
        body_column.setSpacing(2)

        # Field order follows the Tkinter tab: the name first, because it is
        # the reason anybody opened this, then the two numeric/flag fields,
        # then the Comment - which is FF16Tools' own note about the row and
        # not game data, so it is labelled as such rather than presented as
        # something the game reads.
        self.chara_rows["Name"] = TextFieldRow("Name", "Name")
        body_column.addWidget(self.chara_rows["Name"])

        low, high, label, note = c.CHARANAME_NUMERIC_FIELDS["DLCFlags"]
        self.chara_rows["DLCFlags"] = NumericFieldRow(
            "DLCFlags", label, low, high, note)
        body_column.addWidget(self.chara_rows["DLCFlags"])

        bool_label, bool_note = c.CHARANAME_BOOL_FIELDS["IsGeneric"]
        self.chara_rows["IsGeneric"] = BoolFieldRow(
            "IsGeneric", bool_label, bool_note)
        body_column.addWidget(self.chara_rows["IsGeneric"])

        # Just "Comment", with the caveat in a tooltip. The full sentence
        # does not fit the 200px label column every field row uses, and a
        # label clipped mid-word ("Comment (FF16Tools' own note, not") reads
        # as a rendering fault rather than as a truncated explanation. The
        # Items tab clips the same string; it is shortened there too.
        self.chara_rows["Comment"] = TextFieldRow("Comment", "Comment")
        self.chara_rows["Comment"].label.setToolTip(COMMENT_TOOLTIP)
        body_column.addWidget(self.chara_rows["Comment"])

        for row in self.chara_rows.values():
            row.edited.connect(self._on_chara_field_edited)

        self.chara_sections = [
            CollapsibleSection("Unit name", body, expanded=True)]
        form.addWidget(self.chara_sections[0])
        form.addStretch(1)
        scroll.setWidget(holder)
        self.chara_scroll = scroll
        right.addWidget(scroll, 1)
        split.addLayout(right, 1)
        column.addLayout(split, 1)

    @property
    def language(self) -> str:
        return self.language_box.currentText() or "en"

    def _on_language(self, _text: str) -> None:
        """
        Switches language without disturbing the selection.

        `refresh_records()` is NOT used here, and that is the point: it
        clears the list and selects row 0, so changing language threw the
        author off whatever record they were editing and back to the first
        one. Items fixed this some sessions ago; the Unit Names panel kept the old
        shape.

        Relabelling the rows in place and reloading the current record does
        the whole job, because only the TEXT differs between languages -
        everything else on the record is shared.

        Switching language must never tick a field either. Loading a record
        never sets an include box, and neither does this: per-field opt-in
        is what stops two mods claiming a value neither meant to.
        """
        ensure_language_loaded(self.state, "chara_name_records", self.language)
        # A full rebuild only when the row SET could differ - the list being
        # empty, or a different length. Relabelling assumes the two language
        # tables hold the same keys, which they do in every real conversion;
        # this is the check that stops that assumption silently showing an
        # empty tab if it ever fails.
        if self.chara_list.count() != len(self.chara_records()):
            self.refresh_chara_records()
            return
        by_key = {r.key: r for r in self.chara_records()}
        for i in range(self.chara_list.count()):
            item = self.chara_list.item(i)
            key = item.data(Qt.UserRole)
            record = by_key.get(key)
            name = (record.values.get("Name") if record else "") or "(unnamed)"
            item.setText(f"{key:03d} - {name}")
        self._mark_chara_edited()
        self._update_chara_counter()
        if self.current_chara_key is not None:
            self.load_chara_record(self.current_chara_key)

    def chara_records(self) -> list:
        return (self.state.chara_name_records or {}).get(self.language, [])

    def refresh_chara_records(self) -> None:
        ensure_language_loaded(self.state, "chara_name_records", self.language)
        self.chara_list.clear()
        records = self.chara_records()
        for record in records:
            name = record.values.get("Name") or "(unnamed)"
            item = QListWidgetItem(f"{record.key:03d} - {name}")
            item.setData(Qt.UserRole, record.key)
            self.chara_list.addItem(item)
        has_data = bool(records)
        set_empty_state(
            self.chara_empty_note, has_data,
            self.chara_scroll, self.chara_search, self.chara_list,
            self.chara_editing_label, self.language_controls)
        self._mark_chara_edited()
        self._update_chara_counter()
        if self.chara_list.count():
            self.chara_list.setCurrentRow(0)

    def _filter_chara_list(self, text: str) -> None:
        needle = text.strip().lower()
        for i in range(self.chara_list.count()):
            item = self.chara_list.item(i)
            item.setHidden(bool(needle) and needle not in item.text().lower())

    def _on_chara_selection(self, current, _previous) -> None:
        if current is not None:
            self.load_chara_record(current.data(Qt.UserRole))

    def load_chara_record(self, key: int) -> None:
        by_key = {r.key: r for r in self.chara_records()}
        record = by_key.get(key)
        if record is None:
            return
        self.current_chara_key = key
        name = record.values.get("Name") or "(unnamed)"
        self.chara_editing_label.setText(f"Editing: {key:03d} - {name}")

        already = (self.state.chara_name_edits.get(self.language, {})
                   .get(key, {}))
        for field_name, row in self.chara_rows.items():
            if field_name in already:
                row.load(already[field_name], True)
            else:
                row.load(record.values.get(field_name, ""), False)

    def _on_chara_field_edited(self) -> None:
        if self.current_chara_key is None:
            return
        language = self.state.chara_name_edits.setdefault(self.language, {})
        edits = language.setdefault(self.current_chara_key, {})
        for field_name, row in self.chara_rows.items():
            if row.included:
                edits[field_name] = row.get_value_str()
            elif field_name in edits:
                del edits[field_name]
        if not edits:
            language.pop(self.current_chara_key, None)

        self._mark_chara_edited()
        self._update_chara_counter()
        self.edits_changed.emit()

    def copy_current_to_languages(self) -> None:
        """
        This row's non-text fields into the other six languages.

        `CHARA_TEXT_FIELDS` is `Name` and `Comment`, and neither travels - a
        unit's name is exactly the thing that needs translating, and copying
        it would produce a mod shipping English text in the Japanese table
        that nothing downstream could distinguish from a real translation.
        """
        if self.current_chara_key is None:
            self.action_note.setText("Pick a unit name first.")
            return
        changed = copy_edits_to_languages(
            self.state.chara_name_edits, self.language,
            self.current_chara_key, c.NXD_LANGUAGES,
            skip_fields=CHARA_TEXT_FIELDS)
        if changed:
            labels = ", ".join(c.NXD_LANGUAGE_LABELS[lang]
                               for lang in changed)
            self.action_note.setText(f"Copied to {labels}.")
            self.edits_changed.emit()
        else:
            # Distinguishes "nothing ticked" from "only text was ticked",
            # because the second looks like the button failing.
            self.action_note.setText(
                "Nothing to copy - tick a field that isn't Name or Comment "
                "first.")
        self._update_chara_counter()

    def _mark_chara_edited(self) -> None:
        edits = self.state.chara_name_edits.get(self.language, {})
        for i in range(self.chara_list.count()):
            item = self.chara_list.item(i)
            mark_edited(item, bool(edits.get(item.data(Qt.UserRole))))

    def _update_chara_counter(self) -> None:
        total = self.chara_list.count()
        if not total:
            self.chara_counter.setText("")
            return
        edited = self.state.edited_chara_name_count(self.language)
        label = c.NXD_LANGUAGE_LABELS[self.language]
        self.chara_counter.setText(
            f"{edited} of {total} unit names edited in {label}")

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
        row = NumericFieldRow(field_name, label, 0, 65535, note, unknown=unknown)
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
        # Both halves of this tab refresh together. Unit names arrive from
        # the same conversion the encounter rows do.
        self.refresh_chara_records()

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
        self.counter.setText(f"{edited} of {total} encounter rows edited")


    def _apply_view(self, hide_notes: bool, hide_unknown: bool) -> None:
        """
        BOTH row containers.

        This walked `self.rows` only, so the unit rows in `self.chara_rows`
        kept their notes with notes turned off - "Generic Unit" was the one
        that showed. The identical fault to the one Jobs was fixed for, in
        the container next door, and invisible unless somebody counted:
        37 of 38 notes hid, which looks exactly like it working.

        Found by `dev/audit_view_toggles.py`, which was written for a
        different page and turned this up on its first run.
        """
        apply_view_toggles(
            list(self.rows.values()) + list(self.chara_rows.values()),
            hide_notes, hide_unknown)
