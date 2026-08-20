"""
Reading and writing Ability / OverrideAbilityActionData data via the SQLite
database FF16Tools' nxd-to-sqlite produces.

This is a fundamentally different data model from JobData/JobCommandData:
those are XML tables the mod loader itself ships and diffs; .nxd files only
exist after unpacking the actual game, aren't shipped anywhere, and when a
mod overrides one it's a FULL replacement, not a sparse diff. So editing
here works from a complete baseline (read every row) and edits are tracked
per (key, field), same include/inherit idea as everywhere else in this
tool, but the export step must still write every row back out completely.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import constants as c


# ---------------------------------------------------------------------------
# Flags / Element bit packing - ported from flag_codex.html's computeFlagsetByte,
# itself verified against FFTPatcher's AbilityAttributes.cs.
# ---------------------------------------------------------------------------

def pack_flag_group(group_index: int, bit_states: dict) -> int:
    """
    bit_states: {flag_id: bool} for (some or all of) the non-blank flags in
    this group. Missing ids are treated as unchecked. Returns the 0-255 byte
    value, honoring each flag's "inverted" storage.
    """
    items = [f for f in c.ABILITY_FLAG_DEFS if f[2] == group_index]
    result = 0
    for row, (flag_id, _label, _group, inverted, blank) in enumerate(items):
        checked = False if blank else bool(bit_states.get(flag_id, False))
        effective = (not checked) if inverted else checked
        if effective:
            result |= (1 << (7 - row))
    return result


def unpack_flag_group(group_index: int, byte_value: int) -> dict:
    """Inverse of pack_flag_group: byte value -> {flag_id: bool} (checkbox state)."""
    items = [f for f in c.ABILITY_FLAG_DEFS if f[2] == group_index]
    states = {}
    for row, (flag_id, _label, _group, inverted, blank) in enumerate(items):
        if blank:
            continue
        bit_set = bool(byte_value & (1 << (7 - row)))
        states[flag_id] = (not bit_set) if inverted else bit_set
    return states


def pack_element_value(element_states: dict) -> int:
    """{element_name: bool} -> 0-255 bitmask."""
    return sum(value for name, value in c.ABILITY_ELEMENT_VALUES if element_states.get(name, False))


def unpack_element_value(byte_value: int) -> dict:
    """0-255 bitmask -> {element_name: bool}."""
    return {name: bool(byte_value & value) for name, value in c.ABILITY_ELEMENT_VALUES}


def split_jp_cost(value: int) -> tuple[int, int]:
    """JP cost (0-65535) -> (JpCost1 low byte, JpCost2 high byte). Matches flag_codex.html exactly."""
    v = max(0, min(65535, int(value)))
    return v & 0xFF, (v >> 8) & 0xFF


def join_jp_cost(cost1: int, cost2: int) -> int:
    """(JpCost1, JpCost2) -> combined 0-65535 JP cost."""
    return (int(cost1) & 0xFF) | ((int(cost2) & 0xFF) << 8)


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------

@dataclass
class AbilityRecord:
    """One row of a per-language Ability-xx table."""
    key: int
    values: dict = field(default_factory=dict)  # field name -> raw value (as read from sqlite)

    @property
    def display_name(self) -> str:
        name = (self.values.get("Name") or "").strip()
        if name:
            return f"{self.key:04d} - {name}"
        return f"{self.key:04d} - (unnamed)"

    @property
    def jp_cost(self) -> int:
        return join_jp_cost(self.values.get("JpCost1", 0) or 0, self.values.get("JpCost2", 0) or 0)


@dataclass
class OverrideActionRecord:
    """One row of the shared OverrideAbilityActionData table."""
    key: int
    flags12: list  # raw JSON array as read, e.g. [] or [50] or [-1, 50]
    flags34: list
    scalars: dict = field(default_factory=dict)  # e.g. {"Range": -1, "CT": 5, ...}

    def flag_group_value(self, group_index: int) -> int:
        """Effective byte for group 0-3, treating a missing array position as -1 (not set)."""
        arr = self.flags12 if group_index in (0, 1) else self.flags34
        pos = group_index % 2
        raw = arr[pos] if pos < len(arr) else c.OVERRIDE_NOT_SET
        return c.OVERRIDE_NOT_SET if raw is None else int(raw)


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

def _table_exists(con: sqlite3.Connection, table_name: str) -> bool:
    cur = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    return cur.fetchone() is not None


def read_ability_table(sqlite_path: Path, language: str) -> list[AbilityRecord]:
    table = c.NXD_ABILITY_TABLE[language]
    con = sqlite3.connect(str(sqlite_path))
    try:
        if not _table_exists(con, table):
            raise ValueError(
                f"No '{table}' table in this database - was ability.{language}.nxd "
                f"included when it was converted?"
            )
        con.row_factory = sqlite3.Row
        cur = con.execute(f'SELECT * FROM "{table}" ORDER BY Key')
        records = []
        for row in cur.fetchall():
            values = {}
            for k in row.keys():
                if k == "Key":
                    continue
                v = row[k]
                if k in c.ABILITY_ARRAY_FIELDS and v:
                    v = json.loads(v)
                values[k] = v
            records.append(AbilityRecord(key=row["Key"], values=values))
        return records
    finally:
        con.close()


def read_override_action_table(sqlite_path: Path) -> list[OverrideActionRecord]:
    table = c.NXD_OVERRIDE_ACTION_TABLE
    con = sqlite3.connect(str(sqlite_path))
    try:
        if not _table_exists(con, table):
            raise ValueError(
                f"No '{table}' table in this database - was {c.NXD_OVERRIDE_ACTION_FILENAME} "
                f"included when it was converted?"
            )
        con.row_factory = sqlite3.Row
        cur = con.execute(f'SELECT * FROM "{table}" ORDER BY Key')
        records = []
        for row in cur.fetchall():
            flags12 = json.loads(row["Flags12"]) if row["Flags12"] else []
            flags34 = json.loads(row["Flags34"]) if row["Flags34"] else []
            scalars = {name: row[name] for name in c.OVERRIDE_ALL_COLUMNS}
            records.append(OverrideActionRecord(key=row["Key"], flags12=flags12, flags34=flags34, scalars=scalars))
        return records
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Writing - applies {key: {field: value}} edits directly onto the sqlite,
# leaving every other row/field exactly as FF16Tools produced it.
# ---------------------------------------------------------------------------

def write_ability_edits(sqlite_path: Path, language: str, edits: dict) -> None:
    """edits: {key: {field_name: new_raw_value}}. Only touches given keys/fields."""
    if not edits:
        return
    table = c.NXD_ABILITY_TABLE[language]
    con = sqlite3.connect(str(sqlite_path))
    try:
        for key, fields in edits.items():
            if not fields:
                continue
            set_clause = ", ".join(f'"{name}" = ?' for name in fields)
            params = [
                json.dumps(value, separators=(",", ":")) if name in c.ABILITY_ARRAY_FIELDS else value
                for name, value in fields.items()
            ]
            params.append(key)
            con.execute(f'UPDATE "{table}" SET {set_clause} WHERE Key = ?', params)
        con.commit()
    finally:
        con.close()


@dataclass
class ItemRecord:
    """One row of a per-language Item-xx table. Simpler than AbilityRecord - no
    array fields, no JP Cost split, and no OverrideAbilityActionData-style
    shared companion table (items' stats live in the Item*Data.xml diff
    tables instead - see item_xml_io.py)."""
    key: int
    values: dict = field(default_factory=dict)  # field name -> raw value (as read from sqlite)

    @property
    def display_name(self) -> str:
        name = (self.values.get("Name") or "").strip()
        if name:
            return f"{self.key:03d} - {name}"
        return f"{self.key:03d} - (unnamed)"


def read_item_table(sqlite_path: Path, language: str) -> list:
    table = c.NXD_ITEM_TABLE[language]
    con = sqlite3.connect(str(sqlite_path))
    try:
        if not _table_exists(con, table):
            raise ValueError(
                f"No '{table}' table in this database - was item.{language}.nxd "
                f"included when it was converted?"
            )
        con.row_factory = sqlite3.Row
        cur = con.execute(f'SELECT * FROM "{table}" ORDER BY Key')
        records = []
        for row in cur.fetchall():
            values = {k: row[k] for k in row.keys() if k != "Key"}
            records.append(ItemRecord(key=row["Key"], values=values))
        return records
    finally:
        con.close()


def write_item_edits(sqlite_path: Path, language: str, edits: dict) -> None:
    """edits: {key: {field_name: new_raw_value}}. Only touches given keys/fields."""
    if not edits:
        return
    table = c.NXD_ITEM_TABLE[language]
    con = sqlite3.connect(str(sqlite_path))
    try:
        for key, fields in edits.items():
            if not fields:
                continue
            set_clause = ", ".join(f'"{name}" = ?' for name in fields)
            params = list(fields.values())
            params.append(key)
            con.execute(f'UPDATE "{table}" SET {set_clause} WHERE Key = ?', params)
        con.commit()
    finally:
        con.close()


# A group's byte lives at this position within this 2-element JSON array
# column - group 0/1 pack into Flags12, group 2/3 into Flags34 (see
# constants.ABILITY_FLAG_DEFS / nxd_data.pack_flag_group).
FLAG_GROUP_COLUMN = {0: ("Flags12", 0), 1: ("Flags12", 1), 2: ("Flags34", 0), 3: ("Flags34", 1)}


def write_override_action_edits(sqlite_path: Path, edits: dict) -> None:
    """
    edits: {key: {field_name: new_value}}, where field_name is one of:
      - OVERRIDE_ALL_COLUMNS (Range/EffectArea/Vertical/Element/Formula/X/Y/
        InflictStatus/CT/MPCost - all plain ints, OVERRIDE_NOT_SET for
        "don't override")
      - "Flags12"/"Flags34" directly (2-element lists of int, same
        OVERRIDE_NOT_SET sentinel per position) - a whole-column write.
      - "FlagsGroup0".."FlagsGroup3" (a single int 0-255 or OVERRIDE_NOT_SET)
        - the granularity the Abilities tab actually edits at, since each
        group has its own independent include/inherit checkbox but two
        groups share one physical column. Writing one group must not
        clobber its sibling group's value, so this is done as a targeted
        read-modify-write against whatever's already in that column on
        sqlite_path (safe because Export always applies edits to a fresh
        staged copy, never the shared loaded database - see step_export.py/
        stage_sqlite_copy) rather than requiring the caller to already know
        the sibling's baseline value.
    """
    if not edits:
        return
    table = c.NXD_OVERRIDE_ACTION_TABLE
    con = sqlite3.connect(str(sqlite_path))
    try:
        for key, fields in edits.items():
            if not fields:
                continue

            direct_fields = {}
            group_edits: dict = {}  # column_name -> {position: value}
            for name, value in fields.items():
                if name.startswith("FlagsGroup"):
                    group_index = int(name[len("FlagsGroup"):])
                    column, pos = FLAG_GROUP_COLUMN[group_index]
                    group_edits.setdefault(column, {})[pos] = value
                else:
                    direct_fields[name] = value

            set_parts = []
            params: list = []
            for name, value in direct_fields.items():
                set_parts.append(f'"{name}" = ?')
                params.append(json.dumps(value, separators=(",", ":")) if name in ("Flags12", "Flags34") else value)

            if group_edits:
                columns = list(group_edits.keys())
                select_cols = ", ".join('"{}"'.format(col) for col in columns)
                cur = con.execute(
                    f'SELECT {select_cols} FROM "{table}" WHERE Key = ?', (key,)
                )
                row = cur.fetchone()
                for i, column in enumerate(columns):
                    current = list(json.loads(row[i])) if row and row[i] else []
                    while len(current) < 2:
                        current.append(c.OVERRIDE_NOT_SET)
                    for pos, value in group_edits[column].items():
                        current[pos] = value
                    set_parts.append(f'"{column}" = ?')
                    params.append(json.dumps(current, separators=(",", ":")))

            if not set_parts:
                continue
            params.append(key)
            con.execute(f'UPDATE "{table}" SET {", ".join(set_parts)} WHERE Key = ?', params)
        con.commit()
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Staging - nxd is a real game data folder (thousands of files after a full
# unpack); we only ever need the 8 ability-related ones, copied into a small
# scratch folder before handing off to FF16Tools.CLI.
# ---------------------------------------------------------------------------

def prepare_staging_folder(source_nxd_dir: Path, staging_dir: Path,
                           include_all: bool = False) -> list[str]:
    """
    Copies whichever of the known ability-, item-, encounter-, and poach-
    related .nxd files exist in source_nxd_dir into staging_dir/nxd/, ready
    for nxd-to-sqlite. Returns the filenames actually found (missing files
    are skipped, not an error - e.g. a partial/manually-curated nxd folder,
    or one that only covers some of these tabs). A single converted
    database can hold any combination of these tables side by side;
    read_ability_table/read_item_table/read_charaname_table/
    read_poach_table each check for their own table's presence
    independently, so a database missing one just means that tab has
    nothing to show until a fuller conversion is run.

    The `ui.<lang>.nxd` files are staged too, even though nothing in this
    tool edits them: key 3737 of each holds the game's own version string,
    which is how an unpacked game and an opened mod both get dated (see
    migration.read_game_version). Staging them here rather than converting
    separately means a mod's version is readable from the same database
    everything else already reads.

    **The target is emptied first, and that is load-bearing.** This folder
    is a fixed path reused by every mod, and FF16Tools converts the
    *folder*, not the list this function returns - so a file left behind by
    a previous mod is converted as though it belonged to this one. Opening
    Dark Knight Expansion and then a texture pack staged 7 files and
    converted 11, and the mod that ships no abilities at all came up showing
    Dark Knight Expansion's abilities, items and encounter rekeys.

    Only `.nxd` is removed, rather than the whole directory: nothing else
    should be in here, but a targeted delete cannot be the reason someone
    loses a file if that assumption is ever wrong.
    """
    import shutil

    target = staging_dir / "nxd"
    target.mkdir(parents=True, exist_ok=True)
    for stale in target.glob("*.nxd"):
        try:
            stale.unlink()
        except OSError:
            pass
    if include_all:
        # Everything the source has, used when staging a *mod*. A mod ships
        # a handful of files, so converting the lot costs nothing and means
        # the tool can say something true about every one of them. The fixed
        # list below is for the game, where "everything" is 564 files.
        #
        # This was not merely a missing feature. A table that wasn't staged
        # couldn't be read, and assess_unmodelled_table reported an
        # unreadable table as "no differences from the game's copy" - so a
        # mod's uibuttonguide.nxd with 967 differing rows and 35 missing
        # ones was shown as identical to vanilla.
        names = sorted(p.name for p in source_nxd_dir.glob("*.nxd") if p.is_file())
    else:
        names = [n for n in c.NXD_ALL_STAGED_FILENAMES if (source_nxd_dir / n).exists()]

    found = []
    for filename in names:
        src = source_nxd_dir / filename
        if src.exists():
            shutil.copy(src, target / filename)
            found.append(filename)
    return found


def stage_sqlite_copy(source_sqlite: Path, staging_dir: Path) -> Path:
    """
    Copies the (never-mutated) loaded database into a fresh scratch copy for
    this export - so edits get applied to a throwaway file each time rather
    than accumulating on the one the Abilities tab reads from, and so
    un-including a field never leaves a stale value baked in from a
    previous export.
    """
    import shutil

    staging_dir.mkdir(parents=True, exist_ok=True)
    dest = staging_dir / "fft_data.sqlite"
    shutil.copy(source_sqlite, dest)
    return dest


def tables_to_reexport(touched_languages: list, override_touched: bool) -> list:
    """
    Since .nxd files are full replacements (not diffs), only files that were
    actually touched should be re-exported at all - an untouched language or
    OverrideAbilityActionData should be left out of the mod entirely, same
    principle as everywhere else in this tool (don't ship what you didn't
    change), just applied at the whole-file level instead of per-field.
    """
    tables = [c.NXD_ABILITY_TABLE[lang] for lang in touched_languages]
    if override_touched:
        tables.append(c.NXD_OVERRIDE_ACTION_TABLE)
    return tables


def tables_to_reexport_items(touched_languages: list) -> list:
    """Same idea as tables_to_reexport, for Item-xx (no override-table equivalent for items)."""
    return [c.NXD_ITEM_TABLE[lang] for lang in touched_languages]


def tables_to_reexport_encounters(touched_languages: list, entry_touched: bool) -> list:
    """Same idea as tables_to_reexport, for CharaName-xx + OverrideEntryData."""
    tables = [c.NXD_CHARANAME_TABLE[lang] for lang in touched_languages]
    if entry_touched:
        tables.append(c.NXD_OVERRIDE_ENTRY_TABLE)
    return tables


@dataclass
class CharaNameRecord:
    """One row of a per-language CharaName-xx table - same simple shape as ItemRecord."""
    key: int
    values: dict = field(default_factory=dict)

    @property
    def display_name(self) -> str:
        name = (self.values.get("Name") or "").strip()
        if name:
            return f"{self.key:03d} - {name}"
        return f"{self.key:03d} - (unnamed)"


def read_charaname_table(sqlite_path: Path, language: str) -> list:
    table = c.NXD_CHARANAME_TABLE[language]
    con = sqlite3.connect(str(sqlite_path))
    try:
        if not _table_exists(con, table):
            raise ValueError(
                f"No '{table}' table in this database - was charaname.{language}.nxd "
                f"included when it was converted?"
            )
        con.row_factory = sqlite3.Row
        cur = con.execute(f'SELECT * FROM "{table}" ORDER BY Key')
        records = []
        for row in cur.fetchall():
            values = {k: row[k] for k in row.keys() if k != "Key"}
            records.append(CharaNameRecord(key=row["Key"], values=values))
        return records
    finally:
        con.close()


def write_charaname_edits(sqlite_path: Path, language: str, edits: dict) -> None:
    """edits: {key: {field_name: new_raw_value}}. Only touches given keys/fields."""
    if not edits:
        return
    table = c.NXD_CHARANAME_TABLE[language]
    con = sqlite3.connect(str(sqlite_path))
    try:
        for key, fields in edits.items():
            if not fields:
                continue
            set_clause = ", ".join(f'"{name}" = ?' for name in fields)
            params = list(fields.values())
            params.append(key)
            con.execute(f'UPDATE "{table}" SET {set_clause} WHERE Key = ?', params)
        con.commit()
    finally:
        con.close()


@dataclass
class EntryRecord:
    """
    One row of OverrideEntryData - a unit slot (key2, 0-15) within an
    encounter (key). Unlike Ability/Item's per-key tables, this one is
    keyed by the (key, key2) *pair* - see nxd_data module docstring / the
    Encounters section of HANDOFF.md for why there's no dense "reference
    table" backing it the way AbilityData.xml/ItemData.xml did.
    """
    key: int
    key2: int
    values: dict = field(default_factory=dict)  # field name -> raw value; ENTRY_ARRAY_FIELDS already json-parsed to list[int]

    @property
    def display_name(self) -> str:
        return f"Unit {self.key2}"


def read_override_entry_table(sqlite_path: Path) -> list:
    table = c.NXD_OVERRIDE_ENTRY_TABLE
    con = sqlite3.connect(str(sqlite_path))
    try:
        if not _table_exists(con, table):
            raise ValueError(f"No '{table}' table in this database - was overrideentrydata.nxd included when it was converted?")
        con.row_factory = sqlite3.Row
        cur = con.execute(f'SELECT * FROM "{table}" ORDER BY Key, Key2')
        records = []
        for row in cur.fetchall():
            values = {}
            for k in row.keys():
                if k in ("Key", "Key2"):
                    continue
                raw = row[k]
                if k in c.ENTRY_ARRAY_FIELDS:
                    try:
                        values[k] = list(json.loads(raw)) if raw else []
                    except (TypeError, ValueError, json.JSONDecodeError):
                        values[k] = []
                else:
                    values[k] = raw
            records.append(EntryRecord(key=row["Key"], key2=row["Key2"], values=values))
        return records
    finally:
        con.close()


@dataclass
class PoachItemRecord:
    """
    One row of a per-language PoachItem-xx table. Unlike ItemRecord, this
    one carries BOTH text (Name/Description/etc.) AND numeric/economy
    fields (Cost/SellPrice/IconId/IsRare/etc.) - PoachItem has no separate
    shared table the way OverrideAbilityActionData/ItemData.xml provide for
    Ability/Item, so every field genuinely lives in this per-language row.
    See constants.py's Poaching section docstring for the full picture.
    """
    key: int
    values: dict = field(default_factory=dict)  # field name -> raw value (as read from sqlite)

    @property
    def display_name(self) -> str:
        name = (self.values.get("Name") or "").strip()
        if name:
            return f"{self.key:03d} - {name}"
        return f"{self.key:03d} - (unnamed)"


def read_poach_table(sqlite_path: Path, language: str) -> list:
    """
    Reads PoachItem-<language>, translating FF16Tools' raw "UnknownXX"
    column names to this tool's friendly field names (Name/Description/
    ProducedItemId/etc.) via constants.POACH_FIELD_FRIENDLY_NAMES - see
    that mapping's own comment for why this translation exists and where.
    """
    table = c.NXD_POACH_TABLE[language]
    con = sqlite3.connect(str(sqlite_path))
    try:
        if not _table_exists(con, table):
            raise ValueError(
                f"No '{table}' table in this database - was poachitem.{language}.nxd "
                f"included when it was converted?"
            )
        con.row_factory = sqlite3.Row
        cur = con.execute(f'SELECT * FROM "{table}" ORDER BY Key')
        records = []
        for row in cur.fetchall():
            values = {}
            for k in row.keys():
                if k == "Key":
                    continue
                values[c.POACH_FIELD_FRIENDLY_NAMES.get(k, k)] = row[k]
            records.append(PoachItemRecord(key=row["Key"], values=values))
        return records
    finally:
        con.close()


def write_poach_edits(sqlite_path: Path, language: str, edits: dict) -> None:
    """
    edits: {key: {friendly_field_name: new_raw_value}}. Only touches given
    keys/fields. Friendly names are translated back to FF16Tools' real
    "UnknownXX" column names (constants.POACH_FIELD_RAW_NAMES) before the
    UPDATE - see read_poach_table's docstring.
    """
    if not edits:
        return
    table = c.NXD_POACH_TABLE[language]
    con = sqlite3.connect(str(sqlite_path))
    try:
        for key, fields in edits.items():
            if not fields:
                continue
            raw_fields = {c.POACH_FIELD_RAW_NAMES.get(name, name): value for name, value in fields.items()}
            set_clause = ", ".join(f'"{name}" = ?' for name in raw_fields)
            params = list(raw_fields.values())
            params.append(key)
            con.execute(f'UPDATE "{table}" SET {set_clause} WHERE Key = ?', params)
        con.commit()
    finally:
        con.close()


def tables_to_reexport_poach(touched_languages: list) -> list:
    """Same idea as tables_to_reexport_items, for PoachItem-xx (no shared-table equivalent to add)."""
    return [c.NXD_POACH_TABLE[lang] for lang in touched_languages]


def entry_default_row() -> dict:
    """
    What a brand-new OverrideEntryData row carries before anything is set.

    Every value comes from constants.entry_new_row_value, i.e. from the
    patch condition Nenkai's OverrideEntryData.layout states per column.
    This used to be a flat -1 for everything, which was wrong in a way that
    mattered: -1 is the "leave it alone" value for only about half the
    columns. For the rest it is an ordinary value the game will happily
    apply - so a new row silently asked the game to set Spriteset to 255
    (byte cast of -1), MainJob to 255, JobUnlock to 255, every UnknownFlags
    bit on, and - worst - Disable to a non-zero value, which per the layout
    forces Spriteset to 0 and suppresses every other patch on the row.
    """
    return {name: c.entry_new_row_value(name) for name in c.ENTRY_FIELD_ORDER}


def _entry_sql_value(field_name: str, value):
    """Arrays are stored as JSON text; everything else goes in as-is."""
    if field_name in c.ENTRY_ARRAY_FIELDS:
        return json.dumps(value, separators=(",", ":"))
    return value


def translate_entry_edits(edits: dict, rekeys: dict) -> dict:
    """
    Maps edits keyed by a row's ORIGIN address to the address that row will
    actually live at once rekeys are applied.

    The Encounters tab keys edits by origin on purpose: a row the user
    moves twice, or moves and then moves back, keeps one stable identity
    and one set of edits. Only at write time do the two views need to be
    reconciled, and doing it here (rather than in the export worker) keeps
    it testable.
    """
    if not rekeys:
        return dict(edits)
    return {rekeys.get(address, address): fields for address, fields in edits.items()}


def apply_override_entry_rekeys(sqlite_path: Path, rekeys: dict) -> None:
    """
    Moves rows to new (Key, Key2) addresses. rekeys: {(from_key, from_key2):
    (to_key, to_key2)}.

    Why this exists at all: rows cannot be *added* to this table in a way
    the game picks up (Zodi's own in-game testing), so changing an existing
    row's address is the real mechanism for making an encounter/unit slot
    the game doesn't otherwise have. See the Encounters section of
    HANDOFF.md.

    Two details that are easy to get wrong and are handled here:

    - Moves are done in two phases, via a temporary negative key space, so
      a swap (A->B while B->A) or a chain (A->B, B->C) can't collide
      part-way through. The table has no UNIQUE constraint on (Key, Key2),
      so a collision would not raise - it would silently produce duplicate
      rows.
    - The whole table is rewritten in (Key, Key2) order afterwards.
      Converting a real mod's own overrideentrydata.nxd back to SQLite
      gives rows in sorted key order, so the .nxd format is sorted, and
      leaving a moved row sitting at its old rowid would hand
      sqlite-to-nxd an out-of-order table. Not independently verified
      against FF16Tools itself (it can't run in this sandbox), but sorting
      matches what real files look like and costs nothing.
    """
    if not rekeys:
        return
    table = c.NXD_OVERRIDE_ENTRY_TABLE
    con = sqlite3.connect(str(sqlite_path))
    try:
        for index, (source, _dest) in enumerate(sorted(rekeys.items())):
            con.execute(
                f'UPDATE "{table}" SET Key = ?, Key2 = ? WHERE Key = ? AND Key2 = ?',
                (_TEMP_KEY_BASE - index, index, source[0], source[1]),
            )
        for index, (_source, dest) in enumerate(sorted(rekeys.items())):
            con.execute(
                f'UPDATE "{table}" SET Key = ?, Key2 = ? WHERE Key = ? AND Key2 = ?',
                (dest[0], dest[1], _TEMP_KEY_BASE - index, index),
            )
        _resort_override_entry_table(con)
        con.commit()
    finally:
        con.close()


def delete_override_entry_rows(sqlite_path: Path, addresses) -> None:
    """
    Removes rows outright. Used when an opened mod's own table simply
    doesn't have a row the game does, and the author's row set is being
    preserved rather than topped back up from vanilla.
    """
    addresses = list(addresses or [])
    if not addresses:
        return
    table = c.NXD_OVERRIDE_ENTRY_TABLE
    con = sqlite3.connect(str(sqlite_path))
    try:
        for key, key2 in addresses:
            con.execute(f'DELETE FROM "{table}" WHERE Key = ? AND Key2 = ?', (key, key2))
        con.commit()
    finally:
        con.close()


_TEMP_KEY_BASE = -100000


def _resort_override_entry_table(con) -> None:
    """Rewrites the table in (Key, Key2) order - see apply_override_entry_rekeys."""
    table = c.NXD_OVERRIDE_ENTRY_TABLE
    rows = con.execute(f'SELECT rowid FROM "{table}" ORDER BY Key, Key2').fetchall()
    if not rows:
        return
    con.execute(f'CREATE TEMP TABLE "_entry_resort" AS SELECT * FROM "{table}" ORDER BY Key, Key2')
    con.execute(f'DELETE FROM "{table}"')
    con.execute(f'INSERT INTO "{table}" SELECT * FROM "_entry_resort"')
    con.execute('DROP TABLE "_entry_resort"')


def write_override_entry_edits(sqlite_path: Path, edits: dict) -> None:
    """
    edits: {(key, key2): {field_name: new_raw_value}}, addressed by where
    the row will actually live (run translate_entry_edits first if the
    caller keys them by origin).

    Unlike every other write_* function in this module, this one may need
    to INSERT a brand new row - OverrideEntryData has no dense backing
    reference table (see EntryRecord's docstring). Note that a row the game
    has never seen appears not to be picked up in-game (Zodi's own
    testing), so an INSERT here is a last resort rather than the normal
    path; rekeying an existing row is. Fields not given on a newly-inserted
    row come from entry_default_row() above.
    """
    if not edits:
        return
    table = c.NXD_OVERRIDE_ENTRY_TABLE
    default_row = entry_default_row()

    con = sqlite3.connect(str(sqlite_path))
    inserted_any = False
    try:
        for (key, key2), fields in edits.items():
            if not fields:
                continue
            exists = con.execute(
                f'SELECT 1 FROM "{table}" WHERE Key = ? AND Key2 = ? LIMIT 1', (key, key2)
            ).fetchone()
            if exists:
                set_clause = ", ".join(f'"{name}" = ?' for name in fields)
                params = [_entry_sql_value(name, value) for name, value in fields.items()]
                params.append(key)
                params.append(key2)
                con.execute(f'UPDATE "{table}" SET {set_clause} WHERE Key = ? AND Key2 = ?', params)
            else:
                row = dict(default_row)
                row.update(fields)
                columns = ["Key", "Key2"] + list(row.keys())
                values = [key, key2] + [_entry_sql_value(name, value) for name, value in row.items()]
                column_list = ", ".join(f'"{col}"' for col in columns)
                placeholders = ", ".join("?" for _ in columns)
                con.execute(f'INSERT INTO "{table}" ({column_list}) VALUES ({placeholders})', values)
                inserted_any = True
        if inserted_any:
            # A row appended at the end would leave the table out of key
            # order - see apply_override_entry_rekeys for why that matters.
            _resort_override_entry_table(con)
        con.commit()
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Reading a mod's edits back out of its exported .nxd files
# ---------------------------------------------------------------------------
# Export writes whole modified .nxd binaries, not diffs: the edits are
# applied to a staged copy of the database and the result is converted back
# with sqlite-to-nxd. That's what the mod loader needs, but it means a mod
# folder contains final values with no record of which fields the author
# actually changed.
#
# Recovering that is a three-step job: convert the mod's .nxd back to
# SQLite, read the same tables out of both it and the vanilla database, and
# treat every differing field as an edit. The vanilla database is the part
# that can't be skipped - without a baseline there is no way to tell an
# edited value from an untouched one - so this needs game files to have
# been unpacked first, and callers are expected to say so when they aren't.
#
# Comparison is per-field rather than per-row on purpose: a mod that only
# renamed one ability should come back as exactly that one field, not as
# every field of that row, so re-exporting doesn't turn incidental values
# into deliberate-looking overrides.
# ---------------------------------------------------------------------------


def _values_by_key(records: list) -> dict:
    return {record.key: record.values for record in records}


def _diff_values(vanilla: dict, modded: dict) -> dict:
    """
    {key: {field: modded_value}} for every field that differs.

    Keys only present in the modded side are returned in full - that's a
    row the mod added (OverrideEntryData allows this), so every field of it
    is deliberate.
    """
    edits: dict = {}
    for key, mod_values in modded.items():
        base_values = vanilla.get(key)
        if base_values is None:
            changed = dict(mod_values)
        else:
            changed = {
                name: value for name, value in mod_values.items()
                if name in base_values and base_values[name] != value
            }
        if changed:
            edits[key] = changed
    return edits


def _diff_per_language(vanilla_sqlite: Path, modded_sqlite: Path, reader, languages: list) -> dict:
    """
    Runs `reader` over both databases for each language, skipping any
    language whose table is missing from either side - a mod that only
    ships English shouldn't fail to open, it just has nothing to recover
    for the other languages.
    """
    result: dict = {}
    for language in languages:
        try:
            base = _values_by_key(reader(vanilla_sqlite, language))
            mod = _values_by_key(reader(modded_sqlite, language))
        except (ValueError, sqlite3.Error):
            continue
        edits = _diff_values(base, mod)
        if edits:
            result[language] = edits
    return result


def _diff_override_action(vanilla_sqlite: Path, modded_sqlite: Path) -> dict:
    """
    OverrideAbilityActionData, whose record shape differs from the rest
    (two packed flag columns plus scalars). Flags are reported per group
    rather than per column, matching the granularity the Abilities tab
    edits at and what write_override_action_edits expects.
    """
    try:
        base_records = {r.key: r for r in read_override_action_table(vanilla_sqlite)}
        mod_records = {r.key: r for r in read_override_action_table(modded_sqlite)}
    except (ValueError, sqlite3.Error):
        return {}

    edits: dict = {}
    for key, mod in mod_records.items():
        base = base_records.get(key)
        changed: dict = {}
        for name, value in mod.scalars.items():
            if base is None or base.scalars.get(name) != value:
                changed[name] = value
        for group_index in range(4):
            mod_group = mod.flag_group_value(group_index)
            base_group = base.flag_group_value(group_index) if base else c.OVERRIDE_NOT_SET
            if mod_group != base_group:
                changed[f"FlagsGroup{group_index}"] = mod_group
        if changed:
            edits[key] = changed
    return edits


def _diff_entries(vanilla_sqlite: Path, modded_sqlite: Path):
    """
    OverrideEntryData, keyed by the (Key, Key2) pair the Encounters tab
    uses. Returns (edits, rekeys, dropped).

    This one can't be a plain per-row diff, because the mod's row set is
    itself part of what the author changed. Rows cannot be added in a way
    the game picks up, so the way a mod gets an encounter/unit slot the
    game doesn't have is to *move* a row it doesn't care about - which
    shows up here as one address disappearing and another appearing.
    Zodi's Dark Knight Expansion does exactly this: ten rows moved to
    (95, 0..9), ten vanilla addresses vacated, total unchanged at 516.

    Pairing which vacated address became which new one is NOT recoverable -
    a .nxd stores only final rows, no history - so vacated and new
    addresses are paired in sorted order. That is arbitrary, and the UI
    says so. It is also harmless: each new row's edits are diffed against
    the vanilla row it is paired with, so applying rekey + edits
    reconstructs the mod's row byte-for-byte whichever way they pair up.

    Anything left unpaired is real: surplus new addresses are genuine
    additions (no origin row), surplus vacated addresses are genuine
    deletions, reported as `dropped` so export can honour them instead of
    quietly restoring them from vanilla.
    """
    try:
        base = {(r.key, r.key2): r.values for r in read_override_entry_table(vanilla_sqlite)}
        mod = {(r.key, r.key2): r.values for r in read_override_entry_table(modded_sqlite)}
    except (ValueError, sqlite3.Error):
        return {}, {}, []

    vacated = sorted(set(base) - set(mod))
    appeared = sorted(set(mod) - set(base))

    rekeys = {}
    for origin, destination in zip(vacated, appeared):
        rekeys[origin] = destination
    dropped = vacated[len(rekeys):]

    # Rows present at the same address in both: an ordinary field diff.
    #
    # BOTH sides have to be restricted to the shared addresses. Passing the
    # full modded dict here emitted every moved row a second time, as a
    # phantom "added row" keyed by its destination - on top of the
    # rekey-derived edit keyed by its origin. The written bytes came out
    # identical either way, so the round-trip test passed; what gave it
    # away was the tab reporting 20 edited rows for a mod that changes 10.
    # It was also a real latent bug: translate_entry_edits would map the
    # origin-keyed entry onto the same address as the destination-keyed
    # one, leaving dict ordering to decide which survived.
    shared = sorted(set(base) & set(mod))
    edits = _diff_values(
        {address: base[address] for address in shared},
        {address: mod[address] for address in shared},
    )

    # Moved rows: diff the mod's row against the vanilla row it was made
    # from, so re-export reproduces it exactly.
    for origin, destination in rekeys.items():
        changed = {
            name: value for name, value in mod[destination].items()
            if base[origin].get(name) != value
        }
        if changed:
            edits[origin] = changed

    # Genuinely new addresses with no origin to move - carried as full-row
    # edits, which write_override_entry_edits will INSERT.
    for address in appeared[len(rekeys):]:
        edits[address] = dict(mod[address])

    return edits, rekeys, dropped


@dataclass
class RecoveredNxdEdits:
    """Everything a mod's .nxd files turned out to have changed."""
    ability_edits: dict = field(default_factory=dict)
    override_action_edits: dict = field(default_factory=dict)
    item_edits: dict = field(default_factory=dict)
    chara_name_edits: dict = field(default_factory=dict)
    entry_edits: dict = field(default_factory=dict)
    poach_edits: dict = field(default_factory=dict)
    # Encounter rows the mod moved to a different (Key, Key2), and rows it
    # removed outright - both part of what the author changed, not
    # incidental. See _diff_entries.
    entry_rekeys: dict = field(default_factory=dict)
    entry_dropped: list = field(default_factory=list)

    def is_empty(self) -> bool:
        return not any((
            self.ability_edits, self.override_action_edits, self.item_edits,
            self.chara_name_edits, self.entry_edits, self.poach_edits,
            self.entry_rekeys, self.entry_dropped,
        ))

    def summary(self) -> str:
        """Plain-language counts, for telling the user what came back."""
        parts = []
        ability_count = sum(len(rows) for rows in self.ability_edits.values())
        if ability_count:
            parts.append(f"{ability_count} ability text row(s)")
        if self.override_action_edits:
            parts.append(f"{len(self.override_action_edits)} ability stat override(s)")
        item_count = sum(len(rows) for rows in self.item_edits.values())
        if item_count:
            parts.append(f"{item_count} item text row(s)")
        name_count = sum(len(rows) for rows in self.chara_name_edits.values())
        if name_count:
            parts.append(f"{name_count} unit name(s)")
        if self.entry_edits:
            parts.append(f"{len(self.entry_edits)} encounter entry/entries")
        if self.entry_rekeys:
            parts.append(f"{len(self.entry_rekeys)} moved encounter row(s)")
        if self.entry_dropped:
            parts.append(f"{len(self.entry_dropped)} removed encounter row(s)")
        poach_count = sum(len(rows) for rows in self.poach_edits.values())
        if poach_count:
            parts.append(f"{poach_count} poaching row(s)")
        return ", ".join(parts)


def recover_edits_from_sqlite(vanilla_sqlite: Path, modded_sqlite: Path) -> RecoveredNxdEdits:
    """
    Diffs an already-converted modded database against the vanilla one and
    returns edits in exactly the shapes the editor tabs and the write_*
    functions use, so recovered edits are indistinguishable from ones typed
    in by hand and re-export cleanly.
    """
    languages = list(c.NXD_LANGUAGES)
    result = RecoveredNxdEdits(
        ability_edits=_diff_per_language(vanilla_sqlite, modded_sqlite, read_ability_table, languages),
        override_action_edits=_diff_override_action(vanilla_sqlite, modded_sqlite),
        item_edits=_diff_per_language(vanilla_sqlite, modded_sqlite, read_item_table, languages),
        chara_name_edits=_diff_per_language(vanilla_sqlite, modded_sqlite, read_charaname_table, languages),
        poach_edits=_diff_per_language(vanilla_sqlite, modded_sqlite, read_poach_table, languages),
    )
    result.entry_edits, result.entry_rekeys, result.entry_dropped = _diff_entries(
        vanilla_sqlite, modded_sqlite
    )
    return result


def write_unmodelled_table_edits(sqlite_path: Path, table: str, edits: dict) -> int:
    """
    Applies changes to a table this tool has no typed reader for.

    Used by the Game Updates page's Rebase option, which takes the game's
    current table and puts the author's own changes back on top. There is no
    schema knowledge here on purpose: the columns come from the rows being
    written, and the keys from whatever the table's key columns are, so this
    works for any table the working database happens to hold.

    `edits` is {key tuple: {column: value}}. Returns the number of rows
    actually updated - a caller can compare that against what it asked for
    to notice rows the update removed.
    """
    if not edits:
        return 0
    con = sqlite3.connect(sqlite_path)
    try:
        columns = [row[1] for row in con.execute(f'PRAGMA table_info("{table}")')]
        if not columns:
            return 0
        key_columns = [name for name in ("Key", "Key2") if name in columns] or columns[:1]
        updated = 0
        for key, fields in edits.items():
            values = [value for name, value in fields.items() if name in columns]
            names = [name for name in fields if name in columns]
            if not names:
                continue
            assignments = ", ".join(f'"{name}" = ?' for name in names)
            where = " AND ".join(f'"{name}" = ?' for name in key_columns)
            key_values = list(key) if isinstance(key, tuple) else [key]
            if len(key_values) != len(key_columns):
                continue
            cursor = con.execute(
                f'UPDATE "{table}" SET {assignments} WHERE {where}',
                values + key_values,
            )
            updated += cursor.rowcount
        con.commit()
        return updated
    finally:
        con.close()


def import_tables_from(target_sqlite: Path, source_sqlite: Path, tables: list) -> list:
    """
    Copies whole tables from one converted database into another.

    Used to top up an export's staged database with game tables this tool
    doesn't normally convert, so a mod's `uibuttonguide.nxd` can be merged
    onto the game's current copy rather than only kept whole or dropped.

    Copies the game's version wholesale rather than trying to reconcile two
    schemas: the source here is always the same game the staged database
    came from, so the columns match by construction, and a mismatch means
    something is wrong enough that guessing would be worse than failing.

    Returns the tables actually imported.
    """
    if not tables:
        return []
    con = sqlite3.connect(target_sqlite)
    imported = []
    try:
        con.execute("ATTACH DATABASE ? AS source", (str(source_sqlite),))
        available = {
            row[0] for row in con.execute(
                "SELECT name FROM source.sqlite_master WHERE type='table'")
        }
        for table in tables:
            if table not in available:
                continue
            try:
                con.execute(f'DROP TABLE IF EXISTS main."{table}"')
                con.execute(f'CREATE TABLE main."{table}" AS SELECT * FROM source."{table}"')
                imported.append(table)
            except sqlite3.Error:
                continue
        con.commit()
    except sqlite3.Error:
        return imported
    finally:
        try:
            con.execute("DETACH DATABASE source")
        except sqlite3.Error:
            pass
        con.close()
    return imported


def tables_missing_from(sqlite_path: Path, tables: list) -> list:
    """Which of `tables` a database doesn't have."""
    if not tables:
        return []
    try:
        con = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
    except sqlite3.Error:
        return list(tables)
    try:
        present = {
            row[0].lower() for row in
            con.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    except sqlite3.Error:
        return list(tables)
    finally:
        con.close()
    return [name for name in tables if name.lower() not in present]
