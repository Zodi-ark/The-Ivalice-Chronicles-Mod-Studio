"""
A mod's own jobs and abilities, as the New Content page's Jobs and Abilities
tabs edit them (Zodi's order of 13 November: "the Jobs page"; his choices of
14 November: "Build it as shown", jobs and abilities on two tabs, "What
unlocks it"). His goal since 9 November: "let's add everything to Mod Studio
so users can create their new jobs".

**A job** is a folder of its own in a mod, `ModStudioJobs/<job>/`, holding
`job.json`, and **an ability** a folder `ModStudioAbilities/<ability>/`
holding `ability.json`, each read here as Mod Studio Framework reads it
(`helper/ModStudioEventSetup/JobFile.cs`, `AbilityFile.cs`), each problem
said in its words:

- a job's `Name` (1 to 40 characters), the game's generic job it is `Like`
  (74 to 93: its JP table, and its sprites, portraits and icons wherever it
  has none of its own), its `Record` as the game keeps a job's (49 bytes), its
  `Words` (its Name, its Description, and if it has them its words on Job
  Summary), its `Needs` (up to 6 jobs, each at a level of 1 to 8: what
  unlocks it), its `Skillset` (the game's skillset it is Like, 5 to 23, its
  action abilities, 1 to 16 of the game's or of its mod's own by their
  Names, its reaction, support and movement abilities, up to 6, its own
  words and its icon), and if it has them its `Look`, its `Icon` and its
  `Pictures`;
- an ability's `Name`, the game's action ability it is `Like` (1 to 367: its
  effect, how its user moves and its sound), its `Record` (8 bytes: its JP
  cost in two, its chance to be learned, its kind and flags, four bytes of
  flags for the units the game moves), its `Action` (14 bytes in the game's
  order: Range, Effect Area, Vertical, four of flags, Element, Formula, X, Y,
  Inflict Status, CT, MP Cost) and its `Words`.

The helper numbers each job, skillset and ability itself (`Numbers.json`): a
modder never chooses a number, and Mod Studio writes none.

**The game's own jobs and abilities** (`GameJobs`): the game's program read
as data (never run), its job records, skillset records, ability records and
action records found by the code that reads them (its bytes), as
`dev/research/sidequests/jobs.py` and `abilities.py` measured them. A new job
starts as a copy of one of the game's (`copy_of_job`), a new ability as a
copy of one of the game's (`copy_of_ability`).

**A record's fields** (`NUMBERS`, `equipment`, `statuses`, `elements`,
`innate`): where a job's 49 bytes keep each, measured on his program against
the bundled `data/JobData.xml` (0 of 3,654 numbers differing) and agreeing
with FFTPatcher's `Datatypes/Job/Equipment.cs` (Glain, GPL-3, read for
facts); an ability's 8 bytes as the bundled `data/loader_structures/
ABILITY_COMMON_DATA.cs` lays them out, held to his program (0 of 512
differing).

Nothing here imports Qt.
"""
from __future__ import annotations

import copy
import json
import re
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from . import constants as c
from . import helper_json as hj

# =============================================================================
# The files, as the helper names them and bounds them
# =============================================================================

#: Where a mod keeps its jobs and its abilities, one folder each; the file each holds.
FOLDER, FILE_NAME, FORMAT, VERSION = "ModStudioJobs", "job.json", "Mod Studio job", 2
ABILITY_FOLDER, ABILITY_FILE, ABILITY_FORMAT, ABILITY_VERSION = ("ModStudioAbilities", "ability.json",
                                                                 "Mod Studio ability", 1)
#: A job's record's bytes; the game's generic jobs it may be Like (Squire to Mime); its words' bounds.
RECORD_BYTES, FIRST_LIKE, LAST_LIKE = 0x31, 74, 93
NAME_MOST, DESCRIPTION_MOST, SUMMARY_MOST, SUMMARY_BYTES_MOST = 40, 300, 4000, 16000
#: The game's skillsets a skillset may be Like (the generic jobs' but the Mime's), and whose icon it may show (the
#: Mime's too); how many abilities a skillset holds, and the game's numbers (an action is 1 to 421, a reaction, support
#: or movement ability 422 to 511).
FIRST_SKILLSET, LAST_SKILLSET, LAST_SKILLSET_ICON = 5, 23, 24
MOST_ACTIONS, MOST_OTHERS, FIRST_OTHER, LAST_ABILITY = 16, 6, 0x1A6, 0x1FF
#: What a job needs: how many at most, and the levels a need can ask.
MOST_NEEDS, LEAST_NEED_LEVEL, MOST_NEED_LEVEL = 6, 1, 8
#: (Mod Studio Framework 1.55.2 and 1.56.0, his answer of 16 November: "yes build both mastered job line and yes a job
#: also be able to need one of your own mod's jobs mastered") The word a need's Level is to ask its job mastered (in any
#: case, as the helper's `JobFile.MasteredWord`): every place of its skillset learned.
MASTERED_WORD = "Mastered"
#: A Look's Colors, Textures and Portraits (the helper's bounds).
MOST_PALETTES, PALETTE_COLORS = 5, 16
TEXTURE_ROW_BYTES, TEXTURE_ROWS = 256, 512
UPPER_TEXTURE_BYTES, GAME_LOWER_TEXTURE_BYTES = TEXTURE_ROW_BYTES * TEXTURE_ROWS, TEXTURE_ROW_BYTES * 464
MOST_PORTRAITS, PART_NAME_MOST = 5, 64
#: (Mod Studio Framework 1.54.0) A Look's Frames: the game's two kinds of human frames, Type 1 and Type 2 (the helper's
#: `JobFile.Type1Frames` and `Type2Frames`).
TYPE1_FRAMES, TYPE2_FRAMES = 1, 2
PALETTE_ORDINALS = ("first", "second", "third", "fourth", "fifth")
#: Where a job's own art's part lists are in its mod (the helper's `JobFile.PortraitsFolder` and `JobArt`'s).
PORTRAITS_FOLDER = "FFTIVC/data/enhanced/ui/ffto/common/face/textureparts"
ICON_FOLDER = "FFTIVC/data/enhanced/ui/ffto/icon/job/textureparts"
COMMAND_FOLDER = "FFTIVC/data/enhanced/ui/ffto/icon/job_comm/textureparts"
PICTURE_FOLDER = "FFTIVC/data/enhanced/ui/ffto/icon/job_visual/textureparts"
#: An ability's records' bytes; the game's action abilities it may be Like.
ABILITY_RECORD_BYTES, ACTION_BYTES, ABILITY_FIRST_LIKE, ABILITY_LAST_LIKE = 8, 14, 1, 367
#: What the helper can give among every mod at once (`Numbers.json`): jobs (a free skillset each), abilities (549 to
#: 1023) and jobs with a look of their own (the pairs of sprite numbers).
MOST_JOBS, MOST_ABILITIES, MOST_LOOKS = 58, 475, 38
#: A file's size the reader takes as given, where the page checks a job before its files are written.
ANY_SIZE = -1
#: What a file's name in a job's folder can't hold (the helper's `NotInAName` and Windows' own).
_NOT_IN_A_FILE_NAME = set('/\\:"<>|*?') | {chr(n) for n in range(32)}


def _whole(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _raw(d, name: str) -> str:
    """A field as the helper says it (its JSON, cut at 77 characters past 80), "nothing" when it isn't there."""
    if not isinstance(d, dict) or not hj.has(d, name):
        return "nothing"
    return _raw_of(hj.get(d, name))


def _raw_of(value) -> str:
    raw = json.dumps(value, ensure_ascii=False)
    return raw[:77] + "..." if len(raw) > 80 else raw


def _control(ch: str) -> bool:
    """.NET's char.IsControl."""
    return ord(ch) < 0x20 or 0x7F <= ord(ch) <= 0x9F


def _word(words, name: str, most: int, bytes_bound: bool = True) -> Optional[str]:
    """A word of a job's or an ability's (the helper's `Word`): text of 1 to `most` characters, no control characters
    but, in a description, up to two line breaks; None when wrong."""
    if not isinstance(words, dict) or not hj.has(words, name):
        return None
    value = hj.get(words, name)
    if not isinstance(value, str):
        return None
    breaks = 0
    for ch in value:
        if ch == "\n":
            breaks += 1
        elif _control(ch):
            return None
    good = 0 < hj.units(value) <= most and breaks <= (2 if most == DESCRIPTION_MOST else 0)
    if bytes_bound:
        good = good and len(value.encode("utf-8", "surrogatepass")) < 1024
    return value if good else None


def good_name(text) -> bool:
    """A job's or an ability's Name: text of 1 to 40 characters, none a control character."""
    return _word({"Name": text}, "Name", NAME_MOST) is not None


def good_description(text) -> bool:
    return _word({"Description": text}, "Description", DESCRIPTION_MOST) is not None


def good_summary(text) -> bool:
    """A job's words on Job Summary (the helper's `SummaryWords`): 1 to 4,000 characters, no control characters but
    line breaks, 16,000 bytes at the most as the game keeps them."""
    return (isinstance(text, str) and not any(ch != "\n" and _control(ch) for ch in text)
            and 0 < hj.units(text) <= SUMMARY_MOST
            and len(text.encode("utf-8", "surrogatepass")) <= SUMMARY_BYTES_MOST)


def good_part_name(name) -> bool:
    """A part list's name (the helper's `IsPortraitName`): 1 to 64 of the letters a to z (either case), the digits
    and _."""
    return isinstance(name, str) and re.fullmatch(r"[A-Za-z0-9_]{1,64}", name) is not None


def _byte_list(d, name: str, count: int) -> Optional[bytes]:
    value = hj.get(d, name)
    if not isinstance(value, list) or len(value) != count or not all(_whole(b) and 0 <= b <= 255 for b in value):
        return None
    return bytes(value)


# =============================================================================
# A job, as its file gives it
# =============================================================================

@dataclass
class Need:
    """One of the jobs a job needs: one of the game's generic jobs (`job`, 74 to 93) or another of its own mod's by
    its Name (`own`; `job` is 0 then), at a level of 1 to 8; or (his answer of 16 November) mastered (`mastered`: every
    place of its skillset learned; `level` is then 8), written "Level": "Mastered"."""
    job: int = 0
    own: str = ""
    level: int = 1
    mastered: bool = False

    def to_json(self) -> dict:
        return {"Job": self.own if self.own else self.job, "Level": MASTERED_WORD if self.mastered else self.level}


@dataclass
class ModJob:
    """A job as its file gives it (see the module's notes). `actions` holds a number for one of the game's abilities
    and a text for one of the mod's own (its Name); `summary` is "" where the file gives none; `look`, `icon`,
    `skillset_icon` and `pictures` are the file's own values, kept as they are read (None where it has none)."""
    name: str
    like: int
    record: bytes
    word_name: str
    description: str
    skillset_like: int
    actions: list
    others: list
    skillset_name: str
    skillset_description: str
    summary: str = ""
    needs: list = field(default_factory=list)
    look: Optional[dict] = None
    icon: object = None
    skillset_icon: object = None
    pictures: Optional[dict] = None

    def to_json(self) -> dict:
        words = {"Name": self.word_name or self.name, "Description": self.description}
        if self.summary:
            words["Summary"] = self.summary
        skillset = {"Like": self.skillset_like}
        if self.skillset_icon is not None:
            skillset["Icon"] = self.skillset_icon
        skillset["Actions"] = list(self.actions)
        skillset["Others"] = list(self.others)
        skillset["Words"] = {"Name": self.skillset_name, "Description": self.skillset_description}
        out = {"Format": FORMAT, "Version": VERSION, "Name": self.name, "Like": self.like,
               "Record": list(self.record), "Words": words}
        if self.needs:
            out["Needs"] = [need.to_json() for need in self.needs]
        out["Skillset"] = skillset
        if self.look is not None:
            out["Look"] = self.look
        if self.icon is not None:
            out["Icon"] = self.icon
        if self.pictures is not None:
            out["Pictures"] = self.pictures
        return out

    def own_actions(self) -> list:
        """The names of the mod's own abilities its skillset holds, in their places' order."""
        return [a for a in self.actions if isinstance(a, str)]


def _one_line_lists(text: str) -> str:
    """Each list of numbers on one line, as Mod Studio writes a record."""
    return re.sub(r"\[\s+([\d,\s]+?)\s+\]", lambda m: "[" + " ".join(m.group(1).split()) + "]", text)


def job_text(job: ModJob) -> str:
    """A job's `job.json`, as Mod Studio writes it."""
    return _one_line_lists(json.dumps(job.to_json(), indent=2, ensure_ascii=False)) + "\n"


def _needs_of(value, name: str) -> tuple:
    """(the needs, "") or (None, why), as the helper's `NeedsOf`."""
    def bad(what: str) -> tuple:
        return None, (f"its Needs {what}: a list of up to {MOST_NEEDS}, each with a Job (one of the game's generic "
                      f"jobs, {FIRST_LIKE} to {LAST_LIKE}, or the Name of another job of this mod) and a Level "
                      f"({LEAST_NEED_LEVEL} to {MOST_NEED_LEVEL}, or {MASTERED_WORD})")
    if not isinstance(value, list):
        return bad("aren't a list")
    if len(value) > MOST_NEEDS:
        return bad(f"are {len(value)}")
    needs = []
    for item in value:
        if not isinstance(item, dict) or not hj.has(item, "Job") or not hj.has(item, "Level"):
            return bad("hold something that isn't a Job with a Level")
        level = hj.get(item, "Level")
        mastered = isinstance(level, str) and level.casefold() == MASTERED_WORD.casefold()
        if mastered:
            level = MOST_NEED_LEVEL
        elif not _whole(level) or not LEAST_NEED_LEVEL <= level <= MOST_NEED_LEVEL:
            return bad(f"ask the level {_raw(item, 'Level')}")
        job = hj.get(item, "Job")
        number, own = 0, ""
        if _whole(job) and FIRST_LIKE <= job <= LAST_LIKE:
            number = job
        else:
            own = _word(item, "Job", NAME_MOST) if isinstance(job, str) else None
            if own is None:
                return bad(f"name the job {_raw(item, 'Job')}")
        if own and own == name:
            return bad("name the job itself")
        if any((n.own == own) if own else (not n.own and n.job == number) for n in needs):
            return bad(f"name {_raw(item, 'Job')} twice")
        needs.append(Need(number, own, level, mastered))
    return needs, ""


def _action_list(skillset) -> Optional[list]:
    """A skillset's Actions (the helper's `ActionList`): 1 to 16 places, each the game's action ability (a whole
    number from 1 to 421) or one of the mod's own by its Name, no two alike; None when it isn't."""
    values = hj.get(skillset, "Actions")
    if not isinstance(values, list) or not 1 <= len(values) <= MOST_ACTIONS:
        return None
    out = []
    for v in values:
        if _whole(v) and 1 <= v < FIRST_OTHER and v not in out:
            out.append(v)
            continue
        if (isinstance(v, str) and 1 <= hj.units(v) <= NAME_MOST and not any(_control(ch) for ch in v)
                and v not in out):
            out.append(v)
            continue
        return None
    return out


def _other_list(skillset) -> Optional[list]:
    values = hj.get(skillset, "Others")
    if not isinstance(values, list) or len(values) > MOST_OTHERS:
        return None
    out = []
    for v in values:
        if not _whole(v) or not FIRST_OTHER <= v <= LAST_ABILITY or v in out:
            return None
        out.append(v)
    return out


def _color(value) -> int:
    """One "#RRGGBB" color as a number; -1 when it isn't one."""
    if not isinstance(value, str) or len(value) != 7 or value[0] != "#":
        return -1
    if not all(ch in "0123456789abcdefABCDEF" for ch in value[1:]):
        return -1
    return int(value[1:], 16)


def _palettes(colors, who: str) -> str:
    """Why a Look's Colors' palettes for a man or a woman aren't good, "" when they are (the helper's `Palettes`)."""
    listed = hj.get(colors, who)
    if not isinstance(listed, list) or not 1 <= len(listed) <= MOST_PALETTES:
        return f"its Look's Colors' {who} isn't a list of 1 to {MOST_PALETTES} palettes"
    for n, palette in enumerate(listed):
        which = f"its Look's Colors' {who}'s {PALETTE_ORDINALS[n]} palette"
        if not isinstance(palette, list) or len(palette) != PALETTE_COLORS:
            return f"{which} isn't a list of {PALETTE_COLORS} colors"
        for value in palette:
            if _color(value) < 0:
                return f"{which} has {_raw_of(value)}, not a color written \"#RRGGBB\""
        if _color(palette[0]) != 0:
            return f"{which} starts with a color that isn't \"#000000\" (the first color is see through)"
    return ""


def _commas(n: int) -> str:
    return f"{n:,}"


def _textures(textures, who: str, folder: str, size_of: Callable) -> str:
    """Why a Look's Textures for a man or a woman aren't good, "" when they are (the helper's `TexturesOf`):
    `size_of` gives a file's size by its path from the mod's folder, None when it isn't there."""
    listed = hj.get(textures, who)
    if not isinstance(listed, list) or len(listed) != 2:
        return (f"its Look's Textures' {who} isn't a list of two file names (its upper texture's and its lower "
                f"texture's)")
    for n, value in enumerate(listed):
        which = f"its Look's Textures' {who}'s {('upper', 'lower')[n]} texture"
        if (not isinstance(value, str) or not value.strip() or value in (".", "..")
                or any(ch in _NOT_IN_A_FILE_NAME for ch in value)):
            return f"{which} is {_raw_of(value)}, not the name of a file in the job's folder"
        size = size_of(f"{FOLDER}/{folder}/{value}")
        if size is None:
            return f"{which}, {value}, isn't in the job's folder"
        if size == ANY_SIZE:
            continue
        if n == 0 and size != UPPER_TEXTURE_BYTES:
            return (f"{which}, {value}, is {_commas(size)} bytes, not {_commas(UPPER_TEXTURE_BYTES)} (512 by 512 "
                    f"pixels at 4 bits a pixel)")
        if n == 1 and not (TEXTURE_ROW_BYTES <= size <= UPPER_TEXTURE_BYTES and size % TEXTURE_ROW_BYTES == 0):
            return (f"{which}, {value}, is {_commas(size)} bytes, not 512 pixels wide at 4 bits a pixel with 1 to "
                    f"512 rows (the game's own are {_commas(GAME_LOWER_TEXTURE_BYTES)} bytes)")
    return ""


def _frames(frames, who: str, look) -> str:
    """(Mod Studio Framework 1.54.0) Why a Look's Frames for a man or a woman aren't good, "" when they are (the helper's
    own words): 1 or 2, and only for one whose Look's Textures give textures of its own."""
    kind = hj.get(frames, who)
    if not _whole(kind) or kind not in (TYPE1_FRAMES, TYPE2_FRAMES):
        return (f"its Look's Frames' {who} is {_raw(frames, who)}, not {TYPE1_FRAMES} or {TYPE2_FRAMES} (Type 1 or "
                f"Type 2 frames)")
    textures = hj.get(look, "Textures") if hj.has(look, "Textures") else None
    if not (isinstance(textures, dict) and hj.has(textures, who)):
        one = who.lower()
        return (f"its Look's Frames give the {one}'s frames, but its Look's Textures give the {one} no textures of its "
                f"own to draw in them")
    return ""


def _portraits(portraits, who: str, size_of: Callable) -> str:
    """Why a Look's Portraits for a man or a woman aren't good, "" when they are (the helper's `PortraitsOf`)."""
    listed = hj.get(portraits, who)
    if not isinstance(listed, list) or not 1 <= len(listed) <= MOST_PORTRAITS:
        return (f"its Look's Portraits' {who} isn't a list of 1 to {MOST_PORTRAITS} names (one a team's colors, the "
                f"first its player's team's)")
    for n, value in enumerate(listed):
        which = f"its Look's Portraits' {who}'s {PALETTE_ORDINALS[n]} portrait"
        if not good_part_name(value):
            return f"{which} is {_raw_of(value)}, not a name of 1 to {PART_NAME_MOST} letters, digits and _"
        if size_of(f"{PORTRAITS_FOLDER}/{value}.utexpt") is None:
            return f"{which}, {value}, isn't in its mod's folder ({PORTRAITS_FOLDER}/{value}.utexpt)"
    return ""


def _art_pick(holder, name: str, which: str, game: Optional[str], first: int, last: int, own: str,
              art_folder: str, size_of: Callable) -> str:
    """Why one of a job's art picks isn't good, "" when it is (the helper's `ArtPick`): absent or null, one of the
    game's (`first` to `last`, where `game` names them; a picture has none), or its own part list's name."""
    if not hj.has(holder, name) or hj.get(holder, name) is None:
        return ""
    value = hj.get(holder, name)
    if game is not None and _whole(value) and first <= value <= last:
        return ""
    if not good_part_name(value):
        if game is None:
            return (f"{which} is {_raw_of(value)}, not the name of {own} part list (1 to {PART_NAME_MOST} letters, "
                    f"digits and _)")
        return (f"{which} is {_raw_of(value)}, not {game} ({first} to {last}) or the name of {own} part list (1 to "
                f"{PART_NAME_MOST} letters, digits and _)")
    if size_of(f"{art_folder}/{value}.utexpt") is None:
        return f"{which}, {value}, isn't in its mod's folder ({art_folder}/{value}.utexpt)"
    return ""


def _there(_path: str) -> int:
    return ANY_SIZE


def read_job_text(text: str, folder: str = "", size_of: Callable = _there) -> tuple:
    """(the job, problems) from a `job.json`'s text, checked as the helper checks it (`JobFile.Read`); the job is
    None when anything is wrong. `folder` is the job's folder's name and `size_of` gives a file of its mod's size by
    its path from the mod's folder (None when it isn't there, `ANY_SIZE` to take it as it is)."""
    try:
        top = hj.loads(text)
    except ValueError as exc:
        return None, [f"its {FILE_NAME} isn't JSON ({exc})"]
    if not isinstance(top, dict):
        return None, [f"its {FILE_NAME} isn't a list of fields"]
    if hj.get(top, "Format") != FORMAT:
        return None, [f"its Format isn't \"{FORMAT}\""]
    version = hj.get(top, "Version")
    if not _whole(version) or version != VERSION:
        return None, [f"its Version is {_raw(top, 'Version')}, not {VERSION}"]
    name = _word(top, "Name", NAME_MOST)
    if name is None:
        return None, [f"its Name is {_raw(top, 'Name')}, not text of 1 to {NAME_MOST} characters"]
    like = hj.get(top, "Like")
    if not _whole(like) or not FIRST_LIKE <= like <= LAST_LIKE:
        return None, [f"its Like is {_raw(top, 'Like')}, not one of the game's generic jobs ({FIRST_LIKE} to "
                      f"{LAST_LIKE})"]
    record = _byte_list(top, "Record", RECORD_BYTES)
    if record is None:
        return None, [f"its Record isn't a list of {RECORD_BYTES} whole numbers from 0 to 255"]
    words = hj.get(top, "Words")
    if not isinstance(words, dict):
        return None, ["it has no Words"]
    word_name = _word(words, "Name", NAME_MOST)
    if word_name is None:
        return None, [f"its Words' Name is {_raw(words, 'Name')}, not text of 1 to {NAME_MOST} characters"]
    description = _word(words, "Description", DESCRIPTION_MOST)
    if description is None:
        return None, [f"its Words' Description is {_raw(words, 'Description')}, not text of 1 to {DESCRIPTION_MOST} "
                      f"characters with up to two line breaks"]
    summary = ""
    if hj.has(words, "Summary") and hj.get(words, "Summary") is not None:
        summary = hj.get(words, "Summary")
        if not good_summary(summary):
            return None, [f"its Words' Summary is {_raw(words, 'Summary')}, not text of 1 to {SUMMARY_MOST} "
                          f"characters"]
    needs = []
    if hj.has(top, "Needs") and hj.get(top, "Needs") is not None:
        needs, why = _needs_of(hj.get(top, "Needs"), name)
        if needs is None:
            return None, [why]
    skillset = hj.get(top, "Skillset")
    if not isinstance(skillset, dict):
        return None, ["it has no Skillset"]
    skillset_like = hj.get(skillset, "Like")
    if not _whole(skillset_like) or not FIRST_SKILLSET <= skillset_like <= LAST_SKILLSET:
        return None, [f"its Skillset's Like is {_raw(skillset, 'Like')}, not one of the generic jobs' skillsets "
                      f"({FIRST_SKILLSET} to {LAST_SKILLSET})"]
    actions = _action_list(skillset)
    if actions is None:
        return None, [f"its Skillset's Actions aren't a list of 1 to {MOST_ACTIONS} different action abilities (whole "
                      f"numbers from 1 to {FIRST_OTHER - 1}, or the names of the mod's own abilities)"]
    others = _other_list(skillset)
    if others is None:
        return None, [f"its Skillset's Others aren't a list of up to {MOST_OTHERS} different reaction, support or "
                      f"movement abilities (whole numbers from {FIRST_OTHER} to {LAST_ABILITY})"]
    set_words = hj.get(skillset, "Words")
    if not isinstance(set_words, dict):
        return None, ["its Skillset has no Words"]
    set_name = _word(set_words, "Name", NAME_MOST)
    if set_name is None:
        return None, [f"its Skillset's Words' Name is {_raw(set_words, 'Name')}, not text of 1 to {NAME_MOST} "
                      f"characters"]
    set_description = _word(set_words, "Description", DESCRIPTION_MOST)
    if set_description is None:
        return None, [f"its Skillset's Words' Description is {_raw(set_words, 'Description')}, not text of 1 to "
                      f"{DESCRIPTION_MOST} characters with up to two line breaks"]
    look = None
    if hj.has(top, "Look"):
        look = hj.get(top, "Look")
        if not isinstance(look, dict):
            return None, ["its Look isn't a list of fields"]
        look_like = hj.get(look, "Like")
        if not _whole(look_like) or not FIRST_LIKE <= look_like <= LAST_LIKE:
            return None, [f"its Look's Like is {_raw(look, 'Like')}, not one of the game's generic jobs ({FIRST_LIKE} "
                          f"to {LAST_LIKE})"]
        for part, what, check in (
                ("Colors", "palettes", lambda held, who: _palettes(held, who)),
                ("Textures", "textures", lambda held, who: _textures(held, who, folder, size_of)),
                ("Frames", "frames", lambda held, who: _frames(held, who, look)),
                ("Portraits", "portraits", lambda held, who: _portraits(held, who, size_of))):
            if not hj.has(look, part):
                continue
            held = hj.get(look, part)
            if not isinstance(held, dict) or not (hj.has(held, "Man") or hj.has(held, "Woman")):
                return None, [f"its Look's {part} isn't a list of fields with a Man's or a Woman's {what}"]
            for who in ("Man", "Woman"):
                if hj.has(held, who):
                    why = check(held, who)
                    if why:
                        return None, [why]
    why = (_art_pick(top, "Icon", "its Icon", "one of the game's generic jobs whose icon it shows", FIRST_LIKE,
                     LAST_LIKE, "its own icon's", ICON_FOLDER, size_of)
           or _art_pick(skillset, "Icon", "its Skillset's Icon", "one of the game's skillsets whose icon it shows",
                        FIRST_SKILLSET, LAST_SKILLSET_ICON, "its own icon's", COMMAND_FOLDER, size_of))
    if why:
        return None, [why]
    pictures = None
    if hj.has(top, "Pictures"):
        pictures = hj.get(top, "Pictures")
        if not isinstance(pictures, dict) or not (hj.has(pictures, "Man") or hj.has(pictures, "Woman")):
            return None, ["its Pictures isn't a list of fields with a Man's or a Woman's picture"]
        for who in ("Man", "Woman"):
            why = _art_pick(pictures, who, f"its Pictures' {who}", None, 0, 0, "its own picture's", PICTURE_FOLDER,
                            size_of)
            if why:
                return None, [why]
    icon = hj.get(top, "Icon") if hj.has(top, "Icon") else None
    skillset_icon = hj.get(skillset, "Icon") if hj.has(skillset, "Icon") else None
    return ModJob(name, like, record, word_name, description, skillset_like, actions, others, set_name,
                  set_description, summary, needs, _plain(look), icon, skillset_icon, _plain(pictures)), []


def _plain(value):
    """A value read by `helper_json` as plain lists and dicts, to be written again as it is."""
    if isinstance(value, dict):
        return {key: _plain(v) for key, v in hj.pairs(value)}
    if isinstance(value, list):
        return [_plain(v) for v in value]
    return value


def needs_between(jobs: list) -> list:
    """A mod's jobs' needs of each other held to the mod's jobs (the helper's `NeedsBetween`): a job that needs one
    by a name none of the mod's jobs has is taken out of `jobs`, until every name is one of those left; then every
    job in a ring. Returns `[(the job's name, what is said)]`."""
    said = []
    again = True
    while again:
        again = False
        for k in range(len(jobs) - 1, -1, -1):
            for need in jobs[k].needs:
                if need.own and not any(j.name == need.own for j in jobs):
                    said.append((jobs[k].name, f"its Needs name {need.own}, which isn't a job this mod gives"))
                    del jobs[k]
                    again = True
                    break

    def reaches(start: ModJob, to: ModJob, seen: set) -> bool:
        for need in start.needs:
            if not need.own:
                continue
            if need.own == to.name:
                return True
            if need.own in seen:
                continue
            seen.add(need.own)
            following = next((j for j in jobs if j.name == need.own), None)
            if following is not None and reaches(following, to, seen):
                return True
        return False
    ringed = [j for j in jobs if reaches(j, j, set())]
    for job in ringed:
        said.append((job.name, "its Needs go round in a ring (a job it needs needs it in turn)"))
        jobs.remove(job)
    if ringed:
        said.extend(needs_between(jobs))
    return said


def _size_in(mod_folder) -> Callable:
    def size_of(path: str):
        file = Path(mod_folder) / path
        return file.stat().st_size if file.is_file() else None
    return size_of


def read_mod_jobs(mod_folder) -> list:
    """Every job of a mod, in its folders' order: (folder, the job or None, problems); a job named as an earlier one
    of the mod is left out, and so is one whose Needs name a job the mod doesn't give or go round in a ring (the
    helper's `ReadMod`)."""
    root = Path(mod_folder) / FOLDER
    out = []
    if not root.is_dir():
        return out
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
        job, problems = read_job_text(text, sub.name, _size_in(mod_folder))
        if job is not None and job.name in names:
            job, problems = None, [f"another of the mod's jobs is named {job.name}"]
        if job is not None:
            names.add(job.name)
        out.append((sub.name, job, problems))
    kept = [job for _folder, job, _problems in out if job is not None]
    for name, said in needs_between(kept):
        for n, (folder, job, problems) in enumerate(out):
            if job is not None and job.name == name:
                out[n] = (folder, None, [said])
    return out


# =============================================================================
# An ability, as its file gives it
# =============================================================================

@dataclass
class ModAbility:
    """An ability as its file gives it (see the module's notes)."""
    name: str
    like: int
    record: bytes
    action: bytes
    word_name: str
    description: str

    def to_json(self) -> dict:
        return {"Format": ABILITY_FORMAT, "Version": ABILITY_VERSION, "Name": self.name, "Like": self.like,
                "Record": list(self.record), "Action": list(self.action),
                "Words": {"Name": self.word_name or self.name, "Description": self.description}}


def ability_text(ability: ModAbility) -> str:
    """An ability's `ability.json`, as Mod Studio writes it."""
    return _one_line_lists(json.dumps(ability.to_json(), indent=2, ensure_ascii=False)) + "\n"


def read_ability_text(text: str) -> tuple:
    """(the ability, problems) from an `ability.json`'s text, checked as the helper checks it (`AbilityFile.Read`);
    the ability is None when anything is wrong."""
    try:
        top = hj.loads(text)
    except ValueError as exc:
        return None, [f"its {ABILITY_FILE} isn't JSON ({exc})"]
    if not isinstance(top, dict):
        return None, [f"its {ABILITY_FILE} isn't a list of fields"]
    if hj.get(top, "Format") != ABILITY_FORMAT:
        return None, [f"its Format isn't \"{ABILITY_FORMAT}\""]
    version = hj.get(top, "Version")
    if not _whole(version) or version != ABILITY_VERSION:
        return None, [f"its Version is {_raw(top, 'Version')}, not {ABILITY_VERSION}"]
    name = _word(top, "Name", NAME_MOST, False)
    if name is None:
        return None, [f"its Name is {_raw(top, 'Name')}, not text of 1 to {NAME_MOST} characters"]
    like = hj.get(top, "Like")
    if not _whole(like) or not ABILITY_FIRST_LIKE <= like <= ABILITY_LAST_LIKE:
        return None, [f"its Like is {_raw(top, 'Like')}, not one of the game's action abilities "
                      f"({ABILITY_FIRST_LIKE} to {ABILITY_LAST_LIKE})"]
    record = _byte_list(top, "Record", ABILITY_RECORD_BYTES)
    if record is None:
        return None, [f"its Record isn't a list of {ABILITY_RECORD_BYTES} whole numbers from 0 to 255"]
    action = _byte_list(top, "Action", ACTION_BYTES)
    if action is None:
        return None, [f"its Action isn't a list of {ACTION_BYTES} whole numbers from 0 to 255"]
    words = hj.get(top, "Words")
    if not isinstance(words, dict):
        return None, ["it has no Words"]
    word_name = _word(words, "Name", NAME_MOST, False)
    if word_name is None:
        return None, [f"its Words' Name is {_raw(words, 'Name')}, not text of 1 to {NAME_MOST} characters"]
    description = _word(words, "Description", DESCRIPTION_MOST, False)
    if description is None:
        return None, [f"its Words' Description is {_raw(words, 'Description')}, not text of 1 to {DESCRIPTION_MOST} "
                      f"characters with up to two line breaks"]
    return ModAbility(name, like, record, action, word_name, description), []


def read_mod_abilities(mod_folder) -> list:
    """Every ability of a mod, in its folders' order: (folder, the ability or None, problems); one named as an
    earlier one of the mod is left out (the helper's `ReadMod`)."""
    root = Path(mod_folder) / ABILITY_FOLDER
    out = []
    if not root.is_dir():
        return out
    names = set()
    for sub in sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.name):
        file = sub / ABILITY_FILE
        if not file.is_file():
            continue
        try:
            text = hj.read_text(file)
        except OSError as exc:
            out.append((sub.name, None, [f"it can't be read ({exc})"]))
            continue
        ability, problems = read_ability_text(text)
        if ability is not None and ability.name in names:
            ability, problems = None, [f"another of the mod's abilities is named {ability.name}"]
        if ability is not None:
            names.add(ability.name)
        out.append((sub.name, ability, problems))
    return out


# =============================================================================
# The mod's jobs and abilities as the page edits them
# =============================================================================

@dataclass
class JobArt:
    """(The build's second part) A job's own art as the Jobs tab holds it, Export writing its files
    (`job_looks.art_files`): each sex's textures (`{"Man": (upper, lower)}`, as g2d.dat keeps a sprite's), each sex's
    portraits (`{"Man": [(face sheet as a PNG, its parts)]}`, 1 to 5, one a team's colors, the first the player's
    team's), its icon and its skillset's icon (PNGs, empty where it has none of its own) and each sex's job screen art
    (`{"Man": PNG}`; none is no art)."""
    textures: dict = field(default_factory=dict)
    portraits: dict = field(default_factory=dict)
    icon: bytes = b""
    command: bytes = b""
    pictures: dict = field(default_factory=dict)
    #: (Mod Studio Framework 1.54.0, his 8th note of 14 November) The frames each sex's own textures are drawn for,
    #: where told or picked (`{"Man": 2}`: Type 2; else the job's Like's); written as its Look's Frames where they
    #: differ from its Like's (`job_looks.written_job`).
    frames: dict = field(default_factory=dict)
    #: Each sex's classic sprite its textures were made from this session, and whether they were smoothed
    #: (`{"Man": (classic_sprites.Classic, True)}`), for Smooth the edges; not written.
    classic: dict = field(default_factory=dict)
    #: (17 November 2026; his second point of 16 November: "New Jobs sprites should be able to have this as well") Each
    #: sex's own textures at a bigger size, where the figure given was bigger: `{"Man": (scale, upper, lower)}`, 2 to
    #: 8 times the game's size in the same color numbers; its `textures` are then that picture made the game's size.
    #: Export names them by the job in the mod's `ModStudioTextures.json` (`job_looks.big_sheets`), where Mod Studio
    #: Framework reads them and shows them in the game at the same size on the screen.
    big: dict = field(default_factory=dict)
    #: (The thirtieth session; his choices of 17 November: tied to one palette, up to 4 times, Replace... keeps an
    #: image's own colors) Each sex's own colors where the figure given had them: `{"Man": (scale, upper's, lower's,
    #: the palette's 16 words)}`, red, green and blue a pixel at `scale` times the game's size (its `big` scale, or 1),
    #: given in its first palette; Export names a sheet of more colors for each texture (`job_looks.big_sheets`).
    own: dict = field(default_factory=dict)

    def any(self) -> bool:
        return bool(self.textures or self.portraits or self.icon or self.command or self.pictures)


@dataclass
class JobEdit:
    """One of the mod's jobs as the Jobs tab edits it: its folder, the job and (the second part) its own art. Its
    file's names of its own art (its Look's Textures and Portraits, its own Icon, its Skillset's own Icon, its
    Pictures) aren't kept in the job: Export names them again (`job_looks.written_job`)."""
    folder: str
    job: ModJob
    art: JobArt = field(default_factory=JobArt)


@dataclass
class AbilityEdit:
    """One of the mod's abilities as the Abilities tab edits it: its folder and the ability."""
    folder: str
    ability: ModAbility


def copied(edits: dict) -> dict:
    """Copies of the page's jobs or abilities, for an export running beside the page."""
    return copy.deepcopy(edits)


def folder_for(name: str) -> str:
    """The folder a job or an ability is written in: its name's letters, digits, spaces, underscores and hyphens
    (what a folder's name may hold on any computer), anything else left out."""
    kept = "".join(ch if (ch.isalnum() and ch.isascii()) or ch in " _-" else " " for ch in name)
    return " ".join(kept.split())[:64].strip() or "Job"


def free_folder(name: str, taken) -> str:
    """`folder_for(name)`, or it numbered past the folders `taken` (two names that differ only in what a folder can't
    hold)."""
    stem = folder_for(name)
    lowered = {t.lower() for t in taken}
    if stem.lower() not in lowered:
        return stem
    n = 2
    while f"{stem[:60]} {n}".lower() in lowered:
        n += 1
    return f"{stem[:60]} {n}"


def free_name(wanted: str, taken) -> str:
    """`wanted`, or it numbered past the names `taken` ("New Job 2")."""
    stem = wanted[:NAME_MOST - 4]
    if stem not in taken:
        return stem
    n = 2
    while f"{stem} {n}" in taken:
        n += 1
    return f"{stem} {n}"


def job_named(jobs: dict, name: str) -> Optional[JobEdit]:
    return next((e for e in jobs.values() if e.job.name == name), None)


def ability_named(abilities: dict, name: str) -> Optional[AbilityEdit]:
    return next((e for e in abilities.values() if e.ability.name == name), None)


def rename_job(jobs: dict, edit: JobEdit, name: str) -> None:
    """A job given another name: its words' name with it when it was the same, and every job of the mod that needs
    it."""
    old = edit.job.name
    if edit.job.word_name in ("", old):
        edit.job.word_name = name
    edit.job.name = name
    for other in jobs.values():
        for need in other.job.needs:
            if need.own == old:
                need.own = name


def remove_job(jobs: dict, edit: JobEdit) -> None:
    """A job out of the mod: no job of the mod needs it after."""
    jobs.pop(edit.folder, None)
    for other in jobs.values():
        other.job.needs = [need for need in other.job.needs if need.own != edit.job.name]


def rename_ability(jobs: dict, edit: AbilityEdit, name: str) -> None:
    """An ability given another name: its words' name with it when it was the same, and its place in every skillset
    of the mod's jobs that holds it."""
    old = edit.ability.name
    if edit.ability.word_name in ("", old):
        edit.ability.word_name = name
    edit.ability.name = name
    for other in jobs.values():
        other.job.actions = [name if a == old else a for a in other.job.actions]


def skillsets_with(jobs: dict, name: str) -> list:
    """The mod's jobs whose skillsets hold the mod's own ability `name`, in the jobs' order."""
    return [e for e in jobs.values() if name in e.job.actions]


def only_action_of(jobs: dict, name: str) -> list:
    """The mod's jobs whose skillset holds the ability `name` and no other action ability (a skillset has one at the
    least, so the ability can't be taken out of the mod until they have another)."""
    return [e for e in jobs.values() if e.job.actions == [name]]


def remove_ability(jobs: dict, abilities: dict, edit: AbilityEdit) -> None:
    """An ability out of the mod, and out of every skillset of the mod's jobs that holds it (none of which it is the
    only action ability of: `only_action_of`)."""
    abilities.pop(edit.folder, None)
    for other in jobs.values():
        other.job.actions = [a for a in other.job.actions if a != edit.ability.name]


def job_problems(jobs: dict, abilities: dict, edit: JobEdit, size_of: Callable = _there) -> list:
    """What Mod Studio Framework would say of the job as Export writes it: its file read as the helper reads it, its
    Needs held to the mod's jobs (`needs_between`), and each of its skillset's own abilities one the mod gives
    (`AbilityPlan`'s words). (The second part) The job as Export writes it, its own art named and its files there
    (`job_looks.written_job`, `art_files`)."""
    from . import job_looks as jl
    art = {path.lower(): size for path, size in jl.art_paths(edit, "").items()}

    def size_with_art(path: str):
        wanted = path.replace("\\", "/").lower()
        return art[wanted] if wanted in art else size_of(path)
    job, problems = read_job_text(job_text(jl.written_job(edit, "")), edit.folder, size_with_art)
    if job is None:
        return problems
    out = []
    if any(e is not edit and e.job.name == edit.job.name for e in jobs.values()):
        out.append(f"another of the mod's jobs is named {edit.job.name}")
    read = [copy.deepcopy(e.job) for e in jobs.values()]
    out.extend(said for name, said in needs_between(read) if name == edit.job.name)
    given = {e.ability.name for e in abilities.values()}
    for name in edit.job.own_actions():
        if name not in given:
            out.append(f"its skillset leaves out {name}: the mod has no ability of that name that can be added")
    return out


def ability_problems(abilities: dict, edit: AbilityEdit) -> list:
    """What Mod Studio Framework would say of the ability as Export writes it."""
    ability, problems = read_ability_text(ability_text(edit.ability))
    if ability is None:
        return problems
    if any(e is not edit and e.ability.name == edit.ability.name for e in abilities.values()):
        return [f"another of the mod's abilities is named {edit.ability.name}"]
    return []


def write_job(mod_root, edit: JobEdit, mod_id: str = "", frames_of=None) -> list:
    """Writes the job into `<mod_root>/ModStudioJobs/<folder>/job.json` and (the second part) its own art's files, named
    of the mod (`mod_id`) and the job (`job_looks.written_job`, `art_files`; its own textures with the lines the game
    would draw past a frame's pieces cleared where `frames_of` reads the game's frames). Returns the paths written."""
    from . import job_looks as jl
    root = Path(mod_root)
    folder = root / FOLDER / edit.folder
    folder.mkdir(parents=True, exist_ok=True)
    (folder / FILE_NAME).write_text(job_text(jl.written_job(edit, mod_id)), encoding="utf-8")
    written = [f"{FOLDER}/{edit.folder}/{FILE_NAME}"]
    for rel, data in jl.art_files(edit, mod_id, frames_of).items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        written.append(rel)
    return written


def write_ability(mod_root, edit: AbilityEdit) -> list:
    """Writes the ability into `<mod_root>/ModStudioAbilities/<folder>/ability.json`. Returns the paths written."""
    folder = Path(mod_root) / ABILITY_FOLDER / edit.folder
    folder.mkdir(parents=True, exist_ok=True)
    (folder / ABILITY_FILE).write_text(ability_text(edit.ability), encoding="utf-8")
    return [f"{ABILITY_FOLDER}/{edit.folder}/{ABILITY_FILE}"]


def read_mod(mod_root) -> tuple:
    """The mod's jobs and abilities as the page has them: (`[(folder, JobEdit or None, problems)]`, `[(folder,
    AbilityEdit or None, problems)]`), each in its folders' order, as Mod Studio Framework reads them. (The second
    part) A job's own art read back from the mod's files (`job_looks.read_art`); a job whose art can't be read here is
    carried through as it is, and says why."""
    from . import job_looks as jl
    jobs = []
    for folder, job, problems in read_mod_jobs(mod_root):
        if job is None:
            jobs.append((folder, None, problems))
            continue
        art, job, said = jl.read_art(mod_root, folder, job)
        jobs.append((folder, JobEdit(folder, job, art) if not said else None, said))
    abilities = [(folder, AbilityEdit(folder, ability) if ability is not None else None, problems)
                 for folder, ability, problems in read_mod_abilities(mod_root)]
    return jobs, abilities


def named_files(job: ModJob, folder: str) -> list:
    """The files of its mod a job's file names (from the mod's folder): its Look's textures in its own folder, its
    portraits', its icons' and its pictures' part lists. Mod Studio carries them through as they are."""
    out = []
    look = job.look or {}
    for who in ("Man", "Woman"):
        for value in (hj.get(hj.get(look, "Textures") or {}, who) or []):
            if isinstance(value, str):
                out.append(f"{FOLDER}/{folder}/{value}")
        for value in (hj.get(hj.get(look, "Portraits") or {}, who) or []):
            if isinstance(value, str):
                out.append(f"{PORTRAITS_FOLDER}/{value}.utexpt")
        value = hj.get(job.pictures or {}, who)
        if isinstance(value, str):
            out.append(f"{PICTURE_FOLDER}/{value}.utexpt")
    if isinstance(job.icon, str):
        out.append(f"{ICON_FOLDER}/{job.icon}.utexpt")
    if isinstance(job.skillset_icon, str):
        out.append(f"{COMMAND_FOLDER}/{job.skillset_icon}.utexpt")
    return out


# =============================================================================
# The game's own jobs, skillsets and abilities, from its program (read as data, never run)
# =============================================================================

class JobsError(ValueError):
    """The game's jobs can't be read from a program; the message says why, in words."""


#: The code that reads each table (`dev/research/sidequests/jobs.py`, `abilities.py`), found by its bytes, the table's
#: place read where the `( )` is: the job records (174 of 49 bytes; a distance from the instruction's end), the
#: skillset records (176 of 25; from the program's start), the ability records (512 of 8; from the program's start)
#: and the action records the game builds its table from (368 of 20; a distance).
_CODE = {
    "jobs": "41 BB AE 00 00 00 4C 8D 35 ( ?? ?? ?? ?? ) 66 41 3B D3",
    "skillsets": "48 63 C1 4C 8D 15 ?? ?? ?? ?? 4C 6B C0 19 41 8B C1 99 83 E2 07 03 C2 8B C8 83 E0 07 C1 F9 03 2B C2 "
                 "48 63 C9 49 03 C8 42 0F B6 94 11 ( ?? ?? ?? ?? )",
    "abilities": "48 8D 0D ?? ?? ?? ?? 48 8D 81 ( ?? ?? ?? ?? ) 4A 8D 04 C8",
    "actions": "41 B8 C0 1C 00 00 48 8D 15 ( ?? ?? ?? ?? ) 48 8D 0D ?? ?? ?? ?? E8",
}
_RIP = ("jobs", "actions")
JOB_COUNT, SKILLSET_BYTES, SKILLSET_COUNT, ABILITY_COUNT, ACTION_RECORD_BYTES = 174, 25, 176, 512, 20
ACTION_COUNT = ABILITY_LAST_LIKE + 1
#: Where a skillset's record keeps its abilities: 16 actions then 6 others, a byte each, a ninth bit each in its first
#: three bytes (the first place the highest bit).
_ACTIONS_AT, _OTHERS_AT = 3, 19


def _pattern(text: str):
    """A regular expression of bytes from hex, `??` for any byte, `(` `)` round the bytes a value is read from."""
    out = b""
    for token in text.split():
        if token == "??":
            out += b"."
        elif token in "()":
            out += token.encode()
        else:
            out += re.escape(bytes([int(token, 16)]))
    return re.compile(out, re.DOTALL)


class GameJobs:
    """The game's job records, skillset records, ability records and action records from its program's bytes (see
    the module's notes); JobsError when its code isn't as measured (another version of the game)."""

    def __init__(self, data: bytes):
        from . import event_setup as su
        try:
            self._sections = su.sections(data)
        except su.SetupError as exc:
            raise JobsError(f"the game's program can't be read ({exc})") from exc
        self._data = data
        code = next((s for s in self._sections if s.name == ".text"), None)
        if code is None:
            raise JobsError("the game's program has no code")
        text = data[code.at:code.at + code.stored]
        self._tables = {}
        for name, pattern in _CODE.items():
            matches = list(_pattern(pattern).finditer(text))
            if len(matches) != 1:
                raise JobsError(f"the game's jobs can't be read from its program (its {name} code is found "
                                f"{len(matches)} times, not once)")
            value = struct.unpack("<i", matches[0].group(1))[0]
            if name in _RIP:
                value += code.address + matches[0].end(1)
            self._tables[name] = value

    def _at(self, address: int, length: int) -> bytes:
        from . import event_setup as su
        at = su.file_offset(self._sections, address)
        if at is None or at + length > len(self._data):
            raise JobsError(f"the game's jobs can't be read from its program (0x{address:X} isn't in it)")
        return self._data[at:at + length]

    def job_record(self, number: int) -> bytes:
        """A job's 49 bytes."""
        if not 0 <= number < JOB_COUNT:
            raise JobsError(f"{number} isn't one of the game's jobs")
        return self._at(self._tables["jobs"] + RECORD_BYTES * number, RECORD_BYTES)

    def skillset(self, number: int) -> tuple:
        """(a skillset's 16 actions, its 6 others), each an ability's number, 0 where a place holds none."""
        if not 0 <= number < SKILLSET_COUNT:
            raise JobsError(f"{number} isn't one of the game's skillsets")
        record = self._at(self._tables["skillsets"] + SKILLSET_BYTES * number, SKILLSET_BYTES)

        def one(place: int, at: int) -> int:
            return record[at] | (0x100 if record[place >> 3] & (0x80 >> (place & 7)) else 0)
        return (tuple(one(n, _ACTIONS_AT + n) for n in range(MOST_ACTIONS)),
                tuple(one(MOST_ACTIONS + n, _OTHERS_AT + n) for n in range(MOST_OTHERS)))

    def ability_record(self, number: int) -> bytes:
        """An ability's 8 bytes."""
        if not 0 <= number < ABILITY_COUNT:
            raise JobsError(f"{number} isn't one of the game's abilities")
        return self._at(self._tables["abilities"] + ABILITY_RECORD_BYTES * number, ABILITY_RECORD_BYTES)

    def action(self, number: int) -> bytes:
        """An action ability's 14 bytes (the game's action record's, without the six every one has after them)."""
        if not 0 <= number < ACTION_COUNT:
            raise JobsError(f"{number} isn't one of the game's action abilities")
        return self._at(self._tables["actions"] + ACTION_RECORD_BYTES * number, ACTION_BYTES)

    def kind(self, number: int) -> int:
        """An ability's kind (its record's low four bits: `ABILITY_KINDS`)."""
        return self.ability_record(number)[KIND_AT] & 0x0F

    def jp_cost(self, number: int) -> int:
        return struct.unpack_from("<H", self.ability_record(number), 0)[0]


_programs: dict = {}


def game_jobs(path) -> GameJobs:
    """The game's jobs from the program at `path`, read once for each size and time of the file. OSError when it
    can't be read, JobsError when its jobs can't be found."""
    path = Path(path)
    stat = path.stat()
    key = (str(path), stat.st_size, stat.st_mtime_ns)
    if key not in _programs:
        _programs.clear()
        _programs[key] = GameJobs(path.read_bytes())
    return _programs[key]


def copy_of_job(game: GameJobs, like: int, name: str, description: str, skillset_name: str,
                skillset_description: str) -> ModJob:
    """A new job: a copy of one of the game's generic jobs (its record, its skillset's abilities in a skillset of
    its own), named `name`, with the words given (the game's own for that job and its skillset). The record's first
    byte, the skillset's number, is the framework's to give: 0 here. The Mime's skillset (Mimic, 24) holds no ability
    and isn't one a skillset may be like (5 to 23), so a job based on the Mime starts with the Squire's (each of the
    other nineteen generic jobs' skillsets holds action abilities: dev/test_mod_jobs.py)."""
    record = bytearray(game.job_record(like))
    skillset = record[SKILLSET_AT]
    record[SKILLSET_AT] = 0
    if not FIRST_SKILLSET <= skillset <= LAST_SKILLSET:
        skillset = FIRST_SKILLSET
    actions, others = game.skillset(skillset)
    actions = [a for a in dict.fromkeys(actions) if 1 <= a < FIRST_OTHER][:MOST_ACTIONS]
    others = [a for a in dict.fromkeys(others) if FIRST_OTHER <= a <= LAST_ABILITY][:MOST_OTHERS]
    return ModJob(name, like, bytes(record), name, description, skillset, actions, others, skillset_name,
                  skillset_description)


def copy_of_ability(game: GameJobs, like: int, name: str, description: str) -> ModAbility:
    """A new ability: a copy of one of the game's action abilities (its record and its action record), named `name`,
    with the description given (the game's own for that ability)."""
    return ModAbility(name, like, game.ability_record(like), game.action(like), name, description)


# =============================================================================
# A job's record's fields
# =============================================================================

#: Where a job's record keeps its skillset, its four innate abilities (two bytes each), its equipment (5 bytes), its
#: three sets of statuses (5 bytes each) and its four sets of elements (a byte each).
SKILLSET_AT, INNATE_AT, EQUIPMENT_AT = 0, 1, 9
STATUS_SETS_AT = {"InnateStatus": 27, "ImmuneStatus": 32, "StartingStatus": 37}
ELEMENT_SETS_AT = {"AbsorbElements": 42, "NullifyElements": 43, "HalveElements": 44, "WeakElements": 45}
#: The record's numbers the card shows, a byte each: (the Jobs page's name for it, `constants.NUMERIC_FIELDS`, where).
NUMBERS = (("Move", 24), ("Jump", 25), ("CharacterEvasion", 26), ("HPGrowth", 14), ("HPMultiplier", 15),
           ("MPGrowth", 16), ("MPMultiplier", 17), ("SpeedGrowth", 18), ("SpeedMultiplier", 19), ("PAGrowth", 20),
           ("PAMultiplier", 21), ("MAGrowth", 22), ("MAMultiplier", 23))
NUMBER_AT = dict(NUMBERS)
#: The equipment's 40 bits in the record's order (the highest bit of the first byte first), by the Jobs page's names
#: (`constants.EQUIP_ITEMS`); "" for a bit the game gives no kind of item.
EQUIPMENT_BITS = ("Unarmed", "Knife", "NinjaBlade", "Sword", "KnightSword", "Katana", "Axe", "Rod",
                  "Staff", "Flail", "Gun", "Crossbow", "Bow", "Instrument", "Book", "Polearm",
                  "Pole", "Bag", "Cloth", "Shield", "Helmet", "Hat", "HairAdornment", "Armor",
                  "Clothing", "Robe", "Shoes", "Armguard", "Ring", "Armlet", "Cloak", "Perfume",
                  "", "", "", "FellSword", "LipRouge", "", "", "")


def number(job: ModJob, name: str) -> int:
    return job.record[NUMBER_AT[name]]


def set_number(job: ModJob, name: str, value: int) -> None:
    record = bytearray(job.record)
    record[NUMBER_AT[name]] = max(0, min(255, int(value)))
    job.record = bytes(record)


def innate(job: ModJob) -> list:
    """The job's four innate abilities, 0 for none."""
    return list(struct.unpack_from("<4H", job.record, INNATE_AT))


def set_innate(job: ModJob, place: int, ability: int) -> None:
    record = bytearray(job.record)
    struct.pack_into("<H", record, INNATE_AT + 2 * place, max(0, min(LAST_ABILITY, int(ability))))
    job.record = bytes(record)


def _bits(data: bytes, names) -> list:
    return [name for n, name in enumerate(names) if name and data[n >> 3] & (0x80 >> (n & 7))]


def _with_bits(data: bytes, names, ticked) -> bytes:
    """`data` with each named bit set where its name is in `ticked`, a bit with no name kept as it is."""
    out = bytearray(data)
    for n, name in enumerate(names):
        if not name:
            continue
        if name in ticked:
            out[n >> 3] |= 0x80 >> (n & 7)
        else:
            out[n >> 3] &= ~(0x80 >> (n & 7)) & 0xFF
    return bytes(out)


def equipment(job: ModJob) -> list:
    """The kinds of item the job can equip, in the Jobs page's order (`constants.EQUIP_ITEMS`)."""
    held = set(_bits(job.record[EQUIPMENT_AT:EQUIPMENT_AT + 5], EQUIPMENT_BITS))
    return [name for name in c.EQUIP_ITEMS if name in held]


def set_equipment(job: ModJob, ticked) -> None:
    record = bytearray(job.record)
    record[EQUIPMENT_AT:EQUIPMENT_AT + 5] = _with_bits(record[EQUIPMENT_AT:EQUIPMENT_AT + 5], EQUIPMENT_BITS,
                                                       set(ticked))
    job.record = bytes(record)


def statuses(job: ModJob, which: str) -> list:
    """One of the job's three sets of statuses (`STATUS_SETS_AT`), in the game's order (`constants.STATUS_FLAGS`)."""
    at = STATUS_SETS_AT[which]
    return _bits(job.record[at:at + 5], c.STATUS_FLAGS)


def set_statuses(job: ModJob, which: str, ticked) -> None:
    at = STATUS_SETS_AT[which]
    record = bytearray(job.record)
    record[at:at + 5] = _with_bits(record[at:at + 5], c.STATUS_FLAGS, set(ticked))
    job.record = bytes(record)


def elements(job: ModJob, which: str) -> list:
    """One of the job's four sets of elements (`ELEMENT_SETS_AT`), in the game's order (`constants.ELEMENT_FLAGS`)."""
    at = ELEMENT_SETS_AT[which]
    return _bits(job.record[at:at + 1], c.ELEMENT_FLAGS)


def set_elements(job: ModJob, which: str, ticked) -> None:
    at = ELEMENT_SETS_AT[which]
    record = bytearray(job.record)
    record[at:at + 1] = _with_bits(record[at:at + 1], c.ELEMENT_FLAGS, set(ticked))
    job.record = bytes(record)


# =============================================================================
# An ability's records' fields
# =============================================================================

#: An ability's record: its JP cost (two bytes), its chance to be learned, its kind (the low four bits) and its flags
#: (the high four), then the four bytes of flags for the units the game moves.
JP_AT, CHANCE_AT, KIND_AT, AI_AT = 0, 2, 3, 4
ABILITY_KINDS = tuple(c.ABILITY_TYPE_XML_VALUES)
#: The record's own flags (bits of its byte 3), by the Abilities page's names (`constants.ABILITY_XML_FLAGS`).
RECORD_FLAGS = {"LearnOnHit": 0x20, "DisplayAbilityName": 0x40, "DontLearnWithJP": 0x80}
#: The 32 flags for the units the game moves, by their bit (the lowest first), as the bundled
#: `data/loader_structures/ABILITY_COMMON_DATA.cs` names them; the Abilities page shows 30 of them
#: (`constants.ABILITY_AI_BEHAVIOR_FLAGS`), the two it has no name for are kept as they are.
AI_BITS = ("TargetAllies", "TargetEnemies", "Unequip", "Stats", "AddStatus", "CancelStatus", "MP", "HP",
           "Silence", "Evadeable", "AffectedByFaith", "RandomHits", "CheckCT_Target", "UndeadReverse", "Reflectable",
           "TargetMap", "PhysicalAttack", "MagicalAttack", "Ranged3Directions", "Melee3Directions", "NonSpearAttack",
           "LinearAttack", "StopAtObstacle", "Arced", "EvadeWithMotion", "Unk_25", "UseWeaponRange",
           "RequireMonsterSkill", "Unk_28", "OnlyHitsEnemies", "OnlyHitsAlliesOrSelf", "UsableByAI")
#: Where an ability's action record keeps each number (`constants.OVERRIDE_SCALAR_FIELDS`' names), its four bytes of
#: flags (`constants.ABILITY_FLAG_DEFS`' four groups) and its elements.
ACTION_AT = {"Range": 0, "EffectArea": 1, "Vertical": 2, "Formula": 8, "X": 9, "Y": 10, "InflictStatus": 11,
             "CT": 12, "MPCost": 13}
ACTION_FLAGS_AT, ACTION_ELEMENT_AT = 3, 7


def jp_cost(ability: ModAbility) -> int:
    return struct.unpack_from("<H", ability.record, JP_AT)[0]


def set_jp_cost(ability: ModAbility, value: int) -> None:
    record = bytearray(ability.record)
    struct.pack_into("<H", record, JP_AT, max(0, min(65535, int(value))))
    ability.record = bytes(record)


def chance(ability: ModAbility) -> int:
    return ability.record[CHANCE_AT]


def set_chance(ability: ModAbility, value: int) -> None:
    record = bytearray(ability.record)
    record[CHANCE_AT] = max(0, min(255, int(value)))
    ability.record = bytes(record)


def record_flags(ability: ModAbility) -> list:
    """The record's own flags set, in the Abilities page's order."""
    return [name for name in c.ABILITY_XML_FLAGS if ability.record[KIND_AT] & RECORD_FLAGS[name]]


def set_record_flags(ability: ModAbility, ticked) -> None:
    record = bytearray(ability.record)
    for name, bit in RECORD_FLAGS.items():
        record[KIND_AT] = (record[KIND_AT] | bit) if name in ticked else (record[KIND_AT] & ~bit & 0xFF)
    ability.record = bytes(record)


def ai_flags(ability: ModAbility) -> list:
    """The flags for the units the game moves that are set, in the Abilities page's order."""
    value = struct.unpack_from("<I", ability.record, AI_AT)[0]
    held = {name for n, name in enumerate(AI_BITS) if value >> n & 1}
    return [name for name in c.ABILITY_AI_BEHAVIOR_FLAGS if name in held]


def set_ai_flags(ability: ModAbility, ticked) -> None:
    """The flags the Abilities page names set as ticked; the two it has no name for kept as they are."""
    value = struct.unpack_from("<I", ability.record, AI_AT)[0]
    for n, name in enumerate(AI_BITS):
        if name not in c.ABILITY_AI_BEHAVIOR_FLAGS:
            continue
        value = (value | (1 << n)) if name in ticked else (value & ~(1 << n) & 0xFFFFFFFF)
    record = bytearray(ability.record)
    struct.pack_into("<I", record, AI_AT, value)
    ability.record = bytes(record)


def action_number(ability: ModAbility, name: str) -> int:
    return ability.action[ACTION_AT[name]]


def set_action_number(ability: ModAbility, name: str, value: int) -> None:
    action = bytearray(ability.action)
    action[ACTION_AT[name]] = max(0, min(255, int(value)))
    ability.action = bytes(action)


def action_flags(ability: ModAbility) -> dict:
    """The action record's 31 flags as the Abilities page ticks them: `{its id: ticked}` (a flag the game keeps the
    other way round ticked where its bit is clear: `nxd_data.unpack_flag_group`)."""
    from . import nxd_data
    out = {}
    for group in range(4):
        out.update(nxd_data.unpack_flag_group(group, ability.action[ACTION_FLAGS_AT + group]))
    return out


def set_action_flag(ability: ModAbility, flag: str, ticked: bool) -> None:
    from . import nxd_data
    group = next(f[2] for f in c.ABILITY_FLAG_DEFS if f[0] == flag)
    states = nxd_data.unpack_flag_group(group, ability.action[ACTION_FLAGS_AT + group])
    states[flag] = bool(ticked)
    packed = nxd_data.pack_flag_group(group, states)
    # The group's bit with no name (Flagset I's second) kept as it is.
    blank = sum(1 << (7 - row) for row, f in enumerate([f for f in c.ABILITY_FLAG_DEFS if f[2] == group]) if f[4])
    action = bytearray(ability.action)
    action[ACTION_FLAGS_AT + group] = (packed & ~blank & 0xFF) | (action[ACTION_FLAGS_AT + group] & blank)
    ability.action = bytes(action)


def action_elements(ability: ModAbility) -> list:
    return [name for name, bit in c.ABILITY_ELEMENT_VALUES if ability.action[ACTION_ELEMENT_AT] & bit]


def set_action_elements(ability: ModAbility, ticked) -> None:
    action = bytearray(ability.action)
    action[ACTION_ELEMENT_AT] = sum(bit for name, bit in c.ABILITY_ELEMENT_VALUES if name in ticked)
    ability.action = bytes(action)


# =============================================================================
# A job's needs and its skillset, as the card changes them
# =============================================================================

def need_choices(jobs: dict, edit: JobEdit) -> list:
    """What the job may still need: `[(a game job's number or a mod's job's name)]`, the game's generic jobs then the
    mod's other jobs, less those it needs already and less a job of the mod's that needs it in turn (a ring)."""
    has_game = {need.job for need in edit.job.needs if not need.own}
    has_own = {need.own for need in edit.job.needs if need.own}
    out = [n for n in range(FIRST_LIKE, LAST_LIKE + 1) if n not in has_game]
    for other in jobs.values():
        if other is edit or other.job.name in has_own or _needs(jobs, other.job, edit.job.name, set()):
            continue
        out.append(other.job.name)
    return out


def _needs(jobs: dict, job: ModJob, name: str, seen: set) -> bool:
    """Whether `job` needs the mod's job `name`, itself or through the mod's jobs it needs."""
    for need in job.needs:
        if not need.own or need.own in seen:
            continue
        if need.own == name:
            return True
        seen.add(need.own)
        following = job_named(jobs, need.own)
        if following is not None and _needs(jobs, following.job, name, seen):
            return True
    return False


def needed_by(jobs: dict, name: str) -> list:
    """The mod's jobs that need the mod's job `name`: `[(the job, its need of it)]` (the level asked, or mastered)."""
    return [(e, need) for e in jobs.values() for need in e.job.needs if need.own == name]
