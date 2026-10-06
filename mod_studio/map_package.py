"""
A battle map's enhanced look as files anyone can edit: the model as a
Wavefront OBJ, its textures as PNG, and in JSON what OBJ has no room for.
Made for Blender or any 3D program, for a script, and for an AI coworker
changing a map. Asked for by Zodi as "a streamlined process that allows
users and AI coworkers such as Claude to create new maps and or modify
existing maps appearances (model and textures) ... focus on enhanced".

A package is a folder:

    README.txt    how to edit it, for people and for programs
    map.obj       the model, one object per part of the map
    map.mtl       one material per texture group (group_0 ...), and untextured
    parts.txt     how the game draws each part; a new part's line is added here
    textures/     every texture the map's groups use, as PNG
    guides/       each group's texture, darkened, with its faces drawn on it
    map.json      what the OBJ can't hold; not for editing
    base/         the game's mesh it was made from; not for editing
    built/        what `build` last made from it

**Out**, `export_package`: the enhanced mesh (`map_enhanced`) with each
polygon's corners, UVs and normals written as the OBJ's, in world space
(the Map Editor's: x and y the file's turned round, y up, 28 to a tile).
Positions are joined within a part, so an edit in a 3D program moves every
face at a corner together. The highlight panels are left out: they follow
the battle grid (`map_enhanced.panels_following`), which the Map Editor edits.

**Back**, `build`: the OBJ read, and a mesh made from it.

- **Nothing changed** gives the base mesh back, byte for byte.
- **A part whose faces are the same faces** (as many, each with as many
  corners and the same material) takes their new positions, UVs and
  normals, and keeps everything else the polygon had - the tile it is
  drawn for, the classic polygon it came from, its render properties, its
  markers. A value within a hair of the old one (a 3D program writes six
  decimals) keeps the old one exactly.
- **A part whose faces changed**: each face with the corners of one of the
  part's old polygons is that polygon again; any other face is new, drawn
  from every camera corner, bound to no tile, with the markers the game's
  own polygons of its kind have.
- **Textures**: a PNG whose bytes changed since it was written, or a
  material pointed at another file, replaces that texture in the mod.
- **A texture's repeat** (`map_enhanced.Block.repeat`: water's colour
  texture repeats across its faces, 6 by 6 on 009's waterfalls) is written
  as its material's `map_Kd -s U V 1`, which Blender reads into the
  material and writes back, so water looks there as in the game. Changed
  there, it changes in the game. `-o` beside it is for Blender alone: the
  model's UVs run up where the game's run down, which shifts a repeat that
  isn't whole by its fraction.

**What a custom map needs** (asked for by Zodi, 5 October: "What ever you
need to do to allow for adding new custom maps into the game"). The game
finds a texture group's textures through its `RefinedBgTexture` rows (map,
group, kind) and draws a part as its `RefinedBgMeshNode` row (map, block,
name slot) says (`map_enhanced`'s notes). So:

- **A new texture group** is a material `group_N` with a number the map
  doesn't use (to 31: the mesh holds 32 repeats) and a map_Kd naming its
  colour texture. It becomes `gt_N_mapNNN_<name>_color.tga` and
  `..._lighting.tga` in the mod (the lighting `<texture>_lighting.png`
  beside it, else flat, at the brightness of the map's own lighting), and
  two `RefinedBgTexture` rows shaped as the map's first group's are: as
  many entries for its story lightings and random battles, so the group
  is there under every lighting (`Built.table_rows`).
- **A new part** drawn other than solid gets a `RefinedBgMeshNode` row, as
  `parts.txt` says (`PART_KINDS`, measured on the game's 1,429 rows); a
  solid one needs none, as 87 of the game's own parts on 19 maps have none
  (`DEFAULT_KIND`). `parts.txt` changes how an existing part is drawn too.
- Those rows are written as rows a mod adds (`nxd_data.ADDED_ROW`), which
  the Map Editor puts with the mod's other table edits, and which a mod
  opened again gives back (`nxd_data.recover_unmodelled_edits`). A package
  made from the mod's own look says which groups and parts are its own
  (`map.json`), so building it again keeps their rows.
- **Units stand on the battle grid**, not on the model. `ground_under_tiles`
  says where the tiles under a model's moved ground go: by how far the
  model's ground rose or fell at each tile's corners, from the faces drawn
  for that tile where there are any, else from the faces nearest it.

**Guides** (`draw_guides`): where each face is painted on its group's
texture, drawn on it, darkened, in `guides/` - Zodi asked how a person is
to know where on which texture a part of the model is.

Still out of reach, and said so: new moving parts (the anim file and
`RefinedBgAnim`), a new group with frames, the classic look, and what the
game does with a face bound to no tile. Not tried in the game yet: a
package's new texture groups and parts (the rows are the game's shape;
whether the game picks up rows a mod adds to these tables is not known).

`python -m mod_studio.map_package` does all of it from a command line:
`export`, `check`, `build` and `preview`; `preview` runs
`mod_studio.qt.map_preview` in a process of its own, as nothing here
imports Qt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import sqlite3
import struct
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import map_classic as mc
from . import map_enhanced as me
from .nxd_data import ADDED_ROW

VERSION = 2
KIND_NAME = "The Ivalice Chronicles Mod Studio map package"
MODEL, MATERIALS, METADATA, README = "map.obj", "map.mtl", "map.json", "README.txt"
PARTS = "parts.txt"
BASE, TEXTURES, BUILT, GUIDES = "base", "textures", "built", "guides"
UNTEXTURED = "untextured"
#: A value this close to the old one keeps the old one: Blender writes six
#: decimals, which moves a float32 UV by up to 5e-7.
POSITION_SLACK, UV_SLACK = 1e-3, 2e-6
#: What a new polygon's render properties start from, and the four bits
#: that leave it out from a camera corner, which a new polygon doesn't have.
NEW_RENDER, HIDE_BITS = 0x8001, 0x3C00
#: The markers of the game's own polygons, by kind (measured on all 108
#: files: the same on every polygon of a kind in a block). `T` is the tile,
#: `S` the source, `R` the render properties; `F` is FF FF in block 0 and
#: 00 00 in a moving block.
MARKERS = {"tq": ("TF", "0S", "bF", "RF"), "tt": ("TF", "0S", "RF"),
           "uq": ("TF", "0S", "0F", "RF"), "ut": ("TF", "0S", "RF")}

#: The tables a map's look is found by (`map_enhanced`'s notes).
TEXTURE_TABLE, NODE_TABLE = "RefinedBgTexture", "RefinedBgMeshNode"
#: Texture groups a map has room for: the mesh holds a repeat for 32.
GROUPS = 32
#: A part's `RefinedBgMeshNode` columns, bar its key, DLCFlags and Comment.
NODE_COLUMNS = ("Unknown8", "UnknownC", "Unknown10", "Unknown14", "Unknown15", "Unknown16",
                "Unknown17", "Unknown18")
#: How the game draws a part, by the word `parts.txt` gives it: its row's
#: `NODE_COLUMNS`, the row most of the game's parts of that kind have (1.5.2,
#: 1,429 rows). Unknown8 says which views draw it (0 every view, 1 the side
#: views, 2 the top down view lying flat, 3 the top down view standing);
#: UnknownC the order see through parts are drawn in, higher first;
#: Unknown18 0 a part blended over the map. What Unknown10 and 14 to 17
#: do is not known: each kind has the game's values for them.
PART_KINDS = {
    "solid": (0, 0, 0, 1, 0, 0, 1, 1),        # 987 rows: the map, water, walls
    "edge": (0, 0, 0, 1, 0, 0, 0, 1),         # 100: borders and watersides (Unknown17 0)
    "overlay": (0, 0, 0, 1, 0, 0, 1, 0),      # 63: shadows
    "side": (1, 0, 0, 1, 0, 0, 1, 1),         # 28: trees, flames, a fence
    "top": (2, -1, 0, 0, 0, 0, 1, 1),         # 48: the icons of trees, grass, cacti
    "upright": (3, -1, 0, 0, 1, 0, 1, 1),     # 19: the icons of fires and candles
}
#: A part whose row is none of `PART_KINDS`: drawn as its row says, kept.
OWN_KIND = "own"
#: How a part with no `RefinedBgMeshNode` row is drawn: the usual way. In
#: the 1.5.2 game 87 parts with faces on 19 maps have no row (all of 026's,
#: 004's and 014's; 006's doors, 038's windmills), so a part needs a row
#: only to be drawn otherwise, and a new solid part gets none.
DEFAULT_KIND = "solid"
#: A new group's lighting, flat, where the map's own can't be measured: mid
#: grey, which the Map Editor draws as the colour itself.
FLAT_LIGHTING = 128
#: The colour the guides draw faces' edges in, and how dark the texture
#: under them is drawn (its brightness, 0 to 1).
GUIDE_LINE, GUIDE_SHADE = (255, 214, 0), 0.4


class PackageError(ValueError):
    """Raised for a package that can't be read or built; the message says why, for the person."""


# =============================================================================
# Out
# =============================================================================

def object_name(part: str, block: int) -> str:
    """A part's object name in the OBJ: `GT_0_map`, or `GT_1_door@2` for moving block 2."""
    return part if block == 0 else f"{part}@{block}"


def _world(p) -> tuple:
    return (-p[0], -p[1], p[2])


def _num(value: float) -> str:
    """Short, and exact: what reads back as the same float32."""
    return repr(float(value)) if value != 0 else "0"


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _json_list(value) -> list:
    """A `RefinedBgTexture` list column (JSON text) as a list; [] for nothing."""
    if isinstance(value, list):
        return value
    try:
        out = json.loads(value or "[]")
    except (TypeError, ValueError):
        return []
    return out if isinstance(out, list) else []


def _list_text(values: list) -> str:
    """A list as the game's tables hold one: JSON with no spaces."""
    return json.dumps(values, separators=(",", ":"))


def map_rows(sqlite_path, table: str, number: int, rows: Optional[dict] = None) -> tuple:
    """
    `({(key2, key3): {column: value}}, {(key2, key3) the mod adds})`: map
    `number`'s rows of a triple keyed table, the game's (from `sqlite_path`)
    with a mod's over them (`rows`, `state.unmodelled_table_edits[table]`:
    its edits change a row's columns, the rows it adds are added).
    """
    found, added = {}, set()
    if sqlite_path:
        try:
            con = sqlite3.connect(f"file:{Path(sqlite_path).as_posix()}?mode=ro", uri=True)
            try:
                con.row_factory = sqlite3.Row
                for row in con.execute(f'SELECT * FROM "{table}" WHERE Key = ? ORDER BY Key2, Key3',
                                       (number,)):
                    found[(row["Key2"], row["Key3"])] = {
                        k: row[k] for k in row.keys() if k not in ("Key", "Key2", "Key3")}
            finally:
                con.close()
        except sqlite3.Error:
            found = {}
    for key, fields in (rows or {}).items():
        if not isinstance(key, tuple) or len(key) != 3 or key[0] != number:
            continue
        if key[1:] not in found:
            if not fields.get(ADDED_ROW):
                continue                      # an edit to a row the game hasn't
            found[key[1:]] = {}
            added.add(key[1:])
        found[key[1:]].update({k: v for k, v in fields.items() if k != ADDED_ROW})
    return found, added


def kind_of(row: Optional[dict]) -> tuple:
    """
    `(kind word, order)` for a part's row: one of `PART_KINDS`, or
    `OWN_KIND`. A part with no row is drawn the usual way, as solid ones are
    (`DEFAULT_KIND`).
    """
    if not row:
        return DEFAULT_KIND, 0
    values = tuple(row.get(name) for name in NODE_COLUMNS)
    for kind, wanted in PART_KINDS.items():
        if all(v == w for i, (v, w) in enumerate(zip(values, wanted)) if NODE_COLUMNS[i] != "UnknownC"):
            return kind, int(row.get("UnknownC") or 0)
    return OWN_KIND, int(row.get("UnknownC") or 0)


def kind_row(kind: str, order: Optional[int] = None) -> dict:
    """A part's `RefinedBgMeshNode` columns for a kind, its order given or the kind's own."""
    row = dict(zip(NODE_COLUMNS, PART_KINDS[kind]))
    if order is not None:
        row["UnknownC"] = int(order)
    return row


def export_package(game_dir, number: int, folder, sqlite_path=None, mesh_file=None,
                   picture_files: Optional[dict] = None, rows: Optional[dict] = None,
                   tiles: Optional[dict] = None, grid_file: Optional[str] = None) -> dict:
    """
    Writes map `number`'s enhanced look into `folder` as a package.

    `mesh_file` is the mesh to start from when not the game's (a mod's own);
    `picture_files` `{texture name: image file}` the textures a mod replaces
    or adds; `rows` the mod's table rows (`state.unmodelled_table_edits`),
    for the texture groups and parts it adds or changes. `tiles`
    (`{(x, z, level): Tile}`, as edited) and `grid_file` are the battle grid
    the look stands on, for `ground_under_tiles`; without them the game's
    (`enhanced_grid_file`). Returns a summary: `{"folder", "objects",
    "faces", "pictures", "missing", "guides"}`.
    """
    from PIL import Image

    game_dir, folder = Path(game_dir), Path(folder)
    rows = rows or {}
    base_path = Path(mesh_file) if mesh_file else me.mesh_path(game_dir, number)
    data = base_path.read_bytes()
    mesh = me.read_mesh(data)
    pictures = me.pictures(game_dir, number, sqlite_path, rows.get(TEXTURE_TABLE))
    texture_rows, added_rows = map_rows(sqlite_path, TEXTURE_TABLE, number, rows.get(TEXTURE_TABLE))
    node_rows, added_nodes = map_rows(sqlite_path, NODE_TABLE, number, rows.get(NODE_TABLE))
    folder.mkdir(parents=True, exist_ok=True)
    (folder / BASE).mkdir(exist_ok=True)
    (folder / TEXTURES).mkdir(exist_ok=True)
    base_name = f"map_{number:03d}_mesh.bin"
    (folder / BASE / base_name).write_bytes(data)

    # -- textures -------------------------------------------------------------
    source_folder = me.texture_folder(game_dir, number)
    picture_files = {k.lower(): Path(v) for k, v in (picture_files or {}).items()}
    written, missing = {}, []
    groups = {}
    for group, entry in sorted(pictures.items()):
        names = {"colour": list(entry.colour), "lighting": entry.lighting,
                 "lighting2": entry.lighting2, "added": (group, 0) in added_rows}
        groups[str(group)] = names
        for name in list(entry.colour) + [entry.lighting, entry.lighting2]:
            if not name or name in written:
                continue
            source = picture_files.get(name.lower(), source_folder / name)
            png = f"{TEXTURES}/{Path(name).stem}.png"
            try:
                with Image.open(source) as im:
                    im.convert("RGBA").save(folder / png)
            except (OSError, ValueError):
                missing.append(name)
                continue
            written[name] = {"png": png, "sha256": _sha256(folder / png)}

    # -- the model --------------------------------------------------------------
    objects, lines, used_materials = {}, [], set()
    lines += [f"# The Ivalice Chronicles Mod Studio: map {number:03d}'s enhanced look.",
              f"# Read {README} before editing. 28 units to a tile, 12 to a height step, y up.",
              f"mtllib {MATERIALS}"]
    v_count = vt_count = vn_count = 0
    by_object = {}
    for b, block in enumerate(mesh.blocks):
        for poly in block.polygons(b):
            if me.is_panel(poly.part):
                continue
            by_object.setdefault((b, block.parts[poly.corners[0]]), []).append(poly)
    for (b, slot), polys in sorted(by_object.items()):
        block = mesh.blocks[b]
        name = object_name(block.names[slot], b)
        lines.append(f"o {name}")
        vertices, welded, uvs, normals = [], {}, {}, {}
        face_lines = {}
        ids = []
        shapes = set()
        for poly in polys:
            material = f"group_{poly.group}" if poly.textured else UNTEXTURED
            used_materials.add(material)
            refs = []
            corners = [_world(block.positions[c]) for c in poly.corners]
            # A face on the same corners as another (the two sides of a sail,
            # 375 of them on 40-odd maps), or with a corner twice, gets its
            # own vertices: joined, a 3D program keeps one face of the two
            # and drops the other.
            shape = frozenset(corners)
            alone = shape in shapes or len(shape) < len(corners)
            shapes.add(shape)
            for c, p in zip(poly.corners, corners):
                if alone or p not in welded:
                    vertices.append(p)
                    if not alone:
                        welded[p] = v_count + len(vertices)
                    index = v_count + len(vertices)
                else:
                    index = welded[p]
                ref = str(index)
                if poly.textured:
                    u, v = block.uv(c)
                    t = (u, 1.0 - v)
                    if t not in uvs:
                        uvs[t] = vt_count + len(uvs) + 1
                    n = block.normals[c]
                    wn = (-n[0] / 4096, -n[1] / 4096, n[2] / 4096)
                    if wn not in normals:
                        normals[wn] = vn_count + len(normals) + 1
                    ref += f"/{uvs[t]}/{normals[wn]}"
                refs.append(ref)
            face_lines.setdefault(material, []).append((len(ids), "f " + " ".join(refs)))
            ids.append([b, poly.number])
        lines += [f"v {_num(p[0])} {_num(p[1])} {_num(p[2])}" for p in vertices]
        lines += [f"vt {_num(t[0])} {_num(t[1])}" for t in uvs]
        lines += [f"vn {_num(n[0])} {_num(n[1])} {_num(n[2])}" for n in normals]
        v_count += len(vertices)
        vt_count += len(uvs)
        vn_count += len(normals)
        order = []
        for material in sorted(face_lines):
            lines.append(f"usemtl {material}")
            for index, text in face_lines[material]:
                lines.append(text)
                order.append(ids[index])
        objects[name] = order
    (folder / MODEL).write_text("\n".join(lines) + "\n", encoding="utf-8")

    # -- materials --------------------------------------------------------------
    mtl = [f"# The Ivalice Chronicles Mod Studio: map {number:03d}'s texture groups.",
           "# map_Kd is the group's colour texture (its first frame, when it moves).",
           "# On water and a few others, how many times it repeats comes first (README.txt)."]
    for material in sorted(used_materials | {f"group_{g}" for g in groups} | {UNTEXTURED}):
        mtl.append(f"newmtl {material}")
        if material == UNTEXTURED:
            mtl += ["Kd 0 0 0", ""]
            continue
        group = int(material.split("_", 1)[1])
        entry = groups.get(str(group), {})
        colour = (entry.get("colour") or [None])[0]
        mtl.append("Kd 1 1 1")
        if colour in written:
            mtl.append(f"map_Kd {repeat_options(mesh.blocks[0].repeat(group))}{written[colour]['png']}")
        mtl.append("")
    (folder / MATERIALS).write_text("\n".join(mtl), encoding="utf-8")

    # -- the parts, as the game draws them -----------------------------------------
    parts = {}
    for b, block in enumerate(mesh.blocks):
        for slot, part in enumerate(block.names):
            if me.is_panel(part):
                continue
            row = node_rows.get((b, slot))
            parts[object_name(part, b)] = {
                "block": b, "slot": slot, "added": (b, slot) in added_nodes,
                "row": {k: row.get(k) for k in NODE_COLUMNS} if row else None}
    (folder / PARTS).write_text(parts_text(number, parts, by_object, mesh), encoding="utf-8")

    # -- what a new texture group copies -------------------------------------------
    template = new_group_template(texture_rows, groups)
    lighting = template.pop("lighting_texture", None)
    template["grey"] = (lighting_grey(folder / written[lighting]["png"])
                        if lighting in written else FLAT_LIGHTING)

    # -- the grid the look stands on -----------------------------------------------
    if tiles is None or grid_file is None:
        grid_file = enhanced_grid_file(game_dir, number)
        tiles = {}
        if grid_file:
            terrain = mc.read_mesh((game_dir / mc.MAP_FOLDER / grid_file).read_bytes()).terrain
            tiles = {(t.x, t.z, t.level): t for t in terrain.tiles} if terrain else {}
    grid = {"file": grid_file,
            "tiles": {f"{x},{z},{level}": [t.get("height"), t.get("slope"), t.get("slope_height")]
                      for (x, z, level), t in sorted(tiles.items()) if not t.is_blank}}

    metadata = {
        "kind": KIND_NAME, "version": VERSION, "map": number,
        "base": {"file": f"{BASE}/{base_name}", "sha256": hashlib.sha256(data).hexdigest(),
                 "from": "the mod's own mesh" if mesh_file else f"{me.MESH_FOLDER}/{base_name}"},
        "groups": groups,
        "pictures": written,
        "missing_pictures": missing,
        "objects": objects,
        "parts": parts,
        "new_group": template,
        "grid": grid,
    }
    (folder / METADATA).write_text(json.dumps(metadata, indent=1), encoding="utf-8")
    guides = draw_guides(folder, mesh, written, groups)
    free = [g for g in range(GROUPS) if str(g) not in groups and g not in
            {p.group for p in mesh.polygons() if p.textured}]
    (folder / README).write_text(readme(number, groups, by_object, mesh, free[0] if free else None),
                                 encoding="utf-8")
    return {"folder": folder, "objects": len(objects),
            "faces": sum(len(v) for v in objects.values()), "pictures": len(written),
            "missing": missing, "guides": len(guides)}


def repeat_options(repeat) -> str:
    """
    A map_Kd's options for a texture repeating `(u, v)` times: "" for once,
    else `-s U V 1 ` and, when V isn't whole, the `-o` that lines Blender's
    repeat up with the game's (see the module's notes).
    """
    u, v = (float(x) for x in repeat)
    if (u, v) == (1.0, 1.0):
        return ""
    out = f"-s {_num(u)} {_num(v)} 1 "
    shift = (-v) % 1.0
    if shift:
        out += f"-o 0 {_num(shift)} 0 "
    return out


def new_group_template(texture_rows: dict, groups: dict) -> dict:
    """
    What a new texture group's two rows copy: the lists of the map's first
    group that has a colour and a lighting, which say how many story
    lightings and random battles the map has (`map_enhanced.lightings`).
    Its lighting texture's name too, for `lighting_grey`.
    """
    for group in sorted(int(g) for g in groups):
        colour, light = texture_rows.get((group, 0)), texture_rows.get((group, 1))
        if not colour or not light or not _json_list(colour.get("Unknown8")) \
                or not _json_list(light.get("Unknown8")):
            continue
        shape = {}
        for kind, row in (("colour", colour), ("lighting", light)):
            shape[kind] = {"story": len(_json_list(row.get("Unknown8"))),
                           "random": len(_json_list(row.get("Unknown18"))),
                           "Unknown20": _json_list(row.get("Unknown20"))}
        shape["lighting_texture"] = groups[str(group)].get("lighting")
        return shape
    return {"colour": {"story": 1, "random": 0, "Unknown20": []},
            "lighting": {"story": 1, "random": 0, "Unknown20": []}}


def lighting_grey(path: Path) -> int:
    """
    How bright a map's lighting is where it lights anything: the middle of
    its lighting texture's lit pixels (the dark unused corners left out).
    A new group's flat lighting is this, so it sits lit as the map is.
    """
    from PIL import Image

    try:
        with Image.open(path) as im:
            grey = im.convert("L")
            grey.thumbnail((256, 256))
            values = sorted(v for v in grey.getdata() if v > 8)
    except (OSError, ValueError):
        return FLAT_LIGHTING
    return values[len(values) // 2] if values else FLAT_LIGHTING


def parts_text(number: int, parts: dict, by_object: dict, mesh) -> str:
    """`parts.txt`: each part of the model and how the game draws it."""
    used = {object_name(mesh.blocks[b].names[slot], b) for b, slot in by_object}
    lines = [f"# Map {number:03d}: how the game draws each part of the model (its RefinedBgMeshNode row).",
             "# One line a part: its object's name in map.obj, then how it is drawn, then, if you",
             "# like, the order see through parts are drawn in (higher first). A part you add",
             "# with no line here is drawn solid. README.txt says what each word means:",
             "#   " + ", ".join(PART_KINDS) + f", and {OWN_KIND} (the game's own row, kept).",
             ""]
    width = max([len(n) for n in parts] + [20]) + 2
    for name, info in parts.items():
        if name not in used:
            continue
        kind, order = kind_of(info["row"])
        default = PART_KINDS[kind][1] if kind in PART_KINDS else 0
        text = f"{name:<{width}}{kind}"
        if order != default:
            text += f" {order}"
        if kind == OWN_KIND:
            text += "    # " + " ".join(f"{k} {info['row'].get(k)}" for k in NODE_COLUMNS)
        elif info["row"] is None:
            text += "    # no row of its own: drawn the usual way"
        lines.append(text)
    return "\n".join(lines) + "\n"


def draw_guides(folder: Path, mesh, written: dict, groups: dict) -> list:
    """
    One PNG a texture group in `guides/`: its colour texture, darkened, with
    the edges of every face painted with it drawn on it in yellow - where on
    the texture each face is. A group whose texture repeats covers each
    face with it as many times over, so a face crosses several copies of
    the texture: it is drawn in each copy it crosses, wrapped onto the one
    texture, so every part of it shows where it is painted. The lighting
    texture has the same faces, drawn once across.
    """
    from PIL import Image, ImageDraw

    faces = {}
    for b, block in enumerate(mesh.blocks):
        for poly in block.polygons(b):
            if poly.textured and not me.is_panel(poly.part):
                faces.setdefault(poly.group, []).append((block, poly))
    out = []
    for group, entries in sorted(faces.items()):
        colour = (groups.get(str(group), {}).get("colour") or [None])[0]
        info = written.get(colour)
        if info is None:
            continue
        with Image.open(folder / info["png"]) as im:
            texture = im.convert("RGB")
        w, h = texture.size
        guide = Image.blend(Image.new("RGB", texture.size, (0, 0, 0)), texture, GUIDE_SHADE)
        draw = ImageDraw.Draw(guide)
        ru, rv = mesh.blocks[0].repeat(group)
        width = max(1, round(max(w, h) / 1024))
        for block, poly in entries:
            us = [block.uv(c)[0] * ru for c in poly.corners]
            vs = [block.uv(c)[1] * rv for c in poly.corners]
            first_u, first_v = math.floor(min(us)), math.floor(min(vs))
            for du in range(first_u, max(first_u + 1, math.ceil(max(us)))):
                for dv in range(first_v, max(first_v + 1, math.ceil(max(vs)))):
                    points = [((u - du) * w, (v - dv) * h) for u, v in zip(us, vs)]
                    draw.line(points + points[:1], fill=GUIDE_LINE, width=width)
        (folder / GUIDES).mkdir(exist_ok=True)
        path = folder / GUIDES / f"group_{group}.png"
        guide.save(path, compress_level=6)
        out.append(path)
    return out


def readme(number: int, groups: dict, by_object: dict, mesh, free: Optional[int]) -> str:
    """The package's README.txt: how to edit it, for people and for programs."""
    listed = ", ".join(f"group_{g}" for g in sorted(groups, key=int)) or "none"
    owners = {}
    for (b, slot), polys in by_object.items():
        for poly in polys:
            if poly.textured:
                owners.setdefault(poly.group, set()).add(object_name(mesh.blocks[b].names[slot], b))
    table = []
    for g in sorted(groups, key=int):
        entry = groups[g]
        colour = (entry.get("colour") or ["(none)"])[0]
        frames = len(entry.get("colour") or [])
        table.append(f"  group_{g:<4} {', '.join(sorted(owners.get(int(g), ()))) or '(no faces)'}")
        table.append(f"              colour {Path(colour).stem}"
                     + (f", {frames} frames" if frames > 1 else ""))
        if entry.get("lighting"):
            table.append(f"              lighting {Path(entry['lighting']).stem}")
        repeat = mesh.blocks[0].repeat(int(g))
        if repeat != (1.0, 1.0):
            table.append(f"              repeats {repeat[0]:g} by {repeat[1]:g}")
    groups_table = "\n".join(table) or "  (none)"
    next_group = f"group_{free}" if free is not None else "none left (a map has 32)"
    return f"""Map {number:03d}: its enhanced look, for editing
{'=' * 40}

Made by The Ivalice Chronicles Mod Studio from the game's own files. Change
the model and the textures, then load this folder back in the Map Editor
(Load edited), or build it into a mod from a command line (at the end).

What is here

  map.obj      The model. Each object is one part of the map (GT_0_map ...).
               An object named NAME@N is moving part N (a door, a windmill).
  map.mtl      One material per texture group: {listed}.
               And "untextured", which the game draws black.
  parts.txt    How the game draws each part. Add a line for a part you add.
  textures/    Every texture the groups use, as PNG.
  guides/      Each group's texture, darkened, with its faces drawn on it in
               yellow: where on the texture each face is painted.
  map.json     What the model file can't hold. Don't edit it.
  base/        The game's mesh this was made from. Don't edit it.
  built/       What was last built from this folder.

The model

  Units: 28 to a tile, 12 to a height step, y up (Blender turns y up into
  its z up on import and back on export). The model's x runs the other way
  from the game's: tile x, z covers z from 28z to 28z + 28, and x from
  minus 28x to minus 28x minus 28, as the Map Editor draws it.

  * Every face needs a material: group_N (it then needs UVs), or untextured.
  * Faces have 3 or 4 corners. A face with more is split into triangles.
  * A new object name is a new part (31 letters at most, 32 parts to a
    moving part). New moving parts (NAME@N with a new N) can't be added.
  * Faces that are the same as before keep everything the game knows about
    them. New faces are drawn from every camera corner and belong to no tile.
  * The tiles' move and target highlights are not in the model: they follow
    the battle grid (seen in the game: raised tiles carry their highlights
    up with them).

Units stand on the battle grid, not on the model

  The grid is the map's tiles, each with a height and a slope, which you
  change tile by tile in the Map Editor. When a model you load back with
  Load edited raises or lowers the ground, the Map Editor offers to move
  the tiles under it to match: each tile's corners go up or down as far as
  the model's ground did there. Check them after: a tile is whole steps of
  12 units high, and one slope from corner to corner at most.

Textures, and where a face is on one

  Each texture group has a colour texture and a lighting texture, painted
  onto its faces by their UVs: a face's corners each say where on the
  texture they are. These are the groups, the parts that use them, their
  textures (in textures/, as PNG) and how often a texture repeats:

{groups_table}

  * Where a face is on its texture: open guides/group_N.png, which draws
    every face of group N on its texture. In Blender, the UV Editing
    workspace shows the faces you pick on their texture. In the Map Editor,
    a right click on the map opens the texture under the pointer.
  * The game draws each group's colour texture times its lighting texture,
    times 2. A lighting texture of mid grey (128, 128, 128) leaves the
    colour as it is; lighter brightens, darker shades. The lighting is
    painted for the faces as they are (the light and shadow are in it), and
    shares their UVs, but isn't repeated.
  * Change a texture by saving over its PNG here, at any size. Or point the
    material's map_Kd at another file: that replaces the group's colour.
  * A texture with frames (..._color_0.png, ..._color_1.png ...) plays them
    in turn, at the speed the game's anim file gives that group. Keep them
    the same size.
  * A material whose texture repeats across its faces (water's do) says how
    often in its map_Kd line, before the file:

      map_Kd -s 7.5 7.5 1 -o 0 0.5 0 textures/NAME.png

    is 7.5 times across and 7.5 down. Change the two numbers after s to
    change it in the game. The ones after o, there when a repeat isn't
    whole, only line it up in Blender: leave them.
  * Some maps have more than one lighting (a story battle's, the random
    battles'): those textures are in the game folder, and change on the
    Textures page. This folder has the usual one.

What changing the model does to the textures

  * Moving, raising or reshaping faces doesn't move them on the texture:
    their UVs stay, so the texture stretches with them. Change the UVs, or
    paint the texture again, where it looks wrong. The guides show the
    faces where they were when this folder was saved: save for editing
    again for guides of the model as it is now.
  * A new face needs UVs, on some part of a texture: one its group's
    faces don't use (the guides show the free space), or a new group.
  * Moving a face's UVs onto another part of the texture also moves it
    onto another part of the lighting, which was painted for something
    else there. Paint the lighting there too, or give the face a new group.

A new texture group (for a new map, or a new texture)

  * Add a material named for a number no group uses ({next_group} is the
    next; the last is group_31), with its colour texture:

      newmtl {f'group_{free}' if free is not None else 'group_N'}
      Kd 1 1 1
      map_Kd textures/lava.png

    In Blender: a new material of that name, with an Image Texture of a PNG
    you put in textures/, in the Base Color. Give it faces, with UVs.
  * It goes into your mod as gt_N_map{number:03d}_lava_color.tga, named for
    its PNG, with a lighting texture: lava_lighting.png beside lava.png if
    there is one, else a flat one as bright as this map's own lighting.
  * The game finds a group's textures by its rows in the RefinedBgTexture
    table: the Map Editor adds them to your mod when you Load edited, and
    puts them in when you export it. One texture, still (no frames), the
    same under every lighting the map has.

Parts, and how the game draws them

  The game draws each part as its row in the RefinedBgMeshNode table says,
  or the usual way when it has none (many of its own parts have none).
  parts.txt lists the parts with a word for how each is drawn:

    solid      every view, as the ground, walls and water are
    edge       every view, as the borders round a map and its watersides
               are (how it differs from solid isn't known)
    overlay    blended over what is behind it, without hiding it: shadows
    side       the side views only: trees, flames, a fence
    top        the top down view only, lying flat: icons of trees, grass
    upright    the top down view only, standing: icons of fires, candles
    own        a row none of those words fits: the game's own, kept

  A number after the word is the order see through parts are drawn in,
  higher first (the icons are drawn at minus 1). The top down view is the
  remaster's tactical camera: a tree is drawn from the side as a side part,
  and from above as its icon, a top part, so a new tree needs both.

  * A new part (a new object) is drawn solid, with no row, as the game's
    own parts with none are. Give it a line here to draw it another way:
    it then gets a row. Change an existing part's word to draw it another
    way too. The Map Editor adds the rows when you Load edited.

Not tried in the game yet

  New texture groups, and parts drawn other than solid: their rows are
  made as the game's own are, but whether the game picks up rows a mod
  adds to these tables hasn't been tried. A first test: one new group on
  one map, in a battle.

The classic look

  Unchanged. Most mods leave it as it is.

From a command line (for scripts, and AI coworkers)

  From the folder The Ivalice Chronicles Mod Studio is in:

    python -m mod_studio.map_package check THIS_FOLDER
    python -m mod_studio.map_package build THIS_FOLDER --mod MOD_FOLDER
    python -m mod_studio.map_package preview THIS_FOLDER --game GAME_FOLDER --out preview.png

  check says what is wrong with the folder, if anything. build writes the
  mesh and the changed and new textures into MOD_FOLDER
  (FFTIVC/data/enhanced/bg/), and the table rows for new groups and parts
  into built/tables.json: putting those into a mod's tables needs Mod
  Studio (Load edited in the Map Editor, then Export Mod). preview draws
  the map from the four camera corners into one image.
"""


# =============================================================================
# Reading a package
# =============================================================================

@dataclass
class Face:
    corners: list                   # (position, uv or None, normal or None), world space
    material: str
    line: int


@dataclass
class Package:
    folder: Path
    metadata: dict
    base: me.EnhancedMesh
    base_data: bytes
    objects: dict                   # name: [Face], in file order
    object_order: list
    materials: dict                 # material name: map_Kd path or None
    notes: list = field(default_factory=list)
    repeats: dict = field(default_factory=dict)     # material name: its map_Kd's -s (u, v)
    parts: dict = field(default_factory=dict)       # object name: (kind, order or None, line)


def _index(token: str, count: int, what: str, line: int) -> int:
    i = int(token)
    i = i - 1 if i > 0 else count + i
    if not 0 <= i < count:
        raise PackageError(f"{MODEL} line {line}: a face refers to {what} {token}, and there are {count}")
    return i


def read_obj(path: Path) -> tuple:
    """`(objects {name: [Face]}, object order, material library name)` from an OBJ file."""
    vs, vts, vns = [], [], []
    objects, order = {}, []
    current, material, library = None, None, None
    for number, raw in enumerate(Path(path).read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        head, _, rest = line.partition(" ")
        rest = rest.strip()
        try:
            if head == "v":
                vs.append(tuple(float(x) for x in rest.split()[:3]))
            elif head == "vt":
                values = [float(x) for x in rest.split()[:2]]
                vts.append((values[0], values[1] if len(values) > 1 else 0.0))
            elif head == "vn":
                vns.append(tuple(float(x) for x in rest.split()[:3]))
            elif head in ("o", "g"):
                if head == "g" and current is not None and rest in ("", "default"):
                    continue
                current = rest or "unnamed"
                if current not in objects:
                    objects[current] = []
                    order.append(current)
            elif head == "usemtl":
                material = rest
            elif head == "mtllib":
                library = rest
            elif head == "f":
                if current is None:
                    current = "unnamed"
                    objects[current], order = [], [current]
                corners = []
                for token in rest.split():
                    parts = token.split("/")
                    p = vs[_index(parts[0], len(vs), "position", number)]
                    t = (vts[_index(parts[1], len(vts), "UV", number)]
                         if len(parts) > 1 and parts[1] else None)
                    n = (vns[_index(parts[2], len(vns), "normal", number)]
                         if len(parts) > 2 and parts[2] else None)
                    corners.append((p, t, n))
                objects[current].append(Face(corners, material or "", number))
        except (ValueError, IndexError) as exc:
            if isinstance(exc, PackageError):
                raise
            raise PackageError(f"{MODEL} line {number} can't be read: {raw.strip()[:60]}") from exc
    return objects, order, library


def _map_lines(path: Path):
    """`(material, the words after map_Kd)` for each map_Kd line of an MTL file."""
    current = None
    if not Path(path).is_file():
        return
    for raw in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.split("#", 1)[0].strip()
        head, _, rest = line.partition(" ")
        if head == "newmtl":
            current = rest.strip()
            yield current, None
        elif head == "map_Kd" and current is not None:
            yield current, rest.strip()


def read_materials(path: Path) -> dict:
    """`{material: its map_Kd, or None}` from an MTL file."""
    out = {}
    for material, text in _map_lines(path):
        out[material] = _map_options(text)[1] if text is not None else None
    return out


def read_repeats(path: Path) -> dict:
    """`{material: (u, v)}`, for the materials whose map_Kd says how often it repeats (-s)."""
    out = {}
    for material, text in _map_lines(path):
        values = _map_options(text)[0].get("-s") if text is not None else None
        if values:
            # A value left out is 1, as the format has it.
            out[material] = (values[0], values[1] if len(values) > 1 else 1.0)
    return out


#: map_Kd's options and how many values each takes; the file comes after them.
_MAP_OPTIONS = {"-blendu": 1, "-blendv": 1, "-bm": 1, "-boost": 1, "-cc": 1, "-clamp": 1,
                "-imfchan": 1, "-mm": 2, "-o": 3, "-s": 3, "-t": 3, "-texres": 1}
_OPTION_VALUE = re.compile(r"[-+]?(\d+\.?\d*|\.\d+)(e[-+]?\d+)?|on|off", re.I)


def _map_options(text: str) -> tuple:
    """
    `({option: [its numbers]}, file)` from a map_Kd's words: the options
    first, then the file they are for (a path may have spaces in it).
    """
    words = text.split(" ")
    options, i = {}, 0
    while i < len(words) and words[i].lower() in _MAP_OPTIONS:
        name, count = words[i].lower(), _MAP_OPTIONS[words[i].lower()]
        i += 1
        # Options with up to three values take as many as are there.
        values = []
        while len(values) < count and i < len(words) and _OPTION_VALUE.fullmatch(words[i]):
            values.append(words[i])
            i += 1
        try:
            options[name] = [float(v) for v in values]
        except ValueError:
            options[name] = []
    rest = " ".join(words[i:]).strip()
    return options, rest or None


def read_parts(path: Path) -> tuple:
    """
    `({object name: (kind, order or None, line)}, problems)` from a
    `parts.txt`: a part's name, a word from `PART_KINDS` or `OWN_KIND`, and
    an order if it has one. Empty when there is no such file.
    """
    out, problems = {}, []
    if not Path(path).is_file():
        return out, problems
    words = ", ".join(list(PART_KINDS) + [OWN_KIND])
    for number, raw in enumerate(Path(path).read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        text = raw.split("#", 1)[0].split()
        if not text:
            continue
        name, rest = text[0], text[1:]
        kind = rest[0].lower() if rest else DEFAULT_KIND
        if kind not in PART_KINDS and kind != OWN_KIND:
            problems.append(f"{PARTS} line {number}: {name} is {rest[0]!r}, and a part is one of {words}")
            continue
        order = None
        if len(rest) > 1:
            try:
                order = int(rest[1])
            except ValueError:
                problems.append(f"{PARTS} line {number}: {name}'s order is {rest[1]!r}, and an "
                                f"order is a whole number (the icons' is -1)")
                continue
        out[name] = (kind, order, number)
    return out, problems


def read_package(folder) -> Package:
    folder = Path(folder)
    try:
        metadata = json.loads((folder / METADATA).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PackageError(f"{folder} has no {METADATA} this can read: is it a package "
                           f"the Map Editor saved?") from exc
    if metadata.get("kind") != KIND_NAME:
        raise PackageError(f"{folder / METADATA} isn't a map package's")
    if metadata.get("version", 0) > VERSION:
        raise PackageError("this package was made by a newer Mod Studio")
    base_path = folder / metadata["base"]["file"]
    try:
        base_data = base_path.read_bytes()
    except OSError as exc:
        raise PackageError(f"the package's base mesh is missing: {base_path}") from exc
    if hashlib.sha256(base_data).hexdigest() != metadata["base"]["sha256"]:
        raise PackageError(f"the package's base mesh has changed since it was saved: {base_path}")
    if not (folder / MODEL).is_file():
        raise PackageError(f"the package has no {MODEL}")
    objects, order, library = read_obj(folder / MODEL)
    materials = read_materials(folder / (library or MATERIALS))
    parts, problems = read_parts(folder / PARTS)
    if problems:
        raise PackageError("\n".join(problems))
    return Package(folder, metadata, me.read_mesh(base_data), base_data, objects, order, materials,
                   repeats=read_repeats(folder / (library or MATERIALS)), parts=parts)


# =============================================================================
# Building
# =============================================================================

@dataclass
class Built:
    """What a package makes: the mesh file, the textures it changes or adds, and its table rows."""
    number: int
    mesh: bytes
    changed: bool                   # False: the mesh is the base's, byte for byte
    pictures: dict                  # {texture name: image file}, the changed and new ones
    notes: list                     # what was done, for the person
    counts: dict                    # faces kept, moved, new, gone
    #: `{table: {(map, ...): {column: value}}}`: the `RefinedBgTexture` and
    #: `RefinedBgMeshNode` rows this map's look adds (marked `ADDED_ROW`) or
    #: changes, in `state.unmodelled_table_edits`' shape.
    table_rows: dict = field(default_factory=dict)
    #: `{group: [texture names]}`: the texture groups the mod adds that the
    #: model uses, and their textures.
    added_groups: dict = field(default_factory=dict)


def _parse_object(name: str, known: dict) -> tuple:
    """`(part name, block)` for an object: a known one by name, else NAME or NAME@N."""
    if name in known:
        return known[name]
    # 3D programs add to names: "GT_0_map.001", "GT_0_map_GT_0_map".
    for candidate in sorted(known, key=len, reverse=True):
        if name.startswith(candidate) and re.fullmatch(r"(\.\d+|_.*)?", name[len(candidate):]):
            return known[candidate]
    m = re.fullmatch(r"(.+?)(?:@(\d+))?(?:\.\d+)?", name)
    return m.group(1), int(m.group(2) or 0)


def _material_group(material: str) -> Optional[int]:
    """The texture group a material names (`group_3`, `group_3.001`), None for untextured, else raises."""
    base = re.sub(r"\.\d+$", "", material or "")
    if base == UNTEXTURED:
        return None
    m = re.fullmatch(r"group_(\d+)", base)
    if not m:
        raise KeyError(material)
    return int(m.group(1))


def _file(p) -> tuple:
    return (-p[0], -p[1], p[2])


def _snap(new, old, slack) -> tuple:
    """`new`, with each value within `slack` of `old`'s the old one exactly."""
    return tuple(o if abs(n - o) <= slack else n for n, o in zip(new, old))


def _face_normal(points) -> tuple:
    """A face's normal from its corners (Newell's), as the file's int16."""
    nx = ny = nz = 0.0
    for i, (x0, y0, z0) in enumerate(points):
        x1, y1, z1 = points[(i + 1) % len(points)]
        nx += (y0 - y1) * (z0 + z1)
        ny += (z0 - z1) * (x0 + x1)
        nz += (x0 - x1) * (y0 + y1)
    length = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
    return tuple(int(round(max(-1.0, min(1.0, c / length)) * 4096)) for c in (nx, ny, nz))


def _same_direction(a, b) -> bool:
    """
    Whether two normals point the same way to within a degree. A 3D program
    rounds them, and the game's own are not all of one length: (0, 0, -4095)
    is as much straight down as (0, 0, -4096). A normal of (0, 0, 0) points
    nowhere, and says nothing: the game has them on faces with no area, and
    Blender writes them where it can't work one out (4 corners of map 004).
    """
    la = math.sqrt(sum(x * x for x in a))
    lb = math.sqrt(sum(x * x for x in b))
    if not la or not lb:
        return True
    return sum(x * y for x, y in zip(a, b)) / (la * lb) > math.cos(math.radians(1.0))


def _int16_normal(world_normal) -> tuple:
    x, y, z = world_normal
    length = math.sqrt(x * x + y * y + z * z) or 1.0
    return tuple(int(round(max(-1.0, min(1.0, c / length)) * 4096)) for c in (-x, -y, z))


def _new_words(kind: str, block: int, render: int, template: Optional[list]) -> list:
    """A new polygon's corner words: the game's markers for its kind, no tile, no source."""
    if template is not None:
        words = [bytearray(w) for w in template]
    else:
        fill = b"\xff\xff" if block == 0 else b"\x00\x00"
        words = []
        for pattern in MARKERS[kind]:
            word = bytearray(4)
            word[2:4] = fill
            if pattern[0] == "b":
                word[0:2] = b"\xbb\xbb" if block == 0 else b"\x00\x00"
            words.append(word)
    words[0][0:2] = me.UNBOUND
    words[1][2:4] = b"\xff\xff"
    words[-1][0:2] = struct.pack("<H", render)
    return [bytes(w) for w in words]


def texture_label(path) -> str:
    """
    What a new group's texture files are named for: its PNG's name, in the
    game's way (small letters and digits, joined by _), without a game
    name's `gt_N_mapNNN_` and `_color` around it. "new" for nothing left.
    """
    stem = Path(str(path).replace("\\", "/")).stem.lower()
    stem = re.sub(r"^gt_\d+_map\d{3}_", "", stem)
    stem = re.sub(r"_(color|lighting2?)(_[a-z])?(_\d+)?$", "", stem)
    words = re.findall(r"[a-z0-9]+", stem)
    return "_".join(words)[:24].strip("_") or "new"


def build(folder, game_dir=None) -> Built:
    """
    The mesh, textures and table rows a package makes (see the module's
    notes). Raises PackageError, with every problem found, for one that
    can't be built.
    """
    package = read_package(folder)
    base, meta = package.base, package.metadata
    number = int(meta["map"])
    base_blocks = me.blocks_of(base)
    base_polys = {}
    by_part = {}
    for b, block in enumerate(base.blocks):
        for poly in block.polygons(b):
            base_polys[(b, poly.number)] = poly
            by_part.setdefault((b, block.parts[poly.corners[0]]), []).append(poly)
    known = {}
    for b, block in enumerate(base.blocks):
        for slot, name in enumerate(block.names):
            known[object_name(name, b)] = (name, b)
    groups = {int(g) for g in meta["groups"]}
    # The groups the faces use that the map hasn't: new ones, each a material
    # naming its colour texture.
    new_groups = {}
    problems, notes = [], []
    for material in sorted({f.material for faces in package.objects.values() for f in faces}):
        try:
            group = _material_group(material)
        except KeyError:
            continue
        if group is None or group in groups:
            continue
        if not 0 <= group < GROUPS:
            problems.append(f"{material}: a map has room for {GROUPS} texture groups, group_0 to "
                            f"group_{GROUPS - 1}")
            continue
        target = package.materials.get(material)
        if not target:
            problems.append(f"{material} is a new texture group, and has no texture: give it one in "
                            f"{MATERIALS} (map_Kd textures/NAME.png)")
            continue
        path = Path(target.replace("\\", "/"))
        path = path if path.is_absolute() else package.folder / path
        if not path.is_file():
            problems.append(f"{MATERIALS}: {material}'s map_Kd is {target}, which isn't there")
            continue
        if group in new_groups and new_groups[group] != path:
            problems.append(f"{material} and another group_{group} name two textures: one group "
                            f"has one colour texture")
            continue
        new_groups[group] = path
    counts = Counter()

    # Each block's names grow with new parts; its polygons are rebuilt from
    # the OBJ, the highlight panels kept from the base as they are. Its 32
    # pairs are the texture groups' repeats, which the materials can change.
    names = [list(block.names) for block in base.blocks]
    slots = [list(block.slot_values) for block in base.blocks]
    for material, repeat in sorted(package.repeats.items()):
        try:
            group = _material_group(material)
        except KeyError:
            continue
        if group is None or (group not in groups and group not in new_groups) or not 0 <= group < GROUPS:
            continue
        if not all(math.isfinite(x) and x > 0 for x in repeat):
            problems.append(f"{MATERIALS}: {material}'s map_Kd repeats its texture {repeat[0]:g} by "
                            f"{repeat[1]:g} times, and each has to be more than 0")
            continue
        if tuple(base.blocks[0].repeat(group)) != tuple(repeat):
            for b in range(len(slots)):
                slots[b][group] = tuple(repeat)
            notes.append(f"{material}'s texture repeats {repeat[0]:g} by {repeat[1]:g} times now")
    new_polys = [[p for p, poly in zip(base_blocks[b].polygons, block.polygons(b)) if me.is_panel(poly.part)]
                 for b, block in enumerate(base.blocks)]
    templates = {}
    for b, block in enumerate(base.blocks):
        for poly in block.polygons(b):
            if not me.is_panel(poly.part):
                templates.setdefault((b, poly.kind), [block.words[c] for c in poly.corners])
    exact = True
    seen_ids = set()
    for name in package.object_order:
        faces = package.objects[name]
        if not faces:
            continue
        part, b = _parse_object(name, known)
        if not 0 <= b < len(base.blocks):
            problems.append(f"object {name}: moving part {b} isn't in this map (it has "
                            f"{len(base.blocks) - 1}); new moving parts can't be added")
            continue
        if len(part.encode("ascii", "replace")) > 31 or not part.isascii():
            problems.append(f"object {name}: a part's name is 31 plain letters at most")
            continue
        if part not in names[b]:
            if len(names[b]) >= 32:
                problems.append(f"object {name}: a map has room for 32 parts, and this one has them")
                continue
            names[b].append(part)
            exact = False
        slot = names[b].index(part)
        listed = meta["objects"].get(object_name(part, b)) or []
        originals = [base_polys.get((bb, n)) for bb, n in listed]
        try:
            materials = [_material_group(f.material) for f in faces]
        except KeyError as exc:
            problems.append(f"object {name}, line {next(f.line for f in faces if f.material == exc.args[0])}: "
                            f"the material {exc.args[0]!r} isn't one of this map's (group_N, or "
                            f"{UNTEXTURED})")
            continue
        same = (len(faces) == len(originals) and all(
            o is not None and len(f.corners) == len(o.corners)
            and m == (o.group if o.textured else None)
            for f, o, m in zip(faces, originals, materials)))
        if not same:
            exact = False
        # The part's old polygons, by where their corners are, for faces
        # that are old polygons in a changed part.
        by_corners = {}
        if not same:
            for poly in by_part.get((b, base.blocks[b].names.index(part)), []) \
                    if part in base.blocks[b].names else []:
                if me.is_panel(poly.part):
                    continue
                key = (poly.group if poly.textured else None,
                       tuple(sorted(tuple(round(v, 2) for v in base.blocks[b].positions[c])
                                    for c in poly.corners)))
                by_corners.setdefault(key, []).append(poly)
        renders = Counter(p.render & ~HIDE_BITS for p in by_part.get(
            (b, base.blocks[b].names.index(part)), []) if not me.is_panel(p.part)) \
            if part in base.blocks[b].names else Counter()
        for index, (face, group) in enumerate(zip(faces, materials)):
            if len(face.corners) < 3:
                problems.append(f"object {name}, line {face.line}: a face needs 3 corners")
                continue
            if group is not None and group not in groups and group not in new_groups:
                continue                                  # said above, once for the material
            if group is not None and any(t is None for _p, t, _n in face.corners):
                problems.append(f"object {name}, line {face.line}: a face with a texture "
                                f"(group_{group}) needs a UV at every corner")
                continue
            original = originals[index] if same else None
            if original is None and not same:
                key = (group, tuple(sorted(tuple(round(v, 2) for v in _file(p)) for p, _t, _n in face.corners)))
                candidates = [p for p in by_corners.get(key, []) if (b, p.number) not in seen_ids]
                if candidates and len(candidates[0].corners) == len(face.corners):
                    original = candidates[0]
            pieces = ([face.corners] if len(face.corners) <= 4 else
                      [[face.corners[0], face.corners[i], face.corners[i + 1]]
                       for i in range(1, len(face.corners) - 1)])
            if len(pieces) > 1:
                notes.append(f"object {name}, line {face.line}: a face with {len(face.corners)} corners "
                             f"was split into {len(pieces)} triangles")
                original = None
            for piece in pieces:
                kind = ("tq" if len(piece) == 4 else "tt") if group is not None else \
                       ("uq" if len(piece) == 4 else "ut")
                block = base.blocks[b]
                if original is not None:
                    seen_ids.add((b, original.number))
                    corners = []
                    moved = False
                    for (p, t, n), c in zip(piece, original.corners):
                        old = me.CornerData(tuple(block.positions[c]), bytes(block.words[c]))
                        new_position = _snap(_file(p), old.position, POSITION_SLACK)
                        moved |= new_position != old.position
                        old.position = new_position
                        if original.textured:
                            _g, u, v = block.pool[block.uv_index[c]]
                            old.uv = _snap((t[0], 1.0 - t[1]), (u, v), UV_SLACK)
                            moved |= old.uv != (u, v)
                            old.extra = bytes(block.pool_extra[block.uv_index[c]])
                            normal = tuple(block.normals[c])
                            if n is not None and not _same_direction(_int16_normal(n), normal):
                                normal = _int16_normal(n)
                                moved = True
                            old.normal = normal
                        corners.append(old)
                    counts["moved" if moved else "kept"] += 1
                    exact &= not moved
                    new_polys[b].append(me.PolygonData(original.kind, slot, corners,
                                                       original.group if original.textured else 0))
                    continue
                exact = False
                counts["new"] += 1
                render = (renders.most_common(1)[0][0] if renders else NEW_RENDER)
                words = _new_words(kind, b, render, templates.get((b, kind)))
                points = [_file(p) for p, _t, _n in piece]
                face_normal = _face_normal(points)
                corners = []
                for (p, t, n), word in zip(piece, words):
                    corner = me.CornerData(_file(p), word)
                    if group is not None:
                        corner.uv = (t[0], 1.0 - t[1])
                        given = _int16_normal(n) if n is not None else (0, 0, 0)
                        corner.normal = given if any(given) else face_normal
                    corners.append(corner)
                new_polys[b].append(me.PolygonData(kind, slot, corners, group or 0))
    kept_ids = {(b, p.number) for b, block in enumerate(base.blocks) for p in block.polygons(b)
                if me.is_panel(p.part)}
    gone = [key for key, poly in base_polys.items()
            if key not in seen_ids and key not in kept_ids]
    if gone:
        counts["gone"] = len(gone)
        exact = False
        notes.append(f"{len(gone)} of the map's faces are no longer in the model")
    if problems:
        raise PackageError("\n".join(problems))
    repeats_kept = all(tuple(slots[b][g]) == tuple(block.slot_values[g])
                       for b, block in enumerate(base.blocks) for g in range(len(block.slot_values)))
    if exact and repeats_kept and len(seen_ids) == len(base_polys) - len(kept_ids):
        mesh_bytes, changed = package.base_data, False
    else:
        blocks = [me.BlockData(names[b], slots[b], new_polys[b]) for b in range(len(base.blocks))]
        mesh_bytes, changed = me.write_mesh(me.assemble(number, blocks)), True
    pictures = changed_pictures(package, notes, problems)
    used = {p.group for polys in new_polys for p in polys if p.kind in ("tq", "tt")}
    table_rows, added_groups = group_rows(package, new_groups, used, pictures, notes)
    node_rows = part_rows(package, names, problems, notes)
    if problems:
        raise PackageError("\n".join(problems))
    if node_rows:
        table_rows[NODE_TABLE] = node_rows
    return Built(number, mesh_bytes, changed, pictures, notes, dict(counts), table_rows, added_groups)


def changed_pictures(package: Package, notes: list, problems: list) -> dict:
    """`{texture name: image file}` for the textures the package changes."""
    folder, meta = package.folder, package.metadata
    out = {}
    for name, info in meta["pictures"].items():
        png = folder / info["png"]
        if not png.is_file():
            problems.append(f"{info['png']} is missing: put it back, or the texture it was")
            continue
        if _sha256(png) != info["sha256"]:
            out[name] = png
    for material, target in package.materials.items():
        try:
            group = _material_group(material)
        except KeyError:
            continue
        entry = meta["groups"].get(str(group)) if group is not None else None
        if not entry or not entry.get("colour") or not target:
            continue
        colour = entry["colour"][0]
        exported = meta["pictures"].get(colour, {}).get("png")
        path = Path(target.replace("\\", "/"))
        path = path if path.is_absolute() else folder / path
        if exported and path.resolve() == (folder / exported).resolve():
            continue
        if not path.is_file():
            problems.append(f"{MATERIALS}: {material}'s map_Kd is {target}, which isn't there")
            continue
        out[colour] = path
        notes.append(f"{material}'s colour is {target} now")
    return out


def _texture_row(name: str, shape: dict) -> dict:
    """A new group's `RefinedBgTexture` row, `name` in every entry the map's rows have."""
    story = max(1, int(shape.get("story") or 1))
    random = int(shape.get("random") or 0)
    return {"DLCFlags": 0, "Unknown8": _list_text([name] * story), "Unknown10": _list_text([1] * story),
            "Unknown18": _list_text([name] * random), "Unknown20": _list_text(list(shape.get("Unknown20") or [])),
            ADDED_ROW: True}


def group_rows(package: Package, new_groups: dict, used: set, pictures: dict, notes: list) -> tuple:
    """
    `({RefinedBgTexture: rows}, {group: texture names})` for the texture
    groups the mod adds that the model uses: the new ones (`new_groups`,
    `{group: colour image}`), whose textures join `pictures`, and those a
    package made from the mod's own look says are its own.
    """
    from PIL import Image

    folder, meta, number = package.folder, package.metadata, int(package.metadata["map"])
    template = meta.get("new_group") or {}
    rows, added = {}, {}
    for group, entry in sorted(meta["groups"].items(), key=lambda kv: int(kv[0])):
        if not entry.get("added") or int(group) not in used:
            continue
        colour, light = (entry.get("colour") or [None])[0], entry.get("lighting")
        if not colour:
            continue
        rows[(number, int(group), 0)] = _texture_row(Path(colour).stem, template.get("colour") or {})
        if light:
            rows[(number, int(group), 1)] = _texture_row(Path(light).stem, template.get("lighting") or {})
        added[int(group)] = [name for name in (colour, light) if name]
    for group, source in sorted(new_groups.items()):
        if group not in used:
            continue
        label = texture_label(source)
        colour = f"gt_{group}_map{number:03d}_{label}_color.tga"
        light = f"gt_{group}_map{number:03d}_{label}_lighting.tga"
        given = source.with_name(f"{source.stem}_lighting{source.suffix}")
        if given.is_file():
            light_source = given
            said = f"its lighting {given.name}"
        else:
            grey = int((template.get("grey") or FLAT_LIGHTING))
            light_source = folder / BUILT / TEXTURES / f"{Path(light).stem}.png"
            light_source.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (8, 8), (grey, grey, grey)).save(light_source)
            said = "a flat lighting"
        pictures[colour] = source
        pictures[light] = light_source
        rows[(number, group, 0)] = _texture_row(Path(colour).stem, template.get("colour") or {})
        rows[(number, group, 1)] = _texture_row(Path(light).stem, template.get("lighting") or {})
        added[group] = [colour, light]
        notes.append(f"group_{group} is a new texture group: {colour}, with {said}")
    return ({TEXTURE_TABLE: rows} if rows else {}), added


def part_rows(package: Package, names: list, problems: list, notes: list) -> dict:
    """
    The `RefinedBgMeshNode` rows for the model's parts: one the mod adds for
    each new part drawn other than solid (a solid one needs none, as the
    game's own parts with no row show: `DEFAULT_KIND`), and for each a
    package made from the mod's look says is its own; and a changed row for
    each of the game's parts `parts.txt` draws another way.
    """
    meta, number = package.metadata, int(package.metadata["map"])
    recorded = meta.get("parts") or {}
    listed = dict(package.parts)
    plain = kind_row(DEFAULT_KIND)
    rows = {}
    for b, block_names in enumerate(names):
        in_base = package.base.blocks[b].names if b < len(package.base.blocks) else []
        for slot, part in enumerate(block_names):
            if me.is_panel(part):
                continue
            name = object_name(part, b)
            kind, order, _line = listed.pop(name, (None, None, None))
            info = recorded.get(name)
            if info is None and part in in_base:
                info = {"row": None, "added": False}     # a package from before parts.txt
            old = {k: info["row"].get(k) for k in NODE_COLUMNS} if info and info.get("row") else None
            chosen = kind_row(kind, order) if kind in PART_KINDS else None
            if info is None or info.get("added"):
                # The mod's own part: a row only to be drawn otherwise.
                row = chosen if chosen is not None else old
                if info is None:
                    drawn = kind_of(row)[0] if row else DEFAULT_KIND
                    notes.append(f"{name} is a new part" + (f", drawn {drawn}" if row and row != plain else ""))
                if row is None or row == plain:
                    continue
                rows[(number, b, slot)] = dict(row, DLCFlags=0, **{ADDED_ROW: True})
                continue
            if chosen is None or chosen == (old or plain):
                continue                                 # drawn as it was
            rows[(number, b, slot)] = (dict(chosen, DLCFlags=0, **{ADDED_ROW: True}) if old is None
                                       else chosen)
            notes.append(f"{name} is drawn {kind} now")
    for name, (_kind, _order, line) in sorted(listed.items(), key=lambda kv: kv[1][2]):
        problems.append(f"{PARTS} line {line}: {name} isn't a part of the model")
    return rows


def write_built(folder, built: Built) -> Path:
    """Puts the built mesh in the package's `built/` folder, and returns it."""
    out = Path(folder) / BUILT / f"map_{built.number:03d}_mesh.bin"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(built.mesh)
    return out


def mesh_relative_path(number: int) -> str:
    return f"{me.MESH_FOLDER}/map_{number:03d}_mesh.bin"


def picture_relative_path(number: int, name: str) -> str:
    return f"{me.TEXTURE_FOLDER}/{number:03d}/{name}"


# =============================================================================
# The ground under the tiles
# =============================================================================

#: Faces whose normal is this near straight up (its y, the normal of length
#: 1) are ground a unit can stand on, for `ground_under_tiles`.
GROUND_UP = 0.3
#: A corner's ground moved when it moved this many height steps or more.
GROUND_MOVED = 0.25
#: Ground drawn for no tile is a tile's when it is this many height steps
#: from the tile's corner or nearer.
GROUND_NEAR = 1.0
#: How far inside a tile its corners' ground is looked for, in units (a
#: tile is 28 wide): on a slope of 2 steps, 0.17 of a step lower or higher
#: than the corner, before and after alike.
GROUND_INSET = 2.0
#: The kinds of part that are not ground: drawn over it, round it, or only
#: from one camera.
NOT_GROUND = ("edge", "overlay", "side", "top", "upright")
#: A tile's corner with none of its ground near it (`ground_under_tiles`).
_NO_GROUND = object()


@dataclass
class Ground:
    """Where the tiles under a built model go (`ground_under_tiles`)."""
    grid_file: Optional[str]        # the classic file holding the grid
    #: `{(x, z, level): {"height", "slope", "slope_height": value}}` for each
    #: tile whose ground moved: what it becomes.
    tiles: dict
    lost: int                       # tiles whose ground moved but which have none under them now


def _triangles(mesh, skip: set) -> tuple:
    """
    `(by tile, by cell)`: the ground's triangles, in file units (y down),
    those drawn for a tile under its `(x, z, level)`, and every one under
    each 28 unit cell it covers.
    """
    bound, cells = {}, {}
    for poly in mesh.polygons():
        block = mesh.blocks[poly.block]
        if me.is_panel(poly.part) or (poly.block, poly.part) in skip:
            continue
        points = [tuple(block.positions[c]) for c in poly.corners]
        # Up, in file units, is y going down: Newell's normal, its y turned.
        nx = ny = nz = 0.0
        for i, (x0, y0, z0) in enumerate(points):
            x1, y1, z1 = points[(i + 1) % len(points)]
            nx += (y0 - y1) * (z0 + z1)
            ny += (z0 - z1) * (x0 + x1)
            nz += (x0 - x1) * (y0 + y1)
        length = math.sqrt(nx * nx + ny * ny + nz * nz)
        if not length or abs(ny) / length < GROUND_UP:
            continue
        tris = [(points[0], points[1], points[2])] + ([(points[0], points[2], points[3])]
                                                       if len(points) == 4 else [])
        if poly.tile is not None:
            bound.setdefault(tuple(poly.tile), []).extend(tris)
        for tri in tris:
            xs, zs = [p[0] for p in tri], [p[2] for p in tri]
            for cx in range(math.floor(min(xs) / mc.TILE_SIZE), math.floor(max(xs) / mc.TILE_SIZE) + 1):
                for cz in range(math.floor(min(zs) / mc.TILE_SIZE), math.floor(max(zs) / mc.TILE_SIZE) + 1):
                    cells.setdefault((cx, cz), []).append(tri)
    return bound, cells


def _heights_at(tris, x: float, z: float, slack: float = 0.5) -> list:
    """The ground's heights (file y) at a point, on every triangle over or under it."""
    out = []
    for a, b, c in tris:
        d = (b[2] - c[2]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[2] - c[2])
        if abs(d) < 1e-9:
            continue
        l1 = ((b[2] - c[2]) * (x - c[0]) + (c[0] - b[0]) * (z - c[2])) / d
        l2 = ((c[2] - a[2]) * (x - c[0]) + (a[0] - c[0]) * (z - c[2])) / d
        l3 = 1.0 - l1 - l2
        edge = slack / max(1.0, math.sqrt(abs(d)))
        if min(l1, l2, l3) >= -edge:
            out.append(l1 * a[1] + l2 * b[1] + l3 * c[1])
    return out


def _nearest(heights: list, near: float) -> Optional[float]:
    return min(heights, key=lambda y: abs(y - near)) if heights else None


#: What a step of slope costs `fit_tile`, against the squared steps its
#: corners are off: a tile a little uneven stays flat, rather than taking
#: a slope that fits its corners a hair better.
SLOPE_COST = 0.25


def fit_tile(corners) -> tuple:
    """
    `(height, slope, slope height)` whose corners (`map_classic.Tile
    .corner_heights`, in steps) come nearest `corners`: one of the game's
    thirteen slopes, whole steps, the least rise and a flat tile first where
    two fit as well (`SLOPE_COST`).
    """
    low, high = min(corners), max(corners)
    best = None
    for slope, (_name, raised) in mc.SLOPES.items():
        rises = [0] if not any(raised) else range(1, min(31, max(1, math.ceil(high - low) + 1)) + 1)
        for rise in rises:
            mean = sum(c - rise * r for c, r in zip(corners, raised)) / 4.0
            height = min(255, max(0, round(mean)))
            error = sum((height + rise * r - c) ** 2 for c, r in zip(corners, raised)) + SLOPE_COST * rise
            key = (round(error, 6), rise, slope != 0)
            if best is None or key < best[0]:
                best = (key, (height, slope, rise))
    return best[1]


def ground_under_tiles(folder, built: Built, game_dir) -> Ground:
    """
    Where the tiles under a package's built model go, so units stand on its
    ground: for each tile of the grid the package was saved with (`map.json`),
    how far the model's ground rose or fell at its four corners, between the
    package's base mesh and the built one - on the faces drawn for that tile
    where it has them (a face kept or moved keeps its tile), else on the
    ground within a step of the corner. A corner with neither moves as the
    tile's other corners do, and a tile with no such corner stays (002's
    tree top, 8 steps over the ground). A tile whose corners moved a quarter
    step or more gets the height, slope and slope height nearest its
    corners moved so much (`fit_tile`), from where they were when the
    package was saved.
    """
    package = read_package(folder)
    meta = package.metadata
    grid = meta.get("grid") or {}
    grid_name = grid.get("file")
    if not grid_name or not game_dir:
        return Ground(grid_name, {}, 0)
    terrain = mc.read_mesh((Path(game_dir) / mc.MAP_FOLDER / grid_name).read_bytes()).terrain
    game = {(t.x, t.z, t.level): t for t in terrain.tiles} if terrain else {}
    kinds = {}
    for name, info in (meta.get("parts") or {}).items():
        kinds[(info["block"], name.split("@")[0])] = kind_of(info.get("row"))
    for name, (kind, order, _line) in package.parts.items():
        part, _at, block = name.partition("@")
        if kind in PART_KINDS:
            kinds[(int(block or 0), part)] = (kind, PART_KINDS[kind][1] if order is None else order)
    # Nor is a see through layer drawn in its order over the rest: water's
    # surface, and the splashes lying on it (048's).
    skip = {key for key, (kind, order) in kinds.items() if kind in NOT_GROUND or order}
    base_bound, base_cells = _triangles(package.base, skip)
    after = me.read_mesh(built.mesh)
    after_bound, after_cells = _triangles(after, skip)
    tiles, lost = {}, 0
    for text, values in (grid.get("tiles") or {}).items():
        key = tuple(int(v) for v in text.split(","))
        tile = game.get(key)
        if tile is None or tile.is_blank:
            continue
        if key[2] == 1 and key not in base_bound:
            # An upper level tile with nothing drawn for it: most are no
            # tile at all (height 0 under the ground), and none is ground
            # to follow.
            continue
        height, slope, rise = values
        pattern = mc.SLOPES.get(slope, ("", (0, 0, 0, 0)))[1]
        saved = [height + rise * r for r in pattern]
        x, z = key[0], key[1]
        deltas = []
        for (u, w), steps in zip(((0, 0), (1, 0), (1, 1), (0, 1)), saved):
            # A little inside the tile from its corner: on its own ground, and
            # not on the next tile's, which meets it at the corner.
            px = mc.TILE_SIZE * (x + u) + (GROUND_INSET if u == 0 else -GROUND_INSET)
            pz = mc.TILE_SIZE * (z + w) + (GROUND_INSET if w == 0 else -GROUND_INSET)
            cell = (x, z)
            before = _nearest(_heights_at(base_bound.get(key, []), px, pz), -steps * mc.HEIGHT_STEP)
            if before is None:
                # Ground drawn for no tile, where the tile stands on it.
                before = _nearest(_heights_at(base_cells.get(cell, []), px, pz), -steps * mc.HEIGHT_STEP)
                if before is not None and abs(before + steps * mc.HEIGHT_STEP) > GROUND_NEAR * mc.HEIGHT_STEP:
                    before = None
            if before is None:
                deltas.append(_NO_GROUND)        # none of its ground here to follow
                continue
            now = _nearest(_heights_at(after_bound.get(key, []), px, pz), before)
            if now is None:
                now = _nearest(_heights_at(after_cells.get(cell, []), px, pz), before)
            deltas.append(None if now is None else (before - now) / mc.HEIGHT_STEP)
        if any(d is None for d in deltas):
            lost += 1
            continue
        measured = [d for d in deltas if d is not _NO_GROUND]
        if not measured:
            continue                             # nothing of its ground drawn near it
        # A corner with none of the tile's ground near it moves as the rest of
        # the tile does: its faces cover part of it, or the model's ground
        # there is a step or more from the grid's (on 002, several tiles'
        # faces cover half the tile, the ground two steps lower under the
        # rest). Left where it was, the tile would tip into a slope.
        middle = sum(measured) / len(measured)
        deltas = [middle if d is _NO_GROUND else d for d in deltas]
        if all(abs(d) < GROUND_MOVED for d in deltas):
            continue
        tiles[key] = dict(zip(("height", "slope", "slope_height"),
                              fit_tile([s + d for s, d in zip(saved, deltas)])))
    return Ground(grid_name, tiles, lost)


# =============================================================================
# The highlight panels, and the grid a mod has
# =============================================================================

def enhanced_grid_file(game_dir, number: int) -> Optional[str]:
    """
    The classic file holding the grid the enhanced look stands on: its first
    arrangement's, by day and in no weather, as the Map Editor shows it.
    The enhanced mesh has one set of highlight panels, for that grid.
    """
    folder = Path(game_dir) / mc.MAP_FOLDER
    try:
        index = mc.read_gns(folder, number)
    except OSError:
        return None
    states = [s for s in index.states() if s.arrangement == 0] or index.states()
    if not states:
        return None
    source = index.sources(states[0]).get("terrain")
    return source.file_name if source else None


def panels_for_tiles(mesh_bytes: bytes, game_dir, number: int, edited_tiles: dict) -> tuple:
    """
    `(mesh bytes, panels moved)`: the highlight panels of `mesh_bytes` put on
    the grid as edited (`{(x, z, level): Tile}`), from the game's panels and
    the game's tiles (`map_enhanced.panels_following`). The bytes as they
    were when nothing moved.
    """
    game_dir = Path(game_dir)
    name = enhanced_grid_file(game_dir, number)
    if name is None:
        return mesh_bytes, 0
    terrain = mc.read_mesh((game_dir / mc.MAP_FOLDER / name).read_bytes()).terrain
    if terrain is None:
        return mesh_bytes, 0
    game_tiles = {(t.x, t.z, t.level): t for t in terrain.tiles}
    game_mesh = me.read_mesh(me.mesh_path(game_dir, number).read_bytes())
    mesh, moved = me.panels_following(me.read_mesh(mesh_bytes), game_mesh,
                                      me.tile_rise(game_tiles, edited_tiles))
    return (me.write_mesh(mesh) if moved else mesh_bytes), moved


def build_into_mod(folder, mod_folder, mode: str = "enhanced", game_dir=None) -> dict:
    """
    Builds a package straight into a mod folder's `FFTIVC/data/<mode>/`: the
    mesh, and each changed or new texture as the game's own kind of file
    (TGA). With `game_dir`, the highlight panels follow the grid the mod
    has for the map (its `fftpack/map/` copy of the enhanced look's grid
    file), as the Map Editor's export does. The table rows of new groups
    and parts go into the package's `built/tables.json`: a mod's tables are
    written by Mod Studio's export, which needs FF16Tools. Returns `{"mesh":
    path, "pictures": [paths], "tables": path or None, "notes": [...],
    "counts": {...}}`.
    """
    from . import texture_data as td

    built = build(folder)
    data = Path(mod_folder) / "FFTIVC" / "data" / mode
    mesh_bytes = built.mesh
    if game_dir is not None:
        name = enhanced_grid_file(game_dir, built.number)
        edited = data / mc.MAP_FOLDER / name if name else None
        if edited is not None and edited.is_file():
            terrain = mc.read_mesh(edited.read_bytes()).terrain
            tiles = {(t.x, t.z, t.level): t for t in terrain.tiles} if terrain else {}
            mesh_bytes, moved = panels_for_tiles(mesh_bytes, game_dir, built.number, tiles)
            if moved:
                built.notes.append(f"{moved} highlight panels follow the mod's grid ({name})")
    mesh_out = data / mesh_relative_path(built.number)
    mesh_out.parent.mkdir(parents=True, exist_ok=True)
    mesh_out.write_bytes(mesh_bytes)
    write_built(folder, built)
    pictures = []
    staging = Path(folder) / BUILT / "pictures"
    for name, source in sorted(built.pictures.items()):
        relative = picture_relative_path(built.number, name)
        staged = td.stage_texture_replacement(relative, source, staging, None)
        target = data / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(staged, target)
        pictures.append(target)
    tables = None
    if built.table_rows:
        tables = Path(folder) / BUILT / "tables.json"
        tables.write_text(json.dumps(
            {table: [{"Key": key[0], "Key2": key[1], "Key3": key[2],
                      **{k: v for k, v in fields.items() if k != ADDED_ROW},
                      "added": bool(fields.get(ADDED_ROW))}
                     for key, fields in sorted(rows.items())]
             for table, rows in built.table_rows.items()}, indent=1), encoding="utf-8")
    return {"mesh": mesh_out, "pictures": pictures, "tables": tables, "notes": built.notes,
            "counts": built.counts}


def check(folder) -> list:
    """Every problem with a package, as lines for the person; empty when it builds."""
    try:
        built = build(folder)
    except PackageError as exc:
        return str(exc).splitlines()
    return [] if built else ["it builds nothing"]


# =============================================================================
# From a command line
# =============================================================================

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m mod_studio.map_package",
        description="A battle map's enhanced look as files anyone can edit, and back into a mod.")
    sub = parser.add_subparsers(dest="command", required=True)
    e = sub.add_parser("export", help="write a map's enhanced look into a folder for editing")
    e.add_argument("--game", required=True, help="the unpacked game folder")
    e.add_argument("--map", required=True, type=int, help="the map's number, 48 for Sal Ghidos Slumtown")
    e.add_argument("--out", required=True, help="the folder to write (made if missing)")
    e.add_argument("--database", help="the game's database (fft_data.sqlite), for the textures' names "
                                      "and how each part is drawn")
    c = sub.add_parser("check", help="say what is wrong with a package, if anything")
    c.add_argument("folder")
    b = sub.add_parser("build", help="build a package into a mod folder")
    b.add_argument("folder")
    b.add_argument("--mod", required=True, help="the mod's folder (the one with ModConfig.json)")
    b.add_argument("--mode", default="enhanced", choices=("enhanced", "combined"))
    b.add_argument("--game", help="the unpacked game folder: the highlight panels then follow "
                                  "the grid the mod has for the map")
    p = sub.add_parser("preview", help="draw a package's map from the four camera corners")
    p.add_argument("folder")
    p.add_argument("--game", required=True, help="the unpacked game folder")
    p.add_argument("--out", required=True, help="the image to write (.png)")
    args = parser.parse_args(argv)
    try:
        if args.command == "export":
            done = export_package(args.game, args.map, args.out, sqlite_path=args.database)
            print(f"Wrote map {args.map:03d} to {done['folder']}: {done['objects']} parts, "
                  f"{done['faces']} faces, {done['pictures']} textures.")
            for name in done["missing"]:
                print(f"  not in the game folder: {name}")
        elif args.command == "check":
            problems = check(args.folder)
            for line in problems:
                print(line)
            print("It builds." if not problems else f"{len(problems)} problem(s).")
            return 1 if problems else 0
        elif args.command == "build":
            done = build_into_mod(args.folder, args.mod, args.mode, game_dir=args.game)
            print(f"Wrote {done['mesh']}")
            for path in done["pictures"]:
                print(f"Wrote {path}")
            if done["tables"]:
                print(f"Wrote {done['tables']}: the table rows for new texture groups and parts. "
                      f"Mod Studio puts them into a mod (Load edited in the Map Editor, then "
                      f"Export Mod).")
            for line in done["notes"]:
                print(f"  {line}")
        elif args.command == "preview":
            # Drawn by the interface's renderer, in a process of its own: the
            # engine imports no Qt (dev/test_engine_boundary.py).
            import subprocess
            return subprocess.run([sys.executable, "-m", "mod_studio.qt.map_preview", args.folder,
                                   "--game", args.game, "--out", args.out]).returncode
    except PackageError as exc:
        print(str(exc))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
