"""
The "Treasure Hunter" tab within the combined Edit Game Data step.

Architecturally the mirror image of Poaching: this one is an ordinary
reference/diff XML table (MapTrapFormationData.xml), the exact same shape
as the six Item*Data.xml tables, so it's wired into item_xml_io.py's
generic TableSpec engine (MAP_TRAP_SPEC) rather than needing any new
read/write code - no game unpack needed, same as JobData.xml/Items' own
Stats tab. See constants.py's Treasure Hunter section docstring for the
full picture (ability 509, up to 4 tiles per map, TrapFlags semantics).

Reuses ItemFlagFieldPanel/XmlNumberRow from step_editor.py (both already
fully generic - nothing Item-specific to change), plus a new XmlSearchableItemRow here for Rare/Common Item (a
string-valued generalization of step_job_commands.SearchableAbilityRow,
since every other Stats-tab widget in this app is load(value_str)/
get_value_str(), not Encounters' int-valued load(value)/get_value()).
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .. import constants as c
from .step_editor import ItemFlagFieldPanel, ScrollableFrame, XmlNumberRow


def _item_id_to_name(state) -> dict:
    """Same reference data Encounters/Items/Poaching already use - nothing new fetched here."""
    return {r.item_id: r.display_name() for r in state.item_table_records.get("item", [])}


class XmlSearchableItemRow:
    """
    [include] label [type-to-filter item dropdown] - a generalized,
    string-valued version of step_job_commands.SearchableAbilityRow: picks
    an ItemData id by name, reusing this app's own already-loaded Item
    reference data (same idea as Encounters' SearchableIdRow, just XML-
    diff string-valued to match every other Stats-tab widget's
    load(value_str)/get_value_str() contract).
    """

    def __init__(self, parent, field_name: str, label: str, on_user_edit):
        self.field_name = field_name
        self._on_user_edit = on_user_edit
        self._suppress = False
        self._current_id = 0
        self._id_to_display: dict[int, str] = {0: "(0) None"}
        self._display_to_id: dict[str, int] = {"(0) None": 0}

        self.include_var = tk.BooleanVar(value=False)
        self.display_var = tk.StringVar(value=self._id_to_display[0])

        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Checkbutton(row, variable=self.include_var, command=self._fire_edit).pack(side="left")
        ttk.Label(row, text=label, width=14, anchor="w").pack(side="left")
        self.combo = ttk.Combobox(row, textvariable=self.display_var, values=self._display_values(), width=38)
        self.combo.pack(side="left", padx=(4, 10))
        self.combo.bind("<KeyRelease>", self._on_key_release)
        self.combo.bind("<<ComboboxSelected>>", self._on_selected)
        self.combo.bind("<Return>", self._on_selected)
        self.combo.bind("<FocusOut>", self._on_focus_out)

    def _display_values(self) -> list[str]:
        return [self._id_to_display[i] for i in sorted(self._id_to_display)]

    def update_choices(self, id_to_name: dict) -> None:
        # id_to_name's values are ItemTableRecord.display_name() results, which already
        # carry their own "NNN - " id prefix - use them as-is rather than prefixing again.
        self._id_to_display = {0: "(0) None"}
        self._display_to_id = {"(0) None": 0}
        for item_id, display in id_to_name.items():
            if item_id == 0:
                continue
            self._id_to_display[item_id] = display
            self._display_to_id[display] = item_id
        if self._current_id not in self._id_to_display:
            self._register_unrecognized(self._current_id)
        self.combo.configure(values=self._display_values())
        self.display_var.set(self._id_to_display[self._current_id])

    def _register_unrecognized(self, item_id: int) -> None:
        display = f"{item_id:03d} - (unrecognized)"
        self._id_to_display[item_id] = display
        self._display_to_id[display] = item_id

    def _on_key_release(self, event) -> None:
        if event.keysym in ("Up", "Down", "Return", "Escape", "Tab"):
            return
        typed = self.display_var.get().strip().lower()
        filtered = self._display_values() if not typed else [
            d for d in self._display_values() if typed in d.lower()
        ]
        self.combo.configure(values=filtered)

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

    def load(self, value_str, included: bool) -> None:
        self._suppress = True
        try:
            item_id = int(value_str)
        except (ValueError, TypeError):
            item_id = 0
        self._current_id = item_id
        if item_id not in self._id_to_display:
            self._register_unrecognized(item_id)
            self.combo.configure(values=self._display_values())
        self.display_var.set(self._id_to_display[item_id])
        self._suppress = False
        self.include_var.set(included)

    def get_value_str(self) -> str:
        return str(self._current_id)

    @property
    def included(self) -> bool:
        return self.include_var.get()


class TreasureHunterPanel(ttk.Frame):
    """The 'Treasure Hunter' tab within the combined Edit Game Data step."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.current_map_id: int | None = None
        self.slot_fields: dict = {}   # "X1"/"TrapFlags1"/"RareItemId1"/etc. -> widget
        self._loading = False

        self._build_layout()

    # -- layout ---------------------------------------------------------

    def _build_layout(self) -> None:
        ttk.Label(
            self, style="SubHeader.TLabel", wraplength=760, justify="left",
            text=(
                "Treasure Hunter (ability 509, vanilla FFT/FFTPatcher's \u201cMove-Find Item\u201d) reads an "
                "ordinary reference/diff XML table (MapTrapFormationData.xml) - the same include/"
                "inherit-checkbox convention as JobData.xml, no game unpack needed. Each of the 128 "
                "maps has up to 4 treasure tiles; leave a tile's fields unchecked to leave it alone."
            ),
        ).pack(anchor="w", pady=(4, 8))

        self.no_reference_var = tk.StringVar(value="")
        ttk.Label(
            self, textvariable=self.no_reference_var, foreground="#b06000", wraplength=760, justify="left"
        ).pack(anchor="w", pady=(0, 8))

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)

        left = ttk.Frame(body, width=280)
        left.pack(side="left", fill="y", padx=(0, 12))
        left.pack_propagate(False)

        self.changes_var = tk.StringVar(value="")
        ttk.Label(left, textvariable=self.changes_var, foreground="#0a6e0a", wraplength=260, justify="left").pack(
            anchor="w", pady=(0, 6)
        )

        self.search_var = tk.StringVar()
        ttk.Entry(left, textvariable=self.search_var).pack(fill="x", pady=(0, 6))
        self.search_var.trace_add("write", lambda *_a: self._refresh_map_list())
        ttk.Label(left, text="Search by map name or ID", foreground="#888888").pack(anchor="w")

        tree_frame = ttk.Frame(left)
        tree_frame.pack(fill="both", expand=True, pady=(6, 0))
        self.map_tree = ttk.Treeview(tree_frame, show="tree", selectmode="browse")
        tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.map_tree.yview)
        self.map_tree.configure(yscrollcommand=tree_scroll.set)
        self.map_tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")
        self.map_tree.tag_configure("edited", background=c.EDITED_ROW_BG, foreground=c.EDITED_ROW_FG)
        self.map_tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True)

        self.current_map_var = tk.StringVar(value="No map selected")
        ttk.Label(right, textvariable=self.current_map_var, font=("Segoe UI", 12, "bold")).pack(
            anchor="w", pady=(0, 8)
        )

        scroll = ScrollableFrame(right)
        scroll.pack(fill="both", expand=True)
        tab = scroll.inner

        for slot in c.MAPTRAP_SLOTS:
            slot_box = ttk.LabelFrame(tab, text=f"Item {slot}", padding=10)
            slot_box.pack(fill="x", pady=(0, 10))
            self.slot_fields[f"X{slot}"] = XmlNumberRow(
                slot_box, f"X{slot}", c.MAPTRAP_XY_MIN, c.MAPTRAP_XY_MAX, "X", "", self._on_field_edited
            )
            self.slot_fields[f"Y{slot}"] = XmlNumberRow(
                slot_box, f"Y{slot}", c.MAPTRAP_XY_MIN, c.MAPTRAP_XY_MAX, "Y", "", self._on_field_edited
            )
            self.slot_fields[f"TrapFlags{slot}"] = ItemFlagFieldPanel(
                slot_box, f"TrapFlags{slot}", "Trap", {"Trap Type": c.MAPTRAP_TRAP_FLAGS}, self._on_field_edited
            )
            self.slot_fields[f"RareItemId{slot}"] = XmlSearchableItemRow(
                slot_box, f"RareItemId{slot}", "Rare Item", self._on_field_edited
            )
            self.slot_fields[f"CommonItemId{slot}"] = XmlSearchableItemRow(
                slot_box, f"CommonItemId{slot}", "Common Item", self._on_field_edited
            )

    # -- data loading -----------------------------------------------------

    def _reference_ready(self) -> bool:
        return bool(self.app.state_data.item_table_records.get("map_trap"))

    # -- map list -----------------------------------------------------------

    def _refresh_map_list(self) -> None:
        query = self.search_var.get().strip().lower()
        self.map_tree.delete(*self.map_tree.get_children())
        records = self.app.state_data.item_table_records.get("map_trap", [])
        edits = self.app.state_data.item_table_edits.get("map_trap", {})
        for record in records:
            display = record.display_name()
            if query and query not in display.lower() and query != str(record.item_id):
                continue
            tags = ["edited"] if edits.get(record.item_id) else []
            self.map_tree.insert("", "end", iid=str(record.item_id), text=display, tags=tags)
        self._update_changes_label()

    def _update_changes_label(self) -> None:
        state = self.app.state_data
        total = len(state.item_table_records.get("map_trap", [])) or (c.MAX_MAPTRAP_ID + 1)
        count = state.edited_maptrap_count()
        self.changes_var.set(f"{count} of {total} maps have pending Treasure Hunter edits.")

    def _on_tree_select(self, _event=None) -> None:
        selection = self.map_tree.selection()
        if selection:
            self._load_map(int(selection[0]))

    # -- loading / committing -------------------------------------------------

    def _load_map(self, map_id: int) -> None:
        self._loading = True
        self.current_map_id = map_id
        state = self.app.state_data

        record = state.maptrap_records_by_id().get(map_id)
        display = record.display_name() if record else f"{map_id:03d} - (no data)"
        self.current_map_var.set(f"Editing: {display}")

        baseline = record.values if record else {}
        edits = state.item_table_edits.get("map_trap", {}).get(map_id, {})

        item_names = _item_id_to_name(state)
        for name, widget in self.slot_fields.items():
            if name.startswith("RareItemId") or name.startswith("CommonItemId"):
                widget.update_choices(item_names)

        for name, widget in self.slot_fields.items():
            default = "None" if name.startswith("TrapFlags") else "0"
            widget.load(edits.get(name, baseline.get(name, default)), name in edits)

        self._loading = False

    def _on_field_edited(self) -> None:
        if self._loading or self.current_map_id is None:
            return
        map_id = self.current_map_id
        edits = self.app.state_data.item_table_edits.setdefault("map_trap", {}).setdefault(map_id, {})
        for name, widget in self.slot_fields.items():
            if widget.included:
                edits[name] = widget.get_value_str()
            elif name in edits:
                del edits[name]
        if not edits:
            self.app.state_data.item_table_edits["map_trap"].pop(map_id, None)
        self._refresh_tree_tag(map_id)
        self._update_changes_label()

    def _refresh_tree_tag(self, map_id: int) -> None:
        edits = self.app.state_data.item_table_edits.get("map_trap", {})
        tags = ["edited"] if edits.get(map_id) else []
        if self.map_tree.exists(str(map_id)):
            self.map_tree.item(str(map_id), tags=tags)

    # -- called by the combined step's on_show() -----------------------------

    def on_show(self) -> None:
        state = self.app.state_data

        if not self._reference_ready():
            self.no_reference_var.set(
                "Treasure Hunter reference data hasn't loaded yet - it downloads by itself when General "
                "Setup opens, so give it a moment. If it failed, General Setup \u2192 Advanced "
                "options \u2192 Reference Tables has a \u201cCheck for updates\u201d button."
            )
            self.map_tree.delete(*self.map_tree.get_children())
            self.changes_var.set("")
            return
        self.no_reference_var.set("")

        self._refresh_map_list()
        if self.current_map_id is None and state.item_table_records.get("map_trap"):
            first_id = state.item_table_records["map_trap"][0].item_id
            if self.map_tree.exists(str(first_id)):
                self.map_tree.selection_set(str(first_id))
