"""
Edit Game Data / Sounds.

The real unpacked game holds **14,545** sound archives - a bigger tree than
Textures, and the largest thing in the tool. It reuses the same tree model,
which works unchanged because `SoundTreeNode` and `TextureTreeNode` are the
same shape.

It does NOT reuse the Textures page, and that is deliberate rather than
laziness in the other direction. Items, Equip Bonus and Treasure Hunter
became one page because they genuinely are one thing wearing three names. A
sound archive is not a texture: a `.sab` is a container holding many tracks,
each with its own loop points, and replacing one means unpacking the archive
with AudioMog, swapping a track, and repacking. Forcing that into a page
built around "one file, one image" would make both worse.

Two edit stores, kept separate because the engine keeps them separate:

    sound_edits              {archive: {track index: edit}}  tracks
    sound_file_replacements  {archive: source path}          whole files

**AudioMog is a Windows binary.** Browsing, searching and classifying the
tree all work anywhere. Opening an archive to see its tracks does not, and
the page says so instead of showing an empty track list that looks like an
archive with nothing in it.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QPushButton, QSizePolicy, QSpinBox, QTreeView,
    QSplitter, QVBoxLayout, QWidget
)

from ... import sound_data as sd
from ... import paths
from ..models.texture_tree import TextureTreeModel
from ..widgets.actions import page_intro
from ..widgets.marked_tree import MarkedTreeView
from ..workers import Worker, run_in_thread
from ..pages.textures import TexturePathFilter


class UnpackArchiveWorker(Worker):
    """
    Unpacks one `.sab` so its tracks can be listed.

    This is the ONLY part of sound editing that needs AudioMog. Everything
    after it - listing tracks, reading loop points, exporting, replacing -
    is stdlib WAV work and runs anywhere, which is why it was worth wiring
    even though the unpack itself cannot be tested here.

    Cached: `unpack_sab_cached` reuses a previous extraction, so opening the
    same archive twice does not pay for it twice.
    """

    def __init__(self, exe_path: Path, sab_path: Path, relative_path: str,
                 cache_root: Path):
        super().__init__()
        self.exe_path = exe_path
        self.sab_path = sab_path
        self.relative_path = relative_path
        self.cache_root = cache_root

    def run(self):
        self.log.emit(f"Opening {self.relative_path}...")
        project = sd.unpack_sab_cached(
            self.exe_path, self.sab_path, self.relative_path,
            self.cache_root, line_cb=self.log.emit)
        tracks = sd.list_tracks(project)
        if not tracks:
            raise RuntimeError(
                "AudioMog finished but no tracks were found in there.")
        return tracks


class SoundsPage(QWidget):
    edits_changed = Signal()

    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state
        self.current_node = None
        self.tracks = []
        self.current_track = None
        self._player = None
        self._thread = None

        # The model is shared with Textures because the node types match.
        # What it is told about is this page's own edit store.
        self.model = TextureTreeModel(edits=self._replaced_map())
        # Set by whichever handler changed a file, read by `_after_change`.
        self._changed_path = None
        self.proxy = TexturePathFilter()
        self.proxy.setSourceModel(self.model)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 10, 24, 20)
        outer.setSpacing(10)

        outer.addLayout(page_intro(
            "Music, voice lines and sound effects. Each archive holds several "
            "tracks. Only the ones you replace are written into your mod."))

        self.counter = QLabel("")
        self.counter.setProperty("role", "ok")
        outer.addWidget(self.counter)

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
        self.tree.setUniformRowHeights(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.setMinimumWidth(420)
        self.tree.setColumnWidth(0, 300)
        self.tree.selectionModel().currentChanged.connect(self._on_selection)
        left.addWidget(self.tree, 1)

        self.empty_note = QLabel(
            "No game files yet.\n\nGo to General Setup and either unpack your "
            "game, or point at a folder you have already unpacked. The sound "
            "archives will appear here.")
        self.empty_note.setProperty("role", "muted")
        self.empty_note.setWordWrap(True)
        self.empty_note.setAlignment(Qt.AlignTop)
        left.addWidget(self.empty_note, 1)
        left_holder = QWidget()
        left_holder.setLayout(left)
        split.addWidget(left_holder)

        right = QVBoxLayout()
        self.selected_label = QLabel("Select a sound archive")
        self.selected_label.setStyleSheet("font-weight: 600; font-size: 12pt;")
        self.selected_label.setWordWrap(True)
        right.addWidget(self.selected_label)

        self.detail = QLabel("")
        self.detail.setProperty("role", "muted")
        self.detail.setWordWrap(True)
        right.addWidget(self.detail)

        self.tracks_note = QLabel("")
        self.tracks_note.setProperty("role", "attention")
        self.tracks_note.setWordWrap(True)
        right.addWidget(self.tracks_note)

        # No "Open this archive's tracks" button - selecting an archive
        # opens it. It existed because only the first selection opened
        # anything, so a second archive needed a manual push.

        self.track_list = QListWidget()
        self.track_list.setMaximumHeight(160)
        self.track_list.currentItemChanged.connect(self._on_track_selected)
        self.track_list.setVisible(False)
        right.addWidget(self.track_list)

        self.track_detail = QLabel("")
        self.track_detail.setProperty("role", "muted")
        self.track_detail.setWordWrap(True)
        right.addWidget(self.track_detail)

        actions = QVBoxLayout()
        self.play_button = QPushButton("Play")
        self.play_button.setMinimumWidth(self.play_button.sizeHint().width() + 8)
        self.play_button.setEnabled(False)
        self.play_button.clicked.connect(self.play_track)
        actions.addWidget(self.play_button)

        self.stop_button = QPushButton("Stop")
        self.stop_button.setMinimumWidth(self.stop_button.sizeHint().width() + 8)
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_track)
        actions.addWidget(self.stop_button)

        self.export_button = QPushButton("Export this track as WAV...")
        self.export_button.setMinimumWidth(
            self.export_button.sizeHint().width() + 8)
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self.export_track)
        actions.addWidget(self.export_button)

        self.replace_button = QPushButton("Replace this track...")
        self.replace_button.setMinimumWidth(
            self.replace_button.sizeHint().width() + 8)
        self.replace_button.setEnabled(False)
        self.replace_button.clicked.connect(self.replace_track)
        actions.addWidget(self.replace_button)

        self.clear_track_button = QPushButton("Undo this track's replacement")
        self.clear_track_button.setMinimumWidth(
            self.clear_track_button.sizeHint().width() + 8)
        self.clear_track_button.setEnabled(False)
        self.clear_track_button.clicked.connect(self.clear_track_replacement)
        actions.addWidget(self.clear_track_button)
        actions.addStretch(1)
        right.addLayout(actions)

        # -- loop points, editable -------------------------------------------
        #
        # Qt only ever DISPLAYED these ("Loops from sample 1234 to 5678").
        # Tkinter has had a Loop Points (samples) box with both values and a
        # reset since the feature shipped, and editing them is the whole
        # reason they are interesting: a replacement track almost never
        # wants the original's loop, and music whose loop is wrong either
        # stops or repeats a fragment.
        loop_box = QGroupBox("Loop points (samples)")
        loop_row = QHBoxLayout(loop_box)
        loop_row.addWidget(QLabel("Start:"))
        self.loop_start = QSpinBox()
        self.loop_start.setRange(0, 2_000_000_000)
        self.loop_start.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.loop_start.setFixedWidth(120)
        self.loop_start.valueChanged.connect(self._on_loop_changed)
        loop_row.addWidget(self.loop_start)
        loop_row.addSpacing(12)
        loop_row.addWidget(QLabel("End:"))
        self.loop_end = QSpinBox()
        self.loop_end.setRange(0, 2_000_000_000)
        self.loop_end.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.loop_end.setFixedWidth(120)
        self.loop_end.valueChanged.connect(self._on_loop_changed)
        loop_row.addWidget(self.loop_end)
        self.reset_loop_button = QPushButton("Reset to vanilla")
        # `sizeHint()` here is measured before the theme's padding is
        # applied - the stylesheet goes on the QApplication after every page
        # is built - so a width taken from it is short by whatever the theme
        # adds. The clipping check caught this at 115px against 131 needed.
        # Letting Qt size the button at layout time avoids predicting it.
        self.reset_loop_button.setSizePolicy(
            QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.reset_loop_button.clicked.connect(self.reset_loop_points)
        loop_row.addWidget(self.reset_loop_button)
        loop_row.addStretch(1)
        self.loop_box = loop_box
        right.addWidget(loop_box)
        right.addStretch(1)
        # A draggable divider, like Textures. Which side wants the width
        # depends on whether you are hunting for an archive or working on
        # one, so the split is the reader's to set.
        right_holder = QWidget()
        right_holder.setLayout(right)
        split.addWidget(right_holder)
        split.setChildrenCollapsible(False)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        split.setSizes([3000, 2000])

        outer.addWidget(split, 1)
        self.refresh_tree()

    # -- tree --------------------------------------------------------------------

    def _ensure_tree(self):
        """
        The scanned tree, rebuilding it if something cleared it.

        Same fault as the Textures tab: `clear_opened_mod_content` clears
        this to force a rescan, and this page never rescanned - so opening a
        mod left "No game files yet" with the game unpacked on disk.
        """
        tree = getattr(self.state, "sound_tree", None)
        unpacked = getattr(self.state, "nxd_unpack_dir", None)
        if tree is None and unpacked:
            try:
                tree = sd.scan_sound_tree(Path(unpacked))
            except Exception:                                 # noqa: BLE001
                return None
            self.state.sound_tree = tree
        return tree

    def refresh_tree(self) -> None:
        tree = self._ensure_tree()
        self.model.set_root(tree)
        # Re-read both edit stores. Sounds is worse than Textures here:
        # `_replaced_map()` builds a NEW dict merging `sound_edits` and
        # `sound_file_replacements`, so the model holds a snapshot rather
        # than a live reference and goes stale on every change, not just
        # when `clear_opened_mod_content` rebinds the stores.
        self.model.set_edits(self._replaced_map())
        self.empty_note.setVisible(tree is None)
        self.tree.setVisible(tree is not None)
        self.search.setEnabled(tree is not None)
        self._update_counter()

    def _on_filter(self, text: str) -> None:
        self.proxy.setFilterFixedString(text)
        if text.strip():
            self.tree.expandAll()
        else:
            self.tree.collapseAll()

    def _open_selected_archive(self) -> None:
        """
        Opens whatever archive is now selected.

        On selection, not in `_refresh_detail`. That is where it went first,
        and `_after_track_change` calls `_refresh_detail` too - so replacing
        a single track threw the whole track list away and re-ran AudioMog
        over the archive. Minutes of work per replacement, and the selection
        lost each time.

        Always, not `if not self.tracks`: that guard opened the first
        archive and silently ignored every one after it, which is what made
        an "Open this archive's tracks" button look necessary.
        """
        if self.current_node is None or not self.current_node.is_file:
            return
        # Cleared first, so a failure shows an empty list rather than the
        # previous archive's tracks under a new name.
        self.tracks = []
        self.current_track = None
        self.track_list.clear()
        self.tracks_note.setText("Opening the archive...")
        self.open_archive()

    def _on_selection(self, current, _previous) -> None:
        node = self.model.node_at(current) if current.isValid() else None
        self.current_node = node if node is not None and node.is_file else None
        self._refresh_detail()
        self._open_selected_archive()

    def _refresh_detail(self) -> None:
        node = self.current_node
        if node is None:
            self.selected_label.setText("Select a sound archive")
            self.detail.setText("")
            self.tracks_note.setText("")
            return

        self.selected_label.setText(node.name)
        lines = [node.relative_path]

        # What KIND of archive it is, from the engine's own classifier, so a
        # user hunting for the battle theme is not reading paths.
        try:
            kind = sd.classify_sab_path(node.relative_path)
            if kind:
                lines.append(f"Type: {kind}")
        except Exception:                                     # noqa: BLE001
            pass

        tracks = self.state.sound_edits.get(node.relative_path) or {}
        if tracks:
            lines.append(f"{len(tracks)} track(s) replaced.")
        whole = self.state.sound_file_replacements.get(node.relative_path)
        if whole:
            lines.append(f"Whole archive replaced with: {whole}")
        self.detail.setText("\n".join(lines))

        # Said plainly rather than shown as an empty list. An archive whose
        # tracks cannot be read is a different thing from an archive with no
        # tracks in it, and the second would be a lie.


    # -- opening an archive -------------------------------------------------

    def _source_path(self):
        root = getattr(self.state, "nxd_unpack_dir", None)
        if root is None or self.current_node is None:
            return None
        return Path(root) / self.current_node.relative_path

    def open_archive(self) -> None:
        source = self._source_path()
        exe = getattr(self.state, "audiomog_exe_path", None)
        if source is None:
            self.tracks_note.setText("The unpacked game folder isn't set.")
            return
        if exe is None:
            self.tracks_note.setText(
                "AudioMog couldn't be found. It normally ships in this tool's "
                "tools folder - set it under General Setup, Advanced options.")
            return

        self.tracks_note.setText("Opening the archive...")
        worker = UnpackArchiveWorker(
            Path(exe), source, self.current_node.relative_path,
            paths.local_data_dir() / "sab_cache")
        self._thread = run_in_thread(
            worker, on_finished=self._archive_opened,
            on_failed=self._archive_failed)

    def set_tracks(self, tracks) -> None:
        """Fills the track list. Separate so it can be driven without AudioMog."""
        self.tracks = list(tracks)
        self.track_list.clear()
        replaced = (self.state.sound_edits.get(
            self.current_node.relative_path) or {}) if self.current_node else {}
        for track in self.tracks:
            marker = "  (replaced)" if track.index in replaced else ""
            item = QListWidgetItem(f"{track.index:03d} - {track.stem}{marker}")
            item.setData(Qt.UserRole, track.index)
            self.track_list.addItem(item)
        self.track_list.setVisible(bool(self.tracks))
        self.tracks_note.setText("")
        if self.tracks:
            self.track_list.setCurrentRow(0)

    def _archive_opened(self, tracks) -> None:
        self.set_tracks(tracks)

    def _archive_failed(self, message: str) -> None:
        # Selecting the archive again retries, so there is nothing to
        # re-enable - the failure just has to be readable.
        self.tracks_note.setText(f"Couldn't open that archive: {message}")

    # -- a track ---------------------------------------------------------------

    def _on_track_selected(self, current, _previous) -> None:
        if current is None:
            self.current_track = None
            self._refresh_track_buttons()
            return
        index = current.data(Qt.UserRole)
        self.current_track = next(
            (t for t in self.tracks if t.index == index), None)
        self._refresh_track_detail()

    def _refresh_track_detail(self) -> None:
        track = self.current_track
        if track is None:
            self.track_detail.setText("")
            self._refresh_track_buttons()
            return
        info = track.info
        lines = [f"{info.duration_sec:.1f}s, {info.sample_rate} Hz, "
                 f"{info.channels} channel(s)"]
        if info.loop_start is not None:
            lines.append(f"Loops from sample {info.loop_start} to "
                         f"{info.loop_end}.")
        else:
            lines.append("No loop points.")
        if track.users:
            # A STRING, not a list. This did `", ".join(track.users[:6])`,
            # which slices the first six CHARACTERS and comma-joins them -
            # so `FID_MUSIC_TRACK_068_OGG` rendered as "Used by: F, I, D, _,
            # M, U". Reported as "some letters I don't know what this is",
            # which is exactly what it was.
            #
            # Labelled the way the Tkinter column is. The value is the
            # in-game identifier AudioMog records in TrackUsers.txt, and it
            # is the only thing that tells you which of 300 files named
            # music_000NN is the one you are looking for.
            lines.append(f"In-game use: {track.users}")
        self.track_detail.setText("\n".join(lines))
        self._refresh_track_buttons()
        self._sync_loop_fields()

    def _refresh_track_buttons(self) -> None:
        has_track = self.current_track is not None
        self.play_button.setEnabled(has_track)
        self.stop_button.setEnabled(has_track)
        self.export_button.setEnabled(has_track)
        self.replace_button.setEnabled(has_track)
        replaced = self._replacements()
        self.clear_track_button.setEnabled(
            has_track and self.current_track.index in replaced)

    # -- loop points ------------------------------------------------------------

    def _sync_loop_fields(self) -> None:
        """
        Shows the loop this track will actually be written with.

        The edit's values when there is one, the vanilla track's otherwise -
        so the box always reflects what would be exported now, not what the
        file started as.
        """
        edit = self._replacements().get(
            self.current_track.index) if self.current_track else None
        info = self.current_track.info if self.current_track else None
        if isinstance(edit, dict) and edit.get("loop_start") is not None:
            start, end = edit["loop_start"], edit["loop_end"]
        elif info is not None and info.has_loop:
            start, end = info.loop_start, info.loop_end
        else:
            start, end = 0, 0

        self._loading_loop = True
        try:
            self.loop_start.setValue(int(start or 0))
            self.loop_end.setValue(int(end or 0))
        finally:
            self._loading_loop = False

        # Only a replaced track's loop can be changed: editing the vanilla
        # file's loop without replacing its audio would mean writing the
        # game's own track back with a different loop, which is a different
        # feature and not one anybody asked for.
        editable = isinstance(edit, dict)
        for widget in (self.loop_start, self.loop_end, self.reset_loop_button):
            widget.setEnabled(editable)
        self.loop_box.setEnabled(self.current_track is not None)

    def _on_loop_changed(self, _value) -> None:
        if getattr(self, "_loading_loop", False) or self.current_track is None:
            return
        edit = self._replacements().get(self.current_track.index)
        if not isinstance(edit, dict):
            return
        edit["loop_start"] = self.loop_start.value()
        edit["loop_end"] = self.loop_end.value()

    def reset_loop_points(self) -> None:
        """Puts the vanilla track's loop back, clamped to the replacement."""
        if self.current_track is None:
            return
        edit = self._replacements().get(self.current_track.index)
        if not isinstance(edit, dict):
            return
        info = self.current_track.info
        replacement = None
        try:
            replacement = sd.read_wav_info(Path(edit["source_path"]))
        except Exception:                                     # noqa: BLE001
            pass
        if info.has_loop and replacement is not None:
            start, end = sd.clamp_loop_points(
                info.loop_start, info.loop_end, replacement.num_samples)
        else:
            start, end = None, None
        edit["loop_start"], edit["loop_end"] = start, end
        self._sync_loop_fields()

    def _replacements(self) -> dict:
        if self.current_node is None:
            return {}
        return self.state.sound_edits.get(self.current_node.relative_path) or {}

    # -- playing, exporting, replacing ------------------------------------------

    def play_track(self) -> None:
        """
        Plays the track with its loop points applied, so what you hear is
        what the game would do rather than the raw file.
        """
        if self.current_track is None:
            return
        try:
            info = self.current_track.info
            preview = sd.build_preview_wav(
                self.current_track.wav_path,
                paths.local_data_dir() / "sab_cache" / "preview.wav",
                info.loop_start, info.loop_end)
            self._player = sd.SoundPlayer()
            self._player.play(preview)
        except Exception as exc:                              # noqa: BLE001
            self.track_detail.setText(
                self.track_detail.text() + f"\n\nCouldn't play that: {exc}")

    def stop_track(self) -> None:
        if self._player is not None:
            try:
                self._player.stop()
            except Exception:                                 # noqa: BLE001
                pass

    def export_track(self, _checked=False, path: str | None = None) -> None:
        if self.current_track is None:
            return
        if path is None:
            path, _ = QFileDialog.getSaveFileName(
                self, "Export track as WAV",
                f"{self.current_track.stem}.wav", "WAV audio (*.wav)")
        if not path:
            return
        try:
            sd.export_track_wav(self.current_track.wav_path, Path(path))
        except Exception as exc:                              # noqa: BLE001
            self.track_detail.setText(
                self.track_detail.text() + f"\n\nCouldn't export: {exc}")
            return
        self.track_detail.setText(
            self.track_detail.text() + f"\n\nExported to {path}")

    def replace_track(self, _checked=False, path: str | None = None) -> None:
        """
        Swaps a track for your own WAV, keeping the original's loop points.

        Keeping them is the default because a replacement of the same length
        almost always wants the same loop, and losing them turns looping
        music into music that stops.
        """
        if self.current_track is None or self.current_node is None:
            return
        if path is None:
            path, _ = QFileDialog.getOpenFileName(
                self, "Choose a replacement WAV", "",
                # `All files` for the same reason the image dialogs have
                # one, and because the Tkinter tab has always carried it: a
                # dialog with a single pattern cannot open a WAV whose
                # extension is `.WAV`, or missing, or something an audio
                # editor chose - and gives no sign the file is there.
                "WAV audio (*.wav);;All files (*)")
        if not path:
            return
        info = self.current_track.info
        try:
            sd.stage_replacement_track(
                Path(path), self.current_track.wav_path,
                info.loop_start, info.loop_end)
        except Exception as exc:                              # noqa: BLE001
            self.track_detail.setText(
                self.track_detail.text() + f"\n\nCouldn't replace: {exc}")
            return
        # The dict shape `stage_sound_export` documents and the Tkinter page
        # writes, not a bare path.
        #
        # This stored `str(path)`, which the exporter cannot read at all -
        # it takes `{track_index: {"source_path", "loop_start",
        # "loop_end"}}`. Same mistake as the Textures tab's bare string, and
        # invisible for the same reason: nothing exported sounds until this
        # session, so a shape nothing consumed could not be wrong yet.
        #
        # The loop points are clamped to the replacement's own length. A
        # shorter replacement with the original's loop end would loop past
        # its own end, which AudioMog writes happily and the game plays as
        # silence.
        replacement_info = sd.read_wav_info(Path(path))
        if info.has_loop and replacement_info is not None:
            start, end = sd.clamp_loop_points(
                info.loop_start, info.loop_end, replacement_info.num_samples)
        else:
            start, end = None, None
        archive = self.state.sound_edits.setdefault(
            self.current_node.relative_path, {})
        archive[self.current_track.index] = {
            "source_path": Path(path), "loop_start": start, "loop_end": end,
        }
        self._after_track_change()

    def clear_track_replacement(self) -> None:
        if self.current_track is None or self.current_node is None:
            return
        archive = self.state.sound_edits.get(self.current_node.relative_path)
        if archive:
            archive.pop(self.current_track.index, None)
            if not archive:
                self.state.sound_edits.pop(self.current_node.relative_path, None)
        self._after_track_change()

    def _after_track_change(self) -> None:
        selected = self.current_track.index if self.current_track else None
        self.set_tracks(self.tracks)
        if selected is not None:
            for i in range(self.track_list.count()):
                if self.track_list.item(i).data(Qt.UserRole) == selected:
                    self.track_list.setCurrentRow(i)
                    break
            # Restored directly as well as through the list.
            #
            # `setCurrentRow` only emits when the row actually changes, and
            # rebuilding the list often lands the selection back on the same
            # index - so the signal that sets `current_track` never fires and
            # the page ends up with a selected row and no current track.
            # Replacing a track then left the loop point fields disabled
            # until you clicked another track and back.
            if self.current_track is None:
                self.current_track = next(
                    (t for t in self.tracks if t.index == selected), None)
        # The model was never told. Textures called `set_edits` after every
        # replacement and Sounds did not, so a replaced sound file kept its
        # unreplaced colour and its folders their old counts until the tab
        # was rebuilt. The two pages share this model; only one of them was
        # keeping it current.
        self.model.set_edits(self._replaced_map(), self._changed_path)
        self._changed_path = None
        self._update_counter()
        self._refresh_detail()
        self.edits_changed.emit()

    def _replaced_map(self) -> dict:
        """
        Every archive this mod touches, however it touches it.

        There are TWO stores and the tree was only ever given one of them:

            sound_edits              {archive: {track: ...}}   per-track
            sound_file_replacements  {archive: source}         whole file

        Replacing a whole archive is what mod recovery produces; editing a
        track is what this page itself does. Passing only the second meant
        the thing the page is actually for never marked the tree at all -
        you could replace a dozen tracks and the browser looked untouched.

        An archive with an empty track dict is not counted: `sound_edits`
        keeps a key once a track has been looked at, and a row that goes
        green for having been clicked on would be worse than no marking.
        """
        marked = {path: tracks for path, tracks
                  in (self.state.sound_edits or {}).items() if tracks}
        marked.update(self.state.sound_file_replacements or {})
        return marked

    def _update_counter(self) -> None:
        total = self.model.file_count()
        if not total:
            self.counter.setText("")
            return
        tracks = self.state.edited_sound_track_count()
        files = self.state.replaced_sound_file_count()
        parts = []
        if tracks:
            parts.append(f"{tracks} track{'s' if tracks != 1 else ''} replaced")
        if files:
            parts.append(f"{files} whole archive{'s' if files != 1 else ''} replaced")
        self.counter.setText(
            f"{total:,} sound archives" + (" - " + ", ".join(parts) if parts else ""))
