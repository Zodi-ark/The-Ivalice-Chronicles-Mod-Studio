"""
A battle map's enhanced look as files anyone can edit: the model as a
Wavefront OBJ, its pictures as PNG, and in JSON what OBJ has no room for.
Made for Blender or any 3D program, for a script, and for an AI coworker
changing a map. Asked for by Zodi as "a streamlined process that allows
users and AI coworkers such as Claude to create new maps and or modify
existing maps appearances (model and textures) ... focus on enhanced".

A package is a folder:

    README.txt    how to edit it, for people and for programs
    map.obj       the model, one object per part of the map
    map.mtl       one material per texture group (group_0 ...), and untextured
    textures/     every picture the map's groups use, as PNG
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
- **Pictures**: a PNG whose bytes changed since it was written, or a
  material pointed at another file, replaces that picture in the mod.

What it can't do yet, and says so: add texture groups (the game finds a
group's pictures in its `RefinedBgTexture` table, which this doesn't
write), add moving parts, or change the classic look.

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
import struct
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import map_classic as mc
from . import map_enhanced as me

VERSION = 1
KIND_NAME = "The Ivalice Chronicles Mod Studio map package"
MODEL, MATERIALS, METADATA, README = "map.obj", "map.mtl", "map.json", "README.txt"
BASE, TEXTURES, BUILT = "base", "textures", "built"
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


def export_package(game_dir, number: int, folder, sqlite_path=None, mesh_file=None,
                   picture_files: Optional[dict] = None) -> dict:
    """
    Writes map `number`'s enhanced look into `folder` as a package.

    `mesh_file` is the mesh to start from when not the game's (a mod's own);
    `picture_files` `{picture name: image file}` the pictures a mod replaces.
    Returns a summary: `{"folder", "objects", "faces", "pictures"}`.
    """
    from PIL import Image

    game_dir, folder = Path(game_dir), Path(folder)
    base_path = Path(mesh_file) if mesh_file else me.mesh_path(game_dir, number)
    data = base_path.read_bytes()
    mesh = me.read_mesh(data)
    pictures = me.pictures(game_dir, number, sqlite_path)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / BASE).mkdir(exist_ok=True)
    (folder / TEXTURES).mkdir(exist_ok=True)
    base_name = f"map_{number:03d}_mesh.bin"
    (folder / BASE / base_name).write_bytes(data)

    # -- pictures -------------------------------------------------------------
    source_folder = me.texture_folder(game_dir, number)
    picture_files = {k.lower(): Path(v) for k, v in (picture_files or {}).items()}
    written, missing = {}, []
    groups = {}
    for group, entry in sorted(pictures.items()):
        names = {"colour": list(entry.colour), "lighting": entry.lighting,
                 "lighting2": entry.lighting2}
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
           "# map_Kd is the group's colour picture (its first frame, when it moves)."]
    for material in sorted(used_materials | {f"group_{g}" for g in groups} | {UNTEXTURED}):
        mtl.append(f"newmtl {material}")
        if material == UNTEXTURED:
            mtl += ["Kd 0 0 0", ""]
            continue
        entry = groups.get(material.split("_", 1)[1], {})
        colour = (entry.get("colour") or [None])[0]
        mtl.append("Kd 1 1 1")
        if colour in written:
            mtl.append(f"map_Kd {written[colour]['png']}")
        mtl.append("")
    (folder / MATERIALS).write_text("\n".join(mtl), encoding="utf-8")

    metadata = {
        "kind": KIND_NAME, "version": VERSION, "map": number,
        "base": {"file": f"{BASE}/{base_name}", "sha256": hashlib.sha256(data).hexdigest(),
                 "from": "the mod's own mesh" if mesh_file else f"{me.MESH_FOLDER}/{base_name}"},
        "groups": groups,
        "pictures": written,
        "missing_pictures": missing,
        "objects": objects,
    }
    (folder / METADATA).write_text(json.dumps(metadata, indent=1), encoding="utf-8")
    (folder / README).write_text(readme(number, sorted(groups, key=int)), encoding="utf-8")
    return {"folder": folder, "objects": len(objects),
            "faces": sum(len(v) for v in objects.values()), "pictures": len(written),
            "missing": missing}


def readme(number: int, groups: list) -> str:
    listed = ", ".join(f"group_{g}" for g in groups) or "none"
    return f"""Map {number:03d}: its enhanced look, for editing
{'=' * 40}

Made by The Ivalice Chronicles Mod Studio from the game's own files. Change
the model and the pictures, then load this folder back in the Map Editor
(Load edited), or build it into a mod from a command line (at the end).

What is here

  map.obj      The model. Each object is one part of the map (GT_0_map ...).
               An object named NAME@N is moving part N (a door, a windmill).
  map.mtl      One material per texture group: {listed}.
               And "untextured", which the game draws black.
  textures/    Every picture the groups use, as PNG.
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
    the battle grid, which you change tile by tile in the Map Editor. Units
    stand on the grid, not on the model, so raise or lower the tiles to
    match what you build.

The pictures

  * The game draws each group's colour picture times its lighting picture,
    times 2. A lighting picture of mid grey (128, 128, 128) leaves the colour
    as it is; lighter brightens, darker shades.
  * Change a picture by saving over its PNG here, at any size. Or point the
    material's map_Kd at another file: that replaces the group's colour.
  * A picture with frames (..._color_0.png, ..._color_1.png ...) plays them
    in turn. Keep them the same size.
  * New texture groups can't be added: the game finds a group's pictures in
    its RefinedBgTexture table. Use the groups listed above.

The classic look

  Unchanged. Most mods leave it as it is.

From a command line (for scripts, and AI coworkers)

  From the folder The Ivalice Chronicles Mod Studio is in:

    python -m mod_studio.map_package check THIS_FOLDER
    python -m mod_studio.map_package build THIS_FOLDER --mod MOD_FOLDER
    python -m mod_studio.map_package preview THIS_FOLDER --game GAME_FOLDER --out preview.png

  check says what is wrong with the folder, if anything. build writes the
  mesh and the changed pictures into MOD_FOLDER (FFTIVC/data/enhanced/bg/).
  preview draws the map from the four camera corners into one picture.
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


def read_materials(path: Path) -> dict:
    """`{material: its map_Kd, or None}` from an MTL file."""
    out, current = {}, None
    if not Path(path).is_file():
        return out
    for raw in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.split("#", 1)[0].strip()
        head, _, rest = line.partition(" ")
        if head == "newmtl":
            current = rest.strip()
            out[current] = None
        elif head == "map_Kd" and current is not None:
            out[current] = _map_file(rest.strip())
    return out


#: map_Kd's options and how many values each takes; the file comes after them.
_MAP_OPTIONS = {"-blendu": 1, "-blendv": 1, "-bm": 1, "-boost": 1, "-cc": 1, "-clamp": 1,
                "-imfchan": 1, "-mm": 2, "-o": 3, "-s": 3, "-t": 3, "-texres": 1}


def _map_file(text: str) -> Optional[str]:
    """The file a map_Kd names, after any options (a path may have spaces in it)."""
    words = text.split(" ")
    i = 0
    while i < len(words) and words[i].lower() in _MAP_OPTIONS:
        count = _MAP_OPTIONS[words[i].lower()]
        i += 1
        # Options with up to three numbers take as many as are numbers.
        taken = 0
        while taken < count and i < len(words) and re.fullmatch(r"[-+]?[\d.]+(e[-+]?\d+)?|on|off",
                                                                words[i], re.I):
            i += 1
            taken += 1
    rest = " ".join(words[i:]).strip()
    return rest or None


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
    return Package(folder, metadata, me.read_mesh(base_data), base_data, objects, order, materials)


# =============================================================================
# Building
# =============================================================================

@dataclass
class Built:
    """What a package makes: the mesh file, and the pictures it changes."""
    number: int
    mesh: bytes
    changed: bool                   # False: the mesh is the base's, byte for byte
    pictures: dict                  # {picture name: image file}, the changed ones
    notes: list                     # what was done, for the person
    counts: dict                    # faces kept, moved, new, gone


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


def build(folder, game_dir=None) -> Built:
    """
    The mesh and pictures a package makes (see the module's notes). Raises
    PackageError, with every problem found, for one that can't be built.
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
    problems, notes = [], []
    counts = Counter()

    # Each block's names grow with new parts; its polygons are rebuilt from
    # the OBJ, the highlight panels kept from the base as they are.
    names = [list(block.names) for block in base.blocks]
    slots = [list(block.slot_values) for block in base.blocks]
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
            slots[b].append((1.0, 1.0))
            notes.append(f"{name} is a new part")
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
            if group is not None and group not in groups:
                problems.append(f"object {name}, line {face.line}: group_{group} isn't one of this "
                                f"map's texture groups ({', '.join(f'group_{g}' for g in sorted(groups))})")
                continue
            if group is not None and any(t is None for _p, t, _n in face.corners):
                problems.append(f"object {name}, line {face.line}: a face with a picture "
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
    if exact and len(seen_ids) == len(base_polys) - len(kept_ids):
        mesh_bytes, changed = package.base_data, False
    else:
        blocks = [me.BlockData(names[b], slots[b], new_polys[b]) for b in range(len(base.blocks))]
        mesh_bytes, changed = me.write_mesh(me.assemble(number, blocks)), True
    pictures = changed_pictures(package, notes, problems)
    if problems:
        raise PackageError("\n".join(problems))
    return Built(number, mesh_bytes, changed, pictures, notes, dict(counts))


def changed_pictures(package: Package, notes: list, problems: list) -> dict:
    """`{picture name: image file}` for the pictures the package changes."""
    folder, meta = package.folder, package.metadata
    out = {}
    for name, info in meta["pictures"].items():
        png = folder / info["png"]
        if not png.is_file():
            problems.append(f"{info['png']} is missing: put it back, or the picture it was")
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
    mesh, and each changed picture as the game's own kind of file (TGA).
    With `game_dir`, the highlight panels follow the grid the mod has for
    the map (its `fftpack/map/` copy of the enhanced look's grid file), as
    the Map Editor's export does. Returns `{"mesh": path, "pictures": [paths],
    "notes": [...], "counts": {...}}`.
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
    return {"mesh": mesh_out, "pictures": pictures, "notes": built.notes, "counts": built.counts}


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
    e.add_argument("--database", help="the game's database (fft_data.sqlite), for the pictures' names")
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
    p.add_argument("--out", required=True, help="the picture to write (.png)")
    args = parser.parse_args(argv)
    try:
        if args.command == "export":
            done = export_package(args.game, args.map, args.out, sqlite_path=args.database)
            print(f"Wrote map {args.map:03d} to {done['folder']}: {done['objects']} parts, "
                  f"{done['faces']} faces, {done['pictures']} pictures.")
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
