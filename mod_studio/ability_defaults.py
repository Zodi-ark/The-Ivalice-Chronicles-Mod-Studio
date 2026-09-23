"""
What an ability's override layer is inheriting.

`OverrideAbilityActionData` patches the game's own ability table. Every
field it does not set holds `-1`, and in the vanilla game that is **eight of
its ten fields on all 368 rows** - Range, Effect Area, Vertical, Element,
Formula, X, Y and Inflict Status are -1 everywhere, and only CT (28 rows)
and MP Cost (4) are ever set. So those eight told a modder nothing at all
until this file existed.

The same is true of the four flag bytes, nearly: `Flags12` is empty on all
368 rows and `Flags34` on 353 of them. They are in this file too - see
`FLAG_COLUMNS` for why they were left out of the first version and what
was wrong with that reasoning.

The values behind the -1 come from `data/AbilityActionDefaults.txt`, a plain
`|`-separated table that ships populated and can be edited freely. It is
derived from FFTPatcher's vanilla **War of the Lions** ability table, which
is GPL-3.0 - the same licensing situation as `EncounterNames.txt`, and the
reason Mod Studio is GPL-3.0. See NOTICE.md, and
`dev/make_ability_defaults.py` for how the file is produced and what was
measured before building on it.

**War of the Lions, not the original PlayStation release.** The Ivalice
Chronicles is built on War of the Lions, so the PSP table is the right one.
FFTPatcher ships both; they differ in 55 of the 368 records, and the first
version of this file used the wrong one. See the generator's docstring.

**Why a shipped file rather than something read from the game.** The game
does not ship this table. FFTPatcher reads it from the release's boot
executable; a search of all 5,848 files of a real unpacked `fftpack` - for
the whole blob, for its attributes region, and for individual records -
found it in none of them. `Ability-en` holds only text and UI columns, and
`data/AbilityActionData.xml` is a signpost pointing at the Nex table. This
is the one place where the honest answer was "the data is not in the
player's own files".

**It degrades.** Delete the file, or edit it into nonsense, and every caller
gets `{}` - the fields go back to showing -1 and nothing else changes. The
Abilities tab must stay usable without it, the same rule the ENTD reader
follows.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from . import constants as c
from . import paths

#: The file, in `data/` beside the other reference lists.
DEFAULTS_FILENAME = "AbilityActionDefaults.txt"

#: Ability ids 0x000-0x16F have a 14-byte action record; above that the
#: game uses shorter ones for the Reaction/Support/Movement abilities, which
#: have no action data to inherit. `OverrideAbilityActionData` holds exactly
#: 368 rows keyed 0-367, which is the same range - it stops where the record
#: stops, and that agreement is one of the reasons this table is believed to
#: be the right one.
ABILITY_COUNT = 0x170                       # 368
RECORD_BASE = 0x1000
RECORD_BYTES = 14

#: The four flag bytes, in the order `ABILITY_FLAG_DEFS` groups them.
#:
#: Left out of this file at first, on the grounds that the nxd stores them
#: as LISTS while the PlayStation record packs them as bits, with no vanilla
#: row setting either to work the correspondence out from. **Both halves of
#: that were wrong**, and the second one was checkable in ten seconds:
#:
#:   * `data/nex_layouts/OverrideAbilityActionData.layout` states the
#:     mapping in a comment - "each array is two values; if 0 or greater
#:     they patch their respective flags field - ie: Flags12[0] refers to
#:     Flags1, Flags12[1] refers to Flags2". Nothing had to be derived; the
#:     comment had not been read.
#:   * 15 rows DO set `Flags34`. Fourteen hold `[18]` and Dispelna holds
#:     `[50]`, and the vanilla Flags3 behind those same abilities is 16 and
#:     48 - each override is its own vanilla byte with bit 1 set. Two
#:     different base values, one consistent change.
#:
#: `nxd_data.FLAG_GROUP_COLUMN` already maps group 0-3 onto those two
#: columns and `unpack_flag_group` already turns a byte into tick boxes, so
#: what was missing was only the vanilla byte to start from.
FLAG_COLUMNS = ("Flags1", "Flags2", "Flags3", "Flags4")

#: The columns of the shipped file: the engine's ten override columns, then
#: the four flag bytes. The first ten are read from `constants` rather than
#: restated, so the file, the reader and the page cannot disagree about
#: which ten those are.
COLUMNS = tuple(c.OVERRIDE_ALL_COLUMNS) + FLAG_COLUMNS

#: Which of `ABILITY_FLAG_DEFS`' four groups each flag column is. Group 0 is
#: Flags1 and so on, which is the order both the layout comment and
#: `FLAG_GROUP_COLUMN` use.
FLAG_COLUMN_FOR_GROUP = {index: name for index, name in enumerate(FLAG_COLUMNS)}

#: The line in the shipped file that names its columns. The file is meant to
#: be edited by hand, so it says what its own fields are and the reader
#: checks rather than counting on position - a hand-edited file with a
#: column dropped would otherwise be read silently and wrongly.
COLUMNS_DIRECTIVE = "#columns:"

FILE_HEADER = """\
# Vanilla ability action data for The Ivalice Chronicles Mod Studio
# =================================================================
#
# One ability per line:
#
#     <decimal id>|<Range>|<EffectArea>|...|<CT>|<MPCost>|<Flags1..4>
#
# The `#columns:` line below is the authority on the order - the tool reads
# it from there rather than counting positions, so a hand-edited file with a
# column dropped is refused instead of silently misread.
#
# Blank lines and lines starting with # are ignored, except the `#columns:`
# line below, which names the fields and is what the tool reads the order
# from. Edit freely - this is your file. Deleting it is fine too: the
# Abilities tab then shows -1 for an inherited field, as it did before.
#
# WHAT THIS IS FOR
# ----------------
# The Abilities tab's override layer patches the game's own ability table.
# A field it does not set reads -1, and in the vanilla game that is eight of
# its ten fields on all 368 abilities. This file is what lets the tab say
# "Inherits 6" instead of just "-1", and it is what lets the Inflict Status
# tab list the abilities that use each status row.
#
# The last four columns are the flag bytes - FFTPatcher's Flags I to IV, in
# that order. The nxd stores them as `Flags12` and `Flags34`, two values to
# an array, and the table layout says which is which: Flags12[0] is Flags1.
# They are what the four tick-box panels show while a group is inheriting.
#
# WHERE IT CAME FROM, AND HOW SURE IT IS
# --------------------------------------
# Derived from FFTPatcher's copy of the WAR OF THE LIONS ability table
# (Glain, https://github.com/Glain/FFTPatcher, GPL-3.0), 14 bytes per
# ability at 0x1000 + 14*id. The Ivalice Chronicles does not ship this
# table as a file - it lives inside the executable - so it cannot be
# compared byte for byte against your own game. What IS established:
#
#   * the ability ids are the same ids: FFTPatcher's War of the Lions names
#     and this game's agree exactly on 440 of 491 - 89.6%;
#   * the table is the same length, and it is an odd one - the 14-byte
#     record stops at id 0x16F, and OverrideAbilityActionData holds exactly
#     368 rows keyed 0-367;
#   * this game's own 32 overrides all land on an ability whose value here
#     is non-zero, and 31 of the 32 are strictly LOWER - a rebalance of
#     these numbers, with nothing restating a value it already had;
#   * everything else this game reuses from the older data is
#     byte-identical - all four ENTD battle files by checksum, and the
#     ability effect and animation tables inside battle_bin.
#
# **War of the Lions, not the original PlayStation release.** FFTPatcher
# ships both and they differ in 55 of the 368 records. The first version of
# this file used the older one, and about one ability in seven was wrong -
# Plunder Gil, a War of the Lions ability, was showing an Inflict Status it
# does not have. If a value here ever looks wrong, that is the first thing
# to suspect.
#
# That is strong evidence and not a proof. If you find a value here that
# disagrees with the game, this file is yours to correct.
#"""


#: Read once. The same bargain `reference_names._load` makes and for the
#: same reason - it is a file on disk that does not change while the tool
#: runs, and the usage index on the Inflict Status page recomputes on every
#: item edit.
_cache: dict = {}


def defaults_path() -> Path:
    """Where the shipped file lives."""
    return paths.bundled_data_dir() / DEFAULTS_FILENAME


def cached() -> dict:
    """`load()`, read once per process."""
    if "table" not in _cache:
        _cache["table"] = load()
    return _cache["table"]


def forget() -> None:
    """Drops the cache. For checks that write a different file."""
    _cache.clear()


def load(path: Optional[Path] = None) -> dict:
    """
    `{ability id: {column: value}}`, or `{}` when the file is unusable.

    Never raises. A missing, unreadable or malformed file means the
    Abilities tab shows -1 for an inherited field, which is exactly what it
    did before this existed - a page that will not open is not more correct,
    just less useful.

    Rows are validated rather than trusted, because the file is meant to be
    edited by hand: a row with the wrong number of fields, a non-numeric
    value or an id outside the table is skipped, and the rest still load.
    """
    target = Path(path) if path is not None else defaults_path()
    try:
        text = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}

    columns = None
    found: dict = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            if stripped.lower().startswith(COLUMNS_DIRECTIVE):
                names = [part.strip() for part in
                         stripped[len(COLUMNS_DIRECTIVE):].split("|")]
                # The first field is the id; the rest are the columns.
                columns = names[1:] if names and names[0].lower() == "id" \
                    else names
            continue
        if columns is None:
            # No `#columns:` line, so nothing says what the fields are.
            # Falling back to the built-in order would read a hand-edited
            # file positionally and silently, which is the failure this
            # directive exists to prevent.
            return {}
        parts = [part.strip() for part in stripped.split("|")]
        if len(parts) != len(columns) + 1:
            continue
        try:
            ability_id = int(parts[0])
            values = [int(part) for part in parts[1:]]
        except ValueError:
            continue
        if not 0 <= ability_id < ABILITY_COUNT:
            continue
        found[ability_id] = dict(zip(columns, values))
    return found


def inherited(defaults: dict, ability_id, column: str):
    """
    One ability's vanilla value for one column, or None.

    None rather than a number when the table has no row for that ability or
    no such column, so a caller can tell "inherits 0" from "nothing is
    known" - the distinction the whole page turns on.
    """
    try:
        row = defaults.get(int(ability_id))
    except (TypeError, ValueError):
        return None
    if not row:
        return None
    return row.get(column)
