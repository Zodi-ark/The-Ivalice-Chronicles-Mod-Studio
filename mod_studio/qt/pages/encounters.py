"""
Edit Game Data / Encounters.

516 rows of `OverrideEntryData` - the per-battle unit overrides that decide
who shows up, as what job, with what equipment. The most heavily documented
table in the tool and the one with the most honest uncertainty in it.

Three things here are unlike every other tab:

**A row's address is a PAIR.** `(Key, Key2)` together identify a row, not
`Key` alone. A list keyed on `Key` would silently collapse rows that differ
only in `Key2`.

**Inherit is per-field, and it is not one value.** `constants.
ENTRY_INHERIT_VALUES` gives each field its own:

    Spriteset    0   leave the unit's sprite set alone
    MainJob      0   leave the unit's job alone
    JobUnlock    20  leave job unlocks alone

Twenty. Not 0, not -1. Together with Poaching's "0 means none, -1 is
invalid" and the ability override layer's "-1 means inherit", that makes
three different conventions across three adjacent tables, each right for its
own. Anything that made them consistent would break at least two, so the
values come from `ENTRY_INHERIT_VALUES` and are never assumed.

**Field confidence is shown, not hidden.** Every field is confirmed,
inferred, or genuinely unknown, and the page says which. That is the
project's honesty convention: a field nobody has worked out is labelled as
such rather than given an invented meaning that reads as fact.

**Rows cannot be added, and the row COUNT is what matters.** Zodi
established this from in-game testing of Dark Knight Expansion: rows added
to `OverrideEntryData` are ignored by the game, so the published mod
*repurposed* ten existing rows into `(95, 0..9)` instead. Vanilla has 516
rows, the working mod has 516, and an earlier Mod Studio re-export had 526
- precisely `vanilla union mod`, with the ten vacated addresses coming back
from vanilla. That was the bug.

Worth being exact about what is and is not known: `Key 95` does not exist in
vanilla at all, so the mod DID introduce an address the game had never seen,
and it works. What it held constant was the count. Whether the real
constraint is the count, something about file size or offsets, or something
else is **not established**.

So moving a row is the primitive here, not adding or deleting one. Dropping
a row (`entry_dropped`) exists in the engine for recovery - it is how a mod
that vacated an address is read back - rather than as something to offer as
"delete this row", which would invite exactly the row-count change that does
not work.
"""
from __future__ import annotations

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFontMetrics, QPalette, QPen
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QDialog, QDialogButtonBox,
    QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QSizePolicy, QStyle,
    QStyledItemDelegate, QStyleOptionViewItem, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from ... import constants as c
from ... import encounter_names
from ... import entd
from ... import nxd_data
from ... import nxd_layouts
from ... import reference_names
from ..widgets.actions import (
    page_intro,
    COPY_LANGUAGES_LABEL, COPY_LANGUAGES_NOTE, ViewToggles, apply_view_toggles,
    copy_edits_to_languages, ensure_language_loaded, mark_edited,
    language_order, set_empty_state, edit_counter_text)
from ..widgets.field_rows import (
    CollapsibleSection, DropdownFieldRow, NumericFieldRow)
from ..widgets.form_scroll import FormScrollArea
from ..widgets.visible_refresh import RefreshesWhenVisible
from .poaching import BoolFieldRow, TextFieldRow
# The list pane's width, from the page Zodi asked this one to match.
# Imported rather than repeated: two copies of 340 drift, and the reason
# they should agree is that they are the same list in the same place.
from .table_editor import LIST_WIDTH

# Read from Nenkai's layout, not restated. This one was already correct -
# CharaName really does have exactly Name and Comment as strings - but it
# is derived anyway, because being right today is what the other three
# lists were too, until the tables they described changed.
CHARA_TEXT_FIELDS = tuple(
    nxd_layouts.translated_columns("CharaName", c.CHARANAME_TEXT_FIELDS))

# Too long for the 200px label column, so the label says "Comment" and
# this says the rest.
COMMENT_TOOLTIP = (
    "FF16Tools writes this note into the converted table. It is not data the game reads, so editing it changes nothing in play - it is here because a mod that ships the row should ship the row as it found it.")

CONFIDENCE_SUFFIX = {
    "confirmed": "",
    "inferred": "  (inferred)",
    "unknown": "  (unknown)",
}

#: How a row with no `OverrideEntryData` behind it is drawn.
#:
#: A fixed grey rather than a palette role, for the reason the rest of this
#: tool picks its own colours: the stylesheet is applied to the
#: QApplication after these widgets are built, so a palette lookup here
#: reads an unstyled widget. Mid grey reads as "present but not yours" on
#: both the light and dark stylesheets.
GREYED = QBrush(QColor(0x88, 0x88, 0x88))

#: Where the list opens the first time it is used in a session.
#:
#: Zodi's choice, and it is a choice rather than a fact: "it should ...
#: open so that the list is scrolled down so that 384 Chapter 1 - The
#: Siedge Weald appears at the top with no encounter expanded and no unit
#: selected."
#:
#: There is no rule in the data that lands on 384. It begins an 86-long run
#: of named story battles - "Chapter 1 - The Siedge Weald", "Dorter Slums",
#: "Sand Rat's Sietch" - but plenty of encounters below it are named too
#: (the random battles are "Dorvauldar Marsh East 1" and so on, and the
#: first "Chapter" name is 287). So it is a curated starting point, of the
#: same kind as `EncounterNames.txt` itself, and it is written down as one
#: rather than derived from a pattern that would be invented.
#:
#: The id is what is fixed, not the name: renaming 384 in
#: `EncounterNames.txt` still opens on the same battle.
FIRST_STORY_ENCOUNTER = 384

#: What a greyed row says when you select it. The right-hand pane, not a
#: tooltip.
#:
#: It was both, and the tooltip was the wrong half: 7,313 rows carried a
#: four-line explanation that appeared under the pointer while scrolling
#: past them. The same sentence is on the page the moment one is selected,
#: which is the moment it is worth reading.
ENTD_ONLY_MESSAGE = (
    "This ENTD unit lacks an override row. Since the mod loader ignores "
    "new OverrideEntryData rows, the count must stay at 516. Replace an "
    "unused row instead.")

#: Between the two halves of a slot's label: its sprite, then its level.
SLOT_SEPARATOR = "  ·  "
#: Blank space kept between the longest sprite name and the dot column, so
#: the two never touch on the row that sets the width.
SLOT_COLUMN_GAP = 10


class SlotColumnDelegate(QStyledItemDelegate):
    """
    Draws a slot row's two halves as two columns, so the dots line up.

    "we should make it so the dots line up vertically making the list much
    easier on the eye and easier to read using the longest spriteset name
    as the baseline for the dots."

    **Padding the string with spaces cannot do this.** The list is drawn in
    the system UI font, which is proportional - the tool sets no
    font-family anywhere - so a space is one narrow glyph among many widths
    and "Ramza" padded to the character count of "Generic Monster" lands
    wherever those particular letters happen to end. Alignment is a
    question about pixels, so it is answered in the one place that knows
    about pixels: the view.

    The label itself is left alone. `slot_label` still returns one joined
    string, which is what `_relabel_slot`, the Export pane and every check
    read - moving the split into the model would have made the list's
    appearance a fact about the data.

    The background, the selection bar and the edited-row marking are all
    still drawn by the style: `opt.text` is emptied and the standard
    control is drawn first, so the only thing done by hand is the text.
    `initStyleOption` folds the item's own font and foreground into the
    option on the way, which is how a greyed ENTD row stays grey and an
    edited row stays green and bold without this knowing either exists.
    """

    #: The least room the sprite column may be squeezed to when the row is
    #: too narrow for both halves at their natural widths. Something has to
    #: be elided at that point; this decides which.
    MIN_SPRITE_COLUMN = 60

    def __init__(self, parent=None):
        super().__init__(parent)
        #: Pixels from the start of the text to the dot. 0 until the page
        #: has measured its rows, and while it is 0 every row is drawn the
        #: ordinary way - so the list is never worse than it was.
        self.dot_x = 0
        #: Pixels the widest level text needs, dot included. The column is
        #: never pushed past what leaves room for it.
        self.tail_reserve = 0

    def dot_for(self, width: int) -> int:
        """
        Where the dot goes in a row `width` pixels wide.

        **The ideal is the widest sprite name; the limit is the widest
        level.** Aligning on the sprite alone is what was asked for and is
        right until the two together need more room than the row has - the
        list is a fixed 340px and 'Party Level - Random' is nearly half of
        it - at which point holding the ideal would elide the level on
        every row that has a long one. Found by measurement, not foreseen:
        selecting a sprite whose name is wider than any in the file pushed
        the column out by 10px and took the level with it.

        Clamped here rather than when the column is measured, because this
        is the only place the row's real width is known. Every slot row is
        the same width, so they all still line up with each other.
        """
        if self.dot_x <= 0 or width <= 0:
            return 0
        room = width - self.tail_reserve
        return max(min(self.dot_x, room), self.MIN_SPRITE_COLUMN)

    def paint(self, painter, option, index) -> None:
        text = str(index.data(Qt.DisplayRole) or "")
        # Encounter rows have no separator and greyed rows have the same
        # one as any other, so this is the only test needed: a row either
        # has two halves or it does not.
        if self.dot_x <= 0 or SLOT_SEPARATOR not in text:
            super().paint(painter, option, index)
            return
        left, right = text.split(SLOT_SEPARATOR, 1)

        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = ""
        widget = opt.widget
        style = widget.style() if widget is not None else QApplication.style()
        style.drawControl(QStyle.CE_ItemViewItem, opt, painter, widget)

        rect = style.subElementRect(QStyle.SE_ItemViewItemText, opt, widget)
        if rect.width() <= 0:
            return
        dot = self.dot_for(rect.width())
        metrics = QFontMetrics(opt.font)
        colour = (opt.palette.color(QPalette.HighlightedText)
                  if opt.state & QStyle.State_Selected
                  else opt.palette.color(QPalette.Text))
        painter.save()
        painter.setFont(opt.font)
        painter.setPen(QPen(colour))
        # The sprite, clipped to its own column rather than to the row, so
        # a name longer than the widest one measured cannot run under the
        # dot instead of being elided.
        room = max(0, min(dot - SLOT_COLUMN_GAP, rect.width()))
        painter.drawText(QRect(rect.x(), rect.y(), room, rect.height()),
                         Qt.AlignVCenter | Qt.AlignLeft,
                         metrics.elidedText(left, Qt.ElideRight, room))
        # The dot and the level, always starting at the same x.
        tail_x = rect.x() + dot
        tail_room = rect.right() - tail_x + 1
        if tail_room > 0:
            tail = f"·  {right}"
            painter.drawText(
                QRect(tail_x, rect.y(), tail_room, rect.height()),
                Qt.AlignVCenter | Qt.AlignLeft,
                metrics.elidedText(tail, Qt.ElideRight, tail_room))
        painter.restore()


def field_label(field_name: str) -> str:
    """
    The label, with its confidence tier attached where it is not confirmed.

    An inferred field is one read from its name and the values real rows
    carry; an unknown one is genuinely not understood. Saying so in the
    label is the point - a mod author deciding whether to touch a field
    needs to know how much is actually known about it.
    """
    # Two places hold labels, and only one was being read.
    #
    # `ENTRY_FIELD_LABELS` covers the renamed fields - `Unknown4` is really
    # the unit name, `EntryUnknown1D` is the primary job command. Everything
    # numeric gets its label from `ENTRY_NUMERIC_FIELDS`, which already
    # spells them properly: "Job Level", "Job Unlock". Reading only the
    # first meant those two fell through to the raw column name and showed
    # as `JobLevel` and `JobUnlock`.
    label = c.ENTRY_FIELD_LABELS.get(field_name)
    if label is None:
        numeric = c.ENTRY_NUMERIC_FIELDS.get(field_name)
        # (min, max, label, help) - the label is the third item.
        label = numeric[2] if numeric and len(numeric) > 2 else field_name
    tier = c.ENTRY_FIELD_CONFIDENCE.get(field_name, "unknown")
    return label + CONFIDENCE_SUFFIX.get(tier, "")


#: The one field on this page that gets a note, and what it says.
#:
#: "on the Encounters page for Job Level can we give it a field note that
#: says 'Changes the level of the job selected in Job Unlock.'" - which is
#: a different KIND of sentence from the ones that came off. It says what
#: the field is for; they said which number meant inherit, and no field
#: shows that number any more.
FIELD_NOTES = {
    "JobLevel": "Changes the level of the job selected in Job Unlock.",
}


def inherit_note(field_name: str) -> str:
    """
    The note under a field, which for almost every field is now nothing.

    "can we remove the field notes for the Unit Name, Main Job, Job Unlock,
    Job Level, Spriteset, Primary Job Command, Secondary Job Command,
    Reaction, Support, Movement, Right Hand, Left Hand, Head, Body,
    Accessory, Level, Bravery, Faith, Position X, Position Y, and Initial
    Direction" - which is all twenty-one fields that had one.

    They earned their place when the field showed `-1` and the note was the
    only thing saying what -1 meant. The field now shows the value it
    inherits, so the note was explaining a sentinel the reader never sees,
    in a sentence repeated down twenty-one rows.

    The inherit value itself has not gone anywhere: it is in
    `ENTRY_INHERIT_VALUES`, it is what the Inherit entry still writes, and
    `entry_inherit_help` still returns the wording for anything that wants
    it.
    """
    return FIELD_NOTES.get(field_name, "")


# =============================================================================
# The twelve id fields, and where each one's list comes from
# =============================================================================
# Reported from real use, and the reason these stopped being spin boxes:
# nobody knows that Movement 493 is Lifefont or that Head 155 is a Genji
# Helm. Each list is built from the table that page edits, live, so a rename
# on Abilities or Items shows up here without anything being copied.
#
# **The correction that matters most.** The obvious generalisation - "0
# means Inherit" - is true for Unit Name and Main Job ONLY. The other ten
# inherit at -1, and 0 is a real and different value on every one of them
# ("Nothing"). Building all twelve on "0 means Inherit" would silently
# merge "leave this alone" with "equip nothing" on ten fields. The values
# come from `ENTRY_INHERIT_VALUES` and `ENTRY_SPECIAL_VALUES` rather than
# from anything written out here, and `constants.py` asserts the two never
# collide - so this cannot be reintroduced by editing one of them.
#
# Which table feeds which field was measured against the real ENTD data
# before it was wired, because a wrong name is worse than a number:
#
#     ENTD byte 2  -> CharaName      96.3% of used ids have a name;
#                                    the common ones are Ramza, Delita,
#                                    Argath, Agrias
#     ENTD byte 10 -> Job            98.3% named; Squire, Chocobo, Knight
#     ENTD 18/21   -> ItemData       100% named, and they are helmets on
#                                    Head and weapons on Right Hand
#     ENTD 29/11   -> JobCommandData 33%/55% named - the id space is right,
#                                    many rows of that table simply have no
#                                    name. Those show as the number.
# =============================================================================

#: Every field on this page that is a dropdown: the twelve that point at a
#: row in another table, and the six that hold a value with a fixed meaning.
#:
#: One name for "is this a dropdown?", because four places ask it - which
#: control to build, which lists to refill, whose Inherit entry to retitle,
#: and which fields must NOT also carry an "Inherits N" caption. Asking it
#: as `field in c.ENTRY_FIELD_LABELS` in each of them is how three of them
#: end up knowing about the six and the fourth does not.
DROPDOWN_FIELDS = tuple(c.ENTRY_FIELD_LABELS) + tuple(c.ENTRY_VALUE_FIELDS)

#: The AbilityType each of the three ability fields accepts. Derived rather
#: than written out: the three column names ARE the three type names, and
#: the assertion below is what keeps that true if either list changes.
ABILITY_FIELD_TYPES = {name: name for name in sorted(c.RSM_ABILITY_TYPES)}
assert set(ABILITY_FIELD_TYPES) <= set(c.ENTRY_FIELD_LABELS)

#: Which `TypeFlags` an item must carry to be equippable in each slot.
#: Right and Left Hand take either - a shield goes in either hand.
EQUIPMENT_FIELD_TYPES = {
    "Head": ("Headgear",),
    "Body": ("Armor",),
    "Accessory": ("Accessory",),
    "RightHand": ("Weapon", "Shield"),
    "LeftHand": ("Weapon", "Shield"),
}

#: The sections that start open, by NAME rather than by position.
#:
#: Requested from real use: these four hold everything somebody edits, and
#: opening each of them on every row was four clicks before any work
#: started. The four below the fold - placement, the unknown flag bank and
#: the two unknown collections - stay closed, which is what keeps the form
#: a page rather than a wall.
#:
#: By name because an index cannot survive a reorder, and the sections were
#: reordered in the same change that set this.
SECTIONS_OPEN_BY_DEFAULT = ("Identity", "Abilities", "Equipment",
                            "Stats & Level")

#: What the Inherit entry says when there is nothing to name.
INHERIT_LABEL = "Inherit"
#: ...and what is appended once there IS something to name.
#:
#: Empty, at Zodi's request: "can we drop the tag line (Inherited)". The
#: entry then reads plainly "Close Helmet" where it used to read "Close
#: Helmet (Inherited)".
#:
#: It stays a named constant rather than being deleted because two things
#: still depend on it existing. The entry is still distinguishable from the
#: pickable one for the same id - every ordinary entry is rendered
#: "NNN - Name" and this one is bare, since `DropdownFieldRow` shows a
#: negative or zero id by name alone - and the field's own caption still
#: says which value means inherit. Putting " (Inherited)" back is a
#: one-line change here rather than a hunt through the page.
INHERITED_SUFFIX = ""

#: Marks an id this field cannot actually reach. `ENTRY_BYTE_CAST_FIELDS`
#: has said since it was written that these columns are "cast to byte"
#: before being applied and that "the Encounters tab marks unreachable
#: choices rather than silently offering them" - nothing read the constant,
#: because a spin box has nothing to mark. A dropdown does.
UNREACHABLE_SUFFIX = "  · above 255, can't be set here"


def effective_ability_types(state) -> dict:
    """
    `{ability id: AbilityType}` as it stands now, edits included.

    Zodi's requirement is that the filter be live: "if a user changed a
    support ability to a reaction ability it would now appear in the
    Reaction drop down and no longer appear in the Support drop down."

    Three layers, weakest first: `state.ability_types`, parsed from the
    bundled `AbilityData.xml` at start-up; the loaded `ability` table,
    which is the same data as the Abilities page lists; and that page's
    unexported edits. `ability_types` alone is what Job Commands uses, and
    it is the one that cannot see a rename or a retyping.
    """
    types = dict(getattr(state, "ability_types", None) or {})
    for record in (getattr(state, "item_table_records", None) or {}).get(
            "ability", []):
        value = record.values.get("AbilityType")
        if value:
            types[record.item_id] = value
    for ability_id, fields in (
            getattr(state, "item_table_edits", None) or {}
    ).get("ability", {}).items():
        value = fields.get("AbilityType")
        if value:
            types[ability_id] = value
    return types


def effective_item_types(state) -> dict:
    """
    `{item id: the set of TypeFlags it carries}`, edits included.

    Same three-layer shape as the ability types, and live for the same
    reason: retyping an item on the Items page has to move it between the
    equipment dropdowns here.
    """
    found = {}
    for record in (getattr(state, "item_table_records", None) or {}).get(
            "item", []):
        found[record.item_id] = _flag_set(record.values.get("TypeFlags"))
    for item_id, fields in (
            getattr(state, "item_table_edits", None) or {}
    ).get("item", {}).items():
        if "TypeFlags" in fields:
            found[item_id] = _flag_set(fields["TypeFlags"])
    return found


def _flag_set(raw) -> set:
    """`"Rare, Weapon"` -> `{"Rare", "Weapon"}`."""
    if not raw:
        return set()
    return {part.strip() for part in str(raw).replace("|", ",").split(",")
            if part.strip()}


def _named(state, key: str, language: str) -> dict:
    """Live names for a registered `.nxd` table, or {} if it isn't loaded."""
    try:
        return nxd_data.effective_names(state, key, language)
    except Exception:                                         # noqa: BLE001
        # A table the loaded database does not have is normal - a mod's own
        # database holds only what that mod edits - and an empty dropdown
        # is a better answer than a page that will not open.
        return {}


def _row_ids(state, key: str, language: str) -> list:
    """
    Every row id in a loaded `.nxd` table, named or not.

    Derived from the table rather than from a row count written down here.
    Hardcoding counts has been corrected three times in this project, and
    `CharaName` is exactly the shape that invites it: 1,024 rows today, of
    which 180 have no name - and a row without a name is still a row a mod
    can point at.
    """
    try:
        records = (state.nxd_records_for(key) or {}).get(language) or []
    except Exception:                                         # noqa: BLE001
        return []
    return [record.key for record in records]


def base_choices_for(state, field_name: str, language: str = "en") -> dict:
    """
    `{id: name}` for one of the eighteen dropdown fields, before sentinels.

    Names are live throughout: every one of these reads the same table the
    page that edits it reads, so a rename shows here without being copied.
    """
    if field_name == "Unknown4":
        # Every row, not only the named ones. 180 of CharaName's 1,024 rows
        # have no name, and leaving them out would put ids a mod can
        # legitimately use out of reach - this field is not byte-cast and
        # real data reaches 764.
        names = _named(state, "chara_name", language)
        return {row_id: names.get(row_id) or "(unnamed)"
                for row_id in _row_ids(state, "chara_name", language)}
    if field_name == "MainJob":
        # `job_records` for the ids, the live table for the names - exactly
        # how the Jobs page labels its own list, so the two agree.
        names = _named(state, "job", language)
        found = {}
        for record in (getattr(state, "job_records", None) or []):
            found[record.job_id] = (names.get(record.job_id)
                                    or record.name or "(unnamed)")
        for job_id, name in names.items():
            found.setdefault(job_id, name)
        return found
    if field_name in ("EntryUnknown1D", "SecondarySkillset"):
        names = _named(state, "job_command", language)
        found = {}
        for record in (getattr(state, "job_command_records", None) or []):
            found[record.command_id] = (names.get(record.command_id)
                                        or record.name or "(unnamed)")
        for command_id, name in names.items():
            found.setdefault(command_id, name)
        return found
    if field_name in ABILITY_FIELD_TYPES:
        wanted = ABILITY_FIELD_TYPES[field_name]
        types = effective_ability_types(state)
        names = _named(state, "ability", language)
        return {ability_id: names.get(ability_id) or "(unnamed)"
                for ability_id, kind in types.items() if kind == wanted}
    if field_name in EQUIPMENT_FIELD_TYPES:
        wanted = set(EQUIPMENT_FIELD_TYPES[field_name])
        types = effective_item_types(state)
        names = _named(state, "item", language)
        xml_names = {
            r.item_id: (r.name or "")
            for r in (getattr(state, "item_table_records", None) or {}).get(
                "item", [])}
        return {item_id: (names.get(item_id) or xml_names.get(item_id)
                          or "(unnamed)")
                for item_id, flags in types.items() if flags & wanted}

    # -- the six that hold a value rather than a row id -------------------
    #
    # The line above this one is where the twelve end. These six take the
    # same path from here on - `_offered` adds their specials and their
    # Inherit entry, `_refresh_inherited_labels` retitles it - and the only
    # difference is that their lists are the game's own value spaces
    # instead of another table's rows.
    if field_name == "JobUnlock":
        # 1-19 are jobs 0x4B-0x5D, read from the job table so a renamed job
        # follows through, which is what FFTPatcher does too. 0 ("Base") is
        # a special and 20 is Inherit, so neither is built here.
        names = _named(state, "job", language)
        by_job = {}
        for record in (getattr(state, "job_records", None) or []):
            by_job[record.job_id] = (names.get(record.job_id)
                                     or record.name or "")
        for job_id, name in names.items():
            by_job.setdefault(job_id, name)
        found = {}
        for offset in range(c.ENTRY_JOB_UNLOCK_JOBS):
            job_id = c.ENTRY_JOB_UNLOCK_FIRST_JOB + offset
            found[offset + 1] = by_job.get(job_id) or f"Job {job_id}"
        return found
    if field_name == "Spriteset":
        # Every id the game has a sprite row for, named where the shipped
        # list knows one. The unnamed 61 are offered as bare numbers rather
        # than dropped: a mod pointing at sprite 100 is still pointing at
        # it, and hiding the id would make that row uneditable.
        names = reference_names.sprite_set_names()
        return {sprite: names.get(sprite) or "(unnamed)"
                for sprite in range(c.ENTRY_SPRITESET_COUNT)}
    if field_name == "Level":
        return c.entry_level_choices()
    if field_name == "JobLevel":
        # 1-8, not 0-8 - see ENTRY_JOB_LEVEL_MAX for why 0 is absent.
        return {value: str(value)
                for value in range(1, c.ENTRY_JOB_LEVEL_MAX + 1)}
    if field_name in ("Bravery", "Faith"):
        return {value: str(value) for value in range(c.ENTRY_TRAIT_MAX + 1)}
    if field_name == "InitialDirection":
        return dict(entd.FACING_NAMES)
    return {}


def inherited_entry_label(field_name: str, inherited_value,
                          names: dict) -> str:
    """
    What the Inherit entry reads: `Lifefont (Inherited)`.

    Zodi's call, and the whole of the "what is Inherit inheriting?"
    feature: "Ideally in the drop down it would say what it is and then
    inherited in parenthesis so for instance for movement it could be
    Lifefont (Inherited) or if the user changed the name of Lifefont it
    would display the users changed name."

    It resolves through `names` - the same live list every other entry in
    the dropdown comes from - so renaming that ability on the Abilities
    page renames it here too, and nothing needs a fixed table.

    Three things it must not do:

    * **Number a sentinel.** An inherited 254 reads `Random (Inherited)`,
      not `254 (Inherited)`. The words come from `ENTRY_SPECIAL_VALUES`,
      so the Inherit entry and the ordinary entry for that same value say
      the same thing.
    * **Show an empty parenthesis.** An id with no name behind it - and
      JobCommandData has plenty - falls back to the number.
    * **Fail.** With no ENTD files unpacked there is nothing to name and
      this reads plain `Inherit`. The page has to stay usable without
      `fftpack`; this is an addition to it, not a new way for it to break.
    """
    if inherited_value is None:
        return INHERIT_LABEL
    # Job Level inheriting 0 reads `000 - 0`, at Zodi's request: "for the
    # sake of consistency with the rest of the page ... It sticks out." A
    # bare `0` beside eight entries reading `00N - N` looked like a
    # malformed one.
    #
    # Numbered for 0 ONLY, and that is what makes it safe. The list offers
    # 1-8 and never 0 (see ENTRY_JOB_LEVEL_MAX), so `000 - 0` cannot be
    # mistaken for a pickable entry - the confusion the unnumbered Inherit
    # label exists to prevent. 0 was also the only value that showed this
    # label at all: a slot inheriting 1-8 opens on the real `00N - N` entry
    # for it. Its Inherit entry stays a bare `3`, because numbered it would
    # put `003 - 3` in one list twice, one writing 3 and one writing -1.
    #
    # Still the Inherit entry: it writes -1, and the unit keeps its own 0.
    if field_name == "JobLevel" and inherited_value == 0:
        return f"{inherited_value:03d} - {inherited_value}{INHERITED_SUFFIX}"
    specials = c.entry_special_values(field_name)
    if inherited_value in specials:
        return specials[inherited_value] + INHERITED_SUFFIX
    name = names.get(inherited_value)
    if name and name != "(unnamed)":
        return f"{name}{INHERITED_SUFFIX}"
    return f"{inherited_value}{INHERITED_SUFFIX}"


class TradeRowDialog(QDialog):
    """
    "which row would you like to trade out?"

    A plain searchable list of the rows that exist, because the answer is
    a judgement the tool cannot make: which battle the author does not care
    about is the whole content of the decision, and a tool that picked one
    would be picking somebody's favourite fight.

    Three things it does say, because they change the answer:

    * **What each row is**, by the same label the tree uses - the battle's
      name and the unit standing in that slot. "83 Balias Tor South 5 /
      Generic Monster - Random" is a row an author can decide about;
      "83/2" is not.
    * **Which rows are already spent**, marked and unselectable. A row
      traded away once cannot be traded again, and finding that out after
      choosing would be worse than not being offered it.
    * **Which rows have edits**, marked, because trading one carries those
      edits to the new address rather than discarding them. That is the
      existing rekey behaviour and it surprises people.

    Modal and returns the chosen origin address, or None. Nothing is
    written here - the caller does the rekey, so the dialog has no access
    to the store and cannot half-apply anything.
    """

    #: On a row whose edits would travel with it.
    EDITED_SUFFIX = "   (has your edits)"
    #: On a row already traded away.
    SPENT_SUFFIX = "   (already traded)"

    def __init__(self, page, target, parent=None):
        super().__init__(parent or page)
        self.setWindowTitle("Trade a row")
        self.setModal(True)
        self._chosen = None

        column = QVBoxLayout(self)
        heading = QLabel(
            f"Give <b>{target[0]}/{target[1]}</b> one of the "
            f"{len(page.records())} rows that exist.<br>"
            f"The row you pick stops affecting its own battle and starts "
            f"affecting this one. Any edits you have made to it travel "
            f"with it.")
        heading.setWordWrap(True)
        column.addWidget(heading)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search battles\u2026")
        self.search.textChanged.connect(self._filter)
        column.addWidget(self.search)

        self.list = QListWidget()
        spent = set(page.state.entry_rekeys)
        for record in page.records():
            address = page.address_of(record)
            label = (f"{address[0]}/{address[1]}   "
                     f"{page._name_for(record)}   \u00b7   "
                     f"{page.slot_label(address, record)}")
            if address in spent:
                label += self.SPENT_SUFFIX
            elif page.state.entry_edits.get(address):
                label += self.EDITED_SUFFIX
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, address)
            if address in spent:
                # Unselectable rather than absent: a row that has already
                # been traded is still a fact about this mod, and leaving
                # it out would make the list disagree with the count in the
                # heading.
                item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
                item.setForeground(GREYED)
            self.list.addItem(item)
        self.list.itemDoubleClicked.connect(lambda _i: self.accept())
        column.addWidget(self.list, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok
                                   | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Trade this row")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        column.addWidget(buttons)
        self.resize(560, 480)

    def _filter(self, text: str) -> None:
        needle = text.strip().lower()
        for index in range(self.list.count()):
            item = self.list.item(index)
            item.setHidden(bool(needle) and needle not in item.text().lower())

    def chosen(self):
        """The selected origin address, or None."""
        item = self.list.currentItem()
        if item is None or not (item.flags() & Qt.ItemIsEnabled):
            return None
        address = item.data(Qt.UserRole)
        return tuple(address) if address is not None else None

    @classmethod
    def pick(cls, page, target):
        """Runs the dialog. Returns the chosen address, or None."""
        dialog = cls(page, target)
        if dialog.exec() != QDialog.Accepted:
            return None
        return dialog.chosen()


class EncountersPage(RefreshesWhenVisible, QWidget):
    edits_changed = Signal()

    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state
        self.current_address = None
        self._encounter_names = None
        self.rows: dict[str, QWidget] = {}
        #: `{field name: {id: name}}` for the twelve dropdowns, before the
        #: sentinels and the per-row Inherit entry are added.
        self._base_choices: dict[str, dict] = {}
        #: The game's own unit tables, or None when `fftpack` was not
        #: unpacked. Read in `refresh_records`, which is what
        #: `app._on_setup_changed` calls after an unpack finishes.
        self._entd = None
        self._language = "en"
        #: The tree's two levels: `{Key: encounter row}` and
        #: `{(Key, Key2): unit slot row}`. Kept because a slot two levels
        #: down cannot be found by index, and every caller that used to say
        #: `setCurrentRow(n)` wanted an address rather than a position.
        self._encounter_items: dict = {}
        self._slot_items: dict = {}
        #: Addresses in the ENTD files with no `OverrideEntryData` row.
        #: Rebuilt by `refresh_records`; empty until then, and empty for
        #: good with no ENTD files unpacked.
        self._entd_only: set = set()
        #: Whether the list has never been filled in this session. What
        #: `open_at_start` is gated on.
        self._first_fill: bool = True
        #: `{where a row sits in the tree: the row's own address}`, for
        #: every row. The two differ only for a traded row, but an address
        #: missing from here is what makes a slot greyed, so it has to
        #: cover all of them.
        self._origin_at: dict = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 10, 24, 20)
        outer.setSpacing(10)

        outer.addLayout(page_intro(
            "Who turns up in each battle or event, as what job, with what "
            "equipment and so on."))

        # Every tab with field rows gets these, not just Jobs.
        self.view_toggles = ViewToggles()
        self.view_toggles.changed.connect(self._apply_view)
        # Hidden: the shell draws the one visible pair, above the tabs,
        # so it is in the same place on all ten. This instance still
        # receives the preference and still answers `state()`.
        self.view_toggles.follow_only()

        # No tab strip. `CharaName-xx` used to be a second tab in here and
        # is now its own sidebar page - see `unit_names.py` for why. What is
        # left is one table, one list, one counter, which is the shape every
        # other editing page has.
        entries_column = QVBoxLayout()
        # No top margin. The 8px was inset for the tab strip that used to
        # sit above this column; with the strip gone it was just a gap, and
        # it pushed the green counter to y=58 where every other tab has it
        # at y=50 - the "extra line between the description and the green
        # text" reported from real use.
        entries_column.setContentsMargins(0, 0, 0, 0)
        entries_column.setSpacing(10)
        outer.addLayout(entries_column, 1)

        self.counter = QLabel("")
        self.counter.setProperty("role", "ok")
        entries_column.addWidget(self.counter)

        split = QHBoxLayout()
        split.setSpacing(14)

        left = QVBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search by encounter or address")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter_list)
        left.addWidget(self.search)
        # One row per ENCOUNTER, with its unit slots underneath.
        #
        # 516 rows in one flat list meant scrolling past every slot of every
        # battle to reach the next battle, and the encounter name was
        # repeated on each of them - "272 Ch2 Start Orbonne Monastery" twice
        # in a row, differing only in the slot number. There are 95 distinct
        # encounters behind those 516 rows, so collapsed this is a list a
        # fifth of the length whose every line says something different.
        #
        # A slot is still what gets EDITED; the encounter row is a container
        # and selecting it selects nothing. `_on_selection` ignores anything
        # with no address on it, which is how that is enforced rather than
        # by disabling the row - a disabled row cannot be clicked to expand.
        self.list = QTreeWidget()
        self.list.setHeaderHidden(True)
        self.list.setUniformRowHeights(True)
        # 340, matching the Items/Treasure Hunter pages' `LIST_WIDTH`.
        #
        # Reported from real use, and imported rather than repeated so the
        # two cannot drift - this page had 300 and the encounter names are
        # the longest row text in the tool ("384 Chapter 1 - The Siedge
        # Weald" was clipping), and the slots are indented under them now,
        # which costs another level of width.
        self.list.setFixedWidth(LIST_WIDTH)
        self.list.setIndentation(14)
        #: Lines the separator dots up down the list. Kept as an attribute
        #: because the width it aligns on is measured from the rows, and
        #: only the page knows when those have changed.
        self.slot_delegate = SlotColumnDelegate(self.list)
        self.list.setItemDelegate(self.slot_delegate)
        self.list.currentItemChanged.connect(self._on_selection)
        left.addWidget(self.list, 1)
        split.addLayout(left)

        right = QVBoxLayout()
        self.editing_label = QLabel(self.NOTHING_SELECTED)
        self.editing_label.setStyleSheet("font-weight: 600; font-size: 12pt;")
        right.addWidget(self.editing_label)

        self.empty_note = QLabel(
            # Reworded: there is no Convert button any more - unpacking
            # converts, and so does adopting a folder with no database.
            "No game data yet.\n\nGo to General Setup and unpack your game, "
            "or point at a folder you've already unpacked.")
        self.empty_note.setProperty("role", "muted")
        self.empty_note.setWordWrap(True)
        # Top-left, where the content it is standing in for would start.
        #
        # This was `AlignCenter` with a stretch, which put the message in the
        # dead centre of the window - a long way from the sidebar item that
        # was just clicked, and below the "Move this row to:" controls that
        # were still on screen. Textures and Sounds have always used
        # `AlignTop` and read correctly; the four master-detail pages had
        # each been given `AlignCenter` instead. This makes all six agree.
        self.empty_note.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        right.addWidget(self.empty_note)

        # Trading a row for a slot the override table does not cover.
        #
        # This replaces "Move this row to: [key] / [key2] [Move] [Undo
        # move]", which was the same operation wearing a worse interface.
        # Two spin boxes asked for an address in a table the user could not
        # see, so using it at all meant knowing which `(Key, Key2)` you
        # wanted before you started - and the addresses worth wanting are
        # exactly the ones that were not in the list.
        #
        # Reported: "lets get rid of the 'Move this row to' functionality
        # with the move and undo move buttons, instead ... a user can click
        # on a greyed out key 2 from the list, then to the right where it
        # says 'Editing:' ... there will be a button you can click to trade
        # an editable row for this uneditable row."
        #
        # So the destination is chosen by clicking it, and the thing given
        # up is chosen from a list of the 516 rows that exist. Underneath it
        # is the same `state.entry_rekeys` the Move button wrote: edits stay
        # keyed by the row's ORIGIN, so a row traded twice - or traded and
        # traded back - keeps one identity and one set of edits, and
        # `nxd_data.translate_entry_edits` reconciles the two views at
        # write time.
        #
        # All of it in one container, so the whole block goes away together
        # when there is nothing loaded. These used to be bare layouts added
        # straight to the column; a layout has no `setVisible` and nothing
        # owned them, so with no game data the page showed "No game data
        # yet" and a stranded row of controls offering to move a row that
        # did not exist.
        self.move_controls = QWidget()
        move_column = QVBoxLayout(self.move_controls)
        move_column.setContentsMargins(0, 0, 0, 0)
        move_column.setSpacing(4)

        move_row = QHBoxLayout()
        self.trade_button = QPushButton("Trade a row for this slot\u2026")
        self.trade_button.setToolTip(
            "The game ignores rows added to OverrideEntryData, so the "
            "count has to stay at 516. Reaching a new slot means giving up "
            "an existing row - this picks which one.")
        self.trade_button.clicked.connect(self.trade_for_current)
        move_row.addWidget(self.trade_button)

        self.undo_move_button = QPushButton("Undo trade")
        self.undo_move_button.setEnabled(False)
        self.undo_move_button.clicked.connect(self.undo_move)
        move_row.addWidget(self.undo_move_button)
        move_row.addStretch(1)
        move_column.addLayout(move_row)

        # No trailing stretch. With one, the layout gave the leftover width
        # to the spacer and then squeezed the buttons below the width they
        # need - caught by the page-wide clipping check, which is the first
        # time that check found something before a screenshot did.

        self.move_note = QLabel("")
        self.move_note.setProperty("role", "muted")
        self.move_note.setWordWrap(True)
        move_column.addWidget(self.move_note)
        right.addWidget(self.move_controls)

        # No "deleting rows is still only in the old interface" note.
        #
        # It is not in the old interface either - it was taken out, because
        # the game ignores added `OverrideEntryData` rows and the count has
        # to stay at 516. Moving a row is the primitive; `entry_dropped` is
        # for recovery, not a delete button. The note pointed at a feature
        # that does not exist anywhere and never should.

        scroll = FormScrollArea()
        holder = QWidget()
        form = QVBoxLayout(holder)
        form.setContentsMargins(4, 4, 4, 4)
        form.setSpacing(2)

        # Sections come from the engine's own grouping, in its own order, so
        # a field moved between sections there moves here without this page
        # being touched.
        self.sections = []
        for index, (section_name, field_names) in enumerate(
                c.ENTRY_FIELD_SECTIONS.items()):
            body = QWidget()
            column = QVBoxLayout(body)
            column.setContentsMargins(0, 0, 0, 0)
            column.setSpacing(2)
            for field_name in field_names:
                row = self._build_row(field_name)
                if row is None:
                    continue
                row.edited.connect(self._on_field_edited)
                self.rows[field_name] = row
                column.addWidget(row)
            section = CollapsibleSection(
                section_name, body,
                expanded=section_name in SECTIONS_OPEN_BY_DEFAULT)
            self.sections.append(section)
            form.addWidget(section)

        form.addStretch(1)
        scroll.setWidget(holder)
        self.scroll = scroll
        right.addWidget(scroll, 1)

        # What holds the column together when the form is hidden.
        #
        # Reported with a screenshot: selecting a unit with no override row
        # left the header, the buttons and the note spread down the whole
        # pane with big gaps between them. The form is the only widget in
        # this column with a stretch factor, so hiding it left NOTHING
        # expanding - and a QVBoxLayout with no stretch shares the leftover
        # height out among its items instead of packing them to the top.
        #
        # A spacer that appears exactly when the form disappears. Shaped
        # this way rather than by toggling a layout stretch because a
        # QVBoxLayout's stretch items cannot be shown and hidden; a widget
        # can.
        self._form_spacer = QWidget()
        self._form_spacer.setSizePolicy(QSizePolicy.Preferred,
                                        QSizePolicy.Expanding)
        self._form_spacer.setVisible(False)
        right.addWidget(self._form_spacer, 1)
        split.addLayout(right, 1)
        entries_column.addLayout(split, 1)

        self._apply_view(*self.view_toggles.state())
        self.refresh_records()

    # -- Unit Names (CharaName-xx) ----------------------------------------

    def _build_row(self, field_name: str):
        label = field_label(field_name)
        note = inherit_note(field_name)
        unknown = c.ENTRY_FIELD_CONFIDENCE.get(field_name) == "unknown"

        if field_name in c.ENTRY_ARRAY_FIELDS:
            # An array of bytes. Shown as text so it round-trips exactly,
            # rather than as a number it is not.
            return TextFieldRow(field_name, label)
        if field_name in c.ENTRY_BOOL_FIELDS:
            return BoolFieldRow(field_name, label, note)
        if c.ENTRY_COLUMN_TYPES.get(field_name) == "string":
            return TextFieldRow(field_name, label)
        if field_name in DROPDOWN_FIELDS:
            # The twelve fields that hold an id pointing at another table,
            # and the six that hold a value with a fixed meaning.
            # They were spin boxes, which meant knowing that Movement 493
            # is Lifefont and Head 155 a Genji Helm before the field could
            # be used at all. The lists are filled by `_refresh_choices`,
            # after construction, for the reason `DropdownFieldRow` was
            # given `set_choices` in the first place: the tables they come
            # from are fetched during setup and do not exist yet.
            #
            # The six arrived later and take the same path deliberately:
            # "can we turn Spriteset (called Unit in FFTPatcher), Level,
            # Bravery, Faith, and Initial Direction into a drop down
            # matching FFTPatcher", plus Job Unlock. A number in a Level
            # box cannot say that 130 means "party level + 30", and 48 in
            # a facing box cannot say anything at all.
            #
            # The note comes across unchanged. These captions say which
            # value means Inherit for THIS field, which is the single most
            # load-bearing sentence on the page - ten of the twelve inherit
            # at -1 and two at 0.
            #
            # `zero_is_none` is the "is 0 an absence?" switch, and on this
            # page the answer is exactly "only where 0 is the inherit
            # value". Reported: "for the Primary Job Command and Secondary
            # Job Command drop downs 0 is Nothing when 0 should be
            # '000 - Nothing' for consistency with the others", and the
            # same for Reaction/Support/Movement and the five equipment
            # slots. On those ten, 0 is a REAL choice - "Nothing" and
            # "Nothing (Monster)" are values the game stores and Inherit is
            # -1, sitting in the list separately - so hiding its id made
            # the one entry a reader most needs to tell from Inherit the
            # only entry with no id on it.
            #
            # On Unit Name and Main Job 0 IS the inherit value, so its
            # entry reads "Inherit" and a `000 - ` in front of that would
            # say the opposite of what the field means.
            #
            # Read from `ENTRY_INHERIT_VALUES` rather than listed, because
            # a list of ten field names here is a list that drifts from the
            # table the rule actually comes from.
            return DropdownFieldRow(field_name, label, note=note,
                                    unknown=unknown,
                                    zero_is_none=c.entry_inherit_value(
                                        field_name) == 0)
        # The floor is the field's OWN inherit value when that is negative.
        #
        # Sixteen of these fields use -1 to mean "leave the unit's own value
        # alone" - Reaction, Support, Movement, every equipment slot - and
        # the box could not hold it, so a row the nxd says is -1 read as 0.
        # 0 is a real and very different answer: for Head or Body it is an
        # actual item id, so the page was showing an equipped item where the
        # file says "unchanged".
        #
        # Taken from `ENTRY_INHERIT_VALUES`, which is where that fact already
        # lives and which the note under the field is already built from -
        # so the control and its own caption cannot disagree.
        floor = 0
        inherit = c.ENTRY_INHERIT_VALUES.get(field_name)
        if inherit and isinstance(inherit[0], int) and inherit[0] < 0:
            floor = inherit[0]
        row = NumericFieldRow(field_name, label, floor, 65535, note,
                              unknown=unknown)
        return row

    # -- records -----------------------------------------------------------------

    def records(self) -> list:
        return self.state.entry_records or []

    @staticmethod
    def address_of(record) -> tuple:
        """
        A row's identity is the PAIR. Keyed on `key` alone, rows differing
        only in `key2` would collapse into one another.
        """
        return (record.key, record.key2)

    # -- what the twelve dropdowns offer -----------------------------------

    def reload_entd(self) -> None:
        """
        Re-reads the game's own unit tables from the unpack folder.

        Called from `refresh_records`, which is what `app._on_setup_changed`
        calls on every page after an unpack, a conversion or a mod open -
        so unpacking `fftpack` for the first time reaches this without a
        restart. That is not a general precaution: the Sounds page's voice
        index cached on the unpack folder's PATH and went stale in exactly
        this situation, because the path does not change when a second
        unpack fills the same folder with more files. Re-read rather than
        compared: all four files together are 320 KB, so there is nothing
        to be clever about, and a cache that cannot go stale beats one that
        can.
        """
        self._entd = entd.EntdTables.from_folder(
            getattr(self.state, "nxd_unpack_dir", None))

    def _refresh_choices(self) -> None:
        """
        Rebuilds every dropdown's list from the tables as they stand now.

        Run whenever this page comes back on screen as well as after setup,
        because Zodi's requirement is that the filters be live: "if a user
        changed a support ability to a reaction ability it would now appear
        in the Reaction drop down and no longer appear in the Support drop
        down." Retyping happens on the Abilities page, and coming back here
        is the first moment it could be seen.

        `set_choices` keeps the current selection and suppresses the change
        signal, so this cannot mark anything as edited - the fault it was
        given `_loading` for.
        """
        names_by_field = {}
        for field_name in DROPDOWN_FIELDS:
            row = self.rows.get(field_name)
            if row is None:
                continue
            names = base_choices_for(self.state, field_name, self._language)
            names_by_field[field_name] = names
            self._base_choices[field_name] = names
            row.set_choices(self._offered(field_name, names))
        self._names_by_field = names_by_field
        # The Inherit entry is per-row, so whatever is selected needs its
        # label recomputed against the row now loaded. The nine numeric
        # fields carry the same per-row fact in their notes.
        # Unconditionally, including with nothing selected.
        #
        # This used to be guarded on `current_address`, which was harmless
        # while the page always opened on a row. It stopped being harmless
        # when it started opening on nothing: `set_choices` renders the
        # Inherit entry like any other id, so JobUnlock's sat there reading
        # "020 - Inherit" and Initial Direction's "255 - Inherit" until
        # something was clicked. Nobody could see them - the form is hidden
        # in that state - but a list that is only correct once you have
        # touched it is a list that is wrong.
        #
        # With None they all fall back to the plain word, which is what
        # `inherited_entry_label` does with nothing to name and exactly
        # what the no-ENTD case wants.
        self._refresh_inherited_labels(self.current_address)
        self._refresh_inherited_notes(self.current_address)

    def _offered(self, field_name: str, names: dict) -> dict:
        """
        One dropdown's whole list: the table, its sentinels, and Inherit.

        Order matters and is the point. The sentinels are applied LAST, so
        they win: `ItemData` id 0 is a real named row, "Nothing Equipped",
        and it carries the Weapon flag - so without this it would arrive in
        the Right Hand list under its own name while the same id also has
        to mean "Nothing (Monster)" on an encounter row. One id cannot read
        two ways in one list, and the encounter meaning is the one somebody
        editing an encounter needs.

        Inherit is a separate entry at the field's OWN inherit value, which
        is -1 on ten of the twelve. On those ten it therefore cannot
        collide with anything: -1 is not an id. On Unit Name and Main Job
        it sits at 0, which those two tables do not use as a real choice
        either.
        """
        offered = {}
        byte_cast = field_name in c.ENTRY_BYTE_CAST_FIELDS
        for row_id, name in names.items():
            # An id above 255 on a byte-cast field cannot be reached
            # through this table at all. Marked rather than dropped: a mod
            # that already points at one is still pointing at it, and
            # hiding the row would make that invisible.
            offered[row_id] = (f"{name}{UNREACHABLE_SUFFIX}"
                               if byte_cast and row_id > 255 else name)
        offered.update(c.entry_special_values(field_name))
        inherit = c.entry_inherit_value(field_name)
        if inherit is not None:
            offered[inherit] = INHERIT_LABEL
        return offered

    def inherited_values(self, address) -> dict:
        """
        `{column: the value this row inherits}`, or {} when unknown.

        Empty without the ENTD files, for an address outside them, and for
        an address whose unit slot is empty - three different reasons for
        the same honest answer, which is that there is nothing to name.
        """
        if self._entd is None or address is None:
            return {}
        # Through the trade. A row traded for 0/0 patches the ENTD unit at
        # 0/0, so that is the unit it inherits from - resolving it here
        # means `_refresh_inherited_labels`, `_refresh_inherited_notes` and
        # `slot_label` all follow a trade without any of them knowing it
        # happened.
        where = self.display_address(address)
        return self._entd.inherited_values(where[0], where[1])

    def _refresh_inherited_notes(self, address) -> None:
        """
        Nothing, now, and kept as the place that would do it again.

        It used to put "Inherits 61." at the front of the caption beside
        the fields that had no dropdown to put it in. Both halves of that
        went: Job Level became a dropdown, and Position X and Position Y
        are set to the value they inherit like everything else, so there is
        no field left whose inherited value is not simply the value on
        screen.

        The two callers stay, because "re-read what this row inherits" is
        still the right thing to do at those two moments - and if a field
        ever appears that cannot show its own inherited value, this is
        where it says so.
        """
        return

    def _refresh_inherited_labels(self, address) -> None:
        """
        Retitles each dropdown's Inherit entry for the row now selected.

        **Per-row, which nothing else in this tool is.** Every other entry
        in a dropdown is the same whichever record is selected; this one
        changes with the record, because each row inherits from its own
        ENTD slot. Only the one entry's text is rewritten - rebuilding all
        twelve lists on every selection would mean rebuilding a 1,024-entry
        combo box to change one word.

        The id can now appear twice in the same list, and that is correct.
        A row that inherits Lifefont (493) offers both `493 - Lifefont` and
        `Lifefont (Inherited)`: picking the first writes 493, leaving the
        second writes -1. They are different answers - a mod that writes
        493 is pinned to Lifefont even if the battle's own unit changes,
        and one that inherits is not - so they are not merged.
        """
        inherited = self.inherited_values(address)
        names_by_field = getattr(self, "_names_by_field", {})
        for field_name, row in self.rows.items():
            if field_name not in DROPDOWN_FIELDS:
                continue
            inherit = c.entry_inherit_value(field_name)
            if inherit is None:
                continue
            row.set_choice_label(inherit, inherited_entry_label(
                field_name, inherited.get(field_name),
                names_by_field.get(field_name, {})))

    # -- records -------------------------------------------------------------

    def entd_only_addresses(self) -> list:
        """
        Every occupied ENTD slot the nxd has no row for, in order.

        "include in the list all the Key 1s and Key 2s not in the nxd but
        in the users entd files but grey them out and make them
        uneditable."

        There are a lot of them: the four ENTD files hold **7,829 occupied
        slots across 512 events**, and `OverrideEntryData` covers 516 of
        them under 95. So the list goes from 95 battles to 512, and from
        516 unit rows to 7,829 - which is the point. The battles a mod
        author most wants to reach are precisely the ones the override
        table does not mention, and until now the page behaved as though
        they did not exist.

        Every one of the 516 nxd rows IS an occupied ENTD slot - measured,
        none is orphaned - so the two sets nest rather than overlapping,
        and a greyed row is exactly "a real unit with no override row".

        Empty with no ENTD files unpacked, which leaves the list as it was.
        """
        if self._entd is None:
            return []
        have = {self.address_of(r) for r in self.records()}
        found = []
        for event in range(entd.MAX_EVENT_ID + 1):
            for slot in range(entd.UNITS_PER_EVENT):
                address = (event, slot)
                if address in have:
                    continue
                if self._entd.unit_at(event, slot) is not None:
                    found.append(address)
        return found

    def is_editable(self, address) -> bool:
        """Whether this address has an `OverrideEntryData` row behind it."""
        return tuple(address) not in self._entd_only

    def display_address(self, origin) -> tuple:
        """
        Where a row will actually be written: its origin, or what it was
        traded for.

        A row keeps its ORIGIN as its identity - that is what `entry_edits`
        and `entry_rekeys` are keyed by, and what lets a row be traded
        twice without its edits splitting in two. But the list has to show
        it where it ends up, for two reasons and the second is the one that
        matters:

        * the user clicked a slot and traded for it, so finding the row
          still filed under a battle they just stopped affecting reads as
          the trade not having taken;
        * **a traded row inherits from its NEW slot.** `OverrideEntryData`
          patches the ENTD unit at the address it is written to, so after a
          trade every "Inherits ..." on the page is about the new battle.
          Showing it under the old address would put the right numbers
          under the wrong name.
        """
        return tuple(self.state.entry_rekeys.get(tuple(origin), origin))

    def refresh_records(self) -> None:
        self.reload_entd()
        self._refresh_choices()
        # What was open, so a refresh does not collapse the tree under
        # somebody who had just expanded a battle. `refresh_records` runs on
        # every setup change, not only at startup.
        was_open = {key for key, item in self._encounter_items.items()
                    if item.isExpanded()}
        selected = self.current_address
        self.list.clear()
        self._encounter_items = {}
        self._slot_items = {}
        self._origin_at = {}
        records = self.records()
        # Both sets, merged and in address order, so a battle's own units
        # sit together whichever table each of them came from. The greyed
        # ones are built from the ENTD files alone - there is no record to
        # pass, and `slot_label` and `_name_for` both cope with that.
        # Each row under the address it will be WRITTEN to, which is its
        # origin unless it has been traded. A traded row's origin drops
        # back to being a greyed ENTD slot, which is what it now is.
        placed = {self.display_address(self.address_of(r)): r
                  for r in records}
        self._entd_only = {a for a in self.entd_only_addresses()
                           if a not in placed}
        vacated = {self.address_of(r) for r in records} - set(placed)
        self._entd_only |= {a for a in vacated
                            if self._entd is not None
                            and self._entd.unit_at(a[0], a[1]) is not None}
        every = sorted(set(placed) | self._entd_only)
        for address in every:
            record = placed.get(address)
            parent = self._encounter_items.get(address[0])
            if parent is None:
                # `label_for` already begins with the id - "83 Balias Tor
                # South 5" - so prefixing the key here gave "83 - 83 Balias
                # Tor South 5". The flat list wrote "83/10 - " because the
                # slot number had nowhere else to go; it has its own row
                # now, so the encounter row is just the encounter.
                parent = QTreeWidgetItem([self._name_for(record, address[0])])
                # No address on an encounter row. That is what makes it a
                # container rather than something that can be edited, and
                # `_on_selection` reads exactly this.
                parent.setData(0, Qt.UserRole, None)
                self.list.addTopLevelItem(parent)
                self._encounter_items[address[0]] = parent
            slot = QTreeWidgetItem([self.slot_label(address, record)])
            slot.setData(0, Qt.UserRole, address)
            if record is None:
                # Greyed, and still selectable.
                #
                # `setDisabled` would have been the obvious way to make a
                # row uneditable and is the wrong one: a disabled tree item
                # cannot be clicked, and clicking one of these is the whole
                # feature - it is how you say which slot you want to trade
                # a row for. So it is greyed and carries a tooltip, and
                # `load_record` is what refuses to open the form.
                slot.setForeground(0, GREYED)
            parent.addChild(slot)
            # Keyed by where the row IS in the tree, not by its identity.
            #
            # Keying by identity looked tidier and was wrong: a row traded
            # away leaves its origin behind as a greyed ENTD slot, so the
            # origin address is then BOTH a row's identity and a slot of
            # its own, and one dict cannot hold two items under one key.
            # Measured - the tree lost a row on every trade.
            #
            # `_origin_at` is the other direction, for the three places
            # that need the identity: which edits belong to this row, and
            # what to write them under.
            self._slot_items[address] = slot
            if record is not None:
                # EVERY row, not only the traded ones. `_origin_at` is what
                # says "a row sits here"; a greyed slot is exactly an
                # address that is absent from it. Filling it only for
                # traded rows left `load_record` guessing - and its guess,
                # that a tree address is its own identity, was right for
                # every row except the one case this exists for: a traded
                # row's vacated origin, where it found the row that used to
                # be there and reopened it as though nothing had moved.
                self._origin_at[address] = self.address_of(record)
        # Where the dots go, measured once over every row now that they all
        # exist. The whole list is one column, so one name anywhere in it
        # sets the width for all of them - which is what "using the longest
        # spriteset name as the baseline" asks for.
        (self.slot_delegate.dot_x,
         self.slot_delegate.tail_reserve) = self._slot_column_width(
            item.text(0) for item in self._slot_items.values())
        for key in was_open:
            item = self._encounter_items.get(key)
            if item is not None:
                item.setExpanded(True)
        has_data = bool(records)
        # The move controls go with everything else. They are the reason
        # this page needed the shared helper: they were the one block on any
        # tab that `refresh_records` did not know about, so they sat at the
        # bottom of an empty page offering to move a row that did not exist.
        set_empty_state(
            self.empty_note, has_data,
            self.scroll, self.search, self.list, self.editing_label,
            self.move_controls)
        self._mark_edited()
        self._update_counter()
        # Back to whatever was selected, if it still exists - otherwise the
        # first slot of the first encounter, which is what the flat list
        # landed on. `select_record` expands the encounter on the way.
        if self._slot_items:
            # The first EDITABLE slot, not the first slot.
            #
            # `_slot_items` now starts at the lowest ENTD address there is,
            # and the override table's own lowest key is 83 - so a fallback
            # of "the first row in the tree" opened on a greyed row with no
            # form, no fields and no inherited values. Measured: it took
            # out nineteen checks at once, all of them about things a
            # loaded row does.
            #
            # `_origin_at` is in the same address order and holds only the
            # rows, so its first key is the first thing worth opening.
            # **Nothing is ever auto-selected.** Restore what was chosen,
            # and if nothing was, leave nothing chosen.
            #
            # This was `_first_fill` deciding between `open_at_start` and a
            # fallback row, and it shipped broken: `refresh_records` runs
            # more than once while a game is being set up for the first
            # time - once when the database is adopted, again when the ENTD
            # files land - so the second pass found the flag already
            # cleared, nothing selected, and took the fallback. Zodi saw
            # exactly that: a fresh install opened on 83/10 with its battle
            # expanded, and only behaved from the next session on.
            #
            # The flag was the wrong mechanism for the important half. "No
            # selection" is a state the page now has a prompt for, so there
            # is no reason to ever invent one - and a rule with no
            # exceptions cannot be got wrong by a second call.
            #
            # `_first_fill` survives for the SCROLL alone, which really is
            # once-only: re-parking the view mid-session would yank it away
            # from wherever the user had scrolled to.
            if selected and self.select_record(selected):
                pass
            else:
                self.open_at_start(scroll=self._first_fill)
            self._first_fill = False

    def open_at_start(self, scroll: bool = True) -> None:
        """
        How the list looks before anybody has clicked anything.

        "on first open of the session open so that the list is scrolled
        down so that 384 Chapter 1 - The Siedge Weald appears at the top
        with no encounter expanded and no unit selected."

        Before this the page opened on whatever row happened to sort first
        and expanded its battle - a generic monster in Balias Tor - which
        is a form full of an answer to a question nobody asked. Three
        separate things, and the third is the one that needs a constant:
        nothing selected, nothing expanded, and the view parked on
        `FIRST_STORY_ENCOUNTER`.

        Falls back to the top of the list when that encounter is not there,
        which is what a database with a different row set would give.
        """
        self.list.setCurrentItem(None)
        self.current_address = None
        self.form_visible(False)
        self.move_controls.setVisible(False)
        self.editing_label.setText(self.NOTHING_SELECTED)
        self.move_note.setText("")
        if not scroll:
            return
        item = self._encounter_items.get(FIRST_STORY_ENCOUNTER)
        if item is None:
            item = (self.list.topLevelItem(0)
                    if self.list.topLevelItemCount() else None)
        if item is not None:
            self.list.scrollToItem(item, QAbstractItemView.PositionAtTop)

    def select_record(self, address) -> bool:
        """
        Selects a unit slot by its `(Key, Key2)`, expanding its encounter.

        Public because a slot two levels down cannot be reached by index
        any more, and because "go to this address" is the operation every
        caller of the old `setCurrentRow` actually wanted.
        """
        # The row FIRST, the place second.
        #
        # After a trade an address can mean two things: the row that came
        # from there, and the greyed slot it left behind. Every caller of
        # this - `refresh_records` restoring the selection, a jump from
        # another tab, a check - is holding a row and means the row. The
        # slot is still reachable by clicking it, which is the only way
        # anybody asks for it.
        item = (self._slot_items.get(self.display_address(address))
                or self._slot_items.get(tuple(address)))
        if item is None:
            return False
        # No `setExpanded` on the parent here. There was one, and it was
        # dead: `setCurrentItem` scrolls to the item, and scrolling to
        # something inside a collapsed row expands it. Measured rather than
        # assumed - removing the call left the check that a selected slot's
        # encounter ends up open still passing, which is how the line was
        # found to be doing nothing. The check stays, because the
        # requirement is real whoever satisfies it.
        #
        # **Loaded explicitly when the item is already current.**
        # `setCurrentItem` fires `currentItemChanged` only on a CHANGE, so
        # selecting the row that is already selected did nothing at all -
        # and after a refresh it usually is the one already selected.
        # Measured twice before it was fixed: the header kept naming the
        # battle a row had just been traded away from, and an undo aimed at
        # the wrong address because `current_address` was still the last
        # row loaded by hand.
        already = self.list.currentItem() is item
        self.list.setCurrentItem(item)
        if already:
            address = item.data(0, Qt.UserRole)
            if address is not None:
                self.load_record(tuple(address))
        return True

    def addresses(self) -> list:
        """
        Every `(Key, Key2)` in the tree, in list order - **both kinds**.

        7,829 of them once the ENTD files are read: the 516 with an
        override row and the 7,313 without. A caller that means "a row I
        can edit" wants `editable_addresses`; this one is "everything on
        screen", which is what the list-shape checks measure.
        """
        return list(self._slot_items)

    def editable_addresses(self) -> list:
        """
        Where the rows are, in list order - the 516 with a row behind them.

        Separate from `addresses` since the greyed slots joined the list.
        Anything that loads a record, edits a field or reads a form means
        this one; conflating the two is how a check ends up measuring an
        empty form and passing.
        """
        return list(self._origin_at)

    #: Between the two halves of a slot's label. The same separator the
    #: item lists use for the same job - two facts about one row.
    #:
    #: Module-level now, because `SlotColumnDelegate` splits on it and the
    #: delegate is not the page. One definition: a delegate splitting on a
    #: different string from the one the label was built with would simply
    #: stop aligning, silently.
    SLOT_SEPARATOR = SLOT_SEPARATOR

    #: The header before anything is chosen, and again after
    #: `open_at_start`. One string, because those are the same state.
    NOTHING_SELECTED = "Select an encounter row"

    def slot_label(self, address, record=None) -> str:
        """
        What one unit slot reads in the list: its sprite, then its level.

        "for the list instead of the expanded list saying 'Unit slot x' it
        should rather say the units Spriteset then it's Level."

        Worth the trouble because "Unit slot 7" is the slot's own index
        said twice - the row is already the seventh child of its battle -
        whereas "Generic Monster / 30" is who is actually standing there.

        **Effective values, not stored ones.** Spriteset inherits at 0 and
        Level at anything 0 or less, and the great majority of rows inherit
        both - 512 of the 516 leave Spriteset alone and 510 leave Level. A
        label built from the stored numbers would therefore read "Inherit /
        Inherit" on almost every row, which is worse than the slot number.
        So the row's own value wins where it sets one and the ENTD slot
        supplies the rest, which is the same rule the fields themselves
        follow.

        Named through `inherited_entry_label`, so a slot inheriting a
        random level reads "Random" here exactly as it does in the Level
        dropdown's Inherit entry, and a renamed sprite follows.

        Falls back to the slot number when neither half is known, which is
        what happens with no ENTD files unpacked on a row that overrides
        nothing. The page has to stay usable without `fftpack`.
        """
        inherited = self.inherited_values(address)
        # The EFFECTIVE view, pending edits included - the same three
        # layers the form itself shows, in the same order. A label built
        # from `record.values` alone would keep calling a slot a Generic
        # Monster after its Spriteset had been set to Ramza, and go on
        # doing so until the next full refresh.
        #
        # **Edits are keyed by the row's own address, not by where it is
        # drawn**, and after a trade those are two different pairs. Looking
        # them up by `address` worked for every untraded row - the two are
        # equal there - and silently stopped working the moment a row moved:
        # reported as "if you edit a unit after using the Trade a row for
        # this slot... button then the name in the list stops updating",
        # with a screenshot of a row whose Level field read 105 while the
        # list still called it Level 9.
        #
        # The record knows its own identity, so nothing has to be passed in.
        # A greyed slot has no record and no edits either, so falling back
        # to `address` there costs nothing and keeps the no-ENTD path whole.
        origin = (self.address_of(record) if record is not None
                  else tuple(address))
        values = dict(getattr(record, "values", {}) or {})
        values.update(self.state.entry_edits.get(origin, {}))
        parts = []
        for field_name in ("Spriteset", "Level"):
            value = self.effective_entry_value(
                address, field_name, values.get(field_name), inherited)
            if value is None:
                continue
            named = inherited_entry_label(
                field_name, value, self._base_choices.get(field_name, {}))
            # "Level 36", not a bare 36.
            #
            # The sprite half is a name and reads as one; the level half is
            # a number and read as one more number on a page full of them.
            # Only 1-99 get the word: 100 is already "Party level", 101-199
            # already say "Party level + N", and 254 is "Party Level -
            # Random" - all three are sentences already, and "Level Party
            # level + 5" is not an improvement on any of them.
            if field_name == "Level" and named.isdigit():
                named = f"Level {named}"
            # ...and "Sprite 55" rather than a bare 55. The shipped list
            # has no name for 61 of the 131 ids, and a bare number sitting
            # next to "Level 25" reads as a second number rather than as
            # the sprite it is.
            elif field_name == "Spriteset" and named.isdigit():
                named = f"Sprite {named}"
            parts.append(named)
        return (self.SLOT_SEPARATOR.join(parts) if parts
                else f"Unit slot {address[1]}")

    def effective_entry_value(self, address, field_name, stored,
                              inherited=None):
        """
        What a field is actually worth: its own value, or what it inherits.

        "lets do the same to the Encounters page for the following fields
        ... so they can simply be set to the value they are inheriting."

        The same move the Abilities override layer made one round earlier,
        and the same bargain: the control carries the effective value and
        the INCLUDE BOX is what decides whether it reaches the mod. Nothing
        is written by a field nobody has ticked.

        **Inheriting is not one test.** Each column has its own sentinel -
        Spriteset 0, Job Unlock 20, Initial Direction 255, ten fields at -1 -
        and `Level` and `JobLevel` are odder still: the layout gives them
        "if greater than zero", so 0 inherits on those two as surely as -1
        does. Written once here because `slot_label` and `load_record` both
        ask the question and two answers would be two answers.

        None when nothing is known - no ENTD files, or a slot outside them -
        which leaves the caller showing what the file holds, as it did
        before any of this.
        """
        if inherited is None:
            inherited = self.inherited_values(address)
        try:
            stored = (None if stored is None or stored == ""
                      else int(stored))
        except (TypeError, ValueError):
            stored = None
        # The "greater than zero" columns. `ENTRY_INHERIT_VALUES` says so in
        # its own wording - "-1 (in fact any value of 0 or less)" - and this
        # is the one place that difference has to be acted on.
        floor_inherits = field_name in c.ENTRY_POSITIVE_ONLY_FIELDS
        available = inherited.get(field_name)
        # **An inherited value this column cannot express is not offered as
        # one.** On the two positive-only columns anything at or below zero
        # patches nothing, so showing it would put a number in the field
        # that the field cannot mean - and it is not a rare corner: **6,423
        # of the 7,829 occupied slots inherit Job Level 0**. Those keep
        # their sentinel, whose Inherit entry already names what is behind
        # it.
        if available is not None and floor_inherits and available <= 0:
            available = None
        if stored is None:
            return available
        inherit = c.entry_inherit_value(field_name)
        unset = stored == inherit or (floor_inherits and stored <= 0)
        return available if unset else stored

    def _name_for(self, record, key=None) -> str:
        """
        The encounter's real name, from `data/EncounterNames.txt`.

        `key` rather than a record, for the battles that now appear in the
        list with no `OverrideEntryData` row at all - 417 of the 512. The
        record is still accepted because every existing caller has one.

        This read `state.encounter_names`, which nothing ever populates, so
        every row in a 516-row list read "Encounter 12" - the id it already
        showed, twice. There is a whole engine module for this
        (`encounter_names`, sourced from FFTPatcher) and the Tkinter page
        has always used it.

        The table is loaded once and kept: it is read from disk and does
        not change while the tool runs.
        """
        if key is None:
            key = record.key
        if self._encounter_names is None:
            try:
                self._encounter_names = encounter_names.EncounterNames.load()
            except Exception:                                 # noqa: BLE001
                self._encounter_names = False     # tried and failed; don't retry
        if not self._encounter_names:
            return f"Encounter {key}"
        label = self._encounter_names.label_for(key) or ""
        # `label_for` prefixes the id, so an unnamed encounter comes back
        # as the bare number and the row read "0/0 - 0". **69 of the 512
        # are like that**, and it only started showing when the list grew
        # to cover every battle rather than the 95 the override table
        # mentions - all 95 of those happen to be named.
        return f"Encounter {key}" if label == str(key) else (
            label or f"Encounter {key}")

    def _filter_list(self, text: str) -> None:
        """
        Search matches the ENCOUNTER, and keeps its slots with it.

        Typing "Orbonne" has to leave the battle's units reachable, so a
        matching encounter keeps all of its children; a slot matches on its
        own address too, so "272/5" still finds one unit. Matching rows are
        expanded, because a hit hidden inside a collapsed parent reads as no
        hit at all.
        """
        needle = text.strip().lower()
        for key, parent in self._encounter_items.items():
            parent_matches = not needle or needle in parent.text(0).lower()
            shown_children = 0
            for index in range(parent.childCount()):
                child = parent.child(index)
                address = child.data(0, Qt.UserRole)
                address_text = f"{address[0]}/{address[1]}"
                child_matches = (
                    parent_matches
                    or needle in child.text(0).lower()
                    or needle in address_text)
                child.setHidden(not child_matches)
                shown_children += bool(child_matches)
            parent.setHidden(not (parent_matches or shown_children))
            if needle and not parent.isHidden():
                parent.setExpanded(True)

    def _on_selection(self, current, _previous) -> None:
        # An encounter row carries no address; it is a container, and
        # clicking it expands rather than loading anything.
        if current is None:
            return
        address = current.data(0, Qt.UserRole)
        if address is not None:
            self.load_record(tuple(address))

    def load_record(self, address: tuple) -> None:
        """
        Loads whatever sits at one place in the tree.

        `address` is where the row IS, which after a trade is not where it
        came from. `_origin_at` gives back the row's own address, which is
        what `entry_edits` is keyed by and what gets written.
        """
        address = tuple(address)
        origin = self._origin_at.get(address)
        by_address = {self.address_of(r): r for r in self.records()}
        record = by_address.get(origin) if origin is not None else None
        if record is None:
            # A slot from the ENTD files that the override table does not
            # cover. Selectable, so it can be traded FOR; not editable,
            # because there is no row to edit - which is the whole of what
            # "greyed out and uneditable" means here.
            self._load_entd_only(tuple(address))
            return
        self.current_address = origin
        self.form_visible(True)
        # "if a user is on an editable unit there is no need for the 'Trade
        # a row for this slot...' button and 'Undo trade' button to appear."
        #
        # Right, with one exception the request could not have known about:
        # a row that HAS been traded is editable, and Undo trade is the only
        # way back. So the block appears for a traded row and for nothing
        # else - the trade button never does here, because this slot is not
        # one you can trade FOR.
        traded = self.current_address in self.state.entry_rekeys
        self.trade_button.setVisible(False)
        self.undo_move_button.setVisible(traded)
        self.move_controls.setVisible(traded)
        # The address it will be WRITTEN to, which is the battle these
        # values now affect. `_refresh_move_state` says where it came from.
        self.editing_label.setText(
            f"Editing: {address[0]}/{address[1]} - "
            f"{self._name_for(None, address[0])}")
        self._refresh_move_state()

        # Before the rows are filled, not after. Each row's Inherit entry
        # names what THIS row inherits, so it has to be right by the time
        # `load` selects it - otherwise a row sitting on -1 would show the
        # previous row's inherited value for as long as it was on screen.
        self._refresh_inherited_labels(self.current_address)
        self._refresh_inherited_notes(self.current_address)

        already = self.state.entry_edits.get(self.current_address, {})
        inherited = self.inherited_values(self.current_address)
        for field_name, row in self.rows.items():
            if field_name in already:
                row.load(already[field_name], True)
                continue
            stored = record.values.get(field_name, "")
            # The effective value, for the fields that have an inherit
            # sentinel. Everything else - the flags, the arrays, the
            # comment - has no such thing and loads what the file holds.
            if field_name in c.ENTRY_INHERIT_VALUES:
                effective = self.effective_entry_value(
                    self.current_address, field_name, stored, inherited)
                if effective is not None:
                    stored = effective
            row.load(stored, False)

    def _load_entd_only(self, address: tuple) -> None:
        """
        Selecting a greyed row: say what it is, and offer the trade.

        `current_address` is deliberately cleared. Everything that writes -
        `_on_field_edited`, `trade_for_current`, `undo_move` - returns
        early on None, so one assignment makes the whole page read-only for
        this row rather than each writer needing its own guard.
        """
        self.current_address = None
        self.form_visible(False)
        self.move_controls.setVisible(True)
        self.trade_button.setVisible(True)
        self.undo_move_button.setVisible(False)
        self.editing_label.setText(
            f"{address[0]}/{address[1]} - {self._name_for(None, address[0])}"
            f"  \u00b7  {self.slot_label(address)}")
        self.trade_button.setEnabled(True)
        self.undo_move_button.setEnabled(False)
        self._pending_target = address
        self.move_note.setText(ENTD_ONLY_MESSAGE)

    def form_visible(self, on: bool) -> None:
        """Shows or hides the editing form, leaving the list alone."""
        self.scroll.setVisible(on)
        self._form_spacer.setVisible(not on)

    # -- trading a row for a slot the override table does not cover -----------

    def trade_for_current(self) -> None:
        """
        Gives the selected greyed slot one of the 516 existing rows.

        "a user can click on a greyed out key 2 from the list, then ...
        there will be a button you can click to trade an editable row for
        this uneditable row. So when you click on it it will let you select
        which row you'd like to trade it out so that it becomes a row that
        you can now edit."

        Underneath it is a rekey, the same one the Move button wrote. What
        changed is which end the user names: Move asked for a destination
        address in a table they could not see, and the addresses worth
        naming were precisely the ones the list did not show. Here the
        destination is the row they clicked and the choice is which row to
        spend.
        """
        target = getattr(self, "_pending_target", None)
        if target is None or self.is_editable(target):
            return
        chosen = TradeRowDialog.pick(self, target)
        if chosen is None:
            return
        taken = {tuple(v) for v in self.state.entry_rekeys.values()}
        if target in taken:
            self.move_note.setText(
                f"{target[0]}/{target[1]} has already been traded for.")
            return
        self.state.entry_rekeys[chosen] = target
        self.refresh_records()
        # Land on the row they just freed up, which is the one they now
        # want to edit - not on the address it came from.
        self.select_record(chosen)
        self.edits_changed.emit()

    def undo_move(self) -> None:
        if self.current_address is None:
            return
        self.state.entry_rekeys.pop(self.current_address, None)
        self.refresh_records()
        self.select_record(self.current_address)
        self.edits_changed.emit()

    def _refresh_move_state(self) -> None:
        moved = self.state.entry_rekeys.get(self.current_address)
        self.undo_move_button.setEnabled(moved is not None)
        if moved:
            # Where it will be written, and nothing else. "can we remove
            # that part" - the sentence that used to follow said the edits
            # stay attached to the row, which is the behaviour anyone would
            # assume and so was reassurance about something nobody had
            # doubted.
            self.move_note.setText(
                f"Traded: this row will be written to {moved[0]}/{moved[1]} "
                f"instead of {self.current_address[0]}/"
                f"{self.current_address[1]}.")
        else:
            self.move_note.setText("")
        self._mark_edited()

    # -- editing ------------------------------------------------------------------

    def refresh_from_store(self) -> None:
        """
        Re-read the selected encounter row when this page comes back.

        One half now. It used to refresh two, because Unit Names sat behind
        a tab strip on this page where a stale half is invisible; that half
        is its own page and refreshes itself. See
        `widgets/visible_refresh.py`.

        The twelve dropdowns are rebuilt here too, and this is the moment
        that makes their filters live. Renaming an ability, or retyping a
        Support one into a Reaction one, happens on another page; coming
        back here is the first time it could be seen. Rebuilding the lists
        does not rebuild the RECORD list or move the selection, which is
        the thing this hook must not do.
        """
        # The LISTS rebuild whether or not a row is selected.
        #
        # This whole method used to return early on no selection, which was
        # unreachable while the page always opened on a row. Now that it
        # opens on nothing, the early return meant Zodi's live-filter
        # requirement - "if a user changed a support ability to a reaction
        # ability it would now appear in the Reaction drop down" - quietly
        # stopped working until something had been clicked.
        self._refresh_choices()
        self._mark_edited()
        self._update_counter()
        if self.current_address is None:
            return
        self.load_record(self.current_address)

    def _on_field_edited(self) -> None:
        if self.current_address is None:
            return
        edits = self.state.entry_edits.setdefault(self.current_address, {})
        for field_name, row in self.rows.items():
            if row.included:
                edits[field_name] = row.get_value_str()
            elif field_name in edits:
                del edits[field_name]
        if not edits:
            self.state.entry_edits.pop(self.current_address, None)

        # The slot's label is its sprite and its level, so changing either
        # has to change the label. Without this, setting a row's Spriteset
        # to Ramza left the list still calling it a Generic Monster until
        # the next full refresh - the list would be reporting the file
        # rather than what the user has in front of them, which is the
        # fault `ability_display_name` was carrying one page over.
        self._relabel_slot(self.current_address)
        self._mark_edited()
        self._update_counter()
        self.edits_changed.emit()

    def _relabel_slot(self, address) -> None:
        """Re-reads one slot's label. Cheap enough to do on every keystroke."""
        where = self.display_address(address)
        item = self._slot_items.get(where)
        if item is None:
            return
        record = {self.address_of(r): r for r in self.records()}.get(
            tuple(address))
        label = self.slot_label(where, record)
        item.setText(0, label)
        # One row changed, so the dot column can only need WIDENING - and
        # only by this row. Re-measuring all 7,829 on every keystroke to
        # find that out would be the expensive way to learn it.
        #
        # It is deliberately one-way. Editing a row back to a shorter name
        # leaves the column where the longer one put it until the next full
        # refresh, which costs a little space and never overlaps anything;
        # shrinking on every edit would make the whole list shift sideways
        # while somebody is typing.
        self._widen_slot_column(label)

    def _slot_column_width(self, labels) -> tuple:
        """
        `(where the dot wants to go, what the level needs)`, in pixels.

        Both measured in the list's own font rather than counted in
        characters, which is the whole reason this is not `str.ljust`. The
        delegate holds the two apart: the first is the ideal and the second
        is what it must not eat into.
        """
        metrics = QFontMetrics(self.list.font())
        sprite = tail = 0
        for label in labels:
            if SLOT_SEPARATOR not in label:
                continue
            left, right = label.split(SLOT_SEPARATOR, 1)
            sprite = max(sprite, metrics.horizontalAdvance(left))
            tail = max(tail, metrics.horizontalAdvance(f"·  {right}"))
        return (sprite + SLOT_COLUMN_GAP if sprite else 0), tail

    def _widen_slot_column(self, label: str) -> None:
        """Moves the dot right if this one label needs more room."""
        want, tail = self._slot_column_width([label])
        changed = False
        if want > self.slot_delegate.dot_x:
            self.slot_delegate.dot_x = want
            changed = True
        # The level half too: setting a Level to "Party level + 5" makes
        # the tail wider, and a reserve that only ever grew from the sprite
        # side would let the new text be elided on the row that produced it.
        if tail > self.slot_delegate.tail_reserve:
            self.slot_delegate.tail_reserve = tail
            changed = True
        if changed:
            self.list.viewport().update()

    def _mark_edited(self) -> None:
        """
        Marks the edited slots, and the encounters holding them.

        The encounter row is marked when ANY of its slots is, which is not
        decoration: README has promised since this page was built that
        "editing any unit in an encounter highlights the encounter itself
        as well, so changes are visible with the list collapsed", and with
        a tree the list is collapsed most of the time.
        """
        edited_keys = set()
        for address, item in self._slot_items.items():
            # `address` is where the row sits; its edits are filed under
            # where it came from, which for an untraded row is the same
            # thing.
            origin = self._origin_at.get(address, address)
            # `.get(..., address)` is right here and not a guess: a greyed
            # slot has no row, so it has no edits under either reading.
            edited = (bool(self.state.entry_edits.get(origin))
                      or origin in self.state.entry_rekeys)
            mark_edited(item, edited)
            # ...and put the grey back.
            #
            # `mark_edited` owns the foreground: an unedited row gets an
            # INVALID brush, so that the palette decides and no page
            # hard-codes white into a dark theme. That is right, and it
            # wiped the grey a few lines after `refresh_records` set it -
            # every ENTD-only row drew in the ordinary colour. Measured,
            # not noticed: the check for it read #000000.
            #
            # Two mechanisms own one property, so the later one has to know
            # about the earlier. This is the later one.
            if address in self._entd_only:
                item.setForeground(0, GREYED)
            if edited:
                edited_keys.add(address[0])
        for key, item in self._encounter_items.items():
            mark_edited(item, key in edited_keys)

    def _update_counter(self) -> None:
        # Counted in ROWS OF `OverrideEntryData`, which is what the number
        # has always meant - 516, not the 7,829 units now on screen.
        #
        # It read 7,829 for one round, because the tree grew to cover every
        # unit in the ENTD files and this counted `_slot_items`. "0 of 7,829
        # encounters have pending edits" is a true statement about the list
        # and a false one about the table: 7,313 of those have no row to
        # edit, so they can never join the numerator. A denominator you
        # cannot reach is not a denominator.
        total = len(self._origin_at)
        if not total:
            self.counter.setText("")
            return
        edited = sum(1 for fields in self.state.entry_edits.values() if fields)
        self.counter.setText(edit_counter_text(edited, total, "encounters"))


    def _apply_view(self, hide_notes: bool, hide_unknown: bool,
                    hide_comments: bool) -> None:
        """
        One row container, now.

        This used to walk two and was once fixed for walking only one - the
        unit rows in `chara_rows` kept their notes with notes turned off,
        37 of 38 hiding, which looks exactly like it working. Those rows now
        live on `UnitNamesPage`, which walks its own. `audit_view_toggles`
        checks both pages.
        """
        apply_view_toggles(list(self.rows.values()),
                           hide_notes, hide_unknown, hide_comments)
