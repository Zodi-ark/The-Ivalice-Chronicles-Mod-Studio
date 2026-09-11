"""
Edit Game Data / Jobs.

Master-detail: every job on the left, the selected job's fields on the
right. The second Qt page, and the one that carries the interaction the
whole tool is built on - per-field opt-in.

What it does NOT do is own any rules about what an edit is. Those live on
`WizardState.edits`, keyed `{job_id: {field_name: value}}`, and the rules
are exactly the ones the Tkinter panel established:

- a ticked field is written, an unticked one is removed from the mod
- a job with no ticked fields is dropped from `edits` entirely, so an
  emptied job leaves no trace rather than an empty entry
- loading a record never writes anything

Those are re-implemented against the same state object rather than
reinvented, because two front ends disagreeing about what counts as an edit
would be the worst possible outcome of running both.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QPushButton, QSizePolicy, QVBoxLayout,
    QWidget,
)

from ... import ability_names
from ... import constants as c
from ... import nxd_data
from ... import ui_settings
from ..widgets.actions import (
    COPY_LANGUAGES_LABEL, COPY_LANGUAGES_NOTE, TransientNote,
    copy_edits_to_languages, ensure_language_loaded, language_order,
    page_intro,
    ViewToggles, apply_view_toggles, mark_edited)
from ..widgets.column_form import (
    DEFAULT_MIN_COLUMN_WIDTH, NARROW_MIN_COLUMN_WIDTH, ColumnFormBody,
)
from ..widgets.field_rows import (
    CollapsibleSection, DropdownFieldRow, FlagFieldPanel, NumericFieldRow,
    TextFieldRow,
)
from ..widgets.form_scroll import FormScrollArea
from ..widgets.layout_settle import settle_layout

#: Lines given to a prose box in the single-column Name and Description
#: section. Five because the longest real job description - `Job-de`, 427
#: characters - needs five lines at the 1100px minimum window. The default
#: three fits English (261 characters) and clips German.
PROSE_ROWS = 5


def is_unknown_field(field_name: str, label: str = "") -> bool:
    """
    Whether a field is one nobody has worked out yet.

    Judges the LABEL, not the column name. `Unknown4` holds a confirmed unit
    name and is not unknown; `Unknown8F` genuinely is. Getting this backwards
    would hide a working field and show a useless one, and the rule looks
    enough like a bug that it is worth saying why it is not.
    """
    text = (label or field_name).strip().lower()
    return text.startswith("unknown")


def _groups_for(field_name: str, choices: list) -> dict:
    """
    How a flag field's choices are grouped for display.

    Taken from the engine's own grouping rather than invented here, so a
    change to EQUIP_GROUPS or STATUS_GROUPS shows up in the interface
    instead of the two drifting apart.
    """
    if field_name == "EquippableItems":
        return c.EQUIP_GROUPS
    if field_name in ("InnateStatus", "ImmuneStatus", "StartingStatus"):
        return c.STATUS_GROUPS
    return {"Elements": choices}


class JobsPage(QWidget):
    edits_changed = Signal()
    navigate_requested = Signal(str, object)

    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state
        self.current_job_id = None
        self.rows: dict[str, NumericFieldRow] = {}
        # Kept apart from `self.rows` on purpose. `_on_field_edited` walks
        # `rows` and writes every ticked one into `state.edits`, which is
        # JobData.xml's store; a text row in there would be written into the
        # XML as a field that table does not have.
        self.text_rows: dict[str, TextFieldRow] = {}
        self._hide_notes = False
        self._hide_unknown = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 10, 24, 20)
        outer.setSpacing(10)

        # The language controls, in the same place and shape as Abilities,
        # Items and Poaching have them. Jobs needs them because the page now
        # edits two tables at once: JobData.xml, which is shared across
        # every language, and job.<lang>.nxd, which is not.
        top = QHBoxLayout()
        top.addWidget(QLabel("Language:"))
        self.language_box = QComboBox()
        self.language_box.addItems(language_order(c.NXD_JOB_FILENAMES))
        self.language_box.currentTextChanged.connect(self._on_language)
        self.language_box.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.language_box.setMinimumWidth(72)
        top.addWidget(self.language_box)

        self.copy_button = QPushButton(COPY_LANGUAGES_LABEL)
        self.copy_button.setToolTip(COPY_LANGUAGES_NOTE)
        self.copy_button.clicked.connect(self.copy_current_to_languages)
        self.copy_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        top.addWidget(self.copy_button)

        self.language_controls = QWidget()
        top.setContentsMargins(0, 0, 0, 0)
        self.language_controls.setLayout(top)
        self.language_controls.setSizePolicy(QSizePolicy.Maximum,
                                             QSizePolicy.Preferred)

        # Length is no longer load-bearing - `page_intro` caps the
        # description's height, so a longer sentence clips instead of
        # moving everything below it. It used to matter, and tuning this
        # string to four window widths is what proved the cap was the real
        # fix rather than shorter copy.
        outer.addLayout(page_intro(
            "Pick a job on the left, then edit it on the right. Only the "
            "fields you tick are written into your mod. The job's name and "
            "description are per-language - pick the language first.",
            self.language_controls))

        self.action_note = TransientNote()
        outer.addWidget(self.action_note)

        # Restored from the same store the Tkinter interface writes, so a
        # choice made in one is honoured by the other. A view preference
        # that resets every launch is not a preference, it is a chore.
        saved = ui_settings.load()

        toggles = QHBoxLayout()
        self.counter = QLabel("")
        self.counter.setProperty("role", "ok")
        toggles.addWidget(self.counter)
        outer.addLayout(toggles)

        # The shared widget, in the same place as every other tab. Jobs grew
        # these first and every later tab was built from the page rather
        # than from the interface, so they ended up in three different
        # positions across the ten.
        self.view_toggles = ViewToggles()
        self.view_toggles.changed.connect(self._on_view_changed)
        # Hidden: the shell draws the one visible pair, above the tabs,
        # so it is in the same place on all ten. This instance still
        # receives the preference and still answers `state()`.
        self.view_toggles.follow_only()
        # The individual boxes, named for the callers that reach for them.
        self.notes_toggle = self.view_toggles.notes
        self.unknown_toggle = self.view_toggles.unknown

        split = QHBoxLayout()
        split.setSpacing(14)

        # -- the record list ------------------------------------------------
        left = QVBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search by name or ID")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter_list)
        left.addWidget(self.search)
        self.list = QListWidget()
        self.list.setFixedWidth(260)
        self.list.currentItemChanged.connect(self._on_selection)
        left.addWidget(self.list, 1)
        split.addLayout(left)

        # -- the editor -----------------------------------------------------
        right = QVBoxLayout()
        self.editing_label = QLabel("Select a job")
        self.editing_label.setStyleSheet("font-weight: 600; font-size: 12pt;")
        right.addWidget(self.editing_label)

        # A job's skillset: the single most consequential field on the page,
        # and the Qt rewrite shipped without it.
        #
        # There was a jump button here - "Edit this job's command ->" - and
        # no way to CHANGE which command a job has. `JobCommandId` is in
        # neither NUMERIC_FIELDS nor FLAG_FIELDS, so the generic row builder
        # below never produced a control for it, and the jump was the only
        # trace of the field on the whole page. You could go and look at a
        # job's skillset; you could not give it a different one. The Tkinter
        # interface has had both since the beginning
        # (`JobCommandDropdownRow` in gui/step_editor.py).
        #
        # Above Basic Stats rather than inside it because it is not a stat,
        # and because burying the field that decides what a job can DO
        # underneath its HP growth gets the emphasis backwards.
        self.command_row = DropdownFieldRow(
            "JobCommandId", "Job Command (skillset)",
            # "Edit ->", not "Edit this Job Command ->".
            #
            # HANDOFF records the long label being clipped to "Edit this Job
            # C" on the Tkinter Jobs tab at 1280x720 - allocated 107px,
            # requires 190px - and puts fixing it on this tab's acceptance
            # list. Rebuilding the page in Qt and using the same string
            # reproduced it exactly: a screenshot at the 1100 minimum showed
            # ":dit this Job Command -".
            #
            # The row already says "Job Command (skillset)" immediately to
            # the left, so the long label was spending 120px restating its
            # own row. The tooltip carries the full sentence.
            jump_label="Edit \u2192",
            jump_tooltip="Open this skillset on the Job Commands tab")
        self.command_row.edited.connect(self._on_field_edited)
        self.command_row.edited.connect(self._update_command_preview)
        self.command_row.jump_requested.connect(self._jump_to_command)
        self.rows["JobCommandId"] = self.command_row
        right.addWidget(self.command_row)

        # What that skillset actually grants, so choosing one is not a
        # guess at what a number means.
        self.command_preview = QLabel("")
        self.command_preview.setProperty("role", "muted")
        self.command_preview.setWordWrap(True)
        right.addWidget(self.command_preview)

        self.no_reference = QLabel(
            "This job has no reference data, so edits here add new values "
            "rather than overriding known ones.")
        self.no_reference.setProperty("role", "attention")
        self.no_reference.setWordWrap(True)
        self.no_reference.setVisible(False)
        right.addWidget(self.no_reference)

        scroll = FormScrollArea()
        holder = QWidget()
        self.form = QVBoxLayout(holder)
        self.form.setContentsMargins(4, 4, 4, 4)
        self.form.setSpacing(2)

        # -- Name and Description (job.<lang>.nxd) -------------------------
        # First, and open on arrival, because it is the half a person can
        # read. A job's stats are meaningless until you know which job you
        # are looking at, and this is the only place the game's own name for
        # it can be changed.
        #
        # These rows write to `state.job_text_edits`, NOT `state.edits` -
        # a different table, a different file, and per-language where the
        # stats are not. `_on_field_edited` keeps the two apart.
        # `ColumnFormBody`, not a `QVBoxLayout`, for the reason measured in
        # `dev/audit_form_density.py`: a single column showed the same 75 of
        # 106 fields at 2560px as at 1100px and turned the other 1479px into
        # empty space. `column_form.py` carries the full argument, including
        # why `flow_layout.py` is the wrong shape for a form.
        #
        # The three bodies on this page are separate forms so that each
        # section balances its own columns. One form spanning all three
        # would let a stat from Basic Stats land level with a description,
        # and the section headings would stop meaning anything.
        # ONE COLUMN, unlike the two numeric sections below.
        #
        # These four fields are prose - Name, Name (feminine), Description,
        # Description (feminine) - and prose is the case the reflow is wrong
        # for. A spin box does not read better for being 800px wide, so
        # packing stats into columns is free; a description's readable
        # length IS its width. In three columns the Description box was
        # about 190px and showed roughly 75 characters of a 261-character
        # job description, with the rest behind a scrollbar. Reported from a
        # screenshot, and the two boxes also landed in different columns
        # from the names they belong to, so the pairing was invisible.
        #
        # Stacked, they run the width of the page and read in the order
        # someone fills them in: name, then its feminine form, then the
        # description, then its feminine form.
        text_body = ColumnFormBody(min_column_width=DEFAULT_MIN_COLUMN_WIDTH,
                                   max_columns=1)
        self.column_bodies = [text_body]
        for field_name in c.JOB_NXD_TEXT_FIELDS:
            label = c.JOB_NXD_FIELD_LABELS.get(field_name, field_name)
            row = TextFieldRow(
                field_name, label,
                note=c.JOB_NXD_FIELD_NOTES.get(field_name, ""),
                unknown=is_unknown_field(field_name, label),
                # This page has the columns to afford it - see the gate's
                # comment on `TextFieldRow`. A job description runs to 261
                # characters and had one line to show them in.
                multiline=True,
                # Five, not the default three. Measured against the real
                # table rather than the English the developer reads: the
                # longest `Job-en` description is 261 characters and needs
                # three lines at the 1100px minimum, but the same job in
                # `Job-de` is 427 characters and needs five. Three would
                # have looked correct in English and clipped for a German
                # modder on a small window.
                #
                # Costs nothing at the wide end - a text box with room to
                # type in is not wasted space - and only two of these four
                # rows are prose boxes at all; the two names are single-line
                # fields.
                rows=PROSE_ROWS,
                # Stacked rows: hold the note column on rows without notes, and
                # let a note that does not fit wrap rather than elide.
                stacked=True)
            row.edited.connect(self._on_text_field_edited)
            self.text_rows[field_name] = row
            text_body.add_row(row)
        self.text_section = CollapsibleSection(
            "Name and Description", text_body,
            expanded=True)
        self.sections = [self.text_section]
        self.form.addWidget(self.text_section)

        # -- every remaining column of Job-<lang> ---------------------------
        # Collapsed, and last, because most modders will never need it - but
        # PRESENT, because the game data has these columns and a tool that
        # models a table and drops eleven of its sixteen columns is a tool
        # for the five somebody got round to.
        #
        # `dev/audit_field_coverage.py` fails when a column exists in the
        # data and is reachable nowhere, so this staying complete is checked
        # rather than remembered.
        numeric_body = ColumnFormBody(min_column_width=DEFAULT_MIN_COLUMN_WIDTH)
        self.column_bodies.append(numeric_body)
        for field_name, (low, high) in c.JOB_NXD_NUMERIC_FIELDS.items():
            label = c.JOB_NXD_NUMERIC_LABELS.get(field_name, field_name)
            row = NumericFieldRow(
                field_name, label, low, high,
                note=c.JOB_NXD_NUMERIC_NOTES.get(field_name, ""),
                unknown=is_unknown_field(field_name, label))
            row.edited.connect(self._on_text_field_edited)
            self.text_rows[field_name] = row
            numeric_body.add_row(row)
        self.numeric_section = CollapsibleSection(
            "Other fields", numeric_body, expanded=False)
        self.sections.append(self.numeric_section)
        self.form.addWidget(self.numeric_section)

        # Basic Stats is open on arrival - it is what most edits touch, and
        # a page that opens with everything collapsed makes you click before
        # you can do anything.
        stats = ColumnFormBody(min_column_width=DEFAULT_MIN_COLUMN_WIDTH)
        self.column_bodies.append(stats)
        for field_name, spec in c.NUMERIC_FIELDS.items():
            minimum, maximum, label = spec[0], spec[1], spec[2]
            note = spec[3] if len(spec) > 3 else ""
            row = NumericFieldRow(field_name, label, minimum, maximum, note,
                                  unknown=is_unknown_field(field_name, label))
            row.edited.connect(self._on_field_edited)
            self.rows[field_name] = row
            stats.add_row(row)
        self.sections.append(
            CollapsibleSection("Basic Stats", stats,
                               expanded=True))
        self.form.addWidget(self.sections[-1])

        # The flag fields, grouped the way the engine groups them.
        for field_name, (choices, label) in c.FLAG_FIELDS.items():
            groups = _groups_for(field_name, choices)
            # Three columns, not four. At the 1100 minimum the editor pane
            # is about 540px wide, and four columns gives each group ~135px
            # while "Weapons - Blunt/Heavy" needs around 150 - so the grid
            # overflowed and put a horizontal scroll bar under the form.
            # Sideways scrolling to read a checkbox label is the kind of
            # friction nobody reports and everybody feels.
            panel = FlagFieldPanel(field_name, label, groups, columns=3)
            panel.edited.connect(self._on_field_edited)
            self.rows[field_name] = panel
            section = CollapsibleSection(label, panel, expanded=False)
            self.sections.append(section)
            self.form.addWidget(section)

        self.form.addStretch(1)
        scroll.setWidget(holder)
        self.scroll = scroll
        right.addWidget(scroll, 1)
        split.addLayout(right, 1)

        outer.addLayout(split, 1)
        self._apply_display()
        self.refresh_records()

    # -- records -------------------------------------------------------------

    def _job_label(self, job_id: int, xml_name: str = "") -> str:
        """
        What this job is CALLED right now, in the selected language.

        Prefers the `job.<lang>.nxd` name - including one typed and not yet
        exported - because that is the name the player sees. Falls back to
        `JobData.xml`'s own `name`, which is what the list used to show
        unconditionally: renaming a job left the list showing the old name
        until the tab was rebuilt, while Abilities and Items both relabel
        as you type.
        """
        live = nxd_data.effective_name(self.state, "job", job_id, self.language)
        if not live and not xml_name:
            for record in (getattr(self.state, "job_records", []) or []):
                if record.job_id == job_id:
                    xml_name = record.name or ""
                    break
        return f"{job_id:03d} - {live or xml_name or '(unnamed)'}"

    def _relabel_list(self) -> None:
        """Re-read every row's name in place, without rebuilding the list."""
        for i in range(self.list.count()):
            item = self.list.item(i)
            item.setText(self._job_label(item.data(Qt.UserRole)))
        if self.current_job_id is not None:
            self.editing_label.setText(
                f"Editing: {self._job_label(self.current_job_id)}")

    def refresh_records(self) -> None:
        # The nxd half is read lazily, one language at a time, the same way
        # every other per-language page does it. Setup only fetches English.
        ensure_language_loaded(
            self.state, nxd_data.spec_for("job").records_attr, self.language)
        self.list.clear()
        for record in getattr(self.state, "job_records", []) or []:
            item = QListWidgetItem(self._job_label(record.job_id, record.name))
            item.setData(Qt.UserRole, record.job_id)
            self.list.addItem(item)
        self._mark_edited()
        self._update_counter()
        if self.list.count():
            self.list.setCurrentRow(0)

    def _filter_list(self, text: str) -> None:
        needle = text.strip().lower()
        for i in range(self.list.count()):
            item = self.list.item(i)
            item.setHidden(bool(needle) and needle not in item.text().lower())

    def _on_selection(self, current, _previous) -> None:
        if current is None:
            return
        self.load_job(current.data(Qt.UserRole))

    def load_job(self, job_id: int) -> None:
        records = {r.job_id: r for r in (getattr(self.state, "job_records", []) or [])}
        record = records.get(job_id)
        if record is None:
            return
        self.current_job_id = job_id
        self.editing_label.setText(
            f"Editing: {self._job_label(job_id, record.name)}")
        self.no_reference.setVisible(not record.has_reference_data)

        already = self.state.edits.get(job_id, {})
        for field_name, row in self.rows.items():
            if field_name in already:
                row.load(already[field_name], True)
            else:
                row.load(record.values.get(field_name, ""), False)
        self._load_text_rows(job_id)
        self._update_command_preview()

    def _text_record_for(self, job_id: int):
        """This job's row in the currently selected language, if it is loaded."""
        records = self.state.nxd_records_for("job").get(self.language) or []
        for candidate in records:
            if candidate.key == job_id:
                return candidate
        return None

    def _load_text_rows(self, job_id: int) -> None:
        """
        Fills the Name/Description rows from the nxd table.

        Loading never ticks anything: an untouched field shows the game's
        own value with its box clear, exactly as the numeric rows do. The
        value shown is the game's; the tick is what puts it in the mod.
        """
        record = self._text_record_for(job_id)
        already = self.state.nxd_edits_for("job").get(self.language, {}).get(job_id, {})
        for field_name, row in self.text_rows.items():
            if field_name in already:
                row.load(already[field_name], True)
            else:
                value = record.values.get(field_name) if record else ""
                row.load("" if value is None else value, False)

    def set_command_choices(self, id_to_name: dict) -> None:
        """
        Fills the skillset dropdown once the job command table is known.

        Same reason as the ability dropdowns: this table is read during
        setup and does not exist when the page is built.
        """
        self.command_row.set_choices(id_to_name)
        self._update_command_preview()

    def _update_command_preview(self) -> None:
        """
        Lists what the selected skillset grants.

        Reads the command's own record rather than re-deriving anything, and
        says so plainly when the table has not been loaded - an empty line
        would read as "this skillset grants nothing", which is a different
        and wrong claim.
        """
        command_id = self.command_row.current_id()
        records = {r.command_id: r for r
                   in (getattr(self.state, "job_command_records", []) or [])}
        record = records.get(command_id)
        if not command_id:
            self.command_preview.setText("No skillset - this job has no action menu.")
            return
        if record is None:
            self.command_preview.setText("")
            return
        names = getattr(self.state, "ability_names", None) or {}
        granted = [ability_names.resolve_ability_name(i, names)
                   for i in (record.ability_ids or []) if i]
        self.command_preview.setText(
            "Grants: " + ", ".join(granted) if granted
            else "That skillset has no abilities in it.")

    def _jump_to_command(self, command_id: int) -> None:
        """
        Opens Job Commands at the skillset currently selected.

        The id comes from the row, not from the record. Those differ the
        moment somebody picks a different skillset and has not exported
        yet, and jumping to the value they just replaced would be actively
        confusing.
        """
        self.navigate_requested.emit("Job Commands", int(command_id))

    # -- editing -------------------------------------------------------------

    def _on_field_edited(self) -> None:
        if self.current_job_id is None:
            return
        job_id = self.current_job_id
        edits = self.state.edits.setdefault(job_id, {})
        for field_name, row in self.rows.items():
            if row.included:
                edits[field_name] = row.get_value_str()
            elif field_name in edits:
                del edits[field_name]
        # A job with nothing ticked leaves no entry behind. An empty dict
        # would still count as a job in every "how many have you edited"
        # sum, so unticking your last field would leave the tool insisting
        # you had edited something.
        if not edits:
            self.state.edits.pop(job_id, None)

        self._mirror_linked_fields(job_id, edits)
        self._mark_edited()
        self._update_counter()
        self.edits_changed.emit()

    def _mirror_linked_fields(self, job_id: int, xml_edits: dict) -> None:
        """
        Writes the .nxd's copy of any field that exists in both files.

        `JobData.xml`'s own header, shipped by the mod loader, says the nex
        table can override it:

            "This table links to nex table 'Job'. Some properties edited
             here may be overriden by the nex table."

        So setting `JobCommandId` in the XML and leaving `jobcommand+Id`
        alone can silently do nothing - the XML is written correctly and the
        game ignores it. That is the worst kind of failure to debug, because
        every artefact looks right.

        The alternative was two controls on one page for one value, which
        lets a mod disagree with itself and shows the modder nothing. One
        control writes both, and the .nxd row stays in step so a person
        opening that section sees the value they set.

        Written into EVERY language the job already has text edits in, plus
        the one on screen - the .nxd is per-language but this value is not,
        so leaving the others behind would make the game's behaviour depend
        on which language a player runs.
        """
        store = self.state.nxd_edits_for("job")
        for xml_field, key, nxd_field in c.LINKED_FIELDS:
            if key != "job":
                continue
            languages = set(store) | {self.language}
            for language in languages:
                per_language = store.setdefault(language, {})
                row_edits = per_language.setdefault(job_id, {})
                if xml_field in xml_edits:
                    row_edits[nxd_field] = xml_edits[xml_field]
                else:
                    row_edits.pop(nxd_field, None)
                if not row_edits:
                    per_language.pop(job_id, None)
            for language in list(store):
                if not store[language]:
                    store.pop(language)
        self.state.set_nxd_edits_for("job", store)
        # The row on screen has to follow, or the section shows the old
        # value until the job is reselected.
        if self.current_job_id == job_id:
            self._load_text_rows(job_id)

    def _on_text_field_edited(self) -> None:
        """
        The Name/Description half. Writes `state.job_text_edits`, per
        language, and never touches `state.edits`.

        Clearing a box is an edit, not an absence - blanking a job's name is
        a legitimate thing for a mod to do, and the engine writes an empty
        string as a deliberate value.
        """
        if self.current_job_id is None:
            return
        job_id = self.current_job_id
        store = self.state.nxd_edits_for("job")
        per_language = store.setdefault(self.language, {})
        edits = per_language.setdefault(job_id, {})
        for field_name, row in self.text_rows.items():
            if row.included:
                edits[field_name] = row.get_value_str()
            elif field_name in edits:
                del edits[field_name]
        # Same rule as the XML half: a row with nothing ticked leaves no
        # entry, so unticking your last field does not leave the tool
        # insisting you have edits.
        if not edits:
            per_language.pop(job_id, None)
        if not per_language:
            store.pop(self.language, None)
        self.state.set_nxd_edits_for("job", store)

        self._relabel_list()
        self._mark_edited()
        self._update_counter()
        self.edits_changed.emit()

    def copy_current_to_languages(self) -> None:
        """
        Copies this job's ticked NON-TEXT fields into the other languages.

        Which, for this table, is nothing - every column it exposes is a
        translation. The button is here because every other per-language
        page has it in this position and a missing one reads as a page that
        forgot, but it says plainly why it did nothing rather than flashing
        a success message over an empty action.
        """
        if self.current_job_id is None:
            return
        spec = nxd_data.spec_for("job")
        changed = copy_edits_to_languages(
            self.state.nxd_edits_for("job"), self.language,
            self.current_job_id,
            [lang for lang in c.NXD_LANGUAGES if lang != self.language],
            skip_fields=set(spec.text_fields))
        if changed:
            self.action_note.setText(
                f"Copied to {len(changed)} other language(s).")
        else:
            self.action_note.setText(
                "Nothing to copy - every field on this page is text, and "
                "text is never copied between languages.")
        self._mark_edited()
        self._update_counter()
        self.edits_changed.emit()

    @property
    def language(self) -> str:
        return self.language_box.currentText() or "en"

    def _on_language(self, _text: str) -> None:
        """
        Switches language without disturbing the selection.

        Only the TEXT differs between languages, so the job you were looking
        at is still the job you want. Rebuilding the list would reset it to
        row 0 and throw the selection away.
        """
        ensure_language_loaded(
            self.state, nxd_data.spec_for("job").records_attr, self.language)
        if self.current_job_id is not None:
            self._load_text_rows(self.current_job_id)
        # The list shows the name in the SELECTED language, so switching
        # language has to relabel it - otherwise German names sit under
        # English rows.
        self._relabel_list()
        self._mark_edited()
        self._update_counter()

    def _has_text_edits(self, job_id: int) -> bool:
        """Whether this job has a text edit in ANY language, not just this one."""
        for per_language in self.state.nxd_edits_for("job").values():
            if per_language.get(job_id):
                return True
        return False

    def _mark_edited(self) -> None:
        for i in range(self.list.count()):
            item = self.list.item(i)
            job_id = item.data(Qt.UserRole)
            # Marked for either half. A job whose German name was changed
            # and whose stats were not is still an edited job, and a green
            # row that disappears when you switch language would read as
            # the edit having been lost.
            edited = bool(self.state.edits.get(job_id)) or self._has_text_edits(job_id)
            mark_edited(item, edited)

    def _update_counter(self) -> None:
        total = self.list.count()
        edited = len({
            *(job_id for job_id, fields in self.state.edits.items() if fields),
            *(job_id
              for per_language in self.state.nxd_edits_for("job").values()
              for job_id, fields in per_language.items() if fields),
        })
        self.counter.setText(f"{edited} of {total} jobs have pending edits")

    # -- view toggles ---------------------------------------------------------

    def _on_view_changed(self, hide_notes: bool, hide_unknown: bool,
                         hide_comments: bool) -> None:
        # BOTH row dictionaries. Passing only `self.rows` would leave the
        # text rows showing their notes with notes turned off, and "Unknown
        # 2" visible with unknown fields hidden - the identical-container-
        # next-door fault, on the page that just grew the second container.
        apply_view_toggles(
            list(self.rows.values()) + list(self.text_rows.values()),
            hide_notes, hide_unknown, hide_comments)
        # Hiding the notes makes every row narrower, so more columns fit.
        # The layout is told the new minimum rather than being taught about
        # notes: a row's width requirement is the only thing it needs to
        # know, and a second opinion about notes living inside the layout
        # is a thing that can disagree with this one later.
        width = NARROW_MIN_COLUMN_WIDTH if hide_notes else DEFAULT_MIN_COLUMN_WIDTH
        for body in self.column_bodies:
            body.set_min_column_width(width)
        # This page keeps changing the layout AFTER `apply_view_toggles` has
        # settled it, so it has to settle again itself. Without this, 82
        # widgets were still moving once the click returned - the toggles
        # were settled and then the column width changed under them.
        #
        # From the BODIES, not from the page. Walking up from the page never
        # re-lays the bodies, which are below it and are the things that just
        # changed; settling the page alone left all 82 still moving.
        for body in self.column_bodies:
            settle_layout(body)

    def _apply_display(self) -> None:
        """Applies whatever the toggles currently say. Saving is the bar's job."""
        self._on_view_changed(*self.view_toggles.state())
