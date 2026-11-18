"""
A side quest in Mod Studio (Zodi, 28 October, "Side quest page": a page to
make a side quest and a new place by names, its events, battles, starts,
flags and marker, its battle on a quest map; signed off from its mock-up,
"Build it as shown", every option of a battle and its units there).

What a quest is in a mod is `side_quests.py`'s: a folder
`ModStudioQuests/<quest>/` holding `quest.json`, its events' scripts and
its battles' units, and its events' words in the game's folder for scenes'
words. Here it is the same, held while the mod is open (`QuestEdits`: the
quest, its files' bytes, its events' words in each language), and seen as
**steps** (`steps`): each of its starts, the events that start plays in the
order they play (`plays`: a scene and the scenes after it; a battle, the
scene as it starts, the scene once it is won, and what follows), and the
flags those events set. A step Mod Studio makes plays once: its start
waits until a flag of its own is set, which its last event sets as it ends
(`set_flag_at_end`, as 117 of the game's scenes set a variable: clear it,
add 1, then the end); the step after it waits for that flag.

- **Made from the game's** (`Game`): a scene is a copy of one of the
  game's (its script, its setup, its words in every language the game has
  them, any progress flag it would set taken out: a side quest never moves
  the story, `side_quests.story_problem`); a battle is a copy of one of the
  game's battles (its 16 units, and the setup of the event that fights it:
  its map, music, weather, time of day, deploy areas and the rest), with
  the scene played once it is won made from the game's victory scene
  (event 094, which has no unit or place of its own) with a line of words.
- **How a battle is won and lost** (Mod Studio Framework 1.12.0, Zodi's
  choices of 28 October: every enemy beaten, one unit beaten, one unit worn
  down, Ramza on a tile; a unit protected; an objective in the quest's own
  words): `set_won_when`, `set_protect` (the scene once it is lost made from
  the game's game over, event 400, with a line first, as the game's own lost
  scenes end with its instructions), `set_objective` (its start scene shows
  it: a copy of the game's battle start, event 401, when it has none; the
  objective box of the game's openings put in one that shows no objective).
- **Where the player's units start** (Mod Studio Framework 1.14.0, Zodi's
  list, his second: "custom deploy areas"): a battle's own deploy areas, one
  or two, each its squares on the map (up to 25 within 5 by 5, clicked on
  the map), how many units start there and which way they face
  (`set_own_deploy`, `toggle_deploy_square`, `set_deploy`); its setup's, the
  game's, stay as where it starts when the helper can't give it its own. A
  tile where one of the battle's units starts on the field is never one of
  its squares (Zodi's test 45: `SQUARE_UNIT`, `squares_taken`), as in every
  one of the game's 703 deploy areas that have a battle.
- **Its tavern rumors** (Mod Studio Framework 1.15.0, Zodi's list, his
  third: a rumor read in a tavern, told once the story is far enough, after
  which the quest can start): `add_rumor` (its flag made, set once it is
  read), `set_rumor_words`, `toggle_rumor_town`, its When as a start's
  (`set_story_past`, `set_flag_condition`), and a step waiting until it is
  read (`set_waits_for_rumor`).
- **Every field of a unit** is written by name (`entd.unit_with`).
- **What Mod Studio Framework would say** (`problems`): the quest's file
  as it would be written, read as the helper reads it
  (`side_quests.read_quest_text`, its words word for word), and its scripts'
  flags and story.

Nothing here imports Qt.
"""
from __future__ import annotations

import copy
import functools
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from mod_studio import entd
from mod_studio import event_scripts as es
from mod_studio import event_setup as su
from mod_studio import pzd_data
from mod_studio import side_quests as sq

#: The game's victory scene with no unit or place of its own (the Deep Dungeon's): a battle's won scene is made
#: from it (test 15's "ambush won").
VICTORY_SCENE = 94
#: The game's scene whose first words are shown alone on the screen: the box a won scene's line is shown in.
WORDS_ALONE_SCENE = 14
#: The line a won scene's words are (a quest's lines are its own: the game looks a line up in its scene's file).
WON_LINE = 100
#: What a won scene says until it is changed.
WON_WORDS = "The battle is won."
#: Who says a line Mod Studio adds (one the game's words haven't): the game's Speaker row 1, which names no one,
#: as a line of the game's narration (WotL Restoration's "Received the Tynar Rouge!" has it). A Speaker key is
#: type 24; every line of WotL's 15 words files has one.
SPEAKER_KEY, NO_ONE = 24, 1
#: The setup a battle copies from the game's event that fights the battle it is made from.
BATTLE_SETUP = ("Map", "Weather", "Arrangement", "Night", "Music1", "Music2", "DeployArea1", "DeployArea2",
                "RamzaRequired", "Portrait", "PortraitUnit")
#: (28 October) The setup fields that place the player's units, a battle's: a scene copied from the game's has
#: them 0 (and Ramza not required). A scene the game plays inside a battle (Mandalia Plain's 017, deploy area 257)
#: has its battle's; played on its own, a setup with a deploy area opens the formation screen before it (his
#: program's `0x20E578`: the scenario's setup gives 0 for one, and the formation screen's thread starts; test 37's
#: first package had one).
DEPLOYS = ("DeployArea1", "DeployArea2")
SCENE_CLEARS = DEPLOYS + ("RamzaRequired",)
#: (1.12.0) The game's game over (event 400, played once every unit of the player's is beaten; no setup record): a
#: battle's scene once it is lost is made from it, a line of the quest's first, as the game's own lost scenes (21 and
#: nine more) say a line and end with its instructions; Mod Studio Framework has the game start over after it.
GAME_OVER_SCENE = 400
#: (1.12.0) The game's battle start (event 401, a sweep of the camera and its objective box), which a battle without a
#: scene of its own as it starts plays (Mod Studio Framework 1.11.1): a battle with an objective gets a copy of it
#: as its start scene, the helper's to show the objective in.
BATTLE_START_SCENE = 401
#: (1.12.0) A game's opening whose objective box (from the instruction 0x1C before 0x76 to the one after 0x77, its
#: DisplayConditions showing "Defeat all enemies!") a start scene showing no objective gets before its end.
OBJECTIVE_SCENE = 31
#: (1.12.0) DisplayConditions, and its first display that is an objective (BattleObjective's key + 8).
DISPLAY_CONDITIONS, FIRST_OBJECTIVE = sq.DISPLAY_CONDITIONS, 8
#: (1.12.0) The line a lost scene's words are, and what it says until it is changed.
LOST_LINE = WON_LINE
LOST_WORDS = "The battle is lost."
#: (1.12.0) A unit worn down to a share of its HP: the share a battle starts with.
SHARE = 25
#: The opcodes whose `line` is a line of the scene's words (and EB's `next_line`).
LINE_OPCODES = (0x10, 0x51, 0xEB, 0xC2)
#: Clear a variable, add to one: how a flag is set (`set_flag_at_end`).
CLEAR_OP, ADD_OP = 0xBE, 0xB0
#: The words' languages, the game's.
LANGUAGES = pzd_data.PZD_LANGUAGES
#: The language the page shows words in.
LANGUAGE = "en"


@dataclass
class QuestEdits:
    """One quest of the mod as the page edits it: its folder's name, the quest (`side_quests.Quest`), its files'
    bytes (scripts and battles' units, by file name), its events' words (`{event: {language: [PzdLine]}}`)."""
    folder: str
    quest: sq.Quest
    files: dict = field(default_factory=dict)
    words: dict = field(default_factory=dict)
    uid: str = field(default_factory=lambda: uuid.uuid4().hex)

    def copy(self) -> "QuestEdits":
        return QuestEdits(self.folder, copy.deepcopy(self.quest), dict(self.files), copy.deepcopy(self.words),
                          self.uid)


# =============================================================================
# Names
# =============================================================================

good_name = sq.good_name


def free_name(wanted: str, taken) -> str:
    """`wanted`, or it numbered past the names `taken` ("Ambush 2"), as a name may be (`good_name`)."""
    stem = " ".join("".join(ch if good_name(ch) else " " for ch in wanted).split())[:58] or "New"
    lowered = {t.lower() for t in taken}
    if stem.lower() not in lowered:
        return stem
    n = 2
    while f"{stem} {n}".lower() in lowered:
        n += 1
    return f"{stem} {n}"


def _safe(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "x"


def file_name(name: str, ending: str, taken) -> str:
    """A file of the quest's folder for `name`: its letters and digits, lowercase, numbered past those `taken`."""
    lowered = {t.lower() for t in taken}
    stem = _safe(name)[:40]
    out, n = f"{stem}{ending}", 2
    while out.lower() in lowered:
        out, n = f"{stem}_{n}{ending}", n + 1
    return out


def event_names(edits: QuestEdits) -> list:
    return [e.name for e in edits.quest.events]


# =============================================================================
# Reading and writing
# =============================================================================

def read_mod(mod_root) -> list:
    """
    Every quest of a mod as the page edits it, in its folders' order:
    `(folder, QuestEdits or None, problems)` (`side_quests.read_mod_quests`,
    which checks each as the helper does): its scripts and units read from
    its folder, its events' words from the mod's words files, in each
    language the mod has them.
    """
    out = []
    root = Path(mod_root)
    for folder, quest, problems in sq.read_mod_quests(root):
        if quest is None:
            out.append((folder, None, problems))
            continue
        here = root / sq.FOLDER / folder
        files = {}
        try:
            for name in used_files(quest):
                files[name] = (here / name).read_bytes()
        except OSError as exc:
            out.append((folder, None, [f"its files can't be read ({exc})"]))
            continue
        words = {}
        for ev in quest.events:
            if not ev.words:
                continue
            for language in LANGUAGES:
                path = root / sq.words_file(ev.words, language)
                if path.is_file():
                    try:
                        words.setdefault(ev.name, {})[language] = pzd_data.read_pzd(path)
                    except (OSError, ValueError):
                        continue
        out.append((folder, QuestEdits(folder, quest, files, words), []))
    return out


def used_files(quest: sq.Quest) -> list:
    """The files of a quest's folder its file names: its events' scripts and its battles' units."""
    out = [e.script for e in quest.events if e.battle is None and e.script]
    out += [b.units for b in quest.battles]
    return list(dict.fromkeys(out))


def as_written(edits: QuestEdits, mod_id: str) -> sq.Quest:
    """The quest as `write` writes it: each event with words of its own names its words file, by the mod and the
    quest (`side_quests.words_path`); one without none."""
    quest = copy.deepcopy(edits.quest)
    for ev in quest.events:
        if ev.battle is None:
            ev.words = sq.words_path(mod_id, edits.folder, ev.name) if edits.words.get(ev.name) else ""
        elif ev.battle.deploy:
            # (1.14.0) A deploy area of its own without squares yet (one just added, or all taken out) is left out:
            # the page's to fill, and with none left the battle starts on its setup's.
            ev.battle.deploy = [area for area in ev.battle.deploy if area.squares]
    return quest


def write(mod_root, mod_id: str, edits: QuestEdits) -> list:
    """
    Writes a quest into a mod: `ModStudioQuests/<folder>/` (its file and the
    files it names) and each of its events' words files in each language it
    has them (`pzd_data.write_pzd_bytes`). Returns the paths written.
    """
    quest = as_written(edits, mod_id)
    files = {name: edits.files[name] for name in used_files(quest) if name in edits.files}
    written = sq.write_quest(mod_root, edits.folder, quest, files)
    for ev in quest.events:
        if not ev.words:
            continue
        for language, lines in sorted(edits.words.get(ev.name, {}).items()):
            path = Path(mod_root) / sq.words_file(ev.words, language)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(pzd_data.write_pzd_bytes(lines))
            written.append(path)
    return written


def words_files(mod_id: str, edits: QuestEdits) -> list:
    """The mod's words files `write` writes for a quest, as paths under the mod's folder."""
    quest = as_written(edits, mod_id)
    return [sq.words_file(ev.words, language) for ev in quest.events if ev.words
            for language in sorted(edits.words.get(ev.name, {}))]


def problems(edits: QuestEdits, lengths: Optional[es.Lengths] = None, place_names=(), map_names=()) -> list:
    """
    What Mod Studio Framework would say of the quest as it would be
    written, in its own words (`side_quests.read_quest_text`, given the mod's
    places' and quest maps' names), then what its scripts' flags and story
    would (with the scripts' lengths): none when it reads it.
    """
    def read(name: str) -> bytes:
        if name not in edits.files:
            raise OSError(f"no file {name} in its folder")
        return edits.files[name]

    quest, said = sq.read_quest_text(sq.quest_text(as_written(edits, "mod")), read, edits.folder, place_names,
                                     map_names)
    if said:
        return said
    if lengths is None:
        return []
    out = []
    for check in (sq.flags_problem, sq.ramza_problem, sq.story_problem):
        try:
            problem = check(quest, edits.files, lengths)
        except (es.ScriptError, KeyError) as exc:
            problem = f"its scripts can't be read ({exc})"
        if problem:
            out.append(problem)
    return out


# =============================================================================
# Steps
# =============================================================================

@dataclass
class Step:
    """One start of the quest and what it plays: its start's place in the quest's starts, its events in the order
    they play, the flags they set, and the flag it plays once by (a condition that the flag is 0, the flag set
    by its own events), or ""."""
    start: int
    events: list
    sets: list
    once: str


def plays(quest: sq.Quest, name: str) -> list:
    """The events played from event `name` on, in order: a scene and the scene after it (`next_event`), and so on;
    a battle, the scene that plays as it starts, (1.12.0) the one once it is lost (instead of the rest: the game
    starts over after it), the one once it is won, and what follows that one."""
    out, seen = [], set()
    current = name
    while current and current not in seen:
        ev = quest.event_named(current)
        if ev is None:
            break
        seen.add(current)
        out.append(current)
        if ev.battle is None:
            current = ev.next_event
            continue
        for scene in (ev.battle.start, *(d.event for d in ev.battle.during), ev.battle.lost):
            if scene and scene not in seen and quest.event_named(scene) is not None:
                seen.add(scene)
                out.append(scene)
        current = ev.battle.won
    return out


def steps(quest: sq.Quest) -> list:
    """The quest's steps, one for each of its starts in their order."""
    out = []
    for index, start in enumerate(quest.starts):
        events = plays(quest, start.event)
        sets = []
        for name in events:
            ev = quest.event_named(name)
            for _, flag in (ev.flags_in_script if ev is not None else []):
                if flag not in sets:
                    sets.append(flag)
        once = next((c.flag for c in start.when if c.kind == "Flag" and c.value == 0 and c.flag in sets), "")
        out.append(Step(index, events, sets, once))
    return out


def unplayed(quest: sq.Quest) -> list:
    """The quest's events no step plays, in their order."""
    played = {name for step in steps(quest) for name in step.events}
    return [e.name for e in quest.events if e.name not in played]


def role(quest: sq.Quest, name: str) -> str:
    """What an event is in its step: "battle", "start" (the scene as a battle starts), "won" (once it is won), (1.12.0)
    "lost" (once it is lost) or "scene"."""
    ev = quest.event_named(name)
    if ev is not None and ev.battle is not None:
        return "battle"
    fight = quest.fight_of(name)
    if fight is not None:
        if any(d.event == name for d in fight.battle.during):
            return "during"
        return "start" if fight.battle.start == name else "lost" if fight.battle.lost == name else "won"
    return "scene"


def step_of(quest: sq.Quest, name: str) -> Optional[Step]:
    """The first step that plays event `name`, or None."""
    return next((s for s in steps(quest) if name in s.events), None)


# =============================================================================
# The game's own things a quest is made from
# =============================================================================

#: The instructions that start a map's moving parts (the maps' notes, Doors as an event plays them): 0x55 a texture
#: animation record (a door), 0x54 a 3D object (002's door, 006's and 036's parts).
MAP_ANIMATION_OPS = (0x54, 0x55)


class Game:
    """
    The game's things a quest's scenes and battles are made from: its
    unpacked folder (scripts, battles' units), its scripts' lengths, its
    program's setup records (`event_setup.read_program(...).records`, `{}`
    without it), its database (which words files a scene's words are in)
    and how a words file reads (the mod's copy and edits, when the page
    gives them; else the game's file).
    """

    def __init__(self, folder, records: Optional[dict] = None, sqlite_path=None,
                 read_text: Optional[Callable[[str, str], list]] = None, lengths: Optional[es.Lengths] = None):
        self.folder = Path(folder)
        self.lengths = lengths or es.lengths_from_game(self.folder)
        self.records = dict(records or {})
        self.sqlite_path = sqlite_path
        self.read_text = read_text or self._game_text
        self._doors = None

    def _game_text(self, stem: str, language: str) -> list:
        path = self.folder / f"{stem}.{language}.pzd"
        try:
            return pzd_data.read_pzd(path) if path.is_file() else []
        except (OSError, ValueError):
            return []

    def script(self, number: int) -> bytes:
        return (self.folder / es.script_relative(number)).read_bytes()

    def setup(self, number: Optional[int]) -> dict:
        record = self.records.get(number) if number is not None else None
        return su.values(record) if record is not None else {}

    def battle(self, number: int) -> Optional[bytes]:
        return es.battle_block(self.folder, number)

    def battle_event(self, battle: int) -> Optional[int]:
        """The game's event that fights ENTD battle `battle` (its setup's EnemyBattle and battle rules), the first
        such, or None."""
        for number in sorted(self.records):
            values = su.values(self.records[number])
            if values.get("EnemyBattle") == battle and values.get("BattleRules"):
                return number
        return None

    def door_events(self, map_number) -> list:
        """(Zodi, 4 November: a new scene is no copy of the game's, and keeps what a copy had) The game's events on map
        `map_number` (its setup's Map) whose scripts start the map's moving parts (`MAP_ANIMATION_OPS`), in order: the
        remaster plays a map's doors by the event playing, so a quest's scene there plays them as the one it names
        (its From) does. Read once, for every map, from the scripts of the events the program has setups for (485
        of them in his program; 28 maps have such events, 41's 160 and 217 among them)."""
        if self._doors is None:
            found = {}
            for number in sorted(self.records):
                values = su.values(self.records[number])
                try:
                    script = es.read_script(self.script(number), self.lengths, "enhanced")
                except (OSError, es.ScriptError):
                    continue
                if any(ins.opcode in MAP_ANIMATION_OPS for ins in script.instructions):
                    found.setdefault(values.get("Map"), []).append(number)
            self._doors = found
        return list(self._doors.get(map_number, []))

    def words(self, number: int, lines) -> dict:
        """`{language: [PzdLine]}`: the lines `lines` of event `number`'s words files, in each language the game
        has them in."""
        wanted = set(lines)
        out = {}
        if not wanted:
            return out
        stems = es.scene_text_files(self.sqlite_path, number) if self.sqlite_path else []
        for language in LANGUAGES:
            found = {}
            for stem in stems:
                for line in self.read_text(stem, language):
                    if line.line_id in wanted and line.line_id not in found:
                        found[line.line_id] = copy.copy(line)
            if found:
                out[language] = [found[n] for n in sorted(found)]
        return out


#: A line that is no line (EB's next line when there is none).
NO_LINE = 0xFFFFFFFF


def lines_shown(script: bytes, lengths: es.Lengths) -> set:
    """The lines of the scene's words a script shows (DisplayMessage, its pages and the rest)."""
    return set(lines_in_order(script, lengths))


def lines_in_order(script: bytes, lengths: es.Lengths) -> list:
    """The lines a script shows, in the order its instructions name them, each once: the order a scene shows them
    in (Zodi's test 35: event 160 shows its lines 300710, 303432 and 303433 one after another in one box, then 300711
    on; by their numbers 303432 and 303433 came last)."""
    out = []
    for ins in es.read_script(script, lengths, "enhanced").instructions:
        if ins.opcode in LINE_OPCODES:
            named = [es.operand(ins, "line")] + ([es.operand(ins, "next_line")] if ins.opcode == 0xEB else [])
            out.extend(n for n in named if n not in (None, NO_LINE) and n not in out)
    return out


def without_story_flags(script: bytes, lengths: es.Lengths) -> bytes:
    """A script with its progress flags' instructions (EA) taken out: a side quest never moves the story, and Mod
    Studio Framework can't keep one as it was (`side_quests.story_problem`)."""
    parsed = es.read_script(script, lengths, "enhanced")
    kept = [i for i in parsed.instructions if i.opcode != sq.PROGRESS_FLAG_OP]
    return parsed.with_instructions(kept).to_bytes() if len(kept) != len(parsed.instructions) else script


# =============================================================================
# Making a quest's things
# =============================================================================

def new_quest(folder: str) -> QuestEdits:
    """A quest of that name and nothing else: Mod Studio Framework reads none until it has an event."""
    return QuestEdits(folder, sq.Quest(folder))


def make_scene(edits: QuestEdits, game: Game, number: int, name: str) -> str:
    """
    A scene of the quest's own, a copy of the game's event `number`: its
    script (its progress flags taken out, `without_story_flags`), its setup
    (each field a quest's event gives but what follows it, which Mod Studio
    Framework gives as it plays: the world map, or the quest's next event
    when it has one; its deploy areas none and Ramza not required,
    `SCENE_CLEARS`, as a scene played on its own deploys no units), and
    the lines of its words it shows, in each language
    the game has them. Played by no step until one plays it. It knows the
    game's event it was copied from (its `From`, 1.11.0): the remaster plays
    a map's doors by the event playing, and the helper has it play them as
    that event. Returns its name.
    """
    name = free_name(name, event_names(edits))
    script = without_story_flags(game.script(number), game.lengths)
    file = file_name(name, ".e", edits.files)
    setup = {k: 0 if k in SCENE_CLEARS else v for k, v in game.setup(number).items()
             if k in sq.SETUP_FIELDS and k != "AfterEvent"}
    edits.files[file] = script
    words = game.words(number, lines_shown(script, game.lengths))
    if words:
        edits.words[name] = words
    edits.quest.events.append(sq.QuestEvent(name, file, "", setup, copied_from=number))
    return name


def won_script(game: Game) -> bytes:
    """The game's victory scene (event 094) with a line first, shown alone on the screen as event 014's first
    words are (test 15's "ambush won"): its first wait, the line, until it is read, half a second, the rest."""
    lengths = game.lengths
    victory = es.read_script(game.script(VICTORY_SCENE), lengths, "enhanced").instructions
    alone = es.read_script(game.script(WORDS_ALONE_SCENE), lengths, "enhanced").instructions
    box = next(i for i in alone if i.opcode == 0x10)
    head = [victory[0], es.with_operands(box, "enhanced", line=WON_LINE),
            es.make(0xE5, lengths, "enhanced", task=es.TASK_MESSAGE), es.make(0xF1, lengths, "enhanced", frames=30)]
    return es.Script("enhanced", head + victory[1:]).to_bytes()


def _line(line_id: int, text: str) -> pzd_data.PzdLine:
    """A line of the quest's own, said by no one (`NO_ONE`)."""
    return pzd_data.PzdLine(line_id, text, SPEAKER_KEY, NO_ONE)


#: (28 October, his test 39) The flags that have the game take a unit from the player's own units as the battle starts
#: (Load Formation) and write it back to them after (Save Formation), as Gariland's battle has Delita: a side quest's
#: battle has no such unit among the player's, so his place was an empty unit at 0 HP (a Squire to see) and the
#: battle that protects him lost at once. The game's own scenes and battles build their story characters from their
#: own fields too (Delita 21 times, battles 390 to 398 among them: `dev/research/sidequests/formation_units.py`).
FORMATION_FLAGS = ("load_formation", "save_formation")


def own_units(block: bytes) -> bytes:
    """A battle's 16 units with Load Formation and Save Formation off for each unit there (`FORMATION_FLAGS`): each
    built from its own fields as the battle starts, none taken from or written back to the player's own units."""
    out = bytes(block)
    for slot, unit in enumerate(entd.battle_units(out)):
        if unit.occupied and any(unit.values[flag] for flag in FORMATION_FLAGS):
            out = entd.battle_with(out, slot, **{flag: False for flag in FORMATION_FLAGS})
    return out


def make_battle(edits: QuestEdits, game: Game, battle: int, name: str) -> str:
    """
    A battle of the quest's own, a copy of the game's ENTD battle `battle`:
    its 16 units (a battle of the quest's by the same name; `own_units`, each
    built from its own fields), the setup of the
    game's event that fights it (`BATTLE_SETUP`; without one, none: its map is
    to be given), and the scene played once it is won (`won_script`, its line
    in every language). Played by no step until one plays it. Each knows the
    game's event it was copied from (`From`): the battle the event that
    fights it, the won scene the victory scene. Returns its name.
    """
    block = game.battle(battle)
    if block is None:
        raise ValueError(f"the game's battle {battle} isn't in its files")
    name = free_name(name, event_names(edits) + [b.name for b in edits.quest.battles])
    units = file_name(name, ".entd", edits.files)
    edits.files[units] = own_units(block)
    edits.quest.battles.append(sq.Battle(name, units))
    record = game.setup(game.battle_event(battle))
    setup = {k: v for k, v in record.items() if k in BATTLE_SETUP}
    won = free_name(f"{name} won", event_names(edits) + [name])
    won_file = file_name(won, ".e", edits.files)
    edits.files[won_file] = won_script(game)
    edits.words[won] = {language: [_line(WON_LINE, WON_WORDS)] for language in LANGUAGES}
    fights = game.battle_event(battle)
    edits.quest.events.append(sq.QuestEvent(name, setup=setup, battle=sq.Fight(name, won, ""), copied_from=(
        fights if isinstance(fights, int) and 1 <= fights <= sq.MOST_GAME_EVENT else 0)))
    edits.quest.events.append(sq.QuestEvent(won, won_file, "", copied_from=VICTORY_SCENE))
    return name


# =============================================================================
# (Zodi, 4 November) A quest's own samples: the starting quest New quest makes, and every new scene and battle
# =============================================================================
#
# His words: "One of the things that helped the most on the Items page was that we stopped letting users copy items
# from the game so this applies to the new quests ... what do you think if automatically created a Rumor leading to a
# dev sample scene on map 116 then after a dev sample battle on map 116 ... at a different place, and then finally
# leading to another scene back at the original place again on map 116. My thinking is this is similar philosophy to
# how in Blender when they give you a new project it gives to a cube." His choices (4 November): New quest asks a
# story point too, the Places tab's random battles and floors start from the same sample battle, and the samples say
# short story lines.

#: The map a new scene or battle starts on: the game's 116, "(No name) - Battle Arena" in the map table's comments,
#: the canvas the remaster's developers show features on. Measured: 11 by 11 tiles, every one flat at height 0, one
#: surface, every unit and the cursor allowed (its grid, `map_map116_7.bin`); a highlight panel on each of its 121
#: tiles in the enhanced look (`map_116_mesh.bin`), so a battle there shows its moves; none of the game's 713 events is
#: set on it.
SAMPLE_MAP = 116
SAMPLE_TILES = 11
#: The camera over the arena's middle (5.5 tiles across and along, a tile 28 of the world's units and the camera's
#: numbers four times theirs: 616), its height, tilt, turn and zoom event 156's over the middle of its own map.
SAMPLE_CAMERA = {"x": 616, "height": -76, "y": 616, "tilt": 302, "yaw": 512, "roll": 0, "zoom": 4096}
#: The music: a scene's "9. Protagonist's Theme" (73), a battle's "36. Run Past Through the Plain" (2), each played
#: by the game's own scenes and battles (the Music table's titles).
SAMPLE_SCENE_MUSIC, SAMPLE_BATTLE_MUSIC = 73, 2
#: How the game's scenes end, measured over its 399 enhanced scripts: the last screen color (0x3E) fades with style
#: 2 from black to white, which darkens the screen, in 60 frames on 94 of them; then the wait for it (task 12).
SCENE_FADE = {"style": 2, "red": 0, "green": 0, "blue": 0, "end_red": 255, "end_green": 255, "end_blue": 255,
              "frames": 60}
#: A speech box over a unit (kind 1, at the top), as the Event Editor's Speak makes one.
SPEECH_BOX = 0x11
#: (Zodi's test 64) A battle's speech box: kind 7, at the top or the bottom by the speaker's facing and the camera's
#: turn as it opens, as most of the game's battles' boxes are (event 011's, 012's; `event_scripts.facing_window`).
BATTLE_SPEECH_BOX = 0x70
#: (Zodi's test 64: "Normally in non battle events the units do not march in place. They stand still") The game makes
#: every unit in its march (fft_decomp's `animation_status_set` as each is made), and its scenes stand theirs with
#: UnitAnim (0x11) of its standing animation (`event_scripts.STAND`, 2) before their first line: 64 of its 88 scenes,
#: mostly every unit at once (unit 0, 80 of its scripts' first instructions); its battles' won scenes the player's
#: units alive (the group 257, the blue team without the statuses a script passes over: 57 of them, 012 and 032
#: among them), Ramza first stood by InflictStatus (0x92) of status 0 for 12 frames (`STAND_STATUS`), its wait (task
#: 67) after.
EVERY_UNIT, OWN_UNITS = 0, 257
STAND_STATUS, STAND_FRAMES = 0, 12
#: (Zodi's test 64: "Ramza should say something after the battles begins and he should be standing still as he says
#: his lines while the other units march ... after defeating all the enemies while all the units now stand still")
#: A battle's openings stand their speakers before the map comes in (UnitAnim 2: event 010's enemy, 128) and set them
#: marching again with March (0x80) once they have spoken, then show the objective box (`objective_box`).
MARCH_FRAMES = 0
#: A generic unit as the game's battles build theirs (battle 388's enemies and its random battles' 533 at level
#: 0xFE): sprite set 128 a man, 129 a woman; no name of its own (0xFF); its level the party's highest less up to an
#: eighth of it (0xFE: fft_decomp's `unit_entd.h`, read for facts); its month, day, Bravery, Faith, abilities and
#: equipment at random (0xFE, as `EMPTY_UNIT` has them); its career job the one of its main job, at job level 2 (the
#: game's Knight's and Squire's); always present; an enemy in palette 3 (758 of the game's generic enemies), a friend
#: in 0 (368 of its generic friends).
GENERIC_MAN, GENERIC_WOMAN, NO_NAME = 128, 129, 0xFF
FIRST_GENERIC_JOB = 74                     # Squire; 75 Chemist, 76 Knight, 77 Archer ...
SQUIRE, KNIGHT, ARCHER = 74, 76, 77
ENEMY_PALETTE, FRIEND_PALETTE = 3, 0
SAMPLE_JOB_LEVEL = 2
#: The units' ids the scripts name them by, past the story's characters (the game's generic units' 0x80 up).
FIRST_GENERIC_ID = 0x80
#: Facings (`entd.FACING_NAMES`): south looks along the map's y downward, north up, west along x downward, east up
#: (fft_decomp's `unit_facing_turn_to_target`: east the way of x, north of y).
SOUTH, WEST, NORTH, EAST = 0, 1, 2, 3
#: The sample scene's two units, facing each other across the arena's middle: a knight and a squire.
SAMPLE_SCENE_UNITS = ((KNIGHT, False, 4, 5, EAST), (SQUIRE, True, 6, 5, WEST))
#: The sample battle's three enemies near the arena's south edge (y 1 and 2), facing north toward the player's units
#: at its north edge, as the game's Gariland battle (388) faces its enemies and Delita.
SAMPLE_ENEMIES = ((SQUIRE, False, 4, 2, NORTH), (KNIGHT, False, 5, 1, NORTH), (ARCHER, True, 6, 2, NORTH))
#: Where the player's units start in the sample battle: a deploy area of its own, five squares along the north edge
#: (y 10), five units, facing south toward the enemies; the game's squad with those squares (148 in his program, made
#: for map 074) its setup's, where the battle starts when Mod Studio Framework can't give it its own (`sample_squad`).
SAMPLE_SQUARES = [(3, 10), (4, 10), (5, 10), (6, 10), (7, 10)]
SAMPLE_FACING = SOUTH
#: (His choice "Short story lines") What the samples say until they are changed. `{place}` the step's place, `{other}`
#: the battle's. (Zodi's test 64: "Help wanted at Magick City of Gariland" scrolled in the tavern's list, where the
#: game's longest, 32 letters, fits) The title names no place, so it fits whatever the place: 19 letters, in the
#: game's rumors' title case.
SAMPLE_RUMOR_TITLE = "Bandits on the Road"
SAMPLE_RUMOR_TEXT = ("A stranger at {place} is asking travelers for help. Bandits have taken the road to {other}, and "
                     "no one has dared to face them.")
SAMPLE_OPENING_LINES = ("So the rumor brought you here.", "It did. What's wrong?",
                        "Bandits hold the road at {other}. Meet me there, and we'll drive them off together.")
SAMPLE_ENDING_LINES = ("The road is safe again, thanks to you.", "Then our work here is done.",
                       "You'll always be welcome at {place}.")
#: A new scene's lines, added on its own (Add a scene, Add a step).
SAMPLE_SCENE_LINES = ("Is this the place?", "It is. Let's wait here.")
#: The starting quest's names: its rumor, its two scenes and its battle (each scene's units named for it).
OPENING, BATTLE_NAME, ENDING = "Opening", "Battle", "Ending"
SCENE_NAME = "Scene"
UNITS_OF = "{scene} units"


def _generic_unit(job: int, woman: bool, x: int, y: int, facing: int, team: int, unit_id: int) -> bytes:
    """A generic unit's 40 bytes (`GENERIC_MAN` and the rest): `job` its main job (one of the generic jobs, its career
    job with it), a man or a woman, on the tile `x`, `y` facing `facing`, of `team`, the scripts naming it `unit_id`."""
    return entd.unit_with(EMPTY_UNIT, sprite_set=GENERIC_WOMAN if woman else GENERIC_MAN, male=not woman,
                          female=woman, unit_name=NO_NAME, level=entd.RANDOM_BYTE,
                          prereq_job=job - FIRST_GENERIC_JOB, prereq_job_level=SAMPLE_JOB_LEVEL, main_job=job,
                          secondary_command=entd.RANDOM_BYTE, palette=ENEMY_PALETTE if team == 1 else FRIEND_PALETTE,
                          always_present=True, team=team, x=x, y=y, facing=facing, unit_id=unit_id)


def sample_units(units, team: int) -> bytes:
    """A battle's 16 units (640 bytes) holding `units` (`(job, a woman, x, y, facing)`) in its first places, of `team`,
    numbered from `FIRST_GENERIC_ID`; the rest empty."""
    block = b"".join(_generic_unit(job, woman, x, y, facing, team, FIRST_GENERIC_ID + n)
                     for n, (job, woman, x, y, facing) in enumerate(units))
    return block + bytes(entd.EVENT_BYTES - len(block))


def sample_scene_script(lengths: es.Lengths, said: list) -> bytes:
    """A scene's script on the arena (`SAMPLE_CAMERA`): the camera over its middle at once, (Zodi's test 64) every
    unit standing (UnitAnim of `es.STAND`, as the game's scenes stand theirs), the map coming in, a wait, each of
    `said` (`(the unit saying it, its line)`) in a speech box over its unit until it is read, a wait, the screen
    darkening as the game's scenes end (`SCENE_FADE`), the end."""
    def make(opcode, **values):
        return es.make(opcode, lengths, "enhanced", **values)
    out = [make(0x19, frames=1, **SAMPLE_CAMERA), make(0xE5, task=es.TASK_CAMERA),
           make(0x11, unit=EVERY_UNIT, animation=es.STAND, keep_facing=0), make(0x4D, frames=30),
           make(0xF1, frames=50)]
    for unit, line in said:
        out += [make(0x10, thread=0x10, box=SPEECH_BOX, line=line, unit=unit), make(0xE5, task=es.TASK_MESSAGE)]
    out += [make(0xF1, frames=30), make(0x3E, **SCENE_FADE), make(0xE5, task=es.TASK_SCREEN), make(es.END)]
    return es.Script("enhanced", out).to_bytes()


def make_sample_scene(edits: QuestEdits, game: Game, name: str = SCENE_NAME, lines=SAMPLE_SCENE_LINES) -> str:
    """
    (Zodi, 4 November) A scene of the quest's own on the arena (`SAMPLE_MAP`),
    in place of a copy of the game's: two units of its own (a battle of the
    quest's named for it, `UNITS_OF`, its setup's EnemyBattle and SceneUnits),
    a knight and a squire facing each other across the middle
    (`SAMPLE_SCENE_UNITS`), saying `lines` in turn (the first the knight's),
    each in every language; its music `SAMPLE_SCENE_MUSIC`. Played by no step
    until one plays it. Returns its name.
    """
    name = free_name(name, event_names(edits) + [b.name for b in edits.quest.battles])
    units = free_name(UNITS_OF.format(scene=name), event_names(edits) + [b.name for b in edits.quest.battles] + [name])
    units_file = file_name(units, ".entd", edits.files)
    edits.files[units_file] = sample_units(SAMPLE_SCENE_UNITS, 0)
    edits.quest.battles.append(sq.Battle(units, units_file))
    said = [(FIRST_GENERIC_ID + n % len(SAMPLE_SCENE_UNITS), WON_LINE + n) for n in range(len(lines))]
    file = file_name(name, ".e", edits.files)
    edits.files[file] = sample_scene_script(game.lengths, said)
    edits.words[name] = {language: [_line(WON_LINE + n, text) for n, text in enumerate(lines)]
                         for language in LANGUAGES}
    setup = {"Map": SAMPLE_MAP, "Music1": SAMPLE_SCENE_MUSIC, "EnemyBattle": units, "SceneUnits": units}
    edits.quest.events.append(sq.QuestEvent(name, file, "", setup))
    return name


#: A battle's new scene as it starts: its first unit speaking, then Ramza answering (Zodi's test 64).
SAMPLE_START_LINES = ("So you came after all.", "This ends here!")
START_OF = "{battle} start"
#: (Zodi's test 65: "there should be three events. One at start, one mid battle mostly for dialogue, and then the
#: ending event"; his choices "Either, picked on the card" and both of the sample's) A battle's scenes during it: their
#: names, and what the sample battle's two say, the first on Ramza's first turn, the second on its first enemy's (the
#: Squire's), each speaker stopping as he speaks.
DURING_OF = "{battle} during"
SAMPLE_DURING_LINES = (("Turn back while you still can!", "Not until this road is safe."),
                       ("Get them! Don't let them through!", "Hold your ground, everyone!"))
#: (His test 65's balloons) The game moves the camera onto a battle's speaker before his line (Focus, 0x1F: 490 of its
#: 720 lines in a speaker's box placed by his facing, `dev/research/sidequests/battle_scenes.py`), which patches the
#: next Camera's place and yaw (fft_decomp's `script_focus`): its box then over him. Its frames, as the game's 32.
FOCUS, FOCUS_FRAMES = 0x1F, 32
#: (Zodi's test 64) What Ramza says once the sample battle is won.
SAMPLE_WON_WORDS = "That's the last of them."


def _focused(lengths: es.Lengths, unit: int) -> list:
    """(His test 65's balloons) The camera onto `unit` before he speaks, as the game's battle scenes move it: Focus on
    him (his place and the nearest open diagonal its yaw), the Camera it patches (the arena's tilt and zoom, 32 frames),
    the wait for it."""
    def make(opcode, **values):
        return es.make(opcode, lengths, "enhanced", **values)
    return [make(FOCUS, unit=unit, unit2=unit, keep_yaw=0), make(0x19, **dict(SAMPLE_CAMERA, frames=FOCUS_FRAMES)),
            make(0xE5, task=es.TASK_CAMERA)]


def battle_opening_script(lengths: es.Lengths, said: list, box: list) -> bytes:
    """
    (Zodi's test 65: "Events that start in a battle. Everyone is should be
    standing still not marching in place as the event plays out") A battle's
    opening on the arena (`SAMPLE_CAMERA`), as the game's openings that stand
    every unit play (53 of its 154, 034 and 040 among them): the camera over
    its middle at once, every unit standing (UnitAnim of `es.STAND` for
    `EVERY_UNIT`) before the map comes in, a wait, each line of `said` (`(the
    unit saying it, its line)`) in a battle's speech box over its unit, the
    camera onto him first (`_focused`), until it is read, a wait, then `box`
    (the objective box, `objective_box`), every unit marching again (March of
    `EVERY_UNIT`), the end.
    """
    def make(opcode, **values):
        return es.make(opcode, lengths, "enhanced", **values)
    out = [make(0x19, frames=1, **SAMPLE_CAMERA), make(0xE5, task=es.TASK_CAMERA),
           make(0x11, unit=EVERY_UNIT, animation=es.STAND, keep_facing=0), make(0x4D, frames=30), make(0xF1, frames=50)]
    for unit, line in said:
        out += _focused(lengths, unit) + [make(0x10, thread=0x10, box=BATTLE_SPEECH_BOX, line=line, unit=unit),
                                          make(0xE5, task=es.TASK_MESSAGE)]
    out += [make(0xF1, frames=16)] + list(box) + [make(0x80, unit=EVERY_UNIT, frames=MARCH_FRAMES), make(es.END)]
    return es.Script("enhanced", out).to_bytes()


def battle_during_script(lengths: es.Lengths, said: list, guard: int) -> bytes:
    """
    (Zodi's test 65: "It is mid battle events that the unit who begins
    speaking stops marching and when another unit starts speaking then that
    unit stops marching as well and so on until it resumes to the battle and
    everyone is now marching") A scene during a battle, as Gariland's plays on
    Ramza's turn (event 011): each line of `said` (`(the unit saying it, its
    line)`) with the camera onto its unit first (`_focused`), its unit stood
    (InflictStatus `STAND_STATUS` for `STAND_FRAMES`, as the game's battle
    scenes stand a speaker), in a battle's speech box until it is read; then
    each speaker marching again (March), `guard` set (cleared, 1 added: the
    scenario's own variable its rules test, so it plays once a battle), the
    end.
    """
    def make(opcode, **values):
        return es.make(opcode, lengths, "enhanced", **values)
    out = []
    for unit, line in said:
        out += _focused(lengths, unit) + [make(0x92, unit=unit, status=STAND_STATUS, frames=STAND_FRAMES),
                                          make(0x10, thread=0x10, box=BATTLE_SPEECH_BOX, line=line, unit=unit),
                                          make(0xE5, task=es.TASK_MESSAGE)]
    speakers = list(dict.fromkeys(unit for unit, _ in said))
    out += [make(0xF1, frames=16)] + [make(0x80, unit=unit, frames=MARCH_FRAMES) for unit in speakers]
    out += [make(CLEAR_OP, variable=guard), make(ADD_OP, variable=guard, value=1), make(es.END)]
    return es.Script("enhanced", out).to_bytes()


def make_sample_start(edits: QuestEdits, game: Game, battle: str) -> str:
    """(Zodi, 4 November) A battle's new scene as it starts, in place of a copy of the game's: (his test 64) the
    battle's first unit speaks, then Ramza answers (`SAMPLE_START_LINES`), each standing while the rest march, all
    marching again after, then the objective box of the game's openings (`battle_opening_script`), with no setup or
    units of its own, as a battle's start scene plays with the battle's (`set_start_scene`). Ramza is named as Mod
    Studio Framework gives him (its `RamzaInScript`: the party's Ramza as it is read, `side_quests.RAMZAS`). Not yet
    its battle's: `set_start_scene` makes it so. Returns its name."""
    ev = edits.quest.event_named(battle)
    if ev is None or ev.battle is None:
        raise ValueError(f"{battle} isn't a battle of the quest")
    block = battle_units_block(edits, battle)
    ids = [u.values["unit_id"] for u in entd.battle_units(block) if u.occupied][:1] if block else []
    first = ids[0] if ids else FIRST_GENERIC_ID
    name = free_name(START_OF.format(battle=battle), event_names(edits) + [b.name for b in edits.quest.battles])
    said = [(first, WON_LINE), (sq.RAMZA, WON_LINE + 1)]
    file = file_name(name, ".e", edits.files)
    script = battle_opening_script(game.lengths, said, objective_box(game))
    edits.files[file] = script
    edits.words[name] = {language: [_line(WON_LINE + n, text) for n, text in enumerate(SAMPLE_START_LINES)]
                         for language in LANGUAGES}
    edits.quest.events.append(sq.QuestEvent(name, file, "", {},
                                            ramza_in_script=sq.ramza_places(script, game.lengths)))
    return name


def sample_won_script(game: Game) -> bytes:
    """
    (Zodi's test 64) A battle's scene once it is won, as the game's won
    scenes play (012, 032): Ramza stood (InflictStatus `STAND_STATUS` for
    `STAND_FRAMES`, its wait), the player's units alive standing (UnitAnim
    of `es.STAND` for `OWN_UNITS`), the camera over the arena's middle,
    Ramza saying the won line (`WON_LINE`) in a battle's speech box, then
    the game's victory scene (event 094) from its music on.
    """
    lengths = game.lengths

    def make(opcode, **values):
        return es.make(opcode, lengths, "enhanced", **values)
    victory = es.read_script(game.script(VICTORY_SCENE), lengths, "enhanced").instructions
    head = [victory[0], make(0x92, unit=sq.RAMZA, status=STAND_STATUS, frames=STAND_FRAMES),
            make(0xE5, task=es.TASK_STATUS), make(0xF1, frames=20),
            make(0x11, unit=OWN_UNITS, animation=es.STAND, keep_facing=0), make(0xF1, frames=20)]
    # (His test 65's balloons) The camera onto Ramza before he speaks, as Gariland's won scene (012) moves it.
    head += _focused(lengths, sq.RAMZA) + [
        make(0xF1, frames=10), make(0x10, thread=0x10, box=BATTLE_SPEECH_BOX, line=WON_LINE, unit=sq.RAMZA),
        make(0xE5, task=es.TASK_MESSAGE)]
    return es.Script("enhanced", head + list(victory[1:])).to_bytes()


def sample_squad(squads: bytes) -> int:
    """The game's squad whose tiles are the sample battle's squares (`SAMPLE_SQUARES`, on the lower level), its
    lowest number, or 0 when none is (the program's `squads`). A squad's tiles are all on its one level
    (`event_scripts.squad_tiles`), so one on the upper level has none of the lower's."""
    wanted = sorted(SAMPLE_SQUARES)
    for number in range(su.SQUAD_MOST):
        squad = su.squad(squads, number) if squads else None
        tiles = es.squad_tiles(squad) if squad is not None and squad.tiles else []
        if tiles and sorted((x, y) for x, y, level, _facing in tiles if not level) == wanted:
            return number
    return 0


def sample_deploy() -> sq.DeployArea:
    """The sample battle's own deploy area (`SAMPLE_SQUARES`, five units facing `SAMPLE_FACING`)."""
    return sq.DeployArea(list(SAMPLE_SQUARES), min(sq.MOST_DEPLOY_UNITS, len(SAMPLE_SQUARES)), SAMPLE_FACING, False)


def make_sample_battle(edits: QuestEdits, game: Game, name: str = BATTLE_NAME, squads: bytes = b"") -> str:
    """
    (Zodi, 4 November) A battle of the quest's own on the arena
    (`SAMPLE_MAP`), in place of a copy of the game's: three enemies of its
    own near the south edge (`SAMPLE_ENEMIES`, at the party's level), the
    player's units on a deploy area of its own along the north edge
    (`sample_deploy`; its setup's the game's squad with the same squares,
    `sample_squad` from the program's `squads`), Ramza placed, its music
    `SAMPLE_BATTLE_MUSIC`, won once every enemy is beaten; (Zodi's test 64)
    its scene as it starts its first enemy's line and Ramza's
    (`make_sample_start`, each standing while the rest march), and the scene
    once it is won Ramza's line with the player's units standing
    (`sample_won_script`), Ramza named as Mod Studio Framework gives him
    (`RamzaInScript`); (his test 65) every unit standing as it starts, and two
    scenes during it, on Ramza's first turn and on its first enemy's
    (`make_sample_during`). Played by no step until one plays it. Returns its
    name.
    """
    name = free_name(name, event_names(edits) + [b.name for b in edits.quest.battles])
    units = file_name(name, ".entd", edits.files)
    edits.files[units] = sample_units(SAMPLE_ENEMIES, 1)
    edits.quest.battles.append(sq.Battle(name, units))
    setup = {"Map": SAMPLE_MAP, "Music1": SAMPLE_BATTLE_MUSIC, "DeployArea1": sample_squad(squads),
             "RamzaRequired": 1}
    won = free_name(f"{name} won", event_names(edits) + [name])
    won_file = file_name(won, ".e", edits.files)
    won_bytes = sample_won_script(game)
    edits.files[won_file] = won_bytes
    edits.words[won] = {language: [_line(WON_LINE, SAMPLE_WON_WORDS)] for language in LANGUAGES}
    edits.quest.events.append(sq.QuestEvent(name, setup=setup, battle=sq.Fight(name, won, "", deploy=[sample_deploy()])))
    edits.quest.events.append(sq.QuestEvent(won, won_file, "", copied_from=VICTORY_SCENE,
                                            ramza_in_script=sq.ramza_places(won_bytes, game.lengths)))
    set_start_scene(edits, name, make_sample_start(edits, game, name), game.lengths)
    # (His test 65, his choice "both") A scene on Ramza's first turn, then one on its first enemy's (the Squire's).
    make_sample_during(edits, game, name, 0, SAMPLE_DURING_LINES[0])
    make_sample_during(edits, game, name, 1, SAMPLE_DURING_LINES[1])
    return name


def make_sample_during(edits: QuestEdits, game: Game, battle: str, unit: int = 0, lines=SAMPLE_DURING_LINES[0],
                       when: str = sq.TURN, share: int = 0) -> str:
    """
    (Zodi's test 65, his choice "Either, picked on the card") A new scene
    during battle `battle` (`battle_during_script`): its first enemy says the
    first of `lines`, Ramza the second, each stopping as he speaks; it plays
    once a battle, as its unit `unit` (0 Ramza, else one of the battle's own,
    1 to 16) takes its turn (`sq.TURN`), or as its HP falls to `share` percent
    of its most (`sq.HP`, 0 beaten), its guard the next of `sq.GUARDS`. No
    setup or units of its own: it plays with the battle's. Returns its name.
    """
    fight = _fight(edits, battle)
    if len(fight.during) >= sq.MOST_DURING:
        raise ValueError(f"a battle has up to {sq.MOST_DURING} scenes during it")
    block = battle_units_block(edits, battle)
    ids = [u.values["unit_id"] for u in entd.battle_units(block) if u.occupied][:1] if block else []
    first = ids[0] if ids else FIRST_GENERIC_ID
    name = free_name(DURING_OF.format(battle=battle), event_names(edits) + [b.name for b in edits.quest.battles])
    file = file_name(name, ".e", edits.files)
    script = battle_during_script(game.lengths, [(first, WON_LINE), (sq.RAMZA, WON_LINE + 1)],
                                  sq.GUARDS[len(fight.during)])
    edits.files[file] = script
    edits.words[name] = {language: [_line(WON_LINE + n, text) for n, text in enumerate(lines)]
                         for language in LANGUAGES}
    edits.quest.events.append(sq.QuestEvent(name, file, "", {},
                                            ramza_in_script=sq.ramza_places(script, game.lengths)))
    fight.during.append(sq.During(name, when, unit, share if when == sq.HP else 0))
    return name


def set_during(edits: QuestEdits, scene: str, when: Optional[str] = None, unit: Optional[int] = None,
               share: Optional[int] = None) -> None:
    """When a scene during a battle plays: as its unit's turn comes or as its HP falls to a share; its unit (0 Ramza,
    else one of the battle's own, 1 to 16); its share (`sq.HP` only, 0 to 99)."""
    fight = edits.quest.fight_of(scene)
    d = next((x for x in fight.battle.during if x.event == scene), None) if fight is not None else None
    if d is None:
        raise ValueError(f"{scene} plays during no battle")
    if when is not None:
        if when not in (sq.TURN, sq.HP):
            raise ValueError(f"a scene during a battle plays on a unit's turn ({sq.TURN}) or HP ({sq.HP})")
        d.when = when
    if unit is not None:
        d.unit = unit
    if share is not None:
        d.share = share
    if d.when != sq.HP:
        d.share = 0


def _reguard(edits: QuestEdits, fight: sq.Fight, lengths: es.Lengths) -> None:
    """Each scene during a battle setting the guard of its place now (`sq.GUARDS`), as its rules will test it."""
    for k, d in enumerate(fight.during):
        ev = edits.quest.event_named(d.event)
        if ev is None or ev.battle is not None or ev.script not in edits.files:
            continue

        def guarded(instructions: list, guard=sq.GUARDS[k]) -> list:
            return [es.with_operands(i, "enhanced", variable=guard)
                    if i.opcode in (CLEAR_OP, ADD_OP) and es.operand(i, "variable") in sq.GUARDS else i
                    for i in instructions]
        _change_script(edits, ev, lengths, guarded)


def _place_words(place) -> str:
    """A place in words: one of the mod's own by its name, one of the game's by the game's."""
    from mod_studio import map_roads as mr
    return place if isinstance(place, str) else mr.GAME_PLACES.get(place, (f"place {place}",))[0]


#: The game's battle grounds, where it fights its random battles (24 Mandalia Plain to 42 Mount Germinas); 44 to 46
#: are places of its story's own, shown only while it is there.
GAME_BATTLE_GROUNDS = range(24, 43)
#: When the world map shows each of the game's places: the story's progress (variable 110) its chain draws it at
#: (instruction 34), each such chain testing that the place isn't shown yet (variable 512 + the place is 0) and that
#: the progress is that number, once and for good (the bit saved). Measured from the game's EnhancedWorldEvent rows
#: (the 1.5.2 database's, the same as WotL Restoration's copy of the table's file, read by
#: `dev/research/sidequests/place_showing.py`); the earlier of two chains where a place has two (18, 21). Not here:
#: the places shown otherwise (6 Gariland from the start; 22 and 23 by the rumors' variables 165 and 170; 45 and 46
#: by the story's own variables) and the two no chain draws (27 Mount Bervenia, 36 Dorvauldar Marsh).
SHOWN_FROM = {0: 31, 1: 37, 2: 2, 3: 18, 4: 47, 5: 41, 7: 37, 8: 31, 9: 4, 10: 18, 11: 22, 12: 25, 13: 41, 14: 47,
              15: 10, 16: 52, 17: 8, 18: 34, 19: 28, 21: 16, 24: 2, 25: 10, 26: 4, 28: 6, 29: 10, 30: 22, 31: 37,
              32: 16, 33: 37, 34: 45, 35: 16, 37: 18, 38: 41, 39: 25, 40: 41, 41: 47, 42: 47}


def nearest_place(place, places: dict, story: Optional[int] = None):
    """(Zodi, 4 November: the battle "at a different place") The battle ground nearest `place` on the world map of
    `places` (`{place: (x, y, a town)}`, the game's by number and the mod's by name), among those shown by the time
    the quest's first step can play there: the later of `story` (the story's progress it waits for; None, any) and
    `place`'s own showing (`SHOWN_FROM`; the mod's places shown from the start). A battle ground is one of the game's
    the world map shows by the story (`GAME_BATTLE_GROUNDS` in `SHOWN_FROM`) or one of the mod's own; when none is
    shown by then, the nearest of those shown soonest after; failing a battle ground, the nearest other place; None
    when there is none."""
    if place not in places:
        return None
    x0, y0, _town = places[place]
    others = [(p, x, y, town) for p, (x, y, town) in places.items() if p != place]
    if not others:
        return None

    def shown(p) -> int:
        return 0 if isinstance(p, str) else SHOWN_FROM.get(p, 0)

    def far(o) -> tuple:
        return (o[1] - x0) ** 2 + (o[2] - y0) ** 2, str(o[0])
    grounds = [o for o in others if not o[3] and (isinstance(o[0], str) or (o[0] in GAME_BATTLE_GROUNDS
                                                                          and o[0] in SHOWN_FROM))]
    if not grounds:
        return min(others, key=far)[0]
    by = max(story or 0, shown(place))
    ready = [o for o in grounds if shown(o[0]) <= by]
    if not ready:
        soonest = min(shown(o[0]) for o in grounds)
        ready = [o for o in grounds if shown(o[0]) == soonest]
    return min(ready, key=far)[0]


def starting_quest(folder: str, game: Game, place, places: dict, marker: str = "", story: Optional[int] = None,
                   squads: bytes = b"") -> QuestEdits:
    """
    (Zodi, 4 November: "So when the user clicks on New Quest it will bring up
    a menu that only has three things on it Name, Place, and Marker"; his
    choice, a story point too) A new quest, its own Blender cube: a rumor
    told in every tavern (once the story is past `story`, when given), then
    three steps on the arena (`SAMPLE_MAP`): a scene at `place` once the rumor
    is read (`make_sample_scene`, its knight asking for help), a battle at
    the battle ground nearest it the world map shows by then (`nearest_place`
    of `places`, `make_sample_battle`),
    and a scene back at `place` (its knight thanking the squire); its marker
    `marker` ("" for none). Every word is a sample's, every part changeable.
    """
    edits = new_quest(folder)
    quest = edits.quest
    quest.marker = marker or ""
    other = nearest_place(place, places, story)
    if other is None:
        other = place
    words = {"place": _place_words(place), "other": _place_words(other)}
    rumor = add_rumor(edits)
    set_rumor_words(edits, rumor, SAMPLE_RUMOR_TITLE.format(**words), SAMPLE_RUMOR_TEXT.format(**words))
    told = rumor_named(quest, rumor)
    if story is not None:
        set_story_past(told, story)
    opening = make_sample_scene(edits, game, OPENING, [line.format(**words) for line in SAMPLE_OPENING_LINES])
    first = add_step(edits, place, opening, game.lengths)
    set_waits_for_rumor(quest.starts[first], told, True)
    battle = make_sample_battle(edits, game, BATTLE_NAME, squads)
    add_step(edits, other, battle, game.lengths)
    ending = make_sample_scene(edits, game, ENDING, [line.format(**words) for line in SAMPLE_ENDING_LINES])
    add_step(edits, place, ending, game.lengths)
    # (1.31.0, his choices "Its last step only" and "A line in the scene") Its Ending gives gil, and says so.
    set_reward(edits, game.lengths, gil=SAMPLE_REWARD_GIL)
    return edits


# (Zodi, 5 November: "I do not think you updated the sample quest that generates after creating a new quest. That was
# the whole point of test 70 to generate a quest sample so new users could understand how to use it") New quest's
# sample as test 70's quest was (`dev/research/sidequests/make_test70.py`, which passed in his game): its reward 1,500
# gil, three Potions and a ring, the knight asked to join, said in the narration; its units' own names; the knight's
# first line with no name over it (his name not learned yet); Ramza's lines named by the Speaker table's Ramza. Test
# 70's ring, the Wayfarer's Ring, was that test's own item, which a new mod has none of: (his choice "One of the game's
# rings") the Protect Ring, the first of the game's rings its shops sell (from Chapter 2's meeting with Delacroix; the
# only ring sold from Chapter 1's start is the Ring of Aptitude, a bonus item). Never an item to use of a mod's own.
SAMPLE_GIL = 1500
POTION, PROTECT_RING = 240, 220
SAMPLE_ITEMS = ((POTION, 3), (PROTECT_RING, 1))
#: The Ending's knight (its first unit) asked to join.
SAMPLE_JOINS = 0
#: Each scene's or battle's units' own names, by place: test 69's and 70's.
SAMPLE_OWN_NAMES = {OPENING: {0: "Ser Corvin", 1: "Mira"}, BATTLE_NAME: {0: "Rook", 1: "Garrick", 2: "Vessa"},
                    ENDING: {0: "Ser Corvin", 1: "Mira"}}
#: The Speaker table's Ramza: its rows 1010101 to 1010103, the first the one Name over the box gives "Ramza".
RAMZA_SPEAKER = 1010101


def sample_quest(folder: str, game: Game, place, places: dict, marker: str = "", story: Optional[int] = None,
                 squads: bytes = b"", item_words: Optional[dict] = None) -> QuestEdits:
    """(Zodi, 5 November) New quest's sample: `starting_quest`'s quest made as test 70's was. Its reward
    (`SAMPLE_GIL`, `SAMPLE_ITEMS`, `SAMPLE_JOINS`), said in the narration by its items' words (`item_words`, as
    `reward_words` takes them); its units' own names (`SAMPLE_OWN_NAMES`, each marking the lines its unit says); the
    knight's first line at the Opening said by no one, its name not learned yet; every line Ramza says named by the
    Speaker table's Ramza (`RAMZA_SPEAKER`)."""
    edits = starting_quest(folder, game, place, places, marker, story, squads)
    lengths = game.lengths
    quest = edits.quest
    set_reward(edits, lengths, SAMPLE_GIL, list(SAMPLE_ITEMS), SAMPLE_JOINS, True, item_words)
    for event, names in SAMPLE_OWN_NAMES.items():
        ev = quest.event_named(event)
        # A battle's units by its Fight's battle; a scene's by the battle it shows.
        battle = ev.battle.units if ev is not None and ev.battle is not None else scene_battle(quest, event)
        for slot, name in names.items():
            set_own_name(edits, battle, slot, name, lengths)
    opening = quest.event_named(OPENING)
    first = lines_in_order(edits.files[opening.script], lengths)[0]
    set_scene_speaker(edits, OPENING, first, NO_ONE)
    for ev in quest.events:
        if ev.script and ev.script in edits.files:
            for ins in es.read_script(edits.files[ev.script], lengths, "enhanced").instructions:
                if ins.opcode == 0x10 and es.operand(ins, "unit") in es.RAMZA_UNITS:
                    set_scene_speaker(edits, ev.name, es.operand(ins, "line"), RAMZA_SPEAKER)
    return edits


# =============================================================================
# A script's flags
# =============================================================================

def _offsets(instructions: list) -> list:
    out, at = [], 0
    for ins in instructions:
        out.append(at)
        at += ins.size
    return out


def _marks(ev: sq.QuestEvent, instructions: list) -> list:
    """Each of an event's FlagsInScript as (instruction index, the operand's place in it, flag)."""
    starts = _offsets(instructions)
    out = []
    for at, flag in ev.flags_in_script:
        index = next((n for n, s in enumerate(starts) if s < at < s + instructions[n].size), None)
        if index is not None:
            out.append((index, at - starts[index], flag))
    return out


def _ramza_marks(ev: sq.QuestEvent, instructions: list) -> list:
    """(1.30.0) Each of an event's RamzaInScript as (the instruction holding it, the operand's place in it): followed
    by the instruction itself wherever a change moves it (`_rewrite`)."""
    starts = _offsets(instructions)
    out = []
    for at in ev.ramza_in_script:
        index = next((n for n, s in enumerate(starts) if s < at < s + instructions[n].size), None)
        if index is not None:
            out.append((instructions[index], at - starts[index]))
    return out


def _rewrite(edits: QuestEdits, ev: sq.QuestEvent, instructions: list, marks: list, ramza: list = ()) -> None:
    """An event's script as `instructions`, its FlagsInScript where `marks` (index, place, flag) put them; (1.12.0)
    its ObjectiveInScript, if it has one, at each objective it shows now; (1.30.0) its RamzaInScript where the
    instructions of `ramza` (`_ramza_marks`) stand now (one taken out goes)."""
    starts = _offsets(instructions)
    edits.files[ev.script] = es.Script("enhanced", instructions).to_bytes()
    ev.flags_in_script = [(starts[index] + place, flag) for index, place, flag in marks]
    if ev.objective_in_script:
        ev.objective_in_script = [starts[n] + 1 for n, ins in enumerate(instructions)
                                  if ins.opcode == DISPLAY_CONDITIONS
                                  and (es.operand(ins, "display") or 0) >= FIRST_OBJECTIVE]
    if ev.ramza_in_script:
        ev.ramza_in_script = [starts[n] + place for held, place in ramza
                              for n, ins in enumerate(instructions) if ins is held]


def set_flag_at_end(edits: QuestEdits, event: str, flag: str, lengths: es.Lengths) -> None:
    """Event `event`'s script sets `flag` as it ends: clear it, add 1, then the end, as 117 of the game's scenes set
    a variable last; its FlagsInScript says where the flag's number goes, twice."""
    ev = edits.quest.event_named(event)
    if ev is None or ev.battle is not None:
        raise ValueError(f"{event} isn't a scene of the quest")
    instructions = list(es.read_script(edits.files[ev.script], lengths, "enhanced").instructions)
    marks = _marks(ev, instructions)
    ramza = _ramza_marks(ev, instructions)
    end = len(instructions) - 1
    clear = es.make(CLEAR_OP, lengths, "enhanced", variable=0)
    add = es.make(ADD_OP, lengths, "enhanced", variable=0, value=1)
    instructions[end:end] = [clear, add]
    marks = [(i + 2 if i >= end else i, place, f) for i, place, f in marks] + [(end, 1, flag), (end + 1, 1, flag)]
    _rewrite(edits, ev, instructions, marks, ramza)


def unset_flag(edits: QuestEdits, event: str, flag: str, lengths: es.Lengths) -> None:
    """Event `event`'s script no longer sets `flag`: the instructions whose variable is it are taken out."""
    ev = edits.quest.event_named(event)
    if ev is None or ev.battle is not None:
        return
    instructions = list(es.read_script(edits.files[ev.script], lengths, "enhanced").instructions)
    marks = _marks(ev, instructions)
    ramza = _ramza_marks(ev, instructions)
    gone = {index for index, place, f in marks if f == flag and place == 1}
    kept = [ins for n, ins in enumerate(instructions) if n not in gone]
    moved = []
    for index, place, f in marks:
        if index in gone:
            continue
        moved.append((index - sum(1 for g in gone if g < index), place, f))
    _rewrite(edits, ev, kept, moved, ramza)


def last_scene(quest: sq.Quest, step: Step) -> Optional[str]:
    """The event a step ends with, a scene (a battle ends with its won scene; never its lost one, after which the game
    starts over), or None."""
    for name in reversed(step.events):
        if role(quest, name) not in ("battle", "lost"):
            return name
    return None


def _move_done_flag(edits: QuestEdits, before: Optional[Step], lengths: es.Lengths) -> None:
    """After a step's events change: its flag set by whichever scene now ends it."""
    if before is None or not before.once:
        return
    after = next((s for s in steps(edits.quest) if s.start == before.start), None)
    if after is None:
        return
    end = last_scene(edits.quest, after)
    setters = [n for n in after.events if any(f == before.once for _, f in
                                              (edits.quest.event_named(n).flags_in_script or []))]
    if setters == [end]:
        return
    for name in setters:
        unset_flag(edits, name, before.once, lengths)
    if end is not None:
        set_flag_at_end(edits, end, before.once, lengths)


# =============================================================================
# (1.31.0) A quest's reward
# =============================================================================
#
# Zodi's ask of 3 November ("A reward as a quest ends (In WotL Restoration this is done after Agrias birthday event
# and it rewards the player the Tynar Rouge)"; when he chose it: gil, an item, a unit joining the party), his choices
# "Its last step only" and "A line in the scene", given silently too: the quest's last step's last scene gives gil,
# items (the game's or the mod's own) and one of its own units joining. Gil and items are its event's Reward
# (`side_quests.Reward`), which Mod Studio Framework gives as the scene's script sets the step's flag (1.31.0: never
# while a scene is replayed, as the game refuses the flag then). (His test 66) A unit joins as the game's own scenes
# have theirs join: marked Join After Event, the scene ending with the game's party changes (DisplayConditions 7),
# which asks on its New Party Member screen whether it joins, and with the party full which unit to dismiss. The scene
# says the gil and items in the game's narration after its last line, for four seconds (his test 68, his word on test
# 70). The reward
# stays on the last step's last scene as the steps change (`_keeps_reward`).

#: No one says it (253), as event 376's narration and WotL Restoration's event 579's reward line name no unit; 1.31.0
#: said it in a speaker's box at the bottom of the screen (0x12), which still reads as a reward's line.
NARRATOR, OLD_REWARD_BOX = 253, 0x12
#: (His test 66: "the reward message looks very ugly ... It would look a lot better if we used the narrator text that
#: appeared in some of our other tests ... we would need it to appear on the screen for a bit longer for the player
#: to read it. Or maybe the user should click or press their interact key to continue"; his choice left to the
#: recommendation) The reward said as the game's narrations are (events 008, 201 and 203,
#: `dev/research/sidequests/recruits.py`): the words alone at the centre of the screen (box 0x8B: kept open until a
#: ChangeDialog closes it, centred words, at the centre), their opening the narrations' (the options byte, 13), the
#: wait for its words (WaitForInstruction 1), then closed by a ChangeDialog of its window (the box's low two bits, 3)
#: to no line, and the wait for it to close. A box not kept open (event 014's 0x03) closes as soon as its words are out.
NARRATION_BOX, NARRATION_OPTIONS = 0x8B, 13
NARRATION_WINDOW = NARRATION_BOX & 0x03
#: (His test 68: "The narration for the reward appeared and then disappeared without any input ... If it stayed on
#: screen for five seconds that would be perfect if you can not make it input based"; his choice "Five seconds") The
#: game's dialog code ends a narration once its words are out and no sound of its window plays (`dev/research/
#: sidequests/scene_boxes.py`): the game's narrations are voiced, a reward's line isn't, so its words went at once. A
#: box kept open stays until its ChangeDialog, so a Wait before the close keeps them on the screen. Test 70's 300
#: frames stayed about five seconds (his word: "functioned exactly how you said it would"), so the remaster counts an
#: event's frames 60 a second, as `event_scripts` does. (His word on test 70: "instead of 5 seconds for the narration
#: reward text can we make it 4 seconds") 240 frames, four seconds. A narration written before has none (tests 67 and
#: 68) or test 70's 300; `_holds_narration` reads any.
NARRATION_HOLD = 240
CHANGE_DIALOG = 0x51
REWARD_BOXES = (NARRATION_BOX, OLD_REWARD_BOX)
#: (His test 66: "If you have a full party and a new unit wants to join the party the vanilla game asked which unit
#: you want to give up to make room or if you do not want the new unit") A unit joins as the game's own scenes have
#: theirs join (117, 170, 213, 298, 374, 427, 483, 489): the party changes (DisplayConditions 7, its New Party Member
#: screen asking about each unit there marked Join After Event, without Save Formation; the dismissal screen when the
#: party's 50 places are full) and the wait for them (WaitForInstruction 56, the conditions' task), a second after the
#: scene has darkened and a moment before it ends, as the game's waits are. 1.31.0's CallFunction 1 (0x43, its join
#: 1: no screen, no one when the party is full) still reads as a reward's unit joining.
PARTY_CHANGES, TASK_CONDITIONS = 7, 56
PARTY_CHANGES_BEFORE, PARTY_CHANGES_AFTER = 60, 90
CALL_FUNCTION, JOIN_UNITS = 0x43, 1
#: What New quest's sample gives (his choice "Its last step only": its Ending), and what a reward says until its
#: words are changed; 1.31.0 said a unit joining too (`JOINED`), which the New Party Member screen says now.
SAMPLE_REWARD_GIL = 1000
RECEIVED = "Received {what}!"
JOINED = "{a} {job} joined the party!"


@dataclass
class Reward:
    """A quest's reward as the page shows it: its gil, its items (`(the game's item number or the mod's own item's
    name, count)`), the place (0 to 15) of its scene's own unit joining (None for none), and whether its scene says
    its gil and items (`said`; `line` its narration's line's id in the scene's words, None when it has none)."""
    gil: int = 0
    items: list = field(default_factory=list)
    unit: Optional[int] = None
    said: bool = True
    line: Optional[int] = None

    def gives(self) -> bool:
        return bool(self.gil or self.items or self.unit is not None)


def reward_scene(quest: sq.Quest) -> Optional[str]:
    """(His choice "Its last step only") The scene a quest's reward is given in: its last step's last scene (a
    battle's won scene when the step ends with a battle), or None when it has no step."""
    made = steps(quest)
    return last_scene(quest, made[-1]) if made else None


def _reward_flag(quest: sq.Quest) -> str:
    """The flag the last step sets as it ends (its own), which gives the reward; "" when it has none."""
    made = steps(quest)
    return made[-1].once if made else ""


def scene_units(quest: sq.Quest, scene: str) -> Optional[str]:
    """The quest's own battle a scene of a step's own shows as its units (its setup's EnemyBattle, else its
    SceneUnits, naming one of the quest's battles); None for a scene in a battle (the battle's units join as its unit
    cards say, Join After Event) or one showing the game's units."""
    ev = quest.event_named(scene)
    if ev is None or ev.battle is not None or role(quest, scene) != "scene":
        return None
    for key in SCENE_UNITS_FIELDS:
        units = ev.setup.get(key)
        if isinstance(units, str) and any(b.name == units for b in quest.battles):
            return units
    return None


def _is_reward_line(ins) -> bool:
    """A line saying a reward: the narration (`NARRATION_BOX`), or 1.31.0's speaker's box at the bottom, said by no
    one."""
    return ins.opcode == 0x10 and es.operand(ins, "box") in REWARD_BOXES and es.operand(ins, "unit") == NARRATOR


def _is_wait(ins, task: int) -> bool:
    return ins.opcode == 0xE5 and es.operand(ins, "task") == task


def _closes_narration(ins) -> bool:
    """The ChangeDialog that closes the narration's window."""
    return ins.opcode == CHANGE_DIALOG and es.operand(ins, "box") == NARRATION_WINDOW and \
        es.operand(ins, "line") == NO_LINE


def _is_old_join(ins) -> bool:
    """1.31.0's unit joining: CallFunction 1, the game's silent join."""
    return ins.opcode == CALL_FUNCTION and es.operand(ins, "function") == JOIN_UNITS


def _party_changes_at(instructions: list, at: int) -> bool:
    """Whether the reward's party changes (`_party_changes`) start at `at`: the wait before, DisplayConditions 7, the
    wait for it, the wait after."""
    part = instructions[at:at + 4]
    return len(part) == 4 and part[0].opcode == 0xF1 and es.operand(part[0], "frames") == PARTY_CHANGES_BEFORE \
        and part[1].opcode == DISPLAY_CONDITIONS and es.operand(part[1], "display") == PARTY_CHANGES \
        and _is_wait(part[2], TASK_CONDITIONS) \
        and part[3].opcode == 0xF1 and es.operand(part[3], "frames") == PARTY_CHANGES_AFTER


def _joins(instructions: list) -> bool:
    """Whether a script has the reward's unit join: the party changes as Mod Studio writes them, or 1.31.0's
    CallFunction 1."""
    return any(_is_old_join(ins) or _party_changes_at(instructions, n) for n, ins in enumerate(instructions))


def reward_of(edits: QuestEdits, lengths: es.Lengths) -> Optional[Reward]:
    """The quest's reward as its last step's last scene gives it (`reward_scene`): its Reward's gil and items (when it
    comes with the step's flag), its own unit marked Join After Event when its script has them join (a scene Mod
    Studio made: a copy of one of the game's that has its own join is not), its narration's line; said by default
    when it gives no gil or items. None when the quest has no step."""
    quest = edits.quest
    scene = reward_scene(quest)
    if scene is None:
        return None
    ev = quest.event_named(scene)
    out = Reward(said=False)
    if ev.reward is not None and ev.reward.flag == _reward_flag(quest):
        out.gil, out.items = ev.reward.gil, list(ev.reward.items)
    try:
        instructions = es.read_script(edits.files[ev.script], lengths, "enhanced").instructions
    except (es.ScriptError, KeyError):
        instructions = []
    lines = [es.operand(i, "line") for i in instructions if _is_reward_line(i)]
    if lines:
        out.said, out.line = True, lines[0]
    units = scene_units(quest, scene)
    if units is not None and not ev.copied_from and _joins(instructions):
        out.unit = next((u.slot for u in entd.battle_units(battle_block(edits, units))
                         if u.occupied and u.values["join_after_event"]), None)
    if not (out.gil or out.items) and out.line is None:
        # Nothing said yet: Said in the scene is ticked for gil and items to come.
        out.said = True
    return out


def _article(name: str) -> str:
    return "an" if name[:1].lower() in "aeiou" else "a"


def _plural(name: str) -> str:
    if name.endswith("s"):
        return name
    if len(name) > 1 and name.endswith("y") and name[-2].lower() not in "aeiou":
        return name[:-1] + "ies"
    if name.endswith(("x", "ch", "sh")):
        return name + "es"
    return name + "s"


def reward_words(gil: int = 0, items=(), item_words: Optional[dict] = None) -> str:
    """What a reward's line says until its words are changed (`RECEIVED`): "Received 1,000 gil, 3 potions and a Moon
    Sword!"; "" for none. A unit joining isn't said: the game's New Party Member screen says it. An item is said by
    its singular and plural (`item_words`, {the game's item number or the mod's own item's name: (singular,
    plural)}, as the game's Item table and a mod's item give them), else by its name or number."""
    words = item_words or {}
    parts = [f"{gil:,} gil"] if gil else []
    for item, count in items:
        singular, plural = words.get(item) or ("", "")
        singular = singular or (item if isinstance(item, str) else f"item {item}")
        plural = plural or _plural(singular)
        parts.append(f"{_article(singular)} {singular}" if count == 1 else f"{count} {plural}")
    if not parts:
        return ""
    return RECEIVED.format(what=parts[0] if len(parts) == 1 else f"{', '.join(parts[:-1])} and {parts[-1]}")


def _written_words(gil: int, items, job: str, item_words: Optional[dict]) -> set:
    """Every way Mod Studio wrote a reward's line: as now (`reward_words`), and as 1.31.0 did, its unit joining said
    after (`JOINED`, its job's name `job`)."""
    now = reward_words(gil, items, item_words)
    joined = JOINED.format(a=_article(job).capitalize(), job=job) if job else ""
    return {now, " ".join(part for part in (now, joined) if part)}


def _change_script(edits: QuestEdits, ev: sq.QuestEvent, lengths: es.Lengths, change) -> None:
    """An event's script as `change` makes its instructions (a list of them, given), its FlagsInScript and
    RamzaInScript following their instructions."""
    instructions = list(es.read_script(edits.files[ev.script], lengths, "enhanced").instructions)
    flags = [(instructions[n], place, f) for n, place, f in _marks(ev, instructions)]
    ramza = _ramza_marks(ev, instructions)
    changed = change(instructions)
    marks = [(n, place, f) for held, place, f in flags for n, ins in enumerate(changed) if ins is held]
    _rewrite(edits, ev, changed, marks, ramza)


def _holds_narration(ins) -> bool:
    """(His test 68) The wait that keeps the narration's words on the screen before its close: any number of frames,
    as Mod Studio wrote it (test 70's 300, `NARRATION_HOLD` now) or a modder changed it."""
    return ins.opcode == 0xF1


def _without_reward(instructions: list) -> list:
    """A script's instructions without a reward's: its lines (each with the wait for its words, the narration's hold
    when it has one, and its close and the wait for it), its unit joining (the party changes as Mod Studio writes
    them, with their waits; 1.31.0's CallFunction 1)."""
    out, at = [], 0
    while at < len(instructions):
        ins = instructions[at]
        if _is_reward_line(ins):
            # Only the narration has a hold and a close of its own (1.31.0's box at the bottom had neither).
            narration = es.operand(ins, "box") == NARRATION_BOX
            at += 1
            if at < len(instructions) and _is_wait(instructions[at], es.TASK_MESSAGE):
                at += 1
            if narration and at + 1 < len(instructions) and _holds_narration(instructions[at]) \
                    and _closes_narration(instructions[at + 1]):
                at += 1
            if narration and at < len(instructions) and _closes_narration(instructions[at]):
                at += 1
                if at < len(instructions) and _is_wait(instructions[at], es.TASK_MESSAGE):
                    at += 1
            continue
        if _party_changes_at(instructions, at):
            at += 4
            continue
        if not _is_old_join(ins):
            out.append(ins)
        at += 1
    return out


def _reward_at(instructions: list, flag_set: list) -> int:
    """Where a reward's instructions go in a scene's: after its last line (and the wait for it) when it says any,
    else before its flag is set (`flag_set`, the instructions setting it), else before its end."""
    last = max((n for n, ins in enumerate(instructions) if ins.opcode == 0x10), default=None)
    if last is not None:
        at = last + 1
        if at < len(instructions) and instructions[at].opcode == 0xE5 \
                and es.operand(instructions[at], "task") == es.TASK_MESSAGE:
            at += 1
        return at
    first = min((n for n, ins in enumerate(instructions) if any(ins is f for f in flag_set)), default=None)
    if first is not None:
        return first
    return _end_at(instructions)


def _end_at(instructions: list) -> int:
    """Where a scene's script ends: before its End, or after its last instruction."""
    return len(instructions) - 1 if instructions and instructions[-1].opcode == es.END else len(instructions)


def _party_changes(lengths: es.Lengths) -> list:
    """(His test 66) The reward's unit asked to join as the game's own scenes ask theirs: a wait, the game's party
    changes (DisplayConditions 7), the wait for them, a wait."""
    def make(opcode, **values):
        return es.make(opcode, lengths, "enhanced", **values)
    return [make(0xF1, frames=PARTY_CHANGES_BEFORE), make(DISPLAY_CONDITIONS, display=PARTY_CHANGES, frames=60),
            make(0xE5, task=TASK_CONDITIONS), make(0xF1, frames=PARTY_CHANGES_AFTER)]


def _narration(lengths: es.Lengths, line_id: int) -> list:
    """(His test 66) The reward's line said as the game's narrations are: the words alone at the centre of the screen
    (`NARRATION_BOX`), said by no one, the wait for them, (his test 68, his word on test 70) four seconds on the
    screen (`NARRATION_HOLD`), then closed, and the wait for it to close."""
    def make(opcode, **values):
        return es.make(opcode, lengths, "enhanced", **values)
    return [make(0x10, thread=0x10, box=NARRATION_BOX, line=line_id, unit=NARRATOR, options=NARRATION_OPTIONS),
            make(0xE5, task=es.TASK_MESSAGE), make(0xF1, frames=NARRATION_HOLD),
            make(CHANGE_DIALOG, box=NARRATION_WINDOW, line=NO_LINE), make(0xE5, task=es.TASK_MESSAGE)]


def _take_reward(edits: QuestEdits, lengths: Optional[es.Lengths]) -> Optional[dict]:
    """The quest's reward taken from its scene (its Reward, its narrator's line and words, its unit's Join After Event
    and its joining): what it was, where, and its line's words in each language; None when it has none."""
    quest = edits.quest
    if lengths is None:
        return None
    reward = reward_of(edits, lengths)
    if reward is None or (not reward.gives() and reward.line is None):
        return None
    scene = reward_scene(quest)
    ev = quest.event_named(scene)
    units = scene_units(quest, scene)
    words = {}
    if reward.line is not None:
        for language, lines in edits.words.get(scene, {}).items():
            for line in lines:
                if line.line_id == reward.line:
                    words[language] = line.line
            edits.words[scene][language] = [line for line in lines if line.line_id != reward.line]
    ev.reward = None
    _change_script(edits, ev, lengths, _without_reward)
    if reward.unit is not None and units is not None:
        set_unit(edits, units, reward.unit, join_after_event=False)
    return {"reward": reward, "scene": scene, "units": units, "words": words}


def _place_reward(edits: QuestEdits, lengths: es.Lengths, gil: int, items, unit: Optional[int], said: bool,
                  words: dict) -> None:
    """A reward given by the quest's last step's last scene: its Reward (with the step's flag), its gil and items said
    in the narration (`words`, by language, English for any not given) after its last line, its unit marked Join
    After Event and asked to join by the game's party changes as the scene ends (`_party_changes`); nothing when it
    gives nothing or its step has no flag of its own."""
    quest = edits.quest
    scene = reward_scene(quest)
    flag = _reward_flag(quest)
    units = scene_units(quest, scene) if scene is not None else None
    unit = unit if units is not None else None
    if scene is None or not flag or not (gil or items or unit is not None):
        return
    ev = quest.event_named(scene)
    ev.reward = sq.Reward(flag, gil, list(items)) if gil or items else None
    if unit is not None:
        set_unit(edits, units, unit, join_after_event=True)
    narration = []
    english = words.get(LANGUAGE, "") if words else ""
    if said and english and (gil or items):
        taken = {line.line_id for lines in edits.words.get(scene, {}).values() for line in lines}
        line_id = max(taken | {WON_LINE - 1}) + 1
        for language in LANGUAGES:
            set_line(edits, scene, line_id, words.get(language, english), language)
        narration = _narration(lengths, line_id)
    joining = _party_changes(lengths) if unit is not None else []
    if not narration and not joining:
        return

    def change(instructions: list) -> list:
        marks = _marks(ev, instructions)
        flag_set = [instructions[n] for n, place, f in marks if f == flag and place == 1]
        at = _reward_at(instructions, flag_set)
        out = instructions[:at] + narration + instructions[at:]
        # The party changes last, before the step's flag is set (or the end).
        first = min((n for n, ins in enumerate(out) if any(ins is f for f in flag_set)), default=None)
        end = first if first is not None else _end_at(out)
        return out[:end] + joining + out[end:]
    _change_script(edits, ev, lengths, change)


def _put_reward(edits: QuestEdits, lengths: es.Lengths, held: dict) -> None:
    """A reward taken (`_take_reward`) given to the quest's last step's last scene as the steps are now: its unit only
    when that scene shows the same units, its line's words as they were."""
    reward = held["reward"]
    scene = reward_scene(edits.quest)
    same = scene is not None and held["units"] is not None and scene_units(edits.quest, scene) == held["units"]
    _place_reward(edits, lengths, reward.gil, reward.items, reward.unit if same else None, reward.said,
                  held["words"])


def _keeps_reward(change):
    """(His choice "Its last step only") A change to a quest's steps that keeps its reward on its last step's last
    scene: taken from where it is before the change, given to the last scene after it."""
    @functools.wraps(change)
    def kept(edits, *args, **kwargs):
        lengths = kwargs.get("lengths", args[-1] if args else None)
        held = _take_reward(edits, lengths)
        try:
            return change(edits, *args, **kwargs)
        finally:
            if held is not None:
                _put_reward(edits, lengths, held)
    return kept


def set_reward(edits: QuestEdits, lengths: es.Lengths, gil: int = 0, items=(), unit: Optional[int] = None,
               said: bool = True, item_words: Optional[dict] = None, job_names: Optional[dict] = None) -> None:
    """
    The quest's reward, given by its last step's last scene (`reward_scene`):
    `gil`, `items` (`(the game's item number or the mod's own item's name,
    count)`), its own unit at place `unit` asked to join on the game's New
    Party Member screen (None for none), and whether the scene says its gil
    and items in the narration (`said`). The line says what `reward_words`
    says (items by `item_words`) unless its words were changed, which stay;
    a line as 1.31.0 wrote it (its unit's job in `job_names`) is written
    again as now.
    """
    quest = edits.quest
    scene = reward_scene(quest)
    if scene is None:
        raise ValueError("the quest has no step to give a reward")
    if not 0 <= gil <= sq.MOST_GIL:
        raise ValueError(f"a reward's gil is 0 to {sq.MOST_GIL:,}")
    jobs = job_names or {}

    def job_of(units: Optional[str], slot: Optional[int]) -> str:
        if units is None or slot is None:
            return ""
        unit_values = entd.battle_units(battle_block(edits, units))[slot].values
        return jobs.get(unit_values["main_job"], "")
    held = _take_reward(edits, lengths)
    units = scene_units(quest, scene)
    unit = unit if units is not None else None
    words = {LANGUAGE: reward_words(gil, items, item_words)}
    if held is not None and held["words"]:
        # Its words changed from what Mod Studio wrote stay as they are.
        old = held["reward"]
        if held["words"].get(LANGUAGE) not in _written_words(old.gil, old.items, job_of(held["units"], old.unit),
                                                             item_words):
            words = dict(held["words"])
    _place_reward(edits, lengths, gil, items, unit, said, words if words.get(LANGUAGE) else {})


# =============================================================================
# Steps made and changed
# =============================================================================

@_keeps_reward
def add_step(edits: QuestEdits, place, first: str, lengths: es.Lengths) -> int:
    """
    A step of the quest: a start at `place` (one of the world map's places
    by its number, or one of the mod's own by its name) loading event
    `first`, which plays once: a flag of its own ("<first> done"), set as its
    last scene ends, and the start waiting until it is set; after the step
    before it, if any, is done (its own flag set). Returns its start's index.
    """
    quest = edits.quest
    if quest.event_named(first) is None:
        raise ValueError(f"{first} isn't an event of the quest")
    before = steps(quest)
    flag = free_name(f"{first} done", quest.flags)
    quest.flags.append(flag)
    when = []
    if before:
        last = before[-1]
        done = last.once or (last.sets[-1] if last.sets else "")
        if done:
            when.append(sq.Condition("Flag", 0, done, "Is", 1))
    when.append(sq.Condition("Flag", 0, flag, "Is", 0))
    quest.starts.append(sq.Start(place, first, when))
    step = steps(quest)[-1]
    end = last_scene(quest, step)
    if end is not None:
        set_flag_at_end(edits, end, flag, lengths)
    return len(quest.starts) - 1


def set_start_place(start: sq.Start, place, floor: str = "") -> None:
    """(1.25.0) Where a step waits: one of the world map's places (the game's by its number, the mod's own by its
    name), or a floor of one of the mod's own dungeons (`floor`, the floor's name, `place` the dungeon's): it plays as
    the floor is chosen, in place of the floor's battle, while its conditions hold, and never as a travel passes (its
    Passing Waits). A world map place clears the floor."""
    start.place = place
    start.floor = floor if isinstance(place, str) and floor else ""
    if start.floor:
        start.stops_passing = False


@_keeps_reward
def insert_after(edits: QuestEdits, after: str, new: str, lengths: es.Lengths) -> None:
    """
    Event `new` played after `after` on the same visit: a scene's next event
    (it goes straight on, as the game's scene 69 into its battle 70). After a
    battle, or the scene as it starts, that is after the scene once it is won.
    Whatever followed `after` follows `new` (a battle's: its won scene). The
    step's flag is then set by whichever scene ends it.
    """
    quest = edits.quest
    ev, added = quest.event_named(after), quest.event_named(new)
    if ev is None or added is None:
        raise ValueError("both are events of the quest")
    before = step_of(quest, after)
    if ev.battle is not None:
        ev = quest.event_named(ev.battle.won)
    elif role(quest, after) in ("start", "lost"):
        ev = quest.event_named(quest.fight_of(after).battle.won)
    following = ev.next_event
    ev.next_event = new
    tail = quest.event_named(added.battle.won) if added.battle is not None else added
    if tail is not None and following and following != new:
        tail.next_event = following
    _move_done_flag(edits, before, lengths)


def can_remove(quest: sq.Quest, name: str) -> bool:
    """Whether an event can go by itself: not the scene a battle plays once it is won (the battle goes with it), nor
    (1.12.0) the one once it is lost (it goes once the battle protects no unit, `set_protect`)."""
    return quest.event_named(name) is not None and role(quest, name) not in ("won", "lost")


@_keeps_reward
def remove_event(edits: QuestEdits, name: str, lengths: es.Lengths) -> None:
    """
    An event out of the quest; a battle with the scenes it plays as it starts
    and once it is won, and its units if no other battle fights them. What
    followed it follows what came before it; a start that loaded it loads
    what followed, or goes with its step (`remove_step`) if nothing did. The
    scene a battle plays once it is won goes only with its battle
    (`can_remove`).
    """
    quest = edits.quest
    ev = quest.event_named(name)
    if ev is None:
        return
    if not can_remove(quest, name):
        raise ValueError(f"{name} is played once its battle is won or lost: it goes with the battle")
    before = step_of(quest, name)
    if role(quest, name) == "start":
        quest.fight_of(name).battle.start = ""
        _drop(edits, name)
        _move_done_flag(edits, before, lengths)
        return
    # (1.31.0) A scene during a battle: out of its During, those after it setting the guards of their places now.
    if role(quest, name) == "during":
        fight = quest.fight_of(name).battle
        fight.during = [d for d in fight.during if d.event != name]
        _drop(edits, name)
        _reguard(edits, fight, lengths)
        return
    gone = [name]
    following = ev.next_event
    if ev.battle is not None:
        won = quest.event_named(ev.battle.won)
        following = won.next_event if won is not None else ""
        gone += [n for n in ev.battle.scenes() if n]
    for other in quest.events:
        if other.name not in gone and other.next_event in gone:
            other.next_event = following
    loaded = [n for n, start in enumerate(quest.starts) if start.event == name]
    if loaded and not following:
        # Nothing follows it: its step goes, and with it everything only that step plays.
        for index in reversed(loaded):
            remove_step(edits, index, lengths)
        for n in gone:
            _drop(edits, n)
        _drop_units(edits)
        return
    for index in loaded:
        quest.starts[index].event = following
    for n in gone:
        _drop(edits, n)
    _drop_units(edits)
    _move_done_flag(edits, before, lengths)


#: The setup fields a scene names its units by: one of the game's battles by its number, or one of the quest's by its
#: name (`make_sample_scene`'s own units).
SCENE_UNITS_FIELDS = ("EnemyBattle", "SceneUnits")


def units_used(quest: sq.Quest) -> set:
    """The names of the quest's battles' units its events use: each battle event's, and (Zodi, 4 November: a new
    scene's two units of its own) each a scene's setup names (`SCENE_UNITS_FIELDS`)."""
    used = {e.battle.units for e in quest.events if e.battle is not None}
    used |= {e.setup[key] for e in quest.events for key in SCENE_UNITS_FIELDS if isinstance(e.setup.get(key), str)}
    return used


def _drop_units(edits: QuestEdits) -> None:
    """The quest's battles' units no event uses any more (`units_used`), out with their files."""
    quest = edits.quest
    used = units_used(quest)
    for battle in [b for b in quest.battles if b.name not in used]:
        quest.battles.remove(battle)
        if not any(b.units == battle.units for b in quest.battles):
            edits.files.pop(battle.units, None)


def _drop(edits: QuestEdits, name: str) -> None:
    ev = edits.quest.event_named(name)
    if ev is None:
        return
    edits.quest.events.remove(ev)
    edits.words.pop(name, None)
    if ev.battle is None and not any(e.script == ev.script for e in edits.quest.events):
        edits.files.pop(ev.script, None)


@_keeps_reward
def remove_step(edits: QuestEdits, index: int, lengths: es.Lengths) -> None:
    """A step out of the quest: its start, the events only it plays, its flag (and every condition on it)."""
    quest = edits.quest
    step = steps(quest)[index]
    others = {n for s in steps(quest) if s.start != index for n in s.events}
    quest.starts.pop(index)
    for name in step.events:
        if name not in others and quest.event_named(name) is not None:
            _drop(edits, name)
    _drop_units(edits)
    if step.once and not any(step.once in [f for _, f in e.flags_in_script] for e in quest.events):
        remove_flag(edits, step.once, lengths)


# =============================================================================
# Flags and names
# =============================================================================

def add_flag(edits: QuestEdits, name: str) -> str:
    name = free_name(name, edits.quest.flags)
    edits.quest.flags.append(name)
    return name


@_keeps_reward
def remove_flag(edits: QuestEdits, name: str, lengths: es.Lengths) -> None:
    """A flag out of the quest: each condition on it (a start's or (1.15.0) a rumor's), and each script's setting of
    it. A rumor's own flag goes with its rumor (`remove_rumor`)."""
    quest = edits.quest
    if name in quest.flags:
        quest.flags.remove(name)
    for holder in quest.starts + quest.rumors:
        holder.when = [c for c in holder.when if not (c.kind == "Flag" and c.flag == name)]
    for ev in list(quest.events):
        if any(f == name for _, f in ev.flags_in_script):
            unset_flag(edits, ev.name, name, lengths)


def rename_flag(edits: QuestEdits, old: str, new: str) -> None:
    quest = edits.quest
    if old not in quest.flags or not good_name(new) or new in quest.flags:
        raise ValueError(f"{new} can't be the flag {old}'s name")
    quest.flags[quest.flags.index(old)] = new
    for holder in quest.starts + quest.rumors:
        for c in holder.when:
            if c.kind == "Flag" and c.flag == old:
                c.flag = new
    for rumor in quest.rumors:
        if rumor.read == old:
            rumor.read = new
    for ev in quest.events:
        ev.flags_in_script = [(at, new if f == old else f) for at, f in ev.flags_in_script]
        # (1.31.0) And a reward coming with it.
        if ev.reward is not None and ev.reward.flag == old:
            ev.reward.flag = new


def rename_event(edits: QuestEdits, old: str, new: str) -> None:
    """An event's name, everything naming it named so (starts, next events, battles' scenes, its words)."""
    quest = edits.quest
    if quest.event_named(old) is None or not good_name(new) or quest.event_named(new) is not None:
        raise ValueError(f"{new} can't be the event {old}'s name")
    quest.event_named(old).name = new
    for start in quest.starts:
        if start.event == old:
            start.event = new
    for ev in quest.events:
        if ev.next_event == old:
            ev.next_event = new
        if ev.battle is not None:
            if ev.battle.start == old:
                ev.battle.start = new
            if ev.battle.won == old:
                ev.battle.won = new
            if ev.battle.lost == old:
                ev.battle.lost = new
            for d in ev.battle.during:
                if d.event == old:
                    d.event = new
    if old in edits.words:
        edits.words[new] = edits.words.pop(old)


# =============================================================================
# A start's conditions, as the page says them (and (1.15.0) a rumor's: its When is a start's)
# =============================================================================

#: The story's progress (variable 110), which the world map's own steps test.
STORY = sq.STORY_PROGRESS


def story_past(start) -> Optional[int]:
    """The story's progress a start (or a rumor) waits for (a condition that variable 110 is at least it), or
    None."""
    return next((c.value for c in start.when if c.kind == "Variable" and c.variable == STORY
                 and c.test == "AtLeast"), None)


def set_story_past(start, value: Optional[int]) -> None:
    """Waits until the story's progress is at least `value` (None: not for the story), its other conditions kept,
    the story's first."""
    start.when = [c for c in start.when if not (c.kind == "Variable" and c.variable == STORY and c.test == "AtLeast")]
    if value is not None:
        start.when.insert(0, sq.Condition("Variable", STORY, "", "AtLeast", int(value)))


def flag_condition(start, flag: str) -> Optional[int]:
    """What a start (or a rumor) waits for of a flag: 0, 1, or None for nothing."""
    return next((c.value for c in start.when if c.kind == "Flag" and c.flag == flag), None)


def set_flag_condition(start, flag: str, value: Optional[int]) -> None:
    start.when = [c for c in start.when if not (c.kind == "Flag" and c.flag == flag)]
    if value is not None:
        start.when.append(sq.Condition("Flag", 0, flag, "Is", int(value)))


# =============================================================================
# (1.15.0) Tavern rumors
# =============================================================================

#: The flag a rumor sets once it is read, named for it as it is made (and renamed with it while it has that name).
READ_FLAG = "{name} read"
#: A rumor the page makes: its name until it is given one.
NEW_RUMOR = "Rumor"


def rumor_named(quest: sq.Quest, name: str) -> Optional[sq.Rumor]:
    return next((r for r in quest.rumors if r.name == name), None)


def add_rumor(edits: QuestEdits, name: str = NEW_RUMOR) -> str:
    """A new rumor of the quest: told in every tavern at any point of the story (until its towns and conditions are
    given), its title and words to be written, and a flag of its own made, set once it is read. Its name."""
    quest = edits.quest
    name = free_name(name, [r.name for r in quest.rumors])
    flag = add_flag(edits, READ_FLAG.format(name=name))
    quest.rumors.append(sq.Rumor(name, read=flag))
    return name


def remove_rumor(edits: QuestEdits, name: str, lengths: es.Lengths) -> None:
    """A rumor out of the quest, and its flag with it (each condition on it: a step waiting until it is read)."""
    quest = edits.quest
    rumor = rumor_named(quest, name)
    if rumor is None:
        return
    quest.rumors.remove(rumor)
    if not any(r.read == rumor.read for r in quest.rumors):
        remove_flag(edits, rumor.read, lengths)


def rename_rumor(edits: QuestEdits, old: str, new: str) -> None:
    """A rumor's name; its flag's too while it is still named for it (`READ_FLAG`) and that name is free."""
    quest = edits.quest
    rumor = rumor_named(quest, old)
    if rumor is None or not good_name(new) or (new.lower() != old.lower()
                                                and any(r.name.lower() == new.lower() for r in quest.rumors)):
        raise ValueError(f"{new} can't be the rumor {old}'s name")
    rumor.name = new
    flag = READ_FLAG.format(name=new)
    if rumor.read == READ_FLAG.format(name=old) and good_name(flag) and flag not in quest.flags:
        rename_flag(edits, rumor.read, flag)


def set_rumor_words(edits: QuestEdits, name: str, title: Optional[str] = None, text: Optional[str] = None) -> None:
    """A rumor's title (one line, as the tavern's list shows it) or words (its paragraphs apart by line breaks), each
    without spaces at either end, and its words' line breaks as the game's own rumors have them."""
    rumor = rumor_named(edits.quest, name)
    if title is not None:
        rumor.title = title.strip()
    if text is not None:
        rumor.text = text.replace("\r\n", "\n").replace("\r", "\n").strip()


def told_in(rumor: sq.Rumor, mod_towns=()) -> list:
    """The towns whose taverns tell a rumor (the world map's places 0 to 14, and (1.18.0) the mod's own towns with a
    menu, `mod_towns`, by their names): every town's when it names none."""
    return list(rumor.towns) if rumor.towns else list(range(sq.TOWNS)) + list(mod_towns)


def _game_town(town) -> bool:
    return isinstance(town, int) and not isinstance(town, bool) and 0 <= town < sq.TOWNS


def _towns_in_order(towns, mod_towns) -> list:
    """The game's towns by their places, then the mod's in `mod_towns`' order, then any other name as it was."""
    named = [t for t in towns if isinstance(t, str)]
    return (sorted(t for t in towns if _game_town(t)) + [t for t in mod_towns if t in named]
            + [t for t in named if t not in mod_towns])


def toggle_rumor_town(edits: QuestEdits, name: str, town, mod_towns=()) -> bool:
    """A town's tavern tells the rumor, or no longer does (one of the game's by its place, or (1.18.0) one of the mod's
    towns with a menu, `mod_towns`, by its name); never none (a rumor is told in one tavern at least: False, and
    nothing changed, for its last). Every town's (the game's and the mod's) is written as none named, as the helper
    takes it."""
    rumor = rumor_named(edits.quest, name)
    if not (_game_town(town) or (isinstance(town, str) and town in mod_towns)):
        return False
    towns = told_in(rumor, mod_towns)
    if town in towns:
        if len(towns) == 1:
            return False
        towns.remove(town)
    else:
        towns.append(town)
    every = set(range(sq.TOWNS)) | set(mod_towns)
    rumor.towns = [] if set(towns) == every else _towns_in_order(towns, mod_towns)
    return True


def set_rumor_towns(edits: QuestEdits, name: str, towns, mod_towns=()) -> None:
    """The towns whose taverns tell a rumor (none, or all of them: every town's, the game's and (1.18.0) the mod's
    with a menu, `mod_towns`)."""
    chosen = {int(t) for t in towns if not isinstance(t, str) and 0 <= int(t) < sq.TOWNS}
    chosen |= {t for t in towns if isinstance(t, str) and t in mod_towns}
    every = set(range(sq.TOWNS)) | set(mod_towns)
    rumor_named(edits.quest, name).towns = [] if chosen == every else _towns_in_order(chosen, mod_towns)


def waits_for_rumor(start: sq.Start, rumor: sq.Rumor) -> bool:
    """Whether a start waits until a rumor is read (its flag set)."""
    return flag_condition(start, rumor.read) == 1


def set_waits_for_rumor(start: sq.Start, rumor: sq.Rumor, on: bool) -> None:
    set_flag_condition(start, rumor.read, 1 if on else None)


# =============================================================================
# A battle's units
# =============================================================================

def battle_block(edits: QuestEdits, battle: str) -> bytes:
    units = next(b for b in edits.quest.battles if b.name == battle)
    return edits.files[units.units]


def set_unit(edits: QuestEdits, battle: str, slot: int, **fields) -> None:
    """One of a battle's 16 units' fields changed by name (`entd.unit_with`); (Mod Studio Framework 1.53.0) its main job
    changed, its job of its mod's own (the battle's Jobs) given up, so the job the card shows is the one it wears."""
    units = next(b for b in edits.quest.battles if b.name == battle)
    edits.files[units.units] = entd.battle_with(edits.files[units.units], slot, **fields)
    if "main_job" in fields:
        units.jobs.pop(slot, None)


def unit_job(edits: QuestEdits, battle: str, slot: int) -> str:
    """The job of its mod's own a battle's unit wears (the battle's Jobs: the job's Name), "" when it wears none."""
    units = next(b for b in edits.quest.battles if b.name == battle)
    return units.jobs.get(slot, "")


def unit_items(edits: QuestEdits, battle: str, slot: int) -> dict:
    """(Mod Studio Framework 2.0.0, Zodi's first point of 16 November 2026) The items past 255 a battle's unit wears
    (the battle's Items): `{the place worn (`mod_battles.PLACES`): the item's number or its mod's own item's Name}`."""
    units = next(b for b in edits.quest.battles if b.name == battle)
    return dict(units.items.get(slot) or {})


def set_unit_item(edits: QuestEdits, battle: str, slot: int, place: str, item) -> None:
    """(2.0.0) One of a battle's units given an item past 255 at one of the five places it wears one
    (`mod_battles.PLACES`), or none there (`item` None: its file's byte is its item there again)."""
    from . import mod_battles as mb
    if place not in mb.PLACES or (item is not None and not mb.good_item(item)):
        raise ValueError(f"{item!r} at {place} isn't an item past 255 a unit can wear")
    units = next(b for b in edits.quest.battles if b.name == battle)
    worn = dict(units.items.get(slot) or {})
    if item is None:
        worn.pop(place, None)
    else:
        worn[place] = item
    if worn:
        units.items[slot] = worn
    else:
        units.items.pop(slot, None)


def item_renamed(quests: dict, old: str, new) -> None:
    """(2.0.0) One of the mod's items given another name (or, `new` None, taken out of the mod): every unit of the
    mod's quests that wears it wears it still (or no more)."""
    for edits in quests.values():
        for battle in edits.quest.battles:
            for slot in list(battle.items):
                worn = {place: (new if item == old and isinstance(item, str) else item)
                        for place, item in battle.items[slot].items()
                        if not (new is None and isinstance(item, str) and item == old)}
                if worn:
                    battle.items[slot] = worn
                else:
                    battle.items.pop(slot)


def set_unit_job(edits: QuestEdits, battle: str, slot: int, job: str, like: int) -> None:
    """(Zodi's order of 13 November: "choosing a mod's job on a quest unit's card") One of a battle's units put in a
    job of its mod's own, as the framework plays one (1.53.0, `dev/research/sidequests/quest_jobs.py`): its file's job
    the game's job its job is based on (`like`, 74 to 93), its career job that job, at the job level its file gives
    where that is 1 to 8 (else the sample's), and the battle's Jobs naming the job for its place."""
    units = next(b for b in edits.quest.battles if b.name == battle)
    found = entd.battle_units(edits.files[units.units])[slot]
    level = found.values["prereq_job_level"]
    edits.files[units.units] = entd.battle_with(
        edits.files[units.units], slot, main_job=like, prereq_job=like - FIRST_GENERIC_JOB,
        prereq_job_level=level if 1 <= level <= 8 else SAMPLE_JOB_LEVEL)
    units.jobs[slot] = job


def units_in_job(quests: dict, job: str) -> list:
    """Every unit of the mod's quests that wears the mod's job `job`: `[(the quest's folder, its battle's name, the
    unit's place)]`."""
    return [(folder, battle.name, slot) for folder, edits in quests.items() for battle in edits.quest.battles
            for slot, name in sorted(battle.jobs.items()) if name == job]


def job_renamed(quests: dict, old: str, new: str) -> None:
    """A job of the mod's given another name: every unit of the mod's quests that wears it wears it still."""
    for edits in quests.values():
        for battle in edits.quest.battles:
            for slot, name in battle.jobs.items():
                if name == old:
                    battle.jobs[slot] = new


def job_removed(quests: dict, job: str) -> None:
    """A job of the mod's taken out: every unit of the mod's quests that wore it is left in its file's job (the
    game's job the job was based on)."""
    for edits in quests.values():
        for battle in edits.quest.battles:
            for slot in [s for s, name in battle.jobs.items() if name == job]:
                battle.jobs.pop(slot)


def job_based_on(quests: dict, job: str, like: int) -> None:
    """A job of the mod's based on another of the game's jobs: every unit of the mod's quests that wears it has that
    job for its file's job and its career job (`set_unit_job`)."""
    for folder, battle, slot in units_in_job(quests, job):
        set_unit_job(quests[folder], battle, slot, job, like)


#: An empty place for a unit, as the game's battle files most often hold one (289 of their empty places): no
#: sprite, job or name; random birthday, bravery and faith; random abilities and equipment; its job's command.
EMPTY_UNIT = bytes.fromhex("00000000fefefefe00000000fe01fe01fe01fefefefefe0000000000feff0000ff00000000000000")
#: The unit ids a unit Mod Studio adds may have: the game's own run from 0x80 for its generic units, and a scene's
#: script finds a unit by its id, so an added one has an id no other unit of its battle has.
ADDED_UNIT_IDS = range(0x80, 0xFF)


def unit_added(block: bytes, slot: Optional[int] = None) -> tuple:
    """
    (1.17.0, `add_unit`'s, a battle ground's random battles' too) A battle's
    16 units with a copy of unit `slot` (or, when that place is empty, the
    battle's first unit) in its first empty place, with a unit id no other
    unit of the battle has: (the units, its place); (the units as they were,
    None) when its 16 places are all taken or it has no unit to copy.
    """
    found = entd.battle_units(block)
    empty = next((u.slot for u in found if not u.occupied), None)
    source = next((u for u in found if u.occupied and u.slot == slot), None) or next(
        (u for u in found if u.occupied), None)
    if empty is None or source is None:
        return block, None
    taken = {u.values["unit_id"] for u in found if u.occupied}
    new_id = next((n for n in ADDED_UNIT_IDS if n not in taken), source.values["unit_id"])
    size = entd.UNIT_BYTES
    copied = entd.unit_with(block[source.slot * size:(source.slot + 1) * size], unit_id=new_id)
    return block[:empty * size] + copied + block[(empty + 1) * size:], empty


def unit_taken_out(block: bytes, slot: int) -> bytes:
    """(1.17.0) A battle's 16 units with unit `slot`'s place empty, as the game's battle files hold an empty place."""
    size = entd.UNIT_BYTES
    return block[:slot * size] + EMPTY_UNIT + block[(slot + 1) * size:]


def add_unit(edits: QuestEdits, battle: str, slot: Optional[int] = None) -> Optional[int]:
    """
    A copy of unit `slot` (or, when that place is empty, the battle's first
    unit) in the battle's first empty place, with a unit id no other unit of
    the battle has (`unit_added`); (Mod Studio Framework 1.53.0) in the job
    of its mod's own the one copied wears, if it wears one. Returns its
    place, or None when the battle's 16 places are all taken or it has no
    unit to copy.
    """
    units = next(b for b in edits.quest.battles if b.name == battle)
    found = [u.slot for u in entd.battle_units(edits.files[units.units]) if u.occupied]
    # The one copied, as `unit_added` picks it.
    source = slot if slot in found else next(iter(found), None)
    edits.files[units.units], empty = unit_added(edits.files[units.units], slot)
    if empty is not None and source in units.jobs:
        units.jobs[empty] = units.jobs[source]
    # (2.0.0) And wearing the items past 255 the one copied wears.
    if empty is not None and units.items.get(source):
        units.items[empty] = dict(units.items[source])
    return empty


def take_out_unit(edits: QuestEdits, battle: str, slot: int, lengths: Optional[es.Lengths] = None) -> None:
    """Unit `slot` out of the battle: its place empty, as the game's battle files hold an empty place; (1.33.0) its own
    name gone with it, (his test 69) and with `lengths` its lines' marks of it; (1.53.0) and its job of its mod's own."""
    units = next(b for b in edits.quest.battles if b.name == battle)
    if lengths is not None and units.names.get(slot):
        _remark(edits, battle, slot, units.names[slot], "", lengths)
    edits.files[units.units] = unit_taken_out(edits.files[units.units], slot)
    units.names.pop(slot, None)
    units.jobs.pop(slot, None)
    units.items.pop(slot, None)


#: (1.33.0) Why an own name isn't taken: the page says it. (His test 69) None of `UNMARKABLE` either, as the name over
#: its boxes is a mark in its lines' words.
OWN_NAME_NOT_ONE = ("A unit's own name is 1 to {most} characters, none a control character or < > \", with no space "
                    "at either end.")
OWN_NAME_EMPTY_PLACE = "An empty place has no own name: put a unit there first."


def own_name(edits: QuestEdits, battle: str, slot: int) -> str:
    """(1.33.0) Unit `slot`'s own name in battle `battle`, or ""."""
    units = next(b for b in edits.quest.battles if b.name == battle)
    return units.names.get(slot, "")


def set_own_name(edits: QuestEdits, battle: str, slot: int, text: str, lengths: Optional[es.Lengths] = None) -> None:
    """
    (Mod Studio Framework 1.33.0, Zodi's choice of 5 November: "As a renamed
    unit") Unit `slot`'s own name ("" for none). The game shows a renamed
    unit's own text for a generic's name (`dev/research/sidequests/
    unit_names.py`), so the unit's name is made Random (the game then gives it
    a generic's name of its gender, and so a generic's voice); the helper
    writes the text into the unit as the game makes it, and the game copies it
    when the unit joins the party. ValueError for a name that isn't one
    (`side_quests.good_own_name`), (his test 69) holds what a mark can't
    (`UNMARKABLE`), or for an empty place. With `lengths`, the unit's lines
    are marked with it (`_remark`): the name over their boxes.
    """
    units = next(b for b in edits.quest.battles if b.name == battle)
    old = units.names.get(slot, "")
    if not text:
        units.names.pop(slot, None)
        if lengths is not None and old:
            _remark(edits, battle, slot, old, "", lengths)
        return
    if not sq.good_own_name(text) or not markable(text):
        raise ValueError(OWN_NAME_NOT_ONE.format(most=sq.MOST_OWN_NAME))
    unit = entd.battle_units(edits.files[units.units])[slot]
    if not unit.occupied:
        raise ValueError(OWN_NAME_EMPTY_PLACE)
    units.names[slot] = text
    if unit.values["unit_name"] != NO_NAME:
        set_unit(edits, battle, slot, unit_name=NO_NAME)
    if lengths is not None and text != old:
        _remark(edits, battle, slot, old, text, lengths)


# =============================================================================
# (His test 69) A unit's own name over its boxes
# =============================================================================
#
# (Zodi's test 69, 5 November: the own names "did not appear on their Speech balloon"; his choice "Each line
# changeable") The game names a box by its line's Speaker row, or by a `<speaker="...">` mark in its words, which it
# reads over the row (`dev/research/sidequests/scene_boxes.py`; his event 045's Dycedarg line has one); Speaker row 1,
# which every line Mod Studio writes is said by, has no name. An own name is no Speaker row, so each line a unit with
# an own name says carries its mark, at the start of its words in every language: given as the name is (to each of the
# unit's lines said by no one and not marked), changed with it, taken out with it or with the unit, and given to a
# line the unit is made to say; a line marked otherwise, set to No one while the unit has its name, or said by a
# Speaker row is left as it is. The Event Editor's
# Name over the box gives any line the own name, another, or none (`set_scene_mark`, `set_scene_speaker`).

#: The mark as Mod Studio writes it; its start and end as the game finds them (the first `<speaker="`, then `">`).
SPEAKER_MARK = '<speaker="{name}">'
_MARK_START, _MARK_END = '<speaker="', '">'
#: What a name over a box can't hold and be a mark: the game ends a mark at its first `">`, its words' marks at a `>`.
UNMARKABLE = '<>"'


def markable(name: str) -> bool:
    """Whether `name` can be a box's name by a mark (none of `UNMARKABLE`)."""
    return bool(name) and not any(c in name for c in UNMARKABLE)


def _mark_span(text: str) -> Optional[tuple]:
    start = text.find(_MARK_START)
    if start < 0:
        return None
    end = text.find(_MARK_END, start + len(_MARK_START))
    return None if end < 0 else (start, end + len(_MARK_END))


def mark_of(text: Optional[str]) -> Optional[str]:
    """The name a line's words give its box by a mark, as the game reads it, or None."""
    span = _mark_span(text or "")
    return None if span is None else text[span[0] + len(_MARK_START):span[1] - len(_MARK_END)]


def without_mark(text: Optional[str]) -> str:
    """A line's words without the mark naming its box."""
    text = text or ""
    span = _mark_span(text)
    return text if span is None else text[:span[0]] + text[span[1]:]


def with_mark(text: Optional[str], name: Optional[str]) -> str:
    """A line's words naming its box `name` by a mark at their start (none for None or "")."""
    words = without_mark(text)
    return SPEAKER_MARK.format(name=name) + words if name else words


def scene_battle(quest: sq.Quest, scene: str) -> Optional[str]:
    """The quest's own battle whose units scene `scene` shows (its setup's EnemyBattle, else its SceneUnits, as Mod
    Studio Framework gives them: a battle's scenes its own), or None."""
    setup = scene_setup(quest, scene)
    for key in SCENE_UNITS_FIELDS:
        units = setup.get(key)
        if isinstance(units, str) and any(b.name == units for b in quest.battles):
            return units
    return None


def _unit_ids(edits: QuestEdits, battle: str) -> dict:
    """{unit id: place} of battle `battle`'s units: the id a scene's DisplayMessage names its speaker by."""
    units = next(b for b in edits.quest.battles if b.name == battle)
    return {u.values["unit_id"]: u.slot for u in entd.battle_units(edits.files[units.units]) if u.occupied}


def unit_lines(edits: QuestEdits, battle: str, slot: int, lengths: es.Lengths) -> list:
    """The lines unit `slot` of battle `battle` says: (scene, line id) of each DisplayMessage of a scene showing that
    battle's units that names it, in the quest's order."""
    ids = [unit_id for unit_id, place in _unit_ids(edits, battle).items() if place == slot]
    out = []
    for ev in edits.quest.events:
        if not ev.script or ev.script not in edits.files or scene_battle(edits.quest, ev.name) != battle:
            continue
        try:
            instructions = es.read_script(edits.files[ev.script], lengths, "enhanced").instructions
        except es.ScriptError:
            continue
        for ins in instructions:
            if ins.opcode == 0x10 and es.operand(ins, "unit") in ids and (ev.name, es.operand(ins, "line")) not in out:
                out.append((ev.name, es.operand(ins, "line")))
    return out


def _remark(edits: QuestEdits, battle: str, slot: int, old: str, new: str, lengths: es.Lengths) -> None:
    """Unit `slot`'s lines' marks as its own name goes from `old` to `new` ("" for none): a line marked `old` marked
    `new` (none when `new` is ""); a name given where there was none (`old` "") given to each line said by no one and
    not marked. A line set to No one while the unit had its name keeps none as the name changes."""
    for scene, line_id in unit_lines(edits, battle, slot, lengths):
        for lines in edits.words.get(scene, {}).values():
            for line in lines:
                if line.line_id != line_id:
                    continue
                mark = mark_of(line.line)
                if mark is not None and old and mark == old:
                    line.line = with_mark(line.line, new if markable(new) else None)
                elif mark is None and not old and new and markable(new) and line.speaker_value in (NO_ONE, 0):
                    line.line = with_mark(line.line, new)


def own_name_of_unit(edits: QuestEdits, scene: str, unit_id: int) -> str:
    """The own name of the unit a scene's DisplayMessage names (its id among the units the scene shows), or ""."""
    battle = scene_battle(edits.quest, scene)
    if battle is None:
        return ""
    slot = _unit_ids(edits, battle).get(unit_id)
    return own_name(edits, battle, slot) if slot is not None else ""


def scene_own_names(edits: QuestEdits, scene: str) -> list:
    """The own names of the units scene `scene` shows, each once, by their places."""
    battle = scene_battle(edits.quest, scene)
    if battle is None:
        return []
    names = next(b for b in edits.quest.battles if b.name == battle).names
    out = []
    for slot in sorted(names):
        if names[slot] not in out:
            out.append(names[slot])
    return out


def set_scene_mark(edits: QuestEdits, name: str, line_id: int, speaker: str) -> None:
    """(His test 69) Line `line_id` of scene `name` names its box `speaker` by a mark, in every language its words are
    in, said by no one (`NO_ONE`) besides. ValueError for a name a mark can't hold."""
    if not markable(speaker):
        raise ValueError(OWN_NAME_NOT_ONE.format(most=sq.MOST_OWN_NAME))
    for lines in edits.words.get(name, {}).values():
        for line in lines:
            if line.line_id == line_id:
                line.line = with_mark(line.line, speaker)
                line.speaker_type, line.speaker_value = SPEAKER_TYPE, NO_ONE


def speaker_moved(edits: QuestEdits, name: str, line_id: int, was: int, now: int) -> None:
    """(His test 69) Line `line_id` of scene `name`, said by unit `was`, made unit `now`'s: marked with the own name of
    `was`, or not marked and said by no one, it is marked with `now`'s (none when it has none); otherwise as it is."""
    before, after = own_name_of_unit(edits, name, was), own_name_of_unit(edits, name, now)
    for lines in edits.words.get(name, {}).values():
        for line in lines:
            if line.line_id != line_id:
                continue
            mark = mark_of(line.line)
            if (mark is not None and before and mark == before) or (mark is None and line.speaker_value in (NO_ONE, 0)):
                line.line = with_mark(line.line, after if markable(after) else None)


@_keeps_reward
def set_start_scene(edits: QuestEdits, battle: str, scene: str, lengths: es.Lengths) -> None:
    """
    The scene battle `battle` plays as it starts ("" for none); the step's
    flag then set by whichever scene ends it. The scene plays with the
    battle's setup (its map, music and units: Mod Studio Framework gives an
    event in a battle the battle's setup with the event's own fields over
    it), so a scene copied from the game's gives up its own: its units would
    be the game's battle's, not the quest's.
    """
    quest = edits.quest
    ev = quest.event_named(battle)
    if ev is None or ev.battle is None:
        raise ValueError(f"{battle} isn't a battle of the quest")
    if scene and (quest.event_named(scene) is None or quest.event_named(scene).battle is not None
                  or scene in (ev.battle.won, ev.battle.lost)):
        raise ValueError(f"{scene} isn't a scene of the quest the battle may start with")
    before = step_of(quest, battle)
    # (1.12.0) Only a battle's start scene shows its objective: the scene it leaves shows none of the quest's.
    old = quest.event_named(ev.battle.start) if ev.battle.start else None
    if old is not None and old.name != scene:
        old.objective_in_script = []
    ev.battle.start = scene
    if scene:
        quest.event_named(scene).setup = {}
        if ev.battle.objective:
            _show_objective(edits, scene, lengths)
    _move_done_flag(edits, before, lengths)


# =============================================================================
# How a battle is won and lost, and its objective (Mod Studio Framework 1.12.0)
# =============================================================================

#: The ways a battle is won, as the page lists them.
WAYS = (sq.ENEMIES, sq.BEATEN, sq.WORN_DOWN, sq.ON_TILE)


def _fight(edits: QuestEdits, battle: str) -> sq.Fight:
    ev = edits.quest.event_named(battle)
    if ev is None or ev.battle is None:
        raise ValueError(f"{battle} isn't a battle of the quest")
    return ev.battle


def set_won_when(edits: QuestEdits, battle: str, way: str, unit: int = 0, share: int = 0, tile=()) -> None:
    """
    How battle `battle` is won: once every enemy is beaten (`side_quests.ENEMIES`), once its unit `unit` (1 to 16)
    is beaten (`BEATEN`) or down to `share` percent of its HP (`WORN_DOWN`), or once Ramza stands on the tile
    `tile` (its x, y and level, 1 its upper level), or every enemy is beaten (`ON_TILE`). The fields another way
    gives are let go.
    """
    if way not in WAYS:
        raise ValueError(f"{way} isn't a way a battle is won")
    fight = _fight(edits, battle)
    fight.won_by = way
    fight.won_unit = int(unit) if way in (sq.BEATEN, sq.WORN_DOWN) else 0
    fight.share = int(share) if way == sq.WORN_DOWN else 0
    fight.tile = tuple(int(n) for n in tile) if way == sq.ON_TILE else ()


def lost_script(game: Game) -> bytes:
    """The game's game over (event 400) with a line first, shown alone on the screen as event 014's first words are,
    as a won scene's (`won_script`): half a second, the line, until it is read, half a second, then the game over."""
    lengths = game.lengths
    over = es.read_script(game.script(GAME_OVER_SCENE), lengths, "enhanced").instructions
    alone = es.read_script(game.script(WORDS_ALONE_SCENE), lengths, "enhanced").instructions
    box = next(i for i in alone if i.opcode == 0x10)
    head = [es.make(0xF1, lengths, "enhanced", frames=30), es.with_operands(box, "enhanced", line=LOST_LINE),
            es.make(0xE5, lengths, "enhanced", task=es.TASK_MESSAGE), es.make(0xF1, lengths, "enhanced", frames=30)]
    return es.Script("enhanced", head + list(over)).to_bytes()


def set_protect(edits: QuestEdits, game: Optional[Game], battle: str, unit: int) -> None:
    """
    The unit (1 to 16) battle `battle` is lost without, or none (0). A battle that protects one has a scene once it
    is lost, after which the game starts over (Mod Studio Framework gives it what follows, as the game's own lost
    scenes have): made from the game's game over with a line of the quest's first (`lost_script`, its line in every
    language, knowing the event it was copied from), kept while the battle protects one; protecting none, it goes.
    """
    fight = _fight(edits, battle)
    if not unit:
        fight.protect = 0
        if fight.lost:
            _drop(edits, fight.lost)
        fight.lost = ""
        return
    if not fight.lost:
        if game is None:
            raise ValueError("a lost scene is made from the game's: unpack the game first")
        name = free_name(f"{battle} lost", event_names(edits))
        file = file_name(name, ".e", edits.files)
        edits.files[file] = lost_script(game)
        edits.words[name] = {language: [_line(LOST_LINE, LOST_WORDS)] for language in LANGUAGES}
        edits.quest.events.append(sq.QuestEvent(name, file, "", copied_from=GAME_OVER_SCENE))
        fight.lost = name
    fight.protect = int(unit)


def objective_places(script: bytes, lengths: es.Lengths) -> list:
    """Where a script shows an objective: the byte after each DisplayConditions (0x78) whose display is one, 8 or
    more (BattleObjective's key + 8: the game's 31 shows 8, "Defeat all enemies!", its sluice's 368 shows 33, "Open
    the sluice!")."""
    out, at = [], 0
    for ins in es.read_script(script, lengths, "enhanced").instructions:
        if ins.opcode == DISPLAY_CONDITIONS and (es.operand(ins, "display") or 0) >= FIRST_OBJECTIVE:
            out.append(at + 1)
        at += ins.size
    return out


def objective_box(game: Game) -> list:
    """The objective box of the game's opening `OBJECTIVE_SCENE`, its instructions: from the 0x1C before its 0x76 to
    the 0x1C after its 0x77, showing "Defeat all enemies!" (display 8)."""
    instructions = list(es.read_script(game.script(OBJECTIVE_SCENE), game.lengths, "enhanced").instructions)
    first = next(n for n, ins in enumerate(instructions) if ins.opcode == 0x76)
    last = next(n for n, ins in enumerate(instructions) if ins.opcode == 0x77 and n > first)
    while first > 0 and instructions[first].opcode != 0x1C:
        first -= 1
    while last < len(instructions) - 1 and instructions[last].opcode != 0x1C:
        last += 1
    box = instructions[first:last + 1]
    if [es.operand(i, "display") for i in box if i.opcode == DISPLAY_CONDITIONS][:1] != [FIRST_OBJECTIVE]:
        raise ValueError(f"the game's event {OBJECTIVE_SCENE:03d} shows no objective box as it was measured")
    return box


def _show_objective(edits: QuestEdits, scene: str, lengths: es.Lengths, game: Optional[Game] = None) -> None:
    """Scene `scene` shows its battle's objective: where its script shows one (`objective_places`), or, with the
    game, in the game's objective box put in before its end (its flags kept where they are)."""
    ev = edits.quest.event_named(scene)
    places = objective_places(edits.files[ev.script], lengths)
    if not places and game is not None:
        instructions = list(es.read_script(edits.files[ev.script], lengths, "enhanced").instructions)
        marks = _marks(ev, instructions)
        ramza = _ramza_marks(ev, instructions)
        end = len(instructions) - 1
        box = objective_box(game)
        instructions[end:end] = box
        _rewrite(edits, ev, instructions, [(i + len(box) if i >= end else i, place, f) for i, place, f in marks],
                 ramza)
        places = objective_places(edits.files[ev.script], lengths)
    ev.objective_in_script = places


def set_objective(edits: QuestEdits, game: Optional[Game], battle: str, words: str, lengths: es.Lengths) -> None:
    """
    Battle `battle`'s objective in the quest's own words ("" for none: its start shows the game's), which its start
    scene shows (Mod Studio Framework gives the objective a number of its own and the scene's DisplayConditions
    it). A battle without a start scene of its own gets one, a copy of the game's battle start (event 401, which it
    played until then: the same sweep of the camera, its objective the quest's); a start scene showing no objective
    gets the objective box of the game's openings before its end.
    """
    fight = _fight(edits, battle)
    fight.objective = words
    start = edits.quest.event_named(fight.start) if fight.start else None
    if not words:
        if start is not None:
            start.objective_in_script = []
        return
    if start is None:
        if game is None:
            raise ValueError("a start scene is made from the game's: unpack the game first")
        made = make_scene(edits, game, BATTLE_START_SCENE, f"{battle} starts")
        set_start_scene(edits, battle, made, lengths)
        start = edits.quest.event_named(made)
    _show_objective(edits, start.name, lengths, game)


# =============================================================================
# Where the player's units start: a battle's own deploy areas (Mod Studio Framework 1.14.0)
# =============================================================================

#: What a tile clicked can't do to a deploy area, as the page says it.
SQUARE_ELSEWHERE = "The tile {x}, {y} is deploy area {other}'s: pick that area to take it out."
ONE_LEVEL = ("Deploy area {n}'s squares are on the {level} level, and an area's squares are all on one level: change "
             "its level first.")
TOO_MANY_SQUARES = f"A deploy area has up to {sq.MOST_SQUARES} squares."
TOO_WIDE = f"A deploy area's squares fit in {sq.MOST_SPAN} by {sq.MOST_SPAN} squares."
#: (2 November, Zodi's test 45: "my deployment area overlapped on their starting location") A tile where one of the
#: battle's units starts on the field isn't one of a deploy area's squares: none of the game's own 703 deploy areas
#: that have a battle holds one (its records' squads against their battles' units on the field, the add-on file's
#: too), and there the player's unit and that one would share the tile. Said as a tile is clicked (`toggle_square`),
#: and of squares already taken (a unit moved there, a mod opened that has one: `squares_taken`) under the battle's
#: card.
SQUARE_UNIT = "Unit {n} starts on the tile {x}, {y}: your units start on tiles no other unit stands on."
UNIT_ON_SQUARE = ("Unit {n} starts on deploy area {area}'s square {x}, {y}: your units start on tiles no other unit "
                  "stands on.")


def on_field(values: dict) -> bool:
    """A battle's unit on the field as the battle starts: always present or randomly present, not both (both: off the
    field until a scene brings it in; neither: not made; the decompilation's `unit_entd_load`), and not an empty
    place."""
    return bool(values.get("sprite_set")) and bool(values.get("always_present")) != bool(values.get("randomly_present"))


def units_on(block: bytes, x: int, y: int, upper: bool) -> list:
    """The units of the battle `block` (each its place, 1 to 16) that start on the field on the tile `x`, `y` of the
    level `upper`."""
    if not block:
        return []
    return [u.slot + 1 for u in entd.battle_units(block) if on_field(u.values)
            and (int(u.values["x"]), int(u.values["y"])) == (int(x), int(y))
            and bool(u.values["upper_level"]) == bool(upper)]


def squares_taken(areas: list, block: bytes) -> list:
    """What the battle's card says of its deploy areas' squares where one of its units starts on the field
    (`UNIT_ON_SQUARE`), area by area, square by square."""
    said = []
    for n, area in enumerate(areas or []):
        for x, y in area.squares:
            for unit in units_on(block, x, y, area.upper):
                said.append(UNIT_ON_SQUARE.format(n=unit, area=n + 1, x=x, y=y))
    return said


def battle_units_block(edits: QuestEdits, battle: str) -> bytes:
    """The units of the battle event `battle` when they are a battle of the quest's own (its file's bytes), else
    nothing (the game's battle by its number is the game's, unchanged)."""
    fight = _fight(edits, battle)
    if isinstance(fight.units, str):
        own = next((b for b in edits.quest.battles if b.name == fight.units), None)
        if own is not None:
            return edits.files.get(own.units, b"")
    return b""


def deploy_squares_taken(edits: QuestEdits, battle: str) -> list:
    """`squares_taken` of the battle event `battle`'s own deploy areas."""
    fight = _fight(edits, battle)
    return squares_taken(fight.deploy, battle_units_block(edits, battle))


def area_of_squad(squad) -> Optional[sq.DeployArea]:
    """A squad of the game's (`event_scripts.Squad`) as a battle's own deploy area: its squares, as many units as it
    takes (no more than 5, or its squares), the way its units face, its level. None for a squad without tiles."""
    tiles = es.squad_tiles(squad) if squad is not None else []
    squares = list(dict.fromkeys((x, y) for x, y, _level, _facing in tiles
                                 if 0 <= x <= sq.MOST_TILE and 0 <= y <= sq.MOST_TILE))[:sq.MOST_SQUARES]
    if not squares:
        return None
    units = max(1, min(squad.most or sq.MOST_DEPLOY_UNITS, sq.MOST_DEPLOY_UNITS, len(squares)))
    return sq.DeployArea(squares, units, tiles[0][3] & 3, bool(tiles[0][2]))


def set_own_deploy(edits: QuestEdits, battle: str, on: bool, squads: bytes = b"", kept: Optional[list] = None) -> None:
    """
    Whether battle `battle`'s units start on deploy areas of its own (`on`; Mod Studio Framework gives each a squad
    of the program's) or on its setup's, the game's. Its own start as `kept` (the page's, from when they were last
    its), else as the game's its setup names (`area_of_squad`, from the program's `squads`), else one area without
    squares yet. Its setup's stay as they are: where the battle starts when the helper can't give it its own.
    """
    fight = _fight(edits, battle)
    if not on:
        fight.deploy = []
        return
    if fight.deploy:
        return
    if kept:
        fight.deploy = copy.deepcopy(kept)
        return
    ev = edits.quest.event_named(battle)
    areas = []
    for key in DEPLOYS:
        number = ev.setup.get(key) or 0
        area = area_of_squad(su.squad(squads, int(number))) if isinstance(number, int) and number and squads else None
        if area is not None:
            areas.append(area)
    fight.deploy = areas or [sq.DeployArea([])]


def _area(edits: QuestEdits, battle: str, area: int) -> sq.DeployArea:
    fight = _fight(edits, battle)
    if not 0 <= area < len(fight.deploy):
        raise ValueError(f"{battle} has no deploy area {area + 1} of its own")
    return fight.deploy[area]


def toggle_deploy_square(edits: QuestEdits, battle: str, area: int, x: int, y: int, upper: bool = False) -> bool:
    """
    The tile `x`, `y` added to battle `battle`'s own deploy area `area` (0 or 1), or taken out of it if it is one of
    its squares (`toggle_square`). Returns whether the tile is now one of its squares.
    """
    _area(edits, battle, area)
    return toggle_square(_fight(edits, battle).deploy, area, x, y, upper, battle_units_block(edits, battle))


def toggle_square(areas: list, area: int, x: int, y: int, upper: bool = False, units: bytes = b"") -> bool:
    """
    (1.17.0, a battle ground's random battles' too) The tile `x`, `y` added to deploy area `area` of `areas` (0 or 1),
    or taken out of it if it is one of its squares. The first square of an area without any gives it its level
    (`upper`); after it, a tile of the other level can't be added (`ONE_LEVEL`), nor one past 25 squares
    (`TOO_MANY_SQUARES`) or 5 by 5 (`TOO_WIDE`), nor the other area's (`SQUARE_ELSEWHERE`), nor (Zodi's test 45) one
    where a unit of the battle `units` starts on the field (`SQUARE_UNIT`): each raises ValueError, its words the
    page's. How many units start there follows the squares while it is as many as they are (up to 5), and is never
    more than they are. Returns whether the tile is now one of its squares.
    """
    chosen = areas[area]
    square = (int(x), int(y))
    for n, other in enumerate(areas):
        if n != area and square in other.squares:
            raise ValueError(SQUARE_ELSEWHERE.format(x=x, y=y, other=n + 1))
    before = len(chosen.squares)
    following = chosen.units >= before
    if square in chosen.squares:
        chosen.squares.remove(square)
        if chosen.squares:
            chosen.units = min(chosen.units, len(chosen.squares))
        return False
    if chosen.squares and bool(upper) != chosen.upper:
        raise ValueError(ONE_LEVEL.format(n=area + 1, level="upper" if chosen.upper else "lower"))
    standing = units_on(units, square[0], square[1], chosen.upper if chosen.squares else upper)
    if standing:
        raise ValueError(SQUARE_UNIT.format(n=standing[0], x=x, y=y))
    if before >= sq.MOST_SQUARES:
        raise ValueError(TOO_MANY_SQUARES)
    xs = [sx for sx, _sy in chosen.squares] + [square[0]]
    ys = [sy for _sx, sy in chosen.squares] + [square[1]]
    if max(xs) - min(xs) >= sq.MOST_SPAN or max(ys) - min(ys) >= sq.MOST_SPAN:
        raise ValueError(TOO_WIDE)
    if not before:
        chosen.upper = bool(upper)
    chosen.squares.append(square)
    if following or not before:
        chosen.units = min(sq.MOST_DEPLOY_UNITS, len(chosen.squares))
    return True


def set_deploy(edits: QuestEdits, battle: str, area: int, units: Optional[int] = None, facing: Optional[int] = None,
               upper: Optional[bool] = None) -> None:
    """Battle `battle`'s own deploy area `area`: how many units start there (1 to 5, no more than its squares), which
    way they face (0 south, 1 west, 2 north, 3 east), on its squares' upper level or lower (`set_area`)."""
    set_area(_area(edits, battle, area), units, facing, upper)


def set_area(chosen: sq.DeployArea, units: Optional[int] = None, facing: Optional[int] = None,
             upper: Optional[bool] = None) -> None:
    """(1.17.0, a battle ground's random battles' too) A deploy area's fields: how many units start there (1 to 5, no
    more than its squares), which way they face, on its squares' upper level or lower."""
    if units is not None:
        chosen.units = max(1, min(int(units), sq.MOST_DEPLOY_UNITS, max(1, len(chosen.squares))))
    if facing is not None:
        chosen.facing = int(facing) & 3
    if upper is not None:
        chosen.upper = bool(upper)


def add_deploy_area(edits: QuestEdits, battle: str) -> int:
    """A second deploy area of battle `battle`'s own, without squares yet: its index (1)."""
    fight = _fight(edits, battle)
    if not fight.deploy or len(fight.deploy) >= sq.MOST_DEPLOY_AREAS:
        raise ValueError(f"{battle} has one deploy area of its own to add a second to")
    fight.deploy.append(sq.DeployArea([], facing=fight.deploy[0].facing))
    return len(fight.deploy) - 1


def remove_deploy_area(edits: QuestEdits, battle: str, area: int) -> None:
    """Battle `battle`'s own deploy area `area` taken out, of two (its first stays: own deploy areas are one or two)."""
    fight = _fight(edits, battle)
    _area(edits, battle, area)
    if len(fight.deploy) < 2:
        raise ValueError(f"{battle}'s one deploy area stays while its own are used")
    del fight.deploy[area]


def rename_map(quests: dict, old: str, new: str) -> int:
    """A quest map renamed (the Map Editor's Name and title): every quest event fought or shown on it named so.
    Returns how many events were."""
    count = 0
    for edits in (quests or {}).values():
        for ev in edits.quest.events:
            if ev.setup.get("Map") == old:
                ev.setup["Map"] = new
                count += 1
    return count


# =============================================================================
# Words
# =============================================================================

def lines_of(edits: QuestEdits, event: str, language: str = LANGUAGE) -> list:
    return list(edits.words.get(event, {}).get(language, []))


def set_line(edits: QuestEdits, event: str, line_id: int, text: str, language: str = LANGUAGE) -> None:
    """A line's words in one language (the others as they are); a line the event's words haven't in that language
    is added to them, said by no one (`NO_ONE`)."""
    lines = edits.words.setdefault(event, {}).setdefault(language, [])
    for line in lines:
        if line.line_id == line_id:
            line.line = text
            return
    lines.append(_line(line_id, text))
    lines.sort(key=lambda line: line.line_id)


# =============================================================================
# A quest's scene on the Event Editor (C)
# =============================================================================
#
# The Event Editor changes a quest's scene as it changes the game's: its nodes are its script's instructions, its
# Speak nodes' words its lines. A quest's scene keeps its script and words in the quest (`QuestEdits.files` and
# `.words`), and two lists of places in its script that Mod Studio Framework writes numbers into as the game starts
# (its `FlagsInScript`: a quest flag's number; its `ObjectiveInScript`: the battle's objective's): those places follow
# their instructions wherever a change moves them (`scene_marks`, `remark`), and the instructions holding them stay
# as Mod Studio made them (`held_instructions`). (1.30.0) A third, its `RamzaInScript` (the party's Ramza's identity,
# written as the script is handed over), follows its instructions too, but holds none: a node naming Ramza may be
# taken out or changed like any other, and a unit changed from Ramza to another is no longer his.

#: The Speaker table's key a line carries its speaker by (every line of the game's words files has one: type 24).
SPEAKER_TYPE = SPEAKER_KEY


def scene_setup(quest: sq.Quest, name: str) -> dict:
    """
    The setup scene `name` plays with, as Mod Studio Framework gives it:
    a scene a battle plays (as it starts, once it is won or lost) has the
    battle's setup (its map, music and units, the battle's own as its
    EnemyBattle) with the scene's own fields over it, what follows it left
    out; another scene its own. A value may name one of the quest's battles
    or one of the mod's quest maps.
    """
    ev = quest.event_named(name)
    if ev is None:
        return {}
    fight = quest.fight_of(name)
    if fight is None:
        return dict(ev.setup)
    setup = {k: v for k, v in fight.setup.items() if k != "AfterEvent"}
    setup["EnemyBattle"] = fight.battle.units
    setup.update(ev.setup)
    return setup


@dataclass
class Mark:
    """A place in a scene's script Mod Studio Framework writes a number into: the instruction holding it, where in
    it, and the quest flag it is ("" for the battle's objective)."""
    instruction: object
    place: int
    flag: str = ""
    #: (1.30.0) A unit naming Ramza (its RamzaInScript), not a flag or the objective.
    ramza: bool = False


def scene_marks(ev: sq.QuestEvent, instructions: list) -> list:
    """An event's FlagsInScript, ObjectiveInScript and (1.30.0) RamzaInScript as `Mark`s on `instructions` (the script
    as it now reads)."""
    starts = _offsets(instructions)
    out = []

    def mark(at: int, flag: str, ramza: bool = False) -> None:
        index = next((n for n, s in enumerate(starts) if s < at < s + instructions[n].size), None)
        if index is not None:
            out.append(Mark(instructions[index], at - starts[index], flag, ramza))

    for at, flag in ev.flags_in_script:
        mark(at, flag)
    for at in ev.objective_in_script:
        mark(at, "")
    for at in ev.ramza_in_script:
        mark(at, "", True)
    return out


def _names_ramza(instruction, place: int) -> bool:
    """Whether the two bytes at `place` in an instruction (counted from its opcode) hold one of Ramza's identities."""
    operands = bytes(instruction.operands)
    return int.from_bytes(operands[place - 1:place + 1], "little") in sq.RAMZAS if place >= 1 else False


def remark(ev: sq.QuestEvent, marks: list, old: list, new: list) -> None:
    """
    An event's FlagsInScript and ObjectiveInScript where its marks'
    instructions stand in `new`, the script after a change made of `old`'s
    instructions (a node moved, added or taken out keeps every other
    instruction itself); an instruction changed in place (a field of it,
    the script's length the same) keeps its marks while it is still that
    instruction. A mark whose instruction is gone goes. (1.30.0) A Ramza
    mark is kept only while its place still names Ramza: a unit changed to
    another isn't his any more.
    """
    starts = _offsets(new)
    flags, objective, ramza = [], [], []
    for m in marks:
        index = next((n for n, item in enumerate(new) if item is m.instruction), None)
        if index is None and len(new) == len(old):
            was = next((n for n, item in enumerate(old) if item is m.instruction), None)
            if was is not None and new[was].opcode == old[was].opcode:
                index = was
        if index is None:
            continue
        at = starts[index] + m.place
        if m.ramza:
            if _names_ramza(new[index], m.place):
                ramza.append(at)
        elif m.flag:
            flags.append((at, m.flag))
        else:
            objective.append(at)
    ev.flags_in_script = flags
    ev.objective_in_script = objective
    ev.ramza_in_script = ramza


def held_instructions(ev: sq.QuestEvent, instructions: list) -> dict:
    """`{instruction index: what it holds}`: the instructions holding a quest flag's place (its name) or the battle's
    objective's (""), which stay as Mod Studio made them; (1.30.0) never a Ramza's, which a change may take."""
    out = {}
    for m in scene_marks(ev, instructions):
        if m.ramza:
            continue
        index = next(n for n, item in enumerate(instructions) if item is m.instruction)
        out.setdefault(index, m.flag)
    return out


def store_scene_script(edits: QuestEdits, name: str, old: es.Script, new: es.Script,
                       lengths: Optional[es.Lengths] = None) -> list:
    """
    Scene `name`'s script after a change on the Event Editor: its bytes in
    the quest, its flags' and objective's places following their
    instructions (`remark`); with the scripts' lengths, the lines it showed
    and shows no more taken out of its words, in every language. Returns
    the lines taken out.
    """
    ev = edits.quest.event_named(name)
    if ev is None or ev.battle is not None:
        raise ValueError(f"{name} isn't a scene of the quest")
    marks = scene_marks(ev, list(old.instructions))
    edits.files[ev.script] = new.to_bytes()
    remark(ev, marks, list(old.instructions), list(new.instructions))
    gone = []
    if lengths is not None:
        gone = sorted(lines_shown(old.to_bytes(), lengths) - lines_shown(new.to_bytes(), lengths))
        for language, lines in edits.words.get(name, {}).items():
            lines[:] = [line for line in lines if line.line_id not in gone]
    return gone


def next_scene_line(edits: QuestEdits, name: str) -> int:
    """A line id scene `name`'s words have in no language: past its highest (the game's own scenes' run past 300000)."""
    taken = [line.line_id for lines in edits.words.get(name, {}).values() for line in lines]
    return max(taken + [WON_LINE - 1]) + 1


def add_scene_line(edits: QuestEdits, name: str, text: str, like: Optional[int] = None) -> int:
    """A new line of scene `name`'s words, in every language its words are in (English when none): `text`, said as
    line `like` is when it is given (its Speaker row, and its mark), else by no one (`NO_ONE`). Returns its id."""
    line_id = next_scene_line(edits, name)
    words = edits.words.setdefault(name, {})
    model = next((x for x in words.get(LANGUAGE, []) if x.line_id == like), None) if like is not None else None
    for language in sorted(words) or [LANGUAGE]:
        line = _line(line_id, text)
        if model is not None:
            line.speaker_type, line.speaker_value = model.speaker_type, model.speaker_value
            # (His test 69) And the name its mark gives.
            if mark_of(model.line) is not None and mark_of(text) is None:
                line.line = with_mark(text, mark_of(model.line))
        words.setdefault(language, []).append(line)
        words[language].sort(key=lambda x: x.line_id)
    return line_id


def set_scene_words(edits: QuestEdits, name: str, line_id: int, text: str, language: str = LANGUAGE) -> None:
    """A line's words in `language`; in each other language whose words for it were the same as that language's (a
    line written once for all of them), those too. Others keep their own (the game's words in each). (His test 69) A
    line's mark naming its box stays at their start, unless `text` has one."""
    words = edits.words.setdefault(name, {})
    before = next((x.line for x in words.get(language, []) if x.line_id == line_id), None)
    # (His test 69) The name its mark gives kept, unless the words give their own.
    if mark_of(before) is not None and mark_of(text) is None:
        text = with_mark(text, mark_of(before))
    set_line(edits, name, line_id, text, language)
    for other, lines in words.items():
        if other == language:
            continue
        for line in lines:
            if line.line_id == line_id and before is not None and line.line == before:
                line.line = text


def words_apart(edits: QuestEdits, name: str, language: str = LANGUAGE) -> bool:
    """Whether scene `name`'s words in another language say a line otherwise than `language`'s do: a copy of the
    game's keeps the game's words in each; (Zodi, 4 November) a sample says the same in every language until one is
    changed alone (`set_scene_words`)."""
    words = edits.words.get(name, {})
    mine = {x.line_id: x.line for x in words.get(language, [])}
    return any(x.line_id in mine and x.line != mine[x.line_id]
               for other, lines in words.items() if other != language for x in lines)


def set_scene_speaker(edits: QuestEdits, name: str, line_id: int, speaker: int) -> None:
    """Who says line `line_id` of scene `name`, the name over its box: a key of the game's Speaker table (`NO_ONE`,
    1, names no one), in every language its words are in; (his test 69) its mark taken out, which the game reads over
    the row."""
    for lines in edits.words.get(name, {}).values():
        for line in lines:
            if line.line_id == line_id:
                line.speaker_type, line.speaker_value = SPEAKER_TYPE, int(speaker)
                line.line = without_mark(line.line)
