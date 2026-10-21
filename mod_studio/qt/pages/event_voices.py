"""
The voices of the Event Editor's Speak nodes (Zodi, 19 October: "the Speak
boxes always correlate to a track in the Sounds page ... It would be a great
quality of life feature to integrate the Sounds to the Event Editor and
furthermore a jump button to the correlating sound track").

A line of a scene's text names its recording (`VoiceSoundPath`, read by
`pzd_data`): `sound/voice/scenario/scenario0270/vo_scenario0270_001_000.sab`,
without its language, which the archive's file name carries
(`.en.sab`, `.ja.sab`). Every line of the game has one; a line a mod adds
has none until the mod gives it one.

Playing one is what the Sounds page does to show it: AudioMog unpacks the
archive into the same cache (`sounds.SAB_CACHE`, so a recording opened on
either page is unpacked once), and its first track plays through the same
player (`audio_output.LoopPlayer`). What the mod has made of it plays
instead: its track replaced on the Sounds page (`state.sound_edits`, played
as that page plays it, with no unpacking), else its own copy of the archive.

AudioMog takes a moment for each archive, on a worker's thread, and what it
hands back comes to the player through a `_Job`: `run_in_thread` takes only
a bound method of an object living on the page's thread, which is where the
player has to be told (Zodi, 19 October, third round: "Voices are enabled but
I do not hear anything. Also clicking the Play button does not play the voice
line as well". The player gave it a lambda, which `run_in_thread` refuses, so
nothing was ever unpacked; the suite's stand-in unpack answered at once, on
the page's thread, and never met it).

So that an event's voices come as its boxes open rather than a moment after,
the page asks for all of them when Voices is ticked (`prepare`): they are
unpacked one after another, in the order they are said. Only unpacked: what
AudioMog leaves is a WAV on disk, read in a moment when its box opens, so a
long event's recordings are not all held at once (the last `KEEP_MOST` read
are).

**The voices come first** (Zodi, 19 October: "If voices are enabled then
then you should only be allowed to play the event forward if all voice
lines are ready. Furthermore, the voice line must finish before the event
editor moves on to the next node and the talking animation on the portrait
should continue until that voice line ends"): `ready_counts` says how many
of the event's recordings are ready (unpacked, or found to be beyond
getting), `progress` as each comes, and `busy` whether one asked for is
still playing or being opened, which the map waits on.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QObject, Signal

from ... import paths
from ... import pzd_data
from ... import sound_data as sd
from ..audio_output import LoopPlayer
from ..workers import run_in_thread

#: How many recordings are kept read (a voice is a few seconds, about a
#: megabyte): the last played, so going back over an event's lines is quick.
KEEP_MOST = 24

NO_AUDIOMOG = ("AudioMog couldn't be found, which plays the voices as it does on the Sounds page. "
               "It normally ships in the tools folder; set it under General Setup, Advanced options.")
NO_RECORDING = "This line's recording isn't in your unpacked game."
CANT_PLAY = "Couldn't play the voice: {}"
#: Said while a recording is unpacked for the first time, and taken away when it plays.
OPENING = "Opening the recording with AudioMog, as the Sounds page does..."


def _key(name: str, path: Path) -> tuple:
    """What a recording read is kept by: its name, its file, and the file's size and time."""
    try:
        stat = Path(path).stat()
        return name, str(path), stat.st_size, stat.st_mtime_ns
    except OSError:
        return name, str(path), None, None


def recording_path(voice_path: str, language: str) -> str:
    """The archive of a line's recording in `language`, under the unpacked game."""
    return pzd_data.voice_path_for_language(voice_path, language)


class _Job(QObject):
    """One archive being unpacked for the player: what the worker hands back,
    with the recording it was for, delivered on the page's thread (see the
    module's notes)."""

    def __init__(self, player: "VoicePlayer", key: tuple):
        super().__init__(player)
        self.player = player
        self.key = key

    def done(self, tracks) -> None:
        self.player._unpacked(self.key, tracks[0].wav_path if tracks else None)
        self.deleteLater()

    def went_wrong(self, message: str) -> None:
        self.player._failed(self.key, message)
        self.deleteLater()


class VoicePlayer(QObject):
    """Plays one line's recording at a time; `said` carries what it has to
    say in words (what went wrong, or `OPENING`), `started` each recording
    as it begins."""

    said = Signal(str)
    #: A recording started: its archive's path.
    started = Signal(str)
    #: How far getting the event's recordings ready has come: (ready, of how many).
    progress = Signal(int, int)

    def __init__(self, state, parent=None, device_factory=None, unpack: Optional[Callable] = None):
        super().__init__(parent)
        self.state = state
        self.audio = LoopPlayer(self, device_factory)
        #: The recordings read lately, the oldest let go past `KEEP_MOST`:
        #: `{(archive path, file, its size and time): Pcm16}`, so a mod's copy
        #: (or the game unpacked again) is read again; a replaced track's by its file.
        self._pcm: dict = {}
        #: What is to play when it is read: its key in `_pcm`.
        self._wanted: Optional[tuple] = None
        self._busy: set = set()
        #: The recordings unpacked this session, by their keys: the WAV each is.
        self._wavs: dict = {}
        #: The recordings asked for ahead (`prepare`), in the order they are
        #: said: `[(key, archive path, file)]`, unpacked one at a time.
        self._ahead: list = []
        self._ahead_busy: Optional[tuple] = None
        #: Every recording the last `prepare` asked for, by key, and those
        #: found to be beyond getting (their unpacking or reading failed).
        self._prepared: set = set()
        self._beyond: set = set()
        #: Whether what `play` asked for has started (else it is being opened).
        self._started = False
        #: `unpack(source, relative) -> wav path`, swappable for the suites
        #: (AudioMog can't run where they do).
        self.unpack = unpack

    def source(self, voice_path: str, language: str = "en") -> Optional[tuple]:
        """`(archive path under the game, file)`: the mod's copy, else the game's, in `language` or any."""
        game = getattr(self.state, "nxd_unpack_dir", None)
        replacements = getattr(self.state, "sound_file_replacements", {}) or {}
        for code in [language] + [c for c in pzd_data.PZD_LANGUAGES if c != language]:
            relative = recording_path(voice_path, code)
            whole = replacements.get(relative)
            if whole and Path(whole).is_file():
                return relative, Path(whole)
            if game and (Path(game) / relative).is_file():
                return relative, Path(game) / relative
        return None

    @property
    def playing(self) -> bool:
        return self.audio.playing

    @property
    def busy(self) -> bool:
        """What `play` asked for is playing, or is being opened to play."""
        return self.audio.playing or (self._wanted is not None and not self._started)

    def can_unpack(self) -> bool:
        """Whether recordings can be opened at all: AudioMog is set (or the suites' stand-in)."""
        return self.unpack is not None or getattr(self.state, "audiomog_exe_path", None) is not None

    def ready_counts(self) -> tuple:
        """`(ready, of how many)` of the recordings the last `prepare` asked for: ready when
        unpacked (or read, or replaced on the Sounds page), or found to be beyond getting."""
        ready = sum(1 for key in self._prepared
                    if key in self._wavs or key in self._pcm or key in self._beyond)
        return ready, len(self._prepared)

    def play(self, voice_path: str, language: str = "en") -> bool:
        """Plays a line's recording (unpacking it first the first time). False, and `said`, when it can't."""
        self.stop()
        found = self.source(voice_path, language) if voice_path else None
        if found is None:
            self.said.emit(NO_RECORDING)
            return False
        relative, source = found
        replaced = self.replaced_track(relative)
        if replaced is not None:
            try:
                return self._start(relative, self._read(replaced))
            except Exception as exc:                                   # noqa: BLE001
                self.said.emit(CANT_PLAY.format(str(exc) or exc.__class__.__name__))
                return False
        key = _key(relative, source)
        self._wanted = key
        pcm = self._pcm.get(key)
        if pcm is None and key in self._wavs:
            if self._wavs[key].is_file():
                pcm = self._read_wav(key)
                if pcm is None:
                    return False
            else:
                # Its unpacking was cleared away since (local_data emptied): again.
                self._wavs.pop(key)
        if pcm is not None:
            return self._start(relative, pcm)
        if key in self._busy:
            self.said.emit(OPENING)
            return True
        if self.unpack is None and getattr(self.state, "audiomog_exe_path", None) is None:
            self.said.emit(NO_AUDIOMOG)
            return False
        self.said.emit(OPENING)
        return self._unpack(key, relative, source)

    def prepare(self, voice_paths, language: str = "en") -> None:
        """Unpacks, one after another in this order, the recordings of lines
        about to be said (an event's, Voices ticked), so each is ready as its
        box opens; `progress` says how far that has come. Says nothing: one
        that can't be had is told of when it is played (a line without a
        recording isn't waited for). Takes the place of what was asked for
        ahead before."""
        self._ahead = []
        self._prepared = set()
        for voice_path in voice_paths:
            found = self.source(voice_path, language) if voice_path else None
            if found is None or self.replaced_track(found[0]) is not None:
                continue
            key = _key(*found)
            if key in self._prepared:
                continue
            self._prepared.add(key)
            if key not in self._pcm and key not in self._wavs:
                self._beyond.discard(key)
                self._ahead.append((key,) + found)
        if not self.can_unpack():
            # Nothing can open them: they stay not ready, and the page says why.
            self._ahead = []
        self.progress.emit(*self.ready_counts())
        self._next()

    def forget_ahead(self) -> None:
        """Nothing more is unpacked ahead (what is being unpacked finishes)."""
        self._ahead = []

    def _next(self) -> None:
        """The next recording asked for ahead, when none is being unpacked."""
        while self._ahead and self._ahead_busy is None:
            key, relative, source = self._ahead.pop(0)
            if key in self._pcm or key in self._wavs or key in self._busy:
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
        # Staged under the game's own name, as the Sounds page stages it: one
        # unpack for both pages, a mod's archive called whatever it is.
        worker = UnpackArchiveWorker(Path(self.state.audiomog_exe_path), source, relative,
                                     paths.local_data_dir() / SAB_CACHE, as_name=Path(relative).name,
                                     by_content=bool(whole and Path(whole) == source))
        job = _Job(self, key)
        self._busy.add(key)
        run_in_thread(worker, on_finished=job.done, on_failed=job.went_wrong)
        return True

    def replaced_track(self, relative: str) -> Optional[Path]:
        """The audio the mod puts in place of an archive's first track (the
        Sounds page's Replace), or None: a voice archive holds one track."""
        edit = ((getattr(self.state, "sound_edits", {}) or {}).get(relative) or {}).get(0)
        if isinstance(edit, dict) and edit.get("source_path"):
            return Path(edit["source_path"])
        return None

    def _read(self, path: Path):
        """A replacement's audio, read again only when the file changes."""
        key = _key("replaced", path)
        if key not in self._pcm:
            self._keep(key, sd.read_pcm16(path))
        return self._pcm[key]

    def _keep(self, key, pcm) -> None:
        self._pcm.pop(key, None)
        while len(self._pcm) >= KEEP_MOST:
            self._pcm.pop(next(iter(self._pcm)))
        self._pcm[key] = pcm

    def _unpacked(self, key: tuple, wav_path) -> None:
        if wav_path is None:
            self._failed(key, "the archive holds no tracks")
            return
        self._busy.discard(key)
        self._wavs[key] = Path(wav_path)
        self._beyond.discard(key)
        if self._wanted == key:
            pcm = self._read_wav(key)
            if pcm is not None:
                self._start(key[0], pcm)
        self._done_ahead(key)
        self.progress.emit(*self.ready_counts())

    def _read_wav(self, key: tuple):
        """An unpacked recording read (and kept), or None and `said` when it can't be."""
        try:
            pcm = sd.read_pcm16(self._wavs[key])
        except Exception as exc:                                       # noqa: BLE001
            self._wavs.pop(key, None)
            self._beyond.add(key)
            if self._wanted == key:
                self._wanted = None
                self.said.emit(CANT_PLAY.format(str(exc) or exc.__class__.__name__))
            return None
        self._keep(key, pcm)
        return pcm

    def _failed(self, key: tuple, message: str) -> None:
        self._busy.discard(key)
        self._beyond.add(key)
        if self._wanted == key:
            self._wanted = None
            self.said.emit(CANT_PLAY.format(message))
        self._done_ahead(key)
        self.progress.emit(*self.ready_counts())

    def _done_ahead(self, key: tuple) -> None:
        if self._ahead_busy == key:
            self._ahead_busy = None
            self._next()

    def _start(self, relative: str, pcm) -> bool:
        try:
            self.audio.play(pcm, 0)
        except Exception as exc:                                       # noqa: BLE001
            self._wanted = None
            self.said.emit(CANT_PLAY.format(exc))
            return False
        self._started = True
        self.started.emit(relative)
        return True

    def stop(self) -> None:
        self._wanted = None
        self._started = False
        self.audio.stop()
