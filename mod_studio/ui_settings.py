"""
Small persistent store for UI preferences that should survive closing the
app.

Only view preferences live here - which toggles are ticked. Nothing about a
mod, nothing about the game install, nothing that affects what gets
exported. If this file is missing, unreadable, or full of nonsense, every
setting falls back to its default and the app carries on; a preferences file
must never be a reason the tool fails to start.

Kept deliberately separate from the mod state in gui/app.py, which is
per-session and per-mod by design.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import paths

SETTINGS_FILENAME = "ui_settings.json"

# name -> default. Adding a preference means adding a line here and nothing
# else; unknown keys already in a user's file are preserved on save, so an
# older build won't strip settings a newer one wrote.
DEFAULTS = {
    "hide_field_notes": False,
    "hide_unknown_fields": False,
    "export_show_all_sections": False,
    # Compare Versions: show every column of a changed row, not just the
    # columns that differ. Off by default because it's a lot of text; on
    # when you need the surrounding context to tell what a change means.
    "compare_show_full_rows": False,
    # Appearance, for the Qt interface. "system" follows the OS light/dark
    # setting live; "light" and "dark" pin it regardless of the OS.
    "appearance": "dark",
    # Windows 11 backdrop material behind the window: "mica", "acrylic" or
    # "none". Composited by the desktop manager, so it costs real frames on
    # weak hardware - "none" is a plain opaque window and always available.
    "window_backdrop": "none",
    # Unix timestamp of the last reference-table update check. 0 = never.
    # Kept here rather than in local_data/cache so that clearing the cache
    # doesn't silently turn every launch back into a download.
    "tables_last_checked": 0.0,
}


def settings_path() -> Path:
    return paths.local_data_dir() / SETTINGS_FILENAME


def load() -> dict:
    """Every stored preference, with defaults filled in for anything absent."""
    values = dict(DEFAULTS)
    try:
        raw = json.loads(settings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return values
    if not isinstance(raw, dict):
        return values
    for key, default in DEFAULTS.items():
        if key in raw and isinstance(raw[key], type(default)):
            values[key] = raw[key]
    return values


def save(**changes) -> None:
    """
    Writes preferences, merging over whatever is already on disk.

    Merging rather than overwriting so two panels can each save their own
    settings without clobbering the other's, and so a key written by a newer
    build survives being loaded by an older one.
    """
    path = settings_path()
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(existing, dict):
            existing = {}
    except (OSError, ValueError):
        existing = {}
    existing.update(changes)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    except OSError:
        # Read-only install directory, full disk, permissions - none of which
        # should cost the user their click.
        pass
