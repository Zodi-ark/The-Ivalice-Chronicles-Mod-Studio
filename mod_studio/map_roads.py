"""
A mod's own roads on the world map (Zodi, 26 October: "Roads to new
places", step 2 of his "real new places, built in steps").

**A road** is a folder of its own in a mod, `ModStudioRoads/<road>/`, holding
`road.json` (`road_text`): its name, the two places it joins (`From` and
`To`: one of the world map's places by its number, 0 to 46, as a quest's
start names one, or one of the mod's own places by its name), the turns it
takes between them (`Via`: points on the map's picture, in its pixels, 3840 x
2288), and its picture (`Picture`, its files' name, and `PictureAt`, where
its top left corner is on the map's picture). A modder never chooses a number
for anything a road adds. Mod Studio Framework (the helper, since 1.4.0,
`helper/ModStudioEventSetup/RoadFile.cs` reads this same file and says the
same problems) shows each one on the world map as a picture of the map's
layout of its own, copied from one of the game's road pictures as the world
map sets itself up (`MapRoads.cs`).

**This step is pictures only**: a mod's road is drawn where its file says,
under the places, as the game draws its own; the game doesn't travel it yet.
That is the next step, with the mod's place becoming somewhere the game
travels to (its cursor stop, its name). (1.5.0 travels a road between two of
the game's places; 1.7.0 one to a mod's own place too, the place then one of
the world map's.)

**(1.5.0) The walk**: `Walk`, the points Ramza's marker walks along the road
from its From to its To (`walk_points`: the drawn trail's curve every 60
pixels or so, each where his marker stands when his feet are on the trail,
`FOOT` below it; its first and last where he stands at the road's places,
the game's `Town` table's middles, `GAME_MARKERS`). The game walks its own
roads along its `MapRouteTable` rows; the helper gives a road between two of
the game's places rows of these points and a number of the game's past its
51 roads, so the game travels it as its own (`helper/.../Travel.cs`).

**A road's picture** is a texture of the mod's own with its part list, at the
game's paths in the mod, which the mod loader serves (as a town's own picture
is, `map_places`): `FFTIVC/data/enhanced/ui/ffto/worldmap/texture/<Picture>.tex`
and `.../textureparts/<Picture>.utexpt`, its part 1 the picture, drawn at its
own size. `trail_picture` draws one in the game's look (its 51 trails,
`ui_wm_route_all_uitx`: a pale, painted path 11 pixels wide, grained and
spotted, soft edges and round ends, a faint shadow below) along a smooth curve
through the road's places and turns, stopping short of a town's middle as the
game's do (60 pixels; 13 at a battle ground); `picture_files` makes its two
files; `write_road` writes them beside the file.

Nothing here imports Qt.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional, Union

from mod_studio import helper_json as hj
from mod_studio import map_places as mp

#: Where a mod keeps its roads, one folder each; the file each holds.
FOLDER = "ModStudioRoads"
FILE_NAME = "road.json"
FORMAT = "Mod Studio road"
VERSION = 1
#: The world map's places a road may join by number (a quest's start names them so: 0 to 46; 20 and 43 have none).
PLACES = 47
#: The most turns a road takes between its places (with its two places, 64 points).
MOST_VIA = 62
#: The largest picture a road has (its part 1's width and height).
MOST_PICTURE = 4096
#: (1.5.0) The most points a road's walk has (Ramza's marker walks them in order), and about how far apart Mod
#: Studio puts them (the game's own roads' are 40 to 80 pixels apart).
MOST_WALK, WALK_STEP = 64, 60
#: (1.5.0) Where Ramza's marker stands when his feet are on a trail: 3 pixels right of and 19 below it (the game's
#: battle grounds: his marker's place, the Town table's middle, against the middle of the place's piece, which his
#: feet stand on: from 10 left to 10 right and 10 to 29 below, their middles 3 and 19); at a mod's town, 11 right of
#: and 37 below its middle (the game's towns': -3 to 27 and 21 to 52, their middles 11 and 37).
FOOT, TOWN_FOOT = (3, 19), (11, 37)
#: The world map's places by number: (name, a town, its middle on the map's picture), as his layout
#: (worldmap_map_all.uib's Bases) puts their pieces; 20 and 43 have none.
GAME_PLACES = {
    0: ("Royal City of Lesalia", True, 1916, 753), 1: ("Riovanes Castle", True, 1378, 549),
    2: ("Eagrose Castle", True, 647, 806), 3: ("Lionel Castle", True, 1998, 1685),
    4: ("Limberry Castle", True, 2628, 1357), 5: ("Zeltennia Castle", True, 2774, 721),
    6: ("Magick City of Gariland", True, 1030, 1106), 7: ("Walled City of Yardrow", True, 1711, 454),
    8: ("Mining Town of Gollund", True, 1884, 946), 9: ("Merchant City of Dorter", True, 1592, 1147),
    10: ("Castled City of Zaland", True, 1896, 1437), 11: ("Clockwork City of Goug", True, 1220, 1714),
    12: ("Port City of Warjilis", True, 2337, 1896), 13: ("Free City of Bervenia", True, 2343, 827),
    14: ("Trade City of Sal Ghidos", True, 3036, 885), 15: ("Ziekden Fortress", True, 939, 772),
    16: ("Mullonde", True, 1063, 1361), 17: ("Brigands' Den", True, 797, 1252),
    18: ("Orbonne Monastery", True, 1774, 1240), 19: ("Golgollada Gallows", True, 1951, 1863),
    21: ("Fort Besselat", True, 2209, 1212), 22: ("Midlight's Deep", True, 2896, 1760),
    23: ("Nelveska Temple", True, 2613, 481), 24: ("Mandalia Plain", False, 750, 1045),
    25: ("Fovoham Windflats", False, 1130, 661), 26: ("The Siedge Weald", False, 1381, 1029),
    27: ("Mount Bervenia", False, 1484, 771), 28: ("Zeklaus Desert", False, 1655, 971),
    29: ("Lenalian Plateau", False, 1193, 886), 30: ("Tchigolith Fenlands", False, 1664, 1614),
    31: ("The Yuguewood", False, 1471, 421), 32: ("Araguay Woods", False, 1862, 1114),
    33: ("Grogh Heights", False, 1867, 618), 34: ("Beddha Sandwaste", False, 2312, 1069),
    35: ("Zeirchele Falls", False, 2031, 1210), 36: ("Dorvauldar Marsh", False, 2476, 1265),
    37: ("Balias Tor", False, 2102, 1522), 38: ("Dugeura Pass", False, 2155, 709),
    39: ("Balias Swale", False, 2238, 1732), 40: ("Finnath Creek", False, 2649, 904),
    41: ("Lake Poescas", False, 2792, 1221), 42: ("Mount Germinas", False, 2987, 1079),
    44: ("The Royal Military Akademy at Gariland", False, 1283, 1117), 45: ("Goug Lowtown", False, 1330, 1623),
    46: ("Lesalia Castle Postern", False, 2030, 698),
}
#: (1.5.0) Where Ramza's marker stands at each of the world map's places, as the game's Town table has it (its
#: middles, Unknown8 and UnknownC): where the screen's walk of a road ends (it walks him to its To's middle in place
#: of the walk's last point, and from the point after its first; most of the game's own walks, MapRouteTable, start
#: and end there too).
GAME_MARKERS = {
    0: (1943, 798), 1: (1393, 585), 2: (660, 849), 3: (2013, 1718), 4: (2634, 1407), 5: (2780, 769),
    6: (1054, 1131), 7: (1717, 481), 8: (1900, 970), 9: (1600, 1183), 10: (1910, 1470), 11: (1240, 1758),
    12: (2352, 1942), 13: (2340, 878), 14: (3035, 913), 15: (949, 809), 16: (1083, 1413), 17: (808, 1281),
    18: (1781, 1281), 19: (1964, 1884), 21: (2218, 1258), 22: (2902, 1810), 23: (2612, 510), 24: (758, 1068),
    25: (1139, 671), 26: (1379, 1056), 27: (1492, 792), 28: (1661, 993), 29: (1195, 901), 30: (1668, 1643),
    31: (1477, 435), 32: (1858, 1137), 33: (1872, 631), 34: (2309, 1091), 35: (2027, 1229), 36: (2471, 1286),
    37: (2112, 1539), 38: (2154, 723), 39: (2239, 1758), 40: (2648, 918), 41: (2782, 1240), 42: (2986, 1097),
    44: (1287, 1131), 45: (1335, 1643), 46: (2035, 716),
}

#: The game's trails, measured on ui_wm_route_all_uitx's 49 of them: 11 pixels wide (5.5 each side of its
#: middle, a hand's wobble of about half a pixel), 205 of 255 opaque, a soft edge of about 1.5 pixels and
#: softer round ends; a faint shadow below it (12 of 255, fading over about 5 pixels). Painted: soft blotches (about 2
#: pixels across) between a pale sand and a warm tan, a fine grain, a few darker marks; its colours spread
#: as the game's do (red about 190 to 250, its middle 225; green 158 to 229, 196; blue 125 to 185, 155).
#: They stop about 60 pixels short of a town's middle (the town's picture over it) and 13 of a battle
#: ground's.
HALF_WIDTH, WOBBLE, EDGE, END_EDGE, END_LENGTH = 5.5, 0.5, 1.5, 3.5, 8.0
ALPHA, SHADOW_ALPHA, SHADOW_DROP, SHADOW_REACH, SHADOW_SOFT = 205, 12, 2.0, 3.5, 5.0
SAND, TAN, MARK = (244, 223, 177), (208, 177, 134), (180, 149, 117)
BLOTCH, BLOTCHES, GRAIN, GRAINS, MARKS, MARK_FROM, MARK_SOFT = 1.8, 0.38, 0.6, 0.035, 1.1, 1.5, 0.9
TOWN_STOP, BATTLE_STOP = 60, 13
#: Room round the trail in its picture, and where in the sheet its part is (a clear pixel round it).
PICTURE_ROOM = 10


@dataclass
class Road:
    name: str
    start: Union[int, str]          # From: a place of the game's by its number, or one of the mod's by its name
    end: Union[int, str]            # To
    via: list = field(default_factory=list)   # [(x, y), ...] on the map's picture
    picture: str = ""               # its picture's files' name
    at: tuple = (0, 0)              # where its picture's top left corner is on the map's picture
    walk: list = field(default_factory=list)  # (1.5.0) [(x, y), ...]: where Ramza's marker walks, From to To

    @property
    def parts(self) -> str:
        """The part list's name the game makes the picture's parts ready by (the helper's `Parts`)."""
        return mp.PARTS_NAME + self.picture if self.picture else ""

    def to_json(self) -> dict:
        top = {"Format": FORMAT, "Version": VERSION, "Name": self.name, "From": self.start, "To": self.end,
               "Via": [list(p) for p in self.via], "Picture": self.picture, "PictureAt": list(self.at)}
        if self.walk:
            top["Walk"] = [list(p) for p in self.walk]
        return top


def road_text(road: Road) -> str:
    """The road's `road.json`, as the helper reads it."""
    return json.dumps(road.to_json(), indent=2, ensure_ascii=False) + "\n"


def picture_name(mod_id: str, folder: str) -> str:
    """The name Mod Studio gives a road's picture's files: of the mod and the road, apart from its places'
    (`msq_<mod>_road_<road>_uitx`)."""
    return mp.picture_name(mod_id, "road " + folder)


def _whole(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _point(value) -> bool:
    return (isinstance(value, list) and len(value) == 2 and all(_whole(v) for v in value)
            and 0 <= value[0] <= mp.MAP_WIDTH and 0 <= value[1] <= mp.MAP_HEIGHT)


def part_size(data: Optional[bytes]) -> Optional[tuple]:
    """A part list's part 1's width and height (the helper's `RoadFile.PartSize`), or None when it has none
    (not a part list, no part 1, or one of no size or over 4096)."""
    import struct
    if data is None or len(data) < 12:
        return None
    _path, table, count = struct.unpack_from("<III", data, 0)
    at = table + 20
    if count < 2 or table < 12 or at + 20 > len(data):
        return None
    x1, y1, x2, y2 = struct.unpack_from("<iiii", data, at + 4)
    width, height = x2 - x1, y2 - y1
    if not (0 < width <= MOST_PICTURE and 0 < height <= MOST_PICTURE):
        return None
    return width, height


def _end(top: dict, key: str, place_names, problems: list):
    """A road's From or To: a place of the game's by its number, or one of the mod's own by its name."""
    if not mp._has(top, key):
        problems.append(f"it has no {key} (the place it {'starts at' if key == 'From' else 'goes to'})")
        return None
    value = mp._get(top, key)
    if _whole(value) and value in GAME_PLACES:
        return value
    if isinstance(value, str) and value:
        if value in place_names:
            return value
        problems.append(f"its {key} names no place of the mod's ({value})")
        return None
    problems.append(f"its {key} is one of the world map's places by its number (0 to {PLACES - 1}, but not 20 or 43: "
                    f"they have none) or one of the mod's own places by its name, not {mp._raw(value)}")
    return None


def read_road_text(text: str, read_file: Callable[[str], Optional[bytes]], folder: str = "",
                   place_names=()) -> tuple:
    """
    (the road, problems) from a `road.json`'s text, checked as the helper
    checks it (`RoadFile.Read`); the road is None when anything is wrong.
    `read_file` gives a file of the mod's (its path from the mod's folder) or
    None; `place_names` are the mod's own places' names.
    """
    try:
        top = hj.loads(text)
    except ValueError as exc:
        return None, [f"its {FILE_NAME} isn't JSON ({exc})"]
    if not isinstance(top, dict):
        return None, [f"its {FILE_NAME} isn't a list of fields"]
    if hj.broken_text(top):
        return None, [f"its {FILE_NAME} {hj.BROKEN_TEXT}"]
    version = mp._get(top, "Version")
    if mp._get(top, "Format") != FORMAT or not _whole(version) or version != VERSION:
        return None, [f"its {FILE_NAME} isn't a \"{FORMAT}\" file of version {VERSION}"]
    problems = []
    name = mp._get(top, "Name")
    name = name if isinstance(name, str) and name else folder
    start = _end(top, "From", place_names, problems)
    end = _end(top, "To", place_names, problems)
    via = []
    if mp._has(top, "Via"):
        given = mp._get(top, "Via")
        if isinstance(given, list) and len(given) <= MOST_VIA and all(_point(p) for p in given):
            via = [tuple(p) for p in given]
        else:
            problems.append("its Via is the points it passes between its places on the world map, each two whole "
                            f"numbers from 0 to {mp.MAP_WIDTH} and 0 to {mp.MAP_HEIGHT}, at most {MOST_VIA} of them, "
                            f"not {mp._raw(given)}")
    picture = ""
    if not mp._has(top, "Picture"):
        problems.append("it has no Picture (its texture's files' name)")
    else:
        given = mp._get(top, "Picture")
        if mp.good_picture(given):
            picture = given
        else:
            problems.append("its Picture is its texture's files' name (small letters, digits and _, 1 to 64 of them), "
                            f"not {mp._raw(given)}")
    at = (0, 0)
    if not mp._has(top, "PictureAt"):
        problems.append("it has no PictureAt (where its texture's top left corner is on the world map)")
    else:
        given = mp._get(top, "PictureAt")
        if _point(given):
            at = tuple(given)
        else:
            problems.append("its PictureAt is where its texture's top left corner is on the world map, two whole "
                            f"numbers from 0 to {mp.MAP_WIDTH} and 0 to {mp.MAP_HEIGHT}, not {mp._raw(given)}")
    walk = []
    if mp._has(top, "Walk"):
        given = mp._get(top, "Walk")
        if isinstance(given, list) and 2 <= len(given) <= MOST_WALK and all(_point(p) for p in given):
            walk = [tuple(p) for p in given]
        else:
            problems.append("its Walk is the points Ramza walks from its From to its To on the world map, each two "
                            f"whole numbers from 0 to {mp.MAP_WIDTH} and 0 to {mp.MAP_HEIGHT}, 2 to {MOST_WALK} of "
                            f"them, not {mp._raw(given)}")
    if not problems:
        if start == end:
            problems.append("its From and To are the same place")
        else:
            texture = read_file(f"{mp.TEXTURE_FOLDER}/{picture}.tex")
            parts = read_file(f"{mp.PARTS_FOLDER}/{picture}.utexpt")
            if texture is None or parts is None:
                problems.append(f"its texture's files aren't in the mod ({mp.TEXTURE_FOLDER}/{picture}.tex and "
                                f"{mp.PARTS_FOLDER}/{picture}.utexpt)")
            elif part_size(parts) is None:
                problems.append(f"its texture's part list ({mp.PARTS_FOLDER}/{picture}.utexpt) has no part 1 "
                                f"(1 to {MOST_PICTURE} pixels wide and high)")
    if problems:
        return None, problems
    return Road(name, start, end, via, picture, at, walk), []


def read_mod_roads(mod_folder) -> list:
    """Every road of a mod, in its folders' order: (folder, the road or None, problems); a road named as an
    earlier one of the mod is left out (the helper's `ReadMod`). Its places are the mod's own, as read."""
    root = Path(mod_folder) / FOLDER
    out = []
    if not root.is_dir():
        return out
    place_names = {place.name for _, place, _ in mp.read_mod_places(mod_folder) if place is not None}

    def read_file(path: str):
        try:
            return (Path(mod_folder) / path).read_bytes()
        except OSError:
            return None

    names = set()
    for sub in sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.name):
        file = sub / FILE_NAME
        if not file.is_file():
            continue
        try:
            text = hj.read_text(file)
        except OSError as exc:
            out.append((sub.name, None, [f"it can't be read ({exc})"]))
            continue
        road, problems = read_road_text(text, read_file, sub.name, place_names)
        if road is not None and road.name in names:
            road, problems = None, [f"another of the mod's roads is named {road.name}"]
        if road is not None:
            names.add(road.name)
        out.append((sub.name, road, problems))
    return out


# =============================================================================
# The road's trail, and its picture in the game's look
# =============================================================================

def place_of(end: Union[int, str], places: dict) -> tuple:
    """(a town, its middle) of a road's place: one of the game's by number, or one of the mod's (`places`: its
    places by name, map_places.Place)."""
    if _whole(end):
        _name, town, x, y = GAME_PLACES[end]
        return town, (x, y)
    place = places[end]
    return place.town, (place.x, place.y)


def trail(road: Road, places: dict) -> list:
    """The road's points from its From's middle, through its turns, to its To's middle."""
    return [place_of(road.start, places)[1]] + [tuple(p) for p in road.via] + [place_of(road.end, places)[1]]


def marker_of(end: Union[int, str], places: dict) -> tuple:
    """(1.5.0) Where Ramza's marker stands at a road's place: one of the game's as its Town table has it, one of the
    mod's its middle moved as the game's towns' or battle grounds' are (TOWN_FOOT, FOOT)."""
    if _whole(end):
        return GAME_MARKERS[end]
    town, (x, y) = place_of(end, places)
    dx, dy = TOWN_FOOT if town else FOOT
    return (x + dx, y + dy)


def walk_points(road: Road, places: dict) -> list:
    """
    (1.5.0) Where Ramza's marker walks along the road, From to To: where he stands at its From, then the trail's
    curve (as `draw_road` draws it) every `WALK_STEP` pixels or so, each moved by FOOT (his feet on the trail),
    then where he stands at its To; at most MOST_WALK points (further apart on a long road).
    """
    curve = _curve(trail(road, places))
    lengths = [0.0]
    for a, b in zip(curve, curve[1:]):
        lengths.append(lengths[-1] + math.dist(a, b))
    total = lengths[-1]
    count = max(1, min(MOST_WALK - 1, int(round(total / WALK_STEP))))
    inner = []
    n = 1
    for k in range(1, count):
        s = total * k / count
        while n < len(lengths) - 1 and lengths[n] < s:
            n += 1
        a, b = curve[n - 1], curve[n]
        span = lengths[n] - lengths[n - 1]
        u = 0.0 if span == 0 else (s - lengths[n - 1]) / span
        x, y = a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u
        inner.append((int(round(x + FOOT[0])), int(round(y + FOOT[1]))))
    return [marker_of(road.start, places)] + inner + [marker_of(road.end, places)]


def _curve(points: list, step: float = 1.0) -> list:
    """A smooth curve through the points (centripetal Catmull-Rom), as points about `step` pixels apart."""
    pts = [(float(x), float(y)) for x, y in points]
    clean = [pts[0]]
    for p in pts[1:]:
        if math.dist(p, clean[-1]) > 1e-6:
            clean.append(p)
    pts = clean
    if len(pts) < 2:
        return pts
    ext = [(2 * pts[0][0] - pts[1][0], 2 * pts[0][1] - pts[1][1])] + pts + \
          [(2 * pts[-1][0] - pts[-2][0], 2 * pts[-1][1] - pts[-2][1])]
    out = [pts[0]]
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        t0 = 0.0
        t1 = t0 + max(math.dist(p0, p1), 1e-6) ** 0.5
        t2 = t1 + max(math.dist(p1, p2), 1e-6) ** 0.5
        t3 = t2 + max(math.dist(p2, p3), 1e-6) ** 0.5
        steps = max(2, int(math.dist(p1, p2) / step))
        for k in range(1, steps + 1):
            t = t1 + (t2 - t1) * k / steps

            def lerp(a, b, ta, tb):
                if tb - ta < 1e-9:
                    return a
                u = (t - ta) / (tb - ta)
                return (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u)
            a1, a2, a3 = lerp(p0, p1, t0, t1), lerp(p1, p2, t1, t2), lerp(p2, p3, t2, t3)
            b1, b2 = lerp(a1, a2, t0, t2), lerp(a2, a3, t1, t3)
            out.append(lerp(b1, b2, t1, t2))
    return out


def _cut(curve: list, start: float, end: float) -> list:
    """The curve without its first `start` and last `end` pixels (along it)."""
    lengths = [0.0]
    for a, b in zip(curve, curve[1:]):
        lengths.append(lengths[-1] + math.dist(a, b))
    total = lengths[-1]
    if start + end >= total - 2:
        raise ValueError(f"a road of {total:.0f} pixels is too short to draw between its places (a town's texture "
                         f"covers {TOWN_STOP} pixels of it, a battle ground's {BATTLE_STOP})")

    def at(s: float):
        for n in range(1, len(lengths)):
            if lengths[n] >= s:
                a, b = curve[n - 1], curve[n]
                span = lengths[n] - lengths[n - 1]
                u = 0.0 if span == 0 else (s - lengths[n - 1]) / span
                return (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u)
        return curve[-1]
    inner = [p for p, s in zip(curve, lengths) if start < s < total - end]
    return [at(start)] + inner + [at(total - end)]


def _field(width: int, height: int, sigma: float, rng):
    """Smooth noise (white noise blurred by a Gaussian of `sigma` pixels), its spread 1."""
    import numpy as np
    reach = int(3 * sigma) + 1
    kernel = np.exp(-0.5 * (np.arange(-reach, reach + 1) / sigma) ** 2)
    kernel /= kernel.sum()
    noise = rng.standard_normal((height + 2 * reach, width + 2 * reach))
    noise = np.apply_along_axis(lambda v: np.convolve(v, kernel, mode="same"), 0, noise)
    noise = np.apply_along_axis(lambda v: np.convolve(v, kernel, mode="same"), 1, noise)
    noise = noise[reach:reach + height, reach:reach + width]
    return noise / max(float(noise.std()), 1e-9)


def trail_picture(points: list, start_town: bool, end_town: bool, seed: str = "") -> tuple:
    """
    A road's picture in the game's look, along a smooth curve through `points` (on the map's picture, from its
    From's middle to its To's), stopping short of each place as the game's trails do (a town's 60 pixels, a
    battle ground's 13). (the picture, a PIL RGBA image; where its top left corner is on the map's picture).
    `seed` keeps its painted grain the same each time it is drawn.
    """
    import numpy as np
    from PIL import Image
    if len(points) < 2:
        raise ValueError("a road joins two places")
    curve = _cut(_curve(points), TOWN_STOP if start_town else BATTLE_STOP, TOWN_STOP if end_town else BATTLE_STOP)
    reach = HALF_WIDTH + SHADOW_REACH + SHADOW_DROP + PICTURE_ROOM
    left = int(math.floor(min(x for x, _ in curve) - reach))
    top = int(math.floor(min(y for _, y in curve) - reach))
    right = int(math.ceil(max(x for x, _ in curve) + reach))
    bottom = int(math.ceil(max(y for _, y in curve) + reach))
    width, height = right - left, bottom - top
    lengths = [0.0]
    for a, b in zip(curve, curve[1:]):
        lengths.append(lengths[-1] + math.dist(a, b))
    total = lengths[-1]
    far = 1e9
    near = np.full((height, width), far)       # distance to the trail
    along = np.zeros((height, width))          # how far along the trail its nearest point is
    shade = np.full((height, width), far)      # distance to the trail moved down by its shadow's drop
    yy, xx = np.mgrid[0:height, 0:width]
    px, py = xx + left + 0.5, yy + top + 0.5
    pad = int(reach) + 2
    for n, (a, b) in enumerate(zip(curve, curve[1:])):
        x0 = max(0, int(min(a[0], b[0])) - left - pad)
        x1 = min(width, int(max(a[0], b[0])) - left + pad)
        y0 = max(0, int(min(a[1], b[1])) - top - pad)
        y1 = min(height, int(max(a[1], b[1]) + SHADOW_DROP) - top + pad)
        if x0 >= x1 or y0 >= y1:
            continue
        sx, sy = px[y0:y1, x0:x1], py[y0:y1, x0:x1]
        dx, dy = b[0] - a[0], b[1] - a[1]
        span = dx * dx + dy * dy
        for drop, target in ((0.0, near), (SHADOW_DROP, shade)):
            ay = a[1] + drop
            u = np.zeros_like(sx) if span == 0 else np.clip(((sx - a[0]) * dx + (sy - ay) * dy) / span, 0, 1)
            d = np.hypot(sx - (a[0] + u * dx), sy - (ay + u * dy))
            window = target[y0:y1, x0:x1]
            closer = d < window
            window[closer] = d[closer]
            if drop == 0.0:
                part = along[y0:y1, x0:x1]
                part[closer] = (lengths[n] + u * math.sqrt(span))[closer]
    rng = np.random.default_rng(int.from_bytes(hashlib.sha256(seed.encode("utf-8")).digest()[:8], "little"))
    wobble = rng.uniform(-1.0, 1.0, int(total / 12) + 3)
    w = along / 12
    w0 = np.clip(w.astype(int), 0, len(wobble) - 2)
    fw = np.clip(w - w0, 0, 1)
    half = HALF_WIDTH + WOBBLE * (wobble[w0] + (wobble[w0 + 1] - wobble[w0]) * fw * fw * (3 - 2 * fw))
    from_end = np.clip(np.minimum(along, total - along) / END_LENGTH, 0, 1)
    soft = END_EDGE + (EDGE - END_EDGE) * from_end * from_end * (3 - 2 * from_end)
    alpha = ALPHA * np.clip((half + soft / 2 - near) / soft, 0, 1)
    shadow = SHADOW_ALPHA * np.clip((HALF_WIDTH + SHADOW_REACH - shade) / SHADOW_SOFT, 0, 1)
    tan = np.clip(0.5 + BLOTCHES * _field(width, height, BLOTCH, rng), 0, 1)
    grain = GRAINS * _field(width, height, GRAIN, rng)
    marks = np.clip((_field(width, height, MARKS, rng) - MARK_FROM) / MARK_SOFT, 0, 1)
    rgb = np.empty((height, width, 3))
    for c in range(3):
        sand = (SAND[c] * (1 - tan) + TAN[c] * tan) * (1 + grain)
        rgb[:, :, c] = sand * (1 - marks) + MARK[c] * marks
    painted = alpha > 0.5
    out = np.zeros((height, width, 4), dtype=np.uint8)
    out[:, :, :3] = np.where(painted[:, :, None], np.clip(rgb, 0, 255), 0).astype(np.uint8)
    out[:, :, 3] = np.clip(np.where(painted, alpha, shadow), 0, 255).astype(np.uint8)
    # Kept on the map's picture: what falls past its edges is cut off (a road along an edge).
    x0, y0 = max(0, -left), max(0, -top)
    x1, y1 = min(width, mp.MAP_WIDTH - left), min(height, mp.MAP_HEIGHT - top)
    if x0 >= x1 or y0 >= y1:
        raise ValueError("a road off the world map can't be drawn")
    out = out[y0:y1, x0:x1]
    return Image.fromarray(np.ascontiguousarray(out), "RGBA"), (left + x0, top + y0)


def picture_files(picture, name: str) -> tuple:
    """A road's picture's two files from a picture (PIL, any size up to 4094 x 4094): its texture (Mod Studio's own
    writer, one RGBA picture) and its part list naming it at the game's path, the picture its part 1 with a clear
    pixel round it. (tex bytes, utexpt bytes)."""
    from PIL import Image

    from mod_studio import texture_data as td
    from mod_studio import uib
    image = picture.convert("RGBA")
    width, height = image.size
    if not (0 < width <= MOST_PICTURE - 2 and 0 < height <= MOST_PICTURE - 2):
        raise ValueError(f"a road's texture is at most {MOST_PICTURE - 2} x {MOST_PICTURE - 2}, not {width} x {height}")
    sheet = Image.new("RGBA", (width + 2, height + 2), (0, 0, 0, 0))
    sheet.paste(image, (1, 1))
    texture = f"ui/ffto/worldmap/texture/{name}.tex"
    parts = uib.part_list_file(texture, [("TexturePart", (0, 0, width + 2, height + 2)),
                                         ("Road", (1, 1, width + 1, height + 1))])
    return td.rgba_tex(sheet), parts


def draw_road(road: Road, places: dict) -> tuple:
    """A road's picture drawn by Mod Studio from its places and turns: (the picture, where its top left corner
    is), its grain the road's picture's name's."""
    start_town, _ = place_of(road.start, places)
    end_town, _ = place_of(road.end, places)
    return trail_picture(trail(road, places), start_town, end_town, road.picture)


def drawn_road(name: str, start, end, via: list, picture: str, places: dict) -> tuple:
    """A road whose picture Mod Studio draws (`draw_road`), its PictureAt where the picture falls and (1.5.0) its
    Walk along it (`walk_points`): (the road, the picture)."""
    road = Road(name, start, end, [tuple(p) for p in via], picture)
    image, at = draw_road(road, places)
    road.at = at
    road.walk = walk_points(road, places)
    return road, image


def write_road(mod_folder, folder: str, road: Road, picture=None) -> list:
    """
    Writes a road into `<mod_folder>/ModStudioRoads/<folder>/road.json`, and its picture (`picture`, a PIL
    image) as its two files at the game's paths in the mod. Returns the paths written.
    """
    if not isinstance(folder, str) or not folder or folder.strip() != folder or not all(
            c.isalnum() or c in " _-" for c in folder):
        raise ValueError(f"a road's folder is named as a quest's is: {folder!r}")
    written = []
    if picture is not None:
        if not road.picture:
            raise ValueError("a picture given for a road that names none")
        tex, parts = picture_files(picture, road.picture)
        for path, data in ((Path(mod_folder) / mp.TEXTURE_FOLDER / f"{road.picture}.tex", tex),
                           (Path(mod_folder) / mp.PARTS_FOLDER / f"{road.picture}.utexpt", parts)):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            written.append(path)
    root = Path(mod_folder) / FOLDER / folder
    root.mkdir(parents=True, exist_ok=True)
    path = root / FILE_NAME
    path.write_text(road_text(road), encoding="utf-8")
    written.append(path)
    return written
