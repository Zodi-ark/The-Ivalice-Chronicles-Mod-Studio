"""
The event setup records (Zodi's choice, 21 October: "Lets go with "One
shared helper mod""): for every event, the map it plays on, its weather and
time of day, its two pieces of music, its enemy battle, the player's deploy
areas, what follows it and its battle rules.

**Where they are.** Not in a table a mod can change through the mod loader,
but in the game's program, `FFT_enhanced.exe`: 887 slots of 24 bytes (WotL
Restoration's DLL's `SETUP_RECORD_SIZE` and `SETUP_RECORD_COUNT`; the
database's `EventId` has as many rows). Measured on Zodi's program
(12,158,720 bytes, 17 September 2026, read as data and never run): 713
records in the order of their events (1 to 399, 410 to 491, 512 to 743), the
other 174 slots all zero, from file offset 0x8EAEB0 (in its `.data`, 0x8ECAB0
from where the program is loaded). All 480 of the PlayStation's scenarios
(ATTACK.OUT's, events 1 to 490 without 400 to 409) are there: 447 byte for
byte, and 33 differ only in what follows them (29: a next event where the
PlayStation's went to the world map, and the like) or their music (4: events
137 and 138 have a second piece, 326 and 327 their one piece second). Events
578 and 579 hold what WotL Restoration's DLL checks before it changes them
(map 96, battle 527, 578's battle rules 163, 579 followed by the world map).

**How they're found**, as the helper finds them in the running game
(`find_table`): by WotL Restoration's pattern, `48 8D 1D ?? ?? ?? ?? 41 8B D4
BD 27 00 00 00`, once in the program's code: a `lea rbx, [rip + x]` of the
table, whose address is the instruction's end plus x; else by the records'
own bytes (events 1, 2 and 3 in a row). Either way the slots must look like
the table (`scan_table`): events 1 and 2 first, every record laid out as
the game's are (`record_problem`: bytes 21 and 23 zero, what follows one of
0, 0x80, 0x81 and 0x82, night and Ramza required 0 or 1, as in all 713 of
Zodi's program) with a higher event than the one before, at least the
PlayStation's 480. Since the helper's 1.0.1 (Zodi, 21 October: "Yes, make
1.0.1"), the table is read as far as its records go (empty slots among
them read past, up to `MOST_SLOTS`), not assumed to be 887 slots, so a game
update that moves it, or gives it more or fewer events, leaves it found;
one that lays its records out otherwise leaves it refused, saying which
slot and byte, rather than having a mod's change written into the wrong
byte. Zodi's program is found by the pattern, 887 slots: what follows them
isn't a record.

**The fields** (`FIELDS`) are the PlayStation's scenario table's (the
decompilation's `scenario_setup_t`, the FFHacktics wiki's ATTACK.OUT page),
each read and written as the helper does: the event (16 bits, never
changed), the map (2), the weather (3's low half: 0 to 4 in the game, the
Map Editor's None, Light, Normal, Strong, Very strong) and the map's
arrangement (3's high half: 0 to 2), night (4: 1, else day), music 1 and 2
(5 and 6, PlayStation music ids; the first plays as the event starts,
SwitchTrack takes turns between them), the enemy battle (16 bits at 7, its
ENTD battle), deploy areas 1 and 2 (16 bits at 9 and 11, the squads below),
a portrait and its unit (13, 14), the scene's units (16 bits at 15, a second
ENTD battle), Ramza required (17), the next event (16 bits at 18), what
follows (20: `WORLD_MAP` 0x80, `NEXT_EVENT` 0x81, `START_OVER` 0x82, 0 the
script's say) and the battle rules (22, `EnhancedBattleEvent`'s Key; 0 to
235 in Zodi's program). Bytes 21 and 23 are 0 in every record and aren't
fields.

**The deploy areas** are the program's squads (ATTACK.OUT's
`deploy_squad_t`, `event_scripts.Squad`): 768 of 12 bytes, each ending in
its own number, found by squads 0x100 to 0x102 in a row (`find_squads`;
Zodi's program has squad 0 at file offset 0x7AC6D0). So every event's
deployment can be drawn, not only the PlayStation's.

**What a mod gives the helper** (`FILE_NAME`): `EventSetup.json` at its top,
per event only the fields it changes, named as `FIELDS` names them
(`file_text`, `read_file_text`), and the helper among its dependencies
(`modconfig`). The helper, Mod Studio Event Setup (`HELPER_ID`, its source in
`helper/`, built into `tools/ModStudioEventSetup/`), applies every enabled
mod's file as the game starts, the later in Reloaded-II's order winning a
field two mods change, and the game's own values kept where no mod says
otherwise.

Nothing here imports Qt, and nothing of the game's program ships: the
records are read from the program on the machine Mod Studio runs on.
"""
from __future__ import annotations

import json
import re
import shutil
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

#: The program the records are read from: the Enhanced look's, in the game's own folder.
PROGRAM = "FFT_enhanced.exe"
#: A record's bytes; the slots the game's table has (as many as `EventId`
#: has rows), which the table is read for rather than assumed to have
#: (`scan_table`), up to `MOST_SLOTS`, should a game update give it more.
RECORD_BYTES, SLOTS, MOST_SLOTS = 24, 887, 2048
#: The least a table holds: the PlayStation's scenarios.
LEAST_RECORDS = 480

#: WotL Restoration's pattern (see the module's notes): `lea rbx, [rip + x]`,
#: `mov edx, r12d`, `mov ebp, 0x27`; x is the group.
PATTERN = re.compile(rb"\x48\x8D\x1D(.{4})\x41\x8B\xD4\xBD\x27\x00\x00\x00", re.DOTALL)
#: The `lea`'s length: the table is at its end plus x.
LEA_BYTES = 7
#: The records' own bytes: events 1, 2 and 3 in a row.
FIRST_RECORDS = re.compile(rb"\x01\x00.{22}\x02\x00.{22}\x03\x00", re.DOTALL)

#: What follows an event (its byte 20); 0 leaves it to the event's script.
WORLD_MAP, NEXT_EVENT, START_OVER = 0x80, 0x81, 0x82

#: The squads (see the module's notes): 12 bytes each, the last two its own
#: number, as many as `event_scripts.SQUAD_MOST`.
SQUAD_BYTES, SQUAD_MOST = 12, 0x300
SQUADS_IN_A_ROW = re.compile(rb".{10}\x00\x01.{10}\x01\x01.{10}\x02\x01", re.DOTALL)

#: The helper (Zodi, 21 October: its name "Mod Studio Event Setup", its own
#: release and a copy in Mod Studio).
HELPER_ID = "fftivc.utility.modstudio.eventsetup"
HELPER_NAME = "Mod Studio Event Setup"
HELPER_VERSION = "1.0.2"
#: Where Mod Studio keeps its built copy, from the project's folder.
HELPER_FOLDER = "tools/ModStudioEventSetup"
#: Where Reloaded-II fetches it for a player whose mod needs it: its own
#: GitHub release, as `PluginData`'s `GitHubDependencies` names a dependency
#: (WotL Restoration's `ModConfig.json` names its three so): Zodi's
#: repository (21 October: "I created the github page",
#: github.com/Zodi-ark/Mod-Studio-Event-Setup), whose release holds what
#: Reloaded-II's Publish makes (the mod's .7z and its release metadata).
HELPER_RELEASE = {
    "Config": {
        "UserName": "Zodi-ark",
        "RepositoryName": "Mod-Studio-Event-Setup",
        "UseReleaseTag": True,
        "AssetFileName": "Mod.zip",
    },
    "ReleaseMetadataName": f"{HELPER_ID}.ReleaseMetadata.json",
}

#: The file a mod gives the helper, at its top, and the shape's version.
FILE_NAME = "EventSetup.json"
FILE_VERSION = 1


class SetupError(ValueError):
    """A program whose records can't be found or read, or a value a field can't hold."""


# =============================================================================
# The fields
# =============================================================================

@dataclass(frozen=True)
class Field:
    """One field of a record: its name in the helper's file, its byte, how
    many bytes (little endian), and for a part of a byte, its bits."""
    key: str
    at: int
    size: int = 1
    mask: int = 0

    @property
    def shift(self) -> int:
        return (self.mask & -self.mask).bit_length() - 1 if self.mask else 0

    @property
    def most(self) -> int:
        """The highest value it holds."""
        if self.mask:
            return self.mask >> self.shift
        return (1 << (8 * self.size)) - 1


FIELDS = (
    Field("Map", 2),
    Field("Weather", 3, mask=0x0F),
    Field("Arrangement", 3, mask=0xF0),
    Field("Night", 4),
    Field("Music1", 5),
    Field("Music2", 6),
    Field("EnemyBattle", 7, 2),
    Field("DeployArea1", 9, 2),
    Field("DeployArea2", 11, 2),
    Field("Portrait", 13),
    Field("PortraitUnit", 14),
    Field("SceneUnits", 15, 2),
    Field("RamzaRequired", 17),
    Field("NextEvent", 18, 2),
    Field("AfterEvent", 20),
    Field("BattleRules", 22),
)
#: The fields by name, without case (as the helper matches them).
FIELD_BY_KEY = {f.key.lower(): f for f in FIELDS}


def field_of(key: str) -> Optional[Field]:
    return FIELD_BY_KEY.get(str(key).lower())


def event_of(record: bytes) -> int:
    return struct.unpack_from("<H", record, 0)[0]


def value(record: bytes, field: Field) -> int:
    """A field's value in a record."""
    whole = int.from_bytes(record[field.at:field.at + field.size], "little")
    return (whole & field.mask) >> field.shift if field.mask else whole


def with_value(record: bytes, field: Field, number: int) -> bytes:
    """The record with one field set; SetupError for a value it can't hold."""
    if isinstance(number, bool) or not isinstance(number, int) or not 0 <= number <= field.most:
        raise SetupError(f"{field.key} holds 0 to {field.most}, not {number!r}")
    out = bytearray(record)
    if field.mask:
        out[field.at] = (out[field.at] & ~field.mask & 0xFF) | (number << field.shift)
    else:
        out[field.at:field.at + field.size] = number.to_bytes(field.size, "little")
    return bytes(out)


def values(record: bytes) -> dict:
    """`{key: value}` of every field."""
    return {f.key: value(record, f) for f in FIELDS}


def applied(record: bytes, changes: dict) -> bytes:
    """The record with a mod's changes (`{key: value}`) on it, field by field."""
    out = bytes(record)
    for key, number in (changes or {}).items():
        field = field_of(key)
        if field is None:
            raise SetupError(f"no field named {key!r}")
        out = with_value(out, field, number)
    return out


def changes_between(game: bytes, mod: bytes) -> dict:
    """`{key: value}`: the fields `mod` holds otherwise than `game`."""
    return {f.key: value(mod, f) for f in FIELDS if value(mod, f) != value(game, f)}


def tidy(game_records: dict, edits: dict) -> dict:
    """
    A mod's changes as they are worth keeping: only fields a record holds
    otherwise than the game's, only events with any (an event the game's
    program hasn't is kept as it is, for the helper to say so).
    """
    out = {}
    for event, changes in (edits or {}).items():
        record = game_records.get(int(event))
        kept = {}
        for key, number in (changes or {}).items():
            field = field_of(key)
            if field is None or (record is not None and value(record, field) == number):
                continue
            kept[field.key] = number
        if kept:
            out[int(event)] = kept
    return out


# =============================================================================
# Finding the table
# =============================================================================

@dataclass(frozen=True)
class Section:
    name: str
    address: int        # from where the program is loaded
    size: int           # in memory
    at: int             # in the file
    stored: int         # in the file


def sections(data: bytes) -> list:
    """A Windows program's sections; SetupError for anything else."""
    if len(data) < 0x40 or data[:2] != b"MZ":
        raise SetupError("it isn't a Windows program")
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe:pe + 4] != b"PE\0\0":
        raise SetupError("it isn't a Windows program")
    count, = struct.unpack_from("<H", data, pe + 6)
    optional_size, = struct.unpack_from("<H", data, pe + 20)
    first = pe + 24 + optional_size
    out = []
    for n in range(count):
        at = first + 40 * n
        if at + 40 > len(data):
            raise SetupError("its section table is cut short")
        name, size, address, stored, raw = struct.unpack_from("<8sIIII", data, at)
        out.append(Section(name.rstrip(b"\0").decode("latin-1"), address, size, raw, stored))
    return out


def file_offset(found: list, address: int) -> Optional[int]:
    """Where in the file the byte the program loads at `address` is, or None."""
    for section in found:
        if section.address <= address < section.address + max(section.size, section.stored):
            inside = address - section.address
            return section.at + inside if inside < section.stored else None
    return None


def address_of(found: list, at: int) -> Optional[int]:
    """The address the program loads its file's byte `at` at, or None."""
    for section in found:
        if section.at <= at < section.at + section.stored:
            return section.address + at - section.at
    return None


def record_problem(record: bytes) -> str:
    """
    Why a slot's 24 bytes aren't laid out as the game's setup records are,
    or "" when they are: bytes 21 and 23 zero, what follows (20) one of 0,
    0x80, 0x81 and 0x82, night (4) and Ramza required (17) 0 or 1, as in
    every one of the 713 in Zodi's program. A game update that laid the
    records out otherwise fails it, so no mod's change goes into the wrong
    byte (the helper's `Finder.RecordProblem`, in the same words).
    """
    if record[21]:
        return f"byte 21 is {record[21]}, not 0"
    if record[23]:
        return f"byte 23 is {record[23]}, not 0"
    if record[20] and record[20] not in (WORLD_MAP, NEXT_EVENT, START_OVER):
        return f"byte 20, what follows, is {record[20]}"
    if record[4] > 1:
        return f"byte 4, night, is {record[4]}"
    if record[17] > 1:
        return f"byte 17, Ramza required, is {record[17]}"
    return ""


def scan_table(data: bytes, at: int = 0) -> tuple:
    """
    `(slots, problem)` for the slots of 24 bytes from `at`: how many are the
    table's, read until a slot that is neither empty (all zero) nor a record
    laid out as the game's (`record_problem`) with a higher event than the
    one before, `MOST_SLOTS` at the most; and why they don't look like the
    setup table, or "" when they do: events 1 and 2 first, at least the
    PlayStation's 480 records. The game's own table is 887 slots, and what
    follows it in Zodi's program isn't a record, so it is read as 887; one a
    game update gave more or fewer is read as it is (the helper's
    `Finder.Scan`, in the same words).
    """
    previous = records = slots = 0
    stop = ""
    while slots < MOST_SLOTS and at + (slots + 1) * RECORD_BYTES <= len(data):
        record = data[at + slots * RECORD_BYTES:at + (slots + 1) * RECORD_BYTES]
        if any(record):
            event = event_of(record)
            if slots < 2 and event != slots + 1:
                return slots, f"its slot {slots} holds event {event}, not {slots + 1}"
            wrong = record_problem(record)
            if wrong or event <= previous:
                stop = (f"slot {slots}, whose {wrong}" if wrong
                        else f"slot {slots}, whose event {event} comes after event {previous}")
                break
            previous, records = event, records + 1
        elif slots < 2:
            return slots, f"its slot {slots} is empty"
        slots += 1
    if records < LEAST_RECORDS:
        return slots, (f"it has {records} records" + (f" before {stop}" if stop else "")
                       + f", fewer than the PlayStation's {LEAST_RECORDS}")
    return slots, ""


def table_problem(data: bytes, at: int = 0) -> str:
    """Why the slots from `at` don't look like the setup table, or "" when they do (`scan_table`)."""
    return scan_table(data, at)[1]


@dataclass(frozen=True)
class Table:
    """The table as found: where in the file, how, its slots and its records by event."""
    at: int
    how: str            # "pattern" or "records"
    slots: tuple
    records: dict

    @property
    def events(self) -> list:
        return list(self.records)


def _table_at(data: bytes, at: int, how: str) -> Table:
    count, _problem = scan_table(data, at)
    slots = tuple(data[at + n * RECORD_BYTES:at + (n + 1) * RECORD_BYTES] for n in range(count))
    records = {event_of(slot): slot for slot in slots if any(slot)}
    return Table(at, how, slots, records)


def find_by_pattern(data: bytes, found: Optional[list] = None) -> tuple:
    """`(file offset or None, why not)`: the table where WotL's pattern points."""
    found = sections(data) if found is None else found
    hits = list(PATTERN.finditer(data))
    if len(hits) != 1:
        return None, f"WotL Restoration's pattern is in it {len(hits)} times, not once"
    hit = hits[0]
    address = address_of(found, hit.start())
    if address is None:
        return None, "WotL Restoration's pattern is outside its sections"
    target = address + LEA_BYTES + struct.unpack("<i", hit.group(1))[0]
    at = file_offset(found, target)
    if at is None:
        return None, "WotL Restoration's pattern points outside what the file holds"
    problem = table_problem(data, at)
    return (None, f"where WotL Restoration's pattern points, {problem}") if problem else (at, "")


def find_by_records(data: bytes) -> tuple:
    """`(file offset or None, why not)`: the one run of events 1, 2 and 3 that looks like the table."""
    good = [m.start() for m in FIRST_RECORDS.finditer(data) if not table_problem(data, m.start())]
    if len(good) != 1:
        return None, f"the records' own bytes are in it {len(good)} times, not once"
    return good[0], ""


def find_table(data: bytes) -> Table:
    """The setup table in a program's bytes (see the module's notes); SetupError with the reasons."""
    found = sections(data)
    at, why = find_by_pattern(data, found)
    if at is not None:
        return _table_at(data, at, "pattern")
    at, why_records = find_by_records(data)
    if at is not None:
        return _table_at(data, at, "records")
    raise SetupError(f"{why}, and {why_records}")


def find_squads(data: bytes) -> Optional[int]:
    """Where squad 0 is in the program's file (squads 0x100 to 0x102 in a row, once), or None."""
    hits = [m.start() for m in SQUADS_IN_A_ROW.finditer(data)]
    if len(hits) != 1:
        return None
    at = hits[0] - 0x100 * SQUAD_BYTES
    return at if at >= 0 and at + SQUAD_MOST * SQUAD_BYTES <= len(data) else None


# =============================================================================
# The program on this machine
# =============================================================================

@dataclass(frozen=True)
class Program:
    """A program's records, its squads' bytes (squad 0 first; empty if not found), and where it is."""
    path: Path
    table: Table
    squads: bytes

    @property
    def records(self) -> dict:
        return self.table.records


_read: dict = {}


def read_program(path) -> Program:
    """
    The setup records of the program at `path`, read once for each size and
    time of the file. OSError when it can't be read, SetupError when its
    records can't be found.
    """
    path = Path(path)
    stat = path.stat()
    key = (str(path), stat.st_size, stat.st_mtime_ns)
    if key not in _read:
        data = path.read_bytes()
        table = find_table(data)
        squads_at = find_squads(data)
        squads = data[squads_at:squads_at + SQUAD_MOST * SQUAD_BYTES] if squads_at is not None else b""
        _read.clear()
        _read[key] = Program(path, table, squads)
    return _read[key]


def squad(squads: bytes, number: int):
    """Squad `number` from the program's squads (`event_scripts.Squad`), or None."""
    from . import event_scripts as es
    at = SQUAD_BYTES * number
    if not 0 <= number < SQUAD_MOST or at + SQUAD_BYTES > len(squads):
        return None
    tiles, x, y, level, orientation, most, map_number = struct.unpack_from("<IbbBBBB", squads, at)
    return es.Squad(tiles, x, y, level, orientation, most, map_number)


def deployment(record: bytes, squads: bytes):
    """Where the player's units stand as the record's battle starts (`event_scripts.Deployment`), or None."""
    from . import event_scripts as es
    return es.deployment_from_row(record, lambda number: squad(squads, number))


def scenario(record: bytes):
    """The record as the Event Editor's scenarios are (`battle_maps.Scenario`)."""
    from .battle_maps import Scenario
    return Scenario(event_of(record), record[2], record[3], bool(record[4]),
                    struct.unpack_from("<H", record, 7)[0], struct.unpack_from("<H", record, 15)[0],
                    bool(record[17]))


def music(record: bytes) -> tuple:
    """The record's two pieces, `(first, second)`, PlayStation music ids (0: none)."""
    return (record[5], record[6])


# =============================================================================
# The helper's file
# =============================================================================

def file_text(edits: dict) -> str:
    """
    `EventSetup.json` for a mod's changes (`{event: {key: value}}`): per
    event, in order, only its changed fields, in `FIELDS`' order, an event
    to a line so a person can read it.
    """
    events = []
    for event in sorted(int(e) for e in edits):
        changes = {str(k).lower(): v for k, v in (edits.get(event) or edits.get(str(event)) or {}).items()}
        entry = {"Event": event}
        for f in FIELDS:
            if f.key.lower() in changes:
                entry[f.key] = int(changes[f.key.lower()])
        if len(entry) > 1:
            events.append(entry)
    lines = ["{", f'  "Helper": {json.dumps(HELPER_ID)},', f'  "Version": {FILE_VERSION},']
    if events:
        lines.append('  "Events": [')
        lines += [f"    {json.dumps(entry)}" + ("," if n < len(events) - 1 else "") for n, entry in enumerate(events)]
        lines.append("  ]")
    else:
        lines.append('  "Events": []')
    return "\n".join(lines + ["}"]) + "\n"


def _whole(number) -> bool:
    return isinstance(number, int) and not isinstance(number, bool)


def read_file_text(text: str) -> tuple:
    """
    `({event: {key: value}}, problems)` from an `EventSetup.json`, read as
    the helper reads it: the `Events` list's entries, each an `Event` number
    and fields named as `FIELDS` names them (without case), each a whole
    number the field holds; a later entry for the same event changes the
    fields it names. What the helper would skip is left out and said in
    `problems`.
    """
    problems = []
    try:
        top = json.loads(text)
    except (TypeError, ValueError) as exc:
        return {}, [f"it isn't JSON ({exc})"]
    if not isinstance(top, dict) or not isinstance(top.get("Events"), list):
        return {}, ["it has no Events list"]
    out = {}
    for n, entry in enumerate(top["Events"], 1):
        if not isinstance(entry, dict):
            problems.append(f"entry {n} isn't a list of fields")
            continue
        event = next((v for k, v in entry.items() if k.lower() == "event"), None)
        if not _whole(event) or not 1 <= event <= 0xFFFF:
            problems.append(f"entry {n} has no event number")
            continue
        for key, number in entry.items():
            if key.lower() == "event":
                continue
            field = field_of(key)
            if field is None:
                problems.append(f"event {event}: no field is named {key}")
            elif not _whole(number) or not 0 <= number <= field.most:
                problems.append(f"event {event}: {field.key} holds 0 to {field.most}, not {number!r}")
            else:
                out.setdefault(event, {})[field.key] = number
    return out, problems


# =============================================================================
# The helper, for an author's own testing
# =============================================================================

def helper_source(project_root) -> Path:
    """Mod Studio's built copy of the helper."""
    return Path(project_root) / HELPER_FOLDER


def _version(text) -> tuple:
    parts = []
    for part in str(text or "").split("."):
        digits = re.match(r"\d+", part.strip())
        parts.append(int(digits.group()) if digits else 0)
    return tuple(parts + [0] * (3 - len(parts)))[:3]


def installed_version(mods_folder) -> Optional[str]:
    """The helper's version in a Reloaded-II mods folder, or None when it isn't there."""
    config = Path(mods_folder) / HELPER_ID / "ModConfig.json"
    try:
        return str(json.loads(config.read_text(encoding="utf-8-sig")).get("ModVersion") or "0")
    except (OSError, ValueError, AttributeError):
        return None


def install_helper(project_root, mods_folder) -> str:
    """
    Puts Mod Studio's copy of the helper in a Reloaded-II mods folder when it
    isn't there or is older; never over a newer one. Returns "installed",
    "updated" or "kept"; OSError when it can't be copied.
    """
    source = helper_source(project_root)
    ours = json.loads((source / "ModConfig.json").read_text(encoding="utf-8-sig")).get("ModVersion")
    there = installed_version(mods_folder)
    if there is not None and _version(there) >= _version(ours):
        return "kept"
    target = Path(mods_folder) / HELPER_ID
    target.mkdir(parents=True, exist_ok=True)
    for path in sorted(source.iterdir()):
        if path.is_file():
            shutil.copy2(path, target / path.name)
    return "installed" if there is None else "updated"
