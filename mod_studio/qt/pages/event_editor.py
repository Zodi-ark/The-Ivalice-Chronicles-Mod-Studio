"""
The Event Editor (Zodi's Task 4, 12 October: "a node based Event Editor
with a map viewer to preview the events, and it should have the feature to
play each node forward or backward to make editing them or creating new
ones a breeze"). Built 19 October from the second mock-up, in chaiNNer's
style, which he answered "Yes build it with the ready made tab".

- **Left**, three tabs: **Events** (every scene and battle event the game
  has, and the mod's own: its number, its place and its first words),
  **Nodes** (the nodes to add: a search, the favourites, then each kind,
  each with a line saying what it does; drag one into the strip, or double
  click it to add it after the node picked) and **Ready-made** (short
  events of several nodes, to start from).
- **Middle**, the event played on its map (`event_map.EventMap`): Back one,
  Play backward, Pause, Play forward, Forward one, Loop, a speed.
- **Right**, the node picked, drawn as a big node: its fields, labels above
  them, and a line saying when it plays and what it waits for, or what is
  wrong with it. Play from here, Copy, Remove.
- **Under them**, the nodes in the order they play, wired
  (`event_nodes.NodeStrip`): click one to pick it, double click to play
  from it, drag to move it. Gold: played so far.

**What it changes.** A node's fields are the bytes of its instructions
(`event_scripts.with_operands`); adding, moving and taking out nodes is
the script's instruction list. The script, whole, goes into
`state.script_edits` when it differs from the game's, and export writes it
to `FFTIVC/data/<mode>/script/<mode>/eventNNN.e`. A speech line's words go
into `state.pzd_edits`, the Sounds page's store, on the scene's text file;
a Speak node with new words is a new line of that file, in every language
the game has it in (`pzd_data.ADDED_LINE`), written in the language shown.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy, QSpinBox, QSplitter,
    QStackedWidget, QTabBar, QVBoxLayout, QWidget,
)

from ... import battle_maps as bmaps
from ... import encounter_names
from ... import event_scripts as es
from ... import pzd_data
from ... import reference_names
from ... import ui_settings
from ... import unit_sprites as us
from .. import theme
from ..widgets import actions
from ..widgets.actions import page_intro
from ..workers import Worker, run_in_thread
from . import abilities as abilities_page
from . import encounter_map as em
from . import event_words as words
from . import event_map as evm
from .event_map import EventMap
from . import event_music as emu
from .event_music import MusicPlayer
from . import event_voices as evv
from .event_voices import VoicePlayer
from .event_nodes import Card, Line, NodeBand, NodeList, NodeStrip

TITLE = "Event Editor"
BLURB = ("Every scene and battle event in the game. Pick one to play it on its map, then change it node "
         "by node.")
NO_GAME = "No game files yet. Unpack your game on General Setup to see its events here."
NO_LENGTHS = "The game's BATTLE.BIN can't be read ({}), so its events can't be either."
#: Why the list is empty, and what to do about it (Zodi, 19 October: "I
#: unpacked my game files and there is nothing to edit in the event editor":
#: no unpack took the game's script folder until Game data did).
NO_SCRIPTS = ("Your unpacked game has no event scripts yet. On General Setup, unpack again with Game data "
              "ticked: it brings the events too.")
NO_BATTLE_BIN = ("Your unpacked game has no BATTLE.BIN, which says how the events are read. On General "
                 "Setup, unpack again with Textures ticked: it brings the fftpack folder, BATTLE.BIN in it.")
PICK_AN_EVENT = "Pick an event in the list, then a node in the row below, to see it here."
NODES_HEAD = "In the order they play. Click one to pick it, double click to play from it, drag to move it."
GOLD_NOTE = "Gold: played so far"
PICK_A_NODE = "Pick a node in the row below to see it here."
PICK_A_BATTLE = "Pick a battle"
WORDS_NOTE = ("Kept in the scene's text file, once for each language you edit. Line {line} of {file}.")
NEW_WORDS_NOTE = ("New words: a line this mod adds to the scene's text file ({file}), in every language "
                  "the game has it in.")
NO_TEXT_FILE = "The game's files don't say which text file this scene's words are in."
#: A Speak node's recording (Zodi, 19 October: the Speak boxes' lines are the
#: Sounds page's voice tracks), and what a mark in its words does.
VOICE_LABEL = "Voice"
NO_VOICE = "This line has no voice recording."
PLAY_VOICE = "Play"
OPEN_IN_SOUNDS = "Open in Sounds"
#: With Voices ticked, Play forward waits for every voice of the event
#: (Zodi, 19 October: "you should only be allowed to play the event forward
#: if all voice lines are ready").
VOICES_GETTING_READY = ("Getting the event's voices ready: {ready} of {total}. Play forward starts once they all "
                        "are; untick Voices to play without them.")
VOICES_NEED_AUDIOMOG = ("The voices can't be opened: AudioMog couldn't be found (set it under General Setup, "
                        "Advanced options). Untick Voices to play the event without them.")
MARKS_NOTE = ("Words in < > are the game's marks and aren't shown: speaker=\"...\" is the name over the box, "
              "stoplip stops the face's mouth.")
#: A music node's piece (Zodi, 20 October: "it would be nice if you had the
#: track names in there and a jump button to go to it in the Sounds page").
MUSIC_LABEL = "Music"
NO_PIECE = "No music: the event has no other track to switch to."
PLAY_MUSIC, STOP_MUSIC = "Play", "Stop"
#: Which two tracks an event has, and why that can't be changed here (Zodi,
#: 20 October: "If we can change what the two are or even better have it
#: support more than two tracks that would be great").
TRACKS_NOTE = ("This event's two tracks: 1, {first}; 2, {second}. The game keeps every event's two tracks "
               "in its own program, not in a file a mod changes, so which they are can't be changed here; "
               "a SwitchTrack only takes turns between them. A tune (PlayTune) plays a short piece once, "
               "and the Sounds page can replace what any piece sounds like.")
NO_TRACKS = ("The game's files don't say this event's two tracks (its setup is in the game's program; the "
             "PlayStation's copy of it, which Mod Studio reads, has events 1 to 490).")
#: Where the game's voices and music are, under the unpacked game: their being there
#: (and AudioMog) ticks Voices and Music for somebody new (`_first_ticks`).
VOICE_FOLDER, MUSIC_FOLDER = "sound/voice", "sound/music"
CANT_WRITE = "This change can't be made: {}"
END_STAYS = "The end can't be taken out: the event would never finish."
TOO_LONG = ("This event is now {size:,} bytes, and the game reads {most:,} of an event's file ({sectors} "
            "sectors), so what is past that wouldn't play.")
#: The language the words are shown and written in.
LANGUAGE = "en"
#: Nodes drawn as a stack of cards: instructions that run together.
STACKED = ("together", "camera_path", "add_together")
#: The panes' first widths: the list, the big node (the map has the rest). At
#: 1,920 wide the map then holds the transport's one row (`TransportRow`).
LIST_WIDTH, FORM_WIDTH = 280, 380
#: Their least: with the map's transport row (its least) they fit beside the
#: sidebar at the window's narrowest (`shell.MIN_WIDTH`, trap 63).
LIST_LEAST, FORM_LEAST = 200, 270
#: The share of the page's height the map and its panes have over the nodes (the mock-up's).
TOP_SHARE = 0.62


def _int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


#: The opcodes whose `line` is a line of the scene's text the event shows.
LINE_OPCODES = (0x10, 0x51, 0xEB, 0xC2)


class EventListJob(Worker):
    """The events for the Events tab: `[(number, place, first words, placeholder,
    (its scene's text files, the lines it shows))]`, the last so the page can
    tell an event whose words the mod changed."""

    def __init__(self, game_dir, mode, own: dict, lengths, sqlite_path, scenario_maps: dict,
                 map_names: dict, text_reader):
        super().__init__()
        self.game_dir, self.mode, self.own = game_dir, mode, dict(own)
        self.lengths, self.sqlite_path = lengths, sqlite_path
        self.scenario_maps, self.map_names = dict(scenario_maps), dict(map_names)
        self.text_reader = text_reader

    def run(self):
        numbers = set(es.game_script_numbers(self.game_dir, self.mode)) | set(self.own)
        out = []
        files_of = {}
        if self.sqlite_path:
            try:
                for number in sorted(numbers):
                    files_of[number] = es.scene_text_files(self.sqlite_path, number)
            except Exception:                                          # noqa: BLE001
                files_of = {}
        for number in sorted(numbers):
            data = self.own.get(number)
            try:
                if data is None:
                    data = (Path(self.game_dir) / es.script_relative(number, self.mode)).read_bytes()
                script = es.read_script(data, self.lengths, self.mode)
            except (OSError, es.ScriptError):
                out.append((number, "", "", False, ((), frozenset())))
                continue
            place = self.map_names.get(self.scenario_maps.get(number), "")
            first = ""
            line = next((es.operand(i, "line", self.mode) for i in script.instructions if i.opcode == 0x10), None)
            if line is not None:
                first = self.text_reader(files_of.get(number, []), line) or ""
            said = frozenset(es.operand(i, "line", self.mode) for i in script.instructions
                             if i.opcode in LINE_OPCODES)
            out.append((number, place, first, script.is_placeholder(), (tuple(files_of.get(number, [])), said)))
        return out


class EventEditorPage(QWidget):
    """The Event Editor page (see the module's notes)."""

    #: Open a line's recording on the Sounds page: its voice path (without a
    #: language) and the language the page shows.
    open_sound = Signal(str, str)
    #: Open a piece of music on the Sounds page: its archive's path under the game.
    open_music = Signal(str)

    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state
        self.mode = "enhanced"
        self.lengths: Optional[es.Lengths] = None
        self.number: Optional[int] = None
        self.script: Optional[es.Script] = None
        self.nodes: list = []
        self.timeline: Optional[es.Timeline] = None
        self.units: dict = {}
        self.unit_names: dict = {}
        self.sprites_of: dict = {}
        self.text_files: list = []          # the scene's text files, without the language
        self.lines: dict = {}               # {line id: PzdLine} of the scene's text, edits applied
        self.speakers: dict = {}            # {Speaker key: name}
        self.picked = -1
        #: Per event, this session: the map and battle chosen.
        self.chosen_map: dict = {}
        self.chosen_battle: dict = {}
        #: The ENTD battle whose units the event shown moves.
        self.battle: Optional[int] = None
        self._scenarios = None
        self._scenarios_key = None
        self._deployments: dict = {}
        self._musics: dict = {}
        self._list_job = None
        self._loading_form = False
        self._words_timer = QTimer(self)
        self._words_timer.setSingleShot(True)
        self._words_timer.setInterval(400)
        self._words_timer.timeout.connect(self._replay)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 10, 24, 20)
        outer.setSpacing(8)
        # The description every editing tab has, the same distance under
        # the title (`page_intro`, test_qt_app).
        outer.addLayout(page_intro(BLURB))

        self.split = QSplitter(Qt.Vertical)
        self.split.setChildrenCollapsible(False)
        outer.addWidget(self.split, 1)

        top = QWidget()
        top_row = QHBoxLayout(top)
        top_row.setContentsMargins(0, 0, 0, 0)
        # Three panes with dividers, as on Abilities and the Map Editor.
        self.panes_splitter = QSplitter(Qt.Horizontal)
        self.panes_splitter.setChildrenCollapsible(False)
        self.panes_splitter.setHandleWidth(14)
        top_row.addWidget(self.panes_splitter)
        self.split.addWidget(top)

        # The left: Events, Nodes, Ready-made.
        left = QWidget()
        left.setMinimumWidth(LIST_LEAST)
        left_column = QVBoxLayout(left)
        left_column.setContentsMargins(0, 0, 0, 0)
        left_column.setSpacing(6)
        self.tabs = QTabBar()
        self.tabs.setExpanding(True)
        # Narrowed, the names shorten rather than scroll out of sight.
        self.tabs.setUsesScrollButtons(False)
        self.tabs.setElideMode(Qt.ElideRight)
        for name in ("Events", "Nodes", "Ready-made"):
            self.tabs.addTab(name)
        left_column.addWidget(self.tabs)
        self.stack = QStackedWidget()
        events = QWidget()
        events_column = QVBoxLayout(events)
        events_column.setContentsMargins(0, 0, 0, 0)
        events_column.setSpacing(6)
        self.event_search = QLineEdit()
        self.event_search.setPlaceholderText("Search events, by number, place or words")
        self.event_search.setClearButtonEnabled(True)
        self.event_search.textChanged.connect(self._filter_events)
        events_column.addWidget(self.event_search)
        self.events_note = QLabel("")
        self.events_note.setProperty("role", "attention")
        self.events_note.setWordWrap(True)
        self.events_note.setVisible(False)
        events_column.addWidget(self.events_note)
        self.event_list = QListWidget()
        # Light and dark rows, an event the mod changed in green, as the Map
        # Editor's maps are (Zodi, 19 October).
        self.event_list.setAlternatingRowColors(True)
        #: Each listed event's scene text files and the lines it shows, to tell a changed one.
        self._event_said: dict = {}
        # A long place or line ends in an ellipsis; the list never scrolls sideways.
        self.event_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.event_list.setTextElideMode(Qt.ElideRight)
        self.event_list.currentItemChanged.connect(self._event_picked)
        events_column.addWidget(self.event_list, 1)
        self.stack.addWidget(events)
        # The favourites as they were left (Zodi, 19 October).
        self.node_list = NodeList(favourites=ui_settings.load().get("event_favourites", words.FAVOURITES))
        self.node_list.chosen.connect(self.add_entry)
        self.node_list.favourites_changed.connect(self._favourites_changed)
        self.stack.addWidget(self.node_list)
        self.ready_list = NodeList(ready=words.READY_MADE)
        self.ready_list.chosen.connect(self.add_entry)
        self.stack.addWidget(self.ready_list)
        left_column.addWidget(self.stack, 1)
        self.tabs.currentChanged.connect(self.stack.setCurrentIndex)
        self.panes_splitter.addWidget(left)

        # The middle: the map.
        self.map = EventMap(state)
        self.map.map_ready.connect(self._map_ready)
        self.map.map_chosen.connect(self._map_chosen)
        self.map.battle_chosen.connect(self._battle_chosen)
        self.map.frame_changed.connect(self._frame_moved)
        self.map.tile_clicked.connect(self._tile_clicked)
        self.panes_splitter.addWidget(self.map)
        # The voices: a box's recording as it opens (Voices ticked), and Play on a Speak node.
        self.voices = VoicePlayer(state, self)
        self.voices.said.connect(self._show_message)
        self.voices.started.connect(self._voice_started)
        self.voices.progress.connect(self._voices_progress)
        self.map.voice_wanted.connect(self._box_voice)
        self.map.voices_stopped.connect(self._stop_voice)
        # The voices come first: Play forward waits for them all, the clock
        # for each to end, and the face talks while it speaks (`event_voices`).
        #: The line whose voice was asked for last, and when it began (the map's clock).
        self._voice_line: Optional[int] = None
        self._voice_began: Optional[float] = None
        self.map.forward_ready = self.voices_ready
        self.map.voice_now = self.voice_now
        #: While the page ticks Voices or Music itself for somebody new (`_first_ticks`): not saved.
        self._ticking_for_them = False
        # The tick as it was left (Zodi, 19 October: "you have my ok").
        self.map.voices.setChecked(bool(ui_settings.load().get("event_voices", False)))
        self.map.voices.toggled.connect(self._voices_ticked)
        # The event's music, with Music ticked, playing forward, and Play on a
        # music node (`event_music`); the tick as it was left too (Zodi, 20
        # October: "yes").
        self.music = MusicPlayer(state, self)
        self.music.said.connect(self._show_message)
        self.music.changed.connect(self._music_changed)
        self.map.music.setChecked(bool(ui_settings.load().get("event_music", False)))
        self.map.music.toggled.connect(self._music_ticked)
        self.map.music_stopped.connect(self.music.stop)
        self.map.frame_changed.connect(self._music_follow)
        #: Each music instruction's piece, `{id(instruction): MusicPlayed}` (`_replay`).
        self._music_of: dict = {}
        #: The pieces' names (`event_scripts.music_titles`), read with the database.
        self.music_titles: dict = {}
        self._music_titles_from = None

        # The right: the big node, a card as the mock-up draws it: its band
        # across the top, its fields (which scroll when the window is short),
        # and at its foot what it does and its buttons, always in sight.
        self.form = QFrame()
        self.form.setObjectName("bigNode")
        self.form.setMinimumWidth(FORM_LEAST)
        card = QVBoxLayout(self.form)
        card.setContentsMargins(2, 2, 2, 2)
        card.setSpacing(0)
        self.band = NodeBand()
        card.addWidget(self.band)
        self.form_scroll = QScrollArea()
        self.form_scroll.setWidgetResizable(True)
        self.form_scroll.setFrameShape(QFrame.NoFrame)
        # The node's fields narrow with the pane; they never scroll across.
        self.form_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inside = QWidget()
        self.form_column = QVBoxLayout(inside)
        self.form_column.setContentsMargins(12, 10, 12, 6)
        self.form_column.setSpacing(6)
        self.form_scroll.setWidget(inside)
        card.addWidget(self.form_scroll, 1)
        foot = QWidget()
        self.foot_column = QVBoxLayout(foot)
        self.foot_column.setContentsMargins(12, 0, 12, 12)
        self.foot_column.setSpacing(6)
        card.addWidget(foot)
        self.panes_splitter.addWidget(self.form)
        self.panes = abilities_page._Panes(self.panes_splitter)
        self.panes.list_width, self.panes.form_width = LIST_WIDTH, FORM_WIDTH

        # Under them: the nodes.
        bottom = QWidget()
        bottom_column = QVBoxLayout(bottom)
        bottom_column.setContentsMargins(0, 0, 0, 0)
        bottom_column.setSpacing(4)
        head = QHBoxLayout()
        nodes_title = QLabel("Nodes")
        nodes_title.setStyleSheet("font-weight: 600;")
        head.addWidget(nodes_title)
        head_note = QLabel(NODES_HEAD)
        head_note.setProperty("role", "muted")
        head_note.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        head.addWidget(head_note, 1)
        gold = QLabel(GOLD_NOTE)
        gold.setProperty("role", "muted")
        head.addWidget(gold)
        bottom_column.addLayout(head)
        self.strip = NodeStrip()
        self.strip.picked.connect(self.pick_node)
        self.strip.play_from.connect(self.play_from)
        self.strip.moved.connect(self.move_node)
        self.strip.dropped.connect(self.drop_entry)
        self.strip_scroll = QScrollArea()
        self.strip_scroll.setWidgetResizable(True)
        self.strip_scroll.setWidget(self.strip)
        self.strip_scroll.setMinimumHeight(140)
        bottom_column.addWidget(self.strip_scroll, 1)
        self.message = QLabel("")
        self.message.setProperty("role", "muted")
        self.message.setWordWrap(True)
        self.message.setVisible(False)
        bottom_column.addWidget(self.message)
        self.split.addWidget(bottom)
        self.split.setStretchFactor(0, 3)
        self.split.setStretchFactor(1, 2)
        # The mock-up's share of the height, kept as the window changes until
        # the divider is dragged: the map and its panes over about three rows
        # of nodes (`_share_height`).
        self._height_dragged = False
        self.split.splitterMoved.connect(self._height_moved)

        self._build_form()
        # The card empty until an event and a node are picked: no band, no buttons.
        self._fill_form()
        self.refresh_tree()

    # -- the share of the height ----------------------------------------------------

    def _height_moved(self, *_args) -> None:
        self._height_dragged = True

    def _share_height(self) -> None:
        """The map and its panes TOP_SHARE of the height, the nodes the rest, as in the mock-up."""
        if self._height_dragged:
            return
        total = sum(self.split.sizes())
        if total <= 0:
            return
        top = max(self.split.widget(0).minimumSizeHint().height(), round(total * TOP_SHARE))
        top = min(top, total - self.split.widget(1).minimumSizeHint().height())
        self.split.blockSignals(True)
        self.split.setSizes([top, total - top])
        self.split.blockSignals(False)

    def showEvent(self, event):                                       # noqa: N802
        super().showEvent(event)
        self._share_height()
        # Somebody new: Voices and Music ticked when their files are there now.
        self._first_ticks()
        # Back from another page: a face or balloon replaced there is read again.
        self.map._want_faces()

    def hideEvent(self, event):                                       # noqa: N802
        # Another page opened: a voice or music playing stops with the event.
        self.map.pause()
        self.voices.stop()
        self.music.stop()
        super().hideEvent(event)

    def resizeEvent(self, event):                                     # noqa: N802
        super().resizeEvent(event)
        self._share_height()

    # =========================================================================
    # The game, the mod and the list of events
    # =========================================================================

    def game_dir(self) -> Optional[Path]:
        root = getattr(self.state, "nxd_unpack_dir", None)
        return Path(root) if root and Path(root).is_dir() else None

    def sqlite_path(self):
        return getattr(self.state, "nxd_sqlite_path", None)

    def scenarios(self) -> dict:
        """`{event: Scenario}` for the PlayStation's events, from the scenario table the game keeps."""
        game = self.game_dir()
        if game is None:
            return {}
        path = game / bmaps.SCENARIO_FILE
        try:
            stamp = (str(path), path.stat().st_mtime_ns)
        except OSError:
            return {}
        if stamp != self._scenarios_key:
            try:
                rows = bmaps.read_scenarios(path.read_bytes())
            except (OSError, bmaps.BattleMapError):
                rows = []
            self._scenarios = {row.number: row for row in rows}
            self._scenarios_key = stamp
            self._deployments = {}
            self._musics = {}
        return self._scenarios or {}

    def deployment(self, number: Optional[int]) -> Optional[es.Deployment]:
        """Where the player's units stand as event `number`'s battle starts (ATTACK.OUT's squads)."""
        if number is None or number not in self.scenarios():
            return None
        if number not in self._deployments:
            self._deployments[number] = es.deployment_from_game(self.game_dir(), number)
        return self._deployments[number]

    def music_of(self, number: Optional[int]) -> tuple:
        """Event `number`'s two tracks (`event_scripts.scenario_music`), `(0, 0)` for none."""
        if number is None or number not in self.scenarios():
            return (0, 0)
        if number not in self._musics:
            self._musics[number] = es.scenario_music_from_game(self.game_dir(), number)
        return self._musics[number]

    def map_shown(self) -> Optional[int]:
        """The map the event shown is played on: the one chosen, else the scenario table's."""
        scenario = self.scenarios().get(self.number) if self.number is not None else None
        return self.chosen_map.get(self.number, scenario.map if scenario is not None and scenario.map else None)

    def own_scripts(self) -> dict:
        """`{number: bytes}`: the mod's changed and new scripts in this mode."""
        out = {}
        for rel, data in (getattr(self.state, "script_edits", {}) or {}).items():
            if data is None or not str(rel).replace("\\", "/").startswith(es.SCRIPT_FOLDERS[self.mode] + "/"):
                continue
            number = es.script_number(rel)
            if number is not None:
                out[number] = bytes(data)
        return out

    def refresh_tree(self) -> None:
        """Reads the game's events again (after an unpack, an opened mod, a new mod)."""
        self.mode = "classic" if getattr(self.state, "loaded_game_mode", None) == "classic" else "enhanced"
        game = self.game_dir()
        if game is None:
            self.lengths = None
            self.event_list.clear()
            self._show_problem(NO_GAME)
            self._clear_event()
            return
        try:
            self.lengths = es.lengths_from_game(game)
        except es.ScriptError as exc:
            self.lengths = None
            self.event_list.clear()
            self._show_problem(NO_BATTLE_BIN if not (game / es.BATTLE_BIN).is_file() else NO_LENGTHS.format(exc))
            self._clear_event()
            return
        self._show_problem("")
        self._show_message("")
        maps = {number: row.map for number, row in self.scenarios().items()}
        job = EventListJob(game, self.mode, self.own_scripts(), self.lengths, self.sqlite_path(), maps,
                           self._map_names(), self._first_words)
        self._list_job = job
        run_in_thread(job, on_finished=self._events_ready, on_failed=self._events_failed)
        if self.number is not None:
            self.show_event(self.number)

    def _map_names(self) -> dict:
        from . import map_editor as me_page
        return me_page.map_names(self.state)

    def _first_words(self, stems: list, line: int) -> Optional[str]:
        """An event's first line, as its box shows it (its marks taken out)."""
        for stem in stems:
            for entry in self._read_text(stem):
                if entry.line_id == line:
                    return words.shown_words(entry.line)
        return None

    def _events_ready(self, rows) -> None:
        self._list_job = None
        game = self.game_dir()
        if not rows and game is not None and not es.game_script_numbers(game, self.mode):
            self._show_problem(NO_SCRIPTS)
        current = self.number
        self.event_list.blockSignals(True)
        self.event_list.clear()
        self._event_said = {}
        for number, place, first, placeholder, said in rows:
            text = f"{number:03d}  {place}" if place else f"{number:03d}"
            if placeholder:
                text += "  (empty)" if place else "  Empty"
            elif first:
                text += f"\n{words._first_line(first, 48)}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, number)
            self._event_said[number] = said
            self.event_list.addItem(item)
            if number == current:
                self.event_list.setCurrentItem(item)
        self.event_list.blockSignals(False)
        self._mark_list()
        self._filter_events(self.event_search.text())

    def _events_failed(self, message: str) -> None:
        self._list_job = None
        self._show_message(message)

    def _filter_events(self, text: str) -> None:
        needle = text.strip().lower()
        for row in range(self.event_list.count()):
            item = self.event_list.item(row)
            item.setHidden(bool(needle) and needle not in item.text().lower())

    def _event_picked(self, item, _previous=None) -> None:
        if item is None:
            return
        self.show_event(int(item.data(Qt.UserRole)))

    def pick_event(self, number: int) -> bool:
        """Picks event `number` in the list, as a click would; False if the list hasn't it."""
        for row in range(self.event_list.count()):
            item = self.event_list.item(row)
            if item.data(Qt.UserRole) == number:
                self.event_list.setCurrentItem(item)
                return True
        return False

    def _show_message(self, text: str) -> None:
        """What a change couldn't do, or what it did to the event, under its nodes."""
        self.message.setText(text)
        self.message.setVisible(bool(text))

    def _show_problem(self, text: str) -> None:
        """Why there are no events to show: over the list, and on the map where the event would play."""
        self.events_note.setText(text)
        self.events_note.setVisible(bool(text))
        self.map.view.set_message(text or evm.NO_EVENT)
        self.map.view.update()

    # =========================================================================
    # One event
    # =========================================================================

    def game_script(self, number: int) -> Optional[bytes]:
        game = self.game_dir()
        if game is None:
            return None
        try:
            return (game / es.script_relative(number, self.mode)).read_bytes()
        except OSError:
            return None

    def show_event(self, number: int) -> None:
        """Reads event `number` (the mod's copy, else the game's) and plays it on its map."""
        if self.lengths is None:
            return
        data = self.own_scripts().get(number)
        if data is None:
            data = self.game_script(number)
        if data is None:
            self._clear_event()
            return
        try:
            script = es.read_script(data, self.lengths, self.mode)
        except es.ScriptError as exc:
            self._clear_event()
            self._show_message(f"Event {number:03d} can't be read: {exc}")
            return
        changed_event = number != self.number
        self.number, self.script = number, script
        if changed_event:
            self.picked = -1
            self.map.pause()
            self.map.frame = 0.0
        self.text_files = es.scene_text_files(self.sqlite_path(), number)
        self.speakers = es.speaker_names(self.sqlite_path(), LANGUAGE)
        self.map.caption_words = es.caption_words(self.sqlite_path(), LANGUAGE)
        if self._music_titles_from != self.sqlite_path():
            self.music_titles = es.music_titles(self.sqlite_path(), LANGUAGE)
            self._music_titles_from = self.sqlite_path()
            self.music.titles = self.music_titles
        self._read_lines()
        scenario = self.scenarios().get(number)
        own_map = [scenario.map] if scenario is not None and scenario.map else []
        chosen_map = self.chosen_map.get(number, own_map[0] if own_map else None)
        self.map.fill_maps(own_map, chosen_map)
        battle = self.chosen_battle.get(number)
        if battle is None and scenario is not None:
            battle = scenario.battle or scenario.scene or None
        self.map.fill_battles(self._battle_choices(scenario), battle)
        self._scene(battle)
        self.map.show_map(chosen_map)
        self._replay()

    def _clear_event(self) -> None:
        self.number = self.script = self.timeline = None
        self.nodes, self.picked = [], -1
        self.strip.set_cards([])
        self.map.set_event(None, {}, {}, {}, lambda line: None, lambda line: None, lambda u: None)
        self._fill_form()

    def _battle_choices(self, scenario) -> list:
        names = encounter_names.EncounterNames.load()
        game = self.game_dir()
        first = []
        if scenario is not None:
            for battle in (scenario.battle, scenario.scene):
                if battle and battle not in first:
                    first.append(battle)
        count = 512 + es.fifth_battle_count(game) if game is not None else 512
        out = [(None, PICK_A_BATTLE)] if not first else []
        for battle in first + [b for b in range(count) if b not in first]:
            out.append((battle, f"Battle {names.label_for(battle)}"))
        return out

    def _map_chosen(self, number: int) -> None:
        if self.number is None:
            return
        self.chosen_map[self.number] = number
        self.map.show_map(number)

    def _battle_chosen(self, battle: int) -> None:
        if self.number is None:
            return
        self.chosen_battle[self.number] = battle
        self._scene(battle)
        self._replay()

    def _map_ready(self) -> None:
        """A map was read and drawn: the scene's units placed on it again (the player's own
        stand on its tiles), and the event played on it."""
        if self.number is not None and self.script is not None:
            self._scene(self.battle)
        self._replay()

    # -- the scene's units ---------------------------------------------------------------

    def _scene(self, battle: Optional[int]) -> None:
        self.battle = battle
        entd_units = es.battle_units(self.game_dir(), battle) if battle is not None else []
        # The story characters the player deploys (Zodi, 19 October: "the
        # player can choose where to place him at the map at the start of the
        # battle"): on the battle's deployment tiles when the event is shown on
        # their map, else beside the unit they speak to, on the map's tiles
        # once it is drawn.
        shown = self.map_shown()
        deployed = self.deployment(self.number)
        if deployed is not None and deployed.map != shown:
            deployed = None
        tiles = self.map.map_tiles() if shown is not None and self.map.map_number == shown else None
        self.units = es.scene_units(entd_units, self.script.instructions if self.script else [], deployed, tiles,
                                    self.mode)
        names = self._chara_names()
        sprite_names = reference_names.sprite_set_names()
        self.unit_names, self.sprites_of = {}, {}
        for unit_id, unit in self.units.items():
            name = names.get(unit.name_id) or names.get(unit.sprite_set) if not unit.party else names.get(unit_id)
            if not name:
                found = sprite_names.get(unit.sprite_set, "")
                name = found.split(",")[0].strip() if found and unit.sprite_set < 128 else ""
            self.unit_names[unit_id] = name or f"Unit {unit_id}"
            graphic, palette = self._monster_look(unit.job)
            if unit.ghost_sprite is not None:
                sprite = unit.ghost_sprite
            else:
                sprite = us.sprite_number(unit.sprite_set, unit.job, graphic)
            colours = em.drawn_palette(sprite, unit.sprite_set, unit.palette, palette)
            self.sprites_of[unit_id] = (sprite, colours) if sprite is not None else None

    def _chara_names(self) -> dict:
        path = self.sqlite_path()
        if not path:
            return {}
        try:
            db = sqlite3.connect(f"file:{Path(path).as_posix()}?mode=ro", uri=True)
            try:
                return {k: n for k, n in db.execute(f'SELECT Key, Name FROM "CharaName-{LANGUAGE}"') if n}
            finally:
                db.close()
        except sqlite3.Error:
            return {}

    def _monster_look(self, job: int) -> tuple:
        record = self.state.records_by_id().get(job) if getattr(self.state, "job_records", None) else None
        values = dict(getattr(record, "values", {}) or {})
        values.update((getattr(self.state, "edits", {}) or {}).get(job, {}))
        return (_int(values.get("MonsterGraphic")), _int(values.get("MonsterPalette")))

    def face_sprite(self, unit_id: int):
        """The face a unit's box shows (`event_map.face_of`): a generic unit's its job's, a
        monster's in its colours (Zodi, 19 October: the Northern Sky Captain's box showed none)."""
        unit = self.units.get(unit_id)
        if unit is None:
            return None
        return evm.face_of(unit.sprite_set, unit.job, *self._monster_look(unit.job))

    # -- the scene's words ---------------------------------------------------------------

    def text_relative(self, stem: str, language: str = LANGUAGE) -> str:
        return f"{stem}.{language}.pzd"

    def _carried(self, relative: str) -> Optional[Path]:
        wanted = relative.replace("\\", "/").lower()
        for rel, source in (getattr(self.state, "other_file_replacements", {}) or {}).items():
            if str(rel).replace("\\", "/").lower() == wanted:
                return Path(source)
        return None

    def _read_text(self, stem: str, language: str = LANGUAGE) -> list:
        """A scene's text file's lines as the mod has them: its copy or the game's, edits applied."""
        relative = self.text_relative(stem, language)
        path = self._carried(relative)
        game = self.game_dir()
        if path is None and game is not None and (game / relative).is_file():
            path = game / relative
        try:
            lines = pzd_data.read_pzd(path) if path is not None else []
        except (OSError, ValueError):
            lines = []
        edits = (getattr(self.state, "pzd_edits", {}) or {}).get(relative)
        return pzd_data.apply_line_edits(lines, edits) if edits else lines

    def _scene_stems(self) -> list:
        """The scene's text files: the tables' word, else any carried or edited scenario file."""
        if self.text_files:
            return list(self.text_files)
        out = []
        stores = list((getattr(self.state, "other_file_replacements", {}) or {}).keys())
        stores += list((getattr(self.state, "pzd_edits", {}) or {}).keys())
        for rel in stores:
            rel = str(rel).replace("\\", "/")
            if rel.startswith("nxd/text/scenario/") and rel.endswith(f".{LANGUAGE}.pzd"):
                stem = rel[:-len(f".{LANGUAGE}.pzd")]
                if stem not in out:
                    out.append(stem)
        return out

    def _read_lines(self) -> None:
        self.lines = {}
        wanted = {es.operand(i, "line", self.mode) for i in (self.script.instructions if self.script else [])
                  if i.opcode in (0x10, 0x51, 0xEB, 0xC2)}
        stems = self._scene_stems()
        self._line_file = {}
        for stem in stems:
            for entry in self._read_text(stem):
                if entry.line_id not in self.lines:
                    self.lines[entry.line_id] = entry
                    self._line_file[entry.line_id] = stem
        if not self.text_files:
            # Only the files holding a line this event shows are its scene's.
            self.text_files = sorted({self._line_file[line] for line in wanted if line in self._line_file})

    def words_of(self, line: int) -> Optional[str]:
        entry = self.lines.get(line)
        return entry.line if entry is not None else None

    def speaker_of(self, line: int) -> Optional[str]:
        entry = self.lines.get(line)
        if entry is None or not entry.speaker_value:
            return None
        return self.speakers.get(entry.speaker_value)

    # =========================================================================
    # Playing it
    # =========================================================================

    def _replay(self) -> None:
        """The script played out again (after an edit, a map read, another battle)."""
        if self.script is None:
            return
        self.nodes = es.group_nodes(self.script)
        tiles = self.map.map_tiles()
        # A box is read for as long as its words are, marks left out. The
        # player's units march in a battle's scene (a scenario with squads);
        # otherwise the script says (`event_scripts.starts_marching`).
        marching = True if self.deployment(self.number) is not None else None
        self.timeline = es.play(self.script, self.units, lambda line: words.shown_words(self.words_of(line)),
                                self.map.ground_psx, tiles, self.map.map_number, marching=marching,
                                music=self.music_of(self.number))
        self._music_of = self._music_started(self.script, self.timeline)
        self.picked = min(self.picked, len(self.nodes) - 1)
        title = f"{self.number:03d}"
        scenario = self.scenarios().get(self.number)
        shown = scenario.map if scenario is not None else self.map.map_number
        place = self._map_names().get(shown, "") if shown is not None else ""
        if place:
            title += f"  {place}"
        self.map.mode = self.mode
        self.map.portrait_reads = self.portrait_reads(self.script, self.timeline)
        self.map.set_event(self.timeline, self.units, self.sprites_of, self.unit_names, self.words_of,
                           self.speaker_of, self.face_sprite, title)
        self._update_cards()
        self._fill_form()
        self._prepare_voices()
        self._prepare_music()

    def scene_words(self) -> words.Scene:
        return words.Scene(self.unit_names, self.words_of, self.speaker_of, self._map_names(),
                           music=self.piece_of, music_titles=self.music_titles)

    @staticmethod
    def portrait_reads(script: es.Script, timeline: es.Timeline) -> list:
        """`[(frame, block)]`: when the event reads a block of event faces ("Portraits read",
        0x50), the faces its boxes' portraits 1 to 8 show (`event_map.box_face`)."""
        return [(float(timeline.starts[index]), int(es.operand(item, "row") or 0))
                for index, item in enumerate(script.instructions)
                if item.opcode == 0x50 and index < len(timeline.starts)]

    @staticmethod
    def _music_started(script: es.Script, timeline: es.Timeline) -> dict:
        """`{id(instruction): MusicPlayed}`: the piece each music instruction starts (a SwitchTrack,
        a PlayTune, Altima's), as the timeline played it; a SwitchTrack with no other track, none."""
        out = {}
        for index, item in enumerate(script.instructions):
            if item.opcode not in (0x22, 0x84, 0x43) or index >= len(timeline.starts):
                continue
            # The timeline keeps whole frames where an instruction starts; a
            # piece starts on the frame the instruction runs (a part of one,
            # after a walk), so within one of it.
            frame = timeline.starts[index]
            tune = item.opcode == 0x84
            found = [played for played in timeline.music
                     if abs(played.start - frame) < 1.0 and (played.slot == 0) == tune]
            out[id(item)] = min(found, key=lambda played: abs(played.start - frame)) if found else None
        return out

    def piece_of(self, item: es.Instruction) -> Optional[es.MusicPlayed]:
        """The piece a music instruction starts as the event plays, or None."""
        return self._music_of.get(id(item))

    def _update_cards(self) -> None:
        scene = self.scene_words()
        cards = []
        for node in self.nodes:
            title, detail = words.node_words(self.script, node, scene)
            band, colour = words.band_words(self.script, node)
            cards.append(Card(node.kind, title, detail, words.node_problem(node, self.timeline, scene), band,
                              colour, node.shape in STACKED))
        self.strip.set_cards(cards)
        self.strip.set_chosen(self.picked)
        self._frame_moved(self.map.frame)

    def _frame_moved(self, frame: float) -> None:
        if self.timeline is None:
            self.strip.set_playing(-1)
            return
        node = self.map.node if self.map.node is not None else self.timeline.node_at(frame)
        self.strip.set_playing(node)

    def pick_node(self, index: int) -> None:
        """A node picked in the strip: shown on the right, the map at its start."""
        if not 0 <= index < len(self.nodes):
            return
        self.picked = index
        self.strip.set_chosen(index)
        self.map.pause()
        if self.timeline is not None:
            self.map.set_frame(self.timeline.node_starts[index], index)
        self._fill_form()

    def play_from(self, index: int) -> None:
        if self.timeline is None or not 0 <= index < len(self.nodes):
            return
        self.pick_node(index)
        self.map.play(1)

    # =========================================================================
    # Changing it
    # =========================================================================

    def _store(self, script: es.Script) -> None:
        """The script after a change: kept in the mod if it differs from the game's, and played again."""
        rel = es.script_relative(self.number, self.mode)
        data = script.to_bytes()
        if data == self.game_script(self.number):
            self.state.script_edits.pop(rel, None)
        else:
            self.state.script_edits[rel] = data
        self.script = script
        most = es.MOST_BYTES[self.mode]
        self._show_message(TOO_LONG.format(size=script.code_size(), most=most, sectors=most // 2048)
                           if script.code_size() > most else "")
        self._replay()
        self._mark_list()

    def edited_events(self) -> set:
        """The listed events the mod changed: their scripts, or the words of a line they show."""
        out = set(self.own_scripts())
        changed: dict = {}
        for relative, lines in (getattr(self.state, "pzd_edits", {}) or {}).items():
            relative = str(relative).replace("\\", "/")
            stem, _dot, _rest = relative.rpartition(".pzd")[0].rpartition(".")
            if stem and lines:
                changed.setdefault(stem, set()).update(lines)
        for number, (stems, said) in self._event_said.items():
            if any(changed.get(stem, set()) & said for stem in stems):
                out.add(number)
        return out

    def _mark_list(self) -> None:
        """Each listed event the mod changed in green, as other pages' lists mark theirs."""
        edited = self.edited_events()
        for row in range(self.event_list.count()):
            item = self.event_list.item(row)
            mine = item.data(Qt.UserRole) in edited
            actions.mark_edited(item, mine)
            item.setToolTip("Changed in this mod" if mine else "")

    def _can_change(self) -> bool:
        return self.script is not None and self.lengths is not None

    def move_node(self, index: int, before: int) -> None:
        if not self._can_change():
            return
        node = self.nodes[index]
        if any(self.script.instructions[i].opcode == es.END for i in node.indexes()):
            self._show_message(END_STAYS)
            return
        script = es.move_node(self.script, self.nodes, index, before)
        if not es.ends_properly(script, self.lengths):
            self._show_message(CANT_WRITE.format("a jump would lose its mark."))
            return
        self._show_message("")
        self.picked = before if before < index else before - 1
        self._store(script)

    def remove_node(self, index: int) -> None:
        if not self._can_change() or not 0 <= index < len(self.nodes):
            return
        node = self.nodes[index]
        if any(self.script.instructions[i].opcode == es.END for i in node.indexes()):
            self._show_message(END_STAYS)
            return
        script = es.replace_node(self.script, self.nodes, index, [])
        if not es.ends_properly(script, self.lengths):
            self._show_message(CANT_WRITE.format("a jump would lose its mark."))
            return
        self._show_message("")
        self.picked = min(index, len(self.nodes) - 2)
        self._store(script)

    def copy_node(self, index: int) -> None:
        if not self._can_change() or not 0 <= index < len(self.nodes):
            return
        items = list(es.node_instructions(self.script, self.nodes[index]))
        copied = []
        for item in items:
            if item.opcode == 0x10:
                line = es.operand(item, "line", self.mode)
                item = es.with_operands(item, self.mode, line=self.new_line(self.words_of(line) or "",
                                                                            like=line))
            copied.append(item)
        script = es.insert_instructions(self.script, self.nodes, index + 1, copied)
        self.picked = index + 1
        self._store(script)

    def add_entry(self, key: str) -> None:
        """A node of the list double clicked: added after the node picked (or at the end)."""
        before = self.picked + 1 if self.picked >= 0 else len(self.nodes)
        self.drop_entry(key, before)

    def drop_entry(self, key: str, before: int) -> None:
        if not self._can_change():
            return
        made = []
        keys = [key]
        if key.startswith("ready:"):
            ready = next((r for r in words.READY_MADE if r.key == key.split(":", 1)[1]), None)
            keys = list(ready.entries) if ready else []
        unit_ids = [u for u in self.units if self.units[u].shown or True]
        tile = self._a_tile()
        for entry in keys:
            made += words.build_entry(entry, self.lengths, self.mode, unit_ids, lambda: self.new_line(""), tile)
        if not made:
            return
        script = es.insert_instructions(self.script, self.nodes, before, made)
        self.picked = min(before, len(es.group_nodes(script)) - 1)
        self._store(script)

    def _a_tile(self) -> tuple:
        """A tile for a new node: the first unit's, else the map's first."""
        for unit in self.units.values():
            return (unit.x, unit.y)
        tiles = self.map.map_tiles()
        return min(tiles) if tiles else (0, 0)

    def _tile_clicked(self, x: int, y: int, level: int) -> None:
        """A tile clicked on the map: the picked node's tile, if it has one."""
        if not self._can_change() or not 0 <= self.picked < len(self.nodes):
            return
        node = self.nodes[self.picked]
        items = list(es.node_instructions(self.script, node))
        for n, item in enumerate(items):
            names = {spec.name for spec in es.layout(item.opcode, self.mode)}
            if item.opcode in (0x28, 0x5F, 0x69, 0x47) and {"x", "y"} <= names:
                values = {"x": x, "y": y}
                if "level" in names:
                    values["level"] = level
                items[n] = es.with_operands(item, self.mode, **values)
                script = es.replace_node(self.script, self.nodes, self.picked, items)
                self._store(script)
                return

    def set_operand(self, instruction: int, name: str, value: int) -> None:
        """One field of one instruction changed in the big node."""
        if not self._can_change() or self._loading_form:
            return
        items = list(self.script.instructions)
        try:
            items[instruction] = es.with_operands(items[instruction], self.mode, **{name: value})
        except es.ScriptError as exc:
            self._show_message(CANT_WRITE.format(exc))
            return
        self._show_message("")
        self._store(self.script.with_instructions(items))

    def set_button_wait(self, waits: bool) -> None:
        """A Speak node's "Wait for a button press": the wait for the message after it, or none."""
        if not self._can_change() or self._loading_form or not 0 <= self.picked < len(self.nodes):
            return
        node = self.nodes[self.picked]
        items = list(es.node_instructions(self.script, node))
        head = [i for i in items if not (i.opcode == 0xE5 and es.operand(i, "task", self.mode) == es.TASK_MESSAGE)]
        if waits:
            head.append(es.make(0xE5, self.lengths, self.mode, task=es.TASK_MESSAGE))
        self._store(es.replace_node(self.script, self.nodes, self.picked, head))

    # -- words ------------------------------------------------------------------------

    def text_languages(self, stem: str) -> list:
        """The languages a scene's text file is in, in the game or the mod."""
        out = []
        game = self.game_dir()
        for language in pzd_data.PZD_LANGUAGES:
            relative = self.text_relative(stem, language)
            if self._carried(relative) is not None or (game is not None and (game / relative).is_file()) \
                    or relative in (getattr(self.state, "pzd_edits", {}) or {}):
                out.append(language)
        return out or [LANGUAGE]

    def new_line(self, text: str, like: Optional[int] = None) -> int:
        """A new line of the scene's text with `text`, in every language: its id."""
        stems = self.text_files or self._scene_stems()
        if not stems:
            stems = [f"nxd/text/scenario/scenario{9000 + (self.number or 0):04d}"]
            self.text_files = list(stems)
        stem = stems[0]
        highest = 0
        for language in self.text_languages(stem):
            highest = max(highest, es.next_line_id(self._read_text(stem, language)))
        line = max(highest, es.next_line_id(list(self.lines.values())))
        model = self.lines.get(like) if like is not None else None
        fields = {pzd_data.ADDED_LINE: True, "line": text}
        if model is not None:
            fields.update(speaker_type=model.speaker_type, speaker_value=model.speaker_value)
        for language in self.text_languages(stem):
            relative = self.text_relative(stem, language)
            self.state.pzd_edits.setdefault(relative, {})[line] = dict(fields)
        self._read_lines()
        return line

    def set_words(self, line: int, text: str) -> None:
        """A line's words changed in the big node, in the language shown (a new line's in every one)."""
        stem = self._line_file.get(line) if hasattr(self, "_line_file") else None
        if stem is None:
            return
        relative = self.text_relative(stem)
        edits = self.state.pzd_edits.setdefault(relative, {})
        current = edits.get(line, {})
        if current.get(pzd_data.ADDED_LINE):
            for language in self.text_languages(stem):
                other = self.state.pzd_edits.setdefault(self.text_relative(stem, language), {})
                if line in other:
                    other[line]["line"] = text
        else:
            game_lines = {e.line_id: e for e in self._game_text(stem)}
            if line in game_lines and game_lines[line].line == text:
                current.pop("line", None)
                if current:
                    edits[line] = current
                else:
                    edits.pop(line, None)
                if not edits:
                    self.state.pzd_edits.pop(relative, None)
            else:
                current["line"] = text
                edits[line] = current
        self._read_lines()
        self._mark_list()
        self._words_timer.start()

    def _game_text(self, stem: str) -> list:
        relative = self.text_relative(stem)
        path = self._carried(relative)
        game = self.game_dir()
        if path is None and game is not None and (game / relative).is_file():
            path = game / relative
        try:
            return pzd_data.read_pzd(path) if path is not None else []
        except (OSError, ValueError):
            return []

    # =========================================================================
    # The big node
    # =========================================================================

    def _build_form(self) -> None:
        """The big node: as the mock-up draws it, its title and what it does,
        its fields, then at its foot a line, when it plays (or what is wrong
        with it), and Play from here, Copy and Remove."""
        self.empty_note = QLabel("")
        self.empty_note.setProperty("role", "muted")
        self.empty_note.setWordWrap(True)
        self.empty_note.setAlignment(Qt.AlignCenter)
        self.node_title = QLabel("")
        self.node_title.setStyleSheet("font-weight: 600; font-size: 12pt;")
        self.node_title.setWordWrap(True)
        self.form_column.addWidget(self.node_title)
        self.node_blurb = QLabel("")
        self.node_blurb.setProperty("role", "muted")
        self.node_blurb.setWordWrap(True)
        self.form_column.addWidget(self.node_blurb)
        self.fields_holder = QWidget()
        self.fields = QVBoxLayout(self.fields_holder)
        self.fields.setContentsMargins(0, 4, 0, 4)
        self.fields.setSpacing(6)
        self.form_column.addWidget(self.fields_holder)
        self.form_column.addStretch(1)
        self.form_column.addWidget(self.empty_note)
        # As much room under the words as over them: they sit in the card's middle.
        self.empty_stretch = QWidget()
        self.empty_stretch.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.form_column.addWidget(self.empty_stretch, 1)
        self.foot_line = Line()
        self.foot_column.addWidget(self.foot_line)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.foot_column.addWidget(self.status)
        self.buttons = QWidget()
        buttons = QHBoxLayout(self.buttons)
        buttons.setContentsMargins(0, 2, 0, 0)
        buttons.setSpacing(6)
        self.play_here = QPushButton("Play from here")
        self.play_here.clicked.connect(lambda: self.play_from(self.picked))
        self.copy_button = QPushButton("Copy")
        self.copy_button.clicked.connect(lambda: self.copy_node(self.picked))
        self.remove_button = QPushButton("Remove")
        self.remove_button.clicked.connect(lambda: self.remove_node(self.picked))
        for button in (self.play_here, self.copy_button, self.remove_button):
            buttons.addWidget(button, 1)
        self.foot_column.addWidget(self.buttons)
        self.field_widgets: dict = {}

    def _clear_fields(self) -> None:
        while self.fields.count():
            item = self.fields.takeAt(0)
            widget = item.widget()
            if widget is not None:
                # Out of the page at once, its signals quiet: a field of the
                # node shown before must not write into the one shown now.
                widget.blockSignals(True)
                for child in widget.findChildren(QWidget):
                    child.blockSignals(True)
                widget.setParent(None)
                widget.deleteLater()
        self.field_widgets = {}

    def _fill_form(self) -> None:
        self._loading_form = True
        try:
            self._clear_fields()
            has = self.script is not None and 0 <= self.picked < len(self.nodes)
            for button in (self.play_here, self.copy_button, self.remove_button):
                button.setEnabled(has)
            # With no node, the card says what to do and nothing else: no
            # band, no buttons, its words in the middle.
            for part in (self.band, self.node_title, self.node_blurb, self.fields_holder, self.foot_line,
                         self.status, self.buttons):
                part.setVisible(has)
            self.empty_note.setVisible(not has)
            self.empty_stretch.setVisible(not has)
            if not has:
                self.form.setStyleSheet("#bigNode { border: 1px solid palette(mid); border-radius: 8px; }")
                self.empty_note.setText(PICK_A_NODE if self.script is not None else PICK_AN_EVENT)
                self.node_title.setText("")
                self.node_blurb.setText("")
                self.status.setText("")
                return
            node = self.nodes[self.picked]
            label, colour = words.band_words(self.script, node)
            self.band.set_words(label, f"Node {self.picked + 1} of {len(self.nodes)}", colour)
            # The picked node drawn as a big node: its color round it, as the strip's card has.
            self.form.setStyleSheet(f"#bigNode {{ border: 2px solid {colour}; border-radius: 8px; }}")
            scene = self.scene_words()
            title, detail = words.node_words(self.script, node, scene)
            self.node_title.setText(title)
            self.node_blurb.setText(self._node_blurb(node))
            items = es.node_instructions(self.script, node)
            if node.shape == "speak":
                self._speak_fields(node, items)
            else:
                for offset, item in enumerate(items):
                    self._instruction_fields(node.first + offset, item, len(items) > 1)
            self._say_status(node)
        finally:
            self._loading_form = False

    def _node_blurb(self, node: es.Node) -> str:
        first = self.script.instructions[node.first].opcode
        for entry in words.ENTRIES:
            if entry.key == {0x10: "speak", 0x51: "words", 0x28: "walk", 0x2D: "turn", 0x19: "camera",
                             0x5F: "place", 0x11: "pose", 0x45: "add", 0x44: "show", 0x46: "hide",
                             0x98: "teleport_in", 0x94: "teleport_out", 0x4D: "map_in", 0x21: "sound",
                             0x22: "music", 0x7C: "stop_sounds", 0xF1: "wait", 0x16: "button",
                             0x29: "until_arrives", 0x2A: "together", 0x4C: "change_map",
                             0x1D: "camera_path", 0x1F: "camera_on", 0x53: "face"}.get(first):
                return entry.blurb
        return ""

    def _say_status(self, node: es.Node) -> None:
        problem = words.node_problem(node, self.timeline, self.scene_words())
        if problem:
            self.status.setText(problem)
            self.status.setStyleSheet(f"color: {theme.current()['danger']};")
            return
        start = self.timeline.node_starts[self.picked] if self.timeline else 0
        waits = [self.timeline.waits_for_button.get(i) for i in node.indexes()] if self.timeline else []
        button = any(w is not None for w in waits)
        text = f"Ready. Shows at {start / es.FRAMES_A_SECOND:.1f} seconds"
        text += ", until a button is pressed." if button else "."
        self.status.setText(text)
        self.status.setStyleSheet(f"color: {theme.current()['ok']};")

    def _row(self, label: str, widget: QWidget) -> None:
        holder = QWidget()
        column = QVBoxLayout(holder)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(2)
        caption = QLabel(label)
        caption.setProperty("role", "muted")
        column.addWidget(caption)
        column.addWidget(widget)
        self.fields.addWidget(holder)

    def _unit_box(self, value: int, group: bool = False) -> QComboBox:
        box = _combo()
        if group:
            box.addItem("Everyone", es.EVERY_UNIT)
        for unit_id in sorted(self.units):
            box.addItem(f"{self.unit_names.get(unit_id, f'Unit {unit_id}')} (unit {unit_id})", unit_id)
        if box.findData(value) < 0:
            box.addItem(words.Scene(self.unit_names).unit(value) + f" (unit {value})", value)
        box.setCurrentIndex(box.findData(value))
        return box

    def _speak_fields(self, node: es.Node, items: list) -> None:
        index = node.first
        item = items[0]
        v = es.operands(item, self.mode)
        who = self._unit_box(v["unit"])
        who.currentIndexChanged.connect(lambda _i, b=who: self.set_operand(index, "unit", b.currentData()))
        self._row("Who speaks", who)
        self.field_widgets["unit"] = who
        text = QPlainTextEdit()
        text.setPlainText(self.words_of(v["line"]) or "")
        text.setMinimumHeight(64)
        text.setMaximumHeight(84)
        line = v["line"]
        text.textChanged.connect(lambda t=text, l=line: self.set_words(l, t.toPlainText()))
        self._row("What they say", text)
        self.field_widgets["line"] = text
        stem = getattr(self, "_line_file", {}).get(line)
        relative = self.text_relative(stem) if stem else None
        added = bool(relative and (self.state.pzd_edits.get(relative, {}).get(line) or {}).get(pzd_data.ADDED_LINE))
        note = QLabel(NEW_WORDS_NOTE.format(file=Path(stem).name) if added else
                      (WORDS_NOTE.format(line=line, file=Path(stem).name) if stem else NO_TEXT_FILE))
        note.setProperty("role", "muted")
        note.setWordWrap(True)
        self.fields.addWidget(note)
        if "<" in (self.words_of(line) or ""):
            marks = QLabel(MARKS_NOTE)
            marks.setProperty("role", "muted")
            marks.setWordWrap(True)
            self.fields.addWidget(marks)
            self.field_widgets["marks"] = marks
        self._voice_row(line)
        grid = QGridLayout()
        # In line with the fields above it, not set in by a holder's margins.
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        kind = _combo()
        kind.addItem("Speech box", 1)
        # The kind most boxes in battles are: the game puts it above or below
        # by which way its speaker faces the camera, whatever Where says.
        kind.addItem("Speech box, placed by facing", es.FACING_KIND >> 4)
        kind.setItemData(1, "Above or below as the speaker faces the camera, as most boxes in battles are",
                         Qt.ToolTipRole)
        current_kind = (v["box"] >> 4) & 7
        if kind.findData(current_kind) < 0:
            kind.addItem(f"Box kind {current_kind}", current_kind)
        kind.setCurrentIndex(kind.findData(current_kind))
        kind.currentIndexChanged.connect(lambda _i, b=kind: self._set_box_bits(index, 0x70, b.currentData() << 4))
        where = _combo()
        for value, text_ in words.WINDOWS.items():
            where.addItem(text_[0].upper() + text_[1:], value)
        where.setCurrentIndex(where.findData(v["box"] & 3))
        where.currentIndexChanged.connect(lambda _i, b=where: self._set_box_bits(index, 0x03, b.currentData()))
        if current_kind << 4 == es.FACING_KIND:
            where.setEnabled(False)
            where.setToolTip("A box placed by facing goes " + words.FACING_WHERE)
        self.field_widgets["box_kind"], self.field_widgets["box_where"] = kind, where
        grid.addWidget(self._caption("Box"), 0, 0)
        grid.addWidget(self._caption("Where"), 0, 1)
        grid.addWidget(kind, 1, 0)
        grid.addWidget(where, 1, 1)
        portrait = _combo()
        portrait.addItem("The speaker's own", 0)
        portrait.addItem("None", 9)
        if portrait.findData(v["portrait"]) < 0:
            portrait.addItem(f"Portrait {v['portrait']}", v["portrait"])
        portrait.setCurrentIndex(portrait.findData(v["portrait"]))
        portrait.currentIndexChanged.connect(lambda _i, b=portrait: self.set_operand(index, "portrait", b.currentData()))
        grid.addWidget(self._caption("Portrait"), 2, 0)
        grid.addWidget(portrait, 3, 0)
        dx, dy = self._spin(item, "dx"), self._spin(item, "dy")
        dx.valueChanged.connect(lambda value: self.set_operand(index, "dx", value))
        dy.valueChanged.connect(lambda value: self.set_operand(index, "dy", value))
        grid.addWidget(self._caption("Move the box across"), 4, 0)
        grid.addWidget(self._caption("Up or down"), 4, 1)
        grid.addWidget(dx, 5, 0)
        grid.addWidget(dy, 5, 1)
        holder = QWidget()
        holder.setLayout(grid)
        self.fields.addWidget(holder)
        # The box's own switches, two to a row where they fit, as the card is short.
        ticks = QGridLayout()
        ticks.setContentsMargins(0, 0, 0, 0)
        ticks.setHorizontalSpacing(10)
        ticks.setVerticalSpacing(4)
        for n, (bit, label) in enumerate(((0x08, "No arrow to the speaker"), (0x04, "As a thought"),
                                          (0x80, "Open until a Close the box node closes it"))):
            check = QCheckBox(label)
            check.setChecked(bool(v["box"] & bit))
            check.toggled.connect(lambda on, b=bit: self._set_box_bits(index, b, b if on else 0))
            if n < 2:
                ticks.addWidget(check, 0, n)
            else:
                ticks.addWidget(check, 1, 0, 1, 2)
        tick_holder = QWidget()
        tick_holder.setLayout(ticks)
        self.fields.addWidget(tick_holder)
        waits = QCheckBox("Wait for a button press before going on")
        waits.setChecked(any(i.opcode == 0xE5 for i in items[1:]))
        waits.toggled.connect(self.set_button_wait)
        self.fields.addWidget(waits)
        self.field_widgets["waits"] = waits
        self.field_widgets["dx"], self.field_widgets["dy"] = dx, dy

    def voice_of(self, line: int) -> str:
        """A line's recording (its `VoiceSoundPath`, without a language), or "" when it has none."""
        entry = self.lines.get(line)
        return str(getattr(entry, "voice_sound_path", "") or "") if entry is not None else ""

    def _voice_row(self, line: int) -> None:
        """The recording of a Speak node's line: its name, Play and Open in Sounds."""
        voice = self.voice_of(line)
        holder = QWidget()
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        name = QLabel(Path(voice).name.split(".")[0] if voice else NO_VOICE)
        name.setProperty("role", None if voice else "muted")
        name.setToolTip(voice)
        row.addWidget(name, 1)
        play = QPushButton(PLAY_VOICE)
        play.setEnabled(bool(voice))
        play.clicked.connect(lambda: self._play_voice(line, voice))
        row.addWidget(play)
        jump = QPushButton(OPEN_IN_SOUNDS)
        jump.setEnabled(bool(voice))
        jump.setToolTip("Open this recording on the Sounds page, to listen to it or replace it")
        jump.clicked.connect(lambda: self.open_sound.emit(voice, LANGUAGE))
        row.addWidget(jump)
        self._row(VOICE_LABEL, holder)
        self.field_widgets["voice"], self.field_widgets["voice_play"] = name, play
        self.field_widgets["voice_open"] = jump

    def _music_row(self, item: es.Instruction) -> None:
        """
        A music node's piece: its name, Play (alone, from its start) and Open
        in Sounds; and, under a SwitchTrack, the event's two tracks and why
        they can't be changed here.
        """
        played = self.piece_of(item)
        music_id = played.track if played is not None else 0
        relative = es.music_file(music_id) if music_id else None
        holder = QWidget()
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        name = QLabel(emu.music_words(music_id, self.music_titles) if music_id else NO_PIECE)
        name.setProperty("role", None if music_id else "muted")
        name.setWordWrap(True)
        name.setToolTip(relative or "")
        row.addWidget(name, 1)
        play = QPushButton(STOP_MUSIC if music_id and self.music.now == (music_id, None) else PLAY_MUSIC)
        play.setEnabled(bool(music_id))
        play.clicked.connect(lambda: self._play_music(music_id))
        row.addWidget(play)
        jump = QPushButton(OPEN_IN_SOUNDS)
        jump.setEnabled(bool(relative))
        jump.setToolTip("Open this piece on the Sounds page, to listen to it or replace it")
        jump.clicked.connect(lambda: self.open_music.emit(relative))
        row.addWidget(jump)
        self._row(MUSIC_LABEL, holder)
        self.field_widgets["music"], self.field_widgets["music_play"] = name, play
        self.field_widgets["music_open"] = jump
        if item.opcode == 0x22:
            first, second = self.timeline.music_tracks if self.timeline is not None else (0, 0)
            note = QLabel(TRACKS_NOTE.format(first=emu.music_words(first, self.music_titles),
                                             second=emu.music_words(second, self.music_titles))
                          if first or second else NO_TRACKS)
            note.setProperty("role", "muted")
            note.setWordWrap(True)
            self.fields.addWidget(note)
            self.field_widgets["music_note"] = note

    def _play_music(self, music_id: int) -> None:
        """A music node's Play: the piece alone, or Stop when it is playing."""
        if self.music.now == (music_id, None):
            self.music.stop()
            return
        self.map.pause()
        self.music.play_piece(music_id)

    def _music_changed(self, music_id: int) -> None:
        """The piece heard changed: a music node's Play says Stop while its piece plays alone."""
        play = self.field_widgets.get("music_play")
        if play is None:
            return
        shown = self.field_widgets.get("music")
        alone = self.music.now is not None and self.music.now[1] is None
        mine = alone and shown is not None and shown.text() == emu.music_words(music_id, self.music_titles)
        try:
            play.setText(STOP_MUSIC if mine else PLAY_MUSIC)
        except RuntimeError:
            pass                                    # the form was cleared since

    def voices_on_hand(self) -> bool:
        """Whether the game's voices are unpacked (`sound/voice`) and AudioMog can open them."""
        game = self.game_dir()
        return game is not None and (game / VOICE_FOLDER).is_dir() and self.voices.can_unpack()

    def music_on_hand(self) -> bool:
        """Whether the game's music is unpacked (`sound/music`) and AudioMog can open it."""
        game = self.game_dir()
        return game is not None and (game / MUSIC_FOLDER).is_dir() and self.music.can_unpack()

    def _first_ticks(self) -> None:
        """
        Voices and Music for somebody who has never ticked or unticked them
        (`ui_settings.chosen`): ticked when their files are unpacked and
        AudioMog can open them, else not (Zodi, 20 October: "Voices and Music
        should be enabled by default for first time users if they have the
        necessary files unpacked"). Looked at again each time the page is
        shown, and never saved: what they tick or untick is.
        """
        for box, key, on_hand in ((self.map.voices, "event_voices", self.voices_on_hand),
                                  (self.map.music, "event_music", self.music_on_hand)):
            if ui_settings.chosen(key):
                continue
            wanted = on_hand()
            if box.isChecked() != wanted:
                self._ticking_for_them = True
                try:
                    box.setChecked(wanted)
                finally:
                    self._ticking_for_them = False

    def _music_ticked(self, on: bool) -> None:
        """Music ticked: kept for next time, the event's pieces got ready; unticked, the music stops."""
        if not self._ticking_for_them:
            ui_settings.save(event_music=on)
        if on:
            self._prepare_music()
        else:
            self.music.forget_ahead()
            self.music.stop()

    def _prepare_music(self) -> None:
        """With Music ticked, every piece the event plays, unpacked one after another (`MusicPlayer.prepare`)."""
        if not self.map.music.isChecked() or self.timeline is None:
            return
        pieces = []
        for played in self.timeline.music:
            if played.track not in pieces:
                pieces.append(played.track)
        self.music.prepare(pieces)

    def _music_follow(self, frame: float) -> None:
        """Playing forward with Music ticked: the music the event plays at the frame shown."""
        if not self.map.music.isChecked() or self.timeline is None or self.map.direction <= 0:
            return
        self.music.follow(es.music_now(self.timeline, frame), frame)

    def _box_voice(self, box) -> None:
        """A box opened while playing forward with Voices ticked: its line's recording."""
        voice = self.voice_of(box.line)
        self._voice_line, self._voice_began = (box.line if voice else None), None
        if voice and not self.voices.play(voice, LANGUAGE):
            self._voice_line = None

    def _play_voice(self, line: int, voice: str) -> None:
        """A Speak node's Play: its line's recording, the face of its box talking while it does."""
        self._voice_line, self._voice_began = line, None
        if not self.voices.play(voice, LANGUAGE):
            self._voice_line = None
        self.map.view.update()

    def _stop_voice(self) -> None:
        """Paused, a jump, or Voices unticked: the voice stops, and nothing is waited for."""
        self.voices.stop()
        self._voice_line, self._voice_began = None, None

    def voice_now(self) -> Optional[tuple]:
        """`(line, when its voice began on the map's clock or None while it is opened, whether it is
        still to end)` for the voice asked for last, or None (`EventMap.voice_now`)."""
        if self._voice_line is None:
            return None
        return self._voice_line, self._voice_began, self.voices.busy

    def voices_ready(self) -> tuple:
        """`(whether Play forward may start, why not)`: with Voices ticked, once every voice the
        event says is ready (`VoicePlayer.ready_counts`)."""
        if not self.map.voices.isChecked() or self.timeline is None:
            return True, ""
        ready, total = self.voices.ready_counts()
        if ready >= total:
            return True, ""
        if not self.voices.can_unpack():
            return False, VOICES_NEED_AUDIOMOG
        return False, VOICES_GETTING_READY.format(ready=ready, total=total)

    def _voices_progress(self, _ready: int, _total: int) -> None:
        """Another voice ready: Play forward and the note under the map say so."""
        self.map._update_buttons()

    def _favourites_changed(self, keys: list) -> None:
        """A node added to the favourites or taken out: kept for next time."""
        ui_settings.save(event_favourites=list(keys))

    def _voices_ticked(self, on: bool) -> None:
        """Voices ticked or not: kept for next time, and the event's recordings got ready, or not."""
        if not self._ticking_for_them:
            ui_settings.save(event_voices=on)
        if on:
            self._prepare_voices()
        else:
            self.voices.forget_ahead()
        self.map._update_buttons()

    def _prepare_voices(self) -> None:
        """With Voices ticked, every recording the event says, unpacked in the
        order it is said, so each plays as its box opens (`VoicePlayer.prepare`)."""
        if not self.map.voices.isChecked() or self.timeline is None:
            return
        said = [box.line for box in self.map.lines_said(float("-inf"), float("inf"))]
        self.voices.prepare([self.voice_of(line) for line in said], LANGUAGE)

    def _voice_started(self, _relative: str) -> None:
        """A recording began: when, for the face's talking, and the note that it was being opened goes."""
        self._voice_began = self.map.clock()
        if self.message.text() == evv.OPENING:
            self._show_message("")

    def _caption(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setProperty("role", "muted")
        return label

    def _set_box_bits(self, index: int, mask: int, value: int) -> None:
        if self._loading_form or self.script is None:
            return
        box = es.operand(self.script.instructions[index], "box", self.mode)
        if box is None or value is None:
            return
        self.set_operand(index, "box", (box & ~mask & 0xFF) | (value & mask))

    def _spin(self, item: es.Instruction, name: str) -> QSpinBox:
        spec = next(s for s in es.layout(item.opcode, self.mode) if s.name == name)
        low, high = es.operand_range(spec)
        box = QSpinBox()
        box.setRange(low, high)
        box.setValue(es.operand(item, name, self.mode))
        box.setKeyboardTracking(False)
        return box

    def _instruction_fields(self, index: int, item: es.Instruction, titled: bool) -> None:
        scene = self.scene_words()
        if titled:
            title, _detail = words.instruction_words(item, scene, self.mode)
            heading = QLabel(title)
            heading.setStyleSheet("font-weight: 600;")
            self.fields.addWidget(heading)
        specs = es.layout(item.opcode, self.mode)
        if not specs:
            if item.operands:
                raw = QLabel(" ".join(f"{b}" for b in item.operands))
                self._row(f"Its {len(item.operands)} bytes (what they mean isn't known)", raw)
            return
        for spec in specs:
            value = es.operand(item, spec.name, self.mode)
            label = words.field_label(item.opcode, spec.name)
            widget = self._field_widget(index, item, spec, value)
            if isinstance(widget, QCheckBox):
                self.fields.addWidget(widget)
            else:
                self._row(label, widget)
            self.field_widgets.setdefault(spec.name, widget)
        if item.opcode in (0x22, 0x84) or (item.opcode == 0x43
                                          and es.operand(item, "function", self.mode) == es.CALL_ALTIMA_MUSIC):
            self._music_row(item)

    def _field_widget(self, index: int, item: es.Instruction, spec, value: int) -> QWidget:
        if spec.kind in ("unit", "units"):
            box = self._unit_box(value, group=spec.kind == "units")
            box.currentIndexChanged.connect(lambda _i, b=box, n=spec.name: self.set_operand(index, n, b.currentData()))
            return box
        if spec.kind == "line":
            if value == es.CLOSE_BOX[self.mode]:
                return QLabel("Closes the box")
            text = QPlainTextEdit()
            text.setPlainText(self.words_of(value) or "")
            text.setMaximumHeight(90)
            text.textChanged.connect(lambda t=text, l=value: self.set_words(l, t.toPlainText()))
            return text
        if spec.kind == "facing":
            box = _combo()
            for number, name in words.FACINGS.items():
                box.addItem(name.capitalize(), number)
            if box.findData(value) < 0:
                box.addItem(str(value), value)
            box.setCurrentIndex(box.findData(value))
            box.currentIndexChanged.connect(lambda _i, b=box, n=spec.name: self.set_operand(index, n, b.currentData()))
            return box
        if spec.kind == "facing16":
            box = _combo()
            for number in list(range(0, 16, 2)) + [0x10, 0x11, 0x12, 0x13, 0x14]:
                box.addItem(words.sixteenth_words(number).capitalize(), number)
            if box.findData(value) < 0:
                box.addItem(words.sixteenth_words(value).capitalize(), value)
            box.setCurrentIndex(box.findData(value))
            box.currentIndexChanged.connect(lambda _i, b=box, n=spec.name: self.set_operand(index, n, b.currentData()))
            return box
        if spec.kind == "task":
            box = _combo()
            for number, name in words.TASKS.items():
                box.addItem(name, number)
            if box.findData(value) < 0:
                box.addItem(f"Task {value}", value)
            box.setCurrentIndex(box.findData(value))
            box.currentIndexChanged.connect(lambda _i, b=box: self.set_operand(index, "task", b.currentData()))
            return box
        if spec.kind in ("flag", "level"):
            check = QCheckBox(words.field_label(item.opcode, spec.name))
            check.setChecked(bool(value & 1))
            check.toggled.connect(lambda on, n=spec.name, v=value: self.set_operand(index, n, (v & ~1) | int(on)))
            return check
        box = self._spin(item, spec.name)
        box.valueChanged.connect(lambda number, n=spec.name: self.set_operand(index, n, number))
        if spec.kind == "frames":
            holder = QWidget()
            row = QHBoxLayout(holder)
            row.setContentsMargins(0, 0, 0, 0)
            row.addWidget(box)
            seconds = QLabel(words.seconds(value))
            seconds.setProperty("role", "muted")
            row.addWidget(seconds, 1)
            return holder
        return box


def _combo() -> QComboBox:
    """A dropdown of the big node: as wide as the pane lets it be, never wider than it."""
    box = QComboBox()
    box.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
    box.setMinimumContentsLength(6)
    box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    return box
