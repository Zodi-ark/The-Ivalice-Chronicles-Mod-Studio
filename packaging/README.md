# packaging/

Everything needed to turn the project folder into a standalone Windows
build, so a user doesn't need Python, a `pip install`, or a 669 MB Qt
download.

```
pyinstaller packaging/ModStudio.spec --noconfirm
```

**Step-by-step instructions are in `BUILDING.md`** - that is the one to
follow on a Windows machine. This file is the reasoning behind it.

Output: `dist/The Ivalice Chronicles Mod Studio/`. **Ship the whole folder.**
The `.exe` on its own will not run.

## Status

The spec is written and **test-built on Linux**, which is what this sandbox
can do. What that proves and what it doesn't:

| verified here | still needs Windows |
|---|---|
| the spec parses and builds without error | that the `.exe` runs on Windows |
| `data/`, `assets/`, `tools/` land where `project_root()` looks for them | that FF16Tools.CLI and AudioMog still launch as subprocesses from inside the bundle |
| the frozen app launches, draws correctly, and loads the bundled reference tables | that `console=False` really suppresses the console |
| no Qt binding is pulled in | that the icon and taskbar identity survive freezing |
| the build is 173 MB, down from 483 MB | that Defender doesn't flag a fresh unsigned build |

A screenshot of the frozen Linux build was checked against the same page
running unfrozen - the sidebar logo, the reference-table load and the
General Setup copy all render identically, which is what confirms the data
files resolved rather than silently falling back.

## Where files land

Settled. `paths.py` now answers two questions instead of conflating them:

    project_root()   the folder the user downloaded - their files go here
    bundled_root()   the tool's own shipped files - read-only

Running from source these are the same folder, which is why one function did
both jobs for as long as there was no .exe. Frozen, they differ, and the
layout a user sees is:

```
The Ivalice Chronicles Mod Studio/
    The Ivalice Chronicles Mod Studio.exe
    LICENSE   NOTICE.md   README.md
    local_data/        <- unpacked game, converted database, settings
    _internal/         <- the program itself; data/ assets/ tools/ live here
```

Deleting that one folder removes every trace of the tool. Nothing is written
to AppData, the registry, or anywhere else.

Verified against a real frozen build, not reasoned about: the app was run and
its folder inspected afterwards, and `local_data/ui_settings.json` was
created at the top level rather than inside `_internal/`.

`dev/test_frozen_paths.py` keeps it that way without needing Windows. It
sets the two attributes PyInstaller sets - `sys.frozen` and `sys._MEIPASS` -
and reloads the module, so it exercises the real inputs. It also asserts the
one-file case, where `_MEIPASS` points at a temporary directory Windows
deletes on exit: `project_root()` must follow the executable and never that
folder, because a build that put the user's unpacked game there would look
like it worked every single time and lose everything every single time.

**onefile is still not supported**, and the reason is now enforced by that
test rather than by a comment. Even with paths correct, a one-file build
re-extracts ~78 MB on every launch.

### LICENSE, NOTICE and README sit at the top level

They are copied after COLLECT rather than listed in `datas`, because
PyInstaller refuses a destination outside the bundle:

```
ERROR: Invalid (SRC, DEST_DIR) tuple: (.../LICENSE, '..').
DEST_DIR must not point outside of application's top-level directory!
```

A destination of `"."` puts them in `_internal/`. That satisfies GPL-3.0 -
they do accompany the work - but it hides them. Somebody looking for the
licence or the instructions opens the folder they downloaded, sees an .exe
and a folder named `_internal`, and stops.

## Size

The source folder is 22.8 MB, and that number is doing something misleading:
**17 MB of it is FF16Tools + AudioMog, and 1.2 MB is the actual Python
code.** It contains no interpreter and no libraries, because users supplied
those themselves - Python, tkinter, and for the Textures tab a `pip install`
of Pillow, numpy, scipy and imageio.

Measured, that pip install is **231 MB**, and CPython's stdlib another 63 MB.
So a user editing textures already had roughly **295 MB** on disk. Freezing
doesn't add that cost, it makes it visible - and ships less of it.

Measured, installed and zipped:

| build | installed | download | engine change | output |
|---|---|---|---|---|
| first attempt | 175 MB | 81 MB | - | - |
| scipy pruned | 154 MB | 74 MB | none | identical |
| **current** (Pillow only) | **76 MB** | **33 MB** | done | see below |
| no imaging at all | 58 MB | 22 MB | - | Textures loses replace |

`tools/` is 17 MB of every row and isn't going anywhere.

**The floor is 58 MB installed / 22 MB zipped** - CPython, tcl/tk, the
stdlib, `tools/` and `data/`. That is the price of "the user doesn't need
Python".

### What the remaining fat is, and what it would cost to remove

The whole imaging stack exists for **two functions** in `texture_data.py`:

- `load_any_image_array` - reads a replacement image or a `.dds`
- `apply_seam_fix` - dilates colour into transparent regions so BC7 doesn't
  leave a black halo

Everything else in the tool is stdlib.

**`load_any_image_array` can be pure Pillow, provably.** Tested against the
current implementation on greyscale, RGB, RGBA and a real BC7 `.dds` - the
returned arrays are **identical in every case**, because
`Image.open(p).convert("RGBA")` already does what the `np.stack` /
`np.concatenate` branches were hand-rolling. That function's numpy use is
pure ceremony.

**`apply_seam_fix` is the one that needs a decision.** It uses
`scipy.ndimage.distance_transform_edt` for nearest-source lookup. A
numpy-only Danielsson sweep reproduces the *distances* exactly (max error 0-1
px across three test masks) but picks a **different equidistant neighbour**,
so the colour written into transparent pixels differs - about 60% of filled
pixels on a random-colour test field.

Whether that matters is a real judgement, not a technicality: those pixels
are fully transparent, and the fix exists precisely so the encoder has *some*
colour there rather than guessing. Visually it is immaterial. But it changes
the exported bytes, and this project cares about a mod exporting the same way
twice. **Not changed here.** Recorded so the trade is explicit.

## Why the first build was 483 MB

The first build came out at 483 MB. Almost none of it was this project:

```
opencv_contrib_python.libs  115 MB
cv2                          80 MB
imageio_ffmpeg               77 MB
lxml                        9.6 MB
```

None of those is imported anywhere in the codebase. They arrive because
PyInstaller's bundled hook for `imageio` collects its whole plugin
directory, and imageio ships video and computer-vision backends. `cv2` also
carries its own **Qt5**, which is how Qt libraries ended up inside a Tkinter
build.

Excluding them is safe, and that was checked rather than hoped: `imageio` is
used in exactly one place, `texture_data.load_any_image_array`, and only for
`.dds`. Reading a real BC7 `.dds` through imageio imports neither `cv2` nor
`imageio_ffmpeg` - the decode goes to Pillow.

**Worth doing properly at some point:** Pillow 12 decodes BC1 through BC7
natively. Confirmed against a hand-built BC7 file (mode 6, both endpoints
white) - `Image.open(...).convert("RGBA")` returns exactly the array
`load_any_image_array` builds. Dropping the `imageio` import from that one
function would remove this dependency at the source instead of excluding its
symptoms. Also an engine change, so also not done here.

The other large remaining item is **scipy at 53 MB** (23 MB plus 30 MB of
libraries), used for a single call - `ndimage.distance_transform_edt` in the
alpha-dilation pass. Not urgent, but 53 MB for one function is worth knowing
about if build size ever matters more than it does today.

## Choices in the spec worth knowing about

- **UPX is off.** It shaves size and is a reliable way to have a fresh
  unsigned build flagged by antivirus. A modding tool that Defender
  quarantines on download is worse than a larger one.
- **`QtSql` is excluded deliberately.** The engine reads SQLite through the
  stdlib `sqlite3` module. Backing a view with `QSqlTableModel` would bypass
  the engine's own readers, which is the "two changes at once" trap. If that
  is ever revisited, remove the exclusion - don't remove the `sqlite3` use.
- **The Qt exclusion list is already in place** even though the interface is
  still Tkinter, because that list is the reason to write this spec now
  rather than after the rewrite. `QT_INTERFACE_IS_LIVE` flips to `True` in
  the same change that removes the last Tkinter import.
- **`tkinter` is not excluded** while it is still the interface. Obvious,
  and exactly the sort of obvious thing that gets broken by a
  copy-pasted exclusion list.

## A note on what "it built" proves

Not much on its own. This project has been bitten repeatedly by checks that
confirm something happened without confirming it was the right something -
the export that generated 520 tables and copied none of them, the unpack
pass that claimed a pack because it produced *a* file rather than the file
asked for.

So the check here is not "PyInstaller exited 0". It is: the frozen binary
launches, draws the real interface, resolves its bundled data, and its
runtime folder was inspected afterwards to see where it actually wrote.
That last step is what turned a predicted `_internal/` problem into a
confirmed one.


## On the three common size tips

Worth going through these explicitly, because two are right and one is
actively wrong for a mod tool.

**"Use a clean virtual environment; install only what you need."** Right, and
it matters more than it sounds. This sandbox has `PySide6` (the meta-package)
installed, which pulls `PySide6-Addons` - QtWebEngine, Qt3D, Multimedia, the
lot. When the Qt interface arrives, the build environment should install
`pyside6-essentials`, not `pyside6`. The exclusion list in the spec is a
safety net for things that sneak in transitively; it is not a substitute for
not installing them. This build's own history is the argument: `cv2` and
`imageio_ffmpeg` were never imported by anything here and still cost 195 MB,
purely because they were sitting in the environment where a hook could find
them.

**"Exclude unused Qt plugins."** Right, but `--exclude-module` is the wrong
lever and will silently do nothing. Qt plugins and translations are collected
as *data and binaries*, not as Python modules, so `excludes` never sees them.
PyInstaller's PySide6 hook is configured instead:

```python
hooksconfig={
    "pyside6": {
        "translations": False,          # ~30 MB of .qm files
        "plugins": ["platforms", "styles", "imageformats", "iconengines"],
    },
}
```

Keep `platforms` (no window without it) and `styles`. Everything else -
`sqldrivers`, `multimedia`, `position`, `webview`, `tls` - can go for a tool
that talks to no database, plays no media and browses nothing.

**"Use UPX; it shaves 20-30%."** Generally true, and it should stay **off**
here.

UPX-packed, unsigned executables are one of the most reliable ways to get a
generic-heuristic detection from Windows Defender and most other engines,
because self-extracting compressed binaries are what a lot of actual malware
looks like from the outside. The download route makes this worse rather than
better: a tool distributed on Nexus Mods is fetched by thousands of people who
have never heard of the author, cannot check a signature, and will reasonably
believe their antivirus over a stranger. One false positive becomes a comment
thread that outlives the fix.

The trade being declined is roughly 15-20 MB off a 33 MB download, against a
risk that costs the project its credibility rather than a few seconds of
transfer. If the build is ever properly code-signed, the calculation changes
and UPX is worth revisiting - the spec has a single `upx=False` to flip.
