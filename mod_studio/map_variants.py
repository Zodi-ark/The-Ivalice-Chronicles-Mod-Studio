"""
A map's variants: which of its lightings and which sky a battle meets
(measured 21 October, late evening, on the 1.5.2 database and Zodi's
program; `claude/map-research.md`'s open question 3).

**The `Map` table** has a row for every map number, 0 to 128, its
`Unknown14` a list of variants of 24 numbers each. Read against the setup
records of all 713 of the game's events (`event_setup`), the first five
say when a variant applies:

- 0, the time: 0 day and 1 night, as an event's Night says; 2 either;
- 1, the weather: 0 to 4, as an event's Weather says; 5 any;
- 2, the arrangement: as an event's Arrangement says; -1 any;
- 3, a `MapVariationEvent` key: only the events its row names (`Unknown8`,
  and the list `UnknownC`); 0 any. Each of the table's 13 keys names
  events set on exactly the map whose row uses it (085's 3: events 15 to
  25, all on 085);
- 4, a random battle, 1 to 6; 0 a story or event battle.

Every map's first variant but 005's is 2, 5, -1, 0, 0: any story or event
battle (005's two are night and day, both in no weather). Every one of the
713 events meets one of its map's variants, and none meets two that name
any of the five, so the variant an event meets is the one naming most
(`variant_of`; where two named as much, the last would be the choice: the
game's own data never tells), and the first where it meets none.

**Its lighting.** The variants with no random battle are, in order, the
entries of `RefinedBgTexture`'s story lists (`Unknown8`, `map_enhanced`'s
"story" lightings) on 126 of the 129 rows; on the other three (008, 011
and 049) some groups have a list of another length, which
`map_enhanced.lightings_from_database` reads as their first entry. Random
battle n is the entry n - 1 of the random lists (`Unknown18`).

**Its sky**: 14 to 16 the colour at the top, red, green and blue, 17 to 19
at the bottom; -1 in all six where the variant names none. 022's: 74, 132,
218 over 76, 88, 24, and the game draws what the row says (Zodi's test 9,
22 October: magenta over green, as Mod Studio wrote them). 111 of the 271
variants, all of them story ones, name none, and behind those battles the
game draws **the classic map's sky** (`classic_sky`): the background
colours of the lights its classic files have for the battle's time,
weather and arrangement. Measured on two of his screenshots: 023's events
53 and 54, by day in strong weather, the classic 32, 47, 47 over 100,
104, 108 (seen as 20, 35, 42 over 83, 91, 104), and 048's clear day, 36,
52, 124 over 120, 196, 236 (seen as 17, 40, 142 over 89, 164, 221): each a
little darker and deeper, likely the game's grading of the picture's
colours (the test's magenta and green, at the ends of the scale, came
through almost unchanged). The remaster's own skies are often near the classic
ones (019's top 24, 70, 138 against 24, 70, 121). A variant's events can
be in several weathers (12 of the 111: 049's in clear, rain and storm),
each with its own sky; `sky_state` says which one a page shows.

**The post effects** (22 October's afternoon, Zodi's "the sky color does
not quite seem to match"): each number below lies within the keys of the
table it is read as, over all 271 variants: 5 `PostEffectGlare` (1 to
17, of keys 1 to 19), 6 `PostEffectLUT` (0 to 27, of 0 to 30; 1 on 085's
random battles 4 to 6, whose skies are darker), 7 `PostEffectDepthLUT` (0
to 28, of 0 to 29), 13 `PostEffectDOF` (27, 30, 31, of 1 to 34). A depth
LUT row's last three numbers are a colour for what
is farthest, 0.5 leaving a channel as it is (`depth_far_tint`), and the
sky is the farthest of the picture: event 004's battle (056's first
variant, depth LUT 28: 0.344, 0.416, 0.507) has its Background's 48, 56,
48 over 48, 56, 96 seen in the game as about 25, 42, 49 over 31, 50, 94,
which the far colour gives (33, 47, 49 over 33, 47, 97) within the
screenshot's shading. Rows 0 and 16 leave every colour as it is (022's,
whose magenta and green came through as written). What the glare, the
LUT and the depth LUT's other five numbers do isn't measured; 9 and 23 are
set together on two variants that name no time, weather or event of
their own (007's third, 010's second: 4001 and 4002, likely a condition
of the story's).

Nothing here imports Qt; every function takes what it reads as arguments.
"""
from __future__ import annotations

import json
import sqlite3
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

#: The table, its key's column and the column holding the variants.
MAP_TABLE, VARIANTS_COLUMN = "Map", "Unknown14"
EVENT_TABLE = "MapVariationEvent"
#: The places of what a variant says, in its 24 numbers.
TIME, WEATHER, ARRANGEMENT, EVENT_SET, RANDOM = 0, 1, 2, 3, 4
SKY_TOP, SKY_BOTTOM = slice(14, 17), slice(17, 20)
#: A variant's "any" for each.
ANY_TIME, ANY_WEATHER, ANY_ARRANGEMENT, ANY_EVENT = 2, 5, -1, 0
#: How many numbers a variant has.
VARIANT_SIZE = 24
#: Where a variant names its picture's post effects (the module's notes):
#: `PostEffectLUT` and `PostEffectDepthLUT` keys.
POST_LUT, DEPTH_LUT = 6, 7
#: The depth LUT table, its far colour's columns (red, green, blue) and
#: the value that leaves a channel as it is.
DEPTH_TABLE = "PostEffectDepthLUT"
DEPTH_FAR = ("Unknown1C", "Unknown20", "Unknown24")
NEUTRAL = 0.5


@dataclass
class Variant:
    """One of a map's variants: its place in the row's list and its 24 numbers."""
    index: int
    values: list = field(default_factory=list)

    def _get(self, at: int, default: int) -> int:
        try:
            return int(self.values[at])
        except (IndexError, TypeError, ValueError):
            return default

    @property
    def time(self) -> int:
        return self._get(TIME, ANY_TIME)

    @property
    def weather(self) -> int:
        return self._get(WEATHER, ANY_WEATHER)

    @property
    def arrangement(self) -> int:
        return self._get(ARRANGEMENT, ANY_ARRANGEMENT)

    @property
    def event_set(self) -> int:
        return self._get(EVENT_SET, ANY_EVENT)

    @property
    def random(self) -> int:
        return self._get(RANDOM, 0)

    @property
    def depth_lut(self) -> int:
        """Its `PostEffectDepthLUT` key (`depth_far_tint`)."""
        return self._get(DEPTH_LUT, 0)

    def _colour(self, where: slice) -> Optional[tuple]:
        part = self.values[where] if len(self.values) >= where.stop else []
        try:
            colour = tuple(int(v) for v in part)
        except (TypeError, ValueError):
            return None
        if len(colour) != 3 or any(not 0 <= v <= 255 for v in colour):
            return None
        return colour

    @property
    def sky_top(self) -> Optional[tuple]:
        """The sky's colour at the top, `(r, g, b)`, or None where the variant names none."""
        return self._colour(SKY_TOP)

    @property
    def sky_bottom(self) -> Optional[tuple]:
        return self._colour(SKY_BOTTOM)

    def with_sky(self, top: Optional[tuple], bottom: Optional[tuple]) -> list:
        """Its numbers with the sky's colours given (None: -1, none named)."""
        out = list(self.values) + [0] * max(0, VARIANT_SIZE - len(self.values))
        for where, colour in ((SKY_TOP, top), (SKY_BOTTOM, bottom)):
            out[where] = [int(v) for v in colour] if colour is not None else [-1, -1, -1]
        return out

    def specific(self) -> int:
        """How many of time, weather, arrangement and event it names."""
        return sum((self.time != ANY_TIME, self.weather != ANY_WEATHER,
                    self.arrangement != ANY_ARRANGEMENT, self.event_set != ANY_EVENT))


def parse_variants(text) -> list:
    """`[Variant]` from a `Map` row's `Unknown14` (its JSON text, or the list itself); empty for anything else."""
    try:
        found = json.loads(text) if isinstance(text, str) else text
    except ValueError:
        return []
    if not isinstance(found, list):
        return []
    return [Variant(i, list(v)) for i, v in enumerate(found) if isinstance(v, list)]


def variants_text(variants: list) -> str:
    """A `Map` row's `Unknown14` for `variants`, written as the database writes it (no spaces)."""
    return json.dumps([list(v.values) for v in variants], separators=(",", ":"))


def _read(sqlite_path, sql: str, args: tuple = ()) -> list:
    if not sqlite_path or not Path(sqlite_path).is_file():
        return []
    try:
        con = sqlite3.connect(f"file:{Path(sqlite_path).as_posix()}?mode=ro", uri=True)
        try:
            return con.execute(sql, args).fetchall()
        finally:
            con.close()
    except sqlite3.Error:
        return []


def read_variants(sqlite_path, number: int, rows: Optional[dict] = None) -> list:
    """
    Map `number`'s variants: the game's `Map` row's, or the mod's
    (`rows`: `{number: {column: value}}`, `unmodelled_table_edits["Map"]`'s
    shape, keyed by the map alone) where it changes the column.
    """
    edited = (rows or {}).get(number) or {}
    if VARIANTS_COLUMN in edited:
        return parse_variants(edited[VARIANTS_COLUMN])
    found = _read(sqlite_path, f'SELECT "{VARIANTS_COLUMN}" FROM "{MAP_TABLE}" WHERE Key = ?', (int(number),))
    return parse_variants(found[0][0]) if found else []


def depth_far_tint(sqlite_path, key: int, rows: Optional[dict] = None) -> tuple:
    """
    `(r, g, b)`: what the game multiplies the farthest of the picture, the
    sky, by for `PostEffectDepthLUT` row `key` (a variant's `depth_lut`):
    its far colour over `NEUTRAL` (the module's notes), the mod's row
    (`rows`: `{key: {column: value}}`, `unmodelled_table_edits`' shape)
    over the game's. `(1.0, 1.0, 1.0)` where no row is found.
    """
    edited = (rows or {}).get(int(key)) or {}
    found = _read(sqlite_path, f'SELECT {", ".join(DEPTH_FAR)} FROM "{DEPTH_TABLE}" WHERE Key = ?', (int(key),))
    game = dict(zip(DEPTH_FAR, found[0])) if found else {}
    out = []
    for column in DEPTH_FAR:
        value = edited.get(column, game.get(column))
        try:
            out.append(max(0.0, float(value)) / NEUTRAL)
        except (TypeError, ValueError):
            return (1.0, 1.0, 1.0)
    return tuple(out)


def event_sets(sqlite_path) -> dict:
    """`{key: frozenset of events}` from `MapVariationEvent`: each row's `Unknown8` and its list `UnknownC`."""
    out = {}
    for key, first, more in _read(sqlite_path, f'SELECT Key, Unknown8, UnknownC FROM "{EVENT_TABLE}"'):
        try:
            listed = json.loads(more) if more else []
        except ValueError:
            listed = []
        out[int(key)] = frozenset(int(e) for e in [first] + list(listed) if e)
    return out


def meets(variant: Variant, event: int, night: int, weather: int, arrangement: int, sets: dict) -> bool:
    """Whether a story or event battle's setup (`event`, its Night, Weather and Arrangement) meets `variant`."""
    if variant.random:
        return False
    if variant.event_set != ANY_EVENT and event not in sets.get(variant.event_set, ()):
        return False
    if variant.time != ANY_TIME and variant.time != int(bool(night)):
        return False
    if variant.weather != ANY_WEATHER and variant.weather != int(weather):
        return False
    return variant.arrangement == ANY_ARRANGEMENT or variant.arrangement == int(arrangement)


def variant_of(variants: list, event: int, night: int, weather: int, arrangement: int,
               sets: dict) -> Optional[Variant]:
    """
    The variant a story or event battle meets (see the notes): of those its
    setup meets, the one naming most, the last of equals; the first variant
    when it meets none. None for a map with no variants.
    """
    met = [v for v in variants if meets(v, event, night, weather, arrangement, sets)]
    if met:
        return max(reversed(met), key=Variant.specific)
    return variants[0] if variants else None


def with_sky(variants: list, index: int, top: Optional[tuple], bottom: Optional[tuple]) -> list:
    """`variants` with variant `index`'s sky colours given (None: -1, none named), the others as they were."""
    return [Variant(v.index, v.with_sky(top, bottom) if v.index == index else list(v.values)) for v in variants]


def story_variants(variants: list) -> list:
    """The variants of story and event battles, in order: their places are the story lightings'."""
    return [v for v in variants if not v.random]


def story_index(variants: list, variant: Optional[Variant]) -> Optional[int]:
    """`variant`'s place among the map's story variants, its story lighting's in `RefinedBgTexture`."""
    story = story_variants(variants)
    for i, v in enumerate(story):
        if variant is not None and v.index == variant.index:
            return i
    return None


def random_variant(variants: list, random: int) -> Optional[Variant]:
    """The variant of random battle `random` (1 to 6), or None."""
    return next((v for v in variants if v.random == int(random)), None)


def events_by_variant(variants: list, setups: dict, number: int, sets: dict) -> dict:
    """
    `{variant index: [(event, night, weather, arrangement)]}`: the events
    whose setup (`{event: {"Map", "Night", "Weather", "Arrangement", ...}}`,
    `event_setup.values`' shape) sets them on map `number`, by the variant
    each meets, in event order, with the time, weather and arrangement each
    is set in (night 0 or 1).
    """
    out = {}
    for event, setup in sorted(setups.items()):
        try:
            if int(setup.get("Map", -1)) != int(number):
                continue
            battle = (int(bool(int(setup.get("Night", 0)))), int(setup.get("Weather", 0)),
                      int(setup.get("Arrangement", 0)))
            variant = variant_of(variants, int(event), *battle, sets)
        except (TypeError, ValueError):
            continue
        if variant is not None:
            out.setdefault(variant.index, []).append((int(event),) + battle)
    return out


def events_by_story_index(variants: list, setups: dict, number: int, sets: dict) -> dict:
    """
    `{story index: [events]}`: the events whose setup sets them on map
    `number`, by the story variant each meets (`events_by_variant`).
    """
    out = {}
    by_index = {v.index: v for v in variants}
    for index, met in events_by_variant(variants, setups, number, sets).items():
        story = story_index(variants, by_index.get(index))
        if story is not None:
            out.setdefault(story, []).extend(event for event, *_battle in met)
    return {story: sorted(events) for story, events in out.items()}


def sky_state(variant: Variant, met: list, arrangement: int = 0) -> tuple:
    """
    `(night, weather, arrangement)`: the battle whose sky stands for
    `variant`'s where it names no sky colours, as the game draws each
    battle's own (`classic_sky`): of the events that meet it (`met`,
    `events_by_variant`'s), those in `arrangement` (the one a page shows)
    if any are, the setup most of them have, the first event's among
    equals; with none, the variant's own time, weather and arrangement
    where it names them, else by day, in no weather, in `arrangement`.
    """
    here = [m for m in met if m[3] == arrangement] or list(met)
    if here:
        counts = Counter(tuple(m[1:]) for m in here)
        most = max(counts.values())
        return next(tuple(m[1:]) for m in here if counts[tuple(m[1:])] == most)
    return (variant.time if variant.time in (0, 1) else 0,
            variant.weather if 0 <= variant.weather <= 4 else 0,
            variant.arrangement if variant.arrangement != ANY_ARRANGEMENT else int(arrangement))


def classic_sky(index, night: int, weather: int, arrangement: int) -> Optional[tuple]:
    """
    `((r, g, b), (r, g, b))`, top and bottom: the sky the game draws behind
    a battle whose variant names no sky colours (see the notes), the
    background colours of the lights the map's classic files have for its
    time, weather and arrangement (`index`, its `map_classic.MapIndex`;
    `MapIndex.sources`: the state's own lights, else the default state's).
    None for a map with no lights there.
    """
    from . import map_classic as mc
    if index is None:
        return None
    try:
        source = index.sources(mc.State(int(arrangement), bool(night), int(weather))).get("lights")
        if source is None:
            return None
        lights = mc.read_mesh((Path(index.folder) / source.file_name).read_bytes()).lights
    except (OSError, mc.MapError):
        return None
    if lights is None:
        return None
    return tuple(int(v) for v in lights.background_top), tuple(int(v) for v in lights.background_bottom)


def game_records(game_dir=None, program_path=None) -> dict:
    """
    `{event: setup record}`: the game's program's (`event_setup`, every
    event the game has) when it can be read, else the PlayStation's
    scenario table the unpacked game keeps (`battle_maps.SCENARIO_FILE`,
    the same 24 bytes a record, events 1 to 490), else none.
    """
    from . import battle_maps as bm
    from . import event_setup as su
    if program_path:
        try:
            return dict(su.read_program(Path(program_path)).records)
        except (OSError, su.SetupError):
            pass
    if not game_dir:
        return {}
    try:
        data = (Path(game_dir) / bm.SCENARIO_FILE).read_bytes()
    except OSError:
        return {}
    out = {}
    at = bm.SCENARIOS_AT
    while at + bm.SCENARIO_BYTES <= len(data):
        record = data[at:at + bm.SCENARIO_BYTES]
        if not any(record):
            break
        out[su.event_of(record)] = bytes(record)
        at += bm.SCENARIO_BYTES
    return out


def setups(records: dict, edits: Optional[dict] = None) -> dict:
    """`{event: {field: value}}` from setup records, with a mod's changes over them (`state.setup_edits`)."""
    from . import event_setup as su
    out = {}
    for event, record in records.items():
        changes = (edits or {}).get(event)
        if changes:
            try:
                record = su.applied(record, changes)
            except su.SetupError:
                pass
        out[event] = su.values(record)
    return out

