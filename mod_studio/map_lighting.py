"""
Light for a map's enhanced look, made here rather than painted: the
lighting texture of every texture group that has one, a texture for the
map's border, and the units' lighting (`lut_chara`), from a sun, the sky
and lamps placed on the map.

Asked for by Zodi, 12 October: "When creating a custom map can we
optionally generate all the lighting textures for all textures that need
one (map lighting, waterside, watersurface, gate, border, watersplash, ect)
similar to those from the game files with the ability to edit the position
of the light source and color of the source", "additionally generate the
border_color texture", and "generating the lut_chara_ 0 and 1 textures".
He picked a sun, the sky and lamps, made in the Map Editor (and the
package's README says how to bake in Blender instead), and the units'
lighting from the new light.

**What the game's are** (measured on 002, 026 and 048, the map research
notes):

- A group's lighting texture shares the colour texture's UVs, covers them
  once (no repeat), and the game draws colour x lighting x 2, so 128 leaves
  a colour as it is. No two faces of a group share a texel of it.
- It is baked light: a sun, with soft shadows, and a coloured sky light
  dimmer in corners and creases. A sun and a sky fit 048's ground: the sun
  from the south west, 33 degrees up, ambient about 120 plus 111 times the
  sun's angle; 002's is a strong sun and a blue purple sky.
- Around each patch of faces the texture is black.
- `lut_chara_<a to d>_0`: 128 by 128, black but for a box at the file's
  first rows, 4 x (grid x + 1) pixels wide and 4 x (grid z + 1) high: a
  block of 2 by 2 values a tile (the grid's tile x, z; the last row and
  column past the grid), each value 2 by 2 pixels. **A letter is the way
  a unit faces** (FFT's facings 0 to 3: south, west, north, east), and a
  tile's four values are the light on four sides of a unit facing so:
  its front left and front right, a little below level (the block's
  first row in the file), and up, a little to its left and right (the
  next row). Measured 20 October: fitted to that, each map's open ground
  points at the sun its ground's shadows show (048: 217 degrees, the
  ground's 220; 002: north north east), the values within about 4 of the
  game's; the four sides' light differing by facing as much as 32 to 153
  on 048's open ground. `lut_chara_<a to d>_1`: 64 by 64 of (128, 128,
  128) with alpha 0 on every map measured.
- A border's colour texture is dark earth, darker further down the map's
  sides (048: about 53 at the top, 13 at the bottom).

**How it is made here.** The model in tile space: X east (the file's x), Y
up (minus the file's y), Z north (the file's z); 28 units a tile, 12 a
height step. Each group's faces are drawn into its texture by their UVs
(`resolution` texels a side at most, then scaled to the texture's size),
each texel taking its place and normal on the face. Shadows come from
depth maps seen from the light, made by scattering points over every face
that casts one (not the highlight panels, shadows, top down icons or water
surfaces); the sky from 48 such maps round the sphere, a texel's sky light
being the share of them it sees, weighed by how squarely it faces each;
lamps from six maps each, round them. Then each patch grows a few texels
past its edges, so the game's filtering never reads the black between
them.

Needs numpy and Pillow; nothing in the engine imports Qt.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Callable, Optional

import numpy as np
from PIL import Image

from . import map_enhanced as me

UNIT = 28.0                 # units a tile
STEP = 12.0                 # units a height step
SKY_DIRECTIONS = 48
#: What a lighting texture's value means: colour x value / 128.
NEUTRAL = 128.0
#: The units' lighting: each `lut_chara_<letter>_0` is for a unit facing
#: one way, as a compass turn (FFT's facings 0 to 3: south, west, north,
#: east), and a tile's four values the light on four of its sides:
#: `(row, column)` in the tile's block (row 0 the file's first), the turn
#: from the facing and the height above level, in degrees. Fitted to the
#: game's own on 002, 026 and 048 (the module's notes).
UNIT_FACINGS = (("a", 180.0), ("b", 270.0), ("c", 0.0), ("d", 90.0))
UNIT_SIDES = (((0, 0), -45.0, -15.0), ((0, 1), 45.0, -15.0), ((1, 0), -90.0, 85.0), ((1, 1), 90.0, 85.0))
#: How much of the sky's light, and of the sun's and the lamps', those
#: sides take (on the lighting textures' scale), and how far above its
#: tile's ground a unit's light is taken: fitted on 048 under its measured
#: light, every tile of its four letters (24 from the game's, value for
#: value, where one light for all four was 40).
UNIT_SKY, UNIT_SUN = 0.6, 0.8
UNIT_LIFT = 12.0
#: Light the ground under a unit throws back onto its lower sides: the
#: ground's colour (0 to 1) times the light on it, over the share of the
#: side's view that is ground. A quarter is as much as 048's values allow
#: (its grass a quarter of white: with it they are as near the game's, 26
#: over every tile and 16 on open ground, where without it 26 and 14); on
#: snow it lights a unit's shaded sides a little, as snow does.
UNIT_GROUND = 0.25
LUT_SIZE, LUT1_SIZE = 128, 64
LUT1_VALUE = (128, 128, 128, 0)
#: Parts whose faces cast no shadow, by a word in their name.
NO_SHADOW_WORDS = ("shadow", "icon", "surface", "splash", "wave")


@dataclass
class Lamp:
    """A light placed on the map: over tile (x, z), `height` steps above its ground."""
    x: float
    z: float
    height: float = 2.0
    colour: tuple = (255, 190, 120)
    strength: float = 1.0
    reach: float = 3.0              # tiles


@dataclass
class Light:
    """
    A sun, the sky and lamps. `sun_turn` is the compass direction the sun
    shines from (0 north, 90 east, 180 south, 270 west), `sun_height` its
    angle above the horizon. Colours are 0 to 255; a strength of 1 gives
    the colour as it is, on a face square to the light. `corner_shade` is
    how much darker corners and creases are under the sky (0 not at all, 1
    as dark as they are hidden from it). The defaults are 048's light,
    measured.
    """
    sun_turn: float = 220.0
    sun_height: float = 33.0
    sun_colour: tuple = (255, 247, 252)
    sun_strength: float = 0.4
    sky_colour: tuple = (255, 245, 242)
    sky_strength: float = 0.61
    corner_shade: float = 0.5
    shadows: bool = True
    softness: float = 0.4
    lamps: list = field(default_factory=list)

    def to_dict(self) -> dict:
        out = asdict(self)
        out["lamps"] = [asdict(lamp) if isinstance(lamp, Lamp) else dict(lamp) for lamp in self.lamps]
        return out

    @classmethod
    def from_dict(cls, data: dict) -> "Light":
        data = dict(data or {})
        names = set(cls.__dataclass_fields__)
        light = cls(**{k: v for k, v in data.items() if k in names and k != "lamps"})
        lamp_names = set(Lamp.__dataclass_fields__)
        light.lamps = [Lamp(**{k: v for k, v in dict(lamp).items() if k in lamp_names})
                       for lamp in data.get("lamps") or []]
        for name in ("sun_colour", "sky_colour"):
            setattr(light, name, tuple(int(c) for c in getattr(light, name)))
        for lamp in light.lamps:
            lamp.colour = tuple(int(c) for c in lamp.colour)
        return light

    def sun_direction(self) -> np.ndarray:
        """The unit vector towards the sun, in tile space."""
        turn, height = math.radians(self.sun_turn), math.radians(self.sun_height)
        return np.array([math.sin(turn) * math.cos(height), math.sin(height),
                         math.cos(turn) * math.cos(height)])


# -- the model ---------------------------------------------------------------------

@dataclass
class Faces:
    """Every triangle of a map's model, in tile space."""
    corners: np.ndarray             # (T, 3, 3)
    normals: np.ndarray             # (T, 3, 3), unit, at each corner
    uvs: np.ndarray                 # (T, 3, 2), (0, 0) untextured
    groups: np.ndarray              # (T,), -1 untextured
    casts: np.ndarray               # (T,), casts a shadow
    tiles: list                     # the polygon's tile (x, z, level) or None, per triangle
    tops: np.ndarray                # (T,), the highest Y of the polygon the triangle is of
    parts: list = field(default_factory=list)   # the polygon's part's name, per triangle (when known)


def _tile_space(position) -> tuple:
    return (float(position[0]), -float(position[1]), float(position[2]))


def casts_shadow(part: str) -> bool:
    """Whether a part's faces cast shadows: not panels, shadows, icons or water surfaces."""
    name = (part or "").lower()
    return not me.is_panel(part) and not any(word in name for word in NO_SHADOW_WORDS)


def faces_of(mesh: me.EnhancedMesh) -> Faces:
    """`mesh`'s triangles (each quad as two, as the Map Editor draws them), panels left out."""
    corners, normals, uvs, groups, casts, tiles, tops, parts = [], [], [], [], [], [], [], []
    for poly in mesh.polygons():
        if me.is_panel(poly.part):
            continue
        block = mesh.blocks[poly.block]
        points = [_tile_space(block.positions[c]) for c in poly.corners]
        if len({tuple(p) for p in points}) < 3:
            continue                                    # no area: an empty face
        file_points = np.array([block.positions[c] for c in poly.corners[:3]], float)
        flat = np.cross(file_points[1] - file_points[0], file_points[2] - file_points[0])
        flat = flat / (np.linalg.norm(flat) or 1.0)
        corner_normals = []
        for c in poly.corners:
            n = np.array(block.normals[c], float) if poly.textured else np.zeros(3)
            if not n.any():
                n = flat * 4096.0
            n = np.array([n[0], -n[1], n[2]])
            corner_normals.append(n / (np.linalg.norm(n) or 1.0))
        corner_uvs = [block.uv(c) if poly.textured else (0.0, 0.0) for c in poly.corners]
        for tri in ((0, 1, 2), (0, 2, 3)) if len(poly.corners) == 4 else ((0, 1, 2),):
            corners.append([points[k] for k in tri])
            normals.append([corner_normals[k] for k in tri])
            uvs.append([corner_uvs[k] for k in tri])
            groups.append(poly.group if poly.textured else -1)
            casts.append(casts_shadow(poly.part))
            tiles.append(poly.tile)
            tops.append(max(p[1] for p in points))
            parts.append(poly.part or "")
    return Faces(np.array(corners, float).reshape(-1, 3, 3), np.array(normals, float).reshape(-1, 3, 3),
                 np.array(uvs, float).reshape(-1, 3, 2), np.array(groups, int), np.array(casts, bool), tiles,
                 np.array(tops, float), parts)


def surface_points(triangles: np.ndarray, spacing: float) -> np.ndarray:
    """Points over every triangle, no two neighbours further apart than about `spacing`."""
    if not len(triangles):
        return np.zeros((0, 3))
    edges = np.linalg.norm(triangles[:, [1, 2, 0]] - triangles, axis=2).max(axis=1)
    steps = np.maximum(1, np.ceil(edges / spacing)).astype(int)
    out = []
    for k in np.unique(steps):
        chosen = triangles[steps == k]
        i, j = np.meshgrid(np.arange(k + 1), np.arange(k + 1))
        inside = (i + j) <= k
        u = (i[inside] / k)[None, :, None]
        v = (j[inside] / k)[None, :, None]
        points = chosen[:, :1] + (chosen[:, 1:2] - chosen[:, :1]) * u + (chosen[:, 2:3] - chosen[:, :1]) * v
        out.append(points.reshape(-1, 3))
    return np.concatenate(out)


def _basis(direction: np.ndarray) -> tuple:
    d = direction / np.linalg.norm(direction)
    helper = np.array([0.0, 1.0, 0.0]) if abs(d[1]) < 0.9 else np.array([1.0, 0.0, 0.0])
    e1 = np.cross(helper, d)
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(d, e1)
    return d, e1, e2


class DepthMap:
    """
    What a direction's light reaches first: for each cell across it, how
    far towards the light the nearest shadow casting face is. Made from
    the faces themselves (`triangles`), or from points scattered over them
    (`points`, quicker for a coarse map).
    """

    def __init__(self, direction: np.ndarray, cell: float, triangles: Optional[np.ndarray] = None,
                 points: Optional[np.ndarray] = None):
        self.d, self.e1, self.e2 = _basis(direction)
        self.cell = cell
        every = (triangles.reshape(-1, 3) if triangles is not None and len(triangles)
                 else points if points is not None and len(points) else np.zeros((1, 3)))
        u, v = every @ self.e1, every @ self.e2
        margin = 4 * cell
        self.u0, self.v0 = u.min() - margin, v.min() - margin
        self.w = int(math.ceil((u.max() + margin - self.u0) / cell)) + 1
        self.h = int(math.ceil((v.max() + margin - self.v0) / cell)) + 1
        self.depth = np.full((self.h, self.w), -np.inf)
        if triangles is not None and len(triangles):
            self._draw(triangles)
        elif points is not None and len(points):
            iu = ((points @ self.e1 - self.u0) / cell).astype(int)
            iv = ((points @ self.e2 - self.v0) / cell).astype(int)
            flat = self.depth.reshape(-1)
            np.maximum.at(flat, iv * self.w + iu, points @ self.d)

    def _draw(self, triangles: np.ndarray) -> None:
        u = (triangles @ self.e1 - self.u0) / self.cell
        v = (triangles @ self.e2 - self.v0) / self.cell
        depth = triangles @ self.d
        for (ax, bx, cx), (ay, by, cy), (da, db, dc) in zip(u, v, depth):
            x0, x1 = int(math.floor(min(ax, bx, cx))), int(math.ceil(max(ax, bx, cx))) + 1
            y0, y1 = int(math.floor(min(ay, by, cy))), int(math.ceil(max(ay, by, cy))) + 1
            x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, self.w), min(y1, self.h)
            det = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
            if x1 <= x0 or y1 <= y0 or abs(det) < 1e-9:
                continue
            xs, ys = np.meshgrid(np.arange(x0, x1) + 0.5, np.arange(y0, y1) + 0.5)
            w0 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / det
            w1 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / det
            w2 = 1 - w0 - w1
            # A little past the edges, so faces meeting at an edge leave no gap.
            inside = (w0 >= -0.05) & (w1 >= -0.05) & (w2 >= -0.05)
            if not inside.any():
                continue
            here = np.where(inside, w0 * da + w1 * db + w2 * dc, -np.inf)
            block = self.depth[y0:y1, x0:x1]
            np.maximum(block, here, out=block)

    def lit(self, points: np.ndarray, normals: np.ndarray, soft: int = 1) -> np.ndarray:
        """How much of the light each point gets, 0 to 1 (a (2 soft + 1) square of cells averaged)."""
        pushed = points + normals * (1.5 * self.cell)
        u = (pushed @ self.e1 - self.u0) / self.cell
        v = (pushed @ self.e2 - self.v0) / self.cell
        depth = pushed @ self.d
        iu, iv = np.floor(u).astype(int), np.floor(v).astype(int)
        bias = 1.5 * self.cell
        seen = np.zeros(len(points))
        count = 0
        for du in range(-soft, soft + 1):
            for dv in range(-soft, soft + 1):
                cu = np.clip(iu + du, 0, self.w - 1)
                cv = np.clip(iv + dv, 0, self.h - 1)
                seen += depth >= self.depth[cv, cu] - bias
                count += 1
        return seen / count


def blocked(origins: np.ndarray, target: np.ndarray, triangles: np.ndarray, chunk: int = 512) -> np.ndarray:
    """
    Whether a face stands between each of `origins` and `target`: rays to
    the target tested against every one of `triangles` (Moller and
    Trumbore's test), a chunk of rays at a time.
    """
    out = np.zeros(len(origins), bool)
    if not len(triangles) or not len(origins):
        return out
    v0 = triangles[:, 0]
    e1, e2 = triangles[:, 1] - v0, triangles[:, 2] - v0
    for start in range(0, len(origins), chunk):
        o = origins[start:start + chunk]
        d = target[None, :] - o
        p = np.cross(d[:, None, :], e2[None, :, :])
        det = np.einsum("rtk,tk->rt", p, e1)
        usable = np.abs(det) > 1e-9
        inv = np.where(usable, 1.0 / np.where(usable, det, 1.0), 0.0)
        t_vec = o[:, None, :] - v0[None, :, :]
        u = np.einsum("rtk,rtk->rt", t_vec, p) * inv
        q = np.cross(t_vec, e1[None, :, :])
        v = np.einsum("rtk,rk->rt", q, d) * inv
        t = np.einsum("rtk,tk->rt", q, e2) * inv
        hit = usable & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-4) & (t < 0.999)
        out[start:start + chunk] = hit.any(axis=1)
    return out


def sky_directions(count: int = SKY_DIRECTIONS) -> np.ndarray:
    """`count` directions spread evenly round the sphere."""
    i = np.arange(count) + 0.5
    y = 1 - 2 * i / count
    r = np.sqrt(1 - y * y)
    angle = math.pi * (3 - math.sqrt(5)) * i
    return np.stack([r * np.cos(angle), y, r * np.sin(angle)], axis=1)


class Lighter:
    """The light at points of a map's model: made once for a bake, asked for every texel."""

    def __init__(self, faces: Faces, light: Light, grounds: Optional[Callable] = None,
                 quality: str = "full", progress: Optional[Callable] = None):
        self.light = light
        self.quality = quality
        casting = faces.corners[faces.casts]
        self.casting = casting
        every = casting.reshape(-1, 3) if len(casting) else faces.corners.reshape(-1, 3)
        extent = float(max(every.max(axis=0) - every.min(axis=0))) if len(every) else UNIT
        fine = extent / (768 if quality == "full" else 256)
        coarse = extent / (192 if quality == "full" else 96)
        self.coarse_points = surface_points(casting, coarse * 0.5)
        sun = light.sun_direction()
        self.sun = sun
        self.sun_maps = []
        total = 1 + SKY_DIRECTIONS + 6 * len(light.lamps)
        done = 0
        if light.shadows and light.sun_height > 0:
            spread = math.radians(6.0 * max(0.0, min(1.0, light.softness)))
            jitters = [sun]
            if spread > 0 and quality == "full":
                _d, e1, e2 = _basis(sun)
                for k in range(4):
                    angle = k * math.pi / 2 + math.pi / 4
                    jitters.append(sun + math.tan(spread) * (math.cos(angle) * e1 + math.sin(angle) * e2))
            self.sun_maps = [DepthMap(d, fine, triangles=casting) for d in jitters]
        done += 1
        if progress:
            progress(done, total)
        self.sky = sky_directions(SKY_DIRECTIONS if quality == "full" else 24)
        self.sky_maps = []
        for d in self.sky:
            self.sky_maps.append(DepthMap(d, coarse, points=self.coarse_points))
            done += 1
            if progress:
                progress(done, total)
        self.lamps = []
        for lamp in light.lamps:
            ground = grounds(lamp.x, lamp.z) if grounds else 0.0
            centre = np.array([lamp.x * UNIT, (ground + lamp.height) * STEP, lamp.z * UNIT])
            # The faces that can stand between it and what it reaches.
            reach = max(lamp.reach, 0.1) * UNIT
            near = casting[np.linalg.norm(casting.mean(axis=1) - centre, axis=1)
                           - np.linalg.norm(casting - casting.mean(axis=1, keepdims=True), axis=2).max(axis=1)
                           < reach] if len(casting) else casting
            self.lamps.append((lamp, centre, near if light.shadows else None))
            done += 6
            if progress:
                progress(done, total)

    def sky_open(self, points: np.ndarray, normals: Optional[np.ndarray]) -> np.ndarray:
        """The share of the sky each point sees: round its normal, weighed by angle, or all round it."""
        seen = np.zeros(len(points))
        weight = np.zeros(len(points))
        up = normals if normals is not None else np.zeros_like(points)
        for d, depth_map in zip(self.sky, self.sky_maps):
            w = np.clip(up @ d, 0, None) if normals is not None else np.full(len(points), max(d[1], 0) + 0.2)
            if not w.any():
                continue
            seen += w * depth_map.lit(points, up, soft=0)
            weight += w
        return np.where(weight > 0, seen / np.maximum(weight, 1e-9), 1.0)

    def terms(self, points: np.ndarray, normals: np.ndarray) -> tuple:
        """
        `(open sky, sun, lamps)` at each point, on a face turned to its
        normal: the share of the sky it sees (0 to 1), how much of the sun
        reaches it, shadows and angle taken (0 to 1), and the lamps' light
        on it (N, 3).
        """
        light = self.light
        open_sky = self.sky_open(points, normals)
        sun = np.zeros(len(points))
        if light.sun_height > 0:
            facing = np.clip(normals @ self.sun, 0, None)
            lit = np.ones(len(points))
            if self.sun_maps:
                soft = 1 if self.quality == "full" else 0
                lit = np.mean([m.lit(points, normals, soft=soft) for m in self.sun_maps], axis=0)
            sun = facing * lit
        lamps = np.zeros((len(points), 3))
        for lamp, centre, near in self.lamps:
            rel = centre[None, :] - points
            dist = np.linalg.norm(rel, axis=1) + 1e-9
            reach = max(lamp.reach, 0.1) * UNIT
            fall = np.clip(1 - dist / reach, 0, None) ** 2
            facing = np.clip((normals * rel).sum(axis=1) / dist, 0, None)
            lit = np.ones(len(points))
            reached = (fall * facing) > 0
            if near is not None and reached.any():
                lit[reached] = ~blocked(points[reached] + normals[reached] * 0.5, centre, near)
            lamps += (np.array(lamp.colour, float) * lamp.strength)[None, :] * (fall * facing * lit)[:, None]
        return open_sky, sun, lamps

    def combine(self, open_sky: np.ndarray, sun: np.ndarray, lamps: np.ndarray) -> np.ndarray:
        """`terms` as light, on the lighting textures' scale (128 leaves a colour as it is)."""
        light = self.light
        sky = np.array(light.sky_colour, float) * light.sky_strength
        out = sky[None, :] * (1 - light.corner_shade * (1 - open_sky))[:, None]
        out = out + (np.array(light.sun_colour, float) * light.sun_strength)[None, :] * sun[:, None]
        return out + lamps

    def colour(self, points: np.ndarray, normals: np.ndarray) -> np.ndarray:
        """The light at each point (N, 3), on the lighting textures' scale."""
        return self.combine(*self.terms(points, normals))


def blur_within(values: np.ndarray, mask: np.ndarray, radius: int) -> np.ndarray:
    """`values` (H, W) smoothed over `radius` texels, only from texels `mask` covers."""
    if radius < 1:
        return values

    def box(a):
        for axis in (0, 1):
            padded = np.concatenate([np.zeros_like(np.take(a, [0], axis=axis))] * 1 + [a], axis=axis)
            c = np.cumsum(padded, axis=axis)
            n = a.shape[axis]
            hi = np.clip(np.arange(n) + radius + 1, 0, n)
            lo = np.clip(np.arange(n) - radius, 0, n)
            a = np.take(c, hi, axis=axis) - np.take(c, lo, axis=axis)
        return a

    weight = mask.astype(float)
    total, count = values * weight, weight
    for _ in range(2):
        total, count = box(total), box(count)
    return np.where(count > 0, total / np.maximum(count, 1e-9), values)


# -- the textures --------------------------------------------------------------------

def _raster(faces: Faces, chosen: np.ndarray, width: int, height: int) -> tuple:
    """Each texel the chosen triangles cover, by their UVs: `(mask, places, normals)`."""
    mask = np.zeros((height, width), bool)
    places = np.zeros((height, width, 3))
    normals = np.zeros((height, width, 3))
    for t in np.nonzero(chosen)[0]:
        uv = faces.uvs[t] * np.array([width, height])
        x0, y0 = np.floor(uv.min(axis=0)).astype(int)
        x1, y1 = np.ceil(uv.max(axis=0)).astype(int) + 1
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, width), min(y1, height)
        if x1 <= x0 or y1 <= y0:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1) + 0.5, np.arange(y0, y1) + 0.5)
        (ax, ay), (bx, by), (cx, cy) = uv
        det = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(det) < 1e-12:
            continue
        w0 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / det
        w1 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / det
        w2 = 1 - w0 - w1
        inside = (w0 >= -0.02) & (w1 >= -0.02) & (w2 >= -0.02)
        if not inside.any():
            continue
        weights = np.stack([w0, w1, w2], axis=-1)[inside]
        rows, cols = np.nonzero(inside)
        rows, cols = rows + y0, cols + x0
        places[rows, cols] = weights @ faces.corners[t]
        n = weights @ faces.normals[t]
        normals[rows, cols] = n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)
        mask[rows, cols] = True
    return mask, places, normals


def grow(image: np.ndarray, mask: np.ndarray, steps: int) -> tuple:
    """`image` spread `steps` texels past `mask`'s edges, each new texel its covered neighbours' mean."""
    image = image.astype(float).copy()
    mask = mask.copy()
    h, w = mask.shape
    for _ in range(steps):
        total = np.zeros_like(image)
        count = np.zeros(mask.shape)
        padded_mask = np.pad(mask, 1)
        padded = np.pad(image * mask[..., None], ((1, 1), (1, 1), (0, 0)))
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            count += padded_mask[1 + dy:1 + dy + h, 1 + dx:1 + dx + w]
            total += padded[1 + dy:1 + dy + h, 1 + dx:1 + dx + w]
        new = (~mask) & (count > 0)
        if not new.any():
            break
        image[new] = total[new] / count[new][:, None]
        mask = mask | new
    return image, mask


def _finish(values: np.ndarray, mask: np.ndarray, size: tuple) -> Image.Image:
    """Grown past the patches' edges, black elsewhere, scaled to `size`: an RGB image."""
    # The game's own grow 6 or 7 texels in 512 (048's ground): 8 here, more
    # in a bigger texture, so filtering far off never reads the black.
    grown, covered = grow(values, mask, max(4, max(mask.shape) // 64))
    grown[~covered] = 0
    image = Image.fromarray(np.clip(np.rint(grown), 0, 255).astype(np.uint8), "RGB")
    if image.size != tuple(size):
        image = image.resize(tuple(size), Image.BILINEAR)
    return image


def bake_size(size: tuple, resolution: int) -> tuple:
    """The size a texture is baked at: its own, no side over `resolution`."""
    w, h = size
    scale = min(1.0, resolution / max(w, h))
    return max(8, int(round(w * scale))), max(8, int(round(h * scale)))


def lighting_textures(faces: Faces, lighter: Lighter, sizes: dict, resolution: int = 512,
                      progress: Optional[Callable] = None) -> dict:
    """`{group: RGB image}`: each group's lighting texture at its size (`sizes`, `{group: (w, h)}`)."""
    out = {}
    for done, (group, size) in enumerate(sorted(sizes.items())):
        w, h = bake_size(size, resolution)
        mask, places, normals = _raster(faces, faces.groups == group, w, h)
        values = np.zeros((h, w, 3))
        if mask.any():
            open_sky, sun, lamps = lighter.terms(places[mask], normals[mask])
            # The sky's share is read from coarse maps: smoothed over a few
            # texels it shades as the game's does, without their blocks.
            sky = np.zeros((h, w))
            sky[mask] = open_sky
            open_sky = blur_within(sky, mask, max(1, round(max(w, h) / 160)))[mask]
            values[mask] = lighter.combine(open_sky, sun, lamps)
        out[group] = _finish(values, mask, (w, h))
        if progress:
            progress(done + 1, len(sizes))
    return out


def _noise(width: int, height: int, seed: int = 7) -> np.ndarray:
    """Soft earthy noise, about 1 on average, in a texture's own space."""
    rng = np.random.default_rng(seed)
    out = np.zeros((height, width))
    for scale, amount in ((4, 0.5), (16, 0.3), (64, 0.2)):
        grid = rng.random((scale + 1, scale + 1))
        small = Image.fromarray((grid * 255).astype(np.uint8), "L").resize((width, height), Image.BICUBIC)
        out += (np.asarray(small, float) / 255 - 0.5) * amount
    return 1 + out * 0.5


def border_colour(faces: Faces, group: int, size: tuple, colour: tuple, resolution: int = 512) -> Image.Image:
    """
    A border's colour texture: `colour` at the top of its faces, darker
    down them to about a fifth at the bottom of the map's sides, with a
    little noise, as the game's dark earth sides are.
    """
    w, h = bake_size(size, resolution)
    chosen = faces.groups == group
    mask, places, _normals = _raster(faces, chosen, w, h)
    ys = faces.corners[chosen][:, :, 1] if chosen.any() else np.zeros((0, 3))
    bottom = float(ys.min()) if len(ys) else 0.0
    # Each face's top, smoothed across its neighbours: faces of a border
    # meet at different heights, and the shade runs on across them.
    top_face = blur_within(_raster_value(faces, chosen, w, h, faces.tops), mask, max(2, w // 24))
    span = np.maximum(top_face - bottom, 1e-3)
    depth = np.clip((places[..., 1] - bottom) / span, 0, 1)
    shade = 0.2 + 0.8 * depth ** 1.3
    values = np.array(colour, float)[None, None, :] * (shade * _noise(w, h))[..., None]
    return _finish(values, mask, size)


def _raster_value(faces: Faces, chosen: np.ndarray, width: int, height: int, per_triangle: np.ndarray) -> np.ndarray:
    """One value per triangle (`per_triangle`), drawn into the texture at each texel its triangle covers."""
    out = np.zeros((height, width))
    for t in np.nonzero(chosen)[0]:
        uv = faces.uvs[t] * np.array([width, height])
        x0, y0 = np.floor(uv.min(axis=0)).astype(int)
        x1, y1 = np.ceil(uv.max(axis=0)).astype(int) + 1
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, width), min(y1, height)
        if x1 <= x0 or y1 <= y0:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1) + 0.5, np.arange(y0, y1) + 0.5)
        (ax, ay), (bx, by), (cx, cy) = uv
        det = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(det) < 1e-12:
            continue
        w0 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / det
        w1 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / det
        inside = (w0 >= -0.02) & (w1 >= -0.02) & (1 - w0 - w1 >= -0.02)
        out[y0:y1, x0:x1][inside] = per_triangle[t]
    return out


def ground_colour(image: Optional[Image.Image]) -> tuple:
    """A border's colour from the map's ground texture: its mean, less the black between patches, darkened."""
    if image is None:
        return (66, 52, 46)
    a = np.asarray(image.convert("RGB").resize((256, 256)), float).reshape(-1, 3)
    a = a[a.sum(axis=1) > 30]
    if not len(a):
        return (66, 52, 46)
    return tuple(int(round(v)) for v in a.mean(axis=0) * 0.6)


def _towards(turn: float, height: float) -> np.ndarray:
    """The unit vector a compass `turn` round (0 north, 90 east) and `height` degrees up, in tile space."""
    t, h = math.radians(turn), math.radians(height)
    return np.array([math.sin(t) * math.cos(h), math.sin(h), math.cos(t) * math.cos(h)])


def ground_colours(faces: Faces, pictures: dict, size_x: int, size_z: int) -> np.ndarray:
    """
    `(size_z, size_x, 3)`: the colour (0 to 1) of the ground drawn for each
    tile of the grid, the mean of its faces turned up (water's surface
    among them, not shadows or icons lying on the ground), read off their
    groups' colour textures (`pictures`, `{group: image}`) at their corners
    and middles; mid grey for a tile with none.
    """
    total = np.zeros((size_z, size_x, 3))
    count = np.zeros((size_z, size_x))
    arrays = {group: np.asarray(image.convert("RGB"), float) / 255.0 for group, image in pictures.items()}
    for t, tile in enumerate(faces.tiles):
        group = int(faces.groups[t])
        if tile is None or tile[2] != 0 or group not in arrays:
            continue
        part = (faces.parts[t] if t < len(faces.parts) else "").lower()
        if any(word in part for word in ("shadow", "icon")) or (not faces.parts and not faces.casts[t]):
            continue
        x, z = int(tile[0]), int(tile[1])
        if not (0 <= x < size_x and 0 <= z < size_z) or faces.normals[t].mean(axis=0)[1] < 0.7:
            continue
        a = arrays[group]
        h, w = a.shape[:2]
        samples = np.concatenate([faces.uvs[t], faces.uvs[t].mean(axis=0, keepdims=True)])
        px = np.clip((samples[:, 0] * w).astype(int), 0, w - 1)
        py = np.clip((samples[:, 1] * h).astype(int), 0, h - 1)
        total[z, x] += a[py, px].mean(axis=0)
        count[z, x] += 1
    out = np.full((size_z, size_x, 3), 0.5)
    seen = count > 0
    out[seen] = total[seen] / count[seen][:, None]
    return out


def units_lighting(lighter: Lighter, size_x: int, size_z: int, ground: Callable,
                   under: Optional[np.ndarray] = None) -> tuple:
    """
    `({letter: lut_chara_<letter>_0}, lut_chara_X_1)` for a map whose grid
    is `size_x` by `size_z`: for each way a unit faces (`UNIT_FACINGS`), a
    block of four values a tile over (size + 1) tiles each way, each value
    2 by 2 pixels, from the file's first row (the image's bottom): the
    light on the four sides `UNIT_SIDES` names of a unit standing on the
    tile facing so, its sun and lamps shadowed as the map's are, and the
    light its ground throws back when `under` gives the ground's colours
    (`ground_colours`); and the second, as every map's is. `ground(x, z)`
    is the height in steps of the ground there.
    """
    light = lighter.light
    tiles_x, tiles_z = size_x + 1, size_z + 1
    xs, zs = np.meshgrid(np.arange(tiles_x) + 0.5, np.arange(tiles_z) + 0.5)
    heights = np.array([[ground(x, z) for x, z in zip(row_x, row_z)] for row_x, row_z in zip(xs, zs)])
    points = np.stack([xs * UNIT, heights * STEP + UNIT_LIFT, zs * UNIT], axis=-1).reshape(-1, 3)
    sky = np.array(light.sky_colour, float) * light.sky_strength
    sun = np.array(light.sun_colour, float) * light.sun_strength
    thrown = np.zeros((len(points), 3))
    if under is not None and size_x and size_z:
        # The past-the-grid row and column take the colour of the tile beside them.
        colours = np.asarray(under, float)[np.minimum(np.arange(tiles_z), size_z - 1)][:, np.minimum(
            np.arange(tiles_x), size_x - 1)].reshape(-1, 3)
        on_ground = points - np.array([0.0, UNIT_LIFT - 2.0, 0.0])
        thrown = colours * lighter.colour(on_ground, np.tile(np.array([0.0, 1.0, 0.0]), (len(points), 1)))
    firsts = {}
    for letter, facing in UNIT_FACINGS:
        values = np.zeros((2 * tiles_z, 2 * tiles_x, 3))
        for (row, column), turn, height in UNIT_SIDES:
            towards = _towards(facing + turn, height)
            normals = np.tile(towards, (len(points), 1))
            open_sky, sun_on, lamps = lighter.terms(points, normals)
            here = (UNIT_SKY * sky[None, :] * (1 - light.corner_shade * (1 - open_sky))[:, None]
                    + UNIT_SUN * (sun[None, :] * sun_on[:, None] + lamps)
                    + UNIT_GROUND * thrown * (1 - towards[1]) / 2)
            values[row::2, column::2] = here.reshape(tiles_z, tiles_x, 3)
        values = np.clip(np.rint(values), 0, 255).astype(np.uint8)
        lut = np.zeros((LUT_SIZE, LUT_SIZE, 3), np.uint8)
        doubled = values.repeat(2, axis=0).repeat(2, axis=1)
        h, w = min(doubled.shape[0], LUT_SIZE), min(doubled.shape[1], LUT_SIZE)
        # The file's first rows are the image's last: z grows up the image.
        lut[LUT_SIZE - h:, :w] = doubled[:h, :w][::-1]
        firsts[letter] = Image.fromarray(lut, "RGB")
    second = Image.new("RGBA", (LUT1_SIZE, LUT1_SIZE), LUT1_VALUE)
    return firsts, second


# -- a map, lit ---------------------------------------------------------------------

#: The tables a map's lighting is found by: its groups' textures, and its
#: units' lighting per facing (Key3 0 to 3 `lut_chara_a_0` to `d_0`, 4 to 7
#: `lut_chara_a_1` to `d_1`; `Unknown8` per story lighting, `Unknown10` per
#: random battle).
TEXTURE_TABLE, SYSTEM_TABLE = "RefinedBgTexture", "RefinedBgSystemTexture"


@dataclass
class Made:
    """What lighting a map made: textures to put in the mod, and table rows naming them."""
    textures: dict = field(default_factory=dict)    # {texture file name: image}
    rows: dict = field(default_factory=dict)        # {table: {(map, key2, key3): {column: value}}}
    notes: list = field(default_factory=list)


def _json_list(text) -> list:
    import json
    if isinstance(text, list):
        return text
    try:
        value = json.loads(text or "[]")
        return value if isinstance(value, list) else []
    except (TypeError, ValueError):
        return []


def _list_text(values: list) -> str:
    import json
    return json.dumps(values, separators=(",", ":"))


def _image_size(path) -> Optional[tuple]:
    try:
        with Image.open(path) as image:
            return image.size
    except (OSError, ValueError, TypeError):
        return None


def grid_ground(tiles: dict) -> tuple:
    """`(size x, size z, ground(x, z))` from a grid's ground level tiles (`{(x, z, level): Tile}`)."""
    ground_tiles = {(x, z): t for (x, z, level), t in (tiles or {}).items() if level == 0}
    if not ground_tiles:
        return 0, 0, (lambda x, z: 0.0)
    size_x = max(x for x, _z in ground_tiles) + 1
    size_z = max(z for _x, z in ground_tiles) + 1

    def ground(x: float, z: float) -> float:
        tile = ground_tiles.get((min(max(int(x), 0), size_x - 1), min(max(int(z), 0), size_z - 1)))
        if tile is None:
            return 0.0
        return float(tile.get("height")) + float(tile.get("slope_height")) / 2
    return size_x, size_z, ground


def one_lighting_groups(found: list, names: dict) -> list:
    """
    The groups of `names` (`{group: lighting texture name}`, one lighting's)
    whose lighting texture is the same in every lighting of `found`
    (`map_enhanced.lightings`): a group a mod adds has one. Made for one
    lighting, such a group is lit that way in every battle (Zodi's stress
    test of 20 October: Make for random battle C relit the new glacier for
    all of them).
    """
    if len(found) < 2:
        return []
    return sorted(g for g, name in names.items()
                  if all(other.pictures.get(g) is not None and other.pictures[g].lighting == name for other in found))


def light_map(game_dir, number: int, light: Light, sqlite_path=None, mesh_file=None,
              picture_files: Optional[dict] = None, rows: Optional[dict] = None,
              tiles: Optional[dict] = None, which: Optional[int] = None, lighting: bool = True,
              border: bool = True, border_tint: Optional[tuple] = None, units: bool = True,
              resolution: int = 1024, quality: str = "full",
              progress: Optional[Callable] = None) -> Made:
    """
    Map `number` lit by `light`: its groups' lighting textures, its
    border's colour texture, and its units' lighting, for the map as a mod
    has it (`mesh_file`, `picture_files` `{texture name: file}`, `rows`
    `{table: {key: fields}}`, `tiles` its grid as edited).

    `which` is the lighting (`map_enhanced.lightings`' place) the textures
    are for, or None for every lighting the map has: each group's usual
    texture is made, and every row naming another for a lighting is
    pointed at it, so the map is lit one way in every battle. Textures of
    one lighting take that lighting's names, and no row changes.
    """
    from pathlib import Path
    from . import map_package as mpk
    game_dir = Path(game_dir)
    rows = rows or {}
    made = Made()
    replaced = {name.lower(): Path(path) for name, path in (picture_files or {}).items()}
    mesh = me.read_mesh(Path(mesh_file or me.mesh_path(game_dir, number)).read_bytes())
    found = me.lightings(game_dir, number, sqlite_path, rows.get(TEXTURE_TABLE))
    if not found:
        made.notes.append(f"map {number:03d} names no textures, so it has nothing to light")
        return made
    chosen = found[0] if which is None else found[min(max(int(which), 0), len(found) - 1)]
    folder = me.texture_folder(game_dir, number)

    def size_of(name: Optional[str], fallback: Optional[str] = None) -> tuple:
        for candidate in (name, fallback):
            if candidate:
                size = _image_size(replaced.get(candidate.lower(), folder / candidate))
                if size:
                    return size
        return (512, 512)

    faces = faces_of(mesh)
    size_x, size_z, ground = grid_ground(tiles)
    lighter = Lighter(faces, light, ground, quality=quality, progress=progress)
    texture_rows, _added = mpk.map_rows(sqlite_path, TEXTURE_TABLE, number, rows.get(TEXTURE_TABLE))

    def point_rows(table: str, current: dict, key3s, name_stem: str) -> None:
        """Every entry of those rows names `name_stem` (for every lighting)."""
        for (key2, key3), fields in current.items():
            if key3 not in key3s(key2):
                continue
            changes = {}
            for column in ("Unknown8", "Unknown18") if table == TEXTURE_TABLE else ("Unknown8", "Unknown10"):
                values = _json_list(fields.get(column))
                if values and any(v != name_stem for v in values):
                    changes[column] = _list_text([name_stem] * len(values))
            if changes:
                made.rows.setdefault(table, {})[(number, key2, key3)] = changes

    if lighting:
        sizes, names = {}, {}
        for group, entry in sorted(chosen.pictures.items()):
            if not entry.lighting or group not in set(faces.groups.tolist()):
                continue
            names[group] = entry.lighting
            sizes[group] = bake_size(size_of(entry.lighting, entry.colour[0] if entry.colour else None),
                                     resolution)
        for group, image in lighting_textures(faces, lighter, sizes, resolution).items():
            made.textures[names[group]] = image
            if which is None:
                stem = Path(names[group]).stem
                point_rows(TEXTURE_TABLE, texture_rows, lambda g, group=group: (1, 2) if g == group else (),
                           stem)
        if not names:
            made.notes.append("no texture group of the model has a lighting texture")
        shared = one_lighting_groups(found, names) if which is not None else []
        if shared:
            said = ", ".join(f"group_{g}" for g in shared[:-1]) + (" and " if len(shared) > 1 else "") \
                + f"group_{shared[-1]}"
            made.notes.append(f"{said} {'has' if len(shared) == 1 else 'have'} one lighting texture for every "
                              f"battle, so {'it is' if len(shared) == 1 else 'they are'} lit this way in all of "
                              f"them")
    if border:
        borders = sorted({poly.group for poly in mesh.polygons()
                          if poly.textured and "border" in (poly.part or "").lower()})
        if not borders:
            made.notes.append("no part of the model is a border (a part with border in its name)")
        ground_image = None
        if 0 in chosen.pictures and chosen.pictures[0].colour:
            name = chosen.pictures[0].colour[0]
            try:
                ground_image = Image.open(replaced.get(name.lower(), folder / name))
                ground_image.load()
            except (OSError, ValueError):
                ground_image = None
        tint = tuple(border_tint) if border_tint else ground_colour(ground_image)
        for group in borders:
            entry = chosen.pictures.get(group)
            if entry is None or not entry.colour:
                continue
            name = entry.colour[0]
            size = bake_size(size_of(name), min(resolution, 512))
            made.textures[name] = border_colour(faces, group, size, tint, resolution)
            if which is None:
                point_rows(TEXTURE_TABLE, texture_rows, lambda g, group=group: (0,) if g == group else (),
                           Path(name).stem)
    if units:
        system_rows, _added = mpk.map_rows(sqlite_path, SYSTEM_TABLE, number, rows.get(SYSTEM_TABLE))
        if not system_rows:
            made.notes.append(f"map {number:03d} has no {SYSTEM_TABLE} rows, so no units' lighting")
        elif not size_x:
            made.notes.append("the map has no battle grid, so no units' lighting")
        else:
            pictures = {}
            for group, entry in chosen.pictures.items():
                if entry.colour and group in set(faces.groups.tolist()):
                    try:
                        with Image.open(replaced.get(entry.colour[0].lower(), folder / entry.colour[0])) as image:
                            pictures[group] = image.convert("RGB")
                    except (OSError, ValueError):
                        pass
            under = ground_colours(faces, pictures, size_x, size_z)
            firsts, second = units_lighting(lighter, size_x, size_z, ground, under)
            letters = [letter for letter, _turn in UNIT_FACINGS]
            for (key2, key3), fields in sorted(system_rows.items()):
                story, random_ = _json_list(fields.get("Unknown8")), _json_list(fields.get("Unknown10"))
                if which is None or chosen.kind != "random":
                    index = 0 if which is None else chosen.index
                    stem = story[index] if index < len(story) else (story[0] if story else None)
                else:
                    stem = random_[chosen.index] if chosen.index < len(random_) else None
                if not stem:
                    continue
                made.textures[f"{stem}.tga"] = firsts[letters[key3 % 4]] if key3 < 4 else second
                if which is None:
                    point_rows(SYSTEM_TABLE, {(key2, key3): fields}, lambda g: (key3,), stem)
    return made


def save_made(made: Made, folder) -> dict:
    """Writes `made`'s textures into `folder` as PNG: `{texture file name: PNG}`."""
    from pathlib import Path
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    out = {}
    for name, image in sorted(made.textures.items()):
        path = folder / f"{Path(name).stem}.png"
        image.save(path)
        out[name] = path
    return out
