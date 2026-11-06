"""
A mod's own places and roads as the Side Quests page makes and changes them
(Zodi, 28 October, "Side quest page": "a page in Mod Studio to make a side
quest and a new place by names"; its second part, his "A) Places and roads
made on the page", built from the mock-up he signed off: "Build it as
shown").

What a place and a road are in a mod is `map_places.py`'s and
`map_roads.py`'s: a folder `ModStudioPlaces/<place>/` holding `place.json`
(its name, a town or a battle ground, its middle on the world map's
picture, a town's texture: one of the game's 23 or its own, 172 x 172), and
a folder `ModStudioRoads/<road>/` holding `road.json` (the two places it
joins, the game's by number or the mod's by name, its turns, its texture and
where it lies, and the points Ramza walks along it), each texture of the
mod's own beside the game's world map textures. Mod Studio Framework
gives each place a number of its own as the game starts, travels each road
and draws both.

Here they are held while the mod is open: a place (`PlaceEdit`) without its
texture's files' name, which depends on the mod's id and is given at export
(`map_places.picture_name`); a town's own texture kept as a picture
(`texture`, a PNG of 172 x 172); a road (`RoadEdit`) as its places and turns
only: its texture and its walk are drawn by Mod Studio from them at export
(`map_roads.drawn_road`), so they always follow its places.

- **Names**, as a quest's (`helper_json.good_name`) with the apostrophe the
  game's own places have (Midlight's Deep); each place's folder its name
  without apostrophes; no name of one of the game's places.
- **Clear of the game's places** (`overlapping`, `free_spot`): a place's
  piece on the world map (a town's 172 x 172, a battle ground's 64 x 64) is
  kept off the game's places' pieces and the mod's other places', as test
  22's were.
- **What Mod Studio Framework would say** (`place_problems`,
  `road_problems`): each file as it would be written, read as the helper
  reads it, in its own words, and why a road can't be drawn.
- **Renamed and taken out** with what names them: the roads joining a
  place, and the quests' starts waiting there.
- **Written into a mod and read back** (`write_place`, `write_road`,
  `read_mod`): a town's own texture read back from the mod's `.tex`.
- **(1.17.0) A battle ground's own random battles** (`BattleEdit`, Zodi's
  list, his fifth, his choice "Its own battles"): each made as a quest's
  battle is, copied from one of the game's battles (its 16 units, Load and
  Save Formation off; its map; where the game starts the player's units in
  it, as the battle's deploy area), its units and its deploy area's squares
  changed as a quest battle's are (`quest_edits`' own ways), its map one of
  the game's or the mod's quest maps; how many of 100 arrivals start one.
- **(1.18.0) A town's own menu** (`TownMenu`, Zodi's list, his fifth, his
  choice "Its own"), ticked town by town ("Let the modder decide"): the game
  town whose art it shows (first the one whose texture the town shows, if
  it shows one of the game's towns'), its Outfitter's items (empty until
  picked, or a copy of its art town's as the mod has the game's shops,
  ItemShopsData: "copy of its look's town or nothing until picked"), and
  its Poachers' Den, ticked. Its tavern tells the quests' rumors naming it.
- **(1.21.0) A dungeon** (`FloorEdit`, Zodi's list, his seventh: a place
  like Midlight's Deep), drawn as a town is: its floors, the list choosing
  it shows, each its name and words, the quest flag it waits for (his
  choice: "each floor waiting for a quest flag the modder picks, or showing
  from the start if none is picked") and its random battles (his choice: "a
  few random battles per floor"), made and changed as a battle ground's
  are, each naming its floor (`BattleEdit.floor`). (1.23.0) Its art, its
  list's and its location info's (Zodi's choice after test 49, "Its own
  art"): one of the game's places' (Midlight's Deep's until another is
  picked) or its own, made from an image as a town's menu's own art is.

Nothing here imports Qt; Pillow is imported where it is used.
"""
from __future__ import annotations

import copy
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

from mod_studio import constants as c
from mod_studio import entd
from mod_studio import helper_json as hj
from mod_studio import map_places as mp
from mod_studio import map_roads as mr
from mod_studio import quest_edits as qx
from mod_studio import side_quests as sq

#: A place's own piece on the world map, about its middle: a town's 172 x 172, a battle ground's 64 x 64 (the
#: layout's Base and Point pieces, `map_places.overlaps`).
TOWN_SIZE, BATTLE_SIZE = 172, 64
#: A new town's texture until one is chosen: one of the game's (the mock-up's "Town texture 19").
DEFAULT_ICON = "19"
#: How far apart `free_spot` tries places, in the world map's pixels.
SPOT_STEP = 8


# =============================================================================
# Names
# =============================================================================

def good_name(name) -> bool:
    """A place's or a road's name: letters, digits, spaces, apostrophes, underscores and hyphens, 1 to 64 of them,
    with no space at either end (a quest's name, `helper_json.good_name`, with the apostrophe of the game's own
    places' names: Midlight's Deep)."""
    return isinstance(name, str) and hj.good_name(name.replace("'", "x"))


def folder_for(name: str) -> str:
    """The folder a place or a road is written in: its name without apostrophes (a folder's name is letters,
    digits, spaces, underscores and hyphens, as a quest's)."""
    return " ".join(name.replace("'", "").split()) or "Place"


def free_name(wanted: str, taken) -> str:
    """`wanted`, or it numbered past the names `taken` ("Hidden Grove 2"), as a name may be (`good_name`)."""
    stem = " ".join("".join(ch if good_name(ch) else " " for ch in wanted).split())[:58] or "New"
    lowered = {folder_for(t).lower() for t in taken}
    if folder_for(stem).lower() not in lowered:
        return stem
    n = 2
    while folder_for(f"{stem} {n}").lower() in lowered:
        n += 1
    return f"{stem} {n}"


def game_place_named(name: str) -> Optional[int]:
    """The number of the game's place named `name` (whatever its case), or None."""
    wanted = name.strip().lower()
    return next((number for number, (said, *_rest) in mr.GAME_PLACES.items() if said.lower() == wanted), None)


# =============================================================================
# A place and a road
# =============================================================================

@dataclass
class BattleEdit:
    """(1.17.0) One of a battle ground's own random battles as the page has it: its name, its 16 units (`units`, 640
    bytes, as the game's battle files hold a battle; or, read from a file naming one, one of the game's battles as it
    is, `game_units`), its map (one of the game's by number, or one of the mod's quest maps by name; None until one is
    given), where the player's units start (`deploy`: one `side_quests.DeployArea`), the story's progress it waits for
    (variable 110 at least `story`; None, from the start), and the game's battle it was copied from (for its card)."""
    name: str
    units: bytes = b""
    game_units: int = 0
    map: object = None
    deploy: list = field(default_factory=list)
    story: Optional[int] = None
    copied_from: int = 0
    floor: str = ""                 # (1.21.0) a dungeon's battle: its floor's name ("": a battle ground's)


@dataclass
class FloorEdit:
    """(1.21.0) One of a dungeon's floors as the page has it: its name, its words (the Deep's list shows a floor's), and
    the quest flag it waits for (one of the mod's quests by its folder, and that quest's flag; both "": listed from
    the start). Its battles are the place's naming it. (1.24.0) Or `won`: listed once the floor before it is won (the
    first floor never)."""
    name: str
    description: str = ""
    quest: str = ""
    flag: str = ""
    won: bool = False


@dataclass
class PlaceEdit:
    """One of the mod's own places as the page has it: its folder, its name, a town or a battle ground, its middle
    on the world map's picture (3840 x 2288), and a town's texture: one of the game's (`icon`, one of
    `map_places.ICONS`) or its own (`texture`: 172 x 172, as a PNG; `texture_from`, the file it was made from, for
    the card); (1.16.0) its description, what the world map's location info shows under its name, or ""; (1.17.0) a
    battle ground's own random battles (`battles`, `BattleEdit`) and how many of 100 arrivals start one (`chance`);
    (1.18.0) a town's own menu (`menu`, `map_places.TownMenu`; None: no settlement to enter), and (1.19.0) its
    menu's own art (`art`: 680 x 452, as a PNG; `art_from`, the file it was made from; none: the game town's by
    `menu.art`); (1.20.0) a town darkened once one of the mod's quests' flags is set (`darkened`,
    `map_places.PlaceDarkened`; None: never). A town keeps its battles and a battle ground its menu and its darkening
    while its kind is changed back and forth: each is written for its kind only. (1.21.0) A dungeon (`dungeon`, drawn
    as a town is: `town` too) has its floors (`floors`, `FloorEdit`), its battles each naming its floor; a battle
    ground's battles name none; (1.23.0) and its art: one of the game's places' (`dungeon_art`, by its number:
    `map_places.good_art_place`) or its own (`dungeon_own_art`: 680 x 452, as a PNG; `dungeon_own_art_from`, the
    file it was made from), kept apart from a town's menu's."""
    folder: str
    name: str
    town: bool
    x: int
    y: int
    icon: str = ""
    texture: bytes = b""
    texture_from: str = ""
    description: str = ""
    chance: int = 0
    battles: list = field(default_factory=list)
    menu: Optional[mp.TownMenu] = None
    art: bytes = b""
    art_from: str = ""
    darkened: Optional[mp.PlaceDarkened] = None
    dungeon: bool = False
    floors: list = field(default_factory=list)
    dungeon_art: int = mp.DEEP_PLACE
    dungeon_own_art: bytes = b""
    dungeon_own_art_from: str = ""

    def place(self, picture: str = "", art: str = "") -> mp.Place:
        """The place as `map_places` writes it, a town's own texture's files named `picture`; (1.17.0) a battle
        ground's random battles naming their units' files as `battle_files` names them; (1.18.0) a town's menu, its
        own art's files named `art` when it has its own (`self.art`; else the game town's by `menu.art`); (1.23.0) a
        dungeon's own art's files named `art` too (else the game place's by `dungeon_art`)."""
        files = battle_files(self)

        def written(b: BattleEdit) -> mp.PlaceBattle:
            return mp.PlaceBattle(b.name, files[b.name] if b.units else b.game_units, b.map, copy.deepcopy(b.deploy),
                                  b.story)
        if not self.town:
            battles = [written(b) for b in self.battles if not b.floor]
            return mp.Place(self.name, False, self.x, self.y, description=self.description,
                            chance=self.chance if battles else 0, battles=battles)
        if self.dungeon:
            # (1.21.0) A dungeon: drawn as a town is, its floors (each its battles) its list.
            floors = [mp.PlaceFloor(f.name, f.description,
                                    mp.PlaceDarkened(f.quest, f.flag) if f.quest and f.flag and not f.won else None,
                                    [written(b) for b in self.battles if b.floor == f.name], f.won)
                      for f in self.floors]
            look = {"picture": picture} if self.texture else {"icon": self.icon or DEFAULT_ICON}
            shown = (art or PREVIEW_ART) if self.dungeon_own_art else self.dungeon_art
            return mp.Place(self.name, True, self.x, self.y, description=self.description, floors=floors, dungeon=True,
                            dungeon_art=shown, **look)
        menu = copy.deepcopy(self.menu)
        if menu is not None and self.art:
            menu.art = art or PREVIEW_ART
        darkened = copy.deepcopy(self.darkened)
        if self.texture:
            return mp.Place(self.name, True, self.x, self.y, picture=picture, description=self.description, menu=menu,
                            darkened=darkened)
        return mp.Place(self.name, True, self.x, self.y, icon=self.icon or DEFAULT_ICON, description=self.description,
                        menu=menu, darkened=darkened)

    def size(self) -> int:
        return TOWN_SIZE if self.town else BATTLE_SIZE


@dataclass
class RoadEdit:
    """One of the mod's own roads as the page has it: its folder, its name, the places it joins (`start` and `end`:
    one of the game's by its number, or one of the mod's by its name) and its turns between them (`via`, points on
    the world map's picture). Its texture and walk are drawn from them (`draw`)."""
    folder: str
    name: str
    start: Union[int, str]
    end: Union[int, str]
    via: list = field(default_factory=list)


def copied(places: dict, roads: dict) -> tuple:
    """Copies of the page's places and roads, for an export running beside the page."""
    return copy.deepcopy(places), copy.deepcopy(roads)


def new_place(name: str, town: bool, x: int, y: int, dungeon: bool = False) -> PlaceEdit:
    """A new place of the mod's: a town (or (1.21.0) a dungeon, drawn as a town is) shows one of the game's town
    textures until its own is chosen."""
    town = bool(town or dungeon)
    return PlaceEdit(folder_for(name), name, town, int(x), int(y), icon=DEFAULT_ICON if town else "",
                     dungeon=bool(dungeon))


#: (1.21.0) A place's kinds, as the page names them: a town, a battle ground, a dungeon.
TOWN, GROUND, DUNGEON = "town", "ground", "dungeon"


def kind_of(place: PlaceEdit) -> str:
    return DUNGEON if place.dungeon else TOWN if place.town else GROUND


def set_kind(place: PlaceEdit, kind: str) -> None:
    """(1.21.0) A place made a town, a battle ground or a dungeon; what each has is kept, written for its kind only (a
    town and a dungeon show one of the game's town textures until their own is chosen)."""
    place.dungeon = kind == DUNGEON
    place.town = kind in (TOWN, DUNGEON)
    if place.town and not place.texture and not place.icon:
        place.icon = DEFAULT_ICON


def new_road(name: str, start, end, via=()) -> RoadEdit:
    return RoadEdit(folder_for(name), name, start, end, [tuple(p) for p in via])


def place_named(places: dict, name: str) -> Optional[PlaceEdit]:
    return next((p for p in places.values() if p.name == name), None)


def mp_places(places: dict) -> dict:
    """`{name: map_places.Place}` of the page's places: what `map_roads` draws a road between."""
    return {p.name: p.place("drawn") for p in places.values()}


def where(end, places: dict) -> Optional[tuple]:
    """(a town, x, y) of a road's place: one of the game's by number or one of the mod's by name; None for a name
    the mod hasn't."""
    if isinstance(end, int) and not isinstance(end, bool):
        found = mr.GAME_PLACES.get(end)
        return (found[1], found[2], found[3]) if found else None
    place = place_named(places, end)
    return (place.town, place.x, place.y) if place is not None else None


def roads_at(roads: dict, name: str) -> list:
    """The roads joining the mod's place named `name`, in their folders' order."""
    return [r for _, r in sorted(roads.items()) if name in (r.start, r.end)]


def other_end(road: RoadEdit, name: str):
    return road.end if road.start == name else road.start


# =============================================================================
# Clear of the game's places
# =============================================================================

def game_pieces() -> list:
    """The game's places' pieces on the world map, (name, x, y, width, height): a town's 172 x 172 about its middle
    (Gariland's Base01 is at 944, 1020, its middle 1030, 1106), a battle ground's 64 x 64."""
    out = []
    for name, town, x, y in mr.GAME_PLACES.values():
        size = TOWN_SIZE if town else BATTLE_SIZE
        out.append((name, x - size // 2, y - size // 2, size, size))
    return out


def pieces_besides(places: dict, folder: str) -> list:
    """The pieces a place must keep clear of: the game's places' and the mod's other places'."""
    out = game_pieces()
    for other in places.values():
        if other.folder != folder:
            size = other.size()
            out.append((other.name, other.x - size // 2, other.y - size // 2, size, size))
    return out


def overlapping(place: PlaceEdit, places: dict, x: Optional[int] = None, y: Optional[int] = None) -> list:
    """The names of the game's places and the mod's other places whose pieces the place's own would overlap
    (at x, y when given)."""
    at = mp.Place(place.name, place.town, place.x if x is None else int(x), place.y if y is None else int(y))
    return mp.overlaps(at, pieces_besides(places, place.folder))


def on_map(town: bool, x: int, y: int) -> bool:
    """A place's piece wholly on the world map's picture."""
    half = (TOWN_SIZE if town else BATTLE_SIZE) // 2
    return half <= x <= mp.MAP_WIDTH - half and half <= y <= mp.MAP_HEIGHT - half


def free_spot(town: bool, x: int, y: int, places: dict, folder: str = "") -> tuple:
    """The spot nearest (x, y) where a place's piece is on the map and clear of every other place's: tried in rings
    `SPOT_STEP` pixels apart. (x, y) itself when it is."""
    pieces = pieces_besides(places, folder)
    half = (TOWN_SIZE if town else BATTLE_SIZE) // 2
    x = min(max(int(x), half), mp.MAP_WIDTH - half)
    y = min(max(int(y), half), mp.MAP_HEIGHT - half)

    def clear(px: int, py: int) -> bool:
        return on_map(town, px, py) and not mp.overlaps(mp.Place("", town, px, py), pieces)

    if clear(x, y):
        return x, y
    # Rings of spots a step apart, outwards; once a clear one is found, on until no ring can hold a nearer one
    # (a ring's corners are farther than its sides).
    best, best_distance = None, None
    for ring in range(1, 2 + max(mp.MAP_WIDTH, mp.MAP_HEIGHT) // SPOT_STEP):
        reach = ring * SPOT_STEP
        if best_distance is not None and reach > best_distance:
            break
        found = []
        for dx in range(-reach, reach + 1, SPOT_STEP):
            for dy in (-reach, reach):
                found.append((x + dx, y + dy))
        for dy in range(-reach + SPOT_STEP, reach, SPOT_STEP):
            for dx in (-reach, reach):
                found.append((x + dx, y + dy))
        for spot in found:
            distance = ((spot[0] - x) ** 2 + (spot[1] - y) ** 2) ** 0.5
            if (best_distance is None or (distance, spot) < (best_distance, best)) and clear(*spot):
                best, best_distance = spot, distance
    return best if best is not None else (x, y)


# =============================================================================
# A town's own texture
# =============================================================================

def texture_png(image) -> bytes:
    """A town's own texture from any picture (PIL): fitted into 172 x 172 keeping its proportions, in the middle of
    a clear square, as a PNG."""
    from PIL import Image
    picture = image.convert("RGBA")
    width, height = picture.size
    if width <= 0 or height <= 0:
        raise ValueError("the picture is empty")
    side = mp.PICTURE_SIZE[0]
    scale = min(side / width, side / height)
    fitted = picture.resize((max(1, round(width * scale)), max(1, round(height * scale))), Image.LANCZOS)
    square = Image.new("RGBA", mp.PICTURE_SIZE, (0, 0, 0, 0))
    square.paste(fitted, ((side - fitted.width) // 2, (side - fitted.height) // 2))
    out = io.BytesIO()
    square.save(out, "PNG")
    return out.getvalue()


def art_png(image) -> bytes:
    """(1.19.0) A town's menu's own art from any picture (PIL): fitted into 680 x 452 keeping its proportions, in the
    middle of a clear picture, as a PNG."""
    from PIL import Image
    picture = image.convert("RGBA")
    width, height = picture.size
    if width <= 0 or height <= 0:
        raise ValueError("the picture is empty")
    wide, high = mp.ART_SIZE
    scale = min(wide / width, high / height)
    fitted = picture.resize((max(1, round(width * scale)), max(1, round(height * scale))), Image.LANCZOS)
    art = Image.new("RGBA", mp.ART_SIZE, (0, 0, 0, 0))
    art.paste(fitted, ((wide - fitted.width) // 2, (high - fitted.height) // 2))
    out = io.BytesIO()
    art.save(out, "PNG")
    return out.getvalue()


def art_from_file(path) -> bytes:
    """(1.19.0) A town's menu's own art from an image file (any Pillow reads)."""
    from PIL import Image
    with Image.open(path) as image:
        image.load()
        return art_png(image)


def texture_from_file(path) -> bytes:
    """A town's own texture from an image file (any Pillow reads)."""
    from PIL import Image
    with Image.open(path) as image:
        image.load()
        return texture_png(image)


def texture_image(texture: bytes):
    """A town's own texture (PNG bytes) as a PIL picture."""
    from PIL import Image
    image = Image.open(io.BytesIO(texture))
    image.load()
    return image.convert("RGBA")


# =============================================================================
# What Mod Studio Framework would say
# =============================================================================

PREVIEW_PICTURE = "msq_page_preview_uitx"
#: (1.19.0) A menu's own art's files' name as the page checks a place (Export names them for the mod and the place).
PREVIEW_ART = "msq_page_preview__art_uitx"


def place_problems(place: PlaceEdit, map_names=None) -> list:
    """What Mod Studio Framework would say of the place's file as Export writes it (`map_places.read_place_text`,
    its own words): none for a place the page made but (1.17.0) a random battle without a map, without a square to
    start on, or on a quest map the mod hasn't (`map_names`, the mod's quest maps' names; None: any its battles name)."""
    written = place.place(PREVIEW_PICTURE)
    named = battle_files(place)
    files = {named[b.name]: b.units for b in place.battles if b.units}
    names = ({b.map for b in place.battles if isinstance(b.map, str)} if map_names is None else set(map_names))

    def read(name: str) -> bytes:
        if name not in files:
            raise OSError(f"no file {name}")
        return files[name]
    _read, said = mp.read_place_text(mp.place_text(written), lambda _path: True, place.folder, read, names)
    return list(said)


def set_description(place: PlaceEdit, words: str) -> None:
    """(1.16.0) A place's description as it is typed: without spaces at either end, its line breaks as the game's
    own descriptions have them (none, or one)."""
    place.description = words.replace("\r\n", "\n").replace("\r", "\n").strip()


def place_warnings(place: PlaceEdit, places: dict) -> list:
    """Where the place stands, in Mod Studio's words: its piece off the world map, or over another place's (the
    game's places' pieces and the mod's other places')."""
    out = []
    if not on_map(place.town, place.x, place.y):
        out.append(OFF_THE_MAP.format(name=place.name))
    over = overlapping(place, places)
    if over:
        out.append(OVER.format(name=place.name, others=", ".join(over)))
    return out


# =============================================================================
# (1.17.0) A battle ground's own random battles
# =============================================================================

#: How many of 100 arrivals start a battle ground's first random battle until changed: about the game's own (31 of
#: 100, its tables' 30 a roll of 0 to 99 at most).
DEFAULT_CHANCE = 30
#: A random battle the page makes from one of the game's: its name until it is given one.
NEW_BATTLE = "Battle"


def battle_files(place: PlaceEdit) -> dict:
    """`{battle: file}`: each random battle of its own units' file in the place's folder (`quest_edits.file_name`: its
    name's letters and digits, `.entd`, numbered past the battles' before it)."""
    out, taken = {}, []
    for battle in place.battles:
        if battle.units:
            out[battle.name] = qx.file_name(battle.name, mp.UNITS_ENDING, taken)
            taken.append(out[battle.name])
    return out


def battle_named(place: PlaceEdit, name: str) -> Optional[BattleEdit]:
    return next((b for b in place.battles if b.name == name), None)


def _battle(place: PlaceEdit, name: str) -> BattleEdit:
    found = battle_named(place, name)
    if found is None:
        raise ValueError(f"{place.name} has no random battle named {name}")
    return found


def game_battle_map(game_dir, battle: int) -> Optional[int]:
    """The map the game fights its battle `battle` on, first (`battle_maps`: its scenarios' first, then its random
    battles' places'), or None."""
    from mod_studio import battle_maps as bm
    try:
        on = bm.read_battle_maps(game_dir).of(battle)
    except (OSError, bm.BattleMapError):
        return None
    return on[0] if on else None


def game_battle_squad(game_dir, game, battle: int, map_number: Optional[int]) -> Optional[int]:
    """The squad the game starts its battle `battle` on, on `map_number`: its random battles' place's road row's
    (WLDCORE.BIN, its squad byte plus 0x200, the first row of that map naming the battle), else the first event of the
    game's that fights it (its setup's DeployArea1); None without either."""
    from mod_studio import battle_maps as bm
    try:
        world = (Path(game_dir) / bm.RANDOM_FILE).read_bytes()
    except (OSError, TypeError):
        world = b""
    for at in range(bm.RANDOM_AT, bm.RANDOM_END, bm.RANDOM_BYTES):
        row = world[at:at + bm.RANDOM_BYTES]
        # A battle past 255 is in no row (its battles are bytes).
        if len(row) == bm.RANDOM_BYTES and row[22] == map_number and 0 <= battle <= 255 and battle in row[14:22]:
            return row[1] + 0x200
    event = game.battle_event(battle) if game is not None else None
    number = game.setup(event).get("DeployArea1") if event is not None else None
    return number if isinstance(number, int) and number > 0 else None


def add_battle(place: PlaceEdit, game, battle: int, squads: bytes = b"", name: str = "", floor: str = "") -> str:
    """
    (1.17.0) A random battle of the battle ground's own, a copy of the game's
    battle `battle` (`game`: `quest_edits.Game`): its 16 units (`quest_edits.
    own_units`: each built from its own fields), the map the game fights it
    on (`game_battle_map`), and as its deploy area where the game starts the
    player's units in it (`game_battle_squad`, from the program's `squads`;
    else an area without squares yet). The first one starts on
    `DEFAULT_CHANCE` of 100 arrivals. Returns its name (`name`, or the
    battle's own name numbered past the place's battles'). Raises ValueError
    for a town, or a battle ground with 8 already. (1.21.0) A dungeon's is
    one of its floor `floor`'s (8 at the most each).
    """
    if place.town and not place.dungeon:
        raise ValueError(f"{place.name} is a town: random battles are a battle ground's")
    # (1.21.0) A dungeon's battle is one of a floor's.
    if place.dungeon and floor_named(place, floor) is None:
        raise ValueError(f"{place.name} has no floor named {floor}")
    own = [b for b in place.battles if b.floor == (floor if place.dungeon else "")]
    if len(own) >= mp.MOST_BATTLES:
        raise ValueError(TOO_MANY_FLOOR_BATTLES if place.dungeon else TOO_MANY_BATTLES)
    block = game.battle(battle)
    if block is None:
        raise ValueError(f"the game's battle {battle} isn't in its files")
    chosen = qx.free_name(name or NEW_BATTLE, [b.name for b in place.battles])
    map_number = game_battle_map(game.folder, battle)
    number = game_battle_squad(game.folder, game, battle, map_number)
    from mod_studio import event_setup as su
    area = qx.area_of_squad(su.squad(squads, number)) if number and squads else None
    if not place.dungeon and not own and not place.chance:
        place.chance = DEFAULT_CHANCE
    place.battles.append(BattleEdit(chosen, qx.own_units(block), 0, map_number, [area or sq.DeployArea([])],
                                    None, battle, floor if place.dungeon else ""))
    return chosen


def add_sample_battle(place: PlaceEdit, name: str = "", floor: str = "") -> str:
    """
    (Zodi, 4 November, his choice: the Places tab's random battles and floors
    start "from the same map 116 sample battle", as a quest's do) A random
    battle of the battle ground's own on the arena (`quest_edits.SAMPLE_MAP`):
    the quest's sample battle's three enemies (`quest_edits.SAMPLE_ENEMIES`,
    at the party's level) and its deploy area along the north edge
    (`quest_edits.sample_deploy`), in place of a copy of one of the game's
    battles. The first one starts on `DEFAULT_CHANCE` of 100 arrivals. Returns
    its name (`name`, or a new one numbered past the place's battles'). Raises
    ValueError as `add_battle` does.
    """
    if place.town and not place.dungeon:
        raise ValueError(f"{place.name} is a town: random battles are a battle ground's")
    if place.dungeon and floor_named(place, floor) is None:
        raise ValueError(f"{place.name} has no floor named {floor}")
    own = [b for b in place.battles if b.floor == (floor if place.dungeon else "")]
    if len(own) >= mp.MOST_BATTLES:
        raise ValueError(TOO_MANY_FLOOR_BATTLES if place.dungeon else TOO_MANY_BATTLES)
    chosen = qx.free_name(name or NEW_BATTLE, [b.name for b in place.battles])
    if not place.dungeon and not own and not place.chance:
        place.chance = DEFAULT_CHANCE
    place.battles.append(BattleEdit(chosen, qx.sample_units(qx.SAMPLE_ENEMIES, 1), 0, qx.SAMPLE_MAP,
                                    [qx.sample_deploy()], None, 0, floor if place.dungeon else ""))
    return chosen


def remove_battle(place: PlaceEdit, name: str) -> None:
    place.battles.remove(_battle(place, name))


def rename_battle(place: PlaceEdit, old: str, new: str) -> None:
    """A random battle renamed: a name as a quest's battle's (`side_quests.good_name`), none of the place's other
    battles'. Raises ValueError, its words the page's."""
    battle = _battle(place, old)
    if new == old:
        return
    if not sq.good_name(new):
        raise ValueError(BATTLE_NAME_BAD)
    if any(b.name.lower() == new.lower() for b in place.battles if b is not battle):
        raise ValueError((DUNGEON_BATTLE_TAKEN if place.dungeon else BATTLE_TAKEN).format(name=new))
    battle.name = new


def set_chance(place: PlaceEdit, value: int) -> None:
    place.chance = max(0, min(int(value), mp.MOST_CHANCE))


def set_battle_map(place: PlaceEdit, name: str, value) -> None:
    """A random battle's map: one of the game's by number, or one of the mod's quest maps by name."""
    _battle(place, name).map = value


def set_battle_story(place: PlaceEdit, name: str, value: Optional[int]) -> None:
    """The story's progress a random battle waits for (variable 110 at least it), or None: from the start."""
    _battle(place, name).story = None if value is None else int(value)


def battle_block(place: PlaceEdit, name: str) -> bytes:
    return _battle(place, name).units


def set_battle_unit(place: PlaceEdit, name: str, slot: int, **fields) -> None:
    """One of a random battle's 16 units' fields changed by name (`entd.unit_with`)."""
    battle = _battle(place, name)
    battle.units = entd.battle_with(battle.units, slot, **fields)


def add_battle_unit(place: PlaceEdit, name: str, slot: Optional[int] = None) -> Optional[int]:
    """A copy of a random battle's unit `slot` in its first empty place (`quest_edits.unit_added`): its place, or None."""
    battle = _battle(place, name)
    battle.units, empty = qx.unit_added(battle.units, slot)
    return empty


def take_out_battle_unit(place: PlaceEdit, name: str, slot: int) -> None:
    battle = _battle(place, name)
    battle.units = qx.unit_taken_out(battle.units, slot)


def toggle_battle_square(place: PlaceEdit, name: str, x: int, y: int, upper: bool = False) -> bool:
    """A tile added to a random battle's deploy area, or taken out of it (`quest_edits.toggle_square`: never a tile
    where one of its units starts on the field, Zodi's test 45)."""
    battle = _battle(place, name)
    if not battle.deploy:
        battle.deploy = [sq.DeployArea([])]
    return qx.toggle_square(battle.deploy, 0, x, y, upper, battle.units)


def battle_squares_taken(place: PlaceEdit, name: str) -> list:
    """(Zodi's test 45) What a random battle's card says of its deploy area's squares where one of its units starts
    on the field (`quest_edits.squares_taken`)."""
    battle = _battle(place, name)
    return qx.squares_taken(battle.deploy, battle.units)


def set_battle_deploy(place: PlaceEdit, name: str, units: Optional[int] = None, facing: Optional[int] = None,
                      upper: Optional[bool] = None) -> None:
    """A random battle's deploy area: how many units start there, which way they face, on which level."""
    battle = _battle(place, name)
    if not battle.deploy:
        battle.deploy = [sq.DeployArea([])]
    qx.set_area(battle.deploy[0], units, facing, upper)


def battle_problems(place: PlaceEdit, name: str, map_names=None) -> list:
    """What Mod Studio Framework would say of one random battle as Export writes the place (`place_problems`, the
    lines naming it)."""
    said = place_problems(place, map_names)
    return [line for line in said if f"random battle {name}'s" in line or f"random battle {name} " in line]


#: What the page says of random battles (`add_battle`, `rename_battle`).
# =============================================================================
# (1.18.0) A town's own menu
# =============================================================================

#: The game's towns' textures (the TexChange each one's Town row plays, its + 0x2C, the 1.5.2 tables' Unknown2C), by
#: the texture's name in `map_places.ICONS`: a town showing one of them has that town's look.
ICON_TOWNS = {"24": 0, "28": 1, "03": 2, "17": 3, "38": 4, "32": 5, "01": 6, "26": 7, "23": 8, "05": 9, "15": 10,
              "19": 11, "20": 12, "30": 13, "35": 14}
#: The game's towns with a Poachers' Den (their Town rows' + 0x32): Dorter, Warjilis, Sal Ghidos.
POACHERS_TOWNS = (9, 12, 14)
#: A town with a menu, in its line on the page.
MENU_SHORT = "a menu of its own"
#: The game's towns as the shops' table (ItemShopsData, `constants.ITEM_SHOPS`) names them, by their places: the
#: Outfitter's masks give town t the bit 0x8000 shifted right by t, the table reads the two bytes the other way about
#: (`dev/research/sidequests/town_menus.py`).
SHOP_TOWNS = {"Lesalia": 0, "Riovanes": 1, "Eagrose": 2, "Lionel": 3, "Limberry": 4, "Zeltennia": 5, "Gariland": 6,
              "Yardrow": 7, "Gollund": 8, "Dorter": 9, "Zaland": 10, "Goug": 11, "Warjilis": 12, "Bervenia": 13,
              "SalGhidos": 14}
#: The story's last shop point (variable 0x6F as the game's scenes set it: 16, event 457): an item whose Shop
#: Availability (ItemData's, `constants.ITEM_SHOP_AVAILABILITY`) is past it is never sold.
LAST_SHOP_POINT = 16


def _field(records: dict, edits: dict, table: str, item: int, name: str, default: str = "") -> str:
    """An item's field in one of the item tables as the mod has it: its edit, else the table's."""
    edited = (edits.get(table) or {}).get(item) or {}
    if name in edited:
        return str(edited[name])
    record = (records.get(table) or {}).get(item)
    return str(record.values.get(name, default)) if record is not None else default


def towns_selling(shops: str) -> list:
    """The game's towns (their places) a Shops value names ("Gariland, Zeltennia"; "None", none)."""
    return sorted(SHOP_TOWNS[n.strip()] for n in str(shops).split(",") if n.strip() in SHOP_TOWNS)


def town_shop(records: dict, edits: dict, town: int) -> list:
    """The items (1 to 255) a game town's Outfitter sells as the mod has the game's shops (`records`: the item tables'
    records by id, `{"item_shops": {id: record}}`; `edits`: the mod's, `WizardState.item_table_edits`)."""
    return [n for n in range(1, mp.MOST_ITEM + 1)
            if town in towns_selling(_field(records, edits, "item_shops", n, "Shops", "None"))]


def never_sold(records: dict, edits: dict, items) -> list:
    """Of `items`, those whose Shop Availability (as the mod has the item table) is past the story's last shop
    point: no Outfitter ever sells them."""
    points = c.ITEM_SHOP_AVAILABILITY
    out = []
    for n in items:
        value = _field(records, edits, "item", n, "ShopAvailability", "")
        if value in points and points.index(value) > LAST_SHOP_POINT:
            out.append(n)
    return out


def look_town(place: PlaceEdit) -> int:
    """The game's town whose look a town has: the one whose texture it shows, else the first (Lesalia)."""
    return ICON_TOWNS.get(place.icon, 0) if place.town and not place.texture else 0


def set_menu(place: PlaceEdit, on: bool) -> None:
    """A town's menu of its own (Enter Settlement), or none (its own art, if it had one, put aside with it): a new
    one shows its look's town's art, sells nothing until its items are picked (or copied: `copy_shop`), and has no
    Poachers' Den until ticked."""
    if not on:
        place.menu = None
        place.art, place.art_from = b"", ""
    elif place.menu is None:
        place.menu = mp.TownMenu(look_town(place))


def set_menu_art(place: PlaceEdit, town: int) -> None:
    """The game's town (0 to 14) whose art the town's menu shows (its own art, if it had one, put aside)."""
    if place.menu is not None and 0 <= int(town) <= mp.MOST_ART_TOWN:
        place.menu.art = int(town)
        place.art, place.art_from = b"", ""


def set_own_art(place: PlaceEdit, art: bytes, made_from: str = "") -> None:
    """(1.19.0) A town's menu's own art (a PNG of 680 x 452, `art_png`), in place of a game town's."""
    if place.menu is not None and art:
        place.art, place.art_from = bytes(art), made_from


def copy_shop(place: PlaceEdit, records: dict, edits: dict, town: Optional[int] = None) -> int:
    """The Outfitter's items made a copy of a game town's (its art town's unless `town` is given), as the mod has the
    game's shops (`town_shop`); returns how many (0, and nothing changed, when the shops' table has none for it)."""
    if place.menu is None:
        return 0
    items = town_shop(records, edits, place.menu.art if town is None else int(town))
    if items:
        place.menu.shop = items
    return len(items)


def add_shop_item(place: PlaceEdit, item) -> bool:
    """An item (1 to 255; (1.26.0) or one of the mod's own, by its name) the Outfitter sells, after the others; False
    (nothing changed) for one it sells already."""
    from . import mod_items as mi
    if place.menu is None:
        return False
    if isinstance(item, str):
        if not mi.good_name(item) or item in place.menu.own:
            return False
        place.menu.own.append(item)
        return True
    item = int(item)
    if not 1 <= item <= mp.MOST_ITEM or item in place.menu.shop:
        return False
    place.menu.shop.append(item)
    return True


def remove_shop_item(place: PlaceEdit, item) -> None:
    if place.menu is None:
        return
    if isinstance(item, str):
        if item in place.menu.own:
            place.menu.own.remove(item)
    elif int(item) in place.menu.shop:
        place.menu.shop.remove(int(item))


def clear_shop(place: PlaceEdit) -> None:
    """The Outfitter sells nothing."""
    if place.menu is not None:
        place.menu.shop = []
        place.menu.own = []


def towns_selling_item(places: dict, item: str) -> list:
    """(1.26.0) The names of the mod's towns whose Outfitter sells one of its own items (by its name)."""
    return [p.name for p in places.values() if p.town and p.menu is not None and item in p.menu.own]


def item_renamed(places: dict, old: str, new: str) -> None:
    """(1.26.0) One of the mod's own items given another name: each Outfitter selling it sells it by that name."""
    for place in places.values():
        if place.menu is not None and old in place.menu.own:
            place.menu.own[place.menu.own.index(old)] = new


def item_removed(places: dict, item: str) -> None:
    """(1.26.0) One of the mod's own items taken out of the mod: no Outfitter sells it now."""
    for place in places.values():
        if place.menu is not None and item in place.menu.own:
            place.menu.own.remove(item)


def set_poachers(place: PlaceEdit, on: bool) -> None:
    if place.menu is not None:
        place.menu.poachers = bool(on)


def menu_towns(places: dict) -> list:
    """The names of the mod's towns with a menu of their own (whose taverns may tell a rumor), in the places' order."""
    return [p.name for p in places.values() if p.town and p.menu is not None]


# =============================================================================
# (1.20.0) A town darkened once a quest's flag is set
# =============================================================================

#: A town's darkening in a place's line (and Mod Contents): its flag and its quest.
DARK_SHORT = "darkened once {flag} is set ({quest})"
#: A town darkened by a flag the mod's quests don't have (Mod Studio Framework's words: `Framework.DarkLine`).
DARK_MISSING = "{place} isn't darkened: your mod has no side quest {quest} with a flag {flag}."


def flag_choices(quests: dict) -> list:
    """Each flag of the mod's quests a town may be darkened by, as (quest, flag): quest by quest in the page's order
    (each by its folder, its name), each quest's flags in its order (a step's "<event> done", set once its event has
    played; a rumor's "<rumor> read"; a flag of its own)."""
    return [(folder, flag) for folder, edits in (quests or {}).items() for flag in edits.quest.flags]


def first_dark_flag(place: PlaceEdit, quests: dict) -> Optional[tuple]:
    """The flag a town is darkened by when first ticked: the done flag of the first step waiting at it (its event done,
    as the game darkens its places), else the first of the mod's quests' flags; None when they have none."""
    from mod_studio import quest_edits as qx
    for folder, edits in (quests or {}).items():
        for step in qx.steps(edits.quest):
            if edits.quest.starts[step.start].place == place.name and step.once:
                return folder, step.once
    choices = flag_choices(quests)
    return choices[0] if choices else None


def set_darkened(place: PlaceEdit, quest: Optional[str] = None, flag: Optional[str] = None) -> None:
    """A town darkened once a quest's flag is set (its quest's folder and the flag), or never (None)."""
    place.darkened = mp.PlaceDarkened(quest, flag) if quest and flag else None


def dark_problem(place: PlaceEdit, quests: dict) -> str:
    """What Mod Studio Framework would say of a town darkened by a flag the mod's quests don't have, or ""."""
    dark = place.darkened if place.town else None
    if dark is None or (dark.quest, dark.flag) in flag_choices(quests):
        return ""
    return DARK_MISSING.format(place=place.name, quest=dark.quest, flag=dark.flag)


def follow_quest(places: dict, old: str, new: str) -> None:
    """A quest renamed: the towns darkened by its flags named so; (1.21.0) and the dungeons' floors waiting for one."""
    for place in (places or {}).values():
        if place.darkened is not None and place.darkened.quest == old:
            place.darkened.quest = new
        for floor in place.floors:
            if floor.quest == old:
                floor.quest = new


def follow_flags(places: dict, quest: str, before: list, after: list) -> None:
    """A quest's flags renamed (`before` and `after` its flags, each in its place, as `quest_edits` renames them): the
    towns darkened by one named so. A flag taken out leaves them as they were (`dark_problem` says it)."""
    if len(before) != len(after):
        return
    renamed = {old: new for old, new in zip(before, after) if old != new}
    for place in (places or {}).values():
        dark = place.darkened
        if dark is not None and dark.quest == quest and dark.flag in renamed:
            dark.flag = renamed[dark.flag]
        # (1.21.0) And the dungeons' floors waiting for one.
        for floor in place.floors:
            if floor.quest == quest and floor.flag in renamed:
                floor.flag = renamed[floor.flag]


# =============================================================================
# (1.21.0) A dungeon's floors
# =============================================================================

#: A place's kind in words (its line, its card).
KIND_WORDS = {TOWN: "A town", GROUND: "A battle ground", DUNGEON: "A dungeon"}
#: A floor the page makes: its name until it is given one.
NEW_FLOOR = "Floor"
TOO_MANY_FLOORS = f"A dungeon has up to {mp.MOST_FLOORS} floors."
FLOOR_NAME_BAD = (f"A floor's name is letters, digits, spaces, underscores and hyphens, 1 to {mp.MOST_FLOOR_NAME} of "
                  "them, with no space at either end.")
FLOOR_TAKEN = "The dungeon has a floor named {name} already."
#: A floor waiting for a flag the mod's quests don't have (Mod Studio Framework's words: `Framework.PlanDungeon`).
FLOOR_MISSING = "{place}'s floor {floor} isn't listed: your mod has no side quest {quest} with a flag {flag}."
#: (1.24.0) The first floor can't wait for the floor before it to be won.
FIRST_FLOOR_WON = "{floor} is the dungeon's first floor: it has no floor before it to be won."


def good_floor_name(name) -> bool:
    return isinstance(name, str) and hj.good_name(name) and len(name) <= mp.MOST_FLOOR_NAME


def floor_named(place: PlaceEdit, name: str) -> Optional[FloorEdit]:
    return next((f for f in place.floors if f.name == name), None)


def _floor(place: PlaceEdit, name: str) -> FloorEdit:
    found = floor_named(place, name)
    if found is None:
        raise ValueError(f"{place.name} has no floor named {name}")
    return found


def floor_battles(place: PlaceEdit, name: str) -> list:
    """A dungeon's floor's random battles, in their order."""
    return [b for b in place.battles if b.floor == name]


def add_floor(place: PlaceEdit, name: str = "") -> str:
    """A floor of the dungeon's, last in its list, listed from the start, without battles yet: its name (`name`, or
    "Floor" numbered past the dungeon's floors'). Raises ValueError, its words the page's: not a dungeon, or 10 floors
    already."""
    if not place.dungeon:
        raise ValueError(f"{place.name} isn't a dungeon: floors are a dungeon's")
    if len(place.floors) >= mp.MOST_FLOORS:
        raise ValueError(TOO_MANY_FLOORS)
    taken = [f.name for f in place.floors]
    wanted = name or f"{NEW_FLOOR} {len(place.floors) + 1}"
    chosen = wanted if wanted.lower() not in {t.lower() for t in taken} else qx.free_name(wanted, taken)
    place.floors.append(FloorEdit(chosen[:mp.MOST_FLOOR_NAME]))
    return place.floors[-1].name


def remove_floor(place: PlaceEdit, name: str) -> None:
    """A floor taken out, with its battles; (1.24.0) the floor now first, if it waited for the one before it to be won,
    listed from the start (the first floor has none before it)."""
    floor = _floor(place, name)
    place.floors.remove(floor)
    place.battles = [b for b in place.battles if b.floor != name]
    if place.floors and place.floors[0].won:
        place.floors[0].won = False


def rename_floor(place: PlaceEdit, old: str, new: str, quests: Optional[dict] = None) -> None:
    """A floor renamed (`good_floor_name`), none of the dungeon's other floors'; its battles follow, and (1.25.0) the
    quests' steps waiting at it (`quests`, the page's). Raises ValueError, its words the page's."""
    floor = _floor(place, old)
    if new == old:
        return
    if not good_floor_name(new):
        raise ValueError(FLOOR_NAME_BAD)
    if any(f.name.lower() == new.lower() for f in place.floors if f is not floor):
        raise ValueError(FLOOR_TAKEN.format(name=new))
    floor.name = new
    for battle in place.battles:
        if battle.floor == old:
            battle.floor = new
    for edits in (quests or {}).values():
        for start in edits.quest.starts:
            if start.place == place.name and start.floor == old:
                start.floor = new


def waiting_at_floor(quests: dict, place: str, floor: str) -> list:
    """(1.25.0) (quest, step, event) of each quest's step waiting at the floor `floor` of the mod's dungeon named
    `place`, the steps counted from 1, in the quests' order: as the floor is chosen, the first whose conditions hold
    plays in place of its battle."""
    from mod_studio import quest_edits as qx
    out = []
    for folder, edits in (quests or {}).items():
        for n, step in enumerate(qx.steps(edits.quest)):
            start = edits.quest.starts[step.start]
            if start.place == place and start.floor == floor:
                out.append((edits.quest.name or folder, n + 1, start.event))
    return out


#: (1.25.0) Why a step waiting at a floor can't be played there: its place isn't one of the mod's dungeons, or the
#: dungeon has no such floor.
FLOOR_NOT_DUNGEON = "{place} isn't one of your dungeons: a step waits at a floor of one of your dungeons."
FLOOR_NOT_THERE = "{place} has no floor {floor}: this step waits at a floor it doesn't have."


def floor_start_problem(places: dict, start) -> str:
    """(1.25.0) Why a quest's start waiting at a floor isn't played there (its words the page's), or "": the place one
    of the mod's dungeons, the floor one of its floors."""
    if not getattr(start, "floor", ""):
        return ""
    found = place_named(places, start.place) if isinstance(start.place, str) else None
    if found is None or not found.dungeon:
        return FLOOR_NOT_DUNGEON.format(place=start.place)
    if not any(f.name == start.floor for f in found.floors):
        return FLOOR_NOT_THERE.format(place=start.place, floor=start.floor)
    return ""


def set_floor_description(place: PlaceEdit, name: str, words: str) -> None:
    """A floor's words as they are typed, as a place's description is kept (`set_description`)."""
    _floor(place, name).description = words.replace("\r\n", "\n").replace("\r", "\n").strip()


def set_floor_opens(place: PlaceEdit, name: str, quest: Optional[str] = None, flag: Optional[str] = None,
                    won: bool = False) -> None:
    """The quest flag a floor waits for (its quest's folder and the flag), or none: listed from the start; (1.24.0) or,
    `won`, the floor before it won (any one of its battles, once). Raises ValueError for the first floor won: it has no
    floor before it."""
    floor = _floor(place, name)
    if won and place.floors.index(floor) == 0:
        raise ValueError(FIRST_FLOOR_WON.format(floor=floor.name))
    floor.won = bool(won)
    floor.quest, floor.flag = (quest, flag) if quest and flag and not won else ("", "")


def set_dungeon_art(place: PlaceEdit, number: int) -> None:
    """(1.23.0) The game's place (by its number: `map_places.good_art_place`) whose art a dungeon's list and its
    location info show (its own art, if it had one, put aside)."""
    if mp.good_art_place(int(number)):
        place.dungeon_art = int(number)
        place.dungeon_own_art, place.dungeon_own_art_from = b"", ""


def set_dungeon_own_art(place: PlaceEdit, art: bytes, made_from: str = "") -> None:
    """(1.23.0) A dungeon's own art (a PNG of 680 x 452, `art_png`), in place of a game place's."""
    if art:
        place.dungeon_own_art, place.dungeon_own_art_from = bytes(art), made_from


#: (1.23.0) The game's places whose art a dungeon may show, in their numbers' order.
ART_PLACES = tuple(n for n in range(mp.MOST_ART_PLACE + 1) if mp.good_art_place(n))


def floor_problems(place: PlaceEdit, quests: dict) -> list:
    """What Mod Studio Framework would say of a dungeon's floors waiting for a flag the mod's quests don't have."""
    if not place.dungeon:
        return []
    have = set(flag_choices(quests))
    return [FLOOR_MISSING.format(place=place.name, floor=f.name, quest=f.quest, flag=f.flag) for f in place.floors
            if f.quest and f.flag and (f.quest, f.flag) not in have]


TOO_MANY_BATTLES = f"A battle ground has up to {mp.MOST_BATTLES} random battles."
TOO_MANY_FLOOR_BATTLES = f"A floor has up to {mp.MOST_BATTLES} random battles."
BATTLE_NAME_BAD = ("A battle's name is letters, digits, spaces, underscores and hyphens, 1 to 64 of them, with no space at "
                   "either end.")
BATTLE_TAKEN = "The battle ground has a random battle named {name} already."
DUNGEON_BATTLE_TAKEN = "The dungeon has a random battle named {name} already."


#: Where a place stands, said (`place_warnings`).
OFF_THE_MAP = "{name} runs off the world map: drag it onto the map."
OVER = "{name} overlaps {others} on the world map: drag it clear of the game's places."


def draw(road: RoadEdit, places: dict, picture: str = PREVIEW_PICTURE) -> tuple:
    """The road drawn by Mod Studio between its places (`map_roads.drawn_road`): (the road as written, its
    picture, a PIL image), its texture's files named `picture` (its grain follows the name). Raises ValueError when
    it can't be drawn (too short, off the map, a place the mod hasn't)."""
    for end in (road.start, road.end):
        if where(end, places) is None:
            raise ValueError(f"it joins {end}, which isn't one of the places")
    return mr.drawn_road(road.name, road.start, road.end, road.via, picture, mp_places(places))


def road_problems(road: RoadEdit, places: dict, drawn: Optional[tuple] = None) -> list:
    """Why the road can't be drawn (too short between its places, off the map, a place gone), or what Mod Studio
    Framework would say of its file as Export writes it (`map_roads.read_road_text`, its own words). `drawn` is
    the road already drawn, when the caller has it: (the road as written, its texture's width and height)."""
    from mod_studio import uib
    if drawn is None:
        try:
            made, picture = draw(road, places)
        except ValueError as exc:
            return [str(exc)]
        drawn = (made, picture.size)
    made, (width, height) = drawn
    most = mr.MOST_PICTURE - 2
    if not (0 < width <= most and 0 < height <= most):
        return [f"its texture would be {width} x {height}, more than {most} x {most}"]
    parts = uib.part_list_file(f"ui/ffto/worldmap/texture/{made.picture}.tex",
                               [("TexturePart", (0, 0, width + 2, height + 2)),
                                ("Road", (1, 1, width + 1, height + 1))])

    def read_file(path: str):
        return parts if path.endswith(".utexpt") else b"its texture"
    _read, said = mr.read_road_text(mr.road_text(made), read_file, road.folder, {p.name for p in places.values()})
    return list(said)


# =============================================================================
# Renamed and taken out
# =============================================================================

def rename_place(places: dict, roads: dict, quests: dict, folder: str, name: str) -> str:
    """Renames the place in `folder`: its folder follows its name, and the roads joining it, the quests' starts
    waiting there and (1.18.0) the rumors its tavern tells name it so. Returns its new folder. Raises ValueError for a
    name that isn't one, or is taken."""
    place = places[folder]
    problem = name_problem(name, places, folder)
    if problem:
        raise ValueError(problem)
    old = place.name
    new_folder = folder_for(name)
    place.name, place.folder = name, new_folder
    rebuilt = {}
    for key, value in places.items():
        rebuilt[new_folder if key == folder else key] = value
    places.clear()
    places.update(rebuilt)
    for road in roads.values():
        if road.start == old:
            road.start = name
        if road.end == old:
            road.end = name
    for edits in (quests or {}).values():
        for start in edits.quest.starts:
            if start.place == old:
                start.place = name
        # (1.18.0) The rumors told in its tavern.
        for rumor in edits.quest.rumors:
            rumor.towns = [name if town == old else town for town in rumor.towns]
    return new_folder


def name_problem(name, places: dict, folder: str = "", kind: str = "place") -> str:
    """Why a place's (or a road's) name can't be: not a name, one of the game's places' names, or the mod's
    already. "" when it can."""
    if not good_name(name):
        return NAME_BAD
    if kind == "place" and game_place_named(name) is not None:
        return GAME_NAME.format(name=name)
    if any(folder_for(other.name).lower() == folder_for(name).lower() for key, other in places.items()
           if key != folder):
        return TAKEN[kind].format(name=name)
    return ""


#: Why a name can't be (the page says these).
NAME_BAD = ("A name is letters, digits, spaces, apostrophes, underscores and hyphens, 1 to 64 of them, with no space "
            "at either end.")
GAME_NAME = "One of the game's places is named {name}: give yours a name of its own."
TAKEN = {"place": "Your mod has a place named {name} already.", "road": "Your mod has a road named {name} already."}


def rename_road(roads: dict, folder: str, name: str) -> str:
    """Renames the road in `folder`, its folder following its name. Returns its new folder."""
    problem = name_problem(name, roads, folder, "road")
    if problem:
        raise ValueError(problem)
    road = roads[folder]
    new_folder = folder_for(name)
    road.name, road.folder = name, new_folder
    rebuilt = {}
    for key, value in roads.items():
        rebuilt[new_folder if key == folder else key] = value
    roads.clear()
    roads.update(rebuilt)
    return new_folder


def remove_place(places: dict, roads: dict, folder: str) -> list:
    """Takes the place in `folder` out, with the roads joining it. Returns those roads' names."""
    place = places.pop(folder)
    gone = [r.name for r in roads_at(roads, place.name)]
    for key in [k for k, r in roads.items() if place.name in (r.start, r.end)]:
        roads.pop(key)
    return gone


def told_at(quests: dict, name: str) -> list:
    """(1.18.0) (quest, rumor) of each quest's rumor naming the mod's town named `name` among its towns."""
    out = []
    for folder, edits in (quests or {}).items():
        for rumor in edits.quest.rumors:
            if name in rumor.towns:
                out.append((edits.quest.name or folder, rumor.name))
    return out


def waiting_at(quests: dict, name: str, floors: bool = True) -> list:
    """(quest, step) of each quest's step waiting at the mod's place named `name`, the steps counted from 1; (1.25.0)
    with `floors`, those waiting at one of its floors (a dungeon's) too."""
    from mod_studio import quest_edits as qx
    out = []
    for folder, edits in (quests or {}).items():
        for n, step in enumerate(qx.steps(edits.quest)):
            start = edits.quest.starts[step.start]
            if start.place == name and (floors or not start.floor):
                out.append((edits.quest.name or folder, n + 1))
    return out


# =============================================================================
# Written into a mod and read back
# =============================================================================

def write_place(mod_root, mod_id: str, place: PlaceEdit) -> list:
    """Writes the place into `<mod_root>/ModStudioPlaces/<folder>/place.json`, and a town's own texture as its two
    files at the game's paths in the mod, named of the mod and the place (`map_places.picture_name`); (1.17.0) and a
    battle ground's random battles' units beside its file (`battle_files`; (1.21.0) a dungeon's floors' battles'
    too); (1.19.0) and its menu's own art as its two
    files beside its texture's (`map_places.art_name`). Returns the paths written."""
    picture = mp.picture_name(mod_id, place.folder) if place.town and place.texture else ""
    image = texture_image(place.texture) if picture else None
    if image is not None and image.size != mp.PICTURE_SIZE:
        raise ValueError(f"its texture is {image.size[0]} x {image.size[1]}, not 172 x 172")
    # (1.19.0) Its menu's own art, named of the mod and the place apart from its picture (`map_places.art_name`);
    # (1.23.0) a dungeon's own art the same (a place written as a dungeon has no menu, and as a town no dungeon's art).
    own_art = place.dungeon_own_art if place.dungeon else (
        place.art if place.town and place.menu is not None else b"")
    art = mp.art_name(mod_id, place.folder) if own_art else ""
    art_image = texture_image(own_art) if art else None
    if art_image is not None and art_image.size != mp.ART_SIZE:
        raise ValueError(f"its art is {art_image.size[0]} x {art_image.size[1]}, not 680 x 452")
    # Its random battles' units beside its file: a battle ground's own, (1.21.0) a dungeon's floors'.
    if place.dungeon:
        kept = [b for b in place.battles if b.floor and floor_named(place, b.floor) is not None]
    else:
        kept = [] if place.town else [b for b in place.battles if not b.floor]
    named = battle_files(place)
    files = {named[b.name]: b.units for b in kept if b.units}
    return mp.write_place(mod_root, place.folder, place.place(picture, art), image, files, art_image)


def write_road(mod_root, mod_id: str, road: RoadEdit, places: dict) -> list:
    """Draws the road and writes it into `<mod_root>/ModStudioRoads/<folder>/road.json`, its texture as its two
    files at the game's paths in the mod, named of the mod and the road (`map_roads.picture_name`), and its walk.
    Returns the paths written."""
    drawn, picture = draw(road, places, mr.picture_name(mod_id, road.folder))
    return mr.write_road(mod_root, road.folder, drawn, picture)


def named_files(folder: Path, file_name: str) -> list:
    """The texture files (from the mod's folder) a place's or a road's file in `folder` names: its Picture's
    `.tex` and `.utexpt`; (1.23.0) and its own art's (a town's menu's, a dungeon's); none when it names none or can't
    be read."""
    try:
        top = hj.loads(hj.read_text(Path(folder) / file_name))
    except (OSError, ValueError):
        return []
    if not isinstance(top, dict):
        return []
    menu = mp._get(top, "Menu")
    named = [mp._get(top, "Picture"), mp._get(menu, "Art") if isinstance(menu, dict) else None, mp._get(top, "Art")]
    out = []
    for name in named:
        if mp.good_picture(name):
            for rel in (f"{mp.TEXTURE_FOLDER}/{name}.tex", f"{mp.PARTS_FOLDER}/{name}.utexpt"):
                if rel not in out:
                    out.append(rel)
    return out


def _own_art(mod_root: Path, art: str) -> bytes:
    """(1.19.0) A town's menu's own art read back from the mod (its `.tex` read here, its part 0) as a PNG; (1.23.0) a
    dungeon's own art the same."""
    from mod_studio import texture_data as td
    from mod_studio import uib
    # (Its texture is RGBA, 680 x 452: past what is read here quickest, read here all the same.)
    sheet = td.decode_tex_in_process(Path(mod_root) / mp.TEXTURE_FOLDER / f"{art}.tex", None)
    parts = uib.read_part_list((Path(mod_root) / mp.PARTS_FOLDER / f"{art}.utexpt").read_bytes())
    if parts.parts:
        sheet = sheet.crop(parts.parts[0].rect)
    return art_png(sheet)


def _own_texture(mod_root: Path, picture: str) -> bytes:
    """A town's own texture read back from the mod (its `.tex` read here, its part 1 cut out) as a PNG."""
    from mod_studio import texture_data as td
    from mod_studio import uib
    sheet = td.decode_tex_in_process(Path(mod_root) / mp.TEXTURE_FOLDER / f"{picture}.tex")
    parts = uib.read_part_list((Path(mod_root) / mp.PARTS_FOLDER / f"{picture}.utexpt").read_bytes())
    if len(parts.parts) > 1:
        x1, y1, x2, y2 = parts.parts[1].rect
        sheet = sheet.crop((x1, y1, x2, y2))
    return texture_png(sheet)


def read_mod(mod_root) -> tuple:
    """
    The mod's places and roads as the page has them: `(places, roads)`, each
    a list of (folder, the place or road or None, problems) in their
    folders' order, as Mod Studio Framework reads them (`map_places`,
    `map_roads`). A town's own texture is read back from the mod's files; one
    that can't be read here is a problem (the place is then carried through
    as it is).
    """
    places_out, roads_out = [], []
    for folder, place, problems in mp.read_mod_places(mod_root):
        if place is None:
            places_out.append((folder, None, problems))
            continue
        edit = PlaceEdit(folder, place.name, place.town, place.x, place.y, icon=place.icon,
                         description=place.description, chance=place.chance, menu=copy.deepcopy(place.menu),
                         darkened=copy.deepcopy(place.darkened), dungeon=place.dungeon,
                         dungeon_art=place.dungeon_art if isinstance(place.dungeon_art, int) else mp.DEEP_PLACE)
        # (1.17.0) Its random battles, their own units read back from their files; (1.21.0) a dungeon's, floor by floor.
        listed = [(battle, "") for battle in place.battles]
        for floor in place.floors:
            edit.floors.append(FloorEdit(floor.name, floor.description, floor.opens.quest if floor.opens else "",
                                         floor.opens.flag if floor.opens else "", floor.won))
            listed += [(battle, floor.name) for battle in floor.battles]
        for battle, floor_name in listed:
            units = (Path(mod_root) / mp.FOLDER / folder / battle.units).read_bytes() if isinstance(
                battle.units, str) else b""
            edit.battles.append(BattleEdit(battle.name, units, battle.units if isinstance(battle.units, int) else 0,
                                           battle.map, copy.deepcopy(battle.deploy), battle.story, floor=floor_name))
        if place.picture:
            try:
                edit.texture = _own_texture(Path(mod_root), place.picture)
                edit.texture_from = f"{place.picture}.tex"
            except Exception as exc:                                  # noqa: BLE001
                places_out.append((folder, None, [f"its texture can't be read here ({exc})"]))
                continue
        # (1.19.0) Its menu's own art, read back; the menu's game town then the one its look is.
        if edit.menu is not None and isinstance(edit.menu.art, str):
            try:
                edit.art = _own_art(Path(mod_root), edit.menu.art)
                edit.art_from = f"{edit.menu.art}.tex"
            except Exception as exc:                                  # noqa: BLE001
                places_out.append((folder, None, [f"its art can't be read here ({exc})"]))
                continue
            edit.menu.art = look_town(edit)
        # (1.23.0) A dungeon's own art, read back; its game place then Midlight's Deep (shown once it is taken off).
        if place.dungeon and isinstance(place.dungeon_art, str):
            try:
                edit.dungeon_own_art = _own_art(Path(mod_root), place.dungeon_art)
                edit.dungeon_own_art_from = f"{place.dungeon_art}.tex"
            except Exception as exc:                                  # noqa: BLE001
                places_out.append((folder, None, [f"its art can't be read here ({exc})"]))
                continue
        places_out.append((folder, edit, []))
    for folder, road, problems in mr.read_mod_roads(mod_root):
        if road is None:
            roads_out.append((folder, None, problems))
            continue
        roads_out.append((folder, RoadEdit(folder, road.name, road.start, road.end, [tuple(p) for p in road.via]), []))
    return places_out, roads_out


def summary_line(place: PlaceEdit, roads: dict) -> str:
    """A place in a line: its kind and how many roads join it; (1.17.0) a battle ground's random battles; (1.18.0) a
    town's menu; (1.20.0) what darkens a town; (1.21.0) a dungeon's floors."""
    count = len(roads_at(roads, place.name))
    kind = KIND_WORDS[kind_of(place)]
    line = f"{kind}, {count} road{'s' if count != 1 else ''}"
    if place.dungeon:
        many = len(place.floors)
        return line + f", {many} floor{'s' if many != 1 else ''}"
    ground = [b for b in place.battles if not b.floor]
    if ground and not place.town:
        many = len(ground)
        line += f", {many} random battle{'s' if many != 1 else ''}"
    if place.menu is not None and place.town:
        line += ", " + MENU_SHORT
    if place.darkened is not None and place.town:
        line += ", " + DARK_SHORT.format(flag=place.darkened.flag, quest=place.darkened.quest)
    return line


def place_words(end) -> str:
    """A road's place in words: one of the game's by its name, one of the mod's by its own."""
    if isinstance(end, int) and not isinstance(end, bool):
        return mr.GAME_PLACES.get(end, (f"place {end}",))[0]
    return str(end)
