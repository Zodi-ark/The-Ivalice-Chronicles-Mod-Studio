"""
The enhanced battle maps: `bg/meshes/map_NNN_mesh.bin` (FFTOMESH, The
Ivalice Chronicles' own format) and the TGA pictures in `bg/textures/NNN/`.

Nothing public describes FFTOMESH. The layout below was measured on all 108
files, each read to its last byte, and checked against what does not
depend on this reading (`dev/test_map_enhanced.py`): the game's own
`RefinedBg*` tables, the picture files, and the classic mesh of the same
map, whose polygons most of the enhanced ones are.

    0x00  "FFTOMESH", u32 map number, u32 block count,
          five u32 (4096, 4096, 4096, 4096, 8192), 12 zero bytes
    0x30  the blocks, one after another

  A block:
    32 name slots of 32 bytes, zero ended and 0xFE padded: the parts of the
        map ("GT_0_map", "GT_1_waterside" ...; "l_..." names an animated part)
    u32 names used, then the corners of its polygons by kind: u32 textured
        quads, u32 textured triangles, u32 untextured quads, u32 untextured
        triangles; u32 V, the UV pool's size (the same in every block); and
        three u32 zeros. With T the textured corners and A all of them:
    A bytes      the part (name slot) of each corner, the same for all the
                 corners of a polygon
    A x 16       x, y, z float32, then 4 bytes: a polygon's first corner
                 carries the tile it is drawn for (the classic mesh's 2
                 bytes, 0xFFFE unbound), its second the index of the classic
                 polygon it was made from among those of its kind (0xFFFF
                 for a new one), its LAST its render properties (u16, below);
                 the rest are markers, the same on every polygon of a kind
                 in a block (block 0's end 0xFFFF, a moving block's 0x0000)
    T x 8        normal: int16 x, y, z / 4096, 2 zero bytes
    T x 32       u32 its entry in the UV pool, u32 0, u32 its texture
                 group, 20 zero bytes
    V x 28       the UV pool: u32 texture group, float32 u, v, 16 bytes;
                 the same pool in every block, and every entry used
    32 x 16      two float64 per TEXTURE GROUP, by its number: how many
                 times its colour picture repeats across the UVs, in u and
                 v (`Block.repeat`; 1.0, 1.0 on most, more on water)

  A used name slot is the name, a zero and 0xFE to its end; an unused one
  is zeros. `write_mesh` writes all of it back: every one of the 108 files
  comes out byte for byte (`dev/test_map_enhanced.py`).

**Each polygon's render properties** are the first two bytes of its last
corner's word, as the classic polygons' 16 bits are: bit 15 unlit, bits 13,
12, 11 and 10 left out from the SW, NW, NE and SE camera corners. Measured:
on the 46,003 enhanced polygons made from a classic one, those four bits are
the classic polygon's on 86%, and set on some of the 17,227 new ones; the
remaster adjusted the rest for its own walls. The Map Editor leaves out by
these.

  Polygons are in file order: textured quads, textured triangles, then the
  untextured ones, each polygon's corners in order around it. Block 0 is
  the map; the other blocks (10 maps have them) are the parts that move -
  doors, windmills, flags - like the classic mesh's animated meshes.

**Highlight panels follow the grid** (`panels_following`). The game draws a
tile's move and target highlights on the `panel_ui` polygons over it, not
from the grid: Zodi raised every tile two steps in the game and the units
stood two steps up on highlights left on the ground. 11,516 of the 14,311
panels have their corners on their tile's corners, 0.2 above it; the rest
are split tiles. So a panel is moved with its tile: by how much the tile's
surface rose or fell under each corner, from the game's own panel. Seen in
the game (`Map_Grid_Test_2.zip`, every tile and its panels two steps up):
the highlights stood on the raised tiles.

**A picture's repeat.** The 32 pairs at a block's end were first read as
one per name slot. They are one per texture group: how many times the
group's colour picture repeats across its polygons' UVs. 99 groups on 27
maps have them, 92 of them water (009's waterfalls 6 across and 6 down;
its ripples 5, whose UVs are each a fifth of the picture, so a ripple is
the whole of it), the rest grass, a tree, candles, 055's effect and
096's "right"; every map, border, shadow and panel group has 1, and every
block of a mesh the same pairs. Drawn without them, water showed a blown
up corner of its picture. The lighting picture is not repeated: it
covers the UVs once.

**The two versions share their coordinates.** Every corner of the
enhanced mesh is where the classic map's are - x and z on a 28-unit grid,
y on 12-unit steps - and 326 of map 048's 407 enhanced quads have exactly
the corners of one of its classic quads, which is the one the quad says it
came from. The battle grid is the classic map's: the enhanced files have no
terrain of their own, only each polygon's note of its tile.

**Pictures.** A texture group has a colour picture and a lighting picture
(`gt_<group>_map<NNN>_<name>_color.tga`, `..._lighting.tga`), sharing the
polygons' UVs; animated groups number their colour frames (`_color_0`
...). The game's `RefinedBgTexture` table lists them by map, group and kind
(0 colour, 1 lighting, 2 a second lighting 26 groups have); where the
database is to hand it is the authority, as a few groups borrow another
group's lighting. On the page a colour is drawn as colour x lighting x 2.

**Lightings** (`lightings_from_database`). Each of those rows names its
pictures as a list, not one: `Unknown8` one entry per story or event
lighting (20 maps have 2 to 4: 085's are `_lighting_a`, `_a`, `_b`, and on
some maps the colour pictures change with them too), `Unknown18` the six
the random battles use (`_ra` to `_rf`, on 19 maps from 071 to 090), with
`Unknown10` the frame counts of the first. The game's tables don't say
which battle uses which; the Map Editor offers each.

**The anim files** (`read_anim`): `bg/anims/map_NNN_anim.bin` (FFTOANIM),
63 of them, each 1,040,184 bytes:

    0x00   "FFTOANIM", u32 map number, 20 zero bytes
    0x20   32 name slots of 32 bytes, zero ended and 0xFE padded as the
           mesh's: its tracks, named for the part they move ("l_GT_5_anim",
           "l_GT_6_rot")
    0x420  u32 tracks used, 20 zero bytes
    0x438  32 tracks of 32,472 bytes: 9 channels of 900 float32 and a u32
           count, then 36 zero bytes

  Read back from that, 57 of the files are the game's byte for byte; the
  other 6 also have numbers past a channel's count (in the second channel
  of 001's gates and 012's doors, say), which nothing here reads.

Only the third channel ever counts anything. On the 199 tracks of texture
groups whose colour picture has frames (57 maps) it is the frame shown at
each tick (`picture_tracks`): every value is one of the group's frames as
`RefinedBgTexture` counts them, and 194 tracks show every one. So each
animated picture has its own speed, starting frame and order: map 006's
fires flicker 7 ticks a frame, the two quads crossing in each 5 frames
apart; 009's water surface plays its 30 frames over 271 ticks, its
waterfalls 6 ticks a frame; 004's candle goes 0 1 2 1 0 2 1. 22 other
tracks step through numbers on groups of one picture, the moving parts'
(windmills, gears) and light shafts': what they drive is not known, and
nothing here uses them. 6 count nothing (001's gates, 012's doors, 064's
water gate, 078's ripples). A track's group is the number after GT_ in
its name (224 of the 227 are also in `RefinedBgAnim`'s order); 5 groups
with frames have no track (047's four, 056's one). How many ticks a
second is not in the files. 60 is chosen (`TICKS_A_SECOND`): on 013, 014,
039 and 047 a frame lasts as many ticks as the classic map's (15, 5, 7 and
8), whose unit GaneshaDx reads as 60ths of a second.

Nothing here imports Qt.
"""
from __future__ import annotations

import json
import math
import os
import re
import sqlite3
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .nxd_data import ADDED_ROW

MAGIC = b"FFTOMESH"
MESH_FOLDER = "bg/meshes"
TEXTURE_FOLDER = "bg/textures"
UNBOUND = b"\xfe\xff"
NEW_POLYGON = 0xFFFF

_MESH_NAME = re.compile(r"map_(\d{3})_mesh\.bin$", re.IGNORECASE)


def is_panel(part: str) -> bool:
    """
    Whether a part is highlight panels ("GT_6_panel_ui" ...): polygons over
    the tiles, on 1,600-odd of which some maps draw the game's move and
    target highlights with the pictures in bg/ui/panel. Not map scenery.
    """
    return "panel_ui" in part.lower()


class EnhancedMapError(ValueError):
    """Raised for a file this module cannot read as an enhanced map."""


@dataclass
class Polygon:
    block: int
    kind: str               # "tq", "tt", "uq", "ut"
    corners: tuple          # indices into the block's corner arrays
    part: str               # its name slot's name
    group: Optional[int]    # texture group (textured only)
    tile: Optional[tuple]   # (x, z, level), or None when unbound
    source: Optional[int]   # the classic polygon it was made from, among its kind
    render: int = 0         # render properties: bit 15 unlit, 13-10 left out from SW NW NE SE
    number: int = 0         # its place in its block's polygons, in file order

    @property
    def textured(self) -> bool:
        return self.kind in ("tq", "tt")


@dataclass
class Block:
    offset: int
    names: list
    counts: tuple           # corners: textured quads, textured triangles, untextured quads, triangles
    pool_size: int
    parts: bytes
    positions: list         # (x, y, z) per corner; y is negative upward
    words: list             # 4 bytes per corner
    normals: list           # (x, y, z) int16 per textured corner
    uv_index: list          # per textured corner
    groups: list            # texture group per textured corner
    pool: list              # (group, u, v) per pool entry
    pool_extra: list        # the 16 bytes after each pool entry's u, v
    #: (u, v) per texture group, by its number: how many times its colour
    #: picture repeats across the UVs (`repeat`). The name is the one this
    #: had when it was thought to be one pair per name slot.
    slot_values: list

    def repeat(self, group: int) -> tuple:
        """How many times a texture group's colour picture repeats across its UVs, (u, v)."""
        if 0 <= group < len(self.slot_values):
            u, v = self.slot_values[group]
            return (float(u), float(v))
        return (1.0, 1.0)

    def polygons(self, block_number: int = 0) -> list:
        qv, tv, uq, ut = self.counts
        spans = [("tq", 0, qv, 4), ("tt", qv, tv, 3), ("uq", qv + tv, uq, 4), ("ut", qv + tv + uq, ut, 3)]
        out = []
        for kind, start, total, size in spans:
            for i in range(total // size):
                corners = tuple(start + size * i + k for k in range(size))
                first, second = self.words[corners[0]], self.words[corners[1]]
                tile = None
                if first[:2] != UNBOUND:
                    tile = (first[1], first[0] >> 1, first[0] & 1)
                source = second[2] | (second[3] << 8)
                part = self.parts[corners[0]]
                textured = kind in ("tq", "tt")
                render = struct.unpack_from("<H", self.words[corners[-1]], 0)[0]
                out.append(Polygon(block_number, kind, corners,
                                   self.names[part] if part < len(self.names) else "",
                                   self.groups[corners[0]] if textured else None,
                                   tile, None if source == NEW_POLYGON else source,
                                   render, len(out)))
        return out

    def uv(self, corner: int) -> tuple:
        _g, u, v = self.pool[self.uv_index[corner]]
        return (u, v)


@dataclass
class EnhancedMesh:
    map_number: int
    blocks: list

    def polygons(self) -> list:
        out = []
        for i, block in enumerate(self.blocks):
            out.extend(block.polygons(i))
        return out


def mesh_numbers(game_dir: Path) -> list:
    """The map numbers with an enhanced mesh in the unpacked game."""
    try:
        names = os.listdir(Path(game_dir) / MESH_FOLDER)
    except OSError:
        return []
    return sorted(int(m.group(1)) for n in names for m in [_MESH_NAME.match(n)] if m)


def mesh_path(game_dir: Path, number: int) -> Path:
    return Path(game_dir) / MESH_FOLDER / f"map_{number:03d}_mesh.bin"


def read_mesh(data: bytes) -> EnhancedMesh:
    if data[:8] != MAGIC:
        raise EnhancedMapError("not an FFTOMESH file")
    try:
        number, count = struct.unpack_from("<2I", data, 8)
        if count > 64:
            raise EnhancedMapError(f"{count} blocks is not a map")
        o = 0x30
        blocks = []
        for _ in range(count):
            start = o
            names = [data[o + 32 * i:o + 32 * i + 32].split(b"\0")[0].decode("ascii", "replace")
                     for i in range(32)]
            o += 0x400
            used, qv, tv, uq, ut, pool_size = struct.unpack_from("<6I", data, o)
            o += 36
            textured, total = qv + tv, qv + tv + uq + ut
            if qv % 4 or tv % 3 or uq % 4 or ut % 3 or used > 32:
                raise EnhancedMapError("its counts are not whole polygons")
            end = o + total * 17 + textured * 40 + pool_size * 28 + 512
            if end > len(data):
                raise EnhancedMapError("a block runs past the end of the file")
            parts = bytes(data[o:o + total]); o += total
            positions = [struct.unpack_from("<3f", data, o + 16 * i) for i in range(total)]
            words = [bytes(data[o + 16 * i + 12:o + 16 * i + 16]) for i in range(total)]
            o += 16 * total
            normals = [struct.unpack_from("<3h", data, o + 8 * i) for i in range(textured)]
            o += 8 * textured
            uv_index, groups = [], []
            for i in range(textured):
                index, _zero, group = struct.unpack_from("<3I", data, o + 32 * i)
                if index >= pool_size:
                    raise EnhancedMapError("a corner's UV is outside the pool")
                uv_index.append(index)
                groups.append(group)
            o += 32 * textured
            pool, extra = [], []
            for i in range(pool_size):
                pool.append(struct.unpack_from("<I2f", data, o + 28 * i))
                extra.append(bytes(data[o + 28 * i + 12:o + 28 * i + 28]))
            o += 28 * pool_size
            slots = [struct.unpack_from("<2d", data, o + 16 * i) for i in range(32)]
            o += 512
            blocks.append(Block(start, names[:used], (qv, tv, uq, ut), pool_size, parts, positions,
                                words, normals, uv_index, groups, pool, extra, slots))
        if o != len(data):
            raise EnhancedMapError(f"{len(data) - o} bytes left over after its blocks")
    except struct.error as exc:
        raise EnhancedMapError("a part runs past the end of the file") from exc
    return EnhancedMesh(number, blocks)


def write_mesh(mesh: EnhancedMesh) -> bytes:
    """
    The file for a mesh: `read_mesh`'s inverse. Every byte the reader does not
    keep is the same in all 108 of the game's files (the header's five
    numbers, name slot padding, the zeros), so a mesh read and written back
    is the file it was read from.
    """
    out = bytearray(MAGIC + struct.pack("<2I", mesh.map_number, len(mesh.blocks)))
    out += struct.pack("<5I", 4096, 4096, 4096, 4096, 8192) + bytes(12)
    pools = {tuple(zip(b.pool, b.pool_extra)) for b in mesh.blocks}
    if len(pools) > 1:
        raise EnhancedMapError("its blocks have different UV pools; the game's share one")
    for b in mesh.blocks:
        if len(b.names) > 32:
            raise EnhancedMapError(f"{len(b.names)} parts in a block; there is room for 32")
        for i in range(32):
            if i < len(b.names):
                raw = b.names[i].encode("ascii")
                if len(raw) > 31:
                    raise EnhancedMapError(f"the part name {b.names[i]!r} is longer than 31 letters")
                out += raw + b"\0" + b"\xfe" * (31 - len(raw))
            else:
                out += bytes(32)
        qv, tv, uq, ut = b.counts
        textured = qv + tv
        total = textured + uq + ut
        if not (len(b.parts) == len(b.positions) == len(b.words) == total
                and len(b.normals) == len(b.uv_index) == len(b.groups) == textured
                and len(b.pool) == len(b.pool_extra) == b.pool_size and len(b.slot_values) == 32):
            raise EnhancedMapError("a block's lists don't agree with its counts")
        out += struct.pack("<9I", len(b.names), qv, tv, uq, ut, b.pool_size, 0, 0, 0)
        out += bytes(b.parts)
        for position, word in zip(b.positions, b.words):
            out += struct.pack("<3f", *position) + bytes(word)
        for normal in b.normals:
            out += struct.pack("<3h", *normal) + bytes(2)
        for index, group in zip(b.uv_index, b.groups):
            out += struct.pack("<3I", index, 0, group) + bytes(20)
        for (group, u, v), extra in zip(b.pool, b.pool_extra):
            out += struct.pack("<I2f", group, u, v) + bytes(extra)
        for a, c in b.slot_values:
            out += struct.pack("<2d", a, c)
    return bytes(out)


# =============================================================================
# Building a mesh polygon by polygon
# =============================================================================

KINDS = ("tq", "tt", "uq", "ut")
CORNER_COUNT = {"tq": 4, "tt": 3, "uq": 4, "ut": 3}


@dataclass
class CornerData:
    """A corner as a polygon owns it: where it is, its word, and, textured, its normal and UV."""
    position: tuple                 # file coordinates (y negative upward)
    word: bytes                     # its 4 bytes (tile, source, render or markers)
    normal: tuple = (0, 0, 0)       # int16, 4096 = 1 (textured only)
    uv: tuple = (0.0, 0.0)          # (textured only)
    extra: bytes = bytes(16)        # its UV pool entry's last 16 bytes (textured only)


@dataclass
class PolygonData:
    kind: str                       # "tq", "tt", "uq", "ut"
    part: int                       # its name slot
    corners: list                   # CornerData, in order round it
    group: int = 0                  # texture group (textured only)


@dataclass
class BlockData:
    names: list
    slot_values: list               # 32 (float64, float64)
    polygons: list                  # PolygonData


def blocks_of(mesh: EnhancedMesh) -> list:
    """Every block as `BlockData`: its polygons with their corners owned, in file order."""
    out = []
    for number, block in enumerate(mesh.blocks):
        polygons = []
        for poly in block.polygons(number):
            corners = []
            for c in poly.corners:
                corner = CornerData(tuple(block.positions[c]), bytes(block.words[c]))
                if poly.textured:
                    _group, u, v = block.pool[block.uv_index[c]]
                    corner.normal = tuple(block.normals[c])
                    corner.uv = (u, v)
                    corner.extra = bytes(block.pool_extra[block.uv_index[c]])
                corners.append(corner)
            polygons.append(PolygonData(poly.kind, block.parts[poly.corners[0]], corners,
                                        poly.group if poly.textured else 0))
        out.append(BlockData(list(block.names), list(block.slot_values), polygons))
    return out


def assemble(map_number: int, blocks: list) -> EnhancedMesh:
    """
    A mesh from `BlockData`: each block's polygons put in the file's order
    (textured quads, textured triangles, untextured quads, untextured
    triangles), and one UV pool for them all, as the game's files have -
    by texture group, each different entry once.
    """
    entries, pool_index = [], {}
    for block in blocks:
        for poly in block.polygons:
            if poly.kind in ("tq", "tt"):
                for corner in poly.corners:
                    key = (poly.group, *_f32(corner.uv), bytes(corner.extra))
                    if key not in pool_index:
                        pool_index[key] = None
                        entries.append(key)
    entries.sort(key=lambda e: e[0])
    for i, key in enumerate(entries):
        pool_index[key] = i
    pool = [(g, u, v) for g, u, v, _e in entries]
    extras = [e for _g, _u, _v, e in entries]
    out = []
    for block in blocks:
        ordered = [p for kind in KINDS for p in block.polygons if p.kind == kind]
        for p in ordered:
            if p.kind not in CORNER_COUNT or len(p.corners) != CORNER_COUNT[p.kind]:
                raise EnhancedMapError(f"a {p.kind} polygon with {len(p.corners)} corners")
            if not 0 <= p.part < len(block.names):
                raise EnhancedMapError(f"a polygon in part {p.part}, of {len(block.names)}")
        counts = tuple(sum(CORNER_COUNT[k] for p in ordered if p.kind == k) for k in KINDS)
        parts, positions, words, normals, uv_index, groups = bytearray(), [], [], [], [], []
        for p in ordered:
            for corner in p.corners:
                parts.append(p.part)
                positions.append(tuple(corner.position))
                if len(corner.word) != 4:
                    raise EnhancedMapError("a corner's word is not 4 bytes")
                words.append(bytes(corner.word))
        for p in ordered:
            if p.kind in ("tq", "tt"):
                for corner in p.corners:
                    normals.append(tuple(int(n) for n in corner.normal))
                    uv_index.append(pool_index[(p.group, *_f32(corner.uv), bytes(corner.extra))])
                    groups.append(p.group)
        slots = list(block.slot_values) + [(1.0, 1.0)] * (32 - len(block.slot_values))
        out.append(Block(0, list(block.names), counts, len(pool), bytes(parts), positions, words,
                         normals, uv_index, groups, list(pool), list(extras), slots[:32]))
    return EnhancedMesh(map_number, out)


def _f32(pair) -> tuple:
    """Floats as the file will hold them, so two that write the same are one pool entry."""
    return struct.unpack("<2f", struct.pack("<2f", *pair))


# =============================================================================
# Highlight panels that follow the grid
# =============================================================================

def panels_following(mesh: EnhancedMesh, game_mesh: EnhancedMesh, height_change) -> tuple:
    """
    `(mesh, panels moved)`: `mesh` with each highlight panel put where the
    game's own panel is (`game_mesh`: the same block, kind, tile and corners
    across the ground), raised or lowered by `height_change(tile, x, z)` -
    how many height steps the tile the panel is drawn for rose at that point
    of it (x and z in file units). A panel with no match in the game's mesh,
    or no tile, is left as it is. From the game's panels, not `mesh`'s own,
    so doing it again to a mesh it was done to gives the same file, and a
    mesh rebuilt in another order (`map_package`) still finds them.
    """
    from . import map_classic as mc

    def key(number, poly, positions):
        return (number, poly.kind, poly.tile,
                tuple((round(positions[c][0], 2), round(positions[c][2], 2)) for c in poly.corners))

    game = {}
    for number, block in enumerate(game_mesh.blocks):
        for poly in block.polygons(number):
            if is_panel(poly.part):
                game.setdefault(key(number, poly, block.positions),
                                [block.positions[c] for c in poly.corners])
    moved = 0
    blocks = []
    for number, block in enumerate(mesh.blocks):
        positions = list(block.positions)
        for poly in block.polygons(number):
            if not is_panel(poly.part) or poly.tile is None:
                continue
            original = game.get(key(number, poly, block.positions))
            if original is None:
                continue
            changed = False
            for c, (x, y, z) in zip(poly.corners, original):
                rise = height_change(poly.tile, x, z)
                new = (x, y - rise * mc.HEIGHT_STEP, z)
                changed |= new != tuple(positions[c])
                positions[c] = new
            moved += changed
        blocks.append(Block(block.offset, block.names, block.counts, block.pool_size, block.parts,
                            positions, block.words, block.normals, block.uv_index, block.groups,
                            block.pool, block.pool_extra, block.slot_values))
    return EnhancedMesh(mesh.map_number, blocks), moved


def panels_only(game_data: bytes, mod_data: bytes) -> bool:
    """
    Whether a mod's mesh is the game's with nothing changed but where its
    highlight panels are: what an export makes from grid edits, and makes
    again from them, so an opened mod's copy needn't be carried through.
    """
    if len(game_data) != len(mod_data):
        return False
    if game_data == mod_data:
        return True
    try:
        game, mod = read_mesh(game_data), read_mesh(mod_data)
    except EnhancedMapError:
        return False
    if len(game.blocks) != len(mod.blocks):
        return False
    blocks = []
    for number, (g, m) in enumerate(zip(game.blocks, mod.blocks)):
        if g.counts != m.counts or len(g.positions) != len(m.positions):
            return False
        positions = list(g.positions)
        for poly in g.polygons(number):
            if is_panel(poly.part):
                for c in poly.corners:
                    positions[c] = m.positions[c]
        blocks.append(Block(g.offset, g.names, g.counts, g.pool_size, g.parts, positions, g.words,
                            g.normals, g.uv_index, g.groups, g.pool, g.pool_extra, g.slot_values))
    return write_mesh(EnhancedMesh(game.map_number, blocks)) == mod_data


def tile_rise(game_tiles: dict, edited_tiles: dict):
    """
    `height_change` for `panels_following`: `{(x, z, level): Tile}` as the
    game has them and as edited. How much a tile's surface rose at a point,
    the four corners' rises (height and slope) blended across it.
    """
    from . import map_classic as mc

    def rise(tile, x, z):
        before, after = game_tiles.get(tuple(tile)), edited_tiles.get(tuple(tile))
        if before is None or after is None:
            return 0.0
        deltas = [a - b for a, b in zip(after.corner_heights(), before.corner_heights())]
        if not any(deltas):
            return 0.0
        u = min(1.0, max(0.0, x / mc.TILE_SIZE - tile[0]))
        w = min(1.0, max(0.0, z / mc.TILE_SIZE - tile[1]))
        # Corners (x0,z0), (x1,z0), (x1,z1), (x0,z1).
        return ((1 - u) * (1 - w) * deltas[0] + u * (1 - w) * deltas[1]
                + u * w * deltas[2] + (1 - u) * w * deltas[3])

    return rise


# =============================================================================
# Pictures
# =============================================================================

@dataclass
class GroupPictures:
    colour: list            # frame file names, in order (one for a still group)
    lighting: Optional[str]
    lighting2: Optional[str] = None


_PICTURE = re.compile(r"gt_(\d+)_map(\d{3})_.+?_(color|lighting2?)(?:_[a-z])?(?:_(\d+))?\.tga$",
                      re.IGNORECASE)


def texture_folder(game_dir: Path, number: int) -> Path:
    return Path(game_dir) / TEXTURE_FOLDER / f"{number:03d}"


def _frame_names(name: str, count: int) -> list:
    """A colour picture's frames: `..._color_0` with a count of 8 is `_0` to `_7`."""
    if count > 1 and re.search(r"_0$", name):
        stem = name[:-2]
        return [f"{stem}_{i}.tga" for i in range(count)]
    return [f"{name}.tga"]


@dataclass
class Lighting:
    """
    One of a map's lightings: the pictures each texture group is drawn with
    under it. `kind` is "story" (`RefinedBgTexture`'s lists for story and
    event battles, the first being the one the map is drawn with), "second"
    (the groups with a second lighting drawn with it) or "random" (the
    random battles' lists), `index` its place in that list, and `suffix`
    what its first lighting picture's name says after "lighting" ("", "_a",
    "_ra", "2" ...), which is how the game's files tell them apart.
    """
    kind: str
    index: int
    suffix: str
    pictures: dict                      # {group: GroupPictures}


#: The `RefinedBgTexture` columns a lighting is read from, in `_table_rows`' order.
TEXTURE_COLUMNS = ("Unknown8", "Unknown10", "Unknown18")


def _table_rows(sqlite_path: Path, number: int, rows: Optional[dict] = None) -> list:
    """
    Map `number`'s `RefinedBgTexture` rows, `(group, kind, Unknown8,
    Unknown10, Unknown18)` in key order: the game's, with `rows` over them -
    a mod's, as `state.unmodelled_table_edits` holds them (`{(map, group,
    kind): {column: value}}`; its edits change a row's columns, and the rows
    it adds are added). The Map Editor's new texture groups are such rows.
    """
    found = {}
    if sqlite_path:
        try:
            con = sqlite3.connect(f"file:{Path(sqlite_path).as_posix()}?mode=ro", uri=True)
            try:
                for row in con.execute("SELECT Key2, Key3, Unknown8, Unknown10, Unknown18 FROM "
                                       "RefinedBgTexture WHERE Key = ? ORDER BY Key2, Key3", (number,)):
                    found[(row[0], row[1])] = list(row[2:])
            finally:
                con.close()
        except sqlite3.Error:
            found = {}
    for key, fields in (rows or {}).items():
        if not isinstance(key, tuple) or len(key) != 3 or key[0] != number:
            continue
        current = found.get(key[1:])
        if current is None:
            if not fields.get(ADDED_ROW):
                continue
            current = found[key[1:]] = [None, None, None]
        for i, column in enumerate(TEXTURE_COLUMNS):
            if column in fields:
                current[i] = fields[column]
    return [key + tuple(values) for key, values in sorted(found.items())]


def _lighting_suffix(name: Optional[str]) -> str:
    match = re.search(r"lighting(.*?)(?:\.tga)?$", name or "", re.IGNORECASE)
    return match.group(1) if match else ""


def lightings_from_database(sqlite_path: Path, number: int, rows: Optional[dict] = None) -> list:
    """
    Every lighting the game's `RefinedBgTexture` table gives a map (key map,
    group, kind 0 colour / 1 lighting / 2 second lighting; `Unknown8` the
    pictures of each story or event lighting, `Unknown10` their frame
    counts, `Unknown18` the random battles' pictures, all JSON lists): the
    story ones in order, the first being the usual, then the second
    lightings, then the random battles'. One whose pictures are another's
    is left out. Empty when the table is not there. `rows` are a mod's,
    over the game's (`_table_rows`).
    """
    table = {}
    for group, kind, names, frames, random in _table_rows(sqlite_path, number, rows):
        try:
            table[(group, kind)] = (json.loads(names or "[]"), json.loads(frames or "[]"),
                                    json.loads(random or "[]"))
        except ValueError:
            continue
    if not table:
        return []
    groups = sorted({group for group, _kind in table})

    def pick(names: list, index: int):
        return names[index] if index < len(names) else (names[0] if names else None)

    def story(index: int, second: bool = False) -> dict:
        out = {}
        for group in groups:
            colours, counts, _random = table.get((group, 0), ([], [], []))
            name = pick(colours, index)
            count = pick(counts, index) or 1
            entry = GroupPictures(_frame_names(name, count) if name else [], None)
            light = pick(table.get((group, 1), ([], [], []))[0], index)
            light2 = pick(table.get((group, 2), ([], [], []))[0], index)
            entry.lighting = f"{light}.tga" if light else None
            entry.lighting2 = f"{light2}.tga" if light2 else None
            if second and light2:
                entry.lighting = entry.lighting2
            out[group] = entry
        return out

    def random(index: int) -> dict:
        out = story(0)
        for group in groups:
            colours, counts, randoms = table.get((group, 0), ([], [], []))
            name = pick(randoms, index) if index < len(randoms) and randoms[index] else None
            if name:
                out[group].colour = _frame_names(name, pick(counts, 0) or 1)
            lights = table.get((group, 1), ([], [], []))[2]
            if index < len(lights) and lights[index]:
                out[group].lighting = f"{lights[index]}.tga"
        return out

    def first_lighting(pictures: dict) -> Optional[str]:
        return next((pictures[g].lighting for g in groups if pictures[g].lighting), None)

    found = []
    stories = max(len(table[key][0]) for key in table if key[1] in (0, 1)) if any(
        key[1] in (0, 1) for key in table) else 0
    for index in range(max(stories, 1)):
        pictures = story(index)
        found.append(Lighting("story", index, _lighting_suffix(first_lighting(pictures)), pictures))
    seconds = max((len(table[key][0]) for key in table if key[1] == 2), default=0)
    for index in range(seconds):
        pictures = story(index, second=True)
        second = next((pictures[g].lighting2 for g in groups if pictures[g].lighting2), None)
        found.append(Lighting("second", index, _lighting_suffix(second), pictures))
    randoms = max((len(value[2]) for value in table.values()), default=0)
    for index in range(randoms):
        pictures = random(index)
        found.append(Lighting("random", index, _lighting_suffix(first_lighting(pictures)), pictures))
    out, seen = [], set()
    for lighting in found:
        key = tuple((g, tuple(p.colour), p.lighting) for g, p in sorted(lighting.pictures.items()))
        if key not in seen:
            seen.add(key)
            out.append(lighting)
    return out


def pictures_from_database(sqlite_path: Path, number: int) -> dict:
    """
    `{group: GroupPictures}` from the game's `RefinedBgTexture` table: the
    usual lighting's (`lightings_from_database`). Empty when the table is
    not there.
    """
    found = lightings_from_database(sqlite_path, number)
    return found[0].pictures if found else {}


def pictures_from_files(folder: Path, number: int) -> dict:
    """`{group: GroupPictures}` from the picture files' names alone."""
    out = {}
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return {}
    for name in names:
        m = _PICTURE.match(name)
        if not m or int(m.group(2)) != number:
            continue
        group, kind = int(m.group(1)), m.group(3).lower()
        entry = out.setdefault(group, GroupPictures([], None))
        if kind == "color":
            entry.colour.append((int(m.group(4) or 0), name))
        elif kind == "lighting" and entry.lighting is None:
            entry.lighting = name
        elif kind == "lighting2" and entry.lighting2 is None:
            entry.lighting2 = name
    for entry in out.values():
        entry.colour = [n for _i, n in sorted(entry.colour)]
    return out


def lightings(game_dir: Path, number: int, sqlite_path: Optional[Path] = None,
              rows: Optional[dict] = None) -> list:
    """
    The map's lightings (`Lighting`), the usual first: the game's table when
    a database is given and names them, else the file names' one. `rows`
    are a mod's `RefinedBgTexture` rows over the game's (`_table_rows`):
    with no database, the groups they add join the file names' ones.
    """
    found = lightings_from_database(sqlite_path, number, rows) if sqlite_path else []
    if found:
        return found
    named = pictures_from_files(texture_folder(game_dir, number), number)
    added = lightings_from_database(None, number, rows) if rows else []
    for group, entry in (added[0].pictures.items() if added else ()):
        named.setdefault(group, entry)
    return [Lighting("story", 0, "", named)] if named else []


def pictures(game_dir: Path, number: int, sqlite_path: Optional[Path] = None,
             rows: Optional[dict] = None) -> dict:
    """
    The map's pictures by texture group, under its usual lighting: the
    game's table when a database is given and names them, else the file
    names. `rows` as `lightings` takes them.
    """
    found = lightings(game_dir, number, sqlite_path, rows)
    return found[0].pictures if found else {}


# =============================================================================
# The anim files
# =============================================================================

ANIM_MAGIC = b"FFTOANIM"
ANIM_FOLDER = "bg/anims"
#: Where an anim file keeps its track names and how many it uses, where its
#: tracks start, and their shape: 32 tracks of 9 channels of 900 float32,
#: each with a u32 count after it, and 36 zero bytes after each track.
ANIM_NAMES, ANIM_USED, ANIM_TRACKS = 0x20, 0x420, 0x438
ANIM_SLOTS, ANIM_CHANNELS, ANIM_CAPACITY = 32, 9, 900
ANIM_CHANNEL_SIZE = ANIM_CAPACITY * 4 + 4
ANIM_TRACK_SIZE = ANIM_CHANNELS * ANIM_CHANNEL_SIZE + 36
ANIM_SIZE = ANIM_TRACKS + ANIM_SLOTS * ANIM_TRACK_SIZE
#: The one channel the game's files use: the colour frame shown at each tick.
FRAME_CHANNEL = 2
#: Ticks a second. Chosen: no file or table found says. On four maps a
#: frame lasts as many ticks as the classic map's, which GaneshaDx reads as
#: 60ths of a second.
TICKS_A_SECOND = 60

_TRACK_GROUP = re.compile(r"GT_(\d+)_", re.IGNORECASE)


def anim_path(game_dir: Path, number: int) -> Path:
    return Path(game_dir) / ANIM_FOLDER / f"map_{number:03d}_anim.bin"


def read_anim(data: bytes) -> dict:
    """
    An anim file's tracks: `{name: (channel, ...)}`, each channel the floats
    it holds, one a tick. Raises `EnhancedMapError` for anything else.
    """
    if data[:8] != ANIM_MAGIC:
        raise EnhancedMapError("not an FFTOANIM file")
    if len(data) != ANIM_SIZE:
        raise EnhancedMapError(f"an anim file is {ANIM_SIZE:,} bytes; this one is {len(data):,}")
    used = struct.unpack_from("<I", data, ANIM_USED)[0]
    if used > ANIM_SLOTS:
        raise EnhancedMapError(f"{used} tracks is more than an anim file holds")
    tracks = {}
    for k in range(used):
        name = data[ANIM_NAMES + 32 * k:ANIM_NAMES + 32 * (k + 1)].split(b"\0")[0].decode("ascii", "replace")
        base = ANIM_TRACKS + k * ANIM_TRACK_SIZE
        channels = []
        for c in range(ANIM_CHANNELS):
            start = base + c * ANIM_CHANNEL_SIZE
            count = struct.unpack_from("<I", data, start + ANIM_CAPACITY * 4)[0]
            if count > ANIM_CAPACITY:
                raise EnhancedMapError(f"track {name} has {count} ticks, more than {ANIM_CAPACITY}")
            channels.append(struct.unpack_from(f"<{count}f", data, start))
        tracks[name] = tuple(channels)
    return tracks


def picture_tracks(data: bytes) -> dict:
    """
    `{texture group: (frame, ...)}`: the colour frame each animated group
    shows at each tick (`TICKS_A_SECOND`), from an anim file's tracks. A
    track's group is the number after GT_ in its name; a frame is the
    nearest whole number to the file's (a few are a hair off, 4.955).
    """
    out = {}
    for name, channels in read_anim(data).items():
        match = _TRACK_GROUP.search(name)
        frames = channels[FRAME_CHANNEL]
        if match and frames:
            out.setdefault(int(match.group(1)), tuple(int(math.floor(f + 0.5)) for f in frames))
    return out
