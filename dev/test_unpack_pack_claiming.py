"""A pack must not be retired by an incidental filter match.

FF16Tools' --filter is a plain substring test against each file's internal
path, so "ui/" matches "bg/ui/..." as well as "ui/...". The unpack loop
retired a pack as soon as it produced any file for any filter - so the `ui/`
pass pulled a handful of `bg/ui/**` files out of the bg pack, marked it done,
and the `bg/` pass never ran against it. `bg/textures/**` was never
extracted, and the Textures tab then reported those textures as "added by
the mod - the game has no original".
"""
import sys
from pathlib import Path

# The project root, one level up now these live in dev/.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from fft_job_editor import game_install

passed = failed = 0
def check(label, cond, detail=""):
    global passed, failed
    if cond: passed += 1; print(f"  PASS  {label}")
    else: failed += 1; print(f"  FAIL  {label}  ({detail})")


def make_handler(folder_name):
    """The counting logic from step_setup's make_line_handler, isolated."""
    state = {"extracted": 0, "in_folder": 0}
    prefix = f"{folder_name}/" if folder_name else None

    def handle(line):
        if " Extracting '" not in line:
            return
        state["extracted"] += 1
        if prefix:
            start = line.find(" Extracting '") + len(" Extracting '")
            end = line.find("'", start)
            if end > start and line[start:end].replace("\\", "/").startswith(prefix):
                state["in_folder"] += 1

    handle.extracted = lambda: state["extracted"]
    handle.in_folder = lambda: state["in_folder"]
    return handle


# The exact collision: the ui pass reading the bg pack.
ui_pass = make_handler("ui")
for path in ("bg/ui/map_icon_01.tex", "bg/ui/map_icon_02.tex"):
    ui_pass(f"[FF16Tools] Extracting '{path}' ...")
check("the ui filter does extract files from the bg pack", ui_pass.extracted() == 2)
check("but none of them are actually in ui/", ui_pass.in_folder() == 0,
      ui_pass.in_folder())
check("so the bg pack is not retired by the ui pass", ui_pass.in_folder() == 0)

# The bg pass against the same pack does the real work.
bg_pass = make_handler("bg")
for path in ("bg/textures/017/gt_0_map017_map_color.tga", "bg/anims/map_001_anim.bin"):
    bg_pass(f"[FF16Tools] Extracting '{path}' ...")
check("the bg filter matches files genuinely under bg/", bg_pass.in_folder() == 2)
check("so the bg pack is retired only after its own pass", bg_pass.in_folder() > 0)

# A pack that really is the ui pack must still be retired, or the speed-up
# this optimisation exists for is gone.
real_ui = make_handler("ui")
for path in ("ui/ffto/unit/texture/ui_wm_base_uitx.tex", "ui/ffto/icon/a_000_uitx.tex"):
    real_ui(f"[FF16Tools] Extracting '{path}' ...")
check("the real ui pack is still retired by the ui pass", real_ui.in_folder() == 2)

# Windows-style separators must count too.
win = make_handler("bg")
win("[FF16Tools] Extracting 'bg\\textures\\017\\gt_0_map017_map_color.tga' ...")
check("backslash paths are recognised", win.in_folder() == 1)

# Non-extraction lines are never counted as either.
noise = make_handler("bg")
noise("[FF16Tools] Done. 6084 files.")
check("summary lines aren't counted as extractions", noise.extracted() == 0)

# An unfiltered pass has no folder to check against, and must not claim on
# a folder count that can never rise.
whole = make_handler(None)
whole("[FF16Tools] Extracting 'bg/textures/017/x.tga' ...")
check("an unfiltered pass counts extractions", whole.extracted() == 1)
check("and reports no folder match, since there's no folder to match",
      whole.in_folder() == 0)

# The filter strings themselves: a trailing slash is not an anchor.
ui_filter = game_install.GAME_FOLDERS_BY_NAME["ui"].filter_text
check("the ui filter is 'ui/'", ui_filter == "ui/")
check("which really does substring-match a bg path - the root of the bug",
      ui_filter in "bg/ui/map_icon_01.tex")
check("bg is part of the textures group, so it was always meant to unpack",
      "bg" in next(g for g in game_install.CONTENT_GROUPS if g.key == "textures").folders)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
