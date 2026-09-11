"""
Edit Game Data / Abilities.

512 abilities, and the tab with the most going on: names and descriptions
per language in `ability.<lang>.nxd`, plus a separate override layer in
`OverrideAbilityActionData` that changes what an ability *does* - its range,
area, formula, MP cost.

**The two sentinels are opposite, and that is the trap.**

    OverrideAbilityActionData    -1 means "inherit the vanilla value"
    PoachItemRefRow               0 means "none"; -1 is INVALID

Adjacent tables, opposite conventions, and each is correct for its own
table. Writing 0 into an override scalar does not mean "leave it alone" - it
means "set the range to zero", which is a different ability. Being
consistent across the two would break one of them, so `constants.
OVERRIDE_NOT_SET` is used here and asserted, rather than a literal that
looks like a typo waiting to be tidied.

The override layer is optional per ability: an ability with every scalar at
-1 has no override at all, and the page says so rather than showing nine
zeroes.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QPushButton, QVBoxLayout, QWidget,
    QSizePolicy,
)

from ... import constants as c
from ... import nxd_data
from ... import reference_names
from ... import texture_data as td
from ... import nxd_layouts
from ..widgets.ability_flags import AbilityFlagGroupPanel, ElementFlagPanel
from ..widgets.actions import (
    page_intro,
    TransientNote,
    COPY_LANGUAGES_LABEL, COPY_LANGUAGES_NOTE, ViewToggles,
    apply_view_toggles, language_order, select_list_row,
    set_empty_state,
    copy_edits_to_languages, ensure_language_loaded, mark_edited,
)
from ..widgets.field_rows import (
    AnnotatedNumberRow, CollapsibleSection, DropdownFieldRow, FlagFieldPanel,
    NamedNumberRow, NumericFieldRow,
)
from ..widgets.form_scroll import FormScrollArea
from ..widgets.texture_slot import InlineTextureSlot
from .poaching import TextFieldRow


class JpCostRow(NumericFieldRow):
    """
    JP Cost: one number the reader types, two bytes the game stores.

    `JpCost1` is the LOW byte and `JpCost2` the HIGH byte of a 0-65535
    value. The encoding is not inferred here - `nxd_data.split_jp_cost` and
    `join_jp_cost` are the engine's, they match Zodi's `flag_codex.html`,
    and the Tkinter `JpCostRow` in `gui/step_abilities.py` uses the same
    two functions. Anything that reimplements the shift here would be a
    second opinion about a binary format, which is how the two interfaces
    drift apart.

    **This is not the JPCost in `AbilityData.xml`.** That copy is unused -
    the shipped file's own header says so - and the Tkinter Stats tab
    deliberately hides it, saying "JP Cost isn't shown here". The real one
    is this per-language `.nxd` pair, which is why the row lives in the
    per-language text section beside Name and Description rather than with
    the stats.

    `field_name` is `JpCost1` so the row sorts and loads with the others,
    but `commit_into` writes BOTH bytes - a single row standing for two
    fields is the whole reason this is a class rather than an entry in
    `ABILITY_NUMERIC_FIELDS`.
    """

    def __init__(self, parent=None):
        super().__init__(
            "JpCost1", "JP Cost", c.ABILITY_JP_COST_MIN, c.ABILITY_JP_COST_MAX,
            "", parent=parent)
        self._update_split_note()
        self.value.valueChanged.connect(self._update_split_note)

    def _update_split_note(self, *_args) -> None:
        """
        Shows the two bytes the typed number becomes.

        Tkinter shows this and it earns its place: the mod's XML and any
        other tool will show `JpCost1` and `JpCost2`, so an author checking
        their own work needs to know that 250 JP is 250 and 0, and that 300
        is 44 and 1.
        """
        low, high = nxd_data.split_jp_cost(self.value.value())
        self.set_note(f"\u2192 JpCost1 (low byte): {low}, "
                      f"JpCost2 (high byte): {high}")

    def load_pair(self, low, high, included: bool) -> None:
        """Loads from the two stored bytes rather than from one field."""
        self.load(nxd_data.join_jp_cost(low or 0, high or 0), included)
        self._update_split_note()

    def commit_into(self, edits: dict) -> None:
        """
        Writes both bytes, or removes both.

        Removing both matters as much as writing them: leaving a stale
        `JpCost2` behind while clearing `JpCost1` would write a cost the
        author never typed, and it would look like a tool bug rather than
        a leftover.
        """
        if self.included:
            low, high = nxd_data.split_jp_cost(int(self.value.value()))
            edits["JpCost1"], edits["JpCost2"] = low, high
        else:
            edits.pop("JpCost1", None)
            edits.pop("JpCost2", None)


class OverrideScalarRow(NumericFieldRow):
    """
    An override scalar, where **-1 means "inherit vanilla"**.

    A plain spin box cannot express that: its minimum would have to be -1,
    and -1 would then look like an ordinary value one step below zero. So
    the row carries an explicit "Inherit" state, and the number is only
    meaningful when that is off.

    This matters more than it looks. Writing 0 here does not leave the
    ability alone - it sets the value to zero, which for Range or MP Cost is
    a real and very different ability.
    """

    def __init__(self, field_name: str, label: str, low: int, high: int,
                 note: str = "", parent=None):
        super().__init__(field_name, label, low, high, note, parent=parent)
        self.inherit = QComboBox()
        self.inherit.addItems(["Inherit", "Set to"])
        self.inherit.currentIndexChanged.connect(self._on_inherit)
        self.layout().insertWidget(2, self.inherit)
        self.value.setEnabled(False)

    def _on_inherit(self, index: int) -> None:
        self.value.setEnabled(index == 1)
        if self._loading:
            return
        if not self.include.isChecked():
            self.include.setChecked(True)
            return
        self.edited.emit()

    def get_value_str(self) -> str:
        if self.inherit.currentIndex() == 0:
            return str(c.OVERRIDE_NOT_SET)
        return str(self.value.value())

    def load(self, raw_value, included: bool) -> None:
        self._loading = True
        try:
            try:
                number = int(str(raw_value).strip() or c.OVERRIDE_NOT_SET)
            except (TypeError, ValueError):
                number = c.OVERRIDE_NOT_SET
            inheriting = number == c.OVERRIDE_NOT_SET
            self.inherit.setCurrentIndex(0 if inheriting else 1)
            self.value.setEnabled(not inheriting)
            self.value.setValue(self.value.minimum() if inheriting else number)
            self.include.setChecked(bool(included))
        finally:
            self._loading = False


class AbilitiesPage(QWidget):
    edits_changed = Signal()
    # Asks the shell to open another tab at a particular record. The page
    # does not know what tabs exist; it says where it wants to go and the
    # shell decides whether that is possible.
    navigate_requested = Signal(str, object)
    jump_to_texture = Signal(str)

    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state
        self.current_key = None
        self.text_rows: dict[str, QWidget] = {}
        self.override_rows: dict[str, OverrideScalarRow] = {}

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
        self.language_box.addItems(language_order(
            getattr(c, "NXD_ABILITY_FILENAMES", {"en": ""})))
        self.language_box.currentTextChanged.connect(self._on_language)
        # The widest entry is two characters; a
        # minimum keeps the arrow from crowding it.
        self.language_box.setSizePolicy(
            QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.language_box.setMinimumWidth(72)
        top.addWidget(self.language_box)

        # One button. See the note on Poaching's - the second one ("Copy
        # shared fields for every edit") copied every edited record at once
        # under a label that read like a rewording of this one.
        self.copy_button = QPushButton(COPY_LANGUAGES_LABEL)
        self.copy_button.setToolTip(COPY_LANGUAGES_NOTE)
        self.copy_button.clicked.connect(self.copy_current_to_languages)
        self.copy_button.setSizePolicy(
            QSizePolicy.Fixed, QSizePolicy.Fixed)
        top.addWidget(self.copy_button)
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
            "Every ability in the game. Names and descriptions are per-language; "
            "range, area and formula come from a separate override layer.", self.language_controls))

        self.action_note = TransientNote()
        outer.addWidget(self.action_note)

        # Every tab with field rows gets these, not just Jobs.
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
        self.editing_label = QLabel("Select an ability")
        self.editing_label.setStyleSheet("font-weight: 600; font-size: 12pt;")
        right.addWidget(self.editing_label)

        self.empty_note = QLabel(
            # Reworded: there is no Convert button any more - unpacking
            # converts, and so does adopting a folder with no database.
            "No game data yet.\n\nGo to General Setup and unpack your game, "
            "or point at a folder you've already unpacked.")
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
        for field_name in c.ABILITY_TEXT_FIELDS:
            row = TextFieldRow(field_name, field_name)
            row.edited.connect(self._on_text_edited)
            self.text_rows[field_name] = row
            text_column.addWidget(row)
        for field_name, spec in c.ABILITY_NUMERIC_FIELDS.items():
            low, high, label = spec[0], spec[1], spec[2]
            note = spec[3] if len(spec) > 3 else ""
            row = NumericFieldRow(field_name, label, low, high, note)
            row.edited.connect(self._on_text_edited)
            self.text_rows[field_name] = row
            text_column.addWidget(row)
            if field_name == "IconId":
                # The icon preview follows IconId directly, because it is
                # showing what that number currently points at.
                #
                # **A SHARED sheet, unlike an item's own two icons.** Many
                # abilities reference the same file, so replacing it is
                # "the icon this ability happens to point at", not "this
                # ability's icon". Said on the page rather than left to be
                # discovered by an author who changed one ability and found
                # six others had changed with it.
                shared = QLabel(
                    "This icon is shared across the game's icon sheet - "
                    "replacing it affects everything else pointing at the "
                    "same Icon ID, not just this ability.")
                shared.setProperty("role", "muted")
                shared.setWordWrap(True)
                text_column.addWidget(shared)
                self.icon_slot = InlineTextureSlot("Ability Icon", self.state)
                self.icon_slot.edits_changed.connect(self._after_edit)
                self.icon_slot.view_requested.connect(self.jump_to_texture)
                text_column.addWidget(self.icon_slot)

        # JP Cost, which Tkinter has and this page did not.
        #
        # Placed at the end of the per-language section because that is
        # what it is: `Ability-xx` carries a cost per language, the same
        # table Name and Description come from.
        self.jp_cost_row = JpCostRow()
        self.jp_cost_row.edited.connect(self._on_text_edited)
        text_column.addWidget(self.jp_cost_row)

        override_body = QWidget()
        override_column = QVBoxLayout(override_body)
        override_column.setContentsMargins(0, 0, 0, 0)
        override_column.setSpacing(2)

        self.override_state = QLabel("")
        self.override_state.setProperty("role", "muted")
        self.override_state.setWordWrap(True)
        override_column.addWidget(self.override_state)

        dagger = QLabel(
            "Flags marked \u2020 are stored as the opposite bit - ticking the "
            "box clears the underlying flag, the same as FFTPatcher. Each "
            "group has its own tick box; leave it unticked to inherit this "
            "ability's normal behaviour.")
        dagger.setProperty("role", "muted")
        dagger.setWordWrap(True)
        override_column.addWidget(dagger)

        # The four flag bytes, two to a row - the Tkinter layout, which fits
        # four tall groups in half the height of a single column.
        flags_grid = QGridLayout()
        flags_grid.setSpacing(6)
        self.flag_groups = []
        for index in range(len(c.ABILITY_FLAG_GROUP_LABELS)):
            panel = AbilityFlagGroupPanel(index)
            panel.edited.connect(self._on_override_edited)
            self.flag_groups.append(panel)
            flags_grid.addWidget(panel, index // 2, index % 2)
        override_column.addLayout(flags_grid)

        self.element_panel = ElementFlagPanel()
        self.element_panel.edited.connect(self._on_override_edited)
        override_column.addWidget(self.element_panel)

        for field_name in c.OVERRIDE_SCALAR_FIELD_ORDER:
            spec = c.OVERRIDE_SCALAR_FIELDS[field_name]
            low, high, label = spec[0], spec[1], spec[2]
            note = spec[3] if len(spec) > 3 else ""
            row = OverrideScalarRow(field_name, label, low, high, note)
            row.edited.connect(self._on_override_edited)
            self.override_rows[field_name] = row
            override_column.addWidget(row)

        # -- the three ordinary XML tables --------------------------------
        #
        # Effect, Unit Animations and Base Stats are NOT the override layer:
        # they are reference/diff XML tables with the same include-checkbox
        # convention as JobData.xml, and they need no game unpack. They live
        # here rather than as their own tabs because they are keyed by the
        # same ability id as everything else on this page.
        effect_body = QWidget()
        effect_column = QVBoxLayout(effect_body)
        effect_column.setContentsMargins(0, 0, 0, 0)
        effect_column.setSpacing(2)
        effect_note = QLabel(
            "Which hardcoded effect this ability triggers "
            "(AbilityEffectNumberFilterData.xml). -1 is a real and common "
            "value here - 64 vanilla abilities use it, including the four "
            "Rend skills - so this stays a number you can type rather than "
            "a list: 17 of its vanilla values have no name at all.")
        effect_note.setProperty("role", "muted")
        effect_note.setWordWrap(True)
        effect_column.addWidget(effect_note)
        self.effect_row = AnnotatedNumberRow(
            "EffectId", "Effect ID", c.ABILITY_EFFECT_ID_MIN,
            c.ABILITY_EFFECT_ID_MAX, reference_names.effect_names())
        self.effect_row.edited.connect(self._on_effect_edited)
        effect_column.addWidget(self.effect_row)
        effect_column.addStretch(1)

        animation_body = QWidget()
        animation_column = QVBoxLayout(animation_body)
        animation_column.setContentsMargins(0, 0, 0, 0)
        animation_column.setSpacing(2)
        animation_note = QLabel(
            "Which animations play when this ability executes "
            "(AbilityTypeData.xml). Charge Effect Type and Animation ID are "
            "picked by name - every value the shipped table uses has one.")
        animation_note.setProperty("role", "muted")
        animation_note.setWordWrap(True)
        animation_column.addWidget(animation_note)
        self.animation_rows = {}
        for field_name, label, names in (
                ("ChargeEffectType", "Charge Effect Type",
                 reference_names.charge_effect_names()),
                ("AnimationId", "Animation ID",
                 reference_names.animation_names())):
            row = NamedNumberRow(field_name, label, names)
            row.edited.connect(self._on_animation_edited)
            self.animation_rows[field_name] = row
            animation_column.addWidget(row)
        battle_text = NumericFieldRow("BattleTextId", "Battle Text ID", 0, 255)
        battle_text.edited.connect(self._on_animation_edited)
        self.animation_rows["BattleTextId"] = battle_text
        animation_column.addWidget(battle_text)
        animation_column.addStretch(1)

        stats_body = QWidget()
        stats_column = QVBoxLayout(stats_body)
        stats_column.setContentsMargins(0, 0, 0, 0)
        stats_column.setSpacing(2)
        stats_note = QLabel(
            "AbilityData.xml itself. JP Cost is not here - the shipped "
            "file's own header says that copy is unused, and the one that "
            "matters is on the text section above.")
        stats_note.setProperty("role", "muted")
        stats_note.setWordWrap(True)
        stats_column.addWidget(stats_note)
        self.base_stat_rows = {}
        low, high, label, note = c.ABILITY_XML_NUMERIC_FIELDS["ChanceToLearn"]
        chance = NumericFieldRow("ChanceToLearn", label, low, high, note)
        chance.edited.connect(self._on_base_stat_edited)
        self.base_stat_rows["ChanceToLearn"] = chance
        stats_column.addWidget(chance)
        flags = FlagFieldPanel("Flags", "Flags",
                               {"Flags": c.ABILITY_XML_FLAGS}, columns=1)
        flags.edited.connect(self._on_base_stat_edited)
        self.base_stat_rows["Flags"] = flags
        stats_column.addWidget(flags)
        ability_type = _AbilityTypeRow()
        ability_type.edited.connect(self._on_base_stat_edited)
        self.base_stat_rows["AbilityType"] = ability_type
        stats_column.addWidget(ability_type)
        behaviour = FlagFieldPanel("AIBehaviorFlags", "AI Behaviour Flags",
                                   c.ABILITY_AI_BEHAVIOR_GROUPS, columns=2)
        behaviour.edited.connect(self._on_base_stat_edited)
        self.base_stat_rows["AIBehaviorFlags"] = behaviour
        stats_column.addWidget(behaviour)
        stats_column.addStretch(1)

        # -- every remaining column of Ability-<lang> ----------------------
        # Ten columns existed in the table and were editable nowhere.
        # `dev/audit_field_coverage.py` reported them as GAPs, which is how
        # they came to be here; most are constant across all 512 rows,
        # which is exactly why nobody noticed. A column that is zero
        # everywhere looks like padding until a modder tries to use it, and
        # they cannot try if the tool will not show it.
        raw_body = QWidget()
        raw_column = QVBoxLayout(raw_body)
        raw_column.setContentsMargins(0, 0, 0, 0)
        raw_column.setSpacing(2)
        self.raw_rows = {}
        for field_name, (low, high) in c.ABILITY_UNKNOWN_NUMERIC_FIELDS.items():
            row = NumericFieldRow(
                field_name, field_name, low, high,
                c.ABILITY_UNKNOWN_FIELD_NOTES.get(field_name, ""),
                unknown=True)
            # Into `text_rows`, which is this page's store for
            # `Ability-<lang>` fields regardless of their type - the name is
            # historical. `_on_text_edited` writes every entry into
            # `ability_edits`, and the loader at `load_record` reads the
            # same dict, so a row added here is saved and reloaded without
            # either being touched.
            row.edited.connect(self._on_text_edited)
            self.text_rows[field_name] = row
            self.raw_rows[field_name] = row
            raw_column.addWidget(row)
        raw_column.addStretch(1)

        self.sections = [
            CollapsibleSection("Name, description and icon", text_body,
                               expanded=True),
            CollapsibleSection("What it does (override layer)", override_body,
                               expanded=False),
            CollapsibleSection("Effect", effect_body, expanded=False),
            CollapsibleSection("Unit animations", animation_body,
                               expanded=False),
            CollapsibleSection("Base stats", stats_body, expanded=False),
            CollapsibleSection("Other fields", raw_body,
                               expanded=False),
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

    # -- records ---------------------------------------------------------------

    @property
    def language(self) -> str:
        return self.language_box.currentText() or "en"

    def records(self) -> list:
        return (self.state.ability_records or {}).get(self.language, [])

    def refresh_records(self) -> None:
        self.list.clear()
        records = self.records()
        for record in records:
            # Through the same helper the live rename uses, so a list
            # rebuilt after an edit does not drop back to the vanilla name.
            item = QListWidgetItem(self._ability_label(record.key))
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
        one. Items fixed this some sessions ago; Abilities kept the old
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
        ensure_language_loaded(self.state, "ability_records", self.language)
        # A full rebuild only when the row SET could differ - the list being
        # empty, or a different length. Relabelling assumes the two language
        # tables hold the same keys, which they do in every real conversion;
        # this is the check that stops that assumption silently showing an
        # empty tab if it ever fails.
        if self.list.count() != len(self.records()):
            self.refresh_records()
            return
        for i in range(self.list.count()):
            item = self.list.item(i)
            item.setText(self._ability_label(item.data(Qt.UserRole)))
        self._mark_edited()
        self._update_counter()
        if self.current_key is not None:
            self.load_record(self.current_key)

    def _filter_list(self, text: str) -> None:
        needle = text.strip().lower()
        for i in range(self.list.count()):
            item = self.list.item(i)
            item.setHidden(bool(needle) and needle not in item.text().lower())

    def select_record(self, key) -> None:
        """
        Used by a jump from another tab - Job Commands' Edit button.

        Through the LIST, not straight to `load_record`. Selecting the row
        loads the record as a side effect, and it also moves and scrolls the
        list, which calling `load_record` alone did not: the editor filled
        with the right ability while the list stayed on whichever row it was
        already showing.
        """
        if not select_list_row(self.list, int(key), self.search):
            # Not in the list at all - a filter cleared above should have
            # exposed it, so this means the ability is genuinely absent.
            # Load it anyway rather than doing nothing visible.
            self.load_record(int(key))

    def _on_selection(self, current, _previous) -> None:
        if current is not None:
            self.load_record(current.data(Qt.UserRole))

    def load_record(self, key: int) -> None:
        by_key = {r.key: r for r in self.records()}
        record = by_key.get(key)
        if record is None:
            return
        self.current_key = key
        self.editing_label.setText(f"Editing: {self._ability_label(key)}")

        already = self.state.ability_edits.get(self.language, {}).get(key, {})
        for field_name, row in self.text_rows.items():
            if field_name in already:
                row.load(already[field_name], True)
            else:
                row.load(record.values.get(field_name, ""), False)

        # JP Cost reads TWO stored fields into one control, so it cannot go
        # through the loop above. Ticked only when the mod actually carries
        # a cost - loading a record never ticks anything, which is the rule
        # everywhere else on this page.
        has_edit = "JpCost1" in already or "JpCost2" in already
        source = already if has_edit else record.values
        self.jp_cost_row.load_pair(source.get("JpCost1", 0),
                                   source.get("JpCost2", 0), has_edit)

        self._load_override(key)
        self._load_xml_tables(key)
        self._sync_icon_slot()

    def _sync_icon_slot(self) -> None:
        """
        Points the icon preview at whatever IconId currently says.

        Re-read rather than remembered, because the field is editable: an
        author typing a new icon id wants to see what they have just pointed
        at, not what the ability used to use.
        """
        row = self.text_rows.get("IconId")
        if row is None or getattr(self, "icon_slot", None) is None:
            return
        try:
            icon_id = int(row.get_value_str())
        except (TypeError, ValueError):
            icon_id = 0
        self.icon_slot.set_relative_path(
            td.ability_icon_texture_path(icon_id))

    def _load_xml_tables(self, key: int) -> None:
        """
        Effect, Unit Animations and Base Stats.

        All three are ordinary diff XML keyed by the same ability id, and
        all three read their baseline from `item_table_records` - so they
        work with no game unpacked, unlike the text and override layers
        above them.
        """
        for table_key, rows in (
                ("ability_effect", {"EffectId": self.effect_row}),
                ("ability_animation", self.animation_rows),
                ("ability", self.base_stat_rows)):
            record = (self.state.item_table_records_by_id(table_key)
                      .get(key))
            baseline = record.values if record else {}
            edits = (self.state.item_table_edits.get(table_key, {})
                     .get(key, {}))
            for field_name, row in rows.items():
                default = ("None" if isinstance(row, FlagFieldPanel)
                           else "" if field_name == "AbilityType" else "0")
                row.load(
                    edits.get(field_name, baseline.get(field_name, default)),
                    field_name in edits)

    def _load_override(self, key: int) -> None:
        actions = {a.key: a for a in (self.state.override_action_records or [])}
        action = actions.get(key)
        edits = self.state.override_action_edits.get(key, {})

        for field_name, row in self.override_rows.items():
            if field_name in edits:
                row.load(edits[field_name], True)
            elif action is not None:
                row.load(action.scalars.get(field_name, c.OVERRIDE_NOT_SET), False)
            else:
                row.load(c.OVERRIDE_NOT_SET, False)

        if action is None:
            self.override_state.setText(
                "This ability has no override row, so everything below "
                "inherits the vanilla behaviour. Setting any of them creates "
                "one.")
            return
        overridden = [n for n, v in action.scalars.items()
                      if v != c.OVERRIDE_NOT_SET]
        self.override_state.setText(
            f"Currently overriding: {', '.join(sorted(overridden))}."
            if overridden else
            "Every value here inherits the vanilla behaviour.")

    # -- copying across languages --------------------------------------------
    #
    # Only the text layer travels. The override layer is NOT per-language -
    # what an ability does is not translated - so copying it across would be
    # writing the same row five times and calling it five edits.

    def languages(self) -> list:
        return [self.language_box.itemText(i)
                for i in range(self.language_box.count())]

    # Read from Nenkai's layout, not restated. The hand-written list named
    # Name, Description and Comment and missed `Unknown10`, which is also a
    # string and therefore also a translation - so the copy carried English
    # into it. Same fault as Poaching's, one column instead of five.
    COPY_SKIP_FIELDS = frozenset(
        nxd_layouts.translated_columns("Ability", c.ABILITY_TEXT_FIELDS))

    def copy_current_to_languages(self) -> None:
        if self.current_key is None:
            self.action_note.setText("Pick an ability first.")
            return
        changed = copy_edits_to_languages(
            self.state.ability_edits, self.language, self.current_key,
            self.languages(), skip_fields=self.COPY_SKIP_FIELDS)
        self.action_note.setText(
            f"Copied your edits to {', '.join(changed)}. Names and "
            f"descriptions stay per-language." if changed
            else "Nothing on this ability to copy - names and descriptions "
                 "are never copied between languages.")
        self._after_edit()

    # -- editing -----------------------------------------------------------------

    def _on_text_edited(self) -> None:
        if self.current_key is None:
            return
        language = self.state.ability_edits.setdefault(self.language, {})
        edits = language.setdefault(self.current_key, {})
        for field_name, row in self.text_rows.items():
            if row.included:
                edits[field_name] = row.get_value_str()
            elif field_name in edits:
                del edits[field_name]
        # ...and the pair, which writes both bytes or removes both.
        self.jp_cost_row.commit_into(edits)
        if not edits:
            language.pop(self.current_key, None)
        if not language:
            self.state.ability_edits.pop(self.language, None)
        # The list follows the Name field as it is typed - see the Items
        # page for why. The icon preview follows IconId for the same reason.
        self._refresh_current_name()
        self._sync_icon_slot()
        self._after_edit()

    def _ability_label(self, key: int) -> str:
        """
        Through the shared resolver, so this page and the Job Commands
        dropdowns cannot disagree about what an ability is called.

        It used to read `values["Name"]` directly, which is empty on the
        ja/ko/cs/ct tables - those put the name in `NameSingular` - so four
        of the seven languages listed every ability as "(unnamed)".
        `record_name` tries the columns in order and finds it.
        """
        name = nxd_data.effective_name(self.state, "ability", key, self.language)
        return f"{key:03d} - {name or '(unnamed)'}"

    def _refresh_current_name(self) -> None:
        if self.current_key is None:
            return
        label = self._ability_label(self.current_key)
        row = self.list.currentItem()
        if row is not None and row.data(Qt.UserRole) == self.current_key:
            row.setText(label)
        self.editing_label.setText(f"Editing: {label}")

    def _on_override_edited(self) -> None:
        if self.current_key is None:
            return
        edits = self.state.override_action_edits.setdefault(self.current_key, {})
        for field_name, row in self.override_rows.items():
            if row.included:
                edits[field_name] = row.get_value_str()
            elif field_name in edits:
                del edits[field_name]
        # The element byte and the four flag bytes, each written under its
        # own key. `write_override_action_edits` reads
        # "FlagsGroup0".."FlagsGroup3" and read-modify-writes the physical
        # column, so two groups sharing Flags12 do not clobber each other.
        for panel in [self.element_panel] + self.flag_groups:
            if panel.included:
                edits[panel.field_name] = panel.get_value()
            elif panel.field_name in edits:
                del edits[panel.field_name]
        if not edits:
            self.state.override_action_edits.pop(self.current_key, None)
        self._after_edit()

    def _commit_xml_table(self, table_key: str, rows: dict) -> None:
        """One commit path for the three diff-XML sub-sections."""
        if self.current_key is None:
            return
        table = self.state.item_table_edits.setdefault(table_key, {})
        edits = table.setdefault(self.current_key, {})
        for field_name, row in rows.items():
            if row.included:
                edits[field_name] = row.get_value_str()
            elif field_name in edits:
                del edits[field_name]
        if not edits:
            table.pop(self.current_key, None)
        if not table:
            self.state.item_table_edits.pop(table_key, None)
        self._after_edit()

    def _on_effect_edited(self) -> None:
        self._commit_xml_table("ability_effect", {"EffectId": self.effect_row})

    def _on_animation_edited(self) -> None:
        self._commit_xml_table("ability_animation", self.animation_rows)

    def _on_base_stat_edited(self) -> None:
        self._commit_xml_table("ability", self.base_stat_rows)

    def _after_edit(self) -> None:
        self._mark_edited()
        self._update_counter()
        self.edits_changed.emit()

    def _mark_edited(self) -> None:
        text_edits = self.state.ability_edits.get(self.language, {})
        for i in range(self.list.count()):
            item = self.list.item(i)
            key = item.data(Qt.UserRole)
            # Every store an ability can be edited in, not just two.
            # An ability whose only change is its animation or its AI flags
            # is an edited ability, and a list marking only the text and
            # override layers would show a mod's own work as untouched.
            edited = bool(text_edits.get(key)) or bool(
                self.state.override_action_edits.get(key))
            if not edited:
                edited = any(
                    self.state.item_table_edits.get(table_key, {}).get(key)
                    for table_key in ("ability", "ability_effect",
                                      "ability_animation"))
            mark_edited(item, edited)

    def _update_counter(self) -> None:
        total = self.list.count()
        if not total:
            self.counter.setText("")
            return
        text_edits = {k for k, v
                      in self.state.ability_edits.get(self.language, {}).items() if v}
        overrides = {k for k, v in self.state.override_action_edits.items() if v}
        tables = set()
        for table_key in ("ability", "ability_effect", "ability_animation"):
            tables.update(
                k for k, v
                in self.state.item_table_edits.get(table_key, {}).items() if v)
        edited = len(text_edits | overrides | tables)
        self.counter.setText(f"{edited} of {total} abilities edited")


    def _apply_view(self, hide_notes: bool, hide_unknown: bool,
                    hide_comments: bool) -> None:
        rows = (list(self.text_rows.values())
                + list(self.override_rows.values())
                + list(self.animation_rows.values())
                + list(self.base_stat_rows.values())
                + [self.effect_row, self.element_panel] + self.flag_groups)
        apply_view_toggles(rows, hide_notes, hide_unknown,
                           hide_comments)


class _AbilityTypeRow(DropdownFieldRow):
    """
    AbilityData.xml's `AbilityType` - a NAME, not an id.

    The XML holds `Normal`, `Reaction`, `Movement`; the string itself is the
    value. `DropdownFieldRow` stores an integer id and would write `1`,
    which the mod loader does not recognise - the same trap the Items page's
    `ItemCategory` and `ShopAvailability` fall into, and the reason both
    have a row class of their own rather than reusing the id-based one.
    """

    def __init__(self, parent=None):
        super().__init__("AbilityType", "Ability Type", parent=parent)
        self._loading = True
        try:
            self.combo.clear()
            self._id_to_index = {}
            for index, value in enumerate(c.ABILITY_TYPE_XML_VALUES):
                self.combo.addItem(value, value)
                self._id_to_index[value] = index
        finally:
            self._loading = False

    def current_id(self):
        data = self.combo.currentData()
        return data if data is not None else ""

    def get_value_str(self) -> str:
        return str(self.current_id())

    def load(self, raw_value, included: bool) -> None:
        self._loading = True
        try:
            value = "" if raw_value is None else str(raw_value).strip()
            if value not in self._id_to_index:
                # Shown as itself rather than snapped to the first entry.
                self.combo.addItem(value or "(blank)", value)
                self._id_to_index[value] = self.combo.count() - 1
            self.combo.setCurrentIndex(self._id_to_index[value])
            self.include.setChecked(bool(included))
        finally:
            self._loading = False

    def _sync_jump(self) -> None:
        return
