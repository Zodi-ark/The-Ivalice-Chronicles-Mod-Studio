"""
The picture on the UI Layouts page: a screen as the game draws it, with the
selected box outlined, that you can click on to pick a box and drag to move
it.

The drawing itself happens elsewhere (`qt/layout_preview.py`) and arrives as
an image plus a list of where every box landed. This widget only fits the
image to its space - aspect kept, never magnified past 1:1, the way the
Textures preview fits - turns a click into "which box is that", and a drag
into "move that box by so much of its own position".

**A drag.** A press on the picked box - wherever it is drawn, even over
boxes inside it, so a group picked from the list can be dragged - holds it;
a press anywhere else picks the box under the pointer, as a click always
has, and holds that. Moved further than the system's drag distance with the
button held, the press becomes a drag of the held box; let go without
moving, it is a click, and picks the box under the pointer, as before. The
pointer's movement is turned from screen
pixels into the picture's (the fit), then back through everything above the
box (`DrawnBox.parent` - a group scaled 2x moves its boxes 2 pixels for
each 1 of position), rounded to the whole numbers a position holds. The
outline follows live, showing where the box will land; the picture itself is
redrawn once, on release, because a redraw takes up to 585 ms on the
game's biggest screens (median 8 ms, 90th percentile 75 ms, measured with
every sheet already in memory). Esc during a drag puts it back.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QApplication, QSizePolicy, QWidget

#: Boxes that put something on screen. A click lands on the front-most of
#: these first; groups and pieces are only chosen when nothing drawn is
#: under the pointer, or they would swallow every click inside them.
DRAWN_KINDS = ("Image", "Ninegrid", "Text", "Rect")

SELECTION_COLOUR = QColor(255, 204, 51)
#: Every part's outline on a texture sheet, behind the picked one's.
PART_COLOUR = QColor(90, 200, 255, 170)


class LayoutCanvas(QWidget):
    box_clicked = Signal(str)
    #: A box dragged: its key, and how far its position moves (whole numbers,
    #: in the box's own position's units).
    box_dragged = Signal(str, int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(False)
        # Keyboard focus on a click, so Esc reaches a drag.
        self.setFocusPolicy(Qt.ClickFocus)
        self.image = None
        self.boxes = []
        self.file = ""
        self.selected = ""
        self.message = ""
        #: Off for a screen that can't be edited here (a mod's own copy).
        self.draggable = False
        #: Outline every box, not only the picked one: a texture sheet with
        #: all its parts shown.
        self.outline_all = False
        self._press = None          # where the button went down, widget pixels
        self._record = None         # the DrawnBox a drag would move
        self._click = ""            # what a press on the picked box picks if it stays a click
        self.dragging = False
        self.drag_move = (0, 0)     # the position change the drag stands at

    # -- content ---------------------------------------------------------------

    def set_drawing(self, image, boxes, file: str) -> None:
        if file != self.file:
            self.cancel_drag()
        self.image, self.boxes, self.file = image, list(boxes), file
        self.message = ""
        self.update()

    def clear(self, message: str = "") -> None:
        self.cancel_drag()
        self.image, self.boxes, self.file = None, [], ""
        self.message = message
        self.update()

    def set_message(self, message: str) -> None:
        """Shown over the picture - "Drawing..." while a drawing is on its way."""
        self.message = message
        self.update()

    def set_selected(self, key: str) -> None:
        self.selected = key or ""
        self.update()

    def selected_rects(self) -> list:
        """
        Where the selected box was drawn, in canvas pixels; one per time it
        appears. During a drag, where it will be once dropped - each
        appearance moved through its own parents, which need not be the
        dragged one's.
        """
        rects = []
        for b in self.boxes:
            if b.file != self.file or b.key != self.selected:
                continue
            if self.dragging:
                dx, dy = self._on_canvas(b, *self.drag_move)
                rects.append(b.rect.translated(dx, dy))
            else:
                rects.append(b.rect)
        return rects

    # -- dragging ----------------------------------------------------------------

    @staticmethod
    def _on_canvas(record, dx: float, dy: float) -> tuple:
        """A change of the box's position, as a movement on the canvas."""
        m = record.parent
        return (dx * m.m11() + dy * m.m21(), dx * m.m12() + dy * m.m22())

    @staticmethod
    def _in_position(record, cx: float, cy: float):
        """A movement on the canvas, as a change of the box's position; None if its parents flatten it."""
        m = record.parent
        det = m.m11() * m.m22() - m.m12() * m.m21()
        if abs(det) < 1e-9:
            return None
        return ((cx * m.m22() - cy * m.m21()) / det, (cy * m.m11() - cx * m.m12()) / det)

    def _record_under(self, key: str, canvas_point: QPointF):
        """The drawn record of `key` the pointer is on - a piece placed twice has two."""
        mine = [b for b in self.boxes if b.file == self.file and b.key == key]
        for b in reversed(mine):
            if b.rect.contains(canvas_point):
                return b
        return mine[0] if mine else None

    def cancel_drag(self) -> None:
        """Puts a drag back: nothing moves, the outline returns."""
        was = self.dragging
        self._press, self._record, self._click = None, None, ""
        self.dragging = False
        self.drag_move = (0, 0)
        self.unsetCursor()
        if was:
            self.update()

    # -- geometry ----------------------------------------------------------------

    def _fit(self) -> tuple:
        """
        (scale, left, top) placing the image in the widget: centred across,
        but against the top - directly under the "Show the screen" row and
        level with the box list, rather than floating half-way down a tall
        pane with a gap above it.
        """
        if self.image is None or self.image.isNull():
            return 1.0, 0.0, 0.0
        w, h = self.image.width(), self.image.height()
        scale = min(self.width() / w, self.height() / h, 1.0)
        left = (self.width() - w * scale) / 2
        return scale, left, 0.0

    def to_canvas(self, point: QPointF) -> QPointF:
        scale, left, top = self._fit()
        return QPointF((point.x() - left) / scale, (point.y() - top) / scale)

    def box_at(self, canvas_point: QPointF) -> str:
        """
        The box a click at this canvas point means, or "".

        In three passes, front to back each time: something drawn plainly;
        then something drawn as an effect - the screen filters and glows,
        which blend over whole screens and would otherwise catch every
        click on the tavern; then groups and pieces.
        """
        for kinds, effects in ((DRAWN_KINDS, False), (DRAWN_KINDS, True), (None, True)):
            for b in reversed(self.boxes):
                if not b.visible or not b.rect.contains(canvas_point):
                    continue
                if kinds is not None and (b.kind not in kinds or (b.effect and not effects)):
                    continue
                return b.owner
        return ""

    # -- Qt ---------------------------------------------------------------------

    def sizeHint(self) -> QSize:                                   # noqa: N802
        return QSize(640, 360)

    def minimumSizeHint(self) -> QSize:                            # noqa: N802
        return QSize(240, 135)

    def mousePressEvent(self, event):                              # noqa: N802
        if event.button() != Qt.LeftButton or self.image is None:
            return super().mousePressEvent(event)
        self.cancel_drag()
        point = self.to_canvas(event.position())
        key = self.box_at(point)
        on_picked = self.draggable and self.selected and any(
            b.file == self.file and b.key == self.selected and b.rect.contains(point)
            for b in self.boxes)
        if on_picked:
            # Held for a drag; picked on release if it stays a click.
            self._click = key
            key = self.selected
        elif key:
            self.box_clicked.emit(key)
        if key and self.draggable:
            self._press = QPointF(event.position())
            self._record = self._record_under(key, point)
        event.accept()

    def mouseMoveEvent(self, event):                               # noqa: N802
        if self._press is None or self._record is None \
                or not event.buttons() & Qt.LeftButton:
            return super().mouseMoveEvent(event)
        moved = QPointF(event.position()) - self._press
        if not self.dragging:
            if moved.manhattanLength() < QApplication.startDragDistance():
                return
            if self._record.key != self.selected:
                # The press picked something the page did not take up.
                self.cancel_drag()
                return
            self.dragging = True
            self.setCursor(Qt.ClosedHandCursor)
        scale, _left, _top = self._fit()
        change = self._in_position(self._record, moved.x() / scale, moved.y() / scale)
        if change is None:
            self.cancel_drag()
            return
        self.drag_move = (round(change[0]), round(change[1]))
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event):                            # noqa: N802
        if event.button() == Qt.LeftButton and not self.dragging and self._click:
            # A press on the picked box that never became a drag: a click.
            key = self._click
            self.cancel_drag()
            self.box_clicked.emit(key)
            event.accept()
            return
        if event.button() != Qt.LeftButton or not self.dragging:
            self.cancel_drag()
            return super().mouseReleaseEvent(event)
        key, (dx, dy) = self._record.key, self.drag_move
        self.cancel_drag()
        if dx or dy:
            self.box_dragged.emit(key, dx, dy)
        event.accept()

    def keyPressEvent(self, event):                                # noqa: N802
        if event.key() == Qt.Key_Escape and self.dragging:
            self.cancel_drag()
            event.accept()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event):                                   # noqa: N802
        p = QPainter(self)
        p.fillRect(self.rect(), self.palette().window())
        if self.image is not None and not self.image.isNull():
            scale, left, top = self._fit()
            target = QRectF(left, top, self.image.width() * scale, self.image.height() * scale)
            p.setRenderHint(QPainter.SmoothPixmapTransform, True)
            p.drawImage(target, self.image)
            if self.outline_all:
                thin = QPen(PART_COLOUR)
                thin.setWidthF(1.0)
                p.setPen(thin)
                p.setBrush(Qt.NoBrush)
                for b in self.boxes:
                    if b.file == self.file and b.key != self.selected:
                        p.drawRect(QRectF(left + b.rect.x() * scale, top + b.rect.y() * scale,
                                          max(1.0, b.rect.width() * scale),
                                          max(1.0, b.rect.height() * scale)))
            pen = QPen(SELECTION_COLOUR)
            pen.setWidthF(2.0)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            for r in self.selected_rects():
                drawn = QRectF(left + r.x() * scale, top + r.y() * scale,
                               max(2.0, r.width() * scale), max(2.0, r.height() * scale))
                # Kept to the picture: a box bigger than the screen - the
                # tavern scaled up - is outlined along the picture's edges,
                # not by a stray line on the page beneath it.
                shown = drawn.intersected(target.adjusted(1, 1, -1, -1))
                if not shown.isEmpty():
                    p.drawRect(shown)
        if self.message:
            p.setPen(self.palette().text().color())
            p.drawText(self.rect().adjusted(12, 12, -12, -12),
                       int(Qt.AlignLeft | Qt.AlignTop) | int(Qt.TextWordWrap), self.message)
        p.end()
