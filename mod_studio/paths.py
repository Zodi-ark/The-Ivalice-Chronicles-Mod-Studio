"""
Keeps every file this tool downloads or caches at runtime inside its own
project folder (next to the launcher script or the .exe), instead of
scattering it into a hidden folder in the user's home directory. The goal:
if someone wants to stop using this tool, deleting the one folder they
downloaded it into removes everything - no hunting through
AppData/.config/home-directory dot-folders.

There are TWO roots, and conflating them is what a frozen build breaks.

    project_root()   the folder the user downloaded. Their files go here.
    bundled_root()   where the tool's own shipped files are. Read-only.

Running from source they are the same folder, which is why one function did
both jobs for as long as there was no .exe. A PyInstaller build separates
them:

    dist/The Ivalice Chronicles Mod Studio/     <- project_root()
        The Ivalice Chronicles Mod Studio.exe
        local_data/                             <- the user's own files
        _internal/                              <- bundled_root()
            data/  assets/  tools/

Getting this wrong is not a cosmetic problem. With `project_root()` left as
`Path(__file__).parent.parent`, a frozen build resolves it to `_internal/`
and buries the user's unpacked game and settings inside a folder whose name
tells them not to open it - and which an installer would reasonably treat as
replaceable program files. Under a one-file build it resolves to a temporary
directory that Windows deletes when the program closes, so everything the
user built would be silently destroyed on every run.
"""

from __future__ import annotations

import os
import sys
import threading
import uuid
from pathlib import Path


def project_root() -> Path:
    """
    The folder the user downloaded, and where their own files belong.

    Frozen: the folder containing the executable. Deliberately NOT the
    bundle - the whole point of the layout is that deleting this one folder
    removes every trace of the tool, so the user's data has to sit where
    they can see it, beside the program they double-click.

    From source: the project folder, as before.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    # This file lives at <project_root>/mod_studio/paths.py
    return Path(__file__).resolve().parent.parent


def bundled_root() -> Path:
    """
    Where the tool's own shipped files live: data/, assets/, tools/.

    Frozen: the bundle directory PyInstaller extracts to, which it reports
    as `sys._MEIPASS` - `_internal/` in a one-folder build. These are the
    tool's files, not the user's, so they stay in the bundle where an
    updated build can replace them wholesale.

    From source: the project folder, same as project_root().
    """
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        return Path(bundle).resolve()
    return Path(__file__).resolve().parent.parent


def bundled_data_dir() -> Path:
    """Read-only reference tables that ship with the tool."""
    return bundled_root() / "data"


def bundled_assets_dir() -> Path:
    """Icons and the logo."""
    return bundled_root() / "assets"


def bundled_tools_dir() -> Path:
    """
    Where the MIT-licensed external tools (FF16Tools.CLI, AudioMog) ship
    bundled with this project, read-only - see tools/FF16Tools/LICENSE.txt
    and tools/AudioMog/LICENSE for their respective terms. Separate from
    local_data/, which is where a manually-downloaded newer version gets
    extracted to instead if the user chooses to update past what's bundled.

    Bundled, not project, root: these ship with the tool and are replaced by
    a new build, whereas anything the user downloads themselves belongs in
    local_data/ where their own files are.
    """
    return bundled_root() / "tools"


_local_data_dir: Path | None = None
_local_data_lock = threading.Lock()


def local_data_dir() -> Path:
    """
    Where anything downloaded/cached at runtime lives (FF16Tools binaries,
    the cached JobData.xml, the unpacked game folder, the converted
    database). This is separate from data/, which is the read-only reference
    copy bundled with the tool itself.

    Resolved ONCE per process and cached. That is not an optimisation - it
    is the fix for a real bug.

    This used to write-probe the folder on every single call and silently
    fall back to a per-user directory if the probe failed. Two problems:

    - The probe wrote and deleted the SAME filename every time, and this app
      calls local_data_dir() from background threads (the table fetch, the
      autodetect pass, the export worker). Two threads probing at once meant
      one deleted the other's probe file, the loser got FileNotFoundError -
      a subclass of OSError - and concluded the folder was unwritable.
    - The consequence was severe and silent: the caller got an EMPTY
      fallback directory, so the previously unpacked game folder and
      converted database appeared not to exist. That is the intermittent
      "Game data, Textures and Sounds are never ready after relaunch"
      report, and why closing and reopening usually fixed it.

    Resolving once also rules out something worse than the reported symptom:
    a mid-session flip would have scattered one session's files across two
    directories.
    """
    global _local_data_dir
    with _local_data_lock:
        if _local_data_dir is None:
            _local_data_dir = _resolve_local_data_dir()
        return _local_data_dir


def _resolve_local_data_dir() -> Path:
    preferred = project_root() / "local_data"
    if _ensure_writable(preferred):
        return preferred

    # Fallback for the rare case the project folder genuinely isn't writable
    # (e.g. installed somewhere locked-down) - better to work from a per-user
    # location than to crash outright.
    fallback = Path.home() / ".ivalice_chronicles_mod_studio" / "local_data"
    try:
        fallback.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return fallback


def _ensure_writable(directory: Path) -> bool:
    """
    Probe filename is unique per process AND per call, so concurrent probes
    can't delete each other's file, and unlink tolerates the file already
    being gone.
    """
    probe = directory / f".write_test_{os.getpid()}_{uuid.uuid4().hex}"
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe.write_text("ok", encoding="utf-8")
        return True
    except OSError:
        return False
    finally:
        try:
            probe.unlink(missing_ok=True)
        except OSError:
            pass
