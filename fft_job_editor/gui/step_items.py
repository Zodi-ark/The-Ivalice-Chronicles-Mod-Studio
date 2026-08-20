"""
The "Items" tab within the combined Edit Game Data step.

Items are architecturally the opposite split from Abilities: the real stats
(ATK, DEF, evasion, elemental affinities, shop availability, etc.) live in
six ordinary reference/diff XML tables - ItemData.xml (base row, shared
across every language) plus five "Additional Data" tables it links into via
TypeFlags -> AdditionalDataId (item_xml_io.py) - exactly the same
include/inherit-checkbox diff convention as JobData.xml/JobCommandData.xml.
Only the per-language item name/description text (Name, Description, etc.)
lives in a binary .nxd table (Item-xx, nxd_data.py) - the opposite of
Abilities, where the flags/stats were binary and only the name text was XML-
adjacent. The nxd side reuses the *exact* AbilityTextRow/AbilityNumberRow/
AbilityBoolRow widgets from step_abilities.py - those were already written
generically (they take field name/label/bounds directly, nothing Ability-
specific), so there was nothing Item-specific to add there.

TypeFlags determines which of the five Additional Data tables
AdditionalDataId points into (Headgear and Armor both use ItemArmorData -
identical HPBonus/MPBonus shape despite being distinct TypeFlags). That
section of the Stats tab rebuilds its widgets whenever TypeFlags or
AdditionalDataId changes, since which fields even apply depends on those two
values.

ItemEquipBonusData.xml's own fields (following EquipBonusId) used to live
inline here too, but moved out to their own top-level "Equip Bonus" tab
(step_equip_bonus.py) - it's a big, semi-independent system (14 fields,
several shared across many items), more like Job Commands sitting beside
Jobs than "one more item stat". This tab keeps just the EquipBonusId
pointer itself, plus a compact read-only preview and an "Edit this Equip
Bonus" jump button - the same dropdown-preview-plus-jump-button convention
step_editor.py's JobCommandDropdownRow already established for Jobs ->
Job Commands.

A third inner tab (Textures) offers the item's own two icon files - "art"
(equip_item) and "sprite" (equip_item_s) - as an inline quality-of-life
shortcut, reusing step_textures.py's InlineTextureSlot widget and writing
into the exact same app.state_data.texture_edits dict the main Textures
tab uses, so nothing about Export's texture pipeline needed to change.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .. import constants as c
from .. import item_xml_io
from .. import nxd_data
from .. import texture_data as td
from .step_abilities import AbilityBoolRow, AbilityNumberRow, AbilityTextRow
from .step_editor import NOTE_STYLE, UNKNOWN_ROW_STYLE, is_unknown_field, ItemFlagFieldPanel, ScrollableFrame, XmlDropdownRow, XmlNumberRow, nxd_missing_data_message
from .step_textures import InlineTextureSlot

NXD_NUMBER_FIELD_NAMES = [
    "DLCFlags", "Unknown18", "Unknown19", "Unknown1A", "Unknown1B",
    "UiStatusEffectId", "UiItemCategoryId", "SortOrder", "Unknown2C",
]


# =============================================================================
# Widgets for the XML-diff-style tables (item_xml_io) - string-valued,
# mirrors step_editor.py's NumericFieldRow/FlagFieldPanel but generalized to
# take bounds/choices directly instead of looking them up from a Job-Data-
# specific global dict, so nothing there needed to change. XmlNumberRow/
# XmlDropdownRow/ItemFlagFieldPanel all now live in step_editor.py (imported
# above) rather than here - they're used by Abilities' own AbilityData.xml/
# Effect/Unit Animations sub-tabs too, and step_items already imports
# Ability*Row widgets from step_abilities.py, so the reverse import would be
# circular. XmlBoolRow below stays here for now since nothing outside Items/
# Equip Bonus needs it yet.
# =============================================================================

class XmlBoolRow:
    """[include] label [checkbox] - a "true"/"false" Item*Data.xml field (just BoostJP, currently)."""

    def __init__(self, parent, field_name: str, label: str, help_text: str, on_user_edit):
        self.field_name = field_name
        self._on_user_edit = on_user_edit
        self._suppress = False

        self.include_var = tk.BooleanVar(value=False)
        self.bool_var = tk.BooleanVar(value=False)

        row = ttk.Frame(parent, style=UNKNOWN_ROW_STYLE if is_unknown_field(field_name, label) else "")
        row.pack(fill="x", pady=2)
        ttk.Checkbutton(row, variable=self.include_var, command=self._fire_edit).pack(side="left")
        ttk.Label(row, text=label, width=24, anchor="w").pack(side="left")
        ttk.Checkbutton(row, variable=self.bool_var, command=self._on_bool_changed).pack(side="left", padx=(4, 10))
        if help_text:
            ttk.Label(parent, text=help_text, style=NOTE_STYLE, wraplength=600).pack(
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

    def load(self, value_str, included: bool) -> None:
        self._suppress = True
        self.bool_var.set(str(value_str).strip().lower() == "true")
        self._suppress = False
        self.include_var.set(included)

    def get_value_str(self) -> str:
        return "true" if self.bool_var.get() else "false"

    @property
    def included(self) -> bool:
        return self.include_var.get()


# =============================================================================
# Main panel
# =============================================================================

# TypeFlags value -> (item_table_edits key, MAX_ITEM_*_ID, field order, display label)
_LINKED_TABLE_INFO = {
    "weapon": ("item_weapon", c.MAX_ITEM_WEAPON_ID, c.ITEM_WEAPON_FIELD_ORDER, "Weapon Data"),
    "shield": ("item_shield", c.MAX_ITEM_SHIELD_ID, c.ITEM_SHIELD_FIELD_ORDER, "Shield Data"),
    "armor": ("item_armor", c.MAX_ITEM_ARMOR_ID, c.ITEM_ARMOR_FIELD_ORDER, "Armor Data"),
    "accessory": ("item_accessory", c.MAX_ITEM_ACCESSORY_ID, c.ITEM_ACCESSORY_FIELD_ORDER, "Accessory Data"),
}

_STATUS_FLAG_FIELDS = ("InnateStatus", "ImmuneStatus", "StartingStatus")
_ELEMENT_FLAG_FIELDS = ("AbsorbElements", "NullifyElements", "HalveElements", "WeakElements", "StrongElements")


class ItemsPanel(ttk.Frame):
    """The 'Items' tab within the combined Edit Game Data step."""

    def __init__(self, parent, app, on_go_to_equip_bonus=None, on_go_to_textures=None):
        super().__init__(parent)
        self.app = app
        self._on_go_to_equip_bonus = on_go_to_equip_bonus
        self._on_go_to_textures = on_go_to_textures
        self.current_language = c.NXD_DEFAULT_LANGUAGE
        self.current_item_id = None
        self.info_fields = {}
        self.base_fields = {}
        self.linked_fields = {}
        self._linked_table_key = None   # "item_weapon"/"item_shield"/"item_armor"/"item_accessory"
        self._linked_row_id = None
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
                "Item stats live in the mod loader's own XML tables (ready automatically once "
                "General Setup's Reference Tables have loaded) - names/descriptions are "
                "per-language and need a converted Ability & Item Data database (General Setup), "
                "same as Abilities. Pick an item, then edit its name/description on one tab and "
                "its stats - shared across every language - on the other."
            ),
        ).pack(anchor="w", pady=(4, 8))

        self.no_reference_var = tk.StringVar(value="")
        ttk.Label(
            self, textvariable=self.no_reference_var, foreground="#b00020", wraplength=760, justify="left"
        ).pack(anchor="w", pady=(0, 4))

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
        self.search_var.trace_add("write", lambda *_a: self._refresh_item_list())
        ttk.Label(left, text="Search by name or ID", foreground="#888888").pack(anchor="w")

        tree_frame = ttk.Frame(left)
        tree_frame.pack(fill="both", expand=True, pady=(6, 0))
        self.item_tree = ttk.Treeview(tree_frame, show="tree", selectmode="browse")
        tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.item_tree.yview)
        self.item_tree.configure(yscrollcommand=tree_scroll.set)
        self.item_tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")
        self.item_tree.tag_configure("edited", background=c.EDITED_ROW_BG, foreground=c.EDITED_ROW_FG)
        self.item_tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True)

        self.current_item_var = tk.StringVar(value="No item selected")
        ttk.Label(right, textvariable=self.current_item_var, font=("Segoe UI", 12, "bold")).pack(
            anchor="w", pady=(0, 8)
        )

        self.notebook = ttk.Notebook(right)
        self.notebook.pack(fill="both", expand=True)

        self._build_info_tab()
        self._build_stats_tab()
        self._build_textures_tab()

    def _add_scrollable_tab(self, title: str) -> ttk.Frame:
        scroll = ScrollableFrame(self.notebook)
        self.notebook.add(scroll, text=title)
        return scroll.inner

    # -- Item Info (per-language, nxd) tab -------------------------------------

    def _build_info_tab(self) -> None:
        tab = self._add_scrollable_tab("Item Info (this language)")
        self._info_tab_widget = self.notebook.tabs()[-1]

        self.info_hint_var = tk.StringVar()
        ttk.Label(
            tab, textvariable=self.info_hint_var, wraplength=700, justify="left", foreground="#777777",
        ).pack(anchor="w", pady=(0, 4))
        self._refresh_info_hint()

        self.info_status_var = tk.StringVar(value="")
        ttk.Label(tab, textvariable=self.info_status_var, foreground="#0a6e0a").pack(anchor="w", pady=(0, 8))

        self.info_fields["Name"] = AbilityTextRow(tab, "Name", "Name", self._on_info_field_edited)
        self.info_fields["NameSingular"] = AbilityTextRow(
            tab, "NameSingular", "Name (Singular)", self._on_info_field_edited
        )
        self.info_fields["NamePlural"] = AbilityTextRow(
            tab, "NamePlural", "Name (Plural)", self._on_info_field_edited
        )
        self.info_fields["Description"] = AbilityTextRow(
            tab, "Description", "Description", self._on_info_field_edited, multiline=True
        )
        self.info_fields["Name2"] = AbilityTextRow(
            tab, "Name2", "Name2 (alternate name)", self._on_info_field_edited
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
                "above (Name/Description/etc.) are never copied - translate those yourself. You "
                "can still adjust any field per language afterward."
            ),
        ).pack(side="left", padx=(10, 0))

        for name in NXD_NUMBER_FIELD_NAMES:
            self.info_fields[name] = AbilityNumberRow(
                tab, name, c.ITEM_NUMERIC_FIELDS[name], self._on_info_field_edited,
            )
        label, help_text = c.ITEM_BOOL_FIELDS["IsRandomDamage"]
        self.info_fields["IsRandomDamage"] = AbilityBoolRow(
            tab, "IsRandomDamage", label, help_text, self._on_info_field_edited,
        )
        self.info_fields["Comment"] = AbilityTextRow(
            tab, "Comment", "Comment (FF16Tools' own note, not real game data)", self._on_info_field_edited
        )

    def _refresh_info_hint(self) -> None:
        label = c.NXD_LANGUAGE_LABELS[self.current_language]
        self.info_hint_var.set(
            f"Editing {label} text - stored in its own Item-{self.current_language} table. Use the "
            "\u201cCopy all fields to other languages\u201d button below to copy every non-text field "
            "at once instead of repeating each one by hand."
        )
        self.notebook.tab(self._info_tab_widget, text=f"Item Info ({label})")

    # -- Stats (shared, XML) tab -----------------------------------------------

    def _build_stats_tab(self) -> None:
        tab = self._add_scrollable_tab("Stats")
        ttk.Label(
            tab, wraplength=700, justify="left", style=NOTE_STYLE,
            text=(
                "Everything below lives in ItemData.xml and the tables it links into - shared "
                "across every language. Additional Data below follows this item's own Type, "
                "updating live as you edit it. Several items commonly point at the same Additional "
                "Data row, so editing a shared row affects every item using it. Equip Bonus's own "
                "fields moved to their own top-level tab - see the box below to jump there."
            ),
        ).pack(anchor="w", pady=(0, 10))

        base_box = ttk.LabelFrame(tab, text="Base Item Data", padding=10)
        base_box.pack(fill="x", pady=(0, 10))
        for name in ("Palette", "SpriteID", "RequiredLevel"):
            bounds = c.ITEM_XML_NUMERIC_FIELDS[name]
            self.base_fields[name] = XmlNumberRow(base_box, name, *bounds, self._on_base_field_edited)
        self.base_fields["TypeFlags"] = ItemFlagFieldPanel(
            base_box, "TypeFlags", "Type", {"Type": c.ITEM_TYPE_FLAGS}, self._on_type_flags_edited
        )
        self.base_fields["ItemCategory"] = XmlDropdownRow(
            base_box, "ItemCategory", c.ITEM_CATEGORIES, "Item Category", self._on_base_field_edited, width=18
        )
        price_bounds = c.ITEM_XML_NUMERIC_FIELDS["Price"]
        self.base_fields["Price"] = XmlNumberRow(base_box, "Price", *price_bounds, self._on_base_field_edited)
        self.base_fields["ShopAvailability"] = XmlDropdownRow(
            base_box, "ShopAvailability", c.ITEM_SHOP_AVAILABILITY, "Shop Availability",
            self._on_base_field_edited, width=22,
        )
        for name in ("Unused_0x06", "Unused_0x0B"):
            bounds = c.ITEM_XML_NUMERIC_FIELDS[name]
            self.base_fields[name] = XmlNumberRow(base_box, name, *bounds, self._on_base_field_edited)

        self.linked_box = ttk.LabelFrame(tab, text="Additional Data", padding=10)
        self.linked_box.pack(fill="x", pady=(0, 10))
        add_id_bounds = c.ITEM_XML_NUMERIC_FIELDS["AdditionalDataId"]
        self.base_fields["AdditionalDataId"] = XmlNumberRow(
            self.linked_box, "AdditionalDataId", *add_id_bounds, self._on_additional_data_id_edited
        )
        self.linked_content_frame = ttk.Frame(self.linked_box)
        self.linked_content_frame.pack(fill="x", pady=(6, 0))

        self.equip_bonus_box = ttk.LabelFrame(tab, text="Equip Bonus", padding=10)
        self.equip_bonus_box.pack(fill="x", pady=(0, 10))
        equip_id_bounds = c.ITEM_XML_NUMERIC_FIELDS["EquipBonusId"]
        self.base_fields["EquipBonusId"] = XmlNumberRow(
            self.equip_bonus_box, "EquipBonusId", *equip_id_bounds, self._on_equip_bonus_id_edited
        )
        self.equip_bonus_info_var = tk.StringVar(value="")
        ttk.Label(
            self.equip_bonus_box, textvariable=self.equip_bonus_info_var,
            font=("Segoe UI", 9, "italic"), foreground="#666666", wraplength=650, justify="left",
        ).pack(anchor="w", pady=(4, 4))
        self.equip_bonus_goto_button = ttk.Button(
            self.equip_bonus_box, text="Edit this Equip Bonus \u2192",
            command=self._go_to_equip_bonus_clicked, state="disabled",
        )
        self.equip_bonus_goto_button.pack(anchor="w")
        self.equip_bonus_preview_var = tk.StringVar(value="")
        ttk.Label(
            self.equip_bonus_box, textvariable=self.equip_bonus_preview_var, foreground="#555555",
            wraplength=650, justify="left",
        ).pack(anchor="w", pady=(6, 0))

        shops_box = ttk.LabelFrame(tab, text="Shop Availability", padding=10)
        shops_box.pack(fill="x", pady=(0, 10))
        self.shops_field = ItemFlagFieldPanel(
            shops_box, "Shops", "Sold in", {"Towns": c.ITEM_SHOPS}, self._on_shops_field_edited
        )

    # -- Textures (icon shortcuts) tab -----------------------------------------

    def _build_textures_tab(self) -> None:
        tab = self._add_scrollable_tab("Textures")
        ttk.Label(
            tab, wraplength=700, justify="left", foreground="#777777",
            text=(
                "Quality-of-life shortcut to this item's own two icon files, so there's no need to "
                "hunt for them in the main Textures tab. \u201cArt\u201d is the larger icon (menus/shops); "
                "\u201cSprite\u201d is the small inventory/battle icon. Both are staged the exact same way "
                "as the main Textures tab - see there for anything not shown here (Export as PNG, "
                "browsing every other texture in the game, etc.)."
            ),
        ).pack(anchor="w", pady=(0, 10))

        slots_row = ttk.Frame(tab)
        slots_row.pack(fill="x")
        self.art_texture_slot = InlineTextureSlot(
            slots_row, self.app, "Art Texture (equip_item)", on_view_in_textures=self._go_to_textures_clicked,
            on_edit_changed=self._on_texture_edit_changed,
        )
        self.art_texture_slot.pack(fill="x", pady=(0, 10))
        self.sprite_texture_slot = InlineTextureSlot(
            slots_row, self.app, "Sprite Texture (equip_item_s)", on_view_in_textures=self._go_to_textures_clicked,
            on_edit_changed=self._on_texture_edit_changed,
        )
        self.sprite_texture_slot.pack(fill="x")

    # -- dynamic Additional Data / Equip Bonus sections ------------------------

    def _current_type_flags_and_additional_id(self):
        type_flags = item_xml_io.parse_flag_value(self.base_fields["TypeFlags"].get_value_str())
        try:
            additional_id = int(self.base_fields["AdditionalDataId"].get_value_str())
        except (TypeError, ValueError):
            additional_id = 0
        return type_flags, additional_id

    def _current_equip_bonus_id(self) -> int:
        try:
            return int(self.base_fields["EquipBonusId"].get_value_str())
        except (TypeError, ValueError):
            return 0

    def _rebuild_linked_section(self) -> None:
        for child in self.linked_content_frame.winfo_children():
            child.destroy()
        self.linked_fields = {}

        type_flags, additional_id = self._current_type_flags_and_additional_id()
        base_type = next(
            (t for t in ("weapon", "shield", "headgear", "armor", "accessory") if t.capitalize() in type_flags),
            None,
        )
        # Headgear and Armor share ItemArmorData.
        target = "armor" if base_type == "headgear" else base_type
        self._linked_row_id = additional_id

        if target is None:
            self._linked_table_key = None
            ttk.Label(
                self.linked_content_frame, style=NOTE_STYLE, wraplength=650, justify="left",
                text=(
                    "This item has no linked Weapon/Armor/Shield/Accessory data (its Type doesn't "
                    "include Weapon, Shield, Headgear, Armor, or Accessory)."
                ),
            ).pack(anchor="w")
            return

        table_key, max_id, field_order, label = _LINKED_TABLE_INFO[target]
        self._linked_table_key = table_key

        if additional_id > max_id:
            ttk.Label(
                self.linked_content_frame, foreground="#b00020", wraplength=650, justify="left",
                text=(
                    f"Additional Data Id {additional_id} is out of range for {label} (0-{max_id}) - "
                    "fix the Additional Data Id above."
                ),
            ).pack(anchor="w")
            return

        ttk.Label(
            self.linked_content_frame, text=f"{label}, row {additional_id}",
            font=("Segoe UI", 9, "italic"), foreground="#666666",
        ).pack(anchor="w", pady=(0, 6))

        row_record = self.app.state_data.item_table_records_by_id(table_key).get(additional_id)
        row_baseline = row_record.values if row_record else {}
        row_edits = self.app.state_data.item_table_edits.get(table_key, {}).get(additional_id, {})

        for name in field_order:
            if name == "AttackFlags":
                widget = ItemFlagFieldPanel(
                    self.linked_content_frame, name, "Attack Flags", {"Attack": c.ITEM_ATTACK_FLAGS},
                    self._on_linked_field_edited,
                )
                default = "None"
            elif name == "Elements":
                widget = ItemFlagFieldPanel(
                    self.linked_content_frame, name, "Elements", {"Elements": c.ELEMENT_FLAGS},
                    self._on_linked_field_edited,
                )
                default = "None"
            else:
                bounds = c.ITEM_XML_NUMERIC_FIELDS[name]
                widget = XmlNumberRow(self.linked_content_frame, name, *bounds, self._on_linked_field_edited)
                default = "0"
            widget.load(row_edits.get(name, row_baseline.get(name, default)), name in row_edits)
            self.linked_fields[name] = widget

    def _equip_bonus_preview_text(self, equip_bonus_id: int) -> str:
        """A read-only one-glance summary of a row's own fields - same idea as JobCommandDropdownRow's ability preview."""
        state = self.app.state_data
        row_record = state.item_table_records_by_id("item_equip_bonus").get(equip_bonus_id)
        baseline = row_record.values if row_record else {}
        edits = state.item_table_edits.get("item_equip_bonus", {}).get(equip_bonus_id, {})

        def value_of(name: str, default: str) -> str:
            return edits.get(name, baseline.get(name, default))

        stats = []
        for name, label in (
            ("PABonus", "PA"), ("MABonus", "MA"), ("SpeedBonus", "Speed"),
            ("MoveBonus", "Move"), ("JumpBonus", "Jump"),
        ):
            try:
                v = int(value_of(name, "0"))
            except (TypeError, ValueError):
                v = 0
            if v:
                stats.append(f"{label} +{v}")

        parts = []
        if stats:
            parts.append(", ".join(stats))
        for name, label in (
            ("InnateStatus", "Innate"), ("ImmuneStatus", "Immune"), ("StartingStatus", "Starts with"),
            ("AbsorbElements", "Absorbs"), ("NullifyElements", "Nullifies"), ("HalveElements", "Halves"),
            ("WeakElements", "Weak to"), ("StrongElements", "Strong vs"),
        ):
            flags = item_xml_io.parse_flag_value(value_of(name, "None"))
            if flags:
                parts.append(f"{label}: {', '.join(sorted(flags))}")
        if value_of("BoostJP", "false").strip().lower() == "true":
            parts.append("Boosts JP gain")

        return "; ".join(parts) if parts else "No bonuses set on this row."

    def _refresh_equip_bonus_preview(self) -> None:
        equip_bonus_id = self._current_equip_bonus_id()

        if equip_bonus_id > c.MAX_ITEM_EQUIP_BONUS_ID:
            self.equip_bonus_info_var.set(
                f"Id {equip_bonus_id} is out of range (0-{c.MAX_ITEM_EQUIP_BONUS_ID}) - fix the Equip "
                "Bonus Id above."
            )
            self.equip_bonus_preview_var.set("")
            self.equip_bonus_goto_button.configure(state="disabled")
            return

        self.equip_bonus_info_var.set(
            f"ItemEquipBonusData.xml, row {equip_bonus_id} (Id 0 conventionally means \"no bonus\")."
        )
        self.equip_bonus_preview_var.set(self._equip_bonus_preview_text(equip_bonus_id))
        self.equip_bonus_goto_button.configure(state="normal")

    # -- data loading -----------------------------------------------------

    def _reference_tables_ready(self) -> bool:
        return bool(self.app.state_data.item_table_records.get("item"))

    def _ensure_nxd_loaded(self, language: str) -> bool:
        state = self.app.state_data
        if state.nxd_sqlite_path is None:
            return False
        try:
            if language not in state.item_records:
                state.item_records[language] = nxd_data.read_item_table(state.nxd_sqlite_path, language)
        except Exception as exc:  # noqa: BLE001 - surface any read failure honestly
            self.no_data_var.set(nxd_missing_data_message(state, "Item name/description data", exc))
            return False
        return True

    # -- item list -------------------------------------------------------

    def _item_display_name(self, item_id: int) -> str:
        nxd_records = self.app.state_data.item_records.get(self.current_language, [])
        nxd_by_id = {r.key: r for r in nxd_records}
        if item_id in nxd_by_id:
            return nxd_by_id[item_id].display_name
        xml_by_id = self.app.state_data.item_table_records_by_id("item")
        if item_id in xml_by_id:
            return xml_by_id[item_id].display_name()
        return f"{item_id:03d} - (no data)"

    def _item_icon_texture_edited(self, item_id: int) -> bool:
        edits = self.app.state_data.texture_edits
        return (
            td.item_art_texture_path(item_id) in edits
            or td.item_sprite_texture_path(item_id) in edits
        )

    def _edited_item_icon_texture_count(self) -> int:
        records = self.app.state_data.item_table_records.get("item", [])
        return sum(1 for r in records if self._item_icon_texture_edited(r.item_id))

    def _refresh_item_list(self) -> None:
        query = self.search_var.get().strip().lower()
        self.item_tree.delete(*self.item_tree.get_children())
        xml_records = self.app.state_data.item_table_records.get("item", [])
        lang_edits = self.app.state_data.item_edits.get(self.current_language, {})
        base_edits = self.app.state_data.item_table_edits.get("item", {})
        shops_edits = self.app.state_data.item_table_edits.get("item_shops", {})
        for xr in xml_records:
            display = self._item_display_name(xr.item_id)
            if query and query not in display.lower() and query != str(xr.item_id):
                continue
            tags = []
            if (
                lang_edits.get(xr.item_id) or base_edits.get(xr.item_id) or shops_edits.get(xr.item_id)
                or self._item_icon_texture_edited(xr.item_id)
            ):
                tags.append("edited")
            self.item_tree.insert("", "end", iid=str(xr.item_id), text=display, tags=tags)
        self._update_changes_label()

    def _update_changes_label(self) -> None:
        state = self.app.state_data
        lang_label = c.NXD_LANGUAGE_LABELS[self.current_language]
        total = len(state.item_table_records.get("item", [])) or (c.MAX_ITEM_ID + 1)
        text_count = state.edited_item_text_count(self.current_language)
        base_count = state.edited_item_table_count("item")
        weapon_count = state.edited_item_table_count("item_weapon")
        armor_count = state.edited_item_table_count("item_armor")
        shield_count = state.edited_item_table_count("item_shield")
        accessory_count = state.edited_item_table_count("item_accessory")
        shops_count = state.edited_item_table_count("item_shops")
        icon_texture_count = self._edited_item_icon_texture_count()
        self.changes_var.set(
            f"{text_count} of {total} items edited in {lang_label}.\n"
            f"{base_count} base stat edits.\n"
            f"{weapon_count} weapon / {armor_count} armor / {shield_count} shield / "
            f"{accessory_count} accessory edits.\n"
            f"{shops_count} shop-availability edits, {icon_texture_count} item(s) with icon/sprite "
            "replacements."
        )

    def _on_tree_select(self, _event=None) -> None:
        selection = self.item_tree.selection()
        if selection:
            self._load_item(int(selection[0]))

    def _on_language_changed(self, _event=None) -> None:
        lang = self._label_to_lang.get(self.language_var.get(), self.current_language)
        if lang == self.current_language:
            return
        self.current_language = lang
        self._refresh_info_hint()
        self._ensure_nxd_loaded(lang)
        self._refresh_item_list()
        if self.current_item_id is not None:
            self._load_item(self.current_item_id)
        elif self.app.state_data.item_table_records.get("item"):
            first_id = self.app.state_data.item_table_records["item"][0].item_id
            if self.item_tree.exists(str(first_id)):
                self.item_tree.selection_set(str(first_id))

    # -- loading / committing -------------------------------------------------

    def _load_item(self, item_id: int) -> None:
        self._loading = True
        self.current_item_id = item_id
        state = self.app.state_data

        self.current_item_var.set(f"Editing: {self._item_display_name(item_id)}")

        # -- Item Info (nxd) --
        nxd_by_id = {r.key: r for r in state.item_records.get(self.current_language, [])}
        nr = nxd_by_id.get(item_id)
        baseline = nr.values if nr else {}
        lang_edits = state.item_edits.get(self.current_language, {}).get(item_id, {})
        for name, widget in self.info_fields.items():
            if name in lang_edits:
                widget.load(lang_edits[name], True)
            else:
                widget.load(baseline.get(name), False)

        # -- Base Item Data --
        xr = state.item_table_records_by_id("item").get(item_id)
        xml_baseline = xr.values if xr else {}
        base_edits = state.item_table_edits.get("item", {}).get(item_id, {})
        for name, widget in self.base_fields.items():
            default = "None" if name == "TypeFlags" else "0"
            widget.load(base_edits.get(name, xml_baseline.get(name, default)), name in base_edits)

        # -- dynamic sections, driven by the base fields we just loaded --
        self._rebuild_linked_section()
        self._refresh_equip_bonus_preview()

        # -- Shop Availability (same id as item) --
        shops_record = state.item_table_records_by_id("item_shops").get(item_id)
        shops_baseline = shops_record.values if shops_record else {}
        shops_edits = state.item_table_edits.get("item_shops", {}).get(item_id, {})
        self.shops_field.load(shops_edits.get("Shops", shops_baseline.get("Shops", "None")), "Shops" in shops_edits)

        # -- Icon/Sprite texture shortcuts --
        self.art_texture_slot.set_relative_path(td.item_art_texture_path(item_id))
        self.sprite_texture_slot.set_relative_path(td.item_sprite_texture_path(item_id))

        self._loading = False

    def _on_info_field_edited(self) -> None:
        if self._loading or self.current_item_id is None:
            return
        item_id = self.current_item_id
        edits = self.app.state_data.item_edits.setdefault(self.current_language, {}).setdefault(item_id, {})
        for name, widget in self.info_fields.items():
            if widget.included:
                edits[name] = widget.get_value()
            elif name in edits:
                del edits[name]
        if not edits:
            self.app.state_data.item_edits[self.current_language].pop(item_id, None)
        self._refresh_tree_tag(item_id)
        self._update_changes_label()

    def _commit_generic_xml_fields(self, table_key: str, row_id: int, fields_dict: dict) -> None:
        """Shared commit logic - every Stats-tab widget exposes get_value_str()/included."""
        edits = self.app.state_data.item_table_edits.setdefault(table_key, {}).setdefault(row_id, {})
        for name, widget in fields_dict.items():
            if widget.included:
                edits[name] = widget.get_value_str()
            elif name in edits:
                del edits[name]
        if not edits:
            self.app.state_data.item_table_edits[table_key].pop(row_id, None)

    def _on_base_field_edited(self) -> None:
        if self._loading or self.current_item_id is None:
            return
        self._commit_generic_xml_fields("item", self.current_item_id, self.base_fields)
        self._refresh_tree_tag(self.current_item_id)
        self._update_changes_label()

    def _on_type_flags_edited(self) -> None:
        self._on_base_field_edited()
        if not self._loading:
            self._rebuild_linked_section()

    def _on_additional_data_id_edited(self) -> None:
        self._on_base_field_edited()
        if not self._loading:
            self._rebuild_linked_section()

    def _on_equip_bonus_id_edited(self) -> None:
        self._on_base_field_edited()
        if not self._loading:
            self._refresh_equip_bonus_preview()

    def _on_linked_field_edited(self) -> None:
        if self._loading or self._linked_table_key is None or self._linked_row_id is None:
            return
        self._commit_generic_xml_fields(self._linked_table_key, self._linked_row_id, self.linked_fields)
        self._update_changes_label()

    def _go_to_equip_bonus_clicked(self) -> None:
        if self._on_go_to_equip_bonus:
            self._on_go_to_equip_bonus(self._current_equip_bonus_id())

    def _go_to_textures_clicked(self, relative_path: str) -> None:
        if self._on_go_to_textures:
            self._on_go_to_textures(relative_path)

    def _on_texture_edit_changed(self) -> None:
        if self.current_item_id is not None:
            self._refresh_tree_tag(self.current_item_id)
        self._update_changes_label()

    def _on_shops_field_edited(self) -> None:
        if self._loading or self.current_item_id is None:
            return
        self._commit_generic_xml_fields("item_shops", self.current_item_id, {"Shops": self.shops_field})
        self._refresh_tree_tag(self.current_item_id)
        self._update_changes_label()

    def _refresh_tree_tag(self, item_id: int) -> None:
        state = self.app.state_data
        lang_edits = state.item_edits.get(self.current_language, {})
        base_edits = state.item_table_edits.get("item", {})
        shops_edits = state.item_table_edits.get("item_shops", {})
        edited = bool(
            lang_edits.get(item_id) or base_edits.get(item_id) or shops_edits.get(item_id)
            or self._item_icon_texture_edited(item_id)
        )
        tags = ["edited"] if edited else []
        if self.item_tree.exists(str(item_id)):
            self.item_tree.item(str(item_id), tags=tags)

    # -- copy to all languages -------------------------------------------------

    def _on_copy_all_fields_clicked(self) -> None:
        if self.current_item_id is None:
            return
        widgets = [w for w in self.info_fields.values() if hasattr(w, "copy_fields")]
        if not widgets:
            return
        for widget in widgets:
            widget.include_var.set(True)
        self._on_info_field_edited()

        item_id = self.current_item_id
        state = self.app.state_data
        other_langs = [lang for lang in c.NXD_LANGUAGES if lang != self.current_language]
        for lang in other_langs:
            lang_edits = state.item_edits.setdefault(lang, {}).setdefault(item_id, {})
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

        if not self._reference_tables_ready():
            self.no_reference_var.set(
                "Item reference data hasn't loaded yet - it downloads by itself when General "
                "Setup opens, so give it a moment. If it failed, General Setup \u2192 Advanced "
                "options \u2192 Reference Tables has a \u201cCheck for updates\u201d button."
            )
            self.item_tree.delete(*self.item_tree.get_children())
            self.changes_var.set("")
            return
        self.no_reference_var.set("")

        if state.nxd_sqlite_path is None:
            self.no_data_var.set(
                "No ability/item database loaded yet - Item Info (names/descriptions) needs the "
                "converted database from General Setup. Stats below already work, "
                "since those come from the reference tables."
            )
        else:
            if state.nxd_sqlite_path != self._applied_sqlite_path:
                self._applied_sqlite_path = state.nxd_sqlite_path
                state.item_records = {}
                self.current_item_id = None
            self.no_data_var.set("")
            self._ensure_nxd_loaded(self.current_language)

        self._refresh_item_list()
        if self.current_item_id is None and state.item_table_records.get("item"):
            first_id = state.item_table_records["item"][0].item_id
            if self.item_tree.exists(str(first_id)):
                self.item_tree.selection_set(str(first_id))
