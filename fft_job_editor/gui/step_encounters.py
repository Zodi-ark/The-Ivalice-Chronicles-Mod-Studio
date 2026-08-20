"""
The "Encounters" tab within the combined Edit Game Data step.

Two genuinely different things share this tab:
  - "Encounters" - OverrideEntryData, a single shared nxd table (no per-
    language split) keyed by (Key, Key2) - Key is the encounter/ENTD id,
    Key2 is the unit slot (0-15) within it. Unlike every other nxd table in
    this tool, there's no dense reference table backing this one (see
    nxd_data.EntryRecord's docstring). Zodi's own notes (data/
    OverrideEntryDataNotes.txt) plus Nenkai's OverrideEntryData.layout
    explain the trickiest fields; anything not covered is exposed plainly
    as an "Unknown" field rather than guessed at, with a per-field
    confidence marker. Shown as the first sub-tab (Zodi's own call - it's
    the primary reason this tab exists; Unit Names is more of a supporting
    table).

    THE ADDRESS IS EDITABLE, AND THAT IS THE POINT. Rows added to this
    table aren't picked up by the game (Zodi's own in-game testing), so
    the way a mod gets a unit slot the game doesn't have is to *move* an
    existing row it doesn't need - which keeps the row count constant,
    because a move vacates one address as it fills another. Her Dark
    Knight Expansion is exactly this: ten rows moved to (95, 0..9), ten
    vanilla addresses vacated, 516 rows before and after. So Key/Key2 are
    edited here like any other field, with a collision check and a live
    row-count line, and the tab lists rows at their *current* addresses
    rather than at vanilla's. Creating a genuinely new address is still
    possible but warns, since that's the thing that didn't work.
  - "Unit Names" - CharaName-xx, a per-language nxd table with the exact
    same simple shape as Item-xx (Name/Comment/DLCFlags/IsGeneric). Reuses
    step_abilities.py's AbilityTextRow/AbilityNumberRow/AbilityBoolRow
    directly, same as step_items.py did. DLC Flags/Generic Unit/Comment get
    a master "Copy all fields to other languages" button (Zodi's own call -
    Name stays excluded, since it's the one field here that's genuinely
    different per language; unlike Abilities/Items/Poaching's own Comment
    fields, which stay non-copyable, this one's Comment is deliberately
    made copyable via AbilityTextRow's copyable=True).

Reference-data dropdowns (Unit Name, Main Job, Primary/Secondary Job
Command, Reaction/Support/Movement, and the five equipment slots) all reuse
data this app already has loaded for other tabs (state.job_records, state.
job_command_records, state.ability_names/ability_types, state.item_table_
records) rather than requiring anything new to be fetched.
"""

from __future__ import annotations

import re
import tkinter as tk
from tkinter import messagebox, ttk

from .. import constants as c
from .. import encounter_names as enc_names
from .. import nxd_data
from .step_abilities import AbilityBoolRow, AbilityNumberRow, AbilityTextRow
from .step_editor import NOTE_STYLE, UNKNOWN_ROW_STYLE, UNKNOWN_SECTION_STYLE, is_unknown_field, ScrollableFrame, nxd_missing_data_message

# Per-field: the value that means "leave the game's own value alone" is
# 0 / 20 / 255 / -1 depending on the column (constants.ENTRY_INHERIT_VALUES).
NOT_SET_TEMPLATE = "({value}) Inherit / Not Set"


class ArrayFieldRow:
    """[include] label [entry, comma-separated ints] - a generic version of step_abilities.BattleVoiceIdsRow, parametrized by field name."""

    def __init__(self, parent, field_name: str, label: str, help_text: str, on_user_edit):
        self.field_name = field_name
        self._on_user_edit = on_user_edit
        self._suppress = False

        self.include_var = tk.BooleanVar(value=False)
        self.value_var = tk.StringVar(value="")

        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Checkbutton(row, variable=self.include_var, command=self._fire_edit).pack(side="left")
        ttk.Label(row, text=label, width=22, anchor="w").pack(side="left")
        ttk.Entry(row, textvariable=self.value_var, width=24).pack(side="left", padx=(4, 10))
        self.value_var.trace_add("write", self._on_value_written)
        ttk.Label(
            parent, text=help_text or "Comma-separated numbers.", style=NOTE_STYLE, wraplength=600
        ).pack(anchor="w", padx=(24, 0), pady=(0, 2))

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

    @property
    def included(self) -> bool:
        return self.include_var.get()


def _confidence_suffix(field_name: str) -> str:
    """
    The per-field confidence marker shown beside a label. Only "inferred"
    and "unknown" are marked - "confirmed" is the norm here and marking it
    everywhere would be noise. See constants.ENTRY_FIELD_CONFIDENCE.
    """
    tier = c.ENTRY_FIELD_CONFIDENCE.get(field_name)
    if tier in (None, "confirmed"):
        return ""
    return f"  [{c.ENTRY_CONFIDENCE_LABELS[tier][0].lower()}]"


def _inherit_note(field_name: str) -> str:
    """The 'leave the game's own value alone' sentence for a field, if it has one."""
    return c.entry_inherit_help(field_name)


class EntryNumberRow:
    """
    [include] label [spinbox] help - a plain numeric OverrideEntryData
    field.

    Deliberately not step_abilities.AbilityNumberRow: that one's keystroke
    validation is `isdigit()`, so a leading "-" can't be typed at all, and
    -1 is the "leave it alone" value for roughly half the columns in this
    table. Also appends the field's own inherit-value note (from
    constants.ENTRY_INHERIT_VALUES) to the help text, so the answer to
    "what do I put here to change nothing?" is always on screen - it is a
    different number per field and there is no way to guess it.
    """

    def __init__(self, parent, field_name: str, bounds: tuple, on_user_edit):
        self.field_name = field_name
        self.min_v, self.max_v, label, help_text = bounds
        self._on_user_edit = on_user_edit
        self._suppress = False

        self.include_var = tk.BooleanVar(value=False)
        self.value_var = tk.StringVar(value=str(self.min_v))

        row = ttk.Frame(parent, style=UNKNOWN_ROW_STYLE if is_unknown_field(field_name, label) else "")
        row.pack(fill="x", pady=2)
        ttk.Checkbutton(row, variable=self.include_var, command=self._fire_edit).pack(side="left")
        ttk.Label(row, text=label + _confidence_suffix(field_name), width=26, anchor="w").pack(side="left")
        vcmd = row.register(lambda p: re.fullmatch(r"-?\d*", p) is not None)
        spin = ttk.Spinbox(
            row, from_=self.min_v, to=self.max_v, textvariable=self.value_var,
            width=10, validate="key", validatecommand=(vcmd, "%P"),
        )
        spin.pack(side="left", padx=(4, 10))
        spin.bind("<FocusOut>", lambda e: self._clamp())
        self.value_var.trace_add("write", self._on_value_written)

        full_help = " ".join(part for part in (_inherit_note(field_name), help_text) if part)
        if full_help:
            ttk.Label(parent, text=full_help, style=NOTE_STYLE, wraplength=560, justify="left").pack(
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

    @property
    def included(self) -> bool:
        return self.include_var.get()


class EntryFlagRow:
    """
    [include] label [checkbox] help - one of OverrideEntryData's 1/0 flag
    columns.

    Kept separate from step_abilities.AbilityBoolRow purely so the
    "meaning unknown" half of these can say so: the layout confirms
    Unknown8F/90/93-97 each set a specific bit of UnknownFlags (so they
    genuinely are booleans, not numbers), while what those bits do is not
    known. Marking that in the widget itself is the honest alternative to
    either hiding them or inventing names for them.
    """

    def __init__(self, parent, field_name: str, label: str, help_text: str, meaning_known: bool, on_user_edit):
        self.field_name = field_name
        self._on_user_edit = on_user_edit
        self._suppress = False

        self.include_var = tk.BooleanVar(value=False)
        self.bool_var = tk.BooleanVar(value=False)

        row = ttk.Frame(parent, style="" if meaning_known else UNKNOWN_ROW_STYLE)
        row.pack(fill="x", pady=2)
        ttk.Checkbutton(row, variable=self.include_var, command=self._fire_edit).pack(side="left")
        ttk.Checkbutton(row, variable=self.bool_var, command=self._on_bool_changed).pack(side="left", padx=(0, 6))
        ttk.Label(
            row, text=label, anchor="w",
            foreground="#000000" if meaning_known else "#666666",
        ).pack(side="left")
        if help_text:
            ttk.Label(parent, text=help_text, style=NOTE_STYLE, wraplength=560, justify="left").pack(
                anchor="w", padx=(46, 0), pady=(0, 2)
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
            v = int(value) != 0
        except (TypeError, ValueError):
            v = False
        self.bool_var.set(v)
        self._suppress = False
        self.include_var.set(included)

    def get_value(self) -> int:
        return 1 if self.bool_var.get() else 0

    @property
    def included(self) -> bool:
        return self.include_var.get()


class SearchableIdRow:
    """
    [include] label [type-to-search combobox] - a generalized version of
    step_job_commands.SearchableAbilityRow: picks an id by name from an
    explicit id->name mapping (Job/Job Command/Ability/Item names, or
    CharaName unit names) rather than being hardwired to abilities.

    Two things this had to learn for OverrideEntryData:

    - The "leave it alone" value is per field, not always -1 (it's 0 for
      Main Job and Unit Name, 20 for Job Unlock). The choice list is built
      around whichever value the layout gives that column, which also means
      that value's own name is *replaced* by the Inherit choice rather than
      offered alongside it - correct, because a field whose inherit value
      is 0 genuinely cannot be used to select id 0.
    - Fields the layout says are cast to a byte can't reach ids above 255,
      which is real: ItemData runs to 260 and JobCommandData to 226. Those
      choices are marked rather than silently offered.
    """

    def __init__(
        self, parent, field_name: str, label: str, id_to_name: dict, on_user_edit,
        on_copy_all=None, inherit_value: int = -1, byte_cast: bool = False,
    ):
        self.field_name = field_name
        self._on_user_edit = on_user_edit
        self._on_copy_all = on_copy_all
        self._suppress = False
        self.inherit_value = inherit_value
        self.byte_cast = byte_cast
        self.not_set_label = NOT_SET_TEMPLATE.format(value=inherit_value)

        self._set_choices(id_to_name)

        self.include_var = tk.BooleanVar(value=False)
        self.text_var = tk.StringVar(value=self.not_set_label)
        self.selected_id = inherit_value

        row = ttk.Frame(parent, style=UNKNOWN_ROW_STYLE if is_unknown_field(field_name, label) else "")
        row.pack(fill="x", pady=2)
        ttk.Checkbutton(row, variable=self.include_var, command=self._fire_edit).pack(side="left")
        ttk.Label(row, text=label + _confidence_suffix(field_name), width=26, anchor="w").pack(side="left")
        self.combo = ttk.Combobox(row, textvariable=self.text_var, values=self._all_names, width=32)
        self.combo.pack(side="left", padx=(4, 10))
        self.combo.bind("<KeyRelease>", self._on_key_release)
        self.combo.bind("<<ComboboxSelected>>", self._on_selected)
        self.combo.bind("<FocusOut>", self._on_focus_out)
        if on_copy_all:
            ttk.Button(
                row, text="Copy to all languages", command=lambda: self._on_copy_all(self)
            ).pack(side="left", padx=(4, 0))
        note = _inherit_note(field_name)
        if byte_cast:
            note = (note + " Applied as a byte, so ids above 255 can't be reached through this table.").strip()
        if note:
            ttk.Label(parent, text=note, style=NOTE_STYLE, wraplength=560, justify="left").pack(
                anchor="w", padx=(24, 0), pady=(0, 2)
            )

    def _set_choices(self, id_to_name: dict) -> None:
        self.id_to_name = {
            id_: (f"{name}  (id {id_} - unreachable, byte cast)" if self.byte_cast and id_ > 255 else name)
            for id_, name in id_to_name.items()
        }
        # Assignment, not setdefault: the inherit value's slot belongs to
        # the Inherit choice even when a real record shares that id.
        self.id_to_name[self.inherit_value] = self.not_set_label
        self.name_to_id = {name: id_ for id_, name in self.id_to_name.items()}
        self._all_names = sorted(self.name_to_id.keys(), key=lambda n: (n != self.not_set_label, n))

    def _on_key_release(self, _event=None) -> None:
        query = self.text_var.get().strip().lower()
        if not query:
            self.combo.configure(values=self._all_names)
            return
        matches = [n for n in self._all_names if query in n.lower()]
        self.combo.configure(values=matches[:200])

    def _on_selected(self, _event=None) -> None:
        name = self.text_var.get()
        if name in self.name_to_id:
            self.selected_id = self.name_to_id[name]
            if not self._suppress:
                self.include_var.set(True)
                self._fire_edit()

    def _on_focus_out(self, _event=None) -> None:
        name = self.text_var.get()
        if name not in self.name_to_id:
            # Typed text that doesn't match anything - revert to the last
            # valid selection rather than silently discarding an edit.
            self.text_var.set(self.id_to_name.get(self.selected_id, self.not_set_label))

    def _fire_edit(self) -> None:
        if self._on_user_edit:
            self._on_user_edit()

    def load(self, value, included: bool) -> None:
        self._suppress = True
        try:
            id_value = int(value)
        except (TypeError, ValueError):
            id_value = self.inherit_value
        self.selected_id = id_value
        self.text_var.set(self.id_to_name.get(id_value, f"({id_value}) - not in the reference list"))
        self.combo.configure(values=self._all_names)
        self._suppress = False
        self.include_var.set(included)

    def get_value(self) -> int:
        return self.selected_id

    def copy_fields(self) -> dict:
        return {self.field_name: self.get_value()}

    def update_choices(self, id_to_name: dict) -> None:
        """Refreshes the id->name mapping in place (e.g. Unit Name's CharaName choices after a language switch) without losing the current selection."""
        self._set_choices(id_to_name)
        self.combo.configure(values=self._all_names)
        self.text_var.set(self.id_to_name.get(self.selected_id, f"({self.selected_id}) - not in the reference list"))

    @property
    def included(self) -> bool:
        return self.include_var.get()


# =============================================================================
# Reference-data -> id_to_name builders (all reuse data this app already
# loads for other tabs - nothing new is fetched for these dropdowns).
# =============================================================================

def _job_id_to_name(state) -> dict:
    return {r.job_id: r.display_name for r in state.job_records}


def _job_command_id_to_name(state) -> dict:
    return {r.command_id: r.display_name for r in state.job_command_records}


def _rsm_ability_id_to_name(state) -> dict:
    result = {}
    for ability_id, name in state.ability_names.items():
        if state.ability_types.get(ability_id) in c.RSM_ABILITY_TYPES:
            result[ability_id] = f"{ability_id:03d} - {name}"
    return result


def _item_id_to_name(state) -> dict:
    return {r.item_id: r.display_name() for r in state.item_table_records.get("item", [])}


def _chara_name_id_to_name(state, language: str) -> dict:
    return {r.key: r.display_name for r in state.chara_name_records.get(language, [])}


# Which reference list backs each dropdown field. One registry rather than
# a chain of `if name in (...)` in two places (build and refresh), which is
# how MainJob and the equipment slots previously drifted into being
# refreshed in on_show but not the other way round.
_DROPDOWN_FIELDS = {
    "Unknown4": lambda state, lang: _chara_name_id_to_name(state, lang),
    "MainJob": lambda state, lang: _job_id_to_name(state),
    "EntryUnknown1D": lambda state, lang: _job_command_id_to_name(state),
    "SecondarySkillset": lambda state, lang: _job_command_id_to_name(state),
    "Reaction": lambda state, lang: _rsm_ability_id_to_name(state),
    "Support": lambda state, lang: _rsm_ability_id_to_name(state),
    "Movement": lambda state, lang: _rsm_ability_id_to_name(state),
    "Head": lambda state, lang: _item_id_to_name(state),
    "Body": lambda state, lang: _item_id_to_name(state),
    "Accessory": lambda state, lang: _item_id_to_name(state),
    "RightHand": lambda state, lang: _item_id_to_name(state),
    "LeftHand": lambda state, lang: _item_id_to_name(state),
}

# A moved row is marked distinctly from an edited one - they're different
# claims ("this row now lives somewhere else" vs "some of its fields
# changed") and a row is very often both.
MOVED_ROW_BG = "#cfe4ff"

# Tracks the panel now that labels fit; see the tree setup in _build_entries_tab.
TREE_COLUMN_WIDTH = 340


# =============================================================================
# Main panel
# =============================================================================

class EncountersPanel(ttk.Frame):
    """The 'Encounters' tab within the combined Edit Game Data step - two sub-tabs, Unit Names and Encounters (see module docstring)."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.current_language = c.NXD_DEFAULT_LANGUAGE
        self.current_chara_key = None
        # The ORIGIN address of the row being edited - where it sits in
        # the working database, which stays put even when the row is
        # moved. See EditorState.entry_rekeys.
        self.current_entry_key = None   # (key, key2) tuple
        self.chara_fields = {}
        self.entry_fields = {}   # flat: field_name -> widget, across every section
        self._loading = False
        self._applied_sqlite_path = None
        # Set by _ensure_nxd_loaded - the two tables are read separately.
        self._chara_available = True
        self._entry_available = True

        self._label_to_lang = {c.NXD_LANGUAGE_LABELS[lang]: lang for lang in c.NXD_LANGUAGES}
        self._lang_to_label = {lang: label for label, lang in self._label_to_lang.items()}

        self._build_layout()

    # -- layout ---------------------------------------------------------

    def _build_layout(self) -> None:
        ttk.Label(
            self, style="SubHeader.TLabel", wraplength=760, justify="left",
            text=(
                "Encounters live in a single shared .nxd table (OverrideEntryData) keyed by "
                "encounter + unit slot, plus per-language unit names (CharaName) - both need a "
                "converted Ability & Item Data database (General Setup), same as Abilities/Items. "
                "There's no full reference list of encounters here - the names shown come from "
                "data/EncounterNames.txt, which you can edit if any look wrong.\n\n"
                "To give an encounter a unit slot it doesn't already have, MOVE a row you don't "
                "need: open it and change its Key/Key2. Rows added to this table aren't picked up "
                "by the game, so moving is the mechanism - and because a move vacates one address "
                "as it fills another, the row count stays put, which is what makes it work."
            ),
        ).pack(anchor="w", pady=(4, 8))

        self.no_data_var = tk.StringVar(value="")
        ttk.Label(
            self, textvariable=self.no_data_var, foreground="#b06000", wraplength=760, justify="left"
        ).pack(anchor="w", pady=(0, 8))

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
        ttk.Label(
            lang_row, text="  (used for Unit Names below, and for the Unit Name dropdown on Encounters)",
            foreground="#888888",
        ).pack(side="left")

        self.outer_notebook = ttk.Notebook(self)
        self.outer_notebook.pack(fill="both", expand=True, pady=(8, 0))

        self._build_encounters_tab()
        self._build_unit_names_tab()

    # -- Unit Names (CharaName-xx) tab -----------------------------------------

    def _build_unit_names_tab(self) -> None:
        tab = ttk.Frame(self.outer_notebook)
        self.outer_notebook.add(tab, text="Unit Names")

        body = ttk.Frame(tab)
        body.pack(fill="both", expand=True, padx=4, pady=4)

        left = ttk.Frame(body, width=260)
        left.pack(side="left", fill="y", padx=(0, 12))
        left.pack_propagate(False)

        self.chara_changes_var = tk.StringVar(value="")
        ttk.Label(left, textvariable=self.chara_changes_var, foreground="#0a6e0a", wraplength=240, justify="left").pack(
            anchor="w", pady=(0, 6)
        )

        self.chara_search_var = tk.StringVar()
        ttk.Entry(left, textvariable=self.chara_search_var).pack(fill="x", pady=(0, 6))
        self.chara_search_var.trace_add("write", lambda *_a: self._refresh_chara_list())
        ttk.Label(left, text="Search by name or ID", foreground="#888888").pack(anchor="w")

        tree_frame = ttk.Frame(left)
        tree_frame.pack(fill="both", expand=True, pady=(6, 0))
        self.chara_tree = ttk.Treeview(tree_frame, show="tree", selectmode="browse")
        tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.chara_tree.yview)
        self.chara_tree.configure(yscrollcommand=tree_scroll.set)
        self.chara_tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")
        self.chara_tree.tag_configure("edited", background=c.EDITED_ROW_BG, foreground=c.EDITED_ROW_FG)
        self.chara_tree.bind("<<TreeviewSelect>>", self._on_chara_tree_select)

        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True)

        self.current_chara_var = tk.StringVar(value="No unit selected")
        ttk.Label(right, textvariable=self.current_chara_var, font=("Segoe UI", 12, "bold")).pack(
            anchor="w", pady=(0, 8)
        )

        self.chara_copy_status_var = tk.StringVar(value="")
        ttk.Label(right, textvariable=self.chara_copy_status_var, foreground="#0a6e0a").pack(
            anchor="w", pady=(0, 4)
        )

        form_scroll = ScrollableFrame(right)
        form_scroll.pack(fill="both", expand=True)
        form = form_scroll.inner

        self.chara_fields["Name"] = AbilityTextRow(form, "Name", "Name", self._on_chara_field_edited)

        copy_all_row = ttk.Frame(form)
        copy_all_row.pack(fill="x", pady=(4, 10))
        ttk.Separator(copy_all_row, orient="horizontal").pack(fill="x", pady=(0, 8))
        ttk.Button(
            copy_all_row, text="Copy all fields to other languages",
            command=self._on_chara_copy_all_fields_clicked,
        ).pack(side="left")
        ttk.Label(
            copy_all_row, style=NOTE_STYLE, wraplength=460, justify="left",
            text=(
                "Copies DLC Flags, Generic Unit, and Comment to every other language at once. "
                "Name above is never copied - it's genuinely different per language. You can "
                "still adjust any field per language afterward."
            ),
        ).pack(side="left", padx=(10, 0))

        self.chara_fields["DLCFlags"] = AbilityNumberRow(
            form, "DLCFlags", c.CHARANAME_NUMERIC_FIELDS["DLCFlags"], self._on_chara_field_edited
        )
        label, help_text = c.CHARANAME_BOOL_FIELDS["IsGeneric"]
        self.chara_fields["IsGeneric"] = AbilityBoolRow(form, "IsGeneric", label, help_text, self._on_chara_field_edited)
        self.chara_fields["Comment"] = AbilityTextRow(
            form, "Comment", "Comment (FF16Tools' own note, not real game data)", self._on_chara_field_edited,
            copyable=True,
        )

    # -- Encounters (OverrideEntryData) tab -------------------------------------

    def _build_encounters_tab(self) -> None:
        tab = ttk.Frame(self.outer_notebook)
        self.outer_notebook.add(tab, text="Encounters")

        body = ttk.Frame(tab)
        body.pack(fill="both", expand=True, padx=4, pady=4)

        # Wider than the other tabs' lists on purpose, for two reasons: a
        # moved row's label carries where it came from ("Unit 0 <- was
        # 128/0"), and an encounter's label carries its name. The longest
        # real name measures ~375px ("387 Chapter 1 - Orbonne Monastery
        # (Opening Battle)"), so 400 fits every one of the 483 shipped
        # names without needing a horizontal scrollbar.
        left = ttk.Frame(body, width=400)
        left.pack(side="left", fill="y", padx=(0, 12))
        left.pack_propagate(False)

        self.entry_changes_var = tk.StringVar(value="")
        ttk.Label(left, textvariable=self.entry_changes_var, foreground="#0a6e0a", wraplength=380, justify="left").pack(
            anchor="w", pady=(0, 4)
        )
        self.entry_rowset_var = tk.StringVar(value="")
        self.entry_rowset_label = ttk.Label(left, textvariable=self.entry_rowset_var, wraplength=380, justify="left")
        self.entry_rowset_label.pack(anchor="w", pady=(0, 6))

        jump_box = ttk.LabelFrame(left, text="Go to a unit slot", padding=8)
        jump_box.pack(fill="x", pady=(0, 8))
        jump_row = ttk.Frame(jump_box)
        jump_row.pack(fill="x")
        ttk.Label(jump_row, text="Key:").pack(side="left")
        self.jump_key_var = tk.StringVar(value="0")
        # A plain Entry, not a Spinbox: this field takes hex too, and a
        # Spinbox's own numeric stepping would fight that.
        ttk.Entry(jump_row, textvariable=self.jump_key_var, width=7).pack(side="left", padx=(2, 8))
        ttk.Label(jump_row, text="Key2:").pack(side="left")
        self.jump_key2_var = tk.StringVar(value="0")
        ttk.Spinbox(jump_row, from_=0, to=c.MAX_ENTRY_KEY2, textvariable=self.jump_key2_var, width=4).pack(
            side="left", padx=(2, 8)
        )
        ttk.Button(jump_box, text="Go", command=self._on_jump_clicked).pack(anchor="w", pady=(6, 0))

        # No "N encounter names loaded from ..." line here. It was a
        # build-time detail nobody editing an encounter needs, and it cost
        # two rows off the top of the list it was describing.

        tree_frame = ttk.Frame(left)
        tree_frame.pack(fill="both", expand=True, pady=(6, 0))
        self.entry_tree = ttk.Treeview(tree_frame, show="tree", selectmode="browse")
        tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.entry_tree.yview)
        # No horizontal scrollbar. There was one while labels read
        # "Encounter 460 (0x1CC) - Chapter 4 - Mullonde Cathedral", which
        # no sensible panel width could hold; dropping the hex and the
        # redundant "Encounter " prefix took roughly 20 characters off
        # every label and they now fit. stretch=True lets the column track
        # the panel so the few long ones wrap the panel rather than needing
        # a bar that is empty the rest of the time.
        self.entry_tree.configure(yscrollcommand=tree_scroll.set)
        self.entry_tree.column("#0", width=TREE_COLUMN_WIDTH, minwidth=200, stretch=True)
        self.entry_tree.grid(row=0, column=0, sticky="nsew")
        tree_scroll.grid(row=0, column=1, sticky="ns")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)
        self.entry_tree.tag_configure("edited", background=c.EDITED_ROW_BG, foreground=c.EDITED_ROW_FG)
        self.entry_tree.tag_configure("moved", background=MOVED_ROW_BG, foreground=c.EDITED_ROW_FG)
        self.entry_tree.bind("<<TreeviewSelect>>", self._on_entry_tree_select)

        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True)

        self.current_entry_var = tk.StringVar(value="No unit slot selected")
        ttk.Label(right, textvariable=self.current_entry_var, font=("Segoe UI", 12, "bold")).pack(
            anchor="w", pady=(0, 8)
        )

        form_scroll = ScrollableFrame(right)
        form_scroll.pack(fill="both", expand=True)
        form = form_scroll.inner

        self._build_address_box(form)

        for section_name, field_names in c.ENTRY_FIELD_SECTIONS.items():
            # A section where every field is unknown hides as a unit, so
            # "Hide unknown fields" doesn't leave an empty titled box behind.
            all_unknown = all(
                is_unknown_field(n, c.ENTRY_FIELD_LABELS.get(n, n)) for n in field_names
            )
            box = ttk.LabelFrame(
                form, text=section_name, padding=10,
                style=UNKNOWN_SECTION_STYLE if all_unknown else "",
            )
            box.pack(fill="x", pady=(0, 10))
            for name in field_names:
                widget = self._build_entry_field_widget(box, name)
                if widget is not None:
                    self.entry_fields[name] = widget

    def _build_address_box(self, form) -> None:
        """
        Key/Key2, editable. See the module docstring for why this is the
        headline feature of the tab rather than a read-only caption.
        """
        box = ttk.LabelFrame(form, text="Address (which encounter and unit slot this row is)", padding=10)
        box.pack(fill="x", pady=(0, 10))

        ttk.Label(
            box, style=NOTE_STYLE, wraplength=560, justify="left",
            text=(
                "Key is the encounter (FFTPatcher's ENTD list, in decimal), Key2 the unit slot "
                "within it. Changing these MOVES this row - it doesn't copy it. That's how you "
                "give an encounter a unit slot the game doesn't already have: take a row you "
                "don't need and repoint it. The row count stays the same, which is what makes "
                "it work."
            ),
        ).pack(anchor="w", pady=(0, 8))

        row = ttk.Frame(box)
        row.pack(fill="x")
        ttk.Label(row, text="Key (encounter):", width=18, anchor="w").pack(side="left")
        self.addr_key_var = tk.StringVar(value="0")
        vcmd = row.register(lambda p: p == "" or p.isdigit())
        ttk.Spinbox(
            row, from_=0, to=c.MAX_ENTRY_KEY, textvariable=self.addr_key_var, width=8,
            validate="key", validatecommand=(vcmd, "%P"),
        ).pack(side="left", padx=(4, 16))
        ttk.Label(row, text="Key2 (unit slot):", width=15, anchor="w").pack(side="left")
        self.addr_key2_var = tk.StringVar(value="0")
        ttk.Spinbox(
            row, from_=0, to=c.MAX_ENTRY_KEY2, textvariable=self.addr_key2_var, width=6,
            validate="key", validatecommand=(vcmd, "%P"),
        ).pack(side="left", padx=(4, 16))

        button_row = ttk.Frame(box)
        button_row.pack(fill="x", pady=(8, 0))
        self.addr_apply_button = ttk.Button(button_row, text="Move this row", command=self._on_apply_address)
        self.addr_apply_button.pack(side="left")
        self.addr_revert_button = ttk.Button(
            button_row, text="Undo move", command=self._on_revert_address, state="disabled"
        )
        self.addr_revert_button.pack(side="left", padx=(8, 0))

        self.addr_status_var = tk.StringVar(value="")
        self.addr_status_label = ttk.Label(box, textvariable=self.addr_status_var, wraplength=560, justify="left")
        self.addr_status_label.pack(anchor="w", pady=(8, 0))

    def _build_entry_field_widget(self, parent, name: str):
        if name in c.ENTRY_BOOL_FIELDS:
            label, help_text, meaning_known = c.ENTRY_BOOL_FIELDS[name]
            return EntryFlagRow(parent, name, label, help_text, meaning_known, self._on_entry_field_edited)
        if name in c.ENTRY_ARRAY_FIELDS:
            label = c.ENTRY_FIELD_LABELS.get(name, name)
            return ArrayFieldRow(
                parent, name, label + _confidence_suffix(name),
                "Comma-separated numbers. Meaning unconfirmed - left as raw values rather than guessed at.",
                self._on_entry_field_edited,
            )
        if name in c.ENTRY_STRING_FIELDS:
            # Declared `string` in the layout and NULL in every real row, so
            # there's nothing meaningful to edit and no numeric bounds to
            # apply. Showing it as a number field would invite writing a
            # value into a column the game reads as text.
            return None
        if name in _DROPDOWN_FIELDS:
            return SearchableIdRow(
                parent, name, c.ENTRY_FIELD_LABELS.get(name, name),
                _DROPDOWN_FIELDS[name](self.app.state_data, self.current_language),
                self._on_entry_field_edited,
                inherit_value=c.entry_inherit_value(name),
                byte_cast=name in c.ENTRY_BYTE_CAST_FIELDS,
            )
        # plain numeric fallback
        bounds = c.ENTRY_NUMERIC_FIELDS[name]
        return EntryNumberRow(parent, name, bounds, self._on_entry_field_edited)

    # -- data loading -----------------------------------------------------

    def _ensure_nxd_loaded(self, language: str) -> bool:
        """
        Reads the two tables this tab uses, INDEPENDENTLY.

        They used to share one try block, so a database without
        CharaName-xx took the Encounters sub-tab down with it - and the
        Encounters sub-tab doesn't need CharaName for anything except
        putting names on a dropdown that works fine with raw ids. That's
        not hypothetical: a mod that only edits overrideentrydata.nxd,
        opened before the game is unpacked, has its own database adopted as
        the working one, and that database contains only the tables the mod
        shipped. Selective unpacking can produce the same shape.

        Returns True if either table loaded - the caller only treats the
        tab as unusable when both are missing.
        """
        state = self.app.state_data
        if state.nxd_sqlite_path is None:
            return False

        problems = []
        self._chara_available = True
        self._entry_available = True
        # Encounter names are a nicety layered on top - never a reason for
        # the tab to fail to open, so this is separate from the two reads
        # below and swallows its own problems (see encounter_names.py).
        self.encounter_names = enc_names.EncounterNames.load()

        try:
            if language not in state.chara_name_records:
                state.chara_name_records[language] = nxd_data.read_charaname_table(state.nxd_sqlite_path, language)
        except Exception as exc:  # noqa: BLE001 - surface any read failure honestly
            self._chara_available = False
            state.chara_name_records[language] = []
            problems.append(f"unit names (CharaName-{language}): {exc}")

        try:
            if not state.entry_records:
                state.entry_records = nxd_data.read_override_entry_table(state.nxd_sqlite_path)
        except Exception as exc:  # noqa: BLE001
            self._entry_available = False
            state.entry_records = []
            problems.append(f"encounters (OverrideEntryData): {exc}")

        if not self._chara_available and not self._entry_available:
            self.no_data_var.set(
                nxd_missing_data_message(state, "Encounter data", "; ".join(problems))
            )
            return False
        if problems:
            missing = "Unit Names" if not self._chara_available else "Encounters"
            present = "Encounters" if not self._chara_available else "Unit Names"
            self.no_data_var.set(
                f"This database has no {missing} data, so that sub-tab is empty - {present} below "
                f"still works normally. That's expected when a mod only changes one of the two."
            )
        else:
            self.no_data_var.set("")
        return True

    # -- Unit Names list ----------------------------------------------------

    def _refresh_chara_list(self) -> None:
        query = self.chara_search_var.get().strip().lower()
        self.chara_tree.delete(*self.chara_tree.get_children())
        records = self.app.state_data.chara_name_records.get(self.current_language, [])
        lang_edits = self.app.state_data.chara_name_edits.get(self.current_language, {})
        for r in records:
            if query and query not in r.display_name.lower() and query != str(r.key):
                continue
            tags = ["edited"] if lang_edits.get(r.key) else []
            self.chara_tree.insert("", "end", iid=str(r.key), text=r.display_name, tags=tags)
        self._update_chara_changes_label()

    def _update_chara_changes_label(self) -> None:
        state = self.app.state_data
        lang_label = c.NXD_LANGUAGE_LABELS[self.current_language]
        total = len(state.chara_name_records.get(self.current_language, [])) or 1024
        count = state.edited_chara_name_count(self.current_language)
        self.chara_changes_var.set(f"{count} of {total} unit names edited in {lang_label}.")

    def _on_chara_tree_select(self, _event=None) -> None:
        selection = self.chara_tree.selection()
        if selection:
            self._load_chara(int(selection[0]))

    def _load_chara(self, key: int) -> None:
        self._loading = True
        self.current_chara_key = key
        state = self.app.state_data
        records = {r.key: r for r in state.chara_name_records.get(self.current_language, [])}
        r = records.get(key)
        self.current_chara_var.set(f"Editing: {r.display_name if r else f'{key:03d} - (no data)'}")
        baseline = r.values if r else {}
        lang_edits = state.chara_name_edits.get(self.current_language, {}).get(key, {})
        for name, widget in self.chara_fields.items():
            if name in lang_edits:
                widget.load(lang_edits[name], True)
            else:
                widget.load(baseline.get(name), False)
        self._loading = False

    def _on_chara_field_edited(self) -> None:
        if self._loading or self.current_chara_key is None:
            return
        key = self.current_chara_key
        edits = self.app.state_data.chara_name_edits.setdefault(self.current_language, {}).setdefault(key, {})
        for name, widget in self.chara_fields.items():
            if widget.included:
                edits[name] = widget.get_value()
            elif name in edits:
                del edits[name]
        if not edits:
            self.app.state_data.chara_name_edits[self.current_language].pop(key, None)
        self._refresh_chara_tree_tag(key)
        self._update_chara_changes_label()

    def _on_chara_copy_all_fields_clicked(self) -> None:
        if self.current_chara_key is None:
            return
        widgets = [w for w in self.chara_fields.values() if hasattr(w, "copy_fields")]
        if not widgets:
            return
        for widget in widgets:
            widget.include_var.set(True)
        self._on_chara_field_edited()  # also commit/include everything for the language currently being viewed

        key = self.current_chara_key
        state = self.app.state_data
        other_langs = [lang for lang in c.NXD_LANGUAGES if lang != self.current_language]
        for lang in other_langs:
            lang_edits = state.chara_name_edits.setdefault(lang, {}).setdefault(key, {})
            for widget in widgets:
                lang_edits.update(widget.copy_fields())

        self.chara_copy_status_var.set(
            f"Copied {len(widgets)} field(s) to all {len(other_langs)} other languages "
            f"({', '.join(c.NXD_LANGUAGE_LABELS[l] for l in other_langs)})."
        )
        self._update_chara_changes_label()

    def _refresh_chara_tree_tag(self, key: int) -> None:
        edits = self.app.state_data.chara_name_edits.get(self.current_language, {})
        tags = ["edited"] if edits.get(key) else []
        if self.chara_tree.exists(str(key)):
            self.chara_tree.item(str(key), tags=tags)

    # -- Encounters tree/list -------------------------------------------------

    def _entry_iid(self, address: tuple) -> str:
        return f"k{address[0]}_u{address[1]}"

    def _unit_summary(self, origin: tuple) -> str:
        """
        A short "what is this unit" caption for the tree, built from the
        row's own values with any pending edits applied - so a repurposed
        row reads as what the mod made it, not as what vanilla had.
        """
        state = self.app.state_data
        record = state.entry_records_by_key().get(origin)
        values = dict(record.values) if record else {}
        values.update(state.entry_edits.get(origin, {}))

        def readable(lookup: dict, id_value):
            """The name half of a "123 - Ramza" display name, or None."""
            raw = lookup.get(id_value)
            if not raw:
                return None
            name = raw.split(" - ", 1)[-1].strip()
            # Reference tables use "(unnamed)" / "(unnamed slot)" for empty
            # rows. Those say nothing and, appended to a label that already
            # carries a "was 128/0" suffix, they overflowed the tree.
            return None if not name or name.startswith("(") else name

        # Unit name first - it identifies the unit far better than its job
        # does - and only one of the two, to keep the label short enough to
        # fit the panel alongside the move marker.
        name = readable(_chara_name_id_to_name(state, self.current_language), values.get("Unknown4"))
        if name is None and values.get("MainJob"):
            name = readable(_job_id_to_name(state), values.get("MainJob"))
        return f"  ({name})" if name else ""

    def _row_tags(self, origin: tuple) -> list:
        """
        The highlight for a single row. Edited wins over moved: green means
        "you changed something" everywhere else in this tool, and a moved
        row already announces itself in its own label text ("<- was 128/0"),
        so it doesn't need the colour to carry that as well.
        """
        state = self.app.state_data
        if state.entry_edits.get(origin):
            return ["edited"]
        if origin in state.entry_rekeys:
            return ["moved"]
        return []

    def _encounter_tags(self, key: int) -> list:
        """
        The highlight for an Encounter node, from whatever its unit slots
        are doing. Edits to a unit have to show on the encounter too -
        otherwise a collapsed tree hides the fact that anything in it
        changed at all, which is most of what the list is for.
        """
        state = self.app.state_data
        origins = [
            origin for address, origin in state.entry_origins_by_address().items()
            if address[0] == key
        ]
        if any(state.entry_edits.get(origin) for origin in origins):
            return ["edited"]
        if any(origin in state.entry_rekeys for origin in origins):
            return ["moved"]
        return []

    def _unit_label(self, origin: tuple, address: tuple) -> str:
        label = f"Unit {address[1]}"
        if origin in self.app.state_data.entry_rekeys:
            label += f"  \u2190 was {origin[0]}/{origin[1]}"
        return label + self._unit_summary(origin)

    def _refresh_entry_tree(self) -> None:
        """
        Builds the tree from the EFFECTIVE row set - every row at the
        address it will actually be exported to, not the address it has in
        the working database.

        This is the display half of the redesign. Before, the tree was
        built straight from entry_records (i.e. from vanilla), so a mod
        that had moved ten rows to (95, 0..9) showed no Encounter 95 at all
        while simultaneously reporting "10 unit slot(s) edited" - the rows
        were in entry_edits, which nothing drew.
        """
        selected = self.current_entry_key
        self.entry_tree.delete(*self.entry_tree.get_children())
        state = self.app.state_data
        entry_edits = state.entry_edits

        by_key = {}
        for address, origin in state.entry_origins_by_address().items():
            by_key.setdefault(address[0], []).append((address, origin))

        for key in sorted(by_key):
            units = sorted(by_key[key])
            parent_id = self.entry_tree.insert(
                "", "end", iid=f"k{key}", text=self.encounter_names.label_for(key),
                tags=self._encounter_tags(key),
            )
            for address, origin in units:
                self.entry_tree.insert(
                    parent_id, "end", iid=self._entry_iid(address),
                    text=self._unit_label(origin, address), tags=self._row_tags(origin),
                )

        self._update_entry_changes_label()
        if selected is not None:
            iid = self._entry_iid(state.entry_address(selected))
            if self.entry_tree.exists(iid):
                self.entry_tree.selection_set(iid)
                self.entry_tree.see(iid)

    def _update_entry_changes_label(self) -> None:
        state = self.app.state_data
        count = state.edited_entry_count()
        moved = len(state.entry_rekeys)
        parts = [f"{count} unit slot(s) edited."]
        if moved:
            parts.append(f"{moved} row(s) moved to a different encounter/unit slot.")
        self.entry_changes_var.set("\n".join(parts))

        current = state.entry_row_count()
        baseline = state.entry_baseline_row_count()
        if not baseline:
            self.entry_rowset_var.set("")
            return
        if current == baseline:
            self.entry_rowset_var.set(f"{current} rows - same as the database this was loaded from.")
            self.entry_rowset_label.configure(foreground="#0a6e0a")
        else:
            self.entry_rowset_var.set(
                f"{current} rows, up from {baseline}." if current > baseline
                else f"{current} rows, down from {baseline}."
                " Rows removed on purpose are exported as removed."
            )
            self.entry_rowset_label.configure(foreground="#b06000")

    def _on_entry_tree_select(self, _event=None) -> None:
        selection = self.entry_tree.selection()
        if not selection:
            return
        iid = selection[0]
        if "_u" in iid:
            key_part, unit_part = iid[1:].split("_u")
            address = (int(key_part), int(unit_part))
            origin = self.app.state_data.entry_origins_by_address().get(address, address)
            self._load_entry(origin)

    def _on_jump_clicked(self) -> None:
        # Hex is accepted here because someone looking a battle up in
        # FFTPatcher has a hex id in front of them - see
        # encounter_names.parse_encounter_id.
        key = enc_names.parse_encounter_id(self.jump_key_var.get())
        key2 = enc_names.parse_encounter_id(self.jump_key2_var.get())
        if key is None or key2 is None:
            return
        key = max(0, min(c.MAX_ENTRY_KEY, key))
        key2 = max(0, min(c.MAX_ENTRY_KEY2, key2))
        address = (key, key2)
        state = self.app.state_data
        origin = state.entry_origins_by_address().get(address)
        if origin is None:
            self._offer_new_row(address)
            return
        self._load_entry(origin)
        iid = self._entry_iid(address)
        if self.entry_tree.exists(iid):
            self.entry_tree.selection_set(iid)
            self.entry_tree.see(iid)

    def _offer_new_row(self, address: tuple) -> None:
        """
        Creating an address that doesn't exist yet. Kept possible, but it
        is the thing Zodi found didn't work in-game, so it says so plainly
        instead of quietly adding a row that will be ignored.
        """
        if not messagebox.askokcancel(
            "This unit slot doesn't exist yet",
            f"Encounter {address[0]}, Unit {address[1]} isn't in the table.\n\n"
            "Adding a brand new row here does not appear to work in-game - the game only reads "
            "the rows it already knows about. The reliable way to get a new unit slot is to MOVE "
            "an existing row you don't need: open that row and change its Key/Key2.\n\n"
            "Create it anyway?",
            icon="warning",
        ):
            return
        self._load_entry(address, allow_missing=True)

    # -- loading / committing (Encounters) ---------------------------------

    def _load_entry(self, origin: tuple, allow_missing: bool = False) -> None:
        """
        `origin` is where the row sits in the working database - the stable
        identity edits are keyed by. Its current address may differ.
        """
        self._loading = True
        self.current_entry_key = origin
        state = self.app.state_data
        record = state.entry_records_by_key().get(origin)
        address = state.entry_address(origin)
        is_new = record is None

        title = f"Editing: Encounter {self.encounter_names.label_for(address[0])}, Unit {address[1]}"
        if origin != address:
            title += f"   (moved here from {origin[0]}/{origin[1]})"
        if is_new:
            title += "   (new row)"
        self.current_entry_var.set(title)

        baseline = record.values if record else {}
        edits = state.entry_edits.get(origin, {})

        self.addr_key_var.set(str(address[0]))
        self.addr_key2_var.set(str(address[1]))
        self._refresh_address_controls()

        for name, widget in self.entry_fields.items():
            default = c.entry_new_row_value(name)
            widget.load(edits.get(name, baseline.get(name, default)), name in edits)

        self._loading = False

    def _refresh_address_controls(self) -> None:
        state = self.app.state_data
        origin = self.current_entry_key
        if origin is None:
            return
        address = state.entry_address(origin)
        moved = origin in state.entry_rekeys
        self.addr_revert_button.configure(state="normal" if moved else "disabled")
        if moved:
            self.addr_status_var.set(
                f"This row started life as Encounter {origin[0]}, Unit {origin[1]} and now sits at "
                f"Encounter {address[0]}, Unit {address[1]}. \u201cUndo move\u201d puts it back; any field "
                f"edits you've made stay with it either way."
            )
            self.addr_status_label.configure(foreground="#0a4d8c")
        else:
            self.addr_status_var.set("")
            self.addr_status_label.configure(foreground="#666666")

    def _on_apply_address(self) -> None:
        origin = self.current_entry_key
        if origin is None:
            return
        state = self.app.state_data
        try:
            key = max(0, min(c.MAX_ENTRY_KEY, int(self.addr_key_var.get())))
            key2 = max(0, min(c.MAX_ENTRY_KEY2, int(self.addr_key2_var.get())))
        except ValueError:
            self.addr_status_var.set("Key and Key2 both need to be whole numbers.")
            self.addr_status_label.configure(foreground="#b00020")
            return

        target = (key, key2)
        if target == state.entry_address(origin):
            self.addr_status_var.set("That's already where this row is.")
            self.addr_status_label.configure(foreground="#666666")
            return

        conflict = state.entry_address_conflict(origin, target)
        if conflict is not None:
            where = (
                f"the row originally at {conflict[0]}/{conflict[1]}"
                if conflict != target else "another row"
            )
            self.addr_status_var.set(
                f"Encounter {key}, Unit {key2} is already taken by {where}. Two rows at the same "
                f"address would both be written and the game would only see one of them. Move that "
                f"row somewhere else first, or pick a free slot."
            )
            self.addr_status_label.configure(foreground="#b00020")
            return

        if target == origin:
            state.entry_rekeys.pop(origin, None)
        else:
            state.entry_rekeys[origin] = target

        self._refresh_entry_tree()
        self._load_entry(origin)
        iid = self._entry_iid(target)
        if self.entry_tree.exists(iid):
            self.entry_tree.selection_set(iid)
            self.entry_tree.see(iid)

    def _on_revert_address(self) -> None:
        origin = self.current_entry_key
        if origin is None:
            return
        state = self.app.state_data
        if origin not in state.entry_rekeys:
            return
        conflict = state.entry_address_conflict(origin, origin)
        if conflict is not None:
            self.addr_status_var.set(
                f"Can't move this row back to {origin[0]}/{origin[1]} - the row originally at "
                f"{conflict[0]}/{conflict[1]} is sitting there now. Move that one away first."
            )
            self.addr_status_label.configure(foreground="#b00020")
            return
        state.entry_rekeys.pop(origin, None)
        self._refresh_entry_tree()
        self._load_entry(origin)

    def _on_entry_field_edited(self) -> None:
        if self._loading or self.current_entry_key is None:
            return
        origin = self.current_entry_key
        edits = self.app.state_data.entry_edits.setdefault(origin, {})
        for name, widget in self.entry_fields.items():
            if widget.included:
                edits[name] = widget.get_value()
            elif name in edits:
                del edits[name]
        if not edits:
            self.app.state_data.entry_edits.pop(origin, None)
        self._refresh_entry_tree_tag(origin)
        self._update_entry_changes_label()

    def _refresh_entry_tree_tag(self, origin: tuple) -> None:
        """
        Updates one row's label/highlight in place, AND its encounter's.

        The encounter half is the point: editing a unit used to colour only
        the unit, leaving its Encounter node plain until something forced a
        full rebuild. With the tree collapsed - which is how it spends most
        of its time, at 95 encounters - that meant an edited mod looked
        completely untouched.
        """
        state = self.app.state_data
        address = state.entry_address(origin)
        iid = self._entry_iid(address)
        parent_id = f"k{address[0]}"

        if self.entry_tree.exists(iid):
            self.entry_tree.item(iid, tags=self._row_tags(origin), text=self._unit_label(origin, address))
        elif state.entry_edits.get(origin) or origin in state.entry_rekeys:
            # A brand new address that just received its first edit - add
            # it to the tree live rather than making the user reload the tab.
            if not self.entry_tree.exists(parent_id):
                self.entry_tree.insert(
                    "", "end", iid=parent_id, text=self.encounter_names.label_for(address[0])
                )
            self.entry_tree.insert(
                parent_id, "end", iid=iid,
                text=self._unit_label(origin, address), tags=self._row_tags(origin) or ["edited"],
            )

        if self.entry_tree.exists(parent_id):
            self.entry_tree.item(parent_id, tags=self._encounter_tags(address[0]))

    def _on_language_changed(self, _event=None) -> None:
        lang = self._label_to_lang.get(self.language_var.get(), self.current_language)
        if lang == self.current_language:
            return
        self.current_language = lang
        self._ensure_nxd_loaded(lang)
        self._refresh_chara_list()
        if self.current_chara_key is not None:
            self._load_chara(self.current_chara_key)
        elif self.app.state_data.chara_name_records.get(lang):
            first_key = self.app.state_data.chara_name_records[lang][0].key
            if self.chara_tree.exists(str(first_key)):
                self.chara_tree.selection_set(str(first_key))
        if "Unknown4" in self.entry_fields:
            self.entry_fields["Unknown4"].update_choices(_chara_name_id_to_name(self.app.state_data, lang))
        # Unit names feed the Encounters tree captions too, so it has to be
        # redrawn - not just the dropdown.
        self._refresh_entry_tree()

    # -- called by the combined step's on_show() -----------------------------

    def on_show(self) -> None:
        state = self.app.state_data

        if state.nxd_sqlite_path is None:
            self.no_data_var.set(
                "No ability/item/encounter database loaded yet - go to General Setup, tick "
                "\u201cGame data\u201d, and press \u201cUnpack and Prepare Game Files\u201d."
            )
            self.chara_tree.delete(*self.chara_tree.get_children())
            self.entry_tree.delete(*self.entry_tree.get_children())
            self.chara_changes_var.set("")
            self.entry_changes_var.set("")
            return

        if state.nxd_sqlite_path != self._applied_sqlite_path:
            self._applied_sqlite_path = state.nxd_sqlite_path
            state.chara_name_records = {}
            state.entry_records = []
            self.current_chara_key = None
            self.current_entry_key = None

        if not self._ensure_nxd_loaded(self.current_language):
            return

        # Job/Job Command/Ability/Item reference data may have finished
        # loading (or been refreshed) since this panel was built - refresh
        # dropdown choices every time rather than only once at construction.
        self._refresh_dropdown_choices()

        self._refresh_chara_list()
        self._refresh_entry_tree()

        if self.current_chara_key is None and state.chara_name_records.get(self.current_language):
            first_key = state.chara_name_records[self.current_language][0].key
            if self.chara_tree.exists(str(first_key)):
                self.chara_tree.selection_set(str(first_key))

        if self.current_entry_key is None and state.entry_records:
            first_address = min(state.entry_origins_by_address(), default=None)
            if first_address is not None:
                iid = self._entry_iid(first_address)
                if self.entry_tree.exists(iid):
                    self.entry_tree.selection_set(iid)

    def _refresh_dropdown_choices(self) -> None:
        state = self.app.state_data
        for name, builder in _DROPDOWN_FIELDS.items():
            widget = self.entry_fields.get(name)
            if widget is not None:
                widget.update_choices(builder(state, self.current_language))
