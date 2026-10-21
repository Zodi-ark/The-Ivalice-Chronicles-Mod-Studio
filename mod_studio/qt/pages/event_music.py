"""
The event's music in the Event Editor (Zodi, 20 October: "is it possible to
play the music tracks that appear for the event ... If we figure it out being
able to toggle the music in the event editor like we do the Voices would be a
nice touch").

**Which music** is the engine's (`event_scripts.music_now`): an event has two
tracks, the game's setup record for it says which (`scenario_music`), and the
first plays as it begins; SwitchTrack (0x22) stops the music and starts the
other, FadeSound (0x60) fades it out, EndTrack (0x5E) stops it, PlayTune
(0x84) plays a short piece once over it, and CallFunction 12 plays Altima's.
A PlayStation music id m is the remaster's
`sound/music/music_<m less one, five digits>.sab` (`event_scripts.music_file`),
and its name is the sound test's (`BGMMode`, `event_scripts.music_titles`).

**Played** as the voices are (`event_voices`): AudioMog unpacks the archive
into the Sounds page's cache the first time, on a worker's thread, and its
track plays through the same player, looping where the recording says (its
loop points), as loud as the event has it at that moment (`MusicPlayed.volume_at`,
its fades) times `MUSIC_LEVEL`, under the voices. What the mod has made of a
track plays instead: its track replaced on the Sounds page, else its own copy
of the archive.

With Music ticked, playing forward, the piece the event plays at the frame
shown is heard from as far into it as the frame is (`follow`): a tune once,
then the event's track again. Paused, a jump, or Music unticked, it stops.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QObject, Signal

from ... import event_scripts as es
from ... import paths
from ... import sound_data as sd
from ..audio_output import LoopPlayer
from ..workers import run_in_thread

#: How loud the music is, the voices being 1: under them, as in the game.
MUSIC_LEVEL = 0.6
#: Pieces kept read: a piece of music is minutes of sound, tens of megabytes.
KEEP_MOST = 3
#: A piece restarts where the event is when the clock went back by more than this (seconds).
JUMP_BACK = 0.25

NO_AUDIOMOG = ("The music can't be opened: AudioMog couldn't be found (set it under General Setup, "
               "Advanced options).")
NO_MUSIC = "{} isn't in your unpacked game."
CANT_PLAY = "Couldn't play the music: {}"
#: Said while a piece is unpacked for the first time.
OPENING = "Opening the music with AudioMog, as the Sounds page does..."


def title_of(music_id: int, titles: dict) -> str:
    """A piece's name: the sound test's, without its number there ("2. Hall of Worship" is
    "Hall of Worship"), else "Music <id>"."""
    title = str(titles.get(music_id) or "").strip()
    number, dot, rest = title.partition(". ")
    if dot and number.isdigit() and rest.strip():
        title = rest.strip()
    return title or f"Music {music_id}"


def music_words(music_id: int, titles: dict) -> str:
    """A piece named for the page: "Hall of Worship (music 51)", "None" for 0."""
    if not music_id:
        return "None"
    title = title_of(music_id, titles)
    return title if title == f"Music {music_id}" else f"{title} (music {music_id})"


@dataclass
class Loaded:
    """A piece read: its sound, and its loop `(start, end)` in frames, or None (it plays once)."""
    pcm: sd.Pcm16
    loop: Optional[tuple]

    @property
    def seconds(self) -> float:
        return self.pcm.frames / max(1, self.pcm.sample_rate)

    def frame_at(self, seconds: float, looping: bool) -> Optional[int]:
        """The frame `seconds` in, round the loop as often as it has gone round; None past its
        end when it doesn't loop."""
        frame = int(max(0.0, seconds) * self.pcm.sample_rate)
        if looping and self.loop is not None and frame >= self.loop[1]:
            start, end = self.loop
            return start + (frame - start) % max(1, end - start)
        return frame if frame < self.pcm.frames else None


def _key(relative: str, path: Path) -> tuple:
    try:
        stat = Path(path).stat()
        return relative, str(path), stat.st_size, stat.st_mtime_ns
    except OSError:
        return relative, str(path), None, None


def _read(wav: Path) -> Loaded:
    info = sd.read_wav_info(wav)
    loop = (int(info.loop_start), int(info.loop_end)) if info.has_loop else None
    return Loaded(sd.read_pcm16(wav), loop)


class _Job(QObject):
    """One archive being unpacked, what the worker hands back delivered on the page's thread."""

    def __init__(self, player: "MusicPlayer", key: tuple):
        super().__init__(player)
        self.player = player
        self.key = key

    def done(self, tracks) -> None:
        self.player._unpacked(self.key, tracks[0].wav_path if tracks else None)
        self.deleteLater()

    def went_wrong(self, message: str) -> None:
        self.player._failed(self.key, message)
        self.deleteLater()


class MusicPlayer(QObject):
    """Plays the event's music (see the module's notes); `said` carries what it has to say in
    words, `changed` the piece now heard (0: none)."""

    said = Signal(str)
    changed = Signal(int)

    def __init__(self, state, parent=None, device_factory=None, unpack: Optional[Callable] = None):
        super().__init__(parent)
        self.state = state
        self.audio = LoopPlayer(self, device_factory)
        self._loaded: dict = {}
        self._wavs: dict = {}
        self._busy: set = set()
        self._beyond: set = set()
        self._told: set = set()
        self._ahead: list = []
        self._ahead_busy: Optional[tuple] = None
        #: A piece asked for alone (`play_piece`) while it is opened: its key and music id.
        self._wanted: Optional[tuple] = None
        #: The piece heard: `(music id, the frame the event began it)`, `(id, None)` alone, or None.
        self.now: Optional[tuple] = None
        self._last_seconds: Optional[float] = None
        #: `unpack(source, relative) -> wav path`, swappable for the suites.
        self.unpack = unpack
        #: The pieces' names (`event_scripts.music_titles`; the page sets them).
        self.titles: dict = {}

    # -- where a piece is ---------------------------------------------------------------

    def source(self, music_id: int) -> Optional[tuple]:
        """`(archive path under the game, file)`: the mod's copy, else the game's; None without."""
        relative = es.music_file(music_id)
        if relative is None:
            return None
        whole = (getattr(self.state, "sound_file_replacements", {}) or {}).get(relative)
        if whole and Path(whole).is_file():
            return relative, Path(whole)
        game = getattr(self.state, "nxd_unpack_dir", None)
        if game and (Path(game) / relative).is_file():
            return relative, Path(game) / relative
        return None

    def replaced_track(self, relative: str) -> Optional[Path]:
        """The audio the mod puts in place of a piece's track (the Sounds page's Replace), or None."""
        edit = ((getattr(self.state, "sound_edits", {}) or {}).get(relative) or {}).get(0)
        if isinstance(edit, dict) and edit.get("source_path"):
            return Path(edit["source_path"])
        return None

    def can_unpack(self) -> bool:
        return self.unpack is not None or getattr(self.state, "audiomog_exe_path", None) is not None

    @property
    def playing(self) -> bool:
        return self.audio.playing

    def length_of(self, music_id: int) -> Optional[float]:
        """How long a piece read is, in seconds; None when it isn't read yet."""
        found = self._ready(music_id, open_it=False)
        return found.seconds if isinstance(found, Loaded) else None

    # -- playing ------------------------------------------------------------------------

    def follow(self, pieces: list, frame: float) -> None:
        """
        Playing forward with Music ticked: `pieces` are what the event plays at
        `frame` (`event_scripts.music_now`); the one to hear (a tune while it
        lasts, else the event's track) plays from as far into it as the event
        is, as loud as the event has it, and goes on playing as the clock moves.
        """
        track = tune = None
        for played, seconds in pieces:
            if played.slot == 0:
                length = self.length_of(played.track)
                if length is None or seconds < length:
                    tune = (played, seconds)
            else:
                track = (played, seconds)
        chosen = tune or track
        if chosen is None:
            if self.now is not None:
                self.stop()
            return
        played, seconds = chosen
        gain = played.volume_at(frame) * MUSIC_LEVEL
        here = (played.track, played.start)
        went_back = self._last_seconds is not None and seconds < self._last_seconds - JUMP_BACK
        self._last_seconds = seconds
        if here == self.now and self.audio.playing and not went_back:
            self.audio.set_gain(gain)
            return
        self._begin(played.track, seconds, gain, looping=played.slot != 0, now=here)

    def play_piece(self, music_id: int) -> bool:
        """A piece alone, from its start, looping (a Music node's Play). False when it can't be."""
        self.stop()
        return self._begin(music_id, 0.0, MUSIC_LEVEL, looping=True, now=(music_id, None), alone=True)

    def _begin(self, music_id: int, seconds: float, gain: float, looping: bool, now: tuple,
               alone: bool = False) -> bool:
        found = self._ready(music_id, open_it=True, alone=alone)
        if not isinstance(found, Loaded):
            return found is True
        frame = found.frame_at(seconds, looping)
        if frame is None:
            self.stop()
            return False
        loop = found.loop if looping else None
        try:
            self.audio.play(found.pcm, frame, loop[0] if loop else None, loop[1] if loop else None,
                            looping=loop is not None, gain=gain)
        except Exception as exc:                                       # noqa: BLE001
            self.said.emit(CANT_PLAY.format(str(exc) or exc.__class__.__name__))
            return False
        self.now = now
        self.changed.emit(music_id)
        return True

    def _ready(self, music_id: int, open_it: bool, alone: bool = False):
        """
        A piece read (`Loaded`), True while it is being opened, or False when
        it can't be had (said once, with `open_it`).
        """
        found = self.source(music_id)
        if found is None:
            if open_it and ("missing", music_id) not in self._told:
                self._told.add(("missing", music_id))
                self.said.emit(NO_MUSIC.format(music_words(music_id, self.titles)))
            return False
        relative, path = found
        replaced = self.replaced_track(relative)
        if replaced is not None:
            key = _key("replaced", replaced)
            if key not in self._loaded:
                try:
                    self._keep(key, _read(replaced))
                except Exception as exc:                               # noqa: BLE001
                    if open_it:
                        self.said.emit(CANT_PLAY.format(str(exc) or exc.__class__.__name__))
                    return False
            return self._loaded[key]
        key = _key(relative, path)
        if key in self._loaded:
            return self._loaded[key]
        if key in self._wavs:
            try:
                self._keep(key, _read(self._wavs[key]))
                return self._loaded[key]
            except Exception as exc:                                   # noqa: BLE001
                self._wavs.pop(key, None)
                self._beyond.add(key)
                if open_it:
                    self.said.emit(CANT_PLAY.format(str(exc) or exc.__class__.__name__))
                return False
        if key in self._beyond or not open_it:
            return False
        if alone:
            self._wanted = (key, music_id)
        if key in self._busy:
            return True
        if not self.can_unpack():
            if ("audiomog",) not in self._told:
                self._told.add(("audiomog",))
                self.said.emit(NO_AUDIOMOG)
            return False
        self.said.emit(OPENING)
        return self._unpack(key, relative, path)

    def _keep(self, key: tuple, loaded: Loaded) -> None:
        self._loaded.pop(key, None)
        while len(self._loaded) >= KEEP_MOST:
            self._loaded.pop(next(iter(self._loaded)))
        self._loaded[key] = loaded

    def stop(self) -> None:
        self._wanted = None
        self._last_seconds = None
        was = self.now
        self.now = None
        self.audio.stop()
        if was is not None:
            self.changed.emit(0)

    # -- getting pieces ready -------------------------------------------------------------

    def prepare(self, music_ids) -> None:
        """Unpacks, one after another, the pieces an event plays (Music ticked), so each is
        ready when it begins. Says nothing: one that can't be had is told of when it plays."""
        self._ahead = []
        for music_id in music_ids:
            found = self.source(music_id) if music_id else None
            if found is None or self.replaced_track(found[0]) is not None:
                continue
            key = _key(*found)
            if key not in self._wavs and key not in self._loaded and key not in self._beyond:
                self._ahead.append((key,) + found)
        if not self.can_unpack():
            self._ahead = []
        self._next()

    def forget_ahead(self) -> None:
        self._ahead = []

    def _next(self) -> None:
        while self._ahead and self._ahead_busy is None:
            key, relative, source = self._ahead.pop(0)
            if key in self._wavs or key in self._loaded or key in self._busy:
                continue
            self._ahead_busy = key
            if not self._unpack(key, relative, source):
                self._ahead_busy = None

    def _unpack(self, key: tuple, relative: str, source: Path) -> bool:
        """Has AudioMog unpack an archive on a worker's thread (the suites' stand-in at once)."""
        if self.unpack is not None:
            self._busy.add(key)
            try:
                wav = self.unpack(source, relative)
            except Exception as exc:                                   # noqa: BLE001
                self._failed(key, str(exc) or exc.__class__.__name__)
                return False
            self._unpacked(key, wav)
            return True
        from .sounds import SAB_CACHE, UnpackArchiveWorker
        whole = (getattr(self.state, "sound_file_replacements", {}) or {}).get(relative)
        worker = UnpackArchiveWorker(Path(self.state.audiomog_exe_path), source, relative,
                                     paths.local_data_dir() / SAB_CACHE, as_name=Path(relative).name,
                                     by_content=bool(whole and Path(whole) == source))
        job = _Job(self, key)
        self._busy.add(key)
        run_in_thread(worker, on_finished=job.done, on_failed=job.went_wrong)
        return True

    def _unpacked(self, key: tuple, wav_path) -> None:
        if wav_path is None:
            self._failed(key, "the archive holds no tracks")
            return
        self._busy.discard(key)
        self._wavs[key] = Path(wav_path)
        if self._wanted is not None and self._wanted[0] == key:
            music_id = self._wanted[1]
            self._wanted = None
            self._begin(music_id, 0.0, MUSIC_LEVEL, looping=True, now=(music_id, None))
        self._done_ahead(key)

    def _failed(self, key: tuple, message: str) -> None:
        self._busy.discard(key)
        self._beyond.add(key)
        if self._wanted is not None and self._wanted[0] == key:
            self._wanted = None
        self.said.emit(CANT_PLAY.format(message))
        self._done_ahead(key)

    def _done_ahead(self, key: tuple) -> None:
        if self._ahead_busy == key:
            self._ahead_busy = None
            self._next()
