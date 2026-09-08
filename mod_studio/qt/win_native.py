"""
Windows 11 window materials, through ctypes.

Mica and Acrylic are composited by the Desktop Window Manager BEHIND the
window. Asking for one is two calls; actually seeing one needs a third
thing that a first attempt here missed, and it is worth writing down
because the failure looks exactly like "Windows isn't cooperating":

**The window has to be transparent for the backdrop to show.** DWM was
drawing Mica correctly and the application was painting an opaque
background over it. Turning on transparency effects in Windows
personalisation could not help, because nothing translucent ever reached
the screen. See `theme.stylesheet(backdrop=True)`.

So there are three parts, and all three are required:

1. `DWMWA_SYSTEMBACKDROP_TYPE` - ask DWM for the material
2. `DwmExtendFrameIntoClientArea` with -1 margins - let it reach the whole
   client area rather than just the title bar
3. a window that paints nothing behind its content - the stylesheet's job

QWindowKit was considered and skipped. It is C++ with no Python bindings on
PyPI, so it would mean shiboken6 bindings and an ABI-matched toolchain. It
does bundle the plumbing above, which is the honest argument in its favour -
but the plumbing is the twenty lines below, and it primarily exists to
restore snap layouts, edge resizing and shadows after going FRAMELESS.
Keeping the native title bar means there is nothing to restore.

Every call is wrapped and swallowed. This is decoration, and must never be
the reason a window fails to appear. It no-ops off Windows and on builds
older than Windows 11 22H2.
"""
from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes

DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_SYSTEMBACKDROP_TYPE = 38

# Windows 11 22H2 and newer. The caption, its text and the window's own
# 1px border, painted in colours we choose instead of the system's.
DWMWA_BORDER_COLOR = 34
DWMWA_CAPTION_COLOR = 35
DWMWA_TEXT_COLOR = 36

# "Go back to whatever you would have done." Used when the app has no
# opinion, so nothing is left pinned to a stale colour.
DWMWA_COLOR_DEFAULT = 0xFFFFFFFF

BACKDROP_AUTO = 0
BACKDROP_NONE = 1
BACKDROP_MICA = 2        # DWMSBT_MAINWINDOW
BACKDROP_ACRYLIC = 3     # DWMSBT_TRANSIENTWINDOW
BACKDROP_TABBED = 4

BY_NAME = {
    "none": BACKDROP_NONE,
    "mica": BACKDROP_MICA,
    "acrylic": BACKDROP_ACRYLIC,
    "tabbed": BACKDROP_TABBED,
}


class _Margins(ctypes.Structure):
    _fields_ = [("cxLeftWidth", ctypes.c_int), ("cxRightWidth", ctypes.c_int),
                ("cyTopHeight", ctypes.c_int), ("cyBottomHeight", ctypes.c_int)]


def caption_inset() -> int:
    """
    The height of the strip DWM keeps for the caption, in pixels.

    `SM_CYCAPTION + SM_CYSIZEFRAME + SM_CXPADDEDBORDER`, which on Zodi's
    machine is 23 + 4 + 4 = 31 - exactly the gap the probe measured between
    the frame top and the client top in a normal and in a maximised window.
    That is the strip Windows normally puts the client area BELOW.

    Read from the system metrics rather than from
    `frameGeometry() - geometry()`. That difference is the same 31 in the
    two states where no inset is wanted and **0 in fullscreen, the one
    state where it is** - so the reverted attempt was using a number that
    was precisely inverted with respect to the problem, which is why it
    pushed everything down in the wrong windows and did nothing in the
    right one.

    `FFT_CAPTION_INSET` overrides it. The strip is not directly observable
    from here - nobody can measure what DWM paints from inside the process
    - so a way to try 23 against 31 on real hardware without a rebuild is
    worth the four lines.
    """
    override = os.environ.get("FFT_CAPTION_INSET")
    if override:
        try:
            return max(0, int(override))
        except ValueError:
            pass
    if not sys.platform.startswith("win"):
        return 0
    try:
        import ctypes
        metrics = ctypes.windll.user32.GetSystemMetrics
        SM_CYCAPTION, SM_CYSIZEFRAME, SM_CXPADDEDBORDER = 4, 33, 92
        return (metrics(SM_CYCAPTION) + metrics(SM_CYSIZEFRAME)
                + metrics(SM_CXPADDEDBORDER))
    except Exception:                                          # noqa: BLE001
        return 0


def colorref(hex_colour: str) -> int:
    """
    `#rrggbb` as a Win32 COLORREF, which is 0x00bbggrr - byte-reversed.

    Worth a function rather than an inline expression: passing an ordinary
    0xrrggbb here does not fail, it silently paints the wrong colour, and
    a red caption where a blue one was asked for is the whole of the
    symptom.
    """
    value = hex_colour.lstrip("#")
    r, g, b = (int(value[i:i + 2], 16) for i in (0, 2, 4))
    return (b << 16) | (g << 8) | r


def apply_caption_colours(window, background: str | None = None,
                          text: str | None = None) -> bool:
    """
    Paints the title bar in the application's own colours.

    This is the answer to "the sidebar's background extends into the title
    bar", after four attempts at pushing content away from it. The cause is
    not a container with a missing margin - it is that the client area
    overlaps the caption by a few pixels in a maximised window, and the
    sidebar is the one thing up there with a fill of its own. A page that
    paints nothing shows the caption through cleanly; a painted panel
    blends into it.

    Nothing inside the process can measure that overlap, so no margin can
    be the right size for it. Painting the caption the sidebar's colour
    makes the overlap invisible whatever its size - and turns a bleed into
    the deliberate "content extends into the title bar" the Windows
    guidance describes.

    `None` for either colour restores the system default, which is what
    lets a theme change actually change it back rather than leaving the
    last colour pinned.

    Returns True only if the caption colour was accepted. It needs Windows
    11 22H2; older builds ignore the attribute, which lands exactly where
    this project already was, so there is nothing to fall back to.
    """
    if not sys.platform.startswith("win") or window is None:
        return False
    try:
        dwm = ctypes.windll.dwmapi
        hwnd = wintypes.HWND(int(window.winId()))

        def attr(which: int, value: int) -> bool:
            data = ctypes.c_uint(value)
            return dwm.DwmSetWindowAttribute(
                hwnd, ctypes.c_uint(which),
                ctypes.byref(data), ctypes.sizeof(data)) == 0

        fill = (DWMWA_COLOR_DEFAULT if background is None
                else colorref(background))
        # The 1px border too. Left at the system colour it draws a bright
        # hairline around a dark caption, which reads as a seam in exactly
        # the place this is trying to stop looking seamed.
        attr(DWMWA_BORDER_COLOR, fill)
        attr(DWMWA_TEXT_COLOR,
             DWMWA_COLOR_DEFAULT if text is None else colorref(text))
        return attr(DWMWA_CAPTION_COLOR, fill)
    except Exception:                                          # noqa: BLE001
        return False


def is_supported() -> bool:
    """Windows 11 22H2 (build 22621) or newer, where the backdrop API exists."""
    if not sys.platform.startswith("win"):
        return False
    try:
        version = sys.getwindowsversion()
        return version.major >= 10 and version.build >= 22621
    except Exception:                                          # noqa: BLE001
        return False


def apply_window_materials(window, dark: bool = False,
                           backdrop: str = "mica",
                           dark_glyphs: bool | None = None) -> bool:
    """
    Asks the compositor for a backdrop and a matching title bar.

    Returns True only when the backdrop was accepted, so a caller can tell
    "applied" from "not applied" rather than assuming. The Settings page
    uses that to say plainly when a material is unavailable instead of
    showing a tick that does nothing.

    Call this AFTER the window is shown. `winId()` creates the handle, but
    DWM attributes set before the window is mapped are unreliable.
    """
    if not sys.platform.startswith("win"):
        return False
    try:
        dwm = ctypes.windll.dwmapi
        hwnd = wintypes.HWND(int(window.winId()))

        def attr(which: int, value: int) -> bool:
            data = ctypes.c_int(value)
            return dwm.DwmSetWindowAttribute(
                hwnd, ctypes.c_uint(which),
                ctypes.byref(data), ctypes.sizeof(data)) == 0

        # The minimise/maximise/close glyphs, which Windows draws itself.
        #
        # This followed the app THEME, which was right while the caption
        # was whatever Windows painted. Now that the caption is painted in
        # the app's colours it has to follow the CAPTION: light mode has a
        # dark sidebar and therefore a dark title bar, and glyphs chosen
        # from the theme would be dark on dark.
        #
        # `dark_glyphs=None` keeps the old behaviour for callers that do
        # not paint the caption at all.
        wants_light_glyphs = dark if dark_glyphs is None else dark_glyphs
        attr(DWMWA_USE_IMMERSIVE_DARK_MODE, 1 if wants_light_glyphs else 0)

        wanted = BY_NAME.get(backdrop, BACKDROP_NONE)

        # The frame IS extended into the client area, with -1 margins.
        #
        # This was briefly removed, on the theory that
        # `DWMWA_SYSTEMBACKDROP_TYPE` covered the window on its own and that
        # the extension was what bled the material across the title bar.
        # That was wrong in the way that matters: without the extension the
        # backdrop does not reach the client area at all, and the window
        # became a transparent sheet with unreadable text on it. Mica had
        # been working; removing this broke it outright.
        #
        # The lighter band along the top is the tab strip having no
        # background of its own, not the extension misbehaving. That is a
        # stylesheet problem and is fixed there.
        margins = (_Margins(-1, -1, -1, -1)
                   if wanted in (BACKDROP_MICA, BACKDROP_ACRYLIC,
                                 BACKDROP_TABBED)
                   else _Margins(0, 0, 0, 0))
        dwm.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(margins))
        return attr(DWMWA_SYSTEMBACKDROP_TYPE, wanted)
    except Exception:                                          # noqa: BLE001
        return False
