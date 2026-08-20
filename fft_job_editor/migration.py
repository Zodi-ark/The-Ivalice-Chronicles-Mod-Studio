"""
Re-expressing a mod's changes on top of a newer version of the game.

The problem this solves: a `.nxd` file in a mod replaces the game's copy
wholesale. So a mod built against an older game version doesn't just miss
out on what the update changed - it actively reverts it, silently, for
every row in every table it ships. Zodi's own published Dark Knight
Expansion demonstrates this: its `ui.*.nxd` carries `v1.5.1`, so installing
it on 1.5.2 makes the game report the older version.

The shape of the fix is a three-way merge, and the vocabulary is borrowed
from version control on purpose because it's well understood:

    base    the vanilla game the mod was built against
    ours    the mod
    theirs  the vanilla game as it is now

`nxd_data.recover_edits_from_sqlite(base, mod)` already gives us "ours" -
the mod's intent, per field. Running the *same* function on (base, theirs)
gives what the update changed. Comparing those two answers per field is
the whole job.

One trap worth naming, because it cost a debugging round to find:
`nxd_data._diff_entries` infers rekeys by pairing vacated addresses against
newly-appeared ones. That is right for a *mod* - moving a row is how a mod
gets an encounter slot the game doesn't have - and wrong for a *patch*,
which simply adds and removes rows. Feeding a patch through that function
reads an added row as a move. So the vanilla-to-vanilla comparison uses
`diff_vanilla_entries` below, which does a plain structural diff with the
rekey inference switched off.

What this module deliberately does NOT do: decide anything on the author's
behalf where the answer is a judgement call. Clean carries happen silently
because there is nothing to decide; every conflict is surfaced.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import constants as c
from . import nxd_data

# ---------------------------------------------------------------------------
# Version detection
# ---------------------------------------------------------------------------

# The game stores its own version string as an ordinary UI string. Confirmed
# against three real converted databases (1.5.0, 1.5.1, 1.5.2): key 3737 in
# every `UI-<lang>` table holds "v1.5.0"/"v1.5.1"/"v1.5.2", identically
# across all seven languages. Zodi found this; it saves us inventing a
# version-detection scheme and, better, it works retroactively on mods that
# shipped long before this feature existed.
VERSION_UI_KEY = 3737


def read_game_version(sqlite_path: Path) -> Optional[str]:
    """
    The game version a converted database came from, e.g. "v1.5.2".

    Tries every language's UI table rather than just English, because a mod
    is free to ship only some of them - a mod with just `ui.de.nxd` is
    still perfectly datable. Returns None when no UI table is present at
    all, which is the common case for a mod that doesn't touch UI strings.
    """
    try:
        con = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
    except sqlite3.Error:
        return None
    try:
        for language in c.NXD_LANGUAGES:
            table = f"UI-{language}"
            try:
                row = con.execute(
                    f'SELECT Text FROM "{table}" WHERE Key = ?', (VERSION_UI_KEY,)
                ).fetchone()
            except sqlite3.Error:
                continue          # table absent, or an older schema
            if row and row[0]:
                return str(row[0])
        return None
    finally:
        con.close()


# ModConfig.json's `PluginData` is a free-form dictionary and is the
# documented extension point - Reloaded-II's own dependency resolver writes
# into it, and Zodi's published mod already carries "GitHubRelease" and
# "GitHubDependencies" blocks there. It round-trips, and unlike a sidecar
# file it survives publishing: Reloaded-II excludes `.json` files when
# packaging a mod and only special-cases ModConfig.json itself, so a
# sidecar `ModStudio.json` would be stripped from every released zip.
#
# modconfig._apply_update_settings already establishes the convention of
# touching exactly one PluginData key and leaving every other tool's alone.
PLUGIN_DATA_KEY = "ModStudio"


@dataclass
class ModStamp:
    """What a mod records about the data it was built against."""
    game_version: str = ""
    # Reference-table versions (JobData.xml and friends), which ship with
    # Nenkai's mod loader and are versioned independently of the game - so
    # the game version alone doesn't date the XML side of a mod.
    table_versions: dict = field(default_factory=dict)
    # Whether the vanilla database behind this mod was unpacked with mod
    # packs excluded. See game_install.looks_like_mod_pack: `modded*.pac`
    # and `*.diff.pac` are installed mods, and unpacking them produces a
    # "vanilla" reference that is quietly a mix of vanilla and whatever
    # else was installed. A baseline like that makes every diff wrong, so
    # it is worth recording rather than assuming.
    clean_unpack: Optional[bool] = None
    studio_version: str = ""

    def is_empty(self) -> bool:
        return not (self.game_version or self.table_versions or self.studio_version)


def read_stamp(config: dict) -> ModStamp:
    """Reads Mod Studio's own block back out of a ModConfig.json."""
    block = (config.get("PluginData") or {}).get(PLUGIN_DATA_KEY)
    if not isinstance(block, dict):
        return ModStamp()
    versions = block.get("TableVersions")
    clean = block.get("CleanUnpack")
    return ModStamp(
        game_version=str(block.get("GameVersion") or ""),
        table_versions=dict(versions) if isinstance(versions, dict) else {},
        clean_unpack=clean if isinstance(clean, bool) else None,
        studio_version=str(block.get("StudioVersion") or ""),
    )


def apply_stamp(config: dict, stamp: ModStamp) -> None:
    """
    Writes Mod Studio's block into a ModConfig.json in place, leaving every
    other PluginData key alone - same rule modconfig._apply_update_settings
    follows for the GitHub update block, and for the same reason: stomping
    a sibling key would break somebody else's tooling.
    """
    plugin_data = dict(config.get("PluginData") or {})
    if stamp.is_empty():
        plugin_data.pop(PLUGIN_DATA_KEY, None)
    else:
        block = {}
        if stamp.game_version:
            block["GameVersion"] = stamp.game_version
        if stamp.table_versions:
            block["TableVersions"] = dict(stamp.table_versions)
        if stamp.clean_unpack is not None:
            block["CleanUnpack"] = stamp.clean_unpack
        if stamp.studio_version:
            block["StudioVersion"] = stamp.studio_version
        plugin_data[PLUGIN_DATA_KEY] = block
    config["PluginData"] = plugin_data


def detect_mod_game_version(config: Optional[dict], mod_sqlite: Optional[Path]) -> tuple:
    """
    Which game version a mod was built against, and how we know.

    Three sources, most trustworthy first:

    1. The mod's own stamp, if Mod Studio wrote it.
    2. The mod's own `ui.*.nxd`, read back through the converted database.
       This is the one that matters in practice right now, because it works
       on every mod published before this feature existed - including mods
       built with other tools entirely.
    3. Nothing, in which case the author has to say.

    Returns (version_or_None, human_readable_source).
    """
    if config:
        stamp = read_stamp(config)
        if stamp.game_version:
            return stamp.game_version, "recorded in the mod's ModConfig.json"
    if mod_sqlite is not None and Path(mod_sqlite).exists():
        version = read_game_version(Path(mod_sqlite))
        if version:
            return version, "read from the UI table the mod ships"
    return None, "not recorded - this mod doesn't say which game version it was built against"


# ---------------------------------------------------------------------------
# Comparing two versions of the game
# ---------------------------------------------------------------------------

@dataclass
class TableDelta:
    """How one table differs between two databases."""
    table: str
    rows_added: list = field(default_factory=list)
    rows_removed: list = field(default_factory=list)
    # {key: {field: (old_value, new_value)}}
    rows_changed: dict = field(default_factory=dict)
    columns_added: list = field(default_factory=list)
    columns_removed: list = field(default_factory=list)
    # Column order as it appears in the table, so a whole-row view reads the
    # way the table does rather than alphabetically.
    columns: list = field(default_factory=list)
    # Whole rows for anything that changed, appeared or vanished:
    # {key: (old_row_or_None, new_row_or_None)}. Kept because a changed
    # field is often meaningless without its neighbours - "Unknown4 went
    # 20 -> 24" says nothing until you can see which row it belongs to.
    # Only rows that actually differ are stored, so this stays a small
    # fraction of the table even on a large update.
    full_rows: dict = field(default_factory=dict)

    def is_empty(self) -> bool:
        return not (self.rows_added or self.rows_removed or self.rows_changed
                    or self.columns_added or self.columns_removed)

    def summary(self) -> str:
        parts = []
        if self.columns_added:
            parts.append(f"{len(self.columns_added)} column(s) added")
        if self.columns_removed:
            parts.append(f"{len(self.columns_removed)} column(s) removed")
        if self.rows_added:
            parts.append(f"{len(self.rows_added)} row(s) added")
        if self.rows_removed:
            parts.append(f"{len(self.rows_removed)} row(s) removed")
        if self.rows_changed:
            fields = sum(len(v) for v in self.rows_changed.values())
            parts.append(f"{len(self.rows_changed)} row(s) changed ({fields} field(s))")
        return ", ".join(parts)


def _table_names(con: sqlite3.Connection) -> list:
    return sorted(
        r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    )


def _columns(con: sqlite3.Connection, table: str) -> list:
    return [r[1] for r in con.execute(f'PRAGMA table_info("{table}")')]


def _key_columns(columns: list) -> list:
    """
    Which columns identify a row. Every nxd table converted by FF16Tools
    leads with `Key`, and the sparse ones add `Key2`; anything else falls
    back to the first column, which is what FF16Tools emits as the id.
    """
    keys = [name for name in ("Key", "Key2") if name in columns]
    return keys or columns[:1]


def compare_databases(old_sqlite: Path, new_sqlite: Path,
                      tables: Optional[list] = None) -> dict:
    """
    Every difference between two converted databases, table by table.

    Deliberately generic rather than going through nxd_data's typed
    readers: it walks whatever tables are actually there and diffs them by
    their own key columns, so it covers all ~563 tables including the ones
    Mod Studio has no tab for. That breadth is the whole point. The modelled
    readers see nothing at all between 1.5.1 and 1.5.2, because the only
    thing those two versions differ by is a row in `UI-*` - a table with no
    tab, and therefore invisible to every typed reader in this project.

    Used for the "what changed between game versions" view. The merge
    itself uses the typed readers, because carrying an edit forward needs
    to understand what a field *means*, not just that it moved.
    """
    old_con = sqlite3.connect(f"file:{old_sqlite}?mode=ro", uri=True)
    new_con = sqlite3.connect(f"file:{new_sqlite}?mode=ro", uri=True)
    try:
        old_tables = set(_table_names(old_con))
        new_tables = set(_table_names(new_con))
        wanted = sorted(old_tables & new_tables) if tables is None else [
            t for t in tables if t in old_tables and t in new_tables
        ]

        deltas = {}
        for table in wanted:
            old_cols = _columns(old_con, table)
            new_cols = _columns(new_con, table)
            delta = TableDelta(
                table=table,
                columns_added=[cname for cname in new_cols if cname not in old_cols],
                columns_removed=[cname for cname in old_cols if cname not in new_cols],
            )
            shared_cols = [cname for cname in new_cols if cname in old_cols]
            keys = _key_columns(shared_cols)
            if not keys:
                continue

            def load(con, cols):
                rows = {}
                quoted = ", ".join(f'"{cname}"' for cname in cols)
                for row in con.execute(f'SELECT {quoted} FROM "{table}"'):
                    record = dict(zip(cols, row))
                    rows[tuple(record[k] for k in keys)] = record
                return rows

            old_rows = load(old_con, shared_cols)
            new_rows = load(new_con, shared_cols)
            delta.columns = list(shared_cols)
            delta.rows_added = sorted(set(new_rows) - set(old_rows), key=_sort_key)
            delta.rows_removed = sorted(set(old_rows) - set(new_rows), key=_sort_key)
            for key in delta.rows_added:
                delta.full_rows[key] = (None, new_rows[key])
            for key in delta.rows_removed:
                delta.full_rows[key] = (old_rows[key], None)
            for key in set(old_rows) & set(new_rows):
                changed = {
                    name: (old_rows[key][name], new_rows[key][name])
                    for name in shared_cols
                    if old_rows[key][name] != new_rows[key][name]
                }
                if changed:
                    delta.rows_changed[key] = changed
                    delta.full_rows[key] = (old_rows[key], new_rows[key])
            if not delta.is_empty():
                deltas[table] = delta

        for table in sorted(new_tables - old_tables):
            deltas[table] = TableDelta(table=table, columns_added=_columns(new_con, table))
        for table in sorted(old_tables - new_tables):
            deltas[table] = TableDelta(table=table, columns_removed=_columns(old_con, table))
        return deltas
    finally:
        old_con.close()
        new_con.close()


def _sort_key(key):
    """Sorts mixed-type composite keys without tripping over None or str/int mixes."""
    return tuple((value is None, str(type(value)), value if value is not None else 0)
                 for value in key)


# ---------------------------------------------------------------------------
# The three-way merge
# ---------------------------------------------------------------------------

CLEAN = "clean"          # the update didn't touch this field; carries as-is
REDUNDANT = "redundant"  # the update made the same change the mod did
CONFLICT = "conflict"    # the update changed this field to something else
ORPHANED = "orphaned"    # the row is gone from the new version

KEEP_MOD = "mod"
TAKE_UPDATE = "update"
DROP = "drop"
# For a whole file with no editor tab: take the game's new copy and put the
# mod's own changes back on top of it. The only option of the three that
# keeps both what the author did and what the update did - Keep freezes the
# table at the old version, Drop discards the author's work.
REBASE = "rebase"

# Which tab an edit belongs to, for grouping the review the same way the
# Export page's preview groups its own output.
SECTION_ABILITIES = "Abilities"
SECTION_ITEMS = "Items"
SECTION_ENCOUNTERS = "Encounters"
SECTION_POACHING = "Poaching"


@dataclass
class FieldChange:
    """One field the mod changed, and what became of it."""
    section: str
    table: str
    key: object                  # int, or (key, key2) for OverrideEntryData
    field_name: str
    base_value: object           # what the old game had
    mod_value: object            # what the mod made it
    new_value: object            # what the new game has
    outcome: str
    resolution: str = KEEP_MOD   # what will actually be written
    label: str = ""              # human name for the row, when we have one

    @property
    def needs_decision(self) -> bool:
        return self.outcome == CONFLICT

    def resolved_value(self):
        if self.resolution == TAKE_UPDATE:
            return self.new_value
        return self.mod_value


@dataclass
class RowAdvisory:
    """
    The update changed *other* fields on a row the mod also edits.

    No field-level conflict, so nothing to decide - but worth saying,
    because per-field merging can produce a row neither side intended. If
    an update rebalances an ability's Formula while the mod changed its
    X/Y, both carry cleanly and the result is a combination nobody
    designed. No tool can detect that automatically; the honest move is to
    point at the row and let the author look.
    """
    section: str
    table: str
    key: object
    mod_fields: list
    update_fields: list
    label: str = ""


@dataclass
class StructuralFinding:
    """
    Something about the mod's shape, rather than one field, that the update
    disturbed. Currently all from OverrideEntryData, which is the only
    table where a mod's row *set* is part of what it changed.
    """
    kind: str          # see the DESTINATION_/ORIGIN_ constants below
    address: tuple
    detail: str
    severity: str = "info"   # "info" | "warning" | "blocking"


DESTINATION_TAKEN = "destination_taken"
ORIGIN_REMOVED = "origin_removed"
ORIGIN_CHANGED = "origin_changed"
ROW_COUNT_CHANGED = "row_count_changed"


@dataclass
class UnmodelledTable:
    """
    A `.nxd` the mod ships that Mod Studio has no tab for - `ui.*.nxd`,
    `uibuttonguide.nxd` and friends.

    These matter more than their obscurity suggests. Because a `.nxd`
    replaces the game's file wholesale, shipping one freezes that entire
    table at the version it was built against. The Dark Knight Expansion
    ships all seven `ui.*.nxd`, which is why it reverts the game's own
    version display - and, checked against three separate vanilla unpacks,
    also blanks five real UI strings and drops 36 rows from
    `UIButtonGuide` that no vanilla database is missing.

    `additions` is what decides the recommended default. A table whose only
    differences from vanilla are losses - values blanked, rows missing,
    fields zeroed - contributes nothing and costs the update, so the
    recommendation is to drop it. A table with real additions gets rebased
    instead.
    """
    filename: str
    table: str
    additions: int = 0       # values the mod set that the game doesn't have
    losses: int = 0          # values the mod blanked where the game has content
    stale: int = 0           # values the mod never touched, that the game has since changed
    rows_missing: int = 0    # rows the baseline had that the mod's copy dropped
    rows_stale: int = 0      # rows the update added, which the mod predates
    rows_extra: int = 0
    # {key: {column: value}} - only what the author actually changed against
    # the baseline, which is what Rebase re-applies to the game's new table.
    own_changes: dict = field(default_factory=dict)
    # {key: {column: value}} - what the game currently has in those same
    # places, kept so the review can show both sides of each change instead
    # of asking the author to approve a value with nothing to compare it to.
    game_values: dict = field(default_factory=dict)
    # {(key, column): reason} - changes that are listed but start unticked,
    # with the reason shown beside them. For things that look like the
    # author's work but almost certainly aren't, where hiding them would be
    # worse than explaining them.
    excluded_by_default: dict = field(default_factory=dict)
    # Whether this table is present in the working database, and so can be
    # written back out at all. Rebase needs somewhere to put the result.
    rebasable: bool = False
    # False when the mod's copy of this table couldn't be read at all, as
    # opposed to read and found identical. Those are completely different
    # answers and were previously indistinguishable: an unreadable table
    # produced zero counts everywhere, which displayed as "no differences
    # from the game's copy" - stated confidently, and wrong.
    readable: bool = True

    @property
    def change_count(self) -> int:
        """How many individual values differ from the baseline."""
        return sum(len(fields) for fields in self.own_changes.values())

    def default_selection(self) -> set:
        """Which changes start ticked: everything except the flagged ones."""
        return {(key, column)
                for key, fields in self.own_changes.items() for column in fields
                if (key, column) not in self.excluded_by_default}

    @property
    def has_own_work(self) -> bool:
        """
        Whether anything in this file is the author's rather than the
        game's.

        **Blanking counts.** An earlier version treated "the mod has nothing
        where the game has something" as damage and recommended dropping the
        file. That is wrong: clearing a string is how you remove a UI
        element, and at least one real mod exists whose entire purpose is
        tidying the HUD that way. Its deliberate work was being described as
        a file "damaged rather than edited" and offered for deletion.

        Additions and blankings are both edits. Whether an edit was intended
        is not something this data can answer, and guessing at it was the
        mistake.
        """
        # Flagged changes don't count. A file whose only difference is the
        # game's own version marker contains nothing of the author's, and
        # treating it as work would recommend merging a file that has
        # nothing to merge.
        return bool(self.default_selection()) or self.rows_missing > 0 or self.rows_extra > 0

    @property
    def purely_stale(self) -> bool:
        """
        Nothing here is the author's; the file is just an older copy.

        This one *is* answerable from the data: every difference from the
        game is a place where the mod agrees with the baseline and the game
        has since moved on.
        """
        return not self.has_own_work and (self.stale > 0 or self.rows_stale > 0)

    @property
    def recommendation(self) -> str:
        if not self.readable:
            # Nothing is known about this file, so keep what the author
            # shipped. Dropping something unexamined is guessing with their
            # work.
            return KEEP_MOD
        if self.has_own_work:
            # Merging is the only choice that keeps both the author's work
            # and the update, so it is the default whenever it's possible -
            # regardless of what kind of edits they are or how many.
            return REBASE if self.rebasable else KEEP_MOD
        # Provably nothing of the author's in here. Shipping it anyway costs
        # this update and every future one, since the file would go stale
        # again, so leaving it out is the better default. Not "always
        # merge": merging an empty file produces a copy of the game's own,
        # which is a liability with no upside.
        return DROP


@dataclass
class MigrationPlan:
    """Everything migrating one mod to one newer game version would do."""
    from_version: str = ""
    to_version: str = ""
    changes: list = field(default_factory=list)          # list[FieldChange]
    advisories: list = field(default_factory=list)       # list[RowAdvisory]
    structural: list = field(default_factory=list)       # list[StructuralFinding]
    unmodelled: list = field(default_factory=list)       # list[UnmodelledTable]
    rekeys: dict = field(default_factory=dict)
    dropped: list = field(default_factory=list)

    def by_outcome(self, outcome: str) -> list:
        return [ch for ch in self.changes if ch.outcome == outcome]

    def conflicts(self) -> list:
        return self.by_outcome(CONFLICT)

    def unresolved_count(self) -> int:
        return sum(1 for ch in self.changes if ch.needs_decision)

    def is_noop(self) -> bool:
        """
        True when the update changed nothing this mod touches. Worth its own
        answer rather than an empty review list: between 1.5.1 and 1.5.2 the
        game changed exactly one row in the whole database, so "nothing to
        do" is going to be the common case and should read as reassurance,
        not as an empty screen.
        """
        return not (self.conflicts() or self.by_outcome(ORPHANED)
                    or self.structural or self.unmodelled)

    def sections(self) -> list:
        """Section names present, in the Edit Game Data tab order."""
        order = [SECTION_ABILITIES, SECTION_ITEMS, SECTION_POACHING, SECTION_ENCOUNTERS]
        present = {ch.section for ch in self.changes} | {a.section for a in self.advisories}
        return [name for name in order if name in present]

    def summary(self) -> str:
        clean = len(self.by_outcome(CLEAN)) + len(self.by_outcome(REDUNDANT))
        parts = [f"{clean} change(s) carry over cleanly"]
        conflicts = len(self.conflicts())
        if conflicts:
            parts.append(f"{conflicts} conflict(s) need a decision")
        orphaned = len(self.by_outcome(ORPHANED))
        if orphaned:
            parts.append(f"{orphaned} change(s) can't be carried")
        if self.unmodelled:
            parts.append(f"{len(self.unmodelled)} table(s) with no editor tab")
        return " · ".join(parts)


def _classify_field(base_value, mod_value, new_value, row_exists: bool) -> str:
    if not row_exists:
        return ORPHANED
    if new_value == base_value:
        return CLEAN          # the update left this field alone
    if new_value == mod_value:
        return REDUNDANT      # the update happened to make the same change
    return CONFLICT


def _classify_keyed(section, table, mod_edits, update_edits,
                    base_rows, new_rows, labels=None) -> tuple:
    """
    The per-field comparison, shared by every table shaped `{key: {field: value}}`.
    Returns (changes, advisories).
    """
    labels = labels or {}
    changes = []
    advisories = []
    for key in sorted(mod_edits, key=lambda k: _sort_key(k if isinstance(k, tuple) else (k,))):
        fields = mod_edits[key]
        row_exists = key in new_rows
        their_fields = update_edits.get(key, {})
        base_row = base_rows.get(key, {})
        new_row = new_rows.get(key, {})
        label = labels.get(key, "")

        for name, mod_value in sorted(fields.items()):
            changes.append(FieldChange(
                section=section, table=table, key=key, field_name=name,
                base_value=base_row.get(name),
                mod_value=mod_value,
                new_value=new_row.get(name),
                outcome=_classify_field(
                    base_row.get(name), mod_value, new_row.get(name), row_exists
                ),
                label=label,
            ))

        # Row-level advisory: the update touched other fields on this row.
        overlap = [n for n in their_fields if n not in fields]
        if row_exists and overlap:
            advisories.append(RowAdvisory(
                section=section, table=table, key=key,
                mod_fields=sorted(fields), update_fields=sorted(overlap), label=label,
            ))
    return changes, advisories


def diff_vanilla_entries(old_sqlite: Path, new_sqlite: Path) -> dict:
    """
    OverrideEntryData between two *vanilla* databases: a plain structural
    diff, with the rekey inference deliberately switched off.

    nxd_data._diff_entries pairs vacated addresses against newly-appeared
    ones and calls the result a move, which is exactly right for a mod and
    exactly wrong for a game update. A patch that adds a row would be read
    as a mod-style repurpose, inventing an origin that never existed.
    Verified: adding a single row to a copy of 1.5.1 comes back through
    _diff_entries as a rekey, and through this function as an addition.

    Returns {(key, key2): {field: new_value}} for rows present in both,
    plus the raw added/removed sets under the "+"/"-" pseudo-keys.
    """
    try:
        base = {(r.key, r.key2): r.values for r in nxd_data.read_override_entry_table(old_sqlite)}
        new = {(r.key, r.key2): r.values for r in nxd_data.read_override_entry_table(new_sqlite)}
    except (ValueError, sqlite3.Error):
        return {"changed": {}, "added": [], "removed": []}

    changed = {}
    for address in set(base) & set(new):
        fields = {
            name: value for name, value in new[address].items()
            if base[address].get(name) != value
        }
        if fields:
            changed[address] = fields
    return {
        "changed": changed,
        "added": sorted(set(new) - set(base)),
        "removed": sorted(set(base) - set(new)),
    }


def _rows_by_key(sqlite_path: Path, reader, *args) -> dict:
    try:
        return {r.key: r.values for r in reader(sqlite_path, *args)}
    except (ValueError, sqlite3.Error):
        return {}


def build_plan(base_sqlite: Path, mod_sqlite: Path, new_sqlite: Path,
               mod_intent=None) -> MigrationPlan:
    """
    Works out what migrating this mod onto the new game version would do.

    `mod_intent` may be passed in when the caller already has it (opening a
    mod computes exactly this), otherwise it's derived here. Nothing is
    written; the plan is a description, and applying it is a separate step
    so the author gets to look first.
    """
    intent = mod_intent or nxd_data.recover_edits_from_sqlite(base_sqlite, mod_sqlite)
    update = nxd_data.recover_edits_from_sqlite(base_sqlite, new_sqlite)

    plan = MigrationPlan(
        from_version=read_game_version(base_sqlite) or "",
        to_version=read_game_version(new_sqlite) or "",
        rekeys=dict(intent.entry_rekeys),
        dropped=list(intent.entry_dropped),
    )

    # -- the four per-language / per-key tables ----------------------------
    per_language = (
        (SECTION_ABILITIES, c.NXD_ABILITY_TABLE, nxd_data.read_ability_table,
         intent.ability_edits, update.ability_edits),
        (SECTION_ITEMS, c.NXD_ITEM_TABLE, nxd_data.read_item_table,
         intent.item_edits, update.item_edits),
        (SECTION_ENCOUNTERS, c.NXD_CHARANAME_TABLE, nxd_data.read_charaname_table,
         intent.chara_name_edits, update.chara_name_edits),
        (SECTION_POACHING, c.NXD_POACH_TABLE, nxd_data.read_poach_table,
         intent.poach_edits, update.poach_edits),
    )
    for section, table_map, reader, mine, theirs in per_language:
        for language, edits in sorted(mine.items()):
            base_rows = _rows_by_key(base_sqlite, reader, language)
            new_rows = _rows_by_key(new_sqlite, reader, language)
            labels = {
                key: str(values.get("Name") or "")
                for key, values in new_rows.items() if values.get("Name")
            }
            changes, advisories = _classify_keyed(
                section, table_map[language], edits, theirs.get(language, {}),
                base_rows, new_rows, labels,
            )
            plan.changes.extend(changes)
            plan.advisories.extend(advisories)

    # -- OverrideAbilityActionData (packed flag groups) --------------------
    plan.changes.extend(_classify_override_action(
        base_sqlite, new_sqlite, intent.override_action_edits,
        update.override_action_edits,
    )[0])

    # -- OverrideEntryData -------------------------------------------------
    entry_changes, entry_advisories, structural = _classify_entries(
        base_sqlite, new_sqlite, intent,
    )
    plan.changes.extend(entry_changes)
    plan.advisories.extend(entry_advisories)
    plan.structural.extend(structural)
    return plan


def _classify_override_action(base_sqlite, new_sqlite, mine, theirs) -> tuple:
    """
    OverrideAbilityActionData reports flags per group rather than per
    column, so its base/new values have to be read the same way rather than
    straight off the row - see nxd_data._diff_override_action.
    """
    def load(path):
        try:
            return {r.key: r for r in nxd_data.read_override_action_table(path)}
        except (ValueError, sqlite3.Error):
            return {}

    base_records = load(base_sqlite)
    new_records = load(new_sqlite)

    def values_of(record):
        if record is None:
            return {}
        values = dict(record.scalars)
        for group in range(4):
            values[f"FlagsGroup{group}"] = record.flag_group_value(group)
        return values

    base_rows = {key: values_of(r) for key, r in base_records.items()}
    new_rows = {key: values_of(r) for key, r in new_records.items()}
    return _classify_keyed(
        SECTION_ABILITIES, c.NXD_OVERRIDE_ACTION_TABLE, mine, theirs, base_rows, new_rows,
    )


def _classify_entries(base_sqlite, new_sqlite, intent) -> tuple:
    """
    OverrideEntryData, where the mod's row *set* is part of what it changed
    and so the update can disturb the mod structurally, not just per field.

    Four things can go wrong, and they are genuinely different:

    - The update takes an address the mod moved a row *to*. That's a real
      collision and the only one that can break the mod outright.
    - The update removes the row a move started from. The raw material is
      gone; the move can still happen, but what it carries is now the mod's
      own copy rather than something derived from vanilla.
    - The update changes a row the mod moved *away* from. Informational
      only: the mod took that row as raw material and overwrote it, so
      whatever vanilla later put there was never going to be inherited.
    - The row count changed. Not a fault, but the Encounters tab tracks
      parity, so it should be said rather than discovered.
    """
    delta = diff_vanilla_entries(base_sqlite, new_sqlite)
    try:
        base_rows = {(r.key, r.key2): r.values
                     for r in nxd_data.read_override_entry_table(base_sqlite)}
        new_rows = {(r.key, r.key2): r.values
                    for r in nxd_data.read_override_entry_table(new_sqlite)}
    except (ValueError, sqlite3.Error):
        return [], [], []

    structural = []
    added = set(delta["added"])
    removed = set(delta["removed"])

    for origin, destination in sorted(intent.entry_rekeys.items()):
        if destination in added:
            structural.append(StructuralFinding(
                kind=DESTINATION_TAKEN, address=destination, severity="blocking",
                detail=(
                    f"The update adds its own row at {destination[0]}/{destination[1]}, "
                    f"which is where this mod moves the row from "
                    f"{origin[0]}/{origin[1]}. Both can't occupy that address."
                ),
            ))
        if origin in removed:
            structural.append(StructuralFinding(
                kind=ORIGIN_REMOVED, address=origin, severity="warning",
                detail=(
                    f"The update removes row {origin[0]}/{origin[1]}, which this mod "
                    f"moves to {destination[0]}/{destination[1]}. The move still "
                    f"works, but it now carries the mod's own values rather than "
                    f"values derived from the game's."
                ),
            ))
        elif origin in delta["changed"]:
            structural.append(StructuralFinding(
                kind=ORIGIN_CHANGED, address=origin, severity="info",
                detail=(
                    f"The update changes row {origin[0]}/{origin[1]}, which this mod "
                    f"repurposes into {destination[0]}/{destination[1]}. Nothing to "
                    f"decide - the mod overwrote that row on purpose."
                ),
            ))

    if len(base_rows) != len(new_rows):
        structural.append(StructuralFinding(
            kind=ROW_COUNT_CHANGED, address=(), severity="info",
            detail=(
                f"OverrideEntryData went from {len(base_rows)} rows to "
                f"{len(new_rows)} in this update. This mod's own row set is "
                f"preserved either way."
            ),
        ))

    # Field-level comparison. A moved row's edits are keyed by its origin,
    # so they're compared against the origin row on both sides - which is
    # what re-export will do with them too.
    changes, advisories = _classify_keyed(
        SECTION_ENCOUNTERS, c.NXD_OVERRIDE_ENTRY_TABLE,
        intent.entry_edits, delta["changed"], base_rows, new_rows,
    )
    # A row the mod invented outright (no origin) has no vanilla counterpart
    # in either database, so every field reads as ORPHANED. That's wrong:
    # it isn't orphaned, it's new, and it carries forward untouched.
    invented = set(intent.entry_edits) - set(base_rows)
    for change in changes:
        if change.key in invented:
            change.outcome = CLEAN
    return changes, advisories, structural


# ---------------------------------------------------------------------------
# Unmodelled .nxd files
# ---------------------------------------------------------------------------

MODELLED_NXD_FILENAMES = frozenset(
    c.NXD_ALL_FILENAMES + c.NXD_ALL_ITEM_FILENAMES
    + c.NXD_ALL_ENCOUNTER_FILENAMES + c.NXD_ALL_POACH_FILENAMES
)


def _candidate_table_name(filename: str) -> str:
    """
    The table name a `.nxd` filename corresponds to, in lower case.

    `ui.en.nxd` -> `ui-en`, `uibuttonguide.nxd` -> `uibuttonguide`. Case is
    deliberately not guessed here: filenames are lower case and table names
    are CamelCase (`UIButtonGuide`, `UIAnnounce`, `CharaName`), and there is
    no rule that recovers one from the other - `uibuttonguide` could be
    `UiButtonGuide` or `UIButtonGuide` and only the database knows which.
    resolve_table_name does the lookup instead of inventing an answer.
    """
    stem = filename[:-4] if filename.lower().endswith(".nxd") else filename
    parts = stem.lower().split(".")
    if len(parts) == 2 and parts[1] in c.NXD_LANGUAGES:
        return f"{parts[0]}-{parts[1]}"
    return parts[0]


def resolve_table_name(sqlite_path: Path, filename: str) -> Optional[str]:
    """
    Finds the real table a `.nxd` file became, matching case-insensitively
    against what the database actually contains.

    Asking the database beats any naming convention: FF16Tools decides the
    capitalisation, it isn't uniform (`UIButtonGuide` versus `CharaName`),
    and a future table with yet another style would silently fail a
    hard-coded rule.
    """
    wanted = _candidate_table_name(filename)
    try:
        con = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
    except sqlite3.Error:
        return None
    try:
        for name in _table_names(con):
            if name.lower() == wanted:
                return name
        return None
    except sqlite3.Error:
        return None
    finally:
        con.close()


def find_unmodelled_nxd(mod_nxd_dir: Path) -> list:
    """Every .nxd the mod ships that this tool has no tab for."""
    if not Path(mod_nxd_dir).is_dir():
        return []
    return sorted(
        path.name for path in Path(mod_nxd_dir).glob("*.nxd")
        if path.name.lower() not in MODELLED_NXD_FILENAMES
    )


def assess_unmodelled_table(mod_sqlite: Path, vanilla_sqlite: Path,
                            filename: str, table: str,
                            baseline_sqlite: Optional[Path] = None) -> Optional[UnmodelledTable]:
    """
    Compares one unmodelled table against the current game and works out
    what kind of difference it holds.

    `baseline_sqlite` is what separates a deliberate change from a stale
    one, and without it the two are genuinely indistinguishable. A mod
    shipping `ui.en.nxd` from an older release differs from the current
    game at the version string - which is not an edit anybody made, it's
    just an old copy. Read two-way that looks exactly like a deliberate
    value the author chose, and the recommendation comes out backwards;
    read against the baseline it is obviously staleness, because the mod
    and the baseline agree.

    So: a field where the mod matches the baseline but the game has moved
    on is `stale`. A field where the mod differs from the baseline is the
    author's, counted as an `addition` or, if they blanked something, a
    `loss`. Only additions argue for keeping the file.
    """
    result = UnmodelledTable(filename=filename, table=table)
    try:
        mod_con = sqlite3.connect(f"file:{mod_sqlite}?mode=ro", uri=True)
        van_con = sqlite3.connect(f"file:{vanilla_sqlite}?mode=ro", uri=True)
    except sqlite3.Error:
        return None
    try:
        try:
            mod_cols = _columns(mod_con, table)
            van_cols = _columns(van_con, table)
        except sqlite3.Error:
            return None
        shared = [name for name in mod_cols if name in van_cols]
        if not shared:
            return None
        keys = _key_columns(shared)
        quoted = ", ".join(f'"{name}"' for name in shared)

        def load(con):
            rows = {}
            try:
                cursor = con.execute(f'SELECT {quoted} FROM "{table}"')
            except sqlite3.Error:
                return rows
            for row in cursor:
                record = dict(zip(shared, row))
                rows[tuple(record[k] for k in keys)] = record
            return rows

        mod_rows = load(mod_con)
        van_rows = load(van_con)
        if not mod_rows and not van_rows:
            return None

        base_rows = {}
        if baseline_sqlite is not None:
            try:
                base_con = sqlite3.connect(f"file:{baseline_sqlite}?mode=ro", uri=True)
            except sqlite3.Error:
                base_con = None
            if base_con is not None:
                try:
                    if all(name in _columns(base_con, table) for name in shared):
                        base_rows = load(base_con)
                except sqlite3.Error:
                    base_rows = {}
                finally:
                    base_con.close()

        # A row the game has and the mod doesn't is only the mod's doing if
        # the baseline had it too. If the baseline didn't, the update added
        # it and the mod simply predates it - staleness, not deletion.
        absent = set(van_rows) - set(mod_rows)
        if base_rows:
            result.rows_missing = len(absent & set(base_rows))
            result.rows_stale = len(absent - set(base_rows))
        else:
            result.rows_missing = len(absent)
        result.rows_extra = len(set(mod_rows) - set(van_rows))
        for key in set(mod_rows) & set(van_rows):
            base_row = base_rows.get(key)
            for name in shared:
                mine, theirs = mod_rows[key][name], van_rows[key][name]
                if mine == theirs:
                    continue
                if base_row is not None and base_row.get(name) == mine:
                    # The mod agrees with the baseline; the game moved on.
                    result.stale += 1
                    continue
                # Whichever way it falls, this differs from the baseline, so
                # it is the author's doing and merging should carry it.
                # Clearing counts: blanking a string can be a real edit, and
                # second-guessing which of someone's changes they meant is
                # not this function's job.
                if _is_game_version_cell(table, key, name):
                    # The game's own version marker. It looks like the mod's
                    # work whenever the true baseline isn't archived - the
                    # mod holds v1.5.1, the substitute baseline holds
                    # v1.5.2, and the difference reads as an edit. Carrying
                    # it over would make the game report a version it isn't.
                    #
                    # Counted as staleness, and **listed but unticked**
                    # rather than removed. An earlier version dropped it
                    # silently, which was worse than the footgun it fixed:
                    # a row vanished from a review with no explanation, and
                    # the only honest response to "what else is it hiding?"
                    # is that it shouldn't have hidden anything. A modder
                    # who genuinely wants a custom version string can still
                    # tick it - it's their mod.
                    result.stale += 1
                    result.excluded_by_default[(key, name)] = (
                        "The game's own version number")
                else:
                    if _is_blank(mine) and not _is_blank(theirs):
                        result.losses += 1
                    else:
                        result.additions += 1
                result.own_changes.setdefault(key, {})[name] = mine
                result.game_values.setdefault(key, {})[name] = theirs
        # A row only the mod has is an addition in the sense that matters
        # here: the mod put content there that the game doesn't have.
        result.additions += result.rows_extra
        return result
    finally:
        mod_con.close()
        van_con.close()


def _is_game_version_cell(table: str, key, column: str) -> bool:
    """
    Whether this is the row holding the game's own version string.

    The one cell in the whole dataset whose meaning is known, which is why
    it gets a special case rather than a heuristic: `UI-<lang>` key 3737 is
    what the game displays as its version, and it belongs to the game.
    """
    if column != "Text" or not table.upper().startswith("UI-"):
        return False
    identifier = key[0] if isinstance(key, tuple) and key else key
    return identifier == VERSION_UI_KEY


def _is_blank(value) -> bool:
    """
    Whether a value reads as "nothing here".

    NULL is a legitimate, common value in these tables - 1956 of the 4050
    rows in a vanilla `UI-en` have a NULL Text - so blankness alone proves
    nothing. It only becomes evidence when the mod has a blank where
    vanilla has content, which is what the caller checks.
    """
    return value is None or value == 0 or value == "" or value == []


def assess_unmodelled(mod_nxd_dir: Path, mod_sqlite: Path,
                      vanilla_sqlite: Path,
                      baseline_sqlite: Optional[Path] = None,
                      game_nxd_dir: Optional[Path] = None) -> list:
    """
    Every unmodelled table the mod ships, assessed against vanilla.

    A file whose table can't be resolved, or that vanilla doesn't have at
    all, is still returned - with zero counts - rather than dropped. The
    author needs to see that the mod ships it either way; silently omitting
    a file from a review whose whole job is completeness would be worse
    than showing one we can't say much about.
    """
    results = []
    for filename in find_unmodelled_nxd(mod_nxd_dir):
        table = resolve_table_name(mod_sqlite, filename)
        assessment = None
        if table is not None:
            assessment = assess_unmodelled_table(
                mod_sqlite, vanilla_sqlite, filename, table, baseline_sqlite)
            if assessment is None:
                # Table resolved but nothing comparable came back - usually
                # the game has no such table. Recorded as unreadable rather
                # than as an absence of differences.
                results.append(UnmodelledTable(filename=filename, table=table, readable=False))
                continue
            if assessment is not None:
                # Merging needs two things: the mod's own changes, which we
                # have as soon as the table is readable, and the game's copy
                # of the table to put them on.
                #
                # This used to be a hard-coded "only the ui.*.nxd", because
                # only those were in the working database. Export now
                # fetches the game's copy of anything else on demand from
                # its own .nxd, so the real condition is whether the game
                # ships that file at all - which is what `game_nxd_dir`
                # answers. A mod inventing a .nxd the game doesn't have
                # can't be merged, and that is a genuine limit rather than
                # an arbitrary one.
                assessment.rebasable = bool(
                    assessment.readable
                    and (game_nxd_dir is None
                         or (Path(game_nxd_dir) / filename).exists())
                )
        results.append(assessment
                       or UnmodelledTable(filename=filename, table=table or "", readable=False))
    return results


# ---------------------------------------------------------------------------
# Applying a plan
# ---------------------------------------------------------------------------

def apply_plan(plan: MigrationPlan) -> nxd_data.RecoveredNxdEdits:
    """
    Turns a reviewed plan back into the edit dicts the tabs and Export
    already use, so a migrated mod is indistinguishable from one typed in
    by hand - the same property nxd_data.recover_edits_from_sqlite was
    built for, and the reason migration needed no new write path.

    Orphaned changes are dropped (there is no row to write them to) and
    conflicts resolved to whichever side the author chose, defaulting to
    the mod's own value.
    """
    result = nxd_data.RecoveredNxdEdits(
        entry_rekeys=dict(plan.rekeys),
        entry_dropped=list(plan.dropped),
    )
    language_targets = {
        (SECTION_ABILITIES, "Ability"): result.ability_edits,
        (SECTION_ITEMS, "Item"): result.item_edits,
        (SECTION_ENCOUNTERS, "CharaName"): result.chara_name_edits,
        (SECTION_POACHING, "PoachItem"): result.poach_edits,
    }

    for change in plan.changes:
        if change.outcome == ORPHANED or change.resolution == DROP:
            continue
        value = change.resolved_value()

        if change.table == c.NXD_OVERRIDE_ACTION_TABLE:
            result.override_action_edits.setdefault(change.key, {})[change.field_name] = value
            continue
        if change.table == c.NXD_OVERRIDE_ENTRY_TABLE:
            result.entry_edits.setdefault(change.key, {})[change.field_name] = value
            continue

        prefix, _, language = change.table.rpartition("-")
        target = language_targets.get((change.section, prefix))
        if target is None:
            continue
        target.setdefault(language, {}).setdefault(change.key, {})[change.field_name] = value

    return result


# ---------------------------------------------------------------------------
# Finding the baseline a mod was built against
# ---------------------------------------------------------------------------
#
# The first version of this asked the mod what version it was, via a stamp
# or the `ui.*.nxd` it ships. Zodi's objection: most mods ship neither, so
# for most mods the answer is simply unavailable - and asking is the wrong
# question anyway.
#
# She's right, and the better question is content-based. What the merge
# actually needs is *a baseline the mod's edits make sense against*, and
# that can be found by trying each archived version and seeing which one
# fits. A mod built on 1.5.1 diffed against 1.5.1 shows only its own edits;
# diffed against 1.5.0 it shows its own edits **plus** every 1.5.0-to-1.5.1
# difference in the tables it ships. The best fit is the smallest diff.
#
# This is strictly more robust than reading metadata: it works on mods with
# no stamp, no UI table, and built with tools that have never heard of Mod
# Studio - which is nearly all of them.
#
# It also degrades in the right direction. When several versions score
# identically it's because they don't differ in any table this mod touches,
# so the choice cannot affect the result - the ambiguity is real and
# harmless, and saying so is more useful than picking one and implying
# certainty. Measured on the real Dark Knight Expansion against real 1.5.0,
# 1.5.1 and 1.5.2 databases: all three score 256, because those releases are
# identical everywhere that mod reaches.
#
# The version string is kept, demoted from answer to corroboration.


@dataclass
class BaselineCandidate:
    """One archived version, scored as a possible baseline for a mod."""
    version: str
    sqlite_path: Path
    score: int = 0          # field-level differences; lower fits better
    error: str = ""

    @property
    def usable(self) -> bool:
        return not self.error


@dataclass
class BaselineChoice:
    """Which baseline to merge against, and how much to trust the answer."""
    chosen: Optional[BaselineCandidate] = None
    candidates: list = field(default_factory=list)
    ties: list = field(default_factory=list)
    hint_version: str = ""
    hint_source: str = ""
    hint_agreed: bool = False

    @property
    def found(self) -> bool:
        return self.chosen is not None

    @property
    def ambiguous(self) -> bool:
        return len(self.ties) > 1

    @property
    def fell_back(self) -> bool:
        """
        The mod says which version it was built for, and that version isn't
        one of the saved ones.

        Worth its own flag because the chosen baseline is then a substitute,
        not an answer, and everything downstream has to say so. Treating a
        fallback as confident produced a genuinely contradictory Status tab:
        "the mod's own files say v1.5.1, but no saved copy is available,
        using v1.5.2" immediately followed by "this mod already matches the
        game files you have (v1.5.2)" - which it plainly does not.
        """
        return bool(self.hint_version and self.found
                    and self.chosen.version != self.hint_version)

    def explain(self) -> str:
        """Plain-language account of how the baseline was picked."""
        if not self.found:
            return (
                "No saved game version to compare this mod against. Mod Studio saves one "
                "each time you unpack, so this fills in from here on - but a mod built "
                "before any were saved can't be told apart from the game it was built on."
            )
        if self.hint_version and self.chosen.version == self.hint_version:
            agreement = ("and comparing its data against every saved version agrees"
                         if self.hint_agreed else
                         "though its data is a slightly closer match to another saved version")
            return (f"Built against {self.chosen.version} - the mod's own files say so "
                    f"({self.hint_source or 'from the files it ships'}), {agreement}.")
        if self.hint_version:
            return (
                f"The mod's own files say {self.hint_version}, but no saved copy of that "
                f"version is available. Using {self.chosen.version}, the closest match "
                f"among the versions that are saved."
            )
        if self.ambiguous:
            names = ", ".join(sorted(c.version for c in self.ties))
            return (
                f"This mod doesn't record a version. It fits {names} equally well, because "
                f"those versions don't differ anywhere it makes changes - so using "
                f"{self.chosen.version} can't affect the result."
            )
        return (
            f"This mod doesn't record a version. Comparing its data against every saved "
            f"version, {self.chosen.version} is the closest match."
        )


def score_baseline(candidate_sqlite: Path, mod_sqlite: Path) -> int:
    """
    How far a mod sits from a candidate baseline, counted in changed fields.

    Every field the mod appears to change, plus each structural change to
    OverrideEntryData. The number itself has no meaning; only the comparison
    between candidates does.
    """
    edits = nxd_data.recover_edits_from_sqlite(candidate_sqlite, mod_sqlite)
    total = 0
    for per_language in (edits.ability_edits, edits.item_edits,
                         edits.chara_name_edits, edits.poach_edits):
        for rows in per_language.values():
            total += sum(len(fields) for fields in rows.values())
    total += sum(len(fields) for fields in edits.override_action_edits.values())
    total += sum(len(fields) for fields in edits.entry_edits.values())
    total += len(edits.entry_rekeys) + len(edits.entry_dropped)
    return total


def identify_baseline(mod_sqlite: Path, candidates: list,
                      hint_version: str = "", hint_source: str = "") -> BaselineChoice:
    """
    Picks the archived version a mod was most likely built against.

    `candidates` is [(version, sqlite_path)]. A candidate that can't be read
    is recorded with its error rather than dropped, so a corrupt archive is
    visible instead of silently narrowing the field.

    **The stated version wins when there is one.** A mod that ships
    `ui.*.nxd` saying v1.5.1 is carrying a file that came out of a v1.5.1
    install - that's very nearly direct evidence, and stronger than any
    inference from content. Content matching is what handles the majority
    case where a mod states nothing at all.

    The ordering matters because content scoring has a real failure mode,
    measured rather than theorised. Three patch shapes, scored against the
    real Dark Knight Expansion with the true baseline at 256:

      - a patch changing rows the mod doesn't touch scores **287** - higher,
        so the true baseline still wins. This is the normal case and the
        reason the heuristic works at all.
      - a patch changing only fields the mod also changes scores **256** -
        a tie, and harmless, because the versions don't differ anywhere the
        answer could change.
      - a patch that coincidentally sets a field to exactly what the mod set
        it to scores **255** - *lower*, so the wrong version looks like a
        better fit, and the mod's deliberate edit would drop out of the
        merge entirely.

    That last case is rare and costs one field, but it's why a stated
    version isn't overruled by arithmetic. When the two disagree, both are
    reported rather than one being resolved away silently.
    """
    choice = BaselineChoice(hint_version=hint_version, hint_source=hint_source)
    for version, path in candidates:
        entry = BaselineCandidate(version=version, sqlite_path=Path(path))
        try:
            entry.score = score_baseline(Path(path), mod_sqlite)
        except Exception as exc:  # noqa: BLE001 - one bad archive shouldn't end the search
            entry.error = str(exc)
        choice.candidates.append(entry)

    usable = [c for c in choice.candidates if c.usable]
    if not usable:
        return choice

    best = min(c.score for c in usable)
    choice.ties = [c for c in usable if c.score == best]

    stated = next((c for c in usable if c.version == hint_version), None) if hint_version else None
    if stated is not None:
        choice.chosen = stated
        choice.hint_agreed = stated in choice.ties
        return choice

    # Nothing stated, or the stated version isn't among the saved ones.
    # Best fit, with the newest breaking a tie - newest because a mod is
    # more likely to have been built against a recent release, and because
    # among tied candidates the choice provably can't change the result.
    choice.chosen = max(choice.ties, key=lambda c: _version_sort_key(c.version))
    return choice


def _version_sort_key(version: str) -> tuple:
    """
    Orders version strings numerically, so v1.5.10 sorts after v1.5.9.

    Plain string comparison gets that backwards, and a game that reaches a
    two-digit patch number is not a far-fetched scenario.
    """
    digits = []
    current = ""
    for char in version:
        if char.isdigit():
            current += char
        elif current:
            digits.append(int(current))
            current = ""
    if current:
        digits.append(int(current))
    return (tuple(digits), version)


def nxd_filename_for_table(game_nxd_dir, table: str) -> Optional[str]:
    """
    The `.nxd` filename a table came from, found by asking the game's own
    folder.

    The export path used to look this up in `NXD_ALL_STAGED_FILENAMES`,
    which is a list of 37 - so a merged table outside it produced a file
    that FF16Tools wrote and export then never copied. `uibuttonguide.nxd`
    and `uiannounce.nxd` went missing from an exported mod that way, and
    they were only the two anyone happened to try: the same hole covered
    every one of the other ~525 tables.

    Asking the directory is the same reasoning as resolve_table_name going
    to the database. The filenames are right there, with the right case, and
    no naming rule has to be invented or kept in sync.
    """
    if not game_nxd_dir:
        return None
    directory = Path(game_nxd_dir)
    if not directory.is_dir():
        return None
    wanted = table.lower()
    for path in directory.glob("*.nxd"):
        if _candidate_table_name(path.name) == wanted:
            return path.name
    return None
