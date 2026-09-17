"""
Re-reading the edit store when an editing page comes back on screen.

### The fault this exists to stop

Two pages can edit the same row - All Game Data reaches every table, and six
curated tabs reach the same rows with hand-built controls. Both write the
same store, which is right. What was wrong is that neither ever re-READ it.

Every editing page rewrites the row's whole dictionary from its own widgets
on each edit:

    for field_name, row in self.rows.items():
        if row.included:
            edits[field_name] = row.get_value_str()
        elif field_name in edits:
            del edits[field_name]          # <- this line

A page whose widgets were filled before the other page's edit has its
include ticks OFF for every field it never saw, so that `del` deletes them.
Measured in both directions on `JobCommand-en` row 12:

    AGD edits Name        -> {'en': {12: {'Name': 'EDITED VIA ALL GAME DATA'}}}
    tab then edits Descr. -> {'en': {12: {'Description': '...'}}}     Name gone

Nothing on screen says so. The stale display is the symptom; the silent
deletion is the fault, and it reaches **42 per-language tables** across six
curated specs plus `OverrideAbilityActionData` and `OverrideEntryData`.

### Why becoming visible is the moment

`load_record` already reads the store correctly - setting the store directly
and reloading showed the edited value and the right counter. The pages are
not wrong about the data; they simply never re-read it. Only one editing
page is on screen at a time, so becoming visible is both the earliest moment
the staleness could be SEEN and the last moment before somebody can type
into it. One hook closes all four symptoms - the stale display, the
disagreeing counters, the "Open Jobs ->" landing, and the deletion, because
a page showing the edit with its tick ON preserves it when it rewrites the
row.

Explicitly NOT the shape: `edits_changed` wired to `refresh_records`. That
rebuilds a 179-row list and snaps the selection to row 0, so editing in one
place would move the other page out from under anybody who had it open -
the exact fault `refresh_usage` was written to avoid - and `_on_field_edited`
fires on every keystroke.

### Why a mixin rather than a `showEvent` on each page

Nine pages each hand-built the same three lines of scroll-area setup and all
nine carried the same bug; `FormScrollArea` exists because of it. Eight
copies of

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh_from_store()

would be that mistake again, and a ninth page added later would be the one
that forgot. The trigger is shared here; only the reload body differs per
page, because the pages genuinely differ - eight different names for "the
record I am showing".

`showEvent` rather than the shell's `_select_tab`, measured: `_select(index)`
switches STEPS without calling `_select_tab`, so leaving Edit Game Data for
Export Mod and coming back would NOT have refreshed the tab underneath.
Qt sends the show event through both stacks, so this covers that path and
any navigation added later.
"""
from __future__ import annotations


class RefreshesWhenVisible:
    """
    Calls `refresh_from_store()` whenever the page comes on screen.

    Mixed in BEFORE `QWidget` so its `showEvent` runs first and then
    cooperates:

        class JobsPage(RefreshesWhenVisible, QWidget):

    `refresh_from_store` must re-read the current record and recompute the
    marks and counters WITHOUT rebuilding the list or moving the selection.
    Rebuilding is what makes a refresh hostile to the person using it.
    """

    def showEvent(self, event):                              # noqa: N802
        super().showEvent(event)
        # Guarded, because a show event arrives during window construction -
        # before the page has records, sometimes before its state has been
        # populated at all. A refresh that raises there would take the whole
        # window down on start-up, which is a worse fault than the one this
        # is fixing.
        self.refresh_from_store()

    def refresh_from_store(self) -> None:
        """
        Re-read what this page is showing from the edit store.

        Deliberately not implemented here. There is no honest generic body:
        the pages name their current record eight different ways, and a
        default that silently did nothing would let a new page inherit the
        mixin, look wired, and go on deleting edits. `audit_view_toggles`
        checks every editing page reaches this.
        """
        raise NotImplementedError(
            f"{type(self).__name__} inherits RefreshesWhenVisible but does "
            "not implement refresh_from_store()")
