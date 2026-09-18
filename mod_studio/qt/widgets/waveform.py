"""
The loop editor's waveform: the audio across the width, the loop as a
shaded region with a flag at each end, and a playhead.

Asked for from real use: "It would be a huge quality of life feature if a
user could scrub through the wave file live to pin the exact start and end
time that they could hear as they wanted for their track." The Loop points
box takes sample numbers - 444234, 2117614 - which mean nothing to somebody
who hasn't already learned what a sample is.

Drawn the way audio editors draw it (Audacity, Adobe Audition, Logic's cycle
region): the loop is an area you can SEE, its edges are flags you DRAG, and
clicking anywhere else moves the playhead there. The numbers stay available
underneath for exact positions, but nobody has to start there.

Nothing here plays audio - the page does that - so the widget can be driven,
and tested, without a sound device.
"""
from __future__ import annotations

import sys
from array import array

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPalette, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

#: How close, in pixels, a press must be to a loop edge to take hold of it.
GRAB_PX = 7
#: The flag at the top of each loop edge - the obvious thing to drag.
FLAG_W, FLAG_H = 40, 17


def compute_peaks(data: bytes, channels: int, columns: int) -> list:
    """
    (low, high) for each pixel column, from the first channel, as -1..1.

    Each column's min and max are taken over an `array` slice, in C, so a
    three-minute track (8.6 million samples) takes a fraction of a second
    rather than the seconds a Python loop over every sample would.
    """
    if columns <= 0 or channels <= 0:
        return []
    samples = array("h")
    samples.frombytes(data[:len(data) - len(data) % 2])
    if sys.byteorder == "big":
        samples.byteswap()
    if channels > 1:
        samples = samples[0::channels]
    count = len(samples)
    if count == 0:
        return []
    peaks = []
    for column in range(columns):
        first = column * count // columns
        last = max(first + 1, (column + 1) * count // columns)
        chunk = samples[first:last]
        peaks.append((min(chunk) / 32768.0, max(chunk) / 32767.0))
    return peaks


class WaveformView(QWidget):
    """The waveform, the loop region, and the playhead."""

    seekRequested = Signal(int)          # a click: move the playhead to this frame
    loopDragged = Signal(int, int)       # a flag moving
    loopEdited = Signal(int, int)        # a flag let go
    playToggleRequested = Signal()       # Space, while the waveform has focus

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(128)
        self.setMinimumWidth(240)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        # Click focus, so Space can play and pause - never wheel focus.
        self.setFocusPolicy(Qt.ClickFocus)
        self.setMouseTracking(True)
        self.setToolTip(
            "Click anywhere to move the playhead there.\n"
            "Drag the Start and End flags to move the loop.\n"
            "Space plays and pauses.")
        self._pcm = None
        self._peaks = []
        self._peaks_key = None
        self.total_frames = 0
        self.loop_start = None
        self.loop_end = None
        self.editable = False
        self.playhead = 0
        self.min_loop = 1000
        self._drag = None

    # -- what it shows ---------------------------------------------------------

    def set_audio(self, pcm) -> None:
        """A `sound_data.Pcm16`, or None for nothing to show."""
        self._pcm = pcm
        self.total_frames = pcm.frames if pcm is not None else 0
        self._peaks_key = None
        self.playhead = 0
        self._drag = None
        self.update()

    def set_loop(self, start, end, editable: bool) -> None:
        if start is not None and end is not None and end > start:
            self.loop_start, self.loop_end = int(start), int(end)
        else:
            self.loop_start = self.loop_end = None
        self.editable = bool(editable)
        self.update()

    def set_playhead(self, frame) -> None:
        self.playhead = max(0, min(int(frame), self.total_frames))
        self.update()

    # -- geometry ----------------------------------------------------------------

    def _plot(self) -> QRectF:
        return QRectF(1, FLAG_H + 2, max(1, self.width() - 2),
                      max(1, self.height() - FLAG_H - 4))

    def x_at(self, frame) -> float:
        plot = self._plot()
        if not self.total_frames:
            return plot.left()
        return plot.left() + plot.width() * frame / self.total_frames

    def frame_at(self, x) -> int:
        plot = self._plot()
        if not self.total_frames:
            return 0
        ratio = (x - plot.left()) / plot.width()
        return max(0, min(self.total_frames, round(ratio * self.total_frames)))

    def _flags(self):
        """(edge name, flag rectangle, x) for each loop edge."""
        xs, xe = self.x_at(self.loop_start), self.x_at(self.loop_end)
        return (("start", QRectF(xs, 0, FLAG_W, FLAG_H), xs),
                ("end", QRectF(xe - FLAG_W, 0, FLAG_W, FLAG_H), xe))

    def edge_at(self, point) -> str | None:
        """The loop edge a press at `point` takes hold of, if any."""
        if not self.editable or self.loop_start is None:
            return None
        flags = self._flags()
        for name, flag, _x in flags:
            if flag.contains(point):
                return name
        nearest = min(flags, key=lambda item: abs(point.x() - item[2]))
        return nearest[0] if abs(point.x() - nearest[2]) <= GRAB_PX else None

    # -- the mouse and keyboard ------------------------------------------------

    def mousePressEvent(self, event):                            # noqa: N802
        if event.button() != Qt.LeftButton or not self.total_frames:
            return super().mousePressEvent(event)
        edge = self.edge_at(event.position())
        if edge:
            self._drag = edge
            return
        frame = self.frame_at(event.position().x())
        self.set_playhead(frame)
        self.seekRequested.emit(frame)

    def mouseMoveEvent(self, event):                             # noqa: N802
        point = event.position()
        if self._drag:
            frame = self.frame_at(point.x())
            start, end = self.loop_start, self.loop_end
            if self._drag == "start":
                start = max(0, min(frame, end - self.min_loop))
            else:
                end = min(self.total_frames, max(frame, start + self.min_loop))
            if (start, end) != (self.loop_start, self.loop_end):
                self.loop_start, self.loop_end = start, end
                self.update()
                self.loopDragged.emit(start, end)
            return
        if self.edge_at(point):
            self.setCursor(Qt.SizeHorCursor)
        else:
            self.unsetCursor()

    def mouseReleaseEvent(self, event):                          # noqa: N802
        if self._drag:
            self._drag = None
            self.loopEdited.emit(self.loop_start, self.loop_end)
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):                              # noqa: N802
        if event.key() == Qt.Key_Space:
            self.playToggleRequested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    # -- drawing -----------------------------------------------------------------

    def _peaks_for(self, width: int) -> list:
        key = (id(self._pcm), width)
        if key != self._peaks_key:
            self._peaks = compute_peaks(self._pcm.data, self._pcm.channels, width)
            self._peaks_key = key
        return self._peaks

    def paintEvent(self, _event):                                # noqa: N802
        painter = QPainter(self)
        palette = self.palette()
        painter.fillRect(self.rect(), palette.color(QPalette.Base))
        if not self.total_frames or self._pcm is None:
            painter.setPen(palette.color(QPalette.PlaceholderText))
            painter.drawText(self.rect(), Qt.AlignCenter, "No audio to show")
            return
        plot = self._plot()
        accent = palette.color(QPalette.Highlight)
        if self.loop_start is not None:
            xs, xe = self.x_at(self.loop_start), self.x_at(self.loop_end)
            region = QColor(accent)
            region.setAlpha(70 if self.editable else 35)
            painter.fillRect(QRectF(xs, plot.top(), max(1.0, xe - xs), plot.height()),
                             region)
        wave = QColor(palette.color(QPalette.Text))
        wave.setAlpha(175)
        painter.setPen(QPen(wave, 1))
        middle = plot.center().y()
        half = plot.height() / 2 - 1
        for column, (low, high) in enumerate(self._peaks_for(int(plot.width()))):
            x = plot.left() + column + 0.5
            painter.drawLine(QPointF(x, middle - high * half),
                             QPointF(x, middle - low * half))
        if self.loop_start is not None:
            edge = QColor(accent) if self.editable else QColor(wave)
            font = painter.font()
            font.setPointSizeF(max(7.0, font.pointSizeF() - 1))
            font.setBold(True)
            painter.setFont(font)
            for name, flag, x in self._flags():
                painter.setPen(QPen(edge, 2))
                painter.drawLine(QPointF(x, 0), QPointF(x, self.height()))
                painter.fillRect(flag, edge)
                painter.setPen(palette.color(QPalette.HighlightedText))
                painter.drawText(flag, Qt.AlignCenter, name.capitalize())
        head = QColor(palette.color(QPalette.Text))
        painter.setPen(QPen(head, 2))
        x = self.x_at(self.playhead)
        painter.drawLine(QPointF(x, FLAG_H), QPointF(x, self.height()))
