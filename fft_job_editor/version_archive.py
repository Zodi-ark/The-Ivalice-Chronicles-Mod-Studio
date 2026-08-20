"""
Keeping a copy of each game version's `.nxd` files.

Migration needs the vanilla data a mod was built against. Once the player
patches, that data is gone from their disk and cannot be re-obtained -
there is no archive of old game builds to download. So unless Mod Studio
keeps a copy at unpack time, "update this mod for the new game" is
unanswerable for everyone who patched before they thought to save anything.
This module is therefore not a convenience; it is the precondition for the
whole feature.

**Why the `.nxd` and not the converted database.** A `.sqlite` is a derived
artefact of one particular FF16Tools build. HANDOFF already records the
hazard: a row FF16Tools reads differently across versions shows up as a
spurious diff, and the only guard is that both sides were converted by the
same build. An archive of databases accumulated over months would be that
hazard at scale - a 1.5.0 baseline converted by one build, a 1.5.3 baseline
by another, and every comparison between them contaminated by converter
differences masquerading as game changes.

Archiving the `.nxd` removes it entirely: both sides are re-converted with
today's bundled FF16Tools whenever they're compared, so the converter is
always constant across any single comparison. It also means the archive
gets *better* when FF16Tools improves, rather than being frozen at whatever
that build happened to get wrong - which matters given this project has
already hit one real misparse (`Unknown04`).

**Why the converted database as well.** It is readable the moment it's
unzipped, with no FF16Tools invocation at all, and that is what makes
comparing two archived versions instant.

Sizes are now close, because unpacking converts every `.nxd` the game ships
rather than the 37 that have editing tabs - the database went from 2.3 MB to
15.2 MB when that changed. The cache is no longer the cheap half of this
pair, but it is still worth keeping: without it every comparison between two
archived versions would need two full conversions first.

Both, measured:

    nxd.zip     ~3.5 MB   complete (all 564 files), immune to converter
                          drift, needs a conversion to read
    data.zip    ~3.7 MB   every table, instantly readable, tied to one
                          converter build

    total       ~7.2 MB per version

The database is a **cache**, not the archive. It records which FF16Tools
build produced it (`converter_fingerprint`), and any reader that finds a
mismatch ignores it and re-derives from the `.nxd`. That's only possible
because the `.nxd` is still there - which is the whole reason to keep both
rather than choosing.

The division of labour follows from what each is good for: migration merges
the 37 modelled tables and gets them instantly from the cache, while the
version-comparison view and the assessment of tables the editor has no tab
for need all 564 and go to the `.nxd`.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import migration
from . import paths

ARCHIVE_DIRNAME = "game_versions"
NXD_ZIP_NAME = "nxd.zip"
DATA_ZIP_NAME = "data.zip"
DATA_MEMBER_NAME = "fft_data.sqlite"
MANIFEST_NAME = "manifest.json"

# How many archived versions to keep when pruning automatically. Generous on
# purpose: each one is ~7 MB, and unlike almost anything else this tool
# writes, a deleted archive cannot be recreated - the game build it came
# from is no longer installed. Five versions is roughly a year of patches
# for about 36 MB.
DEFAULT_KEEP_COUNT = 5


def archive_root() -> Path:
    root = paths.local_data_dir() / ARCHIVE_DIRNAME
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_dirname(version: str) -> str:
    """
    A folder name from a version string.

    The string comes out of the game's own data, so it isn't trusted to be
    a safe path component - a value containing a separator would otherwise
    write outside the archive folder.
    """
    cleaned = "".join(ch if (ch.isalnum() or ch in "._-") else "_" for ch in version.strip())
    return cleaned.strip("._") or "unknown"


@dataclass
class ArchivedVersion:
    """One archived game version."""
    version: str
    directory: Path
    archived_at: float = 0.0
    file_count: int = 0
    size_bytes: int = 0
    source: str = ""
    # False when the unpack that produced this included mod packs, so the
    # data is a mix of vanilla and whatever was installed. See
    # game_install.looks_like_mod_pack - a baseline like that makes every
    # diff drawn against it wrong, which is worth recording rather than
    # discovering later.
    clean_unpack: Optional[bool] = None
    # True when the version string couldn't be read and the folder is named
    # by date instead. Such an archive is still usable - the author can say
    # what it is - it just can't be matched to a mod automatically.
    version_unknown: bool = False
    # Which FF16Tools build produced the cached database. A cache from a
    # different build is ignored rather than trusted: a converter that
    # reads a column differently would turn its own change into a
    # "the game changed this", which is the exact failure archiving the
    # .nxd exists to prevent.
    converter: str = ""

    @property
    def nxd_zip(self) -> Path:
        return self.directory / NXD_ZIP_NAME

    @property
    def data_zip(self) -> Path:
        return self.directory / DATA_ZIP_NAME

    def has_usable_cache(self, converter: str) -> bool:
        """Whether the cached database can be trusted for this converter."""
        return bool(converter) and self.converter == converter and self.data_zip.exists()

    @property
    def size_mb(self) -> float:
        return self.size_bytes / 1_000_000

    def describe(self) -> str:
        when = time.strftime("%Y-%m-%d", time.localtime(self.archived_at)) if self.archived_at else "unknown date"
        label = self.version if not self.version_unknown else f"{self.version} (version not readable)"
        detail = f"{label} - {self.file_count} file(s), {self.size_mb:.1f} MB, saved {when}"
        if self.data_zip.exists():
            detail += ", ready to read"
        if self.clean_unpack is False:
            detail += " - WARNING: unpacked with mod packs included"
        return detail


def _write_manifest(entry: ArchivedVersion) -> None:
    manifest = {
        "Version": entry.version,
        "ArchivedAt": entry.archived_at,
        "FileCount": entry.file_count,
        "SizeBytes": entry.size_bytes,
        "Source": entry.source,
        "CleanUnpack": entry.clean_unpack,
        "VersionUnknown": entry.version_unknown,
        "Converter": entry.converter,
    }
    try:
        (entry.directory / MANIFEST_NAME).write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
    except OSError:
        pass   # the zip is the archive; a missing manifest degrades, it doesn't break


def _read_manifest(directory: Path) -> ArchivedVersion:
    entry = ArchivedVersion(version=directory.name, directory=directory)
    try:
        raw = json.loads((directory / MANIFEST_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raw = {}
    if isinstance(raw, dict):
        entry.version = str(raw.get("Version") or directory.name)
        entry.archived_at = float(raw.get("ArchivedAt") or 0.0)
        entry.file_count = int(raw.get("FileCount") or 0)
        entry.size_bytes = int(raw.get("SizeBytes") or 0)
        entry.source = str(raw.get("Source") or "")
        clean = raw.get("CleanUnpack")
        entry.clean_unpack = clean if isinstance(clean, bool) else None
        entry.version_unknown = bool(raw.get("VersionUnknown"))
        entry.converter = str(raw.get("Converter") or "")
    if not entry.size_bytes:
        entry.size_bytes = _archive_size(directory)
    return entry


def _archive_size(directory: Path) -> int:
    total = 0
    for name in (NXD_ZIP_NAME, DATA_ZIP_NAME):
        try:
            total += (directory / name).stat().st_size
        except OSError:
            pass
    return total


def converter_fingerprint(cli_path: Optional[Path]) -> str:
    """
    A short, stable identifier for the FF16Tools build in use.

    Hashes the executable rather than reading a version string, because the
    bundled copy doesn't carry one anywhere reachable and a hash answers the
    only question that matters exactly: is this the same binary that
    produced the cached database? Returns "" when the tool isn't available,
    which reads as "can't vouch for any cache" everywhere it's used.
    """
    if not cli_path:
        return ""
    path = Path(cli_path)
    try:
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()[:16]
    except OSError:
        return ""


def archive_unpacked_nxd(nxd_dir: Path, version: Optional[str],
                         source: str = "", clean_unpack: Optional[bool] = None,
                         root: Optional[Path] = None,
                         sqlite_path: Optional[Path] = None,
                         converter: str = "") -> Optional[ArchivedVersion]:
    """
    Copies an unpacked game's `.nxd` folder into the archive under its
    version name.

    `version` is what migration.read_game_version found in the converted
    database. When it's None the archive is still written, named by date
    and flagged - refusing to archive because one string was unreadable
    would throw away data that cannot be recovered, which is a far worse
    outcome than a folder with an awkward name.

    Re-archiving a version already held is a no-op rather than an error:
    unpacking twice on the same game build is a completely normal thing to
    do, and the second copy would be identical.
    """
    nxd_dir = Path(nxd_dir)
    if not nxd_dir.is_dir():
        return None
    files = sorted(p for p in nxd_dir.glob("*.nxd") if p.is_file())
    if not files:
        return None

    version_unknown = not version
    name = _safe_dirname(version) if version else time.strftime("unknown-%Y%m%d-%H%M%S")

    base = Path(root) if root is not None else archive_root()
    directory = base / name
    if (directory / NXD_ZIP_NAME).exists():
        return _read_manifest(directory)

    directory.mkdir(parents=True, exist_ok=True)
    # Written to a temporary name and moved into place, so an interrupted
    # archive can't leave a half-written zip that later looks complete.
    temp_zip = directory / (NXD_ZIP_NAME + ".partial")
    try:
        with zipfile.ZipFile(temp_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            for path in files:
                zf.write(path, arcname=path.name)
        temp_zip.replace(directory / NXD_ZIP_NAME)
    except OSError:
        temp_zip.unlink(missing_ok=True)
        return None

    # The converted database goes in beside it as a cache. Small enough
    # (~0.75 MB against the .nxd's ~4 MB) that skipping it would save
    # almost nothing, and it removes an FF16Tools run from every future
    # comparison.
    cached = _cache_database(directory, sqlite_path)

    entry = ArchivedVersion(
        version=version or name,
        directory=directory,
        archived_at=time.time(),
        file_count=len(files),
        size_bytes=_archive_size(directory),
        source=source,
        clean_unpack=clean_unpack,
        version_unknown=version_unknown,
        converter=converter if cached else "",
    )
    _write_manifest(entry)
    return entry


def _cache_database(directory: Path, sqlite_path: Optional[Path]) -> bool:
    """Zips the converted database beside the .nxd archive. Best-effort."""
    if not sqlite_path:
        return False
    sqlite_path = Path(sqlite_path)
    if not sqlite_path.is_file():
        return False
    temp = directory / (DATA_ZIP_NAME + ".partial")
    try:
        with zipfile.ZipFile(temp, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            zf.write(sqlite_path, arcname=DATA_MEMBER_NAME)
        temp.replace(directory / DATA_ZIP_NAME)
        return True
    except OSError:
        temp.unlink(missing_ok=True)
        return False


def open_archived_database(entry: ArchivedVersion, destination: Path,
                           converter: str = "") -> Optional[Path]:
    """
    A usable database for an archived version, from the cache when it can be
    trusted.

    Returns None when it can't, which is the caller's cue to extract the
    `.nxd` and convert. Deliberately not doing that conversion here: it
    needs FF16Tools, wants to run on a worker thread, and belongs to
    whoever can report progress, not to a storage module.
    """
    if not entry.has_usable_cache(converter):
        return None
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / DATA_MEMBER_NAME

    # Already extracted: hand it straight back. An archive is immutable and
    # the cache is keyed by converter, so a file sitting here can't be
    # stale - and re-extracting it is not merely wasted work, it is
    # actively dangerous. Callers hit this repeatedly (every on_show
    # re-identifies the baseline), and a background refresh landing while a
    # comparison is reading this exact path would truncate the database
    # under the reader mid-query. That produced a review claiming 44
    # conflicts against a game version that had changed nothing.
    if target.exists() and target.stat().st_size > 0:
        return target

    # Extracted under a temporary name and renamed into place, so even two
    # callers racing here can only ever publish a complete file.
    temp = destination / (DATA_MEMBER_NAME + f".partial{os.getpid()}")
    try:
        with zipfile.ZipFile(entry.data_zip) as zf:
            member = next(
                (i for i in zf.infolist()
                 if Path(i.filename).name.lower().endswith(".sqlite")), None
            )
            if member is None:
                return None
            with zf.open(member) as src, open(temp, "wb") as dest:
                shutil.copyfileobj(src, dest)
        temp.replace(target)
    except (OSError, zipfile.BadZipFile, StopIteration):
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass
        return None
    return target


def list_archived(root: Optional[Path] = None) -> list:
    """Every archived version, newest first."""
    base = Path(root) if root is not None else archive_root()
    if not base.is_dir():
        return []
    entries = [
        _read_manifest(child) for child in base.iterdir()
        if child.is_dir() and (child / NXD_ZIP_NAME).exists()
    ]
    return sorted(entries, key=lambda e: (e.archived_at, e.version), reverse=True)


def find_archived(version: str, root: Optional[Path] = None) -> Optional[ArchivedVersion]:
    """The archive for a given version string, if it's held."""
    if not version:
        return None
    wanted = _safe_dirname(version)
    for entry in list_archived(root):
        if _safe_dirname(entry.version) == wanted:
            return entry
    return None


def extract_archived(entry: ArchivedVersion, destination: Path) -> Path:
    """
    Unpacks an archived version's `.nxd` files ready for conversion.

    Extraction is filtered to plain `.nxd` filenames rather than trusting
    the zip's own entry names. The archive is written by this tool, so this
    is belt-and-braces, but a zip is exactly the format where a crafted
    path escapes the directory it's supposed to land in.
    """
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(entry.nxd_zip) as zf:
        for info in zf.infolist():
            name = Path(info.filename).name
            if info.is_dir() or not name.lower().endswith(".nxd"):
                continue
            with zf.open(info) as src, open(destination / name, "wb") as dest:
                shutil.copyfileobj(src, dest)
    return destination


# ---------------------------------------------------------------------------
# Pruning
# ---------------------------------------------------------------------------

def versions_in_use(mods_dir: Optional[Path], installed_version: str = "") -> set:
    """
    Which archived versions something still depends on.

    "No longer relevant" is worth computing rather than guessing from age.
    A version matters if it's the one currently installed, or if some mod
    sitting in the Reloaded-II Mods folder was built against it - that mod
    might not be opened for months, and the day it is, its baseline needs
    to still exist.

    Only stamped mods can be matched this way. Dating an unstamped mod means
    converting its `.nxd`, which is far too expensive for a housekeeping
    check, so those are simply not counted - which is the conservative
    direction to be wrong in only because the keep-count below is generous.
    """
    in_use = set()
    if installed_version:
        in_use.add(_safe_dirname(installed_version))
    if not mods_dir:
        return in_use
    mods_dir = Path(mods_dir)
    if not mods_dir.is_dir():
        return in_use
    for config_path in sorted(mods_dir.glob("*/ModConfig.json")):
        try:
            config = json.loads(config_path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            continue
        if not isinstance(config, dict):
            continue
        stamp = migration.read_stamp(config)
        if stamp.game_version:
            in_use.add(_safe_dirname(stamp.game_version))
    return in_use


@dataclass
class PrunePlan:
    """What pruning would delete, and what it would keep and why."""
    remove: list = field(default_factory=list)
    keep_in_use: list = field(default_factory=list)
    keep_recent: list = field(default_factory=list)

    def freed_bytes(self) -> int:
        return sum(e.size_bytes for e in self.remove)

    def summary(self) -> str:
        if not self.remove:
            return "Nothing to remove."
        return (f"{len(self.remove)} archived version(s) would be removed, "
                f"freeing {self.freed_bytes() / 1_000_000:.1f} MB.")


def plan_prune(in_use: set, keep_count: int = DEFAULT_KEEP_COUNT,
               root: Optional[Path] = None) -> PrunePlan:
    """
    Decides which archives are safe to remove, without removing anything.

    Two protections, in order: a version something depends on is never a
    candidate at all, and beyond those the most recent `keep_count` are
    kept. Deletion is irreversible in a way almost nothing else in this
    tool is, so the plan is returned for display rather than acted on.
    """
    plan = PrunePlan()
    candidates = []
    for entry in list_archived(root):          # newest first
        if _safe_dirname(entry.version) in in_use:
            plan.keep_in_use.append(entry)
        else:
            candidates.append(entry)
    plan.keep_recent = candidates[:keep_count]
    plan.remove = candidates[keep_count:]
    return plan


def apply_prune(plan: PrunePlan) -> list:
    """Deletes what a plan lists. Returns the versions actually removed."""
    removed = []
    for entry in plan.remove:
        try:
            shutil.rmtree(entry.directory)
            removed.append(entry.version)
        except OSError:
            continue   # a locked folder shouldn't abort the rest
    return removed


def total_size_bytes(root: Optional[Path] = None) -> int:
    return sum(entry.size_bytes for entry in list_archived(root))
