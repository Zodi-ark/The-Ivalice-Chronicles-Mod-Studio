"""
The Abilities map's sounds, as The Ivalice Chronicles plays them (Zodi, 20
October, of `FID_SOUND_VFX_001A0000_WAV`, track 668: "Yes, that's Fire";
then "Yes, bring it back" of the map's Sound).

An effect's sounds are recordings in `sound/common/sound.sab`, named by the
effect's sound section (`effect_sound.vfx_name`): each starts when the
effect's timeline starts its sound (`effect_player`), and a name with
several recordings plays them together (`effect_sound.mix_recordings`).

The archive is unpacked as the Sounds page unpacks it, once, by AudioMog,
into the same cache (`sounds.SAB_CACHE`: an archive opened on either page is
unpacked once), on a worker's thread; its tracks are then known by the names
that play them (AudioMog's `TrackUsers.txt`). What the mod has made of them
plays instead: a track replaced on the Sounds page, else the mod's own copy
of the archive.

The engine's sound module (`effect_sound`) is imported where it is used, not
at the top: it needs numpy, and the window builds without it (an effect, and
so its sounds, plays only with it).
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QObject, Signal

from ... import paths
from ... import sound_data as sd
from ..workers import Worker, run_in_thread

NO_AUDIOMOG = ("AudioMog couldn't be found, which opens the game's sounds as it does on the Sounds page "
               "(set it under General Setup, Advanced options)")
NO_ARCHIVE = ("the game's sounds aren't in your unpacked game (sound/common/sound.sab): unpack it on "
              "General Setup with Sounds and music ticked")
#: Said while the archive is unpacked for the first time.
OPENING = "Opening the game's sounds with AudioMog, as the Sounds page does..."


class _Job(QObject):
    """The archive being unpacked: what the worker hands back, delivered on the page's thread."""

    def __init__(self, owner: "AbilitySounds"):
        super().__init__(owner)
        self.owner = owner

    def done(self, tracks) -> None:
        self.owner._unpacked(tracks)
        self.deleteLater()

    def went_wrong(self, message: str) -> None:
        self.owner._failed(message)
        self.deleteLater()


class AbilitySounds(QObject):
    """
    The effects' recordings: `paths_for(names)` gives each name's audio files
    once the archive is unpacked (`ready` says when), `problem` why it can't
    be, and `opening` whether it is being unpacked.
    """

    ready = Signal()

    def __init__(self, state, parent=None, unpack: Optional[Callable] = None):
        super().__init__(parent)
        self.state = state
        #: `unpack(source, relative) -> [sound_data.TrackInfo]`, swappable for the suites.
        self.unpack = unpack
        self._from: Optional[tuple] = None
        self._asked: Optional[tuple] = None
        #: The archive's file as it was when it couldn't be unpacked: not tried again until it changes.
        self._failed_for: Optional[tuple] = None
        self._tracks: dict = {}
        self._names: dict = {}
        self._busy = False
        self.problem = ""

    @property
    def opening(self) -> bool:
        return self._busy

    def source(self) -> Optional[tuple]:
        """`(archive path under the game, file)`: the mod's copy, else the game's; None without."""
        from ... import effect_sound as es
        relative = es.SOUND_ARCHIVE
        whole = (getattr(self.state, "sound_file_replacements", {}) or {}).get(relative)
        if whole and Path(whole).is_file():
            return relative, Path(whole)
        game = getattr(self.state, "nxd_unpack_dir", None)
        if game and (Path(game) / relative).is_file():
            return relative, Path(game) / relative
        return None

    def _stamp(self, found: tuple) -> tuple:
        try:
            stat = found[1].stat()
            return str(found[1]), stat.st_size, stat.st_mtime_ns
        except OSError:
            return str(found[1]), None, None

    def paths_for(self, names) -> Optional[dict]:
        """
        `{name: [audio files]}` for the recordings `names` name (a track
        replaced on the Sounds page by its replacement); None while the
        archive is being unpacked (`ready` follows), `{}` when it can't be
        (`problem` says why).
        """
        from ... import effect_sound as es
        found = self.source()
        if found is None:
            self.problem = NO_ARCHIVE
            return {}
        stamp = self._stamp(found)
        if stamp != self._from:
            if self._busy:
                return None
            if stamp == self._failed_for:
                return {}
            if self.unpack is None and getattr(self.state, "audiomog_exe_path", None) is None:
                self.problem = NO_AUDIOMOG
                return {}
            self._start(found, stamp)
            if self._busy:
                return None
            if stamp != self._from:
                return {}
        self.problem = ""
        edits = (getattr(self.state, "sound_edits", {}) or {}).get(es.SOUND_ARCHIVE) or {}
        out = {}
        for name in names:
            files = []
            for track in self._names.get(name, []):
                edit = edits.get(track)
                if isinstance(edit, dict) and edit.get("source_path") and Path(edit["source_path"]).is_file():
                    files.append(Path(edit["source_path"]))
                elif track in self._tracks:
                    files.append(self._tracks[track])
            out[name] = files
        return out

    def _start(self, found: tuple, stamp: tuple) -> None:
        relative, source = found
        self._asked = stamp
        if self.unpack is not None:
            try:
                tracks = self.unpack(source, relative)
            except Exception as exc:                                   # noqa: BLE001
                self._failed(str(exc) or exc.__class__.__name__, signal=False)
                return
            self._unpacked(tracks, signal=False)
            return
        from .sounds import SAB_CACHE, UnpackArchiveWorker
        whole = (getattr(self.state, "sound_file_replacements", {}) or {}).get(relative)
        worker = UnpackArchiveWorker(Path(self.state.audiomog_exe_path), source, relative,
                                     paths.local_data_dir() / SAB_CACHE, as_name=Path(relative).name,
                                     by_content=bool(whole and Path(whole) == source))
        self._busy = True
        job = _Job(self)
        run_in_thread(worker, on_finished=job.done, on_failed=job.went_wrong)

    def _unpacked(self, tracks, signal: bool = True) -> None:
        from ... import effect_sound as es
        self._busy = False
        self._tracks = {t.index: Path(t.wav_path) for t in tracks or []}
        self._names = es.tracks_by_name({t.stem: t.users for t in tracks or []})
        self._from = self._asked
        self.problem = ""
        if signal:
            self.ready.emit()

    def _failed(self, message: str, signal: bool = True) -> None:
        self._busy = False
        self._from = None
        self._failed_for = self._asked
        self.problem = message
        if signal:
            self.ready.emit()


class MixJob(Worker):
    """An effect's recordings read and mixed (`effect_sound.mix_recordings`):
    `(token, EffectSounds or None, what went wrong)`."""

    def __init__(self, token, events: list, frame_seconds: list, resource: Optional[int], files: dict):
        super().__init__()
        self.token, self.events, self.frame_seconds = token, list(events), list(frame_seconds)
        self.resource, self.files = resource, dict(files)

    def run(self):
        try:
            from ... import effect_sound as es
            recordings = {}
            rate = None
            for name, files in self.files.items():
                layers = []
                for path in files:
                    pcm = sd.read_pcm16(path)
                    rate = rate or pcm.sample_rate
                    layers.append((pcm.sample_rate, pcm.channels, pcm.data))
                recordings[name] = layers
            mixed = es.mix_recordings(self.events, self.frame_seconds, self.resource, recordings,
                                      rate or 48000)
        except Exception as exc:                                       # noqa: BLE001
            return (self.token, None, str(exc) or exc.__class__.__name__)
        return (self.token, mixed, "")
