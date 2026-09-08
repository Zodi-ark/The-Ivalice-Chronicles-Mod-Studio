"""
Browsing, previewing, and staging replacements for the unpacked game's
.sab sound archives (music, voice lines, common SFX/UI banks - anything
under sound/), via AudioMog (github.com/Yoraiz0r/AudioMog, MIT - see
audiomog.py).

A completely different shape of feature from every other tab, closest in
spirit to Textures: no reference table or database, just real files sitting
in the unpacked game folder that Textures already points at. But unlike
.tga/.tex, a .sab can't be read/written directly at all - it's a CRIWARE
sound-archive container (HCA-encoded tracks) that only AudioMog knows how
to unpack/repack, so *every* .sab needs AudioMog set up, not just some.

Loop metadata (so replaced music keeps looping seamlessly) lives directly
inside the unpacked .wav's own standard "smpl" RIFF chunk - confirmed
against a real uploaded sample (music_00067.sab -> AudioMog ->
music_00067_000.wav): a 48kHz/16-bit/stereo PCM wav with a smpl chunk
giving LoopStart=80016, LoopEnd=4726758 samples, PlayCount=0 (infinite).
RebuildSettings.json's own UseWavFilesIfAvailable=true (already the case
on every real sample seen) means AudioMog reads loop points back out of
that same smpl chunk on repack - no separate override file needed for this
game. Voice lines are the same wav format but carry no smpl chunk at all
(they don't loop), matching Zodi's own note.

The smpl chunk is a mainstream, documented WAV extension (not proprietary
to AudioMog or this game) - see e.g. the Microsoft/EA "Multimedia
Programming Interface" RIFF spec.
"""

from __future__ import annotations

import platform
import shutil
import struct
import subprocess
import wave as wave_mod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import audiomog
from . import constants as c

SOUND_EXTENSIONS = (".sab", ".sabf", ".mab", ".mabf")  # everything AudioMog can unpack/repack


def is_sound_archive(path_or_name) -> bool:
    return str(path_or_name).lower().endswith(SOUND_EXTENSIONS)


def classify_sab_path(relative_path: str) -> str:
    """
    Informational label only, for showing the user a plain-English
    expectation ("Voice line - typically doesn't loop"). The real "does
    this loop" answer always comes from whether the unpacked reference
    .wav actually carries a loop (TrackInfo.info.has_loop) - checked data,
    not a path guess.
    """
    p = relative_path.replace("\\", "/").lower()
    if c.SOUND_MUSIC_PATH_FRAGMENT in p:
        return "music"
    if c.SOUND_VOICE_PATH_FRAGMENT in p:
        return "voice"
    return "other"


# =============================================================================
# Browsing (mirrors texture_data.TextureTreeNode/scan_texture_tree)
# =============================================================================

@dataclass
class SoundTreeNode:
    name: str
    relative_path: str        # forward-slashed, rooted at the unpacked game folder (e.g. "sound/music/music_00067.sab")
    is_file: bool
    children: list = field(default_factory=list)   # list[SoundTreeNode], folders only


def scan_sound_tree(unpacked_game_dir: Path) -> SoundTreeNode:
    """
    Scans <unpacked_game_dir>/sound for .sab (and .sabf/.mab/.mabf) files.
    Scoped to sound/ specifically (unlike Textures, which has to scan the
    whole game since .tga/.tex are scattered everywhere) - every sound
    archive in this game lives under sound/, confirmed against the real
    uploaded UnpackedGame_Folder.txt tree.
    """
    sound_root = unpacked_game_dir / "sound"

    def scan_dir(path: Path, rel: str) -> Optional[SoundTreeNode]:
        children = []
        try:
            entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        except OSError:
            return None
        for entry in entries:
            entry_rel = f"{rel}/{entry.name}" if rel else entry.name
            if entry.is_dir():
                sub = scan_dir(entry, entry_rel)
                if sub is not None:
                    children.append(sub)
            elif entry.is_file() and is_sound_archive(entry.name):
                children.append(SoundTreeNode(name=entry.name, relative_path=entry_rel, is_file=True))
        if not children:
            return None
        return SoundTreeNode(name=path.name, relative_path=rel, is_file=False, children=children)

    if not sound_root.exists():
        return SoundTreeNode(name="sound", relative_path="sound", is_file=False)
    result = scan_dir(sound_root, "sound")
    return result if result is not None else SoundTreeNode(name="sound", relative_path="sound", is_file=False)


def count_sounds(node: SoundTreeNode) -> int:
    if node.is_file:
        return 1
    return sum(count_sounds(child) for child in node.children)


# =============================================================================
# WAV / smpl-loop-chunk parsing and writing (stdlib only - no numpy needed,
# every real sample seen is plain 16-bit PCM, which the "wave" module
# already handles natively; only the smpl chunk needs manual RIFF walking,
# since "wave" doesn't expose non-standard chunks).
# =============================================================================

@dataclass
class WavInfo:
    sample_rate: int
    channels: int
    sample_width: int      # bytes per sample per channel
    num_samples: int       # per channel
    duration_sec: float
    loop_start: Optional[int] = None
    loop_end: Optional[int] = None
    loop_play_count: Optional[int] = None

    @property
    def has_loop(self) -> bool:
        return self.loop_start is not None and self.loop_end is not None and self.loop_end > self.loop_start


def _parse_riff_chunks(data: bytes) -> list[tuple]:
    """Returns [(chunk_id: bytes, chunk_data: bytes), ...] for a WAVE file's top-level chunks."""
    if data[0:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError("Not a RIFF/WAVE file.")
    chunks = []
    pos = 12
    n = len(data)
    while pos + 8 <= n:
        cid = data[pos:pos + 4]
        size = struct.unpack("<I", data[pos + 4:pos + 8])[0]
        chunk_data = data[pos + 8:pos + 8 + size]
        chunks.append((cid, chunk_data))
        pos += 8 + size
        if size % 2 == 1:
            pos += 1
    return chunks


def _build_riff(chunks: list[tuple]) -> bytes:
    body = b""
    for cid, cdata in chunks:
        body += cid + struct.pack("<I", len(cdata)) + cdata
        if len(cdata) % 2 == 1:
            body += b"\x00"
    return b"RIFF" + struct.pack("<I", 4 + len(body)) + b"WAVE" + body


def _build_smpl_chunk_data(loop_start: int, loop_end: int, play_count: int = 0, sample_rate: int = 44100) -> bytes:
    sample_period = int(1_000_000_000 / sample_rate) if sample_rate else 0
    header = struct.pack(
        "<9I",
        0,                  # manufacturer
        0,                  # product
        sample_period,
        60,                 # midi_unity_note
        0,                  # midi_pitch_fraction
        0,                  # smpte_format
        0,                  # smpte_offset
        1,                  # num_sample_loops
        0,                  # sampler_data
    )
    loop_entry = struct.pack(
        "<6I",
        0,                  # cue_point_id
        0,                  # loop type (0 = forward)
        loop_start,
        loop_end,
        0,                  # fraction
        play_count,         # 0 = infinite
    )
    return header + loop_entry


def read_wav_info(path: Path) -> WavInfo:
    data = path.read_bytes()
    try:
        chunks = _parse_riff_chunks(data)
    except ValueError as exc:
        raise ValueError(f"{path.name} doesn't look like a WAV file: {exc}") from exc

    fmt_data = None
    data_chunk = None
    smpl_data = None
    for cid, cdata in chunks:
        if cid == b"fmt " and fmt_data is None:
            fmt_data = cdata
        elif cid == b"data" and data_chunk is None:
            data_chunk = cdata
        elif cid == b"smpl" and smpl_data is None:
            smpl_data = cdata

    if fmt_data is None or data_chunk is None:
        raise ValueError(f"{path.name}: missing fmt or data chunk.")

    audio_format, channels, sample_rate, _byte_rate, block_align, bits_per_sample = struct.unpack(
        "<HHIIHH", fmt_data[:16]
    )
    sample_width = bits_per_sample // 8
    num_samples = len(data_chunk) // block_align if block_align else 0
    duration = num_samples / sample_rate if sample_rate else 0.0

    loop_start = loop_end = loop_play_count = None
    if smpl_data and len(smpl_data) >= 36:
        num_loops = struct.unpack("<I", smpl_data[28:32])[0]
        if num_loops >= 1 and len(smpl_data) >= 60:
            _cue, _type, start, end, _frac, play_count = struct.unpack("<6I", smpl_data[36:60])
            loop_start, loop_end, loop_play_count = start, end, play_count

    return WavInfo(
        sample_rate=sample_rate, channels=channels, sample_width=sample_width,
        num_samples=num_samples, duration_sec=duration,
        loop_start=loop_start, loop_end=loop_end, loop_play_count=loop_play_count,
    )


MIN_MEANINGFUL_LOOP_SAMPLES = 1000  # ~20ms even at a low 48kHz - below this it's audible flutter, not a loop


def clamp_loop_points(
    loop_start: Optional[int], loop_end: Optional[int], num_samples: int
) -> tuple:
    """
    Clamps loop points (e.g. inherited from a vanilla track of a different
    length) to fit within num_samples. Returns (None, None) if the result
    would be degenerate or too short to be a meaningful loop (e.g. the
    replacement is much shorter than the vanilla loop start) - a 1-sample
    "loop" would just be audible flutter, not a usable loop point.
    """
    if loop_start is None or loop_end is None or num_samples <= 0:
        return None, None
    start = max(0, min(loop_start, num_samples - 1))
    end = max(0, min(loop_end, num_samples))
    if end - start < MIN_MEANINGFUL_LOOP_SAMPLES:
        return None, None
    return start, end


def write_wav_with_loop(
    src_path: Path, dest_path: Path, loop_start: Optional[int], loop_end: Optional[int], play_count: int = 0
) -> None:
    """
    Copies src_path to dest_path, replacing whatever smpl chunk it has (if
    any) with one built from loop_start/loop_end, or stripping looping
    entirely if either is None. Safe to call with dest_path == src_path
    (reads fully into memory first, writes via a temp file + atomic
    replace).
    """
    data = src_path.read_bytes()
    chunks = _parse_riff_chunks(data)
    chunks = [(cid, cdata) for cid, cdata in chunks if cid != b"smpl"]

    if loop_start is not None and loop_end is not None and loop_end > loop_start:
        fmt_data = next((cdata for cid, cdata in chunks if cid == b"fmt "), None)
        sample_rate = struct.unpack("<I", fmt_data[4:8])[0] if fmt_data else 44100
        chunks.append((b"smpl", _build_smpl_chunk_data(loop_start, loop_end, play_count, sample_rate)))

    output = _build_riff(chunks)
    tmp_path = dest_path.with_name(dest_path.name + ".tmp")
    tmp_path.write_bytes(output)
    tmp_path.replace(dest_path)


def build_preview_wav(
    src_path: Path, dest_path: Path, loop_start: Optional[int], loop_end: Optional[int],
    loop_repeats: int = 2, max_total_seconds: float = 180.0,
) -> Path:
    """
    Builds a short demo clip for the Play button. A straight whole-file
    SND_LOOP replay wouldn't demonstrate the actual in-game loop point
    (which is usually partway into the track, skipping a non-repeating
    intro) - so this plays the intro once, then the loop segment
    loop_repeats more times back-to-back, making the seam itself audible.
    Falls back to a plain copy when there's no loop (voice lines, one-shot
    SFX). Caps total length so a long and/or heavily-repeated track doesn't
    produce an absurd preview.
    """
    with wave_mod.open(str(src_path), "rb") as wf:
        params = wf.getparams()
        n_frames = wf.getnframes()

        if loop_start is None or loop_end is None or loop_end <= loop_start or loop_end > n_frames:
            wf.rewind()
            frames = wf.readframes(n_frames)
            with wave_mod.open(str(dest_path), "wb") as out:
                out.setparams(params)
                out.writeframes(frames)
            return dest_path

        wf.setpos(0)
        intro = wf.readframes(loop_start)
        wf.setpos(loop_start)
        loop_segment = wf.readframes(loop_end - loop_start)

    frame_size = params.sampwidth * params.nchannels
    max_frames = int(max_total_seconds * params.framerate)
    max_bytes = max_frames * frame_size if frame_size else 0

    out_frames = intro
    for _ in range(loop_repeats):
        if max_bytes and len(out_frames) >= max_bytes:
            break
        out_frames += loop_segment
    if max_bytes and len(out_frames) > max_bytes:
        out_frames = out_frames[: max_bytes - (max_bytes % frame_size if frame_size else 0)]

    with wave_mod.open(str(dest_path), "wb") as out:
        out.setparams(params)
        out.writeframes(out_frames)
    return dest_path


# =============================================================================
# Track discovery within an unpacked "<name>_Project/" folder
# =============================================================================

def parse_track_users(path: Path) -> dict:
    """
    Parses a TrackUsers.txt like:
        music_00067_000.hca,\t\tusers: FID_MUSIC_TRACK_068_OGG
    Returns {track_stem: "FID_MUSIC_TRACK_068_OGG"} keyed by the track's
    filename stem (AudioMog lists the internal .hca name here even though
    the file actually on disk is the extracted .wav with the same stem).
    """
    result = {}
    if not path.exists():
        return result
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or "," not in line:
            continue
        name_part, _, rest = line.partition(",")
        stem = Path(name_part.strip()).stem
        users = rest.split("users:", 1)[-1].strip() if "users:" in rest else rest.strip()
        if stem:
            result[stem] = users
    return result


@dataclass
class TrackInfo:
    index: int
    stem: str            # e.g. "music_00067_000"
    wav_path: Path
    users: str            # from TrackUsers.txt, "" if unknown
    info: WavInfo


def list_tracks(project_dir: Path) -> list:
    users_by_stem = parse_track_users(project_dir / "TrackUsers.txt")
    tracks = []
    for wav_path in sorted(project_dir.glob("*.wav")):
        stem = wav_path.stem
        try:
            info = read_wav_info(wav_path)
        except ValueError:
            continue
        idx = 0
        parts = stem.rsplit("_", 1)
        if len(parts) == 2 and parts[1].isdigit():
            idx = int(parts[1])
        tracks.append(TrackInfo(index=idx, stem=stem, wav_path=wav_path, users=users_by_stem.get(stem, ""), info=info))
    tracks.sort(key=lambda t: t.index)
    return tracks


# =============================================================================
# Unpacking (with caching, mirroring texture_data's tex->dds preview cache)
# =============================================================================

def unpack_sab_cached(exe_path: Path, sab_source_path: Path, relative_path: str, cache_root: Path, line_cb=None) -> Path:
    """
    Unpacks a REAL .sab (from the unpacked game folder) into a cached
    "<stem>_Project/" folder under cache_root, mirroring the .sab's own
    relative folder structure so same-named files in different folders
    (common for voice lines) can never collide. Reuses an existing cached
    unpack if one's already there, so repeatedly browsing the same file
    doesn't re-run AudioMog every time. Always stages a COPY of the .sab
    first - never runs AudioMog directly against a file inside the real
    unpacked game folder, since AudioMog writes its output as a sibling of
    whatever file it's given.

    Waits for the actual output to appear on disk rather than for
    AudioMog's own process to exit (audiomog.run_unpack_and_wait) - see
    that function's docstring for why that distinction matters in
    practice, not just in theory.
    """
    rel = relative_path.replace("\\", "/").lstrip("/")
    rel_parent = str(Path(rel).parent) if "/" in rel else ""
    work_dir = (cache_root / rel_parent) if rel_parent else cache_root
    work_dir.mkdir(parents=True, exist_ok=True)

    staged_sab = work_dir / sab_source_path.name
    project_dir = work_dir / f"{sab_source_path.stem}_Project"

    if project_dir.exists() and list(project_dir.glob("*.wav")):
        return project_dir

    shutil.copy(sab_source_path, staged_sab)

    def artifact_check() -> bool:
        return project_dir.exists() and any(project_dir.glob("*.wav"))

    found = audiomog.run_unpack_and_wait(exe_path, staged_sab, artifact_check, line_cb=line_cb)
    if not found or not project_dir.exists():
        raise ValueError(
            f"AudioMog didn't produce {project_dir.name} for {sab_source_path.name} within the timeout."
        )
    return project_dir


# =============================================================================
# Exporting a track (mirrors texture_data.save_array_as_png - lets the user
# pull a track out to edit externally, then bring it back in via Replace)
# =============================================================================

def export_track_wav(source_wav_path: Path, dest_path: Path) -> None:
    """
    Copies an already-unpacked track's own .wav file out to dest_path for
    the Sounds tab's "Export as WAV..." button. The extracted track is
    already a standard PCM .wav (see module docstring) sitting on disk, so
    this is a plain byte-for-byte copy - no re-encoding, and therefore no
    quality loss - and it carries the track's own smpl loop chunk along
    with it untouched.
    """
    dest_path = Path(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_wav_path, dest_path)


# =============================================================================
# Staging a replacement + repack for export (mirrors texture_data's
# stage_texture_replacement, but as a multi-step external-tool pipeline
# rather than a single conversion call)
# =============================================================================

def stage_replacement_track(
    replacement_source_path: Path, target_wav_path: Path, loop_start: Optional[int], loop_end: Optional[int]
) -> None:
    """
    Overwrites target_wav_path (a track inside an unpacked Project folder)
    with the user's replacement audio, baking in the given loop points
    (clamped to the replacement's own length) or stripping looping
    entirely if both are None. Raises ValueError if replacement_source_path
    isn't a valid WAV - AudioMog's own rebuild step only reads .wav/.hca,
    so a non-WAV replacement (e.g. an mp3) would otherwise fail silently
    much later, at repack time, with a far less useful error.
    """
    info = read_wav_info(replacement_source_path)  # raises ValueError if not a real WAV
    clamped_start, clamped_end = clamp_loop_points(loop_start, loop_end, info.num_samples)
    write_wav_with_loop(replacement_source_path, target_wav_path, clamped_start, clamped_end)


def repack_sab_project(exe_path: Path, project_dir: Path, original_ext: str = ".sab", line_cb=None) -> Path:
    """
    Runs AudioMog on project_dir's RebuildSettings.json to repack it back
    into a sound archive - the subprocess equivalent of dragging that json
    file onto AudioMog.exe. Where exactly the repacked file lands isn't
    confirmed against a real run (AudioMog's own docs don't say). Checks
    the two most plausible locations - next to the staged original, and
    inside the Project folder itself - and only accepts one that's both
    present AND newer than the RebuildSettings.json, so a wrong guess
    fails loudly instead of silently handing back a stale file. Waits for
    that artifact to appear rather than for AudioMog's own process to exit
    (audiomog.run_repack_and_wait) - see its docstring for why.
    """
    rebuild_settings = project_dir / "RebuildSettings.json"
    if not rebuild_settings.exists():
        raise ValueError(f"No RebuildSettings.json found in {project_dir} - unpack the sound file first.")

    sab_stem = project_dir.name
    if sab_stem.endswith("_Project"):
        sab_stem = sab_stem[: -len("_Project")]

    before_mtime = rebuild_settings.stat().st_mtime
    candidates = [
        project_dir.parent / f"{sab_stem}{original_ext}",
        project_dir / f"{sab_stem}{original_ext}",
    ]

    def artifact_check() -> bool:
        return any(c.exists() and c.stat().st_mtime >= before_mtime for c in candidates)

    found = audiomog.run_repack_and_wait(exe_path, rebuild_settings, artifact_check, line_cb=line_cb)
    if found:
        for candidate in candidates:
            if candidate.exists() and candidate.stat().st_mtime >= before_mtime:
                return candidate
    raise ValueError(
        f"AudioMog didn't produce a repacked {sab_stem}{original_ext} next to or inside {project_dir} "
        f"within the timeout - this exact output location hasn't been confirmed for real yet (see "
        f"HANDOFF.md); check that folder by hand."
    )


def stage_sound_export(
    exe_path: Path, vanilla_sab_path: Path, relative_path: str, track_edits: dict, staging_root: Path, line_cb=None
) -> Path:
    """
    Full pipeline for one edited sound archive: stage a scratch copy of
    the vanilla file, unpack it with AudioMog, overwrite the edited
    track(s) with loop-corrected replacements, repack, and return the path
    to the resulting file (still just staged in staging_root - the caller
    copies it into the mod's FFTIVC/data/<mode>/ tree, same as Textures).

    track_edits: {track_index: {"source_path": Path, "loop_start":
    Optional[int], "loop_end": Optional[int]}}
    """
    rel = relative_path.replace("\\", "/").lstrip("/")
    rel_parent = str(Path(rel).parent) if "/" in rel else ""
    work_dir = (staging_root / rel_parent) if rel_parent else staging_root
    work_dir.mkdir(parents=True, exist_ok=True)

    staged_sab = work_dir / vanilla_sab_path.name
    shutil.copy(vanilla_sab_path, staged_sab)

    if line_cb:
        line_cb(f"Unpacking {vanilla_sab_path.name} with AudioMog...")
    project_dir = work_dir / f"{staged_sab.stem}_Project"

    def artifact_check() -> bool:
        return project_dir.exists() and any(project_dir.glob("*.wav"))

    found = audiomog.run_unpack_and_wait(exe_path, staged_sab, artifact_check, line_cb=line_cb)
    if not found or not project_dir.exists():
        raise ValueError(f"AudioMog didn't unpack {vanilla_sab_path.name} within the timeout.")

    tracks_by_index = {t.index: t for t in list_tracks(project_dir)}
    for track_index, edit in track_edits.items():
        track = tracks_by_index.get(track_index)
        if track is None:
            raise ValueError(
                f"Track index {track_index} not found in {vanilla_sab_path.name} "
                f"(found indices: {sorted(tracks_by_index)})."
            )
        stage_replacement_track(edit["source_path"], track.wav_path, edit.get("loop_start"), edit.get("loop_end"))

    if line_cb:
        line_cb(f"Repacking {vanilla_sab_path.name} with AudioMog...")
    return repack_sab_project(exe_path, project_dir, original_ext=vanilla_sab_path.suffix, line_cb=line_cb)


# =============================================================================
# Playback
# =============================================================================

class SoundPlayer:
    """
    Plays a .wav file for the Sounds tab's Play/Stop buttons. Uses the
    stdlib winsound module on Windows - no extra dependency needed, and
    this whole tool's actual sound-editing functionality already requires
    Windows tools (AudioMog.exe, FF16Tools.CLI.exe) either way. Falls back
    to a best-effort external player on other platforms (useful for
    exercising the tab's UI/data layer while developing off Windows), and
    raises a clear, catchable error if neither is available rather than
    crashing the GUI.
    """

    def __init__(self):
        self._proc: Optional[subprocess.Popen] = None

    def play(self, path: Path) -> None:
        self.stop()
        if platform.system() == "Windows":
            import winsound
            winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)
            return
        for exe_name in ("paplay", "aplay", "afplay"):
            exe = shutil.which(exe_name)
            if exe:
                self._proc = subprocess.Popen([exe, str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
        raise RuntimeError(
            "No audio playback method available on this platform - on Windows this plays automatically "
            "via the standard winsound module."
        )

    def stop(self) -> None:
        if platform.system() == "Windows":
            import winsound
            winsound.PlaySound(None, winsound.SND_PURGE)
            return
        if self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()
        self._proc = None
