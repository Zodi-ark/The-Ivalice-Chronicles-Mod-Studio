"""
The Event Editor's nodes: the strip of wired cards under the map, and the
list of nodes to add on the left. Both in chaiNNer's style as the second
mock-up took it (chaiNNer, GPL-3.0, studied from its screenshots and its
node and node list code, nothing copied), and drawn as `event_editor2.png`
draws them (Zodi, 19 October: the page should match the mock-up):

- **A card**: a band in its color, fading across, a line of the full color
  under it, its name in capitals (SPEAK, WALK, TURN, or the kind) and its
  number at the right; its title and a line of what it does; a dot and its
  status at the foot ("Playing" in gold, what is wrong in red). The node
  playing is outlined in gold, one with something wrong in red. A block of
  moves that run together is drawn as a stack of cards.
- **Wires** between the cards, gold up to the node playing, each row's last
  wired round to the next row's first.
- **The list**: the favourites as chips two to a row, then each kind, the
  first open and the others closed to a line saying how many nodes it has
  ("10 nodes, show them"); a search opens every kind with a match. The
  favourites close as a kind does, and a right click on a node adds it to
  them or takes it out (Zodi, 19 October: "I can not collapse the favorites
  like I can for Talk, Units, or Camera. Also I can not right click on the
  nodes in favorites ... This should be a feature"); the page keeps them for
  next time (`favourites_changed`).

**Not a free canvas.** An event plays in order, and the order is what a
beginner needs to see, so the cards are laid in rows in the order they
play, each row's last wired to the next row's first. A card is moved by
dragging it between two others, and a node from the list is added the
same way, or by a double click (after the node picked).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QMimeData, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QDrag, QFont, QFontMetricsF, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMenu, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from .. import theme
from ..widgets.layout_settle import retire
from . import event_words as words

#: A node carried by a drag from the list: its entry's key, or "ready:" and a ready-made's.
MIME = "application/x-mod-studio-event-node"
CARD_W, CARD_H = 172.0, 96.0
GAP_X, GAP_Y = 26.0, 22.0
MARGIN = 12.0
BAND_H = 22.0
#: How far each card of a stack's back sits from the one in front.
STACK_STEP = 4.0
#: The band's color at its left and its right: the full color this much over the card's.
BAND_LEFT, BAND_RIGHT = 0.58, 0.17
#: The words of the node list, and its foot.
FAVOURITES = "Favourites"
SHOW_THEM, HIDE_THEM = "{count} nodes, show them", "{count} nodes, hide them"
ADD_FAVOURITE, REMOVE_FAVOURITE = "Add to Favourites", "Remove from Favourites"
NO_FAVOURITES = "Right click a node to add it here."
LIST_FOOT = "Drag a node into the row below, or double click it to add it after the one picked."
READY_FOOT = "Drag one into the row below, or double click it to add it after the node picked."


def show_menu(menu: QMenu, at) -> None:
    """Opens a right click's menu where the click was (a suite puts its own in its place)."""
    menu.exec(at)


@dataclass
class Card:
    """One node as the strip draws it: its kind, its title and line, what is
    wrong with it, and its band's words and color (`event_words.band_words`)."""
    kind: str
    title: str
    detail: str
    problem: str = ""
    band: str = ""
    colour: str = ""
    stacked: bool = False


def _colour(name: str) -> QColor:
    return QColor(theme.current()[name])


def gold() -> QColor:
    return _colour("accent")


def problem_red() -> QColor:
    return _colour("danger")


def fine_green() -> QColor:
    return _colour("ok")


def mixed(colour: QColor, under: QColor, share: float) -> QColor:
    """`colour` laid over `under` at `share` (0 none, 1 whole)."""
    return QColor(round(under.red() + (colour.red() - under.red()) * share),
                  round(under.green() + (colour.green() - under.green()) * share),
                  round(under.blue() + (colour.blue() - under.blue()) * share))


def band_ink(band: QColor, alpha: int = 255) -> QColor:
    """The words on a band: white on a dark one (the dark theme's), near black on
    a light one (the light theme's, where the band is its color over white)."""
    light = 0.299 * band.red() + 0.587 * band.green() + 0.114 * band.blue() > 150
    ink = QColor(30, 32, 36) if light else QColor(255, 255, 255)
    ink.setAlpha(alpha)
    return ink


class NodeStrip(QWidget):
    """The nodes in the order they play, wired (see the module's notes)."""

    picked = Signal(int)
    play_from = Signal(int)
    #: A card dragged to stand before another: (node, before).
    moved = Signal(int, int)
    #: A node of the list dropped before card `before`: (entry key, before).
    dropped = Signal(str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cards: list = []
        self.playing = -1
        self.chosen = -1
        self.setAcceptDrops(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._press: Optional[tuple] = None
        self._drop_at: Optional[int] = None
        self.setMinimumHeight(int(CARD_H + 2 * MARGIN))

    # -- content ---------------------------------------------------------------------

    def set_cards(self, cards: list) -> None:
        self.cards = list(cards)
        self.chosen = min(self.chosen, len(self.cards) - 1)
        # As tall as its rows now, so the scroll area around it scrolls to
        # its last card at once (Zodi, 22 October's afternoon: no scroll bar
        # and no wheel until the nodes' pane was dragged to another size).
        self._fit_height()
        self.updateGeometry()
        self.update()

    def set_playing(self, index: int) -> None:
        if index != self.playing:
            self.playing = index
            self.update()

    def set_chosen(self, index: int) -> None:
        if index != self.chosen:
            self.chosen = index
            self.update()

    # -- layout ----------------------------------------------------------------------

    def per_row(self, width: Optional[float] = None) -> int:
        width = float(self.width() if width is None else width)
        return max(1, int((width - 2 * MARGIN + GAP_X) // (CARD_W + GAP_X)))

    def card_rect(self, index: int, width: Optional[float] = None) -> QRectF:
        per = self.per_row(width)
        row, column = divmod(index, per)
        return QRectF(MARGIN + column * (CARD_W + GAP_X), MARGIN + row * (CARD_H + GAP_Y), CARD_W, CARD_H)

    def heightForWidth(self, width: int) -> int:                     # noqa: N802
        rows = max(1, -(-len(self.cards) // self.per_row(width)))
        return int(2 * MARGIN + rows * CARD_H + (rows - 1) * GAP_Y)

    def hasHeightForWidth(self) -> bool:                              # noqa: N802
        return True

    def sizeHint(self) -> QSize:                                      # noqa: N802
        return QSize(int(6 * (CARD_W + GAP_X)), self.heightForWidth(max(1, self.width())))

    def resizeEvent(self, event):                                     # noqa: N802
        super().resizeEvent(event)
        self._fit_height()

    def _fit_height(self) -> None:
        """Its least height: its rows' at its width (`heightForWidth`), which the scroll area around it reads
        for its scroll bar (it reads a widget's least size, not `heightForWidth`)."""
        wanted = self.heightForWidth(self.width())
        if self.minimumHeight() != wanted:
            self.setMinimumHeight(wanted)

    def index_at(self, point: QPointF) -> int:
        for index in range(len(self.cards)):
            if self.card_rect(index).contains(point):
                return index
        return -1

    def gap_at(self, point: QPointF) -> int:
        """Where a dropped node would go: before the card under or after `point`, or at the end."""
        best, best_distance = len(self.cards), None
        for index in range(len(self.cards) + 1):
            if index < len(self.cards):
                rect = self.card_rect(index)
                spot = QPointF(rect.left() - GAP_X / 2, rect.center().y())
            else:
                rect = self.card_rect(index - 1) if self.cards else QRectF(MARGIN, MARGIN, CARD_W, CARD_H)
                spot = QPointF(rect.right() + GAP_X / 2, rect.center().y())
            distance = (spot.x() - point.x()) ** 2 + 4 * (spot.y() - point.y()) ** 2
            if best_distance is None or distance < best_distance:
                best, best_distance = index, distance
        return best

    # -- painting ----------------------------------------------------------------------

    def paintEvent(self, event):                                      # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        dark = theme.is_dark()
        dots = QColor(255, 255, 255, 22) if dark else QColor(0, 0, 0, 26)
        p.setPen(Qt.NoPen)
        p.setBrush(dots)
        step = 18
        for y in range(6, self.height(), step):
            for x in range(6, self.width(), step):
                p.drawEllipse(QPointF(x, y), 1.0, 1.0)
        self._paint_wires(p)
        for index, card in enumerate(self.cards):
            self._paint_card(p, index, card)
        if self._drop_at is not None:
            self._paint_drop(p, self._drop_at)
        p.end()

    def _wire_colour(self, index: int) -> QColor:
        """The wire into card `index`: gold where the event has played past it."""
        return gold() if 0 <= index <= self.playing else _colour("border")

    def _paint_wires(self, p: QPainter) -> None:
        for index in range(1, len(self.cards)):
            a, b = self.card_rect(index - 1), self.card_rect(index)
            colour = self._wire_colour(index)
            p.setPen(QPen(colour, 2.2))
            p.setBrush(Qt.NoBrush)
            start = QPointF(a.right(), a.center().y())
            end = QPointF(b.left(), b.center().y())
            path = QPainterPath(start)
            if abs(a.center().y() - b.center().y()) < 1:
                path.lineTo(end)
            else:
                # The end of a row to the start of the next: round the right edge and back.
                right = a.right() + GAP_X / 2
                mid_y = a.bottom() + GAP_Y / 2
                left = MARGIN - 6.0
                path.cubicTo(QPointF(right + 8, start.y()), QPointF(right + 8, mid_y), QPointF(right - 6, mid_y))
                path.lineTo(QPointF(left + 6, mid_y))
                path.cubicTo(QPointF(left - 8, mid_y), QPointF(left - 8, end.y()), end)
            p.drawPath(path)
            for point in (start, end):
                p.setPen(QPen(QColor(20, 20, 20, 160), 1))
                p.setBrush(colour)
                p.drawEllipse(point, 3.6, 3.6)

    def card_colour(self, card: Card) -> QColor:
        return QColor(card.colour or words.KIND_COLOURS.get(card.kind, words.KIND_COLOURS["other"]))

    def _paint_card(self, p: QPainter, index: int, card: Card) -> None:
        rect = self.card_rect(index)
        colour = self.card_colour(card)
        surface = _colour("surface")
        border = _colour("border")
        chosen = index == self.chosen
        playing = index == self.playing
        edge = gold() if (chosen or playing) else (problem_red() if card.problem else border)
        if card.stacked:
            # The cards behind: the instructions that run together.
            for depth in (2, 1):
                back = rect.translated(STACK_STEP * depth, -STACK_STEP * depth)
                p.setPen(QPen(border, 1.0))
                p.setBrush(mixed(surface, _colour("window_bg"), 0.6 + 0.2 * (2 - depth)))
                p.drawRoundedRect(back, 7, 7)
        p.setPen(QPen(edge, 2.2 if (chosen or playing or card.problem) else 1.0))
        p.setBrush(surface)
        p.drawRoundedRect(rect, 7, 7)
        band = QRectF(rect.left() + 1, rect.top() + 1, rect.width() - 2, BAND_H)
        gradient = QLinearGradient(band.topLeft(), band.topRight())
        gradient.setColorAt(0.0, mixed(colour, surface, BAND_LEFT))
        gradient.setColorAt(1.0, mixed(colour, surface, BAND_RIGHT))
        # Rounded at the top, square where the band meets the card below it.
        path = QPainterPath()
        path.setFillRule(Qt.WindingFill)
        path.addRoundedRect(band, 6, 6)
        path.addRect(QRectF(band.left(), band.center().y(), band.width(), band.height() / 2))
        p.setPen(Qt.NoPen)
        p.setBrush(gradient)
        p.drawPath(path.simplified())
        p.fillRect(QRectF(band.left(), band.bottom() - 1.5, band.width(), 1.5), colour)
        font = QFont(self.font())
        font.setPixelSize(10)
        font.setBold(True)
        p.setFont(font)
        left = mixed(colour, surface, BAND_LEFT)
        p.setPen(band_ink(left))
        label = card.band or words.KIND_NAMES.get(card.kind, card.kind).upper()
        p.drawText(band.adjusted(8, 0, -8, 0), int(Qt.AlignVCenter | Qt.AlignLeft), label)
        p.setPen(band_ink(mixed(colour, surface, BAND_RIGHT), 190))
        p.drawText(band.adjusted(8, 0, -8, 0), int(Qt.AlignVCenter | Qt.AlignRight), str(index + 1))
        title_font = QFont(self.font())
        title_font.setPixelSize(13)
        title_font.setBold(True)
        p.setFont(title_font)
        p.setPen(_colour("text"))
        metrics = QFontMetricsF(title_font)
        inner = rect.adjusted(9, BAND_H + 6, -9, -6)
        p.drawText(QRectF(inner.left(), inner.top(), inner.width(), 18), int(Qt.AlignLeft | Qt.AlignVCenter),
                   metrics.elidedText(card.title, Qt.ElideRight, inner.width()))
        detail_font = QFont(self.font())
        detail_font.setPixelSize(11)
        p.setFont(detail_font)
        p.setPen(_colour("text_muted"))
        metrics = QFontMetricsF(detail_font)
        p.drawText(QRectF(inner.left(), inner.top() + 19, inner.width(), 16), int(Qt.AlignLeft | Qt.AlignVCenter),
                   metrics.elidedText(card.detail, Qt.ElideRight, inner.width()))
        status, dot = (("Playing", gold()) if playing else
                       (card.problem, problem_red()) if card.problem else ("", fine_green()))
        p.setPen(Qt.NoPen)
        p.setBrush(dot)
        spot = QPointF(inner.left() + 3, inner.bottom() - 7)
        p.drawEllipse(spot, 3.0, 3.0)
        if status:
            p.setPen(dot)
            p.drawText(QRectF(inner.left() + 11, inner.bottom() - 15, inner.width() - 11, 16),
                       int(Qt.AlignLeft | Qt.AlignVCenter),
                       metrics.elidedText(status, Qt.ElideRight, inner.width() - 11))

    def _paint_drop(self, p: QPainter, gap: int) -> None:
        if gap < len(self.cards):
            rect = self.card_rect(gap)
            x = rect.left() - GAP_X / 2
        elif self.cards:
            rect = self.card_rect(gap - 1)
            x = rect.right() + GAP_X / 2
        else:
            rect = QRectF(MARGIN, MARGIN, CARD_W, CARD_H)
            x = rect.left()
        p.setPen(QPen(gold(), 3.0))
        p.drawLine(QPointF(x, rect.top() - 4), QPointF(x, rect.bottom() + 4))

    # -- the mouse ---------------------------------------------------------------------

    def mousePressEvent(self, event):                                 # noqa: N802
        if event.button() != Qt.LeftButton:
            return
        index = self.index_at(event.position())
        self._press = (event.position(), index) if index >= 0 else None
        if index >= 0:
            self.set_chosen(index)
            self.picked.emit(index)

    def mouseMoveEvent(self, event):                                  # noqa: N802
        if self._press is None or not event.buttons() & Qt.LeftButton:
            return
        start, index = self._press
        if (event.position() - start).manhattanLength() < 8:
            return
        self._press = None
        drag = QDrag(self)
        data = QMimeData()
        data.setData(MIME, f"card:{index}".encode())
        drag.setMimeData(data)
        drag.exec(Qt.MoveAction)

    def mouseReleaseEvent(self, event):                               # noqa: N802
        self._press = None

    def mouseDoubleClickEvent(self, event):                           # noqa: N802
        index = self.index_at(event.position())
        if index >= 0:
            self.play_from.emit(index)

    def dragEnterEvent(self, event):                                  # noqa: N802
        if event.mimeData().hasFormat(MIME):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):                                   # noqa: N802
        if event.mimeData().hasFormat(MIME):
            self._drop_at = self.gap_at(event.position())
            self.update()
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):                                  # noqa: N802
        self._drop_at = None
        self.update()

    def dropEvent(self, event):                                       # noqa: N802
        self._drop_at = None
        self.update()
        if not event.mimeData().hasFormat(MIME):
            return
        what = bytes(event.mimeData().data(MIME)).decode()
        gap = self.gap_at(event.position())
        event.acceptProposedAction()
        self.drop(what, gap)

    def drop(self, what: str, gap: int) -> None:
        """A card moved to `gap`, or a node of the list added there."""
        if what.startswith("card:"):
            index = int(what.split(":", 1)[1])
            if gap not in (index, index + 1):
                self.moved.emit(index, gap)
        else:
            self.dropped.emit(what, gap)


class NodeBand(QWidget):
    """The big node's band: as a card's, across the top of the node shown on
    the right, its name at the left and which node of how many at the right."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.label, self.right, self.colour = "", "", QColor(words.KIND_COLOURS["other"])
        self.setFixedHeight(30)

    def set_words(self, label: str, right: str, colour: str) -> None:
        self.label, self.right, self.colour = label, right, QColor(colour)
        self.update()

    def paintEvent(self, event):                                      # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect())
        surface = _colour("surface")
        gradient = QLinearGradient(rect.topLeft(), rect.topRight())
        gradient.setColorAt(0.0, mixed(self.colour, surface, BAND_LEFT))
        gradient.setColorAt(1.0, mixed(self.colour, surface, BAND_RIGHT))
        path = QPainterPath()
        path.setFillRule(Qt.WindingFill)
        path.addRoundedRect(rect, 6, 6)
        path.addRect(QRectF(rect.left(), rect.center().y(), rect.width(), rect.height() / 2))
        p.setPen(Qt.NoPen)
        p.setBrush(gradient)
        p.drawPath(path.simplified())
        p.fillRect(QRectF(rect.left(), rect.bottom() - 1.5, rect.width(), 1.5), self.colour)
        font = QFont(self.font())
        font.setPixelSize(11)
        font.setBold(True)
        p.setFont(font)
        p.setPen(band_ink(mixed(self.colour, surface, BAND_LEFT)))
        p.drawText(rect.adjusted(12, 0, -12, 0), int(Qt.AlignVCenter | Qt.AlignLeft), self.label)
        p.setPen(band_ink(mixed(self.colour, surface, BAND_RIGHT), 190))
        p.drawText(rect.adjusted(12, 0, -12, 0), int(Qt.AlignVCenter | Qt.AlignRight), self.right)
        p.end()


class EntryCard(QFrame):
    """One entry of the node list: its name and what it does, its color down its
    side. A favourite is a chip: its name alone, two to a row."""

    chosen = Signal(str)

    def __init__(self, key: str, title: str, blurb: str, colour: str, chip: bool = False, parent=None):
        super().__init__(parent)
        self.key = key
        self.colour = colour
        self.chip = chip
        self.setObjectName("eventEntry")
        column = QVBoxLayout(self)
        column.setContentsMargins(12, 5 if not chip else 6, 8, 5 if not chip else 6)
        column.setSpacing(1)
        self.title = QLabel(title)
        self.title.setStyleSheet("font-weight: 600;")
        column.addWidget(self.title)
        self.blurb = QLabel(blurb)
        self.blurb.setProperty("role", "muted")
        self.blurb.setWordWrap(True)
        column.addWidget(self.blurb)
        # Hidden once it is in the card, never shown before: a label shown
        # with no parent opens as a window of its own, for a moment, on
        # every start (`audit_startup_windows` counted 32).
        if chip:
            self.blurb.hide()
        self.setToolTip(blurb)
        self._press = None
        self.search_text = f"{title} {blurb}".lower()

    def paintEvent(self, event):                                      # noqa: N802
        # Painted, not styled: the theme's surface as it is now, after a
        # change of appearance too, and the entry's color down its side.
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(Qt.NoPen)
        p.setBrush(_colour("surface"))
        p.drawRoundedRect(rect, 4, 4)
        bar = QPainterPath()
        bar.addRoundedRect(QRectF(rect.left(), rect.top(), 8, rect.height()), 4, 4)
        p.save()
        p.setClipRect(QRectF(rect.left(), rect.top(), 4, rect.height()))
        p.setBrush(QColor(self.colour))
        p.drawPath(bar)
        p.restore()
        p.end()

    def mousePressEvent(self, event):                                 # noqa: N802
        if event.button() == Qt.LeftButton:
            self._press = event.position()

    def mouseMoveEvent(self, event):                                  # noqa: N802
        if self._press is None or (event.position() - self._press).manhattanLength() < 8:
            return
        self._press = None
        drag = QDrag(self)
        data = QMimeData()
        data.setData(MIME, self.key.encode())
        drag.setMimeData(data)
        drag.exec(Qt.CopyAction)

    def mouseDoubleClickEvent(self, event):                           # noqa: N802
        self.chosen.emit(self.key)

    def contextMenuEvent(self, event):                                # noqa: N802
        menu = self.menu() if self.menu is not None else None
        if menu is not None:
            show_menu(menu, event.globalPos())

    #: What a right click shows: set by the list (`NodeList.menu_for`), none in Ready-made.
    menu = None


class Line(QWidget):
    """A thin line in the theme's border color: between two kinds of the node list, and over the
    big node's foot."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(1)

    def paintEvent(self, event):                                      # noqa: N802
        p = QPainter(self)
        p.fillRect(self.rect(), _colour("border"))
        p.end()


class KindHeading(QFrame):
    """A kind's heading in the node list: its color, its name, and how many
    nodes it has with a word to show or hide them. A click opens or closes it."""

    toggled = Signal()

    def __init__(self, text: str, colour: str, count: Optional[int], parent=None):
        super().__init__(parent)
        self.count = count
        self.open = True
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 4, 2, 4)
        row.setSpacing(8)
        bar = QFrame()
        bar.setFixedSize(4, 16)
        bar.setStyleSheet(f"background: {colour}; border-radius: 2px;")
        row.addWidget(bar)
        self.label = QLabel(text)
        self.label.setStyleSheet("font-weight: 600;")
        row.addWidget(self.label, 1)
        self.state = QLabel("")
        self.state.setProperty("role", "muted")
        row.addWidget(self.state)
        if count is not None:
            self.setCursor(Qt.PointingHandCursor)
        self.set_open(True)

    def set_open(self, open_: bool) -> None:
        self.open = open_
        if self.count is not None:
            # None to show or hide (the favourites, all taken out): no words.
            self.state.setText((HIDE_THEM if open_ else SHOW_THEM).format(count=self.count) if self.count else "")

    def mouseReleaseEvent(self, event):                               # noqa: N802
        if self.count is not None and event.button() == Qt.LeftButton:
            self.toggled.emit()


class NodeList(QWidget):
    """The nodes to add: a search box, the favourites, then each kind (see the module's notes)."""

    chosen = Signal(str)
    #: The favourites changed by a right click: their keys, in order.
    favourites_changed = Signal(list)

    def __init__(self, entries=words.ENTRIES, favourites=words.FAVOURITES, ready=None, parent=None):
        super().__init__(parent)
        self.ready = ready
        #: The favourites' keys, in their order: entries the list has, each once.
        self.favourites: list = []
        for key in favourites:
            if words.entry_by_key(key) is not None and key not in self.favourites:
                self.favourites.append(key)
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(6)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Search nodes, as "walk" or "music"' if ready is None
                                       else "Search ready-made events")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter)
        column.addWidget(self.search)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        self.rows = QVBoxLayout(inner)
        self.rows.setContentsMargins(0, 0, 4, 0)
        self.rows.setSpacing(4)
        self.cards: list = []
        #: `[(heading, body, kind or None, cards)]`: each section of the list.
        self.sections: list = []
        #: Which kinds were open when a search began, given back when it is cleared.
        self._opened: Optional[list] = None
        #: The line over each kind's heading, by its section's index.
        self._lines: dict = {}
        if ready is not None:
            body, cards = self._section(None)
            for made in ready:
                card = EntryCard(f"ready:{made.key}", made.title, made.blurb, words.KIND_COLOURS["story"])
                self._add(card, body.layout(), cards)
        else:
            # The favourites close as a kind does (their heading's count is theirs).
            heading = KindHeading(FAVOURITES, words.KIND_COLOURS["talk"], len(self.favourites))
            self.rows.addWidget(heading)
            body, cards = self._section(heading)
            self._favourites_grid = QGridLayout()
            self._favourites_grid.setContentsMargins(0, 0, 0, 0)
            self._favourites_grid.setHorizontalSpacing(6)
            self._favourites_grid.setVerticalSpacing(6)
            body.layout().addLayout(self._favourites_grid)
            self._no_favourites = QLabel(NO_FAVOURITES)
            self._no_favourites.setProperty("role", "muted")
            self._no_favourites.setWordWrap(True)
            body.layout().addWidget(self._no_favourites)
            self._fill_favourites()
            heading.toggled.connect(lambda: self.toggle(0))
            first = True
            for kind in words.KINDS:
                found = [e for e in entries if e.kind == kind]
                if not found:
                    continue
                line = self._line()
                heading = KindHeading(words.KIND_NAMES[kind], words.KIND_COLOURS[kind], len(found))
                self.rows.addWidget(heading)
                body, cards = self._section(heading, kind)
                self._lines[len(self.sections) - 1] = line
                for entry in found:
                    self._add(EntryCard(entry.key, entry.title, entry.blurb,
                                        words.entry_colour(entry.key, entry.kind)), body.layout(), cards)
                # The first kind open, the others closed to their line, as the mock-up has them.
                self._set_open(len(self.sections) - 1, first)
                heading.toggled.connect(lambda index=len(self.sections) - 1: self.toggle(index))
                first = False
        self.rows.addStretch(1)
        self.scroll.setWidget(inner)
        column.addWidget(self.scroll, 1)
        foot = QLabel(READY_FOOT if ready is not None else LIST_FOOT)
        foot.setProperty("role", "muted")
        foot.setWordWrap(True)
        column.addWidget(foot)
        self.foot = foot

    # -- building ----------------------------------------------------------------------

    def _section(self, heading: Optional[KindHeading], kind: Optional[str] = None) -> tuple:
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.rows.addWidget(body)
        cards: list = []
        self.sections.append((heading, body, kind, cards))
        return body, cards

    def _line(self) -> "Line":
        line = Line()
        self.rows.addWidget(line)
        return line

    def _add(self, card: EntryCard, layout, cards: list) -> None:
        card.chosen.connect(self.chosen)
        card.favourite = False
        if self.ready is None:
            card.menu = lambda c=card: self.menu_for(c)
        layout.addWidget(card)
        self.cards.append(card)
        cards.append(card)

    # -- the favourites ------------------------------------------------------------------

    def _fill_favourites(self) -> None:
        """The favourites' chips, two to a row, made again from `favourites`."""
        heading, body, _kind, cards = self.sections[0]
        for card in cards:
            self._favourites_grid.removeWidget(card)
            self.cards.remove(card)
            retire(card)
        cards.clear()
        for n, key in enumerate(self.favourites):
            entry = words.entry_by_key(key)
            card = EntryCard(entry.key, entry.title, entry.blurb, words.entry_colour(entry.key, entry.kind),
                             chip=True)
            card.favourite = True
            card.chosen.connect(self.chosen)
            card.menu = lambda c=card: self.menu_for(c)
            self._favourites_grid.addWidget(card, n // 2, n % 2)
            self.cards.append(card)
            cards.append(card)
        self._no_favourites.setVisible(not self.favourites)
        heading.count = len(self.favourites)
        heading.set_open(heading.open)
        self._filter(self.search.text())

    def menu_for(self, card: EntryCard) -> QMenu:
        """A node's right click: add it to the favourites, or take it out."""
        menu = QMenu(self)
        if card.key in self.favourites:
            menu.addAction(REMOVE_FAVOURITE, lambda key=card.key: self.set_favourite(key, False))
        else:
            menu.addAction(ADD_FAVOURITE, lambda key=card.key: self.set_favourite(key, True))
        return menu

    def set_favourite(self, key: str, on: bool) -> None:
        """A node added to the favourites (at their end) or taken out of them."""
        if on == (key in self.favourites) or words.entry_by_key(key) is None:
            return
        if on:
            self.favourites.append(key)
        else:
            self.favourites.remove(key)
        self._fill_favourites()
        self.favourites_changed.emit(list(self.favourites))

    # -- opening, closing, searching ----------------------------------------------------

    def is_open(self, index: int) -> bool:
        heading, body, _kind, _cards = self.sections[index]
        return heading is None or heading.count is None or heading.open

    def _set_open(self, index: int, open_: bool) -> None:
        heading, body, _kind, _cards = self.sections[index]
        if heading is not None:
            heading.set_open(open_)
        body.setVisible(open_)

    def toggle(self, index: int) -> None:
        """A kind's heading clicked: its nodes shown or hidden."""
        if self.search.text().strip():
            return
        self._set_open(index, not self.is_open(index))

    def _filter(self, text: str) -> None:
        needle = text.strip().lower()
        if needle and self._opened is None:
            # The kinds as the person left them, for when the search is cleared.
            self._opened = [self.is_open(i) for i in range(len(self.sections))]
        for card in self.cards:
            card.setHidden(bool(needle) and needle not in card.search_text)
        shown_before = False
        for index, (heading, body, _kind, cards) in enumerate(self.sections):
            matches = [c for c in cards if not c.isHidden()]
            if needle:
                body.setVisible(bool(matches))
                if heading is not None:
                    heading.setHidden(not matches)
                    if matches and heading.count is not None:
                        heading.set_open(True)
            else:
                if heading is not None:
                    heading.setHidden(False)
            # A kind's line only between kinds shown: a search leaves no lines
            # stacked where the kinds it leaves out were.
            line = self._lines.get(index)
            if line is not None:
                line.setVisible(not needle or (bool(matches) and shown_before))
            shown_before = shown_before or not needle or bool(matches)
        if not needle and self._opened is not None:
            for index, open_ in enumerate(self._opened):
                self._set_open(index, open_)
            self._opened = None
