"""
Edit Game Data / Items.

**Items is not one table, and that is the whole reason this page exists.**

The generic `TableEditorPage` drives eleven tables that are all the same
shape - an ordered field list over records with an id and a name - and it is
right for ten of them. Items is the eleventh, and it is a different shape:
one item spans **seven** tables plus two textures plus a per-language text
row, and which of those seven applies depends on a value the user is
editing at the time.

    ItemData.xml            the base row - type, price, category, sprite
    ItemWeaponData.xml      \
    ItemArmorData.xml        |  ONE of these four, chosen by TypeFlags,
    ItemShieldData.xml       |  at the row AdditionalDataId points to
    ItemAccessoryData.xml   /
    ItemShopsData.xml       which towns sell it
    ItemEquipBonusData.xml  the bonus it grants (previewed, edited on its
                            own tab)
    Item-<lang>             name and description, per language, from the
                            converted database
    two .tex files          the art and sprite icons

Driving that through a page whose model is "one spec, one record" was what
made the Qt version thin: it showed `ItemData` and stopped, so a weapon's
Power - the field somebody making a weapon mod actually wants - was not
reachable in the new interface at all.

**The Additional Data section is rebuilt as you type.** `TypeFlags` decides
which table `AdditionalDataId` points into, so changing an item from Armor
to Weapon changes which fields exist. Headgear and Armor share
`ItemArmorData` - identical HPBonus/MPBonus shape despite being distinct
type flags - which is a rule from `constants.ITEM_TYPE_TO_ADDITIONAL_TABLE`
rather than something inferred here.

**Several items point at the same Additional Data row**, so editing one is
editing every item that shares it. The page says so rather than letting that
be discovered.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QPushButton, QSizePolicy, QSplitter,
    QVBoxLayout, QWidget,
)

from ... import constants as c
from ... import item_xml_io as ix
from ... import reference_names
from ... import texture_data as td
from ..widgets import actions
from ..widgets.actions import (
    page_intro,
    COPY_LANGUAGES_LABEL, COPY_LANGUAGES_NOTE, ViewToggles,
    apply_view_toggles, copy_edits_to_languages,
    ensure_language_loaded, mark_edited, select_list_row,
    set_empty_state, language_combo, language_order, edit_counter_text)
from ..widgets.field_rows import (
    CollapsibleSection, DropdownFieldRow, FlagFieldPanel, NumericFieldRow,
)
from ..widgets.form_scroll import FormScrollArea
from ..widgets.visible_refresh import RefreshesWhenVisible
from ..widgets.texture_slot import InlineTextureSlot
from .poaching import TextFieldRow

# TypeFlags value -> (table key, max id, field order, label). The same
# mapping the Tkinter tab uses, kept in the same order.
LINKED_TABLES = {
    "weapon": ("item_weapon", c.MAX_ITEM_WEAPON_ID,
               c.ITEM_WEAPON_FIELD_ORDER, "Weapon Data"),
    "shield": ("item_shield", c.MAX_ITEM_SHIELD_ID,
               c.ITEM_SHIELD_FIELD_ORDER, "Shield Data"),
    "armor": ("item_armor", c.MAX_ITEM_ARMOR_ID,
              c.ITEM_ARMOR_FIELD_ORDER, "Armor Data"),
    "accessory": ("item_accessory", c.MAX_ITEM_ACCESSORY_ID,
                  c.ITEM_ACCESSORY_FIELD_ORDER, "Accessory Data"),
}

# Which type flag wins when an item has several. Weapon before Shield before
# Headgear before Armor before Accessory, matching the Tkinter tab's own
# search order - an item flagged both Weapon and Rare is a weapon.
TYPE_PRIORITY = ("weapon", "shield", "headgear", "armor", "accessory")


def linked_table_key(values: dict) -> str | None:
    """
    Which Additional Data table THIS item's `AdditionalDataId` indexes.

    `AdditionalDataId` is an index into the item's OWN category table, not
    a global weapon index. Row 8 of `ItemWeaponData` and row 8 of
    `ItemArmorData` are different rows about different items, and the only
    thing that says which one an item means is its `TypeFlags`.

    Getting that wrong is not a display fault. The "Used by" list on
    Inflict Status read every item through `item_weapon` regardless of
    type, so Aegis Shield, Platinum Helm, Genji Gloves and Maiden's Kiss -
    all of which happen to carry `AdditionalDataId=8` - inherited
    Assassin's Dagger's status effect and were listed as inflicting Doom.
    None of them do.

    Returns `None` for an item with none of the five type flags. That is
    not an error and not a fallback to weapon: Maiden's Kiss is flagged
    only `Rare`, so it has no Additional Data row at all, and answering
    "weapon" for it is how it ended up under Doom.

    **`TypeFlags` decides, not `ItemCategory`.** Genji Gloves are category
    `Armguard` and flagged `Accessory`; Platinum Helm is category `Helmet`
    and flagged `Headgear`. The category is a display grouping, the flag is
    the thing the game reads.

    One function rather than a rule per caller. `rebuild_linked_section`
    and `table_usage` both need this answer, and two mechanisms answering
    the same question would fight silently - which is the whole shape of
    the bug above.
    """
    # The engine's own parser, the same one `_type_flags` uses on the live
    # form. A second splitter here would be a second answer to "what are
    # this item's flags", and "None" would parse as the flag `None`.
    flags = ix.parse_flag_value(values.get("TypeFlags") or "")
    for name in TYPE_PRIORITY:
        if name.capitalize() not in flags:
            continue
        # Headgear and Armor share `ItemArmorData` - the same HPBonus/
        # MPBonus shape despite being distinct type flags. That rule lives
        # in the engine's `ITEM_TYPE_TO_ADDITIONAL_TABLE` and is read from
        # there rather than restated, which is what this page used to do.
        target = c.ITEM_TYPE_TO_ADDITIONAL_TABLE[name.capitalize()]
        return LINKED_TABLES[target][0]
    return None


#: `LINKED_TABLES` by table key, for callers holding the key rather than the
#: type name. Derived, so the two cannot disagree about what a table holds.
LINKED_BY_KEY = {spec[0]: spec for spec in LINKED_TABLES.values()}

# The base row's fields, in the order somebody fills an item in rather than
# the order the columns happen to sit in. `ITEM_FIELD_ORDER` is the file's
# order and stays the authority for what gets written.
BASE_FIELD_ORDER = ["Palette", "SpriteID", "RequiredLevel", "TypeFlags",
                    "ItemCategory", "Price", "ShopAvailability",
                    "Unused_0x06", "Unused_0x0B"]

# The per-language numeric fields, after the text ones.
TEXT_NUMERIC_FIELDS = ["DLCFlags", "Unknown18", "Unknown19", "Unknown1A",
                       "Unknown1B", "UiStatusEffectId", "UiItemCategoryId",
                       "SortOrder", "Unknown2C"]


def is_unknown_label(field_name: str, label: str) -> bool:
    """
    Whether the two view toggles should treat this as an unknown field.

    **Judged on the LABEL, not the column name.** `Unknown4` on the
    encounter table holds a confirmed unit name, so a rule reading the
    column would hide a field this project has since identified. The label
    is what the tool claims to know.
    """
    return label.lower().startswith("unknown") or label.lower().startswith(
        "unused")


# The Comment column's caveat, too long for the 200px label column that every
# field row uses. The label says "Comment" and this says the rest.
_COMMENT_TOOLTIP = (
    "FF16Tools writes this note into the converted table. It is not data the "
    "game reads, so editing it changes nothing in play - it is here because a "
    "mod that ships the row should ship the row as it found it.")

class ItemsPage(RefreshesWhenVisible, QWidget):
    """The Items tab: a list, and three sub-tabs of editors for one item."""

    edits_changed = Signal()
    jump_to_equip_bonus = Signal(int)
    jump_to_inflict_status = Signal(int)
    # Where the Inflict Status row goes when Formula makes it an ability.
    # A separate signal rather than a shared `navigate_requested`, matching
    # the two above - this page names its destinations.
    jump_to_ability = Signal(int)
    jump_to_texture = Signal(str)

    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state
        self.current_item_id = None
        self.text_rows: dict[str, QWidget] = {}
        self.base_rows: dict[str, QWidget] = {}
        self.linked_rows: dict[str, QWidget] = {}
        self._linked_table_key = None
        self._linked_row_id = None
        self._loading = False

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
        self.language_box = language_combo()
        self.language_box.currentTextChanged.connect(self._on_language)
        top.addWidget(self.language_box)
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
            "All items, their stats, and respective textures.",
            self.language_controls))

        self.view_toggles = ViewToggles()
        self.view_toggles.changed.connect(self._apply_view)
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
        self.editing_label = QLabel("Select an item")
        self.editing_label.setStyleSheet("font-weight: 600; font-size: 12pt;")
        right.addWidget(self.editing_label)

        self.empty_note = QLabel(
            "No item data loaded.\n\nItem stats come from the reference "
            "tables, which load by themselves when General Setup opens. "
            "Names and descriptions also need your game unpacked.")
        self.empty_note.setProperty("role", "muted")
        self.empty_note.setWordWrap(True)
        # Top-left, where the content it stands in for would start. This was
        # `AlignCenter` with a stretch, which parked the message in the dead
        # centre of the window. Textures and Sounds have always used
        # `AlignTop`; see `set_empty_state`.
        self.empty_note.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        right.addWidget(self.empty_note)

        # The layout from Zodi's concept sketch, not sub-tabs.
        #
        # Sprite and art textures stacked in a narrow column on the left,
        # names and description filling the space beside them, stats across
        # the full width underneath. The first version of this page put the
        # three behind an "Item Info / Stats / Textures" tab strip, which
        # is a different thing: it hides two thirds of an item at all times
        # and makes "what does this item look like, and what is it called"
        # two clicks apart when the sketch has them side by side.
        #
        # A splitter rather than fixed heights, because how much room the
        # description wants against the stats is a per-person question and
        # the stats list is long.
        self.body = QSplitter(Qt.Vertical)

        upper = QWidget()
        upper_row = QHBoxLayout(upper)
        upper_row.setContentsMargins(0, 0, 0, 0)
        upper_row.setSpacing(10)
        upper_row.addWidget(self._build_textures_column())
        # The names panel's HEIGHT is not a vote in how tall this half is.
        #
        # Reported: "by default the Base Item Data box should be higher up
        # so that the 'Right-click a texture to edit' text and 'Base Item
        # Data' text are closer together." The splitter gives this half its
        # size hint, and a scroll area's hint is its content's, capped at
        # 24 lines - 360px here, against 316 for the texture column beside
        # it, so 44px of empty space sat under the column's last line.
        #
        # Ignored vertically, the texture column alone decides: the half
        # opens exactly as tall as the two textures and their hint, and the
        # names scroll inside it, which they were built to do. The divider
        # still moves, so anyone who wants more names showing can drag it.
        self.info_panel = self._build_info_panel()
        self.info_panel.setSizePolicy(QSizePolicy.Preferred,
                                      QSizePolicy.Ignored)
        upper_row.addWidget(self.info_panel, 1)
        self.body.addWidget(upper)

        self.body.addWidget(self._build_stats_panel())
        self.body.setStretchFactor(0, 0)
        self.body.setStretchFactor(1, 1)
        right.addWidget(self.body, 1)
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

    # -- the three sub-tabs -------------------------------------------------

    def _scrollable(self, body: QWidget) -> FormScrollArea:
        scroll = FormScrollArea()
        # Keep the body at the height its contents want, and scroll past it.
        #
        # Without this the seven Type checkboxes were squashed into the
        # height the splitter happened to give the pane - overlapping each
        # other, with the last two cut off. `setWidgetResizable` resizes the
        # body to the viewport in BOTH directions unless the body refuses to
        # shrink, which is what a minimum vertical policy makes it do.
        body.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        scroll.setWidget(body)
        return scroll

    def _build_info_panel(self) -> QWidget:
        body = QWidget()
        column = QVBoxLayout(body)
        column.setContentsMargins(4, 4, 4, 4)
        column.setSpacing(2)

        self.info_hint = QLabel("")
        self.info_hint.setProperty("role", "muted")
        self.info_hint.setWordWrap(True)
        column.addWidget(self.info_hint)

        for field_name in c.ITEM_TEXT_FIELDS:
            label = {"NameSingular": "Name (singular)",
                     "NamePlural": "Name (plural)",
                     "Name2": "Name 2 (alternate)",
                     # Shortened: the parenthetical did not fit the 200px
                     # label column and clipped mid-word. The caveat is on
                     # the label's tooltip instead - see `_COMMENT_TOOLTIP`.
                     "Comment": "Comment",
                     }.get(field_name, field_name)
            row = TextFieldRow(field_name, label)
            if field_name == "Comment":
                row.label.setToolTip(_COMMENT_TOOLTIP)
            row.edited.connect(self._on_text_edited)
            self.text_rows[field_name] = row
            column.addWidget(row)

        for field_name in TEXT_NUMERIC_FIELDS:
            low, high, label, note = c.ITEM_NUMERIC_FIELDS[field_name]
            row = NumericFieldRow(field_name, label, low, high, note,
                                  unknown=is_unknown_label(field_name, label))
            row.edited.connect(self._on_text_edited)
            self.text_rows[field_name] = row
            column.addWidget(row)

        label, note = c.ITEM_BOOL_FIELDS["IsRandomDamage"]
        row = NumericFieldRow("IsRandomDamage", label, 0, 1, note)
        row.edited.connect(self._on_text_edited)
        self.text_rows["IsRandomDamage"] = row
        column.addWidget(row)

        column.addStretch(1)
        self._refresh_info_hint()
        return self._scrollable(body)

    def _build_stats_panel(self) -> QWidget:
        body = QWidget()
        column = QVBoxLayout(body)
        column.setContentsMargins(4, 4, 4, 4)
        column.setSpacing(2)

        base_box = QGroupBox("Base Item Data")
        base_column = QVBoxLayout(base_box)
        base_column.setSpacing(2)
        for field_name in BASE_FIELD_ORDER:
            base_column.addWidget(self._make_base_row(field_name))
        column.addWidget(base_box)

        # Additional Data: the id, then a section rebuilt from whatever the
        # type currently is.
        self.linked_box = QGroupBox("Additional Data")
        linked_column = QVBoxLayout(self.linked_box)
        linked_column.setSpacing(2)
        low, high, label, hint = c.ITEM_XML_NUMERIC_FIELDS["AdditionalDataId"]
        add_row = NumericFieldRow("AdditionalDataId", label, low, high, hint)
        add_row.edited.connect(self._on_additional_id_edited)
        self.base_rows["AdditionalDataId"] = add_row
        linked_column.addWidget(add_row)

        self.linked_caption = QLabel("")
        self.linked_caption.setProperty("role", "muted")
        self.linked_caption.setWordWrap(True)
        linked_column.addWidget(self.linked_caption)

        self.linked_holder = QWidget()
        self.linked_column = QVBoxLayout(self.linked_holder)
        self.linked_column.setContentsMargins(0, 0, 0, 0)
        self.linked_column.setSpacing(2)
        linked_column.addWidget(self.linked_holder)
        column.addWidget(self.linked_box)

        # Equip Bonus: the pointer, a preview, and a jump.
        bonus_box = QGroupBox("Equip Bonus")
        bonus_column = QVBoxLayout(bonus_box)
        bonus_column.setSpacing(2)
        label = c.ITEM_XML_NUMERIC_FIELDS["EquipBonusId"][2]
        bonus_row = DropdownFieldRow(
            "EquipBonusId", label,
            jump_label="Edit \u2192",
            jump_tooltip="Open this row on the Equip Bonus tab")
        bonus_row.set_choices(self._equip_bonus_choices())
        bonus_row.edited.connect(self._on_equip_bonus_edited)
        bonus_row.jump_requested.connect(self.jump_to_equip_bonus.emit)
        self.base_rows["EquipBonusId"] = bonus_row
        bonus_column.addWidget(bonus_row)
        column.addWidget(bonus_box)

        # Shop availability - its own table, keyed by the same item id.
        shops_box = QGroupBox("Shop Availability")
        shops_column = QVBoxLayout(shops_box)
        self.shops_row = FlagFieldPanel(
            "Shops", "Sold in", {"Towns": c.ITEM_SHOPS}, columns=1)
        self.shops_row.edited.connect(self._on_shops_edited)
        shops_column.addWidget(self.shops_row)
        column.addWidget(shops_box)

        column.addStretch(1)
        return self._scrollable(body)

    def _make_base_row(self, field_name: str) -> QWidget:
        if field_name == "TypeFlags":
            row = FlagFieldPanel("TypeFlags", "Type",
                                 {"Type": c.ITEM_TYPE_FLAGS}, columns=1)
            # Changing the type changes which table Additional Data means,
            # so this one rebuilds the section rather than only committing.
            row.edited.connect(self._on_type_flags_edited)
        elif field_name == "ItemCategory":
            row = _EnumRow("ItemCategory", "Item Category", c.ITEM_CATEGORIES)
            row.edited.connect(self._on_base_edited)
        elif field_name == "ShopAvailability":
            row = _EnumRow("ShopAvailability", "Shop Availability",
                           c.ITEM_SHOP_AVAILABILITY)
            row.edited.connect(self._on_base_edited)
        else:
            low, high, label, note = c.ITEM_XML_NUMERIC_FIELDS[field_name]
            row = NumericFieldRow(field_name, label, low, high, note,
                                  unknown=is_unknown_label(field_name, label))
            row.edited.connect(self._on_base_edited)
        self.base_rows[field_name] = row
        return row

    def _build_textures_column(self) -> QWidget:
        """Sprite above art, both narrow - the left column of the sketch."""
        holder = QWidget()
        column = QVBoxLayout(holder)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(6)

        # Sprite first, as drawn. It is the icon seen most often in play -
        # the inventory and the battle menu - so it is the one somebody
        # replacing an item's look is usually after.
        self.sprite_slot = InlineTextureSlot("Sprite Texture", self.state,
                                             compact=True)
        self.art_slot = InlineTextureSlot("Art Texture", self.state,
                                          compact=True)
        for slot in (self.sprite_slot, self.art_slot):
            slot.edits_changed.connect(self._on_texture_changed)
            slot.view_requested.connect(self.jump_to_texture)
            column.addWidget(slot)

        hint = QLabel("Right-click a texture to edit.")
        hint.setProperty("role", "muted")
        hint.setWordWrap(True)
        column.addWidget(hint)
        column.addStretch(1)
        holder.setFixedWidth(250)
        return holder

    # -- the dynamic Additional Data section --------------------------------

    def _linked_key_now(self) -> str | None:
        """
        This item's Additional Data table, read from the LIVE form.

        The form rather than the record, because `TypeFlags` is being
        edited: changing an item from Armor to Weapon has to change which
        table its Additional Data id points into before anything is saved.
        """
        return linked_table_key(
            {"TypeFlags": self.base_rows["TypeFlags"].get_value_str()})

    def _additional_id(self) -> int:
        try:
            return int(self.base_rows["AdditionalDataId"].get_value_str())
        except (TypeError, ValueError):
            return 0

    def _equip_bonus_id(self) -> int:
        try:
            return int(self.base_rows["EquipBonusId"].get_value_str())
        except (TypeError, ValueError):
            return 0

    def rebuild_linked_section(self) -> None:
        """
        Replaces the Additional Data fields with the ones this item's type
        actually has.

        Called whenever TypeFlags or AdditionalDataId changes, and on load.
        """
        while self.linked_column.count():
            item = self.linked_column.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.linked_rows = {}

        # `linked_table_key` is the one place that answers "which table does
        # this item's AdditionalDataId index". The rule used to be restated
        # here as well, and the copy in `table_usage` that disagreed with it
        # is what put Doom on four items that do not inflict it.
        table_key = self._linked_key_now()
        self._linked_row_id = self._additional_id()

        if table_key is None:
            self._linked_table_key = None
            self.linked_caption.setText(
                "This item has no linked Weapon/Armor/Shield/Accessory data "
                "- its Type includes none of Weapon, Shield, Headgear, "
                "Armor or Accessory.")
            return

        _key, max_id, field_order, label = LINKED_BY_KEY[table_key]
        self._linked_table_key = table_key
        row_id = self._linked_row_id

        if row_id > max_id:
            self.linked_caption.setText(
                f"Additional Data Id {row_id} is out of range for {label} "
                f"(0-{max_id}) - fix the Additional Data Id above.")
            return

        self.linked_caption.setText(
            f"{label}, row {row_id}. Several items commonly point at the "
            f"same row, so editing it affects every item that uses it.")

        record = self.state.item_table_records_by_id(table_key).get(row_id)
        baseline = record.values if record else {}
        edits = (self.state.item_table_edits.get(table_key, {})
                 .get(row_id, {}))

        for field_name in field_order:
            if field_name == "AttackFlags":
                row = FlagFieldPanel("AttackFlags", "Attack Flags",
                                     {"Attack": c.ITEM_ATTACK_FLAGS},
                                     columns=1)
                default = "None"
            elif field_name == "Elements":
                row = FlagFieldPanel("Elements", "Elements",
                                     {"Elements": c.ELEMENT_FLAGS}, columns=1)
                default = "None"
            elif field_name == "Formula":
                # A dropdown, not a number box. `Formula` selects one of the
                # game's hardcoded damage routines, and 7 tells a beginner
                # nothing about what it does while "Heal_[Weapon]" does.
                #
                # Safe to constrain here in a way EffectId is not: the 107
                # named routines ARE the domain, and a number outside them
                # names nothing the game can run.
                row = DropdownFieldRow("Formula", "Formula", zero_is_none=False)
                row.set_choices(reference_names.formula_names())
                default = "0"
            elif field_name == "OptionsAbilityId":
                # Built by its own method, because this row is two fields
                # wearing one column. See `_make_options_row`.
                row = self._make_options_row()
                default = "0"
            else:
                low, high, flabel, note = c.ITEM_XML_NUMERIC_FIELDS[field_name]
                row = NumericFieldRow(
                    field_name, flabel, low, high, note,
                    unknown=is_unknown_label(field_name, flabel))
                default = "0"
            row.load(edits.get(field_name, baseline.get(field_name, default)),
                     field_name in edits)
            row.edited.connect(self._on_linked_edited)
            self.linked_rows[field_name] = row
            self.linked_column.addWidget(row)
            if field_name == "Formula":
                # Formula decides what the row below MEANS, so changing it
                # has to change that row - live, without reloading the item.
                row.edited.connect(self._sync_options_kind)
            if field_name == "OptionsAbilityId":
                # No caption and no separate button underneath.
                #
                # The list names the row - "011 - Doom" - so a line of prose
                # repeating that in other words was saying the same thing
                # twice, and the button belongs beside the control it acts
                # on rather than on a line of its own. Same row shape as a
                # Job Commands ability slot.
                row.edited.connect(self.refresh_inflict_status)
                self.refresh_inflict_status()
        apply_view_toggles(list(self.linked_rows.values()),
                           *self.view_toggles.state())

    def _inflict_choices(self) -> dict:
        """
        Every Inflict Status row, named the way the Inflict Status page
        names it.

        Through `inflict_status_descriptor`, the same function that page
        builds its own list from, so the two cannot describe one row
        differently. A number box asked the person to know that 11 is Doom;
        the list says so.
        """
        from .table_editor import inflict_status_descriptor

        records = (self.state.item_table_records or {}).get(
            "item_options", [])
        edits = (self.state.item_table_edits or {}).get("item_options", {})
        choices = {}
        for record in records:
            values = {**record.values, **edits.get(record.item_id, {})}
            choices[record.item_id] = inflict_status_descriptor(values)
        return choices

    def _equip_bonus_choices(self) -> dict:
        """Every Equip Bonus row, summarised the way the page summarises it."""
        records = (self.state.item_table_records or {}).get(
            "item_equip_bonus", [])
        return {r.item_id: self._equip_bonus_summary(r.item_id)
                for r in records}

    def _make_options_row(self):
        """
        The control for `OptionsAbilityId`, which is two fields in one column.

        Normally it is an Inflict Status row id - a number into
        `ItemOptionsData.xml`. When `Formula` is 2 the game reads the same
        byte as an ABILITY id and the item casts that spell instead.

        The page used to show one number box labelled `Inflict Status` with
        a caption explaining the exception. That is honest, and it still
        asks a beginner to hold two meanings in their head and to know
        which one is in force. So the control says which: at Formula 2 the
        label is **Cast Spell** and the box becomes a list of ability names,
        because a name is the thing you can recognise and 183 is not.

        The ability names come from `app.ability_choices`, which is the same
        source the Abilities tab lists from - so renaming an ability there
        renames it here. Poaching's Produces / Unlocks Item does exactly
        this; a second list would be a second set of names to go stale.
        """
        from ..app import ability_choices

        flabel = c.ITEM_XML_NUMERIC_FIELDS["OptionsAbilityId"][2]
        if self._uses_ability_formula():
            row = DropdownFieldRow(
                "OptionsAbilityId", "Cast Spell",
                jump_label="Edit \u2192",
                jump_tooltip="Open this ability on the Abilities tab")
            row.set_choices(ability_choices(self.state))
            row.lists_abilities = True
        else:
            row = DropdownFieldRow(
                "OptionsAbilityId", flabel,
                jump_label="Edit \u2192",
                jump_tooltip="Open this row on the Inflict Status tab")
            row.set_choices(self._inflict_choices())
            row.lists_abilities = False
        row.jump_requested.connect(self._on_options_jump)
        return row

    def _sync_options_kind(self) -> None:
        """
        Swaps the options control when Formula crosses into or out of 2.

        In place, not by rebuilding the Additional Data section: the change
        is triggered BY the Formula box, and tearing down the whole column
        would delete the widget under the cursor mid-edit.

        Does nothing while the kind is unchanged, so typing 1 -> 1 or
        3 -> 4 leaves the row alone rather than replacing it on every
        keystroke and dropping whatever was selected.
        """
        old = self.linked_rows.get("OptionsAbilityId")
        if old is None:
            return
        # What the row currently IS, recorded rather than inferred.
        #
        # This used to ask `isinstance(old, DropdownFieldRow)`, which worked
        # only while one of the two states was a number box. Both are
        # dropdowns now - they differ in what they LIST - so the type stopped
        # telling them apart and the swap silently never happened.
        wants_ability = self._uses_ability_formula()
        if wants_ability == getattr(old, "lists_abilities", False):
            self.refresh_inflict_status()
            return
        index = self.linked_column.indexOf(old)
        if index < 0:
            return
        value, included = old.get_value_str(), old.included
        self.linked_column.takeAt(index)
        old.setParent(None)
        old.deleteLater()
        row = self._make_options_row()
        # The value carries across. The byte does not change when the
        # formula does - what changes is what it means - so blanking it
        # here would silently discard the item's data.
        row.load(value, included)
        row.edited.connect(self._on_linked_edited)
        row.edited.connect(self.refresh_inflict_status)
        self.linked_rows["OptionsAbilityId"] = row
        self.linked_column.insertWidget(index, row)
        apply_view_toggles([row], *self.view_toggles.state())
        self.refresh_inflict_status()

    def _on_options_jump(self, _row_id=None) -> None:
        """
        Sends the jump wherever the field currently points.

        One button, two destinations, decided by the same rule the label
        follows - a button that always went to Inflict Status would, at
        Formula 2, open a status row that has nothing to do with the spell
        the item casts.
        """
        if self._uses_ability_formula():
            self.jump_to_ability.emit(self._options_ability_id())
            return
        self.jump_to_inflict_status.emit(self._options_ability_id())

    def _options_ability_id(self) -> int:
        row = self.linked_rows.get("OptionsAbilityId")
        try:
            return int(row.get_value_str()) if row is not None else 0
        except (TypeError, ValueError):
            return 0

    def _uses_ability_formula(self) -> bool:
        """Formula 2 makes OptionsAbilityId an ability id, not an option."""
        row = self.linked_rows.get("Formula")
        try:
            return int(row.get_value_str()) == 2 if row is not None else False
        except (TypeError, ValueError):
            return False

    def refresh_inflict_status(self) -> None:
        """
        Keeps the control's LIST matching what it currently means.

        There is nothing to caption any more - the row names its own value.
        What still has to happen is the swap between two different lists:
        status rows normally, abilities when Formula is 2. That swap is
        `_sync_options_kind`; this only refreshes the entries, so a status
        row renamed on its own tab is renamed here too.
        """
        from ..app import ability_choices

        row = self.linked_rows.get("OptionsAbilityId")
        if not isinstance(row, DropdownFieldRow):
            return
        current, included = row.get_value_str(), row.included
        row.set_choices(ability_choices(self.state)
                        if self._uses_ability_formula()
                        else self._inflict_choices())
        row.load(current, included)

    def _inflict_status_summary(self, option_id: int) -> str:
        """
        What that row does, in the words the Inflict Status page uses.

        Imported from the page rather than re-derived, so the two cannot
        describe the same row differently.
        """
        from .table_editor import inflict_status_descriptor

        record = (self.state.item_table_records_by_id("item_options")
                  .get(option_id))
        baseline = record.values if record else {}
        edits = (self.state.item_table_edits.get("item_options", {})
                 .get(option_id, {}))
        if not baseline and not edits:
            return "No such row in the loaded table."
        return inflict_status_descriptor({**baseline, **edits})

    def _equip_bonus_summary(self, bonus_id: int) -> str:
        """A one-glance summary of the bonus row, so the id is not alone."""
        record = (self.state.item_table_records_by_id("item_equip_bonus")
                  .get(bonus_id))
        baseline = record.values if record else {}
        edits = (self.state.item_table_edits.get("item_equip_bonus", {})
                 .get(bonus_id, {}))

        def value_of(name, default):
            return edits.get(name, baseline.get(name, default))

        stats = []
        for name, label in (("PABonus", "PA"), ("MABonus", "MA"),
                            ("SpeedBonus", "Speed"), ("MoveBonus", "Move"),
                            ("JumpBonus", "Jump")):
            try:
                amount = int(value_of(name, "0"))
            except (TypeError, ValueError):
                amount = 0
            if amount:
                stats.append(f"{label} +{amount}")

        parts = []
        if stats:
            parts.append(", ".join(stats))
        for name, label in (("InnateStatus", "Innate"),
                            ("ImmuneStatus", "Immune"),
                            ("StartingStatus", "Starts with"),
                            ("AbsorbElements", "Absorbs"),
                            ("NullifyElements", "Nullifies"),
                            ("HalveElements", "Halves"),
                            ("WeakElements", "Weak to"),
                            ("StrongElements", "Strong vs")):
            flags = ix.parse_flag_value(value_of(name, "None"))
            if flags:
                parts.append(f"{label}: {', '.join(sorted(flags))}")
        if str(value_of("BoostJP", "false")).strip().lower() == "true":
            parts.append("Boosts JP gain")
        return "; ".join(parts) if parts else "No bonuses set on this row."

    def refresh_equip_bonus(self) -> None:
        """
        Keeps the Equip Bonus list matching the rows that exist.

        The out-of-range warning is gone with the number box that made it
        possible: a list cannot hold a value that is not in it.
        """
        row = self.base_rows.get("EquipBonusId")
        if not isinstance(row, DropdownFieldRow):
            return
        current, included = row.get_value_str(), row.included
        row.set_choices(self._equip_bonus_choices())
        row.load(current, included)

    # -- records ------------------------------------------------------------

    @property
    def language(self) -> str:
        return self.language_box.currentText() or c.NXD_DEFAULT_LANGUAGE

    def records(self) -> list:
        return (self.state.item_table_records or {}).get("item", [])

    def _edited_name(self, item_id: int) -> str:
        """
        The name the user has typed, if they have typed one.

        The list has to follow the Name field as it is edited. Renaming an
        item and watching the list keep the old name reads as the edit not
        having registered - and on this page the list is the only place the
        new name appears, because the field itself is what you are typing
        into.
        """
        return (self.state.item_edits.get(self.language, {})
                .get(item_id, {}).get("Name") or "").strip()

    def _display_name(self, item_id: int) -> str:
        """
        The name from the converted database if there is one, the XML's own
        name comment otherwise.

        Both, rather than either: the reference tables carry a name comment
        and load without a game unpack, while the database has the real
        localised text. A page that used only the database would be blank
        before setup; one that used only the XML would never show a
        translation.
        """
        edited = self._edited_name(item_id)
        if edited:
            return f"{item_id:03d} - {edited}"
        by_id = {r.key: r for r
                 in (self.state.item_records or {}).get(self.language, [])}
        record = by_id.get(item_id)
        if record is not None:
            # Not `record.display_name`: that reads `Name` alone, and ja,
            # ko, cs and ct leave `Name` null on every row and put the name
            # in `NameSingular`. Every item in those four listed as
            # "(unnamed)".
            return actions.record_display_name(record)
        xml_record = self.state.item_table_records_by_id("item").get(item_id)
        if xml_record is not None:
            return xml_record.display_name()
        return f"{item_id:03d} - (no data)"

    def refresh_records(self) -> None:
        ensure_language_loaded(self.state, "item_records", self.language)
        self.list.clear()
        records = self.records()
        for record in records:
            item = QListWidgetItem(self._display_name(record.item_id))
            item.setData(Qt.UserRole, record.item_id)
            self.list.addItem(item)

        has_data = bool(records)
        set_empty_state(
            self.empty_note, has_data,
            self.body, self.search, self.list, self.editing_label,
            self.language_controls, self.counter)
        self._mark_edited()
        self._update_counter()
        if self.list.count():
            self.list.setCurrentRow(0)

    def _filter_list(self, text: str) -> None:
        needle = text.strip().lower()
        for i in range(self.list.count()):
            item = self.list.item(i)
            item.setHidden(bool(needle) and needle not in item.text().lower())

    def _on_selection(self, current, _previous) -> None:
        if current is not None:
            self.load_record(current.data(Qt.UserRole))

    def select_record(self, item_id: int) -> None:
        """
        Used by a jump from another tab - Equip Bonus' "Used by" links.

        Was a bare loop with `setCurrentRow`, which worked except in two
        cases the shared helper covers: a search term hiding the target, and
        `setCurrentRow` scrolling only far enough to make the row visible,
        which parks a jumped-to item hard against an edge.
        """
        select_list_row(self.list, int(item_id), self.search)

    def _on_language(self, _text: str) -> None:
        """
        Switches language without disturbing the selection.

        `refresh_records()` is not used here, and that is the point: it
        clears the list and selects row 0, so switching language moved the
        selection to the first item and then back. Every widget on the page
        reloaded twice - including both texture slots, which each decode a
        .tex through FF16Tools, so changing language spawned four
        subprocesses for icons that are not per-language at all.

        Relabelling the rows in place and reloading the current record does
        the whole job, because only the TEXT differs between languages: the
        stats, the shop row and the two icons are shared.
        """
        ensure_language_loaded(self.state, "item_records", self.language)
        self._refresh_info_hint()
        for i in range(self.list.count()):
            item = self.list.item(i)
            item.setText(self._display_name(item.data(Qt.UserRole)))
        self._mark_edited()
        self._update_counter()
        if self.current_item_id is not None:
            self.load_record(self.current_item_id)

    def _refresh_info_hint(self) -> None:
        """
        Says which language is being edited - and when that language has no
        text at all.

        A conversion can contain a language table with every Name null: the
        game ships some languages unpopulated, and a partial conversion can
        do the same. The page then shows a list of "(unnamed)" rows and
        blank fields, which is indistinguishable from the tool having failed
        to load anything - the exact complaint that started this. Saying so
        turns "it's broken" into "there's nothing there to edit", which are
        very different problems with very different fixes.

        Typing into a blank field is still a real edit, so nothing is
        disabled - an author adding Japanese text to a table the game left
        empty is a legitimate mod.
        """
        label = c.NXD_LANGUAGE_LABELS.get(self.language, self.language)
        # The second sentence is the copy button's, not the tables'. It
        # used to say the stats below are shared, which is true and was not
        # what a reader needed; what they need is what the button beside it
        # will and will not carry. Checked against `copy_edits_to_languages`
        # in `test_qt_items`: every non-text edit reaches all six other
        # languages and no text field reaches any of them.
        text = (f"Editing {label} text, stored in its own "
                f"Item-{self.language} table. Copy to other languages copies "
                f"everything except the text fields.")
        records = (self.state.item_records or {}).get(self.language)
        # Every name column, not just `Name`.
        #
        # This said "your converted database has no Japanese item text at
        # all" for ja, ko, cs and ct - all four of which have the full text,
        # in `NameSingular`. So the note was not merely unhelpful, it was
        # false, and it told a reader their conversion was incomplete when
        # it was not. Asking the same question the list now asks keeps the
        # note for the case it was written for: a language table that
        # really is empty.
        if records is not None and not any(
                actions.record_name(r) for r in records):
            text += (f"  \u2014  Note: your converted database has no {label} "
                     f"item text at all, so these fields start empty. "
                     f"Anything you type here is still written to your mod.")
        self.info_hint.setText(text)

    # -- loading ------------------------------------------------------------

    def load_record(self, item_id: int) -> None:
        self._loading = True
        try:
            self.current_item_id = item_id
            self.editing_label.setText(
                f"Editing: {self._display_name(item_id)}")

            # Per-language text.
            by_id = {r.key: r for r
                     in (self.state.item_records or {}).get(self.language, [])}
            record = by_id.get(item_id)
            baseline = record.values if record else {}
            edits = (self.state.item_edits.get(self.language, {})
                     .get(item_id, {}))
            for field_name, row in self.text_rows.items():
                if field_name in edits:
                    row.load(edits[field_name], True)
                else:
                    row.load(baseline.get(field_name), False)

            # The base row.
            xml_record = (self.state.item_table_records_by_id("item")
                          .get(item_id))
            xml_baseline = xml_record.values if xml_record else {}
            base_edits = (self.state.item_table_edits.get("item", {})
                          .get(item_id, {}))
            for field_name, row in self.base_rows.items():
                default = "None" if field_name == "TypeFlags" else "0"
                row.load(
                    base_edits.get(field_name,
                                   xml_baseline.get(field_name, default)),
                    field_name in base_edits)

            # Everything that follows the base row.
            self.rebuild_linked_section()
            self.refresh_equip_bonus()

            shops_record = (self.state.item_table_records_by_id("item_shops")
                            .get(item_id))
            shops_baseline = shops_record.values if shops_record else {}
            shops_edits = (self.state.item_table_edits.get("item_shops", {})
                           .get(item_id, {}))
            self.shops_row.load(
                shops_edits.get("Shops", shops_baseline.get("Shops", "None")),
                "Shops" in shops_edits)

            self.art_slot.set_relative_path(td.item_art_texture_path(item_id))
            self.sprite_slot.set_relative_path(
                td.item_sprite_texture_path(item_id))
        finally:
            self._loading = False

    # -- committing ---------------------------------------------------------

    def _commit(self, table_key: str, row_id: int, rows: dict) -> None:
        """
        Only ticked fields are written, and an emptied record is removed.

        The one commit path for all four XML tables this page edits, so
        `item_shops` cannot drift from `item` in how it decides what counts
        as an edit.
        """
        edits = self.state.item_table_edits.setdefault(table_key, {})
        fields = edits.setdefault(row_id, {})
        for field_name, row in rows.items():
            if row.included:
                fields[field_name] = row.get_value_str()
            elif field_name in fields:
                del fields[field_name]
        if not fields:
            edits.pop(row_id, None)
        if not edits:
            self.state.item_table_edits.pop(table_key, None)

    def _on_text_edited(self) -> None:
        if self._loading or self.current_item_id is None:
            return
        item_id = self.current_item_id
        per_language = self.state.item_edits.setdefault(self.language, {})
        fields = per_language.setdefault(item_id, {})
        for field_name, row in self.text_rows.items():
            if row.included:
                fields[field_name] = row.get_value_str()
            elif field_name in fields:
                del fields[field_name]
        if not fields:
            per_language.pop(item_id, None)
        self._refresh_current_name()
        self._after_edit()

    def _refresh_current_name(self) -> None:
        """Retitles the selected row and the heading from the Name field."""
        if self.current_item_id is None:
            return
        label = self._display_name(self.current_item_id)
        row = self.list.currentItem()
        if row is not None and row.data(Qt.UserRole) == self.current_item_id:
            row.setText(label)
        self.editing_label.setText(f"Editing: {label}")

    def _on_base_edited(self) -> None:
        if self._loading or self.current_item_id is None:
            return
        self._commit("item", self.current_item_id, self.base_rows)
        self._after_edit()

    def _on_type_flags_edited(self) -> None:
        self._on_base_edited()
        if not self._loading:
            self.rebuild_linked_section()

    def _on_additional_id_edited(self) -> None:
        self._on_base_edited()
        if not self._loading:
            self.rebuild_linked_section()

    def _on_equip_bonus_edited(self) -> None:
        self._on_base_edited()
        if not self._loading:
            self.refresh_equip_bonus()

    def _on_linked_edited(self) -> None:
        if (self._loading or self._linked_table_key is None
                or self._linked_row_id is None):
            return
        self._commit(self._linked_table_key, self._linked_row_id,
                     self.linked_rows)
        self._after_edit()

    def _on_shops_edited(self) -> None:
        if self._loading or self.current_item_id is None:
            return
        self._commit("item_shops", self.current_item_id,
                     {"Shops": self.shops_row})
        self._after_edit()

    def _on_texture_changed(self) -> None:
        self._after_edit()

    def refresh_from_store(self) -> None:
        """
        Re-read the selected item when this page comes back on screen.

        `load_record` fills the per-language text rows, the base row and the
        shop rows from their stores, so one call re-ticks whatever All Game
        Data wrote. See `widgets/visible_refresh.py`.
        """
        if self.current_item_id is None:
            return
        self.load_record(self.current_item_id)
        self._mark_edited()
        self._update_counter()

    def _after_edit(self) -> None:
        self._mark_edited()
        self._update_counter()
        self.edits_changed.emit()

    # -- copying across languages -------------------------------------------

    def copy_current_to_languages(self) -> None:
        """
        Copies this item's non-text fields to every other language.

        Text is deliberately excluded - copying an English name into the
        Japanese table is not a translation, it is a mod that ships English
        text claiming to be Japanese.
        """
        if self.current_item_id is None:
            return
        copy_edits_to_languages(
            self.state.item_edits, self.language, self.current_item_id,
            [lang for lang in c.NXD_LANGUAGES if lang != self.language],
            skip_fields=set(c.ITEM_TEXT_FIELDS))
        self._after_edit()

    # -- marking and counting -----------------------------------------------

    def _is_edited(self, item_id: int) -> bool:
        """
        Every store an item can be edited in.

        All seven, not just ItemData - an item whose only change is its shop
        list or its icon is an edited item, and a list that marked only base
        edits would show a mod's own work as untouched.
        """
        if self.state.item_edits.get(self.language, {}).get(item_id):
            return True
        # EVERY item table, which is what the docstring above has always
        # claimed and what the counter under the heading has always
        # counted. This loop named `item` and `item_shops` only, so an item
        # whose change was a weapon, armour, shield or accessory field -
        # Power, for one - stayed unmarked in the list while the counter
        # went up. The edit was recorded correctly the whole time; only the
        # green was missing, which is the worst kind of wrong, because the
        # page said the work had not happened.
        #
        # Taken from the state's own accounting rather than a second list
        # here, so a table added later is covered without anyone
        # remembering to come back.
        for key, rows in (self.state.item_table_edits or {}).items():
            if key in self.state.NON_ITEM_TABLE_KEYS:
                continue
            if rows.get(item_id):
                return True
        edits = self.state.texture_edits or {}
        return (td.item_art_texture_path(item_id) in edits
                or td.item_sprite_texture_path(item_id) in edits)

    def _mark_edited(self) -> None:
        for i in range(self.list.count()):
            item = self.list.item(i)
            mark_edited(item, self._is_edited(item.data(Qt.UserRole)))

    def _update_counter(self) -> None:
        # One number, like every other page.
        #
        # This listed seven: text, base, weapon, armor, shield, accessory,
        # shop and icons. Every one of them is true and nobody learning the
        # tool could tell what any of it meant - an item edited in two of
        # those tables is still ONE item somebody changed, which is the
        # question the line is being asked. The breakdown lives in Export
        # Mod's Mod Contents, where it is what somebody is actually
        # checking.
        # `_is_edited` is the same rule the LIST uses to bold a row, so the
        # count and the bolding cannot disagree - which they would if this
        # added up table counts separately.
        edited = sum(1 for record in self.records()
                     if self._is_edited(record.item_id))
        self.counter.setText(
            edit_counter_text(edited, self.list.count(), "items"))

    # -- view toggles -------------------------------------------------------

    def _apply_view(self, hide_notes: bool, hide_unknown: bool,
                    hide_comments: bool) -> None:
        rows = (list(self.text_rows.values()) + list(self.base_rows.values())
                + list(self.linked_rows.values()) + [self.shops_row])
        apply_view_toggles(rows, hide_notes, hide_unknown,
                           hide_comments)


class _EnumRow(DropdownFieldRow):
    """
    A dropdown whose value is the NAME, not an id.

    `ItemCategory` and `ShopAvailability` store `"Knife"` and
    `"Chapter1_Start"` in the XML - the string itself is the value.
    `DropdownFieldRow` stores an id and would write `3`, which the loader
    would not recognise.

    **The label is spaced and the value is not.** The list shows "Knight
    Sword" and the file gets `KnightSword`, the same rule the flag
    checkboxes follow. Getting that backwards writes a mod the game ignores.
    """

    def __init__(self, field_name: str, label: str, values: list, parent=None):
        super().__init__(field_name, label, parent=parent)
        self.set_enum_choices(values)

    def set_enum_choices(self, values: list) -> None:
        from ..widgets.field_rows import split_words
        self._loading = True
        try:
            self.combo.clear()
            self._id_to_index = {}
            for index, value in enumerate(values):
                self.combo.addItem(split_words(value), value)
                self._id_to_index[value] = index
        finally:
            self._loading = False

    def current_id(self):
        data = self.combo.currentData()
        return data if data is not None else ""

    def get_value_str(self) -> str:
        return str(self.current_id())

    def load(self, raw_value, included: bool) -> None:
        from ..widgets.field_rows import split_words
        self._loading = True
        try:
            value = "" if raw_value is None else str(raw_value).strip()
            if value not in self._id_to_index:
                # A value this build has no name for is shown as itself
                # rather than snapping to the first entry, which would
                # rewrite the mod's category to "None" on open.
                self.combo.addItem(split_words(value) or "(blank)", value)
                self._id_to_index[value] = self.combo.count() - 1
            self.combo.setCurrentIndex(self._id_to_index[value])
            self.include.setChecked(bool(included))
        finally:
            self._loading = False

    def _sync_jump(self) -> None:
        return
