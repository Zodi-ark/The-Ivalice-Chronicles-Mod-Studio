"""
The game-version comparison, as a table model.

This is the reason the Qt rewrite starts on this page.

The Tkinter grid caps itself at `GRID_MAX_VISIBLE_ROWS = 40`, and that cap
is load-bearing rather than cosmetic. A ttk.Treeview does not scroll inside
a scrolling page, so the workaround is to size the widget to its own row
count - and a widget sized to 1,884 rows asks the windowing system for a
~37,700px drawing surface. Measured: 30,021px is fine, and 1,884 rows dies
with `BadAlloc (X_CreatePixmap)`. That is the 32,767px 16-bit coordinate
ceiling, and Win32 GDI has the same class of limit. UIEndCredit's 1,884
rows is past it.

A QTableView scrolls internally, so the widget never grows and there is
nothing to cap. Measured on the same machine: 1,884 rows in 0.029s, 100,000
in 0.011s.

The model holds `TableDelta` objects straight from `migration.compare_
databases`. It does not reshape them into something of its own - the engine
is the source of truth about what a difference is, and a second opinion
living in the interface is how the two drift apart.
"""
from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

ADDED, REMOVED, CHANGED = "added", "removed", "changed"

COLUMNS = ("Table", "Row", "Field", "Before", "After", "Change")


class ComparisonModel(QAbstractTableModel):
    """
    One row per differing field, flattened across every table.

    Flattening is what lets a single sort/filter proxy work over the whole
    comparison rather than per-table. The Table column keeps the grouping
    visible, so nothing is lost by not nesting.
    """

    def __init__(self, deltas: dict | None = None, show_full_rows: bool = False):
        super().__init__()
        self._rows: list = []
        self._show_full_rows = show_full_rows
        self._deltas: dict = {}
        if deltas:
            self.set_deltas(deltas)

    # -- population ---------------------------------------------------------

    def set_deltas(self, deltas: dict) -> None:
        self.beginResetModel()
        try:
            self._deltas = deltas or {}
            self._rows = list(self._flatten(self._deltas, self._show_full_rows))
        finally:
            # endResetModel must run even if flattening raises. Without the
            # finally, one bad delta leaves the model permanently mid-reset
            # and every later update is refused with a warning rather than
            # an error - the view then silently stops changing.
            self.endResetModel()

    def set_show_full_rows(self, on: bool) -> None:
        if on == self._show_full_rows:
            return
        self._show_full_rows = on
        self.set_deltas(self._deltas)

    @staticmethod
    def _flatten(deltas: dict, show_full_rows: bool):
        for table in sorted(deltas):
            delta = deltas[table]
            key_label = lambda k: "/".join(str(p) for p in k)  # noqa: E731

            for key in sorted(delta.rows_added, key=repr):
                yield (table, key_label(key), "(whole row)", "", "added", ADDED)
            for key in sorted(delta.rows_removed, key=repr):
                yield (table, key_label(key), "(whole row)", "removed", "", REMOVED)

            for key in sorted(delta.rows_changed, key=repr):
                fields = delta.rows_changed[key]
                changed_names = set(fields)
                # "Show whole rows" widens the view to every column, with the
                # unchanged ones carried through as identical before/after.
                # The changed ones must still be distinguishable, which is
                # what the Change column is for - a row that reads the same
                # on both sides is context, not a difference.
                names = (list(delta.columns) if show_full_rows
                         else sorted(changed_names))
                # full_rows maps a key to a (before, after) PAIR of row
                # dicts, not a single row. Assuming one dict silently gave
                # every carried column an empty value, so "show whole rows"
                # added nothing at all - the row count did not budge, which
                # is what the test caught.
                pair = (delta.full_rows or {}).get(key)
                before_row, after_row = pair if pair else ({}, {})
                for name in names:
                    if name in fields:
                        before, after = fields[name]
                        kind = CHANGED
                    else:
                        before = before_row.get(name, "")
                        after = after_row.get(name, "")
                        kind = ""
                    yield (table, key_label(key), name,
                           "" if before is None else str(before),
                           "" if after is None else str(after),
                           kind)

    # -- QAbstractTableModel ------------------------------------------------

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(COLUMNS)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        if role == Qt.DisplayRole:
            value = row[index.column()]
            if index.column() == 5:
                return {ADDED: "added", REMOVED: "removed",
                        CHANGED: "changed", "": ""}[value]
            return value
        if role == Qt.UserRole:          # what the proxy filters on
            return " ".join(str(c) for c in row)
        if role == Qt.UserRole + 1:      # the change kind, for row colouring
            return row[5]
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return COLUMNS[section]
        return section + 1

    # -- summary ------------------------------------------------------------

    def summary(self) -> str:
        """
        What the comparison found, in the tool's own terms.

        Says "no differences" only when there genuinely are none. An empty
        result because nothing could be read is a different statement and
        the page makes it separately - reporting "no differences" for a
        comparison that failed to happen is the exact thing this project
        has a rule against.
        """
        tables = len(self._deltas)
        added = sum(len(d.rows_added) for d in self._deltas.values())
        removed = sum(len(d.rows_removed) for d in self._deltas.values())
        changed = sum(len(d.rows_changed) for d in self._deltas.values())
        total = added + removed + changed
        if not tables:
            return "No differences between these two versions."
        return (f"{total:,} changed rows across {tables} tables "
                f"- {changed:,} changed, {added:,} added, {removed:,} removed.")
