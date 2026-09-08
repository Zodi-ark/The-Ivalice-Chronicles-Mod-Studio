"""
All Game Data - one editor for every table that has no tab of its own.

WHY THIS IS ONE PAGE AND NOT TWO HUNDRED
----------------------------------------
A converted game folder holds 562 tables. Ten of them have hand-built tabs
because they are what most mods change and they deserve real controls -
dropdowns of ability names, flag panels, icon previews. The other ~550 do
not, and the answer to that is not 550 more sidebar entries. It is one
destination with a search box, the same way an operating system does not
put every file in the menu bar.

So: curated tabs stay the polished path, and this is the everything-else
path. Both edit the same mod. Neither hides the other - a table that has
its own tab says so here and offers to go there, rather than quietly
letting someone edit the same rows through a worse interface.

WHY THIS NEEDED ALMOST NO NEW ENGINE
------------------------------------
The pieces were already here, built for the Game Updates Rebase feature:

  * General Setup already converts with `include_all=True`, so the working
    database already contains every table the game folder has.
  * `nxd_data.write_unmodelled_table_edits` has deliberately had no schema
    knowledge since it was written - "the columns come from the rows being
    written".
  * `state.unmodelled_table_edits` already flows through the export:
    `has_work`, `tables_to_convert`, `filenames_to_copy` and `apply_edits`
    all handle it, and `filenames_to_copy` already resolves an arbitrary
    table name back to its `.nxd`.
  * `migration.assess_unmodelled` already reviews these on a game update.

What was missing was a way to CREATE those edits directly instead of only
inheriting them from a rebase. That is all this page is. `read_any_table`
and `table_shape` were added as the reading counterparts to the writer, so
reads and writes agree about what identifies a row.

WHAT THIS PAGE DELIBERATELY DOES NOT DO
---------------------------------------
No guessing. Values are shown exactly as the converter produced them - no
JSON decoding, no flag unpacking, no friendly column names. The typed tabs
do those things because they know which columns need them. Doing it here,
on a table nobody has characterised, would corrupt data while looking
helpful. A row that reads `Flags12: [0,0]` is honest; a row that reads
`Flags12: Evadeable` on a table where that is not what the bytes mean is
not.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from ... import constants as c
from ... import item_xml_io as ix
from ... import nxd_data
from ... import paths
from ..widgets.actions import (
    TransientNote, mark_edited, page_intro, select_list_row, set_empty_state)
from ..widgets.field_rows import (
    CollapsibleSection, NumericFieldRow, TextFieldRow)

# Rows are loaded on demand, but a table with tens of thousands of rows
# would still build tens of thousands of list items. The cap is generous
# enough to cover every table in a vanilla conversion and is stated in the
# interface when it bites, rather than silently truncating.
MAX_ROWS = 5000

# Marks an XML table in the picker. Not a cosmetic label: `_is_xml` reads it
# to decide which store an edit belongs in, so the two kinds cannot end up
# in each other's.
XML_PREFIX = "XML · "

# Wide enough for a real value, not so wide the notes column vanishes.
NUMERIC_MIN = -2147483648
NUMERIC_MAX = 2147483647


class DataBrowserPage(QWidget):
    edits_changed = Signal()
    navigate_requested = Signal(str, object)

    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state
        self.table = None
        self.current_key = None
        self.rows_by_key = {}
        self.field_rows = {}
        self._loading = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 10, 24, 20)
        outer.setSpacing(10)

        # The table picker. Editable with a completer rather than a plain
        # dropdown, because 550 entries is not something anyone scrolls.
        picker = QHBoxLayout()
        picker.setContentsMargins(0, 0, 0, 0)
        picker.addWidget(QLabel("Table:"))
        self.table_box = QComboBox()
        self.table_box.setEditable(True)
        self.table_box.setInsertPolicy(QComboBox.NoInsert)
        self.table_box.setMinimumWidth(280)
        self.table_box.currentIndexChanged.connect(self._on_table_chosen)
        # Typing a table's name has to select it, not just leave the text in
        # the box. An editable combo fires currentIndexChanged when the
        # POPUP is used, but typing "JobType" in full and pressing nothing
        # left the page still showing the previous table with the new name
        # in the field - which reads as the picker being broken.
        self.table_box.editTextChanged.connect(self._on_table_typed)
        self.table_box.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        picker.addWidget(self.table_box)
        self.table_controls = QWidget()
        self.table_controls.setLayout(picker)
        self.table_controls.setSizePolicy(QSizePolicy.Maximum,
                                          QSizePolicy.Preferred)

        outer.addLayout(page_intro(
            "Every table in the game data, including the ones without their "
            "own tab. Pick a table, then a row. Only the fields you tick are "
            "written into your mod.",
            self.table_controls))

        self.action_note = TransientNote()
        outer.addWidget(self.action_note)

        counter_row = QHBoxLayout()
        counter_row.setContentsMargins(0, 0, 0, 0)
        counter_row.setSpacing(12)
        self.counter = QLabel("")
        self.counter.setProperty("role", "counter")
        counter_row.addWidget(self.counter)
        # What the selected table IS. Without it the page is a grid of
        # numbers with no way to tell a 49-row lookup from a 5000-row one,
        # or which file an edit will end up in.
        self.table_info = QLabel("")
        self.table_info.setProperty("role", "muted")
        counter_row.addWidget(self.table_info)
        counter_row.addStretch(1)
        outer.addLayout(counter_row)

        self.empty_note = QLabel(
            "No game data yet.\n\nGo to General Setup and unpack your game, "
            "or point at a folder you've already unpacked.")
        self.empty_note.setWordWrap(True)
        outer.addWidget(self.empty_note)

        split = QHBoxLayout()
        split.setSpacing(14)

        left = QVBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search rows")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter_list)
        left.addWidget(self.search)
        self.list = QListWidget()
        self.list.setFixedWidth(260)
        self.list.currentItemChanged.connect(self._on_selection)
        left.addWidget(self.list, 1)
        self.left_panel = QWidget()
        self.left_panel.setLayout(left)
        split.addWidget(self.left_panel)

        right = QVBoxLayout()
        self.editing_label = QLabel("Pick a table")
        self.editing_label.setStyleSheet("font-weight: 600; font-size: 12pt;")
        right.addWidget(self.editing_label)

        # A standing warning for tables that have a proper tab, with a way
        # to get there. Two routes to the same rows is a trap unless the
        # worse one points at the better one.
        self.curated_row = QHBoxLayout()
        self.curated_note = QLabel("")
        self.curated_note.setWordWrap(True)
        self.curated_row.addWidget(self.curated_note, 1)
        self.curated_button = QPushButton("Open that tab \u2192")
        self.curated_button.clicked.connect(self._go_to_curated)
        self.curated_row.addWidget(self.curated_button, 0)
        self.curated_holder = QWidget()
        self.curated_holder.setLayout(self.curated_row)
        right.addWidget(self.curated_holder)
        self.curated_holder.setVisible(False)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        holder = QWidget()
        self.form = QVBoxLayout(holder)
        self.form.setContentsMargins(4, 4, 4, 4)
        self.form.setSpacing(2)
        self.fields_holder = QWidget()
        self.fields_column = QVBoxLayout(self.fields_holder)
        self.fields_column.setContentsMargins(0, 0, 0, 0)
        self.fields_column.setSpacing(2)
        self.section = CollapsibleSection("Fields", self.fields_holder,
                                          expanded=True)
        self.form.addWidget(self.section)
        self.form.addStretch(1)
        scroll.setWidget(holder)
        self.scroll = scroll
        right.addWidget(scroll, 1)
        self.right_panel = QWidget()
        self.right_panel.setLayout(right)
        split.addWidget(self.right_panel, 1)
        outer.addLayout(split, 1)

    # -- which tables exist ---------------------------------------------------

    def _curated_tab_for(self, table: str):
        """
        The tab that owns this table, if one does.

        `CURATED_NXD_SPECS`, not `ALL_NXD_SPECS`. The registry now holds a
        spec for all 53 per-language tables, derived from their layouts -
        but only six of them have a tab. Reading the whole registry here
        would tell a person that `ZodiacStone` is "already editable on its
        own tab" and send them looking for one that does not exist, while
        quietly removing the only place it CAN be edited.

        The two shared tables are named because they have tabs and no
        per-language spec, not because anything here is hand-maintained:
        a table gaining a tab means gaining a curated spec, which is what
        this reads.
        """
        for spec in nxd_data.CURATED_NXD_SPECS.values():
            for lang in c.NXD_LANGUAGES:
                if spec.table(lang) == table:
                    return spec.label
        if table == c.NXD_OVERRIDE_ACTION_TABLE:
            return "Abilities"
        if table == c.NXD_OVERRIDE_ENTRY_TABLE:
            return "Encounters"
        return None

    def refresh_records(self) -> None:
        has_data = bool(getattr(self.state, "nxd_sqlite_path", None))
        set_empty_state(self.empty_note, has_data, self.table_controls,
                        self.left_panel, self.right_panel, self.counter)
        if not has_data:
            return
        try:
            tables = nxd_data.list_all_tables(self.state.nxd_sqlite_path)
        except Exception as exc:                              # noqa: BLE001
            self.action_note.setText(f"Couldn't list the tables: {exc}")
            return
        # The XML tables with no curated tab, listed first and prefixed.
        #
        # Same picker rather than a second page, because "which table do I
        # want" is one question and the answer happening to live in a
        # different file format is not the person's problem. The prefix is
        # there because `ItemOptionsData.xml` and `Item-en` are different
        # things and a bare list would not say so.
        tables = [XML_PREFIX + name
                  for name in sorted(self.state.derived_table_records or {})] + tables
        previous = self.table_box.currentText()
        self.table_box.blockSignals(True)
        self.table_box.clear()
        self.table_box.addItems(tables)
        self.table_box.blockSignals(False)
        if previous in tables:
            self.table_box.setCurrentText(previous)
        elif tables:
            self.table_box.setCurrentIndex(0)
        self._on_table_chosen()

    def _on_table_typed(self, text: str) -> None:
        index = self.table_box.findText((text or "").strip(),
                                        Qt.MatchFixedString)
        if index >= 0 and index != self.table_box.currentIndex():
            self.table_box.setCurrentIndex(index)
        elif index >= 0:
            self._on_table_chosen()

    def _on_table_chosen(self, *_args) -> None:
        table = self.table_box.currentText()
        if not table or table == self.table:
            if table:
                # The rows too, not just the counter.
                #
                # This branch exists so that re-choosing the table already
                # on screen does not reload it - the rows have not changed,
                # and rebuilding a 5000-row list to show the same thing is
                # wasteful. But the EDITS may well have changed: opening a
                # mod fills `unmodelled_table_edits` and then refreshes
                # every page, and the refresh lands here, on the same
                # table, and returned without re-marking. So a mod that
                # edits a table with no curated tab arrived with none of
                # its rows highlighted, while Items - whose refresh marks
                # unconditionally - showed its edits correctly. The page
                # could SEE the edits; it just never repainted the list.
                self._mark_edited()
                self._update_counter()
            return
        self.table = table
        self.current_key = None
        owner = self._curated_tab_for(table)
        self.curated_holder.setVisible(owner is not None)
        if owner:
            self.curated_note.setText(
                f"This table has its own tab - {owner} - with proper "
                f"controls, names instead of raw IDs, and per-language "
                f"handling. Editing it here writes the same rows, but you "
                f"will be typing numbers.")
            self.curated_button.setText(f"Open {owner} \u2192")
        self._load_table()

    def _go_to_curated(self) -> None:
        owner = self._curated_tab_for(self.table or "")
        if owner:
            self.navigate_requested.emit(owner, None)

    # -- rows -----------------------------------------------------------------

    @property
    def _is_xml(self) -> bool:
        return bool(self.table) and self.table.startswith(XML_PREFIX)

    @property
    def _xml_filename(self) -> str:
        return (self.table or "")[len(XML_PREFIX):]

    def _load_xml_table(self) -> None:
        """One of the XML tables, through a derived spec."""
        filename = self._xml_filename
        records = (self.state.derived_table_records or {}).get(filename, [])
        spec = ix.discover_specs(paths.bundled_data_dir()).get(filename)
        if spec is None:
            self.action_note.setText(
                f"No spec could be derived for {filename}.")
            return
        self.xml_spec = spec
        for record in records:
            self.rows_by_key[record.item_id] = dict(record.values)
            item = QListWidgetItem(record.display_name())
            item.setData(Qt.UserRole, record.item_id)
            self.list.addItem(item)
        self.table_info.setText(
            f"{len(records)} rows \u00b7 {len(spec.field_order)} fields "
            f"\u00b7 writes {filename}")
        # Every field is text: XML values are strings and the derived spec
        # deliberately does not know which are flags or booleans. Typing a
        # number into a text box writes the same characters the file had.
        self._build_fields(["Id"] + list(spec.field_order), ["Id"],
                           force_text=True)
        self._mark_edited()
        self._update_counter()
        if self.list.count():
            select_list_row(self.list, 0)
            self.load_row(self.list.item(0).data(Qt.UserRole))
        else:
            self.current_key = None
            self.editing_label.setText(f"{filename} has no rows")

    def _load_table(self) -> None:
        self.list.clear()
        self.rows_by_key = {}
        if self._is_xml:
            self._load_xml_table()
            return
        try:
            shape = nxd_data.table_shape(self.state.nxd_sqlite_path, self.table)
            rows = nxd_data.read_any_table(
                self.state.nxd_sqlite_path, self.table, limit=MAX_ROWS)
        except Exception as exc:                              # noqa: BLE001
            self.action_note.setText(f"Couldn't read {self.table}: {exc}")
            return
        self.shape = shape
        filename = self.table.replace("-", ".").lower() + ".nxd"
        self.table_info.setText(
            f"{shape['rows']} rows \u00b7 {len(shape['columns'])} columns "
            f"\u00b7 writes {filename}{self._language_note()}")
        for key, values in rows:
            self.rows_by_key[key] = values
            item = QListWidgetItem(self._row_label(key, values))
            item.setData(Qt.UserRole, key)
            self.list.addItem(item)
        if shape["rows"] > len(rows):
            self.action_note.setText(
                f"{self.table} has {shape['rows']} rows; showing the first "
                f"{len(rows)}.")
        self._build_fields(shape["columns"], shape["keys"])
        self._mark_edited()
        self._update_counter()
        if self.list.count():
            select_list_row(self.list, 0)
            # Explicitly, not just via the selection signal.
            #
            # `select_list_row(list, 0)` emits `currentItemChanged` only if
            # the current row CHANGES. Switching from one table to another
            # when both were sitting on row 0 changed nothing, so the form
            # and the "Editing:" label kept showing the previous table's
            # row while the list underneath showed the new table. Caught by
            # looking at a screenshot: the label read "1 - 治疗", a
            # Simplified Chinese ability name, above a list of JobType IDs.
            self.load_row(self.list.item(0).data(Qt.UserRole))
        else:
            self.current_key = None
            self.editing_label.setText(f"{self.table} has no rows")

    def _language_note(self) -> str:
        """
        " - English only, one of 7 language files", when that is the case.

        371 of the 577 tables in this picker are language variants of the
        same 53 tables: `Book-cs`, `Book-ct`, `Book-de` and four more are
        one table, seven times. Nothing said so, and the cost of not saying
        it is a specific, quiet mistake - a person edits `Book-en`, ships
        the mod, and the text is unchanged for everyone playing in any
        other language. From here `Book-en` looked like any other table.

        Sayable at all only because the bundled layouts state which tables
        the game ships per language. Worked out FROM the layout rather than
        from the `-xx` suffix, because a table whose name merely ends that
        way would otherwise be described as having six translations it does
        not have.
        """
        from ... import nxd_layouts
        prefix, _, language = (self.table or "").rpartition("-")
        if not prefix or language not in c.NXD_LANGUAGES:
            return ""
        layout = nxd_layouts.layout_for(prefix)
        if layout is None or not layout.localized:
            return ""
        label = c.NXD_LANGUAGE_LABELS.get(language, language)
        return (f" \u00b7 {label} only, one of {len(c.NXD_LANGUAGES)} "
                f"language files for this table")

    def _row_label(self, key, values: dict) -> str:
        """
        A row's name if it has one, its key if it does not.

        Goes through `record_name`, which tries Name then NameSingular and
        so on - so a table whose ja/ko rows put the name somewhere other
        than `Name` still labels correctly, the way the typed tabs do.
        """
        name = nxd_data.record_name(values)
        shown = key if not isinstance(key, tuple) else "/".join(str(k) for k in key)
        return f"{shown} - {name}" if name else f"{shown}"

    def _build_fields(self, columns: list, keys: list,
                      force_text: bool = False) -> None:
        while self.fields_column.count():
            item = self.fields_column.takeAt(0)
            widget = item.widget()
            if widget is not None:
                # `setParent(None)` FIRST, then schedule the delete.
                #
                # `takeAt` removes a widget from the layout but leaves it a
                # visible child of the same parent, and `deleteLater` only
                # queues the destruction - so between the two the widget
                # keeps painting at whatever geometry the layout last gave
                # it. Switching from a table with a `Ticks` column to one
                # without drew "Ticks" on top of the new table's first row.
                #
                # It was there before this was noticed and did not always
                # show: an orphan only paints over something if the new
                # layout happens to put a row underneath it. That makes it
                # exactly the kind of fault a screenshot catches and an
                # assertion does not, so `dev/test_qt_data_browser.py` now
                # asserts no orphans survive a table switch.
                widget.setParent(None)
                widget.deleteLater()
        self.field_rows = {}
        for column in columns:
            if column in keys:
                # The key identifies the row. Editing it would not rename
                # the row, it would write over a different one.
                continue
            kind = "text" if force_text else self._column_kind(column)
            if kind == "number":
                row = NumericFieldRow(column, column, NUMERIC_MIN, NUMERIC_MAX)
            else:
                # Capped THROUGH the row, not by setting `row.value`'s
                # maximum afterwards: the row has to know, or it cannot
                # absorb the space the box then refuses. See the note on
                # `max_value_width`.
                row = TextFieldRow(column, column, max_value_width=620)
            row.edited.connect(self._on_field_edited)
            self.field_rows[column] = row
            self.fields_column.addWidget(row)
        self.fields_column.addStretch(1)
        # `CollapsibleSection` takes its title once at construction and
        # has no setter, so the header button is set directly.
        # Rebuilding the section per table would reset its expanded
        # state every time someone switched tables.
        self.section.header.setText(
            f"Fields \u2014 {self._xml_filename if self._is_xml else self.table}")

    def _column_kind(self, column: str) -> str:
        """
        Text or number, decided from the DATA rather than the column name.

        Every value in the table is sampled, not just the first row: a
        column that is NULL in row 1 and an integer in row 2 is a number,
        and typing a string into it would write the wrong type back.
        """
        for values in self.rows_by_key.values():
            value = values.get(column)
            if value is None:
                continue
            return "number" if isinstance(value, int) else "text"
        return "text"

    # -- editing ---------------------------------------------------------------

    def _registered_target(self):
        """
        `(spec, language)` when this table belongs to a registered spec.

        `UI-en` is not a nameless table any more: since the registry began
        deriving itself from the bundled layouts, `ui` is a registered
        per-language spec and its edits live in the SAME store the curated
        tabs use. This page kept reading `unmodelled_table_edits`, which
        after that change is a store those 47 tables no longer use.

        The result was that a mod editing `ui.en.nxd` - the texture pack
        does - showed the VANILLA text here, on the only page where that
        table can be edited at all, with the row unhighlighted. Worse, a
        person correcting what looked like an unmodded row wrote into the
        unmodelled store while the mod's own edits sat in the registered
        one: two sources of truth for one table, both applied at export.

        Resolved against the registry rather than by splitting the name on
        its last hyphen, because plenty of table names contain one and
        `Novel04-en` must not be read as a language variant of `Novel04`.
        """
        if self._is_xml or not self.table:
            return None
        for spec in nxd_data.ALL_NXD_SPECS.values():
            for lang in c.NXD_LANGUAGES:
                if spec.table(lang) == self.table:
                    return spec, lang
        return None

    def _store_and_key(self):
        """(the right store, the key within it) for whichever kind this is."""
        target = self._registered_target()
        if target is not None:
            spec, lang = target
            store = self.state.nxd_edits_for(spec.key)
            # Written straight back, so the store this returns IS the one
            # the state holds. `nxd_edits_for` ends in `or {}` for a
            # curated spec, so an empty store hands out a FRESH dict and
            # every edit made through it would be dropped on the floor.
            self.state.set_nxd_edits_for(spec.key, store)
            return store, lang
        if self._is_xml:
            store = getattr(self.state, "derived_table_edits", None)
            if store is None:
                store = {}
                self.state.derived_table_edits = store
            return store, self._xml_filename
        store = getattr(self.state, "unmodelled_table_edits", None)
        if store is None:
            store = {}
            self.state.unmodelled_table_edits = store
        return store, self.table

    def _edits_for_table(self) -> dict:
        """
        This table's pending edits, WITHOUT creating an entry for it.

        `setdefault` here was wrong: merely looking at a table left an empty
        dict behind under its name, and an empty dict is still a key in
        `unmodelled_table_edits`. Browsing five tables would have told the
        export it had five tables to write and the Review tab that five
        were touched. Every other page in this tool has the same rule -
        no entry until there is something in it.
        """
        target = self._registered_target()
        if target is not None:
            spec, lang = target
            return self.state.nxd_edits_for(spec.key).get(lang, {})
        if self._is_xml:
            store = getattr(self.state, "derived_table_edits", None) or {}
            return store.get(self._xml_filename, {})
        store = getattr(self.state, "unmodelled_table_edits", None) or {}
        return store.get(self.table, {})

    def _writable_edits_for_table(self) -> dict:
        """The same store, created on purpose, for when an edit is being made."""
        store, key = self._store_and_key()
        return store.setdefault(key, {})

    def _on_selection(self, current, _previous) -> None:
        if current is None:
            return
        self.load_row(current.data(Qt.UserRole))

    def load_row(self, key) -> None:
        values = self.rows_by_key.get(key)
        if values is None:
            return
        self.current_key = key
        self._loading = True
        try:
            self.editing_label.setText(
                f"Editing: {self._row_label(key, values)}")
            already = self._edits_for_table().get(key, {})
            for column, row in self.field_rows.items():
                if column in already:
                    row.load(already[column], True)
                else:
                    value = values.get(column)
                    row.load("" if value is None else value, False)
        finally:
            self._loading = False

    def _on_field_edited(self) -> None:
        if self._loading or self.current_key is None:
            return
        table_edits = self._writable_edits_for_table()
        edits = table_edits.setdefault(self.current_key, {})
        for column, row in self.field_rows.items():
            if row.included:
                edits[column] = row.get_value_str()
            elif column in edits:
                del edits[column]
        if not edits:
            table_edits.pop(self.current_key, None)
        if not table_edits:
            store, key = self._store_and_key()
            store.pop(key, None)
        self._mark_edited()
        self._update_counter()
        self.edits_changed.emit()

    def _mark_edited(self) -> None:
        edited_keys = self._edits_for_table()
        for i in range(self.list.count()):
            item = self.list.item(i)
            mark_edited(item, bool(edited_keys.get(item.data(Qt.UserRole))))

    def _update_counter(self) -> None:
        """
        Counts EVERY store this page can write to, so the total does not
        change meaning depending on which kind of table is selected.

        Three kinds now, not two. Registered per-language tables were added
        when the registry began deriving itself from the layouts, and this
        counted only the other two - so selecting a registered table gave
        "1 row(s) edited in UI-en, -1 in other tables". A negative count is
        the arithmetic saying out loud that the total excluded the thing it
        was subtracting.
        """
        here = sum(1 for fields in self._edits_for_table().values() if fields)
        total = 0
        for store in (getattr(self.state, "unmodelled_table_edits", {}) or {},
                      getattr(self.state, "derived_table_edits", {}) or {}):
            for _name, rows in store.items():
                for fields in rows.values():
                    if fields:
                        total += 1
        for spec in nxd_data.ALL_NXD_SPECS.values():
            for _lang, rows in self.state.nxd_edits_for(spec.key).items():
                for fields in rows.values():
                    if fields:
                        total += 1
        shown = self._xml_filename if self._is_xml else self.table
        text = f"{here} row(s) edited in {shown}"
        if total - here:
            text += f", {total - here} in other tables"
        self.counter.setText(text)

    def _filter_list(self, text: str) -> None:
        needle = (text or "").strip().lower()
        for i in range(self.list.count()):
            item = self.list.item(i)
            item.setHidden(bool(needle) and needle not in item.text().lower())
