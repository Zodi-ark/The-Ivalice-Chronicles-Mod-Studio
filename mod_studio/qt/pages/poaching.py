"""
Edit Game Data / Poaching.

The carcasses a poached monster leaves, what they sell for, and what item
they produce. Unlike the XML tables, this one lives in the converted
database and is per-language: there is a `poachitem.<lang>.nxd` for each of
en, ja, de, fr and cs, and a name edited in one is not a name edited in
another.

One rule here is load-bearing and easy to lose:

**Produced Item's empty value is 0, not -1.**

Every other id reference in this tool uses -1 for "inherit / not set", and
copying that habit here would write a broken mod file - -1 is not a valid
ItemData id. The real empty selection is `(0) None`. The Tkinter interface
has a whole subclass, `PoachItemRefRow`, existing only to remove the -1
entry its base class offers. That is the kind of detail a rewrite drops by
being consistent, so it is asserted rather than remembered.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QPushButton, QVBoxLayout, QWidget,
    QSizePolicy,
)

from ... import constants as c
from ... import nxd_layouts
from ..widgets import actions
from ..widgets.actions import (
    page_intro,
    TransientNote, record_name,
    COPY_LANGUAGES_LABEL, COPY_LANGUAGES_NOTE, ViewToggles,
    apply_view_toggles, language_order, set_empty_state,
    copy_edits_to_languages, ensure_language_loaded, mark_edited,
)
from ..widgets.field_rows import TextFieldRow as _TextFieldRow
from ..widgets.field_rows import (
    CollapsibleSection, DropdownFieldRow, NumericFieldRow,
)
from ..widgets.form_scroll import FormScrollArea

# The id that means "produces nothing". NOT -1 - see the module docstring.
PRODUCED_ITEM_NONE = 0


# Re-exported so `from .poaching import TextFieldRow` keeps working.
# The class itself now lives with every other row in
# `qt/widgets/field_rows.py`; Abilities, Items and Encounters all imported
# it from here, which meant three pages depended on a fourth page for a
# widget that has nothing to do with poaching.
TextFieldRow = _TextFieldRow


class BoolFieldRow(NumericFieldRow):
    """A 0/1 field shown as a tick rather than a number."""

    def __init__(self, field_name: str, label: str, note: str = "", parent=None):
        super().__init__(field_name, label, 0, 1, note, parent=parent)
        self.value.setVisible(False)
        self.state_box = QCheckBox()
        self.state_box.toggled.connect(
            lambda on: self.value.setValue(1 if on else 0))
        self.layout().insertWidget(2, self.state_box)

    def load(self, raw_value, included: bool) -> None:
        super().load(raw_value, included)
        self._loading = True
        try:
            self.state_box.setChecked(bool(int(self.value.value())))
        finally:
            self._loading = False


class PoachingPage(QWidget):
    edits_changed = Signal()

    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state
        self.current_key = None
        self.rows: dict[str, QWidget] = {}
        # id -> name, for the note beside Produced Item. Filled by
        # `set_item_choices`; used to describe, not to restrict.
        self._item_names: dict = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 10, 24, 20)
        outer.setSpacing(10)

        # The blurb's line carries the language controls, right-aligned.
        #
        # They were on the HEADING's line, and the heading has moved to the
        # shell so that it sits on the view toggles' line - which is what
        # closed the empty band across the top of every editing tab. The
        # controls could not follow it there: the toggles are already at
        # that line's right-hand end, and two right-aligned groups on one
        # line is a collision, not a layout.
        #
        # So they drop to the next line, which is the blurb's. Measured,
        # that moves them about seven pixels down the page and not at all
        # across it, which is as close to "where they are now" as the two
        # constraints allow. A line of their own was the alternative and it
        # simply reopens the band one row lower.

        top = QHBoxLayout()
        top.addWidget(QLabel("Language:"))
        self.language_box = QComboBox()
        # English first - sorting the whole list put "cs" at the top, so the
        # page opened on Czech and looked empty for anyone whose game data
        # only has English unpacked. `language_order` keeps that and also
        # makes the ORDER match every other page's; this one used to run
        # en, cs, ct, de, fr, ja, ko while Items and Encounters ran the
        # game's own order.
        self.language_box.addItems(language_order(c.NXD_POACH_FILENAMES))
        self.language_box.currentTextChanged.connect(self._on_language)
        # The widest entry is two characters; a
        # minimum keeps the arrow from crowding it.
        self.language_box.setSizePolicy(
            QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.language_box.setMinimumWidth(72)
        top.addWidget(self.language_box)

        # Numbers do not differ per language, so retyping a price five times
        # is pure friction. Copies the EDITS, not the record - only ticked
        # fields travel, or the copy would drag every untouched value into
        # the mod as well.
        #
        # ONE button, not two. There used to be a second, "Copy shared
        # fields for every edit", which did the same thing for every edited
        # record at once. Two buttons whose labels differ by four words and
        # whose effects differ by a whole table is a choice nobody can make
        # correctly from the label, and the bulk one is the more destructive
        # of the pair - it writes into six language tables for every record
        # touched in the session, with no undo. The per-record copy is the
        # safe primitive, and it is what Items has always offered.
        self.copy_button = QPushButton(COPY_LANGUAGES_LABEL)
        self.copy_button.setToolTip(COPY_LANGUAGES_NOTE)
        self.copy_button.clicked.connect(self.copy_current_to_languages)
        self.copy_button.setSizePolicy(
            QSizePolicy.Fixed, QSizePolicy.Fixed)
        top.addWidget(self.copy_button)

        # No trailing stretch.
        #
        # There was one, so the row read: counter, stretch, controls,
        # stretch - which centres the controls in whatever space is left and
        # leaves them floating in the middle of the page instead of sitting
        # against the right edge like every other tab's.
        # The language picker and the copy button in one container, so they
        # go away together when there is nothing loaded. A language box
        # offering to switch between seven empty tables, and a copy button
        # attached to no record, both read as a broken page rather than an
        # empty one.
        self.language_controls = QWidget()
        top.setContentsMargins(0, 0, 0, 0)
        self.language_controls.setLayout(top)
        # Sized to what it holds, not to whatever the row has spare. Left
        # to fill, the combo ran to 540px and the copy button to 545px on a
        # 1920 window - a language picker the width of six words.
        self.language_controls.setSizePolicy(QSizePolicy.Maximum,
                                             QSizePolicy.Preferred)
        outer.addLayout(page_intro(
            "What a poached monster leaves behind, and what it's worth. Names "
            "and descriptions are per-language - pick the language first.", self.language_controls))

        self.action_note = TransientNote()
        # Added once. It used to be added before AND after `top`, so the
        # first add was silently undone by the second when Qt reparented it.
        outer.addWidget(self.action_note)

        # On their own line here, unlike Jobs and the generic table tabs.
        #
        # They were briefly moved up onto the row above, which on those two
        # pages holds only a record counter and had room. This row holds a
        # language picker and two "Copy ... to all languages" buttons, and a
        # screenshot at the 1100 minimum showed the result: the buttons
        # clipped to "opy this one to all language" and the toggles to "Hide
        # unknown". A placement that works on one page is not a placement.
        #
        # A line of their own is no longer the full-width bar it was, since
        # ViewToggles is now sized to its contents rather than stretching -
        # so this reads as a small pair tucked under the controls, which is
        # what the Tkinter interface does with them.
        self.view_toggles = ViewToggles()
        self.view_toggles.changed.connect(self._apply_view)
        # Hidden: the shell draws the one visible pair, above the tabs,
        # so it is in the same place on all ten. This instance still
        # receives the preference and still answers `state()`.
        self.view_toggles.follow_only()

        split = QHBoxLayout()
        split.setSpacing(14)

        left = QVBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search by name or ID")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter_list)
        left.addWidget(self.search)
        self.list = QListWidget()
        self.list.setFixedWidth(280)
        self.list.currentItemChanged.connect(self._on_selection)
        left.addWidget(self.list, 1)
        split.addLayout(left)

        right = QVBoxLayout()
        self.editing_label = QLabel("Select a carcass")
        self.editing_label.setStyleSheet("font-weight: 600; font-size: 12pt;")
        right.addWidget(self.editing_label)

        self.empty_note = QLabel(
            "No game data yet.\n\nGo to General Setup and unpack your game, or "
            "point at a folder you've already unpacked.")
        self.empty_note.setProperty("role", "muted")
        self.empty_note.setWordWrap(True)
        # Top-left, where the content it stands in for would start. This was
        # `AlignCenter` with a stretch, which parked the message in the dead
        # centre of the window. Textures and Sounds have always used
        # `AlignTop`; see `set_empty_state`.
        self.empty_note.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        right.addWidget(self.empty_note)

        scroll = FormScrollArea()
        holder = QWidget()
        form = QVBoxLayout(holder)
        form.setContentsMargins(4, 4, 4, 4)
        form.setSpacing(2)

        text_body = QWidget()
        text_column = QVBoxLayout(text_body)
        text_column.setContentsMargins(0, 0, 0, 0)
        text_column.setSpacing(2)
        for field_name in c.POACH_TEXT_FIELDS:
            row = TextFieldRow(field_name, field_name)
            row.edited.connect(self._on_field_edited)
            self.rows[field_name] = row
            text_column.addWidget(row)

        numbers_body = QWidget()
        numbers_column = QVBoxLayout(numbers_body)
        numbers_column.setContentsMargins(0, 0, 0, 0)
        numbers_column.setSpacing(2)
        for field_name, spec in c.POACH_NUMERIC_FIELDS.items():
            low, high, label = spec[0], spec[1], spec[2]
            note = spec[3] if len(spec) > 3 else ""
            if field_name == "ProducedItemId":
                # A NUMBER you type, with the item it points at named beside
                # it - not a dropdown.
                #
                # It was a `DropdownFieldRow`, which meant the only items
                # offerable were the ones already in the reference list. A
                # poached carcass produces an item by id, and a mod author
                # editing what item 33 IS still wants to point a carcass at
                # 33; a picker that lists the vanilla name for every id gets
                # in the way of exactly the person this field is for. Zodi's
                # call, and it matches how `EffectId` on Abilities stayed a
                # number for the same reason.
                #
                # -1 is still not reachable: the range starts at 0, because
                # -1 is not a valid ItemData id here and writing it would
                # produce a broken mod file. 0 means "none" and is the
                # default.
                row = NumericFieldRow(
                    field_name, label, max(low, 0), high, note)
            else:
                row = NumericFieldRow(
                    field_name, label, low, high, note,
                    unknown=field_name.lower().startswith("unknown"))
            row.edited.connect(self._on_field_edited)
            if field_name == "ProducedItemId":
                # Live, as it is typed - not only when the record loads.
                row.edited.connect(self._describe_produced_item)
            self.rows[field_name] = row
            numbers_column.addWidget(row)

        for field_name, (label, note) in c.POACH_BOOL_FIELDS.items():
            row = BoolFieldRow(field_name, label, note)
            row.edited.connect(self._on_field_edited)
            if field_name == "ProducedItemId":
                # Live, as it is typed - not only when the record loads.
                row.edited.connect(self._describe_produced_item)
            self.rows[field_name] = row
            numbers_column.addWidget(row)

        self.sections = [
            CollapsibleSection("Names and description", text_body, expanded=True),
            CollapsibleSection("Numbers", numbers_body, expanded=False),
        ]
        for section in self.sections:
            form.addWidget(section)
        form.addStretch(1)
        scroll.setWidget(holder)
        self.scroll = scroll
        right.addWidget(scroll, 1)
        split.addLayout(right, 1)

                # The counter goes on a line of its OWN, directly above the body.
        #
        # It used to share the language row, and a QLabel in a QHBoxLayout
        # beside a QComboBox and a QPushButton is sized by THEM: measured on
        # the real window, the counter was 28px tall here and 16px on Jobs,
        # Job Commands, Equip Bonus and Treasure Hunter, sitting 20px below
        # the blurb instead of 11px. That is the whole of the "spacing is
        # different on pages with a language picker" report - the label was
        # being vertically centred inside a taller row.
        #
        # On its own line it is the same widget in the same place as on the
        # four pages that have no language picker, so the rhythm matches by
        # construction rather than by two numbers being kept in step.
        self.counter = QLabel("")
        self.counter.setProperty("role", "ok")
        self.counter.setWordWrap(True)
        outer.addWidget(self.counter)

        outer.addLayout(split, 1)
        self._apply_view(*self.view_toggles.state())
        self.refresh_records()

    # -- records --------------------------------------------------------------

    @property
    def language(self) -> str:
        return self.language_box.currentText() or "en"

    def records(self) -> list:
        return (self.state.poach_records or {}).get(self.language, [])

    def set_item_choices(self, id_to_name: dict) -> None:
        """
        Remembers the item names, for the note beside Produced Item.

        The field is a number now rather than a dropdown, so these are used
        to SAY what the number points at instead of to restrict what can be
        typed. -1 is dropped: it is not a valid ItemData id here.
        """
        self._item_names = {k: v for k, v in dict(id_to_name).items()
                            if k != -1}
        self._describe_produced_item()

    def _refresh_item_names(self) -> None:
        """
        Re-reads the item names from the loaded tables.

        `set_item_choices` was the only way these ever arrived, and
        **nothing in the application called it** - only the test suite did.
        So `_item_names` was empty on every real run and the note beside
        Produced Item read "not in the item list loaded here" for every id,
        including the 260 that are plainly in the vanilla table. It was
        reported as a puzzling message; it was a page waiting to be handed
        something no caller sent.

        Pulled rather than pushed, so there is no wiring to forget. The
        page already refreshes on `setup_changed`, and this rides along
        with it.
        """
        names = actions.item_names_by_id(self.state)
        if names:
            self._item_names = names

    def _describe_produced_item(self) -> None:
        """
        Names the item the Produced Item id points at, live as it is typed.

        Without this the field is a bare number and the author has to hold
        the whole item table in their head.
        """
        row = self.rows.get("ProducedItemId")
        if row is None:
            return
        value = row.value.value()
        if value == PRODUCED_ITEM_NONE:
            row.set_note("Nothing - this carcass produces no item.")
            return
        name = (self._item_names or {}).get(value)
        if name:
            row.set_note(f"Item {value}: {name}")
            return
        # Two different situations, and they need different sentences.
        #
        # With no items loaded at all the tool cannot name ANY id, and
        # saying the item is missing would be a lie about the mod. With the
        # table loaded, an id nothing answers to is a real mistake worth
        # seeing - and also the ordinary state of a mod that adds items,
        # which is why it is phrased as a fact rather than an error.
        if not self._item_names:
            row.set_note(
                f"Item {value} - unpack your game files on General Setup to "
                f"see which item this is.")
        else:
            # Deliberately says nothing about how many items the GAME has.
            # That would be a claim about vanilla, and the whole point of
            # this tool is that the table in front of the reader may not be
            # vanilla any more.
            row.set_note(
                f"Item {value} - no item with this id in the game data "
                f"loaded here.")

    def refresh_records(self) -> None:
        # The item names come from the same tables the list does, so
        # they arrive at the same moment rather than never.
        self._refresh_item_names()
        self.list.clear()
        records = self.records()
        for record in records:
            name = record_name(record) or "(unnamed)"
            item = QListWidgetItem(f"{record.key:03d} - {name}")
            item.setData(Qt.UserRole, record.key)
            self.list.addItem(item)
        has_data = bool(records)
        # The list, its search box, and the language controls all go. An
        # empty list box next to a "no game data yet" message is furniture
        # for browsing nothing.
        set_empty_state(
            self.empty_note, has_data,
            self.scroll, self.search, self.list, self.editing_label,
            self.language_controls, self.counter)
        self._mark_edited()
        self._update_counter()
        if self.list.count():
            self.list.setCurrentRow(0)

    def _on_language(self, _text: str) -> None:
        """
        Switches language without disturbing the selection.

        `refresh_records()` is NOT used here, and that is the point: it
        clears the list and selects row 0, so changing language threw the
        author off whatever record they were editing and back to the first
        one. Items fixed this some sessions ago; Poaching kept the old
        shape.

        Relabelling the rows in place and reloading the current record does
        the whole job, because only the TEXT differs between languages -
        everything else on the record is shared.

        Switching language must never tick a field either. Loading a record
        never sets an include box, and neither does this: per-field opt-in
        is what stops two mods claiming a value neither meant to.
        """
        # Reads this language's table if nothing has yet - the Qt setup
        # loads English only, so without this every field came up blank for
        # any other language.
        ensure_language_loaded(self.state, "poach_records", self.language)
        # A full rebuild only when the row SET could differ - the list being
        # empty, or a different length. Relabelling assumes the two language
        # tables hold the same keys, which they do in every real conversion;
        # this is the check that stops that assumption silently showing an
        # empty tab if it ever fails.
        if self.list.count() != len(self.records()):
            self.refresh_records()
            return
        by_key = {r.key: r for r in self.records()}
        for i in range(self.list.count()):
            item = self.list.item(i)
            key = item.data(Qt.UserRole)
            record = by_key.get(key)
            name = (record_name(record) if record else "") or "(unnamed)"
            item.setText(f"{key:03d} - {name}")
        self._mark_edited()
        self._update_counter()
        if self.current_key is not None:
            self.load_record(self.current_key)

    def _filter_list(self, text: str) -> None:
        needle = text.strip().lower()
        for i in range(self.list.count()):
            item = self.list.item(i)
            item.setHidden(bool(needle) and needle not in item.text().lower())

    def _on_selection(self, current, _previous) -> None:
        if current is not None:
            self.load_record(current.data(Qt.UserRole))

    def load_record(self, key: int) -> None:
        by_key = {r.key: r for r in self.records()}
        record = by_key.get(key)
        if record is None:
            return
        self.current_key = key
        name = record_name(record) or "(unnamed)"
        self.editing_label.setText(f"Editing: {key:03d} - {name}")

        already = (self.state.poach_edits.get(self.language, {})
                   .get(key, {}))
        for field_name, row in self.rows.items():
            if field_name in already:
                row.load(already[field_name], True)
            else:
                row.load(record.values.get(field_name, ""), False)

    # -- copying across languages -------------------------------------------

        # The note has to follow the record, not just the typing.
        self._describe_produced_item()

    def languages(self) -> list:
        return [self.language_box.itemText(i)
                for i in range(self.language_box.count())]

    # Which columns hold translations is a property of the table, so it is
    # read from Nenkai's layout rather than restated here.
    #
    # The list this replaces named Name, NameSingular, NamePlural, Name2,
    # Description and Comment. Five of those six DO NOT EXIST in PoachItem
    # - they were copied from a table that has them - and five columns that
    # do (Unknown8, UnknownC, Unknown10, Unknown14, Unknown18) were left
    # out. All 96 rows of all five differ between every pair of languages
    # in the shipped database, and Unknown18 holds the carcass
    # descriptions, so this button was overwriting the Japanese, French and
    # German text with English every time it was pressed.
    #
    # The old list stays as the fallback: if the layout is ever missing,
    # protecting the wrong six columns is bad, and protecting none of them
    # is destructive.
    COPY_SKIP_FIELDS = frozenset(
        nxd_layouts.translated_columns("PoachItem", c.POACH_TEXT_FIELDS))

    def copy_current_to_languages(self) -> None:
        if self.current_key is None:
            self.action_note.setText("Pick a carcass first.")
            return
        changed = copy_edits_to_languages(
            self.state.poach_edits, self.language, self.current_key,
            self.languages(), skip_fields=self.COPY_SKIP_FIELDS)
        self.action_note.setText(
            f"Copied this carcass's shared fields to {', '.join(changed)}. "
            f"Names and descriptions stay per-language." if changed
            else "Nothing on this carcass to copy - names and descriptions "
                 "are never copied between languages.")
        self._after_copy()

    def _after_copy(self) -> None:
        self._mark_edited()
        self._update_counter()
        self.edits_changed.emit()

    # -- editing ----------------------------------------------------------------

    def _on_field_edited(self) -> None:
        if self.current_key is None:
            return
        language = self.state.poach_edits.setdefault(self.language, {})
        edits = language.setdefault(self.current_key, {})
        for field_name, row in self.rows.items():
            if row.included:
                edits[field_name] = row.get_value_str()
            elif field_name in edits:
                del edits[field_name]
        if not edits:
            language.pop(self.current_key, None)
        if not language:
            self.state.poach_edits.pop(self.language, None)

        self._mark_edited()
        self._update_counter()
        self.edits_changed.emit()

    def _mark_edited(self) -> None:
        edits = self.state.poach_edits.get(self.language, {})
        for i in range(self.list.count()):
            item = self.list.item(i)
            mark_edited(item, bool(edits.get(item.data(Qt.UserRole))))

    def _update_counter(self) -> None:
        total = self.list.count()
        if not total:
            self.counter.setText("")
            return
        edited = sum(1 for fields
                     in self.state.poach_edits.get(self.language, {}).values()
                     if fields)
        self.counter.setText(
            f"{edited} of {total} carcasses edited in {self.language}")


    def _apply_view(self, hide_notes: bool, hide_unknown: bool,
                    hide_comments: bool) -> None:
        apply_view_toggles(self.rows.values(), hide_notes, hide_unknown,
                           hide_comments)
