"""
Which map each battle is fought on, for the Encounters page's map (Zodi, 12
October). Read from two of the PlayStation files The Ivalice Chronicles
keeps in `fftpack/`, measured on the game's own copies:

- **The scenarios**, `fftpack/overlay/event_attack_out.en.bin` (the
  PlayStation's ATTACK.OUT), from 0x10938: 24 bytes a scenario, numbered
  from 1, up to the first scenario of all zeros (480 of them). Laid out as
  the FFHacktics wiki's "ATTACK.OUT" page says ("Loading Maps"): a u16
  number, the map, the weather, 1 for night, two music numbers, a u16 ENTD
  battle (its units), two u16 placement grids; and, measured here, a u16 at
  15 naming a second ENTD for a scene's own units (in "Introducing Algus" 393
  and its "BS" 262), 1 at 17 where the scenario is a battle, a u16 at 18
  naming the next scenario, and a byte at 20 saying what follows (0x80 the
  world map, 0x81 another scenario, 0x82 a reset).
- **The random battles**, `fftpack/world_wldcore_bin.en.bin` (WLDCORE.BIN),
  as the wiki's "Random Battles" page lays them out: from 0x2FA64, 24 bytes
  a place on the world map, eight ENTD battles at 14 and the map at 22; and
  from 0x2FFC0, 10 bytes a floor of the deep dungeon, its map and eight ENTD
  battles, up to a map of 0.

So an ENTD battle is fought on the maps its scenarios and random battles
name, the scenarios' first. Measured: 413 of the 512 battles have one; the
other 99 are named nowhere (0, 253 to 255, 331 to 383, 470 to 511: most are
FFTPatcher's "Test" battles or nameless). 41 are fought on two maps: 33
random battles two places share, and 8 tutorial battles (9 to 12, 33, 45 to
47) that are also random ones.

**Which of a battle's places first.** Each place on the world map has
three rows. Where it has battles of its own for only two, its third row
borrows other places' battles: their fifth ones ("Zeirchele Falls East 5"
in Tchigolith Fenlands' third row) or the deep dungeon's (Terminus 1 to 4
in Dugeura Pass's). The borrowed battles' units stand on the ground of
their own place's map, but not always on the borrowing one's: of the 33
battles borrowed from another map, 20 have units off its ground. So a
battle's places are taken in this order: the place with more battles of
its own first (battles no other place has; a borrowing row has few or
none), and where that is a tie (the four deep dungeon floors whose battles
a world place also borrows), the deep dungeon's floor. Then on 411 of the
413 battles every unit stands on the first map's ground; the other two
(70, nameless, and the scene 269) have units off it on their only map.
Taken in table order, 25 battles would show the borrowing map first, 17 of
them with units off its ground.

Nothing here imports Qt.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

#: The files, relative to the unpacked game.
SCENARIO_FILE = "fftpack/overlay/event_attack_out.en.bin"
RANDOM_FILE = "fftpack/world_wldcore_bin.en.bin"

SCENARIOS_AT, SCENARIO_BYTES = 0x10938, 24
RANDOM_AT, RANDOM_END, RANDOM_BYTES = 0x2FA64, 0x2FFBC, 24
DEEP_AT, DEEP_BYTES, DEEP_MOST = 0x2FFC0, 10, 16


@dataclass(frozen=True)
class Scenario:
    number: int
    map: int
    weather: int
    night: bool
    battle: int          # its ENTD battle
    scene: int           # a second ENTD battle, for a scene's own units (0: none)
    is_battle: bool


@dataclass(frozen=True)
class RandomBattle:
    map: int
    battles: tuple       # eight ENTD battles, the same one may come twice
    deep_dungeon: bool


class BattleMapError(ValueError):
    """A file that isn't the shape this module reads."""


def read_scenarios(data: bytes) -> list:
    """The scenario table: every scenario from `SCENARIOS_AT` to the first all zero one."""
    first = data[SCENARIOS_AT:SCENARIOS_AT + 2 * SCENARIO_BYTES]
    if len(first) < 2 * SCENARIO_BYTES or struct.unpack_from("<HH", first[0:2] + first[24:26]) != (1, 2):
        raise BattleMapError("no scenario table where ATTACK.OUT keeps it (scenarios 1 and 2 at 0x10938)")
    out = []
    at = SCENARIOS_AT
    while at + SCENARIO_BYTES <= len(data):
        row = data[at:at + SCENARIO_BYTES]
        if not any(row):
            break
        number, = struct.unpack_from("<H", row, 0)
        battle, = struct.unpack_from("<H", row, 7)
        scene, = struct.unpack_from("<H", row, 15)
        out.append(Scenario(number, row[2], row[3], bool(row[4]), battle, scene, bool(row[17])))
        at += SCENARIO_BYTES
    return out


def read_random_battles(data: bytes) -> list:
    """The random battles on the world map, then the deep dungeon's floors."""
    if len(data) < DEEP_AT + DEEP_BYTES:
        raise BattleMapError("WLDCORE.BIN ends before its random battles do")
    out = []
    for at in range(RANDOM_AT, RANDOM_END, RANDOM_BYTES):
        row = data[at:at + RANDOM_BYTES]
        out.append(RandomBattle(row[22], tuple(row[14:22]), False))
    for n in range(DEEP_MOST):
        row = data[DEEP_AT + DEEP_BYTES * n:DEEP_AT + DEEP_BYTES * (n + 1)]
        if len(row) < DEEP_BYTES or not row[0]:
            break
        out.append(RandomBattle(row[0], tuple(row[2:10]), True))
    return out


@dataclass
class BattleMaps:
    """`maps[battle]`: the maps an ENTD battle is fought on, the scenarios' first."""
    maps: dict
    scenarios: list
    random: list
    problem: str = ""

    def of(self, battle: int) -> list:
        return list(self.maps.get(int(battle), []))

    def scenario_for(self, battle: int, map_number: int) -> Optional[Scenario]:
        """The first scenario fighting or showing `battle` on `map_number` (its weather and time)."""
        for scenario in self.scenarios:
            if scenario.map == map_number and battle in (scenario.battle, scenario.scene):
                return scenario
        return None


def battle_maps(scenarios: list, random: list) -> dict:
    """
    `{ENTD battle: [maps]}` from the two tables: the scenarios' maps in
    their order, then the random battles' places, those with more battles
    of their own first, the deep dungeon's floors first of equals (see the
    module's notes).
    """
    out = {}

    def add(battle, map_number):
        if battle and map_number:
            found = out.setdefault(battle, [])
            if map_number not in found:
                found.append(map_number)

    for scenario in scenarios:
        add(scenario.battle, scenario.map)
        add(scenario.scene, scenario.map)
    rows_of = {}
    for row, place in enumerate(random):
        for battle in set(place.battles):
            if battle:
                rows_of.setdefault(battle, []).append(row)

    def own(row):
        """How many of a row's battles no other row has."""
        return sum(1 for battle in set(random[row].battles) if battle and len(rows_of[battle]) == 1)

    for battle in sorted(rows_of):
        for row in sorted(rows_of[battle], key=lambda r: (-own(r), not random[r].deep_dungeon, r)):
            add(battle, random[row].map)
    return out


def read_battle_maps(game_dir) -> BattleMaps:
    """
    The maps an unpacked game's battles are fought on. Missing or unreadable
    files leave the tables empty and say so in `problem`, so a page shows the
    encounters it can't place rather than none.
    """
    game = Path(game_dir) if game_dir else None
    scenarios, random, problems = [], [], []
    for relative, reader, into in ((SCENARIO_FILE, read_scenarios, scenarios),
                                   (RANDOM_FILE, read_random_battles, random)):
        try:
            into.extend(reader((game / relative).read_bytes()))
        except (OSError, TypeError, BattleMapError) as exc:
            problems.append(f"{relative}: {exc}")
    return BattleMaps(battle_maps(scenarios, random), scenarios, random, "; ".join(problems))
