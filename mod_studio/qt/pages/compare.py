"""
Game Updates - the Compare Versions tab.

The vertical slice for the Qt rewrite. Chosen because it is the page Tkinter
actively breaks rather than merely renders awkwardly, and because it
exercises most of the hard problems at once: a large virtualised grid, a
background job measured in seconds, live filtering, and three of the rules
about not overclaiming.

Wired to the real engine. `migration.compare_databases` is called
unmodified; nothing here reimplements what a difference is.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSortFilterProxyModel, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QProgressBar, QPushButton, QScrollArea, QTableView,
    QVBoxLayout, QWidget,
)

from .. import theme
from ..models.comparison import ADDED, CHANGED, REMOVED, ComparisonModel
from ..workers import CompareWorker, run_in_thread


# Column -> pixel width for the columns that identify a row. Module level
# so a test can assert they are wide enough for the real data rather than
# re-deriving numbers that would then drift apart.
DEFAULT_WIDTHS = {0: 200, 1: 95, 2: 180, 5: 90}


class RowTintProxy(QSortFilterProxyModel):
    """
    Filters on the whole row, and tints by change kind.

    Filtering against a single column would mean the user has to know which
    column holds the thing they half-remember. `Qt.UserRole` on the source
    model returns the whole row joined, so typing "Ability" finds it in the
    table name, the field name or the value.
    """

    def __init__(self, dark: bool):
        super().__init__()
        self.setFilterRole(Qt.UserRole)
        self.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self._colours = {}
        self.set_dark(dark)

    def set_dark(self, dark: bool) -> None:
        c = theme.palette(dark)
        self._colours = {
            ADDED: QColor(c["added"]),
            REMOVED: QColor(c["removed"]),
            CHANGED: QColor(c["changed"]),
        }
        self.invalidate()

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.BackgroundRole:
            kind = super().data(index, Qt.UserRole + 1)
            return self._colours.get(kind)
        return super().data(index, role)


class SavedVersionsDialog(QDialog):
    """
    Manage the archived game versions: see them, delete them, add one.

    **Why deleting is offered here rather than only in General Setup.**
    General Setup has an automatic prune - "remove what nothing needs,
    keeping the most recent five" - which is housekeeping and deliberately
    cannot be aimed. This is the other half: a person who knows they will
    never look at v1.4.0 again should be able to say so. Compare Versions
    is where the list of versions is already a thing on screen, so it is
    where a person goes looking for it.

    **The rule that has to survive.** A version some mod was built against
    must not be deletable, or the next Review Changes run on that mod loses
    its baseline and silently substitutes another - which is worth exactly
    the size of the patch in between. `version_archive.versions_in_use` is
    what knows this, and it is asked here rather than re-derived.

    The row is DISABLED with the reason written next to it rather than
    accepting the tick and refusing later. A delete that refuses after the
    fact teaches people the button is unreliable; a row that explains
    itself teaches them how the archive works.
    """

    def __init__(self, state=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Saved game versions")
        self.setMinimumWidth(560)
        self._state = state
        self._boxes = {}          # version -> (QCheckBox, ArchivedVersion)
        self._changed = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 18)
        outer.setSpacing(10)

        blurb = QLabel(
            "Mod Studio saves a copy of your game data each time you unpack. "
            "Compare Versions uses these to show what a patch changed, and "
            "Review Changes uses them to tell a mod's own edits apart from "
            "the game's.")
        blurb.setWordWrap(True)
        blurb.setProperty("role", "muted")
        outer.addWidget(blurb)

        self.list_area = QScrollArea()
        self.list_area.setWidgetResizable(True)
        self.list_area.setFrameShape(QScrollArea.NoFrame)
        holder = QWidget()
        self.list_column = QVBoxLayout(holder)
        self.list_column.setContentsMargins(0, 0, 0, 0)
        self.list_column.setSpacing(6)
        self.list_area.setWidget(holder)
        outer.addWidget(self.list_area, 1)

        self.result = QLabel("")
        self.result.setWordWrap(True)
        self.result.setProperty("role", "muted")
        outer.addWidget(self.result)

        actions = QHBoxLayout()
        self.archive_button = QPushButton("Save the game data I already unpacked")
        self.archive_button.clicked.connect(self.archive_current)
        actions.addWidget(self.archive_button)
        actions.addStretch(1)
        self.delete_button = QPushButton("Delete ticked")
        self.delete_button.clicked.connect(self.delete_ticked)
        self.delete_button.setEnabled(False)
        actions.addWidget(self.delete_button)
        outer.addLayout(actions)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.accept)
        outer.addWidget(buttons)

        self.refresh()

    # -- reading the archive ------------------------------------------------

    def _in_use(self) -> set:
        """
        Versions something still depends on.

        Two sources, both from the engine: the version currently installed,
        and every stamped mod sitting in the Reloaded-II Mods folder. A
        failure to read either is treated as "everything is in use" rather
        than "nothing is" - guessing that an archive is disposable is the
        direction that destroys something irreplaceable.
        """
        from ... import migration, reloaded, version_archive

        try:
            installed = ""
            converted = getattr(self._state, "nxd_sqlite_path", None)
            if converted:
                installed = migration.read_game_version(Path(converted)) or ""
            root = getattr(self._state, "reloaded_ii_path", None)
            mods = (reloaded.effective_mods_folder(Path(root)) if root
                    else reloaded.configured_mods_folder())
            return version_archive.versions_in_use(mods, installed)
        except Exception:                                     # noqa: BLE001
            return None

    def refresh(self) -> None:
        """Redraws the list from the archive on disk."""
        from ... import version_archive

        while self.list_column.count():
            item = self.list_column.takeAt(0)
            widget = item.widget()
            if widget is not None:
                # `takeAt` unmanages a widget but leaves it parented and
                # visible, and `deleteLater` only queues the destruction -
                # so without this the old rows go on painting over the new
                # ones. Same fault All Game Data had.
                widget.setParent(None)
                widget.deleteLater()
        self._boxes = {}

        try:
            entries = version_archive.list_archived()
        except Exception as exc:                              # noqa: BLE001
            self.list_column.addWidget(QLabel(f"Couldn't read the archive: {exc}"))
            return

        in_use = self._in_use()
        unreadable = in_use is None
        if unreadable:
            in_use = set()

        if not entries:
            empty = QLabel(
                "No saved versions yet. Unpacking your game files on General "
                "Setup saves one, or use the button below if you have already "
                "unpacked.")
            empty.setWordWrap(True)
            empty.setProperty("role", "muted")
            self.list_column.addWidget(empty)
            self._sync_delete_button()
            return

        for entry in entries:
            row = QWidget()
            line = QHBoxLayout(row)
            line.setContentsMargins(0, 0, 0, 0)
            box = QCheckBox(entry.version)
            box.toggled.connect(self._sync_delete_button)
            line.addWidget(box)
            line.addSpacing(8)

            detail = f"{entry.file_count} files, {entry.size_mb:.1f} MB"
            if entry.source:
                detail += f" - from {entry.source}"
            note = QLabel(detail)
            note.setProperty("role", "muted")
            line.addWidget(note)
            line.addStretch(1)

            reason = ""
            if unreadable:
                reason = "can't check whether a mod needs it"
            elif version_archive._safe_dirname(entry.version) in in_use:
                reason = "in use - a mod or your install is built on it"
            if reason:
                box.setEnabled(False)
                box.setToolTip(reason)
                held = QLabel(reason)
                held.setProperty("role", "muted")
                line.addWidget(held)
            else:
                self._boxes[entry.version] = (box, entry)
            self.list_column.addWidget(row)

        self.list_column.addStretch(1)
        self._sync_delete_button()

    def _sync_delete_button(self, *_args) -> None:
        self.delete_button.setEnabled(bool(self.ticked()))

    def ticked(self) -> list:
        """The archived versions the user has actually ticked."""
        return [entry for box, entry in self._boxes.values() if box.isChecked()]

    # -- acting -------------------------------------------------------------

    def delete_ticked(self) -> None:
        """
        Deletes exactly what is ticked, through the engine's `apply_prune`.

        A `PrunePlan` is built here rather than a new deletion path being
        written, because `apply_prune` already survives a locked folder
        without abandoning the rest, and one deleter is one place for that
        behaviour to live.
        """
        from ... import version_archive

        chosen = self.ticked()
        if not chosen:
            return
        # Re-checked at the moment of deletion, not trusted from when the
        # list was drawn. A mod can be installed while this dialog is open.
        in_use = self._in_use()
        if in_use is None:
            self.result.setText(
                "Couldn't confirm which versions mods still need, so nothing "
                "was deleted.")
            return
        blocked = [e for e in chosen
                   if version_archive._safe_dirname(e.version) in in_use]
        if blocked:
            self.result.setText(
                "Not deleted - now in use by a mod: "
                + ", ".join(sorted(e.version for e in blocked)) + ".")
            self.refresh()
            return

        plan = version_archive.PrunePlan(remove=list(chosen))
        freed = plan.freed_bytes()
        try:
            removed = version_archive.apply_prune(plan)
        except Exception as exc:                              # noqa: BLE001
            self.result.setText(f"Couldn't delete: {exc}")
            return
        if removed:
            self._changed = True
            self.result.setText(
                f"Deleted {', '.join(sorted(removed))} - {freed / 1_000_000:.1f} MB freed. "
                f"These cannot be recovered; the game builds they came from "
                f"are no longer installed.")
        else:
            self.result.setText("Nothing was deleted.")
        self.refresh()

    def archive_current(self) -> None:
        """
        Saves the game data already sitting in the unpack folder.

        For anyone who unpacked before this existed, or who cleared the
        archive. Everything it needs is what General Setup's automatic
        archive uses, so `archive_unpacked_nxd` is called the same way.

        `clean_unpack` is left None on purpose. General Setup knows whether
        the unpack included installed mods because it just ran it; here that
        is genuinely unknown, and unknown must not be recorded as clean -
        claiming a baseline is mod-free when it might not be makes every
        diff drawn against it wrong with nothing to show for it.
        """
        from ... import migration, version_archive

        unpacked = getattr(self._state, "nxd_unpack_dir", None)
        if not unpacked:
            self.result.setText(
                "No unpacked game files to save. Unpack your game on General "
                "Setup first.")
            return
        nxd_dir = Path(unpacked) / "nxd"
        if not nxd_dir.is_dir():
            self.result.setText(
                f"No nxd folder in {unpacked} - nothing to save. If you "
                f"unpacked with a filter, unpack again with Game data ticked.")
            return

        sqlite_path = getattr(self._state, "nxd_sqlite_path", None)
        self.archive_button.setEnabled(False)
        try:
            version = (migration.read_game_version(Path(sqlite_path))
                       if sqlite_path else None)
            existing = version_archive.find_archived(version) if version else None
            entry = version_archive.archive_unpacked_nxd(
                nxd_dir, version, source=Path(unpacked).name,
                clean_unpack=None,
                sqlite_path=Path(sqlite_path) if sqlite_path else None,
                converter=version_archive.converter_fingerprint(
                    getattr(self._state, "ff16tools_cli_path", None)),
            )
        except Exception as exc:                              # noqa: BLE001
            self.result.setText(f"Couldn't save it: {exc}")
            self.archive_button.setEnabled(True)
            return
        finally:
            self.archive_button.setEnabled(True)

        if entry is None:
            self.result.setText(
                "Couldn't save it - no .nxd files were found in the unpack "
                "folder.")
            return
        if existing is not None:
            # `archive_unpacked_nxd` is a no-op on a version already held and
            # returns the existing manifest, which is right - but reporting
            # that as "saved" would tell somebody their second copy took.
            self.result.setText(
                f"{entry.version} was already saved ({entry.size_mb:.1f} MB). "
                f"Nothing to do.")
            return
        self._changed = True
        self.result.setText(
            f"Saved {entry.version} - {entry.file_count} files, "
            f"{entry.size_mb:.1f} MB.")
        self.refresh()

    @property
    def changed(self) -> bool:
        """Whether the archive on disk is different from when this opened."""
        return self._changed


class ComparePage(QWidget):
    # Emitted when the set of archived versions has changed on disk.
    #
    # The page cannot refill its own boxes from here and be correct: an
    # archived version has to be OPENED to be offered, which is
    # `app.discover_versions`'s job, and Review Changes chooses from the
    # same set. So this says "the archive moved" and lets the window
    # re-discover and hand the result to BOTH pages - otherwise saving a
    # version here would appear in Compare Versions and not in the tab
    # beside it. Rule 7: a new artefact gets walked through what consumes it.
    versions_changed = Signal()

    def __init__(self, versions: dict, dark: bool = False, parent=None,
                 state=None):
        """
        `versions` maps a version label to the path of its converted
        database - whatever the archive can actually open. The page shows
        only what it was given, so a version that cannot be read is absent
        rather than present-and-broken.
        """
        super().__init__(parent)
        self._versions = dict(versions)
        self._thread = None
        self._comparing = ("", "")
        self._dark = dark
        # Optional so every existing caller - including four suites that
        # build the page with a fixed dict of versions - keeps working. The
        # dialog degrades honestly without it: it can still list and delete,
        # and says why it cannot save a new one.
        self._state = state

        self.model = ComparisonModel()
        self.proxy = RowTintProxy(dark)
        self.proxy.setSourceModel(self.model)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(10)

        heading = QLabel("Game Updates")
        heading.setProperty("role", "heading")
        outer.addWidget(heading)

        blurb = QLabel(
            "Everything that changed between two saved game versions - including "
            "parts of the game data this tool has no editing tab for.")
        blurb.setProperty("role", "muted")
        blurb.setWordWrap(True)
        outer.addWidget(blurb)

        # -- pickers --------------------------------------------------------
        picker = QHBoxLayout()
        picker.addWidget(QLabel("From:"))
        self.from_box = QComboBox()
        picker.addWidget(self.from_box)
        picker.addSpacing(12)
        picker.addWidget(QLabel("To:"))
        self.to_box = QComboBox()
        picker.addWidget(self.to_box)
        picker.addSpacing(12)
        self.compare_button = QPushButton("Compare")
        self.compare_button.clicked.connect(self.start_compare)
        picker.addWidget(self.compare_button)
        picker.addSpacing(12)
        # Beside Compare, because the versions this manages are the ones the
        # two boxes to its left are choosing between.
        self.manage_button = QPushButton("Saved versions...")
        self.manage_button.clicked.connect(self.manage_versions)
        picker.addWidget(self.manage_button)
        picker.addStretch(1)
        self.full_rows = QCheckBox("Show whole rows")
        self.full_rows.toggled.connect(self.model.set_show_full_rows)
        picker.addWidget(self.full_rows)
        outer.addLayout(picker)

        self._fill_pickers()

        # -- status ---------------------------------------------------------
        self.status = QLabel(self._initial_status())
        self.status.setProperty("role", "muted")
        self.status.setWordWrap(True)
        outer.addWidget(self.status)

        self.busy = QProgressBar()
        self.busy.setRange(0, 0)          # indeterminate
        self.busy.setVisible(False)
        self.busy.setMaximumHeight(6)
        self.busy.setTextVisible(False)
        outer.addWidget(self.busy)

        # -- filter ---------------------------------------------------------
        filter_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText(
            "Filter by table, field or value - searches the whole row")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._on_filter)
        filter_row.addWidget(self.search, 1)
        self.count = QLabel("")
        self.count.setProperty("role", "muted")
        # A fixed width, right-aligned. Left to size itself the label was
        # squeezed to a few pixels by the search box and rendered as "4",
        # which reads as a row count of four rather than a clipped 4,243.
        self.count.setMinimumWidth(150)
        self.count.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        filter_row.addWidget(self.count, 0)
        outer.addLayout(filter_row)

        # A comparison runs to thousands of rows, so acting on all of them
        # at once is not a convenience, it is the only practical way to work.
        bulk = QHBoxLayout()
        self.select_all_button = QPushButton("Select all shown")
        self.select_all_button.setMinimumWidth(
            self.select_all_button.sizeHint().width() + 8)
        self.select_all_button.clicked.connect(self.select_all_shown)
        bulk.addWidget(self.select_all_button)

        self.select_none_button = QPushButton("Select none")
        self.select_none_button.setMinimumWidth(
            self.select_none_button.sizeHint().width() + 8)
        self.select_none_button.clicked.connect(self.select_none)
        bulk.addWidget(self.select_none_button)
        bulk.addStretch(1)
        outer.addLayout(bulk)

        # -- the grid -------------------------------------------------------
        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(22)
        # Uniform row heights let the view skip measuring every row, which is
        # what keeps scrolling flat at 100,000 rows rather than merely
        # survivable.
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.ElideRight)

        # Column widths, set explicitly rather than left to
        # ResizeToContents.
        #
        # ResizeToContents alongside stretching columns gave the two
        # columns that IDENTIFY a row - which table, which field - about
        # 85px each, so they read "WorldSit..." and "Unknown...", while
        # Before and After got ~350px apiece to display values like "-1"
        # and "0". Exactly backwards: the identifying columns were the
        # unreadable ones.
        #
        # The widths below come from the real data. Measured across the
        # 1.4.0 -> 1.5.2 comparison, the longest table name is
        # "UISituationSubtitles-de", the longest field name is
        # "ItemNameTextUIId" and the longest row key is "56520/1".
        # Interactive, so they can still be dragged.
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        for column, width in DEFAULT_WIDTHS.items():
            header.setSectionResizeMode(column, QHeaderView.Interactive)
            self.table.setColumnWidth(column, width)
        # Before and After share whatever is left. Values run to 251
        # characters, so there is no width that fits them all - they elide,
        # and "Show whole rows" is how you see the surrounding context.
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        outer.addWidget(self.table, 1)

    # -- status text --------------------------------------------------------

    def _fill_pickers(self) -> None:
        """
        Puts the saved versions into the two boxes.

        Split out of `__init__` so `set_versions` can call it too. The
        selection is preserved across a refill where it still exists - a new
        version being archived should not silently repoint a comparison
        somebody had already set up.
        """
        previous = (self.from_box.currentText(), self.to_box.currentText())
        labels = list(self._versions)
        for box in (self.from_box, self.to_box):
            box.blockSignals(True)
            box.clear()
            box.addItems(labels)
            box.blockSignals(False)
        if len(labels) >= 2:
            self.from_box.setCurrentIndex(0)
            self.to_box.setCurrentIndex(len(labels) - 1)
            # Oldest to newest by default, but keep what was already picked.
            for box, was in ((self.from_box, previous[0]),
                             (self.to_box, previous[1])):
                if was and was in labels:
                    box.setCurrentText(was)
        self.compare_button.setEnabled(len(labels) >= 2)

    def manage_versions(self) -> None:
        """
        Opens the saved-versions dialog, and reports when it changed anything.

        The signal is emitted after the dialog closes rather than on each
        action, so a person who deletes three versions and saves one causes
        one re-discovery rather than four - and re-discovery opens every
        archive, which is not free.
        """
        dialog = SavedVersionsDialog(self._state, self)
        dialog.exec()
        if dialog.changed:
            self.versions_changed.emit()

    def set_versions(self, versions: dict) -> None:
        """
        New saved versions, after setup has archived one.

        The page had NO way to be told. Both boxes were filled once in
        `__init__` from whatever `discover_versions()` found when the window
        was built, and unpacking the game is what archives a version - so on
        a fresh install the boxes were empty, stayed empty for the whole
        session, and Compare Versions could not be used at all. Restarting
        the tool "fixed" it, which is the shape of a refresh that never
        happens - the same fault Jobs and Job Commands had with their
        dropdowns.

        `ReviewPage.set_versions` already existed and its docstring says
        "the shell calls both the same way". Nothing called either.
        """
        self._versions = dict(versions)
        self._fill_pickers()
        self.status.setText(self._initial_status())

    def _initial_status(self) -> str:
        if len(self._versions) >= 2:
            return "Pick two versions and press Compare."
        return ("Two saved versions are needed to compare. Mod Studio saves one "
                "each time you unpack, so this becomes available after the next "
                "game update.")

    def set_dark(self, dark: bool) -> None:
        self._dark = dark
        self.proxy.set_dark(dark)

    # -- running the comparison --------------------------------------------

    def start_compare(self) -> None:
        older, newer = self.from_box.currentText(), self.to_box.currentText()
        if not older or not newer or older == newer:
            self._say("Pick two different saved versions.", "attention")
            return

        self.compare_button.setEnabled(False)
        self.busy.setVisible(True)
        self._say(f"Comparing {older} with {newer}...", "muted")

        # Which pair is being compared is remembered here rather than
        # captured in a lambda. A lambda would be the natural way to carry
        # it, and it is exactly the thing that must not be passed to
        # run_in_thread - Qt cannot place a lambda on the GUI thread.
        self._comparing = (older, newer)

        worker = CompareWorker(
            self._versions[older], self._versions[newer], older, newer)
        # The thread is kept on self deliberately: a QThread that falls out
        # of scope is collected mid-run.
        self._thread = run_in_thread(
            worker,
            on_finished=self._done,
            on_failed=self._failed,
        )

    def _done(self, deltas) -> None:
        older, newer = self._comparing
        self.model.set_deltas(deltas)
        self.busy.setVisible(False)
        self.compare_button.setEnabled(True)
        self._say(f"{older} to {newer}: {self.model.summary()}", "muted")
        self._update_count()

    def _failed(self, message: str) -> None:
        self.busy.setVisible(False)
        self.compare_button.setEnabled(True)
        # Never "no differences" for a comparison that did not happen.
        self._say(f"The comparison couldn't be completed: {message}", "danger")

    def _say(self, text: str, role: str) -> None:
        self.status.setText(text)
        self.status.setProperty("role", role)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    # -- selecting in bulk ----------------------------------------------------

    def select_all_shown(self) -> None:
        """
        Selects everything the FILTER is currently showing, not everything
        in the comparison.

        "Select all" that quietly reaches past what you can see is how
        somebody accepts two thousand changes while looking at twelve.
        """
        self.table.selectAll()
        self.table.setFocus()

    def select_none(self) -> None:
        self.table.clearSelection()

    def selected_row_count(self) -> int:
        return len(self.table.selectionModel().selectedRows())

    # -- filtering ----------------------------------------------------------

    def _on_filter(self, text: str) -> None:
        self.proxy.setFilterFixedString(text)
        self._update_count()

    def _update_count(self) -> None:
        total = self.model.rowCount()
        shown = self.proxy.rowCount()
        if not total:
            self.count.setText("")
        elif shown == total:
            self.count.setText(f"{total:,} rows")
        else:
            self.count.setText(f"{shown:,} of {total:,} rows")
