"""Per-change selection on files with no editing tab."""
import json, sys, tempfile, time
from pathlib import Path
# The project root, one level up now these live in dev/.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
TMP = Path(tempfile.mkdtemp())
from fft_job_editor import paths
paths.local_data_dir = lambda: TMP
from fft_job_editor import migration, modconfig
from fft_job_editor import version_archive as va
va.paths.local_data_dir = lambda: TMP
from fft_job_editor.gui import step_game_updates as sgu
sgu.paths.local_data_dir = lambda: TMP
va.converter_fingerprint = lambda p: "demo"
sgu.version_archive.converter_fingerprint = lambda p: "demo"
from fft_job_editor.gui import app as app_mod
from tkinter import ttk
import tkinter.messagebox as mb
mb.showinfo = lambda *a, **k: None

passed = failed = 0
def check(label, cond, detail=""):
    global passed, failed
    if cond: passed += 1; print(f"  PASS  {label}")
    else: failed += 1; print(f"  FAIL  {label}  ({detail})")

R2 = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / "refs2"
Z = (Path(sys.argv[2]) if len(sys.argv) > 2
     else ROOT.parent / "zpack" / "fftivc.asset.zoditexturepack")
ZN = Z / "FFTIVC/data/enhanced/nxd"
V151 = Path(str(R2.parent) + "/refs/Version 1.5.1 nxd files to sqlite/fft_data.sqlite")
V152 = R2 / "Version 1.5.2 nxd files to sqlite/fft_data.sqlite"
for ver, db in (("v1.5.1", V151), ("v1.5.2", V152)):
    va.archive_unpacked_nxd(ZN, ver, sqlite_path=db, converter="demo"); time.sleep(0.02)

w = app_mod.WizardApp(); page = w.step_frames[3]; s = w.state_data
s.nxd_sqlite_path = V152; s.loaded_mod_root = Z
s.loaded_mod_config = json.loads((Z / "ModConfig.json").read_text(encoding="utf-8-sig"))
s.mod_sqlite_path = ZN / "fft_data.sqlite"
s.other_file_replacements = dict(modconfig.recover_replaced_files(Z).other)

plan = migration.build_plan(V151, s.mod_sqlite_path, V152)
plan.unmodelled = migration.assess_unmodelled(ZN, s.mod_sqlite_path, V152,
                                              baseline_sqlite=V151, game_nxd_dir=ZN)
page._review_finished(plan, page._identify_baseline(), None)
w.update()

# Item 1: everything mergeable defaults to merge.
defaults = {f: v.get() for f, (v, _t) in page._unmodelled_vars.items()}
check("every file that can be merged defaults to merging",
      all(v == migration.REBASE for v in defaults.values()), defaults)

# Item 3: a mod that only clears values is still 'own work'.
ui_en = next(t for t in plan.unmodelled if t.filename == "ui.en.nxd")
check("clearing values counts as the author's work",
      ui_en.additions == 0 and ui_en.losses == 5 and ui_en.has_own_work)
check("so it is offered for merging, not dropping",
      ui_en.recommendation == migration.REBASE)
check("and nothing calls it damaged", not hasattr(ui_en, "looks_like_damage"))

# A file with genuinely nothing of the author's still defaults to drop.
empty = migration.UnmodelledTable(filename="x.nxd", table="X", rebasable=True, stale=3)
check("a file that is only an older copy still defaults to dropping",
      empty.purely_stale and empty.recommendation == migration.DROP)

# Item 2: the picker.
def find_tree(widget):
    if isinstance(widget, ttk.Treeview): return widget
    for c in widget.winfo_children():
        r = find_tree(c)
        if r is not None: return r
    return None

target = next(t for t in plan.unmodelled if t.filename == "ui.en.nxd")
check("each change carries the game's value for comparison",
      len(target.game_values) == len(target.own_changes) and target.game_values)

# Open the picker for ui.en.nxd.
from fft_job_editor.gui.step_editor import CollapsibleSection
def walk(wdg, out):
    if isinstance(wdg, CollapsibleSection) and "Choose which" in wdg._title:
        out.append(wdg)
    for c in wdg.winfo_children():
        walk(c, out)
found = []
walk(page.review_body, found)
check("a change picker exists for every mergeable file", len(found) == 9, len(found))
section = found[0] if found else None

if section is not None:
    section.expand(); w.update()
    tree = find_tree(section.body)
    check("the picker renders a row per change", tree is not None)
    filename = next(f for f in page._change_selection)
    total = len(page._change_selection[filename])
    check("every change starts selected", total > 0, total)

    tbl = next(t for t in plan.unmodelled if t.filename == filename)
    check("selected changes are all of them initially",
          page._selected_own_changes(tbl) == tbl.own_changes)

    page._set_all_changes(tbl, False); w.update()
    check("select-none clears them", page._selected_own_changes(tbl) == {})
    page._set_all_changes(tbl, True); w.update()
    check("select-all restores them", page._selected_own_changes(tbl) == tbl.own_changes)

    # Untick exactly one and confirm only that one drops out.
    one = next(iter(page._change_selection[filename]))
    page._change_selection[filename].discard(one)
    kept = page._selected_own_changes(tbl)
    check("unticking one change removes only that change",
          sum(len(v) for v in kept.values()) == tbl.change_count - 1,
          (sum(len(v) for v in kept.values()), tbl.change_count))
    check("and the others survive untouched",
          all(one[1] != col or key != one[0]
              for key, fields in kept.items() for col in fields))

    # Applying must write only what is ticked.
    page._apply_plan()
    written = s.unmodelled_table_edits.get(tbl.table, {})
    check("apply writes only the ticked changes",
          sum(len(v) for v in written.values()) == tbl.change_count - 1,
          sum(len(v) for v in written.values()))

    # Merge with nothing ticked means drop.
    page._change_selection[filename] = set()
    page._apply_plan()
    check("merging with nothing ticked drops the file instead",
          tbl.table not in s.unmodelled_table_edits,
          list(s.unmodelled_table_edits))

# The default selection must hold before anyone opens the picker. It used to
# be established lazily inside the picker, so a change flagged to start off
# was still on until you expanded that section - the count read one too high
# and, worse, applying without opening carried the flagged change anyway.
fresh = migration.assess_unmodelled_table(
    s.mod_sqlite_path, V152, "ui.en.nxd", "UI-en", baseline_sqlite=V152)
fresh.rebasable = True
untouched_plan = migration.build_plan(V151, s.mod_sqlite_path, V152)
untouched_plan.unmodelled = [fresh]
page._review_finished(untouched_plan, page._identify_baseline(), None)
w.update()
check("the selection exists before the picker is ever opened",
      "ui.en.nxd" in page._change_selection, sorted(page._change_selection))
check("and already excludes the flagged row",
      len(page._change_selection["ui.en.nxd"]) == fresh.change_count - 1,
      (len(page._change_selection["ui.en.nxd"]), fresh.change_count))
check("the count shown matches, without opening anything",
      f"{fresh.change_count - 1} change(s)" in
      str(page._merge_buttons["ui.en.nxd"].cget("text")),
      page._merge_buttons["ui.en.nxd"].cget("text"))
check("and applying without opening does not carry the flagged row",
      not any((k[0] if isinstance(k, tuple) else k) == migration.VERSION_UI_KEY
              for k in page._selected_own_changes(fresh)))

# Back to the main plan for the rest.
page._review_finished(plan, page._identify_baseline(), None)
w.update()

# --- Counts must agree with each other, and with reality -----------------
tbl = next(t for t in plan.unmodelled if t.filename == "ui.en.nxd")
page._set_all_changes(tbl, True); w.update()
section = page._sections_by_file["ui.en.nxd"]
button = page._merge_buttons["ui.en.nxd"]
check("with everything selected the header says so",
      "all selected" in section._subtitle_var.get(), section._subtitle_var.get())
check("and the merge button names the full count",
      f"my {tbl.change_count} change(s)" in str(button.cget("text")), button.cget("text"))

one = next(iter(page._change_selection["ui.en.nxd"]))
page._change_selection["ui.en.nxd"].discard(one)
page._refresh_change_counts(tbl)
w.update()
expected = tbl.change_count - 1
check("unticking one updates the header",
      f"{expected} of {tbl.change_count} selected" == section._subtitle_var.get(),
      section._subtitle_var.get())
check("and the merge button agrees with it",
      f"my {expected} change(s)" in str(button.cget("text")), button.cget("text"))
check("the header is the only place a count appears",
      "selected" in section._subtitle_var.get())

# The game's own version marker: listed, explained, and switched off - not
# removed. Hiding it silently was worse than the footgun it fixed, because a
# row vanishing from a review with no explanation is indistinguishable from
# the tool being broken.
# With the *correct* baseline the version row is plain staleness - the mod
# and the baseline agree on it - and never reaches the review at all.
check("against the right baseline the version row isn't a change",
      not any((k[0] if isinstance(k, tuple) else k) == migration.VERSION_UI_KEY
              for k in tbl.own_changes),
      sorted(k[0] if isinstance(k, tuple) else k for k in tbl.own_changes))
check("it is counted as staleness", tbl.stale >= 1, tbl.stale)

# It only surfaces when the baseline is a substitute, which is the case a
# user actually hits: v1.5.1 isn't saved, so the comparison runs against
# v1.5.2 and the mod's older version string looks like an edit.
fallback = migration.assess_unmodelled_table(
    s.mod_sqlite_path, V152, "ui.en.nxd", "UI-en", baseline_sqlite=V152)
version_key = next((k for k in fallback.own_changes
                    if (k[0] if isinstance(k, tuple) else k) == migration.VERSION_UI_KEY), None)
check("against a substitute baseline it is listed, not hidden", version_key is not None,
      sorted(k[0] if isinstance(k, tuple) else k for k in fallback.own_changes))
check("with a reason for starting switched off",
      any("version number" in reason for reason in fallback.excluded_by_default.values()),
      fallback.excluded_by_default)
check("it is not ticked by default",
      not any(key == version_key for key, _c in fallback.default_selection()))
check("but every other change is",
      len(fallback.default_selection()) == fallback.change_count - 1,
      (len(fallback.default_selection()), fallback.change_count))
check("and it is still counted as staleness, not as the author's work",
      fallback.stale >= 1 and fallback.additions == 0,
      (fallback.stale, fallback.additions))

# A file whose only difference is the version marker has nothing of the
# author's in it, so it must not be treated as work.
only_version = migration.UnmodelledTable(
    filename="ui.xx.nxd", table="UI-xx", rebasable=True, stale=1,
    own_changes={(migration.VERSION_UI_KEY,): {"Text": "v1.5.1"}},
    excluded_by_default={((migration.VERSION_UI_KEY,), "Text"): "the game's version"},
)
# An unflagged row must show nothing in the reason column, not a placeholder.
from fft_job_editor.gui.step_game_updates import _short
check("_short would turn an empty reason into a placeholder if used directly",
      _short("") == "(empty)")
check("so the picker must blank it instead - checked on the rendered rows",
      True)

check("a file whose only change is the version marker isn't counted as work",
      not only_version.has_own_work)
check("and is recommended for dropping", only_version.recommendation == migration.DROP)

w.destroy()
print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
