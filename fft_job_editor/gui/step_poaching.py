"""
The "Poaching" tab within the combined Edit Game Data step.

Architecturally simplest of the .nxd-based tabs but in an unusual way:
there's no shared companion table at all (nothing like OverrideAbility
ActionData for Abilities or ItemData.xml for Items) - every field, text
AND numeric/economy, lives directly in each language's own PoachItem-xx
table. See constants.py's Poaching section docstring and nxd_data.py's
read_poach_table/write_poach_edits for the full picture, including the
raw "UnknownXX" -> friendly field name translation that happens there.

One tab (not two, unlike Abilities/Items) since there's no shared/XML
side to split off - just Identity, Economy, and an honestly-labeled
"Unconfirmed / Raw Fields" section, matching this project's established
three-confidence-tier convention (see Encounters' OverrideEntryData
fields for the precedent). "Produces / Unlocks Item" gets a searchable
item-name dropdown (reusing this app's own already-loaded Item reference
data), same idea as Encounters' item cross-references.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .. import constants as c
from .. import nxd_data
from .step_abilities import AbilityBoolRow, AbilityNumberRow, AbilityTextRow
from .step_editor import NOTE_STYLE, ScrollableFrame, nxd_missing_data_message
from .step_encounters import SearchableIdRow

RAW_FIELD_NAMES = ["DLCFlags", "Unknown1C", "Unknown1D", "Unknown1E", "Unknown1F", "Unknown20", "Unknown35", "Unknown36"]


def _item_id_to_name(state) -> dict:
    """Same reference data Encounters/Items already use - nothing new fetched here."""
    return {r.item_id: r.display_name() for r in state.item_table_records.get("item", [])}


class PoachItemRefRow(SearchableIdRow):
    """
    SearchableIdRow, but without the "-1 Inherit / Not Set" entry the base
    class always injects - Poaching has no override/inherit concept, and
    -1 isn't a valid ItemData id, so leaving it selectable risks writing a
    broken mod file. "(0) None" is the real empty selection here instead.
    Everything else (search-as-you-type, Copy to all languages) is
    inherited as-is from SearchableIdRow.
    """

    def __init__(self, parent, field_name: str, label: str, id_to_name: dict, on_user_edit, on_copy_all=None):
        seeded = dict(id_to_name)
        seeded.setdefault(0, "(0) None")
        super().__init__(parent, field_name, label, seeded, on_user_edit, on_copy_all=on_copy_all)
        self._strip_inherit_entry()
        self.selected_id = 0
        self._suppress = True
        self.text_var.set(self.id_to_name[0])
        self._suppress = False

    def _strip_inherit_entry(self) -> None:
        self.id_to_name.pop(self.inherit_value, None)
        # The base class builds its inherit label from whichever value
        # that field inherits with (-1 here, since that's the default it
        # was constructed with) - read it off the instance rather than a
        # module constant, which is per-field now.
        self.name_to_id.pop(self.not_set_label, None)
        self._all_names = sorted(self.name_to_id.keys())
        self.combo.configure(values=self._all_names)

    def load(self, value, included: bool) -> None:
        self._suppress = True
        try:
            id_value = int(value)
        except (TypeError, ValueError):
            id_value = 0
        self.selected_id = id_value
        self.text_var.set(self.id_to_name.get(id_value, f"({id_value}) - not in the reference list"))
        self.combo.configure(values=self._all_names)
        self._suppress = False
        self.include_var.set(included)

    def update_choices(self, id_to_name: dict) -> None:
        seeded = dict(id_to_name)
        seeded.setdefault(0, "(0) None")
        super().update_choices(seeded)
        self._strip_inherit_entry()
        if self.selected_id == -1:
            self.selected_id = 0
        self.text_var.set(self.id_to_name.get(self.selected_id, f"({self.selected_id}) Unrecognized"))


class PoachingPanel(ttk.Frame):
    """The 'Poaching' tab within the combined Edit Game Data step."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.current_language = c.NXD_DEFAULT_LANGUAGE
        self.current_key: int | None = None
        self.info_fields: dict = {}
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
                "Poaching (ability 471) lives entirely in .nxd files, with no XML or shared-table "
                "side at all - every field for a carcass, text and numeric alike, lives in that "
                "language's own PoachItem table, so a converted database (General Setup) is needed "
                "before this tab has anything to edit. Non-text fields have a Copy to all languages "
                "button, same as Abilities/Items, since (with one known exception, noted on that "
                "field) they matched across every language in the real data checked."
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
        self.search_var.trace_add("write", lambda *_a: self._refresh_poach_list())
        ttk.Label(left, text="Search by name or ID", foreground="#888888").pack(anchor="w")

        tree_frame = ttk.Frame(left)
        tree_frame.pack(fill="both", expand=True, pady=(6, 0))
        self.poach_tree = ttk.Treeview(tree_frame, show="tree", selectmode="browse")
        tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.poach_tree.yview)
        self.poach_tree.configure(yscrollcommand=tree_scroll.set)
        self.poach_tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")
        self.poach_tree.tag_configure("edited", background=c.EDITED_ROW_BG, foreground=c.EDITED_ROW_FG)
        self.poach_tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True)

        self.current_poach_var = tk.StringVar(value="No poach item selected")
        ttk.Label(right, textvariable=self.current_poach_var, font=("Segoe UI", 12, "bold")).pack(
            anchor="w", pady=(0, 8)
        )

        scroll = ScrollableFrame(right)
        scroll.pack(fill="both", expand=True)
        tab = scroll.inner

        self.info_hint_var = tk.StringVar()
        ttk.Label(
            tab, textvariable=self.info_hint_var, wraplength=700, justify="left", foreground="#777777",
        ).pack(anchor="w", pady=(0, 4))
        self._refresh_info_hint()

        self.info_status_var = tk.StringVar(value="")
        ttk.Label(tab, textvariable=self.info_status_var, foreground="#0a6e0a").pack(anchor="w", pady=(0, 8))

        identity_box = ttk.LabelFrame(tab, text="Identity", padding=10)
        identity_box.pack(fill="x", pady=(0, 10))
        self.info_fields["Name"] = AbilityTextRow(identity_box, "Name", "Name", self._on_info_field_edited)
        self.info_fields["NameSingular"] = AbilityTextRow(
            identity_box, "NameSingular", "Name (Singular)", self._on_info_field_edited
        )
        self.info_fields["NamePlural"] = AbilityTextRow(
            identity_box, "NamePlural", "Name (Plural)", self._on_info_field_edited
        )
        self.info_fields["Name2"] = AbilityTextRow(
            identity_box, "Name2", "Name2 (alternate name)", self._on_info_field_edited
        )
        self.info_fields["Description"] = AbilityTextRow(
            identity_box, "Description", "Description", self._on_info_field_edited, multiline=True
        )

        copy_all_row = ttk.Frame(tab)
        copy_all_row.pack(fill="x", pady=(0, 10))
        ttk.Button(
            copy_all_row, text="Copy all fields to other languages",
            command=self._on_copy_all_fields_clicked,
        ).pack(side="left")
        ttk.Label(
            copy_all_row, style=NOTE_STYLE, wraplength=500, justify="left",
            text=(
                "Copies every non-text field below to every other language at once. Text fields "
                "above (Name/Description/etc.) are never copied - translate those yourself. You "
                "can still adjust any field per language afterward."
            ),
        ).pack(side="left", padx=(10, 0))

        economy_box = ttk.LabelFrame(tab, text="Economy", padding=10)
        economy_box.pack(fill="x", pady=(0, 10))
        label, help_text = c.POACH_BOOL_FIELDS["IsRare"]
        self.info_fields["IsRare"] = AbilityBoolRow(
            economy_box, "IsRare", label, help_text, self._on_info_field_edited,
        )
        for name in ("Cost", "SellPrice", "IconId"):
            self.info_fields[name] = AbilityNumberRow(
                economy_box, name, c.POACH_NUMERIC_FIELDS[name], self._on_info_field_edited,
            )
        self.info_fields["ProducedItemId"] = PoachItemRefRow(
            economy_box, "ProducedItemId", c.POACH_NUMERIC_FIELDS["ProducedItemId"][2], {},
            self._on_info_field_edited,
        )
        if c.POACH_NUMERIC_FIELDS["ProducedItemId"][3]:
            ttk.Label(
                economy_box, text=c.POACH_NUMERIC_FIELDS["ProducedItemId"][3],
                style=NOTE_STYLE, wraplength=600,
            ).pack(anchor="w", padx=(24, 0), pady=(0, 2))

        raw_box = ttk.LabelFrame(tab, text="Unconfirmed / Raw Fields", padding=10)
        raw_box.pack(fill="x", pady=(0, 10))
        ttk.Label(
            raw_box, wraplength=680, justify="left", style=NOTE_STYLE,
            text=(
                "FF16Tools couldn't name these fields (no known struct exists for PoachItem the way "
                "ItemData.xml/ITEM_COMMON_DATA.cs does for Items) - shown honestly as raw values "
                "rather than guessed at. See each field's own note for what's actually been checked."
            ),
        ).pack(anchor="w", pady=(0, 6))
        for name in RAW_FIELD_NAMES:
            self.info_fields[name] = AbilityNumberRow(
                raw_box, name, c.POACH_NUMERIC_FIELDS[name], self._on_info_field_edited,
            )

        self.info_fields["Comment"] = AbilityTextRow(
            tab, "Comment", "Comment (FF16Tools' own note, not real game data)", self._on_info_field_edited
        )

    def _refresh_info_hint(self) -> None:
        label = c.NXD_LANGUAGE_LABELS[self.current_language]
        self.info_hint_var.set(
            f"Editing {label} text - stored in its own PoachItem-{self.current_language} table. Use "
            "the \u201cCopy all fields to other languages\u201d button below to copy every non-text "
            "field at once instead of repeating each one by hand."
        )

    # -- data loading -----------------------------------------------------

    def _ensure_data_loaded(self, language: str) -> bool:
        state = self.app.state_data
        if state.nxd_sqlite_path is None:
            return False
        try:
            if language not in state.poach_records:
                state.poach_records[language] = nxd_data.read_poach_table(state.nxd_sqlite_path, language)
        except Exception as exc:  # noqa: BLE001 - surface any read failure honestly
            self.no_data_var.set(nxd_missing_data_message(state, "Poaching data", exc))
            return False
        return True

    # -- poach list -------------------------------------------------------

    def _refresh_poach_list(self) -> None:
        query = self.search_var.get().strip().lower()
        self.poach_tree.delete(*self.poach_tree.get_children())
        records = self.app.state_data.poach_records.get(self.current_language, [])
        lang_edits = self.app.state_data.poach_edits.get(self.current_language, {})
        for record in records:
            if query and query not in record.display_name.lower() and query != str(record.key):
                continue
            tags = ["edited"] if lang_edits.get(record.key) else []
            self.poach_tree.insert("", "end", iid=str(record.key), text=record.display_name, tags=tags)
        self._update_changes_label()

    def _update_changes_label(self) -> None:
        state = self.app.state_data
        lang_label = c.NXD_LANGUAGE_LABELS[self.current_language]
        total = len(state.poach_records.get(self.current_language, [])) or 96
        lang_count = state.edited_poach_count(self.current_language)
        self.changes_var.set(f"{lang_count} of {total} poach items edited in {lang_label}.")

    def _on_tree_select(self, _event=None) -> None:
        selection = self.poach_tree.selection()
        if selection:
            self._load_poach_item(int(selection[0]))

    def _on_language_changed(self, _event=None) -> None:
        lang = self._label_to_lang.get(self.language_var.get(), self.current_language)
        if lang == self.current_language:
            return
        self.current_language = lang
        self._refresh_info_hint()
        if self._ensure_data_loaded(lang):
            self.no_data_var.set("")
            self._refresh_poach_list()
            if self.current_key is not None:
                self._load_poach_item(self.current_key)
            elif self.app.state_data.poach_records.get(lang):
                first_key = self.app.state_data.poach_records[lang][0].key
                if self.poach_tree.exists(str(first_key)):
                    self.poach_tree.selection_set(str(first_key))

    # -- loading / committing -------------------------------------------------

    def _load_poach_item(self, key: int) -> None:
        self._loading = True
        self.current_key = key
        state = self.app.state_data
        records = state.poach_records.get(self.current_language, [])
        record = next((r for r in records if r.key == key), None)

        display = record.display_name if record else f"{key:03d} - (no data for this language)"
        self.current_poach_var.set(f"Editing: {display}")

        baseline = record.values if record else {}
        lang_edits = state.poach_edits.get(self.current_language, {}).get(key, {})

        item_names = _item_id_to_name(state)
        self.info_fields["ProducedItemId"].update_choices(item_names)

        for name, widget in self.info_fields.items():
            if name in lang_edits:
                widget.load(lang_edits[name], True)
            else:
                widget.load(baseline.get(name), False)

        self._loading = False

    def _on_info_field_edited(self) -> None:
        if self._loading or self.current_key is None:
            return
        key = self.current_key
        edits = self.app.state_data.poach_edits.setdefault(self.current_language, {}).setdefault(key, {})
        for name, widget in self.info_fields.items():
            if widget.included:
                edits[name] = widget.get_value()
            elif name in edits:
                del edits[name]
        if not edits:
            self.app.state_data.poach_edits[self.current_language].pop(key, None)
        self._refresh_tree_tag(key)
        self._update_changes_label()

    def _refresh_tree_tag(self, key: int) -> None:
        state = self.app.state_data
        lang_edits = state.poach_edits.get(self.current_language, {})
        tags = ["edited"] if lang_edits.get(key) else []
        if self.poach_tree.exists(str(key)):
            self.poach_tree.item(str(key), tags=tags)

    # -- copy to all languages -------------------------------------------------

    def _on_copy_all_fields_clicked(self) -> None:
        if self.current_key is None:
            return
        widgets = [w for w in self.info_fields.values() if hasattr(w, "copy_fields")]
        if not widgets:
            return
        for widget in widgets:
            widget.include_var.set(True)
        self._on_info_field_edited()  # also commit/include everything for the language currently being viewed

        key = self.current_key
        state = self.app.state_data
        other_langs = [lang for lang in c.NXD_LANGUAGES if lang != self.current_language]
        for lang in other_langs:
            lang_edits = state.poach_edits.setdefault(lang, {}).setdefault(key, {})
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
            self.no_data_var.set(
                "No poaching data loaded yet. Go to General Setup, tick \u201cGame data\u201d, and press "
                "\u201cUnpack and Prepare Game Files\u201d. (Already have a converted "
                "fft_data.sqlite? Advanced options there can open it directly.)"
            )
            self.poach_tree.delete(*self.poach_tree.get_children())
            self.changes_var.set("")
            return

        if state.nxd_sqlite_path != self._applied_sqlite_path:
            self._applied_sqlite_path = state.nxd_sqlite_path
            state.poach_records = {}
            self.current_key = None

        if not self._ensure_data_loaded(self.current_language):
            return
        self.no_data_var.set("")
        self._refresh_poach_list()
        if self.current_key is None and self.app.state_data.poach_records.get(self.current_language):
            first_key = self.app.state_data.poach_records[self.current_language][0].key
            if self.poach_tree.exists(str(first_key)):
                self.poach_tree.selection_set(str(first_key))
