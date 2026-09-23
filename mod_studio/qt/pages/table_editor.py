"""
A generic editor for any table the `TableSpec` engine describes.

Eleven tables go through `item_xml_io.ALL_SPECS`, and they are all the same
shape: an ordered list of fields, some of which are booleans, some of which
are sets of flags, over records with an id and a name. Items, Equip Bonus
and Treasure Hunter are three tabs' worth of that one shape.

So this is one page, configured, not three pages that resemble each other.
That is the engine's own principle - `item_xml_io.py` handles every one of
these tables with a single `TableSpec` engine, and new tables wire into
`ALL_SPECS` rather than spawning a new one. An interface that answered a
generic engine with N near-duplicate pages would be undoing that: the
eleventh table would mean an eleventh page, and the tenth copy of a bug
would be the one nobody remembered to fix.

Edits land on `WizardState.item_table_edits`, keyed
`{table_key: {record_id: {field_name: value}}}` - the same store, with the
same rules, as the Tkinter tabs.
"""
from __future__ import annotations

from html import escape

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QVBoxLayout, QWidget,
)

from ... import ability_defaults
from ... import constants as c
from ... import item_xml_io as ix
from ... import nxd_data
from ..widgets.actions import (
    page_intro,
    ViewToggles, apply_view_toggles, mark_edited, select_list_row,
    set_empty_state, edit_counter_text)
from ..widgets.field_rows import (
    ChoiceFieldRow,
    DropdownFieldRow,
    CollapsibleSection, FlagFieldPanel, NumericFieldRow, split_words,
)
from ..widgets.column_form import ColumnFormBody
from ..widgets.form_scroll import FormScrollArea
from ..widgets.visible_refresh import RefreshesWhenVisible

# A field's value is text in the XML, so the editor needs a range. Anything
# not named here gets a byte's worth, which is what the great majority of
# these fields are.
DEFAULT_RANGE = (0, 255)
WIDE_RANGE = (0, 65535)
WIDE_FIELDS = {"AdditionalDataId", "RareItemId", "CommonItemId", "Price",
               "ItemNameTextUIId", "DescriptionTextUIId"}


# Where and what before the trap, which is the order somebody fills a
# treasure tile in. `MAPTRAP_SLOT_FIELD_LABELS` has Trap third, between the
# coordinates and the items - correct as a description of the columns,
# wrong as a reading order.
SLOT_FIELD_ORDER = ["X", "Y", "RareItemId", "CommonItemId", "TrapFlags"]


def _range_for(field_name: str) -> tuple:
    if any(field_name.startswith(w) for w in WIDE_FIELDS):
        return WIDE_RANGE
    return DEFAULT_RANGE


def enum_choices(field_name: str, entry_tag: str = "") -> list:
    """
    The named values a plain-enum field can hold, or `[]`.

    Resolved through the loader's OWN declaration of the property's type -
    `ItemOptions.OptionType` is declared `ItemOptionsType` - not by gluing
    the entry tag to the field name. That convention works for the flag
    enums by luck of naming and would have missed this one entirely:
    `ItemOptionsOptionType` does not exist.
    """
    from ... import xml_models

    model = xml_models.model_for(entry_tag) if entry_tag else None
    if model is None:
        return []
    for field in model.fields:
        if field.name == field_name:
            return list(xml_models.choice_enums().get(field.csharp_type, ()))
    return []


def flag_choices(field_name: str, entry_tag: str = "") -> list:
    """
    The set of flags a field can hold.

    `TableSpec.flag_fields` is a tuple of field NAMES, not a mapping to
    choices - the choices live in `constants.py`, in whichever list suits
    the field. Resolved here rather than duplicated: a flag added to
    `ITEM_TYPE_FLAGS` shows up in the interface without this file changing.

    A field whose choices cannot be found returns nothing, and the caller
    skips it rather than rendering an empty box. A flag panel with no flags
    in it would look like a field with nothing to set, which is a different
    and untrue statement.
    """
    if field_name in c.FLAG_FIELDS:
        return list(c.FLAG_FIELDS[field_name][0])
    if field_name == "TypeFlags":
        return list(c.ITEM_TYPE_FLAGS)
    if field_name.startswith("TrapFlags"):
        return list(c.MAPTRAP_TRAP_FLAGS)
    if field_name == "Flags":
        return list(c.ABILITY_XML_FLAGS)
    if field_name == "AIBehaviorFlags":
        return list(c.ABILITY_AI_BEHAVIOR_FLAGS)
    if field_name.endswith("Elements"):
        return list(c.ELEMENT_FLAGS)
    if field_name == "AttackFlags":
        return list(c.ITEM_ATTACK_FLAGS)

    # Last, and only if nothing above matched: the mod loader's own enum,
    # read from its bundled `Tables/Models`. `ItemOptions.Effects` resolves
    # this way and is the only field that does - measured across every flag
    # field of every spec.
    #
    # LAST, deliberately. The hand-written lists above are not a worse copy
    # of these: they were cross-checked against the real struct sources and
    # they DISAGREE with the derived enums in two places on purpose -
    # `ItemTypeFlags` has 8 derived against 7 here, `AbilityFlags` 4 against
    # 3. Letting the derived enum win would silently re-add bits somebody
    # removed on evidence. So this fills gaps; it never overrides.
    if entry_tag:
        from ... import xml_models
        derived = xml_models.flag_enums().get(f"{entry_tag}{field_name}")
        if derived:
            return list(derived)
    return []


def _groups_for(field_name: str, choices: list) -> dict:
    """Reuses the engine's own grouping where it has one."""
    if field_name == "EquippableItems":
        return c.EQUIP_GROUPS
    if field_name in ("InnateStatus", "ImmuneStatus", "StartingStatus",
                      "Effects"):
        # `Effects` joins them because all 40 of its values ARE those
        # statuses - checked, 40 of 40 - so it gets the engine's own
        # grouping rather than a second one invented here.
        #
        # Ungrouped it was one box of 40 checkboxes in a single tall
        # column, which is what prompted the request for columns. Five
        # groups of eight reflow side by side as the window allows, and
        # they are the sets the game itself uses; chunking into four tens
        # would look tidier and would be a grouping nothing else in the
        # data agrees with.
        return c.STATUS_GROUPS
    return {humanise(field_name): list(choices)}


# How many item names to spell out under an Equip Bonus row before the rest
# become "and N more".
#
# Row 0 is the default every unmodified item points at - 183 of them in a
# real table - and listing all of those grew the box until it pushed the
# editable fields off screen. The ones past the cap are counted but not
# named, which costs nothing: nobody jumps to a specific item from the "no
# bonus" row.
USAGE_LIST_LIMIT = 12

# Row 0's name in `ItemEquipBonusData.xml` is "Dummy/Empty", from the file's
# own comment. That is accurate about the table's internals and misleading
# about what the row does: every item defaults to it, and what it means is
# that the item grants no equip bonus at all.
ROW_NAME_OVERRIDES = {"item_equip_bonus": {0: "No bonus"}}

#: The narrowest a treasure-tile column may be before the layout drops to
#: fewer columns.
#:
#: A tile holds an X and a Y spin box, two item dropdowns and a three-column
#: flag grid, and the flag grid is what sets the floor - the trap names run
#: to "Sleeping Gas" and "Steel Needle" across three columns. Measured
#: against the tile body's own size hint rather than guessed; see
#: `test_qt_table_editor`, which asserts the tiles actually reflow and that
#: nothing is clipped at the 1100 minimum.
TILE_COLUMN_WIDTH = 460

#: The narrowest a tile's item dropdown may be.
#:
#: Inside a hugged tile column the combo fell back to `DropdownFieldRow`'s
#: 160px floor while its widest entry - "000 - Featherweave Cloak" - needs
#: 210px, so item names were clipped. Reported from real use.
#:
#: 210, which is that measurement. It was 240 first, copied from Job
#: Commands' `SLOT_COMBO_WIDTH` on the "same job, same number" argument -
#: and that put the whole row at 470px inside the 454px a tile gets at the
#: 1100 minimum, trading a clipped name for a clipped row. Copying a
#: sibling's number is not the same as measuring your own (rule 19); the
#: sibling's combo holds ability names, which are longer.
TILE_COMBO_WIDTH = 210


#: How wide the row list is.
#:
#: 260px until rows started being named by what they do, at which point 27
#: of the 85 Equip Bonus rows no longer fitted and were cut mid-word. 340px
#: is the measured answer: with the shortened connectives and the usage
#: suffix below, the longest label is 309px against 312px of usable width,
#: and nothing is clipped. The form gives up 80px it has to spare.
LIST_WIDTH = 340

# -- naming a row by what it does ---------------------------------------------
#
# 84 of the 85 Equip Bonus rows have no name in the file, so the list read
# "001 - (unnamed) (1 item)" 84 times. The row's own fields say what it is,
# so the list says it instead: "001 - MA +2 (1 item)".
#
# **FFTPatcher was checked first, as the bundled community reference.** It
# contributes two name lists here (`EncounterNames.txt`,
# `AbilityEffectNames.txt`) and neither covers this table; its own
# equivalent tab lists these entries by index with no descriptive label
# either. There was nothing to reuse, so this is derived from the data.
#
# The wording is short forms of what the FORM beside the list already calls
# these fields, not a second vocabulary invented here - but it IS a second
# copy of the field list, so `test_qt_table_editor` asserts it covers every
# field in the spec. A hand-kept list with no check is the thing this
# project has got wrong three times.

#: `field -> stat shown in the label`. The form says "MA Bonus"; a list row
#: has no room for the word "Bonus" 19 times over.
_BONUS_STATS = {
    "PABonus": "PA", "MABonus": "MA", "SpeedBonus": "Speed",
    "MoveBonus": "Move", "JumpBonus": "Jump",
}

#: `field -> (phrase, what the values are)`. The plural noun is only used
#: when there are too many values to name.
#: The phrases are the SHORT forms. "Immune to Charm, Confuse" and
#: "Starts with Invisible" read better in prose and did not fit: the list is
#: 340px and a third of the rows overflowed it before the four longest
#: connectives lost a word each. The form beside the list still says "Immune
#: Status" in full; this is the scanning view, not the editing one.
_BONUS_FLAGS = {
    "InnateStatus": ("Innate", "statuses"),
    "ImmuneStatus": ("Immune", "statuses"),
    "StartingStatus": ("Starts", "statuses"),
    "AbsorbElements": ("Absorbs", "elements"),
    "NullifyElements": ("Nullifies", "elements"),
    "HalveElements": ("Halves", "elements"),
    "WeakElements": ("Weak", "elements"),
    "StrongElements": ("Strong", "elements"),
}

#: Fields that are simply on or off, shown by name when on.
_BONUS_SWITCHES = {"BoostJP": "Boost JP"}

#: The strings this table uses for "nothing here", across its three kinds
#: of field. Compared lower-cased.
_BONUS_EMPTY = {"", "0", "none", "false"}

#: How many values inside ONE field are named before switching to a count.
#: Measured: `ImmuneStatus` on row 071 holds **eighteen** statuses, which
#: named in full is a list row nobody can read. Two is the largest number
#: that keeps "Immune to Sleep, Blind" - a real and useful row - intact.
_BONUS_VALUES_NAMED = 2

#: How many fields are named before switching to "+N more". Measured across
#: the shipped table: 56 of 85 rows do exactly one thing and 76 do one or
#: two, so this only ever bites the tail. At three it truncates ONE row of
#: 85 and the longest label is 43 characters; at two it truncates seven and
#: saves a single character. Three, on that measurement.
_BONUS_EFFECTS_NAMED = 3

#: Between effects. A comma cannot be the separator at both levels: with one,
#: row 041 read "PA +2, MA +1, Innate Shell, Protect" and there is no way to
#: see that the last two are one effect. The middle dot is what this
#: interface already separates facts with on All Game Data.
_BONUS_JOIN = " \u00b7 "


def equip_bonus_effects(values: dict, field_order,
                        values_named: int = _BONUS_VALUES_NAMED) -> list:
    """
    The short phrases describing what a bonus row does, in field order.

    `values` is the row's effective values - the file's, with any pending
    edit already applied - so the caller decides what "current" means and
    this stays a pure function of what it is handed.
    """
    phrases = []
    for field_name in field_order:
        raw = str(values.get(field_name, "")).strip()
        if raw.lower() in _BONUS_EMPTY:
            continue
        if field_name in _BONUS_STATS:
            phrases.append(f"{_BONUS_STATS[field_name]} +{raw}")
        elif field_name in _BONUS_FLAGS:
            phrase, noun = _BONUS_FLAGS[field_name]
            parts = [p.strip() for p in raw.split(",") if p.strip()]
            if len(parts) <= values_named:
                phrases.append(f"{phrase} {', '.join(parts)}")
            else:
                phrases.append(f"{phrase} {len(parts)} {noun}")
        elif field_name in _BONUS_SWITCHES:
            phrases.append(_BONUS_SWITCHES[field_name])
        else:
            # A field the vocabulary above does not know. Named rather than
            # dropped, because a row whose only effect is an unknown field
            # would otherwise read "(no effect)" - which is a false
            # statement about the row, and worse than an ugly one.
            phrases.append(split_words(field_name))
    return phrases


#: How many statuses a row label names before it says "+N more".
#:
#: MEASURED against `LIST_WIDTH`, not chosen, and re-measured when the row
#: grew. Equip Bonus shipped 27 of 85 rows cut mid-word because its labels
#: were measured for readability and never for fit; this table is worse -
#: the naive label runs to 576px against 308px of usable row width.
#:
#: It was 2, correctly, when the label was just the id and the statuses.
#: Then the row gained a "Used by" suffix - `  . unused` or `  . 5 items`,
#: about 55px - and `Cancel ` became `Cancel: `, and 2 no longer fit:
#:
#: Measured three times now, and it has moved twice - which is the whole
#: lesson. A label measurement is only valid for the row it was taken on,
#: and ANY change to that row invalidates it, additions and removals alike.
#:
#:     cap   widest   clipped   when
#:      2     266px    0 of 128   before any usage suffix existed
#:      1     277px    0 of 128   with ". unused" / ". 5 items"
#:      2     353px    8 of 128   (so the cap dropped to 1)
#:      2     288px    0 of 128   with the empty-row suffix removed
#:      3     344px    6 of 128
#:      2     343px    2 of 128   with ABILITIES counted as users
#:      1     277px    0 of 128
#:      3     387px    9 of 128
#:
#: Back to 1, and for the fourth time the cause is the suffix rather than
#: the statuses. `data/AbilityActionDefaults.txt` made the ability half of
#: the usage index readable, and **31 rows now carry a `. N users` suffix
#: where 8 did** - two of them the long `Cancel: ...` rows, which is what
#: tipped cap 2 over. The comment above said any change to the row
#: invalidates the measurement; this is that, happening again.
#:
#: The tooltip still carries every status either way. A clipped label loses
#: information silently; "+7 more" loses it visibly and points at where to
#: look.
INFLICT_STATUS_CAP = 1

#: The option type that is NOT written into the label.
#:
#: `AllOrNothing` is 75 of 128 rows. Near-constant text earns no width - the
#: same reason Equip Bonus dropped its "(1 item)" suffix. What a person
#: scanning this list needs to spot is the row that behaves DIFFERENTLY, and
#: `Cancel` is not a variation on inflicting a status, it is the opposite of
#: it: "Cancel Poison" removes poison where "Poison" applies it. Getting
#: those two the wrong way round is the worst mistake this page can cause,
#: so the verb is spelled out on every row where it is not the plain case.
#:
#: The tooltip always names the type in full, including this one, so nothing
#: is hidden - only the constant is left unsaid.
INFLICT_STATUS_PLAIN_TYPE = "AllOrNothing"

#: How each option type reads at the front of a row label.
INFLICT_STATUS_VERBS = {
    # All three punctuate the same way. "Cancel Poison" against "Random:
    # Poison" made the colon look like it meant something - reported from
    # real use - when it is only the separator between the verb and the
    # list it applies to.
    "Cancel": "Cancel: ",
    "Random": "Random: ",
    "Separate": "Separately: ",
    "AllOrNothing": "",
    "None": "",
}


def inflict_statuses(values: dict) -> list:
    """
    The statuses a row lists, as a list of names.

    The loader has already flattened `Effects1`-`Effects5` into one
    comma-separated `Effects` node - the bundled XML says so in its own
    header - so this splits rather than walking five fields. `"None"` is the
    table's way of writing "nothing", not a status called None.
    """
    raw = (values.get("Effects") or "").strip()
    if not raw or raw == "None":
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def inflict_status_descriptor(values: dict, field_order=None) -> str:
    """
    What a row of `ItemOptionsData.xml` DOES, in a few words.

    Every row of this table is anonymous - it has an id and nothing else -
    so without this the list reads "000 - (unnamed)" 128 times over and the
    only way to find the option you want is to click all of them. Same
    problem Equip Bonus had and the same answer.
    """
    statuses = inflict_statuses(values)
    if not statuses:
        return "(no effect)"
    kind = (values.get("OptionType") or "").strip()
    verb = INFLICT_STATUS_VERBS.get(kind, f"{kind}: " if kind else "")
    if len(statuses) <= INFLICT_STATUS_CAP:
        body = ", ".join(statuses)
    else:
        body = (f"{', '.join(statuses[:INFLICT_STATUS_CAP])} "
                f"+{len(statuses) - INFLICT_STATUS_CAP} more")
    return f"{verb}{body}"


def inflict_status_tooltip(values: dict) -> str:
    """
    The whole row, for hover - every status, and the type spelled out.

    Progressive disclosure rather than truncation: the label answers "which
    row is this", the tooltip answers "what exactly does it do". Eleven
    statuses do not fit in 308px and never will.
    """
    statuses = inflict_statuses(values)
    kind = (values.get("OptionType") or "").strip() or "None"
    meaning = {
        "AllOrNothing": "All of these land together, or none of them do.",
        "Cancel": "REMOVES these statuses rather than inflicting them.",
        "Separate": "Each of these is rolled for separately.",
        "Random": "One of these is picked at random.",
        "None": "Does nothing.",
    }.get(kind, "")
    lines = [f"Option type: {kind}"]
    if meaning:
        lines.append(meaning)
    if statuses:
        lines.append("")
        lines.append(f"{len(statuses)} status"
                     f"{'es' if len(statuses) != 1 else ''}: "
                     + ", ".join(statuses))
    return "\n".join(lines)


def equip_bonus_descriptor(values: dict, field_order) -> str:
    """A row's effects as one line, or "(no effect)" when it has none."""
    phrases = equip_bonus_effects(values, field_order)
    if not phrases:
        # True of 8 rows, and a better thing to tell someone than
        # "(unnamed)": it answers the question they are actually asking,
        # which is whether this row is worth opening.
        return "(no effect)"
    if len(phrases) <= _BONUS_EFFECTS_NAMED:
        return _BONUS_JOIN.join(phrases)
    shown = _BONUS_JOIN.join(phrases[:_BONUS_EFFECTS_NAMED])
    return f"{shown} +{len(phrases) - _BONUS_EFFECTS_NAMED} more"


#: The `Formula` value that repurposes an options id as an ABILITY id.
#:
#: From `ItemWeaponData.xml`'s own header, which the tool ships: "If using
#: Formula 02, <OptionsAbilityId> should be set to an ability id; otherwise,
#: <OptionsAbilityId> should be set to an 'item options' id or 0."
FORMULA_CASTS_ABILITY = 2

#: Columns that hold an ability id rather than a table row under that rule.
#:
#: One definition, because four places need the answer and they must agree:
#: the Items form's caption and control, the Abilities form's copy of the
#: same field, the "Used by" index, and the "unused" label built from it.
#: The rule was written out separately in the first two and absent from the
#: last two, which is why Lightning Bow was listed as inflicting Blind.
#:
#: Both names are here because the same field is called `OptionsAbilityId`
#: on `ItemWeaponData` and `InflictStatus` on `OverrideAbilityActionData`.
ABILITY_WHEN_FORMULA_2 = frozenset({"OptionsAbilityId", "InflictStatus"})

#: Item column -> the column abilities reach the same rows through.
#:
#: The two tables name one concept differently, and assuming they agreed is
#: a mistake this made once already: reading `OptionsAbilityId` off an
#: override row returns nothing at all, silently, so every ability
#: reference was missed and the rows went on reading as unused.
ABILITY_USAGE_COLUMN = {"OptionsAbilityId": "InflictStatus"}


def _is_formula_2(values: dict) -> bool:
    """
    Whether this row's `Formula` makes its options id an ability id.

    Absent or unreadable `Formula` is NOT formula 2. On the ability
    override table `Formula` is `-1` when the row does not override it, and
    a row that declines to set a formula has not set it to 2.
    """
    try:
        return int(values.get("Formula", -1)) == FORMULA_CASTS_ABILITY
    except (TypeError, ValueError):
        return False


#: What each table-editor page calls its rows in the green counter.
#:
#: Written out rather than derived from the title, because "Equip Bonus"
#: pluralises to "Equip Bonus rows" and "Treasure Hunter" to "maps" - a
#: title is what the tab is called, not what the rows are. Anything not
#: listed falls back to "rows", which is true of every table here.
COUNTER_NOUNS = {
    "item_equip_bonus": "equip bonus rows",
    "item_options": "inflict status rows",
    "map_trap": "maps",
    "item_shops": "shops",
}

#: Which item column points at which table, for the "Used by" list.
#:
#: Two tables ask the same question now - "which items use this row" - so
#: the answer is one function taking the column name rather than two
#: near-identical ones. Inflict Status needs it for the reason Equip Bonus
#: did: a row can be shared by several items, and editing it changes all of
#: them, so a page that cannot say which is asking you to guess.
USAGE_COLUMNS = {
    # table key: (column, linked table the column lives on)
    "item_equip_bonus": ("EquipBonusId", ""),
    "item_options": ("OptionsAbilityId", "item_weapon"),
}

#: What a row's suffix calls its users, and what it says when there are none.
#:
#: Per table, because the two tables can prove different things. Every
#: reference to an Equip Bonus row is an item, and the item table is fully
#: loaded, so "unused" there is a fact.
#:
#: Inflict Status cannot say that and never will be able to.
#: `AbilityActionData.xml` ships empty by design - an ability's base Inflict
#: Status is hardcoded in the game - so the tool sees ability references
#: only where an override row sets one. "no items" is chosen because it is
#: TRUE in both states, loaded and not: it reports what was checked instead
#: of what was concluded. A suffix that changed with the load state would
#: also be a label whose width changed with it, and the cap below is
#: measured on this row.
USAGE_NOUNS = {
    "item_equip_bonus": ("items", "unused"),
    # Inflict Status says NOTHING when no item uses a row.
    #
    # It said "no items", which was true and still read as a verdict on the
    # row - and this is the one table where no verdict is possible.
    # `AbilityActionData.xml` ships empty by design, so an ability's base
    # Inflict Status is hardcoded in the game and is not data this tool has
    # ever held. A row with no items may still be the one an ability
    # depends on.
    #
    # The page's own description now carries that warning once, where it
    # belongs, instead of 128 rows each carrying a fragment of it.
    "item_options": ("users", ""),
}

#: What a row nothing uses says, per table: `(the line, the tooltip)`.
#:
#: Reported from real use, both of them, and the fault was the same in each:
#: the sentence named the MECHANISM instead of answering the question.
#:
#:     "Not used by any item, counting any pending OptionsAbilityId edits."
#:     "Not used by any item, counting any pending EquipBonusId edits."
#:
#: `OptionsAbilityId` is a column name out of the nxd table; a modder
#: reading the page has no reason to know it, and the clause it sits in was
#: reassuring the reader about a staleness problem they had not thought to
#: worry about. The pending edits ARE counted - that is worth being true,
#: not worth saying every time.
#:
#: The two tables then differ, and the difference is the point:
#:
#:   * Inflict Status has BOTH kinds of user. Since the vanilla ability
#:     table shipped, 155 of the 368 abilities point at a status row, so a
#:     row with no users has no ability users either and the line can say
#:     so. It said "any item" while the list right above it was headed
#:     "Used by abilities:", which reads as the line having missed them.
#:   * Equip Bonus has only items. `ABILITY_USAGE_COLUMN` maps
#:     `OptionsAbilityId` alone, so `ability_usage` returns `{}` here and
#:     "or abilities" would be offering a kind of user that cannot exist.
#:
#: Kept beside `USAGE_NOUNS` because anyone changing one table's wording
#: should see the other table's in the same glance.
USAGE_EMPTY = {
    "item_equip_bonus": ("Not used by any item.", "Used by: no items"),
    "item_options": ("Not used by any ability or item.",
                     "Used by: no items or abilities"),
}


def table_usage(state, column: str, through: str = "") -> dict:
    """
    `row id -> [(item_id, name)]`, the reverse of one item column.

    `through` names a LINKED table to read the column from instead of the
    item row. `EquipBonusId` sits on the item itself; `OptionsAbilityId`
    does not - it lives on the item's weapon row in `ItemWeaponData.xml`,
    reached by the item's `AdditionalDataId`.

    That distinction is not cosmetic. Reading `OptionsAbilityId` off the
    item row returns "0" for every item, so the first version of this
    reported all 261 items as users of row 0 and every other row as unused -
    confidently, and wrongly, which is worse than not showing usage at all.

    **`through` is a filter, not a destination.** `AdditionalDataId` indexes
    the item's OWN category table, so only items whose own linked table IS
    `through` are read through it. The second version got this wrong in the
    other direction: it sent every item through `item_weapon` whatever the
    item was, and since row 8 of the weapon table inflicts Doom, four items
    that merely share the index 8 - Aegis Shield, Platinum Helm, Genji
    Gloves, Maiden's Kiss - were reported as inflicting Doom. Only the
    dagger does.

    An item with no linked table at all counts for nothing rather than
    counting as row 0. Maiden's Kiss is flagged only `Rare`: it has no
    Additional Data row, so it uses no Inflict Status row.

    `formula_column` on a spec means the column is only a real reference
    when that column is not 2. `Formula` 2 makes `OptionsAbilityId` an
    ABILITY id - Lightning Bow casts Thundara - so it is not a user of the
    options row that happens to carry the same number.
    """
    from .items import linked_table_key

    usage: dict = {}
    records = (state.item_table_records or {}).get("item", [])
    edits = (state.item_table_edits or {}).get("item", {})
    linked = (state.item_table_records_by_id(through) if through else {})
    linked_edits = ((state.item_table_edits or {}).get(through, {})
                    if through else {})
    for record in records:
        pending = edits.get(record.item_id, {})
        if through:
            # The item's OWN table, from its pending TypeFlags edit if it
            # has one - retyping an item from Weapon to Armor takes it out
            # of this index immediately, which is what the page shows.
            values = {**record.values, **pending}
            if linked_table_key(values) != through:
                continue
            try:
                linked_id = int(values.get("AdditionalDataId", "0"))
            except (TypeError, ValueError):
                continue
            source = linked.get(linked_id)
            if source is None:
                continue
            values = {**source.values, **linked_edits.get(linked_id, {})}
        else:
            values = {**record.values, **pending}
        if column in ABILITY_WHEN_FORMULA_2 and _is_formula_2(values):
            continue
        try:
            row_id = int(values.get(column, "0"))
        except (TypeError, ValueError):
            row_id = 0
        usage.setdefault(row_id, []).append(
            (record.item_id, getattr(record, "name", "") or "(unnamed)"))
    return usage


def _named_up_to(users: list) -> str:
    """
    `USAGE_LIST_LIMIT` names, then "and N more".

    The same cap the visible "Used by" line uses, and it is needed in the
    tooltip for the same reason it was needed there: Inflict Status row 0
    is what everything that inflicts nothing points at, and it now has 104
    items AND 213 abilities on it. A tooltip naming all 317 is a tooltip
    taller than the screen.
    """
    shown = ", ".join(name for _id, name in users[:USAGE_LIST_LIMIT])
    remaining = len(users) - USAGE_LIST_LIMIT
    return shown + (f", and {remaining} more" if remaining > 0 else "")


def _effective(values: dict, base: dict, column: str):
    """
    What an ability's column actually holds: its override, or the vanilla
    value the override is declining to change.

    None when neither is known.
    """
    try:
        overridden = int(values.get(column, c.OVERRIDE_NOT_SET))
    except (TypeError, ValueError):
        overridden = c.OVERRIDE_NOT_SET
    if overridden != c.OVERRIDE_NOT_SET:
        return overridden
    return base.get(column)


def ability_usage(state, column: str) -> dict:
    """
    `row id -> [(ability_id, name)]` for every ability that points here.

    The other half of who uses an Inflict Status row. An ability reaches
    one of these rows without any item being involved, and a row that only
    an ability uses read as `unused` - which invites exactly the edit that
    breaks it.

    **This now reads the vanilla value behind a -1, and that is most of the
    answer.** `OverrideAbilityActionData` holds -1 in `InflictStatus` on all
    368 rows of the vanilla game, so reading the override alone found
    nothing at all: every status row an ability uses looked unused, and the
    tab carried a written warning saying so ("Beware abilities also use
    these statuses though they are not listed in Used by"). With
    `data/AbilityActionDefaults.txt` shipped there is a value behind each
    -1, and **155 of the 368 abilities turn out to point at a status row** -
    Raise and Arise at 32, Reraise at 33, Regen at 34, Protect at 35.

    An ability's OWN override still wins where it sets one, and a pending
    edit wins over that, so repointing an ability on the Abilities tab moves
    it between rows here without an export.

    **A row whose effective `Formula` is 2 is excluded**, by the same rule
    items follow: at 2 the id is an ability to cast, not a status row. That
    used to have to guess when the formula was not overridden; the vanilla
    formula is now known, and no ability has 2 as its base.
    """
    usage: dict = {}
    override_column = ABILITY_USAGE_COLUMN.get(column)
    if override_column is None:
        return usage
    defaults = ability_defaults.cached()
    edits = getattr(state, "override_action_edits", None) or {}
    records = {r.key: r for r
               in (getattr(state, "override_action_records", None) or [])}
    # Every ability the tool knows of, from either source. A mod's own
    # database holds only the override rows that mod ships, and the
    # abilities it does not mention still have their vanilla values.
    for ability_id in sorted(set(defaults) | set(records)):
        base = defaults.get(ability_id) or {}
        record = records.get(ability_id)
        values = {**(getattr(record, "scalars", None) or {}),
                  **edits.get(ability_id, {})}
        if _effective(values, base, "Formula") == FORMULA_CASTS_ABILITY:
            continue
        row_id = _effective(values, base, override_column)
        if row_id is None or row_id < 0:
            continue
        usage.setdefault(row_id, []).append(
            (ability_id, ability_display_name(state, ability_id)))
    return usage


def ability_display_name(state, ability_id: int, language: str = "en") -> str:
    """
    An ability's name as the Abilities tab shows it, pending renames and all.

    **Through `nxd_data.effective_name`, which is the call the Abilities
    page's own `_ability_label` makes.** It used to go through
    `app.ability_choices`, and that disagreed with the page on 21 of the
    512 abilities - measured: 184, 219, 220, 357-367 and others, every one
    of them a row the page lists as `(unnamed)`.

    The difference is a FALLBACK. `ability_choices` ends at
    `ability_names.resolve_ability_name`, which drops back to the bundled
    FFTPatcher name list when this game's own `Ability-en` has nothing, so
    ability 359 read `Plunder Gil` here and `359 - (unnamed)` one tab over.
    Reported from real use, and the wrong half is this one: a name the game
    does not carry, printed as though the game carried it, is the same
    mistake as the PlayStation ability table - a plausible value from an
    older release presented as this game's.

    So an ability the game leaves unnamed is `(unnamed)`, exactly as the
    page says and exactly as the ITEM half of this line already did
    (`getattr(record, "name", "") or "(unnamed)"`). The id travels in the
    link beside the name, so the row is still reachable when the name is
    not helpful.
    """
    return nxd_data.effective_name(state, "ability", ability_id,
                                   language) or "(unnamed)"


def usage_certainty(state) -> bool:
    """
    Whether the tool can see ability references at all right now.

    There used to be three honest states for a row rather than two - used,
    not used by anything visible, and **not knowable yet** - because an
    ability's base Inflict Status is hardcoded in the game and was not data
    this tool held. `AbilityActionData.xml` ships empty on purpose; all the
    tool could see was the override table, and only after an unpack.

    `data/AbilityActionDefaults.txt` removes the third state. It ships
    populated, so the vanilla value behind every -1 is available before the
    game is unpacked at all, and "no users" can mean what it says. That is
    what let the tab's own description drop the warning it used to carry.

    Still a function rather than `True`: deleting the file is supported and
    puts the third state back, and a row that says `no items` on the
    strength of a file somebody removed would be making a claim it cannot
    support.
    """
    return bool(ability_defaults.cached()
                or getattr(state, "override_action_records", None))


def equip_bonus_usage(state) -> dict:
    """
    `equip_bonus_id -> [(item_id, name)]`, the reverse of `EquipBonusId`.

    Several items commonly share one bonus row, so editing a row here
    changes every item pointing at it. Without this the page could not say
    which those were, and the Qt tab was the generic table editor showing 85
    rows named "(unnamed)" with no indication that row 3 was worn by four
    items and row 60 by none.

    Reads each item's PENDING `EquipBonusId` edit first and falls back to
    its `ItemData.xml` baseline, so a row repointed in this session counts
    against its new bonus rather than its old one.

    Computed here rather than kept on `WizardState`. The Tkinter tab made
    that call for the same reason - it is a derived view over two stores the
    state already holds, and caching it would mean invalidating it on every
    item edit. Both interfaces now have their own copy of this, which is a
    candidate for promotion to the engine alongside the three merge helpers;
    that is an engine change and needs Zodi's approval first.
    """
    usage: dict = {}
    records = (state.item_table_records or {}).get("item", [])
    edits = (state.item_table_edits or {}).get("item", {})
    for record in records:
        pending = edits.get(record.item_id, {})
        raw = pending.get("EquipBonusId",
                          record.values.get("EquipBonusId", "0"))
        try:
            bonus_id = int(raw)
        except (TypeError, ValueError):
            # A blank or non-numeric value means the item is on the default
            # row, which is what the game reads it as.
            bonus_id = 0
        usage.setdefault(bonus_id, []).append(
            (record.item_id, getattr(record, "name", "") or "(unnamed)"))
    return usage


def humanise(field_name: str) -> str:
    """
    `RequiredLevel` -> `Required Level`, for a label.

    Deliberately does NOT try to prettify names it does not understand.
    A field called `Unknown8F` stays `Unknown8F`, because inventing a
    friendlier name for something nobody has worked out yet would be
    claiming knowledge the project does not have - and `is_unknown_field`
    reads the label to decide what the "hide unknown fields" toggle hides.
    """
    if field_name.lower().startswith("unknown"):
        return field_name
    # A space goes before a capital only at a real word boundary:
    #
    #   after a lowercase letter   RequiredLevel -> Required Level
    #   ending an acronym          PABonus       -> PA Bonus
    #
    # NOT after a digit. The first version split on "any capital following a
    # non-capital", which turned `Unused_0x0B` into "Unused_0x0 B" - a hex
    # offset pulled apart mid-number. These names are addresses as often as
    # they are words, and half a hex offset is worse than no prettifying.
    out = []
    for i, char in enumerate(field_name):
        if i and char.isupper():
            previous = field_name[i - 1]
            following = field_name[i + 1] if i + 1 < len(field_name) else ""
            boundary = (previous.islower()
                        or (previous.isupper() and following.islower()))
            if boundary:
                out.append(" ")
        out.append(char)
    return "".join(out)


#: Tables whose rows have no names of their own, and the function that says
#: what each row DOES instead.
#:
#: A registry rather than `table_key == "..."`, because there are two now and
#: the second one arriving is exactly when a name test quietly becomes a
#: place a third gets forgotten. Both signatures take `(values, field_order)`
#: so the call site does not have to know which it got.
DESCRIBED_TABLES = {
    "item_equip_bonus": equip_bonus_descriptor,
    "item_options": inflict_status_descriptor,
}


class TableEditorPage(RefreshesWhenVisible, QWidget):
    """Master-detail over one `TableSpec` table."""

    edits_changed = Signal()
    # Where the page wants to go, and with what record. The page does not
    # know what tabs exist - it says where it wants to go and the shell
    # navigates, which is the same contract Jobs and Job Commands use.
    navigate_requested = Signal(str, object)

    def __init__(self, state, table_key: str, title: str, blurb: str,
                 parent=None):
        super().__init__(parent)
        self.state = state
        self.table_key = table_key
        self.spec = ix.ALL_SPECS[table_key]
        self.current_id = None
        self.rows: dict[str, QWidget] = {}
        # Only Equip Bonus has a reverse index; every other table's rows
        # stand alone. Kept as an attribute rather than recomputed per row
        # so building an 85-row list is one pass over the item table, not
        # eighty-five.
        # Both describing tables answer "which items use this row".
        self.shows_usage = table_key in USAGE_COLUMNS
        self._usage_column, self._usage_through = USAGE_COLUMNS.get(
            table_key, ("", ""))
        # Whether this table's rows are named by what they DO.
        #
        # A separate flag from `shows_usage` even though both are true of
        # exactly one table today. They answer different questions - "does
        # anything point at this row" and "what does this row do" - and a
        # second table wanting one without the other would otherwise have to
        # untangle them first.
        # Two tables now, which is why this was kept separate from
        # `shows_usage` in the first place. Both answer "what does this
        # row do" for a table whose rows have no names of their own.
        self.counter_noun = COUNTER_NOUNS.get(table_key, "rows")
        self.describes_rows = table_key in DESCRIBED_TABLES
        self._usage: dict = {}
        # The ability half of the same question, and whether it could be
        # read. Both set together in `_recompute_usage`.
        self._ability_usage: dict = {}
        self._usage_seen = True

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 10, 24, 20)
        outer.setSpacing(10)

        outer.addLayout(page_intro(blurb))

        self.counter = QLabel("")
        self.counter.setProperty("role", "ok")
        outer.addWidget(self.counter)

        # Same place as every other Edit Game Data tab. These briefly shared
        # the counter's line here, which read well on this page and put the
        # pair somewhere different from the other nine.
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
        self.list.setFixedWidth(LIST_WIDTH)
        self.list.currentItemChanged.connect(self._on_selection)
        left.addWidget(self.list, 1)
        split.addLayout(left)

        right = QVBoxLayout()
        self.editing_label = QLabel(f"Select a {title.lower()}")
        self.editing_label.setStyleSheet("font-weight: 600; font-size: 12pt;")
        right.addWidget(self.editing_label)

        # "Used by: Angel Ring, Cursed Ring, ..." with each name clickable
        # through to that item on the Items tab.
        #
        # A `QLabel` with rich text rather than a list of buttons: the line
        # has to word-wrap, and a row of separate widgets cannot. Qt gives
        # link clicks back through `linkActivated` with the href, so the
        # item id rides in the href and nothing has to be looked up again.
        # Parented at construction, not by `addWidget`.
        #
        # `right` is a bare QVBoxLayout that is not attached to a widget
        # until much further down, so adding to it does NOT give this label
        # a parent - and `setVisible` on a parentless widget makes a
        # top-level WINDOW. Passing the parent here is what actually closes
        # that, and it holds however the layout is wired later.
        self.usage_label = QLabel("", self)
        self.usage_label.setProperty("role", "muted")
        self.usage_label.setWordWrap(True)
        self.usage_label.setTextFormat(Qt.RichText)
        self.usage_label.linkActivated.connect(self._on_usage_link)
        # Parented before being hidden or shown - a parentless
        # `setVisible` makes a top-level WINDOW, which is what flashed at
        # startup. See `CollapsibleSection.__init__`.
        right.addWidget(self.usage_label)
        self.usage_label.setVisible(self.shows_usage)

        # These tables come from XML bundled with the tool, not from the
        # game, so "no records" here means the reference data failed to
        # load rather than that the game is not unpacked. The Tkinter tab
        # has always said so; the Qt page said nothing because it was never
        # built at all when its table was missing.
        self.empty_note = QLabel(
            "This table's reference data hasn't loaded.\n\n"
            "It downloads by itself when General Setup opens, so give it a "
            "moment. If it failed, General Setup \u2192 Advanced options "
            "\u2192 Reference Tables has a \u201cCheck for updates\u201d "
            "button.")
        self.empty_note.setProperty("role", "muted")
        self.empty_note.setWordWrap(True)
        self.empty_note.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        right.addWidget(self.empty_note)

        scroll = FormScrollArea()
        holder = QWidget()
        form = QVBoxLayout(holder)
        form.setContentsMargins(4, 4, 4, 4)
        form.setSpacing(2)

        # Plain fields first, in the engine's own order, then a section per
        # flag set. The order comes from `field_order` rather than being
        # re-listed here, so a field added to the spec appears without this
        # page being touched.
        plain = QWidget()
        plain_column = QVBoxLayout(plain)
        plain_column.setContentsMargins(0, 0, 0, 0)
        plain_column.setSpacing(2)
        # flag_fields is a tuple of names; a name with no known choice list
        # is treated as a plain field rather than dropped, because the value
        # is still editable even when the individual bits are not named.
        flag_names = {n for n in (self.spec.flag_fields or ())
                      if flag_choices(n, self.spec.entry_tag)}
        self.unresolved_flags = [n for n in (self.spec.flag_fields or ())
                                 if not flag_choices(n, self.spec.entry_tag)]
        for field_name in self.spec.field_order:
            if field_name in flag_names:
                continue
            # A field the loader declares as a PLAIN enum is a choice from a
            # list, so it gets a dropdown of the names it can hold.
            #
            # Without this, `ItemOptions.OptionType` - declared
            # `ItemOptionsType` with five named values - got a spin box. Its
            # value in the XML is the word `Cancel`, which the box read as
            # 0, so opening a row and touching anything wrote an integer
            # into a column that holds a name, and the integer then showed
            # up in the row's own label. Reported from real use.
            #
            # `flag_enums` already documented this case - "a plain enum is a
            # choice from a list and belongs in a dropdown" - and there was
            # simply no function for that half until `choice_enums`.
            names = enum_choices(field_name, self.spec.entry_tag)
            if names:
                row = ChoiceFieldRow(field_name, humanise(field_name), names)
            else:
                low, high = _range_for(field_name)
                row = NumericFieldRow(
                    field_name, humanise(field_name), low, high,
                    unknown=field_name.lower().startswith("unknown"))
            row.edited.connect(self._on_field_edited)
            self.rows[field_name] = row
            plain_column.addWidget(row)

        self.item_dropdowns = []
        if self.table_key == "map_trap":
            # Treasure Hunter is four treasure slots, not twenty loose
            # fields.
            #
            # The generic builder lays out `field_order` flat and puts every
            # flag field in its own section at the bottom, which for this
            # table reads `X1 Y1 Rare Item Id1 Common Item Id1 X2 Y2 ...`
            # followed by `Trap Flags1` .. `Trap Flags4` - so deciding what
            # treasure sits on one tile means reading five fields scattered
            # across two parts of the page. The Tkinter tab groups each slot
            # and is much easier to follow.
            #
            # Driven by `MAPTRAP_SLOTS` and `MAPTRAP_SLOT_FIELD_LABELS`, so
            # a fifth slot or a renamed field arrives from the engine
            # without this file changing.
            self.sections = []
            self.tiles = []
            self.tile_headings = []
            for slot in c.MAPTRAP_SLOTS:
                body = QWidget()
                body_column = QVBoxLayout(body)
                body_column.setContentsMargins(0, 0, 0, 0)
                body_column.setSpacing(2)
                # Where and what first, then the trap. The engine's dict
                # order puts Trap third, between the coordinates and the
                # items, which splits "what treasure is here" in half.
                ordered = sorted(
                    c.MAPTRAP_SLOT_FIELD_LABELS.items(),
                    key=lambda pair: SLOT_FIELD_ORDER.index(pair[0])
                    if pair[0] in SLOT_FIELD_ORDER else len(SLOT_FIELD_ORDER))
                for base, label in ordered:
                    field_name = f"{base}{slot}"
                    choices = flag_choices(field_name, self.spec.entry_tag)
                    if choices:
                        widget = FlagFieldPanel(
                            field_name, label,
                            _groups_for(field_name, choices), columns=3)
                    elif base in ("RareItemId", "CommonItemId"):
                        # A dropdown of item NAMES.
                        #
                        # These were spin boxes, so choosing what a tile
                        # gives you meant knowing that 47 is a Mythril Sword.
                        # The Tkinter tab shows names and so does every other
                        # id field in this interface.
                        widget = DropdownFieldRow(field_name, label)
                        # Wide enough for the names it holds. MEASURED: the
                        # combo rendered at its 160px floor inside a hugged
                        # tile column while its widest entry - "000 -
                        # Featherweave Cloak" - needs 210px, so item names
                        # were being cut off. Reported from real use.
                        #
                        # See TILE_COMBO_WIDTH: 210 is that measurement, and
                        # 240 copied from Job Commands did not fit at 1100.
                        widget.combo.setMinimumWidth(TILE_COMBO_WIDTH)
                        widget.set_choices(self._item_choices())
                        self.item_dropdowns.append(widget)
                    else:
                        low, high = _range_for(field_name)
                        widget = NumericFieldRow(field_name, label, low, high)
                    widget.edited.connect(self._on_field_edited)
                    self.rows[field_name] = widget
                    body_column.addWidget(widget)
                # NO collapsible wrapper. The data is always exposed.
                #
                # Three of the four tiles used to start collapsed, on the
                # reasoning that a map usually has treasure in one or two.
                # That reasoning was about VERTICAL room and stopped being
                # true when the tiles started sitting side by side - four
                # of them now fit at once, so hiding three costs a click
                # each and buys nothing. Reported from real use.
                heading = QLabel(f"Tile {slot}")
                heading.setStyleSheet("font-weight: 600;")
                body.layout().insertWidget(0, heading)
                self.tile_headings.append(heading)
                self.tiles.append(body)
            # The four tiles sit SIDE BY SIDE when the window can hold them.
            #
            # They ran down a single column with the rest of the width
            # empty: measured at 1920 the form was 1296px wide and used 437,
            # so 859px - two thirds of the page - was blank. At 2560 it was
            # 1499 of 1936.
            #
            # Job Commands solved exactly this for its ability and R/S/M
            # columns, so this reuses `ColumnFormBody` rather than growing a
            # second answer to one question. `hug_contents=True` is the part
            # that made that version work and matters here for the same
            # reason: without it a vertical scrollbar appearing resizes the
            # controls underneath it.
            #
            # `max_columns` is not capped. Four tiles are peers - there is
            # no reading order across them the way there is between
            # Abilities and R/S/M - so the layout takes as many as fit and
            # falls back to one at the 1100 minimum.
            self.slots_body = ColumnFormBody(
                min_column_width=TILE_COLUMN_WIDTH, spacing=8,
                hug_contents=True, row_major=True)
            for tile in self.tiles:
                self.slots_body.add_row(tile)
            form.addWidget(self.slots_body)
            form.addStretch(1)
            scroll.setWidget(holder)
            self.scroll = scroll
            right.addWidget(scroll, 1)
            split.addLayout(right, 1)
            outer.addLayout(split, 1)
            self._apply_view(*self.view_toggles.state())
            self.refresh_records()
            return

        self.sections = [CollapsibleSection(title, plain, expanded=True)]
        form.addWidget(self.sections[0])

        for field_name in (self.spec.flag_fields or ()):
            choices = flag_choices(field_name, self.spec.entry_tag)
            if not choices:
                continue
            label = humanise(field_name)
            panel = FlagFieldPanel(field_name, label,
                                   _groups_for(field_name, choices), columns=3)
            panel.edited.connect(self._on_field_edited)
            self.rows[field_name] = panel
            if self.table_key == "item_options":
                # Always visible. This page has exactly two fields, and
                # putting the one that matters behind a disclosure meant it
                # opened showing a dropdown and a closed header - nothing
                # you could do. A section earns its collapse when there is
                # something else competing for the space; here there is
                # not. Reported from real use.
                form.addWidget(panel)
            else:
                section = CollapsibleSection(label, panel, expanded=False)
                self.sections.append(section)
                form.addWidget(section)

        form.addStretch(1)
        scroll.setWidget(holder)
        self.scroll = scroll
        right.addWidget(scroll, 1)
        split.addLayout(right, 1)

        outer.addLayout(split, 1)
        self._apply_view(*self.view_toggles.state())
        self.refresh_records()

    def _item_choices(self) -> dict:
        """
        Item id -> name, for the treasure dropdowns.

        Read from the same `item` records the Items tab lists, so the two
        cannot disagree about what an item is called. Empty until that table
        has loaded, which is why `refresh_records` refills them rather than
        this being read once at construction.
        """
        # Plain names. `DropdownFieldRow.set_choices` puts the id in front
        # itself, so including it here rendered "001 - (1) Dagger".
        found = {0: "(None)"}
        for record in (self.state.item_table_records or {}).get("item", []):
            found[record.item_id] = getattr(record, "name", "") or "(unnamed)"
        return found

    # -- records --------------------------------------------------------------

    def records(self) -> list:
        return (self.state.item_table_records or {}).get(self.table_key, [])

    def refresh_records(self) -> None:
        self.list.clear()
        # Built once per refresh, before the rows that read it. Recomputing
        # inside `_item_for` would walk the whole item table 85 times.
        self._recompute_usage()
        for record in self.records():
            self.list.addItem(self._item_for(record))
        # The treasure dropdowns depend on a DIFFERENT table from the one
        # this page is showing, so they are refilled whenever records are
        # reloaded rather than only when this page's own table arrives.
        for dropdown in getattr(self, "item_dropdowns", []):
            dropdown.set_choices(self._item_choices())
        set_empty_state(
            self.empty_note, bool(self.records()),
            self.scroll, self.search, self.list, self.editing_label,
            self.usage_label if self.shows_usage else None)
        self._mark_edited()
        self._update_counter()
        if self.list.count():
            self.list.setCurrentRow(0)

    def _recompute_usage(self) -> None:
        """
        Rebuilds both halves of the reverse index.

        Two sources, one index. Items reach these rows through their
        Additional Data row; abilities reach them through their own
        override column. Counting only the first is what made rows that an
        ability depends on read as `unused`.

        `_usage_seen` records whether the ability half could be read at
        all, so a row with no users can say which of the two things it
        means.
        """
        if not self.shows_usage:
            self._usage = {}
            self._ability_usage = {}
            self._usage_seen = True
            return
        self._usage = table_usage(self.state, self._usage_column,
                                  self._usage_through)
        self._ability_usage = ability_usage(self.state, self._usage_column)
        # Equip Bonus has no ability half, so its item index IS the whole
        # answer and nothing about it is uncertain. Only a column abilities
        # can reach depends on the overrides being loaded.
        self._usage_seen = (self._usage_column not in ABILITY_USAGE_COLUMN
                            or usage_certainty(self.state))

    def _users_of(self, row_id: int) -> int:
        """How many things point at this row, items and abilities together."""
        return (len(self._usage.get(row_id, []))
                + len(self._ability_usage.get(row_id, [])))

    def select_record(self, record_id) -> None:
        """
        Used by a jump from another tab - Items' "Edit this Equip Bonus".

        The page had none of this, so the shell fell through to
        `load_record` and the jump filled the editor while leaving the list
        of 85 rows wherever it happened to be. Same gap Abilities and Job
        Commands had.
        """
        if not select_list_row(self.list, int(record_id), self.search):
            self.load_record(int(record_id))

    def refresh_usage(self) -> None:
        """
        Recomputes the reverse index without disturbing the selection.

        Repointing an item's `EquipBonusId` on the Items tab changes which
        rows are in use here, and the counts on 85 list rows go stale the
        moment it happens. `refresh_records` would fix them too, but it
        clears the list and snaps the selection back to row 0 - so editing
        an item would move this page out from under anybody who had it open.
        """
        if not self.shows_usage:
            return
        self._recompute_usage()
        self._redress_rows()
        if self.current_id is not None:
            self._show_usage(self.current_id)

    def _redress_rows(self) -> None:
        """
        Rewrites every row's text and tooltip in place.

        In place, not `refresh_records`: the list keeps its rows, so the
        selection and the scroll position stay where the person left them.
        Shared with `refresh_from_store`, because a row's derived name comes
        from its VALUES - so an edit made on another page changes what a row
        should be called here, not only whether it is marked.
        """
        by_id = {r.item_id: r for r in self.records()}
        for i in range(self.list.count()):
            item = self.list.item(i)
            record = by_id.get(item.data(Qt.UserRole))
            if record is not None:
                self._dress_item(item, record)

    def refresh_from_store(self) -> None:
        """
        Re-read the selected row when this page comes back on screen.

        Every row is re-dressed, not just the selected one: All Game Data
        reaches any row of this table, and `describes_rows` derives a row's
        NAME from its values - so "001 - MA +2" beside a store that now says
        7 is the same stale-display fault one row over.

        The list is not rebuilt and the selection is not moved. See
        `widgets/visible_refresh.py`.
        """
        if self.current_id is None:
            return
        self.load_record(self.current_id)
        if self.shows_usage:
            # Recomputes the reverse index as well, and re-dresses the rows
            # itself. Called rather than duplicated so there is one answer
            # to "what does a row say" instead of two.
            self.refresh_usage()
        elif self.describes_rows:
            self._redress_rows()
        self._mark_edited()
        self._update_counter()

    def _effective_values(self, record) -> dict:
        """
        The record's values with this session's pending edits applied.

        The record objects come from the XML and never change - edits live
        in `state.item_table_edits`. A label built from the record alone is
        therefore correct exactly until somebody edits the row, which is the
        half of this that is easy to forget: a list entry disagreeing with
        the form beside it is worse than "(unnamed)".
        """
        values = dict(getattr(record, "values", {}) or {})
        edits = (self.state.item_table_edits.get(self.table_key, {})
                 .get(record.item_id, {}))
        values.update(edits)
        return values

    def display_name(self, record) -> str:
        """The row's name, with the table's own overrides applied."""
        override = ROW_NAME_OVERRIDES.get(self.table_key, {}).get(
            record.item_id)
        if override:
            return override
        name = getattr(record, "name", "") or ""
        if name:
            return name
        if self.describes_rows:
            return DESCRIBED_TABLES[self.table_key](
                self._effective_values(record), self.spec.field_order)
        return "(unnamed)"

    def _label_for(self, record) -> str:
        """
        The row's text in the list.

        Browsing 85 rows to find one worth editing means knowing which are
        in use, and that is why a usage suffix is here at all. What changed
        is WHICH rows carry one: 78 of the 85 are worn by exactly one item,
        so "(1 item)" was near-constant text taking about 30% of every row's
        width while saying almost nothing. The suffix now marks only what is
        worth marking - unused, or worn by several - and the common case
        spends its width on the name instead.

        Nothing is lost by it: `_tooltip_for` spells the usage out in full
        on hover, and the detail pane's "Used by" line always names the
        items outright.
        """
        return (f"{record.item_id:03d} - {self.display_name(record)}"
                + self.usage_suffix(record.item_id))

    def usage_suffix(self, row_id: int) -> str:
        """
        The `  . no items` / `  . 5 users` tail, or "" when the row is
        unremarkable.

        Public and separate because the width check has to measure the row
        as it will actually be drawn. It used to rebuild this suffix by
        hand, which is two mechanisms answering one question - and the one
        that drifts is the one nothing is looking at.
        """
        if not self.shows_usage:
            return ""
        users = self._users_of(row_id)
        noun, empty = USAGE_NOUNS[self.table_key]
        if not users:
            # An empty word means this table does not comment on rows
            # nothing uses. Not the same as having nothing to say about
            # rows that ARE used - the count below still appears.
            return f"  \u00b7 {empty}" if empty else ""
        if users > 1:
            return f"  \u00b7 {users} {noun}"
        return ""

    def _tooltip_for(self, record) -> str:
        """
        The whole truth, on hover, for whatever the row had to shorten.

        A list row names at most three effects and at most two values inside
        one of them, so "+2 more" and "Immune 18 statuses" are both real
        losses of detail. Hovering is where they come back, which is what
        lets the row itself stay short enough to read.
        """
        if not self.describes_rows:
            return ""
        if self.table_key == "item_options":
            # The usage line belongs here too, not only on Equip Bonus: the
            # row label caps at one status, so hover is where both the rest
            # of the statuses and the rest of the users come back.
            return (f"{record.item_id:03d}\n"
                    + inflict_status_tooltip(self._effective_values(record))
                    + "\n\n" + self._usage_tooltip_line(record.item_id))
        # Every value, not the two a list row has room for. This is the
        # whole point of the tooltip: "Immune 18 statuses" is readable and
        # lossy, and hovering is where the eighteen come back. Without the
        # argument the tooltip repeated the row verbatim and recovered
        # nothing.
        phrases = equip_bonus_effects(self._effective_values(record),
                                      self.spec.field_order,
                                      values_named=999)
        lines = [f"{record.item_id:03d} - "
                 + (" \u00b7 ".join(phrases) if phrases else "(no effect)")]
        if self.shows_usage:
            users = self._usage.get(record.item_id, [])
            # `USAGE_EMPTY` when there is nobody, and "Used by" rather than
            # "Worn by" when there is. Changing only the empty half would
            # leave one line with two labels depending on its state, which
            # is worse than either. "Used by" is also the truer verb: the
            # page's visible line already says it, and an Equip Bonus id
            # sits on item types that are not worn.
            #
            # The list itself is unchanged - every user, uncapped. This
            # tooltip exists to recover what the row shortened, so capping
            # it would take back the thing it is for.
            lines.append(("Used by: " + ", ".join(n for _id, n in users))
                         if users else USAGE_EMPTY[self.table_key][1])
        return "\n".join(lines)

    def _usage_tooltip_line(self, row_id: int) -> str:
        """Who uses this row, for the hover text, items and abilities both."""
        users = self._usage.get(row_id, [])
        abilities = self._ability_usage.get(row_id, [])
        if not users and not abilities:
            return (USAGE_EMPTY[self.table_key][1]
                    + ("" if self._usage_seen
                       else " (ability overrides not loaded)"))
        parts = []
        if users:
            parts.append("Items: " + _named_up_to(users))
        if abilities:
            parts.append("Abilities: " + _named_up_to(abilities))
        return "Used by - " + "; ".join(parts)

    def _dress_item(self, item: QListWidgetItem, record) -> None:
        """
        Puts the text and the tooltip on a row.

        One place, because three call sites need them and they must agree:
        the initial build, `refresh_usage` after an item is repointed, and
        `_relabel_current` after the bonus itself is edited. Two of those
        used to copy `_item_for(...).text()`, which took the text and left
        the tooltip behind.
        """
        item.setText(self._label_for(record))
        tip = self._tooltip_for(record)
        if tip:
            item.setToolTip(tip)

    def _item_for(self, record) -> QListWidgetItem:
        item = QListWidgetItem()
        item.setData(Qt.UserRole, record.item_id)
        self._dress_item(item, record)
        return item

    def _filter_list(self, text: str) -> None:
        needle = text.strip().lower()
        for i in range(self.list.count()):
            item = self.list.item(i)
            if not needle:
                item.setHidden(False)
                continue
            haystack = item.text().lower()
            if self.shows_usage:
                # Searching an Equip Bonus row by the item that wears it.
                # The rows are mostly unnamed, so "Angel Ring" is the only
                # handle most people have on the one they want.
                row_id = item.data(Qt.UserRole)
                haystack += " " + " ".join(
                    name.lower() for _id, name
                    in (self._usage.get(row_id, [])
                        + self._ability_usage.get(row_id, [])))
            item.setHidden(needle not in haystack)

    def _on_selection(self, current, _previous) -> None:
        if current is not None:
            self.load_record(current.data(Qt.UserRole))

    def load_record(self, record_id: int) -> None:
        by_id = {r.item_id: r for r in self.records()}
        record = by_id.get(record_id)
        if record is None:
            return
        self.current_id = record_id
        self.editing_label.setText(
            f"Editing: {record_id:03d} - {self.display_name(record)}")
        if self.shows_usage:
            self._show_usage(record_id)

        already = self.state.item_table_edits.get(self.table_key, {}).get(record_id, {})
        for field_name, row in self.rows.items():
            if field_name in already:
                row.load(already[field_name], True)
            else:
                row.load(record.values.get(field_name, ""), False)

    # -- editing --------------------------------------------------------------

    def _show_usage(self, bonus_id: int) -> None:
        """
        Renders "Used by: ..." with each item name a link to the Items tab.

        Escaped, because an item name is game text and this label is rich
        text - a name containing `&` or `<` would otherwise render wrong or
        swallow the rest of the line.
        """
        users = self._usage.get(bonus_id, [])
        abilities = self._ability_usage.get(bonus_id, [])
        if not users and not abilities:
            self.usage_label.setText(
                USAGE_EMPTY[self.table_key][0] + self._unseen_note())
            return
        parts = []
        if users:
            parts.append("Used by: " + self._links("Items", users))
        if abilities:
            parts.append("Used by abilities: "
                         + self._links("Abilities", abilities))
        self.usage_label.setText(
            " &nbsp; ".join(parts) + self._unseen_note())

    def _links(self, page: str, users: list) -> str:
        """
        Up to `USAGE_LIST_LIMIT` names, each a link to `page`.

        The page rides in the href beside the id because this line now
        names two KINDS of user, and a bare id could not say which tab it
        belonged to - clicking an ability would have opened the item with
        that number.
        """
        shown = users[:USAGE_LIST_LIMIT]
        links = " ".join(
            f'<a href="{page}:{row_id}">{escape(name)}</a>'
            + ("," if index < len(shown) - 1 else "")
            for index, (row_id, name) in enumerate(shown))
        remaining = len(users) - len(shown)
        return links + (f", and {remaining} more" if remaining > 0 else "")

    def _unseen_note(self) -> str:
        """
        The part of the answer this tool does not have, said out loud.

        Only when it applies: once the ability overrides are loaded this is
        empty, and on Equip Bonus it never appears at all.
        """
        if self._usage_seen:
            return ""
        return (" Abilities can also use these rows, and that table is not "
                "loaded yet - unpack the game files to include it.")

    def _on_usage_link(self, href: str) -> None:
        page, _, raw = href.rpartition(":")
        try:
            row_id = int(raw)
        except (TypeError, ValueError):
            return
        self.navigate_requested.emit(page or "Items", row_id)

    def _on_field_edited(self) -> None:
        if self.current_id is None:
            return
        table = self.state.item_table_edits.setdefault(self.table_key, {})
        edits = table.setdefault(self.current_id, {})
        for field_name, row in self.rows.items():
            if row.included:
                edits[field_name] = row.get_value_str()
            elif field_name in edits:
                del edits[field_name]
        if not edits:
            table.pop(self.current_id, None)
        if not table:
            self.state.item_table_edits.pop(self.table_key, None)

        self._mark_edited()
        self._relabel_current()
        self._update_counter()
        self.edits_changed.emit()

    def _relabel_current(self) -> None:
        """
        Re-derives the current row's label after an edit.

        A label derived once at load is a label that goes stale the moment
        somebody changes the value it was derived from - change MA Bonus
        from 2 to 4 and the list still says "MA +2" beside a form saying 4.

        Follows `refresh_usage`, which is where this page already rebuilds
        list text after an edit: the row's own item is rewritten in place
        rather than the list being cleared, so the selection and the scroll
        position stay where the person left them. The "Editing:" heading
        carries the same name and is rebuilt with it, for the same reason -
        two places showing one name is two places to go stale.
        """
        if not self.describes_rows or self.current_id is None:
            return
        record = {r.item_id: r for r in self.records()}.get(self.current_id)
        if record is None:
            return
        name = self.display_name(record)
        self.editing_label.setText(f"Editing: {self.current_id:03d} - {name}")
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item.data(Qt.UserRole) == self.current_id:
                self._dress_item(item, record)
                break

    def _mark_edited(self) -> None:
        table = self.state.item_table_edits.get(self.table_key, {})
        for i in range(self.list.count()):
            item = self.list.item(i)
            mark_edited(item, bool(table.get(item.data(Qt.UserRole))))

    def _update_counter(self) -> None:
        # Scoped to THIS table. `edited_item_table_total_count` deliberately
        # excludes map_trap and the ability tables, because Treasure Hunter
        # and Abilities have their own tabs and their own counts - folding
        # them in once made sibling tabs inflate each other's figures.
        edited = self.state.edited_item_table_count(self.table_key)
        self.counter.setText(
            edit_counter_text(edited, self.list.count(), self.counter_noun))


    def _apply_view(self, hide_notes: bool, hide_unknown: bool,
                    hide_comments: bool) -> None:
        apply_view_toggles(self.rows.values(), hide_notes, hide_unknown,
                           hide_comments)
