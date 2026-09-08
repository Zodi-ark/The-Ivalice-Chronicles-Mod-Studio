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

from PySide6.QtCore import QSortFilterProxyModel, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QProgressBar, QPushButton, QTableView, QVBoxLayout, QWidget,
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


class ComparePage(QWidget):
    def __init__(self, versions: dict, dark: bool = False, parent=None):
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
