"""
Edit Game Data / Textures.

Browse the game's textures and swap any of them for your own image. The
real unpacked game has 10,011 of them, which is why this page is a model
and a view rather than a widget per file.

Three hard-won behaviours from the Tkinter tab are carried over, each of
which cost a bug report:

- **The preview cache is keyed on the full path, not the filename.** The
  game's `foo.tex` and a mod's `foo.tex` are different images; keyed on the
  bare name they collided and a replacement preview showed the game's
  picture. That fix lives in `texture_data`, and this page must not
  reintroduce the problem by caching anything of its own by name.
- **Face textures get the seam fix.** `is_face_texture` decides, not the
  page, and the result is a deliberate part of the export rather than a
  display nicety.
- **A replacement is visible in the tree.** A mod's contents should be
  findable without remembering what you changed.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QSortFilterProxyModel, Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMenu, QPushButton,
    QSizePolicy, QSplitter, QTreeView, QVBoxLayout, QWidget,
)

from ... import paths
from ... import texture_data as td
from ..models.texture_tree import TextureTreeModel
from ..widgets import actions
from ..widgets.marked_tree import MarkedTreeView
from ..workers import Worker, run_in_thread

#: The file tree's width on first show; the editor gets the rest. Measured
#: against the real game listing with the tree's own font: 99% of texture
#: rows need 370px or less (the widest, deep in ui/, 471).
TEXTURE_TREE_WIDTH = 420


class TreePaneSizer(QObject):
    """
    Gives a splitter's first pane - the file tree - a set width the first
    time the splitter has a real width, and everything else to the editor.

    Both file pages gave the tree 60% (`setSizes([3000, 2000])`): at 1080p,
    over 950px for names that need 340 (Sounds) or 370 (textures), while
    the editor beside it went without. Reported with screenshots.
    `setSizes` is proportional until the splitter is laid out, which is why
    this waits for a real width. After that the divider is the reader's:
    this never moves it again.
    """

    def __init__(self, splitter, width: int):
        super().__init__(splitter)
        self._width = width
        self._done = False
        splitter.installEventFilter(self)

    def eventFilter(self, watched, event):                       # noqa: N802
        if (not self._done and event.type() == QEvent.Resize
                and watched.width() > self._width * 2):
            self._done = True
            watched.setSizes([self._width,
                              watched.width() - self._width - watched.handleWidth()])
        return False


class TexturePathFilter(QSortFilterProxyModel):
    """
    Matches on the whole relative path, and keeps a match's ancestors.

    Filtering a tree on the leaf alone hides the folders above a match, so
    the match itself disappears with them. Qt has
    `setRecursiveFilteringEnabled` for exactly this; it is set here rather
    than hand-rolled, which is one of the hand-written search paths the Qt
    rewrite was meant to delete.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFilterRole(Qt.UserRole)
        self.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.setRecursiveFilteringEnabled(True)


# The FLOOR for a preview panel, not the ceiling.
#
# Two panels plus spacing have to fit the editor pane, which is about 430px
# wide at the 1100 minimum - 260 each did not, and the replacement ran off
# the right edge. So 190 is what a panel is guaranteed; `PreviewView` grows
# it to whatever the pane actually has.
#
# It used to be a fixed size, which meant a 2048x2048 map background was
# drawn at 190px on a 2560px monitor with most of the pane empty beside it.
# Growing the panel does NOT mean growing the image past its own size - see
# `PreviewView.set_native`.
PREVIEW_SIZE = 190

# ...and the ceiling. Past this a preview stops being a preview and the
# buttons under it end up a long way from the thing they act on.
PREVIEW_MAX = 560


class PreviewView(QLabel):
    """
    A texture preview that fills the space it is given, but never magnifies.

    Shrinking a 2048px map background to fit is necessary; magnifying a
    56x56 icon is not, and the game never does it either - a blown-up icon
    is a blurry lie about what the texture looks like. So the PANEL grows
    with the window and the IMAGE is drawn at its native size or smaller,
    whichever is less.

    The native pixmap is kept, because rescaling a previously-scaled copy
    loses a little more each time the window is resized.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._native = QPixmap()
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(PREVIEW_SIZE, PREVIEW_SIZE)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_native(self, pixmap) -> None:
        self._native = pixmap or QPixmap()
        self._rescale()

    def clear_native(self, message: str = "") -> None:
        self._native = QPixmap()
        self.setPixmap(QPixmap())
        self.setText(message)

    def resizeEvent(self, event):                             # noqa: N802
        super().resizeEvent(event)
        self._rescale()

    def _rescale(self) -> None:
        if self._native.isNull():
            return
        limit = max(PREVIEW_SIZE, min(self.width(), self.height(), PREVIEW_MAX))
        pixmap = self._native
        if pixmap.width() > limit or pixmap.height() > limit:
            pixmap = pixmap.scaled(limit, limit, Qt.KeepAspectRatio,
                                   Qt.SmoothTransformation)
        self.setText("")
        self.setPixmap(pixmap)


def fit_for_preview(image, limit: int = PREVIEW_MAX):
    """
    Shrinks a decoded texture to the largest size a panel can ever show it.

    **This is a memory fix, not a cosmetic one.** A `.tex` is where the
    game keeps its big textures, and one 4096x4096 decodes to 64MB of RGBA
    - which is then copied several times over on its way to the screen:
    `convert("RGBA")` copies, `tobytes()` copies, and `QPixmap.fromImage`
    copies again. Measured, one such preview takes peak RSS from 130MB to
    370MB. Scroll quickly and several are alive at once, because the panel
    still holds the previous pixmap while the next decode lands.

    When that allocation fails, Qt does not raise - the process goes away
    with no traceback and no dialog. Reported exactly that way: silent, and
    only on `.tex`. A `.tga` in this game is a small UI image, so the same
    code path never gets near the limit.

    `PreviewView` never magnifies - it draws at native size or smaller - so
    anything above `PREVIEW_MAX` was decoded, copied and carried around only
    to be thrown away at draw time. A 4096 texture shrinks by about 53x
    here, and what reaches the screen is identical.

    The image's TRUE size is read before this is called, so the panel still
    reports the real dimensions rather than the shrunken ones.
    """
    width, height = image.size
    if width <= limit and height <= limit:
        return image
    from PIL import Image as _Image

    shrunk = image.copy()
    shrunk.thumbnail((limit, limit), _Image.LANCZOS)
    return shrunk


class PreviewWorker(Worker):
    """
    Loads the current texture and its pending replacement, for display.

    On a thread because `.tex` shells out to FF16Tools' tex-conv, which
    takes long enough to stall the tree if it ran on the GUI side. `.tga`
    is pure Pillow and would be fine either way; going through the same
    path for both keeps one code path rather than two.

    Each side is loaded independently and failures are returned rather than
    raised: one unreadable image should cost that panel, not the other, and
    "couldn't read this" is a more useful thing to draw than a blank box.
    """

    def __init__(self, token, source_path, replacement_path, cli_path,
                 cache_dir):
        super().__init__()
        # Which selection asked for this. Carried through the result rather
        # than captured in a lambda: `run_in_thread` requires bound QObject
        # methods, because a lambda would be run on the worker thread.
        self.token = token
        self.source_path = source_path
        self.replacement_path = replacement_path
        self.cli_path = cli_path
        self.cache_dir = cache_dir

    def run(self):
        result = {"token": self.token,
                  "current": None, "current_error": "",
                  "replacement": None, "replacement_error": "",
                  "size": None}
        if self.source_path is not None:
            try:
                image = td.load_game_texture_preview(
                    Path(self.source_path), self.cli_path, self.cache_dir)
                # The true size first, then the shrink. The panel reports
                # what the texture IS, not what was carried to the screen.
                result["size"] = image.size
                result["current"] = fit_for_preview(image)
            except Exception as exc:                          # noqa: BLE001
                result["current_error"] = str(exc)
        if self.replacement_path is not None:
            try:
                # `load_replacement_preview`, not `load_any_image`.
                #
                # A staged replacement is USUALLY a plain image the reader
                # picked, and Pillow reads those. It is not always: opening
                # a mod recovers the finished game files the mod ships, and
                # for a `.tex` target that is a `.tex`. Pillow cannot open
                # one, so the call raised and the Replacement (pending)
                # panel showed a decode error - on every texture of every
                # opened mod that replaces a `.tex`, which is most of them.
                #
                # The engine already had the dispatch: this function sends
                # `.tex` through `load_game_texture_preview` (which shells
                # out to FF16Tools) and everything else through Pillow. The
                # Tkinter tab has always called it. This page reached past
                # it to the narrower of the two, which is the same shape as
                # every other "one source where the engine has several"
                # fault in this rewrite.
                image = td.load_replacement_preview(
                    Path(self.replacement_path), self.cli_path, self.cache_dir)
                # Previewed as it will be WRITTEN, not as it was picked.
                #
                # A face texture gets the seam fix on export, so a preview
                # without it is showing something the mod will not contain
                # - and the seam is the whole reason the fix exists, so it
                # is exactly the thing a reader is checking for. Tkinter
                # does this; this page did not.
                if td.is_face_texture(str(self.token)):
                    image, _ = td.apply_seam_fix(image)
                # After the seam fix, which works on edge pixels and has to
                # see the image at full size to be the fix it claims to be.
                result["replacement"] = fit_for_preview(image)
            except Exception as exc:                          # noqa: BLE001
                result["replacement_error"] = str(exc)
        return result


#: How long the page waits for the selection to stop moving before it
#: decodes a preview.
#:
#: Sized against the thing that causes the crash rather than picked. A held
#: key repeats at a rate the person sets: on Windows the range is roughly
#: 2.5 to 31 repeats a second, an interval of 400ms down to 32ms. The
#: dangerous end is the fast one - at 31/sec, two seconds on the Down arrow
#: is 62 selection changes, and before this each was a thread and possibly
#: an FF16Tools subprocess.
#:
#: 150ms coalesces everything from 31/sec down to about 6.7/sec, which is
#: the whole range that can outrun a decode. Below that a person is
#: generating fewer than seven previews a second by hand and each has room
#: to finish. It is also short enough that a single deliberate click still
#: feels immediate - the placeholders go up with no delay at all, so what
#: waits is the picture, not the page.
PREVIEW_DEBOUNCE_MS = 150


class TexturesPage(QWidget):
    edits_changed = Signal()

    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state
        self.current_node = None

        # Holding Down on a long list used to kill the application.
        #
        # Every selection change started a new `PreviewWorker` on a new
        # `QThread`, each of which may shell out to FF16Tools to decode a
        # `.tex`. A held key fires selection changes at the keyboard repeat
        # rate, so that spawns threads and subprocesses without bound.
        #
        # The stale-result guard `_preview_token` did not help: it drops the
        # RESULT after the work is done, so it neither cancels the work nor
        # stops it starting.
        #
        # So the decode waits for the selection to stop moving, and refuses
        # to start at all for a token that has already been superseded. The
        # placeholders still go up immediately, so the page does not look
        # frozen while you scroll.
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.timeout.connect(self._start_pending_preview)
        self._pending_preview = None
        #: True while a decode is on a thread. One at a time, always.
        self._preview_busy = False
        #: How many decodes have actually been STARTED. Counted because
        #: "it did not crash this time" is not a measurement - see
        #: `test_qt_textures`.
        self.previews_started = 0

        self.model = TextureTreeModel(edits=self.state.texture_edits)
        self.proxy = TexturePathFilter()
        self.proxy.setSourceModel(self.model)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 10, 24, 20)
        outer.setSpacing(10)

        outer.addLayout(actions.page_intro(
            "Beware .tga textures can only be replaced with .tga files, "
            "while .tex textures accept .dds, .png, .jpg, .gif, .bmp, .tga "
            "or .webp."))

        self.counter = QLabel("")
        self.counter.setProperty("role", "ok")
        outer.addWidget(self.counter)

        # Side by side: browser left, editor right.
        #
        # This was briefly stacked - previews and buttons across the top,
        # browser underneath - and reverted at Zodi's request after seeing
        # it on real hardware. The empty space that prompted the experiment
        # was mostly the preview upscaling a 56x56 icon to fill its panel,
        # and that is fixed separately.
        split = QSplitter(Qt.Horizontal)
        split.setHandleWidth(14)

        left = QVBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search by name or folder")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._on_filter)
        left.addWidget(self.search)

        self.tree = MarkedTreeView()
        self.tree.setModel(self.proxy)
        self.tree.setUniformRowHeights(True)      # skip measuring 10,011 rows
        self.tree.setAlternatingRowColors(True)
        self.tree.setMinimumWidth(280)
        self.tree.setColumnWidth(0, 300)
        self.tree.selectionModel().currentChanged.connect(self._on_selection)
        # Right-click does what the three buttons do.
        #
        # The buttons are across the page from the tree, so replacing a run
        # of textures means crossing back and forth for every one. The menu
        # acts on the row under the pointer, which it selects first - acting
        # on a row you right-clicked while a different one is selected is
        # how you replace the wrong file.
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        left.addWidget(self.tree, 1)

        # Shown instead of an empty tree before the game has been unpacked.
        # An empty list reads as a broken tab; this says what to do about it.
        self.empty_note = QLabel(
            "No game files yet.\n\nGo to General Setup and either unpack your "
            "game, or point at a folder you have already unpacked. The "
            "textures will appear here.")
        self.empty_note.setProperty("role", "muted")
        self.empty_note.setWordWrap(True)
        self.empty_note.setAlignment(Qt.AlignTop)
        left.addWidget(self.empty_note, 1)
        right = QVBoxLayout()
        self.selected_label = QLabel("Select a texture")
        self.selected_label.setStyleSheet("font-weight: 600; font-size: 12pt;")
        self.selected_label.setWordWrap(True)
        right.addWidget(self.selected_label)

        #: Set when a replacement is refused for being the wrong kind, so a
        #: check can see WHY rather than only that nothing happened.
        self.refusal = ""
        self.detail = QLabel("")
        self.detail.setProperty("role", "muted")
        self.detail.setWordWrap(True)
        right.addWidget(self.detail)

        # Current and pending replacement, side by side.
        #
        # The page had no preview at all - a texture browser that shows
        # filenames and asks you to remember what each one looks like. The
        # Tkinter tab draws both, which is the only way to tell whether the
        # replacement you staged is the one you meant.
        previews = QHBoxLayout()
        previews.setSpacing(14)
        self.preview_panels = {}
        for key, title in (("current", "Current"),
                           ("replacement", "Replacement (pending)")):
            panel = QVBoxLayout()
            heading = QLabel(title)
            heading.setProperty("role", "muted")
            panel.addWidget(heading)
            view = PreviewView()
            view.setProperty("role", "preview")
            panel.addWidget(view, 1)
            previews.addLayout(panel, 1)
            self.preview_panels[key] = view
        # No trailing stretch. The two panels share the width between them
        # now; a spacer here would take it back and leave them at their
        # minimum however wide the window was.
        right.addLayout(previews, 1)

        # Stacked in a column, not a row.
        #
        # Two buttons in a row needed 403px and the right-hand pane gets
        # about 285px at the minimum window size, so the layout shrank them
        # below their own minimum widths and clipped both labels. A column
        # cannot run out of width. They were briefly a row while the page
        # was stacked and the editor had the full width; with the side-by-
        # side split back, so is this.
        buttons = QVBoxLayout()
        # Capped. Stacked in a column and left to fill, these ran the whole
        # width of the editor pane - on a 2560px monitor that is a 780px
        # "Remove replacement" button, which Zodi asked specifically not to
        # end up with. The floor still comes from `sizeHint`, so they cannot
        # clip at the 1100 minimum either.
        button_width = 360
        # Minimum widths from sizeHint, not from the layout's leftovers.
        # This is the fifth clipped control in this project's history and
        # the pattern is always the same: a button left to take whatever
        # space remains gets less than its own text needs.
        self.replace_button = QPushButton("Choose a replacement image...")
        self.replace_button.setMinimumWidth(
            self.replace_button.sizeHint().width() + 8)
        self.replace_button.setMaximumWidth(button_width)
        self.replace_button.setEnabled(False)
        self.replace_button.clicked.connect(self.choose_replacement)
        buttons.addWidget(self.replace_button)
        self.clear_button = QPushButton("Remove replacement")
        self.clear_button.setMinimumWidth(
            self.clear_button.sizeHint().width() + 8)
        self.clear_button.setMaximumWidth(button_width)
        self.clear_button.setEnabled(False)
        self.clear_button.clicked.connect(self.clear_replacement)
        buttons.addWidget(self.clear_button)

        self.export_button = QPushButton("Export this texture as PNG...")
        self.export_button.setMinimumWidth(
            self.export_button.sizeHint().width() + 8)
        self.export_button.setMaximumWidth(button_width)
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self.export_as_png)
        buttons.addWidget(self.export_button)
        right.addLayout(buttons)
        right.addStretch(1)

        # The tree gets two thirds. File names here run long
        # ("gt_2_map001_watersurface_02.tga") and the right-hand pane is a
        # label, two previews and three buttons, so an even split spent half
        # the width on whitespace and truncated the thing being chosen.
        # A draggable divider, not a fixed 2:1.
        #
        # File names here are long but not 900px long, so on a 2560px
        # monitor a fixed two-thirds left the browser mostly empty while the
        # previews next to it stayed small. Which side wants the width
        # depends on what you are doing - hunting for a file, or looking at
        # one - so the split is the reader's to set.
        left_holder = QWidget()
        left_holder.setLayout(left)
        right_holder = QWidget()
        right_holder.setLayout(right)
        split.addWidget(left_holder)
        split.addWidget(right_holder)
        split.setChildrenCollapsible(False)
        # The tree gets what its names need, the previews everything else,
        # and window resizes go to the previews.
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        self._tree_sizer = TreePaneSizer(split, TEXTURE_TREE_WIDTH)

        outer.addWidget(split, 1)
        self.refresh_tree()

    # -- tree ------------------------------------------------------------------

    def refresh_tree(self) -> None:
        tree = self._ensure_tree()
        self.model.set_root(tree)
        # Re-read the edit store, because it may be a DIFFERENT DICT now.
        #
        # `clear_opened_mod_content` does `self.texture_edits = {}` - a
        # rebind, not a clear - so opening a mod leaves the model holding a
        # reference to the previous, now orphaned dict. Setup then fills the
        # new one, and the tree marks nothing: no green rows, no folder
        # counts, with a mod's replacements plainly listed on the right.
        #
        # This is why the marking looked correct in testing and wrong on
        # real hardware. Setting `texture_edits` before the page is built
        # keeps the model's reference live; opening a mod does not, and
        # opening a mod is the case that matters.
        self.model.set_edits(self.state.texture_edits)
        self.empty_note.setVisible(tree is None)
        self.tree.setVisible(tree is not None)
        self.search.setEnabled(tree is not None)
        self._update_counter()

    def _ensure_tree(self):
        """
        The scanned tree, rebuilding it if something cleared it.

        `clear_opened_mod_content` sets `texture_tree` to None on purpose -
        its own comment says it does so "to force the Textures and Sounds
        tabs to rescan rather than show the previous mod's staged entries".
        The Tkinter tab does that rescan lazily, right here
        (`gui/step_textures.py`, `state.texture_tree is None`).

        This page never did. So opening a mod cleared the tree and nothing
        rebuilt it, and the tab reported "No game files yet" with the game
        sitting unpacked on disk. The state was correct; the page just
        treated a request to rescan as an answer.
        """
        tree = getattr(self.state, "texture_tree", None)
        unpacked = getattr(self.state, "nxd_unpack_dir", None)
        if tree is None and unpacked:
            try:
                tree = td.scan_texture_tree(Path(unpacked))
            except Exception:                                 # noqa: BLE001
                # Left as None: the empty note is a better answer than a
                # half-scanned tree, and the folder may have gone away.
                return None
            self.state.texture_tree = tree
        return tree

    def _on_filter(self, text: str) -> None:
        self.proxy.setFilterFixedString(text)
        if text.strip():
            # Expanding on a filtered tree is cheap because only matches
            # remain; on the unfiltered 10,011 it would not be, which is why
            # this happens only when there is something to show.
            self.tree.expandAll()
        else:
            self.tree.collapseAll()

    def select_record(self, relative_path) -> bool:
        """
        Selects a texture by its relative path - what a jump from another
        tab arrives with.

        Named `select_record` because that is the first method the shell's
        `open_tab` looks for. The shell deliberately knows nothing about
        what a page's records are, so a page that wants to be jumped to
        answers to that name; a texture's "record id" is its path.
        """
        index = self.model.index_for_path(str(relative_path))
        if not index.isValid():
            return False
        mapped = self.proxy.mapFromSource(index)
        if not mapped.isValid():
            # Hidden by the current filter. Cleared rather than reported as
            # a failure - the file exists and the user asked for it, so the
            # filter is the thing that should give way.
            self.search.clear()
            mapped = self.proxy.mapFromSource(index)
            if not mapped.isValid():
                return False
        self.tree.setCurrentIndex(mapped)
        self.tree.scrollTo(mapped)
        return True

    def _on_selection(self, current, _previous) -> None:
        node = self.model.node_at(current) if current.isValid() else None
        self.current_node = node if node is not None and node.is_file else None
        self._refresh_detail()

    def _refresh_detail(self) -> None:
        node = self.current_node
        if node is None:
            self.selected_label.setText("Select a texture")
            self.detail.setText("")
            self.replace_button.setEnabled(False)
            self.clear_button.setEnabled(False)
            self.export_button.setEnabled(False)
            self._preview_token = None
            for key in getattr(self, "preview_panels", {}):
                self._set_preview(key, None, "")
            return

        self.selected_label.setText(node.name)
        replacement = self.state.texture_edits.get(node.relative_path)
        lines = [node.relative_path]
        if td.is_face_texture(node.relative_path):
            lines.append(
                "This is a face texture, so the edges get a seam fix on export "
                "- without it the game draws a dark outline around the portrait.")
        if replacement:
            # A dict now, not a bare path - printing it raw would show
            # `{'source_path': PosixPath('...'), 'is_face_texture': False}`.
            source = replacement.get("source_path", "")
            lines.append(
                f"Replaced with: {Path(source).name}"
                + ("  (recovered from the opened mod, kept as-is)"
                   if replacement.get("already_staged") else ""))
        self.detail.setText("\n".join(lines))
        self.replace_button.setEnabled(True)
        self.clear_button.setEnabled(bool(replacement))
        self.export_button.setEnabled(True)
        self._load_previews(node, replacement)

    def _show_context_menu(self, point) -> None:
        index = self.tree.indexAt(point)
        if not index.isValid():
            return
        node = self.model.node_at(index)
        # Folders have nothing to replace. A menu of three greyed-out items
        # says less than no menu at all.
        if node is None or not getattr(node, "is_file", False):
            return
        # Select it first, so the menu and the panel on the right are
        # talking about the same file.
        self.tree.setCurrentIndex(index)

        menu = QMenu(self.tree)
        replace = menu.addAction("Replace image...")
        remove = menu.addAction("Remove replacement")
        # Enabled state mirrors the buttons: there is nothing to remove
        # until something has been staged.
        remove.setEnabled(node.relative_path in self.state.texture_edits)
        menu.addSeparator()
        export = menu.addAction("Export as PNG...")

        chosen = menu.exec(self.tree.viewport().mapToGlobal(point))
        if chosen is replace:
            self.choose_replacement()
        elif chosen is remove:
            self.clear_replacement()
        elif chosen is export:
            self.export_as_png()

    # -- previews ---------------------------------------------------------------

    def _set_preview(self, key: str, image=None, message: str = "") -> None:
        view = self.preview_panels[key]
        if image is None:
            view.clear_native(message)
            return
        # Through raw RGBA bytes rather than a temporary file. `tobytes()`
        # can be short by a scanline's padding for odd widths, so the stride
        # is passed explicitly - 4 bytes per pixel.
        rgba = image.convert("RGBA")
        width, height = rgba.size
        # The buffer is NAMED, and the QImage is copied before it goes.
        #
        # `QImage(bytes, ...)` does not copy - it borrows. Passing
        # `rgba.tobytes(...)` straight into the call makes the only
        # reference to that buffer a temporary with no name, and the whole
        # arrangement then rests on shiboken choosing to keep it alive.
        # Probing says PySide6 6.11 does, so this is not a live bug today;
        # it is undocumented behaviour holding up a 1MB borrow, and the
        # failure if it ever stops is not an exception. A 512x512 RGBA
        # buffer is over glibc's mmap threshold, so freeing it UNMAPS the
        # page and reading it afterwards is SIGBUS - a hard crash with no
        # Python traceback, intermittent, and dependent on allocator timing.
        #
        # Naming the buffer and copying the image costs one memcpy per
        # preview, on a path that has just decoded an image from disk.
        buffer = rgba.tobytes("raw", "RGBA")
        expected = width * height * 4
        if len(buffer) < expected:
            # Cannot happen for "raw"/"RGBA", and is checked anyway because
            # the consequence is not a wrong picture. QImage would read
            # `expected` bytes from a shorter buffer and run off the end.
            view.clear_native("This texture could not be decoded.")
            return
        qimage = QImage(buffer, width, height,
                        width * 4, QImage.Format_RGBA8888)
        # Scaled DOWN only, never up.
        #
        # A 56x56 icon blown up to fill a 190px panel is a blurry lie about
        # what the texture looks like - and most UI textures in this game
        # are that small. Shrinking a 2048px map background is necessary;
        # magnifying an icon is not, and the game never does it either.
        # Handed over at native size. `PreviewView` decides how much of the
        # panel to use and re-decides whenever the window is resized, so the
        # scaling is not baked in here.
        view.set_native(QPixmap.fromImage(qimage.copy()))

    def _load_previews(self, node, replacement) -> None:
        root = getattr(self.state, "nxd_unpack_dir", None)
        source = Path(root) / node.relative_path if root else None

        self._set_preview("current", None, "Loading...")
        if replacement:
            self._set_preview("replacement", None, "Loading...")
        else:
            self._set_preview("replacement", None,
                              "Nothing staged for this texture.")

        # Remembered so a result arriving after the selection moved on is
        # dropped rather than drawn over the texture now showing.
        self._preview_token = node.relative_path
        readable = (source is not None and source.exists())
        staged_source = replacement.get("source_path") if replacement else None

        # Nothing to decode on either side - so no thread.
        #
        # Before the game is unpacked there is no source file, and selecting
        # a texture with nothing staged started a worker whose only possible
        # outcome was two empty panels. Harmless in itself, but a process
        # exiting while one is still running aborts with "QThread: Destroyed
        # while thread is still running", which is the crash the thread
        # registry exists to prevent and which turned up here while testing
        # a cross-tab jump.
        if not readable and staged_source is None:
            self._set_preview("current", None,
                              "No game files yet" if source is None
                              else "No file here")
            self._set_preview("replacement", None,
                              "Nothing staged for this texture.")
            self.export_button.setEnabled(False)
            # Nothing queued either, or a decode armed by the PREVIOUS
            # selection would fire against this one's token and be thrown
            # away a moment later - work done for a texture nobody is
            # looking at.
            self._pending_preview = None
            self._preview_timer.stop()
            return

        self._pending_preview = (
            node.relative_path,
            source if readable else None,
            staged_source,
        )
        self._preview_timer.start(PREVIEW_DEBOUNCE_MS)

    def flush_pending_preview(self) -> None:
        """
        Starts a debounced decode now instead of waiting out the interval.

        For tests, which cannot hold a key down and should not sleep. It
        fast-forwards the wait rather than switching the debounce off, so a
        check that uses it is still running the shipped code path.
        """
        if self._preview_timer.isActive():
            self._preview_timer.stop()
            self._start_pending_preview()

    def _start_pending_preview(self) -> None:
        pending = self._pending_preview
        if pending is None:
            return
        # ONE decode at a time. This is the half that actually stops the
        # crash.
        #
        # The debounce delays when a decode STARTS; it does nothing about
        # how many run at once. Pressing Down in bursts - fast, but with
        # gaps longer than the debounce - starts a fresh decode each time,
        # and a `.tex` decode holds a full-size image plus an FF16Tools
        # subprocess. Enough of those in flight together and the process
        # dies. Reported precisely that way: it is the images loading at the
        # same time, not the key repeating.
        #
        # The pending job is left in place rather than dropped, so the
        # texture you land on is still decoded once the current one is
        # done - see `_preview_finished`.
        if self._preview_busy:
            return
        self._pending_preview = None
        token, source, staged_source = pending
        # The second half of the fix, and the one the debounce cannot do on
        # its own: a decode whose selection has already moved on is not
        # started. The old guard threw the RESULT away, which is the
        # expensive half done for nothing.
        if token != getattr(self, "_preview_token", None):
            return
        self.previews_started += 1
        self._preview_busy = True

        worker = PreviewWorker(
            token,
            source,
            staged_source,
            getattr(self.state, "ff16tools_cli_path", None),
            paths.local_data_dir() / "texture_preview_cache")
        # Not `self._thread = ...`. `_RunningThreads` holds every started
        # thread until it has genuinely stopped, and its own docstring names
        # the one-attribute-per-page assignment as the bug it exists to
        # replace: the second job overwrites the first thread's only
        # reference while that thread is still running.
        run_in_thread(
            worker, on_finished=self._previews_ready,
            on_failed=self._previews_failed)

    def _preview_finished(self) -> None:
        """
        Frees the single decode slot and queues whatever is waiting.

        Both completion paths come through here, success and failure alike.
        A failure that did not clear the flag would wedge the page: no
        further preview would ever start, and nothing on screen would say
        why.

        **The next decode is QUEUED, not started here.** This runs inside
        the emission of the finishing worker's `finished` signal, so the
        thread that just did the work has not gone away yet - its `quit()`
        and the registry's `release()` hang off the same signal. Starting a
        new thread from inside that emission makes Qt do thread bookkeeping
        re-entrantly, which is the hazard `_RunningThreads` names in its own
        docstring: "a handler that starts more work".

        Reported from real use as a silent crash while clicking through
        many `.tex` textures without waiting. `.tex` is the only kind that
        has to shell out to FF16Tools, so it is the only kind slow enough
        for a queue to build up behind it - which is what makes this chain
        run over and over. Measured, same seeds, 150 clicks a run:

            synchronous start   2 crashes in 10 runs
            queued start        0 crashes in 10 runs

        A zero-delay timer is enough. It does not slow anything down - the
        decode still begins on the next turn of the event loop - it only
        stops it beginning half-way through the previous one's teardown.
        """
        self._preview_busy = False
        if self._pending_preview is not None:
            QTimer.singleShot(0, self._start_pending_preview)

    def _previews_ready(self, result: dict) -> None:
        self._preview_finished()
        if result.get("token") != getattr(self, "_preview_token", None):
            return
        self._set_preview(
            "current", result["current"],
            result["current_error"] or "No file for this texture.")
        if result["replacement"] is not None or result["replacement_error"]:
            self._set_preview(
                "replacement", result["replacement"],
                result["replacement_error"] or "")
        if result["size"]:
            width, height = result["size"]
            self.detail.setText(
                self.detail.text() + f"\n{width} x {height} px")

    def _previews_failed(self, message: str) -> None:
        self._preview_finished()
        # No token here - `failed` carries only the message. A stale failure
        # can only overwrite an error message with another error message,
        # which is not worth threading a token through for.
        self._set_preview("current", None, message)

    # -- editing ----------------------------------------------------------------

    def choose_replacement(self, _checked=False, path: str | None = None) -> None:
        """
        `path` is for tests, which cannot open a file dialog. In normal use
        it is None and the dialog supplies it.
        """
        if self.current_node is None:
            return
        allowed = td.allowed_replacements(self.current_node.relative_path)
        if path is None:
            path, _ = QFileDialog.getOpenFileName(
                self, "Choose a replacement image", "",
                actions.image_open_filter(allowed))
        if not path:
            return
        # Checked as well as filtered. The dialog's filter is a convenience
        # and can be stepped around by typing a name, and a replacement of
        # the wrong kind is not refused anywhere further down - it produces
        # a mod that builds and a texture that does not appear.
        if Path(path).suffix.lower() not in allowed:
            self.refusal = (
                f"{Path(self.current_node.relative_path).suffix.lower()} "
                f"textures can only be replaced with "
                f"{' or '.join(allowed)} files. "
                f"{Path(path).name} was not used.")
            self.detail.setText(self.refusal)
            return
        self.refusal = ""
        self.set_replacement(self.current_node.relative_path, Path(path))

    def set_replacement(self, relative_path: str, source: Path) -> None:
        """
        Records a replacement in the shape the engine reads.

        This stored `str(source)` - a bare path. Everything else that writes
        `texture_edits` stores a dict (`gui/step_textures.py` when you pick
        an image, `gui/step_setup.py` when one is recovered from an opened
        mod), and `texture_data.stage_texture_replacement` is fed from
        `info["source_path"]` with `info.get("already_staged")` deciding
        whether to re-encode.

        A string satisfies neither, so a texture replaced on this tab could
        not be exported at all. Nothing caught it because the Qt export did
        not stage textures either - two halves of the same feature missing,
        each hiding the other.

        `is_face_texture` is recorded here rather than worked out at export
        time, matching the Tkinter tab: it is a property of the target path,
        and the staging call re-derives it anyway, so this is for anything
        that wants to show it without re-deriving.
        """
        self.state.texture_edits[relative_path] = {
            "source_path": Path(source),
            "is_face_texture": td.is_face_texture(relative_path),
        }
        self._after_change()

    def clear_replacement(self) -> None:
        if self.current_node is None:
            return
        self.state.texture_edits.pop(self.current_node.relative_path, None)
        self._after_change()

    def export_as_png(self, _checked=False, path: str | None = None) -> None:
        """
        Writes the selected texture out as a PNG, for editing elsewhere.

        Goes through `load_game_texture_preview`, not `load_any_image`.
        That is the whole of the bug this fixes: the source here is always
        an EXISTING game file, and `load_any_image`'s own docstring says it
        is "for a REPLACEMENT image the user provides, not for existing game
        .tex files - those need load_game_texture_preview". Pillow cannot
        read a `.tex` at all, so exporting one failed with

            Couldn't export: cannot identify image file '...c01_uitx.tex'

        The Items page never had the fault because `texture_slot.export_png`
        exports the already-decoded preview rather than re-reading the file.

        `.tga` still needs nothing - `load_game_texture_preview` forwards it
        straight to `load_any_image` - and `.tex` needs FF16Tools, which is
        why the CLI path and the preview cache are passed in. That is the
        behaviour the docstring above already CLAIMED and the code did not
        implement; the claim is now true.
        """
        if self.current_node is None:
            return
        source = self._source_path()
        if source is None:
            self.detail.setText(
                self.detail.text()
                + "\n\nCan't export: the unpacked game folder isn't set.")
            return
        if path is None:
            suggested = Path(self.current_node.name).with_suffix(".png").name
            path, _ = QFileDialog.getSaveFileName(
                self, "Export texture as PNG", suggested, "PNG images (*.png)")
        if not path:
            return
        try:
            image = td.load_game_texture_preview(
                Path(source),
                getattr(self.state, "ff16tools_cli_path", None),
                paths.local_data_dir() / "texture_preview_cache")
            td.save_image_as_png(image, Path(path))
        except Exception as exc:                              # noqa: BLE001
            self.detail.setText(
                self.detail.text() + f"\n\nCouldn't export: {exc}")
            return
        self.detail.setText(self.detail.text() + f"\n\nExported to {path}")

    def _source_path(self):
        root = getattr(self.state, "nxd_unpack_dir", None)
        if root is None or self.current_node is None:
            return None
        return Path(root) / self.current_node.relative_path

    def _after_change(self) -> None:
        # Named, so the model repaints this file and the folders above it
        # rather than resetting the whole tree and collapsing it.
        changed = (self.current_node.relative_path
                   if self.current_node is not None else None)
        self.model.set_edits(self.state.texture_edits, changed)
        self._refresh_detail()
        self._update_counter()
        self.edits_changed.emit()

    def _update_counter(self) -> None:
        total = self.model.file_count()
        if not total:
            self.counter.setText("")
            return
        replaced = len(self.state.texture_edits)
        self.counter.setText(
            actions.edit_counter_text(replaced, total, "textures", "replaced"))
