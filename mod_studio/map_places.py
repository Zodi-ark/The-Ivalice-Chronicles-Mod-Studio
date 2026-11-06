"""
A mod's own places on the world map (Zodi, 26 October: "we should do "real
new places, built in steps" because the pay off would be a tremendous
achievement and one of the best possible practices for the longevity of the
Ivalice Chronicles modding scene").

**A place** is a folder of its own in a mod, `ModStudioPlaces/<place>/`,
holding `place.json` (`place_text`): its name, its kind (a town, its picture
the mod's own or one of the game's town pictures; or a battle ground, the
game's point) and where its middle is on the world map, in the pixels of the
map's picture (3840 x 2288: Gariland's middle is at 1030, 1106). A modder
never chooses a number: places have names. Mod Studio Framework (the
helper, since 1.3.0, `helper/ModStudioEventSetup/PlaceFile.cs` reads this
same file and says the same problems) shows each one on the world map as a
piece of the map's layout of its own, copied from one of the game's places'
pieces as the world map sets itself up (`MapPieces.cs`).

**The first step is pictures only**: a mod's place is shown where its file
says, as the game shows its own (its markers hidden), but no road leads to
it yet, the cursor doesn't stop at it and no quest starts there; those are
the next steps (roads, then places the game travels to, then a quest's
reveal of one).

**(1.7.0) A place the game goes to**: with the helper's 1.7.0, a mod's place
is one of the world map's places: numbered past the game's 48 by the helper
(kept in its `Numbers.json`), its road (`map_roads`) walked to it, the mouse
showing its name, a save standing on it. Nothing happens there yet: no
menu, no battle, no event (`helper/ModStudioEventSetup/Destinations.cs`).

**(1.16.0) Its description**, if it has one (`Description`, Zodi's list, his
fourth: "We can add the world map place name but we can not yet add its
description"): the words the world map's location info shows under a
place's name, from its `Town` row (the helper's `Destinations.TownRow`),
up to 200 characters on two lines at the most.

**(1.17.0) A battle ground's own random battles**, if it has them
(`RandomBattles`, Zodi's list, his fifth: "A battle on a mod's own battle
ground", his choice "Its own battles"): how many of 100 arrivals start one
(`Chance`; choosing to fight where you stand always does) and one to eight
battles (`PlaceBattle`), each its units (a file of 640 bytes in the place's
folder, 16 units as the game's battle files hold a battle, or one of the
game's battles by its number), its map (one of the game's by number, or one
of the mod's quest maps by name), where the player's units start (one
deploy area, as a quest battle's own: `side_quests.DeployArea`; the game's
random battles start the party on one) and, if it
waits for it, the story's progress it is fought from (`From`: variable 110
at least it). The game picks a random battle by the road arrived along from
a table of its 19 battle grounds (`dev/research/sidequests/README.md`, A
battle on a mod's battle ground); the helper picks one of these instead at a
mod's place, as evenly as the game picks its own, among those the story has
reached.

**(1.18.0) A town's own menu**, if it has one (`Menu`, Zodi's list, his
fifth: "a town's menu at a mod's own town", his choice "Its own"), opened by
Enter Settlement as a town of the game's: the game's town whose art it shows
(`Art`, by its place, 0 to 14; (1.19.0) or its own art, its two files' name,
as a town's own picture's: `art_files`), its Outfitter's items (`Shop`, the
game's by number, each sold once the story reaches the point the game's own
shops start selling it) and, if it has one, its Poachers' Den (`Poachers`). Its
tavern tells the side quests' rumors that name the town; its Warriors' Guild
is the game's (`TownMenu`). A town without one has no settlement to enter,
as some of the game's places have none.

**(1.21.0) A dungeon**, a place like Midlight's Deep (`Kind` Dungeon, Zodi's
list, his seventh: "clicking on it brings up a list of maps in the dungeon
and after selecting one it takes you to a randomly selected battle on that
map"): drawn as a town is (its picture), its `Floors` the list choosing it
shows, one to ten (`PlaceFloor`), each its name and words as the Deep's list
shows its own, the quest flag it waits for if any (`Opens`, his choice:
"each floor waiting for a quest flag the modder picks, or showing from the
start if none is picked") and one to eight random battles (`PlaceBattle`, his
choice: "a few random battles per floor"), one picked evenly each time the
floor is chosen. A dungeon has no Menu and no RandomBattles of its own.
(1.23.0) Its list's art and its location info's (`Art`, Zodi's choice after
test 49, "Its own art"): one of the game's places' by its number (0 to 19,
or 21 to 23: those with a settlement's art; Midlight's Deep's, 22, when it
names none), or its own, its two files' name as a menu's own art's
(`art_files`). Its list shows its name, and its About page its description
(none without one).

**A town's own picture** is a texture of the mod's own with its part list,
at the game's paths in the mod, which the mod loader serves:
`FFTIVC/data/enhanced/ui/ffto/worldmap/texture/<Picture>.tex` and
`.../textureparts/<Picture>.utexpt`, its part 1 the picture (172 x 172, as
the game's town pictures are), drawn in its colors. `picture_files` makes
both from a picture; `write_place` writes them beside the file.

Nothing here imports Qt.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from mod_studio import helper_json as hj
from mod_studio import quest_maps as qm

#: Where a mod keeps its places, one folder each; the file each holds.
FOLDER = "ModStudioPlaces"
FILE_NAME = "place.json"
FORMAT = "Mod Studio place"
VERSION = 1
#: The world map's picture (MapAll's Map, ui_wm_map_uitx): where a place's middle may be.
MAP_WIDTH, MAP_HEIGHT = 3840, 2288
#: The game's town pictures, by their names in ui_wm_icon_base_uitx (each a TexChange of the map's Base piece).
ICONS = ("01", "03", "05", "07", "10", "11", "14_34", "15", "17", "19", "20", "22", "23", "24", "26", "28", "30",
         "32", "35", "38", "40", "41", "42")
#: Which of them each of the map's Base pieces shows: the TexChange the world map's setup plays on it (`0x159304` calls
#: `0x158E30` at `0x159613` for a place whose Town row's + 0x30 is set: "TexChange%s" of its + 0x2C as "%02d", "14_34"
#: for Fort Besselat, 21). Each piece is named "Base" and its row's + 0x18, the same name for all but two: Midlight's
#: Deep's (22, "Deep", + 0x2C 42) and Nelveska Temple's (23, "Nel", + 0x2C 41), the 1.5.2 tables' Town rows.
BASE_ICONS = {"Deep": "42", "Nel": "41"}


def base_icon(piece: str) -> str:
    """The town picture a Base piece of the map shows, by the piece's name past "Base"."""
    return BASE_ICONS.get(piece, piece)
#: Where a town's own picture's files are in its mod, and the part list's name the game knows it by.
TEXTURE_FOLDER = "FFTIVC/data/enhanced/ui/ffto/worldmap/texture"
PARTS_FOLDER = "FFTIVC/data/enhanced/ui/ffto/worldmap/textureparts"
PARTS_NAME = "UITextureParts://ui/ffto/worldmap/textureparts/"
#: A town's picture: its size, as the game's are, and its part in its part list (a clear pixel round it).
PICTURE_SIZE = (172, 172)
PICTURE_SHEET = (174, 174)
PICTURE_PART = (1, 1, 173, 173)
#: (1.19.0) A menu's own art: its size, as the menu's and the location info's thumbnail is (`worldmap_base_menu.uib`'s
#: BaseImage/Thumbnail, 680 x 452), its part 0 the whole texture (the box's own part).
ART_SIZE = (680, 452)
KINDS = ("Town", "Battle", "Dungeon")
#: (1.16.0) A place's description at the most: the location info's two lines (`wm_location_info.uib`'s text_detail,
#: 1750 by 106 at 28 points), the game's own 80 to 160 characters (the helper's `MostDescription`).
MOST_DESCRIPTION = 200
#: (1.17.0) A battle ground's random battles: one to eight (as many formations as each entrance of the game's battle
#: grounds has), started on up to 100 of 100 arrivals (the game's own: 31 of 100, a roll of 0 to 99 at most 30); a
#: battle's units, as the game's battle files hold a battle (`side_quests.BATTLE_BYTES`), in a file of the place's
#: folder ending so; the story's progress a battle may wait for (variable 110, as the world map's own tests compare
#: it: up to 65535).
MOST_BATTLES, MOST_CHANCE, MOST_FROM = 8, 100, 65535
UNITS_ENDING = ".entd"
#: (1.18.0) A town's menu: its art one of the game's 15 towns' (places 0 to 14); its Outfitter's items numbered as the
#: game's shops list them (1 to 255: the stock's loop counts 256, 0 none) (the helper's `MostArtTown`, `MostItem`).
MOST_ART_TOWN, MOST_ITEM = 14, 255
#: (1.21.0) A dungeon's floors: one to ten (as many as Midlight's Deep lists), each named in 1 to 24 characters (the
#: helper's `MostFloors`, `MostFloorName`).
MOST_FLOORS, MOST_FLOOR_NAME = 10, 24
#: (1.24.0) A floor's Opens when it is listed once the floor before it is won (the helper's `FloorBeforeWon`).
FLOOR_BEFORE_WON = "FloorBeforeWon"
#: (1.23.0) The game's places a dungeon's art may be (their Town rows' art: the towns 0 to 14 and the other places with
#: a settlement's art, 15 to 19 and 21 to 23; 20 has none), and the one a dungeon shows when its file names none:
#: Midlight's Deep's (the helper's `MostArtPlace`, `NoArtPlace`, `DeepPlace`).
MOST_ART_PLACE, NO_ART_PLACE, DEEP_PLACE = 23, 20, 22


def good_art_place(place) -> bool:
    """(1.23.0) Whether one of the game's places' art may be a dungeon's (the helper's `GoodArtPlace`)."""
    return _whole(place) and 0 <= place <= MOST_ART_PLACE and place != NO_ART_PLACE


@dataclass
class PlaceBattle:
    """(1.17.0) One of a battle ground's own random battles: its name, its units (its file in the place's folder, or
    one of the game's battles by its number), its map (one of the game's by its number, or one of the mod's quest maps
    by its name), where the player's units start (one `side_quests.DeployArea`, as the game's random battles start
    them on one squad) and the story's progress it waits for (variable 110 at least `story`; None, from the start)."""
    name: str
    units: object
    map: object
    deploy: list = field(default_factory=list)
    story: Optional[int] = None

    def to_json(self) -> dict:
        out = {"Name": self.name, "Units": self.units, "Map": self.map,
               "Deploy": [area.to_json() for area in self.deploy]}
        if self.story is not None:
            out["From"] = self.story
        return out


@dataclass
class TownMenu:
    """(1.18.0) A town's own menu (the helper's `TownMenu`): the game's town (by its place, 0 to 14) whose art it
    shows, or (1.19.0) its own art's files' name (a string, as a town's Picture: `art_files`); its Outfitter's items (the
    game's, by number, in the order given; (1.26.0) then the mod's own, by their names, `own`) and whether it has a
    Poachers' Den."""
    art: object
    shop: list = field(default_factory=list)
    poachers: bool = False
    own: list = field(default_factory=list)

    def to_json(self) -> dict:
        out = {"Art": self.art, "Shop": list(self.shop) + list(self.own)}
        if self.poachers:
            out["Poachers"] = True
        return out


@dataclass
class PlaceDarkened:
    """(1.20.0) What darkens a mod's town on the world map once set (the helper's `PlaceDarkened`): one of its mod's
    quests, by its folder's name, and that quest's flag (Zodi's list, his sixth: as the game darkens Ziekden Fortress
    or Brigands' Den once their event is done)."""
    quest: str
    flag: str

    def to_json(self) -> dict:
        return {"Quest": self.quest, "Flag": self.flag}


@dataclass
class PlaceFloor:
    """(1.21.0) One of a dungeon's floors (the helper's `PlaceFloor`): its name and words (the Deep's list shows a
    floor's), the quest flag it waits for (`opens`, a `PlaceDarkened`: one of its mod's quests and that quest's flag;
    None, listed from the start) and its random battles (`PlaceBattle`, one to eight). (1.24.0) Or `won`: listed once
    the floor before it is won (any one of its battles won once: Zodi's choice "Win once"), never the first floor."""
    name: str
    description: str = ""
    opens: Optional[PlaceDarkened] = None
    battles: list = field(default_factory=list)
    won: bool = False

    def to_json(self) -> dict:
        out = {"Name": self.name}
        if self.description:
            out["Description"] = self.description
        if self.won:
            out["Opens"] = FLOOR_BEFORE_WON
        elif self.opens is not None:
            out["Opens"] = self.opens.to_json()
        out["Battles"] = [b.to_json() for b in self.battles]
        return out


@dataclass
class Place:
    name: str
    town: bool
    x: int
    y: int
    picture: str = ""         # a town's own picture: its files' name
    icon: str = ""            # a town's picture of the game's: one of ICONS
    description: str = ""     # (1.16.0) what the location info shows under its name, or ""
    chance: int = 0           # (1.17.0) a battle ground's: how many of 100 arrivals start one of its battles
    battles: list = field(default_factory=list)    # (1.17.0) a battle ground's own random battles (PlaceBattle)
    menu: Optional[TownMenu] = None                # (1.18.0) a town's own menu, or None: no settlement to enter
    darkened: Optional[PlaceDarkened] = None       # (1.20.0) a town's quest flag that darkens it once set, or None
    floors: list = field(default_factory=list)     # (1.21.0) a dungeon's floors (PlaceFloor)
    dungeon: bool = False                          # (1.21.0) a dungeon (drawn as a town is: `town` True too)
    # (1.23.0) a dungeon's art: one of the game's places' by its number, or its own art's files' name
    dungeon_art: object = DEEP_PLACE

    @property
    def parts(self) -> str:
        """The part list's name the game makes a picture's parts ready by (the helper's `Parts`)."""
        return PARTS_NAME + self.picture if self.picture else ""

    def to_json(self) -> dict:
        kind = "Dungeon" if self.dungeon else "Town" if self.town else "Battle"
        data = {"Format": FORMAT, "Version": VERSION, "Name": self.name, "Kind": kind, "At": [self.x, self.y]}
        if self.picture:
            data["Picture"] = self.picture
        if self.icon:
            data["Icon"] = self.icon
        if self.description:
            data["Description"] = self.description
        if self.battles:
            data["RandomBattles"] = {"Chance": self.chance, "Battles": [b.to_json() for b in self.battles]}
        if self.menu is not None:
            data["Menu"] = self.menu.to_json()
        if self.darkened is not None:
            data["Darkened"] = self.darkened.to_json()
        if self.dungeon:
            # (1.23.0) Its art, when it isn't Midlight's Deep's (a file naming none shows the Deep's).
            if self.dungeon_art != DEEP_PLACE:
                data["Art"] = self.dungeon_art
            data["Floors"] = [f.to_json() for f in self.floors]
        return data


def place_text(place: Place) -> str:
    """The place's `place.json`, as the helper reads it."""
    return json.dumps(place.to_json(), indent=2, ensure_ascii=False) + "\n"


def good_picture(name) -> bool:
    """A picture's files' name: small letters, digits and _, 1 to 64 of them (the helper's `GoodPicture`)."""
    return isinstance(name, str) and re.fullmatch(r"[a-z0-9_]{1,64}", name) is not None


def good_description(words) -> bool:
    """(1.16.0) Words a place's description may be: 1 to 200 characters, a line break the only control character
    among them and once at the most, no space at either end (the helper's `GoodDescription`)."""
    return (isinstance(words, str) and 1 <= len(words) <= MOST_DESCRIPTION and not words[0].isspace()
            and not words[-1].isspace() and words.count("\n") <= 1
            and not any(c != "\n" and (ord(c) < 0x20 or 0x7F <= ord(c) <= 0x9F) for c in words))


def picture_name(mod_id: str, folder: str) -> str:
    """The name Mod Studio gives a town's own picture's files: of the mod and the place, so no two mods'
    meet (`msq_<mod>_<place>_uitx`, as the game names its pictures `..._uitx`)."""
    def safe(text: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "x"
    return f"msq_{safe(mod_id)}_{safe(folder)}_uitx"[:64]


def _whole(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _get(d: dict, name: str, default=None):
    for key, value in d.items():
        if key.lower() == name.lower():
            return value
    return default


def _has(d: dict, name: str) -> bool:
    return any(key.lower() == name.lower() for key in d)


def _raw(value) -> str:
    return json.dumps(value)


def read_place_text(text: str, has_file: Callable[[str], bool], folder: str = "",
                    read: Optional[Callable[[str], bytes]] = None, map_names=()) -> tuple:
    """
    (the place, problems) from a `place.json`'s text, checked as the helper
    checks it (`PlaceFile.Read`); the place is None when anything is wrong.
    `has_file` says whether the mod has a file (its path from the mod's folder);
    (1.17.0) `read` reads a file of the place's folder by name (OSError when it
    can't), `map_names` the mod's quest maps' names, which a random battle may
    name.
    """
    try:
        top = hj.loads(text)
    except ValueError as exc:
        return None, [f"its {FILE_NAME} isn't JSON ({exc})"]
    if not isinstance(top, dict):
        return None, [f"its {FILE_NAME} isn't a list of fields"]
    if hj.broken_text(top):
        return None, [f"its {FILE_NAME} {hj.BROKEN_TEXT}"]
    version = _get(top, "Version")
    if _get(top, "Format") != FORMAT or not _whole(version) or version != VERSION:
        return None, [f"its {FILE_NAME} isn't a \"{FORMAT}\" file of version {VERSION}"]
    problems = []
    name = _get(top, "Name")
    name = name if isinstance(name, str) and name else folder
    town, dungeon = True, False
    if not _has(top, "Kind"):
        problems.append("it has no Kind (Town, Battle or Dungeon)")
    else:
        kind = _get(top, "Kind")
        if kind == "Town" or kind == "Battle":
            town = kind == "Town"
        elif kind == "Dungeon":
            # (1.21.0) A dungeon: drawn as a town is, its floors its list.
            dungeon = True
        else:
            problems.append(f"its Kind is Town, Battle or Dungeon, not {_raw(kind)}")
    x = y = 0
    if not _has(top, "At"):
        problems.append("it has no At (where its middle is on the world map)")
    else:
        at = _get(top, "At")
        if (isinstance(at, list) and len(at) == 2 and all(_whole(v) for v in at)
                and 0 <= at[0] <= MAP_WIDTH and 0 <= at[1] <= MAP_HEIGHT):
            x, y = at
        else:
            problems.append(f"its At is where its middle is on the world map, two whole numbers from 0 to "
                            f"{MAP_WIDTH} and 0 to {MAP_HEIGHT}, not {_raw(at)}")
    picture = icon = ""
    has_picture, has_icon = _has(top, "Picture"), _has(top, "Icon")
    if has_picture:
        given = _get(top, "Picture")
        if good_picture(given):
            picture = given
        else:
            problems.append("its Picture is its texture's files' name (small letters, digits and _, 1 to 64 of them), "
                            f"not {_raw(given)}")
    if has_icon:
        given = _get(top, "Icon")
        if given in ICONS:
            icon = given
        else:
            problems.append(f"its Icon is one of the game's town textures ({', '.join(ICONS)}), not {_raw(given)}")
    # (1.16.0) Its description, if it has one.
    description = ""
    if _has(top, "Description"):
        given = _get(top, "Description")
        if good_description(given):
            description = given
        else:
            problems.append(f"its Description is words of 1 to {MOST_DESCRIPTION} characters, at most one line break "
                            f"among them, not {json.dumps(given, ensure_ascii=False)}")
    # (1.17.0) A battle ground's own random battles, if it has them.
    chance, battles = 0, []
    has_battles = _has(top, "RandomBattles")
    if has_battles:
        chance = _read_random_battles(_get(top, "RandomBattles"), read, set(map_names), battles, problems)
    # (1.18.0) A town's own menu, if it has one.
    menu = None
    has_menu = _has(top, "Menu")
    if has_menu:
        menu = _read_menu(_get(top, "Menu"), problems)
    # (1.20.0) What darkens a town, if anything does.
    darkened = None
    has_darkened = _has(top, "Darkened")
    if has_darkened:
        darkened = _read_darkened(_get(top, "Darkened"), problems)
    # (1.21.0) A dungeon's floors.
    floors = []
    has_floors = _has(top, "Floors")
    if has_floors and dungeon:
        _read_floors(_get(top, "Floors"), read, set(map_names), floors, problems)
    # (1.23.0) A dungeon's art: one of the game's places' (by its number), or its own art's files' name.
    dungeon_art = DEEP_PLACE
    has_art = _has(top, "Art")
    if has_art and dungeon:
        given = _get(top, "Art")
        if isinstance(given, str) and good_picture(given):
            dungeon_art = given
        elif not good_art_place(given):
            problems.append(f"its Art is the game's place whose art its list shows (by its number: 0 to "
                            f"{NO_ART_PLACE - 1}, or {NO_ART_PLACE + 1} to {MOST_ART_PLACE}), or its own art's files' "
                            f"name (small letters, digits and _, 1 to 64 of them), not {_whole_json(top, 'Art')}")
        else:
            dungeon_art = given
    if not problems:
        if dungeon and not has_floors:
            problems.append(f"a dungeon has Floors (1 to {MOST_FLOORS}): the list choosing it shows")
        elif not dungeon and has_floors:
            problems.append("only a dungeon has Floors")
        elif dungeon and has_battles:
            problems.append("a dungeon has no RandomBattles: its floors' battles are its own")
        elif dungeon and has_menu:
            problems.append("a dungeon has no Menu: its floors are the list choosing it shows")
        elif not dungeon and has_art:
            problems.append("only a dungeon has Art: a town's is its Menu's")
        elif town and has_battles:
            problems.append("a town has no random battles: RandomBattles is a battle ground's")
        elif not town and has_menu:
            problems.append("a battle ground has no Menu: Enter Settlement is a town's")
        elif not town and has_darkened:
            problems.append("a battle ground isn't darkened: Darkened is a town's")
        elif not town and (has_picture or has_icon):
            problems.append("a battle ground shows the game's point: it has no Picture or Icon")
        elif town and has_picture and has_icon:
            problems.append("a town shows its own Picture or an Icon of the game's, not both")
        elif town and not has_picture and not has_icon:
            problems.append("a town shows its own Picture or an Icon of the game's")
        elif picture and not (has_file(f"{TEXTURE_FOLDER}/{picture}.tex")
                              and has_file(f"{PARTS_FOLDER}/{picture}.utexpt")):
            problems.append(f"its texture's files aren't in the mod ({TEXTURE_FOLDER}/{picture}.tex and "
                            f"{PARTS_FOLDER}/{picture}.utexpt)")
        elif menu is not None and isinstance(menu.art, str) and not (
                has_file(f"{TEXTURE_FOLDER}/{menu.art}.tex") and has_file(f"{PARTS_FOLDER}/{menu.art}.utexpt")):
            # (1.19.0) A menu's own art: its two files beside a town's picture's.
            problems.append(f"its Menu's art's files aren't in the mod ({TEXTURE_FOLDER}/{menu.art}.tex and "
                            f"{PARTS_FOLDER}/{menu.art}.utexpt)")
        elif isinstance(dungeon_art, str) and not (has_file(f"{TEXTURE_FOLDER}/{dungeon_art}.tex")
                                                   and has_file(f"{PARTS_FOLDER}/{dungeon_art}.utexpt")):
            # (1.23.0) A dungeon's own art: its two files as a menu's own art's.
            problems.append(f"its art's files aren't in the mod ({TEXTURE_FOLDER}/{dungeon_art}.tex and "
                            f"{PARTS_FOLDER}/{dungeon_art}.utexpt)")
    if problems:
        return None, problems
    return Place(name, town, x, y, picture, icon, description, chance, battles, menu, darkened, floors, dungeon,
                 dungeon_art), []


def _read_darkened(given, problems: list) -> Optional[PlaceDarkened]:
    """(1.20.0) A town's Darkened (the helper's `ReadDarkened`): its Quest (one of its mod's quests, by its folder's
    name) and that quest's Flag, each a name as a quest's are."""
    if not isinstance(given, dict):
        problems.append("its Darkened isn't a list of fields")
        return None
    quest, flag = _get(given, "Quest"), _get(given, "Flag")
    if hj.good_name(quest) and hj.good_name(flag):
        return PlaceDarkened(quest, flag)
    problems.append("its Darkened is the quest and its flag that darken it once set, each by its name (Quest and Flag: "
                    "letters, digits, spaces, underscores and hyphens, 1 to 64 of them), not Quest "
                    f"{_whole_json(given, 'Quest')} and Flag {_whole_json(given, 'Flag')}")
    return None


def _whole_json(d: dict, name: str) -> str:
    """A field as the helper says it (its JSON), "none" when it isn't there."""
    return json.dumps(_get(d, name), ensure_ascii=False) if _has(d, name) else "none"


def _read_menu(given, problems: list) -> Optional[TownMenu]:
    """(1.18.0) A town's Menu (the helper's `ReadMenu`): its Art (the game's town whose art it shows, 0 to 14), its
    Shop (the Outfitter's items, each one of the game's by number, 1 to 255, or (1.26.0) one of the mod's own items by
    its name, once; none an empty Outfitter) and, if it has one, Poachers (true or false)."""
    from mod_studio import mod_items as mi
    if not isinstance(given, dict):
        problems.append("its Menu isn't a list of fields")
        return None
    art = _get(given, "Art")
    if not (isinstance(art, str) and good_picture(art)) and (not _whole(art) or not 0 <= art <= MOST_ART_TOWN):
        problems.append(f"its Menu's Art is the game's town (by its place, 0 to {MOST_ART_TOWN}) whose art its menu "
                        "shows, or its own art's files' name (small letters, digits and _, 1 to 64 of them), not "
                        f"{_whole_json(given, 'Art')}")
        return None
    listed = _get(given, "Shop")
    shop, own = [], []
    good = isinstance(listed, list)
    if good:
        for item in listed:
            # (1.26.0) Or one of the mod's own items, by its name (the helper's `ItemFile.GoodName`).
            if isinstance(item, str) and mi.good_name(item) and item not in own:
                own.append(item)
                continue
            if not _whole(item) or not 1 <= item <= MOST_ITEM or item in shop:
                good = False
                break
            shop.append(item)
    if not good:
        problems.append(f"its Menu's Shop is the Outfitter's items, each one of the game's by its number (1 to "
                        f"{MOST_ITEM}) or one of the mod's own items by its name, and once, not "
                        f"{_whole_json(given, 'Shop')}")
        return None
    poachers = False
    if _has(given, "Poachers"):
        den = _get(given, "Poachers")
        if not isinstance(den, bool):
            problems.append(f"its Menu's Poachers is true or false, not {json.dumps(den, ensure_ascii=False)}")
            return None
        poachers = den
    return TownMenu(art, shop, poachers, own)


def _read_floors(given, read, map_names: set, floors: list, problems: list) -> None:
    """(1.21.0) A dungeon's Floors (the helper's `ReadFloors`): 1 to 10, each its Name (1 to 24 characters, as a quest's
    names are), if it has one its Description (as a place's), if it waits for one Opens (a quest's flag, as Darkened;
    1.24.0, or "FloorBeforeWon": the floor before it won, never the first floor's) and its Battles (1 to 8:
    `_read_place_battle`), every battle named once in the whole dungeon."""
    from mod_studio import side_quests as sq
    if not isinstance(given, list) or not 1 <= len(given) <= MOST_FLOORS:
        problems.append(f"its Floors are 1 to {MOST_FLOORS} floors, not {json.dumps(given, ensure_ascii=False)}")
        return
    named = set()
    for f in given:
        name = _get(f, "Name", "") if isinstance(f, dict) else ""
        if not hj.good_name(name) or len(name) > MOST_FLOOR_NAME:
            problems.append(f"a floor's Name is 1 to {MOST_FLOOR_NAME} letters, digits, spaces, underscores and "
                            "hyphens, not "
                            f"{_whole_json(f, 'Name') if isinstance(f, dict) else json.dumps(f, ensure_ascii=False)}")
            return
        if any(other.name.lower() == name.lower() for other in floors):
            problems.append(f"the floor {name} is named twice")
            return
        description = ""
        if _has(f, "Description"):
            words = _get(f, "Description")
            if not isinstance(words, str) or not good_description(words):
                problems.append(f"the floor {name}'s Description is words of 1 to {MOST_DESCRIPTION} characters, at "
                                f"most one line break among them, not {json.dumps(words, ensure_ascii=False)}")
                return
            description = words
        opens = None
        won = False
        if _has(f, "Opens") and _get(f, "Opens") == FLOOR_BEFORE_WON:
            # (1.24.0) Listed once the floor before it is won: never the first floor, which has none.
            if not floors:
                problems.append(f"the floor {name} is the dungeon's first: it has no floor before it to be won, so its "
                                f'Opens can\'t be "{FLOOR_BEFORE_WON}"')
                return
            won = True
        elif _has(f, "Opens"):
            opens = _read_darkened(_get(f, "Opens"), [])
            if opens is None:
                problems.append(f"the floor {name}'s Opens is the quest and its flag that list it once set, each by its "
                                "name (Quest and Flag: letters, digits, spaces, underscores and hyphens, 1 to 64 of "
                                f'them), or "{FLOOR_BEFORE_WON}" (listed once the floor before it is won), not '
                                f"{json.dumps(_get(f, 'Opens'), ensure_ascii=False)}")
                return
        listed = _get(f, "Battles")
        if not isinstance(listed, list) or not 1 <= len(listed) <= MOST_BATTLES:
            problems.append(f"the floor {name}'s Battles are 1 to {MOST_BATTLES} battles, not "
                            f"{_whole_json(f, 'Battles')}")
            return
        battles = []
        for b in listed:
            battle = _read_place_battle(b, read, map_names, problems, sq)
            if battle is None:
                return
            if battle.name in named:
                problems.append(f"the random battle {battle.name} is named twice")
                return
            named.add(battle.name)
            battles.append(battle)
        floors.append(PlaceFloor(name, description, opens, battles, won))


def _read_random_battles(given, read, map_names: set, battles: list, problems: list) -> int:
    """(1.17.0) A battle ground's RandomBattles (the helper's `ReadRandomBattles`): its Chance (how many of 100 arrivals
    start a battle, 0 to 100) and its Battles (1 to 8: `_read_place_battle`), into `battles`; returns the chance."""
    from mod_studio import side_quests as sq
    if not isinstance(given, dict):
        problems.append("its RandomBattles isn't a list of fields")
        return 0
    chance = _get(given, "Chance")
    if not _whole(chance) or not 0 <= chance <= MOST_CHANCE:
        problems.append(f"its RandomBattles' Chance is how many of 100 arrivals start a battle, 0 to {MOST_CHANCE}, "
                        f"not {_whole_json(given, 'Chance')}")
        return 0
    listed = _get(given, "Battles")
    if not isinstance(listed, list) or not 1 <= len(listed) <= MOST_BATTLES:
        problems.append(f"its RandomBattles' Battles are 1 to {MOST_BATTLES} battles, not "
                        f"{_whole_json(given, 'Battles')}")
        return 0
    for b in listed:
        battle = _read_place_battle(b, read, map_names, problems, sq)
        if battle is None:
            return 0
        if any(other.name == battle.name for other in battles):
            problems.append(f"the random battle {battle.name} is named twice")
            return 0
        battles.append(battle)
    return chance


def _read_place_battle(b, read, map_names: set, problems: list, sq) -> Optional[PlaceBattle]:
    """(1.17.0) One random battle (the helper's `ReadPlaceBattle`): its Name, its Units (its file in the place's folder
    or one of the game's battles by number), its Map (one of the game's by number or one of the mod's quest maps by
    name), its Deploy (one deploy area) and, if it waits for the story, From (variable 110 at least it)."""
    name = _get(b, "Name", "") if isinstance(b, dict) else ""
    if not hj.good_name(name):
        problems.append(f"a random battle's name isn't one: {json.dumps(b, ensure_ascii=False)}")
        return None
    who = f"the random battle {name}"
    units = _get(b, "Units")
    if isinstance(units, str):
        if sq._bad_path(units):
            problems.append(f"{who} names no file in its folder")
            return None
        try:
            if read is None:
                raise OSError("its folder isn't read here")
            block = read(units)
        except OSError as exc:
            problems.append(f"{who}'s file {units} can't be read ({exc})")
            return None
        if len(block) != sq.BATTLE_BYTES:
            problems.append(f"{who}'s units are {len(block)} bytes, not {sq.BATTLE_BYTES} (16 units as the game's "
                            "battles hold them)")
            return None
    elif not _whole(units) or not 1 <= units <= sq.MOST_GAME_BATTLE:
        problems.append(f"{who}'s Units are its units' file in the place's folder, or one of the game's battles by its "
                        f"number (1 to {sq.MOST_GAME_BATTLE}), not {_whole_json(b, 'Units')}")
        return None
    map_value = _get(b, "Map")
    if not ((_whole(map_value) and 1 <= map_value <= sq.MOST_GAME_MAP)
            or (isinstance(map_value, str) and map_value in map_names)):
        problems.append(f"{who}'s Map is one of the game's maps by its number (1 to {sq.MOST_GAME_MAP}) or one of the "
                        f"mod's quest maps by its name, not {_whole_json(b, 'Map')}")
        return None
    if not _has(b, "Deploy"):
        problems.append(f"{who} gives no Deploy (where the player's units start: one deploy area)")
        return None
    areas = _get(b, "Deploy")
    if not isinstance(areas, list) or len(areas) != 1:
        problems.append(f"{who}'s Deploy is one deploy area: a random battle starts the player's units on one, as the "
                        "game's own do")
        return None
    deploy = []
    if not sq._read_deploy(name, areas, deploy, problems, who=who):
        return None
    story = None
    if _has(b, "From"):
        given = _get(b, "From")
        if not _whole(given) or not 1 <= given <= MOST_FROM:
            problems.append(f"{who}'s From is the story's progress it waits for, 1 to {MOST_FROM}, not "
                            f"{_whole_json(b, 'From')}")
            return None
        story = given
    return PlaceBattle(name, units, map_value, deploy, story)


def read_mod_places(mod_folder) -> list:
    """Every place of a mod, in its folders' order: (folder, the place or None, problems); a place named as an
    earlier one of the mod is left out (the helper's `ReadMod`)."""
    root = Path(mod_folder) / FOLDER
    out = []
    if not root.is_dir():
        return out
    names = set()
    map_names = qm.map_names(mod_folder)
    for sub in sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.name):
        file = sub / FILE_NAME
        if not file.is_file():
            continue
        try:
            text = hj.read_text(file)
        except OSError as exc:
            out.append((sub.name, None, [f"it can't be read ({exc})"]))
            continue
        place, problems = read_place_text(text, lambda path: (Path(mod_folder) / path).is_file(), sub.name,
                                          lambda name, s=sub: (s / name).read_bytes(), map_names)
        if place is not None and place.name in names:
            place, problems = None, [f"another of the mod's places is named {place.name}"]
        if place is not None:
            names.add(place.name)
        out.append((sub.name, place, problems))
    return out


def picture_files(picture, name: str) -> tuple:
    """A town's own picture's two files from a picture (PIL, 172 x 172): its texture (Mod Studio's own
    writer, one RGBA picture) and its part list naming it at the game's path, the picture its part 1 with a
    clear pixel round it. (tex bytes, utexpt bytes)."""
    from PIL import Image

    from mod_studio import texture_data as td
    from mod_studio import uib
    image = picture.convert("RGBA")
    if image.size != PICTURE_SIZE:
        raise ValueError(f"a town's picture is {PICTURE_SIZE[0]} x {PICTURE_SIZE[1]}, as the game's are, not "
                         f"{image.size[0]} x {image.size[1]}")
    sheet = Image.new("RGBA", PICTURE_SHEET, (0, 0, 0, 0))
    sheet.paste(image, PICTURE_PART[:2])
    texture = f"ui/ffto/worldmap/texture/{name}.tex"
    parts = uib.part_list_file(texture, [("TexturePart", (0, 0) + PICTURE_SHEET), ("Icon", PICTURE_PART)])
    return td.rgba_tex(sheet), parts


def art_name(mod_id: str, folder: str) -> str:
    """(1.19.0) The name Mod Studio gives a town's menu's own art's files: of the mod and the place as its picture's,
    then `__art_uitx` (`msq_<mod>_<place>__art_uitx`): a picture's name never holds two `_` together, so no art's
    meets a picture's, and no two places' meet."""
    def safe(text: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "x"
    return f"msq_{safe(mod_id)}_{safe(folder)}"[:64 - len("__art_uitx")] + "__art_uitx"


def art_files(picture, name: str) -> tuple:
    """(1.19.0) A town's menu's own art's two files from a picture (PIL, 680 x 452): its texture (one RGBA picture)
    and its part list naming it at the game's path, the art its part 0 (the thumbnail's own part); (1.23.0) a
    dungeon's own art's the same. (tex bytes, utexpt bytes)."""
    from mod_studio import texture_data as td
    from mod_studio import uib
    image = picture.convert("RGBA")
    if image.size != ART_SIZE:
        raise ValueError(f"a town's art is {ART_SIZE[0]} x {ART_SIZE[1]}, as the game's are shown, not "
                         f"{image.size[0]} x {image.size[1]}")
    texture = f"ui/ffto/worldmap/texture/{name}.tex"
    return td.rgba_tex(image), uib.part_list_file(texture, [("TexturePart", (0, 0) + ART_SIZE)])


def write_place(mod_folder, folder: str, place: Place, picture=None, files=None, art=None) -> list:
    """
    Writes a place into `<mod_folder>/ModStudioPlaces/<folder>/place.json`, and a town's own picture
    (`picture`, 172 x 172) as its two files at the game's paths in the mod; (1.17.0) and `files` (`{name: bytes}`:
    its random battles' units) beside its file; (1.19.0) and its menu's own art (`art`, 680 x 452) as its two files
    beside its picture's ((1.23.0) a dungeon's own art the same). Returns the paths written.
    """
    if not isinstance(folder, str) or not folder or folder.strip() != folder or not all(
            c.isalnum() or c in " _-" for c in folder):
        raise ValueError(f"a place's folder is named as a quest's is: {folder!r}")
    written = []
    if picture is not None:
        if not place.picture:
            raise ValueError("a picture given for a place that names none")
        tex, parts = picture_files(picture, place.picture)
        for path, data in ((Path(mod_folder) / TEXTURE_FOLDER / f"{place.picture}.tex", tex),
                           (Path(mod_folder) / PARTS_FOLDER / f"{place.picture}.utexpt", parts)):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            written.append(path)
    if art is not None:
        own = (place.dungeon_art if place.dungeon else place.menu.art if place.menu is not None else None)
        if not isinstance(own, str):
            raise ValueError("an art given for a place whose menu names none" if not place.dungeon
                             else "an art given for a dungeon that names none")
        tex, parts = art_files(art, own)
        for path, data in ((Path(mod_folder) / TEXTURE_FOLDER / f"{own}.tex", tex),
                           (Path(mod_folder) / PARTS_FOLDER / f"{own}.utexpt", parts)):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            written.append(path)
    root = Path(mod_folder) / FOLDER / folder
    root.mkdir(parents=True, exist_ok=True)
    for name, data in sorted((files or {}).items()):
        if not isinstance(name, str) or not name or "/" in name or "\\" in name or name == FILE_NAME or ".." in name:
            raise ValueError(f"a place's file is named in its folder: {name!r}")
        own = root / name
        own.write_bytes(bytes(data))
        written.append(own)
    path = root / FILE_NAME
    path.write_text(place_text(place), encoding="utf-8")
    written.append(path)
    return written


def overlaps(place: Place, pieces: list, margin: int = 0) -> list:
    """The game's places' pieces (name, x, y, width, height: the layout's Bases) a place's own would overlap
    (a town's 172 x 172, a battle ground's 64 x 64, about its middle), `margin` pixels round it."""
    size = 172 if place.town else 64
    x0, y0 = place.x - size / 2 - margin, place.y - size / 2 - margin
    x1, y1 = place.x + size / 2 + margin, place.y + size / 2 + margin
    return [name for name, x, y, w, h in pieces if not (x1 <= x or x0 >= x + w or y1 <= y or y0 >= y + h)]

