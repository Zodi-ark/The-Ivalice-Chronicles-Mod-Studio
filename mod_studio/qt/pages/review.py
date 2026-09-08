"""
Game Updates / Review changes.

When the game updates, a mod built against the old version has to be
re-expressed on top of the new one. This is where somebody looks at what
that means, field by field, and says which side wins.

The engine does the thinking: `migration.build_plan(base, mod, new)`
produces a `FieldChange` per field with an outcome and a starting
resolution. This page shows them and lets the resolution be changed. It
does not decide what a conflict is - a second opinion living in the
interface would drift from the one that actually gets applied.

Building a plan needs three databases and the mod's own, so the page says
which are missing rather than offering a button that cannot work.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSortFilterProxyModel, Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QProgressBar, QRadioButton, QSizePolicy, QTableWidget,
    QTableWidgetItem,
    QPushButton, QScrollArea, QTableView, QVBoxLayout, QWidget,
)

from ... import nxd_data
from ... import migration
from ... import paths
from ... import version_archive
from ..models.migration_plan import MigrationModel

# The change table stops growing here and scrolls internally.
#
# A mod can carry hundreds of conflicting fields, and a table 264 rows tall
# would put the whole-file section thousands of pixels below the fold with
# no way to tell it was there. The whole page scrolls, so a cap costs one
# scroll bar in the rare case and saves the page in the common one.
REVIEW_TABLE_MAX = 640
from ..widgets.actions import set_empty_state
from ..widgets.field_rows import CollapsibleSection
from ..workers import Worker, run_in_thread


def _key_text(key) -> str:
    """
    A row key, readable.

    Keys arrive as tuples because a table can be keyed on more than one
    column, and `str()` on a one-element tuple gives `(2801,)` - which reads
    as a typo rather than a row number. Multi-part keys keep both parts,
    joined, because both are needed to find the row.
    """
    if isinstance(key, tuple):
        return "/".join(str(part) for part in key)
    return str(key)


def _shown(value) -> str:
    """`(not set)` rather than an empty cell, which reads as a bug."""
    text = "" if value is None else str(value)
    return text if text else "(not set)"


class PlanWorker(Worker):
    """
    Builds the plan. Minutes of work on a large update, so not on the GUI
    thread.

    Also assesses the whole `.nxd` files the mod ships that have no editor
    tab. That has to happen here rather than afterwards: it reads every one
    of them off disk, and the baseline is what separates a value the author
    chose from one the mod simply has not caught up with.
    """

    def __init__(self, base: Path, mod: Path, new: Path,
                 mod_nxd_dir=None, game_nxd_dir=None):
        super().__init__()
        self.base, self.mod, self.new = base, mod, new
        self.mod_nxd_dir = mod_nxd_dir
        self.game_nxd_dir = game_nxd_dir

    def run(self):
        self.log.emit("Working out what your mod changed, and what the update "
                      "changed...")
        plan = migration.build_plan(self.base, self.mod, self.new)
        if self.mod_nxd_dir is not None:
            try:
                plan.unmodelled = migration.assess_unmodelled(
                    Path(self.mod_nxd_dir), self.mod, self.new,
                    baseline_sqlite=self.base,
                    game_nxd_dir=self.game_nxd_dir)
            except Exception as exc:                          # noqa: BLE001
                # A file that cannot be read must not lose the whole plan -
                # the modelled changes above are the bulk of the work.
                self.log.emit(f"Couldn't assess the whole-file tables: {exc}")
        self.log.emit(f"{len(plan.changes)} of your changes need re-applying.")
        return plan


class ReviewPage(QWidget):
    plan_ready = Signal(object)
    applied = Signal()

    def __init__(self, state, versions: dict | None = None, parent=None):
        super().__init__(parent)
        self.state = state
        self._versions = dict(versions or {})
        self._thread = None

        self.model = MigrationModel()
        self.proxy = QSortFilterProxyModel()
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterRole(Qt.UserRole)
        self.proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)

        # The whole page scrolls.
        #
        # It did not need to while it was a heading, a toolbar and one
        # table. With a block per whole-file table underneath - nine of them
        # for a mod that ships all seven UI languages - the content runs to
        # well over a thousand pixels, and without somewhere to scroll every
        # block past the first is simply unreachable.
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        page_layout.addWidget(self.scroll)

        inner = QWidget()
        self.scroll.setWidget(inner)
        outer = QVBoxLayout(inner)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(10)

        heading = QLabel("Game Updates")
        heading.setProperty("role", "heading")
        outer.addWidget(heading)

        blurb = QLabel(
            "Your mod's changes, re-applied to the game files you have now. "
            "Review them on the normal tabs, then use Export Mod to write "
            "the updated mod out.")
        blurb.setProperty("role", "muted")
        blurb.setWordWrap(True)
        outer.addWidget(blurb)

        # No version pickers.
        #
        # This page used to ask for two: "Mod was built against" and "Now
        # on". That was the original design and it was refined out of the
        # Tkinter interface - it asks the author to know something the tool
        # can work out, and gets the answer wrong the moment they guess.
        #
        # What it needs is the mod (opened on General Setup) and the game
        # files you have now. The baseline - the version the mod was built
        # against - is IDENTIFIED, by `migration.detect_mod_game_version`
        # reading the mod's own stamp and `identify_baseline` scoring it
        # against the saved archive. Picking two versions by hand is what
        # Compare Versions is for, and that is the only feature that needs
        # more than one.
        controls = QHBoxLayout()
        self.build_button = QPushButton("Check This Mod Against Your Game Files")
        self.build_button.setMinimumWidth(
            self.build_button.sizeHint().width() + 8)
        self.build_button.clicked.connect(self.build_plan)
        controls.addWidget(self.build_button)

        self.apply_button = QPushButton("Load Result Into Edit Game Data")
        self.apply_button.setMinimumWidth(
            self.apply_button.sizeHint().width() + 8)
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self.apply_plan)
        controls.addWidget(self.apply_button)

        self.show_clean = QCheckBox("Also list changes that carry over cleanly")
        self.show_clean.toggled.connect(self._render_plan)
        controls.addWidget(self.show_clean)
        controls.addStretch(1)
        outer.addLayout(controls)

        self.baseline_note = QLabel("")
        self.baseline_note.setProperty("role", "muted")
        self.baseline_note.setWordWrap(True)
        outer.addWidget(self.baseline_note)

        self.status = QLabel(self._initial_status())
        self.status.setProperty("role", "muted")
        self.status.setWordWrap(True)
        outer.addWidget(self.status)

        self.busy = QProgressBar()
        self.busy.setRange(0, 0)
        self.busy.setVisible(False)
        self.busy.setMaximumHeight(6)
        self.busy.setTextVisible(False)
        outer.addWidget(self.busy)

        controls = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter by table, field or value")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._on_filter)
        controls.addWidget(self.search, 1)

        self.keep_button = QPushButton("Keep mine")
        self.keep_button.setMinimumWidth(self.keep_button.sizeHint().width() + 8)
        self.keep_button.clicked.connect(self.keep_selected)
        controls.addWidget(self.keep_button)

        self.take_button = QPushButton("Take the update's")
        self.take_button.setMinimumWidth(self.take_button.sizeHint().width() + 8)
        self.take_button.clicked.connect(self.take_selected)
        controls.addWidget(self.take_button)
        # In a container, so the filter and the two buttons disappear with
        # the table they act on. Before the mod has been checked there is
        # nothing to filter and nothing to keep or take.
        self.review_controls = QWidget()
        self.review_controls.setLayout(controls)
        outer.addWidget(self.review_controls)

        bulk = QHBoxLayout()
        self.keep_all_button = QPushButton("Keep all of mine")
        self.keep_all_button.setMinimumWidth(
            self.keep_all_button.sizeHint().width() + 8)
        self.keep_all_button.clicked.connect(lambda: self._resolve_all(
            migration.KEEP_MOD))
        bulk.addWidget(self.keep_all_button)

        self.take_all_button = QPushButton("Take all from the update")
        self.take_all_button.setMinimumWidth(
            self.take_all_button.sizeHint().width() + 8)
        self.take_all_button.clicked.connect(lambda: self._resolve_all(
            migration.TAKE_UPDATE))
        bulk.addWidget(self.take_all_button)
        bulk.addStretch(1)
        self.counts = QLabel("")
        self.counts.setProperty("role", "muted")
        bulk.addWidget(self.counts)
        self.bulk_controls = QWidget()
        self.bulk_controls.setLayout(bulk)
        outer.addWidget(self.bulk_controls)

        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(22)
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.ElideRight)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        # "Why" is the ONLY stretching column, and everything else is sized.
        #
        # With three stretching columns the reason got about 130px and every
        # row read "The update does..." - identical, and useless. The reason
        # is the entire point of a review: without it somebody is accepting
        # 264 changes on faith, which is what this page exists to avoid.
        # Values are short (ids, names); reasons are sentences.
        # Sized so the reason still gets room at the 1100 minimum. The
        # first attempt totalled 900px of fixed columns and left the reason
        # 136 - narrower than the value columns beside it, which is the
        # wrong way round for the thing somebody is meant to read.
        # "What happens" needs 125 for its own header - at 105 it rendered
        # as "/hat happen", the seventh clipped control in this project's
        # history and the second the clipping check caught before a
        # screenshot did.
        for column, width in {0: 90, 1: 120, 2: 60, 3: 125,
                              4: 105, 5: 105, 6: 125}.items():
            header.setSectionResizeMode(column, QHeaderView.Interactive)
            self.table.setColumnWidth(column, width)
        header.setSectionResizeMode(7, QHeaderView.Stretch)
        # Sized to its rows, NOT given the leftover height.
        #
        # It had `stretch 1` inside a scroll area set to resize its widget,
        # so an empty table expanded to fill the whole viewport: before the
        # mod had been checked the page was a filter box, four buttons and a
        # thousand pixels of empty grid. After a check that found no
        # per-field changes - which is the ordinary case for a mod that
        # ships whole files - the same empty grid sat between the summary
        # line and the list of files, so the two states looked like
        # different pages.
        #
        # The page scrolls, so the table can be as tall as its content up to
        # a cap and everything below it follows on directly.
        outer.addWidget(self.table)

        # Shown in the table's place. Says which of the two reasons there is
        # nothing to review, because "check your mod first" and "your mod
        # has no conflicts" need very different things done about them.
        self.no_changes_note = QLabel("")
        self.no_changes_note.setProperty("role", "muted")
        self.no_changes_note.setWordWrap(True)
        self.no_changes_note.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        outer.addWidget(self.no_changes_note)

        # -- whole files with no editor tab -----------------------------------
        #
        # A `.nxd` the mod ships replaces the game's copy wholesale, so
        # shipping one freezes that whole table at the version it was built
        # against - `ui.en.nxd` is why a mod can revert the game's own
        # version display. `assess_unmodelled` works out what is in each of
        # them; the Qt page computed all of it and drew none of it, so the
        # only files that CANNOT be reviewed on a normal tab were also the
        # only ones with no review here.
        self.unmodelled_heading = QLabel("")
        self.unmodelled_heading.setStyleSheet("font-weight: 600;")
        self.unmodelled_heading.setVisible(False)
        outer.addWidget(self.unmodelled_heading)

        self.unmodelled_holder = QWidget()
        self.unmodelled_column = QVBoxLayout(self.unmodelled_holder)
        self.unmodelled_column.setContentsMargins(0, 0, 0, 0)
        self.unmodelled_column.setSpacing(6)
        self.unmodelled_holder.setVisible(False)
        outer.addWidget(self.unmodelled_holder)

        # Packs everything to the top.
        #
        # The change table used to be the only stretching item, so it soaked
        # up any spare height. With it sized to its own rows there is
        # nothing to absorb the difference when the content is shorter than
        # the viewport, and a QVBoxLayout spreads that surplus between its
        # items instead - which left the heading floating a long way above
        # the blurb on a tall window. A stretch at the end takes it all.
        outer.addStretch(1)

        # {filename: resolution} and {filename: {(key, column)}} - the
        # author's decisions, which `apply_plan` reads back off the tables.
        # Set before the first `_sync_review_block`, which reads it to tell
        # "not checked yet" from "checked, nothing conflicts".
        self._plan = None
        self._file_choices = {}
        self._file_selection = {}
        self._merge_buttons = {}
        self._pickers = {}
        self._change_views = {}

        self._update_counts()

    def _sync_review_block(self) -> None:
        """
        Shows the change table only when there are changes in it.

        Also sizes it. A `QTableView` has no useful height of its own, so
        without this it is either whatever the layout spares it or one row
        tall - the first is what produced a viewport-sized empty grid, the
        second is what a table with no stretch does by default.
        """
        rows = self.proxy.rowCount()
        has_rows = rows > 0
        set_empty_state(
            self.no_changes_note, has_rows,
            self.table, self.review_controls, self.bulk_controls)
        if has_rows:
            header = self.table.horizontalHeader().height()
            wanted = header + rows * 22 + 4
            self.table.setMinimumHeight(min(wanted, REVIEW_TABLE_MAX))
            self.table.setMaximumHeight(min(wanted, REVIEW_TABLE_MAX))
            return
        # Only the "you have not checked yet" case says anything.
        #
        # There was a second message here for "checked, nothing conflicts",
        # which Zodi cut: the summary line directly above already gives the
        # counts, and a mod whose whole effect is nine files is the ordinary
        # case rather than something needing explaining. Two sentences
        # restating the line above them is clutter, and Tkinter had neither.
        # Nothing here either.
        #
        # "Nothing to review yet." restated an empty page, and the sentence
        # under it repeated the heading, the blurb and the button all at
        # once. What remains for the "you have not opened a mod" case is
        # the orange status line, which appears when you actually press the
        # button without one - that one is worth keeping, because it is the
        # answer to something the reader just tried to do.
        self.no_changes_note.setText("")
        self.no_changes_note.setVisible(False)

    # -- status ------------------------------------------------------------------

    def _initial_status(self) -> str:
        """
        Names what is missing, in the order it has to be fixed.

        Two things, not three: the mod, and the game files. The saved
        archive is needed too but is not something anyone has to go and do -
        unpacking produces it - so it is described that way rather than
        listed as a chore.
        """
        if getattr(self.state, "mod_sqlite_path", None) is None:
            return ("Open the mod you want to update on General Setup. This "
                    "page compares its game data against the files you have "
                    "unpacked.")
        if getattr(self.state, "nxd_sqlite_path", None) is None:
            return ("Unpack your game files on General Setup first - that is "
                    "what the mod gets compared against.")
        # Nothing. The button is right there and says what it does, so a
        # line telling the reader to press it is the interface narrating
        # itself. The two returns above stay: they name something that is
        # actually MISSING and has to be fixed elsewhere, which is a
        # different kind of sentence.
        return ""

    def set_versions(self, versions: dict) -> None:
        """
        Kept for the shell, which hands both Game Updates pages the archive.

        This page no longer chooses from it - the baseline is identified -
        but Compare Versions still does, and the shell calls both the same
        way.
        """
        self._versions = dict(versions)
        self.status.setText(self._initial_status())

    # -- building -------------------------------------------------------------------

    def identify_baseline(self):
        """
        Works out which saved version this mod was built against.

        The mod's own stamp first (`detect_mod_game_version` reads its
        ModConfig and its database), then scored against the archive. The
        stamp is a hint rather than an answer: a mod can be re-zipped, and
        an author can be wrong about what they built on.
        """
        mod_sqlite = getattr(self.state, "mod_sqlite_path", None)
        if mod_sqlite is None:
            return None
        hint, source = migration.detect_mod_game_version(
            getattr(self.state, "loaded_mod_config", None), Path(mod_sqlite))
        # `(version, sqlite path)` pairs, as `identify_baseline` expects.
        #
        # An archived version is a zip of .nxd files, not a database, so
        # each one has to be opened - `open_archived_database` extracts and
        # converts it into a scratch folder, and returns None for any it
        # cannot. The converter fingerprint is passed so a version converted
        # by a different FF16Tools build is redone rather than trusted.
        converter = version_archive.converter_fingerprint(
            getattr(self.state, "ff16tools_cli_path", None))
        scratch = paths.local_data_dir() / "version_scratch"
        candidates = []
        for entry in version_archive.list_archived():
            opened = version_archive.open_archived_database(
                entry, scratch / Path(entry.directory).name, converter)
            if opened is not None:
                candidates.append((entry.version, opened))
        if not candidates:
            return None
        return migration.identify_baseline(
            Path(mod_sqlite), candidates, hint or "", source if hint else "")

    def build_plan(self) -> None:
        mod_sqlite = getattr(self.state, "mod_sqlite_path", None)
        current = getattr(self.state, "nxd_sqlite_path", None)
        if mod_sqlite is None:
            self._say("Open the mod you want to update on General Setup first.",
                      "attention")
            return
        if current is None:
            self._say("Unpack your game files on General Setup first - that is "
                      "what the mod gets compared against.", "attention")
            return

        baseline = self.identify_baseline()
        if baseline is None or not getattr(baseline, "chosen", None):
            # Said as the thing to do, not as a failure. Unpacking once
            # produces the archive and this works from then on.
            self._say(
                "Mod Studio saves a copy of your game data each time you "
                "unpack, and needs one to tell this mod's deliberate changes "
                "apart from values it simply hasn't caught up with. Unpack "
                "your game files once and this will work from then on.",
                "attention")
            return

        self.build_button.setEnabled(False)
        self.apply_button.setEnabled(False)
        self.busy.setVisible(True)
        self._describe_baseline(baseline)
        self._say("Comparing...", "muted")

        unpacked = getattr(self.state, "nxd_unpack_dir", None)
        worker = PlanWorker(
            Path(baseline.chosen.sqlite_path), Path(mod_sqlite), Path(current),
            mod_nxd_dir=getattr(self.state, "mod_nxd_dir", None),
            game_nxd_dir=(Path(unpacked) / "nxd") if unpacked else None)
        self._thread = run_in_thread(
            worker, on_finished=self._plan_built, on_failed=self._plan_failed)

    def _describe_baseline(self, baseline) -> None:
        """
        Says which version was picked, and admits when it was a guess.

        A baseline chosen against the mod's own stamp is a different level
        of confidence from one inferred by scoring, and the difference
        decides how much to trust everything below it.
        """
        chosen = baseline.chosen
        if getattr(baseline, "hint_agreed", False) and baseline.hint_version:
            self.baseline_note.setText(
                f"Built against {chosen.version}, which matches what the mod "
                f"records ({baseline.hint_source}).")
        elif baseline.hint_version:
            self.baseline_note.setText(
                f"The mod records {baseline.hint_version}, but its data "
                f"matches the saved {chosen.version} more closely - using "
                f"that.")
        else:
            self.baseline_note.setText(
                f"The mod doesn't record which version it was built on. Its "
                f"data matches the saved {chosen.version} most closely.")

    def _build_unmodelled(self, plan) -> None:
        """
        One block per whole `.nxd` the mod ships that has no editor tab.

        Three choices and a per-change picker, matching the Tkinter page.
        The picker is what turns "merge my changes" from an
        accept-everything button into an actual review: a mod can perfectly
        well contain edits its author no longer wants, especially after an
        update has rewritten the thing they were working around.
        """
        while self.unmodelled_column.count():
            item = self.unmodelled_column.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        # NOT `self._plan = None` here - this method redraws the per-file
        # blocks for the plan that has just been built, and clearing the
        # plan it is drawing would leave `_on_change_ticked` with nothing to
        # look the file up in, so ticking a box updated the selection and
        # neither of the two labels quoting its count.
        self._file_choices = {}
        self._file_selection = {}
        self._change_views = {}

        tables = list(getattr(plan, "unmodelled", None) or [])
        self.unmodelled_heading.setText(
            f"Game data files with no editing tab ({len(tables)})")
        self.unmodelled_heading.setVisible(bool(tables))
        self.unmodelled_holder.setVisible(bool(tables))
        if not tables:
            return

        merging = sum(1 for t in tables if t.rebasable)
        text = ("Your mod ships these whole files. Because a file like this "
                "replaces the game's copy completely, keeping one whole "
                "freezes that part of the game at the version your mod was "
                "built on.")
        if merging:
            # The count and the instruction both matter: "most can be
            # merged" does not tell you whether YOUR file is one of them,
            # and nothing else on the page says the picker is behind the
            # collapsed section.
            text += (f"  {merging} of them can be merged instead - the game's "
                     f"new file with your changes put back on top - so you "
                     f"keep both. Open one to pick which of your changes "
                     f"carry over.")
        note = QLabel(text)
        note.setProperty("role", "muted")
        note.setWordWrap(True)
        self.unmodelled_column.addWidget(note)

        for table in tables:
            self.unmodelled_column.addWidget(self._file_block(table))

    def _file_block(self, table) -> QWidget:
        block = QWidget()
        column = QVBoxLayout(block)
        column.setContentsMargins(0, 4, 0, 4)
        column.setSpacing(3)

        headline = QLabel(f"{table.filename} \u2014 {self._describe(table)}")
        headline.setStyleSheet("font-weight: 600;")
        headline.setWordWrap(True)
        column.addWidget(headline)

        # The engine recommends; the author decides. Its recommendation is
        # not a guess - a file with nothing of the author's in it costs this
        # update and every future one, and one that cannot be read at all is
        # kept, because dropping something unexamined is guessing with
        # somebody's work.
        self._file_choices[table.filename] = table.recommendation
        self._file_selection[table.filename] = table.default_selection()

        choices = QHBoxLayout()
        group = QButtonGroup(block)
        options = []
        if table.rebasable:
            options.append((
                migration.REBASE,
                f"Take the game's new file and re-apply my "
                f"{len(self._file_selection[table.filename])} change(s)"))
        options.append((migration.KEEP_MOD, "Keep my whole copy"))
        options.append((migration.DROP, "Drop mine, use the game's"))
        for resolution, label in options:
            button = QRadioButton(label)
            button.setChecked(resolution == table.recommendation)
            button.toggled.connect(
                lambda on, f=table.filename, r=resolution:
                self._set_file_choice(f, r) if on else None)
            group.addButton(button)
            choices.addWidget(button)
            if resolution == migration.REBASE:
                self._merge_buttons[table.filename] = button
        choices.addStretch(1)
        column.addLayout(choices)

        if not table.rebasable and table.readable:
            why = QLabel(
                "The game doesn't ship a file by this name, so there's no "
                "newer copy to merge yours onto - it can only be passed "
                "through whole or left out.")
            why.setProperty("role", "muted")
            why.setWordWrap(True)
            column.addWidget(why)

        if table.own_changes:
            picker = self._change_picker(table)
            section = CollapsibleSection(
                "Choose which of your changes to carry over", picker,
                expanded=False)
            self._pickers[table.filename] = section
            column.addWidget(section)
            self._refresh_file_labels(table)
        return block

    @staticmethod
    def _describe(table) -> str:
        """What is actually in this file, in the order that matters."""
        parts = []
        if table.additions:
            parts.append(f"{table.additions} value(s) your mod sets")
        if table.losses:
            parts.append(f"{table.losses} value(s) your mod clears")
        if table.stale:
            parts.append(f"{table.stale} value(s) the update changed that "
                         f"your copy predates")
        if table.rows_missing:
            parts.append(f"{table.rows_missing} row(s) missing")
        if not table.readable:
            return "couldn't be read, so it will be passed through as-is"
        return "; ".join(parts) or "nothing different from the game's own"

    def _change_picker(self, table) -> QWidget:
        """
        Every individual change in one file, each one tickable.

        A table rather than a stack of checkboxes: `uibuttonguide.nxd`
        carries hundreds of changes, and that many widgets is slow to build
        and impossible to scan.

        A change can start unticked with the reason shown beside it - the
        game's own version marker looks like the author's work and is not.
        It is listed rather than hidden, because a row is never hidden from
        a review.
        """
        panel = QWidget()
        panel_column = QVBoxLayout(panel)
        panel_column.setContentsMargins(0, 0, 0, 0)
        panel_column.setSpacing(4)

        controls = QHBoxLayout()
        for label, wanted in (("Select all", True), ("Select none", False)):
            button = QPushButton(label)
            button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            button.clicked.connect(
                lambda _c=False, t=table, w=wanted: self._set_all_changes(t, w))
            controls.addWidget(button)
        controls.addStretch(1)
        panel_column.addLayout(controls)

        # What a tick does, and - when something starts off - why.
        #
        # A row that begins unticked with no explanation looks like a bug in
        # the tool rather than a deliberate recommendation, and the one that
        # always starts off is the game's own version marker, which is
        # exactly the kind of thing an author might genuinely want to keep.
        hint_text = "Click a row's box to include or exclude it."
        flagged_count = len(table.excluded_by_default)
        if flagged_count:
            hint_text += (
                f"  {flagged_count} row(s) start switched off, with the "
                f"reason in the last column. Carrying the game's version "
                f"number over would make it report the version your mod was "
                f"built for rather than the one that's installed - but it's "
                f"your mod, so turn it on if you mean to.")
        hint = QLabel(hint_text)
        hint.setProperty("role", "muted")
        hint.setWordWrap(True)
        panel_column.addWidget(hint)

        view = QTableWidget()
        rows = [(key, column) for key, fields in sorted(
            table.own_changes.items(), key=lambda kv: str(kv[0]))
            for column in sorted(fields)]
        view.setRowCount(len(rows))
        view.setColumnCount(5)
        view.setHorizontalHeaderLabels(
            ["", "Row", "Field", "Your value", "The game's value"])
        has_reasons = bool(table.excluded_by_default)
        if has_reasons:
            view.setColumnCount(6)
            view.setHorizontalHeaderLabels(
                ["", "Row", "Field", "Your value", "The game's value",
                 "Why it starts off"])
        view.verticalHeader().setVisible(False)
        view.setEditTriggers(QTableWidget.NoEditTriggers)
        view.setSelectionMode(QTableWidget.NoSelection)
        # Tall enough for ALL of its rows, with no scroll bar of its own.
        #
        # This used to cap at eight rows and scroll inside, which put a
        # scrolling area inside a scrolling page: the wheel over the picker
        # moved the picker, and the wheel two pixels to the left moved the
        # page. Zodi asked for the Tkinter behaviour, where a picker extends
        # fully and the page is the only thing that scrolls.
        #
        # `uibuttonguide.nxd` carries 347 changes, so an opened picker can
        # be seven thousand pixels tall - but these sections start collapsed
        # and only the one you opened is drawn, which is what makes that
        # acceptable. The page scroll bar is then the honest indicator of
        # how much you asked to see.
        view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # Height is set AFTER the rows are in - see the end of this method.
        # It used to be computed here from `len(rows) * 22`, a guess made
        # before a single row existed, so any row Qt drew taller than 22px
        # was simply cut off the bottom with the scroll bar hidden. That is
        # why removing the scroll bar alone did not make the picker extend.

        selected = self._file_selection[table.filename]
        for index, (key, column_name) in enumerate(rows):
            tick = QTableWidgetItem()
            tick.setCheckState(
                Qt.Checked if (key, column_name) in selected else Qt.Unchecked)
            tick.setData(Qt.UserRole, (table.filename, key, column_name))
            view.setItem(index, 0, tick)
            mine = table.own_changes.get(key, {}).get(column_name, "")
            theirs = table.game_values.get(key, {}).get(column_name, "")
            for offset, text in enumerate((_key_text(key), str(column_name),
                                           _shown(mine), _shown(theirs))):
                view.setItem(index, offset + 1, QTableWidgetItem(text))
            reason = table.excluded_by_default.get((key, column_name), "")
            if has_reasons:
                view.setItem(index, 5, QTableWidgetItem(reason))
            if reason:
                # Muted across the row, so a change that starts off reads as
                # switched off rather than as one you happen not to have
                # ticked yet.
                for column in range(view.columnCount()):
                    cell = view.item(index, column)
                    if cell is not None:
                        cell.setForeground(QBrush(QColor("#8a8a8a")))
        view.itemChanged.connect(self._on_change_ticked)
        view.resizeColumnsToContents()

        # Now that the rows exist, measure them.
        #
        # `verticalHeader().length()` is the summed height of every section
        # as Qt actually laid them out, which is the only number that
        # survives a font or style change. Adding the horizontal header and
        # twice the frame gives the height at which nothing is cut off and
        # no scroll bar is needed - which is what Zodi asked for and what
        # the Tkinter picker does.
        view.resizeRowsToContents()
        total = (view.horizontalHeader().height()
                 + view.verticalHeader().length()
                 + 2 * view.frameWidth())
        view.setMinimumHeight(total)
        view.setMaximumHeight(total)
        self._change_views[table.filename] = view
        panel_column.addWidget(view)
        return panel

    def _set_all_changes(self, table, wanted: bool) -> None:
        """
        Ticks or unticks every change in one file.

        Through the table's own items rather than the selection set, so the
        boxes and the set cannot disagree - `itemChanged` does the recording
        either way.
        """
        view = self._change_views.get(table.filename)
        if view is None:
            return
        state = Qt.Checked if wanted else Qt.Unchecked
        for row in range(view.rowCount()):
            item = view.item(row, 0)
            if item is not None:
                item.setCheckState(state)

    def _on_change_ticked(self, item) -> None:
        payload = item.data(Qt.UserRole)
        if not payload:
            return
        filename, key, column_name = payload
        selected = self._file_selection.setdefault(filename, set())
        if item.checkState() == Qt.Checked:
            selected.add((key, column_name))
        else:
            selected.discard((key, column_name))
        for table in getattr(self._plan, "unmodelled", None) or []:
            if table.filename == filename:
                self._refresh_file_labels(table)
                break

    def _refresh_file_labels(self, table) -> None:
        """
        Keeps the merge button and the picker's subtitle honest.

        Both quote a count, and the count changes as boxes are ticked. The
        Tkinter page learned this the hard way: three places each with their
        own static total, so unticking one box left two of them contradicting
        the thing that had just changed.
        """
        chosen = len(self._file_selection.get(table.filename, ()))
        total = table.change_count
        button = self._merge_buttons.get(table.filename)
        if button is not None:
            button.setText(
                f"Take the game's new file and re-apply my {chosen} change(s)")
        section = self._pickers.get(table.filename)
        if section is not None:
            section.header.setText(
                f"Choose which of your changes to carry over    "
                f"{chosen} of {total} selected")

    def _selected_own_changes(self, table) -> dict:
        """
        One file's changes, filtered to what the author ticked.

        Falls back to the table's OWN default rather than to everything, so
        a change that starts switched off - the game's version marker - is
        never carried just because nobody opened the picker.
        """
        selected = self._file_selection.get(table.filename)
        if selected is None:
            selected = table.default_selection()
        result = {}
        for key, fields in table.own_changes.items():
            kept = {column: value for column, value in fields.items()
                    if (key, column) in selected}
            if kept:
                result[key] = kept
        return result

    def _apply_file_choices(self, plan) -> None:
        """
        Turns the per-file decisions into something Export will act on.

        This was the missing half. The blocks recorded what the author chose
        and nothing read it back, so every whole file was carried through
        unchanged however the radio buttons were set - the review was real
        and its outcome was not.

        **Dropped and merged files both stop being carried through whole.** A
        dropped one is simply gone. A merged one is regenerated from the
        game's new table instead, so passing the old file along as well
        would leave two sources writing the same output, and the stale one
        would win by being a whole-file replacement.
        """
        dropped, rebased = [], {}
        for table in getattr(plan, "unmodelled", None) or []:
            choice = self._file_choices.get(table.filename, table.recommendation)
            if choice == migration.DROP:
                dropped.append(table.filename)
            elif choice == migration.REBASE:
                chosen = self._selected_own_changes(table)
                if chosen:
                    rebased[table.table] = chosen
                else:
                    # Merge chosen but nothing ticked: the author has said
                    # they want none of their changes in this file, which is
                    # what dropping it means. Doing that explicitly beats
                    # writing the game's own file back out as if it were the
                    # mod's.
                    dropped.append(table.filename)

        # Anything dropped or merged is removed from the carried-through
        # set, matched on file name because the recovery keys those by the
        # path inside the mod.
        stop_carrying = set(dropped) | {
            t.filename for t in (getattr(plan, "unmodelled", None) or [])
            if self._file_choices.get(t.filename, t.recommendation)
            == migration.REBASE}
        for relative in list(self.state.other_file_replacements):
            if Path(relative).name.lower() in {n.lower() for n in stop_carrying}:
                self.state.other_file_replacements.pop(relative, None)

        # Merged, not assigned.
        #
        # `rebased` covers the tables the MOD ships, because that is what
        # `assess_unmodelled` reads. Since All Game Data exists, the same
        # store can also hold edits a person made this session on a table
        # the opened mod never touched - and replacing the store outright
        # would delete those without a word. Rebased tables win, because a
        # rebase is a deliberate decision about exactly those tables.
        carried = {table: rows for table, rows
                   in (self.state.unmodelled_table_edits or {}).items()
                   if table not in rebased
                   and table not in {t.table for t
                                     in (getattr(plan, "unmodelled", None) or [])}}
        self.state.unmodelled_table_edits = {**carried, **rebased}
        if rebased or dropped:
            merged_rows = sum(len(rows) for rows in rebased.values())
            self._log(f"{len(rebased)} file(s) merged onto the game's new "
                      f"copy ({merged_rows} change(s) carried), "
                      f"{len(dropped)} dropped.")

    def _log(self, message: str) -> None:
        """No log widget on this page; the status line is what there is."""
        self._last_file_note = message

    def _set_file_choice(self, filename: str, resolution: str) -> None:
        self._file_choices[filename] = resolution

    def file_choices(self) -> dict:
        """What the author decided for each whole file."""
        return dict(self._file_choices)

    def _plan_built(self, plan) -> None:
        self.busy.setVisible(False)
        self.build_button.setEnabled(True)
        self._plan = plan
        self._render_plan()
        self._build_unmodelled(plan)
        self.apply_button.setEnabled(True)
        self.plan_ready.emit(plan)

    def _render_plan(self) -> None:
        """Redraws for the current 'also list clean changes' setting."""
        plan = getattr(self, "_plan", None)
        if plan is None:
            return
        self.model.set_plan(plan, show_clean=self.show_clean.isChecked())
        self._update_counts()
        # Orange, not muted, whenever the mod needs a decision - a carry-over
        # count and a list of whole files with no editor tab are things to
        # act on, and Tkinter drew them in the attention colour. Muted grey
        # reads as a footnote.
        needs_attention = bool(getattr(plan, "unmodelled", None)) or bool(
            self.model.counts()["total"])
        self._say(self.model.summary(),
                  "attention" if needs_attention else "muted")

        # The table and its controls only exist while there is something in
        # them. A mod whose entire effect is nine whole files has no field
        # changes at all, and an empty grid with a filter box and two bulk
        # buttons above it reads as a page that failed rather than one with
        # nothing to show - the Tkinter page omits the section entirely.
        has_rows = self.model.rowCount() > 0
        for widget in (self.table, self.search, self.keep_all_button,
                       self.take_all_button, self.keep_button,
                       self.take_button):
            widget.setVisible(has_rows)

    def apply_plan(self) -> None:
        """
        Loads the reviewed result into the editor.

        Deliberately not writing a mod folder from here. Export Mod already
        knows how to do that - icons, ModConfig merging, zipping, the
        Reloaded-II folder - and a second path would have to agree with it
        forever. Handing the merged edits to the editor means the author
        sees them on the normal tabs before anything is written, and the mod
        that was opened is untouched by construction rather than by care.
        """
        plan = getattr(self, "_plan", None)
        if plan is None:
            return
        self.apply_button.setEnabled(False)
        self._say("Loading the result into Edit Game Data...", "muted")
        try:
            recovered = migration.apply_plan(plan)
        except Exception as exc:                              # noqa: BLE001
            self.apply_button.setEnabled(True)
            self._say(f"That couldn't be loaded: {exc}", "danger")
            return

        # Every registered per-language table. Listing them by hand here
        # meant a table could be migrated correctly by the plan and then
        # not written back into the state, so the review reported changes
        # the tabs never received.
        for _key in nxd_data.ALL_NXD_SPECS:
            self.state.set_nxd_edits_for(_key, recovered.edits_for(_key))
        self.state.override_action_edits = recovered.override_action_edits
        self.state.entry_edits = recovered.entry_edits
        self.state.entry_rekeys = dict(recovered.entry_rekeys)
        self.state.entry_dropped = set(recovered.entry_dropped)

        self._apply_file_choices(plan)

        # What this now targets, so the next update starts from a known
        # baseline rather than working it out again.
        if plan.to_version:
            self.state.built_against_game_version = plan.to_version

        kept = sum(1 for change in plan.changes
                   if change.outcome != migration.ORPHANED
                   and change.resolution != migration.DROP)
        detail = f"{kept} change(s) loaded into Edit Game Data"
        note = getattr(self, "_last_file_note", "")
        if note:
            detail += f"; {note[0].lower()}{note[1:]}"
        self._say(f"{detail.rstrip('.')}. Review them on the normal tabs, "
                  f"then use Export Mod.", "ok")
        self.applied.emit()

    def _plan_failed(self, message: str) -> None:
        self.busy.setVisible(False)
        self.build_button.setEnabled(True)
        # Never "nothing to re-apply" for a plan that was never built.
        self._say(f"That couldn't be worked out: {message}", "danger")

    # -- resolving ---------------------------------------------------------------

    def _selected_source_rows(self) -> list:
        return [self.proxy.mapToSource(index).row()
                for index in self.table.selectionModel().selectedRows()]

    def keep_selected(self) -> None:
        self._resolve(self._selected_source_rows(), migration.KEEP_MOD)

    def take_selected(self) -> None:
        self._resolve(self._selected_source_rows(), migration.TAKE_UPDATE)

    def _resolve_all(self, resolution: str) -> None:
        """
        Applies to everything the FILTER is showing, not the whole plan.

        Reaching past what somebody can see is how they accept two hundred
        changes while looking at four.
        """
        rows = [self.proxy.mapToSource(self.proxy.index(row, 0)).row()
                for row in range(self.proxy.rowCount())]
        self._resolve(rows, resolution)

    def _resolve(self, rows, resolution: str) -> None:
        if not rows:
            self._say("Nothing selected.", "attention")
            return
        changed = self.model.set_resolution(rows, resolution)
        self._update_counts()
        word = "keeping yours" if resolution == migration.KEEP_MOD \
            else "taking the update's"
        self._say(
            f"{changed} change(s) now {word}." if changed
            else f"Those were already {word}.", "muted")

    def _update_counts(self) -> None:
        # Every path that changes the row count comes through here - the
        # filter, a resolution, a rebuild - so this is the one place the
        # review block has to be re-synced.
        self._sync_review_block()
        counts = self.model.counts()
        shown = self.proxy.rowCount()
        if not counts["total"]:
            self.counts.setText("")
            return
        suffix = "" if shown == counts["total"] else f" ({shown:,} shown)"
        self.counts.setText(
            f"{counts['keep']:,} keeping yours, "
            f"{counts['update']:,} taking the update's{suffix}")

    # -- filtering ------------------------------------------------------------------

    def _on_filter(self, text: str) -> None:
        self.proxy.setFilterFixedString(text)
        self._update_counts()

    def _say(self, text: str, role: str) -> None:
        self.status.setText(text)
        self.status.setProperty("role", role)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
