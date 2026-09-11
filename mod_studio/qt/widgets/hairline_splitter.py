"""
A `QSplitter` whose handle is one pixel, painted at the handle's own centre.

**Why this is not a stylesheet.** Three attempts were made in CSS and all
three were wrong, each in a way that only a rendered screenshot showed:

1. `border-left` on the handle lands at its LEFT edge, so the line had 4px
   of gap on one side and 17px on the other.
2. A `qlineargradient` with stops a fraction apart is INTERPOLATED, so a
   band meant to be one pixel painted as a soft six-pixel smear.
3. `border-left` with equal margins moved it, but not to the middle -
   measured at 7px and 11px, because the handle's own width is not the sum
   of the CSS terms and the arithmetic that assumed it was came out two
   pixels short.

The third failure is the useful one: it was tuned by measurement, verified,
and STILL wrong on the next screenshot, because the number it was tuned
against depends on the widget's real width at the real font and DPI. A
constant cannot track that.

Painting at `rect().center()` cannot be off-centre. There is no arithmetic
to get wrong: whatever width the handle ends up, the line is in the middle
of it. That is the whole reason this file exists.

The colours come from the theme through `set_hairline_colours`, called when
the stylesheet is applied. A custom-painted widget does not receive QSS
`border-color`, so the two have to be handed over explicitly rather than
left to drift apart - and there is a check that they match the palette.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QSplitter, QSplitterHandle


# The width of the grab area. Wide enough to hit with a mouse without
# aiming, which is the whole reason the handle is not one pixel wide as
# well as one pixel visible.
HANDLE_WIDTH = 11

_LINE = QColor("#3d4046")
_HOVER = QColor("#d8b662")


def set_hairline_colours(line: str, hover: str) -> None:
    """
    Tell every handle what colour to paint, from the active palette.

    Module level rather than per widget because the appearance is
    application-wide - one theme is active at a time - and a handle created
    after a theme change would otherwise be painted in the old one.
    """
    global _LINE, _HOVER
    _LINE = QColor(line)
    _HOVER = QColor(hover)


def hairline_colours() -> tuple:
    """The colours currently in use, so a check can compare them."""
    return _LINE.name(), _HOVER.name()


class HairlineHandle(QSplitterHandle):
    """One pixel, in the middle, with a hover state."""

    def __init__(self, orientation, parent):
        super().__init__(orientation, parent)
        self.setAttribute(Qt.WA_Hover, True)

    def paintEvent(self, event):                              # noqa: N802
        painter = QPainter(self)
        colour = _HOVER if self.underMouse() else _LINE
        painter.setPen(colour)
        rect = self.rect()
        if self.orientation() == Qt.Horizontal:
            # `center().x()` and not `width() // 2`: on an odd width those
            # differ by a pixel, and a pixel is the entire subject here.
            x = rect.center().x()
            # Inset top and bottom so the line stops short of whatever it
            # runs between, rather than butting into it.
            painter.drawLine(x, rect.top() + 2, x, rect.bottom() - 2)
        else:
            y = rect.center().y()
            painter.drawLine(rect.left() + 2, y, rect.right() - 2, y)

    def enterEvent(self, event):                              # noqa: N802
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event):                              # noqa: N802
        super().leaveEvent(event)
        self.update()


class HairlineSplitter(QSplitter):
    """A `QSplitter` that makes `HairlineHandle`s."""

    def __init__(self, orientation=Qt.Horizontal, parent=None):
        super().__init__(orientation, parent)
        self.setHandleWidth(HANDLE_WIDTH)

    def createHandle(self):                                   # noqa: N802
        return HairlineHandle(self.orientation(), self)
