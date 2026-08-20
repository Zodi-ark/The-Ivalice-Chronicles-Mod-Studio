"""Export summary must reflect Game Updates decisions - both kinds."""
import sys, tempfile
from pathlib import Path
# The project root, one level up now these live in dev/.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
TMP = Path(tempfile.mkdtemp())
from fft_job_editor import paths
paths.local_data_dir = lambda: TMP
from fft_job_editor.gui import app as app_mod

passed = failed = 0
def check(label, cond, detail=""):
    global passed, failed
    if cond: passed += 1; print(f"  PASS  {label}")
    else: failed += 1; print(f"  FAIL  {label}  ({detail})")

w = app_mod.WizardApp()
export = next(f for f in w.step_frames if hasattr(f, "_contents_summary_text"))
s = w.state_data

text = export._contents_summary_text()
check("an empty session says so", "Nothing has been edited yet" in text, text[:60])

# Decisions on files with NO editor tab.
s.unmodelled_table_edits = {"UI-en": {(2801,): {"Text": None}}}
s.other_file_replacements = {"nxd/uibuttonguide.nxd": Path("/tmp/x")}
text = export._contents_summary_text()
check("a merged table appears in the summary", "merged table" in text, text[:300])
check("a carried-through file appears too", "Carried through" in text, text[:300])
check("and it no longer claims nothing was edited",
      "Nothing has been edited yet" not in text)

# Decisions on files WITH an editor tab, which Zodi asked me to check too.
s.unmodelled_table_edits = {}
s.other_file_replacements = {}
s.ability_edits = {"en": {359: {"Name": "Demonic Ruination"}}}
s.entry_rekeys = {(155, 1): (95, 1)}
text = export._contents_summary_text()
check("ability edits from a migration show under Abilities",
      "Abilities" in text and "Nothing has been edited yet" not in text, text[:300])
check("and rekeyed encounter rows show under Encounters",
      "Encounters" in text, text[:300])

w.destroy()
print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
