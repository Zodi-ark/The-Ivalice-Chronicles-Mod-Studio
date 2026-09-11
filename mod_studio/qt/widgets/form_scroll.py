"""
The scroll area every editing form sits in, whose content keeps its width
when the scrollbar appears.

### The fault

`QScrollArea` with `setWidgetResizable(True)` sizes its widget to the
VIEWPORT, and the viewport is 14px narrower once a vertical scrollbar is
needed. Every elastic control in the form therefore resizes the moment the
content grows past the page. On Job Commands, expanding "Other fields" took
the Description and Description (alternate) boxes from 848px to 837px and
reflowed the text under the reader's eye.

This is not a Job Commands bug. Nine editing pages built the same three
lines by hand, and Jobs escapes it today only because its form always
overflows, so the bar is always there. The page that happens to sit either
side of the threshold is the page that shows the fault.

### Why the width is taken from the SCROLL AREA and not the viewport

`self.width()` does not change when the bar appears - only the viewport's
does. So capping the widget at

    self.width() - 2 * frameWidth() - scrollbar extent

gives a number that is the same with the bar and without it, and there is
no feedback loop: the widget's width depends on the window, the window does
not depend on the bar.

The obvious alternative - `Qt.ScrollBarAlwaysOn` - also holds the content
still, and was rejected on the render. When the content FITS, Qt draws a
handle that fills the whole track: a bright full-height slab down a dark
page, on every editing tab, permanently. Reserving the space without
demanding the bar be painted costs a 14px strip of background instead.

The two other candidates were measured and are recorded here so they are
not tried again:

- **Hugging the text body** (`ColumnFormBody(hug_contents=True)`, which
  fixed exactly this fault for the slot columns) caps a column at its
  widest child's size hint. That hint is built from MINIMUMS: 627px against
  a body of 1368, so the Description box would have gone from 848px to
  about 310. Right for a column of dropdowns, wrong for prose.
- **A maximum width on the boxes** so the last 14px lands in slack. Fixes
  the size it is tuned at and nothing else: across 240 window sizes the bar
  toggled at 42 of them, and with a 90-character cap 18 still moved the
  box - every one at a width between 1400 and 1800 where the cap does not
  bind. A fix that only holds where the reporter happened to be sitting.

The extent is asked of the STYLE rather than written down, for the reason
`hairline_splitter.py` records at length: a constant cannot track the real
widget at the real font and DPI.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QScrollArea, QStyle, QWidget


class FormScrollArea(QScrollArea):
    """
    A resizable scroll area that keeps a constant content width.

    `reserve_scrollbar=False` is for the areas whose vertical bar is turned
    off entirely - there is no bar to reserve room for, and reserving it
    would take 14px off the content for nothing.
    """

    def __init__(self, parent: QWidget = None, reserve_scrollbar: bool = True):
        super().__init__(parent)
        self._reserve_scrollbar = bool(reserve_scrollbar)
        self.setWidgetResizable(True)
        # Vertical only. The form must fit the width it is given; if it ever
        # does not, that is a layout bug to fix rather than something to
        # scroll sideways past.
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    # -- the reservation ----------------------------------------------------

    def scrollbar_extent(self) -> int:
        """The width this style gives a vertical scrollbar."""
        if not self._reserve_scrollbar:
            return 0
        return self.style().pixelMetric(QStyle.PM_ScrollBarExtent, None, self)

    def content_width(self) -> int:
        """
        How wide the widget is allowed to be, bar or no bar.

        Read by the checks, so the number they assert against is the one the
        widget is actually given rather than a second copy of this sum.
        """
        return max(1, self.width() - 2 * self.frameWidth()
                   - self.scrollbar_extent())

    def _apply_reservation(self) -> None:
        widget = self.widget()
        if widget is None or not self._reserve_scrollbar:
            return
        wanted = self.content_width()
        # Only when it changed. Setting a maximum width inside a resize is a
        # layout request, and setting one unconditionally on every resize is
        # how a layout loop starts - the same guard `ColumnFormBody._sync_height`
        # carries, for the same reason.
        if widget.maximumWidth() != wanted:
            widget.setMaximumWidth(wanted)

    # -- QScrollArea --------------------------------------------------------

    def setWidget(self, widget: QWidget) -> None:              # noqa: N802
        super().setWidget(widget)
        self._apply_reservation()

    def resizeEvent(self, event) -> None:                      # noqa: N802
        super().resizeEvent(event)
        self._apply_reservation()

    def showEvent(self, event) -> None:                        # noqa: N802
        # The frame width and the style's scrollbar extent are both only
        # right once the widget has a style and a parent, and a page built
        # before it is shown gets its first resize with neither. Without
        # this the reservation is applied from the pre-show numbers and the
        # first paint is 14px wider than every one after it.
        super().showEvent(event)
        self._apply_reservation()
