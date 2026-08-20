"""End-to-end exercise of the Game Updates page against real data."""
import sys, json, shutil, sqlite3, tempfile, time
from pathlib import Path
# The project root, one level up now these live in dev/.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
TMP = Path(tempfile.mkdtemp(prefix="full_"))
from fft_job_editor import paths
paths.local_data_dir = lambda: TMP
from fft_job_editor import version_archive as va, migration
va.paths.local_data_dir = lambda: TMP
from fft_job_editor.gui import app as app_mod
from fft_job_editor.gui import step_game_updates as sgu
sgu.paths.local_data_dir = lambda: TMP

passed = failed = 0
def check(label, cond, detail=""):
    global passed, failed
    if cond: passed += 1; print(f"  PASS  {label}")
    else: failed += 1; print(f"  FAIL  {label}  ({detail})")

REFS = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / "refs"
V151 = REFS/"Version 1.5.1 nxd files to sqlite/fft_data.sqlite"
V152 = REFS/"Version 1.5.2 nxd files to sqlite/fft_data.sqlite"
MOD  = REFS/"Stale Mod/fftivc.gameplay.darkknightexpansion"
MOD_NXD = MOD/"FFTIVC/data/enhanced/nxd"
MOD_DB = MOD_NXD/"fft_data.sqlite"

# A synthetic 1.5.3 that genuinely conflicts with the mod.
V153 = TMP/"v153.sqlite"; shutil.copy(V152, V153)
con = sqlite3.connect(V153)
con.execute('UPDATE "Ability-en" SET Description=? WHERE Key=359', ("An official rebalance.",))
con.execute('UPDATE "Ability-en" SET Name=? WHERE Key=166', ("Renamed By Patch",))
con.execute('UPDATE "Ability-en" SET Description=? WHERE Key BETWEEN 10 AND 30', ("patched",))
con.execute('UPDATE "UI-en" SET Text=? WHERE Key=?', ("v1.5.3", migration.VERSION_UI_KEY))
con.commit(); con.close()

for ver, db in (("v1.5.1", V151), ("v1.5.3", V153)):
    va.archive_unpacked_nxd(MOD_NXD, ver, source=f"{ver}", clean_unpack=True,
                            sqlite_path=db, converter="demo")
    time.sleep(0.02)

w = app_mod.WizardApp()
page = w.step_frames[3]
state = w.state_data
state.ff16tools_cli_path = None
state.nxd_sqlite_path = V153
state.loaded_mod_root = MOD
state.loaded_mod_config = json.loads((MOD/"ModConfig.json").read_text(encoding="utf-8-sig"))
state.mod_sqlite_path = MOD_DB
state.other_file_replacements = {}

# converter_fingerprint(None) == "" so the cache is refused; force a match.
va.converter_fingerprint = lambda p: "demo"
sgu.version_archive.converter_fingerprint = lambda p: "demo"

page.on_show()
check("installed version read", page.installed_var.get() == "v1.5.3", page.installed_var.get())
check("baseline identified as v1.5.1",
      page._baseline and page._baseline.chosen.version == "v1.5.1",
      page._baseline and page._baseline.chosen.version)
check("the explanation cites the mod's own files",
      "own files say" in page._baseline.explain(), page._baseline.explain())
check("a stale mod is flagged", "would undo whatever the update changed" in page.verdict_var.get())
check("the sidebar entry looks like every other one",
      w.sidebar_labels[3].cget("style") == "SidebarStep.TLabel",
      w.sidebar_labels[3].cget("style"))

# Review, synchronously.
plan = migration.build_plan(V151, MOD_DB, V153)
plan.unmodelled = migration.assess_unmodelled(MOD_NXD, MOD_DB, V153, baseline_sqlite=V151)
page._review_finished(plan, page._baseline, None)
check("review produced conflicts", len(plan.conflicts()) >= 1, len(plan.conflicts()))
check("the conflict is the rebalanced description",
      any(c.key == 359 and c.field_name == "Description" for c in plan.conflicts()))
check("an advisory for the renamed row", any(a.key == 166 for a in plan.advisories))
check("unmodelled tables assessed", len(plan.unmodelled) == 9, len(plan.unmodelled))
check("summary is not a no-op", not plan.is_noop())
check("summary text mentions a conflict", "conflict" in plan.summary(), plan.summary())
check("apply button enabled after review",
      str(page.apply_button.cget("state")) == "normal")
check("conflict rows rendered with radio vars", len(page._resolution_vars) == len(plan.conflicts()))
check("unmodelled rows rendered with radio vars", len(page._unmodelled_vars) == 9)
# Merging is the only choice that keeps both the author's work and the
# update, so it is the default wherever it's possible - including for a file
# whose only changes are cleared values.
check("ui.en.nxd defaults to merging, not dropping",
      page._unmodelled_vars["ui.en.nxd"][0].get() == migration.REBASE,
      page._unmodelled_vars["ui.en.nxd"][0].get())

# Bulk resolution.
page._set_all(plan.conflicts(), migration.TAKE_UPDATE)
check("take-all sets every conflict",
      all(c.resolution == migration.TAKE_UPDATE for c in plan.conflicts()))
check("and the radio buttons follow",
      all(v.get() == migration.TAKE_UPDATE for v, _ in page._resolution_vars.values()))
page._set_all(plan.conflicts(), migration.KEEP_MOD)
check("keep-all sets them back",
      all(c.resolution == migration.KEEP_MOD for c in plan.conflicts()))

# Clean-changes toggle.
page._show_clean.set(True); page._render_plan()
check("toggling clean changes re-renders without error", True)
page._show_clean.set(False); page._render_plan()

# Apply.
from tkinter import ttk
import tkinter.messagebox as mb
mb.showinfo = lambda *a, **k: None
from fft_job_editor import modconfig as _mc
_rec = _mc.recover_replaced_files(MOD)
state.other_file_replacements = dict(_rec.other)
check("unmodelled nxd files are carried through by open-mod recovery",
      len(state.other_file_replacements) == 9, sorted(state.other_file_replacements))
page._apply_plan()
check("edits landed in state", bool(state.ability_edits.get("en")))
check("rekeys carried", len(state.entry_rekeys) == 10, len(state.entry_rekeys))
check("the dropped file was removed from carry-through",
      "nxd/ui.en.nxd" not in state.other_file_replacements)
check("target version recorded",
      getattr(state, "built_against_game_version", "") == "v1.5.3")
check("the sidebar is unchanged after applying",
      w.sidebar_labels[3].cget("style") == "SidebarStep.TLabel")

# Compare tab.
page._refresh_compare()
check("compare offers both saved versions",
      set(page.compare_from.cget("values")) == {"v1.5.1", "v1.5.3"},
      page.compare_from.cget("values"))
page.compare_from.set("v1.5.1"); page.compare_to.set("v1.5.3")
d = migration.compare_databases(V151, V153)
page._compare_finished("v1.5.1", "v1.5.3", d, None)
check("compare found differing tables", len(d) > 0, len(d))
check("compare summary reports them", "table(s) differ" in page.compare_summary_var.get(),
      page.compare_summary_var.get())
page._compare_finished("v1.5.1", "v1.5.1", {}, None)
check("identical versions report as identical",
      "identical" in page.compare_summary_var.get(), page.compare_summary_var.get())

# --- Collapsible sections: nothing truncated, nothing built until opened ---
from fft_job_editor.gui import step_editor as _se
d2 = migration.compare_databases(V151, V153)
page.compare_from.set("v1.5.1"); page.compare_to.set("v1.5.3")
page._compare_finished("v1.5.1", "v1.5.3", d2, None)
check("one collapsible section per differing table",
      len(page._compare_sections) == len(d2), (len(page._compare_sections), len(d2)))
check("all start collapsed", not any(s.is_expanded for s in page._compare_sections))
check("and unbuilt, so fifty tables cost fifty headers",
      not any(s._built for s in page._compare_sections))
first = page._compare_sections[0]
first.expand()
check("expanding builds the body", first._built and first.is_expanded)
check("and produces content", first.body.winfo_children() != [])
first.collapse()
check("collapsing hides it again", not first.is_expanded)
first.expand()
check("re-expanding does not rebuild", first._built)

page._set_all_compare_sections(True)
check("expand all opens everything", all(s.is_expanded for s in page._compare_sections))
page._set_all_compare_sections(False)
check("collapse all closes everything",
      not any(s.is_expanded for s in page._compare_sections))

# The grid view is a Treeview sized to its content, with no scrollbar of
# its own - the whole point of expanding is to see all of it.
page._show_full_rows.set(True); page._on_full_rows_toggled()
target = page._compare_sections[0]
target.expand()
def _find_tree(widget):
    if isinstance(widget, ttk.Treeview):
        return widget
    for child in widget.winfo_children():
        found = _find_tree(child)
        if found is not None:
            return found
    return None

tree = _find_tree(target.body)
check("whole-row mode renders a horizontal grid", tree is not None)
full_columns = list(tree.cget("columns")) if tree else []
check("with every column of the table plus a label column",
      len(full_columns) >= 2, full_columns)
from fft_job_editor.gui.step_game_updates import GRID_MAX_VISIBLE_ROWS
rows_here = len(tree.get_children())
check("the grid is sized to its rows, capped so a huge table can't stall the page",
      int(tree.cget("height")) == min(rows_here, GRID_MAX_VISIBLE_ROWS),
      (tree.cget("height"), rows_here))
scrollbars = [c for c in tree.master.winfo_children() if isinstance(c, ttk.Scrollbar)]
verticals = [c for c in scrollbars if str(c.cget("orient")) == "vertical"]
check("a vertical scrollbar appears only past the cap",
      bool(verticals) == (rows_here > GRID_MAX_VISIBLE_ROWS),
      (rows_here, len(verticals)))

# Toggling must not close what was open, and the default view is the same
# grid with fewer columns.
open_before = {s._title for s in page._compare_sections if s.is_expanded}
page._show_full_rows.set(False); page._on_full_rows_toggled()
open_after = {s._title for s in page._compare_sections if s.is_expanded}
check("toggling keeps the same sections open", open_before == open_after,
      (open_before, open_after))

target = next(s for s in page._compare_sections if s._title in open_after)
narrow = _find_tree(target.body)
check("the default view is also a grid, not a text block", narrow is not None)
narrow_columns = list(narrow.cget("columns")) if narrow else []
check("showing fewer columns than the whole-row view",
      len(narrow_columns) <= len(full_columns), (narrow_columns, full_columns))
check("but still the label column plus at least one field",
      len(narrow_columns) >= 2, narrow_columns)
# Without a widget-level binding the page swallows the wheel, so the grid
# only moves once the whole page has bottomed out.
check("the grid claims the wheel before the page does",
      bool(narrow.bind("<MouseWheel>")) if narrow else False)

# Opening the biggest table must be instant. It wasn't: measuring every
# value in every column cost 6.3 of 8.6 seconds, all of it in font.measure.
import time as _time
_big = max(d2.values(), key=lambda x: len(x.rows_changed)) if d2 else None
if _big is not None and len(_big.rows_changed) > 5:
    _start = _time.time()
    page._column_widths(_big, _big.columns)
    _elapsed = _time.time() - _start
    check("column widths are measured by sampling, not exhaustively",
          _elapsed < 0.5, f"{_elapsed:.2f}s")

# Subtle string changes must be explained, not rendered as two
# identical-looking lines. Real case from 1.4.0 -> 1.5.2.
from fft_job_editor.gui.step_game_updates import _subtle_note
check("a one-character change names the character and codepoints",
      "U+3079" in _subtle_note("べスラ要塞の水門を開け！", "ベスラ要塞の水門を開け！"),
      _subtle_note("べスラ要塞の水門を開け！", "ベスラ要塞の水門を開け！"))
check("a whitespace-only change says so",
      _subtle_note("Cure", " Cure ") == "  (whitespace only)")
check("identical values are never annotated", _subtle_note("same", "same") == "")
check("a visible rewrite needs no annotation",
      _subtle_note("a totally different sentence", "another one entirely!!") == "")
check("non-strings are left alone", _subtle_note(5, 7) == "")

w.destroy(); shutil.rmtree(TMP, ignore_errors=True)
print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
