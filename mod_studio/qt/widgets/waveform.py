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

**Zoom.** Asked for from real use: "being able to zoom into the audio wave
with your scroll wheel for more precise edits". The widget shows a WINDOW of
the track, `view_start` for `view_span` frames, and every mapping between
pixels and frames goes through it - so dragging a flag, clicking to seek and
the Set buttons all work at whatever zoom is showing, with no second code
path. The conventions are the ones audio editors share (Audition, Logic,
Reaper, Audacity):

- **Scroll** zooms, about the point under the pointer, which stays put.
- **Shift+scroll**, or a sideways scroll on a trackpad, moves along.
- Zoomed in, a **thin bar** along the bottom shows which part of the track
  is on screen; drag it to move along. It is drawn inside the waveform, not
  added under it, so zooming moves nothing else on the page.
- **Playing** turns the page when the playhead reaches the edge, so the
  line never plays off the side of what you are looking at.
- Choosing another track shows the whole of it again.

Zoomed in far enough that a pixel column holds less than a sample, it stops
drawing min/max columns and draws the samples themselves, joined up - which
is what "precise" needs.
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
#: Each notch of the wheel shows this much of what was showing.
ZOOM_STEP = 0.8
#: The deepest zoom: this many pixels to a sample.
MAX_PX_PER_SAMPLE = 8
#: Each notch of Shift+scroll moves the view by this share of its width.
PAN_STEP = 0.1
#: The bar that shows where the view is, when zoomed in.
BAR_H = 5


def mono_samples(data: bytes, channels: int) -> array:
    """The first channel, as signed 16-bit samples."""
    samples = array("h")
    samples.frombytes(data[:len(data) - len(data) % 2])
    if sys.byteorder == "big":
        samples.byteswap()
    if channels > 1:
        samples = samples[0::channels]
    return samples


def peaks_between(samples, first: int, last: int, columns: int) -> list:
    """(low, high) per pixel column for frames `first` to `last`, as -1..1."""
    count = max(0, min(last, len(samples)) - max(0, first))
    if columns <= 0 or count <= 0:
        return []
    first = max(0, first)
    peaks = []
    for column in range(columns):
        start = first + column * count // columns
        stop = max(start + 1, first + (column + 1) * count // columns)
        chunk = samples[start:stop]
        peaks.append((min(chunk) / 32768.0, max(chunk) / 32767.0))
    return peaks


def compute_peaks(data: bytes, channels: int, columns: int) -> list:
    """
    (low, high) for each pixel column, from the first channel, as -1..1.

    Each column's min and max are taken over an `array` slice, in C, so a
    three-minute track (8.6 million samples) takes a fraction of a second
    rather than the seconds a Python loop over every sample would.
    """
    if columns <= 0 or channels <= 0:
        return []
    samples = mono_samples(data, channels)
    return peaks_between(samples, 0, len(samples), columns)


class WaveformView(QWidget):
    """The waveform, the loop region, and the playhead."""

    seekRequested = Signal(int)          # a click: move the playhead to this frame
    loopDragged = Signal(int, int)       # a flag moving
    loopEdited = Signal(int, int)        # a flag let go
    playToggleRequested = Signal()       # Space, while the waveform has focus
    viewChanged = Signal(int, int)       # the zoom or position: start, span

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
            "Scroll to zoom in and out; Shift+scroll to move along.\n"
            "Space plays and pauses.")
        self._pcm = None
        self._samples = None
        self._peaks = []
        self._peaks_key = None
        #: The part of the track on screen. `view_span` 0 means all of it.
        self.view_start = 0
        self.view_span = 0
        #: Where on the view bar a drag took hold, as a frame offset.
        self._bar_grab = None
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
        self._samples = None
        self.total_frames = pcm.frames if pcm is not None else 0
        self._peaks_key = None
        self.playhead = 0
        self._drag = None
        self._bar_grab = None
        # Another track is shown whole. A zoom kept across tracks of
        # different lengths would open the next one on an arbitrary slice.
        self.view_start, self.view_span = 0, 0
        self.viewChanged.emit(0, self.total_frames)
        self.update()

    def set_loop(self, start, end, editable: bool) -> None:
        if start is not None and end is not None and end > start:
            self.loop_start, self.loop_end = int(start), int(end)
        else:
            self.loop_start = self.loop_end = None
        self.editable = bool(editable)
        self.update()

    def set_playhead(self, frame, follow: bool = False) -> None:
        """
        Moves the playhead. `follow` is for playback: zoomed in, a playhead
        leaving the view turns the page, the way an audio editor's does.
        """
        self.playhead = max(0, min(int(frame), self.total_frames))
        if follow and self.zoomed():
            start, span = self.view()
            if not start <= self.playhead < start + span:
                self.set_view(self.playhead - span // 10, span)
        self.update()

    # -- the view ----------------------------------------------------------------

    def view(self) -> tuple:
        """(first frame on screen, how many frames are on screen)."""
        if not self.total_frames:
            return 0, 0
        span = self.view_span or self.total_frames
        return self.view_start, span

    def zoomed(self) -> bool:
        return bool(self.total_frames) and self.view()[1] < self.total_frames

    def min_span(self) -> int:
        """The fewest frames the view will show - the deepest zoom."""
        return max(2, int(self._plot().width() / MAX_PX_PER_SAMPLE))

    def set_view(self, start, span) -> None:
        """Shows `span` frames from `start`, kept inside the track."""
        if not self.total_frames:
            return
        span = int(max(min(self.min_span(), self.total_frames),
                       min(int(span), self.total_frames)))
        start = int(max(0, min(int(start), self.total_frames - span)))
        if span >= self.total_frames:
            start, span = 0, 0
        if (start, span) == (self.view_start, self.view_span):
            return
        self.view_start, self.view_span = start, span
        self.viewChanged.emit(*self.view())
        self.update()

    def zoom(self, factor: float, anchor_x=None) -> None:
        """
        Shows `factor` times as much of the track (below 1 zooms in),
        keeping the frame under `anchor_x` - the pointer - where it is.
        """
        if not self.total_frames:
            return
        plot = self._plot()
        if anchor_x is None:
            anchor_x = plot.center().x()
        start, span = self.view()
        ratio = min(1.0, max(0.0, (anchor_x - plot.left()) / plot.width()))
        anchor = start + ratio * span
        new_span = span * factor
        self.set_view(round(anchor - ratio * new_span), round(new_span))

    def pan(self, share: float) -> None:
        """Moves along by `share` of the view's width (negative: back)."""
        start, span = self.view()
        self.set_view(start + round(share * span), span)

    # -- geometry ----------------------------------------------------------------

    def _plot(self) -> QRectF:
        return QRectF(1, FLAG_H + 2, max(1, self.width() - 2),
                      max(1, self.height() - FLAG_H - 4))

    def x_at(self, frame) -> float:
        plot = self._plot()
        if not self.total_frames:
            return plot.left()
        start, span = self.view()
        return plot.left() + plot.width() * (frame - start) / span

    def frame_at(self, x) -> int:
        plot = self._plot()
        if not self.total_frames:
            return 0
        start, span = self.view()
        ratio = (x - plot.left()) / plot.width()
        return max(0, min(self.total_frames, round(start + ratio * span)))

    def _bar(self) -> QRectF:
        """The view bar's track, along the bottom of the plot."""
        plot = self._plot()
        return QRectF(plot.left(), plot.bottom() - BAR_H, plot.width(), BAR_H)

    def _bar_thumb(self) -> QRectF:
        bar = self._bar()
        start, span = self.view()
        return QRectF(bar.left() + bar.width() * start / self.total_frames,
                      bar.top(),
                      max(6.0, bar.width() * span / self.total_frames),
                      bar.height())

    def _on_bar(self, point) -> bool:
        if not self.zoomed():
            return False
        bar = self._bar()
        return (bar.left() <= point.x() <= bar.right()
                and bar.top() - 4 <= point.y() <= self.height())

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
        if self._on_bar(event.position()):
            # Take hold of the thumb where it was pressed; a press beside it
            # centres the view there first, the way a scrollbar's track does.
            bar = self._bar()
            at = round((event.position().x() - bar.left()) / bar.width()
                       * self.total_frames)
            start, span = self.view()
            if not start <= at <= start + span:
                self.set_view(at - span // 2, span)
                start, span = self.view()
            self._bar_grab = at - start
            return
        edge = self.edge_at(event.position())
        if edge:
            self._drag = edge
            return
        frame = self.frame_at(event.position().x())
        self.set_playhead(frame)
        self.seekRequested.emit(frame)

    def mouseMoveEvent(self, event):                             # noqa: N802
        point = event.position()
        if self._bar_grab is not None:
            bar = self._bar()
            at = round((point.x() - bar.left()) / bar.width() * self.total_frames)
            self.set_view(at - self._bar_grab, self.view()[1])
            return
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
        if self._bar_grab is not None:
            self._bar_grab = None
            return
        if self._drag:
            self._drag = None
            self.loopEdited.emit(self.loop_start, self.loop_end)
            return
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):                                 # noqa: N802
        """
        Scroll zooms about the pointer; Shift+scroll, or a sideways scroll,
        moves along. With nothing to show the wheel is left alone, for
        whatever is behind.
        """
        if not self.total_frames:
            event.ignore()
            return
        delta = event.angleDelta()
        sideways = delta.x() if abs(delta.x()) > abs(delta.y()) else 0
        if event.modifiers() & Qt.ShiftModifier and not sideways:
            sideways = delta.y()
        if sideways:
            self.pan(-PAN_STEP * sideways / 120.0)
        elif delta.y():
            self.zoom(ZOOM_STEP ** (delta.y() / 120.0),
                      event.position().x())
        event.accept()

    def keyPressEvent(self, event):                              # noqa: N802
        if event.key() == Qt.Key_Space:
            self.playToggleRequested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    # -- drawing -----------------------------------------------------------------

    def _mono(self):
        if self._samples is None and self._pcm is not None:
            self._samples = mono_samples(self._pcm.data, self._pcm.channels)
        return self._samples

    def _peaks_for(self, width: int) -> list:
        start, span = self.view()
        key = (id(self._pcm), width, start, span)
        if key != self._peaks_key:
            self._peaks = peaks_between(self._mono(), start, start + span, width)
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
        start, span = self.view()
        if span < plot.width():
            # Fewer samples than columns: the samples themselves, joined.
            samples = self._mono()
            last = min(len(samples), start + span + 2)
            points = [QPointF(self.x_at(frame),
                              middle - samples[frame] / 32768.0 * half)
                      for frame in range(start, last)]
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.drawPolyline(points)
            if span * 3 < plot.width():
                painter.setBrush(wave)
                for point in points:
                    painter.drawEllipse(point, 1.5, 1.5)
                painter.setBrush(Qt.NoBrush)
            painter.setRenderHint(QPainter.Antialiasing, False)
        else:
            for column, (low, high) in enumerate(
                    self._peaks_for(int(plot.width()))):
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
        if self.zoomed():
            track = QColor(palette.color(QPalette.Text))
            track.setAlpha(40)
            painter.fillRect(self._bar(), track)
            thumb = QColor(palette.color(QPalette.Text))
            thumb.setAlpha(150)
            painter.fillRect(self._bar_thumb(), thumb)
