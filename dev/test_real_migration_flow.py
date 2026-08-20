"""The exact flow Zodi described: real mod, real clean unpacks, real update.

Driven inside a real mainloop, because the page hands worker-thread results
back with `after` and that only works when one is running.
"""
import json, shutil, sys, tempfile, time
from pathlib import Path
# The project root, one level up now these live in dev/.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
TMP = Path(tempfile.mkdtemp(prefix="realflow_"))
from fft_job_editor import paths
paths.local_data_dir = lambda: TMP
from fft_job_editor import migration, modconfig, ui_settings
from fft_job_editor import version_archive as va
va.paths.local_data_dir = lambda: TMP
from fft_job_editor.gui import step_game_updates as sgu
sgu.paths.local_data_dir = lambda: TMP
va.converter_fingerprint = lambda p: "demo"
sgu.version_archive.converter_fingerprint = lambda p: "demo"
from fft_job_editor.gui import app as app_mod

R2 = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / "refs2"
V140 = R2 / "Version 1.4.0 nxd files to sqlite/fft_data.sqlite"
V152 = R2 / "Version 1.5.2 nxd files to sqlite/fft_data.sqlite"
V151 = Path(str(R2.parent) + "/refs/Version 1.5.1 nxd files to sqlite/fft_data.sqlite")
MOD = R2 / "fftivc.gameplay.darkknightexpansion"
MOD_NXD = MOD / "FFTIVC/data/enhanced/nxd"
MOD_DB = MOD_NXD / "fft_data.sqlite"

passed = failed = 0
def check(label, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1; print(f"  PASS  {label}")
    else:
        failed += 1; print(f"  FAIL  {label}  ({detail})")

for ver, db in (("v1.4.0", V140), ("v1.5.1", V151), ("v1.5.2", V152)):
    va.archive_unpacked_nxd(MOD_NXD, ver, clean_unpack=True, sqlite_path=db, converter="demo")
    time.sleep(0.02)

w = app_mod.WizardApp()
page = w.step_frames[3]
s = w.state_data
s.nxd_sqlite_path = V152
s.loaded_mod_root = MOD
s.loaded_mod_config = json.loads((MOD / "ModConfig.json").read_text(encoding="utf-8-sig"))
s.mod_sqlite_path = MOD_DB
s.other_file_replacements = dict(modconfig.recover_replaced_files(MOD).other)

import tkinter.messagebox as mb
mb.showinfo = lambda *a, **k: None


def run_all():
    page.on_show()
    print(f"\n  [status]  {page.baseline_var.get()}")
    print(f"  [verdict] {page.verdict_var.get()}\n")
    check("installed game reads as v1.5.2", page.installed_var.get() == "v1.5.2")
    check("baseline resolves to v1.5.1 (the mod's own ui.en.nxd)",
          page._baseline.chosen.version == "v1.5.1", page._baseline.chosen.version)
    scores = {c.version: c.score for c in page._baseline.candidates}
    print(f"  [scores]  {scores}\n")
    check("v1.4.0 ruled out on content, not on the hint",
          scores["v1.4.0"] > scores["v1.5.1"], scores)
    check("the mod is reported as stale against v1.5.2",
          "would undo whatever the update changed" in page.verdict_var.get())

    print("  [debug] baseline:", page._baseline.chosen.version, page._baseline.chosen.sqlite_path)
    print("  [debug] mod db:  ", page._mod_sqlite())
    print("  [debug] current: ", s.nxd_sqlite_path)
    page._start_review()
    while page._busy:
        w.update(); time.sleep(0.02)
    check("review completed", page._plan is not None)
    plan = page._plan
    print(f"\n  [summary] {page.review_summary_var.get()}\n")
    check("the mod's ability edits were found",
          any(ch.section == "Abilities" for ch in plan.changes))
    check("its item edit was found", any(ch.section == "Items" for ch in plan.changes))
    check("all ten rekeys carried", len(plan.rekeys) == 10, len(plan.rekeys))
    check("no conflicts - 1.5.1 to 1.5.2 changed nothing this mod touches",
          plan.conflicts() == [], [(c.table, c.key, c.field_name) for c in plan.conflicts()])
    check("nothing orphaned", plan.by_outcome(migration.ORPHANED) == [])
    check("all nine unmodelled files assessed", len(plan.unmodelled) == 9, len(plan.unmodelled))
    for u in sorted(plan.unmodelled, key=lambda x: x.filename):
        print(f"      {u.filename:22s} +{u.additions:4d} added  {u.losses:4d} lost  "
              f"{u.stale:4d} stale  {u.rows_missing:3d} rows missing  -> {u.recommendation}")

    page._apply_plan()
    check("edits landed in the editor state", bool(s.ability_edits.get("en")))
    check("rekeys landed", len(s.entry_rekeys) == 10)
    check("target version recorded as v1.5.2",
          getattr(s, "built_against_game_version", "") == "v1.5.2")

    page.compare_from.set("v1.4.0"); page.compare_to.set("v1.5.2")
    page._start_compare()
    while page._busy:
        w.update(); time.sleep(0.02)
    print(f"\n  [compare] {page.compare_summary_var.get()}\n")
    check("compare found the real 50-table difference",
          "50 table(s) differ" in page.compare_summary_var.get(),
          page.compare_summary_var.get())
    check("no truncation language in the summary",
          "more row(s)" not in page.compare_summary_var.get())
    boxes = page.compare_body.winfo_children()
    check("one panel per differing table", len(boxes) == 50, len(boxes))

    page._show_full_rows.set(True)
    page._on_full_rows_toggled()
    w.update()
    check("whole-row view re-renders", len(page.compare_body.winfo_children()) == 50)
    check("the preference is persisted", ui_settings.load()["compare_show_full_rows"])
    w.quit()


w.after(50, run_all)
w.mainloop()
w.destroy()
shutil.rmtree(TMP, ignore_errors=True)
print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
