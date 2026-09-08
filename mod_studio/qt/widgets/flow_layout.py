"""
A layout that puts its children in a row and wraps when the row runs out.

Qt has no such layout built in, and its absence is what made the Export
page's "Where it goes" box 715px wide at its narrowest. Four buttons in a
`QHBoxLayout` cannot wrap, so the box's minimum width was the sum of all
four - and because that box sat in the left half of a `QSplitter`, it forced
the split to 715/259 at the documented 1100px minimum and squeezed Mod
Contents until its text clipped.

The fix belongs in the layout rather than in the page: shortening the
labels, dropping a button, or stacking them two-by-two would each have
traded something real away to work around a layout that simply could not
wrap. A row that wraps costs nothing at 1500, where all four still fit on
one line and the page looks exactly as it did.

`heightForWidth` is the whole mechanism. A layout that wraps has no single
height - it has a height *given a width* - so it answers that question
instead, and `hasHeightForWidth` tells Qt to ask.
"""
from __future__ import annotations

from PySide6.QtCore import QMargins, QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QLayout, QSizePolicy


class FlowLayout(QLayout):
    """Left-to-right, wrapping when the next item will not fit."""

    def __init__(self, parent=None, margin: int = 0, spacing: int = 6):
        super().__init__(parent)
        self._items: list = []
        self.setContentsMargins(QMargins(margin, margin, margin, margin))
        self.setSpacing(spacing)

    # -- QLayout plumbing --------------------------------------------------

    def addItem(self, item) -> None:                          # noqa: N802
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):                             # noqa: N802
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int):                             # noqa: N802
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):                            # noqa: N802
        # Neither. The row is as wide as its contents need and no wider -
        # an expanding flow layout would stretch to fill the pane and take
        # the space back from whatever it was meant to give it to.
        return Qt.Orientations(Qt.Orientation(0))

    # -- the wrapping itself -----------------------------------------------

    def hasHeightForWidth(self) -> bool:                      # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:              # noqa: N802
        return self._layout(QRect(0, 0, width, 0), apply=False)

    def setGeometry(self, rect: QRect) -> None:               # noqa: N802
        super().setGeometry(rect)
        self._layout(rect, apply=True)

    def sizeHint(self) -> QSize:                              # noqa: N802
        # The natural size is one unwrapped row, so a window wide enough
        # gets the single line the page was designed with.
        margins = self.contentsMargins()
        width = height = 0
        for item in self._items:
            hint = item.sizeHint()
            width += hint.width() + self.spacing()
            height = max(height, hint.height())
        width = max(0, width - self.spacing())
        return QSize(width + margins.left() + margins.right(),
                     height + margins.top() + margins.bottom())

    def minimumSize(self) -> QSize:                           # noqa: N802
        # The WIDEST SINGLE ITEM, not the sum of them. This is the whole
        # point: a row of four buttons can be as narrow as its longest
        # button, because the other three wrap underneath.
        margins = self.contentsMargins()
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        return QSize(size.width() + margins.left() + margins.right(),
                     size.height() + margins.top() + margins.bottom())

    def _layout(self, rect: QRect, apply: bool) -> int:
        """
        Places the items, or measures where they would go.

        Returns the total height. `apply=False` is the measuring pass that
        `heightForWidth` needs - it must not move anything, because Qt calls
        it while deciding on a geometry it has not committed to.
        """
        margins = self.contentsMargins()
        area = rect.adjusted(margins.left(), margins.top(),
                             -margins.right(), -margins.bottom())
        x, y = area.x(), area.y()
        line_height = 0

        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + self.spacing()
            if next_x - self.spacing() > area.right() and line_height > 0:
                # Does not fit on this line, and this line has something on
                # it already - so wrap. The second condition matters: an
                # item wider than the whole area would otherwise wrap
                # forever onto empty lines.
                x = area.x()
                y = y + line_height + self.spacing()
                next_x = x + hint.width() + self.spacing()
                line_height = 0
            if apply:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())

        return y + line_height - rect.y() + margins.bottom()
