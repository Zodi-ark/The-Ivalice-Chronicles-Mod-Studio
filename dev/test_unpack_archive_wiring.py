"""Drives the real SetupStep helpers so the wiring is exercised, not just compiled."""
import sys, json, shutil, tempfile
from pathlib import Path
# The project root, one level up now these live in dev/.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fft_job_editor.gui import app as app_mod
from fft_job_editor import version_archive as va, migration, paths

TMP = Path(tempfile.mkdtemp(prefix="wiring_"))
passed = failed = 0
def check(label, cond, detail=""):
    global passed, failed
    if cond: passed += 1; print(f"  PASS  {label}")
    else: failed += 1; print(f"  FAIL  {label}  ({detail})")

wizard = app_mod.WizardApp()
setup = None
for frame in wizard.step_frames:
    if hasattr(frame, "_archive_this_version"):
        setup = frame
        break
check("SetupStep exposes _archive_this_version", setup is not None)
check("and _prune_version_archive", hasattr(setup, "_prune_version_archive"))
check("and _included_mod_packs", hasattr(setup, "_included_mod_packs"))

# Redirect the archive at a temp root by pointing local_data_dir there.
real_local = paths.local_data_dir
paths.local_data_dir = lambda: TMP
va.paths.local_data_dir = lambda: TMP

# Real nxd files + the real converted database that names the version.
REFS = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / "refs"
nxd_dir = REFS / "Stale Mod" / "fftivc.gameplay.darkknightexpansion" / "FFTIVC" / "data" / "enhanced" / "nxd"
sqlite_path = REFS / "Version 1.5.1 nxd files to sqlite" / "fft_data.sqlite"

setup._archive_this_version(nxd_dir, sqlite_path, "0000.pac")
# Drain whatever the worker queued so we can read the log lines.
lines = []
while not setup._queue.empty():
    kind, payload = setup._queue.get()
    if kind == "log":
        lines.append(payload)
archived = va.list_archived()
check("the unpack path actually archived a version", len(archived) == 1, [e.version for e in archived])
check("named from the database's version string",
      archived and archived[0].version == "v1.5.1", archived and archived[0].version)
check("it logged what it did", any("Archived" in l for l in lines), lines)
check("mentioning why", any("after the game patches" in l for l in lines), lines)
check("clean_unpack recorded as True with no mod packs selected",
      archived and archived[0].clean_unpack is True)

# Archiving twice must not duplicate or error.
setup._archive_this_version(nxd_dir, sqlite_path, "0000.pac")
check("a second unpack of the same version doesn't duplicate", len(va.list_archived()) == 1)

# Pruning must not delete the installed version.
setup._prune_version_archive("v1.5.1")
check("pruning never removes the installed version", len(va.list_archived()) == 1)

# A failure inside archiving must not escape.
try:
    setup._archive_this_version(Path("/nonexistent"), Path("/nonexistent.sqlite"), "x")
    check("a broken archive attempt is swallowed, not raised", True)
except Exception as exc:
    check("a broken archive attempt is swallowed, not raised", False, repr(exc))

paths.local_data_dir = real_local
wizard.destroy()
shutil.rmtree(TMP, ignore_errors=True)
print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
