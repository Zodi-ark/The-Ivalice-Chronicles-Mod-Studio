# Building the Windows .exe

Follow these in order. Each step says what should happen, so you can tell
whether it worked before moving on.

You only do steps 1-4 once. After that, rebuilding is just step 5.

---

## Step 1 - Python 3.14

Mod Studio is built with Python **3.14**: checked with 3.14.8, python.org's
newest on 30 September 2026. If 3.14 is what you already use, check which
one Windows finds. Press `Windows key + R`, type `cmd`, press Enter, then
type:

```
py -3.14 --version
```

You should see `Python 3.14.something`. Then go on to step 2.

If you don't have 3.14 yet, get the **Windows installer (64-bit)** of the
newest 3.14 from https://www.python.org/downloads/windows/ and run it:

- On the first screen, tick **"Add python.exe to PATH"** (bottom of the
  window). Easy to miss.
- On the "Optional Features" screen, **"tcl/tk and IDLE"** makes no
  difference to this build (it leaves Tkinter out either way), and
  **"Download free-threaded binaries"** is best left unticked. The
  free-threaded Python (3.14t) can't run PySide6; `py -3.14` always picks
  the normal one, so even ticked it changes nothing below.

**If `py` is "not recognised"**, the launcher wasn't installed. Type
`python --version` instead: if it says 3.14, use `python` wherever these
steps say `py -3.14`. If it says another version, re-run the 3.14
installer, choose Modify, and tick "py launcher".

Python 3.12 works too (the same steps with `-3.12`). 3.14 is the one this
page was checked with.

---

## Step 2 - Open a command prompt inside the project folder

Open the **The Ivalice Chronicles Mod Studio** folder in File Explorer -
the one containing `HANDOFF.md` and the `packaging` folder.

Click once in the **address bar** at the top (where the folder path is),
type `cmd`, and press Enter.

A black command window opens, already pointing at that folder. Everything
below is typed into this window.

**Check it worked.** Type:

```
dir packaging
```

You should see `ModStudio.spec` listed. If you see "File Not Found", the
window is pointing at the wrong folder.

---

## Step 3 - Make a clean build environment

This creates a private, isolated copy of Python just for building, so
whatever else is installed on your machine can't leak into the .exe. That
is not housekeeping - an earlier build was 483 MB instead of 154 MB purely
because unrelated packages were sitting in the environment.

**If the folder already has a `.venv` from an earlier build, delete it
first.** It holds whatever versions were installed then: 0.9.0 was built
with PySide6 6.12.0, not the 6.11.2 step 4 installs (read from its own
files). Type:

```
rmdir /s /q .venv
```

(If it says "The system cannot find the file specified", there was none,
which is fine.) Then, one at a time:

```
py -3.14 -m venv .venv
```

```
.venv\Scripts\activate
```

```
python --version
```

**Check it worked.** The start of your command line should now show
`(.venv)`, and the last command should say `Python 3.14.something`:

```
(.venv) C:\...\The Ivalice Chronicles Mod Studio>
```

If `(.venv)` isn't there, the rest will build the wrong thing. Windows
sometimes blocks the activate script; if you get a security error, close
this window, open **Command Prompt** rather than PowerShell, and repeat
step 2.

> **Note:** the `.venv` folder appears inside the project folder. That is
> fine and expected - `verify_package.py` knows to ignore it, so it will
> never end up in a release zip.

---

## Step 4 - Install what the build needs

```
python -m pip install PySide6-Essentials==6.11.2 pillow==12.3.0 numpy==2.5.3 scipy==1.18.1 pyinstaller==6.22.3
```

That is the complete list, every version pinned: they are the versions
every check here runs with, and the ones the build was checked with on
3.14.8. Each has a Windows download for Python 3.14, so pip fetches it
ready made rather than trying to compile anything. If pip ever says
"Building wheel for ...", stop: that means a version has no download for
your Python, and the build would not be the one checked.

numpy and scipy are the face seam fix's: the Portrait Seam Fixer's own
algorithm, back at Zodi's asking, adds them to the build again (91 MB of a
Linux build; the spec leaves out the parts of scipy it never loads). **Do not install imageio**: the script used it only to open
.dds files, which Pillow reads itself here, and it drags in video tools.

**Keep the `==6.11.2`**: it is the PySide6 Mod Studio is checked with. The
next, 6.12.0 (pip's newest in October 2026), sizes some panes differently;
on Linux the window then can't be made narrower than 2,476 pixels. 0.9.0
was built with 6.12.0 (its own files say so); none of the checks here ran
with it.

Two notes on that command, both of which cost real megabytes:

- **PySide6 was missing from this step entirely** until the interface
  switched over. The build could not have contained the Qt interface even
  if it had tried to, which for a long time it did not - the entry point
  was still importing the old Tkinter one.
- **`PySide6-Essentials`, not `PySide6`.** The plain name is a
  meta-package that also pulls PySide6-Addons, whose largest component is
  WebEngine - an entire Chromium - along with Pdf, 3D, Charts and
  Multimedia. This application imports exactly four Qt modules: QtCore,
  QtWidgets, QtGui and QtOpenGL (the Map Editor draws battle maps with the
  graphics card). All four are in Essentials.

  Be aware of what this does NOT do, because it is easy to assume
  otherwise: Essentials is not slim. Measured at 6.11, it still ships Qt
  Quick, Qml, QmlCompiler, Qt Designer and the whole QuickControls2 style
  family - 129 MB of Qt libraries, none of which this application uses.
  Choosing Essentials avoids WebEngine and friends; it does not avoid
  those. The spec removes them from the build afterwards, which is what
  actually gets the size down and works whichever package is installed.

**Check it worked.** The last line should say `Successfully installed ...`
mentioning `PySide6_Essentials-6.11.2`, `pillow-12.3.0`, `numpy-2.5.3`,
`scipy-1.18.1` and `pyinstaller-6.22.3`.

---

## Step 5 - Build it

```
pyinstaller packaging\ModStudio.spec --noconfirm --clean
```

This takes a couple of minutes and prints a lot of text. That is normal.
`--clean` makes PyInstaller forget what it kept from an earlier build (one
made with another Python, say), so nothing old is mixed in.

**Check it worked.** The last lines should be these three (the numbers in
front of `INFO` are timings, and differ):

```
... INFO: Building COLLECT COLLECT-00.toc completed successfully.

package check: 3 required folders present, 7 excluded items absent, no Tkinter runtime.
... INFO: Build complete! The results are available in: ...\dist
```

The `package check` line is the spec's own check of what it built: the
folders the program needs are in, the things it must leave out are not.
If it instead stops with `*** The built package is not what it should be
***`, or ends in a red `ERROR`, copy the last 20 lines and send them to me
- don't try to work around it. A few `WARNING` lines along the way are
normal.

---

## Step 6 - Find and run it

The finished program is in:

```
dist\The Ivalice Chronicles Mod Studio\
```

Inside there is **The Ivalice Chronicles Mod Studio.exe**, with `LICENSE`,
`NOTICE.md` and `README.md` beside it (the build copies them there; 0.9.0
had no `NOTICE.md`, so it came from an older spec). Double-click the .exe.

> **Important:** the .exe needs the folder around it. Copying just the .exe
> somewhere else will not work. When you share it, share (or zip) the whole
> `The Ivalice Chronicles Mod Studio` folder from inside `dist`.

---

## What to check, in order

These are ordered by how likely they are to be a problem. The first four
are things freezing typically breaks; the last two are code that changed
this session and has never run on Windows.

**1. It opens at all, with no black console window behind it.**
That is what `console=False` in the spec is for. A console window appearing
means the setting didn't take.

**2. The icon is right** - on the window, and on the taskbar while running.

**3. General Setup can unpack your game files.**
This is the big one. It runs FF16Tools.CLI from inside the bundle as a
separate program, and paths work differently in a frozen build than from
source. If unpacking works, most of the packaging is proven.

**4. The Sounds tab can load a sound bank.** Same test for AudioMog.

**5. The Textures tab can preview a `.tex` file.**
This exercises tex-conv *and* the rewritten image loader. It should look
exactly as it always has.

**6. Replace a face texture, export the mod, and look at it in-game.**
`apply_seam_fix` is the Portrait Seam Fixer's own `_fix_array` again, byte
for byte (`dev/test_seam_fix.py`). **What to look for: no dark line across
the portrait**, as the fixer's own before and after pictures show. If the
build can't find numpy or scipy, the export says so for that texture
rather than writing it without the fix, naming what failed to load in
Python's own words (it used to tell you to run pip, which can't reach the
.exe's own copies in `_internal`).

---

## One thing that will look wrong but isn't

**Your settings and unpacked game should NOT be in `_internal`.** Check
`dist\The Ivalice Chronicles Mod Studio\local_data\` - beside the .exe,
not inside `_internal`. This section used to say the opposite, describing
the `_internal` placement as a known issue awaiting a `paths.py` change.
That change has since been made: `paths.py` now answers "where does the
user's stuff go" and "where are the tool's own bundled files" as two
separate questions, and `dev/test_frozen_paths.py` holds them apart.

If you DO find `local_data` inside `_internal`, that is a real regression
and worth reporting.

**Windows Defender may flag or quarantine the .exe.** It has happened: a
build downloaded from GitHub was reported as `Trojan:Win32/Wacatac.C!ml`.
What to do is in **If Windows Defender flags the .exe** below.

---

## If Windows Defender flags the .exe

Reported from a real download: *"Trojan:Win32/Wacatac.C!ml ... Affected
items: ...\The Ivalice Chronicles Mod Studio.exe"*.

**What that name means.** `!ml` at the end means Defender's
machine-learning model *guessed* the file is malware from how it looks. It
did not match a known piece of malware. `Wacatac` is the generic name that
guess is filed under. Programs built with PyInstaller get this guess
often, because PyInstaller's launcher - the small program at the front of
every PyInstaller .exe - is also used by a lot of real malware, so the model
has learned to distrust it. It is a long-running, widely reported problem
with PyInstaller, not something in this tool's code. Two of the usual
causes are already avoided here: the build is one folder rather than one
self-extracting file, and UPX compression is off.

**But check before trusting it**, because a guess can also be right:

1. **Is the downloaded file exactly the one you built?** Open PowerShell and
   run this on the .exe you built (in `dist\...`) and again on the one you
   downloaded:

   ```
   Get-FileHash "C:\path\to\The Ivalice Chronicles Mod Studio.exe"
   ```

   If the two long `Hash` values are identical, the download is your build,
   byte for byte. If they differ, stop and find out why before going
   further - don't restore or allow the file.
2. **Optionally, a second opinion:** upload the .exe to
   https://www.virustotal.com. A false positive of this kind typically shows
   a few engines with generic or machine-learning names (`Wacatac`, `!ml`,
   `Generic`, `ML`) and the large majority clean.

**Then report it to Microsoft** - this is what actually removes the warning,
for you and for everyone who downloads the same file:

1. Go to https://www.microsoft.com/en-us/wdsi/filesubmission
2. Choose **Software developer** and sign in with a Microsoft account (so
   you can follow the result).
3. Upload **just the .exe**, not the whole folder or zip (the page takes up
   to 50 MB).
4. Choose **Incorrectly detected as malware/malicious**, give the detection
   name (`Trojan:Win32/Wacatac.C!ml`), and say it is an open-source mod tool
   built with PyInstaller, with a link to the GitHub repository.
5. When the result comes back as clean, update Defender (Windows Security,
   Virus & threat protection, **Protection updates**, **Check for updates**),
   and restore the file from **Protection history** if it was quarantined.

**Each new build is a new file**, so a later release can be guessed at
again. Report it again if so. Two things make that less likely:

- **Build PyInstaller's launcher yourself (optional).** The most common
  advice for exactly this problem: a launcher compiled on your own machine
  has different bytes from the one shared by every PyInstaller program,
  malware included. It needs Microsoft's C++ build tools (a large, free
  install: "Build Tools for Visual Studio", with the **Desktop development
  with C++** workload). Then, in the activated `.venv` from step 3:

  ```
  set PYINSTALLER_COMPILE_BOOTLOADER=1
  python -m pip uninstall -y pyinstaller
  python -m pip cache remove pyinstaller
  python -m pip install --verbose --no-binary=pyinstaller pyinstaller
  ```

  and build again with step 5. This is widely reported to reduce these
  detections. It is not a guarantee, and it could not be tested from the
  Linux machine this project is developed on, which has no Windows or
  Defender.
- **Code signing** is the lasting fix: a signed program builds a
  reputation with Microsoft over time. The options, as of September 2026:
  - SignPath Foundation - free for open-source projects that meet its
    conditions. The GitHub repository has to be the project's own, all
    maintainers use two-factor sign-in, and a code signing policy is
    published.
  - Azure Artifact Signing - about US$10 a month, and for individuals
    only in the USA and Canada.
  - A traditional OV certificate - roughly US$150-300 a year.

---

## Rebuilding later

Steps 1-4 are one-off. Next time, do step 2 (open cmd in the folder), then:

```
.venv\Scripts\activate
pyinstaller packaging\ModStudio.spec --noconfirm --clean
```

A new Python (say 3.14.9) needs nothing; a new minor version (3.15) means
steps 3 and 4 again, and is worth asking about first: PySide6 6.11.2 runs
on 3.10 to 3.14 only.

---

## Please tell me

- The size of the `dist\The Ivalice Chronicles Mod Studio` folder
  (right-click it, Properties). My Linux build on Python 3.14.8 is 304 MB,
  92 MB of it numpy and scipy (a Linux build also carries the system's own
  libraries, which Windows doesn't need); Windows will differ and I'd
  rather have the real number than an estimate.
- Which of the six checks passed and which didn't.
- Whether the portrait looks the same in-game.
