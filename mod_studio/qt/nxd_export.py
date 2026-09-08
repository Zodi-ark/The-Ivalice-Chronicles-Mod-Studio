"""
Writing name, description and override edits into a mod's `.nxd` files.

**This is not an optional extra.** Every per-language text layer lives in
`.nxd` - ability and item names and descriptions, unit names, poaching, the
ability override layer and encounter rows - and so does everything Game
Updates' Review My Changes hands back after a patch. Without this the Qt
interface could edit all of it and export none of it, so Review My Changes
dead-ended: an author picked what they wanted from the new patch, loaded it
into Edit Game Data, and then had no way to get it out.

The Tkinter interface has done this since the beginning
(`gui/step_export.py`). This is the same pipeline, in the shape the Qt side
uses - a `Worker` on a `QThread` rather than a raw thread and a queue.

    stage a copy of the working database   (never the original)
    apply each edit store to the copy      (only the languages touched)
    run FF16Tools sqlite-to-nxd            (only the tables touched)
    copy the produced .nxd into the mod

**Not verified here.** `sqlite-to-nxd` is a Windows binary, so the last two
steps have never run in this environment. Everything above them is pure
Python against SQLite and is exercised by `dev/test_qt_nxd_export.py`
against a real converted database. The split is deliberate: the part that
can be tested is tested, and the part that cannot says so.

Ordering rules that are not obvious and are not negotiable:

- **Encounter rows: rekey, then drop, then edit.** Edits are keyed by ORIGIN
  address, so they have to be translated through the rekeys to find the rows
  they now belong to. Doing it in any other order edits whichever row
  happens to be sitting at the address.
- **Dropped rows are not topped back up from vanilla.** A `.nxd` replaces
  the game's file wholesale and rows cannot be added in a way the game
  picks up, so dropping a row is how an author frees an address to
  repurpose. Restoring it undoes half of that.
- **The output folder is emptied before the converter runs.** It is a fixed
  path reused by every export and `copy_nxd_files` takes whatever it finds
  under each expected name, so a file FF16Tools failed to regenerate would
  be silently copied from a previous export - and the "didn't produce"
  check below would see it present and say nothing. Same shape as the
  staging bug that shipped one mod's abilities inside another.
"""
from __future__ import annotations

from pathlib import Path

from .. import constants as c
from .. import ff16tools, migration, modconfig, nxd_data, paths
from .workers import Worker


def entry_rowset_note(rekeys: dict, dropped: list) -> str:
    """What happened to the encounter row set, in a sentence."""
    parts = []
    if rekeys:
        parts.append(f"{len(rekeys)} row(s) moved to a new address")
    if dropped:
        parts.append(f"{len(dropped)} row(s) removed")
    return ("Encounter table: " + ", ".join(parts)
            + ". The row count stays at the game's own." if parts else "")


class NxdExportWorker(Worker):
    """
    Applies every `.nxd`-backed edit store and converts the result.

    Takes snapshots of the stores rather than the stores themselves. They
    are the page's own state and must not be read from a background thread
    while the user carries on editing.
    """

    def __init__(self, state, mod_root: Path, mode: str):
        super().__init__()
        self.mod_root = Path(mod_root)
        self.mode = mode
        self.sqlite_source = state.nxd_sqlite_path
        self.cli_path = state.ff16tools_cli_path
        self.game_nxd = (Path(state.unpacked_game_dir) / "nxd"
                         if getattr(state, "unpacked_game_dir", None) else None)

        # Every registered per-language table, snapshotted by registry key.
        # `nxd_langs`/`nxd_edits` are what the export actually iterates; the
        # four named attributes below are kept because tests and the review
        # read them, and they are views on the same snapshot rather than a
        # second copy that could disagree with it.
        self.nxd_langs = {
            key: list(state.touched_nxd_languages(key))
            for key in nxd_data.ALL_NXD_SPECS
        }
        self.nxd_edits = {
            key: {lang: dict(edits) for lang, edits in state.nxd_edits_for(key).items()}
            for key in nxd_data.ALL_NXD_SPECS
        }
        self.ability_langs = self.nxd_langs["ability"]
        self.item_langs = self.nxd_langs["item"]
        self.chara_langs = self.nxd_langs["chara_name"]
        self.poach_langs = self.nxd_langs["poach"]
        self.job_langs = self.nxd_langs["job"]
        self.override_touched = state.override_touched()
        self.entry_touched = bool(state.entry_edits or state.entry_rekeys
                                  or state.entry_dropped)

        self.override_edits = dict(state.override_action_edits)
        self.ability_edits = self.nxd_edits["ability"]
        self.item_edits = self.nxd_edits["item"]
        self.chara_edits = self.nxd_edits["chara_name"]
        self.poach_edits = self.nxd_edits["poach"]
        self.job_edits = self.nxd_edits["job"]
        self.entry_edits = dict(state.entry_edits)
        self.entry_rekeys = dict(state.entry_rekeys)
        self.entry_dropped = list(state.entry_dropped)
        self.unmodelled = {name: dict(rows) for name, rows
                           in (getattr(state, "unmodelled_table_edits", None)
                               or {}).items() if rows}

    def has_work(self) -> bool:
        return bool(any(self.nxd_langs.values()) or self.override_touched
                    or self.entry_touched or self.unmodelled)

    def apply_edits(self, staged_sqlite: Path) -> None:
        """
        Everything up to the converter - pure Python, and testable.

        Separate from `run()` for exactly that reason: this half can be
        driven against a real database with no Windows binary anywhere near
        it, and it is where all the ordering rules live.
        """
        # Every registered table, in registry order. Adding one needs no
        # change here - which is the point, because the previous shape was
        # four near-identical loops and a fifth would have been a fifth copy.
        for key, langs in self.nxd_langs.items():
            for lang in langs:
                nxd_data.write_nxd_edits(
                    staged_sqlite, key, lang,
                    self.nxd_edits[key].get(lang, {}))
        if self.override_touched:
            nxd_data.write_override_action_edits(
                staged_sqlite, self.override_edits)
        if self.entry_touched:
            # Move, then drop, then edit. See the module docstring.
            nxd_data.apply_override_entry_rekeys(
                staged_sqlite, self.entry_rekeys)
            nxd_data.delete_override_entry_rows(
                staged_sqlite, self.entry_dropped)
            nxd_data.write_override_entry_edits(
                staged_sqlite,
                nxd_data.translate_entry_edits(
                    self.entry_edits, self.entry_rekeys))
            note = entry_rowset_note(self.entry_rekeys, self.entry_dropped)
            if note:
                self.log.emit(note)

    def tables_to_convert(self) -> list:
        tables = []
        for key, langs in self.nxd_langs.items():
            tables += nxd_data.tables_to_reexport_for(key, langs)
        # The two shared tables, which belong to no single language.
        if self.override_touched:
            tables.append(c.NXD_OVERRIDE_ACTION_TABLE)
        if self.entry_touched:
            tables.append(c.NXD_OVERRIDE_ENTRY_TABLE)
        tables += sorted(self.unmodelled)
        return tables

    def filenames_to_copy(self) -> list:
        """
        Which `.nxd` each touched table becomes.

        Merged tables are looked up in the game's own nxd folder rather than
        in a fixed list. The list only had 37 names in it, so anything
        merged outside it was converted and then silently not copied -
        which is how `uibuttonguide.nxd` and `uiannounce.nxd` went missing
        from an export that reported them merged.
        """
        names = []
        for key, langs in self.nxd_langs.items():
            names += nxd_data.filenames_for(key, langs)
        if self.override_touched:
            names.append(c.NXD_OVERRIDE_ACTION_FILENAME)
        if self.entry_touched:
            names.append(c.NXD_OVERRIDE_ENTRY_FILENAME)

        lower_to_name = {name.lower(): name
                         for name in c.NXD_ALL_STAGED_FILENAMES}
        for table_name in sorted(self.unmodelled):
            found = migration.nxd_filename_for_table(self.game_nxd, table_name)
            if found is None:
                # No game folder to ask, or the game has no such file. Fall
                # back to the old list, then to the obvious construction, so
                # a missing game folder degrades rather than dropping a file.
                candidate = table_name.replace("-", ".").lower() + ".nxd"
                found = lower_to_name.get(candidate, candidate)
            names.append(found)
        return names

    def run(self) -> dict:
        """
        **Returns the result; does not emit `finished` itself.**

        `Worker.start()` emits `finished` with whatever `run()` returns, so
        a worker that also emits it directly fires the signal TWICE - once
        with its result and once with the `None` it fell off the end with.
        The page's handler then ran a second time on `None` and raised
        `AttributeError: 'NoneType' object has no attribute 'get'`, after
        the export had already succeeded.

        Failures raise for the same reason: `start()` turns an exception
        into `failed` and logs the traceback. Emitting `failed` and
        returning would send both `failed` AND `finished(None)`.
        """
        if not self.has_work():
            return {"written": 0, "skipped": []}
        if self.sqlite_source is None or self.cli_path is None:
            missing = []
            if self.sqlite_source is None:
                missing.append("a converted game database")
            if self.cli_path is None:
                missing.append("FF16Tools.CLI.exe")
            # Reported, never silently dropped: the whole point of this
            # class is that these edits stop disappearing.
            raise RuntimeError(
                "Name/description and override edits exist but weren't "
                "exported - missing " + " and ".join(missing)
                + " (set them up in General Setup, then Generate again).")

        staging_dir = paths.local_data_dir() / "nxd_export_staging"
        self.log.emit("Staging a copy of the game database...")
        staged_sqlite = nxd_data.stage_sqlite_copy(
            self.sqlite_source, staging_dir)
        self.apply_edits(staged_sqlite)

        skipped = []
        if self.unmodelled:
            missing = nxd_data.tables_missing_from(
                staged_sqlite, list(self.unmodelled))
            for table_name in missing:
                # No fetch-from-game fallback here yet, unlike Tkinter.
                # Said out loud rather than converted into a silent gap.
                self.unmodelled.pop(table_name, None)
                skipped.append(table_name)
                self.log.emit(
                    f"{table_name} isn't in this database, so changes to it "
                    f"were left out. Your original file is unchanged.")
            for table_name, rows in self.unmodelled.items():
                applied = nxd_data.write_unmodelled_table_edits(
                    staged_sqlite, table_name, rows)
                if applied < len(rows):
                    self.log.emit(
                        f"{table_name}: {len(rows) - applied} row(s) your mod "
                        f"changed no longer exist in this version of the game "
                        f"and were left out.")

        tables = self.tables_to_convert()
        output_nxd_dir = staging_dir / "nxd_out"
        output_nxd_dir.mkdir(parents=True, exist_ok=True)
        # Emptied first. See the module docstring - a stale file here would
        # be copied into the mod and reported as a success.
        for stale in output_nxd_dir.glob("*.nxd"):
            try:
                stale.unlink()
            except OSError:
                pass

        self.log.emit(f"Converting back to .nxd: {', '.join(tables)}")
        code = ff16tools.run_sqlite_to_nxd(
            self.cli_path, staged_sqlite, output_nxd_dir, tables=tables,
            line_cb=self.log.emit)
        if code != 0:
            raise RuntimeError(
                f"FF16Tools sqlite-to-nxd failed (exit code {code}). "
                f"Nothing was written into your mod.")

        filenames = self.filenames_to_copy()
        copied = modconfig.copy_nxd_files(
            output_nxd_dir, filenames, self.mod_root, self.mode)
        not_produced = [name for name in filenames if name not in copied]
        if not_produced:
            raise RuntimeError(
                "FF16Tools ran but didn't produce: "
                + ", ".join(not_produced) + ".")
        return {"written": len(copied), "skipped": skipped}
