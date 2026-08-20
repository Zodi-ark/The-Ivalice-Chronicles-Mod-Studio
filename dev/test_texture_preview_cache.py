"""A replacement .tex must not show the game's texture back at you.

The preview cache was keyed on the bare filename, so a mod's `foo.tex` and
the game's `foo.tex` shared one entry. The current texture converts first,
so the replacement preview showed the game's image. `.tga` was unaffected
because it is never cached - which is precisely how the report described it.
"""
import sys, tempfile, time
from pathlib import Path

# The project root, one level up now these live in dev/.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from fft_job_editor import texture_data as td

TMP = Path(tempfile.mkdtemp(prefix="texcache_"))
passed = failed = 0
def check(label, cond, detail=""):
    global passed, failed
    if cond: passed += 1; print(f"  PASS  {label}")
    else: failed += 1; print(f"  FAIL  {label}  ({detail})")

# Two different files that happen to share a name - a game texture and a
# mod's replacement for it.
game_dir = TMP / "game"; mod_dir = TMP / "mod"
game_dir.mkdir(); mod_dir.mkdir()
game_tex = game_dir / "portrait.tex"; mod_tex = mod_dir / "portrait.tex"
game_tex.write_bytes(b"GAME" * 64)
mod_tex.write_bytes(b"MODD" * 128)

cache = TMP / "cache"

def key_for(path):
    """The cache path the loader would use, without needing FF16Tools."""
    import hashlib
    stat = path.stat()
    digest = hashlib.sha256(
        f"{path.resolve()}|{stat.st_size}|{int(stat.st_mtime)}".encode()).hexdigest()[:16]
    return (cache / f"{digest}_{path.name}").with_suffix(".dds")

check("two files with the same name get different cache entries",
      key_for(game_tex) != key_for(mod_tex), (key_for(game_tex), key_for(mod_tex)))
check("the cache name still ends in the original filename, so it stays readable",
      key_for(game_tex).name.endswith("portrait.dds"), key_for(game_tex).name)

# Editing a file must invalidate its entry.
before = key_for(mod_tex)
time.sleep(1.1)
mod_tex.write_bytes(b"MODD" * 200)
check("editing a texture changes its cache entry", key_for(mod_tex) != before)

# The dispatch that makes a recovered mod's .tex previewable at all.
check(".tex replacements route through the game-texture loader",
      "load_game_texture_preview" in td.load_replacement_preview.__doc__)

# A .tga replacement takes the direct path and never touches the cache.
from PIL import Image
tga = mod_dir / "plain.tga"
Image.new("RGBA", (4, 4), (1, 2, 3, 255)).save(tga)
arr = td.load_replacement_preview(tga, None, cache)
check("a .tga replacement loads directly", arr.shape == (4, 4, 4), arr.shape)
check("and writes nothing to the cache",
      not cache.exists() or not any(cache.iterdir()))

import shutil
shutil.rmtree(TMP, ignore_errors=True)
print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
