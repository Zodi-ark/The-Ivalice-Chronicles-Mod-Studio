"""
Reference tables (JobData.xml, JobCommandData.xml, AbilityData.xml and the
item/trap tables) come from the mod loader's repo, so this tool stays
correct if the loader adds new jobs/commands or fixes existing data -
without ever requiring a game unpack for these particular tables.

BUNDLED FIRST. All 13 tables ship in data/, and that is what a normal
launch uses - no network, no waiting, works offline by default. GitHub is
consulted only when the user presses "Check for updates", or on the
periodic check the setup page schedules. Downloaded copies land in
local_data/cache/ and are preferred afterwards, but only while they are
newer than the bundled ones.
"""

from __future__ import annotations

import json
import shutil
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from . import constants as c
from . import paths

USER_AGENT = "Ivalice-Chronicles-Mod-Studio (github.com/Zodi-ark)"
REQUEST_TIMEOUT_SECONDS = 15


@dataclass
class FetchResult:
    path: Path
    source: str          # "downloaded" | "cache" | "bundled"
    detail: str          # human-readable status message


def _bundled_path(filename: str) -> Path:
    return paths.project_root() / "data" / filename


def _cache_dir() -> Path:
    cache = paths.local_data_dir() / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    return cache


def _cache_path(filename: str) -> Path:
    return _cache_dir() / filename


def _http_get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return response.read()


def load_local_table(filename: str) -> FetchResult:
    """
    The best copy already on this machine, with NO network access at all.

    Prefers a previously downloaded copy over the bundled one, but only when
    it is actually newer - a Mod Studio update can ship tables newer than
    whatever a user downloaded months ago, and silently preferring the stale
    download would make the update pointless.
    """
    bundled = _bundled_path(filename)
    cache_path = _cache_path(filename)
    try:
        cache_is_newer = (
            cache_path.is_file()
            and (not bundled.is_file() or cache_path.stat().st_mtime >= bundled.stat().st_mtime)
        )
    except OSError:
        cache_is_newer = False

    if cache_is_newer:
        return FetchResult(
            path=cache_path, source="cache",
            detail=f"Using the downloaded copy of {filename}.",
        )
    return FetchResult(
        path=bundled, source="bundled",
        detail=f"Using the copy of {filename} bundled with this tool.",
    )


def fetch_latest_table(filename: str, force_refresh: bool = False) -> FetchResult:
    """
    A reference table, from the network only when explicitly asked.

    force_refresh=False (the default, and what startup uses) never touches
    the network - it returns whatever is already on disk. Only an explicit
    "Check for updates" downloads.

    This used to be the other way round: every launch re-downloaded all 13
    tables from raw.githubusercontent.com before anything could be edited.
    That was wrong on three counts. It made a local, offline-capable editor
    depend on GitHub being reachable to start up; with a 15-second timeout
    per file it could stall for minutes on a flaky connection; and it put
    13 requests per user per launch onto somebody else's repository, which
    is the sort of thing that gets a raw.githubusercontent.com address rate
    limited for everyone. Every one of those tables ships bundled, so none
    of it bought anything on a normal launch.
    """
    if not force_refresh:
        return load_local_table(filename)

    cache_path = _cache_path(filename)
    try:
        data = _http_get(c.table_raw_url(filename))
        cache_path.write_bytes(data)
        return FetchResult(
            path=cache_path,
            source="downloaded",
            detail=f"Downloaded the latest {filename} from {c.MODLOADER_REPO}.",
        )
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        local = load_local_table(filename)
        return FetchResult(
            path=local.path,
            source=local.source,
            detail=f"Couldn't reach GitHub ({exc}); {local.detail[0].lower()}{local.detail[1:]}",
        )


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
