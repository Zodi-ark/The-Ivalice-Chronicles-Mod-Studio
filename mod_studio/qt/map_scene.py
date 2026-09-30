"""
What the Map Editor draws, made ready for the graphics card: vertex lists
and pictures for one map in one look, and the battle grid. Pure Python and
Pillow, so it runs on a worker thread (`SceneWorker`); only the upload and
the drawing (`map_render.py`) need the GUI thread.

World space is the files' own, turned so it isn't mirrored: x is the
file's -x, y its -y (up), z its z - GaneshaDx's axes. A tile is 28 units
wide and a height step 12 tall.

**Walls in the way.** The game leaves out the walls between its camera and
the map - an inside map like 026 is a closed box without that - by the
camera corner: each polygon's render properties say which corners it is
left out from, the classic polygons' and the enhanced ones' own (see
`map_enhanced`). The first build switched them at the half-way point
between two corners, so parts of a map popped in and out as it turned; they
now fade over the middle of the turn (`corner_weights`), and at a corner the
map is as the game shows it.

**What moves.** Water, fire and the like play on a loop, as in the game:

- Enhanced, a picture with more than one frame (`gt_2_map048_watersurface_
  color_0` ... `_29`), at `ENHANCED_FRAMES_A_SECOND`, except the ones the
  game's `RefinedBgAnim` table plays when something happens in a battle
  (its kind 2: 37 of those 42 rows are doors and levers), which show their
  first frame.
- Classic, the texture animations the game plays on a loop (GaneshaDx's
  reading of them, and the ones it plays): a rectangle of the texture shown
  from a row of frames, or one of the 16 palettes swapped for the animation
  palettes in turn, each frame lasting its own number of 60ths of a second.
"""
from __future__ import annotations

import array
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from .. import map_classic as mc
from .. import map_enhanced as me
from .workers import Worker

if TYPE_CHECKING:
    # For the annotations only. Pillow is imported where a map is built: this
    # module is imported at startup, and the app starts without Pillow.
    from PIL import Image

ENHANCED, CLASSIC = "enhanced", "classic"

#: The camera corners the game uses, where its camera stands (an angle in
#: the files' ground plane: 0 is +x, east; 90 is +z, north), and the
#: render-properties bit of the polygons the game leaves out from there. The
#: bits are the documents' SW, NW, NE and SE; GaneshaDx leaves out the same
#: bits from the same corners.
CORNERS = ((225.0, 13), (135.0, 12), (45.0, 11), (315.0, 10))
#: Between two corners, the share of the turn over which the walls one
#: leaves out fade into the ones the next does: 0.4 of 90 degrees, 36.
FADE_SPAN = 0.4
#: The camera heights: 26.54 degrees above the ground (GaneshaDx's, the
#: 2:1 of the game's pictures), and a higher one.
LOW_PITCH, HIGH_PITCH, TOP_PITCH = 26.54, 45.0, 89.9

#: How fast an enhanced picture's frames play. Chosen: the game's own rate
#: is in no file or table found. At 15 the 30 frames of a water surface
#: take two seconds, and the 8 of a splash half a second.
ENHANCED_FRAMES_A_SECOND = 15.0
#: `RefinedBgAnim`'s kind for a picture the game plays when something
#: happens in a battle rather than on a loop: 37 of its 42 rows are doors
#: and levers, the others a few pieces of water and light in events.
PLAYED_ON_A_TRIGGER = 2


@dataclass
class Batch:
    """One draw: its vertices, and the pictures to draw them with."""
    kind: str                           # "enhanced", "classic" or "flat"
    floats: array.array
    layout: tuple                       # floats per attribute
    colour: Optional[Image.Image] = None
    light: Optional[Image.Image] = None
    see_through: bool = False           # drawn after the solid ones, blended
    group: Optional[int] = None         # enhanced: the texture group it draws
    #: enhanced: the colour picture's frames when it plays on a loop, the
    #: first being `colour`; empty for a picture that stays still
    frames: list = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.floats) // sum(self.layout)


@dataclass
class UvAnimation:
    """A classic texture animation: a rectangle of the texture shown from a row of frames."""
    canvas: tuple                       # x, y, width, height in the 256 x 1024 texture
    frames: list                        # each frame's top left corner (x, y)
    duration: float                     # seconds a frame
    back_and_forth: bool = False


@dataclass
class PaletteAnimation:
    """A classic palette animation: one of the 16 palettes, swapped for animation palettes in turn."""
    palette: int
    start: int                          # its first animation palette, 0-15
    count: int
    duration: float                     # seconds a frame
    back_and_forth: bool = False


@dataclass
class Scene:
    number: int
    look: str
    batches: list = field(default_factory=list)
    #: everything drawn, and the part of it the camera frames: the map
    #: without the enhanced look's border and shadow, which reach well past it
    bounds: tuple = ((0.0, 0.0, 0.0), (1.0, 1.0, 1.0))
    frame: tuple = ((0.0, 0.0, 0.0), (1.0, 1.0, 1.0))
    #: classic look only: 256 x 1024 palette indices, and a 16 x 32 palette
    #: picture, the map's 16 palettes over the 16 its palette animations use
    classic_indices: Optional[bytes] = None
    classic_palette: Optional[Image.Image] = None
    lights: Optional[mc.Lights] = None
    uv_animations: list = field(default_factory=list)
    palette_animations: list = field(default_factory=list)
    #: the battle grid: its tiles, the file they were read from, the name its
    #: edits are kept under (`map_classic.grid_key`) and every file holding it
    terrain: Optional[mc.Terrain] = None
    grid_file: Optional[str] = None
    grid_key: Optional[str] = None
    grid_files: list = field(default_factory=list)
    #: enhanced look only: `{group: GroupPictures}`, and their folder in the game
    pictures: dict = field(default_factory=dict)
    picture_folder: str = ""
    notes: list = field(default_factory=list)


def world(p) -> tuple:
    return (-p[0], -p[1], p[2])


def _bounds(points) -> tuple:
    if not points:
        return ((0.0, 0.0, 0.0), (1.0, 1.0, 1.0))
    xs, ys, zs = zip(*points)
    return ((min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs)))


def surrounds(part: str) -> bool:
    """
    Whether an enhanced part is the dark border or the shadow drawn round a
    map (61 and 60 of the 108 maps have them): drawn, but not what the
    camera frames, as they reach well past the map (100 units on 048).
    """
    name = part.lower()
    return "border" in name or "shadow" in name


def _triangles(n_corners: int) -> tuple:
    """Enhanced polygons go round their corners: a quad is (0,1,2) and (0,2,3)."""
    return ((0, 1, 2), (0, 2, 3)) if n_corners == 4 else ((0, 1, 2),)


def _classic_triangles(n_corners: int) -> tuple:
    """A classic quad's corners are A B C D with D opposite A: (A,B,C) and (B,D,C)."""
    return ((0, 1, 2), (1, 3, 2)) if n_corners == 4 else ((0, 1, 2),)


def _open_rgba(path: Path) -> Optional[Image.Image]:
    from PIL import Image

    try:
        with Image.open(path) as im:
            return im.convert("RGBA")
    except (OSError, ValueError):
        return None


def _is_see_through(image: Image.Image) -> bool:
    lo, _hi = image.getchannel("A").getextrema()
    return lo < 250


def played_on_a_trigger(sqlite_path, number: int) -> set:
    """
    The texture groups of a map the game's `RefinedBgAnim` table plays when
    something happens (map, row, 0, kind, group); empty without the table.
    """
    if not sqlite_path:
        return set()
    try:
        con = sqlite3.connect(f"file:{Path(sqlite_path).as_posix()}?mode=ro", uri=True)
        try:
            rows = con.execute("SELECT Unknown8 FROM RefinedBgAnim WHERE Key = ? AND Unknown4 = ?",
                               (number, PLAYED_ON_A_TRIGGER)).fetchall()
        finally:
            con.close()
    except sqlite3.Error:
        return set()
    return {group for (group,) in rows}


def build_enhanced(game_dir: Path, number: int, sqlite_path: Optional[Path] = None,
                   state: mc.State = mc.State(), mesh_file: Optional[Path] = None,
                   picture_files: Optional[dict] = None) -> Scene:
    """
    The enhanced look of a map: its mesh, coloured by colour x lighting.
    `mesh_file` and `picture_files` (`{picture name: image file}`) are a
    mod's own, drawn in place of the game's.
    """
    from PIL import Image

    game_dir = Path(game_dir)
    mesh = me.read_mesh(Path(mesh_file or me.mesh_path(game_dir, number)).read_bytes())
    replaced = {name.lower(): Path(path) for name, path in (picture_files or {}).items()}
    scene = Scene(number, ENHANCED)
    folder = game_dir / mc.MAP_FOLDER
    if (folder / mc.gns_name(number)).exists():
        sources = mc.read_gns(folder, number).sources(state)
        if "terrain" in sources:
            scene.grid_file = sources["terrain"].file_name
            scene.terrain = mc.read_mesh((folder / scene.grid_file).read_bytes()).terrain
    pictures = me.pictures(game_dir, number, sqlite_path)
    textures = me.texture_folder(game_dir, number)
    scene.pictures = pictures
    scene.picture_folder = f"{me.TEXTURE_FOLDER}/{number:03d}"
    by_group, points, framed = {}, [], []
    black = array.array("f")
    for poly in mesh.polygons():
        if me.is_panel(poly.part):
            continue
        block = mesh.blocks[poly.block]
        corners = [world(block.positions[c]) for c in poly.corners]
        points.extend(corners)
        if not surrounds(poly.part):
            framed.extend(corners)
        render = float(poly.render)
        if not poly.textured:
            for tri in _triangles(len(corners)):
                for k in tri:
                    black.extend(corners[k] + (0.0, 0.0, 0.0, 1.0, render))
            continue
        buf = by_group.setdefault(poly.group, array.array("f"))
        for tri in _triangles(len(corners)):
            for k in tri:
                buf.extend(corners[k] + block.uv(poly.corners[k]) + (render,))
    scene.bounds = _bounds(points)
    scene.frame = _bounds(framed or points)
    still = played_on_a_trigger(sqlite_path, number)

    def picture(name):
        return _open_rgba(replaced.get(name.lower(), textures / name))

    missing = []
    for group, buf in sorted(by_group.items()):
        entry = pictures.get(group)
        colour = light = None
        frames = []
        if entry and entry.colour:
            colour = picture(entry.colour[0])
            if entry.lighting:
                light = picture(entry.lighting)
            if colour is not None and len(entry.colour) > 1 and group not in still:
                frames = [colour] + [picture(name) for name in entry.colour[1:]]
                # A frame that isn't there shows the first in its place.
                frames = [f if f is not None and f.size == colour.size else colour for f in frames]
        if colour is None:
            missing.append(group)
            colour = Image.new("RGBA", (4, 4), (128, 128, 128, 255))
        scene.batches.append(Batch(ENHANCED, buf, (3, 2, 1), colour, light,
                                   see_through=_is_see_through(colour), group=group, frames=frames))
    if len(black):
        scene.batches.append(Batch("flat", black, (3, 4, 1)))
    if missing:
        scene.notes.append(f"{len(missing)} of this map's pictures are not in the game folder, so "
                           f"what they cover is drawn grey.")
    return scene


def classic_animations(raw: Optional[bytes]) -> tuple:
    """
    `(uv animations, palette animations)` from a mesh's 32 texture animation
    records, the ones the game plays on a loop: GaneshaDx's reading (a UV
    record has 3 at bytes 1 and 9, a palette one 224 at byte 2; byte 14 the
    mode, 15 the frames, 17 each frame's 60ths of a second) and GaneshaDx's
    choice of which to play (UV modes 1 and 2, palette 3 and 4, the second
    of each there and back). The others wait for something in a battle.
    """
    uv, palettes = [], []
    for i in range(len(raw or b"") // 20):
        r = raw[20 * i:20 * i + 20]
        mode, count, duration = r[14], r[15], r[17] / 60.0
        if count < 2 or duration <= 0:
            continue
        if r[1] == 3 and r[9] == 3:
            width, height = r[4] * 4, r[6]
            if mode not in (1, 2) or not width or not height:
                continue
            x, page = r[0] * 4 % 256, r[0] * 4 // 256
            fx, fpage, fy = r[8] * 4 % 256, r[8] * 4 // 256, r[10]
            # The frames run along from the first, then on in rows below it.
            first_row, next_rows = (256 - fx) // width, max(1, 256 // width)
            frames = []
            for k in range(count):
                if k < first_row:
                    frames.append((fx + k * width, fy + fpage * 256))
                else:
                    row, col = divmod(k - first_row, next_rows)
                    frames.append((8 + col * width, fy + (row + 1) * height + fpage * 256))
            uv.append(UvAnimation((x, r[2] + page * 256, width, height), frames, duration, mode == 2))
        elif r[2] == 224:
            start = r[8]
            if mode not in (3, 4) or start + count > 16:
                continue
            palettes.append(PaletteAnimation(r[0] >> 4, start, count, duration, mode == 4))
    return uv, palettes


def frame_at(count: int, duration: float, seconds: float, back_and_forth: bool = False) -> int:
    """Which of `count` frames, each `duration` seconds long, shows at `seconds`: 0 1 2 0 1 2, or 0 1 2 2 1 0."""
    if count <= 1 or duration <= 0:
        return 0
    loop, k = divmod(int(seconds / duration), count)
    return count - 1 - k if back_and_forth and loop % 2 else k


def enhanced_frame(count: int, seconds: float) -> int:
    return frame_at(count, 1.0 / ENHANCED_FRAMES_A_SECOND, seconds)


def build_classic(game_dir: Path, number: int, state: mc.State = mc.State()) -> Scene:
    """The classic look: the PlayStation mesh, texture and palettes of `state`."""
    from PIL import Image

    folder = Path(game_dir) / mc.MAP_FOLDER
    index = mc.read_gns(folder, number)
    sources = index.sources(state)
    scene = Scene(number, CLASSIC)
    if "polygons" not in sources:
        raise mc.MapError("this variant of the map has no polygons")
    # Map 000 has polygons and a grid and no texture: drawn plain.
    has_texture = "texture" in sources
    read = {}

    def mesh_of(part):
        name = sources[part].file_name
        if name not in read:
            read[name] = mc.read_mesh((folder / name).read_bytes())
        return read[name]

    polys = mesh_of("polygons").polygons
    palettes = mesh_of("palettes").palettes if "palettes" in sources else None
    frames = mesh_of("palette_animations").palette_frames if "palette_animations" in sources else None
    scene.lights = mesh_of("lights").lights if "lights" in sources else None
    if "terrain" in sources:
        scene.grid_file = sources["terrain"].file_name
        scene.terrain = mesh_of("terrain").terrain
    scene.classic_indices = (mc.read_texture((folder / sources["texture"].file_name).read_bytes())
                             if has_texture else bytes(mc.TEXTURE_WIDTH * mc.TEXTURE_HEIGHT))
    picture = Image.new("RGBA", (16, 32))
    rows = (palettes or [[0] * 16] * 16) + (frames or [[0] * 16] * 16)
    picture.putdata([mc.colour_rgba(c) for row in rows for c in row])
    scene.classic_palette = picture
    if has_texture and "texture_animations" in sources:
        scene.uv_animations, scene.palette_animations = classic_animations(
            mesh_of("texture_animations").texture_animations)
        if frames is None:
            scene.palette_animations = []
    textured, black, points = array.array("f"), array.array("f"), []
    plain = array.array("f")
    for p in polys:
        if p.mesh != 0:
            continue
        corners = [world(v) for v in p.vertices]
        points.extend(corners)
        render = float(p.render or 0)
        for tri in _classic_triangles(len(corners)):
            for k in tri:
                if p.textured and has_texture:
                    u, v = p.uvs[k]
                    n = p.normals[k]
                    textured.extend(corners[k] + ((u + 0.5) / 256.0, (v + 256 * p.page + 0.5) / 1024.0,
                                                  -n[0] / 4096, -n[1] / 4096, n[2] / 4096,
                                                  float(p.palette), render))
                elif p.textured:
                    plain.extend(corners[k] + (0.46, 0.47, 0.50, 1.0, render))
                else:
                    black.extend(corners[k] + (0.0, 0.0, 0.0, 1.0, render))
    scene.bounds = scene.frame = _bounds(points)
    if len(textured):
        scene.batches.append(Batch(CLASSIC, textured, (3, 2, 3, 1, 1)))
    for floats in (plain, black):
        if len(floats):
            scene.batches.append(Batch("flat", floats, (3, 4, 1)))
    if not has_texture:
        scene.notes.append("This map has no texture in its files, so it is drawn plain.")
    return scene


# =============================================================================
# The grid
# =============================================================================

def tile_corners(tile: mc.Tile, lift: float = 0.0) -> list:
    """A tile's four corners in world space, at its surface."""
    heights = tile.corner_heights()
    x0, x1 = tile.x * mc.TILE_SIZE, (tile.x + 1) * mc.TILE_SIZE
    z0, z1 = tile.z * mc.TILE_SIZE, (tile.z + 1) * mc.TILE_SIZE
    raw = ((x0, z0), (x1, z0), (x1, z1), (x0, z1))
    return [(-x, h * mc.HEIGHT_STEP + lift, z) for (x, z), h in zip(raw, heights)]


def shows(tile: mc.Tile) -> bool:
    """Whether the grid draws a tile: every tile but the blank places of the upper level."""
    return not (tile.level == 1 and tile.is_blank)


#: The grid's colours (red, green, blue, opacity): a tile units can stand
#: on, one they can't, an edited tile's outline, the tile under the pointer,
#: and the tiles picked - filled gold and edged in a band of it, so a pick
#: shows on any ground.
STAND_FILL, BLOCKED_FILL = (0.40, 0.78, 1.0, 0.13), (1.0, 0.40, 0.35, 0.16)
STAND_EDGE, BLOCKED_EDGE = (0.88, 0.94, 1.0, 0.42), (1.0, 0.62, 0.58, 0.45)
EDITED_EDGE = (0.35, 0.95, 0.45, 0.95)
HOVER_FILL = (1.0, 1.0, 1.0, 0.32)
PICKED_FILL, PICKED_EDGE = (1.0, 0.78, 0.12, 0.50), (1.0, 0.86, 0.20, 1.0)
#: The picked tile's band: how far in from its edges, as a share of the way to its middle.
PICKED_BAND = 0.22
#: Floats a vertex of the grid: position and colour.
GRID_STRIDE = 7


def _quad(out: array.array, corners: list, rgba: tuple) -> None:
    for tri in ((0, 1, 2), (0, 2, 3)):
        for k in tri:
            out.extend(corners[k] + rgba)


def _band(out: array.array, corners: list, rgba: tuple, share: float) -> None:
    """A band round a tile's edge, reaching `share` of the way to its middle."""
    middle = tuple(sum(c[i] for c in corners) / 4 for i in range(3))
    inner = [tuple(p + (m - p) * share for p, m in zip(c, middle)) for c in corners]
    for a in range(4):
        b = (a + 1) % 4
        _quad(out, [corners[a], corners[b], inner[b], inner[a]], rgba)


def grid_geometry(tiles, edited: set) -> dict:
    """
    The grid as flat-coloured vertex lists, `{"fill": ..., "lines": ...}`,
    7 floats a vertex (position, colour). `tiles` are the tiles as edited,
    so a raised tile shows raised; edited ones are outlined in green.
    """
    fill, lines = array.array("f"), array.array("f")
    for t in tiles:
        if not shows(t):
            continue
        c = tile_corners(t, 0.6)
        stand = not t.no_walk
        _quad(fill, c, STAND_FILL if stand else BLOCKED_FILL)
        if (t.x, t.z, t.level) in edited:
            edge = EDITED_EDGE
        else:
            edge = STAND_EDGE if stand else BLOCKED_EDGE
        for a, b in ((0, 1), (1, 2), (2, 3), (3, 0)):
            lines.extend(c[a] + edge)
            lines.extend(c[b] + edge)
    return {"fill": fill, "lines": lines}


def highlight_geometry(by_key: dict, hovered, picked) -> dict:
    """
    The tile under the pointer and the tiles picked, `{"hover": ...,
    "selected": ...}`, drawn over everything. `by_key` is `{(x, z, level):
    tile}`, the tiles as edited.
    """
    hover, chosen = array.array("f"), array.array("f")
    tile = by_key.get(hovered) if hovered is not None else None
    if tile is not None:
        _quad(hover, tile_corners(tile, 1.0), HOVER_FILL)
    for key in picked or ():
        tile = by_key.get(key)
        if tile is not None:
            corners = tile_corners(tile, 1.0)
            _quad(chosen, corners, PICKED_FILL)
            _band(chosen, corners, PICKED_EDGE, PICKED_BAND)
    return {"hover": hover, "selected": chosen}


class SceneWorker(Worker):
    """
    Reads a map and decodes its pictures, off the GUI thread. Returns
    `(token, scene, None)`, or `(token, None, what went wrong)`: a failure
    carries its token too, so one that arrives after another map was picked
    is dropped like a late success.
    """

    def __init__(self, token, game_dir, number, look, state, sqlite_path=None, mesh_file=None,
                 picture_files=None):
        super().__init__()
        self.token, self.game_dir, self.number, self.look = token, game_dir, number, look
        self.state, self.sqlite_path = state, sqlite_path
        self.mesh_file, self.picture_files = mesh_file, dict(picture_files or {})

    def run(self):
        try:
            if self.look == ENHANCED:
                scene = build_enhanced(self.game_dir, self.number, self.sqlite_path, self.state,
                                       self.mesh_file, self.picture_files)
            else:
                scene = build_classic(self.game_dir, self.number, self.state)
            if scene.grid_file:
                folder = Path(self.game_dir) / mc.MAP_FOLDER
                scene.grid_key = mc.grid_key(folder, self.number, scene.grid_file)
                scene.grid_files = sorted(mc.grid_files(folder, self.number, scene.grid_file),
                                          key=mc.file_order)
        except Exception as exc:                               # noqa: BLE001
            return (self.token, None, str(exc) or exc.__class__.__name__)
        return (self.token, scene, None)


# =============================================================================
# The camera's corner
# =============================================================================

def _smoothstep(a: float, b: float, x: float) -> float:
    t = min(1.0, max(0.0, (x - a) / (b - a))) if b > a else float(x >= a)
    return t * t * (3 - 2 * t)


def corner_weights(yaw: float) -> tuple:
    """
    How far each corner's walls are left out from `yaw`, in `CORNERS`'
    order: 1 for the corner the camera is at, and between two corners the
    two shared over the middle `FADE_SPAN` of the turn - so a wall fades.
    """
    az = yaw % 360.0
    angles = [angle for angle, _bit in CORNERS]
    below = max((a for a in angles if a <= az), default=max(angles) - 360.0)
    share = _smoothstep(0.5 - FADE_SPAN / 2, 0.5 + FADE_SPAN / 2, (az - below) / 90.0)
    weights = [0.0] * len(CORNERS)
    weights[angles.index(below % 360.0)] += 1.0 - share
    weights[angles.index((below + 90.0) % 360.0)] += share
    return tuple(weights)


def shown(render: int, weights: tuple) -> float:
    """How much of a polygon shows (0 left out, 1 drawn) for its render properties."""
    return 1.0 - sum(w for w, (_angle, bit) in zip(weights, CORNERS) if (int(render) >> bit) & 1)
