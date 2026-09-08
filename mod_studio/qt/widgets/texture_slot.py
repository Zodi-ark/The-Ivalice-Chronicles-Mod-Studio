"""
One texture, previewed inline on a page that is not the Textures tab.

Items has two of these (an item's art and sprite icons) and Abilities has
one (the shared ability icon sheet). All three are the same thing: a
quality-of-life shortcut so replacing an item's icon does not mean finding
`ui/ffto/icon/equip_item/texture/ei_042_uitx.tex` by hand among ten thousand
files.

**It writes the exact dict the Textures tab writes**, into the exact same
`state.texture_edits`:

    {"source_path": Path(...), "is_face_texture": bool}

Not a bare `Path`. Both the Qt Textures tab and the Qt Sounds tab shipped a
bare string into stores whose staging functions read a dict, and neither was
visible until export was wired up months later - a shape nothing consumes
cannot be caught by anything. So this widget goes through
`replace_with()`/`clear()` rather than letting three pages each assemble the
dict, and a check asserts the shape against
`texture_data.stage_texture_export`'s own expectations.

The actions live on a **context menu on the preview itself** as well as on
buttons, at Zodi's request: clicking the picture is the obvious gesture and
the buttons are the discoverable one, so both exist rather than either
alone.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QImage, QPixmap
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QLabel, QMenu, QMessageBox, QPushButton,
    QVBoxLayout, QWidget,
)

from ... import paths
from ... import texture_data as td
from . import actions
from ..workers import run_in_thread

# Smaller than the Textures tab's 190. These sit beside a form rather than
# in a panel of their own, and an item icon is 56x56 - at 190 the panel was
# mostly empty box.
SLOT_PREVIEW_SIZE = 96


class InlineTextureSlot(QWidget):
    """
    `[current] [staged]` with Replace / Clear / Export / View buttons.

    `set_relative_path()` points it at a texture; everything else follows.
    A slot with no texture on disk still works - the game has 261 item ids
    and rather fewer icon files, and "no file at this path" is a fact worth
    showing rather than an error.
    """

    edits_changed = Signal()
    view_requested = Signal(str)

    def __init__(self, title: str, state, compact: bool = False, parent=None):
        """
        `compact` is the narrow column form from the Items concept sketch:
        the two previews stay, the four buttons go, and the context menu on
        the picture carries every action instead. Four buttons under a
        250px column wrap onto three rows and swallow the space the
        pictures need.
        """
        super().__init__(parent)
        self.compact = compact
        self.state = state
        self.relative_path: str | None = None
        self._preview_token = None
        self._current_image = None
        # What is actually on screen, so re-selecting the same item costs
        # no decode, and a flag for when a staged replacement changed under
        # an unchanged path.
        self._shown_path = None
        self._dirty = False
        self._pending_while_hidden = False
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(200)
        self._debounce.timeout.connect(self._load_previews)

        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(4)

        self.title = QLabel(title)
        self.title.setStyleSheet("font-weight: 600;")
        column.addWidget(self.title)

        panels = QHBoxLayout()
        panels.setSpacing(6 if compact else 8)
        self.current_view = self._make_panel("In the game")
        self.pending_view = self._make_panel("Staged")
        panels.addWidget(self.current_view["box"])
        panels.addWidget(self.pending_view["box"])
        panels.addStretch(1)
        column.addLayout(panels)

        self.status = QLabel("")
        self.status.setProperty("role", "muted")
        self.status.setWordWrap(True)
        column.addWidget(self.status)

        buttons = QHBoxLayout()
        buttons.setSpacing(6)
        self.replace_button = QPushButton("Replace...")
        self.replace_button.clicked.connect(self.choose_replacement)
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear)
        self.export_button = QPushButton("Export as PNG...")
        self.export_button.clicked.connect(self.export_png)
        self.view_button = QPushButton("View in Textures \u2192")
        self.view_button.clicked.connect(self._emit_view)
        self._buttons = (self.replace_button, self.clear_button,
                         self.export_button, self.view_button)
        for button in self._buttons:
            # Width left to Qt. `sizeHint()` here is measured before the
            # theme's padding exists - the stylesheet goes on the
            # QApplication after every page is built - and seven controls
            # have shipped clipped in this project from being sized in
            # __init__.
            buttons.addWidget(button)
        buttons.addStretch(1)
        self.button_row = QWidget()
        self.button_row.setLayout(buttons)
        column.addWidget(self.button_row)
        if compact:
            # Hidden, not omitted - `set_relative_path` and the tests still
            # drive them, and the context menu calls the same methods.
            self.button_row.setVisible(False)

        self.set_relative_path(None)

    def _make_panel(self, caption: str) -> dict:
        box = QFrame()
        box.setFrameShape(QFrame.StyledPanel)
        inner = QVBoxLayout(box)
        inner.setContentsMargins(6, 4, 6, 4)
        inner.setSpacing(2)
        label = QLabel(caption)
        label.setProperty("role", "muted")
        inner.addWidget(label)
        view = QLabel("")
        view.setAlignment(Qt.AlignCenter)
        view.setMinimumSize(SLOT_PREVIEW_SIZE, SLOT_PREVIEW_SIZE)
        # The picture is a control, not decoration - the context menu is the
        # gesture Zodi asked for.
        view.setContextMenuPolicy(Qt.CustomContextMenu)
        view.customContextMenuRequested.connect(
            lambda point, source=view: self._show_menu(source, point))
        inner.addWidget(view)
        return {"box": box, "view": view}

    # -- the context menu ---------------------------------------------------

    def _show_menu(self, source: QWidget, point) -> None:
        """
        Replace / Clear / Export / View, on the preview itself.

        The same four actions as the buttons, deliberately - a context menu
        holding a different set from the visible buttons is a menu nobody
        can predict. `Clear` is disabled with nothing staged and `Export` is
        disabled with nothing to export, so the menu never offers an action
        that would do nothing.
        """
        if self.relative_path is None:
            return
        menu = QMenu(self)
        replace = QAction("Replace...", menu)
        replace.triggered.connect(self.choose_replacement)
        menu.addAction(replace)

        clear = QAction("Clear replacement", menu)
        clear.setEnabled(bool(self.staged()))
        clear.triggered.connect(self.clear)
        menu.addAction(clear)

        export = QAction("Export as PNG...", menu)
        export.setEnabled(self._current_image is not None)
        export.triggered.connect(self.export_png)
        menu.addAction(export)

        menu.addSeparator()
        view = QAction("View in the Textures tab", menu)
        view.triggered.connect(self._emit_view)
        menu.addAction(view)
        menu.exec(source.mapToGlobal(point))

    def _emit_view(self) -> None:
        if self.relative_path:
            self.view_requested.emit(self.relative_path)

    # -- the texture it points at -------------------------------------------

    def set_relative_path(self, relative_path: str | None) -> None:
        """
        Points the slot at a texture. **Pointing it at the one it already
        shows does nothing.**

        Callers re-set the path whenever the record reloads, and a record
        reloads for reasons that have nothing to do with textures - changing
        the Language box being the obvious one, since an item's icons are
        not per-language. Without this guard each of those re-ran the
        preview, and a `.tex` preview runs FF16Tools as a subprocess.

        The guard lives here rather than in the caller because there are
        three callers and they would each have to remember it.
        """
        if relative_path == self.relative_path and not self._dirty:
            return
        self.relative_path = relative_path
        enabled = relative_path is not None
        for button in (self.replace_button, self.export_button,
                       self.view_button):
            button.setEnabled(enabled)
        if relative_path is None:
            self.clear_button.setEnabled(False)
            self.status.setText("No item selected.")
            self._set_preview(self.current_view, None, "")
            self._set_preview(self.pending_view, None, "")
            return
        self.refresh()

    def staged(self) -> dict | None:
        return (self.state.texture_edits or {}).get(self.relative_path)

    def refresh(self) -> None:
        if self.relative_path is None:
            return
        staged = self.staged()
        self.clear_button.setEnabled(bool(staged))
        # The texture's path is NOT shown in compact form.
        #
        # On the Items page it is derived from the item id and never
        # surprising - two long identical-looking paths under two pictures,
        # on a page that already carries a list, a form and a stats table.
        # It stays as the tooltip for anyone who wants it, and the Textures
        # tab shows it properly.
        lines = []
        if not self.compact:
            lines.append(self.relative_path)
        if staged:
            source = staged.get("source_path", "")
            lines.append(
                f"Replaced with: {Path(source).name}"
                + ("  (recovered from the opened mod, kept as-is)"
                   if staged.get("already_staged") else ""))
        self.status.setText("\n".join(lines))
        self.status.setVisible(bool(lines))
        self.setToolTip(self.relative_path or "")
        self._request_previews()

    # -- previews -----------------------------------------------------------

    def _request_previews(self) -> None:
        """
        Asks for a decode shortly, rather than starting one now.

        **A `.tex` decode runs FF16Tools as a subprocess.** On the Textures
        tab that happens when somebody clicks a texture, which is once. Here
        the slot follows the item selection, so holding an arrow key down
        the item list would fire two subprocesses per item - and the list
        auto-selects its first row every time the records reload, which is
        what happens at the end of an unpack.

        So: coalesce. A short timer means a run of selections costs one
        decode for the item actually landed on, and `_shown_path` means
        re-selecting the item already displayed costs none at all.
        """
        if self.relative_path == self._shown_path and not self._dirty:
            return
        self._set_preview(self.current_view, None, "...")
        self._set_preview(self.pending_view, None, "...")
        self._debounce.start()

    def _load_previews(self) -> None:
        from ..pages.textures import PreviewWorker

        if self.relative_path is None:
            return
        # Nothing is decoded while the slot is off screen. The page rebuilds
        # its selection whenever records reload, and doing that work for a
        # tab nobody is looking at is how an unpack ends in a burst of
        # subprocesses.
        if not self.isVisible():
            self._pending_while_hidden = True
            return
        self._pending_while_hidden = False

        staged = self.staged()
        root = getattr(self.state, "nxd_unpack_dir", None)
        source = Path(root) / self.relative_path if root else None
        if source is not None and not source.exists():
            source = None
        replacement = Path(staged["source_path"]) if staged else None
        if replacement is not None and not replacement.exists():
            self._set_preview(self.pending_view, None, "File is missing")
            replacement = None

        self._current_image = None
        self._set_preview(self.current_view, None,
                          "Loading..." if source else
                          ("No game files yet" if root is None
                           else "No file here"))
        if replacement is not None:
            self._set_preview(self.pending_view, None, "Loading...")
        elif not staged:
            self._set_preview(self.pending_view, None, "Nothing staged")

        self._shown_path = self.relative_path
        self._dirty = False

        # Nothing to decode on either side - so no thread.
        if source is None and replacement is None:
            self.export_button.setEnabled(False)
            return

        self._preview_token = self.relative_path
        worker = PreviewWorker(
            self.relative_path, source, replacement,
            getattr(self.state, "ff16tools_cli_path", None),
            paths.local_data_dir() / "texture_preview_cache")
        self._thread = run_in_thread(
            worker, on_finished=self._previews_ready,
            on_failed=self._previews_failed)

    def showEvent(self, event):
        """Decodes what was skipped while the slot was hidden."""
        super().showEvent(event)
        if self._pending_while_hidden or self.relative_path != self._shown_path:
            self._debounce.start()

    def _set_preview(self, panel: dict, image, message: str) -> None:
        view = panel["view"]
        if image is None:
            view.setPixmap(QPixmap())
            view.setText(message)
            return
        rgba = image.convert("RGBA")
        width, height = rgba.size
        qimage = QImage(rgba.tobytes("raw", "RGBA"), width, height,
                        width * 4, QImage.Format_RGBA8888)
        pixmap = QPixmap.fromImage(qimage)
        # Shrunk, never magnified - the Textures tab's rule, and these
        # icons are exactly the 56x56 case that rule was measured on.
        if (pixmap.width() > SLOT_PREVIEW_SIZE
                or pixmap.height() > SLOT_PREVIEW_SIZE):
            pixmap = pixmap.scaled(SLOT_PREVIEW_SIZE, SLOT_PREVIEW_SIZE,
                                   Qt.KeepAspectRatio, Qt.SmoothTransformation)
        view.setText("")
        view.setPixmap(pixmap)

    def _previews_ready(self, result: dict) -> None:
        # A result for a texture the user has already moved on from is
        # dropped rather than drawn over the one now showing.
        if result.get("token") != self._preview_token:
            return
        self._current_image = result.get("current")
        self._set_preview(self.current_view, result.get("current"),
                          result.get("current_error") or "No file here")
        self._set_preview(self.pending_view, result.get("replacement"),
                          result.get("replacement_error") or "Nothing staged")
        self.export_button.setEnabled(self._current_image is not None)

    def _previews_failed(self, message: str) -> None:
        self._set_preview(self.current_view, None, "Preview failed")

    # -- editing ------------------------------------------------------------

    def choose_replacement(self, _checked=False, path: str | None = None) -> None:
        """`path` is for tests; the dialog is what a user sees."""
        if self.relative_path is None:
            return
        if path is None:
            path, _filter = QFileDialog.getOpenFileName(
                self, f"Replacement image for {self.title.text()}", "",
                actions.image_open_filter(td.REPLACEMENT_IMAGE_EXTENSIONS))
        if not path:
            return
        self.replace_with(Path(path))

    def replace_with(self, source: Path) -> None:
        """
        The one place the staged dict is built.

        `is_face_texture` is recorded here rather than at export time, the
        same as the Textures tab: it is a property of the target path, and
        staging re-derives it anyway.
        """
        self.state.texture_edits[self.relative_path] = {
            "source_path": Path(source),
            "is_face_texture": td.is_face_texture(self.relative_path),
        }
        self._dirty = True
        self.refresh()
        self.edits_changed.emit()

    def clear(self) -> None:
        if self.relative_path is None:
            return
        self.state.texture_edits.pop(self.relative_path, None)
        self._dirty = True
        self.refresh()
        self.edits_changed.emit()

    def export_png(self, _checked=False, path: str | None = None) -> None:
        if self._current_image is None:
            return
        if path is None:
            path, _filter = QFileDialog.getSaveFileName(
                self, "Export texture as PNG",
                Path(self.relative_path).stem + ".png",
                "PNG image (*.png);;All files (*)")
        if not path:
            return
        try:
            td.save_image_as_png(self._current_image, Path(path))
            self.status.setText(f"Exported to {path}")
        except Exception as exc:                              # noqa: BLE001
            QMessageBox.critical(self, "Export failed",
                                 f"Couldn't export texture: {exc}")
