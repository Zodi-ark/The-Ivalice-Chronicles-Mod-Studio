"""
The "Job Commands" tab within the combined Edit Jobs & Job Commands step.

Mirrors FFTPatcher's own split between Jobs and Skill Sets (renamed "Job
Command" in Ivalice Chronicles) - this is a separate table
(JobCommandData.xml) with its own diff file, so it gets its own tab rather
than being mixed into the Job editor's fields.

Same two ideas as step_editor.py: every field has an independent
include/inherit checkbox, and edits commit to
app.state_data.job_command_edits immediately on every change.

Quality-of-life jump: every SearchableAbilityRow (both the Abilities sub-tab's
16 menu slots and the Reaction/Support/Movement sub-tab's 6 slots) gets an
"Edit \u2192" button, disabled while "(None)" is selected - jumps to that
exact ability in the main Abilities tab, the same dropdown-preview-jump-
button convention step_editor.py's own JobCommandDropdownRow already
established for Jobs -> Job Commands (see JobEditorStep._go_to_ability).
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .. import ability_names
from .. import constants as c
from .. import xml_io
from .step_editor import NOTE_STYLE, ScrollableFrame


class SearchableAbilityRow:
    """
    One row: [include checkbox] label [type-to-filter ability dropdown] [Edit \u2192].

    candidate_ids scopes what's offered: action-type abilities for a
    command's 16 menu slots, or Reaction/Support/Movement-type ones for its
    6 R/S/M slots - see constants.ACTION_ABILITY_TYPES / RSM_ABILITY_TYPES
    and xml_io.load_ability_types (the split is read straight from
    AbilityData.xml's own AbilityType field, not guessed at via an id
    range). Either way, a value already present in loaded data that falls
    outside the offered candidates is still shown honestly rather than
    dropped - same safety net used elsewhere. candidate_ids isn't known at
    construction time (it depends on data fetched in Step 1), so it starts
    empty and refresh() populates it.

    The jump button (on_go_to_ability) is the same dropdown-preview-jump-
    button convention step_editor.py's own JobCommandDropdownRow already
    established for Jobs -> Job Commands - jumps to this exact ability in
    the main Abilities tab, disabled while "(None)" is selected.
    """

    def __init__(self, parent, field_name: str, label: str, on_user_edit, on_go_to_ability=None):
        self.field_name = field_name
        self._on_user_edit = on_user_edit
        self._on_go_to_ability = on_go_to_ability
        self._suppress = False
        self._current_id = 0
        self._ability_names_live: dict = {}
        self._candidate_ids: list[int] = []

        self._id_to_display: dict[int, str] = {}
        self._display_to_id: dict[str, int] = {}
        self._rebuild_choice_maps()

        self.include_var = tk.BooleanVar(value=False)
        self.display_var = tk.StringVar(value=self._id_to_display[0])

        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Checkbutton(row, variable=self.include_var, command=self._fire_edit).pack(side="left")
        ttk.Label(row, text=label, width=14, anchor="w").pack(side="left")
        self.combo = ttk.Combobox(
            row, textvariable=self.display_var, values=self._display_values(), width=36
        )
        self.combo.pack(side="left", padx=(4, 8))
        self.combo.bind("<KeyRelease>", self._on_key_release)
        self.combo.bind("<<ComboboxSelected>>", self._on_selected)
        self.combo.bind("<Return>", self._on_selected)
        self.combo.bind("<FocusOut>", self._on_focus_out)
        # Short label ("Edit \u2192", not "Edit this Ability \u2192" like step_editor.py's
        # JobCommandDropdownRow) - this row is repeated 16/6 times per command, and a real
        # screenshot showed the fuller text getting clipped by the panel's width at that
        # repetition (same class of bug HANDOFF.md already documents for the texture jump
        # button/preview panels - fixed the same way, by giving the row less to fit).
        # Compact.TButton (app.py) trims the button back down to the same height as the
        # combobox/checkbutton next to it - an ordinary ttk.Button renders visibly taller,
        # which loosened up the whole list's spacing once repeated 16/6 times per command.
        self.goto_button = ttk.Button(
            row, text="Edit \u2192", width=7, command=self._go_to_ability, state="disabled",
            style="Compact.TButton",
        )
        self.goto_button.pack(side="left", padx=(4, 0))

    # -- choice maps ------------------------------------------------------

    def _rebuild_choice_maps(self) -> None:
        self._id_to_display = {0: "(None)"}
        self._display_to_id = {"(None)": 0}
        for ability_id in self._candidate_ids:
            if ability_id == 0:
                continue
            self._register(ability_id)
        if self._current_id not in self._id_to_display:
            self._register(self._current_id)

    def _register(self, ability_id: int) -> None:
        name = ability_names.resolve_ability_name(ability_id, self._ability_names_live)
        display = f"{ability_id} - {name}"
        self._id_to_display[ability_id] = display
        self._display_to_id[display] = ability_id

    def _display_values(self) -> list[str]:
        return [self._id_to_display[i] for i in sorted(self._id_to_display)]

    def refresh(self, candidate_ids: list, ability_names_live: dict) -> None:
        """Call when the candidate list and/or live ability names change (Step 1 fetch)."""
        self._candidate_ids = list(candidate_ids)
        self._ability_names_live = ability_names_live
        self._rebuild_choice_maps()
        self.combo.configure(values=self._display_values())
        self.display_var.set(self._id_to_display[self._current_id])

    # -- interaction --------------------------------------------------------

    def _on_key_release(self, event) -> None:
        if event.keysym in ("Up", "Down", "Return", "Escape", "Tab"):
            return
        typed = self.display_var.get().strip().lower()
        filtered = self._display_values() if not typed else [
            d for d in self._display_values() if typed in d.lower()
        ]
        self.combo.configure(values=filtered)
        try:
            self.combo.event_generate("<Down>")
        except tk.TclError:
            pass

    def _on_selected(self, _event=None) -> None:
        self._commit_from_display()

    def _on_focus_out(self, _event=None) -> None:
        self._commit_from_display(revert_if_invalid=True)

    def _commit_from_display(self, revert_if_invalid: bool = False) -> None:
        if self._suppress:
            return
        text = self.display_var.get()
        if text in self._display_to_id:
            new_id = self._display_to_id[text]
            changed = new_id != self._current_id
            self._current_id = new_id
            self.combo.configure(values=self._display_values())
            self._update_goto_button()
            if changed:
                self.include_var.set(True)
                self._fire_edit()
        elif revert_if_invalid:
            self._suppress = True
            self.display_var.set(self._id_to_display[self._current_id])
            self._suppress = False
            self.combo.configure(values=self._display_values())

    def _fire_edit(self) -> None:
        if self._on_user_edit:
            self._on_user_edit()

    def _update_goto_button(self) -> None:
        self.goto_button.configure(state="normal" if self._current_id else "disabled")

    def _go_to_ability(self) -> None:
        if self._on_go_to_ability and self._current_id:
            self._on_go_to_ability(self._current_id)

    # -- load/save (same interface as the other field widgets) --------------

    def load(self, value_str: str, included: bool) -> None:
        self._suppress = True
        try:
            ability_id = int(value_str)
        except (ValueError, TypeError):
            ability_id = 0
        self._current_id = ability_id
        if ability_id not in self._id_to_display:
            self._register(ability_id)
            self.combo.configure(values=self._display_values())
        self.display_var.set(self._id_to_display[ability_id])
        self._suppress = False
        self.include_var.set(included)
        self._update_goto_button()

    def get_value_str(self) -> str:
        return str(self._current_id)

    @property
    def included(self) -> bool:
        return self.include_var.get()


class JobCommandsPanel(ttk.Frame):
    """The 'Job Commands' tab within the combined Edit Jobs & Job Commands step."""

    def __init__(self, parent, app, on_go_to_ability=None):
        super().__init__(parent)
        self.app = app
        self._on_go_to_ability = on_go_to_ability
        self.current_command_id: int | None = None
        self.fields: dict[str, object] = {}
        self._loading = False
        self._applied_ability_names: dict | None = None
        self._applied_ability_types: dict | None = None

        self._build_layout()

    # -- layout ---------------------------------------------------------

    def _build_layout(self) -> None:
        ttk.Label(
            self,
            style="SubHeader.TLabel",
            wraplength=760,
            justify="left",
            text=(
                "Job Commands are skillsets (FFTPatcher calls them Skill Sets) - the 16 "
                "abilities on a job's action menu, plus the Reaction/Support/Movement abilities "
                "it unlocks. Type in a dropdown to search by name. Only fields you check the box "
                "next to are written into your mod."
            ),
        ).pack(anchor="w", pady=(4, 12))

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)

        left = ttk.Frame(body, width=260)
        left.pack(side="left", fill="y", padx=(0, 12))
        left.pack_propagate(False)

        self.changes_var = tk.StringVar(value="0 of 179 job commands have pending edits")
        ttk.Label(left, textvariable=self.changes_var, foreground="#0a6e0a").pack(
            anchor="w", pady=(0, 6)
        )

        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(left, textvariable=self.search_var)
        search_entry.pack(fill="x", pady=(0, 6))
        self.search_var.trace_add("write", lambda *_a: self._refresh_command_list())
        ttk.Label(left, text="Search by name or ID", foreground="#888888").pack(anchor="w")

        tree_frame = ttk.Frame(left)
        tree_frame.pack(fill="both", expand=True, pady=(6, 0))
        self.command_tree = ttk.Treeview(tree_frame, show="tree", selectmode="browse")
        tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.command_tree.yview)
        self.command_tree.configure(yscrollcommand=tree_scroll.set)
        self.command_tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")
        self.command_tree.tag_configure("edited", background=c.EDITED_ROW_BG, foreground=c.EDITED_ROW_FG)
        self.command_tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True)

        self.current_command_var = tk.StringVar(value="No job command selected")
        ttk.Label(right, textvariable=self.current_command_var, font=("Segoe UI", 12, "bold")).pack(
            anchor="w", pady=(0, 8)
        )

        self.notebook = ttk.Notebook(right)
        self.notebook.pack(fill="both", expand=True)

        self._build_abilities_tab()
        self._build_rsm_tab()

    def _add_scrollable_tab(self, title: str) -> ttk.Frame:
        scroll = ScrollableFrame(self.notebook)
        self.notebook.add(scroll, text=title)
        return scroll.inner

    def _build_abilities_tab(self) -> None:
        tab = self._add_scrollable_tab("Abilities")
        ttk.Label(
            tab, wraplength=700, justify="left", style=NOTE_STYLE,
            text="The 16 abilities available on this job's action menu (attacks, spells, items, etc.).",
        ).pack(anchor="w", pady=(0, 8))
        for i in range(1, 17):
            field_name = f"AbilityId{i}"
            self.fields[field_name] = SearchableAbilityRow(
                tab, field_name, f"Ability {i}", self._on_field_edited, on_go_to_ability=self._on_go_to_ability
            )

    def _build_rsm_tab(self) -> None:
        tab = self._add_scrollable_tab("Reaction / Support / Movement")
        ttk.Label(
            tab, wraplength=700, justify="left", foreground="#777777",
            text=(
                "Reaction, Support, and Movement abilities this job command unlocks for a "
                "character to equip (from any job they've learned it in)."
            ),
        ).pack(anchor="w", pady=(0, 8))
        for i in range(1, 7):
            field_name = f"ReactionSupportMovementId{i}"
            self.fields[field_name] = SearchableAbilityRow(
                tab, field_name, f"R/S/M {i}", self._on_field_edited, on_go_to_ability=self._on_go_to_ability
            )

    # -- command list -------------------------------------------------------

    def _refresh_command_list(self) -> None:
        query = self.search_var.get().strip().lower()
        self.command_tree.delete(*self.command_tree.get_children())
        for record in self.app.state_data.job_command_records:
            if query and query not in record.display_name.lower() and query != str(record.command_id):
                continue
            tags = []
            if record.command_id in self.app.state_data.job_command_edits and \
                    self.app.state_data.job_command_edits[record.command_id]:
                tags.append("edited")
            self.command_tree.insert(
                "", "end", iid=str(record.command_id), text=record.display_name, tags=tags
            )
        self._update_changes_label()

    def _update_changes_label(self) -> None:
        count = self.app.state_data.edited_job_command_count()
        total = len(self.app.state_data.job_command_records) or 179
        self.changes_var.set(f"{count} of {total} job commands have pending edits")

    def _on_tree_select(self, _event=None) -> None:
        selection = self.command_tree.selection()
        if selection:
            self._load_command(int(selection[0]))

    # -- loading / committing -------------------------------------------------

    def _load_command(self, command_id: int) -> None:
        self._loading = True
        self.current_command_id = command_id
        record = self.app.state_data.job_commands_by_id().get(command_id)
        if record is None:
            self._loading = False
            return

        self.current_command_var.set(f"Editing: {record.display_name}")

        edits_for_command = self.app.state_data.job_command_edits.get(command_id, {})
        for i in range(1, 17):
            field_name = f"AbilityId{i}"
            widget = self.fields[field_name]
            if field_name in edits_for_command:
                widget.load(edits_for_command[field_name], True)
            else:
                widget.load(str(record.ability_ids[i - 1]), False)
        for i in range(1, 7):
            field_name = f"ReactionSupportMovementId{i}"
            widget = self.fields[field_name]
            if field_name in edits_for_command:
                widget.load(edits_for_command[field_name], True)
            else:
                widget.load(str(record.rsm_ids[i - 1]), False)

        self._loading = False

    def _on_field_edited(self) -> None:
        if self._loading or self.current_command_id is None:
            return
        command_id = self.current_command_id
        edits = self.app.state_data.job_command_edits.setdefault(command_id, {})
        for field_name, widget in self.fields.items():
            if widget.included:
                edits[field_name] = widget.get_value_str()
            elif field_name in edits:
                del edits[field_name]
        if not edits:
            self.app.state_data.job_command_edits.pop(command_id, None)

        tags = []
        if command_id in self.app.state_data.job_command_edits and \
                self.app.state_data.job_command_edits[command_id]:
            tags = ["edited"]
        if self.command_tree.exists(str(command_id)):
            self.command_tree.item(str(command_id), tags=tags)
        self._update_changes_label()

    # -- called by the combined step's on_show() -----------------------------

    def on_show(self) -> None:
        ability_names_live = self.app.state_data.ability_names
        ability_types = self.app.state_data.ability_types
        if ability_types is not self._applied_ability_types or ability_names_live is not self._applied_ability_names:
            self._applied_ability_types = ability_types
            self._applied_ability_names = ability_names_live

            action_ids = [i for i, t in ability_types.items() if t in c.ACTION_ABILITY_TYPES]
            rsm_ids = [i for i, t in ability_types.items() if t in c.RSM_ABILITY_TYPES]

            for i in range(1, 17):
                self.fields[f"AbilityId{i}"].refresh(action_ids, ability_names_live)
            for i in range(1, 7):
                self.fields[f"ReactionSupportMovementId{i}"].refresh(rsm_ids, ability_names_live)

            if self.current_command_id is not None:
                self._load_command(self.current_command_id)

        self._refresh_command_list()
        if self.current_command_id is None and self.app.state_data.job_command_records:
            first_id = str(self.app.state_data.job_command_records[0].command_id)
            if self.command_tree.exists(first_id):
                self.command_tree.selection_set(first_id)
