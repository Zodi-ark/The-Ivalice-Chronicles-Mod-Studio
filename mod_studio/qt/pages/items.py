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

import re
from pathlib import Path

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFrame, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QSizePolicy, QSplitter,
    QVBoxLayout, QWidget,
)

from ... import constants as c
from ... import item_xml_io as ix
from ... import reference_names
from ... import texture_data as td
from ... import wotl_items as wl
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
from ..widgets.layout_settle import retire
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
# (Zodi, 3 November) Palette and Sprite Id are one field now (`HELD_FIELD`),
# the icon a unit holds up or throws picked from the enhanced item texture;
# the two columns are still written as they were. (4 November) It sits with
# Attack in the Battle Sprite's own box at the top (`BATTLE_FIELDS_TITLE`),
# so Base Item Data starts with Required Level.
HELD_FIELD = "HeldSprite"
HELD_PARTS = ("Palette", "SpriteID")
BASE_FIELD_ORDER = ["RequiredLevel", "TypeFlags",
                    "ItemCategory", "Price", "ShopAvailability",
                    "Unused_0x06", "Unused_0x0B"]

# (Zodi, 4 November, after the item card's redesign: "I changed an items sprite on the Items page and the Battle
# Sprite attacking preview is not updating", and "shouldn't "Sprite and Palette" already cover the "In battle"
# option"; measured, the game draws the two halves from two things: a weapon's attack from its look, its sprite pair,
# and what a unit holds up or throws from its Sprite and Palette. His choice: "Together, named by half. Both side by
# side with the Battle Sprite, one named Attack and one Held or thrown, each changing only its half. Also make sure the
# field options to change them appear next to each other") The Battle Sprite's two fields in a box of their own at the
# top of the stats, each in the other's design: the sprite drawn, its palette, a button opening the sprites to choose.
BATTLE_FIELDS_TITLE = "Battle Sprite"
# (1.28.0) A weapon's look as it attacks (Zodi, 3 November, after test 60: "apply our item's sprite pair findings to
# the Items page on the Mod Studio so that users can also change the vanilla items look and palette"): its sprite pair,
# which the game keeps in its program rather than in a table, given to the game by Mod Studio Framework as it starts.
ATTACK_FIELD_LABEL = "Attack"
ATTACK_FIELD_NOTE = "The sprite a unit attacks with in battle."
ATTACK_CHOOSE = "Choose a look"
ATTACK_PICKED = "The {item}'s look, palette {palette}."
#: (Zodi, 4 November: "many of them share the same design") A look several of the game's weapons share, all named.
ATTACK_SHARED = "The look of the {items}, palette {palette}."
ATTACK_OWN_PICKED = "Its own look, palette {palette}."
PALETTE_CHOICE = "Palette {n}"
LOOK_NO_PROGRAM = ("A weapon's or shield's look in battle needs the game's program, found from General Setup's folder "
                   "of .pac files: {problem}.")
LOOK_NOT_GAME = "Only the game's own weapons' and shields' looks can be changed here."
LOOK_DIALOG_TITLE = "Attack: {item}"
#: (Zodi, 4 November: "many of them share the same design so what you get is a lot of repeating looks in the list with
#: different item names ... see if you can find a better way to categorize these different looks") Each sprite once,
#: the game's weapons that share it named under it, under the weapon type it is drawn for.
LOOK_DIALOG_INTRO = "Click the sprite a unit attacks with and choose its palette."
# (Zodi, 5 November: "for shields I can not change the look of or the palette of the Guard sprite only the Held or
# thrown sprite"; "Make sure you can also change the look in the New Items card of the New Content page as well") A
# shield's look as it guards, in Attack's place: its sprite pair too (`mod_items.SWING_PALETTES`' note).
GUARD_FIELD_LABEL = "Guard"
GUARD_FIELD_NOTE = "The sprite a unit guards with in battle."
GUARD_DIALOG_TITLE = "Guard: {item}"
GUARD_DIALOG_INTRO = "Click the sprite a unit guards with and choose its palette."
#: A game item the tables name none, in the looks' dialog: by its number.
ITEM_NUMBERED = "item {n}"
# (Zodi, 3 November: "if Palette and Sprite Id do nothing in Enhanced we should remove those field options and in its
# place put a new field that allows the user to change the Sprite and Palette and have the preview update showing the
# users changes. I only want to support Enhanced at this time"; measured, in Enhanced they still choose the icon a
# unit holds up or throws, so his choice "One picker"): one field for both, the icon clicked on the enhanced item
# texture and one of its 16 palettes, the Battle Sprite showing it staged; (4 November) named for its half.
HELD_FIELD_LABEL = "Held or thrown"
HELD_FIELD_NOTE = "The sprite a unit holds up or throws in battle."
HELD_PALETTE_CHOICE = "Palette {n}"
HELD_CHOOSE = "Choose an icon"
HELD_PICKED = "Sprite {sprite}, palette {palette}"
HELD_MISSING = "Choosing an icon needs the unpacked game folder (General Setup): {problem}."
HELD_UNDRAWN = "Its icon can't be drawn ({problem}): choose one."
HELD_DIALOG_TITLE = "Held or thrown: {item}"
HELD_DIALOG_INTRO = ("Click the sprite a unit holds up or throws in battle (a Treasure Hunter's find, an item used, a "
                     "bomb in flight), and choose its palette.")
# (after test 61) An item as the game draws it in battle beside its two textures (Zodi, 3 November: "display how it
# would look from the items page alongside the Sprite Texture preview and the Art Texture preview to show what their
# choices would look like ingame"; then "rename "Battle Texture" to "Battle Sprite"", and every item, as "when using
# treasure hunter units pick the items and swing them over their head"): a weapon as it attacks and a shield as it
# guards, from the weapons' texture by its sprite pair; every item as a unit holds it up or throws it, its icon in
# ITEM.BIN by its Palette and Sprite Id (`unit_sprites.BattleSprites`).
BATTLE_SPRITE_TITLE = "Battle Sprite"
BATTLE_GAME_CAPTION = "In the game"
BATTLE_STAGED_CAPTION = "Staged"
BATTLE_ATTACK = "Attack"
BATTLE_GUARD = "Guard"
BATTLE_HELD = "Held or thrown"
BATTLE_MISSING = "The battle sprite needs the unpacked game folder (General Setup): {problem}."
#: Its files read, what its data asks for isn't in them (a palette past the 16, a sprite past the texture's icons).
BATTLE_UNDRAWN = "The battle sprite can't be drawn: {problem}."
#: What its panel says when a file it is drawn from isn't there (the texture slots' words); why, in its tooltip.
BATTLE_NO_FILE = "No file here"
#: (Zodi, 4 November: "it does not show anything when there is nothing to show while the Art Texture and Sprite
#: Texture preview says "Nothing staged"") Its Staged panel while the mod changes neither half: the texture slots'
#: words.
BATTLE_NOTHING_STAGED = "Nothing staged"
#: The room each part of a Battle Sprite panel has, side by side, as large as the texture slots' panels above it
#: allow.
BATTLE_SIZES = {"look": (72, 48), "held": (32, 32)}

#: (Zodi after test 62: "you can not set at what point in the story the item becomes available") The story's points
#: the shops sell an item from (the record's + 10, 1 to 16), in words, the names the remaster's (CharaName,
#: PlaceName): the New Content page's item card's Sold from; (Zodi, 5 November: "Can we alter the Shop Availability
#: names in the UI. They use the PSX names instead of The Ivalice Chronicles names. Furthermore there is not space
#: between the Chapter and its number"; his choice "As Sold from says them") the Items page's Shop Availability too.
SHOP_POINT_WORDS = {1: "Chapter 1, from its start", 2: "Chapter 1, Eagrose reached", 3: "Chapter 1, Elmdore rescued",
                    4: "Chapter 1, Milleuda defeated", 5: "Chapter 2, from its start", 6: "Chapter 2, Ovelia rescued",
                    7: "Chapter 2, Delacroix met", 8: "Chapter 2, Agrias rescued", 9: "Chapter 3, from its start",
                    10: "Chapter 3, Zalmour", 11: "Chapter 3, Belias met", 12: "Chapter 3, Rapha rescued",
                    13: "Chapter 4, from its start", 14: "Chapter 4, Fort Besselat", 15: "Chapter 4, Elmdore defeated",
                    16: "Chapter 4, Zalbaag defeated"}
#: (his choice "Say what they do") Shop Availability's 0, which the story's point (1 to 16, as its scenes set it) has
#: reached from a new game, and 17 to 20, which it never reaches, so an item with one is never sold (55 of the game's
#: items have 20: the Zwill Straightblade, Excalibur and the other rare ones).
SHOP_POINT_START = "From a new game"
SHOP_POINT_NEVER = "Never sold ({n})"


def shop_availability_words(value: str) -> str:
    """Shop Availability's value (the mod loader's name, `constants.ITEM_SHOP_AVAILABILITY`, which the files keep) in
    the page's words: the story's point it names, as the item card's Sold from says it."""
    if value not in c.ITEM_SHOP_AVAILABILITY:
        return value
    n = c.ITEM_SHOP_AVAILABILITY.index(value)
    if n == 0:
        return SHOP_POINT_START
    return SHOP_POINT_WORDS.get(n) or SHOP_POINT_NEVER.format(n=n)


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
        # Rows alternate dark and light, as the Map Editor's map list does.
        self.list.setAlternatingRowColors(True)
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
        # (The twenty fifth session, 16 November 2026: Zodi's first point of that day, "edited on the Items page";
        # his "Always listed (Recommended)" and, for how one is edited, "I go with your recommendations") War of the
        # Lions' 40 items are listed after the game's, and one picked is edited on the New Content page's item
        # sheet, shown here in the form's place (`lion_items`: its notes say why the sheet and not this form).
        # Made here and not at the module's top: that module leans on this one.
        from .lion_items import LionItemPane
        self.lion_pane = LionItemPane(state)
        self.lion_pane.setVisible(False)
        self.lion_pane.changed.connect(self._after_edit)
        self.lion_pane.named.connect(self._relabel_lions)
        right.addWidget(self.lion_pane, 1)
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

        # (Zodi, 4 November) The Battle Sprite's two halves, side by side at the top: Attack, a game weapon's look as
        # it attacks (shown for one), and Held or thrown, any item's (its Palette and Sprite Id).
        self.battle_fields = QGroupBox(BATTLE_FIELDS_TITLE)
        battle_column = QVBoxLayout(self.battle_fields)
        battle_column.setSpacing(2)
        self.attack_row = AttackLookRow(self.battle_sprites, self._held_item_name, self._look_name,
                                        category_of=self._game_category)
        self.attack_row.edited.connect(self._on_look_edited)
        battle_column.addWidget(self.attack_row)
        battle_column.addWidget(self._make_base_row(HELD_FIELD))
        column.addWidget(self.battle_fields)

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
        if field_name == HELD_FIELD:
            # Zodi's one field for Palette and Sprite Id (Held or thrown), the two to its load and commit.
            self.held_row = HeldSpriteRow(self.battle_sprites, self._held_baseline, self._held_item_name)
            self.held_row.edited.connect(self._on_base_edited)
            self.base_rows.update(self.held_row.parts)
            return self.held_row
        if field_name == "TypeFlags":
            row = FlagFieldPanel("TypeFlags", "Type",
                                 {"Type": c.ITEM_TYPE_FLAGS}, columns=1)
            # Changing the type changes which table Additional Data means,
            # so this one rebuilds the section rather than only committing.
            row.edited.connect(self._on_type_flags_edited)
        elif field_name == "ItemCategory":
            row = _EnumRow("ItemCategory", "Item Category", c.ITEM_CATEGORIES)
            row.edited.connect(self._on_base_edited)
            # (1.28.0) The type decides which looks it may swing.
            row.edited.connect(self.refresh_look)
        elif field_name == "ShopAvailability":
            # (Zodi, 5 November) Its story points as the New Content page's item card says them.
            row = _EnumRow("ShopAvailability", "Shop Availability",
                           c.ITEM_SHOP_AVAILABILITY, words=shop_availability_words)
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
        column.addWidget(self._build_battle_sprite())

        hint = QLabel("Right-click a texture to edit.")
        hint.setProperty("role", "muted")
        hint.setWordWrap(True)
        column.addWidget(hint)
        column.addStretch(1)
        holder.setFixedWidth(250)
        return holder

    def _build_battle_sprite(self) -> QWidget:
        """(after test 61) The item as the game draws it in battle, in the game and as the mod stages it, laid out as
        the two texture slots above it: a weapon as it attacks or a shield as it guards, and any item as a unit holds
        it up or throws it."""
        from ..widgets.texture_slot import SLOT_PREVIEW_SIZE
        self.battle_box = QWidget()
        column = QVBoxLayout(self.battle_box)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(4)
        title = QLabel(BATTLE_SPRITE_TITLE)
        title.setStyleSheet("font-weight: 600;")
        column.addWidget(title)
        from PySide6.QtWidgets import QStackedWidget
        panels = QHBoxLayout()
        panels.setSpacing(6)
        self.battle_views = {}
        self.battle_stacks = {}
        for side, caption in (("game", BATTLE_GAME_CAPTION), ("staged", BATTLE_STAGED_CAPTION)):
            box = QFrame()
            box.setFrameShape(QFrame.StyledPanel)
            inner = QVBoxLayout(box)
            inner.setContentsMargins(6, 4, 6, 4)
            inner.setSpacing(2)
            label = QLabel(caption)
            label.setProperty("role", "muted")
            inner.addWidget(label)
            # A weapon's or a shield's look, then the item held or thrown, side by side; each named by its
            # tooltip, as the panels have no room for words beside the texture slots.
            pair_holder = QWidget()
            pair = QHBoxLayout(pair_holder)
            pair.setContentsMargins(0, 0, 0, 0)
            pair.setSpacing(2)
            for part in ("look", "held"):
                view = QLabel("")
                view.setAlignment(Qt.AlignCenter)
                view.setFixedSize(*BATTLE_SIZES[part])
                pair.addWidget(view)
                self.battle_views[(side, part)] = view
            # (Zodi, 4 November) Or, in the same room, the words its panel shows when it has nothing to draw, as
            # the texture slots' panels say "Nothing staged".
            said = QLabel("")
            said.setAlignment(Qt.AlignCenter)
            stack = QStackedWidget()
            stack.addWidget(pair_holder)
            stack.addWidget(said)
            stack.setFixedSize(sum(w for w, _h in BATTLE_SIZES.values()) + pair.spacing(),
                               max(h for _w, h in BATTLE_SIZES.values()))
            self.battle_stacks[side] = (stack, said)
            inner.addWidget(stack)
            inner.addStretch(1)
            panels.addWidget(box)
        panels.addStretch(1)
        column.addLayout(panels)
        # Shown from the start and always the same height, so the half of the page it is in opens as tall as the
        # texture column (the Items page's measure): what kept a sprite from being drawn goes in its tooltip, and its
        # panel says only that a file isn't there, as the texture slots' panels do.
        self._battle_sprites, self._battle_sprites_key = None, None
        return self.battle_box

    def battle_sprites(self):
        """The unpacked game's battle sprites (`unit_sprites.BattleSprites`), read again when its files change."""
        from ... import unit_sprites as us
        root = getattr(self.state, "nxd_unpack_dir", None)
        game = Path(root) if root and Path(root).is_dir() else None
        if game is None:
            return None

        def stamp(path):
            try:
                return path.stat().st_mtime_ns
            except OSError:
                return None
        key = (str(game), stamp(game / us.WEAPON_SPR_FILE), stamp(game / us.ITEM_BIN_FILES[0]),
               stamp(game / us.G2D_FILE))
        if key != self.__dict__.get("_battle_sprites_key"):
            self._battle_sprites, self._battle_sprites_key = us.BattleSprites(game), key
        return self._battle_sprites

    def _held_baseline(self) -> tuple:
        """The item's Palette and Sprite Id as the data has them, without this mod's edit."""
        return self._base_number("Palette", False), self._base_number("SpriteID", False)

    def _held_item_name(self) -> str:
        if self.current_item_id is None:
            return ""
        return re.sub(r"^\d+ - ", "", self._display_name(self.current_item_id)) or str(self.current_item_id)

    @staticmethod
    def _sprite_pixmap(picture, width: int, height: int):
        """A battle sprite drawn and fitted to `width` by `height` (a whole number of times its size, its pixels kept
        sharp), or None."""
        from PySide6.QtGui import QImage, QPixmap
        if picture is None:
            return None
        image = QImage(picture.rgba, picture.width, picture.height, picture.width * 4,
                       QImage.Format_RGBA8888).copy()
        across, down = max(1, picture.width), max(1, picture.height)
        if across <= width and down <= height:
            times = min(width // across, height // down)
            size = (across * times, down * times)
        else:
            # Larger than its room (an enhanced look's spear): a whole number of times smaller.
            parts = max(-(-across // width), -(-down // height))
            size = (max(1, across // parts), max(1, down // parts))
        return QPixmap.fromImage(image.scaled(size[0], size[1], Qt.IgnoreAspectRatio, Qt.FastTransformation))

    def _base_number(self, field_name: str, staged: bool) -> int:
        """A base field's number for the item shown: the form's when it is ticked (`staged`), or the item's as the
        data has it without this mod's edit; -1 when it isn't a number."""
        if staged and self.base_rows[field_name].included:
            raw = self.base_rows[field_name].get_value_str()
        else:
            record = self.state.item_table_records_by_id("item").get(self.current_item_id)
            raw = (record.values if record else {}).get(field_name, "0")
        try:
            return int(raw)
        except (TypeError, ValueError):
            return -1

    def _show_sprite(self, side: str, part: str, picture, name: str) -> None:
        view = self.battle_views[(side, part)]
        drawn = self._sprite_pixmap(picture, *BATTLE_SIZES[part])
        if drawn is None:
            view.clear()
            view.setToolTip("")
        else:
            view.setPixmap(drawn)
            view.setToolTip(name)

    def _say_in_panel(self, side: str, words: str) -> None:
        """(4 November) A Battle Sprite panel's words in place of its two parts (the texture slots' "Nothing staged"),
        or its parts again when `words` is empty."""
        stack, said = self.battle_stacks[side]
        said.setText(words)
        stack.setCurrentIndex(1 if words else 0)

    def refresh_battle_sprite(self) -> None:
        """The Battle Sprite for the item shown: in the game, and staged once the mod changes any part of it (a
        weapon's look under Attack, any item's under Held or thrown), whole: each part as staged, or as the game has
        it (Zodi after test 62: the staged attack never showed when only the icon changed). (Zodi, 4 November) Its
        Staged panel says "Nothing staged" while the mod changes neither, as the texture slots' panels do; with no
        item shown, both panels empty, as theirs are. (Zodi, 5 November) Item 000, Nothing Equipped, is an item
        shown: its number 0 is not "no item" (its panels were left empty, and Held or thrown kept the icon of the
        item shown before it)."""
        from ... import mod_items as mi
        from ... import unit_sprites as us
        item_id = self.current_item_id
        for key in self.battle_views:
            self._show_sprite(key[0], key[1], None, "")
        for side in self.battle_stacks:
            self._say_in_panel(side, "")
        self.battle_box.setToolTip("")
        if item_id is None:
            return
        # (Held or thrown) its icon as the form has it.
        self.held_row.refresh()
        sprites = self.battle_sprites()
        problems, undrawn = [], []
        flags = ix.parse_flag_value(self.base_rows["TypeFlags"].get_value_str() or "")
        category = self._category_now()
        kind = us.sprite_kind(flags, category)
        look_part = None                 # (its name, as staged) when the item attacks or guards
        look_changed = held_changed = False
        # A thrown item's look in flight is its icon, held up or thrown.
        if kind in ("attack", "guard") and item_id in mi.GAME_ITEMS and sprites is not None:
            game, _why = self.game_items()
            own = bytes(game.item(item_id).sprite_pair) if game is not None else b""
            if len(own) == mi.PAIR_BYTES:
                frames = us.frames_type(kind, category)
                name = BATTLE_ATTACK if kind == "attack" else BATTLE_GUARD
                look = sprites.attack(frames, own)
                self._show_sprite("game", "look", look, name)
                staged = (getattr(self.state, "item_looks", None) or {}).get(item_id)
                look_changed = bool(staged) and bytes(staged) != own
                look_part = (name, sprites.attack(frames, bytes(staged)) if look_changed else look)
                if look is None:
                    (undrawn if sprites.weapons_drawable else problems).append(sprites.problem)
        held_staged = None
        if sprites is not None:
            palette, sprite = self._base_number("Palette", False), self._base_number("SpriteID", False)
            held = sprites.held(palette, sprite)
            self._show_sprite("game", "held", held, BATTLE_HELD)
            if held is None:
                (undrawn if sprites.items_drawable else problems).append(sprites.item_problem)
            changed = (self._base_number("Palette", True), self._base_number("SpriteID", True))
            held_changed = changed != (palette, sprite)
            held_staged = sprites.held(*changed) if held_changed else held
            if held_changed and held_staged is None:
                (undrawn if sprites.items_drawable else problems).append(sprites.item_problem)
        else:
            problems.append("it isn't set")
        if look_changed or held_changed:
            if look_part is not None:
                self._show_sprite("staged", "look", look_part[1], look_part[0])
            self._show_sprite("staged", "held", held_staged, BATTLE_HELD)
        else:
            self._say_in_panel("staged", BATTLE_NOTHING_STAGED)
        missing = [BATTLE_MISSING.format(problem=p) for p in dict.fromkeys(p for p in problems if p)]
        look_view = self.battle_views[("game", "look")]
        if missing and (look_view.pixmap() is None or look_view.pixmap().isNull()):
            look_view.setText(BATTLE_NO_FILE)
        self.battle_box.setToolTip(" ".join(missing + [BATTLE_UNDRAWN.format(problem=p)
                                                       for p in dict.fromkeys(p for p in undrawn if p)]))

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
        retire(old)
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
        if wl.is_one(item_id):
            # One of War of the Lions' 40: its name as the mod has it.
            from .lion_items import LISTED
            return LISTED.format(number=item_id, name=self.lion_pane.name_of(item_id))
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
        # (16 November 2026) War of the Lions' 40 after the game's, for every mod (his "Always listed").
        for number in (self.lion_numbers() if records else ()):
            item = QListWidgetItem(self._display_name(number))
            item.setData(Qt.UserRole, number)
            self.list.addItem(item)

        has_data = bool(records)
        set_empty_state(
            self.empty_note, has_data,
            self.body, self.search, self.list, self.editing_label,
            self.language_controls, self.counter)
        if not has_data:
            self.lion_pane.setVisible(False)
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

    def lion_numbers(self) -> tuple:
        """War of the Lions' 40 items' numbers, as the list has them after the game's items."""
        return wl.numbers()

    def is_lion(self, item_id) -> bool:
        """Whether an item of the list is one of War of the Lions' 40 (edited on the sheet, not this form)."""
        return wl.is_one(item_id)

    def _relabel_lions(self) -> None:
        """The 40's lines of the list, and the title over one shown, said again (one was renamed)."""
        for i in range(self.list.count()):
            item = self.list.item(i)
            if self.is_lion(item.data(Qt.UserRole)):
                item.setText(self._display_name(item.data(Qt.UserRole)))
        if self.is_lion(self.current_item_id):
            self.editing_label.setText(f"Editing: {self._display_name(self.current_item_id)}")
        self._filter_list(self.search.text())

    def load_record(self, item_id: int) -> None:
        lion = self.is_lion(item_id)
        # The form for one of the game's items, the sheet for one of War of the Lions': one of the two shown. The
        # language's copy button is the form's (the 40 have one set of words).
        self.body.setVisible(not lion)
        self.lion_pane.setVisible(lion)
        self.copy_button.setEnabled(not lion)
        if lion:
            self.current_item_id = item_id
            self.editing_label.setText(f"Editing: {self._display_name(item_id)}")
            self.lion_pane.show_item(item_id)
            return
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
            self.refresh_look()
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
        # (after test 61) Palette and Sprite Id draw the item held up or thrown.
        self.refresh_battle_sprite()
        self._after_edit()

    def _on_type_flags_edited(self) -> None:
        self._on_base_edited()
        if not self._loading:
            self.rebuild_linked_section()
            self.refresh_look()

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

    # -- (1.28.0) a weapon's look in battle ----------------------------------

    def find_program(self):
        """The game's program, from the folder of .pac files General Setup has (as the Side Quests page finds it)."""
        from ... import game_install
        from ... import ui_settings
        return game_install.find_program(ui_settings.load().get("game_data_folder") or None)

    def game_items(self) -> tuple:
        """(the game's items read from its program, `mod_items.GameItems`, or None; why not, in words)."""
        from ... import mod_items as mi
        path = self.find_program()
        if path is None:
            return None, "it isn't found"
        try:
            return mi.game_items(path), ""
        except (OSError, mi.ItemsError) as exc:
            return None, str(exc)

    def _category_now(self) -> int:
        """The item's type as the form has it (its Item Category), as the game numbers it; -1 when unknown."""
        name = self.base_rows["ItemCategory"].get_value_str()
        return c.ITEM_CATEGORIES.index(name) if name in c.ITEM_CATEGORIES else -1

    def _look_basis(self):
        """(its game sprite pair, the looks it may take) for the item shown, or (None, why) when it has no look here
        (not a weapon or (5 November) a shield now, not one of the game's, or no program)."""
        from ... import mod_items as mi
        item_id = self.current_item_id
        flags = ix.parse_flag_value(self.base_rows["TypeFlags"].get_value_str() or "")
        if item_id is None or not ({"Weapon", "Shield"} & set(flags)):
            return None, ""
        if item_id not in mi.GAME_ITEMS:
            return None, LOOK_NOT_GAME
        game, why = self.game_items()
        if game is None:
            return None, LOOK_NO_PROGRAM.format(problem=why)
        try:
            own = mi.game_look(game, item_id)
            category = self._category_now()
            looks = mi.looks_of(game, category if category >= 0 else game.item(item_id).record[mi.CATEGORY_AT])
        except mi.ItemsError as exc:
            return None, LOOK_NO_PROGRAM.format(problem=exc)
        if not own:
            return None, LOOK_NOT_GAME
        return (own, looks), ""

    def _look_name(self, number: int) -> str:
        """A game weapon's name as the list names it, without its number (the looks' dialog's and Attack's words)."""
        return re.sub(r"^\d+ - ", "", self._display_name(number)) or ITEM_NUMBERED.format(n=number)

    def _game_category(self, number: int):
        """(4 November) One of the game's items' category as its program has it (the looks' dialog's sections), or
        None without the program."""
        from ... import mod_items as mi
        game, _why = self.game_items()
        if game is None:
            return None
        try:
            return game.item(number).record[mi.CATEGORY_AT]
        except mi.ItemsError:
            return None

    def refresh_look(self) -> None:
        """Attack, for the item shown: shown for a weapon, its look the mod's when it changes it (`state.item_looks`),
        else the game's own, ticked when the mod changes it; for a weapon whose look can't be changed here, why (in
        its note); (5 November) Guard for a shield, the same way; for anything else, hidden (Held or thrown beside it
        stays)."""
        from ... import unit_sprites as us
        if self.current_item_id is None:
            self.attack_row.setVisible(False)
            self.refresh_battle_sprite()
            return
        basis, why = self._look_basis()
        flags = ix.parse_flag_value(self.base_rows["TypeFlags"].get_value_str() or "")
        kind = us.sprite_kind(flags, self._category_now())
        self.attack_row.set_guard(kind == "guard")
        self.attack_row.setVisible(basis is not None or (bool(why) and bool({"Weapon", "Shield"} & set(flags))))
        was_loading = self._loading
        self._loading = True
        try:
            if basis is None:
                self.attack_row.unavailable(why)
            else:
                own, looks = basis
                changed = (getattr(self.state, "item_looks", None) or {}).get(self.current_item_id)
                pair = bytes(changed) if changed else own
                category = self._category_now()
                guard = kind == "guard"
                self.attack_row.load(own, pair, looks, us.frames_type("guard" if guard else "attack", category),
                                     bool(changed) and pair != own, guard=guard)
        finally:
            self._loading = was_loading
        self.refresh_battle_sprite()

    def _on_look_edited(self) -> None:
        """Attack (or a shield's Guard) changed (a look or a palette taken, or unticked): the mod's look for it the
        row's, none when it comes back to the game's own."""
        if self._loading or self.current_item_id is None:
            return
        basis, _why = self._look_basis()
        if basis is None:
            return
        own, _looks = basis
        pair = self.attack_row.pair if self.attack_row.included else own
        looks_store = getattr(self.state, "item_looks", None)
        if looks_store is None:
            looks_store = self.state.item_looks = {}
        if pair == own:
            looks_store.pop(self.current_item_id, None)
        else:
            looks_store[self.current_item_id] = bytes(pair)
        self.refresh_look()
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
        if self.current_item_id is None or self.is_lion(self.current_item_id):
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
        if self.is_lion(item_id):
            # (16 November 2026) One of War of the Lions' 40: the mod has its own version of it.
            return item_id in (getattr(self.state, "wotl_items", None) or {})
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
        # (1.28.0) Its look in battle.
        if item_id in (getattr(self.state, "item_looks", None) or {}):
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
        # (16 November 2026) And War of the Lions' 40 the mod has its own version of, where they are listed.
        if self.records():
            edited += sum(1 for number in self.lion_numbers() if self._is_edited(number))
        self.counter.setText(
            edit_counter_text(edited, self.list.count(), "items"))

    # -- view toggles -------------------------------------------------------

    def _apply_view(self, hide_notes: bool, hide_unknown: bool,
                    hide_comments: bool) -> None:
        rows = (list(self.text_rows.values()) + list(self.base_rows.values())
                + list(self.linked_rows.values()) + [self.shops_row, self.attack_row, self.held_row])
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

    def __init__(self, field_name: str, label: str, values: list, parent=None, words=None):
        super().__init__(field_name, label, parent=parent)
        #: (Zodi, 5 November) How each value is said, when not by its name spaced (Shop Availability's story points).
        self._words = words
        self.set_enum_choices(values)

    def _said(self, value: str) -> str:
        from ..widgets.field_rows import split_words
        return self._words(value) if self._words is not None else split_words(value)

    def set_enum_choices(self, values: list) -> None:
        self._loading = True
        try:
            self.combo.clear()
            self._id_to_index = {}
            for index, value in enumerate(values):
                self.combo.addItem(self._said(value), value)
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
                # A value this build has no name for is shown as itself
                # rather than snapping to the first entry, which would
                # rewrite the mod's category to "None" on open.
                self.combo.addItem(self._said(value) or "(blank)", value)
                self._id_to_index[value] = self.combo.count() - 1
            self.combo.setCurrentIndex(self._id_to_index[value])
            self.include.setChecked(bool(included))
        finally:
            self._loading = False

    def _sync_jump(self) -> None:
        return


# =============================================================================
# Held or thrown (first Sprite and Palette): the icon a unit holds up or throws, picked
# =============================================================================

def _picture_pixmap(picture, times: int = 1):
    """A battle sprite (`unit_sprites.Picture`) as a pixmap `times` its size, its pixels kept sharp; None for none."""
    if picture is None:
        return None
    image = QImage(picture.rgba, picture.width, picture.height, picture.width * 4, QImage.Format_RGBA8888).copy()
    if times != 1:
        image = image.scaled(picture.width * times, picture.height * times, Qt.IgnoreAspectRatio,
                             Qt.FastTransformation)
    return QPixmap.fromImage(image)


class _HeldPart:
    """
    Palette or Sprite Id as the page's load and commit see a row: its number
    and whether it is ticked, both kept by the Held or thrown field
    (`HeldSpriteRow`). Not a widget: the field is what the page shows, so
    the view toggles never show these.
    """

    is_unknown = is_comment = False

    def __init__(self, owner: "HeldSpriteRow", field_name: str):
        self.owner, self.field_name = owner, field_name

    @property
    def included(self) -> bool:
        return self.owner.ticked[self.field_name]

    def get_value_str(self) -> str:
        return str(self.owner.numbers[self.field_name])

    def load(self, raw_value, included: bool) -> None:
        self.owner.load_part(self.field_name, raw_value, included)


class HeldSpriteRow(QWidget):
    """
    `[x] Held or thrown  [icon] [Palette n] [Choose an icon]  note`

    Zodi's one field for Palette and Sprite Id (3 November): the icon a unit
    holds up or throws in battle, drawn from the enhanced item texture in its
    palette; the palette chosen here, the icon in a dialog of the texture's
    icons (`HeldSpriteDialog`). One tick for both: picking either ticks it,
    and unticking puts both back as the game has them. `edited` as the
    page's rows emit it, never while loading.
    """

    edited = Signal()

    def __init__(self, sprites_of, baseline_of, item_name_of, parent=None):
        super().__init__(parent)
        self.field_name = HELD_FIELD
        self.is_unknown = self.is_comment = False
        self._sprites_of, self._baseline_of, self._item_name_of = sprites_of, baseline_of, item_name_of
        self._loading = False
        self.numbers = {"Palette": 0, "SpriteID": 0}
        self.ticked = {"Palette": False, "SpriteID": False}
        self.parts = {name: _HeldPart(self, name) for name in HELD_PARTS}
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 1, 0, 1)
        row.setSpacing(8)
        self.include = QCheckBox()
        self.include.setToolTip(
            "Tick to write this field into your mod. Unticked fields are "
            "left alone, so other mods can change them.")
        self.include.toggled.connect(self._on_include_toggled)
        row.addWidget(self.include)
        self.label = QLabel(HELD_FIELD_LABEL)
        self.label.setFixedWidth(200)
        row.addWidget(self.label)
        self.icon = QLabel()
        # (4 November) As wide as Attack's look above it, so their palettes and buttons line up.
        self.icon.setFixedSize(FIELD_PICTURE[0], 32)
        self.icon.setAlignment(Qt.AlignCenter)
        row.addWidget(self.icon)
        self.palette_box = QComboBox()
        for number in range(16):
            self.palette_box.addItem(HELD_PALETTE_CHOICE.format(n=number), number)
        self.palette_box.currentIndexChanged.connect(self._on_palette_chosen)
        row.addWidget(self.palette_box)
        self.choose = QPushButton(HELD_CHOOSE)
        self.choose.clicked.connect(self.choose_icon)
        row.addWidget(self.choose)
        self._note_text = HELD_FIELD_NOTE
        self.note = QLabel(HELD_FIELD_NOTE)
        self.note.setProperty("role", "muted")
        self.note.setWordWrap(False)
        self.note.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.note.setToolTip(HELD_FIELD_NOTE)
        row.addWidget(self.note, 1)
        self.setProperty("fieldRow", True)
        self.setProperty("unknownField", False)

    # -- the page's load and commit, through `parts` ------------------------

    @property
    def included(self) -> bool:
        return self.include.isChecked()

    def load_part(self, field_name: str, raw_value, included: bool) -> None:
        try:
            self.numbers[field_name] = int(str(raw_value).strip() or 0)
        except (TypeError, ValueError):
            self.numbers[field_name] = 0
        self.ticked[field_name] = bool(included)
        self._show_numbers()

    def _show_numbers(self) -> None:
        self._loading = True
        try:
            self.include.setChecked(any(self.ticked.values()))
            index = self.palette_box.findData(self.numbers["Palette"])
            self.palette_box.setCurrentIndex(index)
        finally:
            self._loading = False

    def _set(self, palette: int, sprite: int) -> None:
        """The user's pick: both numbers, both ticked, then `edited`."""
        self.numbers["Palette"], self.numbers["SpriteID"] = int(palette), int(sprite)
        self.ticked = {name: True for name in HELD_PARTS}
        self._show_numbers()
        self.edited.emit()

    # -- interaction --------------------------------------------------------

    def _on_palette_chosen(self, _index) -> None:
        if self._loading or self.palette_box.currentData() is None:
            return
        self._set(self.palette_box.currentData(), self.numbers["SpriteID"])

    def _on_include_toggled(self, on: bool) -> None:
        if self._loading:
            return
        if on:
            self.ticked = {name: True for name in HELD_PARTS}
        else:
            # Unticked: left alone, so shown as the game has them.
            self.ticked = {name: False for name in HELD_PARTS}
            palette, sprite = self._baseline_of()
            self.numbers["Palette"], self.numbers["SpriteID"] = palette, sprite
            self._show_numbers()
        self.edited.emit()

    def ask(self, palette: int, sprite: int):
        """The icon dialog over the enhanced item texture: (palette, sprite) picked, or None."""
        sprites = self._sprites_of()
        dialog = HeldSpriteDialog(sprites, palette, sprite, self._item_name_of(), self)
        return dialog.choice() if dialog.exec() else None

    def choose_icon(self) -> None:
        picked = self.ask(self.numbers["Palette"], self.numbers["SpriteID"])
        if picked is not None:
            self._set(*picked)

    # -- what it shows ------------------------------------------------------

    def refresh(self) -> None:
        """Its icon as its numbers draw it, from the unpacked game's enhanced item texture; why not, in its note."""
        sprites = self._sprites_of()
        picture, problem = None, "it isn't set"
        if sprites is not None:
            picture = sprites.held(self.numbers["Palette"], self.numbers["SpriteID"])
            problem = "" if picture is not None else sprites.item_problem
        drawn = _picture_pixmap(picture)
        if drawn is None:
            self.icon.clear()
        else:
            self.icon.setPixmap(drawn)
        self.icon.setToolTip(HELD_PICKED.format(sprite=self.numbers["SpriteID"], palette=self.numbers["Palette"]))
        # Choosing needs the texture; a palette past the 16 or a sprite past the texture's icons can still be picked
        # anew from it.
        readable = sprites is not None and sprites.items_drawable
        self.choose.setEnabled(readable)
        if not readable:
            self._note_text = HELD_MISSING.format(problem=problem)
        elif picture is None:
            self._note_text = HELD_UNDRAWN.format(problem=problem)
        else:
            self._note_text = HELD_FIELD_NOTE
        self._show_note()

    def _show_note(self) -> None:
        hidden = getattr(self, "_hide_notes", False)
        self.note.setText("" if hidden else self._note_text)
        self.note.setToolTip(self._note_text)

    def apply_display(self, hide_notes: bool, hide_unknown: bool, hide_comments: bool) -> None:
        """The view toggles: its note emptied with the others' (never unknown, never a comment)."""
        self._hide_notes = bool(hide_notes)
        self._show_note()


class _IconGrid(QLabel):
    """The enhanced item texture's icons, 32 by 32 each; a click picks one (`picked`, its Sprite Id), a double click
    takes it (`chosen`). The icon picked is framed."""

    picked = Signal(int)
    chosen = Signal(int)

    def __init__(self, parent=None):
        from ... import unit_sprites as us
        super().__init__(parent)
        self._columns, self._rows = us.ITEM_COLUMNS, us.ITEM_ROWS
        self._size = us.ITEM_ICON * us.ENHANCED_SCALE
        self.setFixedSize(self._columns * self._size, self._rows * self._size)
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.selected = -1

    def sprite_at(self, x: int, y: int) -> int:
        column, row = x // self._size, y // self._size
        if not (0 <= column < self._columns and 0 <= row < self._rows):
            return -1
        return row * self._columns + column

    def place_of(self, sprite: int) -> QRect:
        return QRect((sprite % self._columns) * self._size, (sprite // self._columns) * self._size,
                     self._size, self._size)

    def set_selected(self, sprite: int) -> None:
        self.selected = sprite
        self.update()

    def mousePressEvent(self, event):                                     # noqa: N802
        sprite = self.sprite_at(int(event.position().x()), int(event.position().y()))
        if sprite >= 0:
            self.set_selected(sprite)
            self.picked.emit(sprite)

    def mouseDoubleClickEvent(self, event):                               # noqa: N802
        sprite = self.sprite_at(int(event.position().x()), int(event.position().y()))
        if sprite >= 0:
            self.chosen.emit(sprite)

    def paintEvent(self, event):                                          # noqa: N802
        super().paintEvent(event)
        if self.selected < 0:
            return
        painter = QPainter(self)
        painter.setPen(QPen(QColor("#f0c040"), 2))
        painter.drawRect(self.place_of(self.selected).adjusted(1, 1, -1, -1))
        painter.end()


class HeldSpriteDialog(QDialog):
    """
    Held or thrown's icons (Zodi, 3 November): the enhanced item texture's
    icons in the palette chosen, the one picked framed and shown twice its
    size; OK takes it (`choice`).
    """

    def __init__(self, sprites, palette: int, sprite: int, item_name: str, parent=None):
        from ... import unit_sprites as us
        super().__init__(parent)
        self.setWindowTitle(HELD_DIALOG_TITLE.format(item=item_name))
        self._sprites = sprites
        self._palette = palette if 0 <= palette < us.ITEM_PALETTES else 0
        self._sprite = sprite if 0 <= sprite < us.ITEM_ICONS else 0
        column = QVBoxLayout(self)
        intro = QLabel(HELD_DIALOG_INTRO)
        intro.setWordWrap(True)
        column.addWidget(intro)
        top = QHBoxLayout()
        self.palette_box = QComboBox()
        for number in range(us.ITEM_PALETTES):
            self.palette_box.addItem(HELD_PALETTE_CHOICE.format(n=number), number)
        self.palette_box.setCurrentIndex(self._palette)
        self.palette_box.currentIndexChanged.connect(self._palette_chosen)
        top.addWidget(self.palette_box)
        self.preview = QLabel()
        self.preview.setFixedSize(64, 64)
        self.preview.setAlignment(Qt.AlignCenter)
        top.addWidget(self.preview)
        self.picked_label = QLabel()
        top.addWidget(self.picked_label, 1)
        column.addLayout(top)
        self.grid = _IconGrid()
        self.grid.picked.connect(self._sprite_picked)
        self.grid.chosen.connect(self._sprite_taken)
        column.addWidget(self.grid)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        column.addWidget(buttons)
        self._draw()

    def choice(self) -> tuple:
        return self._palette, self._sprite

    def _palette_chosen(self, _index) -> None:
        self._palette = int(self.palette_box.currentData())
        self._draw()

    def _sprite_picked(self, sprite: int) -> None:
        self._sprite = sprite
        self._draw()

    def _sprite_taken(self, sprite: int) -> None:
        self._sprite = sprite
        self.accept()

    def _draw(self) -> None:
        sheet = self._sprites.icon_sheet(self._palette) if self._sprites is not None else None
        drawn = _picture_pixmap(sheet)
        if drawn is None:
            self.grid.clear()
        else:
            self.grid.setPixmap(drawn)
        self.grid.set_selected(self._sprite)
        held = self._sprites.held(self._palette, self._sprite) if self._sprites is not None else None
        icon = _picture_pixmap(held, 2)
        if icon is None:
            self.preview.clear()
        else:
            self.preview.setPixmap(icon)
        self.picked_label.setText(HELD_PICKED.format(sprite=self._sprite, palette=self._palette))


# =============================================================================
# (Zodi, 4 November) Attack: a game weapon's look as it attacks, chosen as Held or thrown is
# =============================================================================

def swing_palette_box(value: int) -> QComboBox:
    """The palettes a weapon's look is offered in (`mod_items.SWING_PALETTES`, the game's own weapons'), `value` among
    them even when it isn't one (read from a file); as wide as its words."""
    from ... import mod_items as mi
    box = QComboBox()
    for number in sorted(set(mi.SWING_PALETTES) | {int(value)}):
        box.addItem(PALETTE_CHOICE.format(n=number), number)
    box.setCurrentIndex(box.findData(int(value)))
    box.setSizeAdjustPolicy(QComboBox.AdjustToContents)
    box.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    return box


#: The room each Battle Sprite field's sprite has, so the two fields' palettes and buttons line up.
FIELD_PICTURE = (72, 48)


class AttackLookRow(QWidget):
    """
    `[x] Attack  [look] [Palette n] [Choose a look]  note`

    (Zodi, 4 November) A game weapon's look as it attacks, beside Held or
    thrown and in its design: the look as the swing draws it, its palette
    (one the game's own weapons swing in, `mod_items.SWING_PALETTES`), and
    Choose a look over the looks that swing the same way (`LookDialog`). One
    tick: choosing either ticks it, unticking puts the game's look back.
    `edited` as the page's rows emit it, never while loading; `pair` is the
    look shown.
    """

    edited = Signal()

    def __init__(self, sprites_of, item_name_of, look_name_of, parent=None, category_of=None):
        super().__init__(parent)
        self.field_name = "BattleLook"
        self.is_unknown = self.is_comment = False
        self._sprites_of, self._item_name_of, self._look_name_of = sprites_of, item_name_of, look_name_of
        #: (4 November) A game weapon's category, so the looks' dialog files each look under its weapon type.
        self._category_of = category_of
        self._loading = False
        self._own = self.pair = b""
        self._looks, self._frames = [], 0
        #: (5 November) A shield's look as it guards: Guard's words in Attack's.
        self._guard = False
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 1, 0, 1)
        row.setSpacing(8)
        self.include = QCheckBox()
        self.include.setToolTip(
            "Tick to write this field into your mod. Unticked fields are "
            "left alone, so other mods can change them.")
        self.include.toggled.connect(self._on_include_toggled)
        row.addWidget(self.include)
        self.label = QLabel(ATTACK_FIELD_LABEL)
        self.label.setFixedWidth(200)
        row.addWidget(self.label)
        self.look = QLabel()
        self.look.setFixedSize(*FIELD_PICTURE)
        self.look.setAlignment(Qt.AlignCenter)
        row.addWidget(self.look)
        self.palette_box = QComboBox()
        self.palette_box.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.palette_box.currentIndexChanged.connect(self._on_palette_chosen)
        row.addWidget(self.palette_box)
        self.choose = QPushButton(ATTACK_CHOOSE)
        self.choose.clicked.connect(self.choose_look)
        row.addWidget(self.choose)
        self._note_text = ATTACK_FIELD_NOTE
        self.note = QLabel(ATTACK_FIELD_NOTE)
        self.note.setProperty("role", "muted")
        self.note.setWordWrap(False)
        self.note.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.note.setToolTip(ATTACK_FIELD_NOTE)
        row.addWidget(self.note, 1)
        self.setProperty("fieldRow", True)
        self.setProperty("unknownField", False)

    @property
    def included(self) -> bool:
        return self.include.isChecked()

    def _field_note(self) -> str:
        return GUARD_FIELD_NOTE if self._guard else ATTACK_FIELD_NOTE

    def set_guard(self, guard: bool) -> None:
        """(5 November) A shield's look (Guard) or a weapon's (Attack): its label and note."""
        self._guard = bool(guard)
        self.label.setText(GUARD_FIELD_LABEL if self._guard else ATTACK_FIELD_LABEL)

    def load(self, own: bytes, pair: bytes, looks: list, frames: int, ticked: bool, guard: bool = False) -> None:
        """A game weapon's look: its own (`own`), as shown (`pair`), the looks it may take (`[(the game's weapon, its
        sprite pair)]`) and its type's frames; ticked when the mod changes it; (5 November) a shield's as it guards
        (`guard`), the game's shields' looks."""
        self.set_guard(guard)
        self._own, self.pair, self._looks, self._frames = bytes(own), bytes(pair), list(looks), frames
        self._loading = True
        try:
            self.include.setEnabled(True)
            self.include.setChecked(bool(ticked))
            self._fill_palettes()
        finally:
            self._loading = False
        self.palette_box.setEnabled(True)
        self.choose.setEnabled(bool(self._looks))
        self.refresh()

    def unavailable(self, why: str) -> None:
        """A weapon whose look can't be changed here (not one of the game's, or no program): nothing to choose, and
        why in its note."""
        self._own = self.pair = b""
        self._looks = []
        self._loading = True
        try:
            self.include.setChecked(False)
            self.include.setEnabled(False)
            self.palette_box.clear()
        finally:
            self._loading = False
        self.palette_box.setEnabled(False)
        self.choose.setEnabled(False)
        self.look.clear()
        self.look.setToolTip("")
        self._note_text = why or self._field_note()
        self._show_note()

    def _palette(self) -> int:
        from ... import mod_items as mi
        return self.pair[0] >> 4 if len(self.pair) == mi.PAIR_BYTES else 0

    def _fill_palettes(self) -> None:
        from ... import mod_items as mi
        self.palette_box.clear()
        for number in sorted(set(mi.SWING_PALETTES) | {self._palette()}):
            self.palette_box.addItem(PALETTE_CHOICE.format(n=number), number)
        self.palette_box.setCurrentIndex(self.palette_box.findData(self._palette()))

    def _set(self, pair: bytes) -> None:
        """The user's choice: the look shown, ticked, then `edited`."""
        self.pair = bytes(pair)
        self._loading = True
        try:
            self.include.setChecked(True)
            self._fill_palettes()
        finally:
            self._loading = False
        self.refresh()
        self.edited.emit()

    def take(self, number: int, palette=None) -> None:
        """The look of the game's weapon `number` (one of those it may take), in `palette` (else in its own)."""
        from ... import mod_items as mi
        found = dict(self._looks).get(number)
        if found is None:
            return
        self._set(mi.look_with_palette(found, int(palette)) if palette is not None else found)

    def _on_palette_chosen(self, _index) -> None:
        from ... import mod_items as mi
        if self._loading or self.palette_box.currentData() is None or len(self.pair) != mi.PAIR_BYTES:
            return
        self._set(mi.look_with_palette(self.pair, int(self.palette_box.currentData())))

    def _on_include_toggled(self, on: bool) -> None:
        if self._loading:
            return
        if not on:
            # Unticked: left alone, so shown as the game has it.
            self.pair = self._own
            self._loading = True
            try:
                self._fill_palettes()
            finally:
                self._loading = False
            self.refresh()
        self.edited.emit()

    def ask(self):
        """The looks' dialog over the looks it may take, drawn in the palette chosen: (the game's weapon, the palette)
        taken, or None."""
        from ... import mod_items as mi
        names = {n: self._look_name_of(n) for n, _pair in self._looks}
        categories = ({n: self._category_of(n) for n, _pair in self._looks} if self._category_of is not None
                      else None)
        dialog = LookDialog(self, self._sprites_of(), self._frames, self._looks, names,
                            mi.look_now(self._looks, self.pair), self._palette(), self._item_name_of(),
                            categories=categories, pair=self.pair, guard=self._guard)
        return dialog.choice() if dialog.exec() else None

    def choose_look(self) -> None:
        answer = self.ask()
        if answer:
            self.take(*answer)

    def refresh(self) -> None:
        """Its look as the swing draws it, named in its tooltip (which of the game's weapons' look, its palette)."""
        from ... import mod_items as mi
        sprites = self._sprites_of()
        picture = None
        if sprites is not None and len(self.pair) == mi.PAIR_BYTES:
            picture = sprites.attack(self._frames, self.pair)
        drawn = ItemsPage._sprite_pixmap(picture, *FIELD_PICTURE)
        if drawn is None:
            self.look.clear()
        else:
            self.look.setPixmap(drawn)
        # (4 November) Every one of the game's weapons that shares the look, by name.
        self.look.setToolTip(look_words(mi.look_group(self._looks, self.pair), self._look_name_of, self._palette()))
        self._note_text = self._field_note()
        self._show_note()

    def _show_note(self) -> None:
        hidden = getattr(self, "_hide_notes", False)
        self.note.setText("" if hidden else self._note_text)
        self.note.setToolTip(self._note_text)

    def apply_display(self, hide_notes: bool, hide_unknown: bool, hide_comments: bool) -> None:
        """The view toggles: its note emptied with the others' (never unknown, never a comment)."""
        self._hide_notes = bool(hide_notes)
        self._show_note()


def listed(names: list) -> str:
    """Names as a list in words: "A", "A and B", "A, B and C"."""
    names = [str(n) for n in names]
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def look_words(group: list, name_of, palette: int) -> str:
    """(Zodi, 4 November: "many of them share the same design") A look's words, its tooltip and the looks' dialog's
    line: every one of the game's weapons that shares it (`group`, `mod_items.look_group`), by name, and its palette;
    its own when none of the game's weapons has it."""
    if not group:
        return ATTACK_OWN_PICKED.format(palette=palette)
    if len(group) == 1:
        return ATTACK_PICKED.format(item=name_of(group[0]), palette=palette)
    return ATTACK_SHARED.format(items=listed([name_of(n) for n in group]), palette=palette)


def category_words(category: int) -> str:
    """A weapon type as the Items page's Item Category names it ("Knight Sword")."""
    from ..widgets.field_rows import split_words
    return split_words(c.ITEM_CATEGORIES[category]) if 0 <= category < len(c.ITEM_CATEGORIES) else str(category)


def look_sections(groups: list, categories: dict, rows: list) -> list:
    """
    (4 November) The looks' dialog's sections: `[(weapon type, [group])]`,
    each look (`groups`, `mod_items.look_groups`) under the type most of its
    weapons are (`categories`, their types by number), the types in their
    order. Where its weapons are as many of one type as of another (the
    Materia Blade and Materia Blade+, swords, beside the Excalibur and
    Ragnarok, knight swords), under the type whose other looks lie nearest
    it on the weapons' texture, which is laid out a type's rows together
    (`rows`, each group's row), then the first type. One section, its type
    None, when the looks are of one type or a weapon's type isn't given.
    """
    kinds = {categories.get(n) for group in groups for n in group}
    if len(kinds) <= 1 or None in kinds:
        return [(None, list(groups))]
    tallies = []
    for group in groups:
        tally = {}
        for number in group:
            tally[categories[number]] = tally.get(categories[number], 0) + 1
        tallies.append(tally)
    # Each look's type when one type has most of its weapons; None while tied.
    clear = [next(iter(t for t, n in tally.items() if n == max(tally.values())))
             if list(tally.values()).count(max(tally.values())) == 1 else None for tally in tallies]

    def distance(kind, here: int) -> int:
        near = [abs(rows[k] - rows[here]) for k, other in enumerate(clear) if k != here and other == kind]
        return min(near) if near else 1 << 30
    placed = {}
    for index, (group, tally) in enumerate(zip(groups, tallies)):
        kind = clear[index]
        if kind is None:
            most = max(tally.values())
            kind = min((t for t, n in tally.items() if n == most), key=lambda t: (distance(t, index), t))
        placed.setdefault(kind, []).append(group)
    return [(kind, placed[kind]) for kind in sorted(placed)]


class _LookTiles(QListWidget):
    """(4 November) One weapon type's looks in the looks' dialog: a tile each, as many rows as its tiles need at its
    width, never a scrollbar of its own (the dialog's sections scroll together)."""

    def __init__(self, parent=None):
        from PySide6.QtCore import QSize
        from PySide6.QtWidgets import QListView
        super().__init__(parent)
        self.setViewMode(QListView.IconMode)
        self.setIconSize(QSize(*LOOK_TILE_ICON))
        self.setGridSize(QSize(*LOOK_TILE))
        self.setResizeMode(QListView.Adjust)
        self.setMovement(QListView.Static)
        self.setWrapping(True)
        self.setWordWrap(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def fit(self) -> None:
        """As tall as its rows of tiles at its width (at least `LOOK_ACROSS` tiles, the dialog's least width)."""
        across = max(LOOK_ACROSS, self.viewport().width() // LOOK_TILE[0])
        rows = max(1, -(-self.count() // across))
        self.setFixedHeight(rows * LOOK_TILE[1] + 2 * self.frameWidth() + 4)

    def resizeEvent(self, event):                                         # noqa: N802
        super().resizeEvent(event)
        self.fit()


#: (4 November) A look's tile in the looks' dialog: its sprite, the names of the weapons that share it under it (up to
#: three lines of them: the katanas' five names); the dialog at least four tiles across (a weapon type's most looks in
#: the game, the swords'), and as tall as its sections up to this share of the screen's height, past which they scroll.
LOOK_TILE_ICON = (72, 48)
LOOK_TILE = (180, 104)
LOOK_ACROSS = 4
LOOK_SCREEN_SHARE = 0.65


class LookDialog(QDialog):
    """(Zodi after test 62: "borrow the design of Sprite and Palette from the Items page") A weapon's look as it
    attacks: the looks that swing the same way (`looks`, `[(the game's item, its sprite pair)]`, each named by
    `names`), each drawn as it attacks (`frames`, over `sprites`) in the palette chosen (one the game's own weapons
    swing in), the one picked shown twice its size; a double click takes it. `choice`: (the game's item, the palette).
    (4 November) Here, shared by the Items page's Attack and the New Content page's item card.

    (Zodi, 4 November: "many of them share the same design so what you get is a lot of repeating looks in the list
    with different item names ... see if you can find a better way to categorize these different looks") Each sprite
    once (`mod_items.look_groups`): a tile naming every weapon that shares it, under the weapon type it is drawn for
    when the looks are of more than one (`categories`, `{the game's item: its category}`; `look_sections`). The tile
    picked is the one whose picture `pair` (the look now) draws; taking it takes the look of the weapon `number` (the
    look now's, `mod_items.look_now`) when that weapon shares it, else of its first weapon."""

    def __init__(self, parent, sprites, frames, looks: list, names: dict, number: int, palette: int, item: str,
                 categories: dict = None, pair: bytes = b"", guard: bool = False):
        from PySide6.QtWidgets import QScrollArea
        from ... import mod_items as mi
        super().__init__(parent)
        # (5 November) A shield's looks as it guards (`guard`): Guard's words.
        self.setWindowTitle((GUARD_DIALOG_TITLE if guard else LOOK_DIALOG_TITLE).format(item=item))
        self._sprites, self._frames, self._looks, self._names = sprites, frames, list(looks), names
        self._initial = number
        self._groups = mi.look_groups(self._looks)
        now = mi.look_group(self._looks, pair) if pair else []
        if not now:
            now = next((g for g in self._groups if number in g), self._groups[0] if self._groups else [])
        self._group = list(now)
        self._number = number if number in self._group else (self._group[0] if self._group else 0)
        self._palette = palette if 0 <= palette < 16 else 0
        column = QVBoxLayout(self)
        intro = QLabel(GUARD_DIALOG_INTRO if guard else LOOK_DIALOG_INTRO)
        intro.setWordWrap(True)
        column.addWidget(intro)
        top = QHBoxLayout()
        self.palette_box = swing_palette_box(self._palette)
        self.palette_box.currentIndexChanged.connect(self._palette_chosen)
        top.addWidget(self.palette_box)
        self.preview = QLabel()
        self.preview.setFixedSize(144, 96)
        self.preview.setAlignment(Qt.AlignCenter)
        top.addWidget(self.preview)
        self.picked_label = QLabel()
        self.picked_label.setWordWrap(True)
        top.addWidget(self.picked_label, 1)
        column.addLayout(top)
        # Each weapon type its heading and its tiles, the sections scrolling together.
        self.sections = []
        self.lists = []
        body = QWidget()
        body_column = QVBoxLayout(body)
        body_column.setContentsMargins(0, 0, 0, 0)
        body_column.setSpacing(4)
        for category, groups in self._sectioned(categories or {}):
            heading = None
            if category is not None:
                heading = QLabel(category_words(category))
                heading.setStyleSheet("font-weight: 600;")
                body_column.addWidget(heading)
            tiles = _LookTiles()
            tiles.currentItemChanged.connect(lambda item, _previous, t=tiles: self._look_picked(item, t))
            tiles.itemDoubleClicked.connect(self._look_taken)
            body_column.addWidget(tiles)
            self.sections.append((category, heading, groups))
            self.lists.append(tiles)
        body_column.addStretch(1)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setWidget(body)
        column.addWidget(self.scroll, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        column.addWidget(buttons)
        self._fill()

    def _sectioned(self, categories: dict) -> list:
        """`[(weapon type or None, [group])]` (`look_sections`): one section without a heading when the looks are of
        one type, or their types aren't given."""
        rows = [dict(self._looks)[group[0]][1] for group in self._groups]
        return look_sections(self._groups, categories, rows)

    def choice(self) -> tuple:
        return self._number, self._palette

    def tiles(self) -> list:
        """`[[the game's weapons]]`: each tile's weapons, in the order shown."""
        return [list(lst.item(n).data(Qt.UserRole)) for lst in self.lists for n in range(lst.count())]

    def pick(self, index: int) -> None:
        """Picks the tile `index` (in `tiles`' order), as a click does."""
        for lst in self.lists:
            if index < lst.count():
                lst.setCurrentRow(index)
                return
            index -= lst.count()

    def _pair(self, number: int) -> bytes:
        from ... import mod_items as mi
        pair = dict(self._looks).get(number)
        if pair is None or len(pair) != mi.PAIR_BYTES:
            return b""
        return bytes([(self._palette << 4) | (pair[0] & 0x0F), pair[1]])

    def _picture(self, number: int):
        pair = self._pair(number)
        if self._sprites is None or not pair:
            return None
        return self._sprites.attack(self._frames, pair)

    def _name(self, number: int) -> str:
        return self._names.get(number) or ITEM_NUMBERED.format(n=number)

    def _fill(self) -> None:
        from PySide6.QtGui import QIcon
        for lst, (_category, _heading, groups) in zip(self.lists, self.sections):
            lst.blockSignals(True)
            lst.clear()
            for group in groups:
                drawn = _picture_pixmap(self._picture(group[0]))
                tile = QListWidgetItem(QIcon(drawn) if drawn is not None else QIcon(),
                                       ", ".join(self._name(n) for n in group))
                tile.setData(Qt.UserRole, list(group))
                tile.setToolTip(listed([f"{self._name(n)} ({n})" for n in group]))
                lst.addItem(tile)
                if group == self._group:
                    lst.setCurrentItem(tile)
            lst.blockSignals(False)
            lst.fit()
        self._draw()
        # Wide enough for four tiles beside the scrollbar, as tall as its sections up to a share of the screen.
        body = self.scroll.widget()
        screen = self.screen() or QApplication.primaryScreen()
        tallest = int(screen.availableGeometry().height() * LOOK_SCREEN_SHARE) if screen is not None else 640
        self.scroll.setMinimumSize(LOOK_ACROSS * LOOK_TILE[0] + 2 * self.lists[0].frameWidth()
                                   + self.scroll.verticalScrollBar().sizeHint().width() + 12 if self.lists else 0,
                                   min(body.sizeHint().height(), tallest))

    def _palette_chosen(self, _index) -> None:
        self._palette = int(self.palette_box.currentData())
        self._fill()

    def _look_picked(self, item, source=None) -> None:
        if item is None:
            return
        self._group = list(item.data(Qt.UserRole))
        # The look now kept as it is when its tile is picked again; else its first weapon's.
        self._number = self._initial if self._initial in self._group else self._group[0]
        for lst in self.lists:
            if lst is not source:
                lst.blockSignals(True)
                lst.setCurrentRow(-1)
                lst.clearSelection()
                lst.blockSignals(False)
        self._draw()

    def _look_taken(self, item) -> None:
        source = item.listWidget() if item is not None else None
        self._look_picked(item, source)
        self.accept()

    def _draw(self) -> None:
        drawn = _picture_pixmap(self._picture(self._number), 2)
        if drawn is None:
            self.preview.clear()
        else:
            self.preview.setPixmap(drawn.scaled(144, 96, Qt.KeepAspectRatio, Qt.FastTransformation)
                                   if drawn.width() > 144 or drawn.height() > 96 else drawn)
        self.picked_label.setText(look_words(self._group, self._name, self._palette))
