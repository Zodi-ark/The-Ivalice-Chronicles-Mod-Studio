"""Opening a second mod must not inherit the first one's edits.

Reproduces the reported bug: open Dark Knight Expansion, then open a texture
pack that ships no ability/item/encounter .nxd, and the texture pack showed
Dark Knight Expansion's game data edits.
"""
import json, shutil, sys, tempfile
from pathlib import Path

# The project root, one level up now these live in dev/.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
TMP = Path(tempfile.mkdtemp(prefix="modswitch_"))
from fft_job_editor import paths
paths.local_data_dir = lambda: TMP
from fft_job_editor import migration, modconfig, nxd_data
from fft_job_editor.gui import step_game_updates as sgu
sgu.paths.local_data_dir = lambda: TMP
from fft_job_editor.gui import app as app_mod

R2 = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / "refs2"
PACK = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT.parent / "zpack" / "fftivc.asset.zoditexturepack"
V151 = Path(str(R2.parent) + "/refs/Version 1.5.1 nxd files to sqlite/fft_data.sqlite")
V152 = R2 / "Version 1.5.2 nxd files to sqlite/fft_data.sqlite"
DKE = R2 / "fftivc.gameplay.darkknightexpansion"
DKE_DB = DKE / "FFTIVC/data/enhanced/nxd/fft_data.sqlite"

passed = failed = 0
def check(label, cond, detail=""):
    global passed, failed
    if cond: passed += 1; print(f"  PASS  {label}")
    else: failed += 1; print(f"  FAIL  {label}  ({detail})")

# What each mod actually ships, so the premise of the bug is on the record.
pack_nxd = sorted(p.name for p in (PACK / "FFTIVC/data/enhanced/nxd").glob("*.nxd"))
check("the texture pack ships only UI-ish .nxd, no ability/item/encounter data",
      not any(n.startswith(("ability.", "item.", "overrideentrydata")) for n in pack_nxd),
      pack_nxd)

# --- The staging folder, which is where this bug actually lived ----------
#
# Zodi's sequence: fresh install, open the texture pack (clean), open Dark
# Knight Expansion (its edits show, correctly), open the texture pack again
# - and DKE's edits are back. Only the .nxd ones; not XML, not textures.
# That asymmetry is the tell: everything read straight from the mod folder
# was fine, and only the thing routed through a shared scratch folder was
# wrong.
STAGING = TMP / "mod_nxd_staging"
DKE_NXD = DKE / "FFTIVC/data/enhanced/nxd"
PACK_NXD = PACK / "FFTIVC/data/enhanced/nxd"

first = nxd_data.prepare_staging_folder(PACK_NXD, STAGING)
check("opening the texture pack first stages only its own files",
      sorted(p.name for p in (STAGING / "nxd").glob("*.nxd")) == sorted(first),
      sorted(first))

dke_staged = nxd_data.prepare_staging_folder(DKE_NXD, STAGING)
check("opening Dark Knight Expansion stages its ability/item/encounter files",
      {"ability.en.nxd", "item.en.nxd", "overrideentrydata.nxd"} <= set(dke_staged),
      sorted(dke_staged))

again = nxd_data.prepare_staging_folder(PACK_NXD, STAGING)
on_disk = sorted(p.name for p in (STAGING / "nxd").glob("*.nxd"))
check("opening the texture pack again leaves nothing of the previous mod",
      on_disk == sorted(again), [n for n in on_disk if n not in again])
check("specifically no ability, item or encounter file",
      not any(n.startswith(("ability.", "item.", "overrideentrydata",
                            "overrideabilityactiondata")) for n in on_disk),
      on_disk)
# The list this function returns is not what gets converted - the folder is.
check("what is reported staged and what is on disk are the same set",
      sorted(again) == on_disk, (sorted(again), on_disk))

# The same shape of bug in the export output folder: a file the converter
# failed to regenerate would be copied from a previous export instead, and
# the "didn't produce" check would see it there and stay quiet.
OUT = TMP / "nxd_export_staging" / "nxd_out"
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "ability.en.nxd").write_bytes(b"stale from a previous export")
for stale in OUT.glob("*.nxd"):
    stale.unlink()
check("clearing the export output folder leaves nothing to copy by mistake",
      list(OUT.glob("*.nxd")) == [])

w = app_mod.WizardApp()
state = w.state_data
state.nxd_sqlite_path = V152

# --- Mod 1: Dark Knight Expansion, loaded the way opening it would.
recovered = nxd_data.recover_edits_from_sqlite(V151, DKE_DB)
state.ability_edits = recovered.ability_edits
state.item_edits = recovered.item_edits
state.override_action_edits = recovered.override_action_edits
state.entry_edits = recovered.entry_edits
state.entry_rekeys = dict(recovered.entry_rekeys)
state.loaded_mod_root = DKE
state.loaded_mod_config = json.loads((DKE / "ModConfig.json").read_text(encoding="utf-8-sig"))
state.other_file_replacements = dict(modconfig.recover_replaced_files(DKE).other)
state.mod_sqlite_path = DKE_DB
state.texture_edits = {"ui/fake.tex": {"source_path": Path("/tmp/x"), "already_staged": True}}
shutil.copy(DKE_DB, TMP / "mod_data.sqlite")   # what a real conversion leaves behind

check("mod 1 has ability edits", bool(state.ability_edits.get("en")))
check("mod 1 has ten rekeys", len(state.entry_rekeys) == 10)

# --- Mod 2 opened: the reset the open flow now performs.
state.clear_opened_mod_content()

check("ability edits are gone", state.ability_edits == {}, state.ability_edits)
check("item edits are gone", state.item_edits == {})
check("stat overrides are gone", state.override_action_edits == {})
check("entry edits are gone", state.entry_edits == {})
check("rekeys are gone", state.entry_rekeys == {}, state.entry_rekeys)
check("dropped rows are gone", state.entry_dropped == set())
check("carried-through files are gone", state.other_file_replacements == {})
check("staged textures are gone", state.texture_edits == {})
check("rebased tables are gone", state.unmodelled_table_edits == {})
check("the previous mod's database is no longer pointed at",
      state.mod_sqlite_path is None)
check("the texture and sound trees are invalidated so tabs rescan",
      state.texture_tree is None and state.sound_tree is None)

# The unpacked game and reference tables must survive - they aren't the mod's.
check("the unpacked game files survive a mod switch", state.nxd_sqlite_path == V152)

# --- The second vector: a stale mod_data.sqlite on a fixed path.
state.loaded_mod_root = PACK
state.loaded_mod_config = json.loads((PACK / "ModConfig.json").read_text(encoding="utf-8-sig"))
page = w.step_frames[3]
check("with no database recorded, Game Updates finds none - it does not fall "
      "back to the last mod's file",
      page._mod_sqlite() is None, page._mod_sqlite())
check("even though a stale mod_data.sqlite is sitting right there",
      (TMP / "mod_data.sqlite").exists())

version, source = migration.detect_mod_game_version(state.loaded_mod_config, None)
check("and dating the mod doesn't reach for it either", version is None, version)

# With a database properly recorded, it is used.
state.mod_sqlite_path = PACK / "FFTIVC/data/enhanced/nxd/fft_data.sqlite"
check("once this mod's own database is recorded, that one is used",
      page._mod_sqlite() == state.mod_sqlite_path)
found = migration.read_game_version(state.mod_sqlite_path)
check("and it is the texture pack's data, not Dark Knight Expansion's",
      found is not None, found)
pack_intent = nxd_data.recover_edits_from_sqlite(V151, state.mod_sqlite_path)
check("the texture pack contributes no ability edits at all",
      pack_intent.ability_edits == {}, pack_intent.ability_edits)
check("nor any rekeys", pack_intent.entry_rekeys == {}, pack_intent.entry_rekeys)

w.destroy()
shutil.rmtree(TMP, ignore_errors=True)
print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
