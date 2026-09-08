# Building the Windows .exe

Follow these in order. Each step says what should happen, so you can tell
whether it worked before moving on.

You only do steps 1-4 once. After that, rebuilding is just step 5.

---

## Step 1 - Install Python

Get Python **3.12** from https://www.python.org/downloads/windows/ and run
the installer.

Two things on the installer screens matter:

- On the first screen, tick **"Add python.exe to PATH"** (bottom of the
  window). Easy to miss, and nothing later works without it.
- On the "Optional Features" screen, **"tcl/tk and IDLE"** can be left
  ticked or unticked - it makes no difference to this build. It used to say
  to keep it, because the interface was built with Tkinter, which is what
  tcl/tk provides. The interface is Qt now and the build explicitly excludes
  Tkinter, so nothing here depends on it either way. Leaving it ticked is
  the default and is harmless.

**Check it worked.** Press `Windows key + R`, type `cmd`, press Enter, then
type:

```
python --version
```

You should see `Python 3.12.something`. If you get "not recognised", the
PATH tickbox was missed - re-run the installer, choose Modify, and tick it.

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

Type these one at a time:

```
python -m venv .venv
```

```
.venv\Scripts\activate
```

**Check it worked.** The start of your command line should now show
`(.venv)`, like this:

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

## Step 4 - Install the three things needed to build

```
pip install PySide6-Essentials pillow pyinstaller
```

That is the complete list. **Do not install numpy, scipy or imageio** -
they were removed from this project on purpose and were 96 MB of the build.

Two notes on that command, both of which cost real megabytes:

- **PySide6 was missing from this step entirely** until the interface
  switched over. The build could not have contained the Qt interface even
  if it had tried to, which for a long time it did not - the entry point
  was still importing the old Tkinter one.
- **`PySide6-Essentials`, not `PySide6`.** The plain name is a
  meta-package that also pulls PySide6-Addons, whose largest component is
  WebEngine - an entire Chromium - along with Pdf, 3D, Charts and
  Multimedia. This application imports exactly three Qt modules: QtCore,
  QtWidgets and QtGui.

  Be aware of what this does NOT do, because it is easy to assume
  otherwise: Essentials is not slim. Measured at 6.11, it still ships Qt
  Quick, Qml, QmlCompiler, Qt Designer and the whole QuickControls2 style
  family - 129 MB of Qt libraries, none of which this application uses.
  Choosing Essentials avoids WebEngine and friends; it does not avoid
  those. The spec removes them from the build afterwards, which is what
  actually gets the size down and works whichever package is installed.

**Check it worked.** The last line should say `Successfully installed ...`
mentioning `PySide6_Essentials`, `pillow` and `pyinstaller`.

---

## Step 5 - Build it

```
pyinstaller packaging\ModStudio.spec --noconfirm
```

This takes a couple of minutes and prints a lot of text. That is normal.

**Check it worked.** The last line should be:

```
Building COLLECT COLLECT-00.toc completed successfully.
```

If it ends in a red `ERROR` instead, copy the last 20 lines and send them
to me - don't try to work around it.

---

## Step 6 - Find and run it

The finished program is in:

```
dist\The Ivalice Chronicles Mod Studio\
```

Inside there is **The Ivalice Chronicles Mod Studio.exe**. Double-click it.

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
This is the one I most need your eyes on. `apply_seam_fix` was rewritten
this session to remove scipy, and while the alpha channel is provably
identical and the colour fill is verified to come from within 4 pixels, no
part of it has been seen in the actual game. **What I need to know: is
there any dark halo or outline around the portrait that wasn't there
before?** If it looks the same as it always did, the rewrite is good.

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

**Windows Defender may flag or quarantine the .exe.**
A freshly built, unsigned .exe from an unknown source is a common false
positive. It doesn't mean anything is wrong with the build. If it happens,
note it and tell me - it matters for shipping on Nexus Mods, and it is
exactly why UPX compression is deliberately turned off in the spec even
though it would make the download smaller.

---

## Rebuilding later

Steps 1-4 are one-off. Next time, do step 2 (open cmd in the folder), then:

```
.venv\Scripts\activate
pyinstaller packaging\ModStudio.spec --noconfirm
```

---

## Please tell me

- The size of the `dist\The Ivalice Chronicles Mod Studio` folder
  (right-click it, Properties). My Linux build was 76 MB; Windows will
  differ and I'd rather have the real number than an estimate.
- Which of the six checks passed and which didn't.
- Whether the portrait looks the same in-game.
