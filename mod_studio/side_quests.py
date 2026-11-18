"""
Side quests (Zodi's goal, 26 October: "Adding new events on new maps for new
battles while maintaining compatibility so different modders can create
hundreds of new side quests that users can have loaded and can play").

**A quest** is a folder of its own in a mod, `ModStudioQuests/<quest>/`,
holding `quest.json` (`quest_text`) and its events' scripts. The file names
everything the quest adds, its events and its flags, and gives numbers only
for the game's own things: maps, music, a world map place, the story's
progress. A modder never chooses a number (his rule): Mod Studio Framework
(the helper, since 1.1.0, `helper/ModStudioEventSetup/QuestFile.cs` reads this
same file and says the same problems) gives each name a number of the
game's as the game starts, the same every time, and never one number to two
names, so two modders who never met can each name an event "intro" and a
flag "seen".

**What the helper does with it**: each event gets an event number nothing
of the game's or another mod's uses, and a setup record (its map, music,
units, what follows) in the empty slots after the game's; each event that
a start loads also gets an opening, as every world map scene of the game
has (a three-instruction script and battle rules that start the scene once
the map is in); each flag a bit of the game's saved variables that nothing
uses, numbered from 4096; each start a chain at its world map place after
every chain the place has (the story's first), whose conditions are the
world map's own tests. An event's words are a text file at the mod's
`FFTIVC/data/enhanced/` + its `Words` path with the language put in
(`words_file`), in the game's folder for scenes' words.

**Battles** (1.2.0): a quest's own battles (`Battles`) are files of 640
bytes in its folder, 16 units as the game's battle files hold a battle,
each given a battle number from 4096 as the game starts; the helper hands
the game a quest battle's units when it loads it. A battle event (`Battle`:
its units, the event that plays as it starts, the one that plays once every
enemy is beaten) has no script of its own: the helper gives it the game's
battles' three instructions, battle rules that play its two events as the
game's battles do, a deploy prompt like the game's for its map, and its
units a row of the game's battles' units table; a start loads it as the
world map loads the game's battles. Its two events play with its setup
(map, music, units), the won one going back to the world map.

**How a battle is won and lost** (Zodi's choices of 28 October; the
helper's 1.12.0): a battle event's `WonWhen` says it is won once one of
its units is beaten (`{"Beaten": unit}`), once one is worn down to a
share of its HP (`{"WornDown": unit, "Share": 1 to 99}`) or once Ramza
stands on a tile (`{"OnTile": [x, y, level]}`, or every enemy beaten);
without one, once every enemy is beaten. `Protect` names a unit it is
lost without and `Lost` the event that plays then, after which the game
starts over. Its `Objective`, the quest's own words, is shown by its
start event where that event's `ObjectiveInScript` says (the byte after a
DisplayConditions, 0x78). A unit named so is one of its quest's own
battle's (1 to 16 by place), always on the field, its unit ID one the
game's rules can name (1 to 52, 100 to 103, 128 to 139) and no other
unit's.

**One step after another** (Zodi, 26 October, after test 16): a scene
whose `NextEvent` is one of the quest's battle events goes straight into
the battle on the same visit, as the game's scene 69 goes into its battle
70 (the scene's record names the battle next, 0x81 what follows it); and a
quest's later steps start elsewhere on the map by its own flags (a start
at another place, its conditions the flags the step before set). Since
1.2.2 a quest's event waiting where the player stands never stops travel
on (the game's own events let you go back only the way you came).

**Passing through** (Zodi, 26 October: "these should all be optional
features for modders if they want them"; the helper's 1.2.4): a start's
event waits until the player chooses its place (`"Passing": "Waits"`, the
default), so a travel passing through goes on; or it stops a travel passing
through and plays there, as the game's own events do (`"Passing":
"Stops"`). The helper makes a waiting start's last condition a variable of
its own (4095) that it answers from the travel's state: 1 while a travel
passes through the place.

**Markers** (Zodi, 26 October: "there should be a quest marker for every
quest if the modders choses to have it, the marker should be a different
hue that they can pick"; the helper's 1.2.5): a quest whose file gives
`"Marker": "#RRGGBB"` has a marker of that color on the world map at each
place where one of its starts waits, its conditions holding as the world
map tests them (but for passing through), where the game shows the place
and no marker of its own. Where two quests wait at one place, the first
loaded has it. A quest without a Marker has none.

**A mod's own place** (Zodi, 27 October, "Quests at new places"; the
helper's 1.8.0): a start's `Place` may be one of its mod's own places by
its name (its `ModStudioPlaces`, `map_places`), as a road's `From` and
`To` may; the helper numbers the place as it numbers the mods' places and
adds the start's chain at that number, and shows its Marker over it.

**A quest's own map** (Zodi, 27 October, after his test 32; the helper's
1.10.0): an event's setup `Map` may be one of its mod's quest maps by its
name (its `ModStudioMaps`, `quest_maps`); the helper numbers the quest maps
from 129 as the game starts and gives the event's setup record that number.
By number, a setup's `Map` is one of the game's 0 to 127.

**Copied from the game's** (the helper's 1.11.0): an event may give
`"From"`, the game's event it was copied from (1 to 886). The remaster
plays some of a map's animations by the event playing (a door opens for
event 160's record 0, not for any other event's), so the helper has a
copied event play them as the event it was copied from. Mod Studio gives
every scene it copies its `From`.

**In a script** a flag is a variable (16 bits) of the variable instructions
(0xB0 to 0xBE: the first operand of each, and the second of the odd ones,
which read a second variable); `flag_places` lists where those are, and
`FlagsInScript` says which flag's number goes where. Nothing else in a
script holds a flag: the world map and the variable instructions go through
the two functions the helper watches.

**The story** (1.2.1): a side quest never moves it. A story scene copied
into a quest keeps the instructions that do (`story_changes`): the game's
progress (E9), which the helper leaves as it was while a quest's event
plays, as it does variable 110, the story's progress; and a progress flag
(EA), which it can't, so `story_problem` refuses it.

**Ramza** (Zodi's test 64, his choice "Framework finds him"; the helper's
1.30.0): the game's scenes name Ramza by his character identity, 1 in
chapter 1, 2 in chapters 2 and 3, 3 in chapter 4 (`RAMZAS`), and a quest
may play in any of them. An event's `RamzaInScript` lists the places in its
script where a unit is Ramza (each a unit's two bytes, written as one of
the three, `ramza_places`); as the helper hands the game the script, it
writes there the identity of the Ramza in the party, so he speaks, stands
and marches as himself whatever the chapter.

**A reward** (Zodi's ask of 3 November, "A reward as a quest ends", as
WotL Restoration gives the Tynar Rouge after Agrias's birthday; his choice
"Its last step only"; the helper's 1.31.0): an event's `Reward` names a
flag its script sets (`Reward.flag`), gil and items (the game's by number,
the mod's own by name, each with a count); the helper gives them as the
flag goes from 0 to 1, which the game refuses while a scene is replayed,
so a reward comes once. A unit joining is the scene's own: its unit
marked to join and (Zodi's test 66) the game's party changes as the scene
ends (DisplayConditions 7), its New Party Member screen asking (1.31.0's
CallFunction 1, the silent join, still read).

Nothing here imports Qt.
"""
from __future__ import annotations

import json
import re
import struct
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from mod_studio import event_scripts as es
from mod_studio import event_setup as su
from mod_studio import helper_json as hj
from mod_studio import map_places as mp
from mod_studio import mod_items as mi
from mod_studio import quest_maps as qm

#: Where a mod keeps its quests, one folder each; the file each holds.
FOLDER = "ModStudioQuests"
FILE_NAME = "quest.json"
FORMAT = "Mod Studio side quest"
VERSION = 1
#: The world map's places (the game's `EnhancedWorldEvent` keys 0 to 46).
PLACES = 47
#: The most a script may be: the game reads it into 10,240 bytes after a 4-byte size.
MOST_SCRIPT = 0x2800 - 4
#: The most conditions a start has: the world map writes a place's chain into 256 words.
MOST_CONDITIONS = 16
#: The setup fields a quest's event gives (`EventSetup.json`'s names); its next
#: event is named, and battle rules are the helper's to give.
SETUP_FIELDS = ("Map", "Weather", "Arrangement", "Night", "Music1", "Music2", "EnemyBattle", "DeployArea1",
                "DeployArea2", "Portrait", "PortraitUnit", "SceneUnits", "RamzaRequired", "AfterEvent")
#: The tests a start's condition makes of a game variable; a flag's is "Is" 0 or 1.
TESTS = ("Is", "AtLeast", "AtMost")
#: Where an event's words go: the game's folder for scenes' words.
WORDS_FOLDER = "nxd/text/scenario"
#: The variable instructions (see the module's notes).
VARIABLE_OPS = range(0xB0, 0xBF)
#: The setup fields that may name one of the quest's battles instead of a game's battle number.
BATTLE_FIELDS = ("EnemyBattle", "SceneUnits")
#: A battle's units: 16 units of 40 bytes, as the game's battle files (ENTD) hold a battle.
BATTLE_BYTES = 640
#: (1.10.0) The game's maps a quest's setup may give by number: past them, a quest map's, by its name.
MOST_GAME_MAP = 127
#: The game's battles a quest may fight by number (a setup record's signed 16 bits).
MOST_GAME_BATTLE = 0x7FFF
#: (1.11.0) The game's events a quest's event may say it was copied from (`From`): the remaster keys some of a map's
#: animations (its doors among them) to the event playing, so a copy plays them as the event it was copied from.
MOST_GAME_EVENT = 886
#: (1.12.0) How a battle is won (its `WonWhen`): every enemy beaten (the default, no WonWhen), one of its units beaten,
#: one of its units down to a share of its HP, or Ramza on a tile (or every enemy beaten).
ENEMIES, BEATEN, WORN_DOWN, ON_TILE = "Enemies", "Beaten", "WornDown", "OnTile"
#: (1.12.0) A battle's units (16 of 40 bytes, the sprite set first: 0 an empty place): where a unit's ID and presence
#: are (its unit ID at 32; at 24, Always Present 0x80 and Randomly Present 0x40); the most percent of a unit's HP a
#: WornDown gives, a tile's most x and y, the most characters an objective's words have (the helper's own numbers).
UNITS, UNIT_BYTES, UNIT_ID_AT, PRESENCE_AT, PRESENCE_MASK, ALWAYS_PRESENT = 16, 40, 32, 24, 0xC0, 0x80
MOST_SHARE, MOST_TILE, MOST_OBJECTIVE = 99, 255, 64
#: (1.12.1) A unit's first flags (byte 1) and Load Formation among them (0x08): the game fills such a unit from the
#: player's own units as the battle starts, and a side quest's battle that names it in its rules found an empty place
#: there at 0 HP (Delita in Gariland's battle, his test 39).
FLAGS_AT, LOAD_FORMATION = 1, 0x08
#: (1.12.0) DisplayConditions, the instruction whose byte after it an event's `ObjectiveInScript` names.
DISPLAY_CONDITIONS = 0x78
#: (1.30.0) Ramza's character identities (fft_decomp's `unit_identity.h`): 1 in chapter 1, 2 in chapters 2 and 3, 3
#: in chapter 4. The game's scenes name him by the one of their chapter (its 42 scenes of chapter 1 by 1, 99 by 2, 84
#: by 3, none by two of them: `dev/research/sidequests/ramza.py`), a deployed Ramza keeps it as his unit ID (its
#: `units_init`), and a party member's first byte is its identity (`unit_init.c`). An event's `RamzaInScript` names
#: places holding one of them, which the helper gives the party's Ramza's as it hands the game the script.
RAMZAS = (1, 2, 3)
#: (1.30.0) The identity a script Mod Studio makes names Ramza by until the helper gives it the party's: chapter 1's.
RAMZA = RAMZAS[0]
#: (1.31.0) A reward's most gil (the war funds' own most: the game's add of them, 0x284684, stops them at 99,999,999),
#: most items, and most of one item (the bag holds 99 of an item); the variable commands that set its flag (0xB0 to
#: 0xBE, add to clear: fft_decomp's `script_instruction.h`).
MOST_GIL, MOST_REWARD_ITEMS, MOST_OF_AN_ITEM = 99_999_999, 8, 99
FIRST_VARIABLE_COMMAND, LAST_VARIABLE_COMMAND = 0xB0, 0xBE
#: (1.31.0, Zodi's test 65: "there should be three events. One at start, one mid battle mostly for dialogue, and then
#: the ending event"; his choice "Either, picked on the card") A battle's scenes during it at the most, when each plays
#: (as its unit's turn comes, or as its unit's HP falls to a share of its most, 0 beaten), and the variable each sets
#: as it ends, in their order, which its rules test so that it plays once a battle: the scenario's own variables the
#: game's battles guard their scenes with (127, 126, 125, 129), zeroed each time a battle loads (fft_decomp's
#: `EVENT_SCRIPT_VAR_SCENARIO_LOCAL_FIRST`, 0x70 to 0x8F); the most rules a battle has (the game runs 16).
MOST_DURING, MOST_RULES, MOST_SHARE_DURING = 4, 16, 99
TURN, HP = "Turn", "Hp"
GUARDS = (127, 126, 125, 129)


@dataclass
class Condition:
    """One condition of a start: a game variable (1 to 1023) tested against a number
    (0 to 65535), a quest flag that is 0 or 1, or a character (1 to 255) in the party."""
    kind: str                      # "Variable", "Flag" or "Character"
    variable: int = 0
    flag: str = ""
    test: str = "Is"
    value: int = 0

    def to_json(self) -> dict:
        if self.kind == "Character":
            return {"Character": self.value}
        if self.kind == "Flag":
            return {"Flag": self.flag, "Is": self.value}
        return {"Variable": self.variable, self.test: self.value}


@dataclass
class Start:
    """Where and when a quest starts: a world map place, its conditions, its event; and
    whether that event stops a travel passing through the place, as the game's own events do
    ("Passing": "Stops"), or waits until the place is chosen ("Waits", the default; Mod
    Studio Framework 1.2.4). The place is one of the game's by its number (0 to 46), or
    (1.8.0) one of the mod's own places by its name. (1.25.0) A start whose place is one of
    the mod's own dungeons may wait at one of its floors (`floor`, its name): its event
    plays as that floor is chosen, in place of the floor's battle, while its conditions
    hold (Zodi, 2 November: Midlight's Deep's END and its boss battle)."""
    place: object                  # a game place's number, or one of the mod's places' names
    event: str
    when: list = field(default_factory=list)
    stops_passing: bool = False
    floor: str = ""

    def to_json(self) -> dict:
        out = {"Place": self.place}
        if self.floor:
            out["Floor"] = self.floor
        out.update({"When": [c.to_json() for c in self.when], "Event": self.event,
                    "Passing": "Stops" if self.stops_passing else "Waits"})
        return out


#: (1.14.0) A battle's own deploy areas (its Battle's `Deploy`): one or two, each up to 25 squares within 5 by 5, 1 to
#: 5 of the player's units starting there, facing one of the four ways (a unit's facing in the game's battle files: 0
#: south, 1 west, 2 north, 3 east), on the squares' lower level or upper. The helper gives each a squad of the
#: program's, numbered past its 768 (`DeploySquads.cs`).
MOST_DEPLOY_AREAS, MOST_SQUARES, MOST_DEPLOY_UNITS, MOST_SPAN = 2, 25, 5, 5
FACINGS = ("South", "West", "North", "East")
#: The squads' own: past the game's 768, as the helper numbers them (`DeploySquads.FirstOwn` and `LastOwn`); a squad's
#: 12 bytes (`deploy_squad_t`, `event_scripts.Squad`).
FIRST_SQUAD, LAST_SQUAD, SQUAD_BYTES = 0x300, 4095, 12


@dataclass
class DeployArea:
    """(1.14.0) One of a battle's own deploy areas: its squares (`(x, y)` on its map), how many of the player's units
    start there, which way they face (0 to 3, `FACINGS`) and whether on the squares' upper level."""
    squares: list = field(default_factory=list)
    units: int = 5
    facing: int = 2
    upper: bool = False

    def to_json(self) -> dict:
        out = {"Squares": [[x, y] for x, y in self.squares], "Units": self.units, "Facing": FACINGS[self.facing]}
        if self.upper:
            out["Upper"] = True
        return out


def squad_bytes(area: DeployArea, number: int, map_number: int) -> bytes:
    """The squad the helper gives a deploy area (`DeployArea.Squad`, word for word): its middle tile the squares' box's,
    its grid the game's orientation 0 turned for the facing (the turn the game adds for it: the facing is (0, 3, 2, 1)
    by turn, as `event_scripts.squad_tiles` lays a squad), each square's bit its place in it; its level, how many units,
    its map and its number."""
    xs = [x for x, _y in area.squares]
    ys = [y for _x, y in area.squares]
    mx, my = (min(xs) + max(xs)) // 2, (min(ys) + max(ys)) // 2
    turn = (0, 3, 2, 1).index(area.facing)
    tiles = 0
    for x, y in area.squares:
        row, column = {0: (y - my + 2, mx - x + 2), 1: (mx - x + 2, my - y + 2), 2: (my - y + 2, x - mx + 2),
                       3: (x - mx + 2, y - my + 2)}[turn]
        tiles |= 1 << (row * 5 + column)
    return struct.pack("<IBBBBBBH", tiles, mx & 0xFF, my & 0xFF, 1 if area.upper else 0, ((turn + 1) % 4) << 4,
                       area.units, map_number & 0xFF, number)


@dataclass
class During:
    """(1.31.0) One of a battle's scenes during it: the event, when it plays (`TURN`: its unit's turn comes; `HP`: its
    unit's HP falls to `share` percent of its most, 0 beaten), its unit (0 Ramza, else one of the battle's own, 1 to
    16)."""
    event: str
    when: str = TURN
    unit: int = 0
    share: int = 0

    def to_json(self) -> dict:
        out = {"Event": self.event, "When": self.when, "Unit": self.unit}
        if self.when == HP:
            out["Share"] = self.share
        return out


@dataclass
class Fight:
    """A battle event's battle: whose units it fights (one of the quest's battles by name,
    or one of the game's by number), the quest's event that plays as it starts (or "") and
    the one that plays once it is won. (1.12.0) How it is won (`won_by`: every enemy beaten,
    the default; its unit `won_unit`, 1 to 16, beaten or down to `share` percent of its HP;
    Ramza on the tile `tile`, its x, y and level, or every enemy beaten); a unit it is lost
    without (`protect`, 1 to 16, or 0) and the event that plays then (`lost`), after which the
    game starts over; and its objective's words (`objective`, or ""), which its start event
    shows."""
    units: object                  # a battle's name, or a game battle's number
    won: str
    start: str = ""
    won_by: str = ENEMIES
    won_unit: int = 0
    share: int = 0
    tile: tuple = ()               # (x, y, level) for ON_TILE
    protect: int = 0
    lost: str = ""
    objective: str = ""
    #: (1.14.0) Its own deploy areas (`DeployArea`), in place of its setup's DeployArea1 and DeployArea2.
    deploy: list = field(default_factory=list)
    #: (1.31.0) Its scenes during it (`During`), in their order.
    during: list = field(default_factory=list)

    def to_json(self) -> dict:
        out = {"Units": self.units}
        if self.start:
            out["Start"] = self.start
        out["Won"] = self.won
        if self.won_by == BEATEN:
            out["WonWhen"] = {"Beaten": self.won_unit}
        elif self.won_by == WORN_DOWN:
            out["WonWhen"] = {"WornDown": self.won_unit, "Share": self.share}
        elif self.won_by == ON_TILE:
            out["WonWhen"] = {"OnTile": list(self.tile)}
        if self.protect:
            out["Protect"] = self.protect
            out["Lost"] = self.lost
        if self.objective:
            out["Objective"] = self.objective
        if self.deploy:
            out["Deploy"] = [area.to_json() for area in self.deploy]
        if self.during:
            out["During"] = [d.to_json() for d in self.during]
        return out

    def scenes(self) -> tuple:
        """Its events that play in it: its start (or ""), won and lost (or "") events, (1.31.0) then those during it."""
        return (self.start, self.won, self.lost) + tuple(d.event for d in self.during)


@dataclass
class Battle:
    """A quest's own battle: its name and its units' file (640 bytes) in the quest's folder; (Mod Studio Framework
    1.33.0) its units' own names, by their place in the file (0 to 15), each shown as the game shows a renamed unit's;
    (1.53.0, Zodi's order of 13 November: "jobs in a quest's battle") its units' jobs of its mod's own, by their place in
    the file and the job's Name, each unit put in that job as the framework plans the quests; (Mod Studio Framework
    2.0.0, Zodi's first point of 16 November 2026: War of the Lions' items in "modders new Battles") its units' items
    past the 255 a byte of its file holds, by their place in the file and the place each is worn
    (`mod_battles.PLACES`): a number (256 to 315) or the Name of one of its mod's own items, put on the unit as
    the game makes it."""
    name: str
    units: str
    names: dict = field(default_factory=dict)
    jobs: dict = field(default_factory=dict)
    items: dict = field(default_factory=dict)

    def to_json(self) -> dict:
        out = {"Name": self.name, "Units": self.units}
        if self.names:
            out["Names"] = [{"Unit": slot + 1, "Name": self.names[slot]} for slot in sorted(self.names)]
        if self.jobs:
            out["Jobs"] = [{"Unit": slot + 1, "Job": self.jobs[slot]} for slot in sorted(self.jobs)]
        worn = {slot: found for slot, found in self.items.items() if found}
        if worn:
            from . import mod_battles as mb
            out["Items"] = [{"Unit": slot + 1, **{place: worn[slot][place] for place in mb.PLACES
                                                  if place in worn[slot]}} for slot in sorted(worn)]
        return out


#: (Mod Studio Framework 1.33.0, Zodi's choice of 5 November: "As a renamed unit") A unit's own name at the most: the
#: game shows a renamed unit's own text (64 bytes at a battle unit's + 0x14C, ended by a 0) for a generic's name, up to
#: 16 characters in the remaster's mode (dev/research/sidequests/unit_names.py).
MOST_OWN_NAME, OWN_NAME_BYTES = 16, 63
#: The kinds of character that are spaces (a name neither starts nor ends with one).
SPACE_KINDS = ("Zs", "Zl", "Zp")


def good_own_name(text) -> bool:
    """(1.33.0) A unit's own name: 1 to 16 characters (63 bytes of UTF-8 at the most), none a control character, no
    space at either end (the helper's `GoodOwnName`, character for character)."""
    if not isinstance(text, str) or not 1 <= len(text) <= MOST_OWN_NAME:
        return False
    try:
        if len(text.encode("utf-8")) > OWN_NAME_BYTES:
            return False
    except UnicodeEncodeError:
        return False
    if any(unicodedata.category(c) == "Cc" for c in text):
        return False
    return unicodedata.category(text[0]) not in SPACE_KINDS and unicodedata.category(text[-1]) not in SPACE_KINDS


#: (Mod Studio Framework 1.53.0) A job's Name at the most (the helper's `JobFile.NameMost`), which a battle's Jobs name one of
#: its mod's jobs by.
JOB_NAME_MOST = 40


def good_job_name(text) -> bool:
    """(1.53.0) A job's Name as a job's file gives it: 1 to 40 characters (counted as the helper counts them, in UTF-16),
    none a control character, under 1,024 bytes of UTF-8 (the helper's `JobFile.GoodJobName`, character for character)."""
    if not isinstance(text, str):
        return False
    try:
        units, size = len(text.encode("utf-16-le")) // 2, len(text.encode("utf-8"))
    except UnicodeEncodeError:
        return False
    return (1 <= units <= JOB_NAME_MOST and size < 1024
            and not any(unicodedata.category(c) == "Cc" for c in text))


#: (1.15.0) A tavern rumor's title (as an objective's words) and words at the most; the towns whose taverns tell rumors
#: (the world map's places 0 to 14, each a bit of the program's rumors' masks: `dev/research/sidequests/tavern_rumors.py`).
MOST_RUMOR_TITLE, MOST_RUMOR_TEXT, TOWNS = 64, 3000, 15


@dataclass
class Rumor:
    """(Mod Studio Framework 1.15.0, Zodi's list, his third) One of a quest's tavern rumors: its title and words, the
    towns whose taverns tell it (the game's by their places, 0 to 14, and (1.18.0) the mod's own towns with a menu by
    their names; none: every tavern), when it is told (conditions as a start's),
    and the quest's flag set once it is read, which a start may wait for."""
    name: str
    title: str = ""
    text: str = ""
    towns: list = field(default_factory=list)
    when: list = field(default_factory=list)
    read: str = ""

    def to_json(self) -> dict:
        out = {"Name": self.name, "Title": self.title, "Text": self.text}
        if self.towns:
            out["Towns"] = list(self.towns)
        out["When"] = [c.to_json() for c in self.when]
        out["Read"] = self.read
        return out


@dataclass
class Reward:
    """(1.31.0, Zodi's ask of 3 November: "A reward as a quest ends"; his choice "Its last step only") What an event
    gives as its script sets `flag` (one of the quest's flags): `gil` to the war funds and `items` to the bag, each
    `(item, count)`, the item one of the game's by its number or one of the mod's own by its name (a str). The helper
    gives it as the flag goes from 0 to 1, which the game refuses while a scene is replayed."""
    flag: str
    gil: int = 0
    items: list = field(default_factory=list)          # (game item number or own item name, count)

    def to_json(self) -> dict:
        out = {"Flag": self.flag}
        if self.gil:
            out["Gil"] = self.gil
        if self.items:
            out["Items"] = [{"Item": item, "Count": count} for item, count in self.items]
        return out


@dataclass
class QuestEvent:
    """One of a quest's events: its name, its script's file in the quest's folder, its
    words' path (`words_path`, or ""), its setup fields (EnemyBattle and SceneUnits may
    name one of the quest's battles), the quest's event that follows it (or ""), and where
    its flags' numbers go in its script. A battle event (`battle`) has no script, words or
    flags of its own: the helper gives it the game's battles' three instructions."""
    name: str
    script: str = ""
    words: str = ""
    setup: dict = field(default_factory=dict)
    next_event: str = ""
    flags_in_script: list = field(default_factory=list)   # (at, flag name)
    battle: Optional[Fight] = None
    #: (1.11.0) The game's event it was copied from (its `From`), or 0.
    copied_from: int = 0
    #: (1.12.0) Where its battle's objective goes in its script (its `ObjectiveInScript`): each the byte after an
    #: instruction 0x78 (DisplayConditions), which the helper gives the objective's number.
    objective_in_script: list = field(default_factory=list)
    #: (1.30.0) Where its script names Ramza (its `RamzaInScript`): each a unit's two bytes holding one of `RAMZAS`,
    #: which the helper gives the identity of the Ramza in the party.
    ramza_in_script: list = field(default_factory=list)
    #: (1.31.0) Its reward (its `Reward`), or None.
    reward: Optional[Reward] = None

    def to_json(self) -> dict:
        setup = {k: self.setup[k] for k in SETUP_FIELDS if k in self.setup}
        if self.next_event:
            setup["NextEvent"] = self.next_event
        out = {"Name": self.name}
        if self.battle is not None:
            out["Battle"] = self.battle.to_json()
        else:
            out["Script"] = self.script
            if self.words:
                out["Words"] = self.words
        if self.copied_from:
            out["From"] = self.copied_from
        out["Setup"] = setup
        if self.flags_in_script:
            out["FlagsInScript"] = [{"At": at, "Flag": flag} for at, flag in self.flags_in_script]
        if self.objective_in_script:
            out["ObjectiveInScript"] = list(self.objective_in_script)
        if self.ramza_in_script:
            out["RamzaInScript"] = list(self.ramza_in_script)
        if self.reward is not None:
            out["Reward"] = self.reward.to_json()
        return out


@dataclass
class Quest:
    """A side quest: its name, flags, events, starts and battles; and (Mod Studio Framework
    1.2.5) its marker's color on the world map, "#RRGGBB", or "" for none."""
    name: str
    flags: list = field(default_factory=list)
    events: list = field(default_factory=list)
    starts: list = field(default_factory=list)
    battles: list = field(default_factory=list)
    marker: str = ""
    #: (1.15.0) Its tavern rumors (`Rumor`).
    rumors: list = field(default_factory=list)

    def event_named(self, name: str) -> Optional[QuestEvent]:
        return next((e for e in self.events if e.name == name), None)

    def fight_of(self, name: str) -> Optional[QuestEvent]:
        """The battle event an event plays in (as its start, won or (1.12.0) lost event), or None."""
        return next((e for e in self.events if e.battle is not None and name and name in e.battle.scenes()), None)


# =============================================================================
# The file
# =============================================================================

def quest_text(quest: Quest) -> str:
    """The quest's `quest.json`, as the helper reads it."""
    data = {"Format": FORMAT, "Version": VERSION, "Name": quest.name}
    if quest.marker:
        data["Marker"] = quest.marker
    data["Flags"] = list(quest.flags)
    if quest.battles:
        data["Battles"] = [b.to_json() for b in quest.battles]
    data["Events"] = [e.to_json() for e in quest.events]
    data["Starts"] = [s.to_json() for s in quest.starts]
    if quest.rumors:
        data["Rumors"] = [r.to_json() for r in quest.rumors]
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


#: A name a quest gives: letters, digits, spaces, _ and -, 1 to 64 of them, not starting or ending with a space (the
#: helper's `GoodName`, character for character: `helper_json.good_name`).
good_name = hj.good_name


def is_color(text) -> bool:
    """(1.2.5) A color as a quest's Marker gives it: # and six hex digits, red, green, blue (the
    helper's `IsColor`)."""
    return isinstance(text, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", text) is not None


def _whole(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _get(d: dict, name: str, default=None):
    """A field by its name without case, as the helper reads them."""
    for key, value in d.items():
        if key.lower() == name.lower():
            return value
    return default


def _has(d: dict, name: str) -> bool:
    """Whether a field is there at all, by its name without case."""
    return any(key.lower() == name.lower() for key in d)


def _bad_path(name) -> bool:
    """A file name that isn't one of the quest folder's (the helper's check, with Windows' roots)."""
    return (not isinstance(name, str) or not name or ".." in name or name.startswith(("/", "\\"))
            or bool(re.match(r"^[A-Za-z]:", name)))


def read_quest_text(text: str, read_script: Callable[[str], bytes], folder: str = "",
                    place_names=(), map_names=()) -> tuple:
    """
    (the quest, problems) from a `quest.json`'s text, checked as the helper
    checks it (`QuestFile.Read`); the quest is None when anything is wrong.
    `read_script` gives one of the quest folder's files' bytes by name;
    `place_names` are the mod's own places' names, which a start may name;
    (1.10.0) `map_names` its quest maps', which an event's setup may name.
    """
    problems = []
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
    name = _get(top, "Name")
    name = name if isinstance(name, str) and name else folder
    marker = ""
    if _has(top, "Marker"):
        given = _get(top, "Marker")
        if is_color(given):
            marker = given.upper()
        else:
            problems.append(f"its Marker is a color written #RRGGBB, not {json.dumps(given)}")
    flags = []
    flag_list = _get(top, "Flags")
    for f in flag_list if isinstance(flag_list, list) else []:
        if not good_name(f):
            problems.append(f"a flag's name isn't one: {json.dumps(f)}")
        elif f in flags:
            problems.append(f"the flag {f} is named twice")
        else:
            flags.append(f)
    battles = []
    battle_list = _get(top, "Battles")
    for b in battle_list if isinstance(battle_list, list) else []:
        battle = _read_battle(b, read_script, problems)
        if battle is None:
            continue
        if any(x.name == battle.name for x in battles):
            problems.append(f"the battle {battle.name} is named twice")
        else:
            battles.append(battle)
    events = []
    event_list = _get(top, "Events")
    if not isinstance(event_list, list):
        problems.append("it has no Events list")
    else:
        for e in event_list:
            ev = _read_event(e, flags, battles, read_script, problems, map_names)
            if ev is None:
                continue
            if any(x.name == ev.name for x in events):
                problems.append(f"the event {ev.name} is named twice")
            else:
                events.append(ev)
    for ev in events:
        if ev.next_event and not any(x.name == ev.next_event for x in events):
            problems.append(f"the event {ev.name}'s next event {ev.next_event} isn't one of the quest's")
    _fights_problems(events, problems, read_script)
    _units_problems(events, battles, read_script, problems)
    # (1.31.0) A flag gives one reward.
    rewarded = {}
    for ev in events:
        if ev.reward is None:
            continue
        if ev.reward.flag in rewarded:
            problems.append(f"the events {rewarded[ev.reward.flag]} and {ev.name} each give a reward with the flag "
                            f"{ev.reward.flag}: a flag gives one")
            ev.reward = None
        else:
            rewarded[ev.reward.flag] = ev.name
    starts = []
    start_list = _get(top, "Starts")
    for s in start_list if isinstance(start_list, list) else []:
        start = _read_start(s, flags, events, problems, place_names)
        if start is not None:
            starts.append(start)
    # (1.15.0) Its tavern rumors.
    rumors = []
    if _has(top, "Rumors"):
        rumor_list = _get(top, "Rumors")
        if not isinstance(rumor_list, list):
            problems.append("its Rumors aren't a list")
        else:
            for r in rumor_list:
                rumor = _read_rumor(r, flags, problems, place_names)
                if rumor is None:
                    continue
                if any(x.name == rumor.name for x in rumors):
                    problems.append(f"the rumor {rumor.name} is named twice")
                else:
                    rumors.append(rumor)
    if problems:
        return None, problems
    if not events:
        return None, ["it has no events"]
    return Quest(name, flags, events, starts, battles, marker, rumors), []


def _file_of(what: str, name, read, problems: list) -> Optional[bytes]:
    """One of the quest folder's files by name, or None and why in problems."""
    if _bad_path(name):
        problems.append(f"{what} names no file in its folder")
        return None
    try:
        return read(name)
    except OSError as exc:
        problems.append(f"{what}'s file {name} can't be read ({exc})")
        return None


def _read_battle(b, read, problems: list) -> Optional[Battle]:
    name = _get(b, "Name", "") if isinstance(b, dict) else ""
    if not good_name(name):
        problems.append(f"a battle's name isn't one: {json.dumps(b)}")
        return None
    units_name = _get(b, "Units", "")
    units_name = units_name if isinstance(units_name, str) else ""
    units = _file_of(f"the battle {name}", units_name, read, problems)
    if units is None:
        return None
    if len(units) != BATTLE_BYTES:
        problems.append(f"the battle {name}'s units are {len(units)} bytes, not {BATTLE_BYTES} (16 units as the "
                        "game's battles hold them)")
        return None
    # (1.33.0) Its units' own names: each a unit of its 16 (1 to 16) and a name, a unit named once.
    names = {}
    if _has(b, "Names"):
        listed = _get(b, "Names")
        if not isinstance(listed, list):
            problems.append(f"the battle {name}'s Names isn't a list")
            return None
        for n, entry in enumerate(listed, 1):
            unit = _get(entry, "Unit") if isinstance(entry, dict) else None
            if not _whole(unit) or not 1 <= unit <= UNITS:
                problems.append(f"the battle {name}'s own name {n} names no unit: its Unit is 1 to {UNITS}")
                return None
            if not good_own_name(_get(entry, "Name")):
                problems.append(f"the battle {name}'s unit {unit}'s own name isn't one: 1 to {MOST_OWN_NAME} "
                                "characters, none a control character, no space at either end")
                return None
            if unit - 1 in names:
                problems.append(f"the battle {name} gives unit {unit} two own names")
                return None
            names[unit - 1] = _get(entry, "Name")
    # (1.53.0) Its units' jobs of its mod's own: each a unit of its 16 (1 to 16) and a job's Name, a unit given one job.
    jobs = {}
    if _has(b, "Jobs"):
        listed = _get(b, "Jobs")
        if not isinstance(listed, list):
            problems.append(f"the battle {name}'s Jobs isn't a list")
            return None
        for n, entry in enumerate(listed, 1):
            unit = _get(entry, "Unit") if isinstance(entry, dict) else None
            if not _whole(unit) or not 1 <= unit <= UNITS:
                problems.append(f"the battle {name}'s job {n} names no unit: its Unit is 1 to {UNITS}")
                return None
            if not good_job_name(_get(entry, "Job")):
                problems.append(f"the battle {name}'s unit {unit}'s Job isn't a job's Name: 1 to {JOB_NAME_MOST} "
                                "characters, none a control character")
                return None
            if unit - 1 in jobs:
                problems.append(f"the battle {name} gives unit {unit} two jobs")
                return None
            jobs[unit - 1] = _get(entry, "Job")
    # (2.0.0) Its units' items past 255: each a unit of its 16 (1 to 16) and, by the place each is worn, an item's
    # number (256 to 315) or its mod's own item's Name (the helper's `BattleFile.ReadItems`), a unit given once.
    items = {}
    if _has(b, "Items"):
        from . import mod_battles as mb
        listed = _get(b, "Items")
        if not isinstance(listed, list):
            problems.append(f"the battle {name}'s Items isn't a list")
            return None
        for n, entry in enumerate(listed, 1):
            unit = _get(entry, "Unit") if isinstance(entry, dict) else None
            if not _whole(unit) or not 1 <= unit <= UNITS:
                problems.append(f"the battle {name}'s items {n} name no unit: its Unit is 1 to {UNITS}")
                return None
            worn = {}
            for place in mb.PLACES:
                if not _has(entry, place) or _get(entry, place) is None:
                    continue
                if not mb.good_item(_get(entry, place)):
                    problems.append(f"the battle {name}'s unit {unit}'s {place} is an item past the 255 a byte holds "
                                    f"by its number ({mb.FIRST_WIDE} to {mb.LAST_WIDE}) or the Name of one of its "
                                    f"mod's own items, not {json.dumps(_get(entry, place), ensure_ascii=False)}")
                    return None
                worn[place] = _get(entry, place)
            if not worn:
                problems.append(f"the battle {name}'s unit {unit}'s items name none ({', '.join(mb.PLACES)})")
                return None
            if unit - 1 in items:
                problems.append(f"the battle {name} gives unit {unit}'s items twice")
                return None
            items[unit - 1] = worn
    return Battle(name, units_name, names, jobs, items)


def _read_fight(name: str, battle, battles: list, problems: list) -> Optional[Fight]:
    """A battle event's Battle (the helper's `ReadFight`)."""
    if not isinstance(battle, dict):
        problems.append(f"the battle {name}'s Battle isn't a list of fields")
        return None
    units = _get(battle, "Units")
    if isinstance(units, str) and units:
        if not any(b.name == units for b in battles):
            problems.append(f"the battle {name}'s units {units} aren't one of the quest's battles")
            return None
    elif not _whole(units) or not 1 <= units <= MOST_GAME_BATTLE:
        problems.append(f"the battle {name}'s units are one of the quest's battles by name, or the game's 1 to "
                        f"{MOST_GAME_BATTLE}")
        return None
    start, won = _get(battle, "Start", ""), _get(battle, "Won", "")
    start = start if isinstance(start, str) else ""
    won = won if isinstance(won, str) else ""
    if not won:
        problems.append(f"the battle {name} names no won event (what plays once every enemy is beaten ends the "
                        "battle)")
        return None
    # (1.12.0) How it is won: every enemy beaten unless its WonWhen says one of three other ways.
    won_by, won_unit, share, tile = ENEMIES, 0, 0, ()
    if _has(battle, "WonWhen"):
        when = _get(battle, "WonWhen")
        if not isinstance(when, dict):
            problems.append(f"the battle {name}'s WonWhen isn't a list of fields")
            return None
        beaten, worn, on_tile = _has(when, "Beaten"), _has(when, "WornDown"), _has(when, "OnTile")
        if beaten + worn + on_tile != 1:
            problems.append(f"the battle {name}'s WonWhen gives one of Beaten, WornDown and OnTile")
            return None
        if beaten or worn:
            unit = _get(when, "Beaten" if beaten else "WornDown")
            if not _whole(unit) or not 1 <= unit <= UNITS:
                problems.append(f"the battle {name}'s WonWhen names one of its {UNITS} units, 1 to {UNITS}, not "
                                f"{json.dumps(unit)}")
                return None
            won_by, won_unit = (BEATEN if beaten else WORN_DOWN), unit
            given = _get(when, "Share")
            if worn and (not _whole(given) or not 1 <= given <= MOST_SHARE):
                problems.append(f"the battle {name}'s WornDown gives a Share, 1 to {MOST_SHARE} percent of the "
                                "unit's HP")
                return None
            if beaten and _has(when, "Share"):
                problems.append(f"the battle {name}'s Share goes with WornDown, not Beaten")
                return None
            share = given if worn else 0
        else:
            at = _get(when, "OnTile")
            at = [v if _whole(v) else -1 for v in at] if isinstance(at, list) else []
            if (len(at) != 3 or not 0 <= at[0] <= MOST_TILE or not 0 <= at[1] <= MOST_TILE
                    or not 0 <= at[2] <= 1):
                problems.append(f"the battle {name}'s OnTile is a tile, its x and y (0 to {MOST_TILE}) and its level "
                                f"(0, or 1 for its upper level), not {json.dumps(_get(when, 'OnTile'))}")
                return None
            won_by, tile = ON_TILE, tuple(at)
    # (1.12.0) A unit it is lost without, and its event once it is lost.
    protect = 0
    lost = _get(battle, "Lost", "")
    lost = lost if isinstance(lost, str) else ""
    if _has(battle, "Protect"):
        given = _get(battle, "Protect")
        if not _whole(given) or not 1 <= given <= UNITS:
            problems.append(f"the battle {name}'s Protect names one of its {UNITS} units, 1 to {UNITS}, not "
                            f"{json.dumps(given)}")
            return None
        protect = given
        if not lost:
            problems.append(f"the battle {name} names no lost event (what plays once the unit it protects is beaten, "
                            "after which the game starts over)")
            return None
    elif lost:
        problems.append(f"the battle {name}'s lost event {lost} plays once a unit it protects is beaten: it protects "
                        "none")
        return None
    if protect and protect == won_unit:
        problems.append(f"the battle {name} is won and lost by its unit {protect}")
        return None
    # (1.12.0) Its objective's words, which its start event shows.
    objective = ""
    if _has(battle, "Objective"):
        given = _get(battle, "Objective")
        objective = given if isinstance(given, str) else ""
        if not good_objective(objective):
            problems.append(f"the battle {name}'s Objective is words of 1 to {MOST_OBJECTIVE} characters on one line, "
                            f"not {json.dumps(given, ensure_ascii=False)}")
            return None
    # (1.14.0) Its own deploy areas.
    deploy = []
    if _has(battle, "Deploy") and not _read_deploy(name, _get(battle, "Deploy"), deploy, problems):
        return None
    # (1.31.0) Its scenes during it.
    during = []
    if _has(battle, "During") and not _read_during(name, _get(battle, "During"), during, problems):
        return None
    fight = Fight(units, won, start, won_by, won_unit, share, tile, protect, lost, objective, deploy, during)
    rules = rules_of(fight)
    if rules > MOST_RULES:
        problems.append(f"the battle {name} has {rules} rules, more than the {MOST_RULES} the game runs (each scene "
                        "during it on Ramza's turn or HP takes 3: one for each of his chapters)")
        return None
    return fight


def _read_during(name: str, given, during: list, problems: list) -> bool:
    """(1.31.0) A battle's During (the helper's `ReadDuring`): up to `MOST_DURING` scenes, each its Event (a name,
    once), its When (`TURN` or `HP`), its Unit (0 Ramza, else one of the battle's 16) and, for `HP`, its Share (0 to
    99); False and why in `problems`."""
    good = isinstance(given, list) and len(given) <= MOST_DURING
    for d in given if good else ():
        ev = _get(d, "Event", "") if isinstance(d, dict) else ""
        when = _get(d, "When", "") if isinstance(d, dict) else ""
        unit = _get(d, "Unit") if isinstance(d, dict) else None
        if (not good_name(ev) or any(x.event == ev for x in during) or when not in (TURN, HP) or not _whole(unit)
                or not 0 <= unit <= UNITS):
            good = False
            break
        share = 0
        if _has(d, "Share"):
            share = _get(d, "Share")
            if when != HP or not _whole(share) or not 0 <= share <= MOST_SHARE_DURING:
                problems.append(f"the battle {name}'s scene {ev} during it has a Share only when it plays as its "
                                f"unit's HP falls (Hp): 0 to {MOST_SHARE_DURING} percent of its most, 0 beaten, not "
                                f"{_raw(d, 'Share')}")
                return False
        during.append(During(ev, when, unit, share))
    if not good:
        problems.append(f"the battle {name}'s During is up to {MOST_DURING} scenes, each its Event once, its When "
                        f"({TURN} or {HP}) and its Unit (0 Ramza, else one of its {UNITS} units), not "
                        f"{json.dumps(given, ensure_ascii=False)}")
    return good


def rules_of(fight: Fight) -> int:
    """(1.31.0) How many rules a battle's chains are as Mod Studio Framework lays them out (the helper's `RulesOf`): its
    start, its protected unit's, how it is won (Ramza on a tile one for each of his chapters, then every enemy
    beaten), each scene during it (on Ramza's turn or HP one for each of his chapters)."""
    rules = 1 + (1 if fight.protect else 0)
    rules += 3 + 1 if fight.won_by == ON_TILE else 1
    return rules + sum(3 if d.unit == 0 else 1 for d in fight.during)


def sets_variable(script: bytes, variable: int) -> bool:
    """(1.31.0) Whether a script sets a variable: a variable command (0xB0 to 0xBE) naming it, found by its bytes (the
    helper's `SetsVariable`)."""
    for at in range(len(script) - 2):
        if FIRST_VARIABLE_COMMAND <= script[at] <= LAST_VARIABLE_COMMAND \
                and struct.unpack_from("<H", script, at + 1)[0] == variable:
            return True
    return False


def _raw(d: dict, name: str) -> str:
    """A field as the helper says it (its JSON), "none" when it isn't there."""
    return json.dumps(_get(d, name), ensure_ascii=False) if _has(d, name) else "none"


def _read_deploy(name: str, areas, deploy: list, problems: list, who: str = "") -> bool:
    """(1.14.0) A battle's Deploy (the helper's `ReadDeploy`): one or two deploy areas, each its Squares (1 to 25, each
    a tile's x and y, 0 to 255, within 5 by 5 squares), its Units (1 to 5, no more than its squares), its Facing (South,
    West, North or East) and, if on their upper level, Upper. (1.17.0) `who` names the battle in what is said ("the
    random battle X" for a battle ground's own; "the battle X" by default)."""
    who = who or f"the battle {name}"
    if not isinstance(areas, list) or not 1 <= len(areas) <= MOST_DEPLOY_AREAS:
        problems.append(f"{who}'s Deploy is one or two deploy areas")
        return False
    for n, area in enumerate(areas, start=1):
        which = f"{who}'s deploy area {n}"
        if not isinstance(area, dict):
            problems.append(f"{which} isn't a list of fields")
            return False
        given = _get(area, "Squares")
        squares = []
        good = isinstance(given, list) and 1 <= len(given) <= MOST_SQUARES
        if good:
            for square in given:
                at = [v if _whole(v) else -1 for v in square] if isinstance(square, list) else []
                if len(at) != 2 or not 0 <= at[0] <= MOST_TILE or not 0 <= at[1] <= MOST_TILE:
                    good = False
                    break
                squares.append((at[0], at[1]))
        if not good:
            problems.append(f"{which}'s Squares are 1 to {MOST_SQUARES} tiles, each its x and y (0 to {MOST_TILE}), "
                            f"not {_raw(area, 'Squares')}")
            return False
        seen = set()
        for square in squares:
            if square in seen:
                problems.append(f"{which} gives the square {square[0]}, {square[1]} twice")
                return False
            seen.add(square)
        wide = max(x for x, _y in squares) - min(x for x, _y in squares) + 1
        deep = max(y for _x, y in squares) - min(y for _x, y in squares) + 1
        if wide > MOST_SPAN or deep > MOST_SPAN:
            problems.append(f"{which}'s squares fit in {MOST_SPAN} by {MOST_SPAN} squares, not {wide} by {deep}")
            return False
        count = _get(area, "Units")
        if not _whole(count) or not 1 <= count <= MOST_DEPLOY_UNITS or count > len(squares):
            problems.append(f"{which}'s Units is how many of the player's units start there, 1 to {MOST_DEPLOY_UNITS} "
                            f"and no more than its squares, not {_raw(area, 'Units')}")
            return False
        facing = _get(area, "Facing")
        if not isinstance(facing, str) or facing not in FACINGS:
            problems.append(f"{which}'s Facing is one of South, West, North and East, not {_raw(area, 'Facing')}")
            return False
        upper = False
        if _has(area, "Upper"):
            up = _get(area, "Upper")
            if not isinstance(up, bool):
                problems.append(f"{which}'s Upper is true or false, not {_raw(area, 'Upper')}")
                return False
            upper = up
        deploy.append(DeployArea(squares, count, FACINGS.index(facing), upper))
    return True


def good_objective(words) -> bool:
    """(1.12.0) Words a battle's objective may be: 1 to 64 characters, none a control character (a line break among
    them), no space at either end (the helper's `GoodObjective`)."""
    return (isinstance(words, str) and 1 <= len(words) <= MOST_OBJECTIVE and not words[0].isspace()
            and not words[-1].isspace() and not any(_control(c) for c in words))


def _control(c: str) -> bool:
    """A control character as .NET's `char.IsControl` has them: U+0000 to U+001F and U+007F to U+009F."""
    return ord(c) < 0x20 or 0x7F <= ord(c) <= 0x9F


def named_unit(unit_id: int) -> bool:
    """(1.12.0) Whether a battle's rules can name a unit by its unit ID (the helper's `NamedUnit`): the game's
    CharaControlId table gives the unit ID a rule tests by the rule's key, and its keys 1 to 52, 100 to 103 and 128 to
    139 are those IDs themselves."""
    return 1 <= unit_id <= 52 or 100 <= unit_id <= 103 or 128 <= unit_id <= 139


def _fights_problems(events: list, problems: list, read=None) -> None:
    """Each battle event's start, won and (1.12.0) lost events are events of the quest that
    aren't battles, played in no other battle; its lost event has no next event; its objective
    is shown by its start event, and only a battle's start event with one shows one (the
    helper's `FightsProblems`)."""
    played_in = {}
    for ev in events:
        if ev.battle is None:
            continue
        lost = next((x for x in events if x.name == ev.battle.lost), None) if ev.battle.lost else None
        if lost is not None and lost.next_event:
            problems.append(f"the battle {ev.name}'s lost event {lost.name} has no next event: the game starts over "
                            "after it")
        start = next((x for x in events if x.name == ev.battle.start), None) if ev.battle.start else None
        if ev.battle.objective and (start is None or not start.objective_in_script):
            problems.append(f"the battle {ev.name}'s objective is shown by its start event, which has no place for it "
                            "(its ObjectiveInScript)")
        # (1.31.0) Its scenes during it, each setting its guard as it ends (`GUARDS`, by its place).
        for k, d in enumerate(ev.battle.during):
            mid = next((x for x in events if x.name == d.event), None)
            if mid is not None and mid.battle is None and read is not None:
                try:
                    script = read(mid.script)
                except OSError:
                    script = None
                if script is not None and not sets_variable(script, GUARDS[k]):
                    problems.append(f"the battle {ev.name}'s scene {mid.name} during it never sets variable "
                                    f"{GUARDS[k]}, which keeps it to once a battle: it would play again and again")
        scenes = [("start", ev.battle.start), ("won", ev.battle.won), ("lost", ev.battle.lost)]
        scenes += [("during", d.event) for d in ev.battle.during]
        for what, scene in scenes:
            if not scene:
                continue
            played = next((x for x in events if x.name == scene), None)
            if played is None:
                problems.append(f"the battle {ev.name}'s {what} event {scene} isn't one of the quest's")
            elif played.battle is not None:
                problems.append(f"the battle {ev.name}'s {what} event {scene} is a battle itself")
            elif scene in played_in:
                problems.append(f"the event {scene} plays twice: as {played_in[scene]} event and as {ev.name}'s "
                                f"{what} event")
            else:
                played_in[scene] = f"{ev.name}'s {what}"
    for ev in events:
        if ev.objective_in_script and not any(x.battle is not None and x.battle.start == ev.name
                                              and x.battle.objective for x in events):
            problems.append(f"the event {ev.name} shows a battle's objective (its ObjectiveInScript), but starts no "
                            "battle with one")


def _units_problems(events: list, battles: list, read, problems: list) -> None:
    """(1.12.0) What's wrong with the units a battle event's WonWhen and Protect name: of one of the quest's own
    battles (whose units are in the quest's folder), each a unit (its sprite set not 0) always on the field (Always
    Present alone), its unit ID one the rules can name and no other unit's of its battle, and (1.12.1) not taken from
    the player's own units (Load Formation) (the helper's `UnitsProblems`)."""
    for ev in events:
        fight = ev.battle
        # (1.31.0) And its scenes during it, each by its unit's turn or HP (Ramza's, 0, needs none of its own).
        named = [fight.won_unit, fight.protect] if fight is not None else []
        for d in fight.during if fight is not None else ():
            if d.unit and d.unit not in named:
                named.append(d.unit)
        if fight is None or not any(named):
            continue
        battle = next((b for b in battles if b.name == fight.units), None) if isinstance(fight.units, str) else None
        if battle is None:
            problems.append(f"the battle {ev.name} names a unit of its own in its WonWhen, Protect or During: its "
                            "units are one of the quest's battles, by name, for that")
            continue
        try:
            units = read(battle.units)
        except OSError:
            continue
        if len(units) != BATTLE_BYTES:
            continue
        for slot in named:
            if not slot:
                continue
            at = (slot - 1) * UNIT_BYTES
            if units[at] == 0:
                problems.append(f"the battle {ev.name}'s unit {slot} is an empty place")
                continue
            unit_id = units[at + UNIT_ID_AT]
            if not named_unit(unit_id):
                problems.append(f"the battle {ev.name}'s unit {slot} has the unit ID {unit_id}, which a battle's rules "
                                "can't name: give it one of 1 to 52, 100 to 103 or 128 to 139")
            for other in range(1, UNITS + 1):
                if (other != slot and units[(other - 1) * UNIT_BYTES] != 0
                        and units[(other - 1) * UNIT_BYTES + UNIT_ID_AT] == unit_id):
                    problems.append(f"the battle {ev.name}'s unit {slot} shares its unit ID {unit_id} with its unit "
                                    f"{other}")
                    break
            if units[at + PRESENCE_AT] & PRESENCE_MASK != ALWAYS_PRESENT:
                problems.append(f"the battle {ev.name}'s unit {slot} isn't always on the field (Always Present alone): "
                                "its rules would wait for a unit that may not be there")
            if units[at + FLAGS_AT] & LOAD_FORMATION:
                problems.append(f"the battle {ev.name}'s unit {slot} is taken from the player's own units as the battle "
                                "starts (Load Formation), which leaves an empty place at 0 HP when they haven't that "
                                "unit: build it from its own fields (Load Formation off)")


def _read_event(e, flags: list, battles: list, read_script, problems: list, map_names=()) -> Optional[QuestEvent]:
    if not isinstance(e, dict):
        problems.append("an event isn't a list of fields")
        return None
    name = _get(e, "Name", "")
    if not good_name(name):
        problems.append(f"an event's name isn't one: {json.dumps(e)}")
        return None
    fight = None
    if _has(e, "Battle"):
        fight = _read_fight(name, _get(e, "Battle"), battles, problems)
        if fight is None:
            return None
        if (_has(e, "Script") or _has(e, "Words") or _has(e, "FlagsInScript")
                or _has(e, "ObjectiveInScript") or _has(e, "RamzaInScript") or _has(e, "Reward")):
            problems.append(f"the battle {name} has no script or words of its own: every battle starts with the "
                            "game's three instructions, and its start and won events say what is said")
            return None
    script, script_name, words = b"", "", ""
    if fight is None:
        script_name = _get(e, "Script", "")
        if _bad_path(script_name):
            problems.append(f"the event {name} names no script in its folder")
            return None
        try:
            script = read_script(script_name)
        except OSError as exc:
            problems.append(f"the event {name}'s script {script_name} can't be read ({exc})")
            return None
        if not script or len(script) > MOST_SCRIPT:
            problems.append(f"the event {name}'s script is {len(script)} bytes; the game reads 1 to {MOST_SCRIPT}")
            return None
        words = _get(e, "Words", "")
        words = words if isinstance(words, str) else ""
        if words and (not words.startswith("nxd/text/") or not words.endswith(".pzd") or ".." in words):
            problems.append(f"the event {name}'s words aren't a text file under nxd/text/: {words}")
            return None
    setup, next_event = {}, ""
    given = _get(e, "Setup")
    for key, value in (given.items() if isinstance(given, dict) else ()):
        if key.lower() == "nextevent":
            if isinstance(value, str):
                next_event = value
            else:
                problems.append(f"the event {name}'s NextEvent names the quest's own event, not a number")
            continue
        known = next((f for f in SETUP_FIELDS if f.lower() == key.lower()), None)
        fld = su.field_of(known) if known else None
        names = known in BATTLE_FIELDS
        most = MOST_GAME_BATTLE if names else MOST_GAME_MAP if known == "Map" else (fld.most if fld else 0)
        if fld is None:
            problems.append(f"the event {name}'s setup has no field {key} a quest gives")
        elif fight is not None and known == "EnemyBattle":
            problems.append(f"the battle {name}'s enemies are its Battle's Units, not its setup's EnemyBattle")
        elif known == "Map" and isinstance(value, str):
            # (1.10.0) One of the mod's quest maps, by its name.
            if value not in map_names:
                problems.append(f"the event {name}'s Map names {value}, which isn't one of the mod's quest maps")
            else:
                setup[fld.key] = value
        elif names and isinstance(value, str):
            if not any(b.name == value for b in battles):
                problems.append(f"the event {name}'s {fld.key} names {value}, which isn't one of the quest's "
                                "battles")
            else:
                setup[fld.key] = value
        elif not _whole(value) or not 0 <= value <= most:
            either = (" or one of the quest's battles" if names
                      else " or one of the mod's quest maps" if known == "Map" else "")
            problems.append(f"the event {name}'s {fld.key} holds 0 to {most}{either}, not {json.dumps(value)}")
        else:
            setup[fld.key] = value
    places = []
    listed = _get(e, "FlagsInScript")
    for f in listed if isinstance(listed, list) else []:
        flag = _get(f, "Flag", "") if isinstance(f, dict) else ""
        at = _get(f, "At") if isinstance(f, dict) else None
        if not isinstance(f, dict) or not _whole(at) or at < 0 or at + 2 > len(script):
            problems.append(f"the event {name} puts a flag outside its script: {json.dumps(f)}")
        elif flag not in flags:
            problems.append(f"the event {name}'s script names {flag}, which isn't one of the quest's flags")
        else:
            places.append((at, flag))
    copied_from = 0
    if _has(e, "From"):
        given = _get(e, "From")
        if not _whole(given) or not 1 <= given <= MOST_GAME_EVENT:
            problems.append(f"the event {name}'s From is the game's event it was copied from, 1 to "
                            f"{MOST_GAME_EVENT}, not {json.dumps(given)}")
        else:
            copied_from = given
    # (1.12.0) Where its battle's objective goes in its script: each the byte after an instruction 0x78.
    objective_at = []
    if _has(e, "ObjectiveInScript"):
        listed = _get(e, "ObjectiveInScript")
        if not isinstance(listed, list) or fight is not None:
            problems.append(f"the event {name}'s ObjectiveInScript is a list of places in its script")
        else:
            for at in listed:
                if not _whole(at) or not 1 <= at < len(script) or script[at - 1] != DISPLAY_CONDITIONS:
                    problems.append(f"the event {name} puts its battle's objective where its script shows none: "
                                    f"{json.dumps(at)}")
                elif at not in objective_at:
                    objective_at.append(at)
    # (1.30.0) Where its script names Ramza: each a unit's two bytes holding one of his identities (1, 2 or 3).
    ramza_at = []
    if _has(e, "RamzaInScript"):
        listed = _get(e, "RamzaInScript")
        if not isinstance(listed, list):
            problems.append(f"the event {name}'s RamzaInScript is a list of places in its script")
        else:
            for at in listed:
                if (not _whole(at) or not 1 <= at <= len(script) - 2 or script[at] not in RAMZAS
                        or script[at + 1] != 0):
                    problems.append(f"the event {name} puts Ramza where its script names no Ramza (1, 2 or 3): "
                                    f"{json.dumps(at)}")
                elif at not in ramza_at:
                    ramza_at.append(at)
    # (1.31.0) Its reward: given as its script sets the reward's flag.
    reward = _read_reward(name, _get(e, "Reward"), script, places, problems) if _has(e, "Reward") else None
    return QuestEvent(name, script_name, words, setup, next_event, places, fight, copied_from, objective_at,
                      ramza_at, reward)


def _read_reward(name: str, given, script: bytes, places: list, problems: list) -> Optional[Reward]:
    """(1.31.0) An event's Reward (the helper's `ReadReward`): its Flag (one of the quest's flags, set by a variable
    command of its script, as its FlagsInScript put it), its Gil (0 to `MOST_GIL`) and its Items (up to
    `MOST_REWARD_ITEMS`, each its Item, one of the game's by its number or one of the mod's own by its name, once, and
    its Count, 1 to `MOST_OF_AN_ITEM`), giving something; None and why in `problems`."""
    if not isinstance(given, dict):
        problems.append(f"the event {name}'s Reward is its Flag, its Gil and its Items, not "
                        f"{json.dumps(given, ensure_ascii=False)}")
        return None
    flag = _get(given, "Flag", "")
    flag = flag if isinstance(flag, str) else ""
    if not any(f == flag for _, f in places):
        problems.append(f"the event {name}'s Reward comes with the flag {_raw(given, 'Flag')}, which its script "
                        "doesn't name")
        return None
    if not any(f == flag and at >= 1 and FIRST_VARIABLE_COMMAND <= script[at - 1] <= LAST_VARIABLE_COMMAND
               for at, f in places):
        problems.append(f"the event {name}'s Reward comes with the flag {flag}, which its script never sets")
        return None
    gil = 0
    if _has(given, "Gil"):
        gil = _get(given, "Gil")
        if not _whole(gil) or not 0 <= gil <= MOST_GIL:
            problems.append(f"the event {name}'s Reward's Gil is 0 to {MOST_GIL:,}, not {_raw(given, 'Gil')}")
            return None
    items = []
    if _has(given, "Items"):
        listed = _get(given, "Items")
        good = isinstance(listed, list) and len(listed) <= MOST_REWARD_ITEMS
        taken = set()
        for it in listed if good else ():
            item = _get(it, "Item") if isinstance(it, dict) else None
            count = _get(it, "Count") if isinstance(it, dict) else None
            if not isinstance(it, dict) or not _has(it, "Item") or not _whole(count) \
                    or not 1 <= count <= MOST_OF_AN_ITEM:
                good = False
                break
            if isinstance(item, str) and mi.good_name(item) and ("own", item) not in taken:
                taken.add(("own", item))
                items.append((item, count))
            elif _whole(item) and item in mi.GAME_ITEMS and ("game", item) not in taken:
                taken.add(("game", item))
                items.append((item, count))
            else:
                good = False
                break
        if not good:
            problems.append(f"the event {name}'s Reward's Items are up to {MOST_REWARD_ITEMS} items, each its Item "
                            f"(one of the game's by its number, 1 to {mi.MOST_GAME_ITEM} but 254 and 255, or one of "
                            f"the mod's own by its name) once and its Count, 1 to {MOST_OF_AN_ITEM}, not "
                            f"{_raw(given, 'Items')}")
            return None
    if not gil and not items:
        problems.append(f"the event {name}'s Reward gives nothing: no Gil and no Items")
        return None
    return Reward(flag, gil, items)


def _read_start(s, flags: list, events: list, problems: list, place_names=()) -> Optional[Start]:
    place = _get(s, "Place") if isinstance(s, dict) else None
    if isinstance(place, str) and place:
        # (1.8.0) One of the mod's own places, by its name.
        if place not in place_names:
            problems.append(f"a start's place names no place of the mod's ({place})")
            return None
    elif not isinstance(s, dict) or not _whole(place) or not 0 <= place < PLACES:
        problems.append(f"a start's place isn't one of the world map's 0 to {PLACES - 1}: {json.dumps(s)}")
        return None
    event = _get(s, "Event", "")
    if not any(x.name == event for x in events):
        problems.append(f"a start's event {event} isn't one of the quest's")
        return None
    fight = next((x for x in events if x.battle is not None and event in x.battle.scenes()), None)
    if fight is not None:
        problems.append(f"a start's event {event} plays in the battle {fight.name}: a start loads the battle")
        return None
    stops = False
    if _has(s, "Passing"):
        how = _get(s, "Passing")
        if how not in ("Stops", "Waits"):
            problems.append(f"a start's Passing is Stops or Waits, not {json.dumps(how)}")
            return None
        stops = how == "Stops"
    # (1.25.0) Waiting at a floor of one of the mod's own dungeons, its place named: played as the floor is chosen,
    # never as a travel passes.
    floor = ""
    if _has(s, "Floor"):
        floor = _get(s, "Floor")
        if not isinstance(floor, str) or not good_name(floor) or len(floor) > mp.MOST_FLOOR_NAME:
            problems.append(f"a start's Floor is a floor's name, 1 to {mp.MOST_FLOOR_NAME} letters, digits, spaces, "
                            f"underscores and hyphens, not {json.dumps(floor)}")
            return None
        if not isinstance(place, str):
            problems.append(f"a start's Floor {floor} is a floor of one of the mod's own dungeons, named by its Place, "
                            f"not of the world map's place {place}")
            return None
        if stops:
            problems.append("a start at a floor plays as the floor is chosen: its Passing can't be Stops")
            return None
    when = _read_conditions(s, "a start", flags, problems)
    if when is None:
        return None
    return Start(place, event, when, stops, floor)


def _read_conditions(s: dict, who: str, flags: list, problems: list) -> Optional[list]:
    """The conditions of a start or (1.15.0) a rumor (`who` says which in its problems): its When, as the helper's
    `ReadConditions` reads it; None and why in problems."""
    when = []
    listed = _get(s, "When")
    for c in listed if isinstance(listed, list) else []:
        if not isinstance(c, dict):
            problems.append(f"{who}'s condition isn't a list of fields")
            return None
        if len(when) == MOST_CONDITIONS:
            problems.append(f"{who} has more than {MOST_CONDITIONS} conditions")
            return None
        test, value = next(((t, _get(c, t)) for t in TESTS if _whole(_get(c, t))), ("", 0))
        variable = _get(c, "Variable")
        flag = _get(c, "Flag")
        character = _get(c, "Character")
        if _whole(variable):
            if not test or not 1 <= variable <= 0x3FF or not 0 <= value <= 0xFFFF:
                problems.append(f"{who}'s condition isn't one the world map tests: {json.dumps(c)}")
                return None
            when.append(Condition("Variable", variable, "", test, value))
        elif isinstance(flag, str) and flag:
            if flag not in flags or test != "Is" or value not in (0, 1):
                problems.append(f"{who}'s flag condition isn't one of the quest's flags being 0 or 1: "
                                f"{json.dumps(c)}")
                return None
            when.append(Condition("Flag", 0, flag, "Is", value))
        elif _whole(character):
            if not 1 <= character <= 0xFF:
                problems.append(f"{who}'s character isn't one: {json.dumps(c)}")
                return None
            when.append(Condition("Character", 0, "", "Is", character))
        else:
            problems.append(f"{who}'s condition names no variable, flag or character: {json.dumps(c)}")
            return None
    return when


def good_rumor_text(words) -> bool:
    """(1.15.0) Words a rumor's own may be (its Text): 1 to 3,000 characters, line breaks the only control characters
    among them, no space at either end (the helper's `GoodRumorText`)."""
    return (isinstance(words, str) and 1 <= len(words) <= MOST_RUMOR_TEXT and not words[0].isspace()
            and not words[-1].isspace() and not any(_control(c) and c != "\n" for c in words))


def _read_rumor(r, flags: list, problems: list, place_names=()) -> Optional[Rumor]:
    """(1.15.0) A tavern rumor, as the helper's `ReadRumor` reads it: its Name, Title, Text, Towns, When and Read;
    None and why in problems. (1.18.0) Its Towns may name the mod's own towns (`place_names`) beside the game's."""
    name = _get(r, "Name") if isinstance(r, dict) else None
    if not isinstance(name, str) or not good_name(name):
        problems.append(f"a rumor's name isn't one: {_raw(r, 'Name') if isinstance(r, dict) and _has(r, 'Name') else json.dumps(r, ensure_ascii=False)}")
        return None
    which = f"the rumor {name}"
    title = _get(r, "Title")
    if not good_objective(title):
        problems.append(f"{which}'s Title is words of 1 to {MOST_RUMOR_TITLE} characters on one line, not "
                        f"{_raw(r, 'Title')}")
        return None
    text = _get(r, "Text")
    if not good_rumor_text(text):
        problems.append(f"{which}'s Text is words of 1 to {MOST_RUMOR_TEXT} characters, its paragraphs apart by line "
                        f"breaks, not {_raw(r, 'Text')}")
        return None
    towns = []
    if _has(r, "Towns"):
        # The game's towns by their places; (1.18.0) the mod's own towns by their names.
        given = _get(r, "Towns")
        good = isinstance(given, list) and len(given) >= 1
        if good:
            for town in given:
                if isinstance(town, str):
                    if town not in place_names or town in towns:
                        good = False
                        break
                elif not _whole(town) or not 0 <= town < TOWNS or town in towns:
                    good = False
                    break
                towns.append(town)
        if not good:
            problems.append(f"{which}'s Towns are the towns whose taverns tell it, the game's by their places (0 to "
                            f"{TOWNS - 1}) or the mod's own by their names, each once, not {_raw(r, 'Towns')}")
            return None
    when = _read_conditions(r, which, flags, problems)
    if when is None:
        return None
    read = _get(r, "Read")
    if not isinstance(read, str) or read not in flags:
        problems.append(f"{which}'s Read is the quest's flag set once it is read, not {_raw(r, 'Read')}")
        return None
    return Rumor(name, title, text, towns, when, read)


# =============================================================================
# A mod's quests
# =============================================================================

def _safe(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "x"


def words_path(mod_id: str, folder: str, event: str) -> str:
    """Where an event's words are, as its `Words` names them (without the language): in
    the game's folder for scenes' words, under a name of the mod, the quest and the event."""
    return f"{WORDS_FOLDER}/msq_{_safe(mod_id)}_{_safe(folder)}_{_safe(event)}.pzd"


def words_file(words: str, language: str = "en") -> str:
    """The mod's file for an event's words in a language: `FFTIVC/data/enhanced/` + the
    path with the language before `.pzd` (as WotL Restoration's scenes' words are)."""
    return f"FFTIVC/data/enhanced/{words[:-len('.pzd')]}.{language}.pzd"


def write_quest(mod_folder, folder: str, quest: Quest, scripts: dict) -> list:
    """
    Writes a quest into `<mod_folder>/ModStudioQuests/<folder>/`: its file and
    its events' scripts (`scripts`: file name to bytes). Returns the paths written.
    """
    if not good_name(folder):
        raise ValueError(f"a quest's folder is named as its names are: {folder!r}")
    root = Path(mod_folder) / FOLDER / folder
    root.mkdir(parents=True, exist_ok=True)
    written = []
    for name, data in scripts.items():
        path = root / name
        path.write_bytes(data)
        written.append(path)
    path = root / FILE_NAME
    path.write_text(quest_text(quest), encoding="utf-8")
    written.append(path)
    return written


def read_mod_quests(mod_folder) -> list:
    """Every quest of a mod, in its folders' order: (folder, the quest or None, problems); a start
    may name one of the mod's own places (`map_places.read_mod_places`)."""
    root = Path(mod_folder) / FOLDER
    out = []
    if not root.is_dir():
        return out
    place_names = {place.name for _, place, _ in mp.read_mod_places(mod_folder) if place is not None}
    map_names = set(qm.map_names(mod_folder))
    for sub in sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.name):
        file = sub / FILE_NAME
        if not file.is_file():
            continue
        try:
            text = hj.read_text(file)
        except OSError as exc:
            out.append((sub.name, None, [f"it can't be read ({exc})"]))
            continue
        quest, problems = read_quest_text(text, lambda n, s=sub: (s / n).read_bytes(), sub.name, place_names,
                                          map_names)
        out.append((sub.name, quest, problems))
    return out


# =============================================================================
# Flags in a script
# =============================================================================

def flag_places(script: bytes, lengths: es.Lengths, mode: str = "enhanced") -> list:
    """
    Where a variable's number stands in a script's variable instructions
    (0xB0 to 0xBE), as (byte offset in the script, opcode, operand name): the
    places a flag's number may go. The script is read as Mod Studio reads
    the game's (`event_scripts.read_script`).
    """
    parsed = es.read_script(script, lengths, mode)
    out, at = [], 0
    for ins in parsed.instructions:
        if ins.opcode in VARIABLE_OPS:
            out.append((at + 1, ins.opcode, "variable"))
            if ins.opcode != 0xBE and ins.opcode & 1:
                out.append((at + 3, ins.opcode, "value"))
        at += ins.size
    return out


def flags_problem(quest: Quest, scripts: dict, lengths: es.Lengths, mode: str = "enhanced") -> str:
    """Why a quest's `FlagsInScript` don't each point at a variable's place in their event's
    script (`flag_places`), or ""."""
    for ev in quest.events:
        if ev.battle is not None:
            continue
        places = {at for at, _, _ in flag_places(scripts[ev.script], lengths, mode)}
        for at, flag in ev.flags_in_script:
            if at not in places:
                return f"the event {ev.name}'s flag {flag} at byte {at} isn't a variable of its script"
    return ""


# =============================================================================
# Ramza in a script (1.30.0)
# =============================================================================

def unit_places(script: bytes, lengths: es.Lengths, mode: str = "enhanced") -> list:
    """Where a script names one unit or a group of units (an instruction's operand of the kind "unit" or "units",
    two bytes), as (byte offset in the script, opcode, operand name), read as Mod Studio reads the game's."""
    parsed = es.read_script(script, lengths, mode)
    out, at = [], 0
    for ins in parsed.instructions:
        for spec in es.layout(ins.opcode, mode):
            if spec.kind in ("unit", "units") and spec.size == 2 and 1 + spec.at + 2 <= ins.size:
                out.append((at + 1 + spec.at, ins.opcode, spec.name))
        at += ins.size
    return out


def ramza_places(script: bytes, lengths: es.Lengths, mode: str = "enhanced") -> list:
    """The places a script names Ramza (`unit_places` holding one of `RAMZAS`): where an event's `RamzaInScript` may
    point."""
    return [at for at, _, _ in unit_places(script, lengths, mode)
            if int.from_bytes(script[at:at + 2], "little") in RAMZAS]


def ramza_problem(quest: Quest, scripts: dict, lengths: es.Lengths, mode: str = "enhanced") -> str:
    """Why a quest's `RamzaInScript` don't each point at a unit its event's script names as Ramza (`ramza_places`),
    or ""."""
    for ev in quest.events:
        if ev.battle is not None or not ev.ramza_in_script:
            continue
        places = set(ramza_places(scripts[ev.script], lengths, mode))
        for at in ev.ramza_in_script:
            if at not in places:
                return f"the event {ev.name}'s Ramza at byte {at} isn't a unit its script names"
    return ""


# =============================================================================
# The story in a script (1.2.1)
# =============================================================================

#: A story scene's instructions that move the story: E9 sets the game's progress (a track, 0 the
#: story's, and its value; the world map shows the objective and markers of the point track 0
#: names, and a story scene sets it at its end), EA one of the game's progress flags (its number,
#: and 1 to set it, else clear it); a variable instruction on variable 110 changes the story's
#: progress, which the world map's story steps test.
PROGRESS_OP, PROGRESS_FLAG_OP, STORY_PROGRESS = 0xE9, 0xEA, 110


def story_changes(script: bytes, lengths: es.Lengths, mode: str = "enhanced") -> list:
    """
    What in a script would move the story, as (byte offset in the script, what, its numbers):
    ("progress", (track, value)) for E9, ("progress flag", (flag, set)) for EA, ("story progress",
    (opcode,)) for a variable instruction whose variable is 110 (one that only reads it is left
    out). A story scene copied into a quest keeps them (Zodi's tests 14 and 15: the world map's
    objective went back). Mod Studio Framework (1.2.1) leaves the game's progress and the story's
    progress as they were while a quest's event plays, saying so in its log; a progress flag it
    doesn't (the game's own code sets those too), so `story_problem` refuses it.
    """
    parsed = es.read_script(script, lengths, mode)
    out, at = [], 0
    for ins in parsed.instructions:
        ops = ins.operands
        if ins.opcode == PROGRESS_OP and len(ops) == 8:
            out.append((at, "progress", (int.from_bytes(ops[:4], "little", signed=True),
                                         int.from_bytes(ops[4:], "little", signed=True))))
        elif ins.opcode == PROGRESS_FLAG_OP and len(ops) == 5:
            out.append((at, "progress flag", (int.from_bytes(ops[:4], "little", signed=True), ops[4] == 1)))
        elif ins.opcode in VARIABLE_OPS and len(ops) >= 2 and int.from_bytes(ops[:2], "little") == STORY_PROGRESS:
            out.append((at, "story progress", (ins.opcode,)))
        at += ins.size
    return out


def story_problem(quest: Quest, scripts: dict, lengths: es.Lengths, mode: str = "enhanced") -> str:
    """Why a quest's scripts would change the game's progress in a way the helper can't leave as
    it was (a progress flag, EA), or "". The game's progress and variable 110 the helper keeps."""
    for ev in quest.events:
        if ev.battle is not None:
            continue
        for at, what, numbers in story_changes(scripts[ev.script], lengths, mode):
            if what == "progress flag":
                flag, on = numbers
                return (f"the event {ev.name}'s script {'sets' if on else 'clears'} the game's progress flag "
                        f"{flag} (instruction EA at byte {at}): a side quest never moves the story")
    return ""
