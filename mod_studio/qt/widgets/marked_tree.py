"""
The file tree used by Textures and Sounds, painted deterministically.

Both pages hang off `models.texture_tree.TextureTreeModel`, so both had the
same faults and both are fixed here rather than twice.

Row painting is done here rather than left to the platform style, and that
is the whole point of the module. Three things went wrong when it was left
to the style, and all three were invisible in the development environment
because Fusion draws them differently from Windows 11:

- **The selected row's text was unreadable.** The model returns
  `Qt.ForegroundRole` - the edited-row green - for a replaced file, and
  that colour survived the selection, leaving dark green text sitting on
  the dark blue selection bar.
- **A white focus rectangle** was drawn around the current row, boxing the
  text.
- **The tint stopped short of the left edge**, because a tree's delegate
  paints the ITEM, which starts after the indentation and the expand arrow.

A delegate that decides its own background and its own text colour has no
opinion left to disagree with, so all three are settled by construction and
the result is the same under every platform style.

The colours come from `theme.current()` rather than from `constants`. The
constants are the Tkinter interface's and that is a LIGHT theme; used
unchanged in dark mode they filled the Textures tab of a mod with 3,708
replacements with a wall of bright green.
"""
from __future__ import annotations

from PySide6.QtCore import QModelIndex, QRectF, Qt
from PySide6.QtGui import (
    QBrush, QColor, QFontMetrics, QPainter, QPalette, QPen)
from PySide6.QtWidgets import (
    QStyle, QStyleOptionViewItem, QStyledItemDelegate, QTreeView)

from .. import theme

# Asked of the model for column 0 of a row: True when the row stands for
# something the mod replaces.
#
# A role rather than "does this index have a BackgroundRole" because the
# view should not have to infer intent from a colour. A model that one day
# wants to colour a row for some other reason would silently start getting
# the edited-row treatment.
MARKED_ROLE = Qt.UserRole + 2

# Breathing room at the left of the text, and the corner radius of the
# selection bar. Both small: a heavy pill on every row of a ten-thousand
# row tree is decoration competing with the thing being read.
TEXT_PAD = 4
CORNER = 3


class MarkedRowDelegate(QStyledItemDelegate):
    """
    Draws the TEXT of a row and nothing else.

    Every background - the marking, the hover, the selection - is filled by
    `MarkedTreeView.drawRow` across the whole row. Splitting the two is
    what produced the reported "rounded on the left, square on the right":
    the view painted the branch column in the platform's shape while the
    delegate painted the item in its own, and the seam fell where the text
    began. One rectangle, drawn in one place, cannot disagree with itself.
    """

    def paint(self, painter, option, index):
        colours = theme.current()
        marked = bool(index.data(MARKED_ROLE))
        selected = bool(option.state & QStyle.State_Selected)

        # Text colour: the selection wins, always.
        #
        # This is the fault that made a selected replaced file unreadable.
        # The model returns the marking green through `Qt.ForegroundRole`,
        # and on the selection bar that is 1.02:1 - invisible. The delegate
        # is the only place that knows which background it is drawing on.
        if selected:
            pen = QColor(colours["selection_text"])
        elif marked:
            pen = QColor(colours["edited_fg"])
        else:
            pen = QColor(colours["text"])

        font = option.font
        font.setBold(bool(marked))
        painter.save()
        painter.setFont(font)
        painter.setPen(QPen(pen))
        rect = option.rect.adjusted(TEXT_PAD, 0, -TEXT_PAD, 0)
        text = str(index.data(Qt.DisplayRole) or "")
        painter.drawText(rect, Qt.AlignVCenter | Qt.AlignLeft,
                         QFontMetrics(font).elidedText(
                             text, Qt.ElideRight, rect.width()))
        painter.restore()


class MarkedTreeView(QTreeView):
    """A `QTreeView` that fills its own rows, edge to edge, in one shape."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setItemDelegate(MarkedRowDelegate(self))
        # Hover has to be tracked for the pointer row to update at all.
        self.setMouseTracking(True)
        self._hovered = -1
        # The base style paints the row selection itself, across the branch
        # column, before the delegate runs - that is the bar that appeared
        # to the LEFT of the pointer row with a rounded outer corner and a
        # square inner one. Made invisible so `drawRow` below is the only
        # thing drawing a background; the colours are painted by hand from
        # the theme, so nothing is lost by emptying these.
        self._silence_base_selection()

    def _silence_base_selection(self) -> None:
        """
        Empties every role the base style would fill a row with.

        `QTreeView::drawRow` draws the row background itself, through
        `PE_PanelItemViewRow`, BEFORE the delegate runs - so a fill made
        here was painted over by whatever the palette said. Highlight alone
        was not enough: a selected row survived, because Highlight was
        already empty, while a hovered or merely alternate row was covered
        by AlternateBase and looked as though the hover had never drawn.

        With all three empty, `drawRow` below is the only thing that paints
        a row, which is the whole point - one fill, one shape, one span.
        The tree's own background still comes from the stylesheet, which
        paints the viewport rather than the rows.
        """
        palette = self.palette()
        empty = QColor(0, 0, 0, 0)
        for group in (QPalette.Active, QPalette.Inactive, QPalette.Disabled):
            for role in (QPalette.Highlight, QPalette.Base,
                         QPalette.AlternateBase):
                palette.setColor(group, role, empty)
        self.setPalette(palette)

    def changeEvent(self, event):                           # noqa: N802
        """
        Re-empties it whenever the style changes.

        Setting it once in `__init__` was not enough: applying a stylesheet
        to the QApplication re-polishes every widget and restores the
        palette, so a tree built before the theme was applied - which is
        every tree, since the stylesheet goes on after the pages are
        built - got its Highlight back and drew the second selection again.
        """
        super().changeEvent(event)
        if event.type() in (event.Type.StyleChange, event.Type.PaletteChange,
                            event.Type.ThemeChange):
            if self.palette().color(QPalette.Highlight).alpha() != 0:
                self._silence_base_selection()

    # -- hover ---------------------------------------------------------------

    def mouseMoveEvent(self, event):                        # noqa: N802
        row = self.indexAt(event.position().toPoint())
        key = row.row() if row.isValid() else -1
        if key != self._hovered or not row.isValid():
            self._hovered = key
            self._hovered_index = row
            self.viewport().update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):                            # noqa: N802
        self._hovered = -1
        self._hovered_index = QModelIndex()
        self.viewport().update()
        super().leaveEvent(event)

    def _is_marked(self, index: QModelIndex) -> bool:
        if not index.isValid():
            return False
        model = index.model()
        if model is None:
            return False
        # Column 0 always, because that is the column the model answers for
        # and the only one these two pages have.
        return bool(model.data(index.sibling(index.row(), 0), MARKED_ROLE))

    def drawRow(self, painter, option, index):              # noqa: N802
        """
        Fills the WHOLE row, then lets the tree draw arrows and text on it.

        `Qt.BackgroundRole` reaches the delegate, and the delegate paints
        the ITEM - which in a tree begins after the indentation and the
        expand arrow. So a replaced file three folders deep got a tinted
        bar starting some sixty pixels in with bare background to its left,
        and the hover and selection the style drew covered a different span
        again. Filling here covers branch column, arrow and text alike, and
        it is the only fill, so there is one shape and one span.
        """
        colours = theme.current()
        selection = self.selectionModel()
        selected = selection is not None and selection.isSelected(index)
        hovered = (not selected
                   and getattr(self, "_hovered_index", QModelIndex()) == index)
        rect = QRectF(option.rect).adjusted(0, 1, 0, -1)

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)
        # The alternating band, drawn here because nothing else may.
        #
        # `alternate-background-color` is deliberately absent from the
        # stylesheet's QTreeView rule: with it there, QStyleSheetStyle
        # repainted the band across the ITEM after this fill had run,
        # leaving the hover and the selection showing in the indentation
        # and stopping dead where the item began. That was the reported
        # seam, and removing the property is what closes it - the band is
        # not lost, it is drawn on the line below across the whole row.
        if option.features & QStyleOptionViewItem.Alternate:
            painter.fillRect(option.rect,
                             QBrush(QColor(colours["surface_alt"])))
        if self._is_marked(index) and not selected and not hovered:
            # A band, not a pill: a run of replaced files should read as a
            # block of work rather than a stack of separate buttons.
            painter.fillRect(option.rect,
                             QBrush(QColor(colours["edited_bg"])))
        if hovered:
            painter.setBrush(QBrush(QColor(colours["hover"])))
            painter.drawRoundedRect(rect, CORNER, CORNER)
        if selected:
            painter.setBrush(QBrush(QColor(colours["selection"])))
            painter.drawRoundedRect(rect, CORNER, CORNER)
        painter.restore()

        super().drawRow(painter, option, index)
