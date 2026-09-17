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
    QCheckBox, QComboBox, QFileDialog, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QPlainTextEdit, QSpinBox,
    QListWidgetItem, QPushButton, QSizePolicy, QSpinBox, QTreeView,
    QSplitter, QVBoxLayout, QWidget
)

from ... import pzd_data
from ... import sound_data as sd
from ... import paths
from ..models.texture_tree import TextureTreeModel
from ..widgets.actions import (
    edit_counter_text, language_combo, page_intro)
from ..widgets.field_rows import CollapsibleSection
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


#: How many in-game users to name before saying "and N more".
TRACK_USER_LIMIT = 12

#: A users list with more than this share of undecodable bytes is not worth
#: printing. `parse_track_users` reads with `errors="replace"`, so a track
#: whose entry is binary comes back as thousands of U+FFFD.
TRACK_USER_GARBAGE_SHARE = 0.3


def describe_track_users(users: str) -> str:
    """
    The "In-game use" line, bounded and readable.

    Reported from real use: one track - 016 of `vo_bs001_battle.en.sab` -
    froze Mod Studio for a long time and then printed thousands of question
    marks. Its entry in AudioMog's `TrackUsers.txt` is enormous and mostly
    undecodable, and the page was handing the lot to a word-wrapping QLabel
    to lay out in one go.

    Two separate faults, so two guards:

    - **Length.** Named up to `TRACK_USER_LIMIT`, then a count. Every other
      list in this tool that can run long does this; this one was the
      exception because nobody had seen a long one.
    - **Content.** `parse_track_users` decodes with `errors="replace"`, so a
      binary entry arrives as a wall of U+FFFD. Printing ten thousand
      question marks tells the reader nothing and costs them a frozen
      window; saying the entry is unreadable tells them what is true.
    """
    text = (users or "").strip()
    if not text:
        return ""
    replacement = text.count("\ufffd") + text.count("?")
    if replacement > len(text) * TRACK_USER_GARBAGE_SHARE:
        return ("(this track's usage list is not readable text - AudioMog "
                "wrote bytes that are not a name)")
    parts = [part.strip() for part in text.split(",") if part.strip()]
    if len(parts) <= TRACK_USER_LIMIT:
        return ", ".join(parts)
    return (", ".join(parts[:TRACK_USER_LIMIT])
            + f", and {len(parts) - TRACK_USER_LIMIT} more")


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
            "Music, voice lines and sound effects. Each archive can hold "
            "several tracks, and a voice recording carries the subtitle "
            "spoken in it."))

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

        # In a widget, so the whole set can be hidden until an archive is
        # chosen. Five disabled buttons, a Loop points box and a Subtitle
        # box, all sitting under "Select a sound archive", is a page that
        # looks broken before it has been used - reported from real use,
        # with a screenshot.
        self.actions_box = QWidget()
        actions = QVBoxLayout(self.actions_box)
        actions.setContentsMargins(0, 0, 0, 0)
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
        right.addWidget(self.actions_box)

        # -- the subtitle for this recording ---------------------------------
        #
        # Subtitles live on THIS page, not a page of their own, and the data
        # is what settles it: 14,208 lines, 14,208 distinct voice paths,
        # 100% of lines carrying one, every one a `.sab` under
        # `sound/voice/`. The relationship is total and one-to-one, because
        # these lines ARE the subtitles for these recordings - listen to a
        # file and you hear the line.
        #
        # They were briefly a separate "Text" page. That was wrong: it split
        # one thing across two places and asked somebody checking a line
        # against its recording to hold two tabs in their head. The thing
        # you are looking at when you want the words is the recording.
        #
        # Progressive disclosure, Wroblewski's rule: the SUBTITLE is what
        # somebody came for and is always visible. Speaker, show type and
        # the short-voice fields are real and editable but are the long
        # tail, so they sit behind one disclosure rather than pushing the
        # line itself below the fold.
        self.subtitle_box = QGroupBox("Subtitle")
        subtitle_column = QVBoxLayout(self.subtitle_box)

        self.subtitle_status = QLabel("")
        self.subtitle_status.setProperty("role", "muted")
        self.subtitle_status.setWordWrap(True)
        subtitle_column.addWidget(self.subtitle_status)

        language_row = QHBoxLayout()
        language_row.addWidget(QLabel("Language:"))
        # Built inside the guard: populating a combo emits
        # `currentTextChanged`, and that signal arriving during construction
        # was being read as "the person picked English" - which then stuck,
        # so selecting the Japanese recording went on showing the English
        # line.
        self._loading_subtitle = True
        try:
            self.subtitle_language = language_combo()
        finally:
            self._loading_subtitle = False
        self.subtitle_language.currentTextChanged.connect(
            self._on_subtitle_language)
        language_row.addWidget(self.subtitle_language)
        language_row.addStretch(1)
        self.subtitle_revert = QPushButton("Revert this line")
        self.subtitle_revert.setEnabled(False)
        self.subtitle_revert.clicked.connect(self.revert_subtitle)
        language_row.addWidget(self.subtitle_revert)
        subtitle_column.addLayout(language_row)

        self.subtitle_edit = QPlainTextEdit()
        self.subtitle_edit.setMaximumHeight(90)
        self.subtitle_edit.setPlaceholderText(
            "The words spoken in this recording")
        self.subtitle_edit.textChanged.connect(
            lambda: self._on_subtitle_field("line",
                                            self.subtitle_edit.toPlainText()))
        subtitle_column.addWidget(self.subtitle_edit)

        self.subtitle_more = CollapsibleSection(
            "Speaker, show type and short voice", self._subtitle_fields(),
            expanded=False)
        subtitle_column.addWidget(self.subtitle_more)
        right.addWidget(self.subtitle_box)

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
        self._refresh_detail()

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

    def select_record(self, relative_path) -> bool:
        """
        Selects an archive by its relative path - what a jump arrives with.

        Named `select_record` because that is the first method the shell's
        `open_tab` looks for, the same as Textures. This page had no such
        method, so a jump to it opened the tab and selected nothing; the
        Text page's "Edit ->" on a line's voice path is the first thing that
        needed it.

        The same model and proxy as Textures, so this is that method with
        the archive tree behind it rather than a second way of doing it.
        """
        index = self.model.index_for_path(str(relative_path))
        if not index.isValid():
            # The tree may not have been built yet. A jump can arrive before
            # this tab has ever been shown, and the page builds its tree
            # when it is - so the first jump of a session found an empty
            # model and selected nothing, which is what "it opens Sounds but
            # not the file" looks like.
            self.refresh_tree()
            index = self.model.index_for_path(str(relative_path))
        if not index.isValid():
            return False
        mapped = self.proxy.mapFromSource(index)
        if not mapped.isValid():
            # Hidden by the current filter. Cleared rather than reported as
            # a failure - the file exists and the person asked for it, so
            # the filter is the thing that should give way.
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
        self._open_selected_archive()

    # -- subtitles -----------------------------------------------------------

    def _subtitle_fields(self) -> QWidget:
        """
        The fields beyond the line itself, every one from `PzdTextContent`.

        All of them, because a field this tool reads but will not let
        anybody change is a field they have to leave Mod Studio and
        hand-edit YAML for. `Id` is absent because it is the key.
        """
        holder = QWidget()
        form = QVBoxLayout(holder)
        form.setContentsMargins(0, 0, 0, 0)
        self.subtitle_rows = {}

        def row(label, widget, field, getter):
            line = QHBoxLayout()
            caption = QLabel(label)
            caption.setMinimumWidth(150)
            line.addWidget(caption)
            line.addWidget(widget, 1)
            form.addLayout(line)
            self.subtitle_rows[field] = (widget, getter)

        self.speaker_type = QSpinBox()
        self.speaker_type.setRange(-32768, 32767)
        self.speaker_type.valueChanged.connect(
            lambda: self._on_subtitle_field("speaker_type",
                                            self.speaker_type.value()))
        row("Speaker type", self.speaker_type, "speaker_type",
            self.speaker_type.value)

        self.speaker_value = QSpinBox()
        self.speaker_value.setRange(-2147483648, 2147483647)
        self.speaker_value.valueChanged.connect(
            lambda: self._on_subtitle_field("speaker_value",
                                            self.speaker_value.value()))
        row("Speaker id", self.speaker_value, "speaker_value",
            self.speaker_value.value)

        self.show_type = QComboBox()
        # By name, with the number behind it - the enum's own members, so
        # nobody has to know that 2 is the hearing-impaired one.
        for value, name in sorted(pzd_data.SHOW_TYPES.items()):
            self.show_type.addItem(name, value)
        self.show_type.currentIndexChanged.connect(
            lambda: self._on_subtitle_field("show_type",
                                            self.show_type.currentData()))
        row("Show type", self.show_type, "show_type",
            self.show_type.currentData)

        self.voice_path = QLineEdit()
        self.voice_path.textChanged.connect(
            lambda: self._on_subtitle_field("voice_sound_path",
                                            self.voice_path.text()))
        row("Voice sound path", self.voice_path, "voice_sound_path",
            self.voice_path.text)

        self.short_voice_path = QLineEdit()
        self.short_voice_path.textChanged.connect(
            lambda: self._on_subtitle_field("short_voice_sound_path",
                                            self.short_voice_path.text()))
        row("Short voice path", self.short_voice_path,
            "short_voice_sound_path", self.short_voice_path.text)

        self.is_shortened = QCheckBox("Is shortened")
        self.is_shortened.toggled.connect(
            lambda: self._on_subtitle_field("is_shortened",
                                            self.is_shortened.isChecked()))
        row("", self.is_shortened, "is_shortened",
            self.is_shortened.isChecked)
        return holder

    #: The voice-path index and the folder it was built from. Class-level
    #: defaults so the accessor works before the first build - a page that
    #: raises on a fresh instance is a page that cannot be constructed.
    _voice_index: dict = {}
    _voice_index_root = object()

    def voice_index(self) -> dict:
        """
        `{voice path: (file, line id)}`, built once and kept.

        Rebuilt only when the unpack folder changes. Reading every `.pzd`
        costs about 0.4s for a text mod's 629 files and a few seconds for
        the game's 4,417 - cheap once, wasteful per selection.
        """
        root = getattr(self.state, "nxd_unpack_dir", None)
        if getattr(self, "_voice_index_root", None) != root:
            self._voice_index = pzd_data.build_voice_index(root)
            self._voice_index_root = root
        return self._voice_index

    def _subtitle_for(self, relative_path: str, language: str = ""):
        """
        The line whose voice path is this archive, in `language`.

        The index is keyed on the EN file's path by whichever language was
        scanned; the other languages are the same stem with a different
        code, so the language swap happens on the path rather than by
        indexing seven times.
        """
        # The archive's language is part of its FILE NAME and not part of
        # the voice path a line carries. Split them, and let the archive's
        # own language pick the subtitle unless the person has chosen
        # another - selecting the Japanese recording should show the
        # Japanese line.
        neutral, file_language = pzd_data.voice_key(relative_path)
        language = language or file_language
        found = self.voice_index().get(neutral)
        if not found:
            return None, "", 0
        text_path, line_id = found
        if not language:
            # The archive did not say, and neither did the person. Prefer
            # English, which is the order every other language picker in
            # this tool uses - rather than whichever file the scan reached
            # first, which is arbitrary and changes with the filesystem.
            root = getattr(self.state, "nxd_unpack_dir", None)
            _f, _stem, current = pzd_data.split_pzd_name(text_path)
            for preferred in pzd_data.PZD_LANGUAGES:
                candidate = text_path.replace(f".{current}.pzd",
                                              f".{preferred}.pzd")
                if root and (Path(root) / candidate).is_file():
                    language = preferred
                    break
        if language:
            folder, stem, current = pzd_data.split_pzd_name(text_path)
            if current and current != language:
                text_path = text_path.replace(f".{current}.pzd",
                                              f".{language}.pzd")
        root = getattr(self.state, "nxd_unpack_dir", None)
        try:
            lines = pzd_data.read_pzd(Path(root) / text_path)
        except (OSError, ValueError):
            return None, text_path, line_id
        entry = next((e for e in lines if e.line_id == line_id), None)
        return entry, text_path, line_id

    def _refresh_subtitle(self) -> None:
        """Fills the subtitle panel for whichever archive is selected."""
        node = self.current_node
        relative = node.relative_path if node is not None else ""
        self._subtitle_path = ""
        self._subtitle_line_id = None
        if not relative or not str(relative).endswith(".sab"):
            self.subtitle_box.setVisible(False)
            return
        _neutral, file_language = pzd_data.voice_key(relative)
        language = self._chosen_language or file_language
        entry, text_path, line_id = self._subtitle_for(relative, language)
        if entry is not None and language:
            position = self.subtitle_language.findText(language)
            if position >= 0 and position != self.subtitle_language.currentIndex():
                self._loading_subtitle = True
                try:
                    self.subtitle_language.setCurrentIndex(position)
                finally:
                    self._loading_subtitle = False
        if entry is None:
            # Hidden rather than shown empty. Most archives are music and
            # effects with no words in them, and an empty Subtitle box on
            # every one of them would be noise on 14,000 rows.
            self.subtitle_box.setVisible(False)
            return
        self.subtitle_box.setVisible(True)
        self._subtitle_path = text_path
        self._subtitle_line_id = line_id
        edits = (self.state.pzd_edits or {}).get(text_path, {}).get(
            line_id, {})
        self._loading_subtitle = True
        try:
            self.subtitle_edit.setPlainText(
                edits.get("line", entry.line))
            self.speaker_type.setValue(
                int(edits.get("speaker_type", entry.speaker_type)))
            self.speaker_value.setValue(
                int(edits.get("speaker_value", entry.speaker_value)))
            position = self.show_type.findData(
                int(edits.get("show_type", entry.show_type)))
            if position >= 0:
                self.show_type.setCurrentIndex(position)
            self.voice_path.setText(
                edits.get("voice_sound_path", entry.voice_sound_path))
            self.short_voice_path.setText(
                edits.get("short_voice_sound_path",
                          entry.short_voice_sound_path))
            self.is_shortened.setChecked(
                bool(edits.get("is_shortened", entry.is_shortened)))
        finally:
            self._loading_subtitle = False
        self.subtitle_status.setText(
            f"{text_path}  \u00b7  line {line_id}"
            + (f"  \u00b7  {len(edits)} field(s) edited" if edits else ""))
        self.subtitle_revert.setEnabled(bool(edits))

    #: The language the person PICKED, as opposed to the one the selected
    #: archive happens to be in. Empty means "follow the file", which is
    #: what makes selecting the Japanese recording show the Japanese line.
    _chosen_language = ""

    def _on_subtitle_language(self, text="") -> None:
        if getattr(self, "_loading_subtitle", False):
            return
        self._chosen_language = text or ""
        self._refresh_subtitle()

    def _on_subtitle_field(self, field: str, value) -> None:
        """
        Records one field, and drops it again if it matches the original.

        Typing a value back to what it was is not an edit. Without this,
        touching a field would put an unchanged value into the mod, which
        then wins over any other mod editing that line for no reason
        anybody chose.
        """
        if getattr(self, "_loading_subtitle", False):
            return
        path, line_id = self._subtitle_path, self._subtitle_line_id
        if not path or line_id is None:
            return
        entry, _p, _i = self._subtitle_for(
            self.current_node.relative_path,
            self._chosen_language or "")
        if entry is None:
            return
        lines = self.state.pzd_edits.setdefault(path, {})
        fields = lines.setdefault(line_id, {})
        if value == getattr(entry, field):
            fields.pop(field, None)
        else:
            fields[field] = value
        if not fields:
            lines.pop(line_id, None)
        if not lines:
            self.state.pzd_edits.pop(path, None)
        edits = self.state.pzd_edits.get(path, {}).get(line_id, {})
        self.subtitle_status.setText(
            f"{path}  \u00b7  line {line_id}"
            + (f"  \u00b7  {len(edits)} field(s) edited" if edits else ""))
        self.subtitle_revert.setEnabled(bool(edits))
        self.edits_changed.emit()

    def revert_subtitle(self) -> None:
        """Drops every edit on this line and shows the game's own values."""
        path, line_id = self._subtitle_path, self._subtitle_line_id
        if not path or line_id is None:
            return
        lines = self.state.pzd_edits.get(path, {})
        lines.pop(line_id, None)
        if not lines:
            self.state.pzd_edits.pop(path, None)
        self._refresh_subtitle()
        self.edits_changed.emit()

    def select_subtitle(self, voice_path: str, language: str = "") -> bool:
        """
        Selects the archive a subtitle belongs to - what a Find Text hit
        needs to land somewhere useful.
        """
        if language:
            position = self.subtitle_language.findText(language)
            if position >= 0:
                self.subtitle_language.setCurrentIndex(position)
        # A line's voice path names the RECORDING, not one language's copy
        # of it, so the archive to select is that path with a language put
        # back into it. Tried in order: the language asked for, then every
        # other the game ships, then the bare path - a mod that carries only
        # English subtitles should still land on the English recording.
        candidates = [pzd_data.voice_path_for_language(voice_path, language)]
        candidates += [pzd_data.voice_path_for_language(voice_path, code)
                       for code in pzd_data.PZD_LANGUAGES if code != language]
        candidates.append(str(voice_path))
        for candidate in candidates:
            if self.select_record(candidate):
                return True
        return False

    def subtitle_for_line(self, text_path: str, line_id) -> str:
        """The voice path of one line, so a hit can be turned into a jump."""
        root = getattr(self.state, "nxd_unpack_dir", None)
        try:
            lines = pzd_data.read_pzd(Path(root) / text_path)
        except (OSError, ValueError):
            return ""
        entry = next((e for e in lines if e.line_id == line_id), None)
        return entry.voice_sound_path if entry else ""

    def _refresh_detail(self) -> None:
        node = self.current_node
        if node is None or not node.is_file:
            # Nothing chosen, or a FOLDER chosen. Neither has tracks, loop
            # points or a subtitle, so none of that furniture is shown -
            # the pane says what to do and stops there.
            self.selected_label.setText("Select a sound archive")
            self.detail.setText("")
            self.tracks_note.setText("")
            self.track_list.setVisible(False)
            self.track_detail.setText("")
            self.actions_box.setVisible(False)
            self.loop_box.setVisible(False)
            self.subtitle_box.setVisible(False)
            return
        self.actions_box.setVisible(True)
        self.loop_box.setVisible(True)

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
        self._refresh_subtitle()

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
            lines.append(f"In-game use: {describe_track_users(track.users)}")
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
        # How many ARCHIVES this mod changes, which is the question every
        # other page's counter answers. This said "14,545 sound archives" -
        # the size of the game, the same number forever, and the only page
        # that never reported how much had been edited.
        #
        # An archive counts once whether a track inside it was replaced or
        # the whole thing was, because both mean "this mod ships this
        # archive". Subtitles are counted separately: editing the words is
        # not replacing the recording, and rolling them together would make
        # the number mean two things.
        changed = set(self.state.sound_edits or {}) | set(
            self.state.sound_file_replacements or {})
        text = edit_counter_text(len(changed), total, "sounds", "replaced")
        subtitles = self.state.edited_pzd_line_count()
        if subtitles:
            text += (f" - {subtitles:,} subtitle line"
                     f"{'s' if subtitles != 1 else ''} edited")
        self.counter.setText(text)
