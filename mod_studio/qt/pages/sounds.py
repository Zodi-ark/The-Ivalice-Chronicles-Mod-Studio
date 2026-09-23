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

They LAYER. Whole archives come from opened mods - this page replaces
tracks, and has no whole-archive button: "the overwhelming majority of
people who want to edit Sounds want to change tracks, not the whole
archive", so a button for it only confused them (it was added, then removed
at Zodi's request). A track replaced in an archive a mod already replaces
goes into that file, not the game's, or everything else the mod did to it
would be lost - so the tracks listed are the ones in the file that ships.

**AudioMog is a Windows binary.** Browsing, searching and classifying the
tree all work anywhere. Opening an archive to see its tracks does not, and
the page says so instead of showing an empty track list that looks like an
archive with nothing in it.
"""
from __future__ import annotations

import hashlib

from pathlib import Path

from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QMenu, QMessageBox, QPlainTextEdit, QSpinBox,
    QListWidgetItem, QPushButton, QSizePolicy, QSpinBox, QTreeView,
    QSplitter, QVBoxLayout, QWidget, QGridLayout
)

from ... import pzd_data
from ... import sound_data as sd
from ... import paths
from .. import export_dialogs
from ..bulk_export import (
    SOUND_FOLDER_LABEL, BulkExportRun, SoundExportWorker, files_under,
)
from ..models.texture_tree import TextureTreeModel
from ..widgets.actions import (
    edit_counter_text, language_combo, page_intro)
from ..widgets.field_rows import CollapsibleSection
from ..widgets.marked_tree import MarkedTreeView
from ..workers import Worker, run_in_thread
from ..pages.textures import TexturePathFilter, TreePaneSizer
from ..audio_output import LoopPlayer
from ..widgets.waveform import WaveformView
from ..widgets.stable_button import StableButton
from ..widgets.status_line import StatusLine

#: Where unpacked archives are cached for browsing. A new name, so the old
#: cache is never read: builds before this one wrote a replacement's audio
#: INTO the cached copy of the game's track, and Undo never put it back, so
#: an old cache can hold somebody's replacement where the game's track
#: should be - and Play, Export and Reset to vanilla would go on using it.
SAB_CACHE = "sab_cache_2"

#: The file tree's width on first show; the editor gets the rest. Measured
#: against the real game listing with the tree's own font: the widest row
#: under sound/ needs about 340px.
SOUND_TREE_WIDTH = 360


#: The four facts every track shows, in order: (key, label).
TRACK_INFO_ROWS = (("format", "Format"), ("loop", "Game loop"),
                   ("use", "In-game use"), ("source", "Source"))
UNDO_REPLACEMENT = "Undo this track's replacement"
UNDO_LOOP_CHANGE = "Undo this track's loop change"


def clock_text(frames: int, rate: int) -> str:
    """m:ss.mmm - how audio editors show a position."""
    seconds = frames / rate if rate else 0.0
    minutes, seconds = divmod(seconds, 60)
    return f"{int(minutes)}:{seconds:06.3f}"


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
                 cache_root: Path, as_name: str | None = None):
        super().__init__()
        self.exe_path = exe_path
        self.sab_path = sab_path
        self.relative_path = relative_path
        self.cache_root = cache_root
        self.as_name = as_name

    def run(self):
        self.log.emit(f"Opening {self.relative_path}...")
        project = sd.unpack_sab_cached(
            self.exe_path, self.sab_path, self.relative_path,
            self.cache_root, line_cb=self.log.emit, as_name=self.as_name)
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
        self._thread = None
        #: The folder export on screen, if any - one at a time. Kept after it
        #: finishes, so its result can be read (`last_bulk_export`).
        self._bulk_run = None
        self.last_bulk_export = None

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
        self.tree.setMinimumWidth(280)
        self.tree.setColumnWidth(0, 300)
        self.tree.selectionModel().currentChanged.connect(self._on_selection)
        # Folders only. This tree had no context menu at all; a folder now
        # has one entry, the bulk export Zodi asked for beside the Textures
        # one - "we should also do this for the Sounds page so users can
        # bulk export wav files". An archive's own actions are on the right,
        # where its tracks are, and nobody asked for them here.
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
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

        # -- the editor, laid out so that doing something moves nothing ---
        #
        # Reported: "when exporting tracks as WAV or Replacing tracks it
        # moves elements of the page making it not look modern and it feels
        # amateurish ... feel free to follow the design UI philosophy of the
        # likes of Adobe, Apple, or various Digital Audio Workstations."
        #
        # Measured on this page before the change, at 1920: exporting moved
        # the waveform down 32px, replacing a track moved it another 16 and
        # the track list 16, and pressing Play moved Stop, Loop and both Set
        # buttons 11px right. Every one was text appended to a label ABOVE
        # the thing being worked on, or a button whose width is its text.
        #
        # What an audio editor's inspector does instead, and this does now:
        #
        # * FIXED FIELDS, NOT A PARAGRAPH. The track's facts are four
        #   labelled rows that are always there - Format, Game loop, In-game
        #   use, Source - so replacing a track changes a value, never the
        #   number of lines.
        # * A RESULT GOES BESIDE WHAT PRODUCED IT, in room that is always
        #   laid out: Export and Replace report on their own row, the loop
        #   buttons on theirs (`StatusLine`). Nothing is inserted above the
        #   waveform, ever.
        # * STATE IN A BADGE. "1 track replaced" sits right-aligned in the
        #   title row, which is the title's height whatever it says.
        # * BUTTONS THAT CHANGE THEIR WORDS KEEP THEIR WIDTH (`StableButton`).
        # * LOADING IN PLACE. "Opening the archive..." is a line in the
        #   track list itself, which is one row tall either way for the
        #   single-track archives that are most of the game, rather than a
        #   note that appears above it and vanishes.
        right = QVBoxLayout()
        # Room between the groups, and none inside the header: the title
        # and its path read as one thing, the track list as the next.
        right.setSpacing(12)
        header = QVBoxLayout()
        header.setSpacing(2)
        title_row = QHBoxLayout()
        self.selected_label = QLabel("Select a sound archive")
        self.selected_label.setStyleSheet("font-weight: 600; font-size: 12pt;")
        title_row.addWidget(self.selected_label, 1)
        #: What this mod does to the archive: "1 track replaced", "Whole
        #: archive replaced". Empty when nothing is.
        self.archive_badge = QLabel("")
        self.archive_badge.setProperty("role", "ok")
        title_row.addWidget(self.archive_badge, 0,
                            Qt.AlignRight | Qt.AlignVCenter)
        header.addLayout(title_row)

        #: Where the archive is and what kind it is, on one line.
        self.detail = StatusLine()
        header.addWidget(self.detail)
        right.addLayout(header)

        # No "Open this archive's tracks" button - selecting an archive
        # opens it. It existed because only the first selection opened
        # anything, so a second archive needed a manual push.
        self.track_list = QListWidget()
        self.track_list.currentItemChanged.connect(self._on_track_selected)
        self.track_list.setVisible(False)
        right.addWidget(self.track_list)
        #: What the list is saying INSTEAD of tracks - "Opening the
        #: archive...", or why it couldn't - or "" when it holds tracks.
        self.track_list_message = ""

        # In a widget, so the whole set can be hidden until an archive is
        # chosen. Five disabled buttons, a Loop points box and a Subtitle
        # box, all sitting under "Select a sound archive", is a page that
        # looks broken before it has been used - reported from real use,
        # with a screenshot.
        #
        # Laid out the way audio editors lay out a track (Audacity, Adobe
        # Audition, Logic): what the track is, what you can do to it, then
        # its waveform across the whole width, then the transport under it -
        # every row only as wide as its buttons.
        self.actions_box = QWidget()
        actions = QVBoxLayout(self.actions_box)
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(10)

        # The track's facts, as an inspector shows them: a label column and
        # a value column, every row always present. A value too long for
        # the room is elided and whole in its tooltip.
        info = QGridLayout()
        info.setContentsMargins(0, 0, 0, 0)
        info.setHorizontalSpacing(16)
        info.setVerticalSpacing(4)
        #: key -> the value's line. See `track_info_text`.
        self.info_values = {}
        for row, (key, label) in enumerate(TRACK_INFO_ROWS):
            name = QLabel(label)
            name.setProperty("role", "muted")
            info.addWidget(name, row, 0)
            value = StatusLine()
            value.say("", "plain")
            info.addWidget(value, row, 1)
            self.info_values[key] = value
        info.setColumnStretch(1, 1)
        actions.addLayout(info)

        # Playback - see `play_track`. The playhead is read from the sound
        # device by this timer, never worked out from a clock.
        self._pcm = None
        self._pcm_cache = {}
        self._playing = False
        self._playhead = 0
        self.audio = LoopPlayer(self)
        self.audio.finished.connect(self._on_play_finished)
        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(33)
        self._tick_timer.timeout.connect(self._tick)

        track_row = QHBoxLayout()
        self.replace_button = QPushButton("Replace this track...")
        self.replace_button.setEnabled(False)
        self.replace_button.clicked.connect(self.replace_track)
        track_row.addWidget(self.replace_button)
        self.clear_track_button = StableButton(
            UNDO_REPLACEMENT, (UNDO_LOOP_CHANGE,))
        self.clear_track_button.setEnabled(False)
        self.clear_track_button.clicked.connect(self.clear_track_replacement)
        track_row.addWidget(self.clear_track_button)
        self.export_button = QPushButton("Export this track as WAV...")
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self.export_track)
        track_row.addWidget(self.export_button)
        track_row.addSpacing(8)
        #: What Export, Replace or Undo just did, beside them.
        self.action_status = StatusLine()
        track_row.addWidget(self.action_status, 1)
        actions.addLayout(track_row)

        self.waveform = WaveformView()
        self.waveform.min_loop = sd.MIN_MEANINGFUL_LOOP_SAMPLES
        self.waveform.seekRequested.connect(self._seek)
        self.waveform.loopDragged.connect(self._on_waveform_loop)
        self.waveform.loopEdited.connect(self._on_waveform_loop_edited)
        self.waveform.playToggleRequested.connect(self.play_track)
        actions.addWidget(self.waveform)

        transport = QHBoxLayout()
        self.play_button = StableButton("Play", ("Pause",))
        self.play_button.setEnabled(False)
        self.play_button.clicked.connect(self.play_track)
        transport.addWidget(self.play_button)
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_track)
        transport.addWidget(self.stop_button)
        # Says its state: the theme draws a checked button like any other.
        self.loop_button = StableButton("Loop: on", ("Loop: off",))
        self.loop_button.setCheckable(True)
        self.loop_button.setChecked(True)
        self.loop_button.setEnabled(False)
        self.loop_button.setToolTip(
            "On: playing jumps back to the loop's Start every time it "
            "reaches the End, the way the game plays it.")
        self.loop_button.toggled.connect(self._on_loop_toggled)
        transport.addWidget(self.loop_button)
        transport.addSpacing(16)
        self.set_start_button = QPushButton("Set loop start here")
        self.set_start_button.setEnabled(False)
        self.set_start_button.setToolTip(
            "Moves the loop's Start to the playhead - the line on the "
            "waveform. Play, pause where the loop should begin, click this.")
        self.set_start_button.clicked.connect(self.set_loop_start_here)
        transport.addWidget(self.set_start_button)
        self.set_end_button = QPushButton("Set loop end here")
        self.set_end_button.setEnabled(False)
        self.set_end_button.setToolTip(
            "Moves the loop's End to the playhead. Play, pause where the "
            "loop should jump back, click this.")
        self.set_end_button.clicked.connect(self.set_loop_end_here)
        transport.addWidget(self.set_end_button)
        transport.addSpacing(16)
        self.position_label = QLabel("")
        self.position_label.setProperty("role", "muted")
        transport.addWidget(self.position_label)
        transport.addSpacing(12)
        #: Why a loop edit or playback didn't happen, beside the buttons.
        self.loop_note = StatusLine()
        transport.addWidget(self.loop_note, 1)
        actions.addLayout(transport)
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

        # One line, so an edit adding "1 field(s) edited" cannot wrap it
        # and push the line being typed into down the page.
        self.subtitle_status = StatusLine()
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
        loop_box = QGroupBox("Exact loop points (samples)")
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
        loop_row.addSpacing(12)
        # The same points as times, which is what the waveform shows.
        self.loop_times = QLabel("")
        self.loop_times.setProperty("role", "muted")
        loop_row.addWidget(self.loop_times)
        loop_row.addStretch(1)
        self.loop_box = loop_box
        # Under the waveform it belongs to, not below the subtitle.
        right.insertWidget(right.indexOf(self.actions_box) + 1, loop_box)
        right.addStretch(1)
        # A draggable divider, like Textures. Which side wants the width
        # depends on whether you are hunting for an archive or working on
        # one, so the split is the reader's to set.
        right_holder = QWidget()
        right_holder.setLayout(right)
        split.addWidget(right_holder)
        split.setChildrenCollapsible(False)
        # The tree gets what its names need, the editor everything else, and
        # window resizes go to the editor - the waveform is what wants width.
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        self._tree_sizer = TreePaneSizer(split, SOUND_TREE_WIDTH)

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
        # The unpack folder's contents have just changed, so anything this
        # page cached FROM that folder is stale - the tree below is rebuilt
        # for exactly that reason, and the voice index is read from the
        # same folder.
        #
        # This is the hook because `app._on_setup_changed` already calls
        # `refresh_tree` on every page that has one, and setup emits
        # `setup_changed` at the end of every unpack, every conversion and
        # every mod open. Naming a new signal would have added a second
        # thing to remember; the list of names is what failed three times
        # in `_on_setup_changed` itself.
        self.forget_voice_index()
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
        self._show_track_info(None)
        self._show_list_message("Opening the archive...")
        self._load_waveform()
        self.open_archive()

    def _show_list_message(self, text: str) -> None:
        """
        Puts `text` in the track list in place of tracks - one row that
        cannot be selected.

        In the list rather than above it: the loading line used to be a
        label that appeared over the list and vanished a moment later, so
        every archive chosen made the page jump twice. The list is one row
        tall for a message and one row tall for the one track most
        archives hold, so opening one of those moves nothing.
        """
        self.track_list_message = text
        self.track_list.clear()
        item = QListWidgetItem(text)
        item.setFlags(Qt.NoItemFlags)
        item.setToolTip(text)
        self.track_list.addItem(item)
        self._fit_track_list(1)

    def _fit_track_list(self, rows: int) -> None:
        """As tall as `rows` rows, up to six."""
        rows = max(1, min(rows, 6))
        row = self.track_list.sizeHintForRow(0)
        if row <= 0:
            row = self.track_list.fontMetrics().height() + 4
        self.track_list.setFixedHeight(
            row * rows + 2 * self.track_list.frameWidth() + 2)

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

    def forget_voice_index(self) -> None:
        """
        Drops the cached index so the next lookup rebuilds it.

        Reported from real use: "if the user only unpacks Sounds and music
        on the General Set up page and then after that unpacks Game Data
        and Sounds and music the Subtitle box will not appear on the Sounds
        page until the user closes the session of Mod Studio and then
        reopens it."

        The cache below is keyed on the FOLDER'S PATH, and in that sequence
        the path never changes - only its contents do. The first unpack
        leaves a folder with no `.pzd` files in it at all (they come with
        Game Data), so the index is built empty and cached as such; the
        second unpack drops the `.pzd` files into that same folder, the
        root still compares equal, and `_subtitle_for` goes on finding
        nothing. `_refresh_subtitle` then takes its `entry is None` branch
        and hides the box on every selection.

        That restarting fixes it is the confirming detail rather than a
        coincidence: a new page has the class-level sentinel above for its
        `_voice_index_root`, so the comparison fails, so it rebuilds.

        Invalidated rather than rebuilt here. The rebuild reads every
        `.pzd` on disk, and the event that invalidates the index is not
        the event that needs it - someone who unpacks and never opens
        Sounds should not pay for a scan they will not look at.
        """
        # A fresh object, so the comparison in `voice_index` cannot match
        # any path. Assigning None would collide with the real "no folder
        # chosen" root and leave the empty index cached under it.
        self._voice_index_root = object()

    def voice_index(self) -> dict:
        """
        `{voice path: (file, line id)}`, built once and kept.

        Rebuilt when the unpack folder changes, and when
        `forget_voice_index` says its contents have. Reading every `.pzd`
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
        self.subtitle_status.say(
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
        self.subtitle_status.say(
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
            self.archive_badge.setText("")
            self.archive_badge.setToolTip("")
            self.detail.clear()
            self.track_list_message = ""
            self.track_list.setVisible(False)
            self._show_track_info(None)
            self.actions_box.setVisible(False)
            self.loop_box.setVisible(False)
            self.subtitle_box.setVisible(False)
            return
        self.actions_box.setVisible(True)
        self.track_list.setVisible(True)
        if not self.track_list.count():
            self._fit_track_list(1)
        self.loop_box.setVisible(self._track_loops())

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
        self.detail.say("  \u00b7  ".join(lines), "muted")

        # What the mod does to it, as a badge in the title row - which is
        # the title's height whatever the badge says, so an edit appearing
        # moves nothing. It used to be a third line under the path.
        badge = []
        tracks = self.state.sound_edits.get(node.relative_path) or {}
        if tracks:
            loops_only = sum(1 for edit in tracks.values()
                             if isinstance(edit, dict) and not edit.get("source_path"))
            if len(tracks) - loops_only:
                badge.append(f"{len(tracks) - loops_only} track(s) replaced")
            if loops_only:
                badge.append(f"{loops_only} loop(s) changed")
        whole = self.state.sound_file_replacements.get(node.relative_path)
        if whole:
            badge.append("Whole archive replaced")
        self.archive_badge.setText(", ".join(badge))
        self.archive_badge.setToolTip(
            f"Whole archive replaced with: {whole}" if whole else "")
        self._refresh_subtitle()

        # Said plainly rather than shown as an empty list. An archive whose
        # tracks cannot be read is a different thing from an archive with no
        # tracks in it, and the second would be a lie.


    # -- opening an archive -------------------------------------------------

    def _source_path(self):
        """
        The archive whose tracks the page shows: the whole-archive
        replacement when there is one, the game's own file otherwise - the
        tracks listed are the ones that will ship, and a track replaced now
        goes into that same file at export.
        """
        if self.current_node is None:
            return None
        whole = self.state.sound_file_replacements.get(
            self.current_node.relative_path)
        if whole:
            return Path(whole)
        root = getattr(self.state, "nxd_unpack_dir", None)
        if root is None:
            return None
        return Path(root) / self.current_node.relative_path

    def _cache_root_for(self, source: Path) -> Path:
        """
        The game's archives are cached by path; a replacement by its
        CONTENT, so a file changed and chosen again is unpacked again rather
        than showing what it used to hold.
        """
        cache = paths.local_data_dir() / SAB_CACHE
        whole = (self.state.sound_file_replacements.get(
            self.current_node.relative_path) if self.current_node else None)
        if whole and Path(whole) == Path(source):
            digest = hashlib.sha256(Path(source).read_bytes()).hexdigest()[:16]
            return cache / "replacements" / digest
        return cache

    def open_archive(self) -> None:
        source = self._source_path()
        exe = getattr(self.state, "audiomog_exe_path", None)
        if source is None:
            self._show_list_message("The unpacked game folder isn't set.")
            return
        if exe is None:
            self._show_list_message(
                "AudioMog couldn't be found. It normally ships in this tool's "
                "tools folder - set it under General Setup, Advanced options.")
            return

        self._show_list_message("Opening the archive...")
        worker = UnpackArchiveWorker(
            Path(exe), source, self.current_node.relative_path,
            self._cache_root_for(source), as_name=self.current_node.name)
        self._thread = run_in_thread(
            worker, on_finished=self._archive_opened,
            on_failed=self._archive_failed)

    def set_tracks(self, tracks) -> None:
        """Fills the track list. Separate so it can be driven without AudioMog."""
        self.tracks = list(tracks)
        if not self.tracks:
            # Said plainly rather than shown as an empty list. An archive
            # whose tracks cannot be read is a different thing from an
            # archive with no tracks in it, and the second would be a lie.
            self._show_list_message("This archive holds no tracks.")
            return
        # Rebuilt without the selection signal: `_after_track_change`
        # rebuilds the list to relabel it, and the selection it restores is
        # the same track, so nothing should look as though it was chosen
        # anew.
        blocked = self.track_list.blockSignals(True)
        try:
            self.track_list.clear()
            for track in self.tracks:
                item = QListWidgetItem(self._track_label(track))
                item.setData(Qt.UserRole, track.index)
                self.track_list.addItem(item)
        finally:
            self.track_list.blockSignals(blocked)
        self.track_list_message = ""
        self.track_list.setVisible(True)
        # As tall as its rows, up to six. Most archives hold one track, and
        # a 160px box for one line was height the waveform needed.
        self._fit_track_list(len(self.tracks))
        self.current_track = None
        self.track_list.setCurrentRow(0)

    def _archive_opened(self, tracks) -> None:
        self.set_tracks(tracks)

    def _archive_failed(self, message: str) -> None:
        # Selecting the archive again retries, so there is nothing to
        # re-enable - the failure just has to be readable.
        self._show_list_message(f"Couldn't open that archive: {message}")

    # -- a track ---------------------------------------------------------------

    def _on_track_selected(self, current, _previous) -> None:
        if current is None or current.data(Qt.UserRole) is None:
            self.current_track = None
            self._refresh_track_buttons()
            return
        index = current.data(Qt.UserRole)
        chosen = next((t for t in self.tracks if t.index == index), None)
        # A result belongs to the track it was about.
        if chosen is not self.current_track:
            self.action_status.clear()
            self.loop_note.clear()
        self.current_track = chosen
        self._refresh_track_detail()

    def _refresh_track_detail(self, reload_audio: bool = True) -> None:
        if reload_audio:
            self._load_waveform()
        self._show_track_info(self.current_track)
        self._refresh_track_buttons()
        if self.current_track is not None:
            self._sync_loop_fields()

    def _show_track_info(self, track) -> None:
        """
        The four facts, for `track` - or dashes, keeping every row, when
        there is no track yet.
        """
        values = {key: "\u2014" for key, _label in TRACK_INFO_ROWS}
        kinds = {key: "muted" for key, _label in TRACK_INFO_ROWS}
        if track is not None:
            info = track.info
            channels = f"{info.channels} channel{'s' if info.channels != 1 else ''}"
            values["format"] = (f"{info.duration_sec:.1f} s  \u00b7  "
                                f"{info.sample_rate:,} Hz  \u00b7  {channels}")
            if info.loop_start is not None:
                values["loop"] = (f"Loops from sample {info.loop_start} to "
                                  f"{info.loop_end}")
            else:
                values["loop"] = "No loop points"
            # A STRING, not a list. This did `", ".join(track.users[:6])`,
            # which slices the first six CHARACTERS and comma-joins them -
            # so `FID_MUSIC_TRACK_068_OGG` rendered as "Used by: F, I, D, _,
            # M, U". Reported as "some letters I don't know what this is",
            # which is exactly what it was.
            #
            # The value is the in-game identifier AudioMog records in
            # TrackUsers.txt, and it is the only thing that tells you which
            # of 300 files named music_000NN is the one you are looking for.
            values["use"] = (describe_track_users(track.users) if track.users
                             else "Not recorded")
            values["source"] = "The game's own audio"
            edit = self._replacements().get(track.index)
            if isinstance(edit, dict) and not edit.get("source_path"):
                values["source"] = "The game's own audio, with your loop"
            elif isinstance(edit, dict):
                values["source"] = (
                    f"Replaced with {Path(edit['source_path']).name}.")
                try:
                    mine = sd.read_wav_info(Path(edit["source_path"]))
                except Exception:                             # noqa: BLE001
                    mine = None
                # Said, not fixed: AudioMog writes the file's own rate and
                # channels into the archive, and whether the game resamples
                # has not been tested - so this is a hint, not a refusal.
                # The same row, in the attention colour, rather than a line
                # of its own that appears and pushes the waveform down.
                if mine is not None and ((mine.sample_rate, mine.channels)
                                         != (info.sample_rate, info.channels)):
                    values["source"] += (
                        f" Your file is {mine.sample_rate:,} Hz with "
                        f"{mine.channels} channel(s); the game's is "
                        f"{info.sample_rate:,} Hz with {info.channels}. If "
                        f"it plays wrongly in game convert it to match.")
                    kinds["source"] = "attention"
            for key in ("format", "loop", "use"):
                kinds[key] = "plain"
            if kinds["source"] == "muted":
                kinds["source"] = "plain"
        for key, line in self.info_values.items():
            line.say(values[key], kinds[key])

    def track_info_text(self) -> str:
        """The facts as the rows read them, "Label: value" per line."""
        labels = dict(TRACK_INFO_ROWS)
        return "\n".join(f"{labels[key]}: {line.text()}"
                         for key, line in self.info_values.items())

    def _refresh_track_buttons(self) -> None:
        has_track = self.current_track is not None
        self.play_button.setEnabled(has_track)
        self.stop_button.setEnabled(has_track)
        self.export_button.setEnabled(has_track)
        self.replace_button.setEnabled(has_track)
        # Loop controls only for a track that loops in the game, replaced or
        # not. On one that doesn't they only confused - reported.
        loops = self._track_loops()
        for button in (self.loop_button, self.set_start_button, self.set_end_button):
            button.setVisible(loops)
            button.setEnabled(loops)
        edit = self._replacements().get(self.current_track.index) if has_track else None
        self.clear_track_button.setEnabled(edit is not None)
        self.clear_track_button.setText(
            "Undo this track's loop change"
            if isinstance(edit, dict) and not edit.get("source_path")
            else "Undo this track's replacement")

    # -- loop points ------------------------------------------------------------

    def _sync_loop_fields(self) -> None:
        """
        Shows the loop this track will actually be written with.

        The edit's values when there is one, the vanilla track's otherwise -
        so the box always reflects what would be exported now, not what the
        file started as. Editable on every track that loops, the game's own
        included; hidden on one that doesn't.
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
        loops = self._track_loops()
        for widget in (self.loop_start, self.loop_end):
            widget.setEnabled(loops)
        self.reset_loop_button.setEnabled(isinstance(edit, dict))
        self.loop_box.setVisible(loops)
        self._show_loop()

    def _on_loop_changed(self, _value) -> None:
        if getattr(self, "_loading_loop", False) or not self._track_loops():
            return
        self._set_loop(self.loop_start.value(), self.loop_end.value())

    def reset_loop_points(self, _checked=False) -> None:
        """
        Puts the game's loop back. A loop change on the game's own track is
        simply undone; a replacement gets the game's loop, clamped to its
        own length.
        """
        if self.current_track is None:
            return
        edit = self._replacements().get(self.current_track.index)
        if not isinstance(edit, dict):
            return
        info = self.current_track.info
        if not edit.get("source_path"):
            if info.has_loop:
                self._set_loop(info.loop_start, info.loop_end)
            return
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
        self._update_playing_loop()

    def _replacements(self) -> dict:
        if self.current_node is None:
            return {}
        return self.state.sound_edits.get(self.current_node.relative_path) or {}

    # -- playing, exporting, replacing ------------------------------------------

    # -- playback and the loop editor ---------------------------------------------
    #
    # The audio streams to the sound device (`audio_output.LoopPlayer`), and
    # the playhead IS the device's position: it cannot run ahead of what is
    # heard, and playback ends when the device has played the last sample.
    # It used to follow a clock started when `winsound` returned - before the
    # sound began - so it ran ahead, and stopping at its end cut the sound's
    # end off (reported). A loop change while playing reaches the audio still
    # to be queued - no restart, no gap; only a seek starts over.
    #
    # Every track that loops in the game has a loop to edit, the game's own
    # audio included - asked for. Moving a game track's loop records a
    # loop-only edit (`source_path` None); export re-encodes the game's own
    # track, freshly unpacked, with the new loop. Moved back onto the game's
    # loop, that edit changes nothing, so it goes.

    def _track_loops(self) -> bool:
        """Whether the selected track loops in the game - what loop controls are for."""
        return self.current_track is not None and self.current_track.info.has_loop

    def _audio_source(self):
        """(file, loop start, loop end, editable) for the selected track - what will ship."""
        track = self.current_track
        if track is None:
            return None, None, None, False
        edit = self._replacements().get(track.index)
        if isinstance(edit, dict):
            source = Path(edit["source_path"]) if edit.get("source_path") else track.wav_path
            start, end = edit.get("loop_start"), edit.get("loop_end")
            return source, start, end, self._track_loops() and start is not None
        if track.info.has_loop:
            return track.wav_path, track.info.loop_start, track.info.loop_end, True
        return track.wav_path, None, None, False

    def _pcm_for(self, path: Path):
        stat = Path(path).stat()
        key = (str(path), stat.st_mtime_ns, stat.st_size)
        if key not in self._pcm_cache:
            if len(self._pcm_cache) >= 2:
                self._pcm_cache.clear()
            self._pcm_cache[key] = sd.read_pcm16(Path(path))
        return self._pcm_cache[key]

    def _load_waveform(self) -> None:
        """Shows the selected track's audio: the replacement, once there is one."""
        self._stop_playback()
        self._playhead = 0
        self._pcm = None
        path = self._audio_source()[0]
        if path is not None:
            try:
                self._pcm = self._pcm_for(path)
            except Exception as exc:                          # noqa: BLE001
                self.loop_note.say(f"Couldn't read the audio: {exc}",
                                   "attention")
        self.waveform.set_audio(self._pcm)
        self._show_loop()
        self._update_position()

    def _show_loop(self) -> None:
        """The loop, as the waveform draws it and as times beside the numbers."""
        _path, start, end, editable = self._audio_source()
        self.waveform.set_loop(start, end, editable)
        rate = self._pcm.sample_rate if self._pcm is not None else 0
        if rate and start is not None and end is not None and end > start:
            self.loop_times.setText(
                f"{clock_text(start, rate)} to {clock_text(end, rate)}")
        else:
            self.loop_times.setText("")

    def _update_position(self) -> None:
        if self._pcm is None:
            self.position_label.setText("")
            return
        rate = self._pcm.sample_rate
        text = (f"{clock_text(self._playhead, rate)} / "
                f"{clock_text(self._pcm.frames, rate)}")
        self.position_label.setText(text)

    def play_track(self, _checked=False) -> None:
        """
        Plays from the playhead - or pauses, if playing. What plays is what
        will ship: the replacement once there is one, with the loop it will
        be written with.
        """
        if self._playing:
            self._pause()
            return
        if self.current_track is None or self._pcm is None:
            return
        self._start_playback(self._playhead)

    def _looping(self) -> bool:
        return self.loop_button.isChecked() and self._track_loops()

    def _start_playback(self, frame: int) -> None:
        _path, start, end, _editable = self._audio_source()
        try:
            self.audio.play(self._pcm, frame, start, end, self._looping())
        except Exception as exc:                              # noqa: BLE001
            self._set_playing(False)
            self.loop_note.say(f"Couldn't play that: {exc}", "attention")
            return
        self._playhead = int(frame)
        self._set_playing(True)

    def _set_playing(self, playing: bool) -> None:
        self._playing = playing
        self.play_button.setText("Pause" if playing else "Play")
        if playing:
            self._tick_timer.start()
        else:
            self._tick_timer.stop()

    def _current_frame(self) -> int:
        if self._playing:
            frame = self.audio.current_frame()
            if frame is not None:
                return frame
        return self._playhead

    def _tick(self) -> None:
        if not self._playing:
            return
        self._playhead = self._current_frame()
        self.waveform.set_playhead(self._playhead, follow=True)
        self._update_position()

    def _on_play_finished(self) -> None:
        """The device has played the last sample: back to the start, as Stop does."""
        self._set_playing(False)
        self._playhead = 0
        self.waveform.set_playhead(0)
        self._update_position()

    def _pause(self) -> None:
        frame = self._current_frame()
        self.audio.stop()
        self._set_playing(False)
        self._playhead = frame
        self.waveform.set_playhead(frame)
        self._update_position()

    def stop_track(self, _checked=False) -> None:
        """Stops, and goes back to the beginning - a transport's Stop."""
        self._stop_playback()
        self._playhead = 0
        self.waveform.set_playhead(0)
        self._update_position()

    def _stop_playback(self) -> None:
        self.audio.stop()
        self._set_playing(False)

    def changeEvent(self, event):                                # noqa: N802
        # The list is a FIXED height, worked out from a row's height - and
        # a row's height is the stylesheet's. A theme change in Settings
        # restyles the rows, so the list is refitted to them, or the next
        # archive chosen would refit it and move everything under it.
        # After the children have restyled, which is why it is queued.
        super().changeEvent(event)
        if event.type() in (QEvent.StyleChange, QEvent.FontChange):
            QTimer.singleShot(0, self._refit_track_list)

    def _refit_track_list(self) -> None:
        if self.track_list.count():
            self._fit_track_list(len(self.tracks) or 1)

    def hideEvent(self, event):                                  # noqa: N802
        # Leaving the page stops the music, rather than leaving it playing
        # behind another page with nothing on screen to stop it.
        self._stop_playback()
        super().hideEvent(event)

    def _seek(self, frame: int) -> None:
        self._playhead = frame
        self.waveform.set_playhead(frame)
        self._update_position()
        if self._playing:
            self._start_playback(frame)

    def _update_playing_loop(self) -> None:
        """A loop change reaches the audio still to be queued: no restart, no gap."""
        if self._playing:
            _path, start, end, _editable = self._audio_source()
            self.audio.update_loop(start, end, self._looping())

    def _on_loop_toggled(self, checked) -> None:
        self.loop_button.setText("Loop: on" if checked else "Loop: off")
        self._update_playing_loop()

    def _loop_edit(self, create: bool = False):
        """The edit holding this track's loop - made on first use for a game track that loops."""
        track = self.current_track
        if track is None or self.current_node is None:
            return None
        edit = self._replacements().get(track.index)
        if isinstance(edit, dict):
            return edit
        if not (create and track.info.has_loop):
            return None
        edit = {"source_path": None, "loop_start": track.info.loop_start,
                "loop_end": track.info.loop_end}
        self.state.sound_edits.setdefault(
            self.current_node.relative_path, {})[track.index] = edit
        return edit

    def _drop_edit(self) -> None:
        archive = self.state.sound_edits.get(self.current_node.relative_path)
        if archive is not None:
            archive.pop(self.current_track.index, None)
            if not archive:
                self.state.sound_edits.pop(self.current_node.relative_path, None)

    def _set_loop(self, start: int, end: int) -> None:
        if self.current_track is None:
            return
        had_edit = isinstance(self._replacements().get(self.current_track.index), dict)
        edit = self._loop_edit(create=True)
        if edit is None:
            return
        edit["loop_start"], edit["loop_end"] = int(start), int(end)
        info = self.current_track.info
        dropped = (not edit.get("source_path")
                   and (edit["loop_start"], edit["loop_end"])
                   == (info.loop_start, info.loop_end))
        if dropped:
            self._drop_edit()
        self._loading_loop = True
        try:
            self.loop_start.setValue(int(start))
            self.loop_end.setValue(int(end))
        finally:
            self._loading_loop = False
        self.loop_note.clear()
        self._show_loop()
        if dropped or not had_edit:
            self._mark_track()
        self._update_playing_loop()

    def _mark_track(self) -> None:
        """The list, tree, counter and buttons after an edit appears or goes - the audio stays."""
        item = self.track_list.currentItem()
        if item is not None and self.current_track is not None:
            item.setText(self._track_label(self.current_track))
        self.model.set_edits(self._replaced_map(), self.current_node.relative_path
                             if self.current_node else None)
        self._update_counter()
        self._refresh_detail()
        self._refresh_track_detail(reload_audio=False)
        self.edits_changed.emit()

    def _track_label(self, track) -> str:
        edit = self._replacements().get(track.index)
        if isinstance(edit, dict) and not edit.get("source_path"):
            marker = "  (loop changed)"
        elif track.index in self._replacements():
            marker = "  (replaced)"
        else:
            marker = ""
        return f"{track.index:03d} - {track.stem}{marker}"

    def _on_waveform_loop(self, start, end) -> None:
        self._set_loop(start, end)

    def _on_waveform_loop_edited(self, start, end) -> None:
        self._set_loop(start, end)

    def set_loop_start_here(self, _checked=False) -> None:
        """Moves the loop's start to the playhead."""
        self._set_loop_edge("start")

    def set_loop_end_here(self, _checked=False) -> None:
        """Moves the loop's end to the playhead."""
        self._set_loop_edge("end")

    def _set_loop_edge(self, which: str) -> None:
        if not self._track_loops() or self._pcm is None:
            return
        here = self._current_frame()
        _path, start, end, _editable = self._audio_source()
        start = 0 if start is None else start
        end = self._pcm.frames if end is None else end
        if which == "start":
            start = here
        else:
            end = here
        if end - start < sd.MIN_MEANINGFUL_LOOP_SAMPLES:
            self.loop_note.say(
                "The loop's start has to come before its end - move the "
                "playhead left of the End flag first." if which == "start" else
                "The loop's end has to come after its start - move the "
                "playhead right of the Start flag first.", "attention")
            return
        self._set_loop(start, end)

    def export_track(self, _checked=False, path: str | None = None) -> None:
        if self.current_track is None:
            return
        if path is None:
            path = export_dialogs.save_file(
                self, "Export track as WAV",
                f"{self.current_track.stem}.wav", "WAV audio (*.wav)")
        if not path:
            return
        try:
            sd.export_track_wav(self.current_track.wav_path, Path(path))
        except Exception as exc:                              # noqa: BLE001
            self.action_status.say(f"Couldn't export: {exc}", "attention")
            return
        self.action_status.say(f"Exported to {path}", "ok")

    # -- bulk export -------------------------------------------------------------

    def _show_context_menu(self, point) -> None:
        index = self.tree.indexAt(point)
        if not index.isValid():
            return
        node = self.model.node_at(index)
        if node is None or getattr(node, "is_file", False):
            return
        menu = QMenu(self.tree)
        export_folder = menu.addAction(SOUND_FOLDER_LABEL)
        export_folder.setEnabled(not self.bulk_export_running())
        chosen = menu.exec(self.tree.viewport().mapToGlobal(point))
        if chosen is export_folder:
            self.export_folder_as_wav(node=node)

    def bulk_export_running(self) -> bool:
        return self._bulk_run is not None and self._bulk_run.running

    def export_folder_as_wav(self, _checked=False, node=None,
                             destination: str | None = None):
        """
        Exports every track of every archive under a folder as WAV files,
        mirroring the game's folder structure under the folder picked.

        Each archive is unpacked FRESH, into a private folder, from the
        game's own file - not from the browsing cache, and not from a
        whole-archive replacement an opened mod brought in. See
        `bulk_export` for the naming rule and the rest. `destination` is
        for tests, which cannot answer a folder dialog.

        Nothing can be exported without AudioMog, so that is said before
        anything starts rather than as fourteen thousand identical
        failures afterwards.
        """
        root = getattr(self.state, "nxd_unpack_dir", None)
        if node is None or not root or self.bulk_export_running():
            return None
        exe = getattr(self.state, "audiomog_exe_path", None)
        if exe is None:
            box = QMessageBox(self)
            box.setWindowTitle("Can't export")
            box.setIcon(QMessageBox.Information)
            box.setText(
                "AudioMog couldn't be found, and every sound archive has to "
                "go through it. It normally ships in this tool's tools "
                "folder - set it under General Setup, Advanced options.")
            box.setAttribute(Qt.WA_DeleteOnClose)
            box.show()
            self.refusal_box = box
            return None
        relative_paths = [leaf.relative_path for leaf in files_under(node)]
        if not relative_paths:
            return None
        if destination is None:
            destination = export_dialogs.choose_folder(
                self, f"Export {len(relative_paths):,} sound archives from "
                      f"{node.relative_path} to which folder?")
        if not destination:
            return None
        worker = SoundExportWorker(root, relative_paths, destination, exe)
        run = BulkExportRun(
            self, worker,
            f"Exporting the tracks of {len(relative_paths):,} sound archives "
            f"from {node.relative_path} as WAVs into {destination}")
        run.done.connect(self._bulk_export_done)
        self._bulk_run = run
        run.start()
        return run

    def _bulk_export_done(self, result) -> None:
        self.last_bulk_export = result

    def replace_track(self, _checked=False, path: str | None = None) -> None:
        """
        Swaps a track for your own WAV, keeping the original's loop points.
        Keeping them is the default because a replacement of the same length
        almost always wants the same loop, and losing them turns looping
        music into music that stops.

        RECORDED, not copied. The file is checked now - a WAV the game can't
        take is refused while you are looking at it, not at export as an
        AudioMog stack trace - and it is not written anywhere: it used to go
        over the cached copy of the game's track, which Undo never restored.
        """
        if self.current_track is None or self.current_node is None:
            return
        if path is None:
            path = export_dialogs.open_file(
                self, "Choose a replacement WAV",
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
            replacement_info = sd.check_replacement_wav(Path(path))
        except Exception as exc:                              # noqa: BLE001
            self.action_status.say(f"Couldn't replace: {exc}", "attention")
            return
        # The dict shape `stage_sound_export` reads - `{track_index:
        # {"source_path", "loop_start", "loop_end"}}` - not a bare path, which
        # the exporter could not read at all.
        #
        # The loop points are clamped to the replacement's own length. A
        # shorter replacement with the original's loop end would loop past
        # its own end, which AudioMog writes happily and the game plays as
        # silence.
        current = self._replacements().get(self.current_track.index)
        if info.has_loop:
            # A loop already moved on the game's track carries over: it is
            # the loop the person chose, not the game's.
            base = (info.loop_start, info.loop_end)
            if (isinstance(current, dict) and not current.get("source_path")
                    and current.get("loop_start") is not None):
                base = (current["loop_start"], current["loop_end"])
            start, end = sd.clamp_loop_points(
                base[0], base[1], replacement_info.num_samples)
        else:
            start, end = None, None
        archive = self.state.sound_edits.setdefault(
            self.current_node.relative_path, {})
        archive[self.current_track.index] = {
            "source_path": Path(path), "loop_start": start, "loop_end": end,
        }
        self._after_track_change()
        self.action_status.say("Track replaced.", "ok")

    def clear_track_replacement(self) -> None:
        if self.current_track is None or self.current_node is None:
            return
        archive = self.state.sound_edits.get(self.current_node.relative_path)
        undone = bool(archive) and self.current_track.index in archive
        if archive:
            archive.pop(self.current_track.index, None)
            if not archive:
                self.state.sound_edits.pop(self.current_node.relative_path, None)
        self._after_track_change()
        if undone:
            self.action_status.say("Track undone.", "muted")

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
        # With the archive's path, so the model repaints that row and its
        # folders. Without one it RESETS, and a reset collapses every folder
        # in the tree - which replacing or undoing a track did, reported
        # from real use, because nothing ever set `_changed_path`.
        self.model.set_edits(
            self._replaced_map(),
            self._changed_path or (self.current_node.relative_path
                                   if self.current_node else None))
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
