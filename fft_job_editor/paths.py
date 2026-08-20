"""
Keeps every file this tool downloads or caches at runtime inside its own
project folder (next to the launcher script), instead of scattering it into a hidden
folder in the user's home directory. The goal: if someone wants to stop
using this tool, deleting the one folder they downloaded it into removes
everything - no hunting through AppData/.config/home-directory dot-folders.
"""

from __future__ import annotations

import os
import threading
import uuid
from pathlib import Path


def project_root() -> Path:
    # This file lives at <project_root>/fft_job_editor/paths.py
    return Path(__file__).resolve().parent.parent


def bundled_tools_dir() -> Path:
    """
    Where the MIT-licensed external tools (FF16Tools.CLI, AudioMog) ship
    bundled with this project, read-only - see tools/FF16Tools/LICENSE.txt
    and tools/AudioMog/LICENSE for their respective terms. Separate from
    local_data/, which is where a manually-downloaded newer version gets
    extracted to instead if the user chooses to update past what's bundled.
    """
    return project_root() / "tools"


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
