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

from ... import constants as c
from ... import item_xml_io as ix
from ..widgets.actions import (
    page_intro,
    ViewToggles, apply_view_toggles, mark_edited, select_list_row,
    set_empty_state)
from ..widgets.field_rows import (
    DropdownFieldRow,
    CollapsibleSection, FlagFieldPanel, NumericFieldRow, split_words,
)
from ..widgets.form_scroll import FormScrollArea

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


def flag_choices(field_name: str) -> list:
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
    return []


def _groups_for(field_name: str, choices: list) -> dict:
    """Reuses the engine's own grouping where it has one."""
    if field_name == "EquippableItems":
        return c.EQUIP_GROUPS
    if field_name in ("InnateStatus", "ImmuneStatus", "StartingStatus"):
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


class TableEditorPage(QWidget):
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
        self.shows_usage = table_key == "item_equip_bonus"
        # Whether this table's rows are named by what they DO.
        #
        # A separate flag from `shows_usage` even though both are true of
        # exactly one table today. They answer different questions - "does
        # anything point at this row" and "what does this row do" - and a
        # second table wanting one without the other would otherwise have to
        # untangle them first.
        self.describes_rows = table_key == "item_equip_bonus"
        self._usage: dict = {}

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
        self.usage_label = QLabel("")
        self.usage_label.setProperty("role", "muted")
        self.usage_label.setWordWrap(True)
        self.usage_label.setTextFormat(Qt.RichText)
        self.usage_label.linkActivated.connect(self._on_usage_link)
        self.usage_label.setVisible(self.shows_usage)
        right.addWidget(self.usage_label)

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
        flag_names = {n for n in (self.spec.flag_fields or ()) if flag_choices(n)}
        self.unresolved_flags = [n for n in (self.spec.flag_fields or ())
                                 if not flag_choices(n)]
        for field_name in self.spec.field_order:
            if field_name in flag_names:
                continue
            low, high = _range_for(field_name)
            row = NumericFieldRow(field_name, humanise(field_name), low, high,
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
                    choices = flag_choices(field_name)
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
                        widget.set_choices(self._item_choices())
                        self.item_dropdowns.append(widget)
                    else:
                        low, high = _range_for(field_name)
                        widget = NumericFieldRow(field_name, label, low, high)
                    widget.edited.connect(self._on_field_edited)
                    self.rows[field_name] = widget
                    body_column.addWidget(widget)
                # Only the first is open. Four expanded slots is more than
                # fits, and a map usually has treasure in one or two.
                section = CollapsibleSection(f"Item {slot}", body,
                                             expanded=slot == 1)
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
            return

        self.sections = [CollapsibleSection(title, plain, expanded=True)]
        form.addWidget(self.sections[0])

        for field_name in (self.spec.flag_fields or ()):
            choices = flag_choices(field_name)
            if not choices:
                continue
            label = humanise(field_name)
            panel = FlagFieldPanel(field_name, label,
                                   _groups_for(field_name, choices), columns=3)
            panel.edited.connect(self._on_field_edited)
            self.rows[field_name] = panel
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
        self._usage = equip_bonus_usage(self.state) if self.shows_usage else {}
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
        self._usage = equip_bonus_usage(self.state)
        by_id = {r.item_id: r for r in self.records()}
        for i in range(self.list.count()):
            item = self.list.item(i)
            record = by_id.get(item.data(Qt.UserRole))
            if record is not None:
                self._dress_item(item, record)
        if self.current_id is not None:
            self._show_usage(self.current_id)

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
            return equip_bonus_descriptor(self._effective_values(record),
                                          self.spec.field_order)
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
        label = f"{record.item_id:03d} - {self.display_name(record)}"
        if not self.shows_usage:
            return label
        users = self._usage.get(record.item_id, [])
        if not users:
            return f"{label}  \u00b7 unused"
        if len(users) > 1:
            return f"{label}  \u00b7 {len(users)} items"
        return label

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
            lines.append("Worn by: " + (", ".join(n for _id, n in users)
                                        if users else "nothing"))
        return "\n".join(lines)

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
                haystack += " " + " ".join(
                    name.lower() for _id, name
                    in self._usage.get(item.data(Qt.UserRole), []))
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
        if not users:
            self.usage_label.setText(
                "Not currently used by any item, counting any pending "
                "EquipBonusId edits.")
            return
        shown = users[:USAGE_LIST_LIMIT]
        links = " ".join(
            f'<a href="{item_id}">{escape(name)}</a>'
            + ("," if index < len(shown) - 1 else "")
            for index, (item_id, name) in enumerate(shown))
        remaining = len(users) - len(shown)
        tail = f", and {remaining} more" if remaining > 0 else ""
        self.usage_label.setText(f"Used by: {links}{tail}")

    def _on_usage_link(self, href: str) -> None:
        try:
            item_id = int(href)
        except (TypeError, ValueError):
            return
        self.navigate_requested.emit("Items", item_id)

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
            f"{edited} of {self.list.count()} have pending edits")


    def _apply_view(self, hide_notes: bool, hide_unknown: bool,
                    hide_comments: bool) -> None:
        apply_view_toggles(self.rows.values(), hide_notes, hide_unknown,
                           hide_comments)
