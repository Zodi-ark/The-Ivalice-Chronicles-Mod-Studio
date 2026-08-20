"""
Step 1: General Setup.

Shaped around one question: what does someone who has never modded before
have to do before they can start editing?

The answer is meant to be "press one button". FF16Tools and AudioMog now
ship bundled (see paths.bundled_tools_dir), the reference tables download
themselves, the game install is detected from Steam, and the whole
unpack -> find nxd/ -> convert to a database chain runs as a single
action. Nothing on the main page asks the user to know what a .pac file
is, where FF16Tools.CLI.exe lives, or what "nxd" means.

Everything that used to be on the main page is still here and still fully
functional - pointing at a different FF16Tools/AudioMog build, unpacking
one specific game folder, converting an nxd/ folder by hand, opening a
database someone handed you - it just lives under "Advanced options" now,
because none of it is something a first-time user should have to read past
to get started.

Layout, top to bottom:
  - Open an Existing Mod - the "I already have a mod" shortcut, first
    because it skips everything else on the page.
  - Reference Tables - downloads itself on arrival; only a status line and
    an update button are shown.
  - Game Files - detect the install, tick what you want to be able to
    edit, press one button.
  - Reloaded-II - detected from its own launcher config where possible.
  - Advanced options (collapsed) - every manual control.
  - Details (collapsed) - the running log.
"""

from __future__ import annotations

import queue
import threading
import time
import tkinter as tk
from pathlib import Path
from typing import Optional
from tkinter import filedialog, messagebox, ttk

from .. import ability_names as an
from .. import audiomog
from .. import constants as c
from .. import ui_settings
from .. import (
    fetcher,
    ff16tools,
    game_install,
    item_xml_io,
    migration,
    modconfig,
    nxd_data,
    paths,
    reloaded,
    version_archive,
    xml_io,
)
from .app import WizardStepFrame
from .step_editor import ScrollableFrame

READY_MARK = "\u2713"      # check mark
PENDING_MARK = "\u2014"    # em dash
WARN_MARK = "\u26a0"       # warning sign

MUTED = "#555555"


def _merge_keyed_edits(base: dict, newer: dict) -> dict:
    """
    {key: {field: value}} merged one field at a time, `newer` winning.

    Per-field rather than per-key on purpose: a session edit to one field of
    a row must not discard the mod's other edits to that same row.
    """
    merged = {key: dict(fields) for key, fields in base.items()}
    for key, fields in newer.items():
        merged.setdefault(key, {}).update(fields)
    return merged


def _compose_entry_rekeys(recovered: dict, session: dict) -> dict:
    """
    Combines the moves a mod's own file turned out to contain with any the
    user made during this session, both keyed by a row's origin address.

    Composition, not a plain merge, because the two can be keyed against
    *different* databases. The sequence that makes this real: open a mod
    with no game files, so the mod's own database becomes the working one
    and its rows already sit at their moved addresses; move one of them
    again by hand; then unpack. Recovery now runs against vanilla and says
    "(128,0) became (95,0)", while the session says "(95,0) became (96,0)"
    - and (95,0) is not an address vanilla has at all. Chaining them gives
    the correct single move, (128,0) -> (96,0). Merging them would have
    left a rekey anchored to a row that doesn't exist in the new baseline,
    silently dropping the user's move.
    """
    destination_to_origin = {dest: origin for origin, dest in recovered.items()}
    composed = dict(recovered)
    for address, destination in session.items():
        origin = destination_to_origin.get(address, address)
        composed[origin] = destination
    # A row chained back to where it started isn't a move at all.
    return {origin: dest for origin, dest in composed.items() if origin != dest}


def _merge_language_edits(base: dict, newer: dict) -> dict:
    """The same, one level deeper, for {language: {key: {field: value}}}."""
    merged = {lang: {k: dict(v) for k, v in rows.items()} for lang, rows in base.items()}
    for lang, rows in newer.items():
        merged[lang] = _merge_keyed_edits(merged.get(lang, {}), rows)
    return merged


class CollapsiblePane(ttk.Frame):
    """
    A labelled section that starts collapsed and expands when clicked.

    Used to keep the advanced controls (and the log) off the page without
    removing them, so the main flow stays short enough to take in at a
    glance. Put widgets in .inner.
    """

    def __init__(self, parent, title: str, subtitle: str = "", start_open: bool = False):
        super().__init__(parent)
        self._open = tk.BooleanVar(value=start_open)
        self._title = title

        header = ttk.Frame(self)
        header.pack(fill="x")
        self._toggle = ttk.Button(header, style="Compact.TButton", command=self.toggle)
        self._toggle.pack(side="left")
        if subtitle:
            ttk.Label(header, text=subtitle, foreground=MUTED).pack(side="left", padx=(10, 0))

        self.inner = ttk.Frame(self, padding=(14, 10, 0, 0))
        self._sync()

    def toggle(self) -> None:
        self._open.set(not self._open.get())
        self._sync()

    def _sync(self) -> None:
        arrow = "\u25be" if self._open.get() else "\u25b8"   # down / right triangle
        self._toggle.configure(text=f"{arrow}  {self._title}")
        if self._open.get():
            self.inner.pack(fill="both", expand=True)
        else:
            self.inner.forget()


class SetupStep(WizardStepFrame):
    # How many queued messages one event-loop tick will process. FF16Tools
    # emits a log line per extracted file, so a full unpack queues tens of
    # thousands; draining all of them in a single tick is what made the
    # window stop responding. Anything left over is picked up on the next
    # tick a millisecond later.
    _MAX_MESSAGES_PER_TICK = 200

    # How many lines the Details log keeps. Enough to cover any plausible
    # troubleshooting scrollback without letting the widget grow unbounded.
    _MAX_LOG_LINES = 2000

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self._queue: queue.Queue = queue.Queue()
        self._tables_loaded_once = False
        self._autodetect_done = False
        self._pack_folder_choices: list = []

        ttk.Label(self, text="General Setup", style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            self,
            style="SubHeader.TLabel",
            wraplength=780,
            justify="left",
            text=(
                "Editing a mod? Open it below and you're done. Starting fresh? Unpack your game "
                "files to edit game data."
            ),
        ).pack(anchor="w", pady=(4, 12))

        scroll = ScrollableFrame(self)
        scroll.pack(fill="both", expand=True)
        body = scroll.inner

        self._build_open_mod_section(body)
        ttk.Separator(body, orient="horizontal").pack(fill="x", pady=(4, 16))
        ttk.Label(
            body, text="Or, set up a new mod from scratch:", font=("Segoe UI", 10, "italic"),
            foreground="#666666",
        ).pack(anchor="w", pady=(0, 12))

        self._build_game_files_section(body)
        self._build_reloaded_section(body)
        self._build_advanced_section(body)
        self._build_log_section(body)

        self._auto_detect_bundled_tools()
        self._refresh_reloaded_label()
        self._refresh_cli_label()
        self._refresh_nxd_label()
        self._refresh_audiomog_label()
        self._refresh_readiness()
        self._poll_queue()

    # =========================================================================
    # Open an existing mod
    # =========================================================================

    def _build_open_mod_section(self, parent) -> None:
        box = ttk.LabelFrame(parent, text="Open an Existing Mod", padding=12)
        box.pack(fill="x", pady=(0, 4))
        ttk.Label(
            box,
            wraplength=760,
            justify="left",
            foreground=MUTED,
            text=(
                "Open a mod to keep working on it - its edits load back in ready to change.\n"
                "To edit game data, unpack your game files below."
            ),
        ).pack(anchor="w", pady=(0, 8))

        self.open_mod_status_var = tk.StringVar(value="No mod opened - starting a new mod.")
        ttk.Label(box, textvariable=self.open_mod_status_var, wraplength=760, justify="left").pack(
            anchor="w", pady=(0, 8)
        )
        ttk.Button(box, text="Open Existing Mod...", command=self._browse_for_existing_mod).pack(
            anchor="w"
        )

    def _browse_for_existing_mod(self) -> None:
        if (self.app.state_data.edits or self.app.state_data.job_command_edits) and not messagebox.askyesno(
            "Open Existing Mod",
            "Opening a mod will replace your current unsaved job and job command edits in this "
            "session. Continue?",
        ):
            return

        chosen = filedialog.askdirectory(
            title="Select the mod's folder (containing ModConfig.json)",
            initialdir=self._default_mod_browse_dir(),
        )
        if not chosen:
            return
        mod_root = Path(chosen)

        try:
            existing = modconfig.open_existing_mod(mod_root)
        except (FileNotFoundError, ValueError, OSError) as exc:
            messagebox.showerror("Couldn't Open Mod", str(exc))
            return
        except Exception as exc:  # noqa: BLE001 - e.g. malformed JSON/XML
            messagebox.showerror("Couldn't Open Mod", f"That mod's files couldn't be read: {exc}")
            return

        state = self.app.state_data
        # Everything from whatever mod was open before goes first. Without
        # this the previous mod's game data edits survived into the new one
        # and won every conflict - see clear_opened_mod_content.
        state.clear_opened_mod_content()
        # And the previous mod's converted database, which is written to a
        # fixed path: leaving it there meant a mod whose own .nxd couldn't
        # be converted silently inherited the last one's.
        stale_db = paths.local_data_dir() / "mod_data.sqlite"
        try:
            stale_db.unlink(missing_ok=True)
        except OSError:
            pass

        state.loaded_mod_root = existing.mod_root
        state.loaded_mod_config = existing.config
        state.loaded_game_mode = (
            existing.game_mode or existing.job_command_game_mode or existing.table_game_mode
        )
        state.edits = existing.edits
        state.job_command_edits = existing.job_command_edits
        state.job_command_preserved = existing.job_command_preserved
        state.job_preserved = existing.job_preserved
        state.table_preserved = existing.table_preserved
        # Items, shops, Treasure Hunter and the ability effect/animation
        # tables all live in one dict keyed the same way item_xml_io does.
        state.item_table_edits = dict(existing.table_edits)

        mod_name = existing.config.get("ModName", existing.mod_root.name)
        # Only what the mod actually has. Announcing the absence of
        # particular files by name - "no JobData.xml yet, no
        # JobCommandData.xml yet" - told a texture pack's author about two
        # filenames they have no reason to care about, and read especially
        # oddly directly before "plus 3708 texture(s) replaced". A mod that
        # doesn't edit jobs isn't missing anything; it just isn't that kind
        # of mod.
        details = []
        if existing.game_mode is not None:
            job_detail = f"{len(existing.edits)} job(s) of Job Data from '{existing.game_mode}'"
            if existing.other_modes_found:
                job_detail += f" (also has {', '.join(existing.other_modes_found)}, not touched)"
            details.append(job_detail)
        if existing.job_command_game_mode is not None:
            cmd_detail = (
                f"{len(existing.job_command_edits)} job command(s) from "
                f"'{existing.job_command_game_mode}'"
            )
            if existing.job_command_other_modes_found:
                cmd_detail += f" (also has {', '.join(existing.job_command_other_modes_found)}, not touched)"
            details.append(cmd_detail)

        if existing.table_edits:
            loaded_counts = ", ".join(
                f"{len(rows)} {key.replace('_', ' ')}" for key, rows in sorted(existing.table_edits.items())
            )
            details.append(loaded_counts)

        # Replaced textures and sounds are whole files sitting at their real
        # game paths, so they only need finding, not diffing - no game files
        # required, unlike the .nxd recovery started below.
        recovered_files = modconfig.recover_replaced_files(existing.mod_root)
        self._apply_recovered_files(recovered_files)
        if not recovered_files.is_empty():
            details.append(f"{recovered_files.summary()} replaced")

        # A mod with nothing this tool reads back is a normal thing to open -
        # say so, rather than leaving an empty sentence.
        detail = ("; ".join(details) + "." if details
                  else "nothing this tool edits yet - it's ready for whatever you add.")
        self.open_mod_status_var.set(f"Opened '{mod_name}' - {detail}")
        self._log(f"Opened existing mod: {existing.mod_root}")
        self._log(detail)

        # Ability/item text, encounters and poaching were exported as whole
        # .nxd binaries, so recovering them means converting the mod's .nxd
        # back to SQLite and diffing it against vanilla - which needs both
        # FF16Tools and an unpacked game, and takes long enough to belong on
        # a worker thread.
        self._nxd_recovery_pending_for = None
        self._start_nxd_recovery(existing.mod_root)

    def _apply_recovered_files(self, recovered) -> None:
        """
        Loads a mod's replaced textures and sounds into the editor.

        Textures go into texture_edits marked `already_staged`, so the
        Textures tab shows them as replacements you can view or swap, and
        Export copies them straight through instead of decoding and
        re-encoding an image that is already in the exact target format.

        Sounds and anything else are held as whole-file replacements. A
        repacked .sab doesn't say which track changed or what it came from,
        so claiming those are editable would be a lie; they're carried
        through untouched instead.
        """
        from .. import texture_data as td

        state = self.app.state_data
        for relative_path, source in recovered.textures.items():
            state.texture_edits[relative_path] = {
                "source_path": source,
                "is_face_texture": td.is_face_texture(relative_path),
                "already_staged": True,
            }
        state.sound_file_replacements = dict(recovered.sounds)
        state.other_file_replacements = dict(recovered.other)

        # Force a rescan so the tabs pick up the newly staged entries.
        state.texture_tree = None
        state.sound_tree = None

        if not recovered.is_empty():
            self._log(f"Loaded this mod's replaced files: {recovered.summary()}.")
        if recovered.sounds:
            self._log(
                "Replaced sound archives are kept exactly as they are - a repacked .sab doesn't "
                "record which track was swapped or where it came from, so they can't be reopened "
                "as per-track edits."
            )

    def _archive_this_version(self, nxd_dir: Path, sqlite_path: Path, source_name: str) -> None:
        """
        Keeps a copy of this game version's .nxd files, so a mod built now
        can still be migrated after the game patches.

        Timing matters: once the player updates, the old data is gone from
        their disk and there is nowhere to download it from, so the only
        moment this copy can be taken is while it's still installed. It
        runs on the unpack worker thread, straight after conversion,
        because that's the first point at which the version string is
        readable.

        Every failure here is logged and swallowed. Archiving is insurance
        against a future problem; it must never be the reason a successful
        unpack reports as failed.
        """
        try:
            version = migration.read_game_version(sqlite_path)
            entry = version_archive.archive_unpacked_nxd(
                nxd_dir, version, source=source_name,
                clean_unpack=not self._included_mod_packs(),
                sqlite_path=sqlite_path,
                converter=version_archive.converter_fingerprint(
                    self.app.state_data.ff16tools_cli_path
                ),
            )
            if entry is None:
                return
            if entry.version_unknown:
                self._queue.put(("log", (
                    "Archived this version's game data, but couldn't read the game's "
                    "version string, so it's filed by date. You can rename it later if "
                    "you know which build it was."
                )))
            else:
                self._queue.put(("log", (
                    f"Archived {entry.file_count} game data file(s) as {entry.version} "
                    f"({entry.size_mb:.1f} MB) so mods built on it can be updated after "
                    f"the game patches."
                )))
            self._prune_version_archive(version or "")
        except Exception as exc:  # noqa: BLE001 - insurance must never break the unpack
            self._queue.put(("log", f"Couldn't archive this version's game data: {exc}"))

    def _included_mod_packs(self) -> bool:
        """
        Whether this unpack took in any pack that looks like an installed
        mod. Recorded with the archive because a baseline mixed with mod
        content makes every diff drawn against it wrong - see the
        modded.pac section in HANDOFF.md. Unknown counts as "not clean",
        since claiming a baseline is clean when we can't tell is the
        dangerous direction to guess.
        """
        selected = getattr(self, "_selected_pack_paths", None)
        if not selected:
            return False
        try:
            return any(game_install.looks_like_mod_pack(Path(p).name) for p in selected)
        except Exception:  # noqa: BLE001
            return True

    def _prune_version_archive(self, installed_version: str) -> None:
        """
        Removes archived versions nothing depends on any more.

        Deliberately timid. A deleted archive can't be recreated - the game
        build it came from isn't installed any more - so a version is only
        a candidate once no mod in the Mods folder claims it AND it's
        outside the most recent few. At roughly 4 MB each that ceiling is
        generous on purpose.
        """
        state = self.app.state_data
        try:
            if state.reloaded_ii_path:
                mods_dir = reloaded.effective_mods_folder(Path(state.reloaded_ii_path))
            else:
                mods_dir = reloaded.configured_mods_folder()
        except Exception:  # noqa: BLE001
            mods_dir = None
        try:
            in_use = version_archive.versions_in_use(mods_dir, installed_version)
            plan = version_archive.plan_prune(in_use)
            if not plan.remove:
                return
            removed = version_archive.apply_prune(plan)
            if removed:
                self._queue.put(("log", (
                    f"Removed {len(removed)} archived game version(s) no mod needs any "
                    f"more: {', '.join(removed)}."
                )))
        except Exception as exc:  # noqa: BLE001
            self._queue.put(("log", f"Couldn't tidy the version archive: {exc}"))

    def _start_nxd_recovery(self, mod_root: Path) -> None:
        nxd_dirs = sorted((mod_root / "FFTIVC" / "data").glob("*/nxd")) if (
            mod_root / "FFTIVC" / "data").is_dir() else []
        nxd_dirs = [d for d in nxd_dirs if any(d.glob("*.nxd"))]
        if not nxd_dirs:
            return  # nothing to recover; the XML tables above were the whole mod

        state = self.app.state_data
        cli_path = state.ff16tools_cli_path
        if cli_path is None:
            self._log("Skipping .nxd recovery: FF16Tools.CLI isn't available.")
            return

        source_dir = nxd_dirs[0]
        # Converting the mod's own .nxd needs FF16Tools and nothing else -
        # no game files. So this runs either way, and what changes is only
        # what can be done with the result:
        #
        #   with a vanilla database - diff the two, so every tab shows the
        #   mod's values *and* marks which fields it changed;
        #
        #   without one - there's nothing to diff against, but the mod's own
        #   database is still a complete, correct picture of the mod, so it
        #   becomes the working database. The tabs then show and edit the
        #   mod's real values instead of refusing to open. The only thing
        #   missing is the green "changed from vanilla" markers, which is a
        #   far smaller loss than not being able to edit at all.
        vanilla_sqlite = state.nxd_sqlite_path
        if vanilla_sqlite is None:
            self._nxd_recovery_pending_for = mod_root   # diff once game files arrive
        self._log(f"Reading this mod's game data from {source_dir}...")
        self.setup_status_var.set("Reading this mod's game data...")

        def worker():
            try:
                staging_root = paths.local_data_dir() / "mod_nxd_staging"
                # Everything the mod ships, not just the tables with tabs.
                # A mod carries a handful of .nxd, so this is cheap, and it
                # is what lets the Game Updates page say something true
                # about files like uibuttonguide.nxd instead of reporting an
                # unreadable table as unchanged.
                found = nxd_data.prepare_staging_folder(
                    source_dir, staging_root, include_all=True)
                if not found:
                    self._queue.put(("log", "No recognised .nxd files in this mod - nothing to load."))
                    self._queue.put(("nxd_recovery_done", None))
                    return

                modded_sqlite = paths.local_data_dir() / "mod_data.sqlite"
                if modded_sqlite.exists():
                    modded_sqlite.unlink()
                code = ff16tools.run_nxd_to_sqlite(
                    cli_path, staging_root / "nxd", modded_sqlite,
                    line_cb=lambda line: self._queue.put(("log", line)),
                )
                if code != 0 or not modded_sqlite.exists():
                    self._queue.put((
                        "log", f"Couldn't convert this mod's .nxd files (exit code {code})."
                    ))
                    self._queue.put(("nxd_recovery_done", None))
                    return

                self._queue.put(("mod_sqlite_ready", str(modded_sqlite)))

                if vanilla_sqlite is None:
                    self._queue.put(("mod_database_ready", str(modded_sqlite)))
                    return

                recovered = nxd_data.recover_edits_from_sqlite(vanilla_sqlite, modded_sqlite)
                self._queue.put(("nxd_recovery_done", recovered))
            except Exception as exc:  # noqa: BLE001 - a failure here must not block opening the mod
                self._queue.put(("log", f"Couldn't read this mod's .nxd changes: {exc}"))
                self._queue.put(("nxd_recovery_done", None))

        threading.Thread(target=worker, daemon=True).start()

    def _adopt_mod_database(self, path: Path) -> None:
        """
        Uses a mod's own converted .nxd as the working database.

        Reached when a mod is opened before any game files are unpacked. The
        mod ships complete .nxd files - the game reads them wholesale - so
        this is a valid, complete picture of that mod's game data, just
        without any record of how it differs from vanilla.

        Exporting from here rebuilds the .nxd from the mod's own data, so
        anything not touched in this session round-trips exactly as the mod
        had it.
        """
        self._adopt_sqlite(path, "from the mod you opened", trigger_pending=False)
        self.setup_status_var.set(
            f"{READY_MARK} Loaded this mod's game data - every tab is editable."
        )
        self.open_mod_status_var.set(
            self.open_mod_status_var.get()
            + " Its ability/item text, encounters and poaching are loaded from the mod's own "
              "files, so every tab is editable. Unpack your game files to also see which of "
              "those the mod changed."
        )
        self._log(
            f"Using this mod's own game data as the working database: {path}. Exporting rebuilds "
            f"from it, so untouched values stay exactly as the mod had them."
        )

    def _apply_recovered_nxd(self, recovered) -> None:
        if recovered is None:
            self.setup_status_var.set("")
            return
        state = self.app.state_data
        # Merge rather than replace, with anything already in state winning.
        #
        # This matters in one specific sequence: open a mod with no game
        # files (so its own database becomes the working one and the tabs
        # are editable), make some edits, then unpack. The diff runs at that
        # point and would otherwise overwrite the dicts, throwing away
        # everything typed in between. Nothing recovered can be newer than a
        # session edit, so session edits win on every conflict.
        state.ability_edits = _merge_language_edits(recovered.ability_edits, state.ability_edits)
        state.item_edits = _merge_language_edits(recovered.item_edits, state.item_edits)
        state.chara_name_edits = _merge_language_edits(recovered.chara_name_edits, state.chara_name_edits)
        state.poach_edits = _merge_language_edits(recovered.poach_edits, state.poach_edits)
        state.override_action_edits = _merge_keyed_edits(
            recovered.override_action_edits, state.override_action_edits
        )
        state.entry_edits = _merge_keyed_edits(recovered.entry_edits, state.entry_edits)
        # Rows the mod moved or removed. Session moves are chained onto the
        # recovered ones rather than merged - see _compose_entry_rekeys.
        state.entry_rekeys = _compose_entry_rekeys(recovered.entry_rekeys, state.entry_rekeys)
        state.entry_dropped.update(recovered.entry_dropped)

        if recovered.is_empty():
            self.setup_status_var.set("")
            self._log("This mod's .nxd files match vanilla - no game data changes to load.")
            return

        if recovered.entry_rekeys:
            self._log(
                f"This mod moves {len(recovered.entry_rekeys)} encounter row(s) to different "
                f"Key/Key2 addresses - that's how a mod gets a unit slot the game doesn't have, "
                f"since rows can't simply be added. They're shown at their new addresses in the "
                f"Encounters tab, and exporting keeps them there. Which original row became which "
                f"new one isn't recorded in a .nxd, so the pairing shown is a guess; the exported "
                f"result is the same either way."
            )
        if recovered.entry_dropped:
            self._log(
                f"Your game has {len(recovered.entry_dropped)} encounter row(s) this mod's own "
                f"file doesn't. Exporting keeps them removed, matching the mod."
            )

        summary = recovered.summary()
        self.setup_status_var.set(f"{READY_MARK} Loaded this mod's game data changes: {summary}.")
        self.open_mod_status_var.set(
            self.open_mod_status_var.get() + f" Also loaded {summary} from its game data files."
        )
        self._log(f"Loaded this mod's .nxd changes: {summary}.")

    def _default_mod_browse_dir(self):
        """
        Where "Open Existing Mod" starts browsing.

        Mods live in Reloaded-II's Mods folder, so opening the dialog in the
        user's home folder meant navigating there by hand every single time.
        Order: an explicit override from Advanced options, then whatever
        Reloaded-II's own config says it loads mods from, then nothing (let
        the dialog pick its own default).
        """
        override = self.mod_browse_dir_var.get().strip() if hasattr(self, "mod_browse_dir_var") else ""
        if override and Path(override).is_dir():
            return override

        reloaded_root = self.app.state_data.reloaded_ii_path
        if reloaded_root is not None:
            mods_folder = reloaded.effective_mods_folder(reloaded_root)
            if mods_folder.is_dir():
                return str(mods_folder)
        return None

    # =========================================================================
    # Reference tables
    # =========================================================================

    def _build_tables_section(self, parent) -> None:
        box = ttk.LabelFrame(parent, text="Reference Tables", padding=12)
        box.pack(fill="x", pady=(0, 14))
        ttk.Label(
            box,
            wraplength=720,
            justify="left",
            foreground=MUTED,
            text=(
                "Job, Job Command, Ability and Item data ship with the FFT mod loader itself, so "
                "these download on their own every time this page opens and need no game files at "
                "all. There is nothing to do here - it's only in Advanced options so you can force "
                "a re-check or see exactly what loaded. The Ready to edit box up top says if "
                "something went wrong."
            ),
        ).pack(anchor="w", pady=(0, 8))

        self.tables_status_var = tk.StringVar(value="Loading...")
        ttk.Label(box, textvariable=self.tables_status_var, wraplength=720, justify="left").pack(
            anchor="w", pady=(0, 8)
        )

        self.tables_refresh_button = ttk.Button(
            box, text="Check for updates", style="Compact.TButton", command=self._start_table_fetch
        )
        self.tables_refresh_button.pack(anchor="w")

        self.tables_summary_var = tk.StringVar(value="")
        summary_pane = CollapsiblePane(box, "What loaded")
        summary_pane.pack(fill="x", pady=(10, 0))
        ttk.Label(summary_pane.inner, textvariable=self.tables_summary_var, justify="left").pack(anchor="w")

    TABLE_CHECK_INTERVAL_SECONDS = 7 * 24 * 60 * 60   # weekly

    def _should_check_tables_online(self) -> bool:
        """
        True at most once a week. Startup used to download all 13 tables
        every single launch - see fetcher.fetch_latest_table for why that
        was wrong. These tables change rarely; weekly is far more often than
        they actually move, and "Check for updates" is always there for
        anyone who wants it now.
        """
        last = ui_settings.load().get("tables_last_checked", 0.0)
        return (time.time() - float(last or 0.0)) >= self.TABLE_CHECK_INTERVAL_SECONDS

    def _start_table_fetch(self, force: bool = True) -> None:
        self.tables_refresh_button.configure(state="disabled")
        if force:
            self.tables_status_var.set("Checking github.com/Nenkai/fftivc.utility.modloader ...")
            ui_settings.save(tables_last_checked=time.time())
        else:
            self.tables_status_var.set("Loading reference tables...")

        def worker():
            try:
                job_result = fetcher.fetch_latest_table(c.TABLE_FILENAMES["job"], force_refresh=force)
                self._queue.put(("table_progress", f"[{job_result.source}] {job_result.detail}"))
                job_records, job_version = xml_io.load_job_table(job_result.path)

                cmd_result = fetcher.fetch_latest_table(c.TABLE_FILENAMES["job_command"], force_refresh=force)
                self._queue.put(("table_progress", f"[{cmd_result.source}] {cmd_result.detail}"))
                cmd_records, cmd_version = xml_io.load_job_command_table(cmd_result.path)

                ability_result = fetcher.fetch_latest_table(c.TABLE_FILENAMES["ability"], force_refresh=force)
                self._queue.put(("table_progress", f"[{ability_result.source}] {ability_result.detail}"))
                ability_names_live = xml_io.load_ability_names(ability_result.path)
                ability_types = xml_io.load_ability_types(ability_result.path)

                item_paths, item_records, item_versions = {}, {}, {}
                for table_key, spec in item_xml_io.ALL_SPECS.items():
                    item_result = fetcher.fetch_latest_table(c.TABLE_FILENAMES[table_key], force_refresh=force)
                    self._queue.put(("table_progress", f"[{item_result.source}] {item_result.detail}"))
                    records, version = item_xml_io.load_table(item_result.path, spec)
                    item_paths[table_key] = item_result.path
                    item_records[table_key] = records
                    item_versions[table_key] = version

                self._queue.put((
                    "tables_loaded",
                    (job_result, job_records, job_version, cmd_records, cmd_version,
                     ability_names_live, ability_types, item_paths, item_records, item_versions),
                ))
            except Exception as exc:  # noqa: BLE001
                self._queue.put(("tables_error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    # =========================================================================
    # Game files - the one-button path
    # =========================================================================

    def _build_game_files_section(self, parent) -> None:
        box = ttk.LabelFrame(parent, text="Game Files", padding=12)
        box.pack(fill="x", pady=(0, 16))
        ttk.Label(
            box,
            wraplength=760,
            justify="left",
            foreground=MUTED,
            text=(
                "Most tabs need game files. This unpacks them to an editable database once per "
                "version. Game files are unmodified, only read."
            ),
        ).pack(anchor="w", pady=(0, 10))

        # -- Where the game is ------------------------------------------------
        row = ttk.Frame(box)
        row.pack(fill="x", pady=(0, 2))
        ttk.Label(row, text="Game data folder:", width=18).pack(side="left")
        self.input_dir_var = tk.StringVar()
        self.pack_folder_combo = ttk.Combobox(row, textvariable=self.input_dir_var, values=[])
        self.pack_folder_combo.pack(side="left", fill="x", expand=True, padx=8)
        self.pack_folder_combo.bind(
            "<<ComboboxSelected>>", lambda _e: self._refresh_pack_file_list()
        )
        ttk.Button(
            row, text="Browse...", style="Compact.TButton", command=self._browse_input_dir
        ).pack(side="left")

        self.detect_status_var = tk.StringVar(value="Looking for your installed game...")
        ttk.Label(
            box, textvariable=self.detect_status_var, wraplength=700, justify="left", foreground=MUTED
        ).pack(anchor="w", padx=(140, 0), pady=(0, 12))

        # -- What to unpack ---------------------------------------------------
        ttk.Label(box, text="What do you want to be able to edit?", font=("Segoe UI", 10, "bold")).pack(
            anchor="w", pady=(0, 6)
        )

        self.group_vars: dict = {}
        for group in game_install.CONTENT_GROUPS:
            var = tk.BooleanVar(value=group.default_on)
            self.group_vars[group.key] = var
            holder = ttk.Frame(box)
            holder.pack(fill="x", anchor="w", pady=(0, 6))
            ttk.Checkbutton(holder, text=group.label, variable=var).pack(anchor="w")
            ttk.Label(
                holder, text=group.detail, wraplength=700, justify="left", foreground=MUTED
            ).pack(anchor="w", padx=(22, 0))

        # -- Go ---------------------------------------------------------------
        button_row = ttk.Frame(box)
        button_row.pack(fill="x", pady=(8, 0))
        self.setup_button = ttk.Button(
            button_row, text="Unpack and Prepare Game Files", command=self._start_guided_setup
        )
        self.setup_button.pack(side="left")
        ttk.Button(
            button_row,
            text="Already unpacked it? Use that folder instead...",
            style="Compact.TButton",
            command=self._use_existing_unpacked_folder,
        ).pack(side="left", padx=(10, 0))

        self.setup_progress = ttk.Progressbar(box, mode="determinate", maximum=100)
        self.setup_progress.pack(fill="x", pady=(10, 4))
        self.setup_status_var = tk.StringVar(value="")
        ttk.Label(box, textvariable=self.setup_status_var, wraplength=740, justify="left").pack(anchor="w")

        # -- Readiness --------------------------------------------------------
        ready_box = ttk.LabelFrame(box, text="Ready to edit", padding=10)
        ready_box.pack(fill="x", pady=(12, 0))
        self.ready_tables_var = tk.StringVar()
        self.ready_data_var = tk.StringVar()
        self.ready_texture_var = tk.StringVar()
        self.ready_sound_var = tk.StringVar()
        for var in (self.ready_tables_var, self.ready_data_var,
                    self.ready_texture_var, self.ready_sound_var):
            ttk.Label(ready_box, textvariable=var, wraplength=700, justify="left").pack(
                anchor="w", pady=(0, 3)
            )

    def _refresh_readiness(self) -> None:
        """
        Says what is genuinely usable right now, checked against what's
        actually on disk rather than against "did an unpack run".

        This matters because unpacking is selective: unpacking only `nxd/`
        produces a real unpacked game folder that the data tabs can use and
        the Textures and Sounds tabs cannot. An earlier version reported
        both as ready the moment any unpack finished, which was simply
        wrong and sent people to tabs with nothing in them.
        """
        state = self.app.state_data

        # Reference tables - normally invisible (they live in Advanced now),
        # so this line is the only place a failure would ever surface.
        if state.job_records:
            self.ready_tables_var.set(f"{READY_MARK} Reference tables - loaded. Jobs, Job Commands, "
                                      f"item and unit stats and Treasure Hunter need nothing else.")
        elif WARN_MARK in self.tables_status_var.get():
            self.ready_tables_var.set(
                f"{WARN_MARK} Reference tables - couldn't be downloaded. Open Advanced options "
                f"below to retry; without them most tabs stay empty."
            )
        else:
            self.ready_tables_var.set(f"{PENDING_MARK} Reference tables - loading...")

        if state.nxd_sqlite_path is not None:
            detail = state.nxd_sqlite_source_detail
            # "(from a previous session)" adds nothing the tick mark hasn't
            # already said. Other details do carry information - "from the
            # mod you opened" is why a tab might be empty - so only this one
            # is dropped.
            if detail and detail.strip().lower().startswith("from a previous session"):
                detail = ""
            note = ""
            # The database is a separate file from the unpacked folder, so
            # deleting UnpackedGame leaves it working while Textures and
            # Sounds stop - which looks inconsistent unless it's explained.
            if state.unpacked_game_dir is None:
                note = (
                    "  The database is its own file, so it keeps working even without the "
                    "unpacked game folder."
                )
            self.ready_data_var.set(
                f"{READY_MARK} Game data - Abilities, Items, Encounters and Poaching are ready."
                + (f"  ({detail})" if detail else "") + note
            )
        else:
            self.ready_data_var.set(
                f"{PENDING_MARK} Game data - not set up yet. Needed by the Abilities, Items, "
                f"Encounters and Poaching tabs."
            )

        unpacked = state.unpacked_game_dir
        present = game_install.groups_present_in(unpacked) if unpacked else {}

        texture_folders = present.get("textures") or []
        wanted_textures = len(game_install.folders_for_groups(["textures"]))
        if not texture_folders:
            self.ready_texture_var.set(
                f"{PENDING_MARK} Textures - not unpacked yet. Only the Textures tab needs this."
            )
        elif len(texture_folders) < wanted_textures:
            self.ready_texture_var.set(
                f"{READY_MARK} Textures - partly unpacked ({', '.join(texture_folders)}). "
                f"Anything in the folders you skipped won't show up."
            )
        else:
            self.ready_texture_var.set(f"{READY_MARK} Textures - ready, browsing {unpacked}")

        if present.get("sounds"):
            self.ready_sound_var.set(f"{READY_MARK} Sounds and music - ready, browsing {unpacked}")
        else:
            self.ready_sound_var.set(
                f"{PENDING_MARK} Sounds and music - not unpacked yet. Only the Sounds tab needs this."
            )

    def _browse_input_dir(self) -> None:
        chosen = filedialog.askdirectory(title="Select the folder containing the game's .pac files")
        if not chosen:
            return
        path = Path(chosen)
        self.input_dir_var.set(str(path))
        self._refresh_pack_file_list()
        count = game_install.count_packs(path)
        if count:
            self.detect_status_var.set(f"{READY_MARK} Found {count} pack file(s) here.")
        else:
            self.detect_status_var.set(
                f"{WARN_MARK} No .pac files directly in this folder. Pick the folder that holds "
                f"them (usually a data folder inside the game's install), not the folder above it."
            )

    def _start_autodetect(self) -> None:
        """Finds the installed game and Reloaded-II off the UI thread."""
        def worker():
            try:
                packs = game_install.autodetect_pack_folders()
            except Exception as exc:  # noqa: BLE001 - detection is best-effort by design
                packs = []
                self._queue.put(("log", f"Game detection failed harmlessly: {exc}"))
            self._queue.put(("detected_packs", packs))

            if self.app.state_data.reloaded_ii_path is None:
                try:
                    found = reloaded.find_installed_reloaded()
                except Exception as exc:  # noqa: BLE001
                    found = None
                    self._queue.put(("log", f"Reloaded-II detection failed harmlessly: {exc}"))
                if found is not None:
                    self._queue.put(("detected_reloaded", str(found)))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_detected_packs(self, packs: list) -> None:
        self._pack_folder_choices = packs
        values = [str(pf.path) for pf in packs]
        self.pack_folder_combo.configure(values=values)

        if not packs:
            self.detect_status_var.set(
                "Couldn't find the game automatically. Use Browse to point at the folder holding "
                "the game's .pac files (right-click the game in Steam \u2192 Manage \u2192 Browse "
                "local files, then look for a data folder)."
            )
            return

        if not self.input_dir_var.get().strip():
            self.input_dir_var.set(values[0])
        self._refresh_pack_file_list()

        best = packs[0]
        if len(packs) == 1:
            self.detect_status_var.set(
                f"{READY_MARK} Found your installed game - {best.pack_count} pack file(s)."
            )
        else:
            self.detect_status_var.set(
                f"{READY_MARK} Found your installed game. Using the folder with the most pack files "
                f"({best.pack_count}); {len(packs) - 1} other folder(s) are in the dropdown."
            )
        self._log(f"Detected game data folder: {best.path} ({best.pack_count} packs)")

    def _use_existing_unpacked_folder(self) -> None:
        """
        For someone who already unpacked the game (with this tool before, or
        with FF16Tools directly): point at that folder and get the same end
        result as the button above, minus the unpack itself.
        """
        chosen = filedialog.askdirectory(title="Select your already-unpacked game folder")
        if not chosen:
            return
        folder = Path(chosen)
        self._set_unpacked_game_dir(folder)

        nxd_dir = folder / "nxd"
        if nxd_dir.is_dir():
            self.nxd_folder_var.set(str(nxd_dir))
            self._log(f"Found {nxd_dir} - converting it to an editable database.")
            self.setup_progress.configure(value=50)
            self.setup_status_var.set("Converting the game data into an editable database...")
            self._start_convert_nxd()
        else:
            self.setup_progress.configure(value=0)
            self.setup_status_var.set(
                f"{WARN_MARK} No nxd folder inside {folder}, so the data tabs aren't set up. "
                f"Whatever else is in there is usable - see Ready to edit above."
            )
            self._log(
                f"No nxd/ folder inside {folder}. If you unpacked with a filter that skipped nxd, "
                f"unpack again with Game data ticked."
            )
            self._refresh_readiness()

    # -- the guided run -------------------------------------------------------

    def _start_guided_setup(self) -> None:
        state = self.app.state_data
        cli_path = state.ff16tools_cli_path
        if cli_path is None:
            messagebox.showerror(
                "FF16Tools Missing",
                "FF16Tools.CLI.exe couldn't be found. It normally ships bundled in this tool's "
                "tools folder - use Advanced options below to point at a copy or download one.",
            )
            return

        input_dir = self.input_dir_var.get().strip()
        if not input_dir:
            messagebox.showerror(
                "No Game Folder",
                "Set the game data folder first - Browse to the folder holding the game's .pac files.",
            )
            return
        source = Path(input_dir)
        if not source.is_dir():
            messagebox.showerror("No Game Folder", f"That folder doesn't exist:\n{source}")
            return
        if not game_install.looks_like_pack_folder(source):
            if not messagebox.askyesno(
                "No Pack Files Found",
                f"There are no .pac files directly in:\n{source}\n\n"
                "That usually means it's the wrong folder. Try anyway?",
            ):
                return

        chosen_groups = [key for key, var in self.group_vars.items() if var.get()]
        if not chosen_groups:
            messagebox.showerror(
                "Nothing Selected", "Tick at least one thing you want to be able to edit."
            )
            return
        folders = game_install.folders_for_groups(chosen_groups)
        wants_game_data = "nxd" in folders

        output_dir = Path(self.output_dir_var.get().strip() or (paths.local_data_dir() / "UnpackedGame"))
        include_diff = bool(self.include_diff_var.get())

        self._run_setup_pipeline(
            cli_path, source, output_dir, folders, wants_game_data, include_diff,
            packs=self._resolve_packs_for_run(source),
        )

    def _resolve_packs_for_run(self, source: Path) -> Optional[list]:
        """
        Which pack files this run should read, or None meaning "all of them"
        (in which case the faster whole-folder command is used).

        The picker is built from whatever folder was selected at the time,
        so if the folder has since changed it's rebuilt here rather than
        silently applying stale tick boxes to a different game install.
        """
        current = [p.name for p in game_install.list_pack_files(source)]
        known = [p.name for p in getattr(self, "_pack_files", [])]
        if current != known:
            self.input_dir_var.set(str(source))
            self._refresh_pack_file_list()

        chosen = self._selected_pack_files()
        all_packs = getattr(self, "_pack_files", [])
        if not all_packs or len(chosen) == len(all_packs):
            return None
        return chosen

    def _run_setup_pipeline(
        self,
        cli_path: Path,
        source: Path,
        output_dir: Path,
        folders: list,
        wants_game_data: bool,
        include_diff: bool,
        packs: Optional[list] = None,
    ) -> None:
        """
        Unpack the chosen folders, then (if game data was among them) find
        the nxd/ folder and convert it - the whole chain the user used to
        have to drive by hand across three separate sections of this page.
        """
        self.setup_button.configure(state="disabled")
        self.unpack_button.configure(state="disabled")
        self.setup_progress.configure(value=0)

        filters = game_install.filters_for_folders(folders)
        # None means "everything was picked, so one unfiltered pass does it";
        # otherwise one pass per folder, since --filter takes a single value.
        passes: list = [None] if filters is None else list(filters)
        total_steps = len(passes) + (1 if wants_game_data else 0)

        def report(text: str, step: int) -> None:
            fraction = (step / total_steps) * 100 if total_steps else 100
            self._queue.put(("setup_progress", (text, fraction)))

        def make_line_handler(pass_index: int, folder_name: Optional[str]):
            """
            Turns FF16Tools' per-file chatter into progress instead of log
            traffic.

            It logs one line for every file it extracts, so a full unpack
            produces tens of thousands. Forwarding all of them starved the
            UI. Instead: count them, push a progress update every so often,
            and keep only a periodic sample in the log. Anything that isn't
            a routine "Extracting ..." line (errors, summaries, warnings) is
            always forwarded verbatim - those are the lines that matter when
            something goes wrong.
            """
            # Roughly how many files this folder holds, from a real unpacked
            # copy of the game (game_install.GAME_FOLDERS). Only used to
            # animate the bar within a pass, so being approximate is fine -
            # the count is clamped so an underestimate can't overshoot.
            expected = 0
            if folder_name and folder_name in game_install.GAME_FOLDERS_BY_NAME:
                expected = game_install.GAME_FOLDERS_BY_NAME[folder_name].approx_files
            state = {"extracted": 0, "in_folder": 0}
            label = folder_name or "everything"
            prefix = f"{folder_name}/" if folder_name else None

            def handle(line: str) -> None:
                if " Extracting '" not in line:
                    self._queue.put(("log", line))
                    return

                state["extracted"] += 1
                # Whether this file actually landed under the folder being
                # asked for. FF16Tools' --filter is a plain substring match,
                # so "ui/" also matches "bg/ui/..." - which means a pack can
                # produce files for a filter that isn't its own. Counting
                # those separately is what lets the caller tell a real match
                # from an incidental one.
                if prefix:
                    start = line.find(" Extracting '") + len(" Extracting '")
                    end = line.find("'", start)
                    if end > start and line[start:end].replace("\\", "/").startswith(prefix):
                        state["in_folder"] += 1
                count = state["extracted"]
                if count % 25:
                    return

                if expected:
                    within = min(count / expected, 1.0)
                    fraction = ((pass_index + within) / total_steps) * 100
                else:
                    fraction = (pass_index / total_steps) * 100
                self._queue.put((
                    "setup_progress",
                    (f"Unpacking {label} ({pass_index + 1} of {len(passes)}) - "
                     f"{count:,} files extracted so far...", fraction),
                ))
                if count % 500 == 0:
                    self._queue.put(("log", f"  ... {count:,} files extracted from {label}"))

            # Per-pack mode reads this to tell whether a given pack actually
            # contained anything for this filter.
            handle.extracted = lambda: state["extracted"]
            handle.in_folder = lambda: state["in_folder"]
            return handle

        def worker():
            claimed_packs: set = set()
            try:
                try:
                    output_dir.mkdir(parents=True, exist_ok=True)
                except OSError as exc:
                    self._queue.put(("setup_failed", f"Couldn't create {output_dir}: {exc}"))
                    return

                if packs is not None:
                    self._queue.put((
                        "log",
                        f"Reading {len(packs)} selected pack file(s) individually so deselected "
                        f"packs (e.g. the mod loader's own) stay out of the unpacked copy.",
                    ))

                for index, filter_text in enumerate(passes):
                    label = "everything" if filter_text is None else filter_text.rstrip("/")
                    report(
                        f"Unpacking {label} ({index + 1} of {len(passes)})... "
                        f"the first run can take a while.",
                        index,
                    )
                    self._queue.put((
                        "log",
                        f"Running: FF16Tools.CLI unpack-all-packs -i {source} -o {output_dir} -g fft"
                        + (f" --filter {filter_text}" if filter_text else "")
                        + (" --include-diff" if include_diff else ""),
                    ))
                    handler = make_line_handler(index, None if filter_text is None else label)
                    if packs is None:
                        code = ff16tools.run_unpack_all_packs(
                            cli_path, source, output_dir,
                            line_cb=handler,
                            filter_text=filter_text,
                            include_diff=include_diff,
                        )
                    else:
                        # One pack at a time, so the deselected ones (mod
                        # loader output) are simply never opened. A pack
                        # holds exactly one top-level folder, so once one
                        # has produced files for some filter there's no
                        # point offering it the remaining filters.
                        code = 0
                        for pack in packs:
                            if pack.name in claimed_packs:
                                continue
                            before = handler.in_folder()
                            code = ff16tools.run_unpack_single_pack(
                                cli_path, pack.path, output_dir,
                                line_cb=handler,
                                filter_text=filter_text,
                            )
                            if code != 0:
                                break
                            # Retire a pack only once it has produced files
                            # *for this folder*, not merely produced files.
                            #
                            # It used to be "extracted anything at all", and
                            # because --filter is a substring match the `ui/`
                            # pass matched `bg/ui/...` inside the bg pack.
                            # That pack extracted a handful of files, was
                            # marked done, and never got offered the `bg/`
                            # filter - so `bg/textures/**` was never
                            # unpacked at all. The symptom was a bg folder
                            # containing nothing but a ui folder, and
                            # textures the Textures tab then reported as
                            # "added by the mod - the game has no original".
                            if handler.in_folder() > before:
                                claimed_packs.add(pack.name)
                    self._queue.put(("log", f"Unpack pass finished with exit code {code}"))
                    if code != 0:
                        self._queue.put((
                            "setup_failed",
                            f"Unpacking failed (exit code {code}) - open Details below to see why.",
                        ))
                        return

                self._queue.put(("unpacked_dir_ready", str(output_dir)))

                if not wants_game_data:
                    self._queue.put(("setup_done", "Unpacked. Textures and Sounds are ready to use."))
                    return

                report("Converting the game data into an editable database...", len(passes))
                nxd_dir = output_dir / "nxd"
                if not nxd_dir.is_dir():
                    self._queue.put((
                        "setup_failed",
                        f"Unpacked, but no nxd folder appeared in {output_dir}, so there's no game "
                        f"data to convert. Textures and Sounds are still usable.",
                    ))
                    return

                staging_root = paths.local_data_dir() / "nxd_staging"
                # Every .nxd the game ships, not just the ones with editing
                # tabs today.
                #
                # The narrow set was a constant source of "this table isn't
                # available" behaviour that read as bugs rather than limits:
                # a mod's file couldn't be examined so it was reported as
                # unchanged, merging was restricted to an arbitrary-looking
                # list, and Compare Versions saw 5 differing tables between
                # 1.4.0 and 1.5.2 where the full data has 50. Each was fixed
                # separately; converting everything removes the class.
                #
                # Cost, measured: the database goes from 2.3 MB to 15.2 MB
                # and a full tab load from 36ms to 62ms - neither matters.
                # Conversion takes longer, which is the real price and is
                # paid once per unpack. Files FF16Tools can't handle are
                # skipped rather than fatal: converting the whole folder
                # yields 562 tables from 564 files, with
                # configitemclassictextlanguage.nxd and
                # configitemdifficultylevel.nxd producing nothing.
                found = nxd_data.prepare_staging_folder(
                    nxd_dir, staging_root, include_all=True)
                self._queue.put((
                    "log",
                    f"Converting all {len(found)} data .nxd file(s) from the game - this is the "
                    f"slow part of unpacking, and it only happens once per game version.",
                ))
                if not found:
                    self._queue.put((
                        "setup_failed",
                        "Unpacked, but there were no .nxd files in the nxd folder.",
                    ))
                    return

                sqlite_dest = paths.local_data_dir() / "fft_data.sqlite"
                code = ff16tools.run_nxd_to_sqlite(
                    cli_path, staging_root / "nxd", sqlite_dest,
                    line_cb=lambda line: self._queue.put(("log", line)),
                )
                self._queue.put(("log", f"nxd-to-sqlite finished with exit code {code}"))
                if code != 0 or not sqlite_dest.exists():
                    self._queue.put((
                        "setup_failed", f"Unpacked, but converting the data failed (exit code {code})."
                    ))
                    return

                self._archive_this_version(nxd_dir, sqlite_dest, source.name)

                self._queue.put(("nxd_ready", (str(sqlite_dest), f"converted from {source.name}")))
                self._queue.put((
                    "setup_done",
                    f"All set. Converted {len(found)} data file(s) - every tab is ready to use.",
                ))
            except Exception as exc:  # noqa: BLE001 - any failure belongs on screen, not in a traceback
                self._queue.put(("setup_failed", str(exc)))
            finally:
                self._queue.put(("enable_setup", None))

        threading.Thread(target=worker, daemon=True).start()

    # =========================================================================
    # Reloaded-II
    # =========================================================================

    def _build_reloaded_section(self, parent) -> None:
        box = ttk.LabelFrame(parent, text="Reloaded-II Installation", padding=12)
        box.pack(fill="x", pady=(0, 16))
        ttk.Label(
            box,
            wraplength=760,
            justify="left",
            foreground=MUTED,
            text=(
                "Optional, and detected automatically where possible. Setting this lets the Export "
                "step drop finished mods straight into Reloaded-II."
            ),
        ).pack(anchor="w", pady=(0, 8))

        self.reloaded_path_var = tk.StringVar()
        ttk.Label(box, textvariable=self.reloaded_path_var, foreground="#444444").pack(
            anchor="w", pady=(0, 4)
        )
        self.reloaded_status_var = tk.StringVar()
        ttk.Label(box, textvariable=self.reloaded_status_var, wraplength=760, justify="left").pack(
            anchor="w", pady=(0, 8)
        )
        ttk.Button(
            box, text="Browse for Reloaded-II folder...", style="Compact.TButton",
            command=self._browse_for_reloaded,
        ).pack(anchor="w")

    def _browse_for_reloaded(self) -> None:
        initial = self.app.state_data.reloaded_ii_path or reloaded.find_installed_reloaded()
        chosen = filedialog.askdirectory(
            title="Select your Reloaded-II folder (containing Reloaded-II.exe)",
            initialdir=str(initial) if initial else None,
        )
        if not chosen:
            return
        self._set_reloaded_path(Path(chosen), announce=True)

    def _set_reloaded_path(self, path: Path, announce: bool) -> None:
        self.app.state_data.reloaded_ii_path = path
        self._refresh_reloaded_label()
        if announce:
            looks_right = reloaded.looks_like_reloaded_install(path)
            self._log(
                f"Reloaded-II folder set to: {path}"
                + ("" if looks_right else
                   " (couldn't confirm this looks like a Reloaded-II install, but it'll be used anyway)")
            )

    def _refresh_reloaded_label(self) -> None:
        path = self.app.state_data.reloaded_ii_path
        if not path:
            self.reloaded_path_var.set("(not set)")
            self.reloaded_status_var.set("")
            return
        self.reloaded_path_var.set(str(path))

        if not reloaded.looks_like_reloaded_install(path):
            self.reloaded_status_var.set(
                f"{WARN_MARK} Doesn't look like a Reloaded-II install (no Reloaded-II.exe or Loader "
                f"folder found), but it'll still be used if you continue."
            )
            return

        message = f"{READY_MARK} Looks like a real Reloaded-II install. Mods folder: {path / 'Mods'}"
        # A non-portable install can load mods from somewhere other than
        # <install>/Mods entirely - see reloaded.configured_mods_folder.
        configured = reloaded.configured_mods_folder()
        if configured is not None:
            try:
                mismatch = configured.resolve() != (path / "Mods").resolve()
            except OSError:
                mismatch = False
            if mismatch:
                message += (
                    f"\n{WARN_MARK} Reloaded-II's own config says it loads mods from {configured} "
                    f"instead. Exported mods may not show up in the launcher unless you move them there."
                )
        self.reloaded_status_var.set(message)

    # =========================================================================
    # Advanced options
    # =========================================================================

    def _build_advanced_section(self, parent) -> None:
        pane = CollapsiblePane(
            parent,
            "Advanced options",
            subtitle="Reference tables, tool locations, per-folder unpacking, manual conversion",
        )
        pane.pack(fill="x", pady=(0, 12))
        inner = pane.inner

        self._build_tables_section(inner)
        self._build_selective_unpack(inner)
        self._build_manual_data_section(inner)
        self._build_mod_folder_section(inner)
        self._build_manual_textures_section(inner)
        self._build_ff16tools_section(inner)
        self._build_audiomog_section(inner)

    # -- selective unpack -----------------------------------------------------

    def _build_selective_unpack(self, parent) -> None:
        box = ttk.LabelFrame(parent, text="Unpack specific folders only", padding=12)
        box.pack(fill="x", pady=(0, 14))
        ttk.Label(
            box,
            wraplength=720,
            justify="left",
            foreground=MUTED,
            text=(
                "FF16Tools can extract just part of the game rather than all of it. The tick boxes "
                "up top group these into Game data / Textures / Sounds; this is the same thing at "
                "full resolution - handy when you only want portraits and icons (ui) and nothing "
                "else. Each ticked folder is a separate pass over the packs, so fewer is faster. "
                "File counts come from a real unpacked copy of the game."
            ),
        ).pack(anchor="w", pady=(0, 10))

        self._build_pack_file_picker(box)

        ttk.Label(box, text="Folders to unpack", font=("Segoe UI", 9, "bold")).pack(
            anchor="w", pady=(12, 4)
        )
        grid = ttk.Frame(box)
        grid.pack(fill="x")
        self.folder_vars: dict = {}
        for index, folder in enumerate(game_install.GAME_FOLDERS):
            var = tk.BooleanVar(value=False)
            self.folder_vars[folder.name] = var
            ttk.Checkbutton(
                grid,
                text=f"{folder.name}  -  {folder.summary}  (~{folder.approx_files:,} files)",
                variable=var,
            ).grid(row=index, column=0, sticky="w", pady=1)

        custom_row = ttk.Frame(box)
        custom_row.pack(fill="x", pady=(10, 2))
        ttk.Label(custom_row, text="Or a custom filter:", width=20).pack(side="left")
        self.custom_filter_var = tk.StringVar()
        ttk.Entry(custom_row, textvariable=self.custom_filter_var).pack(
            side="left", fill="x", expand=True, padx=8
        )
        ttk.Label(
            box,
            wraplength=720,
            justify="left",
            foreground=MUTED,
            text=(
                "A custom filter is matched as plain text anywhere in a file's path inside the pack, "
                "so \"ui/ffto/icon\" extracts only the icon folders and \"ability\" extracts every "
                "file with that word in its name. Overrides the tick boxes when filled in."
            ),
        ).pack(anchor="w", pady=(2, 10))

        out_row = ttk.Frame(box)
        out_row.pack(fill="x", pady=(0, 6))
        ttk.Label(out_row, text="Unpack into:", width=20).pack(side="left")
        self.output_dir_var = tk.StringVar(value=str(paths.local_data_dir() / "UnpackedGame"))
        ttk.Entry(out_row, textvariable=self.output_dir_var).pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(
            out_row, text="Browse...", style="Compact.TButton", command=self._browse_output_dir
        ).pack(side="left")

        self.include_diff_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            box,
            text="Also unpack .diff.pac files (installed mods) - normally leave this off",
            variable=self.include_diff_var,
        ).pack(anchor="w", pady=(4, 2))
        ttk.Label(
            box,
            wraplength=720,
            justify="left",
            foreground=MUTED,
            text=(
                ".diff.pac files are mods you already have installed. Including them means this "
                "tool's previews and reference data show someone else's modded values as if they "
                "were vanilla, which is very hard to spot later."
            ),
        ).pack(anchor="w", pady=(0, 10))

        self.unpack_button = ttk.Button(box, text="Run This Unpack", command=self._start_selective_unpack)
        self.unpack_button.pack(anchor="w")

    def _build_pack_file_picker(self, parent) -> None:
        """
        Which .pac files to read. Needed because the FFT mod loader writes
        its own packs (modded.pac, modded.en.pac, ...) into the same folder
        as the game's, and unpack-all-packs takes the whole folder - so
        without this, installed mods get unpacked over the vanilla files and
        every reference in this tool quietly shows modded values.
        """
        ttk.Label(parent, text="Pack files to read", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        ttk.Label(
            parent,
            wraplength=720,
            justify="left",
            foreground=MUTED,
            text=(
                "Packs created by the mod loader are unticked automatically, so an unpack gives "
                "you the vanilla game rather than a mix of vanilla and whatever mods you have "
                "installed. Tick one to include it anyway - useful for inspecting a mod, but not "
                "what you want as reference data."
            ),
        ).pack(anchor="w", pady=(0, 6))

        self.pack_file_vars: dict = {}
        self.pack_file_box = ttk.Frame(parent)
        self.pack_file_box.pack(fill="x")
        self.pack_summary_var = tk.StringVar(value="")
        ttk.Label(
            parent, textvariable=self.pack_summary_var, wraplength=720, justify="left"
        ).pack(anchor="w", pady=(4, 0))
        self._refresh_pack_file_list()

    def _refresh_pack_file_list(self) -> None:
        """
        Rebuilds the list for whatever folder is currently selected,
        keeping any choice the user already made for a pack of the same
        name so switching folders and back doesn't silently re-tick things.
        """
        if not hasattr(self, "pack_file_box"):
            return  # Advanced pane not built yet; it refreshes itself when it is.
        previous = {name: var.get() for name, var in getattr(self, "pack_file_vars", {}).items()}
        for child in self.pack_file_box.winfo_children():
            child.destroy()

        folder_text = self.input_dir_var.get().strip()
        packs = game_install.list_pack_files(Path(folder_text)) if folder_text else []
        if not packs:
            self.pack_file_vars = {}
            self.pack_summary_var.set("No .pac files found in the game data folder above.")
            return

        new_vars: dict = {}
        mod_count = 0
        for pack in packs:
            default_on = not pack.is_mod_output
            var = tk.BooleanVar(value=previous.get(pack.name, default_on))
            var.trace_add("write", lambda *_a: self._refresh_pack_summary())
            new_vars[pack.name] = var
            if pack.is_mod_output:
                mod_count += 1
            ttk.Checkbutton(self.pack_file_box, text=pack.label(), variable=var).pack(anchor="w")
        self.pack_file_vars = new_vars
        self._pack_files = packs
        self._refresh_pack_summary(mod_count)

    def _refresh_pack_summary(self, mod_count: Optional[int] = None) -> None:
        packs = getattr(self, "_pack_files", [])
        if not packs:
            return
        if mod_count is None:
            mod_count = sum(1 for p in packs if p.is_mod_output)
        chosen = self._selected_pack_files()
        skipped = len(packs) - len(chosen)
        if skipped:
            self.pack_summary_var.set(
                f"Reading {len(chosen)} of {len(packs)} packs; skipping {skipped}"
                + (f" (including {mod_count} created by the mod loader)" if mod_count else "")
                + ". Skipping any pack means reading them one at a time, which is a little slower."
            )
        else:
            self.pack_summary_var.set(f"Reading all {len(packs)} packs.")

    def _selected_pack_files(self) -> list:
        """The PackFile entries currently ticked, in list order."""
        packs = getattr(self, "_pack_files", [])
        return [p for p in packs if self.pack_file_vars.get(p.name) and self.pack_file_vars[p.name].get()]

    def _browse_output_dir(self) -> None:
        chosen = filedialog.askdirectory(title="Select an output folder for unpacked files")
        if chosen:
            self.output_dir_var.set(chosen)

    def _start_selective_unpack(self) -> None:
        cli_path = self.app.state_data.ff16tools_cli_path
        if cli_path is None:
            self._log("Set up FF16Tools.CLI.exe first (below).")
            return
        input_dir = self.input_dir_var.get().strip()
        if not input_dir:
            self._log("Set the game data folder up top first.")
            return

        output_dir = Path(self.output_dir_var.get().strip() or (paths.local_data_dir() / "UnpackedGame"))
        include_diff = bool(self.include_diff_var.get())

        custom = self.custom_filter_var.get().strip()
        if custom:
            self._run_custom_unpack(cli_path, Path(input_dir), output_dir, [custom], include_diff)
            return

        folders = [name for name, var in self.folder_vars.items() if var.get()]
        if not folders:
            self._log("Tick at least one folder, or type a custom filter.")
            return
        self._run_setup_pipeline(
            cli_path, Path(input_dir), output_dir, folders, "nxd" in folders, include_diff,
            packs=self._resolve_packs_for_run(Path(input_dir)),
        )

    def _run_custom_unpack(
        self, cli_path: Path, source: Path, output_dir: Path, filters: list, include_diff: bool
    ) -> None:
        self.setup_button.configure(state="disabled")
        self.unpack_button.configure(state="disabled")
        self.setup_progress.configure(value=0)

        def worker():
            try:
                output_dir.mkdir(parents=True, exist_ok=True)
                for index, filter_text in enumerate(filters):
                    self._queue.put((
                        "setup_progress",
                        (f"Unpacking files matching \"{filter_text}\"...", (index / len(filters)) * 100),
                    ))
                    extracted = {"n": 0}

                    def on_line(line: str, _f=filter_text) -> None:
                        # Same reasoning as the guided pipeline: FF16Tools
                        # logs per file, so count them into a live status
                        # line rather than queueing every one.
                        if " Extracting '" not in line:
                            self._queue.put(("log", line))
                            return
                        extracted["n"] += 1
                        if extracted["n"] % 25 == 0:
                            self._queue.put((
                                "setup_progress",
                                (f"Unpacking files matching \"{_f}\" - "
                                 f"{extracted['n']:,} extracted so far...", 50),
                            ))

                    code = ff16tools.run_unpack_all_packs(
                        cli_path, source, output_dir,
                        line_cb=on_line,
                        filter_text=filter_text,
                        include_diff=include_diff,
                    )
                    self._queue.put(("log", f"Unpack finished with exit code {code}"))
                    if code != 0:
                        self._queue.put(("setup_failed", f"Unpacking failed (exit code {code})."))
                        return
                self._queue.put(("unpacked_dir_ready", str(output_dir)))
                self._queue.put(("setup_done", f"Unpacked everything matching \"{filters[0]}\"."))
            except Exception as exc:  # noqa: BLE001
                self._queue.put(("setup_failed", str(exc)))
            finally:
                self._queue.put(("enable_setup", None))

        threading.Thread(target=worker, daemon=True).start()

    # -- manual data conversion ----------------------------------------------

    def _build_manual_data_section(self, parent) -> None:
        box = ttk.LabelFrame(parent, text="Game data database (manual)", padding=12)
        box.pack(fill="x", pady=(0, 14))
        ttk.Label(
            box,
            wraplength=720,
            justify="left",
            foreground=MUTED,
            text=(
                "Ability/Item names and descriptions, unit names, encounter data and poaching data "
                "live in .nxd files, which have to be converted into a SQLite database before they "
                "can be edited. The button up top does this for you; use these if you're converting "
                "an nxd folder you got some other way, or reusing a database from a previous "
                "session or another modder."
            ),
        ).pack(anchor="w", pady=(0, 10))

        row = ttk.Frame(box)
        row.pack(fill="x", pady=4)
        ttk.Label(row, text="Unpacked nxd folder:", width=20).pack(side="left")
        self.nxd_folder_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.nxd_folder_var).pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(
            row, text="Browse...", style="Compact.TButton", command=self._browse_nxd_folder
        ).pack(side="left")

        button_row = ttk.Frame(box)
        button_row.pack(anchor="w", pady=(8, 8))
        self.convert_nxd_button = ttk.Button(
            button_row, text="Convert to Editable Database", command=self._start_convert_nxd
        )
        self.convert_nxd_button.pack(side="left")
        ttk.Button(
            button_row, text="Open an existing database...", style="Compact.TButton",
            command=self._browse_existing_sqlite,
        ).pack(side="left", padx=(10, 0))

        self.nxd_status_var = tk.StringVar()
        ttk.Label(
            box, textvariable=self.nxd_status_var, foreground="#444444", wraplength=720, justify="left"
        ).pack(anchor="w")

    def _browse_nxd_folder(self) -> None:
        chosen = filedialog.askdirectory(title="Select the unpacked game's nxd folder")
        if chosen:
            self.nxd_folder_var.set(chosen)

    def _browse_existing_sqlite(self) -> None:
        chosen = filedialog.askopenfilename(
            title="Select a game data database (e.g. fft_data.sqlite)",
            filetypes=[("SQLite database", "*.sqlite *.db"), ("All files", "*.*")],
        )
        if not chosen:
            return
        self._adopt_sqlite(Path(chosen), "opened directly")
        self._log(f"Using game data database directly: {chosen}")

    def _adopt_sqlite(self, path: Path, detail: str, trigger_pending: bool = True) -> None:
        """
        Points every nxd-backed tab at `path` and drops whatever they'd
        already loaded, so switching databases mid-session can't leave one
        tab showing rows from the old one.
        """
        state = self.app.state_data
        state.nxd_sqlite_path = path
        state.nxd_sqlite_source_detail = detail
        state.ability_records = {}
        state.override_action_records = []
        state.item_records = {}
        state.chara_name_records = {}
        state.entry_records = []
        state.poach_records = {}
        self._refresh_nxd_label()
        self._refresh_readiness()
        # Same reason as _apply_loaded_tables: a database adopted from a
        # previous session arrives after the editor tabs were built.
        self.app.notify_data_loaded(exclude=self)

        # A mod opened before the game was unpacked has been waiting for
        # exactly this - a baseline to diff its .nxd against.
        pending = getattr(self, "_nxd_recovery_pending_for", None)
        if pending is not None and trigger_pending:
            self._nxd_recovery_pending_for = None
            self._log(f"Game data is available now - loading {pending.name}'s .nxd changes.")
            self._start_nxd_recovery(pending)

    def _refresh_nxd_label(self) -> None:
        path = self.app.state_data.nxd_sqlite_path
        if path is None:
            self.nxd_status_var.set("No database loaded yet.")
        else:
            detail = self.app.state_data.nxd_sqlite_source_detail
            self.nxd_status_var.set(f"Database ready: {path}" + (f" ({detail})" if detail else ""))

    def _start_convert_nxd(self) -> None:
        cli_path = self.app.state_data.ff16tools_cli_path
        if cli_path is None:
            self._log("Set up FF16Tools.CLI.exe first.")
            return
        folder = self.nxd_folder_var.get().strip()
        if not folder:
            self._log("Choose an unpacked nxd folder first.")
            return
        source_dir = Path(folder)
        if not source_dir.exists():
            self._log(f"Folder not found: {source_dir}")
            return

        self.convert_nxd_button.configure(state="disabled")
        self._log(f"Looking for data .nxd files in {source_dir}...")

        def worker():
            try:
                staging_root = paths.local_data_dir() / "nxd_staging"
                found = nxd_data.prepare_staging_folder(
                    source_dir, staging_root, include_all=True)
                self._queue.put((
                    "log",
                    f"Found {len(found)} data .nxd file(s) to convert.",
                ))
                if not found:
                    self._queue.put((
                        "nxd_error",
                        "No .nxd files found in that folder - double check it's the unpacked "
                        "game's nxd subfolder.",
                    ))
                    return
                sqlite_dest = paths.local_data_dir() / "fft_data.sqlite"
                self._queue.put(("log", "Running FF16Tools.CLI nxd-to-sqlite..."))
                code = ff16tools.run_nxd_to_sqlite(
                    cli_path, staging_root / "nxd", sqlite_dest,
                    line_cb=lambda line: self._queue.put(("log", line)),
                )
                self._queue.put(("log", f"nxd-to-sqlite finished with exit code {code}"))
                if code != 0 or not sqlite_dest.exists():
                    self._queue.put(("nxd_error", f"Conversion failed (exit code {code}) - see the log above."))
                    return
                self._queue.put(("nxd_ready", (str(sqlite_dest), f"converted from {source_dir}")))
            except Exception as exc:  # noqa: BLE001
                self._queue.put(("nxd_error", str(exc)))
            finally:
                self._queue.put(("enable_convert_nxd", None))

        threading.Thread(target=worker, daemon=True).start()

    # -- manual unpacked folder ----------------------------------------------

    def _build_mod_folder_section(self, parent) -> None:
        box = ttk.LabelFrame(parent, text="Where to look for mods", padding=12)
        box.pack(fill="x", pady=(0, 14))
        ttk.Label(
            box,
            wraplength=720,
            justify="left",
            foreground=MUTED,
            text=(
                "\u201cOpen Existing Mod\u201d starts browsing in your Reloaded-II Mods folder. "
                "Set a folder here to start somewhere else instead - handy if you keep works in "
                "progress outside Reloaded-II."
            ),
        ).pack(anchor="w", pady=(0, 8))

        row = ttk.Frame(box)
        row.pack(fill="x", pady=(0, 6))
        ttk.Label(row, text="Start browsing in:", width=20).pack(side="left")
        self.mod_browse_dir_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.mod_browse_dir_var).pack(
            side="left", fill="x", expand=True, padx=8
        )
        ttk.Button(
            row, text="Browse...", style="Compact.TButton", command=self._browse_mod_browse_dir
        ).pack(side="left")
        ttk.Button(
            box, text="Use my Reloaded-II Mods folder", style="Compact.TButton",
            command=lambda: self.mod_browse_dir_var.set(""),
        ).pack(anchor="w")

    def _browse_mod_browse_dir(self) -> None:
        chosen = filedialog.askdirectory(title="Select the folder your mods live in")
        if chosen:
            self.mod_browse_dir_var.set(chosen)

    def _build_manual_textures_section(self, parent) -> None:
        box = ttk.LabelFrame(parent, text="Unpacked game folder (manual)", padding=12)
        box.pack(fill="x", pady=(0, 14))
        ttk.Label(
            box,
            wraplength=720,
            justify="left",
            foreground=MUTED,
            text=(
                "The Textures and Sounds tabs read this folder directly - no conversion involved. "
                "Set automatically by the button up top; change it here to browse a different "
                "unpacked copy."
            ),
        ).pack(anchor="w", pady=(0, 8))

        row = ttk.Frame(box)
        row.pack(fill="x", pady=(0, 6))
        ttk.Label(row, text="Unpacked game folder:", width=20).pack(side="left")
        self.unpacked_game_dir_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.unpacked_game_dir_var).pack(
            side="left", fill="x", expand=True, padx=8
        )
        ttk.Button(
            row, text="Browse...", style="Compact.TButton", command=self._browse_unpacked_game_dir
        ).pack(side="left")

        self.textures_status_var = tk.StringVar(value="Not set yet.")
        ttk.Label(
            box, textvariable=self.textures_status_var, foreground="#444444", wraplength=720, justify="left"
        ).pack(anchor="w")

    def _browse_unpacked_game_dir(self) -> None:
        chosen = filedialog.askdirectory(title="Select your unpacked game folder")
        if chosen:
            self._set_unpacked_game_dir(Path(chosen))

    def _set_unpacked_game_dir(self, path: Path) -> None:
        self.unpacked_game_dir_var.set(str(path))
        self.app.state_data.unpacked_game_dir = path
        self.app.state_data.texture_tree = None  # force a rescan next time Textures is shown
        self.app.state_data.sound_tree = None    # same folder - force a rescan next time Sounds is shown
        self.textures_status_var.set(f"Unpacked game folder set: {path}")
        self._refresh_readiness()
        self._log(f"Unpacked game folder set: {path}")

    # -- FF16Tools ------------------------------------------------------------

    def _build_ff16tools_section(self, parent) -> None:
        box = ttk.LabelFrame(parent, text="FF16Tools.CLI", padding=12)
        box.pack(fill="x", pady=(0, 14))
        ttk.Label(
            box,
            wraplength=720,
            justify="left",
            foreground=MUTED,
            text=(
                "Unpacks the game and converts .nxd data and .tex textures. Ships bundled with this "
                "tool (MIT license - see tools/FF16Tools/LICENSE.txt) and is picked up "
                "automatically, so there's normally nothing to do here. Use these to point at a "
                "different copy or fetch a newer release."
            ),
        ).pack(anchor="w", pady=(0, 8))

        self.cli_path_var = tk.StringVar(value="(not set)")
        ttk.Label(box, textvariable=self.cli_path_var, foreground="#444444").pack(anchor="w", pady=(0, 8))

        btn_row = ttk.Frame(box)
        btn_row.pack(anchor="w")
        ttk.Button(
            btn_row, text="Browse for FF16Tools.CLI.exe...", style="Compact.TButton",
            command=self._browse_for_cli,
        ).pack(side="left", padx=(0, 8))
        self.download_button = ttk.Button(
            btn_row, text="Check for updates / Download newer release", style="Compact.TButton",
            command=self._start_download,
        )
        self.download_button.pack(side="left")

    def _refresh_cli_label(self) -> None:
        path = self.app.state_data.ff16tools_cli_path
        self.cli_path_var.set(str(path) if path else "(not found - the bundled copy may be missing)")

    def _browse_for_cli(self) -> None:
        chosen = filedialog.askopenfilename(
            title="Select FF16Tools.CLI.exe",
            filetypes=[("FF16Tools CLI", "FF16Tools.CLI.exe"), ("All files", "*.*")],
        )
        if chosen:
            self.app.state_data.ff16tools_cli_path = Path(chosen)
            self._refresh_cli_label()
            self._log(f"Using FF16Tools.CLI at: {chosen}")

    def _start_download(self) -> None:
        self.download_button.configure(state="disabled")
        self._log("Checking GitHub for the latest FF16Tools release...")

        def worker():
            try:
                cli_path = ff16tools.download_and_extract_latest(
                    progress_cb=lambda p: self._queue.put(("log", p.detail))
                )
                self._queue.put(("cli_ready", str(cli_path)))
            except Exception as exc:  # noqa: BLE001 - surface any failure to the log
                self._queue.put(("log", f"Download failed: {exc}"))
            finally:
                self._queue.put(("enable_download", None))

        threading.Thread(target=worker, daemon=True).start()

    # -- AudioMog -------------------------------------------------------------

    def _build_audiomog_section(self, parent) -> None:
        box = ttk.LabelFrame(parent, text="AudioMog", padding=12)
        box.pack(fill="x", pady=(0, 4))
        ttk.Label(
            box,
            wraplength=720,
            justify="left",
            foreground=MUTED,
            text=(
                "Unpacks and repacks .sab sound archives for the Sounds tab - a separate tool from "
                "FF16Tools, since .sab is a different container format "
                "(github.com/Yoraiz0r/AudioMog, MIT license - see tools/AudioMog/LICENSE). Ships "
                "bundled and already configured to run unattended, so there's normally nothing to "
                "do here either."
            ),
        ).pack(anchor="w", pady=(0, 8))

        self.audiomog_path_var = tk.StringVar(value="(not set)")
        ttk.Label(box, textvariable=self.audiomog_path_var, foreground="#444444").pack(anchor="w", pady=(0, 8))

        btn_row = ttk.Frame(box)
        btn_row.pack(anchor="w")
        ttk.Button(
            btn_row, text="Browse for AudioMog.exe...", style="Compact.TButton",
            command=self._browse_for_audiomog,
        ).pack(side="left", padx=(0, 8))
        self.audiomog_download_button = ttk.Button(
            btn_row, text="Check for updates / Download newer release", style="Compact.TButton",
            command=self._start_audiomog_download,
        )
        self.audiomog_download_button.pack(side="left")

        self.audiomog_settings_var = tk.StringVar(value="")
        ttk.Label(
            box, textvariable=self.audiomog_settings_var, foreground="#666666",
            wraplength=720, justify="left",
        ).pack(anchor="w", pady=(6, 0))

    def _refresh_audiomog_label(self) -> None:
        path = self.app.state_data.audiomog_exe_path
        self.audiomog_path_var.set(str(path) if path else "(not found - the bundled copy may be missing)")

    def _browse_for_audiomog(self) -> None:
        chosen = filedialog.askopenfilename(
            title="Select AudioMog.exe",
            filetypes=[("AudioMog", "AudioMog.exe;*AudioMog*.exe"), ("All files", "*.*")],
        )
        if chosen:
            self._set_audiomog_path(Path(chosen))

    def _start_audiomog_download(self) -> None:
        self.audiomog_download_button.configure(state="disabled")
        self._log("Checking GitHub for the latest AudioMog release...")

        def worker():
            try:
                exe_path = audiomog.download_latest(
                    progress_cb=lambda p: self._queue.put(("log", p.detail))
                )
                self._queue.put(("audiomog_ready", str(exe_path)))
            except Exception as exc:  # noqa: BLE001 - surface any failure to the log
                self._queue.put(("log", f"AudioMog download failed: {exc}"))
            finally:
                self._queue.put(("enable_audiomog_download", None))

        threading.Thread(target=worker, daemon=True).start()

    def _set_audiomog_path(self, path: Path) -> None:
        self.app.state_data.audiomog_exe_path = path
        self._refresh_audiomog_label()
        self._log(f"Using AudioMog.exe at: {path}")
        result = audiomog.ensure_terminal_settings_quiet(path)
        if result == "patched":
            self.audiomog_settings_var.set(
                "Updated its TerminalSettings.json so it runs unattended (ImmediatelyQuitOnceAllTasksAreDone)."
            )
        elif result == "no_file":
            self.audiomog_settings_var.set(
                "No TerminalSettings.json found next to it yet - AudioMog generates one on first run. "
                "Run AudioMog.exe once by hand (e.g. drag any file onto it, then close it), then re-select "
                "it here so this tool can confirm it's set to run unattended."
            )
        elif result == "missing_key":
            self.audiomog_settings_var.set(
                "Its TerminalSettings.json doesn't have the expected setting - unpacking/repacking here "
                "may pause waiting for a key press. Check TerminalSettings.json by hand if the Sounds "
                "tab seems to hang."
            )
        # "already_set" - nothing to say, it's already ready.

    # =========================================================================
    # Automatic detection
    # =========================================================================

    def _auto_detect_bundled_tools(self) -> None:
        """
        Checks tools/FF16Tools and tools/AudioMog (bundled with this project
        - see their LICENSE files) for a ready-to-use copy of each, and sets
        state so both tools work immediately without requiring a first-time
        Browse/Download - the Download buttons remain, but only for checking
        updates past what's bundled.
        """
        state = self.app.state_data
        if state.ff16tools_cli_path is None:
            bundled_cli = ff16tools.find_bundled_cli()
            if bundled_cli is not None:
                state.ff16tools_cli_path = bundled_cli
                self._log(f"Using the bundled FF16Tools.CLI at: {bundled_cli}")
        if state.audiomog_exe_path is None:
            bundled_audiomog = audiomog.find_bundled_exe()
            if bundled_audiomog is not None:
                state.audiomog_exe_path = bundled_audiomog
                self._log(f"Using the bundled AudioMog at: {bundled_audiomog}")

    def _adopt_previous_session_output(self) -> None:
        """
        Picks up the unpacked folder and converted database this tool
        produced last time, if they're both still sitting where it left
        them. Re-unpacking the game every launch just to get back to where
        you already were is the single most annoying thing this page could
        ask for, and everything needed to avoid it is already on disk.
        """
        state = self.app.state_data
        local = paths.local_data_dir()

        unpacked = local / "UnpackedGame"
        try:
            has_content = unpacked.is_dir() and any(unpacked.iterdir())
        except OSError:
            has_content = False
        if state.unpacked_game_dir is None and has_content:
            self._set_unpacked_game_dir(unpacked)
            self._log("Reusing the unpacked game folder from a previous session.")

        sqlite_path = local / "fft_data.sqlite"
        if state.nxd_sqlite_path is None and sqlite_path.is_file():
            self._adopt_sqlite(sqlite_path, "from a previous session")
            self._log(f"Reusing the database from a previous session: {sqlite_path}")

    def _start_autodetect(self) -> None:
        """Finds the installed game and Reloaded-II off the UI thread."""
        def worker():
            try:
                packs = game_install.autodetect_pack_folders()
            except Exception as exc:  # noqa: BLE001 - detection is best-effort by design
                packs = []
                self._queue.put(("log", f"Game detection failed harmlessly: {exc}"))
            self._queue.put(("detected_packs", packs))

            if self.app.state_data.reloaded_ii_path is None:
                try:
                    found = reloaded.find_installed_reloaded()
                except Exception as exc:  # noqa: BLE001
                    found = None
                    self._queue.put(("log", f"Reloaded-II detection failed harmlessly: {exc}"))
                if found is not None:
                    self._queue.put(("detected_reloaded", str(found)))

        threading.Thread(target=worker, daemon=True).start()

    # =========================================================================
    # Log
    # =========================================================================

    def _build_log_section(self, parent) -> None:
        # Deliberately not collapsible. Unpacking runs for minutes with no
        # other sign of life, so this is the only live progress there is -
        # and a control that can hide it is a control someone will hide it
        # with, then wonder whether the app has died.
        box = ttk.LabelFrame(parent, text="Log", padding=10)
        box.pack(fill="both", expand=True, pady=(0, 8))
        self.log_text = tk.Text(box, height=12, state="disabled", wrap="word")
        self.log_text.pack(fill="both", expand=True)

    def _log(self, message: str) -> None:
        self._log_many([message])

    def _log_many(self, messages: list) -> None:
        """
        Appends a batch of lines in a single Text update.

        Written as a batch operation on purpose. FF16Tools logs a line for
        every file it touches - tens of thousands of them for a full unpack -
        and doing insert + see("end") + two state toggles per line made the
        UI thread spend longer redrawing the log than the unpack spent
        working, which froze the whole window. One insert, one scroll, two
        toggles per batch instead.
        """
        if not messages:
            return
        self.log_text.configure(state="normal")
        self.log_text.insert("end", "\n".join(messages) + "\n")

        # Keep the widget bounded. Left alone it would hold ~90,000 lines
        # after a full unpack, which costs memory and makes every later
        # redraw slower for no benefit - nobody scrolls back that far.
        line_count = int(self.log_text.index("end-1c").split(".")[0])
        if line_count > self._MAX_LOG_LINES:
            self.log_text.delete("1.0", f"{line_count - self._MAX_LOG_LINES}.0")

        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    # =========================================================================
    # Queue pump
    # =========================================================================

    def _poll_queue(self) -> None:
        log_batch: list = []
        processed = 0
        try:
            while processed < self._MAX_MESSAGES_PER_TICK:
                kind, payload = self._queue.get_nowait()
                processed += 1
                if kind == "log":
                    # Collected and written in one go at the end of the tick.
                    log_batch.append(payload)
                    continue
                if kind == "cli_ready":
                    self.app.state_data.ff16tools_cli_path = Path(payload)
                    self._refresh_cli_label()
                    self._log(f"FF16Tools.CLI ready at: {payload}")
                elif kind == "enable_download":
                    self.download_button.configure(state="normal")
                elif kind == "audiomog_ready":
                    self._set_audiomog_path(Path(payload))
                elif kind == "enable_audiomog_download":
                    self.audiomog_download_button.configure(state="normal")
                elif kind == "detected_packs":
                    self._apply_detected_packs(payload)
                elif kind == "detected_reloaded":
                    self._set_reloaded_path(Path(payload), announce=False)
                    self._log(f"Detected Reloaded-II at: {payload}")
                elif kind == "setup_progress":
                    text, fraction = payload
                    self.setup_status_var.set(text)
                    self.setup_progress.configure(value=fraction)
                elif kind == "setup_done":
                    self.setup_progress.configure(value=100)
                    self.setup_status_var.set(f"{READY_MARK} {payload}")
                    self._refresh_readiness()
                elif kind == "setup_failed":
                    self.setup_progress.configure(value=0)
                    self.setup_status_var.set(f"{WARN_MARK} {payload}")
                    self._log(f"Setup stopped: {payload}")
                    self._refresh_readiness()
                elif kind == "enable_setup":
                    self.setup_button.configure(state="normal")
                    self.unpack_button.configure(state="normal")
                elif kind == "unpacked_dir_ready":
                    self._set_unpacked_game_dir(Path(payload))
                elif kind == "nxd_ready":
                    sqlite_path, detail = payload
                    self._adopt_sqlite(Path(sqlite_path), detail)
                    self._log(f"Game data database ready at: {sqlite_path}")
                    # Also clears the "Converting..." line left by the
                    # "Already unpacked it?" shortcut, which previously
                    # sat there forever because only the full pipeline
                    # ever posted a finishing status.
                    self.setup_progress.configure(value=100)
                    self.setup_status_var.set(
                        f"{READY_MARK} Game data converted - the data tabs are ready to use."
                    )
                elif kind == "nxd_error":
                    self._log(f"Data conversion failed: {payload}")
                    self.setup_status_var.set(f"{WARN_MARK} {payload}")
                elif kind == "mod_database_ready":
                    self._adopt_mod_database(Path(payload))
                elif kind == "mod_sqlite_ready":
                    # Set on the interface thread, so nothing reads a path
                    # to a file that is still being written.
                    self.app.state_data.mod_sqlite_path = Path(payload)
                elif kind == "nxd_recovery_done":
                    self._apply_recovered_nxd(payload)
                elif kind == "enable_convert_nxd":
                    self.convert_nxd_button.configure(state="normal")
                elif kind == "table_progress":
                    self.tables_status_var.set(payload)
                elif kind == "tables_loaded":
                    self._apply_loaded_tables(payload)
                elif kind == "tables_error":
                    self.tables_status_var.set(f"{WARN_MARK} Couldn't load the tables: {payload}")
                    self.tables_refresh_button.configure(state="normal")
                    self._log(f"Reference tables failed to load: {payload}")
                    self._refresh_readiness()
        except queue.Empty:
            pass

        if log_batch:
            self._log_many(log_batch)

        # If the cap was hit there is still work waiting, so come back
        # immediately rather than idling 100ms with a full queue - this
        # keeps a flood draining fast while still yielding to the event
        # loop between batches so the window stays responsive.
        delay = 1 if processed >= self._MAX_MESSAGES_PER_TICK else 100
        self.after(delay, self._poll_queue)

    def _apply_loaded_tables(self, payload) -> None:
        (job_result, job_records, job_version, cmd_records, cmd_version,
         ability_names_live, ability_types, item_paths, item_records, item_versions) = payload
        state = self.app.state_data
        state.job_table_path = job_result.path
        state.job_records = job_records
        state.table_version = job_version
        state.table_source_detail = job_result.detail
        state.job_command_records = cmd_records
        state.job_command_version = cmd_version
        state.ability_names = ability_names_live
        state.ability_types = ability_types
        state.item_table_paths = item_paths
        state.item_table_records = item_records
        state.item_table_versions = item_versions

        self.tables_status_var.set(f"{READY_MARK} All reference tables loaded ({job_result.source}).")
        # The tabs that render this data were built before it existed.
        self.app.notify_data_loaded(exclude=self)

        named_jobs = sum(1 for r in job_records if r.name)
        no_ref_jobs = sum(1 for r in job_records if not r.has_reference_data)
        named_cmds = sum(1 for r in cmd_records if r.name)
        fftp_fallback_used = sum(
            1 for i in range(512)
            if i not in ability_names_live
            and i in an.ABILITY_NAMES
            and not an.ABILITY_NAMES[i].startswith("(")
        )
        named_items = sum(1 for r in item_records["item"] if r.name)
        self.tables_summary_var.set(
            f"Jobs: {len(job_records)} slots ({named_jobs} named, {no_ref_jobs} with no "
            f"reference data - you can still create new data for those from scratch).\n"
            f"Job Commands: {len(cmd_records)} loaded ({named_cmds} named).\n"
            f"Abilities: {len(ability_names_live)} named directly from the mod loader's table, "
            f"plus {fftp_fallback_used} more filled in from FFTPatcher's reference list.\n"
            f"Items: {len(item_records['item'])} loaded ({named_items} named), plus "
            f"{len(item_records['item_weapon'])} weapon / {len(item_records['item_armor'])} armor / "
            f"{len(item_records['item_shield'])} shield / {len(item_records['item_accessory'])} "
            f"accessory / {len(item_records['item_equip_bonus'])} equip-bonus rows and "
            f"{len(item_records['item_shops'])} shop-availability entries.\n"
            f"Treasure Hunter: {len(item_records['map_trap'])} map slots loaded."
        )
        self.tables_refresh_button.configure(state="normal")
        self._refresh_readiness()

    # =========================================================================
    # WizardStepFrame overrides
    # =========================================================================

    def on_show(self) -> None:
        if not self._tables_loaded_once:
            self._tables_loaded_once = True
            # Local copies, unless a week has gone by. Loading the bundled
            # tables is instant and needs no network, so the editor tabs are
            # populated immediately instead of waiting on 13 downloads.
            self._start_table_fetch(force=self._should_check_tables_online())
        if not self._autodetect_done:
            self._autodetect_done = True
            self._adopt_previous_session_output()
            self._start_autodetect()

