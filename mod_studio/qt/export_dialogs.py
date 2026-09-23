"""
Where the "save as" and "export to which folder" dialogs open.

Reported: "when exporting sounds or textures the file browser that asks you
where to save the textures or sounds opens in the windows System32 folder
which feels kinda scary, instead can it open to the root of the drive that
mod studio is on. Furthermore after usage it should remember the last
position that a user saved to and open to that instead."

System32 was nobody's choice. Every export dialog was given a bare file
name, or nothing, as its starting point, and a dialog with no folder starts
in the process's WORKING directory - which for a program started from a
shortcut or the Start menu on Windows can be `C:\\Windows\\System32`.

So every export dialog on Textures, Sounds and the item and ability texture
slots goes through here:

- **The first time**, it opens at the root of the drive Mod Studio is on
  (`F:\\` for a copy in `F:\\Mods\\...`).
- **After that**, at the last folder anything was saved to, from any of
  them - one memory, because "where I put my exports" is one place. Kept
  across launches, in `ui_settings.json` beside the other remembered
  folders.
- **A remembered folder that has gone** falls back to its nearest parent
  that still exists, then to the drive root. A dialog that opens on a
  missing folder opens on the working directory instead - the same
  System32 this is here to stop.

**The Open dialogs too** - choosing a replacement image or WAV. Reported
next: "Choosing a replacement (image or WAV) still opens in System32. You
can decide if they should remember the same folder as exports, or their
own." Their OWN, seeded from the exports':

- **Until a replacement has been chosen**, they open where the last export
  went. The usual round trip is export, edit, bring it back - and the file
  to bring back is in the folder it was exported to.
- **After that**, where the last replacement came from. Replacements
  often come from somewhere else entirely - a folder of music, an artist's
  deliveries - and that folder is not where exports should start going.
  One shared memory would drag each towards the other every time.

Only a path somebody actually chose in a dialog is remembered. The callers'
`path=` arguments, which the suites use to skip the dialog, are not choices
and do not move it.

**Engine note.** `ui_settings.load()` returns only the keys in its
`DEFAULTS`, and adding one there is a change to `mod_studio/ui_settings.py`
that waits on approval. `ui_settings.save()` already keeps keys it does not
know ("an older build won't strip settings a newer one wrote"), so this
writes through it and reads its own key back from the same file. If
`last_export_folder` is added to `DEFAULTS`, `_remembered()` becomes
`ui_settings.load()["last_export_folder"]` and nothing else changes; the
same for `last_replacement_folder`.
"""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtWidgets import QFileDialog

from .. import paths, ui_settings

#: The settings keys. Not in `ui_settings.DEFAULTS` - see the module notes.
SETTING = "last_export_folder"
OPEN_SETTING = "last_replacement_folder"


def drive_root() -> Path:
    """The root of the drive Mod Studio itself is on."""
    root = Path(paths.project_root()).resolve()
    return Path(root.anchor) if root.anchor else root


def _remembered(key: str = SETTING) -> str:
    try:
        raw = json.loads(ui_settings.settings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    value = raw.get(key, "") if isinstance(raw, dict) else ""
    return value if isinstance(value, str) else ""


def _existing(remembered: str):
    """The remembered folder, or its nearest parent that still exists."""
    remembered = (remembered or "").strip()
    if not remembered:
        return None
    folder = Path(remembered)
    for candidate in (folder, *folder.parents):
        try:
            if candidate.is_dir():
                return candidate
        except OSError:
            continue
    return None


def start_folder() -> Path:
    """Where the next export dialog should open."""
    return _existing(_remembered()) or drive_root()


def open_start_folder() -> Path:
    """
    Where the next "choose a replacement" dialog should open: the last
    folder a replacement came from, else where exports go, else the root.
    """
    return _existing(_remembered(OPEN_SETTING)) or start_folder()


def remember(chosen: str | Path, is_folder: bool = False) -> None:
    """Records where somebody just saved, for the next dialog."""
    if not chosen:
        return
    folder = Path(chosen) if is_folder else Path(chosen).parent
    ui_settings.save(**{SETTING: str(folder)})


def save_file(parent, title: str, filename: str, filters: str) -> str:
    """
    A "save as" dialog opening at `start_folder()` with `filename` offered.
    Returns the chosen path, or "" if cancelled.
    """
    path, _ = QFileDialog.getSaveFileName(
        parent, title, str(start_folder() / filename), filters)
    if path:
        remember(path)
    return path or ""


def open_file(parent, title: str, filters: str) -> str:
    """
    A "choose a file" dialog for a replacement, opening at
    `open_start_folder()`. Returns the chosen path, or "" if cancelled.
    """
    path, _ = QFileDialog.getOpenFileName(
        parent, title, str(open_start_folder()), filters)
    if path:
        ui_settings.save(**{OPEN_SETTING: str(Path(path).parent)})
    return path or ""


def choose_folder(parent, title: str) -> str:
    """An "export into which folder" dialog opening at `start_folder()`."""
    folder = QFileDialog.getExistingDirectory(parent, title,
                                              str(start_folder()))
    if folder:
        remember(folder, is_folder=True)
    return folder or ""
