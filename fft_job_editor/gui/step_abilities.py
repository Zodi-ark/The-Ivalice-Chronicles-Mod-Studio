"""
The "Abilities" tab within the combined Edit Game Data step.

Fundamentally different from the Jobs/Job Commands tabs: those edit XML
tables the mod loader itself ships and diffs, but Abilities live in .nxd
files that only exist after unpacking the actual game (see nxd_data.py's
module docstring). This tab edits the SQLite database FF16Tools'
nxd-to-sqlite produces - General Setup's "Unpack and Prepare Game Files"
button is what actually populates app.state_data.nxd_sqlite_path (as does
opening an existing .sqlite from its Advanced options); until that's done,
this tab has nothing to show and says so.

Four sub-areas, same include/inherit-checkbox idea as everywhere else in
this tool, split because they're genuinely different data:
  - "Ability Info" - per-language (Ability-en/ja/etc.) - Name, Description,
    JP Cost, icon, etc. Edits apply only to the language currently being
    viewed, but non-text fields get a "Copy to all languages" button so
    propagating a value everywhere is a deliberate one-click action. Icon
    ID gets a live texture preview (InlineTextureSlot, reused from
    step_textures.py/step_items.py) showing whatever ui/ffto/icon/ability/
    texture/a_<IconId>_uitx.tex currently resolves to, updating as IconId
    changes - unlike Items' own 1:1 art/sprite icons, this is a SHARED
    icon sheet (only 55 real files, ids 0-54, confirmed against a real
    unpacked folder - the field itself allows 0-65535) that many abilities
    can point at, so replacing it isn't "this ability's icon" so much as
    "the icon this ability currently happens to reference".
  - "Flags / Element / Overrides" - OverrideAbilityActionData, shared
    across every language regardless of which one's selected.
  - "Unit Animations" - AbilityTypeData.xml, "Effect" -
    AbilityEffectNumberFilterData.xml, and "Base Stats" - AbilityData.xml
    (ChanceToLearn/Flags/AbilityType/AIBehaviorFlags - JPCost is
    deliberately excluded, see constants.py). Unlike the two sub-areas
    above, none of these three are nxd/sqlite data - they're ordinary
    reference/diff XML tables, the exact same shape as JobData.xml, wired
    into item_xml_io.py's generic TableSpec engine (see constants.py's own
    sections on each for the real-manager-confirmed field/filename
    details) exactly like Treasure Hunter's MapTrapFormationData.xml. They
    live here rather than as their own top-level tabs (unlike Treasure
    Hunter) because they're keyed by the exact same ability id as
    everything else on this page - "shared across every language" in the
    same sense Flags/Element/Overrides is, just a different underlying
    storage mechanism (item_table_edits, not ability_edits/
    override_action_edits), so they get their own item_table_
    edits["ability_effect"/"ability_animation"/"ability"] entries and
    their own WizardState counters rather than folding into
    override_action_edits. Neither strictly needs a converted ability
    database the way Ability Info/Flags/Element/Overrides do, but all
    three still sit behind the same ability-picker tree, which does.

Edits commit to app.state_data.ability_edits / override_action_edits /
item_table_edits["ability_effect"/"ability_animation"] immediately on every
change, same as Jobs/Job Commands.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .. import constants as c
from .. import reference_names
from .. import item_xml_io
from .. import nxd_data
from .. import texture_data as td
from .step_editor import NOTE_STYLE, UNKNOWN_ROW_STYLE, is_unknown_field, ItemFlagFieldPanel, ScrollableFrame, XmlDropdownRow, XmlNumberRow, nxd_missing_data_message
from .step_textures import InlineTextureSlot

NUMBER_FIELD_NAMES = ["IconId", "DLCFlags", "UiId", "UiId2", "AbilityReactionVoiceTypeId"]
BOOL_FIELD_NAMES = ["IsRandomDamage", "IsRandomStatus"]


# =============================================================================
# Ability Info (per-language) field widgets
# =============================================================================

class AbilityTextRow:
    """
    [include] label [Entry or multi-line Text] - Name/Description/Comment.

    No copy-to-all by default (text is inherently per-language) - pass
    copyable=True for a field where copying anyway is genuinely wanted (a
    "Comment" column that isn't game text, for instance - see
    step_encounters.py's Unit Names tab, where Zodi asked for DLC Flags/
    Generic Unit/Comment to be copyable but Name to stay per-language-only).
    Implemented by binding copy_fields onto the instance only when
    copyable=True, so every master "Copy all fields" button's existing
    hasattr(widget, "copy_fields") duck-typing check keeps working
    unchanged - non-copyable text fields simply never have the attribute.
    """

    def __init__(
        self, parent, field_name: str, label: str, on_user_edit, multiline: bool = False,
        copyable: bool = False,
    ):
        self.field_name = field_name
        self.multiline = multiline
        self._on_user_edit = on_user_edit
        self._suppress = False

        self.include_var = tk.BooleanVar(value=False)

        header = ttk.Frame(parent)
        header.pack(fill="x", pady=(6 if multiline else 2, 0))
        ttk.Checkbutton(header, variable=self.include_var, command=self._fire_edit).pack(side="left")
        ttk.Label(header, text=label, width=20, anchor="w").pack(side="left")

        if multiline:
            self.value_var = None
            self.text_widget = tk.Text(parent, height=3, wrap="word")
            self.text_widget.pack(fill="x", padx=(24, 0), pady=(2, 6))
            self.text_widget.bind("<KeyRelease>", self._on_text_changed)
        else:
            self.text_widget = None
            self.value_var = tk.StringVar(value="")
            entry = ttk.Entry(header, textvariable=self.value_var)
            entry.pack(side="left", fill="x", expand=True, padx=(4, 10))
            self.value_var.trace_add("write", self._on_value_written)

        if copyable:
            self.copy_fields = self._copy_fields_impl

    def _copy_fields_impl(self) -> dict:
        return {self.field_name: self.get_value()}

    def _on_text_changed(self, _event=None) -> None:
        if self._suppress:
            return
        self.include_var.set(True)
        self._fire_edit()

    def _on_value_written(self, *_args) -> None:
        if self._suppress:
            return
        self.include_var.set(True)
        self._fire_edit()

    def _fire_edit(self) -> None:
        if self._on_user_edit:
            self._on_user_edit()

    def load(self, value, included: bool) -> None:
        self._suppress = True
        text = "" if value is None else str(value)
        if self.multiline:
            self.text_widget.delete("1.0", "end")
            self.text_widget.insert("1.0", text)
        else:
            self.value_var.set(text)
        self._suppress = False
        self.include_var.set(included)

    def get_value(self) -> str:
        if self.multiline:
            return self.text_widget.get("1.0", "end-1c")
        return self.value_var.get()

    @property
    def included(self) -> bool:
        return self.include_var.get()


class AbilityNumberRow:
    """[include] label [spinbox] help [Copy to all languages] - a per-language numeric Ability field."""

    def __init__(self, parent, field_name: str, bounds: tuple, on_user_edit, on_copy_all=None):
        self.field_name = field_name
        self.min_v, self.max_v, self.label, self.help_text = bounds
        self._on_user_edit = on_user_edit
        self._on_copy_all = on_copy_all
        self._suppress = False

        self.include_var = tk.BooleanVar(value=False)
        self.value_var = tk.StringVar(value=str(self.min_v))

        row = ttk.Frame(parent, style=UNKNOWN_ROW_STYLE if is_unknown_field(field_name, self.label) else "")
        row.pack(fill="x", pady=2)
        ttk.Checkbutton(row, variable=self.include_var, command=self._fire_edit).pack(side="left")
        ttk.Label(row, text=self.label, width=24, anchor="w").pack(side="left")
        vcmd = row.register(lambda p: p == "" or p.isdigit())
        spin = ttk.Spinbox(
            row, from_=self.min_v, to=self.max_v, textvariable=self.value_var,
            width=10, validate="key", validatecommand=(vcmd, "%P"),
        )
        spin.pack(side="left", padx=(4, 10))
        spin.bind("<FocusOut>", lambda e: self._clamp())
        self.value_var.trace_add("write", self._on_value_written)
        if on_copy_all:
            ttk.Button(
                row, text="Copy to all languages", command=lambda: self._on_copy_all(self)
            ).pack(side="left", padx=(4, 0))
        if self.help_text:
            ttk.Label(parent, text=self.help_text, style=NOTE_STYLE, wraplength=600).pack(
                anchor="w", padx=(24, 0), pady=(0, 2)
            )

    def _clamp(self) -> None:
        try:
            v = int(self.value_var.get())
        except ValueError:
            v = self.min_v
        v = max(self.min_v, min(self.max_v, v))
        if str(v) != self.value_var.get():
            self._suppress = True
            self.value_var.set(str(v))
            self._suppress = False

    def _on_value_written(self, *_args) -> None:
        if self._suppress:
            return
        self.include_var.set(True)
        self._fire_edit()

    def _fire_edit(self) -> None:
        if self._on_user_edit:
            self._on_user_edit()

    def load(self, value, included: bool) -> None:
        self._suppress = True
        try:
            v = max(self.min_v, min(self.max_v, int(value)))
        except (ValueError, TypeError):
            v = self.min_v
        self.value_var.set(str(v))
        self._suppress = False
        self.include_var.set(included)

    def get_value(self) -> int:
        try:
            v = int(self.value_var.get())
        except ValueError:
            v = self.min_v
        return max(self.min_v, min(self.max_v, v))

    def copy_fields(self) -> dict:
        return {self.field_name: self.get_value()}

    @property
    def included(self) -> bool:
        return self.include_var.get()


class AbilityBoolRow:
    """[include] label [checkbox 0/1] help [Copy to all languages] - IsRandomDamage/IsRandomStatus."""

    def __init__(self, parent, field_name: str, label: str, help_text: str, on_user_edit, on_copy_all=None):
        self.field_name = field_name
        self.help_text = help_text
        self._on_user_edit = on_user_edit
        self._on_copy_all = on_copy_all
        self._suppress = False

        self.include_var = tk.BooleanVar(value=False)
        self.bool_var = tk.BooleanVar(value=False)

        row = ttk.Frame(parent, style=UNKNOWN_ROW_STYLE if is_unknown_field(field_name, label) else "")
        row.pack(fill="x", pady=2)
        ttk.Checkbutton(row, variable=self.include_var, command=self._fire_edit).pack(side="left")
        ttk.Label(row, text=label, width=24, anchor="w").pack(side="left")
        ttk.Checkbutton(row, variable=self.bool_var, command=self._on_bool_changed).pack(side="left", padx=(4, 10))
        if on_copy_all:
            ttk.Button(
                row, text="Copy to all languages", command=lambda: self._on_copy_all(self)
            ).pack(side="left", padx=(4, 0))
        if self.help_text:
            ttk.Label(parent, text=self.help_text, style=NOTE_STYLE, wraplength=600).pack(
                anchor="w", padx=(24, 0), pady=(0, 2)
            )

    def _on_bool_changed(self) -> None:
        if self._suppress:
            return
        self.include_var.set(True)
        self._fire_edit()

    def _fire_edit(self) -> None:
        if self._on_user_edit:
            self._on_user_edit()

    def load(self, value, included: bool) -> None:
        self._suppress = True
        try:
            v = bool(int(value))
        except (ValueError, TypeError):
            v = False
        self.bool_var.set(v)
        self._suppress = False
        self.include_var.set(included)

    def get_value(self) -> int:
        return 1 if self.bool_var.get() else 0

    def copy_fields(self) -> dict:
        return {self.field_name: self.get_value()}

    @property
    def included(self) -> bool:
        return self.include_var.get()


class JpCostRow:
    """
    [include] "JP Cost" [spinbox 0-65535] "-> JpCost1 X, JpCost2 Y" [Copy to all languages].

    Edited as one combined value; split into JpCost1 (low byte)/JpCost2
    (high byte) on commit - matches Zodi's flag_codex.html exactly (see
    nxd_data.split_jp_cost/join_jp_cost).
    """

    def __init__(self, parent, on_user_edit, on_copy_all=None):
        self.field_name = "JpCost"
        self._on_user_edit = on_user_edit
        self._on_copy_all = on_copy_all
        self._suppress = False

        self.include_var = tk.BooleanVar(value=False)
        self.value_var = tk.StringVar(value="0")

        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Checkbutton(row, variable=self.include_var, command=self._fire_edit).pack(side="left")
        ttk.Label(row, text="JP Cost", width=24, anchor="w").pack(side="left")
        vcmd = row.register(lambda p: p == "" or p.isdigit())
        spin = ttk.Spinbox(
            row, from_=c.ABILITY_JP_COST_MIN, to=c.ABILITY_JP_COST_MAX, textvariable=self.value_var,
            width=10, validate="key", validatecommand=(vcmd, "%P"),
        )
        spin.pack(side="left", padx=(4, 10))
        spin.bind("<FocusOut>", lambda e: self._clamp())
        self.value_var.trace_add("write", self._on_value_written)
        if on_copy_all:
            ttk.Button(
                row, text="Copy to all languages", command=lambda: self._on_copy_all(self)
            ).pack(side="left", padx=(4, 0))

        self.split_var = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self.split_var, style=NOTE_STYLE).pack(
            anchor="w", padx=(24, 0), pady=(0, 2)
        )
        self._update_split_preview()

    def _clamp(self) -> None:
        try:
            v = int(self.value_var.get())
        except ValueError:
            v = 0
        v = max(c.ABILITY_JP_COST_MIN, min(c.ABILITY_JP_COST_MAX, v))
        if str(v) != self.value_var.get():
            self._suppress = True
            self.value_var.set(str(v))
            self._suppress = False

    def _on_value_written(self, *_args) -> None:
        self._update_split_preview()
        if self._suppress:
            return
        self.include_var.set(True)
        self._fire_edit()

    def _update_split_preview(self) -> None:
        try:
            v = int(self.value_var.get())
        except ValueError:
            v = 0
        cost1, cost2 = nxd_data.split_jp_cost(v)
        self.split_var.set(f"\u2192 JpCost1 (low byte): {cost1}, JpCost2 (high byte): {cost2}")

    def _fire_edit(self) -> None:
        if self._on_user_edit:
            self._on_user_edit()

    def load(self, value, included: bool) -> None:
        self._suppress = True
        try:
            v = max(c.ABILITY_JP_COST_MIN, min(c.ABILITY_JP_COST_MAX, int(value)))
        except (ValueError, TypeError):
            v = 0
        self.value_var.set(str(v))
        self._suppress = False
        self.include_var.set(included)
        self._update_split_preview()

    def get_value(self) -> int:
        try:
            v = int(self.value_var.get())
        except ValueError:
            v = 0
        return max(c.ABILITY_JP_COST_MIN, min(c.ABILITY_JP_COST_MAX, v))

    def copy_fields(self) -> dict:
        cost1, cost2 = nxd_data.split_jp_cost(self.get_value())
        return {"JpCost1": cost1, "JpCost2": cost2}

    @property
    def included(self) -> bool:
        return self.include_var.get()


class BattleVoiceIdsRow:
    """[include] "Battle Voice IDs" [entry, comma-separated ids] [Copy to all languages]."""

    def __init__(self, parent, on_user_edit, on_copy_all=None):
        self.field_name = "BattleVoiceIds"
        self._on_user_edit = on_user_edit
        self._on_copy_all = on_copy_all
        self._suppress = False

        self.include_var = tk.BooleanVar(value=False)
        self.value_var = tk.StringVar(value="")

        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Checkbutton(row, variable=self.include_var, command=self._fire_edit).pack(side="left")
        ttk.Label(row, text="Battle Voice IDs", width=24, anchor="w").pack(side="left")
        ttk.Entry(row, textvariable=self.value_var, width=22).pack(side="left", padx=(4, 10))
        self.value_var.trace_add("write", self._on_value_written)
        if on_copy_all:
            ttk.Button(
                row, text="Copy to all languages", command=lambda: self._on_copy_all(self)
            ).pack(side="left", padx=(4, 0))
        ttk.Label(parent, text="Comma-separated ids, e.g. 9, 10", style=NOTE_STYLE).pack(
            anchor="w", padx=(24, 0), pady=(0, 2)
        )

    def _on_value_written(self, *_args) -> None:
        if self._suppress:
            return
        self.include_var.set(True)
        self._fire_edit()

    def _fire_edit(self) -> None:
        if self._on_user_edit:
            self._on_user_edit()

    def load(self, value, included: bool) -> None:
        self._suppress = True
        ids = value if isinstance(value, list) else []
        self.value_var.set(", ".join(str(int(i)) for i in ids))
        self._suppress = False
        self.include_var.set(included)

    def get_value(self) -> list:
        text = self.value_var.get()
        ids = []
        for token in text.replace(";", ",").split(","):
            token = token.strip()
            if not token:
                continue
            try:
                ids.append(int(token))
            except ValueError:
                continue
        return ids

    def copy_fields(self) -> dict:
        return {self.field_name: self.get_value()}

    @property
    def included(self) -> bool:
        return self.include_var.get()


# =============================================================================
# Flags / Element / Overrides (shared, OverrideAbilityActionData) widgets
# =============================================================================

def _baseline_note(raw_value) -> str:
    if raw_value is None or raw_value == c.OVERRIDE_NOT_SET:
        return "Vanilla: not overridden (inherits hardcoded behavior)."
    return f"Vanilla: already overridden in the base data (value {int(raw_value)})."


class AbilityFlagGroupPanel:
    """
    One Flagset (I-IV) - a single override byte with its own include/inherit
    checkbox. Two groups share one physical Flags12/Flags34 column, but each
    is tracked and written independently - see nxd_data.write_override_
    action_edits' "FlagsGroup0".."FlagsGroup3" convention, which does a
    targeted read-modify-write so editing one group never clobbers its
    sibling. Checkboxes show the friendly/effective state, not the raw bit -
    flags marked \u2020 are stored as the opposite bit underneath (checking the
    box clears it), exactly like FFTPatcher and Zodi's flag_codex.html.
    """

    def __init__(self, parent, group_index: int, on_user_edit):
        self.group_index = group_index
        self._on_user_edit = on_user_edit
        self._suppress = False
        self._items = [f for f in c.ABILITY_FLAG_DEFS if f[2] == group_index]

        self.frame = ttk.LabelFrame(parent, text=c.ABILITY_FLAG_GROUP_LABELS[group_index], padding=8)

        header = ttk.Frame(self.frame)
        header.pack(fill="x", pady=(0, 4))
        self.include_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(header, variable=self.include_var, command=self._fire_edit).pack(side="left")
        ttk.Button(header, text="All", width=4, command=self._select_all).pack(side="left", padx=(4, 0))
        ttk.Button(header, text="None", width=5, command=self._select_none).pack(side="left", padx=(4, 0))

        self.check_vars: dict = {}
        for flag_id, label, _group, inverted, blank in self._items:
            if blank:
                ttk.Label(
                    self.frame, text="(unused)", foreground="#aaaaaa", font=("Segoe UI", 9, "italic")
                ).pack(anchor="w")
                continue
            var = tk.BooleanVar(value=False)
            self.check_vars[flag_id] = var
            text = label + (" \u2020" if inverted else "")
            ttk.Checkbutton(self.frame, text=text, variable=var, command=self._fire_checkbox_edit).pack(anchor="w")

        self.baseline_var = tk.StringVar(value="")
        ttk.Label(
            self.frame, textvariable=self.baseline_var, foreground="#888888",
            font=("Segoe UI", 8), wraplength=170, justify="left",
        ).pack(anchor="w", pady=(4, 0))

    def _fire_checkbox_edit(self) -> None:
        if self._suppress:
            return
        self.include_var.set(True)
        self._fire_edit()

    def _fire_edit(self) -> None:
        if self._on_user_edit:
            self._on_user_edit()

    def _select_all(self) -> None:
        self._suppress = True
        for var in self.check_vars.values():
            var.set(True)
        self._suppress = False
        self.include_var.set(True)
        self._fire_edit()

    def _select_none(self) -> None:
        self._suppress = True
        for var in self.check_vars.values():
            var.set(False)
        self._suppress = False
        self.include_var.set(True)
        self._fire_edit()

    def load(self, raw_value, included: bool) -> None:
        self._suppress = True
        if raw_value in (None, c.OVERRIDE_NOT_SET):
            # Not set means "inherit hardcoded/vanilla behavior for this
            # group entirely" - there's no real byte to decode, so show a
            # neutral all-unchecked state. Unpacking a fabricated byte 0
            # here would be actively misleading: "unchecked" for an
            # inverted flag means its bit is SET (e.g. all-unchecked packs
            # to byte 209 for Flagset II, not 0 - see pack_flag_group), so
            # decoding byte 0 shows every inverted flag as checked even
            # though nothing is actually overridden.
            for var in self.check_vars.values():
                var.set(False)
        else:
            states = nxd_data.unpack_flag_group(self.group_index, int(raw_value))
            for flag_id, var in self.check_vars.items():
                var.set(states.get(flag_id, False))
        self._suppress = False
        self.include_var.set(included)
        self.baseline_var.set(_baseline_note(raw_value))

    def get_value(self) -> int:
        states = {flag_id: var.get() for flag_id, var in self.check_vars.items()}
        return nxd_data.pack_flag_group(self.group_index, states)

    @property
    def included(self) -> bool:
        return self.include_var.get()


class ElementFlagPanel:
    """[include] "Override this ability's element" [All][None], then 8 element checkboxes - the Element column."""

    def __init__(self, parent, on_user_edit):
        self._on_user_edit = on_user_edit
        self._suppress = False

        box = ttk.LabelFrame(parent, text="Element", padding=10)
        box.pack(fill="x", pady=(0, 10))

        header = ttk.Frame(box)
        header.pack(fill="x", pady=(0, 4))
        self.include_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(header, variable=self.include_var, command=self._fire_edit).pack(side="left")
        ttk.Label(header, text="Override this ability's element").pack(side="left", padx=(2, 12))
        ttk.Button(header, text="All", width=4, command=self._select_all).pack(side="left")
        ttk.Button(header, text="None", width=5, command=self._select_none).pack(side="left", padx=(4, 0))

        row = ttk.Frame(box)
        row.pack(fill="x")
        self.check_vars: dict = {}
        for name, _value in c.ABILITY_ELEMENT_VALUES:
            var = tk.BooleanVar(value=False)
            self.check_vars[name] = var
            ttk.Checkbutton(row, text=name, variable=var, command=self._fire_checkbox_edit).pack(
                side="left", padx=(0, 10)
            )

        self.baseline_var = tk.StringVar(value="")
        ttk.Label(box, textvariable=self.baseline_var, foreground="#888888").pack(anchor="w", pady=(4, 0))

    def _fire_checkbox_edit(self) -> None:
        if self._suppress:
            return
        self.include_var.set(True)
        self._fire_edit()

    def _fire_edit(self) -> None:
        if self._on_user_edit:
            self._on_user_edit()

    def _select_all(self) -> None:
        self._suppress = True
        for var in self.check_vars.values():
            var.set(True)
        self._suppress = False
        self.include_var.set(True)
        self._fire_edit()

    def _select_none(self) -> None:
        self._suppress = True
        for var in self.check_vars.values():
            var.set(False)
        self._suppress = False
        self.include_var.set(True)
        self._fire_edit()

    def load(self, raw_value, included: bool) -> None:
        self._suppress = True
        baseline_byte = 0 if raw_value in (None, c.OVERRIDE_NOT_SET) else int(raw_value)
        states = nxd_data.unpack_element_value(baseline_byte)
        for name, var in self.check_vars.items():
            var.set(states.get(name, False))
        self._suppress = False
        self.include_var.set(included)
        self.baseline_var.set(_baseline_note(raw_value))

    def get_value(self) -> int:
        states = {name: var.get() for name, var in self.check_vars.items()}
        return nxd_data.pack_element_value(states)

    @property
    def included(self) -> bool:
        return self.include_var.get()


class OverrideScalarFieldRow:
    """[include] label [spinbox 0-255] baseline note - Range/EffectArea/Vertical/Formula/X/Y/InflictStatus/CT/MPCost."""

    def __init__(self, parent, field_name: str, on_user_edit):
        self.field_name = field_name
        self.min_v, self.max_v, self.label, self.help_text = c.OVERRIDE_SCALAR_FIELDS[field_name]
        self._on_user_edit = on_user_edit
        self._suppress = False

        self.include_var = tk.BooleanVar(value=False)
        self.value_var = tk.StringVar(value=str(self.min_v))

        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Checkbutton(row, variable=self.include_var, command=self._fire_edit).pack(side="left")
        ttk.Label(row, text=self.label, width=20, anchor="w").pack(side="left")
        vcmd = row.register(lambda p: p == "" or p.isdigit())
        spin = ttk.Spinbox(
            row, from_=self.min_v, to=self.max_v, textvariable=self.value_var,
            width=8, validate="key", validatecommand=(vcmd, "%P"),
        )
        spin.pack(side="left", padx=(4, 10))
        spin.bind("<FocusOut>", lambda e: self._clamp())
        self.value_var.trace_add("write", self._on_value_written)
        self.baseline_var = tk.StringVar(value="")
        ttk.Label(row, textvariable=self.baseline_var, foreground="#888888").pack(side="left", padx=(4, 0))
        if self.help_text:
            ttk.Label(parent, text=self.help_text, style=NOTE_STYLE, wraplength=600).pack(
                anchor="w", padx=(24, 0)
            )

    def _clamp(self) -> None:
        try:
            v = int(self.value_var.get())
        except ValueError:
            v = self.min_v
        v = max(self.min_v, min(self.max_v, v))
        if str(v) != self.value_var.get():
            self._suppress = True
            self.value_var.set(str(v))
            self._suppress = False

    def _on_value_written(self, *_args) -> None:
        if self._suppress:
            return
        self.include_var.set(True)
        self._fire_edit()

    def _fire_edit(self) -> None:
        if self._on_user_edit:
            self._on_user_edit()

    def load(self, raw_value, included: bool) -> None:
        self._suppress = True
        v = 0 if raw_value in (None, c.OVERRIDE_NOT_SET) else max(self.min_v, min(self.max_v, int(raw_value)))
        self.value_var.set(str(v))
        self._suppress = False
        self.include_var.set(included)
        self.baseline_var.set(_baseline_note(raw_value))

    def get_value(self) -> int:
        try:
            v = int(self.value_var.get())
        except ValueError:
            v = self.min_v
        return max(self.min_v, min(self.max_v, v))

    @property
    def included(self) -> bool:
        return self.include_var.get()


# =============================================================================
# Main panel
# =============================================================================

class AbilitiesPanel(ttk.Frame):
    """The 'Abilities' tab within the combined Edit Game Data step."""

    def __init__(self, parent, app, on_go_to_textures=None):
        super().__init__(parent)
        self.app = app
        self._on_go_to_textures = on_go_to_textures
        self.current_language = c.NXD_DEFAULT_LANGUAGE
        self.current_key: int | None = None
        self.info_fields: dict = {}
        self.override_scalar_fields: dict = {}
        self.flag_groups: list = []
        self.effect_field: XmlNumberRow | None = None
        self.animation_fields: dict = {}
        self.base_stat_fields: dict = {}
        self._loading = False
        self._applied_sqlite_path = None

        self._label_to_lang = {c.NXD_LANGUAGE_LABELS[lang]: lang for lang in c.NXD_LANGUAGES}
        self._lang_to_label = {lang: label for label, lang in self._label_to_lang.items()}

        self._build_layout()

    # -- layout ---------------------------------------------------------

    def _build_layout(self) -> None:
        ttk.Label(
            self, style="SubHeader.TLabel", wraplength=760, justify="left",
            text=(
                "Abilities live in .nxd files, not the mod loader's own XML tables, so the converted "
                "database from General Setup is needed before this tab has anything to "
                "edit. Pick a language, then an ability, then edit its per-language text/JP Cost/etc. "
                "on one tab and its Flags/Element/other overrides - shared across every language - on "
                "the other."
            ),
        ).pack(anchor="w", pady=(4, 8))

        self.no_data_var = tk.StringVar(value="")
        self.no_data_label = ttk.Label(
            self, textvariable=self.no_data_var, foreground="#b06000", wraplength=760, justify="left"
        )
        self.no_data_label.pack(anchor="w", pady=(0, 8))

        lang_row = ttk.Frame(self)
        lang_row.pack(fill="x", pady=(0, 8))
        ttk.Label(lang_row, text="Language:", width=12, anchor="w").pack(side="left")
        self.language_var = tk.StringVar(value=self._lang_to_label[self.current_language])
        self.language_combo = ttk.Combobox(
            lang_row, textvariable=self.language_var,
            values=[c.NXD_LANGUAGE_LABELS[lang] for lang in c.NXD_LANGUAGES],
            state="readonly", width=24,
        )
        self.language_combo.pack(side="left")
        self.language_combo.bind("<<ComboboxSelected>>", self._on_language_changed)

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)

        left = ttk.Frame(body, width=260)
        left.pack(side="left", fill="y", padx=(0, 12))
        left.pack_propagate(False)

        self.changes_var = tk.StringVar(value="")
        ttk.Label(left, textvariable=self.changes_var, foreground="#0a6e0a", wraplength=240, justify="left").pack(
            anchor="w", pady=(0, 6)
        )

        self.search_var = tk.StringVar()
        ttk.Entry(left, textvariable=self.search_var).pack(fill="x", pady=(0, 6))
        self.search_var.trace_add("write", lambda *_a: self._refresh_ability_list())
        ttk.Label(left, text="Search by name or ID", foreground="#888888").pack(anchor="w")

        tree_frame = ttk.Frame(left)
        tree_frame.pack(fill="both", expand=True, pady=(6, 0))
        self.ability_tree = ttk.Treeview(tree_frame, show="tree", selectmode="browse")
        tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.ability_tree.yview)
        self.ability_tree.configure(yscrollcommand=tree_scroll.set)
        self.ability_tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")
        self.ability_tree.tag_configure("edited", background=c.EDITED_ROW_BG, foreground=c.EDITED_ROW_FG)
        self.ability_tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True)

        self.current_ability_var = tk.StringVar(value="No ability selected")
        ttk.Label(right, textvariable=self.current_ability_var, font=("Segoe UI", 12, "bold")).pack(
            anchor="w", pady=(0, 8)
        )

        self.notebook = ttk.Notebook(right)
        self.notebook.pack(fill="both", expand=True)

        self._build_info_tab()
        self._build_override_tab()
        # Unit Animations before Effect: Zodi's call, and it matches how the
        # two read - animations are the visible half, effects the numeric one.
        self._build_animation_tab()
        self._build_effect_tab()
        self._build_base_stats_tab()

    def _add_scrollable_tab(self, title: str) -> ttk.Frame:
        scroll = ScrollableFrame(self.notebook)
        self.notebook.add(scroll, text=title)
        return scroll.inner

    def _build_info_tab(self) -> None:
        tab = self._add_scrollable_tab("Ability Info (this language)")
        self._info_tab_widget = self.notebook.tabs()[-1]

        self.info_hint_var = tk.StringVar()
        ttk.Label(
            tab, textvariable=self.info_hint_var, wraplength=700, justify="left", foreground="#777777",
        ).pack(anchor="w", pady=(0, 4))
        self._refresh_info_hint()

        self.info_status_var = tk.StringVar(value="")
        ttk.Label(tab, textvariable=self.info_status_var, foreground="#0a6e0a").pack(anchor="w", pady=(0, 8))

        self.info_fields["Name"] = AbilityTextRow(tab, "Name", "Name", self._on_info_field_edited)
        self.info_fields["Description"] = AbilityTextRow(
            tab, "Description", "Description", self._on_info_field_edited, multiline=True
        )

        copy_all_row = ttk.Frame(tab)
        copy_all_row.pack(fill="x", pady=(4, 10))
        ttk.Separator(copy_all_row, orient="horizontal").pack(fill="x", pady=(0, 8))
        ttk.Button(
            copy_all_row, text="Copy all fields to other languages",
            command=self._on_copy_all_fields_clicked,
        ).pack(side="left")
        ttk.Label(
            copy_all_row, style=NOTE_STYLE, wraplength=500, justify="left",
            text=(
                "Copies every non-text field below to every other language at once. Text fields "
                "above (Name/Description) are never copied - translate those yourself. You can "
                "still adjust any field per language afterward."
            ),
        ).pack(side="left", padx=(10, 0))

        self.jpcost_field = JpCostRow(tab, self._on_info_field_edited)
        self.info_fields["IconId"] = AbilityNumberRow(
            tab, "IconId", c.ABILITY_NUMERIC_FIELDS["IconId"], self._on_info_field_edited,
        )
        icon_preview_box = ttk.Frame(tab)
        icon_preview_box.pack(fill="x", pady=(0, 8))
        ttk.Label(
            icon_preview_box, style=NOTE_STYLE, wraplength=650, justify="left",
            text=(
                "This icon is shared across the game's icon sheet - replacing it affects every "
                "ability (or anything else) that references this same Icon ID, not just this one."
            ),
        ).pack(anchor="w", pady=(0, 4))
        self.icon_texture_slot = InlineTextureSlot(
            icon_preview_box, self.app, "Ability Icon", on_view_in_textures=self._go_to_textures_clicked,
        )
        self.icon_texture_slot.pack(fill="x")
        self.info_fields["IsRandomDamage"] = AbilityBoolRow(
            tab, "IsRandomDamage", c.ABILITY_NUMERIC_FIELDS["IsRandomDamage"][2],
            c.ABILITY_NUMERIC_FIELDS["IsRandomDamage"][3], self._on_info_field_edited,
        )
        self.info_fields["IsRandomStatus"] = AbilityBoolRow(
            tab, "IsRandomStatus", c.ABILITY_NUMERIC_FIELDS["IsRandomStatus"][2],
            c.ABILITY_NUMERIC_FIELDS["IsRandomStatus"][3], self._on_info_field_edited,
        )
        self.info_fields["DLCFlags"] = AbilityNumberRow(
            tab, "DLCFlags", c.ABILITY_NUMERIC_FIELDS["DLCFlags"], self._on_info_field_edited,
        )
        self.info_fields["UiId"] = AbilityNumberRow(
            tab, "UiId", c.ABILITY_NUMERIC_FIELDS["UiId"], self._on_info_field_edited,
        )
        self.info_fields["UiId2"] = AbilityNumberRow(
            tab, "UiId2", c.ABILITY_NUMERIC_FIELDS["UiId2"], self._on_info_field_edited,
        )
        self.info_fields["AbilityReactionVoiceTypeId"] = AbilityNumberRow(
            tab, "AbilityReactionVoiceTypeId", c.ABILITY_NUMERIC_FIELDS["AbilityReactionVoiceTypeId"],
            self._on_info_field_edited,
        )
        self.info_fields["BattleVoiceIds"] = BattleVoiceIdsRow(tab, self._on_info_field_edited)
        self.info_fields["Comment"] = AbilityTextRow(
            tab, "Comment", "Comment (FF16Tools' own note, not real game data)", self._on_info_field_edited
        )

    def _refresh_info_hint(self) -> None:
        label = c.NXD_LANGUAGE_LABELS[self.current_language]
        self.info_hint_var.set(
            f"Editing {label} text - stored in its own Ability-{self.current_language} table. Use "
            "the \u201cCopy all fields to other languages\u201d button below to copy every non-text "
            "field at once instead of repeating each one by hand."
        )
        self.notebook.tab(self._info_tab_widget, text=f"Ability Info ({label})")

    def _build_override_tab(self) -> None:
        tab = self._add_scrollable_tab("Flags / Element / Overrides")
        ttk.Label(
            tab, wraplength=700, justify="left", foreground="#777777",
            text=(
                "Everything below lives in OverrideAbilityActionData, not the per-language table - "
                "edits apply no matter which language a player has selected. Flags marked \u2020 are "
                "stored as the opposite bit (checking the box clears the underlying flag), same as "
                "FFTPatcher and Zodi's flag_codex.html. Each flag byte/field has its own include "
                "checkbox - leave it unchecked to inherit this ability's normal vanilla/hardcoded "
                "behavior."
            ),
        ).pack(anchor="w", pady=(0, 10))

        flags_grid = ttk.Frame(tab)
        flags_grid.pack(fill="x", pady=(0, 10))
        for i in range(4):
            panel = AbilityFlagGroupPanel(flags_grid, i, self._on_override_field_edited)
            panel.frame.grid(row=i // 2, column=i % 2, padx=6, pady=6, sticky="nw")
            self.flag_groups.append(panel)

        self.element_panel = ElementFlagPanel(tab, self._on_override_field_edited)

        scalar_box = ttk.LabelFrame(tab, text="Other Overrides", padding=10)
        scalar_box.pack(fill="x", pady=(0, 10))
        for name in c.OVERRIDE_SCALAR_FIELD_ORDER:
            self.override_scalar_fields[name] = OverrideScalarFieldRow(
                scalar_box, name, self._on_override_field_edited
            )

    def _build_effect_tab(self) -> None:
        tab = self._add_scrollable_tab("Effect")
        ttk.Label(
            tab, wraplength=700, justify="left", foreground="#777777",
            text=(
                "Determines which hardcoded effect (see https://ffhacktics.com/wiki/Effects) this "
                "ability triggers when it executes. This is an ordinary reference/diff XML table "
                "(AbilityEffectNumberFilterData.xml) - not OverrideAbilityActionData above - same "
                "include/inherit-checkbox convention as JobData.xml, no game unpack needed for this "
                "field specifically. -1 is a real, commonly-used value here (64 vanilla abilities "
                "use it, including all four \u201cRend\u201d/Break skills) - not an error case."
            ),
        ).pack(anchor="w", pady=(0, 10))
        self.effect_field = XmlNumberRow(
            tab, "EffectId", c.ABILITY_EFFECT_ID_MIN, c.ABILITY_EFFECT_ID_MAX, "Effect ID", "",
            self._on_effect_field_edited, allow_negative=True,
            name_lookup=reference_names.effect_names(),
        )

    def _build_animation_tab(self) -> None:
        tab = self._add_scrollable_tab("Unit Animations")
        ttk.Label(
            tab, wraplength=700, justify="left", foreground="#777777",
            text=(
                "Determines which animation(s) play when this ability executes (see "
                "https://ffhacktics.com/wiki/Animations_(Tab)). Another ordinary reference/diff XML "
                "table (AbilityTypeData.xml) - not OverrideAbilityActionData above - same include/"
                "inherit-checkbox convention as JobData.xml, no game unpack needed for these fields "
                "specifically."
            ),
        ).pack(anchor="w", pady=(0, 10))
        self.animation_fields["ChargeEffectType"] = XmlNumberRow(
            tab, "ChargeEffectType", 0, 255, "Charge Effect Type", "", self._on_animation_field_edited,
            name_lookup=reference_names.charge_effect_names(),
        )
        self.animation_fields["AnimationId"] = XmlNumberRow(
            tab, "AnimationId", 0, 255, "Animation ID", "", self._on_animation_field_edited,
            name_lookup=reference_names.animation_names(),
        )
        self.animation_fields["BattleTextId"] = XmlNumberRow(
            tab, "BattleTextId", 0, 255, "Battle Text ID", "", self._on_animation_field_edited,
        )

    def _build_base_stats_tab(self) -> None:
        tab = self._add_scrollable_tab("Base Stats")
        ttk.Label(
            tab, wraplength=700, justify="left", foreground="#777777",
            text=(
                "AbilityData.xml itself - a third ordinary reference/diff XML table (not "
                "OverrideAbilityActionData above), same include/inherit-checkbox convention as "
                "JobData.xml, no game unpack needed for these fields specifically. JP Cost isn't "
                "shown here - the shipped file's own header says that copy is unused; the JP Cost "
                "that actually matters is the one on the Ability Info tab above."
            ),
        ).pack(anchor="w", pady=(0, 10))
        chance_bounds = c.ABILITY_XML_NUMERIC_FIELDS["ChanceToLearn"]
        self.base_stat_fields["ChanceToLearn"] = XmlNumberRow(
            tab, "ChanceToLearn", *chance_bounds, self._on_base_stat_field_edited,
        )
        self.base_stat_fields["Flags"] = ItemFlagFieldPanel(
            tab, "Flags", "Flags", {"Flags": c.ABILITY_XML_FLAGS}, self._on_base_stat_field_edited, columns=1,
        )
        self.base_stat_fields["AbilityType"] = XmlDropdownRow(
            tab, "AbilityType", c.ABILITY_TYPE_XML_VALUES, "Ability Type",
            self._on_base_stat_field_edited, width=14,
        )
        self.base_stat_fields["AIBehaviorFlags"] = ItemFlagFieldPanel(
            tab, "AIBehaviorFlags", "AI Behavior Flags", c.ABILITY_AI_BEHAVIOR_GROUPS,
            self._on_base_stat_field_edited,
        )

    # -- data loading -----------------------------------------------------

    def _ensure_data_loaded(self, language: str) -> bool:
        state = self.app.state_data
        if state.nxd_sqlite_path is None:
            return False
        try:
            if language not in state.ability_records:
                state.ability_records[language] = nxd_data.read_ability_table(state.nxd_sqlite_path, language)
            if not state.override_action_records:
                state.override_action_records = nxd_data.read_override_action_table(state.nxd_sqlite_path)
        except Exception as exc:  # noqa: BLE001 - surface any read failure honestly
            self.no_data_var.set(nxd_missing_data_message(state, "Ability text data", exc))
            return False
        return True

    # -- ability list -------------------------------------------------------

    def _records_from_reference_names(self) -> list:
        """
        Stand-in ability rows built from the mod loader's AbilityData.xml
        names, for when there's no .nxd database.

        They carry a key and a display name and nothing else, which is
        exactly enough to browse and to edit the XML-backed sub-tabs. The
        Info fields stay empty because their real values genuinely aren't
        available, and _on_info_field_edited refuses to record edits against
        them rather than storing changes that couldn't be exported.
        """
        names = self.app.state_data.ability_names or {}
        records = []
        for key in sorted(names):
            record = nxd_data.AbilityRecord(key=key)
            record.values = {"Name": names[key]}
            records.append(record)
        return records

    def _refresh_ability_list(self) -> None:
        query = self.search_var.get().strip().lower()
        self.ability_tree.delete(*self.ability_tree.get_children())
        records = self.app.state_data.ability_records.get(self.current_language, [])
        lang_edits = self.app.state_data.ability_edits.get(self.current_language, {})
        override_edits = self.app.state_data.override_action_edits
        effect_edits = self.app.state_data.item_table_edits.get("ability_effect", {})
        animation_edits = self.app.state_data.item_table_edits.get("ability_animation", {})
        base_stat_edits = self.app.state_data.item_table_edits.get("ability", {})
        for record in records:
            if query and query not in record.display_name.lower() and query != str(record.key):
                continue
            tags = ["edited"] if (
                lang_edits.get(record.key) or override_edits.get(record.key)
                or effect_edits.get(record.key) or animation_edits.get(record.key)
                or base_stat_edits.get(record.key)
            ) else []
            self.ability_tree.insert("", "end", iid=str(record.key), text=record.display_name, tags=tags)
        self._update_changes_label()

    def _update_changes_label(self) -> None:
        state = self.app.state_data
        lang_label = c.NXD_LANGUAGE_LABELS[self.current_language]
        total = len(state.ability_records.get(self.current_language, [])) or 512
        lang_count = state.edited_ability_count(self.current_language)
        override_count = state.edited_override_count()
        effect_count = state.edited_ability_effect_count()
        animation_count = state.edited_ability_animation_count()
        base_stat_count = state.edited_ability_data_count()
        # Lines follow the sub-tab order above (Info, Override, Unit
        # Animations, Effect, Base Stats). They had Effect before Unit
        # Animations, left over from before those two tabs were swapped -
        # a summary that lists things in a different order from the tabs it
        # summarises makes the reader do the mapping every time.
        self.changes_var.set(
            f"{lang_count} of {total} abilities edited in {lang_label}.\n"
            f"{override_count} of {total} abilities have shared Flags/Element/Override edits.\n"
            f"{animation_count} of {total} abilities have Unit Animation edits.\n"
            f"{effect_count} of {total} abilities have Effect edits.\n"
            f"{base_stat_count} of {total} abilities have Base Stat edits."
        )

    def _on_tree_select(self, _event=None) -> None:
        selection = self.ability_tree.selection()
        if selection:
            self._load_ability(int(selection[0]))

    def _on_language_changed(self, _event=None) -> None:
        lang = self._label_to_lang.get(self.language_var.get(), self.current_language)
        if lang == self.current_language:
            return
        self.current_language = lang
        self._refresh_info_hint()
        if self._ensure_data_loaded(lang):
            self.no_data_var.set("")
            self._refresh_ability_list()
            if self.current_key is not None:
                self._load_ability(self.current_key)
            elif self.app.state_data.ability_records.get(lang):
                first_key = self.app.state_data.ability_records[lang][0].key
                if self.ability_tree.exists(str(first_key)):
                    self.ability_tree.selection_set(str(first_key))

    # -- loading / committing -------------------------------------------------

    def _load_ability(self, key: int) -> None:
        self._loading = True
        self.current_key = key
        state = self.app.state_data
        records = state.ability_records.get(self.current_language, [])
        record = next((r for r in records if r.key == key), None)
        override_record = state.override_records_by_key().get(key)

        display = record.display_name if record else f"{key:04d} - (no data for this language)"
        self.current_ability_var.set(f"Editing: {display}")

        baseline = record.values if record else {}
        lang_edits = state.ability_edits.get(self.current_language, {}).get(key, {})

        for name, widget in self.info_fields.items():
            if name in lang_edits:
                widget.load(lang_edits[name], True)
            else:
                widget.load(baseline.get(name), False)

        if "JpCost1" in lang_edits or "JpCost2" in lang_edits:
            cost1 = lang_edits.get("JpCost1", baseline.get("JpCost1", 0)) or 0
            cost2 = lang_edits.get("JpCost2", baseline.get("JpCost2", 0)) or 0
            self.jpcost_field.load(nxd_data.join_jp_cost(cost1, cost2), True)
        else:
            self.jpcost_field.load(record.jp_cost if record else 0, False)

        override_edits = state.override_action_edits.get(key, {})
        for name, widget in self.override_scalar_fields.items():
            if name in override_edits:
                widget.load(override_edits[name], True)
            else:
                baseline_scalar = override_record.scalars.get(name, c.OVERRIDE_NOT_SET) if override_record else c.OVERRIDE_NOT_SET
                widget.load(baseline_scalar, False)

        if "Element" in override_edits:
            self.element_panel.load(override_edits["Element"], True)
        else:
            baseline_element = override_record.scalars.get("Element", c.OVERRIDE_NOT_SET) if override_record else c.OVERRIDE_NOT_SET
            self.element_panel.load(baseline_element, False)

        for i, panel in enumerate(self.flag_groups):
            gname = f"FlagsGroup{i}"
            if gname in override_edits:
                panel.load(override_edits[gname], True)
            else:
                baseline_val = override_record.flag_group_value(i) if override_record else c.OVERRIDE_NOT_SET
                panel.load(baseline_val, False)

        effect_record = state.ability_effect_records_by_id().get(key)
        effect_baseline = effect_record.values if effect_record else {}
        effect_edits = state.item_table_edits.get("ability_effect", {}).get(key, {})
        self.effect_field.load(
            effect_edits.get("EffectId", effect_baseline.get("EffectId", "0")), "EffectId" in effect_edits
        )

        animation_record = state.ability_animation_records_by_id().get(key)
        animation_baseline = animation_record.values if animation_record else {}
        animation_edits = state.item_table_edits.get("ability_animation", {}).get(key, {})
        for name, widget in self.animation_fields.items():
            widget.load(animation_edits.get(name, animation_baseline.get(name, "0")), name in animation_edits)

        base_stat_record = state.ability_data_records_by_id().get(key)
        base_stat_baseline = base_stat_record.values if base_stat_record else {}
        base_stat_edits = state.item_table_edits.get("ability", {}).get(key, {})
        for name, widget in self.base_stat_fields.items():
            default = "0" if name == "ChanceToLearn" else "None"
            widget.load(
                base_stat_edits.get(name, base_stat_baseline.get(name, default)), name in base_stat_edits
            )

        self._loading = False
        self._refresh_icon_preview()

    def _refresh_icon_preview(self) -> None:
        icon_id = self.info_fields["IconId"].get_value()
        new_path = td.ability_icon_texture_path(icon_id)
        if new_path != self.icon_texture_slot.relative_path:
            self.icon_texture_slot.set_relative_path(new_path)

    def _go_to_textures_clicked(self, relative_path: str) -> None:
        if self._on_go_to_textures:
            self._on_go_to_textures(relative_path)

    def _on_info_field_edited(self) -> None:
        if self._loading or self.current_key is None:
            return
        if self.app.state_data.nxd_sqlite_path is None:
            # These fields are written by rebuilding the .nxd from the game
            # database, so without one an edit here could never be exported.
            # Recording it silently would be the worst outcome: it would
            # look saved and then vanish.
            self.no_data_var.set(
                "Names, descriptions and JP Cost need game data - unpack it in General Setup "
                "first, or this change can't be saved into the mod."
            )
            return
        key = self.current_key
        edits = self.app.state_data.ability_edits.setdefault(self.current_language, {}).setdefault(key, {})
        for name, widget in self.info_fields.items():
            if widget.included:
                edits[name] = widget.get_value()
            elif name in edits:
                del edits[name]
        if self.jpcost_field.included:
            cost1, cost2 = nxd_data.split_jp_cost(self.jpcost_field.get_value())
            edits["JpCost1"] = cost1
            edits["JpCost2"] = cost2
        else:
            edits.pop("JpCost1", None)
            edits.pop("JpCost2", None)
        if not edits:
            self.app.state_data.ability_edits[self.current_language].pop(key, None)
        self._refresh_tree_tag(key)
        self._update_changes_label()
        self._refresh_icon_preview()

    def _on_override_field_edited(self) -> None:
        if self._loading or self.current_key is None:
            return
        key = self.current_key
        edits = self.app.state_data.override_action_edits.setdefault(key, {})
        for name, widget in self.override_scalar_fields.items():
            if widget.included:
                edits[name] = widget.get_value()
            elif name in edits:
                del edits[name]
        if self.element_panel.included:
            edits["Element"] = self.element_panel.get_value()
        elif "Element" in edits:
            del edits["Element"]
        for i, panel in enumerate(self.flag_groups):
            gname = f"FlagsGroup{i}"
            if panel.included:
                edits[gname] = panel.get_value()
            elif gname in edits:
                del edits[gname]
        if not edits:
            self.app.state_data.override_action_edits.pop(key, None)
        self._refresh_tree_tag(key)
        self._update_changes_label()

    def _on_effect_field_edited(self) -> None:
        if self._loading or self.current_key is None:
            return
        key = self.current_key
        state = self.app.state_data
        edits = state.item_table_edits.setdefault("ability_effect", {}).setdefault(key, {})
        if self.effect_field.included:
            edits["EffectId"] = self.effect_field.get_value_str()
        else:
            edits.pop("EffectId", None)
        if not edits:
            state.item_table_edits["ability_effect"].pop(key, None)
        self._refresh_tree_tag(key)
        self._update_changes_label()

    def _on_animation_field_edited(self) -> None:
        if self._loading or self.current_key is None:
            return
        key = self.current_key
        state = self.app.state_data
        edits = state.item_table_edits.setdefault("ability_animation", {}).setdefault(key, {})
        for name, widget in self.animation_fields.items():
            if widget.included:
                edits[name] = widget.get_value_str()
            elif name in edits:
                del edits[name]
        if not edits:
            state.item_table_edits["ability_animation"].pop(key, None)
        self._refresh_tree_tag(key)
        self._update_changes_label()

    def _on_base_stat_field_edited(self) -> None:
        if self._loading or self.current_key is None:
            return
        key = self.current_key
        state = self.app.state_data
        edits = state.item_table_edits.setdefault("ability", {}).setdefault(key, {})
        for name, widget in self.base_stat_fields.items():
            if widget.included:
                edits[name] = widget.get_value_str()
            elif name in edits:
                del edits[name]
        if not edits:
            state.item_table_edits["ability"].pop(key, None)
        self._refresh_tree_tag(key)
        self._update_changes_label()

    def _refresh_tree_tag(self, key: int) -> None:
        state = self.app.state_data
        lang_edits = state.ability_edits.get(self.current_language, {})
        tags = ["edited"] if (
            lang_edits.get(key) or state.override_action_edits.get(key)
            or state.item_table_edits.get("ability_effect", {}).get(key)
            or state.item_table_edits.get("ability_animation", {}).get(key)
            or state.item_table_edits.get("ability", {}).get(key)
        ) else []
        if self.ability_tree.exists(str(key)):
            self.ability_tree.item(str(key), tags=tags)

    # -- copy to all languages -------------------------------------------------

    def _on_copy_all_fields_clicked(self) -> None:
        if self.current_key is None:
            return
        widgets = [self.jpcost_field] + [w for w in self.info_fields.values() if hasattr(w, "copy_fields")]
        if not widgets:
            return
        for widget in widgets:
            widget.include_var.set(True)
        self._on_info_field_edited()  # also commit/include everything for the language currently being viewed

        key = self.current_key
        state = self.app.state_data
        other_langs = [lang for lang in c.NXD_LANGUAGES if lang != self.current_language]
        for lang in other_langs:
            lang_edits = state.ability_edits.setdefault(lang, {}).setdefault(key, {})
            for widget in widgets:
                lang_edits.update(widget.copy_fields())

        self.info_status_var.set(
            f"Copied {len(widgets)} field(s) to all {len(other_langs)} other languages "
            f"({', '.join(c.NXD_LANGUAGE_LABELS[l] for l in other_langs)})."
        )
        self._update_changes_label()

    # -- called by the combined step's on_show() -----------------------------

    def on_show(self) -> None:
        state = self.app.state_data
        if state.nxd_sqlite_path is None:
            # Only the Info sub-tab (name/description/JP cost) comes from
            # the .nxd database. Effect, Unit Animations and Base Stats all
            # come from the mod loader's XML tables, which need no game
            # files at all - so blanking the whole tab hid work the user
            # could perfectly well be doing, and hid which abilities an
            # opened mod had already changed.
            self._applied_sqlite_path = None
            state.ability_records = {}
            state.ability_records[self.current_language] = self._records_from_reference_names()
            if not state.ability_records[self.current_language]:
                self.no_data_var.set(
                    "No ability data yet - the reference tables are still loading. Give General "
                    "Setup a moment."
                )
                self.ability_tree.delete(*self.ability_tree.get_children())
                self.changes_var.set("")
                return

            self.no_data_var.set(
                "Showing abilities from the reference tables. Unit Animations, Effect and Base "
                "Stats are fully editable; names, descriptions and JP Cost need game data - "
                "unpack it in General Setup to edit those."
            )
            self._refresh_ability_list()
            if self.current_key is None:
                records = state.ability_records[self.current_language]
                if records and self.ability_tree.exists(str(records[0].key)):
                    self.ability_tree.selection_set(str(records[0].key))
            self._update_changes_label()
            return

        if state.nxd_sqlite_path != self._applied_sqlite_path:
            # A different (or first) database was loaded - drop cached
            # baseline records from any previous one so nothing stale
            # lingers (edits already made are left alone, same as a Job
            # Data table refresh doesn't clear existing job edits).
            self._applied_sqlite_path = state.nxd_sqlite_path
            state.ability_records = {}
            state.override_action_records = []
            self.current_key = None

        if not self._ensure_data_loaded(self.current_language):
            return
        self.no_data_var.set("")
        self._refresh_ability_list()
        if self.current_key is None and self.app.state_data.ability_records.get(self.current_language):
            first_key = self.app.state_data.ability_records[self.current_language][0].key
            if self.ability_tree.exists(str(first_key)):
                self.ability_tree.selection_set(str(first_key))
