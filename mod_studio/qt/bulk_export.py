"""
Bulk export: a folder of textures to PNG, or a folder of sound archives to
WAV, laid out the way the game lays them out.

Asked for by a user - "I need bulk export of textures to PNGs ... right-click
on a directory and it will export PNGs mirroring the directory structure" -
and by Zodi for Sounds: "we should also do this for the Sounds page so users
can bulk export wav files."

**Interface code, built on the engine calls the single-file exports already
use** - `texture_data.load_game_texture_preview` and `save_image_as_png`,
`sound_data.unpack_sab_cached`, `list_tracks` and `export_track_wav`.
Whether the walk and the naming belong in the engine instead was put to Zodi
at the start of the session; with no answer by the time it was built, it was
built here, which needs no approval and moves with no behaviour change if he
would rather it lived in `mod_studio/`. Nothing in this file touches a
widget except `BulkExportRun`, so the move is a cut and a paste.

The decisions, each of which somebody could reasonably want the other way:

* **The whole game path is mirrored**, not just the folder that was clicked.
  Exporting `ui/ffto/bar` into `D:/Exports` writes
  `D:/Exports/ui/ffto/bar/texture/ui_bar_bg_00_uitx.png`. Two exports into
  one folder can then never land on each other - "texture" alone is the
  name of 55 of the 196 folders that hold textures, measured on the real
  listing - and the result lines up with where a mod would put the same
  file.
* **One naming rule for sounds, whatever the track count.** Every track is
  written as `<archive>_<NNN>.wav` in the archive's own folder - the name
  AudioMog gives it, the name the track list shows, and the name the
  single-track export already suggests. A rule that changed shape between
  one track and several would have a branch most exports never reach.
  Measured against the real game: 14,545 archives in 608 folders, no two
  sharing a name in one folder, so no two tracks can collide.
* **Existing files are left alone and counted, never overwritten.** A
  folder somebody exported into, edited in place and exported into again
  keeps their edits. It also makes a cancelled export resumable - run it
  again into the same folder and it picks up where it stopped. Files are
  written under a temporary name and renamed into place, so a cut-off run
  cannot leave a half-written file that the next run would skip as done.
* **The game's own files, never staged replacements.** A replacement is the
  author's own file already; what they cannot get without this is the
  game's.
* **One bad file does not stop the rest.** Every failure is collected with
  its reason and reported at the end, grouped by reason, so a missing
  converter reads as one line rather than four thousand.
* **On a worker thread, with progress and a Cancel.** The texture tree holds
  10,011 files and the sound tree 14,545 archives; the single-file exports
  block the interface because they are one file, and that does not scale.
  Cancel stops before the next file - one already inside FF16Tools or
  AudioMog is allowed to finish, because killing a converter mid-write is
  how half a file ends up on disk.

**`.tex` cannot be converted on the machine this is developed on** - the
bundled FF16Tools is a native Windows build that mono refuses - so the
suites run the texture half with its decode step injected (`decode=`), and
the real conversion is Zodi's to confirm on hardware. `.tga` is plain
Pillow and runs for real; so does the whole Sounds half, under mono.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QMessageBox, QProgressDialog

from .. import sound_data as sd
from .. import texture_data as td
from .workers import Worker, run_in_thread

#: The menu entries, beside the single-file wording they mirror: "Export
#: this texture as PNG..." and "Export this track as WAV...".
TEXTURE_FOLDER_LABEL = "Export this folder as PNGs..."
SOUND_FOLDER_LABEL = "Export this folder as WAVs..."

#: What a file is written as while it is being written. Renamed into place
#: once complete, so a run that is cut off never leaves a file the next run
#: would take for finished.
PARTIAL_SUFFIX = ".part"


def files_under(node) -> list:
    """
    Every file node beneath a tree node, in the tree's own order.

    Works on `TextureTreeNode` and `SoundTreeNode` alike - they are the same
    shape, which is why the two pages share a tree model. A file node given
    directly is its own one-item answer.
    """
    if node is None:
        return []
    if getattr(node, "is_file", False):
        return [node]
    found = []
    stack = [node]
    while stack:
        current = stack.pop()
        if current.is_file:
            found.append(current)
            continue
        # Reversed onto a stack, so they come off in the order drawn.
        stack.extend(reversed(current.children))
    return found


def mirrored_path(destination, relative_path: str, suffix: str) -> Path:
    """
    Where a game file lands under `destination`: its whole game-relative
    path, with the extension swapped.

    `ui/ffto/bar/texture/a.tex` into `D:/Exports` is
    `D:/Exports/ui/ffto/bar/texture/a.png` - the full path, not the part
    below the folder that was clicked. See the module docstring for why.
    """
    parts = relative_path.replace("\\", "/").strip("/").split("/")
    return Path(destination).joinpath(*parts).with_suffix(suffix)


def track_destination(destination, archive_relative_path: str,
                      track_stem: str) -> Path:
    """
    Where one track of an archive lands: the archive's own folder, mirrored,
    under the track's own name - `sound/music/music_00067.sab`'s first track
    is `<destination>/sound/music/music_00067_000.wav`.
    """
    folder = mirrored_path(destination, archive_relative_path, ".wav").parent
    return folder / f"{track_stem}.wav"


def _write_atomically(dest: Path, write) -> None:
    """Writes through a temporary name and renames it into place."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_name(dest.name + PARTIAL_SUFFIX)
    try:
        write(partial)
        os.replace(partial, dest)
    finally:
        if partial.exists():
            try:
                partial.unlink()
            except OSError:
                pass


def _empty_folder(folder: Path) -> None:
    """Removes everything inside `folder`, keeping the folder itself."""
    for entry in list(folder.iterdir()) if folder.exists() else []:
        if entry.is_dir() and not entry.is_symlink():
            shutil.rmtree(entry, ignore_errors=True)
        else:
            try:
                entry.unlink()
            except OSError:
                pass


@dataclass
class BulkExportResult:
    """What a bulk export did, file by file. Built by a worker, read by the
    report and by the suites."""

    #: "textures" or "tracks" - what `written` and `skipped` count.
    noun: str
    #: The folder the reader picked.
    destination: Path
    #: Game files the export was asked for: textures, or sound archives.
    total: int = 0
    #: How many of those were reached before a Cancel.
    processed: int = 0
    written: list = field(default_factory=list)      # destination paths
    skipped: list = field(default_factory=list)      # destination paths
    #: (game-relative path, reason) - one entry per file that failed.
    failed: list = field(default_factory=list)
    cancelled: bool = False

    def failures_by_reason(self) -> dict:
        """{reason: [paths]}, commonest reason first."""
        grouped: dict = {}
        for path, reason in self.failed:
            grouped.setdefault(reason, []).append(path)
        return dict(sorted(grouped.items(), key=lambda kv: -len(kv[1])))

    def summary(self) -> str:
        """The report's headline, in plain sentences."""
        lines = [f"Exported {len(self.written):,} {self.noun} to "
                 f"{self.destination}."]
        if self.skipped:
            lines.append(f"{len(self.skipped):,} were already there and were "
                         f"left alone.")
        if self.failed:
            lines.append(f"{len(self.failed):,} couldn't be exported - see "
                         f"the details for which and why.")
        if self.cancelled:
            lines.append(f"Stopped after {self.processed:,} of "
                         f"{self.total:,}, when Cancel was pressed.")
        return "\n".join(lines)

    def details(self) -> str:
        """Every failure, grouped under its reason."""
        blocks = []
        for reason, paths in self.failures_by_reason().items():
            blocks.append(f"{reason} ({len(paths):,})\n"
                          + "\n".join(f"    {p}" for p in paths))
        return "\n\n".join(blocks)


class _BulkWorker(Worker):
    """Cancel, shared by both kinds."""

    def __init__(self):
        super().__init__()
        self._cancel = threading.Event()

    def cancel(self) -> None:
        """Stops before the next file. Safe to call from the GUI thread."""
        self._cancel.set()

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()


class TextureExportWorker(_BulkWorker):
    """
    Converts game textures to PNG, one at a time, into a mirrored layout.

    `decode` is `texture_data.load_game_texture_preview` - the call the
    single-file export makes, and the one that sends a `.tex` through
    FF16Tools. Injectable because that converter cannot run where this is
    developed; see the module docstring.
    """

    def __init__(self, unpack_dir, relative_paths, destination, cli_path,
                 decode=None):
        super().__init__()
        self.unpack_dir = Path(unpack_dir)
        self.relative_paths = list(relative_paths)
        self.destination = Path(destination)
        self.cli_path = cli_path
        self.decode = decode or td.load_game_texture_preview

    def run(self):
        result = BulkExportResult("textures", self.destination,
                                  total=len(self.relative_paths))
        # A private folder for the converter's scratch copies, emptied after
        # every file. NOT the preview cache: an export of ten thousand files
        # through that would evict every texture somebody was working with,
        # and its 512MB bound would still be a lot of disk for nothing.
        work = Path(tempfile.mkdtemp(prefix="modstudio_png_"))
        #: What THIS run has written, so a second texture that maps to the
        #: same PNG - `a.tga` beside `a.tex`, which the game does not do but
        #: a mod could - is reported as a clash rather than counted as a
        #: file that was already there.
        written_here = set()
        try:
            for index, relative in enumerate(self.relative_paths):
                if self.cancelled:
                    result.cancelled = True
                    break
                self.log.emit(relative)
                dest = mirrored_path(self.destination, relative, ".png")
                if dest in written_here:
                    result.failed.append((
                        relative, "Another texture in this export has the "
                                  "same name, and was written first."))
                elif dest.exists():
                    result.skipped.append(dest)
                else:
                    try:
                        image = self.decode(self.unpack_dir / relative,
                                            self.cli_path, work)
                        if image is None:
                            raise ValueError("The file could not be read "
                                             "as an image.")
                        _write_atomically(
                            dest, lambda target, im=image:
                            td.save_image_as_png(im, target))
                        result.written.append(dest)
                        written_here.add(dest)
                    except Exception as exc:              # noqa: BLE001
                        result.failed.append(
                            (relative, str(exc) or type(exc).__name__))
                    finally:
                        _empty_folder(work)
                result.processed = index + 1
                self.progress.emit(index + 1, result.total)
        finally:
            shutil.rmtree(work, ignore_errors=True)
        return result


class SoundExportWorker(_BulkWorker):
    """
    Unpacks each sound archive and writes its tracks as WAV files.

    `unpack` is `sound_data.unpack_sab_cached`, pointed at a private folder
    rather than the browsing cache: an export of the whole tree would
    otherwise leave every archive in the game unpacked on disk, and that
    cache has held the wrong audio before (see `sounds.SAB_CACHE`). A fresh
    unpack of the game's own file is the only source that is certainly the
    original.

    Progress counts ARCHIVES, which is what the reader chose; the report
    counts TRACKS, which is what landed on disk.
    """

    def __init__(self, unpack_dir, relative_paths, destination, exe_path,
                 unpack=None):
        super().__init__()
        self.unpack_dir = Path(unpack_dir)
        self.relative_paths = list(relative_paths)
        self.destination = Path(destination)
        self.exe_path = exe_path
        self.unpack = unpack or sd.unpack_sab_cached

    def run(self):
        result = BulkExportResult("tracks", self.destination,
                                  total=len(self.relative_paths))
        work = Path(tempfile.mkdtemp(prefix="modstudio_wav_"))
        written_here = set()
        try:
            for index, relative in enumerate(self.relative_paths):
                if self.cancelled:
                    result.cancelled = True
                    break
                self.log.emit(relative)
                try:
                    project = self.unpack(Path(self.exe_path),
                                          self.unpack_dir / relative,
                                          relative, work)
                    tracks = sd.list_tracks(Path(project))
                    if not tracks:
                        raise ValueError("AudioMog finished but no tracks "
                                         "were found in there.")
                    for track in tracks:
                        dest = track_destination(self.destination, relative,
                                                 track.stem)
                        if dest in written_here:
                            result.failed.append((
                                f"{relative} track {track.index:03d}",
                                "Another track in this export has the same "
                                "name, and was written first."))
                        elif dest.exists():
                            result.skipped.append(dest)
                        else:
                            _write_atomically(
                                dest, lambda target, t=track:
                                sd.export_track_wav(t.wav_path, target))
                            result.written.append(dest)
                            written_here.add(dest)
                except Exception as exc:                  # noqa: BLE001
                    result.failed.append(
                        (relative, str(exc) or type(exc).__name__))
                finally:
                    _empty_folder(work)
                result.processed = index + 1
                self.progress.emit(index + 1, result.total)
        finally:
            shutil.rmtree(work, ignore_errors=True)
        return result


class BulkExportRun(QObject):
    """
    One bulk export on screen: the worker, a progress window with Cancel,
    and the report at the end.

    Shared by Textures and Sounds so the two cannot drift apart in how an
    export looks, stops, or reports.

    **Both windows are non-modal and top-level.** An export of a whole
    folder tree can run for a long time, and somebody should be able to go
    on editing - on another tab, where anything drawn on the Textures page
    itself would be out of sight. The progress window stays visible from
    any tab; the report appears wherever they are when it finishes.
    """

    #: Emitted with the `BulkExportResult` once the export has stopped, for
    #: whatever reason.
    done = Signal(object)

    def __init__(self, parent_widget, worker: _BulkWorker, heading: str):
        super().__init__(parent_widget)
        self.parent_widget = parent_widget
        self.worker = worker
        self.heading = heading
        self.result = None
        self.failure = ""
        self.progress_dialog = None
        self.report_box = None
        self._current = ""
        self._stopping = False

    @property
    def running(self) -> bool:
        return self.result is None and not self.failure

    def start(self) -> None:
        total = len(self.worker.relative_paths)
        dialog = QProgressDialog(self.heading, "Cancel", 0, max(total, 1),
                                 self.parent_widget)
        dialog.setWindowTitle("Exporting")
        dialog.setWindowModality(Qt.NonModal)
        dialog.setMinimumDuration(0)
        # Kept up until the worker says it has stopped - a progress window
        # that closed itself on the last tick would vanish before the
        # report exists to replace it.
        dialog.setAutoClose(False)
        dialog.setAutoReset(False)
        dialog.setMinimumWidth(460)
        dialog.canceled.connect(self.cancel)
        dialog.setValue(0)
        dialog.show()
        self.progress_dialog = dialog
        run_in_thread(self.worker, on_finished=self._finished,
                      on_failed=self._failed, on_progress=self._progress,
                      on_log=self._on_file)

    def cancel(self) -> None:
        """Stops before the next file; the report still comes."""
        if not self.running:
            return
        self._stopping = True
        self.worker.cancel()
        if self.progress_dialog is not None:
            self.progress_dialog.setLabelText(
                f"{self.heading}\n\nStopping after the file it is on...")

    def _on_file(self, relative: str) -> None:
        self._current = relative

    def _progress(self, done: int, total: int) -> None:
        dialog = self.progress_dialog
        if dialog is None or self._stopping:
            return
        dialog.setMaximum(max(total, 1))
        dialog.setValue(done)
        dialog.setLabelText(f"{self.heading}\n\n{done:,} of {total:,}"
                            + (f"  -  {self._current}" if self._current
                               else ""))

    def _close_progress(self) -> None:
        if self.progress_dialog is not None:
            self.progress_dialog.close()

    def _finished(self, result) -> None:
        # The result FIRST, then the window. Closing a QProgressDialog emits
        # `canceled` - which is also what makes closing it mid-export a
        # Cancel - and with the result already here `cancel()` sees nothing
        # running and does nothing, so a finished export can never be
        # reported as a stopped one.
        self.result = result
        self._close_progress()
        box = QMessageBox(self.parent_widget)
        box.setWindowTitle("Export finished" if not result.cancelled
                           else "Export stopped")
        box.setIcon(QMessageBox.Warning if result.failed
                    else QMessageBox.Information)
        box.setText(result.summary())
        if result.failed:
            box.setDetailedText(result.details())
        box.setWindowModality(Qt.NonModal)
        box.setAttribute(Qt.WA_DeleteOnClose)
        box.show()
        self.report_box = box
        self.done.emit(result)

    def _failed(self, message: str) -> None:
        # Every per-file error is caught inside `run`, so arriving here is
        # a fault in the export itself - said plainly, not swallowed.
        self.failure = message or "The export stopped unexpectedly."
        self._close_progress()
        box = QMessageBox(self.parent_widget)
        box.setWindowTitle("Export failed")
        box.setIcon(QMessageBox.Critical)
        box.setText(f"The export stopped: {self.failure}")
        box.setWindowModality(Qt.NonModal)
        box.setAttribute(Qt.WA_DeleteOnClose)
        box.show()
        self.report_box = box
        self.done.emit(None)
