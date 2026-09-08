# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for The Ivalice Chronicles Mod Studio.

Build from the PROJECT ROOT, not from this folder:

    pyinstaller packaging/ModStudio.spec --noconfirm

Output lands in `dist/The Ivalice Chronicles Mod Studio/`. Ship that whole
folder (or an installer wrapping it); the .exe alone will not run.


ONEDIR, NOT ONEFILE - and this is not a preference
==================================================

`paths.project_root()` is `Path(__file__).resolve().parent.parent`, and
every runtime file the tool owns hangs off it: `local_data/` (the unpacked
game, the converted database, the cached reference tables, ui_settings.json)
and `tools/` (FF16Tools.CLI, AudioMog).

Measured against a real frozen build rather than assumed:

    unfrozen   project_root() -> <project folder>
    onedir     project_root() -> dist/<app>/          beside the .exe
    onefile    project_root() -> /tmp/_MEIxxxxxx      DELETED ON EXIT

Under onefile the user's unpacked game folder and converted database would
be written into a temporary directory that is removed the moment the program
closes. It would look like it worked, every time, and lose everything, every
time. That is the single most expensive failure this project could ship, so
onefile is not an option.

The engine change this spec used to demand HAS BEEN MADE. `paths.py` now
answers two questions instead of conflating them - `project_root()` follows
the executable, `bundled_root()` follows `sys._MEIPASS` - so under onedir
the user's `local_data/` is created beside the .exe and not inside
`_internal/`. `dev/test_frozen_paths.py` holds it there without needing
Windows, by setting the two attributes PyInstaller sets and reloading the
module.

This docstring went on demanding that change for some time after it landed,
which is its own small lesson: a warning is as capable of going stale as a
number is, and a stale warning costs more, because the next person budgets
for work that is already done.


WHAT GETS BUNDLED
=================

data/    ~2.8 MB  reference XML tables, nex_layouts, loader_models and
                  loader_structures - all read at runtime
assets/  ~1.2 MB  icon.ico, logo.png - the sidebar logo is loaded from disk
tools/  ~20.5 MB  FF16Tools.CLI (win-x64) and AudioMog, both MIT, both
                  invoked as subprocesses, so they must stay real files on
                  disk - they cannot live inside an archive

local_data/ is deliberately NOT bundled. It is created at runtime and
belongs to the user; shipping a copy would ship one machine's cached game
data to everybody.

dev/ and packaging/ are not bundled either, and `_assert_package_contents`
at the bottom of this file fails the build if either appears. Nothing at
runtime may reach into them - see that function for why that is enforced
here rather than written down.
"""

import sys
from pathlib import Path

# SPECPATH is set by PyInstaller to the folder holding this file.
PROJECT_ROOT = Path(SPECPATH).parent  # noqa: F821 - injected by PyInstaller

APP_NAME = "The Ivalice Chronicles Mod Studio"
ENTRY = str(PROJECT_ROOT / "The Ivalice Chronicles Mod Studio.pyw")
ICON = str(PROJECT_ROOT / "assets" / "icon.ico")


# ---------------------------------------------------------------------------
# Data files
# ---------------------------------------------------------------------------
# (source, destination-inside-the-bundle). Destinations are relative to
# _internal/, which is what project_root() resolves to in a onedir build,
# so `data/`, `assets/` and `tools/` sit exactly where the code expects.

datas = [
    (str(PROJECT_ROOT / "data"), "data"),
    (str(PROJECT_ROOT / "assets"), "assets"),
    (str(PROJECT_ROOT / "tools"), "tools"),
    # LICENSE, NOTICE.md and README.md are NOT listed here. They belong
    # beside the .exe rather than inside _internal, and `datas` cannot put
    # them there - PyInstaller rejects a destination of ".." outright
    # ("DEST_DIR must not point outside of application\'s top-level
    # directory"). They are copied after COLLECT instead, at the bottom of
    # this file.
]


# ---------------------------------------------------------------------------
# Hidden imports
# ---------------------------------------------------------------------------
# Everything the tool imports is either stdlib or imported *deferred* inside
# a function, which PyInstaller's static analysis follows fine. These are
# listed anyway because they are imported lazily from inside methods and a
# future refactor could move them somewhere the analysis misses - and a
# missing imaging library does not fail at startup, it fails the first time
# somebody opens the Textures tab, which is a much worse place to find out.

hiddenimports = [
    "PIL.Image",
    "PIL.ImageTk",
    "PIL.ImageChops",
    "PIL.ImageStat",
    "PIL.DdsImagePlugin",   # .dds decode, including BC1-BC7
]


# ---------------------------------------------------------------------------
# Exclusions
# ---------------------------------------------------------------------------
# Two groups, and they are separate on purpose.

# Group 1: Qt. PySide6 IS the interface now, so this list is no longer a
# forward bet - it is load-bearing. The meta-package installs at 669 MB and
# the great majority of that is modules a desktop data editor never touches.
# WebEngine alone is the largest single component: a full Chromium.
#
# Measured: the whole application imports exactly three Qt modules -
# QtCore, QtWidgets and QtGui. Everything below is outside that set.
#
# `BUILDING.md` installs PySide6-Essentials rather than PySide6 so most of
# this is never on disk to begin with. This list stays anyway: excludes are
# the safety net for what arrives transitively, not a substitute for not
# installing it. Delete nothing from here without a reason; anything
# genuinely needed fails loudly at import, which is the right failure mode.
EXCLUDE_QT = [
    # Chromium. The big one.
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtWebChannel",
    "PySide6.QtWebSockets",
    "PySide6.QtWebView",
    # QML / Quick - this is a QtWidgets application.
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuick3D",
    "PySide6.QtQuickControls2",
    "PySide6.QtQuickWidgets",
    "PySide6.QtQuickTest",
    # 3D, multimedia, sensors, and the rest of the addon surface.
    "PySide6.Qt3DCore",
    "PySide6.Qt3DRender",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DExtras",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtSpatialAudio",
    "PySide6.QtSensors",
    "PySide6.QtSerialPort",
    "PySide6.QtSerialBus",
    "PySide6.QtBluetooth",
    "PySide6.QtNfc",
    "PySide6.QtPositioning",
    "PySide6.QtLocation",
    "PySide6.QtRemoteObjects",
    "PySide6.QtScxml",
    "PySide6.QtStateMachine",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtGraphs",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtHelp",
    "PySide6.QtDesigner",
    "PySide6.QtUiTools",
    "PySide6.QtTest",
    "PySide6.QtNetworkAuth",
    "PySide6.QtHttpServer",
    "PySide6.QtTextToSpeech",
    "PySide6.QtVirtualKeyboard",
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
    # QtSql is excluded deliberately. The engine reads SQLite through the
    # stdlib `sqlite3` module and will keep doing so - backing a view with
    # QSqlTableModel would bypass the engine's own readers, which is exactly
    # the "two changes at once" trap. If that decision is ever revisited,
    # remove this line, not the sqlite3 import.
    "PySide6.QtSql",
    # The other binding. Having both installed is a classic way to ship a
    # broken build.
    "PyQt5", "PyQt6", "PySide2",
]

# Group 2: weight pulled in transitively that a mod editor has no use for.
# numpy/scipy/PIL ARE required (the Textures tab), so they are not here.
#
# The four below are the difference between a 483 MB build and a usable one,
# and none of them is imported by this project. They arrive because
# PyInstaller's bundled hooks for `imageio` collect its entire plugin
# directory, and imageio ships bindings for video and computer vision:
#
#     opencv_contrib_python.libs  115 MB      cv2   80 MB
#     imageio_ffmpeg               77 MB      lxml  9.6 MB
#
# cv2 also bundles its own Qt5, which is how Qt got into a Tkinter build.
#
# Verified safe rather than assumed: `imageio` is used in exactly one place,
# `texture_data.load_any_image_array`, and only for `.dds`. Reading a real
# BC7 `.dds` through imageio imports neither cv2 nor imageio_ffmpeg - the
# work goes to Pillow. Excluding them cannot break that path.
#
# Better still, it can be deleted: Pillow 12 decodes BC1 through BC7
# directly, confirmed against a hand-built BC7 file. Dropping the imageio
# import from load_any_image_array would remove this whole problem at the
# source - but that is an engine change and belongs in its own session, so
# the exclusions below deal with it from the packaging side for now.
EXCLUDE_HEAVY = [
    # The scientific stack is gone from the codebase entirely. It existed
    # for two functions in texture_data.py, both now pure Pillow. Listed
    # here so that if anything ever re-imports them the build fails loudly
    # rather than quietly regaining 96 MB.
    "numpy",
    "scipy",
    "imageio",
    "cv2",
    "imageio_ffmpeg",
    "lxml",
    "yaml",
    "tifffile",
    "av",
    "skimage",
    "imageio.plugins.ffmpeg",
    "imageio.plugins.opencv",
    "imageio.plugins.pyav",
]

# Group 3: subpackages of libraries that ARE used, but whose bulk isn't.
#
# `scipy` is imported for exactly one call - `ndimage.distance_transform_edt`
# in the seam fix. Traced which subpackages that actually loads:
#
#     _lib   ndimage   special   __config__   version
#
# Everything else is dead weight. Measured on disk: optimize 15.4 MB,
# stats 17.4, sparse 13.5, linalg 11.8, spatial 7.3, io 6.3, signal 5.1,
# interpolate 4.1, integrate 3.3 - about 84 MB of scipy this tool never
# touches. Pruning them takes the scipy package from ~100 MB to ~7 MB with
# **no behaviour change at all**: the same function is called, on the same
# code path, producing the same bytes.
#
# `scipy.libs` (27 MB of OpenBLAS/gfortran) and `numpy.libs` (28 MB) survive
# this, because PyInstaller collects them as binaries rather than modules and
# `excludes` doesn't reach them. Filtering the binary TOC could remove them,
# but only if nothing loaded still links against them - worth doing only with
# a real check, not a guess, so it isn't done here.
EXCLUDE_UNUSED_SUBPACKAGES = [
    "PIL.ImageShow", "PIL.ImageGrab",
]

EXCLUDE_MISC = [
    "matplotlib",
    "pandas",
    "IPython",
    "jupyter",
    "notebook",
    "pytest",
    "setuptools",
    "pip",
    "PIL.ImageQt",       # would drag a Qt binding in through Pillow
]

# The interface toolkit that is no longer used. Gated, because excluding it
# while Tkinter was still the interface would have produced a build that
# fails at launch.
#
# These are `tkinter` and `_tkinter`, NOT "tcl" and "tk", which is what this
# list said for as long as it existed. Neither of those is an importable
# Python module - `find_spec("tcl")` returns None - so `excludes` never
# matched anything and the whole mechanism would have excluded precisely
# nothing on the day it was switched on. The names PyInstaller resolves are
# the module ones, and it is the `tkinter` module being collected that drags
# in the Tcl/Tk runtime libraries and their data directories behind it.
#
# Checked rather than assumed, because "the exclusion is spelled wrong" and
# "the exclusion works" look identical in a build log: both are silent.
EXCLUDE_TKINTER = ["tkinter", "_tkinter"]

# The interface is Qt. tkinter is excluded, which is what this flag is for.
#
# It was False for as long as `gui/` was what the entry point imported. The
# flag was correct that whole time; what was wrong was the entry point, and
# because this flag honestly described THAT, it kept excluding nothing and
# nobody looked twice. Flipping it is the last step of the change, not the
# first - excluding the toolkit while the entry point still imported it
# would have produced a build that failed at launch.
QT_INTERFACE_IS_LIVE = True

excludes = (list(EXCLUDE_QT) + list(EXCLUDE_HEAVY)
            + list(EXCLUDE_UNUSED_SUBPACKAGES) + list(EXCLUDE_MISC)
            + (list(EXCLUDE_TKINTER) if QT_INTERFACE_IS_LIVE else []))


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

a = Analysis(  # noqa: F821 - injected by PyInstaller
    [ENTRY],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    # NOT `hooksconfig={"pyside6": {...}}`. packaging/README.md recommended
    # exactly that, and it does nothing.
    #
    # Checked in the installed PyInstaller (6.22) rather than believed: the
    # only hooks that call `get_hook_config` are matplotlib's and gi's. No
    # Qt hook reads it, so the setting is accepted, ignored, and leaves no
    # trace in the build log. Confirmed from the other end too - a build
    # carrying that config still shipped 6.7 MB of Qt translations.
    #
    # The lever that does work is filtering the TOC after analysis, below.
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)


# ---------------------------------------------------------------------------
# Trimming Qt: what `excludes` cannot reach
# ---------------------------------------------------------------------------
# Qt plugins and translations are collected as DATA, not as Python modules,
# so `excludes` never sees them and `--exclude-module` silently does nothing
# to them. They have to be removed from the analysis result directly.
#
# This is the SECOND lever, not the first. The first is installing
# PySide6-Essentials rather than the PySide6 meta-package, which keeps Qml,
# Quick, Pdf, WebEngine and the rest off the disk entirely - see BUILDING.md
# step 4. Filtering here is the safety net for what a build environment
# happens to be carrying, exactly as the module excludes are.
#
# The four plugin groups kept, and why none is optional:
#
#   platforms      there is no window at all without it
#   styles         the theme work depends on the platform style
#   imageformats   .ico and .png are loaded from assets/ at runtime - the
#                  window icon, the taskbar icon and the sidebar logo.
#                  Dropping this does NOT raise: images load as null
#                  pixmaps and the app runs with no icon, which is the
#                  quiet kind of failure this project keeps meeting.
#   iconengines    multi-resolution .ico handling
#
# Dropped: sqldrivers (the engine reads SQLite through stdlib sqlite3),
# multimedia, position, webview, tls, virtualkeyboard and the rest.
# Translations are .qm files for an English-only interface.

_KEEP_PLUGINS = {"platforms", "styles", "imageformats", "iconengines"}

# Qt SHARED LIBRARIES for modules this application does not import.
#
# These are a separate problem from the module `excludes` above. Excluding
# `PySide6.QtQuick` stops the Python binding being collected; it does not
# stop `libQt6Quick.so` / `Qt6Quick.dll`, which PyInstaller's Qt hook gathers
# through `collect_extra_binaries()` as a BINARY. Measured: a build with all
# of these in `excludes` still shipped Quick, Qml, Pdf and QmlModels, about
# 20 MB on Linux and more on Windows.
#
# The first-line fix is installing PySide6-Essentials rather than the PySide6
# meta-package, which never puts them on disk. This list is what makes the
# build small anyway on a machine that happens to have Addons installed - and
# a build whose size depends on what else the builder has installed is a
# build that will surprise somebody.
#
# Kept, deliberately: Core, Gui, Widgets (the three the app imports), DBus and
# XcbQpa (Linux platform integration), Svg and OpenGL (QtGui links them).
# Network is kept because Qt's own TLS and platform code reach for it and the
# saving is 2 MB against a risk of a late failure.
_DROP_QT_MODULES = {
    "Quick", "Quick3D", "QuickControls2", "QuickParticles", "QuickShapes",
    "QuickTemplates2", "QuickWidgets", "QuickTest", "QuickDialogs2",
    "QuickDialogs2QuickImpl", "QuickDialogs2Utils", "QuickLayouts",
    "QuickControls2Basic", "QuickControls2BasicStyleImpl",
    "QuickControls2Fusion", "QuickControls2FusionStyleImpl",
    "QuickControls2Imagine", "QuickControls2ImagineStyleImpl",
    "QuickControls2Material", "QuickControls2MaterialStyleImpl",
    "QuickControls2Universal", "QuickControls2UniversalStyleImpl",
    "QuickControls2Impl", "QuickControls2Windows",
    "QuickControls2WindowsStyleImpl", "QuickControls2macOSStyleImpl",
    "QuickControls2FluentWinUI3StyleImpl", "QuickControls2iOSStyleImpl",
    "QuickEffects", "QuickVectorImage", "QuickVectorImageGenerator",
    "QuickTimeline", "QuickTimelineBlendTrees",
    "Qml", "QmlModels", "QmlMeta", "QmlWorkerScript", "QmlLocalStorage",
    "QmlXmlListModel", "QmlCore", "QmlCompiler", "QmlNetwork", "QmlAsset",
    "Designer", "DesignerComponents",   # Qt Designer, shipped in Essentials
    "Pdf", "PdfQuick", "PdfWidgets",
    "WebEngineCore", "WebEngineWidgets", "WebEngineQuick", "WebChannel",
    "WebChannelQuick", "WebSockets", "WebView",
    "Multimedia", "MultimediaWidgets", "MultimediaQuick", "Spatial Audio",
    "SpatialAudio",
    "Charts", "ChartsQml", "DataVisualization", "DataVisualizationQml",
    "3DCore", "3DRender", "3DInput", "3DLogic", "3DAnimation", "3DExtras",
    "3DQuick", "3DQuickScene2D", "3DQuickExtras",
    "VirtualKeyboard", "VirtualKeyboardQml", "VirtualKeyboardSettings",
    "Sensors", "SerialPort", "SerialBus", "Positioning", "Location",
    "Bluetooth", "Nfc", "RemoteObjects", "Scxml", "StateMachine",
    "TextToSpeech", "Help", "Designer", "UiTools", "Test",
    "Sql",                      # the engine reads SQLite through stdlib
    "WaylandClient", "WaylandCompositor", "WaylandEglClientHwIntegration",
}


def _is_dropped_qt_library(dest: str) -> bool:
    """
    True for a Qt shared library belonging to a module we do not import.

    Matches the module name between the `Qt6` prefix and the extension, so
    it catches `libQt6Quick.so.6`, `Qt6Quick.dll` and `QtQuick.abi3.so`
    alike, and does NOT catch `Qt6Core` because "Core" is not in the set.
    """
    name = Path(dest).name
    for prefix in ("libQt6", "Qt6", "libQt", "Qt"):
        if name.startswith(prefix):
            rest = name[len(prefix):]
            module = rest.split(".")[0]
            if module in _DROP_QT_MODULES:
                return True
            break
    return False


# Three more categories, all measured against the real win_amd64 wheel that
# `BUILDING.md` step 4 installs, because the Linux build this spec is
# usually exercised on does not contain them and reasoning from it would
# have missed every one.
#
#   Qt's developer tools     12.2 MB   designer, linguist, assistant, uic,
#                                      rcc, lupdate/lrelease, and the qml*
#                                      family. Build-time and authoring
#                                      tools. A frozen application never
#                                      shells out to any of them.
#   the qml/ module tree     19.0 MB   QML modules and their plugins. This
#                                      application contains no QML.
#   resources/icudtl.dat     10.0 MB   Chromium's Unicode data, which ships
#                                      with WebEngine. Essentials has no
#                                      WebEngine, and - checked - there is
#                                      no ICU library anywhere in the wheel
#                                      that could load it. Qt on Windows
#                                      uses the OS Unicode APIs. It is an
#                                      orphan.
#
# NOT dropped: `opengl32sw.dll`, 19.7 MB and the single largest file in the
# wheel. It is Qt's software OpenGL fallback, used when the machine has no
# usable GPU driver - virtual machines, remote desktop sessions, and old
# laptops. Dropping it would be the biggest single saving available and
# would make the tool fail to start for exactly the users least able to
# diagnose it. Set DROP_SOFTWARE_OPENGL below if you are shipping to a
# known audience; it is off deliberately.

DROP_SOFTWARE_OPENGL = False

# The Qt Python bindings to keep. The application imports Core, Gui and
# Widgets; DBus and Network are kept because Qt's own platform and TLS code
# reaches for them and the saving is under 2 MB against the risk of a
# failure that only appears on someone else's machine.
_KEEP_BINDINGS = {"Core", "Gui", "Widgets", "Network", "DBus"}

_QT_DEV_TOOLS = {
    "designer.exe", "linguist.exe", "assistant.exe", "uic.exe", "rcc.exe",
    "lupdate.exe", "lrelease.exe", "qmlls.exe", "qmlformat.exe",
    "qmllint.exe", "qmlcachegen.exe", "qmltyperegistrar.exe",
    "qmlimportscanner.exe", "svgtoqml.exe", "qmlprofiler.exe",
    "qmlpreview.exe", "qmlscene.exe", "qmltestrunner.exe", "balsam.exe",
    "qsb.exe", "meta objectdump.exe", "androiddeployqt.exe",
    # the same tools where a platform ships them without the extension
    "designer", "linguist", "assistant", "uic", "rcc", "lupdate",
    "lrelease", "qmlls", "qmlformat", "qmllint", "qmlcachegen",
    "qmltyperegistrar", "qmlimportscanner", "svgtoqml",
}


def _is_qt_dead_weight(dest: str) -> bool:
    """Developer tools, the QML tree, build metadata, and orphaned data."""
    path = Path(dest)
    parts = path.parts
    if "PySide6" not in parts:
        return False
    if path.name in _QT_DEV_TOOLS:
        return True
    if "qml" in parts:                       # PySide6/qml/... module tree
        return True
    if "resources" in parts and path.name == "icudtl.dat":
        return True
    if "metatypes" in parts:                 # build-time type metadata
        return True
    if path.suffix == ".pyi":                # type stubs, for editors only
        return True
    # Python bindings for Qt modules this application never imports. The
    # module `excludes` list names these too, but excludes act on the import
    # graph and the Qt hook adds the binding files as BINARIES, so one does
    # not imply the other. `QtOpenGL.pyd` alone is 8.3 MB and survived the
    # excludes.
    if path.suffix in (".pyd", ".so") and path.name.startswith("Qt"):
        module = path.name.split(".")[0][2:]
        if module not in _KEEP_BINDINGS:
            return True
    if DROP_SOFTWARE_OPENGL and path.name == "opengl32sw.dll":
        return True
    return False


def _is_qt_translation(dest: str) -> bool:
    parts = Path(dest).parts
    return "PySide6" in parts and "translations" in parts


def _is_unwanted_qt_plugin(dest: str) -> bool:
    parts = Path(dest).parts
    if "PySide6" not in parts or "plugins" not in parts:
        return False
    index = parts.index("plugins")
    return len(parts) > index + 1 and parts[index + 1] not in _KEEP_PLUGINS


def _strip(entry) -> bool:
    dest = entry[0]
    return (_is_qt_translation(dest) or _is_unwanted_qt_plugin(dest)
            or _is_dropped_qt_library(dest) or _is_qt_dead_weight(dest))


_before = len(a.datas) + len(a.binaries)
a.datas = [e for e in a.datas if not _strip(e)]
a.binaries = [e for e in a.binaries if not _strip(e)]
_removed = _before - (len(a.datas) + len(a.binaries))

# A filter that matches nothing looks identical to a filter that worked, so
# say which it was. This project has been bitten more than once by a pass
# that reported success having inspected nothing.
print(f"\nQt trim: removed {_removed} translation/plugin/library entries "
      f"(kept plugin groups: {', '.join(sorted(_KEEP_PLUGINS))})")

pyz = PYZ(a.pure)  # noqa: F821 - injected by PyInstaller

exe = EXE(  # noqa: F821 - injected by PyInstaller
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX is off deliberately. It shaves size but is a reliable way to get
    # a fresh build flagged by antivirus, and a modding tool that Defender
    # quarantines on download is worse than a larger one.
    upx=False,
    console=False,   # the whole point of the .pyw entry point - no console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON if Path(ICON).exists() else None,
)

coll = COLLECT(  # noqa: F821 - injected by PyInstaller
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)


# ---------------------------------------------------------------------------
# After the build: the three files a user should be able to find
# ---------------------------------------------------------------------------
# A destination of "." would put these inside `_internal/`. That satisfies
# GPL-3.0 - they do accompany the work - but it hides them. Somebody
# looking for the licence or the instructions opens the folder they
# downloaded, sees an .exe and a folder named `_internal`, and stops. The
# top level is the one place people reliably look.
#
# `datas` cannot express this, so it is done here. COLLECT has finished by
# the time this runs, and DISTPATH is injected by PyInstaller.

import shutil

_top_level = Path(DISTPATH) / APP_NAME  # noqa: F821 - DISTPATH is injected
for _name in ("LICENSE", "NOTICE.md", "README.md"):
    _source = PROJECT_ROOT / _name
    if _source.exists():
        shutil.copy2(_source, _top_level / _name)


# ---------------------------------------------------------------------------
# After the copy: assert the package is what it should be
# ---------------------------------------------------------------------------
# "Which folders can I delete once the .exe is built?" is a real question with
# a precise answer, and the answer belongs HERE rather than in a README,
# because a list in a README goes stale silently while a failing build does
# not. `verify_package.py` checks the source zip; this checks the artefact.
#
# The two halves are not symmetrical.
#
# MUST BE PRESENT is about the app working. Each of these is read at runtime
# and its absence fails late - `tools/` only when somebody unpacks, `assets/`
# only as a missing icon - which is the worst kind of packaging bug, because
# the build log is clean and the failure surfaces at a user.
#
# MUST BE ABSENT is about not shipping the development record and, more
# importantly, about proving nothing at runtime reaches into it. `dev/` is
# the one to watch: `audit_flag_enums.py` reads `dev/modloader/`, and if any
# RUNTIME module ever grows a dependency on that path the exe breaks only
# when that one feature is used. Excluding it here turns that from a silent
# runtime failure into a build failure.
#
# `local_data/` is in the absent list for a different reason again: it is the
# user's own cached game data, and shipping one machine's copy to everybody
# would be a privacy problem as well as a size one.

_MUST_BE_PRESENT = [
    "data",           # nex_layouts, loader_models, loader_structures, XML
    "assets",         # icon and sidebar logo, loaded from disk
    "tools",          # FF16Tools.CLI and AudioMog, run as subprocesses
]
_MUST_BE_PRESENT_AT_TOP = ["LICENSE", "NOTICE.md", "README.md"]

_MUST_BE_ABSENT = [
    "dev",            # suites, audits, and dev/modloader/
    "packaging",      # only needed to BUILD
    "local_data",     # runtime cache, the user's own files
    "HANDOFF.md",
    "NEXT_SESSION_PROMPT.md",
    ".venv",
    "build",
]

_internal = _top_level / "_internal"
_problems = []

for _name in _MUST_BE_PRESENT:
    if not (_internal / _name).exists():
        _problems.append(f"MISSING from _internal/: {_name}")

for _name in _MUST_BE_PRESENT_AT_TOP:
    if (PROJECT_ROOT / _name).exists() and not (_top_level / _name).exists():
        _problems.append(f"MISSING from the top level: {_name}")

for _name in _MUST_BE_ABSENT:
    for _where in (_top_level, _internal):
        if (_where / _name).exists():
            _problems.append(f"SHIPPED but should not be: {_where.name}/{_name}")

# Tkinter must not be in a Qt build. This is the one exclusion that was
# spelled wrong for its whole existence ("tcl"/"tk", which are not modules),
# so it is checked against the artefact rather than trusted from the list.
for _pattern in ("tcl", "tk8*", "tk9*", "_tkinter*", "tkinter"):
    for _hit in list(_internal.glob(_pattern)) + list(_top_level.glob(_pattern)):
        _problems.append(f"Tkinter runtime shipped: {_hit.name}")

# Without this the loops above pass by inspecting nothing - the failure this
# project keeps meeting, most recently a reachability probe that reported
# 47 bugs and "everything is reachable" in the same run.
if not _internal.is_dir():
    _problems.append(f"the bundle directory does not exist: {_internal}")

if _problems:
    raise SystemExit(
        "\n*** The built package is not what it should be ***\n  "
        + "\n  ".join(_problems)
        + "\n\nThis is the spec's own post-build check. Fix the cause rather "
          "than deleting the check: it exists because a packaging fault is "
          "invisible in a clean build log and surfaces at a user.\n")

print(f"\npackage check: {len(_MUST_BE_PRESENT)} required folders present, "
      f"{len(_MUST_BE_ABSENT)} excluded items absent, no Tkinter runtime.")
