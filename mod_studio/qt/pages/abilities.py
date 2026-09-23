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

from ... import ability_defaults
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
    apply_view_toggles, language_combo, language_order, select_list_row,
    set_empty_state,
    copy_edits_to_languages, ensure_language_loaded, mark_edited, edit_counter_text)
from ..widgets.field_rows import (
    AnnotatedNumberRow, CollapsibleSection, DropdownFieldRow, FlagFieldPanel,
    NamedNumberRow, NumericFieldRow,
)
from ..widgets.form_scroll import FormScrollArea
from ..widgets.visible_refresh import RefreshesWhenVisible
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

    **The box holds the EFFECTIVE value**: this ability's own override if it
    has one, otherwise the value it inherits. So Meteor's Charge Time reads
    10 (what this game set) and its MP Cost reads 70 (what it leaves alone),
    and ticking either one up starts from the number in front of you.

    What says which of those two a row is showing is the **include box**,
    not the value - the same bargain the Element panel and the four Flagset
    panels have always had, and the reason `_on_override_edited` reads a row
    only when it is included.

    This has been three arrangements, and the history matters because two of
    them were wrong in opposite directions:

    * An "Inherit / Set to" dropdown in front of the value, with the number
      greyed until you picked "Set to". It made the page disagree with the
      file: ability 13 Wall has `-1` in Range, this showed "Inherit" and a
      greyed 0, and the one field where the translation broke down
      (`Formula`) read `001` for a row that actually said `-1`.
    * Then the raw sentinel, `-1`, with the real value written beside it in
      words - honest about the file and useless for working: "the counter
      would simply be set to 5. Ticking it up by one would tick it up to 6."
    * Now the effective value, which is what a modder is actually editing,
      with the include box carrying the distinction the display used to.

    `-1` is still reachable - it is the box's minimum - because writing it
    is how a mod says "stop overriding this", and 32 fields in this game's
    own table override something. Typing the inherited number instead is a
    different edit: it pins the value where -1 follows whatever else is in
    play.

    **No note under it.** "can we remove the field notes for Range, Effect
    Area, Vertical Tolerance, X, Y, CT (Charge Time), and MP Cost" - which
    is every field this class builds.

    Each of the seven used to carry the same three-line sentence about what
    -1 meant, seven times down one column. It was written for the second
    arrangement above, where -1 was the number on screen and the note was
    the only thing saying what it stood for. In the third there is no -1 to
    explain: the box holds the effective value and the include box says
    whether it is being written. The sentence outlived the display it was
    describing.
    """

    def __init__(self, field_name: str, label: str, low: int, high: int,
                 parent=None):
        # The floor is the sentinel, not the field's own minimum - without
        # that the box cannot hold what the file holds.
        super().__init__(field_name, label, c.OVERRIDE_NOT_SET, high, "",
                         parent=parent)
        self.inherited_value = None

    def get_value_str(self) -> str:
        return str(self.value.value())

    def set_inherited(self, value) -> None:
        """
        What the box reads if it is ever left sitting ON the sentinel.

        `_load_override` puts the effective value in the box, so the usual
        row never shows -1 at all. This is for the two cases that still can:
        a mod author who deliberately types -1 to stop overriding a field,
        and any row at all when `data/AbilityActionDefaults.txt` is missing.

        `setSpecialValueText` is what Qt draws in place of the number when a
        spin box sits at its minimum, and the minimum here IS the sentinel -
        so it applies exactly then and never otherwise. `value()` is
        untouched, so `get_value_str()` still returns "-1" and the mod still
        writes -1.

        It says "Inherits 6" rather than "6" for the reason the whole field
        was once built around: -1 and 6 are different edits, and two rows in
        different states must not draw identically. That distinction now
        lives in the include box for the common case; here, where the value
        really is the sentinel, the words carry it.

        None clears it, and the box shows `-1` - which is what the file says
        and what every other tool on this data shows.
        """
        self.inherited_value = None if value is None else int(value)
        self.value.setSpecialValueText(
            "" if value is None else f"Inherits {int(value)}")

    def load(self, raw_value, included: bool) -> None:
        self._loading = True
        try:
            try:
                number = int(str(raw_value).strip() or c.OVERRIDE_NOT_SET)
            except (TypeError, ValueError):
                number = c.OVERRIDE_NOT_SET
            self.value.setValue(number)
            self.include.setChecked(bool(included))
        finally:
            self._loading = False


class OverrideChoiceRow(DropdownFieldRow):
    """
    An override field picked from a named list, with **Inherit as an entry**.

    Three fields use it. `Formula` selects one of the game's hardcoded
    damage routines, where 7 tells a beginner nothing and
    "007 - Heal_[Weapon]" tells them what it does. `InflictStatus` is
    dual-purpose in exactly the way the item field is: normally it names a
    row of `ItemOptionsData.xml`, and when this ability's `Formula` is 2
    the same byte is an ability to cast.

    **Inherit is the first entry rather than a separate control.** The
    dropdown already has to show one of several named things; "inherit" is
    one more named thing, and a second widget in front of it to say which
    kind of answer this is was the arrangement that made `Formula` read
    `001` for a row holding `-1`. The list cannot misreport the file,
    because the file's value IS one of the entries.

    A `DropdownFieldRow` like every other picker on this page and on Job
    Commands, so the Edit button, the 200px label and the include checkbox
    are the same furniture in the same places.
    """

    #: What the sentinel is called in the list when nothing is known about
    #: what it inherits - no defaults file, or an id the file has no row for.
    INHERIT_LABEL = "Inherit (leave the ability's own value)"

    def __init__(self, field_name: str, label: str, choices: dict,
                 jump_label: str | None = None, jump_tooltip: str = "",
                 parent=None):
        #: The value this ability inherits for this field, and what it is
        #: called. Set per RECORD, not per list - every other entry in the
        #: dropdown is the same whichever ability is selected and this one
        #: is not, because each ability inherits its own value.
        self.inherited_value = None
        self._inherited_label = ""
        super().__init__(field_name, label, parent=parent,
                         jump_label=jump_label, jump_tooltip=jump_tooltip,
                         zero_is_none=False)
        self.set_override_choices(choices)

    def set_override_choices(self, choices: dict) -> None:
        """
        The named values, with Inherit in front.

        `zero_is_none` is off for these lists: 0 is an ordinary value here -
        formula 0 is a real routine and status row 0 is a real row - and the
        thing that means "nothing" is -1, which has its own entry.
        """
        self.set_choices({c.OVERRIDE_NOT_SET: self._inherit_text(), **choices})

    def _inherit_text(self) -> str:
        return self._inherited_label or self.INHERIT_LABEL

    def set_inherited(self, value, label: str) -> None:
        """
        Names what this ability's -1 actually means, for this record.

        Retitles the one entry rather than rebuilding the list, so the
        selection survives and nothing registers as an edit.
        """
        self.inherited_value = value
        self._inherited_label = label
        self.set_choice_label(c.OVERRIDE_NOT_SET, self._inherit_text())
        # The jump target depends on what is inherited, so changing that
        # changes whether there is anywhere to jump to. `set_choice_label`
        # only retitles; without this the button kept whatever enabled
        # state the previous ability left it in.
        self._sync_jump()

    def jump_target(self):
        """
        Where the `Edit ->` button should go.

        **The whole point of overriding this.** Every vanilla ability holds
        -1 in `InflictStatus`, so the button was always sitting on the
        sentinel - and it asked the shell to open row **-1**, which is not a
        row. Reported as "make sure the Edit jump button works for these".

        On -1 it now goes to the value being INHERITED, which is the row
        the field is actually pointing at. With nothing known to inherit
        there is still nothing to open, and the button is disabled rather
        than sending the shell somewhere that does not exist.
        """
        value = self.current_id()
        if value == c.OVERRIDE_NOT_SET:
            return self.inherited_value
        return value

    def _sync_jump(self) -> None:
        if self.jump_button is not None:
            target = self.jump_target()
            self.jump_button.setEnabled(target is not None and target >= 0)

    def _emit_jump(self) -> None:
        target = self.jump_target()
        if target is not None and target >= 0:
            self.jump_requested.emit(int(target))


class AbilitiesPage(RefreshesWhenVisible, QWidget):
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
        #: The game's own ability table, read on first use. None means
        #: "not read yet"; {} means "read and unusable", which is a
        #: different thing and is why this is not just {}.
        self._ability_defaults = None
        #: `{field name: its caption as built}`, before any inherited value
        #: is written in front of it. `set_note` replaces the whole string,
        #: so rebuilding it per record needs the original.
        self._override_notes: dict = {}

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
        self.language_box = language_combo(
            getattr(c, "NXD_ABILITY_FILENAMES", {"en": ""}))
        self.language_box.currentTextChanged.connect(self._on_language)
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
            "Every ability in the game select one to make changes.",
            self.language_controls))

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
                    "This icon is shared across the abilities. Replacing it "
                    "affects everything else pointing at the same Icon ID, "
                    "not just this ability.")
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

        # The sentence explaining the dagger is gone, at Zodi's request. The
        # daggers stay, and so does the explanation - on each marked flag's
        # own tooltip ("Stored as the opposite bit..."), set in
        # `AbilityFlagGroupPanel`, and the Override box's tooltip says what
        # leaving it unticked does. `test_qt_abilities` checks both survive,
        # so the page never has a mark nothing on it explains.

        for field_name in c.OVERRIDE_SCALAR_FIELD_ORDER:
            spec = c.OVERRIDE_SCALAR_FIELDS[field_name]
            low, high, label = spec[0], spec[1], spec[2]
            if field_name == "InflictStatus":
                row = self._make_inflict_row()
            elif field_name == "Formula":
                # The same dropdown the Items page gives the same field,
                # from the same list - two pages naming one concept
                # differently is two things to learn.
                row = OverrideChoiceRow(field_name, label,
                                        reference_names.formula_names())
            else:
                # `spec[3]` - the layout's own help text - is deliberately
                # not passed. Effect Area's "AoE radius override." is a
                # field note on Effect Area, and Effect Area is one of the
                # seven that were asked to lose theirs. The text stays in
                # `constants.py` for anything else that wants it.
                row = OverrideScalarRow(field_name, label, low, high)
            row.edited.connect(self._on_override_edited)
            if field_name == "Formula":
                # Formula decides what Inflict Status MEANS, so changing it
                # has to change that row without reloading the ability.
                row.edited.connect(self._sync_inflict_kind)
            self.override_rows[field_name] = row
            self._override_notes[field_name] = getattr(
                row, "_note_text", "") or ""
            override_column.addWidget(row)

        # The five packed-byte panels go BELOW the numbers, not above them.
        #
        # "can we change the order of the fields so that it is Range, Effect
        # Area, Vertical Tolerance, Formula, Inflict Status, X, Y, CT
        # (Charge Time), MP Cost, Element, then the Flagsets."
        #
        # `OVERRIDE_SCALAR_FIELD_ORDER` already gave the nine numbers that
        # order; what put the section in the wrong one was these four tall
        # grids and the element row sitting in front of them, so the first
        # thing on screen was thirty tick boxes and the numbers were below
        # the fold. The numbers are what most edits touch.
        # The four flag bytes, two to a row - the Tkinter layout, which fits
        # four tall groups in half the height of a single column.
        # Element first, then the four Flagsets - "...MP Cost, Element, then
        # the Flagsets". Element is one row of eight tick boxes; the
        # Flagsets are four tall grids of eight, and putting the short one
        # first keeps the section readable from the top down.
        self.element_panel = ElementFlagPanel()
        self.element_panel.edited.connect(self._on_override_edited)
        override_column.addWidget(self.element_panel)

        flags_grid = QGridLayout()
        flags_grid.setSpacing(6)
        self.flag_groups = []
        for index in range(len(c.ABILITY_FLAG_GROUP_LABELS)):
            panel = AbilityFlagGroupPanel(index)
            panel.edited.connect(self._on_override_edited)
            self.flag_groups.append(panel)
            flags_grid.addWidget(panel, index // 2, index % 2)
        override_column.addLayout(flags_grid)

        self.override_column = override_column

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
            # Open by default, like the Encounters page's four. It is the
            # section this tab exists for - what an ability DOES - and it
            # is where every one of the last two rounds' changes landed,
            # so opening on a closed one hid all of them.
            CollapsibleSection("What it does (override layer)", override_body,
                               expanded=True),
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

    def ability_defaults(self) -> dict:
        """
        The game's own ability table, read once and kept.

        `data/AbilityActionDefaults.txt`, which ships populated. Read once
        because it is 368 rows of a file on disk that does not change while
        the tool runs, and `{}` when it cannot be read at all - the page
        then shows -1 for an inherited field, exactly as it did before this
        file existed.
        """
        if self._ability_defaults is None:
            self._ability_defaults = ability_defaults.load()
        return self._ability_defaults

    def inherited_override(self, key, field_name):
        """What this ability's `field_name` holds when the override is -1."""
        return ability_defaults.inherited(self.ability_defaults(), key,
                                          field_name)

    def _refresh_inherited(self, key) -> None:
        """
        Puts the vanilla value behind each -1 in front of the person.

        Reported from real use: "on the Abilities page under What it does
        (override layer) if the field has an Inherit value can we display
        the value that is being inherited instead?"

        It is worth more than it sounds. In the vanilla game **eight of the
        ten override fields are -1 on all 368 rows** - Range, Effect Area,
        Vertical, Element, Formula, X, Y and Inflict Status - so those eight
        said nothing whatsoever until this existed.

        **Three shapes, and none of them is a note any more.** Asked for
        afterwards: "can you input the inherited values into the fields
        (including the Element field and the four Flagsets) instead putting
        the value in the field note."

        * A dropdown gets it as the text of its Inherit ENTRY, the way the
          Encounters dropdowns do - so the id appears twice in one list,
          once as `012 - Heal_F(MA*Y) NS NE` and once bare, which are
          different answers: picking the numbered one writes 12 and pins it,
          leaving the bare one writes -1 and follows the game.
        * A plain number gets it as the text the spin box draws at its
          minimum, which is the sentinel - "Inherits 6" rather than "-1".
          See `OverrideScalarRow.set_inherited` for why it keeps the word.
        * The Element panel and the four Flagset panels tick the boxes the
          vanilla byte sets. Nothing is written: an unincluded panel is
          skipped by `_on_override_edited` whatever it is drawing.

        The note keeps the sentence explaining what -1 means, which is a
        different sentence and still worth one line.
        """
        for field_name, row in self.override_rows.items():
            value = self.inherited_override(key, field_name)
            if isinstance(row, OverrideChoiceRow):
                row.set_inherited(value, self._describe_inherited(field_name,
                                                                  value))
            else:
                row.set_inherited(value)
            # Whatever shape the field is, it says this ONCE. The note used
            # to carry "Inherits 6." in front of it and now carries only
            # what it always did - two places saying one thing is two
            # places free to disagree, which is the fault the Encounters
            # captions were trimmed for in the same round.
            row.set_note(self._override_notes.get(field_name, ""))

        # The Element byte and the four flag bytes. `FLAG_COLUMN_FOR_GROUP`
        # maps a panel's group index onto its column in the shipped table,
        # from the same place the file's column order comes from.
        self.element_panel.set_inherited(
            self.inherited_override(key, "Element"))
        for panel in self.flag_groups:
            column = ability_defaults.FLAG_COLUMN_FOR_GROUP.get(
                panel.group_index)
            panel.set_inherited(self.inherited_override(key, column)
                                if column else None)

    def _effective_override(self, key: int, field_name: str, stored):
        """
        What the control should show: the override if there is one, else the
        value it inherits, else the sentinel.

        The third case is not a fallback nobody hits - delete
        `data/AbilityActionDefaults.txt` and it is every field on every
        ability. The page has to stay usable then, showing -1 exactly as it
        did before that file existed.
        """
        try:
            if int(stored) != c.OVERRIDE_NOT_SET:
                return stored
        except (TypeError, ValueError):
            return stored
        inherited = self.inherited_override(key, field_name)
        return c.OVERRIDE_NOT_SET if inherited is None else inherited

    def _describe_inherited(self, field_name: str, value) -> str:
        """
        The inherited value of a dropdown field, in that dropdown's words.

        Named through the same list the entry for that id uses, so the two
        cannot disagree - and left as a bare number when the list has no
        name for it, rather than as an empty parenthesis.
        """
        if value is None:
            return ""
        row = self.override_rows.get(field_name)
        if field_name == "Formula":
            named = reference_names.formula_names().get(value)
        elif getattr(row, "lists_abilities", False):
            # Formula 2 makes this byte an ability to cast, not a status row.
            from ..app import ability_choices
            named = ability_choices(self.state).get(value)
        else:
            named = self._inflict_choices().get(value)
        return named or str(value)

    def _load_override(self, key: int) -> None:
        actions = {a.key: a for a in (self.state.override_action_records or [])}
        action = actions.get(key)
        edits = self.state.override_action_edits.get(key, {})

        # Before the rows are filled. Each row's Inherit entry names what
        # THIS ability inherits, so it has to be right by the time `load`
        # selects it - otherwise a row sitting on -1 shows the previously
        # selected ability's value for as long as it is on screen.
        self._refresh_inherited(key)

        for field_name, row in self.override_rows.items():
            if field_name in edits:
                row.load(edits[field_name], True)
                continue
            stored = (action.scalars.get(field_name, c.OVERRIDE_NOT_SET)
                      if action is not None else c.OVERRIDE_NOT_SET)
            # **The control holds the EFFECTIVE value, not the sentinel.**
            #
            # "for values that set to -1 and display what their inherited
            # value is I want them set to that displayed value. So for
            # Range, Effect Area, ... if for example if it inherits 5 then
            # the counter would simply be set to 5. Ticking it up by one
            # would tick it up to 6."
            #
            # Right, and it makes the whole layer consistent: the Element
            # panel and the four Flagsets already worked this way, showing
            # the byte they inherit with their own tick box unticked. These
            # ten were the odd ones out, sitting on -1 with the real value
            # written beside them in words.
            #
            # **Nothing is written by it.** `_on_override_edited` reads a
            # row only when it is INCLUDED, and loading never includes -
            # which is the same bargain the panels have always had, and the
            # reason the include box rather than the value is what says
            # "this is mine".
            row.load(self._effective_override(key, field_name, stored),
                     False)

        # -- and the five packed-byte panels ------------------------------
        #
        # **These were not loaded at all.** Measured: ability 234 sets
        # Flags3 to 18 in the real table, and its Flagset III panel drew
        # empty, unticked, with a blank note - and stayed exactly that way
        # when another ability was selected, because nothing ever told it
        # otherwise. Two consequences, both real: a mod that sets a flag
        # byte was invisible here, and whatever a user ticked on one
        # ability was still ticked on the next, where
        # `_on_override_edited` would have written it.
        #
        # Found while adding the inherited values to them, which is the
        # usual way: the panels had to start showing the right ability
        # before "the right ability's vanilla byte" meant anything.
        for panel in [self.element_panel] + self.flag_groups:
            name = panel.field_name
            if name in edits:
                panel.load(edits[name], True)
            elif action is None:
                panel.load(c.OVERRIDE_NOT_SET, False)
            elif panel is self.element_panel:
                panel.load(action.scalars.get("Element", c.OVERRIDE_NOT_SET),
                           False)
            else:
                # Two groups share one physical column, so the record's own
                # accessor does the unpacking rather than this page
                # indexing into `flags12`/`flags34` itself.
                panel.load(action.flag_group_value(panel.group_index), False)

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

    def _uses_ability_formula(self) -> bool:
        """
        Whether this ability's Formula override makes Inflict Status an
        ability id.

        Reads the same rule the Items page and the usage index read, from
        one definition, so the three cannot disagree about what Formula 2
        means.
        """
        from .table_editor import FORMULA_CASTS_ABILITY

        row = self.override_rows.get("Formula")
        if row is None:
            return False
        try:
            return int(row.get_value_str()) == FORMULA_CASTS_ABILITY
        except (TypeError, ValueError):
            return False

    def _inflict_choices(self) -> dict:
        """
        Every Inflict Status row, named as the Inflict Status page names it.

        Same source as the Items page uses for the same field, so one row
        cannot be described two ways in one tool.
        """
        from .table_editor import inflict_status_descriptor

        records = (self.state.item_table_records or {}).get(
            "item_options", [])
        edits = (self.state.item_table_edits or {}).get("item_options", {})
        return {r.item_id: inflict_status_descriptor(
            {**r.values, **edits.get(r.item_id, {})}) for r in records}

    def _make_inflict_row(self):
        """The control for `InflictStatus`, chosen by the current Formula."""
        from ..app import ability_choices

        label = c.OVERRIDE_SCALAR_FIELDS["InflictStatus"][2]
        if self._uses_ability_formula():
            row = OverrideChoiceRow(
                "InflictStatus", "Cast Spell", ability_choices(self.state),
                jump_label="Edit \u2192",
                jump_tooltip="Open this ability on the Abilities tab")
            row.jump_requested.connect(self._jump_to_own_ability)
            row.lists_abilities = True
            return row
        row = OverrideChoiceRow(
            "InflictStatus", label, self._inflict_choices(),
            jump_label="Edit \u2192",
            jump_tooltip="Open this row on the Inflict Status tab")
        # Through the page's general router, which every other cross-tab
        # jump on this page already uses.
        row.jump_requested.connect(
            lambda row_id: self.navigate_requested.emit(
                "Inflict Status", int(row_id)))
        row.lists_abilities = False
        return row

    def _jump_to_own_ability(self, ability_id: int) -> None:
        """Opens the spell this ability casts, on this same tab."""
        if ability_id >= 0:
            self.select_record(ability_id)

    def _sync_inflict_kind(self) -> None:
        """
        Swaps the Inflict Status control when Formula crosses into or out of 2.

        In place, like the Items page: the change is triggered BY the
        Formula row, and rebuilding the column would delete widgets around
        the one being edited. Does nothing while the kind is unchanged.
        """
        old = self.override_rows.get("InflictStatus")
        if old is None:
            return
        # What the row currently LISTS, recorded rather than inferred from
        # its type - both states are the same widget class now.
        if self._uses_ability_formula() == getattr(old, "lists_abilities",
                                                   False):
            return
        index = self.override_column.indexOf(old)
        if index < 0:
            return
        value, included = old.get_value_str(), old.included
        self.override_column.takeAt(index)
        old.setParent(None)
        old.deleteLater()
        row = self._make_inflict_row()
        # The byte does not change when the formula does - what changes is
        # what it means - so the value carries across rather than resetting.
        row.load(value, included)
        row.edited.connect(self._on_override_edited)
        self.override_rows["InflictStatus"] = row
        self.override_column.insertWidget(index, row)
        apply_view_toggles([row], *self.view_toggles.state())

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

    def refresh_from_store(self) -> None:
        """
        Re-read the selected ability when this page comes back on screen.

        `load_record` covers all five stores an ability is spread across -
        the per-language text, the JP cost pair, the override, and the three
        XML tables - so one call re-ticks whatever another page wrote. See
        `widgets/visible_refresh.py` for why a stale tick is a deletion.
        """
        if self.current_key is None:
            return
        self.load_record(self.current_key)
        self._mark_edited()
        self._update_counter()

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
        self.counter.setText(edit_counter_text(edited, total, "abilities"))


    def _apply_view(self, hide_notes: bool, hide_unknown: bool,
                    hide_comments: bool) -> None:
        # JP Cost is named on its own because it is not in `text_rows`: it
        # stands for two columns, so it has an attribute of its own - and a
        # list built from the dicts left it out. That is the whole of "Hide
        # field notes misses JP Cost". `audit_view_toggles` now walks the
        # page's widgets rather than its dicts, so a row left off this list
        # is reported instead of found by somebody reading its note.
        rows = (list(self.text_rows.values())
                + [self.jp_cost_row]
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
