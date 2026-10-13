"""
Draws a played effect (`effect_player.py`) over a picture of the map: each
particle's frameset as quads cut from the effect's sheet, facing the
camera, blended as the PlayStation blends them.

- **The sheet's colours**: a frame's colour line (16 colours at 4 bits a
  pixel, or the whole 256) turns the sheet into a picture; texels whose
  colour word is 0 aren't drawn, those with the top bit clear are drawn
  solid, and those with it set are blended when the quad is see-through
  (solid otherwise).
- **The blends**: half and half (the picture at half strength over half of
  what is there), add, subtract, and add a quarter. Qt's painter has no
  subtract, so effects are drawn on a `Canvas` (a QImage and its painter):
  a subtracted quad is drawn on a picture of its own and taken off the
  canvas's pixels with numpy, in its turn.
- **Brightness**: a texel is multiplied by its particle's colour over 128,
  as the PlayStation's textured polygons are; a particle without colour
  curves is drawn at the full 255 (ExMateria's renderer multiplies every
  particle's texel by about twice its colour curve's value, 2.2, the same
  for all).
- **Order**: far to near, the newest particle on top, each frameset's quads
  in their order; a depth mode pulls a particle nearer, or fixes it at the
  front or the back.

numpy is imported where it is used, not here: the window builds without
it (the README's promise, held by `test_qt_map_editor`), and the Abilities
page asks `numpy_missing()` before playing an effect.
"""
from __future__ import annotations

import math
import sys
from typing import Callable, Optional

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QImage, QPainter, QPolygonF, QTransform

from mod_studio import effect_files as ef

#: A texel times its particle's colour over 128: full colour is 255 / 128.
FULL_BRIGHTNESS = 255.0 / 128.0
#: How finely a particle's colour is matched to a cached tinted picture.
TINT_STEPS = 32
#: World units an ordering-table bucket is deep (ExMateria's DepthMode, in tiles times 28).
BUCKET = 0.19 * 28.0
#: Depth modes: (pulled nearer by, or fixed at).
DEPTH_PULL = {1: 8 * BUCKET, 5: 16 * BUCKET}
DEPTH_FIXED = {2: 1.0e9, 4: 0.5e9, 3: -1.0e9}
#: Where red, green, blue and alpha sit in a premultiplied ARGB32 pixel's four bytes.
RED, GREEN, BLUE, ALPHA = (2, 1, 0, 3) if sys.byteorder == "little" else (1, 2, 3, 0)
RGB = (RED, GREEN, BLUE)


def numpy_missing() -> Optional[str]:
    """Why an effect can't be drawn here, or None: its blends and colours
    work on a picture's pixels with numpy."""
    try:
        import numpy  # noqa: F401
    except ImportError as exc:
        return str(exc) or "numpy isn't installed"
    return None


def _image(rgba: bytes, width: int, height: int) -> QImage:
    return QImage(rgba, width, height, width * 4, QImage.Format_RGBA8888).copy()


def pixels(image: QImage) -> np.ndarray:
    """A premultiplied ARGB32 picture's pixels as a `(height, width, 4)` array
    of its bytes (see `RGB` and `ALPHA`), written straight to the picture.
    The array doesn't keep the picture: hold on to it while it is used."""
    import numpy as np
    if image.format() != QImage.Format_ARGB32_Premultiplied:
        raise ValueError("pixels() needs a premultiplied ARGB32 picture")
    return np.ndarray((image.height(), image.width(), 4), np.uint8, buffer=image.bits(),
                      strides=(image.bytesPerLine(), 4, 1))


class Canvas:
    """
    A picture effects are drawn on (premultiplied ARGB32) and its painter.
    Between drawings the painter is left as it was given (each drawing
    saves and restores it), because `subtract` ends it and begins it again.
    """

    def __init__(self, image: QImage, hints=QPainter.RenderHints()):
        if image.format() != QImage.Format_ARGB32_Premultiplied:
            raise ValueError("a Canvas needs a premultiplied ARGB32 picture")
        self.image = image
        self.hints = hints
        self.painter = QPainter(image)
        self.painter.setRenderHints(hints)

    def subtract(self, picture: QImage, clip: QRectF, transform: QTransform) -> None:
        """Take `picture`'s `clip`, placed by `transform`, off the canvas's
        colours (each channel stops at 0), its see-through parts not."""
        import numpy as np
        ratio = self.image.devicePixelRatio()
        place = transform * QTransform.fromScale(ratio, ratio)
        bounds = place.mapRect(clip).toAlignedRect().intersected(self.image.rect())
        if bounds.isEmpty():
            return
        layer = QImage(bounds.size(), QImage.Format_ARGB32_Premultiplied)
        layer.fill(0)
        lp = QPainter(layer)
        lp.setTransform(place * QTransform.fromTranslate(-bounds.x(), -bounds.y()))
        lp.drawImage(clip, picture, clip)
        lp.end()
        self.painter.end()
        under = pixels(self.image)[bounds.top():bounds.top() + bounds.height(),
                                   bounds.left():bounds.left() + bounds.width()]
        over = pixels(layer)
        for channel in RGB:
            np.subtract(under[..., channel], np.minimum(under[..., channel], over[..., channel]),
                        out=under[..., channel])
        self.painter.begin(self.image)
        self.painter.setRenderHints(self.hints)

    def end(self) -> None:
        if self.painter.isActive():
            self.painter.end()


class EffectPictures:
    """The effect's sheet as pictures, made as frames ask for them."""

    def __init__(self, effect: ef.EffectFile):
        self.effect = effect
        self._sheets = {}
        self._tinted = {}

    def sheet(self, frame: ef.Frame) -> Optional[dict]:
        """`{"blend": QImage, "solid": QImage, "all": QImage}` for a frame's colour line."""
        texture = self.effect.texture
        if texture is None:
            return None
        key = (frame.eight_bit, frame.second_clut, 0 if frame.eight_bit else frame.palette)
        if key not in self._sheets:
            width, height, rgba, kinds = ef.sheet_rgba(texture, *key)
            parts = {}
            for name, wanted in (("blend", (ef.BLENDED,)), ("solid", (ef.SOLID,)),
                                 ("all", (ef.BLENDED, ef.SOLID))):
                masked = bytearray(rgba)
                for i, kind in enumerate(kinds):
                    if kind not in wanted:
                        masked[4 * i + 3] = 0
                parts[name] = _image(bytes(masked), width, height).convertToFormat(
                    QImage.Format_ARGB32_Premultiplied)
            self._sheets[key] = parts
        return self._sheets[key]

    def tinted(self, frame: ef.Frame, part: str, colour) -> Optional[QImage]:
        """The part of a frame's sheet times `colour` (each 0 to 2), clamped."""
        sheet = self.sheet(frame)
        if sheet is None:
            return None
        steps = tuple(max(0, min(2 * TINT_STEPS, int(round(c * TINT_STEPS)))) for c in colour)
        key = (frame.eight_bit, frame.second_clut, 0 if frame.eight_bit else frame.palette, part,
               steps)
        image = self._tinted.get(key)
        if image is None:
            image = tint(sheet[part], tuple(s / TINT_STEPS for s in steps))
            self._tinted[key] = image
        return image


def tint(image: QImage, colour) -> QImage:
    """`image` times `colour` (each 0 to 2, clamped), keeping its see-through parts."""
    return tint_image(image, tuple(max(0.0, c) for c in colour), (0.0, 0.0, 0.0))


def particle_colour(effect: ef.EffectFile, emitter: int, age: int, curves) -> tuple:
    """A particle's brightness, 0 to about 2 a channel: its colour curves at its
    age over 128, or full."""
    emitters = effect.emitters
    if 0 <= emitter < len(emitters) and emitters[emitter].colour_curve_on:
        out = []
        for index in emitters[emitter].colour_curves:
            curve = curves[index] if 0 <= index < len(curves) else None
            value = curve[age % len(curve)] if curve else 255
            out.append(value / 128.0)
        return tuple(out)
    return (FULL_BRIGHTNESS,) * 3


class Projection:
    """
    Where world points (the map's units) land in the picture: `point(world)`
    gives `(x, y, nearness)`, `ppu` the pixels a world unit spans across.
    """

    def __init__(self, point: Callable, ppu: float):
        self.point, self.ppu = point, ppu


def effect_items(pictures: EffectPictures, frame, origin, projection: Projection,
                 curves=None, scale: float = 1.0) -> list:
    """
    One frame's particles as `(nearness, order, draw)`: `draw(canvas)`
    draws the particle on a `Canvas`. `origin` is the effect's place in the world; the
    player's tiles (x and z along the grid, y up) are turned into the
    world's units (x is the files' -x).
    """
    effect = pictures.effect
    framesets = effect.framesets
    curves = curves if curves is not None else effect.curves
    items = []
    ox, oy, oz = origin
    for index, (emitter, position, velocity, frameset_index, offset, depth, age, _target) in \
            enumerate(frame.particles):
        if not 0 <= frameset_index < len(framesets):
            continue
        frameset = framesets[frameset_index]
        if frameset is None or not frameset.frames:
            continue
        world = (ox - position[0] * 28.0, oy + position[1] * 28.0, oz + position[2] * 28.0)
        sx, sy, near = projection.point(world)
        if depth in DEPTH_FIXED:
            near = DEPTH_FIXED[depth]
        else:
            near += DEPTH_PULL.get(depth, 0.0)
        angle = None
        emitters = effect.emitters
        if 0 <= emitter < len(emitters) and emitters[emitter].align_to_velocity and \
                any(abs(v) > 0.0 for v in velocity):
            ahead = (world[0] - velocity[0] * 28.0, world[1] + velocity[1] * 28.0,
                     world[2] + velocity[2] * 28.0)
            ax, ay, _ = projection.point(ahead)
            if abs(ax - sx) + abs(ay - sy) > 1e-6:
                angle = math.atan2(ay - sy, ax - sx)
        colour = particle_colour(effect, emitter, age, curves)
        items.append((near, (-age, index),
                      _drawer(pictures, frameset, (sx, sy), offset, angle, colour,
                              projection.ppu * scale)))
    return items


def _drawer(pictures, frameset, centre, offset, angle, colour, ppu):
    def draw(canvas: Canvas) -> None:
        for frame in frameset.frames:
            draw_quad(canvas, pictures, frame, centre, offset, angle, colour, ppu)
    return draw


def quad_corners(frame: ef.Frame, centre, offset, angle, ppu) -> list:
    """The quad's corners in the picture: top left, top right, bottom left, bottom right."""
    out = []
    c = s = None
    if angle is not None:
        c, s = math.cos(angle), math.sin(angle)
    for x, y in frame.corners:
        x, y = x + offset[0], y + offset[1]
        if angle is not None:
            x, y = x * c - y * s, x * s + y * c
        out.append(QPointF(centre[0] + x * ppu, centre[1] + y * ppu))
    return out


def _placing(u, v, w, h, corners) -> Optional[QTransform]:
    """
    The transform taking the sheet's rectangle `(u, v, w, h)` to the quad's
    corners (top left, top right, bottom left, bottom right). A straight
    one when the corners make a parallelogram, as nearly all do: Qt draws a
    picture under it several times faster than under a perspective one.
    """
    tl, tr, bl, br = corners
    if abs(tl.x() + br.x() - tr.x() - bl.x()) < 0.01 and abs(tl.y() + br.y() - tr.y() - bl.y()) < 0.01:
        ax, ay = (tr.x() - tl.x()) / w, (tr.y() - tl.y()) / w
        bx, by = (bl.x() - tl.x()) / h, (bl.y() - tl.y()) / h
        return QTransform(ax, ay, bx, by, tl.x() - ax * u - bx * v, tl.y() - ay * u - by * v)
    source = QPolygonF([QPointF(u, v), QPointF(u + w, v), QPointF(u + w, v + h), QPointF(u, v + h)])
    target = QPolygonF([tl, tr, br, bl])
    transform = QTransform()
    return transform if QTransform.quadToQuad(source, target, transform) else None


def draw_quad(canvas: Canvas, pictures: EffectPictures, frame: ef.Frame, centre, offset, angle,
              colour, ppu) -> None:
    p = canvas.painter
    corners = quad_corners(frame, centre, offset, angle, ppu)
    u, v, w, h = ef.frame_uv(frame, pictures.effect.texture)
    if w == 0 or h == 0:
        return
    transform = _placing(u, v, w, h, corners)
    if transform is None:
        return
    clip = QRectF(min(u, u + w), min(v, v + h), abs(w), abs(h))
    quarter = None
    if frame.see_through:
        solid = pictures.tinted(frame, "solid", colour)
        blend = pictures.tinted(frame, "blend", colour)
        if frame.blend == ef.QUARTER:
            quarter = pictures.tinted(frame, "blend", tuple(c / 4.0 for c in colour))
    else:
        solid = pictures.tinted(frame, "all", colour)
        blend = None
    if solid is None:
        return
    mode = frame.blend if blend is not None else None
    p.save()
    # Hard edges, as the PlayStation draws them; antialiased, a turned quad
    # took fifteen times as long to draw.
    p.setRenderHint(QPainter.Antialiasing, False)
    p.setRenderHint(QPainter.SmoothPixmapTransform, False)
    p.setTransform(transform, True)
    placed = p.transform()
    p.setCompositionMode(QPainter.CompositionMode_SourceOver)
    p.drawImage(clip, solid, clip)
    if mode == ef.HALF:
        p.setOpacity(0.5)
        p.drawImage(clip, blend, clip)
    elif mode == ef.ADD:
        p.setCompositionMode(QPainter.CompositionMode_Plus)
        p.drawImage(clip, blend, clip)
    elif mode == ef.QUARTER:
        # A quarter of the picture added. Not Plus at an opacity of 0.25:
        # Qt adds the whole picture, clamps, then mixes a quarter of that in.
        p.setCompositionMode(QPainter.CompositionMode_Plus)
        p.drawImage(clip, quarter, clip)
    p.restore()
    if mode == ef.SUBTRACT:
        canvas.subtract(blend, clip, placed)


# =============================================================================
# Colouring a picture as the effect colours the map and units
# =============================================================================

def affine_of(fold) -> tuple:
    """
    `(scale, bias)` a channel, so `colour * scale + bias` is what `fold`
    makes of a colour: exact for the game's add and dim modes, the nearest
    straight line for its grey ones. `fold(rgb) -> rgb`, 0-1 floats.
    """
    dark, light = fold((0.0, 0.0, 0.0)), fold((1.0, 1.0, 1.0))
    return tuple(light[i] - dark[i] for i in range(3)), tuple(dark)


def is_identity(scale, bias) -> bool:
    return all(abs(s - 1.0) < 1e-3 for s in scale) and all(abs(b) < 1e-3 for b in bias)


def tint_image(image: QImage, scale, bias) -> QImage:
    """`image` with each colour times `scale` plus `bias` (0 to 1 floats, the
    result clamped), its see-through parts kept: a new premultiplied ARGB32
    picture of the same size. Each channel goes through a table, right for
    every pixel but the few partly see-through ones (edges), which are
    worked out one by one."""
    import numpy as np
    out = image.convertToFormat(QImage.Format_ARGB32_Premultiplied)
    out.setDevicePixelRatio(image.devicePixelRatio())
    if out.isNull():
        return out
    flat = pixels(out).reshape(-1, 4)
    alpha = flat[:, ALPHA]
    edges = np.flatnonzero((alpha != 0) & (alpha != 255))
    weight = alpha[edges].astype(np.float32)
    levels = np.arange(256, dtype=np.float32)
    for channel, s, b in zip(RGB, scale, bias):
        values = flat[:, channel]
        table = np.clip(levels * float(s) + 255.0 * float(b) + 0.5, 0.0, 255.0).astype(np.uint8)
        changed = table[values]
        if table[0]:
            np.minimum(changed, alpha, out=changed)          # nothing where there's nothing
        if edges.size:
            exact = values[edges].astype(np.float32) * float(s) + weight * float(b) + 0.5
            changed[edges] = np.clip(exact, 0.0, weight).astype(np.uint8)
        flat[:, channel] = changed
    return out
