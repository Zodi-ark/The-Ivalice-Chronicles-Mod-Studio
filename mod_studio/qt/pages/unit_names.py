"""
The per-language unit name table, `CharaName-<lang>`.

### Why this is its own page

It used to be the second tab of a `QTabWidget` on the Encounters page.
`OverrideEntryData` and `CharaName-xx` are both "encounters" to a mod
author, but they are not two views of one record: one is keyed by a
`(Key, Key2)` pair and shared across languages, the other by a plain key and
stored once per language. They needed separate master-detail panes, separate
stores and separate counters, and a tab strip inside a tab was the only
thing holding them together.

Two costs came with that. The sidebar - which is the tool's whole navigation
model - could not reach the second half at all, so "Unit Names" was
invisible until you found the strip. And a page carrying two editors behind
a tab strip has a half that is on screen and a half that is NOT, which is
where the stale-page fault hides: `EncountersPage.refresh_from_store` had to
refresh both, and `_apply_view` had to be fixed once to walk both row
containers after only walking one.

Split, each page refreshes itself and the sidebar names both.

The members are still called `chara_*` - `chara_list`, `chara_rows`,
`chara_editing_label`. Renaming them would touch every line in here for no
behavioural gain, and `chara_name_records` is what the STATE calls this
table, so the names still match the thing they hold.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QVBoxLayout, QWidget,
)

from ... import constants as c
from ..widgets.actions import (
    page_intro,
    COPY_LANGUAGES_LABEL, COPY_LANGUAGES_NOTE, TransientNote, ViewToggles,
    apply_view_toggles, copy_all_records_to_languages,
    copy_edits_to_languages, ensure_language_loaded, mark_edited,
    language_combo, language_order, set_empty_state, edit_counter_text)
from ..widgets.field_rows import CollapsibleSection, NumericFieldRow
from ..widgets.form_scroll import FormScrollArea
from ..widgets.visible_refresh import RefreshesWhenVisible
from .encounters import CHARA_TEXT_FIELDS, COMMENT_TOOLTIP
from .poaching import BoolFieldRow, TextFieldRow


class UnitNamesPage(RefreshesWhenVisible, QWidget):
    edits_changed = Signal()

    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state
        self.chara_rows: dict[str, QWidget] = {}
        self.current_chara_key = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 10, 24, 20)
        outer.setSpacing(10)
        # Every page with field rows gets these, not just Jobs. Hidden -
        # the shell draws the one visible pair - but it still receives the
        # preference and still answers `state()`.
        self.view_toggles = ViewToggles()
        self.view_toggles.changed.connect(self._apply_view)
        self.view_toggles.follow_only()

        self._column = QVBoxLayout()
        self._column.setContentsMargins(0, 0, 0, 0)
        self._column.setSpacing(10)
        outer.addLayout(self._column, 1)
        self._build()
        # AFTER `_build`, because the description row carries the language
        # picker and Copy button and `_build` is what creates them. Inserted
        # at 0 so it is still the page's first row.
        outer.insertLayout(0, page_intro(
            "The name each unit shows throughout the UI. Encounters unit "
            "name fields point at these.",
            self.language_controls))
        self._apply_view(*self.view_toggles.state())
        self.refresh_records()

    def refresh_from_store(self) -> None:
        """
        Re-read the selected unit name when this page comes back on screen.

        Its own now, rather than half of the Encounters page's. See
        `widgets/visible_refresh.py`: a row loaded before another page's
        edit has its include ticks off, and the rewrite in
        `_on_chara_field_edited` deletes every field whose tick is off.
        """
        if self.current_chara_key is None:
            return
        self.load_chara_record(self.current_chara_key)
        self._mark_chara_edited()
        self._update_chara_counter()

    def _apply_view(self, hide_notes: bool, hide_unknown: bool,
                    hide_comments: bool) -> None:
        """
        Shows or hides rows to match the toggles.

        Walks `chara_rows` - the only row container this page has. The
        Encounters page had two and was fixed once for walking only one;
        splitting is what makes that class of mistake impossible here.
        """
        apply_view_toggles(list(self.chara_rows.values()),
                           hide_notes, hide_unknown, hide_comments)

    def _build(self) -> None:
        """
        The per-language unit name table.

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
        column = self._column

        self.chara_rows: dict[str, QWidget] = {}
        self.current_chara_key = None

        # The language picker and Copy button go on the DESCRIPTION line,
        # which is where every other per-language tab puts them - Jobs, Job
        # Commands, Abilities, Items, Poaching. This page inherited them
        # from the Encounters sub-tab, where they sat on their own row below
        # the description with the counter beside them, so the two pages
        # disagreed with the other five about where to look. Reported from
        # real use.
        #
        # The counter comes OUT of this row for the same reason: on the
        # other tabs it is its own line under the description, and leaving
        # it here would have kept this page a line out of step even after
        # the controls moved.
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.addWidget(QLabel("Language:"))
        # Through the shared builder, which is what the other four pages
        # now use. This page set neither a size policy nor a minimum, so it
        # sized itself to its contents and came out wider than every other
        # Language dropdown in the tool.
        self.language_box = language_combo()
        self.language_box.currentTextChanged.connect(self._on_language)
        top.addWidget(self.language_box)
        self.copy_button = QPushButton(COPY_LANGUAGES_LABEL)
        self.copy_button.setToolTip(COPY_LANGUAGES_NOTE)
        self.copy_button.clicked.connect(self.copy_current_to_languages)
        top.addWidget(self.copy_button)
        self.language_controls = QWidget()
        self.language_controls.setLayout(top)

        self.chara_counter = QLabel("")
        self.chara_counter.setProperty("role", "ok")
        self.chara_counter.setWordWrap(True)
        column.addWidget(self.chara_counter)

        # `TransientNote`, not a plain QLabel. An empty QLabel still takes a
        # full row plus the layout's spacing, so this page reserved a gap
        # for a sentence that only appears after Copy is pressed - putting
        # its search bar a line lower than every other tab's. That widget
        # exists because Abilities and Poaching had the identical fault.
        self.action_note = TransientNote()
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

        scroll = FormScrollArea()
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
            self.refresh_records()
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

    def refresh_records(self) -> None:
        """
        Re-read the unit name list.

        Named `refresh_records`, which is the name the shell asks every page
        for after the game is unpacked. It was `refresh_chara_records` when
        this was half of the Encounters page, and Encounters called it from
        its own `refresh_records` - so splitting the page silently
        disconnected it and Unit Names said "No game data yet" forever, even
        after a successful unpack. `app.py`'s own comment at that loop
        describes this exact fault happening twice before; this was the
        third, and the split is what caused it.
        """

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
        self.chara_counter.setText(
            edit_counter_text(edited, total, "unit names"))

