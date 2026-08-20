"""
Finding the installed game's packed data folder (the one full of .pac
files) without making the user hunt for it themselves.

This is the single piece of information General Setup can't get on its own
- everything else (reference tables, FF16Tools, AudioMog) either downloads
or ships bundled. Asking a first-time modder to "browse to the game's
packed data folder" assumes they already know where Steam put it and what
a .pac file is, which is exactly the assumption this tool exists to avoid.

Detection is Steam-focused, because Steam is the only PC storefront the
FFT mod loader's own install guide covers
(https://nenkai.github.io/ffxvi-modding/modding/installing_mods_fft/), and
deliberately conservative - every lookup is a direct existence check
against a known path, never a walk of the whole drive. If nothing is
found, the caller is expected to fall back to a plain Browse button rather
than treat it as an error; a user who copied their data folder somewhere
else entirely (a common "don't touch the real install" habit) is a
perfectly normal case, not a failure.

Confidence tiers, in the project's usual style:
  - CONFIRMED: Steam app id 1004640 and the install folder name
    "FINAL FANTASY TACTICS - The Ivalice Chronicles" (Steam store page,
    PCGamingWiki, and the mod loader install guide all agree).
  - CONFIRMED: pack files are .pac, read by FF16Tools with -g fft.
  - INFERRED: which subfolder of the install holds them. The mod loader
    guide refers to "the game's data/ folders" (plural) without naming
    them exactly, so rather than hardcoding a guess this module just looks
    for any folder containing .pac files and reports what it finds.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

# Steam's own app id / install folder name for the game.
STEAM_APP_ID = "1004640"
GAME_FOLDER_NAME = "FINAL FANTASY TACTICS - The Ivalice Chronicles"

# The game's two executables, per the mod loader's install guide - used
# only as a sanity signal that a folder really is the game's install root.
GAME_EXE_NAMES = ("FFT_enhanced.exe", "FFT_classic.exe")

# How deep under the install root to look for a folder of .pac files.
# The real layout puts them a level or two down; this bound keeps the scan
# instant even if a user points at something unexpectedly large.
_MAX_PACK_SEARCH_DEPTH = 4


@dataclass
class PackFolder:
    """A folder containing .pac files, ready to hand to FF16Tools."""
    path: Path
    pack_count: int

    def label(self) -> str:
        plural = "pack" if self.pack_count == 1 else "packs"
        return f"{self.path}  ({self.pack_count} {plural})"


# =============================================================================
# Steam library discovery
# =============================================================================


def _windows_steam_roots() -> list[Path]:
    """Steam's install path as recorded in the registry, if we're on Windows."""
    roots: list[Path] = []
    try:
        import winreg  # noqa: PLC0415 - Windows-only, deliberately imported lazily
    except ImportError:
        return roots

    for hive, subkey, value_name in (
        (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath"),
    ):
        try:
            with winreg.OpenKey(hive, subkey) as key:
                raw, _ = winreg.QueryValueEx(key, value_name)
            if raw:
                roots.append(Path(str(raw)))
        except OSError:
            continue  # key or value missing - just means Steam isn't registered there
    return roots


def _common_steam_roots() -> list[Path]:
    """
    Well-known Steam locations to check directly, so detection still works
    if the registry lookup comes back empty (or we're not on Windows).
    Every entry is a plain existence check - nothing here walks a drive.
    """
    candidates: list[Path] = []

    # Windows: the default install plus the usual manual/second-drive spots.
    for drive in "CDEFGHIJKLMNOPQRSTUVWXYZ":
        base = Path(f"{drive}:/")
        candidates.extend([
            base / "Program Files (x86)" / "Steam",
            base / "Program Files" / "Steam",
            base / "Steam",
            base / "SteamLibrary",
            base / "Games" / "Steam",
            base / "Games" / "SteamLibrary",
        ])

    # Linux / Steam Deck, including the Flatpak build.
    home = Path.home()
    candidates.extend([
        home / ".steam" / "steam",
        home / ".steam" / "root",
        home / ".local" / "share" / "Steam",
        home / ".var" / "app" / "com.valvesoftware.Steam" / ".local" / "share" / "Steam",
    ])
    return candidates


def _library_roots_from_vdf(steam_root: Path) -> list[Path]:
    """
    Extra library folders declared in steamapps/libraryfolders.vdf - how
    Steam records games installed on a different drive than Steam itself.
    Parsed with a regex rather than a real VDF parser on purpose: the only
    thing needed here is the "path" values, and a malformed/unexpected file
    should degrade to "found nothing", never raise.
    """
    vdf = steam_root / "steamapps" / "libraryfolders.vdf"
    try:
        text = vdf.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return [Path(m.replace("\\\\", "\\")) for m in re.findall(r'"path"\s+"([^"]+)"', text)]


def steam_library_roots() -> list[Path]:
    """Every plausible Steam library root, de-duplicated, existing ones only."""
    seen: set[Path] = set()
    ordered: list[Path] = []

    def add(path: Path) -> None:
        try:
            resolved = path.resolve()
        except OSError:
            return
        if resolved in seen or not resolved.is_dir():
            return
        seen.add(resolved)
        ordered.append(resolved)

    primary = _windows_steam_roots() + _common_steam_roots()
    for root in primary:
        add(root)

    # libraryfolders.vdf can only be read from a root we already found.
    for root in list(ordered):
        for extra in _library_roots_from_vdf(root):
            add(extra)
    return ordered


# =============================================================================
# Game install discovery
# =============================================================================


def looks_like_game_root(folder: Path) -> bool:
    """True if this folder holds one of the game's own executables."""
    try:
        return folder.is_dir() and any((folder / exe).exists() for exe in GAME_EXE_NAMES)
    except OSError:
        return False


def find_game_roots() -> list[Path]:
    """
    Every Steam library that actually has the game installed, in the order
    the libraries were discovered. Usually zero or one entry - more than
    one only if the same game folder name exists in several libraries.
    """
    found: list[Path] = []
    for library in steam_library_roots():
        candidate = library / "steamapps" / "common" / GAME_FOLDER_NAME
        try:
            if candidate.is_dir():
                found.append(candidate)
        except OSError:
            continue
    return found


def find_game_root() -> Optional[Path]:
    """The first installed copy of the game found, or None."""
    roots = find_game_roots()
    return roots[0] if roots else None


# =============================================================================
# Pack folder discovery
# =============================================================================


def count_packs(folder: Path) -> int:
    """
    How many .pac files sit directly in this folder. Directly, not
    recursively, because that's exactly what FF16Tools' unpack-all-packs
    itself looks at (it uses a non-recursive Directory.GetFiles on the
    input folder), so this count is the real "how much will it unpack".
    Modded .diff.pac files are excluded to match unpack-all-packs' own
    default behaviour of skipping them.
    """
    try:
        return sum(
            1 for entry in folder.iterdir()
            if entry.is_file()
            and entry.suffix.lower() == ".pac"
            and ".diff" not in entry.name.lower()
        )
    except OSError:
        return 0


def looks_like_pack_folder(folder: Path) -> bool:
    return count_packs(folder) > 0


def find_pack_folders(root: Path, max_depth: int = _MAX_PACK_SEARCH_DEPTH) -> list[PackFolder]:
    """
    Every folder at or under `root` (bounded by max_depth) that holds .pac
    files, richest first. Depth-bounded rather than a full walk so pointing
    this at something huge by mistake can't hang the UI thread.
    """
    results: list[PackFolder] = []
    try:
        root = root.resolve()
    except OSError:
        return results
    if not root.is_dir():
        return results

    root_depth = len(root.parts)
    for dirpath, dirnames, _filenames in os.walk(root, onerror=lambda _e: None):
        current = Path(dirpath)
        depth = len(current.parts) - root_depth
        if depth >= max_depth:
            dirnames[:] = []  # stop descending, but still check this level

        count = count_packs(current)
        if count:
            results.append(PackFolder(path=current, pack_count=count))

    results.sort(key=lambda pf: (-pf.pack_count, str(pf.path)))
    return results


def autodetect_pack_folders() -> list[PackFolder]:
    """
    The whole detection chain in one call: find the installed game, then
    find the folder(s) of .pac files inside it. Returns an empty list if
    the game isn't installed through Steam or isn't where Steam says -
    callers should fall back to asking the user to browse.

    Safe to call from a worker thread; it only touches the filesystem.
    """
    found: list[PackFolder] = []
    seen: set[Path] = set()
    for game_root in find_game_roots():
        for pack_folder in find_pack_folders(game_root):
            if pack_folder.path not in seen:
                seen.add(pack_folder.path)
                found.append(pack_folder)
    found.sort(key=lambda pf: (-pf.pack_count, str(pf.path)))
    return found


# =============================================================================
# What lives where inside an unpacked game folder
# =============================================================================
# Each .pac carries a single internal folder name, so every file it holds
# unpacks under one top-level folder (FF16Tools' README: "0001.pac has nxd
# as its embedded folder name ... ability.nxd becomes nxd/ability.nxd").
# That makes the CLI's --filter option - a plain substring match against
# each file's internal path - a reliable way to unpack just one category:
# "nxd/" matches every file in the nxd pack and nothing else.
#
# The folder list and file counts below are read straight off Zodi's real
# unpacked game folder listing (UnpackedGame_Folder.txt), not guessed.
# =============================================================================

@dataclass(frozen=True)
class GameFolder:
    """One top-level folder of an unpacked game, and what's actually in it."""
    name: str
    summary: str
    approx_files: int

    @property
    def filter_text(self) -> str:
        """
        What to pass to FF16Tools.CLI's --filter.

        The trailing slash stops "ui" matching "uidata" and the like, but it
        does **not** anchor the start: --filter is a plain substring test,
        so "ui/" still matches "bg/ui/whatever". Anything deciding what a
        pack contains has to allow for that - see the pack-claiming logic in
        step_setup, where assuming otherwise left an entire folder
        unextracted.
        """
        return f"{self.name}/"


GAME_FOLDERS: tuple[GameFolder, ...] = (
    GameFolder("nxd", "Game data tables (jobs, abilities, items, encounters) and text", 4982),
    GameFolder("ui", "Menu, portrait and icon textures", 5581),
    GameFolder("system", "Fonts and system textures", 70),
    GameFolder("char", "Character textures", 4),
    GameFolder("vfx", "Visual effect textures", 2),
    GameFolder("bg", "Map background textures", 6084),
    GameFolder("fftpack", "Classic mode assets (text, textures, sprites)", 5848),
    GameFolder("sound", "Music, voice and sound effect banks", 14546),
    GameFolder("script", "Event scripts", 1075),
    GameFolder("movie", "Full motion videos", 32),
    GameFolder("shader", "Shaders", 9),
    GameFolder("font", "Font data", 1),
)

GAME_FOLDERS_BY_NAME = {folder.name: folder for folder in GAME_FOLDERS}


@dataclass(frozen=True)
class ContentGroup:
    """
    A plain-language bundle of top-level folders, shaped around what this
    tool's own tabs need rather than around the game's folder layout - so
    the everyday choice is "do I want to edit textures?" rather than "do I
    need ui, system, char and vfx?". The per-folder view is still available
    under Advanced options for anyone who wants it.
    """
    key: str
    label: str
    detail: str
    folders: tuple[str, ...]
    default_on: bool

    @property
    def approx_files(self) -> int:
        return sum(GAME_FOLDERS_BY_NAME[name].approx_files for name in self.folders)


CONTENT_GROUPS: tuple[ContentGroup, ...] = (
    ContentGroup(
        key="game_data",
        label="Game data",
        detail=(
            "Jobs, Job Commands, Abilities, Items, Encounters, Poaching, Treasure Hunter - "
            "everything that becomes the editable database."
        ),
        folders=("nxd",),
        default_on=True,
    ),
    ContentGroup(
        key="textures",
        label="Textures",
        detail=(
            "Portraits, icons, menus, and map backgrounds for the Textures tab. "
            "Advanced options unpack can exclude undesired textures."
        ),
        folders=("ui", "system", "char", "vfx", "bg", "fftpack"),
        default_on=True,
    ),
    ContentGroup(
        key="sounds",
        label="Sounds and music",
        detail="Music, voice lines and sound effect banks, for the Sounds tab.",
        folders=("sound",),
        default_on=True,
    ),
)


def folders_present_in(unpacked_dir: Path) -> list[str]:
    """
    Which of the known top-level folders actually exist (and hold at least
    one file) inside an unpacked game folder, in GAME_FOLDERS order.

    Needed because an unpack is *selective* - unpacking only `nxd/` leaves
    a folder that is a perfectly valid "unpacked game folder" for the data
    tabs and useless to the Textures and Sounds tabs. Reporting readiness
    from "did an unpack happen" rather than "what is actually there" told
    users Textures and Sounds were ready when the folders didn't exist,
    which is worse than saying nothing.
    """
    present: list[str] = []
    for folder in GAME_FOLDERS:
        candidate = unpacked_dir / folder.name
        try:
            if candidate.is_dir() and any(candidate.iterdir()):
                present.append(folder.name)
        except OSError:
            continue
    return present


def groups_present_in(unpacked_dir: Path) -> dict:
    """
    Maps each ContentGroup key to the folders of that group actually found
    in `unpacked_dir`. A group with an empty list isn't set up, even if an
    unpack ran; a group with some but not all of its folders is partially
    set up, which the UI says out loud rather than rounding up to "ready".
    """
    present = set(folders_present_in(unpacked_dir))
    return {
        group.key: [name for name in group.folders if name in present]
        for group in CONTENT_GROUPS
    }


def folders_for_groups(group_keys: Iterable[str]) -> list[str]:
    """
    The de-duplicated top-level folder names covered by the given content
    group keys, in GAME_FOLDERS order (so the unpack runs in a stable,
    predictable sequence rather than whatever order the checkboxes were
    ticked in).
    """
    wanted: set[str] = set()
    by_key = {group.key: group for group in CONTENT_GROUPS}
    for key in group_keys:
        group = by_key.get(key)
        if group:
            wanted.update(group.folders)
    return [folder.name for folder in GAME_FOLDERS if folder.name in wanted]


def filters_for_folders(folder_names: Iterable[str]) -> Optional[list[str]]:
    """
    The --filter strings needed to unpack exactly `folder_names`, or None
    meaning "no filter at all - unpack everything in one pass".

    FF16Tools takes one filter per run, so N folders means N runs, and each
    run re-opens every pack up front. When the selection covers every known
    folder anyway, a single unfiltered run does the same work once instead
    of twelve times. (Reading each pack's internal folder name directly to
    run exactly one pass per pack was considered and rejected: it lives at
    a fixed header offset but behind the archive's XOR header encryption,
    so it would mean reimplementing FF16Tools' decryption and key handling
    here just to save a few seconds of header parsing.)
    """
    names = [name for name in folder_names if name in GAME_FOLDERS_BY_NAME]
    if not names:
        return []
    if len(names) == len(GAME_FOLDERS):
        return None
    return [GAME_FOLDERS_BY_NAME[name].filter_text for name in names]


# =============================================================================
# Individual pack files, and telling vanilla apart from mod output
# =============================================================================
# The FFT mod loader applies mods by building its own .pac files alongside
# the game's ("modded.pac", "modded.en.pac", and so on). unpack-all-packs
# takes a *folder*, so it happily unpacks those too - and because they sort
# after the numbered vanilla packs, their files overwrite the vanilla ones
# in the output. The result is an "unpacked game" that is quietly a mix of
# vanilla and whatever mods happen to be installed, which is exactly the
# thing this tool's reference data must not be.
#
# Classification is by filename, because that's all that can be known
# without opening every pack. Anything that isn't recognised as mod output
# is treated as vanilla, so an unfamiliar naming scheme errs towards
# unpacking too much rather than silently skipping real game data - and the
# Advanced options list lets the user correct either way.
# =============================================================================

# Substrings that mark a pack as generated rather than shipped.
_MOD_PACK_MARKERS = ("modded", ".diff.")


@dataclass
class PackFile:
    path: Path
    is_mod_output: bool

    @property
    def name(self) -> str:
        return self.path.name

    def label(self) -> str:
        suffix = "  (created by the mod loader, not part of the game)" if self.is_mod_output else ""
        return f"{self.name}{suffix}"


def looks_like_mod_pack(name: str) -> bool:
    lowered = name.lower()
    return any(marker in lowered for marker in _MOD_PACK_MARKERS)


def list_pack_files(folder: Path) -> list[PackFile]:
    """
    Every .pac sitting directly in `folder`, vanilla first then mod output,
    each alphabetical. Matches what unpack-all-packs itself would see
    (Directory.GetFiles, non-recursive).
    """
    try:
        entries = [e for e in folder.iterdir() if e.is_file() and e.suffix.lower() == ".pac"]
    except OSError:
        return []
    packs = [PackFile(path=e, is_mod_output=looks_like_mod_pack(e.name)) for e in entries]
    packs.sort(key=lambda p: (p.is_mod_output, p.name.lower()))
    return packs


def vanilla_pack_files(folder: Path) -> list[PackFile]:
    return [p for p in list_pack_files(folder) if not p.is_mod_output]
