"""
The "Equip Bonus" tab within the combined Edit Game Data step.

ItemEquipBonusData.xml is architecturally just one more item_xml_io.py
TableSpec (see step_items.py/step_treasure_hunter.py) - an ordinary 85-row
reference/diff table, same include/inherit-checkbox convention as every
other Item*Data table, wired into the same ALL_SPECS engine General Setup's
fetch loop and Export's diff-gathering loop already drive generically.

It used to be edited inline, inside Items' own "Stats" tab, right
alongside Additional Data (Weapon/Armor/Shield/Accessory). Promoted out to
its own top-level tab (Zodi's own call - it's a big, semi-independent set
of fields, more like its own system than "one more item stat"), the same
way Job Commands already sits beside Jobs as a sibling top-level tab rather
than nested inside it. Items keeps just its own EquipBonusId pointer field
plus a compact preview and an "Edit this Equip Bonus" jump button - see
step_items.py's Equip Bonus box - mirroring step_editor.py's own Job
Command dropdown/jump-button convention.

Reuses XmlBoolRow from step_items.py and ItemFlagFieldPanel/XmlNumberRow
from step_editor.py (all already fully generic - nothing Equip-Bonus-
specific to change there). Since many items commonly share one Equip Bonus
row, this tab's own list also shows which items currently point at each row
(by EquipBonusId, baseline or pending edit) - a reverse index only this tab
needs, so it's computed locally rather than added to WizardState.
"""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from .. import constants as c
from .step_editor import ItemFlagFieldPanel, ScrollableFrame, XmlNumberRow
from .step_items import XmlBoolRow

# Mirrors step_items.py's own private field-kind tuples (same field order,
# same default-value convention) - duplicated rather than imported since
# both are module-private to their own file.
_STATUS_FLAG_FIELDS = ("InnateStatus", "ImmuneStatus", "StartingStatus")
_USAGE_LIST_LIMIT = 12

_ELEMENT_FLAG_FIELDS = ("AbsorbElements", "NullifyElements", "HalveElements", "WeakElements", "StrongElements")


def _equip_bonus_usage(state) -> dict:
    """
    equip_bonus_id -> list of (item_id, display name) currently pointing at
    it, reading each item's pending EquipBonusId edit if present,
    otherwise its baseline ItemData.xml value. Same reference data Items'
    own tab already loads - nothing new fetched here.
    """
    usage: dict = {}
    item_records = state.item_table_records.get("item", [])
    item_edits = state.item_table_edits.get("item", {})
    for record in item_records:
        edits = item_edits.get(record.item_id, {})
        raw = edits.get("EquipBonusId", record.values.get("EquipBonusId", "0"))
        try:
            equip_bonus_id = int(raw)
        except (TypeError, ValueError):
            equip_bonus_id = 0
        usage.setdefault(equip_bonus_id, []).append((record.item_id, record.display_name()))
    return usage


# Row 0's name comes from ItemEquipBonusData.xml's own comment, which reads
# "Dummy/Empty" - accurate about the table's internals and misleading about
# what it does. Every item defaults to this row, and what it actually means
# is that the item grants no equip bonus at all, so that's what it says.
_ROW_NAME_OVERRIDES = {0: "No bonus"}


def _row_display_name(record) -> str:
    return _ROW_NAME_OVERRIDES.get(record.item_id, record.name)


def _row_label(record, usage_names: list) -> str:
    label = f"{record.item_id:03d}"
    name = _row_display_name(record)
    if name:
        label += f" - {name}"
    if usage_names:
        label += f"  ({len(usage_names)} item{'s' if len(usage_names) != 1 else ''})"
    else:
        label += "  (unused)"
    return label


class EquipBonusPanel(ttk.Frame):
    """The 'Equip Bonus' tab within the combined Edit Game Data step."""

    def __init__(self, parent, app, on_go_to_item=None):
        super().__init__(parent)
        self.app = app
        self._on_go_to_item = on_go_to_item
        self.current_id: int | None = None
        self.fields: dict = {}
        self._usage: dict = {}
        self._loading = False

        self._build_layout()

    # -- layout ---------------------------------------------------------

    def _build_layout(self) -> None:
        ttk.Label(
            self, style="SubHeader.TLabel", wraplength=760, justify="left",
            text=(
                "ItemEquipBonusData.xml (85 rows, Id 0-84) - stat/status/elemental bonuses granted "
                "while an item with a matching EquipBonusId is equipped. Row 0 is the \u201cno bonus\u201d "
                "convention every item defaults to. Several items commonly share one row - editing a "
                "row here affects every item currently pointing at it. Jump here directly from an "
                "item's own Equip Bonus box on the Items tab, or browse rows below."
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
        self.search_var.trace_add("write", lambda *_a: self._refresh_list())
        ttk.Label(left, text="Search by row Id or item name using it", foreground="#888888").pack(anchor="w")

        tree_frame = ttk.Frame(left)
        tree_frame.pack(fill="both", expand=True, pady=(6, 0))
        self.bonus_tree = ttk.Treeview(tree_frame, show="tree", selectmode="browse")
        tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.bonus_tree.yview)
        self.bonus_tree.configure(yscrollcommand=tree_scroll.set)
        self.bonus_tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")
        self.bonus_tree.tag_configure("edited", background=c.EDITED_ROW_BG, foreground=c.EDITED_ROW_FG)
        self.bonus_tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True)

        self.current_var = tk.StringVar(value="No row selected")
        ttk.Label(right, textvariable=self.current_var, font=("Segoe UI", 12, "bold")).pack(
            anchor="w", pady=(0, 4)
        )
        # A read-only tk.Text rather than a ttk.Label, purely so each item
        # name can carry its own click binding. It's configured to render
        # identically - same font, same colour, same wrapping, no border,
        # theme background, no cursor - because the alternative (a row of
        # separate Labels) can't word-wrap and would visibly change the
        # layout as soon as a row is used by more than a couple of items.
        self.usage_text = tk.Text(
            right, height=1, wrap="word", relief="flat", borderwidth=0,
            highlightthickness=0, cursor="", takefocus=0,
            font=tkfont.nametofont("TkDefaultFont"), foreground="#555555",
            background=ttk.Style().lookup("TFrame", "background"),
        )
        self.usage_text.pack(anchor="w", fill="x", pady=(0, 8))
        # The link tag is deliberately styled the SAME as the surrounding
        # text. Zodi's condition on this feature was that the line must not
        # look any different from the plain label it replaced, so the only
        # affordance is on hover: underline plus a hand cursor, which
        # changes nothing at rest. (Colouring it like a link is a one-line
        # change to this tag if that's ever preferred.)
        self.usage_text.tag_configure("link", foreground="#555555")
        self.usage_text.tag_configure("link_hover", underline=True)
        self.usage_text.bind("<Configure>", lambda _e: self._fit_usage_height())
        self.usage_text.configure(state="disabled")

        scroll = ScrollableFrame(right)
        scroll.pack(fill="both", expand=True)
        tab = scroll.inner

        stat_box = ttk.LabelFrame(tab, text="Stat Bonuses", padding=10)
        stat_box.pack(fill="x", pady=(0, 10))
        for name in ("PABonus", "MABonus", "SpeedBonus", "MoveBonus", "JumpBonus"):
            bounds = c.ITEM_XML_NUMERIC_FIELDS[name]
            self.fields[name] = XmlNumberRow(stat_box, name, *bounds, self._on_field_edited)

        status_box = ttk.LabelFrame(tab, text="Status Effects", padding=10)
        status_box.pack(fill="x", pady=(0, 10))
        for name in _STATUS_FLAG_FIELDS:
            self.fields[name] = ItemFlagFieldPanel(
                status_box, name, name, c.STATUS_GROUPS, self._on_field_edited, columns=5
            )

        element_box = ttk.LabelFrame(tab, text="Elemental Affinities", padding=10)
        element_box.pack(fill="x", pady=(0, 10))
        for name in _ELEMENT_FLAG_FIELDS:
            self.fields[name] = ItemFlagFieldPanel(
                element_box, name, name, {"Elements": c.ELEMENT_FLAGS}, self._on_field_edited
            )

        misc_box = ttk.LabelFrame(tab, text="Other", padding=10)
        misc_box.pack(fill="x", pady=(0, 10))
        self.fields["BoostJP"] = XmlBoolRow(misc_box, "BoostJP", "Boost JP", "", self._on_field_edited)

    # -- data loading -----------------------------------------------------

    def _reference_ready(self) -> bool:
        return bool(self.app.state_data.item_table_records.get("item_equip_bonus"))

    # -- list -----------------------------------------------------------


    def _set_usage_text(self, usage_names: list) -> None:
        """Renders "Used by: ..." with each item name clickable through to the Items tab."""
        self.usage_text.configure(state="normal")
        self.usage_text.delete("1.0", "end")
        if not usage_names:
            self.usage_text.insert(
                "end",
                "Not currently used by any item (per each item's own EquipBonusId, including any "
                "pending edits)."
            )
        else:
            # Capped, because row 0 is the default every unmodified item
            # points at - 183 of them - and listing all of those grew this
            # box until it filled the panel and pushed the actual editable
            # fields off-screen. The ones past the cap aren't listed or
            # clickable, which costs nothing: nobody needs to jump to a
            # specific item from the "no bonus" row.
            shown = usage_names[:_USAGE_LIST_LIMIT]
            self.usage_text.insert("end", "Used by: ")
            for index, (item_id, name) in enumerate(shown):
                if index:
                    self.usage_text.insert("end", ", ")
                tag = f"item{item_id}"
                self.usage_text.insert("end", name, ("link", tag))
                if self._on_go_to_item is not None:
                    self.usage_text.tag_bind(
                        tag, "<Button-1>", lambda _e, i=item_id: self._on_go_to_item(i)
                    )
                    self.usage_text.tag_bind(
                        tag, "<Enter>", lambda _e, t=tag: self._hover_link(t, True)
                    )
                    self.usage_text.tag_bind(
                        tag, "<Leave>", lambda _e, t=tag: self._hover_link(t, False)
                    )
            remaining = len(usage_names) - len(shown)
            if remaining > 0:
                self.usage_text.insert("end", f", and {remaining} more")
        self.usage_text.configure(state="disabled")
        self._fit_usage_height()


    def _hover_link(self, tag: str, hovering: bool) -> None:
        self.usage_text.configure(cursor="hand2" if hovering else "")
        ranges = self.usage_text.tag_ranges(tag)
        for start, end in zip(ranges[::2], ranges[1::2]):
            if hovering:
                self.usage_text.tag_add("link_hover", start, end)
            else:
                self.usage_text.tag_remove("link_hover", start, end)

    def _fit_usage_height(self) -> None:
        """Grows the box to exactly the number of wrapped lines it needs."""
        try:
            lines = self.usage_text.count("1.0", "end", "displaylines")[0]
        except (tk.TclError, TypeError, IndexError):
            lines = 1
        self.usage_text.configure(height=max(1, lines))

    def _refresh_list(self) -> None:
        query = self.search_var.get().strip().lower()
        self.bonus_tree.delete(*self.bonus_tree.get_children())
        state = self.app.state_data
        records = state.item_table_records.get("item_equip_bonus", [])
        edits = state.item_table_edits.get("item_equip_bonus", {})
        self._usage = _equip_bonus_usage(state)
        for record in records:
            usage_names = self._usage.get(record.item_id, [])
            label = _row_label(record, usage_names)
            if query:
                haystack = label.lower() + " " + " ".join(n.lower() for _i, n in usage_names)
                if query not in haystack and query != str(record.item_id):
                    continue
            tags = ["edited"] if edits.get(record.item_id) else []
            self.bonus_tree.insert("", "end", iid=str(record.item_id), text=label, tags=tags)
        self._update_changes_label()

    def _update_changes_label(self) -> None:
        state = self.app.state_data
        total = len(state.item_table_records.get("item_equip_bonus", [])) or (c.MAX_ITEM_EQUIP_BONUS_ID + 1)
        count = state.edited_item_table_count("item_equip_bonus")
        self.changes_var.set(f"{count} of {total} Equip Bonus rows edited.")

    def _on_tree_select(self, _event=None) -> None:
        selection = self.bonus_tree.selection()
        if selection:
            self._load_row(int(selection[0]))

    # -- loading / committing -------------------------------------------------

    def _load_row(self, equip_bonus_id: int) -> None:
        self._loading = True
        self.current_id = equip_bonus_id
        state = self.app.state_data

        record = state.item_table_records_by_id("item_equip_bonus").get(equip_bonus_id)
        header = f"Editing: Equip Bonus {equip_bonus_id:03d}"
        if record and _row_display_name(record):
            header += f" - {_row_display_name(record)}"
        self.current_var.set(header)

        self._set_usage_text(self._usage.get(equip_bonus_id, []))

        baseline = record.values if record else {}
        edits = state.item_table_edits.get("item_equip_bonus", {}).get(equip_bonus_id, {})
        for name, widget in self.fields.items():
            if name == "BoostJP":
                default = "false"
            elif name in _STATUS_FLAG_FIELDS or name in _ELEMENT_FLAG_FIELDS:
                default = "None"
            else:
                default = "0"
            widget.load(edits.get(name, baseline.get(name, default)), name in edits)

        self._loading = False

    def _on_field_edited(self) -> None:
        if self._loading or self.current_id is None:
            return
        equip_bonus_id = self.current_id
        edits = self.app.state_data.item_table_edits.setdefault("item_equip_bonus", {}).setdefault(equip_bonus_id, {})
        for name, widget in self.fields.items():
            if widget.included:
                edits[name] = widget.get_value_str()
            elif name in edits:
                del edits[name]
        if not edits:
            self.app.state_data.item_table_edits["item_equip_bonus"].pop(equip_bonus_id, None)
        self._refresh_tree_tag(equip_bonus_id)
        self._update_changes_label()

    def _refresh_tree_tag(self, equip_bonus_id: int) -> None:
        edits = self.app.state_data.item_table_edits.get("item_equip_bonus", {})
        tags = ["edited"] if edits.get(equip_bonus_id) else []
        if self.bonus_tree.exists(str(equip_bonus_id)):
            self.bonus_tree.item(str(equip_bonus_id), tags=tags)

    # -- called by the combined step's on_show() -----------------------------

    def on_show(self) -> None:
        state = self.app.state_data

        if not self._reference_ready():
            self.no_reference_var.set(
                "Equip Bonus reference data hasn't loaded yet - it downloads by itself when General "
                "Setup opens, so give it a moment. If it failed, General Setup \u2192 Advanced "
                "options \u2192 Reference Tables has a \u201cCheck for updates\u201d button."
            )
            self.bonus_tree.delete(*self.bonus_tree.get_children())
            self.changes_var.set("")
            return
        self.no_reference_var.set("")

        self._refresh_list()
        if self.current_id is None and state.item_table_records.get("item_equip_bonus"):
            first_id = state.item_table_records["item_equip_bonus"][0].item_id
            if self.bonus_tree.exists(str(first_id)):
                self.bonus_tree.selection_set(str(first_id))
