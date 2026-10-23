"""
Doors and such in the enhanced look: what an event's USE_FIELD_OBJECT
(0x55) and USE_3D_OBJECT (0x54) play on its map (Zodi, 22 October: "apply
this knowledge to the Event Editor so doors and such things as this could
affect behave correctly there too").

**In the classic look** a door is two texture animation records on one
rectangle of the map's texture, their canvas: an event starts one (0x55,
the map's data command 0x83, which starts it from its first frame; the
decompilation's `battle_map_texture_animation_start`) and its frames are
copied there (`map_classic.started_records`). One changes the door from
how the map is read (opens it, mostly), the other puts it back: the one
whose last frame (its first, played backward) is the picture the canvas
holds as the map is read puts it back; where neither is (062's three
frame records), the one played backward; where neither plays backward and
neither is (060), the second. WaitFieldObject (0x57) waits while the last
started plays: its frames times each frame's 60ths of a second
(`Doors.frames`).

**In the enhanced look** a door is a texture group the game's
`RefinedBgAnim` table plays on a trigger (kind 2, `map_scene.
PLAYED_ON_A_TRIGGER`): its pictures go from the door to nothing
(`gt_2_map002_door_color_0` solid, `_4` see through), shown as the map's
anim file's track for the group says, 60 ticks a second
(`map_enhanced.picture_tracks`), and its track's first picture until it
plays. Most doors are a part drawn as the map is read (056's `door1OP`,
its track 0 to 4) and one not (`door1CL`, 4 to 0): changed, the first
plays and the second stays nothing; put back, the second plays and the
first is nothing (its track's last picture). A door of one part plays it,
and back to put the door back: 062's `door` (0 to 4) opens and shuts so,
049's (4 to 0: no door as the map is read) shuts and opens. A record
started again the way its door already is changes nothing. Zodi's test 12
(22 October) showed the remaster plays its doors by the classic records:
with 097's own, 062's chapel door didn't open on the copy; with 062's, it
did.

**Which group is which record's.** The group's polygons made from classic
ones (the enhanced polygon's `source`) whose texture corners all lie in a
record's canvas, the canvas holding most; else the canvas whose classic
polygons, any corner in it, are nearest the group's, within half a tile.
Lightshafts and water a map's table plays on a trigger are farther. A map
with no record an event can start (002) has its trigger groups played by
its 3D object (event 226 opens 002's door with 0x54).

Measured on the 26 maps whose table plays a group on a trigger (26
doors); not checked in the game beyond test 12.

Nothing here imports Qt.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import map_classic as mc
from . import map_enhanced as me
from . import map_package as mpk

#: A trigger group's `RefinedBgAnim` kind (`map_scene.PLAYED_ON_A_TRIGGER`).
TRIGGER = 2
#: How near a group's polygons must be to a canvas's classic ones, in the
#: files' units, to be its door when no texture corner says: half a tile.
NEAR = mc.TILE_SIZE / 2
#: The ticks a second the enhanced tracks play at (`map_enhanced.TICKS_A_SECOND`),
#: and the event's frames a second, the same.
TICKS_A_SECOND = me.TICKS_A_SECOND
#: A group with no track: its frames in turn, each this many ticks.
TICKS_A_FRAME = 5
#: How long a 3D object's door plays when no track says (Wait3DObject, 0x56).
OBJECT_FRAMES = 21


@dataclass
class Door:
    """A door: its canvas, its groups drawn as the map is read (`solid`, their track from the door to
    nothing) and those not (`clear`, from nothing to the door)."""
    canvas: tuple                      # (x, y, width, height), in the PlayStation's VRAM units
    solid: list = field(default_factory=list)
    clear: list = field(default_factory=list)


@dataclass
class Doors:
    """A map's doors, as an event plays them (see the module's notes)."""
    #: `{group: (frame, ...)}`: the picture each trigger group shows at each tick.
    tracks: dict = field(default_factory=dict)
    doors: list = field(default_factory=list)
    #: `{record: (door, away)}`: which door a texture animation record plays, and whether it changes it from
    #: how the map is read (else puts it back).
    records: dict = field(default_factory=dict)
    #: `{record: frames}`: how long each record plays (WaitFieldObject).
    frames: dict = field(default_factory=dict)
    #: The trigger groups a 3D object plays (USE_3D_OBJECT), a state other than 0 changing them, 0 putting them
    #: back.
    objects: list = field(default_factory=list)

    def record_frames(self, record: int) -> int:
        return int(self.frames.get(record, 0))

    def object_frames(self, _number: int = 0, _state: int = 0) -> int:
        return max([len(self.tracks.get(g, ())) for g in self.objects] + [0]) if self.objects else 0


def _vram(page: int, u: float, v: float) -> tuple:
    """A classic texture corner (`page`, `u`, `v`) in the PlayStation's VRAM units (4 pixels to a unit)."""
    return (768 + 64 * page + u / 4.0, v)


def _records(raw: bytes) -> dict:
    """`{record: (canvas, frames' first corner, mode, count, 60ths a frame)}` for the records an event starts."""
    out = {}
    for index, mode in mc.started_records(raw):
        r = raw[20 * index:20 * index + 20]
        cx, cy, w, h, fx, fy = struct.unpack_from("<6h", r, 0)
        out[index] = ((cx, cy, w, h), (fx, fy), mode, r[15], r[17])
    return out


def _pixels(texture: bytes, x: int, y: int, w: int, h: int) -> Optional[bytes]:
    """A rectangle of the classic texture in VRAM units, as its pixels' palette indices, or None off it."""
    out = bytearray()
    for row in range(y, y + h):
        for unit in range(x, x + w):
            page = (unit - 768) // 64
            if not (0 <= page < 4) or not (0 <= row < 256):
                return None
            at = (256 * page + row) * 256 + ((unit - 768) % 64) * 4
            out += texture[at:at + 4]
    return bytes(out)


def _frame_corner(first: tuple, width: int, height: int, k: int) -> tuple:
    """Where frame `k` of a record is: along from its first, then on in rows below (`map_scene.classic_animations`)."""
    fx, fy = first
    page_x = (fx - 768) % 64
    along = max(1, (64 - page_x) // max(1, width))
    if k < along:
        return (fx + k * width, fy)
    row, column = divmod(k - along, max(1, 64 // max(1, width)))
    return (fx - page_x + 2 + column * width, fy + (row + 1) * height)


def _away(records: dict, texture: Optional[bytes]) -> dict:
    """`{record: away}`: which of the records sharing a canvas change the door from how the map is read,
    which put it back."""
    by_canvas = {}
    for index, (canvas, _first, _mode, _count, _ticks) in sorted(records.items()):
        by_canvas.setdefault(canvas, []).append(index)
    out = {}
    for canvas, indexes in by_canvas.items():
        start = _pixels(texture, *canvas) if texture else None
        back = []
        for index in indexes:
            _canvas, first, mode, count, _ticks = records[index]
            last = 0 if mode in mc.ONCE_BACKWARD else max(0, count - 1)
            corner = _frame_corner(first, canvas[2], canvas[3], last)
            if start is not None and _pixels(texture, corner[0], corner[1], canvas[2], canvas[3]) == start:
                back.append(index)
        if not back:
            back = [i for i in indexes if records[i][2] in mc.ONCE_BACKWARD]
        if not back and len(indexes) > 1:
            back = indexes[1:]
        for index in indexes:
            out[index] = index not in back
    return out


def _centre(points) -> tuple:
    return tuple(sum(p[i] for p in points) / len(points) for i in range(3))


def read_doors(game_dir, number: int, sqlite_path=None, rows: Optional[dict] = None, mesh_file=None,
               anim_file=None, state: mc.State = mc.State(), classic_number: Optional[int] = None,
               records: Optional[bytes] = None) -> Doors:
    """
    Map `number`'s doors in its enhanced look (see the module's notes): its
    mesh (`mesh_file`, a mod's, else the game's), its trigger groups
    (`RefinedBgAnim`, `rows` a mod's over the game's) and their tracks
    (`anim_file`), against the classic look of `state`. A look copied there
    is another map's: `classic_number` that map, whose classic files its
    door records (`records`, 640 bytes: the copy's, `map_classic.
    animation_records`) were made for. An empty `Doors` where there are
    none, or a file can't be read.
    """
    game_dir = Path(game_dir)
    folder = game_dir / mc.MAP_FOLDER
    classic = int(classic_number if classic_number is not None else number)
    try:
        mesh = me.read_mesh(Path(mesh_file or me.mesh_path(game_dir, number)).read_bytes())
    except (OSError, me.EnhancedMapError):
        return Doors()
    found = mpk.table_rows(sqlite_path, mpk.ANIM_TABLE, number, (rows or {}).get(mpk.ANIM_TABLE))
    groups = sorted({int(f["Unknown8"]) for f in found.values()
                     if f.get("Unknown4") == TRIGGER and f.get("Unknown8") is not None})
    if not groups:
        return Doors()
    try:
        tracks = me.picture_tracks(Path(anim_file or me.anim_path(game_dir, number)).read_bytes())
    except (OSError, me.EnhancedMapError):
        tracks = {}
    polygons = [p for p in mesh.polygons() if p.textured and p.group in groups]
    out = Doors()
    counts = None
    for group in groups:
        track = tracks.get(group)
        if not track:
            # No track: its pictures in turn.
            if counts is None:
                counts = _picture_counts(game_dir, number, sqlite_path, rows)
            track = tuple(k for k in range(counts.get(group, 1)) for _tick in range(TICKS_A_FRAME))
        out.tracks[group] = tuple(track)
    # The classic look: its records (the copy's, where it brought its own), texture and polygons.
    try:
        sources = mc.read_gns(folder, classic).sources(state)
        if "texture_animations" not in sources:
            sources = mc.read_gns(folder, classic).sources(mc.State())
    except (OSError, mc.MapError):
        sources = {}
    raw = records
    if raw is None and "texture_animations" in sources:
        try:
            raw = mc.read_mesh((folder / sources["texture_animations"].file_name).read_bytes()).texture_animations
        except (OSError, mc.MapError):
            raw = None
    started = _records(raw or b"")
    if not started:
        out.objects = list(groups)
        return out
    try:
        texture = mc.read_texture((folder / sources["texture"].file_name).read_bytes()) if "texture" in sources \
            else None
    except (OSError, mc.MapError):
        texture = None
    try:
        classic_polygons = [p for p in mc.read_mesh((folder / sources["polygons"].file_name).read_bytes()).polygons
                            if p.textured and p.mesh == 0] if "polygons" in sources else []
    except (OSError, mc.MapError):
        classic_polygons = []
    by_source = {(p.kind, p.index): p for p in classic_polygons}
    canvases = sorted({r[0] for r in started.values()})
    # Each canvas's classic polygons, a corner of their texture in it.
    near_canvas = {}
    for canvas in canvases:
        cx, cy, w, h = canvas
        near_canvas[canvas] = [_centre(p.vertices) for p in classic_polygons
                               if any(cx <= _vram(p.page, u, v)[0] <= cx + w and cy <= v <= cy + h
                                      for u, v in p.uvs)]
    doors = {}
    for group in groups:
        own = [p for p in polygons if p.group == group]
        if not own:
            continue
        hits = {}
        for poly in own:
            source = by_source.get((poly.kind, poly.source)) if poly.source is not None else None
            if source is None:
                continue
            corners = [_vram(source.page, u, v) for u, v in source.uvs]
            for canvas in canvases:
                cx, cy, w, h = canvas
                if all(cx <= x <= cx + w and cy <= y <= cy + h for x, y in corners):
                    hits[canvas] = hits.get(canvas, 0) + 1
        if hits:
            canvas = max(sorted(hits), key=lambda c: hits[c])
        else:
            block = mesh.blocks[own[0].block]
            centres = [_centre([block.positions[c] for c in p.corners]) for p in own]
            nearest = []
            for candidate, points in near_canvas.items():
                if points:
                    nearest.append((min(sum((a - b) ** 2 for a, b in zip(x, y)) ** 0.5
                                        for x in centres for y in points), candidate))
            nearest.sort()
            if not nearest or nearest[0][0] > NEAR:
                continue
            canvas = nearest[0][1]
        door = doors.setdefault(canvas, Door(canvas))
        track = out.tracks[group]
        (door.solid if track[0] <= track[-1] else door.clear).append(group)
    out.doors = [doors[c] for c in sorted(doors)]
    which = {door.canvas: k for k, door in enumerate(out.doors)}
    away = _away(started, texture)
    for index, (canvas, _first, _mode, count, ticks) in started.items():
        out.frames[index] = count * ticks
        if canvas in which:
            out.records[index] = (which[canvas], away.get(index, True))
    return out


def _picture_counts(game_dir, number, sqlite_path, rows) -> dict:
    """`{group: how many colour pictures}` of the map's usual lighting; {} when it can't be read."""
    try:
        lightings = me.lightings(game_dir, number, sqlite_path, (rows or {}).get(mpk.TEXTURE_TABLE))
    except (OSError, ValueError):
        return {}
    pictures = lightings[0].pictures if lightings else {}
    return {group: max(1, len(entry.colour)) for group, entry in pictures.items() if entry and entry.colour}


def opens(doors: Optional[Doors], record: int, opcode: int = 0x55, state: int = 0) -> Optional[bool]:
    """
    Whether texture animation record `record` (0x55; a 3D object's `state`
    for 0x54) opens a door, its door then not drawn (True), or shuts one
    (False); None where it plays no door. A record that changes its door
    from how the map is read opens it where the door is drawn so (most),
    and shuts it where it isn't (049's).
    """
    if doors is None:
        return None
    if opcode == 0x54:
        return bool(state) if doors.objects else None
    if record not in doors.records:
        return None
    door, away = doors.records[record]
    return away if doors.doors[door].solid else not away


def _track_at(track: tuple, ticks: float, backward: bool = False) -> int:
    if not track:
        return 0
    k = min(len(track) - 1, max(0, int(ticks)))
    return track[len(track) - 1 - k] if backward else track[k]


def pictures_at(doors: Doors, started: list, frame: float) -> dict:
    """
    `{group: picture frame}` each trigger group shows at `frame`, the
    map's moving parts started as `started` says (`event_scripts.Timeline.
    objects`, `[(frame, opcode, number, state)]` in order): each its track's
    first until its door plays (see the module's notes).
    """
    out = {group: (track[0] if track else 0) for group, track in doors.tracks.items()}
    state = {}
    for when, opcode, number, value in started:
        if when > frame:
            break
        if opcode == 0x55 and number in doors.records:
            door, away = doors.records[number]
        elif opcode == 0x54 and doors.objects:
            door, away = None, bool(value)
        else:
            continue
        # Started again the way its door already is: nothing changes.
        if away != state.get(door, (False, 0))[0]:
            state[door] = (away, when)
    for door, (away, when) in state.items():
        ticks = (frame - when) * TICKS_A_SECOND / 60.0
        if door is None:
            for group in doors.objects:
                out[group] = _track_at(doors.tracks[group], ticks, backward=not away)
            continue
        found = doors.doors[door]
        both = bool(found.solid and found.clear)
        for group in found.solid + found.clear:
            track = doors.tracks[group]
            if not both:
                out[group] = _track_at(track, ticks, backward=not away)
            elif (group in found.solid) == away:
                out[group] = _track_at(track, ticks)
            else:
                out[group] = track[0] if away else track[-1]
    return out
