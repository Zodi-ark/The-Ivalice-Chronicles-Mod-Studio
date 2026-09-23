"""
ENTD - the game's own unit tables, which is what an Encounters row inherits.

`OverrideEntryData` patches units that already exist. Every field in it that
means "leave this alone" is pointing at a value it will not name, and
knowing what that value actually is was asked for as "one of the greatest QoL
features of Mod Studio". This module is the half that reads it.

**Read-only, and deliberately so.** Writing ENTD is a much larger feature -
the file is replaced whole, which collides with any other mod that does the
same - and it was not asked for. Nothing here writes.

### Where the format comes from

The layout below is FFTPatcher's, by Glain (https://github.com/Glain/
FFTPatcher), GPL-3, transcribed from `Datatypes/ENTD/ENTD.cs` and
`Datatypes/ENTD/EventUnit.cs`. Mod Studio is GPL-3 too, so it may be adapted
as long as that origin is stated - which is also how the next person finds
the authority for it rather than having to re-derive it.

### Why FFTPatcher's reader is correct for The Ivalice Chronicles' files

Because they are the same files. Measured, September 2026: IC's four
`battle_entd*_ent.bin` under `fftpack/` are BYTE-FOR-BYTE IDENTICAL to the
PlayStation `ENTD1-4.ENT` that FFTPatcher ships in
`PatcherLib.Resources/Resources/`:

    e148fa8659be525e6700484e694f9aba  battle_entd1_ent.bin  (IC's fftpack)
    e148fa8659be525e6700484e694f9aba  ENTD1.ENT             (FFTPatcher's)

So there was nothing to reverse-engineer, and `dev/test_entd.py` can check
this reader against files that ship with the FFTPatcher source - no copy of
the game needed to run it.

### The shape

Each file holds 128 events, each event 16 unit slots, each slot 40 bytes:
128 x 16 x 40 = 81,920, which is the exact size of all four files. Four
files cover event ids 0x000-0x1FF, file *n* starting at (n-1) * 0x80.

**There is no fifth file.** The PSP release has an ENTD5 with 80 more
battles (FFTPatcher ships it as `PSP/bin/ENTD5.bin`, and reads it at event
id 0x200 upward); Zodi confirms it was cut from The Ivalice Chronicles, and
the database agrees - `EntryNo` holds exactly 512 rows and
`OverrideEntryData.Key` tops out at 500, both inside 0x1FF. So an event id
above 511 means something is wrong rather than that a file is missing.

### The mapping into Mod Studio

Measured against the real database and the real files, on all 516 rows of
`OverrideEntryData`:

    Key   -> the ENTD event id  (0x000-0x1FF; 95 distinct values, 83-500)
    Key2  -> the unit slot      (0-15, all sixteen used)

    file   = battle_entd{Key // 128 + 1}_ent.bin
    offset = (Key % 128) * 640 + Key2 * 40

Proof rather than plausibility: of those 516 rows, **516 land on a slot that
actually holds a unit and 0 land on an empty one.** With 7,829 of the 8,192
slots occupied, pointing at random would miss about 23 times. It missed
zero.

That the column names agree is a second, independent check:
`overrideentrydata.nxd` calls the primary job command `EntryUnknown1D`, and
0x1D is 29, which is the byte SkillSet sits at. The column names in that
table are ENTD byte offsets.

One measured NON-match, kept here so nobody assumes the pattern holds
everywhere: `JobUnlock` does not equal ENTD byte 8 (`PrerequisiteJob`) in
any of the 516 rows. Any other column claimed to inherit from its
same-named byte has to be checked the same way first.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

#: One unit slot, sixteen slots to an event, 128 events to a file.
UNIT_BYTES = 40
UNITS_PER_EVENT = 16
EVENT_BYTES = UNIT_BYTES * UNITS_PER_EVENT          # 640
EVENTS_PER_FILE = 0x80                              # 128
FILE_BYTES = EVENT_BYTES * EVENTS_PER_FILE          # 81,920
ENTD_FILE_COUNT = 4
#: Event ids 0x000-0x1FF. A Key outside this is not an ENTD event.
MAX_EVENT_ID = EVENTS_PER_FILE * ENTD_FILE_COUNT - 1

#: The four files, as `fftpack/` names them.
#:
#: The prefix is separate because `game_install` passes it to FF16Tools as a
#: --filter, which is a plain substring test: `fftpack/battle_entd` matches
#: exactly these four files and nothing else in the game. Defined here, where
#: the naming belongs, rather than spelled out again over there.
ENTD_FILENAME_PREFIX = "battle_entd"
ENTD_FILENAMES = tuple(
    f"{ENTD_FILENAME_PREFIX}{n}_ent.bin"
    for n in range(1, ENTD_FILE_COUNT + 1))

#: Where they live inside an unpacked game folder.
ENTD_FOLDER = "fftpack"

#: 0xFE is "Random" on far more fields than the equipment ones. A layout
#: probe over all 8,192 slots flagged Bravery, Faith, Month, Day and Facing
#: as out of range; every one traced to this. Counts of 254 across the
#: occupied slots: Level 5,736, Bravery 6,856, Faith 6,843, Month 6,604,
#: Day 6,613. Excluding it, Bravery tops out at 95, Faith at 100 and Day at
#: 31 - all sane. Anything DISPLAYING an inherited value has to render 254
#: as "Random" on those fields rather than as the number.
RANDOM_BYTE = 0xFE
#: The three ability fields are 16-bit, so their form of the same sentinel
#: is 0x01FE. This is why ENTRY_SPECIAL_VALUES gives Reaction, Support and
#: Movement 510 where the byte fields get 254.
RANDOM_USHORT = 0x01FE                              # 510

#: Byte offset of every single-byte field in a 40-byte slot.
BYTE_FIELDS = {
    "sprite_set": 0, "flags1": 1, "unit_name": 2, "level": 3, "month": 4,
    "day": 5, "bravery": 6, "faith": 7, "prereq_job": 8,
    "prereq_job_level": 9, "main_job": 10, "secondary_command": 11,
    "head": 18, "body": 19, "accessory": 20, "right_hand": 21,
    "left_hand": 22, "palette": 23, "flags2": 24, "x": 25, "y": 26,
    "facing_raw": 27, "experience": 28, "primary_command": 29,
    "war_trophy": 30, "bonus_money": 31, "unit_id": 32, "target_x": 33,
    "target_y": 34, "ai_flags": 35, "target": 36, "unknown10": 37,
    "flags3": 38, "unknown12": 39,
}

#: The three 16-bit little-endian fields, by offset of their low byte.
USHORT_FIELDS = {"reaction": 12, "support": 14, "movement": 16}

#: `OverrideEntryData` column -> the ENTD field it inherits from.
#:
#: Exactly the twelve columns `constants.ENTRY_FIELD_LABELS` names, which is
#: asserted in `dev/test_entd.py` against the constant rather than restated
#: here. `JobUnlock` is deliberately absent: it was measured and does NOT
#: track ENTD byte 8.
ENCOUNTER_FIELD_SOURCES = {
    "Unknown4": "unit_name",
    "MainJob": "main_job",
    "EntryUnknown1D": "primary_command",
    "SecondarySkillset": "secondary_command",
    "Reaction": "reaction",
    "Support": "support",
    "Movement": "movement",
    "Head": "head",
    "Body": "body",
    "Accessory": "accessory",
    "RightHand": "right_hand",
    "LeftHand": "left_hand",
}

#: The columns that hold a plain NUMBER rather than an id into a table.
#:
#: Asked for after the twelve above shipped: "can we also show what the
#: inherited Job Unlock, Job Level, Spriteset, Level, Bravery, Faith,
#: Position X, Position Y, and Initial Direction are." They have no
#: dropdown to put the answer in, so the page puts it in the field's note.
#:
#: **Measured the same way the twelve were, and not by name.** The test
#: that matters is whether the override column and the ENTD byte live in
#: the same value space - across the real table and all 7,829 occupied
#: slots:
#:
#:     Spriteset        set 2-48          sprite_set        0-130
#:     Level            set 3-254         level             0-130 (+254)
#:     JobUnlock        set 0-19          prereq_job        0-19
#:     JobLevel         set 1-8           prereq_job_level  0-8
#:     Bravery          never set         bravery           0-95  (+254)
#:     Faith            never set         faith             0-100 (+254)
#:     PositionX        set 0-7           x                 0-15
#:     PositionY        set 1-6           y                 0-17
#:     InitialDirection set 0,3           facing            0-3 (+48, 51)
#:
#: **JobUnlock is the one to read twice.** An earlier note in this project
#: said it "does NOT equal ENTD byte 8 in any of the 516 rows" and warned
#: against assuming the mapping. That measurement was real and the
#: conclusion drawn from it was wrong: the same test says MainJob does not
#: equal ENTD byte 10 in any of the 516 either, and MainJob is PROVEN to be
#: byte 10. Of course they differ - an override exists to hold a value
#: different from the one being overridden, and only 13 of 516 rows set
#: JobUnlock at all.
#:
#: The test that does discriminate says the opposite: JobUnlock's set
#: values span exactly 0-19 and `prereq_job` spans exactly 0-19, and
#: JobUnlock's inherit value of 20 sits one past the end of that range,
#: which is what "none of them" looks like.
#:
#: **Where that test cannot reach, and this is said rather than glossed
#: over.** PositionX and PositionY are both small map coordinates with
#: overlapping ranges - X runs 0-15 and Y runs 0-17 across the occupied
#: slots, and every X the override sets is also a value Y takes. Swapping
#: the two here produces a table no measurement in this data can fault. The
#: evidence for that one pairing is the column names, and nothing else;
#: `dev/test_entd.py` therefore carries its own copy of the intended
#: pairing so a swap or a typo shows up as a disagreement between two
#: independent statements of it rather than passing silently.
ENCOUNTER_NUMERIC_SOURCES = {
    "Spriteset": "sprite_set",
    "Level": "level",
    "JobUnlock": "prereq_job",
    "JobLevel": "prereq_job_level",
    "Bravery": "bravery",
    "Faith": "faith",
    "PositionX": "x",
    "PositionY": "y",
    "InitialDirection": "facing",
}

#: Every column whose inherited value this module can supply.
ALL_ENCOUNTER_SOURCES = {**ENCOUNTER_FIELD_SOURCES, **ENCOUNTER_NUMERIC_SOURCES}

#: Columns where 254 means "Random" rather than the number 254. Level,
#: Bravery and Faith carry it in the real data on thousands of slots (see
#: RANDOM_BYTE above); the other numeric columns never do.
RANDOM_BYTE_COLUMNS = ("Level", "Bravery", "Faith")

#: `InitialDirection`, named. FFTPatcher's `Facing` enum
#: (`Datatypes/ENTD/EventUnit.cs`), which has exactly four real values and
#: marks 48 and 51 as unknown - and those two are the only others that
#: occur, on 18 of the 7,829 occupied slots. Anything not here is shown as
#: its number rather than given an invented name.
#:
#: **48 and 51 are in the list, under FFTPatcher's own names for them.**
#: They were left out while this only fed a caption, where an unnamed
#: number is harmless. The field is a dropdown now, and a list that offers
#: South/West/North/East and nothing else cannot express a row that holds
#: 48 - 16 of your slots do, and 2 hold 51. Leaving them out would have
#: made those rows uneditable rather than unlabelled.
#:
#: `Unknown0x30` and `Unknown0x33` are FFTPatcher's names and they say what
#: is actually known: that the value occurs and that nobody has worked out
#: what it does. Inventing "South-East" would be worse than the number.
FACING_NAMES = {
    0: "South", 1: "West", 2: "North", 3: "East",
    48: "Unknown 0x30", 51: "Unknown 0x33",
}


@dataclass(frozen=True)
class EventUnit:
    """One 40-byte unit slot, as a mapping of field name to raw number."""
    event_id: int
    slot: int
    values: dict

    @property
    def occupied(self) -> bool:
        """
        Whether this slot holds a unit at all.

        An unused slot is all zeroes, and says nothing either way - so a
        row pointing at one is reported as having nothing to inherit
        rather than as inheriting job 0 from sprite 0.
        """
        return bool(self.values.get("main_job")
                    or self.values.get("unit_name")
                    or self.values.get("sprite_set"))


def read_unit(block: bytes, event_id: int = -1, slot: int = -1) -> EventUnit:
    """One 40-byte slot. `block` must be exactly `UNIT_BYTES` long."""
    if len(block) != UNIT_BYTES:
        raise ValueError(
            f"a unit slot is {UNIT_BYTES} bytes, got {len(block)}")
    values = {name: block[offset] for name, offset in BYTE_FIELDS.items()}
    for name, offset in USHORT_FIELDS.items():
        values[name] = block[offset] | (block[offset + 1] << 8)
    # Byte 27 packs two things; both are given names of their own rather
    # than leaving callers to remember the mask.
    values["facing"] = block[27] & 0x7F
    values["upper_level"] = bool(block[27] & 0x80)
    values["always_present"] = bool(block[24] & 0x01)
    values["randomly_present"] = bool(block[24] & 0x02)
    return EventUnit(event_id=event_id, slot=slot, values=values)


def find_entd_files(unpacked_dir) -> list:
    """
    The four files inside an unpacked game folder, or [] if they aren't all
    there.

    All four or none: three files would silently answer "nothing to
    inherit" for every encounter in the missing one, which reads as the
    feature being broken rather than as a file being absent.
    """
    if unpacked_dir is None:
        return []
    folder = Path(unpacked_dir) / ENTD_FOLDER
    found = [folder / name for name in ENTD_FILENAMES]
    try:
        if all(path.is_file() for path in found):
            return found
    except OSError:
        return []
    return []


class EntdTables:
    """
    The 512 events, read once and kept.

    Read once because all four files together are 320 KB and the answer
    does not change while the tool runs - the same bargain
    `pzd_data.build_voice_index` makes, at a fraction of the cost.
    """

    def __init__(self, events: dict):
        self.events = events

    # -- loading ----------------------------------------------------------

    @classmethod
    def from_folder(cls, unpacked_dir) -> Optional["EntdTables"]:
        """
        Reads an unpacked game folder, or returns None when it has no ENTD
        files.

        None rather than an exception, and None rather than an empty
        table: the Encounters page has to stay usable without `fftpack`,
        and a caller that cannot tell "not unpacked" from "unpacked and
        empty" will display one as the other.
        """
        paths = find_entd_files(unpacked_dir)
        if not paths:
            return None
        try:
            return cls.from_files(paths)
        except (OSError, ValueError):
            return None

    @classmethod
    def from_files(cls, paths) -> "EntdTables":
        """`paths` in file order: battle_entd1 first."""
        events = {}
        for index, path in enumerate(paths):
            data = Path(path).read_bytes()
            if len(data) != FILE_BYTES:
                # Raised, not rounded off. A different size means a
                # different format, and reading it with this layout would
                # produce plausible numbers that are not the game's.
                raise ValueError(
                    f"{Path(path).name} is {len(data)} bytes; every ENTD "
                    f"file is {FILE_BYTES}. A different size means a "
                    f"different format - measure it before reading it.")
            for event in range(EVENTS_PER_FILE):
                base = event * EVENT_BYTES
                event_id = index * EVENTS_PER_FILE + event
                events[event_id] = [
                    read_unit(data[base + slot * UNIT_BYTES:
                                   base + (slot + 1) * UNIT_BYTES],
                              event_id, slot)
                    for slot in range(UNITS_PER_EVENT)]
        return cls(events)

    # -- lookup -----------------------------------------------------------

    def unit_at(self, key: int, key2: int) -> Optional[EventUnit]:
        """
        The unit an `OverrideEntryData` row patches, by its (Key, Key2).

        None when the address is outside the tables or the slot is empty -
        both of which mean "there is nothing to say what this inherits",
        which is a thing the page has to be able to display.
        """
        try:
            slots = self.events[int(key)]
            unit = slots[int(key2)]
        except (KeyError, IndexError, TypeError, ValueError):
            return None
        return unit if unit.occupied else None

    def inherited_values(self, key: int, key2: int) -> dict:
        """
        `{OverrideEntryData column: the value that column inherits}`.

        Both the twelve id columns and the nine plain-number ones, so a
        caller asks once. Empty when the address has nothing behind it, so
        `if not inherited` is the one check a caller needs.
        """
        unit = self.unit_at(key, key2)
        if unit is None:
            return {}
        return {column: unit.values[source]
                for column, source in ALL_ENCOUNTER_SOURCES.items()}


def describe_inherited(column: str, value) -> str:
    """
    One of the numeric columns' inherited value, in words.

    Names what has a name and shows the number otherwise, which is the same
    rule the dropdowns' Inherit entry follows - an invented name is worse
    than a number on a page whose whole convention is to say how much is
    actually known.

    **Six of the nine no longer come through here.** Job Unlock, Spriteset,
    Level, Bravery, Faith and Initial Direction are dropdowns now
    (`constants.ENTRY_VALUE_FIELDS`), and a dropdown says what it inherits
    in its own Inherit ENTRY, from the same list its ordinary entries come
    from - so naming them twice, once in a list and once in a caption
    underneath, would be two mechanisms for one sentence. What still
    arrives here is Job Level, Position X and Position Y, which have no
    list and keep their captions.

    This function stays whole rather than being trimmed to those three: it
    is the reader's answer to "what does this column's value mean", the
    ENTD suite checks it column by column, and a caller outside the page
    asking about Level should still get "Random" for 254.

    `Job Unlock` used to be excluded here on the grounds that its numbering
    "shifted in this game" and naming it would be inventing. That was true
    when nothing had checked. It has now been checked: ids 1-19 are jobs
    0x4B-0x5D in this game's own job table, which is what FFTPatcher builds
    its list from, and 20 is one past the end - so the field became a
    dropdown and the naming happens there.
    """
    if value is None:
        return ""
    if column in RANDOM_BYTE_COLUMNS and value == RANDOM_BYTE:
        return "Random"
    if column == "InitialDirection":
        return FACING_NAMES.get(value, str(value))
    return str(value)
