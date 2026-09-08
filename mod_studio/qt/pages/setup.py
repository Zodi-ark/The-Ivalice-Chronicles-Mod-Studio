"""
General Setup.

The gateway. Nothing else in the tool works until this page has run: the
data tabs need a converted database, Textures needs a scanned tree, Game
Updates needs an archived version. It was the last page to be rebuilt and
should probably have been among the first, because a Qt interface without
it can look at bundled reference tables and nothing else.

Scope, stated plainly because it is smaller than the Tkinter page's 2,329
lines: opening an existing mod, choosing the game folder, unpacking, and
adopting a folder that is already unpacked. The advanced options - manual
FF16Tools paths, unpack filters, version pruning - are not here yet, and
the page says so rather than implying the rewrite is finished.

The unpack itself runs FF16Tools, a Windows binary. Its wiring is written
and its worker is the same one the Compare page uses, but **it has never
been run**; there is no way to run it off Windows. What CAN be exercised
here, and is, is the "already unpacked" path, which does everything the
unpack does except the unpack: scan the textures, find the nxd folder,
report what is now editable.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QFileDialog, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QPlainTextEdit, QProgressBar, QPushButton, QScrollArea, QVBoxLayout,
    QWidget,
)

from ... import (
    audiomog, ff16tools, game_install, modconfig, nxd_data, paths, reloaded)
from ... import sound_data as sd, texture_data as td
from ..widgets.field_rows import CollapsibleSection
from ..workers import Worker, run_in_thread

# The groups come from `game_install.CONTENT_GROUPS`, not a list written
# here. The first version was a hand-copy with keys "game_data", "textures"
# and "sounds" and no folders attached - which looked right and was useless,
# because `filters_for_folders` takes FOLDER names ("nxd", "ui", "bg",
# "sound") and "textures" is not one. It would have unpacked the wrong thing
# or nothing. The engine already knows which folders each group means.
UNPACK_GROUPS = [
    (group.key, group.label, group.detail, tuple(group.folders), group.default_on)
    for group in game_install.CONTENT_GROUPS
]


class AdoptFolderWorker(Worker):
    """
    Takes a folder that is already unpacked and works out what it offers.

    Scanning 10,011 textures off disk is slow enough to freeze the window if
    it happened on the GUI thread, so it does not.
    """

    def __init__(self, folder: Path):
        super().__init__()
        self.folder = folder

    def run(self):
        self.log.emit(f"Looking through {self.folder}...")
        result = {"folder": self.folder, "texture_tree": None,
                  "sound_tree": None, "nxd_dir": None}

        nxd_dir = self.folder / "nxd"
        if nxd_dir.is_dir():
            result["nxd_dir"] = nxd_dir
            self.log.emit(f"Found {nxd_dir} - the game data is here.")
        else:
            # Said out loud rather than left as an empty tab later. A folder
            # unpacked with a filter that skipped nxd is a perfectly normal
            # thing to have, and the user needs to know which tabs it leaves
            # unavailable.
            self.log.emit(
                "No nxd folder in there, so the data tabs stay unavailable. "
                "If you unpacked with a filter, unpack again with Game data "
                "ticked.")

        try:
            tree = td.scan_texture_tree(self.folder)
            count = td.count_textures(tree)
            if count:
                result["texture_tree"] = tree
                self.log.emit(f"Found {count:,} textures.")
            else:
                self.log.emit("No textures in there.")
        except Exception as exc:                              # noqa: BLE001
            self.log.emit(f"Couldn't scan for textures: {exc}")

        try:
            tree = sd.scan_sound_tree(self.folder)
            count = sd.count_sounds(tree)
            if count:
                result["sound_tree"] = tree
                self.log.emit(f"Found {count:,} sound archives.")
            else:
                self.log.emit("No sound archives in there.")
        except Exception as exc:                              # noqa: BLE001
            self.log.emit(f"Couldn't scan for sounds: {exc}")

        return result


class ReferenceTableWorker(Worker):
    """
    Checks all four upstream sources, and fetches only what has changed.

    This used to download FOUR HARDCODED FILENAMES - `JobData.xml`,
    `JobCommandData.xml`, `AbilityData.xml`, `ItemData.xml` - unconditionally,
    every time. It could not see a new table, a renamed one, a changed
    schema, or any of the other 25 sample files, and it had never heard of
    the nxd layouts, the XML models or the flag definitions at all.

    That gap mattered more once the table registry started deriving itself
    from those files: a table's existence, its columns, whether it is
    per-language and which of its fields are flags now all come from the
    repositories, so "is my copy current" is a question about all four
    sources rather than four files from one of them.

    `upstream.py` compares by git blob SHA, one request per directory, so a
    check that finds nothing costs four requests and downloads nothing.
    """

    def run(self):
        from ... import upstream

        reports = upstream.check_all()
        for report in reports:
            self.log.emit(report.summary())
            if not report.ok or not report.outstanding:
                continue
            wanted = report.added + report.changed
            for filename, outcome in upstream.download(report.source, wanted):
                self.log.emit(f"  {filename}: {outcome}")
        return reports


# ---------------------------------------------------------------------------
# Merging recovered edits into the session.
#
# COPIED from `gui/step_setup.py`, not re-derived. The reasoning in
# `_compose_entry_rekeys` in particular took a real bug to work out, and two
# interfaces guessing separately at how to combine a mod's own moves with a
# user's would be two chances to get it wrong differently.
#
# They belong in the engine - both interfaces need them and neither owns
# them - but moving them is an engine change and this is not the session for
# it. Flagged in HANDOFF.md.
# ---------------------------------------------------------------------------


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

class ModNxdWorker(Worker):
    """
    Converts a mod's own `.nxd` files to SQLite, and diffs them if it can.

    **This is how most mods are read.** A mod ships `.nxd`, not a database -
    the game reads those wholesale - so without this step opening one
    recovers its XML tables and nothing else. Game Updates then has no
    `mod_sqlite_path` to compare against and refuses, which is exactly what
    was reported.

    Needs FF16Tools and nothing else: converting the mod's own files does
    not require the game to be unpacked. What the game files change is only
    what can be done with the result:

      with a vanilla database - diff the two, so every tab shows the mod's
      values AND marks which fields it changed;

      without one - there is nothing to diff against, but the mod's own
      database is still a complete, correct picture of the mod, so it
      becomes the working database. The tabs then show and edit the mod's
      real values instead of refusing to open. What is missing is the
      "changed from vanilla" marking, which is a far smaller loss than not
      being able to edit at all.
    """

    def __init__(self, mod_root: Path, cli_path: Path, vanilla_sqlite):
        super().__init__()
        self.mod_root = Path(mod_root)
        self.cli_path = Path(cli_path)
        self.vanilla_sqlite = vanilla_sqlite

    def run(self):
        data_dir = self.mod_root / "FFTIVC" / "data"
        nxd_dirs = sorted(data_dir.glob("*/nxd")) if data_dir.is_dir() else []
        nxd_dirs = [d for d in nxd_dirs if any(d.glob("*.nxd"))]
        if not nxd_dirs:
            # The XML tables were the whole mod. Not a failure.
            return {"mod_sqlite": None, "recovered": None, "nxd_dir": None}

        source = nxd_dirs[0]
        self.log.emit(f"Reading this mod's game data from {source}...")
        staging_root = paths.local_data_dir() / "mod_nxd_staging"
        # Everything the mod ships, not just the tables with tabs. A mod
        # carries a handful of .nxd, so this is cheap, and it is what lets
        # Game Updates say something true about files like uibuttonguide.nxd
        # instead of reporting an unreadable table as unchanged.
        found = nxd_data.prepare_staging_folder(source, staging_root,
                                                include_all=True)
        if not found:
            self.log.emit("No recognised .nxd files in this mod.")
            return {"mod_sqlite": None, "recovered": None, "nxd_dir": source}

        modded = paths.local_data_dir() / "mod_data.sqlite"
        if modded.exists():
            modded.unlink()
        code = ff16tools.run_nxd_to_sqlite(
            self.cli_path, staging_root / "nxd", modded,
            line_cb=self.log.emit)
        if code != 0 or not modded.exists():
            raise RuntimeError(
                f"FF16Tools exited with code {code} converting this mod's "
                f".nxd files.")

        recovered = None
        unmodelled = {}
        if self.vanilla_sqlite is not None:
            recovered = nxd_data.recover_edits_from_sqlite(
                Path(self.vanilla_sqlite), modded)
            # And everything in tables no typed reader covers. Without this
            # the tool could WRITE a mod - through the All Game Data tab -
            # that it could not read back: reopening it recovered the
            # modelled tables and silently dropped the rest.
            unmodelled = nxd_data.recover_unmodelled_edits(
                Path(self.vanilla_sqlite), modded)
        return {"mod_sqlite": modded, "recovered": recovered,
                "unmodelled": unmodelled, "nxd_dir": source}


class UnpackWorker(Worker):
    """
    Runs FF16Tools over the game's pack files, once per filter.

    FF16Tools takes one filter per run, so N folders means N runs -
    `game_install.filters_for_folders` decides how many, and returns None
    when the selection covers everything, meaning one unfiltered pass rather
    than twelve filtered ones.

    **Not verified.** FF16Tools is a Windows binary; the wiring is written
    and the filters are checked, but this has never run.
    """

    def __init__(self, cli_path: Path, source: Path, destination: Path,
                 filters, include_diff: bool, packs=None):
        super().__init__()
        self.cli_path = cli_path
        self.source = source
        self.destination = destination
        self.filters = filters
        self.include_diff = include_diff
        # None means "every pack in the folder", which lets FF16Tools do the
        # whole folder in one command. A list means run them one at a time.
        self.packs = packs

    # Progress is reported in permille rather than "pass 2 of 4", so the bar
    # moves during a pass instead of jumping once every few minutes. A pass
    # over `bg` extracts ~6,000 files and takes long enough that a bar
    # standing still reads as a hang.
    SCALE = 1000

    @staticmethod
    def _folder_of(filter_text):
        """
        The folder a filter is asking for, or None.

        `filters_for_folders` produces "nxd/", "ui/" and so on, so the
        folder name is the filter without its trailing slash. Anything else
        - a custom filter someone typed - has no known file count, and the
        pass then reports no within-pass progress rather than a made-up one.
        """
        if not filter_text:
            return None
        name = filter_text.rstrip("/").strip()
        return name if name in game_install.GAME_FOLDERS_BY_NAME else None

    def _line_handler(self, pass_index: int, passes: list, folder):
        """
        Turns FF16Tools' per-file chatter into progress instead of log traffic.

        It logs a line for every file it extracts, so a full unpack produces
        tens of thousands of them. The Qt worker forwarded all of them
        straight to `self.log.emit`, which is a queued cross-thread signal
        per line - the same starvation the Tkinter interface already fixed
        by counting instead of forwarding.

        Anything that is NOT a routine "Extracting ..." line is still
        forwarded verbatim, because errors, warnings and summaries are
        exactly what is wanted when an unpack goes wrong.
        """
        expected = (game_install.GAME_FOLDERS_BY_NAME[folder].approx_files
                    if folder else 0)
        label = folder or "everything"
        total = len(passes)
        state = {"count": 0}

        def handle(line: str) -> None:
            if " Extracting '" not in line:
                self.log.emit(line)
                return
            state["count"] += 1
            count = state["count"]
            if count % 25:
                return
            if expected:
                # Clamped: approx_files is measured from a real unpack, so
                # an underestimate must not push the bar past its own pass.
                within = min(count / expected, 1.0)
            else:
                within = 0.0
            self.progress.emit(
                int(((pass_index + within) / total) * self.SCALE), self.SCALE)
            if count % 500 == 0:
                self.log.emit(f"  ... {count:,} files extracted from {label}")

        handle.count = lambda: state["count"]
        return handle

    def run(self):
        self.destination.mkdir(parents=True, exist_ok=True)
        passes = self.filters if self.filters else [None]
        for index, filter_text in enumerate(passes):
            folder = self._folder_of(filter_text)
            label = folder or filter_text or "everything"
            self.log.emit(f"Unpacking {label} ({index + 1} of {len(passes)})...")
            self.progress.emit(int((index / len(passes)) * self.SCALE), self.SCALE)
            handler = self._line_handler(index, passes, folder)
            if self.packs is None:
                code = ff16tools.run_unpack_all_packs(
                    self.cli_path, self.source, self.destination,
                    line_cb=handler, filter_text=filter_text,
                    include_diff=self.include_diff)
            else:
                # One pack at a time, so the unticked ones - the mod
                # loader's own output - are simply never opened. There is no
                # "exclude" option on unpack-all-packs, so not opening them
                # is the only way to leave them out.
                code = 0
                for pack in self.packs:
                    code = ff16tools.run_unpack_single_pack(
                        self.cli_path, pack.path, self.destination,
                        line_cb=handler, filter_text=filter_text)
                    if code != 0:
                        break
            self.log.emit(
                f"  {handler.count():,} files extracted for {label}.")
            if code != 0:
                raise RuntimeError(
                    f"FF16Tools exited with code {code} while unpacking "
                    f"{label}.")
        self.progress.emit(self.SCALE, self.SCALE)

        # Exit codes alone are not evidence. An unpack that produced nothing
        # is a failure however politely it ended.
        if not any(self.destination.iterdir()):
            raise RuntimeError(
                "FF16Tools finished without errors but the output folder is "
                "empty. Check that the game data folder is the one holding "
                "the .pac files.")
        return self.destination


class ToolUpdateWorker(Worker):
    """
    Checks GitHub for a newer FF16Tools or AudioMog, and fetches it if asked.

    On a thread because both hit the network, and both can take a while on a
    slow connection - the Tkinter page freezes for the duration and this
    does not have to.

    **Downloading is a separate press from checking.** The bundled tools are
    known to work with this build; a newer one is an improvement somebody
    chose, not something to apply because a check ran. That matters more
    than usual here: AudioMog's shipped `TerminalSettings.json` defaults
    `ImmediatelyQuitOnceAllTasksAreDone` to false, which hangs the unpack,
    and a replacement copy has to be re-patched.
    """

    def __init__(self, tool: str, download: bool):
        super().__init__()
        self.tool = tool                       # "ff16tools" or "audiomog"
        self.download = download

    def run(self):
        from ... import fetcher

        if self.tool == "ff16tools":
            info = fetcher.get_latest_ff16tools_release_info()
        else:
            info = fetcher.get_latest_audiomog_release_info()
        tag = info.get("tag_name") or info.get("name") or "unknown"

        if not self.download:
            return {"tool": self.tool, "tag": tag, "downloaded": None}

        def report(progress):
            self.log.emit(f"{progress.stage}: {progress.detail}")

        if self.tool == "ff16tools":
            path = ff16tools.download_and_extract_latest(progress_cb=report)
        else:
            path = audiomog.download_latest(progress_cb=report)
        return {"tool": self.tool, "tag": tag, "downloaded": path}


class ConvertWorker(Worker):
    """
    Runs `FF16Tools.CLI nxd-to-sqlite` over an unpacked nxd folder.

    This is the same call the old interface makes - `run_nxd_to_sqlite`,
    which builds the command and streams its output. It was left out at
    first on the grounds that FF16Tools is a Windows binary and could not be
    run here, which confused "I cannot test this" with "I should not build
    it". The subprocess call is identical either way; not writing it just
    left the new interface unable to do the one thing that unlocks every
    data tab.

    **Not verified.** The wiring is written and the command construction is
    checked, but this has never actually run - there is no FF16Tools to run
    off Windows.
    """

    def __init__(self, cli_path: Path, nxd_dir: Path, sqlite_path: Path):
        super().__init__()
        self.cli_path = cli_path
        self.nxd_dir = nxd_dir
        self.sqlite_path = sqlite_path

    def run(self):
        self.log.emit(f"Converting {self.nxd_dir} into an editable database...")
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        code = ff16tools.run_nxd_to_sqlite(
            self.cli_path, self.nxd_dir, self.sqlite_path,
            line_cb=self.log.emit)
        self.log.emit(f"nxd-to-sqlite finished with exit code {code}")

        # Exit code AND the file. A converter that returns 0 without writing
        # anything is the exact shape of failure this project keeps meeting -
        # "did it run" standing in for "did it produce what was asked for".
        if code != 0:
            raise RuntimeError(
                f"FF16Tools exited with code {code} - see the log above.")
        if not self.sqlite_path.exists():
            raise RuntimeError(
                "FF16Tools reported success but no database was written.")
        return self.sqlite_path


class SetupPage(QWidget):
    """Emits when something changed that other pages need to react to."""

    setup_changed = Signal()

    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state
        self._thread = None
        self._convert_after_adopt = False

        # The whole page scrolls. With Advanced options open it is taller
        # than a 1080p screen, and without this the sections were squeezed
        # into each other rather than running off the bottom - which reads
        # as a broken layout rather than as more to see.
        page = QVBoxLayout(self)
        page.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        page.addWidget(self.scroll)

        body = QWidget()
        self.scroll.setWidget(body)
        outer = QVBoxLayout(body)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(10)

        heading = QLabel("General Setup")
        heading.setProperty("role", "heading")
        outer.addWidget(heading)

        blurb = QLabel(
            "Editing a mod? Open it below and you're done. Starting fresh? "
            "Unpack your game files so the editing tabs have something to work "
            "with.")
        blurb.setProperty("role", "intro")
        blurb.setWordWrap(True)
        outer.addWidget(blurb)

        outer.addWidget(self._mod_box())
        outer.addWidget(self._game_box())

        self.status = QLabel("")
        self.status.setProperty("role", "muted")
        self.status.setWordWrap(True)
        outer.addWidget(self.status)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        self.progress.setMaximumHeight(6)
        self.progress.setTextVisible(False)
        outer.addWidget(self.progress)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(140)
        outer.addWidget(self.log)

        outer.addWidget(self._advanced_section())
        outer.addStretch(1)
        self.detect_bundled_tools()
        self._refresh_readiness()

    # -- sections ---------------------------------------------------------------

    def _mod_box(self) -> QGroupBox:
        box = QGroupBox("Open an existing mod")
        column = QVBoxLayout(box)
        note = QLabel(
            "Open a mod to keep working on it, its edits load back in ready "
            "to change.")
        note.setProperty("role", "muted")
        note.setWordWrap(True)
        column.addWidget(note)

        self.mod_status = QLabel("No mod opened - starting a new mod.")
        column.addWidget(self.mod_status)

        row = QHBoxLayout()
        self.open_mod_button = QPushButton("Open existing mod...")
        self.open_mod_button.setMinimumWidth(
            self.open_mod_button.sizeHint().width() + 8)
        self.open_mod_button.clicked.connect(self.open_mod)
        row.addWidget(self.open_mod_button)
        row.addStretch(1)
        column.addLayout(row)
        return box

    def _game_box(self) -> QGroupBox:
        box = QGroupBox("Game files")
        column = QVBoxLayout(box)

        note = QLabel(
            "Most tabs need game files. This unpacks them to an editable "
            "database once per version. Your game files are only read, never "
            "modified.")
        note.setProperty("role", "muted")
        note.setWordWrap(True)
        column.addWidget(note)

        row = QHBoxLayout()
        row.addWidget(QLabel("Game data folder:"))
        self.folder_field = QLineEdit()
        row.addWidget(self.folder_field, 1)
        browse = QPushButton("Browse...")
        browse.setMinimumWidth(browse.sizeHint().width() + 8)
        browse.clicked.connect(self.browse_game_folder)
        row.addWidget(browse)
        column.addLayout(row)

        self.folder_hint = QLabel("")
        self.folder_hint.setProperty("role", "muted")
        self.folder_hint.setWordWrap(True)
        column.addWidget(self.folder_hint)

        column.addWidget(QLabel("What do you want to be able to edit?"))
        self.group_boxes = {}
        for key, label, description, _folders, default_on in UNPACK_GROUPS:
            check = QCheckBox(label)
            check.setChecked(bool(default_on))
            self.group_boxes[key] = check
            column.addWidget(check)
            hint = QLabel("   " + description)
            hint.setProperty("role", "muted")
            hint.setWordWrap(True)
            column.addWidget(hint)

        # There is no "Convert game data to an editable database" button.
        #
        # Unpacking runs the conversion itself, and so does adopting a
        # folder that has no database yet - so by the time the button
        # existed there was never anything for it to do. A button that is
        # either disabled or redundant is worse than no button: it reads as
        # a step you have to remember.
        #
        # Converting is still reachable on purpose, under Advanced options:
        # "Convert to editable database" takes any nxd folder, and "Open an
        # existing database..." skips conversion altogether. Those are for
        # folders this tool did not unpack, which is the only case where the
        # automatic path does not apply.

        row = QHBoxLayout()
        self.unpack_button = QPushButton("Unpack and prepare game files")
        self.unpack_button.setMinimumWidth(
            self.unpack_button.sizeHint().width() + 8)
        self.unpack_button.clicked.connect(self.start_unpack)
        row.addWidget(self.unpack_button)
        self.adopt_button = QPushButton("Already unpacked? Use that folder...")
        self.adopt_button.setMinimumWidth(
            self.adopt_button.sizeHint().width() + 8)
        self.adopt_button.clicked.connect(self.adopt_existing_folder)
        row.addWidget(self.adopt_button)
        row.addStretch(1)
        column.addLayout(row)

        # The Reloaded-II location used to sit here, in the open. It lives
        # under Advanced options now - `_build_reloaded_block`.
        #
        # Export Mod asks for it too, and that is the one that has to stay:
        # it is where somebody actually needs it, at the moment they write
        # a mod into the Mods folder. Two copies of the same path, both on
        # display, is clutter that makes the setup page look like it wants
        # more from you than it does - detection fills this in by itself
        # and most people never touch it.
        self.detect_game_folder()
        return box

    def _build_reloaded_block(self, column) -> None:
        """Where Reloaded-II is, for the rare case detection misses it."""
        column.addWidget(self._bold("Reloaded-II"))
        found_note = QLabel(
            "Found automatically. This is only worth changing if it points "
            "somewhere wrong - Export Mod asks for it too, and that is the "
            "copy you normally use.")
        found_note.setProperty("role", "muted")
        found_note.setWordWrap(True)
        column.addWidget(found_note)

        reloaded_row = QHBoxLayout()
        reloaded_row.addWidget(QLabel("Reloaded-II:"))
        self.reloaded_field = QLineEdit()
        self.reloaded_field.setReadOnly(True)
        reloaded_row.addWidget(self.reloaded_field, 1)
        recheck = QPushButton("Find again")
        recheck.setMinimumWidth(recheck.sizeHint().width() + 8)
        recheck.clicked.connect(self.detect_reloaded)
        reloaded_row.addWidget(recheck)
        column.addLayout(reloaded_row)

        self.reloaded_hint = QLabel("")
        self.reloaded_hint.setProperty("role", "muted")
        self.reloaded_hint.setWordWrap(True)
        column.addWidget(self.reloaded_hint)
        self.detect_reloaded()

    def _advanced_section(self) -> QWidget:
        """
        The manual controls, collapsed.

        Not left out. These all worked in the old interface and leaving them
        behind would make the rewrite a downgrade for anyone who relies on
        them - which is most people with a non-Steam install, a filtered
        unpack, or a tools folder somewhere unusual.

        Collapsed because the guided path above is what most people need,
        and an interface that shows every escape hatch at once is harder to
        start with, not easier.
        """
        body = QWidget()
        column = QVBoxLayout(body)
        column.setContentsMargins(6, 4, 6, 6)
        column.setSpacing(6)

        # -- where the tools are ------------------------------------------
        column.addWidget(self._bold("Tool locations"))
        note = QLabel(
            "FF16Tools and AudioMog ship with this tool. Point somewhere else "
            "only if you have a newer copy.")
        note.setProperty("role", "muted")
        note.setWordWrap(True)
        column.addWidget(note)

        self.cli_field = QLineEdit(str(self.state.ff16tools_cli_path or ""))
        column.addLayout(self._browse_row(
            "FF16Tools.CLI:", self.cli_field, self._browse_cli, files=True))

        self.audiomog_field = QLineEdit(str(self.state.audiomog_exe_path or ""))
        column.addLayout(self._browse_row(
            "AudioMog:", self.audiomog_field, self._browse_audiomog, files=True))

        # Update checks, one row per tool. Both are separate presses: the
        # bundled copies are known to work with this build, so a newer one is
        # something somebody chooses rather than something a check applies.
        self.tool_update_rows = {}
        for tool, label in (("ff16tools", "FF16Tools"), ("audiomog", "AudioMog")):
            row = QHBoxLayout()
            check_button = QPushButton(f"Check for a newer {label}")
            check_button.setMinimumWidth(check_button.sizeHint().width() + 8)
            check_button.clicked.connect(
                lambda _c=False, t=tool: self.check_tool_update(t))
            row.addWidget(check_button)
            get_button = QPushButton("Download it")
            get_button.setMinimumWidth(get_button.sizeHint().width() + 8)
            get_button.setEnabled(False)
            get_button.clicked.connect(
                lambda _c=False, t=tool: self.download_tool_update(t))
            row.addWidget(get_button)
            row.addStretch(1)
            column.addLayout(row)

            status = QLabel("")
            status.setProperty("role", "muted")
            status.setWordWrap(True)
            column.addWidget(status)
            self.tool_update_rows[tool] = {
                "check": check_button, "get": get_button, "status": status}

        # -- unpack filter -------------------------------------------------
        column.addSpacing(6)
        column.addWidget(self._bold("Unpack specific folders only"))
        note2 = QLabel(
            "Leave blank to unpack everything the ticks above ask for. A "
            "filter is a folder name such as 'ui' or 'bg/textures'.")
        note2.setProperty("role", "muted")
        note2.setWordWrap(True)
        column.addWidget(note2)

        self.filter_field = QLineEdit()
        self.filter_field.setPlaceholderText("Custom filter (optional)")
        column.addWidget(self.filter_field)

        self.include_diff = QCheckBox(
            "Also unpack .diff.pac files (installed mods) - normally leave "
            "this off")
        column.addWidget(self.include_diff)

        # -- where it goes -------------------------------------------------
        column.addSpacing(6)
        column.addWidget(self._bold("Unpack into"))
        self.output_field = QLineEdit()
        self.output_field.setPlaceholderText(
            "Leave blank to use this tool's own local_data folder")
        column.addLayout(self._browse_row(
            "Folder:", self.output_field, self._browse_output))

        # -- reference tables ---------------------------------------------
        column.addSpacing(6)
        column.addWidget(self._bold("Reference tables"))
        tables_note = QLabel(
            "Ability and encounter names come from tables that ship with this "
            "tool. Newer ones are published occasionally; this checks for them.")
        tables_note.setProperty("role", "muted")
        tables_note.setWordWrap(True)
        column.addWidget(tables_note)

        tables_row = QHBoxLayout()
        self.check_tables_button = QPushButton("Check for newer tables")
        self.check_tables_button.setMinimumWidth(
            self.check_tables_button.sizeHint().width() + 8)
        self.check_tables_button.clicked.connect(self.check_reference_tables)
        tables_row.addWidget(self.check_tables_button)
        tables_row.addStretch(1)
        column.addLayout(tables_row)

        self.tables_result = QLabel("")
        self.tables_result.setProperty("role", "muted")
        self.tables_result.setWordWrap(True)
        column.addWidget(self.tables_result)

        # -- exactly which folders ------------------------------------------
        column.addSpacing(8)
        column.addWidget(self._bold("Unpack exactly these folders"))
        folders_note = QLabel(
            "The three tick boxes above are shorthand for these. Use them "
            "directly to unpack less - sound alone is 14,546 files, and most "
            "mods never touch it. Anything ticked here replaces the choice "
            "above.")
        folders_note.setProperty("role", "muted")
        folders_note.setWordWrap(True)
        column.addWidget(folders_note)

        # From the engine's own list, with its own measured counts. The
        # Tkinter page shows these ("nxd - Game data tables (~4,982 files)")
        # and the number is the point: it is the difference between a
        # two-minute unpack and a twenty-minute one, and nothing else on the
        # page tells you which folders are the expensive ones.
        self.folder_boxes = {}
        grid = QWidget()
        grid_column = QVBoxLayout(grid)
        grid_column.setContentsMargins(8, 2, 0, 2)
        grid_column.setSpacing(1)
        for folder in game_install.GAME_FOLDERS:
            check = QCheckBox(
                f"{folder.name} \u2014 {folder.summary} "
                f"(~{folder.approx_files:,} files)")
            check.toggled.connect(self._on_folder_tick)
            self.folder_boxes[folder.name] = check
            grid_column.addWidget(check)
        column.addWidget(grid)

        folder_buttons = QHBoxLayout()
        for label, handler in (("Select all", self._select_all_folders),
                               ("Select none", self._select_no_folders)):
            button = QPushButton(label)
            button.setMinimumWidth(button.sizeHint().width() + 8)
            button.clicked.connect(handler)
            folder_buttons.addWidget(button)
        folder_buttons.addStretch(1)
        column.addLayout(folder_buttons)

        self.folder_summary = QLabel("")
        self.folder_summary.setProperty("role", "muted")
        self.folder_summary.setWordWrap(True)
        column.addWidget(self.folder_summary)

        # -- run it from down here --------------------------------------------
        #
        # The main Unpack button is at the top of a long page and these
        # sections are at the bottom of it. Having changed the folders and
        # the packs, the next thing anyone wants is to run it, and scrolling
        # back up to a button that is off-screen is friction the Tkinter
        # page removed with exactly this ("Run This Unpack").
        run_row = QHBoxLayout()
        self.advanced_unpack_button = QPushButton("Run this unpack")
        self.advanced_unpack_button.setMinimumWidth(
            self.advanced_unpack_button.sizeHint().width() + 8)
        self.advanced_unpack_button.setToolTip(
            "Same as the Unpack button at the top, using the folders and "
            "packs chosen here.")
        self.advanced_unpack_button.clicked.connect(self.start_unpack)
        run_row.addWidget(self.advanced_unpack_button)
        run_row.addStretch(1)
        column.addLayout(run_row)

        # -- a database from somewhere else -------------------------------------
        column.addSpacing(8)
        column.addWidget(self._bold("Game data database (manual)"))
        manual_note = QLabel(
            "Ability and item names, unit names, encounters and poaching all "
            "live in .nxd files, which have to be converted to SQLite before "
            "they can be edited. The button at the top does that for the "
            "folder you unpacked. Use these for an nxd folder you got some "
            "other way, or to reuse a database from a previous session or "
            "another modder.")
        manual_note.setProperty("role", "muted")
        manual_note.setWordWrap(True)
        column.addWidget(manual_note)

        nxd_row = QHBoxLayout()
        nxd_row.addWidget(QLabel("Unpacked nxd folder:"))
        self.manual_nxd_field = QLineEdit()
        self.manual_nxd_field.setPlaceholderText(
            "A folder containing .nxd files")
        nxd_row.addWidget(self.manual_nxd_field, 1)
        nxd_browse = QPushButton("Browse...")
        nxd_browse.setMinimumWidth(nxd_browse.sizeHint().width() + 8)
        nxd_browse.clicked.connect(self.browse_manual_nxd)
        nxd_row.addWidget(nxd_browse)
        column.addLayout(nxd_row)

        manual_buttons = QHBoxLayout()
        self.manual_convert_button = QPushButton("Convert to editable database")
        self.manual_convert_button.setMinimumWidth(
            self.manual_convert_button.sizeHint().width() + 8)
        self.manual_convert_button.clicked.connect(self.convert_manual_nxd)
        manual_buttons.addWidget(self.manual_convert_button)
        open_db = QPushButton("Open an existing database...")
        open_db.setMinimumWidth(open_db.sizeHint().width() + 8)
        open_db.clicked.connect(self.open_existing_database)
        manual_buttons.addWidget(open_db)
        manual_buttons.addStretch(1)
        column.addLayout(manual_buttons)

        self.manual_status = QLabel("")
        self.manual_status.setProperty("role", "muted")
        self.manual_status.setWordWrap(True)
        column.addWidget(self.manual_status)

        # -- Reloaded-II, and where mods live ---------------------------------
        column.addSpacing(8)
        self._build_reloaded_block(column)

        column.addSpacing(8)
        column.addWidget(self._bold("Where to look for mods"))
        browse_note = QLabel(
            "\u201cOpen an existing mod\u201d starts browsing in your "
            "Reloaded-II Mods folder. Set a folder here to start somewhere "
            "else instead - handy if you keep works in progress outside "
            "Reloaded-II.")
        browse_note.setProperty("role", "muted")
        browse_note.setWordWrap(True)
        column.addWidget(browse_note)

        browse_row = QHBoxLayout()
        browse_row.addWidget(QLabel("Start browsing in:"))
        self.mod_browse_field = QLineEdit()
        self.mod_browse_field.setPlaceholderText(
            "Leave blank to use your Reloaded-II Mods folder")
        browse_row.addWidget(self.mod_browse_field, 1)
        for label, handler in (("Browse...", self.browse_mod_start_folder),
                               ("Clear", lambda: self.mod_browse_field.clear())):
            button = QPushButton(label)
            button.setMinimumWidth(button.sizeHint().width() + 8)
            button.clicked.connect(handler)
            browse_row.addWidget(button)
        column.addLayout(browse_row)

        # Where Reloaded-II *actually* loads from. A non-portable install
        # records an explicit ModConfigDirectory that can point anywhere,
        # and a mod written to the wrong folder simply never appears in the
        # launcher with no error to explain why.
        self.mods_folder_note = QLabel("")
        self.mods_folder_note.setProperty("role", "muted")
        self.mods_folder_note.setWordWrap(True)
        column.addWidget(self.mods_folder_note)
        self._refresh_mods_folder_note()

        # -- which .pac files ------------------------------------------------
        column.addSpacing(8)
        column.addWidget(self._bold("Pack files to read"))
        packs_note = QLabel(
            "The mod loader writes its own packs into the same folder as the "
            "game's, and FF16Tools takes the whole folder - so without this, "
            "an unpack gives you a mix of vanilla and whatever mods you have "
            "installed, and every reference in this tool quietly shows modded "
            "values. Loader packs are unticked automatically. Tick one to "
            "include it anyway, which is useful for inspecting a mod but not "
            "what you want as reference data.")
        packs_note.setProperty("role", "muted")
        packs_note.setWordWrap(True)
        column.addWidget(packs_note)

        self.pack_boxes = {}
        self.pack_list = QWidget()
        self.pack_list_column = QVBoxLayout(self.pack_list)
        self.pack_list_column.setContentsMargins(8, 2, 0, 2)
        self.pack_list_column.setSpacing(1)
        column.addWidget(self.pack_list)

        self.pack_summary = QLabel("")
        self.pack_summary.setProperty("role", "muted")
        self.pack_summary.setWordWrap(True)
        column.addWidget(self.pack_summary)
        self._pack_files = []
        self.refresh_pack_files()

        # -- old game versions ----------------------------------------------
        column.addSpacing(8)
        column.addWidget(self._bold("Archived game versions"))
        prune_note = QLabel(
            "Each unpack keeps a copy of that version's game data so mods "
            "built on it can still be updated after the game patches. This "
            "removes copies nothing needs any more.")
        prune_note.setProperty("role", "muted")
        prune_note.setWordWrap(True)
        column.addWidget(prune_note)

        prune_row = QHBoxLayout()
        self.prune_check_button = QPushButton("See what could be removed")
        self.prune_check_button.setMinimumWidth(
            self.prune_check_button.sizeHint().width() + 8)
        self.prune_check_button.clicked.connect(self.check_prunable_versions)
        prune_row.addWidget(self.prune_check_button)
        self.prune_button = QPushButton("Remove them")
        self.prune_button.setMinimumWidth(
            self.prune_button.sizeHint().width() + 8)
        self.prune_button.setEnabled(False)
        self.prune_button.clicked.connect(self.prune_versions)
        prune_row.addWidget(self.prune_button)
        prune_row.addStretch(1)
        column.addLayout(prune_row)

        self.prune_result = QLabel("")
        self.prune_result.setProperty("role", "muted")
        self.prune_result.setWordWrap(True)
        column.addWidget(self.prune_result)
        self._prune_plan = None

        self._refresh_folder_summary()
        return CollapsibleSection("Advanced options", body, expanded=False)

    # -- per-folder selection ---------------------------------------------------

    def _on_folder_tick(self, _on) -> None:
        self._refresh_folder_summary()

    def _select_all_folders(self) -> None:
        for box in self.folder_boxes.values():
            box.setChecked(True)

    def _select_no_folders(self) -> None:
        for box in self.folder_boxes.values():
            box.setChecked(False)

    def explicit_folders(self) -> list:
        """
        The folders ticked here, or [] when none are.

        Empty means "no opinion", which is what lets the three groups above
        stay in charge for anyone who never opens this section.
        """
        return [name for name, box in self.folder_boxes.items()
                if box.isChecked()]

    def _refresh_folder_summary(self) -> None:
        chosen = self.explicit_folders()
        if not chosen:
            self.folder_summary.setText(
                "Nothing ticked here, so the choice above decides.")
            return
        total = sum(game_install.GAME_FOLDERS_BY_NAME[n].approx_files
                    for n in chosen)
        self.folder_summary.setText(
            f"{len(chosen)} folder(s), roughly {total:,} files.")

    # -- newer tools ------------------------------------------------------------

    def _tool_row(self, tool: str) -> dict:
        return self.tool_update_rows[tool]

    def check_tool_update(self, tool: str) -> None:
        """
        Asks GitHub what the newest release is. Downloads nothing.
        """
        row = self._tool_row(tool)
        row["check"].setEnabled(False)
        row["get"].setEnabled(False)
        row["status"].setText("Asking GitHub...")
        worker = ToolUpdateWorker(tool, download=False)
        self._thread = run_in_thread(
            worker, on_finished=self._tool_update_done,
            on_failed=lambda message, t=tool: self._tool_update_failed(t, message),
            on_log=self._log)

    def download_tool_update(self, tool: str) -> None:
        row = self._tool_row(tool)
        row["check"].setEnabled(False)
        row["get"].setEnabled(False)
        row["status"].setText("Downloading...")
        worker = ToolUpdateWorker(tool, download=True)
        self._thread = run_in_thread(
            worker, on_finished=self._tool_update_done,
            on_failed=lambda message, t=tool: self._tool_update_failed(t, message),
            on_log=self._log)

    def _tool_update_done(self, result: dict) -> None:
        tool = result["tool"]
        row = self._tool_row(tool)
        row["check"].setEnabled(True)
        downloaded = result.get("downloaded")

        if downloaded is None:
            # A check only. The tag is reported rather than compared against
            # a bundled version number, because neither tool records the
            # version it was built from anywhere this can read - claiming
            # "you are up to date" would be a guess.
            row["status"].setText(
                f"The newest release is {result['tag']}. This tool ships its "
                f"own copy that is known to work; download only if you need "
                f"something newer.")
            row["get"].setEnabled(True)
            return

        row["status"].setText(f"Downloaded {result['tag']} to {downloaded}")
        field = self.cli_field if tool == "ff16tools" else self.audiomog_field
        field.setText(str(downloaded))
        if tool == "ff16tools":
            self.state.ff16tools_cli_path = Path(downloaded)
        else:
            self.state.audiomog_exe_path = Path(downloaded)
            # A freshly downloaded AudioMog brings its own
            # TerminalSettings.json, whose shipped default leaves
            # `ImmediatelyQuitOnceAllTasksAreDone` false - which hangs every
            # unpack. `download_latest` patches it, and this re-checks the
            # copy on disk so a hand-placed one is caught too.
            try:
                audiomog.ensure_terminal_settings_quiet(Path(downloaded))
            except Exception as exc:                          # noqa: BLE001
                self._log(f"Couldn't patch AudioMog's settings: {exc}")
        self._refresh_readiness()

    def _tool_update_failed(self, tool: str, message: str) -> None:
        row = self._tool_row(tool)
        row["check"].setEnabled(True)
        row["status"].setText(
            f"Couldn't reach GitHub: {message}. The copy that ships with this "
            f"tool is still fine.")
        self._log(message)

    # -- a database from somewhere else -----------------------------------------

    def browse_manual_nxd(self, _checked=False, path: str | None = None) -> None:
        if path is None:
            path = QFileDialog.getExistingDirectory(
                self, "Select a folder containing .nxd files")
        if path:
            self.manual_nxd_field.setText(path)

    def convert_manual_nxd(self) -> None:
        """
        Converts an nxd folder that did not come from this tool's own unpack.

        Points at the folder given rather than `nxd_unpack_dir`, and does not
        touch it - somebody converting a folder a friend sent them should not
        have that become "the unpacked game" for everything else.
        """
        folder = self.manual_nxd_field.text().strip()
        if not folder:
            self.manual_status.setText("Choose a folder with .nxd files in it.")
            return
        nxd_dir = Path(folder)
        if not nxd_dir.is_dir():
            self.manual_status.setText(f"That folder doesn't exist: {folder}")
            return
        if not any(nxd_dir.glob("*.nxd")):
            # Said up front rather than after a minute of FF16Tools failing.
            self.manual_status.setText(
                f"There are no .nxd files directly in {nxd_dir.name}. If you "
                f"picked the unpacked game folder, pick its nxd subfolder.")
            return
        if self.state.ff16tools_cli_path is None:
            self.manual_status.setText(
                "FF16Tools couldn't be found - set it above.")
            return

        destination = paths.local_data_dir() / "fft_data.sqlite"
        self.manual_convert_button.setEnabled(False)
        self._show_progress()
        self.manual_status.setText("Converting - this takes a minute.")
        worker = ConvertWorker(
            Path(self.state.ff16tools_cli_path), nxd_dir, destination)
        self._thread = run_in_thread(
            worker, on_finished=self._manual_converted,
            on_failed=self._manual_convert_failed, on_log=self._log)

    def _manual_converted(self, sqlite_path: Path) -> None:
        self.manual_convert_button.setEnabled(True)
        self.manual_status.setText(f"Loaded {sqlite_path}")
        self.adopt_database(sqlite_path)

    def _manual_convert_failed(self, message: str) -> None:
        self.manual_convert_button.setEnabled(True)
        self.progress.setVisible(False)
        self.manual_status.setText(f"That folder couldn't be converted: {message}")
        self._log(message)

    def open_existing_database(self, _checked=False,
                               path: str | None = None) -> None:
        """
        Loads a `fft_data.sqlite` directly, skipping conversion entirely.

        Worth having on its own: converting takes a minute and produces the
        same file every time, so reusing one from a previous session or from
        another modder is the fast path - and it is the only way in for
        somebody who has a database but not the .nxd files it came from.
        """
        if path is None:
            path, _ = QFileDialog.getOpenFileName(
                self, "Open a converted game database", "",
                "SQLite databases (*.sqlite *.db);;All files (*)")
        if not path:
            return
        database = Path(path)
        if not database.is_file():
            self.manual_status.setText(f"That file doesn't exist: {path}")
            return
        self.adopt_database(database)

    # Tables that only a converted FFT database has. Any one of them is
    # enough - a mod's own database holds only what that mod edits.
    KNOWN_TABLES = tuple(
        [spec.table("en") for spec in nxd_data.ALL_NXD_SPECS.values()]
        + ["UI-en", "OverrideEntryData", "OverrideAbilityActionData"]
    )

    @classmethod
    def looks_like_game_database(cls, database: Path) -> bool:
        """
        Whether this file is a converted FFT database at all.

        Asked before adopting because `load_database_tables` cannot answer
        it: that method collects successes and failures into one list of
        notes, so a database with none of the right tables comes back with a
        full list of "Couldn't read the ..." lines and looks, to anything
        counting the notes, exactly like a database that loaded fine.
        Pointing at the wrong .sqlite reported "Loaded junk.sqlite" followed
        by four error messages.
        """
        import sqlite3

        try:
            con = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
        except sqlite3.Error:
            return False
        try:
            names = {row[0] for row in con.execute(
                "select name from sqlite_master where type='table'")}
        except sqlite3.Error:
            return False
        finally:
            con.close()
        return any(name in names for name in cls.KNOWN_TABLES)

    def adopt_database(self, database: Path) -> None:
        """
        Makes a database the one every data tab reads.

        Runs the same tail as `_converted`, so a database opened by hand and
        one this tool converted leave the page in the same state. The version
        archive is attempted too, though it only does anything when there is
        an unpacked nxd folder to copy - a database opened on its own has no
        .nxd files behind it to archive.
        """
        self.progress.setVisible(False)
        if not self.looks_like_game_database(database):
            self.manual_status.setText(
                f"{database.name} doesn't have any of the tables this tool "
                f"edits, so it isn't a converted FFT game database.")
            return
        try:
            notes = self.load_database_tables(database)
        except Exception as exc:                              # noqa: BLE001
            self.manual_status.setText(f"That database couldn't be read: {exc}")
            self._log(repr(exc))
            return
        self.state.nxd_sqlite_path = database
        self._log(f"Database ready at {database}")
        for line in notes:
            self._log(f"   {line}")

        # What loaded, separately from what didn't. A mod's own database
        # legitimately holds only the tables that mod edits, so missing ones
        # are normal there and pasting "Couldn't read the poach table: No
        # 'PoachItem-en' table..." into the status made a correct outcome
        # read like a failure. The full text is in the log either way.
        #
        # Split on the prefix `load_database_tables` writes, which is in this
        # same class - not on a guess about how some other module phrases
        # its errors.
        loaded = [n for n in notes if not n.startswith("Couldn't read")]
        missing = len(notes) - len(loaded)
        summary = f"Loaded {database.name}: " + ("; ".join(loaded)
                                                 if loaded else "nothing")
        if missing:
            summary += (f". {missing} table(s) aren't in it - normal for a "
                        f"mod's own database, which only holds what it edits.")
        self.manual_status.setText(summary)
        self._archive_this_version(database)
        self._refresh_readiness()
        self.setup_changed.emit()

    # -- where mods live --------------------------------------------------------

    def browse_mod_start_folder(self, _checked=False,
                                path: str | None = None) -> None:
        if path is None:
            path = QFileDialog.getExistingDirectory(
                self, "Where should Open an existing mod start?")
        if path:
            self.mod_browse_field.setText(path)

    def mod_browse_start(self):
        """
        Where the Open-an-existing-mod dialog should start.

        The override first, then wherever Reloaded-II says it really loads
        mods from, then nothing - at which point the dialog opens wherever
        the platform prefers, which is better than pointing at a folder that
        does not exist.
        """
        override = self.mod_browse_field.text().strip() if hasattr(
            self, "mod_browse_field") else ""
        if override and Path(override).is_dir():
            return Path(override)
        try:
            configured = reloaded.configured_mods_folder()
        except Exception:                                     # noqa: BLE001
            configured = None
        if configured is not None and configured.is_dir():
            return configured
        root = getattr(self.state, "reloaded_ii_path", None)
        if root:
            try:
                effective = reloaded.effective_mods_folder(Path(root))
            except Exception:                                 # noqa: BLE001
                return None
            if effective.is_dir():
                return effective
        return None

    def _refresh_mods_folder_note(self) -> None:
        """
        Says where mods actually go, and warns when the two answers differ.

        `<install>/Mods` is only guaranteed in portable mode. The engine's
        own `configured_mods_folder` docstring says General Setup should
        surface the disagreement rather than exporting into the void, and
        the Qt page never did.
        """
        if not hasattr(self, "mods_folder_note"):
            return
        try:
            configured = reloaded.configured_mods_folder()
        except Exception:                                     # noqa: BLE001
            configured = None
        root = getattr(self.state, "reloaded_ii_path", None)
        conventional = Path(root) / "Mods" if root else None

        if configured is None and conventional is None:
            self.mods_folder_note.setText(
                "Reloaded-II hasn't been found yet, so there's nowhere to "
                "browse by default.")
            return
        if configured is None:
            self.mods_folder_note.setText(f"Mods folder: {conventional}")
            return
        if conventional is not None and configured != conventional:
            self.mods_folder_note.setText(
                f"Reloaded-II loads mods from {configured}, not "
                f"{conventional}. A mod written to the wrong one never "
                f"appears in the launcher, so this tool uses the first.")
            self.mods_folder_note.setProperty("role", "attention")
        else:
            self.mods_folder_note.setText(f"Mods folder: {configured}")
            self.mods_folder_note.setProperty("role", "muted")
        self.mods_folder_note.style().unpolish(self.mods_folder_note)
        self.mods_folder_note.style().polish(self.mods_folder_note)

    # -- which .pac files -------------------------------------------------------

    def refresh_pack_files(self) -> None:
        """
        Rebuilds the list for whatever game folder is selected now.

        A choice already made for a pack of the same name is kept, so
        switching folders and back does not silently re-tick the loader's
        packs. That matters because the default for those is OFF and
        re-ticking them is how an unpack quietly becomes a mix of vanilla
        and installed mods.
        """
        if not hasattr(self, "pack_boxes"):
            return                       # Advanced pane not built yet.
        previous = {name: box.isChecked()
                    for name, box in self.pack_boxes.items()}

        while self.pack_list_column.count():
            item = self.pack_list_column.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.pack_boxes = {}

        source = self.folder_field.text().strip()
        self._pack_files = (game_install.list_pack_files(Path(source))
                            if source else [])
        for pack in self._pack_files:
            box = QCheckBox(pack.label())
            # Loader output starts off. Everything else starts on.
            box.setChecked(previous.get(pack.name, not pack.is_mod_output))
            box.toggled.connect(self._refresh_pack_summary)
            self.pack_boxes[pack.name] = box
            self.pack_list_column.addWidget(box)
        self._refresh_pack_summary()

    def selected_packs(self) -> list:
        return [pack for pack in self._pack_files
                if self.pack_boxes.get(pack.name) is not None
                and self.pack_boxes[pack.name].isChecked()]

    def packs_for_run(self):
        """
        The packs this unpack should read, or None for "all of them".

        None is not the same as a list of everything: it lets FF16Tools do
        the whole folder in one command instead of one command per pack,
        which is markedly faster. So the subset path is only taken when
        something is actually being left out.
        """
        if not self._pack_files:
            return None
        chosen = self.selected_packs()
        if len(chosen) == len(self._pack_files):
            return None
        return chosen

    def _refresh_pack_summary(self, _on=None) -> None:
        if not self._pack_files:
            self.pack_summary.setText(
                "No .pac files found yet - choose your game folder above.")
            return
        chosen = self.selected_packs()
        excluded = len(self._pack_files) - len(chosen)
        loader = sum(1 for p in self._pack_files if p.is_mod_output)
        text = f"{len(chosen)} of {len(self._pack_files)} pack file(s)."
        if loader:
            included_loader = sum(1 for p in chosen if p.is_mod_output)
            if included_loader:
                text += (f" {included_loader} of them are the mod loader's, so "
                         f"this unpack will NOT be clean vanilla.")
            else:
                text += f" The {loader} loader pack(s) are excluded."
        if not chosen:
            text += " Nothing ticked, so there is nothing to unpack."
        self.pack_summary.setText(text)

    # -- old game versions ------------------------------------------------------

    def _mods_folder(self):
        """Where Reloaded-II keeps its mods, or None if it cannot be found."""
        try:
            root = getattr(self.state, "reloaded_ii_path", None)
            if root:
                return reloaded.effective_mods_folder(Path(root))
            return reloaded.configured_mods_folder()
        except Exception:                                     # noqa: BLE001
            return None

    def check_prunable_versions(self) -> None:
        """
        Works out which archived versions nothing needs, and says so first.

        Deliberately two steps. A deleted archive cannot be recreated - the
        game build it came from is not installed any more - so this shows
        the list and waits rather than removing anything on one click. The
        engine is already timid about what it will even offer: a version has
        to be claimed by no mod in the Mods folder AND fall outside the most
        recent few.
        """
        from ... import version_archive

        self._prune_plan = None
        self.prune_button.setEnabled(False)
        try:
            installed = ""
            converted = getattr(self.state, "nxd_sqlite_path", None)
            if converted:
                from ... import migration
                installed = migration.read_game_version(converted) or ""
            in_use = version_archive.versions_in_use(self._mods_folder(),
                                                     installed)
            plan = version_archive.plan_prune(in_use)
        except Exception as exc:                              # noqa: BLE001
            self.prune_result.setText(f"Couldn't check: {exc}")
            return

        kept = len(plan.keep_in_use) + len(plan.keep_recent)
        if not plan.remove:
            self.prune_result.setText(
                f"Nothing to remove - all {kept} archived version(s) are "
                f"either in use by a mod or recent enough to keep.")
            return

        self._prune_plan = plan
        self.prune_button.setEnabled(True)
        # PrunePlan holds ArchivedVersion entries, not names - `remove`,
        # `keep_in_use` and `keep_recent` are all lists of records, and
        # `apply_prune` reads `entry.directory` off them.
        names = sorted(entry.version for entry in plan.remove)
        self.prune_result.setText(
            f"{len(plan.remove)} version(s) could go: {', '.join(names)}. "
            f"Keeping {kept}: {len(plan.keep_in_use)} in use by a mod, "
            f"{len(plan.keep_recent)} recent.")

    def prune_versions(self) -> None:
        """Removes exactly what the check above listed, and nothing else."""
        from ... import version_archive

        if self._prune_plan is None:
            self.prune_result.setText("Check first, so you can see what goes.")
            return
        try:
            removed = version_archive.apply_prune(self._prune_plan)
        except Exception as exc:                              # noqa: BLE001
            self.prune_result.setText(f"Couldn't remove them: {exc}")
            return
        # The plan is spent. Leaving it would let a second press act on a
        # list already applied.
        self._prune_plan = None
        self.prune_button.setEnabled(False)
        self.prune_result.setText(
            f"Removed {len(removed)}: {', '.join(removed)}."
            if removed else "Nothing was removed.")
        self._log(f"Removed {len(removed)} archived game version(s).")

    @staticmethod
    def _bold(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet("font-weight: 600;")
        return label

    def _browse_row(self, label: str, field: QLineEdit, handler,
                    files: bool = False) -> QHBoxLayout:
        row = QHBoxLayout()
        caption = QLabel(label)
        caption.setMinimumWidth(110)
        row.addWidget(caption)
        row.addWidget(field, 1)
        button = QPushButton("Browse...")
        button.setMinimumWidth(button.sizeHint().width() + 8)
        button.clicked.connect(handler)
        row.addWidget(button)
        return row

    def _browse_cli(self, _checked=False, path: str | None = None) -> None:
        if path is None:
            path, _ = QFileDialog.getOpenFileName(self, "Select FF16Tools.CLI")
        if path:
            self.cli_field.setText(path)
            self.state.ff16tools_cli_path = Path(path)
            self._log(f"Using FF16Tools at {path}")

    def _browse_audiomog(self, _checked=False, path: str | None = None) -> None:
        if path is None:
            path, _ = QFileDialog.getOpenFileName(self, "Select AudioMog")
        if path:
            self.audiomog_field.setText(path)
            self.state.audiomog_exe_path = Path(path)
            self._log(f"Using AudioMog at {path}")

    def _browse_output(self, _checked=False, path: str | None = None) -> None:
        if path is None:
            path = QFileDialog.getExistingDirectory(self, "Unpack into")
        if path:
            self.output_field.setText(path)

    def check_reference_tables(self) -> None:
        """
        Asks for the newest published reference tables.

        On a worker thread because it is network I/O, and reported per file:
        "checked, all current" and "couldn't reach GitHub" are different
        outcomes and a single "done" would hide which one happened.
        """
        self.check_tables_button.setEnabled(False)
        self.tables_result.setText("Checking...")
        worker = ReferenceTableWorker()
        self._thread = run_in_thread(
            worker, on_finished=self._tables_checked,
            on_failed=self._tables_failed, on_log=self._log)

    def _tables_checked(self, reports) -> None:
        self.check_tables_button.setEnabled(True)
        updated = sum(r.outstanding for r in reports if r.ok)
        failed = [r for r in reports if not r.ok]
        parts = []
        if updated:
            # WHAT changed, not just how many files. A person does not know
            # what `JOB_DATA.cs` is, and "3 files updated" gives them no way
            # to find out whether it affects them; each source carries a
            # one-line consequence for exactly this.
            for report in reports:
                if report.ok and report.outstanding:
                    parts.append(
                        f"{report.summary()} - affects "
                        f"{report.source.consequence}.")
            parts.append("Restart Mod Studio to pick them up.")
        if failed:
            parts.append(" ".join(r.summary() for r in failed))
        if not parts:
            parts.append("Everything is already up to date.")
        self.tables_result.setText(" ".join(parts))
        if updated:
            self._invalidate_schema_caches()

    @staticmethod
    def _invalidate_schema_caches() -> None:
        """
        Drops the parsed-schema caches so a fetched file is not ignored.

        `all_layouts`, `all_models` and `flag_enums` are `lru_cache`d, and
        `ALL_NXD_SPECS` is built once at import. Without clearing these the
        download would land on disk, the message would say it had been
        applied, and nothing would change until the next launch - the tool
        telling the person it had done something it had not.

        The registry itself still needs the restart the message asks for:
        pages hold references to specs built at construction. Clearing the
        caches is what makes that restart sufficient rather than a second
        thing to remember.
        """
        from ... import nxd_layouts, xml_models
        for cached in (nxd_layouts.all_layouts, xml_models.all_models,
                       xml_models.flag_enums):
            try:
                cached.cache_clear()
            except AttributeError:                            # noqa: PERF203
                pass

    def _tables_failed(self, message: str) -> None:
        self.check_tables_button.setEnabled(True)
        self.tables_result.setText(f"Couldn't check: {message}")

    def unpack_filter(self) -> str | None:
        """The custom filter, or None when the ticks above decide."""
        text = self.filter_field.text().strip()
        return text or None

    # -- game folder ------------------------------------------------------------

    def detect_game_folder(self) -> None:
        """
        Finds the install through `game_install.autodetect_pack_folders`.

        The first version of this called `find_game_data_folder`,
        `detect_game_folder` and `find_install` in turn - three names that do
        not exist in `game_install`. Every one raised AttributeError into a
        bare `except`, so detection silently never worked, in an interface
        where it had always worked before. Guessing at an API and catching
        the consequences is how you ship a feature that cannot run.

        The real API returns PackFolder(path, pack_count), best first.
        """
        try:
            candidates = game_install.autodetect_pack_folders()
        except Exception as exc:                              # noqa: BLE001
            candidates = []
            self._log(f"Couldn't search for the game automatically: {exc}")

        if candidates:
            best = candidates[0]
            self.folder_field.setText(str(best.path))
            extra = (f" ({len(candidates)} candidates found - Browse if this "
                     f"is the wrong one)") if len(candidates) > 1 else ""
            self.folder_hint.setText(
                f"Found your game automatically: {best.pack_count} pack "
                f"files.{extra}")
        else:
            self.folder_hint.setText(
                "Couldn't find the game automatically. Use Browse to point at "
                "the folder holding the game's .pac files (right-click the game "
                "in Steam, Manage, Browse local files, then look for a data "
                "folder).")

    def detect_bundled_tools(self) -> None:
        """
        Points at the FF16Tools and AudioMog that ship with this tool.

        They live in `tools/` beside the program and the engine already
        knows how to find them - `ff16tools.find_bundled_cli()` and
        `audiomog.find_bundled_exe()`. This page simply never called them,
        so it reported "FF16Tools couldn't be found" while FF16Tools sat in
        the folder next to it. The old interface has always done this.

        An explicit choice under Advanced options wins: somebody who pointed
        at a newer copy meant it.
        """
        if self.state.ff16tools_cli_path is None:
            try:
                found = ff16tools.find_bundled_cli()
            except Exception:                                 # noqa: BLE001
                found = None
            if found:
                self.state.ff16tools_cli_path = found
                self.cli_field.setText(str(found))
                # Not logged. Finding the bundled copy is the normal case -
                # it ships in this tool's own folder and is pointed at
                # automatically - so announcing it every launch is noise
                # ahead of anything that actually matters. A copy that had
                # to be looked for elsewhere, or none at all, still reports.
                pass

        if getattr(self.state, "audiomog_exe_path", None) is None:
            try:
                found = audiomog.find_bundled_exe()
            except Exception:                                 # noqa: BLE001
                found = None
            if found:
                self.state.audiomog_exe_path = found
                self.audiomog_field.setText(str(found))
                pass

    def detect_reloaded(self) -> None:
        """
        Finds Reloaded-II, which is where an exported mod has to end up.

        Worth showing here rather than only on the Export page: someone
        setting up wants to know now whether the tool can find their mod
        loader, not after they have built a mod.
        """
        try:
            root = reloaded.find_installed_reloaded()
        except Exception:                                     # noqa: BLE001
            root = None

        if root is None:
            self.reloaded_field.setText("")
            self.reloaded_hint.setText(
                "Couldn't find Reloaded-II automatically. You can still build "
                "a mod - you'll just need to say where it goes when you "
                "export.")
            return

        self.reloaded_field.setText(str(root))
        try:
            mods = reloaded.effective_mods_folder(root)
            installed = reloaded.installed_mod_ids(root)
            self.reloaded_hint.setText(
                f"Mods folder: {mods} ({len(installed)} mods installed).")
        except Exception:                                     # noqa: BLE001
            self.reloaded_hint.setText(f"Found Reloaded-II at {root}.")

    def browse_game_folder(self, _checked=False, path: str | None = None) -> None:
        if path is None:
            path = QFileDialog.getExistingDirectory(
                self, "Select the folder holding the game's .pac files")
        if not path:
            return
        self.folder_field.setText(path)
        folder = Path(path)
        looks_right = True
        checker = getattr(game_install, "looks_like_pack_folder", None)
        if checker:
            try:
                looks_right = bool(checker(folder))
            except Exception:                                 # noqa: BLE001
                looks_right = True
        self.folder_hint.setText(
            "" if looks_right else
            "There are no .pac files directly in there, which usually means "
            "it's the wrong folder.")

    # -- opening a mod ------------------------------------------------------------

    def open_mod(self, _checked=False, path: str | None = None) -> None:
        """
        Opens a mod and loads its edits back in.

        **It used to load nothing.** It cleared the previous mod, recorded
        the folder, and said "Editing: <name>" - so the tool reported a mod
        was open while every tab still showed vanilla. The README has always
        said an opened mod's tables load back in ready to change; only the
        Tkinter page did it.

        That omission also made a documented engine question live. Every
        database-derived edit store is cleared by
        `clear_opened_mod_content`; `edits`, `job_command_edits` and
        `item_table_edits` are not. The Tkinter path never suffered for it
        because it assigns all three wholesale immediately afterwards, so
        whatever the clear left behind is overwritten. This page cleared and
        then assigned nothing, so **the previous mod's job edits survived
        into the next one** - measured against real mods: open Dragoon
        Meliadoul (3 jobs, 7 job commands), then open the texture pack
        (which has neither), and all ten were still there.

        Assigning them here fixes that the same way Tkinter does, without
        touching the engine. The question of whether
        `clear_opened_mod_content` should clear them itself is still open
        and is still Zodi's to answer - this makes the interface correct
        either way rather than depending on the answer.
        """
        if path is None:
            start = self.mod_browse_start()
            path = QFileDialog.getExistingDirectory(
                self, "Open an existing mod", str(start) if start else "")
        if not path:
            return
        folder = Path(path)

        try:
            existing = modconfig.open_existing_mod(folder)
        except Exception as exc:                              # noqa: BLE001
            self._say(f"That mod's files couldn't be read: {exc}", "danger")
            self._log(repr(exc))
            return

        # Anything belonging to a previously-opened mod goes first. Leaving
        # it behind is how one mod's files once got converted as though they
        # belonged to the next one.
        self.state.clear_opened_mod_content()
        self.state.opened_mod_dir = folder
        self.state.loaded_mod_root = existing.mod_root
        self.state.loaded_mod_config = existing.config
        self.state.loaded_game_mode = (
            existing.game_mode or existing.job_command_game_mode
            or existing.table_game_mode)
        self.state.edits = existing.edits
        self.state.job_command_edits = existing.job_command_edits
        self.state.job_command_preserved = existing.job_command_preserved
        self.state.job_preserved = existing.job_preserved
        self.state.table_preserved = existing.table_preserved
        self.state.item_table_edits = dict(existing.table_edits)
        # And the XML tables recovered through a derived spec. Without this
        # the mod's StatusEffectData.xml (and sixteen others) would be read
        # by modconfig and then dropped on the floor here.
        self.state.derived_table_edits = dict(existing.derived_table_edits)
        if existing.derived_table_versions:
            self.state.derived_table_versions.update(
                existing.derived_table_versions)

        # The mod's replaced FILES, which are a separate recovery from its
        # tables. Without this a texture pack opened as an empty mod: the
        # Textures tab showed no pending replacements and Export Mod said
        # "nothing edited yet" for a mod made entirely of textures.
        #
        # Textures are marked `already_staged` so Export copies them through
        # instead of decoding and re-encoding an image that is already in
        # the exact target format. Sounds and anything else are held whole -
        # a repacked .sab does not record which track was swapped or where
        # it came from, so offering them as editable would be a lie.
        try:
            recovered = modconfig.recover_replaced_files(existing.mod_root)
        except Exception as exc:                              # noqa: BLE001
            self._log(f"Couldn't read this mod's replaced files: {exc}")
            recovered = None
        if recovered is not None:
            for relative_path, source in recovered.textures.items():
                self.state.texture_edits[relative_path] = {
                    "source_path": source,
                    "is_face_texture": td.is_face_texture(relative_path),
                    "already_staged": True,
                }
            self.state.sound_file_replacements = dict(recovered.sounds)
            self.state.other_file_replacements = dict(recovered.other)
            # Force the Textures and Sounds tabs to rescan, so the newly
            # staged entries appear. They rebuild the tree themselves now.
            self.state.texture_tree = None
            self.state.sound_tree = None
            if not recovered.is_empty():
                self._log(f"Loaded this mod's replaced files: "
                          f"{recovered.summary()}.")

        # The mod's own game data, converted from the `.nxd` files it ships.
        #
        # Most mods carry `.nxd` and no database - the game reads those
        # wholesale - so this conversion is the normal path, not a fallback.
        # Without it Game Updates has no `mod_sqlite_path` and refuses.
        #
        # An already-converted `fft_data.sqlite` beside them is taken
        # directly, because converting it again would produce the same file
        # a minute later.
        mod_nxd = existing.mod_root / "FFTIVC" / "data" / (
            self.state.loaded_game_mode or "enhanced") / "nxd"
        mod_database = mod_nxd / "fft_data.sqlite"
        if mod_database.is_file():
            self.state.mod_sqlite_path = mod_database
            self.state.mod_nxd_dir = mod_nxd
            self._log(f"This mod ships a converted database: {mod_database}")
        else:
            self._start_mod_nxd_recovery(existing.mod_root)

        name = existing.config.get("ModName", folder.name)
        self.mod_status.setText(f"Editing: {name}")
        self._log(f"Opened {folder}")
        for line in self._describe_opened_mod(existing):
            self._log(f"   {line}")
        self._refresh_readiness()
        self.setup_changed.emit()

    def _start_mod_nxd_recovery(self, mod_root: Path) -> None:
        """
        Converts the mod's `.nxd` files, on a worker thread.

        Skipped only when FF16Tools is genuinely unavailable, and said
        rather than passed over - a mod whose game data could not be read is
        a mod half open, and the tabs that depend on it will look empty for
        no stated reason.
        """
        cli_path = self.state.ff16tools_cli_path
        if cli_path is None:
            self._log("Skipping this mod's .nxd files: FF16Tools.CLI isn't "
                      "available, so its game data can't be read.")
            return
        data_dir = Path(mod_root) / "FFTIVC" / "data"
        has_nxd = data_dir.is_dir() and any(data_dir.glob("*/nxd/*.nxd"))
        if not has_nxd:
            return                       # no .nxd at all; the tables were it
        self._say("Reading this mod's game data - this takes a minute.",
                  "muted")
        self._show_progress()
        worker = ModNxdWorker(
            Path(mod_root), Path(cli_path),
            getattr(self.state, "nxd_sqlite_path", None))
        self._thread = run_in_thread(
            worker, on_finished=self._mod_nxd_ready,
            on_failed=self._mod_nxd_failed, on_log=self._log)

    def _mod_nxd_ready(self, result: dict) -> None:
        self.progress.setVisible(False)
        database = result.get("mod_sqlite")
        if database is None:
            self._say("", "muted")
            return

        self.state.mod_sqlite_path = database
        if result.get("nxd_dir") is not None:
            self.state.mod_nxd_dir = result["nxd_dir"]
        self._log(f"This mod's game data is ready at {database}")

        recovered = result.get("recovered")
        if recovered is None:
            # No vanilla database to diff against, so the mod's own becomes
            # the working one. Every tab is then editable, showing the mod's
            # real values - just without the marking that says which of them
            # differ from the game's.
            self.adopt_database(Path(database))
            self._say(
                "Loaded this mod's game data, so every tab is editable. "
                "Unpack your game files to also see which values it changed.",
                "ok")
            return

        self._apply_recovered_nxd(recovered, result.get("unmodelled"))
        self._say("Loaded this mod's game data and worked out what it "
                  "changed.", "ok")
        self._refresh_readiness()
        self.setup_changed.emit()

    def _apply_recovered_nxd(self, recovered, unmodelled=None) -> None:
        """
        Merges what the mod's files turned out to contain into the session.

        Merge rather than replace, with anything already in state winning.
        The sequence that makes this matter: open a mod with no game files
        (so its own database becomes the working one and the tabs are
        editable), make some edits, then unpack. The diff runs at that point
        and would otherwise overwrite the dicts, throwing away everything
        typed in between. Nothing recovered can be newer than a session
        edit, so session edits win on every conflict.
        """
        state = self.state
        # Every registered per-language table. A table left out of this
        # list would open a mod, recover its edits correctly, and then
        # throw them away here - silently, because the merge that never
        # ran leaves the store exactly as it was.
        for key in nxd_data.ALL_NXD_SPECS:
            state.set_nxd_edits_for(key, _merge_language_edits(
                recovered.edits_for(key), state.nxd_edits_for(key)))
        # Tables with no typed reader, merged the same way: what the mod
        # holds, with anything already in progress kept on top.
        opened_unmodelled = unmodelled or {}
        if opened_unmodelled:
            store = state.unmodelled_table_edits or {}
            for table, rows in opened_unmodelled.items():
                merged = dict(rows)
                merged.update(store.get(table, {}))
                store[table] = merged
            state.unmodelled_table_edits = store
        state.override_action_edits = _merge_keyed_edits(
            recovered.override_action_edits, state.override_action_edits)
        state.entry_edits = _merge_keyed_edits(
            recovered.entry_edits, state.entry_edits)
        # Rows the mod moved. Chained onto the session's, not merged - the
        # two can be keyed against different databases.
        state.entry_rekeys = _compose_entry_rekeys(
            recovered.entry_rekeys, state.entry_rekeys)
        state.entry_dropped.update(recovered.entry_dropped)

    def _mod_nxd_failed(self, message: str) -> None:
        self.progress.setVisible(False)
        # The mod IS open - its tables and files loaded. Only its .nxd game
        # data did not, so this is a partial open, not a failed one.
        self._say(f"This mod's tables and files are loaded, but its game "
                  f"data couldn't be read: {message}", "attention")
        self._log(message)

    @staticmethod
    def _describe_opened_mod(existing) -> list:
        """
        Says what the mod actually brought in - and only that.

        Naming the files it does NOT have told a texture pack's author about
        JobData.xml and JobCommandData.xml, two filenames they have no
        reason to care about. The Tkinter page learned this; the wording
        follows it.
        """
        parts = []
        if existing.edits:
            count = len(existing.edits)
            parts.append(f"{count} job{'s' if count != 1 else ''}")
        if existing.job_command_edits:
            count = len(existing.job_command_edits)
            parts.append(f"{count} job command{'s' if count != 1 else ''}")
        for key, records in sorted((existing.table_edits or {}).items()):
            if records:
                parts.append(f"{len(records)} {key.replace('_', ' ')}")
        return parts or ["No table edits in it - textures or sounds only."]

    # -- unpacking -----------------------------------------------------------------

    def chosen_groups(self) -> list:
        return [key for key, box in self.group_boxes.items() if box.isChecked()]

    def chosen_folders(self) -> list:
        """
        The folders to unpack, in the engine's terms.

        An explicit per-folder selection under Advanced options wins:
        somebody who went and ticked `nxd` and nothing else meant exactly
        that, and having the three broad groups quietly add `sound` back on
        top would make the finer control useless.
        """
        explicit = self.explicit_folders()
        if explicit:
            return explicit
        chosen = set(self.chosen_groups())
        folders = []
        for key, _label, _detail, group_folders, _default in UNPACK_GROUPS:
            if key in chosen:
                folders.extend(group_folders)
        return folders

    def start_unpack(self) -> None:
        folder = self.folder_field.text().strip()
        if not folder:
            self._say("Set the game data folder first.", "attention")
            return
        if not Path(folder).is_dir():
            self._say(f"That folder doesn't exist: {folder}", "danger")
            return
        if not self.chosen_groups() and not self.explicit_folders():
            self._say("Tick at least one thing you want to be able to edit.",
                      "attention")
            return
        if self.state.ff16tools_cli_path is None:
            self._say(
                "FF16Tools couldn't be found. It normally ships in this tool's "
                "tools folder - set it under Advanced options.", "danger")
            return

        destination = Path(self.output_field.text().strip()
                           or (paths.local_data_dir() / "UnpackedGame"))
        custom = self.unpack_filter()
        filters = ([custom] if custom
                   else game_install.filters_for_folders(self.chosen_folders()))

        self.unpack_button.setEnabled(False)
        self.adopt_button.setEnabled(False)
        self._show_progress(determinate=True)
        self._say(
            "Unpacking your game files. This takes several minutes and only "
            "reads them - nothing is modified.", "muted")

        # Rebuilt against the folder about to be used, not whatever was
        # selected when Advanced options was last opened. Applying one
        # install's tick boxes to another install's packs is how a pack
        # nobody chose ends up in the unpack.
        self.refresh_pack_files()
        if self._pack_files and not self.selected_packs():
            self._say("No pack files are ticked, so there is nothing to "
                      "unpack. See Advanced options.", "attention")
            self.unpack_button.setEnabled(True)
            self.adopt_button.setEnabled(True)
            self.progress.setVisible(False)
            return

        worker = UnpackWorker(
            Path(self.state.ff16tools_cli_path), Path(folder), destination,
            filters, self.include_diff.isChecked(),
            packs=self.packs_for_run())
        self._thread = run_in_thread(
            worker, on_finished=self._unpacked, on_failed=self._unpack_failed,
            on_log=self._log, on_progress=self._unpack_progress)

    def _show_progress(self, determinate: bool = False) -> None:
        """
        Shows the bar, in the right mode for the job about to run.

        The unpack switches it to a real 0..N range; adopting and converting
        cannot report progress and need the indeterminate one back. Without
        resetting, the first adopt after an unpack shows a full, motionless
        bar - which reads as finished-but-stuck rather than as working.
        """
        if determinate:
            self.progress.setRange(0, UnpackWorker.SCALE)
            self.progress.setValue(0)
        else:
            self.progress.setRange(0, 0)
        self.progress.setVisible(True)

    def _unpack_progress(self, done: int, total: int) -> None:
        """
        Real progress, not a spinner.

        The bar was created with `setRange(0, 0)` - Qt's indeterminate mode -
        and nothing was connected to the worker's `progress` signal at all,
        so it could only ever spin. For a job that takes several minutes,
        an indeterminate bar and a hung program look identical, which is
        the whole reason the Tkinter page uses a determinate one.
        """
        self.progress.setRange(0, total)
        self.progress.setValue(done)

    def _unpacked(self, destination: Path) -> None:
        # This adopt is the tail of an unpack, so the conversion follows it.
        self._convert_after_adopt = True
        self.progress.setVisible(False)
        self.unpack_button.setEnabled(True)
        self.adopt_button.setEnabled(True)
        self._log(f"Unpacked into {destination}")
        # Straight into the same path an adopted folder takes, so unpacking
        # and adopting cannot end up meaning different things.
        self.adopt_existing_folder(path=str(destination))

    def _unpack_failed(self, message: str) -> None:
        self.progress.setVisible(False)
        self.unpack_button.setEnabled(True)
        self.adopt_button.setEnabled(True)
        self._say(f"The unpack didn't finish: {message}", "danger")

    def start_conversion(self) -> None:
        """
        Turns the unpacked `nxd` folder into the SQLite every data tab reads.
        """
        unpacked = getattr(self.state, "nxd_unpack_dir", None)
        if unpacked is None:
            self._say("Adopt or unpack a game folder first.", "attention")
            return
        nxd_dir = Path(unpacked) / "nxd"
        if not nxd_dir.is_dir():
            self._say(
                f"There's no nxd folder in {unpacked}, so there's nothing to "
                f"convert. Unpack again with Game data ticked.", "attention")
            return
        cli_path = self.state.ff16tools_cli_path
        if cli_path is None:
            self._say(
                "FF16Tools couldn't be found. It normally ships in this tool's "
                "tools folder - set it under Advanced options.", "danger")
            return

        destination = paths.local_data_dir() / "fft_data.sqlite"
        self._show_progress()
        self._say("Converting the game data - this takes a minute.", "muted")

        worker = ConvertWorker(Path(cli_path), nxd_dir, destination)
        self._thread = run_in_thread(
            worker, on_finished=self._converted, on_failed=self._convert_failed,
            on_log=self._log)

    def _converted(self, sqlite_path: Path) -> None:
        self.progress.setVisible(False)
        # `nxd_sqlite_path`, which is the field WizardState actually
        # declares. This wrote `game_sqlite_path` - a name that exists
        # nowhere in the engine and that nothing else in the tool reads, so
        # the path to the converted database was being stored where no one
        # would look for it. Reading it before a conversion raised
        # AttributeError rather than returning None, which is how it was
        # found.
        self.state.nxd_sqlite_path = sqlite_path
        loaded = self.load_database_tables(sqlite_path)
        self._log(f"Database ready at {sqlite_path}")
        for line in loaded:
            self._log(f"   {line}")
        self._archive_this_version(sqlite_path)
        self._refresh_readiness()
        self.setup_changed.emit()

    def _archive_this_version(self, sqlite_path: Path) -> None:
        """
        Keeps a copy of this game version's .nxd files.

        **The Qt page never did this**, and the Tkinter one has since the
        version archive existed (`gui/step_setup.py`, at the end of its
        conversion). The consequence is not visible on this page at all: it
        shows up two pages away, as Game Updates having no baseline to
        compare a new patch against, which reads as Game Updates being
        broken rather than as setup having skipped a step.

        Timing is the whole point. Once the player updates the game, the old
        .nxd files are gone from their disk and there is nowhere to download
        them from - so the only moment this copy can be taken is while that
        version is still installed. Straight after conversion, because that
        is the first point at which the version string is readable.

        Every failure is logged and swallowed. This is insurance against a
        future problem and must never be the reason a successful conversion
        reports as failed.
        """
        from ... import migration, version_archive

        unpacked = getattr(self.state, "nxd_unpack_dir", None)
        if unpacked is None:
            return
        nxd_dir = Path(unpacked) / "nxd"
        if not nxd_dir.is_dir():
            return
        try:
            version = migration.read_game_version(sqlite_path)
            entry = version_archive.archive_unpacked_nxd(
                nxd_dir, version, source=Path(unpacked).name,
                # Whether the unpack took in anything that looks like an
                # installed mod. A baseline mixed with mod content makes
                # every diff drawn against it wrong, and "unknown" has to
                # count as not clean - claiming cleanliness we cannot verify
                # is the dangerous direction to guess.
                clean_unpack=not self.include_diff.isChecked(),
                sqlite_path=sqlite_path,
                converter=version_archive.converter_fingerprint(
                    self.state.ff16tools_cli_path),
            )
            if entry is None:
                return
            if entry.version_unknown:
                self._log(
                    "Archived this version's game data, but couldn't read the "
                    "game's version string, so it's filed by date. You can "
                    "rename it later if you know which build it was.")
            else:
                self._log(
                    f"Archived {entry.file_count} game data file(s) as "
                    f"{entry.version} ({entry.size_mb:.1f} MB) so mods built "
                    f"on it can be updated after the game patches.")
        except Exception as exc:                              # noqa: BLE001
            self._log(f"Couldn't archive this version's game data: {exc}")

    def _convert_failed(self, message: str) -> None:
        self.progress.setVisible(False)
        self._say(f"The conversion didn't finish: {message}", "danger")

    def load_database_tables(self, sqlite_path: Path) -> list:
        """
        Reads the tables the data tabs need out of a converted database.

        Separate from the conversion so it can be run against a database
        that already exists - which is both how an adopted folder gets its
        data and the only part of this path that can be exercised without
        Windows.
        """
        # Every store this method fills is emptied first.
        #
        # It only ever ASSIGNED on success, so a table the new database
        # lacks silently kept the previous one's rows. Loading the game's
        # database and then a texture pack's - which has none of these
        # tables - left all four still reporting the game's 96 poach
        # entries, 512 abilities, 368 overrides and 516 encounter rows,
        # while the status said the pack had loaded. The data tabs would
        # have been editing one database's rows under another one's name.
        #
        # Same shape as the mod-switching leak: state surviving a switch
        # because the thing that replaces it only runs when it succeeds.
        for _key in nxd_data.ALL_NXD_SPECS:
            self.state.set_nxd_records_for(_key, {})
        self.state.override_action_records = []
        self.state.entry_records = []

        notes = []
        for language in ("en",):
            # Every registered per-language table, in registry order.
            #
            # This used to be one near-identical try/except per table, and a
            # table added without its block here loaded no reference rows -
            # so its page opened empty and looked broken rather than
            # unwired. `Item-<lang>` is the recorded case: it lives in the
            # same converted database as `Ability-<lang>` beside it and the
            # Tkinter Items tab had always read it, but the Qt fetch never
            # did, so an item showed as "042 - " with no name and the whole
            # per-language half of that tab had nothing behind it. The loop
            # is what stops that being possible one table at a time.
            #
            # One table failing must not stop the others: a mod's own
            # database holds only what that mod edits, so missing tables
            # here are normal and are reported as notes, not raised.
            for _key, _spec in nxd_data.ALL_NXD_SPECS.items():
                try:
                    records = nxd_data.read_nxd_table(
                        sqlite_path, _key, language)
                    store = self.state.nxd_records_for(_key)
                    store[language] = records
                    self.state.set_nxd_records_for(_key, store)
                    notes.append(
                        f"{len(records)} {_spec.label.lower()} ({language})")
                except Exception as exc:                      # noqa: BLE001
                    notes.append(
                        f"Couldn't read the {_spec.label.lower()} table: {exc}")

        # The override layer is one table for all languages - what an ability
        # DOES is not translated.
        try:
            actions = nxd_data.read_override_action_table(sqlite_path)
            self.state.override_action_records = actions
            notes.append(f"{len(actions)} ability overrides")
        except Exception as exc:                              # noqa: BLE001
            notes.append(f"Couldn't read the ability override table: {exc}")

        try:
            entries = nxd_data.read_override_entry_table(sqlite_path)
            self.state.entry_records = entries
            notes.append(f"{len(entries)} encounter rows")
        except Exception as exc:                              # noqa: BLE001
            notes.append(f"Couldn't read the encounter table: {exc}")

        return notes

    def adopt_existing_folder(self, _checked=False, path: str | None = None) -> None:
        """
        For someone who already unpacked - with this tool before, or with
        FF16Tools directly. Same end result as unpacking, minus the unpack.
        """
        if path is None:
            path = QFileDialog.getExistingDirectory(
                self, "Select your already-unpacked game folder")
        if not path:
            return

        self.adopt_button.setEnabled(False)
        self._show_progress()
        self._say("Looking through that folder...", "muted")

        worker = AdoptFolderWorker(Path(path))
        self._thread = run_in_thread(
            worker, on_finished=self._adopted, on_failed=self._adopt_failed,
            on_log=self._log)

    def _adopted(self, result: dict) -> None:
        self.progress.setVisible(False)
        self.adopt_button.setEnabled(True)
        self.state.nxd_unpack_dir = result["folder"]
        if result["texture_tree"] is not None:
            self.state.texture_tree = result["texture_tree"]
        if result["sound_tree"] is not None:
            self.state.sound_tree = result["sound_tree"]
        self._refresh_readiness()
        self.setup_changed.emit()

        # Straight on to the conversion.
        #
        # Unpacking and converting are one job from where the person is
        # standing: neither is any use on its own, and until the conversion
        # has run every data tab is still empty.
        #
        # After adopting a folder too, not just after an unpack - but only
        # when there is no database loaded. Somebody pointing at a folder
        # they already have usually has one, and the previous-session pickup
        # will already have found it; if it did not, converting is the only
        # thing they could have wanted next. This is what lets the Convert
        # button go: every route to an unpacked folder now reaches a
        # database on its own.
        already_have_one = getattr(self.state, "nxd_sqlite_path", None) is not None
        was_unpack = self._convert_after_adopt
        self._convert_after_adopt = False
        if result["nxd_dir"] is not None and not already_have_one:
            self._say(
                ("Unpacked. Converting the game data now - this takes a "
                 "minute.") if was_unpack else
                ("That folder has game data but no database yet. Converting "
                 "it now - this takes a minute."), "muted")
            self.start_conversion()

    def _adopt_failed(self, message: str) -> None:
        self.progress.setVisible(False)
        self.adopt_button.setEnabled(True)
        self._say(f"Couldn't use that folder: {message}", "danger")

    # -- readiness -------------------------------------------------------------------

    def reuse_previous_session(self) -> list:
        """
        Picks up the unpacked folder and database this tool made last time.

        Re-unpacking the game on every launch to get back to where you
        already were is the most annoying thing this page could ask for, and
        everything needed to avoid it is sitting on disk. The Tkinter page
        has done this since the unpack existed; this one did not, which is
        why Abilities, Poaching, Encounters, Textures and Sounds all came up
        empty after a restart even though the game was unpacked.

        Returns what it found, for the log.
        """
        found = []
        local = paths.local_data_dir()

        unpacked = local / "UnpackedGame"
        try:
            has_content = unpacked.is_dir() and any(unpacked.iterdir())
        except OSError:
            has_content = False
        if getattr(self.state, "nxd_unpack_dir", None) is None and has_content:
            self.state.nxd_unpack_dir = unpacked
            self.folder_field.setText(str(unpacked))
            # The trees are what Textures and Sounds read; without them
            # those two tabs stay empty even with the folder set.
            try:
                self.state.texture_tree = td.scan_texture_tree(unpacked)
            except Exception:                                 # noqa: BLE001
                pass
            try:
                self.state.sound_tree = sd.scan_sound_tree(unpacked)
            except Exception:                                 # noqa: BLE001
                pass
            found.append(f"Reusing the unpacked game folder from a previous "
                         f"session: {unpacked}")

        database = local / "fft_data.sqlite"
        if (getattr(self.state, "nxd_sqlite_path", None) is None
                and database.is_file()
                and self.looks_like_game_database(database)):
            try:
                notes = self.load_database_tables(database)
            except Exception:                                 # noqa: BLE001
                notes = []
            if notes:
                self.state.nxd_sqlite_path = database
                found.append(f"Reusing the database from a previous session: "
                             f"{database}")
        return found

    def _refresh_readiness(self) -> None:
        """
        Says which tabs are usable, and does not overstate it.

        A tab with no data behind it is named as unavailable rather than
        left to look broken when someone clicks it.
        """
        ready, missing = [], []
        (ready if self.state.mod_sqlite_path or self.state.nxd_unpack_dir
         else missing).append("the data tabs")
        (ready if getattr(self.state, "texture_tree", None) is not None
         else missing).append("Textures")
        (ready if getattr(self.state, "sound_tree", None) is not None
         else missing).append("Sounds")

        parts = []
        if ready:
            parts.append("Ready to edit: " + ", ".join(ready) + ".")
        if missing:
            parts.append("Not set up yet: " + ", ".join(missing) + ".")
        self._say(" ".join(parts) or "Nothing set up yet.", "muted")

    def _say(self, text: str, role: str) -> None:
        self.status.setText(text)
        self.status.setProperty("role", role)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    def _log(self, line: str) -> None:
        self.log.appendPlainText(line)
