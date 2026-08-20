"""
Version archive tests.

Uses the real converted databases where a version string is needed, and
synthetic .nxd folders for the archive mechanics themselves - the archive
only ever handles opaque bytes, so real .nxd content proves nothing extra
about zipping, naming or pruning that a fixture doesn't.

Usage:  python3 test_version_archive.py [path-to-References-folder]
"""
import json
import shutil
import sqlite3
import sys
import tempfile
import time
import zipfile
from pathlib import Path

# The project root, one level up now these live in dev/.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fft_job_editor import constants as c
from fft_job_editor import migration
from fft_job_editor import nxd_data
from fft_job_editor import version_archive as va

REFS = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / "refs"
V151 = REFS / "Version 1.5.1 nxd files to sqlite" / "fft_data.sqlite"
V152 = REFS / "Version 1.5.2 nxd files to sqlite" / "fft_data.sqlite"
MOD_NXD = (REFS / "Stale Mod" / "fftivc.gameplay.darkknightexpansion"
           / "FFTIVC" / "data" / "enhanced" / "nxd")

passed = failed = 0
TMP = Path(tempfile.mkdtemp(prefix="archive_tests_"))


def check(label, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed += 1
        print(f"  FAIL  {label}" + (f"  ({detail})" if detail else ""))


def section(title):
    print(f"\n--- {title} ---")


def fake_nxd_dir(name, filenames):
    d = TMP / name
    d.mkdir(parents=True, exist_ok=True)
    for i, filename in enumerate(filenames):
        (d / filename).write_bytes(b"NXD\x00" + bytes([i]) * 4096)
    return d


# ---------------------------------------------------------------------------
section("The staging gap this session found")
# ---------------------------------------------------------------------------
# read_game_version only works if the UI tables actually reach the converted
# database. They didn't - prepare_staging_folder staged 30 files and none of
# them were ui.*.nxd, so every real unpack produced a database with no
# version string in it. The earlier tests passed only because the reference
# databases are full hand-made 563-table conversions.
check("ui.*.nxd are staged for conversion",
      all(f in c.NXD_ALL_STAGED_FILENAMES for f in c.NXD_ALL_UI_FILENAMES),
      c.NXD_ALL_UI_FILENAMES)
check("the staged list now covers 37 files", len(c.NXD_ALL_STAGED_FILENAMES) == 37,
      len(c.NXD_ALL_STAGED_FILENAMES))
check("and has no duplicates",
      len(set(c.NXD_ALL_STAGED_FILENAMES)) == len(c.NXD_ALL_STAGED_FILENAMES))

source = fake_nxd_dir("staging_source", c.NXD_ALL_STAGED_FILENAMES + ["uibuttonguide.nxd"])
found = nxd_data.prepare_staging_folder(source, TMP / "staging_out")
check("prepare_staging_folder picks up every staged file", len(found) == 37, len(found))
check("including the UI tables", "ui.en.nxd" in found)
check("and still ignores files with no tab and no purpose",
      "uibuttonguide.nxd" not in found)

# A real mod's nxd folder: only some files present, must not error.
partial = nxd_data.prepare_staging_folder(MOD_NXD, TMP / "staging_mod")
check("a real mod's partial nxd folder stages what it has",
      set(partial) >= set(c.NXD_ALL_UI_FILENAMES), sorted(partial))
check("so an opened mod's database will carry its version string",
      "ability.en.nxd" in partial and "ui.en.nxd" in partial)

# ---------------------------------------------------------------------------
section("Archiving")
# ---------------------------------------------------------------------------
root = TMP / "archive"
game_nxd = fake_nxd_dir("game_1_5_2", ["ability.en.nxd", "item.en.nxd", "ui.en.nxd"])

entry = va.archive_unpacked_nxd(game_nxd, "v1.5.2", source="test", clean_unpack=True, root=root)
check("archiving returns an entry", entry is not None)
check("named after the version", entry.directory.name == "v1.5.2", entry.directory.name)
check("holding a zip", entry.nxd_zip.exists())
check("with every file in it", entry.file_count == 3, entry.file_count)
check("and a manifest beside it", (entry.directory / va.MANIFEST_NAME).exists())
check("clean_unpack is recorded", entry.clean_unpack is True)
check("the archive is much smaller than the source",
      entry.size_bytes < sum(p.stat().st_size for p in game_nxd.glob("*.nxd")),
      entry.size_bytes)

with zipfile.ZipFile(entry.nxd_zip) as zf:
    names = sorted(zf.namelist())
check("the zip stores bare filenames, no paths", names == ["ability.en.nxd", "item.en.nxd", "ui.en.nxd"],
      names)

again = va.archive_unpacked_nxd(game_nxd, "v1.5.2", root=root)
check("re-archiving the same version is a no-op, not an error", again is not None)
check("and doesn't duplicate the folder", len(list((root).iterdir())) == 1)

check("an empty nxd folder archives nothing",
      va.archive_unpacked_nxd(fake_nxd_dir("empty", []), "v9.9.9", root=root) is None)
check("a missing folder archives nothing",
      va.archive_unpacked_nxd(TMP / "nope", "v9.9.9", root=root) is None)

# Unknown version: still archived, flagged, never refused.
unknown = va.archive_unpacked_nxd(fake_nxd_dir("game_unknown", ["ability.en.nxd"]),
                                  None, root=root)
check("an unreadable version still gets archived", unknown is not None)
check("flagged as unknown", unknown.version_unknown)
check("under a dated folder name", unknown.directory.name.startswith("unknown-"),
      unknown.directory.name)

# A version string containing a path separator must not escape the archive.
nasty = va.archive_unpacked_nxd(fake_nxd_dir("game_nasty", ["ability.en.nxd"]),
                                "../../escaped", root=root)
check("a version string can't write outside the archive folder",
      nasty is not None and nasty.directory.parent == root, nasty and nasty.directory)
check("and is sanitised into a plain name",
      nasty is not None and "/" not in nasty.directory.name and ".." not in nasty.directory.name,
      nasty and nasty.directory.name)

# ---------------------------------------------------------------------------
section("Listing, finding and extracting")
# ---------------------------------------------------------------------------
va.archive_unpacked_nxd(fake_nxd_dir("game_1_5_1", ["ability.en.nxd", "ui.en.nxd"]),
                        "v1.5.1", root=root)
listed = va.list_archived(root)
check("every archive is listed", len(listed) == 4, [e.version for e in listed])
check("newest first",
      [e.archived_at for e in listed] == sorted([e.archived_at for e in listed], reverse=True))

found_entry = va.find_archived("v1.5.1", root)
check("an archive can be found by version", found_entry is not None)
check("and matches on the raw version string too",
      va.find_archived("v1.5.2", root) is not None)
check("a version not held returns None", va.find_archived("v0.0.1", root) is None)
check("an empty version returns None", va.find_archived("", root) is None)

out = va.extract_archived(found_entry, TMP / "restored")
restored = sorted(p.name for p in out.glob("*.nxd"))
check("extracting restores the files", restored == ["ability.en.nxd", "ui.en.nxd"], restored)
check("byte-for-byte",
      (out / "ability.en.nxd").read_bytes()
      == (TMP / "game_1_5_1" / "ability.en.nxd").read_bytes())

# A zip with a traversal path must not escape the destination.
evil = root / "v-evil"
evil.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(evil / va.NXD_ZIP_NAME, "w") as zf:
    zf.writestr("../../escaped.nxd", b"nope")
    zf.writestr("good.nxd", b"yes")
evil_entry = va._read_manifest(evil)
dest = TMP / "restored_evil"
va.extract_archived(evil_entry, dest)
check("extraction strips traversal paths",
      not (TMP / "escaped.nxd").exists() and not (dest.parent.parent / "escaped.nxd").exists())
check("keeping only the bare filename",
      sorted(p.name for p in dest.glob("*.nxd")) == ["escaped.nxd", "good.nxd"],
      sorted(p.name for p in dest.glob("*.nxd")))
shutil.rmtree(evil)

# ---------------------------------------------------------------------------
section("Round trip against a real converted database")
# ---------------------------------------------------------------------------
# The version an archive is named after must be the one migration reads back.
check("migration reads v1.5.1 from the real database",
      migration.read_game_version(V151) == "v1.5.1")
real_entry = va.archive_unpacked_nxd(MOD_NXD, migration.read_game_version(V151),
                                     source="real mod folder", root=root)
check("a real nxd folder archives under that version",
      real_entry is not None and real_entry.directory.name == "v1.5.1",
      real_entry and real_entry.directory.name)
check("it did not overwrite the earlier v1.5.1 archive (same version, no-op)",
      real_entry.file_count == 2, real_entry.file_count)

# ---------------------------------------------------------------------------
section("The converted-database cache")
# ---------------------------------------------------------------------------
cache_root = TMP / "cache_archive"
fake_db = TMP / "working.sqlite"
con = sqlite3.connect(fake_db)
con.execute("CREATE TABLE \"Ability-en\" (Key INTEGER, Name TEXT)")
con.execute('INSERT INTO "Ability-en" VALUES (1, "Cure")')
con.commit()
con.close()

fake_cli = TMP / "FF16Tools.CLI.exe"
fake_cli.write_bytes(b"pretend binary v1")
fp1 = va.converter_fingerprint(fake_cli)
check("a converter fingerprint is produced", len(fp1) == 16, fp1)
check("and is stable across calls", va.converter_fingerprint(fake_cli) == fp1)
fake_cli.write_bytes(b"pretend binary v2 - a different build")
fp2 = va.converter_fingerprint(fake_cli)
check("a different binary fingerprints differently", fp1 != fp2)
check("no converter gives an empty fingerprint", va.converter_fingerprint(None) == "")
check("a missing file gives an empty fingerprint",
      va.converter_fingerprint(TMP / "gone.exe") == "")

cached_entry = va.archive_unpacked_nxd(
    fake_nxd_dir("g_cache", ["ability.en.nxd", "ui.en.nxd"]), "v1.6.0",
    root=cache_root, sqlite_path=fake_db, converter=fp2,
)
check("the archive holds both zips",
      cached_entry.nxd_zip.exists() and cached_entry.data_zip.exists())
# The relative cost of the cache is the whole basis for keeping both, so
# it's measured against real game data rather than fixtures - synthetic
# .nxd bytes compress to almost nothing and would prove the opposite.
real_working = TMP / "real_working.sqlite"
_src = sqlite3.connect(V152)
_staged = set()
for _f in c.NXD_ALL_STAGED_FILENAMES:
    _stem = _f[:-4].split(".")
    _staged.add((_stem[0] + "-" + _stem[1]) if len(_stem) == 2 else _stem[0])
_real_names = {r[0].lower(): r[0] for r in
               _src.execute("SELECT name FROM sqlite_master WHERE type='table'")}
_src.execute("ATTACH DATABASE ? AS out", (str(real_working),))
for _tab in sorted(_staged):
    if _tab.lower() in _real_names:
        _actual = _real_names[_tab.lower()]
        _src.execute(f'CREATE TABLE out."{_actual}" AS SELECT * FROM "{_actual}"')
_src.commit()
_src.close()

real_entry = va.archive_unpacked_nxd(
    MOD_NXD, "v-sizecheck", root=TMP / "size_archive",
    sqlite_path=real_working, converter="sizecheck",
)
_nxd_mb = real_entry.nxd_zip.stat().st_size / 1e6
_db_mb = real_entry.data_zip.stat().st_size / 1e6
print(f"        (real data: 13-file mod nxd.zip {_nxd_mb:.2f} MB, "
      f"37-table working data.zip {_db_mb:.2f} MB)")
# NOT asserting an ordering between those two - they aren't comparable. The
# mod ships 13 .nxd files; a real game unpack has 564. The claim that
# actually justifies keeping the cache is that it is small in absolute
# terms, which is measurable here; the size of a full .nxd archive is an
# extrapolation and doesn't belong in an assertion.
check("the cached working database is under 1 MB zipped - cheap enough to keep",
      _db_mb < 1.0, f"{_db_mb:.2f} MB")
check("and is a real, complete copy of the 37 staged tables",
      len([r for r in sqlite3.connect(real_working).execute(
          "SELECT name FROM sqlite_master WHERE type='table'")]) == 37)
check("size counts both", cached_entry.size_bytes
      == cached_entry.nxd_zip.stat().st_size + cached_entry.data_zip.stat().st_size)
check("the converter is recorded", cached_entry.converter == fp2, cached_entry.converter)

reloaded_entry = va.find_archived("v1.6.0", cache_root)
check("the converter survives a manifest round trip", reloaded_entry.converter == fp2)
check("the cache is usable for the same converter", reloaded_entry.has_usable_cache(fp2))
check("and NOT for a different one", not reloaded_entry.has_usable_cache(fp1))
check("nor for an unknown one", not reloaded_entry.has_usable_cache(""))

opened = va.open_archived_database(reloaded_entry, TMP / "opened", fp2)
check("opening the cache returns a real database", opened is not None and opened.exists())
row = sqlite3.connect(opened).execute('SELECT Name FROM "Ability-en"').fetchone()
check("with the right contents", row and row[0] == "Cure", row)

check("a converter mismatch refuses the cache rather than trusting it",
      va.open_archived_database(reloaded_entry, TMP / "opened2", fp1) is None)
check("so does an unknown converter",
      va.open_archived_database(reloaded_entry, TMP / "opened3", "") is None)

no_cache = va.archive_unpacked_nxd(
    fake_nxd_dir("g_nocache", ["ability.en.nxd"]), "v1.7.0", root=cache_root)
check("archiving without a database still works", no_cache is not None)
check("and records no converter, so nothing trusts a cache that isn't there",
      no_cache.converter == "" and not no_cache.has_usable_cache(fp2))
check("opening a missing cache returns None",
      va.open_archived_database(no_cache, TMP / "opened4", fp2) is None)

bad_sqlite = va.archive_unpacked_nxd(
    fake_nxd_dir("g_badsql", ["ability.en.nxd"]), "v1.8.0", root=cache_root,
    sqlite_path=TMP / "does_not_exist.sqlite", converter=fp2)
check("a missing source database doesn't break archiving", bad_sqlite is not None)
check("and leaves the converter blank rather than claiming a cache",
      bad_sqlite.converter == "")
check("the nxd archive is still written", bad_sqlite.nxd_zip.exists())

check("describe() says when a version is ready to read",
      "ready to read" in reloaded_entry.describe(), reloaded_entry.describe())
check("and doesn't when it isn't",
      "ready to read" not in no_cache.describe(), no_cache.describe())

# ---------------------------------------------------------------------------
section("Pruning: what counts as still needed")
# ---------------------------------------------------------------------------
mods = TMP / "Mods"
(mods / "fftivc.gameplay.one").mkdir(parents=True, exist_ok=True)
(mods / "fftivc.gameplay.two").mkdir(parents=True, exist_ok=True)
(mods / "fftivc.gameplay.unstamped").mkdir(parents=True, exist_ok=True)

stamped = {"ModId": "fftivc.gameplay.one", "PluginData": {}}
migration.apply_stamp(stamped, migration.ModStamp(game_version="v1.4.0"))
(mods / "fftivc.gameplay.one" / "ModConfig.json").write_text(json.dumps(stamped))
stamped2 = {"ModId": "fftivc.gameplay.two", "PluginData": {}}
migration.apply_stamp(stamped2, migration.ModStamp(game_version="v1.3.0"))
(mods / "fftivc.gameplay.two" / "ModConfig.json").write_text(json.dumps(stamped2))
(mods / "fftivc.gameplay.unstamped" / "ModConfig.json").write_text(
    json.dumps({"ModId": "fftivc.gameplay.unstamped"}))
(mods / "broken").mkdir(parents=True, exist_ok=True)
(mods / "broken" / "ModConfig.json").write_text("{ not json")

in_use = va.versions_in_use(mods, installed_version="v1.5.2")
check("the installed version counts as in use", "v1.5.2" in in_use, sorted(in_use))
check("a stamped mod's version counts as in use", "v1.4.0" in in_use, sorted(in_use))
check("every stamped mod, not just the first", "v1.3.0" in in_use, sorted(in_use))
check("an unstamped mod contributes nothing", len(in_use) == 3, sorted(in_use))
check("malformed ModConfig.json is skipped, not fatal", True)
check("no Mods folder still returns the installed version",
      va.versions_in_use(None, "v1.5.2") == {"v1.5.2"})

# ---------------------------------------------------------------------------
section("Pruning: the plan")
# ---------------------------------------------------------------------------
prune_root = TMP / "prune_archive"
for i, ver in enumerate(["v1.0.0", "v1.1.0", "v1.2.0", "v1.3.0", "v1.4.0", "v1.5.0", "v1.5.2"]):
    e = va.archive_unpacked_nxd(fake_nxd_dir(f"g{i}", ["ability.en.nxd"]), ver, root=prune_root)
    # Force distinct, ordered timestamps so "newest first" is deterministic.
    e.archived_at = 1_000_000 + i * 1000
    va._write_manifest(e)

check("seven versions archived", len(va.list_archived(prune_root)) == 7)

plan = va.plan_prune({"v1.5.2", "v1.0.0"}, keep_count=3, root=prune_root)
kept_names = {e.version for e in plan.keep_in_use}
check("an in-use version is protected regardless of age", "v1.0.0" in kept_names, kept_names)
check("so is the installed one", "v1.5.2" in kept_names, kept_names)
check("three most recent of the rest are kept",
      {e.version for e in plan.keep_recent} == {"v1.5.0", "v1.4.0", "v1.3.0"},
      {e.version for e in plan.keep_recent})
check("the oldest unprotected ones are the candidates",
      {e.version for e in plan.remove} == {"v1.1.0", "v1.2.0"},
      {e.version for e in plan.remove})
check("the plan reports what it frees", "MB" in plan.summary(), plan.summary())
check("planning deletes nothing on its own", len(va.list_archived(prune_root)) == 7)

removed = va.apply_prune(plan)
check("applying removes exactly the planned versions", set(removed) == {"v1.1.0", "v1.2.0"},
      removed)
check("and leaves the rest", len(va.list_archived(prune_root)) == 5)
check("protected versions survived",
      {"v1.0.0", "v1.5.2"} <= {e.version for e in va.list_archived(prune_root)})

empty_plan = va.plan_prune({"v1.5.2"}, keep_count=va.DEFAULT_KEEP_COUNT, root=prune_root)
check("with a generous keep-count nothing is removed", empty_plan.remove == [])
check("and it says so", "Nothing to remove" in empty_plan.summary(), empty_plan.summary())

check("total size is reported", va.total_size_bytes(prune_root) > 0)

# ---------------------------------------------------------------------------
section("Robustness")
# ---------------------------------------------------------------------------
check("listing a folder that doesn't exist returns nothing",
      va.list_archived(TMP / "never_created") == [])

stray = root / "not_an_archive"
stray.mkdir(parents=True, exist_ok=True)
check("a folder with no zip is ignored rather than listed",
      all(e.directory != stray for e in va.list_archived(root)))

broken_manifest = root / "v2.0.0"
broken_manifest.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(broken_manifest / va.NXD_ZIP_NAME, "w") as zf:
    zf.writestr("ability.en.nxd", b"x")
(broken_manifest / va.MANIFEST_NAME).write_text("{ not json")
entry = va.find_archived("v2.0.0", root)
check("a corrupt manifest falls back to the folder name", entry is not None)
check("and still reports a size from the zip", entry.size_bytes > 0, entry.size_bytes)
check("describe() works on a degraded entry", isinstance(entry.describe(), str))

# ---------------------------------------------------------------------------
print(f"\n{'=' * 60}")
print(f"{passed} passed, {failed} failed")
print("=" * 60)
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if failed else 0)
