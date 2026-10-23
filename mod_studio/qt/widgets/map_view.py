"""
The Map Editor's picture of a battle map: drawn off screen by `MapRenderer`
and painted here, turned with the mouse, with the battle grid over it.

- **Drag** turns the map: across, around it; up and down, higher or lower.
  **Shift and drag**, or drag with the middle button, moves it. **The
  wheel** zooms, keeping the point under the pointer where it is. Turning
  never changes the map's size (`MapRenderer.half_height`).
- **The pointer is the usual one.** Over a tile, the tile lights up and a
  card beside the pointer says its surface and height (`show_info` turns
  the card off). (The first build used the game's `ui/sword.tga`; Zodi
  asked for the mouse back.)
- **Clicking** a tile picks it; with Ctrl held, it is added to the tiles
  picked, or taken out. The page decides what a pick means. With
  `box_select` on (the Map Editor's), **Ctrl and drag** draws a box and
  says the tiles whose middles are in it (`tiles_boxed`), rather than
  turning the map (Zodi's stress test of 20 October: 109 Ctrl and clicks to
  paint a tundra's grass).
- **Which way is north** (`show_compass`, the Map Editor's): N, E, S and
  W just past the middle of each edge of the grid, and while the camera is
  at one of the game's corners, which (Zodi's stress test of 20 October:
  Light the map's "0 north" and parts.txt's corners had nothing on screen
  to go by).
- **What moves in the map plays on a loop**: the view looks for a new
  frame every `ANIMATION_TICK` milliseconds while it is on screen, and
  draws again only when there is one.
- **A page can draw over it and take a drag** (Treasure Hunter): `overlay`
  paints on the picture after the map, `overlay_moves` repaints it while
  it moves (the picture underneath isn't drawn again), and `grabber` may
  take a press for itself - to drag a treasure tile rather than turn the
  map.

A drawing takes a few milliseconds on a graphics card and tens on the
software renderer, so they are asked for with `schedule()` and made once
the events waiting have been handled: a drag asks for many and gets as many
as the machine can draw.
"""
from __future__ import annotations

import math
import time
from typing import Optional

from PySide6.QtCore import QCoreApplication, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from ... import map_classic as mc
from .. import map_scene as ms
from .. import theme
from ..map_render import Camera, MapRenderer

#: How far the pointer moves before a press becomes a drag, in pixels.
DRAG_START = 4
#: Degrees turned per pixel dragged, across and up or down.
TURN_PER_PIXEL, TILT_PER_PIXEL = 0.4, 0.3
#: The lowest the camera goes, in degrees above the ground.
LOWEST_PITCH = 5.0
#: How far the wheel zooms, per notch, and the limits.
ZOOM_STEP, ZOOM_MIN, ZOOM_MAX = 1.15, 0.35, 14.0
#: Where the tile card sits from the pointer's tip: this far to the right,
#: and its bottom this far above the tip, clear of the arrow.
CARD_RIGHT, CARD_ABOVE = 16, 4
#: How often the view looks whether something in the map has a new frame, in milliseconds.
ANIMATION_TICK = 16
#: How often a moving overlay is painted again, in milliseconds.
OVERLAY_TICK = 33
#: The sky's gradient is drawn through this many steps down the view, so a
#: colour kept to 0 or 255 past its span (`MapView.sky_at`) bends where it is kept.
SKY_STOPS = 16


def _colour(name: str, alpha: int = 255) -> QColor:
    colour = QColor(theme.current()[name])
    colour.setAlpha(alpha)
    return colour


class MapView(QWidget):
    #: The tile under the pointer changed: `(x, z, level)`, or None.
    tile_hovered = Signal(object)
    #: A tile was clicked: `(x, z, level)` or None for a click off the grid,
    #: and whether Ctrl was held (add it to the tiles picked, or take it out).
    tile_clicked = Signal(object, bool)
    #: The camera moved: dragged, zoomed, or set by `set_camera`.
    camera_changed = Signal()
    #: Ctrl and a drag, with `box_select` on: the tiles whose middles are in
    #: the box drawn, as `(x, z, level)`s.
    tiles_boxed = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.renderer = MapRenderer()
        self.camera = Camera()
        self.scene: Optional[ms.Scene] = None
        #: The tiles as edited, and by `(x, z, level)`.
        self.tiles: list = []
        self._by_key: dict = {}
        self.edited: set = set()
        self.hovered = None
        self.picked: list = []
        #: The tiles battles use, `{(x, z, level): kinds}` (`map_scene.battle_geometry`): none shown when empty.
        self.marks: dict = {}
        self._marks_stale = True
        self.show_grid = True
        self.show_info = True
        #: N, E, S and W round the grid, and the corner the camera is at.
        self.show_compass = False
        #: Whether Ctrl and a drag picks the tiles in a box, not turns the map.
        self.box_select = False
        self._box: Optional[QRectF] = None
        #: Said on the picture: why there is no map, or what is happening.
        self.message = ""
        #: `describe(tile) -> (title, detail)`: the card's two lines.
        self.describe = None
        self.image: Optional[QImage] = None
        self.renders = 0
        self._pointer: Optional[QPointF] = None
        self._press = None
        self._dragging = False
        self._grid_stale = True
        self._highlight_stale = True
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(0)
        self._timer.timeout.connect(self.render_now)
        #: The animations' clock: `now()` is seconds, from any start; a map's
        #: animations start from their first frame when it is shown.
        self.now = time.monotonic
        self._started = 0.0
        self._frames_drawn = None
        self._ticker = QTimer(self)
        self._ticker.setInterval(ANIMATION_TICK)
        self._ticker.timeout.connect(self._tick)
        #: `overlay(painter)`: drawn over the map, in the widget's pixels.
        self.overlay = None
        #: Render the map with nothing behind it (alpha 0 there), for an
        #: overlay that paints its own backdrop.
        self.transparent = False
        #: `(top, bottom)` QColors: the sky behind the map, fading from the
        #: top of the view to its bottom, as the game draws a map's `Map` row
        #: colors in a battle (`map_variants`); None, the page's background.
        self.sky = None
        #: `() -> (top, bottom)`: where in the view the sky's top and bottom
        #: colors are, fading on past them as they went (`sky_at`), as the
        #: game spreads an event's sky; None, the view's top and bottom.
        self.sky_span = None
        #: Whether each drawing also measures how far the map is at each pixel
        #: (`MapRenderer.render_depth`), into `depth`: for an overlay that
        #: hides what stands behind the map's walls.
        self.want_depth = False
        self.depth = None
        #: The map's colours changed (`MapRenderer.render`'s `tint`): an
        #: event's ColorField, set by the Event Editor's map. None: its own.
        self.tint = None
        #: Whether the overlay moves by itself (`overlay_ticker` repaints it).
        self.overlay_moves = False
        self.overlay_ticker = QTimer(self)
        self.overlay_ticker.setInterval(OVERLAY_TICK)
        self.overlay_ticker.timeout.connect(self._overlay_tick)
        #: An object with `press(point) -> bool`, `move(point)` and
        #: `release(point, moved)`: a left press it says True to is its drag,
        #: not the map's turn.
        self.grabber = None
        self._grabbed = False
        self.setMouseTracking(True)
        self.setMinimumSize(320, 240)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        app = QCoreApplication.instance()
        if app is not None:
            # The graphics card's copies go before the context does; left to
            # Python's clean up, they would be freed with no context current.
            app.aboutToQuit.connect(self.release)

    # -- what is shown ----------------------------------------------------------

    def set_scene(self, scene: Optional[ms.Scene], tiles: list = (), edited=()) -> None:
        """A new map, or None for none; `tiles` are its grid as edited."""
        self.scene = scene
        self.hovered = None
        self.picked = []
        self.depth = None
        # A new map's doors are as it is read until an event plays them.
        self.renderer.played = {}
        self.renderer.set_scene(scene)
        if scene is not None and self.renderer.error is None:
            # On the graphics card now; an enhanced map's pictures are tens
            # of megabytes, and nothing else reads them.
            for batch in scene.batches:
                batch.colour = batch.light = None
                batch.frames = []
        self._started = self.now()
        self._frames_drawn = None
        self._update_ticker()
        self.set_tiles(tiles, edited)
        self.schedule()

    def set_tiles(self, tiles, edited=()) -> None:
        """The grid as edited, after a change: redrawn, raised tiles raised."""
        self.tiles = list(tiles)
        self._by_key = {(t.x, t.z, t.level): t for t in self.tiles}
        self.edited = set(edited)
        self._grid_stale = self._highlight_stale = self._marks_stale = True
        self.schedule()

    def set_marks(self, marks) -> None:
        """The tiles battles use, drawn over the grid (`map_scene.battle_geometry`); {} for none."""
        marks = {key: set(kinds) for key, kinds in (marks or {}).items()}
        if marks != self.marks:
            self.marks = marks
            self._marks_stale = True
            self.schedule()

    def set_picked(self, keys) -> None:
        self.picked = list(keys)
        self._highlight_stale = True
        self.schedule()

    def set_message(self, text: str) -> None:
        self.message = text
        self.update()

    def set_camera(self, camera: Camera) -> None:
        self.camera = camera
        self.camera_changed.emit()
        self.schedule()

    def tile(self, key):
        return self._by_key.get(key)

    def set_tint(self, tint) -> None:
        """The map's colours changed (`tint`, as the attribute says), drawn again when it changes."""
        if tint != self.tint:
            self.tint = tint
            self.schedule()

    def set_played(self, played) -> None:
        """
        `{texture group: colour frame}`: the doors and such an event has
        played (`MapRenderer.played`, `map_doors.pictures_at`), drawn again
        when they change; {} for each at its track's first frame.
        """
        played = dict(played or {})
        if played != self.renderer.played:
            self.renderer.played = played
            self.schedule()

    # -- drawing ----------------------------------------------------------------

    def sky_at(self, y: float) -> tuple:
        """The sky's colour at `y` in the view, `(r, g, b)`: its top colour faded to its bottom one over
        `sky_span` (the view's height without one), on past them as it went, each channel kept to 0 to 255."""
        if self.sky is None:
            return (0, 0, 0)
        top, bottom = self.sky_span() if self.sky_span is not None else (0.0, float(self.height()))
        t = (y - top) / (bottom - top) if abs(bottom - top) > 1e-6 else 0.0
        return tuple(min(255, max(0, int(round(a + (b - a) * t))))
                     for a, b in zip(self.sky[0].getRgb()[:3], self.sky[1].getRgb()[:3]))

    def set_sky(self, sky) -> None:
        """The sky behind the map (`sky`), drawn again when it changes."""
        if sky == self.sky:
            return
        self.sky = sky
        self.schedule()

    def schedule(self) -> None:
        """Asks for a drawing once the events waiting have been handled."""
        if not self._timer.isActive():
            self._timer.start()

    def render_now(self) -> None:
        self._timer.stop()
        if self.scene is None or not self.isVisible():
            self.update()
            return
        if not self.renderer.ensure_context():
            self.image = None
            self.update()
            return
        if self._grid_stale:
            self.renderer.set_grid(ms.grid_geometry(self.tiles, self.edited))
            self._grid_stale = False
        if self._highlight_stale:
            self.renderer.set_grid(ms.highlight_geometry(self._by_key, self.hovered, self.picked))
            self._highlight_stale = False
        if self._marks_stale:
            self.renderer.set_grid(ms.battle_geometry(self._by_key, self.marks))
            self._marks_stale = False
        ratio = self.devicePixelRatioF()
        ground = _colour("surface_alt")
        seconds = self.seconds()
        self._frames_drawn = self.renderer.frames_at(seconds)
        image = self.renderer.render(self.camera, round(self.width() * ratio),
                                     round(self.height() * ratio), show_grid=self.show_grid,
                                     background=(ground.redF(), ground.greenF(), ground.blueF()),
                                     seconds=seconds, transparent=self.transparent or self.sky is not None,
                                     tint=self.tint)
        if image is not None:
            image.setDevicePixelRatio(ratio)
            self.renders += 1
        self.depth = (self.renderer.render_depth(self.camera, round(self.width() * ratio),
                                                 round(self.height() * ratio), seconds=seconds)
                      if self.want_depth and image is not None else None)
        self.image = image
        self.update()

    def release(self) -> None:
        """Frees what the graphics card holds for this picture."""
        self._ticker.stop()
        self.overlay_ticker.stop()
        self.renderer.close()

    # -- what moves ---------------------------------------------------------------

    def seconds(self) -> float:
        """How far into its animations the map is."""
        return max(0.0, self.now() - self._started)

    def animating(self) -> bool:
        return self._ticker.isActive()

    def _update_ticker(self) -> None:
        """Looks for new frames while a map that moves is on screen, and not otherwise."""
        wanted = (self.scene is not None and self.isVisible() and self.renderer.error is None
                  and self.renderer.animates())
        if wanted and not self._ticker.isActive():
            self._ticker.start()
        elif not wanted and self._ticker.isActive():
            self._ticker.stop()
        self.update_overlay_ticker()

    def update_overlay_ticker(self) -> None:
        """Repaints a moving overlay while it is on screen, and not otherwise."""
        wanted = bool(self.overlay_moves and self.overlay is not None and self.isVisible()
                      and self.scene is not None)
        if wanted and not self.overlay_ticker.isActive():
            self.overlay_ticker.start()
        elif not wanted and self.overlay_ticker.isActive():
            self.overlay_ticker.stop()

    def _overlay_tick(self) -> None:
        window = self.window()
        if not self.isVisible() or (window is not None and window.isMinimized()):
            self.update_overlay_ticker()
            return
        self.update()

    def _tick(self) -> None:
        if not self.isVisible():
            self._update_ticker()
            return
        window = self.window()
        if window is not None and window.isMinimized():
            return
        if self.renderer.frames_at(self.seconds()) != self._frames_drawn:
            self.schedule()

    def showEvent(self, event):                                   # noqa: N802
        super().showEvent(event)
        self._update_ticker()
        self.schedule()

    def hideEvent(self, event):                                   # noqa: N802
        super().hideEvent(event)
        self._update_ticker()

    def resizeEvent(self, event):                                 # noqa: N802
        super().resizeEvent(event)
        self.schedule()

    def paintEvent(self, event):                                  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self.sky is not None and self.image is not None and self.scene is not None:
            sky = QLinearGradient(0, 0, 0, self.height())
            for k in range(SKY_STOPS + 1):
                sky.setColorAt(k / SKY_STOPS, QColor(*self.sky_at(self.height() * k / SKY_STOPS)))
            p.fillRect(self.rect(), sky)
        else:
            p.fillRect(self.rect(), _colour("surface_alt"))
        if self.image is not None and self.scene is not None:
            p.drawImage(QPointF(0, 0), self.image)
        error = self.renderer.error and ("Maps can't be drawn on this computer: "
                                         f"{self.renderer.error}.")
        area = QRectF(self.rect()).adjusted(16, 12, -16, -12)
        p.setPen(_colour("text_muted"))
        if error or (self.message and self.scene is None):
            # Instead of a map: in the middle.
            p.drawText(area, int(Qt.TextWordWrap) | int(Qt.AlignCenter), error or self.message)
        else:
            if self.show_compass and self.image is not None and self.scene is not None:
                self._paint_compass(p, area)
            if self.overlay is not None and self.image is not None and self.scene is not None:
                p.save()
                self.overlay(p)
                p.restore()
            if self._box is not None:
                p.setPen(QPen(_colour("accent", 235), 1.4, Qt.DashLine))
                p.setBrush(_colour("accent", 45))
                p.drawRect(self._box)
                p.setBrush(Qt.NoBrush)
            if self.message:
                # Over a map: in its corner, out of the way.
                p.drawText(area, int(Qt.TextWordWrap) | int(Qt.AlignLeft | Qt.AlignTop), self.message)
            if (self.show_info and self.hovered is not None and self._pointer is not None
                    and not self._dragging and self.describe is not None):
                tile = self._by_key.get(self.hovered)
                if tile is not None:
                    self._paint_card(p, *self.describe(tile))
        p.setPen(QPen(_colour("border"), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5))
        p.end()

    def compass_marks(self) -> dict:
        """
        `{letter: QPointF}`: where N, E, S and W go in the picture, half a
        tile past the middle of each edge of the grid, on the ground (north
        is the files' +z, east their +x: `map_scene.CORNERS`' angles, and
        Light the map's compass). Empty with no grid.
        """
        shown = [t for t in self.tiles if not t.is_blank]
        if self.scene is None or not shown or self.renderer.error:
            return {}
        size = mc.TILE_SIZE
        x0, x1 = min(t.x for t in shown) * size, (max(t.x for t in shown) + 1) * size
        z0, z1 = min(t.z for t in shown) * size, (max(t.z for t in shown) + 1) * size
        cx, cz, pad = (x0 + x1) / 2, (z0 + z1) / 2, size / 2
        places = {"N": (cx, z1 + pad), "E": (x1 + pad, cz), "S": (cx, z0 - pad), "W": (x0 - pad, cz)}
        return {letter: QPointF(*self.renderer.project((-x, 0.0, z), self.camera, self.width(), self.height()))
                for letter, (x, z) in places.items()}

    def corner_text(self) -> str:
        """What the picture says of the camera's corner: "Seen from the SW corner", or nothing between corners."""
        name = ms.corner_at(self.camera.yaw)
        return f"Seen from the {name} corner" if name else ""

    def _paint_compass(self, p: QPainter, area: QRectF) -> None:
        font = QFont(self.font())
        font.setBold(True)
        p.setFont(font)
        metrics = QFontMetricsF(font)
        radius = metrics.height() * 0.75
        for letter, point in self.compass_marks().items():
            disc = QRectF(point.x() - radius, point.y() - radius, 2 * radius, 2 * radius)
            p.setPen(QPen(_colour("accent" if letter == "N" else "border", 230), 1.2))
            p.setBrush(_colour("surface", 215))
            p.drawEllipse(disc)
            p.setPen(_colour("text"))
            p.drawText(disc, int(Qt.AlignCenter), letter)
        p.setBrush(Qt.NoBrush)
        text = self.corner_text()
        if text:
            p.setFont(self.font())
            p.setPen(_colour("text_muted"))
            p.drawText(area, int(Qt.AlignLeft | Qt.AlignBottom), text)

    def card_rect(self, title: str, detail: str) -> QRectF:
        """
        Where the card goes: right of the pointer, above its tip, inside
        the picture - on the left where there's no room on the right, and
        below where there's none above.
        """
        bold, plain = self._card_fonts()
        lines = detail.split("\n")
        width = max([QFontMetricsF(bold).horizontalAdvance(title)]
                    + [QFontMetricsF(plain).horizontalAdvance(line) for line in lines]) + 26
        height = QFontMetricsF(bold).height() + len(lines) * QFontMetricsF(plain).height() + 22
        tip_x, tip_y = self._pointer.x(), self._pointer.y()
        x, y = tip_x + CARD_RIGHT, tip_y - CARD_ABOVE - height
        if x + width > self.width() - 6 and tip_x - CARD_RIGHT - width >= 6:
            x = tip_x - CARD_RIGHT - width
        if y < 6:
            y = tip_y + 2 * CARD_RIGHT          # below the arrow
        return QRectF(max(6.0, min(x, self.width() - width - 6)),
                      max(6.0, min(y, self.height() - height - 6)), width, height)

    def _card_fonts(self):
        bold = QFont(self.font())
        bold.setPointSizeF(max(bold.pointSizeF(), 9.0) + 1.0)
        bold.setBold(True)
        plain = QFont(self.font())
        return bold, plain

    def _paint_card(self, p: QPainter, title: str, detail: str) -> None:
        card = self.card_rect(title, detail)
        path = QPainterPath()
        path.addRoundedRect(card, 8, 8)
        p.fillPath(path, _colour("surface", 238))
        p.setPen(QPen(_colour("accent", 210), 1.2))
        p.drawPath(path)
        bold, plain = self._card_fonts()
        inner = card.adjusted(13, 9, -13, -9)
        p.setFont(bold)
        p.setPen(_colour("text"))
        p.drawText(inner, int(Qt.AlignLeft | Qt.AlignTop), title)
        p.setFont(plain)
        p.setPen(_colour("text_muted"))
        p.drawText(inner, int(Qt.AlignLeft | Qt.AlignBottom), detail)    # its lines, the last at the bottom

    # -- the pointer --------------------------------------------------------------

    def tile_at(self, point: QPointF):
        if self.scene is None or not self.tiles or self.renderer.error:
            return None
        return self.renderer.pick(point.x(), point.y(), self.camera, self.width(), self.height(),
                                  self.tiles)

    def tiles_in(self, box: QRectF) -> list:
        """The tiles the grid shows whose middles are inside `box` of the picture, as `(x, z, level)`s."""
        if self.scene is None or self.renderer.error:
            return []
        out = []
        for tile in self.tiles:
            if not ms.shows(tile) or tile.is_blank:
                continue
            corners = ms.tile_corners(tile)
            middle = tuple(sum(c[i] for c in corners) / 4 for i in range(3))
            x, y = self.renderer.project(middle, self.camera, self.width(), self.height())
            if box.contains(QPointF(x, y)):
                out.append((tile.x, tile.z, tile.level))
        return out

    def batch_at(self, point: QPointF):
        """The batch drawn at a point: an enhanced one's `group` names its pictures."""
        if self.scene is None or self.renderer.error:
            return None
        return self.renderer.pick_batch(point.x(), point.y(), self.camera, self.width(),
                                        self.height())

    def _set_hover(self, key) -> None:
        if key != self.hovered:
            self.hovered = key
            self._highlight_stale = True
            self.schedule()
            self.tile_hovered.emit(key)
        self.update()

    def mousePressEvent(self, event):                             # noqa: N802
        self._press = (event.position(), event.button(), event.modifiers(), self.camera.copy())
        self._dragging = False
        self._box = None
        self._grabbed = bool(self.grabber is not None and event.button() == Qt.LeftButton
                             and not event.modifiers() & (Qt.ShiftModifier | Qt.ControlModifier)
                             and self.grabber.press(event.position()))

    def mouseMoveEvent(self, event):                              # noqa: N802
        point = event.position()
        self._pointer = point
        if self._press is None or not event.buttons():
            self._set_hover(self.tile_at(point))
            return
        start, button, modifiers, camera = self._press
        dx, dy = point.x() - start.x(), point.y() - start.y()
        if not self._dragging and math.hypot(dx, dy) < DRAG_START:
            return
        if self._grabbed:
            self._dragging = True
            self._set_hover(self.tile_at(point))
            self.grabber.move(point)
            return
        if (self.box_select and button == Qt.LeftButton
                and modifiers & (Qt.ControlModifier | Qt.MetaModifier)):
            self._dragging = True
            self._box = QRectF(start, point).normalized()
            self._set_hover(None)
            self.update()
            return
        moving = button == Qt.MiddleButton or (button == Qt.LeftButton
                                               and modifiers & Qt.ShiftModifier)
        if not moving and button != Qt.LeftButton:
            return
        self._dragging = True
        if moving:
            per_pixel = 2 * self.renderer.half_height(camera, self._aspect()) / max(1, self.height())
            # A picture drawn wider across (`Camera.stretch`) moves less across a pixel.
            self.camera.pan = (camera.pan[0] + dx * per_pixel / max(0.05, camera.stretch),
                               camera.pan[1] + dy * per_pixel)
        else:
            self.camera.yaw = (camera.yaw - dx * TURN_PER_PIXEL) % 360.0
            self.camera.pitch = min(ms.TOP_PITCH, max(LOWEST_PITCH, camera.pitch + dy * TILT_PER_PIXEL))
        self._set_hover(None)
        self.camera_changed.emit()
        self.schedule()

    def mouseReleaseEvent(self, event):                           # noqa: N802
        if self._press is None:
            return
        _start, button, modifiers, _camera = self._press
        self._press = None
        if self._grabbed:
            self._grabbed = False
            moved, self._dragging = self._dragging, False
            self.grabber.release(event.position(), moved)
            self._set_hover(self.tile_at(event.position()))
            return
        if self._dragging:
            self._dragging = False
            if self._box is not None:
                box, self._box = self._box, None
                self.tiles_boxed.emit(self.tiles_in(box))
                self.update()
            self._set_hover(self.tile_at(event.position()))
            return
        if button == Qt.LeftButton:
            add = bool(modifiers & (Qt.ControlModifier | Qt.MetaModifier))
            self.tile_clicked.emit(self.tile_at(event.position()), add)

    def wheelEvent(self, event):                                  # noqa: N802
        steps = event.angleDelta().y() / 120.0
        if not steps or self.scene is None:
            return
        zoom = min(ZOOM_MAX, max(ZOOM_MIN, self.camera.zoom * ZOOM_STEP ** steps))
        aspect = self._aspect()
        before = self.renderer.half_height(self.camera, aspect)
        after = before * self.camera.zoom / zoom
        point = event.position()
        across = 2 * point.x() / max(1, self.width()) - 1
        down = 1 - 2 * point.y() / max(1, self.height())
        # The point under the pointer stays where it is.
        px, py = self.camera.pan
        self.camera.pan = (px + (after - before) * aspect * across / max(0.05, self.camera.stretch),
                           py - (after - before) * down)
        self.camera.zoom = zoom
        self.camera_changed.emit()
        self.schedule()
        event.accept()

    def _aspect(self) -> float:
        return self.width() / max(1, self.height())

    def leaveEvent(self, event):                                  # noqa: N802
        super().leaveEvent(event)
        self._pointer = None
        self._set_hover(None)
