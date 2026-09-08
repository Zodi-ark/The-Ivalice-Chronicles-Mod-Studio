"""
Everything related to AudioMog itself (github.com/Yoraiz0r/AudioMog, MIT
license) - the external tool the Sounds tab shells out to for unpacking and
repacking .sab sound archives, mirroring how ff16tools.py drives
FF16Tools.CLI for the Abilities/Items/Encounters/Textures tabs.

AudioMog is drag-and-drop only - there's no documented command-line flag
syntax. Its own README describes usage as literally dragging a file onto
AudioMog.exe in Explorer; on Windows that's just Explorer invoking
`AudioMog.exe <dropped-file-path>`, which subprocess can replicate exactly
the same way. Confirmed via the real README (raw.githubusercontent.com/
Yoraiz0r/AudioMog/master/README.md), not guessed:
  - Dragging a .sab (or .sabf/.mab/.mabf/.uasset/.uexp/.bytes) onto the exe
    unpacks it into a sibling "<name>_Project/" folder, alongside a
    RebuildSettings.json (Zodi's real uploaded sample confirms this shape -
    see Music_Reference.zip: music_00067_Project/{music_00067_000.wav,
    RebuildSettings.json, TrackUsers.txt}).
  - Dragging that RebuildSettings.json back onto the exe repacks it -
    reading .wav files (over .hca) when UseWavFilesIfAvailable is true,
    which is exactly the flag Zodi's real sample already has set.
  - TerminalSettings.json (living next to AudioMog.exe, not per-project)
    has an ImmediatelyQuitOnceAllTasksAreDone flag needed for unattended
    automation - the equivalent of FF16Tools.CLI's "-s" flag. Its exact
    JSON nesting isn't confirmed against a real generated copy (nobody has
    run the real .exe in this dev sandbox - no Windows/.NET runtime here,
    same limitation as FF16Tools.CLI itself), so ensure_terminal_settings_
    quiet() below searches for the key at any depth rather than assuming a
    schema and risking silently corrupting a file it doesn't fully
    understand.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from . import fetcher
from . import paths
from . import proc_util


def default_tools_dir() -> Path:
    d = paths.local_data_dir() / "AudioMog"
    d.mkdir(parents=True, exist_ok=True)
    return d


def find_bundled_exe() -> Optional[Path]:
    """
    Looks for AudioMog.exe bundled with this project itself (MIT license -
    see tools/AudioMog/LICENSE) at tools/AudioMog/, complete with a
    TerminalSettings.json already patched to run unattended, so a fresh
    install works immediately without requiring a first-time download.
    Returns None if the project was somehow shipped/copied without that
    folder.
    """
    return find_exe_in(paths.bundled_tools_dir() / "AudioMog")


def find_exe_in(directory: Path) -> Optional[Path]:
    """Looks for an AudioMog*.exe directly in or one level under `directory`."""
    if not directory.exists():
        return None

    def _match(folder: Path) -> Optional[Path]:
        for child in folder.iterdir():
            if child.is_file() and child.suffix.lower() == ".exe" and "audiomog" in child.name.lower():
                return child
        return None

    direct = _match(directory)
    if direct is not None:
        return direct
    for child in directory.iterdir():
        if child.is_dir():
            found = _match(child)
            if found is not None:
                return found
    return None


@dataclass
class DownloadProgress:
    stage: str
    detail: str


def download_latest(
    dest_dir: Optional[Path] = None,
    progress_cb: Optional[Callable[[DownloadProgress], None]] = None,
) -> Path:
    """
    Downloads the latest AudioMog release directly (no zip to extract -
    AudioMog packs itself into a single standalone .exe, unlike
    FF16Tools.CLI) - including its accompanying TerminalSettings.json if
    the release has one (see fetcher.pick_audiomog_assets - a previous
    version of this only fetched the .exe itself, which meant a fresh
    download never got AudioMog's real config file at all). Patches the
    downloaded TerminalSettings.json to run unattended, same as
    ensure_terminal_settings_quiet does for an already-installed copy.
    Returns the path to the downloaded AudioMog.exe.
    """
    dest_dir = dest_dir or default_tools_dir()

    def report(stage: str, detail: str) -> None:
        if progress_cb:
            progress_cb(DownloadProgress(stage, detail))

    report("checking", "Checking github.com/Yoraiz0r/AudioMog for the latest release...")
    release_info = fetcher.get_latest_audiomog_release_info()
    tag = release_info.get("tag_name", "unknown")

    assets = fetcher.pick_audiomog_assets(release_info)
    if not any(a["name"].lower().endswith(".exe") for a in assets):
        raise RuntimeError(
            f"Couldn't find an AudioMog.exe build in release {tag}. "
            f"You can download one manually from "
            f"https://github.com/Yoraiz0r/AudioMog/releases/tag/{tag}"
        )

    version_dir = dest_dir / tag
    version_dir.mkdir(parents=True, exist_ok=True)

    exe_path: Optional[Path] = None
    for asset in assets:
        report("downloading", f"Downloading {asset['name']} (release {tag})...")
        target = version_dir / asset["name"]
        fetcher.download_asset(asset, target)
        if target.suffix.lower() == ".exe":
            exe_path = target

    assert exe_path is not None  # guaranteed by the check above
    patch_result = ensure_terminal_settings_quiet(exe_path)
    if patch_result == "patched":
        report("done", f"AudioMog ready at {exe_path} (set to run unattended).")
    else:
        report("done", f"AudioMog ready at {exe_path}")
    return exe_path


def _find_key_recursive(obj, key: str) -> bool:
    """True if `key` appears anywhere in a (possibly nested) dict/list."""
    if isinstance(obj, dict):
        if key in obj:
            return True
        return any(_find_key_recursive(v, key) for v in obj.values())
    if isinstance(obj, list):
        return any(_find_key_recursive(v, key) for v in obj)
    return False


def _set_key_recursive(obj, key: str, value) -> bool:
    """Sets every occurrence of `key` anywhere in a nested dict/list. Returns whether anything was set."""
    changed = False
    if isinstance(obj, dict):
        if key in obj and obj[key] != value:
            obj[key] = value
            changed = True
        for v in obj.values():
            changed = _set_key_recursive(v, key, value) or changed
    elif isinstance(obj, list):
        for v in obj:
            changed = _set_key_recursive(v, key, value) or changed
    return changed


QUIET_FLAG_KEY = "ImmediatelyQuitOnceAllTasksAreDone"


def ensure_terminal_settings_quiet(exe_path: Path) -> str:
    """
    Best-effort: if a TerminalSettings.json already sits next to exe_path,
    make sure ImmediatelyQuitOnceAllTasksAreDone is true (searched at any
    JSON nesting depth, since the real schema hasn't been confirmed against
    an actual generated copy in this dev environment - see module docstring).
    Never fabricates the file from scratch, since guessing its full field
    set could ship a broken config AudioMog then can't parse.

    Returns one of: "already_set", "patched", "missing_key", "no_file".
    """
    import json

    settings_path = exe_path.parent / "TerminalSettings.json"
    if not settings_path.exists():
        return "no_file"

    try:
        data = json.loads(settings_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return "no_file"

    if not _find_key_recursive(data, QUIET_FLAG_KEY):
        return "missing_key"

    changed = _set_key_recursive(data, QUIET_FLAG_KEY, True)
    if changed:
        settings_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return "patched"
    return "already_set"


def build_unpack_command(exe_path: Path, sab_path: Path) -> list[str]:
    return [str(exe_path), str(sab_path)]


def run_unpack(
    exe_path: Path, sab_path: Path, line_cb: Optional[Callable[[str], None]] = None
) -> int:
    """
    Runs AudioMog on a single .sab (or .sabf/.mab/.mabf) file, the
    subprocess equivalent of dragging it onto AudioMog.exe in Explorer.
    Produces a sibling "<sab stem>_Project/" folder next to sab_path
    containing the unpacked track .wav file(s), RebuildSettings.json, and
    TrackUsers.txt. Run against a scratch copy of the .sab (see
    sound_data.stage_sound_for_preview), never the real unpacked game
    folder, since this writes a new folder next to its input.

    Blocks until the AudioMog process itself exits - prefer
    run_unpack_and_wait below, which doesn't have that problem (see its
    docstring for why that matters).
    """
    command = proc_util.for_platform(exe_path, build_unpack_command(exe_path, sab_path))
    return proc_util.run_streaming(command, line_cb, cwd=sab_path.parent)


def run_unpack_and_wait(
    exe_path: Path,
    sab_path: Path,
    artifact_check: Callable[[], bool],
    line_cb: Optional[Callable[[str], None]] = None,
    timeout: float = 120.0,
) -> bool:
    """
    Like run_unpack, but proceeds the moment artifact_check() reports the
    expected output exists, rather than waiting for AudioMog's own process
    to exit. Confirmed necessary, not just theoretical: AudioMog's real
    shipped TerminalSettings.json (bundled in tools/AudioMog/ - see that
    folder's own notes) defaults ImmediatelyQuitOnceAllTasksAreDone to
    false, and even with it patched true, nothing here guarantees every
    AudioMog version/build always exits cleanly right after finishing a
    real unpack. This is what fixed a real reported bug: the Sounds tab
    would show "unpacking..." forever after one click, but selecting the
    same file again would immediately show the correct tracks - because
    AudioMog had, in fact, already finished and written its output; only
    the process object itself hadn't returned, so the old blocking
    run_unpack() never got the chance to report success.
    """
    command = proc_util.for_platform(exe_path, build_unpack_command(exe_path, sab_path))
    found, _code = proc_util.run_streaming_with_artifact(
        command, artifact_check, cwd=sab_path.parent, line_cb=line_cb, timeout=timeout
    )
    return found


def build_repack_command(exe_path: Path, rebuild_settings_path: Path) -> list[str]:
    return [str(exe_path), str(rebuild_settings_path)]


def run_repack(
    exe_path: Path, rebuild_settings_path: Path, line_cb: Optional[Callable[[str], None]] = None
) -> int:
    """
    Runs AudioMog on a "<name>_Project/RebuildSettings.json" file, the
    subprocess equivalent of dragging it onto AudioMog.exe - repacks
    whatever .wav files are staged in that same Project folder back into a
    .sab, preferring .wav over .hca when RebuildSettings.json's own
    UseWavFilesIfAvailable is true (already the case for every real sample
    seen so far). Where exactly the repacked .sab lands isn't confirmed
    (AudioMog's own docs don't say) - see sound_data.repack_sab_project,
    which searches the plausible locations rather than assuming one.

    Blocks until the AudioMog process itself exits - prefer
    run_repack_and_wait below, for the same reason as run_unpack_and_wait.
    """
    command = proc_util.for_platform(exe_path, build_repack_command(exe_path, rebuild_settings_path))
    return proc_util.run_streaming(command, line_cb, cwd=rebuild_settings_path.parent)


def run_repack_and_wait(
    exe_path: Path,
    rebuild_settings_path: Path,
    artifact_check: Callable[[], bool],
    line_cb: Optional[Callable[[str], None]] = None,
    timeout: float = 120.0,
) -> bool:
    """Like run_repack, but see run_unpack_and_wait's docstring for why this is the one to actually use."""
    command = proc_util.for_platform(exe_path, build_repack_command(exe_path, rebuild_settings_path))
    found, _code = proc_util.run_streaming_with_artifact(
        command, artifact_check, cwd=rebuild_settings_path.parent, line_cb=line_cb, timeout=timeout
    )
    return found
