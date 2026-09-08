"""
Detecting a Reloaded-II install so generated mods can be placed directly
into its Mods folder instead of requiring a manual copy step.

Reloaded-II is portable/self-contained - it has no fixed install path, and
the user can put it (and move it) anywhere:
https://reloaded-project.github.io/Reloaded-II/
Mods live in <install>/Mods, which isn't always pre-created - manual
installation instructions have users create that folder themselves.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

# Reloaded-II ships as Reloaded-II.exe / Reloaded-II32.exe at its install
# root, alongside a Loader folder (containing Reloaded.Mod.Loader.dll).
# Any of these existing is a good signal a folder really is a Reloaded-II
# install, without requiring the exact case of the .exe name to match
# (Windows filesystems are case-insensitive anyway).
_INSTALL_MARKERS = ["Reloaded-II.exe", "Reloaded-II32.exe", "Loader"]


def looks_like_reloaded_install(folder: Path) -> bool:
    if not folder.exists() or not folder.is_dir():
        return False
    return any((folder / marker).exists() for marker in _INSTALL_MARKERS)


def mods_folder_for(reloaded_root: Path) -> Path:
    mods = reloaded_root / "Mods"
    mods.mkdir(parents=True, exist_ok=True)  # not always pre-created
    return mods


# Reloaded-II records where it lives in its own launcher config, which
# always sits at this fixed per-user location regardless of where the
# portable install itself was put:
#   %APPDATA%/Reloaded-Mod-Loader-II/ReloadedII.json
# (referenced directly by Reloaded-II's own troubleshooting docs). Its
# LauncherPath field is the full path to Reloaded-II.exe, so the install
# root is that file's parent - far more reliable than guessing folders.
_CONFIG_RELATIVE_DIR = "Reloaded-Mod-Loader-II"
_CONFIG_FILENAME = "ReloadedII.json"


def _launcher_config_path() -> Optional[Path]:
    appdata = os.environ.get("APPDATA")
    candidates = []
    if appdata:
        candidates.append(Path(appdata) / _CONFIG_RELATIVE_DIR / _CONFIG_FILENAME)
    # Wine/Proton keeps the same layout under the fake Windows drive, which
    # is how Reloaded-II is run on Linux and the Steam Deck.
    home = Path.home()
    candidates.append(
        home / ".wine" / "drive_c" / "users" / os.environ.get("USER", "")
        / "AppData" / "Roaming" / _CONFIG_RELATIVE_DIR / _CONFIG_FILENAME
    )
    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue
    return None


def _read_launcher_config() -> Optional[dict]:
    config_path = _launcher_config_path()
    if config_path is None:
        return None
    try:
        return json.loads(config_path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return None  # missing or malformed - just means "couldn't detect"


def find_installed_reloaded() -> Optional[Path]:
    """
    Reloaded-II's install root, found from its own launcher config first
    and a short list of common locations second. Returns None if nothing
    convincing turns up, in which case the caller should just let the user
    browse - Reloaded-II is portable and can legitimately live anywhere.
    """
    config = _read_launcher_config()
    if config:
        launcher_path = config.get("LauncherPath")
        if launcher_path:
            root = Path(str(launcher_path)).parent
            if looks_like_reloaded_install(root):
                return root

    home = Path.home()
    common = [
        home / "Desktop" / "Reloaded-II",
        home / "Reloaded-II",
        home / "Downloads" / "Reloaded-II",
        home / "Documents" / "Reloaded-II",
    ]
    for drive in "CDEFGHIJKLMNOPQRSTUVWXYZ":
        common.append(Path(f"{drive}:/Reloaded-II"))
        common.append(Path(f"{drive}:/Games/Reloaded-II"))
    for candidate in common:
        if looks_like_reloaded_install(candidate):
            return candidate
    return None


def configured_mods_folder() -> Optional[Path]:
    """
    Where Reloaded-II's own config says it actually loads mods from.

    Worth cross-checking against mods_folder_for() above: in portable mode
    that's always <install>/Mods, but a non-portable install stores an
    explicit ModConfigDirectory that can point somewhere else entirely. A
    mod written to the wrong folder simply never shows up in the launcher,
    with no error to explain why - so General Setup surfaces a warning when
    the two disagree rather than silently exporting into the void.

    Returns None if the config can't be read or doesn't say.
    """
    config = _read_launcher_config()
    if not config:
        return None
    if config.get("UsePortableMode"):
        launcher_path = config.get("LauncherPath")
        return Path(str(launcher_path)).parent / "Mods" if launcher_path else None
    configured = config.get("ModConfigDirectory")
    return Path(str(configured)) if configured else None


def effective_mods_folder(reloaded_root: Path) -> Path:
    """
    Where a generated mod should actually be written so Reloaded-II sees it.

    `<install>/Mods` is only guaranteed in portable mode. A non-portable
    install records an explicit ModConfigDirectory that can point anywhere,
    and a mod written to the wrong place simply never appears in the
    launcher, with no error to explain why - so prefer whatever the
    launcher's own config says and fall back to the conventional layout
    only when there's no usable config.
    """
    configured = configured_mods_folder()
    if configured is not None:
        try:
            configured.mkdir(parents=True, exist_ok=True)
            return configured
        except OSError:
            pass  # unwritable/unreachable - fall through to the conventional path
    return mods_folder_for(reloaded_root)


def installed_mod_ids(reloaded_root: Optional[Path] = None) -> list:
    """
    The ModId of every mod currently installed in Reloaded-II, so a mod
    being built here can declare a dependency on one by picking it from a
    list instead of typing an id exactly right from memory.

    Any unreadable or malformed ModConfig.json is skipped rather than
    raising - one broken third-party mod shouldn't stop the rest listing.
    """
    mods_dir = configured_mods_folder()
    if mods_dir is None and reloaded_root is not None:
        mods_dir = reloaded_root / "Mods"
    if mods_dir is None:
        return []

    found = set()
    try:
        children = list(mods_dir.iterdir())
    except OSError:
        return []
    for child in children:
        config_path = child / "ModConfig.json"
        try:
            if not config_path.is_file():
                continue
            data = json.loads(config_path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            continue
        mod_id = data.get("ModId")
        if isinstance(mod_id, str) and mod_id.strip():
            found.add(mod_id.strip())
    return sorted(found)
