"""
Rain and snow over an event's map, as the game draws them (Zodi, 22
October's afternoon, with screenshots of event 004's rain and of a snowy
scene, and the game's `bg/textures/weather.tga`: "the top row is for snow
and the bottom row is for rain").

**The sheet** (`SHEET`) is 256 by 256 in cells of 64 (`CELL`): the top
row's first three are snowflakes, small to large, soft round dots; the
second row's first is a raindrop, a thin line with the start of its splash
at its foot, and the three after it its splash: a burst, a ring of
droplets, the ring breaking up. Its colours are flat (grey for the snow,
near black for the rain) and the shapes are in its alpha, so they are
drawn in colours of their own: rain added to what is under it (in his
screenshot a streak lifts the sky's 31, 51, 78 to about 66, 86, 113:
`RAIN_ADD`), snow white over it.

**Rain** falls in the map's world, straight down onto the top of the map's
tiles (the upper level's where a place has one: `surface_tops`), and only
there: each drop a streak drawn from the drop's picture, stretching and
thinning as it falls, then its splash's three pictures where it lands
(`drops`). What of a streak or a splash the map stands in front of isn't
drawn, as a unit behind a wall isn't (`EventMap.paint_weather`). In his
screenshots a light rain shows about a dozen streaks at once, each about
an eighth of the screen long.

**Snow** isn't in the map's world: flakes of the three sizes drift down
over the whole picture, the larger the faster, in front of the map and its
units (`flakes`).

How many, how fast and how big are chosen to look like his screenshots,
not read from the game. Without the sheet (textures not unpacked), the
same shapes are drawn plainly (`plain_sheet`).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QRadialGradient

from ... import map_enhanced as me
from .. import map_scene as ms

#: The game's weather pictures, in the unpacked game (or a mod's in its place).
SHEET = me.TEXTURE_FOLDER + "/weather.tga"
CELL = 64
#: The cells, (column, row): the snowflakes small to large, the raindrop, its splash's three.
SNOW_CELLS = ((0, 0), (1, 0), (2, 0))
DROP_CELL = (0, 1)
SPLASH_CELLS = ((1, 1), (2, 1), (3, 1))
#: Where each splash picture touches the ground, in its cell: the burst's foot, the rings' middle.
SPLASH_FOOT = ((32.0, 37.0), (32.0, 31.5), (32.0, 31.0))
#: The raindrop in its cell: its line's column (drawn a pixel or two wide,
#: the strip of the cell beside it would only thin it out), and its top and foot.
DROP_ACROSS = (32.0, 33.0)
DROP_TOP, DROP_FOOT = 15.0, 36.0

#: Light, normal and heavy rain (an event's weather 2, 3 and 4): raindrops
#: falling at once over the map, per place rain falls on.
DROPS = {2: 0.22, 3: 0.45, 4: 0.9}
#: Snowflakes at once over a picture of 1,920 by 1,080, for the same.
FLAKES = {2: 45, 3: 75, 4: 120}
#: A raindrop: how high over where it lands it starts and how long it
#: falls (seconds), how long its streak is when it lands (the world's
#: units: it starts at `RAIN_STRETCH`'s first share of that and ends at
#: its second), how wide it is on a 1,080 line picture from start to end,
#: and the pause before the next drop (seconds, from the first to the second).
RAIN_HEIGHT, RAIN_FALL = 160.0, 0.34
RAIN_STREAK = 34.0
RAIN_STRETCH = (0.55, 1.15)
RAIN_WIDTH = (2.4, 0.9)
RAIN_PAUSE = (0.05, 0.35)
#: Each splash picture's time (seconds), and how wide a cell is drawn, in the world's units.
SPLASH_FRAME = 0.07
SPLASH_UNITS = 10.0
#: How much a raindrop and its splash add to what is under them, at full strength.
RAIN_ADD, SPLASH_ADD = 46, 70
#: The snow's colour, and for small, medium and large flakes how far they
#: fall in a second (shares of the picture's height), how far they sway
#: (pixels on 1,080 lines) and how big they are drawn (their cell's share).
SNOW_COLOUR = (246, 248, 255)
SNOW_SPEED = (0.055, 0.085, 0.13)
SNOW_SWAY = (6.0, 10.0, 16.0)
SNOW_SIZE = (1.0, 1.0, 1.15)
#: The shares of small and medium flakes (the rest large).
SNOW_SHARES = (0.5, 0.82)
#: The picture's height the sizes above are for.
LINES = 1080.0


def unit(*values) -> float:
    """A number in [0, 1) fixed by `values`: the same drop at the same time falls the same way, played again."""
    h = 0x9E3779B97F4A7C15
    for value in values:
        h = (h ^ ((int(value) & 0xFFFFFFFF) + 0x9E3779B9 + (h << 6) + (h >> 2))) & 0xFFFFFFFFFFFFFFFF
        h = ((h ^ (h >> 30)) * 0xBF58476D1CE4E5B9) & 0xFFFFFFFFFFFFFFFF
        h = ((h ^ (h >> 27)) * 0x94D049BB133111EB) & 0xFFFFFFFFFFFFFFFF
        h ^= h >> 31
    return (h >> 11) / float(1 << 53)


# =============================================================================
# Rain
# =============================================================================

def surface_tops(tiles) -> list:
    """
    The top of each place of the map rain falls on: for each x and z, the
    upper level's tile where it has one, else the ground's, as its four
    corners in world space (`map_scene.tile_corners`); blank places none.
    An upper level place the cursor can't stop on is no tile, as for the
    units standing there (`EventMap.ground_view`): 056's are all 3 steps up.
    """
    top = {}
    for tile in tiles:
        if tile.is_blank or not ms.shows(tile) or (tile.level and tile.no_cursor):
            continue
        key = (tile.x, tile.z)
        if key not in top or tile.level > top[key].level:
            top[key] = tile
    return [ms.tile_corners(top[key]) for key in sorted(top)]


def _bilinear(corners, a: float, b: float) -> tuple:
    c0, c1, c2, c3 = corners
    return tuple((1 - a) * (1 - b) * c0[i] + a * (1 - b) * c1[i] + a * b * c2[i] + (1 - a) * b * c3[i]
                 for i in range(3))


@dataclass(frozen=True)
class Drop:
    """A raindrop at one moment: where it lands (world space), and how far through its fall it is (`fall`,
    0 to 1) or which of its splash's pictures shows (`splash`, 0 to 2)."""
    ground: tuple
    fall: Optional[float] = None
    splash: Optional[int] = None


def drops(surfaces: list, weather: int, seconds: float) -> list:
    """
    The raindrops falling or splashing at `seconds` over `surfaces`
    (`surface_tops`) in `weather` (light, normal or heavy rain: `DROPS`):
    each drop falls, splashes and pauses in turn, landing somewhere new each
    time, the same at the same time however the clock got there.
    """
    density = DROPS.get(int(weather), 0.0)
    if not surfaces or not density:
        return []
    count = max(4, int(round(density * len(surfaces))))
    splash = len(SPLASH_CELLS) * SPLASH_FRAME
    out = []
    for k in range(count):
        cycle = RAIN_FALL + splash + RAIN_PAUSE[0] + (RAIN_PAUSE[1] - RAIN_PAUSE[0]) * unit(k, 1)
        moment = max(0.0, seconds) + unit(k, 2) * cycle
        turn = math.floor(moment / cycle)
        into = moment - turn * cycle
        if into >= RAIN_FALL + splash:
            continue
        corners = surfaces[int(unit(k, turn, 3) * len(surfaces)) % len(surfaces)]
        ground = _bilinear(corners, 0.1 + 0.8 * unit(k, turn, 4), 0.1 + 0.8 * unit(k, turn, 5))
        if into < RAIN_FALL:
            out.append(Drop(ground, fall=into / RAIN_FALL))
        else:
            out.append(Drop(ground, splash=min(len(SPLASH_CELLS) - 1, int((into - RAIN_FALL) / SPLASH_FRAME))))
    return out


def streak(drop: Drop) -> tuple:
    """`(foot, top, width on 1,080 lines)`: a falling drop's streak in world space."""
    u = min(1.0, max(0.0, drop.fall or 0.0))
    x, y, z = drop.ground
    foot_y = y + RAIN_HEIGHT * (1.0 - u)
    length = RAIN_STREAK * (RAIN_STRETCH[0] + (RAIN_STRETCH[1] - RAIN_STRETCH[0]) * u)
    width = RAIN_WIDTH[0] + (RAIN_WIDTH[1] - RAIN_WIDTH[0]) * u
    return (x, foot_y, z), (x, foot_y + length, z), width


def splash_box(x: float, y: float, size: float, picture: int) -> QRectF:
    """Where splash picture `picture` (0 to 2) is drawn, `size` across, for a drop landing at `x`, `y` on the
    picture: its foot there (`SPLASH_FOOT`)."""
    foot_x, foot_y = SPLASH_FOOT[picture]
    return QRectF(x - foot_x / CELL * size, y - foot_y / CELL * size, size, size)


# =============================================================================
# Snow
# =============================================================================

@dataclass(frozen=True)
class Flake:
    """A snowflake on the picture: its middle and its size (0 small, 1 medium, 2 large)."""
    x: float
    y: float
    size: int


def flakes(weather: int, width: float, height: float, seconds: float) -> list:
    """The snowflakes at `seconds` over a picture `width` by `height`, for `weather` (`FLAKES`)."""
    count = FLAKES.get(int(weather), 0)
    if not count or width <= 0 or height <= 0:
        return []
    count = max(1, int(round(count * width * height / (1920.0 * LINES))))
    scale = height / LINES
    out = []
    for k in range(count):
        pick = unit(k, 11)
        size = 0 if pick < SNOW_SHARES[0] else 1 if pick < SNOW_SHARES[1] else 2
        margin = CELL * scale
        span = height + 2 * margin
        fall = SNOW_SPEED[size] * height * (0.8 + 0.4 * unit(k, 12))
        y = (unit(k, 13) * span + fall * seconds) % span - margin
        sway = SNOW_SWAY[size] * scale * math.sin(seconds * (0.6 + 0.8 * unit(k, 14)) + 6.283 * unit(k, 15))
        x = (unit(k, 16) * width + sway) % width
        out.append(Flake(x, y, size))
    return out


# =============================================================================
# The pictures
# =============================================================================

def cell(sheet: QImage, where: tuple) -> QImage:
    column, row = where
    return sheet.copy(column * CELL, row * CELL, CELL, CELL)


def tinted(picture: QImage, colour: QColor) -> QImage:
    """`picture`'s shape (its alpha) in `colour`."""
    out = QImage(picture.size(), QImage.Format_ARGB32_Premultiplied)
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.drawImage(0, 0, picture)
    p.setCompositionMode(QPainter.CompositionMode_SourceIn)
    p.fillRect(out.rect(), colour)
    p.end()
    return out


def plain_sheet() -> QImage:
    """The sheet's shapes drawn plainly, for a game whose textures aren't unpacked."""
    out = QImage(4 * CELL, 4 * CELL, QImage.Format_ARGB32_Premultiplied)
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing)
    for (column, row), radius in zip(SNOW_CELLS, (6.0, 9.5, 13.0)):
        centre = QPointF(column * CELL + 32.0, row * CELL + 32.0)
        glow = QRadialGradient(centre, radius)
        glow.setColorAt(0.0, QColor(255, 255, 255, 255))
        glow.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(glow)
        p.drawEllipse(centre, radius, radius)
    column, row = DROP_CELL
    p.setPen(QPen(QColor(255, 255, 255, 230), 2.0))
    p.drawLine(QPointF(column * CELL + 32.0, row * CELL + DROP_TOP), QPointF(column * CELL + 32.0, row * CELL + DROP_FOOT))
    for n, (column, row) in enumerate(SPLASH_CELLS):
        foot_x, foot_y = SPLASH_FOOT[n]
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 220 - 50 * n))
        for k in range(8):
            angle = 6.283 * k / 8
            reach = 8.0 + 7.0 * n
            p.drawEllipse(QPointF(column * CELL + foot_x + reach * math.cos(angle),
                                  row * CELL + foot_y + 0.5 * reach * math.sin(angle) - (4.0 if n == 0 else 0.0)),
                          1.6, 1.6)
    p.end()
    return out


class Sheet:
    """The weather pictures, ready to draw: the rain's to add to the picture, the snow's in white."""

    def __init__(self, image: Optional[QImage] = None):
        usable = (image is not None and not image.isNull()
                  and image.width() >= 4 * CELL and image.height() >= 2 * CELL)
        #: Whether a sheet read from a file is drawn, the game's or a mod's (else `plain_sheet`).
        self.from_file = bool(usable)
        source = image if usable else plain_sheet()
        snow = QColor(*SNOW_COLOUR)
        self.snow = [tinted(cell(source, where), snow) for where in SNOW_CELLS]
        self.drop = tinted(cell(source, DROP_CELL), QColor(RAIN_ADD, RAIN_ADD, RAIN_ADD))
        self.splash = [tinted(cell(source, where), QColor(SPLASH_ADD, SPLASH_ADD, SPLASH_ADD))
                       for where in SPLASH_CELLS]
