"""
Downloads the external tools the app shells out to: FF16Tools.CLI and
AudioMog, both fetched from their GitHub releases.

This module used to do two unrelated jobs. The other one was a per-file
downloader for the reference XML tables - `fetch_latest_table`, backed by a
bundled-first cache in `local_data/cache/` - and `upstream.py` replaced it
with a four-source comparison that comes to the same question (is the
bundled copy still current?) by comparing git blob SHAs across whole
directories rather than one filename at a time. The old path had no callers
left and has been removed; `_http_get` is shared with what remains and
stays.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

from . import constants as c

USER_AGENT = "Ivalice-Chronicles-Mod-Studio (github.com/Zodi-ark)"
REQUEST_TIMEOUT_SECONDS = 15










def _http_get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return response.read()






def get_latest_ff16tools_release_info() -> dict:
    """Returns the parsed GitHub API response for FF16Tools' latest release."""
    data = _http_get(c.FF16TOOLS_LATEST_RELEASE_API)
    return json.loads(data)


def pick_windows_cli_asset(release_info: dict) -> dict | None:
    """Finds the FF16Tools.CLI-*-win-x64.zip asset in a release's asset list."""
    for asset in release_info.get("assets", []):
        name = asset.get("name", "")
        if "CLI" in name and "win-x64" in name and name.endswith(".zip"):
            return asset
    return None


def download_asset(asset: dict, destination: Path) -> Path:
    url = asset["browser_download_url"]
    data = _http_get(url)
    destination.write_bytes(data)
    return destination


def get_latest_audiomog_release_info() -> dict:
    """Returns the parsed GitHub API response for AudioMog's latest release."""
    data = _http_get(c.AUDIOMOG_LATEST_RELEASE_API)
    return json.loads(data)


def pick_audiomog_exe_asset(release_info: dict) -> dict | None:
    """
    Finds the AudioMog.exe asset in a release's asset list. Unlike
    FF16Tools.CLI (a zip), AudioMog ships as a single standalone .exe - so
    this just looks for a *.exe asset rather than a zip-with-a-name-pattern.
    Prefers one actually named "audiomog" if there's more than one .exe
    asset, but falls back to any .exe present rather than failing outright.
    """
    exe_assets = [
        asset for asset in release_info.get("assets", [])
        if asset.get("name", "").lower().endswith(".exe")
    ]
    if not exe_assets:
        return None
    for asset in exe_assets:
        if "audiomog" in asset["name"].lower():
            return asset
    return exe_assets[0]


def pick_audiomog_assets(release_info: dict) -> list[dict]:
    """
    Returns every asset worth downloading from an AudioMog release - the
    .exe itself plus any accompanying config file such as
    TerminalSettings.json (present in the real release checked against -
    see tools/AudioMog/ in this project for the bundled copy). A previous
    version of this code only grabbed the .exe via pick_audiomog_exe_asset
    above, which silently meant a fresh download never got a
    TerminalSettings.json at all - AudioMog would then run with whatever
    default it generates on its own (observed for real: defaults
    ImmediatelyQuitOnceAllTasksAreDone to false), which is very likely
    why a fresh download exhibited a real reported hang. This grabs both.
    """
    return [
        asset for asset in release_info.get("assets", [])
        if asset.get("name", "").lower().endswith((".exe", ".json"))
    ]
