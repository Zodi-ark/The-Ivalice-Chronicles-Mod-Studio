"""Unpacking converts every .nxd the game ships, not just the ones with tabs.

The narrow set produced a family of "this table isn't available" behaviours
that read as bugs: a mod's file reported as unchanged because it couldn't be
examined, merging limited to an arbitrary-looking list, and Compare Versions
seeing a fraction of what changed. This asserts the breadth that removes
them, and the costs that make it affordable.
"""
import sqlite3, sys, tempfile, time
from pathlib import Path

# The project root, one level up now these live in dev/.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from fft_job_editor import constants as c, migration, nxd_data

R2 = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / "refs2"
V140 = R2 / "Version 1.4.0 nxd files to sqlite/fft_data.sqlite"
V152 = R2 / "Version 1.5.2 nxd files to sqlite/fft_data.sqlite"
MOD_NXD = R2 / "fftivc.gameplay.darkknightexpansion/FFTIVC/data/enhanced/nxd"
TMP = Path(tempfile.mkdtemp(prefix="fullconv_"))

passed = failed = 0
def check(label, cond, detail=""):
    global passed, failed
    if cond: passed += 1; print(f"  PASS  {label}")
    else: failed += 1; print(f"  FAIL  {label}  ({detail})")

# --- Staging takes everything present -------------------------------------
source = TMP / "source_nxd"
source.mkdir(parents=True)
for name in list(c.NXD_ALL_STAGED_FILENAMES) + ["uibuttonguide.nxd", "uiannounce.nxd",
                                                "somethingunknown.nxd"]:
    (source / name).write_bytes(b"NXD\x00")

everything = nxd_data.prepare_staging_folder(source, TMP / "wide", include_all=True)
check("include_all stages every .nxd present, known or not",
      len(everything) == len(set(everything)) == 40, len(everything))
check("including files with no editing tab",
      {"uibuttonguide.nxd", "uiannounce.nxd"} <= set(everything))
check("and files this tool has never heard of",
      "somethingunknown.nxd" in everything)

narrow = nxd_data.prepare_staging_folder(source, TMP / "narrow")
check("without it, only the known list is staged", len(narrow) == 37, len(narrow))
check("which is what the game unpack used to do",
      "uibuttonguide.nxd" not in narrow)

# Non-.nxd must never be swept up.
(source / "notes.txt").write_bytes(b"not game data")
again = nxd_data.prepare_staging_folder(source, TMP / "wide2", include_all=True)
check("non-.nxd files are left alone", "notes.txt" not in again)

# --- What the breadth buys, on real data ----------------------------------
def staged_table_names():
    names = set()
    for filename in c.NXD_ALL_STAGED_FILENAMES:
        stem = filename[:-4].split(".")
        names.add((stem[0] + "-" + stem[1]) if len(stem) == 2 else stem[0])
    return names

con = sqlite3.connect(V152)
real = {r[0].lower(): r[0] for r in
        con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
con.close()
narrow_tables = {real[t.lower()] for t in staged_table_names() if t.lower() in real}

full = migration.compare_databases(V140, V152)
visible_before = {name for name in full if name in narrow_tables}
check("the full comparison sees far more than the old staged set",
      len(full) > len(visible_before) * 5, (len(full), len(visible_before)))
check("and the old set really was a small fraction of it",
      len(visible_before) <= 6, sorted(visible_before))

# FF16Tools metadata must not show up as a game change.
check("the converter's own bookkeeping table is not reported as a difference",
      "_uniontypes" not in full)

# --- The costs that make it affordable ------------------------------------
narrow_db = TMP / "narrow.sqlite"
src = sqlite3.connect(V152)
src.execute("ATTACH DATABASE ? AS out", (str(narrow_db),))
for table in sorted(narrow_tables):
    src.execute(f'CREATE TABLE out."{table}" AS SELECT * FROM "{table}"')
src.commit(); src.close()

def load_time(db):
    start = time.time()
    for _ in range(5):
        nxd_data.read_ability_table(db, "en")
        nxd_data.read_item_table(db, "en")
        nxd_data.read_override_entry_table(db)
    return time.time() - start

slim, wide = load_time(narrow_db), load_time(V152)
print(f"        (tab loads: narrow {slim:.2f}s, wide {wide:.2f}s; "
      f"size {narrow_db.stat().st_size/1e6:.1f} MB vs {V152.stat().st_size/1e6:.1f} MB)")
check("reading from the wide database is not meaningfully slower",
      wide < slim + 0.5, (slim, wide))
check("and it stays well under a hundred megabytes",
      V152.stat().st_size < 100_000_000)

# --- The fallback still works, for tables that never convert ---------------
check("two real game files produce no table at all, so the fallback has a job",
      nxd_data.tables_missing_from(V152, ["ConfigItemClassicTextLanguage",
                                          "ConfigItemDifficultyLevel"])
      == ["ConfigItemClassicTextLanguage", "ConfigItemDifficultyLevel"])
target = TMP / "topup.sqlite"
sqlite3.connect(target).close()
check("a missing table can still be imported from the game's database",
      nxd_data.import_tables_from(target, V152, ["UIButtonGuide"]) == ["UIButtonGuide"])

# --- Every merged table must map back to a real filename ------------------
#
# Export used to look this up in NXD_ALL_STAGED_FILENAMES, a list of 37, so
# a merged table outside it was converted by FF16Tools and then never
# copied. uibuttonguide.nxd and uiannounce.nxd vanished from an export that
# had just reported them merged - and they were only the two anyone tried.
game_nxd = TMP / "game_nxd_all"
game_nxd.mkdir(parents=True, exist_ok=True)
con = sqlite3.connect(V152)
real_tables = [r[0] for r in con.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name != '_uniontypes'")]
con.close()
for name in ("ui.en.nxd", "uiannounce.nxd", "uibuttonguide.nxd",
             "charaname.en.nxd", "guide.en.nxd", "abilityreactionvoicetype.nxd"):
    (game_nxd / name).write_bytes(b"NXD\x00")

for table, expected in (
    ("UI-en", "ui.en.nxd"),
    ("UIAnnounce", "uiannounce.nxd"),
    ("UIButtonGuide", "uibuttonguide.nxd"),
    ("CharaName-en", "charaname.en.nxd"),
    ("Guide-en", "guide.en.nxd"),
    ("AbilityReactionVoiceType", "abilityreactionvoicetype.nxd"),
):
    check(f"{table} maps to {expected}",
          migration.nxd_filename_for_table(game_nxd, table) == expected,
          migration.nxd_filename_for_table(game_nxd, table))

check("a table the game has no file for maps to nothing, rather than a guess",
      migration.nxd_filename_for_table(game_nxd, "InventedTable") is None)
check("no game folder is handled without raising",
      migration.nxd_filename_for_table(None, "UI-en") is None)

# The two that went missing were outside the old 37-name list, and so were
# the great majority of tables.
old_list = {n.lower() for n in c.NXD_ALL_STAGED_FILENAMES}
outside = [t for t in real_tables
           if (t.replace("-", ".").lower() + ".nxd") not in old_list]
check("the old lookup covered only a small fraction of the tables",
      len(outside) > len(real_tables) * 0.9, (len(outside), len(real_tables)))
check("including uibuttonguide and uiannounce",
      "UIButtonGuide" in outside and "UIAnnounce" in outside)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
