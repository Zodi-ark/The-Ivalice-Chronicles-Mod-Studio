"""
Everything related to FF16Tools itself.

None of this is required just to edit Job Data (see fetcher.py) - it's kept
around, clearly marked optional, because future tables/features (textures,
sprites, anything not shipped as a ready-made reference XML) will need a
real unpack of the game's pack files.
"""

from __future__ import annotations

import os
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from . import fetcher
from . import paths
from . import proc_util

CLI_EXE_NAME = "FF16Tools.CLI.exe"


def default_tools_dir() -> Path:
    d = paths.local_data_dir() / "FF16Tools"
    d.mkdir(parents=True, exist_ok=True)
    return d


def find_bundled_cli() -> Optional[Path]:
    """
    Looks for the FF16Tools.CLI.exe bundled with this project itself (MIT
    license - see tools/FF16Tools/LICENSE.txt) at tools/FF16Tools/, so a
    fresh install works immediately without requiring a first-time
    download. Returns None if the project was somehow shipped/copied
    without that folder.
    """
    return find_cli_in(paths.bundled_tools_dir() / "FF16Tools")


def find_cli_in(directory: Path) -> Optional[Path]:
    """Looks for FF16Tools.CLI.exe directly in or one level under `directory`."""
    if not directory.exists():
        return None
    direct = directory / CLI_EXE_NAME
    if direct.exists():
        return direct
    for child in directory.iterdir():
        if child.is_dir():
            candidate = child / CLI_EXE_NAME
            if candidate.exists():
                return candidate
    return None


@dataclass
class DownloadProgress:
    stage: str
    detail: str


def download_and_extract_latest(
    dest_dir: Optional[Path] = None,
    progress_cb: Optional[Callable[[DownloadProgress], None]] = None,
) -> Path:
    """
    Downloads the latest FF16Tools.CLI Windows release and extracts it.
    Returns the path to FF16Tools.CLI.exe inside the extracted folder.
    """
    dest_dir = dest_dir or default_tools_dir()

    def report(stage: str, detail: str) -> None:
        if progress_cb:
            progress_cb(DownloadProgress(stage, detail))

    report("checking", "Checking github.com/Nenkai/FF16Tools for the latest release...")
    release_info = fetcher.get_latest_ff16tools_release_info()
    tag = release_info.get("tag_name", "unknown")

    asset = fetcher.pick_windows_cli_asset(release_info)
    if asset is None:
        raise RuntimeError(
            f"Couldn't find a Windows FF16Tools.CLI build in release {tag}. "
            f"You can download one manually from "
            f"https://github.com/Nenkai/FF16Tools/releases/tag/{tag}"
        )

    zip_path = dest_dir / asset["name"]
    report("downloading", f"Downloading {asset['name']} (release {tag})...")
    fetcher.download_asset(asset, zip_path)

    extract_dir = dest_dir / tag
    extract_dir.mkdir(parents=True, exist_ok=True)
    report("extracting", f"Extracting to {extract_dir}...")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)
    zip_path.unlink(missing_ok=True)

    cli_path = find_cli_in(extract_dir)
    if cli_path is None:
        raise RuntimeError(
            f"Extracted {asset['name']} but couldn't find {CLI_EXE_NAME} inside it."
        )

    report("done", f"FF16Tools.CLI ready at {cli_path}")
    return cli_path


def build_unpack_command(
    cli_path: Path,
    input_dir: Path,
    output_dir: Path,
    game_type: str = "fft",
    filter_text: Optional[str] = None,
    include_diff: bool = False,
) -> list[str]:
    """
    `filter_text` maps to the CLI's --filter option: a plain substring
    match against each file's internal path within the pack, so "nxd/"
    extracts only the game data tables and skips the ~30GB of everything
    else. See game_install.py for the folder-to-filter mapping.

    `include_diff` maps to --include-diff. Left off by default on purpose:
    .diff.pac files are *installed mods*, so including them would quietly
    unpack someone else's modded data as if it were vanilla, and every
    reference/preview in this tool would be wrong in ways that are very
    hard to notice.
    """
    command = [
        str(cli_path),
        "unpack-all-packs",
        "-i", str(input_dir),
        "-o", str(output_dir),
        "-g", game_type,
        "-s",  # skip prompts, since a GUI wizard is driving this
    ]
    if filter_text:
        command.extend(["--filter", filter_text])
    if include_diff:
        command.append("--include-diff")
    return command



# Kept as thin aliases (rather than changing every call site below) - the
# real implementations now live in proc_util.py so audiomog.py can share
# them without duplicating the Wine-wrapping/streaming logic.
_for_platform = proc_util.for_platform
_run_streaming = proc_util.run_streaming


def build_unpack_single_command(
    cli_path: Path,
    pack_file: Path,
    output_dir: Path,
    game_type: str = "fft",
    filter_text: Optional[str] = None,
) -> list[str]:
    """
    The `unpack-all` verb: one specific .pac rather than a whole folder.

    Needed because `unpack-all-packs` takes a directory and unpacks every
    .pac in it, with no way to leave one out - and the mod loader puts its
    own generated packs in that same directory. Selecting pack files
    individually is the only way to keep mod output out of an unpacked copy
    that's meant to be vanilla.
    """
    command = [
        str(cli_path),
        "unpack-all",
        "-i", str(pack_file),
        "-o", str(output_dir),
        "-g", game_type,
    ]
    if filter_text:
        command.extend(["--filter", filter_text])
    return command


def run_unpack_single_pack(
    cli_path: Path,
    pack_file: Path,
    output_dir: Path,
    game_type: str = "fft",
    line_cb: Optional[Callable[[str], None]] = None,
    filter_text: Optional[str] = None,
) -> int:
    command = _for_platform(
        cli_path,
        build_unpack_single_command(cli_path, pack_file, output_dir, game_type, filter_text),
    )
    return _run_streaming(command, line_cb)


def run_unpack_all_packs(
    cli_path: Path,
    input_dir: Path,
    output_dir: Path,
    game_type: str = "fft",
    line_cb: Optional[Callable[[str], None]] = None,
    filter_text: Optional[str] = None,
    include_diff: bool = False,
) -> int:
    """
    Runs `FF16Tools.CLI unpack-all-packs`, streaming stdout/stderr lines to
    line_cb as they arrive (so a GUI log box can show live progress).
    Returns the process return code. See build_unpack_command for what
    filter_text/include_diff do.
    """
    command = _for_platform(
        cli_path,
        build_unpack_command(cli_path, input_dir, output_dir, game_type, filter_text, include_diff),
    )
    return _run_streaming(command, line_cb)


def build_nxd_to_sqlite_command(
    cli_path: Path, nxd_dir: Path, sqlite_path: Path, game_type: str = "fft"
) -> list[str]:
    return [
        str(cli_path),
        "nxd-to-sqlite",
        "-i", str(nxd_dir),
        "-o", str(sqlite_path),
        "-g", game_type,
    ]


def run_nxd_to_sqlite(
    cli_path: Path,
    nxd_dir: Path,
    sqlite_path: Path,
    game_type: str = "fft",
    line_cb: Optional[Callable[[str], None]] = None,
) -> int:
    """
    Runs `FF16Tools.CLI nxd-to-sqlite`, converting every .nxd file found
    directly inside nxd_dir into tables in a fresh SQLite database at
    sqlite_path (overwriting it if it already exists).
    """
    command = _for_platform(cli_path, build_nxd_to_sqlite_command(cli_path, nxd_dir, sqlite_path, game_type))
    return _run_streaming(command, line_cb)


def build_sqlite_to_nxd_command(
    cli_path: Path, sqlite_path: Path, output_nxd_dir: Path, tables: Optional[list[str]] = None,
    game_type: str = "fft",
) -> list[str]:
    command = [
        str(cli_path),
        "sqlite-to-nxd",
        "-i", str(sqlite_path),
        "-o", str(output_nxd_dir),
        "-g", game_type,
    ]
    if tables:
        command.append("-t")
        command.extend(tables)
    return command


def run_sqlite_to_nxd(
    cli_path: Path,
    sqlite_path: Path,
    output_nxd_dir: Path,
    tables: Optional[list[str]] = None,
    game_type: str = "fft",
    line_cb: Optional[Callable[[str], None]] = None,
) -> int:
    """
    Runs `FF16Tools.CLI sqlite-to-nxd`, converting the given table(s) - or
    every table in the database if tables is None/empty - back into .nxd
    files under output_nxd_dir.
    """
    command = _for_platform(
        cli_path, build_sqlite_to_nxd_command(cli_path, sqlite_path, output_nxd_dir, tables, game_type)
    )
    return _run_streaming(command, line_cb)


def build_tex_to_dds_command(cli_path: Path, input_path: Path) -> list[str]:
    return [str(cli_path), "tex-conv", "-i", str(input_path)]


def run_tex_to_dds(
    cli_path: Path, input_path: Path, line_cb: Optional[Callable[[str], None]] = None
) -> int:
    """
    Runs `FF16Tools.CLI tex-conv`, converting a .tex file (or every .tex file
    in a folder) into .dds. No -o flag exists for this command - the CLI
    writes each output file next to its corresponding input file, same
    name, .dds extension.
    """
    command = _for_platform(cli_path, build_tex_to_dds_command(cli_path, input_path))
    return _run_streaming(command, line_cb)


def build_img_to_tex_command(cli_path: Path, input_path: Path) -> list[str]:
    return [str(cli_path), "img-conv", "-i", str(input_path)]


def run_img_to_tex(
    cli_path: Path, input_path: Path, line_cb: Optional[Callable[[str], None]] = None
) -> int:
    """
    Runs `FF16Tools.CLI img-conv`, converting an image (.dds recommended -
    mips supported; .png/.jpg/.gif/.bmp/.tga/.webp also accepted, exported
    internally as R8G8B8A8_UNORM) into a .tex file written next to the
    input, same name, .tex extension. Caller is responsible for naming the
    input file to match whatever .tex filename is actually wanted (see
    texture_data.py) - the CLI has no separate "output name" concept here.
    """
    command = _for_platform(cli_path, build_img_to_tex_command(cli_path, input_path))
    return _run_streaming(command, line_cb)
