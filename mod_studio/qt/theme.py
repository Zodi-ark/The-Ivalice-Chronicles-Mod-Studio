"""
Colours and stylesheet, by role rather than by value.

This is the palette design from the Tkinter theme attempt that was reverted,
brought back because the design was right and only the toolkit was wrong.
Nothing outside this module names a colour. Pages ask for `text_muted` or
`danger`, so a theme change is a change here and nowhere else - which is
exactly what the Tkinter version could not manage, because ttk widgets were
configured at build time and a live switch left half the window looking
like leftovers.

The light palette used to hold the values the Tkinter interface had, on the
principle that light should look like the tool always has. That was the
right caution while dark was the risk; it stopped being right once light
was looked at on hardware under Mica. Measured from those screenshots:

    sidebar text  (185,185,185) on sidebar (114,114,114)   2.5 : 1
    list panel    (252,252,251) on page    (244,243,241)   8 levels apart

2.5:1 is below the 4.5:1 a body-text minimum asks for, and eight levels is
no separation at all - which is exactly the "everything blends into
everything" that was reported. Neither number is a Mica bug: `#1c1c1c` at
0.60 alpha over a LIGHT backdrop composites to mid-grey while
`sidebar_text` stays the light grey chosen for a dark panel, and surfaces
at 0.72 over a near-white backdrop land on near-white. Dark escapes both
because dark-over-dark stays dark.

So light is now its own design rather than dark's values inverted:

  - a page background that is genuinely grey, so panels can sit ABOVE it
    in white rather than beside it in the same colour;
  - three tonal steps (`window_bg` < `surface_alt` < `surface`) instead of
    two that were a rounding error apart;
  - hairlines with enough weight to be seen on white;
  - a sidebar that stays dark under a backdrop, and text that reads on it.

Qt stylesheets have no `box-shadow`, so the "elevation" separating the
editor from the list is done with tone and a hairline rather than with a
shadow. That is a real constraint, not a preference - a QGraphicsEffect per
panel is the alternative and it costs a repaint of the whole subtree.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication

LIGHT = {
    # Grey, not white. This is the layer panels sit on top of; if it is
    # white there is no "on top of" to be had.
    "window_bg":     "#e8ebf0",
    "surface":       "#ffffff",
    "surface_alt":   "#f1f4f8",
    # 1.5:1 against white. Enough to see, not enough to draw a box around
    # everything - which is the failure mode on the other side.
    "border":        "#c5ccd6",
    "text":          "#14181f",
    # 6.6:1 on white. The old #6a6a6a was 5.7:1 on #ffffff but only 3.4:1
    # once Mica washed the surface out from under it.
    #
    # This is NOT enough under Acrylic, where the page background is the
    # wallpaper and measured 99 to 255 across one window. Darkening it to
    # #3f4753 and filling the group boxes was tried and reverted - not
    # because the numbers were wrong but because the result was not wanted.
    # Revisit as a design question, not a contrast one.
    "text_muted":    "#59616e",
    "sidebar_bg":    "#1b1e24",
    # 10.4:1 on the sidebar. The old #b9b9b9 measured 2.5:1 on hardware.
    "sidebar_text":  "#c3cad5",
    "sidebar_active": "#ffffff",
    "accent":        "#c8a44a",
    "ok":            "#1e7a34",
    "attention":     "#96590a",
    "danger":        "#b3261e",
    "added":         "#dcf1e2",
    "removed":       "#fbe3e0",
    "changed":       "#fbf0d2",
    "selection":     "#cbdff7",
    "selection_text": "#10233a",
    # The edited-row marking. It used to be `constants.EDITED_ROW_BG`/`_FG`
    # - see DARK below for why that mattered - and was reported as
    # disappearing into a washed-out light theme. Deepened so it still
    # reads as a marking against a white surface.
    "edited_bg":     "#bde7c6",
    "edited_fg":     "#0e4023",
    # The row under the pointer. Quieter than the selection, or every
    # sweep of the mouse across a ten-thousand-row tree reads as a click.
    "hover":         "#e4ebf4",
    # What the title bar is painted, when Windows lets us paint it.
    #
    # The sidebar's colour, so the sidebar continues into the caption
    # instead of bleeding into a foreign grey - see `caption_colours()`.
    "caption_bg":    "#1b1e24",
    "caption_fg":    "#e8ebf0",
}

DARK = {
    "window_bg":     "#1e1f22",
    "surface":       "#2b2d31",
    "surface_alt":   "#26282c",
    "border":        "#3d4046",
    "text":          "#e6e6e6",
    "text_muted":    "#9a9da3",
    "sidebar_bg":    "#141517",
    "sidebar_text":  "#9a9da3",
    "sidebar_active": "#ffffff",
    "accent":        "#d8b662",
    "ok":            "#6bbf73",
    "attention":     "#e0a253",
    "danger":        "#e8705f",
    "added":         "#1f3324",
    "removed":       "#3a2321",
    "changed":       "#332e1c",
    "selection":     "#2f4a6d",
    "selection_text": "#eaf1fb",
    # A DARK green, not the light one.
    #
    # The marking used `constants.EDITED_ROW_BG` (#c7ecc9) in both themes.
    # That is a light-theme colour, and on the Textures tab of a mod with
    # 3,708 replacements it filled the tree with a wall of bright green in
    # a dark window. The tint here reads as "this row is yours" at a glance
    # while staying part of the theme rather than shouting over it.
    "edited_bg":     "#1e3a2a",
    "edited_fg":     "#8fd9a3",
    "hover":         "#2a2d33",
    "caption_bg":    "#141517",
    "caption_fg":    "#e6e6e6",
}


# Phthalo Green.
#
# Not a hue rotation of DARK. Phthalo is a very deep, blue-leaning
# blue-green and it behaves like a dark theme - surfaces darker than their
# text, panels lifting UPWARD out of the window - so the structure is
# dark's and only the material changes.
#
# Two decisions worth stating, because both are easy to get wrong:
#
# Gold is an ACCENT, not a text colour. The logo's #c8a44a on a deep green
# reads at about 6:1, which is legible - and gold body text over a whole
# interface is exhausting and reads as a warning. So gold carries the
# things that mean "here" and "yours": the active sidebar marker, focus,
# progress, and the edited-row marking. Body text stays a near-white with a
# faint green cast so it belongs to the surface it sits on rather than
# fighting the accent.
#
# The edited marking is GOLD, not green. Every other theme marks an edited
# row in green because green reads as "changed" against a neutral surface.
# Here the surface is green, so a green marking would be the one thing that
# vanishes. Gold is both distinguishable and already the colour this
# interface uses for "this one is active".
PHTHALO = {
    # The window, and the panels lifting out of it. Each step adds green
    # rather than grey, so depth reads as more pigment, not as haze.
    "window_bg":     "#0e2b25",
    "surface":       "#164037",
    "surface_alt":   "#12352d",
    "border":        "#25574a",
    "text":          "#e7f1ec",
    # 7.4:1 on the surface. Muted, still clearly readable.
    "text_muted":    "#9dbcb1",
    "sidebar_bg":    "#0a201b",
    "sidebar_text":  "#a8c6bb",
    "sidebar_active": "#ffffff",
    "accent":        "#c8a44a",
    "ok":            "#5fc98a",
    "attention":     "#e0b055",
    "danger":        "#f08a80",
    "added":         "#123f2e",
    "removed":       "#3f2020",
    "changed":       "#3a3320",
    "selection":     "#1d5a4a",
    "selection_text": "#f2f8f5",
    # Gold, for the reason in the note above.
    "edited_bg":     "#3d3419",
    "edited_fg":     "#f0cd7d",
    "hover":         "#173f36",
    "caption_bg":    "#0a201b",
    "caption_fg":    "#e7f1ec",
}


# Every appearance the interface can be set to, by name.
#
# This used to be a boolean called `dark`, which was fine for exactly two
# of them. The functions below still ACCEPT that boolean - every existing
# caller and every existing check passes one - and a name means the same
# thing said precisely.
APPEARANCES = {"light": LIGHT, "dark": DARK, "phthalo": PHTHALO}

# Which ones behave like a dark theme: light text on dark surfaces, dark
# window buttons, the darker set of backdrop alphas. Phthalo is one, which
# is why it needs saying - a third palette is not automatically a third
# BEHAVIOUR, and everything downstream still only has two.
DARK_FAMILY = frozenset({"dark", "phthalo"})


def appearance_name(appearance) -> str:
    """The name of an appearance, given a name or the old boolean."""
    if isinstance(appearance, str):
        return appearance if appearance in APPEARANCES else "light"
    return "dark" if appearance else "light"


def is_dark_appearance(appearance) -> bool:
    """Whether this appearance behaves like a dark one."""
    return appearance_name(appearance) in DARK_FAMILY


# How much of the backdrop each layer lets through, per MATERIAL and theme.
#
# These were one shared set of numbers and could not be, twice over.
#
# By theme, because the same alpha means "still dark" over a dark material
# and "washed to nothing" over a light one - 0.60 on the sidebar is what
# turned a near-black panel into mid-grey with light-grey text on it.
#
# By material, because Mica and Acrylic are not the same picture. Acrylic
# is the heavier frosted blur and its glassier panels were liked as they
# were, so it keeps the values it always had. Mica's panels are nearly
# solid, which is what gives light mode something to read against.
#
# The sidebar differs between them, and the reason is the title bar.
#
# Under MICA it is opaque. The caption is painted `caption_bg`, and a
# translucent sidebar composites to something a few levels off it, which
# shows up as a seam exactly where this is trying to be seamless - measured
# on hardware at 0.95 alpha, caption (27,30,36) against sidebar (38,40,46).
# Opaque, the sidebar IS `caption_bg` and the two are the same pixel value.
#
# Under ACRYLIC it is translucent, because Acrylic is the material where
# the whole window is glass and a solid column down the left is not that
# material. That is a deliberate trade and it costs two things:
#
#   - the caption cannot match the sidebar, because what a 60%-translucent
#     panel composites to depends on the wallpaper behind it and the
#     process never sees that;
#   - the app cannot promise its own sidebar text is readable, for the same
#     reason. 40% of that background belongs to the user's desktop.
#
# Both are inherent to a see-through sidebar rather than faults in these
# numbers, which is why they are recorded here instead of being tuned away.
BACKDROP_ALPHA = {
    "mica": {
        False: {"surface": 0.94, "surface_alt": 0.80, "sidebar": 1.00},
        True:  {"surface": 0.72, "surface_alt": 0.55, "sidebar": 1.00},
    },
    "acrylic": {
        False: {"surface": 0.72, "surface_alt": 0.55, "sidebar": 0.60},
        True:  {"surface": 0.72, "surface_alt": 0.55, "sidebar": 0.60},
    },
}


def material(backdrop) -> str:
    """
    Normalises what callers pass as `backdrop` into a material name.

    `False`/`"none"` mean no material; `True` means Mica, which is what the
    flag meant when it was a boolean; "tabbed" is Mica's sibling and takes
    Mica's numbers.
    """
    if backdrop is False or backdrop is None or backdrop == "none":
        return "none"
    if backdrop is True:
        return "mica"
    return "acrylic" if backdrop == "acrylic" else "mica"


def caption_colours(dark) -> dict:
    """
    What to paint the title bar, and whether its glyphs need to be light.

    The window cannot stop the caption overlapping it. Measured from
    Zodi's screenshots of a MAXIMISED window, scanning down two columns:

        x=110 (sidebar)             x=900 (page area)
          y= 0..23  (129,140,138)     y= 0..29  (129,140,138)   caption
          y=24..29  ( 69, 73, 72)     y=30+     (246,243,235)   page
          y=30+     (114,114,114)

    The client area starts about six rows before DWM stops painting the
    caption. The page survives that because with a backdrop it paints
    nothing and the caption shows through clean; the sidebar does not,
    because `QFrame#Sidebar` has a fill. That is the whole of the "the
    sidebar extends into the title bar" report - a fill, not a position -
    and no layout margin can move a fill.

    Four attempts pushed content away from the caption, one container at a
    time, and each revealed the next container. The containers were never
    the fault. Nor can the overlap be measured from inside the process:
    `frameGeometry() - geometry()` is 31 where 0 is wanted and 0 where 31
    is, which is what made the first attempt worse than nothing.

    So the caption is painted the SIDEBAR's colour instead. The overlap
    stops mattering at any size, in every window state, with a backdrop and
    without, and the sidebar continuing up into the strip becomes
    deliberate rather than dirty.

    `dark_glyphs` follows the CAPTION's luminance, not the app's theme.
    The minimise/maximise/close glyphs are drawn by Windows from
    `DWMWA_USE_IMMERSIVE_DARK_MODE`; setting that from the app theme would
    put dark glyphs on the dark caption that light mode now has.
    """
    c = palette(dark)
    return {"background": c["caption_bg"], "text": c["caption_fg"],
            "dark_glyphs": _is_dark(c["caption_bg"])}


def _is_dark(hex_colour: str) -> bool:
    """Relative luminance below the midpoint, for choosing glyph colour."""
    value = hex_colour.lstrip("#")
    r, g, b = (int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))

    def channel(x):
        return x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4

    return (0.2126 * channel(r) + 0.7152 * channel(g)
            + 0.0722 * channel(b)) < 0.18


def _rgba(hex_colour: str, alpha: float) -> str:
    """`#rrggbb` plus an alpha, as a CSS rgba() string."""
    value = hex_colour.lstrip("#")
    r, g, b = (int(value[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r}, {g}, {b}, {alpha:.2f})"


def system_is_dark() -> bool:
    """
    What the OS is currently set to.

    Qt 6.5+ reports this through styleHints().colorScheme(), and emits
    colorSchemeChanged when the user flips it - so unlike the Tkinter
    attempt, following the system theme does not need a restart.

    Unknown is treated as light rather than guessed at, which is what
    happens on platforms that do not report a preference.
    """
    hints = QGuiApplication.styleHints()
    scheme = getattr(hints, "colorScheme", None)
    if scheme is None:
        return False
    return scheme() == Qt.ColorScheme.Dark


# Which palette the application is currently showing.
#
# The stylesheet knows, because it is rebuilt on every theme change, but a
# model or a delegate colouring a row had no way to find out and so used
# the light theme's green in both. `_restyle()` sets this.
_CURRENT_DARK = False


def qt_palette(dark):
    """
    A `QPalette` to go with the stylesheet.

    The stylesheet names the widgets this interface uses and nothing else,
    so anything it does not name keeps the PLATFORM palette - which follows
    the OS, not this app's Appearance setting. On a machine whose OS is
    light and whose app is set to Dark, that meant white scroll bars in a
    dark window, and the file trees were a white panel until they were
    given a rule of their own.

    Setting the palette fixes the whole class at once rather than one
    widget at a time as each is noticed. The stylesheet still wins wherever
    it applies; this is what everything else falls back to.
    """
    from PySide6.QtGui import QColor, QPalette

    c = palette(dark)
    result = QPalette()
    window, text = QColor(c["window_bg"]), QColor(c["text"])
    base, alt = QColor(c["surface"]), QColor(c["surface_alt"])
    for group in (QPalette.Active, QPalette.Inactive, QPalette.Disabled):
        result.setColor(group, QPalette.Window, window)
        result.setColor(group, QPalette.Base, base)
        result.setColor(group, QPalette.AlternateBase, alt)
        result.setColor(group, QPalette.Button, base)
        result.setColor(group, QPalette.ToolTipBase, base)
        result.setColor(group, QPalette.Highlight, QColor(c["selection"]))
        for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText,
                     QPalette.ToolTipText):
            result.setColor(group, role, text)
        result.setColor(group, QPalette.HighlightedText,
                        QColor(c["selection_text"]))
    # Disabled text has to read as disabled, or every greyed-out control
    # looks live.
    muted = QColor(c["text_muted"])
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        result.setColor(QPalette.Disabled, role, muted)
    return result


def set_dark(dark) -> None:
    """
    Records the appearance in force, for code that PAINTS rather than
    styles - the edited-row marking on the trees and lists.

    Still called `set_dark` and still accepts the old boolean, because
    every caller passes one and renaming it would touch far more than it
    would clarify. What it stores is the appearance's NAME.
    """
    global _CURRENT_DARK
    _CURRENT_DARK = appearance_name(dark)


def is_dark() -> bool:
    """Whether the appearance in force behaves like a dark one."""
    return is_dark_appearance(_CURRENT_DARK)


def current() -> dict:
    """The palette in force, for code that paints rather than styles."""
    return palette(_CURRENT_DARK)


def palette(dark) -> dict:
    """The palette for an appearance, given its name or the old boolean."""
    return APPEARANCES[appearance_name(dark)]


def stylesheet(dark, backdrop=False) -> str:
    """
    `backdrop` True means Windows is compositing Mica or Acrylic behind the
    window, and the interface must let it show.

    This is where a first attempt at Mica went wrong. The rule below used to
    be `QWidget {{ background: <window_bg>; }}` - every widget, including
    the top-level window, painted opaque. DWM was drawing the backdrop
    correctly the whole time; the application was painting over it. Enabling
    transparency in Windows personalisation could not help, because nothing
    translucent ever reached the screen.

    So with a backdrop on, only the surfaces that need to be readable get a
    fill - lists, tables, input controls - and they use a translucent one.
    The window itself paints nothing.
    """
    c = palette(dark)
    kind = material(backdrop)
    if kind != "none":
        # Semi-opaque so text stays legible over whatever is behind the
        # window, while the material still reads as a material.
        alpha = BACKDROP_ALPHA[kind][is_dark_appearance(dark)]
        surface = _rgba(c["surface"], alpha["surface"])
        surface_alt = _rgba(c["surface_alt"], alpha["surface_alt"])
        window_fill = "transparent"
        sidebar = (c["sidebar_bg"] if alpha["sidebar"] >= 1.0
                   else _rgba(c["sidebar_bg"], alpha["sidebar"]))
        # The page area paints NOTHING under a material, and a wash there
        # was a real bug rather than a missed refinement.
        #
        # In a maximised window the client area starts about six rows
        # before DWM stops painting the caption, and DWM composites the
        # caption over whatever is underneath. Where that is nothing, the
        # caption shows through cleanly. Where it is a light wash and the
        # caption is dark, those six rows come out mid-grey - measured on
        # hardware at (139,143,148) between a (27,30,36) caption and a
        # (238,239,238) page, which is a colour that appears nowhere else
        # in the window and reads as the page smearing into the title bar.
        #
        # So the rule is: in the rows the caption can reach, paint the
        # caption's colour or paint nothing. The sidebar paints the
        # caption's colour (it IS `caption_bg`, opaque); the page area
        # paints nothing. Both are then seamless.
        #
        # What light loses is tonal separation between page and panels;
        # what it keeps is the hairline, which is what separates them under
        # a material. Plain has the full layering.
        content = "transparent"
    else:
        surface, surface_alt = c["surface"], c["surface_alt"]
        window_fill, sidebar = c["window_bg"], c["sidebar_bg"]
        content = "transparent"
    return f"""
    QWidget {{
        color: {c['text']};
        font-size: 10pt;
    }}
    QMainWindow, QMainWindow > QWidget {{ background: {window_fill}; }}
    /* The page area, right of the sidebar. Named so it can carry the base
       layer under a backdrop without the top-level window painting - which
       would cover the material outright, and did once. */
    QStackedWidget#ContentArea {{ background: {content}; }}
    QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; }}
    /* The splitter handle, which the default style paints as a filled bar.
       On the plain window that bar is the window colour, so it reads as
       background and is invisible; under Mica and Acrylic the window is
       translucent and the bar is not, so the same widget reads as a solid
       slab laid across the page. One opaque fill cannot be right for both.

       So: no fill at all. The one visible pixel is painted by
       `HairlineHandle` rather than styled here - three CSS attempts each
       put it off-centre or smeared it, see widgets/hairline_splitter.py.
       All that is left for QSS is to stop the default style filling the
       handle. Transparent is what makes it correct under a material:
       whatever is behind the window shows through the gap exactly as it
       does either side of it.

       Deliberately NOT a different colour per material. The Acrylic
       sidebar's contrast cannot be promised, because much of what is
       behind it is the user's wallpaper - so the fix has to be "not a
       slab" rather than "a slab in a better colour". */
    QSplitter {{ background: transparent; }}
    QSplitter::handle {{ background: transparent; image: none; }}
    /* The tab strip gets a surface of its own. Left transparent over an
       extended frame it read as a lighter band across the top of the
       window - the "bleed onto the title bar". */
    QTabWidget::pane {{ background: {surface}; border: 1px solid {c['border']}; }}
    QTabBar {{ background: {surface_alt}; }}
    QTabBar::tab {{
        background: {surface_alt};
        color: {c['text_muted']};
        padding: 6px 14px;
        border: 1px solid {c['border']};
        border-bottom: none;
    }}
    QTabBar::tab:selected {{ background: {surface}; color: {c['text']}; }}
    QLabel[role="muted"]    {{ color: {c['text_muted']}; }}
    /*
      An editing tab's description line. Muted's colour, plus a floor tall
      enough that the language picker and Copy button beside it never
      decide the row's height - see `page_intro`.
    */
    QLabel[role="intro"]    {{ color: {c['text_muted']}; min-height: 30px; }}
    /*
      Three steps, not one grey for everything: the page title at 17pt/700
      in full-strength text, the blurb at 10pt in the muted tone, the body
      at 10pt/normal. Light had the title at 600 against a blurb only
      marginally lighter than it, which on a flat background read as one
      undifferentiated block.
    */
    /*
      `min-height` is doing real work here, not cosmetics.
      
      The heading shares its row with the view toggles and, on three tabs,
      the language picker and Copy button. A row is as tall as its tallest
      child, so those controls decided where the description below them
      started - and the description sat lower on the pages that had them
      than on the pages that did not. Reported as "inconsistent spacing
      between the title and its description".
      
      Giving the heading a floor taller than any of that furniture makes
      the heading itself the tallest child on every page, so the row is one
      height everywhere and the controls cannot move anything.
    */
    QLabel[role="heading"]  {{ font-size: 17pt; font-weight: 700;
                               min-height: 34px;
                               color: {c['text']}; }}
    QLabel[role="ok"]       {{ color: {c['ok']}; }}
    QLabel[role="attention"]{{ color: {c['attention']}; }}
    QLabel[role="danger"]   {{ color: {c['danger']}; }}

    QFrame#Sidebar {{ background: {sidebar}; border: none; }}
    QFrame#Sidebar QLabel {{ background: transparent; color: {c['sidebar_text']}; }}
    QPushButton[role="nav"] {{
        background: transparent;
        color: {c['sidebar_text']};
        border: none;
        text-align: left;
        padding: 9px 18px;
        font-size: 11pt;
    }}
    QPushButton[role="nav"]:hover  {{ color: {c['sidebar_active']}; }}
    QPushButton[role="nav"][active="true"] {{
        color: {c['sidebar_active']};
        font-weight: 600;
    }}
    QPushButton[role="subnav"] {{
        background: transparent;
        color: {c['sidebar_text']};
        border: none;
        border-left: 2px solid transparent;
        text-align: left;
        padding: 5px 18px 5px 26px;
        font-size: 10pt;
    }}
    QPushButton[role="subnav"]:hover {{ color: {c['sidebar_active']}; }}
    QPushButton[role="subnav"][active="true"] {{
        color: {c['sidebar_active']};
        border-left: 2px solid {c['accent']};
    }}
    QFrame#SidebarDivider {{ background: {c['border']}; max-height: 1px; }}

    /*
      QTreeView belongs here and was missing, which cost two faults on the
      Textures and Sounds tabs.

      Without a rule the tree kept the PLATFORM palette rather than this
      one. On a machine whose OS is light and whose app is set to Dark,
      the file tree stayed white while `QWidget`'s `color` above painted
      its text in the dark theme's near-white - light grey on white, which
      is close to unreadable. It looked correct on hardware only because
      the OS happened to agree with the app.

      The selection shape came from the platform too: rounded and inset on
      Windows 11, square and full-width on Fusion, and neither in this
      interface's selection colour. Naming `::item:selected` with a real
      background hands the shape to the box model, so both platforms draw
      the same square bar that `QListWidget` rows already get.
    */
    QTableView, QListWidget {{
        background: {surface};
        alternate-background-color: {surface_alt};
        gridline-color: {c['border']};
        border: 1px solid {c['border']};
        selection-background-color: {c['selection']};
        selection-color: {c['selection_text']};
    }}
    /*
      The file trees get the surface and the border but NOT the selection
      colours, because they paint their own rows - see
      `widgets/marked_tree.py`. Naming `selection-background-color` here
      would put the colour back into the palette's Highlight role, and the
      base style would then draw a second selection across the branch
      column in the platform's own shape: the bar that appeared to the left
      of the pointer row, rounded on its outer corner and square where it
      met the delegate's.
    */
    QTreeView {{
        background: {surface};
        border: 1px solid {c['border']};
    }}
    QHeaderView::section {{
        background: {surface_alt};
        color: {c['text_muted']};
        border: none;
        border-right: 1px solid {c['border']};
        border-bottom: 1px solid {c['border']};
        padding: 5px 8px;
        font-weight: 600;
    }}
    QPushButton {{
        background: {surface};
        border: 1px solid {c['border']};
        border-radius: 3px;
        padding: 5px 14px;
    }}
    QPushButton:hover    {{ border-color: {c['accent']}; }}
    QPushButton:disabled {{ color: {c['text_muted']}; }}
    QComboBox, QLineEdit {{
        background: {surface};
        border: 1px solid {c['border']};
        border-radius: 3px;
        padding: 4px 8px;
    }}
    /*
      QSpinBox is out of the padded rule above and styled here instead.

      Four variants were rendered and compared before settling on this, and
      two earlier attempts shipped wrong:

      - Inheriting `padding: 4px 8px` from the text-field rule squashes the
        native up/down buttons into an unusable sliver, and the number runs
        underneath them. That was the reported bug.
      - Setting `background` or `border` on `::up-button` makes Qt stop
        drawing its own arrows, leaving two blank boxes.
      - Drawing the arrows with the usual CSS zero-size-plus-borders
        triangle fills a black RECTANGLE - Qt's stylesheet engine treats
        those borders as a real box.

      Setting ONLY the width and position of the two buttons keeps Qt's own
      arrows and stacks them, which is what the Tkinter field looks like.
      `padding-right: 20px` reserves the room so the number cannot clip into
      them.
    */
    QSpinBox {{
        background: {surface};
        border: 1px solid {c['border']};
        border-radius: 3px;
        padding: 2px 20px 2px 6px;
    }}
    QSpinBox::up-button {{
        subcontrol-origin: border;
        subcontrol-position: top right;
        width: 16px;
    }}
    QSpinBox::down-button {{
        subcontrol-origin: border;
        subcontrol-position: bottom right;
        width: 16px;
    }}
    QProgressBar {{
        border: 1px solid {c['border']};
        border-radius: 3px;
        text-align: center;
        background: {surface};
    }}
    QGroupBox {{
        border: 1px solid {c['border']};
        border-radius: 3px;
        margin-top: 8px;
        padding-top: 6px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 8px;
        color: {c['text_muted']};
    }}
    QProgressBar::chunk {{ background: {c['accent']}; }}
    """
