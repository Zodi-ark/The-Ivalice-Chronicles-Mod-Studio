"""
Builds a complete, drag-into-Reloaded-II mod folder:

    <ModId>/
      ModConfig.json
      FFTIVC/tables/<mode>/JobData.xml

The ModConfig.json shape below matches a real published FFT mod
(github.com/Zodi-ark/Dark-Knight-Expansion) rather than a guessed schema.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import constants as c


# The FFT mod loader itself - every mod this tool produces is a set of
# table/data overrides that only that loader knows how to apply, so it's a
# real dependency of every generated mod, not a suggestion.
MOD_LOADER_ID = "fftivc.utility.modloader"

# Where Reloaded-II looks for a mod's own GitHub auto-update settings.
# Verified against Reloaded-II's source rather than guessed: the key is the
# resolver's own ResolverId (GitHubReleasesUpdateResolverFactory.ResolverId
# == "GitHubRelease"), read back via
# PluginData.TryGetValue<GitHubConfig>(factory.ResolverId, ...) in
# IUpdateResolverFactory.TryGetConfiguration. The four field names below
# are GitHubConfig's own properties.
GITHUB_UPDATE_PLUGIN_KEY = "GitHubRelease"

# GitHubConfig.AssetFileName's own default. Only used as a fallback when a
# release has no metadata file; kept because Reloaded-II writes it too.
DEFAULT_UPDATE_ASSET_NAME = "Mod.zip"

# Stamped into a mod's PluginData alongside the game/table versions, so a
# future build can tell how a stamp was produced if the format ever needs
# to change. Bump only when the stamp's own shape changes, not on every
# release of the tool.
STUDIO_STAMP_VERSION = "1"

# What a preview image is saved as inside the mod folder. ModIcon is a
# path relative to ModConfig.json (Reloaded-II resolves it with
# Path.Combine(configDir, ModIcon)), so a fixed name keeps the mod folder
# self-contained no matter where the user's source image came from.
ICON_FILENAME = "preview.png"


@dataclass
class ModMetadata:
    mod_id: str
    mod_name: str
    author: str
    version: str
    description: str
    game_mode: str  # "enhanced" | "classic" | "combined"

    # -- optional, all with sensible defaults for a brand new mod --------
    tags: list = field(default_factory=list)
    dependencies: list = field(default_factory=lambda: [MOD_LOADER_ID])
    # None means "derive from game_mode" (the usual case); an explicit list
    # lets someone ship an enhanced-mode table set that also shows up under
    # the classic executable, which SupportedAppId genuinely allows.
    supported_app_ids: Optional[list] = None
    project_url: str = ""
    # Absolute path to a source image the user picked; copied into the mod
    # folder as ICON_FILENAME at scaffold time. None means "no icon", which
    # is different from "keep whatever icon the existing mod already had".
    icon_source: Optional[Path] = None
    icon_filename: str = ""
    # GitHub Releases auto-update. Inactive unless both user and repo are set.
    github_user: str = ""
    github_repo: str = ""
    github_use_release_tag: bool = True
    github_asset_filename: str = DEFAULT_UPDATE_ASSET_NAME
    # Which game data this mod was built against, recorded so a future
    # release can re-express it on top of a newer game without having to
    # guess. See migration.py - a mod that ships a ui.*.nxd can be dated
    # from that instead, but most mods don't, and nothing should have to
    # ship a whole UI table just to be datable.
    built_against_game_version: str = ""
    built_against_table_versions: dict = field(default_factory=dict)
    built_against_clean_unpack: Optional[bool] = None

    @property
    def resolved_app_ids(self) -> list:
        if self.supported_app_ids:
            return list(self.supported_app_ids)
        return list(c.SUPPORTED_APP_IDS[self.game_mode])

    @property
    def resolved_dependencies(self) -> list:
        """The mod loader is always required, and always listed first."""
        deps = [MOD_LOADER_ID]
        deps.extend(d for d in self.dependencies if d and d != MOD_LOADER_ID)
        return deps

    def github_update_enabled(self) -> bool:
        return bool(self.github_user.strip() and self.github_repo.strip())

    def github_plugin_data(self) -> dict:
        return {
            "UserName": self.github_user.strip(),
            "RepositoryName": self.github_repo.strip(),
            "UseReleaseTag": bool(self.github_use_release_tag),
            "AssetFileName": self.github_asset_filename.strip() or DEFAULT_UPDATE_ASSET_NAME,
        }


_MOD_ID_RE = re.compile(r"^[a-z0-9]+(\.[a-z0-9_]+)+$")


def suggest_mod_id(category: str, mod_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "", mod_name.lower())
    category_slug = re.sub(r"[^a-z0-9]+", "", category.lower()) or "gameplay"
    return f"fftivc.{category_slug}.{slug}"


def validate_mod_id(mod_id: str) -> Optional[str]:
    """Returns an error message if invalid, otherwise None."""
    if not _MOD_ID_RE.match(mod_id):
        return (
            "Mod ID should look like 'fftivc.category.modname' - lowercase "
            "letters/numbers only, dot-separated (e.g. fftivc.gameplay.mymod)."
        )
    return None


def build_mod_config(meta: ModMetadata) -> dict:
    config = {
        "ModId": meta.mod_id,
        "ModName": meta.mod_name,
        "ModAuthor": meta.author,
        "ModVersion": meta.version,
        "ModDescription": meta.description,
        "ModDll": "",
        "ModIcon": meta.icon_filename or (ICON_FILENAME if meta.icon_source else ""),
        "ModR2RManagedDll32": "",
        "ModR2RManagedDll64": "",
        "ModNativeDll32": "",
        "ModNativeDll64": "",
        "Tags": list(meta.tags),
        "CanUnload": None,
        "HasExports": None,
        "IsLibrary": False,
        "PluginData": {},
        "IsUniversalMod": False,
        "ModDependencies": meta.resolved_dependencies,
        "OptionalDependencies": [],
        "SupportedAppId": meta.resolved_app_ids,
        "ProjectUrl": meta.project_url,
    }
    _apply_update_settings(config, meta)
    return config


def _apply_update_settings(config: dict, meta: ModMetadata) -> None:
    """
    Writes (or clears) the mod's own GitHub Releases auto-update block
    in-place, leaving every other PluginData key alone.

    Other keys matter: Reloaded-II writes a "GitHubDependencies" block into
    a mod's PluginData describing how to fetch its *dependencies*, and
    stomping that would break automatic dependency installation for anyone
    downloading the mod. So this only ever touches its own key.
    """
    plugin_data = dict(config.get("PluginData") or {})
    if meta.github_update_enabled():
        plugin_data[GITHUB_UPDATE_PLUGIN_KEY] = meta.github_plugin_data()
    else:
        plugin_data.pop(GITHUB_UPDATE_PLUGIN_KEY, None)
    config["PluginData"] = plugin_data
    _apply_build_stamp(config, meta)


def _apply_build_stamp(config: dict, meta: ModMetadata) -> None:
    """
    Records which game version and reference tables this mod was built
    against, in its own PluginData key.

    Imported here rather than at module scope because migration.py imports
    nxd_data, which this module has no other reason to pull in.

    Only ever written when we actually know the answer: an absent stamp is
    honest and migration falls back to reading the mod's own ui.*.nxd,
    whereas a stamp guessed at export time would be believed.
    """
    from . import migration

    existing = migration.read_stamp(config)
    stamp = migration.ModStamp(
        game_version=meta.built_against_game_version or existing.game_version,
        table_versions=dict(meta.built_against_table_versions or existing.table_versions),
        clean_unpack=(meta.built_against_clean_unpack
                      if meta.built_against_clean_unpack is not None
                      else existing.clean_unpack),
        studio_version=STUDIO_STAMP_VERSION,
    )
    if stamp.game_version or stamp.table_versions:
        migration.apply_stamp(config, stamp)


def merge_mod_config(existing: dict, meta: ModMetadata) -> dict:
    """
    Updates only the fields this editor manages, leaving everything else in
    an existing ModConfig.json untouched - packaging include/ignore
    regexes, release metadata filename, DLL paths, and any PluginData
    belonging to other tools. Used when regenerating a mod opened via
    open_existing_mod(), so re-exporting doesn't quietly wipe settings this
    tool has no field for.

    The fields it *does* now manage (icon, dependencies, supported apps,
    project URL, GitHub auto-update) are all loaded back into the form when
    a mod is opened, so a straight round-trip preserves them; clearing one
    in the form is a deliberate instruction to clear it in the file.
    """
    merged = dict(existing)
    merged["ModId"] = meta.mod_id
    merged["ModName"] = meta.mod_name
    merged["ModAuthor"] = meta.author
    merged["ModVersion"] = meta.version
    merged["ModDescription"] = meta.description
    merged["SupportedAppId"] = meta.resolved_app_ids
    merged["ModDependencies"] = meta.resolved_dependencies
    merged["ProjectUrl"] = meta.project_url
    if meta.tags:
        merged["Tags"] = list(meta.tags)

    # Only overwrite the icon when the user actually picked a new one -
    # otherwise an existing mod's icon (which this tool didn't put there
    # and can't see the source of) survives a regenerate untouched.
    if meta.icon_source is not None:
        merged["ModIcon"] = meta.icon_filename or ICON_FILENAME
    elif meta.icon_filename:
        merged["ModIcon"] = meta.icon_filename

    _apply_update_settings(merged, meta)
    return merged


def read_update_settings(config: dict) -> dict:
    """
    Pulls a mod's existing GitHub auto-update settings back out of its
    ModConfig.json, for populating the form when opening a mod. Returns
    empty strings/defaults when the block is missing or malformed.
    """
    block = (config.get("PluginData") or {}).get(GITHUB_UPDATE_PLUGIN_KEY)
    if not isinstance(block, dict):
        block = {}
    return {
        "user": str(block.get("UserName") or ""),
        "repo": str(block.get("RepositoryName") or ""),
        "use_release_tag": bool(block.get("UseReleaseTag", True)),
        "asset_filename": str(block.get("AssetFileName") or DEFAULT_UPDATE_ASSET_NAME),
    }


@dataclass
class ExistingMod:
    mod_root: Path
    config: dict
    game_mode: Optional[str]           # which tables/<mode>/ the JobData.xml came from
    edits: dict                        # job_id -> {field: value}, from xml_io.parse_diff_xml
    table_version: str
    other_modes_found: list            # modes that also have a JobData.xml, not loaded
    job_command_game_mode: Optional[str] = None      # which tables/<mode>/ JobCommandData.xml came from
    job_command_edits: dict = None                   # command_id -> {field: value}
    # command_id -> {tag: text} for elements this tool doesn't model, kept
    # so rewriting the mod gives them back rather than quietly dropping
    # them. See parse_job_command_diff_xml.
    job_command_preserved: dict = None
    # job_id -> {tag: text}: each JobData entry as it was, verbatim.
    job_preserved: dict = None
    job_command_table_version: str = "1"
    job_command_other_modes_found: list = None
    # Diffs for every other XML table (items, shops, treasure, ability
    # effect/animation), keyed by the same table_key as item_xml_io.ALL_SPECS.
    table_edits: dict = field(default_factory=dict)
    # XML tables recovered through a derived spec, keyed by filename.
    derived_table_edits: dict = field(default_factory=dict)
    derived_table_versions: dict = field(default_factory=dict)
    # {table key: {entry id: {tag: text}}} - each entry as it was, so
    # rewriting gives back elements this tool doesn't model.
    table_preserved: dict = field(default_factory=dict)
    table_versions: dict = field(default_factory=dict)
    table_game_mode: Optional[str] = None

    def __post_init__(self):
        if self.job_command_edits is None:
            self.job_command_edits = {}
        if self.job_command_preserved is None:
            self.job_command_preserved = {}
        if self.job_preserved is None:
            self.job_preserved = {}
        if self.job_command_other_modes_found is None:
            self.job_command_other_modes_found = []


def open_existing_mod(mod_root: Path) -> ExistingMod:
    """
    Reads an existing mod folder's ModConfig.json and every XML diff table
    it contains, for "open this mod to continue editing".

    What comes back here: Job Data, Job Commands, the six Item tables, shop
    availability, Treasure Hunter, and the ability effect/animation tables -
    everything stored as an XML diff.

    Edits exported as binary .nxd (ability and item text, encounters,
    poaching) are recovered separately by nxd_data.recover_edits_from_sqlite,
    because they need the mod's .nxd converted back to SQLite and diffed
    against the vanilla database - i.e. FF16Tools and unpacked game files,
    neither of which this function has. See SetupStep._start_nxd_recovery.

    Replaced textures and sounds are not recovered as editable changes at
    all; they're carried through untouched on re-export.

    Raises FileNotFoundError / ValueError with a clear message on problems.
    """
    config_path = mod_root / "ModConfig.json"
    if not config_path.exists():
        raise FileNotFoundError(
            f"No ModConfig.json found in {mod_root} - pick the mod's root folder "
            f"(the one that directly contains ModConfig.json)."
        )
    config = json.loads(config_path.read_text(encoding="utf-8-sig"))

    # xml_io is imported lazily to avoid a circular import (xml_io doesn't
    # need anything from modconfig, but keeping the dependency one-directional
    # is simpler to reason about).
    from . import xml_io

    found_job_modes = [
        mode for mode in c.GAME_MODES
        if (mod_root / "FFTIVC" / "tables" / mode / "JobData.xml").exists()
    ]
    job_mode = found_job_modes[0] if found_job_modes else None
    job_edits, job_version, job_preserved = ({}, "1", {})
    if job_mode:
        job_edits, job_version, job_preserved = xml_io.parse_diff_xml(
            mod_root / "FFTIVC" / "tables" / job_mode / "JobData.xml"
        )

    found_cmd_modes = [
        mode for mode in c.GAME_MODES
        if (mod_root / "FFTIVC" / "tables" / mode / "JobCommandData.xml").exists()
    ]
    cmd_mode = found_cmd_modes[0] if found_cmd_modes else None
    cmd_edits, cmd_version, cmd_preserved = ({}, "1", {})
    if cmd_mode:
        cmd_edits, cmd_version, cmd_preserved = xml_io.parse_job_command_diff_xml(
            mod_root / "FFTIVC" / "tables" / cmd_mode / "JobCommandData.xml"
        )

    # Every other XML diff table this tool writes - Items and its five
    # companion tables, shop availability, Treasure Hunter, and the two
    # ability sub-tables. These all run through item_xml_io's TableSpec
    # engine, so reading them back is the same one loop as writing them;
    # they were simply never loaded, which meant opening your own mod
    # silently showed no item/treasure/ability-effect edits even though the
    # files were sitting right there.
    from . import item_xml_io
    from . import paths

    table_edits: dict = {}
    table_preserved: dict = {}
    table_versions: dict = {}
    table_mode: Optional[str] = None
    for table_key, spec in item_xml_io.ALL_SPECS.items():
        filename = c.TABLE_FILENAMES[table_key]
        for mode in c.GAME_MODES:
            candidate = mod_root / "FFTIVC" / "tables" / mode / filename
            if not candidate.exists():
                continue
            try:
                edits, version, entry_preserved = item_xml_io.parse_diff_xml(candidate, spec)
            except Exception:  # noqa: BLE001 - a malformed table shouldn't block the rest
                continue
            if edits:
                table_edits[table_key] = edits
                table_versions[table_key] = version
                table_mode = table_mode or mode
            if entry_preserved:
                table_preserved[table_key] = entry_preserved
            break  # first mode that has this table wins, same rule as Job Data

    # XML tables with no hand-written spec.
    #
    # The loop above walks ALL_SPECS - the eleven declared tables. Mod
    # Studio can now WRITE the other seventeen through All Game Data, so
    # scanning only the eleven meant opening a mod that contains, say,
    # StatusEffectData.xml recovered every other table it holds and
    # silently ignored that one. The tool could produce a mod it could not
    # read back, which is the same fault the .nxd side had before
    # `recover_unmodelled_edits`.
    derived_edits: dict = {}
    derived_versions: dict = {}
    declared_shapes = {(spec.root_tag, spec.entry_tag)
                       for spec in item_xml_io.ALL_SPECS.values()}
    for filename, spec in item_xml_io.discover_specs(
            paths.bundled_data_dir()).items():
        if (spec.root_tag, spec.entry_tag) in declared_shapes:
            continue
        if filename in c.XML_HANDLED_ELSEWHERE:
            continue
        for mode in c.GAME_MODES:
            candidate = mod_root / "FFTIVC" / "tables" / mode / filename
            if not candidate.exists():
                continue
            try:
                edits, version, _preserved = item_xml_io.parse_diff_xml(
                    candidate, spec)
            except Exception:  # noqa: BLE001 - one bad table must not block the rest
                continue
            if edits:
                derived_edits[filename] = edits
                derived_versions[filename] = version
                table_mode = table_mode or mode
            break

    return ExistingMod(
        mod_root=mod_root,
        config=config,
        game_mode=job_mode,
        edits=job_edits,
        job_preserved=job_preserved,
        table_version=job_version,
        other_modes_found=found_job_modes[1:],
        job_command_game_mode=cmd_mode,
        job_command_edits=cmd_edits,
        job_command_preserved=cmd_preserved,
        job_command_table_version=cmd_version,
        job_command_other_modes_found=found_cmd_modes[1:],
        table_edits=table_edits,
        derived_table_edits=derived_edits,
        derived_table_versions=derived_versions,
        table_preserved=table_preserved,
        table_versions=table_versions,
        table_game_mode=table_mode,
    )


def scaffold_mod_folder(
    output_root: Path,
    meta: ModMetadata,
    job_data_xml_text: str,
    config: Optional[dict] = None,
    job_command_xml_text: Optional[str] = None,
    extra_table_files: Optional[dict] = None,
) -> Path:
    """
    Creates <output_root>/<ModId>/ModConfig.json and
    <output_root>/<ModId>/FFTIVC/tables/<mode>/JobData.xml, plus
    JobCommandData.xml alongside it if job_command_xml_text is given, plus
    whatever's in extra_table_files ({filename: xml_text}, e.g. the six
    Item*Data.xml files - kept as a generic dict rather than six more named
    parameters since they're all written the same way).

    Pass `config` (e.g. from merge_mod_config) to write a specific config
    dict instead of building a fresh one from `meta`.

    Returns the mod's root folder path.
    """
    mod_root = output_root / meta.mod_id
    mod_root.mkdir(parents=True, exist_ok=True)

    config = config if config is not None else build_mod_config(meta)

    # The preview image has to be *inside* the mod folder: Reloaded-II
    # resolves ModIcon relative to ModConfig.json, so pointing it at the
    # user's original file elsewhere on disk would show a broken icon on
    # any other machine (and break as soon as they move the source image).
    if meta.icon_source is not None:
        import shutil

        icon_name = meta.icon_filename or ICON_FILENAME
        try:
            destination = mod_root / icon_name
            if Path(meta.icon_source).resolve() != destination.resolve():
                shutil.copy(meta.icon_source, destination)
            config["ModIcon"] = icon_name
        except OSError:
            # A missing/unreadable source shouldn't abort the whole export -
            # far better to ship the mod without an icon than not at all.
            config["ModIcon"] = ""

    (mod_root / "ModConfig.json").write_text(
        json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    tables_dir = mod_root / "FFTIVC" / "tables" / meta.game_mode
    tables_dir.mkdir(parents=True, exist_ok=True)
    (tables_dir / "JobData.xml").write_text(job_data_xml_text, encoding="utf-8")

    if job_command_xml_text is not None:
        (tables_dir / "JobCommandData.xml").write_text(job_command_xml_text, encoding="utf-8")

    for filename, xml_text in (extra_table_files or {}).items():
        (tables_dir / filename).write_text(xml_text, encoding="utf-8")

    return mod_root


def data_output_dir(mod_root: Path, mode: str) -> Path:
    """
    FFTIVC/data/<mode>/ - the parent of nxd_output_dir's own nxd/
    subfolder, and also where texture replacements land, mirroring their
    exact relative path from the unpacked game root (e.g. bg/textures/017/
    gt_0_map017_map_color.tga or ui/ffto/common/face/texture/blkface_05_04_
    uitx.tex) - same general "mirror the unpacked structure" convention as
    nxd/, just without a fixed subfolder name since every texture's own
    path already encodes where it goes.
    """
    d = mod_root / "FFTIVC" / "data" / mode
    d.mkdir(parents=True, exist_ok=True)
    return d


def nxd_output_dir(mod_root: Path, mode: str) -> Path:
    """
    FFTIVC/data/<mode>/nxd/ - where .nxd file replacements live, by analogy
    to FFTIVC/tables/<mode>/ for the XML diff tables. Originally an
    unverified assumption (see HANDOFF.md); now confirmed directly against
    two real published mods that ship .nxd overrides this way (Zodi's own
    Divine Dragoon Meliadoul and the WotL Equipment Replacer mod) - no
    special ModConfig.json entry needed, same drop-in convention as tables/.
    """
    d = mod_root / "FFTIVC" / "data" / mode / "nxd"
    d.mkdir(parents=True, exist_ok=True)
    return d


def copy_nxd_files(source_dir: Path, filenames: list, mod_root: Path, mode: str) -> list:
    """
    Copies each named .nxd file from source_dir (FF16Tools.CLI's
    sqlite-to-nxd output folder) into the mod's FFTIVC/data/<mode>/nxd/.
    Returns the filenames actually copied (missing ones are skipped, not an
    error, so a partial/failed CLI run is still visible rather than crashing
    mid-export).
    """
    import shutil

    dest_dir = nxd_output_dir(mod_root, mode)
    copied = []
    for filename in filenames:
        src = source_dir / filename
        if src.exists():
            shutil.copy(src, dest_dir / filename)
            copied.append(filename)
    return copied


# ---------------------------------------------------------------------------
# Recovering replaced textures and sounds from an existing mod
# ---------------------------------------------------------------------------
# Textures and sounds are shipped as finished game-format files at the same
# relative path they occupy in the unpacked game (see data_output_dir), so
# finding them again is a walk of FFTIVC/data/<mode>/ - no conversion or
# diffing needed, the presence of the file *is* the edit.
#
# What can and can't be reconstructed differs between the two, and the
# difference matters:
#
#   - A texture is a single file, so the mod's copy is a complete,
#     usable replacement. It's re-staged as "already in final form" so
#     re-exporting copies it straight through rather than decoding and
#     re-encoding it every time, which would slowly degrade the image
#     across open/export cycles.
#
#   - A .sab is an *archive* of several tracks. The mod's copy is the
#     repacked archive, so which track was replaced, what .wav it came
#     from, and any loop points are not in there in any recoverable form.
#     It's therefore recovered as a whole-file replacement that gets copied
#     through untouched, and the Sounds tab says so rather than pretending
#     the individual tracks are editable.
# ---------------------------------------------------------------------------

TEXTURE_EXTENSIONS = (".tga", ".tex")
SOUND_EXTENSIONS = (".sab",)


@dataclass
class RecoveredFiles:
    """Replaced game files found in a mod, keyed by unpacked-game relative path."""
    textures: dict = field(default_factory=dict)   # rel -> Path inside the mod
    sounds: dict = field(default_factory=dict)     # rel -> Path inside the mod
    other: dict = field(default_factory=dict)      # anything else, reported but not claimed
    game_mode: Optional[str] = None

    def is_empty(self) -> bool:
        return not (self.textures or self.sounds or self.other)

    def summary(self) -> str:
        parts = []
        if self.textures:
            parts.append(f"{len(self.textures)} texture(s)")
        if self.sounds:
            parts.append(f"{len(self.sounds)} sound file(s)")
        if self.other:
            parts.append(f"{len(self.other)} other file(s)")
        return ", ".join(parts)


def recover_replaced_files(mod_root: Path) -> RecoveredFiles:
    """
    Walks a mod's FFTIVC/data/<mode>/ and reports every replaced game file.

    `nxd/` is *mostly* skipped, because the tables this tool models are
    recovered by diffing (nxd_data.recover_edits_from_sqlite) and then
    regenerated on export - carrying the originals through as well would
    have two sources fighting over the same output file.

    The exception is any `.nxd` this tool has no tab for - `ui.*.nxd`,
    `uibuttonguide.nxd` and the like. Those were previously skipped along
    with the rest of the folder, which meant a mod's copies were invisible
    to the editor and silently dropped whenever a mod was regenerated
    anywhere other than in place. They're carried through with everything
    else now, so a mod keeps what it shipped, and the Game Updates page can
    offer to drop one when it turns out to be nothing but a stale copy of
    the game's own table.

    Files that are neither textures nor sounds are reported under `other`
    rather than silently ignored - the mod loader supports replacing any
    game file, and this tool shouldn't imply a mod contains less than it
    does just because it has no tab for that file type.
    """
    result = RecoveredFiles()
    data_root = mod_root / "FFTIVC" / "data"
    if not data_root.is_dir():
        return result

    for mode in c.GAME_MODES:
        mode_root = data_root / mode
        if not mode_root.is_dir():
            continue
        result.game_mode = result.game_mode or mode
        for path in sorted(mode_root.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(mode_root).as_posix()
            if relative.startswith("nxd/"):
                if path.name.lower() in c.NXD_EDITABLE_FILENAMES:
                    continue          # regenerated on export; see the docstring
                if path.suffix.lower() != ".nxd":
                    continue          # e.g. a stray converted .sqlite
                result.other[relative] = path
                continue
            suffix = path.suffix.lower()
            if suffix in TEXTURE_EXTENSIONS:
                result.textures[relative] = path
            elif suffix in SOUND_EXTENSIONS:
                result.sounds[relative] = path
            else:
                result.other[relative] = path
        break  # first mode present wins, same rule as the XML tables

    return result
