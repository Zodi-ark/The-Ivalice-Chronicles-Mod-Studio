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
import sys
from array import array
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

def unpack_sab_cached(exe_path: Path, sab_source_path: Path, relative_path: str, cache_root: Path,
                      line_cb=None, as_name: Optional[str] = None) -> Path:
    """
    Unpacks a REAL .sab (from the unpacked game folder, or a whole-archive
    replacement) into a cached "<stem>_Project/" folder under cache_root,
    mirroring the .sab's own relative folder structure so same-named files
    in different folders (common for voice lines) can never collide. Reuses
    an existing cached unpack if one's already there, so repeatedly browsing
    the same file doesn't re-run AudioMog every time. Always stages a COPY
    of the .sab first - never runs AudioMog directly against a file inside
    the real unpacked game folder, since AudioMog writes its output as a
    sibling of whatever file it's given.

    `as_name` stages the copy under a different file name. A replacement
    archive the user picked may be called anything, and AudioMog names every
    track after the file it was given - so it is staged under the game's own
    name, and its tracks read `music_00049_000` like the game's do.

    **A cache hit needs RebuildSettings.json**, which AudioMog writes last,
    after every track. This used to accept any folder holding a .wav - which
    an unpack that was interrupted, or is still being written, also is.
    """
    rel = relative_path.replace("\\", "/").lstrip("/")
    rel_parent = str(Path(rel).parent) if "/" in rel else ""
    work_dir = (cache_root / rel_parent) if rel_parent else cache_root
    work_dir.mkdir(parents=True, exist_ok=True)

    staged_sab = work_dir / (as_name or sab_source_path.name)
    project_dir = work_dir / f"{staged_sab.stem}_Project"
    rebuild_settings = project_dir / "RebuildSettings.json"

    if rebuild_settings.exists() and list(project_dir.glob("*.wav")):
        return project_dir
    shutil.rmtree(project_dir, ignore_errors=True)

    shutil.copy(sab_source_path, staged_sab)
    run = audiomog.run_to_completion(exe_path, staged_sab, line_cb=line_cb)
    if not (rebuild_settings.exists() and any(project_dir.glob("*.wav"))):
        raise ValueError(_audiomog_failure(f"couldn't unpack {sab_source_path.name}", run))
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

# =============================================================================
# Reading a sound archive's own header - no AudioMog needed
# =============================================================================
#
# The layout is AudioMog's, read from its source (AudioBinaryFileHeader,
# AudioBinarySectionDeclaration, MaterialSection), and checked against real
# files: the community music mod's music_00000.sab and AudioMog's repack of
# it both read as one 48 kHz stereo HCA track, with the loop points the
# unpacked .wav carries in its smpl chunk.

ARCHIVE_MAGICS = (b"sabf", b"mabf")
MATERIAL_CODECS = {0: "none", 1: "PCM", 2: "MS ADPCM", 3: "Ogg Vorbis", 4: "ATRAC9",
                   5: "XMA2", 6: "MP3", 7: "HCA", 8: "Opus"}


@dataclass
class SabTrack:
    index: int
    channels: int
    codec: str
    sample_rate: int
    loop_start: int
    loop_end: int
    span: tuple          # (start, end) of the track's header and audio in the file


@dataclass
class SabSummary:
    magic: bytes
    version: tuple       # (main, sub) - the game's are 2.1
    size_field: int      # the size the header claims
    length: int          # the size the file is
    tracks: list


def read_sab_summary(data: bytes) -> SabSummary:
    """
    Reads a .sab/.mab archive's header and track table. Raises ValueError
    for anything that isn't one, or is cut short.
    """
    try:
        magic = bytes(data[:4])
        if magic not in ARCHIVE_MAGICS:
            raise ValueError("it doesn't begin the way a .sab sound archive does")
        descriptor = data[9]
        header_size = 16 + descriptor + (16 - descriptor % 16)
        sections = {}
        for i in range(data[8]):
            at = header_size + 16 * i
            sections[bytes(data[at:at + 4])] = struct.unpack_from("<I", data, at + 8)[0]
        if b"mtrl" not in sections:
            raise ValueError("it has no track table")
        table = sections[b"mtrl"]
        tracks = []
        for i in range(struct.unpack_from("<H", data, table + 4)[0]):
            head = table + struct.unpack_from("<I", data, table + 0x10 + 4 * i)[0]
            rate, loop_start, loop_end, extra, stream = struct.unpack_from("<5I", data, head + 8)
            end = head + 0x20 + extra + stream
            if end > len(data):
                raise ValueError(f"track {i} runs past the end of the file")
            codec = data[head + 5]
            tracks.append(SabTrack(i, data[head + 4], MATERIAL_CODECS.get(codec, str(codec)),
                                   rate, loop_start, loop_end, (head, end)))
    except (IndexError, struct.error) as exc:
        raise ValueError("it is cut short, or isn't a sound archive at all") from exc
    return SabSummary(magic, (data[4], data[5]), struct.unpack_from("<I", data, 12)[0],
                      len(data), tracks)


def _archive_kind(magic: bytes) -> str:
    return "music bank (mabf)" if magic == b"mabf" else "sound bank (sabf)"


def check_sound_archive(path: Path, like: Optional[Path] = None) -> SabSummary:
    """
    Confirms a file chosen to replace a WHOLE archive really is one, before
    it can go into a mod. A whole replacement is copied into the mod as it
    is, so anything wrong with it is shipped - and "loads without error, and
    the sound doesn't play" is exactly what a wrong file looks like in game.

    `like` is the game's own archive, when there is one: a music bank can't
    stand in for a sound bank.
    """
    path = Path(path)
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"{path.name} couldn't be read: {exc}") from exc
    try:
        summary = read_sab_summary(data)
    except ValueError as exc:
        hint = (" To put a WAV into the game, select a track and use Replace "
                "this track instead." if data[:4] == b"RIFF" else "")
        raise ValueError(f"{path.name} isn't a sound archive - {exc}.{hint}") from exc
    if like is not None and Path(like).is_file():
        with open(like, "rb") as handle:
            own = handle.read(4)
        if own in ARCHIVE_MAGICS and own != summary.magic:
            raise ValueError(f"{path.name} is a {_archive_kind(summary.magic)}, and the "
                             f"game's file is a {_archive_kind(own)}.")
    return summary


# =============================================================================
# Replacement WAVs - what AudioMog can read, and converting what it can't
# =============================================================================
#
# AudioMog reads a replacement through VGAudio, which takes 8- or 16-bit PCM
# and nothing else. Measured with the bundled build: a 24-bit WAV fails with
# "Must have 8 or 16 bits per sample, not 24 bits per sample", a 32-bit float
# WAV with "Must contain PCM data. Has unsupported format 3", and neither
# writes an archive. Audio editors save both routinely, so both are converted
# to 16-bit here rather than refused.

_PCM, _FLOAT, _EXTENSIBLE = 1, 3, 0xFFFE
_CONVERTIBLE = {(_PCM, 8), (_PCM, 16), (_PCM, 24), (_PCM, 32), (_FLOAT, 32), (_FLOAT, 64)}


def _wav_encoding(fmt_data: bytes) -> tuple:
    """(format tag, channels, sample rate, block align, bits) - EXTENSIBLE read through."""
    tag, channels, rate, _byte_rate, block_align, bits = struct.unpack("<HHIIHH", fmt_data[:16])
    if tag == _EXTENSIBLE and len(fmt_data) >= 26:
        tag = struct.unpack("<H", fmt_data[24:26])[0]
    return tag, channels, rate, block_align, bits


def _float_to_16(value: float) -> int:
    if -1.0 < value < 1.0:
        return int(value * 32767.0)
    if value >= 1.0:
        return 32767
    if value <= -1.0:
        return -32768
    return 0                               # NaN


def _as_pcm(fmt_data: bytes, audio: bytes) -> tuple:
    """Returns (fmt, data) as plain 8- or 16-bit PCM, converting when needed."""
    tag, channels, rate, block_align, bits = _wav_encoding(fmt_data)
    if block_align:
        audio = audio[:len(audio) - len(audio) % block_align]
    if tag == _PCM and bits == 8:
        return struct.pack("<HHIIHH", _PCM, channels, rate, rate * channels, channels, 8), audio
    pcm16 = struct.pack("<HHIIHH", _PCM, channels, rate, rate * channels * 2, channels * 2, 16)
    if tag == _PCM and bits == 16:
        return pcm16, audio
    if tag == _PCM and bits == 24:          # keep the top two bytes of each sample
        out = bytearray(len(audio) // 3 * 2)
        out[0::2], out[1::2] = audio[1::3], audio[2::3]
        return pcm16, bytes(out)
    if tag == _PCM and bits == 32:
        out = bytearray(len(audio) // 2)
        out[0::2], out[1::2] = audio[2::4], audio[3::4]
        return pcm16, bytes(out)
    if tag == _FLOAT and bits in (32, 64):
        values = array("f" if bits == 32 else "d")
        values.frombytes(audio)
        if sys.byteorder == "big":
            values.byteswap()
        out = array("h", [_float_to_16(v) for v in values])
        if sys.byteorder == "big":
            out.byteswap()
        return pcm16, out.tobytes()
    raise ValueError("unsupported encoding")      # check_replacement_wav words this


def check_replacement_wav(path: Path) -> WavInfo:
    """
    Confirms a file can replace a track, and says why in plain words if it
    can't. Called when the file is chosen, so a problem is reported then -
    not minutes later, at export, as an AudioMog stack trace.
    """
    path = Path(path)
    info = read_wav_info(path)              # raises "doesn't look like a WAV file"
    fmt = next(cdata for cid, cdata in _parse_riff_chunks(path.read_bytes()) if cid == b"fmt ")
    tag, _channels, _rate, _align, bits = _wav_encoding(fmt)
    if (tag, bits) not in _CONVERTIBLE:
        kind = {_PCM: "PCM", _FLOAT: "floating-point"}.get(tag, f"compressed (format {tag})")
        raise ValueError(f"{path.name} is a {bits}-bit {kind} WAV, which can't be put into "
                         f"the game. Save it again as 16-bit PCM WAV.")
    if info.num_samples == 0:
        raise ValueError(f"{path.name} has no audio in it.")
    return info


# =============================================================================
# Playing a track for the loop editor
# =============================================================================
#
# The Sounds page's waveform and player need the audio as numbers. Playback
# itself streams to the sound device from the page (`qt/audio_output.py`).

@dataclass
class Pcm16:
    """A WAV's audio as interleaved little-endian 16-bit samples."""
    sample_rate: int
    channels: int
    data: bytes

    @property
    def frames(self) -> int:
        return len(self.data) // (2 * self.channels) if self.channels else 0


def read_pcm16(path: Path) -> Pcm16:
    """
    Reads a WAV as 16-bit PCM, whatever it was saved as: 8-bit is widened,
    24-bit, 32-bit and floating point are converted the way a replacement
    is. Raises ValueError, in plain words, for anything that can't be read.
    """
    path = Path(path)
    check_replacement_wav(path)
    chunks = _parse_riff_chunks(path.read_bytes())
    fmt = next(cdata for cid, cdata in chunks if cid == b"fmt ")
    audio = next(cdata for cid, cdata in chunks if cid == b"data")
    fmt, audio = _as_pcm(fmt, audio)
    _tag, channels, rate, _align, bits = _wav_encoding(fmt)
    if bits == 8:
        wide = array("h", [(byte - 128) << 8 for byte in audio])
        if sys.byteorder == "big":
            wide.byteswap()
        audio = wide.tobytes()
    return Pcm16(rate, channels, bytes(audio))



# =============================================================================
# Staging a replacement + repack for export
# =============================================================================

def stage_replacement_track(
    replacement_source_path: Path, target_wav_path: Path, loop_start: Optional[int], loop_end: Optional[int]
) -> None:
    """
    Overwrites target_wav_path (a track inside an unpacked Project folder)
    with the user's replacement audio as 16-bit PCM, baking in the given
    loop points (clamped to the replacement's own length) or stripping
    looping entirely if both are None. Raises ValueError for a file that
    can't be used - see check_replacement_wav.

    Only fmt and data are carried across, plus the loop. Whatever else an
    editor wrote (LIST, bext, cue...) is nothing the game reads and one more
    thing for AudioMog's reader to trip on.
    """
    source = Path(replacement_source_path)
    info = check_replacement_wav(source)
    clamped_start, clamped_end = clamp_loop_points(loop_start, loop_end, info.num_samples)
    chunks = _parse_riff_chunks(source.read_bytes())
    fmt = next(cdata for cid, cdata in chunks if cid == b"fmt ")
    audio = next(cdata for cid, cdata in chunks if cid == b"data")
    fmt, audio = _as_pcm(fmt, audio)
    target = Path(target_wav_path)
    tmp_path = target.with_name(target.name + ".tmp")
    tmp_path.write_bytes(_build_riff([(b"fmt ", fmt), (b"data", audio)]))
    tmp_path.replace(target)
    write_wav_with_loop(target, target, clamped_start, clamped_end)


#: Put in front of an archive before AudioMog repacks it, and taken off after.
#:
#: **Every repack of a plain .sab crashes in the bundled AudioMog.** Its last
#: step (`FixTotalFileSizeStep`, added 2025-01-31 in commit 4434f58, so in
#: both 2025 releases) reads four bytes at the archive's start minus 4 and
#: minus 8, looking for a container's size field. A .sab straight from the
#: game starts at byte 0, so it reads at -4, throws
#: `ArgumentOutOfRangeException`, writes nothing - and exits with code 0.
#: Measured under mono on a real archive, and plain from the source.
#:
#: AudioMog finds an archive by its magic wherever it sits, because its own
#: main use is archives inside Unreal `.uexp` files. Sixteen zero bytes in
#: front put the start at 16: the reads land on zeros, which match no size,
#: so nothing is written there, and the archive after them is rebuilt
#: exactly as it would have been. The rebuilt archive's header is byte for
#: byte the original's apart from the size, and a real replaced track
#: re-unpacks as the audio that went in (correlation 1.0 against the tone
#: used to test it).
#:
#: Harmless if AudioMog is ever fixed, since a prefix is its supported case.
REPACK_PADDING = bytes(16)


def _audiomog_failure(what: str, run) -> str:
    if not run.finished:
        return f"AudioMog {what}: it hadn't finished after several minutes and was stopped."
    problems = run.problems()
    if problems:
        return f"AudioMog {what}: {problems[0]}"
    return f"AudioMog {what}, and didn't say why."


def repack_sab_project(exe_path: Path, project_dir: Path, original_ext: str = ".sab", line_cb=None) -> Path:
    """
    Runs AudioMog on project_dir's RebuildSettings.json to repack it back
    into a sound archive - the subprocess equivalent of dragging that json
    file onto AudioMog.exe - and returns the file it wrote.

    **AudioMog writes the repacked archive INSIDE the Project folder**
    (`outputFolder = RunningDirectory` in its source; confirmed by running
    it). This used to accept a second "plausible location" too, next to the
    Project folder - which is where the staged ORIGINAL sits. Once that copy
    was newer than RebuildSettings.json, which any second export made it,
    the unmodified archive was returned as the repack and shipped: a mod
    that loads without error and plays the original sound.

    A result from an earlier run is deleted first, so the file this returns
    can only have come from this run.
    """
    rebuild_settings = project_dir / "RebuildSettings.json"
    if not rebuild_settings.exists():
        raise ValueError(f"No RebuildSettings.json found in {project_dir} - unpack the sound file first.")
    sab_stem = project_dir.name
    if sab_stem.endswith("_Project"):
        sab_stem = sab_stem[: -len("_Project")]
    output = project_dir / f"{sab_stem}{original_ext}"
    if output.exists():
        output.unlink()
    run = audiomog.run_to_completion(exe_path, rebuild_settings, line_cb=line_cb)
    if not output.exists() or not run.finished:
        raise ValueError(_audiomog_failure(f"couldn't repack {sab_stem}{original_ext}", run))
    return output


def _verify_repack(base: bytes, base_summary: SabSummary, result: bytes, name: str, edited) -> None:
    """
    Checks a repacked archive before it can go into a mod. Each check is a
    way the export has actually gone wrong, or would have: a file that isn't
    an archive, one whose header disagrees with its size, one that lost
    tracks, and one AudioMog wrote back unchanged.
    """
    try:
        summary = read_sab_summary(result)
    except ValueError as exc:
        raise ValueError(f"The repacked {name} isn't a readable sound archive ({exc}).") from exc
    if (summary.magic, summary.version) != (base_summary.magic, base_summary.version):
        raise ValueError(f"The repacked {name} has a different header from the one it was "
                         f"built from, so it wasn't included.")
    if summary.size_field != summary.length:
        raise ValueError(f"The repacked {name} says it is {summary.size_field:,} bytes and is "
                         f"{summary.length:,}, so it wasn't included.")
    if len(summary.tracks) != len(base_summary.tracks):
        raise ValueError(f"The repacked {name} has {len(summary.tracks)} track(s) where the "
                         f"original has {len(base_summary.tracks)}, so it wasn't included.")
    if result == base:
        raise ValueError(f"AudioMog wrote {name} back unchanged - the replacement didn't go "
                         f"in, so it wasn't included.")
    for index in edited:
        if index < len(summary.tracks):
            old, new = base_summary.tracks[index].span, summary.tracks[index].span
            if base[old[0]:old[1]] == result[new[0]:new[1]]:
                raise ValueError(f"Track {index} of the repacked {name} is still the original "
                                 f"audio - AudioMog didn't replace it.")


def stage_sound_export(
    exe_path: Path, base_sab_path: Path, relative_path: str, track_edits: dict, staging_root: Path, line_cb=None
) -> Path:
    """
    Full pipeline for one edited sound archive: stage a scratch copy of the
    archive to start from, unpack it with AudioMog, overwrite the edited
    track(s) with loop-corrected replacements, repack, check the result, and
    return its path (still just staged - the caller copies it into the
    mod's FFTIVC/data/<mode>/ tree, same as Textures).

    `base_sab_path` is the game's own archive, or a whole-archive
    replacement when the mod has one - a track replaced in an archive the
    mod already replaces belongs in THAT archive, or every other change the
    mod made to it is lost.

    **Every run starts from nothing.** The staging folder used to survive
    between exports, and the unpack step accepted "the Project folder has a
    .wav in it" as done - true at once on any second export, before AudioMog
    had even started. The folder is cleared first now, and each AudioMog run
    is waited on until it ends.

    track_edits: {track_index: {"source_path": Path, "loop_start":
    Optional[int], "loop_end": Optional[int]}}
    """
    rel = relative_path.replace("\\", "/").lstrip("/")
    rel_parent = str(Path(rel).parent) if "/" in rel else ""
    work_dir = (staging_root / rel_parent) if rel_parent else staging_root
    work_dir.mkdir(parents=True, exist_ok=True)

    # Staged under the GAME's name, whatever the base file is called: AudioMog
    # names tracks after the file it is given, and the track indices below
    # are read from those names.
    name = Path(rel).name
    staged_sab = work_dir / name
    project_dir = work_dir / f"{staged_sab.stem}_Project"
    result_path = work_dir / "repacked" / name
    shutil.rmtree(project_dir, ignore_errors=True)
    for leftover in (staged_sab, result_path):
        if leftover.exists():
            leftover.unlink()

    base = Path(base_sab_path).read_bytes()
    try:
        base_summary = read_sab_summary(base)
    except ValueError as exc:
        raise ValueError(f"{Path(base_sab_path).name} isn't a sound archive ({exc}).") from exc
    staged_sab.write_bytes(REPACK_PADDING + base)

    if line_cb:
        line_cb(f"Unpacking {name} with AudioMog...")
    run = audiomog.run_to_completion(exe_path, staged_sab, line_cb=line_cb)
    if not (project_dir / "RebuildSettings.json").exists():
        raise ValueError(_audiomog_failure(f"couldn't unpack {name}", run))

    tracks_by_index = {t.index: t for t in list_tracks(project_dir)}
    for track_index, edit in track_edits.items():
        track = tracks_by_index.get(track_index)
        if track is None:
            raise ValueError(
                f"Track index {track_index} not found in {name} "
                f"(found indices: {sorted(tracks_by_index)}).")
        # No source: a loop-only change. The game's own track - freshly
        # unpacked above, so no browse cache is trusted - is re-encoded with
        # the new loop points.
        stage_replacement_track(edit.get("source_path") or track.wav_path, track.wav_path,
                                edit.get("loop_start"), edit.get("loop_end"))
    # Tracks nobody replaced go back in as the game's own bytes. With their
    # .wav present AudioMog re-encodes every one of them from the decoded
    # audio - a lossy round trip for sound nobody touched, and in a bank of
    # many effects, minutes of encoding. Without one it keeps the original
    # track ("Found no replacement ... using original track").
    for track in tracks_by_index.values():
        if track.index not in track_edits:
            track.wav_path.unlink()

    if line_cb:
        line_cb(f"Repacking {name} with AudioMog...")
    repacked = repack_sab_project(exe_path, project_dir, original_ext=staged_sab.suffix, line_cb=line_cb)
    data = repacked.read_bytes()
    if not data.startswith(REPACK_PADDING):
        raise ValueError(f"AudioMog's repack of {name} doesn't begin where the archive was "
                         f"placed, so it wasn't included.")
    data = data[len(REPACK_PADDING):]
    _verify_repack(base, base_summary, data, name, sorted(track_edits))
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_bytes(data)
    return result_path


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
