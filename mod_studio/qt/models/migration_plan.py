"""
A migration plan, as a table model.

When the game updates, a mod built against the old version has to be
re-expressed on top of the new one. `migration.build_plan` works out, field
by field, what the mod changed, what the update changed, and whether those
two collide. This is how a person sees that and decides.

Each row carries a **resolution** - `KEEP_MOD` or `TAKE_UPDATE` - and that
is the only thing this model writes. Everything else comes from the engine's
`FieldChange` and is displayed, not recomputed. The interface deciding for
itself what a conflict is would be a second opinion drifting away from the
one that actually gets applied.

Three of the project's honesty rules land here, and all three are the
difference between a review someone can trust and one they cannot:

- **A row is never hidden.** It can arrive switched off, but it must be
  visible and it must carry a reason.
- **A change that can't be examined says so**, rather than being reported
  as "no differences".
- **A substitute baseline is labelled as one**, so a plan built against an
  approximation is not mistaken for one built against the real thing.
"""
from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from ... import migration

COLUMNS = ("Section", "Table", "Row", "Field", "Your mod", "The update",
           "What happens", "Why")


class MigrationModel(QAbstractTableModel):
    def __init__(self, plan=None, parent=None):
        super().__init__(parent)
        self._plan = None
        self._changes = []
        self._all_changes = []
        if plan is not None:
            self.set_plan(plan)

    # -- population ------------------------------------------------------------

    def set_plan(self, plan, show_clean: bool = True) -> None:
        """
        Loads a plan, optionally hiding the changes that carry over cleanly.

        Hidden by default now. On a real update most changes are clean and
        need no decision, so listing them buries the handful that do - and
        the handful that do is the entire reason for this page. The Tkinter
        interface has the same switch, off by default, labelled "Also list
        changes that carry over cleanly".

        Clean rows are hidden, never dropped: `summary()` still counts every
        one, so the total does not change when the box is ticked.
        """
        self.beginResetModel()
        try:
            self._plan = plan
            everything = list(getattr(plan, "changes", []) or [])
            self._all_changes = everything
            self._changes = everything if show_clean else [
                change for change in everything
                if getattr(change, "outcome", None) != migration.CLEAN]
        finally:
            self.endResetModel()

    @property
    def plan(self):
        return self._plan

    def change_at(self, row: int):
        return self._changes[row] if 0 <= row < len(self._changes) else None

    # -- QAbstractTableModel ----------------------------------------------------

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._changes)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(COLUMNS)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        change = self._changes[index.row()]
        if role == Qt.DisplayRole:
            return (
                change.section,
                change.table,
                str(change.key),
                change.field_name,
                _show(change.mod_value),
                _show(change.new_value),
                "Keep mine" if change.resolution == migration.KEEP_MOD
                else "Take the update",
                _reason(change),
            )[index.column()]
        if role == Qt.ToolTipRole:
            # The reason in full, whatever the column width does to it. A
            # truncated explanation is worse than none: it looks like it
            # said something.
            return _reason(change)
        if role == Qt.UserRole:
            return " ".join(str(part) for part in (
                change.section, change.table, change.key, change.field_name,
                change.mod_value, change.new_value, change.label))
        if role == Qt.UserRole + 1:
            return change
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return COLUMNS[section]
        return None

    # -- resolutions ------------------------------------------------------------

    def set_resolution(self, rows, resolution: str) -> int:
        """
        Sets Keep-mine or Take-the-update on the given source rows.

        Returns how many actually changed, so a caller can report "nothing
        to do" rather than implying it did something.
        """
        touched = 0
        for row in rows:
            change = self.change_at(row)
            if change is None or change.resolution == resolution:
                continue
            change.resolution = resolution
            touched += 1
            top = self.index(row, 0)
            self.dataChanged.emit(top, self.index(row, len(COLUMNS) - 1))
        return touched

    def counts(self) -> dict:
        """
        Counts the WHOLE plan, not the rows currently on screen.

        These feed the summary line, and a total that shrinks when you tick
        "Also list changes that carry over cleanly" would be reporting the
        filter rather than the update. The clean count is separate so the
        page can say how many were left out.
        """
        everything = getattr(self, "_all_changes", None) or self._changes
        keep = sum(1 for c in everything
                   if c.resolution == migration.KEEP_MOD)
        clean = sum(1 for c in everything
                    if getattr(c, "outcome", None) == migration.CLEAN)
        return {"total": len(everything), "keep": keep,
                "update": len(everything) - keep, "clean": clean,
                "shown": len(self._changes)}

    def summary(self) -> str:
        """
        What the plan found, without overstating it.

        Says "nothing to re-apply" only when the plan really is empty. A
        plan that could not be built at all is a different statement and the
        page makes it separately.
        """
        if self._plan is None:
            return ""
        counts = self.counts()
        if not counts["total"]:
            # Not "nothing to do": a plan with no field changes can still
            # carry nine whole files with no editor tab, which is what the
            # engine's own summary reports and what this used to hide.
            # `MigrationPlan.summary()` is the line the Tkinter page shows.
            # `summary()` off the plan when it has one. A real MigrationPlan
            # always does; test stand-ins do not, and a model that only works
            # against the full class is a model that cannot be tested in
            # isolation.
            if getattr(self._plan, "unmodelled", None):
                describe = getattr(self._plan, "summary", None)
                if callable(describe):
                    return describe()
                return (f"{len(self._plan.unmodelled)} table(s) with no "
                        f"editor tab need a decision, below.")
            return ("Nothing of yours needs re-applying - the update doesn't "
                    "touch anything your mod changed.")
        text = (f"{counts['total']:,} of your changes to re-apply "
                f"({counts['keep']:,} keeping yours, "
                f"{counts['update']:,} taking the update's).")
        if getattr(self._plan, "unmodelled", None):
            text += (f" {len(self._plan.unmodelled)} table(s) with no editor "
                     f"tab, below.")
        hidden = counts["total"] - counts["shown"]
        if hidden:
            text += (f" {hidden:,} carry over cleanly and aren't listed - "
                     f"tick the box above to see them.")
        return text


def _show(value) -> str:
    return "" if value is None else str(value)


def _reason(change) -> str:
    """
    Why a row reads the way it does.

    Every row gets one. A change offered without a reason is a change
    somebody has to accept on faith, and the whole point of the review is
    that they do not have to.
    """
    outcome = change.outcome
    if outcome == migration.CONFLICT:
        return ("You and the update both changed this. Whichever you pick, "
                "the other is lost.")
    if outcome == migration.REDUNDANT:
        return ("The update already does what your mod did here, so keeping "
                "yours changes nothing.")
    if outcome == migration.ORPHANED:
        return "The row your mod changed isn't in the new version any more."
    if outcome == migration.CLEAN:
        return "The update doesn't touch this, so your change carries over."
    if outcome == migration.ORIGIN_CHANGED:
        return "The row this came from has changed in the new version."
    if outcome == migration.ORIGIN_REMOVED:
        return "The row this came from is gone from the new version."
    if outcome == migration.ROW_COUNT_CHANGED:
        return "This table has a different number of rows in the new version."
    if outcome == migration.DESTINATION_TAKEN:
        return "Something else already occupies the address this moves to."
    # Never blank. An unrecognised outcome is reported as itself rather than
    # silently reading as though there were nothing to say.
    return f"Outcome: {outcome}"
