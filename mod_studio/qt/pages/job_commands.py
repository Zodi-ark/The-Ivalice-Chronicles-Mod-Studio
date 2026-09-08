"""
Edit Game Data / Job Commands.

A job command is a skillset - the list of abilities a job gets. Sixteen
ability slots and six reaction/support/movement slots, each an ID pointing
at an ability.

Third Qt page, and the one that proves the dropdown primitive. Its rules are
the same as Jobs' and are deliberately the same code shape, because the
thing that would hurt most is the ten tabs each growing their own slightly
different idea of what an edit is.

Edits land on `WizardState.job_command_edits`, keyed
`{command_id: {field_name: value}}`.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from ... import constants as c
from ... import nxd_data
from ... import xml_io
from ..widgets.actions import (
    COPY_LANGUAGES_LABEL, COPY_LANGUAGES_NOTE, TransientNote,
    copy_edits_to_languages, ensure_language_loaded, language_order,
    mark_edited, select_list_row, page_intro)
from ..widgets.field_rows import (
    CollapsibleSection, DropdownFieldRow, NumericFieldRow, TextFieldRow)

ABILITY_SLOTS = 16
RSM_SLOTS = 6


class JobCommandsPage(QWidget):
    edits_changed = Signal()
    navigate_requested = Signal(str, object)

    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state
        self.current_command_id = None
        self.rows: dict[str, DropdownFieldRow] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 10, 24, 20)
        outer.setSpacing(10)

        # Language controls, same position and shape as every other
        # per-language page. This tab now edits two files: the .xml's
        # ability slots, shared across languages, and the .nxd's name and
        # description, which are not.
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.addWidget(QLabel("Language:"))
        self.language_box = QComboBox()
        self.language_box.addItems(language_order(c.NXD_JOBCOMMAND_FILENAMES))
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
        self.language_controls.setLayout(top)
        self.language_controls.setSizePolicy(QSizePolicy.Maximum,
                                             QSizePolicy.Preferred)

        outer.addLayout(page_intro(
            "A job command is a skillset - the abilities a job can use. Pick "
            "one on the left, then set its slots. Only the slots you tick are "
            "written into your mod. Names and descriptions are per-language.",
            self.language_controls))

        self.action_note = TransientNote()
        outer.addWidget(self.action_note)

        self.counter = QLabel("")
        self.counter.setProperty("role", "ok")
        outer.addWidget(self.counter)

        split = QHBoxLayout()
        split.setSpacing(14)

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

        right = QVBoxLayout()
        self.editing_label = QLabel("Select a job command")
        self.editing_label.setStyleSheet("font-weight: 600; font-size: 12pt;")
        right.addWidget(self.editing_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        holder = QWidget()
        form = QVBoxLayout(holder)
        form.setContentsMargins(4, 4, 4, 4)
        form.setSpacing(2)

        abilities = QWidget()
        abilities_column = QVBoxLayout(abilities)
        abilities_column.setContentsMargins(0, 0, 0, 0)
        abilities_column.setSpacing(2)
        for i in range(1, ABILITY_SLOTS + 1):
            row = DropdownFieldRow(
                f"AbilityId{i}", f"Ability slot {i}",
                jump_label="Edit \u2192",
                jump_tooltip="Open this ability on the Abilities tab")
            row.edited.connect(self._on_field_edited)
            row.jump_requested.connect(self._jump_to_ability)
            self.rows[row.field_name] = row
            abilities_column.addWidget(row)

        rsm = QWidget()
        rsm_column = QVBoxLayout(rsm)
        rsm_column.setContentsMargins(0, 0, 0, 0)
        rsm_column.setSpacing(2)
        for i in range(1, RSM_SLOTS + 1):
            row = DropdownFieldRow(
                f"ReactionSupportMovementId{i}", f"R/S/M slot {i}",
                jump_label="Edit \u2192",
                jump_tooltip="Open this ability on the Abilities tab")
            row.edited.connect(self._on_field_edited)
            row.jump_requested.connect(self._jump_to_ability)
            self.rows[row.field_name] = row
            rsm_column.addWidget(row)

        # -- jobcommand.<lang>.nxd -----------------------------------------
        # 227 rows of names and descriptions that had NO editor anywhere.
        # The Dragoon Meliadoul mod already changes one of them (row 67,
        # "Unyielding Blade" -> "Templar Arts"), so opening that mod used to
        # recover every other change it makes and silently drop this one.
        self.text_rows = {}
        text_body = QWidget()
        text_column = QVBoxLayout(text_body)
        text_column.setContentsMargins(0, 0, 0, 0)
        text_column.setSpacing(2)
        for field_name in c.JOBCOMMAND_NXD_TEXT_FIELDS:
            label = c.JOBCOMMAND_NXD_FIELD_LABELS.get(field_name, field_name)
            row = TextFieldRow(field_name, label,
                               note=c.JOBCOMMAND_NXD_FIELD_NOTES.get(field_name, ""))
            row.edited.connect(self._on_text_edited)
            self.text_rows[field_name] = row
            text_column.addWidget(row)

        raw_body = QWidget()
        raw_column = QVBoxLayout(raw_body)
        raw_column.setContentsMargins(0, 0, 0, 0)
        raw_column.setSpacing(2)
        for field_name, (low, high) in c.JOBCOMMAND_NXD_NUMERIC_FIELDS.items():
            label = c.JOBCOMMAND_NXD_FIELD_LABELS.get(field_name, field_name)
            row = NumericFieldRow(
                field_name, label, low, high,
                c.JOBCOMMAND_NXD_FIELD_NOTES.get(field_name, ""),
                unknown=field_name.startswith("Unknown"))
            row.edited.connect(self._on_text_edited)
            self.text_rows[field_name] = row
            raw_column.addWidget(row)
        raw_column.addStretch(1)

        self.sections = [
            CollapsibleSection(
                "Name and Description \u2014 jobcommand.<lang>.nxd",
                text_body, expanded=True),
            CollapsibleSection("Abilities \u2014 JobCommandData.xml",
                               abilities, expanded=True),
            CollapsibleSection("Reaction / Support / Movement \u2014 JobCommandData.xml",
                               rsm, expanded=False),
            CollapsibleSection("Other jobcommand.<lang>.nxd fields",
                               raw_body, expanded=False),
        ]
        for section in self.sections:
            form.addWidget(section)
        form.addStretch(1)
        scroll.setWidget(holder)
        self.scroll = scroll
        right.addWidget(scroll, 1)
        split.addLayout(right, 1)

        outer.addLayout(split, 1)
        self.refresh_records()

    # -- records -------------------------------------------------------------

    def refresh_records(self) -> None:
        ensure_language_loaded(
            self.state, nxd_data.spec_for("job_command").records_attr,
            self.language)
        self.list.clear()
        for record in getattr(self.state, "job_command_records", []) or []:
            item = QListWidgetItem(
                self._command_label(record.command_id, record.name))
            item.setData(Qt.UserRole, record.command_id)
            self.list.addItem(item)
        self._mark_edited()
        self._update_counter()
        if self.list.count():
            self.list.setCurrentRow(0)

    def set_ability_choices(self, id_to_name: dict,
                            ability_types: dict | None = None) -> None:
        """
        Fills the ability dropdowns once the ability table is known.

        Separate from construction because that table is fetched during
        setup, so it does not exist when this page is built.

        **The two slot groups get different lists.** The 16 menu slots take
        action-type abilities; the 6 R/S/M slots take Reaction, Support and
        Movement ones. `constants.ACTION_ABILITY_TYPES` and
        `RSM_ABILITY_TYPES` define the split and `xml_io.load_ability_types`
        reads it out of AbilityData.xml's own AbilityType field - not from
        an id range, because the boundaries are not clean.

        Getting this wrong in either direction is a real bug rather than an
        untidiness: one list for both would offer Fire as a Reaction
        ability, and the Qt page's original behaviour - filling only the
        rows whose field name starts with "AbilityId" - left all six R/S/M
        slots stuck on "(None / Unset)" with no way to set them at all.

        With no types available every row gets the full list. That is worse
        than the split and better than six dead dropdowns, and it is what
        happens before AbilityData.xml has been read.
        """
        types = ability_types or getattr(self.state, "ability_types", None) or {}
        if types:
            action = {i: n for i, n in id_to_name.items()
                      if i == 0 or types.get(i) in c.ACTION_ABILITY_TYPES}
            rsm = {i: n for i, n in id_to_name.items()
                   if i == 0 or types.get(i) in c.RSM_ABILITY_TYPES}
        else:
            action = rsm = id_to_name

        for field_name, row in self.rows.items():
            row.set_choices(action if field_name.startswith("AbilityId") else rsm)

    def _filter_list(self, text: str) -> None:
        needle = text.strip().lower()
        for i in range(self.list.count()):
            item = self.list.item(i)
            item.setHidden(bool(needle) and needle not in item.text().lower())

    def _on_selection(self, current, _previous) -> None:
        if current is not None:
            self.load_command(current.data(Qt.UserRole))

    def load_command(self, command_id: int) -> None:
        records = {r.command_id: r for r
                   in (getattr(self.state, "job_command_records", []) or [])}
        record = records.get(command_id)
        if record is None:
            return
        self.current_command_id = command_id
        self.editing_label.setText(
            f"Editing: {self._command_label(command_id, record.name)}")
        self._load_text_rows(command_id)

        already = self.state.job_command_edits.get(command_id, {})
        for i in range(1, ABILITY_SLOTS + 1):
            field_name = f"AbilityId{i}"
            row = self.rows[field_name]
            if field_name in already:
                row.load(already[field_name], True)
            else:
                row.load(str(record.ability_ids[i - 1]), False)
        for i in range(1, RSM_SLOTS + 1):
            field_name = f"ReactionSupportMovementId{i}"
            row = self.rows[field_name]
            if field_name in already:
                row.load(already[field_name], True)
            else:
                row.load(str(record.rsm_ids[i - 1]), False)

    def _jump_to_ability(self, ability_id: int) -> None:
        """
        Opens Abilities at the slot whose button was pressed.

        The id arrives from the row rather than being read back out of a
        remembered "current slot": there are 22 of these and no notion of
        which one is active, so anything the page had to remember would be
        a second source of truth for something the row already knows.
        """
        if ability_id:
            self.navigate_requested.emit("Abilities", int(ability_id))

    def select_record(self, command_id) -> None:
        """
        Used by a jump from another tab - Jobs' skillset Edit button.

        Through the list, so the row moves and scrolls with the editor. See
        `AbilitiesPage.select_record`; this had the same gap.
        """
        if not select_list_row(self.list, int(command_id),
                               getattr(self, "search", None)):
            self.load_command(int(command_id))

    # -- editing -------------------------------------------------------------

    def _on_field_edited(self) -> None:
        if self.current_command_id is None:
            return
        command_id = self.current_command_id
        edits = self.state.job_command_edits.setdefault(command_id, {})
        for field_name, row in self.rows.items():
            if row.included:
                edits[field_name] = row.get_value_str()
            elif field_name in edits:
                del edits[field_name]
        if not edits:
            self.state.job_command_edits.pop(command_id, None)

        self._mark_edited()
        self._update_counter()
        self.edits_changed.emit()

    @property
    def language(self) -> str:
        return self.language_box.currentText() or "en"

    def _command_label(self, command_id: int, xml_name: str = "") -> str:
        """The name as it stands now, in the selected language."""
        live = nxd_data.effective_name(
            self.state, "job_command", command_id, self.language)
        if not live and not xml_name:
            for record in (getattr(self.state, "job_command_records", []) or []):
                if record.command_id == command_id:
                    xml_name = record.name or ""
                    break
        return f"{command_id:03d} - {live or xml_name or '(unnamed)'}"

    def _relabel_list(self) -> None:
        for i in range(self.list.count()):
            item = self.list.item(i)
            item.setText(self._command_label(item.data(Qt.UserRole)))
        if self.current_command_id is not None:
            self.editing_label.setText(
                f"Editing: {self._command_label(self.current_command_id)}")

    def _on_language(self, _text: str) -> None:
        ensure_language_loaded(
            self.state, nxd_data.spec_for("job_command").records_attr,
            self.language)
        if self.current_command_id is not None:
            self._load_text_rows(self.current_command_id)
        self._relabel_list()
        self._mark_edited()
        self._update_counter()

    def _text_record_for(self, command_id: int):
        for record in (self.state.nxd_records_for("job_command")
                       .get(self.language) or []):
            if record.key == command_id:
                return record
        return None

    def _load_text_rows(self, command_id: int) -> None:
        record = self._text_record_for(command_id)
        already = (self.state.nxd_edits_for("job_command")
                   .get(self.language, {}).get(command_id, {}))
        for field_name, row in self.text_rows.items():
            if field_name in already:
                row.load(already[field_name], True)
            else:
                value = record.values.get(field_name) if record else ""
                row.load("" if value is None else value, False)

    def _on_text_edited(self) -> None:
        """Writes `job_command_text_edits`, per language. Never `job_command_edits`."""
        if self.current_command_id is None:
            return
        command_id = self.current_command_id
        store = self.state.nxd_edits_for("job_command")
        per_language = store.setdefault(self.language, {})
        edits = per_language.setdefault(command_id, {})
        for field_name, row in self.text_rows.items():
            if row.included:
                edits[field_name] = row.get_value_str()
            elif field_name in edits:
                del edits[field_name]
        if not edits:
            per_language.pop(command_id, None)
        if not per_language:
            store.pop(self.language, None)
        self.state.set_nxd_edits_for("job_command", store)
        self._relabel_list()
        self._mark_edited()
        self._update_counter()
        self.edits_changed.emit()

    def copy_current_to_languages(self) -> None:
        """Copies the ticked NON-text fields - the icon and the numbers."""
        if self.current_command_id is None:
            self.action_note.setText("Pick a job command first.")
            return
        spec = nxd_data.spec_for("job_command")
        changed = copy_edits_to_languages(
            self.state.nxd_edits_for("job_command"), self.language,
            self.current_command_id,
            [lang for lang in c.NXD_LANGUAGES if lang != self.language],
            skip_fields=set(spec.text_fields))
        self.action_note.setText(
            f"Copied to {len(changed)} other language(s)." if changed
            else "Nothing to copy - names and descriptions stay per-language.")
        self._mark_edited()
        self._update_counter()
        self.edits_changed.emit()

    def _has_text_edits(self, command_id: int) -> bool:
        for per_language in self.state.nxd_edits_for("job_command").values():
            if per_language.get(command_id):
                return True
        return False

    def _mark_edited(self) -> None:
        for i in range(self.list.count()):
            item = self.list.item(i)
            command_id = item.data(Qt.UserRole)
            # Either half, in any language - see the Jobs page for why a
            # green row that vanishes on a language switch reads as loss.
            edited = (bool(self.state.job_command_edits.get(command_id))
                      or self._has_text_edits(command_id))
            mark_edited(item, edited)

    def _update_counter(self) -> None:
        edited = len({
            *(cid for cid, fields in self.state.job_command_edits.items() if fields),
            *(cid
              for per_language in self.state.nxd_edits_for("job_command").values()
              for cid, fields in per_language.items() if fields),
        })
        self.counter.setText(
            f"{edited} of {self.list.count()} job commands have pending edits")
