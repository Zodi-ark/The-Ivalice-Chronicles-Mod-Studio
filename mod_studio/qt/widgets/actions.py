"""
The small things that make the tool usable, shared across pages.

Each of these exists in the Tkinter interface and is the kind of feature
that never appears in a bug report because people just stop using the tool
instead. They live here rather than in each page so that four tabs cannot
grow four subtly different ideas of what "copy to all languages" means.
"""
from __future__ import annotations

import os
import platform
import subprocess
import weakref
import zipfile
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QCheckBox, QHBoxLayout, QLabel, QSizePolicy, QWidget)

from ... import constants as c
from ... import nxd_data
from .. import theme
from .layout_settle import settle_layout


def copy_edits_to_languages(store: dict, source_language: str, key,
                            languages, skip_fields=None) -> list:
    """
    Copies one record's edits from the language you're editing into all the
    others, and returns the languages that changed.

    Names differ per language; numbers do not. Somebody who has just set an
    item's price or an ability's icon in English does not want to retype it
    five times, and the Tkinter interface has a "Copy to all languages"
    button on every per-language tab for exactly that.

    What it copies is the EDITS, not the record - only fields actually
    ticked travel. Copying the whole record would silently pull every
    untouched value into the mod as well, which is precisely what per-field
    opt-in exists to prevent.

    **`skip_fields` is how text is kept out, and it is not optional in
    practice.** The Tkinter interface never copies game text: its
    `AbilityTextRow` only grows a `copy_fields` method when constructed
    `copyable=True`, which is an explicit opt-in used for a `Comment`
    column and never for a Name or Description. The label on the button
    says so - "Text fields above are never copied - translate those
    yourself".

    The Qt version had no equivalent and copied everything, so one press
    put the English name into all seven language tables at once. That
    produces a mod which ships English text claiming to be Japanese, and
    nothing downstream can tell that apart from a deliberate translation.
    Measured before the fix: copying `{Name: "Firaga", IconId: 12}` from
    `en` wrote the name into cs, ct, de, fr, ja and ko.

    Existing edits in the destination language are updated rather than
    replaced wholesale, so a field edited only in German survives a copy
    from English.
    """
    source = (store.get(source_language) or {}).get(key)
    if not source:
        return []
    if skip_fields:
        source = {name: value for name, value in source.items()
                  if name not in skip_fields}
        if not source:
            return []

    changed = []
    for language in languages:
        if language == source_language:
            continue
        destination = store.setdefault(language, {}).setdefault(key, {})
        before = dict(destination)
        destination.update(source)
        if destination != before:
            changed.append(language)
    return changed


def copy_all_records_to_languages(store: dict, source_language: str,
                                  languages, skip_fields=None) -> tuple:
    """
    The same, for every edited record at once.

    Returns (records copied, languages touched). The Tkinter interface calls
    this "Copy all fields to other languages"; it is what somebody reaches
    for after a session of editing rather than after a single field.
    """
    source = store.get(source_language) or {}
    keys = [key for key, fields in source.items() if fields]
    touched = set()
    copied = 0
    for key in keys:
        changed = copy_edits_to_languages(store, source_language, key,
                                          languages, skip_fields=skip_fields)
        touched.update(changed)
        # A record whose only edits were text fields has nothing to copy,
        # so it is not counted as copied - the number on screen should be
        # what travelled, not what was looked at.
        if changed:
            copied += 1
    return copied, sorted(touched)


def reveal_in_file_manager(path: Path) -> bool:
    """
    Opens a folder in Explorer / Finder / the desktop's file manager.

    Returns whether it was launched, so a caller can say "couldn't open
    that" rather than appearing to do nothing. "Open Mod Folder" is the
    button people press straight after building a mod, and its absence is
    felt immediately.
    """
    path = Path(path)
    if not path.exists():
        return False
    try:
        if platform.system() == "Windows":
            os.startfile(str(path))                    # noqa: S606
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", str(path)])      # noqa: S603,S607
        else:
            subprocess.Popen(["xdg-open", str(path)])  # noqa: S603,S607
        return True
    except Exception:                                  # noqa: BLE001
        return False


def zip_folder(folder: Path, destination: Path) -> Path:
    """
    Zips a built mod for uploading, with the mod folder itself inside.

    The folder is kept as the archive's top level deliberately: a zip that
    unpacks its contents loose into whatever directory someone extracts it
    to is how a Reloaded-II mods folder ends up full of stray XML.
    """
    folder = Path(folder)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for item in sorted(folder.rglob("*")):
            if item.is_file():
                archive.write(item, folder.name + "/"
                              + str(item.relative_to(folder)).replace("\\", "/"))
    return destination


def mark_edited(item, edited: bool) -> None:
    """
    Marks a list row as having pending edits, the way Tkinter does it.

    The whole row goes green - but the THEME's green, not `constants`'.

    The constants are `EDITED_ROW_BG`/`_FG`, which the Tkinter interface
    uses and which are a light theme's colours. Used unchanged in dark mode
    they are a bright mint bar with near-black text in a dark window, and
    on a list of 500 rows with many edited they are the page rather than a
    mark on it. `theme.current()` returns the light theme's own values when
    the light theme is showing, so the two interfaces still agree there.

    The Qt pages used bold instead. Bold is easy to miss in a list of 500
    rows, and impossible to scan for: a green bar is visible while
    scrolling past, which is the whole point of marking them at all.

    Bold is kept as well. Colour alone is a poor signal for anyone who
    cannot easily distinguish it, and the two together cost nothing.

    Clearing sets an invalid brush rather than a theme colour, so the row
    goes back to whatever the palette says - hard-coding white here would
    show as a white bar in dark mode.
    """
    font = item.font()
    font.setBold(edited)
    item.setFont(font)
    if edited:
        colours = theme.current()
        item.setBackground(QBrush(QColor(colours["edited_bg"])))
        item.setForeground(QBrush(QColor(colours["edited_fg"])))
    else:
        item.setBackground(QBrush())
        item.setForeground(QBrush())


class ViewToggles(QWidget):
    """
    `[ ] Hide field notes   [ ] Hide unknown fields   [x] Hide comments`

    Every tab with field rows gets these, not just Jobs. They were on Jobs
    alone for the same reason most gaps happen: the first page that needed
    them grew them, and the next four were built from the page rather than
    from the interface.

    Both choices are saved to `ui_settings.json`, the same store the Tkinter
    interface writes, so a preference set in either is honoured by both -
    and by every tab, since hiding unknown fields on one tab and not the
    next would be a strange thing to mean.

    **Small, and beside the heading.** These are a display preference set
    once and forgotten, and the Qt version gave them a full-width bar on
    all ten tabs - more visual weight than the record counter next to them.
    The Tkinter interface tucks the pair into the header, on the heading's
    own line (`gui/step_editor.py`, around the `toggles` frame). This is
    sized to its contents so a page can do the same rather than having a
    strip forced across it.

    **One preference, ten checkboxes.** Every page builds its own instance,
    so before `_ALL` existed the ten copies did not agree: ticking "Hide
    field notes" on Jobs saved the setting and applied it to Jobs, and the
    Poaching tab went on showing notes with its box unticked until the tool
    was restarted. The setting was shared; the widgets were not. Instances
    now push state to each other, which is the nearest thing to Tkinter's
    single step-level pair without every page having to know about the rest.
    """

    changed = Signal(bool, bool, bool)

    # Every live instance. Weak, so a closed page does not keep its widgets
    # alive and a stale entry cannot be signalled at.
    _ALL: "weakref.WeakSet" = weakref.WeakSet()

    def __init__(self, parent=None):
        super().__init__(parent)
        from ... import ui_settings

        saved = ui_settings.load()
        self._syncing = False

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)

        self.notes = QCheckBox("Hide field notes")
        self.notes.setChecked(bool(saved.get("hide_field_notes", False)))
        self.notes.toggled.connect(self._emit)
        row.addWidget(self.notes)

        self.unknown = QCheckBox("Hide unknown fields")
        self.unknown.setChecked(bool(saved.get("hide_unknown_fields", False)))
        self.unknown.toggled.connect(self._emit)
        row.addWidget(self.unknown)

        # ON by default, unlike the two beside it.
        #
        # `Comment` is a column on 134 of the game's tables and holds the
        # game team's own working notes. It is not something a mod changes,
        # so it costs a row on every record to show a field almost nobody
        # wants - and it sits directly under Description, where it reads
        # like a second one. Defaulted on for that reason, and a toggle
        # rather than a deletion because the people who do want to read
        # those notes have nowhere else to.
        self.comments = QCheckBox("Hide comments")
        self.comments.setChecked(bool(saved.get("hide_comments", True)))
        self.comments.toggled.connect(self._emit)
        row.addWidget(self.comments)

        # Quieter than the content around them: this is a preference, not an
        # action, and it should not compete with the record counter.
        for box in (self.notes, self.unknown, self.comments):
            box.setStyleSheet("font-size: 9pt;")
            box.setProperty("role", "muted")
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        ViewToggles._ALL.add(self)

    def standalone_row(self) -> QHBoxLayout:
        """
        A right-aligned row holding just these toggles.

        Every Edit Game Data tab uses this, at the same point - directly
        above the list-and-editor split - so the pair is in the same place
        on all ten. They had drifted into three different positions: their
        own row on Abilities, Encounters and Poaching, and sharing the
        record counter's line on Jobs and the generic table tabs. Two
        checkboxes that move when you change tab are two checkboxes you have
        to find again each time.

        Right-aligned rather than left because the counter and the heading
        above are the things worth reading, and a preference should not sit
        in front of them.
        """
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addStretch(1)
        row.addWidget(self)
        return row

    def follow_only(self) -> None:
        """
        Keeps this instance in sync but never shows it.

        Pages still build their own so that `self.view_toggles.state()` and
        `_apply_view` keep working unchanged, but only the shell's pair is
        drawn. A hidden widget is skipped by its layout, so this leaves no
        gap where the row used to be.
        """
        self.setVisible(False)

    def show_only(self, notes: bool = True, unknown: bool = True,
                  comments: bool = True) -> None:
        """
        Hides the toggles a page has no use for.

        A checkbox that does nothing where it is shown is worse than one
        that is absent: the reader ticks it, sees no change, and stops
        trusting the other two. Find Text has no field notes, no unknown
        rows and no comment rows - it is a search result list - so all
        three are hidden there. All Game Data has no notes and deliberately
        shows every column including the unknown ones, so it keeps only
        "Hide comments".

        The state is untouched - only the widget's visibility - so a
        preference set on one tab still applies on the tabs that use it.
        Hiding a control must not silently change what it controls.
        """
        self.notes.setVisible(notes)
        self.unknown.setVisible(unknown)
        self.comments.setVisible(comments)
        self.setVisible(notes or unknown or comments)

    def state(self) -> tuple:
        return (self.notes.isChecked(), self.unknown.isChecked(),
                self.comments.isChecked())

    def set_state(self, hide_notes: bool, hide_unknown: bool,
                  hide_comments: bool) -> None:
        """
        Matches another instance without re-broadcasting.

        The guard is what stops ten widgets echoing one click around the
        set forever.
        """
        self._syncing = True
        try:
            self.notes.setChecked(hide_notes)
            self.unknown.setChecked(hide_unknown)
            self.comments.setChecked(hide_comments)
        finally:
            self._syncing = False

    def _emit(self, _on) -> None:
        from ... import ui_settings

        if self._syncing:
            return
        hide_notes, hide_unknown, hide_comments = self.state()
        ui_settings.save(hide_field_notes=hide_notes,
                         hide_unknown_fields=hide_unknown,
                         hide_comments=hide_comments)

        for other in list(ViewToggles._ALL):
            if other is self:
                continue
            other.set_state(hide_notes, hide_unknown, hide_comments)
            # Each page still has to redisplay its own rows; the widget
            # only knows about the preference, not about the form.
            other.changed.emit(hide_notes, hide_unknown, hide_comments)

        self.changed.emit(hide_notes, hide_unknown, hide_comments)


def apply_view_toggles(rows, hide_notes: bool, hide_unknown: bool,
                       hide_comments: bool) -> None:
    """
    Pushes the toggles at every row that understands them.

    Rows that carry no notes and are never unknown - flag panels, dropdowns -
    implement `apply_display` as a no-op rather than being special-cased
    here, so a new row type works without this function knowing about it.
    """
    touched = {}
    for row in rows:
        handler = getattr(row, "apply_display", None)
        if handler is not None:
            handler(hide_notes, hide_unknown, hide_comments)
            parent = row.parentWidget() if hasattr(row, "parentWidget") else None
            if parent is not None:
                touched.setdefault(id(parent), parent)
    # Hiding rows down a page shortens its content, and the page it sits in
    # is only resized a posted event later - the same two-pass window that
    # made a section expand flash. Fixing it on `CollapsibleSection` alone
    # left this path flashing, which is how it was reported the second time.
    #
    # **Once per BODY, not once for the lot.** Items keeps its rows across
    # three sub-tab scroll areas, and a `QStackedWidget` does not pass a
    # layout request sideways to its siblings - so settling from the last
    # row only settled the last row's branch and 311 widgets on the visible
    # sub-tab still moved after the click. Deduplicated by parent, because
    # rows in one body share one, and the walk up from each reaches the
    # window anyway.
    for parent in touched.values():
        settle_layout(parent)


def _registry_key_for_store(store_name: str):
    """
    The registry key behind a state attribute like `poach_records`.

    Pages name the store they already use rather than a second vocabulary
    that can disagree with it - that part was right and is kept. What
    changed is where the answer comes from: this used to be a hand-written
    map of four stores to four reader function names, so a newly registered
    table had a page, an export and a review, and then silently failed to
    load any language but the one Setup had already fetched.
    """
    from ... import nxd_data
    for key, spec in nxd_data.ALL_NXD_SPECS.items():
        if spec.records_attr == store_name:
            return key
    return None


def ensure_language_loaded(state, store_name: str, language: str) -> bool:
    """
    Reads one language's nxd table if it isn't in the state yet.

    **Lazily, one language at a time**, which is what the Tkinter interface
    has always done (`_ensure_nxd_loaded`). The Qt setup read English and
    only English, so switching the Language box to `ja` gave a page with
    every field blank - not because the game data was missing but because
    nothing had ever asked for it. Loading all seven up front for every
    registered table would be seven reads per table at startup to serve the
    one language most people never leave.

    Returns whether the records are now available. A failure leaves the
    store untouched rather than caching an empty list, so switching away
    and back retries instead of showing a permanently empty page.
    """
    if not language:
        return False
    store = getattr(state, store_name, None)
    if store is None:
        store = {}
        setattr(state, store_name, store)
    if store.get(language):
        return True
    if getattr(state, "nxd_sqlite_path", None) is None:
        return False
    key = _registry_key_for_store(store_name)
    if key is None:
        return False
    from ... import nxd_data
    try:
        store[language] = nxd_data.read_nxd_table(
            state.nxd_sqlite_path, key, language)
    except Exception:                                         # noqa: BLE001
        # Not cached as empty - see the docstring. A language whose table is
        # genuinely absent from this conversion should be retried, because
        # the user may convert a fuller database and come back.
        return False
    return bool(store.get(language))


# The one label for "copy this record's non-text fields into the other six
# languages", used by every per-language tab.
#
# It lives here rather than being typed into each page because the pages
# drifted: Items had one button, Abilities and Poaching had two, and the
# second one ("Copy shared fields for every edit") did a different and much
# larger thing under a name that read like a rewording of the first.
#
# "Shared fields" was the engine's own term and accurate - those fields
# genuinely hold one value across every language table - but it described
# the data model rather than the action, and nothing on screen said which
# fields were the shared ones. What a user needs to know before pressing it
# is where the values go; what they need to know after is that their names
# were left alone. So the label carries the first and `COPY_LANGUAGES_NOTE`
# carries the second.
COPY_LANGUAGES_LABEL = "Copy to other languages"
COPY_LANGUAGES_NOTE = (
    "Copies everything except text. Names and descriptions are left alone - "
    "those need translating.")


def page_intro(text: str, trailing: QWidget | None = None) -> QHBoxLayout:
    """
    An editing tab's first row: its one-line description.

    The ten tabs each open-coded a heading and a blurb, which is how "Edit
    Game Data" ended up as the heading of all ten. The heading has moved to
    the shell, onto the view toggles' line, and the language controls with
    it - so what is left here is the description, and it is the same shape
    on every tab.

    `trailing` is the language picker and Copy button on the three tabs
    that have them. They sit on this line rather than one of their own: a
    row holding only right-aligned controls leaves a wide empty band, which
    is the thing moving the heading was meant to get rid of.

    They are aligned to the TOP so a description that wraps on a narrow
    window drops its second line underneath itself instead of dragging the
    controls down the page.

    The description carries `role="intro"`, not `role="muted"`, purely for
    the `min-height` that role has. Those controls are taller than a line
    of text, so without a floor the row was 30px on the three tabs with
    them and 17px on the seven without - and everything below the row sat
    at a different height depending on which tab you were on. The floor
    makes the description the tallest thing in the row everywhere, so the
    controls cost nothing and can move nothing.
    """
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(12)
    blurb = QLabel(text)
    blurb.setProperty("role", "intro")
    blurb.setWordWrap(True)
    # The floor above was not enough on its own, and this is the CEILING.
    #
    # A tab with controls gives its description ~250px less width, so the
    # same sentence wraps to two lines there and one line elsewhere. The
    # label then rendered 32px instead of 30 and everything below it sat
    # 2px lower than on the tabs without controls - which is what
    # test_qt_app's "a language picker does not move the line under it"
    # measures.
    #
    # Trimming the sentence was the first fix and it was the wrong one: it
    # made every future page's DESCRIPTION LENGTH load-bearing, tuned to
    # four window widths, with too long and too short both failing. Job
    # Commands could not be phrased usefully inside the limit at all.
    #
    # Capping the height costs nothing that was not already lost - at 1100
    # these labels ask for 48px and are given 32, so they were clipping on
    # both kinds of tab before this. Now they clip identically, the row is
    # the same height everywhere, and copy can be written for readers.
    _IntroHeightCap(blurb)
    row.addWidget(blurb, 1, Qt.AlignTop)
    if trailing is not None:
        row.addWidget(trailing, 0, Qt.AlignTop)
    return row


class _IntroHeightCap(QObject):
    """
    Pins a description label to the height its `role="intro"` floor gives
    it, once the theme that sets that floor has been applied.

    An event filter rather than a `setFixedHeight` call at build time,
    because `min-height` arrives from the stylesheet and is 0 while the
    page is being constructed - the same "sizeHint() in __init__ is
    pre-theme" trap that got button sizing wrong once already.
    """

    def __init__(self, label):
        super().__init__(label)
        self._label = label
        label.installEventFilter(self)

    def eventFilter(self, watched, event):                    # noqa: N802
        if watched is self._label and event.type() in (
                QEvent.Polish, QEvent.Show, QEvent.Resize):
            floor = self._label.minimumHeight()
            if floor > 0 and self._label.maximumHeight() != floor:
                self._label.setMaximumHeight(floor)
        return False


def set_empty_state(note, has_data: bool, *controls) -> None:
    """
    Shows either the "nothing loaded yet" message or the page's controls.

    Every editing tab has two states and they are mutually exclusive: game
    data is loaded, or it is not. The pages each open-coded that, and each
    of them forgot something different - Encounters left "Move this row to:
    [0] / [0] [Move] [Undo move]" sitting at the bottom of an otherwise
    empty page, Poaching and Abilities left a language picker and their copy
    buttons live over nothing at all.

    Controls that act on a selection are the ones that go. A disabled button
    says "you can't do this yet"; a button that is enabled, pressable and
    attached to nothing says the tool is broken. Zodi found the Encounters
    one on real hardware, which is where a control operating on an empty
    selection is actually noticed.

    Takes widgets, not layouts, because `QLayout` has no `setVisible` and a
    layout hidden by hiding its children leaves its spacing behind. A page
    with controls spread across a layout wraps them in a container first -
    see `EncountersPage`'s `move_controls`.

    Every page calls this from `refresh_records`, so "what disappears when
    there is no data" is one list in one place rather than five.
    """
    note.setVisible(not has_data)
    for control in controls:
        if control is not None:
            control.setVisible(has_data)


def select_list_row(list_widget, record_id, search=None) -> bool:
    """
    Moves a list to the row carrying `record_id`, and scrolls it into view.

    This is what a jump between tabs needs and what several pages were not
    doing. `AbilitiesPage.select_record` and `JobCommandsPage.select_record`
    both called `load_record` and stopped, so pressing Edit beside a job's
    skillset filled the editor on the right with the correct ability while
    the list on the left stayed wherever it was - usually scrolled to the
    top, on a different ability, with the real one somewhere out of sight
    among five hundred rows. The page looked like it had jumped to the
    wrong record. `TableEditorPage` had no `select_record` at all, so the
    shell fell through to `load_record` and Equip Bonus did the same thing.

    A filter is cleared if it is hiding the target. Otherwise the jump
    silently lands on a row the reader cannot see, which is the same failure
    with an extra step - and leaving a search term in the box that excludes
    the thing just jumped to is its own small lie.

    `setCurrentRow` scrolls on its own, but only far enough to make the row
    visible - so a jump usually parked the record hard against the top or
    bottom edge. `PositionAtCenter` puts it where the eye is already
    looking, with its neighbours around it.
    """
    from PySide6.QtWidgets import QAbstractItemView

    for i in range(list_widget.count()):
        item = list_widget.item(i)
        if item.data(Qt.UserRole) != record_id:
            continue
        if item.isHidden() and search is not None:
            search.clear()
        list_widget.setCurrentRow(i)
        list_widget.scrollToItem(item, QAbstractItemView.PositionAtCenter)
        return True
    return False


def language_order(available=None) -> list:
    """
    The languages a picker offers, in ONE order everywhere.

    `constants.NXD_LANGUAGES` is that order - English first, then the rest
    as the game's own tables are laid out. The pages had drifted into two
    different ones: Items and Encounters used the constant, while Abilities
    and Poaching used `sorted(...)` with "en" moved to the front, which
    gives en, cs, ct, de, fr, ja, ko. Two dropdowns doing the same job in a
    different order is the kind of thing that makes someone doubt they
    clicked what they thought they clicked.

    `available` filters to the languages a page actually has files for, so
    unifying the ORDER does not accidentally start offering a language whose
    table this page cannot read. Anything present in `available` but not in
    the canonical list is appended rather than dropped - a conversion that
    gains a language should show it, not hide it.
    """
    if available is None:
        return list(c.NXD_LANGUAGES)
    have = set(available)
    ordered = [lang for lang in c.NXD_LANGUAGES if lang in have]
    ordered += [lang for lang in sorted(have) if lang not in c.NXD_LANGUAGES]
    return ordered or list(c.NXD_LANGUAGES)


# The order the formats are OFFERED in, which is not the order they are
# stored in and is not alphabetical either.
#
# `sorted(REPLACEMENT_IMAGE_EXTENSIONS)` put `*.bmp *.dds *.gif` at the
# front of the line, which is three formats almost nobody exports before
# the one almost everybody does. This is the order a person is likely to
# have a file in.
_IMAGE_FILTER_ORDER = (".png", ".tga", ".dds", ".jpg", ".jpeg", ".webp",
                       ".bmp", ".gif")


def image_open_filter(extensions) -> str:
    """
    The filter string for "choose a replacement image", in one place.

    Built here rather than at each call site because there are two of them
    - the Textures tab and the icon slots on Items and Abilities - and they
    had drifted: one offered `All files`, the other did not.

    **The `All files` entry is the point of this.** Both Tkinter dialogs
    have always carried one (`gui/step_textures.py`), and a dialog without
    it can only open what its patterns match. Anything the list does not
    name - a `.tif` out of an editor, a file whose extension is missing or
    unusual - is not merely unlisted, it cannot be picked at all, and the
    dialog gives no sign that the file is there. The engine does not care:
    `load_any_image` hands the file to Pillow, which decides by CONTENT,
    and `stage_texture_replacement` writes the target's own format
    whatever came in. So the dialog was the only thing narrowing this.

    Kept as a filter rather than dropped entirely, because listing the
    common formats first is genuinely useful in a folder of mixed files.
    """
    ordered = [e for e in _IMAGE_FILTER_ORDER if e in extensions]
    ordered += [e for e in extensions if e not in ordered]
    patterns = " ".join(f"*{e}" for e in ordered)
    return f"Images ({patterns});;All files (*)"


def item_names_by_id(state) -> dict:
    """
    `item_id -> name`, from the same `item` records the Items tab lists.

    One source, because three pages want it: Treasure Hunter's two
    dropdowns, Equip Bonus's usage index, and Poaching's note beside
    Produces / Unlocks Item. Two of them read it and the third was handed
    it by a caller that never existed - `PoachingPage.set_item_choices` was
    called by the test suite and by nothing in the application, so the note
    beside every id read "not in the item list loaded here" whatever the id
    was.

    Empty until the tables have loaded, which is why the pages refill from
    this on `refresh_records` rather than reading it once at construction.
    """
    found = {}
    for record in (getattr(state, "item_table_records", None) or {}).get(
            "item", []):
        found[record.item_id] = getattr(record, "name", "") or "(unnamed)"
    return found


class TransientNote(QLabel):
    """
    A note that takes up no room until it has something to say.

    An empty `QLabel` still occupies a full row plus the layout's spacing,
    so the copy-feedback line on Abilities and Poaching was reserving a gap
    on every page view for a sentence that appears only after the Copy
    button is pressed. Beside pages that have no such line - Jobs, Job
    Commands, Equip Bonus, Treasure Hunter - that reads as the same page
    laid out differently, which is what it was reported as.

    Hiding on empty rather than fixing a height, because the sentence wraps
    to two lines in some languages and a reserved single-line gap would
    then push the list down when it appeared anyway.
    """

    def __init__(self, parent=None):
        super().__init__("", parent)
        self.setProperty("role", "muted")
        self.setWordWrap(True)
        self.setVisible(False)

    def setText(self, text):                                  # noqa: N802
        super().setText(text)
        self.setVisible(bool(str(text).strip()))


# The columns a name can be in, in the order they are worth trying.
#
# `Name` is not always the one that holds it. In `Item-<lang>` and
# `PoachItem-<lang>`, Japanese, Korean and both Chinese tables leave `Name`
# null for EVERY row and carry the name in `NameSingular` - measured on a
# real 1.5.2 conversion, 261 of 261 items in `Item-ja` and `Item-ko`.
# English and French populate both.
#
# The engine's own `display_name` reads `Name` alone, so those four
# languages listed every item and every carcass as "(unnamed)" and the page
# looked as though nothing had loaded.
NAME_FIELDS = nxd_data.NAME_FIELDS


def record_name(record) -> str:
    """
    The record's name from whichever column actually holds it.

    Defers to the engine, which now knows the same thing - so the two
    interfaces cannot disagree about what an item is called, and the
    Tkinter tabs got the fix at the same time. This wrapper stays because
    the pages hold RECORDS and the engine's helper takes the values dict.
    """
    return nxd_data.record_name(getattr(record, "values", None) or {})


def record_display_name(record, width: int = 3) -> str:
    """
    `NNN - Name`, falling back through the name columns.

    `nxd_data.display_name` now does the same thing for records that
    carry a key, so most callers can use that directly; this stays for the
    Items page, whose list mixes records keyed on `key` with XML-side ones
    keyed on `item_id`.
    """
    name = record_name(record)
    key = getattr(record, "key", None)
    if key is None:
        key = getattr(record, "item_id", 0)
    return f"{int(key):0{width}d} - {name or '(unnamed)'}"
