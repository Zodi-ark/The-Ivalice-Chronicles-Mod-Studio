"""
The tiles a map's battles use, and the new faces over them: the Map
Editor's "Show battles" and Load edited's warnings (Zodi's stress test of 20
October, item 19: "Nowhere to see the tiles battles use". The first tundra's
crystals and icons reached over five of them, four of them squares a
player places units on, and nothing on the page showed it).

**What a map's battles use**, read from the unpacked game (measured on 085
with `dev/research/maps/unit_tiles.py`, whose reading this is: 17 battles,
three random roads and the story's squad, 81 tiles):

- **Where each battle's units start**: every ENTD battle fought on the map
  (`battle_maps`), each slot's tile and level (a slot with no sprite set
  and no job is no unit), with the game's `OverrideEntryData` rows and the
  mod's edits over them as the Encounters page takes them: a position of -1
  and an elevation other than 0 or 1 leave the unit's own; a row that
  disables its unit leaves it out. (A row moved to another slot, a trade,
  is read where it is.)
- **The squares the player may place units on**: each scenario on the map's
  deployment squads in ATTACK.OUT (`event_scripts.deployment`), and each
  random battle's: a WLDCORE.BIN road row's byte 1 plus 0x200 is its squad
  (adamrt's fft_decomp, `src/wldcore/map_routes.c`:
  `random_battle_road_t.deployment_squad_id`, "deployment zone id = this +
  0x200").

**Which camera corners new faces hide tiles from** (`corners_hiding`): a
face hides a tile from a corner when, seen from the battle camera standing
there (looking down at `CAMERA_PITCH`, as the game draws it: straight on,
no perspective), it is in front of the tile's middle or of a unit standing
on it (its feet, middle or head). The tiles the faces stand on are not
counted: they are under them from every corner (the tundra's glacier
stands on the east column, where no unit may). `parts.txt`'s "hide auto"
leaves a part out from every corner it hides a tile from, as the game
leaves out its own walls (bits 13 to 2: `map_enhanced.CAMERA_CORNERS`).

**New faces over tiles** (`faces_over`): each face a model adds (drawn for
no tile, on corners its base mesh has no face on), sampled across its area. Over a tile, a
point more than half a height step above the tile's surface stands over it
(a crystal leaning over a square: a unit there is hidden, or can't be
reached); one just above the highlight panels, which sit 0.2 above a tile's
surface, and below that half step, on a face turned up, covers them: the
move and target highlights don't show there (the tundra's frozen lake, a
quarter above its tiles, 20 October's screenshot).

Nothing here imports Qt.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from . import battle_maps as bm
from . import constants as c
from . import entd
from . import event_scripts as es
from . import map_classic as mc
from . import map_enhanced as me

#: What a tile is used for: a unit starts there, or the player may put one there.
START, SQUARE = "start", "square"
#: Where the game draws a tile's move and target highlights: this far above
#: its surface, in units (`map_enhanced`'s notes: the panels).
PANEL_LIFT = 0.2
#: A new face this far above a tile's surface, or more, stands over it.
STANDS = mc.HEIGHT_STEP / 2
#: How many points a side a face is sampled at.
SAMPLES = 6
#: The battle camera's height over the ground, in degrees: the lowest it
#: looks from, where walls hide the most (`map_scene.LOW_PITCH`, GaneshaDx's,
#: the 2:1 of the game's pictures).
CAMERA_PITCH = 26.54
#: Where a unit standing on a tile is, above its surface: its feet, its
#: middle and its head (a unit is about two height steps tall).
UNIT_POINTS = (0.0, mc.HEIGHT_STEP, 2.0 * mc.HEIGHT_STEP)
#: A face this far nearer the camera than a point, or more, is in front of it.
IN_FRONT = 2.0
#: The size of the squares the camera's picture is cut into to find the
#: points behind a face quickly, in units.
_BUCKET = 16.0


@dataclass(frozen=True)
class TileUse:
    """
    One use of a tile: `kind` START or SQUARE, said in `label`; `battle` the
    ENTD battle of a start; `scenario` the scenario, or `road` the random
    battles' road, of a square.
    """
    kind: str
    label: str
    battle: Optional[int] = None
    scenario: Optional[int] = None
    road: Optional[int] = None


def _effective(stored, inherit, own):
    """An override row's value for a column, or the unit's own where the row leaves it."""
    try:
        value = None if stored is None or stored == "" else int(stored)
    except (TypeError, ValueError):
        value = None
    return own if value is None or value == inherit else value


def battle_tiles(game_dir, number: int, entry_records=None, entry_edits=None, entd_dir=None) -> dict:
    """
    `{(x, z, level): [TileUse]}`: the tiles map `number`'s battles use (see
    the module's notes). `entry_records` are the game's `OverrideEntryData`
    rows (`nxd_data.read_override_entry_table`, `state.entry_records`) and
    `entry_edits` the mod's (`state.entry_edits`); without them the ENTD
    files' own places. The ENTD files are the game folder's, or
    `entd_dir`'s (a folder holding `fftpack/battle_entd*`). Without them,
    no starts; without ATTACK.OUT or WLDCORE.BIN, no squares.
    """
    game = Path(game_dir) if game_dir else None
    used = {}
    if game is None:
        return used

    def add(x, z, level, use):
        found = used.setdefault((int(x), int(z), int(level)), [])
        if use not in found:
            found.append(use)

    try:
        attack = (game / bm.SCENARIO_FILE).read_bytes()
    except OSError:
        attack = b""
    maps = bm.read_battle_maps(game)
    if attack:
        for scenario in maps.scenarios:
            if scenario.map != number:
                continue
            deployed = es.deployment(attack, scenario.number)
            for x, z, level, _facing in (deployed.tiles if deployed else ()):
                add(x, z, level, TileUse(SQUARE, f"scenario {scenario.number}'s squares", scenario=scenario.number))
        try:
            world = (game / bm.RANDOM_FILE).read_bytes()
        except OSError:
            world = b""
        for at in range(bm.RANDOM_AT, bm.RANDOM_END, bm.RANDOM_BYTES):
            row = world[at:at + bm.RANDOM_BYTES]
            if len(row) < bm.RANDOM_BYTES or row[22] != number:
                continue
            squad = es.read_squad(attack, row[1] + 0x200)
            for x, z, level, _facing in (es.squad_tiles(squad) if squad and squad.tiles else ()):
                add(x, z, level, TileUse(SQUARE, f"random battles' squares (road {row[0]})", road=row[0]))
    tables = entd.EntdTables.from_folder(entd_dir or game)
    if tables is None:
        return used
    overrides = {(int(r.key), int(r.key2)): dict(r.values) for r in (entry_records or ())}
    for key, fields in (entry_edits or {}).items():
        try:
            overrides.setdefault((int(key[0]), int(key[1])), {}).update(fields)
        except (TypeError, ValueError, IndexError):
            continue
    for battle in sorted(b for b, on in maps.maps.items() if number in on):
        for slot in range(entd.UNITS_PER_EVENT):
            unit = tables.unit_at(battle, slot)
            if unit is None:
                continue
            values = dict(unit.values)
            row = overrides.get((battle, slot), {})
            try:
                if int(row.get("Disable", 0) or 0):
                    continue
            except (TypeError, ValueError):
                pass
            sprite_set = _effective(row.get("Spriteset"), c.entry_inherit_value("Spriteset"), values.get("sprite_set"))
            job = _effective(row.get("MainJob"), c.entry_inherit_value("MainJob"), values.get("main_job"))
            if not sprite_set and not job:
                continue
            x = _effective(row.get("PositionX"), c.entry_inherit_value("PositionX"), values.get("x"))
            z = _effective(row.get("PositionY"), c.entry_inherit_value("PositionY"), values.get("y"))
            level = int(bool(values.get("upper_level")))
            try:
                higher = int(row.get("HigherElevation", 255))
            except (TypeError, ValueError):
                higher = 255
            if higher in (0, 1):
                level = higher
            add(x, z, level, TileUse(START, f"battle {battle}, unit {slot + 1}", battle))
    return used


def _runs(numbers, most: int = 6) -> str:
    """
    Numbers said shortly: runs of three or more as "157 to 168", the rest
    listed, "and" before the last; past `most` pieces, "and N more".
    """
    numbers = sorted(set(numbers))
    pieces, i = [], 0
    while i < len(numbers):
        j = i
        while j + 1 < len(numbers) and numbers[j + 1] == numbers[j] + 1:
            j += 1
        if j - i >= 2:
            pieces.append((f"{numbers[i]} to {numbers[j]}", j - i + 1))
        else:
            pieces.extend((str(n), 1) for n in numbers[i:j + 1])
        i = j + 1
    if len(pieces) > most:
        left = sum(count for _text, count in pieces[most - 1:])
        words = [text for text, _count in pieces[:most - 1]] + [f"{left} more"]
    else:
        words = [text for text, _count in pieces]
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def describe_uses(uses) -> str:
    """A tile's uses in a line: `uses_lines`' lines, joined."""
    return "; ".join(uses_lines(uses))


def uses_lines(uses) -> list:
    """
    A tile's uses, a line each: the battles a unit starts here in, then
    where the player places units here ("scenarios 15 to 23 and random
    battles (road 3)").
    """
    starts = sorted({u.battle for u in uses if u.kind == START and u.battle is not None})
    scenarios = sorted({u.scenario for u in uses if u.kind == SQUARE and u.scenario is not None})
    roads = sorted({u.road for u in uses if u.kind == SQUARE and u.road is not None})
    words = []
    if starts:
        words.append(f"a unit starts here in battle{'s' if len(starts) != 1 else ''} {_runs(starts)}")
    places = []
    if scenarios:
        places.append(f"scenario{'s' if len(scenarios) != 1 else ''} {_runs(scenarios)}")
    if roads:
        places.append(f"random battles (road{'s' if len(roads) != 1 else ''} {_runs(roads)})")
    if places:
        words.append("the player places units here in " + " and ".join(places))
    return words


# -- new faces over tiles ----------------------------------------------------------------

def _surface(tile: mc.Tile, u: float, w: float) -> float:
    """A tile's surface height at (u, w) across it (0 to 1 each way), in units, y up."""
    h00, h10, h11, h01 = tile.corner_heights()
    height = (h00 * (1 - u) * (1 - w) + h10 * u * (1 - w) + h11 * u * w + h01 * (1 - u) * w)
    return height * mc.HEIGHT_STEP


def _samples(points: list) -> list:
    """Points spread over a triangle or a quad (`SAMPLES` a side), its corners among them."""
    if len(points) == 4:
        a, b, c3, d = points
        out = []
        for i in range(SAMPLES + 1):
            for j in range(SAMPLES + 1):
                s, t = i / SAMPLES, j / SAMPLES
                out.append(tuple(a[k] * (1 - s) * (1 - t) + b[k] * s * (1 - t) + c3[k] * s * t + d[k] * (1 - s) * t
                                 for k in range(3)))
        return out
    a, b, c3 = points[:3]
    out = []
    for i in range(SAMPLES + 1):
        for j in range(SAMPLES + 1 - i):
            s, t = i / SAMPLES, j / SAMPLES
            out.append(tuple(a[k] + (b[k] - a[k]) * s + (c3[k] - a[k]) * t for k in range(3)))
    return out


def _corner_set(block, poly) -> tuple:
    return tuple(sorted(tuple(round(float(v), 2) for v in block.positions[k]) for k in poly.corners))


def faces_over(mesh, tiles: dict, base=None) -> dict:
    """
    `{"stands": {(x, z, level): faces}, "covers": {(x, z, level): faces},
    "parts": {(x, z, level): [part names]}}`: how many new faces of `mesh`
    (an `EnhancedMesh`) stand over each tile of `tiles` (`{(x, z, level):
    Tile}`, as edited), how many cover its highlights (see the module's
    notes), and which parts they are. A new face is one drawn for no tile
    whose corners `base` (the mesh the model was made from) has no face on;
    without `base`, every face drawn for no tile. A tile of the upper level
    counts where it is a tile.
    """
    stands, covers, parts = {}, {}, {}
    by_cell = {}
    for key, tile in tiles.items():
        if tile.is_blank or tile.is_placeholder:
            continue
        by_cell.setdefault((key[0], key[1]), []).append((key, tile))
    known = set()
    for block in (base.blocks if base is not None else ()):
        for poly in block.polygons():
            known.add(_corner_set(block, poly))
    for block in mesh.blocks:
        for poly in block.polygons():
            if poly.tile is not None or "panel_ui" in (poly.part or "").lower():
                continue
            if _corner_set(block, poly) in known:
                continue
            points = [(float(block.positions[k][0]), -float(block.positions[k][1]), float(block.positions[k][2]))
                      for k in poly.corners]
            if len({p for p in points}) < 3:
                continue
            ax, ay, az = (points[1][i] - points[0][i] for i in range(3))
            bx, by, bz = (points[2][i] - points[0][i] for i in range(3))
            normal = (ay * bz - az * by, az * bx - ax * bz, ax * by - ay * bx)
            length = math.sqrt(sum(v * v for v in normal)) or 1.0
            flat = abs(normal[1]) / length > 0.7
            stood, covered = set(), set()
            for x, y, z in _samples(points):
                cell = (math.floor(x / mc.TILE_SIZE), math.floor(z / mc.TILE_SIZE))
                for key, tile in by_cell.get(cell, ()):
                    u, w = x / mc.TILE_SIZE - cell[0], z / mc.TILE_SIZE - cell[1]
                    above = y - _surface(tile, u, w)
                    if above >= STANDS:
                        stood.add(key)
                    elif flat and above > PANEL_LIFT + 0.01:
                        covered.add(key)
            for key in stood:
                stands[key] = stands.get(key, 0) + 1
            for key in covered - stood:
                covers[key] = covers.get(key, 0) + 1
            for key in stood | covered:
                parts.setdefault(key, set()).add(poly.part)
    return {"stands": stands, "covers": covers, "parts": {k: sorted(v) for k, v in parts.items()}}


def _camera_axes(angle: float, pitch: float = CAMERA_PITCH) -> tuple:
    """Right, up and towards the camera, for the camera standing at `angle` in the files' ground plane, y up."""
    az, el = math.radians(angle), math.radians(pitch)
    towards = (math.cos(az) * math.cos(el), math.sin(el), math.sin(az) * math.cos(el))
    right = (-math.sin(az), 0.0, math.cos(az))
    up = (towards[1] * right[2] - towards[2] * right[1], towards[2] * right[0] - towards[0] * right[2],
          towards[0] * right[1] - towards[1] * right[0])
    return right, up, towards


def _seen(point, axes) -> tuple:
    """Where `point` is in the camera's picture, and how near the camera: (across, up, nearness)."""
    return tuple(sum(point[i] * axis[i] for i in range(3)) for axis in axes)


def _in_front(x, y, triangle) -> Optional[float]:
    """How near the camera `triangle` (three `_seen` points) is at (x, y) of the picture, or None off it."""
    (ax, ay, ad), (bx, by, bd), (cx, cy, cd) = triangle
    det = (bx - ax) * (cy - ay) - (cx - ax) * (by - ay)
    if abs(det) < 1e-9:
        return None
    s = ((x - ax) * (cy - ay) - (cx - ax) * (y - ay)) / det
    t = ((bx - ax) * (y - ay) - (x - ax) * (by - ay)) / det
    if s < -1e-9 or t < -1e-9 or s + t > 1 + 1e-9:
        return None
    return ad + s * (bd - ad) + t * (cd - ad)


def corners_hiding(faces, tiles: dict, pitch: float = CAMERA_PITCH) -> dict:
    """
    `{corner: {(x, z, level)}}`: for each camera corner
    (`map_enhanced.CAMERA_CORNERS`' names), the tiles of `tiles` (`{(x, z,
    level): Tile}`) that `faces` hide from the camera standing there (see
    the module's notes), but those they stand on. `faces` are each a face's
    corners, (x, y, z) in the files' ground plane with y up. A corner no
    face hides a tile from has an empty set.
    """
    under = {(math.floor(x / mc.TILE_SIZE), math.floor(z / mc.TILE_SIZE))
             for face in faces if len(face) >= 3 for x, _y, z in _samples(list(face))}
    points = []
    for key, tile in tiles.items():
        if tile.is_blank or tile.is_placeholder or (key[0], key[1]) in under:
            continue
        x, z = (key[0] + 0.5) * mc.TILE_SIZE, (key[1] + 0.5) * mc.TILE_SIZE
        ground = _surface(tile, 0.5, 0.5)
        points.extend(((x, ground + lift, z), key) for lift in UNIT_POINTS)
    out = {}
    for name, (angle, _bit, _bands) in me.CAMERA_CORNERS.items():
        axes = _camera_axes(angle, pitch)
        buckets = {}
        for point, key in points:
            seen = _seen(point, axes)
            buckets.setdefault((math.floor(seen[0] / _BUCKET), math.floor(seen[1] / _BUCKET)), []).append(
                (seen, key))
        hidden = set()
        for face in faces:
            if len(face) < 3:
                continue
            corners = [_seen(p, axes) for p in face]
            triangles = [(corners[0], corners[i], corners[i + 1]) for i in range(1, len(corners) - 1)]
            xs, ys = [c[0] for c in corners], [c[1] for c in corners]
            for bx in range(math.floor(min(xs) / _BUCKET), math.floor(max(xs) / _BUCKET) + 1):
                for by in range(math.floor(min(ys) / _BUCKET), math.floor(max(ys) / _BUCKET) + 1):
                    for (px, py, near), key in buckets.get((bx, by), ()):
                        if key in hidden:
                            continue
                        for triangle in triangles:
                            depth = _in_front(px, py, triangle)
                            if depth is not None and depth >= near + IN_FRONT:
                                hidden.add(key)
                                break
        out[name] = hidden
    return out


def package_grid(meta: dict) -> dict:
    """`{(x, z, level): Tile}` from a package's `map.json` grid: each tile's height and slope, as saved."""
    out = {}
    for text, values in ((meta.get("grid") or {}).get("tiles") or {}).items():
        try:
            x, z, level = (int(v) for v in text.split(","))
            height, slope, rise = (int(v) for v in values)
        except (TypeError, ValueError):
            continue
        raw = mc.tile_with(bytes(8), {"height": height, "slope": slope, "slope_height": rise})
        out[(x, z, level)] = mc.Tile(x, z, level, raw)
    return out
