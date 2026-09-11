"""
A form that reflows into columns when the window is wide enough.

### The measurement this exists to answer

`dev/audit_form_density.py` found that a 2560px monitor showed exactly as
many fields as an 1100px one - 75 of 106 either way. Every pixel of extra
width became empty space: about 1479px per page at 1440p, roughly 74% of
the form, while 31 fields sat below the fold. The form was a single column
of rows about 322-523px wide inside a viewport 2002px wide.

Nothing was wrong with the rows. The container was a `QVBoxLayout`, which
has exactly one column and no opinion about how much room it was given.

### Why not `FlowLayout`

`flow_layout.py` already wraps, and it was read first. It is the wrong tool
here, for a reason worth writing down so nobody tries it again:

**A flow layout gives every item its own natural width.** That is right for
the four buttons it was written for, whose widths differ and which nothing
needs to line up with. It is wrong for form rows, because the first thing a
person does with a form is run their eye down the left edge of the values
looking for the field they came for. Under a flow layout a 322px numeric
row and a 523px row with a note sit side by side, the next line starts at a
different offset again, and the labels and boxes form no edge at all. Rows
also cannot then expand to fill the leftover, so the waste this was built
to remove would come back as a ragged margin on the right.

So: uniform column widths, and columns that **fill** the available space
rather than centring a fixed column in it.

### How the column count is decided

Not by a hardcoded number of columns - by how wide a usable column is:

    columns = (available + gap) // (min_column_width + gap)

and then the columns divide the full width between them, which is what
takes the wasted space to roughly zero rather than merely reducing it.

`min_column_width` is **not a constant**, and that is the point of the
design. A row showing its note needs room for the note; a row without one
does not. So the caller sets it from what the rows actually contain, and
the existing "Hide field notes" toggle changes it. That gives the toggle a
second, honest meaning - hiding the notes buys columns - instead of the
alternative, which was to special-case notes inside the layout and have the
two disagree later.

### Fill order is column-major

Items go down the first column, then down the second - newspaper order, not
left-to-right.

Sequential entry forms should not do this: Wroblewski's objection to
multi-column forms is that a zigzag path through name/address/phone causes
people to miss fields and make errors. These are not entry forms. They are
property editors - twenty-five stats belonging to one job, already
displayed in a fixed order the person may half-remember - and the task is
hunting for one field, not filling in all of them. Column-major keeps a
field at the same relative depth it was at before, so "Move is near the
bottom" stays true. Left-to-right would move it to a different place at
every window width.

Columns are balanced by **height**, not by item count, because a
three-line description and a spin box are not the same size and splitting
25 rows into 8/8/9 by counting produces visibly uneven columns as soon as
one row is taller than the rest.

### The scroll-area wrinkle

A layout that wraps has no single height - it has a height *given a width* -
so `heightForWidth` is the whole mechanism, exactly as in `flow_layout.py`.
`QScrollArea` with `setWidgetResizable(True)` does not reliably ask its
widget that question, so `ColumnFormBody` answers it by setting its own
minimum height whenever its width changes. Without that the form is given
its one-column height at three columns and scrolls through empty space.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QEvent, QRect, QSize
from PySide6.QtWidgets import QLayout, QSizePolicy, QWidget

#: A column wide enough for `[x] Label(200) [value] note`, with the note
#: readable. Measured, not chosen: a field row's checkbox, its 200px label
#: column and a spin box come to 322px, and the notes on the Jobs page hint
#: at up to 523px in total. At this width a three-column form at 1440p
#: leaves each note about 334px, which is MORE than the 222px a note gets
#: today at the documented 1100px minimum - so notes end up better off than
#: the width people already accept, not worse.
DEFAULT_MIN_COLUMN_WIDTH = 520

#: With notes hidden a row needs only its checkbox, label and value, so the
#: columns can be much narrower and there can be many more of them.
NARROW_MIN_COLUMN_WIDTH = 340

#: Horizontal gap between columns. Wider than the 2px between rows, because
#: the gap is the only thing separating one column's notes from the next
#: column's checkboxes.
COLUMN_GAP = 20


class ColumnFormLayout(QLayout):
    """Uniform-width columns, filled top-to-bottom, count set by width."""

    def __init__(self, parent=None, min_column_width: int = DEFAULT_MIN_COLUMN_WIDTH,
                 spacing: int = 2, column_gap: int = COLUMN_GAP,
                 max_columns: int = 0, hug_contents: bool = False):
        super().__init__(parent)
        self._items: list = []
        self._min_column_width = int(min_column_width)
        self._column_gap = int(column_gap)
        # A ceiling on the column count, 0 meaning "as many as fit".
        #
        # For PROSE. The reflow is right for a form of short values - a spin
        # box does not read better for being 800px wide - but a description
        # is the opposite case: its readable length IS its width, and a
        # 261-character job description in a 190px column shows about 75
        # characters of itself. `max_columns=1` gives such a section the
        # full width of the page and lets the reflow go on doing its job in
        # the numeric sections beside it.
        #
        # Deliberately a real cap rather than an enormous `min_column_width`,
        # which would have the same effect at today's window sizes and
        # silently stop working on a wider one.
        self._max_columns = max(0, int(max_columns))
        # Columns no wider than the widest thing in them.
        #
        # Normally a column form SHARES the available width equally, which
        # is right when the rows use it - a prose column wants every pixel.
        # It is wrong when the children have a natural width and stop there:
        # two slot sections in a 1368px body were given 674px each while
        # needing about 530, so 282px of nothing sat between the last "Edit"
        # button of one column and the first label of the next.
        #
        # Hugging also makes the layout deaf to small width changes, which
        # fixes a second complaint by itself: a scrollbar appearing took
        # 14px off the viewport and every dropdown in the form visibly
        # resized. With the columns at their natural width the 14px comes
        # off the slack instead.
        self._hug_contents = bool(hug_contents)
        self._columns = 1
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(spacing)

    # -- QLayout plumbing ---------------------------------------------------

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
        from PySide6.QtCore import Qt
        return Qt.Orientations(Qt.Orientation(0))

    # -- the reflow ---------------------------------------------------------

    def set_min_column_width(self, width: int) -> None:
        """
        Changes how wide a column has to be before another one is allowed.

        Called when the notes toggle changes, because a row with a note
        needs more room than a row without one. `invalidate()` is required:
        without it Qt keeps the cached size hint and the form keeps the
        column count it had before the toggle.
        """
        width = int(width)
        if width == self._min_column_width:
            return
        self._min_column_width = width
        self.invalidate()

    @property
    def columns(self) -> int:
        """How many columns the last layout pass used. Read by the audit."""
        return self._columns

    def hasHeightForWidth(self) -> bool:                      # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:              # noqa: N802
        return self._layout(QRect(0, 0, width, 0), apply=False)

    def setGeometry(self, rect: QRect) -> None:               # noqa: N802
        super().setGeometry(rect)
        self._layout(rect, apply=True)

    def sizeHint(self) -> QSize:                              # noqa: N802
        margins = self.contentsMargins()
        width = self._min_column_width
        height = 0
        for item in self._live_items():
            width = max(width, item.sizeHint().width())
            height += item.sizeHint().height() + self.spacing()
        return QSize(width + margins.left() + margins.right(),
                     max(0, height - self.spacing())
                     + margins.top() + margins.bottom())

    def minimumSize(self) -> QSize:                           # noqa: N802
        # The widest single row, NOT the sum - one column is always a legal
        # arrangement, so the form can be as narrow as its widest row.
        margins = self.contentsMargins()
        width = 0
        for item in self._live_items():
            width = max(width, item.minimumSize().width())
        return QSize(width + margins.left() + margins.right(),
                     margins.top() + margins.bottom())

    # -- internals ----------------------------------------------------------

    def _live_items(self) -> list:
        """
        The items that are actually on screen.

        A row hidden by "Hide unknown fields" must not hold a slot in a
        column, or the toggle would leave gaps where the hidden rows were
        and the balancing would work from heights nobody can see.
        """
        return [item for item in self._items if not item.isEmpty()]

    def _height_of(self, item, width: int) -> int:
        if item.hasHeightForWidth():
            return item.heightForWidth(width)
        return item.sizeHint().height()

    def _layout(self, rect: QRect, apply: bool) -> int:
        margins = self.contentsMargins()
        area = rect.adjusted(margins.left(), margins.top(),
                             -margins.right(), -margins.bottom())
        items = self._live_items()
        if not items:
            self._columns = 1
            return margins.top() + margins.bottom()

        available = max(1, area.width())
        gap = self._column_gap
        columns = max(1, (available + gap) // (self._min_column_width + gap))
        columns = min(columns, len(items))
        if self._max_columns:
            columns = min(columns, self._max_columns)
        if apply:
            # ONLY on the applying pass. `heightForWidth` is a question -
            # "how tall would you be at this width" - and Qt asks it with
            # widths it has not committed to, including the minimum. When
            # the measuring pass also recorded the answer, the layout
            # reported one column while displaying three, and the audit
            # dutifully printed the one. A measurement that records itself
            # is the same fault as a probe that measures itself.
            self._columns = columns
        column_width = (available - gap * (columns - 1)) // columns
        if self._hug_contents and columns > 1:
            # NOT floored at `_min_column_width`. That number is the
            # threshold for allowing a second column at all - "do not split
            # into columns narrower than this" - and using it as the hug
            # floor too kept the columns at 660px when their contents wanted
            # 530, which is the gap this option exists to close. The widest
            # child's own hint is by definition wide enough for the child.
            widest = max(item.sizeHint().width() for item in items)
            column_width = max(1, min(column_width, widest))

        heights = [self._height_of(item, column_width) for item in items]
        spacing = self.spacing()

        if columns == 1:
            assignment = [0] * len(items)
        else:
            total = sum(heights) + spacing * (len(items) - 1)
            target = math.ceil(total / columns)
            assignment = []
            column = 0
            used = 0
            for index, height in enumerate(heights):
                remaining_items = len(items) - index
                remaining_columns = columns - column
                # The last condition stops a tall row early in the list from
                # filling every column and leaving the final one empty:
                # never move on if doing so would leave a later column with
                # nothing to put in it.
                #
                # `>=`, not `>`. With two items and two columns - a tall
                # Abilities section and a collapsed R/S/M one - the strict
                # form read "1 > 1" and refused to advance, so the pair
                # stacked in column zero while the layout reported two
                # columns and the second stood empty. Moving the LAST item
                # into the LAST column leaves nothing behind it, which is
                # precisely the case the guard should allow.
                if (column < columns - 1 and used > 0
                        and used + height > target
                        and remaining_items >= remaining_columns - 1):
                    column += 1
                    used = 0
                assignment.append(column)
                used += height + spacing

        tops = [area.y()] * columns
        for index, item in enumerate(items):
            column = assignment[index]
            x = area.x() + column * (column_width + gap)
            y = tops[column]
            if apply:
                item.setGeometry(QRect(x, y, column_width, heights[index]))
            tops[column] = y + heights[index] + spacing

        tallest = max(tops) - spacing
        return tallest - rect.y() + margins.bottom()


class ColumnFormBody(QWidget):
    """
    A widget whose rows reflow into columns, safe to put in a scroll area.

    Exists because `QScrollArea` with `setWidgetResizable(True)` sizes its
    widget from `sizeHint()` and does not consult `heightForWidth`. A form
    laid out in three columns is a third as tall as its hint says, so the
    scroll area would scroll through two thirds of nothing - the form would
    be denser and the scrolling would not improve, which is the one outcome
    this whole change is meant to avoid.

    `resizeEvent` answers the question the scroll area does not ask.
    """

    def __init__(self, parent=None,
                 min_column_width: int = DEFAULT_MIN_COLUMN_WIDTH,
                 spacing: int = 2, margins: tuple = (0, 0, 0, 0),
                 max_columns: int = 0, hug_contents: bool = False):
        super().__init__(parent)
        self.form = ColumnFormLayout(self, min_column_width=min_column_width,
                                     spacing=spacing, max_columns=max_columns,
                                     hug_contents=hug_contents)
        self.form.setContentsMargins(*margins)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)

    def add_row(self, widget: QWidget) -> None:
        # Watched, so hiding a row collapses the space it held.
        #
        # `_live_items` already skips hidden rows, so the LAYOUT was right -
        # but the body's minimum height is cached from the last
        # `heightForWidth`, and nothing recomputed it when a row's
        # visibility changed. Hiding a Comment row left a row-shaped gap
        # where it had been, which reads as the toggle half-working.
        #
        # Done here rather than asked of each page: three pages own column
        # bodies and a fourth will, and "remember to invalidate" is the kind
        # of instruction that gets followed twice out of three times.
        widget.installEventFilter(self)
        self.form.addWidget(widget)

    def eventFilter(self, watched, event) -> bool:            # noqa: N802
        if event.type() in (QEvent.Show, QEvent.Hide, QEvent.ShowToParent,
                            QEvent.HideToParent):
            self.form.invalidate()
            self.updateGeometry()
            self._sync_height()
        return super().eventFilter(watched, event)

    def set_min_column_width(self, width: int) -> None:
        self.form.set_min_column_width(width)
        self._sync_height()

    @property
    def columns(self) -> int:
        return self.form.columns

    def sizeHint(self) -> QSize:                              # noqa: N802
        """
        The height for THIS width, not the height of one column.

        The layout's own `sizeHint` is the unwrapped height, the way
        `FlowLayout`'s is - fine for a wrapping row of buttons, wrong here.
        A parent layout reading it sizes the form as if it were one column,
        so a three-column form is given three times the height it needs and
        the scroll area scrolls through two thirds of nothing. The form
        would be denser and the scrolling would not improve, which is the
        one outcome this whole change exists to avoid.
        """
        width = self.width()
        if width <= 0:
            return self.form.sizeHint()
        return QSize(width, self.form.heightForWidth(width))

    def minimumSizeHint(self) -> QSize:                       # noqa: N802
        width = self.width()
        minimum = self.form.minimumSize()
        if width <= 0:
            return minimum
        return QSize(minimum.width(), self.form.heightForWidth(width))

    def resizeEvent(self, event) -> None:                     # noqa: N802
        super().resizeEvent(event)
        self._sync_height()

    def _sync_height(self) -> None:
        width = self.width()
        if width <= 0:
            return
        wanted = self.form.heightForWidth(width)
        # Only when it actually changed. Setting it unconditionally inside a
        # resize triggers another resize, and Qt will happily run that loop
        # until the frame is dropped.
        if wanted != self.minimumHeight():
            self.setMinimumHeight(wanted)
            # The hint above is width-dependent, so the parent layout has
            # to be told to ask again. Without this the form reflows and
            # the space reserved for it does not.
            self.updateGeometry()
