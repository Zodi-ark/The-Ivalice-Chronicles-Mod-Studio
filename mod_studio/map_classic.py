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


#: The GNS's command rows, after its file rows and a row of kind 0x80 (the
#: decompilation's `battle_map_gns_command_type_e`): the map is indoors
#: (0x85: no weather falls there; `BATTLE_MAP_WEATHER_FLAG_IGNORE_WEATHER`)
#: or out (0x86), its weather snow (0x89: rain falls as snow there;
#: `BATTLE_MAP_WEATHER_FLAG_SNOW`) or not (0x88). Each row is for the
#: states its condition names: a script variable (0x22 the weather and time,
#: 0x30 the arrangement), the state's weather in bits 12 to 14 and night in
#: bit 15 over the variable's own low bits, compared equal (1), less (2) or
#: greater (3). A row is 20 bytes, or the 28 its byte 8 says.
GNS_COMMAND_SEPARATOR = 0x80
GNS_INDOOR, GNS_OUTDOOR, GNS_NO_SNOW, GNS_SNOW = 0x85, 0x86, 0x88, 0x89
GNS_ARRANGEMENT_VARIABLE = 0x30


def gns_commands(folder: Path, number: int) -> list:
    """Map `number`'s GNS command rows: `[(kind, variable, state, comparison)]` in order (see `GNS_INDOOR`)."""
    data = (Path(folder) / gns_name(number)).read_bytes()
    out, at, commands = [], 0, False
    while at + 20 <= len(data):
        variable, state, comparison, kind = struct.unpack_from("<HhBB", data, at)
        if not commands:
            if kind == GNS_COMMAND_SEPARATOR:
                commands = True
            elif not (variable or state or comparison or kind):
                break
            at += 20
            continue
        if not (comparison or kind):
            break
        out.append((kind, variable, state & 0xFFFF, comparison))
        at += data[at + 8] if data[at + 8] in (20, 28) else 20
    return out


def weather_flags(folder: Path, number: int, state: State = State()) -> tuple:
    """
    `(indoors, snow)`: whether map `number` in `state` is indoors, where no
    weather falls, and whether its weather falls as snow (`gns_commands`;
    out of doors and rain without a row saying).
    """
    try:
        rows = gns_commands(folder, number)
    except (OSError, struct.error):
        return (False, False)
    indoors = snow = False
    for kind, variable, wanted, comparison in rows:
        low = state.arrangement if variable == GNS_ARRANGEMENT_VARIABLE else 0
        asked = (low & 0xFFF) | ((state.weather & 7) << 12) | (0x8000 if state.night else 0)
        if not ((comparison == 1 and asked == wanted) or (comparison == 2 and asked < wanted)
                or (comparison == 3 and asked > wanted)):
            continue
        if kind in (GNS_INDOOR, GNS_OUTDOOR):
            indoors = kind == GNS_INDOOR
        elif kind in (GNS_SNOW, GNS_NO_SNOW):
            snow = kind == GNS_SNOW
    return (indoors, snow)


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
#: A whole terrain part: its 2 bytes of size and both levels, whatever the
#: map's size. A grid copied to another map goes as one (`with_terrain`).
TERRAIN_BYTES = 2 + 2 * TERRAIN_LEVEL_BYTES

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
#: An upper level place with no tile: only "no cursor" set (`Tile.is_placeholder`).
PLACEHOLDER_TILE = bytes([0, 0, 0, 0, 0, 0, 1, 0])
#: A new upper level tile (`upper_tile_fields`): how many height steps over
#: the ground under it it starts, and how far down it reaches. The game's
#: own upper level tiles the cursor can stop on (259 on 47 maps' grids)
#: stand 4 to 17 steps over the ground but one (8 for 87 of them, 7 to 10
#: for 183), and reach 1 to 5 steps down (2 for most).
UPPER_STEPS, UPPER_THICKNESS = 8, 2
#: The surface a new upper level tile over water has (its depth more than
#: 0): Bridge, the game's `Land` row 35, which 22 of its own upper level
#: tiles have; over anything else, the ground's own.
BRIDGE_SURFACE = 35
#: The room a unit needs under a tile of the upper level, in half height
#: steps: 6, three steps (a chicken or a frog 4). The battle's movement
#: (the PlayStation game's, read for facts in adamrt's fft_decomp:
#: `src/battle/map/move_range.c`, its `unit_size` and the ceiling checks of
#: `spread_destination_propagate`) takes a tile's underside as twice its
#: height and its slope, less twice its thickness (the decompilation's
#: "ceiling depth"), and lets a unit onto the ground under it only when the
#: underside is at least this far over that ground and over the ground the
#: unit steps in from. All 242 of the game's own upper level tiles the
#: cursor can stop on, over ground units can stand on, leave at least that
#: over their ground (033's (5, 4) exactly). Zodi's test 11 (22 October):
#: a bridge 4 high and 2 thick over Gariland's canal left 4 over the canal
#: and none over the squares beside it, 2 high, and no unit could go under
#: it, though units stood on it.
UNIT_ROOM = 6

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

    @property
    def is_placeholder(self) -> bool:
        """
        A place of the upper level with no tile: every field 0 but "no
        cursor" (the cursor can't go there). The game's grids fill their
        upper level with these where there is none (all 169 of 085's, 13,642
        of the 14,546 upper level places on the 120 grids an enhanced look
        stands on; one has a face drawn for it, none a panel).
        """
        return self.level == 1 and self.raw == PLACEHOLDER_TILE

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


def _read_terrain(data: bytes, o: int) -> Terrain:
    """The terrain part at `o` of `data`; MapError when it doesn't fit."""
    size_x, size_z = data[o], data[o + 1]
    if size_x * size_z > 256 or o + TERRAIN_BYTES > len(data):
        raise MapError("its terrain does not fit")
    tiles = []
    for level in range(2):
        for z in range(size_z):
            for x in range(size_x):
                at = o + 2 + level * TERRAIN_LEVEL_BYTES + TILE_BYTES * (z * size_x + x)
                tiles.append(Tile(x, z, level, bytes(data[at:at + TILE_BYTES])))
    return Terrain(o, size_x, size_z, tiles)


def read_terrain(part: bytes) -> Terrain:
    """
    A bare terrain part's grid (`terrain_part`'s bytes, `TERRAIN_BYTES`), its
    tiles' offsets within the part. MapError for bytes that aren't one.
    """
    if len(part) != TERRAIN_BYTES:
        raise MapError(f"a terrain part is {TERRAIN_BYTES} bytes, not {len(part)}")
    return _read_terrain(part, 0)


def terrain_part(data: bytes) -> bytes:
    """
    A map file's whole terrain part, `TERRAIN_BYTES`: its size and both
    levels, as a look copied to another map number takes its source's grid.
    MapError for a file with none.
    """
    mesh = read_mesh(data)
    if mesh.terrain is None:
        raise MapError("it has no terrain")
    return _terrain_bytes(data, mesh)


def with_terrain(data: bytes, part: bytes) -> bytes:
    """
    The file with its terrain part replaced whole by `part` (another map's
    grid: a look copied to another number stands on its source's), every
    other byte kept and the file its own length. Whole, as a tile's place in
    the part depends on the grid's width (the (z x width + x)th of its
    level's 256), so one map's grid can't be laid into another's file tile
    by tile when their sizes differ. MapError for a file with no terrain or
    a part that isn't one.
    """
    read_terrain(part)
    mesh = read_mesh(data)
    if mesh.terrain is None:
        raise MapError("it has no terrain")
    o = mesh.terrain.offset
    out = bytearray(data)
    out[o:o + TERRAIN_BYTES] = part
    return bytes(out)


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
            mesh.terrain = _read_terrain(data, pointers["terrain"])
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


def has_no_tile(tile: Tile) -> bool:
    """An upper level place with no tile: all eight bytes zero, or the game's placeholder."""
    return tile.level == 1 and (tile.is_blank or tile.is_placeholder)


def underside(tile: Tile) -> int:
    """
    A tile's underside, in half height steps: twice its lowest corner's
    height less twice its thickness (see `UNIT_ROOM`).
    """
    return 2 * min(tile.corner_heights()) - 2 * tile.get("thickness")


def _below(ground: Tile, beside) -> int:
    """Twice the highest corner of `ground` and of the tiles `beside` it, in half height steps."""
    return max(2 * max(t.corner_heights()) for t in (ground, *beside))


def room_under(upper: Tile, ground: Tile, beside=()) -> int:
    """
    Half height steps between `upper`'s underside and the highest corner of
    the ground under it and of the ground tiles `beside` it (where units
    step in from). A unit fits where it is `UNIT_ROOM` or more.
    """
    return underside(upper) - _below(ground, beside)


def can_go_under(upper: Tile, ground: Tile, beside=()) -> bool:
    """
    Whether units can get onto `ground` under the upper level tile `upper`:
    room over the ground itself, and from at least one of the ground tiles
    `beside` it units can stand on (with none beside, the ground's room
    alone). 241 of the game's 242 upper level tiles the cursor can stop on,
    over ground units stand on, can be gone under so; 033's (5, 4) has room
    over its ground and both its walkable sides 5 and 6 steps higher.
    """
    if room_under(upper, ground) < UNIT_ROOM:
        return False
    return not beside or any(room_under(upper, ground, [b]) >= UNIT_ROOM for b in beside)


def least_upper_height(ground: Tile, beside=(), thickness: int = UPPER_THICKNESS) -> int:
    """
    The least height, in whole steps, a flat upper level tile `thickness`
    steps thick over `ground` must have for units to get under it
    (`can_go_under`): over the ground, and over the lowest of the tiles
    `beside` it.
    """
    lowest = min(beside, key=lambda t: max(t.corner_heights()), default=None)
    return -(-(_below(ground, [lowest] if lowest is not None else []) + UNIT_ROOM) // 2) + int(thickness)


def upper_tile_fields(ground: Tile, steps: int = UPPER_STEPS) -> dict:
    """
    `{field: value}`: a new tile on the upper level over `ground` (Zodi's
    list after shaping, "an upper level where a map has none": a bridge or a
    floor a model has over the ground), `steps` height steps over its
    highest corner, with its surface (`BRIDGE_SURFACE` over water), flat,
    `UPPER_THICKNESS` steps thick, units able to stand there and the cursor
    to stop; every other field 0, as the game's own have them mostly. Every
    one of `TILE_FIELDS`, so written over a placeholder or a blank place it
    makes the same tile. With the defaults it leaves units room to get under
    it from ground up to 3 steps higher beside it (`room_under`).
    """
    _low, high = field_range("height")
    surface = BRIDGE_SURFACE if ground.get("depth") else ground.get("surface")
    return {"surface": surface, "height": min(high, max(ground.corner_heights()) + steps),
            "slope_height": 0, "depth": 0, "slope": 0, "thickness": UPPER_THICKNESS, "no_cursor": False,
            "no_walk": False, "shading": 0, "pass_through": False, "camera": 0}


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
    return bytes(data[o:o + TERRAIN_BYTES])


#: A map's texture animation records (`Mesh.texture_animations`): 32 of 20
#: bytes at the 0x6C pointer (the decompilation's
#: `battle_map_texture_animation_t`). An event opens a door by starting one
#: (instruction 0x55, "A ground object's state"), and the remaster's look
#: plays its door with it: Zodi's test 12 (22 October) put 062's over
#: 097's in the files a look copied there stands on, and the chapel door
#: opened on the copy, where with 097's own it hadn't.
ANIMATION_RECORDS_BYTES = 640


def _records_at(data: bytes, mesh: Mesh) -> int:
    at = mesh.pointers.get("texture_animations")
    if not at:
        raise MapError("it has no texture animation records")
    after = [v for v in mesh.pointers.values() if v > at]
    if (min(after) if after else len(data)) - at < ANIMATION_RECORDS_BYTES:
        raise MapError("its texture animation records have less than 640 bytes")
    return at


#: The record modes an event starts (`USE_FIELD_OBJECT`, 0x55), which play
#: once when started: 5 to 12 a UV animation's frames forward, 13 to 20 a
#: palette's, 21 to 28 a UV animation's backward (the decompilation's
#: `battle_map_texture_animation_mode_e`; the eight of a kind alike). 1 to
#: 4 loop from the start, 29 cycles colors.
ONCE_FORWARD, ONCE_PALETTE, ONCE_BACKWARD = range(5, 13), range(13, 21), range(21, 29)


def started_records(records: bytes) -> list:
    """The records (`animation_records`' 32) an event can start, as `[(index, mode)]`: its doors and such."""
    out = []
    for i in range(min(32, len(records) // 20)):
        mode = records[20 * i + 14]
        if ONCE_FORWARD.start <= mode < ONCE_BACKWARD.stop:
            out.append((i, mode))
    return out


def animation_records(data: bytes) -> bytes:
    """A map file's texture animation records, all 640 bytes (`ANIMATION_RECORDS_BYTES`); MapError for a file
    with none, or with less room."""
    at = _records_at(data, read_mesh(data))
    return bytes(data[at:at + ANIMATION_RECORDS_BYTES])


def with_animation_records(data: bytes, records: bytes) -> bytes:
    """
    The file with its texture animation records replaced by `records`
    (another map's: a look copied to another map number takes its doors'
    with it), every other byte kept and the file its own length. MapError
    for a file with no records, or records that aren't 640 bytes.
    """
    if len(records) != ANIMATION_RECORDS_BYTES:
        raise MapError(f"texture animation records are {ANIMATION_RECORDS_BYTES} bytes, these are {len(records)}")
    at = _records_at(data, read_mesh(data))
    out = bytearray(data)
    out[at:at + ANIMATION_RECORDS_BYTES] = records
    return bytes(out)


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
