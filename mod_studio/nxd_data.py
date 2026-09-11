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
import re
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


# The columns a name can actually be in, in the order worth trying.
#
# `Name` is not always the one that holds it. In `Item-<lang>` and
# `PoachItem-<lang>`, Japanese, Korean and both Chinese tables leave `Name`
# null for EVERY row and carry the name in `NameSingular` - 261 of 261 in
# `Item-ja` and `Item-ko` on a real 1.5.2 conversion. English and French
# populate both, which is why this went unnoticed: the language everyone
# develops in is the one that works.
#
# Reading `Name` alone made all four of those languages list every item and
# every carcass as "(unnamed)", in both interfaces.
NAME_FIELDS = ("Name", "NameSingular", "Name2", "NamePlural")


def record_name(values: dict) -> str:
    """The name from whichever of `NAME_FIELDS` actually holds one."""
    for field in NAME_FIELDS:
        text = (values.get(field) or "").strip()
        if text:
            return text
    return ""


def _display_name(key: int, values: dict, width: int) -> str:
    name = record_name(values)
    return f"{key:0{width}d} - {name}" if name else f"{key:0{width}d} - (unnamed)"


@dataclass
class AbilityRecord:
    """One row of a per-language Ability-xx table."""
    key: int
    values: dict = field(default_factory=dict)  # field name -> raw value (as read from sqlite)

    @property
    def display_name(self) -> str:
        return _display_name(self.key, self.values, 4)

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
        return _display_name(self.key, self.values, 3)


@dataclass
class CharaNameRecord:
    """One row of a per-language CharaName-xx table - same simple shape as ItemRecord."""
    key: int
    values: dict = field(default_factory=dict)

    @property
    def display_name(self) -> str:
        return _display_name(self.key, self.values, 3)


@dataclass
class JobTextRecord:
    """
    One row of a per-language Job-xx table: the job's NAME and DESCRIPTION.

    Named `JobTextRecord`, not `JobRecord`, because `xml_io.JobRecord`
    already exists and is a different table - JobData.xml's stats. Both are
    called Job, they share zero column names, and neither is the schema for
    the other. Two classes called JobRecord in one codebase is how that
    distinction gets lost.
    """
    key: int
    values: dict = field(default_factory=dict)

    @property
    def display_name(self) -> str:
        return _display_name(self.key, self.values, 3)


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
        return _display_name(self.key, self.values, 3)


# ===========================================================================
# The per-language nxd table registry
# ===========================================================================
# Every `.nxd` table that exists once per language has the same shape: read
# every row of `<Prefix>-<lang>`, hand back {key: {field: value}}, write
# back only the keys and fields that were edited, and re-export the tables
# whose language was touched. Four tables were implemented by copying that
# shape four times, and the copies had drifted into 20 files: each with its
# own `read_X_table`, `write_X_edits`, `tables_to_reexport_X`, its own
# `WizardState` fields, its own `edited_X_count`/`touched_X_languages`/
# `has_any_X_edits`, its own export wiring and its own review wiring.
#
# `item_xml_io.TableSpec` had already solved this for the reference/diff XML
# tables - one generic engine plus a spec per table - and adding
# MapTrapFormationData there cost a declaration rather than an edit to
# every caller. This is the same move for the nxd side.
#
# What is genuinely per-table turned out to be small: a table prefix, a
# filename stem, an optional column-name translation, an optional set of
# JSON-array columns, and how wide the ID is printed. Everything else was
# the same code with a different noun in it.
#
# ADDING A TABLE: declare it here and in constants.py, and give it a page.
# The export, the re-export list, the Mod Contents summary, opening an
# existing mod, the Game Updates review and the migration all iterate this
# registry and pick it up without being edited.

@dataclass
class JobCommandTextRecord:
    """
    One row of a per-language JobCommand-xx table: the command's NAME and
    DESCRIPTION. Named `...TextRecord` for the same reason as
    `JobTextRecord` - `xml_io.JobCommandRecord` already exists and holds
    the ability slots, which is a different table.
    """
    key: int
    values: dict = field(default_factory=dict)

    @property
    def display_name(self) -> str:
        return _display_name(self.key, self.values, 3)


@dataclass(frozen=True)
class NxdTableSpec:
    """Everything that differs between the per-language `.nxd` tables."""
    key: str                     # registry key; state uses f"{key}_records"/f"{key}_edits"
    label: str                   # what a person calls it: "Poaching", "Unit Names"
    table_prefix: str            # "PoachItem" -> table "PoachItem-en"
    nxd_stem: str                # "poachitem" -> file "poachitem.en.nxd"
    record_class: type           # the dataclass one row becomes
    summary_noun: str            # "poaching row(s)", for the open-mod summary
    id_width: int = 3            # zero-padding in display names
    array_fields: tuple = ()     # columns stored as JSON arrays (Abilities only)
    friendly_names: dict = field(default_factory=dict)  # raw column -> friendly (Poaching only)
    raw_names: dict = field(default_factory=dict)       # friendly -> raw column
    text_fields: tuple = ()      # never copied between languages - they are translations
    # Where WizardState keeps this table's rows and edits. Defaults to
    # f"{key}_records"/f"{key}_edits", which is what four of the five use.
    #
    # Job is why these are settable rather than derived. `state.job_records`
    # was already taken - by JobData.xml's reference rows, which the Jobs
    # tab has used since it was written - so a derived name would have
    # quietly redefined it. As a dataclass field, the second declaration
    # simply wins: `job_records` became a dict and the whole XML half of
    # the page would have been reading the wrong store.
    records_attr_override: str = ""
    edits_attr_override: str = ""
    #: Built from a layout rather than written by hand. Derived tables keep
    #: their stores in `WizardState.nxd_stores` and have no curated tab.
    derived: bool = False

    def table(self, language: str) -> str:
        return f"{self.table_prefix}-{language}"

    def filename(self, language: str) -> str:
        return f"{self.nxd_stem}.{language}.nxd"

    def all_filenames(self) -> list:
        return [self.filename(lang) for lang in c.NXD_LANGUAGES]

    @property
    def records_attr(self) -> str:
        return self.records_attr_override or f"{self.key}_records"

    @property
    def edits_attr(self) -> str:
        return self.edits_attr_override or f"{self.key}_edits"


ABILITY_NXD_SPEC = NxdTableSpec(
    key="ability", label="Abilities", table_prefix="Ability", nxd_stem="ability",
    record_class=AbilityRecord, summary_noun="ability text row(s)", id_width=4,
    array_fields=tuple(c.ABILITY_ARRAY_FIELDS),
    text_fields=("Name", "NameSingular", "NamePlural", "Name2", "Description", "Comment"),
)

ITEM_NXD_SPEC = NxdTableSpec(
    key="item", label="Items", table_prefix="Item", nxd_stem="item",
    record_class=ItemRecord, summary_noun="item text row(s)",
    text_fields=("Name", "NameSingular", "NamePlural", "Name2", "Description", "Comment"),
)

CHARA_NAME_NXD_SPEC = NxdTableSpec(
    key="chara_name", label="Unit Names", table_prefix="CharaName", nxd_stem="charaname",
    record_class=CharaNameRecord, summary_noun="unit name(s)",
    text_fields=("Name", "NameSingular", "NamePlural", "Name2", "Description", "Comment"),
)

POACH_NXD_SPEC = NxdTableSpec(
    key="poach", label="Poaching", table_prefix="PoachItem", nxd_stem="poachitem",
    record_class=PoachItemRecord, summary_noun="poaching row(s)",
    friendly_names=dict(c.POACH_FIELD_FRIENDLY_NAMES),
    raw_names=dict(c.POACH_FIELD_RAW_NAMES),
    text_fields=tuple(c.POACH_TEXT_FIELDS),
)

JOB_NXD_SPEC = NxdTableSpec(
    key="job", label="Jobs", table_prefix="Job", nxd_stem="job",
    record_class=JobTextRecord, summary_noun="job text row(s)",
    records_attr_override="job_text_records",
    edits_attr_override="job_text_edits",
    # Only the string columns. The numeric ones duplicate links JobData.xml
    # already owns - see constants.py's Job nxd section for why they are out.
    text_fields=tuple(c.JOB_NXD_TEXT_FIELDS),
)

# Order matters only for display; every consumer iterates it.
JOBCOMMAND_NXD_SPEC = NxdTableSpec(
    key="job_command", label="Job Commands",
    table_prefix="JobCommand", nxd_stem="jobcommand",
    record_class=JobCommandTextRecord, summary_noun="job command text row(s)",
    text_fields=tuple(c.JOBCOMMAND_NXD_TEXT_FIELDS),
    # `state.job_command_records` is already JobCommandData.xml's rows, the
    # same collision Job hit. Derived names would silently redefine it.
    records_attr_override="job_command_text_records",
    edits_attr_override="job_command_text_edits",
)

@dataclass
class DerivedNxdRecord:
    """
    One row of a per-language table that has no hand-written record class.

    Identical in shape to `JobTextRecord`, `ItemRecord` and the rest -
    they are all a key and a bag of values, because `read_nxd_table` reads
    the columns out of the database and never consulted the class about
    what they should be. That is why deriving a spec costs no new class:
    there was never anything table-specific in them to derive.
    """
    key: int
    values: dict = field(default_factory=dict)

    @property
    def display_name(self) -> str:
        return record_name(self.values)


def _derived_key(table_name: str) -> str:
    """
    `UIStatusEffect` -> `ui_status_effect`, for the registry key.

    Prefixed on collision with a curated key rather than replacing it -
    `job` and `item` are already taken by hand-written specs that carry
    labels, notes and friendly column names no layout knows about.
    """
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", table_name)
    spaced = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "_", spaced)
    return spaced.lower()


def spec_from_layout(layout) -> NxdTableSpec:
    """
    An `NxdTableSpec` built entirely from one of Nenkai's `.layout` files.

    The layout already states everything the spec's identity needs: the
    sqlite prefix (`table_name`), the filename stem (that name lowered),
    whether the game ships one file per language (`_Localized`), and every
    column with its type - which is where `text_fields` comes from, since
    a string column of a localized table IS a translation.

    Verified against all six hand-written specs before this was used:
    `table_prefix`, `nxd_stem`, `localized` and `text_fields` derive with
    no mismatch for every one of them. So the hand-written specs are not
    carrying schema the layout lacks; they are carrying PRESENTATION -
    a human label, a summary noun, friendly column names - which is why
    they still win where they exist.
    """
    key = _derived_key(layout.table_name)
    label = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", layout.table_name)
    return NxdTableSpec(
        key=key,
        label=label,
        table_prefix=layout.table_name,
        nxd_stem=layout.nxd_stem,
        record_class=DerivedNxdRecord,
        summary_noun=f"{label.lower()} row(s)",
        text_fields=layout.string_columns,
        # Derived tables keep their stores in `WizardState.nxd_stores`
        # rather than in a declared field per table. 53 localized layouts
        # exist; declaring 106 dataclass fields for them would be
        # unreadable, and a redeclared dataclass field does not raise - the
        # second silently wins, which is exactly how `job_records` once
        # turned from a list into a dict.
        derived=True,
    )


def _build_registry() -> dict:
    """
    Every per-language table Mod Studio knows about.

    Six are hand-written, because they have curated tabs and carry labels
    and notes no schema contains. The rest are derived from the bundled
    layouts, so a table the community adds support for arrives with a
    registered spec and no code change - which is the whole point, and was
    not true before: `jobcommand` was added to the registry and still went
    unmentioned on the Export page, because five call sites named their
    tables by hand.

    Curated wins on collision. A derived spec must never quietly replace
    one that has a label, friendly column names and a tab pointing at it.
    """
    registry = {spec.key: spec for spec in (
        ABILITY_NXD_SPEC, ITEM_NXD_SPEC, CHARA_NAME_NXD_SPEC,
        POACH_NXD_SPEC, JOB_NXD_SPEC, JOBCOMMAND_NXD_SPEC,
    )}
    curated_prefixes = {spec.table_prefix for spec in registry.values()}
    try:
        from . import nxd_layouts
        localized = nxd_layouts.localized_layouts()
    except Exception:                                         # noqa: BLE001
        # No layouts bundled is not a crash. It is the six curated tables
        # and nothing else - exactly what shipped before - rather than an
        # application that will not start.
        return registry
    for name in sorted(localized):
        if name in curated_prefixes:
            continue
        spec = spec_from_layout(localized[name])
        if spec.key in registry:
            continue
        registry[spec.key] = spec
    return registry


ALL_NXD_SPECS = _build_registry()

#: The six with curated tabs, for the places that legitimately mean those
#: and not all fifty-three - the Edit Game Data tabs, mostly.
CURATED_NXD_SPECS = {
    key: spec for key, spec in ALL_NXD_SPECS.items() if not spec.derived
}


def effective_values(state, key: str, row_key: int, language: str) -> dict:
    """
    A row as it stands RIGHT NOW: the game's values with any pending edit
    laid over the top.

    Nothing has been exported at this point, so "what is this called" has
    two possible answers - what the game shipped, and what the modder has
    typed but not saved. Every page needs the second one, and before this
    each page answered it for itself:

      * the Abilities list had its own `_ability_label` that checked
        `ability_edits` first;
      * the Jobs list had no such check at all, so renaming a job left the
        list showing the old name until the tab was rebuilt;
      * `app.ability_choices()` called `resolve_ability_name(id, {})` with
        an EMPTY live-names dict, so Job Commands' 22 ability dropdowns
        showed the ORIGINAL name of an ability the modder had renamed.

    Three pages, three answers, two of them wrong.
    """
    base = {}
    for record in (state.nxd_records_for(key).get(language) or []):
        if record.key == row_key:
            base = dict(record.values)
            break
    base.update(state.nxd_edits_for(key).get(language, {}).get(row_key, {}))
    return base


def effective_name(state, key: str, row_key: int, language: str) -> str:
    """
    This row's name as it stands now, pending edits included.

    Goes through `record_name`, so the ja/ko/cs/ct tables that leave `Name`
    empty and put the name in `NameSingular` resolve correctly here too -
    a page doing its own `values["Name"]` lookup gets an empty string for
    four of the seven languages.
    """
    return record_name(effective_values(state, key, row_key, language))


def effective_names(state, key: str, language: str) -> dict:
    """
    {row key: name as it stands now} for a whole table, pending edits
    included. Rows with no name at all are omitted rather than given a
    placeholder, so callers can tell "unnamed" from "not in the table".
    """
    names = {}
    records = state.nxd_records_for(key).get(language) or []
    edits = state.nxd_edits_for(key).get(language, {})
    for record in records:
        values = dict(record.values)
        values.update(edits.get(record.key, {}))
        name = record_name(values)
        if name:
            names[record.key] = name
    # An edit to a row the loaded table does not contain still counts.
    for row_key, fields in edits.items():
        if row_key not in names:
            name = record_name(fields)
            if name:
                names[row_key] = name
    return names


def spec_for(key: str) -> NxdTableSpec:
    """The spec for a registry key, with a useful error rather than a KeyError."""
    try:
        return ALL_NXD_SPECS[key]
    except KeyError:
        raise KeyError(
            f"No per-language nxd table registered as {key!r}. "
            f"Known: {', '.join(sorted(ALL_NXD_SPECS))}"
        ) from None


def nxd_spec_keys() -> list:
    return list(ALL_NXD_SPECS)


def read_nxd_table(sqlite_path: Path, key: str, language: str) -> list:
    """
    One language of one registered table.

    Replaces `read_ability_table`/`read_item_table`/`read_charaname_table`/
    `read_poach_table`, which were the same function four times over.
    """
    spec = spec_for(key)
    table = spec.table(language)
    con = sqlite3.connect(str(sqlite_path))
    try:
        if not _table_exists(con, table):
            raise ValueError(
                f"No '{table}' table in this database - was {spec.filename(language)} "
                f"included when it was converted?"
            )
        con.row_factory = sqlite3.Row
        cur = con.execute(f'SELECT * FROM "{table}" ORDER BY Key')
        records = []
        for row in cur.fetchall():
            values = {}
            for column in row.keys():
                if column == "Key":
                    continue
                value = row[column]
                if column in spec.array_fields and value:
                    value = json.loads(value)
                values[spec.friendly_names.get(column, column)] = value
            records.append(spec.record_class(key=row["Key"], values=values))
        return records
    finally:
        con.close()


def write_nxd_edits(sqlite_path: Path, key: str, language: str, edits: dict) -> None:
    """
    Applies {key: {field: value}} to one language of one registered table,
    leaving every other row and column exactly as FF16Tools produced it.
    """
    if not edits:
        return
    spec = spec_for(key)
    table = spec.table(language)
    con = sqlite3.connect(str(sqlite_path))
    try:
        for row_key, fields in edits.items():
            if not fields:
                continue
            columns, params = [], []
            for name, value in fields.items():
                columns.append(spec.raw_names.get(name, name))
                if name in spec.array_fields:
                    value = json.dumps(value, separators=(",", ":"))
                params.append(value)
            set_clause = ", ".join(f'"{name}" = ?' for name in columns)
            params.append(row_key)
            con.execute(f'UPDATE "{table}" SET {set_clause} WHERE Key = ?', params)
        con.commit()
    finally:
        con.close()


def tables_to_reexport_for(key: str, touched_languages) -> list:
    """The sqlite tables one registered table's touched languages need converting back."""
    spec = spec_for(key)
    return [spec.table(lang) for lang in touched_languages]


def filenames_for(key: str, touched_languages) -> list:
    """The `.nxd` files those tables become."""
    spec = spec_for(key)
    return [spec.filename(lang) for lang in touched_languages]


# ---------------------------------------------------------------------------
# The four original entry points, now one line each.
#
# Kept because 20 files and 38 suites call them by name, and because
# `read_poach_table(db, "en")` reads better at a call site than
# `read_nxd_table(db, "poach", "en")`. They are delegates, not copies - the
# behaviour lives in one place above.
# ---------------------------------------------------------------------------

def read_ability_table(sqlite_path: Path, language: str) -> list[AbilityRecord]:
    return read_nxd_table(sqlite_path, "ability", language)


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
    write_nxd_edits(sqlite_path, "ability", language, edits)


def read_item_table(sqlite_path: Path, language: str) -> list:
    return read_nxd_table(sqlite_path, "item", language)


def write_item_edits(sqlite_path: Path, language: str, edits: dict) -> None:
    """edits: {key: {field_name: new_raw_value}}. Only touches given keys/fields."""
    write_nxd_edits(sqlite_path, "item", language, edits)


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


def read_charaname_table(sqlite_path: Path, language: str) -> list:
    return read_nxd_table(sqlite_path, "chara_name", language)


def write_charaname_edits(sqlite_path: Path, language: str, edits: dict) -> None:
    """edits: {key: {field_name: new_raw_value}}. Only touches given keys/fields."""
    write_nxd_edits(sqlite_path, "chara_name", language, edits)


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


def read_poach_table(sqlite_path: Path, language: str) -> list:
    """
    Reads PoachItem-<language>, translating FF16Tools' raw "UnknownXX"
    column names to this tool's friendly field names (Name/Description/
    ProducedItemId/etc.) via the spec's `friendly_names` - see
    constants.POACH_FIELD_FRIENDLY_NAMES for why that translation exists.
    """
    return read_nxd_table(sqlite_path, "poach", language)


def write_poach_edits(sqlite_path: Path, language: str, edits: dict) -> None:
    """
    edits: {key: {friendly_field_name: new_raw_value}}. Friendly names are
    translated back to FF16Tools' real "UnknownXX" column names by the
    spec's `raw_names` before the UPDATE - see read_poach_table.
    """
    write_nxd_edits(sqlite_path, "poach", language, edits)


def tables_to_reexport_poach(touched_languages: list) -> list:
    """Same idea as tables_to_reexport_items, for PoachItem-xx (no shared-table equivalent to add)."""
    return tables_to_reexport_for("poach", touched_languages)


def read_job_table(sqlite_path: Path, language: str) -> list:
    """One language of Job-xx: the job's name and description as the player reads them."""
    return read_nxd_table(sqlite_path, "job", language)


def write_job_edits(sqlite_path: Path, language: str, edits: dict) -> None:
    """edits: {job_id: {field_name: new_raw_value}}. Only touches given keys/fields."""
    write_nxd_edits(sqlite_path, "job", language, edits)


def tables_to_reexport_job(touched_languages: list) -> list:
    return tables_to_reexport_for("job", touched_languages)


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
    """
    Everything a mod's .nxd files turned out to have changed.

    The per-language stores are created from the registry in
    `__post_init__` rather than declared here one by one. They were
    declared by hand, and adding `job_command` to the registry made
    `edits_for("job_command")` raise `AttributeError` from four different
    call sites - the registry knew about the table and this class did not.
    That is precisely the coupling the registry exists to remove, so the
    fix is for this class to stop having its own list rather than for the
    list to gain another entry.
    """
    override_action_edits: dict = field(default_factory=dict)
    entry_edits: dict = field(default_factory=dict)
    # One per registered table. Declared rather than generated because a
    # dataclass only accepts keywords for fields it declares, and
    # `migration` and several suites build one as
    # `RecoveredNxdEdits(ability_edits=...)`. `__post_init__` below creates
    # any that are missing, so forgetting one here degrades to "no keyword
    # support" instead of `AttributeError` from every call site.
    ability_edits: dict = field(default_factory=dict)
    item_edits: dict = field(default_factory=dict)
    chara_name_edits: dict = field(default_factory=dict)
    poach_edits: dict = field(default_factory=dict)
    job_text_edits: dict = field(default_factory=dict)
    job_command_text_edits: dict = field(default_factory=dict)
    # Encounter rows the mod moved to a different (Key, Key2), and rows it
    # removed outright - both part of what the author changed, not
    # incidental. See _diff_entries.
    entry_rekeys: dict = field(default_factory=dict)
    entry_dropped: list = field(default_factory=list)

    def __post_init__(self):
        # One store per registered table, named by the spec. Set only if
        # absent, so a caller passing `ability_edits=` as a keyword still
        # wins - several tests and `migration` build one that way.
        for spec in ALL_NXD_SPECS.values():
            if not hasattr(self, spec.edits_attr):
                setattr(self, spec.edits_attr, {})

    def edits_for(self, key: str) -> dict:
        """
        One registered table's recovered edits, looked up by registry key.

        Resolved with `getattr` at call time rather than held in a dict
        built in `__init__`. A dict of references would keep pointing at
        the original objects after any of these attributes was reassigned,
        which is exactly the orphaned-dict trap `clear_opened_mod_content`
        already cost this project once.
        """
        return getattr(self, spec_for(key).edits_attr)

    def set_edits_for(self, key: str, value: dict) -> None:
        setattr(self, spec_for(key).edits_attr, value)

    def is_empty(self) -> bool:
        return not any(
            [self.edits_for(key) for key in ALL_NXD_SPECS]
            + [self.override_action_edits, self.entry_edits,
               self.entry_rekeys, self.entry_dropped]
        )

    def summary(self) -> str:
        """
        Plain-language counts, for telling the user what came back.

        Registry-driven, so a newly registered table is reported without
        this method being edited. It used to name each table by hand, which
        is how a table could be recovered correctly and then not mentioned.
        """
        parts = []
        for key, spec in ALL_NXD_SPECS.items():
            count = sum(len(rows) for rows in self.edits_for(key).values())
            if count:
                parts.append(f"{count} {spec.summary_noun}")
        if self.override_action_edits:
            parts.append(f"{len(self.override_action_edits)} ability stat override(s)")
        if self.entry_edits:
            parts.append(f"{len(self.entry_edits)} encounter entry/entries")
        if self.entry_rekeys:
            parts.append(f"{len(self.entry_rekeys)} moved encounter row(s)")
        if self.entry_dropped:
            parts.append(f"{len(self.entry_dropped)} removed encounter row(s)")
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
        override_action_edits=_diff_override_action(vanilla_sqlite, modded_sqlite),
    )
    # Every registered per-language table, rather than five named calls.
    # A table added to the registry is recovered from an opened mod without
    # this function being touched.
    for key in ALL_NXD_SPECS:
        result.set_edits_for(key, _diff_per_language(
            vanilla_sqlite, modded_sqlite,
            lambda db, lang, _k=key: read_nxd_table(db, _k, lang),
            languages))
    result.entry_edits, result.entry_rekeys, result.entry_dropped = _diff_entries(
        vanilla_sqlite, modded_sqlite
    )
    return result


def list_all_tables(sqlite_path: Path) -> list:
    """
    Every real table in a converted database, in name order.

    Skips SQLite's own internal tables and the converter's `_uniontypes`
    bookkeeping, which are not game data and cannot be edited.
    """
    con = sqlite3.connect(str(sqlite_path))
    try:
        return sorted(
            name for (name,) in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")
            if not name.startswith("_") and not name.startswith("sqlite_"))
    finally:
        con.close()


def table_shape(sqlite_path: Path, table: str) -> dict:
    """
    What a table looks like, without knowing anything about it in advance:
    its columns, which of those are its key, and how many rows it has.

    This is the counterpart to `write_unmodelled_table_edits`, which has
    deliberately had no schema knowledge since it was written for Rebase.
    Reading needed the same treatment before any table could be shown.
    """
    con = sqlite3.connect(str(sqlite_path))
    try:
        info = list(con.execute(f'PRAGMA table_info("{table}")'))
        columns = [row[1] for row in info]
        if not columns:
            return {"columns": [], "keys": [], "rows": 0}
        keys = [name for name in ("Key", "Key2") if name in columns]
        if not keys:
            # Some tables key on their first column instead. Same rule
            # `write_unmodelled_table_edits` uses, so reads and writes
            # cannot disagree about what identifies a row.
            keys = columns[:1]
        count = con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        return {"columns": columns, "keys": keys, "rows": count}
    finally:
        con.close()


@dataclass
class TextHit:
    """One row whose text matched a search."""
    table: str                   # as it appears in the database, e.g. "Job-de"
    base_table: str              # the same table without its language, "Job"
    language: str                # "de", or "" for a table shipped once
    key: object                  # scalar, or tuple for a compound key - the
                                 # SAME shape read_any_table returns, so a hit
                                 # can be handed to an editor untranslated
    column: str
    value: str

    @property
    def registered(self) -> bool:
        """Whether the table registry models this table."""
        return self.base_table in {spec.table_prefix
                                   for spec in ALL_NXD_SPECS.values()}


def searchable_text_columns(sqlite_path: Path) -> dict:
    """
    Every table in the database mapped to the columns of it that hold text.

    Taken from the bundled `.layout` files, which state each column's type,
    rather than from SQLite's own declared types. FF16Tools writes most
    columns untyped, so `PRAGMA table_info` reports an empty type for them
    and a type-based guess would either scan every column of every table or
    miss real text - measured on the shipped 1.5.2 database, the layouts
    name **1138 string columns across 493 tables**.

    A table with no bundled layout falls back to scanning every column that
    SQLite says is TEXT or untyped. That is deliberately the loose end
    rather than the tight one: the point of this search is finding text
    somebody has no idea the location of, so a table nobody has modelled is
    exactly the case that must not be silently skipped. On 1.5.2 this
    affects one table (`_uniontypes`, the converter's own bookkeeping),
    which `list_all_tables` already excludes.
    """
    con = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
    try:
        return {table: columns
                for table, (columns, _keys) in _text_shape(con).items()}
    finally:
        con.close()


def _text_shape(con) -> dict:
    """
    `{table: (text columns, key columns)}` for every table, on ONE connection.

    Both halves are read in a single pass because both need
    `PRAGMA table_info` and the first version asked for it twice per table
    through helpers that each opened their own connection - 493 tables
    became roughly a thousand `sqlite3.connect` calls and turned a 40ms
    query into 1.3 seconds. The work was never the scanning.
    """
    from . import nxd_layouts

    found = {}
    tables = [name for (name,) in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")
        if not name.startswith("_") and not name.startswith("sqlite_")]
    for table in sorted(tables):
        info = list(con.execute(f'PRAGMA table_info("{table}")'))
        if not info:
            continue
        names = [row[1] for row in info]
        base, _language = split_language_suffix(table)
        layout = nxd_layouts.layout_for(base)
        if layout is not None:
            # Intersected with what the database actually has. A layout
            # naming a column the converter did not write would otherwise
            # put that name into the SQL and fail the whole table.
            columns = [n for n in layout.string_columns if n in names]
        else:
            columns = [row[1] for row in info
                       if (row[2] or "").upper() in ("TEXT", "")]
        if not columns:
            continue
        # The same key rule `table_shape` and `write_unmodelled_table_edits`
        # use, so a hit's key is the one an editor will look the row up by.
        keys = [n for n in ("Key", "Key2") if n in names] or names[:1]
        found[table] = (columns, keys)
    return found


def split_language_suffix(table: str) -> tuple:
    """
    `Job-de` -> `("Job", "de")`, `OverrideEntryData` -> `(..., "")`.

    Split against the known language list rather than on the last hyphen.
    `Novel04-en` is a language variant and `Novel04` is not, but plenty of
    table names contain a hyphen that is not a language - the same reason
    `DataBrowserPage._registered_target` resolves against the registry
    instead of splitting.
    """
    if "-" in table:
        head, tail = table.rsplit("-", 1)
        if tail in c.NXD_LANGUAGES:
            return head, tail
    return table, ""


def like_pattern(needle: str) -> str:
    """
    A `LIKE` pattern matching `needle` literally.

    `%` and `_` are LIKE's own wildcards, so an unescaped search for `100%`
    asks SQLite for "100 followed by anything" and a search for `_` asks for
    every non-empty string.

    **Be precise about what this buys, because it is not correctness.**
    `search_text` re-checks every candidate row in Python before recording a
    hit, so the results are right either way - removing this escaping does
    not change a single returned row, which a test comparing results cannot
    detect and one nearly failed to. What it buys is SELECTIVITY: without
    it, a needle containing `_` makes SQLite return most of the database for
    Python to throw away. Hence a separate function, so the escaping can be
    checked for what it is rather than through a result that does not depend
    on it.
    """
    escaped = (needle.replace("\\", "\\\\")
                     .replace("%", "\\%")
                     .replace("_", "\\_"))
    return f"%{escaped}%"


def search_text(sqlite_path: Path, needle: str, languages=None,
                limit: int = 500) -> list:
    """
    Every row in the database whose text contains `needle`.

    **Across all languages, not the user's own.** The tables are per
    language - `Job-en`, `Job-de`, `Job-ja` - so a person who types an
    English line and is shown only `Job-en` gets told where to change the
    text for English players and nothing else. Shipping a mod that way
    leaves it unchanged for everyone else, silently, which is the specific
    quiet mistake this whole feature exists to prevent.

    Matching is case-insensitive `LIKE` with the wildcards escaped, so a
    search for `100%` looks for a literal percent sign. `LIKE` is not
    case-insensitive for non-ASCII in SQLite's default collation, so a
    Japanese or Czech search is exact-case - which is correct for those
    scripts rather than a limitation, since neither has the case a fold
    would be folding.

    Returns at most `limit` hits. The cap is a display concern rather than
    a cost one - measured on the real 1.5.2 database, scanning every text
    column of all 493 tables takes about 0.04s, so this runs on the GUI
    thread deliberately: a background worker for a 40ms query would add a
    spinner, a cancel path and a race for nothing.
    """
    needle = (needle or "").strip()
    if not needle:
        return []
    wanted = set(languages) if languages else None
    pattern = like_pattern(needle)

    hits = []
    con = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
    try:
        shapes = _text_shape(con)
        con.row_factory = sqlite3.Row
        for table, (columns, keys) in shapes.items():
            base, language = split_language_suffix(table)
            if wanted is not None and language and language not in wanted:
                continue
            if not keys:
                continue
            where = " OR ".join(f'"{col}" LIKE ? ESCAPE \'\\\'' for col in columns)
            sql = f'SELECT * FROM "{table}" WHERE {where}'
            try:
                rows = con.execute(sql, [pattern] * len(columns)).fetchall()
            except sqlite3.Error:
                # One unreadable table must not end the search. A person
                # searching for a line of text cannot act on a traceback,
                # and the other 492 tables still have their answer.
                continue
            for row in rows:
                values = {name: row[name] for name in row.keys()}
                key_values = tuple(values[name] for name in keys)
                key = key_values[0] if len(key_values) == 1 else key_values
                for col in columns:
                    text = values.get(col)
                    if isinstance(text, str) and needle.lower() in text.lower():
                        hits.append(TextHit(
                            table=table, base_table=base, language=language,
                            key=key, column=col, value=text))
                        if len(hits) >= limit:
                            return hits
        return hits
    finally:
        con.close()


def read_any_table(sqlite_path: Path, table: str, limit: int = 0) -> list:
    """
    Every row of any table as [(key, {column: value})].

    `key` is a scalar for a single-key table and a tuple for a compound
    one, matching exactly what `write_unmodelled_table_edits` expects back,
    so a row read here can be written without translation.

    Values are returned raw. No JSON decoding, no friendly column names,
    no flag unpacking - the typed readers above do those things because
    they know which columns need them, and guessing here would corrupt a
    table nobody has looked at yet.
    """
    shape = table_shape(sqlite_path, table)
    if not shape["columns"]:
        return []
    keys = shape["keys"]
    con = sqlite3.connect(str(sqlite_path))
    try:
        con.row_factory = sqlite3.Row
        order = ", ".join(f'"{name}"' for name in keys)
        sql = f'SELECT * FROM "{table}" ORDER BY {order}'
        if limit:
            sql += f" LIMIT {int(limit)}"
        out = []
        for row in con.execute(sql):
            values = {name: row[name] for name in row.keys()}
            key_values = tuple(values[name] for name in keys)
            out.append((key_values[0] if len(key_values) == 1 else key_values,
                        values))
        return out
    finally:
        con.close()


def recover_unmodelled_edits(vanilla_sqlite: Path, mod_sqlite: Path) -> dict:
    """
    Everything a mod changed in tables that have no typed reader.

    `recover_edits_from_sqlite` covers the registered per-language tables
    and the two shared ones. Everything else a mod ships - and a mod can
    ship any of the 562 - was read by nothing, so opening that mod
    recovered its ability names and silently dropped its changes to, say,
    `JobType`. The All Game Data tab can now CREATE those edits, which
    made the gap worse: the tool could write a mod it could not read back.

    Returns {table: {key: {column: value}}}, in exactly the shape
    `write_unmodelled_table_edits` expects and `state.unmodelled_table_edits`
    holds.

    Only tables present in BOTH databases are compared. A table the mod
    ships that vanilla does not have is not an edit, it is a new table, and
    this tool has no way to describe that.
    """
    known = {spec.table(lang) for spec in ALL_NXD_SPECS.values()
             for lang in c.NXD_LANGUAGES}
    known |= {c.NXD_OVERRIDE_ACTION_TABLE, c.NXD_OVERRIDE_ENTRY_TABLE}

    vanilla_tables = set(list_all_tables(vanilla_sqlite))
    found = {}
    for table in list_all_tables(mod_sqlite):
        if table in known or table not in vanilla_tables:
            continue
        base = dict(read_any_table(vanilla_sqlite, table))
        theirs = dict(read_any_table(mod_sqlite, table))
        changed = {}
        for key, values in theirs.items():
            original = base.get(key)
            if original is None:
                continue
            differing = {name: value for name, value in values.items()
                         if name in original and original[name] != value}
            if differing:
                changed[key] = differing
        if changed:
            found[table] = changed
    return found


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
