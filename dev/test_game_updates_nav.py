"""Sidebar structure and the Game Updates page's own logic."""
import sys, json, tempfile, shutil
from pathlib import Path
# The project root, one level up now these live in dev/.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
TMP = Path(tempfile.mkdtemp(prefix="nav_"))
from fft_job_editor import paths
paths.local_data_dir = lambda: TMP
from fft_job_editor import version_archive as va, migration
va.paths.local_data_dir = lambda: TMP
from tkinter import ttk
from fft_job_editor.gui import app as app_mod

passed = failed = 0
def check(label, cond, detail=""):
    global passed, failed
    if cond: passed += 1; print(f"  PASS  {label}")
    else: failed += 1; print(f"  FAIL  {label}  ({detail})")

REFS = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / "refs"
V151 = REFS / "Version 1.5.1 nxd files to sqlite" / "fft_data.sqlite"
V152 = REFS / "Version 1.5.2 nxd files to sqlite" / "fft_data.sqlite"
V151 = REFS / "Version 1.5.1 nxd files to sqlite" / "fft_data.sqlite"
MOD = REFS / "Stale Mod" / "fftivc.gameplay.darkknightexpansion"

w = app_mod.WizardApp()
check("four pages registered", len(w.step_frames) == 4, len(w.step_frames))
check("three are workflow steps", app_mod.STEP_TITLES == ["General Setup", "Edit Game Data", "Export Mod"])
check("Game Updates is a utility page, not a step",
      app_mod.UTILITY_TITLES == ["Game Updates"], app_mod.UTILITY_TITLES)
check("titles and frames line up", len(app_mod.ALL_PAGE_TITLES) == len(w.step_frames))
check("one sidebar label per page",
      len(w.sidebar_labels) == len(app_mod.ALL_PAGE_TITLES), len(w.sidebar_labels))
# Labels are stored by page index, not by creation order. With two utility
# pages the two orders diverge, and the sidebar highlighted the wrong entry.
for _i, _title in enumerate(app_mod.ALL_PAGE_TITLES):
    check(f"sidebar[{_i}] really is {_title}",
          str(w.sidebar_labels[_i].cget("text")) == _title,
          w.sidebar_labels[_i].cget("text"))
w._show_step(len(app_mod.ALL_PAGE_TITLES) - 1); w.update()
check("opening the last page highlights the last page",
      w.sidebar_labels[-1].cget("style") == "SidebarStepActive.TLabel",
      [str(l.cget("style")) for l in w.sidebar_labels])
check("and nothing else is highlighted",
      sum(1 for l in w.sidebar_labels
          if str(l.cget("style")) == "SidebarStepActive.TLabel") == 1)

# The utility entry must be packed to the bottom, the steps to the top.
sides = [lbl.pack_info()["side"] for lbl in w.sidebar_labels]
check("workflow steps pack to the top", sides[:3] == ["top"] * 3, sides)
check("the utility page packs to the bottom", set(sides[3:]) == {"bottom"}, sides)

# Selecting it works, and styling follows.
w._show_step(3)
check("clicking Game Updates raises it", w.current_step == 3)
check("and marks it active",
      w.sidebar_labels[3].cget("style") == "SidebarStepActive.TLabel",
      w.sidebar_labels[3].cget("style"))

# Alerts by title, not index.
# An alert must NOT change how the entry looks: every sidebar entry is
# styled the same way, because one that changes colour when the others
# never do reads as a glitch rather than as a signal.
w.set_sidebar_alert("Game Updates", True)
check("an alert on the active page still looks like any active page",
      w.sidebar_labels[3].cget("style") == "SidebarStepActive.TLabel",
      w.sidebar_labels[3].cget("style"))
w._show_step(0)
check("and like any idle page once you navigate away",
      w.sidebar_labels[3].cget("style") == "SidebarStep.TLabel",
      w.sidebar_labels[3].cget("style"))
check("the now-active page is styled normally",
      w.sidebar_labels[0].cget("style") == "SidebarStepActive.TLabel")
# The amber styles must be gone from the theme, not merely unused - a
# registered-but-unused style is exactly what gets quietly reintroduced.
# `lookup` returns an inherited default ("black") for a style that was
# never configured, so absence can't be tested directly; testing that it
# is not the amber value can, and is the thing that actually matters.
_alert_fg = ttk.Style(w).lookup("SidebarStepAlert.TLabel", "foreground")
check("no amber sidebar style is registered any more",
      _alert_fg not in ("#e0a33c", "#f0b955"), _alert_fg)
w.set_sidebar_alert("Game Updates", False)
check("clearing the alert changes nothing either",
      w.sidebar_labels[3].cget("style") == "SidebarStep.TLabel")
w.set_sidebar_alert("No Such Page", True)
check("an unknown title is ignored rather than raising", True)

page = w.step_frames[3]
state = w.state_data

# Nothing set up at all.
page.on_show()
check("with nothing unpacked it says so",
      "Unpack your game files" in page.verdict_var.get(), page.verdict_var.get())
check("and raises no alert", w.sidebar_labels[3].cget("style") == "SidebarStep.TLabel")

# Game unpacked, no mod.
state.nxd_sqlite_path = V152
page.on_show()
check("the installed version is read from the database",
      page.installed_var.get() == "v1.5.2", page.installed_var.get())
check("with no mod open it invites you to open one",
      "Open a mod" in page.verdict_var.get(), page.verdict_var.get())
check("still no alert", w.sidebar_labels[3].cget("style") == "SidebarStep.TLabel")

# A mod opened with no saved versions to compare against: the page must say
# so plainly rather than guessing a baseline out of thin air.
MOD_NXD = MOD / "FFTIVC" / "data" / "enhanced" / "nxd"
state.loaded_mod_root = MOD
state.loaded_mod_config = json.loads((MOD / "ModConfig.json").read_text(encoding="utf-8-sig"))
state.mod_sqlite_path = MOD_NXD / "fft_data.sqlite"
page.on_show()
check("with no saved versions the page says it can't compare",
      "No saved game version" in page.verdict_var.get(), page.verdict_var.get())
check("and raises no alert it can't justify",
      w.sidebar_labels[3].cget("style") == "SidebarStep.TLabel")

# Now save two versions, so a baseline can actually be identified.
import time as _time
va.converter_fingerprint = lambda p: "demo"
from fft_job_editor.gui import step_game_updates as _sgu
_sgu.version_archive.converter_fingerprint = lambda p: "demo"
_sgu.paths.local_data_dir = lambda: TMP
for _ver, _db in (("v1.5.1", V151), ("v1.5.2", V152)):
    va.archive_unpacked_nxd(MOD_NXD, _ver, sqlite_path=_db, converter="demo")
    _time.sleep(0.02)

page.on_show()
check("the mod's name is shown once a mod is open",
      "Dark Knight" in page.mod_version_var.get(), page.mod_version_var.get())
check("a baseline is identified from the saved versions",
      page._baseline is not None and page._baseline.found)
check("and it is the version the mod's own files claim",
      page._baseline.chosen.version == "v1.5.1", page._baseline.chosen.version)
check("the verdict explains the risk in plain words",
      "would undo whatever the update changed" in page.verdict_var.get(),
      page.verdict_var.get())
check("a stale mod does not recolour the sidebar entry",
      w.sidebar_labels[3].cget("style") == "SidebarStep.TLabel",
      w.sidebar_labels[3].cget("style"))

# A mod matching the installed version clears the alert. Pointing the mod's
# database at v1.5.2 itself is the cleanest way to say "built against this".
state.mod_sqlite_path = V152
state.loaded_mod_config = {"ModId": "x", "PluginData": {}}
migration.apply_stamp(state.loaded_mod_config, migration.ModStamp(game_version="v1.5.2"))
page.on_show()
check("a current mod reads as up to date",
      "built against the game files you have" in page.verdict_var.get(),
      page.verdict_var.get())
check("and does not promise there will be nothing to decide",
      "should find nothing that needs a decision" not in page.verdict_var.get())
check("and the sidebar still looks the same",
      w.sidebar_labels[3].cget("style") == "SidebarStep.TLabel",
      w.sidebar_labels[3].cget("style"))

# A mod naming a version that isn't saved must not be called "up to date".
# Both lines used to appear together: "no saved copy of v1.5.1 is
# available, using v1.5.2" and "this mod already matches v1.5.2".
state.mod_sqlite_path = MOD_NXD / "fft_data.sqlite"
state.loaded_mod_config = {"ModId": "x", "PluginData": {}}
migration.apply_stamp(state.loaded_mod_config, migration.ModStamp(game_version="v1.4.0"))
page.on_show()
check("a fallback baseline is flagged as one",
      page._baseline is not None and page._baseline.fell_back,
      page._baseline and page._baseline.chosen.version)
check("and the verdict says the comparison is against a substitute",
      "no saved copy of that version" in page.verdict_var.get(), page.verdict_var.get())
check("rather than claiming the mod matches the installed game",
      "built against the game files you have" not in page.verdict_var.get())
check("the two lines no longer contradict each other",
      "v1.4.0" in page.baseline_var.get() and "v1.4.0" in page.verdict_var.get(),
      (page.baseline_var.get(), page.verdict_var.get()))

check("the three tabs are present",
      [page.notebook.tab(i, "text") for i in page.notebook.tabs()]
      == ["Status", "Review Changes", "Compare Versions"],
      [page.notebook.tab(i, "text") for i in page.notebook.tabs()])

w.destroy()
shutil.rmtree(TMP, ignore_errors=True)
print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
