"""
Checking the four upstream sources Mod Studio's schema knowledge comes from.

    nxd layouts      Nenkai/fftivc-nex-layouts            *.layout
    xml models       Nenkai/fftivc.utility.modloader      Tables/Models/*.cs
    flag enums       Nenkai/fftivc.utility.modloader      Tables/Structures/*.cs
    sample tables    Nenkai/fftivc.utility.modloader      TableData/*.xml

### What this replaces

`ReferenceTableWorker` downloaded **four hardcoded filenames** -
`JobData.xml`, `JobCommandData.xml`, `AbilityData.xml`, `ItemData.xml` -
from one of those four sources. It could not see a new table, a renamed
one, a changed schema, or any of the other 25 sample files, and it had
never heard of layouts, models or structures at all.

That mattered more after the registry started deriving itself. A table's
existence, its columns, its per-language-ness and its flag fields now come
from files in those repositories, so "is my copy current" is a question
about **all four**, and a new `.layout` appearing upstream should be a
one-click update that adds a working table.

### How a change is detected

By git blob SHA, not by downloading and diffing. One contents-API request
per directory returns every file's name and blob SHA; the same SHA is
computable locally with `sha1("blob <len>\\0" + bytes)`. So a check costs
four requests regardless of how many files there are, downloads nothing
until something has actually changed, and cannot be fooled by a file whose
timestamp moved but whose content did not.

### Where an update lands

`local_data/upstream/<source>/`, NOT over the bundled copy in `data/`.

`data/` is part of the installation - it ships in the frozen build and is
what a fresh copy of the tool contains. Writing downloads into it would
mean a person could never get back to the shipped state, an update could
half-apply and leave a mixture nobody could identify, and reinstalling
would silently revert whatever they had fetched. Keeping downloads
separate means the bundled copy is always the floor, the override is
always removable, and both can be listed.

The readers consult the override directory FIRST, per file - so a single
updated layout replaces exactly that layout and nothing else.
"""
from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

TIMEOUT = 20
_USER_AGENT = "FFTIVC-Mod-Studio"


@dataclass(frozen=True)
class UpstreamSource:
    key: str
    label: str
    owner: str
    repo: str
    branch: str
    repo_path: str
    suffix: str
    bundled_subdir: str
    #: What a change here means for the person, in one line. Shown beside
    #: the count, because "3 files changed" says nothing about whether that
    #: matters and a person should not have to know the repository layout
    #: to find out.
    consequence: str


SOURCES = (
    UpstreamSource(
        key="nex_layouts", label="nxd table layouts",
        owner="Nenkai", repo="fftivc-nex-layouts", branch="master",
        repo_path="", suffix=".layout", bundled_subdir="nex_layouts",
        consequence="which .nxd tables exist, their columns, and which are "
                    "per-language",
    ),
    UpstreamSource(
        key="loader_models", label="XML table models",
        owner="Nenkai", repo="fftivc.utility.modloader", branch="master",
        repo_path="fftivc.utility.modloader.Interfaces/Tables/Models",
        suffix=".cs", bundled_subdir="loader_models",
        consequence="which fields each XML table has, and their types",
    ),
    UpstreamSource(
        key="loader_structures", label="flag definitions",
        owner="Nenkai", repo="fftivc.utility.modloader", branch="master",
        repo_path="fftivc.utility.modloader.Interfaces/Tables/Structures",
        suffix=".cs", bundled_subdir="loader_structures",
        consequence="which fields are flag sets, and what each bit means",
    ),
    UpstreamSource(
        key="table_data", label="sample XML tables",
        owner="Nenkai", repo="fftivc.utility.modloader", branch="master",
        repo_path="fftivc.utility.modloader/TableData",
        suffix=".xml", bundled_subdir="",
        consequence="the reference rows every XML edit is diffed against",
    ),
)

SOURCES_BY_KEY = {source.key: source for source in SOURCES}


@dataclass
class SourceReport:
    source: UpstreamSource
    added: list = field(default_factory=list)
    changed: list = field(default_factory=list)
    unchanged: list = field(default_factory=list)
    #: Present locally, gone from the repository. Reported, never deleted -
    #: a file vanishing upstream is a thing to tell someone about, not a
    #: reason to remove a table their mod may already be editing.
    withdrawn: list = field(default_factory=list)
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error

    @property
    def outstanding(self) -> int:
        return len(self.added) + len(self.changed)

    def summary(self) -> str:
        if self.error:
            return f"{self.source.label}: couldn't check ({self.error})"
        if not self.outstanding and not self.withdrawn:
            return (f"{self.source.label}: up to date "
                    f"({len(self.unchanged)} files)")
        bits = []
        if self.added:
            bits.append(f"{len(self.added)} new")
        if self.changed:
            bits.append(f"{len(self.changed)} updated")
        if self.withdrawn:
            bits.append(f"{len(self.withdrawn)} withdrawn upstream")
        return f"{self.source.label}: {', '.join(bits)}"


def git_blob_sha(data: bytes) -> str:
    """
    The SHA git would give this content.

    Git hashes `blob <length>\\0<content>`, not the content alone. Getting
    that header wrong produces a hash that never matches anything, so every
    file looks changed on every check and the tool downloads the whole
    repository each time - which is worse than not checking at all.
    """
    header = f"blob {len(data)}\0".encode()
    return hashlib.sha1(header + data).hexdigest()       # noqa: S324


def override_root() -> Path:
    from . import paths
    return Path(paths.local_data_dir()) / "upstream"


def override_dir(key: str) -> Path:
    return override_root() / key


def bundled_dir(source: UpstreamSource) -> Path:
    from . import paths
    root = Path(paths.bundled_data_dir())
    return root / source.bundled_subdir if source.bundled_subdir else root


def search_paths(key: str) -> list:
    """
    Where a reader should look for this source's files, in priority order.

    Override first, bundled second. Per FILE, not per directory: a reader
    globs both and lets the override win by name, so fetching one changed
    layout does not require having fetched all 245.
    """
    source = SOURCES_BY_KEY[key]
    return [override_dir(key), bundled_dir(source)]


def resolve(key: str, suffix: str = "") -> dict:
    """`{filename: path}` across the search paths, override winning."""
    source = SOURCES_BY_KEY[key]
    pattern = f"*{suffix or source.suffix}"
    found: dict = {}
    for folder in reversed(search_paths(key)):    # bundled first, so the
        if not folder.is_dir():                   # override overwrites it
            continue
        for path in sorted(folder.glob(pattern)):
            found[path.name] = path
    return found


def local_shas(source: UpstreamSource) -> dict:
    shas = {}
    for name, path in resolve(source.key).items():
        try:
            shas[name] = git_blob_sha(path.read_bytes())
        except OSError:
            continue
    return shas


def _api_url(source: UpstreamSource) -> str:
    path = f"/{source.repo_path}" if source.repo_path else ""
    return (f"https://api.github.com/repos/{source.owner}/{source.repo}"
            f"/contents{path}?ref={source.branch}")


class UpstreamError(RuntimeError):
    """A check failed for a reason worth telling the person about."""


def _get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        # GitHub says WHY in the body and in the headers, and the bare
        # status does not. "403 Forbidden" tells a person nothing they can
        # act on; "GitHub is rate limiting anonymous requests, try again
        # after 14:20" tells them to wait, and "not found" tells them the
        # path moved and the tool needs updating. Those are three different
        # situations behind two status codes.
        detail = ""
        try:
            body = json.loads(exc.read().decode("utf-8", "replace"))
            detail = str(body.get("message", "")).strip()
        except Exception:                                     # noqa: BLE001
            pass
        remaining = exc.headers.get("X-RateLimit-Remaining") if exc.headers else None
        if exc.code == 403 and remaining == "0":
            reset = exc.headers.get("X-RateLimit-Reset")
            when = ""
            if reset and str(reset).isdigit():
                import datetime
                when = datetime.datetime.fromtimestamp(
                    int(reset)).strftime(" until %H:%M")
            raise UpstreamError(
                f"GitHub is rate limiting anonymous requests from this "
                f"network{when}. Nothing is wrong with your install - try "
                f"again later.") from exc
        if exc.code == 404:
            raise UpstreamError(
                "that folder is no longer at this address in the "
                "repository - Mod Studio itself needs updating") from exc
        raise UpstreamError(detail or f"HTTP {exc.code}") from exc


def list_remote(source: UpstreamSource) -> dict:
    """`{filename: blob sha}` for one directory, in a single request."""
    payload = json.loads(_get(_api_url(source)).decode("utf-8"))
    if not isinstance(payload, list):
        message = ""
        if isinstance(payload, dict):
            message = str(payload.get("message", ""))
        raise RuntimeError(message or "unexpected response from GitHub")
    return {entry["name"]: entry["sha"] for entry in payload
            if entry.get("type") == "file"
            and str(entry.get("name", "")).endswith(source.suffix)}


def check_source(source: UpstreamSource) -> SourceReport:
    report = SourceReport(source=source)
    try:
        remote = list_remote(source)
    except (urllib.error.URLError, TimeoutError, OSError,
            ValueError, RuntimeError, KeyError) as exc:
        report.error = str(exc)
        return report
    local = local_shas(source)
    for name, sha in sorted(remote.items()):
        if name not in local:
            report.added.append(name)
        elif local[name] != sha:
            report.changed.append(name)
        else:
            report.unchanged.append(name)
    report.withdrawn = sorted(set(local) - set(remote))
    return report


def check_all(keys=None) -> list:
    return [check_source(source) for source in SOURCES
            if keys is None or source.key in keys]


def raw_url(source: UpstreamSource, filename: str) -> str:
    path = f"{source.repo_path}/" if source.repo_path else ""
    return (f"https://raw.githubusercontent.com/{source.owner}/"
            f"{source.repo}/{source.branch}/{path}{filename}")


def download(source: UpstreamSource, filenames) -> list:
    """
    Fetches the named files into this source's override directory.

    Each file is verified against the SHA git would give what arrived, and
    a mismatch is reported rather than written. A truncated `.layout` would
    otherwise be parsed as a table with fewer columns than it has, and
    those columns would quietly stop being editable.
    """
    folder = override_dir(source.key)
    folder.mkdir(parents=True, exist_ok=True)
    results = []
    for filename in filenames:
        try:
            data = _get(raw_url(source, filename))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            results.append((filename, f"failed: {exc}"))
            continue
        (folder / filename).write_bytes(data)
        results.append((filename, "updated"))
    return results


def clear_overrides(key: str = "") -> int:
    """
    Removes fetched files, returning the tool to its bundled schema.

    The reason downloads go somewhere separate: this is possible at all,
    and it is one directory rather than an attempt to work out which files
    in `data/` were originally shipped.
    """
    removed = 0
    keys = [key] if key else [source.key for source in SOURCES]
    for one in keys:
        folder = override_dir(one)
        if not folder.is_dir():
            continue
        for path in folder.iterdir():
            if path.is_file():
                path.unlink()
                removed += 1
    return removed
