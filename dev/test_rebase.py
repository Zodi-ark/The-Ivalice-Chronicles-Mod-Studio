"""The Rebase option: the game's new table with the mod's own changes on top."""
import shutil, sqlite3, sys, tempfile
from pathlib import Path
# The project root, one level up now these live in dev/.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from fft_job_editor import constants as c, migration, nxd_data

TMP = Path(tempfile.mkdtemp(prefix="rebase_"))
passed = failed = 0
def check(label, cond, detail=""):
    global passed, failed
    if cond: passed += 1; print(f"  PASS  {label}")
    else: failed += 1; print(f"  FAIL  {label}  ({detail})")

R2 = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / "refs2"
V151 = Path(str(R2.parent) + "/refs/Version 1.5.1 nxd files to sqlite/fft_data.sqlite")
V152 = R2/"Version 1.5.2 nxd files to sqlite/fft_data.sqlite"
MOD_NXD = R2/"fftivc.gameplay.darkknightexpansion/FFTIVC/data/enhanced/nxd"
MOD_DB = MOD_NXD/"fft_data.sqlite"

# A stand-in for the game's unpacked nxd folder: whatever the game ships.
FAKE_GAME_NXD = TMP / "game_nxd"
FAKE_GAME_NXD.mkdir(parents=True, exist_ok=True)
for name in sorted(p.name for p in MOD_NXD.glob("*.nxd")):
    (FAKE_GAME_NXD / name).write_bytes(b"stand-in for the game's own file")

tables = {a.filename: a for a in migration.assess_unmodelled(
    MOD_NXD, MOD_DB, V152, baseline_sqlite=V151, game_nxd_dir=FAKE_GAME_NXD)}

ui_en = tables["ui.en.nxd"]
check("ui.en.nxd can be merged", ui_en.rebasable)
check("so can uibuttonguide.nxd, now the game's copy is fetched on demand",
      tables["uibuttonguide.nxd"].rebasable)
check("and uiannounce.nxd", tables["uiannounce.nxd"].rebasable)

# A file the game doesn't ship genuinely cannot be merged.
bare = TMP / "game_nxd_bare"
bare.mkdir(parents=True, exist_ok=True)
(bare / "ui.en.nxd").write_bytes(b"only this one")
limited = {a.filename: a for a in migration.assess_unmodelled(
    MOD_NXD, MOD_DB, V152, baseline_sqlite=V151, game_nxd_dir=bare)}
check("a mod file the game has no counterpart for can't be merged",
      not limited["uibuttonguide.nxd"].rebasable)
check("but one it does have still can", limited["ui.en.nxd"].rebasable)

# An unreadable table must never read as "no differences".
unreadable = migration.UnmodelledTable(filename="mystery.nxd", table="", readable=False)
check("an unreadable table is not called unchanged", not unreadable.readable)
check("and defaults to keeping what the author shipped",
      unreadable.recommendation == migration.KEEP_MOD)
check("the mod's own changes are isolated from staleness",
      len(ui_en.own_changes) == 5, len(ui_en.own_changes))
check("and the version string is NOT among them - that's the game's, not the mod's",
      not any(migration.VERSION_UI_KEY in (k if isinstance(k, tuple) else (k,))
              for k in ui_en.own_changes),
      list(ui_en.own_changes))

# A mod with a real addition must be recommended for rebase, not keep.
with_addition = TMP/"mod_plus.sqlite"
shutil.copy(MOD_DB, with_addition)
con = sqlite3.connect(with_addition)
con.execute('UPDATE "UI-en" SET Text=? WHERE Key=2800', ("Dark Knight",))
con.commit(); con.close()
added = migration.assess_unmodelled_table(with_addition, V152, "ui.en.nxd", "UI-en", V151)
added.rebasable = True
check("a real addition makes rebase the recommendation",
      added.recommendation == migration.REBASE, added.recommendation)
added.rebasable = False
check("but only where rebase is possible; otherwise keep",
      added.recommendation == migration.KEEP_MOD, added.recommendation)

# The heart of it: apply the mod's changes onto the NEW game's table.
staged = TMP/"staged.sqlite"
shutil.copy(V152, staged)
before = sqlite3.connect(staged).execute(
    'SELECT Text FROM "UI-en" WHERE Key=?', (migration.VERSION_UI_KEY,)).fetchone()[0]
check("the staged table starts as the game's v1.5.2", before == "v1.5.2", before)

applied = nxd_data.write_unmodelled_table_edits(staged, "UI-en", ui_en.own_changes)
check("every one of the mod's changes lands", applied == 5, applied)

con = sqlite3.connect(staged)
after_version = con.execute('SELECT Text FROM "UI-en" WHERE Key=?',
                            (migration.VERSION_UI_KEY,)).fetchone()[0]
check("the game's newer version string survives the rebase - this is the whole point",
      after_version == "v1.5.2", after_version)
for key in (2801, 2802, 2803, 2804, 2806):
    value = con.execute('SELECT Text FROM "UI-en" WHERE Key=?', (key,)).fetchone()[0]
    check(f"the mod's change at {key} was re-applied", value is None, value)
# A row the update ADDED must still be there - the mod predates it.
added_row = con.execute('SELECT Text FROM "UI-en" WHERE Key=4031').fetchone()
check("rows the update added are untouched by the rebase",
      added_row is not None and added_row[0] == "Aries", added_row)
con.close()

# Rows the update removed leave their edits nowhere to go, reported not hidden.
shrunk = TMP/"shrunk.sqlite"
shutil.copy(V152, shrunk)
con = sqlite3.connect(shrunk); con.execute('DELETE FROM "UI-en" WHERE Key=2801')
con.commit(); con.close()
applied = nxd_data.write_unmodelled_table_edits(shrunk, "UI-en", ui_en.own_changes)
check("a removed row is reported as unapplied rather than silently lost",
      applied == 4, applied)

check("no edits is a no-op", nxd_data.write_unmodelled_table_edits(staged, "UI-en", {}) == 0)
check("an unknown table is a no-op rather than an error",
      nxd_data.write_unmodelled_table_edits(staged, "NoSuchTable", {(1,): {"x": 1}}) == 0)

# The export path must be able to name the file for each rebased table.
lower = {n.lower(): n for n in c.NXD_ALL_STAGED_FILENAMES}
check("UI-en maps back to ui.en.nxd for export",
      lower.get("UI-en".replace("-", ".").lower() + ".nxd") == "ui.en.nxd")


# --- The pieces behind on-demand fetching -----------------------------------
import sqlite3 as _sq
_target = TMP / "staged_topup.sqlite"
_con = _sq.connect(_target)
_con.execute('CREATE TABLE "Ability-en" (Key INTEGER, Name TEXT)')
_con.commit(); _con.close()

missing = nxd_data.tables_missing_from(_target, ["UIButtonGuide", "Ability-en", "UIAnnounce"])
check("missing tables are identified", sorted(missing) == ["UIAnnounce", "UIButtonGuide"], missing)

imported = nxd_data.import_tables_from(_target, V152, missing)
check("they can be imported from the game's database", sorted(imported) == sorted(missing))
check("nothing is missing afterwards",
      nxd_data.tables_missing_from(_target, missing) == [])
_con = _sq.connect(_target)
check("and the imported table has the game's rows",
      _con.execute("SELECT COUNT(*) FROM UIButtonGuide").fetchone()[0] == 1152)
check("without disturbing what was already there",
      _con.execute("SELECT COUNT(*) FROM \"Ability-en\"").fetchone()[0] == 0)
_con.close()
check("importing a table the source lacks is skipped, not fatal",
      nxd_data.import_tables_from(_target, V152, ["NoSuchTable"]) == [])

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
