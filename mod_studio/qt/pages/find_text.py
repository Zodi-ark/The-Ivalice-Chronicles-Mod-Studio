"""
Edit Game Data / Find Text.

The scenario: somebody sees a line of text in the game, wants to change it,
and has no idea which `.nxd` file or which row it lives in. Without this,
the answer is to open All Game Data and pick through 562 tables by name.

Three things this has to get right, all of them measured against the real
1.5.2 database rather than assumed:

**Every language, not the user's own.** The text tables ship one file per
language - `Job-en`, `Job-de`, `Job-ja` - so a search that returns only
`-en` tells a person where to change the text for English players and
nowhere else. They ship the mod, and it is unchanged for everyone else,
silently. Typing "Chocobo" here returns 117 English rows and **110 German
ones**, which is the whole point.

**Everything, not the modelled 53.** Four counts are in play and they are
all real:

    563  tables in the database - every .nxd, including language variants
    245  distinct tables ignoring the -<lang> suffix
     53  ALL_NXD_SPECS - what the registry models
      6  CURATED_NXD_SPECS - the tables with dedicated tabs

Search covers the **493 that contain text at all**, which is 371 registered
language variants (53 x 7, exactly) plus 122 shared tables. Anything less
and the feature fails at its own premise, because the text somebody cannot
find is disproportionately the text in a table nobody has modelled.

**A result has to be a fix, not a lookup.** "Job-de row 68" names a place
without going there. Every hit here opens All Game Data at that table and
that row, on the editable field.

There is no read-only tier and no table was registered to make this work.
That question was live before it was measured: `list_all_tables` returns
EVERY table, so All Game Data already lists all 562 and can edit any of
them through the unmodelled store. Every hit already had somewhere to go.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from ... import constants as c
from ... import nxd_data
from ..widgets.actions import page_intro, set_empty_state


# Enough to be worth reading, few enough that the list stays a list. A
# search returning every row of Novel01 is not an answer to "where is this
# line", it is the same problem in a different window.
RESULT_LIMIT = 500

# Characters of the matching value to show. The longest real string in the
# database runs past 400 characters, and a column of those makes the table
# unreadable - the snippet is centred on the match instead.
SNIPPET = 110


class FindTextPage(QWidget):
    # (table, key) - a table name AND a row, which is a different payload
    # from `navigate_requested`'s (tab name, record id).
    #
    # A separate signal rather than overloading that one, for the reason
    # already recorded about Items' two jumps: a single signal carrying
    # "either a record id or a table-and-row, depending" works until
    # somebody passes the wrong one.
    locate_requested = Signal(str, object)

    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state
        self._hits = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 10, 24, 20)
        outer.setSpacing(10)

        # `page_intro` rather than a QLabel of its own.
        #
        # It is not just a label: `role="intro"` carries the `min-height`
        # that keeps every tab's description on the same line as every
        # other tab's, whether or not the tab has controls beside it. A
        # hand-rolled `role="muted"` label here put this page's description
        # 13px higher than the eleven beside it - caught by the check in
        # `test_qt_app` that measures all of them against each other, which
        # is exactly the drift that check exists for.
        outer.addLayout(page_intro(
            "Search every line of text in the game data. Type something you "
            "have seen in game and this finds which table and row it lives "
            "in, in every language."))

        self.empty_note = QLabel("")
        self.empty_note.setWordWrap(True)
        outer.addWidget(self.empty_note)

        # -- the search row --------------------------------------------------
        self.controls = QWidget()
        row = QHBoxLayout(self.controls)
        row.setContentsMargins(0, 0, 0, 0)
        self.needle = QLineEdit()
        self.needle.setPlaceholderText(
            "Text as it appears in game - a name, a line of dialogue, part of "
            "a description")
        self.needle.setClearButtonEnabled(True)
        self.needle.returnPressed.connect(self.run_search)
        row.addWidget(self.needle, 1)

        row.addSpacing(8)
        row.addWidget(QLabel("Language:"))
        self.language_box = QComboBox()
        # "All languages" first and selected by default. The requirement is
        # that an English search finds the German row, so the default cannot
        # be the user's own language - narrowing is the opt-in.
        self.language_box.addItem("All languages", None)
        for code in c.NXD_LANGUAGES:
            self.language_box.addItem(
                c.NXD_LANGUAGE_LABELS.get(code, code), code)
        row.addWidget(self.language_box)

        row.addSpacing(8)
        self.search_button = QPushButton("Find")
        self.search_button.clicked.connect(self.run_search)
        row.addWidget(self.search_button)
        outer.addWidget(self.controls)

        self.summary = QLabel("")
        self.summary.setProperty("role", "muted")
        self.summary.setWordWrap(True)
        outer.addWidget(self.summary)

        # -- results ---------------------------------------------------------
        self.results = QTreeWidget()
        self.results.setColumnCount(4)
        self.results.setHeaderLabels(["Table", "Row", "Field", "Text"])
        self.results.setRootIsDecorated(False)
        self.results.setAlternatingRowColors(True)
        self.results.setSelectionMode(QAbstractItemView.SingleSelection)
        self.results.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.results.itemActivated.connect(self._on_activated)
        self.results.itemDoubleClicked.connect(self._on_activated)
        self.results.currentItemChanged.connect(self._sync_open_button)
        header = self.results.header()
        header.setSectionResizeMode(0, QHeaderView.Interactive)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        header.setSectionResizeMode(2, QHeaderView.Interactive)
        # The text column takes the slack. It is the one whose content has
        # no natural width, so giving the slack to any other column leaves
        # it truncated at a fixed size on every monitor.
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        self.results.setColumnWidth(0, 170)
        self.results.setColumnWidth(1, 90)
        self.results.setColumnWidth(2, 150)
        outer.addWidget(self.results, 1)

        # -- opening -----------------------------------------------------------
        actions = QHBoxLayout()
        self.hint = QLabel(
            "Double-click a result to open it in All Game Data.")
        self.hint.setProperty("role", "muted")
        actions.addWidget(self.hint)
        actions.addStretch(1)
        self.open_button = QPushButton("Open in All Game Data \u2192")
        self.open_button.setEnabled(False)
        self.open_button.clicked.connect(self._open_current)
        actions.addWidget(self.open_button)
        outer.addLayout(actions)

        self.refresh_records()

    # -- state ----------------------------------------------------------------

    def view_toggles_used(self) -> tuple:
        """
        `(notes, unknown, comments)` - which toggles mean anything here.

        This page is a list of search results, not a form: it has no field
        notes, no unknown-field rows and no comment rows for the toggles
        to act on. Leaving them on screen invited exactly the worry that
        prompted this - that "Hide unknown fields" might be filtering the
        search. It is not, and never was; the search reads the database.
        """
        return (False, False, False)

    def refresh_records(self) -> None:
        """
        Called when setup finishes, like every other editing page.

        Named `refresh_records` on purpose: `app._on_setup_changed` asks
        EVERY page whether it has this method rather than working from a
        list of page names, and that list has been wrong three times. A
        page that opts out by naming its refresh something else opts out
        of ever being told the game data arrived.
        """
        has_data = bool(getattr(self.state, "nxd_sqlite_path", None))
        set_empty_state(self.empty_note, has_data, self.controls,
                        self.results, self.summary)
        if not has_data:
            self.results.clear()
            self._hits = []
            self.open_button.setEnabled(False)

    # -- searching -------------------------------------------------------------

    def run_search(self) -> None:
        """
        Runs the search and fills the list.

        On the GUI thread, deliberately. Measured against the shipped 1.5.2
        database: scanning all 1138 text columns of all 493 tables takes
        about 0.13s. A background worker would buy nothing and cost a
        spinner, a cancel path and a race - and the first version of the
        engine call DID take 1.28s, because it opened a fresh connection
        per table. That was worth fixing rather than hiding behind a
        thread.
        """
        sqlite_path = getattr(self.state, "nxd_sqlite_path", None)
        if not sqlite_path:
            self.summary.setText("No game data loaded yet.")
            return
        needle = self.needle.text().strip()
        self.results.clear()
        self._hits = []
        self.open_button.setEnabled(False)
        if not needle:
            self.summary.setText("Type something to look for.")
            return

        language = self.language_box.currentData()
        try:
            hits = nxd_data.search_text(
                sqlite_path, needle,
                languages=[language] if language else None,
                limit=RESULT_LIMIT)
        except Exception as exc:                              # noqa: BLE001
            self.summary.setText(f"Couldn't search: {exc}")
            return

        self._hits = hits
        for hit in hits:
            item = QTreeWidgetItem([
                hit.table, self._key_text(hit.key), hit.column,
                self._snippet(hit.value, needle),
            ])
            item.setData(0, Qt.UserRole, hit)
            item.setToolTip(3, hit.value[:2000])
            self.results.addTopLevelItem(item)

        self.summary.setText(self._summarise(hits, needle, language))
        if hits:
            self.results.setCurrentItem(self.results.topLevelItem(0))

    def _summarise(self, hits: list, needle: str, language) -> str:
        """
        What was found, and - when it matters - what was NOT shown.

        A capped list that does not say it is capped reads as a complete
        answer, and the person stops looking. Rule 6 in a different
        costume: a number that was true of the first 500 rows keeps being
        reported as though it were true of all of them.
        """
        if not hits:
            where = ("any language" if not language
                     else c.NXD_LANGUAGE_LABELS.get(language, language))
            return (f"Nothing in {where} contains \u201c{needle}\u201d. The "
                    f"search covers every table that holds text, so if it is "
                    f"not here it is not in the game data - it may be in a "
                    f"texture, or built by the game at runtime.")
        tables = sorted({hit.base_table for hit in hits})
        languages = sorted({hit.language for hit in hits if hit.language})
        parts = [f"{len(hits)} match(es) in {len(tables)} table(s)"]
        if languages:
            parts.append("across " + ", ".join(
                c.NXD_LANGUAGE_LABELS.get(code, code) for code in languages))
        text = " ".join(parts) + "."
        if len(hits) >= RESULT_LIMIT:
            text += (f" Stopped at {RESULT_LIMIT} - there are more. Add a word "
                     f"to narrow it down.")
        return text

    @staticmethod
    def _key_text(key) -> str:
        """A compound key reads as `3131, 1` rather than as a Python tuple."""
        if isinstance(key, tuple):
            return ", ".join(str(part) for part in key)
        return str(key)

    @staticmethod
    def _snippet(value: str, needle: str) -> str:
        """
        The match with a little either side, on one line.

        Centred on the match rather than taken from the start: the longest
        strings in this database run past 400 characters, and the first 110
        of a novel page will not contain the thing you searched for.
        """
        flat = " ".join((value or "").split())
        if len(flat) <= SNIPPET:
            return flat
        at = flat.lower().find(needle.lower())
        if at < 0:
            return flat[:SNIPPET] + "\u2026"
        start = max(0, at - SNIPPET // 3)
        end = min(len(flat), start + SNIPPET)
        return (("\u2026" if start else "") + flat[start:end]
                + ("\u2026" if end < len(flat) else ""))

    # -- opening a hit ----------------------------------------------------------

    def _sync_open_button(self, *_args) -> None:
        self.open_button.setEnabled(self.current_hit() is not None)

    def current_hit(self):
        item = self.results.currentItem()
        return item.data(0, Qt.UserRole) if item is not None else None

    def _on_activated(self, item, _column=0) -> None:
        hit = item.data(0, Qt.UserRole) if item is not None else None
        if hit is not None:
            self.locate_requested.emit(hit.table, hit.key)

    def _open_current(self) -> None:
        hit = self.current_hit()
        if hit is not None:
            self.locate_requested.emit(hit.table, hit.key)
