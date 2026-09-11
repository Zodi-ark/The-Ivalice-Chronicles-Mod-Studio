"""
The window: sidebar, page stack, theme.

The sidebar survives the rewrite unchanged in shape. Three entries -
General Setup, Edit Game Data, Export Mod - are teaching a first-time modder
what making a mod consists of, and Game Updates sits below a divider because
it is not a step in making one. That is a real information architecture, not
decoration, and Qt offers nothing better.

Only Game Updates is built in this slice. The other three are placeholders,
so the shell can be judged at full size without pretending the pages exist.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import (
    QGuiApplication, QIcon, QKeySequence, QPixmap, QShortcut)
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton,
    QStackedWidget, QTabWidget, QVBoxLayout, QWidget,
)

from .. import paths, ui_settings
from . import theme, win_native
from .widgets.hairline_splitter import set_hairline_colours
from .pages.settings import SettingsPage
from .widgets.actions import ViewToggles

STEPS = ["General Setup", "Edit Game Data", "Export Mod"]
UTILITIES = ["Game Updates", "Settings"]

# The ten Edit Game Data tabs, shown as children of that step in the sidebar
# rather than as a strip across the top of the page.
#
# Measured, at the default 1280 and the 1100 minimum:
#
#   a tab strip needs 904px for these ten labels. Content width is 1060px at
#   1280 and 880px at 1100 - so the strip ALREADY OVERFLOWS at the minimum
#   window size, and an eleventh tab does not fit at either.
#
#   a second navigation column would need ~160px, and it would be the third
#   column before any content: sidebar, tab column, record list, editor.
#   That leaves the editor 460px at 1100, where the widest field row already
#   measures 892px and wraps.
#
#   these rows cost nothing horizontally. The sidebar is already 220px and
#   already there.
EDIT_TABS = [
    "Jobs", "Job Commands", "Abilities", "Items", "Equip Bonus",
    "Poaching", "Treasure Hunter", "Encounters", "Textures", "Sounds",
    # Last, and one entry rather than 550. The tables above have hand-built
    # controls because they are what most mods change; everything else in
    # the game data is reachable through this one searchable page. See
    # pages/data_browser.py for why that is the shape.
    "All Game Data",
    # Beside All Game Data, because it is the page every result opens into.
    # This one answers the other half of "which table do I want" - the half
    # where the person knows the TEXT and not the table. A twelfth row costs
    # nothing here for the reason recorded above: these are sidebar rows,
    # not a strip, and the strip is what could not fit an eleventh.
    "Find Text",
]


class Placeholder(QWidget):
    """
    Stands in for a page that has not been rewritten yet.

    Says so plainly rather than showing an empty pane. A blank tab reads as
    a broken tab, and this project's rule about never claiming more than is
    known applies to the interface's own state as much as to game data.
    """

    def __init__(self, title: str):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        heading = QLabel(title)
        heading.setProperty("role", "heading")
        layout.addWidget(heading)
        note = QLabel(
            "This tab hasn't been rebuilt yet. It still works in the old "
            "interface - run the .pyw launcher for it.")
        note.setProperty("role", "muted")
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch(1)


def application_icon() -> QIcon:
    """
    The tool's own icon, at every size Windows might ask for.

    Built from the PNGs rather than handing Qt the `.ico`: Qt reads a
    multi-size .ico but picks one frame, and a 256px frame scaled down to
    16px for the title bar looks soft. Adding each size separately lets it
    choose the one that fits.

    Returns an empty QIcon if the assets are missing, which leaves the
    platform default rather than failing to start - this is cosmetic.
    """
    icon = QIcon()
    assets = paths.bundled_assets_dir()
    for name in ("icon_48.png", "icon_64.png", "icon_128.png", "icon_256.png"):
        path = assets / name
        if path.exists():
            icon.addFile(str(path))
    return icon


class MainWindow(QMainWindow):
    def __init__(self, compare_page: QWidget, follow_system: bool = True,
                 jobs_page: QWidget | None = None,
                 tab_pages: dict | None = None,
                 step_pages: dict | None = None,
                 review_page: QWidget | None = None):
        """
        `tab_pages` maps an Edit Game Data tab name to its page. Any tab
        without one gets a placeholder, so the shell can be run and looked
        at while the ten are built one at a time - a half-built tab that
        says so is better than one that looks finished and isn't.

        `jobs_page` is the older single-page form, kept so existing callers
        keep working; it is treated as `{"Jobs": page}`.
        """
        super().__init__()
        self.setWindowTitle("The Ivalice Chronicles Mod Studio")
        self.setWindowIcon(application_icon())
        self.resize(1280, 720)
        # Qt can enforce a real minimum, which Tkinter never did. The tab
        # strip on Edit Game Data already spans nearly the full width at
        # 1280, so shrinking below this is not a supported layout.
        self.setMinimumSize(1100, 640)

        saved = ui_settings.load()
        appearance = saved.get("appearance", "system")
        self._backdrop = saved.get("window_backdrop", "mica")
        # An explicit `follow_system=False` (tests, mostly) wins over the
        # stored preference; otherwise the stored one decides.
        self._follow_system = follow_system and appearance == "system"
        # The NAME of the appearance in force, and `_dark` derived from it.
        #
        # `_dark` used to be the whole state, which worked while there were
        # exactly two appearances. Phthalo Green is a third, and it BEHAVES
        # like dark - light text, dark window buttons, dark backdrop alphas -
        # so the flag is still the right thing for everything downstream.
        # What it can no longer do is say WHICH palette to use.
        if self._follow_system:
            self._appearance = "dark" if theme.system_is_dark() else "light"
        elif follow_system:
            self._appearance = appearance
        else:
            self._appearance = "light"
        self._dark = theme.is_dark_appearance(self._appearance)
        self._backdrop_active = False
        # Whether DWM accepted the caption colour. False on anything older
        # than Windows 11 22H2, and everywhere that is not Windows, which
        # is what keeps the glyph rule from being applied to a caption the
        # system is still painting itself.
        self._caption_painted = False
        # The material the stylesheet was last built for, so a change of
        # material always rebuilds it.
        self._material_active = "none"
        self._compare_page = compare_page
        self._nav_buttons = []
        self._tab_buttons = []
        self._active_tab = None

        # Where you have been, and where you are in that list.
        #
        # A location is (step index, tab index or None), which is the whole
        # of this window's navigation state - the sidebar picks a step, and
        # Edit Game Data additionally picks one of ten tabs.
        #
        # `_navigating` stops going back from being recorded as another
        # place you went. Without it the history grows every time you use
        # it and Back never reaches anywhere.
        self._history: list = []
        self._history_pos = -1
        self._navigating = False

        root = QWidget()
        row = QHBoxLayout(root)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        row.addWidget(self._build_sidebar())

        pages = dict(tab_pages or {})
        if jobs_page is not None:
            pages.setdefault("Jobs", jobs_page)

        # Edit Game Data is itself a stack, one entry per tab, switched by
        # the sidebar children. The tabs are pages rather than a widget the
        # page swaps its innards for, so each keeps its own scroll position
        # and selection when you leave and come back.
        self.tab_stack = QStackedWidget()
        for tab in EDIT_TABS:
            self.tab_stack.addWidget(pages.get(tab) or Placeholder(tab))

        # One pair of view toggles for all ten tabs, above the stack.
        #
        # Each page used to carry its own, which put them in three different
        # positions across the ten - their own row on some, sharing the
        # record counter's line on others - so two checkboxes moved every
        # time you changed tab. Making the per-page rows identical was tried
        # and cannot work: the pages have different amounts of content above
        # them, so "the same layout position" is still a different pixel.
        #
        # Above the stack it is the same place by construction, which is
        # what the Tkinter interface does (they live in the step header,
        # outside the tab strip). The pages keep their own instances, hidden
        # - `ViewToggles` broadcasts to every live instance, so page code
        # and tests that read `self.view_toggles.state()` go on working
        # without knowing this one exists.
        edit_area = QWidget()
        edit_column = QVBoxLayout(edit_area)
        # A top margin, because this row is the TOPMOST thing in the client
        # area and had none.
        #
        # Measured: the toggles sat at y=0 of the client while the sidebar's
        # logo sat at y=24. Maximised - which is what most people mean by
        # "fullscreen" - the client area begins directly under the title
        # bar, so two checkboxes with no margin land six pixels below it and
        # read as being IN it. Mica makes that worse rather than causes it:
        # a translucent title bar and content pressed against it blend into
        # each other.
        #
        # This is the actual cause of the "UI extends into the title bar"
        # report, and it is not DWM. The caption inset below is still right
        # for true fullscreen; it was never going to help here, because
        # nothing was overlapping - the gap was simply missing.
        #
        # 20 to match the top margin every page already uses, so the strip
        # above the tabs has the same air as the content under it.
        edit_column.setContentsMargins(0, 20, 0, 0)
        # No spacing. The heading's own `min-height` sets the distance to
        # the content below it, and it has to be the same distance the
        # step pages get from their layout spacing - see theme.py.
        edit_column.setSpacing(0)
        self.view_toggles = ViewToggles()

        # The page title shares the toggles' line.
        #
        # Reported as a wide empty band across the top of every editing
        # tab. Measured on the real window: General Setup's heading sits at
        # y=20 and Export Mod's at y=20, while all ten editing tabs put
        # theirs at y=63 - the stack being 20 (this margin) + 19 (the
        # toggles) + 4 (spacing) + 20 (the page's own margin). Forty-three
        # pixels of nothing, and the tab reading as a different, lower
        # kind of page than the two either side of it.
        #
        # The toggles are right-aligned and the title is left-aligned, so
        # the band was empty for the whole width the title wants. Putting
        # the title there costs no height at all and lands it at y=20 -
        # the same line as General Setup, which is what "the same page
        # family" means.
        #
        # It has to live HERE rather than on the pages: the toggles are
        # above the tab stack, deliberately, so a title inside a page can
        # never reach their line. The pages give up their own heading for
        # it - see `_select_tab`, which sets the text from EDIT_TABS so all
        # ten are right by construction and none can drift from its tab's
        # name.
        #
        # Left margin 24 to line up with the 24 every page's content uses;
        # right margin 0 so the toggles stay exactly where they were.
        title_row = QHBoxLayout()
        title_row.setContentsMargins(24, 0, 0, 0)
        title_row.setSpacing(8)
        self.tab_title = QLabel(EDIT_TABS[0])
        self.tab_title.setProperty("role", "heading")
        title_row.addWidget(self.tab_title)
        title_row.addStretch(1)
        title_row.addWidget(self.view_toggles)
        edit_column.addLayout(title_row)
        edit_column.addWidget(self.tab_stack, 1)

        steps = dict(step_pages or {})
        self.stack = QStackedWidget()
        # Named for the stylesheet: with a backdrop the window paints
        # nothing, so without this the "page background" is whatever the
        # material composites to - near-white in light, which left white
        # panels with nothing to sit above.
        self.stack.setObjectName("ContentArea")
        for title in STEPS:
            if title == "Edit Game Data":
                self.stack.addWidget(edit_area)
            else:
                self.stack.addWidget(steps.get(title) or Placeholder(title))
        # Game Updates holds two things that are genuinely different jobs:
        # seeing what changed between two versions, and deciding what of your
        # mod carries over. Two tabs rather than one crowded page - and only
        # two, so a strip is the right shape here where ten would not be.
        if review_page is not None:
            # Wrapped, so the tab STRIP clears the title bar.
            #
            # A `QTabWidget` puts its tab bar at y=0 of itself, and this one
            # is a step page - so it sat at y=0 of the client area, which
            # maximised is directly under the title bar. That is the same
            # fault the view toggles had, in a different container, and
            # fixing the toggles alone did not touch it: they live inside
            # the Edit Game Data column and this does not.
            #
            # A margin on the wrapper rather than on the tab widget, because
            # `QTabWidget` draws its own frame and insetting the widget
            # would inset the frame with it.
            updates_area = QWidget()
            updates_column = QVBoxLayout(updates_area)
            # Zero, and it has to be zero to be flush in BOTH window
            # states. Measured off hardware, with the page background's
            # first row against the tab strip's first row:
            #
            #     maximised   page at 29, tab at 31   ->  2px gap
            #     windowed    page at 31, tab at 39   ->  8px gap
            #
            # The 8px margin was the same 8px in both, but maximised the
            # caption already covers the client's first six rows, so only 2
            # of it showed. No single margin is flush in both states,
            # because the amount the caption covers is not the same in both
            # states - which is the fault four separate attempts at a
            # magic number kept rediscovering.
            #
            # At zero the strip starts at the client's top edge, so what
            # shows begins exactly where the page background does, in both.
            # Maximised, the strip's top few pixels tuck under the caption;
            # that is its border and empty tab shoulder, and the tab labels
            # sit well clear of it - the same thing a browser does with
            # tabs in its title bar.
            # Set from the window state, not written down here.
            #
            # Three fixed values have now been tried and none can work,
            # because the requirement is not constant. Measured off
            # hardware, the caption reaches into the client area by six
            # rows when the window is MAXIMISED and by none when it is
            # windowed:
            #
            #     maximised   client top 23, page visible from 29
            #     windowed    client top 31, page visible from 31
            #
            # So "flush in both" needs 6 in one state and 0 in the other,
            # and any single number is a gap in one or a clipped tab strip
            # in the other. 20 and 8 gave the gap; 0 and 2 gave the
            # clipping.
            self._updates_column = updates_column
            updates_column.setContentsMargins(0, self._caption_reach(), 0, 0)
            updates_column.setSpacing(0)
            updates = QTabWidget()
            # Review first. Re-applying your own mod to the game you have
            # now is the thing people come to this page for; comparing two
            # game versions is the rarer, more specialised job and it needs
            # two archived versions before it can do anything at all.
            updates.addTab(review_page, "Review Changes")
            updates.addTab(compare_page, "Compare Versions")
            self.updates_tabs = updates
            updates_column.addWidget(updates, 1)
            self.stack.addWidget(updates_area)
        else:
            self.updates_tabs = None
            self.stack.addWidget(compare_page)
        self.settings_page = SettingsPage()
        self.settings_page.appearance_changed.connect(self.set_appearance)
        self.settings_page.backdrop_changed.connect(self.set_backdrop)
        self.stack.addWidget(self.settings_page)
        row.addWidget(self.stack, 1)

        self.setCentralWidget(root)
        # Kept so the caption inset has something to put a margin on.
        self._root = root
        self._caption_inset_applied = 0
        # General Setup, which is where the work starts. This opened on Game
        # Updates for months because the vertical slice built that page first
        # and the line was never revisited - a scaffolding decision that
        # outlived the scaffolding.
        self._select(0)

        # The mouse's back/forward buttons, and the keyboard equivalents
        # every browser and file manager also accepts. Installed on the
        # application because a mouse press is consumed by whatever widget
        # is under the pointer - see `eventFilter`.
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
        back = QShortcut(QKeySequence("Alt+Left"), self)
        back.activated.connect(self.go_back)
        forward = QShortcut(QKeySequence("Alt+Right"), self)
        forward.activated.connect(self.go_forward)
        self.apply_theme()

        # Live OS theme following. The reverted Tkinter theme could not do
        # this - ttk widgets were configured at build time, so a switch left
        # half the window with the old colours until a restart.
        hints = QGuiApplication.styleHints()
        if follow_system and hasattr(hints, "colorSchemeChanged"):
            hints.colorSchemeChanged.connect(self._on_system_theme_changed)

    # -- sidebar ------------------------------------------------------------

    def _build_sidebar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("Sidebar")
        bar.setFixedWidth(220)
        layout = QVBoxLayout(bar)
        layout.setContentsMargins(0, 24, 0, 18)
        layout.setSpacing(2)

        # The project's own mark, not the placeholder snowflake glyph this
        # had. `icon_64.png` is the size the Tkinter sidebar uses.
        logo = QLabel()
        # Kept on the window: `dev/caption_probe.py` measures where this
        # actually lands, which is one of the two widgets reported as
        # overlapping the title bar under Mica.
        self.logo = logo
        logo.setAlignment(Qt.AlignCenter)
        logo_path = paths.bundled_assets_dir() / "icon_64.png"
        pixmap = QPixmap(str(logo_path)) if logo_path.exists() else QPixmap()
        if pixmap.isNull():
            # Cosmetic, so a missing or unreadable file falls back rather
            # than leaving a blank gap where the mark should be.
            logo.setText("\u2748")
            logo.setStyleSheet("font-size: 34pt; color: #c8a44a;")
        else:
            logo.setPixmap(pixmap.scaled(
                56, 56, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        layout.addWidget(logo)
        layout.addSpacing(20)

        for i, title in enumerate(STEPS):
            layout.addWidget(self._nav_button(title, i))
            if title == "Edit Game Data":
                # The ten tabs live here, revealed when the step is
                # selected. Always-visible would make a 14-row sidebar and
                # bury the three-step spine that teaches a newcomer what
                # making a mod consists of; hidden until asked for keeps
                # that spine clean and still puts every tab one click away
                # from anywhere in the tool.
                for j, tab in enumerate(EDIT_TABS):
                    button = QPushButton("   " + tab)
                    button.setProperty("role", "subnav")
                    button.setCursor(Qt.PointingHandCursor)
                    button.clicked.connect(
                        lambda _=False, k=j: self._select_tab(k))
                    button.setVisible(False)
                    self._tab_buttons.append(button)
                    layout.addWidget(button)

        layout.addStretch(1)

        divider = QFrame()
        divider.setObjectName("SidebarDivider")
        divider.setFixedHeight(1)
        layout.addWidget(divider)
        layout.addSpacing(8)

        for j, title in enumerate(UTILITIES):
            layout.addWidget(self._nav_button(title, len(STEPS) + j))

        return bar

    def _nav_button(self, title: str, index: int) -> QPushButton:
        button = QPushButton(title)
        button.setProperty("role", "nav")
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(lambda: self._select(index))
        self._nav_buttons.append(button)
        return button

    def _select(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        self._record_location()
        for i, button in enumerate(self._nav_buttons):
            button.setProperty("active", "true" if i == index else "false")
            button.style().unpolish(button)
            button.style().polish(button)
        editing = STEPS[index] == "Edit Game Data" if index < len(STEPS) else False
        for button in self._tab_buttons:
            button.setVisible(editing)
        if editing and self._active_tab is None:
            self._select_tab(0)

    def open_tab(self, tab_name: str, record_id=None) -> bool:
        """
        Opens an Edit Game Data tab, optionally at a particular record.

        Returns whether it worked, so a caller can say "that tab isn't
        available" rather than appearing to do nothing. A jump that silently
        fails is worse than no jump: the user presses the button, the screen
        does not change, and they conclude the tool is broken.
        """
        if tab_name not in EDIT_TABS:
            return False
        index = EDIT_TABS.index(tab_name)
        page = self.tab_stack.widget(index)
        self._select_tab(index)
        if record_id is None:
            return True
        for method in ("select_record", "load_record", "load_job",
                       "load_command"):
            handler = getattr(page, method, None)
            if handler is not None:
                try:
                    handler(record_id)
                    return True
                except Exception:                             # noqa: BLE001
                    return False
        return True

    def _select_tab(self, index: int) -> None:
        """
        Picks one of the ten Edit Game Data tabs.

        Selecting a tab from anywhere also moves to the Edit Game Data page,
        so the sidebar is a destination list rather than a mode switch - the
        thing a strip cannot do, because a strip is only visible once you
        are already on the page it belongs to.
        """
        self._active_tab = index
        self.tab_stack.setCurrentIndex(index)
        # The heading says what you are editing, not which section you are
        # in. All ten used to read "Edit Game Data", which is already the
        # sidebar section above them - so the most prominent line on the
        # page repeated something the reader could already see and told
        # them nothing about the page they were on.
        #
        # Taken from EDIT_TABS rather than from the page, so the heading
        # and the sidebar entry cannot disagree.
        if 0 <= index < len(EDIT_TABS):
            self.tab_title.setText(EDIT_TABS[index])
        # Which of the three view toggles this tab can actually act on.
        #
        # Asked of the PAGE, not looked up from a list of tab names here.
        # A list in the shell is a second place that has to be edited when
        # a page changes, and the twelve-entry version of exactly that has
        # already been wrong three times in this project. A page that says
        # nothing gets all three, so adding a page needs no change here.
        page = self.tab_stack.widget(index)
        relevant = getattr(page, "view_toggles_used", None)
        self.view_toggles.show_only(*(relevant() if callable(relevant)
                                      else (True, True, True)))
        edit_index = STEPS.index("Edit Game Data")
        if self.stack.currentIndex() != edit_index:
            self._select(edit_index)
        self._record_location()
        for i, button in enumerate(self._tab_buttons):
            button.setProperty("active", "true" if i == index else "false")
            button.style().unpolish(button)
            button.style().polish(button)

    # -- history -------------------------------------------------------------

    def _location(self) -> tuple:
        return (self.stack.currentIndex(), self._active_tab)

    def _record_location(self) -> None:
        """
        Remembers where we are, if it is somewhere new.

        Called from both `_select` and `_select_tab`, and those call each
        other - picking a tab from another step moves the step too - so the
        same location arrives twice. Recording it once means Back does not
        need pressing twice to leave a page.

        Going somewhere new after going Back discards what was ahead, which
        is what a browser does: the forward list belongs to a path you have
        left.
        """
        if self._navigating:
            return
        here = self._location()
        if self._history and self._history[self._history_pos] == here:
            return
        del self._history[self._history_pos + 1:]
        self._history.append(here)
        self._history_pos = len(self._history) - 1

    def _go(self, step: int) -> bool:
        """Moves along the history by `step`, without recording it."""
        target = self._history_pos + step
        if not (0 <= target < len(self._history)):
            return False
        self._history_pos = target
        index, tab = self._history[target]
        self._navigating = True
        try:
            if tab is not None and index == STEPS.index("Edit Game Data"):
                self._select_tab(tab)
            else:
                self._select(index)
        finally:
            self._navigating = False
        return True

    def go_back(self) -> bool:
        return self._go(-1)

    def go_forward(self) -> bool:
        return self._go(1)

    def eventFilter(self, watched, event):                    # noqa: N802
        """
        The mouse's fourth and fifth buttons, as a browser uses them.

        On the application rather than on this window, because a press
        lands on whichever widget is under the pointer - a list, a button,
        a tree - and that widget consumes it before the window ever sees it.
        An application-wide filter sees the press first.

        Only presses from inside this window count, so a modal dialog's
        Back button does not navigate the window behind it.
        """
        if event.type() == QEvent.MouseButtonPress:
            window = watched.window() if hasattr(watched, "window") else None
            if window is self:
                if event.button() == Qt.BackButton:
                    self.go_back()
                    return True
                if event.button() == Qt.ForwardButton:
                    self.go_forward()
                    return True
        return super().eventFilter(watched, event)

    # -- theme --------------------------------------------------------------

    def showEvent(self, event) -> None:
        """
        The backdrop is applied here, not in __init__.

        `winId()` creates a handle, but DWM attributes set before the window
        is actually mapped are unreliable - which is one of the reasons a
        first attempt at Mica appeared to do nothing.
        """
        super().showEvent(event)
        self._apply_backdrop()

    def _apply_backdrop(self) -> None:
        """
        Switches the window material, and repaints BEFORE telling DWM.

        The order is the whole of this method. Switching Acrylic to Mica was
        reported as "all kinds of wrong colours", fixed by changing the
        appearance afterwards - and that second clue is the answer, because
        the appearance path is the same two steps in the opposite order:

            apply_theme      restyle, THEN re-apply the material   works
            set_backdrop     apply the material, THEN restyle      wrong

        With a translucent window, the material is what the surfaces are
        composited over. Telling DWM first swaps out what is behind the
        window while its contents are still painted for the old material,
        and whatever does not happen to repaint keeps the stale blend. The
        stylesheet was never wrong - a probe switching every way round
        found the sheet in force correct every time - which is exactly why
        it took a second report to find.

        So the app repaints for the material it is about to ask for, and
        only then asks. If DWM refuses - a build too old for the attribute -
        it restyles back, which costs one extra pass on machines that were
        never going to get a material anyway.
        """
        wanted = self._backdrop if win_native.is_supported() else "none"

        # 1. Repaint for the material we are about to ask for.
        if wanted != self._material_active:
            self._material_active = wanted
            self._backdrop_active = wanted != "none"
            self._restyle()

        # 2. Now tell DWM. The caption first, so the glyph colour the
        #    materials call sets is chosen against a title bar already ours.
        caption = theme.caption_colours(self._appearance)
        self._caption_painted = win_native.apply_caption_colours(
            self, background=caption["background"], text=caption["text"])
        applied = win_native.apply_window_materials(
            self, dark=self._dark, backdrop=wanted,
            # Only once the caption is actually ours do the glyphs follow
            # it. If painting it failed - a build older than 22H2 - the
            # caption is still the system's and the system's rule applies.
            dark_glyphs=(caption["dark_glyphs"] if self._caption_painted
                         else None))

        # 3. Only if it refused. `is_supported` has already ruled out the
        #    builds that cannot do this at all, so this is the rare path.
        if wanted != "none" and not applied:
            self._material_active = "none"
            self._backdrop_active = False
            self._restyle()

        # Whether or not the flag moved: turning a backdrop off while
        # fullscreen has to drop the inset too.
        self._sync_caption_inset()

    def _caption_reach(self) -> int:
        """
        How far the caption reaches into the client area, right now.

        Zero unless the window is maximised. Maximised, Windows places the
        window past every screen edge by the resize border - 8px on Zodi's
        machine - and the caption is drawn from the frame top, so its
        bottom lands inside the client area rather than above it.

        That offscreen amount is the first quantity in this whole saga that
        is actually MEASURABLE from in here, and it is measured against the
        screen rather than against the frame. The four reverted attempts
        used `frameGeometry() - geometry()`, which the probe showed is 31
        in both the states needing nothing and 0 in the one needing 31 -
        precisely inverted. This is not that number.

        It is not exact either: it reports 8 where the caption was measured
        to reach 6, so a maximised window is left about two pixels shy of
        flush rather than clipped. `dev/caption_probe.py` reads
        `DWMWA_CAPTION_BUTTON_BOUNDS`, which would give the reach directly
        and in client coordinates - that is the number to close the last
        two pixels with, and it has never been wired into anything but the
        probe.
        """
        if not self.isMaximized():
            return 0
        screen = self.screen()
        if screen is None:
            return 0
        return max(0, screen.availableGeometry().top()
                   - self.frameGeometry().top())

    def _sync_updates_inset(self) -> None:
        """Re-applies the reach when the window is maximised or restored."""
        column = getattr(self, "_updates_column", None)
        if column is None:
            return
        reach = self._caption_reach()
        if column.contentsMargins().top() != reach:
            column.setContentsMargins(0, reach, 0, 0)

    def changeEvent(self, event):                           # noqa: N802
        # THE ONLY `changeEvent` ON THIS CLASS. There were two, and Python
        # does not complain about that - the second simply won, so the
        # `_sync_updates_inset()` call below had not run since the day the
        # second one was added and the updates column kept whichever inset
        # it was built with. Found by AST-diffing the class's members, not
        # by reading: two definitions 50 lines apart look like two different
        # methods.
        super().changeEvent(event)
        # Maximise, restore and fullscreen all change how far the caption
        # reaches, so both insets have to follow. A value read once at build
        # time is right in whichever state the window happened to start in
        # and wrong in the other.
        if event.type() == QEvent.WindowStateChange:
            self._sync_updates_inset()
            self._sync_caption_inset()

    def _sync_caption_inset(self) -> None:
        """
        Keeps the content clear of the strip DWM paints the caption on.

        **Only fullscreen, and only with a backdrop**, which is exactly
        what was reported. The probe run on Zodi's machine says why:

            normal      client top - frame top = 31
            maximised   client top - frame top = 31
            fullscreen  client top - frame top =  0

        In the first two Windows has already put the client area 31px below
        the frame, so the caption sits above the content and nothing
        overlaps. In fullscreen the client starts at the very top of the
        screen - while `DwmExtendFrameIntoClientArea(-1, -1, -1, -1)` is
        still in force, because that is applied for mica and acrylic and
        nothing about going fullscreen removes it. So the frame is still
        extended across a client area that no longer leaves it any room,
        and the top 31px of the page are underneath it.

        The logo is the evidence: it sits at client y=24 with height 56, so
        in fullscreen it occupies screen rows 24 to 80 and its top seven
        rows fall inside that strip. That is "the logo area overlaps",
        measured rather than guessed.

        This is NOT the reverted fix. That one used
        `frameGeometry() - geometry()` and applied it always; that number
        is 31 in the two states that need no inset and 0 in the one that
        does, so it pushed content down in the wrong windows and did
        nothing in the right one.
        """
        wanted = 0
        if self._backdrop_active and self.isFullScreen():
            wanted = win_native.caption_inset()
        if wanted == self._caption_inset_applied:
            return
        self._caption_inset_applied = wanted
        margins = self._root.contentsMargins()
        self._root.setContentsMargins(
            margins.left(), wanted, margins.right(), margins.bottom())

    def _restyle(self) -> None:
        # Told before the stylesheet is built, so anything that PAINTS a
        # row - the edited-row marking on the file trees and the list rows -
        # picks the right palette on this same pass.
        theme.set_dark(self._appearance)
        app = QGuiApplication.instance()
        if app is not None:
            # Palette FIRST, then the stylesheet on top of it. The
            # stylesheet names the widgets this interface uses; the palette
            # is what everything it does not name falls back to, which is
            # how scroll bars ended up following the OS instead of the
            # app's own Appearance setting.
            if hasattr(app, "setPalette"):
                app.setPalette(theme.qt_palette(self._appearance))
            app.setStyleSheet(theme.stylesheet(self._appearance,
                                               self._material_active))
            # The splitter handle paints itself, so it cannot pick up
            # `border-color` from the stylesheet the way a styled widget
            # would. Handing the two colours over HERE - beside the
            # stylesheet, from the same palette - is what stops the painted
            # hairline and the styled panel edges drifting to different
            # greys when the appearance changes.
            palette = theme.APPEARANCES[self._appearance]
            set_hairline_colours(palette["border"], palette["accent"])

    def apply_theme(self) -> None:
        self._restyle()
        if hasattr(self._compare_page, "set_dark"):
            self._compare_page.set_dark(self._dark)
        if self.isVisible():
            self._apply_backdrop()

    def set_appearance(self, value: str) -> None:
        """"system", "light" or "dark", from the Settings page."""
        self._follow_system = value == "system"
        if self._follow_system:
            self._appearance = "dark" if theme.system_is_dark() else "light"
        else:
            self._appearance = theme.appearance_name(value)
        self._dark = theme.is_dark_appearance(self._appearance)
        self.apply_theme()

    def set_backdrop(self, value: str) -> None:
        """
        Switches the window material.

        This used to flip `_backdrop_active` first, commented "force a
        restyle". It did the opposite. `_apply_backdrop` restyles when the
        new state DIFFERS from the recorded one, so pre-flipping made them
        match precisely when they should not have:

            Plain -> Acrylic   recorded flips False->True, actual is True,
                               they match, no restyle - nothing happens
            Mica  -> Plain     recorded flips True->False, actual is False,
                               they match, no restyle - the window keeps its
                               transparent stylesheet with no material behind
                               it, which is the washed-out look

        Changing light/dark afterwards appeared to "fix" it only because
        `apply_theme` restyles unconditionally. The material was never the
        problem; the bookkeeping was.
        """
        self._backdrop = value
        self._apply_backdrop()

    def _on_system_theme_changed(self, *_args) -> None:
        # Only when actually following the system. Pinning an appearance -
        # Phthalo Green especially, which the OS has no notion of - must
        # not be undone by the user changing their Windows theme.
        if not self._follow_system:
            return
        wanted = "dark" if theme.system_is_dark() else "light"
        if wanted != self._appearance:
            self._appearance = wanted
            self._dark = theme.is_dark_appearance(wanted)
            self.apply_theme()

    def set_dark(self, dark: bool) -> None:
        """Explicit override, for testing and for a future preference."""
        self._follow_system = False
        self._appearance = theme.appearance_name(dark)
        self._dark = theme.is_dark_appearance(self._appearance)
        self.apply_theme()
