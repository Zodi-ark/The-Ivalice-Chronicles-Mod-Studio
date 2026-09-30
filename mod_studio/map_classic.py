"""
The classic battle maps: the PlayStation files The Ivalice Chronicles keeps
in `fftpack/map/`, read from the FFHacktics wiki's documents (Maps/GNS,
Maps/Mesh, Maps/Texture), and tiles changed where they sit.

A map is a GNS file, `map_mapNNN_gns.bin`, and numbered files beside it,
`map_mapNNN_<n>.bin`: textures (256 x 1024 pictures at 4 bits a pixel) and
meshes. A mesh file holds any of: the map's polygons, its colour palettes,
lights and background, its terrain (the battle grid), texture and palette
animations, and per polygon which camera angles hide it. The GNS lists them
by arrangement, day or night and weather, and a state of the map takes each
of those parts from the most particular file that has it
(`MapIndex.sources`). 123 GNS files and 1,828 files in all; maps 126 and 127
list resources and have no files.

**What The Ivalice Chronicles changed.** One thing, in the GNS: bytes 8-11
of a resource's 20-byte record, the PlayStation's CD sector, read
0xFEEDBACC in every record, and bytes 12-15, its length, hold the
resource's place among the map's numbered files in number order. That
pairing holds for every resource of all 121 maps with files, and puts a
texture record on a 131,072-byte file every time. Everything else matches
the documents byte for byte, and `dev/test_map_classic.py` holds this
module to GaneshaDx's own reading classes (Garmichael, GPL-3) on all 970
mesh files, 735 textures and 123 GNS files.

**Two copies of some meshes.** 174 files named `new_map_new_mapNNN_<n>.bin`
are revised copies of the numbered file `<n>`: the same parts, with extra
polygons in 145 of them, and the same terrain in all 145 that have one. 77
maps also have `map_dst_mapNNN_dat.bin`, 131,072 bytes: their first
texture with the see-through pixels at the edges of the pictures filled in.
Which of each pair the game draws is not known, so tile edits are written
into both (`grid_files`).

**Tiles are changed in place.** A terrain is 2 bytes of size and two levels
of 256 tiles, 8 bytes each, whatever the map's size. An edit overwrites the
bits of the fields it changes and nothing else, so every bit nobody has
decoded stays as it was, and the file keeps its size - which the mod loader
needs: it hands the game at most as many bytes of a replaced `fftpack` file
as the game asks for.

Nothing here imports Qt.
"""
from __future__ import annotations

import os
import re
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# =============================================================================
# The GNS: which file is which
# =============================================================================

TEXTURE = 0x1701
PRIMARY_MESH = 0x2E01
OVERRIDE_MESH = 0x2F01
ALTERNATE_MESH = 0x3001
RESOURCE_KINDS = (TEXTURE, PRIMARY_MESH, OVERRIDE_MESH, ALTERNATE_MESH)
MESH_KINDS = (PRIMARY_MESH, OVERRIDE_MESH, ALTERNATE_MESH)

#: Where the maps are, relative to the unpacked game.
MAP_FOLDER = "fftpack/map"
#: 256 x 1024 pixels, two to a byte.
TEXTURE_BYTES = 131072
TEXTURE_WIDTH, TEXTURE_HEIGHT = 256, 1024

#: The weathers a GNS record can name (its time byte's bits 4-6).
WEATHERS = ("None", "Light", "Normal", "Strong", "Very strong")

_GNS_NAME = re.compile(r"map_map(\d{3})_gns\.bin$", re.IGNORECASE)
_NUMBERED = re.compile(r"map_map(\d{3})_(\d+)\.bin$", re.IGNORECASE)


class MapError(ValueError):
    """Raised for a file this module cannot read as what it should be."""


@dataclass(frozen=True)
class State:
    """One way a map can look: arrangement, day or night, weather 0-4."""
    arrangement: int = 0
    night: bool = False
    weather: int = 0

    @property
    def is_default(self) -> bool:
        return self == State()


@dataclass(frozen=True)
class Resource:
    record: int                 # offset of its 20-byte record in the GNS
    kind: int                   # TEXTURE, PRIMARY_MESH, OVERRIDE_MESH or ALTERNATE_MESH
    state: State
    index: int                  # its place among the map's numbered files
    file_name: Optional[str]    # "map_map048_9.bin", or None when there is no such file


@dataclass
class MapIndex:
    """A map's GNS, with each resource paired with its file."""
    number: int
    folder: Path
    resources: list

    def states(self) -> list:
        """Every state the GNS names a file for, the default first."""
        seen = []
        for r in self.resources:
            if r.file_name and r.state not in seen:
                seen.append(r.state)
        return sorted(seen, key=lambda s: (s.arrangement, s.night, s.weather))

    def arrangements(self) -> list:
        return sorted({s.arrangement for s in self.states()})

    def sources(self, state: State) -> dict:
        """
        Which file each part of `state` comes from: `{"polygons": Resource,
        "palettes", "lights", "terrain", "texture", ...}`, a part the map
        does not have being absent.

        A part comes from the first mesh of the state itself that has it,
        in file order, and otherwise from the first of the default state's
        meshes (arrangement 0, day, no weather) that has it. The texture is
        the state's own, or else the default one. It is the reading
        GaneshaDx uses, and fits the files: where a map's primary and
        override meshes both carry polygons or a terrain, the two are the
        same.
        """
        own = [r for r in self.resources if r.state == state and r.file_name]
        default = [r for r in self.resources if r.state.is_default and r.file_name]
        out = {}
        texture = ([r for r in own if r.kind == TEXTURE]
                   or [r for r in default if r.kind == TEXTURE])
        if texture:
            out["texture"] = texture[0]
        meshes = {}
        for resource in [r for r in own + default if r.kind in MESH_KINDS]:
            mesh = meshes.get(resource.file_name)
            if mesh is None:
                mesh = meshes[resource.file_name] = read_mesh(
                    (self.folder / resource.file_name).read_bytes())
            for part in mesh.parts():
                out.setdefault(part, resource)
        return out


def map_numbers(folder: Path) -> list:
    """The map numbers with a GNS file in `folder` (the game's fftpack/map)."""
    try:
        names = os.listdir(folder)
    except OSError:
        return []
    return sorted(int(m.group(1)) for n in names for m in [_GNS_NAME.match(n)] if m)


def gns_name(number: int) -> str:
    return f"map_map{number:03d}_gns.bin"


def read_gns(folder: Path, number: int) -> MapIndex:
    folder = Path(folder)
    data = (folder / gns_name(number)).read_bytes()
    try:
        names = os.listdir(folder)
    except OSError:
        names = []
    numbered = sorted((int(m.group(2)), n) for n in names
                      for m in [_NUMBERED.match(n)] if m and int(m.group(1)) == number)
    resources = []
    for o in range(0, len(data) - 19, 20):
        _head, arrangement, time_weather, kind = struct.unpack_from("<HBBH", data, o)
        if kind not in RESOURCE_KINDS:
            continue
        index = struct.unpack_from("<I", data, o + 12)[0]
        state = State(arrangement, bool(time_weather & 0x80), (time_weather >> 4) & 7)
        file_name = numbered[index][1] if index < len(numbered) else None
        resources.append(Resource(o, kind, state, index, file_name))
    return MapIndex(number, folder, resources)


def revised_name(file_name: str) -> str:
    """`map_map048_9.bin` -> `new_map_new_map048_9.bin`, its revised copy's name."""
    return "new_map_new_" + file_name[len("map_"):]


# =============================================================================
# Meshes
# =============================================================================

#: The mesh file's pointer table (Maps/Mesh): each part's offset, 0 if absent.
POINTERS = {
    "polygons": 0x40, "palettes": 0x44, "lights": 0x64, "terrain": 0x68,
    "texture_animations": 0x6C, "palette_animations": 0x70,
    "grayscale_palettes": 0x7C, "mesh_animations": 0x8C,
    "animated_mesh_1": 0x90, "animated_mesh_2": 0x94, "animated_mesh_3": 0x98,
    "animated_mesh_4": 0x9C, "animated_mesh_5": 0xA0, "animated_mesh_6": 0xA4,
    "animated_mesh_7": 0xA8, "animated_mesh_8": 0xAC,
    "render_properties": 0xB0,
}
#: The polygon kinds, in the order their records come in a mesh.
KINDS = ("tt", "tq", "ut", "uq")      # textured triangle, textured quad, untextured ...
CORNERS = {"tt": 3, "tq": 4, "ut": 3, "uq": 4}
#: Render properties: 896 bytes of something else, then 16 bits per polygon
#: for up to 512 textured triangles, 768 textured quads, 64 and 256 untextured.
RENDER_STARTS = {"tt": 896, "tq": 896 + 1024, "ut": 896 + 2560, "uq": 896 + 2688}
#: Their bits, from the documents' table (listed from the top bit down).
RENDER_UNLIT = 1 << 15
#: The camera angles a polygon can be hidden from, by bit, as the
#: documents name them. Bits 14, 1 and 0 are not known.
HIDE_BITS = {13: "SW", 12: "NW", 11: "NE", 10: "SE", 9: "SSW", 8: "WSW",
             7: "WNW", 6: "NNW", 5: "NNE", 4: "ENE", 3: "ESE", 2: "SSE"}
UNBOUND = (0xFE, 0xFF)


@dataclass
class Polygon:
    mesh: int                   # 0 the map, 1-8 its animated meshes
    kind: str                   # "tt", "tq", "ut" or "uq"
    index: int                  # its place among the mesh's polygons of that kind
    vertices: tuple             # ((x, y, z), ...) as stored: y is negative upward
    normals: tuple = ()         # ((x, y, z), ...) int16, 4096 = 1.0 (textured only)
    uvs: tuple = ()             # ((u, v), ...) 0-255 within the texture page
    palette: int = 0            # 0-15
    page: int = 0               # 0-3: which 256-pixel band of the texture
    image: int = 3              # 3 the map's texture; other values name UI pictures
    texture_record: bytes = b""  # the record as stored (10 or 12 bytes)
    tile: Optional[tuple] = None  # (x, z, level) of the tile it is drawn for
    untextured: bytes = b""     # the 4 bytes an untextured polygon has
    render: Optional[int] = None  # its 16 bits of render properties

    @property
    def textured(self) -> bool:
        return self.kind in ("tt", "tq")

    @property
    def unlit(self) -> bool:
        """
        The render properties' top bit: drawn in its palette's colours with
        no lighting. The documents' table puts it first and calls it
        "Polygon is Unlit"; it is set on 78,288 of the game's 81,914
        polygons with render properties.
        """
        return self.render is not None and bool(self.render & RENDER_UNLIT)

    def hidden_from(self, bit: int) -> bool:
        """Whether one of `HIDE_BITS` is set: hidden when the camera is there."""
        return self.render is not None and bool(self.render >> bit & 1)


@dataclass
class Lights:
    colours: tuple              # three (r, g, b), int16, 4096 = 1.0
    directions: tuple           # three (x, y, z), int16
    ambient: tuple              # (r, g, b) 0-255
    background_top: tuple
    background_bottom: tuple


# -- Tiles --------------------------------------------------------------------

TILE_BYTES = 8
TERRAIN_LEVEL_BYTES = 256 * TILE_BYTES

#: A tile's fields: (byte, first bit, bits). Measured against the documents'
#: table, which lists each byte's fields from its highest bit down.
TILE_FIELDS = {
    "surface": (0, 0, 6),
    "height": (2, 0, 8),
    "slope_height": (3, 0, 5),
    "depth": (3, 5, 3),
    "slope": (4, 0, 8),
    "thickness": (5, 0, 5),
    "no_cursor": (6, 0, 1),
    "no_walk": (6, 1, 1),
    "shading": (6, 2, 2),
    "pass_through": (6, 7, 1),
    "camera": (7, 0, 8),
}
BOOL_FIELDS = ("no_cursor", "no_walk", "pass_through")

#: Slope types: the corners each raises by the slope's height, in the order
#: (x0,z0), (x1,z0), (x1,z1), (x0,z1); north is +z, east is +x. The names
#: are the documents'; which corners rise was measured on the game's maps,
#: from the polygons drawn for sloped tiles (every one of the twelve).
SLOPES = {
    0x00: ("Flat", (0, 0, 0, 0)),
    0x85: ("Incline N", (0, 0, 1, 1)),
    0x52: ("Incline E", (0, 1, 1, 0)),
    0x25: ("Incline S", (1, 1, 0, 0)),
    0x58: ("Incline W", (1, 0, 0, 1)),
    0x41: ("Convex NE", (0, 0, 1, 0)),
    0x11: ("Convex SE", (0, 1, 0, 0)),
    0x14: ("Convex SW", (1, 0, 0, 0)),
    0x44: ("Convex NW", (0, 0, 0, 1)),
    0x96: ("Concave NE", (0, 1, 1, 1)),
    0x66: ("Concave SE", (1, 1, 1, 0)),
    0x69: ("Concave SW", (1, 1, 0, 1)),
    0x99: ("Concave NW", (1, 0, 1, 1)),
}

#: World units: a tile is 28 wide, a height step 12 tall.
TILE_SIZE = 28
HEIGHT_STEP = 12


@dataclass
class Tile:
    x: int
    z: int
    level: int                  # 0 the ground, 1 the level above (bridges, upper floors)
    raw: bytes                  # its 8 bytes

    def get(self, name: str) -> int:
        byte, bit, bits = TILE_FIELDS[name]
        return (self.raw[byte] >> bit) & ((1 << bits) - 1)

    def __getattr__(self, name):
        if name in TILE_FIELDS:
            value = self.get(name)
            return bool(value) if name in BOOL_FIELDS else value
        raise AttributeError(name)

    @property
    def is_blank(self) -> bool:
        """All eight bytes zero: a place on the grid with no tile."""
        return not any(self.raw)

    def corner_heights(self) -> tuple:
        """Heights of (x0,z0), (x1,z0), (x1,z1), (x0,z1), in height steps."""
        raised = SLOPES.get(self.get("slope"), ("", (0, 0, 0, 0)))[1]
        height, rise = self.get("height"), self.get("slope_height")
        return tuple(height + rise * r for r in raised)

    def shown_height_index(self) -> int:
        """
        The row of the game's `LandscapeHeight` table that names this tile's
        height: twice the height plus the slope's rise, the table running in
        half steps (0, 0.5, 1 ...), so a slope is named by its middle.
        """
        return 2 * self.get("height") + self.get("slope_height")


@dataclass
class Terrain:
    offset: int                 # the terrain part's offset in its file
    size_x: int
    size_z: int
    tiles: list                 # size_x * size_z tiles per level, level 0 first

    def tile(self, x: int, z: int, level: int = 0) -> Optional[Tile]:
        if not (0 <= x < self.size_x and 0 <= z < self.size_z and level in (0, 1)):
            return None
        return self.tiles[level * self.size_x * self.size_z + z * self.size_x + x]

    def tile_offset(self, x: int, z: int, level: int) -> int:
        return self.offset + 2 + level * TERRAIN_LEVEL_BYTES + TILE_BYTES * (z * self.size_x + x)


@dataclass
class Mesh:
    size: int
    pointers: dict                          # part -> offset, parts present only
    polygons: list = field(default_factory=list)
    palettes: Optional[list] = None         # 16 palettes of 16 raw 16-bit colours
    palette_frames: Optional[list] = None   # the palette animations' 16 palettes
    grayscale_palettes: Optional[list] = None
    lights: Optional[Lights] = None
    terrain: Optional[Terrain] = None
    texture_animations: Optional[bytes] = None  # 32 records of 20 bytes, as stored

    def parts(self) -> list:
        """The parts a state can take from this file, in `MapIndex.sources`' terms."""
        out = []
        if self.polygons or "polygons" in self.pointers:
            out.append("polygons")
        for name in ("palettes", "palette_animations", "grayscale_palettes", "lights",
                     "terrain", "texture_animations", "mesh_animations", "render_properties"):
            if name in self.pointers:
                out.append(name)
        return out


def _palettes(data: bytes, offset: int) -> list:
    return [list(struct.unpack_from("<16H", data, offset + 32 * p)) for p in range(16)]


def read_mesh(data: bytes) -> Mesh:
    """
    Reads every part of a mesh file this editor uses. Raises `MapError` for
    a file whose pointers or counts run past its end.
    """
    if len(data) < 0xC4:
        raise MapError("too short to be a map mesh")
    pointers = {}
    for name, at in POINTERS.items():
        value = struct.unpack_from("<I", data, at)[0]
        if value:
            if value >= len(data):
                raise MapError(f"its {name} pointer runs past the end")
            pointers[name] = value
    mesh = Mesh(len(data), pointers)
    try:
        render_at = pointers.get("render_properties")
        meshes = [("polygons", 0)] + [(f"animated_mesh_{i}", i) for i in range(1, 9)]
        for name, number in meshes:
            if name in pointers:
                polys = _read_polygons(data, pointers[name], number)
                if render_at and number == 0:
                    for p in polys:
                        p.render = struct.unpack_from(
                            "<H", data, render_at + RENDER_STARTS[p.kind] + 2 * p.index)[0]
                mesh.polygons.extend(polys)
        if "palettes" in pointers:
            mesh.palettes = _palettes(data, pointers["palettes"])
        if "palette_animations" in pointers:
            mesh.palette_frames = _palettes(data, pointers["palette_animations"])
        if "grayscale_palettes" in pointers:
            mesh.grayscale_palettes = _palettes(data, pointers["grayscale_palettes"])
        if "lights" in pointers:
            o = pointers["lights"]
            colours = struct.unpack_from("<9h", data, o)
            directions = struct.unpack_from("<9h", data, o + 18)
            mesh.lights = Lights(
                tuple((colours[i], colours[3 + i], colours[6 + i]) for i in range(3)),
                tuple(directions[3 * i:3 * i + 3] for i in range(3)),
                tuple(data[o + 36:o + 39]), tuple(data[o + 39:o + 42]),
                tuple(data[o + 42:o + 45]))
        if "terrain" in pointers:
            o = pointers["terrain"]
            size_x, size_z = data[o], data[o + 1]
            if size_x * size_z > 256 or o + 2 + 2 * TERRAIN_LEVEL_BYTES > len(data):
                raise MapError("its terrain does not fit")
            tiles = []
            for level in range(2):
                for z in range(size_z):
                    for x in range(size_x):
                        at = o + 2 + level * TERRAIN_LEVEL_BYTES + TILE_BYTES * (z * size_x + x)
                        tiles.append(Tile(x, z, level, bytes(data[at:at + TILE_BYTES])))
            mesh.terrain = Terrain(o, size_x, size_z, tiles)
        if "texture_animations" in pointers:
            o = pointers["texture_animations"]
            mesh.texture_animations = bytes(data[o:o + 640])
    except struct.error as exc:
        raise MapError("a part runs past the end of the file") from exc
    return mesh


def _read_polygons(data: bytes, at: int, mesh_number: int) -> list:
    counts = struct.unpack_from("<4H", data, at)
    count = dict(zip(KINDS, counts))
    o = at + 8
    corners = {}
    for kind in KINDS:            # positions: every kind, in this order
        n = CORNERS[kind]
        corners[kind] = [tuple(struct.unpack_from("<3h", data, o + 6 * (n * i + k)) for k in range(n))
                         for i in range(count[kind])]
        o += 6 * n * count[kind]
    normals = {}
    for kind in ("tt", "tq"):     # normals: textured only
        n = CORNERS[kind]
        normals[kind] = [tuple(struct.unpack_from("<3h", data, o + 6 * (n * i + k)) for k in range(n))
                         for i in range(count[kind])]
        o += 6 * n * count[kind]
    polys = []
    for kind, size in (("tt", 10), ("tq", 12)):
        for i in range(count[kind]):
            r = bytes(data[o:o + size])
            if len(r) < size:
                raise struct.error("short")
            uvs = ((r[0], r[1]), (r[4], r[5]), (r[8], r[9])) + (((r[10], r[11]),) if size == 12 else ())
            polys.append(Polygon(mesh_number, kind, i, corners[kind][i], normals[kind][i], uvs,
                                 palette=r[2] & 0x0F, page=r[6] & 3, image=(r[6] >> 2) & 3,
                                 texture_record=r))
            o += size
    for kind in ("ut", "uq"):
        for i in range(count[kind]):
            polys.append(Polygon(mesh_number, kind, i, corners[kind][i],
                                 untextured=bytes(data[o:o + 4])))
            o += 4
    for p in [p for p in polys if p.textured]:
        b0, b1 = data[o], data[o + 1]
        if (b0, b1) != UNBOUND:
            p.tile = (b1, b0 >> 1, b0 & 1)
        o += 2
    order = {k: n for n, k in enumerate(KINDS)}
    polys.sort(key=lambda p: (order[p.kind], p.index))
    return polys


# =============================================================================
# Textures and colours
# =============================================================================

def read_texture(data: bytes) -> bytes:
    """
    The picture's 262,144 palette indices, one byte each, row by row. Each
    byte of the file is two pixels, the left one in its low 4 bits.
    """
    if len(data) != TEXTURE_BYTES:
        raise MapError(f"a map texture is {TEXTURE_BYTES:,} bytes, this is {len(data):,}")
    out = bytearray(len(data) * 2)
    out[0::2] = bytes(b & 0x0F for b in data)
    out[1::2] = bytes(b >> 4 for b in data)
    return bytes(out)


def colour_rgba(raw: int) -> tuple:
    """
    A palette colour as red, green, blue, alpha 0-255. Five bits a colour,
    red lowest; 0x0000 is see-through, which is what an index 0 usually is.
    """
    r, g, b = raw & 31, (raw >> 5) & 31, (raw >> 10) & 31
    return (r * 255 // 31, g * 255 // 31, b * 255 // 31, 0 if raw == 0 else 255)


# =============================================================================
# Tile edits
# =============================================================================

def field_range(name: str) -> tuple:
    """The lowest and highest value the file can hold for a tile field."""
    _byte, _bit, bits = TILE_FIELDS[name]
    return 0, (1 << bits) - 1


def tile_with(raw: bytes, changes: dict) -> bytes:
    """
    `raw` with `changes` ({field: value}) written into their bits and every
    other bit left as it was. Raises ValueError for a field that does not
    exist or a value the field cannot hold.
    """
    out = bytearray(raw)
    for name, value in changes.items():
        if name not in TILE_FIELDS:
            raise ValueError(f"a tile has no {name}")
        if isinstance(value, bool):
            value = int(value)
        if not isinstance(value, int):
            raise ValueError(f"{name} must be a whole number")
        low, high = field_range(name)
        if not low <= value <= high:
            raise ValueError(f"{name} {value} is outside {low}-{high}")
        byte, bit, bits = TILE_FIELDS[name]
        mask = ((1 << bits) - 1) << bit
        out[byte] = (out[byte] & ~mask & 0xFF) | (value << bit)
    return bytes(out)


def tile_key(x: int, z: int, level: int) -> tuple:
    return (int(x), int(z), int(level))


def apply_tile_edits(data: bytes, edits: dict) -> tuple:
    """
    Returns `(patched bytes, problems)`.

    `edits` is `{(x, z, level): {field: value}}`, values as the tile's new
    ones (fields in `TILE_FIELDS`; the three yes-or-no ones as bools). Each
    edit overwrites only its field's bits, so the result is always the same
    length as the input and every bit nobody has decoded is kept. `problems`
    lists, in words, edits that could not be written - no terrain in this
    file, a tile outside the grid, a field that does not exist, a value the
    field cannot hold - and those tiles are skipped whole.
    """
    out = bytearray(data)
    problems = []
    try:
        mesh = read_mesh(data)
    except MapError as exc:
        return bytes(out), [f"not written, as {exc}"]
    terrain = mesh.terrain
    if not isinstance(edits, dict):
        return bytes(out), ["not written, as the edits are not a list of tiles"]
    for key, changes in edits.items():
        try:
            x, z, level = tile_key(*key)
        except (TypeError, ValueError):
            problems.append(f"{key!r}: not a tile")
            continue
        name = f"tile {x}, {z}" + (" upper level" if level else "")
        if terrain is None:
            problems.append(f"{name}: not written, as this file has no terrain")
            continue
        tile = terrain.tile(x, z, level)
        if tile is None:
            problems.append(f"{name}: not written, as the grid is {terrain.size_x} by {terrain.size_z}")
            continue
        if not isinstance(changes, dict):
            problems.append(f"{name}: not written, as the edit is not a list of fields")
            continue
        try:
            raw = tile_with(tile.raw, changes)
        except ValueError as exc:
            problems.append(f"{name}: not written, as {exc}")
            continue
        at = terrain.tile_offset(x, z, level)
        out[at:at + TILE_BYTES] = raw
    return bytes(out), problems


def tile_edits_between(game: bytes, other: bytes) -> Optional[dict]:
    """
    The tile edits that turn the game's file into `other`, or None when no
    set of tile edits does.

    Used when a mod is opened: a map file the mod ships becomes editable
    here only when re-applying the recovered edits to the game's file
    reproduces the mod's copy byte for byte. A file changed any other way -
    its polygons, colours or anything but tiles - is carried through as it
    is. Never raises.
    """
    try:
        if len(game) != len(other):
            return None
        mesh = read_mesh(game)
        if mesh.terrain is None:
            return {} if game == other else None
        theirs = read_mesh(other).terrain
        if theirs is None or (theirs.size_x, theirs.size_z) != (mesh.terrain.size_x, mesh.terrain.size_z):
            return None
        edits = {}
        for mine, new in zip(mesh.terrain.tiles, theirs.tiles):
            if mine.raw == new.raw:
                continue
            changes = {}
            for name in TILE_FIELDS:
                if mine.get(name) != new.get(name):
                    value = new.get(name)
                    changes[name] = bool(value) if name in BOOL_FIELDS else value
            edits[(mine.x, mine.z, mine.level)] = changes
        patched, problems = apply_tile_edits(game, edits)
        if problems or patched != other:
            return None
        return edits
    except Exception:                                          # noqa: BLE001
        return None


def grid_files(folder: Path, number: int, source: str) -> list:
    """
    Every file of map `number` whose terrain is byte for byte the one in
    `source` (a file name in `folder`), `source` first: the copies a tile
    edit is written into. The game keeps some grids in several files - a
    primary and an override mesh, the revised `new_map_` copies - and which
    one it reads for a battle is not known, so all of them get the edit.
    """
    folder = Path(folder)
    try:
        base = read_mesh((folder / source).read_bytes())
    except (OSError, MapError):
        return []
    if base.terrain is None:
        return []
    want = _terrain_bytes((folder / source).read_bytes(), base)
    out = [source]
    pattern = re.compile(r"(?:map_|new_map_new_)map%03d_\d+\.bin$" % number, re.IGNORECASE)
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        names = []
    for name in names:
        if name == source or not pattern.match(name):
            continue
        path = folder / name
        try:
            if path.stat().st_size == TEXTURE_BYTES:
                continue
            data = path.read_bytes()
            mesh = read_mesh(data)
        except (OSError, MapError):
            continue
        if mesh.terrain is not None and _terrain_bytes(data, mesh) == want:
            out.append(name)
    return out


def _terrain_bytes(data: bytes, mesh: Mesh) -> bytes:
    o = mesh.terrain.offset
    return bytes(data[o:o + 2 + 2 * TERRAIN_LEVEL_BYTES])


def file_order(name: str) -> tuple:
    """Numbered files before their revised copies, each in number order."""
    m = re.search(r"_(\d+)\.bin$", name, re.IGNORECASE)
    return (0 if name.lower().startswith("map_") else 1, int(m.group(1)) if m else 0, name)


def grid_key(folder: Path, number: int, source: str) -> Optional[str]:
    """
    The one name a grid's edits are kept under: the lowest numbered of the
    files holding it byte for byte (`grid_files`). Many maps read one grid
    from a different file in each state - map 001's ten weather and time
    states name ten files with the same bytes - so kept under the file a
    state names, an edit made in one state and another made in the next
    would be two edits to the same bytes. None when `source` has no terrain.
    """
    files = grid_files(folder, number, source)
    return min(files, key=file_order) if files else None


def map_grids(folder: Path, number: int) -> dict:
    """
    `{key: files}`: every battle grid a state of map `number` reads, under
    `grid_key`'s name for it, with the files holding it (`grid_files`), in
    number order. Empty for a map with no GNS or no terrain.
    """
    folder = Path(folder)
    try:
        index = read_gns(folder, number)
    except OSError:
        return {}
    out, seen = {}, set()
    for state in index.states():
        try:
            source = index.sources(state).get("terrain")
        except (OSError, MapError):
            continue
        if source is None or source.file_name in seen:
            continue
        files = sorted(grid_files(folder, number, source.file_name), key=file_order)
        seen.update(files)
        if files:
            out[files[0]] = files
    return out


def relative_path(file_name: str) -> str:
    """A map file's path inside the unpacked game and a mod's data folder."""
    return f"{MAP_FOLDER}/{file_name}"
